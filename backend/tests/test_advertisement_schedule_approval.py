from datetime import UTC, datetime

from app.advertisements.pricing import shift_schedule_start


def stamp(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp())


def test_all_day_ad_starts_at_approval_when_requested_start_is_past():
    requested = stamp("2026-08-12T19:00:00")  # 13-avgust 00:00 UZT
    approved = stamp("2026-08-13T07:44:00")   # 13-avgust 12:44 UZT

    assert shift_schedule_start(
        requested_start_at=requested,
        approved_at=approved,
        daily_all_day=True,
        daily_start="00:00",
    ) == approved


def test_future_all_day_schedule_is_preserved():
    approved = stamp("2026-08-13T07:44:00")
    requested = stamp("2026-08-13T19:00:00")  # 14-avgust 00:00 UZT

    assert shift_schedule_start(
        requested_start_at=requested,
        approved_at=approved,
        daily_all_day=True,
        daily_start="00:00",
    ) == requested


def test_custom_daily_window_still_moves_to_next_matching_hour():
    requested = stamp("2026-08-12T14:00:00")  # 12-avgust 19:00 UZT
    approved = stamp("2026-08-13T17:30:00")   # 13-avgust 22:30 UZT

    assert shift_schedule_start(
        requested_start_at=requested,
        approved_at=approved,
        daily_all_day=False,
        daily_start="19:00",
    ) == stamp("2026-08-14T14:00:00")
