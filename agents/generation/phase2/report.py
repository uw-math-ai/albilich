from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .audit import build_referee_report_lines, is_audit_state
from .branch_summary import build_branch_workbenches, render_branch_workbench
from .fact_graph import DERIVED_EDGE_TYPES, EDGE_TYPES, STUB_EDGE_TYPES, build_fact_graph
from .graph_policy import claim_type_label, proof_trunk_maturity, root_distance_for_claim_id, route_scoreboard
from .metrics import compute_metrics
from .result_status import classify_state
from .research_policy import theorem_matching_confidence
from .research_strategy import strategy_observability
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
    timing = metrics.get("run_timing", {})
    lines = [
        f"# Albilich v1 Report: {store.problem_id}",
        "",
        f"- Outcome: {_outcome_label(metrics, root, final_artifact)}",
        f"- Public status: {result['public_status']}",
        f"- Result kind: {result['result_kind']}",
        f"- Result classification: {result.get('report_classification', 'in_progress')}",
        f"- Relation to target: {result['relation_to_target']}",
        f"- Result summary: {result['summary']}",
        f"- Completion policy: {problem.get('completion_policy', 'full_proof_first')}",
        f"- Revision: {metrics['revision']}",
        f"- Claims: {metrics['claim_count']} total, {metrics['verified_claim_count']} verified, {metrics['integrated_claim_count']} integrated",
        f"- Routes: {metrics['route_count']} total, {metrics['active_route_count']} active",
        f"- {debt_label}: {metrics['active_debt_count']} total, {metrics['blocking_debt_count']} blocking",
        f"- Tokens: {metrics['token_budget']['spent_reported']} reported spent, {metrics['token_budget']['remaining']} remaining, {metrics['token_budget']['reserved_verification']} reserved",
        f"- Run status: {timing.get('run_status', 'running')}",
        f"- Wall-clock elapsed since run start: {_format_seconds(timing.get('wall_clock_seconds', 0))}",
        f"- Active backend compute (child-session wall time): {_format_seconds(timing.get('active_compute_seconds', metrics['runs'].get('wall_time_seconds', 0)))}",
        f"- Paused time (excluded from active compute): {_format_seconds(timing.get('paused_seconds', 0))} across {int(timing.get('pause_count', 0) or 0)} pause interval(s)",
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
            f"| Wall-clock elapsed (seconds) | {float(timing.get('wall_clock_seconds', 0) or 0):.3f} |",
            f"| Active compute wall time (seconds) | {float(metrics['runs'].get('wall_time_seconds', 0) or 0):.3f} |",
            f"| Active compute wall time (hours) | {float(metrics['runs'].get('wall_time_seconds', 0) or 0) / 3600.0:.2f} |",
            f"| Paused time (seconds) | {float(timing.get('paused_seconds', 0) or 0):.3f} |",
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
            "Timing convention: wall-clock elapsed runs from problem init to the last recorded activity; "
            "active compute is the recorded child-session wall time; paused time covers explicit run-pause "
            "intervals and is excluded from active compute.",
            "",
        ]
    )
    lines.extend(_run_control_event_lines(timing))
    if is_audit_state(state):
        # paper_solution_audit (TODO 6): referee-style audit sections with the
        # AI-audit warning line; rendered before proof sections so the audit
        # verdict is never confused with a solved-proof deliverable.
        lines.extend(build_referee_report_lines(state))
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
    # Compact all-branches report (TODOs 1+2): one workbench block per active
    # branch — what is proved, what is blocked, the next nearby lemma, the
    # last useful delta/stale count, and the continue-or-rotate adjudication.
    branch_workbenches = build_branch_workbenches(store, state=state, limit=5)
    if branch_workbenches:
        lines.extend(["## Branches", ""])
        parallel_workers = int(problem.get("parallel_branches") or 0)
        if parallel_workers:
            lines.append(
                f"- Parallel branch mode: `{problem.get('research_parallel_mode') or 'multi_branch_research'}` "
                f"with up to {parallel_workers} simultaneous branch workers"
            )
            lines.append("")
        for workbench in branch_workbenches:
            lines.append("```text")
            lines.append(render_branch_workbench(workbench))
            lines.append("```")
            lines.append("")
    lines.extend(_research_strategy_lines(state))
    lines.extend(_fact_graph_lines(store, state))
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
    lines.extend(_writing_review_lines(state))
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


