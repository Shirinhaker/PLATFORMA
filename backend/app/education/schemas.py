from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourseEnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_item_public_id: str = Field(min_length=1, max_length=64)
    phone: str = Field(default="", max_length=30)
    note: str = Field(default="", max_length=300)

    @field_validator("course_item_public_id", "phone", "note", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class CourseEnrollmentCreated(BaseModel):
    ok: bool = True
    id: int = Field(gt=0)


EducationStatisticsPeriod = Literal["day", "month", "year"]


class EducationStatisticsPeriodRead(BaseModel):
    type: EducationStatisticsPeriod
    date: str
    start: str
    end: str


class EducationStatisticsProcessRead(BaseModel):
    active_students: int = 0
    active_groups: int = 0
    new_enrollments: int = 0
    attendance_percent: int = 0


class EducationStatisticsFinanceRead(BaseModel):
    calculated: int = 0
    paid: int = 0
    debt: int = 0


class EducationStatisticsResultRead(BaseModel):
    other_expenses: int = 0
    cash_flow: int = 0
    accrual_result: int = 0


class EducationStatisticsGroupRead(BaseModel):
    id: int
    name: str
    active_students: int = 0
    attendance_percent: int = 0
    calculated: int = 0
    paid: int = 0
    debt: int = 0


class EducationStatisticsReportRead(BaseModel):
    period: EducationStatisticsPeriodRead
    education: EducationStatisticsProcessRead
    student_finance: EducationStatisticsFinanceRead
    teacher_finance: EducationStatisticsFinanceRead
    result: EducationStatisticsResultRead
    groups: list[EducationStatisticsGroupRead]
