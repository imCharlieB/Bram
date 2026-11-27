"""Puts BRAM's blueprints where Home Assistant lists them, so there is nothing to import.

A blueprint does nothing until the owner creates an automation from it. A file the owner
changed, or one BRAM did not write, is never replaced.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

SOURCE = Path(__file__).parent / "blueprints" / "automation"


def _mark(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def copy(source: Path, target: Path, written: dict[str, str]) -> dict[str, str]:
    """Copy new and updated blueprints. Returns what BRAM wrote, by file name."""
    written = dict(written)
    for file in sorted(source.glob("*.yaml")):
        new, there = file.read_text(encoding="utf-8"), target / file.name
        if there.exists():
            now = there.read_text(encoding="utf-8")
            if now == new:
                written[file.name] = _mark(new)
                continue
            if written.get(file.name) != _mark(now):
                continue  # changed by the owner, or not BRAM's
        target.mkdir(parents=True, exist_ok=True)
        there.write_text(new, encoding="utf-8")
        written[file.name] = _mark(new)
    return written


async def install(hass: HomeAssistant) -> None:
    store: Store[dict[str, str]] = Store(hass, 1, f"{DOMAIN}.blueprints")
    written = await store.async_load() or {}
    target = Path(hass.config.path("blueprints", "automation", DOMAIN))
    done = await hass.async_add_executor_job(copy, SOURCE, target, written)
    if done != written:
        await store.async_save(done)
