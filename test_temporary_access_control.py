import hashlib
import os
import shutil
import sqlite3
import tempfile
import time
import unittest

from location_keys import canonical_district_key, safe_district_display

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


TEST_ROOT = tempfile.mkdtemp(prefix="koprik-location-keys-")
os.environ["DB_PATH"] = os.path.join(TEST_ROOT, "platforma.db")
os.environ["TEST_MODE"] = "1"

from database import db, ensure_user_district_keys, init_db
import access_config

try:
    from fastapi.testclient import TestClient
    from main import app
except ModuleNotFoundError:
    TestClient = None
    app = None


class LocationKeyUnitTests(unittest.TestCase):
    def test_canonical_key_strips_district_suffixes_and_apostrophe_aliases(self):
        self.assertEqual(canonical_district_key("Yunusobod"), "yunusobod")
        self.assertEqual(canonical_district_key("  YUNUSOBOD TUMANI "), "yunusobod")
        self.assertEqual(canonical_district_key("Yunusobod District"), "yunusobod")
        self.assertEqual(canonical_district_key("Yunusobod rayoni"), "yunusobod")
        self.assertEqual(canonical_district_key("Andijon shahri"), "andijon")
        self.assertEqual(canonical_district_key("Bo'stonliq (Gazalkent)"), "bostonliq")
        self.assertEqual(canonical_district_key("Sho\u2018rchi tumani"), "shorchi")
        self.assertEqual(canonical_district_key("SHO'RCHI"), "shorchi")

    def test_placeholder_and_free_form_address_cannot_be_districts(self):
        self.assertEqual(safe_district_display("Joylashuvim"), "")
        self.assertEqual(safe_district_display("Joriy manzilim"), "")
        self.assertEqual(safe_district_display("Joylashuvim tumani"), "")
        self.assertEqual(safe_district_display("Random free form place"), "")
        self.assertEqual(safe_district_display("Noma'lum"), "")
        self.assertEqual(safe_district_display("Aniq manzil topilmadi"), "")
        self.assertEqual(safe_district_display("Amir Temur ko'chasi, 15"), "")
        self.assertEqual(canonical_district_key("Yunusobod tumani, Toshkent shahri"), "")

    def test_backend_catalog_does_not_parse_frontend_regions_javascript(self):
        with open("location_keys.py", encoding="utf-8") as source:
            implementation = source.read()
        self.assertNotIn("regions.js", implementation)
        self.assertNotIn("from pathlib import Path", implementation)

    def test_known_administrative_center_alias_maps_to_its_district(self):
        self.assertEqual(canonical_district_key("Gazalkent"), "bostonliq")
        self.assertEqual(canonical_district_key("Oqtosh"), "narpay")

    def test_migration_backfills_key_without_changing_display_and_adds_index(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, district TEXT DEFAULT '')")
        conn.execute("INSERT INTO users(id,district) VALUES(1,'Yunusobod tumani')")
        conn.execute("INSERT INTO users(id,district) VALUES(2,'Joylashuvim')")

        ensure_user_district_keys(conn)

        rows = conn.execute("SELECT district,district_key FROM users ORDER BY id").fetchall()
        self.assertEqual([(row["district"], row["district_key"]) for row in rows], [
            ("Yunusobod tumani", "yunusobod"),
            ("Joylashuvim", ""),
        ])
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(users)")}
        self.assertIn("idx_users_district_key", indexes)
        conn.close()

    def test_migration_accepts_a_plain_sqlite_connection(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, district TEXT DEFAULT '')")
        conn.execute("INSERT INTO users(id,district) VALUES(1,'Yunusobod tumani')")

        ensure_user_district_keys(conn)

        self.assertEqual(conn.execute("SELECT district_key FROM users WHERE id=1").fetchone()[0], "yunusobod")
        conn.close()

    def test_existing_unmarked_column_is_backfilled_once_without_second_scan(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE users("
            "id INTEGER PRIMARY KEY,district TEXT DEFAULT '',district_key TEXT DEFAULT '')"
        )
        conn.execute(
            "INSERT INTO users(id,district,district_key) "
            "VALUES(1,'Yunusobod tumani','')"
        )

        ensure_user_district_keys(conn)
        self.assertEqual(
            conn.execute("SELECT district_key FROM users WHERE id=1").fetchone()[0],
            "yunusobod",
        )

        statements = []
        conn.set_trace_callback(statements.append)
        try:
            ensure_user_district_keys(conn)
        finally:
            conn.set_trace_callback(None)
        normalized = [" ".join(statement.upper().split()) for statement in statements]
        self.assertFalse(
            any("SELECT ID,DISTRICT FROM USERS" in statement for statement in normalized),
            normalized,
        )
        self.assertFalse(
            any("UPDATE USERS SET DISTRICT_KEY" in statement for statement in normalized),
            normalized,
        )
        conn.close()

    def test_gps_frontend_does_not_use_address_or_placeholder_as_district(self):
        html = frontend_source()
        self.assertNotIn("district:(tuman||place)", html)
        self.assertNotIn('district:"Joylashuvim"', html)
        self.assertIn("district:tuman", html)


@unittest.skipUnless(TestClient is not None, "fastapi test dependencies are not installed")
class LocationKeyApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_restricted = access_config.PROJECT_ACCESS_RESTRICTED
        access_config.PROJECT_ACCESS_RESTRICTED = False
        init_db()
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        cls.now = int(time.time())
        conn = db()

        def add_user(login, role="user"):
            conn.execute(
                "INSERT INTO users(login,pass_hash,role,name,created_at) VALUES(?,?,?,?,?)",
                (login, "x", role, login, cls.now),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        def add_session(user_id, token):
            conn.execute(
                "INSERT INTO mobile_sessions(user_id,token_hash,created_at,expires_at,last_used_at,revoked_at) "
                "VALUES(?,?,?,?,?,0)",
                (user_id, hashlib.sha256(token.encode()).hexdigest(), cls.now, cls.now + 3600, cls.now),
            )

        cls.user_id = add_user("location-user")
        cls.user_token = "location-user-token"
        add_session(cls.user_id, cls.user_token)

        cls.business_user_id = add_user("location-business-owner", role="business")
        cls.business_token = "location-business-token"
        add_session(cls.business_user_id, cls.business_token)
        conn.execute(
            "INSERT INTO businesses(user_id,name,status,created_at) VALUES(?,?,?,?)",
            (cls.business_user_id, "Joy sinov biznesi", "active", cls.now),
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        access_config.PROJECT_ACCESS_RESTRICTED = cls.original_restricted
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    @staticmethod
    def auth(token):
        return {"Authorization": "Bearer " + token}

    def test_manual_profile_keeps_display_and_stores_canonical_key(self):
        response = self.client.put(
            "/api/profile", headers=self.auth(self.user_token), json={"district": "Yunusobod"}
        )
        self.assertEqual(response.status_code, 200)
        conn = db()
        row = conn.execute("SELECT district,district_key FROM users WHERE id=?", (self.user_id,)).fetchone()
        conn.close()
        self.assertEqual((row["district"], row["district_key"]), ("Yunusobod", "yunusobod"))

    def test_invalid_manual_district_is_rejected_without_erasing_existing_value(self):
        conn = db()
        conn.execute(
            "UPDATE users SET district='Yunusobod',district_key='yunusobod' WHERE id=?",
            (self.user_id,),
        )
        conn.commit()
        conn.close()
        response = self.client.put(
            "/api/profile", headers=self.auth(self.user_token), json={"district": "Joylashuvim"}
        )
        self.assertEqual(response.status_code, 400)
        conn = db()
        row = conn.execute("SELECT district,district_key FROM users WHERE id=?", (self.user_id,)).fetchone()
        conn.close()
        self.assertEqual((row["district"], row["district_key"]), ("Yunusobod", "yunusobod"))

    def test_explicit_empty_district_still_clears_location(self):
        response = self.client.put(
            "/api/profile", headers=self.auth(self.user_token), json={"district": ""}
        )
        self.assertEqual(response.status_code, 200)
        conn = db()
        row = conn.execute("SELECT district,district_key FROM users WHERE id=?", (self.user_id,)).fetchone()
        conn.close()
        self.assertEqual((row["district"], row["district_key"]), ("", ""))

    def test_business_geocode_keeps_geocoded_display_and_stores_same_key(self):
        response = self.client.put(
            "/api/business", headers=self.auth(self.business_token), json={"lat": 41.35, "lng": 69.29}
        )
        self.assertEqual(response.status_code, 200)
        conn = db()
        row = conn.execute(
            "SELECT district,district_key FROM users WHERE id=?", (self.business_user_id,)
        ).fetchone()
        conn.close()
        self.assertEqual((row["district"], row["district_key"]), ("Yunusobod tumani", "yunusobod"))


if __name__ == "__main__":
    unittest.main()
