from pathlib import Path
from sqlalchemy import JSON, CheckConstraint, Index, UniqueConstraint

from app.advertisements.model import Advertisement
from app.catalog.model import CatalogGroup, CatalogItem
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MigrationIssue,
    MigrationRun,
)
from app.listings.model import Listing, ListingMedia, ListingSave


def unique_columns(model) -> set[tuple[str, ...]]:
    return {
        tuple(constraint.columns.keys())
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def check_names(model) -> set[str | None]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }


def index_names(model) -> set[str | None]:
    return {
        index.name
        for index in model.__table__.indexes
        if isinstance(index, Index)
    }


def test_catalog_item_keeps_text_price_and_owner_state():
    columns = CatalogItem.__table__.c

    assert columns.price_text.type.length == 120
    assert columns.business_account_id.nullable is True
    assert columns.owner_state.nullable is False
    assert columns.review_state.nullable is False
    assert columns.migration_run_id.nullable is True
    assert columns.source_record_key.nullable is True


def test_catalog_models_restrict_kind_and_keep_migration_ownership():
    assert "ck_catalog_groups_kind" in check_names(CatalogGroup)
    assert "ck_catalog_items_kind" in check_names(CatalogItem)
    assert CatalogGroup.__table__.c.migration_run_id.nullable is True
    assert CatalogItem.__table__.c.migration_run_id.nullable is True
    assert CatalogGroup.__table__.c.source_record_key.nullable is True
    assert CatalogItem.__table__.c.source_record_key.nullable is True
    assert "ix_catalog_groups_live_source" in index_names(CatalogGroup)
    assert "ix_catalog_items_live_source" in index_names(CatalogItem)
    assert "ix_catalog_items_catalog_group_id" in index_names(CatalogItem)


def test_listing_models_support_live_rows_and_saved_items():
    listing_columns = Listing.__table__.c
    media_columns = ListingMedia.__table__.c

    assert listing_columns.price_text.type.length == 120
    assert listing_columns.migration_run_id.nullable is True
    assert listing_columns.source_record_key.nullable is True
    assert media_columns.position.nullable is False
    assert media_columns.migration_run_id.nullable is True
    assert "ck_listing_media_type" in check_names(ListingMedia)
    assert ("listing_id", "position") in unique_columns(ListingMedia)
    assert ("owner_user_account_id", "listing_id") in unique_columns(ListingSave)


def test_advertisement_keeps_json_targets_and_historical_integer_counters():
    columns = Advertisement.__table__.c

    assert isinstance(columns.targets_json.type, JSON)
    assert columns.price.type.python_type is int
    assert columns.views.type.python_type is int
    assert columns.clicks.type.python_type is int
    assert columns.placement.default.arg == "home"
    # K14: reklama joylash qo'shilgach ustun ixtiyoriy bo'ldi — yangi
    # reklama migratsiya yozuvidan kelmaydi. Ko'chirilgan yozuvlarda u
    # baribir to'ladi, buni quyidagi test tekshiradi.
    assert columns.migration_run_id.nullable is True


def test_migrated_advertisements_always_carry_their_run():
    """Ko'chirish bosqichi har bir yozuvga run id sini yozadi.

    Ustun ixtiyoriy bo'lgani bilan bu shart yo'qolmadi: u endi
    ma'lumot ko'chiruvchi kodda ta'minlanadi.
    """
    source = (
        Path(__file__).resolve().parents[1]
        / "app" / "legacy_migration" / "advertisement_stage.py"
    ).read_text(encoding="utf-8")
    assert '"migration_run_id": run.id' in source
    assert "target.migration_run_id = run.id" in source


def test_legacy_mapping_is_unique_per_entity_and_legacy_id():
    assert ("entity_type", "legacy_id") in unique_columns(LegacyIdMap)


def test_media_mapping_distinguishes_desktop_mobile_and_listing_positions():
    assert ("entity_type", "legacy_id", "slot") in unique_columns(MediaMigration)


def test_every_migration_control_row_has_a_run_reference():
    for model in (LegacyIdMap, MigrationIssue, MediaMigration):
        assert model.__table__.c.keys()
        run_column = (
            model.__table__.c.last_run_id
            if model is LegacyIdMap
            else model.__table__.c.migration_run_id
        )
        assert run_column.nullable is False

    assert MigrationRun.__table__.c.environment.nullable is False
    assert MigrationRun.__table__.c.stage.nullable is False
    assert MigrationRun.__table__.c.status.nullable is False
