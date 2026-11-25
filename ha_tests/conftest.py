import pytest
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def _custom(hass, enable_custom_integrations):
    # Assist needs this; a real Home Assistant always has it.
    assert await async_setup_component(hass, "homeassistant", {})
    yield
