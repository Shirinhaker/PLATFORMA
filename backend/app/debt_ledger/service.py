from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.core.errors import ApiError
from app.debt_ledger.model import Debtor, DebtTransaction
from app.debt_ledger.repository import DebtLedgerRepository
from app.debt_ledger.schemas import (
    DebtMutationRead,
    DebtTransactionCreate,
    DebtTransactionRead,
    DebtorCreate,
    DebtorCreated,
    DebtorDetailRead,
    DebtorRead,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
UZBEKISTAN_TZ = ZoneInfo("Asia/Tashkent")


class DebtLedgerService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: DebtLedgerRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or DebtLedgerRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def list_debtors(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[DebtorRead]:
        self._require_any(permissions, "debts", "kassa")
        async with self._session_factory() as session:
            rows = await self._repository.debtors_with_balances(
                session,
                business_account_id=business_account_id,
            )
            await session.rollback()
            return [self._debtor_read(debtor, int(balance or 0)) for debtor, balance in rows]

    async def create_debtor(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        body: DebtorCreate,
    ) -> DebtorCreated:
        self._require_any(permissions, "debts", "kassa")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                debtor = Debtor(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    name=body.name,
                    phone=body.phone,
                    note=body.note,
                    due=body.due,
                    created_by_staff_id=actor_staff_id,
                    created_at=now,
                    updated_at=now,
                )
                session.add(debtor)
                await session.flush()
                if body.initial_debt > 0:
                    await self.create_transaction_in_session(
                        session,
                        business_account_id=business_account_id,
                        debtor_id=debtor.id,
                        transaction_type="debt",
                        amount=body.initial_debt,
                        transaction_date=now.astimezone(UZBEKISTAN_TZ).date(),
                        note=body.note or "Boshlang'ich qarz",
                        actor_staff_id=actor_staff_id,
                    )
                await session.commit()
                return DebtorCreated(id=debtor.id)
            except Exception:
                await session.rollback()
                raise

    async def get_debtor(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        debtor_id: int,
    ) -> DebtorDetailRead:
        self._require_any(permissions, "debts")
        async with self._session_factory() as session:
            debtor = await self.require_debtor_in_session(
                session,
                business_account_id=business_account_id,
                debtor_id=debtor_id,
            )
            transactions = await self._repository.transactions(
                session,
                business_account_id=business_account_id,
                debtor_id=debtor_id,
            )
            balance = await self._repository.balance(
                session,
                business_account_id=business_account_id,
                debtor_id=debtor_id,
            )
            await session.rollback()
            base = self._debtor_read(debtor, balance)
            return DebtorDetailRead(
                **base.model_dump(),
                tx=[self._transaction_read(row) for row in transactions],
            )

    async def add_transaction(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        actor_name: str,
        permissions: tuple[str, ...] | None,
        debtor_id: int,
        body: DebtTransactionCreate,
    ) -> DebtMutationRead:
        self._require_any(permissions, "debts")
        now = self._now_provider()
        transaction_date = body.date or now.astimezone(UZBEKISTAN_TZ).date()
        if transaction_date > now.astimezone(UZBEKISTAN_TZ).date():
            raise ApiError(
                422,
                "debt_future_date_forbidden",
                "Kelajak sanaga qarz amaliyoti yozib bo‘lmaydi.",
            )
        async with self._session_factory() as session:
            try:
                debtor = await self.require_debtor_in_session(
                    session,
                    business_account_id=business_account_id,
                    debtor_id=debtor_id,
                    lock=True,
                )
                cash_receipt_id = None
                if body.type == "payment":
                    receipt_time = now
                    if transaction_date != now.astimezone(UZBEKISTAN_TZ).date():
                        receipt_time = datetime.combine(
                            transaction_date,
                            time(hour=12),
                            tzinfo=UZBEKISTAN_TZ,
                        ).astimezone(UTC)
                    receipt = CashReceipt(
                        business_account_id=business_account_id,
                        receipt_no=None,
                        source="debt_payment",
                        order_id=None,
                        legacy_order_source_id=None,
                        legacy_group_key=None,
                        pay_type="",
                        debtor_id=debtor.id,
                        debtor_name_snapshot=debtor.name,
                        legacy_debtor_source_id=debtor.legacy_source_id,
                        note=body.note,
                        created_by_staff_id=actor_staff_id,
                        actor_name_snapshot=actor_name[:160],
                        created_at=receipt_time,
                    )
                    session.add(receipt)
                    await session.flush()
                    session.add(CashReceiptLine(
                        receipt_id=receipt.id,
                        business_account_id=business_account_id,
                        catalog_item_id=None,
                        inventory_item_id=None,
                        legacy_source_key=None,
                        item_name=f"«{debtor.name}» qarz to'lovi"[:220],
                        qty=1,
                        unit="dona",
                        unit_price=body.amount,
                        total=body.amount,
                        cost_total=0,
                        created_at=receipt_time,
                    ))
                    await session.flush()
                    cash_receipt_id = receipt.id
                transaction = await self.create_transaction_in_session(
                    session,
                    business_account_id=business_account_id,
                    debtor_id=debtor.id,
                    transaction_type=body.type,
                    amount=body.amount,
                    transaction_date=transaction_date,
                    note=body.note,
                    actor_staff_id=actor_staff_id,
                    cash_receipt_id=cash_receipt_id,
                    debtor=debtor,
                )
                balance = await self._repository.balance(
                    session,
                    business_account_id=business_account_id,
                    debtor_id=debtor.id,
                )
                await session.commit()
                return DebtMutationRead(
                    transaction_id=transaction.id,
                    balance=balance,
                )
            except Exception:
                await session.rollback()
                raise

    async def require_debtor_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        debtor_id: int,
        lock: bool = False,
    ) -> Debtor:
        debtor = await self._repository.debtor(
            session,
            business_account_id=business_account_id,
            debtor_id=debtor_id,
            lock=lock,
        )
        if debtor is None:
            raise ApiError(
                400,
                "debt_debtor_required",
                "Qarz uchun qarzdorni tanlang.",
            )
        return debtor

    async def create_transaction_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        debtor_id: int,
        transaction_type: str,
        amount: int,
        transaction_date: date,
        note: str,
        actor_staff_id: int | None,
        order_id: int | None = None,
        cash_receipt_id: int | None = None,
        debtor: Debtor | None = None,
    ) -> DebtTransaction:
        if transaction_type not in {"debt", "payment"} or amount <= 0:
            raise ApiError(400, "debt_transaction_invalid", "Summa noto'g'ri.")
        debtor = debtor or await self.require_debtor_in_session(
            session,
            business_account_id=business_account_id,
            debtor_id=debtor_id,
            lock=True,
        )
        transaction = DebtTransaction(
            business_account_id=business_account_id,
            debtor_id=debtor.id,
            legacy_source_id=None,
            transaction_type=transaction_type,
            amount=amount,
            transaction_date=transaction_date,
            note=note[:200],
            order_id=order_id,
            cash_receipt_id=cash_receipt_id,
            performed_by_staff_id=actor_staff_id,
            created_at=self._now_provider(),
        )
        session.add(transaction)
        await session.flush()
        return transaction

    async def create_order_debt_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        order_id: int,
        debtor_id: int,
        amount: int,
        note: str,
        actor_staff_id: int | None,
        cash_receipt_id: int | None = None,
    ) -> tuple[Debtor, DebtTransaction]:
        existing = await self._repository.order_debt(
            session,
            business_account_id=business_account_id,
            order_id=order_id,
            lock=True,
        )
        if existing is not None:
            debtor = await self.require_debtor_in_session(
                session,
                business_account_id=business_account_id,
                debtor_id=existing.debtor_id,
            )
            if existing.cash_receipt_id is None and cash_receipt_id is not None:
                existing.cash_receipt_id = cash_receipt_id
                await session.flush()
            return debtor, existing
        debtor = await self.require_debtor_in_session(
            session,
            business_account_id=business_account_id,
            debtor_id=debtor_id,
            lock=True,
        )
        transaction = await self.create_transaction_in_session(
            session,
            business_account_id=business_account_id,
            debtor_id=debtor.id,
            transaction_type="debt",
            amount=amount,
            transaction_date=self._now_provider().astimezone(UZBEKISTAN_TZ).date(),
            note=note,
            actor_staff_id=actor_staff_id,
            order_id=order_id,
            cash_receipt_id=cash_receipt_id,
            debtor=debtor,
        )
        return debtor, transaction

    async def replace_receipt_debts_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        cash_receipt_id: int,
        debtor_id: int,
        entries: Iterable[tuple[int, str]],
        actor_staff_id: int | None,
        transaction_date: date,
        order_id: int | None = None,
    ) -> Debtor:
        debtor = await self.require_debtor_in_session(
            session,
            business_account_id=business_account_id,
            debtor_id=debtor_id,
            lock=True,
        )
        existing = await self._repository.transactions_for_receipt(
            session,
            business_account_id=business_account_id,
            cash_receipt_id=cash_receipt_id,
            lock=True,
        )
        for row in existing:
            await session.delete(row)
        await session.flush()
        for amount, note in entries:
            await self.create_transaction_in_session(
                session,
                business_account_id=business_account_id,
                debtor_id=debtor.id,
                transaction_type="debt",
                amount=amount,
                transaction_date=transaction_date,
                note=note,
                actor_staff_id=actor_staff_id,
                order_id=order_id,
                cash_receipt_id=cash_receipt_id,
                debtor=debtor,
            )
        return debtor

    async def delete_receipt_transactions_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        cash_receipt_id: int,
    ) -> None:
        rows = await self._repository.transactions_for_receipt(
            session,
            business_account_id=business_account_id,
            cash_receipt_id=cash_receipt_id,
            lock=True,
        )
        for row in rows:
            await session.delete(row)
        await session.flush()

    async def delete_order_debt_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        order_id: int,
    ) -> None:
        row = await self._repository.order_debt(
            session,
            business_account_id=business_account_id,
            order_id=order_id,
            lock=True,
        )
        if row is not None:
            await session.delete(row)
            await session.flush()

    @staticmethod
    def _require_any(
        permissions: tuple[str, ...] | None,
        *required: str,
    ) -> None:
        if permissions is not None and not set(required).intersection(permissions):
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )

    @staticmethod
    def _debtor_read(debtor: Debtor, balance: int) -> DebtorRead:
        return DebtorRead(
            id=debtor.id,
            name=debtor.name,
            phone=debtor.phone,
            note=debtor.note,
            due=debtor.due,
            balance=balance,
        )

    @staticmethod
    def _transaction_read(row: DebtTransaction) -> DebtTransactionRead:
        return DebtTransactionRead(
            id=row.id,
            type=row.transaction_type,
            amount=row.amount,
            date=row.transaction_date,
            note=row.note,
            order_id=row.order_id,
            cash_receipt_id=row.cash_receipt_id,
            created_at=row.created_at,
        )
