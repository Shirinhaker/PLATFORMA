from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.statistics.repository import StatisticsRepository
from app.statistics.schemas import (
    StatisticsCashierRead,
    StatisticsLowStockRead,
    StatisticsPaymentRead,
    StatisticsProductRead,
    StatisticsReportRead,
    StatisticsSourceRead,
    StatisticsSourceSplitRead,
    StatisticsTrendRead,
    StatisticsWaiterRead,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
UZBEKISTAN_TZ = timezone(timedelta(hours=5))
PERIODS = ("kun", "hafta", "oy", "chorak", "yarim", "yil")
MONTH_LABELS = ("Yan", "Fev", "Mar", "Apr", "May", "Iyn", "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek")
WEEKDAY_LABELS = ("Du", "Se", "Cho", "Pa", "Ju", "Sha", "Ya")


@dataclass(frozen=True)
class PeriodBucket:
    start: datetime
    end: datetime
    label: str


@dataclass(frozen=True)
class PeriodWindow:
    period: str
    anchor_date: date
    start: datetime
    end: datetime
    label: str
    buckets: tuple[PeriodBucket, ...]


def _add_months(value: date, months: int) -> date:
    offset = value.month - 1 + months
    return date(value.year + offset // 12, offset % 12 + 1, 1)


def _local_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UZBEKISTAN_TZ)


class StatisticsService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: StatisticsRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or StatisticsRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def report(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        period: str,
        anchor: str,
    ) -> StatisticsReportRead:
        self._require_statistics(permissions)
        window = self._window(period, anchor)
        bucket_bounds = tuple((bucket.start, bucket.end) for bucket in window.buckets)
        async with self._session_factory() as session:
            financial = await self._repository.financial_summary(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
            )
            payment_sources = await self._repository.payment_source_rows(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
            )
            sales_trend = await self._repository.sales_trend_rows(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
                buckets=bucket_bounds,
            )
            product_rows = await self._repository.top_products(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
            )
            cashier_rows = await self._repository.employee_rows(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
            )
            waiter_rows = await self._repository.waiter_rows(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
            )
            expense_rows = await self._repository.expense_rows(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
                buckets=bucket_bounds,
            )
            low_stock_rows = await self._repository.low_stock(
                session,
                business_account_id=business_account_id,
            )

        pay = StatisticsPaymentRead()
        source_split = StatisticsSourceSplitRead()
        sales_count = 0
        for row in payment_sources:
            value = int(row.total or 0)
            pay_key = row.pay_type if row.pay_type in {"naqd", "karta", "qarz"} else "order"
            setattr(pay, pay_key, getattr(pay, pay_key) + value)
            source_key = "internal" if row.source == "dining" else (
                "external" if row.source == "order" else "manual"
            )
            source_value = getattr(source_split, source_key)
            source_value.total += value
            count = int(row.receipt_count if source_key != "manual" else row.line_count)
            source_value.count += count
            sales_count += int(row.line_count or 0)

        bucket_revenue = [0] * len(window.buckets)
        bucket_cogs = [0] * len(window.buckets)
        for row in sales_trend:
            index = int(row.bucket)
            bucket_revenue[index] = int(row.revenue or 0)
            bucket_cogs[index] = int(row.cogs or 0)

        expenses = 0
        inventory_purchases = 0
        exp_by_cat: dict[str, int] = {}
        bucket_expenses = [0] * len(window.buckets)
        for row in expense_rows:
            amount = int(row.amount or 0)
            category = str(row.category or "Boshqa")
            exp_by_cat[category] = exp_by_cat.get(category, 0) + amount
            if category == "Tovar xaridi":
                inventory_purchases += amount
            else:
                expenses += amount
                bucket_expenses[int(row.bucket)] += amount

        revenue = int(financial.revenue or 0)
        cogs = int(financial.cogs or 0)
        gross_profit = revenue - cogs
        profit = gross_profit - expenses
        trend = [
            StatisticsTrendRead(
                label=bucket.label,
                rev=bucket_revenue[index],
                exp=bucket_expenses[index],
                cogs=bucket_cogs[index],
                profit=(
                    bucket_revenue[index]
                    - bucket_cogs[index]
                    - bucket_expenses[index]
                ),
            )
            for index, bucket in enumerate(window.buckets)
        ]

        return StatisticsReportRead(
            period=window.period,
            anchor=anchor or "",
            label=window.label,
            revenue=revenue,
            cash_in=int(financial.cash_in or 0),
            cogs=cogs,
            gross_profit=gross_profit,
            expenses=expenses,
            inventory_purchases=inventory_purchases,
            profit=profit,
            qarzpay=int(financial.qarzpay or 0),
            pay=pay,
            exp_by_cat=exp_by_cat,
            trend=trend,
            top_products=[
                StatisticsProductRead(
                    name=str(row.name or "?"),
                    qty=round(float(row.qty or 0), 3),
                    unit=str(row.unit or "dona"),
                    total=int(row.total or 0),
                    cost_total=int(row.cost_total or 0),
                    margin=(
                        int(row.total or 0) - int(row.cost_total or 0)
                        if int(row.cost_total or 0) > 0 else None
                    ),
                )
                for row in product_rows
            ],
            low_stock=[
                StatisticsLowStockRead(
                    name=str(row.name),
                    unit=str(row.unit or "dona"),
                    stock_qty=float(row.stock_qty or 0),
                )
                for row in low_stock_rows
            ],
            source_split=source_split,
            cashiers=[
                StatisticsCashierRead(
                    name=str(row.name or "Rahbar"),
                    checks=int(row.count or 0),
                    total=int(row.total or 0),
                )
                for row in cashier_rows
            ],
            waiters=[
                StatisticsWaiterRead(
                    name=str(row.name or "Rahbar"),
                    orders=int(row.count or 0),
                    total=int(row.total or 0),
                )
                for row in waiter_rows
            ],
            sales_count=sales_count,
            can_next=window.end <= _local_start(
                self._now_provider().astimezone(UZBEKISTAN_TZ).date()
            ).astimezone(UTC),
        )

    async def navigation(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        period: str,
        anchor: str,
        direction: int,
    ) -> str:
        del business_account_id
        self._require_statistics(permissions)
        return self.shift(
            period=period,
            anchor=anchor,
            direction=direction,
        )

    def shift(self, *, period: str, anchor: str, direction: int) -> str:
        window = self._window(period, anchor)
        value = window.start.astimezone(UZBEKISTAN_TZ).date()
        step = -1 if direction < 0 else 1
        if window.period == "kun":
            return (value + timedelta(days=step)).isoformat()
        if window.period == "hafta":
            return (value + timedelta(days=step * 7)).isoformat()
        months = {
            "oy": 1,
            "chorak": 3,
            "yarim": 6,
            "yil": 12,
        }[window.period]
        return _add_months(value, step * months).isoformat()

    def _window(self, period: str, anchor: str) -> PeriodWindow:
        today = self._now_provider().astimezone(UZBEKISTAN_TZ).date()
        selected = today
        if (anchor or "").strip():
            try:
                selected = date.fromisoformat(anchor.strip())
            except ValueError:
                selected = today
        normalized = (period or "oy").lower()
        if normalized not in PERIODS:
            normalized = "oy"

        buckets: list[PeriodBucket] = []
        if normalized == "kun":
            local = _local_start(selected)
            for hour in range(24):
                bucket_start = local + timedelta(hours=hour)
                buckets.append(PeriodBucket(
                    start=bucket_start.astimezone(UTC),
                    end=(bucket_start + timedelta(hours=1)).astimezone(UTC),
                    label=f"{hour:02d}",
                ))
            label = selected.isoformat()
        elif normalized == "hafta":
            week_start = selected - timedelta(days=selected.weekday())
            for index, weekday in enumerate(WEEKDAY_LABELS):
                bucket_start = _local_start(week_start + timedelta(days=index))
                buckets.append(PeriodBucket(
                    start=bucket_start.astimezone(UTC),
                    end=(bucket_start + timedelta(days=1)).astimezone(UTC),
                    label=weekday,
                ))
            label = week_start.strftime("%d.%m") + " hafta"
        else:
            if normalized == "oy":
                period_start = date(selected.year, selected.month, 1)
                period_end = _add_months(period_start, 1)
                current = period_start
                while current < period_end:
                    bucket_start = _local_start(current)
                    buckets.append(PeriodBucket(
                        start=bucket_start.astimezone(UTC),
                        end=(bucket_start + timedelta(days=1)).astimezone(UTC),
                        label=str(current.day),
                    ))
                    current += timedelta(days=1)
                label = f"{MONTH_LABELS[period_start.month - 1]} {period_start.year}"
            else:
                size = {"chorak": 3, "yarim": 6, "yil": 12}[normalized]
                if normalized == "chorak":
                    first_month = ((selected.month - 1) // 3) * 3 + 1
                elif normalized == "yarim":
                    first_month = 1 if selected.month <= 6 else 7
                else:
                    first_month = 1
                period_start = date(selected.year, first_month, 1)
                period_end = _add_months(period_start, size)
                for index in range(size):
                    month_start = _add_months(period_start, index)
                    buckets.append(PeriodBucket(
                        start=_local_start(month_start).astimezone(UTC),
                        end=_local_start(_add_months(month_start, 1)).astimezone(UTC),
                        label=MONTH_LABELS[month_start.month - 1],
                    ))
                if normalized == "chorak":
                    label = f"{(first_month - 1) // 3 + 1}-chorak {selected.year}"
                elif normalized == "yarim":
                    label = f"{'1' if first_month == 1 else '2'}-yarim yil {selected.year}"
                else:
                    label = str(selected.year)

        return PeriodWindow(
            period=normalized,
            anchor_date=selected,
            start=buckets[0].start,
            end=buckets[-1].end,
            label=label,
            buckets=tuple(buckets),
        )

    @staticmethod
    def _require_statistics(permissions: tuple[str, ...] | None) -> None:
        if permissions is not None and "statistics" not in permissions:
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )
