from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.research_strategy import (
    ADVISOR_SYNTHESIS_REQUIRED_FIELDS,
    EXPERIMENT_REQUIRED_FIELDS,
    INVENTION_CONDITION_KEYS,
    PROOF_COMPRESSION_SKELETON_REQUIRED_FIELDS,
    advisor_synthesis_trigger,
    apply_active_compression,
    enrich_action,
    latest_active_advisor_synthesis,
    next_strategy_operation,
    retrieve_method_cards,
    score_action,
    strategy_context_card,
)
from agents.generation.phase2.scheduler import next_action
from agents.generation.phase2.store import ProofStateStore


def _bridge_candidate(
    bridge_id: str,
    statement: str,
    *,
    status: str = "selected",
    closes: bool = True,
    leverage: float = 0.9,
    difficulty: float = 0.3,
    methods: list[str] | None = None,
) -> dict:
    return {
        "bridge_id": bridge_id,
        "statement": statement,
        "forward_support": ["root"],
        "target_route_id": "route-root",
        "root_consequence": "The root follows after the existing route assembly.",
        "hidden_obligations": [],
        "estimated_difficulty": difficulty,
        "estimated_root_leverage": leverage,
        "possible_methods": methods or ["direct proof"],
        "falsifiability_plan": "Test the smallest admissible examples and the route boundary case.",
        "status": status,
        "selection_reason": "Highest sufficiency and root-leverage score.",
        "sufficiency_precheck": {
            "materially_reduces_gap": status != "rejected",
            "would_reach_root": closes,
            "restates_root": False,
            "creates_more_severe_obligations": False,
            "hidden_obligations": [],
        },
    }


def _bridge_metadata(*candidates: dict) -> dict:
    return {
        "strategy_schema_version": 1,
        "target_id": "root",
        "bridge_candidates": list(candidates),
    }


def _advisor_synthesis_metadata(*, base_revision: int, supersedes: str = "") -> dict:
    metadata = {
        "strategy_schema_version": 1,
        "valid_until_revision": base_revision + 20,
        "advisor_synthesis": {
            "exact_root_status": "The root is open with one theorem-level gap.",
            "verified_core": ["root"],
            "best_route": "route-root",
            "best_route_summary": "Use the verified core and one bridge.",
            "shortest_plausible_proof_skeleton": ["verified core", "bridge", "root assembly"],
            "decisive_missing_statement": "Every admissible endpoint satisfies the bridge condition.",
            "alternate_routes": ["route-alt"],
            "routes_to_continue": ["route-root"],
            "routes_to_pause": ["route-alt"],
            "routes_to_abandon": [],
            "duplicated_or_stagnant_work": ["repeated broad search"],
            "evidence_that_would_change_strategy": ["a counterexample to the bridge"],
            "recommended_next_actions": ["prove or refute the bridge"],
            "budget_distribution": {"route-root": 0.8, "counterexample_test": 0.2},
            "synthesis_confidence": 0.75,
        },
    }
    if supersedes:
        metadata["supersedes_synthesis_id"] = supersedes
    return metadata


def _valid_experiment_metadata() -> dict:
    return {
        "experiment_workflow_version": 1,
        "mathematical_question": "Does the selected bridge fail in the smallest admissible case?",
        "competing_hypotheses": ["the bridge always holds", "a small counterexample exists"],
        "finite_scope": "All objects of size at most 8.",
        "backend_or_manual_method": "bounded enumeration",
        "code_or_calculation": "enumerate(size <= 8)",
        "expected_decisive_outputs": ["counterexample", "no counterexample in scope"],
        "observations": ["No failure through size 8."],
        "counterexamples": [],
        "interpretation": "The bridge survives the discriminating small cases but is not proved.",
        "next_proof_move": "Prove the structural reduction suggested by the equality cases.",
        "decision_changed": "Retire the small-counterexample attack and move to the structural proof.",
        "claims_infinite_statement_verified": False,
    }


