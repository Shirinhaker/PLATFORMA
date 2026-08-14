"""Admin autentifikatsiyasi — v1656 `admin_auth.py` bilan bir xil oqim.

    Telegram ID (ro'yxatda bo'lishi shart)
    → bir martalik kod botga yuboriladi
    → kod tekshiriladi
    → alohida HttpOnly `koprik_admin_session` cookie beriladi

Admin sessiyasi oddiy foydalanuvchi sessiyasidan ajratilgan: o'g'irlangan
foydalanuvchi cookie'si admin bo'limlarini ochmaydi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
import hmac
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.model import AdminAuthChallenge, AdminSession
from app.auth.security import derive_otp, sha256_token
from app.core.config import Settings
from app.core.errors import ApiError
from app.outbox.repository import enqueue_event


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def _aware(value: datetime) -> datetime:
    """Bazadan kelgan vaqtni UTC deb qaraydi.

    PostgreSQL `timestamptz` mintaqani saqlaydi, SQLite esa yo'qotadi.
    Ikkala holatda ham qiymat UTC da yozilgan.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _code_hash(secret: str, telegram_user_id: int, code: str) -> str:
    return sha256_token(f"admin-code:{secret}:{telegram_user_id}:{code}")


class AdminAuthService:
    def __init__(
        self,
        session_factory: SessionFactory,
        settings: Settings,
        *,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._now = now_provider

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self._settings.admin_telegram_id_set

    async def start(self, *, telegram_user_id: int) -> dict[str, int]:
        """Kod yaratadi va botga yuborish uchun navbatga qo'yadi."""
        if not self.is_admin(telegram_user_id):
            # Ro'yxatda yo'q ID uchun kod umuman yaratilmaydi.
            raise ApiError(
                403,
                "admin_not_allowed",
                "Bu Telegram ID adminlar ro‘yxatida yo‘q.",
            )
        now = self._now()
        expires_at = now + timedelta(
            seconds=self._settings.admin_challenge_ttl_seconds
        )
        async with self._session_factory() as session:
            challenge = AdminAuthChallenge(
                telegram_user_id=telegram_user_id,
                code_hash="",
                attempts=0,
                expires_at=expires_at,
                consumed_at=None,
                created_at=now,
            )
            session.add(challenge)
            await session.flush()
            # Kod saqlanmaydi va navbatga ham yozilmaydi — u challenge
            # id sidan server siri bilan qayta hisoblanadi (auth domeni
            # bilan bir xil yondashuv).
            code = derive_otp(challenge.id, 0, self._settings.otp_secret)
            challenge.code_hash = _code_hash(
                self._settings.otp_secret, telegram_user_id, code
            )
            await enqueue_event(
                session,
                "telegram.admin_code.send",
                {
                    "challenge_id": challenge.id,
                    "chat_id": telegram_user_id,
                },
            )
            challenge_id = challenge.id
            await session.commit()
        return {
            "challenge_id": challenge_id,
            "expires_in": self._settings.admin_challenge_ttl_seconds,
        }

    async def verify(self, *, challenge_id: int, code: str) -> str:
        """Kodni tekshiradi va yangi sessiya tokenini qaytaradi."""
        now = self._now()
        async with self._session_factory() as session:
            challenge = await session.scalar(
                select(AdminAuthChallenge)
                .where(AdminAuthChallenge.id == challenge_id)
                .with_for_update()
            )
            if challenge is None:
                raise ApiError(
                    404,
                    "admin_challenge_not_found",
                    "Tasdiqlash so‘rovi topilmadi.",
                )
            if challenge.consumed_at is not None:
                raise ApiError(
                    409,
                    "admin_challenge_used",
                    "Tasdiqlash kodi allaqachon ishlatilgan.",
                )
            if _aware(challenge.expires_at) < now:
                raise ApiError(
                    410,
                    "admin_challenge_expired",
                    "Tasdiqlash kodi muddati tugagan.",
                )
            if challenge.attempts >= self._settings.admin_challenge_max_attempts:
                raise ApiError(
                    429,
                    "admin_challenge_attempts",
                    "Tasdiqlash urinishlari tugagan.",
                )
            # Ro'yxat kod yuborilgandan keyin o'zgargan bo'lishi mumkin.
            if not self.is_admin(challenge.telegram_user_id):
                raise ApiError(
                    403,
                    "admin_not_allowed",
                    "Bu Telegram ID adminlar ro‘yxatida yo‘q.",
                )
            expected = _code_hash(
                self._settings.otp_secret,
                challenge.telegram_user_id,
                str(code or ""),
            )
            if not hmac.compare_digest(expected, challenge.code_hash):
                challenge.attempts += 1
                await session.commit()
                raise ApiError(
                    400, "admin_code_invalid", "Tasdiqlash kodi noto‘g‘ri."
                )

            raw_token = secrets.token_urlsafe(48)
            challenge.consumed_at = now
            session.add(AdminSession(
                telegram_user_id=challenge.telegram_user_id,
                token_hash=sha256_token(raw_token),
                created_at=now,
                last_used_at=now,
                expires_at=now + timedelta(
                    seconds=self._settings.admin_session_ttl_seconds
                ),
                revoked_at=None,
            ))
            await session.flush()
            await session.commit()
        return raw_token

    async def resolve(self, raw_token: str) -> int | None:
        """Cookie'dan admin Telegram ID sini aniqlaydi.

        Sessiya muddati tugagan yoki uzoq turib qolgan bo'lsa bekor
        qilinadi va `None` qaytadi.
        """
        token = (raw_token or "").strip()
        if not token:
            return None
        now = self._now()
        async with self._session_factory() as session:
            row = await session.scalar(
                select(AdminSession)
                .where(
                    AdminSession.token_hash == sha256_token(token),
                    AdminSession.revoked_at.is_(None),
                )
                .with_for_update()
            )
            if row is None:
                return None
            idle_limit = _aware(row.last_used_at) + timedelta(
                seconds=self._settings.admin_session_idle_seconds
            )
            if _aware(row.expires_at) < now or idle_limit < now:
                row.revoked_at = now
                await session.commit()
                return None
            if not self.is_admin(row.telegram_user_id):
                # Ro'yxatdan chiqarilgan admin darhol quvviladi.
                row.revoked_at = now
                await session.commit()
                return None
            row.last_used_at = now
            telegram_user_id = row.telegram_user_id
            await session.commit()
        return telegram_user_id

    async def logout(self, raw_token: str) -> None:
        token = (raw_token or "").strip()
        if not token:
            return
        now = self._now()
        async with self._session_factory() as session:
            row = await session.scalar(
                select(AdminSession).where(
                    AdminSession.token_hash == sha256_token(token),
                    AdminSession.revoked_at.is_(None),
                )
            )
            if row is not None:
                row.revoked_at = now
            await session.commit()
