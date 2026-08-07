from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


PublicAdvertisementId = Annotated[
    str,
    Field(pattern=r"^a_[0-9a-f]{16}$"),
]


class PublicAdvertisement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    caption: str = Field(default="", max_length=2000)
    owner_public_id: str = Field(default="", max_length=64)
    owner_kind: str | None = Field(
        default=None,
        pattern="^(user|business)$",
    )
    desktop_image_url: str = Field(default="", max_length=2048)
    mobile_image_url: str = Field(default="", max_length=2048)
    crop_x: float = Field(default=50.0, ge=0, le=100)
    crop_y: float = Field(default=50.0, ge=0, le=100)
    crop_zoom: float = Field(default=1.0, gt=0)


class PublicAdvertisementViews(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[PublicAdvertisementId] = Field(min_length=1, max_length=5)


# --- Reklama joylash (K14) ---


class AdvertisementTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = Field(pattern="^(district|region|republic)$")
    region: str = Field(default="", max_length=120)
    district: str = Field(default="", max_length=120)


class AdvertisementQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[AdvertisementTarget] = Field(min_length=1, max_length=30)
    duration_days: int = Field(ge=1, le=30)
    daily_all_day: bool = True
    daily_start: str = Field(default="00:00", max_length=5)
    daily_end: str = Field(default="00:00", max_length=5)


class AdvertisementQuote(BaseModel):
    district_count: int
    hours_per_day: int
    duration_days: int
    district_hour_rate: int
    billable_district_hours: int
    total: int
    currency: str = "UZS"


class AdvertisementRates(BaseModel):
    price_code: str
    district_hour_rate: int
    duration_days: list[int]
    currency: str = "UZS"
    note: str


class AdvertisementCreate(AdvertisementQuoteRequest):
    title: str = Field(min_length=1, max_length=200)
    caption: str = Field(default="", max_length=2000)
    desktop_image_object_key: str = Field(default="", max_length=1024)
    mobile_image_object_key: str = Field(default="", max_length=1024)
    crop_x: float = Field(default=50.0, ge=0, le=100)
    crop_y: float = Field(default=50.0, ge=0, le=100)
    crop_zoom: float = Field(default=1.0, gt=0, le=10)
    # v1656: boshlanish sanasi mijoz tanlaydi, tasdiqlangach suriladi.
    start_date: str = Field(min_length=10, max_length=10)
    placement: str = Field(default="home", max_length=40)


class AdvertisementRead(BaseModel):
    id: int
    title: str
    caption: str
    targets: list[AdvertisementTarget]
    placement: str
    status: str
    daily_all_day: bool
    daily_start: str
    daily_end: str
    duration_days: int
    district_count: int
    hours_per_day: int
    district_hour_rate: int
    billable_district_hours: int
    price: int
    price_code: str
    start_at: int
    end_at: int
    views: int
    clicks: int
    desktop_image_url: str = ""
    mobile_image_url: str = ""
    created_at: int
