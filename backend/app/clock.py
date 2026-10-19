"""Single source of "now" so tests can move time (lockouts, cooldowns, deadlines).

Call it as ``clock.utcnow()`` after ``from app import clock``; importing the
function directly would bind it before a test can replace it.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
