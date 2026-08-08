"""E'lon to'lovsiz chiqmaydi.

v1656da `listing_publish` tarifi bor edi, lekin hech qanday oqim uni
ishlatmasdi — e'lon darhol `active` bo'lib yaratilardi. Egasining
qarori bilan endi to'lov talab qilinadi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.db.base import Base
from app.listings.activation import ListingActivationService
from app.listings.model import Listing, ListingMedia, ListingSave
from app.listings.schemas import ListingCreate
from app.listings.service import ListingService
from app.payments.model import (
    BusinessSubscription,
    PaymentAttempt,
    PaymentEvent,
    PaymentMethod,
    PaymentRequest,
    PlatformPrice,
)
from app.payments.schemas import PaymentReceipt, PaymentRequestCreate
from app.payments.service import PaymentService
from app.profiles.model import UserProfile


NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
STAMP = 1_785_600_000
OWNER = 5
STRANGER = 9
ADMIN_TG = 777
RECEIPT = PaymentReceipt(
    object_key="private/user/5/receipt/a.png",
    filename="chek.png",
    mime="image/png",
    sha256="b" * 64,
)


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    def add_all(self, values):
        self.sync.add_all(values)

    def get_bind(self):
        return self.sync.get_bind()

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)

    async def delete(self, value):
        self.sync.delete(value)

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


def _account(identifier: int) -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.USER,
        login=f"user{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _profile(identifier: int) -> UserProfile:
    return UserProfile(
        account_id=identifier,
        name=f"Foydalanuvchi {identifier}",
        phone="",
        public_username=f"user{identifier}",
        avatar_object_key="",
        avatar_x=50,
        avatar_y=50,
        avatar_zoom=1,
        cabinet_payload={},
    )


@pytest.fixture
def listing_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            Listing.__table__,
            ListingMedia.__table__,
            ListingSave.__table__,
            PlatformPrice.__table__,
            PaymentMethod.__table__,
            PaymentRequest.__table__,
            PaymentAttempt.__table__,
            PaymentEvent.__table__,
            BusinessSubscription.__table__,
        ),
    )
    with Session(engine, expire_on_commit=False) as seed:
        seed.add_all((
            _account(OWNER), _account(STRANGER),
            _profile(OWNER), _profile(STRANGER),
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
            # v1656 `payments.py:57` — e'lon joylash 10 000 so'm.
            PlatformPrice(
                price_code="listing_publish",
                amount_uzs=10_000,
                service_type="listing",
                config={},
                active=1,
                created_at=STAMP,
                updated_at=STAMP,
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    service = ListingService(sessions, lambda key: f"/media/{key}")
    activation = ListingActivationService(sessions)
    payments = PaymentService(
        sessions, now=lambda: STAMP, listing_service=activation,
    )
    try:
        yield service, activation, sessions, engine, payments
    finally:
        engine.dispose()


def _body(title: str = "Nexia sotiladi") -> ListingCreate:
    return ListingCreate(
        cat="moshina",
        title=title,
        price="Kelishilgan",
        descr="Yili 2024",
        address="Toshkent",
        lat=41.3,
        lng=69.2,
        visibility="all",
        media=[],
    )


async def test_new_listing_is_not_public_until_paid(listing_context):
    service, _activation, _sessions, engine, _payments = listing_context

    created = await service.create(
        account_id=OWNER, account_type=AccountType.USER, body=_body(),
    )
    assert created.status == "payment_pending"

    public = await service.list_public(
        category="moshina", query="", current_account_id=None,
    )
    assert public == []
    with Session(engine) as check:
        assert check.scalar(select(Listing.status)) == "payment_pending"


async def test_owner_still_sees_the_pending_listing(listing_context):
    """Egasi o'z e'lonini ko'radi va holatini biladi."""
    service, _activation, _sessions, _engine, _payments = listing_context
    await service.create(
        account_id=OWNER, account_type=AccountType.USER, body=_body(),
    )

    mine = await service.list_owner(
        account_id=OWNER, account_type=AccountType.USER,
    )
    assert len(mine) == 1
    assert mine[0].status == "payment_pending"


async def test_payment_publishes_the_listing(listing_context):
    service, activation, sessions, engine, _payments = listing_context
    await service.create(
        account_id=OWNER, account_type=AccountType.USER, body=_body(),
    )
    with Session(engine) as check:
        listing_id = check.scalar(select(Listing.id))

    async with sessions() as session:
        await activation.activate_paid(
            session, listing_id=listing_id, account_id=OWNER, now=STAMP,
        )
        await session.commit()

    public = await service.list_public(
        category="moshina", query="", current_account_id=None,
    )
    assert [row.title for row in public] == ["Nexia sotiladi"]


