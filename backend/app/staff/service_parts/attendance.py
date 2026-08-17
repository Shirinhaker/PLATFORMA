"""Davomat: oqish va belgilash."""

from __future__ import annotations

from datetime import date

from app.core.errors import ApiError
from app.staff.model import StaffAttendance
from app.staff.schemas import (
    StaffAttendanceRead,
    StaffAttendanceRow,
    StaffAttendanceWrite,
)
from app.staff.service_parts.base import StaffServiceBase
from app.staff.service_parts.helpers import (
    UZBEKISTAN_TZ,
    _clock,
    _clock_text,
)


class AttendanceMixin(StaffServiceBase):
    async def attendance(
        self,
        business_account_id: int,
        day: date,
    ) -> StaffAttendanceRead:
        async with self._session_factory() as session:
            await self._business_profile(session, business_account_id)
            members = await self._repository.members(
                session, business_account_id, active_only=True
            )
            daily = await self._repository.attendance_for_day(
                session, business_account_id=business_account_id, day=day
            )
            first = day.replace(day=1)
            next_month = (
                first.replace(year=first.year + 1, month=1)
                if first.month == 12
                else first.replace(month=first.month + 1)
            )
            monthly = await self._repository.attendance_for_month(
                session,
                business_account_id=business_account_id,
                first_day=first,
                next_month=next_month,
            )
            present: dict[int, int] = {}
            minutes: dict[int, int] = {}
            for row in monthly:
                if row.status != "keldi":
                    continue
                present[row.staff_id] = present.get(row.staff_id, 0) + 1
                if row.time_in is not None and row.time_out is not None:
                    start = row.time_in.hour * 60 + row.time_in.minute
                    end = row.time_out.hour * 60 + row.time_out.minute
                    if end > start:
                        minutes[row.staff_id] = (
                            minutes.get(row.staff_id, 0) + end - start
                        )
            result = []
            for member in members:
                recorded = daily.get(member.id)
                schedule = member.schedule if isinstance(member.schedule, dict) else {}
                planned = schedule.get(f"d{day.weekday()}", {})
                if not isinstance(planned, dict):
                    planned = {}
                result.append(
                    StaffAttendanceRow(
                        id=member.id,
                        name=member.name,
                        profession=member.profession,
                        status=recorded.status if recorded else "",
                        time_in=_clock_text(recorded.time_in) if recorded else "",
                        time_out=_clock_text(recorded.time_out) if recorded else "",
                        sched_on=bool(planned.get("on", False)),
                        sched_start=str(planned.get("start") or planned.get("s") or ""),
                        sched_end=str(planned.get("end") or planned.get("e") or ""),
                        month_present=present.get(member.id, 0),
                        month_minutes=minutes.get(member.id, 0),
                    )
                )
            response = StaffAttendanceRead(
                date=day,
                weekday=day.weekday(),
                staff=result,
            )
            await session.rollback()
            return response

    async def set_attendance(
        self,
        business_account_id: int,
        staff_id: int,
        body: StaffAttendanceWrite,
    ) -> StaffAttendanceRead:
        today = self._now().astimezone(UZBEKISTAN_TZ).date()
        if body.date > today:
            raise ApiError(
                422,
                "staff_attendance_future_forbidden",
                "Kelajak sanaga tabel yozilmaydi.",
            )
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            row = await self._repository.attendance(
                session, staff_id=member.id, day=body.date, lock=True
            )
            if not body.status:
                await self._repository.delete_attendance(
                    session, staff_id=member.id, day=body.date
                )
            else:
                time_in = _clock(body.time_in) if body.status == "keldi" else None
                time_out = _clock(body.time_out) if body.status == "keldi" else None
                if time_in is not None and time_out is not None and time_out <= time_in:
                    raise ApiError(
                        422,
                        "staff_attendance_time_invalid",
                        "Chiqish vaqti kirish vaqtidan keyin bo‘lsin.",
                    )
                now = self._now()
                if row is None:
                    session.add(
                        StaffAttendance(
                            business_account_id=business_account_id,
                            staff_id=member.id,
                            date=body.date,
                            status=body.status,
                            time_in=time_in,
                            time_out=time_out,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                else:
                    row.status = body.status
                    row.time_in = time_in
                    row.time_out = time_out
                    row.updated_at = now
            await session.commit()
        return await self.attendance(business_account_id, body.date)
