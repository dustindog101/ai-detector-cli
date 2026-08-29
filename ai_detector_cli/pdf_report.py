"""
Academic PDF report generator for AI Detector CLI (reportlab-based).

Renders a formal provenance-audit document mirroring the academic HTML
report: ruled masthead, similarity-index band, numbered sections, engine
results table, stylometric signals, sentence-level findings, and a
methodology & limitations section with page numbers.

Requires the `reportlab` package (install via the [pdf] extra). All text is
cp1252-safe for the built-in Type 1 fonts; no external font files needed.
Compatible with Python 3.8+.
"""

import hashlib
import time

from . import __version__
from .models import DetectionReport, BatchReport

# ---------------------------------------------------------------- palette ----
NAVY = "#182c52"
BURGUNDY = "#77202c"
GOLD = "#a98a45"
INK = "#21293a"
MUTED = "#5f6b80"
RULE = "#d9d2bf"
PANEL2 = "#f5f3ec"
GREEN = "#2c6e4d"
YELLOW = "#8f6f14"
ORANGE = "#a4551c"
RED = "#8d2231"


_PDF_REQUIREMENT_NOTE = (
    "PDF export requires the 'reportlab' package on Python 3.9+ (reportlab 4.x "
    "uses a hashlib API unavailable on 3.8). Install it with: "
    "pip install 'ai-detector-cli[pdf]'")


def _require_reportlab():
    """Import reportlab and verify the runtime actually supports it.

    reportlab 4.x internally calls hashlib.md5(..., usedforsecurity=False),
    a keyword argument added in Python 3.9. On 3.8 the import succeeds but
    document builds crash, so probe the kwarg up front and fail with a
    clear, actionable message instead.
    """
    try:
        import reportlab  # noqa: F401
        from reportlab import platypus  # noqa: F401
    except ImportError as exc:
        raise SystemExit(_PDF_REQUIREMENT_NOTE) from exc
    try:
        hashlib.md5(b"probe", usedforsecurity=False)
    except TypeError as exc:
        raise SystemExit(_PDF_REQUIREMENT_NOTE) from exc


def _verdict_color(ai_pct: float) -> str:
    if ai_pct < 20.0:
        return GREEN
    if ai_pct < 45.0:
        return YELLOW
    if ai_pct < 70.0:
        return ORANGE
    return RED


def _stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())


def _report_id(source: str, extra: str = "") -> str:
    seed = f"{source}|{extra}|{_stamp()}|{__version__}"
    return "AIA-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10].upper()


