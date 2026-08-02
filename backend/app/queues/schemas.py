from datetime import date, datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _clean_time(value: object, *, allow_empty: bool) -> str:
    if not isinstance(value, str):
        return value
    cleaned = value.strip()
    if allow_empty and not cleaned:
        return ""
    if not TIME_PATTERN.fullmatch(cleaned):
        raise ValueError("Vaqt HH:MM ko'rinishida bo'lishi kerak.")
    return cleaned


class QueueProviderWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: int = Field(gt=0)
    item_public_ids: list[str] = Field(min_length=1, max_length=100)
    specialty: str = Field(default="", max_length=100)
    experience_years: int = Field(default=0, ge=0, le=100)
    qualification: str = Field(default="", max_length=100)
    work_days: str = Field(default="1,2,3,4,5,6", max_length=30)
    work_start: str = "08:00"
    work_end: str = "17:00"
    avg_minutes: int = Field(default=20, ge=5, le=240)
    room: str = Field(default="", max_length=50)
    bio: str = Field(default="", max_length=500)
    status: Literal["active", "inactive"] = "active"
    mode: Literal["live", "slot"] = "live"

    @field_validator("item_public_ids")
    @classmethod
    def unique_items(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            identifier = str(item or "").strip()[:64]
            if identifier and identifier not in cleaned:
                cleaned.append(identifier)
        if not cleaned:
            raise ValueError("Navbat yoqilgan xizmatni tanlang.")
        return cleaned

    @field_validator("work_days")
    @classmethod
    def valid_work_days(cls, value: str) -> str:
        days = [part.strip() for part in str(value or "").split(",") if part.strip()]
        if not days or any(day not in {"1", "2", "3", "4", "5", "6", "7"} for day in days):
            raise ValueError("Ish kunlari noto'g'ri.")
        return ",".join(dict.fromkeys(days))

    @field_validator("work_start", "work_end", mode="before")
    @classmethod
    def valid_work_time(cls, value):
        return _clean_time(value, allow_empty=False)

    @field_validator("specialty", "qualification", "room", "bio", mode="before")
    @classmethod
    def clean_text(cls, value, info: ValidationInfo):
        if not isinstance(value, str):
            return value
        limits = {"specialty": 100, "qualification": 100, "room": 50, "bio": 500}
        return value.strip()[: limits[info.field_name]]


class QueueProviderRead(BaseModel):
    id: int
    staff_id: int
    name: str
    profession: str
    specialty: str
    experience_years: int
    qualification: str
    work_days: str
    work_start: str
    work_end: str
    avg_minutes: int
    room: str
    bio: str
    status: str
    mode: str
    item_public_ids: list[str]
    queue_count: int = 0


class QueueStaffRead(BaseModel):
    id: int
    name: str
    profession: str


class QueueServiceRead(BaseModel):
    public_id: str
    name: str
    price_text: str


class QueueBusinessSetupRead(BaseModel):
    services: list[QueueServiceRead]
    staff: list[QueueStaffRead]


class QueueOptionsRead(BaseModel):
    business_public_id: str
    item_public_id: str
    queue_date: date
    providers: list[QueueProviderRead]


class QueueSlotsRead(BaseModel):
    mode: Literal["live", "slot"]
    slots: list[str]


class QueueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_public_id: str = Field(min_length=1, max_length=64)
    item_public_id: str = Field(min_length=1, max_length=64)
    provider_id: int = Field(gt=0)
    queue_date: date
    slot_time: str = Field(default="", max_length=5)
    note: str = Field(default="", max_length=200)

    @field_validator("slot_time", mode="before")
    @classmethod
    def valid_slot(cls, value):
        return _clean_time(value, allow_empty=True)

    @field_validator("note", mode="before")
    @classmethod
    def clean_note(cls, value):
        return value.strip()[:200] if isinstance(value, str) else value


class QueueOfflineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_public_id: str = Field(min_length=1, max_length=64)
    provider_id: int = Field(gt=0)
    queue_date: date
    patient_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(default="", max_length=32)
    note: str = Field(default="", max_length=200)
    slot_time: str = Field(default="", max_length=5)

    @field_validator("patient_name", "phone", "note", mode="before")
    @classmethod
    def clean_text(cls, value, info: ValidationInfo):
        if not isinstance(value, str):
            return value
        limits = {"patient_name": 120, "phone": 32, "note": 200}
        return value.strip()[: limits[info.field_name]]

    @field_validator("slot_time", mode="before")
    @classmethod
    def valid_slot(cls, value):
        return _clean_time(value, allow_empty=True)


class QueueStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal[
        "waiting",
        "called",
        "in_service",
        "done",
        "no_show",
        "cancelled",
        "skipped",
    ]


class QueueSwap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    other_queue_id: int = Field(gt=0)


class QueueEntryRead(BaseModel):
    id: int
    business_account_id: int
    business_name: str = ""
    business_direction: str = ""
    customer_account_id: int | None
    item_public_id: str
    provider_id: int
    patient_name: str
    phone: str
    service_name: str
    provider_name: str
    queue_date: date
    queue_no: int
    queue_code: str
    source: str
    status: str
    note: str
    slot_time: str
    ahead_count: int = 0
    avg_minutes: int = 0
    wait_minutes: int = 0
    created_at: datetime
    updated_at: datetime


class QueueNotificationRead(BaseModel):
    id: int
    medical_queue_id: int
    is_read: bool
