from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CabinetRecord(Base):
    __tablename__ = "cabinet_records"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "account_type",
            "resource",
            "source_key",
            name="uq_cabinet_records_owner_resource_source",
        ),
        Index(
            "ix_cabinet_records_owner_resource_ordinal",
            "account_id",
            "account_type",
            "resource",
            "ordinal",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    resource: Mapped[str] = mapped_column(String(96), nullable=False)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CabinetRecordField(Base):
    __tablename__ = "cabinet_record_fields"
    __table_args__ = (
        UniqueConstraint(
            "record_id",
            "path",
            name="uq_cabinet_record_fields_record_path",
        ),
        Index("ix_cabinet_record_fields_record", "record_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cabinet_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_integer: Mapped[int | None] = mapped_column(BigInteger)
    value_float: Mapped[float | None] = mapped_column(Float)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean)


class CabinetNormalizationRun(Base):
    __tablename__ = "cabinet_normalization_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    schema_version: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profiles_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profiles_verified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resources_source: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resources_target: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_source: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_target: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_digest: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    error_code: Mapped[str] = mapped_column(String(120), nullable=False, default="")