def _risk_interpretation(ai_pct: float) -> str:
    if ai_pct < 20.0:
        return ("The engines surveyed attribute this document predominantly to human "
                "authorship. Statistical markers commonly associated with machine "
                "generation are minimal, and no coordinated AI signature was observed.")
    if ai_pct < 45.0:
        return ("The evidence is mixed: several engines lean human while others flag "
                "AI-style structure. Particular sentences, rather than the document as "
                "a whole, warrant scrutiny; consult the sentence-level findings below.")
    if ai_pct < 70.0:
        return ("A majority of engines lean machine-generated. The document exhibits "
                "structural and lexical patterns characteristic of AI generation, though "
                "human editing may be present in places.")
    return ("The panel exhibits strong agreement that the document is machine-generated. "
            "Pervasive AI-typical phrasing, cadence, and token distributions were observed.")


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _build_styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER

    body = ParagraphStyle(
        "Body", fontName="Times-Roman", fontSize=10.5, leading=15,
        textColor=INK, alignment=TA_JUSTIFY, spaceAfter=7)
    h2 = ParagraphStyle(
        "H2", fontName="Helvetica-Bold", fontSize=9.5, leading=13,
        textColor=NAVY, spaceBefore=13, spaceAfter=7)
    masthead_over = ParagraphStyle(
        "MastOver", fontName="Helvetica-Bold", fontSize=8, leading=11,
        textColor=BURGUNDY, alignment=TA_CENTER)
    masthead_title = ParagraphStyle(
        "MastTitle", fontName="Times-Bold", fontSize=22, leading=27,
        textColor=NAVY, alignment=TA_CENTER, spaceBefore=5)
    masthead_sub = ParagraphStyle(
        "MastSub", fontName="Times-Italic", fontSize=11, leading=15,
        textColor=MUTED, alignment=TA_CENTER, spaceBefore=2)
    meta_k = ParagraphStyle(
        "MetaK", fontName="Helvetica", fontSize=6.3, leading=9,
        textColor=MUTED, alignment=TA_CENTER)
    meta_v = ParagraphStyle(
        "MetaV", fontName="Helvetica-Bold", fontSize=9, leading=12,
        textColor=INK, alignment=TA_CENTER)
    score_big = ParagraphStyle(
        "ScoreBig", fontName="Times-Bold", fontSize=34, leading=38,
        textColor=BURGUNDY, alignment=TA_CENTER)
    score_k = ParagraphStyle(
        "ScoreK", fontName="Helvetica", fontSize=7, leading=10,
        textColor=MUTED, alignment=TA_CENTER)
    small = ParagraphStyle(
        "Small", fontName="Helvetica", fontSize=7.5, leading=10.5,
        textColor=MUTED)
    cell = ParagraphStyle(
        "Cell", fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=INK)
    cell_b = ParagraphStyle(
        "CellB", fontName="Helvetica-Bold", fontSize=8.5, leading=11.5, textColor=INK)
    sent_text = ParagraphStyle(
        "SentText", fontName="Times-Roman", fontSize=10, leading=13.5,
        textColor=INK, alignment=TA_JUSTIFY)
    sent_meta = ParagraphStyle(
        "SentMeta", fontName="Helvetica", fontSize=7, leading=9.5,
        textColor=MUTED, spaceBefore=5)
    return dict(mm=mm, body=body, h2=h2, masthead_over=masthead_over,
                masthead_title=masthead_title, masthead_sub=masthead_sub,
                meta_k=meta_k, meta_v=meta_v, score_big=score_big,
                score_k=score_k, small=small, cell=cell, cell_b=cell_b,
                sent_text=sent_text, sent_meta=sent_meta,
                center=TA_CENTER)


def _header_footer(report_id: str):
    from reportlab.lib.colors import HexColor

    def draw(canvas, doc):
        canvas.saveState()
        w, _h = canvas._pagesize
        # footer rule + page identity on every page
        canvas.setStrokeColor(HexColor(RULE))
        canvas.setLineWidth(0.6)
        canvas.line(50, 40, w - 50, 40)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(HexColor(MUTED))
        canvas.drawString(50, 30, f"Report {report_id} · {_stamp()}")
        canvas.drawRightString(w - 50, 30,
                               f"ai-detector-cli v{__version__} · Page {doc.page}")
        canvas.setFont("Helvetica", 6)
        canvas.drawCentredString(w / 2, 20,
                                 "Heuristic consensus - not a verdict of authorship")
        canvas.restoreState()

    return draw


def _tier_of(engine_name: str) -> str:
    browser = {"GPTZero Detector", "CopyLeaks AI Detector", "QuillBot AI Detector",
               "Scribbr AI Detector", "Writer.com AI Detector", "ContentDetector.ai",
               "IsGen AI Detector", "Grammarly AI Detector"}
    premium = {"GPTZero Official API", "Winston AI API", "Originality.ai API",
               "Pangram API", "Detecting-AI API"}
    if engine_name in {"ZeroGPT Live Cloud API", "Sapling AI Detector"}:
        return "Live Cloud APIs"
    if engine_name in premium:
        return "Premium Key-Based APIs"
    if engine_name == "Binoculars (Local Neural)":
        return "Local Neural Engines"
    if engine_name in {"GLTR Rank & Token Distribution", "Burstiness & Cadence Model",
                       "Perplexity & Predictability Model",
                       "PubMed AI Lexicon & Tells"}:
        return "Local Statistical Engines"
    if engine_name in browser:
        return "Stealth Browser Detectors"
    return "Other Engines"


