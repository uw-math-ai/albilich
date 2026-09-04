from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.generation.phase2.cli import DEFAULT_ATTEMPT_STEPS, DEFAULT_ATTEMPT_WALL_SECONDS
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_operator_patch as apply_patch
from agents.generation.phase2.reference_solution import ingest_reference_solution
from agents.generation.phase2.research_strategy import (
    advisor_synthesis_trigger,
    long_session_workspace,
    minimal_active_debt_frontier,
    proof_program_view,
    reference_solution_state,
    root_leverage_metrics,
    threat_propagation_view,
)
from agents.generation.phase2.scheduler import next_action
from agents.generation.phase2.store import ProofStateStore


def _base_state() -> dict:
    return {
        "problem_state": {
            "problem_id": "research-programs",
            "root_statement": "For every admissible X, P(X) holds.",
            "current_revision": 20,
            "remaining_token_budget": 1_000_000,
            "reserved_verification_budget": 100_000,
        },
        "claims": [
            {
                "claim_id": "root",
                "statement": "For every admissible X, P(X) holds.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 1.0,
            },
            {
                "claim_id": "claim-a",
                "statement": "The structural reduction holds.",
                "validation_status": "informally_verified",
                "lifecycle_status": "integrated",
                "root_impact": 0.9,
            },
        ],
        "routes": [
            {
                "route_id": "route-a",
                "conclusion_claim_id": "claim-a",
                "label": "structural route",
                "strategy": "minimal counterexample and degeneration",
                "status": "integrated",
                "relation_to_parent": "sufficient",
                "evidence_artifact_ids_json": "[]",
            },
            {
                "route_id": "route-root",
                "conclusion_claim_id": "root",
                "label": "root assembly",
                "strategy": "assemble the structural reduction",
                "status": "active",
                "relation_to_parent": "sufficient",
                "evidence_artifact_ids_json": "[]",
            },
        ],
        "inferences": [
            {
                "inference_id": "infer-root",
                "route_id": "route-root",
                "conclusion_claim_id": "root",
                "premise_claim_ids_json": '["claim-a"]',
                "condition_claim_ids_json": "[]",
                "validation_status": "untested",
                "evidence_artifact_ids_json": "[]",
            }
        ],
        "debts": [],
        "research_artifacts": [],
        "recent_runs": [],
    }


