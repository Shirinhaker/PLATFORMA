import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class MobileListingsButtonContractTests(unittest.TestCase):
    """Tasdiqlangan dizayn: E’lonlar mobil yuqori panelda turadi."""

    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_home_has_mobile_header_listings_button(self):
        for value in (
            'id="webBrandBtn"',
            'id="webListingsBtn"',
            '>Koprik</button>',
            '>E’lonlar</button>',
        ):
            self.assertIn(value, self.html)
        self.assertIn('@media(max-width:1079px)', self.html)

    def test_button_opens_separate_listings_screen(self):
        self.assertIn('el("webListingsBtn") && el("webListingsBtn").addEventListener("click",openWebListings)', self.html)
        self.assertIn("function openWebListings()", self.html)
        self.assertIn('nav("listings")', self.html)

    def test_home_does_not_duplicate_listings_button_below_offers(self):
        self.assertNotIn('id="homeElonOpenBtn"', self.html)
        self.assertNotIn('id="homeElonMount"', self.html)
        self.assertNotIn("placeElonSection", self.html)
        listings_screen = self.html.index('data-screen="listings"')
        for marker in ('id="elonHead"', 'id="elonRow"', 'id="elonList"'):
            self.assertGreater(self.html.index(marker), listings_screen)


if __name__ == "__main__":
    unittest.main()
