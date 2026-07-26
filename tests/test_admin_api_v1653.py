import hashlib
import os
import shutil
import tempfile
import time
import unittest

# This file is discovered before the older admin/auth contract.  Set the
# established deterministic test runtime before importing the singleton app.
os.environ["TEST_MODE"] = "1"
os.environ["TEST_OTP_CODE"] = "123456"

from fastapi.testclient import TestClient

import access_config
import database
from admin_auth import start_admin_challenge, verify_admin_challenge
from database import db, init_db
from main import app


class AdminApiV1653Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="koprik-admin-v1653-")
        cls.original_db_path = database.DB_PATH
        cls.original_restricted = access_config.PROJECT_ACCESS_RESTRICTED
        database.DB_PATH = os.path.join(cls.root, "platforma.db")
        access_config.PROJECT_ACCESS_RESTRICTED = False
        os.environ["ADMIN_TG_IDS"] = "1423181561"
        init_db()
        stamp = int(time.time())
        conn = db()
        conn.execute(
            """
            INSERT INTO users(
              tg_id,login,pass_hash,role,name,phone,district,district_key,
              created_at
            ) VALUES(1001,'owner','secret-hash','business','Owner','+99890',
              'Qumqo‘rg‘on','qumqorgon',?)
            """,
            (stamp,),
        )
        cls.owner_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO businesses(
              user_id,name,yon,tur,phone,address,lat,lng,status,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                cls.owner_id, "Audit Market", "Savdo", "Do‘kon", "+99891",
                "Markaz", 37.8, 67.6, "active", stamp,
            ),
        )
        cls.business_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO items(
              business_id,name,price,note,kind,created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (cls.business_id, "Audit burg‘i", "100", "", "product", stamp),
        )
        cls.product_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO users(
              tg_id,login,pass_hash,role,name,created_at
            ) VALUES(1002,'reporter','private-secret','user','Reporter',?)
            """,
            (stamp,),
        )
        cls.reporter_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        cls.reporter_token = "reporter-mobile-token"
        conn.execute(
            """
            INSERT INTO mobile_sessions(
              user_id,token_hash,created_at,expires_at,last_used_at,revoked_at
            ) VALUES(?,?,?,?,?,0)
            """,
            (
                cls.reporter_id,
                hashlib.sha256(cls.reporter_token.encode()).hexdigest(),
                stamp,
                stamp + 3600,
                stamp,
            ),
        )
        challenge = start_admin_challenge(
            conn,
            1423181561,
            "platforma-webhook-secret",
            fixed_code="123456",
            now=stamp,
        )
        cls.admin_token = verify_admin_challenge(
            conn,
            challenge["id"],
            "123456",
            "platforma-webhook-secret",
            now=stamp,
        )
        conn.close()
        cls.context = TestClient(app, base_url="https://admin.koprik.uz")
        cls.client = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)
        database.DB_PATH = cls.original_db_path
        access_config.PROJECT_ACCESS_RESTRICTED = cls.original_restricted
        shutil.rmtree(cls.root, ignore_errors=True)

    @property
    def admin_cookies(self):
        return {"koprik_admin_session": self.admin_token}

    @property
    def reporter_auth(self):
        return {"Authorization": "Bearer " + self.reporter_token}

    def test_dashboard_requires_admin_and_has_safe_sections(self):
        self.assertEqual(
            self.client.get("/api/admin/dashboard").status_code, 401
        )
        response = self.client.get(
            "/api/admin/dashboard", cookies=self.admin_cookies
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        for key in (
            "payments", "users", "businesses", "content", "reports",
            "activity",
        ):
            self.assertIn(key, payload)
        self.assertNotIn("pass_hash", response.text)
        self.assertNotIn("token_hash", response.text)
        self.assertNotIn("receipt_path", response.text)

    def test_account_list_is_paginated_private_and_restrictions_independent(self):
        response = self.client.get(
            "/api/admin/users?q=Owner", cookies=self.admin_cookies
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertLessEqual(len(response.json()["items"]), 50)
        self.assertNotIn("district", response.text)
        self.assertNotIn("pass_hash", response.text)
        for restriction in ("content_hidden", "account_blocked"):
            changed = self.client.post(
                f"/api/admin/accounts/business/{self.business_id}/restrict",
                cookies=self.admin_cookies,
                json={"restriction": restriction, "reason": "Tekshiruv"},
            )
            self.assertEqual(changed.status_code, 200, changed.text)
        detail = self.client.get(
            f"/api/admin/businesses/{self.business_id}",
            cookies=self.admin_cookies,
        ).json()
        self.assertEqual(
            set(detail["active_restrictions"]),
            {"content_hidden", "account_blocked"},
        )
        restored = self.client.post(
            f"/api/admin/accounts/business/{self.business_id}/unrestrict",
            cookies=self.admin_cookies,
            json={
                "restriction": "account_blocked",
                "reason": "Mutation testidan keyin ochildi",
            },
        )
        self.assertEqual(restored.status_code, 200, restored.text)

    def test_content_hide_is_reactive_and_owner_row_is_not_deleted(self):
        hidden = self.client.post(
            f"/api/admin/content/product/{self.product_id}/hide",
            cookies=self.admin_cookies,
            json={"reason": "Shikoyat tekshiruvi"},
        )
        self.assertEqual(hidden.status_code, 200, hidden.text)
        self.assertEqual(hidden.json()["moderation_status"], "hidden")
        conn = db()
        self.assertIsNotNone(
            conn.execute(
                "SELECT id FROM items WHERE id=?", (self.product_id,)
            ).fetchone()
        )
        conn.close()
        restored = self.client.post(
            f"/api/admin/content/product/{self.product_id}/restore",
            cookies=self.admin_cookies,
            json={"reason": "Kontent tekshirildi"},
        )
        self.assertEqual(restored.status_code, 200, restored.text)

    def test_report_workflow_and_audit_are_available(self):
        created = self.client.post(
            "/api/reports",
            headers=self.reporter_auth,
            json={
                "content_kind": "product",
                "content_id": self.product_id,
                "reason_code": "fraud",
                "comment": "Narx noto‘g‘ri",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        duplicate = self.client.post(
            "/api/reports",
            headers=self.reporter_auth,
            json={
                "content_kind": "product",
                "content_id": self.product_id,
                "reason_code": "fraud",
                "comment": "Takror",
            },
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        report_id = created.json()["id"]
        resolved = self.client.post(
            f"/api/admin/reports/{report_id}/resolve",
            cookies=self.admin_cookies,
            json={
                "resolution": "Ko‘rib chiqildi",
                "moderation_action": "hide_content",
            },
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        audit = self.client.get(
            "/api/admin/audit", cookies=self.admin_cookies
        )
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertTrue(audit.json()["items"])
        self.assertEqual(
            self.client.delete(
                "/api/admin/audit/1", cookies=self.admin_cookies
            ).status_code,
            405,
        )

    def test_profile_and_business_reports_use_existing_admin_queue(self):
        conn = db()
        conn.execute(
            """
            DELETE FROM moderation_reports
            WHERE reporter_user_id=?
              AND content_kind IN ('profile','business')
            """,
            (self.reporter_id,),
        )
        conn.execute(
            """
            DELETE FROM account_restrictions
            WHERE status='active'
              AND (
                (actor_type='user' AND actor_id=?)
                OR (actor_type='business' AND actor_id=?)
              )
            """,
            (self.owner_id, self.business_id),
        )
        conn.commit()
        conn.close()

        profile = self.client.post(
            "/api/reports",
            headers=self.reporter_auth,
            json={
                "content_kind": "profile",
                "content_id": self.owner_id,
                "reason_code": "fraud",
                "comment": "Profil ma'lumoti noto'g'ri",
            },
        )
        business = self.client.post(
            "/api/reports",
            headers=self.reporter_auth,
            json={
                "content_kind": "business",
                "content_id": self.business_id,
                "reason_code": "illegal",
                "comment": "Faoliyatni tekshirish kerak",
            },
        )
        self.assertEqual(profile.status_code, 201, profile.text)
        self.assertEqual(business.status_code, 201, business.text)

        queue = self.client.get(
            "/api/admin/reports?status=open",
            cookies=self.admin_cookies,
        )
        self.assertEqual(queue.status_code, 200, queue.text)
        kinds = {item["content_kind"] for item in queue.json()["items"]}
        self.assertTrue({"profile", "business"}.issubset(kinds))

        assigned = self.client.post(
            f"/api/admin/reports/{profile.json()['id']}/assign",
            cookies=self.admin_cookies,
            json={},
        )
        self.assertEqual(assigned.status_code, 200, assigned.text)
        self.assertEqual(assigned.json()["status"], "reviewing")

        resolved = self.client.post(
            f"/api/admin/reports/{profile.json()['id']}/resolve",
            cookies=self.admin_cookies,
            json={
                "resolution": "Profil tekshirildi",
                "moderation_action": "content_hidden",
            },
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["status"], "resolved")

        dismissed = self.client.post(
            f"/api/admin/reports/{business.json()['id']}/dismiss",
            cookies=self.admin_cookies,
            json={
                "resolution": "Asos topilmadi",
                "moderation_action": "none",
            },
        )
        self.assertEqual(dismissed.status_code, 200, dismissed.text)
        self.assertEqual(dismissed.json()["status"], "dismissed")

        audit = self.client.get(
            "/api/admin/audit", cookies=self.admin_cookies
        )
        self.assertEqual(audit.status_code, 200, audit.text)
        actions = {item["action"] for item in audit.json()["items"]}
        self.assertTrue(
            {"report.assign", "report.resolved", "report.dismissed"}
            .issubset(actions)
        )


if __name__ == "__main__":
    unittest.main()
