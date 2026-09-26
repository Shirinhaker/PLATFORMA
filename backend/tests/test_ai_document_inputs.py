import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pydantic import ValidationError

from app.ai_assistant.attachments import attachment_content
from app.ai_assistant.schemas import AIAttachment, AIDocumentQuestion
from app.ai_assistant.service import AIAssistantService
from app.core.errors import ApiError


def file(name, data):
    return AIAttachment(name=name, data=base64.b64encode(data).decode())


@pytest.mark.parametrize(
    "name,data,kind",
    [
        ("doc.pdf", b"%PDF-1.7 test", "input_file"),
        ("photo.jpg", b"\xff\xd8\xff test", "input_image"),
        ("photo.png", b"\x89PNG\r\n\x1a\n test", "input_image"),
        ("doc.txt", b"To'lov muddati 10 kun", "input_text"),
    ],
)
def test_supported_inputs(name, data, kind):
    result = attachment_content(file(name, data))
    assert result["type"] == kind


@pytest.mark.parametrize(
    "name,data",
    [
        ("fake.pdf", b"not pdf"),
        ("file.exe", b"MZ"),
        ("empty.txt", b""),
        ("big.txt", b"a" * 60_001),
        ("bad.docx", b"PKbroken"),
        ("binary.txt", b"\xff"),
    ],
)
def test_invalid_inputs_rejected(name, data):
    with pytest.raises((ApiError, ValidationError)):
        attachment_content(file(name, data))


def test_docx_reads_paragraphs_and_rejects_expansion_and_entities():
    def docx(xml):
        buf = BytesIO()
        with ZipFile(buf, "w", ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", xml)
        return file("document.docx", buf.getvalue())

    xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>10 kun</w:t></w:r></w:p></w:document>'
    assert "10 kun" in attachment_content(docx(xml))["text"]
    with pytest.raises(ApiError):
        attachment_content(docx("x" * (2 * 1024 * 1024 + 1)))
    with pytest.raises(ApiError):
        attachment_content(docx('<!DOCTYPE x [<!ENTITY a "hello">]><x>&a;</x>'))


def test_invalid_base64_and_decoded_size_rejected():
    with pytest.raises(ApiError):
        attachment_content(AIAttachment(name="x.pdf", data="%%%"))
    with pytest.raises(ApiError):
        attachment_content(file("x.pdf", b"a" * (2 * 1024 * 1024 + 1)))


@pytest.mark.asyncio
async def test_document_question_has_file_context_but_no_business_data_or_storage():
    provider = SimpleNamespace(enabled=True, answer=AsyncMock(return_value="10 kun"))
    service = AIAssistantService(None, provider)
    body = AIDocumentQuestion(
        message="Muddati?",
        attachment=file("x.txt", b"10 kun"),
        history=[{"role": "user", "text": "Izohla"}],
    )
    result = await service.document_question(body)
    assert result.answer == "10 kun"
    args = provider.answer.call_args.args
    assert "10 kun" in args[1][0]["text"]
    assert "Izohla" in args[1][1]["text"]
    assert "business" not in args[1][1]["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_no_fabricated_fallback_for_document(enabled):
    provider = SimpleNamespace(enabled=enabled, answer=AsyncMock(return_value=""))
    service = AIAssistantService(None, provider)
    with pytest.raises(ApiError):
        await service.document_question(
            AIDocumentQuestion(message="Izohla", attachment=file("x.txt", b"abc"))
        )
    if not enabled:
        provider.answer.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "account_type,actor,status",
    [("business", "owner", 200), ("user", "owner", 403), ("business", "staff", 403)],
)
async def test_route_requires_business_owner_and_csrf(account_type, actor, status):
    import fakeredis.aioredis
    import httpx
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    from app.accounts.model import AccountType
    from app.ai_assistant.router import router
    from app.auth.dependencies import CurrentAccount, require_current_account
    from app.auth.security import derive_csrf

    app = FastAPI()
    app.include_router(router)
    app.state.settings = SimpleNamespace(csrf_secret="test")
    current = CurrentAccount(17, AccountType(account_type), "session", actor_type=actor)
    app.dependency_overrides[require_current_account] = lambda: current
    app.state.ai_assistant_service = SimpleNamespace(
        document_question=AsyncMock(
            return_value={"answer": "javob", "source": "openai"}
        )
    )
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.redis = redis

    @app.exception_handler(ApiError)
    async def handle_error(_request, error):
        return JSONResponse({"code": error.code}, status_code=error.status_code)

    body = {"message": "Izohla", "attachment": file("x.txt", b"text").model_dump()}
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (
                await client.post("/api/v1/ai-assistant/documents/question", json=body)
            ).status_code == 403
            result = await client.post(
                "/api/v1/ai-assistant/documents/question",
                json=body,
                headers={"X-CSRF-Token": derive_csrf("session", "test")},
            )
            assert result.status_code == status
            if status == 403:
                app.state.ai_assistant_service.document_question.assert_not_called()
            else:
                for _ in range(9):
                    assert (
                        await client.post(
                            "/api/v1/ai-assistant/documents/question",
                            json=body,
                            headers={"X-CSRF-Token": derive_csrf("session", "test")},
                        )
                    ).status_code == 200
                assert (
                    await client.post(
                        "/api/v1/ai-assistant/documents/question",
                        json=body,
                        headers={"X-CSRF-Token": derive_csrf("session", "test")},
                    )
                ).status_code == 429
    finally:
        await redis.aclose()
