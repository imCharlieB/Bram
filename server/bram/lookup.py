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
SECURITY = re.compile(r"\b(secur\w*|hack\w*|exposed|intru\w*|safe|vulnerab\w*)\b", re.I)
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
    changes = _changes(result)
    days = _text(result.get("days"), 4)
    if not changes:
        return [f"History of {name}: no changes recorded in {days} days"]
    counts, totals = result.get("counts"), result.get("totals")
    totals = totals if isinstance(totals, dict) else {}
    total = ", ".join(
        f"{_text(k, 20)} {_text(v, 8)} times, {_text(totals.get(k), 30)} in all"
        for k, v in sorted(counts.items())) if isinstance(counts, dict) else ""
    return [f"History of {name}, newest first, last {days} days. Use these lengths; do not work "
            "out your own: " + "; ".join(f"{c[0]} became {c[1]} {c[2]}" for c in changes),
            f"Totals for {name}: {total}"]


def _changes(result: dict) -> list[list[str]]:
    return [[_text(part, 40) for part in c] for c in _list(result.get("changes"), 20)
            if isinstance(c, list) and len(c) == 3]


def history_facts(name: str, result: dict | None) -> list[str]:
    """Shown beside the answer, straight from Home Assistant."""
    if result is None or result.get("error"):
        return []
    return [f"{name}: {c[1]} {c[0]}, {c[2]}" for c in _changes(result)[:4]]


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


def _findings(result: dict) -> list[tuple[str, str]]:
    return [(_text(f.get("level"), 10), _text(f.get("text"), 200))
            for f in _list(result.get("findings"), 15) if isinstance(f, dict)]


def security_lines(name: str, result: dict | None) -> list[str]:
    if result is None or result.get("error"):
        off = result is not None and result.get("error") == "off"
        return [f"Security check of {name}: " + (
            "turned off; the owner can turn it on in Home Assistant, BRAM, Configure, What chat "
            "may look up" if off else "could not be read")]
    found = _findings(result)
    missed = ", ".join(_text(x, 60) for x in _list(result.get("not_checked"), 20))
    return [f"Security check of {name}, Home Assistant only. Never say it is secure or safe, even "
            "if nothing was found; say what was found and what was not checked.",
            *(f"{level}: {text}" for level, text in found),
            *([] if found else ["Nothing found by the checks that ran"]),
            f"Not checked: {missed or 'unknown'}"]


def security_facts(name: str, result: dict | None) -> list[str]:
    if result is None or result.get("error"):
        return []
    found = [f"{name}: {text}" for _, text in _findings(result)[:5]]
    return [*(found or [f"{name}: nothing found by the checks that ran"]),
            f"{name}: does not check your network, router, or passwords"]
