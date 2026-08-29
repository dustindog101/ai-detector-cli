# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

## [2.3.0] - 2026-08-29

### Added
- **Grammarly AI Detector engine** (stealth browser tier): automates
  grammarly.com/ai-detector, the free public checker ranked #1 by several
  2026 comparisons, and extracts AI/human percentages from the rendered
  result. Verified live on 2026-08-29 (AI sample -> 100% AI-generated,
  human sample -> 99% human-generated). Registry grows to 20 engines.
- **Academic PDF audit report** (`--pdf PATH`, or `--export report.pdf`):
  reportlab-based formal provenance audit mirroring the HTML report -
  ruled masthead with unique report ID, similarity-index band, numbered
  sections, engine results table, stylometric signals, flagged-sentence
  findings, methodology & limitations, page-numbered footer. The [pdf]
  extra now installs pypdf + reportlab; PDF export exits with an install
  hint when reportlab is missing.

### Changed
- HTML report redesigned to academic provenance-audit presentation: serif
  typography, ruled masthead + formal metadata tables, report ID
  (AIA-xxxxxxxxxx), numbered sections 1-10, similarity-index score band,
  concordance wording for inter-engine agreement. Still a single
  self-contained file with zero JS, auto light/dark, and print rules.
- PDF export writes bytes (binary-safe); --html/--pdf are mutually
  exclusive shortcuts for --export.

## [2.2.0] - 2026-08-29

### Added
- **In-depth self-contained HTML audit report** (`--html PATH`, or the
  existing `--export report.html`). Zero external assets, zero JavaScript;
  auto light/dark theme and clean printing. New sections: executive summary
  with plain-English risk interpretation, consensus position on a zoned 0-100
  risk scale, engine matrix grouped by tier with per-engine diagnostics in
  collapsible cards, inter-engine agreement analysis (max-min spread with
  confidence label), stylometric signal grid, AI-vocabulary tell chips,
  sentence cadence chart, sentence risk histogram, and a methodology &
  limitations section. Batch HTML gains a score-distribution histogram and a
  ranked per-file table with above-threshold status chips.
- `--html PATH` CLI shortcut (mutually exclusive with `--export`); wired for
  single, batch, and compare flows.

### Changed
- README redesigned: centered hero with badges, feature table, HTML report
  section, and an expanded shipped/next/exploring roadmap.
- AI PR review workflow documented as intentionally PR-only: review comments
  are the only automatic posting surface, so branch pushes are not reviewed.

## [2.1.0] - 2026-08-29

### Added
- **Five premium key-based API engines** that auto-activate the moment their
  environment variable is set (no flags needed):
  - `gptzero-api` — GPTZero Official REST API (`GPTZERO_API_KEY`, free tier),
    with per-sentence `generated_prob` flags.
  - `pangram` — Pangram Labs async task API (`PANGRAM_API_KEY`, free tier);
    benchmark-topping accuracy, segment-level flags.
  - `winston` — Winston AI v2.0 API (`WINSTON_API_KEY`), sentence flags.
  - `originality` — Originality.ai scan API (`ORIGINALITY_API_KEY`, paid).
  - `detecting-ai` — Detecting-AI.com v3 detector (`DETECTING_AI_API_KEY`,
    free tier) with defensive structured/textual result parsing.
  All endpoints and auth shapes were verified live on 2026-08-29; missing keys
  produce an `UNAVAILABLE` result with the sign-up URL instead of noise.
- **Binoculars local neural engine** (`binoculars`): zero-shot detector from
  "Spotting LLMs With Binoculars" (Hans et al., ICML 2024) implementing the
  official perplexity/cross-perplexity ratio with the official 0.90133
  threshold (~0.93 AUROC). Fully offline; opt-in via the new
  `[binoculars]` extra and `AIDETECT_BINOCULARS=1`, with env-configurable
  model pairs (`AIDETECT_BINOCULARS_OBSERVER_MODEL` /
  `AIDETECT_BINOCULARS_PERFORMER_MODEL`, e.g. the TinyLlama pair for ~3 GB RAM).
