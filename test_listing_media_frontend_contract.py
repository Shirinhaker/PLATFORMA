import unittest
from pathlib import Path

import access_config


class PublicAccessContractTests(unittest.TestCase):
    """v1629 — loyiha hamma uchun ochiq; yopish faqat env orqali."""

    def test_default_is_open_in_source(self):
        source = Path("access_config.py").read_text(encoding="utf-8")
        self.assertIn('_env_flag("PROJECT_ACCESS_RESTRICTED", False)', source)
        runtime = Path("runtime_config.py").read_text(encoding="utf-8")
        self.assertIn('env_flag("PROJECT_ACCESS_RESTRICTED", False, env)', runtime)

    def test_build_flags_declare_public_access(self):
        main_text = Path("main.py").read_text(encoding="utf-8")
        self.assertIn('"public_access": True', main_text)
        self.assertIn('"temporary_privileged_access_only": False', main_text)
        self.assertIn('"public_launch_v1629": True', main_text)

    def test_open_mode_allows_everyone(self):
        original = access_config.PROJECT_ACCESS_RESTRICTED
        try:
            access_config.PROJECT_ACCESS_RESTRICTED = False
            self.assertFalse(access_config.project_access_is_restricted())
            self.assertTrue(access_config.project_access_allowed_tg_id(999_999_999))
            self.assertTrue(access_config.project_access_allowed_tg_id(None))
        finally:
            access_config.PROJECT_ACCESS_RESTRICTED = original

    def test_env_can_still_close_temporarily(self):
        original = access_config.PROJECT_ACCESS_RESTRICTED
        try:
            access_config.PROJECT_ACCESS_RESTRICTED = True
            self.assertTrue(access_config.project_access_is_restricted())
            self.assertFalse(access_config.project_access_allowed_tg_id(999_999_999))
            privileged = next(iter(access_config.PRIVILEGED_TG_IDS))
            self.assertTrue(access_config.project_access_allowed_tg_id(privileged))
        finally:
            access_config.PROJECT_ACCESS_RESTRICTED = original


if __name__ == "__main__":
    unittest.main()
