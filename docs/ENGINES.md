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

## Stealth Browser Engines (`--browser` / `--all`)

These automate public web UIs through Patchright (preferred) or Playwright
with anti-detection patches. They are slow (10–60 s each) and break when sites
redesign; treat their results as advisory.

| Engine key | Site | Notes |
| :--- | :--- | :--- |
| `gptzero` | gptzero.me | Requires `GPTZERO_API_KEY` env var for API mode |
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
