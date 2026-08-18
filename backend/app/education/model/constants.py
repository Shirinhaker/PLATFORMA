"""O'quv markazi jadvallari uchun umumiy konstantalar."""

from __future__ import annotations

ENROLLMENT_STATUSES = ("new", "accepted", "rejected")

ACTIVE_ENROLLMENT_SQL = "status IN ('new', 'accepted')"
