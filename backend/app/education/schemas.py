from datetime import date, datetime
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


EducationAttendanceStatus = Literal["present", "late", "excused", "absent"]
EducationPayType = Literal["naqd", "karta"]
EducationSalaryType = Literal["monthly", "per_lesson"]


class EducationGroupRead(BaseModel):
    id: int
    course_item_id: int | None = None
    course_name: str = ""
    name: str
    teacher_id: int | None = None
    teacher_name: str = ""
    room_name: str = ""
    capacity: int = 0
    weekdays: str = ""
    lesson_from: str = ""
    lesson_to: str = ""
    start_date: str = ""
    end_date: str = ""
    billing_type: Literal["monthly", "attendance"] = "monthly"
    package_lessons: int = 0
    package_price: int = 0
    student_count: int = 0


class EducationGroupWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    course_item_id: int | None = None
    teacher_id: int | None = None
    teacher_name: str = Field(default="", max_length=160)
    room_name: str = Field(default="", max_length=80)
    capacity: int = Field(default=0, ge=0, le=10_000)
    weekdays: list[str] = Field(default_factory=list, max_length=7)
    lesson_from: str = Field(default="", max_length=5)
    lesson_to: str = Field(default="", max_length=5)
    start_date: str = Field(default="", max_length=10)
    end_date: str = Field(default="", max_length=10)
    billing_type: Literal["monthly", "attendance"] = "monthly"
    package_lessons: int = Field(default=0, ge=0, le=1000)
    package_price: int = Field(default=0, ge=0, le=10**12)

    @field_validator(
        "name", "teacher_name", "room_name", "lesson_from", "lesson_to",
        "start_date", "end_date", mode="before",
    )
    @classmethod
    def normalize_group_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class EducationCreated(BaseModel):
    ok: bool = True
    id: int = Field(gt=0)


class EducationUpdated(BaseModel):
    ok: bool = True


class EducationStudentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=120)
    group_id: int | None = None
    phone: str = Field(default="", max_length=40)
    parent_name: str = Field(default="", max_length=160)
    parent_phone: str = Field(default="", max_length=40)
    birth_date: str = Field(default="", max_length=10)
    joined_date: str = Field(default="", max_length=10)
    monthly_fee: int = Field(default=0, ge=0, le=10**12)
    payment_start_date: str = Field(default="", max_length=10)
    lesson_package_override: int = Field(default=0, ge=0, le=1000)
    note: str = Field(default="", max_length=2000)

    @field_validator(
        "full_name", "phone", "parent_name", "parent_phone", "birth_date",
        "joined_date", "payment_start_date", "note", mode="before",
    )
    @classmethod
    def normalize_student_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class EducationStudentRead(EducationStudentWrite):
    id: int
    group_name: str = ""
    course_name: str = ""


class EducationStudentAttendanceCounts(BaseModel):
    present: int = 0
    late: int = 0
    excused: int = 0
    absent: int = 0


class EducationStudentAttendanceSummary(BaseModel):
    total: int = 0
    attended: int = 0
    percent: int = 0
    counts: EducationStudentAttendanceCounts


class EducationStudentPaymentSummary(BaseModel):
    expected: int = 0
    paid: int = 0
    debt: int = 0
    total_paid: int = 0


class EducationStudentPaymentRead(BaseModel):
    id: int
    payment_month: str
    amount: int
    pay_type: EducationPayType
    note: str = ""
    voided_at: datetime | None = None
    void_reason: str = ""
    created_at: datetime


class EducationStudentGroupHistoryRead(BaseModel):
    id: int
    group_id: int
    group_name: str = ""
    started_date: str
    ended_date: str = ""
    note: str = ""


class EducationStudentCardRead(BaseModel):
    student: EducationStudentRead
    attendance: EducationStudentAttendanceSummary
    payment: EducationStudentPaymentSummary
    payments: list[EducationStudentPaymentRead]
    group_history: list[EducationStudentGroupHistoryRead]


class EducationStudentTransferWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: int = Field(gt=0)
    transfer_date: date
    note: str = Field(default="", max_length=300)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_transfer_note(cls, value):
        return value.strip() if isinstance(value, str) else value


class EducationStudentTransferred(BaseModel):
    ok: bool = True
    group_id: int
    group_name: str


class EducationAttendanceStudentRead(BaseModel):
    student_id: int
    full_name: str
    phone: str = ""
    attendance_status: str = ""
    attendance_note: str = ""


class EducationAttendanceRead(BaseModel):
    group: EducationGroupRead
    lesson_date: date
    students: list[EducationAttendanceStudentRead]


class EducationAttendanceEntryWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int
    status: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=300)

    @field_validator("status", "note", mode="before")
    @classmethod
    def normalize_entry_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class EducationAttendanceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: int = Field(gt=0)
    lesson_date: date
    entries: list[EducationAttendanceEntryWrite] = Field(max_length=10_000)


class EducationAttendanceSaved(BaseModel):
    ok: bool = True
    saved: int = 0


class EducationPaymentControlSummaryRead(BaseModel):
    overdue: int = 0
    due_today: int = 0
    upcoming: int = 0
    paid: int = 0
    total_debt: int = 0


class EducationPaymentControlStudentRead(BaseModel):
    id: int
    group_id: int | None = None
    full_name: str
    phone: str = ""
    parent_phone: str = ""
    group_name: str = ""
    billing_type: Literal["monthly", "attendance"] = "monthly"
    status: Literal["overdue", "due_today", "upcoming", "paid"]
    start_date: date
    next_due: str = ""
    expected: int = 0
    paid: int = 0
    debt: int = 0
    package_lessons: int = 0
    lessons_done: int = 0
    lessons_remaining: int = 0
    payable_now: int = 0
    payment_month: str


class EducationPaymentControlRead(BaseModel):
    today: date
    summary: EducationPaymentControlSummaryRead
    students: list[EducationPaymentControlStudentRead]


class EducationPaymentStudentRead(BaseModel):
    student_id: int
    full_name: str
    phone: str = ""
    monthly_fee: int = 0
    group_name: str = ""
    billing_type: Literal["monthly", "attendance"] = "monthly"
    package_lessons: int = 0
    package_price: int = 0
    chargeable_lessons: int = 0
    per_lesson_price: int = 0
    expected: int = 0
    paid: int = 0
    debt: int = 0


class EducationPaymentHistoryRead(BaseModel):
    id: int
    student_id: int | None = None
    full_name: str
    payment_month: str
    amount: int
    pay_type: EducationPayType
    note: str = ""
    voided_at: datetime | None = None
    void_reason: str = ""
    created_at: datetime


class EducationPaymentMonthRead(BaseModel):
    payment_month: str
    students: list[EducationPaymentStudentRead]
    history: list[EducationPaymentHistoryRead]


class EducationPaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int = Field(gt=0)
    payment_month: str = Field(min_length=7, max_length=7)
    amount: int = Field(gt=0, le=10**12)
    pay_type: EducationPayType = "naqd"
    note: str = Field(default="", max_length=200)

    @field_validator("payment_month", "note", mode="before")
    @classmethod
    def normalize_payment_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class EducationPaymentCreated(BaseModel):
    ok: bool = True
    id: int
    receipt_no: int


class EducationPaymentVoid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


class EducationPaymentVoided(BaseModel):
    ok: bool = True
    voided: bool = True


class EducationTeacherWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(default="", max_length=30)
    specialty: str = Field(default="", max_length=120)
    hired_date: str = Field(default="", max_length=10)
    salary_type: EducationSalaryType = "monthly"
    salary_amount: int = Field(default=0, ge=0, le=10**12)
    note: str = Field(default="", max_length=500)

    @field_validator(
        "full_name", "phone", "specialty", "hired_date", "note", mode="before"
    )
    @classmethod
    def normalize_teacher_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class EducationTeacherRead(EducationTeacherWrite):
    id: int
    group_count: int = 0


class EducationTeacherCreated(BaseModel):
    ok: bool = True
    id: int


class EducationTeacherUpdated(BaseModel):
    ok: bool = True


class EducationPayrollTeacherRead(BaseModel):
    id: int
    full_name: str
    salary_type: EducationSalaryType
    salary_amount: int
    lesson_count: int = 0
    expected: int = 0
    paid: int = 0
    debt: int = 0


class EducationPayrollHistoryRead(BaseModel):
    id: int
    teacher_id: int | None = None
    full_name: str
    payment_month: str
    amount: int
    pay_type: EducationPayType
    note: str = ""
    created_at: datetime


class EducationPayrollRead(BaseModel):
    payment_month: str
    teachers: list[EducationPayrollTeacherRead]
    history: list[EducationPayrollHistoryRead]


class EducationPayrollCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teacher_id: int = Field(gt=0)
    payment_month: str = Field(min_length=7, max_length=7)
    amount: int = Field(gt=0, le=10**12)
    pay_type: EducationPayType = "naqd"
    note: str = Field(default="", max_length=200)

    @field_validator("payment_month", "note", mode="before")
    @classmethod
    def normalize_payroll_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class EducationPayrollCreated(BaseModel):
    ok: bool = True
    id: int
