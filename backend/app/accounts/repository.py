from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType


async def find_accounts_by_login(
    session: AsyncSession,
    normalized_login: str,
) -> list[Account]:
    result = await session.execute(
        select(Account)
        .where(func.lower(Account.login) == normalized_login)
        .order_by(Account.account_type, Account.id)
    )
    return list(result.scalars().all())


async def find_account_by_login(
    session: AsyncSession,
    normalized_login: str,
    account_type: AccountType | None = None,
) -> Account | None:
    statement = select(Account).where(
        func.lower(Account.login) == normalized_login
    )
    if account_type is not None:
        statement = statement.where(Account.account_type == account_type)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def find_telegram_account(
    session: AsyncSession,
    telegram_user_id: int,
    account_type: AccountType,
) -> Account | None:
    result = await session.execute(
        select(Account).where(
            Account.telegram_user_id == telegram_user_id,
            Account.account_type == account_type,
        )
    )
    return result.scalar_one_or_none()


async def create_account(
    session: AsyncSession,
    *,
    account_type: AccountType,
    login: str,
    password_hash: str,
    telegram_user_id: int,
    now: datetime,
) -> Account:
    account = Account(
        account_type=account_type,
        login=login,
        password_hash=password_hash,
        telegram_user_id=telegram_user_id,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    await session.flush()
    return account
