"""Buyurtma ichidagi yozishmalar."""

from __future__ import annotations

from datetime import UTC, datetime

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.orders.model import OrderMessage
from app.orders.schemas import (
    OrderChatRead,
    OrderMessageCreate,
    OrderMessageRead,
)
from app.orders.service_parts.base import OrderServiceBase
from app.public_discovery.repository import build_public_id
from app.public_discovery.schemas import PublicResultKind


class MessagingMixin(OrderServiceBase):
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
            return [
                await self._project_message(session, row, account_id) for row in rows
            ]

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
        self,
        *,
        order_id: int,
        account_id: int,
        account_type: AccountType,
        body: OrderMessageCreate,
    ) -> OrderMessageRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            text_value = body.text.strip()
            if body.media_type == "photo":
                text_value = text_value[:1000]
            if body.media_type == "text" and not text_value:
                raise ApiError(
                    400, "order_message_required", "Xabar matni kiritilishi shart."
                )
            if body.media_type == "photo":
                prefix = f"private/{account_type.value}/{account_id}/order_chat_image/"
                if not body.object_key.startswith(prefix):
                    raise ApiError(
                        400,
                        "order_media_key_invalid",
                        "Rasm kaliti akkauntga tegishli emas.",
                    )
            if (
                body.reply_to_id is not None
                and await self._repository.message(
                    session, order_id=order_id, message_id=body.reply_to_id
                )
                is None
            ):
                raise ApiError(
                    400, "order_reply_invalid", "Javob berilayotgan xabar topilmadi."
                )
            now = datetime.now(UTC)
            message = OrderMessage(
                legacy_source_id=None,
                order_id=order_id,
                sender_account_id=account_id,
                sender_kind=account_type.value,
                text=text_value,
                media_type=body.media_type,
                media_object_key=body.object_key if body.media_type == "photo" else "",
                legacy_media_url="",
                file_name=body.file_name,
                reply_to_id=body.reply_to_id,
                edited_at=None,
                deleted_at=None,
                is_deleted=False,
                created_at=now,
            )
            session.add(message)
            await session.flush()
            order.updated_at = now
            self._changed(order, side, "message", now)
            await self._event(
                session, "order.message_created", order, account_id, message.id
            )
            await session.commit()
            return await self._project_message(session, message, account_id)

    async def edit_message(
        self,
        *,
        order_id: int,
        message_id: int,
        account_id: int,
        account_type: AccountType,
        text: str,
    ) -> OrderMessageRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            message = await self._repository.message(
                session, order_id=order_id, message_id=message_id, lock=True
            )
            if message is None:
                raise ApiError(404, "order_message_not_found", "Xabar topilmadi.")
            if (
                message.sender_account_id != account_id
                or message.sender_kind != account_type.value
            ):
                raise ApiError(
                    403,
                    "order_message_owner_required",
                    "Faqat o'zingiz yuborgan xabarni tahrirlashingiz mumkin.",
                )
            if message.is_deleted:
                raise ApiError(
                    400,
                    "order_message_deleted",
                    "O'chirilgan xabarni tahrirlab bo'lmaydi.",
                )
            if not message.text.strip():
                raise ApiError(
                    400,
                    "order_message_text_missing",
                    "Bu xabarda tahrirlanadigan matn yo'q.",
                )
            value = text.strip()[:2000]
            if not value:
                raise ApiError(
                    400,
                    "order_message_edit_required",
                    "Tahrirlash uchun matn kiriting.",
                )
            now = datetime.now(UTC)
            message.text = value
            message.edited_at = now
            order.updated_at = now
            self._changed(order, side, "message_edited", now)
            await self._event(
                session, "order.message_edited", order, account_id, message.id
            )
            await session.commit()
            return await self._project_message(session, message, account_id)

    async def delete_message(
        self,
        *,
        order_id: int,
        message_id: int,
        account_id: int,
        account_type: AccountType,
    ) -> OrderMessageRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            message = await self._repository.message(
                session, order_id=order_id, message_id=message_id, lock=True
            )
            if message is None:
                raise ApiError(404, "order_message_not_found", "Xabar topilmadi.")
            if (
                message.sender_account_id != account_id
                or message.sender_kind != account_type.value
            ):
                raise ApiError(
                    403,
                    "order_message_owner_required",
                    "Faqat o'zingiz yuborgan xabarni o'chirishingiz mumkin.",
                )
            if not message.is_deleted:
                now = datetime.now(UTC)
                message.is_deleted = True
                message.deleted_at = now
                message.text = ""
                order.updated_at = now
                self._changed(order, side, "message_deleted", now)
                await self._event(
                    session, "order.message_deleted", order, account_id, message.id
                )
                await session.commit()
            return await self._project_message(session, message, account_id)

    async def _project_message(
        self, session, message: OrderMessage, account_id: int
    ) -> OrderMessageRead:
        sender = await self._profile(
            session, message.sender_account_id, message.sender_kind
        )
        reply = None
        if message.reply_to_id is not None:
            reply_message = await self._repository.message(
                session,
                order_id=message.order_id,
                message_id=message.reply_to_id,
            )
            if reply_message is not None:
                reply_sender = await self._profile(
                    session,
                    reply_message.sender_account_id,
                    reply_message.sender_kind,
                )
                reply = {
                    "id": reply_message.id,
                    "text": "" if reply_message.is_deleted else reply_message.text,
                    "media_type": reply_message.media_type,
                    "is_deleted": reply_message.is_deleted,
                    "sender_name": reply_sender.name if reply_sender else "",
                }
        return OrderMessageRead(
            id=message.id,
            text=message.text,
            media_type=message.media_type,
            media_url=(
                self._image_url_provider(message.media_object_key)
                if message.media_object_key
                else message.legacy_media_url
            ),
            file_name=message.file_name,
            reply_to_id=message.reply_to_id,
            reply=reply,
            edited_at=message.edited_at,
            deleted_at=message.deleted_at,
            is_deleted=message.is_deleted,
            mine=message.sender_account_id == account_id,
            sender_name=sender.name if sender else "",
            sender_kind=message.sender_kind,
            created_at=message.created_at,
        )
