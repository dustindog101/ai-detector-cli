"""
Reporting and terminal visualization for AI Detector CLI.
Formats console output, sentence-level extraction, ASCII rhythm graphs, and JSON/Markdown exports.
"""

import json
from typing import Dict, Any, List
from .models import DetectionReport, SentenceAnalysis

def format_terminal_report(report: DetectionReport, show_sentences: bool = True, verbose: bool = False) -> str:
    lines = []
    lines.append("=" * 82)
    lines.append(" 🛡️  MULTI-ENGINE AI TEXT DETECTION CONSENSUS AUDIT")
    lines.append("=" * 82)
    lines.append(f" 📊 CONSENSUS SCORE:    {report.consensus_ai_probability}% AI Probability ({report.consensus_human_probability}% Human)")
    lines.append(f" 🚦 OVERALL VERDICT:    {report.consensus_verdict}")
    lines.append(f" ⚠️  RISK ASSESSMENT:   {report.risk_level}")
    lines.append("-" * 82)
    lines.append(f" {'ENGINE / DETECTOR':<34} | {'AI %':<8} | {'VERDICT':<10} | {'KEY SIGNAL / FEEDBACK':<22}")
    lines.append("-" * 82)

    for eng in report.engines.values():
        if eng.available:
            fb = ""
            if "feedback" in eng.details:
                fb = str(eng.details["feedback"])[:22]
            elif "extracted_percentage" in eng.details:
                fb = str(eng.details["extracted_percentage"])[:22]
            elif "verdict_label" in eng.details:
                fb = str(eng.details["verdict_label"])[:22]
            elif "burstiness_ratio (sigma / mu)" in eng.details:
                fb = f"Ratio: {eng.details['burstiness_ratio (sigma / mu)']}"
            elif "rare_words_percentage (Red/Purple)" in eng.details:
                fb = f"{eng.details['rare_words_percentage (Red/Purple)']}% rare tokens"
            elif "buzzwords_found" in eng.details:
                fb = f"{eng.details['buzzword_count']} buzzwords found"
            elif "vocabulary_entropy" in eng.details:
                fb = f"Entropy: {eng.details['vocabulary_entropy']}"
            lines.append(f" {eng.engine_name:<34} | {eng.ai_percentage:>5.1f}% | {eng.verdict:<10} | {fb:<22}")
        else:
            err = eng.error or "Unavailable"
            lines.append(f" {eng.engine_name:<34} | {'N/A':>6} | {'OFFLINE':<10} | {err[:22]}")

    lines.append("-" * 82)
    lines.append(" 📈 SENTENCE CADENCE & BURSTINESS RHYTHM CHART:")
    lengths = [s.word_count for s in report.sentences]
    max_len = max(lengths) if lengths else 1
    for idx, s in enumerate(report.sentences, 1):
        bars = int((s.word_count / max_len) * 26) if max_len > 0 else 1
        flag_marker = "🚩 [AI RISK]" if s.flagged else "🟢 [HUMAN]"
        lines.append(f"    S{idx:02d} ({s.word_count:2d}w): |{'█' * max(1, bars):<26}| {flag_marker}")

    if show_sentences and report.sentences:
        lines.append("-" * 82)
        lines.append(" 📝 SENTENCE-LEVEL EXTRACTION & CLASSIFICATION:")
        for s in report.sentences:
            status = "🔴 FLAGGED AS AI" if s.flagged else "🟢 HUMAN-SOUNDING"
            lines.append(f"\n  [Sentence {s.index + 1}] ({s.word_count} words | {status} - {s.ai_probability:.0f}% AI Risk)")
            lines.append(f"  \"{s.text}\"")
            if s.reasons:
                lines.append(f"  ↳ Reasons: {', '.join(s.reasons)}")

    if verbose:
        lines.append("-" * 82)
        lines.append(" 🔍 VERBOSE ENGINE DIAGNOSTICS & METRICS:")
        lines.append(f"  • Total Words:             {report.word_count}")
        lines.append(f"  • Total Sentences:         {report.sentence_count}")
        lines.append(f"  • Mean Sentence Length:    {report.mean_sentence_length:.2f} words")
        lines.append(f"  • Sentence Length Std Dev: {report.sentence_length_std_dev:.2f}")
        lines.append(f"  • Burstiness Ratio (σ/μ):  {report.burstiness_ratio:.2f} (Target: >0.58)")
        lines.append(f"  • Em Dashes Count:         {report.em_dash_count}")
        lines.append(f"  • Semicolons Count:        {report.semicolon_count}")
        lines.append(f"  • Tripartite Lists Count:  {report.tripartite_list_count}")
        for k, v in report.engines.items():
            if v.details:
                lines.append(f"\n  [{v.engine_name} Details]")
                for dk, dv in v.details.items():
                    lines.append(f"    - {dk}: {dv}")

    if report.banned_words_found:
        lines.append("-" * 82)
        lines.append(f" ❌ HIGH-RISK AI BUZZWORDS FOUND: {', '.join(report.banned_words_found)}")

    lines.append("=" * 82)
    return "\n".join(lines)

