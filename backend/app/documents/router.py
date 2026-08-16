from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_current_account
from app.core.errors import ApiError
from app.documents.schemas import (
    CounterpartyListRead,
    CounterpartyWrite,
    CreatedRead,
    DocumentListRead,
    DocumentRead,
    DocumentRespond,
    DocumentRespondedRead,
    DocumentSend,
    DocumentSentRead,
    DocumentWrite,
    MutationRead,
)
from app.documents.service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def document_service(request: Request) -> DocumentService:
    return request.app.state.document_service


DocumentServiceDep = Annotated[DocumentService, Depends(document_service)]


def _business_id(current: CurrentAccount) -> int:
    if current.account_type is not AccountType.BUSINESS:
        raise ApiError(
            403,
            "business_account_required",
            "Bu bo‘lim faqat biznes akkaunt uchun.",
        )
    return current.account_id


def _permissions(current: CurrentAccount) -> tuple[str, ...] | None:
    return current.permissions if current.actor_type == "staff" else None


def _is_owner(current: CurrentAccount) -> bool:
    return current.actor_type != "staff" and current.staff_id is None


@router.get("/counterparties", response_model=CounterpartyListRead)
async def list_counterparties(
    current: CurrentRead,
    service: DocumentServiceDep,
) -> CounterpartyListRead:
    return await service.list_counterparties(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
    )


@router.post(
    "/counterparties",
    response_model=CreatedRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_counterparty(
    body: CounterpartyWrite,
    current: CurrentWrite,
    service: DocumentServiceDep,
) -> CreatedRead:
    return await service.create_counterparty(
        business_account_id=_business_id(current),
        is_owner=_is_owner(current),
        body=body,
    )


@router.put("/counterparties/{counterparty_id}", response_model=MutationRead)
async def update_counterparty(
    counterparty_id: int,
    body: CounterpartyWrite,
    current: CurrentWrite,
    service: DocumentServiceDep,
) -> MutationRead:
    return await service.update_counterparty(
        business_account_id=_business_id(current),
        counterparty_id=counterparty_id,
        is_owner=_is_owner(current),
        body=body,
    )


@router.delete("/counterparties/{counterparty_id}", status_code=204)
async def delete_counterparty(
    counterparty_id: int,
    current: CurrentWrite,
    service: DocumentServiceDep,
) -> Response:
    await service.delete_counterparty(
        business_account_id=_business_id(current),
        counterparty_id=counterparty_id,
        is_owner=_is_owner(current),
    )
    return Response(status_code=204)


@router.get("", response_model=DocumentListRead)
async def list_documents(
    current: CurrentRead,
    service: DocumentServiceDep,
    direction: Annotated[str | None, Query()] = None,
) -> DocumentListRead:
    return await service.list_documents(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        direction=direction,
    )


@router.post("", response_model=CreatedRead, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentWrite,
    current: CurrentWrite,
    service: DocumentServiceDep,
) -> CreatedRead:
    return await service.create_document(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        body=body,
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: int,
    current: CurrentRead,
    service: DocumentServiceDep,
) -> DocumentRead:
    return await service.get_document(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        document_id=document_id,
    )


@router.put("/{document_id}", response_model=MutationRead)
async def update_document(
    document_id: int,
    body: DocumentWrite,
    current: CurrentWrite,
    service: DocumentServiceDep,
) -> MutationRead:
    return await service.update_document(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        document_id=document_id,
        body=body,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    current: CurrentWrite,
    service: DocumentServiceDep,
) -> Response:
    await service.delete_document(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        document_id=document_id,
    )
    return Response(status_code=204)


@router.post("/{document_id}/send", response_model=DocumentSentRead)
async def send_document(
    document_id: int,
    body: DocumentSend,
    current: CurrentWrite,
    service: DocumentServiceDep,
) -> DocumentSentRead:
    return await service.send_document(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        document_id=document_id,
        body=body,
    )


@router.post("/{document_id}/respond", response_model=DocumentRespondedRead)
async def respond_document(
    document_id: int,
    body: DocumentRespond,
    current: CurrentWrite,
    service: DocumentServiceDep,
) -> DocumentRespondedRead:
    return await service.respond_document(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        document_id=document_id,
        body=body,
    )
