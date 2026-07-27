from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from app.accounts.model import AccountType
from app.auth.schemas import SessionIdentity
from app.auth.security import derive_csrf
from app.core.config import Settings
from app.main import create_app
from app.profiles.model import BusinessProfile, UserProfile


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
    app = create_app(settings)
    app.state.database = FakeDatabase(profiles)
    app.state.auth_service = FakeAuthService(identities)

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
        yield SimpleNamespace(**clients)


async def test_user_cannot_read_business_profile(profile_clients):
    response = await profile_clients.first_user.get(
        "/api/v1/business-profile"
    )
    assert response.status_code == 403


async def test_business_cannot_read_user_profile(profile_clients):
    response = await profile_clients.business.get("/api/v1/user-profile")
    assert response.status_code == 403


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


async def test_profile_update_requires_csrf(profile_clients):
    response = await profile_clients.first_user.put(
        "/api/v1/user-profile",
        json={"name": "Ruxsatsiz"},
    )
    assert response.status_code == 403
