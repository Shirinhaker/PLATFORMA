from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BusinessOnlineResourceRead(BaseModel):
    resource: str
    items: list[dict[str, Any]] = Field(default_factory=list)


class BusinessOnlineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: dict[str, Any]


class BusinessOnlinePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch: dict[str, Any]


class BusinessOnlineAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: int | str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class BusinessOnlineMutationRead(BaseModel):
    resource: str
    item: dict[str, Any] | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
