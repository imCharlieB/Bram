import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.setup import async_setup_component


@pytest.fixture
async def custom(hass, enable_custom_integrations):
    # Assist needs this; a real Home Assistant always has it.
    assert await async_setup_component(hass, "homeassistant", {})
    # Setting BRAM up must not write blueprints into the test package's folder.
    with patch("custom_components.bram.blueprints.install", AsyncMock()):
        yield


RULES = set(re.findall(r"^\| ([A-G]\d+) \|", (Path(__file__).parents[1] / "HARD_RULES.md")
                       .read_text(encoding="utf-8"), re.M))


def pytest_configure(config):
    config.addinivalue_line("markers", "rule(id): this test proves a hard rule")


def pytest_collection_modifyitems(items):
    for item in items:
        for mark in item.iter_markers("rule"):
            if len(mark.args) != 1 or mark.args[0] not in RULES:
                raise pytest.UsageError(f"{item.nodeid}: unknown hard rule {mark.args}")
