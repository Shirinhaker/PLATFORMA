"""Admin panel yo'llari uchun konstantalar."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Path

from app.admin.moderation import AdminModerationService
from app.admin.payments_service import AdminPaymentService
from app.admin.reports_service import AdminReportsService
from app.admin.router_parts.deps import (
    admin_payment_service,
    moderation_service,
    payment_service,
    reports_service,
)
from app.payments.service_parts import PaymentService

PaymentId = Annotated[int, Path(gt=0)]

PaymentsDep = Annotated[AdminPaymentService, Depends(admin_payment_service)]

ReviewDep = Annotated[PaymentService, Depends(payment_service)]

ModerationDep = Annotated[AdminModerationService, Depends(moderation_service)]

ReportsDep = Annotated[AdminReportsService, Depends(reports_service)]

ActorType = Annotated[str, Path(pattern="^(user|business)$")]

ContentKind = Annotated[str, Path(min_length=1, max_length=32)]

AccountId = Annotated[int, Path(gt=0)]

ReportId = Annotated[int, Path(gt=0)]

CONTENT_ACTIONS = {"hide": "hidden", "restore": "visible", "remove": "removed"}
