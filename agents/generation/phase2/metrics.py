from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from .budget import summarize_runs
from .graph_policy import (
    DebtCoverageIndex,
    claim_is_retired,
    claim_is_verified,
    debt_covered_by_integrated_claim,
)
from .models import json_loads
from .research_strategy import root_leverage_metrics
from .store import ProofStateStore


def compute_metrics(
    store: ProofStateStore,
    *,
    state: Dict[str, Any] | None = None,
    debt_coverage_index: DebtCoverageIndex | None = None,
) -> Dict[str, Any]:
    state = state if state is not None else store.get_state()
    debt_coverage_index = debt_coverage_index or DebtCoverageIndex(state)
    claims = state["claims"]
    routes = state["routes"]
    debts = state["debts"]
    runs = state["runs"]
    artifacts = state.get("artifacts", [])
    problem = state["problem_state"]
    active_debts = [row for row in debts if row["status"] == "active"]
    open_debts = [
        row for row in active_debts
        if not debt_covered_by_integrated_claim(
            state,
            row,
            debt_coverage_index=debt_coverage_index,
        )
    ]
    by_validation: dict[str, int] = {}
    by_lifecycle: dict[str, int] = {}
    for claim in claims:
        by_validation[claim["validation_status"]] = by_validation.get(claim["validation_status"], 0) + 1
        by_lifecycle[claim["lifecycle_status"]] = by_lifecycle.get(claim["lifecycle_status"], 0) + 1
    run_summary = summarize_runs(runs)
    return {
        "problem_id": store.problem_id,
        "revision": problem["current_revision"],
        "claim_count": len(claims),
        "current_claim_count": sum(1 for row in claims if not claim_is_retired(row)),
        "retired_claim_count": sum(1 for row in claims if claim_is_retired(row)),
        "verified_claim_count": sum(1 for row in claims if claim_is_verified(row)),
        "integrated_claim_count": sum(
            1 for row in claims
            if not claim_is_retired(row) and row["lifecycle_status"] == "integrated"
        ),
        "route_count": len(routes),
        "active_route_count": sum(1 for row in routes if row["status"] == "active"),
        "active_debt_count": len(active_debts),
        "blocking_debt_count": sum(1 for row in active_debts if row["severity"] == "blocking"),
        "open_debt_count": len(open_debts),
        "open_blocking_debt_count": sum(1 for row in open_debts if row["severity"] == "blocking"),
        "claims_by_validation": by_validation,
        "claims_by_lifecycle": by_lifecycle,
        "token_budget": {
            "total": problem["total_token_budget"],
            "remaining": problem["remaining_token_budget"],
            "reserved_verification": problem["reserved_verification_budget"],
            "spent_reported": run_summary["total_tokens"],
            "charged_lifetime": run_summary["charged_tokens"],
        },
        "runs": run_summary,
        "run_timing": store.get_run_timing(),
        "math_yield": _math_yield_metrics(claims, artifacts, run_summary),
        "root_progress": _root_progress_metrics(
            claims,
            routes,
            state.get("inferences", []),
            open_debts,
            artifacts,
        ),
        "root_leverage": root_leverage_metrics(state),
        "benchmark_storage": _benchmark_storage_metrics(
            store,
            state_revision=int(problem.get("current_revision") or 0),
        ),
    }


def _math_yield_metrics(claims: list[Dict[str, Any]], artifacts: list[Dict[str, Any]], run_summary: Dict[str, Any]) -> Dict[str, Any]:
    proof_types = {"proof_dossier", "proof_blueprint", "source_adaptation_notes", "cas_experiment_report"}
    # Advisor output is supervision, not researcher paperwork; counting it as
    # diagnostic made heavier (useful) supervision read as lower math yield.
    diagnostic_types = {"research_diagnostic", "research_notebook", "failed_decomposition_plan"}
    supervision_types = {"advisor_report", "route_triage_report", "key_failure_analysis"}
    proof_artifacts = [row for row in artifacts if row.get("artifact_type") in proof_types]
    diagnostic_artifacts = [row for row in artifacts if row.get("artifact_type") in diagnostic_types]
    supervision_artifacts = [row for row in artifacts if row.get("artifact_type") in supervision_types]
    verified = sum(1 for row in claims if claim_is_verified(row))
    total_tokens = int(run_summary.get("total_tokens") or 0)
    return {
        "proof_artifact_count": len(proof_artifacts),
        "diagnostic_artifact_count": len(diagnostic_artifacts),
        "supervision_artifact_count": len(supervision_artifacts),
        "proof_to_diagnostic_ratio": round(len(proof_artifacts) / max(1, len(diagnostic_artifacts)), 3),
        "tokens_per_verified_claim": round(total_tokens / max(1, verified), 1),
    }


