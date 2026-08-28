"""
Engine 4: Perplexity & Cross-Entropy Predictability Model
Measures vocabulary entropy, n-gram repetitiveness, and formal/informal syntactic ratios.
"""

import re
import math
from typing import List, Dict, Any
from .base import BaseEngine
from ..models import EngineResult

class PerplexityEngine(BaseEngine):
    name = "Perplexity & Predictability Model"
    weight = 0.15

    def analyze(self, text: str, sentences: List[str], words: List[str]) -> EngineResult:
        if len(words) < 5:
            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=50.0,
                human_percentage=50.0,
                verdict="MIXED",
                weight=self.weight
            )

        freq_map = {}
        for w in words:
            freq_map[w] = freq_map.get(w, 0) + 1

        entropy = 0.0
        for count in freq_map.values():
            p = count / len(words)
            entropy -= p * math.log2(p)

        formal_uncontracted = len(re.findall(r'\b(do not|does not|it is|can not|cannot|will not|that is)\b', text, re.IGNORECASE))
        informal_contractions = len(re.findall(r'\b(dont|cant|isnt|arent|thats|wont|im|ive|didnt|it\'s|don\'t|can\'t)\b', text, re.IGNORECASE))

        predictability_score = 10.0
        if entropy < 4.2 and len(words) > 30:
            predictability_score += 35
        if formal_uncontracted > informal_contractions * 2 and formal_uncontracted > 1:
            predictability_score += 25
        if any(s.strip().startswith(("Furthermore", "Moreover", "Additionally", "In conclusion")) for s in sentences):
            predictability_score += 30

        ai_prob = min(95.0, max(5.0, predictability_score))
        verdict = "AI" if ai_prob > 60.0 else ("HUMAN" if ai_prob < 30.0 else "MIXED")

        return EngineResult(
            engine_name=self.name,
            available=True,
            ai_percentage=round(ai_prob, 1),
            human_percentage=round(100.0 - ai_prob, 1),
            verdict=verdict,
            weight=self.weight,
            details={
                "vocabulary_entropy": round(entropy, 2),
                "formal_uncontracted_pairs": formal_uncontracted,
                "informal_contractions": informal_contractions
            }
        )
