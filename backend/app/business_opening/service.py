from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.accounts.repository import create_account, find_account_by_login
from app.auth.security import (
    encrypt_outbox_secret,
    generate_login,
    generate_password,
    hash_password,
)
from app.business_opening.schemas import BusinessOpeningRead, BusinessOpeningWrite
from app.core.config import Settings
from app.core.errors import ApiError
from app.outbox.repository import enqueue_event
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]


class BusinessOpeningService:
    def __init__(
        self,
        session_factory: SessionFactory,
        settings: Settings,
        *,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def open_business(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: BusinessOpeningWrite,
    ) -> BusinessOpeningRead:
        if account_type is not AccountType.USER:
            raise ApiError(
                403,
                "user_account_required",
                "Biznes faqat foydalanuvchi kabinetidan ochiladi.",
            )
        if not body.name:
            raise ApiError(
                400,
                "business_name_required",
                "Biznes nomi kiritilishi shart.",
            )

        async with self._session_factory() as session:
            try:
                owner = await self._lock_owner(session, account_id)
                profile = await self._lock_user_profile(session, account_id)
                if profile.has_business or await self._has_link(session, account_id):
                    raise ApiError(
                        400,
                        "business_already_exists",
                        "Sizda allaqachon biznes profil bor.",
                    )
                if owner.telegram_user_id is None:
                    raise ApiError(
                        409,
                        "telegram_account_required",
                        "Biznes ochish uchun Telegram akkaunti bog‘langan bo‘lishi kerak.",
                    )

                login = await self._generate_unique_login(session)
                password = generate_password()
                now = self._now_provider()
                business = await create_account(
                    session,
                    account_type=AccountType.BUSINESS,
                    login=login,
                    password_hash=hash_password(password),
                    telegram_user_id=owner.telegram_user_id,
                    now=now,
                )
                session.add(
                    BusinessProfile(
                        account_id=business.id,
                        name=body.name,
                        direction=body.direction,
                        activity_type=body.activity_type,
                        phone=body.phone,
                        address=body.address,
                    )
                )
                session.add(
                    ProfileLink(
                        user_account_id=account_id,
                        business_account_id=business.id,
                        created_at=now,
                    )
                )
                profile.has_business = True

                encrypted_credentials = encrypt_outbox_secret(
                    {"login": login, "password": password},
                    self._settings.outbox_encryption_key,
                )
                await enqueue_event(
                    session,
                    "telegram.business_credentials.send",
                    {
                        "account_id": business.id,
                        "chat_id": owner.telegram_user_id,
                        "encrypted_credentials": encrypted_credentials,
                    },
                )
                await session.flush()
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise ApiError(
                    400,
                    "business_already_exists",
                    "Sizda allaqachon biznes profil bor.",
                ) from error
            except Exception:
                await session.rollback()
                raise

        return BusinessOpeningRead(
            business_account_id=business.id,
            biz_login=login,
            biz_password=password,
        )

    @staticmethod
    async def _lock_owner(session: AsyncSession, account_id: int) -> Account:
        result = await session.execute(
            select(Account)
            .where(
                Account.id == account_id,
                Account.account_type == AccountType.USER,
                Account.status == "active",
            )
            .with_for_update()
        )
        owner = result.scalar_one_or_none()
        if owner is None:
            raise ApiError(
                404,
                "user_account_not_found",
                "Foydalanuvchi akkaunti topilmadi.",
            )
        return owner

    @staticmethod
    async def _lock_user_profile(
        session: AsyncSession,
        account_id: int,
    ) -> UserProfile:
        result = await session.execute(
            select(UserProfile)
            .where(UserProfile.account_id == account_id)
            .with_for_update()
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ApiError(
                404,
                "user_profile_not_found",
                "Foydalanuvchi profili topilmadi.",
            )
        return profile

    @staticmethod
    async def _has_link(session: AsyncSession, account_id: int) -> bool:
        result = await session.execute(
            select(ProfileLink.user_account_id).where(
                ProfileLink.user_account_id == account_id,
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def _generate_unique_login(session: AsyncSession) -> str:
        for _ in range(20):
            candidate = generate_login(AccountType.BUSINESS)
            if await find_account_by_login(session, candidate) is None:
                return candidate
        raise ApiError(
            503,
            "login_generation_failed",
            "Yangi login yaratib bo‘lmadi. Qayta urinib ko‘ring.",
        )
