from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocumentDirection = Literal["ichki", "kiruvchi", "chiquvchi"]
DocumentResponseAction = Literal["qabul", "rad"]


class CounterpartyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    ctype: str = Field(default="", max_length=40)
    director: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=200)
    inn: str = Field(default="", max_length=20)
    account: str = Field(default="", max_length=40)
    bank: str = Field(default="", max_length=120)
    mfo: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=300)

    @field_validator(
        "name",
        "ctype",
        "director",
        "phone",
        "address",
        "inn",
        "account",
        "bank",
        "mfo",
        "note",
        mode="before",
    )
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class CounterpartyRead(CounterpartyWrite):
    id: int
    created_at: datetime


class CounterpartyListRead(BaseModel):
    counterparties: list[CounterpartyRead]
    count: int
    types: list[str]


class DocumentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: DocumentDirection = "ichki"
    doc_type: str = Field(default="", max_length=60)
    title: str = Field(default="", max_length=200)
    number: str = Field(default="", max_length=40)
    doc_date: str = Field(default="", max_length=20)
    contractor_id: int | None = Field(default=None, gt=0)
    body: str = Field(min_length=1)

    @field_validator("doc_type", "title", "number", "doc_date", mode="before")
    @classmethod
    def clean_short_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("body", mode="before")
    @classmethod
    def require_body(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Hujjat matni bo'sh.")
        return value.strip()


class DocumentRead(BaseModel):
    id: int
    direction: DocumentDirection
    doc_type: str
    title: str
    number: str
    doc_date: str
    contractor_id: int | None
    contractor_name: str
    body: str
    sender_name: str
    receiver_inn: str
    status: str
    created_at: datetime


class DocumentListRead(BaseModel):
    documents: list[DocumentRead]
    count: int


class CreatedRead(BaseModel):
    ok: bool = True
    id: int


class MutationRead(BaseModel):
    ok: bool = True


class DocumentSend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receiver_inn: str = Field(min_length=1, max_length=40)

    @field_validator("receiver_inn", mode="before")
    @classmethod
    def clean_inn(cls, value):
        return value.strip() if isinstance(value, str) else value


class DocumentSentRead(BaseModel):
    ok: bool = True
    receiver_name: str


class DocumentRespond(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DocumentResponseAction


class DocumentRespondedRead(BaseModel):
    ok: bool = True
    status: str
