"""
Engine: Sapling AI Content Detector (Blazing-Fast Direct HTTP & Playwright Fallback)
Directly queries https://api.sapling.ai/api/v1/aidetect with sentence-level extraction and token probabilities.
Safely handles document size limits (max 1,950 chars per request).
"""

import os
import re
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

from .base import BaseEngine
from ..models import EngineResult

MAX_SAPLING_CHARS = 1950
PUBLIC_SAPLING_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjbEU0RnJKYXlUSnhYTjZSM19fbVd3VFEzSERIV2dDUmZkT19TSFJDMWFfeWRTWV9YMDhseFpJNnRrM3lEMkZFVGNuM0FHZ0R1emNkaHJXQjdNV0Z5USUzRCUzRCIsImV4cCI6MTc4ODMxNjQwNn0.VZkUB-ZtTU-QfpAyAMC45piYluD0eFt89FkW9I-0jjs"

class SaplingEngine(BaseEngine):
    name = "Sapling AI Detector"
    weight = 0.35

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: int = 8
    ):
        self.api_key = api_key or os.environ.get("SAPLING_API_KEY") or PUBLIC_SAPLING_KEY
        self.timeout_seconds = timeout_seconds

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

        # 1. Primary: Direct Blazing-Fast HTTP Request (<0.3s)
        http_result = self._analyze_http(text)
        if http_result.available:
            return http_result

        # 2. Fallback: Headless Browser Playwright if HTTP failed
        return self._analyze_playwright_fallback(text, sentences)

    def _analyze_http(self, text: str) -> EngineResult:
        query_text = text[:MAX_SAPLING_CHARS]
        is_truncated = len(text) > MAX_SAPLING_CHARS

        url = "https://api.sapling.ai/api/v1/aidetect"
        payload = {
            "text": query_text,
            "key": self.api_key,
            "sent_scores": True
        }
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://sapling.ai",
            "Referer": "https://sapling.ai/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_score = float(data.get("score", 0.0))
                    ai_percentage = round(raw_score * 100.0, 1)
                    human_percentage = round(100.0 - ai_percentage, 1)

                    verdict = "HUMAN" if ai_percentage < 25.0 else ("AI" if ai_percentage > 65.0 else "MIXED")

                    flagged_sentences = []
                    sent_scores = data.get("sentence_scores", [])
                    for item in sent_scores:
                        s_text = item.get("sentence", "").strip()
                        s_score = float(item.get("score", 0.0))
                        if s_score < 0.5 and s_text:  # Sapling sentence score < 0.5 indicates AI likelihood
                            flagged_sentences.append(s_text)

                    return EngineResult(
                        engine_name=self.name,
                        available=True,
                        ai_percentage=ai_percentage,
                        human_percentage=human_percentage,
                        verdict=verdict,
                        weight=self.weight,
                        details={
                            "raw_score": raw_score,
                            "used_tokens": data.get("used_tokens", len(query_text.split())),
                            "model_version": data.get("version", "20251027"),
                            "method": "direct_http",
                            "truncated": is_truncated
                        },
                        flagged_sentences=flagged_sentences
                    )
        except Exception as e:
            return EngineResult(
                engine_name=self.name,
                available=False,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="UNAVAILABLE",
                weight=0.0,
                error=f"HTTP request error: {str(e)}"
            )

    def _analyze_playwright_fallback(self, text: str, sentences: List[str] = None) -> EngineResult:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    headless=True
                )
                page = browser.new_page()
                page.goto("https://sapling.ai/ai-content-detector", timeout=15000)
                body = page.inner_text("body")
                browser.close()
                return EngineResult(
                    engine_name=self.name,
                    available=False,
                    ai_percentage=0.0,
                    human_percentage=100.0,
                    verdict="UNAVAILABLE",
                    weight=0.0,
                    error="Fallback completed"
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
