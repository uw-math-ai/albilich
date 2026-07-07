from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .graph_policy import route_scoreboard
from .metrics import compute_metrics
from .research_policy import researcher_mode_summary
from .result_status import classify_state
from .scheduler import verifier_ready_route_summaries
from .store import ProofStateStore


RESEARCH_ARTIFACT_TYPES = {
    "proof_dossier",
    "proof_blueprint",
    "research_notebook",
    "research_diagnostic",
    "route_obstruction",
    "hypothesis_gap",
    "construction_failure",
    "necessary_condition",
    "literature_search_request",
    "decomposition_plan",
    "failed_decomposition_plan",
    "key_failure_analysis",
    "source_adaptation_notes",
    "source_synthesis_report",
    "cas_experiment_report",
    "definition_audit_report",
    "advisor_report",
    "verification_report",
    "integration_report",
    "final_proof",
    "partial_proof_report",
    "stop_summary_report",
    "writer_report",
}


def build_run_console_payload(store: ProofStateStore, *, history: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    state = store.get_state()
    metrics = compute_metrics(store)
    result = classify_state(state)
    runs = sorted(state.get("runs", []), key=lambda row: row.get("created_at", ""))
    verifier_audit = _verifier_audit(state, runs)
    raw_history = history or []
    history_entries = _current_invocation(raw_history)
    usage_summary = _usage_summary(runs, raw_history)
    return {
        "problem_id": store.problem_id,
        "state_dir": str(store.state_dir),
        "snapshot": _run_snapshot(state, metrics, result, runs, verifier_audit, history_entries, usage_summary),
        "usage_summary": usage_summary,
        "storage_summary": metrics.get("benchmark_storage", {}),
        "verifier_audit": verifier_audit,
        "current_invocation": history_entries,
        "live_logs": _live_logs(history_entries),
        "parallel_exchange": _parallel_exchange_payload(store),
        "researcher_mode_state": researcher_mode_summary(state),
        "decomposition_board": _decomposition_board(state),
        "open_cases": _open_case_groups(state),
        "run_timeline": _run_timeline(runs),
        "route_scoreboard": route_scoreboard(state, limit=16),
        "recent_research_artifacts": _research_artifacts(state),
    }


def build_run_console(store: ProofStateStore, *, history: list[Mapping[str, Any]] | None = None) -> str:
    return _render_console_markdown(build_run_console_payload(store, history=history))


def write_run_console(store: ProofStateStore, *, history: list[Mapping[str, Any]] | None = None) -> Path:
    payload = build_run_console_payload(store, history=history)
    path = store.state_dir / "albilich_run_console.md"
    json_path = store.state_dir / "albilich_run_console.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_atomic(path, _render_console_markdown(payload))
    _write_text_atomic(json_path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def _render_console_markdown(payload: Mapping[str, Any]) -> str:
    snapshot = _as_mapping(payload.get("snapshot"))
    audit = _as_mapping(payload.get("verifier_audit"))
    ledger_note = ""
    if snapshot.get("ledger_active_debt_count", 0) != snapshot.get("open_case_count", snapshot.get("active_debt_count", 0)):
        ledger_note = (
            f" (ledger: `{snapshot.get('ledger_active_debt_count', 0)}` active, "
            f"`{snapshot.get('ledger_blocking_debt_count', 0)}` blocking)"
        )
    lines = [
        f"# Albilich v1 Run Console: {payload.get('problem_id', '')}",
        "",
        "## Run Snapshot",
        "",
        f"- Public status: `{snapshot.get('public_status', '')}`",
        f"- Result kind: `{snapshot.get('result_kind', '')}`",
        f"- Relation to target: `{snapshot.get('relation_to_target', '')}`",
        f"- Revision: `{snapshot.get('revision', '')}`",
        f"- Claims: `{snapshot.get('verified_claim_count', 0)}/{snapshot.get('claim_count', 0)}` verified, `{snapshot.get('integrated_claim_count', 0)}` integrated",
        f"- Routes: `{snapshot.get('active_route_count', 0)}` active of `{snapshot.get('route_count', 0)}` total",
        f"- Open cases: `{snapshot.get('open_case_count', snapshot.get('active_debt_count', 0))}` active, "
        f"`{snapshot.get('open_blocking_case_count', snapshot.get('blocking_debt_count', 0))}` blocking{ledger_note}",
        f"- Token budget: `{snapshot.get('tokens_spent_reported', 0)}` spent, `{snapshot.get('tokens_remaining', 0)}` remaining, `{snapshot.get('tokens_reserved_verification', 0)}` reserved",
        f"- Recorded usage: `{snapshot.get('recorded_tokens', 0)}` tokens / `{_format_seconds(snapshot.get('recorded_wall_seconds', 0))}` child wall / `{_format_memory(snapshot.get('recorded_peak_memory_mb', 0))}` peak memory",
        f"- Stored memory: artifacts `{_format_bytes(snapshot.get('stored_memory_artifacts_bytes', 0))}`, native result `{_format_bytes(snapshot.get('native_result_dir_bytes', 0))}`, downloads `{_format_bytes(snapshot.get('downloaded_source_dir_bytes', 0))}`",
        f"- Latest run: {snapshot.get('latest_run_summary', 'none')}",
        f"- Verifier health: {snapshot.get('verifier_health', 'not yet measured')}",
        f"- Summary: {snapshot.get('summary', '')}",
        "",
        "## Status",
        "",
        "This section is kept for compatibility; the same fields are summarized above in Run Snapshot.",
        "",
        f"- Public status: `{snapshot.get('public_status', '')}`",
        f"- Result kind: `{snapshot.get('result_kind', '')}`",
        f"- Relation to target: `{snapshot.get('relation_to_target', '')}`",
        "",
    ]

    lines.extend(_render_usage_summary(_as_mapping(payload.get("usage_summary"))))
    lines.extend(_render_storage_summary(_as_mapping(payload.get("storage_summary"))))
    lines.extend(_render_current_invocation(_as_list(payload.get("current_invocation"))))
    lines.extend(_render_live_logs(_as_list(payload.get("live_logs"))))
    lines.extend(_render_parallel_exchange(_as_list(payload.get("parallel_exchange"))))
    lines.extend(_render_researcher_mode_state(_as_mapping(payload.get("researcher_mode_state"))))
    lines.extend(_render_verifier_audit(audit))
    lines.extend(_render_decomposition_board(_as_list(payload.get("decomposition_board"))))
    lines.extend(_render_open_cases(_as_mapping(payload.get("open_cases"))))
    lines.extend(_render_run_timeline(_as_list(payload.get("run_timeline"))))
    lines.extend(_render_route_scoreboard(_as_list(payload.get("route_scoreboard"))))
    lines.extend(_render_research_artifacts(_as_list(payload.get("recent_research_artifacts"))))
    return "\n".join(lines).rstrip() + "\n"


def _render_current_invocation(entries: list[Any]) -> list[str]:
    lines = ["## Current Invocation", ""]
    if not entries:
        lines.extend(["No invocation history was supplied for this console write.", ""])
        return lines
    lines.append("| step | phase | primary action | execution | patch | parallel actions |")
    lines.append("| ---: | --- | --- | --- | --- | --- |")
    for raw_entry in entries[-12:]:
        entry = _as_mapping(raw_entry)
        lines.append(
            "| "
            f"{_cell(entry.get('step'))} | "
            f"`{_cell(entry.get('execution_phase'))}` | "
            f"{_cell(entry.get('primary_action_summary'))} | "
            f"{_cell(entry.get('execution_summary'))} | "
            f"{_cell(entry.get('patch_summary'))} | "
            f"{_cell('; '.join(_as_str_list(entry.get('parallel_action_summaries'))))} |"
        )
    lines.append("")
    return lines


def _render_live_logs(logs: list[Any]) -> list[str]:
    lines = ["## Live Logs", ""]
    if not logs:
        lines.extend(["No live session log updates recorded for the current invocation.", ""])
        return lines
    for raw_log in logs[-6:]:
        item = _as_mapping(raw_log)
        label = " ".join(
            part
            for part in (
                str(item.get("actor_role") or ""),
                f"mode={item.get('mode')}" if item.get("mode") else "",
                f"target={item.get('target_id')}" if item.get("target_id") else "",
                f"run={item.get('run_id')}" if item.get("run_id") else "",
            )
            if part
        )
        lines.append(f"### {_cell(label) or 'Session'}")
        lines.append("")
        lines.append(
            f"- Status: `{item.get('status', '')}` phase=`{item.get('phase', '')}` elapsed=`{item.get('elapsed_seconds', 0)}`s updated=`{item.get('updated_at', '')}`"
        )
        if float(item.get("peak_memory_mb") or 0) > 0:
            lines.append(f"- Peak memory: `{_format_memory(item.get('peak_memory_mb', 0))}`")
        if item.get("context_path"):
            lines.append(f"- Context: `{item.get('context_path')}`")
        if item.get("log_path"):
            lines.append(f"- Log: `{item.get('log_path')}`")
        tail = str(item.get("log_tail") or "").strip()
        if tail:
            lines.extend(["", "```text", _clip_log_tail(tail), "```"])
        lines.append("")
    return lines


def _render_usage_summary(summary: Mapping[str, Any]) -> list[str]:
    lines = ["## Usage Summary", ""]
    scopes = [
        ("Total recorded", _as_mapping(summary.get("total_recorded"))),
        ("Active live children", _as_mapping(summary.get("active_live_children"))),
    ]
    lines.append("| scope | runs | reported tokens | child wall | peak memory | note |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
    for label, scope in scopes:
        lines.append(
            "| "
            f"{label} | "
            f"{scope.get('run_count', 0)} | "
            f"{scope.get('total_tokens', 0)} | "
            f"{_format_seconds(scope.get('wall_time_seconds', 0))} | "
            f"{_format_memory(scope.get('peak_memory_mb', 0))} | "
            f"{_cell(scope.get('note', ''))} |"
        )
    lines.append("")
    return lines


def _render_storage_summary(summary: Mapping[str, Any]) -> list[str]:
    lines = ["## Storage Summary", ""]
    lines.append("| scope | bytes | human | path |")
    lines.append("| --- | ---: | ---: | --- |")
    rows = [
        ("Stored memory artifacts", "stored_memory_artifacts_bytes", "artifact_dir"),
        ("Native result directory", "native_result_dir_bytes", "native_result_dir"),
        ("Downloaded source directory", "downloaded_source_dir_bytes", "downloaded_source_dirs"),
    ]
    for label, byte_key, path_key in rows:
        value = int(summary.get(byte_key, 0) or 0)
        path_value = summary.get(path_key, "")
        if isinstance(path_value, list):
            path_text = ", ".join(str(item) for item in path_value) or "none recorded"
        else:
            path_text = str(path_value or "none recorded")
        lines.append(
            "| "
            f"{label} | "
            f"{value} | "
            f"{_format_bytes(value)} | "
            f"`{_cell(path_text)}` |"
        )
    lines.append("")
    lines.append("Memory here follows the benchmark-report convention: stored artifact/source bytes, not peak RSS.")
    lines.append("")
    return lines


def _render_parallel_exchange(signals: list[Any]) -> list[str]:
    lines = ["## Parallel Exchange", ""]
    if not signals:
        lines.extend(["No parallel branch signals recorded yet.", ""])
        return lines
    lines.append("| time | actor | signal | target | relation | confidence | summary | evidence |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for raw_signal in signals[-16:]:
        signal = _as_mapping(raw_signal)
        actor = " ".join(
            part
            for part in (
                str(signal.get("actor_role") or ""),
                f"mode={signal.get('mode')}" if signal.get("mode") else "",
            )
            if part
        )
        lines.append(
            "| "
            f"{_cell(signal.get('created_at'))} | "
            f"`{_cell(actor)}` | "
            f"`{_cell(signal.get('signal_type'))}` | "
            f"`{_cell(signal.get('target_id'))}` | "
            f"`{_cell(signal.get('relation'))}` | "
            f"`{_cell(signal.get('confidence'))}` | "
            f"{_cell(signal.get('summary'))} | "
            f"{_cell(signal.get('evidence'))} |"
        )
    lines.append("")
    return lines


def _render_verifier_audit(audit: Mapping[str, Any]) -> list[str]:
    lines = [
        "## Verifier Audit",
        "",
        f"- Workflow verifier runs: `{audit.get('verifier_run_count', 0)}`",
        f"- Strict verifier report artifacts: `{audit.get('strict_verifier_report_count', 0)}`",
        f"- Verified inferences: `{audit.get('verified_inference_count', 0)}`",
        f"- Verified claims: `{audit.get('verified_claim_count', 0)}`",
        f"- Verifier-ready routes: `{len(_as_list(audit.get('verifier_ready_routes')))}`",
        f"- Zero-token verifier runs: `{len(_as_list(audit.get('zero_token_verifier_runs')))}`",
        f"- Low-token verifier runs: `{len(_as_list(audit.get('low_token_verifier_runs')))}`",
        f"- Failed verifier launches: `{len(_as_list(audit.get('failed_verifier_launches')))}`",
    ]
    warnings = _as_str_list(audit.get("warnings"))
    if warnings:
        lines.extend(["", "Warnings:"])
        for warning in warnings:
            lines.append(f"- {warning}")
    ready_routes = _as_list(audit.get("verifier_ready_routes"))
    if ready_routes:
        lines.extend(["", "Verifier-ready routes:"])
        for raw_route in ready_routes[:12]:
            route = _as_mapping(raw_route)
            lines.append(
                f"- `{route.get('route_id', '')}` target=`{route.get('target_id', '')}` inference_count={route.get('inference_count', 0)}"
            )
    lines.append("")
    return lines


def _render_decomposition_board(plans: list[Any]) -> list[str]:
    lines = ["## Decomposition Board", ""]
    if not plans:
        lines.extend(["No active or recent decomposition plans.", ""])
        return lines
    lines.append("| plan | status | kind | parent | branches | dependencies | parallel groups | artifact |")
    lines.append("| --- | --- | --- | --- | --- | ---: | ---: | --- |")
    for raw_plan in plans[:16]:
        plan = _as_mapping(raw_plan)
        lines.append(
            "| "
            f"`{_cell(plan.get('plan_id'))}` | "
            f"`{_cell(plan.get('status'))}` | "
            f"`{_cell(plan.get('plan_kind'))}` | "
            f"`{_cell(plan.get('parent_claim_id'))}` | "
            f"{_cell(plan.get('verified_subgoal_count'))}/{_cell(plan.get('subgoal_count'))} verified, "
            f"{_cell(plan.get('blocked_subgoal_count'))} blocked | "
            f"{_cell(plan.get('dependency_edge_count'))} | "
            f"{_cell(plan.get('parallel_group_count'))} | "
            f"`{_cell(plan.get('artifact_id'))}` |"
        )
        subgoals = _as_list(plan.get("subgoals"))
        if subgoals:
            branch_bits = []
            for raw_subgoal in subgoals[:8]:
                subgoal = _as_mapping(raw_subgoal)
                branch_bits.append(
                    f"`{subgoal.get('claim_id', '')}` {subgoal.get('validation_status', '')}/{subgoal.get('lifecycle_status', '')}"
                )
            lines.append(f"|  |  |  |  | {_cell('; '.join(branch_bits))} |  |  |  |")
    lines.append("")
    return lines


def _render_open_cases(groups: Mapping[str, Any]) -> list[str]:
    lines = ["## Open Cases", ""]
    total = sum(len(_as_list(value)) for value in groups.values())
    if total == 0:
        lines.extend(["No active proof debts.", ""])
        return lines
    for group_name in ("Blocking", "Citation / Hypothesis", "Verifier Repair", "Decomposition / Regulator", "Other"):
        debts = _as_list(groups.get(group_name))
        if not debts:
            continue
        lines.extend([f"### {group_name}", ""])
        for raw_debt in debts[:16]:
            debt = _as_mapping(raw_debt)
            lines.append(
                f"- `{debt.get('debt_id', '')}` `{debt.get('severity', '')}` owner=`{debt.get('owner', '')}` "
                f"next=`{debt.get('suggested_next_target', '')}` repeated=`{debt.get('repeated_count', 1)}`: "
                f"{debt.get('obligation', '')}"
            )
        lines.append("")
    return lines


def _render_run_timeline(timeline: list[Any]) -> list[str]:
    lines = ["## Run Timeline", ""]
    if not timeline:
        lines.extend(["No recorded runs yet.", ""])
        return lines
    lines.append("| created | run | actor | mode | intent | target | route | status | tokens | wall | artifacts |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |")
    for raw_row in timeline[-80:]:
        row = _as_mapping(raw_row)
        lines.append(
            f"| {_cell(row.get('created_at'))} | `{_cell(row.get('run_id'))}` | `{_cell(row.get('actor_role'))}` | "
            f"`{_cell(row.get('mode'))}` | `{_cell(row.get('search_intent'))}` | `{_cell(row.get('target_id'))}` | "
            f"`{_cell(row.get('route_id'))}` | `{_cell(row.get('status'))}` | {row.get('total_tokens', 0)} | "
            f"{_cell(row.get('wall_time_seconds'))} | {_cell(', '.join(_as_str_list(row.get('output_artifact_ids'))))} |"
        )
    lines.append("")
    return lines


def _render_route_scoreboard(scoreboard: list[Any]) -> list[str]:
    lines = ["## Route Scoreboard", ""]
    if not scoreboard:
        lines.extend(["No routes recorded yet.", ""])
        return lines
    for raw_route in scoreboard:
        route = _as_mapping(raw_route)
        lines.append(
            f"- `{route.get('route_id', '')}` `{route.get('scoreboard_status', '')}` score={route.get('score', '')} "
            f"root_distance={route.get('root_distance', '')} verified={route.get('verified_inference_count', 0)}/{route.get('inference_count', 0)}"
        )
    lines.append("")
    return lines


def _render_research_artifacts(artifacts: list[Any]) -> list[str]:
    lines = ["## Recent Research Artifacts", ""]
    if not artifacts:
        lines.extend(["No research artifacts recorded yet.", ""])
        return lines
    for raw_artifact in artifacts[:32]:
        artifact = _as_mapping(raw_artifact)
        summary = artifact.get("metadata_summary") or artifact.get("content_summary") or ""
        lines.append(
            f"- `{artifact.get('artifact_id', '')}` `{artifact.get('artifact_type', '')}` by `{artifact.get('producer_role', '')}` "
            f"rev={artifact.get('state_revision', '')} {summary} path=`{artifact.get('path', '')}`"
        )
    return lines


def _run_snapshot(
    state: Mapping[str, Any],
    metrics: Mapping[str, Any],
    result: Mapping[str, Any],
    runs: list[Mapping[str, Any]],
    audit: Mapping[str, Any],
    history_entries: list[dict[str, Any]],
    usage_summary: Mapping[str, Any],
) -> dict[str, Any]:
    token_budget = _as_mapping(metrics.get("token_budget"))
    latest_run = runs[-1] if runs else {}
    latest_history = history_entries[-1] if history_entries else {}
    warnings = _as_str_list(audit.get("warnings"))
    if warnings:
        verifier_health = f"{len(warnings)} warning(s): {warnings[0]}"
    else:
        verifier_health = (
            f"{audit.get('verifier_run_count', 0)} run(s), "
            f"{len(_as_list(audit.get('verifier_ready_routes')))} route(s) ready"
        )
    latest_run_summary = "none"
    if latest_history:
        latest_run_summary = str(latest_history.get("primary_action_summary") or "planned action")
    elif latest_run:
        latest_run_summary = (
            f"`{latest_run.get('run_id', '')}` {_actor_role(latest_run)} "
            f"mode=`{latest_run.get('mode', '')}` status=`{latest_run.get('status', '')}`"
        )
    total_usage = _as_mapping(usage_summary.get("total_recorded"))
    storage = _as_mapping(metrics.get("benchmark_storage"))
    math_yield = _as_mapping(metrics.get("math_yield"))
    root_progress = _as_mapping(metrics.get("root_progress"))
    public_status = str(result.get("public_status") or "")
    raw_active_debt_count = metrics.get("active_debt_count", 0)
    raw_blocking_debt_count = metrics.get("blocking_debt_count", 0)
    if public_status in {"solved", "solved_pending_final_writer"}:
        open_case_count = 0
        open_blocking_case_count = 0
    else:
        open_case_count = raw_active_debt_count
        open_blocking_case_count = raw_blocking_debt_count
    return {
        "public_status": public_status,
        "result_kind": result.get("result_kind", ""),
        "relation_to_target": result.get("relation_to_target", ""),
        "summary": result.get("summary", ""),
        "revision": metrics.get("revision", 0),
        "claim_count": metrics.get("claim_count", 0),
        "verified_claim_count": metrics.get("verified_claim_count", 0),
        "integrated_claim_count": metrics.get("integrated_claim_count", 0),
        "route_count": metrics.get("route_count", 0),
        "active_route_count": metrics.get("active_route_count", 0),
        "active_debt_count": open_case_count,
        "blocking_debt_count": open_blocking_case_count,
        "open_case_count": open_case_count,
        "open_blocking_case_count": open_blocking_case_count,
        "ledger_active_debt_count": raw_active_debt_count,
        "ledger_blocking_debt_count": raw_blocking_debt_count,
        "tokens_spent_reported": token_budget.get("spent_reported", 0),
        "tokens_total": token_budget.get("total", 0),
        # Budget actually consumed = total - remaining (cached input is not
        # charged, so this is less than recorded_tokens which counts everything).
        "tokens_budget_spent": max(0, int(token_budget.get("total", 0) or 0) - int(token_budget.get("remaining", 0) or 0)),
        "tokens_remaining": token_budget.get("remaining", 0),
        "tokens_reserved_verification": token_budget.get("reserved_verification", 0),
        "recorded_tokens": total_usage.get("total_tokens", 0),
        "recorded_cached_tokens": total_usage.get("cached_input_tokens", 0),
        "recorded_wall_seconds": total_usage.get("wall_time_seconds", 0),
        "recorded_peak_memory_mb": total_usage.get("peak_memory_mb", 0),
        "stored_memory_artifacts_bytes": storage.get("stored_memory_artifacts_bytes", 0),
        "native_result_dir_bytes": storage.get("native_result_dir_bytes", 0),
        "downloaded_source_dir_bytes": storage.get("downloaded_source_dir_bytes", 0),
        "proof_artifact_count": math_yield.get("proof_artifact_count", 0),
        "diagnostic_artifact_count": math_yield.get("diagnostic_artifact_count", 0),
        "proof_to_diagnostic_ratio": math_yield.get("proof_to_diagnostic_ratio", 0),
        "tokens_per_verified_claim": math_yield.get("tokens_per_verified_claim", 0),
        "root_progress_score": root_progress.get("score", 0),
        "root_local_blocking_debt_count": root_progress.get("root_local_blocking_debt_count", 0),
        "verified_root_adjacent_claim_count": root_progress.get("verified_root_adjacent_claim_count", 0),
        "integrated_root_adjacent_claim_count": root_progress.get("integrated_root_adjacent_claim_count", 0),
        "killed_root_route_count": root_progress.get("killed_root_route_count", 0),
        "latest_run_summary": latest_run_summary,
        "verifier_health": verifier_health,
    }


def _current_invocation(history: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw_entry in history[-12:]:
        entry = _as_mapping(raw_entry)
        action = _as_mapping(entry.get("action"))
        execution = _as_mapping(entry.get("execution"))
        outcome = _as_mapping(entry.get("patch_outcome"))
        parallel_actions = [_action_summary(_as_mapping(item)) for item in _as_list(entry.get("parallel_actions"))]
        parallel_results = [
            _action_result_summary(_as_mapping(item))
            for item in _as_list(entry.get("action_results"))
            if _as_mapping(item).get("is_companion")
        ]
        if parallel_results:
            parallel_actions = parallel_results
        patch_summary = ""
        if outcome:
            patch_summary = f"accepted={outcome.get('accepted', '')}"
            if outcome.get("errors"):
                patch_summary += f" errors={'; '.join(_as_str_list(outcome.get('errors'))[:2])}"
        entries.append(
            {
                "step": entry.get("step", ""),
                "execution_phase": entry.get("execution_phase", ""),
                "primary_action_summary": _action_summary(action),
                "execution_summary": _execution_summary(execution, entry),
                "patch_summary": patch_summary,
                "parallel_action_summaries": parallel_actions,
                "live_session_updates": _live_session_updates(entry),
                "terminal_classification": entry.get("terminal_classification", ""),
                "stop_reason": entry.get("stop_reason", ""),
            }
        )
    return entries


def _live_logs(history_entries: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for entry in history_entries[-4:]:
        for update in _as_list(entry.get("live_session_updates")):
            logs.append(_as_dict(update))
    logs.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("run_id") or "")))
    return logs[-8:]


def _usage_summary(runs: list[Mapping[str, Any]], history: list[Mapping[str, Any]]) -> dict[str, Any]:
    recorded_run_ids = {str(row.get("run_id") or "") for row in runs}
    live_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_entry in history:
        for update in _live_session_updates(_as_mapping(raw_entry)):
            run_id = str(update.get("run_id") or "")
            if run_id:
                live_by_id[run_id] = update
    active_live = [update for run_id, update in live_by_id.items() if run_id not in recorded_run_ids]
    return {
        "total_recorded": _usage_scope(runs, note="all completed child runs in this benchmark state, including resumed segments"),
        "active_live_children": _live_usage_scope(active_live),
    }


def _usage_scope(rows: list[Mapping[str, Any]], *, note: str = "") -> dict[str, Any]:
    peak_memory = max((float(row.get("peak_memory_mb", 0.0) or 0.0) for row in rows), default=0.0)
    return {
        "run_count": len(rows),
        "total_tokens": sum(_token_total(row) for row in rows),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in rows),
        "reasoning_output_tokens": sum(int(row.get("reasoning_output_tokens") or 0) for row in rows),
        "wall_time_seconds": round(sum(float(row.get("wall_time_seconds", 0.0) or 0.0) for row in rows), 3),
        "peak_memory_mb": round(peak_memory, 1),
        "memory_recorded": any(float(row.get("peak_memory_mb", 0.0) or 0.0) > 0 for row in rows),
        "note": note,
    }


def _live_usage_scope(updates: list[Mapping[str, Any]]) -> dict[str, Any]:
    usage_rows = [_live_usage_row(update) for update in updates]
    return {
        "run_count": len(updates),
        "total_tokens": sum(_token_total(row) for row in usage_rows),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in usage_rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in usage_rows),
        "reasoning_output_tokens": sum(int(row.get("reasoning_output_tokens") or 0) for row in usage_rows),
        "wall_time_seconds": round(sum(float(update.get("elapsed_seconds", 0.0) or 0.0) for update in updates), 3),
        "peak_memory_mb": round(max((float(update.get("peak_memory_mb", 0.0) or 0.0) for update in updates), default=0.0), 1),
        "memory_recorded": any(float(update.get("peak_memory_mb", 0.0) or 0.0) > 0 for update in updates),
        "note": "active child token counts come from live Codex session telemetry when available",
    }


def _live_usage_row(update: Mapping[str, Any]) -> Mapping[str, Any]:
    usage = _as_mapping(update.get("usage"))
    return usage if usage else update


def _parallel_exchange_payload(store: ProofStateStore) -> list[dict[str, Any]]:
    path = store.state_dir / "parallel_exchange.jsonl"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    signals: list[dict[str, Any]] = []
    for line in lines[-80:]:
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            signals.append(payload)
    return signals[-24:]


def _live_session_updates(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    live = entry.get("live_session_updates")
    if isinstance(live, Mapping):
        updates = [_as_dict(value) for value in live.values()]
    else:
        updates = [_as_dict(value) for value in _as_list(live)]
    updates = [update for update in updates if update]
    updates.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("run_id") or "")))
    return updates


