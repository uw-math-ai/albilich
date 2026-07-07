from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import (
    _blocked_by_pending_priority_barrier,
    _merge_priority,
    _record_parallel_signals,
    _record_execution_metrics,
    _rebase_parallel_patch_if_safe,
    _remaining_wall_seconds,
    _recoverable_parallel_stale_patch,
    _stop_writer_safety_blocker,
    run_workflow,
)


class WorkflowOutageBreakerTests(unittest.TestCase):
    def test_backend_outage_backs_off_and_refunds_steps(self) -> None:
        import agents.generation.phase2.workflow as workflow_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-outage-breaker-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                if calls["count"] <= 2:
                    return {
                        "run_id": f"outage-{calls['count']}",
                        "actor_role": "researcher",
                        "status": "failed",
                        "returncode": 1,
                        "wall_time_seconds": 5.0,
                        "peak_memory_mb": 1.0,
                        "usage": {"input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 0},
                        "session_id": "",
                        "patch": None,
                        "patch_error": "stream disconnected before completion: error sending request",
                        "output_artifact_ids": [],
                        "final_message_path": "",
                        "log_path": "",
                        "model": "fake",
                        "reasoning_effort": "xhigh",
                        "sandbox": "workspace-write",
                        "web_search": "disabled",
                    }
                return {
                    "run_id": f"recovered-{calls['count']}",
                    "actor_role": "researcher",
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 3.0,
                    "peak_memory_mb": 1.0,
                    "usage": {"input_tokens": 20, "output_tokens": 5, "reasoning_output_tokens": 0, "total_tokens": 25},
                    "session_id": f"session-{calls['count']}",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": "researcher",
                        "target_id": action.get("target_id", "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": f"post-outage-dossier-{calls['count']}",
                                "artifact_type": "proof_dossier",
                                "content": f"Recovered pass {calls['count']} after the outage cleared.",
                                "metadata": {"target_id": action.get("target_id", "root")},
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": [f"post-outage-dossier-{calls['count']}"],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            old_base = workflow_mod.OUTAGE_BACKOFF_BASE_SECONDS
            workflow_mod.OUTAGE_BACKOFF_BASE_SECONDS = 0
            try:
                result = run_workflow(
                    store,
                    steps=2,
                    execute=True,
                    parallel_librarian_verifier=False,
                    write_on_stop=False,
                    write_console=False,
                    executor=executor,
                )
            finally:
                workflow_mod.OUTAGE_BACKOFF_BASE_SECONDS = old_base

            outage_entries = [e for e in result["steps"] if e.get("outage_suspected")]
            self.assertEqual(len(outage_entries), 2)
            self.assertEqual(outage_entries[0]["outage_streak"], 1)
            self.assertEqual(outage_entries[1]["outage_streak"], 2)
            completed = [
                e
                for e in result["steps"]
                if isinstance(e.get("execution"), dict) and e["execution"].get("status") == "completed"
            ]
            # The two outage waves were refunded: the full 2-step budget still ran.
            self.assertEqual(len(completed), 2)
            self.assertEqual(calls["count"], 4)


class WorkflowParallelRebaseTests(unittest.TestCase):
    def test_init_creates_parallel_exchange_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-exchange-init-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            path = store.state_dir / "parallel_exchange.jsonl"

            self.assertTrue(path.exists())
            self.assertEqual("", path.read_text(encoding="utf-8"))

    def test_scheduler_state_recent_runs_preserve_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-recent-run-id-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "run-visible-in-scheduler-state",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "state_revision": 0,
                            "context_revision": 0,
                            "search_intent": "parallel_direct_solve",
                            "input_tokens": 1,
                            "output_tokens": 2,
                            "reasoning_output_tokens": 0,
                            "total_tokens": 3,
                            "wall_time_seconds": 1.0,
                            "peak_memory_mb": 10.0,
                            "status": "completed",
                        }
                    ],
                    "rationale": "record run metrics",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            recent = store.get_scheduler_state()["recent_runs"]

        self.assertEqual(recent[0]["run_id"], "run-visible-in-scheduler-state")
        self.assertEqual(recent[0]["search_intent"], "parallel_direct_solve")

    def test_failed_execution_metrics_persist_failure_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-failed-run-artifact-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = _record_execution_metrics(
                store,
                action={"mode": "prove", "target_id": "root"},
                session_plan={
                    "actor_role": "researcher",
                    "state_revision": 0,
                    "context_hash": "ctx",
                    "search_intent": "parallel_direct_solve",
                },
                execution={
                    "run_id": "run:stale/retry",
                    "actor_role": "researcher",
                    "status": "timeout",
                    "returncode": -15,
                    "wall_time_seconds": 12.0,
                    "peak_memory_mb": 3.0,
                    "usage": {"input_tokens": 1, "output_tokens": 2, "reasoning_output_tokens": 0, "total_tokens": 3},
                    "patch_error": "Codex stream retry stalled before a patch was produced.",
                    "log_path": "/tmp/codex.log",
                    "final_message_path": "/tmp/final_patch.json",
                },
                status="timeout",
                model="gpt-test",
                reasoning_effort="xhigh",
                sandbox="workspace-write",
                web_search="disabled",
            )

            self.assertTrue(outcome["accepted"], outcome["errors"])
            with closing(store.connect()) as conn:
                run = conn.execute("SELECT error_artifact_id FROM runs WHERE run_id = ?", ("run:stale/retry",)).fetchone()
                self.assertIsNotNone(run)
                artifact_id = run["error_artifact_id"]
                self.assertTrue(artifact_id.startswith("session_failure_run_stale_retry"))
                artifact = conn.execute(
                    "SELECT artifact_type, path, content_summary FROM artifacts WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()
                self.assertIsNotNone(artifact)
                self.assertEqual(artifact["artifact_type"], "session_failure_report")
                self.assertIn("Codex stream retry stalled", artifact["content_summary"])
                content = Path(artifact["path"]).read_text(encoding="utf-8")
                self.assertIn("run:stale/retry", content)
                self.assertIn("Codex stream retry stalled", content)

    def test_recoverable_researcher_stale_retry_does_not_stop_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-stale-retry-recovery-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                if calls["count"] == 1:
                    return {
                        "run_id": "researcher-stale-retry",
                        "actor_role": "researcher",
                        "status": "timeout",
                        "returncode": -15,
                        "wall_time_seconds": 12.0,
                        "peak_memory_mb": 4.0,
                        "usage": {"input_tokens": 10, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 10},
                        "session_id": "session-stale",
                        "patch": None,
                        "patch_error": "Codex stream retry stalled with no further log/token progress before a patch was produced.",
                        "output_artifact_ids": [],
                        "final_message_path": "",
                        "log_path": "",
                        "model": "fake",
                        "reasoning_effort": "xhigh",
                        "sandbox": "workspace-write",
                        "web_search": "disabled",
                    }
                return {
                    "run_id": "researcher-recovered",
                    "actor_role": "researcher",
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 3.0,
                    "peak_memory_mb": 4.0,
                    "usage": {"input_tokens": 20, "output_tokens": 5, "reasoning_output_tokens": 0, "total_tokens": 25},
                    "session_id": "session-recovered",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": "researcher",
                        "target_id": action.get("target_id", "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": "recovered-proof-dossier",
                                "artifact_type": "proof_dossier",
                                "content": "Recovered researcher pass with a concrete mathematical artifact.",
                                "metadata": {"target_id": action.get("target_id", "root")},
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": ["recovered-proof-dossier"],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            old = os.environ.get("ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS")
            os.environ["ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"] = "1"
            try:
                result = run_workflow(
                    store,
                    steps=2,
                    execute=True,
                    parallel_librarian_verifier=False,
                    write_on_stop=False,
                    write_console=False,
                    executor=executor,
                )
            finally:
                if old is None:
                    os.environ.pop("ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS", None)
                else:
                    os.environ["ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"] = old

            self.assertEqual(calls["count"], 2)
            self.assertTrue(result["steps"][0]["recoverable_failure"])
            self.assertEqual(result["steps"][0]["execution_phase"], "recovering_after_stale_retry")
            self.assertEqual(result["steps"][1]["execution"]["status"], "completed")
            with closing(store.connect()) as conn:
                self.assertIsNotNone(
                    conn.execute("SELECT 1 FROM artifacts WHERE artifact_id = ?", ("recovered-proof-dossier",)).fetchone()
                )

    def test_recoverable_verifier_stale_retry_does_not_stop_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-verifier-stale-retry-recovery-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "route-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete proof packet ready for strict verification.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-proof",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the assembled proof dossier.",
                            "evidence_artifact_ids": ["route-proof-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-proof",
                            "route_id": "route-root-proof",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof packet implies the target.",
                            "evidence_artifact_ids": ["route-proof-dossier"],
                        },
                    ],
                    "rationale": "seed verifier-ready route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                self.assertEqual(action.get("route_id"), "route-root-proof")
                if calls["count"] == 1:
                    return {
                        "run_id": "verifier-stale-retry",
                        "actor_role": "strict_informal_verifier",
                        "status": "timeout",
                        "returncode": -15,
                        "wall_time_seconds": 12.0,
                        "peak_memory_mb": 4.0,
                        "usage": {"input_tokens": 10, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 10},
                        "session_id": "session-stale-verifier",
                        "patch": None,
                        "patch_error": "Codex stream retry stalled with no further log/token progress before a patch was produced.",
                        "output_artifact_ids": [],
                        "final_message_path": "",
                        "log_path": "",
                        "model": "fake",
                        "reasoning_effort": "xhigh",
                        "sandbox": "workspace-write",
                        "web_search": "disabled",
                    }
                return {
                    "run_id": "verifier-recovered",
                    "actor_role": "strict_informal_verifier",
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 3.0,
                    "peak_memory_mb": 4.0,
                    "usage": {"input_tokens": 20, "output_tokens": 5, "reasoning_output_tokens": 0, "total_tokens": 25},
                    "session_id": "session-recovered-verifier",
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": "strict_informal_verifier",
                        "target_id": action.get("target_id", "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": "recovered-verification-report",
                                "artifact_type": "verification_report",
                                "content": "Recovered strict verification pass produced a report.",
                                "metadata": {"target_id": action.get("target_id", "root"), "verdict": "gap_found"},
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": ["recovered-verification-report"],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            old = os.environ.get("ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS")
            os.environ["ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"] = "1"
            try:
                result = run_workflow(
                    store,
                    steps=2,
                    execute=True,
                    parallel_librarian_verifier=False,
                    write_on_stop=False,
                    write_console=False,
                    executor=executor,
                )
            finally:
                if old is None:
                    os.environ.pop("ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS", None)
                else:
                    os.environ["ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"] = old

            self.assertEqual(calls["count"], 2)
            self.assertTrue(result["steps"][0]["recoverable_failure"])
            self.assertEqual(result["steps"][0]["execution_phase"], "recovering_after_stale_retry")
            self.assertEqual(result["steps"][1]["execution"]["status"], "completed")
            with closing(store.connect()) as conn:
                self.assertIsNotNone(
                    conn.execute("SELECT 1 FROM artifacts WHERE artifact_id = ?", ("recovered-verification-report",)).fetchone()
                )

    def test_stop_writer_does_not_treat_blocked_route_as_verifier_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-stop-writer-blocked-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "candidate-note",
                            "artifact_type": "research_notebook",
                            "content": "A candidate route exists, but the bridge lemma is explicitly blocked.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-blocked-candidate",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use a bridge lemma that is still blocked.",
                            "evidence_artifact_ids": ["candidate-note"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-blocked-candidate",
                            "route_id": "route-blocked-candidate",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The route would prove the target if the bridge lemma were supplied.",
                            "evidence_artifact_ids": ["candidate-note"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-blocked-bridge",
                            "owner_type": "route",
                            "owner_id": "route-blocked-candidate",
                            "debt_type": "blocking_bridge_lemma",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Prove the bridge lemma before strict verification.",
                            "suggested_next_target": "root",
                            "source_artifact_ids": ["candidate-note"],
                        },
                    ],
                    "rationale": "seed blocked route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            blocker = _stop_writer_safety_blocker(store, research_mode="balanced", web_search="disabled")

        self.assertNotEqual(
            blocker.get("reason"),
            "verifier-ready route evidence exists, but no strict verifier run is recorded",
        )
        self.assertEqual(blocker.get("verifier_ready_routes", []), [])

    def test_stop_writer_ignores_blocked_route_proof_dossier_candidate_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-stop-writer-blocked-dossier-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "stale-local-route",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "blocked-route-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "Do not verify this stale route; return to the root bottleneck.",
                            "metadata": {
                                "target_id": "stale-local-route",
                                "artifact_roi": "route_blocked_or_abandoned",
                                "next_decisive_action": "Return to root.",
                            },
                        }
                    ],
                    "rationale": "seed blocked route note",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            blocker = _stop_writer_safety_blocker(store, research_mode="balanced", web_search="disabled")

        self.assertNotIn(
            "blocked-route-dossier",
            {item.get("artifact_id") for item in blocker.get("proof_candidate_artifacts", [])},
        )

    def test_additive_parallel_research_patch_rebases_after_companion_lands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            first = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "refute-note",
                            "artifact_type": "research_notebook",
                            "content": "A diagnostic counterexample search found no obstruction.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-refute-diagnostic",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "diagnostic",
                            "strategy": "stress test",
                            "evidence_artifact_ids": ["refute-note"],
                        },
                    ],
                    "rationale": "diagnostic branch landed first",
                },
            )
            self.assertTrue(first.accepted, first.errors)
            current_revision = store.get_revision()

            stale_research_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 0,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "proof-dossier",
                        "artifact_type": "proof_dossier",
                        "content": "A constructive route with local lemmas.",
                    },
                    {
                        "op": "add_claim",
                        "claim_id": "claim-local-lemma",
                        "kind": "lemma",
                        "statement": "A local lemma implies the target under a construction hypothesis.",
                        "validation_status": "plausible",
                        "parent_ids": ["root"],
                        "evidence_artifact_ids": ["proof-dossier"],
                    },
                    {
                        "op": "add_route",
                        "route_id": "route-local-lemma",
                        "conclusion_claim_id": "claim-local-lemma",
                        "relation_to_parent": "sufficient",
                        "strategy": "prove the local lemma",
                        "evidence_artifact_ids": ["proof-dossier"],
                    },
                    {
                        "op": "add_route",
                        "route_id": "route-root-constructive",
                        "conclusion_claim_id": "root",
                        "relation_to_parent": "sufficient",
                        "strategy": "assemble the construction",
                        "evidence_artifact_ids": ["proof-dossier"],
                    },
                    {
                        "op": "add_inference",
                        "inference_id": "inf-root-constructive",
                        "route_id": "route-root-constructive",
                        "conclusion_claim_id": "root",
                        "premise_claim_ids": ["claim-local-lemma"],
                        "validation_status": "plausible",
                        "explanation": "The local lemma is one ingredient in a constructive route.",
                        "evidence_artifact_ids": ["proof-dossier"],
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-construction-source",
                        "owner_type": "route",
                        "owner_id": "route-root-constructive",
                        "debt_type": "citation_or_construction_gap",
                        "severity": "blocking",
                        "status": "active",
                        "obligation": "Supply the construction theorem.",
                        "suggested_next_target": "claim-local-lemma",
                    },
                ],
                "rationale": "constructive branch produced fresh additive research state",
            }

            action = {
                "mode": "reduce",
                "target_id": "root",
                "search_intent": "parallel_independent_solve",
                "parallel_companion": True,
            }
            rebased = _rebase_parallel_patch_if_safe(stale_research_patch, current_revision, action=action)
            self.assertEqual(rebased["base_revision"], current_revision)
            accepted = apply_patch(store, rebased)
            self.assertTrue(accepted.accepted, accepted.errors)

            with closing(store.connect()) as conn:
                self.assertIsNotNone(store.get_route(conn, "route-root-constructive"))
                artifact = store.get_artifact(conn, "proof-dossier")
                self.assertIsNotNone(artifact)
                self.assertEqual(artifact["state_revision"], current_revision)

    def test_parallel_route_proof_patch_rebases_existing_selected_route_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-route-proof-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-existing",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "existing route",
                        }
                    ],
                    "rationale": "setup route",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            landed = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "parallel-obstruction",
                            "artifact_type": "route_obstruction",
                            "content": "parallel branch landed first",
                        }
                    ],
                    "rationale": "parallel companion landed first",
                },
            )
            self.assertTrue(landed.accepted, landed.errors)

            stale_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 1,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {
                        "operation": "attach_artifact",
                        "artifact": {
                            "artifact_id": "route-proof",
                            "artifact_type": "proof_dossier",
                            "content": "proof for selected route",
                        },
                    },
                    {
                        "operation": "add_inference",
                        "inference": {
                            "inference_id": "inf-route-existing",
                            "route_id": "route-existing",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "untested",
                            "explanation": "selected route inference",
                        },
                    },
                ],
                "rationale": "route proof construction",
            }

            rebased = _rebase_parallel_patch_if_safe(
                stale_patch,
                store.get_revision(),
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "route_id": "route-existing",
                    "search_intent": "route_proof_construction",
                },
                parallel_group=True,
            )
            outcome = apply_patch(store, rebased)

            self.assertTrue(outcome.accepted, outcome.errors)
            self.assertEqual(2, rebased["base_revision"])
            self.assertEqual("attach_artifact", rebased["operations"][0]["op"])
            self.assertEqual("add_inference", rebased["operations"][1]["op"])

    def test_parallel_route_conversion_patch_rebases_existing_route_without_action_route_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-route-conversion-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "claim-existing",
                            "kind": "lemma",
                            "statement": "Existing claim awaiting route conversion.",
                            "validation_status": "plausible",
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-existing-claim",
                            "conclusion_claim_id": "claim-existing",
                            "relation_to_parent": "sufficient",
                            "strategy": "existing route awaiting an inference",
                        },
                    ],
                    "rationale": "setup existing claim route",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            landed = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-synthesis",
                            "artifact_type": "advisor_report",
                            "content": "Advisor landed before route conversion.",
                        }
                    ],
                    "rationale": "advisor companion landed first",
                },
            )
            self.assertTrue(landed.accepted, landed.errors)

            stale_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 1,
                "actor_role": "researcher",
                "target_id": "claim-existing",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "route-conversion-dossier",
                        "artifact_type": "proof_dossier",
                        "content": "Proof dossier converting the existing route.",
                    },
                    {
                        "op": "add_inference",
                        "inference_id": "inf-route-existing-claim",
                        "route_id": "route-existing-claim",
                        "conclusion_claim_id": "claim-existing",
                        "premise_claim_ids": [],
                        "validation_status": "untested",
                        "explanation": "Route conversion inference for the existing claim route.",
                        "evidence_artifact_ids": ["route-conversion-dossier"],
                    },
                ],
                "rationale": "route conversion produced an inference for an existing route",
            }

            rebased = _rebase_parallel_patch_if_safe(
                stale_patch,
                store.get_revision(),
                action={
                    "mode": "prove",
                    "target_id": "claim-existing",
                    "search_intent": "proof_candidate_route_conversion",
                },
                parallel_group=True,
            )
            outcome = apply_patch(store, rebased)

            self.assertTrue(outcome.accepted, outcome.errors)
            self.assertEqual(2, rebased["base_revision"])
            with closing(store.connect()) as conn:
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM inferences WHERE inference_id = ?",
                        ("inf-route-existing-claim",),
                    ).fetchone()
                )

    def test_literature_patch_with_target_debt_rebases_after_companion_lands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-literature-debt-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            first = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "parallel-obstruction-note",
                            "artifact_type": "research_diagnostic",
                            "content": "A parallel branch found an obstruction to one route.",
                        }
                    ],
                    "rationale": "companion branch landed first",
                },
            )
            self.assertTrue(first.accepted, first.errors)
            current_revision = store.get_revision()

            stale_literature_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 0,
                "actor_role": "literature_researcher",
                "target_id": "root",
                "operations": [
                    {
                        "op": "cache_retrieval_card",
                        "card_id": "retrieval-partial-match",
                        "target_id": "root",
                        "exact_statement": "A nearby theorem proves a weaker chain-generation target.",
                        "source_identifiers": {"title": "Nearby theorem"},
                        "source_version": "source v1",
                        "source_location": "Theorem 1",
                        "applicability": {"classification": "partial_match"},
                        "missing_hypotheses": ["Bridge the weaker theorem to the target."],
                    },
                    {
                        "op": "attach_artifact",
                        "artifact_id": "retrieval-adaptation",
                        "artifact_type": "source_adaptation_notes",
                        "content": "The source is useful but leaves one target-level bridge.",
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-literature-bridge",
                        "owner_type": "claim",
                        "owner_id": "root",
                        "debt_type": "gap",
                        "severity": "high",
                        "status": "active",
                        "obligation": "Bridge the partial literature theorem to the target.",
                        "source_artifact_ids": ["retrieval-adaptation"],
                        "suggested_next_target": "root",
                    },
                ],
                "rationale": "literature branch found a partial source and a target debt",
            }

            rebased = _rebase_parallel_patch_if_safe(
                stale_literature_patch,
                current_revision,
                action={"mode": "retrieve", "target_id": "root", "search_intent": "literature_scoping"},
            )
            self.assertEqual(rebased["base_revision"], current_revision)
            accepted = apply_patch(store, rebased)
            self.assertTrue(accepted.accepted, accepted.errors)

            with closing(store.connect()) as conn:
                card = conn.execute("SELECT card_id FROM retrieval_cards WHERE card_id = 'retrieval-partial-match'").fetchone()
                debt = conn.execute("SELECT status FROM debts WHERE debt_id = 'debt-literature-bridge'").fetchone()
                artifact = store.get_artifact(conn, "retrieval-adaptation")

            self.assertIsNotNone(card)
            self.assertIsNotNone(debt)
            self.assertEqual(debt["status"], "active")
            self.assertIsNotNone(artifact)
            self.assertEqual(artifact["state_revision"], current_revision)

    def test_advisor_artifact_patch_rebases_after_primary_lands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-advisor-artifact-rebase-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            first = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "primary-proof-note",
                            "artifact_type": "proof_dossier",
                            "content": "The primary child landed first.",
                        }
                    ],
                    "rationale": "primary child landed first",
                },
            )
            self.assertTrue(first.accepted, first.errors)
            current_revision = store.get_revision()

            stale_advisor_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 0,
                "actor_role": "phd_advisor",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "advisor-proof-shape",
                        "artifact_type": "advisor_report",
                        "target_id": "root",
                        "content": "The advisor records a proof-shape triage note.",
                    },
                    {
                        "op": "attach_artifact",
                        "artifact_id": "advisor-route-triage",
                        "artifact_type": "route_triage_report",
                        "target_id": "root",
                        "content": "The advisor records route triage.",
                    },
                ],
                "rationale": "advisor companion finished after primary child",
            }

            rebased = _rebase_parallel_patch_if_safe(
                stale_advisor_patch,
                current_revision,
                action={
                    "mode": "triage_routes",
                    "target_id": "root",
                    "route_id": "route-root",
                    "search_intent": "advisor_evidence_synthesis",
                    "parallel_companion": True,
                },
                parallel_group=True,
            )
            self.assertEqual(rebased["base_revision"], current_revision)
            accepted = apply_patch(store, rebased)
            self.assertTrue(accepted.accepted, accepted.errors)

            with closing(store.connect()) as conn:
                artifact = store.get_artifact(conn, "advisor-proof-shape")
            self.assertIsNotNone(artifact)
            self.assertEqual(artifact["state_revision"], current_revision)

    def test_status_transition_parallel_research_patch_does_not_rebase(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-parallel-rebase-test",
            "base_revision": 0,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "op": "propose_status_transition",
                    "target_type": "claim",
                    "target_id": "root",
                    "status_type": "validation",
                    "new_status": "informally_verified",
                    "evidence_artifact_ids": ["proof-dossier"],
                }
            ],
        }
        rebased = _rebase_parallel_patch_if_safe(
            patch,
            3,
            action={
                "mode": "reduce",
                "target_id": "root",
                "search_intent": "parallel_independent_solve",
                "parallel_companion": True,
            },
        )
        self.assertEqual(rebased["base_revision"], 0)

    def test_additive_primary_patch_rebases_when_launched_in_parallel_group(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-parallel-primary-rebase-test",
            "base_revision": 4,
            "actor_role": "researcher",
            "target_id": "claim-target",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "target-proof-dossier",
                    "artifact_type": "proof_dossier",
                    "content": "A target-local proof repair note.",
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-target-repair",
                    "owner_type": "claim",
                    "owner_id": "claim-target",
                    "debt_type": "gap",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Repair the target-local proof.",
                    "suggested_next_target": "claim-target",
                },
            ],
            "rationale": "primary direct repair finished after a companion",
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            5,
            action={"mode": "prove", "target_id": "claim-target", "search_intent": "direct_solve_debt_repair"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            5,
            action={"mode": "prove", "target_id": "claim-target", "search_intent": "direct_solve_debt_repair"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 4)
        self.assertEqual(rebased_with_group["base_revision"], 5)

    def test_additive_local_repair_patch_rebases_with_root_handoff_debt(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-parallel-root-handoff-rebase-test",
            "base_revision": 12,
            "actor_role": "researcher",
            "target_id": "claim-stale-local-route",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "local-statement-repair-note",
                    "artifact_type": "proof_dossier",
                    "content": "Repair the local stale statement and return to the root bottleneck.",
                    "metadata": {
                        "target_id": "claim-stale-local-route",
                        "next_decisive_action": "return to root bottleneck",
                    },
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-stale-local-wording",
                    "owner_type": "claim",
                    "owner_id": "claim-stale-local-route",
                    "debt_type": "proof_obligation",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Retire the stale local wording before returning to root.",
                    "suggested_next_target": "root",
                    "evidence_artifact_ids": ["local-statement-repair-note"],
                },
            ],
            "rationale": "primary local repair finished after an advisor companion",
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            14,
            action={"mode": "prove", "target_id": "claim-stale-local-route", "search_intent": "advisor_followup_research"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            14,
            action={"mode": "prove", "target_id": "claim-stale-local-route", "search_intent": "advisor_followup_research"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 12)
        self.assertEqual(rebased_with_group["base_revision"], 14)

    def test_additive_root_patch_rebases_debt_on_existing_root_claim(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-root-existing-claim-debt-rebase-test",
            "base_revision": 22,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "root-h2-capacity-note",
                    "artifact_type": "proof_dossier",
                    "content": "A root-local H2 capacity synthesis.",
                },
                {
                    "op": "add_claim",
                    "claim_id": "claim_root_h2_capacity_test",
                    "kind": "lemma",
                    "statement": "H2 capacity criterion.",
                    "parent_ids": ["root"],
                },
                {
                    "op": "add_route",
                    "route_id": "route_root_h2_capacity_test",
                    "conclusion_claim_id": "claim_root_h2_capacity_test",
                    "strategy": "Use the H2 capacity note.",
                    "evidence_artifact_ids": ["root-h2-capacity-note"],
                },
                {
                    "op": "add_inference",
                    "inference_id": "inf_root_h2_capacity_test",
                    "route_id": "route_root_h2_capacity_test",
                    "conclusion_claim_id": "claim_root_h2_capacity_test",
                    "premise_claim_ids": [],
                    "validation_status": "plausible",
                    "explanation": "The note proves the local criterion.",
                    "evidence_artifact_ids": ["root-h2-capacity-note"],
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-root-existing-h2-claim",
                    "owner_type": "claim",
                    "owner_id": "claim_root_irreducible_h2_bridge_lift_bridge_rev115",
                    "debt_type": "sharpened_blocker",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Decide the root-local H2 capacity alternative.",
                    "suggested_next_target": "root",
                },
            ],
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            24,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            24,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 22)
        self.assertEqual(rebased_with_group["base_revision"], 24)

    def test_additive_root_patch_rebases_debt_on_existing_root_route(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-root-existing-route-debt-rebase-test",
            "base_revision": 30,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "root-central-multiplier-note",
                    "artifact_type": "proof_dossier",
                    "content": "A root-local central multiplier synthesis.",
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-root-central-multiplier",
                    "owner_type": "route",
                    "owner_id": "route_root_bridge_h2_head_capacity_criterion_rev122",
                    "debt_type": "proof_obligation",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Decide the central multiplier reservoir test.",
                    "suggested_next_target": "root",
                    "evidence_artifact_ids": ["root-central-multiplier-note"],
                },
            ],
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            32,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            32,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 30)
        self.assertEqual(rebased_with_group["base_revision"], 32)

    def test_additive_root_patch_rebases_existing_root_route_debt_without_suggested_target(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-root-existing-route-debt-no-suggested-target-rebase-test",
            "base_revision": 40,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "root-simple-multiplier-note",
                    "artifact_type": "proof_dossier",
                    "content": "A root-local simple multiplier synthesis.",
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-root-simple-multiplier",
                    "owner_id": "route_root_bridge_h2_head_capacity_criterion_rev122",
                    "debt_type": "proof_obligation",
                    "status": "active",
                    "obligation": "Decide the simple multiplier reservoir test.",
                    "evidence_artifact_ids": ["root-simple-multiplier-note"],
                },
            ],
        }

        rebased_without_group = _rebase_parallel_patch_if_safe(
            patch,
            42,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
        )
        rebased_with_group = _rebase_parallel_patch_if_safe(
            patch,
            42,
            action={"mode": "prove", "target_id": "root", "search_intent": "advisor_followup_research"},
            parallel_group=True,
        )

        self.assertEqual(rebased_without_group["base_revision"], 40)
        self.assertEqual(rebased_with_group["base_revision"], 42)

    def test_additive_parallel_route_update_rebases_for_selected_route(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-route-update-rebase-test",
            "base_revision": 7,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {"op": "attach_artifact", "artifact_id": "route-decision", "artifact_type": "proof_dossier", "content": "Route decision."},
                {
                    "op": "update_route",
                    "route_id": "route-root-selected",
                    "status": "blocked",
                    "failure_fingerprint": "selected route obstruction",
                    "evidence_artifact_ids": ["route-decision"],
                },
            ],
            "rationale": "selected route obstruction conversion",
        }

        rebased = _rebase_parallel_patch_if_safe(
            patch,
            9,
            action={"mode": "reduce", "target_id": "root", "route_id": "route-root-selected", "search_intent": "obstruction_route_conversion"},
            parallel_group=True,
        )

        self.assertEqual(rebased["base_revision"], 9)

    def test_parallel_patch_with_uncreated_inference_route_does_not_rebase(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-missing-route-no-rebase-test",
            "base_revision": 7,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {"op": "attach_artifact", "artifact_id": "route-decision", "artifact_type": "proof_dossier", "content": "Route decision."},
                {"op": "add_claim", "claim_id": "route-obstruction", "kind": "lemma", "statement": "Obstruction.", "parent_ids": ["root"], "root_impact": 0.8},
                {
                    "op": "add_inference",
                    "inference_id": "inf-route-obstruction",
                    "route_id": "route-never-created",
                    "conclusion_claim_id": "route-obstruction",
                    "premise_claim_ids": [],
                    "validation_status": "untested",
                    "explanation": "Missing route should prevent safe rebase.",
                    "evidence_artifact_ids": ["route-decision"],
                },
                {"op": "update_route", "route_id": "route-root-selected", "status": "blocked"},
            ],
            "rationale": "malformed obstruction conversion",
        }

        rebased = _rebase_parallel_patch_if_safe(
            patch,
            9,
            action={"mode": "reduce", "target_id": "root", "route_id": "route-root-selected", "search_intent": "obstruction_route_conversion"},
            parallel_group=True,
        )

        self.assertEqual(rebased["base_revision"], 7)

    def test_parallel_challenge_with_same_patch_artifact_rebases(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "workflow-parallel-challenge-rebase-test",
            "base_revision": 12,
            "actor_role": "villain",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "villain-obstruction",
                    "artifact_type": "research_diagnostic",
                    "content": "A target-local obstruction challenges the active route.",
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-villain-obstruction",
                    "owner_type": "claim",
                    "owner_id": "root",
                    "debt_type": "gap",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Resolve the obstruction.",
                    "suggested_next_target": "root",
                },
                {
                    "op": "update_claim",
                    "claim_id": "root",
                    "updates": {"validation_status": "challenged"},
                    "evidence_artifact_ids": ["villain-obstruction"],
                },
            ],
            "rationale": "parallel villain found an additive challenge",
        }

        rebased = _rebase_parallel_patch_if_safe(
            patch,
            14,
            action={
                "mode": "refute",
                "target_id": "root",
                "search_intent": "parallel_counterexample_search",
                "parallel_companion": True,
            },
        )

        self.assertEqual(rebased["base_revision"], 14)
        transition = next(op for op in rebased["operations"] if op["op"] == "propose_status_transition")
        self.assertEqual(transition["new_status"], "challenged")

    def test_primary_stale_after_parallel_sibling_applies_is_recoverable(self) -> None:
        primary = {
            "is_companion": False,
            "status": "patch_rejected",
            "patch_outcome": {
                "accepted": False,
                "errors": ["stale patch: base_revision 475 != current_revision 477"],
            },
        }
        companion = {
            "is_companion": True,
            "status": "completed",
            "patch_outcome": {"accepted": True, "errors": []},
        }

        self.assertTrue(_recoverable_parallel_stale_patch([primary, companion], primary))

    def test_lone_stale_patch_is_not_parallel_recoverable(self) -> None:
        primary = {
            "is_companion": False,
            "status": "patch_rejected",
            "patch_outcome": {
                "accepted": False,
                "errors": ["stale patch: base_revision 475 != current_revision 477"],
            },
        }

        self.assertFalse(_recoverable_parallel_stale_patch([primary], primary))

    def test_constructive_parallel_branch_merges_before_counterexample_stress(self) -> None:
        constructive = {
            "is_companion": True,
            "action": {"search_intent": "parallel_direct_solve"},
            "session_plan": {"actor_role": "researcher"},
        }
        stress = {
            "is_companion": True,
            "action": {"search_intent": "parallel_counterexample_search"},
            "session_plan": {"actor_role": "researcher"},
        }
        self.assertLess(_merge_priority(constructive), _merge_priority(stress))

    def test_live_apply_barrier_waits_for_pending_primary_or_verifier(self) -> None:
        literature = {
            "is_companion": True,
            "action": {"search_intent": "literature_scoping"},
            "session_plan": {"actor_role": "literature_researcher"},
        }
        pending_verifier = {
            "is_companion": False,
            "action": {"search_intent": ""},
            "session_plan": {"actor_role": "strict_informal_verifier"},
        }
        pending_researcher = {
            "is_companion": False,
            "action": {"search_intent": "direct_solve"},
            "session_plan": {"actor_role": "researcher"},
        }

        self.assertTrue(_blocked_by_pending_priority_barrier(literature, [pending_verifier]))
        self.assertTrue(_blocked_by_pending_priority_barrier(literature, [pending_researcher]))

    def test_live_apply_barrier_allows_safe_advisor_before_pending_researcher(self) -> None:
        advisor = {
            "is_companion": True,
            "action": {"mode": "triage_routes", "target_id": "root", "search_intent": "advisor_evidence_synthesis"},
            "session_plan": {"actor_role": "phd_advisor"},
            "execution": {
                "patch": {
                    "actor_role": "phd_advisor",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-next-step",
                            "artifact_type": "advisor_report",
                            "content": "Verify the bridge next.",
                        }
                    ],
                }
            },
        }
        pending_researcher = {
            "is_companion": False,
            "action": {"search_intent": "direct_solve"},
            "session_plan": {"actor_role": "researcher"},
        }
        pending_verifier = {
            "is_companion": False,
            "action": {"search_intent": "verify_ready_route"},
            "session_plan": {"actor_role": "strict_informal_verifier"},
        }

        self.assertFalse(_blocked_by_pending_priority_barrier(advisor, [pending_researcher]))
        self.assertTrue(_blocked_by_pending_priority_barrier(advisor, [pending_verifier]))

    def test_parallel_signals_written_to_exchange_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-signal-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            _record_parallel_signals(
                store,
                {
                    "actor_role": "researcher",
                    "target_id": "root",
                    "parallel_signals": [
                        {
                            "run_id": "unknown",
                            "signal_type": "useful_lemma",
                            "relation": "supports",
                            "summary": "Lemma A may close the construction branch.",
                            "evidence": "artifact:proof-dossier",
                            "confidence": "high",
                        }
                    ],
                },
                action={"mode": "prove", "target_id": "root"},
                execution={"run_id": "run-signal", "actor_role": "researcher"},
            )
            path = store.state_dir / "parallel_exchange.jsonl"
            payload = json.loads(path.read_text(encoding="utf-8").strip())

        self.assertEqual(payload["run_id"], "run-signal")
        self.assertEqual(payload["signal_type"], "useful_lemma")
        self.assertEqual(payload["relation"], "supports")
        self.assertEqual(payload["target_id"], "root")

    def test_parallel_signal_problem_id_run_id_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-problem-id-signal-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            _record_parallel_signals(
                store,
                {
                    "problem_id": store.problem_id,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "parallel_signals": [
                        {
                            "run_id": store.problem_id,
                            "signal_type": "source_found",
                            "summary": "A source may help.",
                        }
                    ],
                },
                action={"mode": "retrieve", "target_id": "root"},
                execution={"run_id": "run-retrieve-root", "actor_role": "literature_researcher"},
            )
            path = store.state_dir / "parallel_exchange.jsonl"
            payload = json.loads(path.read_text(encoding="utf-8").strip())

        self.assertEqual(payload["run_id"], "run-retrieve-root")
        self.assertEqual(payload["signal_type"], "source_found")

    def test_parallel_signals_are_deduplicated_by_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("workflow-parallel-signal-dedupe-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            patch = {
                "actor_role": "researcher",
                "target_id": "root",
                "parallel_signals": [
                    {
                        "signal_type": "useful_lemma",
                        "relation": "supports",
                        "summary": "Lemma A may close the construction branch.",
                        "evidence": "artifact:proof-dossier",
                        "confidence": "high",
                    }
                ],
            }
            action = {"mode": "prove", "target_id": "root"}
            execution = {"run_id": "run-signal", "actor_role": "researcher"}
            _record_parallel_signals(store, patch, action=action, execution=execution)
            _record_parallel_signals(store, patch, action=action, execution=execution)
            path = store.state_dir / "parallel_exchange.jsonl"
            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)

    def test_zero_wall_limit_stops_immediately(self) -> None:
        self.assertEqual(_remaining_wall_seconds(0.0, 0), 0.0)
        self.assertIsNone(_remaining_wall_seconds(0.0, None))


if __name__ == "__main__":
    unittest.main()
