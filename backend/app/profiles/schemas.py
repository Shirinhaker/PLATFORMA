from math import isfinite
import re
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.accounts.model import AccountType


USERNAME = re.compile(r"^[a-z0-9_]{3,32}$")
USERNAME_MESSAGE = (
    "Username 3–32 ta lotin harfi, raqam yoki _ dan iborat bo‘lsin."
)


def normalize_username(value: str) -> str:
    normalized = value.strip().lower().lstrip("@")
    if normalized and not USERNAME.fullmatch(normalized):
        raise ValueError(USERNAME_MESSAGE)
    return normalized


def normalize_finite_float(value: Any, default: float | None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if isfinite(parsed) else default


def normalize_json_value(value: Any) -> Any:
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, dict):
        return {
            str(key): normalize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_json_value(item) for item in value]
    return value


def normalize_json_object(value: Any) -> dict[str, Any]:
    normalized = normalize_json_value(value)
    return normalized if isinstance(normalized, dict) else {}


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def reject_explicit_null(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} null bo‘lishi mumkin emas.")
        return self


class CabinetActivity(BaseModel):
    id: int
    kind: str
    title: str
    status: str
    amount: int = 0
    created_at: int = 0


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: int
    name: str
    phone: str
    public_username: str
    region: str
    district: str
    mahalla: str
    latitude: float | None
    longitude: float | None
    location_exact: bool
    avatar_object_key: str
    avatar_x: float
    avatar_y: float
    avatar_zoom: float
    followers_count: int = 0
    following_count: int = 0
    has_business: bool = False
    dashboard_snapshot: dict[str, Any] = Field(default_factory=dict)
    recent_activity: list[CabinetActivity] = Field(default_factory=list)
    specialist_profile: dict[str, Any] = Field(default_factory=dict)
    cabinet_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def normalize_coordinates(cls, value):
        return normalize_finite_float(value, None)

    @field_validator("avatar_x", "avatar_y", mode="before")
    @classmethod
    def normalize_avatar_position(cls, value):
        return normalize_finite_float(value, 50.0)

    @field_validator("avatar_zoom", mode="before")
    @classmethod
    def normalize_avatar_zoom(cls, value):
        return normalize_finite_float(value, 1.0)

    @field_validator("followers_count", "following_count", mode="before")
    @classmethod
    def normalize_counts(cls, value):
        return 0 if value is None else value

    @field_validator("has_business", mode="before")
    @classmethod
    def normalize_has_business(cls, value):
        return False if value is None else value

    @field_validator(
        "dashboard_snapshot",
        "specialist_profile",
        "cabinet_payload",
        mode="before",
    )
    @classmethod
    def normalize_objects(cls, value):
        return normalize_json_object(value)

    @field_validator("recent_activity", mode="before")
    @classmethod
    def normalize_activity(cls, value):
        return [] if value is None else value


class UserProfilePatch(ProfilePatch):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    public_username: str | None = Field(default=None, max_length=32)
    region: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    mahalla: str | None = Field(default=None, max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_exact: bool | None = None
    specialist_profile: dict[str, Any] | None = None

    @field_validator("public_username", mode="before")
    @classmethod
    def validate_public_username(cls, value):
        return normalize_username(value) if isinstance(value, str) else value


class BusinessProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: int
    name: str
    phone: str
    description: str
    public_username: str
    direction: str
    activity_type: str
    address: str
    latitude: float | None
    longitude: float | None
    work_hours: dict[str, Any]
    pay_card: str
    pay_holder: str
    pay_qr_object_key: str
    director: str
    tax_id: str
    logo_object_key: str
    logo_x: float
    logo_y: float
    logo_zoom: float
    followers_count: int = 0
    following_count: int = 0
    rating_sum: int = 0
    rating_count: int = 0
    map_visible: bool = False
    dashboard_snapshot: dict[str, Any] = Field(default_factory=dict)
    recent_activity: list[CabinetActivity] = Field(default_factory=list)
    cabinet_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def normalize_coordinates(cls, value):
        return normalize_finite_float(value, None)

    @field_validator("logo_x", "logo_y", mode="before")
    @classmethod
    def normalize_logo_position(cls, value):
        return normalize_finite_float(value, 50.0)

    @field_validator("logo_zoom", mode="before")
    @classmethod
    def normalize_logo_zoom(cls, value):
        return normalize_finite_float(value, 1.0)

    @field_validator(
        "followers_count",
        "following_count",
        "rating_sum",
        "rating_count",
        mode="before",
    )
    @classmethod
    def normalize_counts(cls, value):
        return 0 if value is None else value

    @field_validator("map_visible", mode="before")
    @classmethod
    def normalize_map_visible(cls, value):
        return False if value is None else value

    @field_validator(
        "work_hours",
        "dashboard_snapshot",
        "cabinet_payload",
        mode="before",
    )
    @classmethod
    def normalize_objects(cls, value):
        return normalize_json_object(value)

    @field_validator("recent_activity", mode="before")
    @classmethod
    def normalize_activity(cls, value):
        return [] if value is None else value


class BusinessProfilePatch(ProfilePatch):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=2000)
    public_username: str | None = Field(default=None, max_length=32)
    direction: str | None = Field(default=None, max_length=120)
    activity_type: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    work_hours: dict[str, Any] | None = None
    pay_card: str | None = Field(default=None, max_length=64)
    pay_holder: str | None = Field(default=None, max_length=160)
    director: str | None = Field(default=None, max_length=160)
    tax_id: str | None = Field(default=None, max_length=32)
    map_visible: bool | None = None

    @field_validator("public_username", mode="before")
    @classmethod
    def validate_public_username(cls, value):
        return normalize_username(value) if isinstance(value, str) else value


class MeRead(BaseModel):
    account_id: int
    account_type: AccountType
    name: str
    profile_complete: bool


class ProfileImageAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_key: str = Field(min_length=1, max_length=1024)
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    zoom: float = Field(ge=1, le=5)


class CabinetSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: AccountType


class CabinetSwitchRead(BaseModel):
    account_id: int
    account_type: AccountType
    login: str
    csrf_token: str
    expires_at: str
