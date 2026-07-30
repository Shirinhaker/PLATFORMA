from datetime import datetime, timedelta

from app.accounts.model import AccountType
from app.accounts.repository import find_accounts_by_login
from app.auth.repository import (
    create_challenge,
    resolve_session as resolve_stored_session,
)
from app.auth.schemas import LoginStarted, SessionIdentity
from app.auth.security import (
    PasswordVerification,
    derive_csrf,
    verify_password_with_rehash,
)
from app.auth.service import (
    AuthService,
    INVALID_CREDENTIALS,
    _SESSION_TOUCH_INTERVAL,
)
from app.core.errors import ApiError


class SharedLoginAuthService(AuthService):
    async def start_login(
        self,
        login: str,
        password: str,
        now: datetime,
        *,
        account_type: AccountType | None = None,
    ) -> LoginStarted:
        normalized_login = login.strip().lower()
        async with self._session_factory() as session:
            try:
                candidates = await find_accounts_by_login(
                    session,
                    normalized_login,
                )
                if account_type is not None:
                    candidates = [
                        account
                        for account in candidates
                        if account.account_type is account_type
                    ]

                valid: list[tuple[object, PasswordVerification]] = []
                for account in candidates:
                    if account.status != "active":
                        continue
                    check = verify_password_with_rehash(
                        account.password_hash,
                        password,
                    )
                    if check.valid:
                        valid.append((account, check))

                if not valid:
                    raise INVALID_CREDENTIALS
                if len(valid) > 1 and account_type is None:
                    raise ApiError(
                        409,
                        "account_type_required",
                        "Oddiy yoki biznes kabinetini tanlang.",
                    )

                account, password_check = valid[0]
                if password_check.replacement_hash:
                    account.password_hash = password_check.replacement_hash

                challenge, raw_start_token = await create_challenge(
                    session,
                    purpose="login",
                    account_id=account.id,
                    now=now,
                    start_expires_at=(
                        now
                        + timedelta(
                            seconds=self._settings.telegram_link_ttl_seconds
                        )
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
            last_used_at = auth_session.last_used_at
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
            if last_used_at <= now - _SESSION_TOUCH_INTERVAL:
                last_used_at = now
                auth_session.last_used_at = last_used_at
                await session.commit()
            else:
                await session.rollback()

        await self._cache_session(
            raw_token,
            identity,
            now,
            last_used_at=last_used_at,
        )
        return identity
