from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import CurrentAccount, require_csrf
from app.follows.schemas import FollowResult, FollowToggle
from app.follows.service import FollowService


router = APIRouter(prefix="/api/v1/follows", tags=["follows"])
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def follow_service(request: Request) -> FollowService:
    return request.app.state.follow_service


@router.post("/toggle", response_model=FollowResult)
async def toggle_follow(
    body: FollowToggle,
    current: CurrentWrite,
    service: Annotated[FollowService, Depends(follow_service)],
) -> FollowResult:
    """v1656 kabi bitta amal: obuna bo'ladi yoki bekor qiladi."""
    return await service.toggle(account_id=current.account_id, body=body)
