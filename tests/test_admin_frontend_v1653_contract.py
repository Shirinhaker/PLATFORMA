import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AdminFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "admin" / "index.html").read_text("utf-8")
        cls.js = (ROOT / "admin" / "app.js").read_text("utf-8")
        cls.css = (ROOT / "admin" / "styles.css").read_text("utf-8")

    def test_seven_admin_sections_exist(self):
        for key in (
            "dashboard", "payments", "pricing", "accounts",
            "content", "reports", "audit",
        ):
            self.assertIn(f'data-admin-page="{key}"', self.html)

    def test_admin_uses_only_admin_api_and_cookie_session(self):
        self.assertIn("/api/admin/auth/me", self.js)
        self.assertIn("/api/admin/dashboard", self.js)
        self.assertNotIn("Authorization: Bearer", self.js)

    def test_payment_review_and_receipt_controls_exist(self):
        self.assertIn("paymentReceiptDialog", self.html)
        self.assertIn("/receipt", self.js)
        self.assertIn("/approve", self.js)
        self.assertIn("/reject", self.js)

    def test_mobile_breakpoint_and_drawer_exist(self):
        self.assertIn("@media (max-width: 760px)", self.css)
        self.assertIn('id="adminNavToggle"', self.html)

    def test_main_site_is_not_linked_from_admin(self):
        self.assertNotIn('href="/"', self.html)

