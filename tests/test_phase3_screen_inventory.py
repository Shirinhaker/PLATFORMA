import json
from pathlib import Path
import unittest

from scripts.export_phase3_screen_inventory import collect_screen_inventory


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs/architecture/legacy-v1656-screens.json"


class Phase3ScreenInventoryTests(unittest.TestCase):
    def test_committed_snapshot_matches_v1656_dom(self):
        expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(collect_screen_inventory(ROOT), expected)

    def test_inventory_keeps_all_98_unique_screens(self):
        inventory = collect_screen_inventory(ROOT)
        names = [screen["name"] for screen in inventory["screens"]]

        self.assertEqual(inventory["build"], "v1656")
        self.assertEqual(inventory["screen_count"], 98)
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("home", names)
        self.assertIn("login", names)
        self.assertIn("cabinet", names)
        self.assertIn("ucab", names)
        self.assertIn("staff-home", names)


if __name__ == "__main__":
    unittest.main()
