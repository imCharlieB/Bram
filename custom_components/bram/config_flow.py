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
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        chosen = options.get(CONF_ENTITIES, [])
        allowed = {s.entity_id for s in self.hass.states.async_all()
                   if kind_of(s.entity_id, s.attributes.get("device_class"))}
        # A phone that is missing right now stays chosen.
        saved = options.get(CONF_PHONES, [])
        listed = sorted({*phones(self.hass), *saved})
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_ENTITIES, default=chosen): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=sorted(allowed | set(chosen)),
                                              multiple=True)),
            vol.Required(CONF_PHONES, default=saved): selector.SelectSelector(
                selector.SelectSelectorConfig(multiple=True, options=[
                    selector.SelectOptionDict(value=p, label=p.removeprefix(PREFIX))
                    for p in listed])),
            vol.Optional(CONF_QUIET_FROM, description={
                "suggested_value": options.get(CONF_QUIET_FROM)}): selector.TimeSelector(),
            vol.Optional(CONF_QUIET_TO, description={
                "suggested_value": options.get(CONF_QUIET_TO)}): selector.TimeSelector(),
            vol.Required(CONF_ESCALATE, default=options.get(CONF_ESCALATE, False)): bool,
        }))
