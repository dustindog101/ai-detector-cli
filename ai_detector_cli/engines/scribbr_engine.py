"""
Engine: Scribbr Playwright AI Detector (with Patchright Stealth)
Automates https://www.scribbr.com/ai-detector/ using Patchright stealth browser.
Extracts AI likelihood percentage, verdict, and highlighted text.
"""

import re
import time
from typing import List, Optional
from .base import BaseEngine
from ..models import EngineResult
from ..stealth import get_stealth_browser

MAX_SCRIBBR_WORDS = 1100

class ScribbrEngine(BaseEngine):
    name = "Scribbr AI Detector"
    weight = 0.35

    def __init__(self, executable_path: Optional[str] = None, headless: bool = True, timeout_ms: int = 35000):
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
        query_text = " ".join(word_list[:MAX_SCRIBBR_WORDS])

        try:
            with get_stealth_browser(headless=self.headless, executable_path=self.executable_path) as (browser, page, driver_name):
                page.goto("https://www.scribbr.com/ai-detector/", timeout=self.timeout_ms, wait_until="domcontentloaded")
                time.sleep(3)

                # Cookie dismiss
                for btn_text in ["Accept All", "Accept Cookies", "Agree", "I accept"]:
                    try:
                        btn = page.query_selector(f"button:has-text('{btn_text}')")
                        if btn:
                            btn.click()
                            time.sleep(0.5)
                            break
                    except Exception:
                        pass

                editor = page.query_selector("textarea, div[contenteditable='true'], [role='textbox']")
                if editor:
                    editor.fill(query_text)
                    time.sleep(1)
                    scan_btn = page.query_selector("button:has-text('Scan text'), button:has-text('Check for AI'), button:has-text('Detect')")
                    if scan_btn:
                        scan_btn.click()
                        time.sleep(6)

                body_text = page.inner_text("body")

                match_ai = re.search(r'(\d+)%\s*(?:AI|chance|probability)', body_text, re.IGNORECASE)
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
                        error="Could not extract score from Scribbr"
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
                error=f"Scribbr error: {str(e)}"
            )
