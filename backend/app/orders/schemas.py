from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class OrderCreateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    public_id: str = Field(min_length=1, max_length=64)
    qty: float = Field(default=1, gt=0, le=999)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_kind: Literal["user", "business"]
    provider_public_id: str = Field(min_length=1, max_length=64)
    items: list[OrderCreateItem] = Field(default_factory=list, max_length=50)
    listing_public_id: str = Field(default="", max_length=64)
    title: str = Field(default="", max_length=180)
    phone: str = Field(default="", max_length=80)
    order_type: Literal["delivery", "pickup", "booking"] = "delivery"
    address: str = Field(default="", max_length=500)
    desired_time: str = Field(default="", max_length=160)
    delivery_lat: float | None = Field(default=None, ge=-90, le=90)
    delivery_lng: float | None = Field(default=None, ge=-180, le=180)
    note: str = Field(default="", max_length=1000)

    @field_validator("title", "phone", "address", "desired_time", "note", mode="before")
    @classmethod
    def strip_text(cls, value, info: ValidationInfo):
        if not isinstance(value, str):
            return value
        limits = {
            "title": 180,
            "phone": 80,
            "address": 500,
            "desired_time": 160,
            "note": 1000,
        }
        return value.strip()[:limits[info.field_name]]


class OrderStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "rejected", "tayyor", "cancelled"]


class OrderPaymentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["confirmed", "rejected", "pending", "debt"]
    debtor_id: int | None = Field(default=None, gt=0)


class OrderProblemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal[
        "not_received", "amount_short", "receipt_mismatch",
        "receipt_unreadable", "wrong_receipt", "other",
    ]
    note: str = Field(default="", max_length=1000)

    @field_validator("note", mode="before")
    @classmethod
    def clean_note(cls, value):
        return value.strip()[:1000] if isinstance(value, str) else value


class OrderProblemSolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solution: Literal["pickup", "wait", "new_receipt"]


class OrderMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=2000)
    media_type: Literal["text", "photo"] = "text"
    object_key: str = Field(default="", max_length=1024)
    file_name: str = Field(default="", max_length=255)
    reply_to_id: int | None = Field(default=None, gt=0)

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip()[:2000] if isinstance(value, str) else value


class OrderMessageEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip()[:2000] if isinstance(value, str) else value


class OrderItemRead(BaseModel):
    id: int
    public_id: str = ""
    name: str
    price: str
    qty: float
    unit: str
    line_total: int
    note: str
    kind: str


class OrderMessageReplyRead(BaseModel):
    id: int
    text: str
    media_type: str
    is_deleted: bool
    sender_name: str


class OrderMessageRead(BaseModel):
    id: int
    text: str
    media_type: str
    media_url: str
    file_name: str
    reply_to_id: int | None
    reply: OrderMessageReplyRead | None = None
    edited_at: datetime | None
    deleted_at: datetime | None
    is_deleted: bool
    mine: bool
    sender_name: str
    sender_kind: str
    created_at: datetime


class OrderRead(BaseModel):
    id: int
    view: Literal["customer", "provider"]
    title: str
    customer_name: str
    customer_public_id: str
    provider_name: str
    provider_kind: str
    provider_public_id: str
    item_public_id: str
    listing_public_id: str
    order_type: str
    order_category: str
    address: str
    desired_time: str
    delivery_lat: float | None
    delivery_lng: float | None
    note: str
    phone: str
    qty: float
    total_amount: int
    total_text: str
    status: str
    payment_status: str
    pay_type: str
    debtor_id: int | None
    receipt_message_id: int | None
    problem_open: bool
    problem_reason: str
    problem_note: str
    problem_solution: str
    problem_opened_at: datetime | None
    problem_resolved_at: datetime | None
    seller_completed_at: datetime | None
    customer_received_at: datetime | None
    last_event: str
    chat_count: int = 0
    last_chat: str = ""
    last_chat_at: datetime | None = None
    pay_card: str
    pay_holder: str
    pay_qr_url: str
    provider_address: str
    provider_phone: str
    provider_work_hours: dict[str, object]
    provider_lat: float | None
    provider_lng: float | None
    customer_seen_at: datetime | None
    provider_seen_at: datetime | None
    seen_at: datetime | None
    is_unread: bool
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class OrderChatOtherRead(BaseModel):
    side: Literal["customer", "provider"]
    kind: Literal["user", "business"]
    public_id: str
    name: str


class OrderChatRead(BaseModel):
    ok: bool = True
    side: Literal["customer", "provider"]
    seen_at: datetime
    other: OrderChatOtherRead
    order: OrderRead
    messages: list[OrderMessageRead]
