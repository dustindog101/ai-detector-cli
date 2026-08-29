"""
Engine: IsGen AI Detector (Stealth Browser & API Integration)
Automates https://isgen.ai using Patchright / Playwright stealth automation.
"""

import re
import time
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult


class IsGenEngine(BaseEngine):
    name = "IsGen AI Detector"
    weight = 0.25

    def __init__(
        self,
        executable_path: Optional[str] = None,
        headless: bool = True,
        timeout_ms: int = 30000
    ):
        self.executable_path = executable_path  # None -> stealth auto-discovery
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
                page.goto("https://isgen.ai", timeout=self.timeout_ms, wait_until="domcontentloaded")
                time.sleep(2)

                editor = page.query_selector("textarea, [contenteditable='true'], [role='textbox']")
                if editor:
                    editor.fill(text[:3000])
                    time.sleep(1)
                    btn = page.query_selector("button:has-text('Check for AI'), button:has-text('Detect'), button:has-text('Analyze')")
                    if btn:
                        btn.click()
                        time.sleep(5)

                body_text = page.inner_text("body")
                browser.close()

                match_ai = re.search(r'(\d+)%\s*(?:AI|Fake|Probability)', body_text, re.IGNORECASE)
                if match_ai:
                    ai_prob = float(match_ai.group(1))
                    human_prob = 100.0 - ai_prob
                else:
                    return EngineResult(
                        engine_name=self.name,
                        available=False,
                        ai_percentage=0.0,
                        human_percentage=100.0,
                        verdict="UNAVAILABLE",
                        weight=0.0,
                        error="Could not parse IsGen score"
                    )

                verdict = "AI" if ai_prob > 65.0 else ("HUMAN" if ai_prob < 25.0 else "MIXED")
                return EngineResult(
                    engine_name=self.name,
                    available=True,
                    ai_percentage=round(ai_prob, 1),
                    human_percentage=round(human_prob, 1),
                    verdict=verdict,
                    weight=self.weight,
                    details={"driver": driver_type}
                )
        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"IsGen error: {str(e)}"
            )
