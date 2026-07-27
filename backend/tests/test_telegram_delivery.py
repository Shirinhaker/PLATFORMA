from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import httpx
import pytest

from app.auth.model import AuthChallenge
from app.auth.security import derive_otp, encrypt_outbox_secret
from app.auth.telegram import TelegramClient
from app.core.config import Settings
from app.main import create_app
from app.outbox.model import OutboxEvent
from app.outbox.repository import mark_failed, mark_processed
from app.outbox.worker import build_handlers, cleanup_expired_auth


class RecordingAuthService:
    def __init__(self):
        self.activations = []

    async def activate_deep_link(self, token, telegram_user_id, now):
        self.activations.append((token, telegram_user_id, now))


@pytest.fixture
async def webhook_client():
    app = create_app(
        Settings(
            environment="test",
            telegram_webhook_secret="test-webhook-secret",
        )
    )
    service = RecordingAuthService()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.redis = redis
    app.state.auth_service = service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://api.test",
    ) as client:
        client.auth_service = service
        yield client
    await redis.aclose()


async def test_webhook_rejects_wrong_secret(webhook_client):
    response = await webhook_client.post(
        "/api/v1/auth/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"message": {"chat": {"id": 42}, "text": "/start abc"}},
    )
    assert response.status_code == 403


async def test_start_webhook_activates_private_chat_challenge(webhook_client):
    response = await webhook_client.post(
        "/api/v1/auth/telegram/webhook",
        headers={
            "X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret",
        },
        json={
            "update_id": 1001,
            "message": {
                "chat": {"id": 42, "type": "private"},
                "text": "/start raw-start-token",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    token, telegram_user_id, now = webhook_client.auth_service.activations[0]
    assert token == "raw-start-token"
    assert telegram_user_id == 42
    assert now.tzinfo is UTC


async def test_telegram_client_raises_only_generic_delivery_error():
    async def reject(request):
        return httpx.Response(400, text="secret Telegram response")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(reject)
    ) as http:
        client = TelegramClient("bot-secret", http)
        with pytest.raises(RuntimeError) as captured:
            await client.send_message(42, "123456")

    error = str(captured.value)
    assert "bot-secret" not in error
    assert "123456" not in error
    assert "secret Telegram response" not in error


async def test_telegram_client_sanitizes_transport_error():
    async def disconnect(request):
        raise httpx.ConnectError(
            f"failed to connect to {request.url}",
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(disconnect)
    ) as http:
        client = TelegramClient("bot-secret", http)
        with pytest.raises(RuntimeError) as captured:
            await client.send_message(42, "123456")

    error = str(captured.value)
    assert "bot-secret" not in error
    assert "123456" not in error


async def test_worker_sends_derived_code_without_plaintext_outbox_payload():
    challenge = AuthChallenge(
        id=41,
        code_version=1,
        telegram_user_id=42,
        code_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    class FakeSession:
        async def get(self, model, object_id, **kwargs):
            assert model is AuthChallenge
            assert object_id == 41
            assert kwargs["with_for_update"] is True
            return challenge

    class FakeDatabase:
        @asynccontextmanager
        async def session(self):
            yield FakeSession()

    class FakeTelegram:
        def __init__(self):
            self.messages = []

        async def send_message(self, chat_id, text):
            self.messages.append((chat_id, text))

    settings = Settings(environment="test", otp_secret="test-otp-secret")
    telegram = FakeTelegram()
    handlers = build_handlers(settings, FakeDatabase(), telegram)
    payload = {
        "challenge_id": 41,
        "code_version": 1,
        "chat_id": 42,
    }

    await handlers["telegram.auth_code.send"](payload)

    expected = derive_otp(41, 1, "test-otp-secret")
    assert telegram.messages == [
        (42, f"Koprik tasdiqlash kodi: {expected}")
    ]
    assert "code" not in payload


async def test_worker_does_not_send_an_expired_code():
    challenge = AuthChallenge(
        id=41,
        code_version=1,
        telegram_user_id=42,
        code_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    class FakeSession:
        async def get(self, model, object_id, **kwargs):
            return challenge

    class FakeDatabase:
        @asynccontextmanager
        async def session(self):
            yield FakeSession()

    class FakeTelegram:
        def __init__(self):
            self.messages = []

        async def send_message(self, chat_id, text):
            self.messages.append((chat_id, text))

    telegram = FakeTelegram()
    handlers = build_handlers(
        Settings(environment="test", otp_secret="test-otp-secret"),
        FakeDatabase(),
        telegram,
    )
    await handlers["telegram.auth_code.send"](
        {
            "challenge_id": 41,
            "code_version": 1,
            "chat_id": 42,
        }
    )

    assert telegram.messages == []


async def test_worker_decrypts_credentials_only_for_delivery():
    key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    class FakeDatabase:
        pass

    class FakeTelegram:
        def __init__(self):
            self.messages = []

        async def send_message(self, chat_id, text):
            self.messages.append((chat_id, text))

    telegram = FakeTelegram()
    handlers = build_handlers(
        Settings(environment="test", outbox_encryption_key=key),
        FakeDatabase(),
        telegram,
    )
    payload = {
        "account_id": 7,
        "chat_id": 42,
        "encrypted_credentials": encrypt_outbox_secret(
            {"login": "u_test", "password": "one-time-secret"},
            key,
        ),
    }

    await handlers["telegram.credentials.send"](payload)

    assert telegram.messages == [
        (
            42,
            "Koprik login: u_test\nKoprik parol: one-time-secret",
        )
    ]


async def test_processed_credentials_are_scrubbed_from_outbox_payload():
    event = OutboxEvent(
        id=1,
        topic="telegram.credentials.send",
        payload={"encrypted_credentials": "ciphertext"},
        status="processing",
        attempts=1,
        available_at=datetime.now(UTC),
        last_error="",
        created_at=datetime.now(UTC),
    )

    class FakeSession:
        async def get(self, model, event_id, **kwargs):
            assert model is OutboxEvent
            assert event_id == 1
            return event

    await mark_processed(
        FakeSession(),
        1,
        sanitized_payload={"account_id": 7, "delivery": "telegram"},
    )

    assert event.status == "processed"
    assert event.payload == {"account_id": 7, "delivery": "telegram"}


async def test_telegram_failure_retries_with_backoff():
    now = datetime.now(UTC)
    event = OutboxEvent(
        id=1,
        topic="telegram.auth_code.send",
        payload={"challenge_id": 41, "code_version": 1, "chat_id": 42},
        status="processing",
        attempts=1,
        available_at=now,
        last_error="",
        created_at=now,
    )

    class FakeSession:
        async def get(self, model, event_id, **kwargs):
            assert model is OutboxEvent
            assert event_id == 1
            return event

    before = datetime.now(UTC)
    await mark_failed(FakeSession(), 1, "Telegram xabarni qabul qilmadi.")
    after = datetime.now(UTC)

    assert event.status == "retry"
    assert event.attempts == 1
    assert before.timestamp() + 30 <= event.available_at.timestamp()
    assert event.available_at.timestamp() <= after.timestamp() + 30
    assert "token" not in event.last_error.lower()
    assert "code" not in event.last_error.lower()


async def test_cleanup_deletes_only_expired_auth_records():
    class FakeSession:
        def __init__(self):
            self.statements = []
            self.commits = 0

        async def execute(self, statement):
            self.statements.append(statement)

        async def commit(self):
            self.commits += 1

    session = FakeSession()

    class FakeDatabase:
        @asynccontextmanager
        async def session(self):
            yield session

    await cleanup_expired_auth(FakeDatabase(), datetime.now(UTC))

    assert {
        statement.table.name for statement in session.statements
    } == {
        "pending_registrations",
        "auth_challenges",
        "auth_sessions",
    }
    assert session.commits == 1
