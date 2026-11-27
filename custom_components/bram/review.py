"""The review page in Home Assistant: what BRAM suggests, with the evidence and exactly what
would change. Only a signed-in Home Assistant admin can answer, and only here (F4).

The page is opened from the phone message, or at /bram-review. It is not in the sidebar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

PANEL = "bram-review"
STATIC = "/bram_static"
FILES = Path(__file__).parent / "frontend"
READY = "bram_review_ready"


def _learners(hass: HomeAssistant) -> list[Any]:
    """Everything that can suggest: learned hours, and fewer messages."""
    found = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        feed = getattr(entry, "runtime_data", None)
        found += [part for part in (getattr(feed, "learner", None),
                                    getattr(feed, "suggestions", None)) if part is not None]
    return found


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "bram/review/list"})
@callback
def _list(hass: HomeAssistant, connection: websocket_api.ActiveConnection,
          msg: dict[str, Any]) -> None:
    items = [item for learner in _learners(hass) for item in learner.review()]
    connection.send_result(msg["id"], {"items": items})


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "bram/review/answer",
    vol.Required("item"): vol.All(str, vol.Length(max=100)),
    vol.Required("answer"): vol.In(["approve", "stop", "less", "later", "never"]),
})
@callback
def _answer(hass: HomeAssistant, connection: websocket_api.ActiveConnection,
            msg: dict[str, Any]) -> None:
    who = connection.user.name if connection.user is not None else ""
    if any(learner.answer(msg["item"], msg["answer"], who or "")
           for learner in _learners(hass)):
        connection.send_result(msg["id"], {"ok": True})
    else:
        connection.send_error(msg["id"], "gone", "This suggestion is no longer waiting.")


async def start(hass: HomeAssistant) -> None:
    """Once per Home Assistant run: the page, its script, and its two commands."""
    if hass.data.get(READY):
        return
    hass.data[READY] = True
    websocket_api.async_register_command(hass, _list)
    websocket_api.async_register_command(hass, _answer)
    # Home Assistant always runs its frontend; a bare test setup may not.
    if "frontend" not in hass.config.components or hass.http is None:
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC, str(FILES), cache_headers=False)])
    if PANEL not in hass.data.get(frontend.DATA_PANELS, {}):
        await panel_custom.async_register_panel(
            hass, frontend_url_path=PANEL, webcomponent_name="bram-review",
            module_url=f"{STATIC}/review.js", require_admin=True)
