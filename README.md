# 🛡️ ai-detect — Multi-Engine AI Text Detector CLI

[![CI](https://github.com/dustindog101/ai-detector-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/dustindog101/ai-detector-cli/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ai-detector-cli)](https://pypi.org/project/ai-detector-cli/)
[![Python](https://img.shields.io/pypi/pyversions/ai-detector-cli)](https://pypi.org/project/ai-detector-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**Audit text against 13 detection engines simultaneously** — live cloud APIs
(ZeroGPT, Sapling), stealth-browser detectors (GPTZero, QuillBot, Scribbr,
Writer, CopyLeaks, and more), and instant local statistical models (GLTR,
burstiness, perplexity, AI-lexicon tells) — and get one weighted consensus
score with sentence-level explanations.

```
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

## Why ai-detect

- **Consensus, not vibes.** One weighted score across independent engines,
  each with tunable trust weights.
- **Explainable.** Every flagged sentence lists *why* it tripped — cloud
  flags, AI buzzwords, formulaic transitions, em dashes, tripartite lists.
- **Auto-adaptive.** Cloud + local engines run concurrently; if you're
  offline it automatically degrades to local-only mode with a warning instead
  of crashing.
- **Fast.** Default suite finishes in ~1 s (network-bound); local-only mode
  runs in **< 10 ms**. Keep-alive connection pooling, retries with backoff,
  and parallel engine workers keep it snappy.
- **Zero required dependencies.** Core runs on the Python standard library
  (3.8+). Browser engines and PDF support are optional extras.
- **Private local mode.** `--local-only` never sends your text anywhere.

## Install

### One-line install script (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/dustindog101/ai-detector-cli/main/install.sh | sh
```

The script installs an isolated venv under `~/.local/share/ai-detector-cli`,
symlinks `ai-detect` into `~/.local/bin`, and sets up **bash/zsh/fish shell
completions**. Re-run it any time to update. Uninstall with
`sh uninstall.sh`.

Flags: `--prefix DIR` · `--ref REF` · `--repo URL` · `--no-completions`

### pip

```bash
pip install ai-detector-cli
# optional extras:
pip install "ai-detector-cli[browser]"   # stealth browser engines (patchright)
pip install "ai-detector-cli[pdf]"       # full .pdf text extraction (pypdf)
```

### pipx / uv (one-shot)

```bash
pipx install ai-detector-cli
uvx ai-detector-cli --local-only notes.md
```

## Quick Start

```bash
ai-detect assignment.md                  # full audit (cloud + local, concurrent)
ai-detect --local-only notes.md          # instant, offline, private
echo "text..." | ai-detect --json        # pipe stdin, machine-readable out
ai-detect --batch ./essays/ -r           # rank every document in a folder
ai-detect --compare draft.txt humanized.txt
ai-detect --export report.html paper.txt # self-contained HTML report
ai-detect --list-engines                 # inspect the engine registry
```

Exit code is `1` when the consensus score exceeds `--threshold` (default 30),
so you can drop it straight into CI:

```yaml
# GitHub Actions example: fail PRs that look > 50% AI
- run: ai-detect --local-only --threshold 50 $(git diff --name-only HEAD~1 | grep -E '\.(md|txt)$')
```

## All Options

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
  --no-sentences         hide sentence-level breakdown
  --verbose, -v          full engine diagnostics
  --stdin                read text from stdin
```

## The Engines

| Tier | Engines | Speed | Network |
| :--- | :--- | :--- | :--- |
| **Live HTTP** (default) | ZeroGPT, Sapling | ~0.3–1 s | Yes |
| **Local statistical** (default) | GLTR token-rank, Burstiness σ/μ, Perplexity/entropy, PubMed AI-lexicon | < 5 ms each | None |
| **Stealth browser** (`--browser`) | GPTZero, CopyLeaks, QuillBot, Scribbr, Writer, ContentDetector.ai, IsGen | 10–60 s | Yes |

Full endpoint reference — payloads, limits, response schemas, quirks, key
expiry notes — lives in [`docs/ENGINES.md`](docs/ENGINES.md). The consensus is
a weighted average of available engines; unavailable engines simply drop out
of the denominator.

### Benchmarks (local-only tier, 3.12 on Linux)

| Operation | Time |
| :--- | :--- |
| Single document, 4 local engines | **~3 ms** |
| Batch scan, 4 documents | **~6 ms** |
| Default suite (2 cloud + 4 local, concurrent) | ~1.2 s (network-bound) |
| Package import | ~30 ms |

## Automating with JSON

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

## Roadmap / Ideas

- [ ] Optional local transformer baseline (ONNX) as a 5th tier
- [ ] SARIF output for code-review integration
- [ ] `--watch` mode for live re-scanning while writing
- [ ] Pluggable custom engines via entry points

See [`CONTRIBUTING.md`](CONTRIBUTING.md) to pick one up.

## Honest Limitations

AI-text detection is **probabilistic**. False positives happen (especially on
short or formulaic human writing) and false negatives happen (light paraphrase
defeats most detectors, including the commercial ones this tool queries). Use
`ai-detect` for signal, not verdicts. Live engines are public endpoints and
may rate-limit or change without notice; the tool degrades gracefully when
they do.

## License

MIT — see [`LICENSE`](LICENSE).
