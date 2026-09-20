"""Umumiy asos: bog'liqliklar, kod yuborish, tekshiruv qoidalari."""

from __future__ import annotations

import asyncio
import hmac
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.accounts.repository import (
    find_account_by_login,
)
from app.auth.model import AuthChallenge, PendingRegistration
from app.auth.repository import (
    lock_challenge,
)
from app.auth.schemas import (
    Authenticated,
    RegistrationStart,
    SessionIdentity,
)
from app.auth.security import (
    derive_otp,
    generate_login,
    sha256_token,
)
from app.auth.service_parts.helpers import (
    INVALID_CODE,
    SessionFactory,
)
from app.core.config import Settings
from app.core.errors import ApiError
from app.outbox.repository import enqueue_event


class AuthServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        redis: Any,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._settings = settings
        self._session_resolution_tasks: dict[
            str,
            asyncio.Task[SessionIdentity | None],
        ] = {}

    async def _verify_challenge(
        self,
        request_id: int,
        code: str,
        device_name: str,
        now: datetime,
        *,
        purpose: str,
    ) -> Authenticated:
        async with self._session_factory() as session:
            try:
                challenge = await lock_challenge(session, request_id)
                self._require_verifiable_challenge(challenge, now)
                assert challenge is not None
                if challenge.purpose != purpose:
                    raise INVALID_CODE

                submitted_hash = sha256_token(code)
                if not hmac.compare_digest(
                    challenge.code_hash or "",
                    submitted_hash,
                ):
                    challenge.attempts += 1
                    if challenge.attempts >= challenge.max_attempts:
                        challenge.invalidated_at = now
                        await session.commit()
                        raise self._challenge_locked()
                    await session.commit()
                    raise INVALID_CODE

                if purpose == "register":
                    result = await self._complete_registration(
                        session,
                        challenge,
                        device_name,
                        now,
                    )
                else:
                    result = await self._complete_login(
                        session,
                        challenge,
                        device_name,
                        now,
                    )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        await self._cache_authenticated_session(result, now)
        return result

    async def _generate_unique_login(
        self,
        session: AsyncSession,
        account_type: AccountType,
    ) -> str:
        for _ in range(20):
            candidate = generate_login(account_type)
            if await find_account_by_login(session, candidate) is None:
                return candidate
        raise ApiError(
            503,
            "login_generation_failed",
            "Yangi login yaratib bo‘lmadi. Qayta urinib ko‘ring.",
        )

    def _issue_code(
        self,
        challenge: AuthChallenge,
        now: datetime,
    ) -> None:
        code = derive_otp(
            challenge.id,
            challenge.code_version,
            self._settings.otp_secret,
        )
        challenge.code_hash = sha256_token(code)
        challenge.code_sent_at = now
        challenge.code_expires_at = now + timedelta(
            seconds=self._settings.telegram_code_ttl_seconds
        )

    async def _enqueue_code(
        self,
        session: AsyncSession,
        challenge: AuthChallenge,
    ) -> None:
        if challenge.purpose == "register":
            pending = await session.get(
                PendingRegistration,
                challenge.pending_registration_id,
                with_for_update=True,
            )
            assert challenge.code_sent_at is not None
            assert challenge.code_expires_at is not None
            if (
                pending is None
                or pending.verified_at is not None
                or pending.expires_at <= challenge.code_sent_at
            ):
                raise INVALID_CODE
            # Yangi kod amal qilayotganida forma eskirib qolmasin.
            pending.expires_at = max(pending.expires_at, challenge.code_expires_at)
        await enqueue_event(
            session,
            "telegram.auth_code.send",
            {
                "challenge_id": challenge.id,
                "code_version": challenge.code_version,
                "chat_id": challenge.telegram_user_id,
            },
        )

    def _deep_link(self, raw_start_token: str) -> str:
        return (
            f"https://t.me/{self._settings.telegram_bot_username}"
            f"?start={raw_start_token}"
        )

    @staticmethod
    def _validate_registration(data: RegistrationStart) -> None:
        if data.account_type is AccountType.BUSINESS and (
            not data.direction.strip() or not data.address.strip()
        ):
            raise ApiError(
                422,
                "business_fields_required",
                "Biznes yo‘nalishi va manzili majburiy.",
            )

    @staticmethod
    def _require_startable_challenge(
        challenge: AuthChallenge | None,
        now: datetime,
    ) -> None:
        if (
            challenge is None
            or challenge.verified_at is not None
            or challenge.invalidated_at is not None
            or challenge.start_expires_at <= now
        ):
            raise ApiError(
                400,
                "invalid_start_token",
                "Telegram tasdiqlash havolasi noto‘g‘ri yoki muddati tugagan.",
            )

    @classmethod
    def _require_verifiable_challenge(
        cls,
        challenge: AuthChallenge | None,
        now: datetime,
        *,
        allow_expired: bool = False,
    ) -> None:
        if challenge is None or challenge.verified_at is not None:
            raise INVALID_CODE
        if (
            challenge.invalidated_at is not None
            or challenge.attempts >= challenge.max_attempts
        ):
            raise cls._challenge_locked()
        if not allow_expired and (
            challenge.code_hash is None
            or challenge.code_expires_at is None
            or challenge.code_expires_at <= now
        ):
            raise INVALID_CODE

    @staticmethod
    def _challenge_locked() -> ApiError:
        return ApiError(
            423,
            "challenge_locked",
            "Tasdiqlash urinishlari tugadi. Yangi jarayonni boshlang.",
        )