async def test_second_activation_is_refused(listing_context):
    service, activation, sessions, engine, _payments = listing_context
    await service.create(
        account_id=OWNER, account_type=AccountType.USER, body=_body(),
    )
    with Session(engine) as check:
        listing_id = check.scalar(select(Listing.id))

    async with sessions() as session:
        await activation.activate_paid(
            session, listing_id=listing_id, account_id=OWNER, now=STAMP,
        )
        await session.commit()

    async with sessions() as session:
        with pytest.raises(ApiError) as failure:
            await activation.activate_paid(
                session, listing_id=listing_id, account_id=OWNER, now=STAMP,
            )
        assert failure.value.code == "listing_not_pending"


def _payment_body(public_id: str) -> PaymentRequestCreate:
    return PaymentRequestCreate(
        service_type="listing",
        price_code="listing_publish",
        payment_method_id=1,
        receipt=RECEIPT,
        target_public_id=public_id,
    )


async def test_payment_request_to_approval_publishes_the_listing(listing_context):
    """Uchidan-uchiga: chek → admin tasdig'i → e'lon ko'rinadi."""
    service, _activation, _sessions, _engine, payments = listing_context
    created = await service.create(
        account_id=OWNER, account_type=AccountType.USER, body=_body(),
    )

    request = await payments.create(
        account_id=OWNER,
        account_type=AccountType.USER,
        body=_payment_body(created.public_id),
    )
    assert request.amount == 10_000

    await payments.review(
        payment_id=request.id,
        admin_telegram_id=ADMIN_TG,
        decision="approved",
    )

    public = await service.list_public(
        category="moshina", query="", current_account_id=None,
    )
    assert [row.public_id for row in public] == [created.public_id]


async def test_rejected_payment_keeps_the_listing_hidden(listing_context):
    service, _activation, _sessions, engine, payments = listing_context
    created = await service.create(
        account_id=OWNER, account_type=AccountType.USER, body=_body(),
    )
    request = await payments.create(
        account_id=OWNER,
        account_type=AccountType.USER,
        body=_payment_body(created.public_id),
    )

    await payments.review(
        payment_id=request.id,
        admin_telegram_id=ADMIN_TG,
        decision="rejected",
        reason="Chek o‘qilmadi.",
    )

    with Session(engine) as check:
        assert check.scalar(select(Listing.status)) == "payment_pending"


async def test_payment_for_someone_elses_listing_is_refused(listing_context):
    """Begona e'lonning kalitini yuborish to'lov so'rovi yaratmaydi."""
    service, _activation, _sessions, engine, payments = listing_context
    created = await service.create(
        account_id=OWNER, account_type=AccountType.USER, body=_body(),
    )

    with pytest.raises(ApiError) as failure:
        await payments.create(
            account_id=STRANGER,
            account_type=AccountType.USER,
            body=_payment_body(created.public_id),
        )

    assert failure.value.code == "listing_not_found"
    with Session(engine) as check:
        assert check.scalar(select(func.count()).select_from(PaymentRequest)) == 0


async def test_listing_payment_without_a_target_is_refused(listing_context):
    _service, _activation, _sessions, _engine, payments = listing_context

    with pytest.raises(ApiError) as failure:
        await payments.create(
            account_id=OWNER,
            account_type=AccountType.USER,
            body=PaymentRequestCreate(
                service_type="listing",
                price_code="listing_publish",
                payment_method_id=1,
                receipt=RECEIPT,
            ),
        )

    assert failure.value.code == "listing_target_required"


async def test_stranger_payment_does_not_publish(listing_context):
    """Boshqa akkauntning to'lovi begona e'lonni chiqarmaydi."""
    service, activation, sessions, engine, _payments = listing_context
    await service.create(
        account_id=OWNER, account_type=AccountType.USER, body=_body(),
    )
    with Session(engine) as check:
        listing_id = check.scalar(select(Listing.id))

    async with sessions() as session:
        with pytest.raises(ApiError) as failure:
            await activation.activate_paid(
                session, listing_id=listing_id, account_id=STRANGER, now=STAMP,
            )
        assert failure.value.code == "listing_owner_mismatch"

    with Session(engine) as check:
        assert check.scalar(select(Listing.status)) == "payment_pending"