def _run_timeline(runs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for row in runs[-80:]:
        timeline.append(
            {
                "created_at": row.get("created_at", ""),
                "run_id": row.get("run_id", ""),
                "actor_role": _actor_role(row),
                "mode": row.get("mode", ""),
                "search_intent": row.get("search_intent", ""),
                "researcher_work_mode": row.get("researcher_work_mode", ""),
                "work_mode_source": row.get("work_mode_source", ""),
                "failure_kind": row.get("failure_kind", ""),
                "target_id": row.get("target_id", ""),
                "route_id": row.get("route_id", ""),
                "status": row.get("status", ""),
                "total_tokens": _token_total(row),
                "wall_time_seconds": row.get("wall_time_seconds", 0),
                "output_artifact_ids": _json_list(row.get("output_artifact_ids_json")),
            }
        )
    return timeline


def _decomposition_board(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    debts_by_owner: dict[str, list[Mapping[str, Any]]] = {}
    for debt in state.get("debts", []):
        if debt.get("status") != "active":
            continue
        debts_by_owner.setdefault(str(debt.get("owner_id") or ""), []).append(debt)
    failed_plan_ids = _failed_decomposition_plan_ids(state)
    plans: list[dict[str, Any]] = []
    rows = [
        row for row in state.get("artifacts", [])
        if row.get("artifact_type") in {"decomposition_plan", "failed_decomposition_plan"}
    ]
    rows.sort(key=lambda row: (int(row.get("state_revision", 0)), str(row.get("created_at") or "")), reverse=True)
    for row in rows[:24]:
        metadata = _json_object(row.get("metadata_json"))
        plan_id = str(metadata.get("decomposition_plan_id") or metadata.get("plan_id") or row.get("artifact_id") or "")
        status = str(metadata.get("status") or "active").lower()
        if row.get("artifact_type") == "failed_decomposition_plan" or plan_id in failed_plan_ids:
            status = "failed"
        subgoal_ids = _metadata_strings(metadata, "subgoal_claim_ids", "subgoals", "claim_ids")
        subgoals = [_subgoal_status(claim_id, claims, debts_by_owner) for claim_id in subgoal_ids]
        blocked_count = sum(1 for item in subgoals if item["blocking_debt_count"] > 0)
        verified_count = sum(
            1
            for item in subgoals
            if item["validation_status"] in {"informally_verified", "formally_verified", "refuted"}
            or item["lifecycle_status"] == "integrated"
        )
        plans.append(
            {
                "plan_id": plan_id,
                "artifact_id": row.get("artifact_id", ""),
                "artifact_type": row.get("artifact_type", ""),
                "status": status,
                "plan_kind": metadata.get("plan_kind", ""),
                "trigger": metadata.get("trigger", ""),
                "parent_claim_id": metadata.get("parent_claim_id") or metadata.get("target_id") or "",
                "route_id": metadata.get("route_id", ""),
                "subgoal_count": len(subgoals),
                "verified_subgoal_count": verified_count,
                "blocked_subgoal_count": blocked_count,
                "dependency_edge_count": len(_json_list(metadata.get("dependency_edges"))),
                "parallel_group_count": len(_json_list(metadata.get("parallelizable_groups"))),
                "subgoals": subgoals,
                "assembly_argument": _first_text(
                    metadata,
                    "assembly_argument",
                    "why_subgoals_imply_parent",
                    "case_exhaustiveness",
                ),
                "path": row.get("path", ""),
                "state_revision": row.get("state_revision", 0),
                "created_at": row.get("created_at", ""),
            }
        )
    return plans


def _failed_decomposition_plan_ids(state: Mapping[str, Any]) -> set[str]:
    failed: set[str] = set()
    for row in state.get("artifacts", []):
        if row.get("artifact_type") != "failed_decomposition_plan":
            continue
        metadata = _json_object(row.get("metadata_json"))
        for key in ("decomposition_plan_id", "plan_id", "source_decomposition_plan_id"):
            value = str(metadata.get(key) or "").strip()
            if value:
                failed.add(value)
    return failed


def _subgoal_status(
    claim_id: str,
    claims: Mapping[str, Mapping[str, Any]],
    debts_by_owner: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any]:
    claim = _as_mapping(claims.get(claim_id))
    debts = debts_by_owner.get(claim_id, [])
    return {
        "claim_id": claim_id,
        "validation_status": claim.get("validation_status", "missing"),
        "lifecycle_status": claim.get("lifecycle_status", "missing"),
        "blocking_debt_count": sum(1 for debt in debts if debt.get("severity") == "blocking"),
        "active_debt_count": len(debts),
    }


def _open_case_groups(state: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "Blocking": [],
        "Citation / Hypothesis": [],
        "Verifier Repair": [],
        "Decomposition / Regulator": [],
        "Other": [],
    }
    active_debts = [row for row in state.get("debts", []) if row.get("status") == "active"]
    active_debts.sort(
        key=lambda row: (
            row.get("severity") != "blocking",
            row.get("owner_id", ""),
            row.get("debt_id", ""),
        )
    )
    for debt in active_debts[:80]:
        group = _debt_group(debt)
        groups[group].append(
            {
                "debt_id": debt.get("debt_id", ""),
                "severity": debt.get("severity", ""),
                "owner": f"{debt.get('owner_type', '')}:{debt.get('owner_id', '')}",
                "debt_type": debt.get("debt_type", ""),
                "obligation": debt.get("obligation", ""),
                "suggested_next_target": debt.get("suggested_next_target", ""),
                "repeated_count": debt.get("repeated_count", 1),
                "source_artifact_ids": _json_list(debt.get("source_artifact_ids_json")),
            }
        )
    return groups


def _research_artifacts(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifacts = [row for row in state.get("artifacts", []) if row.get("artifact_type") in RESEARCH_ARTIFACT_TYPES]
    priority = {
        "final_proof": 0,
        "partial_proof_report": 1,
        "integration_report": 2,
        "verification_report": 3,
        "proof_dossier": 4,
        "proof_blueprint": 5,
        "research_notebook": 6,
        "decomposition_plan": 7,
        "source_adaptation_notes": 8,
        "source_synthesis_report": 9,
        "literature_search_request": 10,
        "cas_experiment_report": 11,
        "advisor_report": 12,
        "stop_summary_report": 13,
        "writer_report": 14,
    }
    artifacts.sort(
        key=lambda row: (
            int(row.get("state_revision", 0)),
            -priority.get(str(row.get("artifact_type") or ""), 99),
            str(row.get("created_at") or ""),
        ),
        reverse=True,
    )
    return [
        {
            "artifact_id": row.get("artifact_id", ""),
            "artifact_type": row.get("artifact_type", ""),
            "producer_role": row.get("producer_role", ""),
            "state_revision": row.get("state_revision", 0),
            "content_summary": row.get("content_summary", ""),
            "metadata_summary": _artifact_metadata_summary(row),
            "path": row.get("path", ""),
            "created_at": row.get("created_at", ""),
        }
        for row in artifacts[:32]
    ]


def _render_researcher_mode_state(state: Mapping[str, Any]) -> list[str]:
    lines = ["## Researcher Mode & Advisor Supervision", ""]
    if not state:
        lines.extend(["No researcher work-mode history yet.", ""])
        return lines
    current = _as_mapping(state.get("current"))
    predicted = _as_mapping(state.get("predicted_next"))
    directive = _as_mapping(state.get("advisor_directive"))
    cycle = " -> ".join(str(item) for item in _as_list(state.get("cycle")))
    lines.append(f"- Mode loop: `{cycle}` (advisor may override)")
    if current:
        lines.append(
            f"- Last researcher pass: `{current.get('work_mode', '')}` (source `{current.get('source', '')}`, status `{current.get('status', '')}`)"
        )
    else:
        lines.append("- Last researcher pass: none recorded yet")
    if predicted.get("work_mode"):
        lines.append(f"- Next default mode: `{predicted.get('work_mode')}` ({predicted.get('source', '')})")
    if directive:
        steps = directive.get("steps_remaining", directive.get("steps", 1))
        reason = str(directive.get("reason") or "").strip()
        lines.append(
            f"- ACTIVE ADVISOR DIRECTIVE: `{directive.get('work_mode', '')}` for `{steps}` more researcher pass(es)"
            + (f" — {reason}" if reason else "")
        )
    else:
        lines.append("- Advisor directive: none active (default rotation)")
    history = [item for item in _as_list(state.get("history")) if isinstance(item, Mapping)]
    if history:
        trail = " ".join(f"`{item.get('work_mode', '')}`" for item in reversed(history[:10]))
        lines.append(f"- Recent mode trail (oldest to newest): {trail}")
    villain = _as_mapping(state.get("villain"))
    if villain:
        v_current = _as_mapping(villain.get("current"))
        v_directive = _as_mapping(villain.get("advisor_directive"))
        v_cycle = " -> ".join(str(item) for item in _as_list(villain.get("cycle")))
        v_bits = [f"loop `{v_cycle}`"]
        if v_current:
            v_bits.append(f"last pass `{v_current.get('work_mode', '')}` ({v_current.get('source', '')})")
        if v_directive:
            v_reason = str(v_directive.get("reason") or "").strip()
            v_bits.append(
                f"ACTIVE DIRECTIVE `{v_directive.get('work_mode', '')}`" + (f" — {v_reason}" if v_reason else "")
            )
        else:
            v_bits.append("no directive")
        v_history = [item for item in _as_list(villain.get("history")) if isinstance(item, Mapping)]
        if v_history:
            v_trail = " ".join(f"`{item.get('work_mode', '')}`" for item in reversed(v_history[:10]))
            v_bits.append(f"trail {v_trail}")
        lines.append(f"- Villain (refuter): {'; '.join(v_bits)}")
    lines.append("")
    return lines


def _artifact_metadata_summary(row: Mapping[str, Any]) -> str:
    metadata = _json_object(row.get("metadata_json"))
    keys = (
        "claim_id",
        "target_id",
        "route_id",
        "decomposition_plan_id",
        "search_request_id",
        "verdict",
        "status",
        "result_kind",
        "relation_to_target",
        "theorem_matching_confidence",
        "directed_researcher_mode",
        "directed_researcher_mode_reason",
        "directed_researcher_mode_steps",
        "directed_villain_mode",
        "directed_villain_mode_reason",
        "directed_villain_mode_steps",
    )
    pieces = []
    for key in keys:
        value = metadata.get(key)
        if value in (None, "", [], {}):
            continue
        pieces.append(f"{key}={_short_json(value)}")
    return "; ".join(pieces)


def _verifier_audit(state: Mapping[str, Any], runs: list[Mapping[str, Any]]) -> dict[str, Any]:
    verifier_runs = [row for row in runs if _actor_role(row) == "strict_informal_verifier"]
    strict_verifier_reports = _strict_verifier_reports(state)
    verified_inference_count = sum(
        1
        for row in state.get("inferences", [])
        if row.get("validation_status") in {"informally_verified", "formally_verified"}
    )
    verified_claim_count = sum(
        1
        for row in state.get("claims", [])
        if row.get("validation_status") in {"informally_verified", "formally_verified"}
    )
    failed_launches = [row for row in verifier_runs if _is_failed_launch(row)]
    audit_runs = [row for row in verifier_runs if not _is_failed_launch(row)]
    zero_token = [row for row in audit_runs if _token_total(row) == 0]
    low_token = [row for row in audit_runs if 0 < _token_total(row) < 100]
    ready_routes = _verifier_ready_routes(state)
    warnings: list[str] = []
    if ready_routes and not verifier_runs and not strict_verifier_reports:
        warnings.append("Verifier-ready route evidence exists, but no strict verifier run or report artifact is recorded.")
    if zero_token:
        warnings.append("One or more strict verifier runs recorded zero tokens; inspect token parsing or launch logs.")
    if low_token:
        warnings.append("One or more strict verifier runs recorded unusually low token usage.")
    return {
        "verifier_run_count": len(verifier_runs),
        "strict_verifier_report_count": len(strict_verifier_reports),
        "strict_verifier_report_artifact_ids": [row.get("artifact_id", "") for row in strict_verifier_reports],
        "verified_inference_count": verified_inference_count,
        "verified_claim_count": verified_claim_count,
        "zero_token_verifier_runs": [row.get("run_id", "") for row in zero_token],
        "low_token_verifier_runs": [row.get("run_id", "") for row in low_token],
        "failed_verifier_launches": [row.get("run_id", "") for row in failed_launches],
        "verifier_ready_routes": ready_routes,
        "warnings": warnings,
    }


def _is_failed_launch(row: Mapping[str, Any]) -> bool:
    status = str(row.get("status") or "").lower()
    if status not in {"failed", "timeout", "cancelled", "terminated"}:
        return False
    outputs = _as_list(row.get("output_artifact_ids"))
    if not outputs:
        outputs = _json_list(row.get("output_artifact_ids_json"))
    return _token_total(row) == 0 and not outputs


def _strict_verifier_reports(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = state.get("research_artifacts", [])
    return [
        row
        for row in artifacts
        if row.get("artifact_type") == "verification_report" and row.get("producer_role") == "strict_informal_verifier"
    ]


def _verifier_ready_routes(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    return verifier_ready_route_summaries(state)


def _action_summary(action: Mapping[str, Any]) -> str:
    if not action:
        return ""
    fields = [
        ("actor", action.get("actor_role")),
        ("mode", action.get("display_mode") or action.get("mode")),
        ("internal_mode", action.get("mode") if action.get("display_mode") else ""),
        ("work_mode", action.get("researcher_work_mode")),
        ("target", action.get("target_id")),
        ("route", action.get("route_id")),
        ("intent", action.get("search_intent")),
        ("plan", action.get("decomposition_plan_id")),
    ]
    return " ".join(f"{key}=`{value}`" for key, value in fields if value not in (None, ""))


def _action_result_summary(result: Mapping[str, Any]) -> str:
    action = _as_mapping(result.get("action"))
    execution = _as_mapping(result.get("execution"))
    outcome = _as_mapping(result.get("patch_outcome"))
    pieces = [_action_summary(action)]
    status = result.get("status") or execution.get("status")
    if status:
        pieces.append(f"status=`{status}`")
    if outcome:
        pieces.append(f"patch_accepted=`{outcome.get('accepted', '')}`")
    return " ".join(piece for piece in pieces if piece)


def _execution_summary(execution: Mapping[str, Any], entry: Mapping[str, Any]) -> str:
    if execution:
        usage = _as_mapping(execution.get("usage"))
        tokens = usage.get("total_tokens")
        token_text = f" tokens={tokens}" if tokens not in (None, "") else ""
        return f"status=`{execution.get('status', '')}` returncode=`{execution.get('returncode', '')}`{token_text}"
    if entry.get("terminal_classification"):
        return f"terminal=`{entry.get('terminal_classification', '')}`"
    if entry.get("dry_run_note"):
        return str(entry.get("dry_run_note"))
    return ""


def _actor_role(row: Mapping[str, Any]) -> str:
    actor = str(row.get("actor_role") or "")
    if actor:
        return actor
    mode = str(row.get("mode") or "")
    route_id = str(row.get("route_id") or "")
    if mode == "prove" and route_id:
        return "strict_informal_verifier"
    if mode in {"retrieve", "synthesize_sources", "audit_definitions"}:
        return "literature_researcher"
    if mode == "integrate":
        return "integration_verifier"
    if mode == "triage_routes":
        return "phd_advisor"
    if mode == "refute":
        return "villain"
    if mode == "write":
        return "writer"
    return "researcher" if mode else ""


def _token_total(row: Mapping[str, Any]) -> int:
    explicit = int(row.get("total_tokens") or 0)
    if explicit > 0:
        return explicit
    return max(
        0,
        int(row.get("input_tokens") or 0)
        + int(row.get("output_tokens") or 0)
        + int(row.get("reasoning_output_tokens") or 0),
    )


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


def _debt_group(debt: Mapping[str, Any]) -> str:
    text = " ".join(
        str(debt.get(key) or "").lower()
        for key in ("debt_type", "obligation", "owner_type", "owner_id", "suggested_next_target")
    )
    if debt.get("severity") == "blocking":
        return "Blocking"
    if any(word in text for word in ("citation", "source", "hypothesis", "hypotheses", "literature", "theorem")):
        return "Citation / Hypothesis"
    if any(word in text for word in ("verifier", "verification", "packet", "proof gap", "gap")):
        return "Verifier Repair"
    if any(word in text for word in ("decomposition", "subgoal", "branch", "advisor", "regulator", "case")):
        return "Decomposition / Regulator"
    return "Other"


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    return []


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _metadata_strings(metadata: Mapping[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = metadata.get(key)
        for item in _json_list(raw):
            if isinstance(item, Mapping):
                value = str(item.get("claim_id") or item.get("id") or item.get("name") or "").strip()
            else:
                value = str(item or "").strip()
            if value and value not in values:
                values.append(value)
    return values


def _first_text(metadata: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_str_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value)]


def _short_json(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    else:
        text = str(value)
    return _cell(text)


def _clip_log_tail(text: str, max_chars: int = 3_000) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    return "[...]\n" + stripped[-max_chars:]


def _write_text_atomic(path: Path, text: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _cell(value: Any) -> str:
    text = str(value or "")
    return text.replace("|", "\\|").replace("\n", " ")[:240]
