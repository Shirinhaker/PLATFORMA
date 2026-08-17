"""Xizmatlarni `app.state` dan olish va audit meta ma'lumoti."""

from __future__ import annotations

from fastapi import Request

from app.admin.audit import request_meta
from app.admin.moderation import AdminModerationService
from app.admin.payments_service import AdminPaymentService
from app.admin.reports_service import AdminReportsService
from app.payments.service_parts import PaymentService


def admin_payment_service(request: Request) -> AdminPaymentService:
    return request.app.state.admin_payment_service


def payment_service(request: Request) -> PaymentService:
    return request.app.state.payment_service


def moderation_service(request: Request) -> AdminModerationService:
    return request.app.state.admin_moderation_service


def reports_service(request: Request) -> AdminReportsService:
    return request.app.state.admin_reports_service


def _meta(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return request_meta(request, settings.admin_audit_ip_secret or settings.csrf_secret)
