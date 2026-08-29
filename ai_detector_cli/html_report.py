"""
Self-contained, professional HTML report generator for AI Detector CLI.

Produces a single portable .html file (zero external assets, inline CSS/SVG,
no JavaScript) that renders an in-depth audit:

- Branded header band with report metadata chips
- Executive summary: consensus donut gauge, verdict badge, human/AI split bar
- Consensus scale with risk zones and a position marker
- Engine matrix grouped by tier, with weights, score bars, and per-engine
  diagnostic details (collapsible)
- Inter-engine agreement analysis (score spread)
- Stylometric signal grid + AI buzzword chips
- Sentence cadence chart + sentence risk distribution histogram
- Sentence-level classification cards with reasons
- Methodology and limitations section
- Optional batch summary (--batch --export report.html)

Auto-adapts to light/dark OS theme and prints cleanly.
Compatible with Python 3.8+. No third-party dependencies.
"""

import html
import json
import time

from . import __version__
from .models import DetectionReport, BatchReport

_CSS = """
:root{
  --bg:#f4f6fa;--panel:#ffffff;--panel2:#eef2f9;--text:#18202f;--muted:#5f6f8a;
  --accent:#3b4fd8;--accent2:#7a8cff;--border:#e2e8f2;--shadow:0 1px 3px rgba(24,32,47,.06);
  --green:#188a55;--green-bg:rgba(24,138,85,.10);
  --yellow:#9a6a00;--yellow-bg:rgba(214,158,46,.13);
  --orange:#c05621;--orange-bg:rgba(192,86,33,.12);
  --red:#c53030;--red-bg:rgba(197,48,48,.10);
  --zone1:#e8f5ee;--zone2:#fdf6e3;--zone3:#fdeee2;--zone4:#fbe7e7}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0e1320;--panel:#161d2e;--panel2:#1c2438;--text:#e8ecf4;--muted:#8b93a7;
    --accent:#6f86ff;--accent2:#9db0ff;--border:#2a3450;--shadow:0 1px 3px rgba(0,0,0,.35);
    --green:#2ecc71;--green-bg:rgba(46,204,113,.14);
    --yellow:#ffd166;--yellow-bg:rgba(255,209,102,.12);
    --orange:#ffa94d;--orange-bg:rgba(255,169,77,.12);
    --red:#ff5b6e;--red-bg:rgba(255,91,110,.12);
    --zone1:rgba(46,204,113,.10);--zone2:rgba(255,209,102,.08);
    --zone3:rgba(255,169,77,.08);--zone4:rgba(255,91,110,.10)}}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);
  font-family:'Segoe UI',system-ui,-apple-system,Roboto,'Helvetica Neue',Arial,sans-serif;
  line-height:1.6;font-size:15px}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 40px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}

/* ---------- header band ---------- */
.band{background:linear-gradient(120deg,#24307a 0%,#3b4fd8 55%,#5a6ef0 100%);
  color:#fff;padding:34px 0 30px;margin-bottom:26px}
.band .wrap{padding-bottom:0}
.band h1{font-size:1.65rem;font-weight:700;letter-spacing:.01em;display:flex;align-items:center;gap:12px}
.band h1 svg{flex:none}
.band .tag{color:#c9d3ff;font-size:.92rem;margin-top:4px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.chip{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.25);
  border-radius:999px;padding:3px 13px;font-size:.76rem;font-weight:500;letter-spacing:.02em}
.chip b{font-weight:700;font-variant-numeric:tabular-nums}

/* ---------- generic blocks ---------- */
h2{font-size:.86rem;margin:30px 0 12px;color:var(--accent);
  text-transform:uppercase;letter-spacing:.09em;font-weight:700}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;
  padding:22px 24px;margin-bottom:16px;box-shadow:var(--shadow)}
.sub{color:var(--muted);font-size:.85rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:12px}
.metric{background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:13px 15px}
.metric .v{font-size:1.3rem;font-weight:700;font-variant-numeric:tabular-nums}
.metric .v small{font-size:.8rem;font-weight:600;color:var(--muted)}
.metric .k{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:3px}
table{width:100%;border-collapse:collapse;font-size:.87rem}
th{color:var(--muted);text-align:left;font-weight:600;padding:8px 10px;
  border-bottom:1px solid var(--border);font-size:.74rem;text-transform:uppercase;letter-spacing:.05em}
td{padding:9px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
tr:last-child td{border-bottom:none}
.num{font-variant-numeric:tabular-nums}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.82rem}

/* ---------- badges & bars ---------- */
.badge{display:inline-block;padding:3px 12px;border-radius:999px;font-size:.78rem;
  font-weight:700;letter-spacing:.02em;white-space:nowrap}
.b-green{background:var(--green-bg);color:var(--green);border:1px solid var(--green)}
.b-yellow{background:var(--yellow-bg);color:var(--yellow);border:1px solid var(--yellow)}
.b-orange{background:var(--orange-bg);color:var(--orange);border:1px solid var(--orange)}
.b-red{background:var(--red-bg);color:var(--red);border:1px solid var(--red)}
.b-neutral{background:var(--panel2);color:var(--muted);border:1px solid var(--border)}
.bar-wrap{background:var(--panel2);border-radius:6px;height:13px;width:100%;min-width:100px;overflow:hidden}
.bar{height:100%;border-radius:6px}

/* ---------- executive summary ---------- */
.exec{display:flex;gap:30px;align-items:center;flex-wrap:wrap}
.exec .right{flex:1;min-width:290px}
.verdict-line{font-size:1.18rem;font-weight:700;margin:10px 0 6px}
.splitbar{display:flex;height:18px;border-radius:8px;overflow:hidden;margin:14px 0 6px;border:1px solid var(--border)}
.splitbar .ai{background:var(--red);opacity:.85}
.splitbar .hu{background:var(--green);opacity:.85}
.splitlegend{display:flex;justify-content:space-between;font-size:.78rem;color:var(--muted)}

/* ---------- consensus scale ---------- */
.scale{position:relative;height:34px;border-radius:9px;overflow:hidden;display:flex;border:1px solid var(--border)}
.scale .z{height:100%}
.scale .z1{background:var(--zone1)}
.scale .z2{background:var(--zone2)}
.scale .z3{background:var(--zone3)}
.scale .z4{background:var(--zone4)}
.marker{position:absolute;top:-1px;bottom:-1px;width:3px;background:var(--text);border-radius:2px}
.marker:after{content:'';position:absolute;top:-2px;left:-4px;border:6px solid transparent;border-top-color:var(--text)}
.scalelabels{display:flex;font-size:.72rem;color:var(--muted);margin-top:6px}
.scalelabels span{flex:1}
.scalelabels span:last-child{text-align:right}

/* ---------- tells ---------- */
.chiprow{display:flex;flex-wrap:wrap;gap:8px}
.tell{background:var(--red-bg);color:var(--red);border:1px solid var(--red);
  border-radius:999px;padding:3px 13px;font-size:.8rem;font-weight:600}
.tell.alt{background:var(--panel2);color:var(--muted);border-color:var(--border)}

/* ---------- engine matrix ---------- */
.tier{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;
  font-weight:700;margin:16px 0 6px}
.tier:first-child{margin-top:0}
details.eng{border:1px solid var(--border);border-radius:10px;background:var(--panel2);
  margin-bottom:8px;overflow:hidden}
details.eng summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;
  padding:10px 14px;flex-wrap:wrap}
details.eng summary::-webkit-details-marker{display:none}
details.eng summary:hover{background:rgba(59,79,216,.05)}
details.eng .ename{font-weight:600;flex:1;min-width:160px}
details.eng .ew{font-size:.72rem;color:var(--muted);white-space:nowrap}
details.eng .caret{color:var(--muted);font-size:.75rem}
details.eng .body{padding:4px 16px 14px;border-top:1px solid var(--border)}
details.eng dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;
  font-size:.8rem;margin-top:10px}
details.eng dt{color:var(--muted)}
details.eng dd{font-variant-numeric:tabular-nums;word-break:break-word}
.engine-table-row td{padding-top:6px;padding-bottom:6px}

/* ---------- cadence ---------- */
.cad{display:flex;align-items:flex-end;gap:3px;height:132px;padding:6px 4px 0;
  border-bottom:1px solid var(--border)}
.cad .col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%;min-width:3px}
.cad .col i{display:block;border-radius:3px 3px 0 0}
.cadlegend{display:flex;gap:18px;margin-top:10px;font-size:.78rem;color:var(--muted)}
.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}

/* ---------- histogram ---------- */
.hist{display:flex;align-items:flex-end;gap:14px;height:150px;padding:0 6px}
.hist .hcol{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.hist .hcol i{display:block;width:100%;max-width:86px;border-radius:6px 6px 0 0}
.hist .hv{font-size:.8rem;font-weight:700;margin-bottom:4px;font-variant-numeric:tabular-nums}
.hist .hl{font-size:.72rem;color:var(--muted);margin-top:6px;text-align:center}

/* ---------- sentences ---------- */
.sent{border-left:3px solid var(--border);padding:11px 15px;margin-bottom:10px;
  background:var(--panel2);border-radius:0 10px 10px 0}
.sent.flag{border-left-color:var(--red)}
.sent.ok{border-left-color:var(--green)}
.sent .meta{font-size:.75rem;color:var(--muted);margin-bottom:4px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.sent .rs{font-size:.78rem;color:var(--muted);margin-top:5px}
.sidx{background:var(--panel);border:1px solid var(--border);border-radius:6px;
  padding:0 7px;font-weight:700;font-size:.72rem;color:var(--muted);font-variant-numeric:tabular-nums}

/* ---------- methodology ---------- */
.method p{font-size:.86rem;color:var(--muted);margin-bottom:10px}
.method b{color:var(--text)}
.notice{border:1px solid var(--yellow);background:var(--yellow-bg);color:var(--text);
  border-radius:10px;padding:12px 16px;font-size:.86rem;margin-bottom:16px}

footer{color:var(--muted);font-size:.76rem;margin-top:30px;text-align:center;line-height:1.8}

@media print{
  body{background:#fff;font-size:12px}
  .band{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .panel{box-shadow:none;break-inside:avoid}
  details.eng{break-inside:avoid}
}
"""


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _verdict_color(ai_pct: float) -> str:
    if ai_pct < 20.0:
        return "var(--green)"
    if ai_pct < 45.0:
        return "var(--yellow)"
    if ai_pct < 70.0:
        return "var(--orange)"
    return "var(--red)"


