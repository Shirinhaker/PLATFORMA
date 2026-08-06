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
