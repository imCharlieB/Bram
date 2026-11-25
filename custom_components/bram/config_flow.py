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
    CONF_ENTITIES,
    CONF_ESCALATE,
    CONF_PHONES,
    CONF_QUIET_FROM,
    CONF_QUIET_TO,
    DEFAULT_PORT,
    DOMAIN,
    GROUPS,
)
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
        return self.async_show_menu(step_id="init", menu_options=["see", "alerts"])

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

    async def async_step_alerts(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            # Emptied quiet hours are turned off.
            options.pop(CONF_QUIET_FROM, None)
            options.pop(CONF_QUIET_TO, None)
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
            vol.Required(CONF_ESCALATE, default=options.get(CONF_ESCALATE, False)): bool,
        }))
