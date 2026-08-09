from importlib import import_module
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogItem  # noqa: F401
from app.core.errors import ApiError
from app.db.base import Base
from app.debt_ledger.model import Debtor  # noqa: F401
from app.listings.model import Listing  # noqa: F401
from app.orders.model import Order
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_ids import build_profile_public_id
from app.reviews.model import Review
from app.reviews.schemas import ReviewReplyWrite, ReviewTargetKind, ReviewWrite
from app.reviews.service import ReviewService


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)


def module(name: str):
    return import_module(f"app.reviews.{name}")


def test_review_model_keeps_one_rating_per_reviewer_and_target():
    model = module("model")

    assert model.Review.__tablename__ == "reviews"
    assert model.Review.__table__.c.target_account_id.foreign_keys
    assert model.Review.__table__.c.reviewer_account_id.foreign_keys
    assert model.Review.__table__.c.order_id.foreign_keys
    indexes = {index.name for index in model.Review.__table__.indexes}
    assert "uq_reviews_target_reviewer" in indexes
    assert "ix_reviews_target_created" in indexes
    assert "uq_reviews_legacy_source" in indexes


def test_review_schemas_match_v1656_star_comment_and_reply_limits():
    schemas = module("schemas")

    body = schemas.ReviewWrite(
        target_kind="specialist",
        target_public_id="u_0123456789abcdef",
        stars=5,
        comment="  Juda yaxshi  ",
    )
    assert body.comment == "Juda yaxshi"
    assert body.target_kind.value == "specialist"

    reply = schemas.ReviewReplyWrite(reply="  Rahmat  ")
    assert reply.reply == "Rahmat"

    with pytest.raises(ValidationError):
        schemas.ReviewWrite(
            target_kind="business",
            target_public_id="b_0123456789abcdef",
            stars=0,
            comment="",
        )
    with pytest.raises(ValidationError):
        schemas.ReviewWrite(
            target_kind="business",
            target_public_id="u_0123456789abcdef",
            stars=5,
            comment="",
        )
    with pytest.raises(ValidationError):
        schemas.ReviewReplyWrite(reply=" ")


def test_review_average_matches_v1656_one_decimal_summary():
    service = module("service")

    assert service.review_average(0, 0) == 0
    assert service.review_average(9, 2) == 4.5
    assert service.review_average(13, 3) == 4.3


def test_reviews_router_exposes_public_customer_and_owner_flows():
    routes = {
        (route.path, method)
        for route in module("router").router.routes
        for method in (route.methods or set())
    }

    assert ("/api/v1/reviews/received", "GET") in routes
    assert ("/api/v1/reviews/{target_kind}/{target_public_id}", "GET") in routes
    assert ("/api/v1/reviews", "POST") in routes
    assert ("/api/v1/reviews/{target_kind}/{target_public_id}", "DELETE") in routes
    assert ("/api/v1/reviews/{review_id}/reply", "PUT") in routes


def test_reviews_migration_backfills_duplicate_legacy_json_idempotently():
    migration = ROOT / "migrations" / "versions" / "0032_reviews.py"
    source = migration.read_text(encoding="utf-8")
    upper = source.upper()

    assert 'revision = "0032_reviews"' in source
    assert 'down_revision = "0031_messages"' in source
    assert '"reviews"' in source
    assert 'op.drop_table("reviews")' in source
    assert "business_reviews" in source
    assert "reviews_received" in source
    assert "reviews_given" in source
    assert "cabinet_records" in source
    assert "cabinet_payload" in source
    assert "legacy_id_map" in source
    assert "user_account" in source
    assert "business_account" in source
    assert "legacy_source_id" in source
    assert "DISTINCT ON" in upper
    assert "ON CONFLICT" in upper
    assert "DO NOTHING" in upper
    assert "rating_sum" in source
    assert "rating_count" in source


def test_reviews_are_registered_in_app_and_alembic_metadata():
    main_source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    env_source = (ROOT / "migrations" / "env.py").read_text(encoding="utf-8")

    assert "review_service" in main_source
    assert "reviews_router" in main_source
    assert "app.include_router(reviews_router)" in main_source
    assert "from app.reviews import model as reviews_model" in env_source


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            if table not in self.sequences:
                highest = self.sync.scalar(select(func.max(value.__table__.c.id)))
                self.sequences[table] = int(highest or 0)
            self.sequences[table] += 1
            value.id = self.sequences[table]
        self.sync.flush()

    async def commit(self):
        self.sync.commit()


def _account(identifier: int, kind: AccountType) -> Account:
    return Account(
        id=identifier,
        account_type=kind,
        login=f"review-{kind.value}-{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _user(identifier: int, name: str, specialist: bool = False) -> UserProfile:
    return UserProfile(
        account_id=identifier,
        public_id=build_profile_public_id("user", identifier),
        name=name,
        phone="",
        public_username=f"reviewer{identifier}",
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
        specialist_rating_sum=0,
        specialist_rating_count=0,
        has_business=False,
        dashboard_snapshot={},
        recent_activity=[],
        specialist_profile={"visible": True, "kasb": "Usta"} if specialist else {},
        cabinet_payload={},
    )


def _business(identifier: int) -> BusinessProfile:
    return BusinessProfile(
        account_id=identifier,
        public_id=build_profile_public_id("business", identifier),
        name="Turon savdo",
        phone="",
        description="",
        public_username=f"shop{identifier}",
        direction="Savdo",
        activity_type="",
        address="",
        latitude=None,
        longitude=None,
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


def _order(identifier: int, provider_id: int, provider_kind: str) -> Order:
    return Order(
        id=identifier,
        legacy_source_id=None,
        customer_account_id=70,
        customer_kind="user",
        customer_name="Ali",
        customer_phone="",
        provider_account_id=provider_id,
        provider_kind=provider_kind,
        provider_name="Xizmat ko‘rsatuvchi",
        provider_phone="",
        item_id=None,
        listing_id=None,
        title="Buyurtma",
        note="",
        phone="",
        order_type="delivery",
        order_category="service" if provider_kind == "user" else "product",
        address="",
        desired_time="",
        delivery_lat=None,
        delivery_lng=None,
        qty=Decimal("1"),
        total_amount=1000,
        status="done",
        payment_status="",
        pay_type="",
        debtor_id=None,
        receipt_message_id=None,
        problem_open=False,
        problem_reason="",
        problem_note="",
        problem_solution="",
        last_event="done",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_review_service_upserts_replies_deletes_and_recomputes_rating():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            ProfileLink.__table__,
            Order.__table__,
            Review.__table__,
        ),
    )
    sync = Session(engine, expire_on_commit=False)
    sync.add_all([
        _account(70, AccountType.USER),
        _account(71, AccountType.USER),
        _account(72, AccountType.USER),
        _account(7, AccountType.BUSINESS),
        _account(8, AccountType.BUSINESS),
        _user(70, "Ali"),
        _user(71, "Usta", specialist=True),
        _user(72, "Vali"),
        _business(7),
        _business(8),
        ProfileLink(
            user_account_id=70,
            business_account_id=8,
            created_at=NOW,
        ),
        _order(101, 7, "business"),
        _order(102, 71, "user"),
    ])
    sync.commit()
    store = AsyncStore(sync)

    @asynccontextmanager
    async def sessions():
        yield store

    service = ReviewService(sessions, now_provider=lambda: NOW)
    business_public_id = build_profile_public_id("business", 7)
    specialist_public_id = build_profile_public_id("user", 71)

    with pytest.raises(ApiError) as no_order:
        await service.save(
            reviewer_account_id=72,
            reviewer_account_type=AccountType.USER,
            body=ReviewWrite(
                target_kind="business",
                target_public_id=business_public_id,
                stars=5,
                comment="Buyurtmasiz",
            ),
        )
    assert no_order.value.status_code == 403

    with pytest.raises(ApiError) as self_review:
        await service.save(
            reviewer_account_id=71,
            reviewer_account_type=AccountType.USER,
            body=ReviewWrite(
                target_kind="specialist",
                target_public_id=specialist_public_id,
                stars=5,
                comment="O‘ziga",
            ),
        )
    assert self_review.value.status_code == 400

    with pytest.raises(ApiError) as own_business:
        await service.save(
            reviewer_account_id=70,
            reviewer_account_type=AccountType.USER,
            body=ReviewWrite(
                target_kind="business",
                target_public_id=build_profile_public_id("business", 8),
                stars=5,
                comment="O‘z do‘koni",
            ),
        )
    assert own_business.value.status_code == 400

    created = await service.save(
        reviewer_account_id=70,
        reviewer_account_type=AccountType.USER,
        body=ReviewWrite(
            target_kind="business",
            target_public_id=business_public_id,
            stars=4,
            comment="Yaxshi",
        ),
    )
    assert (created.avg, created.count) == (4, 1)
    updated = await service.save(
        reviewer_account_id=70,
        reviewer_account_type=AccountType.USER,
        body=ReviewWrite(
            target_kind="business",
            target_public_id=business_public_id,
            stars=5,
            comment="Juda yaxshi",
        ),
    )
    assert (updated.avg, updated.count) == (5, 1)
    assert sync.scalar(select(func.count(Review.id))) == 1

    owner_list = await service.received(
        account_id=7, account_type=AccountType.BUSINESS
    )
    replied = await service.reply(
        review_id=owner_list.reviews[0].id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=ReviewReplyWrite(reply="Rahmat"),
    )
    assert replied.owner_reply == "Rahmat"

    public = await service.public_list(
        target_kind=ReviewTargetKind.BUSINESS,
        target_public_id=business_public_id,
        reviewer_account_id=70,
        reviewer_account_type=AccountType.USER,
    )
    assert public.can_review is True
    assert public.my_review and public.my_review.stars == 5
    assert public.reviews[0].owner_reply == "Rahmat"

    specialist = await service.save(
        reviewer_account_id=70,
        reviewer_account_type=AccountType.USER,
        body=ReviewWrite(
            target_kind="specialist",
            target_public_id=specialist_public_id,
            stars=4,
            comment="Usta yaxshi",
        ),
    )
    assert specialist.count == 1
    specialist_profile = sync.get(UserProfile, 71)
    assert specialist_profile.specialist_rating_sum == 4
    assert specialist_profile.specialist_rating_count == 1

    deleted = await service.delete_own(
        reviewer_account_id=70,
        reviewer_account_type=AccountType.USER,
        target_kind=ReviewTargetKind.BUSINESS,
        target_public_id=business_public_id,
    )
    assert (deleted.avg, deleted.count) == (0, 0)
    business_profile = sync.get(BusinessProfile, 7)
    assert business_profile.rating_sum == 0
    assert business_profile.rating_count == 0

    sync.close()
    engine.dispose()
