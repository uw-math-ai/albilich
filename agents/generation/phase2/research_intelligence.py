from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Mapping

from .graph_policy import (
    VERIFIED_VALIDATION_STATUSES,
    claim_is_unresolved,
    debt_covered_by_integrated_claim,
    paused_route_ids,
    root_distance_for_claim_id,
)
from .models import json_loads, normalize_text


OUTCOME_LEARNING_VERSION = 1
OBLIGATION_FRONTIER_VERSION = 1
DEEP_SESSION_ROI_VERSION = 1
REPRESENTATION_SWITCH_VERSION = 1
THEOREM_ADAPTATION_VERSION = 1
PROOF_INTERFACE_CHECK_VERSION = 1

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

REPRESENTATION_SWITCH_FIELDS = (
    "representations_considered",
    "translation_dictionary",
    "equivalence_or_implication_checks",
    "chosen_representation",
    "choice_reason",
    "next_test_in_chosen_representation",
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
    "combinatorics": ("graph", "hypergraph", "coloring", "matching", "set system", "extremal"),
    "algebraic_geometry": ("scheme", "variety", "fiber", "flat", "dimension", "specialization"),
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
    return sorted(
        domain
        for domain, cues in _DOMAIN_CUES.items()
        if any(normalize_text(cue) in normalized for cue in cues)
    )


def strategy_family(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("research_philosophy") or "").strip()
    if explicit:
        explicit_family = {
            "main_spine_construction": "global_assembly",
            "global_assembly": "global_assembly",
            "local_support_lemma": "bridge_lemma",
            "external_theorem_adaptation": "theorem_adaptation",
            "adversarial_probe": "adversarial_probe",
            "conceptual_invariant": "conceptual_invariant",
            "conceptual_invariant_discovery": "conceptual_invariant",
            "alternative_construction": "alternative_construction",
            "representation_switch": "representation_switch",
            "direct_proof": "direct_proof",
        }.get(explicit)
        if explicit_family:
            return explicit_family
    text = " ".join(
        [
            str(row.get("search_intent") or ""),
            str(row.get("researcher_work_mode") or ""),
            str(row.get("mode") or ""),
        ]
    ).lower()
    families = (
        ("adversarial_probe", ("refute", "villain", "counterexample", "obstruction")),
        ("theorem_adaptation", ("retrieve", "literature", "citation", "source", "theorem_search")),
        ("conceptual_invariant", ("conceptual", "invariant")),
        ("experimental_mathematics", ("experiment", "cas", "compute")),
        ("global_assembly", ("compression", "spine", "synthesis", "assembly")),
        ("bridge_lemma", ("bridge", "support_lemma", "nearby_lemma")),
        ("alternative_construction", ("alternative", "construction")),
        ("direct_proof", ("prove", "direct_solve")),
    )
    for family, cues in families:
        if any(cue in text for cue in cues):
            return family
    return str(row.get("mode") or "research")


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


def verifier_filtered_outcome_learning(
    state: Mapping[str, Any], action: Mapping[str, Any] | None = None
) -> Dict[str, Any]:
    """Calibrate strategy families only from accepted proof-state outcomes.

    This is deliberately not benchmark scoring and never consults a reference
    solution. A research run earns success only when one of its output
    artifacts later appears in verified/integrated evidence, or when its
    concrete route is integrated. Rejections and timeouts remain negative
    evidence; merely producing prose is not a success.
    """

    verified_evidence = _verified_evidence_ids(state)
    integrated_routes = {
        str(row.get("route_id") or "")
        for row in state.get("routes", []) or []
        if str(row.get("status") or "") == "integrated"
    }
    verified_claims = {
        str(row.get("claim_id") or "")
        for row in state.get("claims", []) or []
        if str(row.get("claim_id") or "") != "root"
        and (
            str(row.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES
            or str(row.get("lifecycle_status") or "") == "integrated"
        )
    }
    grouped: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"trials": 0.0, "verified_successes": 0.0, "execution_failures": 0.0, "tokens": 0.0}
    )
    for run in state.get("recent_runs", []) or []:
        role = str(run.get("actor_role") or "")
        if role not in {"researcher", "villain", "literature_researcher"}:
            continue
        family = strategy_family(run)
        stats = grouped[family]
        stats["trials"] += 1
        stats["tokens"] += float(run.get("total_tokens") or 0.0)
        status = str(run.get("status") or "").lower()
        if status in {"patch_rejected", "timeout", "no_patch", "failed", "error", "cancelled"}:
            stats["execution_failures"] += 1
        output_ids = {str(item) for item in _json_list(run.get("output_artifact_ids_json")) if str(item)}
        route_id = str(run.get("route_id") or "")
        target_id = str(run.get("target_id") or "")
        success = bool(output_ids & verified_evidence)
        success = success or bool(route_id and route_id in integrated_routes)
        success = success or bool(target_id and target_id in verified_claims)
        if success:
            stats["verified_successes"] += 1

    families: Dict[str, Dict[str, Any]] = {}
    for family, raw in sorted(grouped.items()):
        trials = int(raw["trials"])
        successes = int(raw["verified_successes"])
        posterior = (successes + 1.0) / (trials + 2.0)
        confidence = min(1.0, trials / 8.0)
        adjustment = (posterior - 0.5) * confidence
        families[family] = {
            "trials": trials,
            "verified_successes": successes,
            "execution_failures": int(raw["execution_failures"]),
            "posterior_verified_yield": round(posterior, 4),
            "confidence": round(confidence, 3),
            "score_adjustment": round(adjustment, 4),
            "average_tokens": round(raw["tokens"] / max(1, trials)),
        }

    current_family = strategy_family(action or {}) if action is not None else ""
    current = families.get(
        current_family,
        {
            "trials": 0,
            "verified_successes": 0,
            "execution_failures": 0,
            "posterior_verified_yield": 0.5,
            "confidence": 0.0,
            "score_adjustment": 0.0,
            "average_tokens": 0,
        },
    )
    return {
        "outcome_learning_version": OUTCOME_LEARNING_VERSION,
        "policy": "verifier-filtered local outcome learning",
        "reference_solution_used": False,
        "private_cross_problem_cache_used": False,
        "current_strategy_family": current_family,
        "current_family": current,
        "families": families,
    }


