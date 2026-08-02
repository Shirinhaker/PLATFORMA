from enum import Enum
from math import ceil

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)


class PublicResultKind(str, Enum):
    USER = "user"
    BUSINESS = "business"
    PRODUCT = "product"
    SERVICE = "service"
    LISTING = "listing"


class PublicResultType(str, Enum):
    ALL = "all"
    USER = "user"
    BUSINESS = "business"
    PRODUCT = "product"
    SERVICE = "service"
    LISTING = "listing"


class PublicSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(default="", max_length=120)
    result_type: PublicResultType = PublicResultType.ALL
    direction: str = Field(default="", max_length=120)
    activity_type: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=120)
    district: str = Field(default="", max_length=120)
    mahalla: str = Field(default="", max_length=160)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)

    @field_validator(
        "q",
        "direction",
        "activity_type",
        "region",
        "district",
        "mahalla",
        mode="before",
    )
    @classmethod
    def normalize_text_filter(cls, value):
        return value.strip() if isinstance(value, str) else value

    @computed_field
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PublicSearchMapPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_public_id: str = Field(min_length=1, max_length=64)
    business_name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PublicSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PublicResultKind
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    public_username: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=2000)
    direction: str = Field(default="", max_length=120)
    activity_type: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=120)
    district: str = Field(default="", max_length=120)
    mahalla: str = Field(default="", max_length=160)
    image_url: str = Field(default="", max_length=2048)
    price_text: str | None = Field(default=None, max_length=120)
    owner_state: str | None = Field(default=None, pattern="^(linked|unlinked)$")
    owner_label: str | None = Field(default=None, max_length=200)
    can_order: bool | None = None
    can_chat: bool | None = None
    map_point: PublicSearchMapPoint | None = None


class PublicSearchResponse(BaseModel):
    items: list[PublicSearchItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total: int = Field(ge=0)

    @computed_field
    @property
    def pages(self) -> int:
        return ceil(self.total / self.page_size) if self.total else 0


class PublicHomeBusinessPin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    yon: str = Field(default="", max_length=120)
    tur: str = Field(default="", max_length=120)
    lat: float
    lng: float
    logo_file: str = Field(default="", max_length=2048)
    logo_x: float = Field(default=50, ge=0, le=100)
    logo_y: float = Field(default=50, ge=0, le=100)
    logo_zoom: float = Field(default=1, gt=0)
    address: str = Field(default="", max_length=300)
    source: str = Field(default="public", max_length=40)


class PublicHomeSpecialistPin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    kasb: str = Field(default="Mutaxasis", max_length=160)
    is_gov: bool = False
    lat: float
    lng: float
    avatar_file: str = Field(default="", max_length=2048)
    avatar_x: float = Field(default=50, ge=0, le=100)
    avatar_y: float = Field(default=50, ge=0, le=100)
    avatar_zoom: float = Field(default=1, gt=0)
    source: str = Field(default="public", max_length=40)


class PublicHomeMapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    businesses: list[PublicHomeBusinessPin]
    specialists: list[PublicHomeSpecialistPin]


class PublicDistrictOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern="^(product|service|listing)$")
    business_id: int = 0
    business_public_id: str = Field(default="", max_length=64)
    content_id: int
    content_public_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    business_name: str = Field(default="", max_length=160)
    image: str = Field(default="", max_length=2048)
    business_logo: str = Field(default="", max_length=2048)
    price: str = Field(default="", max_length=120)
    unit: str = Field(default="", max_length=40)


class PublicDistrictOffersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    needs_district: bool
    items: list[PublicDistrictOffer]
    slot: int | None = None


class PublicFollowedProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern="^(user|business)$")
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    image_url: str = Field(default="", max_length=2048)
    crop_x: float = Field(default=50, ge=0, le=100)
    crop_y: float = Field(default=50, ge=0, le=100)
    crop_zoom: float = Field(default=1, gt=0)


class PublicProfileItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern="^(product|service)$")
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    price_text: str = Field(default="", max_length=120)
    unit: str = Field(default="dona", max_length=40)
    note: str = Field(default="", max_length=2000)
    image_url: str = Field(default="", max_length=2048)
    group_name: str = Field(default="", max_length=160)
    queue_enabled: bool = False
    queue_provider_count: int = Field(default=0, ge=0)


class PublicProfileListing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    price_text: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=4000)
    address: str = Field(default="", max_length=300)
    image_url: str = Field(default="", max_length=2048)


class PublicSpecialistSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profession: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=2000)


class PublicProfileDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern="^(user|business)$")
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    public_username: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=2000)
    direction: str = Field(default="", max_length=120)
    activity_type: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=32)
    image_url: str = Field(default="", max_length=2048)
    crop_x: float = Field(default=50, ge=0, le=100)
    crop_y: float = Field(default=50, ge=0, le=100)
    crop_zoom: float = Field(default=1, gt=0)
    followers_count: int = Field(default=0, ge=0)
    specialist: PublicSpecialistSummary | None = None
    items: list[PublicProfileItem] = Field(default_factory=list)
    listings: list[PublicProfileListing] = Field(default_factory=list)
