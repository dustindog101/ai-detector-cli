"""
Engine: GPTZero AI Detector (Stealth Browser / Patchright & API Integration)
Automates https://gptzero.me using stealth browser automation (Patchright / Playwright)
and extracts Perplexity, Burstiness, and overall AI probability percentages.
"""

import os
import re
import json
import time
from typing import List, Dict, Any, Optional

from .base import BaseEngine
from ..models import EngineResult

MAX_GPTZERO_CHARS = 5000

class GPTZeroEngine(BaseEngine):
    name = "GPTZero Detector"
    weight = 0.35

    def __init__(
        self,
        api_key: Optional[str] = None,
        executable_path: Optional[str] = None,
        headless: bool = True,
        timeout_ms: int = 35000
    ):
        self.api_key = api_key or os.environ.get("GPTZERO_API_KEY")
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

        query_text = text[:MAX_GPTZERO_CHARS]
        is_truncated = len(text) > MAX_GPTZERO_CHARS

        # 1. If official API key provided, use REST API
        if self.api_key:
            return self._analyze_api(query_text)

        # 2. Stealth Browser Automation (Patchright / Playwright)
        return self._analyze_stealth_browser(query_text, sentences)

    def _analyze_api(self, text: str) -> EngineResult:
        import urllib.request
        url = "https://api.gptzero.me/v2/predict/text"
        payload = json.dumps({"document": text, "version": "latest"}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "Accept": "application/json"
        }
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    docs = data.get("documents", [{}])[0]
                    ai_prob = float(docs.get("completely_generated_prob", 0.0)) * 100.0
                    human_prob = 100.0 - ai_prob
                    verdict = "AI" if ai_prob > 65.0 else ("HUMAN" if ai_prob < 25.0 else "MIXED")

                    flagged = []
                    for sent in docs.get("sentences", []):
                        if sent.get("generated_prob", 0.0) > 0.6:
                            flagged.append(sent.get("sentence", ""))

                    return EngineResult(
                        engine_name=self.name,
                        available=True,
                        ai_percentage=round(ai_prob, 1),
                        human_percentage=round(human_prob, 1),
                        verdict=verdict,
                        weight=self.weight,
                        details={
                            "overall_burstiness": docs.get("overall_burstiness", 0.0),
                            "average_generated_prob": docs.get("average_generated_prob", 0.0),
                            "method": "official_api"
                        },
                        flagged_sentences=flagged
                    )
        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"API error: {e}"
            )

    def _analyze_stealth_browser(self, text: str, sentences: List[str] = None) -> EngineResult:
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
                error="Neither patchright nor playwright installed. Install with 'pip install patchright' or 'pip install playwright'."
            )

        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "headless": self.headless,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox"
                    ]
                }
                if self.executable_path:
                    launch_kwargs["executable_path"] = self.executable_path

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                # Anti-detection script injection
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = { runtime: {} };
                """)

                page.goto("https://gptzero.me", timeout=self.timeout_ms, wait_until="domcontentloaded")
                time.sleep(3)

                # Locate editor
                editor = page.query_selector("textarea, [contenteditable='true'], [role='textbox']")
                if editor:
                    editor.fill(text)
                    time.sleep(1)
                    btn = page.query_selector("button:has-text('Check Origin'), button:has-text('Scan'), button:has-text('Check text'), button:has-text('Get Results')")
                    if btn:
                        btn.click()
                        time.sleep(6)

                body_text = page.inner_text("body")
                browser.close()

                # Extract score from page text
                match_prob = re.search(r'(\d+)%\s*(?:probability|likely|AI|chance)', body_text, re.IGNORECASE)
                match_human = re.search(r'(\d+)%\s*(?:human|human-written)', body_text, re.IGNORECASE)

                if match_prob:
                    ai_prob = float(match_prob.group(1))
                    human_prob = 100.0 - ai_prob
                elif match_human:
                    human_prob = float(match_human.group(1))
                    ai_prob = 100.0 - human_prob
                else:
                    return EngineResult(
                        engine_name=self.name,
                        available=False,
                        ai_percentage=0.0,
                        human_percentage=100.0,
                        verdict="UNAVAILABLE",
                        weight=0.0,
                        error="Could not parse GPTZero web score"
                    )

                verdict = "HUMAN" if ai_prob < 25.0 else ("AI" if ai_prob > 65.0 else "MIXED")
                return EngineResult(
                    engine_name=self.name,
                    available=True,
                    ai_percentage=round(ai_prob, 1),
                    human_percentage=round(human_prob, 1),
                    verdict=verdict,
                    weight=self.weight,
                    details={
                        "driver": driver_type,
                        "method": "stealth_browser",
                        "raw_extracted": f"{ai_prob}% AI"
                    }
                )

        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"GPTZero automation error: {str(e)}"
            )
