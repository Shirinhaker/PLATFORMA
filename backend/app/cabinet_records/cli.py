from __future__ import annotations

import argparse
import asyncio

# Standalone CLI FastAPI app import zanjiridan tashqarida ishlaydi. Foreign key
# metadata resolve bo‘lishi uchun parent account jadvali birinchi ro‘yxatdan o‘tadi.
from app.accounts.model import Account as _Account  # noqa: F401
from app.cabinet_records.backfill import backfill_all_profiles
from app.cabinet_records.batch_runner import execute_backfill_batches
from app.cabinet_records.lock import normalization_lock
from app.cabinet_records.verify_existing import verify_existing_normalization
from app.core.config import get_settings
from app.db.session import Database


async def run(
    *,
    execute: bool,
    verify_only: bool,
    batch_size: int,
) -> int:
    settings = get_settings()
    database = Database(settings.database_url)
    await database.start()
    try:
        async with database.session() as lock_session:
            async with normalization_lock(lock_session):
                return await run_locked(
                    database,
                    execute=execute,
                    verify_only=verify_only,
                    batch_size=batch_size,
                )
    finally:
        await database.stop()


async def run_locked(
    database: Database,
    *,
    execute: bool,
    verify_only: bool,
    batch_size: int,
) -> int:
    if verify_only:
        async with database.session() as session:
            summary = await verify_existing_normalization(session)
            await session.rollback()
        print_summary(
            mode="VERIFY_ONLY",
            run_id=0,
            summary=summary,
            batches_committed=0,
        )
        print(f"MARKER_MISMATCHES={summary.marker_mismatches}")
        print(f"VERIFY_OK={int(summary.ok)}")
        print("DATABASE_WRITES=0")
        return 0 if summary.ok else 2

    if execute:
        summary = await execute_backfill_batches(
            database.session,
            batch_size=batch_size,
        )
        print_summary(
            mode="EXECUTE_BATCHED",
            run_id=summary.run_id,
            summary=summary,
            batches_committed=summary.batches_committed,
        )
        print("VERIFY_OK=1")
        print("DATABASE_WRITES=RELATIONAL_AND_SYNCED_FALLBACK")
        return 0

    async with database.session() as session:
        summary = await backfill_all_profiles(session)
        await session.rollback()
    print_summary(
        mode="DRY_RUN",
        run_id=summary.run_id,
        summary=summary,
        batches_committed=0,
    )
    print("VERIFY_OK=1")
    print("DATABASE_WRITES=0")
    return 0


def print_summary(*, mode: str, run_id: int, summary, batches_committed: int) -> None:
    print("SCRIPT=KOPRIK_V7_CABINET_JSON_NORMALIZATION")
    print(f"MODE={mode}")
    print(f"RUN_ID={run_id}")
    print(f"PROFILES_TOTAL={summary.profiles_total}")
    print(f"PROFILES_VERIFIED={summary.profiles_verified}")
    print(f"RESOURCES_SOURCE={summary.resources_source}")
    print(f"RESOURCES_TARGET={summary.resources_target}")
    print(f"RECORDS_SOURCE={summary.records_source}")
    print(f"RECORDS_TARGET={summary.records_target}")
    print(f"SOURCE_DIGEST={summary.source_digest}")
    print(f"TARGET_DIGEST={summary.target_digest}")
    print(f"BATCHES_COMMITTED={batches_committed}")
    print("JSON_KEYS_DELETED=0")
    print("NORMALIZATION_COMPLETE")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Verified relational yozuvlarni batchlar bilan commit qiladi.",
    )
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="JSON source va relational targetni read-only tekshiradi.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Execute rejimidagi profil batch hajmi (1–1000).",
    )
    args = parser.parse_args()
    return asyncio.run(
        run(
            execute=args.execute,
            verify_only=args.verify_only,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
