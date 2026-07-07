from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.budget import run_spend_from_operation
from agents.generation.phase2.codex_runner import (
    DEFAULT_CODEX_CHILD_DISABLED_FEATURES,
    DEFAULT_CODEX_STALE_RETRY_SECONDS,
    DEFAULT_SANDBOX,
    _codex_child_exec_args,
    _codex_child_env,
    _should_suppress_child_log_line,
    _stale_retry_timeout_seconds,
    execute_session,
    parse_codex_session_usage,
    prepare_session,
    resolve_cli_usage,
)
from agents.generation.phase2.console import _live_usage_scope
from agents.generation.phase2.store import ProofStateStore


def token_count_event(total_tokens: int, *, input_tokens: int, output_tokens: int) -> str:
    return json.dumps(
        {
            "timestamp": "2026-06-23T00:00:00.000Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": input_tokens,
                        "cached_input_tokens": 700,
                        "output_tokens": output_tokens,
                        "reasoning_output_tokens": 50,
                        "total_tokens": total_tokens,
                    },
                    "last_token_usage": {
                        "input_tokens": 10,
                        "cached_input_tokens": 0,
                        "output_tokens": 5,
                        "reasoning_output_tokens": 2,
                        "total_tokens": 15,
                    },
                },
            },
        }
    )


