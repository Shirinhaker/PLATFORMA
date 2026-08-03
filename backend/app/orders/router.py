from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.orders.schemas import (
    OrderMessageCreate,
    OrderMessageEdit,
    OrderMessageRead,
    OrderPaymentDecision,
    OrderProblemCreate,
    OrderProblemSolution,
    OrderRead,
    OrderStatusChange,
    OrderCreate,
    OrderChatRead,
)
from app.orders.service import OrderService


router = APIRouter(prefix="/api/v1/orders", tags=["orders"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
OrderId = Annotated[int, Path(gt=0)]
MessageId = Annotated[int, Path(gt=0)]


def service(request: Request) -> OrderService:
    return request.app.state.order_service


ORDER_PERMISSIONS = (
    "buyurtma", "service_orders", "dining_internal", "dining_external", "kitchen",
)


def require_order_permission(current: CurrentAccount) -> None:
    require_staff_permission(current, *ORDER_PERMISSIONS)


def staff_order_categories(current: CurrentAccount) -> frozenset[str] | None:
    if current.actor_type != "staff":
        return None
    require_order_permission(current)
    categories: set[str] = set()
    if "service_orders" in current.permissions:
        categories.add("service")
    if set(current.permissions).intersection({
        "buyurtma", "dining_internal", "dining_external", "kitchen",
    }):
        categories.add("product")
    return frozenset(categories)


async def require_staff_order_access(
    request: Request,
    current: CurrentAccount,
    order_id: int,
) -> None:
    categories = staff_order_categories(current)
    if categories is not None:
        await service(request).assert_staff_provider_access(
            order_id=order_id,
            account_id=current.account_id,
            allowed_categories=categories,
        )


@router.post("", response_model=OrderRead, status_code=201)
async def create_order(body: OrderCreate, request: Request, current: CurrentWrite):
    require_staff_permission(current, "__business_owner__")
    return await service(request).create(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.get("/my", response_model=list[OrderRead])
async def my_orders(request: Request, current: CurrentRead):
    require_staff_permission(current, "__business_owner__")
    return await service(request).list_my(
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.get("/inbox", response_model=list[OrderRead])
async def order_inbox(request: Request, current: CurrentRead):
    categories = staff_order_categories(current)
    return await service(request).list_inbox(
        account_id=current.account_id,
        account_type=current.account_type,
        allowed_categories=categories,
    )


@router.put("/{order_id}/seen", response_model=OrderRead)
async def mark_order_seen(
    order_id: OrderId, request: Request, current: CurrentWrite
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).mark_seen(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.put("/{order_id}/status", response_model=OrderRead)
async def change_order_status(
    order_id: OrderId,
    body: OrderStatusChange,
    request: Request,
    current: CurrentWrite,
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).change_status(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.post("/{order_id}/payment/submit", response_model=OrderRead)
async def submit_order_payment(
    order_id: OrderId, request: Request, current: CurrentWrite
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).submit_payment(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.post("/{order_id}/payment", response_model=OrderRead)
async def decide_order_payment(
    order_id: OrderId,
    body: OrderPaymentDecision,
    request: Request,
    current: CurrentWrite,
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).set_payment(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.post("/{order_id}/problem", response_model=OrderRead)
async def open_order_problem(
    order_id: OrderId,
    body: OrderProblemCreate,
    request: Request,
    current: CurrentWrite,
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).open_problem(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.put("/{order_id}/problem/solution", response_model=OrderRead)
async def choose_order_problem_solution(
    order_id: OrderId,
    body: OrderProblemSolution,
    request: Request,
    current: CurrentWrite,
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).choose_problem_solution(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.post("/{order_id}/handoff", response_model=OrderRead)
async def handoff_order(order_id: OrderId, request: Request, current: CurrentWrite):
    await require_staff_order_access(request, current, order_id)
    return await service(request).handoff(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
        actor_staff_id=current.staff_id,
    )


@router.post("/{order_id}/received", response_model=OrderRead)
async def receive_order(order_id: OrderId, request: Request, current: CurrentWrite):
    await require_staff_order_access(request, current, order_id)
    return await service(request).received(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.get("/{order_id}/chat", response_model=OrderChatRead)
async def order_chat(order_id: OrderId, request: Request, current: CurrentRead):
    await require_staff_order_access(request, current, order_id)
    return await service(request).chat(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.post("/{order_id}/chat", response_model=OrderMessageRead, status_code=201)
async def send_order_chat_message(
    order_id: OrderId,
    body: OrderMessageCreate,
    request: Request,
    current: CurrentWrite,
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).send_message(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.post("/{order_id}/chat/image", response_model=OrderMessageRead, status_code=201)
async def send_order_chat_image(
    order_id: OrderId,
    body: OrderMessageCreate,
    request: Request,
    current: CurrentWrite,
):
    await require_staff_order_access(request, current, order_id)
    image_body = body.model_copy(update={"media_type": "photo"})
    return await service(request).send_message(
        order_id=order_id,
        account_id=current.account_id,
        account_type=current.account_type,
        body=image_body,
    )


@router.put("/{order_id}/chat/{message_id}", response_model=OrderMessageRead)
async def edit_order_chat_message(
    order_id: OrderId,
    message_id: MessageId,
    body: OrderMessageEdit,
    request: Request,
    current: CurrentWrite,
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).edit_message(
        order_id=order_id,
        message_id=message_id,
        account_id=current.account_id,
        account_type=current.account_type,
        text=body.text,
    )


@router.delete("/{order_id}/chat/{message_id}", response_model=OrderMessageRead)
async def delete_order_chat_message(
    order_id: OrderId,
    message_id: MessageId,
    request: Request,
    current: CurrentWrite,
):
    await require_staff_order_access(request, current, order_id)
    return await service(request).delete_message(
        order_id=order_id,
        message_id=message_id,
        account_id=current.account_id,
        account_type=current.account_type,
    )
