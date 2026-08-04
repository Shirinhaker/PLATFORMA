from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExpenseCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(default="Boshqa", min_length=1, max_length=40)
    amount: int = Field(gt=0, le=10**15)
    note: str = Field(default="", max_length=200)

    @field_validator("category", "note", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class ExpenseCategoryList(BaseModel):
    categories: list[str]
    defaults: list[str]


class ExpenseCategoryCreated(BaseModel):
    ok: bool = True
    exists: bool


class ExpenseCreated(BaseModel):
    id: int


class ExpenseRead(BaseModel):
    id: int
    category: str
    amount: int
    note: str
    source: str
    who: str
    created_at: datetime


class ExpenseDayRead(BaseModel):
    day: date
    expenses: list[ExpenseRead]
    total: int
    by_category: dict[str, int]
