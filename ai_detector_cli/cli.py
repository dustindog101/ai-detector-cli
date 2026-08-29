"""
Main CLI entry point for AI Detector.
Supports multi-format document loading (.txt, .md, .docx, .pdf, .html, .rtf, .json),
intelligent character limit handling, and blazing-fast multi-engine analysis.

v2 highlights:
- Auto-adaptive engine orchestration: live HTTP + local statistical engines run
  concurrently; when the network is unreachable the tool degrades gracefully
  to local-only mode with a warning instead of failing.
- Batch mode (--batch) with per-file scores and a ranked summary table.
- Self-contained HTML report export (--export report.html).
- Tunable concurrency (--workers), global HTTP timeout (--timeout), and
  per-engine selection (--engines).
"""

import sys
import os
import re
import json
import math
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple

from .models import DetectionReport, SentenceAnalysis, EngineResult, BatchEntry, BatchReport
from .engines import (
    DEFAULT_ENGINES,
    LIVE_HTTP_ENGINES,
    LOCAL_ENGINES,
    BROWSER_ENGINES,
    ALL_ENGINES,
    LIVE_WEB_ENGINES,
    PREMIUM_KEY_ENGINES,
    BINOCULARS_ACTIVE,
)
from .reporter import (
    format_terminal_report,
    format_comparative_report,
    export_json,
    export_markdown,
    format_batch_report,
    export_batch_json,
)
from .html_report import export_html, export_batch_html

