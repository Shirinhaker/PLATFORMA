import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.accounts.model import Account, AccountType
from app.core.config import Settings
from app.core.errors import ApiError
from app.main import create_app
from app.messages.schemas import MessageCreate, MessageEdit, MessageImageCreate
from app.messages.service import MessageService
from app.profiles.model import BusinessProfile, UserProfile

ROOT = Path(__file__).resolve().parents[1]


def module(name: str):
    return import_module(f"app.messages.{name}")


def test_message_models_define_one_conversation_per_account_pair():
    model = module("model")

    assert model.MessageConversation.__tablename__ == "message_conversations"
    assert model.MessageConversationMember.__tablename__ == "message_conversation_members"
    assert model.Message.__tablename__ == "messages"
    assert model.Message.__table__.c.reply_to_id.foreign_keys
    assert model.Message.__table__.c.sender_account_id.foreign_keys
    assert model.Message.__table__.c.receiver_account_id.foreign_keys

    conversation_indexes = {
        index.name for index in model.MessageConversation.__table__.indexes
    }
    message_indexes = {index.name for index in model.Message.__table__.indexes}
    assert "uq_message_conversations_pair" in conversation_indexes
    assert "ix_message_conversation_member" in message_indexes
    assert "ix_messages_receiver_unread" in message_indexes
    assert "uq_messages_legacy_source" in message_indexes


def test_message_pair_and_preview_rules_match_v1656():
    service = module("service")

    assert service.canonical_account_pair(9, 3) == (3, 9)
    assert service.canonical_account_pair(3, 9) == (3, 9)
    with pytest.raises(ValueError, match="same_account"):
        service.canonical_account_pair(7, 7)

    assert service.message_preview_text(
        text="", media_type="text", is_deleted=True
    ) == "Xabar o‘chirildi"
    assert service.message_preview_text(
        text="", media_type="photo", is_deleted=False
    ) == "📷 Rasm"
    assert service.message_preview_text(
        text=" Salom ", media_type="photo", is_deleted=False
    ) == "Salom"


def test_message_schemas_enforce_v1656_text_photo_and_reply_limits():
    schemas = module("schemas")

    sent = schemas.MessageCreate(
        target_kind="business",
        target_public_id="b_0123456789abcdef",
        text="  Salom  ",
        reply_to_id=4,
    )
    assert sent.text == "Salom"
    assert sent.target_kind is AccountType.BUSINESS

    image = schemas.MessageImageCreate(
        target_kind="user",
        target_public_id="u_0123456789abcdef",
        object_key="private/user/4/chat_image/photo.webp",
        file_name="photo.webp",
        text="  Izoh  ",
    )
    assert image.text == "Izoh"

    with pytest.raises(ValidationError):
        schemas.MessageCreate(
            target_kind="user",
            target_public_id="u_0123456789abcdef",
            text="",
        )
    with pytest.raises(ValidationError):
        schemas.MessageImageCreate(
            target_kind="user",
            target_public_id="u_0123456789abcdef",
            object_key="",
            file_name="photo.webp",
        )


def test_messages_router_exposes_general_chat_without_order_chat_changes():
    router = module("router").router
    routes = {
        (route.path, method)
        for route in router.routes
        for method in (route.methods or set())
    }

    assert ("/api/v1/messages/conversations", "GET") in routes
    assert ("/api/v1/messages/with/{target_kind}/{target_public_id}", "GET") in routes
    assert ("/api/v1/messages/send", "POST") in routes
    assert ("/api/v1/messages/image", "POST") in routes
    assert ("/api/v1/messages/{message_id}", "PUT") in routes
    assert ("/api/v1/messages/{message_id}", "DELETE") in routes
    assert ("/api/v1/messages/unread-count", "GET") in routes


def test_messages_migration_backfills_legacy_json_idempotently_and_reverses():
    migration = ROOT / "migrations" / "versions" / "0031_messages.py"
    source = migration.read_text(encoding="utf-8")
    upper = source.upper()

    assert 'revision = "0031_messages"' in source
    assert 'down_revision = "0030_stories"' in source
    for table in (
        "message_conversations", "message_conversation_members", "messages"
    ):
        assert f'"{table}"' in source
        assert f'op.drop_table("{table}")' in source
    assert "user_profiles" in source
    assert "business_profiles" in source
    assert "cabinet_payload" in source
    assert "legacy_id_map" in source
    assert "user_account" in source
    assert "business_account" in source
    assert "jsonb_array_elements" in source
    assert "legacy_source_id" in source
    assert "source_key" in source
    assert "media_object_key" in source
    assert "CASE" in upper
    assert "ON CONFLICT" in upper
    assert "DO NOTHING" in upper


