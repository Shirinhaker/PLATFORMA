from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "cutover_app.py"


def _load_maintenance_app(monkeypatch):
    monkeypatch.setenv("KOPRIK_MIGRATION_MAINTENANCE", "1")
    module_name = "cutover_app_contract_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cutover_maintenance_keeps_health_up_and_freezes_writes(monkeypatch):
    module = _load_maintenance_app(monkeypatch)

    assert module.MAINTENANCE_MODE is True
    assert module._normal_app is None

    with TestClient(module.app) as client:
        ready = client.get("/readyz")
        assert ready.status_code == 200
        assert ready.json()["writes_frozen"] is True
        assert ready.headers["x-koprik-maintenance"] == "migration-write-freeze"

        page = client.get("/")
        assert page.status_code == 503
        assert "Texnik ishlar olib borilmoqda" in page.text
        assert "qayta kiring" in page.text

        direct_page = client.get("/maintenance.html")
        assert direct_page.status_code == 200
        assert "Texnik ishlar olib borilmoqda" in direct_page.text

        mutation = client.post("/api/profile", json={"name": "blocked"})
        assert mutation.status_code == 503
        assert mutation.json()["code"] == "migration_maintenance"
        assert mutation.json()["writes_frozen"] is True

        webhook = client.post("/webhook", json={"update_id": 1})
        assert webhook.status_code == 503
        assert webhook.json()["code"] == "migration_maintenance"


def test_cutover_wrapper_uses_existing_frontend_maintenance_page(monkeypatch):
    module = _load_maintenance_app(monkeypatch)
    assert module.MAINTENANCE_HTML == ROOT / "frontend" / "public" / "maintenance.html"
    assert module.MAINTENANCE_HTML.is_file()
