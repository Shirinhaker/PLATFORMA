from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.follows.schemas import FollowListRead, FollowResult, FollowToggle
from app.follows.service import FollowService


router = APIRouter(prefix="/api/v1/follows", tags=["follows"])
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]


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


@router.get("/followers", response_model=FollowListRead)
async def list_followers(
    current: CurrentRead,
    service: Annotated[FollowService, Depends(follow_service)],
) -> FollowListRead:
    return await service.followers(account_id=current.account_id)


@router.get("/following", response_model=FollowListRead)
async def list_following(
    current: CurrentRead,
    service: Annotated[FollowService, Depends(follow_service)],
) -> FollowListRead:
    return await service.following(account_id=current.account_id)
