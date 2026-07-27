import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
import hmac
import json
import logging
import math
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.accounts.repository import (
    create_account,
    find_account_by_login,
    find_telegram_account,
)
from app.auth.model import AuthChallenge, PendingRegistration
from app.auth.repository import (
    create_challenge,
    create_pending_registration,
    create_session,
    find_challenge_by_start_token,
    lock_challenge,
    lock_session,
    resolve_session as resolve_stored_session,
)
from app.auth.schemas import (
    Authenticated,
    ChallengeResent,
    LoginStarted,
    RegistrationStart,
    RegistrationStarted,
    SessionIdentity,
)
from app.auth.security import (
    derive_csrf,
    derive_otp,
    encrypt_outbox_secret,
    generate_login,
    generate_password,
    hash_password,
    sha256_token,
    verify_password,
)
from app.core.config import Settings
from app.core.errors import ApiError
from app.outbox.repository import enqueue_event
from app.profiles.model import BusinessProfile, UserProfile


SessionFactory = Callable[
    [],
    AbstractAsyncContextManager[AsyncSession],
]

logger = logging.getLogger(__name__)
_CACHE_MISS = object()
_SESSION_CACHE_PREFIX = "auth:session:v1:"
_SESSION_REVOKED_PREFIX = "auth:session:revoked:v1:"
_CACHE_SESSION_SCRIPT = """
if redis.call('EXISTS', KEYS[2]) == 1 then
  return 0
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""
_REVOKE_CACHED_SESSION_SCRIPT = """
redis.call('SET', KEYS[1], '1', 'EX', ARGV[1])
redis.call('DEL', KEYS[2])
return 1
"""

INVALID_CREDENTIALS = ApiError(
    401,
    "invalid_credentials",
    "Login yoki parol noto‘g‘ri.",
)
INVALID_CODE = ApiError(
    400,
    "invalid_code",
    "Tasdiqlash kodi noto‘g‘ri yoki muddati tugagan.",
)


class AuthService:
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

    async def start_registration(
        self,
        data: RegistrationStart,
        now: datetime,
    ) -> RegistrationStarted:
        self._validate_registration(data)
        expires_at = now + timedelta(
            seconds=self._settings.telegram_link_ttl_seconds
        )
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
                if (
                    account is None
                    or account.status != "active"
                    or not verify_password(account.password_hash, password)
                ):
                    raise INVALID_CREDENTIALS

                challenge, raw_start_token = await create_challenge(
                    session,
                    purpose="login",
                    account_id=account.id,
                    now=now,
                    start_expires_at=now
                    + timedelta(
                        seconds=self._settings.telegram_link_ttl_seconds
                    ),
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

    async def resolve_session(
        self,
        raw_token: str,
        now: datetime,
    ) -> SessionIdentity | None:
        cached = await self._read_cached_session(raw_token, now)
        if cached is not _CACHE_MISS:
            return cached

        cache_key = self._session_cache_key(raw_token)
        task = self._session_resolution_tasks.get(cache_key)
        if task is None:
            task = asyncio.create_task(
                self._resolve_session_from_database(raw_token, now)
            )
            self._session_resolution_tasks[cache_key] = task

            def clear_completed(completed):
                if self._session_resolution_tasks.get(cache_key) is completed:
                    self._session_resolution_tasks.pop(cache_key, None)

            task.add_done_callback(clear_completed)
        return await asyncio.shield(task)

    async def _resolve_session_from_database(
        self,
        raw_token: str,
        now: datetime,
    ) -> SessionIdentity | None:
        async with self._session_factory() as session:
            stored = await resolve_stored_session(session, raw_token, now)
            if stored is None:
                await session.rollback()
                return None
            auth_session, account = stored
            identity = SessionIdentity(
                account_id=account.id,
                account_type=account.account_type,
                login=account.login,
                csrf_token=derive_csrf(
                    raw_token,
                    self._settings.csrf_secret,
                ),
                expires_at=auth_session.expires_at,
            )
            if auth_session.last_used_at <= now - timedelta(minutes=5):
                auth_session.last_used_at = now
                await session.commit()
            else:
                await session.rollback()
        await self._cache_session(raw_token, identity, now)
        return identity

    async def revoke_session(
        self,
        raw_token: str,
        now: datetime,
    ) -> None:
        async with self._session_factory() as session:
            try:
                auth_session = await lock_session(session, raw_token)
                if auth_session is not None and auth_session.revoked_at is None:
                    auth_session.revoked_at = now
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        await self._revoke_cached_session(raw_token)

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

    async def _cache_authenticated_session(
        self,
        authenticated: Authenticated,
        now: datetime,
    ) -> None:
        if authenticated.login is None:
            return
        await self._cache_session(
            authenticated.session_token,
            SessionIdentity(
                account_id=authenticated.account_id,
                account_type=authenticated.account_type,
                login=authenticated.login,
                csrf_token=authenticated.csrf_token,
                expires_at=authenticated.expires_at,
            ),
            now,
        )

    async def _read_cached_session(
        self,
        raw_token: str,
        now: datetime,
    ) -> SessionIdentity | None | object:
        redis = self._redis_connection()
        if redis is None:
            return _CACHE_MISS

        cache_key = self._session_cache_key(raw_token)
        revoked_key = self._session_revoked_key(raw_token)
        try:
            payload, revoked = await redis.mget(cache_key, revoked_key)
        except Exception:
            logger.warning("Session cache read failed; using database.")
            return _CACHE_MISS

        if revoked is not None:
            return None
        if payload is None:
            return _CACHE_MISS

        try:
            cached = json.loads(payload)
            cached["csrf_token"] = derive_csrf(
                raw_token,
                self._settings.csrf_secret,
            )
            identity = SessionIdentity.model_validate(cached)
        except (TypeError, ValueError, json.JSONDecodeError):
            try:
                await redis.delete(cache_key)
            except Exception:
                pass
            return _CACHE_MISS

        if identity.expires_at <= now:
            try:
                await redis.delete(cache_key)
            except Exception:
                pass
            return None
        return identity

    async def _cache_session(
        self,
        raw_token: str,
        identity: SessionIdentity,
        now: datetime,
    ) -> None:
        redis = self._redis_connection()
        if redis is None:
            return

        remaining_seconds = math.ceil(
            (identity.expires_at - now).total_seconds()
        )
        if remaining_seconds <= 0:
            return
        ttl_seconds = min(
            self._settings.session_cache_ttl_seconds,
            remaining_seconds,
        )
        payload = json.dumps(
            identity.model_dump(
                mode="json",
                exclude={"csrf_token"},
            ),
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            await redis.eval(
                _CACHE_SESSION_SCRIPT,
                2,
                self._session_cache_key(raw_token),
                self._session_revoked_key(raw_token),
                payload,
                ttl_seconds,
            )
        except Exception:
            logger.warning("Session cache write failed; continuing without cache.")

    async def _revoke_cached_session(self, raw_token: str) -> None:
        redis = self._redis_connection()
        if redis is None:
            return
        revoked_ttl_seconds = max(
            60,
            self._settings.session_cache_ttl_seconds * 2,
        )
        try:
            await redis.eval(
                _REVOKE_CACHED_SESSION_SCRIPT,
                2,
                self._session_revoked_key(raw_token),
                self._session_cache_key(raw_token),
                revoked_ttl_seconds,
            )
        except Exception:
            logger.warning(
                "Session cache invalidation failed; database session is revoked."
            )

    def _redis_connection(self):
        client = getattr(self._redis, "client", None)
        if client is not None and not callable(client):
            return client
        if callable(getattr(self._redis, "mget", None)):
            return self._redis
        return None

    @staticmethod
    def _session_cache_key(raw_token: str) -> str:
        return f"{_SESSION_CACHE_PREFIX}{sha256_token(raw_token)}"

    @staticmethod
    def _session_revoked_key(raw_token: str) -> str:
        return f"{_SESSION_REVOKED_PREFIX}{sha256_token(raw_token)}"

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
        if (
            not allow_expired
            and (
                challenge.code_hash is None
                or challenge.code_expires_at is None
                or challenge.code_expires_at <= now
            )
        ):
            raise INVALID_CODE

    @staticmethod
    def _challenge_locked() -> ApiError:
        return ApiError(
            423,
            "challenge_locked",
            "Tasdiqlash urinishlari tugadi. Yangi jarayonni boshlang.",
        )
