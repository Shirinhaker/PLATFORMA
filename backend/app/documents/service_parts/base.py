"""Umumiy asos: huquq tekshiruvi va javob shakli."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.documents.model import BusinessDocument, DocumentCounterparty
from app.documents.repository import DocumentRepository
from app.documents.schemas import (
    CounterpartyRead,
    DocumentRead,
)
from app.documents.service_parts.helpers import (
    NowProvider,
    SessionFactory,
)


class DocumentServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: DocumentRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or DocumentRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def _contractor_id(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        direction: str,
        contractor_id: int | None,
    ) -> int | None:
        if direction != "chiquvchi" or contractor_id is None:
            return None
        row = await self._repository.counterparty(
            session,
            business_account_id=business_account_id,
            counterparty_id=contractor_id,
        )
        if row is None:
            raise ApiError(404, "counterparty_not_found", "Kontragent topilmadi.")
        return row.id

    @staticmethod
    def _counterparty_read(row: DocumentCounterparty) -> CounterpartyRead:
        return CounterpartyRead(
            id=row.id,
            name=row.name,
            ctype=row.ctype,
            director=row.director,
            phone=row.phone,
            address=row.address,
            inn=row.inn,
            account=row.account,
            bank=row.bank,
            mfo=row.mfo,
            note=row.note,
            created_at=row.created_at,
        )

    @staticmethod
    def _document_read(row: BusinessDocument, contractor_name: str) -> DocumentRead:
        return DocumentRead(
            id=row.id,
            direction=row.direction,
            doc_type=row.doc_type,
            title=row.title,
            number=row.number,
            doc_date=row.doc_date,
            contractor_id=row.contractor_id,
            contractor_name=contractor_name,
            body=row.body,
            sender_name=row.sender_name_snapshot,
            receiver_inn=row.receiver_tax_id,
            status=row.status,
            created_at=row.created_at,
        )

    @staticmethod
    def _require_documents(permissions: tuple[str, ...] | None) -> None:
        if permissions is not None and "documents" not in permissions:
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )

    @staticmethod
    def _require_owner(is_owner: bool) -> None:
        if not is_owner:
            raise ApiError(
                403,
                "business_owner_required",
                "Bu amal faqat biznes egasi uchun.",
            )
