"""
Engines package initialization.
Exports all live public online GPT detectors and local statistical engines.
"""

from .base import BaseEngine
from .zerogpt_engine import ZeroGPTEngine
from .sapling_engine import SaplingEngine
from .contentdetector_engine import ContentDetectorEngine
from .quillbot_engine import QuillBotEngine
from .scribbr_engine import ScribbrEngine
from .writer_engine import WriterEngine
from .gltr_engine import GLTREngine
from .burstiness_engine import BurstinessEngine
from .perplexity_engine import PerplexityEngine
from .lexicon_engine import LexiconEngine

# Top 5 Public Online GPT Detectors (HTTP & Playwright)
LIVE_WEB_ENGINES = [
    ZeroGPTEngine(),
    SaplingEngine(),
    ContentDetectorEngine(),
    QuillBotEngine(),
    ScribbrEngine()
]

# Local Statistical & Stylometric Engines
LOCAL_ENGINES = [
    GLTREngine(),
    BurstinessEngine(),
    PerplexityEngine(),
    LexiconEngine()
]

# Full Suite of All 9 Detection Engines
ALL_ENGINES = LIVE_WEB_ENGINES + LOCAL_ENGINES
