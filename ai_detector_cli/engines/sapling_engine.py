"""
Engine: Sapling AI Content Detector (Playwright & Direct HTTP)
Automates browser interaction with https://sapling.ai/ai-content-detector using Playwright.
Extracts AI percentage, human percentage, verdict, and highlighted sentences.
"""

import os
import re
import json
import time
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

from .base import BaseEngine
from ..models import EngineResult

DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

class SaplingEngine(BaseEngine):
    name = "Sapling AI Detector"
    weight = 0.30

    def __init__(
        self,
        api_key: Optional[str] = None,
        executable_path: str = DEFAULT_CHROME_PATH,
        headless: bool = True,
        prefer_browser: bool = True,
        timeout_ms: int = 40000
    ):
        self.api_key = api_key or os.environ.get("SAPLING_API_KEY")
        self.executable_path = executable_path if os.path.exists(executable_path) else None
        self.headless = headless
        self.prefer_browser = prefer_browser
        self.timeout_ms = timeout_ms

    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        """
        Analyzes input text using Playwright browser automation or direct HTTP fallback.
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

        # If API key is provided and prefer_browser is False, use direct HTTP
        if self.api_key and not self.prefer_browser:
            api_res = self._analyze_http(text)
            if api_res.available:
                return api_res

        # Attempt Playwright browser automation
        playwright_res = self._analyze_playwright(text, sentences, words)
        if playwright_res.available:
            return playwright_res

        # Fallback to direct HTTP API if browser automation was unavailable
        if self.api_key:
            return self._analyze_http(text)

        return playwright_res

    def _analyze_playwright(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
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
                if any(k in url for k in ["aidetect", "ai-detect", "ai-content-detector", "sapling.ai/api"]):
                    if response.status == 200:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type:
                            data = response.json()
                            if isinstance(data, dict) and any(k in data for k in ["score", "sentence_scores", "sentences", "ai_score", "fake"]):
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

                page.goto("https://sapling.ai/ai-content-detector", wait_until="domcontentloaded", timeout=self.timeout_ms)
                time.sleep(2)

                # Dismiss cookies if any
                try:
                    cookie_btn = page.locator("button:has-text('Accept'), button:has-text('Agree'), button#onetrust-accept-btn-handler").first
                    if cookie_btn.is_visible(timeout=2000):
                        cookie_btn.click()
                        time.sleep(0.5)
                except Exception:
                    pass

                # Locate input element
                input_selector = None
                selectors = [
                    "textarea#content-editor",
                    "#content-editor",
                    "textarea[placeholder*='text']",
                    "textarea[placeholder*='paste']",
                    "div[contenteditable='true']",
                    "textarea",
                    ".editor-container textarea"
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

                # Set input text
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

                # Click detect/analyze button if present
                button_candidates = [
                    "button:has-text('Check')",
                    "button:has-text('Analyze')",
                    "button:has-text('Detect AI')",
                    "button:has-text('Scan')",
                    "button[type='submit']"
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
                        if "score" in api_data:
                            raw_score = float(api_data["score"])
                            ai_pct = raw_score * 100.0 if raw_score <= 1.0 else raw_score
                        if "sentence_scores" in api_data and isinstance(api_data["sentence_scores"], list):
                            for s in api_data["sentence_scores"]:
                                if isinstance(s, dict) and s.get("score", 0.0) >= 0.5:
                                    stext = s.get("sentence", "")
                                    if stext:
                                        flagged_sentences.append(stext)
                        if ai_pct is not None:
                            break

                    # 2. Check DOM for overall score
                    try:
                        dom_info = page.evaluate("""() => {
                            const text = document.body.innerText || "";
                            
                            // Extract overall score elements
                            const scoreMatches = [];
                            const elements = Array.from(document.querySelectorAll('div, span, p, h1, h2, h3, h4, strong, b'));
                            for (const el of elements) {
                                const t = el.innerText ? el.innerText.trim() : "";
                                if (/(?:Overall\\s*Score|AI\\s*Score|Fake|Probability|AI)[\s:]*\\d{1,3}(?:\\.\\d+)?%/i.test(t) && t.length < 60) {
                                    scoreMatches.push(t);
                                } else if (/\\b\\d{1,3}(?:\\.\\d+)?%\\b/.test(t) && t.length < 30) {
                                    scoreMatches.push(t);
                                }
                            }

                            // Extract highlights
                            const highlights = Array.from(document.querySelectorAll('[class*="highlight"], [class*="sentence-score"], [class*="flagged"], [style*="background"], mark, span.ai'))
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
                            if not flagged_sentences:
                                flagged_sentences = dom_info.get("highlights", [])
                            break
                    except Exception:
                        pass

                    time.sleep(1.5)

                browser.close()

                if ai_pct is None:
                    # Check if text was analyzed as 0% AI (Clean Human)
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
                        "verdict_label": verdict_label or f"{ai_pct}% AI Content",
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
                error=f"Sapling Playwright Error: {str(e)}"
            )

    def _analyze_http(self, text: str) -> EngineResult:
        url = "https://api.sapling.ai/api/v1/aidetect"
        payload = {
            "text": text,
            "sent_scores": True
        }
        if self.api_key:
            payload["key"] = self.api_key

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_score = float(data.get("score", 0.0))
                    ai_percentage = round(raw_score * 100.0 if raw_score <= 1.0 else raw_score, 1)
                    human_percentage = round(max(0.0, min(100.0, 100.0 - ai_percentage)), 1)
                    verdict = "HUMAN" if ai_percentage < 25.0 else ("AI" if ai_percentage > 65.0 else "MIXED")

                    flagged_sentences = []
                    sent_scores = data.get("sentence_scores", [])
                    for s in sent_scores:
                        if isinstance(s, dict) and s.get("score", 0.0) >= 0.5:
                            stext = s.get("sentence", "")
                            if stext:
                                flagged_sentences.append(stext)

                    return EngineResult(
                        engine_name=self.name,
                        available=True,
                        ai_percentage=ai_percentage,
                        human_percentage=human_percentage,
                        verdict=verdict,
                        weight=self.weight,
                        details={
                            "method": "rest_api",
                            "raw_score": raw_score,
                            "sentence_scores": sent_scores
                        },
                        flagged_sentences=flagged_sentences
                    )
                else:
                    return EngineResult(
                        engine_name=self.name,
                        available=False,
                        ai_percentage=0.0,
                        human_percentage=100.0,
                        verdict="UNAVAILABLE",
                        weight=0.0,
                        error=f"HTTP status {resp.status}"
                    )
        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"HTTP error: {str(e)}"
            )
