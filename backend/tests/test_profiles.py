from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from app.accounts.model import AccountType
from app.auth.schemas import SessionIdentity
from app.auth.security import derive_csrf
from app.core.config import Settings
from app.main import create_app
from app.profiles.model import BusinessProfile, UserProfile
from app.profiles.summary_service import ProfileSummaryService


class FakeProfileSession:
    def __init__(self, profiles):
        self.profiles = profiles
        self.snapshot = {
            profile: {
                column.name: getattr(profile, column.name)
                for column in model.__table__.columns
            }
            for model in (UserProfile, BusinessProfile)
            for profile in profiles[model].values()
        }

    async def get(self, model, account_id):
        return self.profiles[model].get(account_id)

    async def flush(self):
        for model in (UserProfile, BusinessProfile):
            usernames = [
                profile.public_username.lower()
                for profile in self.profiles[model].values()
                if profile.public_username
            ]
            if len(usernames) != len(set(usernames)):
                raise IntegrityError(
                    "duplicate public username",
                    {},
                    RuntimeError("unique username"),
                )

    async def commit(self):
        return None

    async def rollback(self):
        for profile, values in self.snapshot.items():
            for field, value in values.items():
                setattr(profile, field, value)


class FakeDatabase:
    def __init__(self, profiles):
        self.profiles = profiles

    @asynccontextmanager
    async def session(self):
        yield FakeProfileSession(self.profiles)


class FakeAuthService:
    def __init__(self, identities):
        self.identities = identities

    async def resolve_session(self, raw_token, now):
        return self.identities.get(raw_token)


