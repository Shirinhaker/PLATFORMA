from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MediaUploadGrant(Base):
    __tablename__ = "media_upload_grants"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    owner_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    object_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    declared_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "ix_media_upload_grants_cleanup",
    MediaUploadGrant.status,
    MediaUploadGrant.created_at,
)
