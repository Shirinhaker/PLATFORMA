from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.reviews.schemas import (
    ReviewListRead,
    ReviewMutationRead,
    ReviewRead,
    ReviewReplyWrite,
    ReviewTargetKind,
    ReviewWrite,
)
from app.reviews.service import ReviewService


router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
PublicId = Annotated[str, Path(pattern=r"^[ub]_[0-9a-f]{16}$")]
ReviewId = Annotated[int, Path(gt=0)]


def service(request: Request) -> ReviewService:
    return request.app.state.review_service


async def optional_current_account(request: Request) -> CurrentAccount | None:
    token = request.cookies.get(request.app.state.settings.auth_cookie_name)
    if not token:
        return None
    identity = await request.app.state.auth_service.resolve_session(
        token, datetime.now(UTC)
    )
    if identity is None:
        staff_service = getattr(request.app.state, "staff_service", None)
        if staff_service is not None:
            identity = await staff_service.resolve_session(
                token, datetime.now(UTC)
            )
    if identity is None:
        return None
    return CurrentAccount(
        account_id=identity.account_id,
        account_type=identity.account_type,
        session_token=token,
        actor_type=identity.actor_type,
        staff_id=identity.staff_id,
        permissions=tuple(identity.permissions),
    )


@router.get("/received", response_model=ReviewListRead)
async def received(request: Request, current: CurrentRead):
    require_staff_permission(current, "reviews")
    return await service(request).received(
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.get(
    "/{target_kind}/{target_public_id}",
    response_model=ReviewListRead,
)
async def public_reviews(
    target_kind: ReviewTargetKind,
    target_public_id: PublicId,
    request: Request,
    current: CurrentAccount | None = Depends(optional_current_account),
):
    return await service(request).public_list(
        target_kind=target_kind,
        target_public_id=target_public_id,
        reviewer_account_id=current.account_id if current else None,
        reviewer_account_type=current.account_type if current else None,
    )


@router.post("", response_model=ReviewMutationRead)
async def save_review(body: ReviewWrite, request: Request, current: CurrentWrite):
    return await service(request).save(
        reviewer_account_id=current.account_id,
        reviewer_account_type=current.account_type,
        body=body,
    )


@router.delete(
    "/{target_kind}/{target_public_id}",
    response_model=ReviewMutationRead,
)
async def delete_review(
    target_kind: ReviewTargetKind,
    target_public_id: PublicId,
    request: Request,
    current: CurrentWrite,
):
    return await service(request).delete_own(
        reviewer_account_id=current.account_id,
        reviewer_account_type=current.account_type,
        target_kind=target_kind,
        target_public_id=target_public_id,
    )


@router.put("/{review_id}/reply", response_model=ReviewRead)
async def reply_to_review(
    review_id: ReviewId,
    body: ReviewReplyWrite,
    request: Request,
    current: CurrentWrite,
):
    require_staff_permission(current, "reviews")
    return await service(request).reply(
        review_id=review_id,
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )
