from __future__ import annotations

import tempfile
from pathlib import Path

from agents.generation.phase2.certified_memory import certified_cross_run_candidates
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.research_intelligence import (
    mathematical_interface_contract,
    theorem_adaptation_contract,
    validate_proof_interface_metadata,
    validate_source_technique_metadata,
)
from agents.generation.phase2.research_strategy import (
    canonical_route_ownership,
    enrich_action,
    root_cut_progress_gate,
)
from agents.generation.phase2.store import ProofStateStore


def test_typed_interface_tracks_quantifier_order_and_permutation_action() -> None:
    state = {
        "problem_state": {
            "root_statement": (
                "Let G be a finite primitive permutation group. For all alpha and beta "
                "there exists gamma with both 2-point stabilisers trivial."
            )
        },
        "claims": [
            {
                "claim_id": "root",
                "statement": (
                    "Let G be a finite primitive permutation group. For all alpha and beta "
                    "there exists gamma with both 2-point stabilisers trivial."
                ),
            }
        ],
        "inferences": [],
    }
    contract = mathematical_interface_contract(state, {"mode": "integrate", "target_id": "root"})
    interface = contract["target_interface"]
    assert "permutation_group" in interface["object_types"]
    assert "permutation" in interface["action_types"]
    assert interface["finiteness_scope"] == "finite"
    assert interface["quantifier_scope"]["order_must_be_preserved"] is True
    assert "mixed_quantifier_order" in contract["risk_flags"]


def test_v2_zero_gap_interface_rejects_unresolved_type_mismatch() -> None:
    metadata = {
        "proof_interface_check_version": 2,
        "verdict": "verified",
        "quantifiers_preserved": True,
        "hypotheses_matched": True,
        "cases_exhaustive": True,
        "reduction_direction_valid": True,
        "finite_scope_not_overclaimed": True,
        "dependencies_assemble": True,
        "mathematical_interface_version": 1,
        "interface_checks": ["linear versus semilinear action checked"],
        "unresolved_interface_mismatches": ["semilinear descent is not justified"],
    }
    errors = validate_proof_interface_metadata(metadata)
    assert any("cannot retain unresolved_interface_mismatches" in error for error in errors)
    metadata["unresolved_interface_mismatches"] = []
    assert validate_proof_interface_metadata(metadata) == []


def test_source_technique_compiler_is_stricter_than_theorem_summary() -> None:
    contract = theorem_adaptation_contract({"mode": "synthesize_sources"})
    assert contract["source_technique_compiler"]["proof_skeleton_not_summary_required"] is True
    errors = validate_source_technique_metadata(
        {
            "source_technique_compiler_version": 1,
            "source_proof_skeleton": ["minimal counterexample", "quotient reduction"],
        }
    )
    assert any("hypothesis_necessity" in error for error in errors)


def test_cross_run_memory_nominates_but_does_not_import_exact_certified_root() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        generation_root = Path(tmpdir) / "generation"
        source = ProofStateStore("source/problem", generation_root=generation_root)
        target = ProofStateStore("target/problem", generation_root=generation_root)
        statement = "Every finite primitive group in this class has the common-neighbour property."
        source.init_problem(statement)
        target.init_problem(statement)
        with source.connect() as conn:
            conn.execute(
                "UPDATE claims SET validation_status='informally_verified', lifecycle_status='integrated' WHERE claim_id='root'"
            )
            conn.commit()
        card = certified_cross_run_candidates(target)
        assert card["automatic_import"] is False
        assert card["verification_authority"] is False
        assert card["candidates"][0]["source_problem_id"] == "source/problem"
        assert card["candidates"][0]["exact_statement_fingerprint"] is True
        assert card["candidates"][0]["explicit_scope_import_required"] is True


def test_root_cut_gate_freezes_claim_growth_after_unassembled_verified_lemmas() -> None:
    claims = [
        {
            "claim_id": "root",
            "statement": "Target theorem.",
            "validation_status": "untested",
            "lifecycle_status": "active",
            "root_impact": 1.0,
        }
    ] + [
        {
            "claim_id": f"lemma-{index}",
            "statement": f"Verified lemma {index}.",
            "validation_status": "informally_verified",
            "lifecycle_status": "active",
            "root_impact": 0.8,
        }
        for index in range(3)
    ]
    state = {
        "problem_state": {"current_revision": 8, "root_statement": "Target theorem."},
        "claims": claims,
        "routes": [
            {
                "route_id": "route-root",
                "conclusion_claim_id": "root",
                "status": "active",
                "relation_to_parent": "sufficient",
            }
        ],
        "inferences": [
            {
                "inference_id": "inf-root",
                "route_id": "route-root",
                "conclusion_claim_id": "root",
                "premise_claim_ids": [],
                "validation_status": "untested",
                "explanation": "assemble the route",
            }
        ],
        "debts": [],
        "recent_runs": [],
        "research_artifacts": [],
    }
    gate = root_cut_progress_gate(state)
    assert gate["active"] is True
    assert gate["claim_creation_frozen"] is True
    assert gate["cut_signature"] == ["inference:inf-root"]


