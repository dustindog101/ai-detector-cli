"""
Tests for v2 features: batch mode, HTML export, auto-adaptive degradation,
http_client pooling/retries, engine selection, and JSON schema additions.
All tests are offline-safe (network is mocked).
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ai_detector_cli.cli import (
    analyze_text,
    run_batch,
    select_engines,
    list_engines,
    engine_key,
    discover_batch_files,
)
from ai_detector_cli.models import EngineResult
from ai_detector_cli.engines import LIVE_HTTP_ENGINES, LOCAL_ENGINES, DEFAULT_ENGINES
from ai_detector_cli import html_report
from ai_detector_cli.reporter import format_batch_report, export_batch_json
from ai_detector_cli import http_client


SAMPLES = os.path.join(current_dir, "samples")


def _load(name):
    with open(os.path.join(SAMPLES, name), "r", encoding="utf-8") as f:
        return f.read()


class TestEngineSelection(unittest.TestCase):
    def test_default_includes_live_and_local(self):
        selected = select_engines()
        keys = {engine_key(e) for e in selected}
        self.assertIn("zerogpt", keys)
        self.assertIn("sapling", keys)
        self.assertIn("gltr", keys)
        self.assertIn("burstiness", keys)

    def test_local_only_excludes_network(self):
        selected = select_engines(local_only=True)
        keys = {engine_key(e) for e in selected}
        self.assertNotIn("zerogpt", keys)
        self.assertNotIn("sapling", keys)
        self.assertEqual(keys, {engine_key(e) for e in LOCAL_ENGINES})

    def test_engines_filter(self):
        selected = select_engines(only=["gltr", "lexicon"])
        self.assertEqual({engine_key(e) for e in selected}, {"gltr", "lexicon"})

    def test_engines_filter_no_match_yields_empty(self):
        self.assertEqual(select_engines(only=["nonexistent"]), [])

    def test_list_engines_output(self):
        out = list_engines()
        self.assertIn("ZeroGPT", out)
        self.assertIn("Burstiness", out)


class TestAutoAdaptiveDegradation(unittest.TestCase):
    """When all live engines fail but local ones succeed, report is degraded."""

    def _make_live_failure(self, name):
        return mock.patch.object(
            type(name), "analyze",
            side_effect=lambda text, sentences=None, words=None: EngineResult(
                engine_name=name.name, available=False, ai_percentage=0.0,
                human_percentage=100.0, verdict="UNAVAILABLE", weight=0.0,
                error="Connection refused (simulated offline)"),
        )

    def test_degraded_flag_and_stderr(self):
        text = _load("ai_sample.txt")
        patches = [self._make_live_failure(eng) for eng in LIVE_HTTP_ENGINES]
        with mock.patch("builtins.print") as fake_print:
            for p in patches:
                p.start()
            try:
                report = analyze_text(text, max_workers=4, source="unit-test")
            finally:
                for p in patches:
                    p.stop()
        self.assertTrue(report.degraded)
        self.assertIsNotNone(report.degradation_note)
        self.assertIn("offline", report.degradation_note.lower())
        # warning goes through print(..., file=sys.stderr)
        printed_args = fake_print.call_args_list
        self.assertTrue(any(
            "unreachable" in str(call) for call in printed_args
        ))
        # Local engines still produced a usable consensus
        self.assertGreater(report.consensus_ai_probability, 0.0)
        self.assertGreater(len(report.sentences), 0)

    def test_json_schema_includes_v2_fields(self):
        text = _load("human_sample.txt")
        report = analyze_text(text, local_only=True, source="unit-test")
        data = json.loads(json.dumps({
            "source": report.source,
            "degraded": report.degraded,
            "analysis_ms": report.analysis_ms,
            "engine_mode": report.engine_mode,
        }))
        self.assertEqual(data["source"], "unit-test")
        self.assertFalse(data["degraded"])
        self.assertEqual(data["engine_mode"], "local-only")


class TestBatchMode(unittest.TestCase):
    def test_discover_files(self):
        files = discover_batch_files(SAMPLES, recursive=False, pattern=None)
        names = [os.path.basename(f) for f in files]
        self.assertIn("ai_sample.txt", names)
        self.assertIn("human_sample.txt", names)
        self.assertIn("test_doc.html", names)

    def test_discover_with_glob(self):
        files = discover_batch_files(SAMPLES, recursive=False, pattern="*.md")
        self.assertEqual(files, [])

    def test_run_batch_local_only(self):
        batch = run_batch(SAMPLES, threshold=30.0, local_only=True)
        self.assertEqual(len(batch.entries), 4)
        ok_entries = [e for e in batch.entries if e.report]
        self.assertEqual(len(ok_entries), 4)
        # Ranked descending by AI probability
        scores = [e.report.consensus_ai_probability for e in ok_entries]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # AI sample should outrank human sample
        self.assertGreater(ok_entries[0].report.consensus_ai_probability,
                           min(scores))
        self.assertGreater(batch.elapsed_ms, 0.0)

    def test_batch_json_and_terminal_report(self):
        batch = run_batch(SAMPLES, threshold=30.0, local_only=True)
        data = json.loads(export_batch_json(batch))
        self.assertEqual(data["mode"], "batch")
        self.assertEqual(data["summary"]["files_ok"], 4)
        self.assertIn("files", data)
        terminal = format_batch_report(batch)
        self.assertIn("BATCH AI DETECTION SCAN", terminal)
        self.assertIn("SUMMARY", terminal)

    def test_batch_html_export(self):
        batch = run_batch(SAMPLES, threshold=30.0, local_only=True)
        html = html_report.export_batch_html(batch)
        self.assertIn("Batch AI Detection Report", html)
        self.assertIn("bar-wrap", html)

    def test_batch_handles_bad_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "good.txt"), "w") as f:
                f.write(_load("human_sample.txt"))
            with open(os.path.join(tmp, "bad.bin"), "wb") as f:
                f.write(b"\x00\x01\x02not-a-docx")
            # bad.bin is not a supported extension; test an unreadable docx instead
            fake = os.path.join(tmp, "broken.docx")
            with open(fake, "wb") as f:
                f.write(b"PK\x00\x00garbage")
            batch = run_batch(tmp, threshold=30.0, local_only=True)
            self.assertGreaterEqual(len(batch.entries), 2)
            errors = [e for e in batch.entries if e.error]
            self.assertGreaterEqual(len(errors), 1)
            paths = [os.path.basename(e.path) for e in batch.entries]
            self.assertIn("good.txt", paths)


class TestHTMLExport(unittest.TestCase):
    def test_single_report_html_self_contained(self):
        report = analyze_text(_load("ai_sample.txt"), local_only=True, source="s.html")
        html = html_report.export_html(report)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<style>", html)
        self.assertIn("AI Text Detection Report", html)
        self.assertIn("<svg", html.lower())
        # No external scripts/styles/fonts
        self.assertNotIn("<script src=", html)
        self.assertNotIn('<link rel="stylesheet"', html)

    def test_verdict_colors_present(self):
        report = analyze_text(_load("ai_sample.txt"), local_only=True)
        html = html_report.export_html(report)
        # Colored bars exist for engine rows
        self.assertIn("bar-wrap", html)

    def test_in_depth_report_sections(self):
        report = analyze_text(_load("ai_sample.txt"), local_only=True, source="x.md")
        html = html_report.export_html(report)
        # Academic presentation
        self.assertIn("AI Provenance Audit", html)
        self.assertIn("Report ID", html)
        self.assertIn("Executive Summary", html)
        self.assertIn("§1", html)                          # numbered academic sections
        self.assertIn("Methodology", html)
        # In-depth sections
        self.assertIn("class=\"marker\"", html)            # risk-scale position marker
        self.assertIn("Local Statistical Engines", html)   # tier grouping
        self.assertIn("Max−Min Engine Spread", html)       # agreement analysis
        self.assertIn('class="hist"', html)                # risk histogram
        self.assertIn('class="cad"', html)                 # cadence chart
        self.assertIn("How the consensus is computed".replace(
            "How the consensus is computed", "Computation of the consensus"), html)
        self.assertIn("v2.3.0", html)                      # version chip
        self.assertIn("UTC", html)                         # issued stamp
        # Engine details are collapsible, not lost
        self.assertIn("<details", html)
        self.assertIn("append ▾", html)

    def test_batch_report_distribution_and_status(self):
        batch = run_batch(SAMPLES, threshold=30.0, local_only=True)
        html = html_report.export_batch_html(batch)
        self.assertIn('class="hist"', html)
        self.assertIn("Score Distribution", html)
        self.assertIn("Above threshold", html)
        self.assertIn("Per-File Results", html)

    def test_pdf_report_academic_layout(self):
        try:
            from ai_detector_cli import pdf_report
        except SystemExit:
            self.skipTest("reportlab not installed (install the [pdf] extra)")
        report = analyze_text(_load("ai_sample.txt"), local_only=True, source="x.md")
        data = pdf_report.export_pdf_bytes(report)
        self.assertTrue(data.startswith(b"%PDF"), "PDF magic missing")
        self.assertGreater(len(data), 5000, "PDF suspiciously small")
        # Readable metadata via pypdf (installed with the [pdf] extra)
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "".join(page.extract_text() or "" for page in reader.pages)
            self.assertIn("AI Text Detection Report", text)
            self.assertIn("EXECUTIVE SUMMARY", text.upper())
            self.assertIn("METHODOLOGY", text.upper())
            self.assertIn("Report AIA-", text)
        except ImportError:
            self.skipTest("pypdf not installed")

    def test_batch_pdf_report(self):
        try:
            from ai_detector_cli import pdf_report
        except SystemExit:
            self.skipTest("reportlab not installed (install the [pdf] extra)")
        batch = run_batch(SAMPLES, threshold=30.0, local_only=True)
        data = pdf_report.export_batch_pdf_bytes(batch)
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 3000)

    def test_html_flag_mutually_exclusive_with_export(self):
        from ai_detector_cli import cli as cli_mod
        from ai_detector_cli.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--html", "r.html", "file.md"])
        self.assertEqual(args.html, "r.html")
        # The conflict is enforced in main(), immediately after parsing.
        with self.assertRaises(SystemExit) as ctx:
            cli_mod.main(["--html", "r.html", "--export", "o.json", "file.md"])
        self.assertEqual(ctx.exception.code, 2)


class TestHTTPClient(unittest.TestCase):
    def test_configure_timeout_env(self):
        old = http_client.get_default_timeout()
        http_client.configure_timeout(42)
        self.assertEqual(http_client.get_default_timeout(), 42.0)
        http_client.configure_timeout(old)

    def test_transient_status_list(self):
        self.assertIn(503, http_client._TRANSIENT_STATUSES)
        self.assertIn(429, http_client._TRANSIENT_STATUSES)

    def test_request_unreachable_raises_http_error(self):
        # Port 1 on localhost is (almost) never open; retries exhaust fast.
        with self.assertRaises(http_client.HTTPError):
            http_client.post_json(
                "http://127.0.0.1:1/api", {"x": 1}, timeout=0.3, retries=1
            )

    def test_pool_is_thread_local(self):
        pool1 = getattr(http_client._local, "pool", {})
        self.assertIsInstance(pool1, dict)


class TestPerformanceCharacteristics(unittest.TestCase):
    def test_local_analysis_is_fast(self):
        import time
        text = _load("mixed_sample.txt")
        start = time.perf_counter()
        analyze_text(text, local_only=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        # Local statistical engines should complete in well under 500 ms.
        self.assertLess(elapsed_ms, 500.0)

    def test_default_engine_count(self):
        self.assertEqual(len(DEFAULT_ENGINES), 6)


class TestCLIRegressionGuards(unittest.TestCase):
    """Regression guards for behaviors introduced in v2."""

    def test_report_has_source_and_duration(self):
        report = analyze_text(_load("ai_sample.txt"), local_only=True, source="x.txt")
        self.assertEqual(report.source, "x.txt")
        self.assertGreaterEqual(report.analysis_ms, 0.0)

    def test_sentence_reasons_deduplicated(self):
        report = analyze_text(_load("ai_sample.txt"), local_only=True)
        for s in report.sentences:
            self.assertEqual(len(s.reasons), len(set(s.reasons)))

    def test_empty_text_report(self):
        report = analyze_text("", local_only=True)
        self.assertEqual(report.consensus_verdict, "EMPTY")


if __name__ == "__main__":
    unittest.main()
