from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.expenses.model import Expense, ExpenseCategory
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import (
    ExpenseCategoryCreate,
    ExpenseCategoryCreated,
    ExpenseCategoryList,
    ExpenseCreate,
    ExpenseCreated,
    ExpenseDayRead,
    ExpenseRead,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
UZBEKISTAN_TZ = ZoneInfo("Asia/Tashkent")
DEFAULT_EXPENSE_CATEGORIES = (
    "Ijara",
    "Kommunal",
    "Maosh",
    "Transport",
    "Tovar xaridi",
    "Soliq",
    "Boshqa",
)


class ExpenseService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: ExpenseRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or ExpenseRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def list_categories(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> ExpenseCategoryList:
        self._require_expenses(permissions)
        async with self._session_factory() as session:
            extra = await self._repository.category_names(
                session,
                business_account_id=business_account_id,
            )
            await session.rollback()
        categories = list(DEFAULT_EXPENSE_CATEGORIES)
        for name in extra:
            if name not in categories:
                categories.append(name)
        return ExpenseCategoryList(
            categories=categories,
            defaults=list(DEFAULT_EXPENSE_CATEGORIES),
        )

    async def create_category(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: ExpenseCategoryCreate,
    ) -> ExpenseCategoryCreated:
        self._require_expenses(permissions)
        if body.name in DEFAULT_EXPENSE_CATEGORIES:
            return ExpenseCategoryCreated(exists=True)
        async with self._session_factory() as session:
            try:
                existing = await self._repository.category(
                    session,
                    business_account_id=business_account_id,
                    name=body.name,
                )
                if existing is not None:
                    await session.rollback()
                    return ExpenseCategoryCreated(exists=True)
                session.add(ExpenseCategory(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    name=body.name,
                    created_at=self._now_provider(),
                ))
                await session.flush()
                await session.commit()
                return ExpenseCategoryCreated(exists=False)
            except IntegrityError:
                # Another request may have created the same business-scoped
                # category after the lookup but before this insert.
                await session.rollback()
                return ExpenseCategoryCreated(exists=True)
            except Exception:
                await session.rollback()
                raise

    async def list_expenses(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        day: date | None,
    ) -> ExpenseDayRead:
        self._require_expenses(permissions)
        selected_day, start, end = self._day_bounds(day)
        async with self._session_factory() as session:
            rows = await self._repository.expenses_between(
                session,
                business_account_id=business_account_id,
                start=start,
                end=end,
            )
            result: list[ExpenseRead] = []
            total = 0
            by_category: dict[str, int] = {}
            for expense in rows:
                total += expense.amount
                by_category[expense.category] = (
                    by_category.get(expense.category, 0) + expense.amount
                )
                result.append(ExpenseRead(
                    id=expense.id,
                    category=expense.category,
                    amount=expense.amount,
                    note=expense.note,
                    source=expense.source,
                    who=expense.actor_name_snapshot,
                    created_at=expense.created_at,
                ))
            await session.rollback()
            return ExpenseDayRead(
                day=selected_day,
                expenses=result,
                total=total,
                by_category=by_category,
            )

    async def create_expense(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        actor_name: str,
        permissions: tuple[str, ...] | None,
        body: ExpenseCreate,
    ) -> ExpenseCreated:
        self._require_expenses(permissions)
        async with self._session_factory() as session:
            try:
                expense = Expense(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    category=body.category or "Boshqa",
                    amount=body.amount,
                    note=body.note,
                    source="manual",
                    inventory_stock_move_id=None,
                    performed_by_staff_id=actor_staff_id,
                    actor_name_snapshot=actor_name[:160],
                    created_at=self._now_provider(),
                )
                session.add(expense)
                await session.flush()
                await session.commit()
                return ExpenseCreated(id=expense.id)
            except Exception:
                await session.rollback()
                raise

    async def delete_expense(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        expense_id: int,
    ) -> None:
        self._require_expenses(permissions)
        async with self._session_factory() as session:
            try:
                expense = await self._repository.expense(
                    session,
                    business_account_id=business_account_id,
                    expense_id=expense_id,
                    lock=True,
                )
                if expense is None:
                    raise ApiError(
                        404,
                        "expense_not_found",
                        "Xarajat topilmadi.",
                    )
                if expense.source == "stock":
                    raise ApiError(
                        400,
                        "expense_stock_locked",
                        "Bu xarajat ombor kirimidan — uni Ombordagi kirimni "
                        "o‘chirsangiz yo‘qoladi.",
                    )
                await session.delete(expense)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_stock_expense_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        inventory_stock_move_id: int,
        amount: int,
        note: str,
        actor_staff_id: int | None,
        actor_name: str,
        created_at: datetime,
    ) -> Expense:
        existing = await self._repository.stock_expense(
            session,
            business_account_id=business_account_id,
            inventory_stock_move_id=inventory_stock_move_id,
            lock=True,
        )
        if existing is not None:
            return existing
        if amount <= 0:
            raise ApiError(422, "expense_amount_required", "Summa kiritilmadi.")
        expense = Expense(
            business_account_id=business_account_id,
            legacy_source_id=None,
            category="Tovar xaridi",
            amount=amount,
            note=note[:200],
            source="stock",
            inventory_stock_move_id=inventory_stock_move_id,
            performed_by_staff_id=actor_staff_id,
            actor_name_snapshot=actor_name[:160],
            created_at=created_at,
        )
        session.add(expense)
        await session.flush()
        return expense

    async def delete_stock_expense_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        inventory_stock_move_id: int,
    ) -> None:
        expense = await self._repository.stock_expense(
            session,
            business_account_id=business_account_id,
            inventory_stock_move_id=inventory_stock_move_id,
            lock=True,
        )
        if expense is not None:
            await session.delete(expense)
            await session.flush()

    def _day_bounds(self, value: date | None) -> tuple[date, datetime, datetime]:
        selected = value or self._now_provider().astimezone(UZBEKISTAN_TZ).date()
        local_start = datetime.combine(selected, time.min, tzinfo=UZBEKISTAN_TZ)
        start = local_start.astimezone(UTC)
        return selected, start, start + timedelta(days=1)

    @staticmethod
    def _require_expenses(permissions: tuple[str, ...] | None) -> None:
        if permissions is not None and "expenses" not in permissions:
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )
