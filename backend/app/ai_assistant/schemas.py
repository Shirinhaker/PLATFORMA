from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(max_length=1000)


class AIChatMessageRead(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


class AIChatHistoryRead(BaseModel):
    history: list[AIChatMessageRead]


class AIChatAnswerRead(BaseModel):
    ok: bool = True
    answer: str
    source: Literal["openai", "local"]


class AIStatusRead(BaseModel):
    ok: bool = True
    build: str
    business_id: int
    openai_enabled: bool
    local_fallback: bool = True


class AIDocumentDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(max_length=4000)
    direction: str = Field(default="", max_length=16)
    doc_type: str = Field(default="", max_length=60)
    title: str = Field(default="", max_length=200)
    number: str = Field(default="", max_length=40)
    doc_date: str = Field(default="", max_length=20)
    contractor_id: int | None = Field(default=None, gt=0)
    firm_name: str = Field(default="", max_length=120)
    director: str = Field(default="", max_length=160)
    inn: str = Field(default="", max_length=32)


class AIDocumentDraftRead(BaseModel):
    ok: bool = True
    source: Literal["openai", "local"]
    direction: str
    doc_type: str
    title: str
    number: str
    doc_date: str
    body: str
    note: str = "Bu AI draft. Saqlashdan oldin tekshiring."
