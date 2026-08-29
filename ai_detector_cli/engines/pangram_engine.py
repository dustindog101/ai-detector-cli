"""
Engine: Pangram Labs REST API (premium, key-based)
Pangram is consistently the top scorer in third-party AI-text benchmarks
(rugged against paraphrasing/humanizer attacks, near-zero false positives on
human writing). Uses an async two-step task API.

Endpoint reference (verified alive 2026-08-29):
  Step 1: POST https://text.external-api.pangram.com/task
          Header: x-api-key: <PANGRAM_API_KEY>
          Body:   {"text": "<text>", "public_dashboard_link": false}
          Response: {task_id: "<uuid>"}
  Step 2: GET https://text.external-api.pangram.com/task/<task_id>  (poll)
          Response: {stage: "STAGE_SUCCESS"|"STAGE_FAILED"|...,
                     fraction_ai: <0-1>, fraction_ai_assisted: <0-1>,
                     fraction_human: <0-1>, prediction_short, headline,
                     ai_segments: [{text, ...}], num_ai_segments}
  Notes: invalid keys return 401 {"detail": "Invalid API key"}. Free tier
  available for testing. Poll interval 0.75s, ~18s worst case.

Environment:
  PANGRAM_API_KEY - API key from https://www.pangram.com
"""

import os
import time
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult
from ..http_client import request, get_default_timeout

MAX_PANGRAM_CHARS = 40000
PANGRAM_BASE = "https://text.external-api.pangram.com"
POLL_INTERVAL_SECONDS = 0.75
MAX_POLLS = 24


class PangramEngine(BaseEngine):
    name = "Pangram API"
    key = "pangram"
    weight = 0.45

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = None, retries: int = 2):
        self.api_key = api_key or os.environ.get("PANGRAM_API_KEY", "").strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else get_default_timeout()
        self.retries = retries

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return self._unavailable("Input text is empty")
        if not self.api_key:
            return self._unavailable(
                "PANGRAM_API_KEY not set - get a key at https://www.pangram.com"
            )

        query_text = text[:MAX_PANGRAM_CHARS]
        is_truncated = len(text) > MAX_PANGRAM_CHARS
        started = time.monotonic()

        try:
            # Step 1: create the async detection task
            resp = request(
                f"{PANGRAM_BASE}/task",
                method="POST",
                payload={"text": query_text, "public_dashboard_link": False},
                headers=self._headers(),
                timeout=self.timeout_seconds,
                retries=self.retries,
            )
            if resp.status in (401, 403):
                return self._unavailable(
                    f"Authentication failed (HTTP {resp.status}) - check PANGRAM_API_KEY"
                )
            if resp.status != 200:
                return self._unavailable(f"Task creation returned HTTP {resp.status}")
            created = resp.json()
            task_id = (created or {}).get("task_id") if isinstance(created, dict) else None
            if not task_id:
                return self._unavailable("No task_id in Pangram response")

            # Step 2: poll until the task reaches a terminal stage
            result = None
            for _ in range(MAX_POLLS):
                time.sleep(POLL_INTERVAL_SECONDS)
                poll = request(
                    f"{PANGRAM_BASE}/task/{task_id}",
                    method="GET",
                    headers=self._headers(),
                    timeout=self.timeout_seconds,
                    retries=self.retries,
                )
                if poll.status != 200:
                    return self._unavailable(f"Task polling returned HTTP {poll.status}")
                data = poll.json()
                if not isinstance(data, dict):
                    continue
                stage = data.get("stage", "")
                if stage == "STAGE_SUCCESS":
                    result = data
                    break
                if stage == "STAGE_FAILED":
                    return self._unavailable("Pangram task failed (STAGE_FAILED)")

            if result is None:
                return self._unavailable("Pangram task timed out while polling")

            elapsed_ms = (time.monotonic() - started) * 1000.0

            fraction_ai = float(result.get("fraction_ai") or 0.0)
            fraction_assisted = float(result.get("fraction_ai_assisted") or 0.0)
            ai_pct = min(99.9, max(0.0, fraction_ai * 100.0))
            verdict = "HUMAN" if ai_pct < 20.0 else ("AI" if ai_pct > 65.0 else "MIXED")

            flagged = []
            for seg in result.get("ai_segments") or []:
                if isinstance(seg, dict):
                    seg_text = (seg.get("text") or "").strip()
                    if seg_text:
                        flagged.append(seg_text)

            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=round(ai_pct, 1),
                human_percentage=round(100.0 - ai_pct, 1),
                verdict=verdict,
                weight=self.weight,
                details={
                    "headline": result.get("headline"),
                    "prediction_short": result.get("prediction_short"),
                    "fraction_ai_assisted": round(fraction_assisted, 4),
                    "fraction_human": result.get("fraction_human"),
                    "num_ai_segments": result.get("num_ai_segments", len(flagged)),
                    "api_version": result.get("version"),
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
            engine_name=PangramEngine.name,
            available=False,
            ai_percentage=0.0,
            human_percentage=100.0,
            verdict="UNAVAILABLE",
            weight=0.0,
            error=error,
        )
