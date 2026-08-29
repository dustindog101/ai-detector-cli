"""
Self-contained HTML report generator for AI Detector CLI.

Produces a single portable .html file (zero external assets, inline CSS/SVG)
that renders:
- Consensus donut gauge with verdict badge
- Per-engine horizontal bar chart
- Sentence cadence chart + flagged sentence table
- Stylometric metrics grid
- Optional batch summary table (--batch --export report.html)

Compatible with Python 3.8+. No third-party dependencies.
"""

import html
import json
from typing import List, Optional

from .models import DetectionReport, BatchReport

_CSS = """
:root{--bg:#0f1420;--panel:#171e2e;--panel2:#1c2438;--text:#e8ecf4;--muted:#8b93a7;
--accent:#5b8cff;--green:#2ecc71;--red:#ff5b6e;--orange:#ffa94d;--yellow:#ffd166;
--border:#2a3450}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif;padding:32px;line-height:1.55}
.wrap{max-width:980px;margin:0 auto}
h1{font-size:1.5rem;display:flex;align-items:center;gap:10px;margin-bottom:4px}
h2{font-size:1.05rem;margin:26px 0 12px;color:var(--accent);text-transform:uppercase;letter-spacing:.06em}
.sub{color:var(--muted);font-size:.85rem;margin-bottom:22px}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:20px 22px;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.metric{background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.metric .v{font-size:1.25rem;font-weight:700}
.metric .k{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-top:2px}
.badge{display:inline-block;padding:3px 12px;border-radius:999px;font-size:.8rem;font-weight:600}
.b-green{background:rgba(46,204,113,.15);color:var(--green);border:1px solid rgba(46,204,113,.4)}
.b-yellow{background:rgba(255,209,102,.12);color:var(--yellow);border:1px solid rgba(255,209,102,.4)}
.b-orange{background:rgba(255,169,77,.12);color:var(--orange);border:1px solid rgba(255,169,77,.4)}
.b-red{background:rgba(255,91,110,.12);color:var(--red);border:1px solid rgba(255,91,110,.4)}
table{width:100%;border-collapse:collapse;font-size:.86rem}
th{color:var(--muted);text-align:left;font-weight:600;padding:8px 10px;border-bottom:1px solid var(--border)}
td{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:top}
tr:last-child td{border-bottom:none}
.bar-wrap{background:var(--panel2);border-radius:6px;height:14px;width:100%;min-width:110px;overflow:hidden}
.bar{height:100%;border-radius:6px}
.sent{border-left:3px solid var(--border);padding:10px 14px;margin-bottom:10px;background:var(--panel2);border-radius:0 8px 8px 0}
.sent.flag{border-left-color:var(--red)}
.sent.ok{border-left-color:var(--green)}
.sent .meta{font-size:.75rem;color:var(--muted);margin-bottom:4px}
.sent .rs{font-size:.78rem;color:var(--muted);margin-top:4px}
footer{color:var(--muted);font-size:.75rem;margin-top:26px;text-align:center}
a{color:var(--accent);text-decoration:none}
@media print{body{background:#fff;color:#111}.panel{border-color:#ddd}}
"""


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


def _donut(ai_pct: float) -> str:
    """SVG donut gauge for the consensus score."""
    pct = max(0.0, min(100.0, ai_pct))
    r, cx, cy = 62.0, 80.0, 80.0
    circ = 2 * 3.14159265 * r
    dash = circ * pct / 100.0
    color = _verdict_color(pct)
    return f"""
<svg viewBox="0 0 160 160" width="170" height="170" role="img" aria-label="Consensus {pct:.0f}% AI">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="var(--panel2)" stroke-width="16"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="16"
      stroke-dasharray="{dash:.1f} {circ - dash:.1f}" stroke-linecap="round"
      transform="rotate(-90 {cx} {cy})"/>
  <text x="{cx}" y="{cy - 2}" text-anchor="middle" fill="var(--text)"
      font-size="30" font-weight="700">{pct:.0f}%</text>
  <text x="{cx}" y="{cy + 22}" text-anchor="middle" fill="var(--muted)" font-size="11">AI PROBABILITY</text>
</svg>"""


