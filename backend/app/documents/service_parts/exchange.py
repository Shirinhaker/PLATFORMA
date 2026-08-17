"""Hujjat almashinuvi: yuborish va javob."""

from __future__ import annotations

from app.core.errors import ApiError
from app.documents.model import BusinessDocument
from app.documents.schemas import (
    DocumentRespond,
    DocumentRespondedRead,
    DocumentSend,
    DocumentSentRead,
)
from app.documents.service_parts.base import DocumentServiceBase
from app.documents.service_parts.helpers import (
    _digits,
)


class ExchangeMixin(DocumentServiceBase):
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
                session.add(
                    BusinessDocument(
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
                    )
                )
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
