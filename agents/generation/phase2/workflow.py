from __future__ import annotations

import inspect
import json
import os
import re
import time
import threading
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping, Optional

from .codex_runner import (
    DEFAULT_CHILD_TIMEOUT_SECONDS,
    DEFAULT_CODEX_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_SANDBOX,
    actor_role_for_action,
    attached_artifact_ids,
    execute_session,
    prepare_session,
    run_metrics_operation,
)

# Same-role session resume: keep the same agent alive across consecutive same-role,
# same-target primary steps (so it does not re-read artifacts each step), then
# cold-start to reset the context window after this many resumes.
MAX_RESUME_CHAIN = 4
from .console import write_run_console
from .metrics import compute_metrics
from .models import utc_now
from .patches import _normalize_patch_aliases, apply_patch, apply_patch_with_stale_retry
from .report import write_markdown_report
from .result_status import classify_result
from .research_policy import (
    DEFAULT_RESEARCH_MODE,
    DEFAULT_WEB_SEARCH,
    normalize_research_mode,
    research_intent_for_action,
    search_policy_for_action,
)
from .scheduler import _artifact_is_proof_candidate, next_action, parallel_companion_actions, verifier_ready_route_summaries
from .store import ProofStateStore
from . import steering

STOP_WRITER_CONTEXT_MIN_CHARS = 150_000
STOP_WRITER_PROOF_CRITICAL_INTENTS = {
    "proof_candidate_route_conversion": "scheduler selected proof-candidate route conversion as the next mathematical action",
    "proof_architecture_pressure": "scheduler selected proof-architecture pressure synthesis before writer closure",
}
STOP_WRITER_NO_ROUTE_TOKEN_THRESHOLD = 1_000_000
DEFAULT_STALE_RETRY_RECOVERY_ATTEMPTS = 2
STALE_RETRY_RECOVERY_ATTEMPTS_ENV = "ALBILICH_STALE_RETRY_RECOVERY_ATTEMPTS"
STALE_RETRY_FAILURE_FRAGMENT = "Codex stream retry stalled"

Executor = Callable[..., Mapping[str, Any]]
TERMINAL_MODES = {"stop_with_partial_results", "stop_solved"}
DOWNLOAD_PATH_RE = re.compile(r"(?:/[^\s\"'<>]*agents/generation/downloads(?:/[^\s\"'<>]+)?|agents/generation/downloads(?:/[^\s\"'<>]+)?)")
ARTIFACT_PATH_RE = re.compile(
    r"(?:/[^\s\"'<>]*agents/generation/results/[^\s\"'<>]+/phase2/artifacts/[^\s\"'<>]+|"
    r"agents/generation/results/[^\s\"'<>]+/phase2/artifacts/[^\s\"'<>]+)"
)


