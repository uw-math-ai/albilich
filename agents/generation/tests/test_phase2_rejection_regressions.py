from __future__ import annotations

import copy
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.generation.phase2.authority import PatchAuthority, authority_contract_errors
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.codex_runner import build_session_prompt, execute_session
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.monitor import INDEX_HTML
from agents.generation.phase2.patches import apply_operator_patch, preflight_patch_errors
from agents.generation.phase2.replay import verify_patch_journal
from agents.generation.phase2.research_policy import researcher_mode_summary
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import _apply_scheduled_results, run_workflow


class RejectionRegressionTests(unittest.TestCase):
    def test_artifact_paths_are_checked_before_repair_without_relaxing_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofStateStore("artifact-preflight", generation_root=Path(tmp))
            store.init_problem("The exact target.")
            capsule = store.state_dir / "contexts" / "context" / "capsule"
            capsule.mkdir(parents=True)
            report = capsule / "report.md"
            report.write_text("The proposed argument has an unresolved gap.", encoding="utf-8")
            proposal = {"operations": [{"op": "attach_artifact", "artifact_id": "report",
                "artifact_type": "verification_report", "path": str(report)}]}
            errors = preflight_patch_errors(proposal, "strict_informal_verifier", store=store)
            self.assertIn("attach_artifact.content and omit path", " ".join(errors))
            self.assertEqual(0, store.get_revision())

            # The writer's existing filename/type exception is not widened.
            writer = copy.deepcopy(proposal)
            writer["operations"][0]["artifact_type"] = "final_paper"
            self.assertEqual([], preflight_patch_errors(writer, "writer", store=store))
            writer["operations"][0]["artifact_id"] = "different-name"
            self.assertIn("invalid attachment path", " ".join(preflight_patch_errors(writer, "writer", store=store)))
            self.assertIn("invalid attachment path", " ".join(preflight_patch_errors(proposal, "writer", store=store)))

            stored = store.state_dir / "artifacts" / "report.md"
            stored.parent.mkdir(exist_ok=True)
            stored.write_text(report.read_text(), encoding="utf-8")
            operation = proposal["operations"][0]
            operation["path"] = str(stored)
            self.assertEqual([], preflight_patch_errors(proposal, "strict_informal_verifier", store=store))
            operation["path"] = str(stored.with_name("missing.md"))
            self.assertIn("does not exist", " ".join(preflight_patch_errors(proposal, "strict_informal_verifier", store=store)))
            outside = Path(tmp) / "outside.md"
            outside.write_text("Not authorized staging.", encoding="utf-8")
            link = stored.with_name("linked.md")
            link.symlink_to(outside)
            operation["path"] = str(link)
            self.assertIn("invalid attachment path", " ".join(preflight_patch_errors(proposal, "strict_informal_verifier", store=store)))
            operation["content"] = report.read_text()
            self.assertIn("must omit path", " ".join(preflight_patch_errors(proposal, "strict_informal_verifier")))
            operation.pop("path")
            self.assertEqual([], preflight_patch_errors(proposal, "strict_informal_verifier", store=store))

    def test_runner_repairs_capsule_report_in_same_session_only_once(self):
        from unittest.mock import Mock
        for repaired_path_is_valid in (True, False):
            with self.subTest(repaired_path_is_valid=repaired_path_is_valid), tempfile.TemporaryDirectory() as tmp:
                store = ProofStateStore("capsule-report-repair", generation_root=Path(tmp))
                store.init_problem("The exact target.")
                capsule = store.state_dir / "contexts" / "context" / "capsule"
                capsule.mkdir(parents=True)
                context_path = capsule / "context.json"
                context_path.write_text("{}", encoding="utf-8")
                report = capsule / "report.md"
                report.write_text("The claimed reduction has an unresolved gap.", encoding="utf-8")
                proposal = {"schema_version": SCHEMA_VERSION, "problem_id": store.problem_id,
                    "base_revision": 0, "actor_role": "strict_informal_verifier", "target_id": "root",
                    "operations": [{"op": "attach_artifact", "artifact_id": "report",
                        "artifact_type": "verification_report", "path": str(report),
                        "metadata": {"verdict": "not_verified", "gaps": ["Unproved reduction."], "blocking_gap": True}}]}
                repaired = copy.deepcopy(proposal)
                if repaired_path_is_valid:
                    repaired["operations"][0]["content"] = report.read_text()
                    repaired["operations"][0].pop("path")
                action = {"mode": "prove", "target_id": "root", "route_id": "route-root"}
                plan = {"actor_role": "strict_informal_verifier", "target_id": "root", "state_revision": 0,
                    "context_hash": "host-context", "context_path": str(context_path), "codex_workdir": str(capsule)}
                commands = []
                def fake_child(command, **kwargs):
                    commands.append(command)
                    output_path = Path(command[command.index("--output-last-message") + 1])
                    output_path.write_text(json.dumps(proposal if len(commands) == 1 else repaired), encoding="utf-8")
                    return Mock(pid=12345, returncode=0, stdout=io.StringIO("session id: same-test-session\n"),
                                **{"wait.return_value": 0, "poll.return_value": 0})
                runner = "agents.generation.phase2.codex_runner."
                with patch(runner + "subprocess.Popen", side_effect=fake_child), \
                     patch(runner + "resolve_codex_executable", return_value="/usr/bin/true"), \
                     patch(runner + "_process_tree_rss_mb", return_value=1.0), \
                     patch(runner + "resolve_cli_usage", return_value={"total_tokens": 0}):
                    result = execute_session(store, action, plan, timeout_sec=600, enforce_backend_contract=False)
                self.assertEqual(2, len(commands), result)
                self.assertIn("resume", commands[1])
                self.assertIn("same-test-session", commands[1])
                self.assertIn("do not repeat the mathematical work", commands[1][-1])
                self.assertTrue(result["preflight_repair"]["attempted"])
                self.assertIn("invalid attachment path", " ".join(result["preflight_repair"]["errors_before"]))
                self.assertEqual(not repaired_path_is_valid, bool(result["preflight_repair"]["errors_after"]))
                self.assertEqual(proposal["operations"][0]["metadata"], result["patch"]["operations"][0]["metadata"])
                self.assertEqual(0, store.get_revision())

    def test_non_writer_prompt_requires_inline_report_without_changing_writer(self):
        for role in ("strict_informal_verifier", "researcher", "phd_advisor", "writer"):
            prompt = build_session_prompt(context_path=Path("context.json"),
                action={"mode": "prove", "target_id": "root"}, actor_role=role)
            self.assertEqual(role != "writer", "Attach reports using the complete text" in prompt)

    def test_parallel_result_keeps_original_context_revision_during_safe_rebase(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofStateStore("parallel-authority", generation_root=Path(tmp))
            store.init_problem("The exact target.")
            advanced = apply_operator_patch(store, {
                "schema_version": SCHEMA_VERSION, "problem_id": store.problem_id,
                "base_revision": 0, "actor_role": "researcher", "target_id": "root",
                "operations": [{"op": "attach_artifact", "artifact_id": "sibling", "artifact_type": "research_notebook", "content": "Independent sibling work."}],
            })
            self.assertTrue(advanced.accepted, advanced.errors)
            item = {"action": {"mode": "triage_routes", "target_id": "root"},
                    "session_plan": {"actor_role": "phd_advisor", "state_revision": 0, "target_id": "root", "context_hash": "original-packet", "authorized_existing_entity_ids": ["root"]},
                    "session_web_search": "disabled", "is_companion": True, "parallel_group_size": 2,
                    "durable_validation_errors": [],
                    "execution": {"run_id": "advisor", "status": "completed", "patch": {
                        "schema_version": SCHEMA_VERSION, "problem_id": store.problem_id, "base_revision": 0,
                        "actor_role": "phd_advisor", "target_id": "root", "operations": [{"op": "attach_artifact",
                        "artifact_id": "advisor-note", "artifact_type": "advisor_report", "content": "Independent route analysis."}]}}}
            with patch("agents.generation.phase2.workflow._prepare_and_record_scheduled_result"), patch("agents.generation.phase2.workflow._record_execution_metrics", return_value={"accepted": True}):
                result = _apply_scheduled_results(store, [item], model="test", reasoning_effort="xhigh", sandbox="workspace-write")[0]
            self.assertTrue(result["patch_outcome"]["accepted"], result["patch_outcome"])
            self.assertTrue(verify_patch_journal(store)["valid"])

    def test_preflight_catches_wrong_problem_and_undisclosed_evidence(self):
        authority = PatchAuthority(source="session", actor_role="researcher", target_id="root", context_hash="packet")
        proposal = {"actor_role": "researcher", "target_id": "root", "base_revision": 0, "problem_id": "wrong",
                    "operations": [{"op": "attach_artifact", "artifact_id": "note", "artifact_type": "research_notebook", "metadata": {"source_artifact_ids": ["undisclosed"]}}]}
        errors = preflight_patch_errors(proposal, "researcher", authority=authority, problem_id="expected")
        self.assertIn("problem_id", " ".join(errors))
        self.assertIn("out-of-scope", " ".join(errors))

    def test_advisor_passes_do_not_erase_researcher_mode_history(self):
        runs = [{"run_id": "research", "actor_role": "researcher", "researcher_work_mode": "offline", "created_at": "001"}]
        runs += [{"run_id": f"advisor-{i}", "actor_role": "phd_advisor", "created_at": f"{i:03d}"} for i in range(2, 50)]
        self.assertEqual("offline", researcher_mode_summary({"runs": runs})["current"]["work_mode"])

    def test_monitor_labels_budget_and_control_state_honestly(self):
        self.assertNotIn("Cached (free)", INDEX_HTML)
        self.assertNotIn("cached excluded", INDEX_HTML)
        self.assertIn('control === "paused"', INDEX_HTML)
        self.assertIn('control === "pause_requested"', INDEX_HTML)
        self.assertIn('snap.revision}:${mon.source', INDEX_HTML)

    def test_supported_identifier_aliases_remain_scope_checked(self):
        authority = PatchAuthority(source="session", actor_role="researcher", target_id="root",
                                   context_hash="host-packet", authorized_existing_ids=("proof",))
        for field, value in (("add_evidence_artifact_ids", ["proof"]),
                             ("premise_ids", ["root"]), ("conclusion_id", "root"),
                             ("target_claim_id", "root")):
            with self.subTest(field=field):
                proposal = {"actor_role": "researcher", "target_id": "root", "base_revision": 0,
                            "operations": [{"op": "update_inference", "inference_id": "root", field: value}]}
                self.assertEqual([], authority_contract_errors(proposal, authority))
                proposal["operations"][0][field] = ["hidden"] if isinstance(value, list) else "hidden"
                self.assertIn("out-of-scope", " ".join(authority_contract_errors(proposal, authority)))

    def test_compression_contract_is_disclosed_even_when_optional_and_preflight_checks_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofStateStore("compression-regression", generation_root=Path(tmp))
            store.init_problem("The exact target.")
            manifest = build_context_manifest(store, max_chars=30000,
                action={"mode": "triage_routes", "target_id": "root", "advisor_global_synthesis_required": True})
            metadata = copy.deepcopy(manifest["proof_compression_contract"]["metadata_shape"])
            metadata["minimal_proof_skeleton"]["root"] = "root"
            proposal = {"operations": [{"op": "attach_artifact", "artifact_id": "compression",
                                        "artifact_type": "proof_compression", "metadata": metadata}]}
            self.assertEqual([], preflight_patch_errors(proposal, "phd_advisor"))
            del metadata["strategy_schema_version"]
            del metadata["minimal_proof_skeleton"]["root"]
            errors = " ".join(preflight_patch_errors(proposal, "phd_advisor"))
            self.assertIn("strategy_schema_version=1", errors)
            self.assertIn("requires nonempty root", errors)

    def test_three_rejected_waves_stop_without_writer_and_expose_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofStateStore("rejection-breaker", generation_root=Path(tmp))
            store.init_problem("The exact target.")
            calls = []
            def executor(*, action, session_plan, **kwargs):
                calls.append(action["mode"])
                return {"run_id": f"rejected-{len(calls)}", "actor_role": session_plan["actor_role"],
                        "status": "completed", "returncode": 0, "wall_time_seconds": 1,
                        "peak_memory_mb": 1, "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                        "patch": {"schema_version": SCHEMA_VERSION, "problem_id": store.problem_id,
                                  "base_revision": session_plan["state_revision"], "actor_role": session_plan["actor_role"],
                                  "target_id": "root", "operations": [{"op": "attach_artifact",
                                  "artifact_id": f"bad-{len(calls)}", "artifact_type": "research_notebook",
                                  "content": "A rejected output.", "unknown_claim_id": "hidden"}]}}
            result = run_workflow(store, steps=10, execute=True, executor=executor,
                parallel_librarian_verifier=False, parallel_branches=0,
                stop_on_rejection=False, write_on_stop=True, write_console=False)
            self.assertEqual(3, len(calls), json.dumps(result["steps"], default=str)[-10000:])
            self.assertNotIn("write", calls)
            self.assertEqual("awaiting_human", store.get_run_status())
            self.assertEqual("execution_configuration_required", result["steps"][-1]["terminal_classification"])
            self.assertTrue(verify_patch_journal(store)["valid"])
            manifest = build_context_manifest(store, max_chars=30000, action={"mode": calls[-1], "target_id": "root"})
            self.assertIn("unknown_claim_id", json.dumps(manifest["recent_patch_rejections"]))
            self.assertEqual(3, sum(bool(row.get("error_artifact_id")) for row in store.get_state()["runs"]))

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to execute the browser fallback regression")
    def test_dynamic_math_is_visible_without_mathjax(self):
        source = INDEX_HTML[INDEX_HTML.index("function typesetPending("):INDEX_HTML.index("window.addEventListener('load'", INDEX_HTML.index("function typesetPending("))]
        script = """
const assert = require('node:assert/strict');
const window = {};
let mathJaxQueue = Promise.resolve();
let removed = false, failed = false;
const node = {removeAttribute: key => {removed = key === 'data-math-pending';},
              classList: {add: key => {failed = key === 'math-typeset-failed';}}};
const document = {querySelectorAll: () => [node]};
""" + source + "typesetPending(document); assert(removed); assert(failed);"
        subprocess.run([shutil.which("node"), "-e", script], check=True, capture_output=True, text=True)
        self.assertNotIn('.math-tex[data-math-pending="1"] { visibility: hidden;', INDEX_HTML)
