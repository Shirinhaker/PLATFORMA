from pathlib import Path
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class V1616SecurityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = Path("main.py").read_text(encoding="utf-8")
        cls.html = frontend_source()

    def test_test_mode_never_returns_otp_to_http_client(self):
        self.assertNotIn('"test_code": code', self.main)
        self.assertNotIn("/api/_test/last_code", self.main)
        self.assertNotIn("_test_codes", self.main)
        self.assertNotIn("r.test_code", self.html)

    def test_frontend_sends_exactly_one_authentication_mechanism(self):
        start = self.html.index("function apiHeaders(")
        end = self.html.index("function api(", start)
        body = self.html[start:end]
        self.assertIn("if(STAFF_TOKEN)", body)
        self.assertIn("else if(MOBILE_TOKEN)", body)
        self.assertIn("else if(INIT_DATA)", body)

    def test_build_is_v1628_and_preserves_product_constraints(self):
        self.assertIn('APP_BUILD = "v1629"', self.main)
        self.assertIn('<!-- BUILD: v1629 -->', self.html)
        self.assertIn('"stories_subscription_independent": True', self.main)
        self.assertIn('"pro_follow_map": True', self.main)
        self.assertIn('"temporary_privileged_access_only": False', self.main)


if __name__ == "__main__":
    unittest.main()
