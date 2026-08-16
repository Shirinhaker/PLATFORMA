import sqlite3

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import MigrationRun
from app.legacy_migration.reconcile import (
    StageResult,
    _ensure_issue,
    _find_mapping,
    _optional_int,
    _unix_datetime,
)
from app.orders.model import Order
from app.taxi.model import RIDE_STATUSES, TaxiDriver, TaxiRide


async def import_taxi_domain(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    counters = {"created": 0, "reused": 0, "updated": 0, "quarantined": 0, "issues": 0}
    driver_ids: dict[int, int] = {}
    if _table_exists(source, "drivers"):
        for row in _rows(source, "drivers"):
            legacy_id = _optional_int(row.get("id"))
            legacy_user_id = _optional_int(row.get("user_id"))
            mapping = (
                await _find_mapping(session, "user_account", legacy_user_id)
                if legacy_user_id
                else None
            )
            if legacy_id is None or mapping is None or mapping.target_id is None:
                counters["quarantined"] += 1
                counters["issues"] += await _ensure_issue(
                    session,
                    run,
                    entity_type="taxi_driver",
                    legacy_id=legacy_id or 0,
                    issue_code="taxi_driver.user_unresolved",
                )
                continue
            existing = await session.scalar(
                select(TaxiDriver).where(TaxiDriver.legacy_source_id == legacy_id)
            )
            now = _unix_datetime(row.get("created_at"))
            values = {
                "user_account_id": mapping.target_id,
                "phone": str(row.get("phone") or "").strip(),
                "car_model": str(row.get("car_model") or "").strip(),
                "car_color": str(row.get("car_color") or "").strip(),
                "car_plate": str(row.get("car_plate") or "").strip(),
                "service": str(row.get("service") or "taxi")
                if str(row.get("service") or "taxi") in {"taxi", "dostavka", "both"}
                else "taxi",
                "available": bool(row.get("available")),
                "rating_sum": max(0, _optional_int(row.get("rating_sum")) or 0),
                "rating_count": max(0, _optional_int(row.get("rating_cnt")) or 0),
                "balance": max(0, _optional_int(row.get("balance")) or 0),
                "status": "blocked" if row.get("status") == "blocked" else "active",
                "updated_at": now,
            }
            if existing is None:
                existing = TaxiDriver(
                    legacy_source_id=legacy_id,
                    created_at=now,
                    **values,
                )
                session.add(existing)
                await session.flush()
                counters["created"] += 1
            else:
                changed = any(
                    getattr(existing, key) != value for key, value in values.items()
                )
                for key, value in values.items():
                    setattr(existing, key, value)
                counters["updated" if changed else "reused"] += 1
            driver_ids[legacy_id] = existing.id

    if _table_exists(source, "rides"):
        for row in _rows(source, "rides"):
            legacy_id = _optional_int(row.get("id"))
            legacy_customer_id = _optional_int(row.get("customer_id"))
            mapping = (
                await _find_mapping(session, "user_account", legacy_customer_id)
                if legacy_customer_id
                else None
            )
            if legacy_id is None or mapping is None or mapping.target_id is None:
                counters["quarantined"] += 1
                counters["issues"] += await _ensure_issue(
                    session,
                    run,
                    entity_type="taxi_ride",
                    legacy_id=legacy_id or 0,
                    issue_code="taxi_ride.customer_unresolved",
                )
                continue
            existing = await session.scalar(
                select(TaxiRide).where(TaxiRide.legacy_source_id == legacy_id)
            )
            legacy_order_id = _optional_int(row.get("src_order_id"))
            source_order_id = (
                await session.scalar(
                    select(Order.id).where(Order.legacy_source_id == legacy_order_id)
                )
                if legacy_order_id
                else None
            )
            created_at = _unix_datetime(row.get("created_at"))
            accepted_at = (
                _unix_datetime(row.get("accepted_at"))
                if row.get("accepted_at")
                else None
            )
            status = str(row.get("status") or "pending")
            values = {
                "customer_account_id": mapping.target_id,
                "driver_id": driver_ids.get(_optional_int(row.get("driver_id")) or 0),
                "source_order_id": source_order_id,
                "kind": "dostavka" if row.get("kind") == "dostavka" else "taxi",
                "from_addr": str(row.get("from_addr") or ""),
                "to_addr": str(row.get("to_addr") or ""),
                "from_lat": _number(row.get("from_lat")),
                "from_lng": _number(row.get("from_lng")),
                "to_lat": _number(row.get("to_lat")),
                "to_lng": _number(row.get("to_lng")),
                "dist_km": _nonnegative_number(row.get("dist_km")),
                "dur_min": max(0, _optional_int(row.get("dur_min")) or 0)
                if row.get("dur_min") is not None
                else None,
                "meter_km": _nonnegative_number(row.get("meter_km")),
                "ozim": bool(row.get("ozim")),
                "cargo": str(row.get("cargo") or ""),
                "car_type": str(row.get("car_type") or ""),
                "note": str(row.get("note") or ""),
                "status": status if status in RIDE_STATUSES else "pending",
                "accepted_at": accepted_at,
                "updated_at": accepted_at or created_at,
            }
            if existing is None:
                session.add(
                    TaxiRide(
                        legacy_source_id=legacy_id,
                        created_at=created_at,
                        **values,
                    )
                )
                counters["created"] += 1
            else:
                changed = any(
                    getattr(existing, key) != value for key, value in values.items()
                )
                for key, value in values.items():
                    setattr(existing, key, value)
                counters["updated" if changed else "reused"] += 1
    await session.flush()
    return StageResult(**counters)


def _table_exists(source: sqlite3.Connection, table: str) -> bool:
    return (
        source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _rows(source: sqlite3.Connection, table: str) -> list[dict[str, object]]:
    cursor = source.execute(f'SELECT * FROM "{table}" ORDER BY id')
    columns = [column[0] for column in cursor.description or ()]
    return [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _nonnegative_number(value: object) -> float | None:
    number = _number(value)
    return max(0.0, number) if number is not None else None