def _research_strategy_lines(state: Dict[str, Any]) -> list[str]:
    strategy = strategy_observability(state)
    frontier = strategy.get("decisive_obligation_frontier") or {}
    learning = strategy.get("verifier_filtered_outcome_learning") or {}
    roi = strategy.get("deep_session_roi") or {}
    if not any(
        strategy.get(key)
        for key in (
            "latest_advisor_synthesis_artifact_id",
            "latest_proof_compression_artifact_id",
            "latest_bridge_search_artifact_id",
            "latest_conjecture_portfolio_artifact_id",
            "active_invention_authorization_artifact_id",
            "decisive_obligation_frontier",
        )
    ):
        return []
    trigger = strategy.get("advisor_synthesis_trigger") or {}
    lines = [
        "## Research Strategy",
        "",
        "Strategic artifacts are persisted proof-state context, not verified mathematical evidence.",
        "",
        f"- Latest global advisor synthesis: `{strategy.get('latest_advisor_synthesis_artifact_id') or 'none'}`",
        f"- Latest active proof compression: `{strategy.get('latest_proof_compression_artifact_id') or 'none'}`",
        f"- Bridge search: `{strategy.get('latest_bridge_search_artifact_id') or 'none'}`; "
        f"candidates={strategy.get('bridge_candidate_count', 0)}, selected=`{strategy.get('selected_bridge_id') or 'none'}`",
    ]
    if strategy.get("selected_bridge_reason"):
        lines.append(f"  - Selection reason: {strategy['selected_bridge_reason']}")
    lines.extend(
        [
            f"- Conjecture portfolio: `{strategy.get('latest_conjecture_portfolio_artifact_id') or 'none'}`; "
            f"candidates={strategy.get('conjecture_candidate_count', 0)}, selected=`{strategy.get('selected_conjecture_id') or 'none'}`",
            f"- Active invention authorization: `{strategy.get('active_invention_authorization_artifact_id') or 'none'}`",
            f"- Global synthesis due: `{bool(trigger.get('due'))}`; reasons={trigger.get('reasons', [])}",
            f"- Graph-derived decisive obligation: `{(frontier.get('decisive_obligation') or {}).get('obligation_id') or 'none'}`; "
            f"selected route=`{frontier.get('selected_route_id') or 'none'}`, ready_for_verification={bool(frontier.get('selected_route_ready_for_verification'))}",
            f"- Verifier-filtered outcome learning: family=`{learning.get('current_strategy_family') or 'none'}`; "
            f"local families={len(learning.get('families') or {})}; reference_solution_used={bool(learning.get('reference_solution_used'))}",
            f"- Deep-session ROI: allowed={bool(roi.get('allowed', True))}; reason={roi.get('reason') or 'not evaluated'}",
            "- Information-gain policy: scheduler exposes closing, refuting, root-progress, information, reuse, duplication, token, wall-time, verification-cost, and verifier-filtered outcome components; speculative work never consumes the protected verification reserve.",
            "- Method library policy: 18 developer-curated structural/domain method cards are advisory only and are kept separate from verified facts, external theorem cards, and private speculation.",
            "",
        ]
    )
    return lines


def _fact_graph_lines(store: ProofStateStore, state: Dict[str, Any]) -> list[str]:
    """"Fact Graph" health section (2026-07-09 TODO 3 pilot): node counts by
    type, edge counts by type (deriving vs stubbed), and the per-branch
    deep/shallow/blocked/converging depth report. The graph is a generated,
    read-only view over the proof state — never a second store."""
    graph = build_fact_graph(store, state=state)
    node_counts = graph.node_counts_by_type()
    if not any(node_counts.values()):
        return []
    edge_counts = graph.edge_counts_by_type()
    lines = [
        "## Fact Graph",
        "",
        "Read-only graph view generated from claims, routes, inferences, debts, and sources.",
        "",
        "- Nodes: " + ", ".join(f"{label}={count}" for label, count in node_counts.items()),
        "- Edges: "
        + ", ".join(f"{edge_type}={edge_counts.get(edge_type, 0)}" for edge_type in EDGE_TYPES if edge_type in DERIVED_EDGE_TYPES),
        "- Edge types awaiting a data source (not derived): " + ", ".join(sorted(STUB_EDGE_TYPES)),
    ]
    depth_report = graph.branch_depth_report()
    if depth_report:
        lines.append("- Branch depth report:")
        for row in depth_report:
            flags = "".join(
                f", {flag}" for flag, present in (("blocked", row["blocked"]), ("converging", row["converging"])) if present
            )
            lines.append(
                f"  - `{row['branch_id']}` {row['classification']} (depth={row['depth']}, "
                f"verified={row['verified_fact_count']}, candidate={row['candidate_fact_count']}, "
                f"active_obstructions={row['active_obstruction_count']}{flags})"
            )
    lines.append("")
    return lines


def _run_control_event_lines(timing: Dict[str, Any]) -> list[str]:
    """Pause/resume/stop/interruption ledger so benchmark comparisons can see
    exactly when the run was live versus paused or interrupted."""
    events = timing.get("run_control_events") or []
    if not events:
        return []
    lines = ["## Run Control Events", ""]
    for event in events:
        if str(event.get("event_type") or "") == "run_interrupted":
            lines.append(f"- `{event.get('at', '')}` interruption recorded: {event.get('reason', '')}")
            continue
        hard = " (hard)" if event.get("hard") else ""
        lines.append(
            f"- `{event.get('at', '')}` `{event.get('from', '?')} -> {event.get('to', '?')}`{hard} "
            f"[{event.get('source', '')}] {event.get('reason', '')}"
        )
    lines.append("")
    return lines


