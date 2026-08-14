from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.messages.model import Message, MessageConversation
from app.messages.repository import MessageRepository
from app.messages.schemas import (
    MessageConversationRead,
    MessageCreate,
    MessageEdit,
    MessageImageCreate,
    MessageRead,
    MessageThreadRead,
    MessageUnreadRead,
)
from app.public_ids import build_profile_public_id


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
ImageUrlProvider = Callable[[str], str]
NowProvider = Callable[[], datetime]


def canonical_account_pair(first: int, second: int) -> tuple[int, int]:
    if first == second:
        raise ValueError("same_account")
    return (first, second) if first < second else (second, first)


def message_preview_text(*, text: str, media_type: str, is_deleted: bool) -> str:
    if is_deleted:
        return "Xabar o‘chirildi"
    clean = text.strip()
    if media_type == "photo":
        return clean or "📷 Rasm"
    return clean


class MessageService:
    def __init__(
        self,
        session_factory: SessionFactory,
        image_url_provider: ImageUrlProvider,
        *,
        repository: MessageRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._image_url_provider = image_url_provider
        self._repository = repository or MessageRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def conversations(
        self,
        *,
        account_id: int,
    ) -> list[MessageConversationRead]:
        async with self._session_factory() as session:
            rows = await self._repository.conversations(
                session, account_id=account_id
            )
            ids = [int(row.id) for row in rows]
            latest = await self._repository.latest_messages(session, ids)
            unread = await self._repository.unread_counts(
                session,
                account_id=account_id,
                conversation_ids=ids,
            )
            other_ids = {
                self._other_account_id(row, account_id) for row in rows
            }
            profiles = await self._repository.profiles(session, other_ids)
            result: list[MessageConversationRead] = []
            for row in rows:
                other_id = self._other_account_id(row, account_id)
                profile = profiles.get(other_id)
                last = latest.get(int(row.id))
                if profile is None or last is None:
                    continue
                result.append(MessageConversationRead(
                    target_kind=profile["kind"],
                    target_public_id=self._public_id(profile, other_id),
                    name=str(profile["name"]),
                    avatar_url=self._image_url(profile),
                    last=message_preview_text(
                        text=last.text,
                        media_type=last.media_type,
                        is_deleted=last.is_deleted,
                    ),
                    created_at=last.created_at,
                    unread=unread.get(int(row.id), 0),
                ))
            return result

    async def thread(
        self,
        *,
        account_id: int,
        target_kind: AccountType,
        target_public_id: str,
        before_id: int | None = None,
        limit: int = 100,
    ) -> MessageThreadRead:
        async with self._session_factory() as session:
            target = await self._target(
                session,
                account_id=account_id,
                target_kind=target_kind,
                target_public_id=target_public_id,
            )
            target_id = int(target.account_id)
            low, high = canonical_account_pair(account_id, target_id)
            conversation = await self._repository.conversation_by_pair(
                session,
                low_account_id=low,
                high_account_id=high,
            )
            profile = self._profile_dict(target, target_kind)
            if conversation is None:
                return MessageThreadRead(
                    other=self._profile_read(profile, target_id),
                    messages=[],
                )
            messages = await self._repository.messages(
                session,
                conversation_id=int(conversation.id),
                before_id=before_id,
                limit=limit,
            )
            has_more = len(messages) > limit
            if has_more:
                messages = messages[1:]
            await self._repository.mark_read(
                session,
                conversation_id=int(conversation.id),
                receiver_account_id=account_id,
                now=self._now(),
            )
            projected = await self._project_messages(
                session, messages, account_id=account_id
            )
            await session.commit()
            return MessageThreadRead(
                other=self._profile_read(profile, target_id),
                messages=projected,
                next_cursor=(
                    min(int(row.id) for row in messages)
                    if has_more and messages else None
                ),
            )

    async def send_text(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: MessageCreate,
    ) -> MessageRead:
        return await self._send(
            account_id=account_id,
            account_type=account_type,
            target_kind=body.target_kind,
            target_public_id=body.target_public_id,
            text=body.text,
            media_type="text",
            object_key="",
            file_name="",
            reply_to_id=body.reply_to_id,
        )

    async def send_image(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: MessageImageCreate,
    ) -> MessageRead:
        prefix = f"private/{account_type.value}/{account_id}/chat_image/"
        if not body.object_key.startswith(prefix):
            raise ApiError(
                400,
                "message_media_key_invalid",
                "Rasm kaliti akkauntga tegishli emas.",
            )
        return await self._send(
            account_id=account_id,
            account_type=account_type,
            target_kind=body.target_kind,
            target_public_id=body.target_public_id,
            text=body.text,
            media_type="photo",
            object_key=body.object_key,
            file_name=body.file_name,
            reply_to_id=body.reply_to_id,
        )

    async def edit(
        self,
        *,
        message_id: int,
        account_id: int,
        body: MessageEdit,
    ) -> MessageRead:
        async with self._session_factory() as session:
            message = await self._repository.message(
                session, message_id=message_id, lock=True
            )
            if message is None:
                raise ApiError(404, "message_not_found", "Xabar topilmadi.")
            if int(message.sender_account_id) != account_id:
                raise ApiError(
                    403,
                    "message_owner_required",
                    "Faqat o‘zingiz yuborgan xabarni tahrirlashingiz mumkin.",
                )
            if message.is_deleted:
                raise ApiError(
                    400,
                    "message_deleted",
                    "O‘chirilgan xabarni tahrirlab bo‘lmaydi.",
                )
            if not message.text.strip():
                raise ApiError(
                    400,
                    "message_text_missing",
                    "Bu xabarda tahrirlanadigan matn yo‘q.",
                )
            message.text = body.text
            message.edited_at = self._now()
            message.read_at = None
            conversation = await session.get(
                MessageConversation, message.conversation_id
            )
            if conversation is not None:
                conversation.updated_at = message.edited_at
            await session.commit()
            return (await self._project_messages(
                session, [message], account_id=account_id
            ))[0]

    async def delete(
        self,
        *,
        message_id: int,
        account_id: int,
    ) -> MessageRead:
        async with self._session_factory() as session:
            message = await self._repository.message(
                session, message_id=message_id, lock=True
            )
            if message is None:
                raise ApiError(404, "message_not_found", "Xabar topilmadi.")
            if int(message.sender_account_id) != account_id:
                raise ApiError(
                    403,
                    "message_owner_required",
                    "Faqat o‘zingiz yuborgan xabarni o‘chirishingiz mumkin.",
                )
            if not message.is_deleted:
                now = self._now()
                message.is_deleted = True
                message.deleted_at = now
                message.text = ""
                message.read_at = None
                conversation = await session.get(
                    MessageConversation, message.conversation_id
                )
                if conversation is not None:
                    conversation.updated_at = now
                await session.commit()
            return (await self._project_messages(
                session, [message], account_id=account_id
            ))[0]

    async def unread_count(self, *, account_id: int) -> MessageUnreadRead:
        async with self._session_factory() as session:
            return MessageUnreadRead(count=await self._repository.unread_count(
                session, account_id=account_id
            ))

    async def _send(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        target_kind: AccountType,
        target_public_id: str,
        text: str,
        media_type: str,
        object_key: str,
        file_name: str,
        reply_to_id: int | None,
    ) -> MessageRead:
        async with self._session_factory() as session:
            target = await self._target(
                session,
                account_id=account_id,
                target_kind=target_kind,
                target_public_id=target_public_id,
            )
            target_id = int(target.account_id)
            low, high = canonical_account_pair(account_id, target_id)
            now = self._now()
            conversation = await self._repository.ensure_conversation(
                session,
                low_account_id=low,
                high_account_id=high,
                now=now,
            )
            if reply_to_id is not None:
                reply = await self._repository.message(
                    session,
                    message_id=reply_to_id,
                    conversation_id=int(conversation.id),
                )
                if reply is None:
                    raise ApiError(
                        400,
                        "message_reply_invalid",
                        "Javob berilayotgan xabar topilmadi.",
                    )
            message = Message(
                legacy_source_id=None,
                conversation_id=int(conversation.id),
                sender_account_id=account_id,
                receiver_account_id=target_id,
                text=text,
                media_type=media_type,
                media_object_key=object_key,
                legacy_media_url="",
                file_name=file_name,
                reply_to_id=reply_to_id,
                edited_at=None,
                deleted_at=None,
                read_at=None,
                is_deleted=False,
                created_at=now,
            )
            session.add(message)
            await session.flush()
            conversation.updated_at = now
            await session.commit()
            return (await self._project_messages(
                session, [message], account_id=account_id
            ))[0]

    async def _target(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        target_kind: AccountType,
        target_public_id: str,
    ):
        target = await self._repository.profile_by_public_id(
            session,
            kind=target_kind,
            public_id=target_public_id,
        )
        if target is None:
            raise ApiError(404, "message_target_not_found", "Qabul qiluvchi topilmadi.")
        if int(target.account_id) == account_id:
            raise ApiError(
                400,
                "message_self_forbidden",
                "O‘zingizga xabar yubora olmaysiz.",
            )
        return target

    async def _project_messages(
        self,
        session: AsyncSession,
        messages: list[Message],
        *,
        account_id: int,
    ) -> list[MessageRead]:
        reply_ids = {
            int(row.reply_to_id) for row in messages if row.reply_to_id is not None
        }
        replies = await self._repository.messages_by_ids(session, reply_ids)
        account_ids = {
            int(row.sender_account_id) for row in messages
        } | {
            int(row.sender_account_id) for row in replies.values()
        }
        profiles = await self._repository.profiles(session, account_ids)
        result: list[MessageRead] = []
        for row in messages:
            sender = profiles.get(int(row.sender_account_id), {})
            reply = replies.get(int(row.reply_to_id or 0))
            reply_read = None
            if reply is not None:
                reply_sender = profiles.get(int(reply.sender_account_id), {})
                reply_read = {
                    "id": int(reply.id),
                    "text": "" if reply.is_deleted else reply.text,
                    "media_type": reply.media_type,
                    "is_deleted": reply.is_deleted,
                    "sender_name": str(reply_sender.get("name") or ""),
                }
            kind = sender.get("kind")
            if not isinstance(kind, AccountType):
                kind = AccountType.USER
            result.append(MessageRead(
                id=int(row.id),
                text=row.text,
                media_type=row.media_type,
                media_url=(
                    self._image_url_provider(row.media_object_key)
                    if row.media_object_key
                    else row.legacy_media_url
                ),
                file_name=row.file_name,
                reply_to_id=row.reply_to_id,
                reply=reply_read,
                edited_at=row.edited_at,
                deleted_at=row.deleted_at,
                is_deleted=row.is_deleted,
                mine=int(row.sender_account_id) == account_id,
                sender_name=str(sender.get("name") or ""),
                sender_kind=kind,
                created_at=row.created_at,
            ))
        return result

    @staticmethod
    def _other_account_id(conversation, account_id: int) -> int:
        return int(
            conversation.high_account_id
            if int(conversation.low_account_id) == account_id
            else conversation.low_account_id
        )

    @staticmethod
    def _profile_dict(profile, kind: AccountType) -> dict[str, object]:
        return {
            "kind": kind,
            "public_id": profile.public_id or "",
            "name": profile.name or "",
            "image_object_key": (
                profile.logo_object_key
                if kind is AccountType.BUSINESS
                else profile.avatar_object_key
            ) or "",
        }

    def _profile_read(self, profile: dict[str, object], account_id: int):
        return {
            "kind": profile["kind"],
            "public_id": self._public_id(profile, account_id),
            "name": str(profile["name"]),
            "avatar_url": self._image_url(profile),
        }

    @staticmethod
    def _public_id(profile: dict[str, object], account_id: int) -> str:
        value = str(profile.get("public_id") or "")
        kind = profile.get("kind")
        return value or build_profile_public_id(
            kind.value if isinstance(kind, AccountType) else "user",
            account_id,
        )

    def _image_url(self, profile: dict[str, object]) -> str:
        key = str(profile.get("image_object_key") or "")
        return self._image_url_provider(key) if key else ""

    def _now(self) -> datetime:
        value = self._now_provider()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
