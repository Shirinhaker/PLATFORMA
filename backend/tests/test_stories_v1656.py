from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib
from pathlib import Path

import pytest

from app.accounts.model import AccountType
from app.core.config import Settings
from app.main import create_app


ROOT = Path(__file__).resolve().parents[1]


def _stories_module(name: str):
    return importlib.import_module(f"app.stories.{name}")


def test_story_limits_and_signature_validation_match_v1656():
    processor = _stories_module("processor")

    assert processor.STORY_TTL_SECONDS == 24 * 60 * 60
    assert processor.MAX_ACTIVE_STORIES == 10
    assert processor.MAX_IMAGE_BYTES == 10 * 1024 * 1024
    assert processor.MAX_VIDEO_BYTES == 100 * 1024 * 1024
    assert processor.MAX_VIDEO_SECONDS == 60.0
    assert processor.MAX_CAPTION_LENGTH == 200
    assert processor.sniff_media_type(b"\xff\xd8\xffrest") == "image/jpeg"
    assert (
        processor.sniff_media_type(b"\x89PNG\r\n\x1a\nrest")
        == "image/png"
    )
    assert (
        processor.sniff_media_type(b"RIFF\x01\x00\x00\x00WEBPrest")
        == "image/webp"
    )
    assert (
        processor.sniff_media_type(b"\x00\x00\x00\x18ftypisomrest")
        == "video/mp4"
    )
    assert (
        processor.sniff_media_type(b"\x1a\x45\xdf\xa3rest")
        == "video/webm"
    )


def test_story_upload_validation_rejects_spoofing_and_v1656_limits():
    processor = _stories_module("processor")

    image = processor.validate_story_upload(
        claimed_type="image/jpeg",
        actual_type="image/jpeg",
        size_bytes=1024,
        duration_seconds=0,
        caption="  Salom  ",
    )
    assert image.media_type == "image"
    assert image.caption == "Salom"

    with pytest.raises(processor.StoryValidationError, match="mos emas"):
        processor.validate_story_upload(
            claimed_type="image/jpeg",
            actual_type="video/mp4",
            size_bytes=1024,
            duration_seconds=5,
            caption="",
        )
    with pytest.raises(processor.StoryValidationError, match="100 MB"):
        processor.validate_story_upload(
            claimed_type="video/mp4",
            actual_type="video/mp4",
            size_bytes=100 * 1024 * 1024 + 1,
            duration_seconds=5,
            caption="",
        )
    with pytest.raises(processor.StoryValidationError, match="60 soniya"):
        processor.validate_story_upload(
            claimed_type="video/mp4",
            actual_type="video/mp4",
            size_bytes=1024,
            duration_seconds=60.01,
            caption="",
        )
    with pytest.raises(processor.StoryValidationError, match="200"):
        processor.validate_story_upload(
            claimed_type="image/png",
            actual_type="image/png",
            size_bytes=1024,
            duration_seconds=0,
            caption="x" * 201,
        )


def test_story_feed_rank_is_own_unseen_followed_nearest_newest():
    service = _stories_module("service")
    groups = [
        {"name": "newest", "is_own": False, "has_unseen": False,
         "is_followed": False, "distance_km": None, "latest_story_at": 50},
        {"name": "nearest", "is_own": False, "has_unseen": True,
         "is_followed": True, "distance_km": 1.0, "latest_story_at": 10},
        {"name": "followed", "is_own": False, "has_unseen": True,
         "is_followed": True, "distance_km": 5.0, "latest_story_at": 40},
        {"name": "unseen", "is_own": False, "has_unseen": True,
         "is_followed": False, "distance_km": 0.1, "latest_story_at": 30},
        {"name": "own", "is_own": True, "has_unseen": False,
         "is_followed": False, "distance_km": None, "latest_story_at": 1},
    ]

    ranked = service.rank_story_groups(groups)

    assert [item["name"] for item in ranked] == [
        "own", "nearest", "followed", "unseen", "newest",
    ]


def test_story_models_define_views_reports_and_active_indexes():
    model = _stories_module("model")

    assert model.Story.__tablename__ == "stories"
    assert model.StoryView.__tablename__ == "story_views"
    assert model.StoryReport.__tablename__ == "story_reports"
    assert model.Story.__table__.c.owner_account_id.foreign_keys
    assert model.StoryView.__table__.c.viewer_account_id.foreign_keys
    assert model.StoryReport.__table__.c.reporter_account_id.foreign_keys

    story_indexes = {index.name for index in model.Story.__table__.indexes}
    view_indexes = {index.name for index in model.StoryView.__table__.indexes}
    report_indexes = {index.name for index in model.StoryReport.__table__.indexes}
    assert "ix_stories_active_owner" in story_indexes
    assert "ix_stories_feed_active" in story_indexes
    assert "ix_stories_creator_account" in story_indexes
    assert "ix_stories_creator_staff" in story_indexes
    assert "ix_stories_migration_run" in story_indexes
    assert "ix_story_views_story_viewed" in view_indexes
    assert "ix_story_views_viewer" in view_indexes
    assert "ix_story_reports_status_created" in report_indexes
    assert "ix_story_reports_reporter" in report_indexes


def test_story_migration_is_reversible_and_quarantines_unresolved_data():
    migration = ROOT / "migrations" / "versions" / "0030_stories.py"
    stage = ROOT / "app" / "legacy_migration" / "story_stage.py"

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")
    assert 'revision = "0030_stories"' in source
    assert 'down_revision = "0029_listing_publish_price"' in source
    for table in ("stories", "story_views", "story_reports"):
        assert f'"{table}"' in source
        assert f'op.drop_table("{table}")' in source
    assert "ix_stories_feed_active" in source
    assert "ix_stories_active_owner" in source

    assert stage.exists()
    stage_source = stage.read_text(encoding="utf-8")
    assert "story.owner_unresolved" in stage_source
    assert "story.media_missing" in stage_source
    assert "mapping_status=\"quarantined\"" in stage_source
    assert "source_row_hash" in stage_source
    verify_source = (ROOT / "app" / "legacy_migration" / "verify.py").read_text(
        encoding="utf-8"
    )
    assert '"story_view_count"' in verify_source
    assert '"story_report_count"' in verify_source


def test_stories_router_service_and_metadata_are_registered():
    main_source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    env_source = (ROOT / "migrations" / "env.py").read_text(encoding="utf-8")

    assert "story_service" in main_source
    assert "stories_router" in main_source
    assert "app.include_router(stories_router)" in main_source
    assert "from app.stories import model as stories_model" in env_source


def test_stories_feature_flag_is_configurable_and_defaults_closed():
    closed = create_app(Settings(environment="test", stories_enabled=False))
    opened = create_app(Settings(environment="test", stories_enabled=True))

    from fastapi.testclient import TestClient

    assert TestClient(closed).get("/api/v1/public/features").json()["stories"] is False
    assert TestClient(opened).get("/api/v1/public/features").json()["stories"] is True


def test_story_schemas_keep_automatic_archive_and_unique_view_contract():
    schemas = _stories_module("schemas")
    created = datetime(2026, 8, 8, 8, 0, tzinfo=UTC)
    story = schemas.StoryRead(
        id=7,
        owner_type=AccountType.USER,
        owner_public_id="u_0123456789abcdef",
        media_type="image",
        media_url="https://media.test/story.jpg",
        thumbnail_url="https://media.test/story.jpg",
        caption="Salom",
        duration_seconds=0,
        created_at=created,
        expires_at=created + timedelta(hours=24),
        viewed=False,
    )
    assert story.state == "active"
