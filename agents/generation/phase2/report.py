from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .graph_policy import claim_type_label, proof_trunk_maturity, root_distance_for_claim_id, route_scoreboard
from .metrics import compute_metrics
from .result_status import classify_state
from .research_policy import theorem_matching_confidence
from .store import ProofStateStore


def build_markdown_report(store: ProofStateStore) -> str:
    state = store.get_state()
    metrics = compute_metrics(store)
    problem = state["problem_state"]
    root = next((row for row in state["claims"] if row["claim_id"] == "root"), {})
    final_artifact = _final_proof_artifact(state)
    result = classify_state(state)
    storage = metrics.get("benchmark_storage", {})
    run_counts = _benchmark_run_counts(state)
    debt_label = "Active debts"
    if result["public_status"] in {"solved", "solved_pending_final_writer"}:
        debt_label = "Active debts (ledger only)"
    lines = [
        f"# Albilich v1 Report: {store.problem_id}",
        "",
        f"- Outcome: {_outcome_label(metrics, root, final_artifact)}",
        f"- Public status: {result['public_status']}",
        f"- Result kind: {result['result_kind']}",
        f"- Relation to target: {result['relation_to_target']}",
        f"- Result summary: {result['summary']}",
        f"- Revision: {metrics['revision']}",
        f"- Claims: {metrics['claim_count']} total, {metrics['verified_claim_count']} verified, {metrics['integrated_claim_count']} integrated",
        f"- Routes: {metrics['route_count']} total, {metrics['active_route_count']} active",
        f"- {debt_label}: {metrics['active_debt_count']} total, {metrics['blocking_debt_count']} blocking",
        f"- Tokens: {metrics['token_budget']['spent_reported']} reported spent, {metrics['token_budget']['remaining']} remaining, {metrics['token_budget']['reserved_verification']} reserved",
        f"- Recorded child wall time: {_format_seconds(metrics['runs'].get('wall_time_seconds', 0))}",
        f"- Peak recorded child memory: {_format_memory(metrics['runs'].get('peak_memory_mb', 0))}",
        f"- Stored memory artifacts: {_format_bytes(storage.get('stored_memory_artifacts_bytes', 0))}",
        f"- Native result directory: {_format_bytes(storage.get('native_result_dir_bytes', 0))}",
        f"- Downloaded source directory: {_format_bytes(storage.get('downloaded_source_dir_bytes', 0))}",
        "",
        "## Root Statement",
        "",
        problem["root_statement"],
        "",
    ]
    lines.extend(
        [
            "## Benchmark Quantitative Snapshot",
            "",
            "| Quantity | Albilich v1 benchmark run |",
            "| --- | ---: |",
            f"| Iterations / generator calls | {metrics['runs'].get('run_count', 0)} |",
            f"| Wall time (seconds) | {float(metrics['runs'].get('wall_time_seconds', 0) or 0):.3f} |",
            f"| Wall time (hours) | {float(metrics['runs'].get('wall_time_seconds', 0) or 0) / 3600.0:.2f} |",
            f"| Reported tokens | {metrics['runs'].get('total_tokens', 0)} |",
            f"| Search / theorem-retrieval calls | {run_counts['search_retrieval']} |",
            f"| Verifier-call estimate | {run_counts['verifier']} |",
            f"| Advisor / reducer calls | {run_counts['advisor_reducer']} |",
            f"| Stored memory artifacts | {storage.get('stored_memory_artifacts_bytes', 0)} bytes |",
            f"| Native result directory | {storage.get('native_result_dir_bytes', 0)} bytes |",
            f"| Downloaded source directory | {storage.get('downloaded_source_dir_bytes', 0)} bytes |",
            "",
            "Memory in this table follows the legacy benchmark convention: stored artifact/source directory size, not peak process RSS. Peak RSS is reported separately when the runner can sample it.",
            "",
        ]
    )
    if final_artifact:
        lines.extend(["## Final Proof", ""])
        proof_text = _artifact_text(final_artifact)
        lines.append(proof_text or f"Final proof artifact: `{final_artifact['artifact_id']}`")
        lines.append("")
    elif root.get("lifecycle_status") == "integrated":
        lines.extend(
            [
                "## Final Proof",
                "",
                "The root claim is integrated, but no final proof artifact has been written yet. Run the workflow again so the writer/closer can emit the final proof.",
                "",
            ]
        )
    if result["proved_statement"] and result["proved_statement"] != result["target_statement"]:
        lines.extend(["## Proved Result", "", result["proved_statement"], ""])
    if result["certified_partial_results"]:
        lines.extend(["## Certified Partial Results", ""])
        for item in result["certified_partial_results"]:
            lines.append(f"- `{item['claim_id']}` `{item['status']}` `{item['relation_to_target']}`: {item['statement']}")
        lines.append("")
    if result["remaining_obligations"]:
        lines.extend(["## Remaining Obligations", ""])
        for obligation in result["remaining_obligations"]:
            lines.append(f"- {obligation}")
        lines.append("")
    lines.extend(["## Route Scoreboard", ""])
    scoreboard = route_scoreboard(state, limit=12)
    if not scoreboard:
        lines.append("No proof routes recorded yet.")
    else:
        for route in scoreboard:
            reason = f" reasons={route['kill_reasons']}" if route["kill_reasons"] else ""
            lines.append(
                f"- `{route['route_id']}` `{route['scoreboard_status']}` score={route['score']} "
                f"root_distance={route['root_distance']} verified={route['verified_inference_count']}/{route['inference_count']}{reason}"
            )
    lines.append("")
    retrieval_cards = state.get("retrieval_cards", [])
    if retrieval_cards:
        lines.extend(["## Retrieval Cards", ""])
        for card in retrieval_cards[:12]:
            applicability = json.loads(card.get("applicability_json") or "{}")
            missing = json.loads(card.get("missing_hypotheses_json") or "[]")
            confidence = applicability.get("theorem_matching_confidence") or theorem_matching_confidence(applicability, missing_hypotheses=missing)
            relation = applicability.get("classification") or applicability.get("relation") or confidence.get("relation", "")
            lines.append(f"- `{card['card_id']}` `{relation}` confidence={confidence}: {card['exact_statement']}")
        lines.append("")
    theorem_library = state.get("theorem_library_entries", [])
    if theorem_library:
        lines.extend(["## Reusable Theorem Library", ""])
        for entry in theorem_library[:12]:
            source = json.loads(entry.get("source_identifiers_json") or "{}")
            title = source.get("title") or "unknown source"
            location = (
                source.get("theorem_number")
                or source.get("proposition_number")
                or source.get("lemma_number")
                or source.get("corollary_number")
                or entry.get("source_location")
                or "unspecified location"
            )
            lines.append(
                f"- `{entry['entry_id']}` `{entry['certification_type']}` `{entry['relation_to_target']}` "
                f"{title}, {location}: {entry['statement']}"
            )
        lines.append("")
    lines.extend(["## Claims", ""])
    for claim in sorted(state["claims"], key=lambda row: (int(row.get("reduction_depth", 0)), row["claim_id"])):
        maturity = proof_trunk_maturity(state, claim["claim_id"])
        label = claim_type_label(state, claim)
        distance = root_distance_for_claim_id(state, claim["claim_id"])
        lines.append(
            f"- `{claim['claim_id']}` `{claim['validation_status']}` `{claim['lifecycle_status']}` "
            f"`{label}` maturity={maturity} root_distance={distance}: {claim['statement']}"
        )
    lines.extend(["", "## Active Proof Debts", ""])
    active_debts = [row for row in state["debts"] if row["status"] == "active"]
    if not active_debts:
        lines.append("No active proof debts.")
    else:
        for debt in active_debts:
            lines.append(f"- `{debt['debt_id']}` `{debt['severity']}` on `{debt['owner_id']}`: {debt['obligation']}")
    return "\n".join(lines) + "\n"


