"""
Offline-safe tests for the premium key-based engines, the local Binoculars
neural engine, and the v2.1 registry/selection wiring. All network access is
mocked so the suite runs in CI without keys.
"""

import json
import os
import unittest
from unittest import mock

from ai_detector_cli.models import EngineResult
from ai_detector_cli.cli import analyze_text, select_engines, engine_key
from ai_detector_cli.engines import (
    ALL_ENGINES,
    LIVE_HTTP_ENGINES,
    LOCAL_ENGINES,
    PREMIUM_KEY_ENGINES,
    BINOCULARS_ACTIVE,
)
from ai_detector_cli.engines.gptzero_api_engine import GPTZeroApiEngine
from ai_detector_cli.engines.winston_engine import WinstonEngine
from ai_detector_cli.engines.originality_engine import OriginalityEngine
from ai_detector_cli.engines.pangram_engine import PangramEngine
from ai_detector_cli.engines.detectingai_engine import DetectingAIEngine
from ai_detector_cli.engines.binoculars_engine import BinocularsEngine

TEXT = (
    "The industrial revolution fundamentally reshaped human society in ways "
    "that continue to echo through our modern world. Steam engines transformed "
    "manufacturing, railways connected distant communities, and factories drew "
    "rural populations into expanding cities."
)


def _result(engine_cls, **kwargs):
    return EngineResult(
        engine_name=engine_cls.name,
        available=kwargs.get("available", False),
        ai_percentage=0.0,
        human_percentage=100.0,
        verdict="UNAVAILABLE",
        weight=0.0,
        error=kwargs.get("error"),
    )


