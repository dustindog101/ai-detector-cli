"""
Self-contained academic HTML report generator for AI Detector CLI.

Produces a single portable .html file (zero external assets, inline CSS/SVG,
no JavaScript) styled as a formal academic provenance audit — serif
typography, ruled masthead, numbered sections, and a similarity-index score
band reminiscent of institutional originality reports.

Renders:
- Ruled cover masthead with report ID and formal metadata table
- AI Similarity Index band with verdict and risk interpretation
- Consensus position on a zoned 0-100 scale
- Engine matrix grouped by tier with collapsible diagnostics
- Inter-engine agreement analysis
- Stylometric signal grid + AI vocabulary tells
- Sentence cadence chart + sentence risk distribution histogram
- Sentence-level classification with reasons
- Methodology and limitations (academic register)
- Optional batch summary (--batch --export report.html)

Auto light/dark via prefers-color-scheme; clean printing.
Compatible with Python 3.8+. No third-party dependencies.
"""

import hashlib
import html
import json
import time

from . import __version__
from .models import DetectionReport, BatchReport

_CSS = """
:root{
  --paper:#fbfaf5;--panel:#ffffff;--panel2:#f5f3ec;--ink:#21293a;--muted:#5f6b80;
  --navy:#182c52;--burgundy:#77202c;--gold:#a98a45;--rule:#d9d2bf;--rule2:#efece1;
  --green:#2c6e4d;--green-bg:rgba(44,110,77,.09);
  --yellow:#8f6f14;--yellow-bg:rgba(175,140,40,.11);
  --orange:#a4551c;--orange-bg:rgba(164,85,28,.10);
  --red:#8d2231;--red-bg:rgba(141,34,49,.08);
  --zone1:#e9f1ea;--zone2:#f7f1dd;--zone3:#f7ead9;--zone4:#f6e4e2}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#12161f;--panel:#1a2130;--panel2:#202838;--ink:#e6e9f0;--muted:#98a0b3;
    --navy:#a8bbe6;--burgundy:#e08795;--gold:#c9ab6b;--rule:#39415a;--rule2:#262e42;
    --green:#63b18a;--green-bg:rgba(99,177,138,.13);
    --yellow:#d4b258;--yellow-bg:rgba(212,178,88,.12);
    --orange:#d98a54;--orange-bg:rgba(217,138,84,.12);
    --red:#d4707e;--red-bg:rgba(212,112,126,.12);
    --zone1:rgba(99,177,138,.10);--zone2:rgba(212,178,88,.08);
    --zone3:rgba(217,138,84,.08);--zone4:rgba(212,112,126,.10)}}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--paper);color:var(--ink);
  font-family:Georgia,'Times New Roman',Times,serif;line-height:1.65;font-size:15.5px}
.wrap{max-width:1000px;margin:0 auto;padding:0 24px 46px}
a{color:var(--burgundy);text-decoration:none}
a:hover{text-decoration:underline}
.num{font-variant-numeric:tabular-nums}
.sans{font-family:'Segoe UI',Helvetica,Arial,sans-serif}

/* ---------- ruled masthead ---------- */
.masthead{border-top:3px double var(--navy);border-bottom:1px solid var(--navy);
  margin:26px 0 0;padding:18px 4px 14px;text-align:center}
.masthead .over{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.68rem;
  letter-spacing:.34em;text-transform:uppercase;color:var(--burgundy);font-weight:700}
.masthead h1{font-size:1.9rem;font-weight:700;color:var(--navy);margin-top:6px;letter-spacing:.01em}
.masthead .under{font-style:italic;color:var(--muted);margin-top:4px;font-size:.95rem}
.metaRule{display:flex;justify-content:center;gap:0;border:1px solid var(--rule);
  margin:18px auto 26px;background:var(--panel);max-width:860px}
.metaRule div{flex:1;padding:9px 12px;text-align:center;border-right:1px solid var(--rule)}
.metaRule div:last-child{border-right:none}
.metaRule .k{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.62rem;
  text-transform:uppercase;letter-spacing:.14em;color:var(--muted)}
.metaRule .v{font-size:.86rem;margin-top:2px;font-variant-numeric:tabular-nums;word-break:break-word}

/* ---------- generic ---------- */
h2{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.82rem;margin:34px 0 13px;
  color:var(--navy);text-transform:uppercase;letter-spacing:.13em;font-weight:700;
  border-bottom:1px solid var(--rule);padding-bottom:7px}
h2 .secno{color:var(--burgundy);margin-right:10px}
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:4px;
  padding:22px 26px;margin-bottom:16px}
.sub{color:var(--muted);font-size:.86rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(146px,1fr));gap:10px}
.metric{background:var(--panel2);border:1px solid var(--rule2);border-radius:4px;padding:12px 14px}
.metric .v{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:1.28rem;font-weight:700;
  font-variant-numeric:tabular-nums;color:var(--navy)}
.metric .v small{font-size:.8rem;font-weight:600;color:var(--muted)}
.metric .k{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.64rem;color:var(--muted);
  text-transform:uppercase;letter-spacing:.08em;margin-top:3px}
table{width:100%;border-collapse:collapse;font-size:.87rem}
th{font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:var(--muted);text-align:left;
  font-weight:700;padding:8px 10px;border-bottom:1px solid var(--navy);
  font-size:.68rem;text-transform:uppercase;letter-spacing:.09em}
td{padding:9px 10px;border-bottom:1px solid var(--rule2);vertical-align:middle}
tr:last-child td{border-bottom:none}

/* ---------- badges & bars ---------- */
.badge{display:inline-block;padding:2px 12px;border-radius:2px;font-size:.74rem;
  font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-weight:700;letter-spacing:.05em;
  white-space:nowrap;text-transform:uppercase}
.b-green{background:var(--green-bg);color:var(--green);border:1px solid var(--green)}
.b-yellow{background:var(--yellow-bg);color:var(--yellow);border:1px solid var(--yellow)}
.b-orange{background:var(--orange-bg);color:var(--orange);border:1px solid var(--orange)}
.b-red{background:var(--red-bg);color:var(--red);border:1px solid var(--red)}
.b-neutral{background:var(--panel2);color:var(--muted);border:1px solid var(--rule)}
.bar-wrap{background:var(--panel2);border-radius:2px;height:12px;width:100%;
  min-width:100px;overflow:hidden;border:1px solid var(--rule2)}
.bar{height:100%;border-radius:0}

/* ---------- similarity index ---------- */
.simband{display:flex;gap:30px;align-items:center;flex-wrap:wrap}
.simband .right{flex:1;min-width:290px}
.scorebig{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:2.5rem;font-weight:800;
  color:var(--burgundy);line-height:1;font-variant-numeric:tabular-nums}
.scorebig small{font-size:1rem;color:var(--muted);font-weight:600}
.verdict-line{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-weight:700;
  font-size:1.02rem;margin:10px 0 6px;color:var(--navy)}
.splitbar{display:flex;height:16px;border-radius:2px;overflow:hidden;margin:14px 0 6px;
  border:1px solid var(--rule)}
.splitbar .ai{background:var(--red);opacity:.82}
.splitbar .hu{background:var(--green);opacity:.82}
.splitlegend{display:flex;justify-content:space-between;
  font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.76rem;color:var(--muted)}

/* ---------- scale ---------- */
.scale{position:relative;height:30px;display:flex;border:1px solid var(--rule)}
.scale .z{height:100%}
.scale .z1{background:var(--zone1)}.scale .z2{background:var(--zone2)}
.scale .z3{background:var(--zone3)}.scale .z4{background:var(--zone4)}
.marker{position:absolute;top:-2px;bottom:-2px;width:3px;background:var(--navy)}
.marker:after{content:'';position:absolute;top:-3px;left:-4px;
  border:6px solid transparent;border-top-color:var(--navy)}
.scalelabels{display:flex;font-family:'Segoe UI',Helvetica,Arial,sans-serif;
  font-size:.68rem;color:var(--muted);margin-top:6px}
.scalelabels span{flex:1}
.scalelabels span:last-child{text-align:right}

/* ---------- tells ---------- */
.chiprow{display:flex;flex-wrap:wrap;gap:8px}
.tell{background:var(--red-bg);color:var(--red);border:1px solid var(--red);
  border-radius:2px;padding:2px 12px;font-size:.82rem;font-style:italic}
.tell.alt{background:var(--panel2);color:var(--muted);border-color:var(--rule);font-style:normal}

/* ---------- engine matrix ---------- */
.tier{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.66rem;color:var(--gold);
  text-transform:uppercase;letter-spacing:.16em;font-weight:700;margin:16px 0 7px}
.tier:first-child{margin-top:0}
details.eng{border:1px solid var(--rule2);background:var(--panel2);margin-bottom:7px}
details.eng summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;
  padding:9px 14px;flex-wrap:wrap}
details.eng summary::-webkit-details-marker{display:none}
details.eng summary:hover{background:rgba(119,32,44,.04)}
details.eng .ename{font-weight:700;flex:1;min-width:160px}
details.eng .ew{font-size:.72rem;color:var(--muted);white-space:nowrap}
details.eng .caret{color:var(--muted);font-size:.72rem;
  font-family:'Segoe UI',Helvetica,Arial,sans-serif}
details.eng .body{padding:4px 16px 13px;border-top:1px solid var(--rule2)}
details.eng dl{display:grid;grid-template-columns:max-content 1fr;gap:3px 16px;
  font-size:.8rem;margin-top:10px}
details.eng dt{color:var(--muted);font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.7rem}
details.eng dd{font-variant-numeric:tabular-nums;word-break:break-word}

/* ---------- cadence ---------- */
.cad{display:flex;align-items:flex-end;gap:3px;height:128px;padding:6px 4px 0;
  border-bottom:1px solid var(--rule)}
.cad .col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%;min-width:3px}
.cad .col i{display:block;border-radius:1px 1px 0 0}
.cadlegend{display:flex;gap:18px;margin-top:10px;
  font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.74rem;color:var(--muted)}
.dot{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}

/* ---------- histogram ---------- */
.hist{display:flex;align-items:flex-end;gap:14px;height:146px;padding:0 6px}
.hist .hcol{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.hist .hcol i{display:block;width:100%;max-width:86px;border-radius:2px 2px 0 0}
.hist .hv{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.8rem;font-weight:700;
  margin-bottom:4px;font-variant-numeric:tabular-nums;color:var(--navy)}
.hist .hl{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.68rem;color:var(--muted);margin-top:6px;text-align:center}

/* ---------- sentences ---------- */
.sent{border-left:3px solid var(--rule);padding:10px 15px;margin-bottom:9px;
  background:var(--panel2)}
.sent.flag{border-left-color:var(--red)}
.sent.ok{border-left-color:var(--green)}
.sent .meta{font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.72rem;
  color:var(--muted);margin-bottom:4px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.sent .rs{font-size:.8rem;color:var(--muted);margin-top:5px;font-style:italic}
.sidx{font-family:'Segoe UI',Helvetica,Arial,sans-serif;background:var(--panel);
  border:1px solid var(--rule);padding:0 7px;font-weight:700;font-size:.7rem;
  color:var(--muted);font-variant-numeric:tabular-nums}

/* ---------- methodology ---------- */
.method p{font-size:.9rem;color:var(--ink);margin-bottom:12px;text-align:justify}
.method b{color:var(--navy)}
.notice{border:1px solid var(--yellow);background:var(--yellow-bg);color:var(--ink);
  border-radius:3px;padding:11px 16px;font-size:.88rem;margin-bottom:16px}
.signature{margin-top:26px;border-top:1px solid var(--rule);padding-top:12px;
  display:flex;justify-content:space-between;flex-wrap:gap;flex-wrap:wrap;
  font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:.72rem;color:var(--muted)}

@media print{
  body{background:#fff;font-size:11.5pt}
  .panel{box-shadow:none;break-inside:avoid}
  details.eng{break-inside:avoid}
  @page{margin:2cm}
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


def _report_id(source: str, extra: str = "") -> str:
    seed = f"{source}|{extra}|{_stamp()}|{__version__}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10].upper()
    return f"AIA-{digest}"


def _shield_rule() -> str:
    return """