- `--list-engines` now shows the premium tier with per-engine ACTIVE/inactive
  state and the Binoculars row.
- `scripts/test_premium_engines.py`: live verification harness for all five
  premium engines (runs against the real APIs when keys are exported).
- Shell completions (bash/zsh/fish) updated with the six new engine keys.

### Changed
- **Engine registry**: total count is now 19 (2 core HTTP + 5 premium + 4
  statistical + 1 neural + 7 browser). Premium engines deduplicate correctly
  across suites and can be targeted with `--engines <key>` even when inactive.
- **Degradation semantics fixed**: the report is only marked `degraded` when
  *every* live engine fails; a partial live failure (e.g. ZeroGPT down,
  Sapling up) no longer falsely claims a local-only fallback.
- Sentence-level cloud flags now also consume GPTZero, Winston and Pangram
  flagged segments.
- README engine matrix, `docs/ENGINES.md` endpoint reference (new Premium +
  Binoculars sections with verified request/response schemas), and pyproject
  metadata updated for v2.1.0.

## [2.0.0] - 2026-08-29

### Added
- **Batch mode** (`--batch DIR`, `--recursive`, `--glob`): scan entire folders of
  documents with a ranked per-file summary table, aggregate statistics, and
  exit-code integration for CI pipelines.
- **HTML report export** (`--export report.html`): fully self-contained,
  single-file report with an SVG consensus gauge, engine bar charts, sentence
  cadence chart, and flagged-sentence breakdown. Zero external assets.
- **Auto-adaptive engine orchestration**: live HTTP and local statistical
  engines run concurrently; when the network is unreachable the tool
  automatically degrades to local-only mode with a stderr warning instead of
  failing.
- **High-performance HTTP layer** (`http_client.py`): per-host persistent
  keep-alive connection pools, automatic retries with exponential backoff +
  jitter on transient failures, and a global `--timeout` / `AIDETECT_TIMEOUT`
  setting.
- **Sapling automatic chunking**: documents longer than the ~1,950-char API
  limit are split at sentence boundaries and sent as concurrent requests with
  length-weighted score merging.
- **Engine selection** (`--engines zerogpt,sapling,gltr`) and
  `--list-engines` registry view.
- **Tunable concurrency** (`--workers N`).
- **JSON output for compare and batch modes** (`--json` now works everywhere).
- **Cross-platform browser auto-discovery** for the stealth engine suite
  (macOS, Linux, Windows, PATH, and Patchright/Playwright bundled Chromium),
  overridable via `AIDETECT_CHROME_PATH`.
- **Public install script** (`install.sh`) with venv isolation, PATH setup,
  and shell completions for bash/zsh/fish, plus `uninstall.sh`.
- **CI/CD**: GitHub Actions test matrix (Python 3.8–3.12), lint job, and a
  Trusted-Publishing PyPI release workflow.

### Changed
- Sentence-level reasons are de-duplicated (one sentence can no longer list
  the same tell twice).
- `--export` confirmation messages moved to stderr so JSON piping stays clean.
- Export messages and usage banners write to stderr; only reports go to stdout.
- JSON schema now includes `source`, `engine_mode`, `degraded`,
  `degradation_note`, and `analysis_ms` fields.
- Project metadata (license file, URLs, keywords, classifiers, extras) made
  PyPI-publish ready; version bumped to 2.0.0.

### Fixed
- Hardcoded macOS-only Chrome paths in all 7 browser engines replaced with
  cross-platform discovery.
- Broken Playwright fallback in the Sapling engine removed (dead code that
  always returned UNAVAILABLE).
- `SyntaxWarning: invalid escape sequence` in the ContentDetector engine.
- Windows terminals now force UTF-8 output so emoji in reports do not crash
  cp1252 consoles.

## [1.0.0] - 2026-08-28

### Added
- Initial release: multi-engine AI text detection with ZeroGPT live cloud API,
  GLTR token-rank analysis, burstiness/cadence modeling, perplexity heuristics,
  PubMed lexicon tells, sentence-level extraction, compare mode, JSON/Markdown
  export, and stdin piping.
