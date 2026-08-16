from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account
from app.documents.model import BusinessDocument, DocumentCounterparty
from app.profiles.model import BusinessProfile


def _tax_id_digits(column):
    expression = column
    for character in (" ", "-", ".", "/", "(", ")"):
        expression = func.replace(expression, character, "")
    return expression


class DocumentRepository:
    async def business_profile(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> BusinessProfile | None:
        return await session.get(BusinessProfile, business_account_id)

    async def counterparties(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> list[DocumentCounterparty]:
        return list(
            (
                await session.scalars(
                    select(DocumentCounterparty)
                    .where(
                        DocumentCounterparty.business_account_id == business_account_id
                    )
                    .order_by(
                        func.lower(DocumentCounterparty.name),
                        DocumentCounterparty.id,
                    )
                )
            ).all()
        )

    async def counterparty(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        counterparty_id: int,
        lock: bool = False,
    ) -> DocumentCounterparty | None:
        statement = select(DocumentCounterparty).where(
            DocumentCounterparty.id == counterparty_id,
            DocumentCounterparty.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def documents(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        direction: str | None,
    ) -> list[tuple[BusinessDocument, str]]:
        statement = (
            select(BusinessDocument, DocumentCounterparty.name)
            .outerjoin(
                DocumentCounterparty,
                DocumentCounterparty.id == BusinessDocument.contractor_id,
            )
            .where(BusinessDocument.business_account_id == business_account_id)
        )
        if direction:
            statement = statement.where(BusinessDocument.direction == direction)
        rows = (
            await session.execute(statement.order_by(BusinessDocument.id.desc()))
        ).all()
        return [(row[0], row[1] or "") for row in rows]

    async def document(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        document_id: int,
        lock: bool = False,
    ) -> tuple[BusinessDocument, str] | None:
        statement = (
            select(BusinessDocument, DocumentCounterparty.name)
            .outerjoin(
                DocumentCounterparty,
                DocumentCounterparty.id == BusinessDocument.contractor_id,
            )
            .where(
                BusinessDocument.id == document_id,
                BusinessDocument.business_account_id == business_account_id,
            )
        )
        if lock:
            statement = statement.with_for_update(of=BusinessDocument)
        row = (await session.execute(statement)).first()
        return (row[0], row[1] or "") if row else None

    async def receiver_businesses(
        self,
        session: AsyncSession,
        *,
        tax_id_digits: str,
    ) -> list[BusinessProfile]:
        return list(
            (
                await session.scalars(
                    select(BusinessProfile)
                    .join(Account, Account.id == BusinessProfile.account_id)
                    .where(
                        Account.status == "active",
                        _tax_id_digits(BusinessProfile.tax_id) == tax_id_digits,
                    )
                    .order_by(BusinessProfile.account_id)
                    .limit(2)
                )
            ).all()
        )

    async def source_document(
        self,
        session: AsyncSession,
        *,
        source_document_id: int,
        sender_business_id: int,
        doc_type: str,
        number: str,
        body: str,
    ) -> BusinessDocument | None:
        source = await session.scalar(
            select(BusinessDocument)
            .where(
                BusinessDocument.id == source_document_id,
                BusinessDocument.business_account_id == sender_business_id,
                BusinessDocument.direction == "chiquvchi",
            )
            .with_for_update()
        )
        if source is not None:
            return source
        return await session.scalar(
            select(BusinessDocument)
            .where(
                BusinessDocument.business_account_id == sender_business_id,
                BusinessDocument.direction == "chiquvchi",
                BusinessDocument.doc_type == doc_type,
                BusinessDocument.number == number,
                BusinessDocument.body == body,
            )
            .order_by(BusinessDocument.id.desc())
            .limit(1)
            .with_for_update()
        )
