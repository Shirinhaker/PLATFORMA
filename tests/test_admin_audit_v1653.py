import sqlite3
import unittest

from admin_audit import append_admin_audit, ensure_admin_audit_schema


class AdminAuditTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_admin_audit_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_append_records_safe_context(self):
        audit_id = append_admin_audit(
            self.conn,
            admin_tg_id=1423181561,
            action="payment.reject",
            target={"kind": "payment", "id": 15},
            before={"status": "pending"},
            after={"status": "rejected"},
            reason="Kvitansiya o‘qilmaydi",
            request_meta={"ip_hash": "abc", "user_agent": "test"},
            now=100,
        )
        row = self.conn.execute(
            "SELECT * FROM admin_audit_log WHERE id=?", (audit_id,)
        ).fetchone()
        self.assertEqual(row["action"], "payment.reject")
        self.assertEqual(row["target_kind"], "payment")
        self.assertEqual(row["target_id"], "15")
        self.assertEqual(row["reason"], "Kvitansiya o‘qilmaydi")
        self.assertEqual(row["ip_hash"], "abc")

    def test_sqlite_guards_against_update_and_delete(self):
        audit_id = append_admin_audit(
            self.conn,
            admin_tg_id=1,
            action="test",
            target={"kind": "user", "id": 1},
            before={},
            after={},
            reason="",
            request_meta={},
            now=100,
        )
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute(
                "UPDATE admin_audit_log SET action='changed' WHERE id=?",
                (audit_id,),
            )
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute(
                "DELETE FROM admin_audit_log WHERE id=?", (audit_id,)
            )

