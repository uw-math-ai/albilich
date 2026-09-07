from __future__ import annotations

import hashlib
import inspect
import fcntl
import json
import os
import re
import stat
import time
import threading
import uuid
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping, Optional, Sequence

from .action_contract import (
    scheduler_action_contract_trace_errors,
    scheduler_dispatch_action_errors,
)
from .authority import session_authority
from .audit_chain import GENESIS_HASH, POLICY_EVENT_TYPES
from .bounded_io import read_bounded_text, stable_file_sha256_size
from .context_builder import manifest_hash
from .decision_policy import action_sha256
from .dispatch_execution import (
    CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY,
    CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE,
    CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
    CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE,
    canonical_dispatch_json,
    durable_path_source_identity_errors,
    dispatch_json_sha256,
    dispatch_result_sha256,
    execution_resource_result_errors,
)
from .codex_runner import (
    AggregateProcessTreeRSSGovernor,
    DEFAULT_CHILD_TIMEOUT_SECONDS,
    DEFAULT_CODEX_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_SANDBOX,
    actor_role_for_action,
    attached_artifact_ids,
    execute_session,
    prepare_session,
    resolve_codex_executable,
    run_metrics_operation,
    session_cas_enabled,
    aggregate_child_max_process_tree_rss_mb,
)
from .executable_attestation import attest_executable_identity
from .scheduler_provenance import append_scheduler_provenance_entry

# Same-role session resume: keep the same agent alive across consecutive same-role,
# same-target primary steps (so it does not re-read artifacts each step), then
# cold-start to reset the context window after this many resumes.
MAX_RESUME_CHAIN = 4
from .console import write_run_console
from .metrics import compute_metrics
from .models import SCHEMA_VERSION, utc_now
from .patches import (
    MAX_COPIED_ARTIFACT_BYTES,
    WRITER_PATH_ATTACH_ARTIFACT_TYPES,
    WRITER_PATH_ATTACH_MAX_BYTES,
    PatchRejected,
    _normalize_patch_aliases,
    _run_provenance_hash,
    _validated_artifact_path,
    apply_patch_with_stale_retry,
    apply_system_patch,
    preflight_patch_errors,
)
from .parallel_exchange import append_parallel_signal_batch
from .parallel_admission import PARALLEL_WAVE_ADMISSION_POLICY_VERSION
from .randomized_assignment import (
    BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION,
    WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS,
    bind_randomized_assignment,
    randomized_assignment_metadata,
    workflow_assignment_from_certificate,
)
from .report import write_markdown_report
from .result_status import classify_result
from .research_policy import (
    DEFAULT_RESEARCH_MODE,
    DEFAULT_WEB_SEARCH,
    normalize_research_mode,
    research_intent_for_action,
    search_policy_for_action,
)
from .research_intelligence import action_patch_contract_errors
from .research_strategy import approach_portfolio_view
from .branch_summary import sync_branch_workbenches
from .hmt_sidecar import periodic_hmt_sidecar_action, publish_hmt_sidecar
from .scheduler import (
    DEFAULT_MULTI_BRANCH_WORKERS,
    _admit_and_finalize_parallel_companions,
    _artifact_is_proof_candidate,
    _bind_primary_parallel_wave_decision,
    _select_parallel_wave_leader,
    multi_branch_research_actions,
    next_action,
    normalize_parallel_branches,
    parallel_companion_actions,
    verifier_ready_route_summaries,
)
from .scheduler_registry import (
    PARALLEL_COMPANION_GENERATOR_IDS,
    mark_candidate_generators_skipped,
    new_parallel_generator_evaluation,
)
from .store import ProofStateStore, ValidatedCommitSuperseded
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
CONSOLE_REFRESH_INTERVAL_ENV = "ALBILICH_CONSOLE_REFRESH_INTERVAL_SECONDS"
DEFAULT_CONSOLE_REFRESH_INTERVAL_SECONDS = 15.0
MAX_SESSION_CONTEXT_FILE_BYTES = 16 * 1024 * 1024
MAX_DISPATCH_RESULT_RECORD_BYTES = 20 * 1024 * 1024

Executor = Callable[..., Mapping[str, Any]]
TERMINAL_MODES = {"await_human", "stop_with_partial_results", "stop_solved"}
CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE = "albilich_dispatch_recovery"
CUSTOM_EXECUTOR_RECOVERY_CAPABILITY = "idempotent_by_scheduler_dispatch_id"
CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE = "albilich_executor_identity"
# Run-control: persisted pause/stop states honored between
# action dispatches; the watcher polls for hard stops during child sessions.
RUN_CONTROL_POLL_SECONDS = 2.0
RUN_CONTROL_BLOCKING_STATUSES = {"pause_requested", "paused", "stopping", "stopped"}


