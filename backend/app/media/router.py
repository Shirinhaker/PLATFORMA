from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_staff_permission
from app.core.errors import ApiError
from app.media.storage import UploadRejected


router = APIRouter(prefix="/api/v1/media", tags=["media"])


class UploadGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Literal[
        "avatar", "logo", "payment_qr", "listing_photo", "listing_video",
        "order_chat_image", "payment_receipt", "advertisement_image",
        "story_image", "story_video",
    ]
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1)


@router.post("/upload-grants")
async def create_upload_grant(
    body: UploadGrantRequest,
    request: Request,
    current: Annotated[CurrentAccount, Depends(require_csrf)],
):
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
        }.get(body.purpose, ("__business_owner__",))
        require_staff_permission(current, *required)
    allowed = body.purpose in {
        "listing_photo", "listing_video", "order_chat_image",
        "story_image", "story_video",
        # Reklamani oddiy foydalanuvchi ham joylashi mumkin.
        "payment_receipt", "advertisement_image",
    } or (
        current.account_type is AccountType.USER
        and body.purpose == "avatar"
    ) or (
        current.account_type is AccountType.BUSINESS
        and body.purpose in {"logo", "payment_qr"}
    )
    if not allowed:
        raise ApiError(
            403,
            "media_purpose_forbidden",
            "Bu rasm turi akkauntga mos emas.",
        )
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
        raise ApiError(
            400,
            "media_upload_rejected",
            str(exc),
        ) from None
    return grant
