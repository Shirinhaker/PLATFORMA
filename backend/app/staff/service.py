from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, time, timedelta, timezone
import re
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.auth.schemas import SessionIdentity
from app.auth.security import (
    derive_csrf,
    hash_password,
    sha256_token,
    verify_password_with_rehash,
)
from app.core.config import Settings
from app.core.errors import ApiError
from app.staff.model import StaffAttendance, StaffMember, StaffProfession, StaffSession
from app.staff.permissions import (
    clean_permissions,
    permission_definitions,
    permission_templates,
)
from app.staff.repository import StaffRepository
from app.staff.schemas import (
    StaffAccessWrite,
    StaffAttendanceRead,
    StaffAttendanceRow,
    StaffAttendanceWrite,
    StaffMemberCreate,
    StaffMemberPatch,
    StaffMemberRead,
    StaffPermissionRead,
    StaffScheduleWrite,
    StaffSetupRead,
    StaffTemplateRead,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
DEFAULT_PROFESSIONS = (
    "Sotuvchi", "Kassir", "Menejer", "Hisobchi", "Omborchi",
    "Yuk tashuvchi", "Haydovchi", "Farrosh", "Qorovul", "Boshqa",
)
LOGIN_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")
UZBEKISTAN_TZ = timezone(timedelta(hours=5))


def _clock(value: str) -> time | None:
    return time.fromisoformat(value) if value else None


def _clock_text(value: time | None) -> str:
    return value.strftime("%H:%M") if value is not None else ""


class StaffService:
    def __init__(
        self,
        session_factory: SessionFactory,
        settings: Settings,
        *,
        repository: StaffRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._repository = repository or StaffRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def setup(self, business_account_id: int) -> StaffSetupRead:
        async with self._session_factory() as session:
            profile = await self._business_profile(session, business_account_id)
            account = await session.get(Account, business_account_id)
            rows = await self._repository.members(session, business_account_id)
            professions = await self._profession_names(session, business_account_id)
            active = [self._member_read(row) for row in rows if row.status == "active"]
            fired = [self._member_read(row) for row in rows if row.status == "fired"]
            definitions = permission_definitions(profile.direction)
            templates = permission_templates(profile.direction)
            result = StaffSetupRead(
                active=active,
                fired=fired,
                active_count=len(active),
                fired_count=len(fired),
                total_salary=sum(row.salary for row in rows if row.status == "active"),
                firm_login=str(account.login if account else ""),
                business_direction=str(profile.direction or ""),
                professions=professions,
                permission_definitions=[
                    StaffPermissionRead(key=item.key, label=item.label, icon=item.icon)
                    for item in definitions
                ],
                permission_templates=[
                    StaffTemplateRead(
                        key=item.key,
                        label=item.label,
                        permissions=list(item.permissions),
                    )
                    for item in templates
                ],
            )
            await session.rollback()
            return result

    async def create_member(
        self,
        business_account_id: int,
        body: StaffMemberCreate,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            await self._business_profile(session, business_account_id)
            now = self._now()
            member = StaffMember(
                business_account_id=business_account_id,
                legacy_source_id=None,
                name=body.name.strip(),
                profession=body.profession.strip(),
                phone=body.phone.strip(),
                salary=body.salary,
                hire_date=body.hire_date,
                status="active",
                note=body.note.strip(),
                login=None,
                password_hash=None,
                can_login=False,
                permissions=[],
                schedule={},
                created_at=now,
                updated_at=now,
                fired_at=None,
            )
            session.add(member)
            await session.commit()
            return self._member_read(member)

    async def update_member(
        self,
        business_account_id: int,
        staff_id: int,
        body: StaffMemberPatch,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            values = body.model_dump(exclude_unset=True)
            for name, value in values.items():
                if isinstance(value, str):
                    value = value.strip()
                setattr(member, name, value)
            member.updated_at = self._now()
            await session.commit()
            return self._member_read(member)

    async def set_status(
        self,
        business_account_id: int,
        staff_id: int,
        status: str,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            now = self._now()
            member.status = status
            member.fired_at = now if status == "fired" else None
            member.updated_at = now
            if status == "fired":
                await self._repository.revoke_staff_sessions(
                    session, staff_id=member.id, now=now
                )
                await self._repository.deactivate_queue_providers(
                    session,
                    business_account_id=business_account_id,
                    staff_id=member.id,
                    now=now,
                )
            await session.commit()
            return self._member_read(member)

    async def delete_member(self, business_account_id: int, staff_id: int) -> None:
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            now = self._now()
            await self._repository.revoke_staff_sessions(
                session, staff_id=member.id, now=now
            )
            await self._repository.deactivate_queue_providers(
                session,
                business_account_id=business_account_id,
                staff_id=member.id,
                now=now,
            )
            await session.delete(member)
            await session.commit()

    async def set_access(
        self,
        business_account_id: int,
        staff_id: int,
        body: StaffAccessWrite,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            profile = await self._business_profile(session, business_account_id)
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            login = body.login.strip().casefold()
            if body.can_login:
                if not LOGIN_RE.fullmatch(login):
                    raise ApiError(
                        422,
                        "staff_login_invalid",
                        "Login 3–20 belgi bo‘lsin, kichik lotin harfi bilan boshlansin.",
                    )
                if await self._repository.duplicate_login(
                    session,
                    business_account_id=business_account_id,
                    login=login,
                    excluding_staff_id=member.id,
                ):
                    raise ApiError(409, "staff_login_taken", "Bu xodim logini band.")
                if not member.password_hash and not body.password:
                    raise ApiError(
                        422,
                        "staff_password_required",
                        "Xodim uchun yangi parol kiriting.",
                    )
            if body.password and len(body.password) < 8:
                raise ApiError(
                    422,
                    "staff_password_too_short",
                    "Parol kamida 8 belgi bo‘lsin.",
                )

            now = self._now()
            password_changed = bool(body.password)
            member.login = login or None
            member.can_login = body.can_login
            member.permissions = clean_permissions(
                body.permissions, str(profile.direction or "")
            )
            if password_changed:
                member.password_hash = hash_password(body.password)
            member.updated_at = now
            if not body.can_login or password_changed:
                await self._repository.revoke_staff_sessions(
                    session, staff_id=member.id, now=now
                )
            await session.commit()
            return self._member_read(member)

    async def set_schedule(
        self,
        business_account_id: int,
        staff_id: int,
        body: StaffScheduleWrite,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            schedule: dict[str, dict[str, object]] = {}
            for index in range(7):
                key = f"d{index}"
                day = body.schedule.get(key)
                if day is None:
                    schedule[key] = {"on": False, "start": "", "end": ""}
                    continue
                if day.on and (not day.start or not day.end or day.start >= day.end):
                    raise ApiError(
                        422,
                        "staff_schedule_invalid",
                        "Ish kuni boshlanish va tugash vaqtini to‘g‘ri kiriting.",
                    )
                schedule[key] = day.model_dump()
            member.schedule = schedule
            member.updated_at = self._now()
            await session.commit()
            return self._member_read(member)

    async def add_profession(
        self,
        business_account_id: int,
        name: str,
    ) -> list[str]:
        clean = name.strip()
        if not clean:
            raise ApiError(422, "staff_profession_required", "Lavozim nomini kiriting.")
        async with self._session_factory() as session:
            await self._business_profile(session, business_account_id)
            if clean.casefold() not in {value.casefold() for value in DEFAULT_PROFESSIONS}:
                if not await self._repository.profession_exists(
                    session,
                    business_account_id=business_account_id,
                    name=clean,
                ):
                    session.add(StaffProfession(
                        business_account_id=business_account_id,
                        name=clean,
                        created_at=self._now(),
                    ))
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
            return await self._profession_names(session, business_account_id)

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
                        minutes[row.staff_id] = minutes.get(row.staff_id, 0) + end - start
            result = []
            for member in members:
                recorded = daily.get(member.id)
                schedule = member.schedule if isinstance(member.schedule, dict) else {}
                planned = schedule.get(f"d{day.weekday()}", {})
                if not isinstance(planned, dict):
                    planned = {}
                result.append(StaffAttendanceRow(
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
                ))
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
                    session.add(StaffAttendance(
                        business_account_id=business_account_id,
                        staff_id=member.id,
                        date=body.date,
                        status=body.status,
                        time_in=time_in,
                        time_out=time_out,
                        created_at=now,
                        updated_at=now,
                    ))
                else:
                    row.status = body.status
                    row.time_in = time_in
                    row.time_out = time_out
                    row.updated_at = now
            await session.commit()
        return await self.attendance(business_account_id, body.date)

    async def login(
        self,
        firm_login: str,
        staff_login: str,
        password: str,
    ) -> tuple[str, SessionIdentity]:
        firm = firm_login.strip().casefold()
        login = staff_login.strip().casefold()
        async with self._session_factory() as session:
            account = await self._repository.business_account_by_login(session, firm)
            if account is None:
                raise self._invalid_credentials()
            member = await self._repository.member_by_login(
                session,
                business_account_id=account.id,
                login=login,
            )
            if (
                member is None
                or not member.can_login
                or member.status != "active"
                or not member.password_hash
            ):
                raise self._invalid_credentials()
            checked = verify_password_with_rehash(member.password_hash, password)
            if not checked.valid:
                raise self._invalid_credentials()
            if checked.replacement_hash:
                member.password_hash = checked.replacement_hash
            raw_token = secrets.token_urlsafe(32)
            now = self._now()
            expires_at = now + timedelta(seconds=self._settings.session_ttl_seconds)
            session.add(StaffSession(
                staff_id=member.id,
                token_hash=sha256_token(raw_token),
                created_at=now,
                expires_at=expires_at,
                last_used_at=now,
                revoked_at=None,
            ))
            await session.commit()
            return raw_token, self._identity(raw_token, member, expires_at)

    async def resolve_session(
        self,
        raw_token: str,
        now: datetime,
    ) -> SessionIdentity | None:
        async with self._session_factory() as session:
            stored = await self._repository.session_by_token_hash(
                session,
                token_hash=sha256_token(raw_token),
                now=now,
                lock=True,
            )
            if stored is None:
                await session.rollback()
                return None
            member = await self._repository.member(
                session, staff_id=stored.staff_id, lock=False
            )
            if (
                member is None
                or member.status != "active"
                or not member.can_login
                or not member.password_hash
            ):
                stored.revoked_at = now
                await session.commit()
                return None
            stored.last_used_at = now
            await session.commit()
            return self._identity(raw_token, member, stored.expires_at)

    async def revoke_session(self, raw_token: str, now: datetime) -> None:
        async with self._session_factory() as session:
            stored = await self._repository.session_by_token_hash(
                session,
                token_hash=sha256_token(raw_token),
                now=now,
                lock=True,
            )
            if stored is not None:
                stored.revoked_at = now
                await session.commit()
            else:
                await session.rollback()

    async def active_member_rows(
        self,
        business_account_id: int,
    ) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            rows = await self._repository.members(
                session, business_account_id, active_only=True
            )
            result = [
                {"id": row.id, "name": row.name, "profession": row.profession}
                for row in rows
            ]
            await session.rollback()
            return result

    async def _business_profile(self, session: AsyncSession, account_id: int):
        profile = await self._repository.business_profile(session, account_id)
        if profile is None:
            raise ApiError(
                404,
                "business_profile_not_found",
                "Biznes profil topilmadi.",
            )
        return profile

    async def _owned_member(
        self,
        session: AsyncSession,
        business_account_id: int,
        staff_id: int,
        *,
        lock: bool,
    ) -> StaffMember:
        member = await self._repository.member(
            session,
            staff_id=staff_id,
            business_account_id=business_account_id,
            lock=lock,
        )
        if member is None:
            raise ApiError(404, "staff_not_found", "Xodim topilmadi.")
        return member

    async def _profession_names(
        self,
        session: AsyncSession,
        business_account_id: int,
    ) -> list[str]:
        custom = await self._repository.professions(session, business_account_id)
        result = list(DEFAULT_PROFESSIONS)
        seen = {value.casefold() for value in result}
        for row in custom:
            if row.name.casefold() not in seen:
                result.append(row.name)
                seen.add(row.name.casefold())
        return result

    def _member_read(self, member: StaffMember) -> StaffMemberRead:
        return StaffMemberRead(
            id=member.id,
            name=member.name,
            profession=member.profession,
            phone=member.phone,
            salary=member.salary,
            hire_date=member.hire_date,
            status=member.status,
            note=member.note,
            login=member.login or "",
            can_login=member.can_login,
            has_password=bool(member.password_hash),
            permissions=clean_permissions(member.permissions),
            schedule=member.schedule if isinstance(member.schedule, dict) else {},
            created_at=member.created_at,
            fired_at=member.fired_at,
        )

    def _identity(
        self,
        raw_token: str,
        member: StaffMember,
        expires_at: datetime,
    ) -> SessionIdentity:
        return SessionIdentity(
            account_id=member.business_account_id,
            account_type=AccountType.BUSINESS,
            login=member.login or "",
            name=member.name,
            csrf_token=derive_csrf(raw_token, self._settings.csrf_secret),
            expires_at=expires_at,
            actor_type="staff",
            staff_id=member.id,
            permissions=clean_permissions(member.permissions),
        )

    @staticmethod
    def _invalid_credentials() -> ApiError:
        return ApiError(
            401,
            "staff_invalid_credentials",
            "Firma logini, xodim logini yoki parol noto‘g‘ri.",
        )

    def _now(self) -> datetime:
        value = self._now_provider()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
