"""
Stealth Browser Launcher for AI Detector Engines.
Provides seamless anti-bot evasion using Patchright (preferred) with Playwright
fallback and Camoufox (stealth Firefox) as an alternative driver.
Handles CDP Runtime.enable leak patching, navigator.webdriver masking, and Chrome execution.

Cross-platform browser discovery: macOS, Linux, and Windows are all supported.
Override resolution order:
  1. ``AIDETECT_CHROME_PATH`` environment variable
  2. ``executable_path`` argument (if it exists on disk)
  3. Auto-discovery across well-known install locations on every OS
  4. ``shutil.which`` on PATH (chrome, chromium, chromium-browser, ...)
  5. Patchright/Playwright bundled Chromium (if drivers are installed)

Driver selection (stealth browser engine):
  - ``driver`` argument to :func:`get_stealth_browser`
  - ``AIDETECT_STEALTH_DRIVER`` environment variable (patchright|playwright|camoufox|auto)
  - ``auto``: Patchright Chromium -> Playwright Chromium -> Camoufox Firefox

Camoufox ships randomized Firefox fingerprints (FP-Inject) and is useful when a
site hard-blocks Chromium-family automation. Install with ``pip install
'ai-detector-cli[camoufox]'`` and fetch its browser once via ``python -m camoufox fetch``.
"""

import os
import platform
import shutil
from typing import Optional, Dict, Any, Generator, Tuple, List
from contextlib import contextmanager

BROWSER_ENV_VAR = "AIDETECT_CHROME_PATH"
STEALTH_DRIVER_ENV_VAR = "AIDETECT_STEALTH_DRIVER"


def is_patchright_available() -> bool:
    try:
        import patchright  # noqa: F401
        return True
    except ImportError:
        return False


def is_playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def is_camoufox_available() -> bool:
    try:
        import camoufox  # noqa: F401
        return True
    except ImportError:
        return False


