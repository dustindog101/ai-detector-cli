# Engine & Endpoint Reference

Practical, reverse-engineered documentation for every detection engine in
`ai-detect` — useful for end users tuning weights, and for AI agents operating
the tool programmatically. All live endpoints were verified working on
**2026-08-29**.

---

## Live HTTP Cloud Engines

### ZeroGPT (`zerogpt`)

| Property | Value |
| :--- | :--- |
| Endpoint | `POST https://api.zerogpt.com/api/detect/detectText` |
| Auth | None (browser-like headers required) |
| Required headers | `Origin: https://www.zerogpt.com`, `Referer: https://www.zerogpt.com/`, browser `User-Agent` |
| Payload | `{"input_text": "<text>"}` |
| Max size | ~14,000 chars (tool truncates and sets `details.truncated`) |
| Weight | 0.35 |

**Response fields (inside `data`):**
- `fakePercentage` — 0–100, AI probability (mapped to engine AI %)
- `isHuman` — complementary human score
- `h` — array of flagged sentence strings (used for sentence-level flags)
- `sentences`, `specialIndexes`, `specialSentences` — per-sentence breakdown
- `feedback` — human-readable summary string
- `textWords`, `aiWords` — word counts
- `detected_language` — language code

**Quirks:**
- Very short inputs (< ~30 words) return `isHuman: 50` with feedback
  *"Please input more text for a more accurate result"* — treat scores for
  tiny texts as noise.
- `feedback` often says "mixed signals" even for clearly AI text; rely on
  `fakePercentage` instead.
- No documented rate limit; be polite — bursts may trigger Cloudflare.

---

### Sapling (`sapling`)

| Property | Value |
| :--- | :--- |
| Endpoint | `POST https://api.sapling.ai/api/v1/aidetect` |
| Auth | `key` field in JSON body (JWT). Tool bundles the public web key; override via `SAPLING_API_KEY` env var |
| Payload | `{"text": "...", "key": "...", "sent_scores": true}` |
| Max size | ~1,950 chars/request — the tool auto-chunks at sentence boundaries and sends chunks concurrently, merging scores weighted by chunk length |
| Weight | 0.35 |

**Response fields:**
- `score` — 0–1 float, **higher = more AI** (tool multiplies by 100)
- `sentence_scores` — `[{sentence, score}]`; sentence score **< 0.5 ⇒ AI-likely**
- `score_string` — HTML string with per-token background shading (useful for
  visual diffs; not used by the CLI)
- `used_tokens`, `hash`, `premium` — metadata

