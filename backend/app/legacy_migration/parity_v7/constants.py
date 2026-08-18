"""Parity tekshiruvi uchun konstantalar."""

from __future__ import annotations

EXPLICIT_DEMO_FLAGS = (
    "is_demo",
    "demo",
    "is_test",
    "test_mode",
    "demo_mode",
)

SENSITIVE_KEYS = {
    "pass_hash",
    "pass_plain",
    "password",
    "password_hash",
    "biz_pass_hash",
    "token",
    "token_hash",
    "start_token",
    "start_token_hash",
    "code_hash",
    "otp",
    "otp_hash",
    "secret",
    "private_key",
}

SENSITIVE_SUFFIXES = (
    "_password",
    "_secret",
    "_token",
)

_DROP = object()

BUSINESS_MODULE_TABLES = (
    "advertisements",
    "business_subscriptions",
    "staff",
    "staff_attendance",
    "staff_professions",
    "documents",
    "contractors",
    "stock_moves",
    "production_batches",
    "stock_batches",
    "item_recipes",
    "expenses",
    "expense_cats",
    "sales",
    "dining_places",
    "dining_bookings",
    "education_groups",
    "education_students",
    "education_student_group_history",
    "education_attendance",
    "education_payments",
    "education_teachers",
    "education_exams",
    "education_exam_results",
    "education_enrollments",
    "education_teacher_payments",
    "medical_doctor_services",
    "medical_doctors",
    "medical_queue",
    "medical_queue_history",
    # Eski snapshotlarda uchrashi mumkin bo‘lgan avvalgi nomlar.
    "business_reviews",
    "business_staff",
    "employees",
    "business_documents",
    "incoming_documents",
    "outgoing_documents",
    "internal_documents",
    "counterparties",
    "dining_orders",
    "warehouse_items",
    "warehouse_tx",
    "cash_transactions",
    "cash_register_transactions",
    "medical_queues",
    "medical_appointments",
)

USER_MODULE_TABLES = (
    "specialist_credentials",
    "specialist_offers",
    "specialist_portfolio",
    "push_preferences",
)
