from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ServiceType = Literal["advertisement", "subscription", "listing"]


class PaymentPriceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_code: str
    service_type: str
    amount_uzs: int = Field(ge=0)
    plan_code: str = ""
    duration_months: int = 0


class PaymentMethodRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    method_type: str
    name: str
    recipient_name: str = ""
    instructions: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class PaymentCatalogRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prices: list[PaymentPriceRead]
    methods: list[PaymentMethodRead]


class PaymentReceipt(BaseModel):
    """R2'ga yuklangan chek — kalit `media` moduli bergan."""

    model_config = ConfigDict(extra="forbid")

    object_key: str = Field(min_length=1, max_length=1024)
    filename: str = Field(default="", max_length=255)
    mime: str = Field(max_length=120)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PaymentRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_type: ServiceType
    price_code: str = Field(min_length=1, max_length=64)
    payment_method_id: int = Field(gt=0)
    receipt: PaymentReceipt
    plan_code: str = Field(default="", max_length=32)
    duration_months: int = Field(default=0, ge=0, le=60)
    quantity: int = Field(default=1, ge=1, le=10000)
    target_id: int | None = Field(default=None, gt=0)


class PaymentAttemptRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_no: int
    review_status: str
    review_reason: str = ""
    submitted_at: int


class PaymentRequestRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    request_code: str
    service_type: str
    status: str
    plan_code: str = ""
    duration_months: int = 0
    quantity: int = 1
    amount: int = Field(ge=0)
    currency: str = "UZS"
    price_code: str = ""
    public_reason: str = ""
    created_at: int
    updated_at: int
    attempts: list[PaymentAttemptRead] = Field(default_factory=list)


class PaymentResubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt: PaymentReceipt


class PaymentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="", max_length=500)
