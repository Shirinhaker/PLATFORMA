"""Admin paneli sxemalari."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminAuthStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telegram_user_id: int = Field(gt=0)


class AdminAuthStarted(BaseModel):
    challenge_id: int
    expires_in: int


class AdminAuthVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: int = Field(gt=0)
    code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")


class AdminIdentity(BaseModel):
    telegram_user_id: int


class AdminPaymentRow(BaseModel):
    """To'lov navbati qatori. Chek fayli yo'li javobda chiqmaydi."""

    id: int
    request_code: str
    actor_type: str
    account_id: int
    account_login: str
    service_type: str
    plan_code: str
    duration_months: int
    quantity: int
    amount: int
    currency: str
    price_code: str
    status: str
    public_reason: str
    reviewed_by_admin_tg_id: int | None
    created_at: int
    updated_at: int


class AdminPaymentAttempt(BaseModel):
    attempt_no: int
    review_status: str
    review_reason: str
    submitted_at: int
    reviewed_at: int
    receipt_mime: str
    receipt_sha256: str
    has_receipt: bool


class AdminPaymentDetail(AdminPaymentRow):
    target_id: int | None
    payment_method_id: int
    payment_method_name: str
    internal_note: str
    approved_at: int
    rejected_at: int
    cancelled_at: int
    attempts: list[AdminPaymentAttempt]


class AdminReceiptLink(BaseModel):
    """Chek uchun qisqa muddatli imzolangan havola."""

    url: str
    mime: str
    expires_in: int


class AdminDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="", max_length=500)
    internal_note: str = Field(default="", max_length=1000)


class AdminPriceRow(BaseModel):
    id: int
    price_code: str
    service_type: str
    amount_uzs: int
    config: dict[str, Any]
    active: bool
    updated_at: int


class AdminPriceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_uzs: int = Field(ge=0, le=1_000_000_000)
    active: bool = True


class AdminMethodRow(BaseModel):
    id: int
    method_type: str
    name: str
    recipient_name: str
    instructions: str
    details: dict[str, Any]
    sort_order: int
    active: bool


class AdminMethodWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_type: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    recipient_name: str = Field(default="", max_length=160)
    instructions: str = Field(default="", max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = Field(default=0, ge=0, le=999)
    active: bool = True


# --- A2: moderatsiya ---


class AdminAccountRow(BaseModel):
    actor_type: str
    account_id: int
    login: str
    telegram_user_id: int | None
    name: str
    phone: str
    restrictions: list[str]


class AdminRestrictionRow(BaseModel):
    id: int
    restriction: str
    status: str
    reason: str
    created_by_tg_id: int
    created_at: int
    revoked_reason: str
    revoked_at: int


class AdminNoteRow(BaseModel):
    id: int
    note: str
    admin_tg_id: int
    created_at: int


class AdminAccountDetail(BaseModel):
    actor_type: str
    account_id: int
    login: str
    telegram_user_id: int | None
    status: str
    created_at: int
    name: str
    phone: str
    restrictions: list[AdminRestrictionRow]
    notes: list[AdminNoteRow]


class AdminRestrictionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restriction: str = Field(
        pattern="^(content_hidden|account_blocked)$",
    )
    reason: str = Field(min_length=1, max_length=2000)


class AdminRestrictionResult(BaseModel):
    id: int
    already_active: bool


class AdminNoteWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=2000)


class AdminContentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="", max_length=2000)


class AdminContentHistory(BaseModel):
    status: str
    reason: str
    changed_by_tg_id: int
    created_at: int


class AdminContentStatus(BaseModel):
    content_kind: str
    content_id: int
    status: str
    history: list[AdminContentHistory] = Field(default_factory=list)


class AdminContentResult(BaseModel):
    content_kind: str
    content_id: int
    status: str
    previous_status: str
    created_at: int


# --- A3: shikoyatlar va audit ---


class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_kind: str = Field(min_length=1, max_length=32)
    content_id: int = Field(gt=0)
    reason_code: str = Field(
        pattern="^(fraud|spam|illegal|abuse|other)$",
    )
    comment: str = Field(default="", max_length=1000)


class ReportRow(BaseModel):
    id: int
    reporter_account_id: int
    content_kind: str
    content_id: int
    reason_code: str
    comment: str
    status: str
    assigned_admin_tg_id: int | None
    resolution: str
    created_at: int
    updated_at: int


class ReportDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: str = Field(min_length=1, max_length=2000)


class AuditRow(BaseModel):
    id: int
    admin_tg_id: int
    action: str
    target_kind: str
    target_id: str
    reason: str
    created_at: int


class AuditDetail(AuditRow):
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    ip_hash: str
    user_agent: str
