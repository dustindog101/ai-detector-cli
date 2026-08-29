"""
Main CLI entry point for AI Detector.
Supports multi-format document loading (.txt, .md, .docx, .pdf, .html, .rtf, .json),
intelligent character limit handling, and blazing-fast multi-engine analysis.
"""

import sys
import os
import re
import math
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from .models import DetectionReport, SentenceAnalysis, EngineResult
from .engines import (
    DEFAULT_ENGINES,
    LIVE_HTTP_ENGINES,
    LOCAL_ENGINES,
    BROWSER_ENGINES,
    ALL_ENGINES,
    LIVE_WEB_ENGINES
)
from .reporter import (
    format_terminal_report,
    format_comparative_report,
    export_json,
    export_markdown
)

def load_document(file_path: str) -> str:
    """
    Loads text from a wide range of document formats (.txt, .md, .docx, .pdf, .html, .rtf, .json, .csv).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    # 1. Word Documents (.docx)
    if ext == ".docx":
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(file_path) as z:
                xml_content = z.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                texts = [node.text for node in tree.iter() if node.text]
                return "\n".join(texts)
        except Exception as e:
            raise ValueError(f"Failed to read .docx file: {e}")

    # 2. PDF Documents (.pdf)
    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            extracted = [p.extract_text() for p in reader.pages if p.extract_text()]
            if extracted:
                return "\n".join(extracted)
        except ImportError:
            pass
        # Fallback raw extraction for simple text PDFs
        with open(file_path, "rb") as f:
            content = f.read().decode("latin-1", errors="ignore")
            matches = re.findall(r'\(([A-Za-z0-9 ,.!?\'-]+)\)Tj', content)
            if matches:
                return " ".join(matches)
        raise ValueError("Could not extract text from PDF. Install pypdf ('pip install pypdf') for full PDF support.")

    # 3. HTML / Web pages (.html, .htm)
    elif ext in [".html", ".htm"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            html_raw = f.read()
        # Strip scripts and tags
        clean_text = re.sub(r'<script.*?</script>', '', html_raw, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<style.*?</style>', '', clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        return re.sub(r'\s+', ' ', clean_text).strip()

    # 4. Standard Text / Markdown / Code / JSON / RTF (.txt, .md, .markdown, .rtf, .json, .csv)
    else:
        for enc in ["utf-8", "latin-1", "utf-16", "cp1252"]:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

def split_sentences(text: str) -> List[str]:
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in raw_sentences if s.strip()]

def analyze_text(
    text: str,
    live_only: bool = False,
    local_only: bool = False,
    browser: bool = False,
    all_engines: bool = False,
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
    if all_engines:
        selected_engines = ALL_ENGINES
    elif browser:
        selected_engines = LIVE_WEB_ENGINES
    elif live_only:
        selected_engines = LIVE_HTTP_ENGINES
    elif local_only:
        selected_engines = LOCAL_ENGINES
    else:
        # Default: Blazing-Fast Suite (ZeroGPT HTTP + Sapling HTTP + 4 Statistical Engines) -> < 0.5s!
        selected_engines = DEFAULT_ENGINES

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

    sapling_res = engine_results.get("sapling")
    sapling_flagged = set(sapling_res.flagged_sentences if sapling_res else [])

    quillbot_res = engine_results.get("quillbot")
    quillbot_flagged = set(quillbot_res.flagged_sentences if quillbot_res else [])

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

        # Check Sapling match
        if s in sapling_flagged or any(s in f or f in s for f in sapling_flagged):
            reasons.append("Sapling Cloud Flag")
            s_ai_prob += 35.0

        # Check QuillBot match
        if s in quillbot_flagged or any(s in f or f in s for f in quillbot_flagged):
            reasons.append("QuillBot Highlight")
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
        description="Multi-Format AI Text Detector CLI (Supports .docx, .pdf, .md, .txt, .html with Fast HTTP Detection)"
    )
    parser.add_argument("file", nargs="?", help="Path to text, markdown, docx, or pdf document to audit")
    parser.add_argument("--compare", "-c", nargs=2, metavar=("ORIGINAL", "MODIFIED"), help="Compare original vs modified documents across all engines")
    parser.add_argument("--live-only", action="store_true", help="Run only the live direct HTTP cloud detectors (ZeroGPT, Sapling)")
    parser.add_argument("--local-only", action="store_true", help="Run only local statistical engines (GLTR, Burstiness, Perplexity, Lexicon) without network requests")
    parser.add_argument("--browser", action="store_true", help="Include Playwright browser automation engines (QuillBot, Scribbr, Writer)")
    parser.add_argument("--all", action="store_true", help="Run every single engine (HTTP + Browser + Local)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full verbose diagnostic output and engine details")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--export", "-e", metavar="OUTPUT_PATH", help="Export full report to a Markdown (.md) or JSON (.json) file")
    parser.add_argument("--no-sentences", action="store_true", help="Hide detailed sentence-level extraction breakdown")
    parser.add_argument("--threshold", "-t", type=int, default=30, help="Maximum AI percentage allowed to exit with code 0 (default: 30)")
    parser.add_argument("--stdin", action="store_true", help="Read text directly from standard input")

    args = parser.parse_args()

    # Mode 1: Comparative Audit
    if args.compare:
        text1 = load_document(args.compare[0])
        text2 = load_document(args.compare[1])
        rep1 = analyze_text(text1, live_only=args.live_only, local_only=args.local_only, browser=args.browser, all_engines=args.all)
        rep2 = analyze_text(text2, live_only=args.live_only, local_only=args.local_only, browser=args.browser, all_engines=args.all)
        print(format_comparative_report(rep1, rep2))
        if rep2.consensus_ai_probability > args.threshold:
            sys.exit(1)
        sys.exit(0)

    # Mode 2: Single Text / Document Audit
    if args.stdin or (not sys.stdin.isatty() and not args.file):
        text = sys.stdin.read()
    elif args.file:
        try:
            text = load_document(args.file)
        except Exception as e:
            print(f"❌ Error loading document: {e}")
            sys.exit(1)
    else:
        print("Usage: ai-detect <file.docx | file.pdf | file.md | file.txt> or pipe input. Run 'ai-detect --help' for options.\n")
        text = "When evaluating relational databases versus NoSQL solutions, it is crucial to delve into the multifaceted trade-offs. Furthermore, scalability plays a pivotal role in modern software architecture. For instance, developers can optimize latency, enhance reliability, and bolster data integrity. In conclusion, understanding these nuances is paramount for fostering long-term technological success."
        print("Running benchmark on standard AI sample text:\n")

    report = analyze_text(text, live_only=args.live_only, local_only=args.local_only, browser=args.browser, all_engines=args.all)

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
