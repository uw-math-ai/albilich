from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from .models import fingerprint_text, json_loads, normalize_text


STRATEGY_SCHEMA_VERSION = 1
STRATEGIC_ARTIFACT_TYPES = {
    "advisor_synthesis",
    "bridge_lemma_search",
    "conjecture_portfolio",
    "deep_session_report",
    "definition_candidate",
    "invention_authorization",
    "proof_compression",
}
STRATEGIC_MARKDOWN_ARTIFACT_TYPES = set(STRATEGIC_ARTIFACT_TYPES)
BRIDGE_STATUSES = {"proposed", "prechecked", "selected", "viable", "rejected", "proved", "refuted"}
CONJECTURE_STATUSES = {"candidate", "selected", "archived", "proved", "refuted"}
CONJECTURE_CATEGORIES = {
    "bridge_conjecture",
    "equivalent_reformulation",
    "sharp_special_case",
    "minimal_counterexample_necessary_condition",
    "structural_explanation",
}
DEFINITION_LIFECYCLE = {
    "experimental_definition",
    "well_defined",
    "mathematically_nontrivial",
    "proof_relevant",
    "adopted",
    "rejected",
}
EXPERIMENT_REQUIRED_FIELDS = (
    "mathematical_question",
    "competing_hypotheses",
    "finite_scope",
    "backend_or_manual_method",
    "code_or_calculation",
    "expected_decisive_outputs",
    "observations",
    "counterexamples",
    "interpretation",
    "next_proof_move",
)
ADVISOR_SYNTHESIS_REQUIRED_FIELDS = (
    "exact_root_status",
    "verified_core",
    "best_route",
    "best_route_summary",
    "shortest_plausible_proof_skeleton",
    "decisive_missing_statement",
    "alternate_routes",
    "routes_to_continue",
    "routes_to_pause",
    "routes_to_abandon",
    "duplicated_or_stagnant_work",
    "evidence_that_would_change_strategy",
    "recommended_next_actions",
    "budget_distribution",
    "synthesis_confidence",
)
PROOF_COMPRESSION_SKELETON_REQUIRED_FIELDS = (
    "root",
    "essential_verified_facts",
    "essential_routes",
    "unresolved_bridges",
    "conditional_steps",
    "unused_or_low_value_branches",
    "shortest_known_route",
    "weakest_sufficient_new_statement",
)
INVENTION_CONDITION_KEYS = (
    "distinct_routes_share_obstruction",
    "bridge_search_exhausted",
    "literature_search_exhausted",
    "existing_language_insufficient",
    "examples_suggest_hidden_structure",
    "required_behavior_stated",
)
METHOD_CARD_PATH = Path(__file__).with_name("method_cards.json")
_METHOD_CARD_CACHE: Optional[list[Dict[str, Any]]] = None


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    decoded = json_loads(value, {})
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    decoded = json_loads(value, []) if isinstance(value, str) else []
    return list(decoded) if isinstance(decoded, list) else []


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(str(item or "").strip() for item in value)


def _artifact_rows(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = state.get("research_artifacts")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, Mapping)]
    rows = state.get("artifacts")
    return [row for row in rows or [] if isinstance(row, Mapping)]


def _artifact_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    return _json_object(row.get("metadata_json") if "metadata_json" in row else row.get("metadata"))


def _artifact_sort_key(row: Mapping[str, Any]) -> tuple[int, str, str]:
    return (
        int(row.get("state_revision") or 0),
        str(row.get("created_at") or ""),
        str(row.get("artifact_id") or ""),
    )


def latest_artifact(state: Mapping[str, Any], artifact_type: str) -> Optional[Dict[str, Any]]:
    rows = [row for row in _artifact_rows(state) if str(row.get("artifact_type") or "") == artifact_type]
    if not rows:
        return None
    row = dict(max(rows, key=_artifact_sort_key))
    row["metadata"] = _artifact_metadata(row)
    return row


