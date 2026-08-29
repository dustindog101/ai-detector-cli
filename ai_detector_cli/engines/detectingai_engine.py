"""
Engine: Detecting-AI.com REST API (premium, key-based)
Detecting-AI offers a REST AI detector with a free API tier (v1/v2/v3 model
versions; v3 is recommended for new integrations).

Endpoint reference (verified alive 2026-08-29):
  POST https://api.detecting-ai.com/api/detect/
  Header: X-API-Key: <DETECTING_AI_API_KEY>
  Body:   {"text": "<text>", "version": "v3"}
  Response: {success: true, data: {details: {result: <analysis>},
            version: "v3", words_processed: N}}
  Notes: the documented response wraps the analysis inside
  data.details.result; the exact inner shape varies, so the parser handles
  both structured dicts and textual results (percentage extraction).

Environment:
  DETECTING_AI_API_KEY - API key from https://detecting-ai.com
"""

import os
import re
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult
from ..http_client import post_json_parsed, get_default_timeout

MAX_DETECTINGAI_CHARS = 20000
DETECTINGAI_URL = "https://api.detecting-ai.com/api/detect/"

_AI_PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%", re.IGNORECASE)
_AI_NEAR_RE = re.compile(r"ai", re.IGNORECASE)


class DetectingAIEngine(BaseEngine):
    name = "Detecting-AI API"
    key = "detecting-ai"
    weight = 0.20

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = None, retries: int = 2):
        self.api_key = api_key or os.environ.get("DETECTING_AI_API_KEY", "").strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else get_default_timeout()
        self.retries = retries

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _extract_ai_pct(result) -> Optional[float]:
        """Pull the AI percentage out of either a structured or textual result."""
        if isinstance(result, dict):
            for k in ("ai", "aiScore", "ai_score", "aiPercentage", "ai_percentage", "fake", "aiProbability"):
                if k in result:
                    try:
                        v = float(result[k])
                        return v * 100.0 if v <= 1.0 else v
                    except (TypeError, ValueError):
                        continue
            return None
        if isinstance(result, str):
            matches = list(_AI_PERCENT_RE.finditer(result))
            if not matches:
                return None
            ai_mentions = [m for m in _AI_NEAR_RE.finditer(result)]
            best = None
            for m in matches:
                for ai in ai_mentions:
                    if abs(m.start() - ai.start()) <= 60:
                        best = m
                        break
                if best:
                    break
            if best is None and len(matches) == 1:
                best = matches[0]
            if best is None:
                return None
            try:
                return float(best.group(1))
            except (TypeError, ValueError):
                return None
        return None

    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return self._unavailable("Input text is empty")
        if not self.api_key:
            return self._unavailable(
                "DETECTING_AI_API_KEY not set - get a key at https://detecting-ai.com"
            )

        query_text = text[:MAX_DETECTINGAI_CHARS]
        is_truncated = len(text) > MAX_DETECTINGAI_CHARS

        try:
            status, raw, elapsed_ms = post_json_parsed(
                DETECTINGAI_URL,
                {"text": query_text, "version": "v3"},
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.api_key,
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
                retries=self.retries,
            )
            if status in (401, 403):
                return self._unavailable(
                    f"Authentication failed (HTTP {status}) - check DETECTING_AI_API_KEY"
                )
            if status != 200 or not isinstance(raw, dict):
                return self._unavailable(f"HTTP Status {status}")
            if not raw.get("success", True):
                return self._unavailable(f"API reported failure: {raw.get('error') or 'unknown'}")

            data = raw.get("data") or {}
            details = data.get("details") or {}
            result = details.get("result", details if not isinstance(details, dict) else None)
            ai_pct = self._extract_ai_pct(result)
            if ai_pct is None:
                return self._unavailable("Could not parse AI percentage from Detecting-AI response")

            ai_pct = min(99.9, max(0.0, ai_pct))
            verdict = "HUMAN" if ai_pct < 20.0 else ("AI" if ai_pct > 65.0 else "MIXED")

            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=round(ai_pct, 1),
                human_percentage=round(100.0 - ai_pct, 1),
                verdict=verdict,
                weight=self.weight,
                details={
                    "api_version": data.get("version") or raw.get("version"),
                    "words_processed": data.get("words_processed"),
                    "latency_ms": round(elapsed_ms, 1),
                    "truncated": is_truncated,
                },
            )
        except Exception as e:
            return self._unavailable(str(e))

    @staticmethod
    def _unavailable(error: str) -> EngineResult:
        return EngineResult(
            engine_name=DetectingAIEngine.name,
            available=False,
            ai_percentage=0.0,
            human_percentage=100.0,
            verdict="UNAVAILABLE",
            weight=0.0,
            error=error,
        )
