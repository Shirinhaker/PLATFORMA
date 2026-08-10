from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FollowToggle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["user", "business"]
    public_id: str = Field(pattern=r"^[ub]_[0-9a-f]{16}$")


class FollowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    following: bool
    followers: int = Field(ge=0)


class FollowProfileRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["user", "business"]
    public_id: str = Field(pattern=r"^[ub]_[0-9a-f]{16}$")
    name: str = Field(min_length=1, max_length=120)
    info: str = Field(default="", max_length=160)
    image_url: str = Field(default="", max_length=2048)
    crop_x: float = Field(default=50, ge=0, le=100)
    crop_y: float = Field(default=50, ge=0, le=100)
    crop_zoom: float = Field(default=1, gt=0)
    followed_at: int = Field(ge=0)


class FollowListRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FollowProfileRead]
    count: int = Field(ge=0)
