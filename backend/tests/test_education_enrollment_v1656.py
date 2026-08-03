from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.accounts.model import AccountType
from app.auth.schemas import SessionIdentity
from app.auth.security import derive_csrf
from app.core.config import Settings
from app.core.errors import ApiError
from app.education.schemas import CourseEnrollmentCreate, CourseEnrollmentCreated
from app.education.service import EducationEnrollmentService
from app.main import create_app


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeEducationEnrollmentRepository:
    def __init__(self) -> None:
        self.user = SimpleNamespace(
            account_id=70,
            name="Ali Valiyev",
            phone="+998901234567",
        )
        self.business = SimpleNamespace(
            account_id=7,
            name="English House",
            direction="Ta'lim faoliyati",
            cabinet_payload={},
        )
        self.course = SimpleNamespace(
            public_id="s_english",
            source_record_key="51",
            business_account_id=7,
            name="Ingliz tili",
            kind="service",
        )
        self.resources = {
            "items": [{
                "id": 51,
                "name": "Ingliz tili",
                "kind": "service",
                "enrollment_status": "open",
            }],
            "education_enrollments": [],
        }
        self.replacements: list[tuple[str, list[dict[str, object]]]] = []

    async def user_profile(self, _session, account_id: int):
        return self.user if account_id == self.user.account_id else None

    async def locked_course_context(self, _session, public_id: str):
        if public_id != self.course.public_id:
            return None
        return self.course, self.business

    async def legacy_id(self, _session, entity_type: str, target_id: int):
        mapping = {
            ("user_account", 70): 17,
            ("business_account", 7): 3,
        }
        return mapping.get((entity_type, target_id))

    async def resource_rows(self, _session, _profile, resource: str):
        return [dict(row) for row in self.resources.get(resource, [])]

    async def replace_resource(
        self,
        _session,
        *,
        account_id: int,
        resource: str,
        rows: list[dict[str, object]],
    ) -> None:
        assert account_id == self.business.account_id
        self.resources[resource] = [dict(row) for row in rows]
        self.replacements.append((resource, self.resources[resource]))


def service_and_repository():
    session = FakeSession()
    repository = FakeEducationEnrollmentRepository()

    @asynccontextmanager
    async def session_factory():
        yield session

    return (
        EducationEnrollmentService(session_factory, repository=repository),
        repository,
        session,
    )


@pytest.mark.asyncio
async def test_course_enrollment_creates_v1656_business_application():
    service, repository, session = service_and_repository()

    created = await service.create(
        account_id=70,
        account_type=AccountType.USER,
        body=CourseEnrollmentCreate(
            course_item_public_id="s_english",
            phone=" +998 90 123 45 67 ",
            note=" Kechki guruh qulay ",
        ),
    )

    assert created.ok is True
    assert created.id == 1
    assert session.commits == 1
    assert [name for name, _rows in repository.replacements] == [
        "education_enrollments",
    ]
    row = repository.resources["education_enrollments"][0]
    assert row == {
        "id": 1,
        "business_id": 3,
        "course_item_id": 51,
        "user_id": 17,
        "user_account_id": 70,
        "user_legacy_id": 17,
        "customer_name": "Ali Valiyev",
        "phone": "+998 90 123 45 67",
        "note": "Kechki guruh qulay",
        "status": "new",
        "created_at": row["created_at"],
        "updated_at": row["created_at"],
    }
    assert repository.business.cabinet_payload["education_enrollments"] == [row]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("account_type", "status", "expected_code", "expected_message"),
    [
        (
            AccountType.BUSINESS,
            "open",
            "education_user_required",
            "Avval oddiy profilga o'ting.",
        ),
        (
            AccountType.USER,
            "closed",
            "course_enrollment_closed",
            "Bu kursga qabul yopilgan.",
        ),
    ],
)
async def test_course_enrollment_guards_actor_and_closed_course(
    account_type,
    status,
    expected_code,
    expected_message,
):
    service, repository, _session = service_and_repository()
    repository.resources["items"][0]["enrollment_status"] = status

    with pytest.raises(ApiError) as error:
        await service.create(
            account_id=70,
            account_type=account_type,
            body=CourseEnrollmentCreate(
                course_item_public_id="s_english",
                phone="+998901234567",
                note="",
            ),
        )

    assert error.value.code == expected_code
    assert error.value.message == expected_message
    assert repository.replacements == []


@pytest.mark.asyncio
async def test_course_enrollment_rejects_active_duplicate_and_empty_phone():
    service, repository, _session = service_and_repository()
    repository.resources["education_enrollments"] = [{
        "id": 9,
        "course_item_id": 51,
        "user_id": 17,
        "customer_name": "Ali Valiyev",
        "phone": "+998901234567",
        "status": "accepted",
    }]

    with pytest.raises(ApiError) as duplicate:
        await service.create(
            account_id=70,
            account_type=AccountType.USER,
            body=CourseEnrollmentCreate(
                course_item_public_id="s_english",
                phone="+998901234567",
                note="",
            ),
        )
    assert duplicate.value.code == "course_enrollment_duplicate"
    assert duplicate.value.message == "Siz bu kursga avval yozilgansiz."

    repository.resources["education_enrollments"] = []
    repository.user.phone = ""
    with pytest.raises(ApiError) as phone:
        await service.create(
            account_id=70,
            account_type=AccountType.USER,
            body=CourseEnrollmentCreate(
                course_item_public_id="s_english",
                phone=" ",
                note="",
            ),
        )
    assert phone.value.code == "course_enrollment_phone_required"
    assert phone.value.message == "Telefon raqamini kiriting."
    assert repository.replacements == []


@pytest.mark.asyncio
async def test_course_enrollment_route_requires_csrf_and_passes_current_user():
    settings = Settings(environment="test", csrf_secret="education-secret")
    token = "user-token"
    identity = SessionIdentity(
        account_id=70,
        account_type=AccountType.USER,
        login="u_ali",
        csrf_token=derive_csrf(token, settings.csrf_secret),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    class FakeAuthService:
        async def resolve_session(self, raw_token, _now):
            return identity if raw_token == token else None

    enrollment_service = SimpleNamespace(
        create=AsyncMock(return_value=CourseEnrollmentCreated(id=91)),
    )
    app = create_app(settings)
    app.state.auth_service = FakeAuthService()
    app.state.education_enrollment_service = enrollment_service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://api.test",
    ) as client:
        client.cookies.set(
            settings.auth_cookie_name,
            token,
            domain="api.test",
            path="/",
        )
        body = {
            "course_item_public_id": "s_english",
            "phone": "+998901234567",
            "note": "Kechki guruh",
        }
        rejected = await client.post(
            "/api/v1/education/enrollments",
            json=body,
        )
        accepted = await client.post(
            "/api/v1/education/enrollments",
            json=body,
            headers={"X-CSRF-Token": derive_csrf(token, settings.csrf_secret)},
        )

    assert rejected.status_code == 403
    assert rejected.json()["code"] == "csrf_failed"
    assert accepted.status_code == 201
    assert accepted.json() == {"ok": True, "id": 91}
    enrollment_service.create.assert_awaited_once()
    call = enrollment_service.create.await_args.kwargs
    assert call["account_id"] == 70
    assert call["account_type"] is AccountType.USER
    assert call["body"] == CourseEnrollmentCreate(**body)
