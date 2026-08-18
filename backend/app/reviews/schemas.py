from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReviewTargetKind(StrEnum):
    BUSINESS = "business"
    SPECIALIST = "specialist"


PUBLIC_ID_PATTERN = r"^[ub]_[0-9a-f]{16}$"


class ReviewWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_kind: ReviewTargetKind
    target_public_id: str = Field(pattern=PUBLIC_ID_PATTERN)
    stars: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)

    @field_validator("comment", mode="before")
    @classmethod
    def clean_comment(cls, value):
        return value.strip()[:1000] if isinstance(value, str) else value

    @model_validator(mode="after")
    def public_id_matches_target(self):
        prefix = "b_" if self.target_kind is ReviewTargetKind.BUSINESS else "u_"
        if not self.target_public_id.startswith(prefix):
            raise ValueError("review_target_public_id_kind_mismatch")
        return self


class ReviewReplyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(min_length=1, max_length=1500)

    @field_validator("reply", mode="before")
    @classmethod
    def clean_reply(cls, value):
        return value.strip()[:1500] if isinstance(value, str) else value


class ReviewRead(BaseModel):
    id: int
    stars: int = Field(ge=1, le=5)
    comment: str
    user_name: str
    created_at: datetime
    owner_reply: str
    owner_replied_at: datetime | None


class MyReviewRead(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str


class ReviewListRead(BaseModel):
    reviews: list[ReviewRead]
    avg: float = Field(ge=0, le=5)
    count: int = Field(ge=0)
    can_review: bool = False
    my_review: MyReviewRead | None = None


class ReviewMutationRead(BaseModel):
    ok: bool = True
    avg: float = Field(ge=0, le=5)
    count: int = Field(ge=0)