def run_workflow(
    store: ProofStateStore,
    *,
    steps: int = 10,
    execute: bool = False,
    max_context_chars: int = 12_000,
    model_profile: str = "default",
    model: str = DEFAULT_CODEX_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    codex_bin: str = "codex",
    sandbox: str = DEFAULT_SANDBOX,
    web_search: str | None = DEFAULT_WEB_SEARCH,
    research_mode: str | None = DEFAULT_RESEARCH_MODE,
    timeout_sec: int = DEFAULT_CHILD_TIMEOUT_SECONDS,
    max_wall_seconds: int | None = None,
    parallel_librarian_verifier: bool = True,
    stop_on_rejection: bool = True,
    write_on_stop: bool = True,
    write_report: bool = False,
    write_console: bool = True,
    session_resume: bool = True,
    executor: Optional[Executor] = None,
) -> Dict[str, Any]:
    """Run the Albilich v1 scheduler as an executable workflow.

    With execute=False this produces bounded plans. With execute=True it launches
    one Codex session per scheduler action, applies the returned patch, records
    run metrics, and repeats until the root is integrated, the budget stops work,
    or the step limit is reached.
    """
    research_mode = normalize_research_mode(research_mode)
    history = []
    console_path = ""
    console_lock = threading.Lock()
    started = time.monotonic()
    # Per-role live session registry for same-role session resume:
    # actor_role -> {session_id, target_id, chain_len, last_revision}.
    role_sessions: Dict[str, Dict[str, Any]] = {}
    stale_retry_recoveries = 0
    max_stale_retry_recoveries = _stale_retry_recovery_attempts()

    def write_console_snapshot_locked() -> None:
        nonlocal console_path
        if write_console:
            console_path = str(write_run_console(store, history=history))

    def record_entry(entry: Dict[str, Any]) -> None:
        with console_lock:
            if not any(item is entry for item in history):
                history.append(entry)
            write_console_snapshot_locked()
            _write_partial_result_locked(store, history)

    def progress_callback_for(entry: Dict[str, Any]) -> Callable[[Mapping[str, Any]], None]:
        def update(progress: Mapping[str, Any]) -> None:
            run_id = str(progress.get("run_id") or f"live-{len(entry.get('live_session_updates', {})) + 1}")
            with console_lock:
                if not any(item is entry for item in history):
                    history.append(entry)
                entry["execution_phase"] = "running"
                live_updates = entry.setdefault("live_session_updates", {})
                if not isinstance(live_updates, dict):
                    live_updates = {}
                    entry["live_session_updates"] = live_updates
                live_updates[run_id] = dict(progress)
                write_console_snapshot_locked()

        return update

    outage_streak = 0
    outage_refunds = 0
    # steps <= 0 means "run until the wall clock, token budget, or a terminal
    # scheduler state stops the attempt" — no manual relaunch chains.
    step_limit = steps if steps > 0 else 10_000_000
    index = -1
    while True:
        index += 1
        if index >= step_limit:
            break
        remaining_wall = _remaining_wall_seconds(started, max_wall_seconds)
        if remaining_wall is not None and remaining_wall <= 0:
            action = _wall_limit_action(max_wall_seconds)
            entry = {
                "step": index + 1,
                "action": action,
                "stop_reason": action["reason"],
                "terminal_classification": action["terminal_classification"],
            }
            if write_on_stop:
                _attach_stop_writer(
                    store,
                    entry,
                    action,
                    execute=execute,
                    research_mode=research_mode,
                    web_search=web_search,
                    max_context_chars=max_context_chars,
                    model_profile=model_profile,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    codex_bin=codex_bin,
                    sandbox=sandbox,
                    timeout_sec=timeout_sec,
                    executor=executor,
                )
            record_entry(entry)
            break

        action = next_action(store, research_mode=research_mode, web_search=web_search)
        # Human steering present at step start is injected into this step's agent context
        # (via build_context_manifest); mark it consumed once the step has run so it is
        # delivered exactly once without halting the run.
        pending_steering_ids = [m.get("id") for m in steering.unconsumed_steering(store.state_dir)]
        actions = [action]
        if parallel_librarian_verifier:
            actions.extend(
                parallel_companion_actions(
                    store,
                    action,
                    research_mode=research_mode,
                    web_search=web_search,
                )
            )
        entry: Dict[str, Any] = {"step": index + 1, "action": action}
        if len(actions) > 1:
            entry["parallel_actions"] = actions[1:]
        if action["mode"] in TERMINAL_MODES:
            entry["stop_reason"] = action.get("reason", "scheduler stopped")
            entry["terminal_classification"] = action.get("terminal_classification", "partial")
            if action["mode"] == "stop_with_partial_results" and write_on_stop:
                _attach_stop_writer(
                    store,
                    entry,
                    action,
                    execute=execute,
                    research_mode=research_mode,
                    web_search=web_search,
                    max_context_chars=max_context_chars,
                    model_profile=model_profile,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    codex_bin=codex_bin,
                    sandbox=sandbox,
                    timeout_sec=timeout_sec,
                    executor=executor,
                )
            record_entry(entry)
            break

        # Same-role session resume: if the primary action is the same role on the
        # same target as that role's previous primary step (and under the chain cap),
        # resume its live agent with a compact delta instead of a cold restart.
        primary_role = actor_role_for_action(action)
        primary_target = str(action.get("target_id") or "root")
        prev_sess = role_sessions.get(primary_role)
        resume_id = ""
        resume_since: Optional[int] = None
        if (
            session_resume
            and prev_sess
            and prev_sess.get("session_id")
            and prev_sess.get("target_id") == primary_target
            and int(prev_sess.get("chain_len", 0)) < MAX_RESUME_CHAIN
        ):
            resume_id = str(prev_sess["session_id"])
            resume_since = int(prev_sess.get("last_revision") or 0)
        scheduled = [
            _prepare_scheduled_session(
                store,
                scheduled_action,
                research_mode=research_mode,
                web_search=web_search,
                max_context_chars=max_context_chars,
                model_profile=model_profile,
                is_companion=(position > 0),
                resume_session_id=(resume_id if position == 0 else ""),
                resume_since_revision=(resume_since if position == 0 else None),
            )
            for position, scheduled_action in enumerate(actions)
        ]
        for scheduled_index, scheduled_item in enumerate(scheduled):
            scheduled_item["scheduled_index"] = scheduled_index
            scheduled_item["parallel_group_size"] = len(scheduled)
        entry["session_plan"] = scheduled[0]["session_plan"]
        if len(scheduled) > 1:
            entry["parallel_session_plans"] = [item["session_plan"] for item in scheduled[1:]]
        if not execute:
            entry["execution_phase"] = "planned"
            entry["dry_run_note"] = "dry-run planning stops after one action because proof state is not mutated without execution"
            record_entry(entry)
            break

        entry["execution_phase"] = "running"
        entry["started_at"] = utc_now()
        record_entry(entry)

        step_timeout = timeout_sec
        if remaining_wall is not None:
            step_timeout = max(1, min(timeout_sec, int(remaining_wall)))
        applied_results: list[Dict[str, Any]] = []
        pending_by_index = {
            int(item["scheduled_index"]): item
            for item in scheduled
        }
        completed_buffer: list[Dict[str, Any]] = []

        def flush_completed_results_locked(*, force: bool = False) -> None:
            changed = True
            while changed:
                changed = False
                for completed_item in sorted(list(completed_buffer), key=_merge_priority):
                    if not force and _blocked_by_pending_priority_barrier(completed_item, pending_by_index.values()):
                        continue
                    result = _apply_scheduled_results(
                        store,
                        [completed_item],
                        model=model,
                        reasoning_effort=reasoning_effort,
                        sandbox=sandbox,
                    )[0]
                    completed_item["action_result"] = result
                    completed_buffer.remove(completed_item)
                    applied_results.append(result)
                    entry["action_results"] = list(applied_results)
                    if not result.get("is_companion"):
                        entry["execution"] = result["execution"]
                        entry["patch_outcome"] = result["patch_outcome"]
                        entry["metrics_outcome"] = result["metrics_outcome"]
                    if len(applied_results) < len(scheduled) and str(result.get("status") or "") not in {"failed", "timeout", "no_patch", "patch_rejected", "cancelled"}:
                        entry["execution_phase"] = f"running: {len(applied_results)}/{len(scheduled)} completed"
                    else:
                        primary = next((row for row in applied_results if not row.get("is_companion")), None)
                        entry["execution_phase"] = str((primary or result).get("status") or "completed")
                    changed = True
                    break

        def apply_completed_item(completed_item: Dict[str, Any]) -> None:
            with console_lock:
                pending_by_index.pop(int(completed_item.get("scheduled_index", -1)), None)
                completed_buffer.append(completed_item)
                flush_completed_results_locked()
                write_console_snapshot_locked()

        executed_items = _execute_scheduled_sessions(
            store,
            scheduled,
            model=model,
            reasoning_effort=reasoning_effort,
            model_profile=model_profile,
            codex_bin=codex_bin,
            sandbox=sandbox,
            timeout_sec=step_timeout,
            executor=executor,
            progress_callback=progress_callback_for(entry),
            cancel_on_primary_failure=stop_on_rejection,
            result_callback=apply_completed_item,
        )
        with console_lock:
            flush_completed_results_locked(force=True)
            write_console_snapshot_locked()
        action_results = [
            item["action_result"]
            for item in executed_items
            if isinstance(item.get("action_result"), Mapping)
        ]
        if len(action_results) != len(executed_items):
            missing_items = [
                item
                for item in executed_items
                if not isinstance(item.get("action_result"), Mapping)
            ]
            missing_results = _apply_scheduled_results(
                store,
                missing_items,
                model=model,
                reasoning_effort=reasoning_effort,
                sandbox=sandbox,
            )
            for item, result in zip(missing_items, missing_results):
                item["action_result"] = result
            action_results = [
                item["action_result"]
                for item in executed_items
                if isinstance(item.get("action_result"), Mapping)
            ]
        entry["action_results"] = action_results
        primary_result = next((item for item in action_results if not item.get("is_companion")), action_results[0])
        entry["execution"] = primary_result["execution"]
        entry["patch_outcome"] = primary_result["patch_outcome"]
        entry["metrics_outcome"] = primary_result["metrics_outcome"]
        entry["execution_phase"] = str(primary_result.get("status") or "completed")
        entry["finished_at"] = utc_now()
        record_entry(entry)

        if pending_steering_ids:
            steering.mark_consumed(store.state_dir, pending_steering_ids)

        # Update the per-role session registry for same-role resume. Keep a healthy
        # session to continue next step; drop it on a failed/timed-out step so the
        # next same-role step cold-starts (graceful fallback).
        primary_status = str(primary_result.get("status") or "completed")
        new_session_id = str(primary_result.get("session_id") or "")
        if new_session_id and primary_status not in {"failed", "timeout"}:
            chain_len = (int(prev_sess.get("chain_len", 0)) + 1) if resume_id else 1
            role_sessions[primary_role] = {
                "session_id": new_session_id,
                "target_id": primary_target,
                "chain_len": chain_len,
                "last_revision": store.get_revision(),
            }
        else:
            role_sessions.pop(primary_role, None)

        # Backend-outage circuit breaker: a wave where every session died almost
        # instantly with zero token usage is a provider/network outage, not
        # mathematics. Back off exponentially and refund the step so an outage
        # cannot silently consume the step budget.
        if _looks_like_backend_outage(action_results):
            outage_streak += 1
            if outage_refunds < MAX_OUTAGE_STEP_REFUNDS:
                outage_refunds += 1
                index -= 1
            backoff = OUTAGE_BACKOFF_BASE_SECONDS * (2 ** min(outage_streak - 1, 4))
            backoff = min(OUTAGE_BACKOFF_MAX_SECONDS, backoff)
            outage_wall = _remaining_wall_seconds(started, max_wall_seconds)
            if outage_wall is not None:
                backoff = max(0, min(backoff, int(outage_wall) - 1))
            entry["outage_suspected"] = True
            entry["outage_streak"] = outage_streak
            entry["outage_backoff_seconds"] = backoff
            entry["execution_phase"] = f"backend_outage_backoff_{backoff}s"
            record_entry(entry)
            if backoff > 0:
                time.sleep(backoff)
            continue
        outage_streak = 0

        status = str(primary_result.get("status") or "completed")
        if status in {"failed", "timeout", "no_patch", "patch_rejected", "cancelled"} and stop_on_rejection:
            if _recoverable_parallel_stale_patch(action_results, primary_result):
                entry["recoverable_failure"] = True
                entry["recovery_reason"] = (
                    "Primary patch became stale after a sibling parallel patch advanced the proof "
                    "state; continuing from the newer revision instead of stopping the workflow."
                )
                entry["execution_phase"] = "recovering_after_parallel_stale_patch"
                record_entry(entry)
                continue
            if _recoverable_stale_retry_failure(action, primary_result):
                stale_retry_recoveries += 1
                entry["recoverable_failure"] = True
                if stale_retry_recoveries > max_stale_retry_recoveries:
                    entry["recovery_escalated"] = True
                    entry["recovery_reason"] = (
                        "Codex child session hit another stream retry stall; continuing so the "
                        "scheduler can recover instead of stopping the workflow on a transport failure"
                    )
                else:
                    entry["recovery_reason"] = (
                        "Codex child session hit a stream retry stall before producing a patch; "
                        "continuing to the scheduler instead of stopping the workflow"
                    )
                entry["recovery_attempt"] = stale_retry_recoveries
                entry["max_recovery_attempts"] = max_stale_retry_recoveries
                entry["execution_phase"] = "recovering_after_stale_retry"
                record_entry(entry)
                continue
            if write_on_stop:
                stop_action = _execution_stop_action(action, status, primary_result)
                entry["stop_reason"] = stop_action["reason"]
                entry["terminal_classification"] = stop_action["terminal_classification"]
                _attach_stop_writer(
                    store,
                    entry,
                    stop_action,
                    execute=execute,
                    research_mode=research_mode,
                    web_search=web_search,
                    max_context_chars=max_context_chars,
                    model_profile=model_profile,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    codex_bin=codex_bin,
                    sandbox=sandbox,
                    timeout_sec=timeout_sec,
                    executor=executor,
                )
                record_entry(entry)
            break
    else:
        if write_on_stop and classify_result(store).get("public_status") != "solved":
            action = _step_limit_action(steps)
            entry = {
                "step": steps + 1,
                "action": action,
                "stop_reason": action["reason"],
                "terminal_classification": action["terminal_classification"],
            }
            _attach_stop_writer(
                store,
                entry,
                action,
                execute=execute,
                research_mode=research_mode,
                web_search=web_search,
                max_context_chars=max_context_chars,
                model_profile=model_profile,
                model=model,
                reasoning_effort=reasoning_effort,
                codex_bin=codex_bin,
                sandbox=sandbox,
                timeout_sec=timeout_sec,
                executor=executor,
            )
            record_entry(entry)

    report_path = str(write_markdown_report(store)) if write_report else ""
    if write_console and not console_path:
        console_path = str(write_run_console(store, history=history))
    wall_time_seconds = time.monotonic() - started
    return {
        "problem_id": store.problem_id,
        "executed": execute,
        "steps": history,
        "metrics": compute_metrics(store),
        "result_status": classify_result(store),
        "report_path": report_path,
        "console_path": console_path,
        "wall_time_seconds": round(wall_time_seconds, 3),
        "wall_limit_seconds": max_wall_seconds,
        "parallel_librarian_verifier": parallel_librarian_verifier,
        "write_on_stop": write_on_stop,
        "write_console": write_console,
    }


