"""
Engine 1: ZeroGPT Live Cloud API Engine
Performs live HTTP queries to ZeroGPT detection backend and extracts sentence-level flags.
"""

import json
import urllib.request
import urllib.error
from typing import List, Dict, Any
from .base import BaseEngine
from ..models import EngineResult

class ZeroGPTEngine(BaseEngine):
    name = "ZeroGPT Live Cloud API"
    weight = 0.35

    def analyze(self, text: str, sentences: List[str], words: List[str]) -> EngineResult:
        url = "https://api.zerogpt.com/api/detect/detectText"
        payload = json.dumps({"input_text": text}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Origin": "https://www.zerogpt.com",
            "Referer": "https://www.zerogpt.com/"
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    raw = json.loads(resp.read().decode("utf-8"))
                    data = raw.get("data", {})
                    fake_pct = float(data.get("fakePercentage", 0.0))
                    human_pct = 100.0 - fake_pct
                    feedback = data.get("feedback", "Analysis complete")
                    flagged_sentences = data.get("h", [])

                    verdict = "HUMAN" if fake_pct < 20.0 else ("AI" if fake_pct > 65.0 else "MIXED")

                    return EngineResult(
                        engine_name=self.name,
                        available=True,
                        ai_percentage=round(fake_pct, 1),
                        human_percentage=round(human_pct, 1),
                        verdict=verdict,
                        weight=self.weight,
                        details={
                            "feedback": feedback,
                            "ai_words": data.get("aiWords", 0),
                            "total_words": data.get("textWords", len(words)),
                            "is_human_score": data.get("isHuman", 100)
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
                        error=f"HTTP Status {resp.status}"
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
