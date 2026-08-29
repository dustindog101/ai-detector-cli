"""
AI Detector CLI Package
Multi-engine AI text detection with live cloud APIs, stealth browser engines,
and local statistical models.
"""

__version__ = "2.0.0"

from .cli import analyze_text, run_batch, main, load_document
from .models import DetectionReport, EngineResult, SentenceAnalysis, BatchEntry, BatchReport
from .http_client import configure_timeout, close_all_connections

__all__ = [
    "analyze_text",
    "run_batch",
    "main",
    "load_document",
    "DetectionReport",
    "EngineResult",
    "SentenceAnalysis",
    "BatchEntry",
    "BatchReport",
    "configure_timeout",
    "close_all_connections",
    "__version__",
]
