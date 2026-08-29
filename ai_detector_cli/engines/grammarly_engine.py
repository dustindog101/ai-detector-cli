"""
Engine: Grammarly Free AI Detector (Playwright/Patchright stealth browser)

Automates https://www.grammarly.com/ai-detector — Grammarly's public free
AI checker — and extracts the AI-generated / human-generated percentages
from the rendered result panel. Verified live on 2026-08-29: AI-written
sample scored 100% AI-generated, human sample scored 99% human-generated.
"""

import re
import time
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult
from ..stealth import get_stealth_browser

MAX_GRAMMARLY_CHARS = 5000
MIN_GRAMMARLY_WORDS = 12

_SET_VALUE_JS = """(t) => {
    const el = document.querySelector("textarea, div[contenteditable='true']");
    if (!el) return "NO_EDITOR";
    if (el.tagName === 'TEXTAREA') {
        const st = Object.getOwnPropertyDescriptor(
            HTMLTextAreaElement.prototype, 'value').set;
        st.call(el, t);
    } else {
        el.textContent = t;
    }
    el.dispatchEvent(new Event('input', {bubbles: true}));
    return "OK";
}"""

_CLICK_SCAN_JS = """() => {
    const els = [...document.querySelectorAll('button')];
    const b = els.find(x =>
        x.textContent.trim().toLowerCase() === 'scan for ai');
    if (b) { b.click(); return true; }
    return false;
}"""


class GrammarlyEngine(BaseEngine):
    name = "Grammarly AI Detector"
    weight = 0.55

    def __init__(self, executable_path: Optional[str] = None, headless: bool = True,
                 timeout_ms: int = 45000):
        self.executable_path = executable_path
        self.headless = headless
        self.timeout_ms = timeout_ms

    def analyze(self, text: str, sentences: List[str] = None,
                words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return EngineResult(
                engine_name=self.name, available=False,
                ai_percentage=0.0, human_percentage=100.0,
                verdict="UNAVAILABLE", weight=0.0, error="Input text is empty")

        word_list = words if words else text.split()
        if len(word_list) < MIN_GRAMMARLY_WORDS:
            return EngineResult(
                engine_name=self.name, available=False,
                ai_percentage=0.0, human_percentage=100.0,
                verdict="UNAVAILABLE", weight=0.0,
                error=(f"Grammarly requires at least {MIN_GRAMMARLY_WORDS} words "
                       f"(provided: {len(word_list)})."))

        query_text = " ".join(word_list)[:MAX_GRAMMARLY_CHARS]

        try:
            with get_stealth_browser(headless=self.headless,
                                     executable_path=self.executable_path) as (browser, page, driver_name):
                page.goto("https://www.grammarly.com/ai-detector",
                          timeout=self.timeout_ms, wait_until="domcontentloaded")
                time.sleep(4)

                # Dismiss consent banners if present.
                for cookie_sel in ["button:has-text('Accept All')",
                                   "button:has-text('Accept')",
                                   "#onetrust-accept-btn-handler",
                                   "button:has-text('I agree')"]:
                    try:
                        btn = page.query_selector(cookie_sel)
                        if btn and btn.is_visible():
                            btn.click()
                            time.sleep(0.5)
                            break
                    except Exception:
                        pass

                status = page.evaluate(_SET_VALUE_JS, query_text)
                if status != "OK":
                    return self._unavailable(f"Grammarly editor not found ({status})")
                time.sleep(1.5)

                clicked = False
                for _ in range(3):
                    if page.evaluate(_CLICK_SCAN_JS):
                        clicked = True
                        break
                    time.sleep(2)
                if not clicked:
                    return self._unavailable("Grammarly 'Scan for AI' button not found")

                # Poll the rendered result for up to ~30 s.
                ai_pct = None
                human_pct = None
                deadline = time.time() + 30
                while time.time() < deadline:
                    time.sleep(3)
                    body = page.inner_text("body")
                    m = re.search(r'AI-generated\s*:?\s*(\d{1,3})\s*%', body, re.IGNORECASE)
                    if not m:
                        m = re.search(r'(\d{1,3})\s*%\s*AI-generated', body, re.IGNORECASE)
                    if m:
                        ai_pct = float(m.group(1))
                        mh = (re.search(r'Human-generated\s*:?\s*(\d{1,3})\s*%', body,
                                        re.IGNORECASE)
                              or re.search(r'(\d{1,3})\s*%\s*Human-generated', body,
                                           re.IGNORECASE))
                        if mh:
                            human_pct = float(mh.group(1))
                        break
                if ai_pct is None:
                    return self._unavailable(
                        "Grammarly result did not render in time (timeout or rate limit)")

                if human_pct is None:
                    human_pct = 100.0 - ai_pct

                verdict = ("AI" if ai_pct > 65.0
                           else ("HUMAN" if ai_pct < 25.0 else "MIXED"))
                return EngineResult(
                    engine_name=self.name,
                    available=True,
                    ai_percentage=round(ai_pct, 1),
                    human_percentage=round(human_pct, 1),
                    verdict=verdict,
                    weight=self.weight,
                    details={"driver": driver_name,
                             "total_words": len(word_list),
                             "chars_sent": len(query_text)},
                )
        except Exception as exc:
            return EngineResult(
                engine_name=self.name, available=False,
                ai_percentage=0.0, human_percentage=100.0,
                verdict="UNAVAILABLE", weight=0.0,
                error=f"Grammarly error: {str(exc)}")

    def _unavailable(self, reason: str) -> EngineResult:
        return EngineResult(
            engine_name=self.name, available=False,
            ai_percentage=0.0, human_percentage=100.0,
            verdict="UNAVAILABLE", weight=0.0, error=reason)
