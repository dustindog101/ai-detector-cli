"""
AI Detector CLI Package
"""

__version__ = "1.0.0"

from .cli import analyze_text, main
from .models import DetectionReport, EngineResult, SentenceAnalysis
