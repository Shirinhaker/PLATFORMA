from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "cutover_app.py"


def _load_retired_app(monkeypatch):
    monkeypatch.setenv("KOPRIK_MIGRATION_MAINTENANCE", "0")
    module_name = "cutover_app_contract_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retired_legacy_shell_keeps_health_up_and_writes_frozen(monkeypatch):
    module = _load_retired_app(monkeypatch)

    assert not hasattr(module, "_normal_app")
    assert not hasattr(module, "MAINTENANCE_MODE")

    with TestClient(module.app) as client:
        ready = client.get("/readyz")
        assert ready.status_code == 200
        assert ready.json()["retired"] is True
        assert ready.json()["writes_frozen"] is True
        assert ready.json()["legacy_runtime_enabled"] is False
        assert ready.json()["mode"] == "legacy_retired"
        assert ready.headers["x-koprik-maintenance"] == "legacy-retired"

        page = client.get("/")
        assert page.status_code == 503

        direct_page = client.get("/maintenance.html")
        assert direct_page.status_code == 200
        assert "Texnik ishlar olib borilmoqda" in direct_page.text

        mutation = client.post("/api/profile", json={"name": "blocked"})
        assert mutation.status_code == 503
        assert mutation.json()["code"] == "legacy_retired"
        assert mutation.json()["retired"] is True
        assert mutation.json()["writes_frozen"] is True

        webhook = client.post("/webhook", json={"update_id": 1})
        assert webhook.status_code == 503
        assert webhook.json()["code"] == "legacy_retired"


def test_retired_wrapper_uses_existing_frontend_maintenance_page(monkeypatch):
    module = _load_retired_app(monkeypatch)
    assert module.MAINTENANCE_HTML == ROOT / "frontend" / "public" / "maintenance.html"
    assert module.MAINTENANCE_HTML.is_file()
