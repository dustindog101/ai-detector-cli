# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

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
