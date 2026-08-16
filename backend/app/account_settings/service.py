from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_settings.schemas import (
    BusinessCredentialsRead,
    BusinessCredentialsUpdate,
)
from app.accounts.model import Account, AccountType
from app.auth.security import hash_password
from app.core.errors import ApiError
from app.profiles.model import ProfileLink

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
LOGIN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class AccountSettingsService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def get_business_credentials(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> BusinessCredentialsRead:
        async with self._session_factory() as session:
            business_account_id = await self._resolve_business_account_id(
                session,
                account_id=account_id,
                account_type=account_type,
            )
            account = await self._business_account(session, business_account_id)
            login = account.login
            await session.rollback()
        return BusinessCredentialsRead(login=login)

    async def update_business_credentials(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: BusinessCredentialsUpdate,
    ) -> BusinessCredentialsRead:
        if not body.new_login and not body.new_password:
            raise ApiError(
                400,
                "credentials_change_required",
                "Yangi login yoki parol kiriting.",
            )
        if body.new_login:
            self._validate_login(body.new_login)
        if body.new_password and len(body.new_password) < 4:
            raise ApiError(
                400,
                "password_too_short",
                "Parol kamida 4 belgidan iborat bo‘lsin.",
            )

        async with self._session_factory() as session:
            try:
                business_account_id = await self._resolve_business_account_id(
                    session,
                    account_id=account_id,
                    account_type=account_type,
                )
                account = await self._business_account(
                    session,
                    business_account_id,
                    lock=True,
                )
                if body.new_login:
                    occupied = await session.execute(
                        select(Account.id).where(
                            func.lower(Account.login) == body.new_login,
                            Account.id != account.id,
                        )
                    )
                    if occupied.scalar_one_or_none() is not None:
                        raise ApiError(
                            409,
                            "login_already_exists",
                            "Bu login band. Boshqasini tanlang.",
                        )
                    account.login = body.new_login
                if body.new_password:
                    account.password_hash = hash_password(body.new_password)
                account.updated_at = self._now_provider()
                await session.flush()
                await session.commit()
                return BusinessCredentialsRead(login=account.login)
            except IntegrityError as error:
                await session.rollback()
                raise ApiError(
                    409,
                    "login_already_exists",
                    "Bu login band. Boshqasini tanlang.",
                ) from error
            except Exception:
                await session.rollback()
                raise

    @staticmethod
    async def _resolve_business_account_id(
        session: AsyncSession,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> int:
        if account_type is AccountType.BUSINESS:
            return account_id
        result = await session.execute(
            select(ProfileLink.business_account_id).where(
                ProfileLink.user_account_id == account_id,
            )
        )
        business_account_id = result.scalar_one_or_none()
        if business_account_id is None:
            raise ApiError(
                403,
                "linked_business_required",
                "Bu bo‘lim do‘kon egalari uchun.",
            )
        return business_account_id

    @staticmethod
    async def _business_account(
        session: AsyncSession,
        account_id: int,
        *,
        lock: bool = False,
    ) -> Account:
        statement = select(Account).where(
            Account.id == account_id,
            Account.account_type == AccountType.BUSINESS,
        )
        if lock:
            statement = statement.with_for_update()
        result = await session.execute(statement)
        account = result.scalar_one_or_none()
        if account is None:
            raise ApiError(
                404,
                "business_account_not_found",
                "Biznes akkaunt topilmadi.",
            )
        return account

    @staticmethod
    def _validate_login(login: str) -> None:
        if len(login) < 4 or not LOGIN_PATTERN.fullmatch(login):
            raise ApiError(
                400,
                "invalid_login",
                "Login 4–20 belgi bo‘lsin va kichik harf bilan boshlansin; "
                "faqat a-z, 0-9 va _ ishlating.",
            )
