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


class PublicResultType(str, Enum):
    ALL = "all"
    USER = "user"
    BUSINESS = "business"


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


class PublicSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PublicResultKind
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    public_username: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=2000)
    direction: str = Field(default="", max_length=120)
    activity_type: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=120)
    district: str = Field(default="", max_length=120)
    mahalla: str = Field(default="", max_length=160)
    image_url: str = Field(default="", max_length=2048)


class PublicSearchResponse(BaseModel):
    items: list[PublicSearchItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total: int = Field(ge=0)

    @computed_field
    @property
    def pages(self) -> int:
        return ceil(self.total / self.page_size) if self.total else 0