@pytest.fixture
async def profile_clients():
    settings = Settings(
        environment="test",
        csrf_secret="profile-csrf-secret",
    )
    profiles = {
        UserProfile: {
            1: UserProfile(
                account_id=1,
                name="Ali",
                phone="+998901112233",
                public_username="",
                region="Toshkent",
                district="Chilonzor",
                mahalla="Bunyodkor",
                location_exact=False,
                avatar_object_key="",
                avatar_x=50,
                avatar_y=50,
                avatar_zoom=1,
            ),
            2: UserProfile(
                account_id=2,
                name="Vali",
                phone="+998909998877",
                public_username="",
                region="Samarqand",
                district="Samarqand",
                mahalla="Registon",
                location_exact=False,
                avatar_object_key="",
                avatar_x=50,
                avatar_y=50,
                avatar_zoom=1,
            ),
        },
        BusinessProfile: {
            3: BusinessProfile(
                account_id=3,
                name="Koprik Savdo",
                phone="+998907770000",
                description="Test biznes",
                public_username="",
                direction="Savdo",
                activity_type="Chakana savdo",
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
        "user-1": SessionIdentity(
            account_id=1,
            account_type=AccountType.USER,
            login="u_one",
            csrf_token=derive_csrf("user-1", settings.csrf_secret),
            expires_at=now + timedelta(days=30),
        ),
        "user-2": SessionIdentity(
            account_id=2,
            account_type=AccountType.USER,
            login="u_two",
            csrf_token=derive_csrf("user-2", settings.csrf_secret),
            expires_at=now + timedelta(days=30),
        ),
        "business-3": SessionIdentity(
            account_id=3,
            account_type=AccountType.BUSINESS,
            login="b_three",
            csrf_token=derive_csrf("business-3", settings.csrf_secret),
            expires_at=now + timedelta(days=30),
        ),
    }
    database = FakeDatabase(profiles)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = create_app(settings)
    app.state.database = database
    app.state.auth_service = FakeAuthService(identities)
    app.state.profile_summary_service = ProfileSummaryService(
        database.session,
        redis,
        settings,
    )

    async with AsyncExitStack() as stack:
        clients = {}
        for name, token in (
            ("first_user", "user-1"),
            ("second_user", "user-2"),
            ("business", "business-3"),
        ):
            client = await stack.enter_async_context(
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="https://api.test",
                )
            )
            client.cookies.set(
                settings.auth_cookie_name,
                token,
                domain="api.test",
                path="/",
            )
            client.csrf = derive_csrf(token, settings.csrf_secret)
            clients[name] = client
        clients["database"] = database
        clients["redis"] = redis
        yield SimpleNamespace(**clients)
    await redis.aclose()


async def test_user_cannot_read_business_profile(profile_clients):
    response = await profile_clients.first_user.get(
        "/api/v1/business-profile"
    )
    assert response.status_code == 403


async def test_business_cannot_read_user_profile(profile_clients):
    response = await profile_clients.business.get("/api/v1/user-profile")
    assert response.status_code == 403


async def test_profile_reads_normalize_non_finite_legacy_values(profile_clients):
    user = profile_clients.database.profiles[UserProfile][1]
    user.latitude = float("nan")
    user.longitude = float("inf")
    user.avatar_x = float("-inf")
    user.avatar_y = float("nan")
    user.avatar_zoom = float("inf")
    user.dashboard_snapshot = {"broken": float("nan")}
    user.specialist_profile = {"price": float("inf")}
    user.cabinet_payload = {
        "items": [{"price": float("-inf")}],
    }

    user_response = await profile_clients.first_user.get(
        "/api/v1/user-profile"
    )

    assert user_response.status_code == 200, user_response.text
    user_body = user_response.json()
    assert user_body["latitude"] is None
    assert user_body["longitude"] is None
    assert user_body["avatar_x"] == 50.0
    assert user_body["avatar_y"] == 50.0
    assert user_body["avatar_zoom"] == 1.0
    assert user_body["dashboard_snapshot"]["broken"] is None
    assert user_body["specialist_profile"]["price"] is None
    assert user_body["cabinet_payload"]["items"][0]["price"] is None

    business = profile_clients.database.profiles[BusinessProfile][3]
    business.latitude = float("nan")
    business.longitude = float("-inf")
    business.logo_x = float("inf")
    business.logo_y = float("nan")
    business.logo_zoom = float("-inf")
    business.work_hours = {"monday": float("nan")}
    business.cabinet_payload = {"sales": [{"total": float("inf")}]}

    business_response = await profile_clients.business.get(
        "/api/v1/business-profile"
    )

    assert business_response.status_code == 200, business_response.text
    business_body = business_response.json()
    assert business_body["latitude"] is None
    assert business_body["longitude"] is None
    assert business_body["logo_x"] == 50.0
    assert business_body["logo_y"] == 50.0
    assert business_body["logo_zoom"] == 1.0
    assert business_body["work_hours"]["monday"] is None
    assert business_body["cabinet_payload"]["sales"][0]["total"] is None


async def test_partial_profile_update_preserves_unsent_fields(profile_clients):
    before = (
        await profile_clients.first_user.get("/api/v1/user-profile")
    ).json()
    response = await profile_clients.first_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.first_user.csrf},
        json={"name": "Yangi ism"},
    )
    assert response.status_code == 200
    after = response.json()
    assert after["name"] == "Yangi ism"
    assert after["phone"] == before["phone"]


