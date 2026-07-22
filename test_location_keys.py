from pathlib import Path
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class BusinessSubscriptionFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_subscription_card_is_immediately_after_profile(self):
        online_start = self.html.index('id="cabGridOnline"')
        online_end = self.html.index('</div>\n        </div>\n        <div class="cab-group" id="cabGroupTizim"')
        online = self.html[online_start:online_end]
        profile = online.index('data-nav="cab-profil"')
        subscription = online.index('data-nav="cab-subscriptions"')
        items = online.index('data-nav="cab-items"')
        self.assertLess(profile, subscription)
        self.assertLess(subscription, items)
        self.assertEqual(online.count('data-nav="cab-subscriptions"'), 1)

    def test_subscription_screen_and_states_exist(self):
        for value in (
            'data-screen="cab-subscriptions"',
            'id="businessSubscriptionLoading"',
            'id="businessSubscriptionError"',
            'id="businessSubscriptionContent"',
            'id="businessSubscriptionCurrent"',
            'id="businessSubscriptionHistory"',
            'data-sub-duration="1"',
            'data-sub-duration="3"',
            'data-sub-duration="12"',
            'data-sub-activate="free"',
            'data-sub-activate="plus"',
            'data-sub-activate="pro"',
            "Haqiqiy to‘lov hali ulanmagan",
        ):
            self.assertIn(value, self.html)

    def test_plan_copy_has_unlimited_items_but_no_story_benefits_or_prices(self):
        screen_start = self.html.index('data-screen="cab-subscriptions"')
        screen_end = self.html.index('</section>', screen_start)
        screen = self.html[screen_start:screen_end]
        self.assertIn("Mahsulot va xizmatlarni cheksiz joylash", screen)
        self.assertIn("Sizga yaqin", screen)
        self.assertIn("xaritada", screen)
        self.assertNotIn("istoriya", screen.lower())
        self.assertNotIn("so'm", screen.lower())
        self.assertNotIn("narxi", screen.lower())

    def test_follow_labels_are_unambiguous(self):
        self.assertIn('"cab-following":"Kuzatayotganlar"', self.html)
        self.assertIn('"ucab-subs":"Kuzatayotganlar"', self.html)
        self.assertNotIn('"cab-following":"Obunalarim"', self.html)
        self.assertNotIn('"ucab-subs":"Obunalarim"', self.html)

    def test_subscription_functions_and_routes_exist(self):
        for function_name in (
            "loadBusinessSubscription",
            "renderBusinessSubscription",
            "activateBusinessSubscription",
            "setBusinessSubscriptionBusy",
        ):
            self.assertIn(f"function {function_name}(", self.html)
        self.assertIn('"/api/business/subscription"', self.html)
        self.assertIn('"/api/business/subscription/demo-activate"', self.html)
        self.assertIn('screen==="cab-subscriptions"', self.html)

    def test_subscription_layout_has_mobile_safe_constraints(self):
        for value in (
            ".subscription-shell",
            ".subscription-plan-grid",
            "minmax(0,1fr)",
            "min-width:0",
            "overflow-wrap:anywhere",
            "@media(min-width:720px)",
        ):
            self.assertIn(value, self.html)

    def test_subscription_is_not_exposed_in_staff_section_catalog(self):
        staff_start = self.html.index("var STAFF_SECTIONS")
        staff_end = self.html.index("function showStaffLogin", staff_start)
        staff_catalog = self.html[staff_start:staff_end]
        self.assertNotIn('nav:"cab-subscriptions"', staff_catalog)


if __name__ == "__main__":
    unittest.main()
