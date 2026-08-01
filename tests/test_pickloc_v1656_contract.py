import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PicklocV1656ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    def test_marker_is_a_fixed_overlay_above_the_map_center(self):
        picker = re.search(
            r'<section class="screen" data-screen="pickloc">(?P<body>.*?)</section>',
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(picker)
        body = picker.group("body")
        self.assertRegex(
            body,
            r'<div id="pickMap"[^>]*></div>\s*<div id="pickPin"[^>]*'
            r'left:50%;top:50%;transform:translate\(-50%,-100%\)',
        )
        self.assertIn(
            "height:calc(100vh - 180px);height:calc(100dvh - 180px)",
            body,
        )

    def test_map_size_is_recalculated_after_animation_and_viewport_changes(self):
        self.assertIn('function syncPickerSize()', self.html)
        self.assertIn('addEventListener("animationend", syncPickerSize)', self.html)
        self.assertIn('window.addEventListener("resize", syncPickerSize)', self.html)
        self.assertIn(
            'window.addEventListener("orientationchange", syncPickerSize)',
            self.html,
        )

    def test_confirmed_coordinate_comes_from_map_center(self):
        self.assertIsNotNone(re.search(
            r'el\("pickConfirm"\)\.addEventListener\("click".*?'
            r'var c = PMAP\.getCenter\(\);.*?setPicked\(pickTarget, ll\[0\], ll\[1\]\);',
            self.html,
            re.DOTALL,
        ))


if __name__ == "__main__":
    unittest.main()
