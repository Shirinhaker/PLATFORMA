"""To'lov oqimi: tarif → chek → so'rov → tasdiqlash → obuna.

Bu oqim umuman ko'chirilmagan edi, shu sababli obuna sotib olish
tugmasi bosilganda to'lov oynasi ochilmasdi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.db.base import Base
from app.payments.model import (
    BusinessSubscription,
    PaymentAttempt,
    PaymentEvent,
    PaymentMethod,
    PaymentRequest,
    PlatformPrice,
)
from app.payments.schemas import (
    PaymentDecision,
    PaymentReceipt,
    PaymentRequestCreate,
    PaymentResubmit,
)
from app.payments.service import PaymentService


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
STAMP = 1785200000
SHOP = 7
ADMIN = 9
RECEIPT = PaymentReceipt(
    object_key="private/business/7/receipt/a.png",
    filename="chek.png",
    mime="image/png",
    sha256="a" * 64,
)


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


@pytest.fixture
def payments():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            PlatformPrice.__table__,
            PaymentMethod.__table__,
            PaymentRequest.__table__,
            PaymentAttempt.__table__,
            PaymentEvent.__table__,
            BusinessSubscription.__table__,
        ),
    )
    with Session(engine) as seed:
        seed.add_all((
            Account(
                id=SHOP,
                account_type=AccountType.BUSINESS,
                login="shop",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            ),
            Account(
                id=ADMIN,
                account_type=AccountType.BUSINESS,
                login="admin",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            ),
            PaymentMethod(
                id=1,
                method_type="manual_card",
                name="Bank kartasi",
                details={},
                recipient_name="",
                instructions="",
                sort_order=0,
                active=1,
                created_at=STAMP,
                updated_at=STAMP,
            ),
        ))
        seed.add_all(
            PlatformPrice(
                price_code=code,
                amount_uzs=amount,
                service_type="subscription",
                config={"plan_code": plan, "duration_months": months},
                active=1,
                created_at=STAMP,
                updated_at=STAMP,
            )
            for code, plan, months, amount in (
                ("subscription_plus_1m", "plus", 1, 99_000),
                ("subscription_pro_3m", "pro", 3, 419_000),
            )
        )
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    yield PaymentService(sessions, now=lambda: STAMP), engine
    engine.dispose()


def _body(code: str = "subscription_plus_1m", plan: str = "plus", months: int = 1):
    return PaymentRequestCreate(
        service_type="subscription",
        price_code=code,
        payment_method_id=1,
        receipt=RECEIPT,
        plan_code=plan,
        duration_months=months,
    )


async def _make_request(service):
    return await service.create(
        account_id=SHOP,
        account_type=AccountType.BUSINESS,
        body=_body(),
    )


async def test_catalog_lists_active_prices_and_methods(payments):
    service, _engine = payments

    catalog = await service.catalog()

    assert {price.price_code for price in catalog.prices} == {
        "subscription_plus_1m",
        "subscription_pro_3m",
    }
    assert catalog.prices[0].plan_code in {"plus", "pro"}
    assert [method.name for method in catalog.methods] == ["Bank kartasi"]


async def test_request_stores_price_snapshot_and_first_attempt(payments):
    service, engine = payments

    created = await _make_request(service)

    assert created.status == "pending"
    assert created.amount == 99_000
    assert created.request_code.startswith("PAY-")
    assert [attempt.attempt_no for attempt in created.attempts] == [1]
    with Session(engine) as check:
        request = check.scalars(select(PaymentRequest)).one()
        attempt = check.scalars(select(PaymentAttempt)).one()
        event = check.scalars(select(PaymentEvent)).one()
        assert request.unit_price_snapshot == 99_000
        assert attempt.receipt_object_key == RECEIPT.object_key
        assert event.to_status == "pending"


async def test_plan_parameters_must_match_the_price_code(payments):
    """v1656: tarif kodi va parametrlar mos kelishi shart."""
    service, _engine = payments

    with pytest.raises(ApiError) as error:
        await service.create(
            account_id=SHOP,
            account_type=AccountType.BUSINESS,
            body=_body("subscription_plus_1m", plan="pro", months=1),
        )

    assert error.value.code == "payment_price_mismatch"


async def test_inactive_price_is_rejected(payments):
    service, engine = payments
    with Session(engine) as seed:
        price = seed.scalars(
            select(PlatformPrice).where(
                PlatformPrice.price_code == "subscription_plus_1m"
            )
        ).one()
        price.active = 0
        seed.commit()

    with pytest.raises(ApiError) as error:
        await _make_request(service)

    assert error.value.code == "payment_price_inactive"


async def test_approval_activates_the_subscription(payments):
    service, engine = payments
    created = await _make_request(service)

    approved = await service.review(
        payment_id=created.id,
        reviewer_account_id=ADMIN,
        decision="approved",
        body=PaymentDecision(),
    )

    assert approved.status == "approved"
    with Session(engine) as check:
        subscription = check.scalars(select(BusinessSubscription)).one()
        attempt = check.scalars(select(PaymentAttempt)).one()
        assert subscription.plan_code == "plus"
        assert subscription.status == "active"
        assert subscription.expires_at > subscription.starts_at
        assert subscription.payment_request_id == created.id
        assert attempt.review_status == "approved"


async def test_rejection_requires_a_reason(payments):
    service, _engine = payments
    created = await _make_request(service)

    with pytest.raises(ApiError) as error:
        await service.review(
            payment_id=created.id,
            reviewer_account_id=ADMIN,
            decision="rejected",
            body=PaymentDecision(reason="  "),
        )

    assert error.value.code == "payment_reason_required"


async def test_second_review_is_rejected(payments):
    """Holat allaqachon o'zgargan bo'lsa ikkinchi qaror qabul qilinmaydi."""
    service, _engine = payments
    created = await _make_request(service)
    await service.review(
        payment_id=created.id,
        reviewer_account_id=ADMIN,
        decision="approved",
        body=PaymentDecision(),
    )

    with pytest.raises(ApiError) as error:
        await service.review(
            payment_id=created.id,
            reviewer_account_id=ADMIN,
            decision="rejected",
            body=PaymentDecision(reason="xato"),
        )

    assert error.value.code == "payment_already_reviewed"


async def test_resubmit_supersedes_the_old_receipt(payments):
    service, engine = payments
    created = await _make_request(service)
    await service.review(
        payment_id=created.id,
        reviewer_account_id=ADMIN,
        decision="rejected",
        body=PaymentDecision(reason="Chek xira"),
    )

    again = await service.resubmit(
        account_id=SHOP,
        payment_id=created.id,
        body=PaymentResubmit(receipt=RECEIPT.model_copy(
            update={"sha256": "b" * 64}
        )),
    )

    assert again.status == "pending"
    assert again.public_reason == ""
    with Session(engine) as check:
        attempts = check.scalars(
            select(PaymentAttempt).order_by(PaymentAttempt.attempt_no)
        ).all()
        assert [row.attempt_no for row in attempts] == [1, 2]
        assert attempts[0].review_status == "rejected"
        assert attempts[1].review_status == "pending"


async def test_same_plan_extends_the_existing_subscription(payments):
    """v1656: bir xil tarif tugash sanasidan davom etadi."""
    service, engine = payments
    first = await _make_request(service)
    await service.review(
        payment_id=first.id,
        reviewer_account_id=ADMIN,
        decision="approved",
        body=PaymentDecision(),
    )
    with Session(engine) as check:
        first_expiry = check.scalars(
            select(BusinessSubscription.expires_at)
        ).one()

    second = await _make_request(service)
    await service.review(
        payment_id=second.id,
        reviewer_account_id=ADMIN,
        decision="approved",
        body=PaymentDecision(),
    )

    with Session(engine) as check:
        rows = check.scalars(
            select(BusinessSubscription).order_by(BusinessSubscription.id)
        ).all()
        assert [row.status for row in rows] == ["superseded", "active"]
        assert rows[1].expires_at > first_expiry


async def test_my_payments_lists_newest_first(payments):
    service, _engine = payments
    await _make_request(service)
    await _make_request(service)

    rows = await service.list_mine(account_id=SHOP)

    assert len(rows) == 2
    assert rows[0].id > rows[1].id
    assert all(row.attempts for row in rows)


async def test_other_account_cannot_resubmit(payments):
    service, _engine = payments
    created = await _make_request(service)

    with pytest.raises(ApiError) as error:
        await service.resubmit(
            account_id=ADMIN,
            payment_id=created.id,
            body=PaymentResubmit(receipt=RECEIPT),
        )

    assert error.value.code == "payment_not_found"
