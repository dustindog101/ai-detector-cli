"""
Main CLI entry point for AI Detector.
Supports concurrent multi-engine analysis across live public detectors and local models.
"""

import sys
import os
import re
import math
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from .models import DetectionReport, SentenceAnalysis, EngineResult
from .engines import ALL_ENGINES, LIVE_WEB_ENGINES, LOCAL_ENGINES
from .reporter import (
    format_terminal_report,
    format_comparative_report,
    export_json,
    export_markdown
)

def split_sentences(text: str) -> List[str]:
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in raw_sentences if s.strip()]

def analyze_text(
    text: str,
    live_only: bool = False,
    local_only: bool = False,
    max_workers: int = 5
) -> DetectionReport:
    sentences = split_sentences(text)
    words = re.findall(r'\b[A-Za-z0-9\'-]+\b', text.lower())

    if not sentences or not words:
        empty_res = EngineResult(
            engine_name="Error",
            available=False,
            ai_percentage=0.0,
            human_percentage=0.0,
            verdict="EMPTY",
            weight=1.0,
            error="Input text is empty"
        )
        return DetectionReport(
            text=text,
            word_count=0,
            sentence_count=0,
            consensus_ai_probability=0.0,
            consensus_human_probability=100.0,
            consensus_verdict="EMPTY",
            risk_level="NONE",
            engines={"error": empty_res}
        )

    # Select engines to run
    if live_only:
        selected_engines = LIVE_WEB_ENGINES
    elif local_only:
        selected_engines = LOCAL_ENGINES
    else:
        selected_engines = ALL_ENGINES

    # 1. Run selected engines concurrently using ThreadPoolExecutor
    engine_results: Dict[str, EngineResult] = {}
    weights = []
    probs = []

    def run_engine(engine):
        res = engine.analyze(text, sentences, words)
        key = engine.__class__.__name__.lower().replace("engine", "")
        return key, res

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_engine = {executor.submit(run_engine, eng): eng for eng in selected_engines}
        for future in as_completed(future_to_engine):
            try:
                key, res = future.result()
                engine_results[key] = res
                if res.available:
                    probs.append(res.ai_percentage)
                    weights.append(res.weight)
            except Exception as e:
                eng = future_to_engine[future]
                key = eng.__class__.__name__.lower().replace("engine", "")
                engine_results[key] = EngineResult(
                    engine_name=eng.name,
                    available=False,
                    ai_percentage=0.0,
                    human_percentage=100.0,
                    verdict="UNAVAILABLE",
                    weight=0.0,
                    error=str(e)
                )

    total_weight = sum(weights) if weights else 1.0
    consensus_ai_prob = sum(p * w for p, w in zip(probs, weights)) / total_weight if probs else 0.0

    if consensus_ai_prob < 20.0:
        consensus_verdict = "🟢 100% HUMAN (Zero Detection Risk)"
        risk_level = "VERY LOW (Safe for Submission)"
    elif consensus_ai_prob < 45.0:
        consensus_verdict = "🟡 LOW AI RISK (Minor Heuristic Signals)"
        risk_level = "LOW TO MODERATE"
    elif consensus_ai_prob < 70.0:
        consensus_verdict = "🟠 MODERATE TO HIGH AI SIGNALS"
        risk_level = "ELEVATED RISK"
    else:
        consensus_verdict = "🔴 HIGH AI DETECTION RISK (Will Trip Turnitin/GPTZero)"
        risk_level = "CRITICAL (De-linearization Required)"

    # 2. Extract Sentence-by-Sentence Analysis
    sentence_analyses: List[SentenceAnalysis] = []
    zerogpt_res = engine_results.get("zerogpt")
    zerogpt_flagged_texts = set(zerogpt_res.flagged_sentences if zerogpt_res else [])

    quillbot_res = engine_results.get("quillbot")
    quillbot_flagged = set(quillbot_res.flagged_sentences if quillbot_res else [])

    sapling_res = engine_results.get("sapling")
    sapling_flagged = set(sapling_res.flagged_sentences if sapling_res else [])

    lengths = [len(re.findall(r'\b[A-Za-z0-9\'-]+\b', s)) for s in sentences]
    mean_len = sum(lengths) / len(lengths) if lengths else 0
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths) if lengths else 0
    std_dev = math.sqrt(variance)
    burstiness = (std_dev / mean_len) if mean_len > 0 else 0

    from .engines.lexicon_engine import BANNED_WORDS, BANNED_PHRASES

    for idx, s in enumerate(sentences):
        s_words = re.findall(r'\b[A-Za-z0-9\'-]+\b', s.lower())
        s_len = len(s_words)
        reasons = []
        s_ai_prob = 5.0

        # Check ZeroGPT match
        if s in zerogpt_flagged_texts or any(s in f or f in s for f in zerogpt_flagged_texts):
            reasons.append("ZeroGPT Cloud Flag")
            s_ai_prob += 40.0

        # Check QuillBot match
        if s in quillbot_flagged or any(s in f or f in s for f in quillbot_flagged):
            reasons.append("QuillBot Highlight")
            s_ai_prob += 30.0

        # Check Sapling match
        if s in sapling_flagged or any(s in f or f in s for f in sapling_flagged):
            reasons.append("Sapling Highlight")
            s_ai_prob += 30.0

        # Check banned words in this sentence
        s_banned = [w for w in s_words if w in BANNED_WORDS]
        if s_banned:
            reasons.append(f"AI buzzwords: {', '.join(set(s_banned))}")
            s_ai_prob += len(s_banned) * 20.0

        # Check formulaic transitions
        for p in BANNED_PHRASES:
            if re.search(p, s, re.IGNORECASE):
                reasons.append("Formulaic AI phrase/transition")
                s_ai_prob += 25.0

        # Check em dash
        if re.search(r'[—–]|--', s):
            reasons.append("Em dash clause connection")
            s_ai_prob += 15.0

        # Check tripartite list
        if re.search(r'(\b\w+\b,\s+\b\w+\b,?\s+and\s+\b\w+\b)', s, re.IGNORECASE):
            reasons.append("Rule-of-Three tripartite list")
            s_ai_prob += 20.0

        s_ai_prob = min(99.0, max(0.0, s_ai_prob))
        is_flagged = s_ai_prob >= 40.0

        sentence_analyses.append(SentenceAnalysis(
            index=idx,
            text=s,
            word_count=s_len,
            ai_probability=round(s_ai_prob, 1),
            flagged=is_flagged,
            reasons=reasons
        ))

    # Overall lexical metrics
    all_banned_found = list(set([w for w in words if w in BANNED_WORDS]))
    em_dash_count = len(re.findall(r'[—–]|--', text))
    semicolon_count = text.count(';')
    tripartite_count = len(re.findall(r'(\b\w+\b,\s+\b\w+\b,?\s+and\s+\b\w+\b)', text, re.IGNORECASE))

    return DetectionReport(
        text=text,
        word_count=len(words),
        sentence_count=len(sentences),
        consensus_ai_probability=round(consensus_ai_prob, 1),
        consensus_human_probability=round(100.0 - consensus_ai_prob, 1),
        consensus_verdict=consensus_verdict,
        risk_level=risk_level,
        engines=engine_results,
        sentences=sentence_analyses,
        burstiness_ratio=round(burstiness, 2),
        mean_sentence_length=round(mean_len, 1),
        sentence_length_std_dev=round(std_dev, 1),
        banned_words_found=all_banned_found,
        em_dash_count=em_dash_count,
        semicolon_count=semicolon_count,
        tripartite_list_count=tripartite_count
    )

