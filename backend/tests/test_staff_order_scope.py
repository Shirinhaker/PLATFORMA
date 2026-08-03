from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.core.errors import ApiError
from app.orders.repository import OrderRepository
from app.orders.service import OrderService


class EmptyScalars:
    def all(self):
        return []


class CapturingSession:
    def __init__(self):
        self.statement = None

    async def scalars(self, statement):
        self.statement = statement
        return EmptyScalars()

    async def rollback(self):
        return None


async def test_staff_inbox_query_filters_categories_before_loading_rows():
    session = CapturingSession()

    rows = await OrderRepository().list_for_side(
        session,
        account_id=7,
        side="provider",
        allowed_categories=frozenset({"service"}),
    )

    assert rows == []
    compiled = session.statement.compile()
    assert "orders.order_category IN" in str(compiled)
    assert set(compiled.params["order_category_1"]) == {"service"}


async def test_staff_order_detail_rechecks_provider_and_category():
    session = CapturingSession()

    @asynccontextmanager
    async def sessions():
        yield session

    class Repository:
        order = SimpleNamespace(
            provider_account_id=7,
            order_category="service",
        )

        async def owned_order(self, *_args, **_kwargs):
            return self.order

    repository = Repository()
    service = OrderService(sessions, lambda _key: "", repository=repository)

    await service.assert_staff_provider_access(
        order_id=41,
        account_id=7,
        allowed_categories=frozenset({"service"}),
    )

    repository.order = SimpleNamespace(
        provider_account_id=7,
        order_category="product",
    )
    with pytest.raises(ApiError) as wrong_category:
        await service.assert_staff_provider_access(
            order_id=41,
            account_id=7,
            allowed_categories=frozenset({"service"}),
        )
    assert wrong_category.value.code == "staff_order_forbidden"

    repository.order = SimpleNamespace(
        provider_account_id=8,
        order_category="service",
    )
    with pytest.raises(ApiError) as wrong_business:
        await service.assert_staff_provider_access(
            order_id=41,
            account_id=7,
            allowed_categories=frozenset({"service"}),
        )
    assert wrong_business.value.code == "staff_order_forbidden"
