"""
Engines package initialization.
Exports all fast HTTP engines, local statistical models, premium key-based
API engines, and stealth Patchright/Playwright browser engines.

Activation model:
- Live HTTP + Local engines always run (default suite).
- Premium key-based engines auto-join the live suite as soon as their API key
  environment variable is present (GPTZERO_API_KEY, WINSTON_API_KEY,
  ORIGINALITY_API_KEY, PANGRAM_API_KEY, DETECTING_AI_API_KEY).
- Binoculars joins the local suite when AIDETECT_BINOCULARS=1 and the
  [binoculars] extra is installed. It can always be requested explicitly via
  --engines binoculars.
"""

from .base import BaseEngine
from .zerogpt_engine import ZeroGPTEngine
from .sapling_engine import SaplingEngine
from .gltr_engine import GLTREngine
from .burstiness_engine import BurstinessEngine
from .perplexity_engine import PerplexityEngine
from .lexicon_engine import LexiconEngine
from .gptzero_engine import GPTZeroEngine
from .copyleaks_engine import CopyLeaksEngine
from .quillbot_engine import QuillBotEngine
from .scribbr_engine import ScribbrEngine
from .writer_engine import WriterEngine
from .contentdetector_engine import ContentDetectorEngine
from .isgen_engine import IsGenEngine
from .grammarly_engine import GrammarlyEngine
from .zerogptcom_engine import ZeroGPTComEngine
from .gptzero_api_engine import GPTZeroApiEngine
from .winston_engine import WinstonEngine
from .originality_engine import OriginalityEngine
from .pangram_engine import PangramEngine
from .detectingai_engine import DetectingAIEngine
from .binoculars_engine import BinocularsEngine

__all__ = [
    "BaseEngine",
    "ZeroGPTEngine",
    "SaplingEngine",
    "GLTREngine",
    "BurstinessEngine",
    "PerplexityEngine",
    "LexiconEngine",
    "GPTZeroEngine",
    "CopyLeaksEngine",
    "QuillBotEngine",
    "ScribbrEngine",
    "WriterEngine",
    "ContentDetectorEngine",
    "IsGenEngine",
    "GrammarlyEngine",
    "ZeroGPTComEngine",
    "GPTZeroApiEngine",
    "WinstonEngine",
    "OriginalityEngine",
    "PangramEngine",
    "DetectingAIEngine",
    "BinocularsEngine",
    "CORE_HTTP_ENGINES",
    "PREMIUM_KEY_ENGINES",
    "ACTIVE_KEY_ENGINES",
    "LOCAL_ENGINES",
    "LIVE_HTTP_ENGINES",
    "DEFAULT_ENGINES",
    "BROWSER_ENGINES",
    "ALL_ENGINES",
    "LIVE_WEB_ENGINES",
    "BINOCULARS_ACTIVE",
]


def _engine_key(engine) -> str:
    override = getattr(engine, "key", None)
    if override:
        return override
    return engine.__class__.__name__.lower().replace("engine", "")


# Blazing-Fast Direct HTTP Public Cloud Engines (<0.4s)
CORE_HTTP_ENGINES = [
    ZeroGPTEngine(),
    SaplingEngine()
]

# Premium key-based engines: registered always, activated automatically when
# their API key is configured. Request them explicitly with --engines <key>.
PREMIUM_KEY_ENGINES = [
    GPTZeroApiEngine(),
    WinstonEngine(),
    OriginalityEngine(),
    PangramEngine(),
    DetectingAIEngine(),
]

ACTIVE_KEY_ENGINES = [e for e in PREMIUM_KEY_ENGINES if e.is_configured()]

# Local Statistical & Stylometric Engines (<0.005s)
LOCAL_ENGINES = [
    GLTREngine(),
    BurstinessEngine(),
    PerplexityEngine(),
    LexiconEngine()
]

_BINOCULARS_ENGINE = BinocularsEngine()
BINOCULARS_ACTIVE = _BINOCULARS_ENGINE.is_configured()
if BINOCULARS_ACTIVE:
    LOCAL_ENGINES = LOCAL_ENGINES + [_BINOCULARS_ENGINE]

# Live HTTP suite = core cloud engines + any configured premium engines.
LIVE_HTTP_ENGINES = CORE_HTTP_ENGINES + ACTIVE_KEY_ENGINES

# Default High-Speed Engine Suite -> Runs in < 0.5s (without premium keys).
DEFAULT_ENGINES = LIVE_HTTP_ENGINES + LOCAL_ENGINES

# Stealth Browser / Patchright Engines (On-Demand via --browser / --all)
BROWSER_ENGINES = [
    GPTZeroEngine(),
    CopyLeaksEngine(),
    QuillBotEngine(),
    ScribbrEngine(),
    WriterEngine(),
    ContentDetectorEngine(),
    IsGenEngine(),
    GrammarlyEngine(),
    ZeroGPTComEngine(),
]


def _dedupe(engines):
    seen = set()
    unique = []
    for e in engines:
        k = _engine_key(e)
        if k not in seen:
            seen.add(k)
            unique.append(e)
    return unique


# Full registry: every engine the CLI can run, deduplicated. Premium engines
# and Binoculars appear even when inactive so `--engines <key>` can target
# them directly and `--list-engines` can advertise them.
ALL_ENGINES = _dedupe(DEFAULT_ENGINES + BROWSER_ENGINES + PREMIUM_KEY_ENGINES + [_BINOCULARS_ENGINE])
LIVE_WEB_ENGINES = LIVE_HTTP_ENGINES + BROWSER_ENGINES
