"""
Engine: QuillBot Playwright AI Content Detector
Automates browser interaction with https://quillbot.com/ai-content-detector using Playwright.
Extracts AI percentage, verdict, flagged sentences, and word count statistics.
"""

import os
import re
import json
import time
from typing import List, Dict, Any, Optional
from .base import BaseEngine
from ..models import EngineResult

DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

class QuillBotEngine(BaseEngine):
    name = "QuillBot AI Detector"
    weight = 0.35

    def __init__(self, executable_path: str = DEFAULT_CHROME_PATH, headless: bool = True, timeout_ms: int = 45000):
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
                error="playwright package is not installed. Install via 'pip install playwright'."
            )

        api_data: Dict[str, Any] = {}

        def handle_response(response):
            nonlocal api_data
            try:
                url = response.url.lower()
                if any(k in url for k in ["ai-detector", "aidetect", "detect", "score", "quillbot.com/api"]):
                    if response.status == 200:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type:
                            data = response.json()
                            if isinstance(data, dict) and any(k in data for k in ["data", "score", "aiScore", "ai_percentage", "fakePercentage", "sentences", "result"]):
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

                # 1. Navigate to QuillBot AI Content Detector
                page.goto("https://quillbot.com/ai-content-detector", wait_until="domcontentloaded", timeout=self.timeout_ms)
                time.sleep(2)

                # 2. Dismiss cookie / consent banner if present
                try:
                    cookie_btn = page.locator("button#onetrust-accept-btn-handler, button:has-text('Accept All'), button:has-text('Accept all cookies'), button:has-text('Agree'), button:has-text('Accept')").first
                    if cookie_btn.is_visible(timeout=3000):
                        cookie_btn.click()
                        time.sleep(0.5)
                except Exception:
                    pass

                # 3. Locate input element
                input_selector = None
                selectors_to_try = [
                    "div[contenteditable='true']",
                    "div[role='textbox']",
                    "#input-text-area",
                    "div[data-testid='input-box']",
                    "textarea",
                    ".quill-editor",
                    "[contenteditable='true']"
                ]

                for sel in selectors_to_try:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=2000):
                            input_selector = sel
                            break
                    except Exception:
                        continue

                if not input_selector:
                    # Fallback to general contenteditable or textarea search
                    input_selector = "div[contenteditable='true'], textarea"

                input_elem = page.locator(input_selector).first
                input_elem.wait_for(state="visible", timeout=10000)
                input_elem.click()
                time.sleep(0.5)

                # Input text into the editor
                try:
                    # Clear and insert
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

                # Also use keyboard / fill fallback to trigger all framework listeners
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

                # 4. Click Detect / Scan Button
                detect_btn_selectors = [
                    "button:has-text('Detect AI')",
                    "button:has-text('Scan text')",
                    "button:has-text('Check for AI')",
                    "button:has-text('Analyze text')",
                    "button:has-text('Detect')",
                    "button[type='submit']",
                    "button.detect-button"
                ]

                button_clicked = False
                for btn_sel in detect_btn_selectors:
                    try:
                        btn = page.locator(btn_sel).first
                        if btn.is_visible(timeout=1500) and btn.is_enabled(timeout=1500):
                            btn.click()
                            button_clicked = True
                            break
                    except Exception:
                        continue

                if not button_clicked:
                    # Try clicking by evaluate
                    page.evaluate("""() => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const target = buttons.find(b => /detect|scan|check|analyze/i.test(b.innerText || b.textContent));
                        if (target) target.click();
                    }""")

                # 5. Wait for results to render
                time.sleep(4)
                start_wait = time.time()
                ai_pct = None
                verdict_text = ""
                flagged_sentences = []
                word_count_val = len(words) if words else len(text.split())

                while time.time() - start_wait < 25:
                    # Check DOM for percentage
                    try:
                        # Search for score text in DOM
                        dom_info = page.evaluate("""() => {
                            const textContent = document.body.innerText || "";
                            
                            // Look for percentage patterns: "XX% AI", "XX% of text is likely AI", "XX%"
                            const matches = Array.from(document.querySelectorAll('span, div, p, h1, h2, h3, h4, b, strong'))
                                .map(e => e.innerText ? e.innerText.trim() : "")
                                .filter(t => /\\b\\d{1,3}%\\b/.test(t) && t.length < 100);

                            // Find highlighted sentences
                            const highlights = Array.from(document.querySelectorAll('[class*="highlight"], [class*="ai-sentence"], [class*="flagged"], [style*="background-color"], mark, span.ai'))
                                .map(e => e.innerText ? e.innerText.trim() : "")
                                .filter(t => t.length > 5);

                            return {
                                bodySample: textContent.slice(0, 3000),
                                pctElements: matches,
                                highlights: highlights
                            };
                        }""")

                        # If API data was captured
                        if api_data:
                            # Try to extract score from API response
                            if "data" in api_data and isinstance(api_data["data"], dict):
                                d = api_data["data"]
                                if "fakePercentage" in d or "aiScore" in d or "score" in d:
                                    raw_pct = d.get("fakePercentage") or d.get("aiScore") or d.get("score")
                                    ai_pct = float(raw_pct)
                                    if "sentences" in d and isinstance(d["sentences"], list):
                                        flagged_sentences = [str(s) for s in d["sentences"]]
                                    break
                            elif "score" in api_data:
                                ai_pct = float(api_data["score"])
                                break
                            elif "ai_percentage" in api_data:
                                ai_pct = float(api_data["ai_percentage"])
                                break

                        # Check DOM percentage matches
                        pct_elements = dom_info.get("pctElements", [])
                        for item in pct_elements:
                            m = re.search(r'(\\d{1,3})%', item)
                            if m:
                                val = float(m.group(1))
                                if 0.0 <= val <= 100.0:
                                    ai_pct = val
                                    verdict_text = item
                                    break

                        if ai_pct is not None:
                            flagged_sentences = dom_info.get("highlights", [])
                            break

                    except Exception:
                        pass
                    time.sleep(1.5)

                browser.close()

                # Fallback if no percentage found but analysis finished
                if ai_pct is None:
                    ai_pct = 0.0
                    verdict = "HUMAN"
                else:
                    if ai_pct < 25.0:
                        verdict = "HUMAN"
                    elif ai_pct > 65.0:
                        verdict = "AI"
                    else:
                        verdict = "MIXED"

                return EngineResult(
                    engine_name=self.name,
                    available=True,
                    ai_percentage=round(ai_pct, 1),
                    human_percentage=round(100.0 - ai_pct, 1),
                    verdict=verdict,
                    weight=self.weight,
                    details={
                        "verdict_label": verdict_text or f"{ai_pct}% AI-generated",
                        "total_words": word_count_val,
                        "flagged_sentence_count": len(flagged_sentences),
                        "api_captured": bool(api_data)
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
                error=f"QuillBot Playwright Automation Error: {str(e)}"
            )
