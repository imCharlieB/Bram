"""Telegram and ntfy. Off until the owner turns them on. Neither can approve anything."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import re
import secrets
import time
from collections.abc import Awaitable, Callable

import httpx

from .alerts import Outgoing
from .chat import Busy
from .local_model import check_local
from .models.base import ModelError
from .settings import Settings

_LOGGER = logging.getLogger(__name__)
LINK_LIFETIME = 600
TOKEN = re.compile(r"\d{5,15}:[A-Za-z0-9_-]{30,60}")
ACTION = re.compile(r"(ack|snooze|mute):[0-9a-f]{16}")


class ChannelError(Exception):
    """Safe to show: never contains a token or address."""


def new_topic() -> str:
    """Short enough to type, with about 48 bits to guess. No look-alike characters."""
    return "bram-" + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(10))


async def _pause(failures: int) -> None:
    await asyncio.sleep(min(5 * 2**min(failures, 6), 300))


class Ntfy:
    """Sends to one secret topic. Buttons answer on another."""

    name = "ntfy"

    def __init__(self, settings: Settings, answer: Callable[[str, str], str],
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings, self._answer, self._transport = settings, answer, transport

    def config(self) -> dict:
        return self._settings.channel("ntfy")

    def ready(self) -> bool:
        c = self.config()
        return bool(c.get("on") and c.get("url") and c.get("phone_url") and c.get("topic"))

    def _client(self, timeout: float | httpx.Timeout = 15) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self._transport, trust_env=False,
                                 follow_redirects=False)

    async def _base(self, url: str) -> str:
        try:
            return await check_local(url, default_port=80)
        except ModelError as err:
            raise ChannelError(str(err)) from None

    async def send(self, message: Outgoing) -> None:
        c = self.config()
        base = await self._base(c["url"])
        body = {"topic": c["topic"], "title": message.title, "message": message.text,
                "priority": 5 if message.safety else 3,
                "tags": ["rotating_light"] if message.safety else [],
                "actions": [{"action": "http", "label": label, "method": "POST", "clear": True,
                             "url": f"{c['phone_url'].rstrip('/')}/{c['reply']}", "body": action}
                            for label, action in message.buttons]}
        try:
            async with self._client() as client:
                response = await client.post(base + "/", json=body)
        except httpx.HTTPError as err:
            raise ChannelError(f"ntfy did not answer ({type(err).__name__})") from None
        if response.status_code != 200:
            raise ChannelError(f"ntfy refused the message ({response.status_code})")

    async def listen(self) -> None:
        failures, since = 0, str(int(time.time()))
        while True:
            if not self.ready():
                await asyncio.sleep(5)
                continue
            c = self.config()
            try:
                base = await self._base(c["url"])
                # ntfy sends a keepalive at least every 45 seconds.
                async with self._client(httpx.Timeout(15, read=90)) as client, client.stream(
                        "GET", f"{base}/{c['reply']}/json", params={"since": since}) as response:
                    if response.status_code != 200:
                        raise ChannelError(f"ntfy refused ({response.status_code})")
                    failures = 0
                    async for line in response.aiter_lines():
                        if self.config() != c:
                            break
                        since = self.handle(line) or since
            except (httpx.HTTPError, ChannelError) as err:
                failures += 1
                if failures == 1:
                    _LOGGER.warning("ntfy replies unavailable: %s", type(err).__name__)
                await _pause(failures)

    def handle(self, line: str) -> str | None:
        """Accept only a button press. Anything typed is ignored (D1)."""
        try:
            data = json.loads(line)
        except ValueError:
            return None
        if not isinstance(data, dict) or data.get("event") != "message":
            return None
        text = data.get("message")
        if isinstance(text, str) and ACTION.fullmatch(text):
            self._answer(text, "ntfy")
        return data["id"] if isinstance(data.get("id"), str) else None


class Telegram:
    """One linked account. Nobody else is answered."""

    name = "telegram"

    def __init__(self, settings: Settings, answer: Callable[[str, str], str],
                 transport: httpx.AsyncBaseTransport | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 talk: Callable[[str], Awaitable[str]] | None = None) -> None:
        self._settings, self._answer, self._clock = settings, answer, clock
        self._talk = talk
        self._talking: set[asyncio.Task] = set()
        self._transport = transport
        self._link: tuple[str, float] | None = None
        self._link_failures = 0

    def config(self) -> dict:
        return self._settings.channel("telegram")

    def ready(self) -> bool:
        c = self.config()
        return bool(c.get("on") and c.get("token") and c.get("user_id"))

    async def call(self, method: str, body: dict, token: str | None = None,
                   timeout: float = 15) -> object:  # noqa: ASYNC109 - httpx timeout
        token = token or self.config().get("token", "")
        if not TOKEN.fullmatch(token):
            raise ChannelError("That does not look like a bot token")
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport,
                                         trust_env=False, follow_redirects=False) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{token}/{method}", json=body)
                data = response.json()
        except (httpx.HTTPError, ValueError) as err:
            # The address holds the token, so the original error is not passed on.
            raise ChannelError(f"Telegram did not answer ({type(err).__name__})") from None
        if not isinstance(data, dict) or not data.get("ok"):
            raise ChannelError(f"Telegram refused ({response.status_code})")
        return data.get("result")

    async def bot_name(self, token: str) -> str:
        me = await self.call("getMe", {}, token)
        return str(me.get("username", "")) if isinstance(me, dict) else ""

    def new_link(self) -> str:
        self._link_failures = 0
        code = secrets.token_urlsafe(16)
        self._link = (code, self._clock() + LINK_LIFETIME)
        return code

    async def send(self, message: Outgoing) -> None:
        body: dict = {"chat_id": self.config()["user_id"],
                      "text": f"{message.title}\n{message.text}",
                      "link_preview_options": {"is_disabled": True}}
        if message.buttons:
            body["reply_markup"] = {"inline_keyboard": [
                [{"text": label, "callback_data": action}] for label, action in message.buttons]}
        await self.call("sendMessage", body)

    async def listen(self) -> None:
        failures, offset, token = 0, 0, ""
        while True:
            c = self.config()
            if not (c.get("on") and c.get("token")):
                await asyncio.sleep(5)
                continue
            if c["token"] != token:
                token, offset = c["token"], 0
            try:
                updates = await self.call("getUpdates", {
                    "offset": offset, "timeout": 25,
                    "allowed_updates": ["message", "callback_query"]}, timeout=40)
                failures = 0
                for update in updates if isinstance(updates, list) else []:
                    if isinstance(update, dict) and isinstance(update.get("update_id"), int):
                        offset = update["update_id"] + 1
                        await self.handle(update)
            except ChannelError as err:
                failures += 1
                if failures == 1:
                    _LOGGER.warning("Telegram replies unavailable: %s", err)
                await _pause(failures)

    async def handle(self, update: dict) -> None:
        message, press = update.get("message"), update.get("callback_query")
        if isinstance(message, dict):
            await self._message(message)
        elif isinstance(press, dict):
            await self._press(press)

    async def _message(self, message: dict) -> None:
        sender, chat = message.get("from") or {}, message.get("chat") or {}
        user_id, text = sender.get("id"), message.get("text")
        if (not isinstance(user_id, int) or not isinstance(text, str) or sender.get("is_bot")
                or chat.get("type") != "private" or chat.get("id") != user_id):
            return
        if text.startswith("/start ") and self._try_link(text[7:].strip()):
            self._settings.update_channel("telegram", {"user_id": user_id})
            await self._reply(user_id, "Linked. BRAM will message you here.")
        elif user_id == self.config().get("user_id"):
            if self._talk is None or not self.config().get("chat"):
                await self._reply(user_id, "Chat is turned off for Telegram. You can turn it on "
                                           "on BRAM's Messages page.")
                return
            # A slow model must not hold up buttons.
            task = asyncio.create_task(self._chat(user_id, text))
            self._talking.add(task)
            task.add_done_callback(self._talking.discard)

    async def _chat(self, user_id: int, text: str) -> None:
        try:
            answer = await self._talk(text)
        except Busy:
            answer = "I'm still thinking about the last thing. Try again in a moment."
        except ModelError as err:
            answer = f"I can't answer right now: {err}"
        await self._reply(user_id, answer[:4000])

    async def idle(self) -> None:
        await asyncio.gather(*self._talking, return_exceptions=True)

    def _try_link(self, code: str) -> bool:
        if self._link is None or self._clock() > self._link[1]:
            return False
        if not hmac.compare_digest(code.encode(), self._link[0].encode()):
            self._link_failures += 1
            if self._link_failures >= 5:
                self._link = None
            return False
        self._link = None
        return True

    async def _press(self, press: dict) -> None:
        sender, action = press.get("from") or {}, press.get("data")
        user_id = sender.get("id")
        if not isinstance(user_id, int) or user_id != self.config().get("user_id"):
            return
        result = "That is not something I can do."
        if isinstance(action, str) and ACTION.fullmatch(action):
            result = self._answer(action, "telegram")
        try:
            await self.call("answerCallbackQuery", {"callback_query_id": press.get("id"),
                                                    "text": result})
        except ChannelError:
            pass  # the answer already counted

    async def _reply(self, user_id: int, text: str) -> None:
        try:
            await self.call("sendMessage", {"chat_id": user_id, "text": text})
        except ChannelError:
            pass