def decisive_obligation_frontier(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the smallest active sufficient-route obligation cut near root."""

    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", []) or []}
    inferences_by_route: Dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for inference in state.get("inferences", []) or []:
        inferences_by_route[str(inference.get("route_id") or "")].append(inference)
    active_debts = [
        row
        for row in state.get("debts", []) or []
        if str(row.get("status") or "") == "active"
        and not debt_covered_by_integrated_claim(state, row)
    ]
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
        if conclusion_id != "root" and root_distance_for_claim_id(state, conclusion_id) > 2:
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

        for debt in active_debts:
            owner_id = str(debt.get("owner_id") or "")
            suggested = str(debt.get("suggested_next_target") or "")
            if owner_id not in owner_ids and suggested not in owner_ids:
                continue
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
                -int(item.get("weight") or 0),
                root_distance_for_claim_id(state, str(item.get("target_id") or "")),
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
                    state, str(row.get("suggested_next_target") or row.get("owner_id") or "")
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
    candidates: list[Dict[str, Any]] = []
    for row in _artifact_rows(state):
        artifact_type = str(row.get("artifact_type") or "")
        metadata = _artifact_metadata(row)
        if artifact_type not in {"deep_session_report", "proof_dossier", "proof_blueprint"}:
            continue
        if artifact_type != "deep_session_report" and int(metadata.get("deep_session_roi_version") or 0) != DEEP_SESSION_ROI_VERSION:
            continue
        artifact_target = str(metadata.get("exact_local_target") or metadata.get("target_id") or "root")
        if artifact_target != target_id:
            continue
        delta_kind = str(metadata.get("mathematical_delta_kind") or "")
        changed = metadata.get("changed_proof_state") is True
        if not delta_kind:
            roi = str(metadata.get("artifact_roi") or "")
            changed = changed or roi in {"verifier_ready_route", "route_repaired", "debt_closed_or_sharpened"}
            delta_kind = "legacy_productive_delta" if changed else "none"
        candidates.append(
            {
                "artifact_id": str(row.get("artifact_id") or ""),
                "state_revision": int(row.get("state_revision") or 0),
                "delta_kind": delta_kind,
                "productive": changed and delta_kind != "none",
            }
        )
    candidates.sort(key=lambda item: (item["state_revision"], item["artifact_id"]), reverse=True)
    recent = candidates[:2]
    stalled = len(recent) >= 2 and not any(item["productive"] for item in recent)
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
        "delta_only_persistence": True,
        "management_only_report_is_progress": False,
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
        and str(run.get("actor_role") or "") in {"researcher", "villain"}
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
        "survey_only_output_rejected": True,
        "hypothesis_mapping_required": True,
        "definition_translation_required": True,
        "proof_technique_extraction_required": True,
        "exact_local_deduction_required": True,
        "stop_after_decisive_match": True,
    }


def proof_interface_contract(action: Mapping[str, Any]) -> Dict[str, Any]:
    mode = str(action.get("mode") or "")
    route_id = str(action.get("route_id") or "")
    selective = mode in {"integrate", "formalize", "validate_counterexample"}
    selective = selective or (mode == "prove" and bool(route_id))
    selective = selective or bool(action.get("parent_implication_required"))
    if not selective:
        return {}
    return {
        "proof_interface_check_version": PROOF_INTERFACE_CHECK_VERSION,
        "required_boolean_fields": list(PROOF_INTERFACE_FIELDS),
        "lean4_required": False,
        "scope": (
            "quantifiers, hypothesis propagation, case exhaustiveness, reduction direction, "
            "finite-to-universal boundaries, and dependency assembly"
        ),
        "zero_gap_rule": "a verified verdict requires every interface field to be true",
    }


def philosophy_signature(action: Mapping[str, Any]) -> tuple[str, ...]:
    family = strategy_family(action)
    mode = str(action.get("mode") or "")
    worker = str(action.get("multi_branch_worker") or "")
    return tuple(item for item in (family, mode, worker) if item)


def validate_proof_interface_metadata(metadata: Mapping[str, Any]) -> list[str]:
    if int(metadata.get("proof_interface_check_version") or 0) != PROOF_INTERFACE_CHECK_VERSION:
        return []
    errors = [f"proof interface check requires {field}" for field in PROOF_INTERFACE_FIELDS if field not in metadata]
    verdict = str(metadata.get("verdict") or "").lower()
    if verdict in {"verified", "correct_no_gaps", "pass", "integrates"}:
        false_fields = [field for field in PROOF_INTERFACE_FIELDS if metadata.get(field) is not True]
        if false_fields:
            errors.append("zero-gap verdict requires true proof interface checks: " + ", ".join(false_fields))
    return errors


def validate_theorem_adaptation_metadata(metadata: Mapping[str, Any]) -> list[str]:
    if int(metadata.get("theorem_adaptation_version") or 0) != THEOREM_ADAPTATION_VERSION:
        return []
    errors: list[str] = []
    for field in THEOREM_ADAPTATION_FIELDS:
        if field not in metadata or metadata.get(field) in (None, "", {}):
            if field == "missing_hypotheses" and isinstance(metadata.get(field), list):
                continue
            errors.append(f"theorem adaptation packet requires {field}")
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