def _verdict_badge_class(ai_pct: float) -> str:
    if ai_pct < 20.0:
        return "b-green"
    if ai_pct < 45.0:
        return "b-yellow"
    if ai_pct < 70.0:
        return "b-orange"
    return "b-red"


def _stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())


def _shield() -> str:
    """Small inline shield logo for the header band."""
    return """
<svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <path d="M12 2L4 5.5v5.1c0 5.1 3.4 9.6 8 11.4 4.6-1.8 8-6.3 8-11.4V5.5L12 2z"
      fill="rgba(255,255,255,.16)" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/>
  <path d="M8.2 12.1l2.6 2.6 5-5.4" stroke="#fff" stroke-width="1.8"
      stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>"""


def _donut(ai_pct: float, size: int = 190) -> str:
    """SVG donut gauge for a 0-100 score."""
    pct = max(0.0, min(100.0, ai_pct))
    r, cx, cy = 66.0, 80.0, 80.0
    circ = 2 * 3.14159265 * r
    dash = circ * pct / 100.0
    color = _verdict_color(pct)
    return f"""
<svg viewBox="0 0 160 160" width="{size}" height="{size}" role="img" aria-label="Consensus {pct:.0f}% AI">
  <defs><linearGradient id="dg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{color}"/><stop offset="100%" stop-color="{color}" stop-opacity=".55"/>
  </linearGradient></defs>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="var(--panel2)" stroke-width="15"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#dg)" stroke-width="15"
      stroke-dasharray="{dash:.1f} {circ - dash:.1f}" stroke-linecap="round"
      transform="rotate(-90 {cx} {cy})"/>
  <text x="{cx}" y="{cy + 2}" text-anchor="middle" fill="var(--text)"
      font-size="34" font-weight="700">{pct:.0f}%</text>
  <text x="{cx}" y="{cy + 26}" text-anchor="middle" fill="var(--muted)" font-size="10.5"
      letter-spacing="1.5">AI PROBABILITY</text>
</svg>"""


