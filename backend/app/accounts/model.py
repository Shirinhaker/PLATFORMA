from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, Identity, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountType(str, Enum):
    USER = "user"
    BUSINESS = "business"


ACCOUNT_TYPE_ENUM = SqlEnum(
    AccountType,
    name="account_type",
    values_callable=lambda enum_type: [item.value for item in enum_type],
    validate_strings=True,
)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        Index(
            "uq_accounts_telegram_type",
            "telegram_user_id",
            "account_type",
            unique=True,
            postgresql_where=text("telegram_user_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_type: Mapped[AccountType] = mapped_column(
        ACCOUNT_TYPE_ENUM,
        nullable=False,
    )
    login: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
