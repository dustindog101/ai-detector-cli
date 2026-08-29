"""
Base engine interface for AI Detector.
"""

from abc import ABC, abstractmethod
from typing import List
from ..models import EngineResult

class BaseEngine(ABC):
    name: str = "BaseEngine"
    weight: float = 1.0

    @abstractmethod
    def analyze(self, text: str, sentences: List[str], words: List[str]) -> EngineResult:
        """Analyzes text and returns an EngineResult."""
        pass
