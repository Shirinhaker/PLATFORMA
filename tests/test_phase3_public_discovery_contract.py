import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase3PublicDiscoveryContractTests(unittest.TestCase):
    def test_public_search_contract_is_safe_and_bounded(self):
        schemas = (
            ROOT / "backend/app/public_discovery/schemas.py"
        ).read_text(encoding="utf-8")
        router = (
            ROOT / "backend/app/public_discovery/router.py"
        ).read_text(encoding="utf-8")
        config = (ROOT / "backend/app/core/config.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('prefix="/api/v1/public"', router)
        self.assertIn('@router.get("/search"', router)
        self.assertIn("page_size: int = Field(default=20, ge=1, le=50)", schemas)
        self.assertIn("public_search_cache_ttl_seconds", config)
        self.assertIn("default=30", config)

        public_item = schemas.split(
            "class PublicSearchItem(BaseModel):", maxsplit=1
        )[1].split("class PublicSearchResponse", maxsplit=1)[0]
        for expected in (
            "kind:",
            "public_id:",
            "name:",
            "public_username:",
            "description:",
            "direction:",
            "activity_type:",
            "region:",
            "district:",
            "mahalla:",
            "image_url:",
        ):
            self.assertIn(expected, public_item)

        for forbidden in (
            "phone:",
            "latitude:",
            "longitude:",
            "pay_card:",
            "pay_holder:",
            "tax_id:",
            "object_key:",
        ):
            self.assertNotIn(forbidden, public_item)

    def test_public_catalog_uses_live_api_without_requiring_a_session(self):
        app = (ROOT / "frontend/src/app/App.tsx").read_text(encoding="utf-8")
        client = (ROOT / "frontend/src/api/client.ts").read_text(
            encoding="utf-8"
        )
        catalog = (
            ROOT / "frontend/src/legacy/public/CatalogScreen.tsx"
        ).read_text(encoding="utf-8")
        category = (
            ROOT / "frontend/src/legacy/public/CategoryScreen.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("/api/v1/public/search", client)
        self.assertIn("searchPublic", app)
        self.assertIn("searchPublic", catalog)
        self.assertIn("searchPublic", category)
        self.assertIn("renderPublicContent", app)
        self.assertIn("failed && accountView", app)

    def test_ci_and_runbook_cover_staging_and_preserve_legacy_production(self):
        verifier = (ROOT / "scripts/verify_phase3a.py").read_text(
            encoding="utf-8"
        )
        runbook = (
            ROOT / "docs/deploy-phase3-public-discovery-staging.md"
        ).read_text(encoding="utf-8")
        legacy = (ROOT / "static/index.html").read_text(encoding="utf-8")

        self.assertIn(
            "tests.test_phase3_public_discovery_contract",
            verifier,
        )
        for expected in (
            "frontend-staging",
            "api-staging",
            "/api/v1/public/search",
            "30 soniya",
            "rollback",
            "koprik.uz",
            "v1656",
            "o‘zgartirmang",
        ):
            self.assertIn(expected, runbook)

        self.assertIn("<!-- BUILD: v1656 -->", legacy)


if __name__ == "__main__":
    unittest.main()
