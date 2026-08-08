from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ListingCategory = Literal["uy", "ish", "moshina", "hayvon", "texnika", "boshqa"]
ListingVisibility = Literal["all", "own"]
# `payment_pending` — to'lov tasdiqlanmaguncha e'lon ko'rinmaydi.
ListingStatus = Literal["active", "inactive", "payment_pending"]
ListingMediaType = Literal["photo", "video"]


class ListingMediaAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ListingMediaType
    object_key: str = Field(min_length=1, max_length=1024)


class ListingMediaRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ListingMediaType
    url: str = Field(default="", max_length=4096)


class ListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cat: ListingCategory
    title: str = Field(min_length=1, max_length=200)
    price: str = Field(default="", max_length=120)
    descr: str = Field(default="", max_length=4000)
    address: str = Field(default="", max_length=300)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    visibility: ListingVisibility = "all"
    media: list[ListingMediaAttachment] = Field(default_factory=list, max_length=10)

    @field_validator("title", "price", "descr", "address", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class ListingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cat: ListingCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    price: str | None = Field(default=None, max_length=120)
    descr: str | None = Field(default=None, max_length=4000)
    address: str | None = Field(default=None, max_length=300)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    visibility: ListingVisibility | None = None
    status: ListingStatus | None = None
    media: list[ListingMediaAttachment] | None = Field(default=None, max_length=10)

    @field_validator("title", "price", "descr", "address", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_patch(self):
        if not self.model_fields_set:
            raise ValueError("O‘zgartirish ma’lumotlari bo‘sh.")
        return self


class ListingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_id: str = Field(pattern=r"^l_[0-9a-f]{16}$")
    cat: ListingCategory
    title: str
    price: str = ""
    descr: str = ""
    address: str = ""
    lat: float | None = None
    lng: float | None = None
    visibility: ListingVisibility
    status: ListingStatus
    created_at: datetime
    media: list[ListingMediaRead] = Field(default_factory=list)
    owner_kind: Literal["user", "business"]
    owner_public_id: str
    owner_name: str = ""
    is_saved: bool = False


class ListingSaveRead(BaseModel):
    saved: bool
