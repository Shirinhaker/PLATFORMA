from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.legacy_migration import cabinet_parity_v8, profile_media_v8
from app.media.storage import StoredObject
from app.profiles.model import UserProfile


def test_v1656_active_order_statuses_are_exact():
    assert cabinet_parity_v8.v1656_order_is_active({"status": "new"}) is True
    assert cabinet_parity_v8.v1656_order_is_active(
        {"status": "pickup_waiting_customer"}
    ) is True
    assert cabinet_parity_v8.v1656_order_is_active(
        {"status": "new", "problem_open": 1}
    ) is False
    assert cabinet_parity_v8.v1656_order_is_active({"status": "done"}) is False
    assert cabinet_parity_v8.v1656_order_is_active({"status": "pending"}) is False
    assert cabinet_parity_v8.v1656_order_is_active({"status": ""}) is False


@pytest.mark.asyncio
async def test_user_dashboard_filters_business_actor_notifications(monkeypatch):
    source = sqlite3.connect(":memory:")
    source.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
    source.execute("INSERT INTO users(id) VALUES(7)")

    profile = SimpleNamespace(
        cabinet_payload={
            "orders": [
                {"status": "done"},
                {"status": "pending"},
                {"status": "new", "problem_open": 1},
            ],
            "saved": [],
            "notifications": [
                {
                    "id": 1,
                    "actor_kind": "business",
                    "actor_id": 3,
                    "is_read": 0,
                    "resolved_at": 0,
                },
                {
                    "id": 2,
                    "actor_kind": "user",
                    "actor_id": 7,
                    "is_read": 1,
                    "resolved_at": 0,
                },
            ],
        },
        dashboard_snapshot={"active_orders": 99, "unread": 99},
        following_count=2,
        followers_count=1,
    )
    mapping = SimpleNamespace(target_id=70)

    monkeypatch.setattr(
        cabinet_parity_v8,
        "_find_mapping",
        AsyncMock(return_value=mapping),
    )

    class Session:
        async def get(self, model, target_id):
            assert model is UserProfile
            assert target_id == 70
            return profile

    await cabinet_parity_v8.repair_user_cabinet_parity(Session(), source)

    assert profile.dashboard_snapshot == {
        "active_orders": 0,
        "unread": 0,
        "following": 2,
        "saved": 0,
        "followers": 1,
    }
    assert [row["id"] for row in profile.cabinet_payload["notifications"]] == [2]
    source.close()


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str, str]] = {}

    def put_migration_object(
        self,
        *,
        stream,
        run_id,
        entity_type,
        legacy_id,
        slot,
        sha256,
        content_type,
        size_bytes,
        suffix,
    ):
        raw = stream.read()
        assert len(raw) == size_bytes
        key = (
            f"migration/{run_id}/{entity_type}/{legacy_id}/{slot}/"
            f"{sha256}{suffix}"
        )
        self.objects[key] = (raw, sha256, content_type)
        return StoredObject(
            object_key=key,
            size_bytes=size_bytes,
            sha256=sha256,
            content_type=content_type,
        )

    def verify_object(
        self,
        object_key,
        *,
        expected_size,
        expected_sha256,
        expected_content_type,
    ):
        stored = self.objects.get(object_key)
        return bool(
            stored
            and len(stored[0]) == expected_size
            and stored[1] == expected_sha256
            and stored[2] == expected_content_type
        )


@pytest.mark.asyncio
async def test_v1656_profile_image_blob_is_copied_to_r2(monkeypatch):
    source = sqlite3.connect(":memory:")
    source.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
    source.execute(
        """CREATE TABLE profile_images(
            owner_kind TEXT,owner_id INTEGER,mime_type TEXT,
            content BLOB,updated_at INTEGER
        )"""
    )
    source.execute("INSERT INTO users(id) VALUES(7)")
    raw = b"\x89PNG\r\n\x1a\n" + b"koprik-avatar"
    source.execute(
        "INSERT INTO profile_images VALUES('user',7,'image/png',?,1)",
        (raw,),
    )
    source.commit()

    mapping = SimpleNamespace(target_id=70)
    profile = SimpleNamespace(avatar_object_key="")
    monkeypatch.setattr(
        profile_media_v8,
        "_find_mapping",
        AsyncMock(return_value=mapping),
    )

    class Session:
        async def get(self, model, target_id):
            assert model is UserProfile
            assert target_id == 70
            return profile

        async def flush(self):
            return None

    run = SimpleNamespace(id=11)
    storage = FakeStorage()
    result = await profile_media_v8.migrate_profile_images(
        Session(),
        source,
        storage,
        run,
    )

    assert result.created == 1
    assert result.reused == 0
    assert profile.avatar_object_key.startswith("migration/11/user_profile/7/avatar/")
    assert storage.verify_object(
        profile.avatar_object_key,
        expected_size=len(raw),
        expected_sha256=profile.avatar_object_key.rsplit("/", 1)[-1].removesuffix(".png"),
        expected_content_type="image/png",
    )
    source.close()


@pytest.mark.asyncio
async def test_orphan_demo_profile_blob_is_not_migrated(monkeypatch):
    source = sqlite3.connect(":memory:")
    source.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
    source.execute(
        """CREATE TABLE profile_images(
            owner_kind TEXT,owner_id INTEGER,mime_type TEXT,
            content BLOB,updated_at INTEGER
        )"""
    )
    source.execute(
        "INSERT INTO profile_images VALUES('user',99,'image/png',?,1)",
        (b"\x89PNG\r\n\x1a\nold-demo",),
    )
    source.commit()

    finder = AsyncMock()
    monkeypatch.setattr(profile_media_v8, "_find_mapping", finder)

    class Session:
        async def flush(self):
            return None

    result = await profile_media_v8.migrate_profile_images(
        Session(),
        source,
        FakeStorage(),
        SimpleNamespace(id=11),
    )
    assert result.created == 0
    assert result.reused == 0
    finder.assert_not_awaited()
    source.close()
