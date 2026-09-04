from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Dict, Mapping

from .graph_policy import (
    VERIFIED_VALIDATION_STATUSES,
    build_graph_policy_index,
    claim_is_unresolved,
    debt_covered_by_integrated_claim,
    get_debt_coverage_index,
    paused_route_ids,
    root_distance_for_claim_id,
)
from .models import json_loads, normalize_text


OUTCOME_LEARNING_VERSION = 4
OBLIGATION_FRONTIER_VERSION = 2
DEEP_SESSION_ROI_VERSION = 1
REPRESENTATION_SWITCH_VERSION = 1
THEOREM_ADAPTATION_VERSION = 1
PROOF_INTERFACE_CHECK_VERSION = 2
THEOREM_PREFLIGHT_VERSION = 1
MATHEMATICAL_INTERFACE_VERSION = 1
SOURCE_TECHNIQUE_COMPILER_VERSION = 1

PRODUCTIVE_DELTA_KINDS = {
    "verifier_ready_proof",
    "proved_lemma",
    "refuted_conjecture",
    "verified_source_adaptation",
    "narrowed_obligation",
    "route_killing_obstruction",
    "decisive_counterexample",
}

PROOF_INTERFACE_FIELDS = (
    "quantifiers_preserved",
    "hypotheses_matched",
    "cases_exhaustive",
    "reduction_direction_valid",
    "finite_scope_not_overclaimed",
    "dependencies_assemble",
)

THEOREM_ADAPTATION_FIELDS = (
    "source_location",
    "exact_source_statement",
    "local_statement_translation",
    "definition_dictionary",
    "hypothesis_dictionary",
    "checked_hypotheses",
    "missing_hypotheses",
    "local_deduction",
    "reusable_proof_moves",
    "failure_boundary",
)

SOURCE_TECHNIQUE_FIELDS = (
    "source_proof_skeleton",
    "key_constructions",
    "reusable_proof_moves",
    "hypothesis_necessity",
    "failure_examples",
    "local_translation_steps",
    "next_local_deduction",
)

MATHEMATICAL_INTERFACE_FIELDS = (
    "object_types",
    "ambient_categories",
    "base_fields_or_rings",
    "action_types",
    "finiteness_scope",
    "quantifier_scope",
    "subobject_quotient_scope",
    "normalization_conventions",
    "parameter_ranges",
)

REPRESENTATION_SWITCH_FIELDS = (
    "representations_considered",
    "translation_dictionary",
    "equivalence_or_implication_checks",
    "relation_to_original",
    "preserved_quantities",
    "loss_or_error_terms",
    "application_back_to_original",
    "interface_status",
    "chosen_representation",
    "choice_reason",
    "next_test_in_chosen_representation",
)

_UNIVERSAL_CUES = (
    "for every",
    "for all",
    "every ",
    "all ",
    "any ",
    "each ",
    "if and only if",
    "exactly when",
)
_REPRESENTATION_RISK_CUES = (
    "normalization",
    "normalize",
    "saturation",
    "saturated",
    "rees",
    "associated graded",
    "specialization",
    "degeneration",
    "retraction",
    "transport",
    "filtration",
    "identify with",
    "equivalent to",
)
_BOUNDARY_CUES = (
    "rank",
    "dimension",
    "degree",
    "weight",
    "codimension",
    "index",
    "nonnegative",
    "positive",
    "equality",
)
_CLASSIFICATION_SCOPE_CUES = (
    "classify",
    "classification",
    "describe the",
    "determine all",
    "find all",
    "which objects",
)
_EXAMPLE_FAMILY_CUES = (
    "for example",
    "examples include",
    "is known to",
    "are known to",
    "known examples",
)

_DOMAIN_CUES: Dict[str, tuple[str, ...]] = {
    "group_theory": (
        "group",
        "subgroup",
        "normal subgroup",
        "chief factor",
        "sylow",
        "solvable",
        "soluble",
        "conjugacy",
        "invariably generated",
    ),
    "representation_theory": (
        "character",
        "module",
        "representation",
        "restriction",
        "induction",
        "irreducible",
    ),
    "linear_algebra": ("vector space", "matrix", "linear map", "rank", "eigenvalue", "bilinear form"),
    "cohomology": ("cohomology", "cocycle", "extension class", "obstruction class", "torsor"),
    "number_theory": ("prime", "integer", "divisibility", "galois", "number field", "local field"),
    "combinatorics": (
        "graph",
        "hypergraph",
        "coloring",
        "perfect matching",
        "matching number",
        "set system",
        "extremal",
    ),
    "algebraic_geometry": (
        "scheme",
        "variety",
        "fiber",
        "flat",
        "dimension",
        "specialization",
        "hypersurface",
        "fano",
        "k stability",
        "k stable",
        "cubic fivefold",
    ),
    "commutative_algebra": ("ring", "ideal", "module", "noetherian", "localization", "hilbert"),
    "topology": ("topological", "homotopy", "homology", "covering space", "fundamental group"),
    "analysis": ("measure", "integral", "continuous", "compact", "norm", "operator"),
    "probability": ("random", "probability", "expectation", "martingale", "concentration"),
}

