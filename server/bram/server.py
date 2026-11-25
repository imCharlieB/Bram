"""BRAM Server. Watches and sends messages. Controls nothing."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import signal
import sys
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

from aiohttp import WSCloseCode, WSMsgType, web

from .alerts import Alerts
from .audit import Audit
from .chat import MAX_TEXT, Busy, Chat
from .models.base import ModelError
from .monitors import Monitors
from .pairing import CODE_LIFETIME, Pairing, ensure_certificate
from .settings import Settings
from .watch import NOTABLE, Watcher, named
from .web import ConfigPage
from .world import Event, World

PAIRING = web.AppKey("pairing", Pairing)
AUDIT = web.AppKey("audit", Audit)
HOUSES = web.AppKey("houses", dict)
SOCKETS = web.AppKey("sockets", dict)
ALERTS = web.AppKey("alerts", Alerts)
MONITORS = web.AppKey("monitors", Monitors)
TASKS = web.AppKey("tasks", list)
CHAT = web.AppKey("chat", Chat)
ASKED = web.AppKey("asked", dict)
ASK_TIMEOUT = 12


def _event(house_id: str, raw: object) -> Event:
    if not isinstance(raw, dict):
        raise ValueError("state must be an object")
    values = [raw.get(k) for k in ("entity_id", "kind", "state")]
    if not all(isinstance(v, str) and len(v) <= 255 for v in values):
        raise ValueError("bad state")
    # The house comes from the token, never from the message (E4).
    name = raw.get("name")
    return Event(house_id, *values, name[:100] if isinstance(name, str) else "")


async def _pair(request: web.Request) -> web.Response:
    try:
        secret = (await request.json())["secret"]
    except (ValueError, KeyError, TypeError):
        raise web.HTTPBadRequest from None
    result = request.app[PAIRING].redeem(secret) if isinstance(secret, str) else None
    if result is None:
        raise web.HTTPForbidden
    house_id, token = result
    request.app[AUDIT].record(house_id, "pairing", "paired", "valid one-time code", "ok")
    return web.json_response({"house_id": house_id, "token": token})


async def _feed(request: web.Request) -> web.WebSocketResponse:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    house_id = request.app[PAIRING].house_for(token) if scheme == "Bearer" and token else None
    if house_id is None:
        raise web.HTTPUnauthorized
    audit, sockets = request.app[AUDIT], request.app[SOCKETS]
    ws = web.WebSocketResponse(max_msg_size=1_000_000, heartbeat=30)
    await ws.prepare(request)
    # Only the newest connection counts for a house.
    old = sockets.get(house_id)
    sockets[house_id] = ws
    if old is not None:
        await old.close(code=WSCloseCode.POLICY_VIOLATION, message=b"replaced")
    world, watcher = request.app[HOUSES].setdefault(house_id, _new_house(house_id, audit))
    world.disconnected()
    audit.record(house_id, "feed", "connected", "valid token", "ok")
    await ws.send_json({"type": "hello", "version": version("bram-core")})
    ready, questions = False, set()
    try:
        async for message in ws:
            # Replaced, or unpaired by the owner.
            if sockets.get(house_id) is not ws or request.app[PAIRING].house_for(token) is None:
                break
            if message.type is not WSMsgType.TEXT:
                break
            try:
                data = json.loads(message.data)
                kind = data.get("type") if isinstance(data, dict) else None
                if kind == "snapshot":
                    world.disconnected()
                    world.heartbeat()
                    theirs = data.get("version")
                    world.version = theirs[:20] if isinstance(theirs, str) else ""
                    for event in [_event(house_id, s) for s in data["states"]]:
                        watcher.handle(event)
                        await _belief(ws, world, event)
                    ready = True
                    if request.app.get(ALERTS) is not None:
                        request.app[ALERTS].house_up(house_id, _name(request.app, house_id))
                elif kind == "state" and ready:
                    event = _event(house_id, data.get("state"))
                    watcher.handle(event)
                    await _belief(ws, world, event)
                elif kind in ("escalate", "deescalate") and ready:
                    _escalate(request.app, world.event(data.get("entity_id")), kind)
                elif kind == "result" and ready:
                    waiting = request.app[ASKED].get((house_id, data.get("id")))
                    if waiting is not None and not waiting.done():
                        waiting.set_result(data.get("result"))
                elif kind == "ask" and ready:
                    # Answered on the side, so a slow model never holds up the feed.
                    task = asyncio.create_task(_answer(request.app, ws, house_id, data))
                    questions.add(task)
                    task.add_done_callback(questions.discard)
                elif kind == "heartbeat" and ready:
                    world.heartbeat()
                else:
                    raise ValueError("unexpected message")
            except ConnectionError:
                break
            except (ValueError, KeyError, TypeError):
                await ws.close(code=WSCloseCode.UNSUPPORTED_DATA)
                break
    finally:
        for task in questions:
            task.cancel()
        if sockets.get(house_id) is ws:
            del sockets[house_id]
            world.disconnected()
            audit.record(house_id, "feed", "disconnected", "connection closed", "state unknown")
            # Not when the owner removed the house.
            if request.app.get(ALERTS) is not None and request.app[PAIRING].house_for(token):
                request.app[ALERTS].house_down(house_id, _name(request.app, house_id))
    return ws


async def ask_house(app: web.Application, house_id: str, what: str,
                    entity_id: str = "") -> dict | None:
    """Ask Home Assistant one of its two allowed questions. None if it did not answer."""
    ws = app[SOCKETS].get(house_id)
    if ws is None:
        return None
    key = (house_id, secrets.token_hex(8))
    waiting = app[ASKED][key] = asyncio.get_running_loop().create_future()
    try:
        await ws.send_json({"type": "query", "id": key[1], "what": what, "entity_id": entity_id})
        async with asyncio.timeout(ASK_TIMEOUT):
            result = await waiting
    except (TimeoutError, ConnectionError):
        return None
    finally:
        app[ASKED].pop(key, None)
    return result if isinstance(result, dict) else None


async def _answer(app: web.Application, ws: web.WebSocketResponse, house_id: str,
                  data: dict) -> None:
    question, text, talk = data.get("id"), data.get("text"), data.get("conversation")
    if not all(isinstance(v, str) and len(v) <= n
               for v, n in ((question, 64), (talk, 64), (text, MAX_TEXT))):
        return
    if app.get(CHAT) is None:
        reply = "Chat is not available."
    else:
        try:
            reply = (await app[CHAT].ask(f"ha:{house_id}:{talk}", text, house=house_id)).text
        except Busy:
            reply = "I'm still thinking about something else. Try again in a moment."
        except ModelError:
            reply = "I can't think right now. My model is not answering."
    try:
        await ws.send_json({"type": "answer", "id": question, "text": reply})
    except ConnectionError:
        pass


def _escalate(app: web.Application, event: Event | None, kind: str) -> None:
    """A home alert nobody acknowledged, if the owner turned this on in Home Assistant."""
    if event is None or event.kind not in NOTABLE or app.get(ALERTS) is None:
        return
    if kind == "escalate":
        text = f"{named(NOTABLE[event.kind], event)} Not acknowledged in Home Assistant."
        app[ALERTS].raise_alert(event.house_id, event.entity_id, text, safety=True)
    else:
        app[ALERTS].settle(event.house_id, event.entity_id)


def _name(app: web.Application, house_id: str) -> str:
    return dict(app[PAIRING].houses()).get(house_id, "home")


async def _start(app: web.Application) -> None:
    # A house that does not come back after a server restart is also down.
    for house_id, name in app[PAIRING].houses():
        app[ALERTS].house_down(house_id, name)
    app[TASKS] += [asyncio.create_task(c.listen()) for c in app[ALERTS].channels]
    app[TASKS].append(asyncio.create_task(app[ALERTS].run()))
    app[TASKS].append(asyncio.create_task(app[MONITORS].run()))


async def _stop(app: web.Application) -> None:
    for task in app[TASKS]:
        task.cancel()
    await asyncio.gather(*app[TASKS], return_exceptions=True)


async def _belief(ws: web.WebSocketResponse, world: World, event: Event) -> None:
    """Tell Home Assistant what BRAM now believes. For display only; nothing is stored."""
    await ws.send_json({"type": "belief", "entity_id": event.entity_id,
                        "answer": world.check(event.entity_id)})


def _log_house(houses: list[tuple[str, str]], wanted: str | None) -> str:
    ids = [h[0] for h in houses]
    if wanted is None and len(ids) == 1:
        return ids[0]
    if wanted in ids:
        return wanted
    listing = "\n".join(f"  {i} {name}" for i, name in houses) or "  (none)"
    raise SystemExit(f"Choose a paired house:\n{listing}")


def _new_house(house_id: str, audit: Audit) -> tuple[World, Watcher]:
    world = World(house_id)
    return world, Watcher(world, audit)


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def _shutdown(app: web.Application) -> None:
    for ws in list(app[SOCKETS].values()):
        await ws.close(code=WSCloseCode.GOING_AWAY)


def make_app(pairing: Pairing, audit: Audit, settings: Settings | None = None,
             fingerprint: str = "", alerts: Alerts | None = None,
             clock: Callable[[], float] = time.monotonic) -> web.Application:
    app = web.Application(client_max_size=4096)
    app[PAIRING], app[AUDIT], app[HOUSES], app[SOCKETS] = pairing, audit, {}, {}
    app[ASKED] = {}
    app.router.add_post("/pair", _pair)
    app.router.add_get("/feed", _feed)
    app.router.add_get("/health", _health)
    if settings is not None:
        async def disconnect(house_id: str) -> None:
            ws = app[SOCKETS].get(house_id)
            if ws is not None:
                await ws.close(code=WSCloseCode.POLICY_VIOLATION, message=b"unpaired")

        page = ConfigPage(settings, pairing, audit, fingerprint, lambda: set(app[SOCKETS]),
                          disconnect, alerts,
                          lambda: {k: v[0] for k, v in app[HOUSES].items()}, clock,
                          lambda *a: ask_house(app, *a))
        if alerts is not None:
            app[ALERTS], app[TASKS] = alerts, []
            alerts.channels = [page.ntfy, page.telegram]
            app[MONITORS] = page.monitors
            app.on_startup.append(_start)
            app.on_cleanup.append(_stop)
        app[CHAT] = page.chat
        app.add_routes(page.routes())
    app.on_shutdown.append(_shutdown)
    return app


async def _serve(host: str, port: int, data: Path) -> None:
    context, fingerprint = ensure_certificate(data)
    database = data / "bram.db"
    audit, settings = Audit(database), Settings(database)
    alerts = Alerts(database, audit, lambda channel: settings.channel(channel).get("quiet", {}))
    app = make_app(Pairing(database), audit, settings, fingerprint, alerts)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host, port, ssl_context=context).start()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass
    print(f"BRAM Server listening on port {port} (cannot control anything)")
    try:
        await stop.wait()
    finally:
        await runner.cleanup()


def main() -> None:
    p = argparse.ArgumentParser(prog="bram-server")
    p.add_argument("--data", default="data", type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--host", default="0.0.0.0")  # noqa: S104 - TLS and a token are required
    run.add_argument("--port", type=int, default=8765)
    sub.add_parser("pair").add_argument("--name", required=True)
    sub.add_parser("reset-login")
    sub.add_parser("houses")
    sub.add_parser("unpair").add_argument("house_id")
    log = sub.add_parser("log")
    log.add_argument("house_id", nargs="?")
    log.add_argument("--json", action="store_true")
    args = p.parse_args()
    os.umask(0o077)  # only this user may read the key and database
    _, fingerprint = ensure_certificate(args.data)
    database = args.data / "bram.db"
    if args.command == "run":
        try:
            asyncio.run(_serve(args.host, args.port, args.data))
        except KeyboardInterrupt:
            return
    elif args.command == "pair":
        print(Pairing(database).new_code(args.name, fingerprint))
        print(f"Enter this code in Home Assistant within {CODE_LIFETIME // 60} minutes. "
              "It works once.")
    elif args.command == "reset-login":
        Settings(database).reset_login()
        print("Login removed. Restart the server, then open the config page to make a new one.")
    elif args.command == "houses":
        for house_id, name in Pairing(database).houses():
            print(house_id, name)
    elif args.command == "unpair":
        if not Pairing(database).remove(args.house_id):
            sys.exit("No such house")
        print("Removed.")
    elif args.command == "log":
        for row in Audit(database).entries(_log_house(Pairing(database).houses(), args.house_id)):
            if args.json:
                print(json.dumps(row))
            else:
                at = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(row["at"]))
                print(f"{at}  {row['decision']:<12}  {row['trigger']}: {row['reason']}")


if __name__ == "__main__":
    main()
