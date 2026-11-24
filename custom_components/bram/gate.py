"""The only place an action request may be decided.

M1: refuses everything. It holds no reference to Home Assistant, so it has no
way to run an action.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def decide(request: object) -> Decision:
    return Decision(False, "log_only")