def _scale_marker(ai_pct: float) -> str:
    """Horizontal 0-100 scale with risk zones and a marker at the score."""
    pct = max(0.0, min(100.0, ai_pct))
    return f"""
<div class="scale">
  <div class="z z1" style="width:20%"></div>
  <div class="z z2" style="width:25%"></div>
  <div class="z z3" style="width:25%"></div>
  <div class="z z4" style="width:30%"></div>
  <div class="marker" style="left:calc({pct:.1f}% - 1px)"></div>
</div>
<div class="scalelabels"><span>0 · likely human</span><span>mixed</span><span>elevated</span><span>likely AI · 100</span></div>"""


def _split_bar(ai_pct: float, human_pct: float) -> str:
    return f"""
<div class="splitbar">
  <div class="ai" style="width:{max(0.0, min(100.0, ai_pct)):.1f}%"></div>
  <div class="hu" style="width:{max(0.0, min(100.0, human_pct)):.1f}%"></div>
</div>
<div class="splitlegend"><span>AI-attributed: <b class="num">{ai_pct:.1f}%</b></span><span>Human-attributed: <b class="num">{human_pct:.1f}%</b></span></div>"""


def _risk_interpretation(ai_pct: float, risk_level: str) -> str:
    if ai_pct < 20.0:
        return ("Engines broadly attribute this text to a human writer. Statistical "
                "tells are minimal and no coordinated AI signature was observed.")
    if ai_pct < 45.0:
        return ("Signals are mixed: some engines lean human, others flag AI-style "
                "structure. Treat specific flagged sentences, not the whole text, as suspect.")
    if ai_pct < 70.0:
        return ("Multiple engines lean AI. The text shows structural or lexical patterns "
                "typical of machine generation, though human editing may be present.")
    return ("Strong cross-engine agreement on machine generation. The text exhibits "
            "pervasive AI-typical phrasing, cadence, and token distributions.")


