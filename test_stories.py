import json
from pathlib import Path
import unittest


class StoryApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = Path("api.py").read_text(encoding="utf-8")
        cls.main = Path("main.py").read_text(encoding="utf-8")

    def test_authenticated_routes_exist(self):
        for route in (
            '@router.get("/stories/feed")',
            '@router.get("/stories/mine")',
            '@router.post("/stories")',
            '@router.post("/stories/{story_id}/view")',
            '@router.get("/stories/{story_id}/viewers")',
            '@router.get("/stories/{story_id}/owner-media")',
            '@router.delete("/stories/{story_id}")',
            '@router.post("/stories/{story_id}/reports")',
        ):
            self.assertIn(route, self.api)

    def test_owner_media_is_not_a_public_route(self):
        self.assertIn(
            '@router.get("/stories/{story_id}/owner-media")',
            self.api,
        )
        self.assertNotIn(
            '@public_router.get("/stories/{story_id}/owner-media")',
            self.api,
        )

    def test_public_media_routes_exist(self):
        self.assertIn('@public_router.get("/story-media/{story_id}")', self.api)
        self.assertIn('@public_router.get("/story-thumbnail/{story_id}")', self.api)
        self.assertIn("app.include_router(public_api_router)", self.main)

    def test_ffmpeg_is_declared_for_deployment(self):
        config = Path("nixpacks.toml").read_text(encoding="utf-8")
        self.assertIn('nixPkgs = ["...", "ffmpeg"]', config)

    def test_ffmpeg_is_declared_for_current_railpack_runtime(self):
        config = json.loads(Path("railpack.json").read_text(encoding="utf-8"))
        self.assertEqual(config.get("provider"), "python")
        self.assertIn("ffmpeg", config.get("deploy", {}).get("aptPackages", []))


if __name__ == "__main__":
    unittest.main()
