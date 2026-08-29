"""
Data models for AI Detector CLI.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class SentenceAnalysis:
    index: int
    text: str
    word_count: int
    ai_probability: float  # 0.0 to 100.0
    flagged: bool
    reasons: List[str] = field(default_factory=list)

@dataclass
class EngineResult:
    engine_name: str
    available: bool
    ai_percentage: float  # 0.0 to 100.0
    human_percentage: float  # 0.0 to 100.0
    verdict: str  # "HUMAN", "AI", "MIXED", "UNAVAILABLE"
    weight: float
    details: Dict[str, Any] = field(default_factory=dict)
    flagged_sentences: List[str] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class DetectionReport:
    text: str
    word_count: int
    sentence_count: int
    consensus_ai_probability: float  # 0.0 to 100.0
    consensus_human_probability: float  # 0.0 to 100.0
    consensus_verdict: str
    risk_level: str
    engines: Dict[str, EngineResult] = field(default_factory=dict)
    sentences: List[SentenceAnalysis] = field(default_factory=list)
    burstiness_ratio: float = 0.0
    mean_sentence_length: float = 0.0
    sentence_length_std_dev: float = 0.0
    banned_words_found: List[str] = field(default_factory=list)
    em_dash_count: int = 0
    semicolon_count: int = 0
    tripartite_list_count: int = 0
    # --- v2 fields ---
    source: str = "<stdin>"                # file path / "stdin" / "demo"
    degraded: bool = False                 # True when live engines fell back to local-only
    degradation_note: Optional[str] = None
    analysis_ms: float = 0.0               # wall-clock duration of the analysis
    engine_mode: str = "default"           # default | live-only | local-only | browser | all

@dataclass
class BatchEntry:
    """Result of analyzing one file in batch mode."""
    path: str
    report: DetectionReport
    error: Optional[str] = None            # set when the file could not be read

@dataclass
class BatchReport:
    """Aggregate result for --batch mode."""
    entries: List[BatchEntry] = field(default_factory=list)
    threshold: float = 30.0
    engines_mode: str = "local-only"
    elapsed_ms: float = 0.0
