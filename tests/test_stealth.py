"""
Tests for Stealth Browser Launcher Seam (Patchright / Playwright).
"""

import unittest
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ai_detector_cli.stealth import get_stealth_browser, is_patchright_available

class TestStealthBrowser(unittest.TestCase):
    def test_patchright_availability(self):
        # Asserts Patchright is detected in the environment
        self.assertTrue(is_patchright_available(), "Patchright should be installed and detected.")

    def test_stealth_browser_launch(self):
        # Asserts stealth browser launches, navigates, and masks navigator.webdriver
        with get_stealth_browser(headless=True) as (browser, page, driver_name):
            self.assertIn(driver_name, ["patchright", "playwright"])
            page.goto("https://example.com")
            title = page.title()
            self.assertEqual(title, "Example Domain")

            # Verify navigator.webdriver masking (should be False or None)
            webdriver_val = page.evaluate("() => navigator.webdriver")
            self.assertIn(webdriver_val, [None, False], "navigator.webdriver should be False or None in stealth mode.")

if __name__ == "__main__":
    unittest.main()
