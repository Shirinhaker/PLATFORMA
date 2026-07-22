import hashlib
import os
import shutil
import tempfile
import time
import unittest


TEST_ROOT = tempfile.mkdtemp(prefix="koprik-subscription-api-")
os.environ["TEST_MODE"] = "1"

from fastapi.testclient import TestClient

import database
import access_config
from database import db, init_db
from main import app


class BusinessSubscriptionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_db_path = database.DB_PATH
        cls.original_restricted = access_config.PROJECT_ACCESS_RESTRICTED
        access_config.PROJECT_ACCESS_RESTRICTED = False
        database.DB_PATH = os.path.join(TEST_ROOT, "platforma.db")
        init_db()
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        now = int(time.time())
        conn = db()

        def add_user(login, role):
            conn.execute(
                "INSERT INTO users(login,pass_hash,role,name,created_at) VALUES(?,?,?,?,?)",
                (login, "x", role, login.replace("_", " ").title(), now),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        def add_session(user_id, token):
            conn.execute(
                "INSERT INTO mobile_sessions(user_id,token_hash,created_at,expires_at,last_used_at,revoked_at) "
                "VALUES(?,?,?,?,?,0)",
                (
                    user_id,
                    hashlib.sha256(token.encode()).hexdigest(),
                    now,
                    now + 3600,
                    now,
                ),
            )

        cls.owner_id = add_user("subscription_owner", "business")
        cls.owner_token = "subscription-owner-token"
        add_session(cls.owner_id, cls.owner_token)
        conn.execute(
            "INSERT INTO businesses(user_id,name,status,created_at) VALUES(?,?,?,?)",
            (cls.owner_id, "Birinchi biznes", "active", now),
        )
        cls.business_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        cls.other_owner_id = add_user("subscription_other", "business")
        cls.other_owner_token = "subscription-other-token"
        add_session(cls.other_owner_id, cls.other_owner_token)
        conn.execute(
            "INSERT INTO businesses(user_id,name,status,created_at) VALUES(?,?,?,?)",
            (cls.other_owner_id, "Ikkinchi biznes", "active", now),
        )
        cls.other_business_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        cls.user_id = add_user("subscription_personal", "user")
        cls.user_token = "subscription-personal-token"
        add_session(cls.user_id, cls.user_token)

        conn.execute(
            "INSERT INTO staff(business_id,name,status,created_at,perms,can_login) "
            "VALUES(?,?,?,?,?,?)",
            (cls.business_id, "Obuna xodimi", "active", now, '["ads"]', 1),
        )
        staff_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        cls.staff_token = "subscription-staff-token"
        conn.execute(
            "INSERT INTO staff_sessions(token,staff_id,business_id,created_at) VALUES(?,?,?,?)",
            (cls.staff_token, staff_id, cls.business_id, now),
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        database.DB_PATH = cls.original_db_path
        access_config.PROJECT_ACCESS_RESTRICTED = cls.original_restricted
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def setUp(self):
        conn = db()
        conn.execute("DELETE FROM business_subscriptions")
        conn.commit()
        conn.close()

    def auth(self, token):
        return {"Authorization": "Bearer " + token}

    def staff_auth(self):
        return {
            "X-Telegram-Init-Data": "staff:" + self.staff_token,
            "X-Staff-Token": self.staff_token,
        }

    def test_owner_can_read_default_activate_and_read_persisted_plus(self):
        default = self.client.get(
            "/api/business/subscription", headers=self.auth(self.owner_token)
        )
        self.assertEqual(default.status_code, 200)
        self.assertEqual(default.json()["current"]["plan_code"], "free")
        self.assertTrue(default.json()["demo_mode"])

        activated = self.client.post(
            "/api/business/subscription/demo-activate",
            headers=self.auth(self.owner_token),
            json={"plan_code": "plus", "duration_months": 3},
        )
        self.assertEqual(activated.status_code, 200)
        self.assertTrue(activated.json()["ok"])
        self.assertEqual(activated.json()["current"]["plan_code"], "plus")
        self.assertTrue(activated.json()["features"]["home_nearby_eligible"])
        self.assertNotIn("unlimited_stories", activated.json()["features"])
        self.assertNotIn("regional_stories_eligible", activated.json()["features"])

        persisted = self.client.get(
            "/api/business/subscription", headers=self.auth(self.owner_token)
        )
        self.assertEqual(persisted.json()["current"]["id"], activated.json()["current"]["id"])

    def test_invalid_plan_and_durations_return_400(self):
        cases = (("gold", 1), ("free", 1), ("plus", 2), ("pro", 0))
        for plan_code, duration in cases:
            with self.subTest(plan_code=plan_code, duration=duration):
                response = self.client.post(
                    "/api/business/subscription/demo-activate",
                    headers=self.auth(self.owner_token),
                    json={"plan_code": plan_code, "duration_months": duration},
                )
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.json().get("detail"))

    def test_non_exact_duration_json_values_return_controlled_400(self):
        cases = (True, False, 1.9, "3", None)
        for duration in cases:
            with self.subTest(duration=repr(duration)):
                response = self.client.post(
                    "/api/business/subscription/demo-activate",
                    headers=self.auth(self.owner_token),
                    json={"plan_code": "plus", "duration_months": duration},
                )
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.json().get("detail"))

        overflow = self.client.post(
            "/api/business/subscription/demo-activate",
            headers={**self.auth(self.owner_token), "content-type": "application/json"},
            content='{"plan_code":"plus","duration_months":1e400}',
        )
        self.assertEqual(overflow.status_code, 400)
        self.assertTrue(overflow.json().get("detail"))

    def test_unauthenticated_personal_and_staff_are_rejected(self):
        unauthenticated = self.client.get("/api/business/subscription")
        personal = self.client.get(
            "/api/business/subscription", headers=self.auth(self.user_token)
        )
        staff_get = self.client.get(
            "/api/business/subscription", headers=self.staff_auth()
        )
        staff_post = self.client.post(
            "/api/business/subscription/demo-activate",
            headers=self.staff_auth(),
            json={"plan_code": "pro", "duration_months": 1},
        )

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(personal.status_code, 403)
        self.assertEqual(staff_get.status_code, 403)
        self.assertEqual(staff_post.status_code, 403)

    def test_two_businesses_only_see_their_own_subscription_history(self):
        self.client.post(
            "/api/business/subscription/demo-activate",
            headers=self.auth(self.owner_token),
            json={"plan_code": "plus", "duration_months": 1},
        )
        self.client.post(
            "/api/business/subscription/demo-activate",
            headers=self.auth(self.owner_token),
            json={"plan_code": "pro", "duration_months": 3},
        )

        first = self.client.get(
            "/api/business/subscription", headers=self.auth(self.owner_token)
        ).json()
        second = self.client.get(
            "/api/business/subscription", headers=self.auth(self.other_owner_token)
        ).json()

        self.assertEqual(first["current"]["plan_code"], "pro")
        self.assertEqual(len(first["history"]), 1)
        self.assertEqual(second["current"]["plan_code"], "free")
        self.assertEqual(second["history"], [])


if __name__ == "__main__":
    unittest.main()
