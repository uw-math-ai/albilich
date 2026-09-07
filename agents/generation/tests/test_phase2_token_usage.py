from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.budget import parse_token_usage, run_spend_from_operation
from agents.generation.phase2.codex_runner import (
    AggregateProcessTreeRSSGovernor,
    DEFAULT_CODEX_CHILD_DISABLED_FEATURES,
    DEFAULT_CODEX_STALE_RETRY_SECONDS,
    DEFAULT_SANDBOX,
    MAX_SESSION_USAGE_TAIL_BYTES,
    _codex_child_exec_args,
    _codex_child_env,
    _should_suppress_child_log_line,
    _stale_retry_timeout_seconds,
    _RSSSamplingFailure,
    execute_session,
    parse_codex_session_usage,
    prepare_session,
    resolve_codex_executable,
    resolve_cli_usage,
)
from agents.generation.phase2.console import _live_usage_scope
from agents.generation.phase2.models import SCHEMA_VERSION
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
    def test_builtin_session_enforces_aggregate_child_rss_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_codex = root / "fake_memory_codex.py"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import time\n"
                "memory = bytearray(16 * 1024 * 1024)\n"
                "print('memory-ready', flush=True)\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            store = ProofStateStore(
                "codex-aggregate-rss-limit-test",
                generation_root=root / "generation",
            )
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)
            governor = AggregateProcessTreeRSSGovernor(1.0)
            old_heartbeat = os.environ.get("ALBILICH_UI_HEARTBEAT_SECONDS")
            os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = "0.05"
            try:
                result = execute_session(
                    store,
                    action,
                    plan,
                    codex_bin=str(fake_codex),
                    timeout_sec=5,
                    progress_callback=lambda _progress: None,
                    stop_event=threading.Event(),
                    aggregate_rss_governor=governor,
                    enforce_backend_contract=False,
                )
            finally:
                if old_heartbeat is None:
                    os.environ.pop("ALBILICH_UI_HEARTBEAT_SECONDS", None)
                else:
                    os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = old_heartbeat

            self.assertEqual("failed", result["status"])
            self.assertEqual("resource_limit", result["failure_kind"])
            self.assertGreater(result["observed_aggregate_peak_memory_mb"], 1.0)
            self.assertEqual(
                1.0,
                result["resource_limits"][
                    "max_aggregate_child_process_tree_rss_mb"
                ],
            )
            self.assertIn(
                "aggregate child process-tree RSS",
                Path(result["log_path"]).read_text(encoding="utf-8"),
            )
            self.assertEqual(0, governor.snapshot()["participant_count"])

    def test_tripped_aggregate_limit_blocks_later_child_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            launch_marker = root / "launched"
            fake_codex = root / "must_not_launch.py"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                f"Path({str(launch_marker)!r}).write_text('launched')\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            store = ProofStateStore(
                "codex-prelaunch-aggregate-rss-test",
                generation_root=root / "generation",
            )
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)
            governor = AggregateProcessTreeRSSGovernor(1.0)
            stop_event = threading.Event()
            governor.observe("earlier-child", 2.0, stop_event=stop_event)

            result = execute_session(
                store,
                action,
                plan,
                codex_bin=str(fake_codex),
                timeout_sec=5,
                progress_callback=lambda _progress: None,
                stop_event=stop_event,
                aggregate_rss_governor=governor,
                enforce_backend_contract=False,
            )

            self.assertFalse(launch_marker.exists())
            self.assertEqual("failed", result["status"])
            self.assertEqual("resource_limit", result["failure_kind"])
            self.assertIn(
                "resource limit before launch",
                Path(result["log_path"]).read_text(encoding="utf-8"),
            )
            governor.release("earlier-child")


    def test_missing_codex_path_uses_configured_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fallback = Path(temp_dir) / "codex"
            fallback.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fallback.chmod(0o755)
            old = os.environ.get("ALBILICH_CODEX_BIN_FALLBACK")
            os.environ["ALBILICH_CODEX_BIN_FALLBACK"] = str(fallback)
            try:
                self.assertEqual(
                    resolve_codex_executable("/missing/Codex.app/Contents/Resources/codex"),
                    str(fallback),
                )
            finally:
                if old is None:
                    os.environ.pop("ALBILICH_CODEX_BIN_FALLBACK", None)
                else:
                    os.environ["ALBILICH_CODEX_BIN_FALLBACK"] = old

    def test_requested_codex_path_wins_over_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            requested = Path(temp_dir) / "requested-codex"
            requested.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            requested.chmod(0o755)
            old = os.environ.get("ALBILICH_CODEX_BIN_FALLBACK")
            os.environ["ALBILICH_CODEX_BIN_FALLBACK"] = "/missing/fallback-codex"
            try:
                self.assertEqual(resolve_codex_executable(str(requested)), str(requested))
            finally:
                if old is None:
                    os.environ.pop("ALBILICH_CODEX_BIN_FALLBACK", None)
                else:
                    os.environ["ALBILICH_CODEX_BIN_FALLBACK"] = old

    def test_codex_child_default_sandbox_allows_cas_temp_files(self) -> None:
        self.assertEqual(DEFAULT_SANDBOX, "permission-profile:albilich-evidence-capsule")

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

    def test_codex_child_user_config_escape_hatch_is_ignored(self) -> None:
        old = os.environ.get("ALBILICH_CODEX_CHILD_USE_USER_CONFIG")
        os.environ["ALBILICH_CODEX_CHILD_USE_USER_CONFIG"] = "1"
        try:
            self.assertEqual(_codex_child_exec_args(["--json"])[0], "--ignore-user-config")
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

    def test_codex_child_env_exposes_tools_bundled_next_to_codex(self) -> None:
        old_path = os.environ.get("PATH")
        old_gap = os.environ.pop("GAP_BIN", None)
        old_real_gap = os.environ.pop("ALBILICH_REAL_GAP_BIN", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_dir = Path(tmpdir) / "Codex.app" / "Contents" / "Resources"
            tool_dir.mkdir(parents=True)
            codex_bin = tool_dir / "codex"
            rg_bin = tool_dir / "rg"
            codex_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            rg_bin.write_text("#!/bin/sh\nprintf 'rg-ready\\n'\n", encoding="utf-8")
            codex_bin.chmod(0o755)
            rg_bin.chmod(0o755)
            os.environ["PATH"] = "/usr/bin:/bin"
            try:
                env = _codex_child_env(codex_bin=str(codex_bin))
                self.assertIn(str(tool_dir), env["PATH"].split(os.pathsep))
                result = subprocess.run(
                    ["rg"],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                self.assertEqual(result.stdout, "rg-ready\n")
            finally:
                if old_path is None:
                    os.environ.pop("PATH", None)
                else:
                    os.environ["PATH"] = old_path
                if old_gap is not None:
                    os.environ["GAP_BIN"] = old_gap
                if old_real_gap is not None:
                    os.environ["ALBILICH_REAL_GAP_BIN"] = old_real_gap

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

    def test_codex_child_env_honors_documented_gap_path(self) -> None:
        names = (
            "ALBILICH_CODEX_TMPDIR",
            "ALBILICH_REAL_GAP_BIN",
            "ALBILICH_GAP_PATH",
            "GAP_BIN",
            "GAP_PATH",
            "GAP_EXECUTABLE",
            "PATH",
        )
        old = {name: os.environ.get(name) for name in names}
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            real_gap = tmp_path / "documented-gap"
            real_gap.write_text("#!/bin/sh\nprintf 'ARGS=%s\\n' \"$*\"\n", encoding="utf-8")
            real_gap.chmod(0o755)
            os.environ["ALBILICH_CODEX_TMPDIR"] = str(tmp_path / "child")
            os.environ["ALBILICH_GAP_PATH"] = str(real_gap)
            os.environ["PATH"] = "/usr/bin:/bin"
            for name in ("ALBILICH_REAL_GAP_BIN", "GAP_BIN", "GAP_PATH", "GAP_EXECUTABLE"):
                os.environ.pop(name, None)
            try:
                env = _codex_child_env()
                self.assertEqual(env["ALBILICH_REAL_GAP_BIN"], str(real_gap))
                result = subprocess.run(
                    ["gap", "-q"],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                self.assertEqual(result.stdout, "ARGS=-n -q\n")
            finally:
                for name, value in old.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value

    def test_child_log_filter_suppresses_only_known_background_noise(self) -> None:
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
        self.assertTrue(
            _should_suppress_child_log_line(
                "2026-07-27T00:00:00Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `supports_reasoning_summaries` at line 88 column 5\n"
            )
        )
        self.assertTrue(
            _should_suppress_child_log_line(
                "2026-08-20T00:00:00Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 97 column 5\n"
            )
        )
        self.assertTrue(
            _should_suppress_child_log_line(
                "2026-07-27T00:00:00Z ERROR codex_models_manager::manager: failed to refresh available models: timeout waiting for child process to exit\n"
            )
        )
        self.assertTrue(
            _should_suppress_child_log_line(
                "2026-07-27T00:00:00Z WARN codex_analytics::client: failed to send events request: network error\n"
            )
        )
        self.assertFalse(
            _should_suppress_child_log_line(
                "2026-07-27T00:00:00Z WARN codex_core::responses_retry: stream disconnected - retrying sampling request (1/5)\n"
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
                "for _ in range(200):\n"
                "    print('2026-08-20T00:00:00Z ERROR codex_models_manager::manager: failed to renew cache TTL: missing field `base_instructions` at line 97 column 5', flush=True)\n"
                "    time.sleep(0.05)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            store = ProofStateStore("codex-stale-retry-timeout-test", generation_root=root / "generation")
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)
            old_stale = os.environ.get("ALBILICH_CODEX_STALE_RETRY_SECONDS")
            old_retry_grace = os.environ.get("ALBILICH_CODEX_ACTIVE_RETRY_GRACE_SECONDS")
            old_heartbeat = os.environ.get("ALBILICH_UI_HEARTBEAT_SECONDS")
            os.environ["ALBILICH_CODEX_STALE_RETRY_SECONDS"] = "0.2"
            os.environ["ALBILICH_CODEX_ACTIVE_RETRY_GRACE_SECONDS"] = "0.2"
            os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = "0.1"
            try:
                result = execute_session(
                    store,
                    action,
                    plan,
                    codex_bin=str(fake_codex),
                    timeout_sec=5,
                    enforce_backend_contract=False,
                )
            finally:
                if old_stale is None:
                    os.environ.pop("ALBILICH_CODEX_STALE_RETRY_SECONDS", None)
                else:
                    os.environ["ALBILICH_CODEX_STALE_RETRY_SECONDS"] = old_stale
                if old_retry_grace is None:
                    os.environ.pop("ALBILICH_CODEX_ACTIVE_RETRY_GRACE_SECONDS", None)
                else:
                    os.environ["ALBILICH_CODEX_ACTIVE_RETRY_GRACE_SECONDS"] = old_retry_grace
                if old_heartbeat is None:
                    os.environ.pop("ALBILICH_UI_HEARTBEAT_SECONDS", None)
                else:
                    os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = old_heartbeat

            self.assertEqual(result["status"], "timeout")
            self.assertEqual(result["failure_kind"], "stale_stream")
            self.assertLess(result["wall_time_seconds"], 3.0)
            log = Path(result["log_path"]).read_text(encoding="utf-8")
            self.assertIn("stream disconnected - retrying sampling request", log)
            self.assertNotIn("base_instructions", log)
            self.assertIn("no log/token progress after a Codex stream retry", log)
            self.assertIn("Codex stream retry stalled", result["patch_error"])

    def test_active_codex_retry_gets_bounded_reconnect_grace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_codex = root / "fake_codex.py"
            patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": "codex-active-retry-grace-test",
                "base_revision": 0,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "recovered-after-reconnect",
                        "artifact_type": "proof_dossier",
                        "content": "The child recovered within its bounded reconnect grace.",
                        "metadata": {"target_id": "root"},
                    }
                ],
            }
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json, time\n"
                "print('session id: 019ef5aa-0000-7000-9000-retrygrace1', flush=True)\n"
                "print('2026-08-24T00:00:00Z WARN codex_core::responses_retry: stream disconnected - retrying sampling request (2/5 in 374ms)...', flush=True)\n"
                "time.sleep(0.4)\n"
                f"print({json.dumps(json.dumps(patch))}, flush=True)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            store = ProofStateStore("codex-active-retry-grace-test", generation_root=root / "generation")
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)
            old_stale = os.environ.get("ALBILICH_CODEX_STALE_RETRY_SECONDS")
            old_retry_grace = os.environ.get("ALBILICH_CODEX_ACTIVE_RETRY_GRACE_SECONDS")
            old_heartbeat = os.environ.get("ALBILICH_UI_HEARTBEAT_SECONDS")
            os.environ["ALBILICH_CODEX_STALE_RETRY_SECONDS"] = "0.1"
            os.environ["ALBILICH_CODEX_ACTIVE_RETRY_GRACE_SECONDS"] = "0.8"
            os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = "0.05"
            try:
                result = execute_session(
                    store,
                    action,
                    plan,
                    codex_bin=str(fake_codex),
                    timeout_sec=5,
                    enforce_backend_contract=False,
                )
            finally:
                if old_stale is None:
                    os.environ.pop("ALBILICH_CODEX_STALE_RETRY_SECONDS", None)
                else:
                    os.environ["ALBILICH_CODEX_STALE_RETRY_SECONDS"] = old_stale
                if old_retry_grace is None:
                    os.environ.pop("ALBILICH_CODEX_ACTIVE_RETRY_GRACE_SECONDS", None)
                else:
                    os.environ["ALBILICH_CODEX_ACTIVE_RETRY_GRACE_SECONDS"] = old_retry_grace
                if old_heartbeat is None:
                    os.environ.pop("ALBILICH_UI_HEARTBEAT_SECONDS", None)
                else:
                    os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = old_heartbeat

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["patch"]["operations"][0]["artifact_id"], "recovered-after-reconnect")
            log = Path(result["log_path"]).read_text(encoding="utf-8")
            self.assertNotIn("no log/token progress after a Codex stream retry", log)

    def test_old_codex_retry_warning_does_not_poison_later_quiet_period(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_codex = root / "fake_codex.py"
            patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": "codex-old-retry-warning-test",
                "base_revision": 0,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "post-retry-progress-dossier",
                        "artifact_type": "proof_dossier",
                        "content": "The session made ordinary progress after an old retry warning.",
                        "metadata": {"target_id": "root"},
                    }
                ],
            }
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json, time\n"
                "print('session id: 019ef5aa-0000-7000-9000-oldretry1', flush=True)\n"
                "print('2026-06-28T00:00:00Z  WARN codex_core::responses_retry: stream disconnected - retrying sampling request (1/5 in 196ms)...', flush=True)\n"
                "time.sleep(0.2)\n"
                "print('[fake-codex] ordinary progress after the retry warning', flush=True)\n"
                "time.sleep(0.25)\n"
                f"print({json.dumps(json.dumps(patch))}, flush=True)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            store = ProofStateStore("codex-old-retry-warning-test", generation_root=root / "generation")
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)
            old_stale = os.environ.get("ALBILICH_CODEX_STALE_RETRY_SECONDS")
            old_heartbeat = os.environ.get("ALBILICH_UI_HEARTBEAT_SECONDS")
            os.environ["ALBILICH_CODEX_STALE_RETRY_SECONDS"] = "0.15"
            os.environ["ALBILICH_UI_HEARTBEAT_SECONDS"] = "0.05"
            try:
                result = execute_session(
                    store,
                    action,
                    plan,
                    codex_bin=str(fake_codex),
                    timeout_sec=5,
                    enforce_backend_contract=False,
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

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["patch"]["operations"][0]["artifact_id"], "post-retry-progress-dossier")
            log = Path(result["log_path"]).read_text(encoding="utf-8")
            self.assertIn("ordinary progress after the retry warning", log)
            self.assertNotIn("no log/token progress after a Codex stream retry", log)

    def test_nonzero_codex_exits_record_actionable_failure_kinds(self) -> None:
        cases = {
            "usage-limit": ("ERROR: You've hit your usage limit. Try again later.", "usage_limit"),
            "transport": (
                "ERROR: stream disconnected before completion: error sending request for url (https://example.invalid)",
                "transport_error",
            ),
            "launch": ("[albilich] failed to launch Codex session: no such file", "launch_error"),
            "generic": ("ERROR: child backend exited unexpectedly", "process_exit"),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ProofStateStore("codex-failure-kind-test", generation_root=root / "generation")
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)

            for name, (message, expected) in cases.items():
                with self.subTest(name=name):
                    fake_codex = root / f"fake_codex_{name}.py"
                    fake_codex.write_text(
                        "#!/usr/bin/env python3\n"
                        f"print({message!r}, flush=True)\n"
                        "raise SystemExit(1)\n",
                        encoding="utf-8",
                    )
                    fake_codex.chmod(0o755)

                    result = execute_session(
                        store,
                        action,
                        plan,
                        codex_bin=str(fake_codex),
                        timeout_sec=5,
                        enforce_backend_contract=False,
                    )

                    self.assertEqual(result["status"], "failed")
                    self.assertEqual(result["failure_kind"], expected)

    def test_malformed_final_json_gets_one_session_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_codex = root / "fake_codex.py"
            repaired_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": "codex-malformed-json-repair-test",
                "base_revision": 0,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "recovered-proof-dossier",
                        "artifact_type": "proof_dossier",
                        "content": "The repaired patch preserves the mathematical work.",
                        "metadata": {"target_id": "root"},
                    }
                ],
            }
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json, pathlib, sys\n"
                "args = sys.argv\n"
                "out = pathlib.Path(args[args.index('--output-last-message') + 1])\n"
                "state = pathlib.Path(__file__).with_suffix('.state')\n"
                "if not state.exists():\n"
                "    print('session id: 019ef5aa-0000-7000-9000-jsonfix001', flush=True)\n"
                f"    out.write_text(r'{{\"schema_version\":{SCHEMA_VERSION},\"problem_id\":\"codex-malformed-json-repair-test\",\"base_revision\":0,\"actor_role\":\"researcher\",\"target_id\":\"root\",\"operations\":[{{\"op\":\"attach_artifact\",\"artifact_id\":\"broken\",\"artifact_type\":\"proof_dossier\",\"content\":\"G\\uZZZZ H\"}}]}}')\n"
                "    state.write_text('repair')\n"
                "else:\n"
                f"    out.write_text({json.dumps(json.dumps(repaired_patch))})\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            store = ProofStateStore("codex-malformed-json-repair-test", generation_root=root / "generation")
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)

            result = execute_session(
                store,
                action,
                plan,
                codex_bin=str(fake_codex),
                timeout_sec=200,
                enforce_backend_contract=False,
            )

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["patch"]["operations"][0]["artifact_id"], "recovered-proof-dossier")
            self.assertTrue(result["preflight_repair"]["attempted"])
            self.assertIn("not valid Albilich patch JSON", result["preflight_repair"]["errors_before"][0])
            self.assertEqual(result["preflight_repair"]["errors_after"], [])

    def test_repair_sampling_failure_is_visible_and_not_reported_as_measured_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_codex = root / "fake_codex.py"
            repaired_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": "repair-rss-diagnostic",
                "base_revision": 0,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [{"op": "attach_artifact", "artifact_id": "repaired-note", "artifact_type": "proof_dossier", "content": "A repaired note."}],
            }
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib,sys,time\n"
                "out=pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1])\n"
                "marker=pathlib.Path(__file__).with_suffix('.state')\n"
                "if not marker.exists():\n"
                " print('session id: 019ef5aa-0000-7000-9000-jsonfix001',flush=True)\n"
                " out.write_text('malformed patch'); marker.write_text('repair')\n"
                "else:\n"
                f" out.write_text({json.dumps(json.dumps(repaired_patch))}); time.sleep(30)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            store = ProofStateStore("repair-rss-diagnostic", generation_root=root / "generation")
            store.init_problem("Prove the target theorem.")
            action = {"mode": "prove", "target_id": "root"}
            plan = prepare_session(store, action)
            first_pid = None
            def sample(pid):
                nonlocal first_pid
                if first_pid is None:
                    first_pid = pid
                if pid == first_pid:
                    return 24.0
                return _RSSSamplingFailure("children_read_error", pid=pid, path=f"/proc/{pid}/task/{pid}/children", error="unreadable")
            governor = AggregateProcessTreeRSSGovernor(512)
            with mock.patch("agents.generation.phase2.codex_runner._process_tree_rss_mb", side_effect=sample):
                result = execute_session(store, action, plan, codex_bin=str(fake_codex), timeout_sec=200, enforce_backend_contract=False, aggregate_rss_governor=governor, stop_event=threading.Event())
            self.assertEqual("failed", result["status"])
            self.assertEqual("resource_limit", result["failure_kind"])
            self.assertIn("RSS sampling failed", result["patch_error"])
            self.assertIn("children_read_error", result["patch_error"])
            self.assertIn("RSS sampling failed", result["preflight_repair"]["resource_error"])
            self.assertEqual("preflight_repair", result["memory_sampling_failures"][0]["phase"])
            self.assertEqual(24.0, result["peak_memory_mb"])
            self.assertEqual(24.0, result["observed_aggregate_peak_memory_mb"])
            self.assertTrue(governor.snapshot()["tripped"])

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

    def test_session_usage_parser_reads_a_bounded_tail_of_large_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "sessions"
            session_id = "019ef5aa-0000-7000-9000-tokenfix-tail"
            session_path = root / f"rollout-{session_id}.jsonl"
            session_path.parent.mkdir(parents=True)
            with session_path.open("wb") as handle:
                block = b'{"type":"irrelevant"}\n' * 4096
                remaining = MAX_SESSION_USAGE_TAIL_BYTES + 1024
                while remaining > 0:
                    chunk = block[:remaining]
                    handle.write(chunk)
                    remaining -= len(chunk)
                handle.write(b"\n")
                handle.write(
                    (
                        token_count_event(
                            12_345, input_tokens=12_000, output_tokens=345
                        )
                        + "\n"
                    ).encode("utf-8")
                )

            usage = parse_codex_session_usage(session_id, session_root=root)

        self.assertEqual(12_345, usage["total_tokens"])
        self.assertEqual(345, usage["output_tokens"])

    def test_budget_spend_uses_provider_total_without_double_counting_reasoning(self) -> None:
        # Cached input is still processed model usage, while reasoning tokens
        # are already included in output/provider total and are not added twice.
        op = {
            "input_tokens": 1_300_000,
            "cached_input_tokens": 1_200_000,
            "output_tokens": 9_000,
            "reasoning_output_tokens": 5_000,
            "total_tokens": 1_314_000,
        }
        self.assertEqual(run_spend_from_operation(op), 1_314_000)

    def test_budget_spend_falls_back_to_total_without_breakdown(self) -> None:
        # Collapsed CLI footer: only a total, no component breakdown.
        self.assertEqual(run_spend_from_operation({"total_tokens": 6_368}), 6_368)
        self.assertEqual(run_spend_from_operation({"input_tokens": 6_368, "total_tokens": 6_368}), 6_368)

    def test_inconsistent_usage_cannot_understate_resource_consumption(self) -> None:
        usage = parse_token_usage(
            {
                "input_tokens": 100,
                "cached_input_tokens": 120,
                "output_tokens": 20,
                "reasoning_output_tokens": 30,
                "total_tokens": 1,
            }
        )
        self.assertEqual(120, usage["input_tokens"])
        self.assertEqual(30, usage["output_tokens"])
        self.assertEqual(150, usage["total_tokens"])
        self.assertEqual(150, run_spend_from_operation(usage))
        self.assertEqual(
            200,
            run_spend_from_operation(
                {"input_tokens": 100, "output_tokens": 100, "total_tokens": 1}
            ),
        )

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
                    "usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 70,
                        "output_tokens": 20,
                        "reasoning_output_tokens": 5,
                        "total_tokens": 120,
                    },
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
        self.assertEqual(summary["cached_input_tokens"], 70)
        self.assertEqual(summary["output_tokens"], 79)
        self.assertEqual(summary["reasoning_output_tokens"], 15)
        self.assertEqual(summary["wall_time_seconds"], 3.5)
        self.assertEqual(summary["peak_memory_mb"], 222.0)


if __name__ == "__main__":
    unittest.main()