async def test_public_username_is_unique_per_profile_type(profile_clients):
    first = await profile_clients.first_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.first_user.csrf},
        json={"public_username": " @Koprik_Test "},
    )
    assert first.status_code == 200
    assert first.json()["public_username"] == "koprik_test"
    duplicate = await profile_clients.second_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.second_user.csrf},
        json={"public_username": "KOPRIK_TEST"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "username_taken"

    other_type = await profile_clients.business.put(
        "/api/v1/business-profile",
        headers={"X-CSRF-Token": profile_clients.business.csrf},
        json={"public_username": "KOPRIK_TEST"},
    )
    assert other_type.status_code == 200
    assert other_type.json()["public_username"] == "koprik_test"


async def test_me_returns_exact_role_specific_identity(profile_clients):
    response = await profile_clients.business.get("/api/v1/me")
    assert response.status_code == 200
    assert response.json() == {
        "account_id": 3,
        "account_type": "business",
        "name": "Koprik Savdo",
        "profile_complete": True,
    }


async def test_me_populates_profile_summary_cache(profile_clients):
    response = await profile_clients.first_user.get("/api/v1/me")
    cached = await profile_clients.redis.get(
        "profile:me:v1:user:1"
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Ali"
    assert cached is not None


async def test_user_profile_update_invalidates_cached_me(profile_clients):
    before = await profile_clients.first_user.get("/api/v1/me")
    assert before.json()["name"] == "Ali"
    assert await profile_clients.redis.get(
        "profile:me:v1:user:1"
    ) is not None

    updated = await profile_clients.first_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.first_user.csrf},
        json={"name": "Yangi Ali"},
    )
    after = await profile_clients.first_user.get("/api/v1/me")

    assert updated.status_code == 200
    assert after.status_code == 200
    assert after.json()["name"] == "Yangi Ali"


async def test_failed_profile_update_keeps_existing_me_cache(profile_clients):
    first = await profile_clients.first_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.first_user.csrf},
        json={"public_username": "shared_name"},
    )
    assert first.status_code == 200

    cached_second = await profile_clients.second_user.get("/api/v1/me")
    assert cached_second.status_code == 200
    cache_key = "profile:me:v1:user:2"
    cached_before_failure = await profile_clients.redis.get(cache_key)
    assert cached_before_failure is not None

    duplicate = await profile_clients.second_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.second_user.csrf},
        json={"public_username": "shared_name"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "username_taken"
    assert await profile_clients.redis.get(cache_key) == cached_before_failure
    after = await profile_clients.second_user.get("/api/v1/me")
    assert after.status_code == 200
    assert after.json()["name"] == "Vali"


async def test_user_avatar_update_invalidates_cached_me(profile_clients):
    cache_key = "profile:me:v1:user:1"
    before = await profile_clients.first_user.get("/api/v1/me")
    assert before.status_code == 200
    assert await profile_clients.redis.get(cache_key) is not None

    updated = await profile_clients.first_user.put(
        "/api/v1/user-profile/avatar",
        headers={"X-CSRF-Token": profile_clients.first_user.csrf},
        json={
            "object_key": (
                "private/user/1/avatar/"
                "0123456789abcdef0123456789abcdef.webp"
            ),
            "x": 50,
            "y": 50,
            "zoom": 1,
        },
    )

    assert updated.status_code == 200
    assert await profile_clients.redis.get(cache_key) is None
    after = await profile_clients.first_user.get("/api/v1/me")
    assert after.status_code == 200
    assert await profile_clients.redis.get(cache_key) is not None


async def test_business_logo_update_invalidates_cached_me(profile_clients):
    cache_key = "profile:me:v1:business:3"
    before = await profile_clients.business.get("/api/v1/me")
    assert before.status_code == 200
    assert await profile_clients.redis.get(cache_key) is not None

    updated = await profile_clients.business.put(
        "/api/v1/business-profile/logo",
        headers={"X-CSRF-Token": profile_clients.business.csrf},
        json={
            "object_key": (
                "private/business/3/logo/"
                "0123456789abcdef0123456789abcdef.webp"
            ),
            "x": 50,
            "y": 50,
            "zoom": 1,
        },
    )

    assert updated.status_code == 200
    assert await profile_clients.redis.get(cache_key) is None
    after = await profile_clients.business.get("/api/v1/me")
    assert after.status_code == 200
    assert await profile_clients.redis.get(cache_key) is not None


async def test_profile_update_requires_csrf(profile_clients):
    response = await profile_clients.first_user.put(
        "/api/v1/user-profile",
        json={"name": "Ruxsatsiz"},
    )
    assert response.status_code == 403