class Phase2ResearchProgramTest(unittest.TestCase):
    def test_attempt_defaults_have_no_step_or_wall_clock_expiration(self) -> None:
        self.assertEqual(DEFAULT_ATTEMPT_STEPS, 0)
        self.assertIsNone(DEFAULT_ATTEMPT_WALL_SECONDS)

    def test_proof_program_records_case_coverage_and_long_session_persistence(self) -> None:
        state = _base_state()
        state["research_artifacts"] = [
            {
                "artifact_id": "dossier-root",
                "artifact_type": "proof_dossier",
                "state_revision": 19,
                "metadata_json": {
                    "route_id": "route-root",
                    "target_id": "root",
                    "proof_program_id": "program-degeneration",
                    "proof_philosophy": "degeneration plus induction",
                    "root_implication": "the two named cases exhaust the root",
                    "decisive_obligation": "prove specialization preserves P",
                    "covered_cases": ["smooth boundary", "singular boundary"],
                    "open_cases": [],
                    "cases_exhaustive": True,
                    "validation_criteria": ["check specialization and induction interfaces"],
                    "abandonment_criteria": ["counterexample to specialization"],
                },
            }
        ]
        programs = proof_program_view(state)
        root_program = next(row for row in programs["programs"] if row["route_id"] == "route-root")
        self.assertEqual(root_program["program_id"], "program-degeneration")
        self.assertEqual(root_program["case_coverage_status"], "exhaustive")
        self.assertTrue(programs["no_wall_clock_abandonment"])
        workspace = long_session_workspace(state, {"target_id": "root", "route_id": "route-root"})
        self.assertEqual(workspace["canonical_artifact_id"], "dossier-root")
        self.assertTrue(workspace["continue_in_place"])
        self.assertIsNone(workspace["wall_clock_expiration"])

    def test_semantic_debt_aliases_collapse_to_one_work_item_without_false_resolution(self) -> None:
        state = _base_state()
        state["debts"] = [
            {
                "debt_id": "debt-one",
                "owner_type": "route",
                "owner_id": "route-root",
                "suggested_next_target": "root",
                "debt_type": "blocking_bridge",
                "severity": "blocking",
                "status": "active",
                "obligation": "Prove the local compatibility bridge for the global construction.",
                "repeated_count": 4,
            },
            {
                "debt_id": "debt-two",
                "owner_type": "inference",
                "owner_id": "infer-root",
                "suggested_next_target": "root",
                "debt_type": "proof_obligation",
                "severity": "blocking",
                "status": "active",
                "obligation": "Show that local compatibility gives the global bridge construction.",
                "repeated_count": 2,
            },
        ]
        frontier = minimal_active_debt_frontier(state)
        self.assertEqual(frontier["active_blocking_debt_count"], 2)
        self.assertEqual(frontier["minimal_frontier_count"], 1)
        self.assertEqual(len(frontier["alias_to_primary"]), 1)
        self.assertTrue(frontier["alias_database_status_unchanged"])
        self.assertTrue(all(row["status"] == "active" for row in state["debts"]))

    def test_counterevidence_propagates_to_downstream_certification_for_revalidation(self) -> None:
        state = _base_state()
        state["research_artifacts"] = [
            {
                "artifact_id": "obstruction-a",
                "artifact_type": "route_obstruction",
                "state_revision": 20,
                "metadata_json": {"target_id": "claim-a", "status": "candidate"},
            }
        ]
        threat = threat_propagation_view(state)
        self.assertIn("claim-a", threat["direct_threatened_claim_ids"])
        self.assertIn("root", threat["threatened_claim_ids"])
        self.assertIn("claim-a", threat["threatened_verified_claim_ids"])
        self.assertEqual(threat["pending_revalidation_routes"][0]["route_id"], "route-a")
        self.assertTrue(threat["certification_unchanged_pending_verifier"])
        leverage = root_leverage_metrics(state)
        self.assertEqual(leverage["pending_threat_revalidation_count"], 1)
        self.assertTrue(leverage["artifact_count_is_not_root_progress"])

    def test_advisor_checkpoint_is_evidence_based_and_never_elapsed_time_based(self) -> None:
        state = _base_state()
        state["recent_runs"] = [
            {
                "run_id": f"run-{index}",
                "actor_role": "researcher",
                "mode": "reduce",
                "target_id": "root",
                "state_revision": 17 + index,
                "status": "completed",
                "search_intent": f"program-pass-{index}",
                "output_artifact_ids_json": "[]",
            }
            for index in range(3)
        ]
        state["routes"].append(
            {
                "route_id": "route-root-alt",
                "conclusion_claim_id": "root",
                "label": "analytic route",
                "strategy": "direct analytic inequality",
                "status": "active",
                "relation_to_parent": "sufficient",
                "evidence_artifact_ids_json": "[]",
            }
        )
        trigger = advisor_synthesis_trigger(state)
        self.assertTrue(trigger["due"])
        self.assertIn("multiple_root_proof_philosophies_need_comparison", trigger["reasons"])
        self.assertTrue(trigger["evidence_based_only"])
        self.assertFalse(trigger["wall_clock_trigger_used"])
        self.assertTrue(trigger["long_proofs_may_continue"])

    def test_reference_solution_ingestion_forces_reconstruction_not_certification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("reference-reconstruction", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            reference_path = Path(tmpdir) / "solution.md"
            reference_path.write_text("# Solution\n\nFirst reduce to Lemma A, then handle both cases.", encoding="utf-8")
            ingested = ingest_reference_solution(
                store,
                reference_path,
                title="Reference proof",
                source_statement="Target theorem.",
            )
            self.assertTrue(ingested["created"])
            self.assertFalse(ingested["verification_authority"])
            state = store.get_scheduler_state()
            reference = reference_solution_state(state)
            self.assertTrue(reference["pending_reconstruction"])
            action = next_action(store, web_search="disabled")
            self.assertEqual(action["search_intent"], "reference_solution_reconstruction")
            self.assertTrue(action["reference_solution_reconstruction_required"])
            manifest = build_context_manifest(store, action=action, max_chars=40_000)
            contract = manifest["reference_solution_reconstruction_contract"]
            self.assertTrue(contract["reference_is_not_verification_authority"])
            self.assertEqual(contract["source"]["artifact_id"], ingested["artifact_id"])
            self.assertTrue(
                any("Reconstruct the human-supplied reference solution now" in line for line in manifest["instructions"])
            )

    def test_proof_candidate_evidence_gets_automatic_strict_verifier_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("automatic-proof-handoff", generation_root=Path(tmpdir) / "generation")
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
                            "artifact_id": "root-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete proof of the target through one terminal implication.",
                            "metadata": {
                                "target_id": "root",
                                "route_id": "route-root",
                                "proof_candidate": True,
                                "ready_for_verifier": True,
                                "cases_exhaustive": True,
                            },
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "label": "complete route",
                            "strategy": "direct terminal implication",
                            "relation_to_parent": "sufficient",
                            "evidence_artifact_ids": ["root-proof-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "infer-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "explanation": "The dossier proves the root directly.",
                            "validation_status": "plausible",
                            "evidence_artifact_ids": ["root-proof-dossier"],
                        },
                    ],
                    "rationale": "submit a complete proof route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            action = next_action(store, web_search="disabled")
            self.assertTrue(action["automatic_researcher_verifier_handoff"])
            self.assertEqual(action["route_id"], "route-root")
            self.assertEqual(action["strict_verifier_scope"], "fresh_route_evidence_revalidation")
            self.assertIn("root-proof-dossier", action["verifier_evidence_artifact_ids"])


if __name__ == "__main__":
    unittest.main()
