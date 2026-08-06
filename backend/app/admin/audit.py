"""Admin amallarining o'zgartirib bo'lmaydigan jurnali.

Xom IP hech qachon saqlanmaydi — faqat server siri bilan HMAC xeshi.
Shu sababli jurnal kimningdir joylashuvini oshkor qilmaydi, lekin bir
xil manzildan kelgan amallarni solishtirish mumkin bo'lib qoladi.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.moderation_model import AdminAuditLog


def request_meta(request: Request, secret: str) -> dict[str, str]:
    """Chegaralangan metama'lumot; xom IP qaytarilmaydi."""
    raw_ip = request.client.host if request.client else ""
    digest = ""
    if raw_ip:
        digest = hmac.new(
            (secret or "koprik-admin-audit").encode("utf-8"),
            raw_ip.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    return {
        "ip_hash": digest,
        "user_agent": str(request.headers.get("user-agent", ""))[:500],
    }


async def append_audit(
    session: AsyncSession,
    *,
    admin_tg_id: int,
    action: str,
    target_kind: str,
    target_id: object,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    reason: str,
    meta: dict[str, str] | None,
    now: datetime,
) -> None:
    """Bitta yozuv qo'shadi; chaqiruvchining tranzaksiyasini yopmaydi.

    `flush` shu yerda chaqiriladi: yozuv id si darhol ma'lum bo'lsin va
    jurnal qatori chaqiruvchi keyingi so'rov yuborishidan oldin
    tranzaksiyaga tushsin.
    """
    meta = meta or {}
    session.add(AdminAuditLog(
        admin_tg_id=admin_tg_id,
        action=action.strip()[:80],
        target_kind=(target_kind or "unknown").strip()[:40],
        target_id="" if target_id is None else str(target_id)[:64],
        before_state=before or {},
        after_state=after or {},
        reason=(reason or "").strip()[:2000],
        ip_hash=str(meta.get("ip_hash", ""))[:128],
        user_agent=str(meta.get("user_agent", ""))[:500],
        created_at=now,
    ))
    await session.flush()