def write_markdown_report(store: ProofStateStore) -> Path:
    path = store.state_dir / "phase2_report.md"
    path.write_text(build_markdown_report(store), encoding="utf-8")
    return path


def _outcome_label(metrics: Dict[str, Any], root: Dict[str, Any], final_artifact: Dict[str, Any] | None) -> str:
    if final_artifact:
        return "solved_final"
    if root.get("lifecycle_status") == "integrated":
        return "solved_internal_needs_final_writer"
    if metrics["verified_claim_count"] > 0:
        return "verified_partial"
    if metrics["active_debt_count"] > 0:
        return "useful_partial_with_debt"
    return "in_progress"


def _format_seconds(value: Any) -> str:
    try:
        seconds = float(value or 0)
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds <= 0:
        return "0s"
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _format_memory(value: Any) -> str:
    try:
        memory = float(value or 0)
    except (TypeError, ValueError):
        memory = 0.0
    if memory <= 0:
        return "not recorded"
    if memory >= 1024:
        return f"{memory / 1024.0:.2f} GB"
    return f"{memory:.1f} MB"


def _format_bytes(value: Any) -> str:
    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
        return "0 bytes"
    units = ["bytes", "KB", "MB", "GB"]
    amount = float(size)
    unit = units[0]
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            break
        amount /= 1024.0
    if unit == "bytes":
        return f"{size} bytes"
    return f"{amount:.2f} {unit} ({size} bytes)"


def _benchmark_run_counts(state: Dict[str, Any]) -> Dict[str, int]:
    runs = state.get("runs", [])
    search_retrieval = 0
    verifier = 0
    advisor_reducer = 0
    for run in runs:
        actor = str(run.get("actor_role") or "")
        mode = str(run.get("mode") or "")
        if actor == "literature_researcher" or mode in {"retrieve", "synthesize_sources", "audit_definitions"}:
            search_retrieval += 1
        if actor in {"strict_informal_verifier", "integration_verifier"} or mode in {
            "integrate",
            "formalize",
            "validate_counterexample",
        }:
            verifier += 1
        if actor in {"PhD_advisor", "advisor"} or mode in {"reduce", "triage_routes", "regulate_decomposition"}:
            advisor_reducer += 1
    return {
        "search_retrieval": search_retrieval,
        "verifier": verifier,
        "advisor_reducer": advisor_reducer,
    }


def _final_proof_artifact(state: Dict[str, Any]) -> Dict[str, Any] | None:
    artifacts = [row for row in state["artifacts"] if row["artifact_type"] in {"final_proof", "verified_blueprint"}]
    for artifact in sorted(artifacts, key=lambda row: row.get("created_at", ""), reverse=True):
        metadata = json.loads(artifact.get("metadata_json") or "{}")
        if metadata.get("claim_id", "root") == "root":
            return artifact
    return None


def _artifact_text(artifact: Dict[str, Any]) -> str:
    path_text = artifact.get("path", "")
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()
