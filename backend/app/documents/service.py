from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.documents.model import BusinessDocument, DocumentCounterparty
from app.documents.repository import DocumentRepository
from app.documents.schemas import (
    CounterpartyListRead,
    CounterpartyRead,
    CounterpartyWrite,
    CreatedRead,
    DocumentListRead,
    DocumentRead,
    DocumentRespond,
    DocumentRespondedRead,
    DocumentSend,
    DocumentSentRead,
    DocumentWrite,
    MutationRead,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
COUNTERPARTY_TYPES = ("Yetkazib beruvchi", "Mijoz", "Hamkor", "Boshqa")


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


class DocumentService:
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
                    raise ApiError(404, "counterparty_not_found", "Kontragent topilmadi.")
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
                    raise ApiError(404, "counterparty_not_found", "Kontragent topilmadi.")
                await session.delete(row)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def list_documents(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        direction: str | None,
    ) -> DocumentListRead:
        self._require_documents(permissions)
        normalized = direction if direction in {"ichki", "kiruvchi", "chiquvchi"} else None
        async with self._session_factory() as session:
            rows = await self._repository.documents(
                session,
                business_account_id=business_account_id,
                direction=normalized,
            )
            result = DocumentListRead(
                documents=[self._document_read(row, name) for row, name in rows],
                count=len(rows),
            )
            await session.rollback()
            return result

    async def get_document(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        document_id: int,
    ) -> DocumentRead:
        self._require_documents(permissions)
        async with self._session_factory() as session:
            found = await self._repository.document(
                session,
                business_account_id=business_account_id,
                document_id=document_id,
            )
            if found is None:
                raise ApiError(404, "document_not_found", "Hujjat topilmadi.")
            result = self._document_read(*found)
            await session.rollback()
            return result

    async def create_document(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: DocumentWrite,
    ) -> CreatedRead:
        self._require_documents(permissions)
        async with self._session_factory() as session:
            try:
                contractor_id = await self._contractor_id(
                    session,
                    business_account_id=business_account_id,
                    direction=body.direction,
                    contractor_id=body.contractor_id,
                )
                now = self._now_provider()
                row = BusinessDocument(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    **body.model_dump(exclude={"contractor_id"}),
                    contractor_id=contractor_id,
                    sender_business_id=None,
                    sender_name_snapshot="",
                    receiver_tax_id="",
                    status="",
                    source_document_id=None,
                    responded_at=None,
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

    async def update_document(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        document_id: int,
        body: DocumentWrite,
    ) -> MutationRead:
        self._require_documents(permissions)
        async with self._session_factory() as session:
            try:
                found = await self._repository.document(
                    session,
                    business_account_id=business_account_id,
                    document_id=document_id,
                    lock=True,
                )
                if found is None:
                    raise ApiError(404, "document_not_found", "Hujjat topilmadi.")
                row, _name = found
                if row.direction == "kiruvchi":
                    raise ApiError(
                        409,
                        "incoming_document_read_only",
                        "Kiruvchi hujjat matnini o‘zgartirib bo‘lmaydi.",
                    )
                contractor_id = await self._contractor_id(
                    session,
                    business_account_id=business_account_id,
                    direction=body.direction,
                    contractor_id=body.contractor_id,
                )
                for name, value in body.model_dump(exclude={"contractor_id"}).items():
                    setattr(row, name, value)
                row.contractor_id = contractor_id
                row.updated_at = self._now_provider()
                await session.flush()
                await session.commit()
                return MutationRead()
            except Exception:
                await session.rollback()
                raise

    async def delete_document(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        document_id: int,
    ) -> None:
        self._require_documents(permissions)
        async with self._session_factory() as session:
            try:
                found = await self._repository.document(
                    session,
                    business_account_id=business_account_id,
                    document_id=document_id,
                    lock=True,
                )
                if found is None:
                    raise ApiError(404, "document_not_found", "Hujjat topilmadi.")
                row, _name = found
                if row.direction == "kiruvchi":
                    raise ApiError(
                        409,
                        "incoming_document_read_only",
                        "Kiruvchi hujjatni bu yerdan o‘chirib bo‘lmaydi.",
                    )
                await session.delete(row)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def send_document(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        document_id: int,
        body: DocumentSend,
    ) -> DocumentSentRead:
        self._require_documents(permissions)
        receiver_inn = _digits(body.receiver_inn)
        if len(receiver_inn) < 9:
            raise ApiError(
                422,
                "receiver_tax_id_invalid",
                "STIR raqami noto'g'ri (kamida 9 raqam).",
            )
        async with self._session_factory() as session:
            try:
                found = await self._repository.document(
                    session,
                    business_account_id=business_account_id,
                    document_id=document_id,
                    lock=True,
                )
                if found is None:
                    raise ApiError(404, "document_not_found", "Hujjat topilmadi.")
                source, _name = found
                if source.direction != "chiquvchi":
                    raise ApiError(
                        409,
                        "outgoing_document_required",
                        "Faqat chiquvchi hujjat yuboriladi.",
                    )
                sender = await self._repository.business_profile(
                    session,
                    business_account_id=business_account_id,
                )
                if sender is None:
                    raise ApiError(404, "profile_not_found", "Profil topilmadi.")
                targets = await self._repository.receiver_businesses(
                    session,
                    tax_id_digits=receiver_inn,
                )
                if not targets:
                    raise ApiError(
                        404,
                        "document_receiver_not_found",
                        "Bu STIR raqamli firma ilovada topilmadi. Firma ro'yxatdan o'tganini tekshiring.",
                    )
                if len(targets) > 1:
                    raise ApiError(
                        409,
                        "document_receiver_ambiguous",
                        "Bu STIR bir nechta profilga tegishli. Administratorga murojaat qiling.",
                    )
                target = targets[0]
                if target.account_id == business_account_id:
                    raise ApiError(
                        422,
                        "document_self_send",
                        "Hujjatni o'zingizga yubora olmaysiz.",
                    )
                now = self._now_provider()
                session.add(BusinessDocument(
                    business_account_id=target.account_id,
                    legacy_source_id=None,
                    direction="kiruvchi",
                    doc_type=source.doc_type,
                    title=source.title,
                    number=source.number,
                    doc_date=source.doc_date,
                    contractor_id=None,
                    body=source.body,
                    sender_business_id=business_account_id,
                    sender_name_snapshot=sender.name[:120],
                    receiver_tax_id=receiver_inn,
                    status="kutilmoqda",
                    source_document_id=source.id,
                    responded_at=None,
                    created_at=now,
                    updated_at=now,
                ))
                source.status = "yuborilgan"
                source.receiver_tax_id = receiver_inn
                source.updated_at = now
                await session.flush()
                await session.commit()
                return DocumentSentRead(receiver_name=target.name)
            except Exception:
                await session.rollback()
                raise

    async def respond_document(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        document_id: int,
        body: DocumentRespond,
    ) -> DocumentRespondedRead:
        self._require_documents(permissions)
        async with self._session_factory() as session:
            try:
                found = await self._repository.document(
                    session,
                    business_account_id=business_account_id,
                    document_id=document_id,
                    lock=True,
                )
                if found is None:
                    raise ApiError(404, "document_not_found", "Hujjat topilmadi.")
                incoming, _name = found
                if incoming.direction != "kiruvchi":
                    raise ApiError(
                        409,
                        "incoming_document_required",
                        "Bu amal faqat kiruvchi hujjat uchun.",
                    )
                if incoming.status != "kutilmoqda":
                    raise ApiError(
                        409,
                        "document_already_responded",
                        "Bu hujjatga allaqachon javob berilgan.",
                    )
                status = "qabul qilindi" if body.action == "qabul" else "rad etildi"
                now = self._now_provider()
                incoming.status = status
                incoming.responded_at = now
                incoming.updated_at = now
                if incoming.sender_business_id:
                    source = await self._repository.source_document(
                        session,
                        source_document_id=incoming.source_document_id or 0,
                        sender_business_id=incoming.sender_business_id,
                        doc_type=incoming.doc_type,
                        number=incoming.number,
                        body=incoming.body,
                    )
                    if source is not None:
                        source.status = status
                        source.updated_at = now
                await session.flush()
                await session.commit()
                return DocumentRespondedRead(status=status)
            except Exception:
                await session.rollback()
                raise

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
