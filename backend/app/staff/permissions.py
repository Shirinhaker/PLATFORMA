from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDefinition:
    key: str
    label: str
    icon: str


@dataclass(frozen=True)
class PermissionTemplate:
    key: str
    label: str
    permissions: tuple[str, ...]


COMMON = (
    PermissionDefinition("chats", "Suhbatlar", "💬"),
    PermissionDefinition("notifications", "Bildirishnomalar", "🔔"),
    PermissionDefinition("reviews", "Mijoz fikrlari", "⭐"),
    PermissionDefinition("ads", "E’lon va reklamalar", "📢"),
    PermissionDefinition("documents", "Hujjatlar", "📄"),
)
TRADE = (
    PermissionDefinition("items", "Mahsulotlar", "🛍️"),
    PermissionDefinition("buyurtma", "Buyurtmalar", "📦"),
    PermissionDefinition("kassa", "Kassa", "🧾"),
    PermissionDefinition("ombor", "Ombor", "📦"),
    PermissionDefinition("expenses", "Xarajatlar", "💸"),
    PermissionDefinition("debts", "Qarz daftari", "📒"),
    PermissionDefinition("statistics", "Statistika", "📊"),
    PermissionDefinition("reports", "Hisobotlar", "📑"),
)
SERVICE = (
    PermissionDefinition("items", "Xizmatlar", "🧰"),
    PermissionDefinition("service_orders", "Xizmat buyurtmalari", "📋"),
    PermissionDefinition("kassa", "Kassa", "🧾"),
    PermissionDefinition("expenses", "Xarajatlar", "💸"),
    PermissionDefinition("debts", "Qarz daftari", "📒"),
    PermissionDefinition("statistics", "Statistika", "📊"),
    PermissionDefinition("reports", "Hisobotlar", "📑"),
)
DINING = (
    PermissionDefinition("items", "Menyu va xizmatlarimiz", "🍽️"),
    PermissionDefinition("dining_places", "Stollar va xonalar", "🍽️"),
    PermissionDefinition("dining_internal", "Ichki buyurtmalar", "🪑"),
    PermissionDefinition("dining_external", "Tashqi buyurtmalar", "🛵"),
    PermissionDefinition("kitchen", "Oshpaz buyurtmalari", "👨‍🍳"),
    PermissionDefinition("kassa", "Kassa", "🧾"),
    PermissionDefinition("ombor", "Ombor", "📦"),
    PermissionDefinition("expenses", "Xarajatlar", "💸"),
    PermissionDefinition("ready_food", "Tayyor taomlar ombori", "🍲"),
    PermissionDefinition("raw_stock", "Mahsulot va xomashyo", "🥕"),
    PermissionDefinition("recipes", "Retseptlar", "📖"),
    PermissionDefinition("production", "Taom tayyorlash / kirim", "🥘"),
    PermissionDefinition("open_accounts", "Kassadagi ochiq hisoblar", "🧾"),
    PermissionDefinition("payment_review", "To‘lovni tekshirish", "🔎"),
    PermissionDefinition("payment_confirm", "To‘lovni tasdiqlash", "✅"),
    PermissionDefinition("payment_problems", "Muammoli to‘lovlar", "⚠️"),
    PermissionDefinition("statistics", "Statistika", "📊"),
    PermissionDefinition("reports", "Hisobotlar", "📑"),
)
EDUCATION = (
    PermissionDefinition("education_courses", "Kurslar", "📚"),
    PermissionDefinition("education_groups", "Guruhlar", "👥"),
    PermissionDefinition("education_students", "O‘quvchilar", "🎓"),
    PermissionDefinition("education_schedule", "Dars jadvali", "🗓️"),
    PermissionDefinition("education_attendance", "Davomat", "✅"),
    PermissionDefinition("education_payments", "To‘lov nazorati", "💳"),
    PermissionDefinition("education_teachers", "O‘qituvchilar", "🧑‍🏫"),
    PermissionDefinition("education_enrollments", "Yozilish arizalari", "📝"),
    PermissionDefinition("education_payroll", "O‘qituvchi maoshi", "💰"),
    PermissionDefinition("education_statistics", "Ta’lim statistikasi", "📊"),
)

TRADE_DIRECTIONS = frozenset({
    "Savdo", "Qishloq xo'jaligi", "Ishlab chiqarish", "Hunarmandchilik",
})


def direction_kind(direction: str) -> str:
    if direction == "Umumiy ovqatlanish":
        return "dining"
    if direction in {"Ta'lim faoliyati", "Ta’lim faoliyati"}:
        return "education"
    if direction in TRADE_DIRECTIONS:
        return "trade"
    return "service"


def permission_definitions(direction: str) -> tuple[PermissionDefinition, ...]:
    specific = {
        "trade": TRADE,
        "service": SERVICE,
        "dining": DINING,
        "education": EDUCATION,
    }[direction_kind(direction)]
    return specific + COMMON


def permission_templates(direction: str) -> tuple[PermissionTemplate, ...]:
    templates = {
        "trade": (
            PermissionTemplate("seller", "Sotuvchi", ("items", "buyurtma", "kassa")),
            PermissionTemplate("cashier", "Kassir", ("buyurtma", "kassa", "debts")),
            PermissionTemplate("storekeeper", "Omborchi", ("ombor", "items", "expenses")),
        ),
        "service": (
            PermissionTemplate(
                "specialist", "Mutaxassis",
                ("items", "service_orders", "chats", "notifications"),
            ),
            PermissionTemplate("cashier", "Kassir", ("service_orders", "kassa", "debts")),
        ),
        "dining": (
            PermissionTemplate(
                "waiter", "Ofitsiant",
                ("dining_places", "dining_internal", "chats", "notifications"),
            ),
            PermissionTemplate(
                "cook", "Oshpaz",
                ("dining_internal", "dining_external", "kitchen", "ready_food", "production", "notifications"),
            ),
            PermissionTemplate(
                "cashier", "Kassir",
                ("kassa", "open_accounts", "payment_review", "payment_confirm", "payment_problems"),
            ),
            PermissionTemplate(
                "storekeeper", "Omborchi",
                ("ombor", "ready_food", "raw_stock", "recipes", "production", "expenses"),
            ),
        ),
        "education": (
            PermissionTemplate(
                "teacher", "O‘qituvchi",
                ("education_groups", "education_students", "education_schedule", "education_attendance", "notifications"),
            ),
            PermissionTemplate(
                "education_cashier", "Administrator / kassir",
                ("education_students", "education_payments", "education_enrollments", "chats", "notifications"),
            ),
        ),
    }[direction_kind(direction)]
    all_keys = tuple(item.key for item in permission_definitions(direction))
    return templates + (PermissionTemplate("manager", "Menejer (barchasi)", all_keys),)


ALL_PERMISSION_KEYS = frozenset(
    item.key
    for group in (COMMON, TRADE, SERVICE, DINING, EDUCATION)
    for item in group
)


def clean_permissions(values: object, direction: str = "") -> list[str]:
    if not isinstance(values, list):
        return []
    allowed = (
        {item.key for item in permission_definitions(direction)}
        if direction
        else ALL_PERMISSION_KEYS
    )
    return list(dict.fromkeys(
        str(value) for value in values if str(value) in allowed
    ))


RESOURCE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "items": ("items",),
    "item_groups": ("items",),
    # Xodim buyurtmalari category bo'yicha typed /orders API'da ajratiladi.
    # Generic snapshot butun inboxni aralashtirgani uchun faqat egada qoladi.
    "orders": ("__business_owner__",),
    "messages": ("chats",),
    "business_reviews": ("reviews",),
    "advertisements": ("ads",),
    "listings": ("ads",),
    "stories": ("ads",),
    "notifications": ("notifications",),
    "dining_places": ("dining_places",),
    "dining_orders": ("dining_internal", "dining_external", "kitchen"),
    "medical_doctors": ("service_orders",),
    "medical_staff": ("service_orders",),
    "medical_queue": ("service_orders",),
    "education_groups": ("education_groups",),
    "education_students": ("education_students",),
    "education_schedule": ("education_schedule",),
    "education_attendance": ("education_attendance",),
    "education_payments": ("education_payments",),
    "education_teachers": ("education_teachers",),
    "education_enrollments": ("education_enrollments",),
    "education_payroll": ("education_payroll",),
    "sales": ("kassa",),
    "cash_transactions": ("kassa",),
    "cash_register_transactions": ("kassa",),
    "expenses": ("expenses",),
    "debtors": ("debts",),
    "qarz_transactions": ("debts",),
    "warehouse_items": ("ombor", "production"),
    "warehouse_tx": ("ombor", "production"),
    "documents": ("documents",),
    "business_documents": ("documents",),
    "incoming_documents": ("documents",),
    "outgoing_documents": ("documents",),
    "internal_documents": ("documents",),
    "counterparties": ("documents",),
}


def allowed_payload_resources(permissions: tuple[str, ...]) -> frozenset[str]:
    granted = set(permissions)
    return frozenset(
        resource
        for resource, required in RESOURCE_PERMISSIONS.items()
        if granted.intersection(required)
    )
