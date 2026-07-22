import sqlite3
import unittest

from subscriptions import (
    SubscriptionValidationError,
    activate_demo_subscription,
    business_has_entitlement,
    current_business_subscription,
    home_nearby_eligible_plan_codes,
    init_subscription_schema,
    subscription_entitlements,
    subscription_payload,
)


class BusinessSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_subscription_schema(self.conn)
        self.now = 1_704_067_200  # 2024-01-01 00:00:00 UTC

    def tearDown(self):
        self.conn.close()

    def test_schema_and_default_free(self):
        tables = {
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("business_subscriptions", tables)

        payload = subscription_payload(self.conn, 41, now=self.now)
        self.assertEqual(payload["current"]["plan_code"], "free")
        self.assertEqual(payload["current"]["duration_months"], 0)
        self.assertEqual(payload["current"]["expires_at"], 0)
        self.assertTrue(payload["current"]["is_virtual"])
        self.assertEqual(payload["history"], [])

    def test_plan_entitlements_are_cumulative_and_do_not_control_stories(self):
        free = subscription_entitlements("free")
        plus = subscription_entitlements("plus")
        pro = subscription_entitlements("pro")

        for features in (free, plus, pro):
            self.assertTrue(features["unlimited_items"])
            self.assertNotIn("unlimited_stories", features)
            self.assertNotIn("regional_stories_eligible", features)
        self.assertFalse(free["home_nearby_eligible"])
        self.assertTrue(plus["home_nearby_eligible"])
        self.assertFalse(plus["map_marker_eligible"])
        self.assertTrue(pro["home_nearby_eligible"])
        self.assertTrue(pro["map_marker_eligible"])

    def test_invalid_plan_and_duration_are_rejected(self):
        cases = (("gold", 1), ("free", 1), ("plus", 0), ("plus", 2), ("pro", 6))
        for plan_code, duration in cases:
            with self.subTest(plan_code=plan_code, duration=duration):
                with self.assertRaises(SubscriptionValidationError):
                    activate_demo_subscription(
                        self.conn, 7, plan_code, duration, now=self.now
                    )

    def test_duration_requires_an_exact_json_integer(self):
        invalid_durations = (True, False, 1.9, float("inf"), float("-inf"), "1", "3", None)
        for duration in invalid_durations:
            with self.subTest(duration=repr(duration)):
                with self.assertRaises(SubscriptionValidationError):
                    activate_demo_subscription(
                        self.conn, 7, "plus", duration, now=self.now
                    )

    def test_no_expiry_current_subscription_read_does_not_open_a_transaction(self):
        activate_demo_subscription(self.conn, 7, "plus", 1, now=self.now)
        self.assertFalse(self.conn.in_transaction)

        current = current_business_subscription(self.conn, 7, now=self.now + 1)

        self.assertEqual(current["plan_code"], "plus")
        self.assertFalse(self.conn.in_transaction)

    def test_expired_cleanup_commits_before_returning_virtual_free(self):
        paid = activate_demo_subscription(self.conn, 7, "plus", 1, now=self.now)
        self.assertFalse(self.conn.in_transaction)

        current = current_business_subscription(
            self.conn, 7, now=paid["current"]["expires_at"] + 1
        )

        self.assertEqual(current["plan_code"], "free")
        self.assertFalse(self.conn.in_transaction)
        status = self.conn.execute(
            "SELECT status FROM business_subscriptions WHERE id=?", (paid["current"]["id"],)
        ).fetchone()["status"]
        self.assertEqual(status, "expired")

    def test_activation_uses_one_immediate_transaction_for_expired_switch(self):
        self.conn.execute(
            "INSERT INTO business_subscriptions("
            "business_id,plan_code,duration_months,starts_at,expires_at,status,is_demo,created_at"
            ") VALUES(?,?,?,?,?,'active',1,?)",
            (7, "plus", 1, self.now - 100, self.now - 1, self.now - 100),
        )
        self.conn.commit()
        statements = []
        self.conn.set_trace_callback(statements.append)

        activated = activate_demo_subscription(self.conn, 7, "pro", 3, now=self.now)

        self.conn.set_trace_callback(None)
        self.assertEqual(activated["current"]["plan_code"], "pro")
        self.assertEqual(
            [statement for statement in statements if statement.upper().startswith("BEGIN")],
            ["BEGIN IMMEDIATE"],
        )
        self.assertFalse(self.conn.in_transaction)

    def test_home_nearby_eligibility_source_is_derived_from_plan_features(self):
        self.assertEqual(home_nearby_eligible_plan_codes(), ("plus", "pro"))
        self.assertNotIn("free", home_nearby_eligible_plan_codes())

    def test_same_paid_plan_extends_from_existing_expiry(self):
        first = activate_demo_subscription(self.conn, 7, "plus", 1, now=self.now)
        second = activate_demo_subscription(
            self.conn, 7, "plus", 3, now=self.now + 60
        )

        self.assertEqual(second["current"]["id"], first["current"]["id"])
        self.assertEqual(
            second["current"]["starts_at"], first["current"]["starts_at"]
        )
        self.assertGreater(
            second["current"]["expires_at"], first["current"]["expires_at"]
        )
        self.assertEqual(second["current"]["duration_months"], 4)
        self.assertEqual(second["history"], [])

    def test_switch_supersedes_previous_and_keeps_businesses_isolated(self):
        activate_demo_subscription(self.conn, 7, "plus", 1, now=self.now)
        switched = activate_demo_subscription(
            self.conn, 7, "pro", 3, now=self.now + 60
        )
        other = subscription_payload(self.conn, 8, now=self.now + 60)

        self.assertEqual(switched["current"]["plan_code"], "pro")
        self.assertEqual(len(switched["history"]), 1)
        self.assertEqual(switched["history"][0]["plan_code"], "plus")
        self.assertEqual(switched["history"][0]["status"], "superseded")
        self.assertEqual(other["current"]["plan_code"], "free")
        self.assertEqual(other["history"], [])

    def test_expired_paid_plan_returns_to_virtual_free_and_keeps_history(self):
        paid = activate_demo_subscription(self.conn, 7, "pro", 1, now=self.now)
        after_expiry = subscription_payload(
            self.conn, 7, now=paid["current"]["expires_at"] + 1
        )

        self.assertEqual(after_expiry["current"]["plan_code"], "free")
        self.assertTrue(after_expiry["current"]["is_virtual"])
        self.assertEqual(after_expiry["history"][0]["status"], "expired")

    def test_switch_to_free_is_perpetual_and_not_duplicated(self):
        activate_demo_subscription(self.conn, 7, "plus", 1, now=self.now)
        free = activate_demo_subscription(self.conn, 7, "free", 0, now=self.now + 5)
        repeated = activate_demo_subscription(
            self.conn, 7, "free", 0, now=self.now + 10
        )

        self.assertEqual(free["current"]["plan_code"], "free")
        self.assertEqual(free["current"]["expires_at"], 0)
        self.assertFalse(free["current"]["is_virtual"])
        self.assertEqual(repeated["current"]["id"], free["current"]["id"])
        count = self.conn.execute(
            "SELECT COUNT(*) AS c FROM business_subscriptions WHERE business_id=7"
        ).fetchone()["c"]
        self.assertEqual(count, 2)

    def test_payload_contains_plan_catalog_without_prices(self):
        payload = subscription_payload(self.conn, 7, now=self.now)
        self.assertEqual(payload["durations"], [1, 3, 12])
        self.assertTrue(payload["demo_mode"])
        self.assertEqual([plan["code"] for plan in payload["plans"]], ["free", "plus", "pro"])
        self.assertNotIn("price", str(payload).lower())

    def test_future_visibility_checks_use_one_entitlement_helper(self):
        self.assertFalse(
            business_has_entitlement(
                self.conn, 7, "home_nearby_eligible", now=self.now
            )
        )
        activate_demo_subscription(self.conn, 7, "pro", 1, now=self.now)
        self.assertTrue(
            business_has_entitlement(
                self.conn, 7, "home_nearby_eligible", now=self.now
            )
        )
        self.assertTrue(
            business_has_entitlement(
                self.conn, 7, "map_marker_eligible", now=self.now
            )
        )
        self.assertFalse(
            business_has_entitlement(self.conn, 7, "unknown_feature", now=self.now)
        )


if __name__ == "__main__":
    unittest.main()