# --- engine tier grouping -----------------------------------------------------

_TIER_PREMIUM = {
    "GPTZero Official API", "Winston AI API", "Originality.ai API",
    "Pangram API", "Detecting-AI API",
}
_TIER_CLOUD = {"ZeroGPT Live Cloud API", "Sapling AI Detector"}
_TIER_LOCAL = {
    "GLTR Rank & Token Distribution", "Burstiness & Cadence Model",
    "Perplexity & Predictability Model", "PubMed AI Lexicon & Tells",
}
_TIER_NEURAL = {"Binoculars (Local Neural)"}
_TIER_BROWSER = {
    "GPTZero Detector", "CopyLeaks AI Detector", "QuillBot AI Detector",
    "Scribbr AI Detector", "Writer.com AI Detector", "ContentDetector.ai",
    "IsGen AI Detector",
}
_TIER_ORDER = [
    "Live Cloud APIs",
    "Premium Key-Based APIs",
    "Local Statistical Engines",
    "Local Neural Engines",
    "Stealth Browser Detectors",
    "Other Engines",
]


def _tier_of(engine_name: str) -> str:
    if engine_name in _TIER_CLOUD:
        return "Live Cloud APIs"
    if engine_name in _TIER_PREMIUM:
        return "Premium Key-Based APIs"
    if engine_name in _TIER_LOCAL:
        return "Local Statistical Engines"
    if engine_name in _TIER_NEURAL:
        return "Local Neural Engines"
    if engine_name in _TIER_BROWSER:
        return "Stealth Browser Detectors"
    return "Other Engines"


def _detail_rows(details: dict) -> str:
    """Render an EngineResult.details dict as a definition list."""
    rows = []
    for key, value in details.items():
        if value is None or value == "" or value == [] or value == {}:
            continue
        if isinstance(value, (dict, list)):
            try:
                shown = json.dumps(value, default=str, ensure_ascii=False)
            except (TypeError, ValueError):
                shown = str(value)
            if len(shown) > 220:
                shown = shown[:217] + "..."
        elif isinstance(value, float):
            shown = f"{value:.4g}"
        else:
            shown = str(value)
        rows.append(f"<dt>{_esc(key.replace('_', ' ').title())}</dt><dd>{_esc(shown)}</dd>")
    if not rows:
        return ""
    return "<dl>" + "".join(rows) + "</dl>"