class _ConsoleWriteThrottle:
    """Bound expensive full-state console rebuilds during live heartbeats."""

    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = max(0.0, float(interval_seconds))
        self.last_write_at: float | None = None

    def should_write(self, *, force: bool = False, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        if (
            force
            or self.last_write_at is None
            or current - self.last_write_at >= self.interval_seconds
        ):
            self.last_write_at = current
            return True
        return False


class _StaleSchedulerDispatch(RuntimeError):
    """The authenticated planning snapshot changed before dispatch commit."""


class _WorkflowAlreadyExecuting(RuntimeError):
    """Another orchestrator owns this proof store's execution lock."""


class _WorkflowExecutionLock:
    """Non-inheritable process lock for one executing orchestrator per store."""

    def __init__(self, store: ProofStateStore) -> None:
        self.path = store.state_dir / "workflow_execution.lock"
        self.fd: int | None = None

    def __enter__(self) -> "_WorkflowExecutionLock":
        flags = os.O_CREAT | os.O_RDWR
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.path, flags, 0o600)
        except OSError as exc:
            raise RuntimeError(
                f"cannot open workflow execution lock {self.path}: {exc}"
            ) from exc
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise RuntimeError(
                    "workflow execution lock must be a regular, singly linked file"
                )
            if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
                raise RuntimeError(
                    "workflow execution lock must be owned by the current user "
                    "and inaccessible to group/other users"
                )
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise _WorkflowAlreadyExecuting(
                    "another executing workflow already owns this proof store"
                ) from exc
        except BaseException:  # intentional-boundary: close the security-sensitive lock fd on every failed acquisition path
            os.close(fd)
            raise
        self.fd = fd
        return self

    def __exit__(self, *_exc: Any) -> None:
        fd = self.fd
        self.fd = None
        if fd is None:
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _exclusive_workflow_execution(
    func: Callable[..., Dict[str, Any]],
) -> Callable[..., Dict[str, Any]]:
    """Serialize execute=True workflows without affecting read-only plans."""

    @wraps(func)
    def wrapped(store: ProofStateStore, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        if not bool(kwargs.get("execute", False)):
            return func(store, *args, **kwargs)
        with _WorkflowExecutionLock(store):
            return func(store, *args, **kwargs)

    return wrapped


def _console_refresh_interval_seconds() -> float:
    raw = os.environ.get(CONSOLE_REFRESH_INTERVAL_ENV, "").strip()
    if not raw:
        return DEFAULT_CONSOLE_REFRESH_INTERVAL_SECONDS
    try:
        return max(1.0, float(raw))
    except ValueError:
        return DEFAULT_CONSOLE_REFRESH_INTERVAL_SECONDS
DOWNLOAD_PATH_RE = re.compile(r"(?:/[^\s\"'<>]*agents/generation/downloads(?:/[^\s\"'<>]+)?|agents/generation/downloads(?:/[^\s\"'<>]+)?)")
ARTIFACT_PATH_RE = re.compile(
    r"(?:/[^\s\"'<>]*agents/generation/results/[^\s\"'<>]+/phase2/artifacts/[^\s\"'<>]+|"
    r"agents/generation/results/[^\s\"'<>]+/phase2/artifacts/[^\s\"'<>]+)"
)


def _persist_abnormal_workflow_exit(func: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
    """Ensure an executing workflow never leaves a stale ``running`` state.

    Normal scheduler exits are finalized inside ``run_workflow``.  This wrapper
    covers exceptions and process signals converted to Python exceptions by the
    CLI, after the child runner has terminated any in-flight Codex process.
    """

    @wraps(func)
    def wrapped(store: ProofStateStore, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        execute = bool(kwargs.get("execute", False))
        try:
            return func(store, *args, **kwargs)
        except BaseException as exc:  # intentional-boundary: persist terminal state before propagating signals/errors
            if execute:
                _record_abnormal_workflow_exit(store, exc)
            raise

    return wrapped


def _latest_workflow_randomized_assignment(
    store: ProofStateStore,
) -> dict[str, Any] | None:
    """Recover a durable workflow assignment from the latest primary wave."""

    with store.connect() as conn:
        row = conn.execute(
            "SELECT d.decision_trace_json FROM scheduler_source_entries AS s "
            "JOIN scheduler_dispatches AS d ON d.dispatch_id = s.record_id "
            "WHERE s.record_kind = 'dispatch' AND d.dispatch_position = 0 "
            "ORDER BY s.sequence DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    try:
        trace = json.loads(str(row["decision_trace_json"] or ""))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "latest scheduler dispatch has malformed decision provenance"
        ) from exc
    certificate = (
        trace.get("randomized_assignment")
        if isinstance(trace, Mapping)
        else None
    )
    if (
        not isinstance(certificate, Mapping)
        or certificate.get("protocol_version")
        not in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
    ):
        return None
    try:
        return workflow_assignment_from_certificate(certificate)
    except ValueError as exc:
        raise RuntimeError(
            f"latest workflow randomized assignment is invalid: {exc}"
        ) from exc


def _next_workflow_assignment_exposure_index(
    store: ProofStateStore,
    assignment: Mapping[str, Any],
) -> int:
    """Return the next indexed exposure for one immutable workflow assignment."""

    experiment_id = str(assignment.get("experiment_id") or "")
    assignment_unit_id = str(assignment.get("assignment_unit_id") or "")
    with store.connect() as conn:
        row = conn.execute(
            "SELECT decision_trace_json FROM scheduler_dispatches "
            "WHERE selection_design = 'randomized' AND dispatch_position = 0 "
            "AND json_extract(decision_trace_json, "
            "'$.randomized_assignment.experiment_id') = ? "
            "AND json_extract(decision_trace_json, "
            "'$.randomized_assignment.assignment_unit_id') = ? "
            "ORDER BY COALESCE(json_extract(decision_trace_json, "
            "'$.randomized_assignment.exposure_index'), -1) DESC LIMIT 1",
            (experiment_id, assignment_unit_id),
        ).fetchone()
    if row is None:
        return 0
    try:
        trace = json.loads(str(row["decision_trace_json"] or ""))
        certificate = trace.get("randomized_assignment")
        persisted_assignment = workflow_assignment_from_certificate(certificate)
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "prior workflow randomized exposure has invalid provenance"
        ) from exc
    if (
        persisted_assignment.get("assignment_input_sha256")
        != assignment.get("assignment_input_sha256")
    ):
        raise ValueError(
            "workflow randomized assignment changes within the experimental unit"
        )
    exposure_index = certificate.get("exposure_index")
    if type(exposure_index) is not int or exposure_index < 0:
        raise RuntimeError(
            "prior workflow randomized exposure has an invalid index"
        )
    return exposure_index + 1


@_exclusive_workflow_execution
@_persist_abnormal_workflow_exit
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
    parallel_branches: int = DEFAULT_MULTI_BRANCH_WORKERS,
    stop_on_rejection: bool = True,
    write_on_stop: bool = True,
    write_report: bool = False,
    write_console: bool = True,
    session_resume: bool = True,
    executor: Optional[Executor] = None,
    parallel_admission_assignment: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run the Albilich v1 scheduler as an executable workflow.

    With execute=False this produces bounded plans. With execute=True it launches
    one Codex session per scheduler action, applies the returned patch, records
    run metrics, and repeats until the root is integrated, the budget stops work,
    or the step limit is reached.

    parallel_branches: defaults to three branch slots; 0 explicitly
    disables multi_branch_research, while 2..5 plans up to that many simultaneous
    branch-scoped researcher/adversarial-review workers per step window through the existing
    companion-session machinery.
    """
    research_mode = normalize_research_mode(research_mode)
    parallel_branches = normalize_parallel_branches(parallel_branches)
    if parallel_admission_assignment is not None and not isinstance(
        parallel_admission_assignment, Mapping
    ):
        raise ValueError("parallel admission assignment must be an object")
    persisted_workflow_assignment = _latest_workflow_randomized_assignment(store)
    if persisted_workflow_assignment is not None:
        if parallel_admission_assignment is None:
            parallel_admission_assignment = persisted_workflow_assignment
        elif (
            parallel_admission_assignment.get("assignment_input_sha256")
            != persisted_workflow_assignment.get("assignment_input_sha256")
        ):
            raise ValueError(
                "an existing workflow randomized assignment cannot be replaced"
            )
    parallel_policy_version = PARALLEL_WAVE_ADMISSION_POLICY_VERSION
    if parallel_admission_assignment is not None:
        assignment_protocol_version = parallel_admission_assignment.get(
            "protocol_version"
        )
        workflow_scoped_assignment = (
            assignment_protocol_version
            in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
        )
        if (
            assignment_protocol_version
            == BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
        ):
            with store.connect() as conn:
                stored_problem = store.get_problem_row(conn)
            stored_problem_sha256 = hashlib.sha256(
                str(stored_problem["root_statement"]).encode("utf-8")
            ).hexdigest()
            if parallel_admission_assignment.get("problem_id") != store.problem_id:
                raise ValueError(
                    "randomized block assignment problem does not match the proof store"
                )
            if (
                parallel_admission_assignment.get("problem_sha256")
                != stored_problem_sha256
            ):
                raise ValueError(
                    "randomized block assignment problem commitment does not match the proof store"
                )
        if not workflow_scoped_assignment and steps != 1:
            raise ValueError(
                "a protocol-v1 parallel-admission assignment must execute exactly one workflow step"
            )
        try:
            assignment_probe = bind_randomized_assignment(
                parallel_admission_assignment,
                candidate_set_sha256="0" * 64,
                dispatched_action_sha256="0" * 64,
                exposure_index=(0 if workflow_scoped_assignment else None),
            )
        except ValueError as exc:
            raise ValueError(f"invalid parallel admission assignment: {exc}") from exc
        selected_arm = next(
            (
                arm
                for arm in assignment_probe["arms"]
                if arm["arm_id"] == assignment_probe["selected_arm_id"]
            ),
            None,
        )
        if (
            not isinstance(selected_arm, Mapping)
            or selected_arm.get("policy_family") != "parallel_admission"
        ):
            raise ValueError(
                "parallel admission experiment requires parallel_admission policy arms"
            )
        parallel_policy_version = int(
            assignment_probe["selected_policy_version"]
        )
    local_aggregate_rss_supervision = (
        executor is None or _custom_executor_uses_local_aggregate_rss(executor)
    )
    local_aggregate_child_rss_limit_mb = (
        aggregate_child_max_process_tree_rss_mb()
        if local_aggregate_rss_supervision
        else None
    )
    aggregate_rss_governor = (
        AggregateProcessTreeRSSGovernor(local_aggregate_child_rss_limit_mb)
        if execute and local_aggregate_rss_supervision
        else None
    )
    execution_contract = (
        _workflow_execution_contract(
            executor=executor,
            model_profile=model_profile,
            model=model,
            reasoning_effort=reasoning_effort,
            codex_bin=codex_bin,
            sandbox=sandbox,
            web_search=web_search,
            research_mode=research_mode,
            timeout_sec=timeout_sec,
            max_context_chars=max_context_chars,
            max_aggregate_child_rss_mb=(
                local_aggregate_child_rss_limit_mb
            ),
        )
        if execute
        else {}
    )
    history = []
    console_path = ""
    console_lock = threading.Lock()
    console_write_throttle = _ConsoleWriteThrottle(_console_refresh_interval_seconds())
    started = time.monotonic()
    if execute:
        # Launching the workflow is an explicit (re)start: clear any prior
        # pause/stop so the run continues from the latest accepted revision.
        _sync_run_status_at_start(store)
        # Record the multi_branch_research mode (or its absence) on
        # problem_state; a no-op event-free update when unchanged.
        store.set_parallel_branches(
            parallel_branches,
            reason=(
                "explicit --parallel-branches flag"
                if parallel_branches
                else "parallel branch mode off for this run"
            ),
            source="workflow",
        )
        # Branch workbenches survive across sessions: refresh them from the
        # latest accepted proof state before the first dispatch. A malformed
        # state must abort before launch rather than being silently ignored.
        sync_branch_workbenches(store)
    # Per-role live session registry for same-role session resume:
    # actor_role -> {session_id, target_id, chain_len, last_revision}.
    role_sessions: Dict[str, Dict[str, Any]] = {}
    stale_retry_recoveries = 0
    max_stale_retry_recoveries = _stale_retry_recovery_attempts()

    # Periodic HMT authoring is deliberately independent of the proof wave.
    # The daemon writer may run while research continues, but its result is
    # published only to the sidecar catalog and never patched into proof state.
    hmt_lock = threading.Lock()
    hmt_thread: threading.Thread | None = None
    hmt_completed: Dict[str, Any] | None = None
    hmt_stop_event = threading.Event()
    hmt_last_attempted_integrated_claim_count = 0
    hmt_retry_not_before_revision = 0
    hmt_sidecar_results: list[Dict[str, Any]] = []

    def collect_hmt_sidecar() -> None:
        nonlocal hmt_thread, hmt_completed
        nonlocal hmt_last_attempted_integrated_claim_count, hmt_retry_not_before_revision
        with hmt_lock:
            completed = hmt_completed
            hmt_completed = None
        if completed is None:
            return
        action = completed["action"]
        execution = completed["execution"]
        owner_entry = completed["owner_entry"]
        # Compilation and publication belong to the sidecar thread. Collect
        # only bookkeeping here, so neither lane waits for the other's work.
        outcome = completed["publish_outcome"]
        result = {
            "action": dict(action),
            "execution": _public_execution(execution),
            "publish_outcome": outcome,
            "status": "completed" if outcome.get("accepted") else "failed",
            "non_blocking": True,
            "proof_state_revision": store.get_revision(),
        }
        hmt_sidecar_results.append(result)
        owner_entry["hmt_sidecar_result"] = result
        owner_entry["hmt_sidecar_status"] = result["status"]
        if outcome.get("accepted"):
            hmt_retry_not_before_revision = 0
        else:
            # A failed non-certifying writer must not consume an entire
            # integrated-claim cadence.  The old guard remembered the failed
            # checkpoint and suppressed every retry until ten more claims were
            # integrated, which could leave the dashboard with no HMT at the
            # 10-claim milestone and a mislabeled sequence 1 at 20 claims.
            # Retry after one accepted proof-state revision, keeping the HMT
            # off the proof lane while avoiding a same-step failure loop.
            hmt_last_attempted_integrated_claim_count = 0
            hmt_retry_not_before_revision = store.get_revision() + 1
        hmt_thread = None
        with console_lock:
            write_console_snapshot_locked(force=True)

    def start_hmt_sidecar(action: Mapping[str, Any], owner_entry: Dict[str, Any]) -> None:
        nonlocal hmt_thread, hmt_completed, hmt_last_attempted_integrated_claim_count
        if executor is not None and not _custom_executor_supports_parallel(
            executor
        ):
            # A serial executor has not promised thread safety or cooperative
            # cancellation. Keep the non-certifying HMT due for a later run
            # instead of violating that execution contract in a side thread.
            owner_entry["hmt_sidecar_status"] = "deferred_serial_executor"
            return
        session_item = _prepare_scheduled_session(
            store,
            action,
            research_mode=research_mode,
            web_search=web_search,
            max_context_chars=max_context_chars,
            model_profile=model_profile,
            is_companion=True,
        )
        session_plan = session_item["session_plan"]
        item_progress = _progress_callback_for_item(progress_callback_for(owner_entry), session_item)
        hmt_last_attempted_integrated_claim_count = int(
            action.get("hmt_source_integrated_claim_count") or 0
        )
        owner_entry.setdefault("parallel_actions", []).append(dict(action))
        owner_entry["hmt_sidecar_status"] = "running"

        def invoke() -> None:
            nonlocal hmt_completed
            try:
                if executor is None:
                    execution = execute_session(
                        store,
                        action,
                        session_plan,
                        model=model,
                        reasoning_effort=reasoning_effort,
                        model_profile=model_profile,
                        codex_bin=codex_bin,
                        sandbox=sandbox,
                        web_search=session_item["session_web_search"],
                        timeout_sec=timeout_sec,
                        progress_callback=item_progress,
                        stop_event=hmt_stop_event,
                        aggregate_rss_governor=aggregate_rss_governor,
                    )
                else:
                    _emit_synthetic_progress(item_progress, session_item, phase="started", status="running")
                    call_kwargs: Dict[str, Any] = {
                        "store": store,
                        "action": action,
                        "session_plan": session_plan,
                    }
                    try:
                        params = inspect.signature(executor).parameters
                        accepts_var_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
                        if accepts_var_kw or "progress_callback" in params:
                            call_kwargs["progress_callback"] = item_progress
                        if accepts_var_kw or "stop_event" in params:
                            call_kwargs["stop_event"] = hmt_stop_event
                        if accepts_var_kw or "aggregate_rss_governor" in params:
                            call_kwargs["aggregate_rss_governor"] = (
                                aggregate_rss_governor
                            )
                    except (TypeError, ValueError):
                        pass
                    execution = dict(executor(**call_kwargs))
                    _emit_synthetic_progress(
                        item_progress,
                        session_item,
                        phase="completed",
                        status=str(execution.get("status") or "completed"),
                        execution=execution,
                    )
            except BaseException as exc:  # intentional-boundary: non-certifying paper sidecar cannot stop proof work
                execution = {
                    "run_id": f"hmt-sidecar-{hmt_last_attempted_integrated_claim_count}",
                    "actor_role": "writer",
                    "status": "failed",
                    "returncode": -1,
                    "patch": None,
                    "patch_error": f"{type(exc).__name__}: {exc}",
                    "usage": {},
                }
            if hmt_stop_event.is_set():
                return
            with console_lock:
                owner_entry["hmt_sidecar_status"] = "publishing"
                write_console_snapshot_locked(force=True)
            try:
                errors = _evidence_boundary_errors(execution, session_plan)
                patch = execution.get("patch")
                if isinstance(patch, Mapping):
                    errors.extend(action_patch_contract_errors(action, patch))
                outcome = (
                    {"accepted": False, "errors": errors}
                    if errors
                    else publish_hmt_sidecar(store, action=action, execution=execution)
                )
            except Exception as exc:  # intentional-boundary: publication failure must not abort mathematical research
                outcome = {"accepted": False, "errors": [f"{type(exc).__name__}: {exc}"]}
            with hmt_lock:
                hmt_completed = {
                    "action": dict(action),
                    "session_plan": dict(session_plan),
                    "execution": execution,
                    "publish_outcome": outcome,
                    "owner_entry": owner_entry,
                }
            if not hmt_stop_event.is_set():
                # Do not wait for a possibly hours-long research step to make
                # the finished paper and publication status visible.
                collect_hmt_sidecar()

        hmt_thread = threading.Thread(
            target=invoke,
            daemon=True,
            name=(
                "albilich-hmt-sidecar-integrated-"
                f"{hmt_last_attempted_integrated_claim_count}"
            ),
        )
        hmt_thread.start()

    def write_console_snapshot_locked(*, force: bool = False) -> None:
        nonlocal console_path
        if write_console and console_write_throttle.should_write(force=force):
            console_path = str(write_run_console(store, history=history))

    def record_entry(entry: Dict[str, Any]) -> None:
        with console_lock:
            if not any(item is entry for item in history):
                history.append(entry)
            write_console_snapshot_locked(force=True)
            _write_partial_result_locked(store, history)

    def progress_callback_for(entry: Dict[str, Any]) -> Callable[[Mapping[str, Any]], None]:
        def update(progress: Mapping[str, Any]) -> None:
            run_id = str(progress.get("run_id") or f"live-{len(entry.get('live_session_updates', {})) + 1}")
            with console_lock:
                if not any(item is entry for item in history):
                    history.append(entry)
                # A periodic HMT is attached to the proof step that happened to
                # launch it, but may finish several proof steps later.  Its late
                # progress callback must not resurrect that already-finished
                # owner step as ``running`` in the console/dashboard.
                if not entry.get("finished_at"):
                    entry["execution_phase"] = "running"
                live_updates = entry.setdefault("live_session_updates", {})
                if not isinstance(live_updates, dict):
                    live_updates = {}
                    entry["live_session_updates"] = live_updates
                live_updates[run_id] = dict(progress)
                # The executor is allowed to inspect the dashboard snapshot as
                # soon as it starts.  Bypass the mature-run refresh throttle for
                # that first synthetic heartbeat so the UI never starts a child
                # with an empty live-session list.
                write_console_snapshot_locked(force=str(progress.get("phase") or "") == "started")

        return update

    outage_streak = 0
    outage_refunds = 0
    rejected_wave_streak = 0
    # steps <= 0 means "run until the wall clock, token budget, or a terminal
    # scheduler state stops the attempt" — no manual relaunch chains.
    step_limit = steps if steps > 0 else 10_000_000
    index = -1
    while True:
        index += 1
        if index >= step_limit:
            break
        if execute:
            # Pause/stop checkpoint: honored before every new action dispatch.
            control_action = _run_control_stop_action(store)
            if control_action is not None:
                entry = {
                    "step": index + 1,
                    "action": control_action,
                    "stop_reason": control_action["reason"],
                    "terminal_classification": control_action["terminal_classification"],
                }
                record_entry(entry)
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
                    aggregate_rss_governor=aggregate_rss_governor,
                )
            record_entry(entry)
            break

        collect_hmt_sidecar()
        recovery = _oldest_unlinked_dispatch_group(store) if execute else None
        dispatches: list[Dict[str, Any]] = []
        recovering_dispatch = recovery is not None
        replaying_results = False
        recovered_result_items: list[Dict[str, Any]] = []
        if recovery is not None:
            recovery_reason = str(recovery.get("reason") or "")
            if not bool(recovery.get("recoverable")):
                action = _dispatch_recovery_stop_action(
                    recovery, reason=recovery_reason or "the committed action is unavailable"
                )
                entry = {
                    "step": index + 1,
                    "action": action,
                    "stop_reason": action["reason"],
                    "terminal_classification": action["terminal_classification"],
                    "operator_action_required": action["operator_action_required"],
                    "dispatch_recovery": True,
                }
                record_entry(entry)
                break
            recovered_result_items = [
                dict(item) for item in recovery.get("result_items", [])
            ]
            all_recovery_actions = [
                dict(item) for item in recovery.get("actions", [])
            ]
            all_recovery_dispatches = [
                dict(item) for item in recovery.get("dispatches", [])
            ]
            if len(all_recovery_actions) != len(all_recovery_dispatches):
                raise RuntimeError("recoverable scheduler dispatch group is misaligned")
            replayable_result_items, unreturned_pairs = (
                _partition_recovery_results(
                    recovered_result_items,
                    all_recovery_actions,
                    all_recovery_dispatches,
                )
            )
            if replayable_result_items:
                # Returned results no longer depend on the current executor.
                # Consume only records that pass the same proof-critical merge
                # barrier used during live execution. A lower-priority receipt
                # cannot jump past a still-unreturned primary or verifier.
                replaying_results = True
                recovered_result_items = replayable_result_items
                actions = [dict(item["action"]) for item in replayable_result_items]
                recovered_ids = {
                    str(item["session_plan"].get("scheduler_dispatch_id") or "")
                    for item in replayable_result_items
                }
                dispatches = [
                    dict(item)
                    for item in all_recovery_dispatches
                    if str(item.get("dispatch_id") or "") in recovered_ids
                ]
            else:
                compatible, incompatibility_reason = _recovery_contract_compatibility(
                    recovery.get("execution_contract"), execution_contract
                )
                if not compatible:
                    action = _dispatch_recovery_stop_action(
                        recovery,
                        reason=incompatibility_reason,
                    )
                    entry = {
                        "step": index + 1,
                        "action": action,
                        "stop_reason": action["reason"],
                        "terminal_classification": action["terminal_classification"],
                        "operator_action_required": action["operator_action_required"],
                        "dispatch_recovery": True,
                    }
                    record_entry(entry)
                    break
                actions = [item[0] for item in unreturned_pairs]
                dispatches = [item[1] for item in unreturned_pairs]
            if not actions or len(actions) != len(dispatches):
                raise RuntimeError("recoverable scheduler dispatch group is empty or misaligned")
            action = actions[0]
            planning_audit_heads = dict(recovery["audit_chain_heads"])
            stored_wave = dict(action.get("decision_trace") or {}).get(
                "parallel_wave_admission"
            )
            parallel_wave_admission = (
                dict(stored_wave) if isinstance(stored_wave, Mapping) else {}
            )
        else:
            action, planning_audit_heads = _stable_next_action(
                store,
                research_mode=research_mode,
                web_search=web_search,
            )
            actions = [action]
            # All companion generators and the admission transition consume
            # one immutable projection.  Dispatch still compares its audit
            # heads with ``planning_audit_heads`` and replans if a concurrent
            # mutation occurred after the primary decision.
            wave_scheduler_state = store.get_scheduler_state()
            def materialize_wave(
                leader: Mapping[str, Any],
            ) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
                evaluation = new_parallel_generator_evaluation()
                materialized = [dict(leader)]
                if parallel_librarian_verifier:
                    materialized.extend(
                        parallel_companion_actions(
                            store,
                            leader,
                            research_mode=research_mode,
                            web_search=web_search,
                            parallel_branches=parallel_branches,
                            _defer_admission=True,
                            _scheduler_state=wave_scheduler_state,
                            _generator_evaluation=evaluation,
                            _parallel_policy_version=parallel_policy_version,
                        )
                    )
                else:
                    mark_candidate_generators_skipped(
                        evaluation,
                        PARALLEL_COMPANION_GENERATOR_IDS,
                        "parallel_companions_disabled",
                    )
                if parallel_branches:
                    materialized.extend(
                        multi_branch_research_actions(
                            store,
                            leader,
                            materialized[1:],
                            parallel_branches=parallel_branches,
                            research_mode=research_mode,
                            web_search=web_search,
                            _defer_capacity=True,
                            _scheduler_state=wave_scheduler_state,
                            _generator_evaluation=evaluation,
                        )
                    )
                else:
                    mark_candidate_generators_skipped(
                        evaluation,
                        {"multi_branch"},
                        "configured_parallelism_disabled",
                    )
                return materialized, evaluation

            actions, wave_generator_evaluation = materialize_wave(action)
            action, leader_promoted = _select_parallel_wave_leader(
                wave_scheduler_state, action, actions[1:]
            )
            if leader_promoted:
                # Candidate generation is conditional on its leader. Discard
                # the old companion set and regenerate every family against
                # the promoted action under the same authenticated snapshot.
                actions, wave_generator_evaluation = materialize_wave(action)
            admitted_companions, parallel_wave_admission = (
                _admit_and_finalize_parallel_companions(
                    store,
                    action,
                    actions[1:],
                    research_mode=research_mode,
                    web_search=web_search,
                    parallel_branches=parallel_branches,
                    _scheduler_state=wave_scheduler_state,
                    _generator_evaluation=wave_generator_evaluation,
                    _parallel_policy_version=parallel_policy_version,
                )
            )
            action = _bind_primary_parallel_wave_decision(
                action, parallel_wave_admission
            )
            actions = [action, *admitted_companions]
            if parallel_admission_assignment is not None:
                exposure_index = (
                    _next_workflow_assignment_exposure_index(
                        store, parallel_admission_assignment
                    )
                    if parallel_admission_assignment.get("protocol_version")
                    in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
                    else None
                )
                randomized_actions: list[Dict[str, Any]] = []
                for admitted_action in actions:
                    randomized_action = dict(admitted_action)
                    randomized_trace = dict(
                        randomized_action.get("decision_trace") or {}
                    )
                    randomized_trace["randomized_assignment"] = (
                        bind_randomized_assignment(
                            parallel_admission_assignment,
                            candidate_set_sha256=str(
                                randomized_trace.get("candidate_set_sha256")
                                or ""
                            ),
                            dispatched_action_sha256=str(
                                randomized_trace.get(
                                    "dispatched_action_sha256"
                                )
                                or ""
                            ),
                            exposure_index=exposure_index,
                        )
                    )
                    randomized_action["decision_trace"] = randomized_trace
                    randomized_actions.append(randomized_action)
                actions = randomized_actions
                action = actions[0]
        # Human steering present at step start is injected into this step's agent context
        # (via build_context_manifest); mark it consumed once the step has run so it is
        # delivered exactly once without halting the run.
        pending_steering_ids = [
            m.get("id") for m in steering.authenticated_unconsumed_steering(store)
        ]
        approach_alignment_steering_ids = [
            str(item)
            for item in dict(action.get("approach_alignment") or {}).get("source_steering_ids", [])
            if str(item)
        ]
        entry: Dict[str, Any] = {
            "step": index + 1,
            "action": action,
            "planning_audit_heads": planning_audit_heads,
            "parallel_wave_admission": parallel_wave_admission,
        }
        if recovering_dispatch:
            entry["dispatch_recovery"] = True
            entry["dispatch_group_id"] = str(
                recovery.get("dispatch_group_id") or ""
            )
            entry["scheduler_dispatch_ids"] = [
                dispatch["dispatch_id"] for dispatch in dispatches
            ]
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
                    aggregate_rss_governor=aggregate_rss_governor,
                )
            record_entry(entry)
            break

        # Same-role session resume: if the primary action is the same role on the
        # same target as that role's previous primary step (and under the chain cap),
        # resume its live agent with a compact delta instead of a cold restart.
        primary_role = actor_role_for_action(action)
        primary_target = str(action.get("target_id") or "root")
        primary_session_identity = _session_resume_identity(
            action,
            actor_role=primary_role,
            research_mode=research_mode,
            web_search=web_search,
            model_profile=model_profile,
        )
        prev_sess = role_sessions.get(primary_role)
        resume_id = ""
        resume_since: Optional[int] = None
        if (
            session_resume
            and not action.get("force_cold_start")
            and prev_sess
            and prev_sess.get("session_id")
            and prev_sess.get("identity") == primary_session_identity
            and int(prev_sess.get("chain_len", 0)) < MAX_RESUME_CHAIN
        ):
            resume_id = str(prev_sess["session_id"])
            resume_since = int(prev_sess.get("last_revision") or 0)
        if execute and not recovering_dispatch:
            try:
                dispatches, planning_audit_heads = _record_scheduler_dispatches(
                    store,
                    actions,
                    planning_audit_heads,
                    execution_contract=execution_contract,
                )
            except _StaleSchedulerDispatch:
                # No child launched. A pre-commit race needs a fresh decision;
                # a post-commit race is picked up by durable dispatch recovery.
                # Neither consumes the caller's step count.
                index -= 1
                continue
            entry["scheduler_dispatch_ids"] = [
                dispatch["dispatch_id"] for dispatch in dispatches
            ]
            entry["execution_context_audit_heads"] = planning_audit_heads

        scheduled: list[Dict[str, Any]] = []
        if replaying_results:
            scheduled = recovered_result_items
        else:
            preparation_attempts = MAX_SCHEDULER_SNAPSHOT_RETRIES if execute else 1
            for preparation_attempt in range(preparation_attempts):
                expected_context_heads = (
                    store.audit_chain_heads()
                    if execute and preparation_attempt > 0
                    else planning_audit_heads
                )
                scheduled = [
                    _prepare_scheduled_session(
                        store,
                        scheduled_action,
                        research_mode=research_mode,
                        web_search=web_search,
                        max_context_chars=max_context_chars,
                        model_profile=model_profile,
                        is_companion=(
                            bool(dispatches[position].get("is_companion"))
                            if execute and dispatches
                            else position > 0
                        ),
                        resume_session_id=(resume_id if position == 0 else ""),
                        resume_since_revision=(resume_since if position == 0 else None),
                        prior_context_hash=(
                            str(prev_sess.get("context_hash") or "")
                            if position == 0 and resume_id and prev_sess
                            else ""
                        ),
                        prior_authorized_entity_ids=(
                            prev_sess.get("authorized_existing_entity_ids", [])
                            if position == 0 and resume_id and prev_sess
                            else None
                        ),
                    )
                    for position, scheduled_action in enumerate(actions)
                ]
                if execute:
                    for scheduled_item, dispatch in zip(scheduled, dispatches):
                        scheduled_item["session_plan"]["scheduler_dispatch_id"] = (
                            dispatch["dispatch_id"]
                        )
                        scheduled_item["session_plan"][
                            "scheduler_decision_state_revision"
                        ] = dispatch["decision_state_revision"]
                        scheduled_item["session_plan"]["dispatched_action_hash"] = (
                            dispatch["dispatched_action_hash"]
                        )
                if _scheduled_plans_match_audit_heads(
                    scheduled, expected_context_heads
                ) and _audit_heads_equal(
                    store.audit_chain_heads(), expected_context_heads
                ):
                    planning_audit_heads = dict(expected_context_heads)
                    break
            else:
                if execute:
                    raise RuntimeError(
                        "scheduler could not construct a stable execution context after "
                        "committing the dispatch"
                    )
        if execute:
            entry["execution_context_audit_heads"] = planning_audit_heads
        execution_group_size = len(scheduled)
        if recovering_dispatch:
            try:
                execution_group_size = int(
                    recovery.get("dispatch_group_size") or len(scheduled)
                )
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    "recoverable scheduler dispatch group has an invalid size"
                ) from exc
            if execution_group_size < len(scheduled):
                raise RuntimeError(
                    "recoverable scheduler dispatch group is smaller than its "
                    "unresolved member set"
                )
        for scheduled_index, scheduled_item in enumerate(scheduled):
            scheduled_item["scheduled_index"] = scheduled_index
            scheduled_item["parallel_group_size"] = execution_group_size
        if not replaying_results and not _scheduled_plans_match_audit_heads(scheduled, planning_audit_heads):
            # A patch or policy event landed after planning but before all
            # evidence capsules were built. No child has launched, so discard
            # the stale plans and retry without consuming the step budget.
            index -= 1
            continue
        entry["session_plan"] = scheduled[0]["session_plan"]
        if len(scheduled) > 1:
            entry["parallel_session_plans"] = [item["session_plan"] for item in scheduled[1:]]
        if not execute:
            entry["execution_phase"] = "planned"
            entry["dry_run_note"] = "dry-run planning stops after one action because proof state is not mutated without execution"
            record_entry(entry)
            break

        if not replaying_results:
            _record_scheduler_attempts(store, scheduled)
            entry["scheduler_attempt_ids"] = [
                str(item.get("scheduler_attempt_id") or "")
                for item in scheduled
                if str(item.get("scheduler_attempt_id") or "")
            ]
        else:
            entry["execution_phase"] = "recovering_returned_result"
            entry["scheduler_result_ids"] = [
                str(item.get("scheduler_result_id") or "") for item in scheduled
            ]

        if pending_steering_ids:
            steering.mark_authenticated_delivered(
                store,
                pending_steering_ids,
                revision=store.get_revision(),
            )
        if approach_alignment_steering_ids:
            steering.mark_authenticated_approach_alignment_processing(
                store,
                approach_alignment_steering_ids,
            )

        entry["execution_phase"] = "running"
        entry["started_at"] = utc_now()
        record_entry(entry)

        if hmt_thread is None and store.get_revision() >= hmt_retry_not_before_revision:
            hmt_action = periodic_hmt_sidecar_action(store, research_mode=research_mode)
            if hmt_action is not None:
                source_integrated_claim_count = int(
                    hmt_action.get("hmt_source_integrated_claim_count") or 0
                )
                interval = int(hmt_action.get("hmt_integrated_claim_interval") or 1)
                if (
                    not hmt_last_attempted_integrated_claim_count
                    or source_integrated_claim_count
                    - hmt_last_attempted_integrated_claim_count
                    >= interval
                ):
                    start_hmt_sidecar(hmt_action, entry)

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
            # Persist a returned result before it waits behind any proof-merge
            # priority barrier.  Result durability and mutation order are
            # separate concerns.
            _prepare_and_record_scheduled_result(store, completed_item)
            with console_lock:
                pending_by_index.pop(int(completed_item.get("scheduled_index", -1)), None)
                completed_buffer.append(completed_item)
                flush_completed_results_locked()
                write_console_snapshot_locked()

        if replaying_results:
            executed_items = scheduled
            for completed_item in executed_items:
                apply_completed_item(completed_item)
        else:
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
                aggregate_rss_governor=aggregate_rss_governor,
            )
        with console_lock:
            flush_completed_results_locked(force=True)
            write_console_snapshot_locked(force=True)
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
        collect_hmt_sidecar()

        # Persist the per-branch workbenches from the just-accepted proof
        # state (idempotent: no write when a branch's workbench is unchanged).
        sync_branch_workbenches(store)

        if pending_steering_ids:
            steering.mark_authenticated_consumed(store, pending_steering_ids)

        # A steering message is not fully reconciled merely because an agent
        # read it.  Complete its alignment lifecycle only after an accepted
        # replacement portfolio is durably visible in SQLite.  Failed or
        # rejected refreshes remain pending and are retried automatically.
        if action.get("approach_brainstorming_required") and (primary_result.get("patch_outcome") or {}).get("accepted"):
            latest_portfolio = approach_portfolio_view(store.get_scheduler_state())
            previous_portfolio_id = str(action.get("supersedes_artifact_id") or "")
            latest_portfolio_id = str(latest_portfolio.get("artifact_id") or "")
            if latest_portfolio_id and latest_portfolio_id != previous_portfolio_id:
                completed_alignment_ids = list(
                    dict.fromkeys(
                        [
                            *approach_alignment_steering_ids,
                            *(
                                [str(item) for item in pending_steering_ids if str(item)]
                                if action.get("approach_alignment")
                                else []
                            ),
                        ]
                    )
                )
                steering.mark_authenticated_approach_alignment_completed(
                    store,
                    completed_alignment_ids,
                    artifact_id=latest_portfolio_id,
                    revision=int(latest_portfolio.get("state_revision") or store.get_revision()),
                )

        # Update the per-role session registry for same-role resume. Keep a healthy
        # session to continue next step; drop it on a failed/timed-out step so the
        # next same-role step cold-starts (graceful fallback).
        primary_status = str(primary_result.get("status") or "completed")
        new_session_id = str(primary_result.get("session_id") or "")
        if (
            not bool(scheduled[0].get("is_companion"))
            and new_session_id
            and primary_status not in {"failed", "timeout"}
        ):
            actually_resumed = bool(scheduled[0]["session_plan"].get("resume_session_id"))
            chain_len = (int(prev_sess.get("chain_len", 0)) + 1) if actually_resumed and prev_sess else 1
            role_sessions[primary_role] = {
                "session_id": new_session_id,
                "target_id": primary_target,
                "identity": primary_session_identity,
                "context_hash": str(scheduled[0]["session_plan"].get("context_hash") or ""),
                "authorized_existing_entity_ids": list(
                    scheduled[0]["session_plan"].get(
                        "authorized_existing_entity_ids", []
                    )
                ),
                "chain_len": chain_len,
                "last_revision": store.get_revision(),
            }
        elif not bool(scheduled[0].get("is_companion")):
            role_sessions.pop(primary_role, None)

        # A tripped aggregate guard is permanent for this invocation. Preserve
        # all returned work, then exit; retrying only launches more cancelled
        # children and can never recover memory supervision.
        if (
            aggregate_rss_governor is not None
            and aggregate_rss_governor.snapshot()["tripped"]
        ):
            entry["stop_reason"] = (
                "aggregate child memory supervision tripped; "
                "restart after checking resource limits"
            )
            entry["terminal_classification"] = "execution_configuration_required"
            entry["execution_phase"] = "awaiting_operator_configuration"
            entry["operator_action_required"] = (
                "check memory usage and limits before resuming"
            )
            record_entry(entry)
            break

        # Continuing after one rejection must not mean spending the entire
        # budget on an unrepaired output-contract loop. Accepted mathematical
        # counterexamples/gap reports are progress, not rejected patches.
        if action_results and all(str(row.get("status")) == "patch_rejected" for row in action_results):
            rejected_wave_streak += 1
        else:
            rejected_wave_streak = 0
        entry["rejected_wave_streak"] = rejected_wave_streak
        if rejected_wave_streak >= 3:
            entry["stop_reason"] = "three consecutive waves produced only rejected patches; inspect the patch errors before resuming"
            entry["terminal_classification"] = "execution_configuration_required"
            entry["execution_phase"] = "awaiting_operator_configuration"
            entry["operator_action_required"] = "repair the output contract or context before resuming; no automatic writer was launched"
            record_entry(entry)
            break

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
        if status == "blocked":
            execution = (
                primary_result.get("execution")
                if isinstance(primary_result.get("execution"), Mapping)
                else {}
            )
            failure_kind = str(execution.get("failure_kind") or "")
            detail = str(
                execution.get("patch_error")
                or "the configured execution backend cannot satisfy this mandatory action"
            )
            entry["stop_reason"] = detail
            entry["terminal_classification"] = (
                "backend_selection_required"
                if failure_kind == "heterogeneous_backend_required"
                else "execution_configuration_required"
            )
            entry["operator_action_required"] = (
                "resume with a model provider outside the recorded reviewer classes, "
                "or supply an explicit human/formal checkpoint"
                if failure_kind == "heterogeneous_backend_required"
                else "correct the execution configuration before resuming"
            )
            entry["execution_phase"] = "awaiting_operator_configuration"
            record_entry(entry)
            break
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
            # A failure caused by an operator pause/stop request (e.g. a hard
            # stop terminating the child) must not launch a stop-writer child.
            control_action = _run_control_stop_action(store)
            if control_action is not None:
                record_entry(entry)
                # Preserve both facts: the dispatched child produced a result
                # under a policy context that became stale, and the operator's
                # run-control request is the reason no replacement action is
                # launched.  Folding the latter into the failed execution entry
                # hid the explicit pause/stop action from reports and clients.
                record_entry(
                    {
                        "step": index + 2,
                        "action": control_action,
                        "stop_reason": control_action["reason"],
                        "terminal_classification": control_action[
                            "terminal_classification"
                        ],
                    }
                )
                break
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
                    aggregate_rss_governor=aggregate_rss_governor,
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
                aggregate_rss_governor=aggregate_rss_governor,
            )
            record_entry(entry)

    collect_hmt_sidecar()
    hmt_stop_event.set()
    if hmt_thread is not None:
        # Never wait for exposition when the proof run reaches a stop.  The
        # daemon writer observes this event and systemd also owns its process
        # cgroup, so no HMT child can keep a research attempt alive.
        for entry in reversed(history):
            if entry.get("hmt_sidecar_status") == "running":
                entry["hmt_sidecar_status"] = "cancelled_on_research_stop"
                break

    if execute:
        _finalize_run_status(store, history)
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
        "parallel_branches": parallel_branches,
        "hmt_sidecar_results": hmt_sidecar_results,
        "write_on_stop": write_on_stop,
        "write_console": write_console,
    }


def _sync_run_status_at_start(store: ProofStateStore) -> None:
    """Normalize an already-honored terminal run_status when a workflow launches.

    Relaunching after 'stopped'/'completed' is an explicit new attempt, so those
    become 'running' (the scheduler always plans from the latest accepted
    proof-state revision). Pending pause/stop requests ('pause_requested',
    'paused', 'stopping') are NOT cleared here: they are honored by the loop
    checkpoint before the first dispatch, and only an explicit `resume` clears
    them. dashboard_paused is display-only and is normalized.
    """
    try:
        current = store.get_run_status()
    except ValueError:
        return
    if current not in {"stopped", "awaiting_human", "completed", "dashboard_paused"}:
        return
    store.set_run_status(
        "running",
        reason=f"workflow started; clearing already-honored run_status {current}",
        source="workflow",
    )


def _run_control_stop_action(store: ProofStateStore) -> Optional[Dict[str, Any]]:
    """Return a synthetic stop action when a pause/stop request must halt the
    loop before the next dispatch; None when the run should keep going.

    Soft pause semantics: the current child session has already finished by the
    time this checkpoint runs, so honoring 'pause_requested' here implements
    finish-current-child-then-pause.
    """
    try:
        status = store.get_run_status()
    except ValueError:
        return None
    if status not in RUN_CONTROL_BLOCKING_STATUSES:
        return None
    if status == "pause_requested":
        store.set_run_status(
            "paused",
            reason="pause request honored: current child session finished; no new actions dispatched",
            source="workflow",
        )
        reason = "run paused by operator request (soft pause honored before the next action dispatch)"
        classification = "paused"
    elif status == "paused":
        reason = "run is paused; not dispatching new actions"
        classification = "paused"
    else:
        if status == "stopping":
            store.set_run_status(
                "stopped",
                reason="stop request honored: workflow exited before the next action dispatch",
                source="workflow",
            )
        reason = "run stopped by operator request"
        classification = "interrupted"
    return {
        "mode": "pause_run" if classification == "paused" else "stop_run",
        "target_id": "root",
        "reason": reason,
        "terminal_classification": classification,
    }


def _finalize_run_status(store: ProofStateStore, history: list[Mapping[str, Any]]) -> None:
    """Persist the terminal run_status when the executed workflow exits."""
    try:
        current = store.get_run_status()
    except ValueError:
        return
    if current in {"paused", "stopped", "completed", "awaiting_human"}:
        return
    last = history[-1] if history else {}
    action = last.get("action") if isinstance(last.get("action"), Mapping) else {}
    mode = str(action.get("mode") or "")
    if str(last.get("terminal_classification") or "") in {
        "backend_selection_required",
        "execution_configuration_required",
    }:
        store.set_run_status(
            "awaiting_human",
            reason=str(last.get("stop_reason") or "execution configuration is required"),
            source="workflow",
        )
        return
    if mode == "await_human":
        store.set_run_status(
            "awaiting_human",
            reason="scheduler paused for human steering",
            source="workflow",
        )
        return
    if mode in TERMINAL_MODES:
        stop_code = str(action.get("stop_reason_code") or "")
        reason = f"scheduler stopped: {mode}"
        if stop_code:
            reason = f"{reason} (stop_reason_code={stop_code})"
        store.set_run_status(
            "completed",
            reason=reason,
            source="workflow",
        )
        return
    reason = str(last.get("stop_reason") or "") or "workflow exited (step budget reached or execution stopped)"
    store.set_run_status("stopped", reason=reason, source="workflow")


def _record_abnormal_workflow_exit(store: ProofStateStore, exc: BaseException) -> None:
    """Persist a truthful terminal state when the workflow unwinds abnormally."""

    exception_type = type(exc).__name__
    message = str(exc).strip()
    reason = f"workflow aborted by {exception_type}"
    if message:
        reason = f"{reason}: {message[:240]}"
    try:
        current = store.get_run_status()
        if current not in {"paused", "stopped", "completed"}:
            store.set_run_status("stopped", reason=reason, source="workflow_exception")
        with store.connect() as conn:
            store.write_event(
                conn,
                store.get_revision(conn),
                "workflow_aborted",
                {
                    "exception_type": exception_type,
                    "message": message[:400],
                    "reason": reason,
                },
            )
            conn.commit()
    except Exception:  # intentional-boundary: diagnostic I/O must never replace the original exception
        # Never mask the original workflow exception with diagnostic I/O.
        pass


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
    if str(execution.get("failure_kind") or "") == "stale_stream":
        return True
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
    aggregate_rss_governor: AggregateProcessTreeRSSGovernor | None,
) -> None:
    blocker = _stop_writer_safety_blocker(store, research_mode=research_mode, web_search=web_search)
    if blocker:
        entry["stop_writer_blocked"] = True
        entry["stop_writer_blocker"] = blocker
        entry["stop_writer_action"] = _blocked_stop_writer_action(stop_action, blocker)
        return

    writer_action = _stop_writer_action(stop_action, research_mode=research_mode)
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
        aggregate_rss_governor=aggregate_rss_governor,
    )
    action_results = _apply_scheduled_results(
        store,
        executed_items,
        model=model,
        reasoning_effort=reasoning_effort,
        sandbox=sandbox,
    )
    entry["stop_writer_results"] = action_results


def _stop_writer_action(stop_action: Mapping[str, Any], *, research_mode: str = "") -> Dict[str, Any]:
    return {
        "mode": "write",
        "target_id": "root",
        "route_id": "",
        "research_mode": research_mode,
        "reason": "workflow stopped before a solved final proof; write existing verified and partial proof material honestly",
        "budget": {
            "allowed": True,
            "requested_tokens": 0,
            "spendable_tokens": 0,
            "reason": "writer closure after workflow stop",
        },
        "write_existing_proofs_on_stop": True,
        "stop_reason": str(stop_action.get("reason") or "workflow stopped"),
        "stop_reason_code": str(stop_action.get("stop_reason_code") or ""),
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
    except Exception as exc:  # intentional-boundary: stop safety fails closed when state inspection fails
        return {"reason": "could not inspect proof state before stop writer", "error": str(exc)}

    try:
        recommended = next_action(store, research_mode=research_mode, web_search=web_search)
    except Exception as exc:  # intentional-boundary: stop safety fails closed when scheduler inspection fails
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
        # Infrastructure stop, outside the completion policy's jurisdiction
        # The run stopped on a failed session, not on mathematics.
        "stop_reason_code": "execution_failure",
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
        # The step budget is an operator-set budget.
        "stop_reason_code": "exhausted_budget",
        "stop_reason_detail": "workflow step limit reached",
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
    prior_context_hash: str = "",
    prior_authorized_entity_ids: Any = None,
) -> Dict[str, Any]:
    session_web_search = search_policy_for_action(action, research_mode=research_mode, web_search=web_search)
    session_plan = prepare_session(
        store,
        action,
        max_context_chars=max_context_chars,
        model_profile=model_profile,
        resume_session_id=resume_session_id or None,
        resume_since_revision=resume_since_revision,
        prior_context_hash=prior_context_hash,
        prior_authorized_entity_ids=prior_authorized_entity_ids,
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
    aggregate_rss_governor: AggregateProcessTreeRSSGovernor | None = None,
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
            if accepts_var_kw or "aggregate_rss_governor" in params:
                call_kwargs["aggregate_rss_governor"] = kwargs.get(
                    "aggregate_rss_governor"
                )
        except (TypeError, ValueError):
            pass
        return executor(**call_kwargs)

    stop_event = threading.Event()
    watcher_stop = threading.Event()

    def _watch_run_control() -> None:
        # Hard-stop watcher: a `stop --hard` from another process flips the
        # persisted run_status to 'stopping' (hard=True); terminate the active
        # child sessions via the existing stop_event machinery.
        while not watcher_stop.wait(RUN_CONTROL_POLL_SECONDS):
            control = store.peek_run_control()
            if control.get("run_status") == "stopping" and control.get("hard"):
                stop_event.set()
                return

    watcher = threading.Thread(target=_watch_run_control, daemon=True, name="albilich-run-control-watcher")
    watcher.start()
    try:
        parallel_execution = (
            executor is None or _custom_executor_supports_parallel(executor)
        )

        def execute_item(item: Dict[str, Any]) -> Mapping[str, Any]:
            item_progress = _progress_callback_for_item(progress_callback, item)
            if executor is not None:
                _emit_synthetic_progress(
                    item_progress,
                    item,
                    phase="started",
                    status="running",
                )
                execution = dict(
                    _invoke_executor(
                        executor,
                        store=store,
                        action=item["action"],
                        session_plan=item["session_plan"],
                        progress_callback=item_progress,
                        stop_event=stop_event,
                        aggregate_rss_governor=aggregate_rss_governor,
                    )
                )
                _emit_synthetic_progress(
                    item_progress,
                    item,
                    phase="completed",
                    status=str(execution.get("status") or "completed"),
                    execution=execution,
                )
                return execution
            return execute_session(
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
                aggregate_rss_governor=aggregate_rss_governor,
            )

        if not parallel_execution or len(scheduled) == 1:
            executed: list[Dict[str, Any]] = []
            try:
                for item in scheduled:
                    execution = execute_item(item)
                    completed_item = {**item, "execution": execution}
                    if result_callback is not None:
                        result_callback(completed_item)
                    executed.append(completed_item)
            except BaseException:  # intentional-boundary: signal all companion workers before propagation
                stop_event.set()
                raise
            return executed

        executed: list[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(scheduled)) as pool:
            futures = {
                pool.submit(
                    execute_item,
                    item,
                ): item
                for item in scheduled
            }
            try:
                for future in as_completed(futures):
                    item = futures[future]
                    try:
                        execution = future.result()
                    except CancelledError:
                        execution = _cancelled_execution_for_item(
                            item,
                            aggregate_rss_governor=aggregate_rss_governor,
                        )
                    completed_item = {**item, "execution": execution}
                    if result_callback is not None:
                        result_callback(completed_item)
                    executed.append(completed_item)
                    if cancel_on_primary_failure and _primary_failure_should_cancel_companions(item, execution):
                        stop_event.set()
                        for pending in futures:
                            if pending is not future:
                                pending.cancel()
            except BaseException:  # intentional-boundary: cancel all companion futures before propagation
                stop_event.set()
                for future in futures:
                    future.cancel()
                raise
        executed.sort(key=lambda item: int(item["is_companion"]))
        return executed
    finally:
        watcher_stop.set()


def _write_partial_result_locked(store: ProofStateStore, history: list[Mapping[str, Any]]) -> None:
    """Keep a small always-current result summary on disk.

    The CLI prints its full result JSON only at process exit, so a killed run
    used to leave an empty stdout file; this sidecar preserves the recent step record.
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
    except Exception:  # intentional-boundary: partial-result sidecar has no proof authority
        pass


# Backend-outage circuit breaker tuning: a failed session that used zero
# tokens never reached the model — whether it died instantly or spent minutes
# in provider reconnect loops before giving up (both patterns observed live
# 2026-07-04/05; the original 60s threshold missed the slow-death variant).
OUTAGE_INSTANT_FAILURE_WALL_SECONDS = 600.0
OUTAGE_BACKOFF_BASE_SECONDS = 60
OUTAGE_BACKOFF_MAX_SECONDS = 600
MAX_OUTAGE_STEP_REFUNDS = 48
MAX_SCHEDULER_SNAPSHOT_RETRIES = 8


def _audit_heads_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    fields = (
        "proof_revision",
        "patch_journal_head",
        "proof_state_hash",
        "run_provenance_hash",
        "event_chain_length",
        "event_chain_head",
        "policy_event_head",
    )
    return all(left.get(field) == right.get(field) for field in fields)


def _stable_next_action(
    store: ProofStateStore,
    *,
    research_mode: str,
    web_search: str | None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Plan only across a quiescent, audit-identical state interval.

    ``next_action`` still contains several independently optimized state reads.
    This optimistic boundary prevents a concurrent patch or policy event from
    producing a decision assembled from different revisions. Deterministic
    planner maintenance writes cause a retry and then settle normally.
    """

    for _attempt in range(MAX_SCHEDULER_SNAPSHOT_RETRIES):
        before = store.audit_chain_heads()
        action = next_action(
            store,
            research_mode=research_mode,
            web_search=web_search,
            include_periodic_hmt=False,
        )
        after = store.audit_chain_heads()
        if _audit_heads_equal(before, after):
            return action, after
    raise RuntimeError(
        "scheduler could not obtain a stable proof/configuration snapshot after "
        f"{MAX_SCHEDULER_SNAPSHOT_RETRIES} attempts"
    )


def _record_scheduler_dispatches(
    store: ProofStateStore,
    actions: Sequence[Mapping[str, Any]],
    planning_audit_heads: Mapping[str, Any],
    *,
    execution_contract: Mapping[str, Any],
) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    """Commit an admitted execution wave before any external child starts."""

    group_id = f"dispatch-group-{uuid.uuid4().hex}"
    committed_at = utc_now()
    dispatches: list[Dict[str, Any]] = []
    for position, action in enumerate(actions):
        routing_errors = scheduler_dispatch_action_errors(action)
        if routing_errors:
            raise RuntimeError(
                "scheduler produced a nondispatchable action: "
                + "; ".join(routing_errors)
            )
        trace = action.get("decision_trace")
        if not isinstance(trace, Mapping):
            raise RuntimeError(
                "scheduler produced an executable action without decision provenance"
            )
        contract_trace_errors = scheduler_action_contract_trace_errors(
            trace, required=True
        )
        if contract_trace_errors:
            raise RuntimeError(
                "scheduler decision provenance has no valid action-semantics binding: "
                + "; ".join(contract_trace_errors)
            )
        dispatched_hash = action_sha256(action)
        if str(trace.get("dispatched_action_sha256") or "") != dispatched_hash:
            raise RuntimeError(
                "scheduler action no longer matches its decision-trace commitment"
            )
        if trace.get("randomized_assignment") is None:
            selection_metadata = {
                "selection_design": "deterministic",
                "candidate_set_hash": str(
                    trace.get("candidate_set_sha256") or ""
                ),
                "selection_policy_version": int(
                    trace.get("decision_policy_version") or 0
                ),
            }
        else:
            try:
                selection_metadata = randomized_assignment_metadata(trace)
            except ValueError as exc:
                raise RuntimeError(
                    f"scheduler randomized assignment is invalid: {exc}"
                ) from exc
        dispatch_id = f"dispatch-{uuid.uuid4().hex}"
        dispatched_action = {
            str(key): value
            for key, value in action.items()
            if str(key) != "decision_trace"
        }
        dispatches.append(
            {
                "op": "record_scheduler_dispatch",
                "dispatch_id": dispatch_id,
                "dispatch_group_id": group_id,
                "dispatch_position": position,
                "is_companion": position > 0,
                "actor_role": actor_role_for_action(action),
                "mode": str(action.get("mode") or ""),
                "target_id": str(action.get("target_id") or ""),
                "route_id": str(action.get("route_id") or ""),
                "decision_state_revision": int(
                    planning_audit_heads.get("proof_revision") or 0
                ),
                "proof_state_hash": str(
                    planning_audit_heads.get("proof_state_hash") or ""
                ),
                "prior_run_provenance_hash": str(
                    planning_audit_heads.get("run_provenance_hash") or ""
                ),
                "selection_design": selection_metadata["selection_design"],
                "candidate_set_hash": selection_metadata["candidate_set_hash"],
                "selection_policy_version": selection_metadata[
                    "selection_policy_version"
                ],
                "decision_trace": dict(trace),
                "dispatched_action_hash": dispatched_hash,
                "dispatched_action": dispatched_action,
                "execution_contract": dict(execution_contract),
                "committed_at": committed_at,
            }
        )
    patch = {
        "schema_version": SCHEMA_VERSION,
        "problem_id": store.problem_id,
        "base_revision": int(planning_audit_heads.get("proof_revision") or 0),
        "actor_role": "scheduler",
        "target_id": str(actions[0].get("target_id") or "root"),
        "operations": dispatches,
        "rationale": "commit scheduler dispatch before external execution",
    }
    outcome = apply_system_patch(store, patch, mode="dispatch")
    if not outcome.accepted:
        if any("stale patch:" in str(error) for error in outcome.errors):
            raise _StaleSchedulerDispatch("; ".join(outcome.errors))
        raise RuntimeError(
            "scheduler dispatch was not committed: " + "; ".join(outcome.errors)
        )
    try:
        committed_heads = store.audit_chain_heads_after_validated_commit(
            expected_revision=outcome.revision,
        )
    except ValidatedCommitSuperseded as exc:
        raise _StaleSchedulerDispatch(str(exc)) from exc
    return dispatches, committed_heads


def _record_scheduler_attempts(
    store: ProofStateStore,
    scheduled: Sequence[Dict[str, Any]],
) -> None:
    """Durably claim each dispatch before entering an external executor."""

    claimed_at = utc_now()
    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        seal = store.current_state_seal(conn)
        if not seal["valid"]:
            raise RuntimeError(
                "cannot claim scheduler execution against an invalid state seal: "
                + "; ".join(str(error) for error in seal["errors"][:8])
            )
        for item in scheduled:
            session_plan = item.get("session_plan")
            if not isinstance(session_plan, Mapping):
                raise RuntimeError("scheduler execution has no session plan")
            dispatch_id = str(session_plan.get("scheduler_dispatch_id") or "")
            if not dispatch_id:
                continue
            dispatch = conn.execute(
                "SELECT * FROM scheduler_dispatches "
                "WHERE dispatch_id = ?",
                (dispatch_id,),
            ).fetchone()
            if dispatch is None:
                raise RuntimeError(
                    f"cannot claim missing scheduler dispatch {dispatch_id}"
                )
            if conn.execute(
                "SELECT 1 FROM runs WHERE scheduler_dispatch_id = ?",
                (dispatch_id,),
            ).fetchone():
                raise RuntimeError(
                    f"cannot claim already completed scheduler dispatch {dispatch_id}"
                )
            if conn.execute(
                "SELECT 1 FROM scheduler_dispatch_results WHERE dispatch_id = ?",
                (dispatch_id,),
            ).fetchone():
                raise RuntimeError(
                    f"cannot invoke an executor after dispatch {dispatch_id} returned a result"
                )
            row = conn.execute(
                "SELECT COALESCE(MAX(attempt_number), 0) AS n "
                "FROM scheduler_dispatch_attempts WHERE dispatch_id = ?",
                (dispatch_id,),
            ).fetchone()
            attempt_number = int(row["n"] or 0) + 1
            attempt_id = f"attempt-{dispatch_id}-{attempt_number}"
            session_plan_hash = dispatch_json_sha256(dict(session_plan))
            try:
                execution_contract = json.loads(
                    str(dispatch["execution_contract_json"] or "")
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"scheduler dispatch {dispatch_id} has a malformed execution contract"
                ) from exc
            if not isinstance(execution_contract, Mapping):
                raise RuntimeError(
                    f"scheduler dispatch {dispatch_id} has no execution contract"
                )
            action = item.get("action")
            plan_errors: list[str] = []
            if not isinstance(action, Mapping) or action_sha256(action) != str(
                dispatch["dispatched_action_hash"] or ""
            ):
                plan_errors.append("action does not match the durable dispatch")
            expected_plan_fields = {
                "scheduler_dispatch_id": dispatch_id,
                "scheduler_decision_state_revision": int(
                    dispatch["decision_state_revision"] or 0
                ),
                "dispatched_action_hash": str(
                    dispatch["dispatched_action_hash"] or ""
                ),
                "actor_role": str(dispatch["actor_role"] or ""),
                "mode": str(dispatch["mode"] or ""),
                "target_id": str(dispatch["target_id"] or ""),
                "route_id": str(dispatch["route_id"] or ""),
                "state_revision": store.get_revision(conn),
            }
            if "model_profile" in execution_contract:
                expected_plan_fields["model_profile"] = str(
                    execution_contract.get("model_profile") or ""
                )
            for field, expected in expected_plan_fields.items():
                observed = session_plan.get(field)
                if type(expected) is int:
                    if type(observed) is not int or observed != expected:
                        plan_errors.append(
                            f"session plan {field} does not match the durable dispatch"
                        )
                elif not isinstance(observed, str) or observed != expected:
                    plan_errors.append(
                        f"session plan {field} does not match the durable dispatch"
                    )
            context_path = str(session_plan.get("context_path") or "")
            planned_context_hash = str(
                session_plan.get("context_hash") or ""
            )
            context_required = "max_context_chars" in execution_contract
            if context_required and (
                not context_path or not planned_context_hash
            ):
                plan_errors.append(
                    "session plan has no content-bound context manifest"
                )
            if context_path and planned_context_hash:
                try:
                    context_packet = json.loads(
                        read_bounded_text(
                            Path(context_path),
                            max_bytes=MAX_SESSION_CONTEXT_FILE_BYTES,
                            label="session context manifest",
                        )
                    )
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    plan_errors.append(
                        f"session context is unavailable or malformed: {exc}"
                    )
                else:
                    observed_context_hash = manifest_hash(context_packet)
                    embedded_context_hash = str(
                        context_packet.get("manifest_hash") or ""
                    )
                    if (
                        observed_context_hash != planned_context_hash
                        or embedded_context_hash != planned_context_hash
                    ):
                        plan_errors.append(
                            "session context content does not match its planned hash"
                        )
            if plan_errors:
                raise RuntimeError(
                    f"cannot claim scheduler dispatch {dispatch_id}: "
                    + "; ".join(plan_errors)
                )
            executor_identity = str(execution_contract.get("identity") or "")
            payload = {
                "attempt_id": attempt_id,
                "dispatch_id": dispatch_id,
                "attempt_number": attempt_number,
                "session_plan_hash": session_plan_hash,
                "executor_identity": executor_identity,
                "claimed_at": claimed_at,
            }
            event_id = store.write_event(
                conn,
                store.get_revision(conn),
                "scheduler_dispatch_attempt_claimed",
                payload,
            )
            conn.execute(
                "INSERT INTO scheduler_dispatch_attempts("
                "attempt_id, dispatch_id, attempt_number, session_plan_hash, "
                "executor_identity, claimed_at, event_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    attempt_id,
                    dispatch_id,
                    attempt_number,
                    session_plan_hash,
                    executor_identity,
                    claimed_at,
                    event_id,
                ),
            )
            append_scheduler_provenance_entry(
                conn,
                record_kind="attempt",
                record_id=attempt_id,
            )
            item["scheduler_attempt_id"] = attempt_id
            item["scheduler_attempt_number"] = attempt_number
        conn.execute(
            "UPDATE problem_state SET run_provenance_hash = ? WHERE problem_id = ?",
            (_run_provenance_hash(conn), store.problem_id),
        )
        conn.commit()


_DISPATCH_EXECUTION_FIELDS = (
    "backend",
    "backend_attestation",
    "run_id",
    "executor_run_id",
    "actor_role",
    "status",
    "returncode",
    "wall_time_seconds",
    "peak_memory_mb",
    "observed_aggregate_peak_memory_mb",
    "usage",
    "session_id",
    "patch",
    "patch_error",
    "output_artifact_ids",
    "final_message_path",
    "log_path",
    "model",
    "reasoning_effort",
    "sandbox",
    "web_search",
    "preflight_repair",
    "failure_kind",
    "resource_limits",
)


def _durable_execution_projection(
    execution: Mapping[str, Any], *, dispatch_id: str
) -> Dict[str, Any]:
    """Return the bounded execution fields needed to apply and report a result."""

    projected = {
        field: execution[field]
        for field in _DISPATCH_EXECUTION_FIELDS
        if field in execution
    }
    projected["run_id"] = str(
        projected.get("run_id") or f"run-{dispatch_id}"
    )
    patch = projected.get("patch")
    if isinstance(patch, Mapping):
        # Dispatch-bound patch identity belongs to the host.  It makes replay
        # idempotent and prevents an untrusted child from colliding with an
        # unrelated accepted patch identifier.
        projected["patch"] = {
            **dict(patch),
            "patch_id": f"dispatch-output-{dispatch_id}",
        }
    try:
        encoded = canonical_dispatch_json(projected)
    except (TypeError, ValueError, OverflowError) as exc:
        # Preserve a deterministic failure result even when a custom executor
        # returns a Python-only object or a non-finite number.
        projected = {
            "run_id": str(projected.get("run_id") or f"run-{dispatch_id}"),
            "actor_role": str(projected.get("actor_role") or ""),
            "status": "failed",
            "returncode": -1,
            "wall_time_seconds": 0.0,
            "peak_memory_mb": 0.0,
            "usage": {},
            "session_id": str(projected.get("session_id") or ""),
            "patch": None,
            "patch_error": (
                "executor returned a result that cannot be represented as "
                f"strict JSON: {type(exc).__name__}: {exc}"
            ),
            "output_artifact_ids": [],
            "model": str(projected.get("model") or ""),
            "reasoning_effort": str(projected.get("reasoning_effort") or ""),
            "sandbox": str(projected.get("sandbox") or ""),
            "web_search": str(projected.get("web_search") or ""),
            "failure_kind": "invalid_executor_result",
        }
        encoded = canonical_dispatch_json(projected)
    if len(encoded.encode("utf-8")) > MAX_DISPATCH_RESULT_RECORD_BYTES:
        return {
            "run_id": str(projected.get("run_id") or f"run-{dispatch_id}"),
            "actor_role": str(projected.get("actor_role") or ""),
            "status": "failed",
            "returncode": -1,
            "wall_time_seconds": 0.0,
            "peak_memory_mb": 0.0,
            "usage": {},
            "session_id": str(projected.get("session_id") or ""),
            "patch": None,
            "patch_error": (
                "executor result exceeds the durable result-record limit of "
                f"{MAX_DISPATCH_RESULT_RECORD_BYTES} bytes"
            ),
            "output_artifact_ids": [],
            "model": str(projected.get("model") or ""),
            "reasoning_effort": str(projected.get("reasoning_effort") or ""),
            "sandbox": str(projected.get("sandbox") or ""),
            "web_search": str(projected.get("web_search") or ""),
            "failure_kind": "result_record_limit",
        }
    return projected


def _bind_durable_path_artifact_sources(
    store: ProofStateStore,
    patch: Dict[str, Any],
) -> list[str]:
    """Commit staged artifact bytes, not only their mutable path names."""

    operations = patch.get("operations")
    if not isinstance(operations, list):
        return []
    actor_role = str(patch.get("actor_role") or "")
    errors: list[str] = []
    bound_operations: list[Any] = []
    for raw_operation in operations:
        if not isinstance(raw_operation, Mapping):
            bound_operations.append(raw_operation)
            continue
        operation = dict(raw_operation)
        # These fields are host-owned. Ignore any child assertion and replace
        # it with an identity observed through a stable descriptor.
        operation.pop("source_file_sha256", None)
        operation.pop("source_file_size_bytes", None)
        if (
            str(operation.get("op") or "")
            not in {"attach_artifact", "add_artifact"}
            or not str(operation.get("path") or "").strip()
            or "content" in operation
        ):
            bound_operations.append(operation)
            continue
        artifact_type = str(operation.get("artifact_type") or "")
        artifact_id = str(operation.get("artifact_id") or "")
        try:
            source_path = _validated_artifact_path(
                store,
                operation.get("path"),
                allow_writer_context_staging=(
                    actor_role == "writer"
                    and artifact_type in WRITER_PATH_ATTACH_ARTIFACT_TYPES
                ),
                artifact_id=artifact_id,
            )
            max_bytes = (
                WRITER_PATH_ATTACH_MAX_BYTES
                if actor_role == "writer"
                and artifact_type in WRITER_PATH_ATTACH_ARTIFACT_TYPES
                else MAX_COPIED_ARTIFACT_BYTES
            )
            digest, size = stable_file_sha256_size(
                source_path,
                max_bytes=max_bytes,
                label=f"staged artifact {artifact_id or '<empty>'}",
            )
        except (PatchRejected, ValueError) as exc:
            errors.append(f"could not bind path-based artifact source: {exc}")
        else:
            operation["path"] = source_path
            operation["source_file_sha256"] = digest
            operation["source_file_size_bytes"] = size
        bound_operations.append(operation)
    patch["operations"] = bound_operations
    return errors


def _record_scheduler_result(
    store: ProofStateStore,
    item: Dict[str, Any],
    *,
    validation_errors: Sequence[str],
) -> None:
    """Commit a returned executor result before applying its proof patch."""

    session_plan = item.get("session_plan")
    execution = item.get("execution")
    if not isinstance(session_plan, Mapping) or not isinstance(execution, Mapping):
        raise RuntimeError("scheduler result is missing its session plan or execution")
    dispatch_id = str(session_plan.get("scheduler_dispatch_id") or "")
    if not dispatch_id:
        return
    attempt_id = str(item.get("scheduler_attempt_id") or "")
    if not attempt_id:
        raise RuntimeError(
            f"scheduler dispatch {dispatch_id} returned without a durable attempt claim"
        )
    plan = dict(session_plan)
    result = dict(execution)
    errors = [str(error) for error in validation_errors]
    source_identity_errors = durable_path_source_identity_errors(
        result,
        allow_unbound=bool(errors),
    )
    if source_identity_errors:
        raise RuntimeError(
            "scheduler result has invalid staged-source identity: "
            + "; ".join(source_identity_errors)
        )
    result_id = f"result-{dispatch_id}"
    completed_at = utc_now()
    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        seal = store.current_state_seal(conn)
        if not seal["valid"]:
            raise RuntimeError(
                "cannot record scheduler result against an invalid state seal: "
                + "; ".join(str(error) for error in seal["errors"][:8])
            )
        attempt = conn.execute(
            "SELECT attempts.dispatch_id, attempts.session_plan_hash, "
            "dispatches.execution_contract_json "
            "FROM scheduler_dispatch_attempts AS attempts "
            "JOIN scheduler_dispatches AS dispatches "
            "ON dispatches.dispatch_id = attempts.dispatch_id "
            "WHERE attempts.attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if attempt is None or str(attempt["dispatch_id"] or "") != dispatch_id:
            raise RuntimeError(
                f"scheduler result {result_id} does not match its attempt claim"
            )
        if dispatch_json_sha256(plan) != str(
            attempt["session_plan_hash"] or ""
        ):
            raise RuntimeError(
                f"scheduler result {result_id} changed its claimed session plan"
            )
        try:
            execution_contract = json.loads(
                str(attempt["execution_contract_json"] or "")
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            execution_contract = None
        errors.extend(
            execution_resource_result_errors(execution_contract, result)
        )
        if conn.execute(
            "SELECT 1 FROM runs WHERE scheduler_dispatch_id = ?", (dispatch_id,)
        ).fetchone():
            raise RuntimeError(
                f"scheduler dispatch {dispatch_id} already has execution telemetry"
            )
        requested_run_id = str(result.get("run_id") or f"run-{dispatch_id}")

        def run_id_is_reserved(candidate: str) -> bool:
            result_owner = conn.execute(
                "SELECT dispatch_id FROM scheduler_dispatch_results "
                "WHERE run_id = ? AND dispatch_id != ?",
                (candidate, dispatch_id),
            ).fetchone()
            run_owner = conn.execute(
                "SELECT scheduler_dispatch_id FROM runs WHERE run_id = ?",
                (candidate,),
            ).fetchone()
            return result_owner is not None or run_owner is not None

        if run_id_is_reserved(requested_run_id):
            result["executor_run_id"] = str(
                result.get("executor_run_id") or requested_run_id
            )
            base_run_id = f"run-{dispatch_id}"
            reserved_run_id = base_run_id
            suffix = 0
            while run_id_is_reserved(reserved_run_id):
                suffix += 1
                reserved_run_id = f"{base_run_id}-{suffix}"
            result["run_id"] = reserved_run_id
            result_patch = result.get("patch")
            if isinstance(result_patch, Mapping) and isinstance(
                result_patch.get("operations"), list
            ):
                remapped_operations: list[Any] = []
                for operation in result_patch["operations"]:
                    if (
                        isinstance(operation, Mapping)
                        and str(operation.get("run_id") or "")
                        == requested_run_id
                    ):
                        remapped_operations.append(
                            {**dict(operation), "run_id": reserved_run_id}
                        )
                    else:
                        remapped_operations.append(operation)
                result["patch"] = {
                    **dict(result_patch),
                    "operations": remapped_operations,
                }
        else:
            result["run_id"] = requested_run_id
        item["execution"] = result
        plan_json = canonical_dispatch_json(plan)
        execution_json = canonical_dispatch_json(result)
        errors_json = canonical_dispatch_json(errors)
        if (
            len(plan_json.encode("utf-8"))
            + len(execution_json.encode("utf-8"))
            + len(errors_json.encode("utf-8"))
            > MAX_DISPATCH_RESULT_RECORD_BYTES
        ):
            raise RuntimeError(
                "scheduler result envelope exceeds its durable byte limit"
            )
        result_hash = dispatch_result_sha256(
            dispatch_id=dispatch_id,
            attempt_id=attempt_id,
            session_plan=plan,
            execution=result,
            validation_errors=errors,
        )
        existing = conn.execute(
            "SELECT run_id, result_hash, attempt_id, session_plan_json, execution_json, "
            "validation_errors_json FROM scheduler_dispatch_results "
            "WHERE dispatch_id = ?",
            (dispatch_id,),
        ).fetchone()
        if existing is not None:
            if (
                str(existing["result_hash"] or "") != result_hash
                or str(existing["run_id"] or "") != str(result.get("run_id") or "")
                or str(existing["attempt_id"] or "") != attempt_id
                or str(existing["session_plan_json"] or "") != plan_json
                or str(existing["execution_json"] or "") != execution_json
                or str(existing["validation_errors_json"] or "") != errors_json
            ):
                raise RuntimeError(
                    f"scheduler dispatch {dispatch_id} returned two different results"
                )
            item["scheduler_result_id"] = result_id
            conn.rollback()
            return
        payload = {
            "result_id": result_id,
            "dispatch_id": dispatch_id,
            "attempt_id": attempt_id,
            "result_hash": result_hash,
            "completed_at": completed_at,
        }
        event_id = store.write_event(
            conn,
            store.get_revision(conn),
            "scheduler_dispatch_result_recorded",
            payload,
        )
        conn.execute(
            "INSERT INTO scheduler_dispatch_results("
            "result_id, dispatch_id, attempt_id, run_id, session_plan_json, "
            "execution_json, validation_errors_json, result_hash, completed_at, "
            "event_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result_id,
                dispatch_id,
                attempt_id,
                str(result.get("run_id") or ""),
                plan_json,
                execution_json,
                errors_json,
                result_hash,
                completed_at,
                event_id,
            ),
        )
        append_scheduler_provenance_entry(
            conn,
            record_kind="result",
            record_id=result_id,
        )
        conn.execute(
            "UPDATE problem_state SET run_provenance_hash = ? WHERE problem_id = ?",
            (_run_provenance_hash(conn), store.problem_id),
        )
        conn.commit()
    item["scheduler_result_id"] = result_id


def _oldest_unlinked_dispatch_group(
    store: ProofStateStore,
) -> Optional[Dict[str, Any]]:
    """Load the sole potentially incomplete wave from one sealed snapshot.

    A valid transition cannot append a group while the then-latest group is
    unresolved, and completed run rows are immutable. Inductively, an
    unresolved group must therefore be the latest dispatch group.
    """

    with store.connect() as conn:
        conn.execute("BEGIN")
        audit_heads = store.audit_chain_heads(conn)
        first = conn.execute(
            "SELECT d.dispatch_group_id FROM scheduler_source_entries AS s "
            "JOIN scheduler_dispatches AS d ON d.dispatch_id = s.record_id "
            "WHERE s.record_kind = 'dispatch' "
            "ORDER BY s.sequence DESC LIMIT 1"
        ).fetchone()
        if first is None:
            return None
        group_id = str(first["dispatch_group_id"] or "")
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT d.* FROM scheduler_dispatches AS d "
                "LEFT JOIN runs AS r ON r.scheduler_dispatch_id = d.dispatch_id "
                "WHERE d.dispatch_group_id = ? AND r.run_id IS NULL "
                "ORDER BY d.dispatch_position",
                (group_id,),
            ).fetchall()
        ]
        if not rows:
            return None
        group_size_row = conn.execute(
            "SELECT COUNT(*) AS n FROM scheduler_dispatches "
            "WHERE dispatch_group_id = ?",
            (group_id,),
        ).fetchone()
        dispatch_group_size = int(group_size_row["n"] or 0)
        for row in rows:
            receipt = conn.execute(
                "SELECT result.*, attempt.session_plan_hash AS attempt_plan_hash, "
                "attempt.dispatch_id AS attempt_dispatch_id, "
                "attempt.attempt_number AS receipt_attempt_number, "
                "event.event_type AS receipt_event_type, "
                "event.payload_json AS receipt_event_payload_json "
                "FROM scheduler_dispatch_results AS result "
                "JOIN scheduler_dispatch_attempts AS attempt "
                "ON attempt.attempt_id = result.attempt_id "
                "JOIN events AS event ON event.event_id = result.event_id "
                "WHERE result.dispatch_id = ?",
                (row["dispatch_id"],),
            ).fetchone()
            row["_result_receipt"] = dict(receipt) if receipt is not None else None

    actions: list[Dict[str, Any]] = []
    receipt_items: list[Dict[str, Any]] = []
    execution_contract: Dict[str, Any] | None = None
    for row in rows:
        dispatch_id = str(row.get("dispatch_id") or "")
        raw_action = row.get("dispatched_action_json")
        raw_execution_contract = row.get("execution_contract_json")
        if raw_action is None or raw_execution_contract is None:
            return {
                "dispatch_group_id": group_id,
                "dispatches": rows,
                "actions": [],
                "audit_chain_heads": audit_heads,
                "recoverable": False,
                "reason": (
                    f"dispatch {dispatch_id} predates recoverable action and "
                    "executor-contract storage"
                ),
            }
        try:
            action_body = json.loads(str(raw_action))
            trace = json.loads(str(row.get("decision_trace_json") or ""))
            row_execution_contract = json.loads(str(raw_execution_contract))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"unlinked scheduler dispatch {dispatch_id} is malformed: {exc}"
            ) from exc
        if (
            not isinstance(action_body, dict)
            or "decision_trace" in action_body
            or not isinstance(trace, dict)
            or action_sha256(action_body)
            != str(row.get("dispatched_action_hash") or "")
            or str(trace.get("dispatched_action_sha256") or "")
            != str(row.get("dispatched_action_hash") or "")
            or str(action_body.get("mode") or "") != str(row.get("mode") or "")
            or str(action_body.get("target_id") or "")
            != str(row.get("target_id") or "")
            or str(action_body.get("route_id") or "")
            != str(row.get("route_id") or "")
            or actor_role_for_action(action_body)
            != str(row.get("actor_role") or "")
            or not isinstance(row_execution_contract, dict)
        ):
            raise RuntimeError(
                f"unlinked scheduler dispatch {dispatch_id} fails recovery validation"
            )
        if execution_contract is None:
            execution_contract = row_execution_contract
        elif execution_contract != row_execution_contract:
            raise RuntimeError(
                f"unlinked scheduler dispatch group {group_id} mixes execution contracts"
            )
        recovered_action = {**action_body, "decision_trace": trace}
        actions.append(recovered_action)
        receipt = row.get("_result_receipt")
        if receipt is not None:
            if not isinstance(receipt, Mapping):
                raise RuntimeError(
                    f"scheduler dispatch {dispatch_id} has an invalid result receipt"
                )
            try:
                plan = json.loads(str(receipt.get("session_plan_json") or ""))
                execution = json.loads(str(receipt.get("execution_json") or ""))
                validation_errors = json.loads(
                    str(receipt.get("validation_errors_json") or "")
                )
                event_payload = json.loads(
                    str(receipt.get("receipt_event_payload_json") or "")
                )
                receipt_attempt_number = int(
                    receipt.get("receipt_attempt_number") or 0
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"scheduler dispatch {dispatch_id} result receipt is malformed: {exc}"
                ) from exc
            result_id = str(receipt.get("result_id") or "")
            attempt_id = str(receipt.get("attempt_id") or "")
            result_hash = str(receipt.get("result_hash") or "")
            expected_event_payload = {
                "result_id": result_id,
                "dispatch_id": dispatch_id,
                "attempt_id": attempt_id,
                "result_hash": result_hash,
                "completed_at": str(receipt.get("completed_at") or ""),
            }
            result_patch = execution.get("patch") if isinstance(execution, dict) else None
            valid_receipt = (
                isinstance(plan, dict)
                and isinstance(execution, dict)
                and isinstance(validation_errors, list)
                and all(isinstance(error, str) for error in validation_errors)
                and str(receipt.get("dispatch_id") or "") == dispatch_id
                and str(receipt.get("attempt_dispatch_id") or "") == dispatch_id
                and str(receipt.get("run_id") or "")
                == str(execution.get("run_id") or "")
                and result_id == f"result-{dispatch_id}"
                and attempt_id
                == (
                    f"attempt-{dispatch_id}-"
                    f"{receipt_attempt_number}"
                )
                and str(plan.get("scheduler_dispatch_id") or "") == dispatch_id
                and dispatch_json_sha256(plan)
                == str(receipt.get("attempt_plan_hash") or "")
                and dispatch_result_sha256(
                    dispatch_id=dispatch_id,
                    attempt_id=attempt_id,
                    session_plan=plan,
                    execution=execution,
                    validation_errors=validation_errors,
                )
                == result_hash
                and not durable_path_source_identity_errors(
                    execution,
                    allow_unbound=bool(validation_errors),
                )
                and str(receipt.get("receipt_event_type") or "")
                == "scheduler_dispatch_result_recorded"
                and event_payload == expected_event_payload
                and str(plan.get("actor_role") or "")
                == str(row.get("actor_role") or "")
                and str(plan.get("mode") or "") == str(row.get("mode") or "")
                and str(plan.get("target_id") or "")
                == str(row.get("target_id") or "")
                and str(plan.get("route_id") or "")
                == str(row.get("route_id") or "")
                and (
                    not isinstance(result_patch, dict)
                    or str(result_patch.get("patch_id") or "")
                    == f"dispatch-output-{dispatch_id}"
                )
            )
            if not valid_receipt:
                raise RuntimeError(
                    f"scheduler dispatch {dispatch_id} result receipt fails recovery validation"
                )
            receipt_items.append(
                {
                    "action": recovered_action,
                    "session_plan": plan,
                    "session_web_search": str(plan.get("web_search") or ""),
                    "is_companion": bool(row.get("is_companion")),
                    "scheduled_index": int(row.get("dispatch_position") or 0),
                    # Preserve the committed wave cardinality after other
                    # members link telemetry. A remaining primary was still
                    # produced in parallel and may require the safe parallel
                    # stale-rebase path after a sibling changed the revision.
                    "parallel_group_size": dispatch_group_size,
                    "scheduler_attempt_id": attempt_id,
                    "scheduler_result_id": result_id,
                    "durable_validation_errors": validation_errors,
                    "execution": execution,
                }
            )
    return {
        "dispatch_group_id": group_id,
        "dispatch_group_size": dispatch_group_size,
        "dispatches": rows,
        "actions": actions,
        "result_items": receipt_items,
        "audit_chain_heads": audit_heads,
        "execution_contract": execution_contract,
        "recoverable": True,
        "reason": "",
    }


def _custom_executor_supports_dispatch_recovery(executor: Executor) -> bool:
    """Require an explicit dispatch-key idempotency declaration for retries."""

    return (
        getattr(executor, CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE, None)
        == CUSTOM_EXECUTOR_RECOVERY_CAPABILITY
    )


def _executor_accepts_keyword(executor: Executor, keyword: str) -> bool:
    try:
        parameters = inspect.signature(executor).parameters
    except (TypeError, ValueError):
        return False
    return keyword in parameters or any(
        parameter.kind == parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


def _custom_executor_uses_local_aggregate_rss(executor: Executor) -> bool:
    declared = str(
        getattr(executor, CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE, "") or ""
    )
    if declared not in {"", CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY}:
        raise ValueError(
            f"unsupported {CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE}: {declared!r}"
        )
    if declared == CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY and not (
        _executor_accepts_keyword(executor, "aggregate_rss_governor")
        and _executor_accepts_keyword(executor, "stop_event")
    ):
        raise ValueError(
            "a locally supervised custom executor must accept "
            "aggregate_rss_governor and stop_event"
        )
    return declared == CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY


def _custom_executor_supports_parallel(executor: Executor) -> bool:
    declared = str(
        getattr(executor, CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE, "") or ""
    )
    if declared not in {"", CUSTOM_EXECUTOR_PARALLEL_CAPABILITY}:
        raise ValueError(
            f"unsupported {CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE}: {declared!r}"
        )
    if declared == CUSTOM_EXECUTOR_PARALLEL_CAPABILITY:
        if not _executor_accepts_keyword(executor, "stop_event"):
            raise ValueError(
                "a parallel custom executor must accept stop_event"
            )
        if not _custom_executor_uses_local_aggregate_rss(executor):
            raise ValueError(
                "parallel custom execution requires local aggregate RSS supervision"
            )
    return declared == CUSTOM_EXECUTOR_PARALLEL_CAPABILITY


def _workflow_execution_contract(
    *,
    executor: Optional[Executor],
    model_profile: str,
    model: str,
    reasoning_effort: str,
    codex_bin: str,
    sandbox: str,
    web_search: str | None,
    research_mode: str,
    timeout_sec: int,
    max_context_chars: int,
    max_aggregate_child_rss_mb: float | None,
) -> Dict[str, Any]:
    local_aggregate_rss = (
        executor is None or _custom_executor_uses_local_aggregate_rss(executor)
    )
    parallel_execution = (
        executor is None or _custom_executor_supports_parallel(executor)
    )
    if executor is None:
        driver = "builtin_codex"
        resolved_executable = resolve_codex_executable(codex_bin)
        executable_attestation = attest_executable_identity(resolved_executable)
        if executable_attestation.get("valid"):
            identity = (
                "codex:"
                f"{executable_attestation.get('executable_path', '')}:"
                f"{executable_attestation.get('executable_sha256', '')}"
            )
        else:
            # The child runner will fail closed if the executable remains
            # unavailable.  Retaining this exact failed attestation still
            # prevents recovery under a different path/configuration.
            identity = f"codex-unresolved:{resolved_executable}"
        recovery_capability = "supervised_process"
    else:
        driver = "custom"
        executable_attestation = {}
        identity = str(
            getattr(executor, CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE, "") or ""
        ).strip()
        recovery_capability = (
            CUSTOM_EXECUTOR_RECOVERY_CAPABILITY
            if _custom_executor_supports_dispatch_recovery(executor)
            else "none"
        )
        if recovery_capability != "none" and not identity:
            raise ValueError(
                "an idempotent custom executor must declare a stable "
                f"{CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE}"
            )
    return {
        "version": 2,
        "driver": driver,
        "identity": identity,
        "executable_attestation": executable_attestation,
        "recovery_capability": recovery_capability,
        "concurrency_capability": (
            CUSTOM_EXECUTOR_PARALLEL_CAPABILITY
            if parallel_execution
            else "serial"
        ),
        "model_profile": str(model_profile),
        "model": str(model),
        "reasoning_effort": str(reasoning_effort),
        "codex_bin": str(codex_bin),
        "sandbox": str(sandbox),
        "web_search": str(web_search or ""),
        "research_mode": str(research_mode),
        "timeout_sec": int(timeout_sec),
        "max_context_chars": int(max_context_chars),
        "aggregate_process_tree_rss_enforcement": (
            "local_supervisor"
            if local_aggregate_rss
            else "external_executor_unverified"
        ),
        "max_aggregate_child_process_tree_rss_mb": (
            float(max_aggregate_child_rss_mb)
            if max_aggregate_child_rss_mb is not None
            else None
        ),
    }


def _recovery_contract_compatibility(
    recorded: Any, current: Mapping[str, Any]
) -> tuple[bool, str]:
    if not isinstance(recorded, Mapping):
        return False, "the original execution contract is unavailable"
    recorded_contract = dict(recorded)
    if recorded_contract != dict(current):
        return False, "the current execution configuration differs from the committed one"
    capability = str(recorded_contract.get("recovery_capability") or "")
    if capability not in {
        "supervised_process",
        CUSTOM_EXECUTOR_RECOVERY_CAPABILITY,
    }:
        return False, "the original executor did not guarantee safe dispatch replay"
    return True, ""


def _dispatch_recovery_stop_action(
    recovery: Mapping[str, Any], *, reason: str
) -> Dict[str, Any]:
    dispatches = recovery.get("dispatches")
    first = dispatches[0] if isinstance(dispatches, list) and dispatches else {}
    dispatch_id = str(first.get("dispatch_id") or "") if isinstance(first, Mapping) else ""
    return {
        "mode": "await_human",
        "target_id": str(first.get("target_id") or "root") if isinstance(first, Mapping) else "root",
        "reason": (
            f"cannot safely recover committed scheduler dispatch {dispatch_id or '<unknown>'}: "
            f"{reason}"
        ),
        "terminal_classification": "execution_configuration_required",
        "operator_action_required": (
            "use the built-in supervised backend, or provide a custom executor "
            f"with {CUSTOM_EXECUTOR_RECOVERY_ATTRIBUTE}="
            f"{CUSTOM_EXECUTOR_RECOVERY_CAPABILITY!r} and deduplicate work by "
            "session_plan['scheduler_dispatch_id']; the replacement must also "
            "match the originally committed execution configuration and "
            f"{CUSTOM_EXECUTOR_IDENTITY_ATTRIBUTE}"
        ),
    }
    return dispatches, store.audit_chain_heads()


def _scheduled_plans_match_audit_heads(
    scheduled: Sequence[Mapping[str, Any]],
    expected: Mapping[str, Any],
) -> bool:
    for item in scheduled:
        plan = item.get("session_plan") if isinstance(item, Mapping) else None
        if not isinstance(plan, Mapping):
            return False
        observed = plan.get("audit_chain_heads")
        if not isinstance(observed, Mapping) or not _audit_heads_equal(
            expected, observed
        ):
            return False
    return True


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
        if str(execution.get("failure_kind") or "") in {
            "resource_limit", "cancelled", "backend_contract", "configuration",
        }:
            return False
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


def _session_resume_identity(
    action: Mapping[str, Any],
    *,
    actor_role: str,
    research_mode: str,
    web_search: str | None,
    model_profile: str,
) -> Dict[str, Any]:
    """Identity fields that must remain equal before a provider session resumes."""

    effective_search = search_policy_for_action(
        action,
        research_mode=research_mode,
        web_search=web_search,
    )
    return {
        "actor_role": actor_role,
        "mode": str(action.get("mode") or ""),
        "target_id": str(action.get("target_id") or "root"),
        "route_id": str(action.get("route_id") or ""),
        "researcher_work_mode": str(action.get("researcher_work_mode") or ""),
        "search_setting": str(effective_search or "disabled"),
        "cas_enabled": bool(session_cas_enabled(actor_role, action)),
        "model_profile": model_profile,
    }


def _primary_failure_should_cancel_companions(item: Mapping[str, Any], execution: Mapping[str, Any]) -> bool:
    if item.get("is_companion"):
        return False
    return str(execution.get("status") or "") in {"failed", "timeout", "no_patch", "cancelled"}


def _cancelled_execution_for_item(
    item: Mapping[str, Any],
    *,
    aggregate_rss_governor: AggregateProcessTreeRSSGovernor | None = None,
) -> Dict[str, Any]:
    action = item.get("action", {}) if isinstance(item.get("action"), Mapping) else {}
    session_plan = item.get("session_plan", {}) if isinstance(item.get("session_plan"), Mapping) else {}
    mode = str(action.get("mode") or "step")
    target_id = str(action.get("target_id") or "root")
    governor_snapshot = (
        aggregate_rss_governor.snapshot()
        if aggregate_rss_governor is not None
        else {"peak_mb": 0.0}
    )
    return {
        "run_id": f"cancelled-{mode}-{target_id}",
        "actor_role": str(session_plan.get("actor_role") or ""),
        "status": "cancelled",
        "returncode": -1,
        "wall_time_seconds": 0.0,
        "peak_memory_mb": 0.0,
        "observed_aggregate_peak_memory_mb": float(
            governor_snapshot["peak_mb"]
        ),
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
        "failure_kind": "cancelled",
        "resource_limits": {
            "max_aggregate_child_process_tree_rss_mb": (
                aggregate_rss_governor.limit_mb
                if aggregate_rss_governor is not None
                else None
            ),
        },
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
        _prepare_and_record_scheduled_result(store, item)
        action = item["action"]
        session_plan = item["session_plan"]
        session_web_search = item["session_web_search"]
        execution = item["execution"]
        patch = execution.get("patch")
        patch_outcome = None
        durable_errors = item.get("durable_validation_errors")
        boundary_errors = (
            [str(error) for error in durable_errors]
            if isinstance(durable_errors, list)
            else ["scheduler result validation was not recorded"]
        )
        if boundary_errors:
            patch_outcome = {"accepted": False, "errors": boundary_errors}
            execution["patch_error"] = "\n".join(boundary_errors)
        elif isinstance(patch, Mapping):
            patch_outcome = _accepted_dispatch_patch_outcome(
                store,
                patch=patch,
                session_plan=session_plan,
                execution=execution,
            )
            if patch_outcome is None:
                authority_plan = session_plan
                policy_errors: list[str] = []
                if str(item.get("scheduler_result_id") or ""):
                    recovery_policy_head, policy_errors = (
                        _durable_result_recovery_policy_head(
                            store,
                            original_policy_head=str(
                                session_plan.get("policy_event_head")
                                or GENESIS_HASH
                            ),
                        )
                    )
                    if not policy_errors:
                        authority_plan = {
                            **dict(session_plan),
                            "policy_event_head": recovery_policy_head,
                        }
                if policy_errors:
                    patch_outcome = {
                        "accepted": False,
                        "errors": policy_errors,
                        "patch_id": str(patch.get("patch_id") or ""),
                    }
                else:
                    authority = session_authority(
                        action, authority_plan, execution
                    )
                    # Keep the child's original revision for session authority.
                    # The shared retry path checks intervening mutations before
                    # rebasing and carries that original revision to the guard.
                    patch_outcome = apply_patch_with_stale_retry(
                        store,
                        patch,
                        authority=authority,
                    ).to_dict()
            if patch_outcome.get("accepted"):
                _record_parallel_signals(store, patch, action=action, execution=execution)
        else:
            patch_outcome = {"accepted": False, "errors": [execution.get("patch_error") or "missing patch"]}

        status = str(execution.get("status") or "completed")
        if patch_outcome and not patch_outcome.get("accepted") and status not in {"failed", "timeout", "no_patch", "cancelled", "blocked"}:
            status = "patch_rejected"
        if status == "patch_rejected":
            execution["patch_error"] = "\n".join(str(error) for error in (patch_outcome or {}).get("errors", []))
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
            patch_accepted=bool(patch_outcome and patch_outcome.get("accepted")),
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


def _durable_result_recovery_policy_head(
    store: ProofStateStore,
    *,
    original_policy_head: str,
) -> tuple[str, list[str]]:
    """Allow crash recovery and draining a requested soft pause/stop.

    The result was already validated under ``original_policy_head`` before it
    became durable. A truthful workflow-abort transition and the automatic
    stopped-to-running transition on restart must not invalidate it.
    A soft request explicitly lets already-dispatched children finish. Allow
    that result to merge while the request is pending, not after the run has
    parked or resumed. Hard stops and other policy changes still fail closed.
    """

    with store.connect() as conn:
        conn.execute("BEGIN")
        seal = store.current_state_seal(conn)
        if not seal["valid"]:
            return "", [
                "cannot recover scheduler result against an invalid state seal: "
                + "; ".join(str(error) for error in seal["errors"][:8])
            ]
        state = conn.execute(
            "SELECT policy_event_head FROM problem_state WHERE problem_id = ?",
            (store.problem_id,),
        ).fetchone()
        current_head = str(
            state["policy_event_head"] or GENESIS_HASH
        ) if state is not None else ""
        if original_policy_head == current_head:
            return current_head, []
        if original_policy_head == GENESIS_HASH:
            base_event_id = 0
        else:
            base = conn.execute(
                "SELECT event_id FROM events WHERE event_hash = ?",
                (original_policy_head,),
            ).fetchone()
            if base is None:
                return "", [
                    "durable scheduler result cites an unknown policy-event head"
                ]
            base_event_id = int(base["event_id"] or 0)
        placeholders = ", ".join("?" for _ in POLICY_EVENT_TYPES)
        rows = conn.execute(
            "SELECT event_type, payload_json FROM events "
            f"WHERE event_id > ? AND event_type IN ({placeholders}) "
            "ORDER BY event_id",
            (base_event_id, *sorted(POLICY_EVENT_TYPES)),
        ).fetchall()

    waiting_for_restart = False
    for row in rows:
        if str(row["event_type"] or "") != "run_control_policy":
            return "", [
                "scheduler policy changed after the durable result returned"
            ]
        try:
            payload = json.loads(str(row["payload_json"] or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            return "", [
                "scheduler run-control policy is malformed after durable return"
            ]
        if not isinstance(payload, dict):
            return "", [
                "scheduler run-control policy is malformed after durable return"
            ]
        source = str(payload.get("source") or "")
        previous = str(payload.get("from") or "")
        current = str(payload.get("to") or "")
        if (
            not waiting_for_restart
            and previous == "running"
            and current in {"pause_requested", "stopping"}
            and payload.get("hard") is False
        ):
            continue
        if (
            not waiting_for_restart
            and source == "workflow_exception"
            and current == "stopped"
            and previous == "running"
        ):
            waiting_for_restart = True
            continue
        if (
            waiting_for_restart
            and source == "workflow"
            and previous == "stopped"
            and current == "running"
        ):
            waiting_for_restart = False
            continue
        return "", [
            "run-control policy changed outside the crash-recovery sequence "
            "after the durable result returned"
        ]
    if waiting_for_restart:
        return "", [
            "durable scheduler result recovery has not entered a restarted workflow"
        ]
    return current_head, []


def _prepare_and_record_scheduled_result(
    store: ProofStateStore, item: Dict[str, Any]
) -> None:
    """Validate one return once and persist it before ordered proof merging."""

    if isinstance(item.get("durable_validation_errors"), list):
        return
    action = item["action"]
    session_plan = item["session_plan"]
    execution = item["execution"]
    dispatch_id = str(session_plan.get("scheduler_dispatch_id") or "")
    if dispatch_id:
        execution = _durable_execution_projection(
            execution,
            dispatch_id=dispatch_id,
        )
        item["execution"] = execution
    patch = execution.get("patch")
    boundary_errors = _evidence_boundary_errors(execution, session_plan)
    if isinstance(patch, Mapping):
        boundary_errors.extend(
            _session_contract_errors(
                action=action,
                session_plan=session_plan,
                execution=execution,
                patch=patch,
            )
        )
        boundary_errors.extend(action_patch_contract_errors(action, patch))
        boundary_errors.extend(
            preflight_patch_errors(
                dict(patch),
                str(session_plan.get("actor_role") or ""),
                store=store,
            )
        )
        if not boundary_errors and isinstance(patch, dict):
            boundary_errors.extend(
                _bind_durable_path_artifact_sources(store, patch)
            )
    repair = execution.get("preflight_repair")
    if isinstance(repair, Mapping):
        remaining = repair.get("errors_after")
        if not isinstance(remaining, list):
            remaining = (
                repair.get("errors_before")
                if repair.get("attempted") is False
                else []
            )
        for error in remaining or []:
            message = f"unresolved patch preflight error: {error}"
            if message not in boundary_errors:
                boundary_errors.append(message)
    if dispatch_id:
        _record_scheduler_result(
            store,
            item,
            validation_errors=boundary_errors,
        )
    item["durable_validation_errors"] = list(boundary_errors)


def _accepted_dispatch_patch_outcome(
    store: ProofStateStore,
    *,
    patch: Mapping[str, Any],
    session_plan: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    """Recognize the exact result patch if a crash occurred after acceptance."""

    patch_id = str(patch.get("patch_id") or "")
    if not patch_id.startswith("dispatch-output-dispatch-"):
        return None
    with store.connect() as conn:
        row = conn.execute(
            "SELECT * FROM patches WHERE patch_id = ? AND status = 'applied'",
            (patch_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        normalized = _normalize_patch_aliases(dict(patch))
        operations = json.loads(str(row["operations_json"] or "[]"))
        evidence = json.loads(str(row["evidence_artifact_ids_json"] or "[]"))
        authority = json.loads(str(row["authority_json"] or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "accepted": False,
            "errors": [f"accepted dispatch patch record is malformed: {exc}"],
            "patch_id": patch_id,
        }
    expected_authority = session_authority(
        {}, session_plan, execution
    ).to_audit_dict()
    matches = (
        str(row["problem_id"] or "") == str(normalized.get("problem_id") or "")
        and str(row["actor_role"] or "") == str(normalized.get("actor_role") or "")
        and str(row["target_id"] or "") == str(normalized.get("target_id") or "")
        and operations == normalized.get("operations")
        and evidence == normalized.get("evidence_artifact_ids", [])
        and str(row["rationale"] or "") == str(normalized.get("rationale") or "")
        and isinstance(authority, dict)
        and authority.get("source") == "session"
        and authority.get("actor_role") == expected_authority["actor_role"]
        and authority.get("context_revision")
        == expected_authority["context_revision"]
        and authority.get("context_hash") == expected_authority["context_hash"]
        and authority.get("run_id") == expected_authority["run_id"]
        and authority.get("session_id") == expected_authority["session_id"]
    )
    if not matches:
        return {
            "accepted": False,
            "errors": [
                "dispatch patch identifier is already bound to a different accepted patch"
            ],
            "patch_id": patch_id,
        }
    return {
        "accepted": True,
        "revision": int(row["applied_revision"] or 0),
        "patch_id": patch_id,
        "errors": [],
        "recovered_from_accepted_patch": True,
    }


def _session_contract_errors(
    *,
    action: Mapping[str, Any],
    session_plan: Mapping[str, Any],
    execution: Mapping[str, Any],
    patch: Mapping[str, Any],
) -> list[str]:
    """Bind untrusted child output to the exact host-scheduled session."""

    errors: list[str] = []
    expected_role = actor_role_for_action(action)
    plan_role = str(session_plan.get("actor_role") or "")
    if plan_role != expected_role:
        errors.append(
            f"invalid session plan: actor_role {plan_role!r} != role for action {expected_role!r}"
        )
    comparisons = (
        ("mode", str(action.get("mode") or ""), str(session_plan.get("mode") or "")),
        ("target_id", str(action.get("target_id") or "root"), str(session_plan.get("target_id") or "root")),
        ("route_id", str(action.get("route_id") or ""), str(session_plan.get("route_id") or "")),
    )
    for field, scheduled, planned in comparisons:
        if scheduled != planned:
            errors.append(
                f"invalid session plan: {field} {planned!r} != scheduled value {scheduled!r}"
            )
    execution_role = str(execution.get("actor_role") or "")
    if execution_role != plan_role:
        errors.append(
            f"execution identity mismatch: actor_role {execution_role!r} != session role {plan_role!r}"
        )
    patch_role = str(patch.get("actor_role") or "")
    if patch_role != plan_role:
        errors.append(
            f"patch identity mismatch: actor_role {patch_role!r} != session role {plan_role!r}"
        )
    patch_target = str(patch.get("target_id") or "")
    plan_target = str(session_plan.get("target_id") or "")
    if patch_target != plan_target:
        errors.append(
            f"patch identity mismatch: target_id {patch_target!r} != session target {plan_target!r}"
        )
    if action.get("assurance_review_required"):
        actual_authority = session_authority(action, session_plan, execution)
        actual_class = actual_authority.reviewer_independence_class
        observed_classes = {
            str(item)
            for item in action.get(
                "observed_reviewer_independence_classes", []
            )
            or []
            if str(item)
        }
        if not actual_class:
            errors.append(
                "enhanced assurance review has no host-attested reviewer family"
            )
        elif actual_class in observed_classes:
            errors.append(
                "enhanced assurance review reused reviewer family "
                f"{actual_class!r}; choose a different provider/model family "
                "or obtain a human/formal checkpoint"
            )
    try:
        patch_revision = int(patch.get("base_revision"))
    except (TypeError, ValueError):
        patch_revision = -1
    try:
        context_revision = int(session_plan.get("state_revision"))
    except (TypeError, ValueError):
        context_revision = -2
    if patch_revision != context_revision:
        errors.append(
            f"patch context mismatch: base_revision {patch_revision} != session revision {context_revision}"
        )
    planned_context_hash = str(session_plan.get("context_hash") or "")
    if not planned_context_hash:
        errors.append("invalid session plan: context_hash is missing")
    context_path = str(session_plan.get("context_path") or "")
    if context_path:
        try:
            context_packet = json.loads(
                read_bounded_text(
                    Path(context_path),
                    max_bytes=MAX_SESSION_CONTEXT_FILE_BYTES,
                    label="session context manifest",
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"session context is unavailable or malformed: {exc}")
        else:
            actual_context_hash = manifest_hash(context_packet)
            embedded_context_hash = str(context_packet.get("manifest_hash") or "")
            if actual_context_hash != planned_context_hash:
                errors.append(
                    "session context content hash does not match the host-issued session plan"
                )
            if embedded_context_hash != planned_context_hash:
                errors.append(
                    "session context embedded hash does not match the host-issued session plan"
                )
    else:
        errors.append("invalid session plan: context_path is missing")
    return errors


def _evidence_boundary_errors(execution: Mapping[str, Any], session_plan: Mapping[str, Any]) -> list[str]:
    """Reject child patches that visibly searched unlisted local evidence paths."""
    log_path_text = str(execution.get("log_path") or "")
    context_path_text = str(session_plan.get("context_path") or "")
    if not log_path_text or not context_path_text:
        return []
    try:
        context = json.loads(
            read_bounded_text(
                Path(context_path_text),
                max_bytes=MAX_SESSION_CONTEXT_FILE_BYTES,
                label="session context manifest",
            )
        )
    except (OSError, ValueError, json.JSONDecodeError):
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
    in_exec_command = False
    pending_exec_command = False
    scan_exec_output = True
    for line in handle:
        stripped = line.strip()
        if stripped == "exec":
            in_exec_block = False
            in_exec_command = False
            pending_exec_command = True
            scan_exec_output = True
            continue
        if stripped == "codex" or stripped == "tokens used" or stripped.startswith("web search:"):
            in_exec_block = False
            in_exec_command = False
            pending_exec_command = False
            scan_exec_output = True
            continue
        if pending_exec_command:
            pending_exec_command = False
            in_exec_block = True
            in_exec_command = True
            scan_exec_output = not (
                _shell_command_reads_context_manifest(stripped)
                or _shell_command_reads_evidence_capsule(stripped)
            )
            yield line
            continue
        if in_exec_block:
            if in_exec_command:
                # Codex prints multiline shell commands verbatim before the
                # execution-result marker. Inspect every command line, but
                # decide whether its *output* is inert only after seeing the
                # entire command (e.g. a Python heredoc reading context.json).
                if re.match(r"^(?:succeeded in |exited \d+ in )", stripped):
                    in_exec_command = False
                else:
                    if (
                        _shell_command_reads_context_manifest(stripped)
                        or _shell_command_reads_evidence_capsule(stripped)
                    ):
                        scan_exec_output = False
                    yield line
                    continue
            if not scan_exec_output:
                continue
            yield line


def _shell_command_reads_context_manifest(command_line: str) -> bool:
    return "context.json" in command_line


def _shell_command_reads_evidence_capsule(command_line: str) -> bool:
    """Return whether a shell command reads the manifest-copied evidence packet.

    Output from these reads is inert artifact content.  It may legitimately
    quote provenance paths from an older checkout, but those quoted strings do
    not mean the child opened the old files.  The command line itself remains
    scanned, so an explicit second access outside the capsule is still caught.
    """
    return "/evidence/" in command_line or bool(
        re.search(r"(?:^|[\s'\"=])(?:\./)?evidence/", command_line)
    )


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
        relative = path[path.find(marker):]
        variants.append(relative)
        # Codex's workspace sandbox reports an explicitly granted repository
        # path through its synthetic /agents mount.  Treat that spelling as
        # the same approved path; without it, a writer can create the exact
        # manifest-listed staging file and still be rejected after the fact.
        variants.append("/" + relative)
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


def _partition_recovery_results(
    result_items: Sequence[Dict[str, Any]],
    actions: Sequence[Dict[str, Any]],
    dispatches: Sequence[Dict[str, Any]],
) -> tuple[
    list[Dict[str, Any]],
    list[tuple[Dict[str, Any], Dict[str, Any]]],
]:
    """Preserve live merge barriers while partitioning restart work."""

    receipt_ids = {
        str(item.get("session_plan", {}).get("scheduler_dispatch_id") or "")
        for item in result_items
    }
    unreturned_pairs = [
        (action, dispatch)
        for action, dispatch in zip(actions, dispatches)
        if str(dispatch.get("dispatch_id") or "") not in receipt_ids
    ]
    pending_items = [
        {
            "action": action,
            "session_plan": {
                "actor_role": str(dispatch.get("actor_role") or "")
            },
            "is_companion": bool(dispatch.get("is_companion")),
        }
        for action, dispatch in unreturned_pairs
    ]
    replayable = [
        item
        for item in result_items
        if not _blocked_by_pending_priority_barrier(item, pending_items)
    ]
    return replayable, unreturned_pairs


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
    actor_role = str(patch.get("actor_role") or execution.get("actor_role") or "")
    mode = str(action.get("mode") or "")
    target_id = str(action.get("target_id") or patch.get("target_id") or "root")
    run_id = str(execution.get("run_id") or "")
    invalid_run_ids = {str(getattr(store, "problem_id", "") or ""), str(patch.get("problem_id") or "")}
    normalized: list[Dict[str, Any]] = []
    for raw_signal in signals[:20]:
        if not isinstance(raw_signal, Mapping):
            continue
        payload = {
            # A child may guess or hallucinate its wall-clock time.  Stamp the
            # accepted exchange entry here so ordering reflects workflow time.
            "created_at": utc_now(),
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
        normalized.append(payload)
    if not normalized:
        return
    try:
        append_parallel_signal_batch(store, normalized)
    except (OSError, RuntimeError, TypeError, ValueError):
        # Signal exchange is advisory and must not undo an accepted proof-state
        # patch. No unauthenticated filesystem fallback is used.
        return


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
    # Artifact revisions are host-owned.  Rebase only the patch's optimistic
    # concurrency token; injecting ``state_revision`` into a child operation
    # both forged host metadata and created the historical off-by-one bug.
    rebased["operations"] = [dict(op) if isinstance(op, dict) else op for op in rebased.get("operations", [])]
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
    if actor not in {"researcher", "adversarial_reviewer", "villain"}:
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
    if actor not in {"researcher", "adversarial_reviewer", "villain", "strict_informal_verifier"}:
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
        # Operator-set wall clock is a budget: exhausting it always allows the
        # stop under every completion policy.
        "stop_reason_code": "exhausted_budget",
        "stop_reason_detail": "workflow wall time limit reached",
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
    patch_accepted: bool | None = None,
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
    if patch_accepted is not None:
        output_ids = (
            attached_artifact_ids(execution.get("patch"))
            if patch_accepted and isinstance(execution.get("patch"), Mapping)
            else []
        )
    elif not output_ids and isinstance(execution.get("patch"), Mapping):
        output_ids = attached_artifact_ids(execution.get("patch"))
    op["output_artifact_ids"] = list(output_ids or [])
    operations: list[Dict[str, Any]] = []
    failure_artifact = _session_failure_artifact_operation(action=action, execution=execution, status=status)
    if failure_artifact is not None:
        op["error_artifact_id"] = failure_artifact["artifact_id"]
        operations.append(failure_artifact)
    operations.append(op)
    patch = {
        "schema_version": SCHEMA_VERSION,
        "problem_id": store.problem_id,
        "base_revision": store.get_revision(),
        "actor_role": "scheduler",
        "target_id": str(action.get("target_id") or "root"),
        "operations": operations,
        "rationale": "record Albilich v1 workflow session metrics",
    }
    outcome = apply_system_patch(
        store,
        patch,
        mode=str(action.get("mode") or ""),
        route_id=str(action.get("route_id") or ""),
    ).to_dict()
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
        "executor_run_id": execution.get("executor_run_id", ""),
        "actor_role": execution.get("actor_role", ""),
        "status": execution.get("status", ""),
        "returncode": execution.get("returncode", 0),
        "wall_time_seconds": execution.get("wall_time_seconds", 0.0),
        "peak_memory_mb": execution.get("peak_memory_mb", 0.0),
        "observed_aggregate_peak_memory_mb": execution.get(
            "observed_aggregate_peak_memory_mb",
            execution.get("peak_memory_mb", 0.0),
        ),
        "usage": execution.get("usage", {}),
        "session_id": execution.get("session_id", ""),
        "patch_error": execution.get("patch_error", ""),
        "output_artifact_ids": execution.get("output_artifact_ids", []),
        "final_message_path": execution.get("final_message_path", ""),
        "log_path": execution.get("log_path", ""),
        "web_search": execution.get("web_search", ""),
        "preflight_repair": execution.get("preflight_repair", {}),
        "failure_kind": execution.get("failure_kind", ""),
        "resource_limits": execution.get("resource_limits", {}),
    }
