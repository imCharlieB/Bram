import datetime
import logging

import pytest
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.bram.details import values
from custom_components.bram.queries import answer

TEMP = "sensor.den"


async def test_past_hours_in_the_unit_shown(recorder_mock, hass, enable_custom_integrations):
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    hass.states.async_set(TEMP, "68", {"unit_of_measurement": "\u00b0F",
                                       "device_class": "temperature"})
    hour = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    starts = [hour - datetime.timedelta(hours=2), hour - datetime.timedelta(days=100)]
    async_import_statistics(hass, {
        "has_mean": True, "mean_type": 1, "has_sum": False, "name": None, "source": "recorder",
        "statistic_id": TEMP, "unit_class": "temperature", "unit_of_measurement": "\u00b0C",
    }, [{"start": s, "mean": 20.0, "min": 19.0, "max": 21.0} for s in starts])
    await async_wait_recording_done(hass)
    entry = MockConfigEntry(domain="bram", options={"share_history": True, "entities": [TEMP]})
    first = await answer(hass, entry, {}, "statistics:0", TEMP)
    ((at, low, mean, high),) = first["rows"]
    assert at == starts[0].timestamp() and first["more"]
    assert (round(low, 1), round(mean, 1), round(high, 1)) == (66.2, 68.0, 69.8)
    second = await answer(hass, entry, {}, "statistics:1", TEMP)
    assert len(second["rows"]) == 1


@pytest.mark.parametrize(("options", "what", "error"), [
    ({"entities": [TEMP]}, "statistics:0", "off"),
    ({"share_history": True, "entities": []}, "statistics:0", "refused"),
    ({"share_history": True, "entities": [TEMP]}, "statistics:-1", "refused"),
    ({"share_history": True, "entities": [TEMP]}, "statistics:0; x", "refused")])
async def test_past_is_refused(hass, options, what, error):
    entry = MockConfigEntry(domain="bram", options=options)
    assert await answer(hass, entry, {}, what, TEMP) == {"error": error}


async def test_values(hass):
    def of(entity, state, **attrs):
        hass.states.async_set(entity, state, attrs)
        return values(hass, hass.states.get(entity))

    found = of("climate.a", "cool", current_temperature=75, temperature=72, hvac_action="cooling",
               fan_mode="auto", preset_mode=None)
    assert found == {"now": 75, "target": 72, "action": "cooling", "fan": "auto", "mode": "cool",
                     "unit": hass.config.units.temperature_unit}
    assert of("sensor.a", "5.5", unit_of_measurement="W") == {"now": 5.5, "unit": "W"}
    assert of("sensor.b", "hello", unit_of_measurement="W") == {}
    assert of("sensor.c", "nan", unit_of_measurement="W") == {"unit": "W"}
    assert of("sensor.d", "unavailable", unit_of_measurement="W") == {}
    assert of("light.a", "on", brightness=5) == {}