<svg width="40" height="26" viewBox="0 0 40 26" aria-hidden="true" style="margin:0 auto;display:block">
  <line x1="0" y1="13" x2="13" y2="13" stroke="var(--gold)" stroke-width="1"/>
  <path d="M20 3l6 2.6v2.9c0 4.1-2.6 7.7-6 9.2-3.4-1.5-6-5.1-6-9.2V5.6L20 3z"
      fill="none" stroke="var(--navy)" stroke-width="1.3" stroke-linejoin="round"/>
  <line x1="27" y1="13" x2="40" y2="13" stroke="var(--gold)" stroke-width="1"/>
</svg>"""


def _donut(ai_pct: float, size: int = 186) -> str:
    """SVG donut gauge for a 0-100 score."""
    pct = max(0.0, min(100.0, ai_pct))
    r, cx, cy = 64.0, 80.0, 80.0
    circ = 2 * 3.14159265 * r
    dash = circ * pct / 100.0
    color = _verdict_color(pct)
    return f"""
<svg viewBox="0 0 160 160" width="{size}" height="{size}" role="img" aria-label="Consensus {pct:.0f}% AI">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="var(--panel2)" stroke-width="13"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="13"
      stroke-dasharray="{dash:.1f} {circ - dash:.1f}" stroke-linecap="butt"
      transform="rotate(-90 {cx} {cy})"/>
  <text x="{cx}" y="{cy + 3}" text-anchor="middle" fill="var(--navy)"
      font-size="33" font-weight="700"
      font-family="Georgia,serif">{pct:.0f}%</text>
  <text x="{cx}" y="{cy + 26}" text-anchor="middle" fill="var(--muted)" font-size="9"
      letter-spacing="2" font-family="Helvetica,Arial,sans-serif">AI PROBABILITY</text>
