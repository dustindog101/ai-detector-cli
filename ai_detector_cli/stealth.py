"""
Stealth Browser Launcher for AI Detector Engines.
Provides seamless anti-bot evasion using Patchright (preferred) with Playwright fallback.
Handles CDP Runtime.enable leak patching, navigator.webdriver masking, and Chrome execution.
"""

import os
import time
from typing import Optional, Dict, Any, Generator, Tuple
from contextlib import contextmanager

DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

def is_patchright_available() -> bool:
    try:
        import patchright
        return True
    except ImportError:
        return False

@contextmanager
def get_stealth_browser(
    headless: bool = True,
    executable_path: Optional[str] = DEFAULT_CHROME_PATH,
    viewport: Dict[str, int] = None,
    user_agent: Optional[str] = None
) -> Generator[Tuple[Any, Any, str], None, None]:
    """
    Context manager that yields (browser, page, driver_name).
    Automatically tries Patchright first, falling back to Playwright.
    """
    if viewport is None:
        viewport = {"width": 1440, "height": 900}
    if user_agent is None:
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    # Select Driver: Patchright (Stealth) vs Playwright (Standard)
    driver_name = "playwright"
    try:
        from patchright.sync_api import sync_playwright
        driver_name = "patchright"
    except ImportError:
        try:
            from playwright.sync_api import sync_playwright
            driver_name = "playwright"
        except ImportError:
            raise ImportError(
                "Neither 'patchright' nor 'playwright' is installed. "
                "Install with: pip install patchright"
            )

    chrome_exec = executable_path if (executable_path and os.path.exists(executable_path)) else None

    with sync_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage"
        ]

        launch_kwargs: Dict[str, Any] = {
            "headless": headless,
            "args": launch_args
        }
        if chrome_exec:
            launch_kwargs["executable_path"] = chrome_exec

        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York"
        )
        page = context.new_page()

        # In-page navigator anti-detection scripts
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)

        try:
            yield browser, page, driver_name
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
