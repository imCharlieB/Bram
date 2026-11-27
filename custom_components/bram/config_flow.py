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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import printers
from .client import CannotConnect, InvalidCode, pair
from .const import (
    CONF_CODE,
    CONF_DIGEST,
    CONF_ENTITIES,
    CONF_ESCALATE,
    CONF_HISTORY,
    CONF_LEARN,
    CONF_PHONES,
    CONF_PRINTERS,
    CONF_PRINTERS_CHOSEN,
    CONF_PROBLEM_WATCH,
    CONF_PROBLEMS,
    CONF_QUIET_FROM,
    CONF_QUIET_TO,
    CONF_ROOMS,
    CONF_SAFETY_PHONES,
    CONF_SECURITY,
    CONF_SECURITY_WATCH,
    CONF_WEEKEND_FROM,
    CONF_WEEKEND_TO,
    DEFAULT_DIGEST,
    DEFAULT_NIGHT_FROM,
    DEFAULT_NIGHT_TO,
    DEFAULT_OPEN_MINUTES,
    DEFAULT_PORT,
    DOMAIN,
    GROUPS,
    OPEN_TYPES,
)
from .details import room_sensors
from .discover import find, suggest
from .feed import kind_of
from .house_rules import limits
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
            "basic", "devices", "alerts", "watching", "chat", "learn"])

    async def async_step_devices(self, user_input: dict[str, Any] | None = None,
                                 ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="devices",
                                    menu_options=["suggest", "quick", "see", "rooms"])

    async def async_step_watching(self, user_input: dict[str, Any] | None = None,
                                  ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="watching",
                                    menu_options=["watch_ha", "watch", "comfort", "printers"])

    async def async_step_watch_ha(self, user_input: dict[str, Any] | None = None,
                                  ) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        return self.async_show_form(step_id="watch_ha", data_schema=vol.Schema({
            vol.Required(key, default=options.get(key, False)): bool
            for key in (CONF_PROBLEM_WATCH, CONF_SECURITY_WATCH)}))

    _found: list[str] = []

    async def async_step_basic(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Everything most people want, on one page."""
        options = dict(self.config_entry.options)
        chosen = options.get(CONF_ENTITIES, [])
        offered = suggest(self.hass, chosen)
        known = phones(self.hass)
        saved = options.get(CONF_PHONES, [])
        if user_input is not None:
            skip = user_input.pop("skip", [])
            add = [e for e in offered if e not in skip]
            if user_input.pop("summary"):
                user_input[CONF_DIGEST] = options.get(CONF_DIGEST, DEFAULT_DIGEST)
            else:
                options.pop(CONF_DIGEST, None)
            return self.async_create_entry(data={
                **options, **user_input, CONF_ENTITIES: [*chosen, *add]})
        schema = {
            vol.Required(CONF_PHONES, default=saved or (known if len(known) == 1 else [])):
                self._phone_list(sorted({*known, *saved})),
        }
        if offered:
            schema[vol.Optional("skip")] = self._picker(offered)
        # Away stays off here: it is wrong until everyone who lives there is shared.
        schema |= {vol.Required(key, default=options.get(key, True)): bool
                   for key in ("night", "left_open", "offline", CONF_PROBLEM_WATCH, CONF_HISTORY)}
        if printers.find(self.hass):
            schema[vol.Required(CONF_PRINTERS, default=options.get(CONF_PRINTERS, True))] = bool
        schema[vol.Required("summary", default=True)] = bool
        return self.async_show_form(step_id="basic", data_schema=vol.Schema(schema),
                                    description_placeholders={"found": self._names(offered)})

    # Picking what to leave out, because Home Assistant fills an emptied list of suggestions
    # back in, which would share everything the owner removed.
    @staticmethod
    def _picker(offered: list[str]) -> selector.EntitySelector:
        return selector.EntitySelector(selector.EntitySelectorConfig(
            include_entities=offered, multiple=True))

    def _names(self, offered: list[str]) -> str:
        if not offered:
            return "Nothing new to share."
        names = sorted((s.name if (s := self.hass.states.get(e)) else e) for e in offered)
        more = f"\n- and {len(names) - 40} more" if len(names) > 40 else ""
        return "\n".join(f"- {n}" for n in names[:40]) + more

    @staticmethod
    def _phone_list(listed: list[str]) -> selector.SelectSelector:
        return selector.SelectSelector(selector.SelectSelectorConfig(multiple=True, options=[
            selector.SelectOptionDict(
                value=p, label=p.removeprefix(PREFIX).replace("_", " ").title())
            for p in listed]))

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
            vol.Required(
                "groups", default=["people", "doors", "safety", "motion"],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[g for g in GROUPS if g != "other"], multiple=True,
                    translation_key="groups",
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
            # Only what was offered, less what the owner left out.
            skip = user_input.get("skip", [])
            add = [e for e in self._found if e not in skip]
            return self.async_create_entry(data={**options, CONF_ENTITIES: [*chosen, *add]})
        return self.async_show_form(
            step_id="review", description_placeholders={
                "count": str(len(self._found)), "found": self._names(self._found)},
            data_schema=vol.Schema({vol.Optional("skip"): self._picker(self._found)}))

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
            mine = [e for e in chosen if self._kind(e, kinds) in wanted]
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
            for key in (CONF_HISTORY, CONF_PROBLEMS, CONF_SECURITY)}))

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Which sensor says what room a person is in."""
        options = dict(self.config_entry.options)
        people = {}
        for entity_id in options.get(CONF_ENTITIES, []):
            if entity_id.startswith("person."):
                state = self.hass.states.get(entity_id)
                people[state.name if state is not None else entity_id] = entity_id
        if not people:
            return self.async_abort(reason="no_people")
        saved = options.get(CONF_ROOMS, {})
        if user_input is not None:
            return self.async_create_entry(data={**options, CONF_ROOMS: {
                people[name]: sensor for name, sensor in user_input.items() if sensor}})
        fields = {}
        for name, person in people.items():
            auto = room_sensors(self.hass, self.hass.states.get(person))
            fields[vol.Optional(name, description={
                "suggested_value": saved.get(person) or (auto[0] if auto else None)})] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")))
        return self.async_show_form(step_id="rooms", data_schema=vol.Schema(fields))

    async def async_step_printers(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """A switch for each printer, so none is watched without the owner wanting it."""
        options = dict(self.config_entry.options)
        found = {p.name: p.id for p in printers.find(self.hass)}
        if not found:
            return self.async_abort(reason="no_printers")
        chosen = options.get(CONF_PRINTERS_CHOSEN, [])
        if user_input is not None:
            # A printer missing right now keeps its choice.
            kept = [p for p in chosen if p not in found.values()]
            options.pop("printers_off", None)
            return self.async_create_entry(data={
                **options, CONF_PRINTERS: user_input.pop(CONF_PRINTERS),
                CONF_PRINTERS_CHOSEN: kept + [found[n] for n, on in user_input.items() if on]})
        return self.async_show_form(step_id="printers", data_schema=vol.Schema({
            vol.Required(CONF_PRINTERS, default=options.get(CONF_PRINTERS, False)): bool,
            **{vol.Required(name, default=device in chosen): bool
               for name, device in found.items()}}))

    async def async_step_learn(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        learner = getattr(getattr(self.config_entry, "runtime_data", None), "learner", None)
        if learner is None:
            return self.async_abort(reason="not_running")
        if user_input is not None:
            if user_input.get("undo"):
                options = learner.undone(options)
            if user_input["forget"]:
                await learner.forget()
            return self.async_create_entry(data={**options, CONF_LEARN: user_input[CONF_LEARN]})
        fields = {vol.Required(CONF_LEARN, default=options.get(CONF_LEARN, False)): bool}
        if learner.data["undo"]:
            fields[vol.Required("undo", default=False)] = bool
        fields[vol.Required("forget", default=False)] = bool
        return self.async_show_form(
            step_id="learn", data_schema=vol.Schema(fields),
            description_placeholders={"nights": str(len(learner.data["nights"]))})

    async def async_step_watch(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            options.pop(CONF_WEEKEND_FROM, None)
            options.pop(CONF_WEEKEND_TO, None)
            return self.async_create_entry(data={**options, **user_input})
        return self.async_show_form(step_id="watch", data_schema=vol.Schema({
            **{vol.Required(rule, default=options.get(rule, False)): bool
               for rule in ("night", "away", "left_open", "offline", "open_night",
                            "open_climate", "motion_away")},
            **{vol.Required(kind, default=options.get(kind, True)): bool for kind in OPEN_TYPES},
            vol.Required("night_from", default=options.get("night_from", DEFAULT_NIGHT_FROM)):
                selector.TimeSelector(),
            vol.Required("night_to", default=options.get("night_to", DEFAULT_NIGHT_TO)):
                selector.TimeSelector(),
            **{vol.Optional(key, description={"suggested_value": options.get(key)}):
               selector.TimeSelector() for key in (CONF_WEEKEND_FROM, CONF_WEEKEND_TO)},
            vol.Required("open_minutes", default=options.get(
                "open_minutes", DEFAULT_OPEN_MINUTES)): vol.All(int, vol.Range(1, 1440)),
        }))

    async def async_step_comfort(self, user_input: dict[str, Any] | None = None,
                                 ) -> ConfigFlowResult:
        """Too hot, too cold, near freezing, and humid, with the home's own unit."""
        options = dict(self.config_entry.options)
        if user_input is not None:
            options.pop("comfort_skip", None)
            return self.async_create_entry(data={**options, **user_input})
        unit = self.hass.config.units.temperature_unit
        now = limits(unit, options)
        degrees = selector.NumberSelector(selector.NumberSelectorConfig(
            min=-40, max=140, step=1, unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX))
        return self.async_show_form(step_id="comfort", data_schema=vol.Schema({
            **{vol.Required(rule, default=options.get(rule, False)): bool
               for rule in ("too_hot", "too_cold", "freezing", "humid")},
            vol.Required("hot_above", default=now["hot_above"]): degrees,
            vol.Required("cold_below", default=now["cold_below"]): degrees,
            vol.Required("freeze_below", default=now["freeze_below"]): degrees,
            vol.Required("humid_above", default=now["humid_above"]): selector.NumberSelector(
                selector.NumberSelectorConfig(min=30, max=100, step=1, unit_of_measurement="%",
                                              mode=selector.NumberSelectorMode.BOX)),
            vol.Optional("comfort_skip", description={
                "suggested_value": options.get("comfort_skip", [])}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "climate"], multiple=True)),
        }))

    def _kind(self, entity_id: str, kinds: dict[str, str | None]) -> str:
        """What a chosen device is, even if it is missing right now."""
        entry = er.async_get(self.hass).async_get(entity_id)
        known = entry and (entry.device_class or entry.original_device_class)
        return kinds.get(entity_id) or kind_of(entity_id, known or None) or "other"

    async def async_step_alerts(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if user_input is not None:
            # Emptied quiet hours are turned off.
            options.pop(CONF_QUIET_FROM, None)
            options.pop(CONF_QUIET_TO, None)
            options.pop(CONF_DIGEST, None)
            options.pop(CONF_SAFETY_PHONES, None)
            return self.async_create_entry(data={**options, **user_input})
        only = options.get(CONF_SAFETY_PHONES, [])
        # A phone that is missing right now stays chosen.
        saved = options.get(CONF_PHONES, [])
        listed = sorted({*phones(self.hass), *saved})
        return self.async_show_form(step_id="alerts", data_schema=vol.Schema({
            vol.Required(CONF_PHONES, default=saved): self._phone_list(listed),
            vol.Optional(CONF_SAFETY_PHONES, description={
                "suggested_value": only}): self._phone_list(sorted({*listed, *only})),
            vol.Optional(CONF_QUIET_FROM, description={
                "suggested_value": options.get(CONF_QUIET_FROM)}): selector.TimeSelector(),
            vol.Optional(CONF_QUIET_TO, description={
                "suggested_value": options.get(CONF_QUIET_TO)}): selector.TimeSelector(),
            vol.Optional(CONF_DIGEST, description={
                "suggested_value": options.get(CONF_DIGEST)}): selector.TimeSelector(),
            vol.Required(CONF_ESCALATE, default=options.get(CONF_ESCALATE, False)): bool,
        }))
