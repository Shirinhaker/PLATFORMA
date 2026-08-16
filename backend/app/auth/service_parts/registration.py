"""Ro'yxatdan o'tish va Telegram havolasi orqali faollashtirish."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.accounts.repository import (
    create_account,
    find_telegram_account,
)
from app.auth.model import AuthChallenge, PendingRegistration
from app.auth.repository import (
    create_challenge,
    create_pending_registration,
    create_session,
    find_challenge_by_start_token,
)
from app.auth.schemas import (
    Authenticated,
    RegistrationStart,
    RegistrationStarted,
)
from app.auth.security import (
    derive_csrf,
    encrypt_outbox_secret,
    generate_password,
    hash_password,
)
from app.auth.service_parts.base import AuthServiceBase
from app.auth.service_parts.helpers import (
    INVALID_CODE,
    INVALID_CREDENTIALS,
)
from app.core.errors import ApiError
from app.outbox.repository import enqueue_event
from app.profiles.model import BusinessProfile, UserProfile


class RegistrationMixin(AuthServiceBase):
    async def start_registration(
        self,
        data: RegistrationStart,
        now: datetime,
    ) -> RegistrationStarted:
        self._validate_registration(data)
        expires_at = now + timedelta(seconds=self._settings.telegram_link_ttl_seconds)
        async with self._session_factory() as session:
            try:
                pending = await create_pending_registration(
                    session,
                    data,
                    now,
                    expires_at,
                )
                challenge, raw_start_token = await create_challenge(
                    session,
                    purpose="register",
                    pending_registration_id=pending.id,
                    now=now,
                    start_expires_at=expires_at,
                    max_attempts=self._settings.telegram_max_attempts,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        return RegistrationStarted(
            request_id=challenge.id,
            deep_link=self._deep_link(raw_start_token),
            expires_in=self._settings.telegram_link_ttl_seconds,
            resend_after=self._settings.telegram_resend_seconds,
        )

    async def activate_deep_link(
        self,
        start_token: str,
        telegram_user_id: int,
        now: datetime,
    ) -> None:
        async with self._session_factory() as session:
            try:
                challenge = await find_challenge_by_start_token(
                    session,
                    start_token,
                )
                self._require_startable_challenge(challenge, now)
                assert challenge is not None

                if challenge.telegram_user_id is not None:
                    if challenge.telegram_user_id == telegram_user_id:
                        await session.rollback()
                        return
                    raise ApiError(
                        409,
                        "challenge_already_activated",
                        "Tasdiqlash havolasi allaqachon ishlatilgan.",
                    )

                if challenge.purpose == "register":
                    pending = await session.get(
                        PendingRegistration,
                        challenge.pending_registration_id,
                        with_for_update=True,
                    )
                    if (
                        pending is None
                        or pending.verified_at is not None
                        or pending.expires_at <= now
                    ):
                        raise INVALID_CODE
                    existing = await find_telegram_account(
                        session,
                        telegram_user_id,
                        pending.account_type,
                    )
                    if existing is not None:
                        raise ApiError(
                            409,
                            "telegram_account_type_exists",
                            "Bu Telegram akkauntiga ushbu turdagi akkaunt bog‘langan.",
                        )
                elif challenge.purpose == "login":
                    account = await session.get(
                        Account,
                        challenge.account_id,
                        with_for_update=True,
                    )
                    if account is None or account.status != "active":
                        raise INVALID_CREDENTIALS
                    if (
                        account.telegram_user_id is not None
                        and account.telegram_user_id != telegram_user_id
                    ):
                        raise ApiError(
                            409,
                            "telegram_account_mismatch",
                            "Akkaunt boshqa Telegram hisobiga bog‘langan.",
                        )
                    account.telegram_user_id = telegram_user_id
                else:
                    raise INVALID_CODE

                challenge.telegram_user_id = telegram_user_id
                self._issue_code(challenge, now)
                await self._enqueue_code(session, challenge)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def verify_registration(
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
            purpose="register",
        )

    async def _complete_registration(
        self,
        session: AsyncSession,
        challenge: AuthChallenge,
        device_name: str,
        now: datetime,
    ) -> Authenticated:
        pending = await session.get(
            PendingRegistration,
            challenge.pending_registration_id,
            with_for_update=True,
        )
        if (
            pending is None
            or pending.verified_at is not None
            or pending.expires_at <= now
            or challenge.telegram_user_id is None
        ):
            raise INVALID_CODE

        existing = await find_telegram_account(
            session,
            challenge.telegram_user_id,
            pending.account_type,
        )
        if existing is not None:
            raise ApiError(
                409,
                "telegram_account_type_exists",
                "Bu Telegram akkauntiga ushbu turdagi akkaunt bog‘langan.",
            )

        login = await self._generate_unique_login(session, pending.account_type)
        password = generate_password()
        account = await create_account(
            session,
            account_type=pending.account_type,
            login=login,
            password_hash=hash_password(password),
            telegram_user_id=challenge.telegram_user_id,
            now=now,
        )
        data = RegistrationStart.model_validate(pending.payload_json)
        if account.account_type is AccountType.USER:
            session.add(
                UserProfile(
                    account_id=account.id,
                    name=data.name,
                    phone=data.phone,
                )
            )
        else:
            session.add(
                BusinessProfile(
                    account_id=account.id,
                    name=data.name,
                    phone=data.phone,
                    direction=data.direction,
                    address=data.address,
                )
            )

        expires_at = now + timedelta(seconds=self._settings.session_ttl_seconds)
        _, raw_session_token = await create_session(
            session,
            account_id=account.id,
            device_name=device_name[:200],
            now=now,
            expires_at=expires_at,
        )
        encrypted_credentials = encrypt_outbox_secret(
            {"login": login, "password": password},
            self._settings.outbox_encryption_key,
        )
        await enqueue_event(
            session,
            "telegram.credentials.send",
            {
                "account_id": account.id,
                "chat_id": challenge.telegram_user_id,
                "encrypted_credentials": encrypted_credentials,
            },
        )
        pending.verified_at = now
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
            login=login,
            password=password,
        )