def _stale_retry_recovery_attempts() -> int:
    raw = os.environ.get(STALE_RETRY_RECOVERY_ATTEMPTS_ENV, "").strip()
    if not raw:
        return DEFAULT_STALE_RETRY_RECOVERY_ATTEMPTS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_STALE_RETRY_RECOVERY_ATTEMPTS


def _recoverable_stale_retry_failure(action: Mapping[str, Any], result: Mapping[str, Any]) -> bool:
    if str(result.get("status") or "") != "timeout":
        return False
    execution = result.get("execution") if isinstance(result.get("execution"), Mapping) else {}
    patch_error = str(execution.get("patch_error") or "")
    patch_outcome = result.get("patch_outcome") if isinstance(result.get("patch_outcome"), Mapping) else {}
    for error in patch_outcome.get("errors", []) if isinstance(patch_outcome.get("errors"), list) else []:
        patch_error += "\n" + str(error)
    return STALE_RETRY_FAILURE_FRAGMENT in patch_error


def _recoverable_parallel_stale_patch(action_results: Any, primary_result: Mapping[str, Any]) -> bool:
    if str(primary_result.get("status") or "") != "patch_rejected":
        return False
    if not isinstance(action_results, list) or len(action_results) < 2:
        return False
    patch_outcome = primary_result.get("patch_outcome") if isinstance(primary_result.get("patch_outcome"), Mapping) else {}
    errors = patch_outcome.get("errors") if isinstance(patch_outcome, Mapping) else []
    if not isinstance(errors, list) or not any(str(error).startswith("stale patch:") for error in errors):
        return False
    for result in action_results:
        if result is primary_result:
            continue
        outcome = result.get("patch_outcome") if isinstance(result, Mapping) else {}
        if isinstance(outcome, Mapping) and outcome.get("accepted"):
            return True
    return False


def _attach_stop_writer(
    store: ProofStateStore,
    entry: Dict[str, Any],
    stop_action: Mapping[str, Any],
    *,
    execute: bool,
    research_mode: str,
    web_search: str | None,
    max_context_chars: int,
    model_profile: str,
    model: str,
    reasoning_effort: str,
    codex_bin: str,
    sandbox: str,
    timeout_sec: int,
    executor: Optional[Executor],
) -> None:
    blocker = _stop_writer_safety_blocker(store, research_mode=research_mode, web_search=web_search)
    if blocker:
        entry["stop_writer_blocked"] = True
        entry["stop_writer_blocker"] = blocker
        entry["stop_writer_action"] = _blocked_stop_writer_action(stop_action, blocker)
        return

    writer_action = _stop_writer_action(stop_action)
    scheduled = [
        _prepare_scheduled_session(
            store,
            writer_action,
            research_mode=research_mode,
            web_search=web_search,
            max_context_chars=max(max_context_chars, STOP_WRITER_CONTEXT_MIN_CHARS),
            model_profile=model_profile,
            is_companion=False,
        )
    ]
    entry["stop_writer_action"] = writer_action
    entry["stop_writer_session_plan"] = scheduled[0]["session_plan"]
    if not execute:
        return

    executed_items = _execute_scheduled_sessions(
        store,
        scheduled,
        model=model,
        reasoning_effort=reasoning_effort,
        model_profile=model_profile,
        codex_bin=codex_bin,
        sandbox=sandbox,
        timeout_sec=max(1, min(timeout_sec, 900)),
        executor=executor,
    )
    action_results = _apply_scheduled_results(
        store,
        executed_items,
        model=model,
        reasoning_effort=reasoning_effort,
        sandbox=sandbox,
    )
    entry["stop_writer_results"] = action_results


def _stop_writer_action(stop_action: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "mode": "write",
        "target_id": "root",
        "route_id": "",
        "reason": "workflow stopped before a solved final proof; write existing verified and partial proof material honestly",
        "budget": {
            "allowed": True,
            "requested_tokens": 0,
            "spendable_tokens": 0,
            "reason": "writer closure after workflow stop",
        },
        "write_existing_proofs_on_stop": True,
        "stop_reason": str(stop_action.get("reason") or "workflow stopped"),
        "terminal_classification": str(stop_action.get("terminal_classification") or "partial"),
        "search_intent": "stop_writer_closure",
    }


def _blocked_stop_writer_action(stop_action: Mapping[str, Any], blocker: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "mode": "write",
        "target_id": "root",
        "route_id": "",
        "reason": "writer closure suppressed because proof-critical work remains before an honest partial report",
        "budget": {
            "allowed": False,
            "requested_tokens": 0,
            "spendable_tokens": 0,
            "reason": "proof-critical work blocks stop writer",
        },
        "write_existing_proofs_on_stop": False,
        "writer_suppressed": True,
        "stop_reason": str(stop_action.get("reason") or "workflow stopped"),
        "terminal_classification": str(stop_action.get("terminal_classification") or "partial"),
        "blocker": dict(blocker),
        "search_intent": "stop_writer_blocked_by_proof_critical_work",
    }


def _stop_writer_safety_blocker(
    store: ProofStateStore,
    *,
    research_mode: str,
    web_search: str | None,
) -> Dict[str, Any]:
    try:
        state = store.get_scheduler_state()
    except Exception as exc:
        return {"reason": "could not inspect proof state before stop writer", "error": str(exc)}

    try:
        recommended = next_action(store, research_mode=research_mode, web_search=web_search)
    except Exception as exc:
        recommended = {"mode": "", "target_id": "root", "route_id": "", "reason": f"scheduler inspection failed: {exc}"}

    critical_reason = _proof_critical_action_reason(recommended)
    if critical_reason:
        return {
            "reason": critical_reason,
            "recommended_action": _summarize_stop_blocker_action(recommended),
            "proof_candidate_artifacts": _proof_artifact_summaries(state, candidates_only=True),
            "verifier_ready_routes": verifier_ready_route_summaries(state),
            "verifier_run_count": _verifier_run_count(state),
        }

    proof_candidates = _proof_artifact_summaries(state, candidates_only=True)
    if proof_candidates:
        return {
            "reason": "unrouted or unverified proof candidate exists; route conversion or strict verification must run before writer closure",
            "recommended_action": _summarize_stop_blocker_action(recommended),
            "proof_candidate_artifacts": proof_candidates,
            "verifier_ready_routes": verifier_ready_route_summaries(state),
            "verifier_run_count": _verifier_run_count(state),
        }

    proof_artifacts = _proof_artifact_summaries(state, candidates_only=False)
    route_count = len(state.get("routes", []))
    spent_tokens = _reported_token_total(state)
    if route_count == 0 and proof_artifacts and spent_tokens >= STOP_WRITER_NO_ROUTE_TOKEN_THRESHOLD:
        return {
            "reason": "substantial research produced proof dossiers but no proof routes; writer closure would hide verifier starvation",
            "recommended_action": _summarize_stop_blocker_action(recommended),
            "proof_artifacts": proof_artifacts[:8],
            "route_count": route_count,
            "reported_tokens": spent_tokens,
            "verifier_run_count": _verifier_run_count(state),
        }

    ready_routes = verifier_ready_route_summaries(state)
    if ready_routes and _verifier_run_count(state) == 0:
        return {
            "reason": "verifier-ready route evidence exists, but no strict verifier run is recorded",
            "recommended_action": _summarize_stop_blocker_action(recommended),
            "verifier_ready_routes": ready_routes,
            "verifier_run_count": 0,
        }

    return {}