def _executive_summary(report: DetectionReport, st, rid: str) -> list:
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.colors import HexColor

    ai = report.consensus_ai_probability
    color = _verdict_color(ai)
    flow = []

    flow.append(Paragraph("§1&nbsp;&nbsp;EXECUTIVE SUMMARY", st["h2"]))
    score_cell = [Paragraph(f"{ai:.1f}", st["score_big"]),
                  Paragraph("% AI PROBABILITY", st["score_k"])]
    verdict_cell = [
        Paragraph(f"Verdict: <b>{_esc(report.consensus_verdict)}</b>", st["cell_b"]),
        Spacer(1, 4),
        Paragraph(f"Assessed risk level: <b>{_esc(report.risk_level)}</b>", st["cell"]),
        Spacer(1, 5),
        Paragraph(f"Human-attributed: {report.consensus_human_probability:.1f}% · "
                  f"AI-attributed: {ai:.1f}%", st["cell"]),
    ]
    t = Table([[score_cell, verdict_cell]], colWidths=[55 * st["mm"], 117 * st["mm"]])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), HexColor(PANEL2)),
        ("BOX", (0, 0), (-1, -1), 0.8, HexColor(RULE)),
        ("LINEBEFORE", (1, 0), (1, 0), 2.2, HexColor(color)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(_esc(_risk_interpretation(ai)), st["body"]))
    return flow


def _scale_section(report: DetectionReport, st) -> list:
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.colors import HexColor

    ai = max(0.0, min(100.0, report.consensus_ai_probability))
    zones = [("0-19", "Likely human", GREEN), ("20-44", "Mixed", YELLOW),
             ("45-69", "Elevated", ORANGE), ("70-100", "Likely AI", RED)]
    row = []
    for lo_hi, label, color in zones:
        row.append([Paragraph(f"<b>{lo_hi}</b>", st["cell_b"]),
                    Paragraph(f"<font color='{color}'>{label}</font>", st["cell"])])
    marker_cell = [Paragraph(f"<b>Consensus: {ai:.1f}</b>", st["cell_b"])]
    data = [row + [marker_cell]]
    t = Table(data, colWidths=[24 * st["mm"]] * 4 + [52 * st["mm"]])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, HexColor(RULE)),
        ("BACKGROUND", (0, 0), (0, 0), HexColor("#e9f1ea")),
        ("BACKGROUND", (1, 0), (1, 0), HexColor("#f7f1dd")),
        ("BACKGROUND", (2, 0), (2, 0), HexColor("#f7ead9")),
        ("BACKGROUND", (3, 0), (3, 0), HexColor("#f6e4e2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [Paragraph("§2&nbsp;&nbsp;CONSENSUS POSITION ON THE RISK SCALE", st["h2"]), t,
            Spacer(1, 4),
            Paragraph("The consensus estimate falls within the highlighted band "
                      "corresponding to its risk classification.", st["small"])]


def _engine_section(report: DetectionReport, st) -> list:
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor

    flow = [Paragraph("§3&nbsp;&nbsp;DETECTION RESULTS BY ENGINE", st["h2"])]
    data = [[Paragraph("<b>Engine</b>", st["cell_b"]),
             Paragraph("<b>Tier</b>", st["cell_b"]),
             Paragraph("<b>AI %</b>", st["cell_b"]),
             Paragraph("<b>Verdict</b>", st["cell_b"]),
             Paragraph("<b>Weight</b>", st["cell_b"]),
             Paragraph("<b>Note</b>", st["cell_b"])]]
    for eng in report.engines.values():
        if eng.available:
            color = _verdict_color(eng.ai_percentage)
            note = f"{len(eng.flagged_sentences)} flagged sentence(s)" if eng.flagged_sentences else ""
            data.append([
                Paragraph(_esc(eng.engine_name), st["cell"]),
                Paragraph(_esc(_tier_of(eng.engine_name)), st["cell"]),
                Paragraph(f"<font color='{color}'><b>{eng.ai_percentage:.1f}</b></font>", st["cell"]),
                Paragraph(_esc(eng.verdict), st["cell"]),
                Paragraph(f"{eng.weight:g}", st["cell"]),
                Paragraph(_esc(note), st["cell"]),
            ])
        else:
            data.append([
                Paragraph(_esc(eng.engine_name), st["cell"]),
                Paragraph(_esc(_tier_of(eng.engine_name)), st["cell"]),
                Paragraph("-", st["cell"]),
                Paragraph("OFFLINE", st["cell"]),
                Paragraph("-", st["cell"]),
                Paragraph(_esc((eng.error or "unavailable")[:60]), st["cell"]),
            ])
    t = Table(data, colWidths=[44 * st["mm"], 32 * st["mm"], 16 * st["mm"],
                               20 * st["mm"], 14 * st["mm"], 46 * st["mm"]],
              repeatRows=1)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor(RULE)),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            style.append(("BACKGROUND", (0, r), (-1, r), HexColor(PANEL2)))
    t.setStyle(TableStyle(style))
    flow.append(t)
    return flow


