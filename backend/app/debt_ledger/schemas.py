from __future__ import annotations

from datetime import date as DateValue, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DebtorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    phone: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=200)
    due: str = Field(default="", max_length=40)
    initial_debt: int = Field(default=0, ge=0, le=10**15)

    @field_validator("name", "phone", "note", "due", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class DebtTransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["debt", "payment"]
    amount: int = Field(gt=0, le=10**15)
    date: DateValue | None = None
    note: str = Field(default="", max_length=200)

    @field_validator("note", mode="before")
    @classmethod
    def clean_note(cls, value):
        return value.strip() if isinstance(value, str) else value


class DebtorCreated(BaseModel):
    id: int


class DebtTransactionRead(BaseModel):
    id: int
    type: Literal["debt", "payment"]
    amount: int
    date: DateValue
    note: str
    order_id: int | None
    cash_receipt_id: int | None
    created_at: datetime


class DebtorRead(BaseModel):
    id: int
    name: str
    phone: str
    note: str
    due: str
    balance: int


class DebtorDetailRead(DebtorRead):
    tx: list[DebtTransactionRead]


class DebtMutationRead(BaseModel):
    ok: bool = True
    transaction_id: int
    balance: int
