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
