"""Kabinet payloadi uchun jadval-konstantalar.

Resurs ta'riflari, holat ro'yxatlari va reklama narxlari. Kod emas,
ma'lumot — shuning uchun alohida turadi.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AsyncIterator[AsyncSession]]


@dataclass(frozen=True)
class ResourceSpec:
    create: bool = False
    update: bool = False
    delete: bool = False


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "business_subscriptions": ResourceSpec(),
    "subscription_payments": ResourceSpec(),
    "item_groups": ResourceSpec(create=True, update=True, delete=True),
    "items": ResourceSpec(create=True, update=True, delete=True),
    "listings": ResourceSpec(create=True, update=True, delete=True),
    "orders": ResourceSpec(update=True),
    "messages": ResourceSpec(create=True, update=True, delete=True),
    "business_reviews": ResourceSpec(update=True),
    "advertisements": ResourceSpec(create=True, update=True, delete=True),
    "stories": ResourceSpec(create=True, update=True, delete=True),
    "notifications": ResourceSpec(update=True, delete=True),
    "notify_filters": ResourceSpec(create=True, delete=True),
    "push_preferences": ResourceSpec(),
    "followers": ResourceSpec(),
    "following": ResourceSpec(delete=True),
    "dining_places": ResourceSpec(create=True, update=True, delete=True),
    "dining_orders": ResourceSpec(),
    "medical_staff": ResourceSpec(),
    "medical_doctors": ResourceSpec(create=True, update=True),
    "medical_doctor_services": ResourceSpec(),
    "medical_queue": ResourceSpec(),
    "medical_queue_history": ResourceSpec(),
    # Yozish amallari relatsion jadvallarga yo'naltiriladi
    # (`service.py`), JSON payloadga tegmaydi.
    "education_groups": ResourceSpec(create=True, update=True, delete=True),
    "education_students": ResourceSpec(create=True, update=True, delete=True),
    "education_enrollments": ResourceSpec(),
}

SENSITIVE_NAMES = {
    "password",
    "password_hash",
    "pass_hash",
    "pass_plain",
    "token",
    "token_hash",
    "secret",
    "private_key",
    "csrf_token",
    "telegram_user_id",
}

SENSITIVE_SUFFIXES = ("_password", "_secret", "_token", "_hash")

OWNERSHIP_FIELDS = {
    "account_id",
    "business_id",
    "user_id",
    "owner_id",
    "owner_account_id",
    "actor_id",
    "actor_account_id",
}

IMMUTABLE_FIELDS = OWNERSHIP_FIELDS | {"id", "created_at"}

ORDER_STATUSES = {
    "new",
    "accepted",
    "payment_waiting",
    "payment_confirmed",
    "preparing",
    "ready",
    "tayyor",
    "courier_search",
    "courier_assigned",
    "courier_arrived_store",
    "handoff_waiting_seller",
    "in_delivery",
    "courier_arrived_customer",
    "delivered_waiting_customer",
    "delivered",
    "pickup_waiting_customer",
    "done",
    "rejected",
    "cancelled",
    "canceled",
}

GENERIC_STATUSES = {
    "draft",
    "pending",
    "active",
    "paused",
    "archived",
    "approved",
    "rejected",
    "expired",
    "cancelled",
    "canceled",
}

TERMINAL_ORDER_STATUSES = {
    "done",
    "delivered",
    "pickup_waiting_customer",
    "rejected",
    "cancelled",
    "canceled",
}

QUEUE_DIRECTIONS = {
    "Transport va logistika",
    "Xizmat ko'rsatish",
    "Maishiy xizmatlar",
    "Qurilish",
    "Tibbiy xizmatlar",
    "Ko'chmas mulk",
    "Axborot texnologiyalari",
    "Konsalting va professional",
    "Madaniyat, sport, ko'ngilochar",
    "Turizm va mehmonxona",
    "Reklama va marketing",
    "Poligrafiya va nashriyot",
    "Moliyaviy faoliyat",
    "Import-eksport",
}

MEDICAL_RESOURCES = {
    "medical_staff",
    "medical_doctors",
    "medical_doctor_services",
    "medical_queue",
    "medical_queue_history",
}

EDUCATION_RESOURCES = {
    "education_groups",
    "education_students",
    "education_enrollments",
}

MEDICAL_QUEUE_STATUSES = {
    "waiting",
    "called",
    "in_service",
    "done",
    "no_show",
    "cancelled",
    "skipped",
}

MEDICAL_QUEUE_TERMINAL = {"done", "cancelled", "no_show"}

AD_VALID_DURATIONS = {1, 3, 7, 14, 30}

AD_DISTRICT_HOUR_RATE = 20_000

AD_REGION_DISTRICT_COUNTS = {
    "Toshkent shahri": 11,
    "Toshkent viloyati": 14,
    "Andijon viloyati": 14,
    "Farg'ona viloyati": 15,
    "Namangan viloyati": 11,
    "Samarqand viloyati": 14,
    "Buxoro viloyati": 11,
    "Qashqadaryo viloyati": 13,
    "Surxondaryo viloyati": 13,
    "Jizzax viloyati": 12,
    "Sirdaryo viloyati": 10,
    "Navoiy viloyati": 10,
    "Xorazm viloyati": 10,
    "Qoraqalpog'iston Respublikasi": 14,
}

DINING_ACTIVE_FIELDS = {
    "active_id",
    "active_kind",
    "customer_name",
    "booking_date",
    "booking_time",
    "guests",
    "total",
}
