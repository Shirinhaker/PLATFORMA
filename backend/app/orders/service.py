from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogItem
from app.catalog.repository import build_content_public_id
from app.core.errors import ApiError
from app.legacy_migration.model import ReviewState
from app.listings.model import Listing
from app.orders.model import Order, OrderItem, OrderMessage
from app.orders.repository import OrderRepository
from app.orders.schemas import (
    OrderCreate,
    OrderChatRead,
    OrderMessageCreate,
    OrderMessageRead,
    OrderPaymentDecision,
    OrderProblemCreate,
    OrderProblemSolution,
    OrderRead,
    OrderStatusChange,
)
from app.orders.status import validate_status_change
from app.outbox.repository import enqueue_event
from app.profiles.model import BusinessProfile, UserProfile
from app.public_discovery.repository import build_listing_public_id, build_public_id
from app.public_discovery.schemas import PublicResultKind


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
ImageUrlProvider = Callable[[str], str]
FRACTIONAL_UNITS = frozenset({"kg", "g", "litr", "ml", "metr", "sm", "m²", "soat"})


class OrderService:
    def __init__(
        self,
        session_factory: SessionFactory,
        image_url_provider: ImageUrlProvider,
        *,
        repository: OrderRepository | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._image_url_provider = image_url_provider
        self._repository = repository or OrderRepository()

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
                raise ApiError(400, "order_self_forbidden", "O'zingizga buyurtma bera olmaysiz.")
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
                    400, "order_delivery_point_required",
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
                title=title[:180], note=body.note, phone=body.phone,
                order_type=body.order_type, order_category=category,
                address=body.address, desired_time=body.desired_time,
                delivery_lat=body.delivery_lat, delivery_lng=body.delivery_lng,
                qty=(
                    sum(Decimal(str(row["qty"])) for row in snapshots)
                    if snapshots
                    else Decimal("1")
                ),
                total_amount=total, status="new", payment_status="", pay_type="",
                receipt_message_id=None, problem_open=False, problem_reason="",
                problem_note="", problem_solution="", problem_opened_at=None,
                problem_resolved_at=None, last_event="created",
                customer_seen_at=now, provider_seen_at=None,
                accepted_at=None, ready_at=None, handed_off_at=None,
                seller_completed_at=None, customer_received_at=None,
                created_at=now, updated_at=now,
            )
            session.add(order)
            await session.flush()
            for row in snapshots:
                session.add(OrderItem(
                    order_id=order.id, legacy_source_id=None,
                    catalog_item_id=row["item"].id, item_name=row["name"],
                    price_text=row["price"], qty=Decimal(str(row["qty"])),
                    unit=row["unit"], line_total=row["line_total"],
                    note=row["note"], kind=row["kind"], created_at=now,
                ))
            await session.flush()
            await self._event(session, "order.created", order, account_id)
            await session.commit()
            return await self._project(session, order, "customer")

    async def list_my(self, *, account_id: int, account_type: AccountType) -> list[OrderRead]:
        return await self._list(account_id, "customer")

    async def list_inbox(self, *, account_id: int, account_type: AccountType) -> list[OrderRead]:
        return await self._list(account_id, "provider")

    async def mark_seen(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            now = datetime.now(UTC)
            if side == "customer":
                order.customer_seen_at = now
            else:
                order.provider_seen_at = now
            await session.commit()
            return await self._project(session, order, side)

    async def _list(self, account_id: int, side: str) -> list[OrderRead]:
        async with self._session_factory() as session:
            rows = await self._repository.list_for_side(session, account_id=account_id, side=side)
            items_by_order = await self._repository.items_for_orders(
                session, [row.id for row in rows]
            )
            business_ids = {
                row.provider_account_id
                for row in rows
                if row.provider_kind == "business"
            }
            businesses = {
                row.account_id: row
                for row in list((await session.scalars(
                    select(BusinessProfile).where(
                        BusinessProfile.account_id.in_(business_ids)
                    )
                )).all())
            } if business_ids else {}
            result = [
                await self._project(
                    session,
                    row,
                    side,
                    prefetched_items=items_by_order.get(row.id, []),
                    prefetched_business=businesses.get(row.provider_account_id),
                    business_prefetched=True,
                )
                for row in rows
            ]
            await session.rollback()
            return result

    async def change_status(
        self, *, order_id: int, account_id: int, account_type: AccountType,
        body: OrderStatusChange,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            validate_status_change(current=order.status, requested=body.status, side=side)
            if body.status == "tayyor":
                if order.problem_open:
                    raise ApiError(
                        409,
                        "order_problem_open",
                        "Muammoli buyurtmani tayyorlash yoki yakunlash mumkin emas. "
                        "Avval to'lov muammosini hal qiling.",
                    )
                if order.payment_status != "confirmed":
                    raise ApiError(
                        409,
                        "order_payment_not_confirmed",
                        "To'lov tasdiqlanmaguncha buyurtmani tayyorlash "
                        "yoki yakunlash mumkin emas.",
                    )
            now = datetime.now(UTC)
            order.status = body.status
            if body.status == "accepted":
                order.accepted_at = now
                order.payment_status = "pending"
            elif body.status == "tayyor":
                order.ready_at = now
            order.updated_at = now
            self._changed(order, side, body.status, now)
            await self._event(session, "order.status_changed", order, account_id)
            await session.commit()
            return await self._project(session, order, side)

    async def submit_payment(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "customer":
                raise ApiError(403, "order_customer_required", "Bu amal faqat buyurtmachiga tegishli.")
            if order.status != "accepted":
                raise ApiError(
                    409,
                    "order_not_accepted",
                    "Buyurtma sotuvchi tomonidan qabul qilinmagan.",
                )
            receipt = await self._repository.latest_receipt(
                session,
                order_id=order.id,
                sender_account_id=account_id,
            )
            if receipt is None:
                raise ApiError(
                    400,
                    "order_receipt_required",
                    "Avval to'lov cheki rasmini buyurtma chatiga yuboring.",
                )
            now = datetime.now(UTC)
            order.receipt_message_id = receipt.id
            order.payment_status = "submitted"
            order.updated_at = now
            self._changed(order, side, "payment_submitted", now)
            await self._event(session, "order.payment_submitted", order, account_id)
            await session.commit()
            return await self._project(session, order, side)

    async def set_payment(
        self, *, order_id: int, account_id: int, account_type: AccountType,
        body: OrderPaymentDecision,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "provider":
                raise ApiError(403, "order_provider_required", "Bu amal faqat xizmat ko'rsatuvchiga tegishli.")
            if order.status in {"done", "cancelled", "rejected"}:
                raise ApiError(
                    409,
                    "order_payment_finished",
                    "Yakunlangan buyurtmada to'lovni o'zgartirib bo'lmaydi.",
                )
            if body.status == "debt":
                raise ApiError(409, "order_debt_external", "Qarzga yozish bu modulga kirmaydi.")
            if order.payment_status not in {"submitted", "recheck", "disputed"}:
                message = (
                    "Buyurtmachi to'lov cheki va 'To'lov qildim' tasdig'ini "
                    "yubormagan."
                    if body.status == "confirmed"
                    else "To'lovni hozir tekshirib bo'lmaydi."
                )
                raise ApiError(409, "order_payment_transition_invalid", message)
            now = datetime.now(UTC)
            if body.status == "confirmed":
                order.payment_status = "confirmed"
                order.pay_type = "karta"
                order.status = "preparing"
                order.problem_open = False
                order.problem_resolved_at = now
                topic = "order.payment_confirmed"
            else:
                order.payment_status = body.status
                topic = (
                    "order.payment_rejected"
                    if body.status == "rejected"
                    else "order.payment_pending"
                )
            order.updated_at = now
            self._changed(order, side, body.status, now)
            system_text = {
                "confirmed": "✅ To'lov tasdiqlandi. Rahmat!",
                "rejected": (
                    "❌ To'lov tasdiqlanmadi. Iltimos, to'lovni tekshiring "
                    "yoki qayta yuboring."
                ),
                "pending": "⏳ To'lov kutilmoqda.",
            }[body.status]
            session.add(OrderMessage(
                legacy_source_id=None,
                order_id=order.id,
                sender_account_id=account_id,
                sender_kind=account_type.value,
                text=system_text,
                media_type="text",
                media_object_key="",
                legacy_media_url="",
                file_name="",
                reply_to_id=None,
                edited_at=None,
                deleted_at=None,
                is_deleted=False,
                created_at=now,
            ))
            await session.flush()
            await self._event(session, topic, order, account_id)
            await session.commit()
            return await self._project(session, order, side)

    async def open_problem(
        self, *, order_id: int, account_id: int, account_type: AccountType,
        body: OrderProblemCreate,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "provider":
                raise ApiError(403, "order_provider_required", "Bu amal faqat xizmat ko'rsatuvchiga tegishli.")
            if order.status in {"done", "cancelled", "rejected"}:
                raise ApiError(
                    409,
                    "order_problem_finished",
                    "Yakunlangan buyurtmada muammo ochib bo'lmaydi.",
                )
            if order.payment_status not in {"submitted", "recheck", "disputed"}:
                raise ApiError(
                    409,
                    "order_problem_invalid",
                    "Avval buyurtmachi to'lov qilganini bildirishi kerak.",
                )
            now = datetime.now(UTC)
            order.problem_open = True
            order.problem_reason = body.reason
            order.problem_note = body.note.strip()
            order.problem_solution = ""
            order.problem_opened_at = now
            order.problem_resolved_at = None
            order.payment_status = "disputed"
            order.updated_at = now
            self._changed(order, side, "problem", now)
            await self._event(session, "order.problem_opened", order, account_id)
            await session.commit()
            return await self._project(session, order, side)

    async def choose_problem_solution(
        self, *, order_id: int, account_id: int, account_type: AccountType,
        body: OrderProblemSolution,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "customer" or not order.problem_open:
                raise ApiError(
                    409,
                    "order_problem_solution_invalid",
                    "Bu buyurtmada ochiq muammo yo'q.",
                )
            now = datetime.now(UTC)
            order.problem_solution = body.solution
            if body.solution == "new_receipt":
                order.payment_status = "recheck"
            elif body.solution == "pickup":
                order.order_type = "pickup"
            order.updated_at = now
            self._changed(order, side, "problem_solution", now)
            await self._event(session, "order.problem_solution_selected", order, account_id)
            await session.commit()
            return await self._project(session, order, side)

    async def handoff(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "provider":
                raise ApiError(
                    403,
                    "order_provider_required",
                    "Bu amal faqat xizmat ko'rsatuvchiga tegishli.",
                )
            if order.status != "tayyor":
                raise ApiError(
                    409,
                    "order_handoff_invalid",
                    "Buyurtma hali topshirishga tayyor emas.",
                )
            if order.order_type != "pickup":
                raise ApiError(409, "order_delivery_external", "Yetkazib berish holati alohida modulda tasdiqlanadi.")
            now = datetime.now(UTC)
            order.status = "pickup_waiting_customer"
            order.handed_off_at = now
            order.seller_completed_at = now
            order.updated_at = now
            self._changed(order, side, "handoff", now)
            await self._event(session, "order.handed_off", order, account_id)
            await session.commit()
            return await self._project(session, order, side)

    async def received(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "customer" or order.status not in {
                "pickup_waiting_customer", "delivered_waiting_customer"
            }:
                raise ApiError(
                    409,
                    "order_received_invalid",
                    "Buyurtmani qabul qilish bosqichi hali kelmagan.",
                )
            now = datetime.now(UTC)
            order.status = "done"
            order.customer_received_at = now
            order.updated_at = now
            self._changed(order, side, "completed", now)
            await self._event(session, "order.completed", order, account_id)
            await session.commit()
            return await self._project(session, order, side)

    async def list_messages(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> list[OrderMessageRead]:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id)
            rows = await self._repository.messages(session, order_id)
            now = datetime.now(UTC)
            if side == "customer":
                order.customer_seen_at = now
            else:
                order.provider_seen_at = now
            await session.commit()
            return [await self._project_message(session, row, account_id) for row in rows]

    async def chat(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> OrderChatRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id)
            rows = await self._repository.messages(session, order_id)
            now = datetime.now(UTC)
            if side == "customer":
                order.customer_seen_at = now
                other_side = "provider"
                other_kind = order.provider_kind
                other_id = order.provider_account_id
            else:
                order.provider_seen_at = now
                other_side = "customer"
                other_kind = order.customer_kind
                other_id = order.customer_account_id
            other = await self._profile(session, other_id, other_kind)
            await session.commit()
            public_kind = (
                PublicResultKind.BUSINESS
                if other_kind == "business"
                else PublicResultKind.USER
            )
            return OrderChatRead(
                side=side,
                seen_at=now,
                other={
                    "side": other_side,
                    "kind": other_kind,
                    "public_id": build_public_id(public_kind, other_id),
                    "name": other.name if other else "",
                },
                order=await self._project(session, order, side),
                messages=[
                    await self._project_message(session, row, account_id)
                    for row in rows
                ],
            )

    async def send_message(
        self, *, order_id: int, account_id: int, account_type: AccountType,
        body: OrderMessageCreate,
    ) -> OrderMessageRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            text_value = body.text.strip()
            if body.media_type == "photo":
                text_value = text_value[:1000]
            if body.media_type == "text" and not text_value:
                raise ApiError(400, "order_message_required", "Xabar matni kiritilishi shart.")
            if body.media_type == "photo":
                prefix = f"private/{account_type.value}/{account_id}/order_chat_image/"
                if not body.object_key.startswith(prefix):
                    raise ApiError(400, "order_media_key_invalid", "Rasm kaliti akkauntga tegishli emas.")
            if body.reply_to_id is not None and await self._repository.message(
                session, order_id=order_id, message_id=body.reply_to_id
            ) is None:
                raise ApiError(400, "order_reply_invalid", "Javob berilayotgan xabar topilmadi.")
            now = datetime.now(UTC)
            message = OrderMessage(
                legacy_source_id=None, order_id=order_id,
                sender_account_id=account_id, sender_kind=account_type.value,
                text=text_value, media_type=body.media_type,
                media_object_key=body.object_key if body.media_type == "photo" else "",
                legacy_media_url="", file_name=body.file_name,
                reply_to_id=body.reply_to_id, edited_at=None, deleted_at=None,
                is_deleted=False, created_at=now,
            )
            session.add(message)
            await session.flush()
            order.updated_at = now
            self._changed(order, side, "message", now)
            await self._event(session, "order.message_created", order, account_id, message.id)
            await session.commit()
            return await self._project_message(session, message, account_id)

    async def edit_message(
        self, *, order_id: int, message_id: int, account_id: int,
        account_type: AccountType, text: str,
    ) -> OrderMessageRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            message = await self._repository.message(
                session, order_id=order_id, message_id=message_id, lock=True
            )
            if message is None:
                raise ApiError(404, "order_message_not_found", "Xabar topilmadi.")
            if message.sender_account_id != account_id or message.sender_kind != account_type.value:
                raise ApiError(403, "order_message_owner_required", "Faqat o'zingiz yuborgan xabarni tahrirlashingiz mumkin.")
            if message.is_deleted:
                raise ApiError(400, "order_message_deleted", "O'chirilgan xabarni tahrirlab bo'lmaydi.")
            if not message.text.strip():
                raise ApiError(400, "order_message_text_missing", "Bu xabarda tahrirlanadigan matn yo'q.")
            value = text.strip()[:2000]
            if not value:
                raise ApiError(400, "order_message_edit_required", "Tahrirlash uchun matn kiriting.")
            now = datetime.now(UTC)
            message.text = value
            message.edited_at = now
            order.updated_at = now
            self._changed(order, side, "message_edited", now)
            await self._event(session, "order.message_edited", order, account_id, message.id)
            await session.commit()
            return await self._project_message(session, message, account_id)

    async def delete_message(
        self, *, order_id: int, message_id: int, account_id: int,
        account_type: AccountType,
    ) -> OrderMessageRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            message = await self._repository.message(
                session, order_id=order_id, message_id=message_id, lock=True
            )
            if message is None:
                raise ApiError(404, "order_message_not_found", "Xabar topilmadi.")
            if message.sender_account_id != account_id or message.sender_kind != account_type.value:
                raise ApiError(403, "order_message_owner_required", "Faqat o'zingiz yuborgan xabarni o'chirishingiz mumkin.")
            if not message.is_deleted:
                now = datetime.now(UTC)
                message.is_deleted = True
                message.deleted_at = now
                message.text = ""
                order.updated_at = now
                self._changed(order, side, "message_deleted", now)
                await self._event(session, "order.message_deleted", order, account_id, message.id)
                await session.commit()
            return await self._project_message(session, message, account_id)

    async def _owned(self, session, order_id: int, account_id: int, lock: bool = False):
        order = await self._repository.owned_order(
            session, order_id=order_id, account_id=account_id, lock=lock
        )
        if order is None:
            raise ApiError(404, "order_not_found", "Buyurtma topilmadi.")
        side = "customer" if order.customer_account_id == account_id else "provider"
        return order, side

    async def _resolve_profile_public_id(self, session, kind: str, public_id: str) -> int | None:
        model = BusinessProfile if kind == "business" else UserProfile
        enum_kind = PublicResultKind.BUSINESS if kind == "business" else PublicResultKind.USER
        ids = list((await session.scalars(
            select(model.account_id)
            .join(Account, Account.id == model.account_id)
            .where(
                Account.status == "active",
                Account.account_type == AccountType(kind),
            )
        )).all())
        return next((int(value) for value in ids if build_public_id(enum_kind, int(value)) == public_id), None)

    async def _profile(self, session, account_id: int, kind: str):
        model = BusinessProfile if kind == "business" else UserProfile
        return await session.get(model, account_id)

    async def _resolve_listing(
        self,
        session,
        public_id: str,
        provider_id: int,
        provider_kind: str,
    ) -> Listing | None:
        if not public_id:
            return None
        rows = list((await session.scalars(
            select(Listing).where(
                Listing.status == "active",
                Listing.review_state == ReviewState.READY,
            )
        )).all())
        listing = next(
            (row for row in rows if build_listing_public_id(row.id) == public_id),
            None,
        )
        if listing is None:
            raise ApiError(404, "order_listing_not_found", "E'lon topilmadi.")
        owner_id = (
            listing.owner_business_account_id
            if provider_kind == "business"
            else listing.owner_user_account_id
        )
        if owner_id != provider_id:
            raise ApiError(
                400,
                "order_listing_owner_mismatch",
                (
                    "E'lon bu biznesga tegishli emas."
                    if provider_kind == "business"
                    else "E'lon bu foydalanuvchiga tegishli emas."
                ),
            )
        return listing

    async def _catalog_snapshots(self, session, requested, provider_id: int, provider_kind: str):
        if requested and provider_kind != "business":
            raise ApiError(400, "order_items_business_only", "Mahsulot/xizmatli buyurtma faqat biznesga yuboriladi.")
        all_items = await self._repository.all_catalog_items(session)
        by_public = {
            build_content_public_id(item.kind, item.id): item for item in all_items
        }
        quantities: dict[int, Decimal] = {}
        rows: dict[int, CatalogItem] = {}
        for entry in requested[:50]:
            item = by_public.get(entry.public_id)
            if item is None:
                raise ApiError(404, "order_item_not_found", "Mahsulot/xizmat topilmadi.")
            if item.business_account_id != provider_id:
                raise ApiError(400, "order_item_owner_mismatch", "Mahsulot/xizmat bu biznesga tegishli emas.")
            qty = Decimal(str(entry.qty)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            quantities[item.id] = min(Decimal("999"), quantities.get(item.id, Decimal("0")) + qty)
            rows[item.id] = item
        result = []
        for item_id, qty in quantities.items():
            item = rows[item_id]
            unit = (item.unit or "dona").strip() or "dona"
            if unit not in FRACTIONAL_UNITS:
                qty = max(Decimal("1"), qty.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            price = self._price_to_int(item.price_text)
            result.append({
                "item": item, "name": item.name or "Mahsulot/xizmat",
                "price": item.price_text or "", "qty": qty, "unit": unit,
                "line_total": int((Decimal(price) * qty).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_EVEN,
                )),
                "note": item.note or "", "kind": item.kind,
            })
        return result

    @staticmethod
    def _price_to_int(value: str) -> int:
        digits = re.sub(r"[^0-9]", "", value or "")
        return int(digits[:12]) if digits else 0

    def _changed(self, order: Order, side: str, event: str, now: datetime) -> None:
        order.last_event = event
        if side == "customer":
            order.customer_seen_at = now
            order.provider_seen_at = None
        else:
            order.provider_seen_at = now
            order.customer_seen_at = None

    async def _event(self, session, topic: str, order: Order, actor_id: int, message_id: int | None = None):
        payload = {"order_id": order.id, "actor_account_id": actor_id, "status": order.status}
        if message_id is not None:
            payload["message_id"] = message_id
        await enqueue_event(session, topic, payload)

    async def _project(
        self,
        session,
        order: Order,
        side: str,
        *,
        prefetched_items: list[OrderItem] | None = None,
        prefetched_business: BusinessProfile | None = None,
        business_prefetched: bool = False,
    ) -> OrderRead:
        items = (
            prefetched_items
            if prefetched_items is not None
            else await self._repository.items(session, order.id)
        )
        business = prefetched_business
        if not business_prefetched and order.provider_kind == "business":
            business = await session.get(BusinessProfile, order.provider_account_id)
        customer_kind = (
            PublicResultKind.BUSINESS
            if order.customer_kind == "business"
            else PublicResultKind.USER
        )
        provider_kind = (
            PublicResultKind.BUSINESS
            if order.provider_kind == "business"
            else PublicResultKind.USER
        )
        item_public_id = (
            build_content_public_id(items[0].kind, order.item_id)
            if order.item_id is not None and items
            else ""
        )
        return OrderRead(
            id=order.id, view=side, title=order.title,
            customer_name=order.customer_name,
            customer_public_id=build_public_id(customer_kind, order.customer_account_id),
            provider_name=order.provider_name,
            provider_kind=order.provider_kind, order_type=order.order_type,
            provider_public_id=build_public_id(provider_kind, order.provider_account_id),
            item_public_id=item_public_id,
            listing_public_id=(
                build_listing_public_id(order.listing_id)
                if order.listing_id is not None
                else ""
            ),
            order_category=order.order_category, address=order.address,
            desired_time=order.desired_time, delivery_lat=order.delivery_lat,
            delivery_lng=order.delivery_lng, note=order.note, phone=order.phone,
            qty=float(order.qty), total_amount=order.total_amount,
            total_text=(
                f"{order.total_amount:,}".replace(",", " ") + " so'm"
                if order.total_amount > 0
                else ""
            ),
            status=order.status, payment_status=order.payment_status,
            pay_type=order.pay_type, receipt_message_id=order.receipt_message_id,
            problem_open=order.problem_open, problem_reason=order.problem_reason,
            problem_note=order.problem_note, problem_solution=order.problem_solution,
            problem_opened_at=order.problem_opened_at,
            problem_resolved_at=order.problem_resolved_at,
            seller_completed_at=order.seller_completed_at,
            customer_received_at=order.customer_received_at,
            last_event=order.last_event,
            pay_card=business.pay_card if business else "",
            pay_holder=business.pay_holder if business else "",
            pay_qr_url=self._image_url_provider(business.pay_qr_object_key) if business else "",
            provider_address=business.address if business else "",
            provider_phone=business.phone if business else order.provider_phone,
            provider_work_hours=business.work_hours if business else {},
            provider_lat=business.latitude if business else None,
            provider_lng=business.longitude if business else None,
            customer_seen_at=order.customer_seen_at,
            provider_seen_at=order.provider_seen_at,
            seen_at=order.provider_seen_at if side == "provider" else order.customer_seen_at,
            is_unread=(
                order.provider_seen_at is None
                if side == "provider"
                else order.customer_seen_at is None
            ),
            created_at=order.created_at, updated_at=order.updated_at,
            items=[{
                "id": item.id,
                "public_id": build_content_public_id(item.kind, item.catalog_item_id) if item.catalog_item_id else "",
                "name": item.item_name, "price": item.price_text,
                "qty": float(item.qty), "unit": item.unit,
                "line_total": item.line_total, "note": item.note, "kind": item.kind,
            } for item in items],
        )

    async def _project_message(self, session, message: OrderMessage, account_id: int) -> OrderMessageRead:
        sender = await self._profile(session, message.sender_account_id, message.sender_kind)
        return OrderMessageRead(
            id=message.id, text=message.text, media_type=message.media_type,
            media_url=(self._image_url_provider(message.media_object_key) if message.media_object_key else message.legacy_media_url),
            file_name=message.file_name, reply_to_id=message.reply_to_id,
            edited_at=message.edited_at, deleted_at=message.deleted_at,
            is_deleted=message.is_deleted, mine=message.sender_account_id == account_id,
            sender_name=sender.name if sender else "", sender_kind=message.sender_kind,
            created_at=message.created_at,
        )