def _root_progress_metrics(
    claims: list[Dict[str, Any]],
    routes: list[Dict[str, Any]],
    inferences: list[Dict[str, Any]],
    debts: list[Dict[str, Any]],
    artifacts: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """Measure certified closure of a root proof, not nearby activity.

    The former metric added points for every root-adjacent claim, killed route,
    and support artifact.  It could therefore exceed 100 while the root had no
    inference at all.  This staged metric is intentionally conservative: local
    lemmas remain useful diagnostics, but only an assembled sufficient route
    can move the proof through the closure stages.
    """
    verified = {"informally_verified", "formally_verified"}
    claim_by_id = {str(row.get("claim_id") or ""): row for row in claims}
    root = claim_by_id.get("root", {})

    def parent_ids(row: Dict[str, Any]) -> list[str]:
        value = row.get("parent_ids")
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(item) for item in json_loads(row.get("parent_ids_json"), [])]

    def id_list(row: Dict[str, Any], key: str, json_key: str) -> list[str]:
        value = row.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(item) for item in json_loads(row.get(json_key), [])]

    def root_adjacent(row: Dict[str, Any]) -> bool:
        if str(row.get("claim_id") or "") == "root":
            return False
        return "root" in parent_ids(row) or int(row.get("reduction_depth", 99) or 99) <= 1

    root_adjacent_claims = [row for row in claims if root_adjacent(row)]
    verified_root_adjacent = [row for row in root_adjacent_claims if claim_is_verified(row)]
    integrated_root_adjacent = [
        row for row in root_adjacent_claims
        if not claim_is_retired(row) and row.get("lifecycle_status") == "integrated"
    ]

    root_local_debts = []
    for debt in debts:
        if debt.get("status") != "active" or debt.get("severity") != "blocking":
            continue
        owner_id = str(debt.get("owner_id") or "")
        suggested = str(debt.get("suggested_next_target") or "")
        owner = claim_by_id.get(owner_id) or claim_by_id.get(suggested)
        if owner_id == "root" or suggested == "root" or (owner and root_adjacent(owner)):
            root_local_debts.append(debt)

    root_routes = [
        row
        for row in routes
        if str(row.get("conclusion_claim_id") or "") == "root"
        and str(row.get("relation_to_parent") or "sufficient") == "sufficient"
        and str(row.get("status") or "active") not in {"abandoned", "superseded"}
    ]
    root_route_ids = {str(row.get("route_id") or "") for row in root_routes}
    root_inferences = [
        row
        for row in inferences
        if str(row.get("route_id") or "") in root_route_ids
        and str(row.get("conclusion_claim_id") or "") == "root"
    ]
    terminal_verified = [
        row for row in root_inferences
        if str(row.get("validation_status") or "") in verified
        and all(
            str(claim_by_id.get(claim_id, {}).get("validation_status") or "") in verified
            for claim_id in (
                id_list(row, "premise_claim_ids", "premise_claim_ids_json")
                + id_list(row, "condition_claim_ids", "condition_claim_ids_json")
            )
        )
    ]
    premise_ids = {
        claim_id
        for row in root_inferences
        for claim_id in (
            id_list(row, "premise_claim_ids", "premise_claim_ids_json")
            + id_list(row, "condition_claim_ids", "condition_claim_ids_json")
        )
    }
    verified_premise_ids = {
        claim_id
        for claim_id in premise_ids
        if str(claim_by_id.get(claim_id, {}).get("validation_status") or "") in verified
    }
    root_owner_ids = {"root", *root_route_ids, *[str(row.get("inference_id") or "") for row in root_inferences]}
    direct_root_blockers = [
        debt
        for debt in debts
        if debt.get("status") == "active"
        and debt.get("severity") == "blocking"
        and (
            str(debt.get("owner_id") or "") in root_owner_ids
            or str(debt.get("suggested_next_target") or "") == "root"
        )
    ]

    root_validation = str(root.get("validation_status") or "unknown")
    root_lifecycle = str(root.get("lifecycle_status") or "unknown")
    if root_lifecycle == "integrated":
        closure_stage = "root_integrated"
        score = 100
    elif root_validation in verified:
        closure_stage = "root_verified_integration_pending"
        score = 90
    elif not root_routes:
        closure_stage = "no_sufficient_root_route"
        score = 0
    elif not root_inferences:
        closure_stage = "root_route_unassembled"
        score = 10
    elif terminal_verified and direct_root_blockers:
        closure_stage = "verified_root_inference_blocked"
        score = 65
    elif terminal_verified:
        closure_stage = "root_route_ready_for_integration"
        score = 75
    else:
        premise_fraction = (
            len(verified_premise_ids) / len(premise_ids)
            if premise_ids
            else 0.0
        )
        all_premises_ready = bool(premise_ids) and premise_fraction == 1.0
        closure_stage = (
            "root_inference_ready_for_verification"
            if all_premises_ready
            else "root_inference_has_open_premises"
        )
        score = 55 if all_premises_ready else min(49, 20 + int(30 * premise_fraction))

    support_artifacts = [
        row for row in artifacts
        if row.get("artifact_type") in {"source_adaptation_notes", "source_synthesis_report", "cas_experiment_report"}
    ]

    return {
        "root_validation_status": root_validation,
        "root_lifecycle_status": root_lifecycle,
        "closure_stage": closure_stage,
        "sufficient_root_route_count": len(root_routes),
        "root_terminal_inference_count": len(root_inferences),
        "verified_root_terminal_inference_count": len(terminal_verified),
        "root_premise_count": len(premise_ids),
        "verified_root_premise_count": len(verified_premise_ids),
        "direct_root_blocking_debt_count": len(direct_root_blockers),
        "verified_root_adjacent_claim_count": len(verified_root_adjacent),
        "integrated_root_adjacent_claim_count": len(integrated_root_adjacent),
        "root_local_blocking_debt_count": len(root_local_debts),
        "support_artifact_count": len(support_artifacts),
        "score": score,
        "score_is_stage_not_percentage": True,
        "score_interpretation": (
            "bounded closure stage for an assembled sufficient root route; "
            "nearby lemmas, failed routes, and support artifacts do not add score"
        ),
    }