def main():
    parser = argparse.ArgumentParser(
        prog="ai-detect",
        description="Multi-Engine AI Text Detector CLI (Queries Live Public Detectors + Statistical Models in Parallel)"
    )
    parser.add_argument("file", nargs="?", help="Path to text or markdown file to audit")
    parser.add_argument("--compare", "-c", nargs=2, metavar=("ORIGINAL", "MODIFIED"), help="Compare original vs modified text files across all engines")
    parser.add_argument("--live-only", action="store_true", help="Run only the 5 public online GPT detectors (ZeroGPT, QuillBot, Sapling, Scribbr, Writer)")
    parser.add_argument("--local-only", action="store_true", help="Run only local statistical engines (GLTR, Burstiness, Perplexity, Lexicon) without network requests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full verbose diagnostic output and engine details")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--export", "-e", metavar="OUTPUT_PATH", help="Export full report to a Markdown (.md) or JSON (.json) file")
    parser.add_argument("--no-sentences", action="store_true", help="Hide detailed sentence-level extraction breakdown")
    parser.add_argument("--threshold", "-t", type=int, default=30, help="Maximum AI percentage allowed to exit with code 0 (default: 30)")
    parser.add_argument("--stdin", action="store_true", help="Read text directly from standard input")

    args = parser.parse_args()

    # Mode 1: Comparative Audit
    if args.compare:
        with open(args.compare[0], "r", encoding="utf-8") as f1, open(args.compare[1], "r", encoding="utf-8") as f2:
            text1 = f1.read()
            text2 = f2.read()
        rep1 = analyze_text(text1, live_only=args.live_only, local_only=args.local_only)
        rep2 = analyze_text(text2, live_only=args.live_only, local_only=args.local_only)
        print(format_comparative_report(rep1, rep2))
        if rep2.consensus_ai_probability > args.threshold:
            sys.exit(1)
        sys.exit(0)

    # Mode 2: Single Text Audit
    if args.stdin or (not sys.stdin.isatty() and not args.file):
        text = sys.stdin.read()
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        print("Usage: ai-detect <file.txt> or pipe input. Run 'ai-detect --help' for options.\n")
        text = "When evaluating relational databases versus NoSQL solutions, it is crucial to delve into the multifaceted trade-offs. Furthermore, scalability plays a pivotal role in modern software architecture. For instance, developers can optimize latency, enhance reliability, and bolster data integrity. In conclusion, understanding these nuances is paramount for fostering long-term technological success."
        print("Running benchmark on standard AI sample text:\n")

    report = analyze_text(text, live_only=args.live_only, local_only=args.local_only)

    # Handle Exports
    if args.export:
        if args.export.endswith(".json"):
            content = export_json(report)
        else:
            content = export_markdown(report)
        with open(args.export, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Report successfully exported to: {args.export}\n")

    # Output formatting
    if args.json:
        print(export_json(report))
    else:
        print(format_terminal_report(report, show_sentences=not args.no_sentences, verbose=args.verbose))

    if report.consensus_ai_probability > args.threshold:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
