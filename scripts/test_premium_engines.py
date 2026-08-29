#!/usr/bin/env python3
"""
Live verification for the premium key-based engines (v2.1).

Exports any of these before running:
    GPTZERO_API_KEY      (free tier: https://dashboard.gptzero.me)
    WINSTON_API_KEY      (trial:     https://gowinston.ai)
    ORIGINALITY_API_KEY  (paid:      https://app.originality.ai/api-access)
    PANGRAM_API_KEY      (free tier: https://www.pangram.com)
    DETECTING_AI_API_KEY (free tier: https://detecting-ai.com)

Usage:
    python scripts/test_premium_engines.py
Engines without keys are reported as SKIPPED. Every configured engine is hit
with a short obviously-AI sample and a human-written sample.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_detector_cli.engines.gptzero_api_engine import GPTZeroApiEngine  # noqa: E402
from ai_detector_cli.engines.winston_engine import WinstonEngine  # noqa: E402
from ai_detector_cli.engines.originality_engine import OriginalityEngine  # noqa: E402
from ai_detector_cli.engines.pangram_engine import PangramEngine  # noqa: E402
from ai_detector_cli.engines.detectingai_engine import DetectingAIEngine  # noqa: E402

AI_TEXT = (
    "In today's rapidly evolving digital landscape, it is crucial to delve into the "
    "multifaceted implications of artificial intelligence. Furthermore, organizations "
    "must navigate the delicate balance between innovation and responsibility, "
    "fostering sustainable growth while bolstering stakeholder trust."
)
HUMAN_TEXT = (
    "I burned the rice again. Third time this week. My grandmother would be horrified - "
    "she could tell when rice was done just by listening to the pot, never lifted the "
    "lid once. Mine sticks and goes crunchy at the bottom while the top stays raw."
)

ENGINES = [
    ("GPTZero Official API", "GPTZERO_API_KEY", GPTZeroApiEngine),
    ("Winston AI", "WINSTON_API_KEY", WinstonEngine),
    ("Originality.ai", "ORIGINALITY_API_KEY", OriginalityEngine),
    ("Pangram", "PANGRAM_API_KEY", PangramEngine),
    ("Detecting-AI", "DETECTING_AI_API_KEY", DetectingAIEngine),
]


def main() -> None:
    print("=" * 74)
    print(" PREMIUM ENGINE LIVE TEST")
    print("=" * 74)
    for name, env_var, cls in ENGINES:
        if not os.environ.get(env_var, "").strip():
            print(f"\n[{name:<22}] SKIPPED - {env_var} not set")
            continue
        print(f"\n[{name:<22}] testing ...")
        engine = cls()
        for label, sample in (("ai-sample", AI_TEXT), ("human-sample", HUMAN_TEXT)):
            try:
                res = engine.analyze(sample)
                if res.available:
                    print(f"  {label:<13} -> AI {res.ai_percentage:5.1f}%  "
                          f"({res.verdict})  details={res.details}")
                else:
                    print(f"  {label:<13} -> UNAVAILABLE: {res.error}")
            except Exception as exc:  # pragma: no cover - live diagnostics
                print(f"  {label:<13} -> EXCEPTION: {exc}")
    print("\nDone.")


if __name__ == "__main__":
    main()
