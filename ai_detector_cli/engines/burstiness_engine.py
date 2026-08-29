"""
Engine 3: Burstiness & Cadence Dispersion Engine
Calculates sentence-length variance, standard deviation, and rhythmic burstiness ratio (sigma / mu).
"""

import re
import math
from typing import List
from .base import BaseEngine
from ..models import EngineResult

class BurstinessEngine(BaseEngine):
    name = "Burstiness & Cadence Model"
    weight = 0.20

    def analyze(self, text: str, sentences: List[str], words: List[str]) -> EngineResult:
        if not sentences:
            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=50.0,
                human_percentage=50.0,
                verdict="MIXED",
                weight=self.weight
            )

        lengths = [len(re.findall(r'\b[A-Za-z0-9\'-]+\b', s)) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((length - mean_len) ** 2 for length in lengths) / len(lengths)
        std_dev = math.sqrt(variance)
        burstiness = (std_dev / mean_len) if mean_len > 0 else 0

        # Burstiness thresholds:
        # < 0.30: Flat cadence (High AI probability ~90%)
        # 0.30 - 0.45: Low variance (~70%)
        # 0.45 - 0.58: Moderate variance (~35%)
        # > 0.58: High human variance (~5%)
        if burstiness < 0.30:
            ai_prob = 90.0
        elif burstiness < 0.45:
            ai_prob = 70.0
        elif burstiness < 0.58:
            ai_prob = 35.0
        else:
            ai_prob = 5.0

        verdict = "AI" if ai_prob > 60.0 else ("HUMAN" if ai_prob < 30.0 else "MIXED")

        return EngineResult(
            engine_name=self.name,
            available=True,
            ai_percentage=round(ai_prob, 1),
            human_percentage=round(100.0 - ai_prob, 1),
            verdict=verdict,
            weight=self.weight,
            details={
                "mean_sentence_length": round(mean_len, 2),
                "sentence_length_std_dev": round(std_dev, 2),
                "burstiness_ratio (sigma / mu)": round(burstiness, 2),
                "sentence_lengths": lengths
            }
        )
