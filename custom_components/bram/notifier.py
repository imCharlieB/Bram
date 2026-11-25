"""The only code that calls a Home Assistant service, and only to notify chosen phones.

It takes no input from the server or a model.
"""
from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant

PREFIX = "mobile_app_"


def phones(hass: HomeAssistant) -> list[str]:
    return sorted(s for s in hass.services.async_services_for_domain("notify")
                  if s.startswith(PREFIX))


async def notify(hass: HomeAssistant, targets: list[str], title: str, text: str, tag: str, *,
                 safety: bool, actions: list[dict[str, str]]) -> bool:
    """Send to every chosen phone. True if at least one accepted it."""
    data: dict = {"tag": tag, "actions": actions}
    if safety:
        data |= {"ttl": 0, "priority": "high", "channel": "BRAM safety", "importance": "max",
                 "push": {"interruption-level": "critical",
                          "sound": {"name": "default", "critical": 1, "volume": 1.0}}}
        # Also shown inside Home Assistant, in case no phone can be reached.
        persistent_notification.async_create(hass, text, title, tag)
    sent = False
    for target in targets:
        if not target.startswith(PREFIX):
            continue
        try:
            await hass.services.async_call("notify", target, {
                "title": title, "message": text, "data": data}, blocking=True)
            sent = True
        except Exception:  # noqa: BLE001, S112 - one phone must not stop the others
            continue
    return sent


def dismiss(hass: HomeAssistant, tag: str) -> None:
    persistent_notification.async_dismiss(hass, tag)
