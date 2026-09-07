from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.generation.phase2.codex_runner import build_session_prompt
from agents.generation.phase2.context_builder import _patch_contract, _role_context_policy
from agents.generation.phase2.integration import integration_patch
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_operator_patch
from agents.generation.phase2.scheduler import _integration_candidates
from agents.generation.phase2.store import ProofStateStore
from agents.generation.tests._phase2_test_support import strictly_verify_entities


class LocalIntegrationContractTests(unittest.TestCase):
    def packet(self, target_id: str, **extra):
        action = {"mode": "integrate", "target_id": target_id, "route_id": "route", **extra}
        policy = _role_context_policy(action)
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action=action,
            actor_role="integration_verifier",
        )
        return prompt, policy, _patch_contract(action, policy)

    def test_local_integration_does_not_require_solving_root(self) -> None:
        prompt, policy, contract = self.packet("lemma")
        self.assertIn("LOCAL INTEGRATION", prompt)
        self.assertIn("does not require a proof of the root", prompt)
        self.assertIn("Do not repeat a root-alignment-only audit", prompt)
        self.assertNotIn("and root_alignment={", prompt)
        self.assertIn("local claim", policy["summary"])
        fields = contract["operation_templates"][0]["fields"]
        self.assertNotIn("metadata.root_alignment", fields)
        self.assertIn("metadata.claim_id", fields)
        self.assertIn("metadata.route_id", fields)

    def test_root_integration_retains_strict_alignment(self) -> None:
        prompt, _, contract = self.packet("root")
        self.assertIn("WEAKER-STATEMENT DISCIPLINE", prompt)
        self.assertIn("implication_verified: true", prompt)
        self.assertIn("COPY it verbatim", prompt)
        self.assertIn("metadata.root_alignment", contract["operation_templates"][0]["fields"])
        self.assertNotIn("LOCAL INTEGRATION", prompt)

    def test_explicit_alignment_audit_remains_an_audit(self) -> None:
        prompt, policy, contract = self.packet("lemma", root_alignment_audit=True)
        self.assertIn("perform an audit only", prompt)
        self.assertIn("root alignment", policy["summary"])
        self.assertNotIn("LOCAL INTEGRATION", prompt)
        templates = contract["operation_templates"]
        self.assertIn("artifact_type=root_alignment_audit", templates[0]["fields"])
        self.assertFalse(any(row["op"] == "propose_status_transition" for row in templates))

    def test_local_integration_preserves_root_debt_and_leaves_scheduler_frontier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofStateStore("local-integration", generation_root=Path(tmp) / "generation")
            store.init_problem("The unrestricted root theorem.")
            outcome = apply_operator_patch(store, {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": store.get_revision(),
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {"op": "add_claim", "claim_id": "lemma", "kind": "lemma",
                     "statement": "A strictly narrower local lemma.", "parent_ids": ["root"]},
                    {"op": "add_route", "route_id": "route", "conclusion_claim_id": "lemma",
                     "relation_to_parent": "sufficient", "strategy": "Prove the local lemma only."},
                    {"op": "add_inference", "inference_id": "terminal", "route_id": "route",
                     "conclusion_claim_id": "lemma", "premise_claim_ids": [],
                     "validation_status": "untested", "explanation": "Local argument."},
                    {"op": "add_debt", "debt_id": "root-gap", "owner_type": "claim",
                     "owner_id": "root", "severity": "blocking", "status": "active",
                     "obligation": "Prove the missing implication to the unrestricted root."},
                ],
                "rationale": "Model a verified side route with an unresolved root implication.",
            })
            self.assertTrue(outcome.accepted, outcome.errors)
            strictly_verify_entities(store, target_id="lemma", claim_ids=["lemma"],
                                     inference_ids=["terminal"], artifact_id="strict-report")
            self.assertEqual(1, len(_integration_candidates(store.get_state())))
            patch = integration_patch(store, route_id="route")
            self.assertNotIn("root_alignment", patch["operations"][0]["metadata"])
            outcome = apply_operator_patch(store, patch)
            self.assertTrue(outcome.accepted, outcome.errors)
            state = store.get_state()
            claims = {row["claim_id"]: row for row in state["claims"]}
            self.assertEqual("integrated", claims["lemma"]["lifecycle_status"])
            self.assertEqual("active", claims["root"]["lifecycle_status"])
            self.assertEqual("untested", claims["root"]["validation_status"])
            self.assertEqual("active", state["debts"][0]["status"])
            self.assertEqual([], _integration_candidates(state))


if __name__ == "__main__":
    unittest.main()