</svg>"""


def _scale_marker(ai_pct: float) -> str:
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


def _risk_interpretation(ai_pct: float) -> str:
    if ai_pct < 20.0:
        return ("The engines surveyed attribute this document predominantly to human "
                "authorship. Statistical markers commonly associated with machine "
                "generation are minimal, and no coordinated AI signature was observed "
                "across the panel.")
    if ai_pct < 45.0:
        return ("The evidence is mixed: several engines lean human while others flag "
                "AI-style structure. Particular sentences, rather than the document as "
                "a whole, warrant scrutiny; consult the sentence-level findings below.")
    if ai_pct < 70.0:
        return ("A majority of engines lean machine-generated. The document exhibits "
                "structural and lexical patterns characteristic of AI generation, though "
                "human editing may be present in places.")
    return ("The panel exhibits strong agreement that the document is machine-generated. "
            "Pervasive AI-typical phrasing, cadence, and token distributions were observed "
            "throughout the text.")


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
    "IsGen AI Detector", "Grammarly AI Detector",
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
  <span class="caret">append ▾</span>
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
        label, cls, note = "Strong concordance", "b-green", (
            "The engines landed within a narrow band, which strengthens confidence "
            "in the consensus estimate.")
    elif spread < 35.0:
        label, cls, note = "Moderate concordance", "b-yellow", (
            "The engines disagree noticeably. The consensus remains a reasonable "
            "middle estimate, but the per-engine findings should be inspected "
            "before any conclusion is drawn.")
    else:
        label, cls, note = "Low concordance", "b-red", (
            "The engines diverge sharply. Consensus estimates are unstable under "
            "such disagreement; the individual verdicts and sentence-level "
            "evidence deserve greater weight than the headline figure.")
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
        h = max(6, int((s.word_count / max_len) * 116))
        color = "var(--red)" if s.flagged else "var(--green)"
        tip = html.escape(f"S{i}: {s.word_count} words · {s.ai_probability:.0f}% AI risk")
        show_label = (i == 1 or i % 5 == 0 or i == len(report.sentences))
        label = (f"<span class='hl num' style='font-size:.6rem;color:var(--muted)'>{i}</span>"
                 if show_label else "<span class='hl'></span>")
        cols.append(f'<div class="col" title="{tip}"><i style="height:{h}px;background:{color}"></i>{label}</div>')
    flagged_n = sum(1 for s in report.sentences if s.flagged)
    return (
        '<div class="cad">' + "".join(cols) + "</div>"
        + '<div class="cadlegend">'
        + f'<span><span class="dot" style="background:var(--red)"></span>Flagged as AI-typical ({flagged_n})</span>'
        + f'<span><span class="dot" style="background:var(--green)"></span>Human-sounding ({len(lengths) - flagged_n})</span>'
        + '<span style="margin-left:auto">Bar height = sentence length (words)</span>'
        + "</div>"
    )


def _histogram(values: list, color: str) -> str:
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
        h = max(4, int((c / max_c) * 106)) if c else 4
        opacity = "0.9" if c else "0.25"
        bar = f'<i style="height:{h}px;background:{color};opacity:{opacity}"></i>'
        cols.append(
            f'<div class="hcol"><span class="hv num">{c if c else ""}</span>{bar}'
            f'<span class="hl">{labels[i]}</span></div>'
        )
    return '<div class="hist">' + "".join(cols) + "</div>"


def _sentences(report: DetectionReport) -> str:
    if not report.sentences:
        return ("<p class='sub'>Sentence-level analysis is disabled or the document "
                "contained no sentences.</p>")
    blocks = []
    for s in report.sentences:
        cls = "flag" if s.flagged else "ok"
        pill = ('<span class="badge b-red">Flagged</span>' if s.flagged
                else '<span class="badge b-green">Human</span>')
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
        note = ("<p class='sub' style='margin-top:12px'>These phrases are heavily "
                "over-represented in machine-generated prose relative to the human "
                "reference corpus. Their presence alone does not establish machine "
                "authorship; clustered occurrences, however, are a substantive indicator.</p>")
    else:
        chips = '<span class="tell alt">No AI-lexicon markers detected</span>'
        note = ""
    return f'<div class="chiprow">{chips}</div>{note}'


def _methodology(report: DetectionReport, engine_count: int) -> str:
    return f"""