def _engine_matrix(report: DetectionReport) -> str:
    """Engine results grouped by tier, each row expandable into diagnostics."""
    groups = {tier: [] for tier in _TIER_ORDER}
    for eng in report.engines.values():
        groups[_tier_of(eng.engine_name)].append(eng)

    blocks = []
    for tier in _TIER_ORDER:
        engines = groups[tier]
        if not engines:
            continue
        rows = []
        for eng in engines:
            weight_label = f"weight {eng.weight:g}"
            if eng.available:
                color = _verdict_color(eng.ai_percentage)
                flagged = len(eng.flagged_sentences)
                extra = f" · {flagged} flagged sentence(s)" if flagged else ""
                summary = f"""
<summary>
  <span class="ename">{_esc(eng.engine_name)}</span>
  <span class="badge {_verdict_badge_class(eng.ai_percentage)}">{eng.ai_percentage:.1f}%</span>
  <span class="bar-wrap" style="flex:1;min-width:120px;max-width:280px"><span class="bar" style="display:block;width:{eng.ai_percentage:.0f}%;background:{color};height:100%"></span></span>
  <span class="sub">{_esc(eng.verdict)} · <span class="ew">{weight_label}{extra}</span></span>
  <span class="caret">details ▾</span>
</summary>"""
                body_rows = _detail_rows(eng.details)
                if body_rows:
                    body = f'<div class="body">{body_rows}</div>'
                else:
                    body = '<div class="body sub">No additional diagnostics reported by this engine.</div>'
                rows.append(f'<details class="eng">{summary}{body}</details>')
            else:
                summary = f"""
<summary style="opacity:.6">
  <span class="ename">{_esc(eng.engine_name)}</span>
  <span class="badge b-neutral">OFFLINE</span>
  <span class="sub" style="flex:1">{_esc((eng.error or "unavailable")[:110])}</span>
</summary>"""
                rows.append(f'<details class="eng">{summary}</details>')
        blocks.append(f'<div class="tier">{_esc(tier)}</div>' + "".join(rows))
    return "".join(blocks)


def _agreement(report: DetectionReport) -> str:
    scores = [e.ai_percentage for e in report.engines.values() if e.available]
    if len(scores) < 2:
        return ("<p class='sub'>Fewer than two engines reported scores — agreement "
                "analysis is not meaningful for this run.</p>")
    spread = max(scores) - min(scores)
    if spread < 15.0:
        label, cls, note = "Strong agreement", "b-green", (
            "Engines landed within a narrow band, which raises confidence in the consensus.")
    elif spread < 35.0:
        label, cls, note = "Moderate agreement", "b-yellow", (
            "Engines disagree noticeably; the consensus is a reasonable middle ground, "
            "but inspect the per-engine results below before acting on it.")
    else:
        label, cls, note = "Low agreement", "b-red", (
            "Engines diverge sharply. Consensus scores are unstable when this happens — "
            "read individual engine verdicts and the sentence-level evidence instead.")
    return f"""
<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr))">
  <div class="metric"><div class="v">{spread:.1f}<small> pts</small></div><div class="k">Max−Min Engine Spread</div></div>
  <div class="metric"><div class="v">{len(scores)}</div><div class="k">Engines Reporting</div></div>
  <div class="metric" style="display:flex;align-items:center"><div><span class="badge {cls}">{label}</span></div></div>
</div>
<p class="sub" style="margin-top:12px">{note}</p>"""


def _cadence_chart(report: DetectionReport) -> str:
    lengths = [s.word_count for s in report.sentences]
    if not lengths:
        return "<p class='sub'>No sentences to chart.</p>"
    max_len = max(lengths) or 1
    cols = []
    for i, s in enumerate(report.sentences, 1):
        h = max(6, int((s.word_count / max_len) * 120))
        color = "var(--red)" if s.flagged else "var(--green)"
        tip = html.escape(f"S{i}: {s.word_count} words · {s.ai_probability:.0f}% AI risk")
        show_label = (i == 1 or i % 5 == 0 or i == len(report.sentences))
        label = f"<span class='hl num' style='font-size:.62rem;color:var(--muted)'>{i}</span>" if show_label else "<span class='hl'></span>"
        cols.append(
            f'<div class="col" title="{tip}"><i style="height:{h}px;background:{color}"></i>{label}</div>'
        )
    flagged_n = sum(1 for s in report.sentences if s.flagged)
    return (
        '<div class="cad">' + "".join(cols) + "</div>"
        + '<div class="cadlegend">'
        + f'<span><span class="dot" style="background:var(--red)"></span>Flagged as AI-typical ({flagged_n})</span>'
        + f'<span><span class="dot" style="background:var(--green)"></span>Human-sounding ({len(lengths) - flagged_n})</span>'
        + '<span style="margin-left:auto">Bar height = sentence length (words)</span>'
        + "</div>"
    )


