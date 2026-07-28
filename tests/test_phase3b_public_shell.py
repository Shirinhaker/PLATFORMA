import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend/src/legacy/public"


class Phase3BPublicShellContractTests(unittest.TestCase):
    def test_expected_react_owners_exist(self):
        expected = (
            ROOT / "frontend/src/app/AppShell.tsx",
            PUBLIC / "PublicHeader.tsx",
            PUBLIC / "HomeScreen.tsx",
            PUBLIC / "CatalogScreen.tsx",
            PUBLIC / "CategoryScreen.tsx",
            PUBLIC / "LocationScreen.tsx",
            PUBLIC / "public-navigation.ts",
        )

        for owner in expected:
            self.assertTrue(owner.is_file(), owner)

    def test_app_owns_the_six_approved_views(self):
        source = (ROOT / "frontend/src/app/App.tsx").read_text(
            encoding="utf-8"
        )

        for view in (
            'case "home"',
            'case "catalog"',
            'case "category"',
            'case "location"',
            'case "auth"',
            'case "cabinet"',
        ):
            self.assertIn(view, source)

    def test_phase3b_public_components_do_not_embed_legacy_iframes(self):
        sources = [
            path.read_text(encoding="utf-8")
            for path in PUBLIC.glob("*.tsx")
        ]

        self.assertNotIn("<iframe", "\n".join(sources).lower())

    def test_immutable_v1656_evidence_is_preserved(self):
        legacy_html = (ROOT / "static/index.html").read_text(
            encoding="utf-8"
        )
        inventory = json.loads(
            (
                ROOT / "docs/architecture/legacy-v1656-screens.json"
            ).read_text(encoding="utf-8")
        )

        self.assertIn("BUILD: v1656", legacy_html)
        self.assertEqual(len(legacy_html.splitlines()), 14091)
        self.assertEqual(inventory["build"], "v1656")
        self.assertEqual(inventory["screen_count"], 98)

    def test_production_references_remain_legacy_only(self):
        production = (ROOT / ".env.production.example").read_text(
            encoding="utf-8"
        )
        workflow = (
            ROOT / ".github/workflows/phase1-ci.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("BASE_URL=https://koprik.uz", production)
        self.assertIn("PRIMARY_DOMAIN=koprik.uz", production)
        self.assertNotIn("railway up", workflow)
        self.assertNotIn("railway deploy", workflow)

    def test_phase3b_stays_in_progress_until_manual_staging_acceptance(self):
        parity = (
            ROOT / "docs/phase3/legacy-parity.md"
        ).read_text(encoding="utf-8")

        for screen in ("`home`", "`catalog`", "`cat-types`", "`loc`"):
            matching_rows = [
                row
                for row in parity.splitlines()
                if row.startswith(f"| {screen} ")
            ]
            self.assertEqual(len(matching_rows), 1, screen)
            self.assertIn("| in-progress |", matching_rows[0])

    def test_ci_and_runbook_use_the_phase3b_gate(self):
        workflow = (
            ROOT / ".github/workflows/phase1-ci.yml"
        ).read_text(encoding="utf-8")
        runbook = (
            ROOT / "docs/deploy-phase3b-staging.md"
        ).read_text(encoding="utf-8")

        self.assertIn("python scripts/verify_phase3b.py", workflow)
        for expected in (
            "frontend-staging",
            "Bosh sahifa",
            "Katalog",
            "Yo‘nalish",
            "Manzil",
            "Kirish",
            "Oddiy kabinet",
            "Biznes kabinet",
            "desktop",
            "mobil",
            "rollback",
            "web",
            "koprik.uz",
        ):
            self.assertIn(expected, runbook)


if __name__ == "__main__":
    unittest.main()
