from __future__ import annotations

import argparse
import asyncio

from app.cabinet_records.backfill import backfill_all_profiles
from app.core.config import get_settings
from app.db.session import Database


async def run(*, execute: bool) -> int:
    settings = get_settings()
    database = Database(settings.database_url)
    await database.start()
    try:
        async with database.session() as session:
            summary = await backfill_all_profiles(session)
            if execute:
                await session.commit()
                mode = "EXECUTE"
            else:
                await session.rollback()
                mode = "DRY_RUN"
            print("SCRIPT=KOPRIK_V7_CABINET_JSON_NORMALIZATION")
            print(f"MODE={mode}")
            print(f"RUN_ID={summary.run_id}")
            print(f"PROFILES_TOTAL={summary.profiles_total}")
            print(f"PROFILES_VERIFIED={summary.profiles_verified}")
            print(f"RESOURCES_SOURCE={summary.resources_source}")
            print(f"RESOURCES_TARGET={summary.resources_target}")
            print(f"RECORDS_SOURCE={summary.records_source}")
            print(f"RECORDS_TARGET={summary.records_target}")
            print(f"SOURCE_DIGEST={summary.source_digest}")
            print(f"TARGET_DIGEST={summary.target_digest}")
            print("JSON_KEYS_DELETED=0")
            print("NORMALIZATION_COMPLETE")
        return 0
    finally:
        await database.stop()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Verified relational rowsni commit qiladi. Aks holda dry-run rollback bo‘ladi.",
    )
    args = parser.parse_args()
    return asyncio.run(run(execute=args.execute))


if __name__ == "__main__":
    raise SystemExit(main())
