from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_staff_permission
from app.cache.rate_limit import consume_rate_limit, consume_weighted_rate_limit
from app.core.errors import ApiError
from app.media.storage import UploadRejected


router = APIRouter(prefix="/api/v1/media", tags=["media"])
MediaPurpose = Literal[
    "avatar", "logo", "payment_qr", "listing_photo", "listing_video",
    "order_chat_image", "chat_image", "payment_receipt", "advertisement_image",
    "story_image", "story_video", "specialist_credential", "specialist_offer_image",
    "specialist_portfolio_image", "specialist_portfolio_video",
]


class UploadGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: MediaPurpose
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1)


def _redis(request: Request):
    wrapper = request.app.state.redis
    client = getattr(wrapper, "client", None)
    return client if client is not None and not callable(client) else wrapper


def _require_purpose_access(current: CurrentAccount, purpose: str) -> None:
    if current.actor_type == "staff":
        required = {
            "listing_photo": ("ads",),
            "listing_video": ("ads",),
            "story_image": ("ads",),
            "story_video": ("ads",),
            "order_chat_image": (
                "buyurtma", "service_orders", "dining_internal",
                "dining_external", "kitchen",
            ),
            "chat_image": ("chats",),
        }.get(purpose, ("__business_owner__",))
        require_staff_permission(current, *required)

    allowed = purpose in {
        "listing_photo", "listing_video", "order_chat_image", "chat_image",
        "story_image", "story_video", "payment_receipt", "advertisement_image",
    } or (
        current.account_type is AccountType.USER
        and purpose in {
            "avatar", "specialist_credential", "specialist_offer_image",
            "specialist_portfolio_image", "specialist_portfolio_video",
        }
    ) or (
        current.account_type is AccountType.BUSINESS
        and purpose in {"logo", "payment_qr"}
    )
    if not allowed:
        raise ApiError(
            403,
            "media_purpose_forbidden",
            "Bu media turi akkauntga mos emas.",
        )


async def _limit_upload_grant(
    request: Request,
    *,
    account_id: int,
    size_bytes: int,
) -> None:
    redis = _redis(request)
    request_limit = await consume_rate_limit(
        redis,
        f"media-grant:count:{account_id}",
        30,
        10 * 60,
    )
    if not request_limit.allowed:
        raise ApiError(
            429,
            "media_upload_rate_limited",
            "Juda ko‘p media yuklash boshlandi. Biroz kuting.",
            headers={"Retry-After": str(request_limit.retry_after_seconds)},
        )

    for key, limit, window in (
        ("hour", 1024 * 1024 * 1024, 60 * 60),
        ("day", 5 * 1024 * 1024 * 1024, 24 * 60 * 60),
    ):
        quota = await consume_weighted_rate_limit(
            redis,
            f"media-grant:bytes:{key}:{account_id}",
            cost=size_bytes,
            limit=limit,
            window_seconds=window,
        )
        if not quota.allowed:
            raise ApiError(
                429,
                "media_upload_quota_exceeded",
                "Media yuklash hajmi limiti tugadi. Keyinroq qayta urinib ko‘ring.",
                headers={"Retry-After": str(quota.retry_after_seconds)},
            )


@router.post("/upload-grants")
async def create_upload_grant(
    body: UploadGrantRequest,
    request: Request,
    current: Annotated[CurrentAccount, Depends(require_csrf)],
):
    _require_purpose_access(current, body.purpose)
    try:
        grant = request.app.state.r2.create_upload_grant(
            owner_type=current.account_type,
            owner_id=current.account_id,
            purpose=body.purpose,
            filename=body.filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
    except UploadRejected as exc:
        raise ApiError(400, "media_upload_rejected", str(exc)) from None

    await _limit_upload_grant(
        request,
        account_id=current.account_id,
        size_bytes=body.size_bytes,
    )
    return grant
