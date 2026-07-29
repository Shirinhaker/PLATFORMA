from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
from sqlalchemy import select

from app.accounts.model import Account, AccountType
from app.auth.model import AuthSession
from app.auth.schemas import SessionIdentity
from app.auth.security import derive_csrf, sha256_token
from app.core.config import Settings
from app.main import create_app
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.profiles.summary_service import ProfileSummaryService


class FakeAuthService:
    def __init__(self, identity):
        self.identity = identity
        self.revoked = []

    async def resolve_session(self, raw_token, now):
        return self.identity if raw_token == "user-token" else None

    async def _revoke_cached_session(self, raw_token):
        self.revoked.append(raw_token)


async def test_user_switches_to_linked_business_without_new_login(
    db_session,
    fixed_now,
):
    user = Account(
        account_type=AccountType.USER,
        login="shared_owner",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=fixed_now,
        updated_at=fixed_now,
    )
    business = Account(
        account_type=AccountType.BUSINESS,
        login="shared_owner",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=fixed_now,
        updated_at=fixed_now,
    )
    db_session.add_all([user, business])
    await db_session.flush()
    db_session.add_all(
        [
            UserProfile(account_id=user.id, name="Ali", phone=""),
            BusinessProfile(account_id=business.id, name="Turon", phone=""),
            ProfileLink(
                user_account_id=user.id,
                business_account_id=business.id,
                created_at=fixed_now,
            ),
            AuthSession(
                account_id=user.id,
                token_hash=sha256_token("user-token"),
                device_name="pytest",
                created_at=fixed_now,
                expires_at=fixed_now + timedelta(days=30),
                last_used_at=fixed_now,
            ),
        ]
    )
    await db_session.flush()

    settings = Settings(
        environment="test",
        csrf_secret="profile-switch-secret",
    )

    @asynccontextmanager
    async def session_factory():
        yield db_session

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = create_app(settings)
    identity = SessionIdentity(
        account_id=user.id,
        account_type=AccountType.USER,
        login=user.login,
        csrf_token=derive_csrf("user-token", settings.csrf_secret),
        expires_at=fixed_now + timedelta(days=30),
    )
    auth_service = FakeAuthService(identity)
    app.state.database = SimpleNamespace(session=session_factory)
    app.state.auth_service = auth_service
    app.state.redis = redis
    app.state.profile_summary_service = ProfileSummaryService(
        session_factory,
        redis,
        settings,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://api.test",
    ) as client:
        client.cookies.set(
            settings.auth_cookie_name,
            "user-token",
            domain="api.test",
            path="/",
        )
        response = await client.post(
            "/api/v1/cabinet/switch",
            headers={
                "X-CSRF-Token": derive_csrf(
                    "user-token",
                    settings.csrf_secret,
                )
            },
            json={"target_type": "business"},
        )

    await redis.aclose()
    assert response.status_code == 200, response.text
    assert response.json()["account_id"] == business.id
    assert response.json()["account_type"] == "business"
    assert response.json()["login"] == "shared_owner"
    assert "koprik_session=" in response.headers["set-cookie"]
    assert auth_service.revoked == ["user-token"]

    old_session = await db_session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == sha256_token("user-token")
        )
    )
    assert old_session is not None
    assert old_session.revoked_at is not None
    active_business_sessions = (
        await db_session.scalars(
            select(AuthSession).where(
                AuthSession.account_id == business.id,
                AuthSession.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(active_business_sessions) == 1