def _histogram(values: list, color: str, label_fmt=str) -> str:
    """Generic 5-bucket histogram renderer for 0-100 scores."""
    if not values:
        return "<p class='sub'>No data to chart.</p>"
    edges = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]
    counts = [0] * 5
    for v in values:
        for i, (lo, hi) in enumerate(edges):
            if lo <= v < hi:
                counts[i] += 1
                break
    max_c = max(counts) or 1
    labels = ["0–19%", "20–39%", "40–59%", "60–79%", "80–100%"]
    cols = []
    for i, c in enumerate(counts):
        h = max(4, int((c / max_c) * 110)) if c else 4
        opacity = "0.9" if c else "0.25"
        bar = f'<i style="height:{h}px;background:{color};opacity:{opacity}"></i>'
        cols.append(
            f'<div class="hcol"><span class="hv num">{c if c else ""}</span>{bar}'
            f'<span class="hl">{label_fmt(labels[i])}</span></div>'
        )
    return '<div class="hist">' + "".join(cols) + "</div>"


def _sentences(report: DetectionReport) -> str:
    if not report.sentences:
        return "<p class='sub'>Sentence-level analysis is disabled or the document had no sentences.</p>"
    blocks = []
    for s in report.sentences:
        cls = "flag" if s.flagged else "ok"
        pill = ('<span class="badge b-red">FLAGGED</span>' if s.flagged
                else '<span class="badge b-green">HUMAN</span>')
        reason_html = f"<div class='rs'>↳ {_esc(', '.join(s.reasons))}</div>" if s.reasons else ""
        blocks.append(f"""
<div class="sent {cls}">
  <div class="meta"><span class="sidx">#{s.index + 1}</span> {pill}
    <span>{s.word_count} words</span><span class="num">{s.ai_probability:.0f}% AI risk</span></div>
  <div>{_esc(s.text)}</div>
  {reason_html}
</div>""")
    return "".join(blocks)


def _signal_grid(report: DetectionReport) -> str:
    return f"""
<div class="grid">
  <div class="metric"><div class="v">{report.word_count}</div><div class="k">Words</div></div>
  <div class="metric"><div class="v">{report.sentence_count}</div><div class="k">Sentences</div></div>
  <div class="metric"><div class="v">{report.mean_sentence_length:.1f}<small> ±{report.sentence_length_std_dev:.1f}</small></div><div class="k">Mean Sent. Length</div></div>
  <div class="metric"><div class="v">{report.burstiness_ratio:.2f}</div><div class="k">Burstiness σ/μ</div></div>
  <div class="metric"><div class="v">{len(report.banned_words_found)}</div><div class="k">AI Buzzwords</div></div>
  <div class="metric"><div class="v">{report.em_dash_count}</div><div class="k">Em Dashes</div></div>
  <div class="metric"><div class="v">{report.semicolon_count}</div><div class="k">Semicolons</div></div>
  <div class="metric"><div class="v">{report.tripartite_list_count}</div><div class="k">Tripartite Lists</div></div>
</div>"""


def _tells(report: DetectionReport) -> str:
    if report.banned_words_found:
        chips = "".join(f'<span class="tell">{_esc(w)}</span>' for w in report.banned_words_found)
        note = ("<p class='sub' style='margin-top:12px'>These phrases are heavily over-represented "
                "in machine-generated prose (per the PubMed AI-lexicon corpus). Their presence "
                "alone is not proof of AI authorship, but clusters of them are a strong tell.</p>")
    else:
        chips = '<span class="tell alt">No AI-lexicon buzzwords detected</span>'
        note = ""
    return f'<div class="chiprow">{chips}</div>{note}'