_REPRESENTATIONS_BY_DOMAIN: Dict[str, tuple[str, ...]] = {
    "group_theory": (
        "subgroup and quotient structure",
        "permutation action",
        "module or chief-factor action",
        "character or conjugacy-class data",
        "extension or cohomology data",
    ),
    "representation_theory": (
        "module structure",
        "character identities",
        "endomorphism algebra",
        "orbit or geometric action",
    ),
    "combinatorics": (
        "incidence structure",
        "linear-algebraic encoding",
        "probabilistic model",
        "generating function",
    ),
    "algebraic_geometry": (
        "geometric fibers",
        "coordinate or local algebra",
        "deformation family",
        "cohomological obstruction",
    ),
    "number_theory": (
        "local-global data",
        "Galois representation",
        "ideal or valuation data",
        "analytic generating series",
    ),
}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    decoded = json_loads(value, []) if isinstance(value, str) else []
    return list(decoded) if isinstance(decoded, list) else []


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    decoded = json_loads(value, {}) if isinstance(value, str) else {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def infer_domain_tags(text: str) -> list[str]:
    normalized = normalize_text(text)
    padded = f" {normalized} "
    return sorted(
        domain
        for domain, cues in _DOMAIN_CUES.items()
        if any(f" {normalize_text(cue)} " in padded for cue in cues)
    )


def strategy_family(row: Mapping[str, Any]) -> str:
    recorded = str(row.get("strategy_family") or "").strip()
    if recorded:
        return recorded
    philosophy = str(row.get("research_philosophy") or "").strip()
    explicit_family = {
        "main_spine_construction": "global_assembly",
        "global_approach_generation": "approach_portfolio",
        "global_assembly": "global_assembly",
        "local_support_lemma": "bridge_lemma",
        "external_theorem_adaptation": "theorem_adaptation",
        "adversarial_probe": "adversarial_probe",
        "conceptual_invariant": "conceptual_invariant",
        "conceptual_invariant_discovery": "conceptual_invariant",
        "alternative_construction": "alternative_construction",
        "representation_switch": "representation_switch",
        "direct_proof": "direct_proof",
    }.get(philosophy)
    if explicit_family:
        return explicit_family
    # Only exact structured fields are used.  Free-text search intents are not
    # classification data and must never silently move outcome statistics.
    work_mode = str(row.get("researcher_work_mode") or "").strip()
    mode = str(row.get("mode") or "").strip()
    if work_mode == "cas":
        return "experimental_mathematics"
    return {
        "refute": "adversarial_probe",
        "validate_counterexample": "adversarial_validation",
        "retrieve": "theorem_adaptation",
        "synthesize_sources": "theorem_adaptation",
        "audit_definitions": "definition_audit",
        "integrate": "global_assembly",
        "formalize": "formal_verification",
        "prove": "direct_proof",
    }.get(mode, "unclassified")


def _artifact_rows(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for key in ("research_artifacts", "audit_artifacts", "artifacts", "confirmed_counterexamples"):
        for row in state.get(key, []) or []:
            if not isinstance(row, Mapping):
                continue
            artifact_id = str(row.get("artifact_id") or "")
            if artifact_id and artifact_id in seen:
                continue
            if artifact_id:
                seen.add(artifact_id)
            rows.append(row)
    return rows


def _artifact_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    return _json_object(row.get("metadata_json", row.get("metadata", {})))


def _advisor_root_cut_policy(state: Mapping[str, Any]) -> tuple[list[str], set[str]]:
    """Return the newest explicit advisor cut order and its retired debts.

    Advisor reports may retain obsolete obstruction debts for provenance.  A
    report that supplies both root-cut signatures is an explicit scheduling
    decision, so debts removed from the successor cut must not reappear merely
    because their durable graph rows remain active.
    """

    reports = [
        row
        for row in _artifact_rows(state)
        if str(row.get("artifact_type") or "") in {"advisor_report", "advisor_synthesis"}
        and str(row.get("producer_role") or "") == "phd_advisor"
    ]
    reports.sort(
        key=lambda row: (
            int(row.get("state_revision") or 0),
            str(row.get("created_at") or ""),
            str(row.get("artifact_id") or ""),
        ),
        reverse=True,
    )
    for report in reports:
        metadata = _artifact_metadata(report)
        if "root_cut_signature_before" not in metadata or "root_cut_signature_after" not in metadata:
            continue

        def debt_ids(values: Any) -> list[str]:
            ids: list[str] = []
            for item in _json_list(values):
                value = str(item or "").strip()
                if value.startswith("debt:"):
                    value = value.removeprefix("debt:")
                if value and value not in ids:
                    ids.append(value)
            return ids

        before = debt_ids(metadata.get("root_cut_signature_before"))
        after = debt_ids(metadata.get("root_cut_signature_after"))
        if before:
            return after, set(before) - set(after)
    return [], set()


def _verified_evidence_ids(state: Mapping[str, Any]) -> set[str]:
    evidence: set[str] = set()
    for claim in state.get("claims", []) or []:
        if (
            str(claim.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES
            or str(claim.get("lifecycle_status") or "") == "integrated"
        ):
            evidence.update(str(item) for item in _json_list(claim.get("evidence_artifact_ids_json")) if str(item))
    for inference in state.get("inferences", []) or []:
        if str(inference.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES:
            evidence.update(str(item) for item in _json_list(inference.get("evidence_artifact_ids_json")) if str(item))
    for route in state.get("routes", []) or []:
        if str(route.get("status") or "") == "integrated":
            evidence.update(str(item) for item in _json_list(route.get("evidence_artifact_ids_json")) if str(item))
    return evidence


def _explicit_certificate_sources(
    state: Mapping[str, Any], certificate_ids: set[str]
) -> set[str]:
    """Return exact artifact provenance named by current host certificates."""

    artifacts = {
        str(row.get("artifact_id") or ""): row
        for row in _artifact_rows(state)
        if str(row.get("artifact_id") or "")
    }
    source_ids: set[str] = set()
    pending = list(sorted(certificate_ids))
    visited: set[str] = set()
    while pending:
        artifact_id = pending.pop()
        if artifact_id in visited:
            continue
        visited.add(artifact_id)
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            continue
        metadata = _artifact_metadata(artifact)
        bindings = metadata.get("host_certificate_bindings")
        if not isinstance(bindings, Mapping) or not bindings:
            continue
        direct_sources: set[str] = set()
        for item in _json_list(metadata.get("source_artifact_ids")):
            if str(item):
                direct_sources.add(str(item))
        for key in (
            "audit_subject_artifact_id",
            "candidate_artifact_id",
            "strict_report_artifact_id",
        ):
            if str(metadata.get(key) or ""):
                direct_sources.add(str(metadata[key]))
        source_ids.update(direct_sources)
        # Follow a certificate-to-certificate chain (for example integration
        # report -> strict report -> audited proof), but only while every hop
        # is an explicit identifier and the next artifact is host-bound.
        pending.extend(sorted(direct_sources - visited))
    return source_ids


def verifier_filtered_outcome_learning(
    state: Mapping[str, Any], action: Mapping[str, Any] | None = None
) -> Dict[str, Any]:
    """Compute verifier-filtered *descriptive* strategy yields.

    A run is counted as accepted only when an artifact produced by that run is
    current verified evidence, or is explicitly named as the source of a
    current host-bound certificate. Merely sharing a target or route with a
    later successful run is intentionally insufficient. Scheduler assignment
    is ordinarily adaptive rather than randomized, so these observations are
    not causal estimates and have no effect on action ranking.
    """

    verified_evidence = _verified_evidence_ids(state)
    accepted_evidence = verified_evidence | _explicit_certificate_sources(state, verified_evidence)
    routes_by_id = {
        str(row.get("route_id") or ""): row
        for row in state.get("routes", []) or []
        if str(row.get("route_id") or "")
    }
    root_route_ids = {
        route_id
        for route_id, row in routes_by_id.items()
        if str(row.get("conclusion_claim_id") or "") == "root"
        and str(row.get("relation_to_parent") or "sufficient") == "sufficient"
        and str(row.get("status") or "active") not in {"abandoned", "superseded"}
    }
    root_dependency_claim_ids: set[str] = set()
    root_evidence_ids: set[str] = set()
    for inference in state.get("inferences", []) or []:
        if str(inference.get("route_id") or "") not in root_route_ids:
            continue
        root_dependency_claim_ids.update(
            str(item)
            for item in _json_list(inference.get("premise_claim_ids") or inference.get("premise_claim_ids_json"))
            if str(item)
        )
        root_dependency_claim_ids.update(
            str(item)
            for item in _json_list(inference.get("condition_claim_ids") or inference.get("condition_claim_ids_json"))
            if str(item)
        )
        if str(inference.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES:
            root_evidence_ids.update(
                str(item)
                for item in _json_list(inference.get("evidence_artifact_ids_json") or inference.get("evidence_artifact_ids"))
                if str(item)
            )
    for claim in state.get("claims", []) or []:
        claim_id = str(claim.get("claim_id") or "")
        if claim_id not in root_dependency_claim_ids:
            continue
        if (
            str(claim.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES
            or str(claim.get("lifecycle_status") or "") == "integrated"
        ):
            root_evidence_ids.update(
                str(item)
                for item in _json_list(claim.get("evidence_artifact_ids_json") or claim.get("evidence_artifact_ids"))
                if str(item)
            )
    for route_id in root_route_ids:
        route = routes_by_id[route_id]
        if str(route.get("status") or "") == "integrated":
            root_evidence_ids.update(
                str(item)
                for item in _json_list(route.get("evidence_artifact_ids_json") or route.get("evidence_artifact_ids"))
                if str(item)
            )
    root_accepted_evidence = root_evidence_ids | _explicit_certificate_sources(state, root_evidence_ids)
    grouped: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "trials": 0.0,
            "accepted_successes": 0.0,
            "root_contributing_successes": 0.0,
            "execution_failures": 0.0,
            "tokens": 0.0,
            "observational_trials": 0.0,
            "deterministic_trials": 0.0,
            "randomized_trials": 0.0,
        }
    )
    for run in (state.get("outcome_runs") or state.get("recent_runs") or []):
        role = str(run.get("actor_role") or "")
        if role not in {"researcher", "adversarial_reviewer", "villain", "literature_researcher"}:
            continue
        family = strategy_family(run)
        stats = grouped[family]
        stats["trials"] += 1
        stats["tokens"] += float(run.get("total_tokens") or 0.0)
        design = str(run.get("selection_design") or "observational")
        if design == "randomized":
            stats["randomized_trials"] += 1
        elif design == "deterministic":
            stats["deterministic_trials"] += 1
            stats["observational_trials"] += 1
        else:
            stats["observational_trials"] += 1
        status = str(run.get("status") or "").lower()
        if status in {"patch_rejected", "timeout", "no_patch", "failed", "error", "cancelled"}:
            stats["execution_failures"] += 1
        output_ids = {str(item) for item in _json_list(run.get("output_artifact_ids_json")) if str(item)}
        if output_ids & accepted_evidence:
            stats["accepted_successes"] += 1
        if output_ids & root_accepted_evidence:
            stats["root_contributing_successes"] += 1

    families: Dict[str, Dict[str, Any]] = {}
    for family, raw in sorted(grouped.items()):
        trials = int(raw["trials"])
        successes = int(raw["accepted_successes"])
        root_successes = int(raw["root_contributing_successes"])
        accepted_rate = successes / trials if trials else 0.0
        root_rate = root_successes / trials if trials else 0.0
        # Laplace smoothing prevents a single early run from dominating. This
        # is a fixed heuristic transformation, not a Bayesian posterior claim.
        smoothed_accepted_rate = (successes + 1.0) / (trials + 2.0)
        smoothed_root_rate = (root_successes + 1.0) / (trials + 2.0)
        sample_weight = min(1.0, trials / 8.0)
        blended_rate = 0.25 * smoothed_accepted_rate + 0.75 * smoothed_root_rate
        # Even rows labelled randomized are not used here: a valid causal
        # comparison additionally needs a preregistered candidate set,
        # contemporaneous controls, and a fixed outcome horizon. The current
        # harness does not yet run that protocol. Fail closed instead of
        # laundering adaptive historical choices into a ranking signal.
        adjustment = 0.0
        families[family] = {
            "trials": trials,
            "observational_trials": int(raw["observational_trials"]),
            "deterministic_trials": int(raw["deterministic_trials"]),
            "randomized_trials": int(raw["randomized_trials"]),
            "accepted_successes": successes,
            "root_contributing_successes": root_successes,
            "execution_failures": int(raw["execution_failures"]),
            "observed_accepted_rate": round(accepted_rate, 4),
            "observed_root_contribution_rate": round(root_rate, 4),
            "laplace_smoothed_accepted_rate": round(smoothed_accepted_rate, 4),
            "laplace_smoothed_root_rate": round(smoothed_root_rate, 4),
            "root_weighted_heuristic_rate": round(blended_rate, 4),
            "sample_weight": round(sample_weight, 3),
            "heuristic_score_adjustment": round(adjustment, 4),
            "ranking_effect": "disabled",
            "causal_eligible": False,
            "average_tokens": round(raw["tokens"] / max(1, trials)),
        }

    current_family = strategy_family(action or {}) if action is not None else ""
    current = families.get(
        current_family,
        {
            "trials": 0,
            "observational_trials": 0,
            "deterministic_trials": 0,
            "randomized_trials": 0,
            "accepted_successes": 0,
            "root_contributing_successes": 0,
            "execution_failures": 0,
            "observed_accepted_rate": 0.0,
            "observed_root_contribution_rate": 0.0,
            "laplace_smoothed_accepted_rate": 0.5,
            "laplace_smoothed_root_rate": 0.5,
            "root_weighted_heuristic_rate": 0.5,
            "sample_weight": 0.0,
            "heuristic_score_adjustment": 0.0,
            "ranking_effect": "disabled",
            "causal_eligible": False,
            "average_tokens": 0,
        },
    )
    return {
        "outcome_learning_version": OUTCOME_LEARNING_VERSION,
        "policy": "descriptive verifier-filtered outcomes; adaptive assignments never affect scheduler ranking",
        "history_scope": dict(state.get("outcome_history") or {}),
        "causal_estimate": False,
        "ranking_effect": "disabled_until_preregistered_randomized_comparison",
        "confounding_controls": "not available for adaptive historical runs",
        "calibrated_probabilities": False,
        "reference_solution_used": False,
        "private_cross_problem_cache_used": False,
        "current_strategy_family": current_family,
        "current_family": current,
        "families": families,
    }


def decisive_obligation_frontier(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the smallest active sufficient-route obligation cut near root."""

    debt_coverage_index = get_debt_coverage_index(state)
    advisor_root_cut_order, advisor_retired_debt_ids = _advisor_root_cut_policy(state)
    advisor_root_cut_rank = {
        debt_id: index for index, debt_id in enumerate(advisor_root_cut_order)
    }
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", []) or []}
    inferences_by_route: Dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for inference in state.get("inferences", []) or []:
        inferences_by_route[str(inference.get("route_id") or "")].append(inference)
    active_debts = [
        row
        for row in state.get("debts", []) or []
        if str(row.get("status") or "") == "active"
        and str(row.get("debt_id") or "") not in advisor_retired_debt_ids
        and not debt_covered_by_integrated_claim(
            state,
            row,
            debt_coverage_index=debt_coverage_index,
        )
    ]
    # A route only needs obligations attached to its route, conclusion,
    # inferences, or premises.  Index both supported attachment fields once;
    # scanning every active obligation for every route made this cut
    # computation quadratic on wide proof states.
    active_debts_by_scope_id: Dict[
        str, list[tuple[int, Mapping[str, Any]]]
    ] = defaultdict(list)
    for position, debt in enumerate(active_debts):
        owner_id = str(debt.get("owner_id") or "")
        suggested = str(debt.get("suggested_next_target") or "")
        if owner_id:
            active_debts_by_scope_id[owner_id].append((position, debt))
        if suggested and suggested != owner_id:
            active_debts_by_scope_id[suggested].append((position, debt))
    policy_index = build_graph_policy_index(state)
    paused = paused_route_ids(state)
    route_cuts: list[Dict[str, Any]] = []

    for route in state.get("routes", []) or []:
        route_id = str(route.get("route_id") or "")
        conclusion_id = str(route.get("conclusion_claim_id") or "")
        conclusion = claims.get(conclusion_id, {})
        if (
            not route_id
            or route_id in paused
            or str(route.get("status") or "") != "active"
            or str(route.get("relation_to_parent") or "") != "sufficient"
            or (
                conclusion_id != "root"
                and str(conclusion.get("lifecycle_status") or "") == "integrated"
            )
        ):
            continue
        if conclusion_id != "root" and root_distance_for_claim_id(
            state, conclusion_id, policy_index=policy_index
        ) > 2:
            continue
        route_inferences = inferences_by_route.get(route_id, [])
        owner_ids = {route_id, conclusion_id}
        for inference in route_inferences:
            owner_ids.add(str(inference.get("inference_id") or ""))
            owner_ids.update(str(item) for item in inference.get("premise_claim_ids", []) or [])
        obligations: Dict[str, Dict[str, Any]] = {}

        def add_obligation(key: str, payload: Dict[str, Any]) -> None:
            if key and key not in obligations:
                obligations[key] = payload

        scoped_debts: dict[str, tuple[int, Mapping[str, Any]]] = {}
        for owner_id in owner_ids:
            for position, debt in active_debts_by_scope_id.get(owner_id, []):
                debt_id = str(debt.get("debt_id") or "")
                key = debt_id or f"row:{position}"
                previous = scoped_debts.get(key)
                if previous is None or position < previous[0]:
                    scoped_debts[key] = (position, debt)
        for _, debt in sorted(scoped_debts.values(), key=lambda item: item[0]):
            owner_id = str(debt.get("owner_id") or "")
            suggested = str(debt.get("suggested_next_target") or "")
            severity = str(debt.get("severity") or "major")
            add_obligation(
                f"debt:{debt.get('debt_id')}",
                {
                    "obligation_type": "debt",
                    "obligation_id": str(debt.get("debt_id") or ""),
                    "target_id": suggested or owner_id or conclusion_id,
                    "route_id": route_id,
                    "severity": severity,
                    "statement": str(debt.get("obligation") or ""),
                    "weight": {"blocking": 5, "major": 3, "minor": 1}.get(severity, 2),
                },
            )
        for inference in route_inferences:
            inference_id = str(inference.get("inference_id") or "")
            if str(inference.get("validation_status") or "") not in VERIFIED_VALIDATION_STATUSES:
                add_obligation(
                    f"inference:{inference_id}",
                    {
                        "obligation_type": "inference",
                        "obligation_id": inference_id,
                        "target_id": str(inference.get("conclusion_claim_id") or conclusion_id),
                        "route_id": route_id,
                        "severity": "blocking",
                        "statement": str(inference.get("explanation") or "verify the terminal inference"),
                        "weight": 4,
                    },
                )
            for premise_id in inference.get("premise_claim_ids", []) or []:
                premise_id = str(premise_id)
                premise = claims.get(premise_id, {})
                if premise and claim_is_unresolved(premise):
                    add_obligation(
                        f"claim:{premise_id}",
                        {
                            "obligation_type": "claim",
                            "obligation_id": premise_id,
                            "target_id": premise_id,
                            "route_id": route_id,
                            "severity": "blocking",
                            "statement": str(premise.get("statement") or ""),
                            "weight": 4,
                        },
                    )
        if not route_inferences:
            if conclusion and claim_is_unresolved(conclusion):
                add_obligation(
                    f"claim:{conclusion_id}",
                    {
                        "obligation_type": "claim",
                        "obligation_id": conclusion_id,
                        "target_id": conclusion_id,
                        "route_id": route_id,
                        "severity": "blocking",
                        "statement": str(conclusion.get("statement") or ""),
                        "weight": 4,
                    },
                )
        ordered = sorted(
            obligations.values(),
            key=lambda item: (
                0 if str(item.get("obligation_id") or "") in advisor_root_cut_rank else 1,
                advisor_root_cut_rank.get(
                    str(item.get("obligation_id") or ""), len(advisor_root_cut_rank)
                ),
                -int(item.get("weight") or 0),
                root_distance_for_claim_id(
                    state,
                    str(item.get("target_id") or ""),
                    policy_index=policy_index,
                ),
                str(item.get("obligation_id") or ""),
            ),
        )
        route_cuts.append(
            {
                "route_id": route_id,
                "conclusion_claim_id": conclusion_id,
                "obligation_count": len(ordered),
                "weighted_cost": sum(int(item.get("weight") or 0) for item in ordered),
                "obligations": ordered,
            }
        )

    route_cuts.sort(
        key=lambda cut: (
            int(cut["weighted_cost"]),
            int(cut["obligation_count"]),
            0 if str(cut["conclusion_claim_id"]) == "root" else 1,
            str(cut["route_id"]),
        )
    )
    selected = route_cuts[0] if route_cuts else {}
    obligations = list(selected.get("obligations", []))
    if not obligations and not route_cuts:
        for debt in sorted(
            active_debts,
            key=lambda row: (
                str(row.get("severity") or "") != "blocking",
                root_distance_for_claim_id(
                    state,
                    str(row.get("suggested_next_target") or row.get("owner_id") or ""),
                    policy_index=policy_index,
                ),
                str(row.get("debt_id") or ""),
            ),
        )[:6]:
            obligations.append(
                {
                    "obligation_type": "debt",
                    "obligation_id": str(debt.get("debt_id") or ""),
                    "target_id": str(debt.get("suggested_next_target") or debt.get("owner_id") or "root"),
                    "route_id": "",
                    "severity": str(debt.get("severity") or "major"),
                    "statement": str(debt.get("obligation") or ""),
                    "weight": {"blocking": 5, "major": 3, "minor": 1}.get(str(debt.get("severity") or ""), 2),
                }
            )
    return {
        "obligation_frontier_version": OBLIGATION_FRONTIER_VERSION,
        "policy": "smallest graph-derived sufficient-route obligation cut",
        "graph_derived": True,
        "advisor_root_cut_order": advisor_root_cut_order,
        "advisor_retired_debt_ids": sorted(advisor_retired_debt_ids),
        "self_reported_root_leverage_used": False,
        "selected_route_id": str(selected.get("route_id") or ""),
        "selected_route_ready_for_verification": bool(route_cuts and not selected.get("obligations")),
        "minimal_cut_obligations": obligations[:6],
        "decisive_obligation": obligations[0] if obligations else {},
        "alternate_route_costs": [
            {
                "route_id": str(cut.get("route_id") or ""),
                "weighted_cost": int(cut.get("weighted_cost") or 0),
                "obligation_count": int(cut.get("obligation_count") or 0),
            }
            for cut in route_cuts[:5]
        ],
    }


def deep_session_roi(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    target_id = str(action.get("target_id") or "root")
    deep_artifacts = {
        str(row.get("artifact_id") or "")
        for row in _artifact_rows(state)
        if str(row.get("artifact_type") or "") == "deep_session_report"
        or (
            str(row.get("artifact_type") or "") in {"proof_dossier", "proof_blueprint"}
            and int(_artifact_metadata(row).get("deep_session_roi_version") or 0)
            == DEEP_SESSION_ROI_VERSION
        )
    }
    accepted_run_ids = {
        str(row.get("run_id") or "")
        for row in state.get("accepted_mathematical_deltas", []) or []
        if isinstance(row, Mapping) and row.get("changes")
    }
    candidates: list[Dict[str, Any]] = []
    for run in (state.get("outcome_runs") or state.get("recent_runs") or []):
        if str(run.get("target_id") or "") != target_id:
            continue
        output_ids = {
            str(item)
            for item in _json_list(run.get("output_artifact_ids_json"))
            if str(item)
        }
        if not output_ids & deep_artifacts:
            continue
        run_id = str(run.get("run_id") or "")
        changed = bool(run_id and run_id in accepted_run_ids)
        candidates.append(
            {
                "run_id": run_id,
                "artifact_ids": sorted(output_ids & deep_artifacts),
                "state_revision": int(run.get("state_revision") or 0),
                "accepted_graph_change": changed,
            }
        )
    candidates.sort(key=lambda item: (item["state_revision"], item["run_id"]), reverse=True)
    recent = candidates[:2]
    stalled = len(recent) >= 2 and not any(item["accepted_graph_change"] for item in recent)
    current_philosophy = str(action.get("research_philosophy") or "")
    philosophy_cycle = (
        "direct_proof",
        "adversarial_probe",
        "theorem_adaptation",
        "representation_switch",
        "alternative_construction",
        "global_assembly",
    )
    next_philosophy = next((item for item in philosophy_cycle if item != current_philosophy), "alternative_construction")
    return {
        "deep_session_roi_version": DEEP_SESSION_ROI_VERSION,
        "target_id": target_id,
        "allowed": not stalled,
        "recent_sessions": recent,
        "consecutive_no_delta_limit": 2,
        "host_journal_is_authoritative": True,
        "artifact_self_assessment_used": False,
        "forced_next_philosophy": next_philosophy if stalled else "",
        "reason": (
            "two recent long sessions produced no proof-state mathematical delta"
            if stalled
            else "deep-session ROI gate is open"
        ),
    }


def representation_switch_contract(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    target_id = str(action.get("target_id") or "root")
    repeated = sum(
        1
        for run in (state.get("recent_runs", []) or [])[:12]
        if str(run.get("target_id") or "") == target_id
        and str(run.get("actor_role") or "") in {"researcher", "adversarial_reviewer", "villain"}
    )
    due = repeated >= 2 or any(
        action.get(key)
        for key in (
            "deep_session_required",
            "conceptual_invariant_discovery_required",
            "bridge_lemma_workbench_required",
            "decisive_theorem_test_required",
            "creative_proof_attack_required",
        )
    )
    if not due:
        return {}
    text = " ".join(
        [
            str(state.get("problem_state", {}).get("root_statement") or ""),
            str(action.get("reason") or ""),
            str(action.get("decisive_obligation_statement") or ""),
        ]
    )
    domains = infer_domain_tags(text)
    suggestions: list[str] = []
    for domain in domains:
        suggestions.extend(_REPRESENTATIONS_BY_DOMAIN.get(domain, ()))
    if not suggestions:
        suggestions = [
            "original object language",
            "invariant or functorial language",
            "extremal or minimal-counterexample language",
            "computational or finite-model language",
        ]
    return {
        "representation_switch_version": REPRESENTATION_SWITCH_VERSION,
        "minimum_representations": 2,
        "maximum_representations": 4,
        "domain_tags": domains,
        "suggested_representations": list(dict.fromkeys(suggestions))[:6],
        "required_fields": list(REPRESENTATION_SWITCH_FIELDS),
        "round_trip_rule": "state and check the implication or equivalence back to the original obligation",
        "selection_rule": "choose the representation that makes the decisive missing statement strictly simpler",
    }


def theorem_adaptation_contract(action: Mapping[str, Any]) -> Dict[str, Any]:
    mode = str(action.get("mode") or "")
    worker = str(action.get("multi_branch_worker") or "")
    due = mode in {"retrieve", "synthesize_sources", "audit_definitions"} or worker == "literature_adaptation"
    due = due or bool(action.get("source_adaptation_digest_required"))
    if not due:
        return {}
    return {
        "theorem_adaptation_version": THEOREM_ADAPTATION_VERSION,
        "required_fields": list(THEOREM_ADAPTATION_FIELDS),
        "source_technique_compiler": {
            "source_technique_compiler_version": SOURCE_TECHNIQUE_COMPILER_VERSION,
            "required_fields": list(SOURCE_TECHNIQUE_FIELDS),
            "proof_skeleton_not_summary_required": True,
            "hypothesis_necessity_required": True,
            "failure_examples_required": True,
            "translated_next_deduction_required": True,
        },
        "survey_only_output_rejected": True,
        "hypothesis_mapping_required": True,
        "definition_translation_required": True,
        "proof_technique_extraction_required": True,
        "exact_local_deduction_required": True,
        "stop_after_decisive_match": True,
    }


def _interface_values(statement: str) -> Dict[str, Any]:
    normalized = normalize_text(statement)

    object_types = []
    for cue, label in (
        ("group", "group"),
        ("permutation", "permutation_group"),
        ("module", "module"),
        ("representation", "representation"),
        ("variety", "variety"),
        ("scheme", "scheme"),
        ("graph", "graph"),
        ("character", "character"),
    ):
        if cue in normalized and label not in object_types:
            object_types.append(label)

    ambient_categories = []
    for cue, label in (
        ("primitive permutation", "finite_primitive_permutation_groups"),
        ("locally finite", "locally_finite_groups"),
        ("finite group", "finite_groups"),
        ("algebraic variety", "algebraic_varieties"),
        ("scheme", "schemes"),
    ):
        if cue in normalized:
            ambient_categories.append(label)

    fields = []
    for cue, label in (
        ("characteristic 2", "characteristic_2"),
        ("characteristic p", "characteristic_p"),
        ("complex", "complex_numbers"),
        ("real", "real_numbers"),
        ("finite field", "finite_field"),
    ):
        if cue in normalized:
            fields.append(label)

    action_types = []
    for cue, label in (
        ("semilinear", "semilinear"),
        ("linear", "linear"),
        ("permutation", "permutation"),
        ("acts on", "group_action"),
        ("suborbit", "point_stabilizer_action"),
    ):
        if cue in normalized and label not in action_types:
            action_types.append(label)

    subobject_scope = []
    for cue, label in (
        ("subgroup", "subgroups"),
        ("quotient", "quotients"),
        ("section", "sections"),
        ("subquotient", "subquotients"),
        ("stabiliser", "stabilizers"),
        ("stabilizer", "stabilizers"),
        ("normal subgroup", "normal_subgroups"),
    ):
        if cue in normalized and label not in subobject_scope:
            subobject_scope.append(label)

    ranges = re.findall(r"\b[a-z][a-z0-9_]*\s*(?:>=|<=|>|<|=)\s*-?\d+\b", normalized)
    universal = any(cue in normalized for cue in _UNIVERSAL_CUES)
    existential = bool(re.search(r"\b(?:there exists|exists|some)\b", normalized))
    return {
        "object_types": object_types or ["unspecified"],
        "ambient_categories": ambient_categories or ["unspecified"],
        "base_fields_or_rings": fields or ["not_applicable_or_unspecified"],
        "action_types": action_types or ["not_applicable_or_unspecified"],
        "finiteness_scope": (
            "locally_finite" if "locally finite" in normalized else "finite" if "finite" in normalized else "unspecified"
        ),
        "quantifier_scope": {
            "universal": universal,
            "existential": existential,
            "order_must_be_preserved": universal and existential,
        },
        "subobject_quotient_scope": subobject_scope or ["not_applicable_or_unspecified"],
        "normalization_conventions": [
            cue for cue in ("regular suborbit", "2 point stabiliser", "2 point stabilizer") if cue in normalized
        ] or ["none_declared"],
        "parameter_ranges": ranges or ["none_declared"],
    }


def mathematical_interface_contract(
    state: Mapping[str, Any], action: Mapping[str, Any]
) -> Dict[str, Any]:
    target_id = str(action.get("target_id") or "root")
    claim = next(
        (row for row in state.get("claims", []) if str(row.get("claim_id") or "") == target_id),
        {},
    )
    statement = str(claim.get("statement") or "")
    if not statement and target_id == "root":
        statement = str(state.get("problem_state", {}).get("root_statement") or "")
    route_id = str(action.get("route_id") or "")
    premise_ids: list[str] = []
    if route_id:
        for inference in state.get("inferences", []):
            if str(inference.get("route_id") or "") != route_id:
                continue
            premise_ids.extend(str(item) for item in inference.get("premise_claim_ids", []) if str(item))
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    premise_interfaces = [
        {
            "claim_id": claim_id,
            "statement": str(claims.get(claim_id, {}).get("statement") or ""),
            "interface": _interface_values(str(claims.get(claim_id, {}).get("statement") or "")),
        }
        for claim_id in dict.fromkeys(premise_ids)
        if claim_id in claims
    ]
    target_interface = _interface_values(statement)
    risk_flags = []
    combined_actions = {
        item
        for card in [target_interface, *(row["interface"] for row in premise_interfaces)]
        for item in card.get("action_types", [])
    }
    if {"linear", "semilinear"}.issubset(combined_actions):
        risk_flags.append("linear_semilinear_mismatch")
    combined_scopes = {
        item
        for card in [target_interface, *(row["interface"] for row in premise_interfaces)]
        for item in card.get("subobject_quotient_scope", [])
    }
    if len(combined_scopes & {"subgroups", "quotients", "sections", "subquotients"}) > 1:
        risk_flags.append("subgroup_quotient_section_mismatch")
    if target_interface.get("quantifier_scope", {}).get("order_must_be_preserved"):
        risk_flags.append("mixed_quantifier_order")
    return {
        "mathematical_interface_version": MATHEMATICAL_INTERFACE_VERSION,
        "target_id": target_id,
        "target_statement": statement,
        "target_interface": target_interface,
        "premise_interfaces": premise_interfaces,
        "required_fields": list(MATHEMATICAL_INTERFACE_FIELDS),
        "risk_flags": risk_flags,
        "unresolved_mismatches_must_block_verification": True,
        "comparison_rule": (
            "Compare every premise and representation with the target before certification; "
            "do not silently identify linear with semilinear, subgroup with section/quotient, "
            "finite with universal, or differently normalized invariants."
        ),
    }


def theorem_preflight_contract(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a compact, risk-triggered statement audit from existing data.

    This is not a new report.  It is an automatically generated checklist
    attached to the ordinary research or verification task only when the
    target has universal, boundary, or representation-transfer risk.
    """

    mode = str(action.get("mode") or "")
    if mode not in {"prove", "reduce", "weaken", "strengthen", "refute", "integrate", "formalize"}:
        return {}
    target_id = str(action.get("target_id") or "root")
    claim = next(
        (
            row
            for row in state.get("claims", [])
            if str(row.get("claim_id") or "") == target_id
        ),
        {},
    )
    statement = str(claim.get("statement") or "")
    hypotheses = claim.get("hypotheses")
    conditions = claim.get("conditions")
    if conditions in (None, ""):
        conditions = _json_list(claim.get("conditions_json"))
    normalized = normalize_text(" ".join([statement, str(hypotheses or ""), str(conditions or "")]))
    universal = any(cue in normalized for cue in _UNIVERSAL_CUES)
    representation_risk = any(cue in normalized for cue in _REPRESENTATION_RISK_CUES)
    boundary_risk = any(cue in normalized for cue in _BOUNDARY_CUES) or bool(
        re.search(r"(?:>=|<=|>|<|=)\s*-?\d", statement)
    )
    root_critical = target_id == "root" or float(claim.get("root_impact") or 0.0) >= 0.7
    classification_scope_risk = bool(
        root_critical and any(cue in normalized for cue in _CLASSIFICATION_SCOPE_CUES)
    )
    example_family_risk = bool(
        classification_scope_risk
        and any(cue in normalized for cue in _EXAMPLE_FAMILY_CUES)
    )
    case_map = action.get("case_coverage_map") if isinstance(action.get("case_coverage_map"), Mapping) else {}
    open_cases = []
    for program in case_map.get("programs", []) if isinstance(case_map.get("programs"), list) else []:
        if not isinstance(program, Mapping):
            continue
        if str(program.get("route_id") or "") not in {"", str(action.get("route_id") or "")}:
            continue
        for item in program.get("open_cases", []) if isinstance(program.get("open_cases"), list) else []:
            text = str(item or "").strip()
            if text and text not in open_cases:
                open_cases.append(text)
    unspecified_root_coverage = bool(
        root_critical
        and any(
            isinstance(program, Mapping)
            and str(program.get("status") or "") == "unspecified"
            for program in case_map.get("programs", []) if isinstance(case_map.get("programs"), list)
        )
    )
    if not (
        representation_risk
        or (root_critical and (universal or boundary_risk))
        or classification_scope_risk
        or open_cases
        or unspecified_root_coverage
    ):
        return {}

    probes = ["test the weakest allowed hypotheses and equality endpoints"]
    if universal:
        probes.append("test zero, one, and minimal admissible parameter values before the universal proof")
    if boundary_risk:
        probes.append("test minimal dimension/rank/degree and every stated equality case")
    if representation_risk:
        probes.append("separate the original object from the model and state the exact transfer back")
    if classification_scope_risk:
        probes.append(
            "state the intended exhaustive if-and-only-if classification target while preserving the submitted root wording"
        )
    if example_family_risk:
        probes.append(
            "treat every displayed known family as evidence only; test whether it is exhaustive and search minimal boundary counterexamples"
        )
    probes.extend(f"test named uncovered case: {case}" for case in open_cases[:6])
    return {
        "theorem_preflight_version": THEOREM_PREFLIGHT_VERSION,
        "target_id": target_id,
        "risk_level": (
            "high"
            if representation_risk or (universal and boundary_risk) or example_family_risk
            else "medium"
        ),
        "risk_flags": {
            "universal_or_iff_statement": universal,
            "boundary_or_endpoint_parameters": boundary_risk,
            "representation_or_transport_step": representation_risk,
            "classification_scope_requires_iff_target": classification_scope_risk,
            "displayed_examples_may_not_be_exhaustive": example_family_risk,
            "root_critical": root_critical,
            "named_open_cases": open_cases,
            "root_case_coverage_unspecified": unspecified_root_coverage,
        },
        "canonical_signature": {
            "statement": statement,
            "hypotheses": hypotheses or "",
            "conditions": conditions or [],
        },
        "required_checks": [
            "domains and omitted endpoint hypotheses",
            "zero/minimal/degenerate cases when admissible",
            "equality cases and normalization conventions",
            "the exact original object used by the downstream application",
            *(
                [
                    "the exact exhaustive iff target implicit in describe/classify wording",
                    "the definitions, normalization, and boundary convention for every invariant used in the classification",
                ]
                if classification_scope_risk
                else []
            ),
            *(
                [
                    "known example families are not silently promoted to an exhaustive answer",
                ]
                if example_family_risk
                else []
            ),
        ],
        "suggested_probes": probes,
        "case_coverage_gate": {
            "open_cases": open_cases,
            "cases_exhaustive_required_for_root_closure": root_critical,
            "unspecified_coverage_must_be_resolved": unspecified_root_coverage,
        },
        "new_management_artifact_required": False,
        "cache_key": str(claim.get("fingerprint") or target_id),
    }


def proof_interface_contract(
    action: Mapping[str, Any], *, state: Mapping[str, Any] | None = None
) -> Dict[str, Any]:
    mode = str(action.get("mode") or "")
    route_id = str(action.get("route_id") or "")
    selective = mode in {"integrate", "formalize", "validate_counterexample"}
    selective = selective or bool(action.get("parent_implication_required"))
    mathematical_interface: Dict[str, Any] = {}
    if state is not None:
        mathematical_interface = mathematical_interface_contract(state, action)
    if mode == "prove" and route_id:
        # Routed verification always remains a strict, evidence-bound proof
        # check. The large typed-interface checklist is an additional
        # safeguard for root-critical or transfer-sensitive arguments, not a
        # paperwork prerequisite for an elementary side lemma.
        if state is None:
            selective = True  # conservative for callers without proof state
        else:
            target_id = str(action.get("target_id") or "root")
            claim = next(
                (
                    row
                    for row in state.get("claims", [])
                    if str(row.get("claim_id") or "") == target_id
                ),
                {},
            )
            try:
                root_impact = float(claim.get("root_impact") or 0.0)
            except (TypeError, ValueError):
                root_impact = 0.0
            high_risk_recheck = any(
                bool(action.get(flag))
                for flag in (
                    "dependency_threat_revalidation_required",
                    "revalidating_integrated_route",
                    "proof_repair_verification_required",
                    "advisor_requested_verification",
                )
            )
            selective = selective or bool(
                not claim
                or target_id == "root"
                or root_impact >= 0.7
                or action.get("theorem_preflight_required")
                or mathematical_interface.get("risk_flags")
                or high_risk_recheck
            )
    if not selective:
        return {}
    result = {
        "proof_interface_check_version": PROOF_INTERFACE_CHECK_VERSION,
        "required_boolean_fields": list(PROOF_INTERFACE_FIELDS),
        "lean4_required": False,
        "scope": (
            "quantifiers, hypothesis propagation, case exhaustiveness, reduction direction, "
            "finite-to-universal boundaries, and dependency assembly"
        ),
        "zero_gap_rule": "a verified verdict requires every interface field to be true",
        "theorem_preflight": dict(action.get("theorem_preflight_contract") or {}),
    }
    if state is not None:
        result["mathematical_interface"] = mathematical_interface
        result["required_metadata"] = {
            "mathematical_interface_version": MATHEMATICAL_INTERFACE_VERSION,
            "interface_checks": "one explicit comparison per risk flag and proof boundary",
            "unresolved_interface_mismatches": "a list, empty only after all comparisons pass",
        }
    return result


def philosophy_signature(action: Mapping[str, Any]) -> tuple[str, ...]:
    family = strategy_family(action)
    mode = str(action.get("mode") or "")
    worker = str(action.get("multi_branch_worker") or "")
    return tuple(item for item in (family, mode, worker) if item)


def validate_proof_interface_metadata(metadata: Mapping[str, Any]) -> list[str]:
    version = int(metadata.get("proof_interface_check_version") or 0)
    if version not in {1, PROOF_INTERFACE_CHECK_VERSION}:
        return []
    errors = [f"proof interface check requires {field}" for field in PROOF_INTERFACE_FIELDS if field not in metadata]
    verdict = str(metadata.get("verdict") or "").lower()
    if verdict in {"verified", "correct_no_gaps", "pass", "correct", "integrates"} or metadata.get("integrates") is True:
        false_fields = [field for field in PROOF_INTERFACE_FIELDS if metadata.get(field) is not True]
        if false_fields:
            errors.append("zero-gap verdict requires true proof interface checks: " + ", ".join(false_fields))
        if version >= 2 and int(metadata.get("mathematical_interface_version") or 0) != MATHEMATICAL_INTERFACE_VERSION:
            errors.append(
                f"zero-gap verdict requires mathematical_interface_version={MATHEMATICAL_INTERFACE_VERSION}"
            )
        checks = metadata.get("interface_checks")
        if version >= 2 and (not isinstance(checks, (list, dict)) or not checks):
            errors.append("zero-gap verdict requires nonempty interface_checks")
        unresolved = metadata.get("unresolved_interface_mismatches")
        if version >= 2 and not isinstance(unresolved, list):
            errors.append("zero-gap verdict requires unresolved_interface_mismatches as a list")
        elif version >= 2 and unresolved:
            errors.append("zero-gap verdict cannot retain unresolved_interface_mismatches")
    return errors


def _mapping_declares_nonempty_field(value: Any, field: str) -> bool:
    if isinstance(value, Mapping):
        if field in value:
            candidate = value.get(field)
            if field == "missing_hypotheses" and isinstance(candidate, list):
                return True
            if candidate not in (None, "", [], {}):
                return True
        return any(_mapping_declares_nonempty_field(item, field) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_mapping_declares_nonempty_field(item, field) for item in value)
    return False


def _content_declares_theorem_adaptation_field(content: Any, field: str) -> bool:
    if isinstance(content, Mapping):
        return _mapping_declares_nonempty_field(content, field)
    text = str(content or "")
    decoded = json_loads(text, {})
    if isinstance(decoded, Mapping) and _mapping_declares_nonempty_field(decoded, field):
        return True
    marker = re.search(
        rf"(?mi)^\s*(?:[-*]\s*)?{re.escape(field)}\s*:\s*(.*)$",
        text,
    )
    if marker is None:
        return False
    inline_value = marker.group(1).strip()
    if inline_value or field == "missing_hypotheses":
        return True
    remainder = text[marker.end() :]
    next_field = re.search(r"(?m)^\s*(?:[-*]\s*)?[a-z][a-z0-9_]*\s*:", remainder)
    block = remainder[: next_field.start()] if next_field else remainder
    return bool(block.strip())


def validate_theorem_adaptation_metadata(
    metadata: Mapping[str, Any],
    *,
    content: Any = None,
) -> list[str]:
    if int(metadata.get("theorem_adaptation_version") or 0) != THEOREM_ADAPTATION_VERSION:
        return []
    errors: list[str] = []
    for field in THEOREM_ADAPTATION_FIELDS:
        if field not in metadata or metadata.get(field) in (None, "", {}):
            if field == "missing_hypotheses" and isinstance(metadata.get(field), list):
                continue
            if _content_declares_theorem_adaptation_field(content, field):
                continue
            errors.append(f"theorem adaptation packet requires {field}")
    return errors


def validate_source_technique_metadata(
    metadata: Mapping[str, Any], *, content: Any = None
) -> list[str]:
    if int(metadata.get("source_technique_compiler_version") or 0) != SOURCE_TECHNIQUE_COMPILER_VERSION:
        return []
    errors: list[str] = []
    for field in SOURCE_TECHNIQUE_FIELDS:
        if field not in metadata or metadata.get(field) in (None, "", [], {}):
            if _content_declares_theorem_adaptation_field(content, field):
                continue
            errors.append(f"source technique compiler requires {field}")
    return errors


def validate_representation_switch_metadata(metadata: Mapping[str, Any]) -> list[str]:
    if int(metadata.get("representation_switch_version") or 0) != REPRESENTATION_SWITCH_VERSION:
        return []
    errors = [
        f"representation switch requires {field}"
        for field in REPRESENTATION_SWITCH_FIELDS
        if field not in metadata or metadata.get(field) in (None, "", [], {})
    ]
    representations = metadata.get("representations_considered")
    if not isinstance(representations, list) or len(representations) < 2:
        errors.append("representation switch requires at least two representations_considered")
    return errors


def validate_deep_session_roi_metadata(metadata: Mapping[str, Any]) -> list[str]:
    if int(metadata.get("deep_session_roi_version") or 0) != DEEP_SESSION_ROI_VERSION:
        return []
    errors: list[str] = []
    delta_kind = str(metadata.get("mathematical_delta_kind") or "")
    if delta_kind not in PRODUCTIVE_DELTA_KINDS:
        errors.append("deep-session persistence requires a productive mathematical_delta_kind")
    if metadata.get("changed_proof_state") is not True:
        errors.append("deep-session persistence requires changed_proof_state=true")
    if not str(metadata.get("mathematical_delta_summary") or "").strip():
        errors.append("deep-session persistence requires mathematical_delta_summary")
    if not str(metadata.get("next_philosophy_if_stalled") or "").strip():
        errors.append("deep-session persistence requires next_philosophy_if_stalled")
    return errors


def validate_state_independent_artifact_metadata(
    *,
    artifact_type: str,
    metadata: Mapping[str, Any],
    content: Any = None,
) -> list[str]:
    """Validate artifact contracts that do not require proof-store state.

    The runner can apply these checks before ending the child session, so a
    malformed patch can be repaired in place instead of being discarded by
    the later SQLite guard.  Store-dependent checks remain in
    ``strategic_artifact_errors``.
    """

    errors: list[str] = []
    errors.extend(validate_proof_interface_metadata(metadata))
    errors.extend(validate_theorem_adaptation_metadata(metadata, content=content))
    errors.extend(validate_source_technique_metadata(metadata, content=content))
    errors.extend(validate_representation_switch_metadata(metadata))
    if artifact_type in {"proof_dossier", "proof_blueprint"}:
        errors.extend(validate_deep_session_roi_metadata(metadata))
    return errors


def action_patch_contract_errors(action: Mapping[str, Any], patch: Mapping[str, Any]) -> list[str]:
    """Enforce only contracts whose omission would make verification unsafe."""

    operations = [item for item in patch.get("operations", []) or [] if isinstance(item, Mapping)]
    attachments = [item for item in operations if str(item.get("op") or "") == "attach_artifact"]
    errors: list[str] = []
    if action.get("proof_interface_check_required"):
        reports = [
            item
            for item in attachments
            if str(item.get("artifact_type") or "") in {"verification_report", "integration_report"}
        ]
        if reports and not any(
            int(_json_object(item.get("metadata")).get("proof_interface_check_version") or 0)
            == PROOF_INTERFACE_CHECK_VERSION
            for item in reports
        ):
            errors.append("scheduled proof-interface check missing from verifier report metadata")
    return errors