def _benchmark_storage_metrics(
    store: ProofStateStore,
    *,
    state_revision: int,
) -> Dict[str, Any]:
    state_dir = store.state_dir
    result_dir = state_dir.parent
    source_dirs = _existing_source_dirs(state_dir, result_dir)
    source_bytes = sum(_directory_size_at_revision(path, state_revision) for path in source_dirs)
    return {
        "artifact_dir": str(state_dir / "artifacts"),
        "native_result_dir": str(result_dir),
        "downloaded_source_dirs": [str(path) for path in source_dirs],
        "stored_memory_artifacts_bytes": _directory_size_at_revision(
            state_dir / "artifacts",
            state_revision,
        ),
        "native_result_dir_bytes": _directory_size_at_revision(result_dir, state_revision),
        "downloaded_source_dir_bytes": source_bytes,
    }


def _existing_source_dirs(state_dir: Path, result_dir: Path) -> list[Path]:
    candidates = [
        state_dir / "downloads",
        state_dir / ".refs",
        state_dir / "sources",
        result_dir / "downloads",
        result_dir / ".refs",
        result_dir / "sources",
    ]
    seen: set[Path] = set()
    paths: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        paths.append(resolved)
    return paths


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


@lru_cache(maxsize=32)
def _directory_size_at_revision(path: Path, state_revision: int) -> int:
    """Avoid walking a mature result tree on every unchanged-state refresh."""

    return _directory_size(path)
