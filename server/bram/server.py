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
from zoneinfo import ZoneInfo

from aiohttp import WSCloseCode, WSMsgType, web

from .alerts import Alerts
from .audit import Audit
from .chat import MAX_TEXT, Busy, Chat
from .findings import Findings
from .history import History, number
from .models.base import ModelError
from .monitors import Monitors
from .pairing import CODE_LIFETIME, Pairing, ensure_certificate
from .personality import MODES
from .settings import Settings
from .watch import NOTABLE, Watcher, named
from .web import ConfigPage, _older
from .world import Event, World

PAIRING = web.AppKey("pairing", Pairing)
AUDIT = web.AppKey("audit", Audit)
HOUSES = web.AppKey("houses", dict)
SOCKETS = web.AppKey("sockets", dict)
ALERTS = web.AppKey("alerts", Alerts)
MONITORS = web.AppKey("monitors", Monitors)
TASKS = web.AppKey("tasks", list)
CHAT = web.AppKey("chat", Chat)
CONFIG = web.AppKey("config", ConfigPage)
ASKED = web.AppKey("asked", dict)
SETTINGS = web.AppKey("settings", Settings)
ASK_TIMEOUT = 12
HISTORY = web.AppKey("history", History)
FINDINGS = web.AppKey("findings", Findings)
NUMBERS = ("now", "humidity", "target", "low", "high")
WORDS = ("unit", "action", "mode", "preset", "fan")
MAX_PAGES = 60
PRINTERS = web.AppKey("printers", dict)
WATCHING = web.AppKey("watching", dict)
WATCH_KINDS = ("rule", "printer", "night", "problem")
PRINTER_STATES = ("printing", "paused", "finished", "failed", "stopped", "idle", "off",
                  "unknown", "failing")
PRINTER_NUMBERS = ("progress", "left", "nozzle", "nozzle2", "nozzle_target", "nozzle2_target",
                   "bed", "bed_target", "chamber", "weight")


def _detail(raw: object) -> dict:
    """Only what is expected, and short."""
    if not isinstance(raw, dict):
        return {}
    found: dict = {}
    for key, limit in (("area", 40), ("floor", 40), ("text", 160), ("picture", 16)):
        if isinstance(raw.get(key), str):
            found[key] = raw[key][:limit]
    values = raw.get("values")
    if isinstance(values, dict):
        found["values"] = {}
        for key in NUMBERS:
            if (value := number(values.get(key))) is not None:
                found["values"][key] = value
        for key in WORDS:
            if isinstance(values.get(key), str):
                found["values"][key] = values[key][:40]
    lines = raw.get("parts")
    if isinstance(lines, list):
        found["parts"] = [[str(a)[:40], str(b)[:30]] for a, b in
                          (p for p in lines[:12] if isinstance(p, list) and len(p) == 2)]
    since = raw.get("since")
    if isinstance(since, (int, float)) and not isinstance(since, bool) and 0 < since < 1e11:
        found["since"] = float(since)
    return found


def _printer(raw: object) -> dict:
    """Only what is expected, and short."""
    if not isinstance(raw, dict) or raw.get("state") not in PRINTER_STATES:
        raise ValueError("bad printer")
    found: dict = {"state": raw["state"], "problem": raw.get("problem") is True}
    for key, limit in (("id", 64), ("name", 40), ("area", 40), ("file", 80), ("unit", 5),
                       ("problem_text", 160)):
        if isinstance(raw.get(key), str):
            found[key] = raw[key][:limit]
    for key in PRINTER_NUMBERS:
        if (value := number(raw.get(key))) is not None:
            found[key] = value
    return found


