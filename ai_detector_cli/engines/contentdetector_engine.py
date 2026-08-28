"""
Engine: ContentDetector.ai Playwright Automation
Automates browser interaction with https://contentdetector.ai/ using Playwright.
Extracts AI percentage, human percentage, verdict, and highlighted sentences.
"""

import os
import re
import json
import time
from typing import List, Dict, Any, Optional

from .base import BaseEngine
from ..models import EngineResult

DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

class ContentDetectorEngine(BaseEngine):
    name = "ContentDetector.ai"
    weight = 0.25

    def __init__(
        self,
        executable_path: str = DEFAULT_CHROME_PATH,
        headless: bool = True,
        timeout_ms: int = 40000
    ):
        self.executable_path = executable_path if os.path.exists(executable_path) else None
        self.headless = headless
        self.timeout_ms = timeout_ms

    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        """
        Analyzes input text using Playwright browser automation on ContentDetector.ai.
        """
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
                error="Playwright is not installed. Install with: pip install playwright"
            )

        api_data: Dict[str, Any] = {}

        def handle_response(response):
            nonlocal api_data
            try:
                url = response.url.lower()
                if any(k in url for k in ["contentdetector", "detect", "score", "ai-probability", "api"]):
                    if response.status == 200:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type:
                            data = response.json()
                            if isinstance(data, dict) and any(k in data for k in ["data", "score", "percentage", "aiPercentage", "estimatedAI", "probability", "result"]):
                                api_data = data
            except Exception:
                pass

        try:
            with sync_playwright() as p:
                launch_args = [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]

                launch_kwargs = {
                    "headless": self.headless,
                    "args": launch_args
                }
                if self.executable_path and os.path.exists(self.executable_path):
                    launch_kwargs["executable_path"] = self.executable_path

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                page = context.new_page()
                page.on("response", handle_response)

                page.goto("https://contentdetector.ai/", wait_until="domcontentloaded", timeout=self.timeout_ms)
                time.sleep(2)

                # Dismiss cookie dialogs if any
                try:
                    cookie_btn = page.locator("button:has-text('Accept'), button:has-text('Agree'), button:has-text('Got it')").first
                    if cookie_btn.is_visible(timeout=2000):
                        cookie_btn.click()
                        time.sleep(0.5)
                except Exception:
                    pass

                # Locate input area
                input_selector = None
                selectors = [
                    "textarea#content-input",
                    "#content-input",
                    "textarea#editor",
                    "textarea[placeholder*='text']",
                    "textarea[placeholder*='paste']",
                    "div[contenteditable='true']",
                    "textarea",
                    ".editor-wrapper textarea"
                ]

                for sel in selectors:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=2000):
                            input_selector = sel
                            break
                    except Exception:
                        continue

                if not input_selector:
                    input_selector = "textarea, div[contenteditable='true']"

                input_elem = page.locator(input_selector).first
                input_elem.wait_for(state="visible", timeout=10000)
                input_elem.click()
                time.sleep(0.5)

                # Set input text via evaluate and fill
                try:
                    page.evaluate(
                        """(selector, content) => {
                            const el = document.querySelector(selector);
                            if (el) {
                                if (el.tagName.toLowerCase() === 'textarea' || el.tagName.toLowerCase() === 'input') {
                                    el.value = content;
                                } else {
                                    el.innerText = content;
                                }
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }""",
                        input_selector,
                        text
                    )
                except Exception:
                    pass

                try:
                    input_elem.fill(text)
                except Exception:
                    try:
                        input_elem.press("Meta+A")
                        input_elem.press("Backspace")
                        page.keyboard.insert_text(text)
                    except Exception:
                        pass

                time.sleep(1)

                # Click analyze / check button
                button_candidates = [
                    "button:has-text('Check for AI')",
                    "button:has-text('Analyze')",
                    "button:has-text('Analyze Text')",
                    "button:has-text('Detect AI')",
                    "button:has-text('Scan')",
                    "button[type='submit']",
                    ".analyze-btn"
                ]

                for btn_sel in button_candidates:
                    try:
                        btn = page.locator(btn_sel).first
                        if btn.is_visible(timeout=1500) and btn.is_enabled(timeout=1500):
                            btn.click()
                            break
                    except Exception:
                        continue

                # Wait for score to render
                time.sleep(4)
                start_wait = time.time()
                ai_pct = None
                flagged_sentences = []
                verdict_label = ""

                while time.time() - start_wait < 20:
                    # 1. Check intercepted API data
                    if api_data:
                        if "percentage" in api_data:
                            ai_pct = float(api_data["percentage"])
                        elif "score" in api_data:
                            raw = float(api_data["score"])
                            ai_pct = raw * 100.0 if raw <= 1.0 else raw
                        elif "estimatedAI" in api_data:
                            ai_pct = float(api_data["estimatedAI"])
                        elif "aiPercentage" in api_data:
                            ai_pct = float(api_data["aiPercentage"])
                        if ai_pct is not None:
                            break

                    # 2. Check DOM for percentage
                    try:
                        dom_info = page.evaluate("""() => {
                            const text = document.body.innerText || "";
                            
                            const scoreMatches = [];
                            const elements = Array.from(document.querySelectorAll('div, span, p, h1, h2, h3, h4, strong, b'));
                            for (const el of elements) {
                                const t = el.innerText ? el.innerText.trim() : "";
                                if (/(?:Estimated\\s*AI|AI\\s*Percentage|Probability|AI\\s*Score|Fake)[\s:]*\\d{1,3}(?:\\.\\d+)?%/i.test(t) && t.length < 60) {
                                    scoreMatches.push(t);
                                } else if (/\\b\\d{1,3}(?:\\.\\d+)?%\\b/.test(t) && t.length < 30) {
                                    scoreMatches.push(t);
                                }
                            }

                            const highlights = Array.from(document.querySelectorAll('[class*="highlight"], [class*="ai"], [class*="flagged"], mark, span.ai'))
                                .map(e => e.innerText ? e.innerText.trim() : "")
                                .filter(t => t.length > 8);

                            return {
                                bodySample: text.slice(0, 3000),
                                scoreMatches: scoreMatches,
                                highlights: highlights
                            };
                        }""")

                        for item in dom_info.get("scoreMatches", []):
                            m = re.search(r'(\d+(?:\.\d+)?)%', item)
                            if m:
                                val = float(m.group(1))
                                if 0.0 <= val <= 100.0:
                                    ai_pct = val
                                    verdict_label = item
                                    break

                        if ai_pct is not None:
                            flagged_sentences = dom_info.get("highlights", [])
                            break
                    except Exception:
                        pass

                    time.sleep(1.5)

                browser.close()

                if ai_pct is None:
                    ai_pct = 0.0
                    verdict = "HUMAN"
                else:
                    verdict = "HUMAN" if ai_pct < 25.0 else ("AI" if ai_pct > 65.0 else "MIXED")

                human_pct = round(max(0.0, min(100.0, 100.0 - ai_pct)), 1)

                return EngineResult(
                    engine_name=self.name,
                    available=True,
                    ai_percentage=round(ai_pct, 1),
                    human_percentage=human_pct,
                    verdict=verdict,
                    weight=self.weight,
                    details={
                        "verdict_label": verdict_label or f"{ai_pct}% Estimated AI",
                        "method": "playwright_browser",
                        "api_intercepted": bool(api_data),
                        "flagged_count": len(flagged_sentences)
                    },
                    flagged_sentences=flagged_sentences
                )

        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"ContentDetector Playwright Error: {str(e)}"
            )
