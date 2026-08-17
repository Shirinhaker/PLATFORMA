"""Hujjatlar: royxat, yaratish, tahrirlash, ochirish."""

from __future__ import annotations

from app.core.errors import ApiError
from app.documents.model import BusinessDocument
from app.documents.schemas import (
    CreatedRead,
    DocumentListRead,
    DocumentRead,
    DocumentWrite,
    MutationRead,
)
from app.documents.service_parts.base import DocumentServiceBase


class DocumentsMixin(DocumentServiceBase):
    async def list_documents(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        direction: str | None,
    ) -> DocumentListRead:
        self._require_documents(permissions)
        normalized = (
            direction if direction in {"ichki", "kiruvchi", "chiquvchi"} else None
        )
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
