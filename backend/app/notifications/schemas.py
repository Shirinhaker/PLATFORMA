from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NotificationCategory = Literal[
    "uy", "ish", "moshina", "hayvon", "texnika", "boshqa"
]
PushPlatform = Literal["android", "ios", "web"]


class NotificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    body: str
    order_id: int | None = None
    listing_id: int | None = None
    listing_public_id: str = ""
    profile_kind: Literal["user", "business"] | None = None
    profile_public_id: str = ""
    dining_order_id: int | None = None
    medical_queue_id: int | None = None
    ride_id: int | None = None
    action_type: str = ""
    requires_action: bool = False
    is_read: bool = False
    created_at: int
    read_at: int | None = None
    resolved_at: int | None = None


class NotificationListRead(BaseModel):
    items: list[NotificationRead]
    unread: int = Field(ge=0)


class ActionNotificationListRead(BaseModel):
    items: list[NotificationRead]
    count: int = Field(ge=0)


class NotificationMutationRead(BaseModel):
    ok: bool = True
    read_at: int | None = None


class NotificationPreferenceRead(BaseModel):
    enabled: bool = True
    orders_enabled: bool = True


class NotificationPreferenceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    orders_enabled: bool = True


class NotificationFilterWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cat: NotificationCategory
    region: str = Field(default="", max_length=120)
    district: str = Field(default="", max_length=120)
    price_min: int = Field(default=0, ge=0)
    price_max: int = Field(default=0, ge=0)
    keyword: str = Field(default="", max_length=160)

    @field_validator("region", "district", "keyword", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def valid_price_range(self):
        if self.price_max and self.price_min > self.price_max:
            raise ValueError("notification_filter_price_range_invalid")
        return self


class NotificationFilterRead(NotificationFilterWrite):
    id: int
    created_at: int


class PushDeviceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=4096)
    platform: PushPlatform = "android"
    device_name: str = Field(default="", max_length=120)
    app_version: str = Field(default="", max_length=40)

    @field_validator("token", "device_name", "app_version", mode="before")
    @classmethod
    def clean_device_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class PushDeviceRemove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=4096)

    @field_validator("token", mode="before")
    @classmethod
    def clean_token(cls, value):
        return value.strip() if isinstance(value, str) else value


class PushDeviceRead(BaseModel):
    ok: bool = True
    device_id: int


class PushStatusRead(BaseModel):
    provider: Literal["firebase"] = "firebase"
    configured: bool
    active_devices: int = Field(ge=0)
    pending: int = Field(ge=0)
