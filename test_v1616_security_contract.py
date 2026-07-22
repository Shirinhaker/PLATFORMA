import unittest
from pathlib import Path


class FrontendAssetContractTests(unittest.TestCase):
    """v1628 — frontend bitta faylda: CSS va JS index.html ichida."""

    @classmethod
    def setUpClass(cls):
        cls.index = Path("static/index.html").read_text(encoding="utf-8")
        cls.main = Path("main.py").read_text(encoding="utf-8")

    def test_frontend_is_single_file(self):
        self.assertFalse(Path("static/app.css").exists())
        self.assertFalse(Path("static/app.js").exists())
        self.assertGreater(len(self.index.encode("utf-8")), 800_000)
        self.assertNotIn('href="/app.css', self.index)
        self.assertNotIn('src="/app.js', self.index)

    def test_inline_assets_load_in_browser_order(self):
        style = self.index.index("<style>")
        head_end = self.index.index("</head>")
        body_end = self.index.index("</body>")
        inline_script = self.index.index("function openWebListings()")
        self.assertLess(style, head_end)
        self.assertLess(head_end, inline_script)
        self.assertLess(inline_script, body_end)

    def test_remaining_static_assets_keep_revalidation_cache_policy(self):
        self.assertIn('path in ("/app.css", "/app.js", "/regions.js", "/qrcode.min.js")', self.main)
        self.assertIn('"public, max-age=86400, stale-while-revalidate=604800"', self.main)
        self.assertIn("response.status_code < 400", self.main)
        self.assertIn('response.headers["Cache-Control"] = "no-store"', self.main)

    def test_release_metadata_declares_single_file_frontend(self):
        self.assertIn('APP_BUILD = "v1629"', self.main)
        self.assertIn('<!-- BUILD: v1629 -->', self.index)
        self.assertIn('"single_file_frontend_v1627": True', self.main)
        self.assertIn('"mobile_listings_button_v1628": True', self.main)


if __name__ == "__main__":
    unittest.main()