<p><b>1. Computation of the consensus estimate.</b> Each available engine returns
an AI probability on a 0–100 scale. The consensus reported here is the weighted
mean of those estimates, where each engine carries a trust weight reflecting its
demonstrated reliability (<b>{engine_count} engines contributed</b> to this
report in <b>{_esc(report.engine_mode)}</b> mode). Engines that error or are
unavailable are excluded from the denominator entirely; they are never counted
as evidence of human authorship.</p>
<p><b>2. Interpretation of risk bands.</b> Risk bands map onto the consensus
estimate as follows: 0–19 low, 20–44 mixed, 45–69 elevated, 70–100 high. The
command-line exit code mirrors a configurable threshold (30% by default) so
that automated pipelines may act upon the same standard.</p>
<p><b>3. Limitations.</b> AI-text detection is probabilistic rather than
conclusive. Short passages, formulaic writing, and lightly paraphrased machine
text can each skew results in either direction; public detection endpoints may
rate-limit or change without notice. This report constitutes investigative
signal and should never serve as the sole basis for allegations of academic or
professional misconduct.</p>"""


def _masthead(title: str, subtitle: str, report_id: str) -> str:
    return f"""
<div class="masthead">
  {_shield_rule()}
  <div class="over">AI Provenance Audit · ai-detector-cli v{__version__}</div>
  <h1>{_esc(title)}</h1>
  <div class="under">{_esc(subtitle)}</div>
