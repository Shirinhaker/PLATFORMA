from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.auth.repository import create_session, lock_session
from app.auth.router import _set_session_cookie
from app.auth.security import derive_csrf
from app.cabinet_records.repository import CabinetRecordRepository
from app.core.errors import ApiError
from app.notifications.repository import NotificationRepository
from app.profiles.model import ProfileLink
from app.profiles.repository import (
    get_business_profile,
    get_user_profile,
    patch_business_profile,
    patch_user_profile,
)
from app.profiles.schemas import (
    BusinessPaymentQrAttachment,
    BusinessProfilePatch,
    BusinessProfileRead,
    CabinetSwitchRead,
    CabinetSwitchRequest,
    MeRead,
    ProfileImageAttachment,
    UserProfilePatch,
    UserProfileRead,
)
from app.profiles.summary_service import ProfileSummaryService


router = APIRouter(prefix="/api/v1", tags=["profiles"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
_cabinet_records = CabinetRecordRepository()
_notifications = NotificationRepository()


async def profile_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session() as session:
        yield session


ProfileSession = Annotated[AsyncSession, Depends(profile_session)]


def get_profile_summary_service(request: Request) -> ProfileSummaryService:
    return request.app.state.profile_summary_service


ProfileSummary = Annotated[
    ProfileSummaryService,
    Depends(get_profile_summary_service),
]


def require_account_type(
    current: CurrentAccount,
    expected: AccountType,
) -> None:
    if current.account_type is not expected:
        raise ApiError(
            403,
            "profile_type_forbidden",
            "Bu profil turiga kirish mumkin emas.",
        )


def require_profile_object_key(
    object_key: str,
    *,
    account_type: AccountType,
    account_id: int,
    purpose: str,
) -> None:
    prefix = f"private/{account_type.value}/{account_id}/{purpose}/"
    allowed = re.fullmatch(
        re.escape(prefix) + r"[0-9a-f]{32}\.(?:jpg|png|webp|gif)",
        object_key,
    )
    if allowed is None:
        raise ApiError(
            403,
            "media_object_forbidden",
            "Bu media obyekti akkauntga tegishli emas.",
        )


async def assembled_cabinet_payload(
    session: AsyncSession,
    *,
    account_id: int,
    account_type: AccountType,
    fallback: object,
) -> dict[str, Any]:
    result = dict(fallback) if isinstance(fallback, dict) else {}
    relational = await _cabinet_records.read_payload(
        session,
        account_id=account_id,
        account_type=account_type.value,
    )
    result.update(relational)
    notification_rows = await _notifications.list_rows(
        session,
        account_id=account_id,
        account_type=account_type.value,
    )
    if notification_rows is not None:
        result["notifications"] = notification_rows
    return result


def dashboard_with_notification_count(
    profile,
    cabinet_payload: dict[str, Any],
) -> dict[str, Any]:
    def is_read(row: dict[str, Any]) -> bool:
        value = row.get("is_read")
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "on"}
        try:
            return bool(int(value or 0))
        except (TypeError, ValueError):
            return bool(value)

    snapshot = dict(profile.dashboard_snapshot or {})
    rows = cabinet_payload.get("notifications")
    if isinstance(rows, list):
        snapshot["unread"] = sum(
            not is_read(row)
            for row in rows
            if isinstance(row, dict)
        )
    return snapshot


def business_profile_read(
    request: Request,
    profile,
    *,
    cabinet_payload: dict[str, Any] | None = None,
) -> BusinessProfileRead:
    updates: dict[str, Any] = {
        "logo_url": request.app.state.r2.create_download_url(
            profile.logo_object_key
        ),
        "pay_qr_url": request.app.state.r2.create_download_url(
            profile.pay_qr_object_key
        ),
    }
    if cabinet_payload is not None:
        updates["cabinet_payload"] = cabinet_payload
        updates["dashboard_snapshot"] = dashboard_with_notification_count(
            profile,
            cabinet_payload,
        )
    return BusinessProfileRead.model_validate(profile).model_copy(update=updates)


async def user_profile_read(session: AsyncSession, profile) -> UserProfileRead:
    payload = await assembled_cabinet_payload(
        session,
        account_id=profile.account_id,
        account_type=AccountType.USER,
        fallback=profile.cabinet_payload,
    )
    return UserProfileRead.model_validate(profile).model_copy(
        update={
            "cabinet_payload": payload,
            "dashboard_snapshot": dashboard_with_notification_count(
                profile,
                payload,
            ),
        }
    )


async def business_profile_response(
    request: Request,
    session: AsyncSession,
    profile,
) -> BusinessProfileRead:
    payload = await assembled_cabinet_payload(
        session,
        account_id=profile.account_id,
        account_type=AccountType.BUSINESS,
        fallback=profile.cabinet_payload,
    )
    return business_profile_read(request, profile, cabinet_payload=payload)


@router.get("/me", response_model=MeRead)
async def get_me(
    current: CurrentRead,
    summaries: ProfileSummary,
) -> MeRead:
    return await summaries.resolve(current.account_type, current.account_id)


@router.get("/user-profile", response_model=UserProfileRead)
async def read_user_profile(current: CurrentRead, session: ProfileSession):
    require_account_type(current, AccountType.USER)
    profile = await get_user_profile(session, current.account_id)
    return await user_profile_read(session, profile)


@router.put("/user-profile", response_model=UserProfileRead)
async def update_user_profile(
    body: UserProfilePatch,
    current: CurrentWrite,
    session: ProfileSession,
    summaries: ProfileSummary,
):
    require_account_type(current, AccountType.USER)
    try:
        profile = await get_user_profile(session, current.account_id)
        await patch_user_profile(session, profile, body)
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        return await user_profile_read(session, profile)
    except Exception:
        await session.rollback()
        raise


@router.get("/business-profile", response_model=BusinessProfileRead)
async def read_business_profile(
    request: Request,
    current: CurrentRead,
    session: ProfileSession,
):
    require_account_type(current, AccountType.BUSINESS)
    profile = await get_business_profile(session, current.account_id)
    return await business_profile_response(request, session, profile)


@router.put("/business-profile", response_model=BusinessProfileRead)
async def update_business_profile(
    body: BusinessProfilePatch,
    request: Request,
    current: CurrentWrite,
    session: ProfileSession,
    summaries: ProfileSummary,
):
    require_account_type(current, AccountType.BUSINESS)
    if (
        "pay_qr_object_key" in body.model_fields_set
        and body.pay_qr_object_key
    ):
        require_profile_object_key(
            body.pay_qr_object_key,
            account_type=AccountType.BUSINESS,
            account_id=current.account_id,
            purpose="payment_qr",
        )
    try:
        profile = await get_business_profile(session, current.account_id)
        await patch_business_profile(session, profile, body)
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        return await business_profile_response(request, session, profile)
    except Exception:
        await session.rollback()
        raise


@router.post("/cabinet/switch", response_model=CabinetSwitchRead)
async def switch_cabinet(
    body: CabinetSwitchRequest,
    request: Request,
    response: Response,
    current: CurrentWrite,
    session: ProfileSession,
):
    if body.target_type is current.account_type:
        raise ApiError(409, "cabinet_already_active", "Tanlangan kabinet allaqachon ochiq.")

    link = (
        await session.get(ProfileLink, current.account_id)
        if current.account_type is AccountType.USER
        else None
    )
    if current.account_type is AccountType.BUSINESS:
        from sqlalchemy import select

        link = await session.scalar(
            select(ProfileLink).where(
                ProfileLink.business_account_id == current.account_id
            )
        )
    if link is None:
        raise ApiError(404, "linked_cabinet_not_found", "Bog‘langan kabinet topilmadi.")

    target_id = (
        link.business_account_id
        if body.target_type is AccountType.BUSINESS
        else link.user_account_id
    )
    target = await session.get(Account, target_id)
    if target is None or target.status != "active" or target.account_type is not body.target_type:
        raise ApiError(404, "linked_cabinet_not_found", "Bog‘langan kabinet topilmadi.")

    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=request.app.state.settings.session_ttl_seconds)
    try:
        old_session = await lock_session(session, current.session_token)
        if old_session is not None and old_session.revoked_at is None:
            old_session.revoked_at = now
        _, raw_token = await create_session(
            session,
            account_id=target.id,
            device_name="cabinet-switch",
            now=now,
            expires_at=expires_at,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    await request.app.state.auth_service._revoke_cached_session(current.session_token)
    _set_session_cookie(response, request, raw_token)
    return CabinetSwitchRead(
        account_id=target.id,
        account_type=target.account_type,
        login=target.login,
        csrf_token=derive_csrf(raw_token, request.app.state.settings.csrf_secret),
        expires_at=expires_at.isoformat(),
    )


@router.put("/user-profile/avatar", response_model=UserProfileRead)
async def attach_user_avatar(
    body: ProfileImageAttachment,
    current: CurrentWrite,
    session: ProfileSession,
    summaries: ProfileSummary,
):
    require_account_type(current, AccountType.USER)
    require_profile_object_key(
        body.object_key,
        account_type=AccountType.USER,
        account_id=current.account_id,
        purpose="avatar",
    )
    try:
        profile = await get_user_profile(session, current.account_id)
        profile.avatar_object_key = body.object_key
        profile.avatar_x = body.x
        profile.avatar_y = body.y
        profile.avatar_zoom = body.zoom
        await session.flush()
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        return await user_profile_read(session, profile)
    except Exception:
        await session.rollback()
        raise


@router.put("/business-profile/logo", response_model=BusinessProfileRead)
async def attach_business_logo(
    body: ProfileImageAttachment,
    request: Request,
    current: CurrentWrite,
    session: ProfileSession,
    summaries: ProfileSummary,
):
    require_account_type(current, AccountType.BUSINESS)
    require_profile_object_key(
        body.object_key,
        account_type=AccountType.BUSINESS,
        account_id=current.account_id,
        purpose="logo",
    )
    try:
        profile = await get_business_profile(session, current.account_id)
        profile.logo_object_key = body.object_key
        profile.logo_x = body.x
        profile.logo_y = body.y
        profile.logo_zoom = body.zoom
        await session.flush()
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        return await business_profile_response(request, session, profile)
    except Exception:
        await session.rollback()
        raise


@router.put("/business-profile/payment-qr", response_model=BusinessProfileRead)
async def attach_business_payment_qr(
    body: BusinessPaymentQrAttachment,
    request: Request,
    current: CurrentWrite,
    session: ProfileSession,
    summaries: ProfileSummary,
):
    require_account_type(current, AccountType.BUSINESS)
    if body.object_key:
        require_profile_object_key(
            body.object_key,
            account_type=AccountType.BUSINESS,
            account_id=current.account_id,
            purpose="payment_qr",
        )
    try:
        profile = await get_business_profile(session, current.account_id)
        profile.pay_qr_object_key = body.object_key
        await session.flush()
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        return await business_profile_response(request, session, profile)
    except Exception:
        await session.rollback()
        raise
