import hashlib
import os
import shutil
import tempfile
import time
import unittest


TEST_ROOT = tempfile.mkdtemp(prefix="koprik-district-offers-api-")
os.environ["DB_PATH"] = os.path.join(TEST_ROOT, "platforma.db")
os.environ["TEST_MODE"] = "1"

from fastapi.testclient import TestClient

import access_config
from database import db, init_db
from location_keys import canonical_district_key
from main import app


class DistrictOffersApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_restricted = access_config.PROJECT_ACCESS_RESTRICTED
        access_config.PROJECT_ACCESS_RESTRICTED = False
        init_db()
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        now = int(time.time())
        conn = db()

        def add_user(login, name, district, role="user"):
            conn.execute(
                "INSERT INTO users(login,pass_hash,role,name,district,district_key,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    login,
                    "x",
                    role,
                    name,
                    district,
                    canonical_district_key(district),
                    now,
                ),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        def add_session(user_id, token):
            conn.execute(
                "INSERT INTO mobile_sessions("
                "user_id,token_hash,created_at,expires_at,last_used_at,revoked_at"
                ") VALUES(?,?,?,?,?,0)",
                (
                    user_id,
                    hashlib.sha256(token.encode()).hexdigest(),
                    now,
                    now + 3600,
                    now,
                ),
            )

        cls.no_district_id = add_user("district_missing", "Manzilsiz", "")
        cls.no_district_token = "district-missing-token"
        add_session(cls.no_district_id, cls.no_district_token)

        cls.viewer_id = add_user("district_viewer", "Ko'ruvchi", "Sho'rchi")
        cls.viewer_token = "district-viewer-token"
        add_session(cls.viewer_id, cls.viewer_token)

        owner_id = add_user(
            "district_owner", "Taklif egasi", "Sho'rchi", role="business"
        )
        cls.owner_token = "district-owner-token"
        add_session(owner_id, cls.owner_token)
        conn.execute(
            "INSERT INTO businesses(user_id,name,status,created_at) VALUES(?,?,?,?)",
            (owner_id, "Mahalliy Plus", "active", now),
        )
        business_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO items(business_id,name,price,kind,created_at) VALUES(?,?,?,?,?)",
            (business_id, "Mahalliy mahsulot", "25000", "product", now),
        )
        conn.execute(
            "INSERT INTO business_subscriptions("
            "business_id,plan_code,duration_months,starts_at,expires_at,status,is_demo,created_at"
            ") VALUES(?,?,?,?,?,'active',1,?)",
            (business_id, "plus", 1, now - 1, now + 3600, now),
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        access_config.PROJECT_ACCESS_RESTRICTED = cls.original_restricted
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def auth(self, token):
        return {"Authorization": "Bearer " + token}

    def test_unauthenticated_and_user_without_district_need_district(self):
        public = self.client.get("/api/home/district-offers")
        missing = self.client.get(
            "/api/home/district-offers", headers=self.auth(self.no_district_token)
        )
        self.assertEqual(public.status_code, 200)
        self.assertTrue(public.json()["needs_district"])
        self.assertTrue(missing.json()["needs_district"])

    def test_authenticated_user_receives_same_district_paid_offers_only(self):
        response = self.client.get(
            "/api/home/district-offers", headers=self.auth(self.viewer_token)
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["needs_district"])
        self.assertTrue(body["items"])
        self.assertEqual(body["items"][0]["business_name"], "Mahalliy Plus")
        self.assertLessEqual(len(body["items"]), 20)
        self.assertNotIn("district", str(body["items"]).lower())

    def test_endpoint_does_not_require_business_owner_role(self):
        response = self.client.get(
            "/api/home/district-offers", headers=self.auth(self.viewer_token)
        )
        self.assertEqual(response.status_code, 200)

    def test_personalized_response_is_private_no_store_and_varies_by_auth(self):
        response = self.client.get(
            "/api/home/district-offers", headers=self.auth(self.viewer_token)
        )
        self.assertEqual(response.headers.get("cache-control"), "private, no-store")
        vary = {
            part.strip().lower()
            for part in response.headers.get("vary", "").split(",")
            if part.strip()
        }
        self.assertTrue(
            {"authorization", "x-telegram-init-data", "x-staff-token"}.issubset(vary),
            vary,
        )

    def test_hot_selector_composite_indexes_exist(self):
        conn = db()
        try:
            for table, expected in (
                ("users", ("district_key",)),
                ("items", ("business_id", "kind", "id")),
                ("listings", ("business_id", "status", "visibility", "id")),
            ):
                actual = {
                    tuple(
                        row["name"]
                        for row in conn.execute(
                            'PRAGMA index_info("%s")' % index["name"]
                        ).fetchall()
                    )
                    for index in conn.execute(
                        'PRAGMA index_list("%s")' % table
                    ).fetchall()
                }
                self.assertIn(expected, actual, (table, actual))
        finally:
            conn.close()

    def test_business_media_write_paths_reject_unsafe_references(self):
        headers = self.auth(self.owner_token)
        invalid_values = (
            "//attacker.example/image.png",
            "https://attacker.example/image.png",
            "http://attacker.example/image.png",
            "javascript:alert(1)",
            "/uploads/../secret.png",
            "/uploads/./secret.png",
        )
        for value in invalid_values:
            with self.subTest(endpoint="items", value=value):
                response = self.client.post(
                    "/api/items",
                    headers=headers,
                    json={"name": "Xavfsizlik testi", "kind": "product", "photo_file": value},
                )
                self.assertEqual(response.status_code, 400, response.text)
            with self.subTest(endpoint="listings", value=value):
                response = self.client.post(
                    "/api/listings",
                    headers=headers,
                    json={
                        "actor_type": "business",
                        "title": "Xavfsizlik testi",
                        "cat": "other",
                        "media": [{"file_id": value, "type": "photo"}],
                    },
                )
                self.assertEqual(response.status_code, 400, response.text)

    def test_business_media_write_paths_accept_server_references(self):
        headers = self.auth(self.owner_token)
        for value in ("/uploads/items/server-issued.png", "opaque_File-ID-123"):
            with self.subTest(endpoint="items", value=value):
                response = self.client.post(
                    "/api/items",
                    headers=headers,
                    json={"name": "Xavfsiz mahsulot", "kind": "product", "photo_file": value},
                )
                self.assertEqual(response.status_code, 200, response.text)
        for value in ("/uploads/listings/server-issued.png", "opaque_File-ID-456"):
            with self.subTest(endpoint="listings", value=value):
                response = self.client.post(
                    "/api/listings",
                    headers=headers,
                    json={
                        "actor_type": "business",
                        "title": "Xavfsiz e'lon",
                        "cat": "other",
                        "media": [{"file_id": value, "type": "photo"}],
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main()
