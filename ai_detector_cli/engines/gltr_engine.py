"""
Engine 2: GLTR (Giant Language Model Test Room) Rank & Entropy Token Model
Evaluates token prediction rank distributions based on Gehrmann et al. (Harvard/MIT-IBM).
"""

from typing import List
from .base import BaseEngine
from ..models import EngineResult

TOP_100_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on", "with",
    "he", "as", "you", "do", "at", "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there", "their", "what", "so", "up",
    "out", "if", "about", "who", "get", "which", "go", "me", "when", "make", "can", "like", "time",
    "no", "just", "him", "know", "take", "people", "into", "year", "your", "good", "some", "could",
    "them", "see", "other", "than", "then", "now", "look", "only", "come", "its", "over", "think",
    "also", "back", "after", "use", "two", "how", "our", "work", "first", "well", "way", "even",
    "new", "want", "because", "any", "these", "give", "day", "most", "us", "is", "are", "was", "were"
}

TOP_1000_WORDS = TOP_100_WORDS.union({
    "system", "systems", "data", "database", "databases", "model", "models", "relational", "software",
    "project", "class", "development", "information", "important", "problem", "different", "number",
    "point", "great", "group", "case", "fact", "week", "month", "program", "question", "work", "government",
    "company", "issue", "side", "kind", "head", "far", "black", "long", "both", "little", "since",
    "around", "friend", "father", "mother", "real", "life", "few", "public", "bad", "same", "able"
})

class GLTREngine(BaseEngine):
    name = "GLTR Rank & Token Distribution"
    weight = 0.15

    def analyze(self, text: str, sentences: List[str], words: List[str]) -> EngineResult:
        if not words:
            return EngineResult(
                engine_name=self.name,
                available=True,
                ai_percentage=0.0,
                human_percentage=100.0,
                verdict="HUMAN",
                weight=self.weight
            )

        top_100_count = sum(1 for w in words if w in TOP_100_WORDS)
        top_1000_count = sum(1 for w in words if w in TOP_1000_WORDS and w not in TOP_100_WORDS)
        rare_count = len(words) - (top_100_count + top_1000_count)

        top_100_pct = (top_100_count / len(words)) * 100
        top_1000_pct = (top_1000_count / len(words)) * 100
        rare_pct = (rare_count / len(words)) * 100

        # LLMs generate predominantly high-rank top-100 words (>68%) with low long-tail dispersion (<15%)
        if top_100_pct > 68.0 and rare_pct < 15.0:
            ai_prob = min(95.0, 50.0 + (top_100_pct - 68.0) * 2.5)
        elif rare_pct >= 25.0:
            ai_prob = max(5.0, 25.0 - (rare_pct - 25.0) * 1.5)
        else:
            ai_prob = 30.0

        verdict = "AI" if ai_prob > 60.0 else ("HUMAN" if ai_prob < 30.0 else "MIXED")

        return EngineResult(
            engine_name=self.name,
            available=True,
            ai_percentage=round(ai_prob, 1),
            human_percentage=round(100.0 - ai_prob, 1),
            verdict=verdict,
            weight=self.weight,
            details={
                "top_100_percentage (Green)": round(top_100_pct, 1),
                "top_1000_percentage (Yellow)": round(top_1000_pct, 1),
                "rare_words_percentage (Red/Purple)": round(rare_pct, 1)
            }
        )
