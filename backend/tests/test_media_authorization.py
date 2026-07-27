from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest

from app.accounts.model import AccountType
from app.auth.schemas import SessionIdentity
from app.auth.security import derive_csrf
from app.core.config import Settings
from app.main import create_app
from app.media.storage import R2Storage
from app.profiles.model import BusinessProfile, UserProfile
from app.profiles.summary_service import ProfileSummaryService


class FakeAuthService:
    def __init__(self, identities):
        self.identities = identities

    async def resolve_session(self, raw_token, now):
        return self.identities.get(raw_token)


class FakeProfileSession:
    def __init__(self, profiles):
        self.profiles = profiles

    async def get(self, model, account_id):
        return self.profiles[model].get(account_id)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


class FakeDatabase:
    def __init__(self, profiles):
        self.profiles = profiles

    @asynccontextmanager
    async def session(self):
        yield FakeProfileSession(self.profiles)


@pytest.fixture
async def media_clients(s3_client):
    settings = Settings(
        environment="test",
        csrf_secret="media-csrf-secret",
    )
    profiles = {
        UserProfile: {
            42: UserProfile(
                account_id=42,
                name="Ali",
                phone="+998901234567",
                public_username="",
                region="",
                district="",
                mahalla="",
                location_exact=False,
                avatar_object_key="",
                avatar_x=50,
                avatar_y=50,
                avatar_zoom=1,
            ),
        },
        BusinessProfile: {
            84: BusinessProfile(
                account_id=84,
                name="Koprik Biznes",
                phone="+998907654321",
                description="",
                public_username="",
                direction="Savdo",
                activity_type="",
                address="Toshkent",
                work_hours={},
                pay_card="",
                pay_holder="",
                pay_qr_object_key="",
                director="",
                tax_id="",
                logo_object_key="",
                logo_x=50,
                logo_y=50,
                logo_zoom=1,
            ),
        },
    }
    now = datetime.now(UTC)
    identities = {
        "user-session": SessionIdentity(
            account_id=42,
            account_type=AccountType.USER,
            login="u_media",
            csrf_token=derive_csrf("user-session", settings.csrf_secret),
            expires_at=now + timedelta(days=30),
        ),
        "business-session": SessionIdentity(
            account_id=84,
            account_type=AccountType.BUSINESS,
            login="b_media",
            csrf_token=derive_csrf(
                "business-session",
                settings.csrf_secret,
            ),
            expires_at=now + timedelta(days=30),
        ),
    }
    database = FakeDatabase(profiles)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = create_app(settings)
    app.state.auth_service = FakeAuthService(identities)
    app.state.database = database
    app.state.profile_summary_service = ProfileSummaryService(
        database.session,
        redis,
        settings,
    )
    app.state.r2 = R2Storage(s3_client, bucket="koprik-test")

    async with AsyncExitStack() as stack:
        clients = {}
        for name, token in (
            ("anonymous", None),
            ("user", "user-session"),
            ("business", "business-session"),
        ):
            client = await stack.enter_async_context(
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="https://api.test",
                )
            )
            if token:
                client.cookies.set(
                    settings.auth_cookie_name,
                    token,
                    domain="api.test",
                    path="/",
                )
                client.csrf = derive_csrf(token, settings.csrf_secret)
            clients[name] = client
        yield SimpleNamespace(**clients)
    await redis.aclose()


def upload_request(purpose):
    return {
        "purpose": purpose,
        "filename": "profile.png",
        "content_type": "image/png",
        "size_bytes": 1024,
    }


async def test_upload_grant_rejects_foundation_actor_header(media_clients):
    response = await media_clients.anonymous.post(
        "/api/v1/media/upload-grants",
        headers={"X-Foundation-Actor-Id": "42"},
        json=upload_request("avatar"),
    )
    assert response.status_code == 401


async def test_user_receives_only_avatar_prefix(media_clients):
    response = await media_clients.user.post(
        "/api/v1/media/upload-grants",
        headers={"X-CSRF-Token": media_clients.user.csrf},
        json=upload_request("avatar"),
    )
    assert response.status_code == 200
    assert response.json()["object_key"].startswith(
        "private/user/42/avatar/"
    )


async def test_user_cannot_request_business_logo(media_clients):
    response = await media_clients.user.post(
        "/api/v1/media/upload-grants",
        headers={"X-CSRF-Token": media_clients.user.csrf},
        json=upload_request("logo"),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "media_purpose_forbidden"


async def test_business_receives_only_logo_prefix(media_clients):
    response = await media_clients.business.post(
        "/api/v1/media/upload-grants",
        headers={"X-CSRF-Token": media_clients.business.csrf},
        json=upload_request("logo"),
    )
    assert response.status_code == 200
    assert response.json()["object_key"].startswith(
        "private/business/84/logo/"
    )


async def test_user_attaches_only_own_generated_avatar(media_clients):
    grant = await media_clients.user.post(
        "/api/v1/media/upload-grants",
        headers={"X-CSRF-Token": media_clients.user.csrf},
        json=upload_request("avatar"),
    )
    object_key = grant.json()["object_key"]
    attached = await media_clients.user.put(
        "/api/v1/user-profile/avatar",
        headers={"X-CSRF-Token": media_clients.user.csrf},
        json={
            "object_key": object_key,
            "x": 44.5,
            "y": 55.5,
            "zoom": 1.25,
        },
    )
    assert attached.status_code == 200
    assert attached.json()["avatar_object_key"] == object_key
    assert attached.json()["avatar_x"] == 44.5

    foreign = await media_clients.user.put(
        "/api/v1/user-profile/avatar",
        headers={"X-CSRF-Token": media_clients.user.csrf},
        json={
            "object_key": (
                "private/user/99/avatar/"
                "0123456789abcdef0123456789abcdef.png"
            ),
            "x": 50,
            "y": 50,
            "zoom": 1,
        },
    )
    assert foreign.status_code == 403
    assert foreign.json()["code"] == "media_object_forbidden"
