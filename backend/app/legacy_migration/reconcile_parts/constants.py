"""Ko'chirish bosqichi natijasi va konstantalar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageResult:
    created: int = 0
    reused: int = 0
    updated: int = 0
    quarantined: int = 0
    issues: int = 0
