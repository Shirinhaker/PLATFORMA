import sqlite3
import unittest

from moderation import (
    account_restrictions,
    clear_account_restriction,
    content_is_public,
    ensure_moderation_schema,
    set_account_restriction,
    set_content_visibility,
)


class ModerationDomainTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_moderation_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_two_account_restrictions_are_independent(self):
        set_account_restriction(
            self.conn, "business", 20, "content_hidden",
            1423181561, "Tekshiruv", now=100,
        )
        set_account_restriction(
            self.conn, "business", 20, "account_blocked",
            1423181561, "Soxta profil", now=101,
        )
        clear_account_restriction(
            self.conn, "business", 20, "content_hidden",
            1423181561, "Kontent tekshirildi", now=102,
        )
        self.assertEqual(
            account_restrictions(self.conn, "business", 20),
            {"account_blocked"},
        )

    def test_latest_content_state_controls_public_visibility(self):
        self.assertTrue(content_is_public(self.conn, "product", 7))
        set_content_visibility(
            self.conn, "product", 7, "hidden", 1, "Tekshiruv", now=100
        )
        self.assertFalse(content_is_public(self.conn, "product", 7))
        set_content_visibility(
            self.conn, "product", 7, "visible", 1, "Tiklandi", now=101
        )
        self.assertTrue(content_is_public(self.conn, "product", 7))
