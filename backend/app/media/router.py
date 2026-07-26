from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.media.storage import UploadRejected


router = APIRouter(prefix="/api/v1/media", tags=["media"])


class UploadGrantRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1)


@router.post("/upload-grants")
async def create_upload_grant(
    body: UploadGrantRequest,
    request: Request,
    x_foundation_actor_id: int | None = Header(default=None),
):
    settings = request.app.state.settings
    if settings.environment not in {"test", "staging"}:
        raise HTTPException(
            status_code=503,
            detail="Media autentifikatsiyasi hali production uchun yoqilmagan.",
        )
    if x_foundation_actor_id is None or x_foundation_actor_id < 1:
        raise HTTPException(
            status_code=401,
            detail="Foundation actor identifikatori talab qilinadi.",
        )
    try:
        grant = request.app.state.r2.create_upload_grant(
            actor_id=x_foundation_actor_id,
            filename=body.filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return grant