</div>
<div class="metaRule sans">
  <div><div class="k">Report ID</div><div class="v">{_esc(report_id)}</div></div>
  <div><div class="k">Issued</div><div class="v">{_stamp()}</div></div>
</div>"""


def _meta_rule(report: DetectionReport, engine_count: int) -> str:
    cells = [
        ("Source", report.source),
        ("Mode", report.engine_mode),
        ("Words", f"{report.word_count:,}"),
        ("Sentences", f"{report.sentence_count:,}"),
        ("Engines", f"{engine_count}/{len(report.engines)}"),
        ("Duration", f"{report.analysis_ms:.0f} ms"),
    ]
    cells_html = "".join(
        f'<div><div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div></div>'
        for k, v in cells
    )
    return f'<div class="metaRule sans">{cells_html}</div>'


def _single_page(report: DetectionReport) -> str:
    ai = report.consensus_ai_probability
    badge = _verdict_badge_class(ai)
    available_engines = [e for e in report.engines.values() if e.available]
    rid = _report_id(report.source, f"{ai:.1f}")
    degraded = ""
    if report.degraded:
        note_text = report.degradation_note or "Live engines degraded to local-only mode."
        degraded = f"<div class='notice'>⚠ {_esc(note_text)}</div>"

    return "".join([
        _masthead("AI Text Detection Report",
                  "A multi-engine consensus audit of textual provenance", rid),
        _meta_rule(report, len(available_engines)),
        "<div class='wrap'>",
        degraded,
        """<h2><span class="secno">§1</span>Executive Summary</h2>