# Windows terminals default to cp1252 and choke on emoji - force UTF-8 when possible.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Precompiled patterns (module level => compiled once, reused everywhere)
# ---------------------------------------------------------------------------
WORD_RE = re.compile(r"\b[A-Za-z0-9'-]+\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
EM_DASH_RE = re.compile(r"[—–]|--")
TRIPARTITE_RE = re.compile(r"(\b\w+\b,\s+\b\w+\b,?\s+and\s+\b\w+\b)", re.IGNORECASE)
FORMAL_TRANSITIONS = ("Furthermore", "Moreover", "Additionally", "In conclusion")

from .engines.lexicon_engine import BANNED_WORDS, BANNED_PHRASES  # noqa: E402

# Supported document extensions for batch discovery
BATCH_EXTENSIONS = {".txt", ".md", ".markdown", ".rtf", ".json", ".csv",
                    ".html", ".htm", ".docx", ".pdf"}


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
            matches = re.findall(r"\(([A-Za-z0-9 ,.!?\'-]+)\)Tj", content)
            if matches:
                return " ".join(matches)
        raise ValueError("Could not extract text from PDF. Install pypdf ('pip install pypdf') for full PDF support.")

    # 3. HTML / Web pages (.html, .htm)
    elif ext in [".html", ".htm"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            html_raw = f.read()
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
    raw_sentences = SENTENCE_SPLIT_RE.split(text.strip())
    return [s.strip() for s in raw_sentences if s.strip()]


def engine_key(engine) -> str:
    override = getattr(engine, "key", None)
    if override:
        return override
    return engine.__class__.__name__.lower().replace("engine", "")


def _empty_report(text: str, source: str) -> DetectionReport:
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
        engines={"error": empty_res},
        source=source,
    )


def select_engines(
    live_only: bool = False,
    local_only: bool = False,
    browser: bool = False,
    all_engines: bool = False,
    only: Optional[List[str]] = None,
) -> List:
    """Resolve which engine instances to run based on CLI flags."""
    if all_engines:
        selected = list(ALL_ENGINES)
    elif browser:
        selected = list(LIVE_WEB_ENGINES)
    elif live_only and local_only:
        selected = list(DEFAULT_ENGINES)  # contradictory flags -> sensible default
    elif live_only:
        selected = list(LIVE_HTTP_ENGINES)
    elif local_only:
        selected = list(LOCAL_ENGINES)
    else:
        selected = list(DEFAULT_ENGINES)

    if only:
        wanted = {name.strip().lower() for name in only if name.strip()}
        # Explicitly requested engines are honored even when they are outside
        # the current mode's pool (e.g. --engines pangram in default mode, or
        # --engines binoculars without the auto-enable env flag).
        selected = [e for e in selected if engine_key(e) in wanted]
        selected_keys = {engine_key(e) for e in selected}
        for e in ALL_ENGINES:
            if engine_key(e) in wanted and engine_key(e) not in selected_keys:
                selected.append(e)
                selected_keys.add(engine_key(e))
    return selected


def analyze_text(
    text: str,
    live_only: bool = False,
    local_only: bool = False,
    browser: bool = False,
    all_engines: bool = False,
    max_workers: int = 6,
    source: str = "<stdin>",
    only: Optional[List[str]] = None,
    strict_offline: bool = False,
) -> DetectionReport:
    """
    Run the selected engine suite concurrently over ``text`` and build a
    DetectionReport. Live HTTP engines run in parallel with local statistical
    engines; if every live engine fails while local ones succeeded, the report
    is marked ``degraded`` (auto-adaptive offline fallback).
    """
    started = time.perf_counter()
    sentences = split_sentences(text)
    words = WORD_RE.findall(text.lower())

    if not sentences or not words:
        return _empty_report(text, source)

    if local_only or strict_offline:
        engine_mode = "local-only" if local_only else ("local-only" if strict_offline else "default")
        selected_engines = select_engines(False, True, False, False, only)
    elif all_engines:
        engine_mode = "all"
        selected_engines = select_engines(False, False, False, True, only)
    elif browser:
        engine_mode = "browser"
        selected_engines = select_engines(False, False, True, False, only)
    elif live_only:
        engine_mode = "live-only"
        selected_engines = select_engines(True, False, False, False, only)
    else:
        engine_mode = "default"
        selected_engines = select_engines(False, False, False, False, only)

    if not selected_engines:
        return _empty_report(text, source)

    live_keys = {engine_key(e) for e in LIVE_HTTP_ENGINES}
    selected_keys = {engine_key(e) for e in selected_engines}

    # 1. Run selected engines concurrently
    engine_results: Dict[str, EngineResult] = {}
    weights: List[float] = []
    probs: List[float] = []
    live_errors: List[str] = []
    live_ran = bool(selected_keys & live_keys)

    def run_engine(engine):
        res = engine.analyze(text, sentences, words)
        return engine_key(engine), res

    workers = max(1, min(max_workers, len(selected_engines)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_engine = {executor.submit(run_engine, eng): eng for eng in selected_engines}
        for future in as_completed(future_to_engine):
            eng = future_to_engine[future]
            key = engine_key(eng)
            try:
                _, res = future.result()
                engine_results[key] = res
                if res.available:
                    probs.append(res.ai_percentage)
                    weights.append(res.weight)
                elif key in live_keys:
                    live_errors.append(f"{eng.name}: {res.error or 'unavailable'}")
            except Exception as e:
                engine_results[key] = EngineResult(
                    engine_name=eng.name,
                    available=False,
                    ai_percentage=0.0,
                    human_percentage=100.0,
                    verdict="UNAVAILABLE",
                    weight=0.0,
                    error=str(e)
                )
                if key in live_keys:
                    live_errors.append(f"{eng.name}: {e}")

    # 2. Auto-adaptive degradation: every live engine failed but local results exist.
    degraded = False
    degradation_note: Optional[str] = None
    live_succeeded = any(res.available for k, res in engine_results.items() if k in live_keys)
    if live_ran and live_errors and not live_succeeded and len(engine_results) > len(live_errors):
        local_ok = any(res.available for k, res in engine_results.items() if k not in live_keys)
        if local_ok:
            degraded = True
            degradation_note = "Live cloud engines unreachable - using local statistical engines only. " + "; ".join(live_errors[:2])
            print(f"⚠️  {degradation_note}", file=sys.stderr)

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

    # 3. Sentence-by-sentence analysis
    sentence_analyses = _analyze_sentences(sentences, engine_results)

    # 4. Overall lexical metrics
    all_banned_found = sorted({w for w in words if w in BANNED_WORDS})
    em_dash_count = len(EM_DASH_RE.findall(text))
    semicolon_count = text.count(';')
    tripartite_count = len(TRIPARTITE_RE.findall(text))

    lengths = [len(WORD_RE.findall(s)) for s in sentences]
    mean_len = sum(lengths) / len(lengths) if lengths else 0
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths) if lengths else 0
    std_dev = math.sqrt(variance)
    burstiness = (std_dev / mean_len) if mean_len > 0 else 0

    elapsed_ms = (time.perf_counter() - started) * 1000.0

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
        tripartite_list_count=tripartite_count,
        source=source,
        degraded=degraded,
        degradation_note=degradation_note,
        analysis_ms=round(elapsed_ms, 1),
        engine_mode=engine_mode,
    )


def _analyze_sentences(sentences: List[str], engine_results: Dict[str, EngineResult]) -> List[SentenceAnalysis]:
    """Sentence-level risk classification using cloud flags + lexical tells."""
    cloud_flag_sources = [
        ("zerogpt", "ZeroGPT Cloud Flag", 40.0),
        ("sapling", "Sapling Cloud Flag", 35.0),
        ("quillbot", "QuillBot Highlight", 30.0),
        ("gptzero-api", "GPTZero Cloud Flag", 40.0),
        ("winston", "Winston AI Cloud Flag", 35.0),
        ("pangram", "Pangram Cloud Flag", 40.0),
    ]
    flagged_sets = []
    for src_key, src_reason, src_bonus in cloud_flag_sources:
        result = engine_results.get(src_key)
        if result is not None and result.flagged_sentences:
            flagged_sets.append((set(result.flagged_sentences), src_reason, src_bonus))

    def _match(flagged_texts, sentence):
        if sentence in flagged_texts:
            return True
        return any(sentence in f or f in sentence for f in flagged_texts)

    phrase_res = [(p, re.compile(p, re.IGNORECASE)) for p in BANNED_PHRASES]

    sentence_analyses: List[SentenceAnalysis] = []
    for idx, s in enumerate(sentences):
        s_words = WORD_RE.findall(s.lower())
        s_len = len(s_words)
        reasons: List[str] = []
        s_ai_prob = 5.0

        for flagged_texts, reason, bonus in flagged_sets:
            if _match(flagged_texts, s):
                reasons.append(reason)
                s_ai_prob += bonus

        s_banned = [w for w in s_words if w in BANNED_WORDS]
        if s_banned:
            reasons.append(f"AI buzzwords: {', '.join(sorted(set(s_banned)))}")
            s_ai_prob += len(s_banned) * 20.0

        for _pat, compiled in phrase_res:
            if compiled.search(s):
                reasons.append("Formulaic AI phrase/transition")
                s_ai_prob += 25.0

        if EM_DASH_RE.search(s):
            reasons.append("Em dash clause connection")
            s_ai_prob += 15.0
        if TRIPARTITE_RE.search(s):
            reasons.append("Rule-of-Three tripartite list")
            s_ai_prob += 20.0

        s_ai_prob = min(99.0, max(0.0, s_ai_prob))
        # Dedupe reasons while preserving order (multiple patterns can match one sentence).
        seen = set()
        unique_reasons = [r for r in reasons if not (r in seen or seen.add(r))]
        sentence_analyses.append(SentenceAnalysis(
            index=idx,
            text=s,
            word_count=s_len,
            ai_probability=round(s_ai_prob, 1),
            flagged=s_ai_prob >= 40.0,
            reasons=unique_reasons
        ))
    return sentence_analyses


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------

def discover_batch_files(directory: str, recursive: bool, pattern: Optional[str]) -> List[str]:
    """Collect analyzable files from a directory."""
    collected: List[str] = []
    if recursive:
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                if _batch_match(fname, pattern):
                    collected.append(os.path.join(root, fname))
    else:
        for fname in sorted(os.listdir(directory)):
            full = os.path.join(directory, fname)
            if os.path.isfile(full) and _batch_match(fname, pattern):
                collected.append(full)
    return sorted(collected)


def _batch_match(fname: str, pattern: Optional[str]) -> bool:
    if pattern:
        import fnmatch
        return fnmatch.fnmatch(fname, pattern)
    return os.path.splitext(fname)[1].lower() in BATCH_EXTENSIONS


def run_batch(
    directory: str,
    threshold: float,
    live_only: bool = False,
    local_only: bool = False,
    browser: bool = False,
    all_engines: bool = False,
    recursive: bool = False,
    pattern: Optional[str] = None,
    max_workers: int = 4,
    only: Optional[List[str]] = None,
) -> BatchReport:
    """Analyze every supported document in ``directory``; returns a BatchReport."""
    started = time.perf_counter()
    files = discover_batch_files(directory, recursive, pattern)
    if not files:
        print(f"❌ No analyzable documents found in: {directory}", file=sys.stderr)
        return BatchReport(threshold=threshold, engines_mode="n/a")

    # Batch defaults to local-only (fast, no rate limits) unless live engines requested.
    use_live = live_only or browser or all_engines
    entries: List[BatchEntry] = []

    def analyze_file(path: str) -> BatchEntry:
        try:
            text = load_document(path)
            if not text.strip():
                return BatchEntry(path=path, report=None, error="Empty document")  # type: ignore[arg-type]
            rep = analyze_text(
                text,
                live_only=live_only,
                local_only=local_only or not use_live,
                browser=browser,
                all_engines=all_engines,
                max_workers=max_workers,
                source=path,
                only=only,
            )
            rep.degraded = False  # suppress per-file stderr warnings in batch mode
            return BatchEntry(path=path, report=rep)
        except Exception as e:
            return BatchEntry(path=path, report=None, error=str(e))  # type: ignore[arg-type]

    if use_live:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(analyze_file, f) for f in files]
            for fut in as_completed(futures):
                entries.append(fut.result())
    else:
        for f in files:
            entries.append(analyze_file(f))

    entries.sort(key=lambda e: e.report.consensus_ai_probability if e.report else -1.0, reverse=True)
    elapsed = (time.perf_counter() - started) * 1000.0
    mode = "all" if all_engines else ("browser" if browser else ("live-only" if live_only else "local-only"))
    return BatchReport(
        entries=entries,
        threshold=threshold,
        engines_mode=mode,
        elapsed_ms=round(elapsed, 1),
    )


