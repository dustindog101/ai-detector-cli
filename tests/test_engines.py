"""
Unit and integration tests for AI Detector CLI.
"""

import unittest
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ai_detector_cli.cli import analyze_text
from ai_detector_cli.engines import (
    ZeroGPTEngine,
    GLTREngine,
    BurstinessEngine,
    PerplexityEngine,
    LexiconEngine,
    QuillBotEngine,
    ScribbrEngine,
    SaplingEngine,
    ContentDetectorEngine,
    WriterEngine
)

class TestAIDetectorEngines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        samples_dir = os.path.join(current_dir, "samples")
        with open(os.path.join(samples_dir, "ai_sample.txt"), "r", encoding="utf-8") as f:
            cls.ai_text = f.read()
        with open(os.path.join(samples_dir, "human_sample.txt"), "r", encoding="utf-8") as f:
            cls.human_text = f.read()
        with open(os.path.join(samples_dir, "mixed_sample.txt"), "r", encoding="utf-8") as f:
            cls.mixed_text = f.read()

    def test_gltr_engine(self):
        eng = GLTREngine()
        res_ai = eng.analyze(self.ai_text, [self.ai_text], self.ai_text.split())
        res_hu = eng.analyze(self.human_text, [self.human_text], self.human_text.split())
        self.assertIsNotNone(res_ai.ai_percentage)
        self.assertIsNotNone(res_hu.ai_percentage)

    def test_burstiness_engine(self):
        eng = BurstinessEngine()
        res_ai = eng.analyze(self.ai_text, self.ai_text.split(". "), self.ai_text.split())
        res_hu = eng.analyze(self.human_text, self.human_text.split(". "), self.human_text.split())
        self.assertGreater(res_ai.ai_percentage, res_hu.ai_percentage)

    def test_lexicon_engine(self):
        eng = LexiconEngine()
        res_ai = eng.analyze(self.ai_text, [self.ai_text], self.ai_text.lower().split())
        res_hu = eng.analyze(self.human_text, [self.human_text], self.human_text.lower().split())
        self.assertGreater(res_ai.details["buzzword_count"], 0)
        self.assertEqual(res_hu.details["buzzword_count"], 0)

    def test_full_analysis_consensus(self):
        report_ai = analyze_text(self.ai_text, local_only=True)
        report_hu = analyze_text(self.human_text, local_only=True)

        self.assertGreater(report_ai.consensus_ai_probability, 50.0)
        self.assertLess(report_hu.consensus_ai_probability, 25.0)
        self.assertGreater(len(report_ai.sentences), 0)
        self.assertGreater(len(report_hu.sentences), 0)

    def test_sentence_extraction(self):
        report_ai = analyze_text(self.ai_text, local_only=True)
        # Verify sentences are parsed and scored individually
        self.assertEqual(len(report_ai.sentences), 4)
        for s in report_ai.sentences:
            self.assertGreaterEqual(s.ai_probability, 0.0)
            self.assertLessEqual(s.ai_probability, 100.0)

    def test_quillbot_engine_interface(self):
        eng = QuillBotEngine()
        self.assertEqual(eng.name, "QuillBot AI Detector")
        self.assertEqual(eng.weight, 0.35)
        # Empty input handling
        res_empty = eng.analyze("")
        self.assertFalse(res_empty.available)
        self.assertEqual(res_empty.verdict, "UNAVAILABLE")

    def test_scribbr_engine_interface(self):
        eng = ScribbrEngine()
        self.assertEqual(eng.name, "Scribbr AI Detector")
        self.assertEqual(eng.weight, 0.35)
        # Empty input handling
        res_empty = eng.analyze("")
        self.assertFalse(res_empty.available)
        self.assertEqual(res_empty.verdict, "UNAVAILABLE")

    def test_sapling_engine_interface(self):
        eng = SaplingEngine()
        self.assertEqual(eng.name, "Sapling AI Detector")
        self.assertEqual(eng.weight, 0.30)
        # Empty input handling
        res_empty = eng.analyze("")
        self.assertFalse(res_empty.available)
        self.assertEqual(res_empty.verdict, "UNAVAILABLE")

    def test_contentdetector_engine_interface(self):
        eng = ContentDetectorEngine()
        self.assertEqual(eng.name, "ContentDetector.ai")
        self.assertEqual(eng.weight, 0.25)
        # Empty input handling
        res_empty = eng.analyze("")
        self.assertFalse(res_empty.available)
        self.assertEqual(res_empty.verdict, "UNAVAILABLE")

    def test_writer_engine_interface(self):
        eng = WriterEngine()
        self.assertEqual(eng.name, "Writer.com AI Detector")
        self.assertEqual(eng.weight, 0.25)
        # Empty input handling
        res_empty = eng.analyze("")
        self.assertFalse(res_empty.available)
        self.assertEqual(res_empty.verdict, "UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()