<div class="panel simband">
  """ + _donut(ai) + f"""
  <div class="right">
    <div class="scorebig">{ai:.1f}<small> % AI</small></div>
    <div style="margin-top:8px"><span class="badge {badge}" style="font-size:.85rem">{_esc(report.consensus_verdict)}</span></div>
    <div class="verdict-line">Assessed risk level: {_esc(report.risk_level)}</div>
    <p class="sub">{_risk_interpretation(ai)}</p>
    {_split_bar(ai, report.consensus_human_probability)}
  </div>
</div>""",
        f"""<h2><span class="secno">§2</span>Consensus Position on the Risk Scale</h2>
<div class="panel">{_scale_marker(ai)}</div>""",
        f"""<h2><span class="secno">§3</span>Detection Results by Engine</h2>
<div class="panel">{_engine_matrix(report)}</div>""",
        f"""<h2><span class="secno">§4</span>Inter-Engine Agreement</h2>
<div class="panel">{_agreement(report)}</div>""",
        """<h2><span class="secno">§5</span>Stylometric Signals</h2>
<div class="panel">""" + _signal_grid(report) + "</div>",
        f"""<h2><span class="secno">§6</span>AI Vocabulary Markers</h2>
<div class="panel">{_tells(report)}</div>""",
        f"""<h2><span class="secno">§7</span>Sentence Cadence &amp; Burstiness</h2>
<div class="panel">{_cadence_chart(report)}</div>""",
        f"""<h2><span class="secno">§8</span>Sentence Risk Distribution</h2>
<div class="panel">{_histogram([s.ai_probability for s in report.sentences], "var(--burgundy)")}</div>""",
        f"""<h2><span class="secno">§9</span>Sentence-Level Findings</h2>
<div class="panel">{_sentences(report)}</div>""",
        f"""<h2><span class="secno">§10</span>Methodology &amp; Limitations</h2>