class TestRegistryWiring(unittest.TestCase):
    def test_all_engines_contains_premium_and_binoculars(self):
        keys = {engine_key(e) for e in ALL_ENGINES}
        expected = {"gptzero-api", "winston", "originality", "pangram", "detecting-ai", "binoculars"}
        self.assertTrue(expected.issubset(keys))
        self.assertEqual(len(keys), len(ALL_ENGINES), "engine keys must be unique")

    def test_premium_engines_inactive_without_keys(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for var in ("GPTZERO_API_KEY", "WINSTON_API_KEY", "ORIGINALITY_API_KEY",
                        "PANGRAM_API_KEY", "DETECTING_AI_API_KEY"):
                os.environ.pop(var, None)
            from ai_detector_cli.engines import CORE_HTTP_ENGINES
            live_keys = {engine_key(e) for e in LIVE_HTTP_ENGINES}
            for k in ("gptzero-api", "winston", "pangram"):
                self.assertNotIn(k, live_keys)

    def test_explicit_selection_pulls_from_full_registry(self):
        selected = select_engines(only=["pangram", "binoculars"])
        self.assertEqual({engine_key(e) for e in selected}, {"pangram", "binoculars"})

    def test_selection_no_match_still_empty(self):
        self.assertEqual(select_engines(only=["definitely-not-an-engine"]), [])

    def test_local_only_pool_unchanged_without_env(self):
        keys = {engine_key(e) for e in LOCAL_ENGINES}
        self.assertEqual(keys, {"gltr", "burstiness", "perplexity", "lexicon"} | (
            {"binoculars"} if BINOCULARS_ACTIVE else set()))


class TestGPTZeroApiEngine(unittest.TestCase):
    def _engine(self):
        return GPTZeroApiEngine(api_key="test-key")

    def test_missing_key_reports_setup_hint(self):
        eng = GPTZeroApiEngine(api_key="")
        res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("GPTZERO_API_KEY", res.error)
        self.assertIn("dashboard.gptzero.me", res.error)

    def test_parses_ai_only_response(self):
        canned = {
            "documents": [{
                "completely_generated_prob": 0.98,
                "average_generated_prob": 0.9,
                "predicted_class": "ai-only",
                "confidence_score": 0.95,
                "sentences": [
                    {"sentence": "AI sentence one.", "generated_prob": 0.99},
                    {"sentence": "Human sentence.", "generated_prob": 0.1},
                ],
            }]
        }
        eng = self._engine()
        with mock.patch("ai_detector_cli.engines.gptzero_api_engine.post_json_parsed",
                        return_value=(200, canned, 123.0)):
            res = eng.analyze(TEXT)
        self.assertTrue(res.available)
        self.assertGreaterEqual(res.ai_percentage, 90.0)
        self.assertEqual(res.verdict, "AI")
        self.assertEqual(res.flagged_sentences, ["AI sentence one."])
        self.assertEqual(res.details["predicted_class"], "ai-only")

    def test_parses_human_response(self):
        canned = {"documents": [{
            "completely_generated_prob": 0.02,
            "average_generated_prob": 0.05,
            "predicted_class": "human-only",
        }]}
        eng = self._engine()
        with mock.patch("ai_detector_cli.engines.gptzero_api_engine.post_json_parsed",
                        return_value=(200, canned, 100.0)):
            res = eng.analyze(TEXT)
        self.assertTrue(res.available)
        self.assertLess(res.ai_percentage, 10.0)
        self.assertEqual(res.verdict, "HUMAN")

    def test_auth_failure_message(self):
        eng = self._engine()
        with mock.patch("ai_detector_cli.engines.gptzero_api_engine.post_json_parsed",
                        return_value=(403, {"error": "API key has no owner"}, 50.0)):
            res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("Authentication failed", res.error)


class TestWinstonEngine(unittest.TestCase):
    def test_missing_key_reports_setup_hint(self):
        eng = WinstonEngine(api_key="")
        res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("WINSTON_API_KEY", res.error)

    def test_parses_fraction_score(self):
        canned = {
            "score": 0.92,
            "result": "ai",
            "sentences": [
                {"text": "Flagged sentence here.", "ai_score": 0.88},
                {"text": "Fine sentence.", "ai_score": 0.2},
            ],
        }
        eng = WinstonEngine(api_key="test-key")
        with mock.patch("ai_detector_cli.engines.winston_engine.post_json_parsed",
                        return_value=(200, canned, 140.0)):
            res = eng.analyze(TEXT)
        self.assertTrue(res.available)
        self.assertAlmostEqual(res.ai_percentage, 92.0, delta=0.1)
        self.assertEqual(res.verdict, "AI")
        self.assertEqual(res.flagged_sentences, ["Flagged sentence here."])

    def test_parses_percentage_score(self):
        canned = {"score": 12.5}
        eng = WinstonEngine(api_key="test-key")
        with mock.patch("ai_detector_cli.engines.winston_engine.post_json_parsed",
                        return_value=(200, canned, 90.0)):
            res = eng.analyze(TEXT)
        self.assertTrue(res.available)
        self.assertAlmostEqual(res.ai_percentage, 12.5, delta=0.1)


class TestOriginalityEngine(unittest.TestCase):
    def test_missing_key_reports_setup_hint(self):
        eng = OriginalityEngine(api_key="")
        res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("ORIGINALITY_API_KEY", res.error)

    def test_parses_ai_score_dict(self):
        canned = {"ai_score": {"fake": 0.87, "clear": 0.13}, "version": "1.0.0", "credits_used": 1}
        eng = OriginalityEngine(api_key="test-key")
        with mock.patch("ai_detector_cli.engines.originality_engine.post_json_parsed",
                        return_value=(200, canned, 160.0)):
            res = eng.analyze(TEXT)
        self.assertTrue(res.available)
        self.assertAlmostEqual(res.ai_percentage, 87.0, delta=0.1)
        self.assertEqual(res.verdict, "AI")

    def test_subscription_error_is_reported(self):
        eng = OriginalityEngine(api_key="test-key")
        with mock.patch("ai_detector_cli.engines.originality_engine.post_json_parsed",
                        return_value=(422, {"error": "Enterprise Subscription Required"}, 40.0)):
            res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("subscription", res.error.lower())


class TestPangramEngine(unittest.TestCase):
    def test_missing_key_reports_setup_hint(self):
        eng = PangramEngine(api_key="")
        res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("PANGRAM_API_KEY", res.error)

    def _run_with_polls(self, engine, poll_results):
        responses = iter(poll_results)
        with mock.patch("ai_detector_cli.engines.pangram_engine.time.sleep"), \
             mock.patch("ai_detector_cli.engines.pangram_engine.request") as req:
            def side_effect(url, method="GET", payload=None, headers=None, **kw):
                if method == "POST":
                    resp = mock.Mock()
                    resp.status = 200
                    resp.json.return_value = {"task_id": "task-123"}
                    return resp
                resp = mock.Mock()
                resp.status = 200
                resp.json.return_value = next(responses)
                return resp
            req.side_effect = side_effect
            return engine.analyze(TEXT)

    def test_full_task_flow_success(self):
        eng = PangramEngine(api_key="test-key")
        res = self._run_with_polls(eng, [
            {"stage": "STAGE_PROCESSING"},
            {"stage": "STAGE_SUCCESS", "fraction_ai": 0.91, "fraction_ai_assisted": 0.02,
             "fraction_human": 0.07, "prediction_short": "AI-generated",
             "headline": "AI", "num_ai_segments": 1,
             "ai_segments": [{"text": "Segment flagged as AI."}]},
        ])
        self.assertTrue(res.available)
        self.assertAlmostEqual(res.ai_percentage, 91.0, delta=0.1)
        self.assertEqual(res.verdict, "AI")
        self.assertEqual(res.flagged_sentences, ["Segment flagged as AI."])

    def test_task_failure_stage(self):
        eng = PangramEngine(api_key="test-key")
        res = self._run_with_polls(eng, [{"stage": "STAGE_FAILED"}])
        self.assertFalse(res.available)
        self.assertIn("STAGE_FAILED", res.error)

    def test_auth_failure(self):
        eng = PangramEngine(api_key="test-key")
        with mock.patch("ai_detector_cli.engines.pangram_engine.request") as req:
            resp = mock.Mock()
            resp.status = 401
            resp.json.return_value = {"detail": "Invalid API key"}
            req.return_value = resp
            res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("Authentication failed", res.error)


class TestDetectingAIEngine(unittest.TestCase):
    def test_missing_key_reports_setup_hint(self):
        eng = DetectingAIEngine(api_key="")
        res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("DETECTING_AI_API_KEY", res.error)

    def test_structured_result(self):
        canned = {"success": True, "data": {"details": {"result": {"ai": 0.77}},
                                            "version": "v3", "words_processed": 40}}
        eng = DetectingAIEngine(api_key="test-key")
        with mock.patch("ai_detector_cli.engines.detectingai_engine.post_json_parsed",
                        return_value=(200, canned, 110.0)):
            res = eng.analyze(TEXT)
        self.assertTrue(res.available)
        self.assertAlmostEqual(res.ai_percentage, 77.0, delta=0.1)

    def test_textual_result_extraction(self):
        canned = {"success": True,
                  "data": {"details": {"result": "The analyzed text appears to be 84% AI-generated."},
                           "version": "v3", "words_processed": 40}}
        eng = DetectingAIEngine(api_key="test-key")
        with mock.patch("ai_detector_cli.engines.detectingai_engine.post_json_parsed",
                        return_value=(200, canned, 110.0)):
            res = eng.analyze(TEXT)
        self.assertTrue(res.available)
        self.assertAlmostEqual(res.ai_percentage, 84.0, delta=0.1)

    def test_unparseable_result_marks_unavailable(self):
        canned = {"success": True,
                  "data": {"details": {"result": "No numeric score present."}, "version": "v3"}}
        eng = DetectingAIEngine(api_key="test-key")
        with mock.patch("ai_detector_cli.engines.detectingai_engine.post_json_parsed",
                        return_value=(200, canned, 90.0)):
            res = eng.analyze(TEXT)
        self.assertFalse(res.available)


class TestBinocularsEngine(unittest.TestCase):
    def test_score_mapping_calibrated(self):
        # Official threshold lands near the human/AI boundary.
        self.assertAlmostEqual(BinocularsEngine.score_to_ai_pct(0.9013310719761093), 13.9, delta=1.5)
        self.assertAlmostEqual(BinocularsEngine.score_to_ai_pct(0.60), 100.0, delta=0.1)
        self.assertAlmostEqual(BinocularsEngine.score_to_ai_pct(0.95), 0.0, delta=0.1)
        # Very human scores clamp at zero, never go negative.
        self.assertEqual(BinocularsEngine.score_to_ai_pct(1.20), 0.0)

    def test_unavailable_without_deps(self):
        eng = BinocularsEngine()
        if eng.deps_available():
            self.skipTest("torch/transformers installed - skipping unavailable path")
        res = eng.analyze(TEXT)
        self.assertFalse(res.available)
        self.assertIn("binoculars", res.error.lower())

    def test_not_auto_active_by_default(self):
        if BinocularsEngine().deps_available() and os.environ.get("AIDETECT_BINOCULARS", "").lower() in ("1", "true"):
            self.skipTest("binoculars explicitly enabled in this environment")
        self.assertFalse(BINOCULARS_ACTIVE)

    def test_env_flag_gates_auto_activation(self):
        eng = BinocularsEngine()
        if not eng.deps_available():
            self.assertFalse(eng.is_configured())  # deps missing -> never auto-active
        else:
            with mock.patch.dict(os.environ, {"AIDETECT_BINOCULARS": "1"}):
                self.assertTrue(eng.is_configured())


class TestDegradationSemantics(unittest.TestCase):
    """v2.1: partial live failure (one cloud engine down) must NOT claim degraded."""

    def _fail_engine(self, engine_cls):
        return mock.patch.object(
            engine_cls, "analyze",
            side_effect=lambda text, sentences=None, words=None: EngineResult(
                engine_name=engine_cls.name, available=False, ai_percentage=0.0,
                human_percentage=100.0, verdict="UNAVAILABLE", weight=0.0,
                error="Connection refused (simulated offline)"),
        )

    def test_partial_live_failure_is_not_degraded(self):
        # Simulate: ZeroGPT unavailable, Sapling and locals fine.
        with self._fail_engine(type(LIVE_HTTP_ENGINES[0])):
            report = analyze_text(TEXT, max_workers=4, source="unit-test")
        self.assertFalse(report.degraded)

    def test_total_live_failure_still_degrades(self):
        patches = [self._fail_engine(type(eng)) for eng in LIVE_HTTP_ENGINES]
        with mock.patch("builtins.print"):
            for p in patches:
                p.start()
            try:
                report = analyze_text(TEXT, max_workers=4, source="unit-test")
            finally:
                for p in patches:
                    p.stop()
        self.assertTrue(report.degraded)
        self.assertIn("unreachable", report.degradation_note)


if __name__ == "__main__":
    unittest.main()