class Phase2TokenUsageTest(unittest.TestCase):
    def test_codex_child_default_sandbox_allows_cas_temp_files(self) -> None:
        self.assertEqual(DEFAULT_SANDBOX, "workspace-write")

    def test_codex_child_ignores_user_config_by_default(self) -> None:
        old = os.environ.pop("ALBILICH_CODEX_CHILD_USE_USER_CONFIG", None)
        try:
            args = _codex_child_exec_args(["--json"])
            self.assertEqual(args[0], "--ignore-user-config")
            self.assertEqual(args[-1], "--json")
            self.assertEqual(
                {args[index + 1] for index, token in enumerate(args[:-1]) if token == "--disable"},
                set(DEFAULT_CODEX_CHILD_DISABLED_FEATURES),
            )
            guarded = _codex_child_exec_args(["--ignore-user-config"])
            self.assertEqual(guarded.count("--ignore-user-config"), 1)
        finally:
            if old is not None:
                os.environ["ALBILICH_CODEX_CHILD_USE_USER_CONFIG"] = old

    def test_codex_child_user_config_escape_hatch(self) -> None:
        old = os.environ.get("ALBILICH_CODEX_CHILD_USE_USER_CONFIG")
        os.environ["ALBILICH_CODEX_CHILD_USE_USER_CONFIG"] = "1"
        try:
            self.assertEqual(_codex_child_exec_args(["--json"]), ["--json"])
        finally:
            if old is None:
                os.environ.pop("ALBILICH_CODEX_CHILD_USE_USER_CONFIG", None)
            else:
                os.environ["ALBILICH_CODEX_CHILD_USE_USER_CONFIG"] = old

    def test_codex_child_env_sets_writable_python_cache_paths(self) -> None:
        old = os.environ.get("ALBILICH_CODEX_TMPDIR")
        old_rust_log = os.environ.pop("RUST_LOG", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["ALBILICH_CODEX_TMPDIR"] = tmpdir
            try:
                env = _codex_child_env()
                self.assertEqual(env["TMPDIR"], tmpdir)
                self.assertEqual(env["TEMP"], tmpdir)
                self.assertEqual(env["TMP"], tmpdir)
                self.assertTrue(Path(env["TMPDIR"]).is_dir())
                self.assertEqual(env["PYTHONPYCACHEPREFIX"], str(Path(tmpdir) / "pycache"))
                self.assertTrue(Path(env["PYTHONPYCACHEPREFIX"]).is_dir())
                self.assertEqual(env["DOT_SAGE"], str(Path(tmpdir) / ".sage"))
                self.assertTrue(Path(env["DOT_SAGE"]).is_dir())
                self.assertEqual(env["SAGE_STARTUP_FILE"], str(Path(tmpdir) / "nonexistent_sage_startup.py"))
                self.assertEqual(env.get("HOME"), os.environ.get("HOME"))
                self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
                self.assertIn("codex_core_plugins::manifest=error", env["RUST_LOG"])
                self.assertIn("codex_core_skills::loader=error", env["RUST_LOG"])
                self.assertIn("codex_mcp::rmcp_client=error", env["RUST_LOG"])
                self.assertIn("codex_rollout::state_db=error", env["RUST_LOG"])
            finally:
                if old is None:
                    os.environ.pop("ALBILICH_CODEX_TMPDIR", None)
                else:
                    os.environ["ALBILICH_CODEX_TMPDIR"] = old
                if old_rust_log is not None:
                    os.environ["RUST_LOG"] = old_rust_log

    def test_codex_child_env_wraps_gap_with_no_history_flag(self) -> None:
        old_tmp = os.environ.get("ALBILICH_CODEX_TMPDIR")
        old_gap = os.environ.get("GAP_BIN")
        old_real_gap = os.environ.get("ALBILICH_REAL_GAP_BIN")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            real_gap = tmp_path / "real-gap"
            real_gap.write_text(
                "#!/bin/sh\n"
                "printf 'HOME=%s\\n' \"$HOME\"\n"
                "printf 'GAP_HISTFILE=%s\\n' \"$GAP_HISTFILE\"\n"
                "printf 'ARGS=%s\\n' \"$*\"\n",
                encoding="utf-8",
            )
            real_gap.chmod(0o755)
            os.environ["ALBILICH_CODEX_TMPDIR"] = str(tmp_path / "child")
            os.environ["GAP_BIN"] = str(real_gap)
            os.environ.pop("ALBILICH_REAL_GAP_BIN", None)
            try:
                env = _codex_child_env()
                wrapper = Path(env["GAP_BIN"])
                self.assertEqual(wrapper.name, "gap")
                self.assertTrue(wrapper.exists())
                self.assertEqual(env["ALBILICH_REAL_GAP_BIN"], str(real_gap))
                self.assertEqual(env["PATH"].split(os.pathsep)[0], str(wrapper.parent))
                result = subprocess.run(
                    [env["GAP_BIN"], "-q"],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                self.assertEqual(
                    result.stdout.splitlines(),
                    [
                        f"HOME={tmp_path / 'child' / 'gap-home'}",
                        "GAP_HISTFILE=/dev/null",
                        "ARGS=-n -q",
                    ],
                )
            finally:
                if old_tmp is None:
                    os.environ.pop("ALBILICH_CODEX_TMPDIR", None)
                else:
                    os.environ["ALBILICH_CODEX_TMPDIR"] = old_tmp
                if old_gap is None:
                    os.environ.pop("GAP_BIN", None)
                else:
                    os.environ["GAP_BIN"] = old_gap
                if old_real_gap is None:
                    os.environ.pop("ALBILICH_REAL_GAP_BIN", None)
                else:
                    os.environ["ALBILICH_REAL_GAP_BIN"] = old_real_gap

    def test_child_log_filter_suppresses_only_known_startup_noise(self) -> None:
        self.assertTrue(
            _should_suppress_child_log_line(
                "2026-06-26T00:00:00Z  WARN codex_core_plugins::manifest: ignoring interface.defaultPrompt[0]\n"
            )
        )
        self.assertTrue(
            _should_suppress_child_log_line(
                "2026-06-26T00:00:00Z  WARN codex_core_skills::loader: ignoring interface.icon_small: bad icon\n"
            )
        )
        self.assertTrue(
            _should_suppress_child_log_line(
                "2026-06-26T00:00:00Z  WARN codex_mcp::rmcp_client: failed to initialize MCP client during shutdown: MCP startup failed: Environment variable GITHUB_PAT_TOKEN for MCP server 'github' is not set\n"
            )
        )
        self.assertTrue(
            _should_suppress_child_log_line(
                "2026-06-26T00:00:00Z  WARN codex_rollout::state_db: state db discrepancy during read_repair_rollout_path: upsert_needed (slow path)\n"
            )
        )
        self.assertFalse(_should_suppress_child_log_line("2026-06-26T00:00:00Z ERROR codex_core::tools::router: failed\n"))
        self.assertFalse(_should_suppress_child_log_line("Traceback (most recent call last):\n"))

    def test_codex_retry_stall_times_out_before_full_session_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_codex = root / "fake_codex.py"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import time\n"
                "print('session id: 019ef5aa-0000-7000-9000-staleretry1', flush=True)\n"
                "print('2026-06-28T00:00:00Z  WARN codex_core::responses_retry: stream disconnected - retrying sampling request (1/5 in 196ms)...', flush=True)\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            store = ProofStateStore("codex-stale-retry-timeout-test", generation_root=root / "generation")
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)
            old_stale = os.environ.get("ALBILICH_CODEX_STALE_RETRY_SECONDS")
            old_heartbeat = os.environ.get("ALBILICH_UI_HEARTBEAT_SECONDS")
            os.environ["ALBILICH_CODEX_STALE_RETRY_SECONDS"] = "0.2"
            os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = "0.1"
            try:
                result = execute_session(
                    store,
                    action,
                    plan,
                    codex_bin=str(fake_codex),
                    timeout_sec=5,
                )
            finally:
                if old_stale is None:
                    os.environ.pop("ALBILICH_CODEX_STALE_RETRY_SECONDS", None)
                else:
                    os.environ["ALBILICH_CODEX_STALE_RETRY_SECONDS"] = old_stale
                if old_heartbeat is None:
                    os.environ.pop("ALBILICH_UI_HEARTBEAT_SECONDS", None)
                else:
                    os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = old_heartbeat

            self.assertEqual(result["status"], "timeout")
            self.assertLess(result["wall_time_seconds"], 3.0)
            log = Path(result["log_path"]).read_text(encoding="utf-8")
            self.assertIn("stream disconnected - retrying sampling request", log)
            self.assertIn("no log/token progress after a Codex stream retry", log)
            self.assertIn("Codex stream retry stalled", result["patch_error"])

    def test_default_codex_retry_stall_timeout_is_short(self) -> None:
        old_stale = os.environ.get("ALBILICH_CODEX_STALE_RETRY_SECONDS")
        try:
            os.environ.pop("ALBILICH_CODEX_STALE_RETRY_SECONDS", None)
            self.assertLessEqual(DEFAULT_CODEX_STALE_RETRY_SECONDS, 90.0)
            self.assertEqual(_stale_retry_timeout_seconds(1800), DEFAULT_CODEX_STALE_RETRY_SECONDS)
        finally:
            if old_stale is not None:
                os.environ["ALBILICH_CODEX_STALE_RETRY_SECONDS"] = old_stale

    def test_session_telemetry_beats_cli_footer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "sessions"
            session_id = "019ef5aa-0000-7000-9000-tokenfix0001"
            session_path = root / "2026" / "06" / "23" / f"rollout-2026-06-23T00-00-00-{session_id}.jsonl"
            session_path.parent.mkdir(parents=True)
            session_path.write_text(
                "\n".join(
                    [
                        token_count_event(1_200, input_tokens=1_000, output_tokens=200),
                        token_count_event(35_012, input_tokens=34_263, output_tokens=749),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            usage = resolve_cli_usage(
                f"session id: {session_id}\n\n"
                "tokens used\n"
                "6,368\n",
                session_root=root,
            )

        self.assertEqual(usage["total_tokens"], 35_012)
        self.assertEqual(usage["input_tokens"], 34_263)
        self.assertEqual(usage["cached_input_tokens"], 700)
        self.assertEqual(usage["output_tokens"], 749)
        self.assertEqual(usage["reasoning_output_tokens"], 50)

    def test_cli_footer_remains_fallback_without_session_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            usage = resolve_cli_usage(
                "session id: missing-session\n\n"
                "tokens used\n"
                "6,368\n",
                session_root=Path(tmpdir) / "sessions",
            )

        self.assertEqual(usage["total_tokens"], 6_368)
        self.assertEqual(usage["input_tokens"], 6_368)

    def test_session_usage_parser_ignores_last_token_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "sessions"
            session_id = "019ef5aa-0000-7000-9000-tokenfix0002"
            session_path = root / f"rollout-2026-06-23T00-00-00-{session_id}.jsonl"
            session_path.parent.mkdir(parents=True)
            session_path.write_text(token_count_event(9_999, input_tokens=9_000, output_tokens=999) + "\n", encoding="utf-8")

            usage = parse_codex_session_usage(session_id, session_root=root)

        self.assertEqual(usage["total_tokens"], 9_999)
        self.assertEqual(usage["input_tokens"], 9_000)

    def test_budget_spend_excludes_cached_input(self) -> None:
        # 1.30M processed but 1.20M cached -> only new work is charged.
        op = {
            "input_tokens": 1_300_000,
            "cached_input_tokens": 1_200_000,
            "output_tokens": 9_000,
            "reasoning_output_tokens": 5_000,
            "total_tokens": 1_314_000,
        }
        self.assertEqual(run_spend_from_operation(op), 100_000 + 9_000 + 5_000)

    def test_budget_spend_falls_back_to_total_without_breakdown(self) -> None:
        # Collapsed CLI footer: only a total, no component breakdown.
        self.assertEqual(run_spend_from_operation({"total_tokens": 6_368}), 6_368)
        self.assertEqual(run_spend_from_operation({"input_tokens": 6_368, "total_tokens": 6_368}), 6_368)

    def test_session_breakdown_preferred_over_equal_total_cli_footer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "sessions"
            session_id = "019ef5aa-0000-7000-9000-tokenfix0003"
            session_path = root / f"rollout-2026-06-23T00-00-00-{session_id}.jsonl"
            session_path.parent.mkdir(parents=True)
            # Session total equals the CLI footer total but carries the breakdown.
            session_path.write_text(token_count_event(6_368, input_tokens=6_000, output_tokens=368) + "\n", encoding="utf-8")
            usage = resolve_cli_usage(f"session id: {session_id}\n\ntokens used\n6,368\n", session_root=root)
        self.assertEqual(usage["output_tokens"], 368)
        self.assertEqual(usage["cached_input_tokens"], 700)

    def test_live_usage_scope_sums_live_usage_payloads(self) -> None:
        summary = _live_usage_scope(
            [
                {
                    "elapsed_seconds": 1.25,
                    "peak_memory_mb": 111.0,
                    "usage": {"input_tokens": 100, "output_tokens": 20, "reasoning_output_tokens": 5, "total_tokens": 120},
                },
                {
                    "elapsed_seconds": 2.25,
                    "peak_memory_mb": 222.0,
                    "usage": {"input_tokens": 400, "output_tokens": 59, "reasoning_output_tokens": 10, "total_tokens": 459},
                },
            ]
        )

        self.assertEqual(summary["run_count"], 2)
        self.assertEqual(summary["total_tokens"], 579)
        self.assertEqual(summary["input_tokens"], 500)
        self.assertEqual(summary["output_tokens"], 79)
        self.assertEqual(summary["reasoning_output_tokens"], 15)
        self.assertEqual(summary["wall_time_seconds"], 3.5)
        self.assertEqual(summary["peak_memory_mb"], 222.0)


if __name__ == "__main__":
    unittest.main()
