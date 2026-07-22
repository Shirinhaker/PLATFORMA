import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from backup_database import create_database_backup
from runtime_config import validate_runtime_config


def valid_production_env(root):
    return {
        "APP_ENV": "production",
        "BASE_URL": "https://koprik.uz",
        "BOT_TOKEN": "123456789:abcdefghijklmnopqrstuvwxyzABCDE",
        "WEBHOOK_SECRET": "w" * 48,
        "MOBILE_OTP_SECRET": "m" * 48,
        "INIT_DATA_MAX_AGE_SEC": "86400",
        "PERSISTENT_ROOT": root,
        "PROJECT_ACCESS_RESTRICTED": "1",
        "PRIVILEGED_TG_IDS": "123456789",
        "TEST_MODE": "0",
    }


class ProductionConfigTests(unittest.TestCase):
    def test_development_keeps_local_defaults_available(self):
        validate_runtime_config(
            db_path="platforma.db",
            upload_dir="uploads",
            backup_dir="backups",
            environ={"APP_ENV": "development", "TEST_MODE": "1"},
        )

    def test_valid_production_configuration_is_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            validate_runtime_config(
                db_path=os.path.join(root, "platforma.db"),
                upload_dir=os.path.join(root, "uploads"),
                backup_dir=os.path.join(root, "backups"),
                environ=valid_production_env(root),
            )

    def test_production_rejects_test_mode_weak_secrets_and_ephemeral_paths(self):
        env = {
            "APP_ENV": "production",
            "BASE_URL": "http://localhost:8000",
            "BOT_TOKEN": "short",
            "WEBHOOK_SECRET": "platforma-webhook-secret",
            "MOBILE_OTP_SECRET": "platforma-webhook-secret",
            "TEST_MODE": "1",
            "TEST_OTP_CODE": "123456",
            "PERSISTENT_ROOT": "/data",
            "PROJECT_ACCESS_RESTRICTED": "1",
        }
        with self.assertRaises(RuntimeError) as raised:
            validate_runtime_config(
                db_path="platforma.db",
                upload_dir="uploads",
                backup_dir="backups",
                environ=env,
            )
        message = str(raised.exception)
        for expected in (
            "BASE_URL",
            "BOT_TOKEN",
            "WEBHOOK_SECRET",
            "MOBILE_OTP_SECRET",
            "TEST_MODE",
            "TEST_OTP_CODE",
            "DB_PATH",
            "UPLOAD_DIR",
            "BACKUP_DIR",
            "PRIVILEGED_TG_IDS",
        ):
            self.assertIn(expected, message)

    def test_production_requires_paths_inside_selected_volume(self):
        with tempfile.TemporaryDirectory() as root:
            env = valid_production_env(root)
            with self.assertRaises(RuntimeError) as raised:
                validate_runtime_config(
                    db_path="/tmp/platforma.db",
                    upload_dir=os.path.join(root, "uploads"),
                    backup_dir=os.path.join(root, "backups"),
                    environ=env,
                )
            self.assertIn("DB_PATH PERSISTENT_ROOT ichida", str(raised.exception))

    def test_example_placeholders_can_never_pass_as_real_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            env = valid_production_env(root)
            env.update(
                {
                    "BASE_URL": "https://YOUR-DOMAIN.example",
                    "BOT_TOKEN": "YOUR_TELEGRAM_BOT_TOKEN",
                    "WEBHOOK_SECRET": "GENERATE_A_RANDOM_SECRET_AT_LEAST_32_CHARS",
                    "MOBILE_OTP_SECRET": "GENERATE_A_DIFFERENT_RANDOM_SECRET_AT_LEAST_32_CHARS",
                }
            )
            with self.assertRaises(RuntimeError) as raised:
                validate_runtime_config(
                    db_path=os.path.join(root, "platforma.db"),
                    upload_dir=os.path.join(root, "uploads"),
                    backup_dir=os.path.join(root, "backups"),
                    environ=env,
                )
            message = str(raised.exception)
            self.assertIn("BASE_URL", message)
            self.assertIn("BOT_TOKEN", message)
            self.assertIn("WEBHOOK_SECRET", message)
            self.assertIn("MOBILE_OTP_SECRET", message)


class DatabaseBackupTests(unittest.TestCase):
    def _create_source_database(self, path):
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        conn.executemany("INSERT INTO sample(value) VALUES(?)", [("bir",), ("ikki",)])
        conn.commit()
        conn.close()

    def test_backup_is_complete_private_and_readable(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "platforma.db")
            backup_dir = os.path.join(root, "backups")
            self._create_source_database(source)

            created = create_database_backup(source, backup_dir, retention=14)

            self.assertTrue(os.path.isfile(created))
            mode = stat.S_IMODE(os.stat(created).st_mode)
            self.assertEqual(mode, 0o600)
            conn = sqlite3.connect(created)
            rows = conn.execute("SELECT value FROM sample ORDER BY id").fetchall()
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            conn.close()
            self.assertEqual(rows, [("bir",), ("ikki",)])
            self.assertEqual(integrity, "ok")

    def test_backup_retention_keeps_only_requested_count(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "platforma.db")
            backup_dir = os.path.join(root, "backups")
            self._create_source_database(source)
            for _ in range(4):
                create_database_backup(source, backup_dir, retention=2)
            files = list(Path(backup_dir).glob("platforma-*.sqlite3"))
            self.assertEqual(len(files), 2)


class ProductionFoundationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.main_text = (root / "main.py").read_text(encoding="utf-8")
        cls.database_text = (root / "database.py").read_text(encoding="utf-8")
        cls.requirements = (root / "requirements.txt").read_text(encoding="utf-8")

    def test_health_and_readiness_routes_exist_outside_private_api(self):
        self.assertIn('@app.get("/healthz"', self.main_text)
        self.assertIn('@app.get("/readyz"', self.main_text)
        self.assertNotIn('@app.get("/api/healthz"', self.main_text)

    def test_sqlite_connections_have_busy_timeout_and_safe_sync(self):
        self.assertIn("timeout=30", self.database_text)
        self.assertIn("PRAGMA busy_timeout = 30000", self.database_text)
        self.assertIn("PRAGMA synchronous = NORMAL", self.database_text)

    def test_direct_dependencies_are_pinned(self):
        for line in self.requirements.splitlines():
            if line.strip():
                self.assertIn("==", line)

    def test_v1621_foundation_remains_in_current_build(self):
        self.assertIn('APP_BUILD = "v1629"', self.main_text)
        self.assertIn('"production_foundation_v1621": True', self.main_text)


if __name__ == "__main__":
    unittest.main()
