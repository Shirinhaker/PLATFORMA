import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class ApprovedHomeCatalogContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_home_search_matches_approved_compact_composition(self):
        for value in (
            "Kerakli mahsulot va<br>xizmatni yaqiningizdan toping",
            'id="homeQueryInput"',
            'id="homeQueryClear"',
            'id="homeSearchSubmit"',
            'id="homeCatalogOpen"',
            "Katalog bo‘yicha",
            "Qumqo‘rg‘on tumani",
        ):
            self.assertIn(value, self.html)

    def test_home_search_card_omits_legacy_shortcuts_and_location_note(self):
        self.assertNotIn('class="desktop-hero-tags"', self.html)
        self.assertNotIn('class="home-location-note"', self.html)

    def test_home_search_results_use_an_in_place_overlay(self):
        for value in (
            'id="homeSearchResultsOverlay"',
            'id="homeSearchResultsClose"',
            'id="homeSearchResultsBody"',
            "function openHomeSearchResults(",
            "function closeHomeSearchResults(",
            'runSearch(q,false,"home-overlay")',
            'el("homeCatalogOpen")',
            'el("homeSearchSubmit")',
            'el("homeQueryClear")',
        ):
            self.assertIn(value, self.html)

    def test_catalog_keeps_scope_then_direction_then_activity_flow(self):
        for value in (
            'data-scope="Mahalla"',
            'data-scope="Tuman"',
            'data-scope="Viloyat"',
            'data-scope="Respublika"',
            "Faoliyat yo'nalishlari",
            'id="catalogDirectionCount">20 ta',
            'data-screen="cat-types"',
            'function openYon(i)',
            'function openType(t)',
        ):
            self.assertIn(value, self.html)

    def test_responsive_layout_hides_horizontal_scrollbar_chrome(self):
        for value in (
            "html,body{max-width:100%;overflow-x:hidden;}",
            ".screens{scrollbar-width:none;}",
            ".screens::-webkit-scrollbar{display:none;}",
            "@media(max-width:1079px)",
            ".home-discovery{display:flex;flex-direction:column;",
        ):
            self.assertIn(value, self.html)


if __name__ == "__main__":
    unittest.main()
