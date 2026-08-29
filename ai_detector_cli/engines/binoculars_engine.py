"""
Engine: Binoculars (local neural zero-shot detector, opt-in)
Implementation of "Spotting LLMs With Binoculars" (Hans et al., ICML 2024,
https://arxiv.org/abs/2401.12070) - a zero-shot detector that needs no
training data and no API. It scores text with the ratio of two signal from a
pair of language models:

    binoculars_score = perplexity(performer) / cross-perplexity(observer -> performer)

Low scores indicate machine-generated text. The official threshold is
0.9013310719761093 (reported 0.93+ AUROC on multiple benchmarks, strong against
paraphrasing attacks).

Requirements (heavy, opt-in):
    pip install "ai-detector-cli[binoculars]"
    (installs torch + transformers; models are downloaded on first use,
    ~13 GB for the default Falcon-7B pair)

Environment:
    AIDETECT_BINOCULARS=1                      - auto-include in default/local runs
    AIDETECT_BINOCULARS_OBSERVER_MODEL=name    - default tiiuae/falcon-7b
    AIDETECT_BINOCULARS_PERFORMER_MODEL=name   - default tiiuae/falcon-7b-instruct
    AIDETECT_BINOCULARS_DEVICE=cpu|cuda|mps    - default: auto

Low-RAM tip: any tokenizer-compatible model pair works, e.g.
    AIDETECT_BINOCULARS_OBSERVER_MODEL=TinyLlama/TinyLlama-1.1B-intermediate-step-1431k-3T
    AIDETECT_BINOCULARS_PERFORMER_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0
(accuracy is reduced versus Falcon-7B but memory drops to ~3 GB).
"""

import os
import threading
from typing import List

from .base import BaseEngine
from ..models import EngineResult

try:  # fast structural check without importing the heavy modules
    from importlib.util import find_spec as _find_spec
    _TORCH_SPEC = _find_spec("torch")
    _TRANSFORMERS_SPEC = _find_spec("transformers")
    DEPS_AVAILABLE = _TORCH_SPEC is not None and _TRANSFORMERS_SPEC is not None
except Exception:  # pragma: no cover - importlib always present in practice
    DEPS_AVAILABLE = False

MAX_BINOCULARS_CHARS = 8000
BINOCULARS_THRESHOLD = 0.9013310719761093  # official from the paper repo
DEFAULT_OBSERVER = "tiiuae/falcon-7b"
DEFAULT_PERFORMER = "tiiuae/falcon-7b-instruct"

_TRUTHY = ("1", "true", "yes", "on")


def _env_flag_enabled() -> bool:
    return os.environ.get("AIDETECT_BINOCULARS", "").strip().lower() in _TRUTHY


