import re
from pathlib import Path

import pytest

RULES = set(re.findall(r"^\| ([A-G]\d+) \|", (Path(__file__).parents[2] / "HARD_RULES.md")
                       .read_text(encoding="utf-8"), re.M))


def pytest_configure(config):
    config.addinivalue_line("markers", "rule(id): this test proves a hard rule")


def pytest_collection_modifyitems(items):
    for item in items:
        for mark in item.iter_markers("rule"):
            if len(mark.args) != 1 or mark.args[0] not in RULES:
                raise pytest.UsageError(f"{item.nodeid}: unknown hard rule {mark.args}")
