"""Obunalar: kim kimga obuna bo'lgani.

v1656da ikkita jadval bor edi — `follows` (foydalanuvchi obunalari) va
`business_follows` (biznes obunalari). Yangi modelda obunachi ham
akkaunt, shuning uchun bitta jadval yetarli: akkaunt turi
`accounts.account_type` dan ma'lum.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProfileFollow(Base):
    __tablename__ = "profile_follows"
    __table_args__ = (
        CheckConstraint(
            "target_kind IN ('user', 'business')",
            name="ck_profile_follows_target_kind",
        ),
        CheckConstraint(
            "follower_account_id <> target_account_id",
            name="ck_profile_follows_not_self",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    follower_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


# Bir akkaunt bir nishonga faqat bir marta obuna bo'ladi.
Index(
    "uq_profile_follows_pair",
    ProfileFollow.follower_account_id,
    ProfileFollow.target_account_id,
    unique=True,
)
# Obunachilar sonini sanash uchun.
Index(
    "ix_profile_follows_target",
    ProfileFollow.target_account_id,
    ProfileFollow.id,
)
# "Men kimga obuna bo'lganman" ro'yxati uchun.
Index(
    "ix_profile_follows_follower",
    ProfileFollow.follower_account_id,
    ProfileFollow.created_at,
    ProfileFollow.id,
)
