from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.messages.model import (
    Message,
    MessageConversation,
    MessageConversationMember,
)
from app.profiles.model import BusinessProfile, UserProfile


class MessageRepository:
    async def profile_by_public_id(
        self,
        session: AsyncSession,
        *,
        kind: AccountType,
        public_id: str,
    ) -> BusinessProfile | UserProfile | None:
        model = BusinessProfile if kind is AccountType.BUSINESS else UserProfile
        return await session.scalar(
            select(model)
            .join(Account, Account.id == model.account_id)
            .where(
                model.public_id == public_id,
                Account.account_type == kind,
                Account.status == "active",
            )
            .limit(1)
        )

    async def profiles(
        self,
        session: AsyncSession,
        account_ids: set[int],
    ) -> dict[int, dict[str, object]]:
        if not account_ids:
            return {}
        result: dict[int, dict[str, object]] = {}
        for model, kind, image_field in (
            (UserProfile, AccountType.USER, "avatar_object_key"),
            (BusinessProfile, AccountType.BUSINESS, "logo_object_key"),
        ):
            rows = list((await session.scalars(
                select(model).where(model.account_id.in_(account_ids))
            )).all())
            for profile in rows:
                result[int(profile.account_id)] = {
                    "kind": kind,
                    "public_id": profile.public_id or "",
                    "name": profile.name or "",
                    "image_object_key": getattr(profile, image_field) or "",
                }
        return result

    async def ensure_conversation(
        self,
        session: AsyncSession,
        *,
        low_account_id: int,
        high_account_id: int,
        now: datetime,
    ) -> MessageConversation:
        statement = (
            postgresql_insert(MessageConversation)
            .values(
                low_account_id=low_account_id,
                high_account_id=high_account_id,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    MessageConversation.low_account_id,
                    MessageConversation.high_account_id,
                ]
            )
            .returning(MessageConversation.id)
        )
        conversation_id = await session.scalar(statement)
        if conversation_id is None:
            conversation_id = await session.scalar(
                select(MessageConversation.id).where(
                    MessageConversation.low_account_id == low_account_id,
                    MessageConversation.high_account_id == high_account_id,
                )
            )
        if conversation_id is None:
            raise RuntimeError("message_conversation_create_failed")
        await session.execute(
            postgresql_insert(MessageConversationMember)
            .values([
                {
                    "conversation_id": int(conversation_id),
                    "account_id": low_account_id,
                    "joined_at": now,
                },
                {
                    "conversation_id": int(conversation_id),
                    "account_id": high_account_id,
                    "joined_at": now,
                },
            ])
            .on_conflict_do_nothing(
                index_elements=[
                    MessageConversationMember.conversation_id,
                    MessageConversationMember.account_id,
                ]
            )
        )
        conversation = await session.get(MessageConversation, int(conversation_id))
        if conversation is None:
            raise RuntimeError("message_conversation_load_failed")
        return conversation

    async def conversation_by_pair(
        self,
        session: AsyncSession,
        *,
        low_account_id: int,
        high_account_id: int,
    ) -> MessageConversation | None:
        return await session.scalar(
            select(MessageConversation).where(
                MessageConversation.low_account_id == low_account_id,
                MessageConversation.high_account_id == high_account_id,
            )
        )

    async def conversations(
        self,
        session: AsyncSession,
        *,
        account_id: int,
    ) -> list[MessageConversation]:
        return list((await session.scalars(
            select(MessageConversation)
            .join(
                MessageConversationMember,
                MessageConversationMember.conversation_id
                == MessageConversation.id,
            )
            .where(MessageConversationMember.account_id == account_id)
            .order_by(
                MessageConversation.updated_at.desc(),
                MessageConversation.id.desc(),
            )
            .limit(200)
        )).all())

    async def latest_messages(
        self,
        session: AsyncSession,
        conversation_ids: list[int],
    ) -> dict[int, Message]:
        if not conversation_ids:
            return {}
        rows = list((await session.scalars(
            select(Message)
            .where(Message.conversation_id.in_(conversation_ids))
            .distinct(Message.conversation_id)
            .order_by(
                Message.conversation_id,
                Message.created_at.desc(),
                Message.id.desc(),
            )
        )).all())
        return {int(row.conversation_id): row for row in rows}

    async def unread_counts(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        conversation_ids: list[int],
    ) -> dict[int, int]:
        if not conversation_ids:
            return {}
        rows = (await session.execute(
            select(Message.conversation_id, func.count(Message.id))
            .where(
                Message.conversation_id.in_(conversation_ids),
                Message.receiver_account_id == account_id,
                Message.read_at.is_(None),
            )
            .group_by(Message.conversation_id)
        )).all()
        return {int(conversation_id): int(count) for conversation_id, count in rows}

    async def messages(
        self,
        session: AsyncSession,
        *,
        conversation_id: int,
        before_id: int | None = None,
        limit: int = 100,
    ) -> list[Message]:
        statement = select(Message).where(
            Message.conversation_id == conversation_id
        )
        if before_id is not None:
            statement = statement.where(Message.id < before_id)
        rows = list((await session.scalars(
            statement.order_by(Message.id.desc()).limit(limit + 1)
        )).all())
        rows.reverse()
        return rows

    async def messages_by_ids(
        self,
        session: AsyncSession,
        message_ids: set[int],
    ) -> dict[int, Message]:
        if not message_ids:
            return {}
        rows = list((await session.scalars(
            select(Message).where(Message.id.in_(message_ids))
        )).all())
        return {int(row.id): row for row in rows}

    async def message(
        self,
        session: AsyncSession,
        *,
        message_id: int,
        conversation_id: int | None = None,
        lock: bool = False,
    ) -> Message | None:
        statement = select(Message).where(Message.id == message_id)
        if conversation_id is not None:
            statement = statement.where(
                Message.conversation_id == conversation_id
            )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def mark_read(
        self,
        session: AsyncSession,
        *,
        conversation_id: int,
        receiver_account_id: int,
        now: datetime,
    ) -> None:
        await session.execute(
            update(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.receiver_account_id == receiver_account_id,
                Message.read_at.is_(None),
            )
            .values(read_at=now)
        )

    async def unread_count(
        self,
        session: AsyncSession,
        *,
        account_id: int,
    ) -> int:
        value = await session.scalar(
            select(func.count(Message.id)).where(
                Message.receiver_account_id == account_id,
                Message.read_at.is_(None),
            )
        )
        return int(value or 0)