# ---------------------------------------------------------------------------
# Engine registry listing
# ---------------------------------------------------------------------------

def list_engines() -> str:
    lines = ["=" * 82, " 🔧 REGISTERED DETECTION ENGINES", "=" * 82]
    groups = [
        ("Live HTTP Cloud Engines (fast, default)", LIVE_HTTP_ENGINES, False),
        ("Local Statistical Engines (instant, offline)", LOCAL_ENGINES, False),
        ("Premium Key-Based API Engines (auto-activate when key is set)", PREMIUM_KEY_ENGINES, True),
        ("Stealth Browser Engines (--browser / --all)", BROWSER_ENGINES, False),
    ]
    for title, engines, show_state in groups:
        lines.append(f"\n {title}:")
        for e in engines:
            if show_state:
                state = "ACTIVE " if e.is_configured() else "inactive"
                lines.append(f"   • {e.name:<34} weight={e.weight:.2f}  key={engine_key(e)}  [{state}]")
            else:
                lines.append(f"   • {e.name:<34} weight={e.weight:.2f}  key={engine_key(e)}")
    binoculars_note = (
        "   • Binoculars (Local Neural)            weight=0.50  key=binoculars  "
        f"[{'ACTIVE ' if BINOCULARS_ACTIVE else 'inactive'}]"
    )
    lines.append("\n Local Neural Detector (academic-grade, opt-in):")
    lines.append(binoculars_note)
    lines.append("\n Select with: --engines zerogpt,sapling,pangram,binoculars  |  --local-only | --live-only | --browser | --all")
    lines.append("=" * 82)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-detect",
        description="Multi-Format AI Text Detector CLI (19 engines: live cloud HTTP, premium key-based APIs, local neural & statistical models, stealth browser automation)"
    )
    parser.add_argument("file", nargs="?", help="Path to text, markdown, docx, pdf, html, json, or csv document to audit")
    parser.add_argument("--compare", "-c", nargs=2, metavar=("ORIGINAL", "MODIFIED"), help="Compare original vs modified documents across all engines")
    parser.add_argument("--batch", "-b", metavar="DIR", help="Batch-scan every supported document in a directory and print a ranked summary")
    parser.add_argument("--recursive", "-r", action="store_true", help="With --batch: recurse into subdirectories")
    parser.add_argument("--glob", metavar="PATTERN", help="With --batch: only files matching this glob (e.g. '*.md')")
    parser.add_argument("--live-only", action="store_true", help="Run only the live direct HTTP cloud detectors (ZeroGPT, Sapling + any configured premium APIs)")
    parser.add_argument("--local-only", action="store_true", help="Run only local engines (GLTR, Burstiness, Perplexity, Lexicon + Binoculars when enabled) without cloud API requests")
    parser.add_argument("--browser", action="store_true", help="Include Playwright browser automation engines (QuillBot, Scribbr, Writer, ...)")
    parser.add_argument("--all", action="store_true", help="Run every single engine (HTTP + Browser + Local)")
    parser.add_argument("--engines", metavar="E1,E2", help="Comma-separated engine keys to run (see --list-engines)")
    parser.add_argument("--list-engines", action="store_true", help="List all registered engines and exit")
    parser.add_argument("--workers", "-w", type=int, default=6, metavar="N", help="Max concurrent engine workers (default: 6)")
    parser.add_argument("--timeout", type=float, default=None, metavar="SEC", help="Global HTTP timeout in seconds (default: 10, env AIDETECT_TIMEOUT)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full verbose diagnostic output and engine details")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format (works for single, compare, and batch modes)")
    parser.add_argument("--export", "-e", metavar="OUTPUT_PATH", help="Export report to .json, .md, or .html file")
    parser.add_argument("--no-sentences", action="store_true", help="Hide detailed sentence-level extraction breakdown")
    parser.add_argument("--threshold", "-t", type=int, default=30, help="Maximum AI percentage allowed to exit with code 0 (default: 30)")
    parser.add_argument("--stdin", action="store_true", help="Read text directly from standard input")
    return parser


