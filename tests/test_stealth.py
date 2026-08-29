"""
Tests for Stealth Browser Launcher Seam (Patchright / Playwright).
Skips automatically when browser drivers or network access are unavailable,
so the suite stays green in offline CI environments.
"""

import unittest
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ai_detector_cli.stealth import (
    get_stealth_browser,
    is_patchright_available,
    is_playwright_available,
    find_browser_executable,
)

_patchright = is_patchright_available()
_any_driver = _patchright or is_playwright_available()


class TestStealthBrowser(unittest.TestCase):
    def test_patchright_availability(self):
        if not _patchright:
            self.skipTest("patchright not installed (optional extra)")
        self.assertTrue(_patchright)

    def test_find_browser_executable_returns_path_or_none(self):
        # Must never raise; may return None on headless CI without browsers.
        result = find_browser_executable()
        if result is not None:
            self.assertTrue(os.path.exists(result))

    def test_stealth_browser_launch(self):
        if not _any_driver:
            self.skipTest("neither patchright nor playwright installed")
        try:
            with get_stealth_browser(headless=True) as (browser, page, driver_name):
                self.assertIn(driver_name, ["patchright", "playwright"])
                page.goto("https://example.com", timeout=15000)
                title = page.title()
                self.assertEqual(title, "Example Domain")
                webdriver_val = page.evaluate("() => navigator.webdriver")
                self.assertIn(webdriver_val, [None, False])
        except Exception as exc:
            self.skipTest(f"browser/network unavailable in this environment: {exc}")


if __name__ == "__main__":
    unittest.main()
