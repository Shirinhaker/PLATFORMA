from pathlib import Path
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class TemporaryAccessFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_closed_project_has_full_screen_message(self):
        for value in (
            'id="projectClosed"',
            "Loyiha vaqtincha yopiq",
            "function showProjectClosed(",
            'error.code==="project_temporarily_closed"',
        ):
            self.assertIn(value, self.html)


if __name__ == "__main__":
    unittest.main()