def _methodology(report: DetectionReport, engine_count: int) -> str:
    return f"""
<p><b>How the consensus is computed.</b> Each available engine returns an AI
probability in 0–100. The consensus is the weighted mean of those scores, where
each engine carries a trust weight reflecting its measured reliability
(<b>{engine_count} engines contributed to this report</b> in
<b>{_esc(report.engine_mode)}</b> mode). Engines that error or are unavailable
drop out of the denominator entirely — they never silently count as "human".</p>
<p><b>How to read the risk level.</b> Risk bands map to the consensus score:
0–19 low, 20–44 mixed, 45–69 elevated, 70–100 high. The exit code of the CLI
mirrors a configurable threshold (default 30%) so CI pipelines can fail on
suspicious text.</p>
<p><b>Limitations.</b> AI-text detection is probabilistic. Short texts, formulaic
writing, and light paraphrasing can all skew results in either direction; public
endpoints may rate-limit or change without notice. Use this report as
investigative signal — never as a sole basis for accusations.</p>"""


def _header_band(title: str, tagline: str, chips: list) -> str:
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in chips)
    return f"""
<div class="band"><div class="wrap">
  <h1>{_shield()}{_esc(title)}</h1>
  <div class="tag">{_esc(tagline)}</div>
  <div class="chips">{chip_html}</div>
</div></div>"""


def _single_page(report: DetectionReport) -> str:
    ai = report.consensus_ai_probability
    badge = _verdict_badge_class(ai)
    available_engines = [e for e in report.engines.values() if e.available]

    chips = [
        f"Generated <b>{_stamp()}</b>",
        f"Source: <b>{_esc(report.source)}</b>",
        f"Mode: <b>{_esc(report.engine_mode)}</b>",
        f"Duration: <b>{report.analysis_ms:.0f} ms</b>",
        f"Engines: <b>{len(available_engines)}/{len(report.engines)}</b>",
        f"ai-detector-cli <b>v{__version__}</b>",
    ]
    degraded = ""
    if report.degraded:
        note_text = report.degradation_note or "Live engines degraded to local-only mode."
        degraded = f"<div class='notice'>⚠️ {_esc(note_text)}</div>"

    return "".join([
        _header_band("AI Text Detection Report",
                     "Multi-engine consensus audit · ai-detector-cli", chips),
        "<div class='wrap'>",
        degraded,
        f"""<h2>Executive Summary</h2>
<div class="panel exec">
  {_donut(ai)}
  <div class="right">
    <span class="badge {badge}" style="font-size:.92rem">{_esc(report.consensus_verdict)}</span>
    <div class="verdict-line">Risk level: {_esc(report.risk_level)}</div>
    <p class="sub">{_risk_interpretation(ai, report.risk_level)}</p>
    {_split_bar(ai, report.consensus_human_probability)}
  </div>
</div>""",
        f"""<h2>Consensus Position on the Risk Scale</h2>
<div class="panel">{_scale_marker(ai)}</div>""",
        f"""<h2>Engine Breakdown</h2>
<div class="panel">{_engine_matrix(report)}</div>""",
        f"""<h2>Inter-Engine Agreement</h2>
<div class="panel">{_agreement(report)}</div>""",
        """<h2>Stylometric Signals</h2>
<div class="panel">""" + _signal_grid(report) + "</div>",
        f"""<h2>AI Vocabulary Tells</h2>
<div class="panel">{_tells(report)}</div>""",
        f"""<h2>Sentence Cadence &amp; Burstiness</h2>
<div class="panel">{_cadence_chart(report)}</div>""",
        f"""<h2>Sentence Risk Distribution</h2>
<div class="panel">{_histogram([s.ai_probability for s in report.sentences],
                               "var(--accent)")}</div>""",
        f"""<h2>Sentence-Level Classification</h2>
<div class="panel">{_sentences(report)}</div>""",
        f"""<h2>Methodology &amp; Limitations</h2>
<div class="panel method">{_methodology(report, len(available_engines))}</div>""",
        "<footer>Generated by <a href='https://github.com/dustindog101/ai-detector-cli'>"
        "ai-detector-cli</a> v" + __version__ + " · heuristic consensus, not a verdict "
        "of authorship · " + _stamp() + "</footer>",
        "</div>",
    ])


