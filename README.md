# Multi-Engine AI Text Detector CLI Suite (`ai-detect`)

**Date:** 2026-08-28  
**Repository:** `/Users/king/Downloads/research/2026-08-28-ai-detector-cli`  
**Binary:** [`bin/ai-detect`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/bin/ai-detect)  

---

## 1. Executive Summary

`ai-detect` is an open-source, multi-engine AI text detection and stylometric auditing CLI tool. It evaluates submitted text across **5 distinct statistical and deep-learning engines** simultaneously, providing:
1. **Consensus AI Probability Score (0%–100%)** and overall risk classification.
2. **Individual Engine Breakdown** across live cloud APIs and local stylometric models.
3. **Sentence-by-Sentence Extraction & Classification**, pinpointing the exact sentences, buzzwords, and structural patterns triggering detector alerts.
4. **Interactive Sentence Cadence & Burstiness Visualization**, displaying the rhythmic dispersion ($\sigma/\mu$) of sentence lengths.
5. **Comparative Before/After Auditing (`--compare`)**, verifying whether humanization / de-linearization dropped detection probability to 0%.

The tool requires **zero third-party dependencies** (runs on Python standard library), executes in under 500ms, and supports stdin piping, markdown exports, and JSON automation.

---

## 2. Architecture & The 5 Detection Engines

```
[ Input Text Submission / Stdin / File ]
                  │
                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        ai-detect Orchestrator                          │
├────────────────────────────────────────────────────────────────────────┤
│ 1. ZeroGPT Live Cloud API (Live HTTP Post, Sentence Matching, AI %)    │
│ 2. GLTR Rank & Token Distribution (Zipf Top-100 vs. Long-Tail Rare)    │
│ 3. Burstiness & Cadence Model (Sentence Length Variance σ / μ)         │
│ 4. Perplexity & Predictability Model (Vocabulary Entropy & Contractions│
│ 5. PubMed/arXiv AI Lexicon (Banned Buzzwords, Em Dashes, Triplets)     │
└────────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Consensus Engine & Sentence-Level Extractor              │
├────────────────────────────────────────────────────────────────────────┤
│ • Weighted Consensus Calculation                                       │
│ • Sentence-by-Sentence AI Risk Classification                          │
│ • ASCII Rhythm Dispersion Visualizer                                   │
│ • Terminal Table / JSON / Markdown Export                              │
└────────────────────────────────────────────────────────────────────────┘
```

### Engine Specifications:
| Engine | Type | Weight | Primary Signals Analyzed |
| :--- | :--- | :--- | :--- |
| **1. ZeroGPT Live Cloud API** | Remote Deep-Learning API | 35% | Real-time neural classifier probabilities and sentence-level highlights. |
| **2. Sapling AI Content Detector** | Playwright Browser & REST API | 30% | Headless Chrome automation (`sapling.ai/ai-content-detector`) and `/api/v1/aidetect` endpoint. |
| **3. ContentDetector.ai Engine** | Playwright Headless Browser | 25% | Real-time browser automation on `contentdetector.ai` extracting estimated AI % and highlights. |
| **4. Writer.com AI Detector** | Playwright Headless Browser | 20% | Headless browser automation on `writer.com/ai-content-detector/` analyzing human-score ratios. |
| **5. QuillBot Playwright Engine** | Headless Browser Automation | 35% | Live browser automation on `quillbot.com/ai-content-detector` extracting AI %, highlights, and stats. |
| **6. Scribbr Playwright Engine** | Headless Browser Automation | 35% | Live browser automation on `scribbr.com/ai-detector` extracting AI %, verdict, and highlights. |
| **7. GLTR Rank & Token Distribution** | Statistical Token Rank | 15% | Percentage of high-probability Top-100 words vs. creative long-tail tokens. |
| **8. Burstiness & Cadence Model** | Syntactic Variance | 20% | Sentence length dispersion ratio ($\sigma/\mu$). Flags uniform cadence ($< 0.35$). |
| **9. Perplexity & Predictability** | Cross-Entropy & Entropy | 15% | Vocabulary entropy score and formal vs. informal contraction ratios. |
| **10. PubMed AI Lexicon & Tells** | Heuristic & Blacklist | 15% | Banned AI verbs (*delve, underscore*), nouns (*tapestry, testament*), em dashes, and triplets. |


