"""v6 solishtiruvi uchun konstantalar."""

from __future__ import annotations

TERMINAL_ORDER_STATUSES = {
    "done",
    "delivered",
    "cancelled",
    "canceled",
    "rejected",
    "pickup_waiting_customer",
}

SERVICE_ORDER_TYPES = {"booking", "service", "queue", "medical"}