def _writing_review_lines(state: Dict[str, Any]) -> list[str]:
    """"Writing review" section: lens verdicts per reviewed document revision
    (naming the reviewed artifact's type: final_proof certificate or shipped
    final_paper/revision_document), shipped-document status, writing-debt counts
    by severity, and the unresolved list used for human quality steering."""
    reviews = [row for row in state.get("artifacts", []) if row.get("artifact_type") == "writing_review"]
    writing_debts = [row for row in state.get("debts", []) if str(row.get("debt_type") or "") == "writing"]
    has_revision_document = any(
        row.get("artifact_type") == "revision_document" for row in state.get("artifacts", [])
    )
    if not reviews and not writing_debts and not has_revision_document:
        return []
    artifact_types = {
        str(row.get("artifact_id") or ""): str(row.get("artifact_type") or "")
        for row in state.get("artifacts", [])
    }
    lines = ["## Writing Review", ""]
    if reviews:
        for review in sorted(reviews, key=lambda row: str(row.get("created_at") or "")):
            metadata = json.loads(review.get("metadata_json") or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
            lens = metadata.get("lens", "unknown_lens")
            verdict = metadata.get("verdict", "unknown")
            reviewed = metadata.get("artifact_reviewed", "unknown")
            reviewed_type = artifact_types.get(str(reviewed), "unknown_type")
            revision = metadata.get("state_revision_reviewed", "?")
            lines.append(f"- `{lens}` `{verdict}` on `{reviewed}` (`{reviewed_type}`, state revision {revision})")
    else:
        lines.append("No writing_review artifacts recorded.")
    lines.append("")
    final_paper = _latest_final_paper(state)
    if final_paper is not None:
        paper_metadata = json.loads(final_paper.get("metadata_json") or "{}")
        if not isinstance(paper_metadata, dict):
            paper_metadata = {}
        paper_status = str(paper_metadata.get("pdf_status") or "no compile status recorded")
        lines.append(f"- Final paper: `{final_paper.get('artifact_id', '')}` ({paper_status})")
        lines.append("")
    revision_document = _latest_revision_document(state)
    if revision_document is not None:
        revision_metadata = json.loads(revision_document.get("metadata_json") or "{}")
        if not isinstance(revision_metadata, dict):
            revision_metadata = {}
        lines.append(
            f"- Revised external manuscript: `{revision_document.get('artifact_id', '')}` "
            f"(`{revision_metadata.get('document_format', 'unknown')}`, revision "
            f"{revision_metadata.get('revision_number', 0)}, mathematical status "
            f"`{revision_metadata.get('mathematical_status', 'not_verified_by_writing_harness')}`)"
        )
        lines.append(f"- Source lineage: `{revision_metadata.get('original_sha256', '')}`")
        lines.append("")
    compile_status = _shipped_final_proof_compile_status(state)
    if compile_status:
        lines.append(f"- Shipped final_proof LaTeX compile status: `{compile_status}`")
        lines.append("")
    open_debts = [row for row in writing_debts if row.get("status") == "active"]
    resolved_debts = [row for row in writing_debts if row.get("status") == "resolved"]
    lines.append(
        "- Open writing debts: "
        f"{len(open_debts)} ({_writing_debt_severity_counts(open_debts)}); "
        f"resolved: {len(resolved_debts)} ({_writing_debt_severity_counts(resolved_debts)})"
    )
    if open_debts:
        lines.extend(["", "Unresolved writing debts:", ""])
        for debt in open_debts:
            lines.append(f"- `{debt['debt_id']}` `{debt['severity']}` on `{debt['owner_id']}`: {debt['obligation']}")
    lines.append("")
    return lines


def _latest_final_paper(state: Dict[str, Any]) -> Dict[str, Any] | None:
    papers = [row for row in state.get("artifacts", []) if row.get("artifact_type") == "final_paper"]
    if not papers:
        return None
    return max(papers, key=lambda row: (int(row.get("state_revision") or 0), str(row.get("created_at") or "")))


def _latest_revision_document(state: Dict[str, Any]) -> Dict[str, Any] | None:
    documents = [row for row in state.get("artifacts", []) if row.get("artifact_type") == "revision_document"]
    if not documents:
        return None
    return max(
        documents,
        key=lambda row: (int(row.get("state_revision") or 0), str(row.get("created_at") or "")),
    )


def _shipped_final_proof_compile_status(state: Dict[str, Any]) -> str:
    """pdf_status of the most recent final_proof (persisted by the writer at
    attach time); empty if none recorded (e.g. no writer sidecar)."""
    finals = [row for row in state.get("artifacts", []) if row.get("artifact_type") == "final_proof"]
    if not finals:
        return ""
    latest = max(finals, key=lambda row: (int(row.get("state_revision") or 0), str(row.get("created_at") or "")))
    metadata = json.loads(latest.get("metadata_json") or "{}")
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("pdf_status") or "")


def _writing_debt_severity_counts(debts: list[Dict[str, Any]]) -> str:
    counts = {"blocking": 0, "major": 0, "minor": 0}
    for debt in debts:
        severity = str(debt.get("severity") or "")
        if severity in counts:
            counts[severity] += 1
    return ", ".join(f"{severity} {count}" for severity, count in counts.items())


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
