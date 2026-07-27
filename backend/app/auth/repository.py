from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account
from app.auth.model import AuthChallenge, AuthSession, PendingRegistration
from app.auth.schemas import RegistrationStart
from app.auth.security import new_url_token, sha256_token


async def create_pending_registration(
    session: AsyncSession,
    data: RegistrationStart,
    now: datetime,
    expires_at: datetime,
) -> PendingRegistration:
    registration = PendingRegistration(
        account_type=data.account_type,
        payload_json=data.model_dump(mode="json"),
        created_at=now,
        expires_at=expires_at,
    )
    session.add(registration)
    await session.flush()
    return registration


async def create_challenge(
    session: AsyncSession,
    *,
    purpose: str,
    now: datetime,
    start_expires_at: datetime,
    max_attempts: int,
    account_id: int | None = None,
    pending_registration_id: int | None = None,
) -> tuple[AuthChallenge, str]:
    raw_start_token = new_url_token()
    challenge = AuthChallenge(
        purpose=purpose,
        account_id=account_id,
        pending_registration_id=pending_registration_id,
        start_token_hash=sha256_token(raw_start_token),
        code_version=1,
        attempts=0,
        max_attempts=max_attempts,
        created_at=now,
        start_expires_at=start_expires_at,
    )
    session.add(challenge)
    await session.flush()
    return challenge, raw_start_token


async def find_challenge_by_start_token(
    session: AsyncSession,
    raw_start_token: str,
) -> AuthChallenge | None:
    result = await session.execute(
        select(AuthChallenge)
        .where(AuthChallenge.start_token_hash == sha256_token(raw_start_token))
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def lock_challenge(
    session: AsyncSession,
    request_id: int,
) -> AuthChallenge | None:
    result = await session.execute(
        select(AuthChallenge)
        .where(AuthChallenge.id == request_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def create_session(
    session: AsyncSession,
    *,
    account_id: int,
    device_name: str,
    now: datetime,
    expires_at: datetime,
) -> tuple[AuthSession, str]:
    raw_token = new_url_token()
    auth_session = AuthSession(
        account_id=account_id,
        token_hash=sha256_token(raw_token),
        device_name=device_name,
        created_at=now,
        expires_at=expires_at,
        last_used_at=now,
    )
    session.add(auth_session)
    await session.flush()
    return auth_session, raw_token


async def resolve_session(
    session: AsyncSession,
    raw_token: str,
    now: datetime,
) -> tuple[AuthSession, Account] | None:
    result = await session.execute(
        select(AuthSession, Account)
        .join(Account, Account.id == AuthSession.account_id)
        .where(
            AuthSession.token_hash == sha256_token(raw_token),
            AuthSession.expires_at > now,
            AuthSession.revoked_at.is_(None),
            Account.status == "active",
        )
    )
    row = result.one_or_none()
    return tuple(row) if row is not None else None


async def lock_session(
    session: AsyncSession,
    raw_token: str,
) -> AuthSession | None:
    result = await session.execute(
        select(AuthSession)
        .where(AuthSession.token_hash == sha256_token(raw_token))
        .with_for_update()
    )
    return result.scalar_one_or_none()
