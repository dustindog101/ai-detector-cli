"""
Engine 5: PubMed/arXiv AI Lexicon & Syntactic Tell Classifier
Audits for overrepresented AI vocabulary, formulaic transitions, em dashes, and tripartite lists.
"""

import re
from typing import List, Dict, Any
from .base import BaseEngine
from ..models import EngineResult

BANNED_WORDS = {
    "delve", "delves", "delving", "delved",
    "underscore", "underscores", "underscoring", "underscored",
    "foster", "fosters", "fostering", "fostered",
    "leverage", "leverages", "leveraging", "leveraged",
    "facilitate", "facilitates", "facilitating", "facilitated",
    "bolster", "bolsters", "bolstering", "bolstered",
    "showcase", "showcases", "showcasing", "showcased",
    "elucidate", "elucidates", "elucidating",
    "encapsulate", "encapsulates", "encapsulating",
    "harness", "harnesses", "harnessing",
    "navigate", "navigates", "navigating",
    "tapestry", "tapestries",
    "testament",
    "realm", "realms",
    "cornerstone", "cornerstones",
    "beacon", "beacons",
    "symphony",
    "interplay",
    "paradigm", "paradigms",
    "nuance", "nuances",
    "myriad",
    "paramount",
    "pivotal",
    "crucial",
    "multifaceted",
    "intricate",
    "meticulous",
    "robust",
    "transformative",
    "invaluable",
    "quintessential",
    "indispensable",
    "seamless", "seamlessly",
    "vibrant"
}

BANNED_PHRASES = [
    r"\bit is (crucial|important|essential|worth noting|imperative) to\b",
    r"\bin today'?s (fast-paced|digital|interconnected|modern) (world|landscape|era|society)\b",
    r"\ba testament to\b",
    r"\bplays a (crucial|pivotal|vital|key) role\b",
    r"\brich tapestry\b",
    r"\bin summary\b",
    r"\bin conclusion\b",
    r"\bfurthermore\b",
    r"\bmoreover\b",
    r"\badditionally\b",
    r"\bconsequently\b",
    r"\bultimately\b",
    r"\bgreat post,? i really (enjoyed|appreciated)\b",
    r"\bi completely agree with your point about\b"
]

class LexiconEngine(BaseEngine):
    name = "PubMed AI Lexicon & Tells"
    weight = 0.15

    def analyze(self, text: str, sentences: List[str], words: List[str]) -> EngineResult:
        found_buzzwords = [w for w in words if w in BANNED_WORDS]
        found_phrases = []
        for pattern in BANNED_PHRASES:
            if re.search(pattern, text, re.IGNORECASE):
                found_phrases.append(pattern)

        em_dash_count = len(re.findall(r'[—–]|--', text))
        semicolon_count = text.count(';')
        tripartite_matches = re.findall(r'(\b\w+\b,\s+\b\w+\b,?\s+and\s+\b\w+\b)', text, re.IGNORECASE)

        risk_score = 0
        risk_score += len(found_buzzwords) * 15
        risk_score += len(found_phrases) * 20
        risk_score += em_dash_count * 15
        risk_score += len(tripartite_matches) * 15

        ai_prob = min(99.0, max(0.0, float(risk_score)))
        verdict = "AI" if ai_prob > 50.0 else ("HUMAN" if ai_prob < 20.0 else "MIXED")

        return EngineResult(
            engine_name=self.name,
            available=True,
            ai_percentage=round(ai_prob, 1),
            human_percentage=round(100.0 - ai_prob, 1),
            verdict=verdict,
            weight=self.weight,
            details={
                "buzzword_count": len(found_buzzwords),
                "buzzwords_found": list(set(found_buzzwords)),
                "formulaic_phrases_count": len(found_phrases),
                "em_dash_count": em_dash_count,
                "semicolon_count": semicolon_count,
                "tripartite_lists_count": len(tripartite_matches)
            }
        )
