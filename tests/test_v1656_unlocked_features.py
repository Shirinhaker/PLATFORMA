import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import main
from feature_flags import FEATURE_ENV_NAMES, feature_snapshot
from migration_check import prepare_release_database
from runtime_config import validate_runtime_config


ROOT = Path(__file__).resolve().parents[1]
UNLOCKED_FEATURES = {
    "listings": "MVP_LISTINGS_ENABLED",
    "stories": "MVP_STORIES_ENABLED",
    "chat": "MVP_CHAT_ENABLED",
    "systemization": "MVP_SYSTEMIZATION_ENABLED",
    "taxi": "MVP_TAXI_ENABLED",
}


class V1656UnlockedFeaturesTests(unittest.TestCase):
    def test_all_completed_v1656_features_are_enabled_by_default(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE platform_feature_flags(
              feature_code TEXT PRIMARY KEY,
              enabled INTEGER NOT NULL,
              updated_by_tg_id INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            )
            """
        )
        try:
            self.assertEqual(FEATURE_ENV_NAMES, UNLOCKED_FEATURES)
            self.assertEqual(
                feature_snapshot(conn, environ={}),
                {code: True for code in UNLOCKED_FEATURES},
            )
        finally:
            conn.close()

    def test_database_override_can_still_disable_one_feature(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE platform_feature_flags(
              feature_code TEXT PRIMARY KEY,
              enabled INTEGER NOT NULL,
              updated_by_tg_id INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO platform_feature_flags VALUES('chat', 0, 1, 1)"
        )
        try:
            snapshot = feature_snapshot(conn, environ={})
            self.assertFalse(snapshot["chat"])
            self.assertTrue(snapshot["listings"])
            self.assertTrue(snapshot["stories"])
            self.assertTrue(snapshot["systemization"])
            self.assertTrue(snapshot["taxi"])
        finally:
            conn.close()

    def test_build_contract_reports_every_open_section(self):
        response = TestClient(main.app).get("/api/build")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        for field in (
            "stories_enabled",
            "listings_enabled",
            "general_chat_enabled",
            "systemization_enabled",
            "taxi_call_enabled",
            "ai_all_businesses_enabled",
        ):
            self.assertIs(payload.get(field), True, field)

    def test_production_requires_every_unlocked_feature_to_be_on(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            env = {
                "APP_ENV": "production",
                "BASE_URL": "https://koprik.uz",
                "BOT_TOKEN": "12345:" + "A" * 24,
                "WEBHOOK_SECRET": "w" * 40,
                "MOBILE_OTP_SECRET": "m" * 40,
                "PAYMENT_TOKEN_SECRET": "p" * 56,
                "ADMIN_AUDIT_IP_SECRET": "a" * 40,
                "ADMIN_TG_IDS": "123456",
                "PERSISTENT_ROOT": str(base),
                "PAYMENT_RECEIPT_DIR": str(base / "private" / "receipts"),
                "TEST_MODE": "0",
                **{env_name: "1" for env_name in UNLOCKED_FEATURES.values()},
            }
            validate_runtime_config(
                db_path=str(base / "db" / "platforma.db"),
                upload_dir=str(base / "uploads"),
                backup_dir=str(base / "backups"),
                environ=env,
            )
            env["MVP_CHAT_ENABLED"] = "0"
            with self.assertRaisesRegex(RuntimeError, "MVP_CHAT_ENABLED=1"):
                validate_runtime_config(
                    db_path=str(base / "db" / "platforma.db"),
                    upload_dir=str(base / "uploads"),
                    backup_dir=str(base / "backups"),
                    environ=env,
                )

    def test_release_migration_backs_up_and_opens_existing_feature_rows(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            db_path = base / "platforma.db"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE platform_feature_flags(
                  feature_code TEXT PRIMARY KEY,
                  enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                  updated_by_tg_id INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL
                )
                """
            )
            conn.executemany(
                "INSERT INTO platform_feature_flags VALUES(?, 0, 9, 9)",
                [(code,) for code in UNLOCKED_FEATURES],
            )
            conn.commit()
            conn.close()

            result = prepare_release_database(
                db_path,
                base / "backups",
                expected_schema="v1656-unlocked",
                retention=2,
            )

            conn = sqlite3.connect(db_path)
            rows = dict(
                conn.execute(
                    "SELECT feature_code, enabled FROM platform_feature_flags"
                ).fetchall()
            )
            conn.close()
            self.assertEqual(
                rows,
                {code: 1 for code in UNLOCKED_FEATURES},
            )
            self.assertEqual(result["integrity"], "ok")
            self.assertTrue(Path(result["backup_path"]).is_file())

    def test_ai_is_open_to_business_owners_but_report_stays_restricted(self):
        html = (ROOT / "static/index.html").read_text(encoding="utf-8")
        ai_backend = (ROOT / "ai_agent.py").read_text(encoding="utf-8")

        ai_card = html.split('data-nav="ai-chat"', maxsplit=1)[1].split(
            "</div>", maxsplit=1
        )[0]
        report_card = html.split('id="cabReportMenu"', maxsplit=1)[1].split(
            "</div>", maxsplit=1
        )[0]
        self.assertNotIn("data-privileged-only", ai_card)
        self.assertIn("data-privileged-only", report_card)
        self.assertNotIn("_require_privileged_ai", ai_backend)
        self.assertIn("require_business", ai_backend)
        self.assertIn("deny_staff", ai_backend)

    def test_taxi_category_call_uses_the_live_taxi_flow(self):
        html = (ROOT / "static/index.html").read_text(encoding="utf-8")

        self.assertIn("data-taxi-call", html)
        self.assertIn("if(taxiCall){enterCall();return;}", html)
        self.assertNotIn("Chaqiruv tizimi 2-bosqichda ishlaydi", html)

    def test_security_controls_remain_in_place(self):
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        access_source = (ROOT / "access_config.py").read_text(encoding="utf-8")
        admin_source = (ROOT / "admin_auth.py").read_text(encoding="utf-8")

        for expected in (
            "_account_blocked_for_user",
            "_staff_account_blocked",
            "_mutation_block_exempt",
            "project_access_is_restricted",
            "PAYMENT_RECEIPT_DIR",
        ):
            self.assertIn(expected, main_source)
        self.assertIn("PROJECT_ACCESS_RESTRICTED", access_source)
        self.assertIn("ensure_admin_auth_schema", admin_source)
        self.assertIn("admin_session", admin_source)


if __name__ == "__main__":
    unittest.main()
