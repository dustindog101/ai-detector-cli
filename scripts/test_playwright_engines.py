#!/usr/bin/env python3
"""
Test runner script for QuillBot and Scribbr Playwright engines.
Runs both engines with sample AI and Human text.
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
pkg_dir = os.path.abspath(os.path.join(current_dir, ".."))
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

from ai_detector_cli.engines.quillbot_engine import QuillBotEngine
from ai_detector_cli.engines.scribbr_engine import ScribbrEngine

def main():
    sample_ai_text = (
        "When evaluating relational databases versus NoSQL solutions, it is crucial to delve into the multifaceted trade-offs. "
        "Furthermore, scalability plays a pivotal role in modern software architecture. For instance, developers can optimize latency, "
        "enhance reliability, and bolster data integrity. In conclusion, understanding these nuances is paramount for fostering "
        "long-term technological success and seamless operational efficiency."
    )

    sample_human_text = (
        "I looked into PostgreSQL vs MongoDB for our project yesterday. Postgres has worked fine for most of our standard table structures, "
        "and setting up foreign keys saved us a ton of debugging time on the backend. Mongo could be helpful down the line if we get into "
        "unstructured JSON payloads, but right now sticking with Postgres avoids unnecessary overhead."
    )

    print("=" * 70)
    print("Testing QuillBot Playwright Engine...")
    print("=" * 70)
    qb = QuillBotEngine()
    qb_res_ai = qb.analyze(sample_ai_text)
    print(f"QuillBot AI Text Result: Available={qb_res_ai.available}, AI%={qb_res_ai.ai_percentage}%, Verdict={qb_res_ai.verdict}")
    print(f"Details: {qb_res_ai.details}")
    if qb_res_ai.error:
        print(f"Error: {qb_res_ai.error}")

    qb_res_human = qb.analyze(sample_human_text)
    print(f"QuillBot Human Text Result: Available={qb_res_human.available}, AI%={qb_res_human.ai_percentage}%, Verdict={qb_res_human.verdict}")
    if qb_res_human.error:
        print(f"Error: {qb_res_human.error}")

    print("\n" + "=" * 70)
    print("Testing Scribbr Playwright Engine...")
    print("=" * 70)
    sc = ScribbrEngine()
    sc_res_ai = sc.analyze(sample_ai_text)
    print(f"Scribbr AI Text Result: Available={sc_res_ai.available}, AI%={sc_res_ai.ai_percentage}%, Verdict={sc_res_ai.verdict}")
    print(f"Details: {sc_res_ai.details}")
    if sc_res_ai.error:
        print(f"Error: {sc_res_ai.error}")

    sc_res_human = sc.analyze(sample_human_text)
    print(f"Scribbr Human Text Result: Available={sc_res_human.available}, AI%={sc_res_human.ai_percentage}%, Verdict={sc_res_human.verdict}")
    if sc_res_human.error:
        print(f"Error: {sc_res_human.error}")

if __name__ == "__main__":
    main()
