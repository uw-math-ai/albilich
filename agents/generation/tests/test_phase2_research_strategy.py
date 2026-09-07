from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.codex_runner import _base_mode_guidance
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_operator_patch as apply_patch
from agents.generation.phase2.research_strategy import (
    ADVISOR_SYNTHESIS_REQUIRED_FIELDS,
    EXPERIMENT_REQUIRED_FIELDS,
    INVENTION_CONDITION_KEYS,
    PROOF_COMPRESSION_SKELETON_REQUIRED_FIELDS,
    advisor_synthesis_trigger,
    apply_active_compression,
    approach_alignment_evidence,
    approach_portfolio_view,
    bottleneck_lease_state,
    conceptual_invariant_trigger,
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
        "root_leverage_gate": {
            "if_proved_major_case": closes,
            "if_refuted_information_gain": True,
            "stronger_than_necessary": False,
            "renames_current_gap": False,
            "hypotheses_attainable": True,
        },
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
        "experiment_workflow_version": 2,
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
        "reproduction_request": {"kind": "manual"},
    }


def _approach_candidate(index: int, *, status: str = "idea") -> dict:
    methods = (
        "induction on a canonical filtration",
        "spectral analysis of an incidence operator",
        "deformation to a rigid boundary object",
        "duality and categorical adjunction",
        "minimal-counterexample extremal argument",
        "probabilistic sampling followed by derandomization",
    )
    starts = (
        "Pass to the first nontrivial quotient in the filtration.",
        "Diagonalize the incidence operator and isolate its exceptional eigenspace.",
        "Construct a one-parameter degeneration to the boundary stratum.",
        "Apply the contravariant functor and work with the adjoint morphism.",
        "Choose a counterexample minimal in size and then in defect.",
        "Sample a random witness and convert the expectation bound into a deterministic choice.",
    )
    representations = (
        "filtered quotient sequence",
        "eigenspace decomposition",
        "flat deformation family",
        "dual category and adjunction unit",
        "lexicographically minimal obstruction",
        "probability space with a conditional-expectation potential",
    )
    return {
        "approach_id": f"approach-{index}",
        "title": f"Approach {index}",
        "method_family": methods[index],
        "independent_starting_point": starts[index],
        "mechanism": f"Develop the {methods[index]} through its characteristic construction.",
        "mathematical_objects": [f"object-{index}"],
        "representation_or_invariant": representations[index],
        "target_id": "root",
        "target_route_id": "none_yet",
        "root_consequence": "If the bridge is proved, the original theorem follows.",
        "bridge_statement": f"Exact bridge statement {index}.",
        "contribution_level": 5 if index == 0 else max(1, 5 - index),
        "contribution_kind": "root_closing" if index == 0 else "exploratory",
        "evidence": "A neighboring theorem suggests this mechanism.",
        "likely_failure_mode": f"Obstruction family {index} may survive.",
        "decisive_test": f"Test boundary family {index}.",
        "estimated_cost": "low" if index < 2 else "medium",
        "originality_status": "new_combination",
        "originality_rationale": f"This combines mechanism and representation family {index} in a distinct way.",
        "comparison_to_existing_work": f"The nearest known argument does not use the {representations[index]}; this changes the first reduction.",
        "confidence": "medium",
        "confidence_basis": "The analogy matches the main hypotheses but not yet the endpoint.",
        "status": status,
        "semantic_signature": {
            "mechanism": f"mechanism-{index}",
            "representation": f"representation-{index}",
            "proof_direction": "forward" if index % 2 == 0 else "adversarial",
            "theorem_family": f"theorem-family-{index}",
            "root_obligation": f"root-obligation-{index}",
            "failure_mode": f"failure-{index}",
        },
    }


