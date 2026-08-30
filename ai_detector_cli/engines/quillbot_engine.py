"""
Engine: QuillBot Playwright AI Content Detector (with Patchright Stealth)
Automates https://quillbot.com/ai-content-detector using Patchright stealth browser.
Extracts AI percentage, verdict, flagged sentences, and word count statistics.
"""

import re
import time
from typing import List, Optional
from .base import BaseEngine
from ..models import EngineResult
from ..stealth import get_stealth_browser

MAX_QUILLBOT_WORDS = 1100
MIN_QUILLBOT_WORDS = 80

class QuillBotEngine(BaseEngine):
    name = "QuillBot AI Detector"
    weight = 0.35

    def __init__(self, executable_path: Optional[str] = None, headless: bool = True, timeout_ms: int = 40000):
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

        word_list = words if words else text.split()
        if len(word_list) < MIN_QUILLBOT_WORDS:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"QuillBot requires at least {MIN_QUILLBOT_WORDS} words (provided: {len(word_list)} words)."
            )

        query_text = " ".join(word_list[:MAX_QUILLBOT_WORDS])

        try:
            with get_stealth_browser(headless=self.headless, executable_path=self.executable_path) as (browser, page, driver_name):
                api_data = {}

                def handle_response(response):
                    nonlocal api_data
                    try:
                        url = response.url.lower()
                        if any(k in url for k in ["ai-detector", "detect", "score", "quillbot.com/api"]):
                            if response.status == 200:
                                res_json = response.json()
                                if isinstance(res_json, dict) and any(k in res_json for k in ["score", "percentage", "data", "result", "ai"]):
                                    api_data = res_json
                    except Exception:
                        pass

                page.on("response", handle_response)
                page.goto("https://quillbot.com/ai-content-detector", timeout=self.timeout_ms, wait_until="domcontentloaded")
                time.sleep(3)

                # Cookie banner dismissal
                for cookie_sel in [
                    "button:has-text('Accept All')",
                    "button:has-text('Accept Cookies')",
                    "button:has-text('Agree')",
                    "button#onetrust-accept-btn-handler",
                    ".accept-cookies-button"
                ]:
                    try:
                        btn = page.query_selector(cookie_sel)
                        if btn:
                            btn.click()
                            time.sleep(0.5)
                            break
                    except Exception:
                        pass

                # Locate editor
                editor = page.query_selector("div[contenteditable='true'], div[role='textbox'], #input-text-area, textarea")
                if editor:
                    editor.fill(query_text)
                    time.sleep(1)
                    scan_btn = page.query_selector("button:has-text('Detect AI'), button:has-text('Scan text'), button:has-text('Scan')")
                    if scan_btn:
                        # JS click: the button is often covered by overlays or
                        # outside the viewport, so Playwright's actionability
                        # checks time out even though the click works.
                        try:
                            scan_btn.evaluate("b => b.click()")
                        except Exception:
                            scan_btn.click()
                        time.sleep(6)

                body_text = page.inner_text("body")

                match_ai = re.search(r'(\d+)%\s*(?:of text is likely AI-generated|AI|probability)', body_text, re.IGNORECASE)
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
                        error="Could not extract score from QuillBot"
                    )

                verdict = "AI" if ai_prob > 65.0 else ("HUMAN" if ai_prob < 25.0 else "MIXED")
                return EngineResult(
                    engine_name=self.name,
                    available=True,
                    ai_percentage=round(ai_prob, 1),
                    human_percentage=round(human_prob, 1),
                    verdict=verdict,
                    weight=self.weight,
                    details={"driver": driver_name, "total_words": len(word_list)}
                )
        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"QuillBot error: {str(e)}"
            )