def _batch_page(batch: BatchReport) -> str:
    ok_entries = [e for e in batch.entries if e.report]
    scores = [e.report.consensus_ai_probability for e in ok_entries]
    avg = sum(scores) / len(scores) if scores else 0.0
    flagged = sum(1 for e in ok_entries if e.report.consensus_ai_probability > batch.threshold)

    chips = [
        f"Generated <b>{_stamp()}</b>",
        f"Mode: <b>{_esc(batch.engines_mode)}</b>",
        f"Threshold: <b>{batch.threshold:.0f}%</b>",
        f"Files: <b>{len(batch.entries)}</b>",
        f"Duration: <b>{batch.elapsed_ms:.0f} ms</b>",
        f"ai-detector-cli <b>v{__version__}</b>",
    ]

    rows = []
    ranked = sorted(
        batch.entries,
        key=lambda e: e.report.consensus_ai_probability if e.report else -1.0,
        reverse=True,
    )
    for rank, entry in enumerate(ranked, 1):
        rep = entry.report
        if entry.error:
            rows.append(f"""
<tr><td class="num">{rank}</td><td>{_esc(entry.path)}</td>
<td colspan="4" style="color:var(--red)">{_esc(entry.error)}</td></tr>""")
            continue
        over = rep.consensus_ai_probability > batch.threshold
        status = ('<span class="badge b-red">ABOVE THRESHOLD</span>' if over
                  else '<span class="badge b-green">OK</span>')
        color = _verdict_color(rep.consensus_ai_probability)
        fname = entry.path.replace("\\", "/").rsplit("/", 1)[-1]
        rows.append(f"""
<tr>
  <td class="num">{rank}</td>
  <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{_esc(entry.path)}">{_esc(fname)}</td>
  <td><span class="badge {_verdict_badge_class(rep.consensus_ai_probability)}">{rep.consensus_ai_probability:.1f}%</span></td>
  <td style="width:26%"><div class="bar-wrap"><div class="bar" style="width:{rep.consensus_ai_probability:.0f}%;background:{color}"></div></div></td>
  <td class="num">{rep.word_count}</td>
  <td class="num">{rep.sentence_count}</td>
  <td>{status}</td>
</tr>""")

    return "".join([
        _header_band("Batch AI Detection Report",
                     "Directory scan · ranked per-file consensus", chips),
        "<div class='wrap'>",
        f"""<h2>Summary</h2>
<div class="panel exec">
  {_donut(avg, size=170)}
  <div class="right">
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
      <div class="metric"><div class="v">{len(batch.entries)}</div><div class="k">Files Scanned</div></div>
      <div class="metric"><div class="v">{flagged}</div><div class="k">Above {batch.threshold:.0f}% Threshold</div></div>
      <div class="metric"><div class="v">{avg:.1f}%</div><div class="k">Mean AI Score</div></div>
      <div class="metric"><div class="v">{max(scores):.1f}%</div><div class="k">Highest Score</div></div>
    </div>
  </div>
</div>""",
        f"""<h2>Score Distribution</h2>
<div class="panel">{_histogram(scores, "var(--accent)")}</div>""",
        f"""<h2>Per-File Results (ranked by AI score)</h2>
<div class="panel" style="overflow-x:auto">
<table>
<thead><tr><th>#</th><th>File</th><th>AI %</th><th>Score</th><th>Words</th><th>Sent.</th><th>Status</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</div>""",
        f"""<h2>Methodology &amp; Limitations</h2>
<div class="panel method">
<p><b>Ranking.</b> Files are sorted by consensus AI probability (weighted mean of
available engines in <b>{_esc(batch.engines_mode)}</b> mode). The status column
flags files above the configured threshold of <b>{batch.threshold:.0f}%</b> — the
same threshold the CLI uses for its exit code.</p>
<p><b>Limitations.</b> Batch consensus scores are screening signals, not proof of
authorship. Always follow up on flagged files with the in-depth single-file
report (<code>ai-detect --export report.html &lt;file&gt;</code>) before drawing
conclusions.</p>
</div>""",
        "<footer>Generated by <a href='https://github.com/dustindog101/ai-detector-cli'>"
        "ai-detector-cli</a> v" + __version__ + " · " + _stamp() + "</footer>",
        "</div>",
    ])


def export_html(report: DetectionReport) -> str:
    """Render one DetectionReport as a standalone HTML document."""
    return _wrap_page(_single_page(report))


def export_batch_html(batch: BatchReport) -> str:
    """Render a BatchReport as a standalone HTML document."""
    return _wrap_page(_batch_page(batch))


def _wrap_page(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Detection Report</title>
<style>{_CSS}</style>
</head>
<body>{body}
</body>
</html>"""
