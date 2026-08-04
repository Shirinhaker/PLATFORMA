from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PayType = Literal["naqd", "karta", "qarz"]


class CashSaleLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_item_id: int | None = Field(default=None, gt=0)
    name: str = Field(default="", max_length=220)
    qty: float = Field(gt=0, le=100_000)
    price: int = Field(gt=0, le=10**12)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class CashReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CashSaleLineCreate] = Field(min_length=1, max_length=30)
    pay_type: PayType = "naqd"
    debtor_id: int | None = Field(default=None, gt=0)
    note: str = Field(default="", max_length=200)
    sale_date: date | None = None

    @field_validator("note", mode="before")
    @classmethod
    def clean_note(cls, value):
        return value.strip() if isinstance(value, str) else value


class CashPaymentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pay_type: PayType
    debtor_id: int | None = Field(default=None, gt=0)


class CashCatalogItemRead(BaseModel):
    id: int
    name: str
    price: int
    price_text: str
    unit: str
    track_stock: bool
    stock_qty: float
    low_stock: bool


class CashReceiptLineRead(BaseModel):
    id: int
    catalog_item_id: int | None
    item_name: str
    qty: float
    unit: str
    price: int
    total: int
    cost_total: int


class CashReceiptRead(BaseModel):
    id: int
    receipt_no: int | None
    source: str
    order_id: int | None
    pay_type: str
    pay_text: str
    debtor_name: str
    note: str
    who: str
    created_at: datetime
    total: int
    can_delete: bool
    can_change_payment: bool
    lines: list[CashReceiptLineRead]


class CashTotalsRead(BaseModel):
    all: int = 0
    cash_in: int = 0
    naqd: int = 0
    karta: int = 0
    qarz: int = 0
    qarzpay: int = 0
    order: int = 0


class CashRegisterRead(BaseModel):
    day: date
    totals: CashTotalsRead
    receipts: list[CashReceiptRead]


class CashReceiptCreated(BaseModel):
    ok: bool = True
    id: int
    receipt_no: int
    count: int
    total: int