<div class="panel method">{_methodology(report, len(available_engines))}</div>""",
        f"""<div class="signature">
  <span>Report {_esc(rid)} · {_stamp()}</span>
  <span>Generated by <a href='https://github.com/dustindog101/ai-detector-cli'>ai-detector-cli</a> v{__version__}</span>
  <span>Heuristic consensus — not a verdict of authorship</span>
</div>""",
        "</div>",
    ])


def _batch_page(batch: BatchReport) -> str:
    ok_entries = [e for e in batch.entries if e.report]
    scores = [e.report.consensus_ai_probability for e in ok_entries]
    avg = sum(scores) / len(scores) if scores else 0.0
    flagged = sum(1 for e in ok_entries
                  if e.report.consensus_ai_probability > batch.threshold)
    rid = _report_id(f"batch:{len(batch.entries)}", f"{avg:.1f}")

    cells = [
        ("Files", f"{len(batch.entries)}"),
        ("Mode", batch.engines_mode),
        ("Threshold", f"{batch.threshold:.0f}%"),
        ("Flagged", f"{flagged}"),
        ("Duration", f"{batch.elapsed_ms:.0f} ms"),
    ]
    cells_html = "".join(
        f'<div><div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div></div>'
        for k, v in cells
    )

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
<td colspan="5" style="color:var(--red)">{_esc(entry.error)}</td></tr>""")
            continue
        over = rep.consensus_ai_probability > batch.threshold
        status = ('<span class="badge b-red">Above threshold</span>' if over
                  else '<span class="badge b-green">Within threshold</span>')
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
        _masthead("Batch AI Detection Report",
                  "A ranked provenance survey of a document corpus", rid),
        f'<div class="metaRule sans">{cells_html}</div>',
        "<div class='wrap'>",
        f"""<h2><span class="secno">§1</span>Summary of Findings</h2>
<div class="panel simband">
  {_donut(avg, size=168)}
  <div class="right">
    <div class="scorebig">{avg:.1f}<small> % mean AI</small></div>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-top:14px">
      <div class="metric"><div class="v">{len(batch.entries)}</div><div class="k">Files Scanned</div></div>
      <div class="metric"><div class="v">{flagged}</div><div class="k">Above {batch.threshold:.0f}% Threshold</div></div>
      <div class="metric"><div class="v">{max(scores):.1f}%</div><div class="k">Highest Score</div></div>
      <div class="metric"><div class="v">{batch.elapsed_ms:.0f} ms</div><div class="k">Total Time</div></div>
    </div>
  </div>
</div>""",
        f"""<h2><span class="secno">§2</span>Score Distribution</h2>
<div class="panel">{_histogram(scores, "var(--burgundy)")}</div>""",
        f"""<h2><span class="secno">§3</span>Per-File Results (ranked by AI score)</h2>
<div class="panel" style="overflow-x:auto">
<table>
<thead><tr><th>#</th><th>File</th><th>AI %</th><th>Score</th><th>Words</th><th>Sent.</th><th>Disposition</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</div>""",
        f"""<h2><span class="secno">§4</span>Methodology &amp; Limitations</h2>
<div class="panel method">
<p><b>Ranking.</b> Documents are ordered by consensus AI probability — the weighted
mean of available engines in <b>{_esc(batch.engines_mode)}</b> mode. The
disposition column marks files above the configured threshold of
<b>{batch.threshold:.0f}%</b>, the same standard the command-line exit code
applies.</p>
<p><b>Limitations.</b> Batch consensus scores are screening signals, not proof of
authorship. Flagged documents should be followed up with the in-depth
single-file audit (<code>ai-detect --export report.html &lt;file&gt;</code>)
before conclusions are drawn.</p>
</div>""",
        f"""<div class="signature">
  <span>Report {_esc(rid)} · {_stamp()}</span>
  <span>Generated by <a href='https://github.com/dustindog101/ai-detector-cli'>ai-detector-cli</a> v{__version__}</span>
</div>""",
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
