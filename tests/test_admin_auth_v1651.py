import sqlite3
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ["TEST_MODE"] = "1"
os.environ["ADMIN_TG_IDS"] = "1423181561"
os.environ["TEST_OTP_CODE"] = "123456"

from fastapi.testclient import TestClient

from admin_auth import (
    admin_ids,
    admin_session,
    ensure_admin_auth_schema,
    is_admin_tg_id,
    revoke_admin_session,
    start_admin_challenge,
    verify_admin_challenge,
)
import access_config
import database
from database import init_db
from main import app


class AdminAuthDomainTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_admin_auth_schema(self.conn)
        self.env = {"ADMIN_TG_IDS": "1423181561, 607563067"}
        self.secret = "s" * 48

    def tearDown(self):
        self.conn.close()

    def test_admin_ids_are_separate_and_strict(self):
        self.assertEqual(admin_ids(self.env), {1423181561, 607563067})
        self.assertTrue(is_admin_tg_id(1423181561, self.env))
        self.assertFalse(is_admin_tg_id(1, self.env))
        self.assertEqual(
            admin_ids({"ADMIN_TG_IDS": "1, x, -2, 0, 3"}),
            {1, 3},
        )

    def test_single_use_code_creates_hashed_session(self):
        challenge = start_admin_challenge(
            self.conn,
            1423181561,
            self.secret,
            fixed_code="123456",
            now=100,
        )
        token = verify_admin_challenge(
            self.conn,
            challenge["id"],
            "123456",
            self.secret,
            now=101,
        )
        self.assertIsNotNone(admin_session(self.conn, token, now=102))
        with self.assertRaises(ValueError):
            verify_admin_challenge(
                self.conn,
                challenge["id"],
                "123456",
                self.secret,
                now=103,
            )
        stored = self.conn.execute(
            "SELECT token_hash FROM admin_sessions"
        ).fetchone()["token_hash"]
        self.assertNotEqual(stored, token)

    def test_challenge_and_idle_session_expire(self):
        expired = start_admin_challenge(
            self.conn,
            1423181561,
            self.secret,
            fixed_code="123456",
            now=100,
        )
        with self.assertRaises(ValueError):
            verify_admin_challenge(
                self.conn,
                expired["id"],
                "123456",
                self.secret,
                now=401,
            )

        challenge = start_admin_challenge(
            self.conn,
            1423181561,
            self.secret,
            fixed_code="654321",
            now=500,
        )
        token = verify_admin_challenge(
            self.conn,
            challenge["id"],
            "654321",
            self.secret,
            now=501,
        )
        self.assertIsNone(admin_session(self.conn, token, now=2302))

    def test_wrong_attempts_are_limited_and_logout_revokes(self):
        challenge = start_admin_challenge(
            self.conn,
            1423181561,
            self.secret,
            fixed_code="123456",
            now=100,
        )
        for attempt in range(5):
            with self.assertRaises(ValueError):
                verify_admin_challenge(
                    self.conn,
                    challenge["id"],
                    "000000",
                    self.secret,
                    now=101 + attempt,
                )
        with self.assertRaises(ValueError):
            verify_admin_challenge(
                self.conn,
                challenge["id"],
                "123456",
                self.secret,
                now=110,
            )

        fresh = start_admin_challenge(
            self.conn,
            1423181561,
            self.secret,
            fixed_code="654321",
            now=200,
        )
        token = verify_admin_challenge(
            self.conn,
            fresh["id"],
            "654321",
            self.secret,
            now=201,
        )
        revoke_admin_session(self.conn, token, now=202)
        self.assertIsNone(admin_session(self.conn, token, now=203))


class AdminAuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_db_path = database.DB_PATH
        cls.original_restricted = access_config.PROJECT_ACCESS_RESTRICTED
        cls.temp_root = tempfile.mkdtemp(prefix="koprik-admin-auth-api-")
        database.DB_PATH = os.path.join(cls.temp_root, "platforma.db")
        access_config.PROJECT_ACCESS_RESTRICTED = False
        init_db()
        cls.ctx = TestClient(app, base_url="https://admin.koprik.uz")
        cls.client = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)
        database.DB_PATH = cls.original_db_path
        access_config.PROJECT_ACCESS_RESTRICTED = cls.original_restricted
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    def setUp(self):
        self.client.cookies.clear()

    def test_non_admin_id_cannot_start_login(self):
        response = self.client.post(
            "/api/admin/auth/start",
            json={"tg_id": 999},
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_allowed_admin_receives_code_and_cookie_session(self):
        with patch("main.tg_call", new=AsyncMock(return_value={"ok": True})):
            started = self.client.post(
                "/api/admin/auth/start",
                json={"tg_id": 1423181561},
            )
        self.assertEqual(started.status_code, 200, started.text)
        self.assertNotIn("code", started.json())
        verified = self.client.post(
            "/api/admin/auth/verify",
            json={
                "challenge_id": started.json()["challenge_id"],
                "code": "123456",
            },
        )
        self.assertEqual(verified.status_code, 200, verified.text)
        cookie = verified.headers["set-cookie"]
        self.assertIn("koprik_admin_session", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertIn("Secure", cookie)
        self.assertEqual(
            self.client.get("/api/admin/auth/me").status_code,
            200,
        )

    def test_user_bearer_token_never_grants_admin(self):
        response = self.client.get(
            "/api/admin/auth/me",
            headers={"Authorization": "Bearer ordinary-user-token"},
        )
        self.assertEqual(response.status_code, 401, response.text)


if __name__ == "__main__":
    unittest.main()
