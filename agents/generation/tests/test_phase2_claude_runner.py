import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from agents.generation.phase2.claude_runner import (
    _claude_usage,
    _claude_child_env,
    _spawn_pty_session,
    build_claude_command,
    execute_claude_session,
    make_claude_executor,
    parse_claude_envelope,
    latest_stream_usage,
    parse_stream_events,
    stream_activity_tail,
)
from agents.generation.phase2.codex_runner import AggregateProcessTreeRSSGovernor
from agents.generation.phase2.dispatch_execution import (
    CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY,
    CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE,
    CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
    CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE,
)
from agents.generation.phase2.codex_runner import prepare_session
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.store import ProofStateStore


def _write_fake_claude(path: Path, patch: dict, *, usage: dict, session_id: str = "sess-test") -> None:
    envelope = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": json.dumps(patch),
        "session_id": session_id,
        "usage": usage,
    }
    script = (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({json.dumps(json.dumps(envelope))})\n"
    )
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


class ClaudeRunnerTest(unittest.TestCase):
    def test_claude_session_enforces_shared_aggregate_rss_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_bin = root / "fake-memory-claude"
            fake_bin.write_text(
                "#!/usr/bin/env python3\n"
                "import time\n"
                "memory = bytearray(16 * 1024 * 1024)\n"
                "print('memory-ready', flush=True)\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            fake_bin.chmod(0o755)
            store = ProofStateStore(
                "claude-aggregate-rss-test",
                generation_root=root / "generation",
            )
            store.init_problem("Prove the root theorem.")
            action = {"mode": "prove", "target_id": "root"}
            session_plan = prepare_session(store, action, max_context_chars=8_000)
            governor = AggregateProcessTreeRSSGovernor(1.0)

            execution = execute_claude_session(
                store,
                action,
                session_plan,
                claude_bin=str(fake_bin),
                timeout_sec=5,
                progress_callback=lambda _progress: None,
                stop_event=threading.Event(),
                aggregate_rss_governor=governor,
                enforce_backend_contract=False,
            )

            self.assertEqual("failed", execution["status"])
            self.assertEqual("resource_limit", execution["failure_kind"])
            self.assertGreater(
                execution["observed_aggregate_peak_memory_mb"],
                1.0,
            )
            self.assertEqual(
                1.0,
                execution["resource_limits"][
                    "max_aggregate_child_process_tree_rss_mb"
                ],
            )
            self.assertEqual(0, governor.snapshot()["participant_count"])

    def test_pty_capture_discards_output_after_hard_byte_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            raw_path = root / "stream.jsonl"
            log_path = root / "claude.log"
            reached = threading.Event()
            with log_path.open("w", encoding="utf-8") as log_file:
                process, reader = _spawn_pty_session(
                    [sys.executable, "-c", "print('x' * 10000)"],
                    cwd=root,
                    raw_path=raw_path,
                    log_file=log_file,
                    limit_event=reached,
                    max_bytes=64,
                )
                self.assertEqual(0, process.wait(timeout=10))
                reader.join(timeout=2)
            self.assertTrue(reached.is_set())
            self.assertLessEqual(raw_path.stat().st_size, 64)

    def test_build_claude_command_shape(self) -> None:
        cmd = build_claude_command(
            prompt="do the thing",
            claude_bin="claude",
            model="claude-opus-4-8",
            permission_mode="dontAsk",
            max_turns=12,
            effort="xhigh",
            add_dirs=["/repo"],
        )
        self.assertEqual(cmd[0], "claude")
        self.assertIn("-p", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-opus-4-8")
        self.assertEqual(cmd[cmd.index("--effort") + 1], "xhigh")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        # Default is stream-json (timeout-resilient) and requires --verbose.
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", cmd)
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "12")
        self.assertEqual(cmd[cmd.index("--add-dir") + 1], "/repo")
        settings = json.loads(cmd[cmd.index("--settings") + 1])
        self.assertTrue(settings["sandbox"]["enabled"])
        self.assertTrue(settings["sandbox"]["failIfUnavailable"])
        self.assertEqual(settings["sandbox"]["network"]["deniedDomains"], ["*"])
        self.assertIn("--tools", cmd)
        # Prompt is the trailing positional argument.
        self.assertEqual(cmd[-1], "do the thing")

    def test_bypass_permissions_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "bypassPermissions"):
            build_claude_command(prompt="unsafe", permission_mode="bypassPermissions")

    def test_caller_cannot_disable_the_claude_sandbox(self) -> None:
        unsafe = {
            "disableAllHooks": True,
            "permissions": {"defaultMode": "dontAsk", "deny": ["mcp__*", "Agent", "Skill"]},
            "sandbox": {
                "enabled": False,
                "failIfUnavailable": False,
                "allowUnsandboxedCommands": True,
                "filesystem": {
                    "denyRead": ["/", "~/"],
                    "allowRead": ["."],
                    "denyWrite": ["/", "~/"],
                    "allowWrite": ["."],
                },
                "network": {"deniedDomains": ["*"]},
            },
        }
        with self.assertRaisesRegex(ValueError, "sandbox must be enabled"):
            build_claude_command(prompt="unsafe", settings=unsafe)

    def test_caller_cannot_load_user_settings_or_delegated_tools(self) -> None:
        with self.assertRaisesRegex(ValueError, "setting_sources must be explicitly empty"):
            build_claude_command(prompt="unsafe", setting_sources=["user"])
        with self.assertRaisesRegex(ValueError, "forbidden delegated capabilities"):
            build_claude_command(prompt="unsafe", tools=["Read", "Agent"])

    def test_parse_stream_prefers_result_event(self) -> None:
        stream = "\n".join([
            json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "interim"}]}}),
            json.dumps({"type": "result", "subtype": "success", "result": "FINAL", "session_id": "s1",
                        "usage": {"input_tokens": 5, "cache_read_input_tokens": 100, "output_tokens": 9}}),
        ])
        parsed = parse_stream_events(stream)
        self.assertEqual(parsed["result"], "FINAL")
        self.assertEqual(parsed["session_id"], "s1")
        self.assertFalse(parsed["is_error"])
        self.assertEqual(parsed["usage"]["input_tokens"], 105)
        self.assertEqual(parsed["usage"]["output_tokens"], 9)

    def test_latest_stream_usage_tracks_in_flight_tokens(self) -> None:
        stream = "\n".join([
            json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 100, "output_tokens": 10}}}),
            json.dumps({"type": "stream_event", "event": {"type": "message_delta",
                        "usage": {"input_tokens": 100, "cache_read_input_tokens": 5000, "output_tokens": 220}}}),
        ])
        usage = latest_stream_usage(stream)
        # Picks the heaviest usage object seen so far (the later delta).
        self.assertEqual(usage["input_tokens"], 5100)
        self.assertEqual(usage["output_tokens"], 220)

    def test_stream_activity_tail_renders_tool_calls(self) -> None:
        stream = "\n".join([
            json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Let me compute the h-vector."},
                {"type": "tool_use", "name": "Bash", "input": {"command": "M2 hStarMat.m2"}}]}}),
        ])
        tail = stream_activity_tail(stream)
        self.assertIn("Let me compute", tail)
        self.assertIn("⏵ Bash: M2 hStarMat.m2", tail)

    def test_parse_stream_salvages_last_assistant_on_no_result(self) -> None:
        # Simulates a session killed at the timeout before the result event.
        stream = "\n".join([
            json.dumps({"type": "system", "subtype": "init", "session_id": "s2"}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "early thought"}]}}),
            json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": '{"schema_version": 1, "operations": []}'}]}}),
        ])
        parsed = parse_stream_events(stream)
        self.assertIn('"schema_version": 1', parsed["result"])
        self.assertEqual(parsed["session_id"], "s2")

    def test_claude_usage_sums_cache_into_full_input(self) -> None:
        usage = _claude_usage(
            {"usage": {"input_tokens": 10, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 500, "output_tokens": 50}}
        )
        self.assertEqual(usage["input_tokens"], 1510)
        # Only cache reads count as cached/free; cache creation is new work.
        self.assertEqual(usage["cached_input_tokens"], 1000)
        self.assertEqual(usage["output_tokens"], 50)
        self.assertEqual(usage["total_tokens"], 1560)

    def test_parse_envelope_handles_trailing_stderr_lines(self) -> None:
        env = parse_claude_envelope('warning: noise\n{"type":"result","result":"hi","session_id":"s"}\n')
        self.assertEqual(env.get("result"), "hi")

    def test_execute_claude_session_parses_patch_and_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store = ProofStateStore("claude-runner-test", generation_root=tmp / "generation")
            store.init_problem("Prove the root theorem.")
            action = {"mode": "prove", "target_id": "root"}
            session_plan = prepare_session(store, action, max_context_chars=8_000)

            patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": session_plan["state_revision"],
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "claude-notebook",
                        "artifact_type": "research_notebook",
                        "metadata": {"target_id": "root"},
                        "content": "A direct attempt via the Claude backend.",
                    }
                ],
                "rationale": "claude backend smoke",
            }
            fake_bin = tmp / "fake-claude"
            _write_fake_claude(
                fake_bin,
                patch,
                usage={"input_tokens": 12, "cache_read_input_tokens": 2000, "output_tokens": 80},
            )

            execution = execute_claude_session(
                store,
                action,
                session_plan,
                claude_bin=str(fake_bin),
                timeout_sec=30,
                enforce_backend_contract=False,
            )

            self.assertEqual(execution["status"], "completed", execution.get("patch_error"))
            self.assertEqual(execution["session_id"], "sess-test")
            self.assertIsNotNone(execution["patch"])
            self.assertEqual(execution["patch"]["operations"][0]["artifact_id"], "claude-notebook")
            self.assertEqual(execution["output_artifact_ids"], ["claude-notebook"])
            self.assertEqual(execution["usage"]["input_tokens"], 2012)
            self.assertEqual(execution["usage"]["total_tokens"], 2092)
            self.assertEqual(
                "supervisor polling plus bounded host capture",
                execution["resource_limits"]["enforcement"],
            )
            self.assertTrue(Path(execution["final_message_path"]).exists())

    def test_make_claude_executor_matches_workflow_call_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store = ProofStateStore("claude-executor-test", generation_root=tmp / "generation")
            store.init_problem("Prove the root theorem.")
            action = {"mode": "prove", "target_id": "root"}
            session_plan = prepare_session(store, action, max_context_chars=8_000)
            patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": session_plan["state_revision"],
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {"op": "attach_artifact", "artifact_id": "exec-note", "artifact_type": "research_notebook", "content": "x"}
                ],
                "rationale": "exec",
            }
            fake_bin = tmp / "fake-claude"
            _write_fake_claude(fake_bin, patch, usage={"input_tokens": 1, "output_tokens": 1})
            executor = make_claude_executor(
                claude_bin=str(fake_bin),
                timeout_sec=30,
                enforce_backend_contract=False,
            )
            self.assertEqual(
                CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
                getattr(executor, CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE),
            )
            self.assertEqual(
                CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY,
                getattr(executor, CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE),
            )
            # workflow.py calls executor(store=..., action=..., session_plan=...)
            execution = dict(executor(store=store, action=action, session_plan=session_plan))
            self.assertEqual(execution["status"], "completed")
            self.assertEqual(execution["patch"]["operations"][0]["artifact_id"], "exec-note")