def format_comparative_report(report_orig: DetectionReport, report_mod: DetectionReport) -> str:
    lines = []
    lines.append("\n" + "=" * 82)
    lines.append(" 🔄 MULTI-DETECTOR COMPARATIVE AUDIT (BEFORE vs. AFTER)")
    lines.append("=" * 82)
    lines.append(f" {'METRIC / DETECTOR':<34} | {'ORIGINAL (UNMODIFIED)':<20} | {'MODIFIED (HUMANIZED)':<20}")
    lines.append("-" * 82)
    lines.append(f" {'Consensus AI Probability':<34} | {report_orig.consensus_ai_probability:>18.1f}% | {report_mod.consensus_ai_probability:>18.1f}%")

    for key, eng_orig in report_orig.engines.items():
        eng_mod = report_mod.engines.get(key)
        val_orig = f"{eng_orig.ai_percentage:.1f}%" if eng_orig.available else "Offline"
        val_mod = f"{eng_mod.ai_percentage:.1f}%" if (eng_mod and eng_mod.available) else "Offline"
        lines.append(f" {eng_orig.engine_name:<34} | {val_orig:>19} | {val_mod:>19}")

    lines.append(f" {'Burstiness Ratio (σ/μ)':<34} | {report_orig.burstiness_ratio:>19.2f} | {report_mod.burstiness_ratio:>19.2f}")
    lines.append(f" {'Banned AI Buzzwords':<34} | {len(report_orig.banned_words_found):>19} | {len(report_mod.banned_words_found):>19}")
    lines.append(f" {'Em Dashes (—)':<34} | {report_orig.em_dash_count:>19} | {report_mod.em_dash_count:>19}")
    lines.append("=" * 82)

    delta = report_orig.consensus_ai_probability - report_mod.consensus_ai_probability
    lines.append(f" 🎉 AI RISK REDUCTION: {delta:.1f}% drop in AI detection probability")
    if report_mod.consensus_ai_probability < 20.0:
        lines.append(" ✅ VERDICT: 100% READY FOR SUBMISSION (0% AI DETECTION RISK)")
    else:
        lines.append(" ⚠️ VERDICT: BORDERLINE - RECOMMEND FURTHER CADENCE VARIANCE")
    lines.append("")
    return "\n".join(lines)

def export_json(report: DetectionReport) -> str:
    data = {
        "word_count": report.word_count,
        "sentence_count": report.sentence_count,
        "consensus_ai_probability": report.consensus_ai_probability,
        "consensus_human_probability": report.consensus_human_probability,
        "consensus_verdict": report.consensus_verdict,
        "risk_level": report.risk_level,
        "burstiness_ratio": report.burstiness_ratio,
        "mean_sentence_length": report.mean_sentence_length,
        "sentence_length_std_dev": report.sentence_length_std_dev,
        "banned_words_found": report.banned_words_found,
        "em_dash_count": report.em_dash_count,
        "semicolon_count": report.semicolon_count,
        "tripartite_list_count": report.tripartite_list_count,
        "engines": {
            k: {
                "name": v.engine_name,
                "available": v.available,
                "ai_percentage": v.ai_percentage,
                "human_percentage": v.human_percentage,
                "verdict": v.verdict,
                "details": v.details,
                "flagged_sentences": v.flagged_sentences,
                "error": v.error
            } for k, v in report.engines.items()
        },
        "sentences": [
            {
                "index": s.index,
                "text": s.text,
                "word_count": s.word_count,
                "ai_probability": s.ai_probability,
                "flagged": s.flagged,
                "reasons": s.reasons
            } for s in report.sentences
        ]
    }
    return json.dumps(data, indent=2)

def export_markdown(report: DetectionReport) -> str:
    md = []
    md.append("# AI Detection Consensus Audit Report\n")
    md.append(f"- **Consensus AI Probability:** {report.consensus_ai_probability}%")
    md.append(f"- **Consensus Human Probability:** {report.consensus_human_probability}%")
    md.append(f"- **Verdict:** {report.consensus_verdict}")
    md.append(f"- **Risk Level:** {report.risk_level}\n")
    md.append("## Detection Engine Breakdown\n")
    md.append("| Engine | AI % | Human % | Verdict | Status | Key Details |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for eng in report.engines.values():
        status = "Active" if eng.available else "Offline"
        details_str = json.dumps(eng.details) if eng.details else (eng.error or "N/A")
        md.append(f"| {eng.engine_name} | {eng.ai_percentage:.1f}% | {eng.human_percentage:.1f}% | {eng.verdict} | {status} | {details_str[:40]} |")

    md.append("\n## Stylometric Cadence Metrics\n")
    md.append(f"- **Word Count:** {report.word_count}")
    md.append(f"- **Sentence Count:** {report.sentence_count}")
    md.append(f"- **Mean Sentence Length:** {report.mean_sentence_length:.1f} words")
    md.append(rf"- **Burstiness Ratio ($\sigma/\mu$):** {report.burstiness_ratio:.2f}")
    md.append(f"- **High-Risk AI Words Found:** {', '.join(report.banned_words_found) if report.banned_words_found else 'None'}\n")

    md.append("## Sentence-by-Sentence Breakdown\n")
    for s in report.sentences:
        status_icon = "🔴 AI Flagged" if s.flagged else "🟢 Human"
        md.append(f"### Sentence {s.index + 1} ({s.word_count} words | {status_icon} - {s.ai_probability:.0f}% Risk)")
        md.append(f"> {s.text}\n")
        if s.reasons:
            md.append(f"*Reasons: {', '.join(s.reasons)}*\n")

    return "\n".join(md)
