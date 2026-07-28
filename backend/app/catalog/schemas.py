from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)


class PublicCatalogParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["product", "service"] | None = None
    q: str = Field(default="", max_length=120)
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
    def normalize_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @computed_field
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PublicCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["product", "service"]
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    price_text: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=2000)
    owner_state: Literal["linked", "unlinked"]
    owner_public_id: str = Field(default="", max_length=64)
    owner_name: str = Field(default="", max_length=160)
    owner_label: str = Field(default="", max_length=200)
    direction: str = Field(default="", max_length=120)
    activity_type: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=120)
    district: str = Field(default="", max_length=300)
    mahalla: str = Field(default="", max_length=160)
    image_url: str = Field(default="", max_length=2048)
    can_order: bool
    can_chat: bool


class PublicCatalogResponse(BaseModel):
    items: list[PublicCatalogItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total: int = Field(ge=0)

    @computed_field
    @property
    def pages(self) -> int:
        if not self.total:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

