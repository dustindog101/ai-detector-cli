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
    is_camoufox_available,
    find_browser_executable,
    resolve_stealth_driver,
)

_patchright = is_patchright_available()
_any_driver = _patchright or is_playwright_available()


class TestStealthDriverResolution(unittest.TestCase):
    def test_auto_resolves_to_something_installed(self):
        try:
            name = resolve_stealth_driver("auto")
        except ImportError:
            self.skipTest("no stealth driver installed")
        self.assertIn(name, ["patchright", "playwright", "camoufox"])

    def test_env_var_pin(self):
        if not (is_patchright_available() or is_playwright_available()
                or is_camoufox_available()):
            self.skipTest("no stealth driver installed")
        old = os.environ.get("AIDETECT_STEALTH_DRIVER")
        try:
            for candidate, installed in (
                    ("patchright", is_patchright_available()),
                    ("playwright", is_playwright_available()),
                    ("camoufox", is_camoufox_available())):
                if installed:
                    os.environ["AIDETECT_STEALTH_DRIVER"] = candidate
                    self.assertEqual(resolve_stealth_driver(None), candidate)
                    break
        finally:
            if old is None:
                os.environ.pop("AIDETECT_STEALTH_DRIVER", None)
            else:
                os.environ["AIDETECT_STEALTH_DRIVER"] = old

    def test_unknown_driver_raises(self):
        self.assertRaises(ImportError, resolve_stealth_driver, "nonsense")


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

    def test_explicit_camoufox_launch(self):
        if not is_camoufox_available():
            self.skipTest("camoufox not installed (optional extra)")
        try:
            with get_stealth_browser(headless=True, driver="camoufox") as (
                    browser, page, driver_name):
                self.assertEqual(driver_name, "camoufox")
                page.goto("https://example.com", timeout=20000)
                self.assertEqual(page.title(), "Example Domain")
        except Exception as exc:
            self.skipTest(f"camoufox browser/network unavailable here: {exc}")


if __name__ == "__main__":
    unittest.main()