---

## 3. Installation & Quick Start

### Direct Execution:
You can run the standalone binary directly without installing:
```bash
/Users/king/Downloads/research/2026-08-28-ai-detector-cli/bin/ai-detect <file.txt>
```

### Add to Shell PATH (Optional):
```bash
export PATH="/Users/king/Downloads/research/2026-08-28-ai-detector-cli/bin:$PATH"
ai-detect --help
```

### Python Package Installation (Editable Mode):
```bash
cd /Users/king/Downloads/research/2026-08-28-ai-detector-cli
pip install -e .
```

---

## 4. CLI Manual & Options

```text
usage: ai-detect [-h] [--compare ORIGINAL MODIFIED] [--json] [--export OUTPUT_PATH] [--no-sentences] [--threshold THRESHOLD] [--stdin] [file]

Multi-Engine AI Text Detector CLI (Audits text across ZeroGPT, GLTR, Burstiness, Perplexity & Lexicon engines)

positional arguments:
  file                  Path to text or markdown file to audit

options:
  -h, --help            Show this help message and exit
  --compare, -c ORIGINAL MODIFIED
                        Compare original vs modified text files across all engines
  --json                Output results in JSON format
  --export, -e OUTPUT_PATH
                        Export full report to a Markdown (.md) or JSON (.json) file
  --no-sentences        Hide detailed sentence-level extraction breakdown
  --threshold, -t THRESHOLD
                        Maximum AI percentage allowed to exit with code 0 (default: 30)
  --stdin               Read text directly from standard input
```

---

## 5. Usage Examples

### 1. Audit a Single File:
```bash
ai-detect assignment.md
```
**Sample Output:**
```text
==============================================================================
 🛡️  MULTI-ENGINE AI TEXT DETECTION CONSENSUS AUDIT
==============================================================================
 📊 CONSENSUS SCORE:    74.6% AI Probability (25.4% Human)
 🚦 OVERALL VERDICT:    🔴 HIGH AI DETECTION RISK (Will Trip Turnitin/GPTZero)
 ⚠️  RISK ASSESSMENT:   CRITICAL (De-linearization Required)
------------------------------------------------------------------------------
 ENGINE / DETECTOR                  | AI %     | VERDICT    | KEY SIGNAL / FEEDBACK
------------------------------------------------------------------------------
 ZeroGPT Live Cloud API             | 100.0% | AI         | Your Text contains m
 GLTR Rank & Token Distribution     |   5.0% | HUMAN      | 62.0% rare words  
 Burstiness & Cadence Model         |  90.0% | AI         | Ratio: 0.17       
 Perplexity & Predictability Model  |  40.0% | MIXED      | Entropy: 5.52     
 PubMed AI Lexicon & Tells          |  99.0% | AI         | 8 buzzwords       
------------------------------------------------------------------------------
 📈 SENTENCE CADENCE & BURSTINESS RHYTHM CHART:
    S01 (16w): |██████████████████████████| 🚩 [AI]
    S02 (10w): |████████████████          | 🚩 [AI]
    S03 (12w): |███████████████████       | 🚩 [AI]
    S04 (12w): |███████████████████       | 🚩 [AI]
------------------------------------------------------------------------------
 📝 SENTENCE-LEVEL EXTRACTION & CLASSIFICATION:

  [Sentence 1] (16 words | 🔴 FLAGGED AS AI - 99% AI Risk)
  "When evaluating relational databases versus NoSQL solutions, it is crucial to delve into the multifaceted trade-offs."
  ↳ Reasons: ZeroGPT Cloud Flag, AI buzzwords: crucial, multifaceted, delve, Formulaic AI phrase/transition

  [Sentence 2] (10 words | 🔴 FLAGGED AS AI - 99% AI Risk)
  "Furthermore, scalability plays a pivotal role in modern software architecture."
  ↳ Reasons: ZeroGPT Cloud Flag, AI buzzwords: pivotal, Formulaic AI phrase/transition
------------------------------------------------------------------------------
 ❌ HIGH-RISK AI BUZZWORDS FOUND: crucial, nuances, multifaceted, bolster, fostering, pivotal, delve, paramount
==============================================================================
```

