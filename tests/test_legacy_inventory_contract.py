import json
from pathlib import Path
import unittest

from scripts.export_legacy_inventory import collect_inventory


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs/architecture/legacy-v1656-inventory.json"


class LegacyInventoryContractTests(unittest.TestCase):
    def test_runtime_contract_matches_committed_snapshot(self):
        expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(collect_inventory(ROOT), expected)

    def test_phase_one_does_not_change_legacy_frontend(self):
        html = (ROOT / "static/index.html").read_text(encoding="utf-8")
        self.assertEqual(len(html.splitlines()), 14091)
        self.assertIn("<!-- BUILD: v1656 -->", html)


if __name__ == "__main__":
    unittest.main()
