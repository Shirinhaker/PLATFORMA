import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from domain_config import (
    DomainPolicyMiddleware,
    configured_allowed_hosts,
    validate_domain_config,
)
from integrations import (
    IntegrationNotConfigured,
    get_provider,
    integration_status,
    register_provider,
    unregister_provider,
)


class DomainConfigTests(unittest.TestCase):
    def production_env(self):
        return {
            "APP_ENV": "production",
            "BASE_URL": "https://koprik.uz",
            "PRIMARY_DOMAIN": "koprik.uz",
            "ALLOWED_HOSTS": "koprik.uz,www.koprik.uz,*.up.railway.app",
            "CANONICAL_WWW_REDIRECT": "1",
        }

    def test_koprik_production_domain_configuration_is_valid(self):
        env = self.production_env()
        validate_domain_config(env)
        self.assertEqual(
            configured_allowed_hosts(env),
            ["koprik.uz", "www.koprik.uz", "*.up.railway.app"],
        )

    def test_production_rejects_wrong_base_host_and_wildcard(self):
        env = self.production_env()
        env["BASE_URL"] = "https://other.uz"
        env["ALLOWED_HOSTS"] = "*"
        with self.assertRaises(RuntimeError) as raised:
            validate_domain_config(env)
        message = str(raised.exception)
        self.assertIn("BASE_URL", message)
        self.assertIn("ALLOWED_HOSTS=*", message)

    def _app(self):
        app = FastAPI()
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["koprik.uz", "www.koprik.uz"],
            www_redirect=False,
        )
        app.add_middleware(
            DomainPolicyMiddleware,
            domain="koprik.uz",
            production=True,
            redirect_www=True,
        )

        @app.get("/demo")
        async def demo():
            return {"ok": True}

        return app

    def test_www_redirect_preserves_path_and_query(self):
        client = TestClient(self._app(), base_url="https://www.koprik.uz")
        response = client.get("/demo?a=1", follow_redirects=False)
        self.assertEqual(response.status_code, 308)
        self.assertEqual(response.headers["location"], "https://koprik.uz/demo?a=1")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_primary_domain_has_hsts_and_unknown_host_is_rejected(self):
        client = TestClient(self._app(), base_url="https://koprik.uz")
        response = client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["strict-transport-security"], "max-age=31536000")
        self.assertIn("object-src 'none'", response.headers["content-security-policy"])
        blocked = client.get("/demo", headers={"Host": "fake.example"})
        self.assertEqual(blocked.status_code, 400)


class IntegrationRegistryTests(unittest.TestCase):
    def tearDown(self):
        unregister_provider("sms", "fake")

    def test_all_external_integrations_are_disabled_by_default(self):
        status = integration_status({})
        self.assertEqual(set(status), {"sms", "payment", "object_storage"})
        self.assertTrue(all(not value["configured"] for value in status.values()))
        with self.assertRaises(IntegrationNotConfigured):
            get_provider("sms", {})

    def test_sms_adapter_can_be_added_without_changing_callers(self):
        calls = []

        class FakeSms:
            async def send_verification_code(self, **payload):
                calls.append(payload)

        register_provider("sms", "fake", FakeSms)
        provider = get_provider("sms", {"SMS_PROVIDER": "fake"})
        asyncio.run(
            provider.send_verification_code(
                phone="+998901234567",
                code="654321",
                purpose="login",
                expires_in=300,
            )
        )
        self.assertEqual(calls[0]["purpose"], "login")
        self.assertTrue(integration_status({"SMS_PROVIDER": "fake"})["sms"]["configured"])


class DomainIntegrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.main = (root / "main.py").read_text(encoding="utf-8")
        cls.html = (root / "static" / "index.html").read_text(encoding="utf-8")
        cls.env_example = (root / ".env.production.example").read_text(encoding="utf-8")

    def test_current_build_and_canonical_domain_are_declared(self):
        self.assertIn('APP_BUILD = "v1629"', self.main)
        self.assertIn('"domain_integration_ready_v1622": True', self.main)
        self.assertIn('<link rel="canonical" href="https://koprik.uz/"', self.html)
        self.assertIn("PRIMARY_DOMAIN=koprik.uz", self.env_example)

    def test_existing_otp_routes_use_the_sms_adapter_boundary(self):
        self.assertIn('await deliver_mobile_code(phone, code, "register")', self.main)
        self.assertIn('await deliver_mobile_code(phone, code, "login")', self.main)
        self.assertIn('provider = get_provider("sms")', self.main)

    def test_integrations_remain_disabled_until_owner_selects_providers(self):
        self.assertIn("SMS_PROVIDER=disabled", self.env_example)
        self.assertIn("PAYMENT_PROVIDER=disabled", self.env_example)
        self.assertIn("OBJECT_STORAGE_PROVIDER=disabled", self.env_example)


if __name__ == "__main__":
    unittest.main()
