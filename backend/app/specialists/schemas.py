from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.schemas import CreatedRead, MutationRead  # noqa: F401


class SpecialistProfileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profession: str = Field(default="", max_length=180)
    description: str = Field(default="", max_length=3000)
    visible: bool = False
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("profession", "description", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_location_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Joylashuv kenglik va uzunlik bilan birga yuborilsin.")
        return self


class SpecialistCredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_key: str = Field(min_length=1, max_length=600)


class SpecialistOfferWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["service", "product"] = "service"
    name: str = Field(min_length=1, max_length=160)
    price_text: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=1000)
    image_object_key: str = Field(default="", max_length=600)
    clear_image: bool = False

    @field_validator("name", "price_text", "note", "image_object_key", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class SpecialistPortfolioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_type: Literal["photo", "video"]
    object_key: str = Field(min_length=1, max_length=600)


class SpecialistCredentialRead(BaseModel):
    id: int
    image_url: str
    position: int
    created_at: datetime


class SpecialistOfferRead(BaseModel):
    id: int
    kind: Literal["service", "product"]
    name: str
    price_text: str
    note: str
    image_url: str
    image_object_key: str
    created_at: datetime


class SpecialistPortfolioRead(BaseModel):
    id: int
    media_type: Literal["photo", "video"]
    media_url: str
    created_at: datetime


class SpecialistRead(BaseModel):
    exists: bool
    profession: str
    description: str
    visible: bool
    latitude: float | None
    longitude: float | None
    review_count: int = Field(default=0, ge=0)
    credentials: list[SpecialistCredentialRead]
    offers: list[SpecialistOfferRead]
    portfolio: list[SpecialistPortfolioRead]
