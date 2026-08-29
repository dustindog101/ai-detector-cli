"""
Engine: GPTZero Official REST API (premium, key-based)
GPTZero is the most widely adopted academic AI detector (built for teachers and
institutions). This engine talks directly to the official API endpoint - no
browser needed, runs in parallel with the other HTTP engines.

Endpoint reference (verified alive 2026-08-29):
  POST https://api.gptzero.me/v2/predict/text
  Header: X-Api-Key: <GPTZERO_API_KEY>
  Body:   {"document": "<text>"}
  Response: {documents: [{completely_generated_prob, average_generated_prob,
            predicted_class, confidence_score, sentences: [{sentence, generated_prob}]}]}
  Notes: free tier ~10k words/month. Invalid keys return 403
  {"error": "API key has no owner"}. Sentence objects expose generated_prob
  (0-1) which we use for per-sentence cloud flags.

Environment:
  GPTZERO_API_KEY  - API key from https://dashboard.gptzero.me (free tier available)
"""

import os
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult
from ..http_client import post_json_parsed, get_default_timeout

MAX_GPTZERO_CHARS = 50000
GPTZERO_URL = "https://api.gptzero.me/v2/predict/text"
SENTENCE_AI_FLAG_THRESHOLD = 0.65  # generated_prob above which a sentence is flagged


class GPTZeroApiEngine(BaseEngine):
    name = "GPTZero Official API"
    key = "gptzero-api"
    weight = 0.40

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = None, retries: int = 2):
        self.api_key = api_key or os.environ.get("GPTZERO_API_KEY", "").strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else get_default_timeout()
        self.retries = retries

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return self._unavailable("Input text is empty")
        if not self.api_key:
            return self._unavailable(
                "GPTZERO_API_KEY not set - get a free key at https://dashboard.gptzero.me"
            )

        query_text = text[:MAX_GPTZERO_CHARS]
        is_truncated = len(text) > MAX_GPTZERO_CHARS

        try:
            status, raw, elapsed_ms = post_json_parsed(
                GPTZERO_URL,
                {"document": query_text},
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": self.api_key,
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
                retries=self.retries,
            )
            if status in (401, 403):
                return self._unavailable(
                    f"Authentication failed (HTTP {status}) - check GPTZERO_API_KEY"
                )
            if status != 200 or not isinstance(raw, dict):
                return self._unavailable(f"HTTP Status {status}")

            documents = raw.get("documents") or []
            doc = documents[0] if documents else {}
            if not doc:
                return self._unavailable("Empty document list in GPTZero response")

            predicted_class = str(doc.get("predicted_class") or doc.get("classification") or "").lower()
            completely_prob = float(doc.get("completely_generated_prob") or 0.0)
            average_prob = float(doc.get("average_generated_prob") or 0.0)

            # Map GPTZero's class probabilities onto the 0-100 AI scale.
            if "ai-only" in predicted_class or predicted_class == "ai":
                ai_pct = completely_prob * 100.0
            elif "mixed" in predicted_class:
                ai_pct = (completely_prob + average_prob) / 2.0 * 100.0
            elif "human" in predicted_class:
                ai_pct = min(completely_prob, 0.45) * 100.0
            else:
                ai_pct = max(completely_prob, average_prob) * 100.0
            ai_pct = min(99.9, max(0.0, ai_pct))

            verdict = "HUMAN" if ai_pct < 20.0 else ("AI" if ai_pct > 65.0 else "MIXED")

            flagged = []
            for sent in doc.get("sentences") or []:
                try:
                    if float(sent.get("generated_prob") or 0.0) >= SENTENCE_AI_FLAG_THRESHOLD:
                        flag_text = (sent.get("sentence") or "").strip()
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
                    "predicted_class": predicted_class or "unknown",
                    "completely_generated_prob": completely_prob,
                    "average_generated_prob": average_prob,
                    "confidence_score": doc.get("confidence_score"),
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
            engine_name=GPTZeroApiEngine.name,
            available=False,
            ai_percentage=0.0,
            human_percentage=100.0,
            verdict="UNAVAILABLE",
            weight=0.0,
            error=error,
        )
