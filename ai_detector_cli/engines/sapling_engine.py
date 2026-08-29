"""
Engine: Sapling AI Content Detector (Blazing-Fast Direct HTTP with Chunking)
Directly queries https://api.sapling.ai/api/v1/aidetect with sentence-level extraction.

Endpoint reference (verified 2026-08-29):
  POST https://api.sapling.ai/api/v1/aidetect
  Body: {"text": "<text>", "key": "<jwt>", "sent_scores": true}
  Response: {score (0..1, higher = AI), score_string (HTML spans),
             sentence_scores: [{sentence, score}], hash, premium, used_tokens}
  Limits: ~1,950 chars per request. Longer documents are automatically split
  into sentence-boundary chunks and sent concurrently; scores are merged
  weighted by chunk length.

The bundled public web key expires periodically; override it any time with the
SAPLING_API_KEY environment variable.
"""

import os
import re
import json
from typing import List, Optional

from .base import BaseEngine
from ..models import EngineResult
from ..http_client import post_json_parsed

MAX_SAPLING_CHARS = 1900  # safety margin below the 1,950 hard limit
SAPLING_URL = "https://api.sapling.ai/api/v1/aidetect"

PUBLIC_SAPLING_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjbEU0RnJKYXlUSnhYTjZSM19fbVd3VFEzSERIV2dDUmZkT19TSFJDMWFfeWRTWV9YMDhseFpJNnRrM3lEMkZFVGNuM0FHZ0R1emNkaHJXQjdNV0Z5USUzRCUzRCIsImV4cCI6MTc4ODMxNjQwNn0.VZkUB-ZtTU-QfpAyAMC45piYluD0eFt89FkW9I-0jjs"

_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://sapling.ai",
    "Referer": "https://sapling.ai/",
    "Accept": "application/json",
}

_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


class SaplingEngine(BaseEngine):
    name = "Sapling AI Detector"
    weight = 0.35

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: float = None,
        retries: int = 2,
        max_concurrent_chunks: int = 4
    ):
        from ..http_client import get_default_timeout
        self.api_key = api_key or os.environ.get("SAPLING_API_KEY") or PUBLIC_SAPLING_KEY
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else get_default_timeout()
        self.retries = retries
        self.max_concurrent_chunks = max_concurrent_chunks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return self._unavailable("Input text is empty")

        chunks = self._chunk_text(text)
        if not chunks:
            return self._unavailable("No analyzable content")

        if len(chunks) == 1:
            return self._analyze_chunk(chunks[0], chunk_meta={"chunk_count": 1, "truncated": False})

        # Multiple chunks: send concurrently and merge results.
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        errors = []
        with ThreadPoolExecutor(max_workers=min(self.max_concurrent_chunks, len(chunks))) as pool:
            future_map = {pool.submit(self._analyze_chunk, ch, None): ch for ch in chunks}
            for fut in as_completed(future_map):
                res = fut.result()
                if res.available:
                    results.append((future_map[fut], res))
                else:
                    errors.append(res.error)

        if not results:
            return self._unavailable(errors[0] if errors else "All chunk requests failed")

        total_chars = sum(len(ch) for ch, _ in results)
        merged_ai = sum(res.ai_percentage * len(ch) for ch, res in results) / total_chars
        merged_flags = []
        for _, res in results:
            merged_flags.extend(res.flagged_sentences)

        avg_latency = sum(res.details.get("latency_ms", 0) for _, res in results) / len(results)
        verdict = "HUMAN" if merged_ai < 25.0 else ("AI" if merged_ai > 65.0 else "MIXED")

        return EngineResult(
            engine_name=self.name,
            available=True,
            ai_percentage=round(merged_ai, 1),
            human_percentage=round(100.0 - merged_ai, 1),
            verdict=verdict,
            weight=self.weight,
            details={
                "chunk_count": len(chunks),
                "chunks_ok": len(results),
                "chunks_failed": len(errors),
                "avg_latency_ms": round(avg_latency, 1),
                "method": "chunked_http",
            },
            flagged_sentences=merged_flags
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into <=MAX_SAPLING_CHARS chunks at sentence boundaries."""
        text = text.strip()
        if len(text) <= MAX_SAPLING_CHARS:
            return [text]

        sentences = [s for s in _SPLIT_RE.split(text) if s.strip()]
        chunks, current = [], ""
        for sentence in sentences:
            # A single over-long sentence is hard-split.
            while len(sentence) > MAX_SAPLING_CHARS:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(sentence[:MAX_SAPLING_CHARS])
                sentence = sentence[MAX_SAPLING_CHARS:]
            if not sentence:
                continue
            if len(current) + len(sentence) + 1 > MAX_SAPLING_CHARS:
                chunks.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current)
        return chunks

    def _analyze_chunk(self, query_text: str, chunk_meta=None) -> EngineResult:
        payload = {
            "text": query_text,
            "key": self.api_key,
            "sent_scores": True
        }

        try:
            status, data, elapsed_ms = post_json_parsed(
                SAPLING_URL,
                payload,
                headers=_HEADERS,
                timeout=self.timeout_seconds,
                retries=self.retries,
            )
            if status != 200 or not isinstance(data, dict):
                hint = ""
                if status in (401, 403):
                    hint = (" (The bundled public web key may have expired. "
                            "Set the SAPLING_API_KEY environment variable with a fresh "
                            "key from https://sapling.ai)")
                return self._unavailable(f"HTTP Status {status}{hint}")

            raw_score = float(data.get("score", 0.0))
            ai_percentage = round(raw_score * 100.0, 1)
            human_percentage = round(100.0 - ai_percentage, 1)

            verdict = "HUMAN" if ai_percentage < 25.0 else ("AI" if ai_percentage > 65.0 else "MIXED")

            flagged_sentences = []
            for item in data.get("sentence_scores", []) or []:
                s_text = item.get("sentence", "").strip()
                s_score = float(item.get("score", 0.0))
                if s_score < 0.5 and s_text:  # Sapling sentence score < 0.5 indicates AI likelihood
                    flagged_sentences.append(s_text)

            details = {
                "raw_score": raw_score,
                "used_tokens": data.get("used_tokens", len(query_text.split())),
                "method": "direct_http",
                "latency_ms": round(elapsed_ms, 1),
            }
            if chunk_meta:
                details.update(chunk_meta)

            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=ai_percentage,
                human_percentage=human_percentage,
                verdict=verdict,
                weight=self.weight,
                details=details,
                flagged_sentences=flagged_sentences
            )
        except Exception as e:
            return self._unavailable(f"HTTP request error: {str(e)}")

    @staticmethod
    def _unavailable(error: str) -> EngineResult:
        return EngineResult(
            engine_name=SaplingEngine.name,
            available=False,
            ai_percentage=0.0,
            human_percentage=100.0,
            verdict="UNAVAILABLE",
            weight=0.0,
            error=error
        )
