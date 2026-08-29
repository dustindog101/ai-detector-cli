"""
Engine: Winston AI REST API (premium, key-based)
Winston AI (gowinston.ai) markets the highest claimed detection accuracy
(99.98%) and is popular in education/publishing. Direct API integration - no
browser needed.

Endpoint reference (verified alive 2026-08-29):
  POST https://api.gowinston.ai/v1/ai-content-detection
  Header: Authorization: Bearer <WINSTON_API_KEY>
  Body:   {"text": "<text>", "version": "2.0"}
  Response: {score: <AI probability>, sentences: [{text, score}], ...}
  Notes: invalid keys return 401 {"error": "ERROR_RETRIEVING_USER"}.
  The score field is an AI probability; the API has historically returned
  both 0-1 fractions and 0-100 percentages across versions, so the parser
  normalizes defensively. 3-day free trial available.

Environment:
  WINSTON_API_KEY  - API key from https://gowinston.ai
"""

import os
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult
from ..http_client import post_json_parsed, get_default_timeout

MAX_WINSTON_CHARS = 30000
WINSTON_URL = "https://api.gowinston.ai/v1/ai-content-detection"
SENTENCE_AI_FLAG_THRESHOLD = 0.65


def _to_percent(value) -> float:
    """Normalize a 0-1 fraction or 0-100 percentage to 0-100."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return v * 100.0 if v <= 1.0 else v


class WinstonEngine(BaseEngine):
    name = "Winston AI API"
    key = "winston"
    weight = 0.30

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = None, retries: int = 2):
        self.api_key = api_key or os.environ.get("WINSTON_API_KEY", "").strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else get_default_timeout()
        self.retries = retries

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return self._unavailable("Input text is empty")
        if not self.api_key:
            return self._unavailable(
                "WINSTON_API_KEY not set - get a key at https://gowinston.ai"
            )

        query_text = text[:MAX_WINSTON_CHARS]
        is_truncated = len(text) > MAX_WINSTON_CHARS

        try:
            status, raw, elapsed_ms = post_json_parsed(
                WINSTON_URL,
                {"text": query_text, "version": "2.0"},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
                retries=self.retries,
            )
            if status in (401, 403):
                return self._unavailable(
                    f"Authentication failed (HTTP {status}) - check WINSTON_API_KEY"
                )
            if status != 200 or not isinstance(raw, dict):
                return self._unavailable(f"HTTP Status {status}")

            ai_pct: Optional[float] = None
            ai_detection = raw.get("ai_detection")
            if isinstance(ai_detection, dict):
                ai_pct = _to_percent(ai_detection.get("ai_score") or ai_detection.get("score"))
            if ai_pct is None or ai_pct == 0.0:
                # primary "score" field (may be absent from error payloads)
                if raw.get("score") is not None:
                    ai_pct = _to_percent(raw.get("score"))
            if ai_pct is None:
                return self._unavailable("Unrecognized Winston AI response shape")

            ai_pct = min(99.9, max(0.0, ai_pct))
            verdict = "HUMAN" if ai_pct < 20.0 else ("AI" if ai_pct > 65.0 else "MIXED")

            flagged = []
            for sent in raw.get("sentences") or []:
                if not isinstance(sent, dict):
                    continue
                score = sent.get("ai_score", sent.get("score"))
                try:
                    if _to_percent(score) >= SENTENCE_AI_FLAG_THRESHOLD * 100.0:
                        flag_text = (sent.get("text") or "").strip()
                        if flag_text:
                            flagged.append(flag_text)
                except (TypeError, ValueError):
                    continue

            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=round(ai_pct, 1),
                human_percentage=round(100.0 - ai_pct, 1),
                verdict=verdict,
                weight=self.weight,
                details={
                    "result": raw.get("result"),
                    "words": raw.get("words"),
                    "flagged_sentence_count": len(flagged),
                    "latency_ms": round(elapsed_ms, 1),
                    "truncated": is_truncated,
                },
                flagged_sentences=flagged,
            )
        except Exception as e:
            return self._unavailable(str(e))

    @staticmethod
    def _unavailable(error: str) -> EngineResult:
        return EngineResult(
            engine_name=WinstonEngine.name,
            available=False,
            ai_percentage=0.0,
            human_percentage=100.0,
            verdict="UNAVAILABLE",
            weight=0.0,
            error=error,
        )
