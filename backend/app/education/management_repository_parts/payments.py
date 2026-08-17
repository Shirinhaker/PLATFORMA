"""O'quvchi to'lovlari va jamlar."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.education.management_repository_parts.base import (
    EducationManagementRepositoryBase,
)
from app.education.model import (
    EducationPayment,
    EducationStudent,
)


class PaymentsMixin(EducationManagementRepositoryBase):
    async def student_payments(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_id: int,
    ) -> list[EducationPayment]:
        return list(
            (
                await session.scalars(
                    select(EducationPayment)
                    .where(
                        EducationPayment.business_account_id == business_account_id,
                        EducationPayment.student_id == student_id,
                    )
                    .order_by(
                        EducationPayment.payment_month.desc(),
                        EducationPayment.id.desc(),
                    )
                    .limit(300)
                )
            ).all()
        )

    async def payment_totals(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_ids: list[int],
        minimum_month: str = "",
    ):
        if not student_ids:
            return []
        statement = (
            select(
                EducationPayment.student_id,
                EducationPayment.payment_month,
                func.coalesce(func.sum(EducationPayment.amount), 0),
            )
            .where(
                EducationPayment.business_account_id == business_account_id,
                EducationPayment.student_id.in_(student_ids),
                EducationPayment.voided_at.is_(None),
            )
            .group_by(EducationPayment.student_id, EducationPayment.payment_month)
        )
        if minimum_month:
            statement = statement.where(EducationPayment.payment_month >= minimum_month)
        return (await session.execute(statement)).all()

    async def active_payments(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_ids: list[int],
        minimum_month: str = "",
    ) -> list[EducationPayment]:
        if not student_ids:
            return []
        statement = select(EducationPayment).where(
            EducationPayment.business_account_id == business_account_id,
            EducationPayment.student_id.in_(student_ids),
            EducationPayment.voided_at.is_(None),
        )
        if minimum_month:
            statement = statement.where(EducationPayment.payment_month >= minimum_month)
        return list((await session.scalars(statement)).all())

    async def payment_history(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_month: str,
    ):
        return (
            await session.execute(
                select(EducationPayment, EducationStudent.full_name)
                .outerjoin(
                    EducationStudent,
                    (EducationStudent.id == EducationPayment.student_id)
                    & (
                        EducationStudent.business_account_id
                        == EducationPayment.business_account_id
                    ),
                )
                .where(
                    EducationPayment.business_account_id == business_account_id,
                    EducationPayment.payment_month == payment_month,
                )
                .order_by(EducationPayment.id.desc())
                .limit(300)
            )
        ).all()

    async def payment(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_id: int,
        lock: bool = False,
    ) -> EducationPayment | None:
        statement = select(EducationPayment).where(
            EducationPayment.id == payment_id,
            EducationPayment.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
