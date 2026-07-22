from pathlib import Path
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class WebHomeFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_desktop_header_matches_koprik_web_navigation(self):
        for value in (
            'id="webBrandBtn"',
            'id="webListingsBtn"',
            ">Koprik</button>",
            ">E’lonlar</button>",
        ):
            self.assertIn(value, self.html)
        self.assertNotIn('id="webHomeBtn"', self.html)
        self.assertNotIn(">Bosh sahifa</button>", self.html)
        self.assertIn(
            'el("webBrandBtn") && el("webBrandBtn").addEventListener("click",openWebHome)',
            self.html,
        )

    def test_desktop_layout_reuses_live_search_map_stories_and_offers(self):
        for value in (
            "@media(min-width:1080px)",
            ".home-discovery{display:grid",
            'id="homeSearchSubmit"',
            'id="homeCatalogOpen"',
            'id="leafletMap"',
            'id="storyRail"',
            'id="districtOffersMount"',
            "animation:districtOffersFlow 68s linear infinite",
        ):
            self.assertIn(value, self.html)

    def test_listings_button_opens_separate_listings_screen(self):
        for value in (
            'data-screen="listings"',
            'id="elonHead"',
            'id="elonRow"',
            'id="elonList"',
            "function openWebListings()",
            'nav("listings")',
        ):
            self.assertIn(value, self.html)
        self.assertNotIn('id="webAdsBtn"', self.html)
        self.assertNotIn('data-screen="ads"', self.html)

    def test_advertisement_is_after_hero_and_before_offers(self):
        hero = self.html.index('class="home-discovery"')
        offers = self.html.index('id="districtOffersMount"')
        advertisement = self.html.index('id="adBox"')
        listings_screen = self.html.index('data-screen="listings"')
        listings_heading = self.html.index('id="elonHead"')
        self.assertLess(hero, advertisement)
        self.assertLess(advertisement, offers)
        self.assertLess(offers, listings_screen)
        self.assertLess(listings_screen, listings_heading)

    def test_desktop_layout_does_not_clip_hero_or_show_duplicate_header_search(self):
        for value in (
            '.tb-home>.search{display:none;}',
            'min-height:430px',
            'justify-content:flex-start',
            'class="home-catalog-open"',
            '/demo_ads/demo_sofa.svg',
            '.district-offers-track{animation-duration:150s;}',
        ):
            self.assertIn(value, self.html)

    def test_current_product_constraints_remain_present(self):
        for value in (
            'data-screen="cab-subscriptions"',
            'id="storyAddCard"',
            'id="seedDistrictOffers"',
            'id="mapChip"',
        ):
            self.assertIn(value, self.html)


if __name__ == "__main__":
    unittest.main()
