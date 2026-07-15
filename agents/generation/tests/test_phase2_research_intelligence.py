from __future__ import annotations

import unittest

from agents.generation.phase2.research_intelligence import (
    action_patch_contract_errors,
    decisive_obligation_frontier,
    deep_session_roi,
    proof_interface_contract,
    representation_switch_contract,
    theorem_adaptation_contract,
    validate_deep_session_roi_metadata,
    validate_proof_interface_metadata,
    verifier_filtered_outcome_learning,
)
from agents.generation.phase2.research_strategy import enrich_action, retrieve_method_cards


def _state() -> dict:
    return {
        "problem_state": {
            "root_statement": "Every finite group has the required permutation action.",
            "current_revision": 12,
        },
        "claims": [
            {
                "claim_id": "root",
                "statement": "Every finite group has the required permutation action.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 1.0,
            },
            {
                "claim_id": "lemma-a",
                "statement": "The chief factor action has a fixed point.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 0.9,
                "parent_ids_json": '["root"]',
            },
            {
                "claim_id": "lemma-b",
                "statement": "The alternative action has two compatible fixed points.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 0.7,
                "parent_ids_json": '["root"]',
            },
        ],
        "routes": [
            {
                "route_id": "route-short",
                "conclusion_claim_id": "root",
                "status": "active",
                "relation_to_parent": "sufficient",
                "evidence_artifact_ids_json": "[]",
            },
            {
                "route_id": "route-long",
                "conclusion_claim_id": "root",
                "status": "active",
                "relation_to_parent": "sufficient",
                "evidence_artifact_ids_json": "[]",
            },
        ],
        "inferences": [
            {
                "inference_id": "inf-short",
                "route_id": "route-short",
                "conclusion_claim_id": "root",
                "premise_claim_ids": ["lemma-a"],
                "validation_status": "plausible",
                "explanation": "Lemma A implies the root.",
                "evidence_artifact_ids_json": "[]",
            },
            {
                "inference_id": "inf-long",
                "route_id": "route-long",
                "conclusion_claim_id": "root",
                "premise_claim_ids": ["lemma-a", "lemma-b"],
                "validation_status": "plausible",
                "explanation": "Both lemmas imply the root.",
                "evidence_artifact_ids_json": "[]",
            },
        ],
        "debts": [],
        "research_artifacts": [],
        "audit_artifacts": [],
        "confirmed_counterexamples": [],
        "recent_runs": [],
    }


