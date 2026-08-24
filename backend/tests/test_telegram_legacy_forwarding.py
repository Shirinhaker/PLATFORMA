import fakeredis.aioredis
import httpx
import pytest

from app.auth.legacy_webhook import LegacyWebhookForwarder
from app.core.config import Settings
from app.core.errors import ApiError
from app.main import create_app

SECRET = "test-webhook-secret"
HEADERS = {"X-Telegram-Bot-Api-Secret-Token": SECRET}


class RecordingForwarder:
    def __init__(self, fails: bool = False):
        self.payloads = []
        self._fails = fails

    async def forward(self, payload):
        self.payloads.append(payload)
        if self._fails:
            raise AssertionError("uzatuvchi xatoni o'zi yutishi kerak edi")


class StubAuthService:
    """`activate_deep_link` faqat taniqli tokenni qabul qiladi."""

    def __init__(self, known_token: str | None = None, error: ApiError | None = None):
        self.known_token = known_token
        self.error = error
        self.activations = []

    async def activate_deep_link(self, token, telegram_user_id, now):
        if self.error is not None:
            raise self.error
        if token != self.known_token:
            raise ApiError(
                400,
                "invalid_start_token",
                "Telegram tasdiqlash havolasi noto‘g‘ri yoki muddati tugagan.",
            )
        self.activations.append((token, telegram_user_id, now))


@pytest.fixture
async def build_client():
    created = []

    async def _build(auth_service, forwarder):
        app = create_app(Settings(environment="test", telegram_webhook_secret=SECRET))
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        app.state.redis = redis
        app.state.auth_service = auth_service
        app.state.legacy_webhook_forwarder = forwarder
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://api.test",
        )
        created.append((client, redis))
        return client

    yield _build
    for client, redis in created:
        await client.aclose()
        await redis.aclose()


async def test_unknown_token_is_forwarded_to_legacy(build_client):
    """Eski tizimda ochilgan havola — biz tanimaymiz, uzatamiz."""
    forwarder = RecordingForwarder()
    client = await build_client(StubAuthService(known_token="bizniki"), forwarder)
    payload = {
        "update_id": 5,
        "message": {
            "chat": {"id": 42, "type": "private"},
            "text": "/start eski-tizim-tokeni",
        },
    }

    response = await client.post(
        "/api/v1/auth/telegram/webhook", headers=HEADERS, json=payload
    )

    assert response.status_code == 200
    assert forwarder.payloads == [payload]


async def test_known_token_is_not_forwarded(build_client):
    """Bizning tokenimiz — eski tizim ham javob bermasligi kerak."""
    forwarder = RecordingForwarder()
    service = StubAuthService(known_token="bizniki")
    client = await build_client(service, forwarder)

    response = await client.post(
        "/api/v1/auth/telegram/webhook",
        headers=HEADERS,
        json={
            "message": {
                "chat": {"id": 42, "type": "private"},
                "text": "/start bizniki",
            }
        },
    )

    assert response.status_code == 200
    assert forwarder.payloads == []
    assert service.activations[0][0] == "bizniki"


async def test_non_start_message_is_forwarded(build_client):
    """`/start` bo'lmagan xabar bizga tegishli emas — eski tizim ishlatadi."""
    forwarder = RecordingForwarder()
    client = await build_client(StubAuthService(), forwarder)
    payload = {"message": {"chat": {"id": 7, "type": "private"}, "text": "salom"}}

    response = await client.post(
        "/api/v1/auth/telegram/webhook", headers=HEADERS, json=payload
    )

    assert response.status_code == 200
    assert forwarder.payloads == [payload]


async def test_bare_start_is_forwarded(build_client):
    """Tokensiz `/start` — eski tizim salomlashish xabarini yuboradi."""
    forwarder = RecordingForwarder()
    client = await build_client(StubAuthService(), forwarder)
    payload = {"message": {"chat": {"id": 7, "type": "private"}, "text": "/start"}}

    response = await client.post(
        "/api/v1/auth/telegram/webhook", headers=HEADERS, json=payload
    )

    assert response.status_code == 200
    assert forwarder.payloads == [payload]


async def test_our_other_errors_are_not_forwarded(build_client):
    """Token bizniki, lekin allaqachon ishlatilgan — eski tizimga yubormaymiz."""
    forwarder = RecordingForwarder()
    service = StubAuthService(
        error=ApiError(409, "challenge_already_activated", "Allaqachon.")
    )
    client = await build_client(service, forwarder)

    response = await client.post(
        "/api/v1/auth/telegram/webhook",
        headers=HEADERS,
        json={
            "message": {
                "chat": {"id": 42, "type": "private"},
                "text": "/start bizniki",
            }
        },
    )

    assert response.status_code == 409
    assert forwarder.payloads == []


async def test_webhook_works_without_forwarder_configured(build_client):
    """Uzatish sozlanmagan bo'lsa xatolik chiqmaydi — hozirgi xulq saqlanadi."""
    client = await build_client(StubAuthService(known_token="bizniki"), None)

    response = await client.post(
        "/api/v1/auth/telegram/webhook",
        headers=HEADERS,
        json={"message": {"chat": {"id": 1, "type": "private"}, "text": "salom"}},
    )

    assert response.status_code == 200


async def test_forwarder_sends_secret_and_payload():
    """Eski tizim o'z sirini kutadi — aynan u yuborilishi kerak."""
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["secret"] = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        seen["body"] = request.read().decode("utf-8")
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        forwarder = LegacyWebhookForwarder(
            "https://eski.example/webhook", "eski-sir", http
        )
        await forwarder.forward({"update_id": 9})

    assert seen["secret"] == "eski-sir"
    assert seen["url"] == "https://eski.example/webhook"
    assert '"update_id"' in seen["body"]


async def test_forwarder_swallows_network_error():
    """Eski tizim o'chgan bo'lsa ham Telegramga xato qaytarmaymiz."""

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ulanmadi")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        forwarder = LegacyWebhookForwarder(
            "https://eski.example/webhook", "eski-sir", http
        )
        await forwarder.forward({"update_id": 9})


async def test_forwarder_swallows_rejection():
    """Eski tizim 403 qaytarsa ham webhook yiqilmaydi."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "forbidden"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        forwarder = LegacyWebhookForwarder(
            "https://eski.example/webhook", "eski-sir", http
        )
        await forwarder.forward({"update_id": 9})
