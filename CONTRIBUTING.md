# Contributing to ai-detector-cli

Thank you for considering a contribution! This guide covers everything needed
to get a development environment running and submit a quality pull request.

## Development Setup

```bash
# 1. Clone your fork
git clone https://github.com/<your-username>/ai-detector-cli.git
cd ai-detector-cli

# 2. Create an isolated environment
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install in editable mode with dev tools
pip install -e ".[dev,browser,pdf]"
```

## Running the Tests

```bash
# Full local suite (no network required)
python -m unittest discover -s tests -v

# Lint
ruff check ai_detector_cli/
```

Tests marked as live/integration (`scripts/test_live_engines.py`) hit real
detection endpoints and are **not** run in CI; run them manually when changing
an engine's parsing logic:

```bash
python scripts/test_live_engines.py
```

## Project Layout

```
ai_detector_cli/
├── cli.py             # argument parsing, orchestration, batch mode, exit codes
├── models.py          # dataclasses: DetectionReport, EngineResult, BatchReport...
├── reporter.py        # terminal rendering + JSON/Markdown export
├── html_report.py     # self-contained HTML report generator
├── http_client.py     # keep-alive pooling, retries, timeouts
├── stealth.py         # cross-platform browser discovery + anti-detection
└── engines/           # one file per detection engine (base.py = interface)
```

## Adding a New Engine

1. Create `ai_detector_cli/engines/my_engine.py` with a class extending
   `BaseEngine` from `base.py`. Return an `EngineResult`; set `available=False`
   with an `error` message instead of raising on failure.
2. Register the instance in the right tier list in `engines/__init__.py`
   (live HTTP → `LIVE_HTTP_ENGINES`, browser → `BROWSER_ENGINES`, local →
   `LOCAL_ENGINES`).
3. Choose an honest `weight` (0–1) reflecting how much the consensus should
   trust this engine.
4. Add unit tests in `tests/test_engines.py` (offline; mock network calls).
5. Document the endpoint (payload, limits, response fields) in
   `docs/ENGINES.md`.

## Code Style

- Python 3.8+ compatible syntax only (no `match`, no `X | Y` unions,
  no `dict |` merge).
- Standard library only for the core package; third-party imports must be
  lazy and optional.
- All regexes in hot paths are precompiled at module level.
- Errors never crash the CLI: engines return `EngineResult(available=False)`,
  files produce per-entry errors in batch mode.

## Pull Requests

1. Fork → feature branch (`git checkout -b feat/my-feature`).
2. Make the change, add tests, run the suite and lint.
3. Update `CHANGELOG.md` under an "Unreleased" heading.
4. Open the PR with a clear description of what changed and why.

## Reporting Bugs

Open a GitHub issue with: the exact command, full output, OS + Python version,
and whether the text was run with live engines or `--local-only`.
Do **not** paste confidential documents into issues.