class ResearchIntelligenceTests(unittest.TestCase):
    def test_graph_frontier_selects_smallest_sufficient_route_cut(self) -> None:
        frontier = decisive_obligation_frontier(_state())
        self.assertTrue(frontier["graph_derived"])
        self.assertEqual(frontier["selected_route_id"], "route-short")
        self.assertEqual(frontier["decisive_obligation"]["route_id"], "route-short")
        self.assertIn(frontier["decisive_obligation"]["obligation_id"], {"inf-short", "lemma-a"})

    def test_verifier_ready_route_does_not_inherit_unrelated_debt(self) -> None:
        state = _state()
        state["claims"][1]["validation_status"] = "informally_verified"
        state["inferences"][0]["validation_status"] = "informally_verified"
        state["routes"] = [state["routes"][0]]
        state["inferences"] = [state["inferences"][0]]
        state["debts"] = [
            {
                "debt_id": "unrelated",
                "owner_id": "lemma-b",
                "suggested_next_target": "lemma-b",
                "status": "active",
                "severity": "blocking",
                "obligation": "Prove the unused alternative lemma.",
            }
        ]
        frontier = decisive_obligation_frontier(state)
        self.assertTrue(frontier["selected_route_ready_for_verification"])
        self.assertEqual(frontier["minimal_cut_obligations"], [])

    def test_frontier_ignores_root_debt_matched_to_integrated_claim_id(self) -> None:
        state = _state()
        state["routes"] = []
        state["inferences"] = []
        state["claims"].append(
            {
                "claim_id": "claim_psl_outer_bridge",
                "statement": "The PSL outer bridge holds.",
                "validation_status": "informally_verified",
                "lifecycle_status": "integrated",
                "root_impact": 0.8,
                "parent_ids_json": '["root"]',
            }
        )
        state["debts"] = [
            {
                "debt_id": "debt_psl_outer_bridge",
                "owner_id": "root",
                "suggested_next_target": "root",
                "status": "active",
                "severity": "blocking",
                "obligation": "Prove the already integrated PSL outer bridge.",
            },
            {
                "debt_id": "debt_unitary_outer_bridge",
                "owner_id": "root",
                "suggested_next_target": "root",
                "status": "active",
                "severity": "blocking",
                "obligation": "Prove the new unitary outer bridge.",
            },
        ]

        frontier = decisive_obligation_frontier(state)

        self.assertEqual(frontier["decisive_obligation"]["obligation_id"], "debt_unitary_outer_bridge")
        self.assertFalse(
            any(
                row["obligation_id"] == "debt_psl_outer_bridge"
                for row in frontier["minimal_cut_obligations"]
            )
        )

    def test_frontier_skips_active_route_concluding_integrated_claim(self) -> None:
        state = _state()
        state["claims"].append(
            {
                "claim_id": "claim_unitary_outer_bridge",
                "statement": "The unitary outer bridge holds.",
                "validation_status": "informally_verified",
                "lifecycle_status": "integrated",
                "root_impact": 0.8,
                "parent_ids_json": '["root"]',
            }
        )
        state["routes"] = [
            {
                "route_id": "route_unitary_old",
                "conclusion_claim_id": "claim_unitary_outer_bridge",
                "status": "active",
                "relation_to_parent": "sufficient",
                "evidence_artifact_ids_json": "[]",
            }
        ]
        state["inferences"] = [
            {
                "inference_id": "inf_unitary_old",
                "route_id": "route_unitary_old",
                "conclusion_claim_id": "claim_unitary_outer_bridge",
                "premise_claim_ids": [],
                "validation_status": "untested",
                "explanation": "Repair the older unitary route.",
                "evidence_artifact_ids_json": "[]",
            }
        ]
        state["debts"] = [
            {
                "debt_id": "debt_orthogonal_outer_bridge",
                "owner_id": "root",
                "suggested_next_target": "root",
                "status": "active",
                "severity": "blocking",
                "obligation": "Prove the next orthogonal outer bridge.",
            }
        ]

        frontier = decisive_obligation_frontier(state)

        self.assertEqual(frontier["selected_route_id"], "")
        self.assertEqual(
            frontier["decisive_obligation"]["obligation_id"],
            "debt_orthogonal_outer_bridge",
        )
        self.assertFalse(
            any(
                row["obligation_id"] == "inf_unitary_old"
                for row in frontier["minimal_cut_obligations"]
            )
        )

    def test_outcome_learning_uses_only_verified_local_evidence(self) -> None:
        state = _state()
        state["claims"][1]["validation_status"] = "informally_verified"
        state["claims"][1]["evidence_artifact_ids_json"] = '["proof-a"]'
        state["recent_runs"] = [
            {
                "actor_role": "researcher",
                "mode": "prove",
                "target_id": "lemma-a",
                "route_id": "",
                "search_intent": "direct_solve",
                "status": "completed",
                "output_artifact_ids_json": '["proof-a"]',
                "total_tokens": 1000,
            },
            {
                "actor_role": "researcher",
                "mode": "prove",
                "target_id": "lemma-b",
                "route_id": "",
                "search_intent": "direct_solve",
                "status": "patch_rejected",
                "output_artifact_ids_json": "[]",
                "total_tokens": 1000,
            },
        ]
        learned = verifier_filtered_outcome_learning(
            state, {"mode": "prove", "target_id": "lemma-a", "search_intent": "direct_solve"}
        )
        self.assertFalse(learned["reference_solution_used"])
        self.assertFalse(learned["private_cross_problem_cache_used"])
        self.assertEqual(learned["current_family"]["verified_successes"], 1)
        self.assertEqual(learned["current_family"]["execution_failures"], 1)

    def test_two_no_delta_sessions_force_philosophy_change(self) -> None:
        state = _state()
        state["research_artifacts"] = [
            {
                "artifact_id": "deep-1",
                "artifact_type": "deep_session_report",
                "state_revision": 11,
                "metadata_json": '{"target_id":"root","mathematical_delta_kind":"none","changed_proof_state":false}',
            },
            {
                "artifact_id": "deep-2",
                "artifact_type": "deep_session_report",
                "state_revision": 10,
                "metadata_json": '{"target_id":"root","mathematical_delta_kind":"none","changed_proof_state":false}',
            },
        ]
        roi = deep_session_roi(state, {"mode": "reduce", "target_id": "root", "research_philosophy": "direct_proof"})
        self.assertFalse(roi["allowed"])
        action = enrich_action(
            state,
            {
                "mode": "reduce",
                "target_id": "root",
                "canonical_full_proof_reconstruction_required": True,
            },
        )
        self.assertTrue(action["deep_session_suppressed"])
        self.assertEqual(action["research_philosophy"], action["forced_research_philosophy"])
        self.assertNotIn("deep_session_required", action)

    def test_productive_deep_session_metadata_is_delta_only(self) -> None:
        valid = {
            "deep_session_roi_version": 1,
            "mathematical_delta_kind": "proved_lemma",
            "mathematical_delta_summary": "Proved the exact fixed-point lemma.",
            "changed_proof_state": True,
            "next_philosophy_if_stalled": "adversarial_probe",
        }
        self.assertEqual(validate_deep_session_roi_metadata(valid), [])
        invalid = {**valid, "mathematical_delta_kind": "none", "changed_proof_state": False}
        self.assertTrue(validate_deep_session_roi_metadata(invalid))

    def test_representation_switch_is_required_after_repeated_attack(self) -> None:
        state = _state()
        state["recent_runs"] = [
            {"actor_role": "researcher", "target_id": "root"},
            {"actor_role": "researcher", "target_id": "root"},
        ]
        contract = representation_switch_contract(state, {"mode": "reduce", "target_id": "root"})
        self.assertEqual(contract["representation_switch_version"], 1)
        self.assertGreaterEqual(len(contract["suggested_representations"]), 2)
        self.assertIn("group_theory", contract["domain_tags"])

    def test_literature_action_gets_exact_adaptation_contract(self) -> None:
        contract = theorem_adaptation_contract(
            {"mode": "retrieve", "search_intent": "exact_theorem_search", "target_id": "root"}
        )
        self.assertEqual(contract["theorem_adaptation_version"], 1)
        self.assertTrue(contract["proof_technique_extraction_required"])
        self.assertIn("hypothesis_dictionary", contract["required_fields"])
        verifier = theorem_adaptation_contract(
            {"mode": "prove", "route_id": "route-short", "search_intent": "citation_certification"}
        )
        self.assertEqual(verifier, {})

    def test_zero_gap_verdict_requires_all_interface_checks(self) -> None:
        contract = proof_interface_contract({"mode": "prove", "route_id": "route-short"})
        self.assertFalse(contract["lean4_required"])
        metadata = {
            "proof_interface_check_version": 1,
            "verdict": "verified",
            "quantifiers_preserved": True,
            "hypotheses_matched": True,
            "cases_exhaustive": True,
            "reduction_direction_valid": True,
            "finite_scope_not_overclaimed": True,
            "dependencies_assemble": False,
        }
        self.assertTrue(validate_proof_interface_metadata(metadata))
        metadata["dependencies_assemble"] = True
        self.assertEqual(validate_proof_interface_metadata(metadata), [])

    def test_scheduled_verifier_patch_must_include_interface_version(self) -> None:
        action = {"mode": "prove", "route_id": "route-short", "proof_interface_check_required": True}
        missing = {
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_type": "verification_report",
                    "artifact_id": "report",
                    "metadata": {"verdict": "major_gaps"},
                }
            ]
        }
        self.assertTrue(action_patch_contract_errors(action, missing))
        missing["operations"][0]["metadata"]["proof_interface_check_version"] = 1
        self.assertEqual(action_patch_contract_errors(action, missing), [])

    def test_method_library_has_domain_specific_transfer_cards(self) -> None:
        cards = retrieve_method_cards(
            "For this finite group use a minimal normal subgroup and its chief factor action, then analyze conjugacy."
        )
        ids = {card["method_id"] for card in cards}
        self.assertIn("chief_factor_induction", ids)
        chief = next(card for card in cards if card["method_id"] == "chief_factor_induction")
        self.assertIn("group_theory", chief["matched_domain_tags"])
        self.assertTrue(chief["method_transfer_packet_required"])


if __name__ == "__main__":
    unittest.main()
