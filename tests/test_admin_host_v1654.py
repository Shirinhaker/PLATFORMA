import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class AdminHostTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_admin_host_serves_admin_shell(self):
        response = self.client.get(
            "/",
            headers={"host": "admin.koprik.uz"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ko‘prik Admin", response.text)
        self.assertNotIn('id="homeStoryStrip"', response.text)

    def test_main_host_serves_public_site(self):
        response = self.client.get("/", headers={"host": "koprik.uz"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ko‘prik", response.text)
        self.assertNotIn("Ko‘prik Admin", response.text)

    def test_readyz_reports_private_storage_integrity_and_flags(self):
        with tempfile.TemporaryDirectory() as root, patch.object(
            main,
            "UPLOAD_DIR",
            os.path.join(root, "uploads"),
        ), patch.object(
            main,
            "PAYMENT_RECEIPT_DIR",
            os.path.join(root, "private", "payment_receipts"),
        ), patch.object(
            main,
            "feature_snapshot",
            return_value={
                "listings": False,
                "stories": False,
                "chat": False,
                "systemization": False,
            },
        ):
            os.makedirs(main.UPLOAD_DIR)
            os.makedirs(main.PAYMENT_RECEIPT_DIR)
            response = self.client.get("/readyz")
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertTrue(payload["database"])
            self.assertTrue(payload["database_integrity"])
            self.assertTrue(payload["uploads"])
            self.assertTrue(payload["payment_receipts"])
            self.assertTrue(payload["admin_assets"])
            self.assertEqual(
                payload["features"],
                {
                    "listings": False,
                    "stories": False,
                    "chat": False,
                    "systemization": False,
                },
            )
            self.assertNotIn(root, response.text)


if __name__ == "__main__":
    unittest.main()
