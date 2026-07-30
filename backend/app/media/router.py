from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf
from app.core.errors import ApiError
from app.media.storage import UploadRejected


router = APIRouter(prefix="/api/v1/media", tags=["media"])


class UploadGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Literal["avatar", "logo", "payment_qr"]
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1)


@router.post("/upload-grants")
async def create_upload_grant(
    body: UploadGrantRequest,
    request: Request,
    current: Annotated[CurrentAccount, Depends(require_csrf)],
):
    allowed = (
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