def _macos_candidates() -> List[str]:
    home = os.path.expanduser("~")
    roots = ["/Applications", os.path.join(home, "Applications"), "/Applications/Chromium.app"]
    names = [
        "Google Chrome.app/Contents/MacOS/Google Chrome",
        "Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "Chromium.app/Contents/MacOS/Chromium",
        "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    return [os.path.join(root, n) for root in roots for n in names]


def _linux_candidates() -> List[str]:
    return [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/microsoft-edge",
        "/usr/bin/microsoft-edge-stable",
        "/usr/bin/brave-browser",
        "/snap/bin/chromium",
        "/opt/google/chrome/chrome",
        "/usr/local/bin/chrome",
    ]


def _windows_candidates() -> List[str]:
    candidates = []
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_appdata = os.environ.get("LocalAppData", os.path.expandvars(r"%LocalAppData%"))
    for root in (pf, pf86, local_appdata):
        candidates.extend([
            os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(root, "Chromium", "Application", "chrome.exe"),
            os.path.join(root, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        ])
    return candidates


_CANDIDATE_FUNCS = {
    "Darwin": _macos_candidates,
    "Linux": _linux_candidates,
    "Windows": _windows_candidates,
}

_BROWSER_BIN_NAMES = [
    "google-chrome-stable", "google-chrome", "chromium", "chromium-browser",
    "chrome", "microsoft-edge", "microsoft-edge-stable", "brave-browser", "chromium-browser",
]


def find_browser_executable(explicit: Optional[str] = None) -> Optional[str]:
    """
    Locate a Chromium-family browser executable across platforms.

    Returns the first existing path, or None when no browser can be found.
    """
    # 1. Environment override always wins.
    env_path = os.environ.get(BROWSER_ENV_VAR)
    if env_path and os.path.exists(env_path):
        return env_path

    # 2. Explicit argument if valid.
    if explicit and os.path.exists(explicit):
        return explicit

    # 3. Well-known per-OS locations (current platform first, then others as fallback).
    system = platform.system()
    ordered = [system] + [s for s in _CANDIDATE_FUNCS if s != system]
    for sysname in ordered:
        func = _CANDIDATE_FUNCS.get(sysname)
        if not func:
            continue
        for candidate in func():
            if candidate and os.path.exists(candidate):
                return candidate

    # 4. PATH lookup.
    for name in _BROWSER_BIN_NAMES:
        found = shutil.which(name)
        if found:
            return found

    # 5. Patchright / Playwright managed Chromium.
    for module, getter in (
        ("patchright.sync_api", "chromium"),
        ("playwright.sync_api", "chromium"),
    ):
        try:
            mod = __import__(module, fromlist=["sync_playwright"])
            with mod.sync_playwright() as p:
                path = getattr(p, getter).executable_path
                if path and os.path.exists(path):
                    return path
        except Exception:
            continue

    return None


DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def resolve_stealth_driver(driver: Optional[str] = None) -> str:
    """
    Resolve which stealth driver to use: 'patchright', 'playwright' or 'camoufox'.

    Precedence: explicit ``driver`` argument > ``AIDETECT_STEALTH_DRIVER`` env var
    > auto (patchright -> playwright -> camoufox). Raises ImportError when nothing
    usable is installed.
    """
    choice = (driver or os.environ.get(STEALTH_DRIVER_ENV_VAR) or "auto").strip().lower()
    if choice != "auto" and choice not in ("patchright", "playwright", "camoufox"):
        raise ImportError(
            "Unknown stealth driver '%s' (expected patchright, playwright, "
            "camoufox or auto)" % choice)
    if choice in ("patchright", "playwright", "camoufox"):
        available = {
            "patchright": is_patchright_available(),
            "playwright": is_playwright_available(),
            "camoufox": is_camoufox_available(),
        }
        if available.get(choice):
            return choice
        raise ImportError(
            "AIDETECT_STEALTH_DRIVER=%s requested but the driver is not installed. "
            "Install with: pip install '%s'" % (
                choice, "patchright" if choice != "camoufox" else "camoufox"))
    # auto mode: chromium stealth first, camoufox firefox as last resort.
    if is_patchright_available():
        return "patchright"
    if is_playwright_available():
        return "playwright"
    if is_camoufox_available():
        return "camoufox"
    raise ImportError(
        "Neither 'patchright', 'playwright' nor 'camoufox' is installed. "
        "Install with: pip install patchright   (or: pip install camoufox)"
    )


@contextmanager
def _open_camoufox(headless: bool, viewport: Dict[str, int]):
    """Yield (browser, page) from a Camoufox stealth-Firefox launch."""
    from camoufox.sync_api import Camoufox

    cm = Camoufox(headless=headless)
    browser = cm.__enter__()
    page = None
    try:
        page = browser.new_page(viewport=viewport)
        yield browser, page
    finally:
        try:
            if page is not None:
                page.close()
        except Exception:
            pass
        try:
            cm.__exit__(None, None, None)
        except Exception:
            pass


@contextmanager
def get_stealth_browser(
    headless: bool = True,
    executable_path: Optional[str] = None,
    viewport: Optional[Dict[str, int]] = None,
    user_agent: Optional[str] = None,
    driver: Optional[str] = None
) -> Generator[Tuple[Any, Any, str], None, None]:
    """
    Context manager that yields (browser, page, driver_name).
    Automatically tries Patchright first, falling back to Playwright, then to
    Camoufox (stealth Firefox). ``driver`` pins one of the three.
    When ``executable_path`` is None or missing, auto-discovers a browser
    (chromium drivers only).
    """
    if viewport is None:
        viewport = {"width": 1440, "height": 900}

    driver_name = resolve_stealth_driver(driver)

    if driver_name == "camoufox":
        with _open_camoufox(headless, viewport) as (browser, page):
            yield browser, page, "camoufox"
        return

    if user_agent is None:
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    # Select Driver: Patchright (Stealth) vs Playwright (Standard)
    if driver_name == "patchright":
        from patchright.sync_api import sync_playwright
    else:
        from playwright.sync_api import sync_playwright

    chrome_exec = find_browser_executable(executable_path)

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