def test_messages_are_registered_and_feature_can_be_closed_or_opened():
    main_source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    env_source = (ROOT / "migrations" / "env.py").read_text(encoding="utf-8")

    assert "message_service" in main_source
    assert "messages_router" in main_source
    assert "app.include_router(messages_router)" in main_source
    assert "from app.messages import model as messages_model" in env_source

    from fastapi.testclient import TestClient

    closed = create_app(Settings(environment="test", chat_enabled=False))
    opened = create_app(Settings(environment="test", chat_enabled=True))
    assert TestClient(closed).get("/api/v1/public/features").json()["chat"] is False
    assert TestClient(opened).get("/api/v1/public/features").json()["chat"] is True


def test_media_grant_has_dedicated_general_chat_image_purpose():
    router_source = (ROOT / "app" / "media" / "router.py").read_text(
        encoding="utf-8"
    )
    storage_source = (ROOT / "app" / "media" / "storage.py").read_text(
        encoding="utf-8"
    )

    assert '"chat_image"' in router_source
    assert '"chat_image"' in storage_source


@pytest.mark.asyncio
async def test_two_actors_text_image_reply_edit_delete_read_flow(db_session):
    now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    token = secrets.token_hex(8)
    user = Account(
        account_type=AccountType.USER,
        login=f"chat-user-{token}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    business = Account(
        account_type=AccountType.BUSINESS,
        login=f"chat-business-{token}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([user, business])
    await db_session.flush()
    user_public_id = f"u_{int(user.id):016x}"
    business_public_id = f"b_{int(business.id):016x}"
    db_session.add_all([
        UserProfile(
            account_id=user.id,
            public_id=user_public_id,
            name="Ali",
            phone="",
        ),
        BusinessProfile(
            account_id=business.id,
            public_id=business_public_id,
            name="Turon savdo",
            phone="",
        ),
    ])
    await db_session.flush()

    @asynccontextmanager
    async def sessions():
        yield db_session

    service = MessageService(
        sessions,
        lambda key: f"https://media.test/{key}",
        now_provider=lambda: now,
    )
    sent = await service.send_text(
        account_id=user.id,
        account_type=AccountType.USER,
        body=MessageCreate(
            target_kind=AccountType.BUSINESS,
            target_public_id=business_public_id,
            text="Assalomu alaykum",
        ),
    )
    assert sent.mine is True
    assert (await service.unread_count(account_id=business.id)).count == 1

    business_thread = await service.thread(
        account_id=business.id,
        target_kind=AccountType.USER,
        target_public_id=user_public_id,
    )
    assert business_thread.other.name == "Ali"
    assert business_thread.messages[0].mine is False
    assert (await service.unread_count(account_id=business.id)).count == 0

    image = await service.send_image(
        account_id=business.id,
        account_type=AccountType.BUSINESS,
        body=MessageImageCreate(
            target_kind=AccountType.USER,
            target_public_id=user_public_id,
            object_key=f"private/business/{business.id}/chat_image/photo.webp",
            file_name="photo.webp",
            text="Mana rasm",
            reply_to_id=sent.id,
        ),
    )
    assert image.reply and image.reply.text == "Assalomu alaykum"
    assert image.media_url.endswith("/chat_image/photo.webp")

    with pytest.raises(ApiError) as forbidden:
        await service.edit(
            message_id=image.id,
            account_id=user.id,
            body=MessageEdit(text="Begona tahrir"),
        )
    assert forbidden.value.status_code == 403

    edited = await service.edit(
        message_id=image.id,
        account_id=business.id,
        body=MessageEdit(text="Yangilangan izoh"),
    )
    assert edited.text == "Yangilangan izoh"
    assert edited.edited_at == now

    deleted = await service.delete(
        message_id=image.id,
        account_id=business.id,
    )
    assert deleted.is_deleted is True
    assert deleted.text == ""
    conversations = await service.conversations(account_id=user.id)
    assert conversations[0].last == "Xabar o‘chirildi"
