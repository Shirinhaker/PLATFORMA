"""Buyurtma yaratish.

Eng murakkab amal: narx, ombor, qarz va bildirishnoma bir
tranzaksiyada bog'lanadi.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.orders.model import Order, OrderItem
from app.orders.notifications import (
    append_order_notification,
)
from app.orders.schemas import (
    OrderCreate,
    OrderRead,
)
from app.orders.service_parts.base import OrderServiceBase


class CreationMixin(OrderServiceBase):
    async def create(
        self, *, account_id: int, account_type: AccountType, body: OrderCreate
    ) -> OrderRead:
        async with self._session_factory() as session:
            provider_id = await self._resolve_profile_public_id(
                session, body.provider_kind, body.provider_public_id
            )
            if provider_id is None:
                raise ApiError(
                    404,
                    "order_provider_not_found",
                    "Buyurtma qabul qiluvchi topilmadi.",
                )
            if provider_id == account_id and body.provider_kind == account_type.value:
                raise ApiError(
                    400, "order_self_forbidden", "O'zingizga buyurtma bera olmaysiz."
                )
            if not body.phone.strip():
                raise ApiError(
                    400,
                    "order_phone_required",
                    "Telefon raqam kiritish kerak.",
                )
            if body.order_type == "delivery" and (
                body.delivery_lat is None or body.delivery_lng is None
            ):
                raise ApiError(
                    400,
                    "order_delivery_point_required",
                    "Yetkazib berish joyini xaritada belgilang.",
                )
            customer = await self._profile(session, account_id, account_type.value)
            provider = await self._profile(session, provider_id, body.provider_kind)
            if customer is None or provider is None:
                raise ApiError(404, "order_profile_not_found", "Profil topilmadi.")
            snapshots = await self._catalog_snapshots(
                session, body.items, provider_id, body.provider_kind
            )
            listing = await self._resolve_listing(
                session,
                body.listing_public_id,
                provider_id,
                body.provider_kind,
            )
            now = datetime.now(UTC)
            title = body.title or (
                snapshots[0]["name"]
                if snapshots
                else listing.title
                if listing is not None
                else (
                    "Biznesga buyurtma"
                    if body.provider_kind == "business"
                    else "Qabul / xizmatga yozilish"
                )
            )
            if not body.title and len(snapshots) > 1:
                title = f"{title} + {len(snapshots) - 1} ta"
            total = sum(int(row["line_total"]) for row in snapshots)
            category = (
                "service"
                if body.order_type == "booking"
                or (snapshots and all(row["kind"] == "service" for row in snapshots))
                or (not snapshots and body.provider_kind == "user")
                else "product"
            )
            order = Order(
                legacy_source_id=None,
                customer_account_id=account_id,
                customer_kind=account_type.value,
                customer_name=customer.name,
                customer_phone=customer.phone,
                provider_account_id=provider_id,
                provider_kind=body.provider_kind,
                provider_name=provider.name,
                provider_phone=provider.phone,
                item_id=snapshots[0]["item"].id if len(snapshots) == 1 else None,
                listing_id=listing.id if listing is not None else None,
                title=title[:180],
                note=body.note,
                phone=body.phone,
                order_type=body.order_type,
                order_category=category,
                address=body.address,
                desired_time=body.desired_time,
                delivery_lat=body.delivery_lat,
                delivery_lng=body.delivery_lng,
                qty=(
                    sum(Decimal(str(row["qty"])) for row in snapshots)
                    if snapshots
                    else Decimal("1")
                ),
                total_amount=total,
                status="new",
                payment_status="",
                pay_type="",
                debtor_id=None,
                receipt_message_id=None,
                problem_open=False,
                problem_reason="",
                problem_note="",
                problem_solution="",
                problem_opened_at=None,
                problem_resolved_at=None,
                last_event="created",
                customer_seen_at=now,
                provider_seen_at=None,
                accepted_at=None,
                ready_at=None,
                handed_off_at=None,
                seller_completed_at=None,
                customer_received_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(order)
            await session.flush()
            for row in snapshots:
                session.add(
                    OrderItem(
                        order_id=order.id,
                        legacy_source_id=None,
                        catalog_item_id=row["item"].id,
                        item_name=row["name"],
                        price_text=row["price"],
                        qty=Decimal(str(row["qty"])),
                        unit=row["unit"],
                        line_total=row["line_total"],
                        note=row["note"],
                        kind=row["kind"],
                        created_at=now,
                    )
                )
            await session.flush()
            await self._event(session, "order.created", order, account_id)
            await append_order_notification(
                session,
                self._notification_repository,
                order,
                side="provider",
                event="created",
                title="Yangi buyurtma keldi",
                body="Buyurtmani ko'rib, qabul qiling.",
                action_type="accept_order",
            )
            await session.commit()
            return await self._project(session, order, "customer")