DEMO_TEXT = (
    "When evaluating relational databases versus NoSQL solutions, it is crucial to delve "
    "into the multifaceted trade-offs. Furthermore, scalability plays a pivotal role in "
    "modern software architecture. For instance, developers can optimize latency, enhance "
    "reliability, and bolster data integrity. In conclusion, understanding these nuances is "
    "paramount for fostering long-term technological success."
)


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "timeout", None):
        from . import http_client
        http_client.configure_timeout(args.timeout)

    if args.list_engines:
        print(list_engines())
        sys.exit(0)

    engine_selection = [e for e in (args.engines or "").split(",") if e.strip()] or None

    # Mode 1: Engine listing (handled above), Batch Audit
    if args.batch:
        batch = run_batch(
            directory=args.batch,
            threshold=args.threshold,
            live_only=args.live_only,
            local_only=args.local_only,
            browser=args.browser,
            all_engines=args.all,
            recursive=args.recursive,
            pattern=args.glob,
            max_workers=args.workers,
            only=engine_selection,
        )
        if args.export:
            _write_export(args.export, batch_report=batch)
            print(f"✅ Batch report exported to: {args.export}", file=sys.stderr)
        if args.json:
            print(export_batch_json(batch))
        else:
            print(format_batch_report(batch))
        any_success = any(e.report for e in batch.entries)
        exceeded = any(e.report and e.report.consensus_ai_probability > args.threshold for e in batch.entries)
        sys.exit(1 if (exceeded or not any_success) else 0)

    # Mode 2: Comparative Audit
    if args.compare:
        try:
            text1 = load_document(args.compare[0])
            text2 = load_document(args.compare[1])
        except Exception as e:
            print(f"❌ Error loading documents: {e}", file=sys.stderr)
            sys.exit(1)
        rep1 = analyze_text(text1, live_only=args.live_only, local_only=args.local_only,
                            browser=args.browser, all_engines=args.all,
                            max_workers=args.workers, source=args.compare[0], only=engine_selection)
        rep2 = analyze_text(text2, live_only=args.live_only, local_only=args.local_only,
                            browser=args.browser, all_engines=args.all,
                            max_workers=args.workers, source=args.compare[1], only=engine_selection)
        if args.export:
            _write_export(args.export, report=rep2)
            print(f"✅ Report exported to: {args.export}", file=sys.stderr)
        if args.json:
            delta = rep1.consensus_ai_probability - rep2.consensus_ai_probability
            combined = {
                "original": json.loads(export_json(rep1)),
                "modified": json.loads(export_json(rep2)),
                "risk_reduction": round(delta, 1),
            }
            print(json.dumps(combined, indent=2))
        else:
            print(format_comparative_report(rep1, rep2))
        sys.exit(1 if rep2.consensus_ai_probability > args.threshold else 0)

    # Mode 3: Single Text / Document Audit
    if args.stdin or (not sys.stdin.isatty() and not args.file):
        text = sys.stdin.read()
        source = "<stdin>"
    elif args.file:
        try:
            text = load_document(args.file)
            source = args.file
        except Exception as e:
            print(f"❌ Error loading document: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        text = DEMO_TEXT
        source = "demo"
        print("Usage: ai-detect <file.docx | file.pdf | file.md | file.txt> or pipe input. Run 'ai-detect --help' for options.\n", file=sys.stderr)
        print("Running benchmark on standard AI sample text:\n", file=sys.stderr)

    report = analyze_text(text, live_only=args.live_only, local_only=args.local_only,
                          browser=args.browser, all_engines=args.all,
                          max_workers=args.workers, source=source, only=engine_selection)

    if args.export:
        _write_export(args.export, report=report)
        print(f"✅ Report successfully exported to: {args.export}", file=sys.stderr)

    if args.json:
        print(export_json(report))
    else:
        print(format_terminal_report(report, show_sentences=not args.no_sentences, verbose=args.verbose))

    sys.exit(1 if report.consensus_ai_probability > args.threshold else 0)


def _write_export(path: str, report: Optional[DetectionReport] = None, batch_report: Optional[BatchReport] = None) -> None:
    lower = path.lower()
    if lower.endswith(".json"):
        content = export_json(report) if report is not None else export_batch_json(batch_report)  # type: ignore[arg-type]
    elif lower.endswith(".html"):
        content = export_html(report) if report is not None else export_batch_html(batch_report)  # type: ignore[arg-type]
    elif lower.endswith(".md") or lower.endswith(".markdown"):
        if report is not None:
            content = export_markdown(report)
        else:
            raise ValueError("Batch markdown export is not supported; use .json or .html")
    else:
        raise ValueError("Unsupported export format. Use .json, .md, or .html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
