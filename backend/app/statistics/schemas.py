from typing import Literal

from pydantic import BaseModel, Field


StatisticsPeriod = Literal["kun", "hafta", "oy", "chorak", "yarim", "yil"]


class StatisticsPaymentRead(BaseModel):
    naqd: int = 0
    karta: int = 0
    qarz: int = 0
    order: int = 0


class StatisticsSourceRead(BaseModel):
    count: int = 0
    total: int = 0


class StatisticsSourceSplitRead(BaseModel):
    internal: StatisticsSourceRead = Field(default_factory=StatisticsSourceRead)
    external: StatisticsSourceRead = Field(default_factory=StatisticsSourceRead)
    manual: StatisticsSourceRead = Field(default_factory=StatisticsSourceRead)


class StatisticsTrendRead(BaseModel):
    label: str
    rev: int = 0
    exp: int = 0
    cogs: int = 0
    profit: int = 0


class StatisticsProductRead(BaseModel):
    name: str
    qty: float
    unit: str
    total: int
    cost_total: int
    margin: int | None


class StatisticsLowStockRead(BaseModel):
    name: str
    unit: str
    stock_qty: float


class StatisticsCashierRead(BaseModel):
    name: str
    checks: int
    total: int


class StatisticsWaiterRead(BaseModel):
    name: str
    orders: int
    total: int


class StatisticsReportRead(BaseModel):
    period: StatisticsPeriod
    anchor: str
    label: str
    revenue: int
    cash_in: int
    cogs: int
    gross_profit: int
    expenses: int
    inventory_purchases: int
    profit: int
    qarzpay: int
    pay: StatisticsPaymentRead
    exp_by_cat: dict[str, int]
    trend: list[StatisticsTrendRead]
    top_products: list[StatisticsProductRead]
    low_stock: list[StatisticsLowStockRead]
    source_split: StatisticsSourceSplitRead
    cashiers: list[StatisticsCashierRead]
    waiters: list[StatisticsWaiterRead]
    sales_count: int
    can_next: bool


class StatisticsNavigationRead(BaseModel):
    anchor: str
