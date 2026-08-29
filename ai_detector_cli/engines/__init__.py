"""
Engines package initialization.
Exports all fast HTTP engines, local statistical models, and stealth Patchright/Playwright browser engines.
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

# Blazing-Fast Direct HTTP Public Cloud Engines (<0.4s)
LIVE_HTTP_ENGINES = [
    ZeroGPTEngine(),
    SaplingEngine()
]

# Local Statistical & Stylometric Engines (<0.005s)
LOCAL_ENGINES = [
    GLTREngine(),
    BurstinessEngine(),
    PerplexityEngine(),
    LexiconEngine()
]

# Default High-Speed Engine Suite (ZeroGPT + Sapling HTTP + 4 Statistical Engines) -> Runs in < 0.5s!
DEFAULT_ENGINES = LIVE_HTTP_ENGINES + LOCAL_ENGINES

# Stealth Browser / Patchright Engines (On-Demand via --browser / --all)
BROWSER_ENGINES = [
    GPTZeroEngine(),
    CopyLeaksEngine(),
    QuillBotEngine(),
    ScribbrEngine(),
    WriterEngine(),
    ContentDetectorEngine(),
    IsGenEngine()
]

# Full Suite of All 13 Detection Engines
ALL_ENGINES = DEFAULT_ENGINES + BROWSER_ENGINES
LIVE_WEB_ENGINES = LIVE_HTTP_ENGINES + BROWSER_ENGINES
