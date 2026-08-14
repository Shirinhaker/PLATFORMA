from sqlalchemy import BigInteger, String, column, select, table
from sqlalchemy.ext.asyncio import AsyncSession


_LEGACY_ID_MAP = table(
    "legacy_id_map",
    column("entity_type", String(64)),
    column("legacy_id", BigInteger),
    column("target_id", BigInteger),
    column("mapping_status", String(40)),
)


async def legacy_id_for_target(
    session: AsyncSession,
    *,
    entity_type: str,
    target_id: int,
) -> int | None:
    """Migratsiya ORM paketini import qilmasdan eski ID ni topadi."""
    value = await session.scalar(
        select(_LEGACY_ID_MAP.c.legacy_id)
        .where(
            _LEGACY_ID_MAP.c.entity_type == entity_type,
            _LEGACY_ID_MAP.c.target_id == target_id,
            _LEGACY_ID_MAP.c.mapping_status == "mapped",
        )
        .order_by(_LEGACY_ID_MAP.c.legacy_id)
        .limit(1)
    )
    return int(value) if value is not None else None
