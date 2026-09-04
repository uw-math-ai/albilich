from __future__ import annotations

import io
import os
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from agents.generation.phase2.codex_runner import (
    AGGREGATE_CHILD_MAX_RSS_ENV,
    CHILD_MAX_RSS_ENV,
    DEFAULT_MAX_AGGREGATE_CHILD_RSS_MB,
    DEFAULT_MAX_CHILD_RSS_MB,
    MAX_RESOURCE_POLL_SECONDS,
    AggregateProcessTreeRSSGovernor,
    _progress_interval_seconds,
    _child_max_rss_mb,
    _process_tree_rss_mb,
    _read_bounded_text,
    _replace_oversized_model_output,
    _run_id,
    _stream_child_log,
    extract_patch_from_text,
    aggregate_child_max_process_tree_rss_mb,
)


class CodexPatchExtractionTests(unittest.TestCase):
    def test_aggregate_rss_governor_trips_every_participant_permanently(self) -> None:
        governor = AggregateProcessTreeRSSGovernor(100.0)
        first_stop = threading.Event()
        second_stop = threading.Event()

        self.assertEqual(
            (40.0, False),
            governor.observe("first", 40.0, stop_event=first_stop),
        )
        self.assertEqual(
            (101.0, True),
            governor.observe("second", 61.0, stop_event=second_stop),
        )
        self.assertTrue(first_stop.is_set())
        self.assertTrue(second_stop.is_set())

        governor.release("first")
        governor.release("second")
        self.assertEqual(
            {
                "limit_mb": 100.0,
                "current_mb": 0,
                "peak_mb": 101.0,
                "participant_count": 0,
                "tripped": True,
            },
            governor.snapshot(),
        )
        later_stop = threading.Event()
        self.assertEqual(
            (1.0, True),
            governor.observe("later", 1.0, stop_event=later_stop),
        )
        self.assertTrue(later_stop.is_set())

    def test_aggregate_rss_governor_rejects_invalid_limits_and_samples(self) -> None:
        for limit in (
            0,
            -1,
            float("nan"),
            float("inf"),
            float("-inf"),
            1024 * 1024 + 1,
        ):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    AggregateProcessTreeRSSGovernor(limit)
        governor = AggregateProcessTreeRSSGovernor(10)
        for sample in (-1, float("nan"), float("inf"), float("-inf"), "bad"):
            with self.subTest(sample=sample):
                with self.assertRaises(ValueError):
                    governor.observe("participant", sample)
        with self.assertRaises(ValueError):
            governor.observe("", 1)

    def test_aggregate_rss_limit_uses_finite_positive_environment_override(self) -> None:
        with mock.patch.dict(os.environ, {AGGREGATE_CHILD_MAX_RSS_ENV: ""}):
            self.assertEqual(
                float(DEFAULT_MAX_AGGREGATE_CHILD_RSS_MB),
                aggregate_child_max_process_tree_rss_mb(),
            )
        for raw in (
            "bad",
            "0",
            "-1",
            "nan",
            "inf",
            "-inf",
            "1048577",
        ):
            with self.subTest(raw=raw), mock.patch.dict(
                os.environ,
                {AGGREGATE_CHILD_MAX_RSS_ENV: raw},
            ):
                with self.assertRaises(ValueError):
                    aggregate_child_max_process_tree_rss_mb()
        with mock.patch.dict(
            os.environ,
            {AGGREGATE_CHILD_MAX_RSS_ENV: "123.5"},
        ):
            self.assertEqual(123.5, aggregate_child_max_process_tree_rss_mb())

    def test_per_child_rss_limit_fails_closed_on_invalid_operator_input(self) -> None:
        with mock.patch.dict(os.environ, {CHILD_MAX_RSS_ENV: ""}):
            self.assertEqual(float(DEFAULT_MAX_CHILD_RSS_MB), _child_max_rss_mb())
        for raw in ("bad", "0", "-1", "nan", "inf", "-inf", "1048577"):
            with self.subTest(raw=raw), mock.patch.dict(
                os.environ,
                {CHILD_MAX_RSS_ENV: raw},
            ):
                with self.assertRaises(ValueError):
                    _child_max_rss_mb()

    def test_child_log_capture_is_bounded_and_signals_supervisor(self) -> None:
        source = io.StringIO("x" * 200 + "\n")
        destination = io.StringIO()
        reached = threading.Event()
        _stream_child_log(
            source,
            destination,
            threading.Lock(),
            reached,
            32,
        )
        self.assertTrue(reached.is_set())
        self.assertLessEqual(len(destination.getvalue().encode("utf-8")), 32)

    def test_model_response_reader_rejects_partial_oversized_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            response = Path(tmpdir) / "final_patch.json"
            response.write_text('{"schema_version":3,"operations":[]}', encoding="utf-8")
            text, oversized = _read_bounded_text(response, max_bytes=8)
            self.assertEqual("", text)
            self.assertTrue(oversized)

    def test_oversized_response_replacement_does_not_follow_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "operator-file.txt"
            target.write_bytes(b"protected" * 100)
            response = Path(tmpdir) / "final_patch.json"
            response.symlink_to(target)
            before = target.read_bytes()

            _replace_oversized_model_output(response, max_bytes=32)

            self.assertTrue(response.is_symlink())
            self.assertEqual(before, target.read_bytes())
            self.assertFalse(
                (Path(tmpdir) / "final_patch.rejected-sample.txt").exists()
            )

    def test_parallel_run_ids_remain_unique_at_the_same_timestamp(self) -> None:
        with mock.patch(
            "agents.generation.phase2.codex_runner.utc_now",
            return_value="2026-09-01T00:00:00+00:00",
        ):
            first = _run_id("prove", "root")
            second = _run_id("prove", "root")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("v1_prove_root_20260901T000000Z_"))

    def test_resource_poll_interval_cannot_be_disabled_by_large_heartbeat(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"ALBILICH_UI_HEARTBEAT_SECONDS": "86400"},
        ):
            self.assertEqual(
                MAX_RESOURCE_POLL_SECONDS,
                _progress_interval_seconds(),
            )

    @unittest.skipUnless(Path("/proc/self/task").is_dir(), "requires Linux procfs")
    def test_process_tree_rss_counts_child_forked_by_nonleader_thread(self) -> None:
        script = (
            "import subprocess,sys,threading,time\n"
            "ready=threading.Event()\n"
            "def worker():\n"
            " p=subprocess.Popen([sys.executable,'-c',"
            "'import time; x=bytearray(48*1024*1024); print(\"child-ready\",flush=True); time.sleep(30)'],"
            "stdout=subprocess.PIPE,text=True)\n"
            " p.stdout.readline(); ready.set(); p.wait()\n"
            "threading.Thread(target=worker,daemon=True).start()\n"
            "ready.wait(10); print('tree-ready',flush=True); time.sleep(30)\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            self.assertEqual("tree-ready", process.stdout.readline().strip())
            self.assertGreater(_process_tree_rss_mb(process.pid), 40.0)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            if process.stdout is not None:
                process.stdout.close()

    def test_preserves_unescaped_latex_commands_with_valid_json_prefixes(self) -> None:
        raw = (
            r'{"schema_version":3,"operations":[{"content":"'
            r'Let \\(W\neq0\\), \\beta, \\frac{x}{y}, \\rho, \\text{x}, and A\nleq B.'
            r'"}]}'
        )

        patch, error = extract_patch_from_text(raw)

        self.assertEqual(error, "")
        self.assertIsNotNone(patch)
        self.assertEqual(
            patch["operations"][0]["content"],
            r"Let \(W\neq0\), \beta, \frac{x}{y}, \rho, \text{x}, and A\nleq B.",
        )

    def test_leaves_ordinary_json_newlines_and_escaped_latex_unchanged(self) -> None:
        raw = (
            r'{"schema_version":3,"operations":[{"content":"'
            r'line one\nline two; \\(W\\neq0\\)'
            r'"}]}'
        )

        patch, error = extract_patch_from_text(raw)

        self.assertEqual(error, "")
        self.assertIsNotNone(patch)
        self.assertEqual(patch["operations"][0]["content"], "line one\nline two; \\(W\\neq0\\)")


if __name__ == "__main__":
    unittest.main()
