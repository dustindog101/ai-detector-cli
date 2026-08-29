"""
Engine 1: ZeroGPT Live Cloud API Engine
Performs live HTTP queries to ZeroGPT detection backend and extracts sentence-level flags.
Safely handles document size limits (max 14,000 chars).

Endpoint reference (verified 2026-08-29):
  POST https://api.zerogpt.com/api/detect/detectText
  Body: {"input_text": "<text>"}
  Response: {data: {fakePercentage, isHuman, textWords, aiWords, feedback,
                    h (flagged sentences), sentences, detected_language}}
  Notes: browser-like Origin/Referer headers required; short inputs (<30 words)
  return isHuman=50 with "input more text" feedback.
"""

import json
from typing import List

from .base import BaseEngine
from ..models import EngineResult
from ..http_client import post_json_parsed

MAX_ZEROGPT_CHARS = 14000
ZEROGPT_URL = "https://api.zerogpt.com/api/detect/detectText"

_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.zerogpt.com",
    "Referer": "https://www.zerogpt.com/",
    "Accept": "application/json",
}


class ZeroGPTEngine(BaseEngine):
    name = "ZeroGPT Live Cloud API"
    weight = 0.35

    def __init__(self, timeout_seconds: float = None, retries: int = 2):
        from ..http_client import get_default_timeout
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else get_default_timeout()
        self.retries = retries

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

        # Safe truncation for large documents
        query_text = text[:MAX_ZEROGPT_CHARS]
        is_truncated = len(text) > MAX_ZEROGPT_CHARS

        try:
            status, raw, elapsed_ms = post_json_parsed(
                ZEROGPT_URL,
                {"input_text": query_text},
                headers=_HEADERS,
                timeout=self.timeout_seconds,
                retries=self.retries,
            )
            if status != 200 or not isinstance(raw, dict):
                return self._unavailable(f"HTTP Status {status}")

            data = raw.get("data") or {}
            fake_pct = float(data.get("fakePercentage", 0.0))
            human_pct = 100.0 - fake_pct
            feedback = data.get("feedback", "Analysis complete")
            flagged_sentences = data.get("h", []) or []

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
                    "total_words": data.get("textWords", len(words) if words else len(text.split())),
                    "is_human_score": data.get("isHuman", 100),
                    "detected_language": data.get("detected_language", "unknown"),
                    "latency_ms": round(elapsed_ms, 1),
                    "truncated": is_truncated
                },
                flagged_sentences=flagged_sentences
            )
        except Exception as e:
            return self._unavailable(str(e))

    @staticmethod
    def _unavailable(error: str) -> EngineResult:
        return EngineResult(
            engine_name=ZeroGPTEngine.name,
            available=False,
            ai_percentage=0.0,
            human_percentage=100.0,
            verdict="UNAVAILABLE",
            weight=0.0,
            error=error
        )
