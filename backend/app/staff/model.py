from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    JSON,
    String,
    Time,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StaffMember(Base):
    __tablename__ = "staff_members"
    __table_args__ = (
        CheckConstraint("salary >= 0", name="ck_staff_members_salary"),
        CheckConstraint(
            "status IN ('active', 'fired')",
            name="ck_staff_members_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    profession: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    salary: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    hire_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    login: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    can_login: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    schedule: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StaffProfession(Base):
    __tablename__ = "staff_professions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StaffAttendance(Base):
    __tablename__ = "staff_attendance"
    __table_args__ = (
        CheckConstraint(
            "status IN ('keldi', 'kelmadi', 'dam')",
            name="ck_staff_attendance_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    time_in: Mapped[time | None] = mapped_column(Time)
    time_out: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StaffSession(Base):
    __tablename__ = "staff_sessions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "uq_staff_members_business_legacy",
    StaffMember.business_account_id,
    StaffMember.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_staff_members_business_login",
    StaffMember.business_account_id,
    func.lower(StaffMember.login),
    unique=True,
    postgresql_where=text("login IS NOT NULL AND login <> ''"),
    sqlite_where=text("login IS NOT NULL AND login <> ''"),
)
Index(
    "ix_staff_members_business_status_name",
    StaffMember.business_account_id,
    StaffMember.status,
    StaffMember.name,
)
Index(
    "uq_staff_professions_business_name",
    StaffProfession.business_account_id,
    func.lower(StaffProfession.name),
    unique=True,
)
Index(
    "uq_staff_attendance_staff_date",
    StaffAttendance.staff_id,
    StaffAttendance.date,
    unique=True,
)
Index(
    "ix_staff_attendance_business_date",
    StaffAttendance.business_account_id,
    StaffAttendance.date,
    StaffAttendance.staff_id,
)
Index("uq_staff_sessions_token_hash", StaffSession.token_hash, unique=True)
Index(
    "ix_staff_sessions_active_staff",
    StaffSession.staff_id,
    StaffSession.expires_at,
    postgresql_where=text("revoked_at IS NULL"),
    sqlite_where=text("revoked_at IS NULL"),
)