def _engine_bars(report: DetectionReport) -> str:
    rows = []
    for eng in report.engines.values():
        if eng.available:
            color = _verdict_color(eng.ai_percentage)
            rows.append(f"""
<tr>
  <td style="width:32%">{html.escape(eng.engine_name)}</td>
  <td style="width:12%"><span class="badge {_verdict_badge_class(eng.ai_percentage)}">{eng.ai_percentage:.1f}%</span></td>
  <td style="width:40%"><div class="bar-wrap"><div class="bar" style="width:{eng.ai_percentage:.0f}%;background:{color}"></div></div></td>
  <td style="width:16%;color:var(--muted)">{html.escape(eng.verdict)}</td>
</tr>""")
        else:
            rows.append(f"""
<tr style="opacity:.55">
  <td>{html.escape(eng.engine_name)}</td>
  <td><span class="badge b-yellow">OFFLINE</span></td>
  <td colspan="2" style="color:var(--muted)">{html.escape((eng.error or "unavailable")[:80])}</td>
</tr>""")
    return "<table><thead><tr><th>Engine</th><th>AI&nbsp;%</th><th>Distribution</th><th>Verdict</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _cadence_chart(report: DetectionReport) -> str:
    lengths = [s.word_count for s in report.sentences]
    if not lengths:
        return "<p style='color:var(--muted)'>No sentences to chart.</p>"
    max_len = max(lengths) or 1
    bars = []
    for i, s in enumerate(report.sentences, 1):
        w = max(2, int((s.word_count / max_len) * 100))
        color = "var(--red)" if s.flagged else "var(--green)"
        bars.append(f"""
<tr>
  <td style="width:8%;color:var(--muted)">S{i:02d}</td>
  <td style="width:70%"><div class="bar-wrap"><div class="bar" style="width:{w}%;background:{color}"></div></div></td>
  <td style="width:10%;color:var(--muted)">{s.word_count}w</td>
  <td style="width:12%;color:{color}">{'AI' if s.flagged else 'OK'}</td>
</tr>""")
    return "<table><tbody>" + "".join(bars) + "</tbody></table>"


def _sentences(report: DetectionReport) -> str:
    if not report.sentences:
        return ""
    blocks = []
    for s in report.sentences:
        cls = "flag" if s.flagged else "ok"
        reason_html = f"<div class='rs'>↳ {html.escape(', '.join(s.reasons))}</div>" if s.reasons else ""
        blocks.append(f"""
<div class="sent {cls}">
  <div class="meta">Sentence {s.index + 1} · {s.word_count} words · {s.ai_probability:.0f}% AI risk · {'🔴 FLAGGED' if s.flagged else '🟢 human-sounding'}</div>
  <div>{html.escape(s.text)}</div>
  {reason_html}
</div>""")
    return "".join(blocks)


