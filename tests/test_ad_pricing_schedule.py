from datetime import datetime, timezone

from ad_pricing import shift_schedule_start


def stamp(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


def test_all_day_approval_starts_immediately_after_requested_start_passed():
    requested = stamp("2026-08-12T19:00:00")
    approved = stamp("2026-08-13T07:44:00")

    assert shift_schedule_start(
        requested_start_at=requested,
        approved_at=approved,
        daily_all_day=True,
        daily_start="00:00",
    ) == approved


def test_all_day_future_start_is_not_pulled_forward():
    approved = stamp("2026-08-13T07:44:00")
    requested = stamp("2026-08-13T19:00:00")

    assert shift_schedule_start(
        requested_start_at=requested,
        approved_at=approved,
        daily_all_day=True,
        daily_start="00:00",
    ) == requested
