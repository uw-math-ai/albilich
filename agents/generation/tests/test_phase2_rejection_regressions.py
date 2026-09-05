from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.generation.phase2.authority import PatchAuthority, authority_contract_errors
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.monitor import INDEX_HTML
from agents.generation.phase2.patches import apply_operator_patch, preflight_patch_errors
from agents.generation.phase2.replay import verify_patch_journal
from agents.generation.phase2.research_policy import researcher_mode_summary
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import _apply_scheduled_results, run_workflow


class RejectionRegressionTests(unittest.TestCase):
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
