"""Suggestions wait in Home Assistant's Repairs for the owner to answer."""
from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant


class SuggestionFlow(RepairsFlow):
    def __init__(self, entry_id: str, text: str) -> None:
        self._entry_id, self._text = entry_id, text

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        return self.async_show_menu(
            step_id="init", menu_options=["approve", "later", "never"],
            description_placeholders={"text": self._text})

    def _learner(self) -> Any:
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        return getattr(getattr(entry, "runtime_data", None), "learner", None)

    def _answer(self, word: str) -> Any:
        learner = self._learner()
        # Only the suggestion that was shown can be answered.
        held = learner.data["suggestion"] if learner is not None else None
        if held is None or held["text"] != self._text:
            return self.async_abort(reason="gone")
        getattr(learner, word)()
        return self.async_create_entry(data={})

    async def async_step_approve(self, user_input: dict[str, Any] | None = None) -> Any:
        return self._answer("approve")

    async def async_step_later(self, user_input: dict[str, Any] | None = None) -> Any:
        return self._answer("later")

    async def async_step_never(self, user_input: dict[str, Any] | None = None) -> Any:
        return self._answer("never")


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str,
                                data: dict[str, Any] | None) -> RepairsFlow:
    return SuggestionFlow(str((data or {}).get("entry_id")), str((data or {}).get("text")))
