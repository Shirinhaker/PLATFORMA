"""Shikoyatlar navbati va audit tarixi.

Shikoyat qarori atomar: bitta shikoyat ikki admin tomonidan bir vaqtda
hal qilinmaydi — qator qulflanadi va holat o'tishi tekshiriladi.

Audit jurnali faqat o'qiladi. Uni o'zgartirish yoki o'chirish baza
darajasida to'silgan (0027 migratsiyasidagi trigger).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import csv
from datetime import UTC, datetime
import io
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import append_audit
from app.admin.moderation_model import (
    CONTENT_KINDS,
    REPORT_REASONS,
    REPORT_STATUSES,
    AdminAuditLog,
    ModerationReport,
)
from app.core.errors import ApiError


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

# Ochiq shikoyat qaysi holatlardan qaror tomon o'tishi mumkin.
DECIDABLE = ("open", "reviewing")


def _unix(value: datetime | None) -> int:
    return int(value.timestamp()) if value is not None else 0


def _report_row(report: ModerationReport) -> dict[str, Any]:
    return {
        "id": report.id,
        "reporter_account_id": report.reporter_account_id,
        "content_kind": report.content_kind,
        "content_id": report.content_id,
        "reason_code": report.reason_code,
        "comment": report.comment,
        "status": report.status,
        "assigned_admin_tg_id": report.assigned_admin_tg_id,
        "resolution": report.resolution,
        "created_at": _unix(report.created_at),
        "updated_at": _unix(report.updated_at),
    }


class AdminReportsService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._now = now_provider

    # --------------------------------------------------------- shikoyatlar

    async def create_report(
        self,
        *,
        reporter_account_id: int,
        content_kind: str,
        content_id: int,
        reason_code: str,
        comment: str,
    ) -> dict[str, Any]:
        """Foydalanuvchi shikoyati — admin sessiyasi talab qilinmaydi."""
        if content_kind not in CONTENT_KINDS:
            raise ApiError(
                400, "admin_content_kind_invalid", "Kontent turi noto‘g‘ri."
            )
        if reason_code not in REPORT_REASONS:
            raise ApiError(
                400, "report_reason_invalid", "Shikoyat sababi noto‘g‘ri."
            )
        now = self._now()
        async with self._session_factory() as session:
            # Bir foydalanuvchi bitta kontentga takror shikoyat yozmaydi.
            existing = await session.scalar(
                select(ModerationReport).where(
                    ModerationReport.reporter_account_id == reporter_account_id,
                    ModerationReport.content_kind == content_kind,
                    ModerationReport.content_id == content_id,
                    ModerationReport.status.in_(DECIDABLE),
                )
            )
            if existing is not None:
                result = _report_row(existing)
                await session.rollback()
                return result
            report = ModerationReport(
                reporter_account_id=reporter_account_id,
                content_kind=content_kind,
                content_id=content_id,
                reason_code=reason_code,
                comment=comment.strip()[:1000],
                status="open",
                created_at=now,
                updated_at=now,
            )
            session.add(report)
            await session.flush()
            result = _report_row(report)
            await session.commit()
        return result

    async def list_reports(
        self, *, status: str = "", limit: int = 100
    ) -> list[dict[str, Any]]:
        if status and status not in REPORT_STATUSES:
            raise ApiError(
                400, "report_status_invalid", "Shikoyat holati noto‘g‘ri."
            )
        statement = select(ModerationReport)
        if status:
            statement = statement.where(ModerationReport.status == status)
        statement = statement.order_by(
            ModerationReport.created_at, ModerationReport.id
        ).limit(max(1, min(500, limit)))
        async with self._session_factory() as session:
            rows = list((await session.scalars(statement)).all())
            result = [_report_row(row) for row in rows]
            await session.rollback()
        return result

    async def report_detail(self, report_id: int) -> dict[str, Any]:
        async with self._session_factory() as session:
            report = await session.get(ModerationReport, report_id)
            if report is None:
                raise ApiError(
                    404, "report_not_found", "Shikoyat topilmadi."
                )
            result = _report_row(report)
            await session.rollback()
        return result

    async def assign(
        self, *, report_id: int, admin_tg_id: int, meta: dict[str, str] | None
    ) -> dict[str, Any]:
        now = self._now()
        async with self._session_factory() as session:
            report = await self._lock(session, report_id)
            if report.status not in DECIDABLE:
                raise ApiError(
                    409,
                    "report_already_decided",
                    "Shikoyat bo‘yicha qaror qabul qilingan.",
                )
            before = report.assigned_admin_tg_id
            report.assigned_admin_tg_id = admin_tg_id
            report.status = "reviewing"
            report.updated_at = now
            await append_audit(
                session,
                admin_tg_id=admin_tg_id,
                action="report.assign",
                target_kind="report",
                target_id=report_id,
                before={"assigned_admin_tg_id": before},
                after={"assigned_admin_tg_id": admin_tg_id},
                reason="",
                meta=meta,
                now=now,
            )
            result = _report_row(report)
            await session.commit()
        return result

    async def decide(
        self,
        *,
        report_id: int,
        decision: str,
        resolution: str,
        admin_tg_id: int,
        meta: dict[str, str] | None,
    ) -> dict[str, Any]:
        if decision not in {"resolved", "dismissed"}:
            raise ApiError(
                400, "report_decision_invalid", "Qaror turi noto‘g‘ri."
            )
        resolution = resolution.strip()
        if not resolution:
            raise ApiError(
                400, "admin_reason_required", "Sabab kiritilishi shart."
            )
        now = self._now()
        async with self._session_factory() as session:
            report = await self._lock(session, report_id)
            if report.status not in DECIDABLE:
                raise ApiError(
                    409,
                    "report_already_decided",
                    "Shikoyat bo‘yicha qaror qabul qilingan.",
                )
            previous = report.status
            report.status = decision
            report.resolution = resolution[:2000]
            report.assigned_admin_tg_id = admin_tg_id
            report.updated_at = now
            await append_audit(
                session,
                admin_tg_id=admin_tg_id,
                action=f"report.{decision}",
                target_kind="report",
                target_id=report_id,
                before={"status": previous},
                after={"status": decision},
                reason=resolution,
                meta=meta,
                now=now,
            )
            result = _report_row(report)
            await session.commit()
        return result

    # --------------------------------------------------------------- audit

    async def list_audit(
        self,
        *,
        action: str = "",
        admin_tg_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        statement = select(AdminAuditLog)
        if action:
            statement = statement.where(AdminAuditLog.action == action)
        if admin_tg_id:
            statement = statement.where(
                AdminAuditLog.admin_tg_id == admin_tg_id
            )
        statement = statement.order_by(
            AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()
        ).limit(max(1, min(500, limit)))
        async with self._session_factory() as session:
            rows = list((await session.scalars(statement)).all())
            result = [self._audit_row(row) for row in rows]
            await session.rollback()
        return result

    async def audit_detail(self, audit_id: int) -> dict[str, Any]:
        async with self._session_factory() as session:
            row = await session.get(AdminAuditLog, audit_id)
            if row is None:
                raise ApiError(404, "audit_not_found", "Yozuv topilmadi.")
            result = self._audit_row(row, full=True)
            await session.rollback()
        return result

    async def audit_csv(self, *, action: str = "", limit: int = 500) -> str:
        rows = await self.list_audit(action=action, limit=limit)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "id", "created_at", "admin_tg_id", "action",
            "target_kind", "target_id", "reason",
        ])
        for row in rows:
            writer.writerow([
                row["id"],
                datetime.fromtimestamp(row["created_at"], UTC).isoformat(),
                row["admin_tg_id"],
                row["action"],
                row["target_kind"],
                row["target_id"],
                row["reason"],
            ])
        return buffer.getvalue()

    # ------------------------------------------------------------ yordamchi

    @staticmethod
    def _audit_row(row: AdminAuditLog, *, full: bool = False) -> dict[str, Any]:
        result = {
            "id": row.id,
            "admin_tg_id": row.admin_tg_id,
            "action": row.action,
            "target_kind": row.target_kind,
            "target_id": row.target_id,
            "reason": row.reason,
            "created_at": _unix(row.created_at),
        }
        if full:
            result["before"] = row.before_state or {}
            result["after"] = row.after_state or {}
            # Xom IP saqlanmagan; xesh faqat solishtirish uchun.
            result["ip_hash"] = row.ip_hash
            result["user_agent"] = row.user_agent
        return result

    @staticmethod
    async def _lock(
        session: AsyncSession, report_id: int
    ) -> ModerationReport:
        report = await session.scalar(
            select(ModerationReport)
            .where(ModerationReport.id == report_id)
            .with_for_update()
        )
        if report is None:
            raise ApiError(404, "report_not_found", "Shikoyat topilmadi.")
        return report
