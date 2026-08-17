"""Tarif katalogi va joriy obuna."""

from __future__ import annotations

from sqlalchemy import select

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.payments.model import (
    BusinessSubscription,
    PaymentMethod,
    PlatformPrice,
)
from app.payments.schemas import (
    BusinessSubscriptionSummary,
    PaymentCatalogRead,
    PaymentMethodRead,
    PaymentPriceRead,
)
from app.payments.service_parts.base import PaymentServiceBase
from app.payments.service_parts.helpers import (
    _subscription_row,
    _virtual_free_subscription,
)


class CatalogMixin(PaymentServiceBase):
    async def catalog(self) -> PaymentCatalogRead:
        async with self._session_factory() as session:
            prices = list(
                (
                    await session.scalars(
                        select(PlatformPrice)
                        .where(PlatformPrice.active == 1)
                        .order_by(PlatformPrice.service_type, PlatformPrice.amount_uzs)
                    )
                ).all()
            )
            methods = list(
                (
                    await session.scalars(
                        select(PaymentMethod)
                        .where(PaymentMethod.active == 1)
                        .order_by(PaymentMethod.sort_order, PaymentMethod.id)
                    )
                ).all()
            )
            response = PaymentCatalogRead(
                prices=[
                    PaymentPriceRead(
                        price_code=price.price_code,
                        service_type=price.service_type,
                        amount_uzs=price.amount_uzs,
                        plan_code=str((price.config or {}).get("plan_code") or ""),
                        duration_months=int(
                            (price.config or {}).get("duration_months") or 0
                        ),
                    )
                    for price in prices
                ],
                methods=[
                    PaymentMethodRead(
                        id=method.id,
                        method_type=method.method_type,
                        name=method.name,
                        recipient_name=method.recipient_name,
                        instructions=method.instructions,
                        details=method.details or {},
                    )
                    for method in methods
                ],
            )
            await session.rollback()
            return response

    async def subscription(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> BusinessSubscriptionSummary:
        """Biznesning joriy obunasi va v1656 tartibidagi tarixi."""
        if account_type is not AccountType.BUSINESS:
            raise ApiError(
                403,
                "business_account_required",
                "Bu bo'lim faqat biznes kabinetida mavjud.",
            )
        async with self._session_factory() as session:
            now = self._now()
            expired = await session.execute(
                BusinessSubscription.__table__.update()
                .where(
                    BusinessSubscription.business_account_id == account_id,
                    BusinessSubscription.status == "active",
                    BusinessSubscription.expires_at > 0,
                    BusinessSubscription.expires_at <= now,
                )
                .values(status="expired")
            )
            rows = list(
                (
                    await session.scalars(
                        select(BusinessSubscription)
                        .where(BusinessSubscription.business_account_id == account_id)
                        .order_by(BusinessSubscription.id.desc())
                    )
                ).all()
            )
            current = next((row for row in rows if row.status == "active"), None)
            response = BusinessSubscriptionSummary(
                current=(
                    _subscription_row(current)
                    if current is not None
                    else _virtual_free_subscription()
                ),
                history=[
                    _subscription_row(row) for row in rows if row.status != "active"
                ],
            )
            if expired.rowcount:
                await session.commit()
            else:
                await session.rollback()
            return response
