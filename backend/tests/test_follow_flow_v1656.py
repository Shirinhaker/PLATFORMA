"""Obuna bo'lish va bekor qilish.

Ilgari faqat ro'yxatni ko'rish va bekor qilish bor edi — obuna bo'lish
oqimi umuman yo'q edi. v1656 (`api.py:toggle_follow`) bitta amal
beradi: bo'lmagan bo'lsa obuna bo'ladi, bo'lgan bo'lsa bekor qiladi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.db.base import Base
from app.follows.model import ProfileFollow
from app.follows.schemas import FollowToggle
from app.follows.service import FollowService
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_ids import build_profile_public_id


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
STAMP = 1785200000
READER = 70          # obuna bo'luvchi oddiy foydalanuvchi
AUTHOR = 71          # boshqa oddiy foydalanuvchi
SHOP = 7             # biznes
READER_SHOP = 8      # READER ga bog'langan biznes


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
            if table not in self.sequences:
                highest = self.sync.scalar(
                    select(func.max(value.__table__.c.id))
                )
                self.sequences[table] = int(highest or 0)
            self.sequences[table] += 1
            value.id = self.sequences[table]
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def _account(identifier: int, kind: AccountType) -> Account:
    return Account(
        id=identifier,
        account_type=kind,
        login=f"follow_{kind.value}_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _user(account_id: int, name: str) -> UserProfile:
    return UserProfile(
        account_id=account_id,
        name=name,
        phone="",
        public_username=f"user{account_id}",
        public_id=build_profile_public_id("user", account_id),
        region="",
        district="",
        mahalla="",
        latitude=None,
        longitude=None,
        location_exact=False,
        avatar_object_key="",
        avatar_x=50,
        avatar_y=50,
        avatar_zoom=1,
        followers_count=0,
        following_count=0,
        has_business=False,
        dashboard_snapshot={},
        recent_activity=[],
        specialist_profile={},
        cabinet_payload={},
    )


def _business(account_id: int) -> BusinessProfile:
    return BusinessProfile(
        account_id=account_id,
        name="Turon Savdo",
        phone="",
        description="",
        public_username=f"shop{account_id}",
        public_id=build_profile_public_id("business", account_id),
        direction="Savdo",
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
    )


@pytest.fixture
def follows():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            ProfileLink.__table__,
            ProfileFollow.__table__,
        ),
    )
    with Session(engine) as seed:
        seed.add_all((
            _account(READER, AccountType.USER),
            _account(AUTHOR, AccountType.USER),
            _account(SHOP, AccountType.BUSINESS),
            _account(READER_SHOP, AccountType.BUSINESS),
        ))
        seed.flush()
        seed.add_all((
            _user(READER, "Ali"),
            _user(AUTHOR, "Vali"),
            _business(SHOP),
            _business(READER_SHOP),
            ProfileLink(
                user_account_id=READER,
                business_account_id=READER_SHOP,
                created_at=NOW,
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    yield FollowService(sessions, now=lambda: STAMP), engine
    engine.dispose()


def _body(kind: str, account_id: int) -> FollowToggle:
    return FollowToggle(
        kind=kind,
        public_id=build_profile_public_id(kind, account_id),
    )


async def test_first_call_follows_and_second_unfollows(follows):
    """v1656 kabi bitta amal — bosgan sari holat almashadi."""
    service, engine = follows

    first = await service.toggle(account_id=READER, body=_body("business", SHOP))
    assert first.following is True
    assert first.followers == 1

    second = await service.toggle(account_id=READER, body=_body("business", SHOP))
    assert second.following is False
    assert second.followers == 0

    with Session(engine) as check:
        assert check.scalar(select(func.count(ProfileFollow.id))) == 0


async def test_counters_follow_the_table(follows):
    service, engine = follows

    await service.toggle(account_id=READER, body=_body("business", SHOP))
    await service.toggle(account_id=AUTHOR, body=_body("business", SHOP))

    with Session(engine) as check:
        shop = check.get(BusinessProfile, SHOP)
        reader = check.get(UserProfile, READER)
        assert shop.followers_count == 2
        assert reader.following_count == 1

    await service.toggle(account_id=AUTHOR, body=_body("business", SHOP))

    with Session(engine) as check:
        assert check.get(BusinessProfile, SHOP).followers_count == 1
        assert check.get(UserProfile, AUTHOR).following_count == 0


async def test_user_can_follow_another_user(follows):
    service, engine = follows

    result = await service.toggle(account_id=READER, body=_body("user", AUTHOR))

    assert result.following is True
    with Session(engine) as check:
        row = check.scalars(select(ProfileFollow)).one()
        assert row.target_kind == "user"
        assert row.target_account_id == AUTHOR


async def test_self_follow_is_rejected(follows):
    service, _engine = follows

    with pytest.raises(ApiError) as error:
        await service.toggle(account_id=READER, body=_body("user", READER))

    assert error.value.code == "follow_self_forbidden"


async def test_owner_cannot_follow_own_business(follows):
    """v1656: biznes egasining o'z profiliga obuna bo'lishi taqiqlangan."""
    service, _engine = follows

    with pytest.raises(ApiError) as forward:
        await service.toggle(
            account_id=READER,
            body=_body("business", READER_SHOP),
        )
    with pytest.raises(ApiError) as backward:
        await service.toggle(
            account_id=READER_SHOP,
            body=_body("user", READER),
        )

    assert forward.value.code == "follow_self_forbidden"
    assert backward.value.code == "follow_self_forbidden"


async def test_unknown_target_is_rejected(follows):
    service, _engine = follows

    with pytest.raises(ApiError) as error:
        await service.toggle(
            account_id=READER,
            body=FollowToggle(
                kind="business",
                public_id="b_0000000000000000",
            ),
        )

    assert error.value.code == "follow_target_not_found"


async def test_business_account_can_follow(follows):
    """Biznes kabineti ham obuna bo'la oladi — v1656dagi kabi."""
    service, engine = follows

    result = await service.toggle(
        account_id=SHOP,
        body=_body("user", AUTHOR),
    )

    assert result.following is True
    with Session(engine) as check:
        assert check.get(BusinessProfile, SHOP).following_count == 1
        assert check.get(UserProfile, AUTHOR).followers_count == 1


async def test_is_following_reports_state(follows):
    service, _engine = follows
    await service.toggle(account_id=READER, body=_body("business", SHOP))

    async with service._session_factory() as session:
        followed = await service.is_following(
            session,
            account_id=READER,
            target_id=SHOP,
        )
        guest = await service.is_following(
            session,
            account_id=None,
            target_id=SHOP,
        )
        other = await service.is_following(
            session,
            account_id=AUTHOR,
            target_id=SHOP,
        )

    assert followed is True
    assert guest is False
    assert other is False
