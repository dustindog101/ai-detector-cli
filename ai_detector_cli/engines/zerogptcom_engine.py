"""
Engine: ZeroGPT.com Free Web Detector (Patchright / Playwright / Camoufox stealth browser)

Automates https://www.zerogpt.com/ — the zerogpt.com web UI, a distinct site
from the zerogpt.net JSON API used by :class:`ZeroGPTEngine`. The web tool
renders a headline "N% AI GPT*" score plus a verdict sentence
("Your Text is Human written" / "contains mixed signals...") after clicking
"Detect Text". Verified live on 2026-08-30: GPT-written sample scored
"100% AI GPT*", casually-written human sample scored "Human written 0% AI GPT*",
and a mixed document reported the mixed-signals banner.

Why a browser engine: zerogpt.com has no documented public API and gates its
endpoints behind ad-network token flows, so the free tier is only reachable
through a real rendering context. The site accepts 1-15,000 characters per scan.
"""

import re
import time
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult
from ..stealth import get_stealth_browser

MAX_ZGPTCOM_CHARS = 15000
MIN_ZGPTCOM_WORDS = 10

_SET_TEXT_JS = """(t) => {
    const el = document.querySelector("textarea#textArea") ||
               document.querySelector("textarea");
    if (!el) return "NO_EDITOR";
    const st = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype, 'value').set;
    st.call(el, t);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    return "OK";
}"""

_CLICK_DETECT_JS = """() => {
    let b = document.querySelector("button.scoreButton");
    if (!b) {
        const cands = [...document.querySelectorAll('button, input[type=submit]')];
        b = cands.find(x => /detect text/i.test(
            (x.innerText || x.value || '').trim()));
    }
    if (!b) return false;
    b.click();
    return true;
}"""

# Headline score: "100% AI GPT*" / "0% AI GPT*"
_RESULT_RE = re.compile(r"(\d{1,3})\s*%\s*AI\s*GPT", re.IGNORECASE)
# Fallback anchor if the site renames its headline suffix.
_FALLBACK_RE = re.compile(r"(\d{1,3})\s*%\s*AI\b", re.IGNORECASE)


class ZeroGPTComEngine(BaseEngine):
    name = "ZeroGPT.com Web Detector"
    weight = 0.35

    def __init__(self, executable_path: Optional[str] = None, headless: bool = True,
                 timeout_ms: int = 45000, driver: Optional[str] = None):
        self.executable_path = executable_path
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.driver = driver

    def analyze(self, text: str, sentences: List[str] = None,
                words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return self._unavailable("Input text is empty")

        word_list = words if words else text.split()
        if len(word_list) < MIN_ZGPTCOM_WORDS:
            return self._unavailable(
                "ZeroGPT.com requires at least %d words (provided: %d)."
                % (MIN_ZGPTCOM_WORDS, len(word_list)))

        query_text = " ".join(word_list)[:MAX_ZGPTCOM_CHARS]

        try:
            with get_stealth_browser(headless=self.headless,
                                     executable_path=self.executable_path,
                                     driver=self.driver) as (browser, page, driver_name):
                page.goto("https://www.zerogpt.com/",
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

                status = page.evaluate(_SET_TEXT_JS, query_text)
                if status != "OK":
                    return self._unavailable(
                        "ZeroGPT.com editor not found (%s)" % status)
                time.sleep(1.5)

                clicked = False
                for _ in range(3):
                    if page.evaluate(_CLICK_DETECT_JS):
                        clicked = True
                        break
                    time.sleep(2)
                if not clicked:
                    return self._unavailable(
                        "ZeroGPT.com 'Detect Text' button not found")

                # Poll the rendered result for up to ~60 s; re-click once at
                # ~20 s in case the first submit was swallowed by the ad stack.
                ai_pct = None
                deadline = time.time() + 60
                recliked = False
                while time.time() < deadline:
                    time.sleep(3)
                    body = page.inner_text("body")
                    m = _RESULT_RE.search(body) or _FALLBACK_RE.search(body)
                    if m:
                        ai_pct = float(m.group(1))
                        break
                    if (not recliked and deadline - time.time() < 40):
                        try:
                            page.evaluate(_CLICK_DETECT_JS)
                        except Exception:
                            pass
                        recliked = True
                if ai_pct is None:
                    return self._unavailable(
                        "ZeroGPT.com result did not render in time "
                        "(timeout or rate limit)")

                low = body.lower()
                if (("human written" in low or "is human" in low)
                        and ai_pct < 25.0):
                    verdict = "HUMAN"
                elif ai_pct > 65.0:
                    verdict = "AI"
                elif ai_pct < 25.0:
                    verdict = "HUMAN"
                else:
                    verdict = "MIXED"

                return EngineResult(
                    engine_name=self.name,
                    available=True,
                    ai_percentage=round(ai_pct, 1),
                    human_percentage=round(100.0 - ai_pct, 1),
                    verdict=verdict,
                    weight=self.weight,
                    details={"driver": driver_name,
                             "total_words": len(word_list),
                             "chars_sent": len(query_text)},
                )
        except Exception as exc:
            return self._unavailable("ZeroGPT.com error: %s" % str(exc))

    def _unavailable(self, reason: str) -> EngineResult:
        return EngineResult(
            engine_name=self.name, available=False,
            ai_percentage=0.0, human_percentage=100.0,
            verdict="UNAVAILABLE", weight=0.0, error=reason)