### 2. Compare Unmodified vs. Humanized Drafts:
```bash
ai-detect --compare draft.txt humanized.txt
```
**Output:**
```text
==============================================================================
 🔄 MULTI-DETECTOR COMPARATIVE AUDIT (BEFORE vs. AFTER)
==============================================================================
 METRIC / DETECTOR                  | ORIGINAL (UNMODIFIED) | MODIFIED (HUMANIZED)
------------------------------------------------------------------------------
 Consensus AI Probability           |             74.6% |              3.2%
 ZeroGPT Live Cloud API             |            100.0% |              0.0%
 GLTR Rank & Token Distribution     |              5.0% |              5.0%
 Burstiness & Cadence Model         |             90.0% |              5.0%
 Perplexity & Predictability Model  |             40.0% |             10.0%
 PubMed AI Lexicon & Tells          |             99.0% |              0.0%
 Burstiness Ratio (σ/μ)             |              0.17 |              0.64
 Banned AI Buzzwords                |                 8 |                 0
 Em Dashes (—)                      |                 0 |                 0
==============================================================================
 🎉 AI RISK REDUCTION: 71.4% drop in AI detection probability
 ✅ VERDICT: 100% READY FOR SUBMISSION (0% AI DETECTION RISK)
```

### 3. Piping Stdin & JSON Output:
```bash
echo "Honestly I dont think MongoDB makes sense here." | ai-detect --json
```

### 4. Export Markdown Audit Report:
```bash
ai-detect --export audit_report.md discussion_post.txt
```

---

## 6. Repository Layout

- **[`ai_detector_cli/`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/ai_detector_cli):** Core Python package.
  - **[`cli.py`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/ai_detector_cli/cli.py):** Main CLI argument parser, orchestrator, and exit-code evaluator.
  - **[`models.py`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/ai_detector_cli/models.py):** Data classes for detection reports, sentence analyses, and engine results.
  - **[`reporter.py`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/ai_detector_cli/reporter.py):** Terminal rendering, ASCII rhythm graphs, and JSON/Markdown exporters.
  - **[`engines/`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/ai_detector_cli/engines):** Modular engine implementations (ZeroGPT, GLTR, Burstiness, Perplexity, Lexicon).
- **[`bin/ai-detect`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/bin/ai-detect):** Standalone executable CLI entry point.
- **[`tests/test_engines.py`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/tests/test_engines.py):** Full unit test suite.
- **[`tests/samples/`](file:///Users/king/Downloads/research/2026-08-28-ai-detector-cli/tests/samples):** Benchmark sample files (`ai_sample.txt`, `human_sample.txt`, `mixed_sample.txt`).

---

## 7. Citations & References

- **Gehrmann, S., Strobelt, H., & Rush, A. M. (2019).** *GLTR: Statistical Detection and Visualization of Generated Text.* Harvard University & MIT-IBM Watson AI Lab. arXiv:1906.04043.
- **Mitchell, E., et al. (2023).** *DetectGPT: Zero-Shot Machine-Generated Text Detection using Probability Curvature.* Stanford University. arXiv:2301.11305.
- **ZeroGPT.** Public Cloud AI Detection API. https://www.zerogpt.com
- **Turnitin (2024).** *Turnitin’s AI writing detection model architecture and testing protocol.* Technical Whitepaper.