def test_root_cut_gate_does_not_deadlock_route_less_unverified_research() -> None:
    state = {
        "problem_state": {"current_revision": 12, "root_statement": "Target theorem."},
        "claims": [
            {
                "claim_id": "root",
                "statement": "Target theorem.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 1.0,
            },
            *[
                {
                    "claim_id": f"lemma-{index}",
                    "statement": f"Unverified lemma {index}.",
                    "validation_status": "untested",
                    "lifecycle_status": "active",
                    "root_impact": 0.5,
                }
                for index in range(4)
            ],
        ],
        "routes": [],
        "inferences": [],
        "debts": [
            {
                "debt_id": "debt-root-gap",
                "owner_id": "root",
                "suggested_next_target": "root",
                "status": "active",
                "severity": "blocking",
                "obligation": "Find a route-level bridge.",
            }
        ],
        "recent_runs": [
            {
                "actor_role": "researcher",
                "status": "completed",
                "target_id": "root",
            }
            for _ in range(5)
        ],
        "research_artifacts": [],
    }

    gate = root_cut_progress_gate(state)

    assert gate["active"] is False
    assert gate["claim_creation_frozen"] is False
    assert gate["has_consolidatable_material"] is False
    assert gate["activation_blocker"] == "no_route_inference_or_verified_claim_to_consolidate"
    action = enrich_action(state, {"mode": "prove", "target_id": "root", "route_id": ""})
    assert action["root_cut_progress_gate"]["active"] is False
    assert "claim_creation_frozen" not in action


def test_root_cut_research_streak_freezes_an_existing_route_frontier() -> None:
    state = {
        "problem_state": {"current_revision": 12, "root_statement": "Target theorem."},
        "claims": [
            {
                "claim_id": "root",
                "statement": "Target theorem.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 1.0,
            }
        ],
        "routes": [
            {
                "route_id": "route-root",
                "conclusion_claim_id": "root",
                "status": "active",
                "relation_to_parent": "sufficient",
            }
        ],
        "inferences": [
            {
                "inference_id": "inf-root",
                "route_id": "route-root",
                "conclusion_claim_id": "root",
                "premise_claim_ids": [],
                "validation_status": "untested",
                "explanation": "Complete the root inference.",
            }
        ],
        "debts": [],
        "recent_runs": [
            {"actor_role": "researcher", "status": "completed", "target_id": "root"}
            for _ in range(3)
        ],
        "research_artifacts": [],
    }

    gate = root_cut_progress_gate(state)

    assert gate["active"] is True
    assert gate["claim_creation_frozen"] is True
    assert gate["has_consolidatable_material"] is True
    assert gate["selected_route_id"] == "route-root"


def test_enrichment_keeps_scheduler_selected_debt_as_decisive_obligation() -> None:
    state = {
        "problem_state": {"current_revision": 12, "root_statement": "Target theorem."},
        "claims": [
            {
                "claim_id": "root",
                "statement": "Target theorem.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 1.0,
            },
            *[
                {
                    "claim_id": f"verified-lemma-{index}",
                    "statement": f"Verified lemma {index}.",
                    "validation_status": "informally_verified",
                    "lifecycle_status": "integrated",
                    "root_impact": 0.8,
                }
                for index in range(3)
            ],
        ],
        "routes": [],
        "inferences": [],
        "debts": [
            {
                "debt_id": "debt-a-stale-global-first",
                "owner_id": "root",
                "suggested_next_target": "root",
                "status": "active",
                "severity": "blocking",
                "obligation": "Close the older broad obstruction that sorts first globally.",
            },
            {
                "debt_id": "debt-z-selected-narrow-child",
                "owner_id": "root",
                "suggested_next_target": "root",
                "status": "active",
                "severity": "blocking",
                "obligation": "Prove the newly selected narrow child obstruction.",
            },
        ],
        "recent_runs": [
            {"actor_role": "researcher", "status": "completed", "target_id": "root"}
            for _ in range(3)
        ],
        "research_artifacts": [],
    }
    assert root_cut_progress_gate(state)["decisive_obligation"]["obligation_id"] == (
        "debt-a-stale-global-first"
    )

    action = enrich_action(
        state,
        {
            "mode": "prove",
            "target_id": "root",
            "route_id": "",
            "debt_id": "debt-z-selected-narrow-child",
            "bottleneck_lock_required": True,
            "bottleneck_lock_signal": {"debt_id": "debt-z-selected-narrow-child"},
        },
    )

    assert action["root_cut_progress_gate"]["action_selected_debt_aligned"] is True
    assert action["root_cut_progress_gate"]["decisive_obligation"]["obligation_id"] == (
        "debt-z-selected-narrow-child"
    )
    assert action["decisive_obligation_id"] == "debt-z-selected-narrow-child"
    assert "debt-z-selected-narrow-child" in action["reason"]


