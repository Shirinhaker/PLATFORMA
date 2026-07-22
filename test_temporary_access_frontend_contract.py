from pathlib import Path
import subprocess
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class DistrictOffersFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_mount_is_after_map_and_before_existing_listing_heading(self):
        home = self.html[self.html.index('data-screen="home"'):]
        map_start = home.index('<div class="map-wrap">')
        mount = home.index('id="districtOffersMount"')
        driver = home.index('id="driverCard"')
        heading = home.index('id="elonHead"')
        self.assertLess(map_start, mount)
        self.assertLess(mount, driver)
        self.assertLess(driver, heading)

    def test_rail_has_no_visible_section_title(self):
        start = self.html.index('id="districtOffersMount"')
        block = self.html[start:start + 500]
        self.assertNotIn("Sizga yaqin", block)
        self.assertNotIn("Tumandagi takliflar", block)
        self.assertNotIn("<h2", block)

    def test_loader_renderer_cache_and_navigation_contracts_exist(self):
        for value in (
            "function loadDistrictOffers(",
            "function renderDistrictOffers(",
            "function clearDistrictOffersCache(",
            '"/api/home/district-offers"',
            "openBizSrv(",
            "openElonSrv(",
        ):
            self.assertIn(value, self.html)

    def test_carousel_schedules_refresh_at_the_next_rotation_slot(self):
        for value in (
            "function scheduleDistrictOffersRefresh(",
            "DISTRICT_OFFERS_REFRESH_TIMER",
            "DISTRICT_OFFER_SLOT_MS",
            'document.addEventListener("visibilitychange"',
            "loadDistrictOffers(true)",
        ):
            self.assertIn(value, self.html)

    def test_continuous_motion_pause_and_accessibility_contracts_exist(self):
        for value in (
            "district-offers-track",
            "animation-play-state:paused",
            "prefers-reduced-motion:reduce",
            "pointerenter",
            "pointerleave",
            "focusin",
            "focusout",
            "Tumanni tanlang",
        ):
            self.assertIn(value, self.html)

    def test_carousel_motion_is_slow_enough_to_read_cards(self):
        self.assertIn(
            "animation:districtOffersFlow 68s linear infinite",
            self.html,
        )

    def test_safe_media_badges_and_synchronous_invalidation_contracts_exist(self):
        for value in (
            "function safeDistrictOfferMediaUrl(",
            "DISTRICT_OFFER_MEDIA_PATHS",
            "profile-media",
            "data-district-kind-badge",
            "Mahsulot",
            "Xizmat",
            "E’lon",
            "mount.innerHTML=\"\";",
            "mount.hidden=true;",
        ):
            self.assertIn(value, self.html)
        clear_start = self.html.index("function clearDistrictOffersCache(")
        clear_end = self.html.index("function districtOfferCardHtml(", clear_start)
        clear_body = self.html[clear_start:clear_end]
        self.assertLess(clear_body.index("mount.innerHTML=\"\";"), clear_body.index("DISTRICT_OFFERS_GENERATION++"))
        self.assertLess(clear_body.index("mount.hidden=true;"), clear_body.index("DISTRICT_OFFERS_GENERATION++"))

    def test_opaque_media_id_rule_matches_server_boundaries(self):
        self.assertIn(
            "var DISTRICT_OFFER_MEDIA_ID=/^[A-Za-z0-9_-]{1,512}$/;",
            self.html,
        )

    def test_smoke_covers_required_resilience_scenarios(self):
        smoke = Path("tests/district-offers-ui-smoke.cjs").read_text(encoding="utf-8")
        for value in (
            "validateDistrictOfferMedia",
            "verifyDistrictOfferClientStateContract",
            "RTL displacement/continuity",
            "touch/focus pause",
            "manual scroll",
            "reduced motion",
            "single static",
            "cache reuse/coalescing",
            "invalidation old cards disappear",
            "stale response protection",
            "retry after failure",
            "all three badges/media safety",
        ):
            self.assertIn(value, smoke)

    def test_browser_free_smoke_fixture_contract(self):
        result = subprocess.run(
            ["node", "tests/district-offers-ui-smoke.cjs", "--contract-only"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("District offers UI contract passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
