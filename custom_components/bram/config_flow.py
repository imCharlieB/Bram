"""Pairing and entity selection."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CannotConnect, InvalidCode, pair
from .const import (
    CONF_CODE,
    CONF_DIGEST,
    CONF_ENTITIES,
    CONF_ESCALATE,
    CONF_HISTORY,
    CONF_PHONES,
    CONF_PROBLEMS,
    CONF_QUIET_FROM,
    CONF_QUIET_TO,
    DEFAULT_NIGHT_FROM,
    DEFAULT_NIGHT_TO,
    DEFAULT_OPEN_MINUTES,
    DEFAULT_PORT,
    DOMAIN,
    GROUPS,
)
from .discover import find, suggest
from .feed import kind_of
from .notifier import PREFIX, phones


class BramConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            host, port = user_input["host"].strip(), user_input["port"]
            try:
                data = await pair(async_get_clientsession(self.hass), host, port,
                                  user_input[CONF_CODE])
            except InvalidCode:
                errors["base"] = "invalid_code"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                # Nothing is shared until the owner picks entities (F5).
                return self.async_create_entry(title="BRAM", data={
                    "host": host, "port": port, **data}, options={CONF_ENTITIES: []})
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required("host"): str,
            vol.Required("port", default=DEFAULT_PORT): vol.All(int, vol.Range(1, 65535)),
            vol.Required(CONF_CODE): str,
        }))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BramOptionsFlow:
        return BramOptionsFlow()


class BramOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=[
            "suggest", "quick", "see", "alerts", "watch", "chat"])

    _found: list[str] = []

    async def async_step_quick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            chosen = self.config_entry.options.get(CONF_ENTITIES, [])
            self._found = [e for e in find(self.hass, user_input["groups"],
                                           user_input.get("areas", [])) if e not in chosen]
            if self._found:
                return await self.async_step_review()
            errors["base"] = "nothing_found"
        return self.async_show_form(step_id="quick", errors=errors, data_schema=vol.Schema({
            vol.Required("groups", default=list(GROUPS)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(GROUPS), multiple=True, translation_key="groups",
                    mode=selector.SelectSelectorMode.LIST)),
            vol.Optional("areas"): selector.AreaSelector(
                selector.AreaSelectorConfig(multiple=True)),
        }))

    async def async_step_suggest(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        self._found = suggest(self.hass, self.config_entry.options.get(CONF_ENTITIES, []))
        if not self._found:
            return self.async_abort(reason="nothing_to_suggest")
        return await self.async_step_review()

    async def async_step_review(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            chosen = options.get(CONF_ENTITIES, [])
            # Only what was offered, and only what the owner left in the list.
            add = [e for e in user_input.get("add", []) if e in self._found]
            return self.async_create_entry(data={**options, CONF_ENTITIES: [*chosen, *add]})
        return self.async_show_form(
            step_id="review", description_placeholders={"count": str(len(self._found))},
            data_schema=vol.Schema({
                vol.Optional("add", description={"suggested_value": self._found}): (
                    selector.EntitySelector(selector.EntitySelectorConfig(
                        include_entities=self._found, multiple=True)))}))

    async def async_step_see(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            chosen = [e for group in GROUPS for e in user_input.get(group, [])]
            return self.async_create_entry(data={**options, CONF_ENTITIES: chosen})
        chosen = options.get(CONF_ENTITIES, [])
        kinds = {s.entity_id: kind_of(s.entity_id, s.attributes.get("device_class"))
                 for s in self.hass.states.async_all()}
        fields = {}
        for group, wanted in GROUPS.items():
            # A chosen device that is missing right now must not be dropped by saving.
            mine = [e for e in chosen if (kinds.get(e) or kind_of(e, None) or "leak") in wanted]
            listed = sorted({e for e, k in kinds.items() if k in wanted} | set(mine))
            # A default would come back after the owner empties the group.
            fields[vol.Optional(group, description={"suggested_value": mine})] = (
                selector.EntitySelector(
                    selector.EntitySelectorConfig(include_entities=listed, multiple=True)))
        return self.async_show_form(step_id="see", data_schema=vol.Schema(fields))

    async def async_step_chat(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        return self.async_show_form(step_id="chat", data_schema=vol.Schema({
            vol.Required(key, default=options.get(key, False)): bool
            for key in (CONF_HISTORY, CONF_PROBLEMS)}))

    async def async_step_watch(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        return self.async_show_form(step_id="watch", data_schema=vol.Schema({
            **{vol.Required(rule, default=options.get(rule, False)): bool
               for rule in ("night", "away", "left_open", "offline")},
            vol.Required("night_from", default=options.get("night_from", DEFAULT_NIGHT_FROM)):
                selector.TimeSelector(),
            vol.Required("night_to", default=options.get("night_to", DEFAULT_NIGHT_TO)):
                selector.TimeSelector(),
            vol.Required("open_minutes", default=options.get(
                "open_minutes", DEFAULT_OPEN_MINUTES)): vol.All(int, vol.Range(1, 1440)),
        }))

    async def async_step_alerts(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            # Emptied quiet hours are turned off.
            options.pop(CONF_QUIET_FROM, None)
            options.pop(CONF_QUIET_TO, None)
            options.pop(CONF_DIGEST, None)
            return self.async_create_entry(data={**options, **user_input})
        # A phone that is missing right now stays chosen.
        saved = options.get(CONF_PHONES, [])
        listed = sorted({*phones(self.hass), *saved})
        return self.async_show_form(step_id="alerts", data_schema=vol.Schema({
            vol.Required(CONF_PHONES, default=saved): selector.SelectSelector(
                selector.SelectSelectorConfig(multiple=True, options=[
                    selector.SelectOptionDict(
                        value=p, label=p.removeprefix(PREFIX).replace("_", " ").title())
                    for p in listed])),
            vol.Optional(CONF_QUIET_FROM, description={
                "suggested_value": options.get(CONF_QUIET_FROM)}): selector.TimeSelector(),
            vol.Optional(CONF_QUIET_TO, description={
                "suggested_value": options.get(CONF_QUIET_TO)}): selector.TimeSelector(),
            vol.Optional(CONF_DIGEST, description={
                "suggested_value": options.get(CONF_DIGEST)}): selector.TimeSelector(),
            vol.Required(CONF_ESCALATE, default=options.get(CONF_ESCALATE, False)): bool,
        }))
