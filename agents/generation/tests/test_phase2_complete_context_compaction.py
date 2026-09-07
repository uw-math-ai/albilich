from __future__ import annotations

import copy
import json
import unittest

from agents.generation.phase2.context_builder import (
    ContextTooLargeError,
    _fit_manifest,
    render_manifest,
)


class CompleteContextCompactionTests(unittest.TestCase):
    def manifest(self, role="integration_verifier"):
        return {
            "proof_context_complete": True,
            "target_id": "lemma",
            "root_statement": "The unrestricted root theorem.",
            "role_context_policy": {"context_role": role},
            "claims": [{"claim_id": "lemma", "statement": "Exact local theorem."}],
            "routes": [{"route_id": "route", "conclusion_claim_id": "lemma"}],
            "inferences": [{"inference_id": "step", "explanation": "Exact argument."}],
            "debts": [{"debt_id": "gap", "obligation": "An unresolved root gap."}],
            "artifacts": [{"artifact_id": "proof", "content": "Proof detail. " * 2000}],
            "local_search_policy": {"allowed_local_evidence_paths": ["/capsule/proof.md"]},
            "patch_contract": {"required": "strict report metadata"},
            "workflow_action": {
                "mode": "integrate",
                "target_id": "lemma",
                "route_id": "route",
                "proof_interface_contract": {"required_checks": ["exact hypotheses"]},
                "theorem_preflight_contract": {"required_checks": ["endpoint cases"]},
                "verifier_evidence_artifact_ids": ["proof"],
                "assurance_review_required": True,
                "observed_reviewer_independence_classes": ["prior-family"],
                "root_alignment_audit": True,
                "unknown_future_requirement": "Preserve fields not explicitly advisory.",
                **{key: {"advisory_summary": "Global planning summary. " * 600}
                   for key in (
                       "minimal_active_debt_frontier", "proof_program_view",
                       "priority_assessment", "case_coverage_map", "root_cut_progress_gate",
                   )},
            },
        }

    def test_complete_verifier_packets_drop_planning_not_proof_inputs(self):
        for role in ("integration_verifier", "strict_informal_verifier", "formal_backend"):
            with self.subTest(role=role):
                source = self.manifest(role)
                original = copy.deepcopy(source)
                fitted = _fit_manifest(source, max_chars=60_000)
                self.assertLessEqual(len(render_manifest(fitted)), 60_000)
                self.assertTrue(fitted["proof_context_complete"])
                for key in (
                    "root_statement", "claims", "routes", "inferences", "debts",
                    "artifacts", "local_search_policy", "patch_contract",
                ):
                    self.assertEqual(original[key], fitted[key], key)
                for key in (
                    "mode", "target_id", "route_id", "proof_interface_contract",
                    "theorem_preflight_contract", "verifier_evidence_artifact_ids",
                    "assurance_review_required", "observed_reviewer_independence_classes",
                    "root_alignment_audit", "unknown_future_requirement",
                ):
                    self.assertEqual(original["workflow_action"][key], fitted["workflow_action"][key], key)
                # Compaction must not mutate the admitted dispatch action or its caller's copy.
                self.assertEqual(original, source)

    def test_genuinely_oversized_proof_still_fails_closed(self):
        source = self.manifest()
        source["artifacts"][0]["content"] = "Required proof detail. " * 4000
        original = copy.deepcopy(source)
        with self.assertRaises(ContextTooLargeError):
            _fit_manifest(source, max_chars=60_000)
        self.assertEqual(original, source)

    def test_fitting_packet_keeps_advisory_context(self):
        source = self.manifest()
        fitted = _fit_manifest(source, max_chars=200_000)
        self.assertEqual(source["workflow_action"], fitted["workflow_action"])

    def test_lossless_serialization_is_tried_before_removing_context(self):
        source = self.manifest()
        original = copy.deepcopy(source)
        compact_size = len(json.dumps(source, ensure_ascii=False, separators=(",", ":")))
        fitted = _fit_manifest(source, max_chars=compact_size + 300)
        self.assertEqual("compact_json", fitted.get("context_serialization"))
        self.assertLessEqual(len(render_manifest(fitted)), compact_size + 300)
        self.assertEqual(fitted, json.loads(render_manifest(fitted)))
        for key in original:
            self.assertEqual(original[key], fitted[key], key)
        self.assertEqual(original, source)

    def test_optional_root_reconciliation_does_not_crowd_out_local_proof(self):
        source = self.manifest()
        source["workflow_action"] = {"mode": "integrate", "target_id": "lemma"}
        required = {"debt_id": "local", "owner_id": "lemma", "obligation": "Exact blocker. " * 300}
        optional = {
            "debt_id": "root-candidate", "owner_id": "root",
            "obligation": "Optional root reconciliation. " * 2000,
            "integration_resolution_candidate": True,
            "candidate_is_not_route_blocker": True,
            "candidate_for_claim_id": "lemma",
        }
        source["debts"] = [required, optional]
        source["context_coverage"] = {
            "complete_for_assigned_proof_check": True,
            "population_counts": {"proof_obligations": 2},
        }
        original = copy.deepcopy(source)
        fitted = _fit_manifest(source, max_chars=50_000)
        self.assertLessEqual(len(render_manifest(fitted)), 50_000)
        self.assertEqual([required], fitted["debts"])
        self.assertEqual(original["artifacts"], fitted["artifacts"])
        self.assertEqual(original["inferences"], fitted["inferences"])
        coverage = fitted["context_coverage"]
        self.assertEqual(1, coverage["omitted_counts"]["proof_obligations"])
        self.assertEqual(1, coverage["omitted_optional_reconciliation_candidates"])
        self.assertTrue(coverage["complete_for_assigned_proof_check"])
        self.assertEqual(original, source)

    def test_candidate_flags_cannot_remove_a_route_local_blocker(self):
        for owner in ("lemma", "premise", "route", "step"):
            with self.subTest(owner=owner):
                source = self.manifest()
                source["claims"].append({"claim_id": "premise", "statement": "A required premise."})
                source["debts"] = [{
                    "debt_id": "required", "owner_id": owner,
                    "obligation": "Required local blocker. " * 4000,
                    "integration_resolution_candidate": True,
                    "candidate_is_not_route_blocker": True,
                    "candidate_for_claim_id": "lemma",
                }]
                with self.assertRaises(ContextTooLargeError):
                    _fit_manifest(source, max_chars=60_000)

    def test_reconciliation_trimming_is_only_for_nonroot_integration(self):
        for role, target in (("strict_informal_verifier", "lemma"), ("formal_backend", "lemma"), ("integration_verifier", "root")):
            with self.subTest(role=role, target=target):
                source = self.manifest(role)
                source["target_id"] = target
                source["debts"] = [{
                    "debt_id": "root-candidate", "owner_id": "root",
                    "obligation": "Required in this proof scope. " * 4000,
                    "integration_resolution_candidate": True,
                    "candidate_is_not_route_blocker": True,
                    "candidate_for_claim_id": target,
                }]
                with self.assertRaises(ContextTooLargeError):
                    _fit_manifest(source, max_chars=60_000)


if __name__ == "__main__":
    unittest.main()
