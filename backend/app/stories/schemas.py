from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.accounts.model import AccountType


StoryState = Literal["active", "archived"]


class StoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_key: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1, le=100 * 1024 * 1024)
    caption: str = Field(default="", max_length=200)


class StoryRead(BaseModel):
    id: int
    owner_type: AccountType
    owner_public_id: str
    media_type: Literal["image", "video"]
    media_url: str
    thumbnail_url: str
    caption: str
    duration_seconds: float
    created_at: datetime
    expires_at: datetime
    viewed: bool = False
    state: StoryState | None = None

    @model_validator(mode="after")
    def set_lifecycle_state(self) -> "StoryRead":
        if self.state is None:
            now = datetime.now(UTC)
            expires = self.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            self.state = "active" if expires > now else "archived"
        return self


class ManagedStoryRead(StoryRead):
    view_count: int = 0


class StoryGroup(BaseModel):
    owner_type: AccountType
    owner_public_id: str
    name: str
    avatar_url: str
    is_own: bool
    is_followed: bool
    has_unseen: bool
    distance_km: float | None
    stories: list[StoryRead]


class StoryViewerRead(BaseModel):
    account_public_id: str
    name: str
    viewed_at: datetime


class StoryViewResult(BaseModel):
    ok: Literal[True] = True
    counted: bool


class StoryReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=300)


class StoryCreated(BaseModel):
    ok: Literal[True] = True
    story: StoryRead


class StoryOk(BaseModel):
    ok: Literal[True] = True
