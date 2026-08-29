"""
Engine: CopyLeaks AI Content Detector (Stealth Browser / Patchright & API Integration)
Automates https://copyleaks.com/ai-content-detector using Patchright/Playwright stealth automation.
"""

import os
import re
import json
import time
from typing import List, Dict, Any, Optional

from .base import BaseEngine
from ..models import EngineResult

DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MAX_COPYLEAKS_CHARS = 4000

class CopyLeaksEngine(BaseEngine):
    name = "CopyLeaks AI Detector"
    weight = 0.35

    def __init__(
        self,
        api_key: Optional[str] = None,
        email: Optional[str] = None,
        executable_path: str = DEFAULT_CHROME_PATH,
        headless: bool = True,
        timeout_ms: int = 35000
    ):
        self.api_key = api_key or os.environ.get("COPYLEAKS_API_KEY")
        self.email = email or os.environ.get("COPYLEAKS_EMAIL")
        self.executable_path = executable_path if os.path.exists(executable_path) else None
        self.headless = headless
        self.timeout_ms = timeout_ms

    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error="Input text is empty"
            )

        query_text = text[:MAX_COPYLEAKS_CHARS]

        # Stealth Browser Automation (Patchright / Playwright)
        try:
            try:
                from patchright.sync_api import sync_playwright
                driver_type = "patchright"
            except ImportError:
                from playwright.sync_api import sync_playwright
                driver_type = "playwright"
        except ImportError:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error="Neither patchright nor playwright installed."
            )

        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "headless": self.headless,
                    "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                }
                if self.executable_path:
                    launch_kwargs["executable_path"] = self.executable_path

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

                page.goto("https://copyleaks.com/ai-content-detector", timeout=self.timeout_ms, wait_until="domcontentloaded")
                time.sleep(3)

                # Paste text
                editor = page.query_selector("textarea, [contenteditable='true'], [role='textbox']")
                if editor:
                    editor.fill(query_text)
                    time.sleep(1)
                    btn = page.query_selector("button:has-text('Check'), button:has-text('Scan'), button:has-text('Detect')")
                    if btn:
                        btn.click()
                        time.sleep(6)

                body_text = page.inner_text("body")
                browser.close()

                match_ai = re.search(r'(\d+)%\s*(?:AI|probability|confidence)', body_text, re.IGNORECASE)
                match_human = re.search(r'(\d+)%\s*human', body_text, re.IGNORECASE)

                if match_ai:
                    ai_prob = float(match_ai.group(1))
                    human_prob = 100.0 - ai_prob
                elif match_human:
                    human_prob = float(match_human.group(1))
                    ai_prob = 100.0 - human_prob
                elif "This is AI" in body_text or "AI Content Detected" in body_text:
                    ai_prob = 95.0
                    human_prob = 5.0
                elif "This is human" in body_text or "Human text" in body_text:
                    ai_prob = 5.0
                    human_prob = 95.0
                else:
                    return EngineResult(
                        engine_name=self.name,
                        available=False,
                        ai_percentage=0.0,
                        human_percentage=100.0,
                        verdict="UNAVAILABLE",
                        weight=0.0,
                        error="Could not parse CopyLeaks score"
                    )

                verdict = "AI" if ai_prob > 65.0 else ("HUMAN" if ai_prob < 25.0 else "MIXED")
                return EngineResult(
                    engine_name=self.name,
                    available=True,
                    ai_percentage=round(ai_prob, 1),
                    human_percentage=round(human_prob, 1),
                    verdict=verdict,
                    weight=self.weight,
                    details={"driver": driver_type, "method": "stealth_browser"}
                )

        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"CopyLeaks error: {str(e)}"
            )