def _agreement_section(report: DetectionReport, st) -> list:
    from reportlab.platypus import Paragraph
    scores = [e.ai_percentage for e in report.engines.values() if e.available]
    if len(scores) < 2:
        return [Paragraph("§4&nbsp;&nbsp;INTER-ENGINE AGREEMENT", st["h2"]),
                Paragraph("Fewer than two engines reported scores; agreement analysis "
                          "is not meaningful for this run.", st["body"])]
    spread = max(scores) - min(scores)
    if spread < 15.0:
        label, note = "Strong concordance", ("Engines landed within a narrow band, "
                                             "which strengthens confidence in the consensus estimate.")
    elif spread < 35.0:
        label, note = "Moderate concordance", ("Engines disagree noticeably; inspect "
                                               "the per-engine findings before drawing conclusions.")
    else:
        label, note = "Low concordance", ("Engines diverge sharply; the headline figure "
                                          "is unstable and the individual verdicts deserve greater weight.")
    from reportlab.platypus import Paragraph
    return [Paragraph("§4&nbsp;&nbsp;INTER-ENGINE AGREEMENT", st["h2"]),
            Paragraph(f"<b>Max-min spread:</b> {spread:.1f} points across "
                      f"{len(scores)} reporting engines - <b>{label}</b>. {note}",
                      st["body"])]


