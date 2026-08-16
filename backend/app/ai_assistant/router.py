from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.ai_assistant.schemas import (
    AIChatAnswerRead,
    AIChatHistoryRead,
    AIChatRequest,
    AIDocumentDraftRead,
    AIDocumentDraftRequest,
    AIStatusRead,
)
from app.ai_assistant.service import AIAssistantService
from app.auth.dependencies import (
    CurrentAccount,
    require_business_owner,
    require_csrf,
    require_current_account,
)
from app.cache.rate_limit import consume_rate_limit
from app.core.errors import ApiError

router = APIRouter(prefix="/api/v1/ai-assistant", tags=["ai-assistant"])
ReadAccount = Annotated[CurrentAccount, Depends(require_current_account)]
WriteAccount = Annotated[CurrentAccount, Depends(require_csrf)]


def service(request: Request) -> AIAssistantService:
    return request.app.state.ai_assistant_service


Service = Annotated[AIAssistantService, Depends(service)]


@router.get("/history", response_model=AIChatHistoryRead)
async def history(
    current: ReadAccount, ai: Service, limit: Annotated[int, Query(ge=1, le=100)] = 30
):
    require_business_owner(current)
    return await ai.history(current.account_id, limit)


@router.post("/chat", response_model=AIChatAnswerRead)
async def chat(
    body: AIChatRequest, current: WriteAccount, ai: Service, request: Request
):
    require_business_owner(current)
    redis_wrapper = request.app.state.redis
    redis = getattr(redis_wrapper, "client", None)
    if redis is None or callable(redis):
        redis = redis_wrapper
    result = await consume_rate_limit(redis, f"ai-chat:{current.account_id}", 20, 60)
    if not result.allowed:
        raise ApiError(
            429,
            "ai_rate_limited",
            "Juda ko‘p savol yuborildi. Biroz kuting.",
            headers={"Retry-After": str(result.retry_after_seconds)},
        )
    return await ai.chat(current.account_id, body.message)


@router.get("/status", response_model=AIStatusRead)
async def status(current: ReadAccount, ai: Service):
    require_business_owner(current)
    return AIStatusRead(
        build="v1656", business_id=current.account_id, openai_enabled=ai.openai_enabled
    )


@router.post("/documents/draft", response_model=AIDocumentDraftRead)
async def document_draft(
    body: AIDocumentDraftRequest, current: WriteAccount, ai: Service
):
    require_business_owner(current)
    return await ai.document_draft(current.account_id, body)
