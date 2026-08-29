<div align="center">

<img src="https://img.shields.io/badge/🛡️_ai--detect-19_engines-3b4fd8?style=for-the-badge&labelColor=24307a" alt="ai-detect" height="34"><br>

**Multi-Engine AI Text Detector CLI**<br>
*Run your text through 19 detection engines at once — get one weighted consensus, sentence-level evidence, and an in-depth HTML audit report.*

[![CI](https://github.com/dustindog101/ai-detector-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/dustindog101/ai-detector-cli/actions/workflows/ci.yml)
[![CodeQL](https://github.com/dustindog101/ai-detector-cli/actions/workflows/codeql.yml/badge.svg)](https://github.com/dustindog101/ai-detector-cli/actions/workflows/codeql.yml)
[![Coverage](https://github.com/dustindog101/ai-detector-cli/actions/workflows/coverage.yml/badge.svg)](https://github.com/dustindog101/ai-detector-cli/actions/workflows/coverage.yml)
[![PyPI](https://img.shields.io/pypi/v/ai-detector-cli)](https://pypi.org/project/ai-detector-cli/)
[![Python](https://img.shields.io/pypi/pyversions/ai-detector-cli)](https://pypi.org/project/ai-detector-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Install](#-install) · [Quick Start](#-quick-start) · [Engines](#-the-engines) · [HTML Report](#-in-depth-html-report) · [JSON Automation](#-automating-with-json) · [Roadmap](#-roadmap)

</div>

---

```text
 🛡️  MULTI-ENGINE AI TEXT DETECTION CONSENSUS AUDIT
==================================================================================
 📊 CONSENSUS SCORE:    81.2% AI Probability (18.8% Human)
 🚦 OVERALL VERDICT:    🔴 HIGH AI DETECTION RISK (Will Trip Turnitin/GPTZero)
----------------------------------------------------------------------------------
 Sapling AI Detector                | 100.0% | AI    | 4 flagged sentences
 ZeroGPT Live Cloud API             | 100.0% | AI    | Your Text contains mix
 Burstiness & Cadence Model         |  90.0% | AI    | Ratio: 0.17
 PubMed AI Lexicon & Tells          |  99.0% | AI    | 8 buzzwords found
 GLTR Rank & Token Distribution     |   5.0% | HUMAN | 62.0% rare tokens
----------------------------------------------------------------------------------
 📝 [Sentence 1] 🔴 FLAGGED — "When evaluating relational databases versus
     NoSQL solutions, it is crucial to delve into the multifaceted trade-offs."
     ↳ ZeroGPT Cloud Flag, Sapling Cloud Flag, AI buzzwords: crucial, delve
```

## ✨ Why ai-detect

| | |
| :--- | :--- |
| 🎯 **Consensus, not vibes** | One weighted score across independent engines, each with a tunable trust weight. Unavailable engines drop out of the denominator — they never silently count as "human". |
| 🔍 **Explainable** | Every flagged sentence lists *why* it tripped: cloud flags, AI buzzwords, formulaic transitions, em dashes, tripartite lists. |
| 🩹 **Auto-adaptive** | Cloud + local engines run concurrently; offline it degrades to local-only mode with a warning instead of crashing. |
| ⚡ **Fast** | Default suite ~1 s (network-bound); local-only mode **< 10 ms** with keep-alive pooling, backoff retries, and parallel workers. |
| 📦 **Zero required deps** | Core runs on the Python standard library (3.8+). Browser engines, PDF, and Binoculars are optional extras. |
| 🔒 **Private local mode** | `--local-only` never sends your text anywhere. |
| 📊 **In-depth HTML report** | A self-contained consulting-grade audit document — donut gauge, engine matrix, agreement analysis, cadence charts. [See below.](#-in-depth-html-report) |

## 📥 Install

### One-line install script (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/dustindog101/ai-detector-cli/main/install.sh | sh
```

The script installs an isolated venv under `~/.local/share/ai-detector-cli`,
symlinks `ai-detect` into `~/.local/bin`, and sets up **bash/zsh/fish shell
completions**. Re-run it any time to update. Uninstall with `sh uninstall.sh`.

Flags: `--prefix DIR` · `--ref REF` · `--repo URL` · `--no-completions`

### pip

```bash
pip install ai-detector-cli
# optional extras:
pip install "ai-detector-cli[browser]"     # stealth browser engines (patchright)
pip install "ai-detector-cli[pdf]"         # full .pdf text extraction (pypdf)
pip install "ai-detector-cli[binoculars]"  # local neural detector (torch + transformers)
```

<details>
<summary><b>Premium engines (optional) — export a key, the engine auto-joins every run</b></summary>

```bash
export GPTZERO_API_KEY=...      # free tier - https://dashboard.gptzero.me
export PANGRAM_API_KEY=...      # free tier - https://www.pangram.com
export WINSTON_API_KEY=...      # trial     - https://gowinston.ai
export ORIGINALITY_API_KEY=...  # paid      - https://app.originality.ai/api-access
export DETECTING_AI_API_KEY=... # free tier - https://detecting-ai.com
```

No flags needed — setting the environment variable is enough.

</details>

<details>
<summary><b>Binoculars (optional, local neural) — 93%+ AUROC zero-shot detector, ICML 2024</b></summary>

```bash
pip install "ai-detector-cli[binoculars]"
export AIDETECT_BINOCULARS=1               # auto-include in default runs
ai-detect --engines binoculars report.md   # or run it standalone
```

Runs fully offline once models are downloaded (~13 GB for the Falcon-7B pair,
or ~3 GB with the TinyLlama pair — see
[`docs/ENGINES.md`](docs/ENGINES.md) for tuning either pair).

</details>

### pipx / uv (one-shot)

```bash
pipx install ai-detector-cli
uvx ai-detector-cli --local-only notes.md
```

## 🚀 Quick Start

```bash
ai-detect assignment.md                  # full audit (cloud + local, concurrent)
ai-detect --local-only notes.md          # instant, offline, private
ai-detect --html report.html paper.txt   # in-depth standalone HTML audit
echo "text..." | ai-detect --json        # pipe stdin, machine-readable out
ai-detect --batch ./essays/ -r           # rank every document in a folder
ai-detect --compare draft.txt humanized.txt
ai-detect --list-engines                 # inspect the engine registry
```

Exit code is `1` when the consensus score exceeds `--threshold` (default 30),
so you can drop it straight into CI:

```yaml
# GitHub Actions example: fail PRs that look > 50% AI
- run: ai-detect --local-only --threshold 50 $(git diff --name-only HEAD~1 | grep -E '\.(md|txt)$')
```

<details>
<summary><b>All options</b></summary>

```text
usage: ai-detect [file] [-c ORIG MOD] [-b DIR] [flags]

  --batch, -b DIR        batch-scan a directory; prints a ranked table
  --recursive, -r        recurse into subdirectories (with --batch)
  --glob PATTERN         filter batch files, e.g. '*.md'
  --compare, -c A B      before/after comparative audit
  --engines E1,E2        run only these engines (keys from --list-engines)
  --live-only            only ZeroGPT + Sapling cloud APIs
  --local-only           only local statistical engines (offline, private)
  --browser              add stealth browser engines (needs patchright)
  --all                  every engine (HTTP + browser + local)
  --workers, -w N        concurrent engine workers (default 6)
  --timeout SEC          global HTTP timeout (default 10; env AIDETECT_TIMEOUT)
  --threshold, -t PCT    exit-code threshold (default 30)
  --json                 JSON output (single, compare, and batch modes)
  --export, -e PATH      export .json / .md / .html report
  --html PATH            shortcut: in-depth standalone HTML audit report
  --no-sentences         hide sentence-level breakdown
  --verbose, -v          full engine diagnostics
  --stdin                read text from stdin
```

</details>

## 🛰️ The Engines

| Tier | Engines | Speed | Network |
| :--- | :--- | :--- | :--- |
| **Live HTTP** (default) | ZeroGPT, Sapling | ~0.3–1 s | Yes |
| **Premium API** (auto when key set) | GPTZero Official, Pangram, Winston AI, Originality.ai, Detecting-AI | ~0.5–5 s | Yes |
| **Local neural** (`--engines binoculars` / `AIDETECT_BINOCULARS=1`) | Binoculars (Falcon-7B pair, ICML 2024) | ~2–60 s first run | None* |
| **Local statistical** (default) | GLTR token-rank, Burstiness σ/μ, Perplexity/entropy, PubMed AI-lexicon | < 5 ms each | None |
| **Stealth browser** (`--browser`) | GPTZero, CopyLeaks, QuillBot, Scribbr, Writer, ContentDetector.ai, IsGen | 10–60 s | Yes |

\* first run downloads model weights; afterwards fully offline.

The consensus is a weighted average of available engines; unavailable engines
simply drop out of the denominator. Full endpoint reference — payloads, limits,
response schemas, quirks, key expiry notes — lives in
[`docs/ENGINES.md`](docs/ENGINES.md).

### Benchmarks (local-only tier, 3.12 on Linux)

| Operation | Time |
| :--- | :--- |
| Single document, 4 local engines | **~3 ms** |
| Batch scan, 4 documents | **~6 ms** |
| Default suite (2 cloud + 4 local, concurrent) | ~1.2 s (network-bound) |
| Package import | ~30 ms |

## 📊 In-Depth HTML Report

```bash
ai-detect --html report.html paper.txt    # or: --export report.html
ai-detect --batch ./essays/ --html batch.html
```

One **self-contained file** — zero external assets, zero JavaScript, works
offline, prints cleanly, and auto-adapts to dark mode. Open it anywhere and
share it as-is. What's inside:

| Section | What you get |
| :--- | :--- |
| **Executive summary** | Consensus donut gauge, verdict badge, human/AI split bar, and a plain-English interpretation of the risk level |
| **Risk scale** | The consensus score positioned on a 0–100 scale with color-coded risk zones |
| **Engine matrix** | Every engine grouped by tier (cloud / premium / local / browser) with weights, score bars, and per-engine diagnostics in collapsible cards |
| **Agreement analysis** | Max−min engine spread with a confidence label — know when engines disagree and the consensus is unstable |
| **Stylometric signals** | Words, sentences, mean sentence length ± σ, burstiness σ/μ, em dashes, semicolons, tripartite lists |
| **AI vocabulary tells** | Over-represented AI-lexicon phrases rendered as highlighted chips |
| **Cadence & distribution** | Per-sentence length chart (flagged vs human) + sentence risk histogram |
| **Sentence evidence** | Every sentence classified with its AI-risk % and the exact reasons it was flagged |
| **Methodology** | How the weighted consensus is computed, how risk bands map to verdicts, and the honest limitations |

Batch mode adds a score-distribution histogram and a ranked per-file table with
above-threshold status chips.

## 🤖 Automating with JSON

```bash
$ ai-detect --local-only --json notes.md | jq '.consensus_ai_probability, .degraded'
5.0
false
```

Every report includes `consensus_ai_probability`, `risk_level`, per-engine
`details`, `sentences[]` with `flagged` + `reasons`, burstiness metrics, and
v2 fields (`source`, `engine_mode`, `degraded`, `analysis_ms`). Batch JSON
adds a `summary` block with `files_above_threshold` — ideal for agents and
dashboards.

## 🗺️ Roadmap

**Shipped**

- [x] 19-engine registry: live cloud, premium key APIs, stealth browser, local statistical
- [x] Local neural detector (Binoculars, v2.1)
- [x] Weighted consensus + sentence-level explanations
- [x] Batch mode, compare mode, JSON automation
- [x] In-depth self-contained HTML audit report (v2.2)

**Next up**

- [ ] **Annotated exports** — flagged sentences highlighted *in-place* in DOCX/PDF copies
- [ ] **Diff mode** — `ai-detect --diff old.md new.md` with per-section score deltas
- [ ] **GitHub Action** — official marketplace action + pre-commit hook wrapping the threshold check
- [ ] **SARIF output** — feed findings into code-scanning UIs
- [ ] **CSV export** for batch runs (spreadsheet-friendly triage)

**Exploring**

- [ ] **Local web dashboard** — `ai-detect --serve` with drag-and-drop and live re-scan (`--watch`)
- [ ] **Ensemble meta-model** — stack engine outputs with a trained calibrator instead of fixed weights
- [ ] **Agreement statistics** — Kendall's W / Krippendorff's α across engines in reports
- [ ] **Multilingual lexicons** — burstiness + lexicon tells for ES/FR/DE/PT
- [ ] **Pluggable engines** — third-party engines via package entry points
- [ ] **Premium response caching** — avoid burning API quota on unchanged text
- [ ] **PDF report export** — the HTML audit as a print-ready PDF

Pick one up — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## ⚠️ Honest Limitations

AI-text detection is **probabilistic**. False positives happen (especially on
short or formulaic human writing) and false negatives happen (light paraphrase
defeats most detectors, including the commercial ones this tool queries). Use
`ai-detect` for signal, not verdicts. Live engines are public endpoints and
may rate-limit or change without notice; the tool degrades gracefully when
they do.

## 📄 License

MIT — see [`LICENSE`](LICENSE).
