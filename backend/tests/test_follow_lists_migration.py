from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.follows.router import router as follows_router


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/0035_follow_lists.py"


def _migration():
    spec = spec_from_file_location("follow_lists", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_follow_lists_migration_extends_education_head_with_target_index():
    migration = _migration()
    source = MIGRATION.read_text(encoding="utf-8")
    assert migration.revision == "0035_follow_lists"
    assert migration.down_revision == "0034_education_management"
    assert '["target_account_id", "created_at", "id"]' in source


def test_follow_lists_have_authenticated_typed_routes():
    routes = {
        (route.path, method)
        for route in follows_router.routes
        for method in (route.methods or set())
    }
    assert ("/api/v1/follows/followers", "GET") in routes
    assert ("/api/v1/follows/following", "GET") in routes
