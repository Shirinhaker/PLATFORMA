"""Kontragentlar: royxat va kartochka."""

from __future__ import annotations

from app.core.errors import ApiError
from app.documents.model import DocumentCounterparty
from app.documents.schemas import (
    CounterpartyListRead,
    CounterpartyWrite,
    CreatedRead,
    MutationRead,
)
from app.documents.service_parts.base import DocumentServiceBase
from app.documents.service_parts.helpers import (
    COUNTERPARTY_TYPES,
)


class CounterpartiesMixin(DocumentServiceBase):
    async def list_counterparties(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> CounterpartyListRead:
        self._require_documents(permissions)
        async with self._session_factory() as session:
            rows = await self._repository.counterparties(
                session,
                business_account_id=business_account_id,
            )
            result = CounterpartyListRead(
                counterparties=[self._counterparty_read(row) for row in rows],
                count=len(rows),
                types=list(COUNTERPARTY_TYPES),
            )
            await session.rollback()
            return result

    async def create_counterparty(
        self,
        *,
        business_account_id: int,
        is_owner: bool,
        body: CounterpartyWrite,
    ) -> CreatedRead:
        self._require_owner(is_owner)
        async with self._session_factory() as session:
            try:
                now = self._now_provider()
                row = DocumentCounterparty(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    **body.model_dump(),
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                await session.flush()
                await session.commit()
                return CreatedRead(id=row.id)
            except Exception:
                await session.rollback()
                raise

    async def update_counterparty(
        self,
        *,
        business_account_id: int,
        counterparty_id: int,
        is_owner: bool,
        body: CounterpartyWrite,
    ) -> MutationRead:
        self._require_owner(is_owner)
        async with self._session_factory() as session:
            try:
                row = await self._repository.counterparty(
                    session,
                    business_account_id=business_account_id,
                    counterparty_id=counterparty_id,
                    lock=True,
                )
                if row is None:
                    raise ApiError(
                        404, "counterparty_not_found", "Kontragent topilmadi."
                    )
                for name, value in body.model_dump().items():
                    setattr(row, name, value)
                row.updated_at = self._now_provider()
                await session.flush()
                await session.commit()
                return MutationRead()
            except Exception:
                await session.rollback()
                raise

    async def delete_counterparty(
        self,
        *,
        business_account_id: int,
        counterparty_id: int,
        is_owner: bool,
    ) -> None:
        self._require_owner(is_owner)
        async with self._session_factory() as session:
            try:
                row = await self._repository.counterparty(
                    session,
                    business_account_id=business_account_id,
                    counterparty_id=counterparty_id,
                    lock=True,
                )
                if row is None:
                    raise ApiError(
                        404, "counterparty_not_found", "Kontragent topilmadi."
                    )
                await session.delete(row)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise
