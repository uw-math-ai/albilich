from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.generation.phase2.certificates import artifact_has_current_binding, rebase_dependency_lifecycle_bindings
from agents.generation.phase2.integration import integration_patch
from agents.generation.phase2.invariants import validate_conn
from agents.generation.phase2.models import SCHEMA_VERSION, json_loads
from agents.generation.phase2.patches import _state_journal_projection, apply_operator_patch
from agents.generation.phase2.replay import verify_patch_journal
from agents.generation.phase2.store import ProofStateStore
from agents.generation.tests._phase2_test_support import strictly_verify_entities


class DependencyIntegrationCertificateTests(unittest.TestCase):
    def seed(self, tmp):
        store = ProofStateStore("dependency-integration", generation_root=Path(tmp))
        store.init_problem("The unrestricted root theorem.")
        operations = []
        for claim, premises in (("premise", []), ("dependent", ["premise"])):
            operations.extend([
                {"op": "add_claim", "claim_id": claim, "kind": "lemma",
                 "statement": "Exact theorem " + claim, "parent_ids": ["root"]},
                {"op": "add_route", "route_id": "route-" + claim,
                 "conclusion_claim_id": claim, "relation_to_parent": "sufficient",
                 "strategy": "Prove the local theorem."},
                {"op": "add_inference", "inference_id": "inference-" + claim,
                 "route_id": "route-" + claim, "conclusion_claim_id": claim,
                 "premise_claim_ids": premises, "explanation": "Exact local proof."},
            ])
        outcome = apply_operator_patch(store, {
            "schema_version": SCHEMA_VERSION, "problem_id": store.problem_id,
            "base_revision": 0, "actor_role": "researcher", "target_id": "root",
            "operations": operations, "rationale": "Seed a proof dependency chain.",
        })
        self.assertTrue(outcome.accepted, outcome.errors)
        for claim in ("premise", "dependent"):
            strictly_verify_entities(store, target_id=claim, claim_ids=[claim],
                                     inference_ids=["inference-" + claim], artifact_id="review-" + claim)
        return store

    def test_premise_integration_preserves_downstream_certificates_in_either_order(self):
        for order in (("premise", "dependent"), ("dependent", "premise")):
            with self.subTest(order=order), tempfile.TemporaryDirectory() as tmp:
                store = self.seed(tmp)
                with store.connect() as conn:
                    original = json_loads(conn.execute(
                        "SELECT metadata_json FROM artifacts WHERE artifact_id='review-dependent'"
                    ).fetchone()[0])["host_certificate_bindings"]
                for claim in order:
                    outcome = apply_operator_patch(store, integration_patch(store, route_id="route-" + claim))
                    self.assertTrue(outcome.accepted, outcome.errors)
                with store.connect() as conn:
                    self.assertEqual([], validate_conn(conn))
                    for kind, entity in (("claim", "dependent"), ("inference", "inference-dependent")):
                        self.assertTrue(artifact_has_current_binding(
                            conn, "review-dependent", entity_type=kind, entity_id=entity))
                    updated = json_loads(conn.execute(
                        "SELECT metadata_json FROM artifacts WHERE artifact_id='review-dependent'"
                    ).fetchone()[0])["host_certificate_bindings"]
                    for key, old in original.items():
                        for field in ("subject_digest", "artifact_sha256", "bound_revision",
                                      "certified_status", "reviewer_identity"):
                            self.assertEqual(old[field], updated[key][field], field)
                        self.assertEqual(old["dependency_digest"],
                                         updated[key]["dependency_lifecycle_rebases"][0]["previous_dependency_digest"])
                    # A real proof edit must still make the downstream certificate stale.
                    conn.execute("UPDATE inferences SET explanation='Changed proof' WHERE inference_id='inference-premise'")
                    self.assertFalse(artifact_has_current_binding(
                        conn, "review-dependent", entity_type="claim", entity_id="dependent"))
                    conn.rollback()
                self.assertTrue(verify_patch_journal(store)["valid"])

    def test_lifecycle_rebase_does_not_refresh_changed_or_revoked_evidence(self):
        mutations = (
            "UPDATE inferences SET explanation='Changed argument' WHERE inference_id='inference-premise'",
            "UPDATE claims SET statement='Changed premise' WHERE claim_id='premise'",
            "UPDATE claims SET statement='Changed conclusion' WHERE claim_id='dependent'",
            "UPDATE claims SET validation_status='challenged' WHERE claim_id='premise'",
            "UPDATE claims SET validation_status='challenged' WHERE claim_id='dependent'",
            "UPDATE artifacts SET sha256='changed' WHERE artifact_id='review-dependent'",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = self.seed(tmp)
            for mutation in mutations:
                with self.subTest(mutation=mutation), store.connect() as conn:
                    conn.execute("BEGIN")
                    before = _state_journal_projection(conn)
                    old_metadata = conn.execute(
                        "SELECT metadata_json FROM artifacts WHERE artifact_id='review-dependent'"
                    ).fetchone()[0]
                    conn.execute("UPDATE claims SET lifecycle_status='integrated' WHERE claim_id='premise'")
                    conn.execute(mutation)
                    rebase_dependency_lifecycle_bindings(conn, previous_state=before, applied_revision=4)
                    metadata = conn.execute(
                        "SELECT metadata_json FROM artifacts WHERE artifact_id='review-dependent'"
                    ).fetchone()[0]
                    key = "claim:dependent"
                    self.assertEqual(json_loads(old_metadata)["host_certificate_bindings"][key],
                                     json_loads(metadata)["host_certificate_bindings"][key])
                    self.assertFalse(artifact_has_current_binding(
                        conn, "review-dependent", entity_type="claim", entity_id="dependent"))
                    conn.rollback()


if __name__ == "__main__":
    unittest.main()
