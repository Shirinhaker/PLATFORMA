import hashlib
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch


TEST_ROOT = tempfile.mkdtemp(prefix="koprik-temporary-access-")
os.environ["TEST_MODE"] = "1"

from fastapi.testclient import TestClient

import access_config
import database
import main
from database import db, init_db
from main import app


class TemporaryAccessControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_db_path = database.DB_PATH
        cls.original_restricted = access_config.PROJECT_ACCESS_RESTRICTED
        database.DB_PATH = os.path.join(TEST_ROOT, "platforma.db")
        init_db()
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        now = int(time.time())
        conn = db()

        def add_mobile_user(tg_id, login, token):
            conn.execute(
                "INSERT INTO users(tg_id,login,pass_hash,role,name,created_at) VALUES(?,?,?,?,?,?)",
                (tg_id, login, "x", "user", login, now),
            )
            user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO mobile_sessions(user_id,token_hash,created_at,expires_at,last_used_at,revoked_at) "
                "VALUES(?,?,?,?,?,0)",
                (user_id, hashlib.sha256(token.encode()).hexdigest(), now, now + 3600, now),
            )

        cls.allowed_mobile_token = "allowed-mobile-access-token"
        cls.blocked_mobile_token = "blocked-mobile-access-token"
        add_mobile_user(next(iter(access_config.PRIVILEGED_TG_IDS)), "allowed_mobile", cls.allowed_mobile_token)
        add_mobile_user(999999998, "blocked_mobile", cls.blocked_mobile_token)
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        database.DB_PATH = cls.original_db_path
        access_config.PROJECT_ACCESS_RESTRICTED = cls.original_restricted
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def setUp(self):
        access_config.PROJECT_ACCESS_RESTRICTED = True
        self.client.cookies.clear()

    def test_non_privileged_telegram_id_is_temporarily_blocked(self):
        with patch("main.verify_init_data", return_value={"id": 999999999}):
            response = self.client.get(
                "/api/build", headers={"X-Telegram-Init-Data": "signed"}
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "project_temporarily_closed")

    def test_given_privileged_telegram_id_can_use_project(self):
        allowed_id = next(iter(access_config.PRIVILEGED_TG_IDS))
        with patch("main.verify_init_data", return_value={"id": allowed_id}):
            response = self.client.get(
                "/api/build", headers={"X-Telegram-Init-Data": "signed"}
            )
        self.assertEqual(response.status_code, 200)

    def test_staff_token_does_not_bypass_temporary_global_block(self):
        response = self.client.get(
            "/api/build",
            headers={"X-Telegram-Init-Data": "staff:token", "X-Staff-Token": "token"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "project_temporarily_closed")

    def test_only_mobile_session_linked_to_given_id_can_pass(self):
        allowed = self.client.get(
            "/api/build",
            headers={"Authorization": "Bearer " + self.allowed_mobile_token},
        )
        blocked = self.client.get(
            "/api/build",
            headers={"Authorization": "Bearer " + self.blocked_mobile_token},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["code"], "project_temporarily_closed")

    def test_mixed_bearer_and_init_data_is_rejected_as_ambiguous(self):
        response = self.client.get(
            "/api/build",
            headers={
                "Authorization": "Bearer " + self.allowed_mobile_token,
                "X-Telegram-Init-Data": "signed",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "ambiguous_authentication")

    def test_media_and_uploaded_static_files_need_privileged_access_cookie(self):
        blocked_media = self.client.get("/media/demo-file")
        blocked_upload = self.client.get("/uploads/demo-file.jpg")
        self.assertEqual(blocked_media.status_code, 403)
        self.assertEqual(blocked_upload.status_code, 403)

        allowed_api = self.client.get(
            "/api/build",
            headers={"Authorization": "Bearer " + self.allowed_mobile_token},
        )
        self.assertEqual(allowed_api.status_code, 200)
        self.assertIn("koprik_privileged_access", self.client.cookies)
        allowed_media = self.client.get("/media/demo-file")
        self.assertEqual(allowed_media.status_code, 200)

    def test_diagnostics_are_off_by_default_and_safe_when_explicitly_enabled(self):
        allowed_id = next(iter(access_config.PRIVILEGED_TG_IDS))
        with patch("main.verify_init_data", return_value={"id": allowed_id}):
            disabled = self.client.get(
                "/api/_dbinfo", headers={"X-Telegram-Init-Data": "signed"}
            )
        self.assertEqual(disabled.status_code, 404)

        with patch.object(main, "PRIVILEGED_DIAGNOSTICS_ENABLED", True), patch(
            "main.verify_init_data", return_value={"id": allowed_id}
        ):
            enabled = self.client.get(
                "/api/_dbinfo", headers={"X-Telegram-Init-Data": "signed"}
            )
            setup_get = self.client.get(
                "/api/_setup", headers={"X-Telegram-Init-Data": "signed"}
            )
        self.assertEqual(enabled.status_code, 200)
        self.assertNotIn("DB_PATH", enabled.json())
        self.assertNotIn("oxirgi_foydalanuvchilar", enabled.json())
        self.assertEqual(setup_get.status_code, 405)

    def test_switch_can_reopen_project_later(self):
        access_config.PROJECT_ACCESS_RESTRICTED = False
        with patch("main.verify_init_data", return_value={"id": 999999999}):
            response = self.client.get(
                "/api/build", headers={"X-Telegram-Init-Data": "signed"}
            )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
