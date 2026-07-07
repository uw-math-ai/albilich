from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .budget import summarize_runs
from .models import json_loads
from .store import ProofStateStore


def compute_metrics(store: ProofStateStore) -> Dict[str, Any]:
    state = store.get_state()
    claims = state["claims"]
    routes = state["routes"]
    debts = state["debts"]
    runs = state["runs"]
    artifacts = state.get("artifacts", [])
    verified = {"informally_verified", "formally_verified"}
    problem = state["problem_state"]
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
        "verified_claim_count": sum(1 for row in claims if row["validation_status"] in verified),
        "integrated_claim_count": sum(1 for row in claims if row["lifecycle_status"] == "integrated"),
        "route_count": len(routes),
        "active_route_count": sum(1 for row in routes if row["status"] == "active"),
        "active_debt_count": sum(1 for row in debts if row["status"] == "active"),
        "blocking_debt_count": sum(1 for row in debts if row["status"] == "active" and row["severity"] == "blocking"),
        "claims_by_validation": by_validation,
        "claims_by_lifecycle": by_lifecycle,
        "token_budget": {
            "total": problem["total_token_budget"],
            "remaining": problem["remaining_token_budget"],
            "reserved_verification": problem["reserved_verification_budget"],
            "spent_reported": run_summary["total_tokens"],
        },
        "runs": run_summary,
        "math_yield": _math_yield_metrics(claims, artifacts, run_summary),
        "root_progress": _root_progress_metrics(claims, routes, debts, artifacts),
        "benchmark_storage": _benchmark_storage_metrics(store),
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
    verified = sum(1 for row in claims if row.get("validation_status") in {"informally_verified", "formally_verified"})
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
    debts: list[Dict[str, Any]],
    artifacts: list[Dict[str, Any]],
) -> Dict[str, Any]:
    verified = {"informally_verified", "formally_verified"}
    claim_by_id = {str(row.get("claim_id") or ""): row for row in claims}
    root = claim_by_id.get("root", {})

    def parent_ids(row: Dict[str, Any]) -> list[str]:
        return [str(item) for item in json_loads(row.get("parent_ids_json"), [])]

    def root_adjacent(row: Dict[str, Any]) -> bool:
        if str(row.get("claim_id") or "") == "root":
            return False
        return "root" in parent_ids(row) or int(row.get("reduction_depth", 99) or 99) <= 1

    root_adjacent_claims = [row for row in claims if root_adjacent(row)]
    verified_root_adjacent = [row for row in root_adjacent_claims if row.get("validation_status") in verified]
    integrated_root_adjacent = [row for row in root_adjacent_claims if row.get("lifecycle_status") == "integrated"]

    root_local_debts = []
    for debt in debts:
        if debt.get("status") != "active" or debt.get("severity") != "blocking":
            continue
        owner_id = str(debt.get("owner_id") or "")
        suggested = str(debt.get("suggested_next_target") or "")
        owner = claim_by_id.get(owner_id) or claim_by_id.get(suggested)
        if owner_id == "root" or suggested == "root" or (owner and root_adjacent(owner)):
            root_local_debts.append(debt)

    killed_routes = [
        row for row in routes
        if row.get("status") in {"abandoned", "blocked", "refuted"} and (
            str(row.get("conclusion_claim_id") or "") == "root"
            or root_adjacent(claim_by_id.get(str(row.get("conclusion_claim_id") or ""), {}))
        )
    ]
    support_artifacts = [
        row for row in artifacts
        if row.get("artifact_type") in {"source_adaptation_notes", "source_synthesis_report", "cas_experiment_report"}
    ]
    score = 0
    if root.get("lifecycle_status") == "integrated":
        score += 100
    elif root.get("validation_status") in verified:
        score += 70
    score += 8 * len(integrated_root_adjacent)
    score += 4 * len(verified_root_adjacent)
    score += 3 * len(killed_routes)
    score += 2 * len(support_artifacts)
    score -= 5 * len(root_local_debts)

    return {
        "root_validation_status": root.get("validation_status", "unknown"),
        "root_lifecycle_status": root.get("lifecycle_status", "unknown"),
        "verified_root_adjacent_claim_count": len(verified_root_adjacent),
        "integrated_root_adjacent_claim_count": len(integrated_root_adjacent),
        "root_local_blocking_debt_count": len(root_local_debts),
        "killed_root_route_count": len(killed_routes),
        "support_artifact_count": len(support_artifacts),
        "score": max(0, score),
        "score_interpretation": "higher means root theorem or root-adjacent bottlenecks moved, not merely that more claims were generated",
    }


def _benchmark_storage_metrics(store: ProofStateStore) -> Dict[str, Any]:
    state_dir = store.state_dir
    result_dir = state_dir.parent
    source_dirs = _existing_source_dirs(state_dir, result_dir)
    source_bytes = sum(_directory_size(path) for path in source_dirs)
    return {
        "artifact_dir": str(state_dir / "artifacts"),
        "native_result_dir": str(result_dir),
        "downloaded_source_dirs": [str(path) for path in source_dirs],
        "stored_memory_artifacts_bytes": _directory_size(state_dir / "artifacts"),
        "native_result_dir_bytes": _directory_size(result_dir),
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
