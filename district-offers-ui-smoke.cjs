import sqlite3
import unittest

import district_offers
from district_offers import (
    _stable_offset,
    district_offers_payload,
    normalize_district,
    offer_time_slot,
)
from subscriptions import PLAN_FEATURES, init_subscription_schema


class DistrictOffersTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE users(
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                district TEXT DEFAULT '',
                district_key TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE businesses(
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                yon TEXT DEFAULT '',
                logo_file TEXT DEFAULT '',
                logo_x REAL DEFAULT 50,
                logo_y REAL DEFAULT 50,
                logo_zoom REAL DEFAULT 1,
                status TEXT DEFAULT 'active'
            );
            CREATE TABLE items(
                id INTEGER PRIMARY KEY,
                business_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price TEXT DEFAULT '',
                unit TEXT DEFAULT 'dona',
                kind TEXT DEFAULT 'product',
                photo_file TEXT DEFAULT '',
                stock_type TEXT DEFAULT 'ready_food'
            );
            CREATE TABLE listings(
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                business_id INTEGER,
                cat TEXT DEFAULT '',
                title TEXT NOT NULL,
                price TEXT DEFAULT '',
                visibility TEXT DEFAULT 'all',
                status TEXT DEFAULT 'active',
                created_at INTEGER DEFAULT 0
            );
            CREATE TABLE listing_media(
                id INTEGER PRIMARY KEY,
                listing_id INTEGER NOT NULL,
                tg_file_id TEXT NOT NULL,
                mtype TEXT DEFAULT 'photo',
                pos INTEGER DEFAULT 0
            );
            """
        )
        init_subscription_schema(self.conn)
        self.now = 1_704_067_200
        self.conn.execute(
            "INSERT INTO users(id,name,district,district_key) VALUES(?,?,?,?)",
            (1, "Ko'ruvchi", " Sho‘rchi ", "shorchi"),
        )
        self.viewer_id = 1

        self.plus_business_id = self._business(10, "Plus market")
        self.pro_business_id = self._business(11, "Pro xizmat", plan="pro")
        self._business(12, "Yettinchi", plan="plus")
        self._business(13, "Sakkizinchi", plan="pro")
        self._business(14, "To'qqizinchi", plan="plus")
        self._business(15, "O'ninchi", plan="pro")
        self._business(16, "O'n birinchi", plan="plus")
        self.free_business_id = self._business(17, "Bepul", plan="free")
        self.other_district_business_id = self._business(
            18, "Boshqa tuman", district="Denov", plan="plus"
        )
        self.inactive_business_id = self._business(
            19, "Nofaol", status="inactive", plan="pro"
        )

        for business_id in tuple(range(10, 15)) + (16, 17, 18, 19):
            self.conn.execute(
                "INSERT INTO items(business_id,name,price,unit,kind,photo_file) "
                "VALUES(?,?,?,?,?,?)",
                (business_id, "Taklif %s" % business_id, "2500000", "dona", "product", ""),
            )

        self.public_listing_id = self._listing(100, self.plus_business_id, "Ommaviy e'lon")
        self.private_listing_id = self._listing(
            101, self.plus_business_id, "Yopiq e'lon", visibility="own"
        )
        self.inactive_listing_id = self._listing(
            102, self.plus_business_id, "Nofaol e'lon", status="inactive"
        )
        self.null_visibility_listing_id = self._listing(
            103, self.plus_business_id, "Noaniq ko'rinish", visibility=None
        )
        self.conn.execute(
            "INSERT INTO listing_media(listing_id,tg_file_id,mtype,pos) VALUES(?,?,?,?)",
            (self.public_listing_id, "listing-photo", "photo", 0),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _business(
        self,
        business_id,
        name,
        district="SHO'RCHI",
        status="active",
        plan="plus",
        district_key=None,
        expires_at=None,
    ):
        owner_id = business_id + 100
        self.conn.execute(
            "INSERT INTO users(id,name,district,district_key) VALUES(?,?,?,?)",
            (
                owner_id,
                "Egasi %s" % business_id,
                district,
                normalize_district(district) if district_key is None else district_key,
            ),
        )
        self.conn.execute(
            "INSERT INTO businesses(id,user_id,name,status) VALUES(?,?,?,?)",
            (business_id, owner_id, name, status),
        )
        self.conn.execute(
            "INSERT INTO business_subscriptions("
            "business_id,plan_code,duration_months,starts_at,expires_at,status,is_demo,created_at"
            ") VALUES(?,?,?,?,?,'active',1,?)",
            (
                business_id,
                plan,
                1 if plan != "free" else 0,
                self.now - 10,
                self.now + 10_000 if expires_at is None else expires_at,
                self.now,
            ),
        )
        return business_id

    def _listing(self, listing_id, business_id, title, visibility="all", status="active"):
        self.conn.execute(
            "INSERT INTO listings(id,user_id,business_id,title,price,visibility,status) "
            "VALUES(?,?,?,?,?,?,?)",
            (listing_id, business_id + 100, business_id, title, "2500000", visibility, status),
        )
        return listing_id

    def test_normalize_district_handles_case_spaces_and_apostrophes(self):
        self.assertEqual(normalize_district("  Sho‘rchi  "), "shorchi")
        self.assertEqual(normalize_district("SHO'RCHI"), "shorchi")

    def test_normalize_district_strips_known_suffix_and_rejects_placeholders(self):
        self.assertEqual(normalize_district("Yunusobod tumani"), "yunusobod")
        self.assertEqual(normalize_district("Yunusobod"), "yunusobod")
        self.assertEqual(normalize_district("Joylashuvim"), "")
        self.assertEqual(normalize_district("Amir Temur ko'chasi, 12-uy"), "")

    def test_missing_user_or_district_requests_district(self):
        self.assertEqual(
            district_offers_payload(self.conn, None, now=self.now),
            {"needs_district": True, "slot": self.now // 1800, "items": []},
        )

    def test_only_same_district_active_paid_businesses_are_returned(self):
        payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
        ids = {item["business_id"] for item in payload["items"]}
        self.assertIn(self.plus_business_id, ids)
        self.assertIn(self.pro_business_id, ids)
        self.assertNotIn(self.free_business_id, ids)
        self.assertNotIn(self.other_district_business_id, ids)
        self.assertNotIn(self.inactive_business_id, ids)

    def test_canonical_key_matches_display_suffix_aliases(self):
        self.conn.execute(
            "UPDATE users SET district=?,district_key=? WHERE id=?",
            ("Yunusobod", "yunusobod", self.viewer_id),
        )
        alias_business = self._business(
            30,
            "Yunusobod taklifi",
            district="Yunusobod tumani",
            district_key="yunusobod",
        )
        self.conn.execute(
            "INSERT INTO items(business_id,name,kind) VALUES(?,?,?)",
            (alias_business, "Alias mahsulot", "product"),
        )
        payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
        self.assertEqual([item["business_id"] for item in payload["items"]], [alias_business])

    def test_expired_subscription_is_excluded(self):
        expired_id = self._business(
            31, "Muddati tugagan", plan="pro", expires_at=self.now
        )
        self.conn.execute(
            "INSERT INTO items(business_id,name,kind) VALUES(?,?,?)",
            (expired_id, "Eski mahsulot", "product"),
        )
        ids = {
            item["business_id"]
            for item in district_offers_payload(
                self.conn, self.viewer_id, now=self.now
            )["items"]
        }
        self.assertNotIn(expired_id, ids)

    def test_response_has_at_most_twenty_unique_businesses(self):
        payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
        ids = [item["business_id"] for item in payload["items"]]
        self.assertLessEqual(len(ids), 20)
        self.assertEqual(len(ids), len(set(ids)))

    def test_private_and_inactive_listings_are_excluded(self):
        payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
        listing_ids = {x["content_id"] for x in payload["items"] if x["kind"] == "listing"}
        self.assertNotIn(self.private_listing_id, listing_ids)
        self.assertNotIn(self.inactive_listing_id, listing_ids)

    def test_null_visibility_listing_is_excluded(self):
        payload = district_offers_payload(self.conn, self.viewer_id, now=self.now + 5400)
        listing_ids = {x["content_id"] for x in payload["items"] if x["kind"] == "listing"}
        self.assertNotIn(self.null_visibility_listing_id, listing_ids)

    def test_same_slot_is_stable_and_next_slot_rotates(self):
        first = district_offers_payload(self.conn, self.viewer_id, now=self.now)
        same = district_offers_payload(self.conn, self.viewer_id, now=self.now + 1799)
        later = district_offers_payload(self.conn, self.viewer_id, now=self.now + 1800)
        self.assertEqual(first, same)
        self.assertNotEqual(
            [x["business_id"] for x in first["items"]],
            [x["business_id"] for x in later["items"]],
        )

    def test_contentless_businesses_do_not_bias_twenty_item_rotation(self):
        for business_id in (20, 21, 22, 23, 24, 25, 26, 27, 28):
            self._business(business_id, "Biznes %s" % business_id)
            if business_id not in (21, 24):
                self.conn.execute(
                    "INSERT INTO items(business_id,name,kind) VALUES(?,?,?)",
                    (business_id, "Taklif %s" % business_id, "product"),
                )
        eligible = [10, 11, 12, 13, 14, 16, 20, 22, 23, 25, 26, 27, 28]
        base_slot = offer_time_slot(self.now)
        for delta in range(4):
            slot = base_slot + delta
            offset = _stable_offset("shorchi", slot, len(eligible))
            expected = [
                eligible[(offset + index) % len(eligible)]
                for index in range(min(20, len(eligible)))
            ]
            actual = [
                item["business_id"]
                for item in district_offers_payload(
                    self.conn, self.viewer_id, now=slot * 1800
                )["items"]
            ]
            self.assertEqual(actual, expected)

    def test_product_service_and_listing_kinds_cycle(self):
        self.conn.execute(
            "INSERT INTO items(business_id,name,kind) VALUES(?,?,?)",
            (self.plus_business_id, "Yetkazib berish", "service"),
        )
        kinds = []
        for delta in range(3):
            payload = district_offers_payload(
                self.conn, self.viewer_id, now=self.now + delta * 1800
            )
            chosen = next(
                item
                for item in payload["items"]
                if item["business_id"] == self.plus_business_id
            )
            kinds.append(chosen["kind"])
        self.assertEqual(set(kinds), {"product", "service", "listing"})

    def test_media_reference_allowlist_and_serialization_boundary(self):
        validator = getattr(district_offers, "safe_media_reference", None)
        self.assertIsNotNone(validator)
        for value in (
            "//attacker.example/pixel.png",
            "https://attacker.example/pixel.png",
            "http://attacker.example/pixel.png",
            "javascript:alert(1)",
            "/uploads/../secret.png",
            "/uploads/./secret.png",
        ):
            with self.subTest(value=value):
                self.assertEqual(validator(value), "")
        for value in ("/uploads/items/issued.png", "opaque_File-ID-123"):
            with self.subTest(value=value):
                self.assertEqual(validator(value), value)

        self.conn.execute("UPDATE businesses SET logo_file='//attacker.example/logo.png'")
        self.conn.execute("UPDATE items SET photo_file='https://attacker.example/item.png'")
        self.conn.execute(
            "UPDATE listing_media SET tg_file_id='javascript:alert(1)'"
        )
        payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
        for item in payload["items"]:
            self.assertEqual(item["business_logo"], "")
            self.assertEqual(item["image"], "")

    def test_listing_image_uses_first_valid_bounded_photo(self):
        self.conn.execute(
            "UPDATE listing_media SET tg_file_id='//attacker.example/first.png' "
            "WHERE listing_id=?",
            (self.public_listing_id,),
        )
        self.conn.execute(
            "INSERT INTO listing_media(listing_id,tg_file_id,mtype,pos) "
            "VALUES(?,?,?,?)",
            (self.public_listing_id, "second-valid-photo", "photo", 1),
        )
        statements = []
        self.conn.set_trace_callback(statements.append)
        try:
            image = district_offers._listing_image(
                self.conn, self.public_listing_id
            )
        finally:
            self.conn.set_trace_callback(None)
        self.assertEqual(image, "second-valid-photo")
        media_reads = [
            " ".join(statement.upper().split())
            for statement in statements
            if "FROM LISTING_MEDIA" in statement.upper()
        ]
        self.assertEqual(len(media_reads), 1)
        self.assertIn("LIMIT 10", media_reads[0])

    def test_catalog_rows_are_not_materialized_by_selector(self):
        self.conn.executemany(
            "INSERT INTO items(business_id,name,kind) VALUES(?,?,?)",
            [
                (self.plus_business_id, "Katalog %s" % index, "product")
                for index in range(1000)
            ],
        )
        statements = []
        self.conn.set_trace_callback(statements.append)
        try:
            district_offers_payload(self.conn, self.viewer_id, now=self.now)
        finally:
            self.conn.set_trace_callback(None)
        catalog_reads = [
            " ".join(statement.upper().split())
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
            and (" FROM ITEMS " in statement.upper() or " FROM LISTINGS " in statement.upper())
        ]
        self.assertTrue(catalog_reads)
        self.assertTrue(
            all("COUNT(" in statement or "LIMIT 1" in statement for statement in catalog_reads),
            catalog_reads,
        )

    def test_only_rotated_candidate_rows_are_materialized(self):
        for business_id in range(100, 140):
            self._business(business_id, "Katta tuman %s" % business_id)
            self.conn.execute(
                "INSERT INTO items(business_id,name,kind) VALUES(?,?,?)",
                (business_id, "Taklif %s" % business_id, "product"),
            )
        statements = []
        self.conn.set_trace_callback(statements.append)
        try:
            payload = district_offers_payload(self.conn, self.viewer_id, now=self.now)
        finally:
            self.conn.set_trace_callback(None)
        self.assertEqual(len(payload["items"]), 20)
        candidate_selects = [
            " ".join(statement.upper().split())
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
            and "FROM USERS U JOIN BUSINESSES B" in " ".join(statement.upper().split())
        ]
        self.assertTrue(candidate_selects, statements)
        self.assertTrue(
            all(
                statement.startswith("SELECT COUNT(") or " LIMIT " in statement
                for statement in candidate_selects
            ),
            candidate_selects,
        )

    def test_candidate_query_uses_indexed_district_key(self):
        statements = []
        self.conn.set_trace_callback(statements.append)
        try:
            district_offers_payload(self.conn, self.viewer_id, now=self.now)
        finally:
            self.conn.set_trace_callback(None)
        candidate_sql = "\n".join(statements).lower()
        self.assertIn("district_key", candidate_sql)
        self.assertIn("u.district_key=", candidate_sql.replace(" ", ""))

    def test_plan_eligibility_is_derived_from_plan_features(self):
        original = PLAN_FEATURES["plus"]["home_nearby_eligible"]
        PLAN_FEATURES["plus"]["home_nearby_eligible"] = False
        try:
            ids = {
                item["business_id"]
                for item in district_offers_payload(
                    self.conn, self.viewer_id, now=self.now
                )["items"]
            }
        finally:
            PLAN_FEATURES["plus"]["home_nearby_eligible"] = original
        self.assertNotIn(self.plus_business_id, ids)
        self.assertIn(self.pro_business_id, ids)

    def test_offer_time_slot_uses_thirty_minute_buckets(self):
        self.assertEqual(offer_time_slot(self.now), self.now // 1800)


if __name__ == "__main__":
    unittest.main()
