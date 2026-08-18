"""Akkauntlar, cheklovlar va kontent holati."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from app.admin.dependencies import CurrentAdmin
from app.admin.router_parts.constants import (
    CONTENT_ACTIONS,
    AccountId,
    ActorType,
    ContentKind,
    ModerationDep,
)
from app.admin.router_parts.deps import (
    _meta,
)
from app.admin.schemas import (
    AdminAccountDetail,
    AdminAccountRow,
    AdminContentResult,
    AdminContentStatus,
    AdminContentWrite,
    AdminNoteRow,
    AdminNoteWrite,
    AdminRestrictionResult,
    AdminRestrictionWrite,
)

router = APIRouter()


@router.get("/accounts/{actor_type}", response_model=list[AdminAccountRow])
async def admin_accounts(
    actor_type: ActorType,
    admin: CurrentAdmin,
    service: ModerationDep,
    query: Annotated[str, Query(max_length=120)] = "",
    restriction: Annotated[str, Query(max_length=32)] = "",
) -> list[AdminAccountRow]:
    del admin
    rows = await service.list_accounts(
        actor_type=actor_type, query=query, restriction=restriction
    )
    return [AdminAccountRow(**row) for row in rows]


@router.get("/accounts/{actor_type}/{account_id}", response_model=AdminAccountDetail)
async def admin_account_detail(
    actor_type: ActorType,
    account_id: AccountId,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminAccountDetail:
    del admin
    return AdminAccountDetail(
        **await service.account_detail(actor_type=actor_type, account_id=account_id)
    )


@router.post(
    "/accounts/{actor_type}/{account_id}/restrict",
    response_model=AdminRestrictionResult,
)
async def admin_restrict_account(
    actor_type: ActorType,
    account_id: AccountId,
    body: AdminRestrictionWrite,
    request: Request,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminRestrictionResult:
    return AdminRestrictionResult(
        **await service.restrict(
            actor_type=actor_type,
            account_id=account_id,
            restriction=body.restriction,
            reason=body.reason,
            admin_tg_id=admin,
            meta=_meta(request),
        )
    )


@router.post(
    "/accounts/{actor_type}/{account_id}/unrestrict",
    response_model=AdminRestrictionResult,
)
async def admin_unrestrict_account(
    actor_type: ActorType,
    account_id: AccountId,
    body: AdminRestrictionWrite,
    request: Request,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminRestrictionResult:
    return AdminRestrictionResult(
        **await service.unrestrict(
            actor_type=actor_type,
            account_id=account_id,
            restriction=body.restriction,
            reason=body.reason,
            admin_tg_id=admin,
            meta=_meta(request),
        )
    )


@router.post(
    "/accounts/{actor_type}/{account_id}/notes",
    response_model=AdminNoteRow,
    status_code=201,
)
async def admin_add_note(
    actor_type: ActorType,
    account_id: AccountId,
    body: AdminNoteWrite,
    request: Request,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminNoteRow:
    return AdminNoteRow(
        **await service.add_note(
            actor_type=actor_type,
            account_id=account_id,
            note=body.note,
            admin_tg_id=admin,
            meta=_meta(request),
        )
    )


@router.get("/content/{content_kind}/{content_id}", response_model=AdminContentStatus)
async def admin_content_status(
    content_kind: ContentKind,
    content_id: AccountId,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminContentStatus:
    del admin
    return AdminContentStatus(
        **await service.content_status(content_kind=content_kind, content_id=content_id)
    )


@router.post(
    "/content/{content_kind}/{content_id}/{action}",
    response_model=AdminContentResult,
)
async def admin_set_content_status(
    content_kind: ContentKind,
    content_id: AccountId,
    action: Annotated[str, Path(pattern="^(hide|restore|remove)$")],
    body: AdminContentWrite,
    request: Request,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminContentResult:
    return AdminContentResult(
        **await service.set_content_status(
            content_kind=content_kind,
            content_id=content_id,
            status=CONTENT_ACTIONS[action],
            reason=body.reason,
            admin_tg_id=admin,
            meta=_meta(request),
        )
    )
