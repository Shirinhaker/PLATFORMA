from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.core.errors import ApiError
from app.messages.schemas import (
    MessageConversationRead,
    MessageCreate,
    MessageEdit,
    MessageImageCreate,
    MessageRead,
    MessageThreadRead,
    MessageUnreadRead,
)
from app.messages.service import MessageService


router = APIRouter(prefix="/api/v1/messages", tags=["messages"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
MessageId = Annotated[int, Path(gt=0)]


def service(request: Request) -> MessageService:
    return request.app.state.message_service


def require_enabled(request: Request) -> None:
    if not request.app.state.settings.chat_enabled:
        raise ApiError(
            404,
            "feature_not_available",
            "Suhbatlar hozircha ochilmagan.",
        )


def require_chat_access(current: CurrentAccount) -> None:
    require_staff_permission(current, "chats")


@router.get("/conversations", response_model=list[MessageConversationRead])
async def conversations(request: Request, current: CurrentRead):
    require_enabled(request)
    require_chat_access(current)
    return await service(request).conversations(account_id=current.account_id)


@router.get(
    "/with/{target_kind}/{target_public_id}",
    response_model=MessageThreadRead,
)
async def thread(
    target_kind: AccountType,
    target_public_id: Annotated[str, Path(pattern=r"^[ub]_[0-9a-f]{16}$")],
    request: Request,
    current: CurrentRead,
):
    require_enabled(request)
    require_chat_access(current)
    return await service(request).thread(
        account_id=current.account_id,
        target_kind=target_kind,
        target_public_id=target_public_id,
    )


@router.post("/send", response_model=MessageRead, status_code=201)
async def send_text(body: MessageCreate, request: Request, current: CurrentWrite):
    require_enabled(request)
    require_chat_access(current)
    return await service(request).send_text(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.post("/image", response_model=MessageRead, status_code=201)
async def send_image(
    body: MessageImageCreate,
    request: Request,
    current: CurrentWrite,
):
    require_enabled(request)
    require_chat_access(current)
    return await service(request).send_image(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.put("/{message_id}", response_model=MessageRead)
async def edit_message(
    message_id: MessageId,
    body: MessageEdit,
    request: Request,
    current: CurrentWrite,
):
    require_enabled(request)
    require_chat_access(current)
    return await service(request).edit(
        message_id=message_id,
        account_id=current.account_id,
        body=body,
    )


@router.delete("/{message_id}", response_model=MessageRead)
async def delete_message(
    message_id: MessageId,
    request: Request,
    current: CurrentWrite,
):
    require_enabled(request)
    require_chat_access(current)
    return await service(request).delete(
        message_id=message_id,
        account_id=current.account_id,
    )


@router.get("/unread-count", response_model=MessageUnreadRead)
async def unread_count(request: Request, current: CurrentRead):
    require_enabled(request)
    require_chat_access(current)
    return await service(request).unread_count(account_id=current.account_id)