def load_method_cards() -> list[Dict[str, Any]]:
    global _METHOD_CARD_CACHE
    if _METHOD_CARD_CACHE is None:
        payload = json.loads(METHOD_CARD_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("method_cards.json must contain a list")
        _METHOD_CARD_CACHE = [dict(card) for card in payload if isinstance(card, Mapping)]
    return [dict(card) for card in _METHOD_CARD_CACHE]


_STRUCTURAL_CUE_GROUPS: Dict[str, tuple[str, ...]] = {
    "local_data": ("local choice", "on each piece", "at every place", "fiberwise", "locally"),
    "global_assembly": ("global object", "assemble", "glue", "patch together", "globalize"),
    "compatibility_obstruction": ("compatibility fails", "does not glue", "do not glue", "obstruction", "inconsistent overlaps"),
    "minimal_counterexample": ("smallest counterexample", "minimal counterexample", "least counterexample", "minimal bad"),
    "natural_reduction": ("quotient", "delete", "contract", "reduce", "smaller object", "proper subobject"),
    "inductive_closure": ("induction", "well founded", "preserves failure", "minimality"),
    "extremal_object": ("maximizer", "minimizer", "extremal", "optimal configuration", "largest possible"),
    "sharp_bound": ("sharp bound", "best constant", "optimal inequality", "upper bound", "lower bound"),
    "equality_case": ("equality case", "when equality", "near equality", "rigidity"),
    "family_parameter": ("one parameter", "family", "deform", "vary continuously", "specialize"),
    "special_fiber": ("special fiber", "limit object", "degeneration", "boundary member"),
    "property_transport": ("semicontinu", "transport back", "preserved under specialization", "generic fiber"),
    "forms_or_torsors": ("form of", "torsor", "becomes isomorphic", "after extension"),
    "symmetry_action": ("galois action", "automorphism action", "symmetry action", "equivariant"),
    "descent_data": ("descent", "cocycle", "twist", "base field", "compatibility equation"),
    "proof_invariant": ("invariant", "filtration", "valuation", "rank", "monotone quantity"),
    "natural_operations": ("under quotient", "under product", "under extension", "under deletion", "natural operation"),
    "monotonicity_or_stability": ("monotone", "stable under", "transformation law", "does not increase", "does not decrease"),
}


def structural_signature(text: str) -> list[str]:
    normalized = " ".join(str(text or "").lower().replace("-", " ").split())
    features: list[str] = []
    for feature, cues in _STRUCTURAL_CUE_GROUPS.items():
        if any(cue in normalized for cue in cues):
            features.append(feature)
    return features


def retrieve_method_cards(text: str, *, limit: int = 3) -> list[Dict[str, Any]]:
    query_features = set(structural_signature(text))
    if not query_features:
        return []
    ranked: list[tuple[float, str, Dict[str, Any]]] = []
    for card in load_method_cards():
        signature = set(str(item) for item in card.get("structural_signature", []))
        overlap = len(query_features & signature)
        if not overlap:
            continue
        coverage = overlap / max(1, len(signature))
        precision = overlap / max(1, len(query_features))
        score = round(0.65 * coverage + 0.35 * precision, 4)
        ranked.append((score, str(card.get("method_id") or ""), card))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    results: list[Dict[str, Any]] = []
    for score, _, card in ranked[: max(0, limit)]:
        results.append(
            {
                **card,
                "structural_match_score": score,
                "matched_structural_features": sorted(query_features & set(card.get("structural_signature", []))),
                "advisory_only": True,
            }
        )
    return results


def _route_for_id(state: Mapping[str, Any], route_id: str) -> Dict[str, Any]:
    return next((dict(row) for row in state.get("routes", []) if str(row.get("route_id") or "") == route_id), {})


def _claim_for_id(state: Mapping[str, Any], claim_id: str) -> Dict[str, Any]:
    return next((dict(row) for row in state.get("claims", []) if str(row.get("claim_id") or "") == claim_id), {})


def _relevant_debts(state: Mapping[str, Any], target_id: str, route_id: str) -> list[Mapping[str, Any]]:
    claim_ids = {target_id, "root"}
    route = _route_for_id(state, route_id)
    if route:
        claim_ids.add(str(route.get("conclusion_claim_id") or ""))
    rows = []
    for debt in state.get("debts", []):
        if str(debt.get("status") or "active") != "active":
            continue
        owner_id = str(debt.get("owner_id") or "")
        suggested = str(debt.get("suggested_next_target") or "")
        if not route_id or owner_id in claim_ids or owner_id == route_id or suggested in claim_ids:
            rows.append(debt)
    rows.sort(
        key=lambda row: (
            0 if str(row.get("severity") or "") == "blocking" else 1,
            -int(row.get("repeated_count") or 0),
            str(row.get("debt_id") or ""),
        )
    )
    return rows


def bridge_frontier_context(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    target_id = str(action.get("target_id") or "root")
    route_id = str(action.get("route_id") or "")
    verified = []
    for claim in state.get("claims", []):
        if str(claim.get("validation_status") or "") not in {"informally_verified", "formally_verified"} and str(
            claim.get("lifecycle_status") or ""
        ) != "integrated":
            continue
        verified.append(
            {
                "claim_id": str(claim.get("claim_id") or ""),
                "statement": str(claim.get("statement") or ""),
                "root_impact": float(claim.get("root_impact") or 0.0),
            }
        )
    verified.sort(key=lambda item: (-item["root_impact"], item["claim_id"]))
    debts = _relevant_debts(state, target_id, route_id)
    compression = latest_artifact(state, "proof_compression")
    compression_meta = compression.get("metadata", {}) if compression else {}
    skeleton = _json_object(compression_meta.get("minimal_proof_skeleton"))
    weakest = str(skeleton.get("weakest_sufficient_new_statement") or "")
    backward = [
        {
            "debt_id": str(debt.get("debt_id") or ""),
            "obligation": str(debt.get("obligation") or ""),
            "severity": str(debt.get("severity") or ""),
        }
        for debt in debts[:6]
    ]
    if weakest and all(weakest != item["obligation"] for item in backward):
        backward.insert(0, {"debt_id": "compression-weakest-bridge", "obligation": weakest, "severity": "blocking"})
    root_statement = str(state.get("problem_state", {}).get("root_statement") or "")
    method_query = " ".join(
        [root_statement, str(_route_for_id(state, route_id).get("strategy") or ""), *(item["obligation"] for item in backward)]
    )
    return {
        "forward_frontier": verified[:8],
        "backward_frontier": backward[:7],
        "target_id": target_id,
        "target_route_id": route_id,
        "root_statement": root_statement,
        "maximum_candidates": 3,
        "maximum_selected": 2,
        "sufficiency_precheck_required": True,
        "selection_policy": "prefer the smallest candidate that materially reduces obligations and would close the route",
        "existing_statement_fingerprints": sorted(
            {
                str(claim.get("fingerprint") or fingerprint_text(str(claim.get("statement") or "")))
                for claim in state.get("claims", [])
                if str(claim.get("statement") or "").strip()
            }
        )[:40],
        "retrieved_method_cards": retrieve_method_cards(method_query, limit=3),
    }


def _bridge_candidates(metadata: Mapping[str, Any]) -> list[Dict[str, Any]]:
    raw = metadata.get("bridge_candidates")
    if raw is None:
        raw = _json_object(metadata.get("bridge_search")).get("candidates", [])
    return [dict(item) for item in raw or [] if isinstance(item, Mapping)]


def _conjecture_candidates(metadata: Mapping[str, Any]) -> list[Dict[str, Any]]:
    raw = metadata.get("conjectures")
    if raw is None:
        raw = _json_object(metadata.get("conjecture_portfolio")).get("candidates", [])
    return [dict(item) for item in raw or [] if isinstance(item, Mapping)]


def _bridge_rank(candidate: Mapping[str, Any]) -> tuple[float, float, float, str]:
    precheck = _json_object(candidate.get("sufficiency_precheck"))
    closes = 1.0 if precheck.get("would_reach_root") or precheck.get("would_close_route") else 0.0
    leverage = float(candidate.get("estimated_root_leverage") or 0.0)
    difficulty = float(candidate.get("estimated_difficulty") or 0.0)
    hidden = len(_json_list(candidate.get("hidden_obligations")) or _json_list(precheck.get("hidden_obligations")))
    return (closes, leverage - 0.35 * difficulty - 0.08 * hidden, leverage, str(candidate.get("bridge_id") or ""))


def _candidate_needs_experiment(candidate: Mapping[str, Any]) -> bool:
    text = " ".join(
        [
            str(candidate.get("counterexample_plan") or candidate.get("falsifiability_plan") or ""),
            *[str(item) for item in _json_list(candidate.get("possible_methods"))],
        ]
    ).lower()
    return any(term in text for term in ("cas", "compute", "experiment", "enumerat", "parameter sweep", "small example"))


def selected_bridge_candidate(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    artifact = latest_artifact(state, "bridge_lemma_search")
    if not artifact:
        return None
    selected = [candidate for candidate in _bridge_candidates(artifact["metadata"]) if str(candidate.get("status") or "") == "selected"]
    if not selected:
        return None
    selected.sort(key=_bridge_rank, reverse=True)
    return {**selected[0], "artifact_id": artifact["artifact_id"], "state_revision": artifact.get("state_revision", 0)}


def selected_conjecture_candidate(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    artifact = latest_artifact(state, "conjecture_portfolio")
    if not artifact:
        return None
    selected = [candidate for candidate in _conjecture_candidates(artifact["metadata"]) if str(candidate.get("status") or "") == "selected"]
    if not selected:
        return None
    selected.sort(
        key=lambda item: (
            -float(item.get("estimated_cost") or 0.0),
            str(item.get("conjecture_id") or ""),
        ),
        reverse=True,
    )
    return {**selected[0], "artifact_id": artifact["artifact_id"], "state_revision": artifact.get("state_revision", 0)}


def _claim_statement_fingerprints(state: Mapping[str, Any]) -> set[str]:
    return {
        str(claim.get("fingerprint") or fingerprint_text(str(claim.get("statement") or "")))
        for claim in state.get("claims", [])
        if str(claim.get("statement") or "").strip()
    }


def latest_active_advisor_synthesis(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    artifact = latest_artifact(state, "advisor_synthesis")
    if not artifact:
        return None
    metadata = artifact["metadata"]
    synthesis = _json_object(metadata.get("advisor_synthesis")) or metadata
    current_revision = int(state.get("problem_state", {}).get("current_revision") or 0)
    valid_until = int(metadata.get("valid_until_revision") or int(artifact.get("state_revision") or 0) + 20)
    if current_revision > valid_until:
        return None
    return {**artifact, "advisor_synthesis": synthesis, "valid_until_revision": valid_until}


def active_invention_authorization(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    artifact = latest_artifact(state, "invention_authorization")
    if not artifact:
        return None
    metadata = artifact["metadata"]
    current_revision = int(state.get("problem_state", {}).get("current_revision") or 0)
    authorization_revision = int(metadata.get("authorization_revision") or artifact.get("state_revision") or 0)
    max_passes = min(2, int(metadata.get("maximum_research_passes") or 0))
    passes = sum(
        1
        for run in state.get("recent_runs", [])
        if int(run.get("state_revision") or 0) >= authorization_revision
        and str(run.get("search_intent") or "") == "definition_invention"
    )
    candidates = [
        row
        for row in _artifact_rows(state)
        if str(row.get("artifact_type") or "") == "definition_candidate"
        and str(_artifact_metadata(row).get("authorization_artifact_id") or "") == str(artifact.get("artifact_id") or "")
    ]
    if passes >= max_passes or len(candidates) >= min(2, int(metadata.get("maximum_candidates") or 0)):
        return None
    if current_revision < authorization_revision:
        return None
    return {**artifact, "passes_used": passes, "candidate_count": len(candidates)}


def advisor_synthesis_trigger(state: Mapping[str, Any]) -> Dict[str, Any]:
    latest = latest_artifact(state, "advisor_synthesis")
    latest_revision = int(latest.get("state_revision") or -1) if latest else -1
    current_revision = int(state.get("problem_state", {}).get("current_revision") or 0)
    recent_runs = [
        row
        for row in state.get("recent_runs", [])
        if int(row.get("state_revision") or 0) >= latest_revision
        and str(row.get("actor_role") or "") in {"researcher", "villain", "literature_researcher", "strict_informal_verifier"}
    ]
    artifact_by_id = {str(row.get("artifact_id") or ""): row for row in _artifact_rows(state)}

    def root_progress(run: Mapping[str, Any]) -> bool:
        for artifact_id in _json_list(run.get("output_artifact_ids_json")):
            metadata = _artifact_metadata(artifact_by_id.get(str(artifact_id), {}))
            if str(metadata.get("artifact_roi") or "") in {
                "verifier_ready_route",
                "route_repaired",
                "debt_closed_or_sharpened",
            }:
                return True
            if bool(metadata.get("root_relevant_fact_added")):
                return True
        return False

    substantive = [
        run
        for run in recent_runs
        if str(run.get("mode") or "") in {"prove", "reduce", "refute", "retrieve", "synthesize_sources", "strengthen"}
        and str(run.get("status") or "").lower() not in {"failed", "error", "cancelled"}
    ]
    reasons: list[str] = []
    if len(substantive) >= 3 and not any(root_progress(run) for run in substantive[:3]):
        reasons.append("three_substantive_passes_without_root_relevant_fact")
    obstruction_routes: Dict[str, set[str]] = {}
    for route in state.get("routes", []):
        fingerprint = str(route.get("failure_fingerprint") or "")
        if fingerprint and str(route.get("status") or "") in {"active", "blocked"}:
            obstruction_routes.setdefault(fingerprint, set()).add(str(route.get("route_id") or ""))
    if any(len(route_ids) >= 2 for route_ids in obstruction_routes.values()):
        reasons.append("multiple_routes_share_obstruction")
    active_claims = [claim for claim in state.get("claims", []) if str(claim.get("lifecycle_status") or "") == "active"]
    verified_claims = [
        claim
        for claim in state.get("claims", [])
        if str(claim.get("validation_status") or "") in {"informally_verified", "formally_verified"}
    ]
    if len(substantive) >= 3 and len(active_claims) >= max(8, 3 * max(1, len(verified_claims))):
        reasons.append("active_claim_growth_without_verified_core_growth")
    bridge = latest_artifact(state, "bridge_lemma_search")
    if bridge and int(bridge.get("state_revision") or 0) >= latest_revision:
        if any(str(candidate.get("status") or "") == "refuted" for candidate in _bridge_candidates(bridge["metadata"])):
            reasons.append("central_bridge_refuted")
    verifier_rejections = [
        run
        for run in recent_runs
        if str(run.get("actor_role") or "") == "strict_informal_verifier"
        and str(run.get("status") or "").lower() in {"rejected", "failed", "wrong"}
    ]
    if len(verifier_rejections) >= 2:
        reasons.append("repeated_verifier_rejection_is_strategic")
    if len(substantive) >= 15:
        reasons.append("meaningful_action_cadence")
    if latest:
        valid_until = int(latest["metadata"].get("valid_until_revision") or latest_revision + 12)
        major_new_event = "central_bridge_refuted" in reasons or any(
            int(run.get("state_revision") or 0) > latest_revision for run in verifier_rejections
        )
        if current_revision <= valid_until and not major_new_event:
            reasons = []
    return {
        "due": bool(reasons),
        "reasons": reasons,
        "latest_synthesis_artifact_id": str(latest.get("artifact_id") or "") if latest else "",
        "latest_synthesis_revision": latest_revision,
        "substantive_actions_since_synthesis": len(substantive),
    }


def _compression_is_fresh_for_trigger(state: Mapping[str, Any], trigger: Mapping[str, Any]) -> bool:
    compression = latest_artifact(state, "proof_compression")
    if not compression:
        return False
    return int(compression.get("state_revision") or 0) >= int(trigger.get("latest_synthesis_revision") or -1)


def _compression_would_help(state: Mapping[str, Any]) -> bool:
    return len(state.get("claims", [])) >= 5 or len(state.get("routes", [])) >= 2 or len(state.get("debts", [])) >= 4


def _protected_primary_action(action: Mapping[str, Any]) -> bool:
    mode = str(action.get("mode") or "")
    if mode in {"integrate", "formalize", "validate_counterexample", "write", "review_writing", "stop_solved", "stop_with_partial_results"}:
        return True
    if mode == "prove" and (action.get("route_id") or action.get("citation_certification_required") or action.get("citation_triage_required")):
        return True
    if mode in {"triage_routes", "regulate_decomposition"}:
        return True
    return bool(
        action.get("proof_repair_verification_required")
        or action.get("proof_repair_required")
        or action.get("root_alignment_audit")
        or action.get("debt_id")
        or action.get("parallel_wave_summary")
        or action.get("retrieve_reduce_loop_guard")
        or action.get("research_synthesis_required")
        or action.get("global_synthesis_required")
        or action.get("advisor_evidence_synthesis_required")
    )


def next_strategy_operation(state: Mapping[str, Any], primary_action: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if _protected_primary_action(primary_action):
        return None
    fingerprints = _claim_statement_fingerprints(state)
    bridge = selected_bridge_candidate(state)
    if bridge and fingerprint_text(str(bridge.get("statement") or "")) not in fingerprints:
        return {
            "operation": "experiment" if _candidate_needs_experiment(bridge) else "bridge_promotion",
            "mode": "reduce",
            "target_id": str(primary_action.get("target_id") or "root"),
            "route_id": str(bridge.get("target_route_id") or primary_action.get("route_id") or ""),
            "search_intent": "experiment_conjecture_proof" if _candidate_needs_experiment(bridge) else "selected_bridge_promotion",
            "reason": "selected bridge candidate outranks unrelated decomposition because it has passed a root-sufficiency precheck",
            "selected_bridge": bridge,
            "experiment_workflow_required": _candidate_needs_experiment(bridge),
            "selected_bridge_promotion_required": not _candidate_needs_experiment(bridge),
            "preferred_work_mode": "cas" if _candidate_needs_experiment(bridge) else "offline",
        }
    conjecture = selected_conjecture_candidate(state)
    if conjecture and fingerprint_text(str(conjecture.get("statement") or "")) not in fingerprints:
        experiment = _candidate_needs_experiment(conjecture)
        return {
            "operation": "experiment" if experiment else "conjecture_proof",
            "mode": "reduce",
            "target_id": str(primary_action.get("target_id") or "root"),
            "route_id": str(primary_action.get("route_id") or ""),
            "search_intent": "experiment_conjecture_proof" if experiment else "selected_conjecture_proof",
            "reason": "a bounded selected conjecture is more root-relevant than arbitrary new decomposition",
            "selected_conjecture": conjecture,
            "experiment_workflow_required": experiment,
            "selected_conjecture_proof_required": not experiment,
            "preferred_work_mode": "cas" if experiment else "offline",
        }
    trigger = advisor_synthesis_trigger(state)
    if trigger.get("due"):
        if _compression_would_help(state) and not _compression_is_fresh_for_trigger(state, trigger):
            return {
                "operation": "proof_compression",
                "mode": "reduce",
                "target_id": "root",
                "route_id": str(primary_action.get("route_id") or ""),
                "search_intent": "active_proof_compression",
                "reason": "compress the current proof architecture before the due global advisor synthesis",
                "proof_compression_operation_required": True,
                "proof_spine_mode_required": True,
                "synthesis_trigger": trigger,
                "preferred_work_mode": "offline",
            }
        return {
            "operation": "advisor_global_synthesis",
            "mode": "triage_routes",
            "target_id": "root",
            "route_id": str(primary_action.get("route_id") or ""),
            "search_intent": "advisor_global_synthesis",
            "reason": "persisted research-state triggers require a global PhD-advisor synthesis",
            "advisor_global_synthesis_required": True,
            "global_synthesis_required": True,
            "synthesis_trigger": trigger,
        }
    authorization = active_invention_authorization(state)
    if authorization:
        return {
            "operation": "definition_invention",
            "mode": "reduce",
            "target_id": str(primary_action.get("target_id") or "root"),
            "route_id": str(primary_action.get("route_id") or ""),
            "search_intent": "definition_invention",
            "reason": "a bounded PhD-advisor authorization permits one exceptional auxiliary-object invention pass",
            "definition_invention_required": True,
            "invention_authorization": {
                "artifact_id": authorization.get("artifact_id", ""),
                **authorization.get("metadata", {}),
                "passes_used": authorization.get("passes_used", 0),
                "candidate_count": authorization.get("candidate_count", 0),
            },
            "preferred_work_mode": "offline",
        }
    return None


def _target_root_impact(state: Mapping[str, Any], target_id: str) -> float:
    claim = _claim_for_id(state, target_id)
    if claim:
        return float(claim.get("root_impact") or (1.0 if target_id == "root" else 0.4))
    return 1.0 if target_id == "root" else 0.4


def score_action(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    mode = str(action.get("mode") or "")
    target_id = str(action.get("target_id") or "root")
    search_intent = str(action.get("search_intent") or "")
    is_experiment = bool(action.get("experiment_workflow_required")) or search_intent == "experiment_conjecture_proof"
    is_verification = mode in {"integrate", "formalize", "validate_counterexample"} or (mode == "prove" and bool(action.get("route_id")))
    closing = 0.92 if is_verification else 0.62 if target_id == "root" and mode in {"prove", "reduce"} else 0.42
    if action.get("selected_bridge_promotion_required"):
        closing = 0.76
    refuting = 0.82 if is_experiment else 0.55 if mode == "refute" else 0.18
    root_progress = min(1.0, max(0.0, _target_root_impact(state, target_id)))
    information = 0.9 if is_experiment else 0.76 if mode in {"triage_routes", "regulate_decomposition"} else 0.58
    reuse = 0.85 if action.get("proof_compression_operation_required") else 0.68 if action.get("advisor_global_synthesis_required") else 0.35
    duplicate_count = sum(
        1
        for run in state.get("recent_runs", [])[:8]
        if str(run.get("target_id") or "") == target_id
        and str(run.get("search_intent") or "") == search_intent
        and search_intent
    )
    duplication = min(1.0, duplicate_count / 3.0)
    budget = _json_object(action.get("budget"))
    requested = float(action.get("requested_tokens") or budget.get("requested_tokens") or budget.get("planned_tokens") or 0.0)
    token_cost = min(1.0, requested / 250_000.0) if requested else 0.25
    wall_cost = 0.8 if is_experiment else 0.55 if action.get("deep_session_required") else 0.3
    verification_cost = 0.15 if is_verification else 0.55 if action.get("definition_invention_required") else 0.35
    score = (
        1.6 * closing
        + 1.25 * refuting
        + 1.8 * root_progress
        + 1.35 * information
        + 0.55 * reuse
        - 1.25 * duplication
        - 0.45 * token_cost
        - 0.25 * wall_cost
        - 0.4 * verification_cost
    )
    return {
        "probability_of_closing_bottleneck": round(closing, 3),
        "probability_of_refuting_route": round(refuting, 3),
        "expected_root_progress": round(root_progress, 3),
        "expected_information_gain": round(information, 3),
        "reuse_value": round(reuse, 3),
        "duplication_risk": round(duplication, 3),
        "token_cost": round(token_cost, 3),
        "wall_time_cost": round(wall_cost, 3),
        "verification_cost": round(verification_cost, 3),
        "expected_value_score": round(score, 4),
        "heuristic_not_calibrated_probability": True,
        "rotation_tie_break_rule": "when scores differ by at most 0.25, prefer the least-recent researcher work mode",
        "protected_verification_budget": "never charged to speculative research actions",
    }


def _deep_session_context(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    mode = str(action.get("mode") or "")
    if mode not in {"prove", "reduce", "strengthen", "weaken"}:
        return {}
    if action.get("retrieval_required") or action.get("citation_triage_required"):
        return {}
    target_id = str(action.get("target_id") or "root")
    route_id = str(action.get("route_id") or "")
    leverage = _target_root_impact(state, target_id)
    repeated = sum(
        1
        for run in state.get("recent_runs", [])[:10]
        if str(run.get("target_id") or "") == target_id
        and str(run.get("actor_role") or "") == "researcher"
    )
    eligible_reason = ""
    if action.get("selected_bridge_promotion_required") or action.get("bridge_lemma_workbench_required"):
        eligible_reason = "central_bridge_lemma"
    elif action.get("source_adaptation_digest_required"):
        eligible_reason = "difficult_source_adaptation"
    elif action.get("near_solution_spine_synthesis_required") or action.get("global_synthesis_required"):
        eligible_reason = "route_close_to_integration"
    elif repeated >= 3 and leverage >= 0.7:
        eligible_reason = "high_leverage_bottleneck_survived_short_passes"
    elif action.get("deep_research_required") and leverage >= 0.7:
        eligible_reason = "high_estimated_root_leverage"
    if not eligible_reason:
        return {}
    debts = _relevant_debts(state, target_id, route_id)
    synthesis = latest_active_advisor_synthesis(state)
    return {
        "eligible": True,
        "eligibility_reason": eligible_reason,
        "exact_local_target": target_id,
        "route_id": route_id,
        "relation_to_root": "root" if target_id == "root" else f"root_impact={leverage:.3f}",
        "verified_supporting_claim_ids": [
            str(claim.get("claim_id") or "")
            for claim in state.get("claims", [])
            if str(claim.get("validation_status") or "") in {"informally_verified", "formally_verified"}
        ][:12],
        "active_debt_ids": [str(debt.get("debt_id") or "") for debt in debts[:8]],
        "latest_advisor_synthesis_artifact_id": str(synthesis.get("artifact_id") or "") if synthesis else "",
        "branch_budget_policy": "one coherent long session; ordinary patch and verification gates still apply",
        "required_deliverable": {
            "artifact_type": "deep_session_report",
            "strategy_schema_version": STRATEGY_SCHEMA_VERSION,
            "fields": [
                "strategy_schema_version",
                "complete_local_argument",
                "candidate_lemmas",
                "failed_approaches",
                "new_obstructions",
                "source_adaptations",
                "proposed_route_revision",
                "next_decisive_step",
                "state_patch_operations",
            ],
            "field_rules": {
                "candidate_lemmas": "nonempty list; include at least one exact local lemma, hypothesis, or falsifiable subclaim from this session",
                "failed_approaches": "nonempty list",
                "new_obstructions": "nonempty list",
                "source_adaptations": "list; may be empty in an offline session",
                "state_patch_operations": "nonempty list",
            },
        },
        "verification_authority": False,
        "unrelated_result_directories_forbidden": True,
    }


def enrich_action(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    enriched = dict(action)
    bridge_like = bool(enriched.get("bridge_lemma_workbench_required")) or "bridge" in str(
        enriched.get("reason") or ""
    ).lower()
    if bridge_like:
        frontier = bridge_frontier_context(state, enriched)
        latest_bridge = latest_artifact(state, "bridge_lemma_search")
        recent_for_same_target = bool(
            latest_bridge
            and str(latest_bridge["metadata"].get("target_id") or "root") == str(enriched.get("target_id") or "root")
            and int(latest_bridge.get("state_revision") or 0)
            >= int(state.get("problem_state", {}).get("current_revision") or 0) - 4
        )
        enriched["bidirectional_bridge_search_required"] = not recent_for_same_target
        enriched["bridge_search_context"] = frontier
        enriched["bridge_candidate_limit"] = 3
        enriched["bridge_selection_limit"] = 2
    synthesis = latest_active_advisor_synthesis(state)
    if synthesis:
        advisor = synthesis["advisor_synthesis"]
        enriched["advisor_synthesis_artifact_id"] = str(synthesis.get("artifact_id") or "")
        enriched["advisor_synthesis_revision"] = int(synthesis.get("state_revision") or 0)
        enriched["advisor_decisive_missing_statement"] = str(advisor.get("decisive_missing_statement") or "")
        enriched["advisor_best_route"] = str(advisor.get("best_route") or "")
    query = " ".join(
        [
            str(state.get("problem_state", {}).get("root_statement") or ""),
            str(enriched.get("reason") or ""),
            *[str(debt.get("obligation") or "") for debt in _relevant_debts(state, str(enriched.get("target_id") or "root"), str(enriched.get("route_id") or ""))[:4]],
        ]
    )
    methods = retrieve_method_cards(query, limit=3)
    if methods:
        enriched["method_card_ids"] = [str(card.get("method_id") or "") for card in methods]
        enriched["method_retrieval_structural_features"] = sorted(
            {feature for card in methods for feature in card.get("matched_structural_features", [])}
        )
        enriched["method_cards_are_proof_evidence"] = False
    deep = _deep_session_context(state, enriched)
    if deep:
        enriched["deep_session_required"] = True
        enriched["deep_session"] = deep
    enriched["information_gain_score"] = score_action(state, enriched)
    return enriched


def apply_active_compression(
    state: Mapping[str, Any], selected_claim_ids: Sequence[str], *, target_id: str
) -> tuple[list[str], Dict[str, Any]]:
    compression = latest_artifact(state, "proof_compression")
    if not compression:
        return list(selected_claim_ids), {}
    skeleton = _json_object(compression["metadata"].get("minimal_proof_skeleton"))
    essential = {str(item) for item in _json_list(skeleton.get("essential_verified_facts")) if str(item)}
    if not essential:
        return list(selected_claim_ids), {}
    keep = {"root", target_id, *essential}
    compressed = [claim_id for claim_id in selected_claim_ids if claim_id in keep]
    for mandatory in ("root", target_id):
        if mandatory in selected_claim_ids and mandatory not in compressed:
            compressed.append(mandatory)
    return compressed, {
        "source_artifact_id": str(compression.get("artifact_id") or ""),
        "before_claim_count": len(selected_claim_ids),
        "after_claim_count": len(compressed),
        "history_preserved": True,
        "weakest_sufficient_new_statement": str(skeleton.get("weakest_sufficient_new_statement") or ""),
    }


def strategy_context_card(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    synthesis = latest_active_advisor_synthesis(state)
    compression = latest_artifact(state, "proof_compression")
    bridge = selected_bridge_candidate(state)
    conjecture = selected_conjecture_candidate(state)
    authorization = active_invention_authorization(state)
    query = " ".join(
        [
            str(state.get("problem_state", {}).get("root_statement") or ""),
            str(action.get("reason") or ""),
            *[str(debt.get("obligation") or "") for debt in state.get("debts", [])[:6]],
        ]
    )
    return {
        "memory_separation": {
            "verified_problem_facts": "claims/inferences accepted by verifiers",
            "external_theorems": "retrieval cards and theorem-library entries",
            "strategic_method_cards": "developer-curated advisory cards; never proof premises",
            "private_speculation": "local candidate artifacts; never exported into cross-user learning",
        },
        "latest_advisor_synthesis": (
            {
                "artifact_id": synthesis.get("artifact_id", ""),
                "state_revision": synthesis.get("state_revision", 0),
                "valid_until_revision": synthesis.get("valid_until_revision", 0),
                "advisor_synthesis": synthesis.get("advisor_synthesis", {}),
            }
            if synthesis
            else {}
        ),
        "latest_proof_compression": (
            {"artifact_id": compression.get("artifact_id", ""), **compression.get("metadata", {})}
            if compression
            else {}
        ),
        "selected_bridge": bridge or {},
        "selected_conjecture": conjecture or {},
        "active_invention_authorization": (
            {"artifact_id": authorization.get("artifact_id", ""), **authorization.get("metadata", {})}
            if authorization
            else {}
        ),
        "retrieved_method_cards": retrieve_method_cards(query, limit=3),
        "experiment_conjecture_proof_contract": {
            "experiment_workflow_version": STRATEGY_SCHEMA_VERSION,
            "required_fields": list(EXPERIMENT_REQUIRED_FIELDS),
            "raw_output_is_not_progress": True,
            "infinite_statement_requires_verified_finite_reduction": True,
            "decision_changed_required": True,
        },
        "action_information_gain_score": dict(action.get("information_gain_score") or {}),
        "deep_session": dict(action.get("deep_session") or {}),
    }


def strategy_observability(state: Mapping[str, Any], action: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    synthesis = latest_artifact(state, "advisor_synthesis")
    compression = latest_artifact(state, "proof_compression")
    bridge_artifact = latest_artifact(state, "bridge_lemma_search")
    conjecture_artifact = latest_artifact(state, "conjecture_portfolio")
    authorization = active_invention_authorization(state)
    bridge_candidates = _bridge_candidates(bridge_artifact["metadata"]) if bridge_artifact else []
    conjectures = _conjecture_candidates(conjecture_artifact["metadata"]) if conjecture_artifact else []
    selected_bridge = next((item for item in bridge_candidates if str(item.get("status") or "") == "selected"), {})
    selected_conjecture = next((item for item in conjectures if str(item.get("status") or "") == "selected"), {})
    return {
        "latest_advisor_synthesis_artifact_id": str(synthesis.get("artifact_id") or "") if synthesis else "",
        "latest_proof_compression_artifact_id": str(compression.get("artifact_id") or "") if compression else "",
        "latest_bridge_search_artifact_id": str(bridge_artifact.get("artifact_id") or "") if bridge_artifact else "",
        "bridge_candidate_count": len(bridge_candidates),
        "selected_bridge_id": str(selected_bridge.get("bridge_id") or ""),
        "selected_bridge_reason": str(selected_bridge.get("selection_reason") or ""),
        "latest_conjecture_portfolio_artifact_id": str(conjecture_artifact.get("artifact_id") or "") if conjecture_artifact else "",
        "conjecture_candidate_count": len(conjectures),
        "selected_conjecture_id": str(selected_conjecture.get("conjecture_id") or ""),
        "active_invention_authorization_artifact_id": str(authorization.get("artifact_id") or "") if authorization else "",
        "information_gain_score": dict((action or {}).get("information_gain_score") or {}),
        "advisor_synthesis_trigger": advisor_synthesis_trigger(state),
    }


def _require_fields(payload: Mapping[str, Any], fields: Iterable[str], *, prefix: str) -> list[str]:
    errors = []
    for field in fields:
        value = payload.get(field)
        if value in (None, "") or value == [] or value == {}:
            errors.append(f"{prefix} requires nonempty {field}")
    return errors


def _validate_bridge_metadata(metadata: Mapping[str, Any], conn: sqlite3.Connection) -> list[str]:
    candidates = _bridge_candidates(metadata)
    errors: list[str] = []
    if not 1 <= len(candidates) <= 3:
        errors.append("bridge_lemma_search requires one to three bridge_candidates")
        return errors
    ids: set[str] = set()
    fingerprints: set[str] = set()
    existing_claim_fingerprints = {str(row[0]) for row in conn.execute("SELECT fingerprint FROM claims").fetchall()}
    viable: list[Dict[str, Any]] = []
    selected: list[Dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        prefix = f"bridge_candidates[{index}]"
        errors.extend(
            _require_fields(
                candidate,
                (
                    "bridge_id",
                    "statement",
                    "forward_support",
                    "target_route_id",
                    "root_consequence",
                    "possible_methods",
                    "falsifiability_plan",
                    "status",
                    "sufficiency_precheck",
                ),
                prefix=prefix,
            )
        )
        bridge_id = str(candidate.get("bridge_id") or "")
        if bridge_id in ids:
            errors.append(f"duplicate bridge_id: {bridge_id}")
        ids.add(bridge_id)
        fingerprint = fingerprint_text(str(candidate.get("statement") or ""))
        if fingerprint in fingerprints:
            errors.append(f"duplicate bridge statement in one search: {bridge_id}")
        fingerprints.add(fingerprint)
        status = str(candidate.get("status") or "")
        if status not in BRIDGE_STATUSES:
            errors.append(f"{prefix} has invalid status {status}")
        precheck = _json_object(candidate.get("sufficiency_precheck"))
        for key in ("materially_reduces_gap", "would_reach_root", "restates_root", "creates_more_severe_obligations"):
            if key not in precheck:
                errors.append(f"{prefix}.sufficiency_precheck requires {key}")
        duplicate_active = fingerprint in existing_claim_fingerprints
        if duplicate_active and status != "rejected":
            errors.append(f"{prefix} duplicates an existing claim and must be rejected")
        material = bool(precheck.get("materially_reduces_gap"))
        valid = (
            material
            and not bool(precheck.get("restates_root"))
            and not bool(precheck.get("creates_more_severe_obligations"))
            and _nonempty_list(candidate.get("possible_methods"))
            and not duplicate_active
        )
        if not valid and status not in {"rejected", "refuted"}:
            errors.append(f"{prefix} fails a guardrail and must be rejected")
        if valid:
            viable.append(candidate)
        if status == "selected":
            selected.append(candidate)
    if len(selected) > 2:
        errors.append("bridge_lemma_search may select at most two candidates")
    if viable and not selected:
        errors.append("bridge_lemma_search must select one or two viable candidates")
    if selected:
        ranked = sorted(viable, key=_bridge_rank, reverse=True)[:2]
        ranked_ids = {str(item.get("bridge_id") or "") for item in ranked}
        if any(str(item.get("bridge_id") or "") not in ranked_ids for item in selected):
            errors.append("selected bridge candidates must be the top sufficiency-precheck candidates")
        closers = [candidate for candidate in viable if _json_object(candidate.get("sufficiency_precheck")).get("would_reach_root")]
        if closers and not any(_json_object(candidate.get("sufficiency_precheck")).get("would_reach_root") for candidate in selected):
            errors.append("a route-closing bridge must be selected over a merely interesting side lemma")
    return errors


def _validate_advisor_synthesis(metadata: Mapping[str, Any], conn: sqlite3.Connection) -> list[str]:
    synthesis = _json_object(metadata.get("advisor_synthesis")) or dict(metadata)
    errors = [
        f"advisor_synthesis requires {field}"
        for field in ADVISOR_SYNTHESIS_REQUIRED_FIELDS
        if field not in synthesis
    ]
    errors.extend(
        _require_fields(
            synthesis,
            (
                "exact_root_status",
                "verified_core",
                "best_route",
                "best_route_summary",
                "shortest_plausible_proof_skeleton",
                "decisive_missing_statement",
                "evidence_that_would_change_strategy",
                "recommended_next_actions",
                "budget_distribution",
                "synthesis_confidence",
            ),
            prefix="advisor_synthesis",
        )
    )
    for field in (
        "alternate_routes",
        "routes_to_continue",
        "routes_to_pause",
        "routes_to_abandon",
        "duplicated_or_stagnant_work",
    ):
        if field in synthesis and not isinstance(synthesis.get(field), list):
            errors.append(f"advisor_synthesis {field} must be a list")
    decisive = str(synthesis.get("decisive_missing_statement") or "").strip()
    if not decisive:
        errors.append("advisor_synthesis must identify exactly one decisive_missing_statement")
    continued = set(str(item) for item in _json_list(synthesis.get("routes_to_continue")))
    paused = set(str(item) for item in _json_list(synthesis.get("routes_to_pause")))
    abandoned = set(str(item) for item in _json_list(synthesis.get("routes_to_abandon")))
    if (continued & paused) or (continued & abandoned) or (paused & abandoned):
        errors.append("advisor_synthesis route continue/pause/abandon sets must be disjoint")
    budget = synthesis.get("budget_distribution")
    if not isinstance(budget, Mapping) or not budget:
        errors.append("advisor_synthesis budget_distribution must be a nonempty object")
    else:
        try:
            values = [float(value) for value in budget.values()]
        except (TypeError, ValueError):
            errors.append("advisor_synthesis budget_distribution values must be numeric")
        else:
            if any(value < 0.0 or value > 1.0 for value in values) or sum(values) > 1.05:
                errors.append("advisor_synthesis budget_distribution must use fractions in [0,1] summing to at most 1")
    previous = conn.execute(
        "SELECT artifact_id FROM artifacts WHERE artifact_type='advisor_synthesis' ORDER BY state_revision DESC, created_at DESC LIMIT 1"
    ).fetchone()
    if previous and str(metadata.get("supersedes_synthesis_id") or "") != str(previous["artifact_id"]):
        errors.append(f"new advisor_synthesis must supersede latest synthesis {previous['artifact_id']}")
    return errors


def _validate_invention_authorization(metadata: Mapping[str, Any], *, base_revision: int) -> list[str]:
    errors = _require_fields(
        metadata,
        (
            "shared_obstruction",
            "why_existing_language_is_insufficient",
            "required_properties",
            "maximum_candidates",
            "maximum_research_passes",
            "token_budget",
            "authorization_revision",
            "authorization_conditions",
        ),
        prefix="invention_authorization",
    )
    if metadata.get("invention_authorized") is not True:
        errors.append("invention_authorization requires invention_authorized=true")
    conditions = _json_object(metadata.get("authorization_conditions"))
    for key in INVENTION_CONDITION_KEYS:
        if conditions.get(key) is not True:
            errors.append(f"invention_authorization condition {key} must be true")
    if int(metadata.get("maximum_candidates") or 0) < 1 or int(metadata.get("maximum_candidates") or 0) > 2:
        errors.append("invention_authorization maximum_candidates must be 1 or 2")
    if int(metadata.get("maximum_research_passes") or 0) < 1 or int(metadata.get("maximum_research_passes") or 0) > 2:
        errors.append("invention_authorization maximum_research_passes must be 1 or 2")
    if int(metadata.get("token_budget") or 0) <= 0:
        errors.append("invention_authorization token_budget must be positive")
    authorization_revision = metadata.get("authorization_revision")
    if authorization_revision is None or int(authorization_revision) != int(base_revision):
        errors.append("invention_authorization authorization_revision must equal the patch base_revision")
    return errors


def _validate_definition_candidate(metadata: Mapping[str, Any], conn: sqlite3.Connection, *, base_revision: int) -> list[str]:
    errors = _require_fields(
        metadata,
        (
            "authorization_artifact_id",
            "candidate_id",
            "statement",
            "lifecycle_status",
            "evaluation_example",
            "exact_bridge_lemma",
        ),
        prefix="definition_candidate",
    )
    authorization_id = str(metadata.get("authorization_artifact_id") or "")
    row = conn.execute(
        "SELECT metadata_json, state_revision FROM artifacts WHERE artifact_id=? AND artifact_type='invention_authorization'",
        (authorization_id,),
    ).fetchone()
    if not row:
        errors.append("definition_candidate requires an existing invention_authorization artifact")
        return errors
    authorization = _json_object(row["metadata_json"])
    auth_revision = int(authorization.get("authorization_revision") or row["state_revision"] or 0)
    passes = int(
        conn.execute(
            "SELECT COUNT(*) FROM runs WHERE state_revision>=? AND search_intent='definition_invention'",
            (auth_revision,),
        ).fetchone()[0]
    )
    if passes >= min(2, int(authorization.get("maximum_research_passes") or 0)):
        errors.append("definition_candidate authorization has expired after its bounded research passes")
    count = 0
    for candidate_row in conn.execute(
        "SELECT metadata_json FROM artifacts WHERE artifact_type='definition_candidate'"
    ).fetchall():
        candidate_metadata = _json_object(candidate_row["metadata_json"])
        if str(candidate_metadata.get("authorization_artifact_id") or "") == authorization_id:
            count += 1
    if count >= min(2, int(authorization.get("maximum_candidates") or 0)):
        errors.append("definition_candidate authorization candidate limit is exhausted")
    status = str(metadata.get("lifecycle_status") or "")
    if status not in DEFINITION_LIFECYCLE:
        errors.append(f"definition_candidate has invalid lifecycle_status {status}")
    rejection_checks = _json_object(metadata.get("automatic_rejection_checks"))
    if any(rejection_checks.get(key) is True for key in ("mere_renaming", "equivalent_to_root", "creates_more_obligations", "no_advantage")) and status != "rejected":
        errors.append("definition_candidate meeting an automatic rejection condition must be rejected")
    if status == "adopted":
        lifecycle = _json_object(metadata.get("lifecycle_evidence"))
        for key in ("well_defined", "mathematically_nontrivial", "proof_relevant"):
            if lifecycle.get(key) is not True:
                errors.append(f"adopted definition_candidate requires lifecycle_evidence.{key}=true")
        if not str(metadata.get("attached_root_relevant_theorem") or "").strip():
            errors.append("adopted definition_candidate requires attached_root_relevant_theorem")
    if base_revision < auth_revision:
        errors.append("definition_candidate cannot predate its authorization")
    return errors


def _validate_conjectures(metadata: Mapping[str, Any]) -> list[str]:
    candidates = _conjecture_candidates(metadata)
    errors: list[str] = []
    if not 1 <= len(candidates) <= 3:
        return ["conjecture_portfolio requires one to three conjectures"]
    selected = 0
    fingerprints: set[str] = set()
    for index, candidate in enumerate(candidates):
        prefix = f"conjectures[{index}]"
        errors.extend(
            _require_fields(
                candidate,
                (
                    "conjecture_id",
                    "category",
                    "statement",
                    "bottleneck_id",
                    "root_utility",
                    "counterexample_plan",
                    "literature_status",
                    "estimated_cost",
                    "status",
                    "prechecks",
                ),
                prefix=prefix,
            )
        )
        category = str(candidate.get("category") or "")
        if category not in CONJECTURE_CATEGORIES:
            errors.append(f"{prefix} has invalid category {category}")
        status = str(candidate.get("status") or "")
        if status not in CONJECTURE_STATUSES:
            errors.append(f"{prefix} has invalid status {status}")
        if status == "selected":
            selected += 1
        fingerprint = fingerprint_text(str(candidate.get("statement") or ""))
        if fingerprint in fingerprints:
            errors.append(f"{prefix} duplicates another conjecture statement")
        fingerprints.add(fingerprint)
        prechecks = _json_object(candidate.get("prechecks"))
        for key in (
            "root_utility",
            "nontriviality",
            "small_examples",
            "counterexample_search",
            "literature_novelty",
            "estimated_proof_cost",
            "duplication_check",
        ):
            if key not in prechecks:
                errors.append(f"{prefix}.prechecks requires {key}")
        if not str(candidate.get("root_utility") or "").strip() and status != "archived":
            errors.append(f"{prefix} with no root utility must be archived")
        if category == "equivalent_reformulation" and (
            prechecks.get("exact_hypotheses_preserved") is not True
            or prechecks.get("exact_quantifiers_preserved") is not True
        ):
            errors.append(f"{prefix} equivalent reformulation must preserve exact hypotheses and quantifiers")
        if status == "refuted" and not str(candidate.get("negative_result_summary") or "").strip():
            errors.append(f"{prefix} refuted conjecture requires negative_result_summary")
    if selected > 2:
        errors.append("conjecture_portfolio may select at most two conjectures")
    return errors


def _validate_proof_compression(metadata: Mapping[str, Any], conn: sqlite3.Connection) -> list[str]:
    skeleton = _json_object(metadata.get("minimal_proof_skeleton"))
    errors = _require_fields(
        skeleton,
        tuple(
            field
            for field in PROOF_COMPRESSION_SKELETON_REQUIRED_FIELDS
            if field != "essential_verified_facts"
        ),
        prefix="minimal_proof_skeleton",
    )
    if "essential_verified_facts" not in skeleton or not isinstance(
        skeleton.get("essential_verified_facts"), list
    ):
        errors.append(
            "minimal_proof_skeleton requires essential_verified_facts as a list (possibly empty)"
        )
    claim_ids = {str(row[0]) for row in conn.execute("SELECT claim_id FROM claims").fetchall()}
    unknown = [str(item) for item in _json_list(skeleton.get("essential_verified_facts")) if str(item) not in claim_ids]
    if unknown:
        errors.append(f"proof_compression essential_verified_facts contains unknown claims: {unknown[:3]}")
    if metadata.get("history_preserved") is not True:
        errors.append("proof_compression requires history_preserved=true")
    return errors


def _validate_deep_session(metadata: Mapping[str, Any]) -> list[str]:
    errors = _require_fields(
        metadata,
        (
            "complete_local_argument",
            "candidate_lemmas",
            "failed_approaches",
            "new_obstructions",
            "proposed_route_revision",
            "next_decisive_step",
            "state_patch_operations",
        ),
        prefix="deep_session_report",
    )
    if "source_adaptations" not in metadata or not isinstance(metadata.get("source_adaptations"), list):
        errors.append("deep_session_report requires source_adaptations as a list (possibly empty)")
    return errors


def _validate_experiment(metadata: Mapping[str, Any]) -> list[str]:
    # Backward compatibility: pre-strategy CAS artifacts remain readable and
    # attachable. New workflow prompts stamp experiment_workflow_version=1,
    # which activates the strict decision-oriented contract.
    if not metadata.get("experiment_workflow_version"):
        return []
    errors = _require_fields(
        metadata,
        tuple(field for field in EXPERIMENT_REQUIRED_FIELDS if field != "counterexamples"),
        prefix="cas_experiment_report",
    )
    if "counterexamples" not in metadata or not isinstance(metadata.get("counterexamples"), list):
        errors.append("cas_experiment_report requires counterexamples as a list (possibly empty)")
    hypotheses = _json_list(metadata.get("competing_hypotheses"))
    if len(hypotheses) < 2:
        errors.append("cas_experiment_report requires at least two competing_hypotheses")
    if not _nonempty_list(metadata.get("expected_decisive_outputs")):
        errors.append("cas_experiment_report expected_decisive_outputs must be a nonempty list")
    if not str(metadata.get("decision_changed") or "").strip():
        errors.append("cas_experiment_report requires decision_changed explaining the research consequence")
    if metadata.get("claims_infinite_statement_verified") is True and metadata.get("complete_finite_reduction_verified") is not True:
        errors.append("CAS output cannot verify an infinite statement without complete_finite_reduction_verified=true")
    return errors


def strategic_artifact_errors(
    conn: sqlite3.Connection,
    *,
    artifact_type: str,
    metadata: Mapping[str, Any],
    actor_role: str,
    base_revision: int,
) -> list[str]:
    errors: list[str] = []
    allowed_roles = {
        "advisor_synthesis": {"phd_advisor", "advisor"},
        "invention_authorization": {"phd_advisor", "advisor"},
        "bridge_lemma_search": {"researcher"},
        "conjecture_portfolio": {"researcher", "villain"},
        "definition_candidate": {"researcher"},
        "deep_session_report": {"researcher"},
        "proof_compression": {"researcher", "phd_advisor", "advisor"},
    }
    if artifact_type in allowed_roles and actor_role not in allowed_roles[artifact_type]:
        errors.append(f"{actor_role} cannot attach {artifact_type}; expected {', '.join(sorted(allowed_roles[artifact_type]))}")
    if artifact_type in STRATEGIC_ARTIFACT_TYPES and int(metadata.get("strategy_schema_version") or 0) != STRATEGY_SCHEMA_VERSION:
        errors.append(f"{artifact_type} requires strategy_schema_version={STRATEGY_SCHEMA_VERSION}")
    if artifact_type == "bridge_lemma_search":
        errors.extend(_validate_bridge_metadata(metadata, conn))
    elif artifact_type == "advisor_synthesis":
        errors.extend(_validate_advisor_synthesis(metadata, conn))
    elif artifact_type == "invention_authorization":
        errors.extend(_validate_invention_authorization(metadata, base_revision=base_revision))
    elif artifact_type == "definition_candidate":
        errors.extend(_validate_definition_candidate(metadata, conn, base_revision=base_revision))
    elif artifact_type == "conjecture_portfolio":
        errors.extend(_validate_conjectures(metadata))
    elif artifact_type == "proof_compression":
        errors.extend(_validate_proof_compression(metadata, conn))
    elif artifact_type == "deep_session_report":
        errors.extend(_validate_deep_session(metadata))
    elif artifact_type == "cas_experiment_report":
        errors.extend(_validate_experiment(metadata))
    return errors
