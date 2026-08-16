"""Kirish: kod yuborish va tasdiqlash."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account
from app.accounts.repository import (
    find_account_by_login,
)
from app.auth.model import AuthChallenge
from app.auth.repository import (
    create_challenge,
    create_session,
    lock_challenge,
)
from app.auth.schemas import (
    Authenticated,
    ChallengeResent,
    LoginStarted,
)
from app.auth.security import (
    PasswordVerification,
    derive_csrf,
    verify_password_with_rehash,
)
from app.auth.service_parts.base import AuthServiceBase
from app.auth.service_parts.helpers import (
    INVALID_CREDENTIALS,
)
from app.core.errors import ApiError


class LoginMixin(AuthServiceBase):
    async def start_login(
        self,
        login: str,
        password: str,
        now: datetime,
    ) -> LoginStarted:
        normalized_login = login.strip().lower()
        async with self._session_factory() as session:
            try:
                account = await find_account_by_login(session, normalized_login)
                password_check = (
                    verify_password_with_rehash(
                        account.password_hash,
                        password,
                    )
                    if account is not None and account.status == "active"
                    else PasswordVerification(False)
                )
                if not password_check.valid:
                    raise INVALID_CREDENTIALS
                if password_check.replacement_hash:
                    account.password_hash = password_check.replacement_hash

                challenge, raw_start_token = await create_challenge(
                    session,
                    purpose="login",
                    account_id=account.id,
                    now=now,
                    start_expires_at=now
                    + timedelta(seconds=self._settings.telegram_link_ttl_seconds),
                    max_attempts=self._settings.telegram_max_attempts,
                )
                code_sent = account.telegram_user_id is not None
                if account.telegram_user_id is not None:
                    challenge.telegram_user_id = account.telegram_user_id
                    self._issue_code(challenge, now)
                    await self._enqueue_code(session, challenge)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        return LoginStarted(
            request_id=challenge.id,
            deep_link=self._deep_link(raw_start_token),
            code_sent=code_sent,
            expires_in=(
                self._settings.telegram_code_ttl_seconds
                if code_sent
                else self._settings.telegram_link_ttl_seconds
            ),
            resend_after=self._settings.telegram_resend_seconds,
        )

    async def resend_challenge(
        self,
        request_id: int,
        now: datetime,
    ) -> ChallengeResent:
        async with self._session_factory() as session:
            try:
                challenge = await lock_challenge(session, request_id)
                self._require_verifiable_challenge(
                    challenge,
                    now,
                    allow_expired=True,
                )
                assert challenge is not None
                if challenge.telegram_user_id is None:
                    raise ApiError(
                        409,
                        "telegram_not_activated",
                        "Avval Telegram orqali tasdiqlashni boshlang.",
                    )
                if (
                    challenge.code_sent_at is not None
                    and challenge.code_sent_at
                    + timedelta(seconds=self._settings.telegram_resend_seconds)
                    > now
                ):
                    raise ApiError(
                        429,
                        "resend_too_soon",
                        "Yangi kod yuborish uchun biroz kuting.",
                    )

                challenge.code_version += 1
                challenge.attempts = 0
                self._issue_code(challenge, now)
                await self._enqueue_code(session, challenge)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        return ChallengeResent(
            request_id=challenge.id,
            code_version=challenge.code_version,
            expires_in=self._settings.telegram_code_ttl_seconds,
            resend_after=self._settings.telegram_resend_seconds,
        )

    async def verify_login(
        self,
        request_id: int,
        code: str,
        device_name: str,
        now: datetime,
    ) -> Authenticated:
        return await self._verify_challenge(
            request_id,
            code,
            device_name,
            now,
            purpose="login",
        )

    async def _complete_login(
        self,
        session: AsyncSession,
        challenge: AuthChallenge,
        device_name: str,
        now: datetime,
    ) -> Authenticated:
        account = await session.get(
            Account,
            challenge.account_id,
            with_for_update=True,
        )
        if account is None or account.status != "active":
            raise INVALID_CREDENTIALS
        expires_at = now + timedelta(seconds=self._settings.session_ttl_seconds)
        _, raw_session_token = await create_session(
            session,
            account_id=account.id,
            device_name=device_name[:200],
            now=now,
            expires_at=expires_at,
        )
        challenge.verified_at = now
        return Authenticated(
            account_id=account.id,
            account_type=account.account_type,
            session_token=raw_session_token,
            csrf_token=derive_csrf(
                raw_session_token,
                self._settings.csrf_secret,
            ),
            expires_at=expires_at,
            login=account.login,
        )