**Quirks:**
- ⚠️ The bundled public web key expires **2026-09-02** (it is the sapling.ai
  website's own key). When it expires the engine returns HTTP 401/403 and the
  tool prints a hint. Fix: set a fresh key with `export SAPLING_API_KEY=...`
- Sentence scores use the opposite polarity of the overall score — mind the
  `< 0.5` threshold when parsing manually.

---

## Premium Key-Based API Engines (auto-activate when key is set)

These engines talk directly to official vendor APIs. They are registered
always, but only **run automatically when their environment variable is set**
(set the key → the engine silently joins the default and `--live-only` suites;
remove it → it drops out). You can always force one with
`--engines <key>`, even without a key — you'll get an `UNAVAILABLE` result
with the sign-up URL in `error`.

### GPTZero Official API (`gptzero-api`)

| Property | Value |
| :--- | :--- |
| Endpoint | `POST https://api.gptzero.me/v2/predict/text` |
| Auth | `X-Api-Key: <GPTZERO_API_KEY>` (free tier ~10k words/mo — https://dashboard.gptzero.me) |
| Payload | `{"document": "<text>"}` |
| Max size | 50,000 chars (tool truncates) |
| Weight | 0.40 |
| Verified | 2026-08-29 (endpoint alive; invalid key → 403 `{"error":"API key has no owner"}`) |

**Response fields (inside `documents[0]`):**
- `completely_generated_prob` — 0–1 probability the text is fully AI-generated
- `average_generated_prob` — mean per-sentence AI probability
- `predicted_class` — `human-only` / `mixed` / `ai-only`
- `confidence_score` — model confidence
- `sentences[]` — `[{sentence, generated_prob}]`; sentences with
  `generated_prob >= 0.65` become tool-level sentence flags

**Score mapping:** `ai-only` → `completely_generated_prob × 100`; `mixed` →
average of the two probabilities; `human-only` → capped at 45%.

---

### Pangram (`pangram`)

| Property | Value |
| :--- | :--- |
| Endpoint | `POST https://text.external-api.pangram.com/task` then `GET /task/<task_id>` (async, tool polls every 0.75 s, max ~18 s) |
| Auth | `x-api-key: <PANGRAM_API_KEY>` (free tier — https://www.pangram.com) |
| Payload | `{"text": "<text>", "public_dashboard_link": false}` |
| Max size | 40,000 chars (tool truncates) |
| Weight | 0.45 |
| Verified | 2026-08-29 (invalid key → 401 `{"detail":"Invalid API key"}`) |

**Task result fields:** `fraction_ai` (0–1 → engine AI %), `fraction_ai_assisted`,
`fraction_human`, `prediction_short`, `headline`, `num_ai_segments`,
`ai_segments[]` (each `text` becomes a sentence-level flag). Terminal stages:
`STAGE_SUCCESS` / `STAGE_FAILED`.

Pangram is consistently the top scorer in third-party benchmarks and is the
most rugged against paraphrase/humanizer attacks.

---

### Winston AI (`winston`)

| Property | Value |
| :--- | :--- |
| Endpoint | `POST https://api.gowinston.ai/v1/ai-content-detection` |
| Auth | `Authorization: Bearer <WINSTON_API_KEY>` (3-day trial — https://gowinston.ai) |
| Payload | `{"text": "<text>", "version": "2.0"}` |
| Max size | 30,000 chars (tool truncates) |
| Weight | 0.30 |
| Verified | 2026-08-29 (invalid key → 401 `{"error":"ERROR_RETRIEVING_USER"}`) |

**Response fields:** `score` (AI probability — historically returned as either
0–1 or 0–100 across versions; the tool normalizes defensively), `result`,
`sentences[]` (`[{text, ai_score}]` — flagged at ≥ 0.65 normalized).

---

### Originality.ai (`originality`)

| Property | Value |
| :--- | :--- |
| Endpoint | `POST https://api.originality.ai/api/v1/scan/ai` |
| Auth | `X-OAI-API-Key: <ORIGINALITY_API_KEY>` (paid/enterprise — https://app.originality.ai/api-access) |
| Payload | `{"content": "<text>", "aiModelVersion": "1.0.0", "storeScan": "false"}` |
| Max size | 50,000 chars (tool truncates) |
| Weight | 0.35 |
| Verified | 2026-08-29 (endpoint/auth shape verified; free plans → 422 "Enterprise Subscription Required") |

**Response fields:** `ai_score.fake` (0–1 → engine AI %), `ai_score.clear`,
`version`, `credits_used`. No sentence-level output.

---

### Detecting-AI (`detecting-ai`)

| Property | Value |
| :--- | :--- |
| Endpoint | `POST https://api.detecting-ai.com/api/detect/` |
| Auth | `X-API-Key: <DETECTING_AI_API_KEY>` (free tier — https://detecting-ai.com) |
| Payload | `{"text": "<text>", "version": "v3"}` |
| Max size | 20,000 chars (tool truncates) |
| Weight | 0.20 |
| Verified | 2026-08-29 (docs verified at detecting-ai.com/api-docs) |

**Response fields:** `{success, data: {details: {result}, version, words_processed}}`.
The inner `result` shape varies between versions — the tool handles structured
dicts (keys like `ai`/`aiScore`) and textual results (percentage regex), and
marks itself UNAVAILABLE when no score can be extracted.

---

## Local Neural Detector (opt-in)

### Binoculars (`binoculars`)

| Property | Value |
| :--- | :--- |
| Model | Zero-shot pair ratio — "Spotting LLMs With Binoculars" (Hans et al., ICML 2024, arXiv:2401.12070) |
| Default models | `tiiuae/falcon-7b` (observer) + `tiiuae/falcon-7b-instruct` (performer) |
| Extra | `pip install "ai-detector-cli[binoculars]"` (torch + transformers) |
| Activation | `AIDETECT_BINOCULARS=1` auto-includes it; or force with `--engines binoculars` |
| Max size | 8,000 chars (tool truncates) |
| Weight | 0.50 |
| Device | auto (`cuda` → `cpu`); override with `AIDETECT_BINOCULARS_DEVICE` |

**Score:** `perplexity(performer) / cross-perplexity(observer→performer)`.
Lower = more AI. Official decision threshold **0.9013310719761093** (~0.93
AUROC). The tool maps the raw score to a 0–100 AI percentage calibrated so the
threshold lands at ~14%, and reports the raw score in `details.binoculars_score`.

**Environment knobs:**
- `AIDETECT_BINOCULARS_OBSERVER_MODEL` / `AIDETECT_BINOCULARS_PERFORMER_MODEL` —
  any tokenizer-compatible pair. Low-RAM option (~3 GB):
  `TinyLlama/TinyLlama-1.1B-intermediate-step-1431k-3T` +
  `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (accuracy reduced vs Falcon-7B).
- First run downloads weights (~13 GB Falcon / ~3 GB TinyLlama); afterwards
  fully offline.

---

## Stealth Browser Engines (`--browser` / `--all`)

These automate public web UIs through Patchright (preferred) or Playwright
with anti-detection patches. They are slow (10–60 s each) and break when sites
redesign; treat their results as advisory.

| Engine key | Site | Notes |
| :--- | :--- | :--- |
| `gptzero` | gptzero.me | Web-UI automation; prefer the official `gptzero-api` engine |
| `copyleaks` | copyleaks.com | Requires `COPYLEAKS_API_KEY` / `COPYLEAKS_EMAIL` |
| `quillbot` | quillbot.com/ai-content-detector | Needs ≥ 80 words, ≤ 1,100 words |
| `scribbr` | scribbr.com/ai-detector | ≤ 1,100 words |
| `writer` | writer.com/ai-content-detector | Extracts human-score ratio |
| `contentdetector` | contentdetector.ai | Extracts percentage + DOM highlights |
| `isgen` | isgen.ai | Simple percentage extraction |

**Browser discovery order** (all engines): `AIDETECT_CHROME_PATH` env var →
explicit `executable_path` → well-known macOS/Linux/Windows install locations
→ `PATH` lookup → Patchright/Playwright bundled Chromium.

Install browser drivers with: `pip install "ai-detector-cli[browser]"` then
`patchright install chromium` (or use any locally installed Chrome/Edge/Brave).

---

## Local Statistical Engines (offline, < 5 ms each)

| Engine key | Model | Weight | Signal |
| :--- | :--- | :--- | :--- |
| `gltr` | GLTR token-rank distribution (Gehrmann et al., 2019) | 0.15 | % of top-100 words vs. rare long-tail tokens. AI text: top-100 > 68% and rare < 15% |
| `burstiness` | Sentence-length dispersion (σ/μ) | 0.20 | AI cadence is flat: ratio < 0.30 ⇒ ~90% AI; > 0.58 ⇒ ~5% |
| `perplexity` | Vocabulary entropy + formality | 0.15 | Low entropy + no contractions + formulaic openers ⇒ AI |
| `lexicon` | PubMed/arXiv AI-vocabulary tells | 0.15 | Buzzwords (*delve, tapestry, multifaceted...*), em dashes, rule-of-three lists, formulaic transitions |

These run fully offline, never send data anywhere, and always produce results
— they are the fallback tier when cloud engines are unreachable.

---

## Consensus Formula

```
consensus = Σ(engine_ai_pct × engine_weight) / Σ(engine_weight)   [available engines only]
```

Verdict bands: < 20% human · 20–45% low · 45–70% elevated · > 70% critical.
Exit code is `1` when consensus exceeds `--threshold` (default 30).

Sentence-level flags now come from ZeroGPT, Sapling, QuillBot, GPTZero API,
Winston and Pangram (when available); each cloud flag adds to that sentence's
risk score with the same precedence as before.
