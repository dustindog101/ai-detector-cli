"""
Engine: Originality.ai REST API (premium, key-based)
Originality.ai is the publisher/agency standard for AI detection with some of
the lowest false-positive rates on long-form content. Direct API integration.

Endpoint reference (verified alive 2026-08-29):
  POST https://api.originality.ai/api/v1/scan/ai
  Header: X-OAI-API-Key: <ORIGINALITY_API_KEY>
  Body:   {"content": "<text>", "aiModelVersion": "1.0.0", "storeScan": "false"}
  Response: {ai_score: {fake: <0-1>, clear: <0-1>}, version, credits_used, ...}
  Notes: requires a paid/enterprise subscription (422 "Enterprise Subscription
  Required" on free plans - endpoint and auth shape verified working).

Environment:
  ORIGINALITY_API_KEY - API key from https://app.originality.ai/api-access
"""

import os
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult
from ..http_client import post_json_parsed, get_default_timeout

MAX_ORIGINALITY_CHARS = 50000
ORIGINALITY_URL = "https://api.originality.ai/api/v1/scan/ai"


class OriginalityEngine(BaseEngine):
    name = "Originality.ai API"
    key = "originality"
    weight = 0.35

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = None, retries: int = 2):
        self.api_key = api_key or os.environ.get("ORIGINALITY_API_KEY", "").strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else get_default_timeout()
        self.retries = retries

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return self._unavailable("Input text is empty")
        if not self.api_key:
            return self._unavailable(
                "ORIGINALITY_API_KEY not set - get a key at https://app.originality.ai/api-access"
            )

        query_text = text[:MAX_ORIGINALITY_CHARS]
        is_truncated = len(text) > MAX_ORIGINALITY_CHARS

        try:
            status, raw, elapsed_ms = post_json_parsed(
                ORIGINALITY_URL,
                {"content": query_text, "aiModelVersion": "1.0.0", "storeScan": "false"},
                headers={
                    "Content-Type": "application/json",
                    "X-OAI-API-Key": self.api_key,
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
                retries=self.retries,
            )
            if status in (401, 403):
                return self._unavailable(
                    f"Authentication failed (HTTP {status}) - check ORIGINALITY_API_KEY"
                )
            if status == 422:
                msg = (raw or {}).get("error") if isinstance(raw, dict) else None
                return self._unavailable(
                    msg or "Originality.ai requires a paid subscription for API access (HTTP 422)"
                )
            if status != 200 or not isinstance(raw, dict):
                return self._unavailable(f"HTTP Status {status}")

            ai_score = raw.get("ai_score")
            if isinstance(ai_score, dict):
                fake = ai_score.get("fake")
            else:
                fake = ai_score  # some versions return a bare fraction
            if fake is None:
                return self._unavailable("Missing ai_score.fake in Originality.ai response")

            ai_pct = min(99.9, max(0.0, float(fake) * 100.0))
            verdict = "HUMAN" if ai_pct < 20.0 else ("AI" if ai_pct > 65.0 else "MIXED")

            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=round(ai_pct, 1),
                human_percentage=round(100.0 - ai_pct, 1),
                verdict=verdict,
                weight=self.weight,
                details={
                    "model_version": raw.get("version"),
                    "credits_used": raw.get("credits_used"),
                    "latency_ms": round(elapsed_ms, 1),
                    "truncated": is_truncated,
                },
            )
        except Exception as e:
            return self._unavailable(str(e))

    @staticmethod
    def _unavailable(error: str) -> EngineResult:
        return EngineResult(
            engine_name=OriginalityEngine.name,
            available=False,
            ai_percentage=0.0,
            human_percentage=100.0,
            verdict="UNAVAILABLE",
            weight=0.0,
            error=error,
        )
