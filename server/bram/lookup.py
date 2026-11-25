"""Decide what a question needs looked up, and put the answer in plain lines.

Plain rules choose; the model cannot ask for anything.
"""
from __future__ import annotations

import re

HISTORY = re.compile(
    r"\b(when|last|history|often|how many|how long|times|yesterday|today|tonight|overnight|"
    r"week|since|ago|earlier|recently|morning|did|was|were|been)\b", re.I)
PROBLEMS = re.compile(
    r"\b(errors?|logs?|problems?|issues?|repairs?|broken|failing|failed|wrong|batter(y|ies)|"
    r"updates?|unavailable|health)\b", re.I)
MAX_LOOKUPS = 3


def _text(value: object, limit: int = 160) -> str:
    text = str(value) if isinstance(value, (str, int, float)) else ""
    return " ".join("".join(c if c.isprintable() else " " for c in text).split())[:limit]


def _list(value: object, limit: int) -> list:
    return value[:limit] if isinstance(value, list) else []


def history_lines(name: str, result: dict | None) -> list[str]:
    if result is None or result.get("error"):
        off = result is not None and result.get("error") == "off"
        return [f"History of {name}: " + (
            "turned off; the owner can turn it on in Home Assistant, BRAM, Configure, What chat "
            "may look up" if off else "could not be read")]
    changes = [c for c in _list(result.get("changes"), 20) if isinstance(c, list) and len(c) == 2]
    if not changes:
        return [f"History of {name}: no changes recorded in {_text(result.get('days'), 4)} days"]
    counts = result.get("counts")
    total = ", ".join(f"{_text(k, 20)} {_text(v, 8)} times" for k, v in sorted(counts.items())
                      ) if isinstance(counts, dict) else ""
    return [f"History of {name}, newest first, last {_text(result.get('days'), 4)} days: "
            + "; ".join(f"{_text(when, 30)} became {_text(word, 20)}" for when, word in changes),
            f"Totals for {name}: {total}"]


def problem_lines(name: str, result: dict | None) -> list[str]:
    if result is None or result.get("error"):
        off = result is not None and result.get("error") == "off"
        return [f"Home Assistant problems in {name}: " + (
            "turned off; the owner can turn it on in Home Assistant, BRAM, Configure, What chat "
            "may look up" if off else "could not be read")]
    lines = [f"Home Assistant problems in {name}. Any cause you suggest is a guess; say so:"]
    for e in _list(result.get("errors"), 12):
        if isinstance(e, dict):
            lines.append(f"{_text(e.get('level'), 10)} from {_text(e.get('from'), 60)}, "
                         f"{_text(e.get('times'), 8)} times, first {_text(e.get('first'), 30)}, "
                         f"last {_text(e.get('last'), 30)}: {_text(e.get('text'))}")
    if result.get("more_errors"):
        lines.append(f"{_text(result['more_errors'], 6)} more log entries not shown")
    for key, label in (("failed", "Integrations that failed to start"),
                       ("repairs", "Open repairs"), ("low_batteries", "Low batteries"),
                       ("updates", "Updates waiting")):
        found = [_text(x, 80) for x in _list(result.get(key), 10)]
        lines.append(f"{label}: {', '.join(found) or 'none'}")
    lines.append(f"Entities unavailable now: {_text(result.get('unavailable'), 6)}")
    return lines