def test_root_cut_inference_debt_targets_its_conclusion_claim() -> None:
    state = {
        "problem_state": {"current_revision": 12, "root_statement": "Target theorem."},
        "claims": [
            {
                "claim_id": "root",
                "statement": "Target theorem.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 1.0,
            },
            {
                "claim_id": "local-lemma",
                "statement": "Local lemma.",
                "validation_status": "challenged",
                "lifecycle_status": "active",
                "root_impact": 0.8,
            },
        ],
        "routes": [
            {
                "route_id": "route-local",
                "conclusion_claim_id": "local-lemma",
                "status": "active",
                "relation_to_parent": "sufficient",
            }
        ],
        "inferences": [
            {
                "inference_id": "inf-local",
                "route_id": "route-local",
                "conclusion_claim_id": "local-lemma",
                "premise_claim_ids": [],
                "validation_status": "untested",
                "explanation": "Complete the local inference.",
            }
        ],
        "debts": [
            {
                "debt_id": "debt-inf-interface",
                "owner_type": "inference",
                "owner_id": "inf-local",
                "suggested_next_target": "inf-local",
                "status": "active",
                "severity": "blocking",
                "obligation": "Repair the inference interface.",
            }
        ],
        "recent_runs": [
            {"actor_role": "researcher", "status": "completed", "target_id": "local-lemma"}
            for _ in range(3)
        ],
        "research_artifacts": [],
    }

    action = enrich_action(
        state,
        {"mode": "reduce", "target_id": "root", "route_id": "route-local"},
    )

    assert action["root_cut_consolidation_required"] is True
    assert action["target_id"] == "local-lemma"
    assert action["route_id"] == "route-local"
    assert action["decisive_obligation_target_id"] == "inf-local"


def test_fresh_refutation_action_is_stamped_as_counterexample_preflight() -> None:
    state = {
        "problem_state": {"current_revision": 0, "root_statement": "Target theorem."},
        "claims": [
            {
                "claim_id": "root",
                "statement": "Target theorem.",
                "validation_status": "untested",
                "lifecycle_status": "active",
                "root_impact": 1.0,
            }
        ],
        "routes": [],
        "inferences": [],
        "debts": [],
        "recent_runs": [],
        "research_artifacts": [],
    }
    action = enrich_action(state, {"mode": "refute", "target_id": "root", "route_id": ""})
    assert action["initial_counterexample_preflight_required"] is True
    assert action["counterexample_preflight_contract"]["no_counterexample_is_not_a_proof"] is True


def test_unrouted_canonical_dossier_requires_continuity_not_route_ownership() -> None:
    state = {
        "problem_state": {"current_revision": 2, "root_statement": "Target theorem."},
        "claims": [{"claim_id": "root", "statement": "Target theorem."}],
        "routes": [],
        "inferences": [],
        "debts": [],
        "recent_runs": [],
        "research_artifacts": [
            {
                "artifact_id": "dossier-root-v1",
                "artifact_type": "proof_dossier",
                "state_revision": 2,
                "metadata_json": '{"target_id":"root"}',
            }
        ],
    }
    owner = canonical_route_ownership(state, {"mode": "prove", "target_id": "root"})
    assert owner["canonical_artifact_id"] == "dossier-root-v1"
    assert owner["route_id"] == ""
    assert owner["ownership_required"] is False
    assert owner["continuity_required"] is True
    assert owner["supersede_or_update_required"] is True
    assert owner["parallel_dossier_creation_forbidden"] is True
    assert "supersedes_artifact_id" in owner["required_metadata_fields"]
    assert "canonical_route_id" not in owner["required_metadata_fields"]


def test_named_route_requires_canonical_route_owner_metadata() -> None:
    state = {
        "problem_state": {"current_revision": 2, "root_statement": "Target theorem."},
        "claims": [{"claim_id": "root", "statement": "Target theorem."}],
        "routes": [],
        "inferences": [],
        "debts": [],
        "recent_runs": [],
        "research_artifacts": [],
    }
    owner = canonical_route_ownership(
        state,
        {"mode": "prove", "target_id": "root", "route_id": "route-root"},
    )
    assert owner["route_id"] == "route-root"
    assert owner["ownership_required"] is True
    assert owner["continuity_required"] is False
    assert "canonical_route_id" in owner["required_metadata_fields"]


def test_route_less_context_does_not_demand_a_canonical_route_id() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ProofStateStore(
            "route-less-canonical-context-test",
            generation_root=Path(tmpdir) / "generation",
        )
        store.init_problem("Prove the target theorem.")
        manifest = build_context_manifest(
            store,
            action={
                "mode": "prove",
                "target_id": "root",
                "canonical_route_ownership": {
                    "route_id": "",
                    "canonical_artifact_id": "dossier-root-v1",
                    "ownership_required": False,
                    "continuity_required": True,
                },
            },
            max_chars=40_000,
        )

    instructions = "\n".join(manifest["instructions"])
    assert "Continue the existing route-less canonical proof draft" in instructions
    assert "Do not set canonical_route_owner_version or canonical_route_id" in instructions
    assert "selected nonempty route has one canonical proof draft" not in instructions
    assert "creates_parallel_proof_draft=false" in instructions