def _proof_critical_action_reason(action: Mapping[str, Any]) -> str:
    mode = str(action.get("mode") or "")
    route_id = str(action.get("route_id") or "")
    intent = str(action.get("search_intent") or "")
    if intent in STOP_WRITER_PROOF_CRITICAL_INTENTS:
        return STOP_WRITER_PROOF_CRITICAL_INTENTS[intent]
    if mode == "prove" and route_id:
        return "scheduler selected strict verification of a proof route as the next mathematical action"
    if action.get("verify_ready_route_policy"):
        return "scheduler found verifier-ready proof evidence"
    return ""


def _summarize_stop_blocker_action(action: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "mode": str(action.get("mode") or ""),
        "target_id": str(action.get("target_id") or ""),
        "route_id": str(action.get("route_id") or ""),
        "search_intent": str(action.get("search_intent") or ""),
        "reason": str(action.get("reason") or ""),
    }


def _proof_artifact_summaries(state: Mapping[str, Any], *, candidates_only: bool) -> list[Dict[str, Any]]:
    summaries: list[Dict[str, Any]] = []
    for artifact in state.get("research_artifacts", []):
        artifact_type = str(artifact.get("artifact_type") or "")
        if artifact_type not in {"proof_dossier", "proof_blueprint"}:
            continue
        if candidates_only and not _artifact_looks_verifier_ready(artifact):
            continue
        summaries.append(
            {
                "artifact_id": str(artifact.get("artifact_id") or ""),
                "artifact_type": artifact_type,
                "state_revision": artifact.get("state_revision", ""),
                "summary": str(artifact.get("content_summary") or "")[:240],
            }
        )
    return summaries


def _artifact_looks_verifier_ready(artifact: Mapping[str, Any]) -> bool:
    if not _artifact_is_proof_candidate(artifact):
        return False
    metadata_text = str(artifact.get("metadata_json") or "").lower()
    text = " ".join(
        [
            str(artifact.get("artifact_type") or ""),
            str(artifact.get("producer_role") or ""),
            str(artifact.get("content_summary") or ""),
            metadata_text,
        ]
    ).lower()
    negative = (
        "not verifier-ready",
        "not verifier ready",
        "no verifier-ready",
        "not a proof candidate",
        "only a diagnostic",
    )
    if any(phrase in text for phrase in negative):
        return False
    positive = (
        "verifier-ready",
        "verifier ready",
        "ready_for_verifier",
        "proof_candidate",
        "proof candidate",
        "recommended_next_action",
        "selected_next_action",
        "verify",
    )
    return any(phrase in text for phrase in positive)


def _verifier_run_count(state: Mapping[str, Any]) -> int:
    return sum(
        1
        for row in state.get("recent_runs", [])
        if str(row.get("actor_role") or "") == "strict_informal_verifier"
        or (str(row.get("mode") or "") == "prove" and str(row.get("route_id") or ""))
    )


