"""
Engine: Writer.com AI Content Detector (Playwright Browser Automation)
Automates https://writer.com/ai-content-detector/ using Playwright and extracts AI score.
"""

import re
import time
from typing import List, Optional
from .base import BaseEngine
from ..models import EngineResult


class WriterEngine(BaseEngine):
    name = "Writer.com AI Detector"
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
            from playwright.sync_api import sync_playwright
        except ImportError:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error="playwright package is not installed."
            )

        try:
            with sync_playwright() as p:
                launch_kwargs = {"headless": self.headless}
                if self.executable_path:
                    launch_kwargs["executable_path"] = self.executable_path

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                page.goto("https://writer.com/ai-content-detector/", timeout=self.timeout_ms, wait_until="domcontentloaded")
                time.sleep(2)

                # Fill text into input
                input_elem = page.query_selector("textarea, [contenteditable='true'], [role='textbox']")
                if input_elem:
                    input_elem.fill(text[:1500])
                    time.sleep(1)

                    # Click Analyze button
                    btn = page.query_selector("button:has-text('Analyze text'), button:has-text('Detect'), button:has-text('Scan')")
                    if btn:
                        btn.click()
                        time.sleep(3)

                # Extract score from page
                body_text = page.inner_text("body")
                browser.close()

                # Look for percentage scores (e.g., "85% Human", "15% AI")
                human_pct = None
                ai_pct = None

                match_human = re.search(r'(\d+)\s*%\s*(?:human-generated|human content|human)', body_text, re.IGNORECASE)
                if match_human:
                    human_pct = float(match_human.group(1))
                    ai_pct = 100.0 - human_pct

                match_ai = re.search(r'(\d+)\s*%\s*(?:AI|fake|machine)', body_text, re.IGNORECASE)
                if match_ai and ai_pct is None:
                    ai_pct = float(match_ai.group(1))
                    human_pct = 100.0 - ai_pct

                if ai_pct is not None:
                    verdict = "HUMAN" if ai_pct < 25.0 else ("AI" if ai_pct > 65.0 else "MIXED")
                    return EngineResult(
                        engine_name=self.name,
                        available=True,
                        ai_percentage=round(ai_pct, 1),
                        human_percentage=round(human_pct, 1),
                        verdict=verdict,
                        weight=self.weight,
                        details={"extracted_percentage": f"{ai_pct}% AI / {human_pct}% Human"}
                    )
                else:
                    return EngineResult(
                        engine_name=self.name,
                        available=False,
                        ai_percentage=0.0,
                        human_percentage=100.0,
                        verdict="UNAVAILABLE",
                        weight=0.0,
                        error="Score element not found on page"
                    )

        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=str(e)
            )
