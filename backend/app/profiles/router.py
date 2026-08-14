import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_business_owner,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.auth.repository import create_session, lock_session
from app.auth.router import _set_session_cookie
from app.auth.security import derive_csrf
from app.cabinet_records.repository import CabinetRecordRepository
from app.core.errors import ApiError
from app.notifications.repository import NotificationRepository
from app.media.storage import UploadRejected
from app.media.model import MediaUploadGrant
from app.outbox.repository import enqueue_event
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
from app.public_ids import build_profile_public_id
from app.business_online.service_relational import (
    RELATIONAL_EDUCATION_RESOURCES,
)
from app.education.repository import EducationEnrollmentRepository
from app.staff.permissions import allowed_payload_resources


router = APIRouter(prefix="/api/v1", tags=["profiles"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
_cabinet_records = CabinetRecordRepository()
_notifications = NotificationRepository()
_education = EducationEnrollmentRepository()


async def verify_profile_upload(request: Request, object_key: str) -> None:
    try:
        await asyncio.to_thread(
            request.app.state.r2.verify_profile_image,
            object_key,
        )
    except UploadRejected as exc:
        try:
            await asyncio.to_thread(
                request.app.state.r2.delete_object,
                object_key,
            )
        except Exception:
            await defer_profile_object_cleanup(request, object_key)
        raise ApiError(400, "media_upload_rejected", str(exc)) from None


async def defer_profile_object_cleanup(request: Request, object_key: str) -> None:
    database = getattr(request.app.state, "database", None)
    if database is None:
        return
    try:
        async with database.session() as session:
            await enqueue_event(
                session,
                "media.object.delete",
                {"object_key": object_key},
            )
            await session.commit()
    except Exception:
        # A periodic orphan sweep remains the final fallback for unattached
        # uploads when even the cleanup event cannot be persisted.
        return


async def delete_replaced_profile_object(
    request: Request,
    old_key: str,
    new_key: str | None,
) -> None:
    if not old_key or old_key == new_key:
        return
    try:
        await asyncio.to_thread(request.app.state.r2.delete_object, old_key)
    except Exception:
        # Profil yozuvi saqlangan; cleanup xatosi foydalanuvchi amalini buzmaydi.
        await defer_profile_object_cleanup(request, old_key)


async def mark_profile_upload_attached(
    session: AsyncSession,
    object_key: str | None,
) -> None:
    if not object_key:
        return
    grant = await session.scalar(
        select(MediaUploadGrant)
        .where(
            MediaUploadGrant.object_key == object_key,
            MediaUploadGrant.status == "pending",
        )
        .with_for_update()
    )
    if grant is not None:
        grant.status = "attached"
        grant.attached_at = datetime.now(UTC)


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
    if account_type is AccountType.BUSINESS:
        # Ta'lim resurslari o'z jadvallariga ko'chirilgan.
        for resource in RELATIONAL_EDUCATION_RESOURCES:
            rows = await _education.list_rows(
                session,
                business_account_id=account_id,
                resource=resource,
            )
            if rows is not None:
                result[resource] = rows
    return result


def runtime_cabinet_fallback(request: Request, payload: object) -> object:
    # Compatibility fixtures still exercise the old JSON projection in tests.
    # Every deploy environment reads only normalized relational records.
    settings = getattr(request.app.state, "settings", None)
    if settings is not None and settings.environment == "test":
        return payload
    return {}


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


async def user_profile_response(
    request: Request,
    session: AsyncSession,
    profile,
) -> UserProfileRead:
    payload = await assembled_cabinet_payload(
        session,
        account_id=profile.account_id,
        account_type=AccountType.USER,
        fallback=runtime_cabinet_fallback(request, profile.cabinet_payload),
    )
    return UserProfileRead.model_validate(profile).model_copy(
        update={
            "public_id": profile.public_id or build_profile_public_id(
                "user",
                profile.account_id,
            ),
            "avatar_url": request.app.state.r2.create_download_url(
                profile.avatar_object_key
            ),
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
    *,
    current: CurrentAccount | None = None,
) -> BusinessProfileRead:
    payload = await assembled_cabinet_payload(
        session,
        account_id=profile.account_id,
        account_type=AccountType.BUSINESS,
        fallback=runtime_cabinet_fallback(request, profile.cabinet_payload),
    )
    response = business_profile_read(request, profile, cabinet_payload=payload)
    if current is None or current.actor_type != "staff":
        return response
    allowed = allowed_payload_resources(current.permissions)
    filtered = {name: value for name, value in payload.items() if name in allowed}
    return response.model_copy(update={
        "pay_card": "",
        "pay_holder": "",
        "pay_qr_object_key": "",
        "pay_qr_url": "",
        "director": "",
        "tax_id": "",
        "cabinet_payload": filtered,
        "dashboard_snapshot": {},
        "recent_activity": [],
    })


@router.get("/me", response_model=MeRead)
async def get_me(
    current: CurrentRead,
    summaries: ProfileSummary,
) -> MeRead:
    require_staff_permission(current, "__business_owner__")
    return await summaries.resolve(current.account_type, current.account_id)


@router.get("/user-profile", response_model=UserProfileRead)
async def read_user_profile(
    request: Request,
    current: CurrentRead,
    session: ProfileSession,
):
    require_account_type(current, AccountType.USER)
    profile = await get_user_profile(session, current.account_id)
    return await user_profile_response(request, session, profile)


@router.put("/user-profile", response_model=UserProfileRead)
async def update_user_profile(
    body: UserProfilePatch,
    request: Request,
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
        return await user_profile_response(request, session, profile)
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
    return await business_profile_response(
        request,
        session,
        profile,
        current=current,
    )


@router.put("/business-profile", response_model=BusinessProfileRead)
async def update_business_profile(
    body: BusinessProfilePatch,
    request: Request,
    current: CurrentWrite,
    session: ProfileSession,
    summaries: ProfileSummary,
):
    require_account_type(current, AccountType.BUSINESS)
    require_business_owner(current)
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
        await verify_profile_upload(request, body.pay_qr_object_key)
    try:
        profile = await get_business_profile(session, current.account_id)
        old_qr_key = profile.pay_qr_object_key
        await patch_business_profile(session, profile, body)
        if "pay_qr_object_key" in body.model_fields_set:
            await mark_profile_upload_attached(
                session,
                body.pay_qr_object_key,
            )
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        response = await business_profile_response(request, session, profile)
        if "pay_qr_object_key" in body.model_fields_set:
            await delete_replaced_profile_object(
                request,
                old_qr_key,
                body.pay_qr_object_key,
            )
        return response
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
    require_staff_permission(current, "__business_owner__")
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
    request: Request,
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
    await verify_profile_upload(request, body.object_key)
    try:
        profile = await get_user_profile(session, current.account_id)
        old_key = profile.avatar_object_key
        profile.avatar_object_key = body.object_key
        profile.avatar_x = body.x
        profile.avatar_y = body.y
        profile.avatar_zoom = body.zoom
        await mark_profile_upload_attached(session, body.object_key)
        await session.flush()
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        response = await user_profile_response(request, session, profile)
        await delete_replaced_profile_object(request, old_key, body.object_key)
        return response
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
    require_business_owner(current)
    require_profile_object_key(
        body.object_key,
        account_type=AccountType.BUSINESS,
        account_id=current.account_id,
        purpose="logo",
    )
    await verify_profile_upload(request, body.object_key)
    try:
        profile = await get_business_profile(session, current.account_id)
        old_key = profile.logo_object_key
        profile.logo_object_key = body.object_key
        profile.logo_x = body.x
        profile.logo_y = body.y
        profile.logo_zoom = body.zoom
        await mark_profile_upload_attached(session, body.object_key)
        await session.flush()
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        response = await business_profile_response(request, session, profile)
        await delete_replaced_profile_object(request, old_key, body.object_key)
        return response
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
    require_business_owner(current)
    if body.object_key:
        require_profile_object_key(
            body.object_key,
            account_type=AccountType.BUSINESS,
            account_id=current.account_id,
            purpose="payment_qr",
        )
        await verify_profile_upload(request, body.object_key)
    try:
        profile = await get_business_profile(session, current.account_id)
        old_key = profile.pay_qr_object_key
        profile.pay_qr_object_key = body.object_key
        await mark_profile_upload_attached(session, body.object_key)
        await session.flush()
        await session.commit()
        await summaries.invalidate(current.account_type, current.account_id)
        response = await business_profile_response(request, session, profile)
        await delete_replaced_profile_object(request, old_key, body.object_key)
        return response
    except Exception:
        await session.rollback()
        raise
