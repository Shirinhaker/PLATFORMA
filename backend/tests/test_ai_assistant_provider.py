import httpx
import pytest

from app.ai_assistant.provider import OpenAIResponsesProvider


@pytest.mark.asyncio
async def test_openai_provider_reuses_injected_http_client_and_parses_responses():
    requests = []

    async def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(
            200,
            headers={"x-request-id": "req_test"},
            json={"output_text": " Tayyor javob "},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIResponsesProvider(
        api_key="secret",
        model="gpt-4o-mini",
        client=client,
    )
    try:
        first = await provider.answer("system", "bir", max_output_tokens=100)
        second = await provider.answer("system", "ikki", max_output_tokens=100)
        await provider.close()
        assert client.is_closed is False
    finally:
        await client.aclose()

    assert first == second == "Tayyor javob"
    assert len(requests) == 2
    assert all(request.headers["authorization"] == "Bearer secret" for request in requests)


@pytest.mark.asyncio
async def test_openai_provider_keeps_v1656_robust_response_extraction():
    responses = iter((
        {"output": [{"content": [{"content": "Muqobil javob"}]}]},
        [],
    ))

    async def handler(_request: httpx.Request):
        return httpx.Response(200, json=next(responses))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIResponsesProvider(
        api_key="secret",
        model="gpt-4o-mini",
        client=client,
    )
    try:
        assert await provider.answer("system", "bir", max_output_tokens=100) == (
            "Muqobil javob"
        )
        assert await provider.answer("system", "ikki", max_output_tokens=100) == ""
    finally:
        await client.aclose()
