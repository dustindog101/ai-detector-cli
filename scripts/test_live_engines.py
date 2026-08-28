"""
Test script for live Playwright/HTTP AI detector engines:
- Sapling AI Content Detector
- ContentDetector.ai
- Writer.com AI Content Detector
"""

import sys
import os
import time

# Add root package to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_detector_cli.engines.sapling_engine import SaplingEngine
from ai_detector_cli.engines.contentdetector_engine import ContentDetectorEngine
from ai_detector_cli.engines.writer_engine import WriterEngine
from ai_detector_cli.cli import split_sentences

AI_SAMPLE_TEXT = (
    "When evaluating relational databases versus NoSQL solutions, it is crucial to delve into the "
    "multifaceted trade-offs. Furthermore, scalability plays a pivotal role in modern software architecture. "
    "For instance, developers can optimize latency, enhance reliability, and bolster data integrity. "
    "In conclusion, understanding these nuances is paramount for fostering long-term technological success."
)

HUMAN_SAMPLE_TEXT = (
    "Honestly I don't think switching to NoSQL makes sense here. When we tried using MongoDB for our "
    "web dev project last term, it seemed really convenient at first, but as soon as our data relationships "
    "got messy with user profiles and order histories we spent days fixing schema errors that PostgreSQL "
    "would have prevented automatically. And our professor mentioned in lecture that ACID compliance is pretty "
    "much mandatory for any transaction data anyway. So I'd stick with a standard relational database for this system."
)

def run_test():
    print("=" * 70)
    print("LIVE AI DETECTOR ENGINE TEST BENCH")
    print("=" * 70)

    engines = [
        ("Sapling AI Content Detector", SaplingEngine(headless=True)),
        ("ContentDetector.ai", ContentDetectorEngine(headless=True)),
        ("Writer.com AI Detector", WriterEngine(headless=True)),
    ]

    for label, sample in [("🤖 AI-Generated Sample", AI_SAMPLE_TEXT), ("👤 Human-Written Sample", HUMAN_SAMPLE_TEXT)]:
        print(f"\n--- Testing on: {label} ---")
        print(f"Text ({len(sample.split())} words):\n\"{sample}\"\n")
        sentences = split_sentences(sample)
        words = sample.lower().split()

        for name, engine in engines:
            print(f"▶ Testing [{name}]...")
            start_t = time.time()
            try:
                res = engine.analyze(sample, sentences, words)
                elapsed = time.time() - start_t
                status_icon = "✅" if res.available else "⚠️"
                print(f"  {status_icon} Available: {res.available} ({elapsed:.2f}s)")
                print(f"     AI Score:    {res.ai_percentage}%")
                print(f"     Human Score: {res.human_percentage}%")
                print(f"     Verdict:     {res.verdict}")
                if res.flagged_sentences:
                    print(f"     Flagged Sentences ({len(res.flagged_sentences)}):")
                    for s in res.flagged_sentences[:3]:
                        print(f"       - \"{s[:80]}...\"" if len(s) > 80 else f"       - \"{s}\"")
                if res.error:
                    print(f"     Error / Notes: {res.error}")
            except Exception as ex:
                print(f"  ❌ Exception during analysis: {ex}")
            print()

if __name__ == "__main__":
    run_test()
