"""BRAM as a conversation agent. Text in, text out: it cannot control anything."""
from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BramEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([Agent(entry)])


class Agent(BramEntity, conversation.ConversationEntity):
    _attr_name = "Assist"
    _attr_icon = "mdi:account-tie-voice"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "assist")

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def _async_handle_message(
        self, user_input: conversation.ConversationInput, chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        user = (await self.hass.auth.async_get_user(user_input.context.user_id)
                if user_input.context.user_id else None)
        text = await self._feed.ask(user_input.text, chat_log.conversation_id,
                                    user.name or "" if user is not None else "")
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=user_input.agent_id, content=text))
        return conversation.async_get_result_from_chat_log(user_input, chat_log)