def _approach_portfolio_metadata(*, kind: str = "initial", supersedes: str = "") -> dict:
    metadata = {
        "strategy_schema_version": 1,
        "portfolio_contract_version": 3,
        "portfolio_kind": kind,
        "brainstorming_summary": "Six genuinely different mechanisms were compared against the root.",
        "approaches": [_approach_candidate(index, status="selected" if index < 2 else "idea") for index in range(6)],
        "selected_approach_ids": ["approach-0", "approach-1"],
        "selection_rationale": "The first two mechanisms have complementary starting points and decisive tests.",
        "research_questions": ["Which boundary family distinguishes the first two mechanisms?"],
    }
    if supersedes:
        metadata["supersedes_artifact_id"] = supersedes
        for candidate in metadata["approaches"]:
            candidate["originality_status"] = "retained_prior_approach"
            candidate["originality_rationale"] = (
                "This is retained from the superseded portfolio for controlled comparison."
            )
    return metadata


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

    def test_hard_problem_starts_with_approach_portfolio_before_local_reduction(self) -> None:
        state = _pure_strategy_state()
        state["recent_runs"] = []
        action = next_strategy_operation(
            state,
            {"mode": "reduce", "target_id": "root", "route_id": "", "research_mode": "hard_problem"},
        )

        self.assertEqual(action["operation"], "approach_portfolio_brainstorming")
        self.assertTrue(action["approach_brainstorming_required"])
        self.assertTrue(action["proof_claim_creation_forbidden"])
        self.assertTrue(action["blocking_proof_debt_creation_forbidden"])
        self.assertEqual(action["approach_candidate_minimum"], 6)

    def test_bottleneck_receives_two_no_delta_passes_then_forces_creative_escape(self) -> None:
        state = _pure_strategy_state()
        primary = {
            "mode": "reduce",
            "target_id": "root",
            "route_id": "route-root",
            "debt_id": "debt-root",
            "proof_repair_required": True,
            "bottleneck_lock_required": True,
            "research_mode": "hard_problem",
        }

        lease = bottleneck_lease_state(state, primary)
        action = next_strategy_operation(state, primary)

        self.assertTrue(lease["escape_required"])
        self.assertGreaterEqual(lease["completed_no_delta_passes"], 2)
        self.assertEqual(action["operation"], "approach_portfolio_brainstorming")
        self.assertIn("no mathematical root-relevant delta", action["reason"])
        self.assertIsNone(lease["wall_clock_timeout"])

    def test_bottleneck_lease_consumes_only_the_exact_selected_obligation(self) -> None:
        state = _pure_strategy_state()
        selected_a = "base_recovery:bottleneck_lock:obligation-a"
        selected_b = "base_recovery:bottleneck_lock:obligation-b"
        recovery_trace = {
            "selected_candidate_id": selected_a,
            "candidates": [
                {
                    "candidate_id": selected_a,
                    "admissible": True,
                    "disposition": "selected",
                },
                {
                    "candidate_id": selected_b,
                    "admissible": True,
                    "disposition": "rejected_by_ordinal_comparison",
                },
            ],
        }
        outer_trace = {
            "selected_candidate_id": "base_open_problem:recovery_synthesis",
            "candidates": [
                {
                    "candidate_id": "base_open_problem:recovery_synthesis",
                    "admissible": True,
                    "disposition": "selected",
                }
            ],
            "nested_policy_traces": {
                "base_open_problem:recovery_synthesis": recovery_trace
            },
        }
        state["recent_runs"] = [
            {
                "run_id": f"run-{index}",
                "actor_role": "researcher",
                "mode": "prove",
                "target_id": "root",
                "status": "completed",
                "selection_design": "deterministic",
                "decision_trace_json": outer_trace,
                "decision_trace_history_included": True,
            }
            for index in range(2)
        ]
        action_a = {
            "target_id": "root",
            "debt_id": "obligation-a",
            "bottleneck_candidate_id": selected_a,
        }
        action_b = {
            "target_id": "root",
            "debt_id": "obligation-b",
            "bottleneck_candidate_id": selected_b,
        }

        lease_a = bottleneck_lease_state(state, action_a)
        lease_b = bottleneck_lease_state(state, action_b)

        self.assertTrue(lease_a["escape_required"])
        self.assertEqual(2, lease_a["completed_no_delta_passes"])
        self.assertFalse(lease_b["escape_required"])
        self.assertEqual(0, lease_b["completed_no_delta_passes"])

    def test_bottleneck_lease_fails_open_when_exact_trace_is_omitted(self) -> None:
        state = _pure_strategy_state()
        state["recent_runs"] = [
            {
                "run_id": "run-with-omitted-trace",
                "actor_role": "researcher",
                "mode": "prove",
                "target_id": "root",
                "status": "completed",
                "selection_design": "deterministic",
                "decision_trace_json": "{}",
                "decision_trace_history_included": False,
            }
        ]
        lease = bottleneck_lease_state(
            state,
            {
                "target_id": "root",
                "debt_id": "obligation-b",
                "bottleneck_candidate_id": (
                    "base_recovery:bottleneck_lock:obligation-b"
                ),
            },
        )

        self.assertFalse(lease["escape_required"])
        self.assertEqual(0, lease["completed_no_delta_passes"])

    def test_fresh_bottleneck_is_not_preempted_only_because_portfolio_is_missing(self) -> None:
        state = _pure_strategy_state()
        state["recent_runs"] = []
        action = next_strategy_operation(
            state,
            {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "route-root",
                "debt_id": "debt-root",
                "proof_repair_required": True,
                "bottleneck_lock_required": True,
                "research_mode": "hard_problem",
            },
        )

        self.assertIsNone(action)

    def test_approach_portfolio_validation_and_selected_pilot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-approach-portfolio")
            accepted = self._attach(
                store,
                "researcher",
                "portfolio-initial",
                "approach_portfolio",
                _approach_portfolio_metadata(),
            )
            self.assertTrue(accepted.accepted, accepted.errors)
            state = store.get_scheduler_state()
            view = approach_portfolio_view(state)
            action = next_strategy_operation(
                state,
                {"mode": "reduce", "target_id": "root", "route_id": "", "research_mode": "hard_problem"},
            )

        self.assertEqual(view["approach_count"], 6)
        self.assertEqual(view["selected_approach_ids"], ["approach-0", "approach-1"])
        self.assertEqual(action["operation"], "approach_pilot")
        self.assertTrue(action["search_intent"].startswith("approach_pilot:"))

    def test_compact_legacy_portfolio_cannot_downgrade_the_current_contract(self) -> None:
        compact = {
            "strategy_schema_version": 1,
            "portfolio_kind": "initial",
            "approaches": [
                {
                    "approach_id": f"compact-{index}",
                    "title": f"Compact route {index}",
                    "mechanism": f"Use mechanism {index}.",
                    "root_consequence": f"The mechanism would settle root branch {index}.",
                    "decisive_test": f"Test boundary case {index}.",
                    "status": "idea",
                }
                for index in range(3)
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-compact-approach-portfolio")
            accepted = self._attach(
                store,
                "researcher",
                "portfolio-compact",
                "approach_portfolio",
                compact,
            )
            self.assertFalse(accepted.accepted)

        self.assertIn("may not downgrade", " ".join(accepted.errors))

    def test_failed_brainstorm_without_portfolio_is_visible_as_retry_pending(self) -> None:
        state = _pure_strategy_state()
        state["recent_runs"] = [
            {
                "run_id": "brainstorm-failed",
                "actor_role": "researcher",
                "mode": "reduce",
                "target_id": "root",
                "state_revision": 10,
                "status": "failed",
                "search_intent": "approach_portfolio_brainstorming",
                "output_artifact_ids_json": "[]",
            }
        ]

        view = approach_portfolio_view(state)
        action = next_strategy_operation(
            state,
            {"mode": "reduce", "target_id": "root", "route_id": "", "research_mode": "hard_problem"},
        )

        self.assertEqual(view["generation_state"]["status"], "retry_pending")
        self.assertEqual(view["generation_state"]["latest_run_id"], "brainstorm-failed")
        self.assertEqual(action["operation"], "approach_portfolio_brainstorming")

    def test_approach_portfolio_rejects_semantic_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-approach-duplicate")
            metadata = _approach_portfolio_metadata()
            metadata["approaches"][1]["semantic_signature"] = dict(metadata["approaches"][0]["semantic_signature"])
            rejected = self._attach(
                store,
                "researcher",
                "portfolio-duplicate",
                "approach_portfolio",
                metadata,
            )

        self.assertFalse(rejected.accepted)
        self.assertTrue(any("duplicates another semantic_signature" in error for error in rejected.errors))

    def test_rediscovered_prior_approach_cannot_be_labelled_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-prior-approach-originality")
            initial = self._attach(
                store,
                "researcher",
                "portfolio-originality-baseline",
                "approach_portfolio",
                _approach_portfolio_metadata(),
            )
            self.assertTrue(initial.accepted, initial.errors)
            refresh = _approach_portfolio_metadata(
                kind="refresh", supersedes="portfolio-originality-baseline"
            )
            refresh["approaches"][0]["originality_status"] = "potentially_original"
            refresh["approaches"][0]["originality_rationale"] = (
                "This incorrectly claims that an unchanged prior approach is original."
            )
            rejected = self._attach(
                store,
                "researcher",
                "portfolio-originality-mislabel",
                "approach_portfolio",
                refresh,
            )

        self.assertFalse(rejected.accepted)
        self.assertIn("duplicates a prior portfolio approach", " ".join(rejected.errors))

    def test_new_verified_root_evidence_forces_exclusive_portfolio_refresh(self) -> None:
        state = _pure_strategy_state(revision=30)
        state["research_artifacts"] = [
            {
                "artifact_id": "portfolio-old",
                "artifact_type": "approach_portfolio",
                "state_revision": 4,
                "metadata_json": _approach_portfolio_metadata(),
            },
            {
                "artifact_id": "proof-gap-three",
                "artifact_type": "proof_dossier",
                "state_revision": 24,
                "content_summary": "A verified example proves every universal constant is at least three.",
                "metadata_json": {},
            },
        ]
        state["claims"].append(
            {
                "claim_id": "claim-gap-three",
                "statement": "There is a maximal pair with derived-length gap three.",
                "validation_status": "informally_verified",
                "lifecycle_status": "integrated",
                "root_impact": 0.5,
                "parent_ids_json": '["root"]',
                "evidence_artifact_ids_json": '["proof-gap-three"]',
            }
        )

        evidence = approach_alignment_evidence(state, portfolio_revision=4)
        action = next_strategy_operation(
            state,
            {"mode": "retrieve", "target_id": "root", "route_id": "", "research_mode": "hard_problem"},
        )

        self.assertEqual([row["claim_id"] for row in evidence], ["claim-gap-three"])
        self.assertEqual(action["operation"], "approach_portfolio_refresh")
        self.assertTrue(action["exclusive_wave_required"])
        self.assertEqual(action["approach_candidate_minimum"], 6)
        self.assertEqual(
            action["approach_alignment"]["evidence_artifact_ids"],
            ["proof-gap-three"],
        )

    def test_processed_steering_forces_alignment_even_without_new_verified_claim(self) -> None:
        state = _pure_strategy_state()
        state["research_artifacts"] = [
            {
                "artifact_id": "portfolio-old",
                "artifact_type": "approach_portfolio",
                "state_revision": 4,
                "metadata_json": _approach_portfolio_metadata(),
            }
        ]
        action = next_strategy_operation(
            state,
            {"mode": "retrieve", "target_id": "root", "route_id": "", "research_mode": "hard_problem"},
            steering_alignment={
                "required": True,
                "source_steering_ids": ["steer-1"],
                "directives": [{"id": "steer-1", "text": "Reconsider the sharp bound."}],
            },
        )

        self.assertEqual(action["operation"], "approach_portfolio_refresh")
        self.assertEqual(action["approach_alignment"]["source_steering_ids"], ["steer-1"])
        self.assertTrue(action["exclusive_wave_required"])

    def test_pending_alignment_preempts_periodic_writing_after_failed_refresh(self) -> None:
        state = _pure_strategy_state(revision=30)
        state["research_artifacts"] = [
            {
                "artifact_id": "portfolio-old",
                "artifact_type": "approach_portfolio",
                "state_revision": 4,
                "metadata_json": _approach_portfolio_metadata(),
            }
        ]
        action = next_strategy_operation(
            state,
            {
                "mode": "write",
                "target_id": "root",
                "route_id": "",
                "research_mode": "hard_problem",
                "periodic_hmt": True,
                "search_intent": "periodic_human_readable_mathematical_text",
            },
            steering_alignment={
                "required": True,
                "source_steering_ids": ["steer-1"],
                "directives": [{"id": "steer-1", "text": "Refresh the root effects."}],
            },
        )

        self.assertEqual(action["operation"], "approach_portfolio_refresh")
        self.assertTrue(action["exclusive_wave_required"])
        self.assertEqual(action["approach_alignment"]["source_steering_ids"], ["steer-1"])

    def test_alignment_portfolio_requires_recomputed_root_effects_for_every_approach(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-aligned-portfolio-contract")
            initial = self._attach(
                store,
                "researcher",
                "portfolio-initial",
                "approach_portfolio",
                _approach_portfolio_metadata(),
            )
            self.assertTrue(initial.accepted, initial.errors)
            missing = _approach_portfolio_metadata(kind="refresh", supersedes="portfolio-initial")
            missing["alignment_source_steering_ids"] = ["steer-1"]
            missing["alignment_summary"] = "The sharp lower bound changed."
            missing["root_effect_recomputed"] = True
            rejected = self._attach(
                store,
                "researcher",
                "portfolio-refresh-missing-impact",
                "approach_portfolio",
                missing,
            )
            self.assertFalse(rejected.accepted)
            self.assertTrue(any("steering_impact" in error for error in rejected.errors))

            aligned = _approach_portfolio_metadata(kind="refresh", supersedes="portfolio-initial")
            aligned["alignment_source_steering_ids"] = ["steer-1"]
            aligned["alignment_evidence_artifact_ids"] = []
            aligned["alignment_summary"] = "Every route is recomputed after the new lower bound."
            aligned["root_effect_recomputed"] = True
            for candidate in aligned["approaches"]:
                candidate["steering_impact"] = "The route now targets a bound compatible with the new lower bound."
            accepted = self._attach(
                store,
                "researcher",
                "portfolio-refresh-aligned",
                "approach_portfolio",
                aligned,
            )

        self.assertTrue(accepted.accepted, accepted.errors)

    def test_brainstorming_manifest_keeps_ideas_questions_and_debts_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-approach-contract")
            action = enrich_action(
                store.get_scheduler_state(),
                {
                    "mode": "reduce",
                    "target_id": "root",
                    "research_mode": "hard_problem",
                    "approach_brainstorming_required": True,
                    "approach_portfolio_kind": "initial",
                    "approach_candidate_minimum": 6,
                },
            )
            manifest = build_context_manifest(store, action=action, max_chars=30_000)

        contract = manifest["approach_portfolio_contract"]
        self.assertEqual(contract["layer_policy"]["ideas"].split()[0], "live")
        self.assertIn("nonblocking", contract["layer_policy"]["research_questions"])
        self.assertIn("strict", contract["layer_policy"]["proof_obligations"])
        self.assertTrue(any("manifest.approach_portfolio_contract exactly" in line for line in manifest["instructions"]))

    def test_alignment_manifest_exposes_directives_evidence_and_per_approach_impact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-alignment-manifest")
            action = {
                "mode": "reduce",
                "target_id": "root",
                "approach_brainstorming_required": True,
                "approach_portfolio_kind": "refresh",
                "approach_candidate_minimum": 6,
                "supersedes_artifact_id": "portfolio-old",
                "approach_alignment": {
                    "required": True,
                    "source_steering_ids": ["steer-1"],
                    "directives": [{"id": "steer-1", "text": "Use the gap-three example."}],
                    "evidence_artifact_ids": ["proof-gap-three"],
                    "verified_root_developments": [{"claim_id": "claim-gap-three"}],
                },
            }
            manifest = build_context_manifest(store, action=action, max_chars=30_000)

        contract = manifest["approach_portfolio_contract"]
        self.assertEqual(contract["metadata_shape"]["alignment_source_steering_ids"], ["steer-1"])
        self.assertTrue(contract["metadata_shape"]["root_effect_recomputed"])
        self.assertIn("steering_impact", contract["metadata_shape"]["approaches"][0])
        self.assertIn("verified_root_developments", contract["steering_alignment"])

    def test_selected_approach_manifest_keeps_the_full_pilot_contract(self) -> None:
        selected = {
            "approach_id": "approach-deep-core",
            "title": "Deep-core metabelianity",
            "mechanism": "Prove the ambient deep derived core is metabelian.",
            "decisive_test": "Check the critical chief lift after crown localization.",
            "root_consequence": "This proves the universal upper bound three.",
            "steering_impact": "The verified gap-three example makes metabelianity the sharp target.",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-selected-approach-manifest")
            manifest = build_context_manifest(
                store,
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "search_intent": "approach_pilot:approach-deep-core",
                    "approach_pilot_required": True,
                    "selected_approach": selected,
                    "decisive_test_required": True,
                    "root_consequence_required": True,
                    "proof_claim_creation_forbidden_unless_test_succeeds": True,
                },
                max_chars=30_000,
            )

        card = manifest["workflow_action"]
        self.assertTrue(card["approach_pilot_required"])
        self.assertEqual(card["selected_approach"], selected)
        self.assertTrue(card["decisive_test_required"])
        self.assertTrue(card["root_consequence_required"])
        self.assertTrue(card["proof_claim_creation_forbidden_unless_test_succeeds"])

    def test_brainstorming_uses_a_short_dedicated_researcher_prompt(self) -> None:
        guidance = _base_mode_guidance(
            "reduce",
            "researcher",
            "",
            {"approach_brainstorming_required": True, "researcher_work_mode": "offline"},
        )

        self.assertLess(len(guidance), 5_000)
        self.assertIn("dedicated breadth-first mathematical brainstorming pass", guidance)
        self.assertIn("ideas live only in the advisory portfolio", guidance)
        self.assertIn("blocking proof debts arise only later", guidance)
        self.assertNotIn("closure_pipeline_required", guidance)

    def test_source_adaptation_digest_is_not_preempted_by_selected_bridge(self) -> None:
        state = _pure_strategy_state()
        state["research_artifacts"] = [
            {
                "artifact_id": "older-selected-bridge",
                "artifact_type": "bridge_lemma_search",
                "state_revision": 10,
                "metadata_json": _bridge_metadata(
                    _bridge_candidate("bridge-before-source", "An older selected bridge theorem.")
                ),
            }
        ]
        primary_action = {
            "mode": "reduce",
            "target_id": "root",
            "route_id": "",
            "source_adaptation_digest_required": True,
            "source_artifact_id": "fresh-source-adaptation",
        }

        self.assertIsNone(next_strategy_operation(state, primary_action))

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

    def test_bridge_root_leverage_gate_rejects_gap_renaming(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-bridge-root-leverage")
            candidate = _bridge_candidate("bridge-renamed", "The current gap in renamed notation.")
            candidate["root_leverage_gate"]["renames_current_gap"] = True
            outcome = self._attach(
                store,
                "researcher",
                "bridge-gap-renaming",
                "bridge_lemma_search",
                _bridge_metadata(candidate),
            )
        self.assertFalse(outcome.accepted)
        self.assertTrue(any("fails a guardrail" in error for error in outcome.errors))

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
        self.assertIn("scheduler_priority", action["priority_assessment"])
        self.assertFalse(action["priority_assessment"]["calibrated_probability"])

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
        self.assertEqual(set(candidate["root_leverage_gate"]), {
            "if_proved_major_case",
            "if_refuted_information_gain",
            "stronger_than_necessary",
            "renames_current_gap",
            "hypotheses_attainable",
        })
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
        self.assertIn("single_decisive_missing_theorem", skeleton)
        self.assertIn("most_informative_failed_ideas", skeleton)
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
                        "single_decisive_missing_theorem": "The bridge holds.",
                        "strongest_candidate_counterexample_architecture": "Search the smallest admissible endpoint.",
                        "most_informative_failed_ideas": ["Direct counting only renames the bridge gap."],
                    },
                },
            )

        self.assertTrue(accepted.accepted, accepted.errors)

    def test_proof_compression_keeps_at_most_three_active_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-compression-failure-cap")
            rejected = self._attach(
                store,
                "researcher",
                "compression-too-many-failures",
                "proof_compression",
                {
                    "strategy_schema_version": 1,
                    "history_preserved": True,
                    "minimal_proof_skeleton": {
                        "root": "root",
                        "essential_verified_facts": [],
                        "essential_routes": ["none_yet"],
                        "unresolved_bridges": ["The decisive bridge."],
                        "conditional_steps": ["The root follows from the bridge."],
                        "unused_or_low_value_branches": ["Background branch."],
                        "shortest_known_route": ["Prove the decisive bridge."],
                        "weakest_sufficient_new_statement": "The decisive bridge holds.",
                        "single_decisive_missing_theorem": "The decisive bridge holds.",
                        "strongest_candidate_counterexample_architecture": "Minimal bad endpoint.",
                        "most_informative_failed_ideas": ["one", "two", "three", "four"],
                    },
                },
            )
        self.assertFalse(rejected.accepted)
        self.assertTrue(any("at most three" in error for error in rejected.errors))

    def test_repeated_local_attacks_schedule_long_conceptual_invariant_session(self) -> None:
        state = _pure_strategy_state()
        state["research_artifacts"].append(
            {
                "artifact_id": "compression-before-concept",
                "artifact_type": "proof_compression",
                "state_revision": 6,
                "metadata_json": "{}",
            }
        )
        action = next_strategy_operation(state, {"mode": "reduce", "target_id": "root", "route_id": ""})
        self.assertEqual(action["operation"], "conceptual_invariant_discovery")
        self.assertTrue(action["long_mathematical_session_required"])
        self.assertTrue(action["analogy_pass_required"])

    def test_deep_session_conceptual_invariant_satisfies_freshness_watermark(self) -> None:
        state = _pure_strategy_state(revision=12)
        state["research_artifacts"].extend(
            [
                {
                    "artifact_id": "compression-before-deep-concept",
                    "artifact_type": "proof_compression",
                    "state_revision": 6,
                    "metadata_json": "{}",
                },
                {
                    "artifact_id": "deep-conceptual-invariant",
                    "artifact_type": "deep_session_report",
                    "state_revision": 11,
                    "metadata_json": {
                        "candidate_invariants": [
                            {
                                "invariant_id": "simple-projective-height",
                                "definition": "Maximum projective degree of a simple subgroup.",
                            }
                        ],
                        "selected_invariant_id": "simple-projective-height",
                    },
                },
            ]
        )

        trigger = conceptual_invariant_trigger(state)

        self.assertFalse(trigger["due"])
        self.assertEqual(trigger["reason"], "conceptual invariant pass is still fresh")

    def test_conceptual_invariant_contract_requires_compression_and_falsification(self) -> None:
        metadata = {
            "strategy_schema_version": 1,
            "candidate_invariants": [
                {
                    "invariant_id": "inv-kernel",
                    "definition": "The common kernel of the induced chief-factor actions.",
                    "transformations_controlled": ["quotients", "restriction"],
                    "local_lemmas_subsumed": ["claim-a", "claim-b"],
                    "root_consequence": "Both local kernel lemmas become one functorial statement.",
                    "falsification_example": "A split extension with distinct action kernels.",
                    "failure_modes": ["kernel is not functorial under the required quotient"],
                    "status": "selected",
                }
            ],
            "selected_invariant_id": "inv-kernel",
            "neighboring_theorem_comparison": "The neighboring theorem controls the same action after quotienting.",
            "object_dictionary": {"local kernel": "neighboring theorem stabilizer"},
            "next_decisive_test": "Check functoriality on the smallest split extension.",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "strategy-conceptual-invariant")
            accepted = self._attach(
                store,
                "researcher",
                "conceptual-invariant-valid",
                "conceptual_invariant_report",
                metadata,
            )
            manifest = build_context_manifest(
                store,
                max_chars=30_000,
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "conceptual_invariant_discovery_required": True,
                },
            )
        self.assertTrue(accepted.accepted, accepted.errors)
        self.assertEqual(manifest["conceptual_invariant_contract"]["candidate_count"], "one to three")

    def test_compact_conceptual_contract_exposes_metadata_version_and_status_enum(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir, "compact-conceptual-contract")
            manifest = build_context_manifest(
                store,
                max_chars=12_000,
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "conceptual_invariant_discovery_required": True,
                },
            )
        contract = manifest["conceptual_invariant_contract"]
        self.assertEqual(1, contract.get("strategy_schema_version"))
        self.assertIn("strategy_schema_version", contract["required_fields"])
        self.assertEqual(
            {"selected", "viable", "rejected", "refuted"},
            set(contract["candidate_status_values"]),
        )
        self.assertIn("attach_artifact.metadata", contract["metadata_rule"])
        self.assertNotIn("complete_local_proof_candidate", contract["candidate_status_values"])
        self.assertEqual(
            {"type": "list", "min_items": 2, "applies_to": "every candidate, including rejected and refuted"},
            contract.get("local_lemmas_subsumed_constraint"),
        )
        self.assertIn("Do not invent", contract["ineligible_candidate_rule"])
        self.assertIn("research_diagnostic", contract["ineligible_candidate_rule"])

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
                {"experiment_workflow_version": 2, "observations": ["42"]},
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
                action["priority_assessment"]["refutation_priority"],
                action["priority_assessment"]["verification_cost_level"],
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
        self.assertTrue(deep["long_mathematical_session_required"])
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
            "independent_proof_attacks": ["Direct reduction.", "Minimal-counterexample induction."],
            "candidate_lemmas": ["The reduction lemma."],
            "failed_approaches": ["The direct counting bound was too weak."],
            "new_obstructions": ["One exact family bound remains."],
            "source_adaptations": [],
            "analogy_or_neighboring_theorem_comparison": "The neighboring theorem uses the same quotient but a stronger kernel hypothesis.",
            "full_proof_assembly_attempt": "Insert the reduction lemma after the verified core; only the family bound remains.",
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

    def test_priority_assessment_penalizes_duplicate_actions(self) -> None:
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
        self.assertGreater(duplicate["duplicate_recent_attempts"], baseline["duplicate_recent_attempts"])
        self.assertLess(duplicate["scheduler_priority"], baseline["scheduler_priority"])


if __name__ == "__main__":
    unittest.main()