class BinocularsEngine(BaseEngine):
    name = "Binoculars (Local Neural)"
    key = "binoculars"
    weight = 0.50

    def __init__(self):
        self._loaded = False
        self._load_lock = threading.Lock()
        self._observer_model = None
        self._performer_model = None
        self._tokenizer = None
        self._torch = None

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @staticmethod
    def deps_available() -> bool:
        return DEPS_AVAILABLE

    def is_configured(self) -> bool:
        """Auto-inclusion gate: env flag ON and heavy deps importable."""
        return _env_flag_enabled() and DEPS_AVAILABLE

    # ------------------------------------------------------------------
    # Lazy model loading (once per process, thread-safe)
    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:
                return
            if not DEPS_AVAILABLE:
                raise RuntimeError(
                    "Binoculars requires torch + transformers: "
                    'pip install "ai-detector-cli[binoculars]"'
                )
            import torch  # noqa: WPS433 (heavy import deferred on purpose)
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._torch = torch
            observer_name = os.environ.get("AIDETECT_BINOCULARS_OBSERVER_MODEL", DEFAULT_OBSERVER)
            performer_name = os.environ.get("AIDETECT_BINOCULARS_PERFORMER_MODEL", DEFAULT_PERFORMER)

            device_pref = os.environ.get("AIDETECT_BINOCULARS_DEVICE", "").strip().lower()
            if device_pref in ("cpu", "cuda", "mps"):
                device = device_pref
            else:
                device = "cuda" if torch.cuda.is_available() else "cpu"

            dtype = torch.float16 if device == "cuda" else torch.float32
            self._observer_model = AutoModelForCausalLM.from_pretrained(
                observer_name, torch_dtype=dtype
            ).to(device).eval()
            self._performer_model = AutoModelForCausalLM.from_pretrained(
                performer_name, torch_dtype=dtype
            ).to(device).eval()
            self._tokenizer = AutoTokenizer.from_pretrained(observer_name)
            if not self._tokenizer.pad_token:
                self._tokenizer.pad_token = self._tokenizer.eos_token
            self._device = device
            self._loaded = True

    # ------------------------------------------------------------------
    # Core math (faithful to the official implementation, MIT licensed)
    # ------------------------------------------------------------------
    def _score_text(self, text: str) -> float:
        torch = self._torch
        encodings = self._tokenizer(
            text, return_tensors="pt", return_token_type_ids=False, truncation=True,
        ).to(self._device)
        with torch.no_grad():
            observer_logits = self._observer_model(**encodings).logits
            performer_logits = self._performer_model(**encodings).logits

        # Perplexity: exp of cross-entropy between performer predictions and true tokens.
        shifted_logits = performer_logits[..., :-1, :].transpose(-1, -2)
        shifted_labels = encodings.input_ids[..., 1:]
        ppl = torch.exp(
            torch.nn.functional.cross_entropy(shifted_logits, shifted_labels, reduction="mean")
        )

        # Cross-perplexity: how surprised the performer is at the observer's distribution.
        softmax_observer = torch.nn.functional.softmax(observer_logits[..., :-1, :], dim=-1)
        logsoftmax_performer = torch.nn.functional.log_softmax(performer_logits[..., :-1, :], dim=-1)
        x_ppl = -(softmax_observer * logsoftmax_performer).sum(dim=-1).mean()

        score = (ppl / x_ppl).item()
        return float(score)

    @staticmethod
    def score_to_ai_pct(score: float) -> float:
        """
        Map the raw binoculars score onto a 0-100 AI percentage.

        Calibrated so that the official decision threshold (0.9013) lands at
        ~14% AI (borderline-human), 0.60 maps to 100% and >= 0.95 maps to 0%.
        """
        mapped = 100.0 * (0.95 - score) / (0.95 - 0.60)
        return min(99.9, max(0.0, mapped))

    # ------------------------------------------------------------------
    # BaseEngine interface
    # ------------------------------------------------------------------
    def analyze(self, text: str, sentences: List[str] = None, words: List[str] = None) -> EngineResult:
        if not text or not text.strip():
            return self._unavailable("Input text is empty")
        if not DEPS_AVAILABLE:
            return self._unavailable(
                'Binoculars requires torch + transformers: pip install "ai-detector-cli[binoculars]"'
            )

        query_text = text[:MAX_BINOCULARS_CHARS]
        is_truncated = len(text) > MAX_BINOCULARS_CHARS

        try:
            self._ensure_loaded()
            score = self._score_text(query_text)
            ai_pct = self.score_to_ai_pct(score)
            verdict = "HUMAN" if score > BINOCULARS_THRESHOLD else "AI"
            if abs(score - BINOCULARS_THRESHOLD) < 0.01:
                verdict = "MIXED"

            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=round(ai_pct, 1),
                human_percentage=round(100.0 - ai_pct, 1),
                verdict=verdict,
                weight=self.weight,
                details={
                    "binoculars_score": round(score, 5),
                    "threshold": BINOCULARS_THRESHOLD,
                    "device": getattr(self, "_device", "unknown"),
                    "observer_model": os.environ.get(
                        "AIDETECT_BINOCULARS_OBSERVER_MODEL", DEFAULT_OBSERVER
                    ),
                    "performer_model": os.environ.get(
                        "AIDETECT_BINOCULARS_PERFORMER_MODEL", DEFAULT_PERFORMER
                    ),
                    "truncated": is_truncated,
                },
            )
        except Exception as e:
            return self._unavailable(str(e))

    @staticmethod
    def _unavailable(error: str) -> EngineResult:
        return EngineResult(
            engine_name=BinocularsEngine.name,
            available=False,
            ai_percentage=0.0,
            human_percentage=100.0,
            verdict="UNAVAILABLE",
            weight=0.0,
            error=error,
        )
