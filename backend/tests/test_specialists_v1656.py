from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.db.base import Base
from app.specialists.model import (
    SpecialistCredential,
    SpecialistOffer,
    SpecialistPortfolio,
    SpecialistProfile,
)
from app.specialists.schemas import (
    SpecialistCredentialCreate,
    SpecialistOfferWrite,
    SpecialistPortfolioCreate,
    SpecialistProfileWrite,
)
from app.specialists.service import SpecialistService


NOW = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, sync: Session):
        self.sync = sync

    async def get(self, model, identity, **kwargs):
        return self.sync.get(model, identity, **kwargs)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    def add(self, row):
        self.sync.add(row)

    async def delete(self, row):
        self.sync.delete(row)

    async def flush(self):
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def account(account_id: int) -> Account:
    return Account(
        id=account_id,
        account_type=AccountType.USER,
        login=f"specialist-user-{account_id}",
        password_hash="hash",
        status="active",
        telegram_user_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_specialist_service_preserves_v1656_profile_and_media_limits():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            SpecialistProfile.__table__,
            SpecialistCredential.__table__,
            SpecialistOffer.__table__,
            SpecialistPortfolio.__table__,
        ),
    )
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE reviews ("
            "id INTEGER PRIMARY KEY, target_kind VARCHAR(16) NOT NULL, "
            "target_account_id BIGINT NOT NULL)"
        ))
    sync = Session(engine, expire_on_commit=False)
    sync.add_all((account(7), account(8)))
    sync.commit()
    store = AsyncStore(sync)
    deleted: list[str] = []

    @asynccontextmanager
    async def sessions():
        yield store

    service = SpecialistService(
        sessions,
        image_url_provider=lambda key: f"signed:{key}",
        object_deleter=deleted.append,
        now_provider=lambda: NOW,
    )

    empty = await service.get(user_account_id=7)
    assert empty.exists is False
    assert empty.credentials == []

    with pytest.raises(ApiError) as required:
        await service.update_profile(
            user_account_id=7,
            body=SpecialistProfileWrite(profession="", visible=True),
        )
    assert required.value.message == "Ko'rinish uchun kasb/yo'nalish kiritilishi shart."

    saved = await service.update_profile(
        user_account_id=7,
        body=SpecialistProfileWrite(
            profession="Santexnik",
            description="10 yillik tajriba",
            visible=True,
            latitude=37.8389,
            longitude=67.5834,
        ),
    )
    assert saved.exists is True
    assert saved.profession == "Santexnik"
    assert (saved.latitude, saved.longitude) == (37.8389, 67.5834)

    credential_key = "private/user/7/specialist_credential/diplom.webp"
    credential = await service.add_credential(
        user_account_id=7,
        body=SpecialistCredentialCreate(object_key=credential_key),
    )
    offer_key = "private/user/7/specialist_offer_image/service.webp"
    offer = await service.create_offer(
        user_account_id=7,
        body=SpecialistOfferWrite(
            kind="service",
            name="Ta'mirlash",
            price_text="100 000 so'm",
            note="Uyga borib",
            image_object_key=offer_key,
        ),
    )
    portfolio_key = "private/user/7/specialist_portfolio_video/work.mp4"
    portfolio = await service.add_portfolio(
        user_account_id=7,
        body=SpecialistPortfolioCreate(
            media_type="video",
            object_key=portfolio_key,
        ),
    )

    loaded = await service.get(user_account_id=7)
    assert loaded.credentials[0].image_url == f"signed:{credential_key}"
    assert loaded.offers[0].name == "Ta'mirlash"
    assert loaded.portfolio[0].media_type == "video"

    with pytest.raises(ApiError) as foreign:
        await service.add_credential(
            user_account_id=7,
            body=SpecialistCredentialCreate(
                object_key="private/user/8/specialist_credential/stolen.webp",
            ),
        )
    assert foreign.value.status_code == 403

    await service.delete_credential(user_account_id=7, row_id=credential.id)
    await service.delete_offer(user_account_id=7, row_id=offer.id)
    await service.delete_portfolio(user_account_id=7, row_id=portfolio.id)
    assert deleted == [credential_key, offer_key, portfolio_key]

    sync.close()
    engine.dispose()


def test_specialist_tables_are_tenant_indexed_and_constrained():
    assert SpecialistProfile.__table__.c.user_account_id.foreign_keys
    assert SpecialistCredential.__table__.c.user_account_id.foreign_keys
    assert SpecialistOffer.__table__.c.user_account_id.foreign_keys
    assert SpecialistPortfolio.__table__.c.user_account_id.foreign_keys
    indexes = {
        index.name
        for model in (SpecialistProfile, SpecialistCredential, SpecialistOffer, SpecialistPortfolio)
        for index in model.__table__.indexes
    }
    assert "ix_specialist_profiles_visible_location" in indexes
    assert "uq_specialist_credentials_user_legacy" in indexes
    assert "uq_specialist_offers_user_legacy" in indexes
    assert "uq_specialist_portfolio_user_legacy" in indexes
