"""Moderatsiya, shikoyatlar va audit tarixi.

v1656 qoidalari: `content_hidden` egasining kabinetidagi ma'lumotni
o'chirmaydi, `account_blocked` dan mustaqil, va har bir admin amali
o'zgartirib bo'lmaydigan jurnalga tushadi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.admin.moderation_model import (
    AccountRestriction,
    AdminAccountNote,
    AdminAuditLog,
    ContentModeration,
    ModerationReport,
)
from app.admin.moderation_service import AdminModerationService
from app.admin.reports_service import AdminReportsService
from app.core.errors import ApiError
from app.db.base import Base
from app.legacy_migration.model import OwnerState, ReviewState
from app.profiles.model import BusinessProfile, UserProfile


NOW = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
ADMIN = 1423181561
OTHER_ADMIN = 607563067
SHOP = 7
CUSTOMER = 11
META = {"ip_hash": "a" * 64, "user_agent": "AdminPanel/1.0"}


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    def get_bind(self):
        return self.sync.get_bind()

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            highest = self.sequences.get(table)
            if highest is None:
                highest = int(
                    self.sync.scalar(select(func.max(value.__table__.c.id))) or 0
                )
            highest += 1
            self.sequences[table] = highest
            value.id = highest
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def _account(identifier: int, kind: AccountType, login: str) -> Account:
    return Account(
        id=identifier,
        account_type=kind,
        login=login,
        password_hash="hash",
        telegram_user_id=900000 + identifier,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def admin_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            AccountRestriction.__table__,
            AdminAccountNote.__table__,
            ContentModeration.__table__,
            ModerationReport.__table__,
            AdminAuditLog.__table__,
        ),
    )
    with Session(engine, expire_on_commit=False) as seed:
        seed.add_all((
            _account(SHOP, AccountType.BUSINESS, "choyxona"),
            _account(CUSTOMER, AccountType.USER, "anvar"),
            BusinessProfile(
                account_id=SHOP,
                name="Choyxona",
                phone="+998901112233",
                description="",
                public_username="choyxona",
                direction="Umumiy ovqatlanish",
                activity_type="",
                address="",
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
                followers_count=0,
                following_count=0,
                rating_sum=0,
                rating_count=0,
                map_visible=False,
                dashboard_snapshot={},
                recent_activity=[],
                cabinet_payload={},
            ),
            UserProfile(
                account_id=CUSTOMER,
                name="Anvar",
                phone="+998907776655",
                public_username="anvar",
                avatar_object_key="",
                avatar_x=50,
                avatar_y=50,
                avatar_zoom=1,
                cabinet_payload={},
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    moderation = AdminModerationService(sessions, now_provider=lambda: NOW)
    reports = AdminReportsService(sessions, now_provider=lambda: NOW)
    try:
        yield moderation, reports, engine
    finally:
        engine.dispose()


# ------------------------------------------------------------------ qidiruv


async def test_accounts_are_searchable_by_name_and_login(admin_context):
    moderation, _reports, _engine = admin_context

    by_login = await moderation.list_accounts(
        actor_type="business", query="choy"
    )
    assert [row["account_id"] for row in by_login] == [SHOP]
    assert by_login[0]["name"] == "Choyxona"

    by_name = await moderation.list_accounts(actor_type="user", query="anvar")
    assert [row["account_id"] for row in by_name] == [CUSTOMER]


async def test_user_search_does_not_return_businesses(admin_context):
    moderation, _reports, _engine = admin_context
    rows = await moderation.list_accounts(actor_type="user", query="choy")
    assert rows == []


# --------------------------------------------------------------- cheklovlar


async def test_restriction_is_recorded_and_audited(admin_context):
    moderation, _reports, engine = admin_context

    result = await moderation.restrict(
        actor_type="business",
        account_id=SHOP,
        restriction="content_hidden",
        reason="Shikoyat tasdiqlandi",
        admin_tg_id=ADMIN,
        meta=META,
    )
    assert result["already_active"] is False

    detail = await moderation.account_detail(
        actor_type="business", account_id=SHOP
    )
    assert detail["restrictions"][0]["restriction"] == "content_hidden"
    assert detail["restrictions"][0]["status"] == "active"

    with Session(engine) as check:
        entry = check.scalar(select(AdminAuditLog))
        assert entry.action == "account.restrict"
        assert entry.admin_tg_id == ADMIN
        assert entry.target_id == str(SHOP)
        assert entry.reason == "Shikoyat tasdiqlandi"
        # Xom IP saqlanmaydi.
        assert entry.ip_hash == META["ip_hash"]


async def test_restriction_is_idempotent(admin_context):
    moderation, _reports, engine = admin_context
    for _ in range(2):
        await moderation.restrict(
            actor_type="business",
            account_id=SHOP,
            restriction="account_blocked",
            reason="Firibgarlik",
            admin_tg_id=ADMIN,
            meta=META,
        )
    with Session(engine) as check:
        assert check.scalar(
            select(func.count()).select_from(AccountRestriction)
        ) == 1


async def test_two_restrictions_are_independent(admin_context):
    """`content_hidden` bloklashni yoqmaydi va aksincha."""
    moderation, _reports, _engine = admin_context
    await moderation.restrict(
        actor_type="business", account_id=SHOP,
        restriction="content_hidden", reason="Tekshiruv",
        admin_tg_id=ADMIN, meta=META,
    )
    detail = await moderation.account_detail(
        actor_type="business", account_id=SHOP
    )
    active = {
        row["restriction"] for row in detail["restrictions"]
        if row["status"] == "active"
    }
    assert active == {"content_hidden"}


async def test_restriction_requires_a_reason(admin_context):
    moderation, _reports, _engine = admin_context
    with pytest.raises(ApiError) as failure:
        await moderation.restrict(
            actor_type="business", account_id=SHOP,
            restriction="content_hidden", reason="   ",
            admin_tg_id=ADMIN, meta=META,
        )
    assert failure.value.code == "admin_reason_required"


async def test_unrestrict_revokes_and_audits(admin_context):
    moderation, _reports, engine = admin_context
    await moderation.restrict(
        actor_type="user", account_id=CUSTOMER,
        restriction="account_blocked", reason="Spam",
        admin_tg_id=ADMIN, meta=META,
    )

    await moderation.unrestrict(
        actor_type="user", account_id=CUSTOMER,
        restriction="account_blocked", reason="Shikoyat asossiz",
        admin_tg_id=OTHER_ADMIN, meta=META,
    )

    detail = await moderation.account_detail(
        actor_type="user", account_id=CUSTOMER
    )
    assert detail["restrictions"][0]["status"] == "revoked"
    assert detail["restrictions"][0]["revoked_reason"] == "Shikoyat asossiz"
    with Session(engine) as check:
        actions = check.scalars(
            select(AdminAuditLog.action).order_by(AdminAuditLog.id)
        ).all()
        assert list(actions) == ["account.restrict", "account.unrestrict"]


async def test_unrestrict_without_active_restriction_fails(admin_context):
    moderation, _reports, _engine = admin_context
    with pytest.raises(ApiError) as failure:
        await moderation.unrestrict(
            actor_type="user", account_id=CUSTOMER,
            restriction="account_blocked", reason="Sabab",
            admin_tg_id=ADMIN, meta=META,
        )
    assert failure.value.status_code == 404


async def test_unknown_account_is_refused(admin_context):
    moderation, _reports, _engine = admin_context
    with pytest.raises(ApiError) as failure:
        await moderation.restrict(
            actor_type="business", account_id=999,
            restriction="content_hidden", reason="Sabab",
            admin_tg_id=ADMIN, meta=META,
        )
    assert failure.value.status_code == 404


async def test_notes_are_stored_for_admins_only(admin_context):
    moderation, _reports, _engine = admin_context

    await moderation.add_note(
        actor_type="business", account_id=SHOP,
        note="Telefon orqali bog'lanildi",
        admin_tg_id=ADMIN, meta=META,
    )
    detail = await moderation.account_detail(
        actor_type="business", account_id=SHOP
    )
    assert detail["notes"][0]["note"] == "Telefon orqali bog'lanildi"
    assert detail["notes"][0]["admin_tg_id"] == ADMIN


# ------------------------------------------------------------------ kontent


async def test_content_is_visible_until_hidden(admin_context):
    moderation, _reports, _engine = admin_context

    before = await moderation.content_status(
        content_kind="listing", content_id=42
    )
    assert before["status"] == "visible"
    assert before["history"] == []

    await moderation.set_content_status(
        content_kind="listing", content_id=42, status="hidden",
        reason="Noqonuniy mahsulot", admin_tg_id=ADMIN, meta=META,
    )
    after = await moderation.content_status(
        content_kind="listing", content_id=42
    )
    assert after["status"] == "hidden"
    assert after["history"][0]["reason"] == "Noqonuniy mahsulot"


async def test_content_history_keeps_every_change(admin_context):
    moderation, _reports, engine = admin_context
    for status, reason in (
        ("hidden", "Tekshiruv"),
        ("visible", ""),
        ("removed", "Qayta buzildi"),
    ):
        await moderation.set_content_status(
            content_kind="story", content_id=5, status=status,
            reason=reason, admin_tg_id=ADMIN, meta=META,
        )
    detail = await moderation.content_status(
        content_kind="story", content_id=5
    )
    assert detail["status"] == "removed"
    assert [row["status"] for row in detail["history"]] == [
        "removed", "visible", "hidden",
    ]
    with Session(engine) as check:
        actions = check.scalars(
            select(AdminAuditLog.action).order_by(AdminAuditLog.id)
        ).all()
        assert list(actions) == [
            "content.hidden", "content.visible", "content.removed",
        ]


async def test_hiding_content_requires_a_reason(admin_context):
    moderation, _reports, _engine = admin_context
    with pytest.raises(ApiError) as failure:
        await moderation.set_content_status(
            content_kind="listing", content_id=42, status="hidden",
            reason="", admin_tg_id=ADMIN, meta=META,
        )
    assert failure.value.code == "admin_reason_required"


async def test_unknown_content_kind_is_refused(admin_context):
    moderation, _reports, _engine = admin_context
    with pytest.raises(ApiError) as failure:
        await moderation.set_content_status(
            content_kind="taxi", content_id=1, status="hidden",
            reason="Sabab", admin_tg_id=ADMIN, meta=META,
        )
    assert failure.value.code == "admin_content_kind_invalid"


# --------------------------------------------------------------- shikoyatlar


async def test_report_reaches_the_queue(admin_context):
    _moderation, reports, _engine = admin_context

    created = await reports.create_report(
        reporter_account_id=CUSTOMER,
        content_kind="listing",
        content_id=42,
        reason_code="fraud",
        comment="Pul olib mahsulot bermadi",
    )
    assert created["status"] == "open"

    queue = await reports.list_reports(status="open")
    assert [row["id"] for row in queue] == [created["id"]]


async def test_duplicate_report_does_not_flood_the_queue(admin_context):
    _moderation, reports, engine = admin_context
    for _ in range(3):
        await reports.create_report(
            reporter_account_id=CUSTOMER, content_kind="listing",
            content_id=42, reason_code="spam", comment="",
        )
    with Session(engine) as check:
        assert check.scalar(
            select(func.count()).select_from(ModerationReport)
        ) == 1


async def test_assign_then_resolve_is_audited(admin_context):
    _moderation, reports, engine = admin_context
    created = await reports.create_report(
        reporter_account_id=CUSTOMER, content_kind="listing",
        content_id=42, reason_code="fraud", comment="",
    )

    assigned = await reports.assign(
        report_id=created["id"], admin_tg_id=ADMIN, meta=META
    )
    assert assigned["status"] == "reviewing"
    assert assigned["assigned_admin_tg_id"] == ADMIN

    resolved = await reports.decide(
        report_id=created["id"], decision="resolved",
        resolution="E'lon olib tashlandi", admin_tg_id=ADMIN, meta=META,
    )
    assert resolved["status"] == "resolved"

    with Session(engine) as check:
        actions = check.scalars(
            select(AdminAuditLog.action).order_by(AdminAuditLog.id)
        ).all()
        assert list(actions) == ["report.assign", "report.resolved"]


async def test_second_decision_is_refused(admin_context):
    """Ikki admin bir shikoyatni ikki marta hal qilmaydi."""
    _moderation, reports, _engine = admin_context
    created = await reports.create_report(
        reporter_account_id=CUSTOMER, content_kind="listing",
        content_id=42, reason_code="abuse", comment="",
    )
    await reports.decide(
        report_id=created["id"], decision="dismissed",
        resolution="Asossiz", admin_tg_id=ADMIN, meta=META,
    )

    with pytest.raises(ApiError) as failure:
        await reports.decide(
            report_id=created["id"], decision="resolved",
            resolution="Boshqa qaror", admin_tg_id=OTHER_ADMIN, meta=META,
        )
    assert failure.value.status_code == 409
    assert failure.value.code == "report_already_decided"


async def test_decision_requires_a_resolution(admin_context):
    _moderation, reports, _engine = admin_context
    created = await reports.create_report(
        reporter_account_id=CUSTOMER, content_kind="listing",
        content_id=42, reason_code="other", comment="",
    )
    with pytest.raises(ApiError) as failure:
        await reports.decide(
            report_id=created["id"], decision="resolved",
            resolution="  ", admin_tg_id=ADMIN, meta=META,
        )
    assert failure.value.code == "admin_reason_required"


async def test_invalid_reason_code_is_refused(admin_context):
    _moderation, reports, _engine = admin_context
    with pytest.raises(ApiError) as failure:
        await reports.create_report(
            reporter_account_id=CUSTOMER, content_kind="listing",
            content_id=42, reason_code="boshqa", comment="",
        )
    assert failure.value.code == "report_reason_invalid"


# -------------------------------------------------------------------- audit


async def test_audit_detail_carries_before_and_after(admin_context):
    moderation, reports, _engine = admin_context
    await moderation.restrict(
        actor_type="business", account_id=SHOP,
        restriction="content_hidden", reason="Tekshiruv",
        admin_tg_id=ADMIN, meta=META,
    )
    rows = await reports.list_audit()
    detail = await reports.audit_detail(rows[0]["id"])

    assert detail["before"] == {"restriction": "content_hidden", "status": "none"}
    assert detail["after"] == {"restriction": "content_hidden", "status": "active"}
    assert detail["user_agent"] == "AdminPanel/1.0"


async def test_audit_can_be_filtered_by_action(admin_context):
    moderation, reports, _engine = admin_context
    await moderation.restrict(
        actor_type="business", account_id=SHOP,
        restriction="content_hidden", reason="Tekshiruv",
        admin_tg_id=ADMIN, meta=META,
    )
    await moderation.add_note(
        actor_type="business", account_id=SHOP, note="Izoh",
        admin_tg_id=ADMIN, meta=META,
    )

    assert len(await reports.list_audit()) == 2
    only_notes = await reports.list_audit(action="account.note")
    assert [row["action"] for row in only_notes] == ["account.note"]


async def test_audit_export_is_csv(admin_context):
    moderation, reports, _engine = admin_context
    await moderation.restrict(
        actor_type="business", account_id=SHOP,
        restriction="content_hidden", reason="Tekshiruv",
        admin_tg_id=ADMIN, meta=META,
    )

    csv_text = await reports.audit_csv()
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("id,created_at,admin_tg_id,action")
    assert "account.restrict" in lines[1]
    # Eksportda IP xeshi va brauzer satri bo'lmaydi.
    assert META["ip_hash"] not in csv_text
    assert "AdminPanel/1.0" not in csv_text