def _watching(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("kind") not in WATCH_KINDS:
        raise ValueError("bad watching")
    text = raw.get("text")
    if not isinstance(text, str):
        raise ValueError("bad watching")
    found: dict = {"kind": raw["kind"], "text": " ".join(text.split())[:120],
                   "told": raw.get("told") is True}
    for key in ("since", "due"):
        if (value := number(raw.get(key))) is not None and 0 < value < 1e11:
            found[key] = value
    return found


def _event(house_id: str, raw: object) -> Event:
    if not isinstance(raw, dict):
        raise ValueError("state must be an object")
    values = [raw.get(k) for k in ("entity_id", "kind", "state")]
    if not all(isinstance(v, str) and len(v) <= 255 for v in values):
        raise ValueError("bad state")
    # The house comes from the token, never from the message (E4).
    name = raw.get("name")
    return Event(house_id, *values, name[:100] if isinstance(name, str) else "",
                 _detail(raw.get("detail")))


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
    if request.app.get(SETTINGS) is not None:
        mode = request.app[SETTINGS].all()["personality"]
        await ws.send_json({"type": "mood", "mode": mode})
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
                    events = [_event(house_id, s) for s in data["states"]]
                    for event in events:
                        watcher.handle(event)
                        _remember(request.app, event, world)
                        await _belief(ws, world, event)
                    ready = True
                    if request.app.get(CONFIG) is not None:
                        await request.app[CONFIG].tell_cameras(house_id)
                    if request.app.get(ALERTS) is not None:
                        request.app[ALERTS].house_up(house_id, _name(request.app, house_id))
                elif kind == "state" and ready:
                    event = _event(house_id, data.get("state"))
                    watcher.handle(event)
                    _remember(request.app, event, world)
                    await _belief(ws, world, event)
                elif kind in ("escalate", "deescalate") and ready:
                    _escalate(request.app, world.event(data.get("entity_id")), kind)
                elif kind == "result" and ready:
                    waiting = request.app[ASKED].get((house_id, data.get("id")))
                    if waiting is not None and not waiting.done():
                        waiting.set_result(data.get("result"))
                elif kind == "mood" and ready:
                    # Wording only, so the house may choose it.
                    if data.get("mode") in tuple(MODES) and request.app.get(SETTINGS) is not None:
                        request.app[SETTINGS].update({"personality": data["mode"]})
                        audit.record(house_id, "mood", "mood changed", data["mode"], "ok")
                        await _tell_mood(request.app)
                elif kind == "ask" and ready:
                    # Answered on the side, so a slow model never holds up the feed.
                    task = asyncio.create_task(_answer(request.app, ws, house_id, data))
                    questions.add(task)
                    task.add_done_callback(questions.discard)
                elif kind == "printers" and ready:
                    items = data["items"]
                    if not isinstance(items, list) or len(items) > 20:
                        raise ValueError("bad printers")
                    request.app[PRINTERS][house_id] = [_printer(i) for i in items]
                elif kind == "watching" and ready:
                    items = data["items"]
                    if not isinstance(items, list) or len(items) > 30:
                        raise ValueError("bad watching")
                    request.app[WATCHING][house_id] = [_watching(i) for i in items]
                elif kind == "note" and ready:
                    uid = data.get("id")
                    if request.app.get(FINDINGS) is not None:
                        try:
                            request.app[FINDINGS].from_home(house_id, data)
                        except ValueError:
                            pass  # confirmed below, or it would come back forever
                    # A camera message told or held: Home on BRAM's page shows that event.
                    key = data.get("key")
                    if (data.get("source") == "cameras" and data.get("what") in ("sent", "held")
                            and isinstance(key, str) and request.app.get(CONFIG) is not None
                            and request.app[CONFIG].cameras.house() == house_id):
                        request.app[CONFIG].cameras.mark_told(key.split(":")[1:2][0]
                                                              if ":" in key else "")
                    if isinstance(uid, str):
                        await ws.send_json({"type": "noted", "id": uid[:32]})
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
            request.app[PRINTERS].pop(house_id, None)
            request.app[WATCHING].pop(house_id, None)
            if request.app.get(HISTORY) is not None:
                request.app[HISTORY].lost(house_id)
            audit.record(house_id, "feed", "disconnected", "connection closed", "state unknown")
            # Not when the owner removed the house.
            if request.app.get(ALERTS) is not None and request.app[PAIRING].house_for(token):
                request.app[ALERTS].house_down(house_id, _name(request.app, house_id))
    return ws


def _remember(app: web.Application, event: Event, world: World) -> None:
    if app.get(HISTORY) is not None:
        app[HISTORY].record(event, world)


async def _keep(app: web.Application) -> None:
    """Once a minute, note the readings. Now and then, bring in what is already known."""
    tries: dict[int, float] = {}
    told: dict[str, tuple] = {}
    while True:
        await asyncio.sleep(60)
        try:
            app[HISTORY].sample([w for w, _ in app[HOUSES].values()])
            mind_space(app)
            for house_id in list(app[SOCKETS]):
                await bring_past(app, house_id, tries)
                await tell_learning(app, house_id, told)
                await tell_habits(app, house_id)
        except Exception as err:  # noqa: BLE001 - history must never stop the server
            print(f"History could not be kept: {type(err).__name__}", file=sys.stderr)


def mind_space(app: web.Application) -> None:
    """Ask once when history is nearly full. Say so if old detail had to give way."""
    alerts, cleanup = app.get(ALERTS), app[CONFIG].cleanup
    if alerts is None or cleanup is None:
        return
    text = cleanup.should_ask()
    if text is not None and app[HISTORY].shortened:
        text += " The limit was reached, so the oldest 5-minute readings are now hourly."
    if text is not None:
        alerts.raise_alert("server", "storage", text, safety=False)
    else:
        alerts.clear("server", "storage", safety=False)


async def tell_learning(app: web.Application, house_id: str, told: dict[str, tuple]) -> None:
    """Quiet nights and door times from history, for Learning in Home Assistant to judge."""
    ws, house = app[SOCKETS].get(house_id), app[HOUSES].get(house_id)
    if ws is None or house is None or _older(house[0].version, (0, 34)):
        return
    history = app[HISTORY]
    zone = ZoneInfo(app[SETTINGS].all()["timezone"] or "UTC") if SETTINGS in app else ZoneInfo(
        "UTC")
    found = history.learning(house_id, zone) if history.on else {"nights": {}, "opens": {}}
    # Again when it changes, when Home Assistant reconnects, and once an hour.
    mark = (id(ws), int(time.time() // 3600), json.dumps(found, sort_keys=True))
    if told.get(house_id) == mark:
        return
    try:
        await ws.send_json({"type": "learned", **found})
    except ConnectionError:
        return
    told[house_id] = mark


async def tell_habits(app: web.Application, house_id: str) -> None:
    """Suggestions from what the owner does. Home Assistant checks each and an admin answers."""
    ws, house, findings = app[SOCKETS].get(house_id), app[HOUSES].get(house_id), app.get(FINDINGS)
    if ws is None or house is None or findings is None or _older(house[0].version, (0, 37)):
        return
    for key, why in findings.habits(house_id)[:3]:
        try:
            await ws.send_json({"type": "suggest", "key": key, "why": why})
        except ConnectionError:
            return
        findings.suggested(house_id, key)


async def bring_past(app: web.Application, house_id: str, tries: dict[int, float]) -> None:
    for device, entity_id in app[HISTORY].to_import(house_id):
        if time.monotonic() - tries.get(device, -1e9) < 3600:
            continue
        tries[device] = time.monotonic()
        for page in range(MAX_PAGES):
            result = await ask_house(app, house_id, f"statistics:{page}", entity_id)
            if result is None or "error" in result:
                break
            app[HISTORY].add_past(device, result.get("rows"))
            if not result.get("more"):
                app[HISTORY].imported(device)
                break


async def _tell_mood(app: web.Application) -> None:
    message = {"type": "mood", "mode": app[SETTINGS].all()["personality"]}
    for ws in list(app[SOCKETS].values()):
        try:
            await ws.send_json(message)
        except ConnectionError:
            continue


async def send_house(app: web.Application, house_id: str, message: dict) -> bool:
    ws = app[SOCKETS].get(house_id)
    if ws is None:
        return False
    try:
        await ws.send_json(message)
    except ConnectionError:
        return False
    return True


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
    app[TASKS].append(asyncio.create_task(app[CONFIG].cameras.run()))
    if app.get(HISTORY) is not None:
        app[TASKS].append(asyncio.create_task(_keep(app)))


async def _stop(app: web.Application) -> None:
    for task in app[TASKS]:
        task.cancel()
    await asyncio.gather(*app[TASKS], return_exceptions=True)
    await app[CONFIG].cameras.close()


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
             clock: Callable[[], float] = time.monotonic,
             history: History | None = None,
             findings: Findings | None = None) -> web.Application:
    app = web.Application(client_max_size=4096)
    app[PAIRING], app[AUDIT], app[HOUSES], app[SOCKETS] = pairing, audit, {}, {}
    app[ASKED], app[PRINTERS], app[WATCHING] = {}, {}, {}
    if history is not None:
        app[HISTORY] = history
    if findings is not None:
        app[FINDINGS] = findings
        if alerts is not None:
            alerts.findings = findings
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
                          lambda *a: ask_house(app, *a), lambda: _tell_mood(app), history,
                          findings, app[PRINTERS], app[WATCHING],
                          lambda *a: send_house(app, *a))
        app[SETTINGS] = settings
        if alerts is not None:
            app[ALERTS], app[TASKS] = alerts, []
            alerts.channels = [page.ntfy, page.telegram]
            app[MONITORS] = page.monitors
            app.on_startup.append(_start)
            app.on_cleanup.append(_stop)
        app[CHAT], app[CONFIG] = page.chat, page
        app.add_routes(page.routes())
    app.on_shutdown.append(_shutdown)
    return app


async def _serve(host: str, port: int, data: Path) -> None:
    context, fingerprint = ensure_certificate(data)
    database = data / "bram.db"
    audit, settings = Audit(database), Settings(database)
    alerts = Alerts(database, audit, lambda channel: settings.channel(channel).get("quiet", {}))
    history = History(database, lambda: settings.all()["keep_history"],
                      lambda: settings.all()["history_limit_mb"])
    if not history.healthy:
        audit.record("server", "database", "database damaged", "quick check failed", "problem")
        print("The database failed its check. Restore a backup.", file=sys.stderr)
    app = make_app(Pairing(database), audit, settings, fingerprint, alerts, history=history,
                   findings=Findings(
                       database, keep_prints=lambda: settings.all()["keep_history"]))
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
        history.close()


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