def _signals_section(report: DetectionReport, st) -> list:
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
    rows = [
        ("Words", f"{report.word_count:,}"),
        ("Sentences", f"{report.sentence_count:,}"),
        ("Mean sentence length (± s.d.)",
         f"{report.mean_sentence_length:.1f} ± {report.sentence_length_std_dev:.1f}"),
        ("Burstiness (std/mean of sentence length)", f"{report.burstiness_ratio:.2f}"),
        ("AI buzzwords detected", f"{len(report.banned_words_found)}"),
        ("Em dashes", f"{report.em_dash_count}"),
        ("Semicolons", f"{report.semicolon_count}"),
        ("Tripartite lists", f"{report.tripartite_list_count}"),
    ]
    data = [[Paragraph("<b>Signal</b>", st["cell_b"]),
             Paragraph("<b>Value</b>", st["cell_b"])]]
    for k, v in rows:
        data.append([Paragraph(_esc(k), st["cell"]), Paragraph(_esc(v), st["cell"])])
    t = Table(data, colWidths=[100 * st["mm"], 72 * st["mm"]])
    style = [("GRID", (0, 0), (-1, -1), 0.4, HexColor(RULE)),
             ("BACKGROUND", (0, 0), (-1, 0), HexColor(NAVY)),
             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    for r in range(1, len(data)):
        if r % 2 == 0:
            style.append(("BACKGROUND", (0, r), (-1, r), HexColor(PANEL2)))
    t.setStyle(TableStyle(style))
    tells = ("; ".join(report.banned_words_found)
             if report.banned_words_found else "None detected")
    return [Paragraph("§5&nbsp;&nbsp;STYLOMETRIC SIGNALS", st["h2"]), t, Spacer(1, 6),
            Paragraph(f"<b>AI vocabulary markers:</b> {_esc(tells)}", st["body"])]


def _findings_section(report: DetectionReport, st) -> list:
    from reportlab.platypus import Paragraph
    flow = [Paragraph("§6&nbsp;&nbsp;SENTENCE-LEVEL FINDINGS", st["h2"])]
    if not report.sentences:
        flow.append(Paragraph("Sentence-level analysis is disabled or the document "
                              "contained no sentences.", st["body"]))
        return flow
    for s in report.sentences:
        if not s.flagged:
            continue
        reasons = _esc(", ".join(s.reasons)) if s.reasons else "heuristic flag"
        flow.append(Paragraph(
            f"#{s.index + 1} · {s.word_count} words · {s.ai_probability:.0f}% AI risk · "
            f"Reasons: {reasons}", st["sent_meta"]))
        flow.append(Paragraph(_esc(s.text), st["sent_text"]))
    if not any(s.flagged for s in report.sentences):
        flow.append(Paragraph("No individual sentences were flagged by the "
                              "sentence-level heuristics.", st["body"]))
    return flow


def _methodology_section(report: DetectionReport, engine_count: int, st) -> list:
    from reportlab.platypus import Paragraph
    return [
        Paragraph("§7&nbsp;&nbsp;METHODOLOGY &amp; LIMITATIONS", st["h2"]),
        Paragraph(f"<b>1. Computation of the consensus estimate.</b> Each available "
                  f"engine returns an AI probability on a 0-100 scale. The consensus "
                  f"reported here is the weighted mean of those estimates, where each "
                  f"engine carries a trust weight reflecting its demonstrated reliability "
                  f"({engine_count} engines contributed to this report in "
                  f"{_esc(report.engine_mode)} mode). Engines that error or are "
                  f"unavailable are excluded from the denominator entirely.", st["body"]),
        Paragraph("<b>2. Interpretation of risk bands.</b> Risk bands map onto the "
                  "consensus estimate as follows: 0-19 low, 20-44 mixed, 45-69 elevated, "
                  "70-100 high. The command-line exit code mirrors a configurable "
                  "threshold (30% by default).", st["body"]),
        Paragraph("<b>3. Limitations.</b> AI-text detection is probabilistic rather "
                  "than conclusive. Short passages, formulaic writing, and lightly "
                  "paraphrased machine text can each skew results in either direction. "
                  "This report constitutes investigative signal and should never serve "
                  "as the sole basis for allegations of academic or professional "
                  "misconduct.", st["body"]),
    ]


def export_pdf_bytes(report: DetectionReport) -> bytes:
    """Render one DetectionReport as an academic PDF document (bytes)."""
    _require_reportlab()
    try:
        import io
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor
    except ImportError as exc:
        raise SystemExit(_PDF_REQUIREMENT_NOTE) from exc

    st = _build_styles()
    rid = _report_id(report.source, f"{report.consensus_ai_probability:.1f}")
    available = [e for e in report.engines.values() if e.available]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * st["mm"], rightMargin=18 * st["mm"],
        topMargin=16 * st["mm"], bottomMargin=20 * st["mm"],
        title="AI Text Detection Report", author="ai-detector-cli")
    story = []

    # Masthead
    story.append(Paragraph("AI PROVENANCE AUDIT", st["masthead_over"]))
    story.append(Paragraph("AI Text Detection Report", st["masthead_title"]))
    story.append(Paragraph("A multi-engine consensus audit of textual provenance",
                           st["masthead_sub"]))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2.4, color=HexColor(NAVY)))
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=0.7, color=HexColor(GOLD)))
    story.append(Spacer(1, 10))

    meta = [("Report ID", rid), ("Issued", _stamp()),
            ("Source", report.source), ("Mode", report.engine_mode),
            ("Words", f"{report.word_count:,}"),
            ("Engines", f"{len(available)}/{len(report.engines)}")]
    meta_row = [[Paragraph(f"<font size=6 color='{MUTED}'>{_esc(k).upper()}</font><br/>"
                           f"<b>{_esc(v)}</b>", st["meta_v"]) for k, v in meta]]
    mt = Table(meta_row, colWidths=[28.8 * st["mm"]] * 6)
    mt.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, HexColor(RULE)),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, HexColor(RULE)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(mt)
    story.append(Spacer(1, 10))

    if report.degraded:
        note = report.degradation_note or "Live engines degraded to local-only mode."
        story.append(Paragraph(f"<b>Notice:</b> {_esc(note)}", st["small"]))
        story.append(Spacer(1, 6))

    story.extend(_executive_summary(report, st, rid))
    story.extend(_scale_section(report, st))
    story.extend(_engine_section(report, st))
    story.extend(_agreement_section(report, st))
    story.extend(_signals_section(report, st))
    story.extend(_findings_section(report, st))
    story.extend(_methodology_section(report, len(available), st))

    doc.build(story, onFirstPage=_header_footer(rid), onLaterPages=_header_footer(rid))
    return buf.getvalue()


