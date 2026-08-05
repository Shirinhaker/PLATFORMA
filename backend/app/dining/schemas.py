"""Ovqatlanish domeni sxemalari.

Javob maydonlari v1656 frontendi kutgan nomlar bilan bir xil — vaqt
qiymatlari unix songa aylantiriladi, garchi bazada `timestamptz` bo'lsa
ham.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DiningItemInput(BaseModel):
    """Zakazga qo'shiladigan taom."""

    item_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, le=999)


class DiningPlaceWrite(BaseModel):
    kind: str = Field(pattern="^(table|room)$")
    name: str = Field(min_length=1, max_length=120)
    seats: int = Field(default=0, ge=0, le=999)
    x: float = 4
    y: float = 4
    locked: bool = True


class DiningPlaceMove(BaseModel):
    """Zal rejasida stolni surish."""

    x: float
    y: float
    locked: bool | None = None


class DiningBookingCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=80)
    booking_date: str = Field(min_length=1, max_length=10)
    booking_time: str = Field(min_length=1, max_length=5)
    phone: str = Field(default="", max_length=30)
    guests: int = Field(default=1, ge=1, le=100)
    note: str = Field(default="", max_length=300)


class DiningOrderCreate(BaseModel):
    items: list[DiningItemInput] = Field(min_length=1, max_length=100)
    customer_name: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=300)


class DiningItemsAdd(BaseModel):
    items: list[DiningItemInput] = Field(min_length=1, max_length=100)


class DiningKitchenUpdate(BaseModel):
    status: str = Field(pattern="^(preparing|done)$")


class DiningPaymentCreate(BaseModel):
    pay_type: str = Field(pattern="^(naqd|karta|qarz)$")
    debtor_id: int | None = Field(default=None, gt=0)


class DiningCashierLine(BaseModel):
    line_id: int = Field(gt=0)
    # 0 — qatorni o'chirish (v1656dagi kabi).
    qty: Decimal = Field(ge=0, le=999)


class DiningCashierItemsUpdate(BaseModel):
    items: list[DiningCashierLine] = Field(min_length=1, max_length=200)


class DiningCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class DiningProblemOpen(BaseModel):
    reason: str = Field(default="Boshqa", max_length=80)
    note: str = Field(default="", max_length=300)


class DiningOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int | None
    name: str
    qty: float
    unit: str
    price: int
    total: int


class DiningOrderRead(BaseModel):
    id: int
    place_id: int
    place_name: str
    kind: str
    customer_name: str
    phone: str
    booking_date: str
    booking_time: str
    guests: int
    note: str
    total: int
    waiter_staff_id: int | None
    waiter_name: str
    problem_open: bool
    problem_reason: str
    problem_note: str
    problem_opened_at: int
    kitchen_status: str
    payment_status: str
    pay_type: str
    debtor_id: int | None
    receipt_no: int | None
    status: str
    created_at: int
    updated_at: int
    items: list[DiningOrderItemRead]


class DiningPlaceRead(BaseModel):
    id: int
    kind: str
    name: str
    seats: int
    x: float
    y: float
    locked: bool
    # v1656 zal rejasi stol band yoki bo'shligini shu maydondan biladi.
    active_order_id: int | None
    occupied: bool
    created_at: int
    updated_at: int


class DiningPaymentResult(BaseModel):
    ok: bool = True
    pay_type: str
    receipt_no: int | None
    already_confirmed: bool = False