def _reported_token_total(state: Mapping[str, Any]) -> int:
    total = 0
    for row in state.get("recent_runs", []):
        try:
            total += int(row.get("total_tokens") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _execution_stop_action(
    action: Mapping[str, Any],
    status: str,
    result: Mapping[str, Any],
) -> Dict[str, Any]:
    mode = str(action.get("mode") or "unknown")
    target_id = str(action.get("target_id") or "root")
    reason = f"workflow stopped after {status} session for mode={mode}, target={target_id}"
    patch_errors = result.get("patch_outcome", {}).get("errors", []) if isinstance(result.get("patch_outcome"), Mapping) else []
    if patch_errors:
        reason = f"{reason}: {patch_errors[0]}"
    return {
        "mode": "stop_with_partial_results",
        "target_id": "root",
        "route_id": "",
        "reason": reason,
        "budget": dict(action.get("budget") or {}),
        "terminal_classification": "execution_stopped_partial",
    }


def _step_limit_action(steps: int) -> Dict[str, Any]:
    return {
        "mode": "stop_with_partial_results",
        "target_id": "root",
        "route_id": "",
        "reason": f"workflow step limit reached ({steps} steps)",
        "budget": {
            "allowed": False,
            "reason": "workflow step limit reached",
        },
        "terminal_classification": "step_limited_partial",
    }


def _prepare_scheduled_session(
    store: ProofStateStore,
    action: Mapping[str, Any],
    *,
    research_mode: str,
    web_search: str | None,
    max_context_chars: int,
    model_profile: str,
    is_companion: bool,
    resume_session_id: str = "",
    resume_since_revision: Optional[int] = None,
) -> Dict[str, Any]:
    session_web_search = search_policy_for_action(action, research_mode=research_mode, web_search=web_search)
    session_plan = prepare_session(
        store,
        action,
        max_context_chars=max_context_chars,
        model_profile=model_profile,
        resume_session_id=resume_session_id or None,
        resume_since_revision=resume_since_revision,
    )
    session_plan["web_search"] = session_web_search or ""
    session_plan["search_intent"] = research_intent_for_action(
        action,
        research_mode=research_mode,
        session_web_search=session_web_search,
    )
    return {
        "action": action,
        "session_plan": session_plan,
        "session_web_search": session_web_search,
        "is_companion": is_companion,
    }


def _execute_scheduled_sessions(
    store: ProofStateStore,
    scheduled: list[Dict[str, Any]],
    *,
    model: str,
    reasoning_effort: str,
    model_profile: str,
    codex_bin: str,
    sandbox: str,
    timeout_sec: int,
    executor: Optional[Executor],
    progress_callback: Optional[Callable[[Mapping[str, Any]], None]] = None,
    result_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancel_on_primary_failure: bool = True,
) -> list[Dict[str, Any]]:
    def _invoke_executor(executor: Executor, **kwargs: Any) -> Mapping[str, Any]:
        # Forward live progress/cancellation only to executors that accept them,
        # so custom backends can emit heartbeats during long in-flight steps.
        call_kwargs = {"store": kwargs["store"], "action": kwargs["action"], "session_plan": kwargs["session_plan"]}
        try:
            params = inspect.signature(executor).parameters
            accepts_var_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
            if accepts_var_kw or "progress_callback" in params:
                call_kwargs["progress_callback"] = kwargs.get("progress_callback")
            if accepts_var_kw or "stop_event" in params:
                call_kwargs["stop_event"] = kwargs.get("stop_event")
        except (TypeError, ValueError):
            pass
        return executor(**call_kwargs)

    stop_event = threading.Event()
    if executor is not None or len(scheduled) == 1:
        executed: list[Dict[str, Any]] = []
        try:
            for item in scheduled:
                item_progress = _progress_callback_for_item(progress_callback, item)
                if executor is not None:
                    _emit_synthetic_progress(item_progress, item, phase="started", status="running")
                    execution = dict(
                        _invoke_executor(
                            executor,
                            store=store,
                            action=item["action"],
                            session_plan=item["session_plan"],
                            progress_callback=item_progress,
                            stop_event=stop_event,
                        )
                    )
                    _emit_synthetic_progress(item_progress, item, phase="completed", status=str(execution.get("status") or "completed"), execution=execution)
                else:
                    execution = execute_session(
                        store,
                        item["action"],
                        item["session_plan"],
                        model=model,
                        reasoning_effort=reasoning_effort,
                        model_profile=model_profile,
                        codex_bin=codex_bin,
                        sandbox=sandbox,
                        web_search=item["session_web_search"],
                        timeout_sec=timeout_sec,
                        progress_callback=item_progress,
                        stop_event=stop_event,
                    )
                completed_item = {**item, "execution": execution}
                if result_callback is not None:
                    result_callback(completed_item)
                executed.append(completed_item)
        except BaseException:
            stop_event.set()
            raise
        return executed

    executed: list[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(scheduled)) as pool:
        futures = {
            pool.submit(
                execute_session,
                store,
                item["action"],
                item["session_plan"],
                model=model,
                reasoning_effort=reasoning_effort,
                model_profile=model_profile,
                codex_bin=codex_bin,
                sandbox=sandbox,
                web_search=item["session_web_search"],
                timeout_sec=timeout_sec,
                progress_callback=_progress_callback_for_item(progress_callback, item),
                stop_event=stop_event,
            ): item
            for item in scheduled
        }
        try:
            for future in as_completed(futures):
                item = futures[future]
                try:
                    execution = future.result()
                except CancelledError:
                    execution = _cancelled_execution_for_item(item)
                completed_item = {**item, "execution": execution}
                if result_callback is not None:
                    result_callback(completed_item)
                executed.append(completed_item)
                if cancel_on_primary_failure and _primary_failure_should_cancel_companions(item, execution):
                    stop_event.set()
                    for pending in futures:
                        if pending is not future:
                            pending.cancel()
        except BaseException:
            stop_event.set()
            for future in futures:
                future.cancel()
            raise
    executed.sort(key=lambda item: int(item["is_companion"]))
    return executed


def _write_partial_result_locked(store: ProofStateStore, history: list[Mapping[str, Any]]) -> None:
    """Keep a small always-current result summary on disk.

    The CLI prints its full result JSON only at process exit, so a killed run
    used to leave an empty stdout file; this sidecar preserves the step ledger.
    """
    try:
        entries = []
        for entry in history[-8:]:
            action = entry.get("action") if isinstance(entry.get("action"), Mapping) else {}
            entries.append(
                {
                    "step": entry.get("step"),
                    "mode": str(action.get("mode") or ""),
                    "target_id": str(action.get("target_id") or ""),
                    "researcher_work_mode": str(action.get("researcher_work_mode") or ""),
                    "execution_phase": str(entry.get("execution_phase") or ""),
                    "stop_reason": str(entry.get("stop_reason") or ""),
                }
            )
        payload = {
            "updated_at": utc_now(),
            "problem_id": store.problem_id,
            "revision": store.get_revision(),
            "steps_recorded": len(history),
            "recent_steps": entries,
        }
        path = store.state_dir / "attempt_result.partial.json"
        tmp_path = path.with_suffix(".partial.json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, path)
    except Exception:
        pass


# Backend-outage circuit breaker tuning: a failed session that used zero
# tokens never reached the model — whether it died instantly or spent minutes
# in provider reconnect loops before giving up (both patterns observed live
# 2026-07-04/05; the original 60s threshold missed the slow-death variant).
OUTAGE_INSTANT_FAILURE_WALL_SECONDS = 600.0
OUTAGE_BACKOFF_BASE_SECONDS = 60
OUTAGE_BACKOFF_MAX_SECONDS = 600
MAX_OUTAGE_STEP_REFUNDS = 48


def _looks_like_backend_outage(action_results: list[Mapping[str, Any]]) -> bool:
    """True when every session in the wave failed instantly with zero usage."""
    if not action_results:
        return False
    for row in action_results:
        if not isinstance(row, Mapping):
            return False
        status = str(row.get("status") or "")
        if status not in {"failed", "timeout", "no_patch"}:
            return False
        execution = row.get("execution") if isinstance(row.get("execution"), Mapping) else {}
        usage = execution.get("usage") if isinstance(execution.get("usage"), Mapping) else {}
        try:
            total_tokens = int(usage.get("total_tokens") or 0)
        except (TypeError, ValueError):
            total_tokens = 0
        try:
            wall = float(execution.get("wall_time_seconds") or 0.0)
        except (TypeError, ValueError):
            wall = 0.0
        if total_tokens > 0 or wall >= OUTAGE_INSTANT_FAILURE_WALL_SECONDS:
            return False
    return True


def _primary_failure_should_cancel_companions(item: Mapping[str, Any], execution: Mapping[str, Any]) -> bool:
    if item.get("is_companion"):
        return False
    return str(execution.get("status") or "") in {"failed", "timeout", "no_patch", "cancelled"}


def _cancelled_execution_for_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    action = item.get("action", {}) if isinstance(item.get("action"), Mapping) else {}
    session_plan = item.get("session_plan", {}) if isinstance(item.get("session_plan"), Mapping) else {}
    mode = str(action.get("mode") or "step")
    target_id = str(action.get("target_id") or "root")
    return {
        "run_id": f"cancelled-{mode}-{target_id}",
        "actor_role": str(session_plan.get("actor_role") or ""),
        "status": "cancelled",
        "returncode": -1,
        "wall_time_seconds": 0.0,
        "usage": {},
        "session_id": "",
        "patch": None,
        "patch_error": "cancelled before launch",
        "output_artifact_ids": [],
        "final_message_path": "",
        "log_path": "",
        "model": "",
        "reasoning_effort": "",
        "sandbox": "",
        "web_search": str(item.get("session_web_search") or ""),
    }


def _progress_callback_for_item(
    progress_callback: Optional[Callable[[Mapping[str, Any]], None]],
    item: Mapping[str, Any],
) -> Optional[Callable[[Mapping[str, Any]], None]]:
    if progress_callback is None:
        return None

    def update(progress: Mapping[str, Any]) -> None:
        payload = dict(progress)
        payload["is_companion"] = bool(item.get("is_companion"))
        progress_callback(payload)

    return update


def _emit_synthetic_progress(
    progress_callback: Optional[Callable[[Mapping[str, Any]], None]],
    item: Mapping[str, Any],
    *,
    phase: str,
    status: str,
    execution: Mapping[str, Any] | None = None,
) -> None:
    if progress_callback is None:
        return
    action = item.get("action", {}) if isinstance(item.get("action"), Mapping) else {}
    session_plan = item.get("session_plan", {}) if isinstance(item.get("session_plan"), Mapping) else {}
    execution = execution or {}
    progress_callback(
        {
            "run_id": execution.get("run_id") or f"pending-{session_plan.get('mode', action.get('mode', 'step'))}-{session_plan.get('target_id', action.get('target_id', 'root'))}",
            "actor_role": session_plan.get("actor_role", ""),
            "mode": action.get("mode", ""),
            "target_id": action.get("target_id", ""),
            "route_id": action.get("route_id", ""),
            "phase": phase,
            "status": status,
            "returncode": execution.get("returncode", ""),
            "elapsed_seconds": execution.get("wall_time_seconds", 0),
            "peak_memory_mb": execution.get("peak_memory_mb", 0),
            "updated_at": utc_now(),
            "context_path": session_plan.get("context_path", ""),
            "log_path": execution.get("log_path", ""),
            "final_message_path": execution.get("final_message_path", ""),
            "log_tail": "",
        }
    )


def _apply_scheduled_results(
    store: ProofStateStore,
    executed_items: list[Dict[str, Any]],
    *,
    model: str,
    reasoning_effort: str,
    sandbox: str,
) -> list[Dict[str, Any]]:
    results_by_id: dict[int, Dict[str, Any]] = {}
    for item in sorted(executed_items, key=_merge_priority):
        action = item["action"]
        session_plan = item["session_plan"]
        session_web_search = item["session_web_search"]
        execution = item["execution"]
        patch = execution.get("patch")
        patch_outcome = None
        boundary_errors = _evidence_boundary_errors(execution, session_plan)
        if boundary_errors:
            patch_outcome = {"accepted": False, "errors": boundary_errors}
            execution["patch_error"] = "\n".join(boundary_errors)
        elif isinstance(patch, Mapping):
            patch = _rebase_parallel_patch_if_safe(
                dict(patch),
                store.get_revision(),
                action=action,
                parallel_group=int(item.get("parallel_group_size", 1)) > 1,
            )
            patch_outcome = apply_patch_with_stale_retry(store, patch).to_dict()
            if patch_outcome.get("accepted"):
                _record_parallel_signals(store, patch, action=action, execution=execution)
        else:
            patch_outcome = {"accepted": False, "errors": [execution.get("patch_error") or "missing patch"]}

        status = str(execution.get("status") or "completed")
        if patch_outcome and not patch_outcome.get("accepted") and status not in {"failed", "timeout", "no_patch", "cancelled"}:
            status = "patch_rejected"
        metrics_outcome = _record_execution_metrics(
            store,
            action=action,
            session_plan=session_plan,
            execution=execution,
            status=status,
            model=model,
            reasoning_effort=reasoning_effort,
            sandbox=sandbox,
            web_search=session_web_search,
        )
        results_by_id[id(item)] = {
            "action": dict(action),
            "session_plan": dict(session_plan),
            "execution": _public_execution(execution),
            "patch_outcome": patch_outcome,
            "metrics_outcome": metrics_outcome,
            "status": status,
            "is_companion": item["is_companion"],
        }
    return [results_by_id[id(item)] for item in executed_items]


def _evidence_boundary_errors(execution: Mapping[str, Any], session_plan: Mapping[str, Any]) -> list[str]:
    """Reject child patches that visibly searched unlisted local evidence paths."""
    log_path_text = str(execution.get("log_path") or "")
    context_path_text = str(session_plan.get("context_path") or "")
    if not log_path_text or not context_path_text:
        return []
    try:
        context = json.loads(Path(context_path_text).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    allowed = _allowed_local_evidence_prefixes(context)
    violations: list[str] = []
    try:
        with Path(log_path_text).open("r", encoding="utf-8", errors="ignore") as handle:
            for line in _iter_shell_evidence_access_lines(handle):
                if _local_evidence_policy_text_line(line):
                    continue
                matches = list(DOWNLOAD_PATH_RE.findall(line)) + list(ARTIFACT_PATH_RE.findall(line))
                for match in matches:
                    path = match.rstrip(".,;:)]}")
                    if not path or "*" in path:
                        continue
                    if _local_evidence_path_allowed(path, allowed):
                        continue
                    if path not in violations:
                        violations.append(path)
                    if len(violations) >= 5:
                        break
                if len(violations) >= 5:
                    break
    except OSError:
        return []
    if not violations:
        return []
    return [
        "evidence boundary violation: child accessed unlisted local evidence path(s): "
        + ", ".join(violations)
    ]


def _iter_shell_evidence_access_lines(handle: Any) -> Iterator[str]:
    """Return Codex log lines from actual shell commands/output, not prompts."""
    in_exec_block = False
    pending_exec_command = False
    scan_exec_output = True
    for line in handle:
        stripped = line.strip()
        if stripped == "exec":
            in_exec_block = False
            pending_exec_command = True
            scan_exec_output = True
            continue
        if stripped == "codex" or stripped == "tokens used" or stripped.startswith("web search:"):
            in_exec_block = False
            pending_exec_command = False
            scan_exec_output = True
            continue
        if pending_exec_command:
            pending_exec_command = False
            in_exec_block = True
            scan_exec_output = not _shell_command_reads_context_manifest(stripped)
            yield line
            continue
        if in_exec_block:
            if not scan_exec_output:
                continue
            yield line


def _shell_command_reads_context_manifest(command_line: str) -> bool:
    return "context.json" in command_line


def _local_evidence_policy_text_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith('"download_scope_rule":') or stripped.startswith('"local_shell_rule":')


def _allowed_local_evidence_prefixes(context: Mapping[str, Any]) -> list[str]:
    policy = context.get("local_search_policy")
    raw_paths: list[Any] = []
    if isinstance(policy, Mapping):
        raw_paths.extend(policy.get("allowed_local_evidence_paths") or [])
        raw_paths.extend(policy.get("allowed_cas_assets") or [])
    cas_tooling = context.get("cas_tooling")
    if isinstance(cas_tooling, Mapping):
        for asset in cas_tooling.get("assets", []) or []:
            if isinstance(asset, Mapping):
                raw_paths.append(asset.get("path"))
    prefixes: list[str] = []
    seen: set[str] = set()
    for raw in raw_paths:
        text = str(raw or "").strip().rstrip("/")
        if not text or "*" in text:
            continue
        for prefix in _local_evidence_prefix_variants(text):
            if prefix not in seen:
                seen.add(prefix)
                prefixes.append(prefix)
    return prefixes


def _local_evidence_prefix_variants(path: str) -> list[str]:
    variants = [path]
    marker = "agents/generation/"
    if marker in path:
        variants.append(path[path.find(marker):])
    return variants


def _local_evidence_path_allowed(path: str, allowed_prefixes: list[str]) -> bool:
    normalized = path.strip().rstrip("/")
    return any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in allowed_prefixes)


def _blocked_by_pending_priority_barrier(
    completed_item: Mapping[str, Any],
    pending_items: Any,
) -> bool:
    """Delay lower-priority live application behind proof-critical barriers."""
    completed_priority = _merge_priority(completed_item)
    for pending in pending_items:
        if _merge_priority(pending) >= completed_priority:
            continue
        role = str(pending.get("session_plan", {}).get("actor_role") or "")
        if role in {"strict_informal_verifier", "integration_verifier", "writer"}:
            return True
        if completed_item.get("is_companion") and not pending.get("is_companion"):
            if _safe_advisor_companion_can_land_before_primary(completed_item):
                continue
            return True
    return False


def _safe_advisor_companion_can_land_before_primary(item: Mapping[str, Any]) -> bool:
    """Allow compact advisor triage to unblock a stalled parallel wave."""
    role = str(item.get("session_plan", {}).get("actor_role") or "")
    if role != "phd_advisor":
        return False
    execution = item.get("execution") if isinstance(item.get("execution"), Mapping) else {}
    patch = execution.get("patch") if isinstance(execution, Mapping) else None
    if not isinstance(patch, Mapping):
        return False
    if str(patch.get("actor_role") or role) != "phd_advisor":
        return False
    action = item.get("action") if isinstance(item.get("action"), Mapping) else {}
    return _safe_advisor_patch(patch.get("operations"), action)


def _record_parallel_signals(
    store: ProofStateStore,
    patch: Mapping[str, Any],
    *,
    action: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> None:
    signals = patch.get("parallel_signals")
    if not isinstance(signals, list) or not signals:
        return
    path = store.state_dir / "parallel_exchange.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    actor_role = str(patch.get("actor_role") or execution.get("actor_role") or "")
    mode = str(action.get("mode") or "")
    target_id = str(action.get("target_id") or patch.get("target_id") or "root")
    run_id = str(execution.get("run_id") or "")
    invalid_run_ids = {str(getattr(store, "problem_id", "") or ""), str(patch.get("problem_id") or "")}
    existing_keys = _existing_parallel_signal_keys(path)
    lines: list[str] = []
    for raw_signal in signals[:20]:
        if not isinstance(raw_signal, Mapping):
            continue
        payload = {
            "created_at": str(raw_signal.get("created_at") or utc_now()),
            "run_id": _signal_field(raw_signal.get("run_id"), fallback=run_id, invalid_values=invalid_run_ids),
            "actor_role": str(raw_signal.get("actor_role") or actor_role),
            "mode": str(raw_signal.get("mode") or mode),
            "signal_type": str(raw_signal.get("signal_type") or "route_update"),
            "target_id": str(raw_signal.get("target_id") or target_id),
            "relation": str(raw_signal.get("relation") or "needs_verifier"),
            "summary": _clip_signal_text(raw_signal.get("summary"), 800),
            "evidence": _clip_signal_text(raw_signal.get("evidence"), 500),
            "confidence": str(raw_signal.get("confidence") or "medium"),
        }
        key = _parallel_signal_dedupe_key(payload)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if not lines:
        return
    try:
        with path.open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
    except OSError:
        return


def _existing_parallel_signal_keys(path: Any) -> set[tuple[str, ...]]:
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return set()
    keys: set[tuple[str, ...]] = set()
    for line in raw_lines[-200:]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            keys.add(_parallel_signal_dedupe_key(payload))
    return keys


def _parallel_signal_dedupe_key(payload: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(payload.get("actor_role") or ""),
        str(payload.get("mode") or ""),
        str(payload.get("signal_type") or ""),
        str(payload.get("target_id") or ""),
        str(payload.get("relation") or ""),
        str(payload.get("summary") or ""),
        str(payload.get("evidence") or ""),
        str(payload.get("confidence") or ""),
    )


def _signal_field(value: Any, *, fallback: str, invalid_values: set[str] | None = None) -> str:
    text = str(value or "").strip()
    invalid = {str(item).strip().lower() for item in (invalid_values or set()) if str(item).strip()}
    if text.lower() in {"", "unknown", "n/a", "none", "null"} or text.lower() in invalid:
        return fallback
    return text


def _clip_signal_text(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 24)].rstrip() + " ... [truncated]"


def _merge_priority(item: Mapping[str, Any]) -> tuple[int, int, int]:
    role = str(item.get("session_plan", {}).get("actor_role") or "")
    priority = {
        "strict_informal_verifier": 0,
        "integration_verifier": 1,
        "writer": 2,
        "literature_researcher": 10,
    }.get(role, 5)
    action = item.get("action", {}) if isinstance(item.get("action"), Mapping) else {}
    intent = str(action.get("search_intent") or item.get("session_plan", {}).get("search_intent") or "")
    intent_priority = {
        "parallel_direct_solve": 0,
        "parallel_independent_solve": 0,
        "parallel_decomposition_branch": 1,
        "parallel_counterexample_search": 4,
    }.get(intent, 2)
    return (priority, intent_priority, int(item.get("is_companion", False)))


def _rebase_parallel_patch_if_safe(
    patch: Dict[str, Any],
    current_revision: int,
    *,
    action: Mapping[str, Any],
    parallel_group: bool = False,
) -> Dict[str, Any]:
    patch = _normalize_patch_aliases(patch)
    if int(patch.get("base_revision", current_revision)) == current_revision:
        return patch
    actor = patch.get("actor_role")
    operations = patch.get("operations", [])
    if actor == "literature_researcher" and _safe_literature_patch(operations, action):
        return _rebased_patch_with_current_revision(patch, current_revision)
    if actor == "phd_advisor" and _safe_advisor_patch(operations, action):
        return _rebased_patch_with_current_revision(patch, current_revision)
    if _safe_decomposition_branch_patch(actor, operations, action):
        return _rebased_patch_with_current_revision(patch, current_revision)
    if _safe_additive_parallel_research_patch(actor, operations, action, parallel_group=parallel_group):
        return _rebased_patch_with_current_revision(patch, current_revision)
    return patch


def _rebased_patch_with_current_revision(patch: Dict[str, Any], current_revision: int) -> Dict[str, Any]:
    rebased = dict(patch)
    rebased["base_revision"] = current_revision
    rebased_operations = []
    for op in rebased.get("operations", []):
        if isinstance(op, dict):
            copied = dict(op)
            if copied.get("op") == "attach_artifact":
                copied["state_revision"] = current_revision
            rebased_operations.append(copied)
        else:
            rebased_operations.append(op)
    rebased["operations"] = rebased_operations
    return rebased


def _safe_literature_patch(operations: Any, action: Mapping[str, Any]) -> bool:
    if not isinstance(operations, list):
        return False
    target_id = str(action.get("target_id") or "root")
    allowed_ops = {"cache_retrieval_card", "attach_artifact", "add_debt"}
    for op in operations:
        if not isinstance(op, Mapping) or op.get("op") not in allowed_ops:
            return False
        if op.get("op") != "add_debt":
            continue
        owner_id = str(op.get("owner_id") or "")
        suggested = str(op.get("suggested_next_target") or "")
        if owner_id and owner_id != target_id:
            return False
        if suggested and suggested != target_id:
            return False
        if str(op.get("status") or "active") != "active":
            return False
    return True


def _safe_advisor_patch(operations: Any, action: Mapping[str, Any]) -> bool:
    if not isinstance(operations, list):
        return False
    target_id = str(action.get("target_id") or "root")
    route_id = str(action.get("route_id") or "")
    allowed_owner_refs = {target_id}
    if route_id:
        allowed_owner_refs.add(route_id)
    allowed_ops = {"attach_artifact", "add_debt"}
    for op in operations:
        if not isinstance(op, Mapping) or op.get("op") not in allowed_ops:
            return False
        if op.get("op") != "add_debt":
            continue
        owner_id = str(op.get("owner_id") or "")
        suggested = str(op.get("suggested_next_target") or "")
        if owner_id and owner_id not in allowed_owner_refs:
            return False
        if suggested and suggested not in allowed_owner_refs:
            return False
        if str(op.get("status") or "active") != "active":
            return False
    return True


def _safe_additive_parallel_research_patch(
    actor: Any,
    operations: Any,
    action: Mapping[str, Any],
    *,
    parallel_group: bool = False,
) -> bool:
    if actor not in {"researcher", "villain"}:
        return False
    if (
        not parallel_group
        and not action.get("parallel_companion")
        and not str(action.get("search_intent") or "").startswith("parallel_")
    ):
        return False
    if not isinstance(operations, list):
        return False
    target_id = str(action.get("target_id") or "")
    action_route_id = str(action.get("route_id") or "")
    if not target_id:
        return False

    allowed_ops = {
        "attach_artifact",
        "add_artifact",
        "add_claim",
        "add_route",
        "add_inference",
        "add_debt",
        "update_route",
        "propose_status_transition",
    }
    created_artifact_ids = {
        str(op.get("artifact_id") or "")
        for op in operations
        if isinstance(op, Mapping) and op.get("op") in {"attach_artifact", "add_artifact"}
    }
    created_claim_ids = {
        str(op.get("claim_id") or "")
        for op in operations
        if isinstance(op, Mapping) and op.get("op") == "add_claim"
    }
    created_route_ids = {
        str(op.get("route_id") or "")
        for op in operations
        if isinstance(op, Mapping) and op.get("op") == "add_route"
    }
    created_artifact_ids.discard("")
    created_claim_ids.discard("")
    created_route_ids.discard("")
    if "root" in created_claim_ids:
        return False

    allowed_route_refs = {*created_route_ids}
    if action_route_id:
        allowed_route_refs.add(action_route_id)
    allowed_claim_refs = {target_id, *created_claim_ids}
    if parallel_group and str(action.get("search_intent") or "") in {
        "proof_candidate_route_conversion",
        "route_proof_construction",
    }:
        for op in operations:
            if not isinstance(op, Mapping) or str(op.get("op") or "") != "add_inference":
                continue
            route_id = str(op.get("route_id") or "")
            conclusion_id = str(op.get("conclusion_claim_id") or "")
            validation_status = str(op.get("validation_status") or "untested")
            if (
                route_id
                and route_id.startswith(("route_", "route-"))
                and conclusion_id in allowed_claim_refs
                and validation_status not in {"informally_verified", "formally_verified", "refuted"}
            ):
                allowed_route_refs.add(route_id)
    allowed_owner_refs = {target_id, *created_claim_ids, *allowed_route_refs}
    for op in operations:
        if not isinstance(op, Mapping) or op.get("op") not in allowed_ops:
            return False
        kind = str(op.get("op") or "")
        if kind in {"attach_artifact", "add_artifact"}:
            continue
        if kind == "add_claim":
            claim_id = str(op.get("claim_id") or "")
            if not claim_id or claim_id == "root":
                return False
            if str(op.get("validation_status") or "untested") in {"informally_verified", "formally_verified", "refuted"}:
                return False
            parent_ids = {str(item or "") for item in op.get("parent_ids", []) if str(item or "")}
            if not parent_ids.issubset(allowed_claim_refs):
                return False
        elif kind == "add_route":
            route_id = str(op.get("route_id") or "")
            conclusion_id = str(op.get("conclusion_claim_id") or "")
            if not route_id or conclusion_id not in allowed_claim_refs:
                return False
        elif kind == "add_inference":
            route_id = str(op.get("route_id") or "")
            conclusion_id = str(op.get("conclusion_claim_id") or "")
            premise_ids = op.get("premise_claim_ids", [])
            if not isinstance(premise_ids, list):
                return False
            if route_id not in allowed_route_refs or conclusion_id not in allowed_claim_refs:
                return False
            if any(str(premise_id or "") not in allowed_claim_refs for premise_id in premise_ids):
                return False
            if str(op.get("validation_status") or "untested") in {"informally_verified", "formally_verified", "refuted"}:
                return False
        elif kind == "add_debt":
            owner_id = str(op.get("owner_id") or "")
            suggested = str(op.get("suggested_next_target") or "")
            root_local_existing_owner = (
                parallel_group
                and target_id == "root"
                and suggested in {"", "root"}
                and (owner_id.startswith("claim_root_") or owner_id.startswith("route_root_"))
            )
            if owner_id and owner_id not in allowed_owner_refs and not root_local_existing_owner:
                return False
            root_handoff = (
                parallel_group
                and target_id != "root"
                and suggested == "root"
                and owner_id in allowed_owner_refs
            )
            if suggested and suggested not in allowed_claim_refs and not root_handoff:
                return False
            if str(op.get("status") or "active") != "active":
                return False
        elif kind == "update_route":
            route_id = str(op.get("route_id") or "")
            if not action_route_id or route_id != action_route_id:
                return False
            if str(op.get("status") or "active") == "integrated":
                return False
        elif kind == "propose_status_transition":
            if str(op.get("target_type") or "claim") != "claim":
                return False
            if str(op.get("status_type") or "validation") != "validation":
                return False
            if str(op.get("new_status") or "") != "challenged":
                return False
            if str(op.get("target_id") or "") not in allowed_claim_refs:
                return False
            evidence_ids = {str(item or "") for item in op.get("evidence_artifact_ids", []) if str(item or "")}
            if not evidence_ids or not evidence_ids.issubset(created_artifact_ids):
                return False
    return True


def _safe_decomposition_branch_patch(actor: Any, operations: Any, action: Mapping[str, Any]) -> bool:
    if actor not in {"researcher", "villain", "strict_informal_verifier"}:
        return False
    if not action.get("decomposition_step_required"):
        return False
    target_id = str(action.get("target_id") or "")
    parent_id = str(action.get("decomposition_parent_id") or "")
    route_id = str(action.get("route_id") or "")
    if not target_id or target_id == parent_id:
        return False
    if not isinstance(operations, list):
        return False
    created_claim_ids: set[str] = set()
    created_route_ids: set[str] = set()
    allowed_ops = {
        "attach_artifact",
        "add_claim",
        "add_route",
        "add_inference",
        "add_debt",
        "update_debt",
        "propose_status_transition",
    }
    for op in operations:
        if not isinstance(op, Mapping) or op.get("op") not in allowed_ops:
            return False
        kind = str(op.get("op") or "")
        if kind == "add_claim":
            claim_id = str(op.get("claim_id") or "")
            parent_ids = {str(item or "") for item in op.get("parent_ids", []) if str(item or "")}
            if target_id not in {claim_id, *parent_ids}:
                return False
            created_claim_ids.add(claim_id)
        elif kind == "add_route":
            current_route_id = str(op.get("route_id") or "")
            conclusion_id = str(op.get("conclusion_claim_id") or "")
            if conclusion_id not in {target_id, *created_claim_ids}:
                return False
            created_route_ids.add(current_route_id)
        elif kind == "add_inference":
            conclusion_id = str(op.get("conclusion_claim_id") or "")
            current_route_id = str(op.get("route_id") or "")
            if conclusion_id not in {target_id, *created_claim_ids}:
                return False
            if route_id and current_route_id not in {route_id, *created_route_ids}:
                return False
        elif kind in {"add_debt", "update_debt"}:
            owner_id = str(op.get("owner_id") or "")
            suggested = str(op.get("suggested_next_target") or "")
            if owner_id and owner_id not in {target_id, route_id, *created_claim_ids, *created_route_ids}:
                return False
            if suggested and suggested not in {target_id, *created_claim_ids}:
                return False
        elif kind == "propose_status_transition":
            target_type = str(op.get("target_type") or "")
            transition_target = str(op.get("target_id") or "")
            if target_type == "claim" and transition_target not in {target_id, *created_claim_ids}:
                return False
            if target_type == "inference" and actor != "strict_informal_verifier":
                return False
    return True


def _remaining_wall_seconds(started: float, max_wall_seconds: int | None) -> float | None:
    if max_wall_seconds is None:
        return None
    if max_wall_seconds <= 0:
        return 0.0
    return float(max_wall_seconds) - (time.monotonic() - started)


def _wall_limit_action(max_wall_seconds: int | None) -> Dict[str, Any]:
    return {
        "mode": "stop_with_partial_results",
        "target_id": "root",
        "route_id": "",
        "reason": f"workflow wall time limit reached ({max_wall_seconds} seconds)",
        "budget": {
            "allowed": False,
            "reason": "workflow wall time limit reached",
        },
        "terminal_classification": "time_limited_partial",
    }


def _record_execution_metrics(
    store: ProofStateStore,
    *,
    action: Mapping[str, Any],
    session_plan: Mapping[str, Any],
    execution: Mapping[str, Any],
    status: str,
    model: str,
    reasoning_effort: str,
    sandbox: str,
    web_search: str | None = None,
) -> Dict[str, Any]:
    usage = execution.get("usage") if isinstance(execution.get("usage"), Mapping) else {}
    op = run_metrics_operation(
        run_id=str(execution.get("run_id") or f"run-{store.get_revision()}"),
        action=action,
        session_plan={**dict(session_plan), "session_id": execution.get("session_id", "")},
        usage_payload=usage,
        status=status,
        wall_time_seconds=float(execution.get("wall_time_seconds") or 0.0),
        peak_memory_mb=float(execution.get("peak_memory_mb") or 0.0),
        model=str(execution.get("model") or model),
    )
    op["reasoning_effort"] = str(execution.get("reasoning_effort") or reasoning_effort)
    op["search_setting"] = str(execution.get("web_search") or web_search or "disabled")
    op["search_intent"] = str(session_plan.get("search_intent") or "")
    op["sandbox_setting"] = str(execution.get("sandbox") or sandbox)
    op["failure_kind"] = str(execution.get("failure_kind") or "")
    output_ids = execution.get("output_artifact_ids")
    if not output_ids and isinstance(execution.get("patch"), Mapping):
        output_ids = attached_artifact_ids(execution.get("patch"))
    op["output_artifact_ids"] = list(output_ids or [])
    operations: list[Dict[str, Any]] = []
    failure_artifact = _session_failure_artifact_operation(action=action, execution=execution, status=status)
    if failure_artifact is not None:
        op["error_artifact_id"] = failure_artifact["artifact_id"]
        operations.append(failure_artifact)
    operations.append(op)
    patch = {
        "schema_version": 1,
        "problem_id": store.problem_id,
        "base_revision": store.get_revision(),
        "actor_role": "scheduler",
        "target_id": str(action.get("target_id") or "root"),
        "operations": operations,
        "rationale": "record Albilich v1 workflow session metrics",
    }
    outcome = apply_patch(store, patch).to_dict()
    outcome["web_search"] = op["search_setting"]
    outcome["search_intent"] = op["search_intent"]
    return outcome


def _session_failure_artifact_operation(
    *,
    action: Mapping[str, Any],
    execution: Mapping[str, Any],
    status: str,
) -> Optional[Dict[str, Any]]:
    patch_error = str(execution.get("patch_error") or "").strip()
    if not patch_error:
        return None
    run_id = str(execution.get("run_id") or "run")
    artifact_id = f"session_failure_{_safe_artifact_suffix(run_id)}"
    mode = str(action.get("mode") or "")
    target_id = str(action.get("target_id") or "")
    route_id = str(action.get("route_id") or "")
    content = "\n".join(
        [
            "# Session Failure Report",
            "",
            f"- run_id: `{run_id}`",
            f"- actor_role: `{execution.get('actor_role', '')}`",
            f"- mode: `{mode}`",
            f"- target_id: `{target_id}`",
            f"- route_id: `{route_id}`",
            f"- status: `{status}`",
            f"- returncode: `{execution.get('returncode', '')}`",
            f"- wall_time_seconds: `{execution.get('wall_time_seconds', '')}`",
            f"- log_path: `{execution.get('log_path', '')}`",
            f"- final_message_path: `{execution.get('final_message_path', '')}`",
            "",
            "## Failure",
            "",
            patch_error,
            "",
        ]
    )
    return {
        "op": "attach_artifact",
        "artifact_id": artifact_id,
        "artifact_type": "session_failure_report",
        "content": content,
        "content_summary": patch_error[:240],
        "metadata": {
            "run_id": run_id,
            "actor_role": str(execution.get("actor_role") or ""),
            "mode": mode,
            "target_id": target_id,
            "route_id": route_id,
            "status": status,
            "returncode": execution.get("returncode", ""),
            "log_path": str(execution.get("log_path") or ""),
            "final_message_path": str(execution.get("final_message_path") or ""),
        },
    }


def _safe_artifact_suffix(text: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text).strip("._-")
    return (safe or "run")[:160]


def _public_execution(execution: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "run_id": execution.get("run_id", ""),
        "actor_role": execution.get("actor_role", ""),
        "status": execution.get("status", ""),
        "returncode": execution.get("returncode", 0),
        "wall_time_seconds": execution.get("wall_time_seconds", 0.0),
        "peak_memory_mb": execution.get("peak_memory_mb", 0.0),
        "usage": execution.get("usage", {}),
        "session_id": execution.get("session_id", ""),
        "patch_error": execution.get("patch_error", ""),
        "output_artifact_ids": execution.get("output_artifact_ids", []),
        "final_message_path": execution.get("final_message_path", ""),
        "log_path": execution.get("log_path", ""),
        "web_search": execution.get("web_search", ""),
        "preflight_repair": execution.get("preflight_repair", {}),
        "failure_kind": execution.get("failure_kind", ""),
    }