def export_batch_pdf_bytes(batch: BatchReport) -> bytes:
    """Render a BatchReport as an academic PDF document (bytes)."""
    try:
        import io
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.colors import HexColor
    except ImportError as exc:
        raise SystemExit(
            "PDF export requires the 'reportlab' package. "
            "Install it with: pip install 'ai-detector-cli[pdf]'"
        ) from exc

    st = _build_styles()
    ok = [e for e in batch.entries if e.report]
    scores = [e.report.consensus_ai_probability for e in ok]
    avg = sum(scores) / len(scores) if scores else 0.0
    flagged = sum(1 for e in ok if e.report.consensus_ai_probability > batch.threshold)
    rid = _report_id(f"batch:{len(batch.entries)}", f"{avg:.1f}")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * st["mm"], rightMargin=18 * st["mm"],
        topMargin=16 * st["mm"], bottomMargin=20 * st["mm"],
        title="Batch AI Detection Report", author="ai-detector-cli")
    story = []

    story.append(Paragraph("AI PROVENANCE AUDIT", st["masthead_over"]))
    story.append(Paragraph("Batch AI Detection Report", st["masthead_title"]))
    story.append(Paragraph("A ranked provenance survey of a document corpus",
                           st["masthead_sub"]))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2.4, color=HexColor(NAVY)))
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=0.7, color=HexColor(GOLD)))
    story.append(Spacer(1, 10))

    meta = [("Report ID", rid), ("Issued", _stamp()), ("Files", f"{len(batch.entries)}"),
            ("Mode", batch.engines_mode), ("Threshold", f"{batch.threshold:.0f}%"),
            ("Flagged", f"{flagged}")]
    meta_row = [[Paragraph(f"<font size=6 color='{MUTED}'>{_esc(k).upper()}</font><br/>"
                           f"<b>{_esc(v)}</b>", st["meta_v"]) for k, v in meta]]
    mt = Table(meta_row, colWidths=[28.8 * st["mm"]] * 6)
    mt.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, HexColor(RULE)),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, HexColor(RULE)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(mt)
    story.append(Spacer(1, 10))

    # Summary
    story.append(Paragraph("§1&nbsp;&nbsp;SUMMARY OF FINDINGS", st["h2"]))
    story.append(Paragraph(
        f"<b>{len(batch.entries)}</b> documents were scanned in "
        f"<b>{batch.elapsed_ms:.0f} ms</b>; <b>{flagged}</b> exceeded the "
        f"{batch.threshold:.0f}% consensus threshold. The mean AI probability across "
        f"the corpus is <b>{avg:.1f}%</b>"
        + (f", with a maximum of <b>{max(scores):.1f}%</b>." if scores else "."),
        st["body"]))

    # Ranked table
    story.append(Paragraph("§2&nbsp;&nbsp;PER-FILE RESULTS (RANKED BY AI SCORE)", st["h2"]))
    data = [[Paragraph("<b>#</b>", st["cell_b"]),
             Paragraph("<b>File</b>", st["cell_b"]),
             Paragraph("<b>AI %</b>", st["cell_b"]),
             Paragraph("<b>Words</b>", st["cell_b"]),
             Paragraph("<b>Sent.</b>", st["cell_b"]),
             Paragraph("<b>Disposition</b>", st["cell_b"])]]
    ranked = sorted(batch.entries,
                    key=lambda e: e.report.consensus_ai_probability if e.report else -1.0,
                    reverse=True)
    for rank, entry in enumerate(ranked, 1):
        rep = entry.report
        if entry.error:
            data.append([Paragraph(f"{rank}", st["cell"]),
                         Paragraph(_esc(entry.path), st["cell"]),
                         Paragraph("-", st["cell"]), Paragraph("-", st["cell"]),
                         Paragraph("-", st["cell"]),
                         Paragraph(f"<font color='{RED}'>{_esc(entry.error[:60])}</font>",
                                   st["cell"])])
            continue
        over = rep.consensus_ai_probability > batch.threshold
        color = _verdict_color(rep.consensus_ai_probability)
        fname = entry.path.replace("\\", "/").rsplit("/", 1)[-1]
        data.append([
            Paragraph(f"{rank}", st["cell"]),
            Paragraph(_esc(fname[:48]), st["cell"]),
            Paragraph(f"<font color='{color}'><b>{rep.consensus_ai_probability:.1f}</b></font>",
                      st["cell"]),
            Paragraph(f"{rep.word_count}", st["cell"]),
            Paragraph(f"{rep.sentence_count}", st["cell"]),
            Paragraph("<b>Above threshold</b>" if over else "Within threshold", st["cell"]),
        ])
    t = Table(data, colWidths=[10 * st["mm"], 62 * st["mm"], 18 * st["mm"],
                               18 * st["mm"], 16 * st["mm"], 48 * st["mm"]],
              repeatRows=1)
    style = [("GRID", (0, 0), (-1, -1), 0.4, HexColor(RULE)),
             ("BACKGROUND", (0, 0), (-1, 0), HexColor(NAVY)),
             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for r in range(1, len(data)):
        if r % 2 == 0:
            style.append(("BACKGROUND", (0, r), (-1, r), HexColor(PANEL2)))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 8))

    story.append(Paragraph("§3&nbsp;&nbsp;METHODOLOGY &amp; LIMITATIONS", st["h2"]))
    story.append(Paragraph(
        "Documents are ordered by consensus AI probability - the weighted mean of "
        "available engines. The disposition column marks files above the configured "
        "threshold, the same standard the command-line exit code applies. Batch "
        "consensus scores are screening signals, not proof of authorship; flagged "
        "documents should be followed up with the in-depth single-file audit "
        "(ai-detect --export report.html <file>) before conclusions are drawn.",
        st["body"]))

    doc.build(story, onFirstPage=_header_footer(rid), onLaterPages=_header_footer(rid))
    return buf.getvalue()


def export_pdf(report: DetectionReport) -> bytes:
    """Render one DetectionReport as an academic PDF document (bytes)."""
    return export_pdf_bytes(report)


def export_batch_pdf(batch: BatchReport):
    return export_batch_pdf_bytes(batch)