def _single_page(report: DetectionReport) -> str:
    badge = _verdict_badge_class(report.consensus_ai_probability)
    metrics = f"""
<div class="grid">
  <div class="metric"><div class="v">{report.word_count}</div><div class="k">Words</div></div>
  <div class="metric"><div class="v">{report.sentence_count}</div><div class="k">Sentences</div></div>
  <div class="metric"><div class="v">{report.burstiness_ratio:.2f}</div><div class="k">Burstiness σ/μ</div></div>
  <div class="metric"><div class="v">{report.mean_sentence_length:.1f}</div><div class="k">Mean Sent. Len</div></div>
  <div class="metric"><div class="v">{len(report.banned_words_found)}</div><div class="k">AI Buzzwords</div></div>
  <div class="metric"><div class="v">{report.em_dash_count}</div><div class="k">Em Dashes</div></div>
</div>"""

    engines_note = ""
    if report.degraded:
        engines_note = f"<p class='sub'>⚠️ {html.escape(report.degradation_note or 'Live engines degraded to local-only mode.')}</p>"

    return f"""
<div class="wrap">
  <h1>🛡️ AI Text Detection Report</h1>
  <div class="sub">Source: {html.escape(report.source)} · Mode: {html.escape(report.engine_mode)} · {report.analysis_ms:.0f} ms</div>
  {engines_note}
  <div class="panel" style="display:flex;align-items:center;gap:28px;flex-wrap:wrap">
    {_donut(report.consensus_ai_probability)}
    <div style="flex:1;min-width:260px">
      <span class="badge {badge}">{html.escape(report.consensus_verdict)}</span>
      <p style="margin-top:12px;color:var(--muted);font-size:.9rem">Risk level: <strong style="color:var(--text)">{html.escape(report.risk_level)}</strong><br/>
      Human probability: {report.consensus_human_probability:.1f}%</p>
    </div>
  </div>
  <div class="panel">{metrics}</div>
  <h2>Engine Breakdown</h2>
  <div class="panel">{_engine_bars(report)}</div>
  <h2>Sentence Cadence &amp; Burstiness</h2>
  <div class="panel">{_cadence_chart(report)}</div>
  <h2>Sentence-Level Classification</h2>
  <div class="panel">{_sentences(report)}</div>
  <footer>Generated by <a href="https://github.com/dustindog101/ai-detector-cli">ai-detector-cli</a> · heuristic consensus, not a verdict of authorship.</footer>
</div>"""


def _batch_page(batch: BatchReport, per_file_reports: bool = False) -> str:
    rows = []
    flagged_count = 0
    for entry in batch.entries:
        rep = entry.report
        if entry.error:
            rows.append(f"""
<tr><td>{html.escape(entry.path)}</td><td colspan="4" style="color:var(--red)">{html.escape(entry.error)}</td></tr>""")
            continue
        if rep.consensus_ai_probability > batch.threshold:
            flagged_count += 1
        color = _verdict_color(rep.consensus_ai_probability)
        rows.append(f"""
<tr>
  <td style="max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{html.escape(entry.path)}</td>
  <td><span class="badge {_verdict_badge_class(rep.consensus_ai_probability)}">{rep.consensus_ai_probability:.1f}%</span></td>
  <td style="width:34%"><div class="bar-wrap"><div class="bar" style="width:{rep.consensus_ai_probability:.0f}%;background:{color}"></div></div></td>
  <td>{rep.word_count}</td>
  <td style="color:var(--muted)">{html.escape(rep.risk_level)}</td>
</tr>""")

    ok = [e for e in batch.entries if e.report]
    avg = sum(e.report.consensus_ai_probability for e in ok) / len(ok) if ok else 0.0
    summary = f"""
<div class="grid">
  <div class="metric"><div class="v">{len(batch.entries)}</div><div class="k">Files Scanned</div></div>
  <div class="metric"><div class="v">{flagged_count}</div><div class="k">Above {batch.threshold:.0f}% Threshold</div></div>
  <div class="metric"><div class="v">{avg:.1f}%</div><div class="k">Mean AI Score</div></div>
  <div class="metric"><div class="v">{batch.elapsed_ms:.0f} ms</div><div class="k">Total Time</div></div>
</div>"""
    return f"""
<div class="wrap">
  <h1>🗂️ Batch AI Detection Report</h1>
  <div class="sub">Mode: {html.escape(batch.engines_mode)} · Threshold: {batch.threshold:.0f}%</div>
  <div class="panel">{summary}</div>
  <h2>Per-File Results (ranked)</h2>
  <div class="panel">
  <table><thead><tr><th>File</th><th>AI %</th><th>Score</th><th>Words</th><th>Risk</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
  </div>
  <footer>Generated by <a href="https://github.com/dustindog101/ai-detector-cli">ai-detector-cli</a></footer>
</div>"""


def export_html(report: DetectionReport) -> str:
    """Render one DetectionReport as a standalone HTML document."""
    body = _single_page(report)
    return _wrap_page(body)


def export_batch_html(batch: BatchReport) -> str:
    """Render a BatchReport as a standalone HTML document."""
    body = _batch_page(batch)
    return _wrap_page(body)


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
