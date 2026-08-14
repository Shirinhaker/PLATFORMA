from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.core.errors import ApiError
from app.public_discovery.router import optional_current_account
from app.stories.schemas import (
    ManagedStoryRead,
    StoryCreate,
    StoryCreated,
    StoryGroup,
    StoryOk,
    StoryRead,
    StoryReportCreate,
    StoryViewResult,
    StoryViewerRead,
)
from app.stories.service import StoryService


router = APIRouter(prefix="/api/v1/stories", tags=["stories"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
StoryId = Annotated[int, Path(ge=1)]


def service(request: Request) -> StoryService:
    return request.app.state.story_service


def require_enabled(request: Request) -> None:
    if not request.app.state.settings.stories_enabled:
        raise ApiError(
            404,
            "feature_not_available",
            "Istoriyalar hozircha ochilmagan.",
        )


@router.get("/feed", response_model=list[StoryGroup])
async def story_feed(
    request: Request,
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    current: CurrentAccount | None = Depends(optional_current_account),
) -> list[StoryGroup]:
    require_enabled(request)
    return await service(request).feed(
        account_id=current.account_id if current is not None else None,
        account_type=current.account_type if current is not None else None,
        latitude=lat,
        longitude=lng,
    )


@router.get("/mine", response_model=list[ManagedStoryRead])
async def my_stories(
    request: Request,
    current: CurrentRead,
    state: Literal["active", "archived", "all"] = "all",
) -> list[ManagedStoryRead]:
    require_enabled(request)
    require_staff_permission(current, "ads")
    return await service(request).mine(
        account_id=current.account_id,
        state=state,
    )


@router.get(
    "/owner/{owner_type}/{owner_public_id}",
    response_model=list[StoryRead],
)
async def owner_stories(
    request: Request,
    owner_type: Literal["user", "business"],
    owner_public_id: Annotated[str, Path(pattern=r"^[ub]_[0-9a-f]{16}$")],
    current: CurrentAccount | None = Depends(optional_current_account),
) -> list[StoryRead]:
    require_enabled(request)
    return await service(request).owner_stories(
        owner_type=owner_type,
        owner_public_id=owner_public_id,
        viewer_account_id=current.account_id if current is not None else None,
    )


@router.post("", response_model=StoryCreated, status_code=201)
async def create_story(
    body: StoryCreate,
    request: Request,
    current: CurrentWrite,
) -> StoryCreated:
    require_enabled(request)
    require_staff_permission(current, "ads")
    return await service(request).create(
        account_id=current.account_id,
        account_type=current.account_type,
        staff_id=current.staff_id,
        body=body,
    )


@router.post("/{story_id}/view", response_model=StoryViewResult)
async def record_story_view(
    story_id: StoryId,
    request: Request,
    current: CurrentWrite,
) -> StoryViewResult:
    require_enabled(request)
    return await service(request).view(
        story_id=story_id,
        account_id=current.account_id,
    )


@router.get("/{story_id}/viewers", response_model=list[StoryViewerRead])
async def story_viewers(
    story_id: StoryId,
    request: Request,
    current: CurrentRead,
) -> list[StoryViewerRead]:
    require_enabled(request)
    require_staff_permission(current, "ads")
    return await service(request).viewers(
        story_id=story_id,
        owner_account_id=current.account_id,
    )


@router.delete("/{story_id}", status_code=204)
async def delete_story(
    story_id: StoryId,
    request: Request,
    current: CurrentWrite,
) -> Response:
    require_enabled(request)
    require_staff_permission(current, "ads")
    await service(request).delete(
        story_id=story_id,
        owner_account_id=current.account_id,
    )
    return Response(status_code=204)


@router.post("/{story_id}/reports", response_model=StoryOk)
async def report_story(
    story_id: StoryId,
    body: StoryReportCreate,
    request: Request,
    current: CurrentWrite,
) -> StoryOk:
    require_enabled(request)
    await service(request).report(
        story_id=story_id,
        reporter_account_id=current.account_id,
        reason=body.reason,
    )
    return StoryOk()
