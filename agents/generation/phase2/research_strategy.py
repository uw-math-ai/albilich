from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from .graph_policy import debt_covered_by_integrated_claim, get_debt_coverage_index
from .models import canonical_math_text, fingerprint_text, json_loads, normalize_text
from .research_intelligence import (
    DEEP_SESSION_ROI_VERSION,
    PRODUCTIVE_DELTA_KINDS,
    decisive_obligation_frontier,
    deep_session_roi,
    infer_domain_tags,
    proof_interface_contract,
    theorem_preflight_contract,
    representation_switch_contract,
    theorem_adaptation_contract,
    validate_deep_session_roi_metadata,
    validate_state_independent_artifact_metadata,
    verifier_filtered_outcome_learning,
)


STRATEGY_SCHEMA_VERSION = 1
APPROACH_PORTFOLIO_CONTRACT_VERSION = 3
ROOT_CUT_GATE_VERSION = 2
COUNTEREXAMPLE_PREFLIGHT_VERSION = 1
CANONICAL_ROUTE_OWNER_VERSION = 1
REFERENCE_SOLUTION_ARTIFACT_TYPE = "reference_solution"
REFERENCE_RECONSTRUCTION_INTENT = "reference_solution_reconstruction"
THREAT_ARTIFACT_TYPES = {
    "candidate_counterexample",
    "construction_failure",
    "hypothesis_gap",
    "key_failure_analysis",
    "route_obstruction",
}
THREAT_REVALIDATION_REVISION_WINDOW = 24
STRATEGIC_ARTIFACT_TYPES = {
    "approach_portfolio",
    "advisor_synthesis",
    "bridge_lemma_search",
    "conjecture_portfolio",
    "deep_session_report",
    "definition_candidate",
    "invention_authorization",
    "proof_compression",
    "conceptual_invariant_report",
}
STRATEGIC_MARKDOWN_ARTIFACT_TYPES = set(STRATEGIC_ARTIFACT_TYPES)
APPROACH_PORTFOLIO_INTENT = "approach_portfolio_brainstorming"
APPROACH_REFRESH_INTENT = "approach_portfolio_refresh"
APPROACH_PILOT_INTENT_PREFIX = "approach_pilot:"
APPROACH_STATUSES = {"idea", "pilot", "selected", "active", "paused", "killed", "successful"}
APPROACH_CONTRIBUTION_KINDS = {
    "root_closing",
    "major_bridge",
    "major_case",
    "route_killing",
    "informative_probe",
    "exploratory",
    "unplaced",
}
APPROACH_COSTS = {"low", "medium", "high"}
APPROACH_CONFIDENCE_LEVELS = {"low", "medium", "high"}
BOTTLENECK_COMPLETED_NO_DELTA_LIMIT = 2
BOTTLENECK_EXECUTION_FAILURE_LIMIT = 2
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
    "single_decisive_missing_theorem",
    "strongest_candidate_counterexample_architecture",
    "most_informative_failed_ideas",
)
LEMMA_ROOT_LEVERAGE_GATE_FIELDS = (
    "if_proved_major_case",
    "if_refuted_information_gain",
    "stronger_than_necessary",
    "renames_current_gap",
    "hypotheses_attainable",
)
CONCEPTUAL_INVARIANT_REQUIRED_FIELDS = (
    "candidate_invariants",
    "selected_invariant_id",
    "neighboring_theorem_comparison",
    "object_dictionary",
    "next_decisive_test",
)
CONCEPTUAL_INVARIANT_INTENT = "conceptual_invariant_discovery"
CONCEPTUAL_INVARIANT_LOCAL_PASS_THRESHOLD = 2
CONCEPTUAL_INVARIANT_COOLDOWN_REVISIONS = 12
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


def _all_artifact_rows(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return every artifact family exposed by either state representation."""
    result: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for key in (
        "artifacts",
        "research_artifacts",
        "audit_artifacts",
        "confirmed_counterexamples",
        "final_artifacts",
    ):
        for row in state.get(key, []) or []:
            if not isinstance(row, Mapping):
                continue
            artifact_id = str(row.get("artifact_id") or "")
            dedupe_key = artifact_id or f"{key}:{len(result)}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            result.append(row)
    return result


def _artifact_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    return _json_object(row.get("metadata_json") if "metadata_json" in row else row.get("metadata"))


def _artifact_sort_key(row: Mapping[str, Any]) -> tuple[int, str, str]:
    return (
        int(row.get("state_revision") or 0),
        str(row.get("created_at") or ""),
        str(row.get("artifact_id") or ""),
    )


def _unique_strings(value: Any) -> list[str]:
    values = _json_list(value)
    if not values and isinstance(value, str) and value.strip():
        values = [value]
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _artifact_route_id(row: Mapping[str, Any]) -> str:
    metadata = _artifact_metadata(row)
    return str(metadata.get("route_id") or metadata.get("target_route_id") or "")


def _artifact_target_id(row: Mapping[str, Any]) -> str:
    metadata = _artifact_metadata(row)
    return str(
        metadata.get("target_id")
        or metadata.get("claim_id")
        or metadata.get("conclusion_claim_id")
        or ""
    )


def _claim_target_for_context(state: Mapping[str, Any], target_id: str) -> str:
    """Map a graph-entity target to the claim accepted by context packets.

    Decisive debts can legitimately belong to a route or inference, and that
    owner should remain visible in the obligation metadata.  Workflow actions,
    however, are built around a target claim.  Normalize only known graph
    entities here so malformed unknown IDs still fail loudly downstream.
    """
    target_id = str(target_id or "")
    if not target_id:
        return ""
    if any(str(row.get("claim_id") or "") == target_id for row in state.get("claims", [])):
        return target_id
    for row in state.get("routes", []):
        if str(row.get("route_id") or "") == target_id:
            return str(row.get("conclusion_claim_id") or target_id)
    for row in state.get("inferences", []):
        if str(row.get("inference_id") or "") == target_id:
            return str(row.get("conclusion_claim_id") or target_id)
    return target_id


def minimal_active_debt_frontier(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Collapse semantic debt aliases for scheduling without erasing history.

    Exact duplicates are already coalesced when inserted.  This view handles
    differently worded descriptions of the same obstruction: the primary debt
    stays on the active work frontier, while aliases remain visible evidence
    and are not falsely marked mathematically resolved.
    """
    from .debt_canonicalizer import central_debt_clusters

    coverage_index = get_debt_coverage_index(state)
    active = [
        row
        for row in state.get("debts", [])
        if str(row.get("status") or "") == "active"
        and str(row.get("severity") or "") == "blocking"
        and not debt_covered_by_integrated_claim(
            state,
            row,
            debt_coverage_index=coverage_index,
        )
    ]
    clusters = central_debt_clusters(active)
    alias_to_primary: Dict[str, str] = {}
    for cluster in clusters:
        primary = str(cluster.get("primary_debt_id") or "")
        for alias in cluster.get("alias_debt_ids", []):
            alias_id = str(alias or "")
            if alias_id and alias_id != primary:
                alias_to_primary[alias_id] = primary
    primary_ids = [
        str(row.get("debt_id") or "")
        for row in active
        if str(row.get("debt_id") or "") not in alias_to_primary
    ]
    return {
        "active_blocking_debt_count": len(active),
        "minimal_frontier_count": len(primary_ids),
        "primary_debt_ids": primary_ids,
        "alias_to_primary": alias_to_primary,
        "clusters": clusters[:6],
        "aliases_suppressed_from_independent_scheduling": True,
        "alias_database_status_unchanged": True,
        "policy": (
            "work one canonical obstruction; retain aliases as provenance until a verifier "
            "certifies the mathematical resolution"
        ),
    }


def threat_propagation_view(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Propagate fresh counterevidence through claim dependencies.

    The view never downgrades a certified claim by itself.  It marks a
    verifier-owned revalidation frontier, distinguishing a mathematical threat
    from an already confirmed refutation.
    """
    current_revision = int(state.get("problem_state", {}).get("current_revision") or 0)
    minimum_revision = max(0, current_revision - THREAT_REVALIDATION_REVISION_WINDOW)
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    routes = {str(row.get("route_id") or ""): row for row in state.get("routes", [])}
    inferences = {str(row.get("inference_id") or ""): row for row in state.get("inferences", [])}
    direct_claim_revisions: Dict[str, int] = {}
    direct_route_revisions: Dict[str, int] = {}
    source_ids: list[str] = []

    for artifact in _artifact_rows(state):
        if str(artifact.get("artifact_type") or "") not in THREAT_ARTIFACT_TYPES:
            continue
        revision = int(artifact.get("state_revision") or 0)
        if revision < minimum_revision:
            continue
        metadata = _artifact_metadata(artifact)
        disposition = str(
            metadata.get("disposition")
            or metadata.get("status")
            or metadata.get("validation_status")
            or ""
        ).lower()
        if disposition in {"dismissed", "resolved", "invalid", "refuted_as_counterexample"}:
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        if artifact_id:
            source_ids.append(artifact_id)
        raw_ids = []
        for key in (
            "target_id",
            "claim_id",
            "inference_id",
            "route_id",
            "related_id",
            "challenged_target_id",
        ):
            raw_ids.extend(_unique_strings(metadata.get(key)))
        if not raw_ids:
            fallback = _artifact_target_id(artifact)
            if fallback:
                raw_ids.append(fallback)
        for target in raw_ids:
            if target in claims:
                direct_claim_revisions[target] = max(direct_claim_revisions.get(target, -1), revision)
            elif target in routes:
                direct_route_revisions[target] = max(direct_route_revisions.get(target, -1), revision)
                conclusion = str(routes[target].get("conclusion_claim_id") or "")
                if conclusion:
                    direct_claim_revisions[conclusion] = max(direct_claim_revisions.get(conclusion, -1), revision)
            elif target in inferences:
                route_id = str(inferences[target].get("route_id") or "")
                conclusion = str(inferences[target].get("conclusion_claim_id") or "")
                if route_id:
                    direct_route_revisions[route_id] = max(direct_route_revisions.get(route_id, -1), revision)
                if conclusion:
                    direct_claim_revisions[conclusion] = max(direct_claim_revisions.get(conclusion, -1), revision)

    threatened_claim_revisions = dict(direct_claim_revisions)
    changed = True
    while changed:
        changed = False
        for inference in inferences.values():
            premise_ids = [
                *_unique_strings(inference.get("premise_claim_ids") or inference.get("premise_claim_ids_json")),
                *_unique_strings(inference.get("condition_claim_ids") or inference.get("condition_claim_ids_json")),
            ]
            source_revision = max(
                (threatened_claim_revisions.get(claim_id, -1) for claim_id in premise_ids),
                default=-1,
            )
            if source_revision < 0:
                continue
            conclusion = str(inference.get("conclusion_claim_id") or "")
            route_id = str(inference.get("route_id") or "")
            if conclusion and source_revision > threatened_claim_revisions.get(conclusion, -1):
                threatened_claim_revisions[conclusion] = source_revision
                changed = True
            if route_id:
                direct_route_revisions[route_id] = max(direct_route_revisions.get(route_id, -1), source_revision)

    verified_statuses = {"informally_verified", "formally_verified"}
    threatened_verified = sorted(
        claim_id
        for claim_id in threatened_claim_revisions
        if str(claims.get(claim_id, {}).get("validation_status") or "") in verified_statuses
        or str(claims.get(claim_id, {}).get("lifecycle_status") or "") == "integrated"
    )
    last_verifier_by_route: Dict[str, int] = {}
    for run in state.get("recent_runs", []):
        if str(run.get("actor_role") or "") != "strict_informal_verifier":
            continue
        if str(run.get("status") or "").lower() in {"failed", "timeout", "cancelled", "patch_rejected"}:
            continue
        route_id = str(run.get("route_id") or "")
        if route_id:
            last_verifier_by_route[route_id] = max(
                last_verifier_by_route.get(route_id, -1), int(run.get("state_revision") or 0)
            )
    pending_routes: list[Dict[str, Any]] = []
    for route_id, route in routes.items():
        conclusion = str(route.get("conclusion_claim_id") or "")
        threat_revision = max(
            direct_route_revisions.get(route_id, -1),
            threatened_claim_revisions.get(conclusion, -1),
        )
        if threat_revision < 0 or conclusion not in threatened_verified:
            continue
        if last_verifier_by_route.get(route_id, -1) >= threat_revision:
            continue
        pending_routes.append(
            {
                "route_id": route_id,
                "target_id": conclusion,
                "threat_revision": threat_revision,
                "route_status": str(route.get("status") or ""),
            }
        )
    pending_routes.sort(key=lambda row: (-int(row["threat_revision"]), str(row["route_id"])))
    return {
        "source_artifact_ids": sorted(set(source_ids)),
        "direct_threatened_claim_ids": sorted(direct_claim_revisions),
        "threatened_claim_ids": sorted(threatened_claim_revisions),
        "threatened_route_ids": sorted(direct_route_revisions),
        "threatened_verified_claim_ids": threatened_verified,
        "pending_revalidation_routes": pending_routes,
        "certification_unchanged_pending_verifier": True,
        "lookback_revisions": THREAT_REVALIDATION_REVISION_WINDOW,
    }


def reference_solution_state(state: Mapping[str, Any]) -> Dict[str, Any]:
    references = [
        row
        for row in _artifact_rows(state)
        if str(row.get("artifact_type") or "") == REFERENCE_SOLUTION_ARTIFACT_TYPE
    ]
    if not references:
        return {"available": False, "pending_reconstruction": False}
    reference = max(references, key=_artifact_sort_key)
    artifact_id = str(reference.get("artifact_id") or "")
    revision = int(reference.get("state_revision") or 0)
    reconstructions = []
    for artifact in _artifact_rows(state):
        if str(artifact.get("artifact_type") or "") not in {"proof_dossier", "proof_blueprint"}:
            continue
        metadata = _artifact_metadata(artifact)
        if str(metadata.get("reference_solution_artifact_id") or "") != artifact_id:
            continue
        if int(artifact.get("state_revision") or 0) >= revision:
            reconstructions.append(artifact)
    reconstruction = max(reconstructions, key=_artifact_sort_key) if reconstructions else None
    metadata = _artifact_metadata(reference)
    return {
        "available": True,
        "artifact_id": artifact_id,
        "path": str(reference.get("path") or ""),
        "source_title": str(metadata.get("title") or ""),
        "source_statement": str(metadata.get("source_statement") or ""),
        "reference_revision": revision,
        "pending_reconstruction": reconstruction is None,
        "reconstruction_artifact_id": str(reconstruction.get("artifact_id") or "") if reconstruction else "",
        "verification_authority": False,
        "policy": (
            "reconstruct the argument in local notation, check every hypothesis and case, and then submit the "
            "resulting route to the ordinary strict verifier"
        ),
    }


def proof_program_view(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Build compact proof programs from routes and existing artifact metadata."""
    routes = [
        row
        for row in state.get("routes", [])
        if str(row.get("status") or "") not in {"abandoned", "superseded"}
    ]
    artifacts = list(_artifact_rows(state))
    programs: list[Dict[str, Any]] = []
    for route in routes:
        route_id = str(route.get("route_id") or "")
        target_id = str(route.get("conclusion_claim_id") or "")
        related = [
            artifact
            for artifact in artifacts
            if _artifact_route_id(artifact) == route_id
            or (not _artifact_route_id(artifact) and _artifact_target_id(artifact) == target_id)
        ]
        related.sort(key=_artifact_sort_key, reverse=True)
        metadata_rows = [_artifact_metadata(row) for row in related]

        def newest_value(*keys: str, default: Any = "") -> Any:
            for metadata in metadata_rows:
                for key in keys:
                    value = metadata.get(key)
                    if value not in (None, "", [], {}):
                        return value
            return default

        covered_cases: list[str] = []
        open_cases: list[str] = []
        for metadata in metadata_rows:
            for item in _unique_strings(metadata.get("covered_cases") or metadata.get("cases_covered")):
                if item not in covered_cases:
                    covered_cases.append(item)
            for item in _unique_strings(metadata.get("open_cases") or metadata.get("uncovered_cases")):
                if item not in open_cases:
                    open_cases.append(item)
        cases_exhaustive = bool(newest_value("cases_exhaustive", "case_coverage_complete", default=False))
        program_id = str(newest_value("proof_program_id", default=f"program:{route_id}"))
        programs.append(
            {
                "program_id": program_id,
                "route_id": route_id,
                "target_id": target_id,
                "status": str(route.get("status") or "active"),
                "relation_to_parent": str(route.get("relation_to_parent") or "sufficient"),
                "proof_philosophy": str(
                    newest_value("proof_philosophy", "research_philosophy", default=route.get("strategy") or route.get("label") or route_id)
                ),
                "root_implication": str(
                    newest_value(
                        "root_implication",
                        "root_consequence",
                        default=("route concludes the root" if target_id == "root" else "must be spliced into a root route"),
                    )
                ),
                "decisive_obligation": str(newest_value("decisive_obligation", "next_decisive_step", default="")),
                "validation_criteria": _unique_strings(
                    newest_value(
                        "validation_criteria",
                        default=["strict verifier accepts the terminal inference and every dependency interface"],
                    )
                ),
                "abandonment_criteria": _unique_strings(
                    newest_value(
                        "abandonment_criteria",
                        "route_reset_criteria",
                        default=["a named counterexample or refuted decisive implication invalidates the program"],
                    )
                ),
                "covered_cases": covered_cases,
                "open_cases": open_cases,
                "cases_exhaustive": cases_exhaustive,
                "case_coverage_status": (
                    "exhaustive" if cases_exhaustive and not open_cases else "open" if open_cases else "unspecified"
                ),
                "canonical_artifact_id": str(related[0].get("artifact_id") or "") if related else "",
                "long_session_continuation_allowed": True,
                "wall_clock_expiration": None,
            }
        )
    if not programs:
        programs.append(
            {
                "program_id": "program:root-unrouted",
                "route_id": "",
                "target_id": "root",
                "status": "forming",
                "relation_to_parent": "sufficient",
                "proof_philosophy": "unrouted root-program discovery",
                "root_implication": "must produce an explicit sufficient root route",
                "decisive_obligation": "",
                "validation_criteria": ["an explicit root route and terminal inference pass strict verification"],
                "abandonment_criteria": ["replace only after mathematical counterevidence or a strictly stronger program emerges"],
                "covered_cases": [],
                "open_cases": [],
                "cases_exhaustive": False,
                "case_coverage_status": "unspecified",
                "canonical_artifact_id": "",
                "long_session_continuation_allowed": True,
                "wall_clock_expiration": None,
            }
        )
    case_status_counts: Dict[str, int] = {}
    for program in programs:
        status = str(program.get("case_coverage_status") or "unspecified")
        case_status_counts[status] = case_status_counts.get(status, 0) + 1
    return {
        "programs": programs[:8],
        "program_count": len(programs),
        "root_closing_program_count": sum(
            1
            for row in programs
            if str(row.get("target_id") or "") == "root"
            and str(row.get("route_id") or "")
            and str(row.get("relation_to_parent") or "sufficient") == "sufficient"
        ),
        "case_coverage_status_counts": case_status_counts,
        "uncovered_or_unspecified_program_ids": [
            str(row.get("program_id") or "")
            for row in programs
            if str(row.get("case_coverage_status") or "") != "exhaustive"
        ],
        "comparison_policy": (
            "compare genuinely different proof philosophies by root implication, decisive obligation, case coverage, "
            "validation evidence, and mathematical reset criteria"
        ),
        "no_wall_clock_abandonment": True,
    }


def long_session_workspace(state: Mapping[str, Any], action: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    action = action or {}
    target_id = str(action.get("target_id") or "root")
    route_id = str(action.get("route_id") or "")
    candidates = []
    for artifact in _artifact_rows(state):
        if str(artifact.get("artifact_type") or "") not in {
            "proof_dossier",
            "proof_blueprint",
            "proof_compression",
            "deep_session_report",
        }:
            continue
        artifact_route = _artifact_route_id(artifact)
        artifact_target = _artifact_target_id(artifact)
        if route_id and artifact_route == route_id:
            candidates.append(artifact)
        elif artifact_target in {"", target_id}:
            candidates.append(artifact)
    canonical = max(candidates, key=_artifact_sort_key) if candidates else None
    recent_target_runs = [
        row
        for row in state.get("recent_runs", [])
        if str(row.get("actor_role") or "") == "researcher"
        and str(row.get("target_id") or "root") == target_id
        and str(row.get("status") or "").lower() not in {"failed", "error", "cancelled", "timeout"}
    ]
    return {
        "target_id": target_id,
        "route_id": route_id,
        "canonical_artifact_id": str(canonical.get("artifact_id") or "") if canonical else "",
        "canonical_artifact_type": str(canonical.get("artifact_type") or "") if canonical else "",
        "successful_target_passes": len(recent_target_runs),
        "continue_in_place": canonical is not None,
        "wall_clock_expiration": None,
        "continuation_policy": (
            "continue a coherent long proof indefinitely while it produces or sharpens mathematical deltas; "
            "review only on evidence of contradiction, interface failure, duplication, or a stalled decisive obligation"
        ),
        "create_new_management_artifact": False,
    }


def canonical_route_ownership(
    state: Mapping[str, Any],
    action: Mapping[str, Any] | None = None,
    *,
    obligation_frontier: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    action = action or {}
    workspace = long_session_workspace(state, action)
    frontier = (
        dict(obligation_frontier)
        if obligation_frontier is not None
        else decisive_obligation_frontier(state)
    )
    route_id = str(action.get("route_id") or frontier.get("selected_route_id") or "")
    target_id = str(action.get("target_id") or "root")
    canonical_id = str(workspace.get("canonical_artifact_id") or "")
    ownership_required = bool(route_id)
    continuity_required = bool(canonical_id)
    if ownership_required:
        required_metadata_fields = [
            "canonical_route_owner_version",
            "canonical_route_id",
            "root_implication_update",
            "root_cut_signature_before",
            "root_cut_signature_after",
            "creates_parallel_dossier",
        ]
    elif continuity_required:
        required_metadata_fields = [
            "supersedes_artifact_id",
            "root_implication_update",
            "root_cut_signature_before",
            "root_cut_signature_after",
            "creates_parallel_dossier",
        ]
    else:
        required_metadata_fields = []
    return {
        "canonical_route_owner_version": CANONICAL_ROUTE_OWNER_VERSION,
        "route_id": route_id,
        "target_id": target_id,
        "canonical_artifact_id": canonical_id,
        "canonical_artifact_type": str(workspace.get("canonical_artifact_type") or ""),
        "ownership_required": ownership_required,
        "continuity_required": continuity_required,
        "supersede_or_update_required": continuity_required,
        "parallel_dossier_creation_forbidden": continuity_required,
        "required_metadata_fields": required_metadata_fields,
        "policy": (
            "One proof program owns one canonical dossier. Continue it by explicit supersession, "
            "or state why the route is replaced; do not accumulate parallel proof paperwork."
        ),
    }


def root_cut_progress_gate(
    state: Mapping[str, Any],
    *,
    obligation_frontier: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    frontier = (
        dict(obligation_frontier)
        if obligation_frontier is not None
        else decisive_obligation_frontier(state)
    )
    obligations = list(frontier.get("minimal_cut_obligations") or [])
    cut_signature = [
        f"{item.get('obligation_type')}:{item.get('obligation_id')}"
        for item in obligations
        if str(item.get("obligation_id") or "")
    ]
    used_as_premise = {
        str(item)
        for inference in state.get("inferences", [])
        for item in inference.get("premise_claim_ids", []) or []
        if str(item)
    }
    verified = {"informally_verified", "formally_verified"}
    unplaced_verified = [
        str(claim.get("claim_id") or "")
        for claim in state.get("claims", [])
        if str(claim.get("claim_id") or "") != "root"
        and (
            str(claim.get("validation_status") or "") in verified
            or str(claim.get("lifecycle_status") or "") == "integrated"
        )
        and str(claim.get("claim_id") or "") not in used_as_premise
    ]
    research_streak = 0
    for run in state.get("recent_runs", []):
        role = str(run.get("actor_role") or "")
        status = str(run.get("status") or "").lower()
        if status in {"failed", "error", "cancelled", "timeout", "patch_rejected"}:
            continue
        if role in {"strict_informal_verifier", "integration_verifier"}:
            break
        if role == "researcher":
            research_streak += 1
    metrics = root_leverage_metrics(state)
    selected_route_id = str(frontier.get("selected_route_id") or "")
    has_inference_frontier = bool(state.get("inferences", []))
    has_consolidatable_material = bool(
        selected_route_id or has_inference_frontier or unplaced_verified
    )
    claim_cap_reached = len(state.get("claims", [])) >= 24
    research_streak_pressure = research_streak >= 3 and has_consolidatable_material
    active = bool(
        obligations
        and int(metrics.get("verified_root_terminal_inference_count") or 0) == 0
        and (research_streak_pressure or len(unplaced_verified) >= 3 or claim_cap_reached)
    )
    return {
        "root_cut_gate_version": ROOT_CUT_GATE_VERSION,
        "active": active,
        "selected_route_id": selected_route_id,
        "cut_signature": cut_signature,
        "minimal_cut_count": len(obligations),
        "decisive_obligation": dict(frontier.get("decisive_obligation") or {}),
        "recent_research_passes_without_verifier_handoff": research_streak,
        "has_consolidatable_material": has_consolidatable_material,
        "claim_cap_reached": claim_cap_reached,
        "activation_blocker": (
            ""
            if active or research_streak < 3 or has_consolidatable_material or claim_cap_reached
            else "no_route_inference_or_verified_claim_to_consolidate"
        ),
        "unplaced_verified_claim_ids": unplaced_verified[:12],
        "claim_creation_frozen": active,
        "allowed_moves": [
            "assemble_existing_claims_into_root_route",
            "prove_or_refute_one_cut_obligation",
            "validate_a_counterexample",
            "abandon_or_replace_the_selected_route_with_evidence",
        ],
        "release_condition": (
            "create a verifier-ready terminal inference, complete verifier handoff, "
            "or remove the consolidatable frontier below the claim cap"
        ),
    }


def counterexample_preflight_state(state: Mapping[str, Any]) -> Dict[str, Any]:
    evidence_types = {
        "candidate_counterexample",
        "confirmed_counterexample",
        "cas_experiment_report",
        "route_obstruction",
        "construction_failure",
    }
    evidence = []
    for artifact in _artifact_rows(state):
        if str(artifact.get("artifact_type") or "") not in evidence_types:
            continue
        metadata = _artifact_metadata(artifact)
        target_id = str(
            metadata.get("target_id")
            or metadata.get("claim_id")
            or metadata.get("challenged_target_id")
            or "root"
        )
        if target_id == "root":
            evidence.append(str(artifact.get("artifact_id") or ""))
    root = next(
        (row for row in state.get("claims", []) if str(row.get("claim_id") or "") == "root"),
        {},
    )
    solved = (
        str(root.get("validation_status") or "") in {"informally_verified", "formally_verified", "refuted"}
        or str(root.get("lifecycle_status") or "") in {"integrated", "refuted"}
    )
    return {
        "counterexample_preflight_version": COUNTEREXAMPLE_PREFLIGHT_VERSION,
        "due": not solved and not evidence,
        "completed_evidence_artifact_ids": evidence[:8],
        "full_original_hypotheses_required": True,
        "boundary_and_small_case_sweep_required": True,
        "bounded_cas_plan_required_when_available": True,
        "no_counterexample_is_not_a_proof": True,
    }


def root_leverage_metrics(state: Mapping[str, Any]) -> Dict[str, Any]:
    programs = proof_program_view(state)
    debts = minimal_active_debt_frontier(state)
    threats = threat_propagation_view(state)
    root_routes = [
        row
        for row in state.get("routes", [])
        if str(row.get("conclusion_claim_id") or "") == "root"
        and str(row.get("relation_to_parent") or "sufficient") == "sufficient"
        and str(row.get("status") or "") not in {"abandoned", "superseded"}
    ]
    root_route_ids = {str(row.get("route_id") or "") for row in root_routes}
    terminal = [
        row
        for row in state.get("inferences", [])
        if str(row.get("route_id") or "") in root_route_ids
        and str(row.get("conclusion_claim_id") or "") == "root"
    ]
    verified = {"informally_verified", "formally_verified"}
    return {
        "root_closing_program_count": int(programs.get("root_closing_program_count") or 0),
        "root_terminal_inference_count": len(terminal),
        "verified_root_terminal_inference_count": sum(
            1 for row in terminal if str(row.get("validation_status") or "") in verified
        ),
        "programs_with_exhaustive_case_coverage": int(
            (programs.get("case_coverage_status_counts") or {}).get("exhaustive", 0)
        ),
        "minimal_active_blocking_frontier_count": int(debts.get("minimal_frontier_count") or 0),
        "semantic_debt_alias_count": len(debts.get("alias_to_primary") or {}),
        "threatened_verified_claim_count": len(threats.get("threatened_verified_claim_ids") or []),
        "pending_threat_revalidation_count": len(threats.get("pending_revalidation_routes") or []),
        "artifact_count_is_not_root_progress": True,
    }


def latest_artifact(state: Mapping[str, Any], artifact_type: str) -> Optional[Dict[str, Any]]:
    rows = [row for row in _artifact_rows(state) if str(row.get("artifact_type") or "") == artifact_type]
    if not rows:
        return None
    row = dict(max(rows, key=_artifact_sort_key))
    row["metadata"] = _artifact_metadata(row)
    return row


def _approach_candidates(metadata: Mapping[str, Any]) -> list[Dict[str, Any]]:
    raw = metadata.get("approaches")
    if raw is None:
        raw = _json_object(metadata.get("approach_portfolio")).get("approaches", [])
    return [dict(item) for item in raw or [] if isinstance(item, Mapping)]


def approach_alignment_evidence(
    state: Mapping[str, Any], *, portfolio_revision: int
) -> list[Dict[str, Any]]:
    """Verified root-relevant developments newer than a portfolio baseline.

    A speculative portfolio is a view of the current mathematical landscape,
    not permanent proof state.  Once a verified or integrated root-adjacent
    claim gains newer evidence, every displayed root consequence must be
    recomputed before the scheduler returns to local approach pilots.
    """
    artifacts = {
        str(row.get("artifact_id") or ""): row
        for row in _all_artifact_rows(state)
        if str(row.get("artifact_id") or "")
    }
    developments: list[Dict[str, Any]] = []
    verified = {"informally_verified", "formally_verified"}
    for claim in state.get("claims", []) or []:
        if not isinstance(claim, Mapping):
            continue
        claim_id = str(claim.get("claim_id") or "")
        status = str(claim.get("validation_status") or "")
        lifecycle = str(claim.get("lifecycle_status") or "")
        if lifecycle in {"superseded", "abandoned", "blocked"}:
            continue
        parent_ids = {
            str(item)
            for item in _json_list(claim.get("parent_ids") or claim.get("parent_ids_json"))
            if str(item)
        }
        try:
            root_impact = float(claim.get("root_impact") or 0.0)
        except (TypeError, ValueError):
            root_impact = 0.0
        if status not in verified and lifecycle != "integrated":
            continue
        if claim_id != "root" and "root" not in parent_ids and root_impact < 0.5:
            continue
        evidence_rows = [
            artifacts[artifact_id]
            for artifact_id in _unique_strings(claim.get("evidence_artifact_ids_json"))
            if artifact_id in artifacts
            and int(artifacts[artifact_id].get("state_revision") or 0) > int(portfolio_revision)
        ]
        if not evidence_rows:
            continue
        newest = max(evidence_rows, key=_artifact_sort_key)
        developments.append(
            {
                "claim_id": claim_id,
                "statement": str(claim.get("statement") or ""),
                "validation_status": status,
                "lifecycle_status": lifecycle,
                "root_impact": root_impact,
                "evidence_artifact_ids": [str(row.get("artifact_id") or "") for row in evidence_rows],
                "newest_evidence_revision": int(newest.get("state_revision") or 0),
                "newest_evidence_summary": str(newest.get("content_summary") or ""),
            }
        )
    developments.sort(
        key=lambda row: (
            -int(row.get("newest_evidence_revision") or 0),
            -float(row.get("root_impact") or 0.0),
            str(row.get("claim_id") or ""),
        )
    )
    return developments[:12]


def approach_portfolio_view(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the latest speculative approach portfolio without granting proof authority."""
    artifact = latest_artifact(state, "approach_portfolio")
    candidates = _approach_candidates(artifact["metadata"]) if artifact else []
    selected_ids = {
        str(item)
        for item in _json_list((artifact or {}).get("metadata", {}).get("selected_approach_ids"))
        if str(item)
    }
    if candidates and not selected_ids:
        selected_ids = {
            str(item.get("approach_id") or "")
            for item in candidates
            if str(item.get("status") or "") in {"selected", "pilot", "active"}
            and str(item.get("approach_id") or "")
        }
    if candidates and not selected_ids:
        # Missing advisory ranking metadata must not make useful ideas vanish.
        # This fallback has no proof or verification authority.
        selected_ids = {
            str(item.get("approach_id") or "")
            for item in candidates[:2]
            if str(item.get("approach_id") or "")
        }
    ranked = sorted(
        candidates,
        key=lambda item: (
            0 if str(item.get("approach_id") or "") in selected_ids else 1,
            -int(item.get("contribution_level") or 0),
            str(item.get("approach_id") or ""),
        ),
    )
    portfolio_revision = int(artifact.get("state_revision") or 0) if artifact else 0
    alignment_evidence = (
        approach_alignment_evidence(state, portfolio_revision=portfolio_revision) if artifact else []
    )
    approach_runs = [
        run
        for run in state.get("recent_runs", [])
        if str(run.get("search_intent") or "")
        in {APPROACH_PORTFOLIO_INTENT, APPROACH_REFRESH_INTENT}
    ]
    approach_runs.sort(
        key=lambda run: (
            int(run.get("state_revision") or 0),
            str(run.get("created_at") or ""),
            str(run.get("run_id") or ""),
        ),
        reverse=True,
    )
    latest_run = approach_runs[0] if approach_runs else {}
    latest_status = str(latest_run.get("status") or "").lower()
    if artifact:
        generation_status = "current"
    elif latest_status in {"running", "started", "in_progress", "pending"}:
        generation_status = "generating"
    elif latest_status in {"failed", "error", "cancelled", "timeout", "patch_rejected"}:
        generation_status = "retry_pending"
    elif latest_status in {"completed", "succeeded", "success"}:
        generation_status = "missing_output_retry_pending"
    else:
        generation_status = "pending"
    return {
        "artifact_id": str(artifact.get("artifact_id") or "") if artifact else "",
        "state_revision": int(artifact.get("state_revision") or 0) if artifact else 0,
        "portfolio_kind": str((artifact or {}).get("metadata", {}).get("portfolio_kind") or ""),
        "brainstorming_summary": str((artifact or {}).get("metadata", {}).get("brainstorming_summary") or ""),
        "approaches": ranked,
        "approach_count": len(ranked),
        "selected_approach_ids": sorted(selected_ids),
        "research_questions": _json_list((artifact or {}).get("metadata", {}).get("research_questions")),
        "generation_state": {
            "status": generation_status,
            "latest_run_id": str(latest_run.get("run_id") or ""),
            "latest_run_status": latest_status,
            "attempt_count": len(approach_runs),
        },
        "alignment_status": "stale" if alignment_evidence else ("current" if artifact else "uninitialized"),
        "alignment_evidence": alignment_evidence,
        "contribution_legend": {
            "5": "root-closing if its exact bridge is verified",
            "4": "major bridge into a sufficient root route",
            "3": "closes a major case or decisively kills a route",
            "2": "informative probe that changes the next decision",
            "1": "exploratory but mathematically placed",
            "0": "unplaced idea; no claimed root contribution",
        },
        "portfolio_policy": {
            "allocation_rule": (
                "interleave selected pilots, an untried mechanism, and an adversarial test; "
                "the deterministic scheduler chooses the next admissible action"
            ),
            "fixed_percentage_claim": False,
            "qualitative_scores_only": True,
            "ideas_are_not_proof_evidence": True,
            "proof_debts_remain_strict": True,
        },
    }


def _run_has_accepted_mathematical_delta(
    state: Mapping[str, Any], run: Mapping[str, Any]
) -> bool:
    """Whether the host journal recorded a mathematical change by this run.

    Child-authored artifact labels are intentionally ignored.  The summary is
    derived from an invariant-checked patch delta and a host-issued run id in
    ``ProofStateStore.get_scheduler_state``.
    """

    run_id = str(run.get("run_id") or "")
    if not run_id:
        return False
    return any(
        str(delta.get("run_id") or "") == run_id and bool(delta.get("changes"))
        for delta in state.get("accepted_mathematical_deltas", []) or []
        if isinstance(delta, Mapping)
    )


def _selected_candidate_ids_in_trace(trace: Mapping[str, Any]) -> set[str]:
    """Return selections on the actually selected path of a nested trace."""

    selected_id = str(trace.get("selected_candidate_id") or "")
    selected_ids = {selected_id} if selected_id else set()
    nested_traces = trace.get("nested_policy_traces")
    if isinstance(nested_traces, Mapping):
        nested = nested_traces.get(selected_id)
        if isinstance(nested, Mapping):
            selected_ids.update(_selected_candidate_ids_in_trace(nested))
    legacy_nested = trace.get("base_policy_trace")
    if isinstance(legacy_nested, Mapping):
        # Older traces stored only the selected base-policy comparison.
        selected_ids.update(_selected_candidate_ids_in_trace(legacy_nested))
    return selected_ids


def _run_selected_exact_candidate(
    run: Mapping[str, Any], candidate_id: str
) -> Optional[bool]:
    """Report exact selection, or ``None`` when trace identity is unavailable."""

    if run.get("decision_trace_history_included") is False:
        return None
    raw_trace = run.get("decision_trace_json") or run.get("decision_trace")
    if not raw_trace:
        return None
    trace = json_loads(raw_trace, {}) if isinstance(raw_trace, str) else raw_trace
    if not isinstance(trace, Mapping) or not trace.get("candidates"):
        return None
    return candidate_id in _selected_candidate_ids_in_trace(trace)


def bottleneck_lease_state(
    state: Mapping[str, Any], action: Optional[Mapping[str, Any]] = None
) -> Dict[str, Any]:
    """Bound repeated local work by mathematical outcomes, never wall-clock time."""
    action = action or {}
    target_id = str(action.get("target_id") or "")
    debt_id = str(action.get("debt_id") or _json_object(action.get("bottleneck_lock_signal")).get("debt_id") or "")
    exact_candidate_id = str(action.get("bottleneck_candidate_id") or "")
    inferred_from_state = False
    if not target_id and not debt_id:
        blocking = sorted(
            (
                row
                for row in state.get("debts", [])
                if str(row.get("status") or "active") == "active"
                and str(row.get("severity") or "") == "blocking"
            ),
            key=lambda row: (-int(row.get("repeated_count") or 0), str(row.get("debt_id") or "")),
        )
        if blocking:
            selected = blocking[0]
            debt_id = str(selected.get("debt_id") or "")
            owner_id = str(selected.get("suggested_next_target") or selected.get("owner_id") or "root")
            target_id = _claim_target_for_context(state, owner_id) or "root"
            inferred_from_state = True
    if not target_id and not debt_id:
        return {
            "active": False,
            "escape_required": False,
            "completed_no_delta_passes": 0,
            "consecutive_execution_failures": 0,
            "completed_no_delta_limit": BOTTLENECK_COMPLETED_NO_DELTA_LIMIT,
            "execution_failure_limit": BOTTLENECK_EXECUTION_FAILURE_LIMIT,
            "wall_clock_timeout": None,
        }
    reset_intents = {
        APPROACH_PORTFOLIO_INTENT,
        APPROACH_REFRESH_INTENT,
        CONCEPTUAL_INVARIANT_INTENT,
        "creative_proof_attack",
        "global_synthesis",
        "advisor_global_synthesis",
        "active_proof_compression",
    }
    completed_no_delta = 0
    execution_failures = 0
    failure_window_open = True
    examined_run_ids: list[str] = []
    for run in state.get("recent_runs", []):
        intent = str(run.get("search_intent") or "")
        if intent in reset_intents or intent.startswith(APPROACH_PILOT_INTENT_PREFIX):
            break
        if exact_candidate_id:
            exact_selection = _run_selected_exact_candidate(
                run, exact_candidate_id
            )
            if exact_selection is False:
                continue
            if exact_selection is None and (
                run.get("decision_trace_history_included") is False
                or str(run.get("selection_design") or "") == "deterministic"
            ):
                # Do not charge an exact proof obligation when bounded trace
                # history no longer proves which peer was selected.
                break
        same_target = not target_id or str(run.get("target_id") or "") == target_id
        if (
            not same_target
            or str(run.get("actor_role") or "") != "researcher"
            or str(run.get("mode") or "") not in {"prove", "reduce", "strengthen", "weaken"}
        ):
            continue
        status = str(run.get("status") or "").lower()
        examined_run_ids.append(str(run.get("run_id") or ""))
        if status in {"failed", "error", "cancelled", "timeout"}:
            if failure_window_open:
                execution_failures += 1
            continue
        if status not in {"completed", "succeeded", "success"}:
            continue
        failure_window_open = False
        if _run_has_accepted_mathematical_delta(state, run):
            break
        completed_no_delta += 1
    escape_required = (
        completed_no_delta >= BOTTLENECK_COMPLETED_NO_DELTA_LIMIT
        or execution_failures >= BOTTLENECK_EXECUTION_FAILURE_LIMIT
    )
    if execution_failures >= BOTTLENECK_EXECUTION_FAILURE_LIMIT:
        reason = "the same local bottleneck reached the execution-failure retry cap"
    elif completed_no_delta >= BOTTLENECK_COMPLETED_NO_DELTA_LIMIT:
        reason = "two completed passes produced no mathematical root-relevant delta"
    else:
        reason = "the local bottleneck still has an evidence-based lease"
    return {
        "active": True,
        "target_id": target_id,
        "debt_id": debt_id,
        "inferred_from_state": inferred_from_state,
        "escape_required": escape_required,
        "reason": reason,
        "completed_no_delta_passes": completed_no_delta,
        "consecutive_execution_failures": execution_failures,
        "completed_no_delta_limit": BOTTLENECK_COMPLETED_NO_DELTA_LIMIT,
        "execution_failure_limit": BOTTLENECK_EXECUTION_FAILURE_LIMIT,
        "examined_run_ids": [item for item in examined_run_ids if item][:8],
        "required_escape": "refresh the approach portfolio and change mechanism, representation, or proof direction",
        "wall_clock_timeout": None,
    }


def approach_brainstorming_trigger(
    state: Mapping[str, Any],
    primary_action: Mapping[str, Any],
    *,
    steering_alignment: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    root_claim = next(
        (row for row in state.get("claims", []) if str(row.get("claim_id") or "") == "root"),
        {},
    )
    if (
        str(root_claim.get("lifecycle_status") or "") == "integrated"
        or str(root_claim.get("validation_status") or "") in {"informally_verified", "formally_verified"}
    ):
        return {"due": False, "reason": "the root has left discovery mode"}
    research_mode = str(primary_action.get("research_mode") or "")
    parallel_mode = str(state.get("problem_state", {}).get("research_parallel_mode") or "")
    explicitly_enabled = bool(primary_action.get("approach_brainstorming_enabled"))
    if research_mode != "hard_problem" and parallel_mode != "multi_branch_research" and not explicitly_enabled:
        if not (steering_alignment or {}).get("required"):
            return {"due": False, "reason": "initial portfolios are reserved for hard or multi-branch research runs"}
    portfolio = approach_portfolio_view(state)
    alignment_evidence = list(portfolio.get("alignment_evidence") or [])
    if (steering_alignment or {}).get("required") or alignment_evidence:
        kind = "refresh" if portfolio.get("artifact_id") else "initial"
        source_steering_ids = [
            str(item)
            for item in (steering_alignment or {}).get("source_steering_ids", [])
            if str(item)
        ]
        return {
            "due": True,
            "kind": kind,
            "reason": (
                "processed human steering and newer verified root evidence require every approach's root effect to be recomputed"
                if source_steering_ids and alignment_evidence
                else "processed human steering requires a dedicated global approach-alignment pass"
                if source_steering_ids
                else "newer verified root-relevant evidence makes the displayed approach portfolio stale"
            ),
            "supersedes_artifact_id": str(portfolio.get("artifact_id") or ""),
            "alignment_required": True,
            "candidate_minimum": 6,
            "approach_alignment": {
                "required": True,
                "source_steering_ids": source_steering_ids,
                "directives": list((steering_alignment or {}).get("directives") or []),
                "baseline_portfolio_artifact_id": str(portfolio.get("artifact_id") or ""),
                "baseline_portfolio_revision": int(portfolio.get("state_revision") or 0),
                "current_revision": int(state.get("problem_state", {}).get("current_revision") or 0),
                "verified_root_developments": alignment_evidence,
                "evidence_artifact_ids": list(
                    dict.fromkeys(
                        artifact_id
                        for development in alignment_evidence
                        for artifact_id in development.get("evidence_artifact_ids", [])
                        if str(artifact_id)
                    )
                ),
                "root_effect_recomputation_required": True,
                "every_approach_must_explain_steering_impact": True,
            },
        }
    if not portfolio.get("artifact_id"):
        lease = bottleneck_lease_state(state, primary_action)
        if primary_action.get("bottleneck_lock_required") and not lease.get("escape_required"):
            return {
                "due": False,
                "reason": "the already-selected bottleneck receives its evidence-based lease before a portfolio refresh",
                "bottleneck_lease": lease,
            }
        if lease.get("escape_required"):
            return {
                "due": True,
                "kind": "initial",
                "reason": str(lease.get("reason") or "the first local bottleneck lease expired"),
                "bottleneck_lease": lease,
            }
        return {
            "due": True,
            "kind": "initial",
            "reason": "a hard research question should begin with globally different approaches before local proof work",
        }
    lease = bottleneck_lease_state(state, primary_action)
    if lease.get("escape_required"):
        return {
            "due": True,
            "kind": "refresh",
            "reason": str(lease.get("reason") or "the bottleneck lease expired"),
            "supersedes_artifact_id": str(portfolio.get("artifact_id") or ""),
            "bottleneck_lease": lease,
        }
    revision = int(portfolio.get("state_revision") or 0)
    later_completed = [
        run
        for run in state.get("recent_runs", [])
        if int(run.get("state_revision") or 0) >= revision
        and str(run.get("actor_role") or "") == "researcher"
        and str(run.get("status") or "").lower() in {"completed", "succeeded", "success"}
    ]
    if len(later_completed) >= 6 and not any(
        _run_has_accepted_mathematical_delta(state, run) for run in later_completed
    ):
        return {
            "due": True,
            "kind": "refresh",
            "reason": "six completed research passes since the portfolio produced no mathematical root-relevant delta",
            "supersedes_artifact_id": str(portfolio.get("artifact_id") or ""),
            "bottleneck_lease": lease,
        }
    return {"due": False, "reason": "the current portfolio still has untested or productive approaches", "bottleneck_lease": lease}


def selected_approach_candidate(state: Mapping[str, Any]) -> Dict[str, Any]:
    portfolio = approach_portfolio_view(state)
    selected_ids = set(portfolio.get("selected_approach_ids") or [])
    if not selected_ids:
        return {}
    attempted = {
        str(run.get("search_intent") or "").removeprefix(APPROACH_PILOT_INTENT_PREFIX)
        for run in state.get("recent_runs", [])
        if str(run.get("search_intent") or "").startswith(APPROACH_PILOT_INTENT_PREFIX)
        and int(run.get("state_revision") or 0) >= int(portfolio.get("state_revision") or 0)
    }
    for candidate in portfolio.get("approaches", []):
        approach_id = str(candidate.get("approach_id") or "")
        if approach_id in selected_ids and approach_id not in attempted and str(candidate.get("status") or "") not in {"killed", "successful"}:
            return dict(candidate)
    return {}


def latest_conceptual_invariant_artifact(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the newest completed conceptual pass across valid deliverables.

    Conceptual discovery can run as an ordinary ``conceptual_invariant_report``
    or as a long mathematical session whose required artifact type is
    ``deep_session_report``.  The latter counts only when it actually contains
    the conceptual-invariant contract, so unrelated deep sessions do not reset
    the watermark.
    """
    candidates: list[Mapping[str, Any]] = []
    for row in _artifact_rows(state):
        artifact_type = str(row.get("artifact_type") or "")
        metadata = _artifact_metadata(row)
        if artifact_type == "conceptual_invariant_report":
            candidates.append(row)
            continue
        if (
            artifact_type == "deep_session_report"
            and _nonempty_list(metadata.get("candidate_invariants"))
            and str(metadata.get("selected_invariant_id") or "").strip()
        ):
            candidates.append(row)
    if not candidates:
        return None
    row = dict(max(candidates, key=_artifact_sort_key))
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
    "chief_factor_structure": ("chief factor", "minimal normal subgroup", "composition factor", "socle", "primitive group"),
    "fixed_point_action": ("fixed point", "stabilizer", "orbit", "permutation action", "base size"),
    "character_restriction": ("character restriction", "restrict character", "induced character", "clifford theory", "codegree"),
    "extension_obstruction": ("group extension", "extension class", "splitting", "complement", "cohomology"),
    "double_counting": ("count in two ways", "double count", "incidence", "average degree"),
    "probabilistic_witness": ("random choice", "positive probability", "expectation", "local lemma", "concentration"),
    "spectral_encoding": ("eigenvalue", "spectrum", "adjacency matrix", "laplacian", "trace method"),
    "generating_function": ("generating function", "coefficient", "recurrence", "formal power series"),
    "normal_form": ("normal form", "rewrite", "canonical representative", "groebner", "reduction system"),
    "duality_or_universal_property": ("dual", "adjoint", "universal property", "representable", "functor"),
    "classification_reduction": ("classification", "simple group", "irreducible case", "finite list", "exceptional case"),
    "representation_switch": ("reformulate", "equivalent language", "translate into", "view as", "encode as"),
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
    query_domains = set(infer_domain_tags(text))
    if not query_features and not query_domains:
        return []
    ranked: list[tuple[float, str, Dict[str, Any]]] = []
    for card in load_method_cards():
        signature = set(str(item) for item in card.get("structural_signature", []))
        domains = set(str(item) for item in card.get("domain_tags", []))
        feature_overlap = len(query_features & signature)
        domain_overlap = len(query_domains & domains)
        if not feature_overlap and not domain_overlap:
            continue
        coverage = feature_overlap / max(1, len(signature))
        precision = feature_overlap / max(1, len(query_features))
        domain_coverage = domain_overlap / max(1, min(3, len(domains)))
        score = round(0.5 * coverage + 0.25 * precision + 0.25 * domain_coverage, 4)
        ranked.append((score, str(card.get("method_id") or ""), card))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    results: list[Dict[str, Any]] = []
    for score, _, card in ranked[: max(0, limit)]:
        results.append(
            {
                **card,
                "structural_match_score": score,
                "matched_structural_features": sorted(query_features & set(card.get("structural_signature", []))),
                "matched_domain_tags": sorted(query_domains & set(card.get("domain_tags", []))),
                "method_transfer_packet_required": True,
                "method_transfer_fields": [
                    "hypothesis_match",
                    "object_translation",
                    "reusable_proof_moves",
                    "failure_boundaries",
                    "decisive_test",
                ],
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
    graph_frontier = decisive_obligation_frontier(state)
    graph_obligations = [
        {
            "debt_id": str(item.get("obligation_id") or ""),
            "obligation": str(item.get("statement") or ""),
            "severity": str(item.get("severity") or "blocking"),
            "target_id": str(item.get("target_id") or ""),
            "graph_derived": True,
        }
        for item in graph_frontier.get("minimal_cut_obligations", [])
        if str(item.get("statement") or "").strip()
    ]
    backward = graph_obligations + [
        {
            "debt_id": str(debt.get("debt_id") or ""),
            "obligation": str(debt.get("obligation") or ""),
            "severity": str(debt.get("severity") or ""),
        }
        for debt in debts[:6]
        if str(debt.get("debt_id") or "")
        not in {str(item.get("debt_id") or "") for item in graph_obligations}
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
        "graph_obligation_frontier": graph_frontier,
        "target_id": target_id,
        "target_route_id": route_id,
        "root_statement": root_statement,
        "maximum_candidates": 3,
        "maximum_selected": 2,
        "sufficiency_precheck_required": True,
        "lemma_root_leverage_gate": {
            "required_fields": list(LEMMA_ROOT_LEVERAGE_GATE_FIELDS),
            "admission_rule": (
                "Admit a lemma only when proving it closes a major case or materially shortens the root proof, refuting it is informative, "
                "it is not stronger than necessary, it does not rename the current gap, and its hypotheses can realistically be obtained."
            ),
            "qualitative_not_hidden_solution_score": True,
        },
        "selection_policy": "prefer the weakest attainable candidate that materially reduces obligations and would close a major root case",
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
    leverage_gate = _json_object(candidate.get("root_leverage_gate"))
    closes = 1.0 if precheck.get("would_reach_root") or precheck.get("would_close_route") else 0.0
    if leverage_gate.get("if_proved_major_case") is True:
        closes = max(closes, 0.85)
    leverage = float(candidate.get("estimated_root_leverage") or 0.0)
    difficulty = float(candidate.get("estimated_difficulty") or 0.0)
    hidden = len(_json_list(candidate.get("hidden_obligations")) or _json_list(precheck.get("hidden_obligations")))
    attainable = 0.0 if leverage_gate.get("hypotheses_attainable") is False else 0.15
    informative_refutation = 0.1 if leverage_gate.get("if_refuted_information_gain") is True else 0.0
    overstrong = 0.5 if leverage_gate.get("stronger_than_necessary") is True else 0.0
    gap_rename = 0.8 if leverage_gate.get("renames_current_gap") is True else 0.0
    return (
        closes,
        leverage + attainable + informative_refutation - overstrong - gap_rename - 0.35 * difficulty - 0.08 * hidden,
        leverage,
        str(candidate.get("bridge_id") or ""),
    )


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
        and str(row.get("actor_role") or "") in {"researcher", "adversarial_reviewer", "villain", "literature_researcher", "strict_informal_verifier"}
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
    root_route_ids = {
        str(route.get("route_id") or "")
        for route in state.get("routes", [])
        if str(route.get("conclusion_claim_id") or "") == "root"
        and str(route.get("relation_to_parent") or "sufficient") == "sufficient"
        and str(route.get("status") or "active") not in {"abandoned", "superseded"}
    }
    root_terminal_inferences = [
        inference
        for inference in state.get("inferences", [])
        if str(inference.get("route_id") or "") in root_route_ids
        and str(inference.get("conclusion_claim_id") or "") == "root"
    ]
    active_blockers = [
        debt
        for debt in state.get("debts", [])
        if str(debt.get("status") or "") == "active"
        and str(debt.get("severity") or "") == "blocking"
    ]
    if (
        len(substantive) >= 5
        and not root_terminal_inferences
        and len(active_blockers) >= max(8, 2 * max(1, len(verified_claims)))
    ):
        reasons.append("blocking_debt_growth_without_root_assembly")
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
    program_view = proof_program_view(state)
    root_programs = [
        row
        for row in program_view.get("programs", [])
        if str(row.get("target_id") or "") == "root"
        and str(row.get("route_id") or "")
    ]
    philosophies = {
        normalize_text(str(row.get("proof_philosophy") or ""))
        for row in root_programs
        if str(row.get("proof_philosophy") or "").strip()
    }
    proof_shaped_artifacts = [
        artifact
        for artifact in _artifact_rows(state)
        if str(artifact.get("artifact_type") or "") in {"proof_dossier", "proof_blueprint", "proof_compression"}
    ]
    mature_program_review = len(substantive) >= 3 or len(proof_shaped_artifacts) >= 2
    if mature_program_review and len(root_programs) >= 2 and len(philosophies) >= 2:
        reasons.append("multiple_root_proof_philosophies_need_comparison")
    if mature_program_review and root_programs and all(
        str(row.get("case_coverage_status") or "") != "exhaustive"
        for row in root_programs
    ):
        reasons.append("root_case_coverage_not_exhaustive")
    threat_view = threat_propagation_view(state)
    if threat_view.get("pending_revalidation_routes"):
        reasons.append("certified_dependency_threat_requires_revalidation")
    debt_frontier = minimal_active_debt_frontier(state)
    if len(substantive) >= 3 and debt_frontier.get("alias_to_primary"):
        reasons.append("semantic_debt_aliases_need_one_canonical_program")
    successful_research = [
        run
        for run in substantive
        if str(run.get("actor_role") or "") == "researcher"
    ]
    target_counts: Dict[str, int] = {}
    for run in successful_research[:8]:
        target_id = str(run.get("target_id") or "root")
        target_counts[target_id] = target_counts.get(target_id, 0) + 1
    repeated_targets = sorted(target_id for target_id, count in target_counts.items() if count >= 3)
    if repeated_targets:
        verifier_targets = {
            str(run.get("target_id") or "root")
            for run in recent_runs
            if str(run.get("actor_role") or "") == "strict_informal_verifier"
            and str(run.get("status") or "").lower() not in {"failed", "error", "cancelled", "timeout"}
        }
        if any(target_id not in verifier_targets for target_id in repeated_targets):
            reasons.append("repeated_research_without_verifier_handoff")
    if len(substantive) >= 15:
        reasons.append("meaningful_action_cadence")
    if latest:
        valid_until = int(latest["metadata"].get("valid_until_revision") or latest_revision + 12)
        major_new_event = any(
            reason in reasons
            for reason in {
                "central_bridge_refuted",
                "certified_dependency_threat_requires_revalidation",
                "multiple_root_proof_philosophies_need_comparison",
                "repeated_research_without_verifier_handoff",
            }
        ) or any(
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
        "evidence_based_only": True,
        "wall_clock_trigger_used": False,
        "long_proofs_may_continue": True,
        "proof_program_count": int(program_view.get("program_count") or 0),
        "pending_threat_revalidation_count": len(threat_view.get("pending_revalidation_routes") or []),
        "minimal_active_debt_frontier_count": int(debt_frontier.get("minimal_frontier_count") or 0),
    }


def _compression_is_fresh_for_trigger(state: Mapping[str, Any], trigger: Mapping[str, Any]) -> bool:
    compression = latest_artifact(state, "proof_compression")
    if not compression:
        return False
    return int(compression.get("state_revision") or 0) >= int(trigger.get("latest_synthesis_revision") or -1)


def _compression_would_help(state: Mapping[str, Any]) -> bool:
    return len(state.get("claims", [])) >= 5 or len(state.get("routes", [])) >= 2 or len(state.get("debts", [])) >= 4


def _successful_local_research_runs(
    state: Mapping[str, Any], *, after_revision: int = -1
) -> list[Mapping[str, Any]]:
    global_intents = {
        "active_proof_compression",
        "proof_compression",
        "advisor_global_synthesis",
        CONCEPTUAL_INVARIANT_INTENT,
        "global_synthesis",
        "near_solution_spine_synthesis",
    }
    return [
        run
        for run in state.get("recent_runs", [])
        if int(run.get("state_revision") or 0) > after_revision
        and str(run.get("actor_role") or "") == "researcher"
        and str(run.get("mode") or "") in {"prove", "reduce", "strengthen", "weaken"}
        and str(run.get("status") or "").lower() not in {"failed", "error", "cancelled", "timeout"}
        and str(run.get("search_intent") or "") not in global_intents
    ]


def conceptual_invariant_trigger(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Ask for a global mathematical object after repeated local formalism.

    This is deliberately event-driven rather than a rigid round-robin.  A
    conceptual pass becomes due only after a compressed proof picture exists
    and at least two later local attacks have not closed the decisive gap.
    """
    compression = latest_artifact(state, "proof_compression")
    if not compression:
        return {"due": False, "reason": "canonical proof picture not yet available"}
    latest_concept = latest_conceptual_invariant_artifact(state)
    compression_revision = int(compression.get("state_revision") or 0)
    concept_revision = int(latest_concept.get("state_revision") or -1) if latest_concept else -1
    current_revision = int(state.get("problem_state", {}).get("current_revision") or 0)
    if latest_concept and current_revision - concept_revision < CONCEPTUAL_INVARIANT_COOLDOWN_REVISIONS:
        return {"due": False, "reason": "conceptual invariant pass is still fresh"}
    local_runs = _successful_local_research_runs(
        state, after_revision=max(compression_revision, concept_revision)
    )
    target_counts: Dict[str, int] = {}
    for run in local_runs:
        target_id = str(run.get("target_id") or "root")
        target_counts[target_id] = target_counts.get(target_id, 0) + 1
    target_id = max(target_counts, key=target_counts.get) if target_counts else "root"
    repeated_same_formalism = target_counts.get(target_id, 0) >= CONCEPTUAL_INVARIANT_LOCAL_PASS_THRESHOLD
    shared_obstruction = False
    obstruction_routes: Dict[str, set[str]] = {}
    for route in state.get("routes", []):
        fingerprint = str(route.get("failure_fingerprint") or "")
        if fingerprint and str(route.get("status") or "") in {"active", "blocked"}:
            obstruction_routes.setdefault(fingerprint, set()).add(str(route.get("route_id") or ""))
    shared_obstruction = any(len(route_ids) >= 2 for route_ids in obstruction_routes.values())
    due = repeated_same_formalism or shared_obstruction
    return {
        "due": due,
        "reason": (
            "repeated local attacks should be compressed by one conceptual invariant"
            if repeated_same_formalism
            else "multiple routes share one obstruction that may have a common invariant explanation"
            if shared_obstruction
            else "local attacks have not yet justified a conceptual pass"
        ),
        "target_id": target_id,
        "local_pass_count": len(local_runs),
        "canonical_picture_artifact_id": str(compression.get("artifact_id") or ""),
        "latest_concept_artifact_id": str(latest_concept.get("artifact_id") or "") if latest_concept else "",
    }


def research_cycle_state(state: Mapping[str, Any]) -> Dict[str, Any]:
    recent = [
        run
        for run in state.get("recent_runs", [])
        if str(run.get("status") or "").lower() not in {"failed", "error", "cancelled", "timeout"}
    ][:8]
    phases: list[str] = []
    for run in recent:
        intent = str(run.get("search_intent") or "")
        mode = str(run.get("mode") or "")
        if intent in {"active_proof_compression", "proof_compression", "near_solution_spine_synthesis"}:
            phase = "global_assembly"
        elif intent == CONCEPTUAL_INVARIANT_INTENT:
            phase = "conceptual_comparison"
        elif mode == "refute" or "counterexample" in intent:
            phase = "adversarial_probe"
        elif mode in {"triage_routes", "regulate_decomposition"}:
            phase = "strategic_decision"
        elif mode in {"prove", "reduce", "strengthen", "weaken"}:
            phase = "local_attack"
        else:
            continue
        if not phases or phases[-1] != phase:
            phases.append(phase)
    trigger = conceptual_invariant_trigger(state)
    return {
        "recent_distinct_phases": phases[:5],
        "conceptual_invariant_due": bool(trigger.get("due")),
        "policy": (
            "Alternate deep local proof, global assembly, adversarial probe, conceptual comparison, and strategic decision when evidence changes; "
            "do not repeat one formalism merely to satisfy a fixed cycle."
        ),
    }


def _protected_primary_action(action: Mapping[str, Any]) -> bool:
    mode = str(action.get("mode") or "")
    if mode in {"integrate", "formalize", "validate_counterexample", "write", "review_writing", "await_human", "stop_solved", "stop_with_partial_results"}:
        return True
    if str(action.get("search_intent") or "") == "branch_nearby_lemma":
        return True
    if mode == "retrieve" and (
        action.get("retrieval_required")
        or action.get("citation_certification_required")
        or action.get("citation_triage_required")
        or action.get("source_certification_packet_required")
    ):
        return True
    research_route_action = bool(
        action.get("bottleneck_lock_required")
        or action.get("bridge_lemma_workbench_required")
        or action.get("hard_theorem_attack_required")
        or action.get("creative_proof_attack_required")
        or action.get("proof_construction_required")
    )
    if mode == "prove" and (
        action.get("citation_certification_required")
        or action.get("citation_triage_required")
        or (action.get("route_id") and not research_route_action)
    ):
        return True
    if mode in {"triage_routes", "regulate_decomposition"}:
        return True
    return bool(
        action.get("proof_repair_verification_required")
        or (action.get("proof_repair_required") and not research_route_action)
        or action.get("root_alignment_audit")
        or (action.get("debt_id") and not research_route_action)
        or action.get("branch_persistence")
        or action.get("nearby_lemma_directive")
        or action.get("parallel_wave_summary")
        or action.get("retrieve_reduce_loop_guard")
        or action.get("source_adaptation_digest_required")
        or (action.get("research_synthesis_required") and not action.get("creative_proof_attack_required"))
        or action.get("global_synthesis_required")
        or action.get("advisor_evidence_synthesis_required")
    )


def _approach_strategy_operation(brainstorming: Mapping[str, Any]) -> Dict[str, Any]:
    kind = str(brainstorming.get("kind") or "initial")
    operation = "approach_portfolio_refresh" if kind == "refresh" else "approach_portfolio_brainstorming"
    alignment = dict(brainstorming.get("approach_alignment") or {})
    return {
        "_candidate_generator_id": "approach_portfolio",
        "operation": operation,
        "mode": "reduce",
        "target_id": "root",
        "route_id": "",
        "search_intent": APPROACH_REFRESH_INTENT if kind == "refresh" else APPROACH_PORTFOLIO_INTENT,
        "reason": str(brainstorming.get("reason") or "compare globally different approaches before local work"),
        "approach_brainstorming_required": True,
        "approach_portfolio_required": True,
        "approach_portfolio_kind": kind,
        "approach_candidate_minimum": int(
            brainstorming.get("candidate_minimum") or (6 if kind == "initial" else 3)
        ),
        "approach_candidate_maximum": 12,
        "approach_selection_minimum": 2,
        "approach_selection_maximum": 3,
        "supersedes_artifact_id": str(brainstorming.get("supersedes_artifact_id") or ""),
        "bottleneck_lease": dict(brainstorming.get("bottleneck_lease") or {}),
        "approach_alignment": alignment,
        "exclusive_wave_required": bool(brainstorming.get("alignment_required")),
        "proof_claim_creation_forbidden": True,
        "blocking_proof_debt_creation_forbidden": True,
        "nonblocking_research_questions_allowed": True,
        "research_question_debt_cap": 6,
        "research_question_debt_types": [
            "conceptual_question",
            "representation_question",
            "counterexample_program",
            "experiment_question",
            "source_question",
            "possible_bridge",
        ],
        "verification_authority": False,
        "deep_research_required": False,
        "long_mathematical_session_required": False,
        "preferred_work_mode": "offline",
        "research_philosophy": "global_approach_generation",
        "research_attack_stage": "breadth_first",
    }


def strategy_operation_candidates(
    state: Mapping[str, Any],
    primary_action: Mapping[str, Any],
    *,
    steering_alignment: Optional[Mapping[str, Any]] = None,
) -> list[Dict[str, Any]]:
    """Materialize every admissible top-level research-strategy operation.

    The previous function returned at the first matching branch.  That hid
    simultaneous alternatives from the scheduler and made later branches
    impossible to audit.  Order here records the historical precedence only;
    the scheduler compares the returned operations explicitly.
    """

    brainstorming = approach_brainstorming_trigger(
        state,
        primary_action,
        steering_alignment=steering_alignment,
    )
    candidates: list[Dict[str, Any]] = []
    protected_alignment_modes = {
        "integrate",
        "formalize",
        "validate_counterexample",
        "stop_with_partial_results",
        "stop_solved",
        "await_human",
    }
    if (
        brainstorming.get("due")
        and brainstorming.get("alignment_required")
        and str(primary_action.get("mode") or "") not in protected_alignment_modes
    ):
        return [_approach_strategy_operation(brainstorming)]
    if _protected_primary_action(primary_action):
        return []
    reference = reference_solution_state(state)
    if reference.get("pending_reconstruction"):
        candidates.append({
            "_candidate_generator_id": "reference_solution_reconstruction",
            "operation": "reference_solution_reconstruction",
            "mode": "reduce",
            "target_id": "root",
            "route_id": str(primary_action.get("route_id") or ""),
            "search_intent": REFERENCE_RECONSTRUCTION_INTENT,
            "reason": (
                "a human-supplied reference solution must be reconstructed into the local proof graph "
                "before independent search repeats solved architecture"
            ),
            "reference_solution_reconstruction_required": True,
            "reference_solution": reference,
            "canonical_full_proof_reconstruction_required": True,
            "proof_spine_mode_required": True,
            "theorem_preflight_required": True,
            "case_coverage_map_required": True,
            "deep_research_required": True,
            "long_mathematical_session_required": True,
            "verification_authority": False,
            "preferred_work_mode": "offline",
        })
    if brainstorming.get("due"):
        candidates.append(_approach_strategy_operation(brainstorming))
    approach = selected_approach_candidate(state)
    if approach:
        approach_id = str(approach.get("approach_id") or "")
        candidates.append({
            "_candidate_generator_id": "approach_pilot",
            "operation": "approach_pilot",
            "mode": "reduce",
            "target_id": str(approach.get("target_id") or primary_action.get("target_id") or "root"),
            "route_id": str(approach.get("target_route_id") or primary_action.get("route_id") or ""),
            "search_intent": f"{APPROACH_PILOT_INTENT_PREFIX}{approach_id}",
            "reason": f"run the decisive low-cost test for selected approach {approach_id} before committing to local proof construction",
            "selected_approach": approach,
            "approach_pilot_required": True,
            "decisive_test_required": True,
            "root_consequence_required": True,
            "proof_claim_creation_forbidden_unless_test_succeeds": True,
            "preferred_work_mode": "cas" if str(approach.get("estimated_cost") or "") == "low" and approach.get("computational_probe") else "offline",
            "research_philosophy": str(approach.get("mechanism") or "selected_approach_pilot"),
        })
    fingerprints = _claim_statement_fingerprints(state)
    bridge = selected_bridge_candidate(state)
    if bridge and fingerprint_text(str(bridge.get("statement") or "")) not in fingerprints:
        candidates.append({
            "_candidate_generator_id": "selected_bridge",
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
        })
    conjecture = selected_conjecture_candidate(state)
    if conjecture and fingerprint_text(str(conjecture.get("statement") or "")) not in fingerprints:
        experiment = _candidate_needs_experiment(conjecture)
        candidates.append({
            "_candidate_generator_id": "selected_conjecture",
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
        })
    conceptual = conceptual_invariant_trigger(state)
    if conceptual.get("due"):
        candidates.append({
            "_candidate_generator_id": "conceptual_invariant",
            "operation": "conceptual_invariant_discovery",
            "mode": "reduce",
            "target_id": str(conceptual.get("target_id") or "root"),
            "route_id": str(primary_action.get("route_id") or ""),
            "search_intent": CONCEPTUAL_INVARIANT_INTENT,
            "reason": str(conceptual.get("reason") or "repeated local work needs a conceptual invariant"),
            "conceptual_invariant_discovery_required": True,
            "conceptual_invariant_trigger": conceptual,
            "deep_research_required": True,
            "long_mathematical_session_required": True,
            "analogy_pass_required": True,
            "counterexample_probe_required": True,
            "research_philosophy": "conceptual_invariant",
            "research_attack_stage": "deep",
            "preferred_work_mode": "offline",
        })
    authorization = active_invention_authorization(state)
    if authorization:
        candidates.append({
            "_candidate_generator_id": "definition_invention",
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
        })
    trigger = advisor_synthesis_trigger(state)
    if trigger.get("due"):
        if _compression_would_help(state) and not _compression_is_fresh_for_trigger(state, trigger):
            candidates.append({
                "_candidate_generator_id": "proof_compression",
                "operation": "proof_compression",
                "mode": "reduce",
                "target_id": "root",
                "route_id": str(primary_action.get("route_id") or ""),
                "search_intent": "active_proof_compression",
                "reason": "compress the current proof architecture before the due global advisor synthesis",
                "proof_compression_operation_required": True,
                "canonical_full_proof_reconstruction_required": True,
                "proof_spine_mode_required": True,
                "deep_research_required": True,
                "long_mathematical_session_required": True,
                "research_philosophy": "global_assembly",
                "research_attack_stage": "deep",
                "synthesis_trigger": trigger,
                "preferred_work_mode": "offline",
            })
        else:
            candidates.append({
                "_candidate_generator_id": "advisor_synthesis",
                "operation": "advisor_global_synthesis",
                "mode": "triage_routes",
                "target_id": "root",
                "route_id": str(primary_action.get("route_id") or ""),
                "search_intent": "advisor_global_synthesis",
                "reason": "persisted research-state triggers require a global PhD-advisor synthesis",
                "advisor_global_synthesis_required": True,
                "global_synthesis_required": True,
                "synthesis_trigger": trigger,
            })
    return candidates


def next_strategy_operation(
    state: Mapping[str, Any],
    primary_action: Mapping[str, Any],
    *,
    steering_alignment: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Compatibility view returning the historically first strategy operation."""

    candidates = strategy_operation_candidates(
        state,
        primary_action,
        steering_alignment=steering_alignment,
    )
    return candidates[0] if candidates else None


def _target_root_impact(state: Mapping[str, Any], target_id: str) -> float:
    if target_id == "root":
        return 1.0
    claim = _claim_for_id(state, target_id)
    if not claim:
        return 0.3

    root_route_ids = {
        str(route.get("route_id") or "")
        for route in state.get("routes", [])
        if str(route.get("conclusion_claim_id") or "") == "root"
        and str(route.get("relation_to_parent") or "sufficient") == "sufficient"
        and str(route.get("status") or "active") not in {"abandoned", "superseded"}
    }
    for inference in state.get("inferences", []):
        if str(inference.get("route_id") or "") not in root_route_ids:
            continue
        dependencies = {
            str(item)
            for item in [
                *_json_list(inference.get("premise_claim_ids") or inference.get("premise_claim_ids_json")),
                *_json_list(inference.get("condition_claim_ids") or inference.get("condition_claim_ids_json")),
            ]
        }
        if target_id in dependencies:
            return 0.9

    parent_ids = {
        str(item)
        for item in _json_list(claim.get("parent_ids") or claim.get("parent_ids_json"))
    }
    if "root" in parent_ids or int(claim.get("reduction_depth") or 99) <= 1:
        return 0.55
    # Self-reported root impact remains a weak tie-breaker only; an unplaced
    # lemma cannot score like an assembled premise of the root theorem.
    return min(0.4, max(0.1, float(claim.get("root_impact") or 0.3)))


def score_action(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    """Return an auditable ordinal priority assessment.

    The former implementation emitted decimal "probabilities" and
    "expected values" that were constants chosen by the authors, not measured
    estimates.  This version exposes the exact ordinal rules used by the
    scheduler and keeps empirical run history in a separately labelled,
    non-calibrated adjustment.
    """

    mode = str(action.get("mode") or "")
    target_id = str(action.get("target_id") or "root")
    search_intent = str(action.get("search_intent") or "")
    is_experiment = bool(action.get("experiment_workflow_required")) or search_intent == "experiment_conjecture_proof"
    is_verification = mode in {"integrate", "formalize", "validate_counterexample"} or (mode == "prove" and bool(action.get("route_id")))
    closure_priority = 4 if is_verification else 3 if target_id == "root" and mode in {"prove", "reduce"} else 2
    if action.get("selected_bridge_promotion_required"):
        closure_priority = max(closure_priority, 3)
    refutation_priority = 4 if mode in {"refute", "validate_counterexample"} else 3 if is_experiment else 1
    root_impact = min(1.0, max(0.0, _target_root_impact(state, target_id)))
    root_relevance_level = 4 if target_id == "root" else 3 if root_impact >= 0.7 else 2 if root_impact >= 0.35 else 1
    information_priority = 4 if is_experiment or mode in {"triage_routes", "regulate_decomposition"} else 2
    if action.get("approach_brainstorming_required"):
        closure_priority = 1
        refutation_priority = 2
        information_priority = 4
        root_relevance_level = max(root_relevance_level, 3)
    selected_approach = _json_object(action.get("selected_approach"))
    if selected_approach:
        contribution = max(0, min(5, int(selected_approach.get("contribution_level") or 0)))
        closure_priority = max(closure_priority, 1 + min(3, contribution // 2))
        information_priority = max(information_priority, 3)
        root_relevance_level = max(root_relevance_level, min(4, max(1, contribution)))
    reference_used = bool(reference_solution_state(state).get("available"))
    reuse_priority = (
        4
        if action.get("reference_solution_reconstruction_required")
        else 4
        if action.get("proof_compression_operation_required")
        else 3
        if action.get("advisor_global_synthesis_required")
        else 1
    )
    duplicate_count = sum(
        1
        for run in state.get("recent_runs", [])[:8]
        if str(run.get("target_id") or "") == target_id
        and str(run.get("search_intent") or "") == search_intent
        and search_intent
    )
    duplication_penalty = min(4, duplicate_count)
    budget = _json_object(action.get("budget"))
    requested = int(action.get("requested_tokens") or budget.get("requested_tokens") or budget.get("planned_tokens") or 0)
    token_cost_level = 4 if requested >= 250_000 else 3 if requested >= 100_000 else 2 if requested >= 25_000 else 1
    execution_cost_level = 4 if is_experiment else 3 if action.get("deep_session_required") else 2
    verification_cost_level = 1 if is_verification else 3 if action.get("definition_invention_required") else 2
    outcome_learning = verifier_filtered_outcome_learning(state, action)
    outcome_adjustment = float(
        outcome_learning.get("current_family", {}).get("heuristic_score_adjustment") or 0.0
    )
    compact_outcome_learning = {
        "outcome_learning_version": outcome_learning.get("outcome_learning_version"),
        "policy": outcome_learning.get("policy"),
        "reference_solution_used": reference_used,
        "private_cross_problem_cache_used": False,
        "current_strategy_family": outcome_learning.get("current_strategy_family", ""),
        "current_family": outcome_learning.get("current_family", {}),
    }
    priority = (
        4 * closure_priority
        + 3 * root_relevance_level
        + 2 * information_priority
        + refutation_priority
        + reuse_priority
        - 3 * duplication_penalty
        - token_cost_level
        - execution_cost_level
        - verification_cost_level
        + outcome_adjustment
    )
    return {
        "priority_assessment_version": 2,
        "scale": "ordinal levels 1 (low) through 4 (high); not probabilities or expected values",
        "closure_priority": closure_priority,
        "refutation_priority": refutation_priority,
        "root_relevance_level": root_relevance_level,
        "graph_root_impact_tiebreaker": round(root_impact, 3),
        "information_priority": information_priority,
        "reuse_priority": reuse_priority,
        "duplicate_recent_attempts": duplicate_count,
        "duplication_penalty": duplication_penalty,
        "requested_tokens": requested,
        "token_cost_level": token_cost_level,
        "execution_cost_level": execution_cost_level,
        "verification_cost_level": verification_cost_level,
        "scheduler_priority": round(priority, 4),
        "calibrated_probability": False,
        "descriptive_outcome_summary": compact_outcome_learning,
        # Compatibility alias for persisted dashboards written before schema
        # v4. The payload itself explicitly states that it is not causal.
        "causal_outcome_summary": compact_outcome_learning,
        "outcome_heuristic_adjustment": round(outcome_adjustment, 4),
        "reference_solution_used": reference_used,
        "rotation_tie_break_active": False,
        "rotation_tie_break_rule": (
            "no work-mode tie-break is applied at this score layer; the scheduler's "
            "persisted bounded-deferral rule governs top-level rotation"
        ),
        "protected_verification_budget": "never charged to speculative research actions",
    }


def _deep_session_context(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    if action.get("approach_brainstorming_required") or action.get("approach_pilot_required"):
        return {}
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
    if action.get("conceptual_invariant_discovery_required"):
        eligible_reason = "conceptual_invariant_discovery"
    elif action.get("canonical_full_proof_reconstruction_required"):
        eligible_reason = "canonical_full_proof_reconstruction"
    elif action.get("selected_bridge_promotion_required") or action.get("bridge_lemma_workbench_required"):
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
    roi = deep_session_roi(state, action)
    if not roi.get("allowed"):
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
        "roi_gate": roi,
        "branch_budget_policy": (
            "one coherent long session; persist only a mathematical proof-state delta; ordinary patch and verification gates still apply"
        ),
        "required_deliverable": {
            "preferred_artifact_type": "proof_dossier",
            "fallback_artifact_type": "deep_session_report",
            "fallback_rule": "use deep_session_report only when it carries a productive mathematical delta",
            "strategy_schema_version": STRATEGY_SCHEMA_VERSION,
            "deep_session_roi_version": DEEP_SESSION_ROI_VERSION,
            "fields": [
                "strategy_schema_version",
                "deep_session_roi_version",
                "mathematical_delta_kind",
                "mathematical_delta_summary",
                "changed_proof_state",
                "next_philosophy_if_stalled",
                "complete_local_argument",
                "independent_proof_attacks",
                "candidate_lemmas",
                "failed_approaches",
                "new_obstructions",
                "source_adaptations",
                "analogy_or_neighboring_theorem_comparison",
                "full_proof_assembly_attempt",
                "proposed_route_revision",
                "next_decisive_step",
                "state_patch_operations",
            ],
            "field_rules": {
                "candidate_lemmas": "nonempty list; include at least one exact local lemma, hypothesis, or falsifiable subclaim from this session",
                "independent_proof_attacks": "at least two materially different proof attacks, unless the first closes the target",
                "failed_approaches": "nonempty list",
                "new_obstructions": "nonempty list",
                "source_adaptations": "list; may be empty in an offline session",
                "analogy_or_neighboring_theorem_comparison": "nonempty comparison with an explicit object and hypothesis dictionary",
                "full_proof_assembly_attempt": "nonempty attempt to place the local result into the entire root proof",
                "state_patch_operations": "nonempty list",
                "mathematical_delta_kind": "one of: " + " | ".join(sorted(PRODUCTIVE_DELTA_KINDS)),
                "changed_proof_state": "must be true; a management-only report is not progress and must not be persisted",
            },
        },
        "verification_authority": False,
        "unrelated_result_directories_forbidden": True,
    }


def enrich_action(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    enriched = dict(action)
    # A direct ``prove`` action without a route is researcher-owned.  The
    # root-cut gate may later attach the decisive route to that action.  If it
    # leaves the mode as ``prove``, actor_role_for_action reclassifies the
    # session as a strict verifier even though the payload is still a
    # researcher proof-construction/route-conversion task.  Besides giving the
    # verifier the wrong packet, each gap report advances the proof-state
    # revision and can create an unbounded verifier loop.  Remember the
    # original ownership before any retargeting and preserve it below.
    direct_researcher_prove = (
        str(enriched.get("mode") or "") == "prove"
        and not str(enriched.get("route_id") or "")
        and not any(
            enriched.get(flag)
            for flag in (
                "citation_certification_required",
                "citation_triage_required",
                "paper_audit_document_review_required",
                "proof_repair_verification_required",
                "verify_ready_route_policy",
                "strict_verifier_scope",
            )
        )
    )
    program_view = proof_program_view(state)
    threat_view = threat_propagation_view(state)
    debt_frontier = minimal_active_debt_frontier(state)
    workspace = long_session_workspace(state, enriched)
    enriched["proof_program_view"] = program_view
    enriched["case_coverage_map"] = {
        "programs": [
            {
                "program_id": row.get("program_id", ""),
                "route_id": row.get("route_id", ""),
                "covered_cases": row.get("covered_cases", []),
                "open_cases": row.get("open_cases", []),
                "cases_exhaustive": bool(row.get("cases_exhaustive")),
                "status": row.get("case_coverage_status", "unspecified"),
            }
            for row in program_view.get("programs", [])
        ],
        "exhaustiveness_required_for_root_closure": True,
    }
    enriched["threat_propagation"] = threat_view
    enriched["minimal_active_debt_frontier"] = debt_frontier
    enriched["long_session_workspace"] = workspace
    enriched["root_leverage_metrics"] = root_leverage_metrics(state)
    portfolio = approach_portfolio_view(state)
    if portfolio.get("artifact_id") or enriched.get("approach_brainstorming_required"):
        enriched["approach_portfolio"] = portfolio
    if enriched.get("bottleneck_lock_required") or enriched.get("approach_brainstorming_required"):
        enriched["bottleneck_lease"] = {
            **bottleneck_lease_state(state, enriched),
            **dict(enriched.get("bottleneck_lease") or {}),
        }
    selected_debt_obligation = _selected_action_debt_obligation(state, enriched)
    # These three action views share the same mathematical cut.  Construct it
    # once for this immutable scheduler snapshot so enrichment cannot repeat a
    # graph-wide frontier computation under different field names.
    graph_frontier = decisive_obligation_frontier(state)
    cut_gate = root_cut_progress_gate(
        state, obligation_frontier=graph_frontier
    )
    if selected_debt_obligation:
        cut_gate = _align_frontier_to_selected_debt(cut_gate, selected_debt_obligation)
    enriched["root_cut_progress_gate"] = cut_gate
    ownership = canonical_route_ownership(
        state,
        enriched,
        obligation_frontier=graph_frontier,
    )
    enriched["canonical_route_ownership"] = ownership
    if (
        cut_gate.get("active")
        and not enriched.get("approach_brainstorming_required")
        and not enriched.get("approach_pilot_required")
        and not enriched.get("strict_verifier_scope")
        and str(enriched.get("mode") or "") in {
        "prove", "reduce", "weaken", "strengthen", "triage_routes"
        }
    ):
        decisive = _json_object(cut_gate.get("decisive_obligation"))
        enriched["root_cut_consolidation_required"] = True
        enriched["claim_creation_frozen"] = True
        enriched["forbidden_outputs"] = list(
            dict.fromkeys([
                *_json_list(enriched.get("forbidden_outputs")),
                "new route-less claims",
                "parallel proof dossiers",
                "management-only inventories",
            ])
        )
        if decisive and not enriched.get("role_starvation_recovery"):
            decisive_target_id = str(decisive.get("target_id") or enriched.get("target_id") or "root")
            enriched["target_id"] = _claim_target_for_context(state, decisive_target_id)
            enriched["route_id"] = str(decisive.get("route_id") or enriched.get("route_id") or "")
            if direct_researcher_prove and enriched["route_id"]:
                enriched["mode"] = "reduce"
                enriched["display_mode"] = "researcher_prove"
                enriched["root_cut_preserved_researcher_ownership"] = True
                enriched.setdefault("proof_construction_required", True)
            enriched["reason"] = (
                "root-cut consolidation gate: close, refute, or strictly shrink the decisive obligation "
                f"{decisive.get('obligation_id') or ''} before creating another claim"
            )
    enriched["no_wall_clock_strategy_timeout"] = True
    if enriched.get("advisor_global_synthesis_required"):
        enriched["proof_program_comparison_required"] = True
        enriched["evidence_based_strategic_review_required"] = True
        enriched["strategy_review_trigger"] = enriched.get("synthesis_trigger") or {}
        enriched["continue_long_proof_when_coherent"] = True
    if selected_debt_obligation:
        graph_frontier = _align_frontier_to_selected_debt(
            graph_frontier,
            selected_debt_obligation,
        )
    enriched["decisive_obligation_frontier"] = graph_frontier
    decisive = _json_object(graph_frontier.get("decisive_obligation"))
    if decisive:
        enriched["decisive_obligation_frontier_required"] = True
        enriched["decisive_obligation_id"] = str(decisive.get("obligation_id") or "")
        enriched["decisive_obligation_target_id"] = str(decisive.get("target_id") or "")
        enriched["decisive_obligation_statement"] = str(decisive.get("statement") or "")
    if enriched.get("proof_compression_operation_required"):
        enriched["canonical_full_proof_reconstruction_required"] = True
        enriched["deep_research_required"] = True
        enriched["long_mathematical_session_required"] = True
        enriched.setdefault("research_philosophy", "global_assembly")
    if str(enriched.get("mode") or "") == "refute" or enriched.get("counterexample_search_required"):
        enriched["counterexample_probe_required"] = True
        enriched["counterexample_probe_contract"] = {
            "full_original_hypotheses_required": True,
            "competing_conjectures_required": True,
            "structural_question_required": True,
            "outcome_dependent_next_actions_required": True,
            "weakened_shadow_tests_are_diagnostic_only": True,
        }
        enriched.setdefault("research_philosophy", "adversarial_probe")
        counterexample_preflight = counterexample_preflight_state(state)
        if counterexample_preflight.get("due"):
            enriched["initial_counterexample_preflight_required"] = True
            enriched["counterexample_preflight_contract"] = counterexample_preflight
    preflight = theorem_preflight_contract(state, enriched)
    if preflight:
        enriched["theorem_preflight_required"] = True
        enriched["theorem_preflight_contract"] = preflight
        # Research passes test high-risk statements before investing in a long
        # universal proof.  Verifiers receive the same signature as an audit
        # lens but are not converted into research workers.
        verifier_like = str(enriched.get("mode") or "") in {"integrate", "formalize"} or (
            str(enriched.get("mode") or "") == "prove" and bool(enriched.get("route_id"))
        )
        if preflight.get("risk_level") == "high" and not verifier_like:
            enriched["counterexample_probe_required"] = True
            existing_probe = _json_object(enriched.get("counterexample_probe_contract"))
            enriched["counterexample_probe_contract"] = {
                **existing_probe,
                "full_original_hypotheses_required": True,
                "boundary_and_degenerate_cases_required": True,
                "outcome_dependent_next_actions_required": True,
                "management_only_artifact_forbidden": True,
            }
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
    roi = deep_session_roi(state, enriched)
    enriched["deep_session_roi"] = roi
    deep = _deep_session_context(state, enriched)
    if deep:
        enriched["deep_session_required"] = True
        enriched["deep_session"] = deep
        enriched["long_mathematical_session_required"] = True
    elif not roi.get("allowed", True):
        enriched["deep_session_suppressed"] = True
        enriched["forced_research_philosophy"] = str(roi.get("forced_next_philosophy") or "alternative_construction")
        enriched["research_philosophy"] = enriched["forced_research_philosophy"]
        enriched.pop("long_mathematical_session_required", None)
    representation_contract = representation_switch_contract(state, enriched)
    if representation_contract:
        enriched["representation_switch_required"] = True
        enriched["representation_switch_contract"] = representation_contract
    adaptation_contract = theorem_adaptation_contract(enriched)
    if adaptation_contract:
        enriched["theorem_adaptation_required"] = True
        enriched["theorem_adaptation_contract"] = adaptation_contract
    interface_contract = proof_interface_contract(enriched, state=state)
    if interface_contract:
        enriched["proof_interface_check_required"] = True
        enriched["proof_interface_contract"] = interface_contract
    enriched["research_cycle"] = research_cycle_state(state)
    enriched["priority_assessment"] = score_action(state, enriched)
    return enriched


def _selected_action_debt_obligation(
    state: Mapping[str, Any],
    action: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return the active debt that the scheduler explicitly selected.

    Enrichment adds graph-wide strategy context after the scheduler has chosen
    an action.  It must not silently retarget a bottleneck/decisive-theorem
    action to whichever debt happens to sort first in the global frontier.
    """
    candidate_ids: list[str] = []

    def add_candidate(value: Any) -> None:
        debt_id = str(value or "")
        if debt_id and debt_id not in candidate_ids:
            candidate_ids.append(debt_id)

    add_candidate(action.get("debt_id"))
    for key in ("decisive_theorem_test", "bottleneck_lock_signal", "central_obstruction"):
        add_candidate(_json_object(action.get(key)).get("debt_id"))
    if not candidate_ids:
        return {}

    coverage_index = get_debt_coverage_index(state)
    debts = {
        str(row.get("debt_id") or ""): row
        for row in state.get("debts", [])
        if str(row.get("status") or "") == "active"
    }
    for debt_id in candidate_ids:
        debt = debts.get(debt_id)
        if not debt or debt_covered_by_integrated_claim(
            state,
            debt,
            debt_coverage_index=coverage_index,
        ):
            continue
        severity = str(debt.get("severity") or "major")
        return {
            "obligation_type": "debt",
            "obligation_id": debt_id,
            "target_id": str(
                action.get("target_id")
                or debt.get("suggested_next_target")
                or debt.get("owner_id")
                or "root"
            ),
            "route_id": str(action.get("route_id") or ""),
            "severity": severity,
            "statement": str(debt.get("obligation") or ""),
            "weight": {"blocking": 5, "major": 3, "minor": 1}.get(severity, 2),
        }
    return {}


def _align_frontier_to_selected_debt(
    frontier: Mapping[str, Any],
    selected: Mapping[str, Any],
) -> Dict[str, Any]:
    aligned = dict(frontier)
    selected_id = str(selected.get("obligation_id") or "")
    obligations = [
        dict(row)
        for row in frontier.get("minimal_cut_obligations", []) or []
        if str(row.get("obligation_id") or "") != selected_id
    ]
    aligned["minimal_cut_obligations"] = [dict(selected), *obligations][:6]
    aligned["decisive_obligation"] = dict(selected)
    aligned["selected_route_id"] = str(selected.get("route_id") or "")
    if "cut_signature" in aligned:
        aligned["cut_signature"] = [
            f"{row.get('obligation_type')}:{row.get('obligation_id')}"
            for row in aligned["minimal_cut_obligations"]
            if str(row.get("obligation_id") or "")
        ]
        aligned["minimal_cut_count"] = len(aligned["minimal_cut_obligations"])
    aligned["action_selected_debt_aligned"] = True
    return aligned


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
        "single_decisive_missing_theorem": str(skeleton.get("single_decisive_missing_theorem") or ""),
        "strongest_candidate_counterexample_architecture": str(
            skeleton.get("strongest_candidate_counterexample_architecture") or ""
        ),
        "most_informative_failed_ideas": _json_list(skeleton.get("most_informative_failed_ideas"))[:3],
        "everything_else_is_background": True,
    }


def strategy_context_card(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    synthesis = latest_active_advisor_synthesis(state)
    compression = latest_artifact(state, "proof_compression")
    bridge = selected_bridge_candidate(state)
    conjecture = selected_conjecture_candidate(state)
    authorization = active_invention_authorization(state)
    conceptual = latest_artifact(state, "conceptual_invariant_report")
    approach_portfolio = approach_portfolio_view(state)
    if not approach_portfolio.get("artifact_id") and not action.get("approach_brainstorming_required"):
        approach_portfolio = {"artifact_id": "", "approach_count": 0, "approaches": []}
    bottleneck_lease = (
        bottleneck_lease_state(state, action)
        if action.get("bottleneck_lock_required") or action.get("approach_brainstorming_required")
        else {"active": False, "escape_required": False}
    )
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
        "compressed_mathematical_picture": (
            {
                "source_artifact_id": compression.get("artifact_id", ""),
                "shortest_plausible_proof_spine": _json_object(compression.get("metadata", {}).get("minimal_proof_skeleton")).get("shortest_known_route", []),
                "single_decisive_missing_theorem": _json_object(compression.get("metadata", {}).get("minimal_proof_skeleton")).get("single_decisive_missing_theorem", ""),
                "strongest_candidate_counterexample_architecture": _json_object(compression.get("metadata", {}).get("minimal_proof_skeleton")).get("strongest_candidate_counterexample_architecture", ""),
                "most_informative_failed_ideas": _json_list(_json_object(compression.get("metadata", {}).get("minimal_proof_skeleton")).get("most_informative_failed_ideas"))[:3],
                "everything_else_is_background": True,
            }
            if compression
            else {}
        ),
        "latest_conceptual_invariant_report": (
            {"artifact_id": conceptual.get("artifact_id", ""), **conceptual.get("metadata", {})}
            if conceptual
            else {}
        ),
        "lemma_root_leverage_gate": {
            "required_fields": list(LEMMA_ROOT_LEVERAGE_GATE_FIELDS),
            "qualitative_not_hidden_solution_score": True,
        },
        "research_cycle": research_cycle_state(state),
        "approach_portfolio": approach_portfolio,
        "bottleneck_lease": bottleneck_lease,
        "proof_programs": proof_program_view(state),
        "case_coverage_map": dict(action.get("case_coverage_map") or {}),
        "threat_propagation": threat_propagation_view(state),
        "minimal_active_debt_frontier": minimal_active_debt_frontier(state),
        "reference_solution": reference_solution_state(state),
        "long_session_workspace": long_session_workspace(state, action),
        "root_leverage_metrics": root_leverage_metrics(state),
        "root_cut_progress_gate": root_cut_progress_gate(state),
        "canonical_route_ownership": canonical_route_ownership(state, action),
        "counterexample_preflight": counterexample_preflight_state(state),
        "strategy_review_policy": {
            "evidence_based_only": True,
            "wall_clock_timeout": None,
            "long_proof_may_continue_indefinitely": True,
            "review_events": [
                "new contradiction or dependency threat",
                "repeated mathematical work without verifier handoff",
                "semantic debt duplication",
                "uncovered root cases",
                "multiple genuinely different proof philosophies",
            ],
        },
        "selected_bridge": bridge or {},
        "selected_conjecture": conjecture or {},
        "active_invention_authorization": (
            {"artifact_id": authorization.get("artifact_id", ""), **authorization.get("metadata", {})}
            if authorization
            else {}
        ),
        "retrieved_method_cards": retrieve_method_cards(query, limit=3),
        "decisive_obligation_frontier": decisive_obligation_frontier(state),
        "verifier_filtered_outcome_learning": verifier_filtered_outcome_learning(state, action),
        "deep_session_roi": deep_session_roi(state, action),
        "representation_switch_contract": dict(action.get("representation_switch_contract") or {}),
        "theorem_adaptation_contract": dict(action.get("theorem_adaptation_contract") or {}),
        "proof_interface_contract": dict(action.get("proof_interface_contract") or {}),
        "experiment_conjecture_proof_contract": {
            "experiment_workflow_version": 2,
            "required_fields": list(EXPERIMENT_REQUIRED_FIELDS),
            "raw_output_is_not_progress": True,
            "infinite_statement_verification_authority": False,
            "host_reproduction_required_for_programs": True,
            "decision_changed_required": True,
        },
        "action_priority_assessment": dict(action.get("priority_assessment") or {}),
        "deep_session": dict(action.get("deep_session") or {}),
    }


def strategy_observability(state: Mapping[str, Any], action: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    synthesis = latest_artifact(state, "advisor_synthesis")
    compression = latest_artifact(state, "proof_compression")
    bridge_artifact = latest_artifact(state, "bridge_lemma_search")
    conjecture_artifact = latest_artifact(state, "conjecture_portfolio")
    conceptual_artifact = latest_artifact(state, "conceptual_invariant_report")
    authorization = active_invention_authorization(state)
    approach_portfolio = approach_portfolio_view(state)
    bridge_candidates = _bridge_candidates(bridge_artifact["metadata"]) if bridge_artifact else []
    conjectures = _conjecture_candidates(conjecture_artifact["metadata"]) if conjecture_artifact else []
    selected_bridge = next((item for item in bridge_candidates if str(item.get("status") or "") == "selected"), {})
    selected_conjecture = next((item for item in conjectures if str(item.get("status") or "") == "selected"), {})
    return {
        "latest_approach_portfolio_artifact_id": str(approach_portfolio.get("artifact_id") or ""),
        "approach_portfolio": approach_portfolio,
        "bottleneck_lease": bottleneck_lease_state(state, action or {}),
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
        "latest_conceptual_invariant_artifact_id": str(conceptual_artifact.get("artifact_id") or "") if conceptual_artifact else "",
        "conceptual_invariant_trigger": conceptual_invariant_trigger(state),
        "research_cycle": research_cycle_state(state),
        "priority_assessment": dict((action or {}).get("priority_assessment") or {}),
        "decisive_obligation_frontier": decisive_obligation_frontier(state),
        "verifier_filtered_outcome_learning": verifier_filtered_outcome_learning(state, action or {}),
        "deep_session_roi": deep_session_roi(state, action or {}),
        "advisor_synthesis_trigger": advisor_synthesis_trigger(state),
        "proof_programs": proof_program_view(state),
        "threat_propagation": threat_propagation_view(state),
        "minimal_active_debt_frontier": minimal_active_debt_frontier(state),
        "reference_solution": reference_solution_state(state),
        "long_session_workspace": long_session_workspace(state, action or {}),
        "root_leverage_metrics": root_leverage_metrics(state),
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
        leverage_gate = _json_object(candidate.get("root_leverage_gate"))
        for key in LEMMA_ROOT_LEVERAGE_GATE_FIELDS:
            if key not in leverage_gate:
                errors.append(f"{prefix}.root_leverage_gate requires {key}")
        duplicate_active = fingerprint in existing_claim_fingerprints
        if duplicate_active and status != "rejected":
            errors.append(f"{prefix} duplicates an existing claim and must be rejected")
        material = bool(precheck.get("materially_reduces_gap"))
        valid = (
            material
            and not bool(precheck.get("restates_root"))
            and not bool(precheck.get("creates_more_severe_obligations"))
            and bool(leverage_gate.get("if_proved_major_case"))
            and bool(leverage_gate.get("if_refuted_information_gain"))
            and not bool(leverage_gate.get("stronger_than_necessary"))
            and not bool(leverage_gate.get("renames_current_gap"))
            and bool(leverage_gate.get("hypotheses_attainable"))
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
    failed_ideas = skeleton.get("most_informative_failed_ideas")
    if not isinstance(failed_ideas, list):
        errors.append("minimal_proof_skeleton most_informative_failed_ideas must be a list")
    elif len(failed_ideas) > 3:
        errors.append("minimal_proof_skeleton may keep at most three most_informative_failed_ideas active")
    return errors


def _validate_deep_session(metadata: Mapping[str, Any]) -> list[str]:
    errors = _require_fields(
        metadata,
        (
            "complete_local_argument",
            "independent_proof_attacks",
            "candidate_lemmas",
            "failed_approaches",
            "new_obstructions",
            "analogy_or_neighboring_theorem_comparison",
            "full_proof_assembly_attempt",
            "proposed_route_revision",
            "next_decisive_step",
            "state_patch_operations",
        ),
        prefix="deep_session_report",
    )
    if "source_adaptations" not in metadata or not isinstance(metadata.get("source_adaptations"), list):
        errors.append("deep_session_report requires source_adaptations as a list (possibly empty)")
    attacks = _json_list(metadata.get("independent_proof_attacks"))
    if len(attacks) < 2 and metadata.get("target_closed_on_first_attack") is not True:
        errors.append("deep_session_report requires at least two independent_proof_attacks unless the first closes the target")
    errors.extend(validate_deep_session_roi_metadata(metadata))
    return errors


def _validate_conceptual_invariant_report(metadata: Mapping[str, Any]) -> list[str]:
    errors = _require_fields(metadata, CONCEPTUAL_INVARIANT_REQUIRED_FIELDS, prefix="conceptual_invariant_report")
    candidates = [dict(item) for item in _json_list(metadata.get("candidate_invariants")) if isinstance(item, Mapping)]
    if not 1 <= len(candidates) <= 3:
        errors.append("conceptual_invariant_report requires one to three candidate_invariants")
        return errors
    candidate_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        prefix = f"candidate_invariants[{index}]"
        errors.extend(
            _require_fields(
                candidate,
                (
                    "invariant_id",
                    "definition",
                    "transformations_controlled",
                    "local_lemmas_subsumed",
                    "root_consequence",
                    "falsification_example",
                    "failure_modes",
                    "status",
                ),
                prefix=prefix,
            )
        )
        invariant_id = str(candidate.get("invariant_id") or "")
        if invariant_id in candidate_ids:
            errors.append(f"duplicate conceptual invariant id: {invariant_id}")
        candidate_ids.add(invariant_id)
        if len(_json_list(candidate.get("local_lemmas_subsumed"))) < 2:
            errors.append(f"{prefix} must subsume at least two existing local lemmas")
        if str(candidate.get("status") or "") not in {"selected", "viable", "rejected", "refuted"}:
            errors.append(f"{prefix} has invalid status {candidate.get('status')}")
    selected = str(metadata.get("selected_invariant_id") or "")
    if selected != "none" and selected not in candidate_ids:
        errors.append("conceptual_invariant_report selected_invariant_id must name a candidate or be none")
    return errors


def _validate_experiment(metadata: Mapping[str, Any]) -> list[str]:
    # Pre-strategy artifacts already in a database remain readable. Every new
    # versioned computation uses the reproducible v2 contract.
    if not metadata.get("experiment_workflow_version"):
        return []
    if int(metadata.get("experiment_workflow_version") or 0) != 2:
        return ["cas_experiment_report requires experiment_workflow_version=2"]
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
    if metadata.get("claims_infinite_statement_verified") is True:
        errors.append(
            "a CAS experiment may not claim that an infinite statement is verified; attach a separate proof "
            "inference and have a verifier certify its complete reduction"
        )
    request = metadata.get("reproduction_request")
    if not isinstance(request, Mapping):
        errors.append("cas_experiment_report requires reproduction_request")
    else:
        kind = str(request.get("kind") or "program").lower()
        if kind not in {"program", "manual"}:
            errors.append("reproduction_request.kind must be program or manual")
    reproduction = metadata.get("host_reproduction")
    if not isinstance(reproduction, Mapping):
        errors.append("cas_experiment_report is missing host reproduction results")
    elif isinstance(request, Mapping) and str(request.get("kind") or "program").lower() == "program":
        if reproduction.get("reproduced") is not True:
            errors.append(
                "host CAS reproduction did not match the reported output: "
                + str(reproduction.get("status") or "unknown")
            )
    if isinstance(reproduction, Mapping) and reproduction.get("proof_authority") is not False:
        errors.append("host CAS reproduction must explicitly carry proof_authority=false")
    return errors


def _validate_approach_portfolio(metadata: Mapping[str, Any], conn: sqlite3.Connection) -> list[str]:
    errors = _require_fields(
        metadata,
        ("portfolio_kind", "approaches"),
        prefix="approach_portfolio",
    )
    kind = str(metadata.get("portfolio_kind") or "")
    if kind not in {"initial", "refresh", "challenge"}:
        errors.append("approach_portfolio portfolio_kind must be initial, refresh, or challenge")
    alignment_source_ids = _unique_strings(metadata.get("alignment_source_steering_ids"))
    alignment_evidence_ids = _unique_strings(metadata.get("alignment_evidence_artifact_ids"))
    alignment_required = bool(
        alignment_source_ids
        or alignment_evidence_ids
        or "root_effect_recomputed" in metadata
        or "alignment_summary" in metadata
    )
    if alignment_required:
        errors.extend(
            _require_fields(
                metadata,
                ("alignment_summary", "root_effect_recomputed"),
                prefix="approach_portfolio steering alignment",
            )
        )
        if metadata.get("root_effect_recomputed") is not True:
            errors.append("steer-aligned approach_portfolio requires root_effect_recomputed=true")
        if not alignment_source_ids and not alignment_evidence_ids:
            errors.append(
                "steer-aligned approach_portfolio requires alignment_source_steering_ids or alignment_evidence_artifact_ids"
            )
        for artifact_id in alignment_evidence_ids:
            row = conn.execute(
                "SELECT artifact_id FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            if row is None:
                errors.append(
                    f"approach_portfolio alignment_evidence_artifact_ids contains unknown artifact {artifact_id}"
                )
    candidates = _approach_candidates(metadata)
    try:
        contract_version = int(metadata.get("portfolio_contract_version"))
    except (TypeError, ValueError):
        contract_version = -1
    if contract_version != APPROACH_PORTFOLIO_CONTRACT_VERSION:
        errors.append(
            "new approach_portfolio artifacts require portfolio_contract_version="
            f"{APPROACH_PORTFOLIO_CONTRACT_VERSION}; omitting the version may not "
            "downgrade to the legacy diversity contract"
        )
    strict_diversity = contract_version >= 2
    minimum = (6 if kind == "initial" else 3) if strict_diversity else (3 if kind == "initial" else 2)
    if not minimum <= len(candidates) <= 12:
        errors.append(f"approach_portfolio requires {minimum} to 12 approaches for portfolio_kind={kind or 'unknown'}")
        return errors
    approach_ids: set[str] = set()
    semantic_signatures: set[str] = set()
    host_signatures: list[tuple[str, set[str], str]] = []
    structural_families: set[tuple[str, str, str]] = set()
    prior_host_signatures: set[str] = set()
    prior_semantic_signatures: set[str] = set()
    for row in conn.execute(
        "SELECT metadata_json FROM artifacts WHERE artifact_type = 'approach_portfolio'"
    ):
        prior_metadata = _json_object(row["metadata_json"])
        for prior_candidate in _approach_candidates(prior_metadata):
            prior_host_signature, _prior_tokens, _prior_family = _host_approach_signature(
                prior_candidate
            )
            if prior_host_signature:
                prior_host_signatures.add(prior_host_signature)
            prior_semantic = _json_object(prior_candidate.get("semantic_signature"))
            if prior_semantic:
                prior_semantic_signatures.add(
                    normalize_text(
                        json.dumps(prior_semantic, sort_keys=True, ensure_ascii=True)
                    )
                )
    originality_statuses = {
        "established_method",
        "adaptation",
        "new_combination",
        "potentially_original",
        "retained_prior_approach",
        "unknown",
    }
    for index, candidate in enumerate(candidates):
        prefix = f"approaches[{index}]"
        errors.extend(
            _require_fields(
                candidate,
                (
                    "approach_id",
                    "title",
                    "mechanism",
                    *(("method_family", "independent_starting_point", "representation_or_invariant")
                      if strict_diversity else ()),
                    "root_consequence",
                    "decisive_test",
                    *((
                        "originality_status",
                        "originality_rationale",
                        "comparison_to_existing_work",
                    ) if strict_diversity else ()),
                    "status",
                    *(("steering_impact",) if alignment_required else ()),
                ),
                prefix=prefix,
            )
        )
        approach_id = str(candidate.get("approach_id") or "")
        if approach_id in approach_ids:
            errors.append(f"duplicate approach id: {approach_id}")
        approach_ids.add(approach_id)
        if "mathematical_objects" in candidate and not _nonempty_list(candidate.get("mathematical_objects")):
            errors.append(f"{prefix} mathematical_objects must be a nonempty list")
        if "contribution_level" in candidate:
            try:
                contribution = int(candidate.get("contribution_level"))
            except (TypeError, ValueError):
                contribution = -1
            if not 0 <= contribution <= 5:
                errors.append(f"{prefix} contribution_level must be an integer from 0 to 5")
        if (
            "contribution_kind" in candidate
            and str(candidate.get("contribution_kind") or "") not in APPROACH_CONTRIBUTION_KINDS
        ):
            errors.append(f"{prefix} has invalid contribution_kind")
        if "estimated_cost" in candidate and str(candidate.get("estimated_cost") or "") not in APPROACH_COSTS:
            errors.append(f"{prefix} estimated_cost must be low, medium, or high")
        originality_status = str(candidate.get("originality_status") or "")
        if strict_diversity and originality_status not in originality_statuses:
            errors.append(
                f"{prefix} originality_status must be one of "
                + ", ".join(sorted(originality_statuses))
            )
        if strict_diversity and "novelty_score" in candidate:
            errors.append(
                f"{prefix} may not use novelty_score; originality is not a calibrated probability"
            )
        if "confidence" in candidate and str(candidate.get("confidence") or "") not in APPROACH_CONFIDENCE_LEVELS:
            errors.append(f"{prefix} confidence must be low, medium, or high")
        if str(candidate.get("status") or "") not in APPROACH_STATUSES:
            errors.append(f"{prefix} has invalid status")
        signature = _json_object(candidate.get("semantic_signature"))
        if not signature:
            signature = {
                "mechanism": str(candidate.get("mechanism") or ""),
                "representation": str(candidate.get("representation_or_invariant") or ""),
                "proof_direction": "",
                "theorem_family": "",
                "root_obligation": str(candidate.get("bridge_statement") or candidate.get("root_consequence") or ""),
                "failure_mode": str(candidate.get("likely_failure_mode") or ""),
            }
        fingerprint = normalize_text(json.dumps(signature, sort_keys=True, ensure_ascii=True))
        if fingerprint and fingerprint in semantic_signatures:
            errors.append(f"{prefix} duplicates another semantic_signature")
        semantic_signatures.add(fingerprint)
        host_signature, host_tokens, family_key = _host_approach_signature(candidate)
        rediscovered_prior = bool(
            (host_signature and host_signature in prior_host_signatures)
            or (fingerprint and fingerprint in prior_semantic_signatures)
        )
        if rediscovered_prior and originality_status in {
            "new_combination",
            "potentially_original",
        }:
            errors.append(
                f"{prefix} duplicates a prior portfolio approach and may not be labelled "
                f"{originality_status}; use retained_prior_approach or explain a material adaptation"
            )
        if strict_diversity and host_signature and any(host_signature == prior[0] for prior in host_signatures):
            errors.append(f"{prefix} is a host-detected restatement of another approach")
        for _, prior_tokens, prior_prefix in host_signatures:
            union = host_tokens | prior_tokens
            similarity = len(host_tokens & prior_tokens) / len(union) if union else 1.0
            if strict_diversity and similarity >= 0.82:
                errors.append(
                    f"{prefix} is too similar to {prior_prefix} under the host token comparison ({similarity:.2f})"
                )
                break
        host_signatures.append((host_signature, host_tokens, prefix))
        structural_families.add(family_key)
    required_families = 4 if kind == "initial" else 3
    if strict_diversity and len(structural_families) < required_families:
        errors.append(
            f"approach_portfolio requires at least {required_families} distinct "
            "(method_family, representation, proof_direction) combinations"
        )
    selected = _unique_strings(metadata.get("selected_approach_ids"))
    if strict_diversity:
        if not 2 <= len(selected) <= 3:
            errors.append("approach_portfolio requires two or three selected_approach_ids")
    elif selected and not 1 <= len(selected) <= 3:
        errors.append("approach_portfolio accepts at most three selected_approach_ids")
    unknown = [item for item in selected if item not in approach_ids]
    if unknown:
        errors.append("approach_portfolio selected_approach_ids must name portfolio approaches")
    if strict_diversity and not str(metadata.get("selection_rationale") or "").strip():
        errors.append("approach_portfolio requires selection_rationale comparing all candidates")
    supersedes = str(metadata.get("supersedes_artifact_id") or "")
    if kind in {"refresh", "challenge"} and not supersedes:
        errors.append("refreshed approach_portfolio requires supersedes_artifact_id")
    if supersedes:
        row = conn.execute(
            "SELECT artifact_type FROM artifacts WHERE artifact_id = ?",
            (supersedes,),
        ).fetchone()
        if row is None or str(row[0]) != "approach_portfolio":
            errors.append("approach_portfolio supersedes_artifact_id must name an existing approach_portfolio")
    questions = metadata.get("research_questions", [])
    if not isinstance(questions, list):
        errors.append("approach_portfolio research_questions must be a list")
    return errors


def _host_approach_signature(candidate: Mapping[str, Any]) -> tuple[str, set[str], tuple[str, str, str]]:
    """Compute an operator-preserving diversity signature independently."""

    semantic = _json_object(candidate.get("semantic_signature"))
    method = canonical_math_text(str(candidate.get("method_family") or ""))
    representation = canonical_math_text(str(candidate.get("representation_or_invariant") or ""))
    direction = canonical_math_text(str(semantic.get("proof_direction") or "other"))
    text = canonical_math_text(
        "\n".join(
            str(candidate.get(field) or "")
            for field in (
                "method_family",
                "independent_starting_point",
                "mechanism",
                "representation_or_invariant",
                "bridge_statement",
                "root_consequence",
                "decisive_test",
            )
        )
    )
    tokens = set(re.findall(r"[\w]+|[^\w\s]", text, flags=re.UNICODE))
    signature = fingerprint_text(text) if text else ""
    return signature, tokens, (method, representation, direction)


def strategic_artifact_errors(
    conn: sqlite3.Connection,
    *,
    artifact_type: str,
    metadata: Mapping[str, Any],
    content: Any = None,
    actor_role: str,
    base_revision: int,
) -> list[str]:
    errors: list[str] = []
    errors.extend(
        validate_state_independent_artifact_metadata(
            artifact_type=artifact_type,
            metadata=metadata,
            content=content,
        )
    )
    if artifact_type in {"proof_dossier", "proof_blueprint"} and int(
        metadata.get("canonical_route_owner_version") or 0
    ) == CANONICAL_ROUTE_OWNER_VERSION:
        for field in (
            "canonical_route_id",
            "root_implication_update",
            "root_cut_signature_before",
            "root_cut_signature_after",
            "creates_parallel_dossier",
        ):
            if field not in metadata or metadata.get(field) in (None, ""):
                errors.append(f"canonical route dossier requires {field}")
        if metadata.get("creates_parallel_dossier") is not False:
            errors.append("canonical route dossier requires creates_parallel_dossier=false")
        supersedes = str(metadata.get("supersedes_artifact_id") or "")
        if supersedes:
            row = conn.execute(
                "SELECT artifact_id FROM artifacts WHERE artifact_id = ?",
                (supersedes,),
            ).fetchone()
            if row is None:
                errors.append("canonical route dossier supersedes_artifact_id must name an existing artifact")
    allowed_roles = {
        "approach_portfolio": {"researcher"},
        "advisor_synthesis": {"phd_advisor", "advisor"},
        "invention_authorization": {"phd_advisor", "advisor"},
        "bridge_lemma_search": {"researcher"},
        "conjecture_portfolio": {"researcher", "adversarial_reviewer", "villain"},
        "definition_candidate": {"researcher"},
        "deep_session_report": {"researcher"},
        "proof_compression": {"researcher", "phd_advisor", "advisor"},
        "conceptual_invariant_report": {"researcher"},
    }
    if artifact_type in allowed_roles and actor_role not in allowed_roles[artifact_type]:
        errors.append(f"{actor_role} cannot attach {artifact_type}; expected {', '.join(sorted(allowed_roles[artifact_type]))}")
    if artifact_type in STRATEGIC_ARTIFACT_TYPES and int(metadata.get("strategy_schema_version") or 0) != STRATEGY_SCHEMA_VERSION:
        errors.append(f"{artifact_type} requires strategy_schema_version={STRATEGY_SCHEMA_VERSION}")
    if artifact_type == "approach_portfolio":
        errors.extend(_validate_approach_portfolio(metadata, conn))
    elif artifact_type == "bridge_lemma_search":
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
    elif artifact_type == "conceptual_invariant_report":
        errors.extend(_validate_conceptual_invariant_report(metadata))
    elif artifact_type == "cas_experiment_report":
        errors.extend(_validate_experiment(metadata))
    return errors
