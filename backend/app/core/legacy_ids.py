"""Shared identifier mapping used while old IDs remain in public contracts.

The mapping table is runtime data, so its ORM model lives outside the offline
migration package. Migration commands re-export this same model.
"""

from sqlalchemy import BigInteger, ForeignKey, Identity, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LegacyIdMap(Base):
    __tablename__ = "legacy_id_map"
    __table_args__ = (
        UniqueConstraint("entity_type", "legacy_id", name="uq_legacy_id_map"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    source_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_reason: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="",
    )
    last_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