class CasToolingManifestTest(unittest.TestCase):
    def test_existing_cas_asset_is_content_bound(self) -> None:
        from agents.generation.phase2.context_builder import _cas_tooling_card

        with tempfile.TemporaryDirectory() as tmpdir:
            asset = Path(tmpdir) / "check.py"
            asset.write_text("print(42)\n", encoding="utf-8")
            prev = os.environ.get("ALBILICH_CAS_ASSETS")
            os.environ["ALBILICH_CAS_ASSETS"] = str(asset)
            try:
                card = _cas_tooling_card()
            finally:
                if prev is None:
                    os.environ.pop("ALBILICH_CAS_ASSETS", None)
                else:
                    os.environ["ALBILICH_CAS_ASSETS"] = prev
            self.assertEqual(
                hashlib.sha256(b"print(42)\n").hexdigest(),
                card["assets"][0]["sha256"],
            )

    def test_cas_assets_surface_in_manifest_and_search_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("cas-tooling-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Prove the root theorem.")
            asset = "experiment data/eur_matroid_h_vectors/bibliography/hStar Matroid Upload.m2"
            prev = os.environ.get("ALBILICH_CAS_ASSETS")
            os.environ["ALBILICH_CAS_ASSETS"] = f"{asset}::Eur h* matroid Macaulay2 helper"
            try:
                # Large budget so advisory blocks (local_search_policy) are not trimmed.
                manifest = build_context_manifest(
                    store, target_id="root", action={"mode": "prove", "target_id": "root"}, max_chars=400_000
                )
            finally:
                if prev is None:
                    os.environ.pop("ALBILICH_CAS_ASSETS", None)
                else:
                    os.environ["ALBILICH_CAS_ASSETS"] = prev

            self.assertIn("cas_tooling", manifest)
            self.assertEqual(manifest["cas_tooling"]["assets"][0]["path"], asset)
            self.assertIn(asset, manifest["local_search_policy"].get("allowed_cas_assets", []))
            self.assertTrue(any("cas_tooling" in line for line in manifest["instructions"]))

    def test_no_cas_tooling_without_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("cas-tooling-absent-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Prove the root theorem.")
            prev = os.environ.pop("ALBILICH_CAS_ASSETS", None)
            try:
                manifest = build_context_manifest(store, target_id="root", action={"mode": "prove", "target_id": "root"})
            finally:
                if prev is not None:
                    os.environ["ALBILICH_CAS_ASSETS"] = prev
            self.assertNotIn("cas_tooling", manifest)

    def test_cas_assets_hidden_from_advisor_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("cas-tooling-advisor-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Prove the root theorem.")
            prev = os.environ.get("ALBILICH_CAS_ASSETS")
            os.environ["ALBILICH_CAS_ASSETS"] = "helpers/check.g::GAP helper"
            try:
                manifest = build_context_manifest(
                    store,
                    target_id="root",
                    action={"mode": "triage_routes", "target_id": "root"},
                    max_chars=400_000,
                )
            finally:
                if prev is None:
                    os.environ.pop("ALBILICH_CAS_ASSETS", None)
                else:
                    os.environ["ALBILICH_CAS_ASSETS"] = prev

            self.assertFalse(manifest["role_context_policy"]["cas_access"])
            self.assertEqual(manifest["role_context_policy"]["context_role"], "phd_advisor")
            self.assertNotIn("cas_tooling", manifest)
            self.assertNotIn("cas_trigger_policy", manifest)
            self.assertEqual(manifest["local_search_policy"].get("allowed_cas_assets", []), [])
            self.assertEqual(manifest["patch_contract"]["context_role"], "phd_advisor")
            templates = manifest["patch_contract"]["operation_templates"]
            artifact_templates = [
                template
                for template in templates
                if template.get("op") == "attach_artifact"
            ]
            self.assertTrue(artifact_templates)
            self.assertIn("advisor_report", artifact_templates[0]["fields"][1])
            self.assertIn("route_triage_report", artifact_templates[0]["fields"][1])

    def test_claude_child_env_sets_role_scoped_cas_policy(self) -> None:
        researcher_env = _claude_child_env("researcher")
        advisor_env = _claude_child_env("phd_advisor")
        self.assertEqual(researcher_env["ALBILICH_CAS_ENABLED"], "1")
        self.assertEqual(researcher_env["ALBILICH_CAS_ROLE"], "researcher")
        self.assertEqual(advisor_env["ALBILICH_CAS_ENABLED"], "0")
        self.assertEqual(advisor_env["ALBILICH_CAS_ROLE"], "phd_advisor")

    def test_multiple_assets_infer_backends_and_survive_colons(self) -> None:
        from agents.generation.phase2.context_builder import _cas_tooling_card
        prev = os.environ.get("ALBILICH_CAS_ASSETS")
        # Newline-separated; paths/descriptions contain ':' which must not split.
        os.environ["ALBILICH_CAS_ASSETS"] = "\n".join([
            "dir/build.m2::Macaulay2 helper",
            "dir/examples.jsonl::300k h*-vectors: palindromic/unimodal flags",
            "dir/gen.jl::Julia generator",
        ])
        try:
            card = _cas_tooling_card()
        finally:
            if prev is None:
                os.environ.pop("ALBILICH_CAS_ASSETS", None)
            else:
                os.environ["ALBILICH_CAS_ASSETS"] = prev
        self.assertEqual(len(card["assets"]), 3)
        kinds = {a["path"]: a["backend"] for a in card["assets"]}
        self.assertEqual(kinds["dir/build.m2"], "Macaulay2 (M2)")
        self.assertEqual(kinds["dir/examples.jsonl"], "dataset")
        self.assertEqual(kinds["dir/gen.jl"], "Julia")
        # Description with a ':' is preserved intact, not split into a junk asset.
        jsonl = next(a for a in card["assets"] if a["path"].endswith(".jsonl"))
        self.assertIn("palindromic/unimodal", jsonl["description"])
        self.assertEqual(set(card["backends"]), {"Macaulay2 (M2)", "dataset", "Julia"})


if __name__ == "__main__":
    unittest.main()
