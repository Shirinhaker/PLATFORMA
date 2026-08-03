from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StaffMemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    profession: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=32)
    salary: int = Field(default=0, ge=0)
    hire_date: date | None = None
    note: str = Field(default="", max_length=500)


class StaffMemberPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    profession: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=32)
    salary: int | None = Field(default=None, ge=0)
    hire_date: date | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def reject_null_for_required_columns(self):
        for name in ("name", "profession", "phone", "salary", "note"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} null bo‘lishi mumkin emas.")
        return self


class StaffAccessWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_login: bool = False
    login: str = Field(default="", max_length=20)
    password: str = Field(default="", max_length=200)
    permissions: list[str] = Field(default_factory=list, max_length=64)


class StaffScheduleDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    on: bool = False
    start: str = Field(default="", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$|^$")
    end: str = Field(default="", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$|^$")


class StaffScheduleWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule: dict[str, StaffScheduleDay]

    @field_validator("schedule")
    @classmethod
    def validate_days(cls, value: dict[str, StaffScheduleDay]):
        if set(value) - {f"d{index}" for index in range(7)}:
            raise ValueError("Hafta kuni noto‘g‘ri.")
        return value


class StaffMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    profession: str
    phone: str
    salary: int
    hire_date: date | None
    status: Literal["active", "fired"]
    note: str
    login: str
    can_login: bool
    has_password: bool
    permissions: list[str]
    schedule: dict
    created_at: datetime
    fired_at: datetime | None


class StaffPermissionRead(BaseModel):
    key: str
    label: str
    icon: str


class StaffTemplateRead(BaseModel):
    key: str
    label: str
    permissions: list[str]


class StaffSetupRead(BaseModel):
    active: list[StaffMemberRead]
    fired: list[StaffMemberRead]
    active_count: int
    fired_count: int
    total_salary: int
    firm_login: str
    business_direction: str
    professions: list[str]
    permission_definitions: list[StaffPermissionRead]
    permission_templates: list[StaffTemplateRead]


class StaffProfessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)


class StaffProfessionsRead(BaseModel):
    professions: list[str]


class StaffAttendanceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    status: Literal["", "keldi", "kelmadi", "dam"]
    time_in: str = Field(default="", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$|^$")
    time_out: str = Field(default="", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$|^$")


class StaffAttendanceRow(BaseModel):
    id: int
    name: str
    profession: str
    status: str
    time_in: str
    time_out: str
    sched_on: bool
    sched_start: str
    sched_end: str
    month_present: int
    month_minutes: int


class StaffAttendanceRead(BaseModel):
    date: date
    weekday: int
    staff: list[StaffAttendanceRow]


class StaffLoginWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    firm_login: str = Field(min_length=1, max_length=80)
    login: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=200)
