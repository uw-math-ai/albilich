from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.debt_canonicalizer import central_debt_clusters
from agents.generation.phase2.graph_policy import paused_route_ids, route_scoreboard
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.scheduler import next_action
from agents.generation.phase2.store import ProofStateStore


def _patch(store: ProofStateStore, *, base_revision: int, operations: list[dict], actor_role: str = "researcher") -> None:
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": base_revision,
            "actor_role": actor_role,
            "target_id": "root",
            "operations": operations,
            "rationale": "central obstruction unit test setup",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


class Phase2CentralObstructionTest(unittest.TestCase):
    def test_central_bridge_debt_schedules_researcher_workbench(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("central-workbench-scheduler-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            _patch(
                store,
                base_revision=0,
                operations=[
                    {
                        "op": "add_claim",
                        "claim_id": "root_bridge",
                        "kind": "lemma",
                        "statement": "The central Rank chained bridge lemma.",
                        "parent_ids": ["root"],
                        "root_impact": 0.9,
                        "reduction_depth": 1,
                    },
                    {
                        "op": "add_route",
                        "route_id": "route-root-bridge",
                        "conclusion_claim_id": "root_bridge",
                        "relation_to_parent": "sufficient",
                        "strategy": "Prove the Rank chained bridge.",
                    },
                    {
                        "op": "attach_artifact",
                        "artifact_id": "route-obstruction-rank",
                        "artifact_type": "research_diagnostic",
                        "content": "Previous Rank attempt failed because it identified terms but not a common pure complex.",
                        "metadata": {
                            "target_id": "root_bridge",
                            "route_id": "route-root-bridge",
                            "failure_fingerprint": "termwise-Rank-not-pure-complex",
                            "lesson": "Do not reuse the termwise Rank expansion without proving the pure relative chained model.",
                        },
                    },
                    {
                        "op": "attach_artifact",
                        "artifact_id": "zz-generic-diagnostic",
                        "artifact_type": "research_diagnostic",
                        "content": "A generic summary of the current route state without a new mathematical lesson.",
                        "metadata": {
                            "target_id": "root_bridge",
                            "route_id": "route-root-bridge",
                        },
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-rank-bridge",
                        "owner_type": "claim",
                        "owner_id": "root_bridge",
                        "debt_type": "gap",
                        "severity": "blocking",
                        "obligation": "Prove the Rank-to-chained-complex bridge for the actual MSSS line bundle L_P.",
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-pure-chained",
                        "owner_type": "claim",
                        "owner_id": "root_bridge",
                        "debt_type": "gap",
                        "severity": "blocking",
                        "obligation": "Show the Rank rank-union feasible set gives a pure relative chained model.",
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-hd-stars",
                        "owner_type": "route",
                        "owner_id": "route-root-bridge",
                        "debt_type": "gap",
                        "severity": "blocking",
                        "obligation": "Identify h_d with interior local stars in the Rank chained construction.",
                    },
                ],
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, target_id=action["target_id"], route_id=action["route_id"], action=action)

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(action["search_intent"], "bridge_lemma_workbench")
        self.assertTrue(action["bridge_lemma_workbench_required"])
        self.assertTrue(action["closure_pressure_required"])
        self.assertTrue(action["cas_check_recommended"])
        self.assertEqual(action["central_obstruction"]["target_id"], "root_bridge")
        self.assertEqual(
            set(action["central_obstruction"]["alias_debt_ids"]),
            {"debt-rank-bridge", "debt-pure-chained", "debt-hd-stars"},
        )
        self.assertEqual(manifest["central_obstruction"]["target_id"], "root_bridge")
        self.assertTrue(manifest["workflow_action"]["bridge_lemma_workbench_required"])
        self.assertIn("workbench_acceptance_criteria", manifest["researcher_packet"])
        self.assertIn(
            "narrowed obligation",
            manifest["researcher_packet"]["staged_attack_policy"]["bridge_lemma_workbench_rule"],
        )
        self.assertIn("negative_result_ledger", manifest)
        self.assertEqual(manifest["negative_result_ledger"][0]["artifact_id"], "route-obstruction-rank")
        self.assertEqual(manifest["negative_result_ledger"][0]["failure_fingerprint"], "termwise-Rank-not-pure-complex")
        self.assertNotIn(
            "zz-generic-diagnostic",
            {row["artifact_id"] for row in manifest["negative_result_ledger"]},
        )
        self.assertIn("proof_architecture_templates", manifest)
        self.assertIn(
            "combinatorial-bridge-patterns",
            {row["template_id"] for row in manifest["proof_architecture_templates"]},
        )
        self.assertIn("cas_trigger_policy", manifest)

    def test_source_like_central_bridge_debt_prefers_workbench_over_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("central-workbench-source-like-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            _patch(
                store,
                base_revision=0,
                operations=[
                    {
                        "op": "add_claim",
                        "claim_id": "root_bridge",
                        "kind": "lemma",
                        "statement": "The central crown class-avoidance bridge lemma.",
                        "parent_ids": ["root"],
                        "root_impact": 0.95,
                        "reduction_depth": 1,
                    },
                    {
                        "op": "add_route",
                        "route_id": "route-root-bridge",
                        "conclusion_claim_id": "root_bridge",
                        "relation_to_parent": "sufficient",
                        "strategy": "Prove the crown class-avoidance bridge.",
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-crown-source",
                        "owner_type": "claim",
                        "owner_id": "root_bridge",
                        "debt_type": "missing_hypothesis",
                        "severity": "blocking",
                        "obligation": "Prove or cite the crown maximal subgroup class-avoidance bridge.",
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-nonsplit-source",
                        "owner_type": "route",
                        "owner_id": "route-root-bridge",
                        "debt_type": "missing_hypothesis",
                        "severity": "blocking",
                        "obligation": "Prove or cite the non-split crown construction controlling maximal subgroup class avoidance.",
                    },
                ],
            )
            _patch(
                store,
                base_revision=1,
                operations=[
                    {
                        "op": "attach_artifact",
                        "artifact_id": "search-request-crown-bridge",
                        "artifact_type": "literature_search_request",
                        "content": "Search for the crown bridge theorem.",
                        "metadata": {
                            "search_request_id": "req-crown-bridge",
                            "target_id": "root_bridge",
                            "route_id": "route-root-bridge",
                            "query": "crown maximal subgroup class avoidance bridge theorem",
                        },
                    }
                ],
            )

            action = next_action(store, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(action["search_intent"], "bridge_lemma_workbench")
        self.assertTrue(action["bridge_lemma_workbench_required"])
        self.assertEqual(action["route_id"], "route-root-bridge")
        self.assertEqual(
            set(action["central_obstruction"]["alias_debt_ids"]),
            {"debt-crown-source", "debt-nonsplit-source"},
        )

    def test_root_level_central_workbench_does_not_borrow_unrelated_root_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("central-workbench-root-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            _patch(
                store,
                base_revision=0,
                operations=[
                    {
                        "op": "add_route",
                        "route_id": "route-root-old",
                        "conclusion_claim_id": "root",
                        "relation_to_parent": "sufficient",
                        "strategy": "An older root route.",
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-root-crown",
                        "owner_type": "claim",
                        "owner_id": "root",
                        "debt_type": "missing_hypothesis",
                        "severity": "blocking",
                        "obligation": "Prove or cite the root crown maximal subgroup class-avoidance bridge.",
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-root-nonsplit",
                        "owner_type": "claim",
                        "owner_id": "root",
                        "debt_type": "missing_hypothesis",
                        "severity": "blocking",
                        "obligation": "Prove or cite the root non-split crown construction controlling maximal subgroup class avoidance.",
                    },
                ],
            )

            action = next_action(store, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["route_id"], "")
        self.assertEqual(action["search_intent"], "bridge_lemma_workbench")
        self.assertTrue(action["bridge_lemma_workbench_required"])

    def test_group_bridge_workbench_exposes_group_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("central-workbench-group-template-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Finite group crown and maximal subgroup class-avoidance bridge.")
            action = {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "",
                "bridge_lemma_workbench_required": True,
                "proof_architecture_templates_required": True,
                "central_obstruction": {
                    "keywords": ["crown", "non-split", "subgroup", "maximal"],
                    "obligation": "Prove the crown/non-split class-avoidance bridge.",
                },
            }

            manifest = build_context_manifest(store, action=action)

        self.assertIn(
            "finite-group-closure-patterns",
            {row["template_id"] for row in manifest["proof_architecture_templates"]},
        )

    def test_blocked_route_is_paused_not_selected_as_ordinary_trunk(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "statement": "Root",
                    "root_impact": 1.0,
                    "reduction_depth": 0,
                    "validation_status": "untested",
                    "lifecycle_status": "active",
                    "parent_ids_json": "[]",
                }
            ],
            "routes": [
                {
                    "route_id": "route-blocked",
                    "conclusion_claim_id": "root",
                    "status": "blocked",
                    "relation_to_parent": "sufficient",
                    "label": "Blocked route",
                    "failure_fingerprint": "known-obstruction",
                }
            ],
            "inferences": [],
            "debts": [],
            "research_artifacts": [],
        }

        scoreboard = route_scoreboard(state)

        self.assertEqual(scoreboard[0]["scoreboard_status"], "blocked")
        self.assertIn("route-blocked", paused_route_ids(state))


if __name__ == "__main__":
    unittest.main()