def _pure_strategy_state(*, revision: int = 10) -> dict:
    claims = [
        {
            "claim_id": "root",
            "statement": "Target theorem.",
            "fingerprint": "root",
            "validation_status": "untested",
            "lifecycle_status": "active",
            "root_impact": 1.0,
        }
    ]
    for index in range(4):
        claims.append(
            {
                "claim_id": f"claim-{index}",
                "statement": f"Auxiliary statement {index}.",
                "fingerprint": f"claim-{index}",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 0.5,
            }
        )
    runs = [
        {
            "run_id": f"run-{index}",
            "actor_role": "researcher",
            "mode": "reduce",
            "target_id": "root",
            "state_revision": revision - index,
            "status": "completed",
            "search_intent": f"attempt-{index}",
            "output_artifact_ids_json": "[]",
        }
        for index in range(3)
    ]
    return {
        "problem_state": {
            "problem_id": "strategy-pure",
            "root_statement": "Target theorem.",
            "current_revision": revision,
            "remaining_token_budget": 1_000_000,
            "reserved_verification_budget": 100_000,
        },
        "claims": claims,
        "routes": [],
        "inferences": [],
        "debts": [],
        "research_artifacts": [],
        "recent_runs": runs,
    }


class Phase2ResearchStrategyTest(unittest.TestCase):
    def _store(self, tmpdir: str, problem_id: str) -> ProofStateStore:
        store = ProofStateStore(problem_id, generation_root=Path(tmpdir) / "generation")
        store.init_problem("Target theorem.")
        return store

    def _attach(self, store: ProofStateStore, actor: str, artifact_id: str, artifact_type: str, metadata: dict):
        return apply_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": store.get_revision(),
                "actor_role": actor,
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": artifact_id,
                        "artifact_type": artifact_type,
                        "content": f"{artifact_type} content for {artifact_id}.",
                        "metadata": metadata,
                    }
                ],
                "rationale": f"attach {artifact_type}",
            },
        )

    def test_method_retrieval_uses_structural_signature_and_includes_failures(self) -> None:
        cards = retrieve_method_cards(
            "A construction exists at every place and on each piece, but the pieces do not glue into one global object."
        )
        self.assertTrue(cards)
        self.assertEqual(cards[0]["method_id"], "local_to_global_obstruction")
        self.assertIn("compatibility_obstruction", cards[0]["matched_structural_features"])
        self.assertTrue(cards[0]["known_failure_modes"])
        self.assertTrue(cards[0]["advisory_only"])

    def test_bridge_search_enforces_limit_and_sufficiency_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-bridge-limits")
            too_many = self._attach(
                store,
                "researcher",
                "bridge-too-many",
                "bridge_lemma_search",
                _bridge_metadata(
                    *[_bridge_candidate(f"bridge-{index}", f"Bridge statement {index}.") for index in range(4)]
                ),
            )
            self.assertFalse(too_many.accepted)
            self.assertTrue(any("one to three" in error for error in too_many.errors))

            side = _bridge_candidate(
                "bridge-side",
                "An interesting side lemma.",
                status="rejected",
                closes=False,
                leverage=0.2,
            )
            side["sufficiency_precheck"]["materially_reduces_gap"] = False
            accepted = self._attach(
                store,
                "researcher",
                "bridge-ranked",
                "bridge_lemma_search",
                _bridge_metadata(
                    _bridge_candidate("bridge-close", "The route-closing bridge theorem."),
                    side,
                ),
            )
            self.assertTrue(accepted.accepted, accepted.errors)

    def test_manifest_viable_bridge_status_is_accepted_by_validator(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-bridge-viable-status")
            manifest = build_context_manifest(
                store,
                target_id="root",
                max_chars=30_000,
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "bidirectional_bridge_search_required": True,
                },
            )
            status_contract = manifest["bridge_lemma_search_contract"]["metadata_shape"]["bridge_candidates"][0]["status"]
            self.assertIn("viable", status_contract.split("|"))

            selected = _bridge_candidate(
                "bridge-selected",
                "The selected route-closing bridge theorem.",
                leverage=0.9,
            )
            runner_up = _bridge_candidate(
                "bridge-runner-up",
                "A distinct viable bridge theorem.",
                status="viable",
                closes=False,
                leverage=0.3,
            )
            accepted = self._attach(
                store,
                "researcher",
                "bridge-with-viable-runner-up",
                "bridge_lemma_search",
                _bridge_metadata(selected, runner_up),
            )
            self.assertTrue(accepted.accepted, accepted.errors)
    def test_duplicate_active_bridge_must_be_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-bridge-duplicate")
            add_claim = apply_patch(
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
                            "claim_id": "existing-bridge",
                            "kind": "lemma",
                            "statement": "The route-closing bridge theorem.",
                            "validation_status": "plausible",
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                        }
                    ],
                    "rationale": "seed existing bridge",
                },
            )
            self.assertTrue(add_claim.accepted, add_claim.errors)
            outcome = self._attach(
                store,
                "researcher",
                "bridge-duplicate",
                "bridge_lemma_search",
                _bridge_metadata(_bridge_candidate("bridge-copy", "The route-closing bridge theorem.")),
            )
            self.assertFalse(outcome.accepted)
            self.assertTrue(any("duplicates an existing claim" in error for error in outcome.errors))

    def test_bridge_workbench_is_enriched_with_two_sided_frontier(self) -> None:
        state = _pure_strategy_state()
        state["claims"][1]["validation_status"] = "informally_verified"
        state["debts"] = [
            {
                "debt_id": "debt-root-bridge",
                "owner_id": "root",
                "obligation": "Prove the endpoint compatibility bridge.",
                "severity": "blocking",
                "status": "active",
                "repeated_count": 3,
            }
        ]
        action = enrich_action(
            state,
            {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "",
                "reason": "central bridge is blocked",
                "bridge_lemma_workbench_required": True,
                "budget": {"allowed": True, "requested_tokens": 100_000},
            },
        )
        self.assertTrue(action["bidirectional_bridge_search_required"])
        self.assertEqual(action["bridge_candidate_limit"], 3)
        self.assertTrue(action["bridge_search_context"]["forward_frontier"])
        self.assertTrue(action["bridge_search_context"]["backward_frontier"])
        self.assertIn("expected_value_score", action["information_gain_score"])

    def test_global_synthesis_trigger_runs_compression_then_phd_advisor(self) -> None:
        state = _pure_strategy_state()
        trigger = advisor_synthesis_trigger(state)
        self.assertTrue(trigger["due"])
        first = next_strategy_operation(state, {"mode": "retrieve", "target_id": "root", "route_id": ""})
        self.assertEqual(first["operation"], "proof_compression")
        state["research_artifacts"].append(
            {
                "artifact_id": "compression-1",
                "artifact_type": "proof_compression",
                "state_revision": 10,
                "metadata_json": "{\"minimal_proof_skeleton\": {\"essential_verified_facts\": [\"root\"]}}",
            }
        )
        second = next_strategy_operation(state, {"mode": "retrieve", "target_id": "root", "route_id": ""})
        self.assertEqual(second["operation"], "advisor_global_synthesis")
        self.assertEqual(second["mode"], "triage_routes")
        self.assertTrue(second["advisor_global_synthesis_required"])

    def test_global_synthesis_manifest_exposes_exact_metadata_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-synthesis-contract")
            manifest = build_context_manifest(
                store,
                target_id="root",
                max_chars=30_000,
                action={
                    "mode": "triage_routes",
                    "target_id": "root",
                    "advisor_global_synthesis_required": True,
                    "synthesis_trigger": {"latest_synthesis_artifact_id": ""},
                },
            )

        contract = manifest["advisor_synthesis_contract"]
        synthesis = contract["metadata_shape"]["advisor_synthesis"]
        self.assertEqual(set(synthesis), set(ADVISOR_SYNTHESIS_REQUIRED_FIELDS))
        self.assertIn("metadata.advisor_synthesis", contract["nesting_rule"])
        self.assertTrue(any("manifest.advisor_synthesis_contract exactly" in line for line in manifest["instructions"]))

    def test_bridge_search_manifest_exposes_exact_metadata_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-bridge-contract")
            manifest = build_context_manifest(
                store,
                target_id="root",
                max_chars=30_000,
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "bidirectional_bridge_search_required": True,
                },
            )

        contract = manifest["bridge_lemma_search_contract"]
        candidate = contract["metadata_shape"]["bridge_candidates"][0]
        self.assertIn("bridge_id", candidate)
        self.assertIn("forward_support", candidate)
        self.assertIn("sufficiency_precheck", candidate)
        self.assertIn("do not rename it candidates", contract["nesting_rule"])
        self.assertTrue(any("manifest.bridge_lemma_search_contract exactly" in line for line in manifest["instructions"]))

    def test_proof_compression_manifest_exposes_exact_metadata_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-compression-contract")
            manifest = build_context_manifest(
                store,
                target_id="root",
                max_chars=30_000,
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "proof_compression_operation_required": True,
                },
            )

        contract = manifest["proof_compression_contract"]
        skeleton = contract["metadata_shape"]["minimal_proof_skeleton"]
        self.assertEqual(set(skeleton), set(PROOF_COMPRESSION_SKELETON_REQUIRED_FIELDS))
        self.assertTrue(contract["metadata_shape"]["history_preserved"])
        self.assertIn("metadata.minimal_proof_skeleton", contract["nesting_rule"])
        self.assertIn("may be empty", contract["verified_fact_rule"])
        self.assertTrue(any("manifest.proof_compression_contract exactly" in line for line in manifest["instructions"]))

    def test_proof_compression_accepts_no_verified_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-compression-empty-verified-core")
            accepted = self._attach(
                store,
                "researcher",
                "compression-empty-verified-core",
                "proof_compression",
                {
                    "strategy_schema_version": 1,
                    "history_preserved": True,
                    "minimal_proof_skeleton": {
                        "root": "root",
                        "essential_verified_facts": [],
                        "essential_routes": ["none_yet"],
                        "unresolved_bridges": ["Prove the remaining bridge."],
                        "conditional_steps": ["If the bridge holds, the root follows."],
                        "unused_or_low_value_branches": ["Retire the failed branch."],
                        "shortest_known_route": ["Prove the bridge."],
                        "weakest_sufficient_new_statement": "The bridge holds.",
                    },
                },
            )

        self.assertTrue(accepted.accepted, accepted.errors)

    def test_cas_mode_manifest_exposes_exact_experiment_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-cas-contract")
            manifest = build_context_manifest(
                store,
                target_id="root",
                max_chars=30_000,
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "researcher_work_mode": "cas",
                },
            )

        contract = manifest["cas_experiment_contract"]
        self.assertEqual(
            set(EXPERIMENT_REQUIRED_FIELDS) | {"decision_changed"},
            set(contract["required_fields"]),
        )
        self.assertIn("decision_changed", contract["metadata_shape"])
        self.assertEqual(contract["list_rules"]["counterexamples"], "a list, possibly empty")
        self.assertTrue(any("manifest.cas_experiment_contract exactly" in line for line in manifest["instructions"]))

    def test_new_advisor_synthesis_must_supersede_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-synthesis-supersession")
            first = self._attach(
                store,
                "phd_advisor",
                "synthesis-1",
                "advisor_synthesis",
                _advisor_synthesis_metadata(base_revision=0),
            )
            self.assertTrue(first.accepted, first.errors)
            stale_append = self._attach(
                store,
                "phd_advisor",
                "synthesis-2-bad",
                "advisor_synthesis",
                _advisor_synthesis_metadata(base_revision=1),
            )
            self.assertFalse(stale_append.accepted)
            self.assertTrue(any("must supersede" in error for error in stale_append.errors))
            second = self._attach(
                store,
                "phd_advisor",
                "synthesis-2",
                "advisor_synthesis",
                _advisor_synthesis_metadata(base_revision=1, supersedes="synthesis-1"),
            )
            self.assertTrue(second.accepted, second.errors)
            latest = latest_active_advisor_synthesis(store.get_state())
            self.assertEqual(latest["artifact_id"], "synthesis-2")

    def test_old_latest_synthesis_stays_in_scheduler_snapshot_and_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-synthesis-sticky-snapshot")
            first = self._attach(
                store,
                "phd_advisor",
                "synthesis-old-but-latest",
                "advisor_synthesis",
                _advisor_synthesis_metadata(base_revision=0),
            )
            self.assertTrue(first.accepted, first.errors)
            for index in range(50):
                outcome = self._attach(
                    store,
                    "researcher",
                    f"newer-notebook-{index}",
                    "research_notebook",
                    {"target_id": "root", "index": index},
                )
                self.assertTrue(outcome.accepted, outcome.errors)

            state = store.get_scheduler_state()
            artifact_ids = {
                str(row.get("artifact_id") or "")
                for row in state["research_artifacts"]
            }
            trigger = advisor_synthesis_trigger(state)
            action = {
                "mode": "triage_routes",
                "target_id": "root",
                "advisor_global_synthesis_required": True,
                "synthesis_trigger": trigger,
            }
            manifest = build_context_manifest(store, action=action)

        self.assertIn("synthesis-old-but-latest", artifact_ids)
        self.assertEqual(
            trigger["latest_synthesis_artifact_id"],
            "synthesis-old-but-latest",
        )
        self.assertEqual(
            manifest["advisor_synthesis_contract"]["metadata_shape"]["supersedes_synthesis_id"],
            "synthesis-old-but-latest",
        )

    def test_invention_requires_full_advisor_authorization_and_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-invention-gate")
            invalid_metadata = {
                "strategy_schema_version": 1,
                "invention_authorized": True,
                "shared_obstruction": "Two routes fail at the same compatibility condition.",
                "why_existing_language_is_insufficient": "No standard invariant records the needed behavior.",
                "required_properties": ["evaluable", "stable under quotient"],
                "maximum_candidates": 2,
                "maximum_research_passes": 2,
                "token_budget": 20_000,
                "authorization_revision": 0,
                "authorization_conditions": {key: True for key in INVENTION_CONDITION_KEYS},
            }
            invalid_metadata["authorization_conditions"]["literature_search_exhausted"] = False
            invalid = self._attach(
                store,
                "phd_advisor",
                "invention-invalid",
                "invention_authorization",
                invalid_metadata,
            )
            self.assertFalse(invalid.accepted)

            valid_metadata = dict(invalid_metadata)
            valid_metadata["authorization_conditions"] = {key: True for key in INVENTION_CONDITION_KEYS}
            valid_metadata["authorization_revision"] = store.get_revision()
            valid = self._attach(
                store,
                "phd_advisor",
                "invention-auth",
                "invention_authorization",
                valid_metadata,
            )
            self.assertTrue(valid.accepted, valid.errors)
            signal = next_strategy_operation(
                store.get_scheduler_state(),
                {"mode": "retrieve", "target_id": "root", "route_id": ""},
            )
            self.assertEqual(signal["operation"], "definition_invention")

            for index in range(2):
                candidate = self._attach(
                    store,
                    "researcher",
                    f"definition-{index}",
                    "definition_candidate",
                    {
                        "strategy_schema_version": 1,
                        "authorization_artifact_id": "invention-auth",
                        "candidate_id": f"definition-{index}",
                        "statement": f"Auxiliary invariant {index}.",
                        "lifecycle_status": "experimental_definition",
                        "evaluation_example": f"Example {index} has value {index}.",
                        "exact_bridge_lemma": f"If invariant {index} vanishes, the bridge holds.",
                    },
                )
                self.assertTrue(candidate.accepted, candidate.errors)
            third = self._attach(
                store,
                "researcher",
                "definition-2",
                "definition_candidate",
                {
                    "strategy_schema_version": 1,
                    "authorization_artifact_id": "invention-auth",
                    "candidate_id": "definition-2",
                    "statement": "Auxiliary invariant 2.",
                    "lifecycle_status": "experimental_definition",
                    "evaluation_example": "Example 2 has value 2.",
                    "exact_bridge_lemma": "If invariant 2 vanishes, the bridge holds.",
                },
            )
            self.assertFalse(third.accepted)
            self.assertTrue(any("candidate limit" in error for error in third.errors))

    def test_experiment_contract_rejects_raw_output_and_cannot_close_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-experiment-contract")
            debt = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-experiment",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Decide the finite bridge test.",
                        }
                    ],
                    "rationale": "seed experimental debt",
                },
            )
            self.assertTrue(debt.accepted, debt.errors)
            raw = self._attach(
                store,
                "researcher",
                "cas-raw",
                "cas_experiment_report",
                {"experiment_workflow_version": 1, "observations": ["42"]},
            )
            self.assertFalse(raw.accepted)
            self.assertTrue(any("mathematical_question" in error for error in raw.errors))

            patch = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "cas-decisive",
                            "artifact_type": "cas_experiment_report",
                            "content": "Bounded experiment with mathematical interpretation.",
                            "metadata": _valid_experiment_metadata(),
                        },
                        {
                            "op": "resolve_debt",
                            "debt_id": "debt-experiment",
                            "resolution_evidence": {"artifact_id": "cas-decisive"},
                        },
                    ],
                    "rationale": "record experiment and submit repair",
                },
            )
            self.assertTrue(patch.accepted, patch.errors)
            state = store.get_state()
            debt_row = next(row for row in state["debts"] if row["debt_id"] == "debt-experiment")
            self.assertEqual(debt_row["status"], "active")
            self.assertIn("pending_verifier", debt_row["resolution_evidence_json"])

    def test_conjecture_portfolio_is_bounded_and_preserves_equivalence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-conjecture-limits")
            base_candidate = {
                "conjecture_id": "conj-equivalent",
                "category": "equivalent_reformulation",
                "statement": "An equivalent formulation of the root.",
                "bottleneck_id": "root",
                "root_utility": "Would expose the only missing bridge.",
                "evidence": [],
                "counterexample_plan": "Check both implication directions on boundary examples.",
                "literature_status": "No duplicate found in the reviewed local cards.",
                "estimated_cost": 0.4,
                "status": "selected",
                "prechecks": {
                    "root_utility": True,
                    "nontriviality": True,
                    "small_examples": True,
                    "counterexample_search": True,
                    "literature_novelty": True,
                    "estimated_proof_cost": 0.4,
                    "duplication_check": True,
                    "exact_hypotheses_preserved": True,
                    "exact_quantifiers_preserved": False,
                },
            }
            bad = self._attach(
                store,
                "researcher",
                "conjecture-bad",
                "conjecture_portfolio",
                {
                    "strategy_schema_version": 1,
                    "conjectures": [base_candidate],
                },
            )
            self.assertFalse(bad.accepted)
            self.assertTrue(any("exact hypotheses and quantifiers" in error for error in bad.errors))
            base_candidate["prechecks"]["exact_quantifiers_preserved"] = True
            good = self._attach(
                store,
                "researcher",
                "conjecture-good",
                "conjecture_portfolio",
                {
                    "strategy_schema_version": 1,
                    "conjectures": [base_candidate],
                },
            )
            self.assertTrue(good.accepted, good.errors)

    def test_decisive_negative_experiment_outranks_generic_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-information-gain")
            bridge = self._attach(
                store,
                "researcher",
                "bridge-cas-selected",
                "bridge_lemma_search",
                _bridge_metadata(
                    _bridge_candidate(
                        "bridge-cas",
                        "Every minimal endpoint satisfies the compatibility condition.",
                        methods=["bounded CAS counterexample search"],
                    )
                ),
            )
            self.assertTrue(bridge.accepted, bridge.errors)
            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action)
            self.assertEqual(action["search_intent"], "experiment_conjecture_proof")
            self.assertTrue(action["experiment_workflow_required"])
            self.assertEqual(action["researcher_work_mode"], "cas")
            self.assertGreater(
                action["information_gain_score"]["probability_of_refuting_route"],
                action["information_gain_score"]["verification_cost"],
            )
            self.assertTrue(manifest["workflow_action"]["experiment_workflow_required"])

    def test_deep_session_is_only_added_for_root_critical_work(self) -> None:
        state = _pure_strategy_state()
        deep = enrich_action(
            state,
            {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "",
                "reason": "hard central theorem",
                "deep_research_required": True,
                "budget": {"allowed": True},
            },
        )
        self.assertTrue(deep["deep_session_required"])
        self.assertFalse(deep["deep_session"]["verification_authority"])
        self.assertEqual(deep["deep_session"]["required_deliverable"]["strategy_schema_version"], 1)
        self.assertIn("strategy_schema_version", deep["deep_session"]["required_deliverable"]["fields"])
        self.assertIn("state_patch_operations", deep["deep_session"]["required_deliverable"]["fields"])
        self.assertIn(
            "nonempty list",
            deep["deep_session"]["required_deliverable"]["field_rules"]["candidate_lemmas"],
        )
        routine = enrich_action(
            state,
            {
                "mode": "retrieve",
                "target_id": "root",
                "route_id": "",
                "reason": "routine search",
                "budget": {"allowed": True},
            },
        )
        self.assertNotIn("deep_session_required", routine)

    def test_offline_deep_session_accepts_empty_source_adaptations(self) -> None:
        metadata = {
            "strategy_schema_version": 1,
            "complete_local_argument": "A complete local reduction with one named gap.",
            "candidate_lemmas": ["The reduction lemma."],
            "failed_approaches": ["The direct counting bound was too weak."],
            "new_obstructions": ["One exact family bound remains."],
            "source_adaptations": [],
            "proposed_route_revision": {"route_id": "route-root"},
            "next_decisive_step": "Prove the remaining family bound.",
            "state_patch_operations": ["Attach the reduction lemma."],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-deep-session-offline")
            accepted = self._attach(
                store,
                "researcher",
                "deep-session-offline",
                "deep_session_report",
                metadata,
            )
            self.assertTrue(accepted.accepted, accepted.errors)

            missing_field = dict(metadata)
            del missing_field["source_adaptations"]
            rejected = self._attach(
                store,
                "researcher",
                "deep-session-missing-source-field",
                "deep_session_report",
                missing_field,
            )
            self.assertFalse(rejected.accepted)
            self.assertIn(
                "deep_session_report requires source_adaptations as a list (possibly empty)",
                rejected.errors,
            )

    def test_active_proof_compression_shrinks_context_without_deleting_history(self) -> None:
        state = _pure_strategy_state()
        state["research_artifacts"] = [
            {
                "artifact_id": "compression-active",
                "artifact_type": "proof_compression",
                "state_revision": 10,
                "metadata_json": (
                    "{\"minimal_proof_skeleton\": {"
                    "\"essential_verified_facts\": [\"claim-0\"], "
                    "\"weakest_sufficient_new_statement\": \"Prove the final bridge.\"}}"
                ),
            }
        ]
        selected = ["root", "claim-0", "claim-1", "claim-2"]
        compressed, observability = apply_active_compression(state, selected, target_id="root")
        self.assertEqual(set(compressed), {"root", "claim-0"})
        self.assertLess(observability["after_claim_count"], observability["before_claim_count"])
        self.assertTrue(observability["history_preserved"])
        self.assertEqual(len(state["claims"]), 5)

    def test_method_cards_and_strategy_artifacts_are_never_proof_premises(self) -> None:
        state = _pure_strategy_state()
        action = enrich_action(
            state,
            {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "",
                "reason": "local choices do not glue into a global object",
                "budget": {"allowed": True},
            },
        )
        card = strategy_context_card(state, action)
        self.assertEqual(card["memory_separation"]["strategic_method_cards"], "developer-curated advisory cards; never proof premises")
        self.assertFalse(action["method_cards_are_proof_evidence"])

    def test_information_gain_score_penalizes_duplicate_actions(self) -> None:
        state = _pure_strategy_state()
        action = {
            "mode": "reduce",
            "target_id": "root",
            "route_id": "",
            "search_intent": "repeat-me",
            "budget": {"allowed": True},
        }
        baseline = score_action(state, action)
        for run in state["recent_runs"]:
            run["search_intent"] = "repeat-me"
        duplicate = score_action(state, action)
        self.assertGreater(duplicate["duplication_risk"], baseline["duplication_risk"])
        self.assertLess(duplicate["expected_value_score"], baseline["expected_value_score"])


if __name__ == "__main__":
    unittest.main()
