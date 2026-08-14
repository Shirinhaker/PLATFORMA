from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.accounts.model import AccountType


PROFILE_PUBLIC_ID_PATTERN = r"^[ub]_[0-9a-f]{16}$"


class MessageTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_kind: AccountType
    target_public_id: str = Field(pattern=PROFILE_PUBLIC_ID_PATTERN)
    reply_to_id: int | None = Field(default=None, gt=0)


class MessageCreate(MessageTarget):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip()[:2000] if isinstance(value, str) else value


class MessageImageCreate(MessageTarget):
    object_key: str = Field(min_length=1, max_length=1024)
    file_name: str = Field(default="", max_length=255)
    text: str = Field(default="", max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip()[:1000] if isinstance(value, str) else value


class MessageEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip()[:2000] if isinstance(value, str) else value


class MessageReplyRead(BaseModel):
    id: int
    text: str
    media_type: str
    is_deleted: bool
    sender_name: str


class MessageRead(BaseModel):
    id: int
    text: str
    media_type: str
    media_url: str
    file_name: str
    reply_to_id: int | None
    reply: MessageReplyRead | None = None
    edited_at: datetime | None
    deleted_at: datetime | None
    is_deleted: bool
    mine: bool
    sender_name: str
    sender_kind: AccountType
    created_at: datetime


class MessageProfileRead(BaseModel):
    kind: AccountType
    public_id: str
    name: str
    avatar_url: str


class MessageThreadRead(BaseModel):
    other: MessageProfileRead
    messages: list[MessageRead]
    next_cursor: int | None = Field(default=None, gt=0)


class MessageConversationRead(BaseModel):
    target_kind: AccountType
    target_public_id: str
    name: str
    avatar_url: str
    last: str
    created_at: datetime
    unread: int = Field(ge=0)


class MessageUnreadRead(BaseModel):
    count: int = Field(ge=0)
