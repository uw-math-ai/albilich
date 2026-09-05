from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from .audit import PAPER_AUDIT_RESEARCH_MODE, ingest_paper_audit
from .bounded_io import read_bounded_text
from .backend_contract import BackendContractError, attest_backend
from .audit_checkpoint import (
    create_signed_audit_checkpoint,
    verify_signed_audit_checkpoint,
)
from .claude_runner import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_CLAUDE_PERMISSION_MODE,
    make_claude_executor,
)
from .completion_policy import record_root_intent_resolution
from .codex_runner import DEFAULT_CHILD_TIMEOUT_SECONDS, DEFAULT_CODEX_MODEL, DEFAULT_REASONING_EFFORT, DEFAULT_SANDBOX, prepare_session, resolve_codex_executable
from .console import build_run_console, write_run_console
from .context_builder import build_context_manifest
from .formal_handoff import write_formalization_manifest
from .invariants import validate_conn
from .metrics import compute_metrics
from .models import (
    COMPLETION_POLICIES,
    DEFAULT_COMPLETION_POLICY,
    SCHEMA_VERSION,
    problem_id_from_file,
    sanitize_problem_id,
)
from .monitor import BackgroundMonitor, start_background_monitor
from .patches import apply_operator_patch, reconcile_integrated_claims
from .report import build_markdown_report, write_markdown_report
from .result_status import classify_result
from .research_policy import DEFAULT_RESEARCH_MODE, DEFAULT_WEB_SEARCH, RESEARCH_MODES
from .reference_solution import ingest_reference_solution
from .replay import verify_event_journal, verify_patch_journal
from .scheduler import DEFAULT_MULTI_BRANCH_WORKERS, next_action
from .scope_state import import_certified_scope
from .store import GENERATION_ROOT, ProofStateStore
from .workflow import run_workflow
from .writing.revision import WRITING_REVISION_RESEARCH_MODE, ingest_writing_revision

DEFAULT_ATTEMPT_STEPS = 0
# Mathematical strategy has no default wall-clock expiration.  Operators may
# still supply --max-wall-sec as an explicit resource budget for a particular
# invocation; evidence-based scheduler checkpoints decide whether a proof
# program continues, pivots, or is revalidated.
DEFAULT_ATTEMPT_WALL_SECONDS: int | None = None
DEFAULT_INIT_TOTAL_TOKEN_BUDGET = 80_000_000
DEFAULT_INIT_VERIFICATION_RESERVE = 12_000_000
DEFAULT_ATTEMPT_TOTAL_TOKEN_BUDGET = 80_000_000
DEFAULT_ATTEMPT_VERIFICATION_RESERVE = 12_000_000
DEFAULT_ATTEMPT_MAX_REDUCTION_DEPTH = 4
MAX_OPERATOR_PATCH_BYTES = 16 * 1024 * 1024
MAX_PROBLEM_DOCUMENT_BYTES = 8 * 1024 * 1024


class _WorkflowTerminationSignal(BaseException):
    def __init__(self, signum: int):
        self.signum = int(signum)
        super().__init__(f"received signal {self.signum}")


@contextmanager
def _workflow_termination_guard():
    """Turn terminal/session shutdown signals into a finalizable exception."""

    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous: dict[int, Any] = {}

    def _raise_signal(signum: int, _frame: Any) -> None:
        raise _WorkflowTerminationSignal(signum)

    try:
        for signal_name in ("SIGHUP", "SIGTERM"):
            signum = getattr(signal, signal_name, None)
            if signum is None:
                continue
            previous[int(signum)] = signal.getsignal(signum)
            signal.signal(signum, _raise_signal)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Albilich v1 proof-state workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize Albilich v1 state for a data/*.md problem")
    p_init.add_argument("problem")
    p_init.add_argument("--problem-id")
    p_init.add_argument("--total-token-budget", type=int, default=DEFAULT_INIT_TOTAL_TOKEN_BUDGET)
    p_init.add_argument("--reserved-verification-budget", type=int, default=DEFAULT_INIT_VERIFICATION_RESERVE)
    p_init.add_argument("--max-reduction-depth", type=int, default=DEFAULT_ATTEMPT_MAX_REDUCTION_DEPTH)
    _add_completion_policy_arg(p_init)

    p_status = sub.add_parser("status", help="print proof-state metrics")
    p_status.add_argument("problem")

    p_check = sub.add_parser(
        "check", help="run proof invariants, journal replay, and artifact-file integrity checks"
    )
    p_check.add_argument("problem")

    p_checkpoint = sub.add_parser(
        "audit-checkpoint",
        help="write an Ed25519-signed audit root outside the mutable run directory",
    )
    p_checkpoint.add_argument("problem")
    p_checkpoint.add_argument("--private-key", required=True)
    p_checkpoint.add_argument("--output", required=True)

    p_verify_checkpoint = sub.add_parser(
        "verify-audit-checkpoint",
        help="verify an external signed audit checkpoint against this append-only history",
    )
    p_verify_checkpoint.add_argument("problem")
    p_verify_checkpoint.add_argument("checkpoint")
    p_verify_checkpoint.add_argument("--public-key", required=True)

    p_reconcile = sub.add_parser(
        "reconcile-integrations",
        help="reconcile stale verification obligations and claim/proof-approach integration state",
    )
    p_reconcile.add_argument("problem")

    p_assurance = sub.add_parser(
        "set-claim-assurance",
        help="designate the independent-review requirement for a claim",
    )
    p_assurance.add_argument("problem")
    p_assurance.add_argument("claim_id")
    p_assurance.add_argument(
        "--level",
        choices=("standard", "heterogeneous_review"),
        required=True,
    )
    p_assurance.add_argument("--rationale", required=True)
    p_assurance.add_argument("--allow-downgrade", action="store_true")

    p_scope = sub.add_parser(
        "scope-import",
        help="merge a certified theorem subgraph into a differently rooted paused proof state",
    )
    p_scope.add_argument("source_problem")
    p_scope.add_argument("target_problem")
    p_scope.add_argument(
        "--claim-id-pattern",
        action="append",
        default=[],
        help="case-insensitive regex selecting integrated source claim ids; repeatable",
    )
    p_scope.add_argument(
        "--include-claim",
        action="append",
        default=[],
        help="explicit integrated source claim id to include; repeatable",
    )
    p_scope.add_argument(
        "--artifact-pattern",
        action="append",
        default=[],
        help="case-insensitive regex selecting additional in-scope evidence artifacts; repeatable",
    )
    p_scope.add_argument(
        "--exclude-pattern",
        action="append",
        default=[],
        help="case-insensitive regex forbidden anywhere in the imported dependency closure; repeatable",
    )

    p_snapshot = sub.add_parser("snapshot", help="write an explicit JSON snapshot of the SQLite proof state")
    p_snapshot.add_argument("problem")

    p_context = sub.add_parser("context", help="print a compact context manifest")
    p_context.add_argument("problem")
    p_context.add_argument("--target-id", default="root")
    p_context.add_argument("--route-id")
    p_context.add_argument("--max-chars", type=int, default=12_000)

    p_step = sub.add_parser("step", help="choose the next deterministic Albilich v1 action")
    p_step.add_argument("problem")
    p_step.add_argument("--dry-run", action="store_true")
    p_step.add_argument("--max-context-chars", type=int, default=12_000)
    p_step.add_argument("--model-profile", default="default")
    p_step.add_argument("--web-search", choices=["disabled", "live"], default=DEFAULT_WEB_SEARCH, help="search policy used by research-mode planning")
    p_step.add_argument("--research-mode", choices=sorted(RESEARCH_MODES), default=DEFAULT_RESEARCH_MODE)
    _add_completion_policy_arg(p_step)

    p_run = sub.add_parser("run", help="run the Albilich v1 workflow planner or executor")
    p_run.add_argument("problem")
    p_run.add_argument("--steps", type=int, default=10)
    p_run.add_argument("--dry-run", action="store_true", help="plan sessions without launching Codex")
    p_run.add_argument("--execute", action="store_true", help="launch Codex sessions, apply patches, and record metrics")
    p_run.add_argument("--max-context-chars", type=int, default=12_000)
    p_run.add_argument("--model-profile", default="default")
    p_run.add_argument("--model", default=DEFAULT_CODEX_MODEL)
    p_run.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    p_run.add_argument("--codex-bin", default="codex")
    _add_backend_args(p_run)
    p_run.add_argument(
        "--sandbox",
        choices=(DEFAULT_SANDBOX, "read-only"),
        default=DEFAULT_SANDBOX,
        help="child command boundary; the default is the capsule-only permission profile",
    )
    p_run.add_argument("--web-search", choices=["disabled", "live"], default=DEFAULT_WEB_SEARCH, help="Codex web_search policy for executed sessions")
    p_run.add_argument("--research-mode", choices=sorted(RESEARCH_MODES), default=DEFAULT_RESEARCH_MODE)
    _add_completion_policy_arg(p_run)
    p_run.add_argument("--timeout-sec", type=int, default=DEFAULT_CHILD_TIMEOUT_SECONDS)
    p_run.add_argument("--max-wall-sec", type=int, help="optional whole-workflow wall-clock cap in seconds")
    p_run.add_argument("--parallel-librarian-verifier", dest="parallel_librarian_verifier", action="store_true", default=True)
    p_run.add_argument("--no-parallel-librarian-verifier", dest="parallel_librarian_verifier", action="store_false")
    _add_parallel_branches_arg(p_run)
    p_run.add_argument(
        "--parallel-admission-assignment",
        help=(
            "JSON file containing a preregistered randomized v9/v10 parallel-"
            "admission assignment; protocol v2 covers every workflow wave, "
            "while legacy protocol v1 requires --steps 1"
        ),
    )
    p_run.add_argument("--write-report", action="store_true")
    p_run.add_argument("--write-console", dest="write_console", action="store_true", default=True)
    p_run.add_argument("--no-write-console", dest="write_console", action="store_false")
    _add_dashboard_args(p_run)
    p_run.add_argument("--stop-on-rejection", dest="stop_on_rejection", action="store_true", default=True)
    p_run.add_argument("--no-stop-on-rejection", dest="stop_on_rejection", action="store_false")
    p_run.add_argument("--session-resume", dest="session_resume", action="store_true", default=True)
    p_run.add_argument("--no-session-resume", dest="session_resume", action="store_false")
    p_run.add_argument("--write-on-stop", dest="write_on_stop", action="store_true", default=True)
    p_run.add_argument("--no-write-on-stop", dest="write_on_stop", action="store_false")

    p_attempt = sub.add_parser("attempt", help="one-command Albilich v1 proof attempt")
    p_attempt.add_argument("problem")
    p_attempt.add_argument(
        "--steps",
        type=int,
        default=DEFAULT_ATTEMPT_STEPS,
        help="number of scheduler steps; 0 (default) continues until a terminal state, budget, or operator stop",
    )
    p_attempt.add_argument("--dry-run", action="store_true", help="plan sessions without launching Codex")
    p_attempt.add_argument("--max-context-chars", type=int, default=12_000)
    p_attempt.add_argument("--model-profile", default="default")
    p_attempt.add_argument("--model", default=DEFAULT_CODEX_MODEL)
    p_attempt.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    p_attempt.add_argument("--codex-bin", default="codex")
    _add_backend_args(p_attempt)
    p_attempt.add_argument(
        "--sandbox",
        choices=(DEFAULT_SANDBOX, "read-only"),
        default=DEFAULT_SANDBOX,
        help="child command boundary; the default is the capsule-only permission profile",
    )
    p_attempt.add_argument("--web-search", choices=["disabled", "live"], default=DEFAULT_WEB_SEARCH)
    p_attempt.add_argument("--research-mode", choices=sorted(RESEARCH_MODES), default=DEFAULT_RESEARCH_MODE)
    _add_completion_policy_arg(p_attempt)
    p_attempt.add_argument("--timeout-sec", type=int, default=DEFAULT_CHILD_TIMEOUT_SECONDS)
    p_attempt.add_argument(
        "--max-wall-sec",
        type=int,
        default=DEFAULT_ATTEMPT_WALL_SECONDS,
        help="optional explicit operator wall-clock budget; no wall-clock cap by default",
    )
    p_attempt.add_argument("--parallel-librarian-verifier", dest="parallel_librarian_verifier", action="store_true", default=True)
    p_attempt.add_argument("--no-parallel-librarian-verifier", dest="parallel_librarian_verifier", action="store_false")
    _add_parallel_branches_arg(p_attempt)
    p_attempt.add_argument(
        "--parallel-admission-assignment",
        help=(
            "JSON file containing a preregistered randomized v9/v10 parallel-"
            "admission assignment; protocol v2 covers every workflow wave, "
            "while legacy protocol v1 requires --steps 1"
        ),
    )
    p_attempt.add_argument("--total-token-budget", type=int, default=DEFAULT_ATTEMPT_TOTAL_TOKEN_BUDGET)
    p_attempt.add_argument("--reserved-verification-budget", type=int, default=DEFAULT_ATTEMPT_VERIFICATION_RESERVE)
    p_attempt.add_argument("--max-reduction-depth", type=int, default=DEFAULT_ATTEMPT_MAX_REDUCTION_DEPTH)
    p_attempt.add_argument("--stop-on-rejection", dest="stop_on_rejection", action="store_true", default=False)
    p_attempt.add_argument("--no-stop-on-rejection", dest="stop_on_rejection", action="store_false")
    p_attempt.add_argument("--session-resume", dest="session_resume", action="store_true", default=True)
    p_attempt.add_argument("--no-session-resume", dest="session_resume", action="store_false")
    p_attempt.add_argument("--write-on-stop", dest="write_on_stop", action="store_true", default=True)
    p_attempt.add_argument("--no-write-on-stop", dest="write_on_stop", action="store_false")
    p_attempt.add_argument("--no-write-report", dest="write_report", action="store_false", default=True)
    p_attempt.add_argument("--write-console", dest="write_console", action="store_true", default=True)
    p_attempt.add_argument("--no-write-console", dest="write_console", action="store_false")
    _add_dashboard_args(p_attempt)

    p_audit = sub.add_parser(
        "audit-paper",
        help="ingest a LaTeX/markdown/pasted proof file as a paper_solution_audit subject (conservative referee mode)",
    )
    p_audit.add_argument("document", help="path to the proof document to audit (.tex/.md/.txt)")
    p_audit.add_argument("--problem-id", help="explicit problem id (default: audit/<document stem>)")
    p_audit.add_argument("--title", default="", help="statement/title being audited (default: derived from the document)")
    p_audit.add_argument("--total-token-budget", type=int, default=DEFAULT_INIT_TOTAL_TOKEN_BUDGET)
    p_audit.add_argument("--reserved-verification-budget", type=int, default=DEFAULT_INIT_VERIFICATION_RESERVE)

    p_revise = sub.add_parser(
        "revise-paper",
        help="ingest an externally authored Markdown/LaTeX manuscript for writing-only revision and audit",
    )
    p_revise.add_argument("document", help="path to the manuscript to revise (.md or .tex)")
    p_revise.add_argument("--problem-id", help="explicit problem id (default: writing/<document stem>)")
    p_revise.add_argument("--title", default="", help="manuscript title (default: derived from the document)")
    p_revise.add_argument("--total-token-budget", type=int, default=DEFAULT_INIT_TOTAL_TOKEN_BUDGET)
    p_revise.add_argument("--reserved-verification-budget", type=int, default=DEFAULT_INIT_VERIFICATION_RESERVE)

    p_reference = sub.add_parser(
        "ingest-reference-solution",
        help="attach a human-supplied solution to an existing theorem run for local reconstruction and strict verification",
    )
    p_reference.add_argument("problem", help="existing data/*.md problem or problem id")
    p_reference.add_argument("document", help="reference solution (.md, .tex, .txt, or text-extractable .pdf)")
    p_reference.add_argument("--title", default="", help="reference title (default: derived from filename)")
    p_reference.add_argument(
        "--source-statement",
        default="",
        help="optional exact theorem statement claimed by the reference",
    )

    p_patch = sub.add_parser("apply-patch", help="apply a structured Albilich v1 patch JSON file")
    p_patch.add_argument("problem")
    p_patch.add_argument("patch_json")

    p_report = sub.add_parser("report", help="write or print a markdown report")
    p_report.add_argument("problem")
    p_report.add_argument("--write", action="store_true")

    p_console = sub.add_parser("console", help="write or print the consolidated Albilich run console")
    p_console.add_argument("problem")
    p_console.add_argument("--write", action="store_true")

    p_pause = sub.add_parser(
        "pause",
        help="soft-pause the run: the workflow finishes the current child session, then stops dispatching new actions (this pauses the run itself, not just the dashboard)",
    )
    p_pause.add_argument("problem")
    p_pause.add_argument("--reason", default="")

    p_resume = sub.add_parser(
        "resume",
        help="clear a run pause/stop; the workflow (relaunch run/attempt if none is active) continues from the latest accepted proof-state revision",
    )
    p_resume.add_argument("problem")
    p_resume.add_argument("--reason", default="")

    p_stop = sub.add_parser("stop", help="stop the run after the current child session finishes")
    p_stop.add_argument("problem")
    p_stop.add_argument(
        "--hard",
        action="store_true",
        help="also terminate the active child session immediately and record an interruption event artifact",
    )
    p_stop.add_argument("--reason", default="")

    p_formal = sub.add_parser("formal-handoff", help="write a formalization handoff manifest")
    p_formal.add_argument("problem")
    p_formal.add_argument("--claim-id", default="root")
    p_formal.add_argument("--route-id")

    p_monitor = sub.add_parser("monitor", help="serve a live web dashboard for a run")
    p_monitor.add_argument("problem")
    p_monitor.add_argument("--host", default="127.0.0.1")
    p_monitor.add_argument("--port", type=int, default=8765)
    p_monitor.add_argument("--interval", type=float, default=3.0, help="browser poll interval in seconds")
    p_monitor.add_argument("--no-open", dest="open_browser", action="store_false", default=True, help="do not auto-open a browser tab")

    args = parser.parse_args(argv)
    if args.command == "init":
        store = _store(args.problem, args.problem_id)
        root_statement = _read_root_statement(args.problem)
        state = store.init_problem(
            root_statement,
            total_token_budget=args.total_token_budget,
            reserved_verification_budget=args.reserved_verification_budget,
            max_reduction_depth=args.max_reduction_depth,
        )
        _apply_completion_policy(store, args)
        # Root-intent parsing: record how exploratory wording in the
        # problem file relates to the formal target; soft wording never flips
        # the completion policy by itself.
        state["root_intent_resolution"] = record_root_intent_resolution(store, markdown=root_statement)
        state["completion_policy"] = store.get_completion_policy()
        _print(state)
        return
    if args.command == "audit-paper":
        problem_id = args.problem_id or ("audit/" + sanitize_problem_id(Path(args.document).stem))
        store = ProofStateStore(problem_id)
        result = ingest_paper_audit(
            store,
            Path(args.document),
            title=args.title,
            total_token_budget=args.total_token_budget,
            reserved_verification_budget=args.reserved_verification_budget,
        )
        result["next_step"] = (
            f"run the audit with: run {store.problem_id} --execute --research-mode {PAPER_AUDIT_RESEARCH_MODE}"
        )
        _print(result)
        return
    if args.command == "scope-import":
        source_store = _store(args.source_problem)
        target_store = _store(args.target_problem)
        _ensure_initialized_if_problem_file(source_store, args.source_problem)
        _ensure_initialized_if_problem_file(target_store, args.target_problem)
        _print(
            import_certified_scope(
                source_store,
                target_store,
                claim_id_patterns=args.claim_id_pattern,
                include_claim_ids=args.include_claim,
                artifact_patterns=args.artifact_pattern,
                exclude_patterns=args.exclude_pattern,
            )
        )
        return
    if args.command == "revise-paper":
        problem_id = args.problem_id or ("writing/" + sanitize_problem_id(Path(args.document).stem))
        store = ProofStateStore(problem_id)
        result = ingest_writing_revision(
            store,
            Path(args.document),
            title=args.title,
            total_token_budget=args.total_token_budget,
            reserved_verification_budget=args.reserved_verification_budget,
        )
        result["next_step"] = (
            f"run the revision with: run {store.problem_id} --execute "
            f"--research-mode {WRITING_REVISION_RESEARCH_MODE} --completion-policy publication_ready"
        )
        _print(result)
        return

    # Validate the runtime before initializing or changing durable proof state.
    # Otherwise a missing helper leaves a committed, unexecutable dispatch.
    if (
        args.command == "attempt" and not args.dry_run
        or args.command == "run" and args.execute and not args.dry_run
    ):
        backend = getattr(args, "backend", "codex")
        if backend == "codex":
            args.codex_bin = resolve_codex_executable(args.codex_bin)
        binary = args.claude_bin if backend == "claude" else args.codex_bin
        try:
            attest_backend(binary, backend)
        except BackendContractError as exc:
            parser.error(str(exc))

    store = _store(args.problem, getattr(args, "problem_id", None))
    if args.command == "attempt":
        _ensure_initialized_if_problem_file(
            store,
            args.problem,
            total_token_budget=args.total_token_budget,
            reserved_verification_budget=args.reserved_verification_budget,
            max_reduction_depth=args.max_reduction_depth,
        )
    else:
        _ensure_initialized_if_problem_file(store, args.problem)
    _apply_completion_policy(store, args)

    if args.command == "status":
        payload = compute_metrics(store)
        payload["result_status"] = classify_result(store)
        _print(payload)
    elif args.command == "ingest-reference-solution":
        _print(
            ingest_reference_solution(
                store,
                Path(args.document),
                title=args.title,
                source_statement=args.source_statement,
            )
        )
    elif args.command == "check":
        with store.connect() as conn:
            invariant_errors = validate_conn(conn)
        replay = verify_patch_journal(store)
        event_replay = verify_event_journal(store)
        errors = [
            *invariant_errors,
            *[f"replay: {error}" for error in replay["errors"]],
            *[f"event replay: {error}" for error in event_replay["errors"]],
        ]
        _print(
            {
                "ok": not errors,
                "errors": errors,
                "invariant_errors": invariant_errors,
                "replay": replay,
                "event_replay": event_replay,
            }
        )
    elif args.command == "audit-checkpoint":
        _print(
            create_signed_audit_checkpoint(
                store,
                output_path=Path(args.output),
                private_key_path=Path(args.private_key),
            )
        )
    elif args.command == "verify-audit-checkpoint":
        _print(
            verify_signed_audit_checkpoint(
                store,
                checkpoint_path=Path(args.checkpoint),
                public_key_path=Path(args.public_key),
            )
        )
    elif args.command == "reconcile-integrations":
        _print(reconcile_integrated_claims(store))
    elif args.command == "set-claim-assurance":
        _print(
            apply_operator_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "human_operator",
                    "target_id": args.claim_id,
                    "operations": [
                        {
                            "op": "set_claim_assurance",
                            "claim_id": args.claim_id,
                            "assurance_level": args.level,
                            "rationale": args.rationale,
                            "allow_assurance_downgrade": bool(
                                args.allow_downgrade
                            ),
                        }
                    ],
                    "rationale": "operator claim-assurance designation",
                },
            ).to_dict()
        )
    elif args.command == "snapshot":
        store.write_snapshot()
        _print({"path": str(store.snapshot_path)})
    elif args.command == "context":
        _print(build_context_manifest(store, target_id=args.target_id, route_id=args.route_id, max_chars=args.max_chars))
    elif args.command == "step":
        action = next_action(store, research_mode=args.research_mode, web_search=args.web_search)
        result: Dict[str, Any] = {"action": action}
        if args.dry_run:
            result["session_plan"] = prepare_session(store, action, max_context_chars=args.max_context_chars, model_profile=args.model_profile)
        _print(result)
    elif args.command == "run":
        _apply_cas_assets(args)
        dashboard, _dashboard_handle = _maybe_start_run_dashboard(args, store)
        result = run_workflow(
            store,
            steps=args.steps,
            execute=bool(args.execute and not args.dry_run),
            max_context_chars=args.max_context_chars,
            model_profile=args.model_profile,
            model=_resolve_model_for_backend(args),
            reasoning_effort=args.reasoning_effort,
            codex_bin=args.codex_bin,
            sandbox=args.sandbox,
            web_search=args.web_search,
            research_mode=args.research_mode,
            timeout_sec=args.timeout_sec,
            max_wall_seconds=args.max_wall_sec,
            parallel_librarian_verifier=args.parallel_librarian_verifier,
            parallel_branches=args.parallel_branches,
            stop_on_rejection=args.stop_on_rejection,
            session_resume=args.session_resume,
            write_on_stop=args.write_on_stop,
            write_report=args.write_report,
            write_console=args.write_console,
            executor=_executor_for(args),
            parallel_admission_assignment=_parallel_admission_assignment(args),
        )
        if dashboard:
            result["dashboard"] = dashboard
        _print(result)
    elif args.command == "attempt":
        _apply_cas_assets(args)
        dashboard, _dashboard_handle = _maybe_start_run_dashboard(args, store)
        try:
            with _workflow_termination_guard():
                result = run_workflow(
                    store,
                    steps=args.steps,
                    execute=not args.dry_run,
                    max_context_chars=args.max_context_chars,
                    model_profile=args.model_profile,
                    model=_resolve_model_for_backend(args),
                    reasoning_effort=args.reasoning_effort,
                    codex_bin=args.codex_bin,
                    sandbox=args.sandbox,
                    web_search=args.web_search,
                    research_mode=args.research_mode,
                    timeout_sec=args.timeout_sec,
                    max_wall_seconds=args.max_wall_sec,
                    parallel_librarian_verifier=args.parallel_librarian_verifier,
                    parallel_branches=args.parallel_branches,
                    stop_on_rejection=args.stop_on_rejection,
                    session_resume=args.session_resume,
                    write_on_stop=args.write_on_stop,
                    write_report=args.write_report,
                    write_console=args.write_console,
                    executor=_executor_for(args),
                    parallel_admission_assignment=_parallel_admission_assignment(args),
                )
        except _WorkflowTerminationSignal as exc:
            raise SystemExit(128 + exc.signum) from None
        if dashboard:
            result["dashboard"] = dashboard
        _print(result)
    elif args.command == "apply-patch":
        patch = json.loads(
            read_bounded_text(
                Path(args.patch_json),
                max_bytes=MAX_OPERATOR_PATCH_BYTES,
                label="operator patch document",
            )
        )
        _print(apply_operator_patch(store, patch).to_dict())
    elif args.command == "report":
        if args.write:
            _print({"path": str(write_markdown_report(store))})
        else:
            print(build_markdown_report(store))
    elif args.command == "console":
        if args.write:
            _print({"path": str(write_run_console(store))})
        else:
            print(build_run_console(store))
    elif args.command == "pause":
        result = store.request_pause(reason=args.reason, source="cli")
        result["note"] = (
            "Soft pause: the workflow finishes the current child session, then sets run_status=paused "
            "before dispatching any new action. This pauses the Albilich run itself; the dashboard "
            "pause button only freezes the display."
        )
        result["run_timing"] = store.get_run_timing()
        _print(result)
    elif args.command == "resume":
        result = store.resume_run(reason=args.reason, source="cli")
        result["note"] = (
            f"Run resumed at proof-state revision {store.get_revision()}; the workflow continues from "
            "the latest accepted revision. If no workflow process is active, relaunch `run`/`attempt`."
        )
        result["run_timing"] = store.get_run_timing()
        _print(result)
    elif args.command == "stop":
        result = store.request_stop(hard=args.hard, reason=args.reason, source="cli")
        result["note"] = (
            "Hard stop: the active child session is terminated by the workflow's run-control watcher "
            "and an interruption event artifact was recorded."
            if args.hard
            else "Soft stop: the workflow finishes the current child session, then exits before the next dispatch."
        )
        result["run_timing"] = store.get_run_timing()
        _print(result)
    elif args.command == "formal-handoff":
        _print({"path": str(write_formalization_manifest(store, claim_id=args.claim_id, route_id=args.route_id))})
    elif args.command == "monitor":
        from .monitor import serve as _serve_monitor

        _serve_monitor(
            store,
            host=args.host,
            port=args.port,
            poll_ms=max(500, int(args.interval * 1000)),
            open_browser=args.open_browser,
        )


def _add_parallel_branches_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--parallel-branches",
        dest="parallel_branches",
        type=int,
        choices=[0, 2, 3, 4, 5],
        default=DEFAULT_MULTI_BRANCH_WORKERS,
        help=(
            "multi_branch_research mode: plan up to N (2-5) simultaneous branch-scoped researcher/adversarial-review "
            f"workers per step window (default {DEFAULT_MULTI_BRANCH_WORKERS}; use 0 to disable); "
            "the worker count and mode name are recorded on problem_state"
        ),
    )


def _parallel_admission_assignment(
    args: argparse.Namespace,
) -> Mapping[str, Any] | None:
    path = getattr(args, "parallel_admission_assignment", None)
    if not path:
        return None
    try:
        value = json.loads(
            read_bounded_text(
                Path(path),
                max_bytes=MAX_OPERATOR_PATCH_BYTES,
                label="parallel admission assignment",
            )
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid parallel admission assignment file: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ValueError("parallel admission assignment file must contain an object")
    return value


def _add_completion_policy_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--completion-policy",
        dest="completion_policy",
        choices=sorted(COMPLETION_POLICIES),
        default=None,
        help=(
            f"run-level completion policy persisted on problem_state (default {DEFAULT_COMPLETION_POLICY}): "
            "full_proof_first stops once the certified final proof exists; publication_ready additionally "
            "runs the post-proof paper/editor gate; partial_ok/exploratory explicitly accept partial results. "
            "Soft wording in the problem file never changes this by itself."
        ),
    )


def _apply_completion_policy(store: ProofStateStore, args: argparse.Namespace) -> None:
    """Persist an explicitly requested completion policy.

    Only the explicit flag changes the persisted policy; commands without the
    flag (or with it unset) leave the stored policy untouched.
    """
    policy = getattr(args, "completion_policy", None)
    if not policy:
        return
    try:
        store.set_completion_policy(policy, reason="explicit --completion-policy flag", source="cli")
    except ValueError:
        # Uninitialized problem state: nothing to persist onto yet.
        return
    # Keep the recorded root-intent note in sync with the explicit policy
    # (record_root_intent_resolution dedupes when nothing changed).
    record_root_intent_resolution(store, completion_policy=policy)


def _add_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--backend",
        choices=["codex", "claude"],
        default="codex",
        help="model backend for executed sessions (codex CLI or Claude Code CLI)",
    )
    parser.add_argument("--claude-bin", default="claude", help="Claude Code CLI binary when --backend=claude")
    parser.add_argument(
        "--claude-permission-mode",
        default=DEFAULT_CLAUDE_PERMISSION_MODE,
        choices=("dontAsk", "default", "manual", "plan", "acceptEdits", "auto"),
        help="Claude Code permission mode (default dontAsk inside the mandatory fail-closed evidence-capsule sandbox)",
    )
    parser.add_argument("--claude-max-turns", type=int, default=None, help="optional Claude Code --max-turns cap per session")
    parser.add_argument(
        "--cas",
        dest="cas_mode",
        choices=["on", "off"],
        default="on",
        help="enable or disable CAS scheduling and CAS access for every child session (default: on)",
    )
    parser.add_argument(
        "--cas-asset",
        action="append",
        default=[],
        metavar="PATH[::DESCRIPTION]",
        help="approved CAS helper file (e.g. a Macaulay2 .m2 script) surfaced to agents as a tool resource; repeatable",
    )


def _add_dashboard_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dashboard",
        dest="serve_dashboard",
        action="store_true",
        default=True,
        help="serve the associated dashboard while this run is active",
    )
    parser.add_argument(
        "--no-dashboard",
        dest="serve_dashboard",
        action="store_false",
        help="do not auto-serve the dashboard for this run",
    )
    parser.add_argument("--dashboard-host", default="127.0.0.1")
    parser.add_argument("--dashboard-port", type=int, default=8765)
    parser.add_argument(
        "--dashboard-interval",
        type=float,
        default=3.0,
        help="dashboard browser poll interval in seconds",
    )
    parser.add_argument("--open-dashboard", dest="open_dashboard", action="store_true", default=True)
    parser.add_argument("--no-open-dashboard", dest="open_dashboard", action="store_false")


def _maybe_start_run_dashboard(args: argparse.Namespace, store: ProofStateStore) -> tuple[Dict[str, Any], BackgroundMonitor | None]:
    if not getattr(args, "serve_dashboard", False):
        return {}, None
    requested_host = str(getattr(args, "dashboard_host", "127.0.0.1") or "127.0.0.1")
    requested_port = int(getattr(args, "dashboard_port", 8765) or 8765)
    existing_problem_id = _probe_dashboard_problem(requested_host, requested_port)
    try:
        handle = start_background_monitor(
            store,
            host=requested_host,
            port=requested_port,
            poll_ms=max(500, int(float(getattr(args, "dashboard_interval", 3.0) or 3.0) * 1000)),
            open_browser=bool(getattr(args, "open_dashboard", True)),
        )
    except Exception as exc:  # intentional-boundary: dashboard startup is optional and reported to stderr/result JSON
        info = {
            "enabled": False,
            "error": str(exc),
            "requested_host": requested_host,
            "requested_port": requested_port,
            "requested_url": f"http://{requested_host}:{requested_port}/",
            "existing_problem_id": existing_problem_id,
        }
        print(f"Albilich dashboard failed to start: {exc}", file=sys.stderr, flush=True)
        return info, None
    info = {
        "enabled": True,
        "url": handle.url,
        "host": handle.host,
        "port": handle.port,
        "problem_id": store.problem_id,
        "requested_url": f"http://{requested_host}:{requested_port}/",
        "requested_port_occupied": handle.port != requested_port,
        "existing_problem_id": existing_problem_id if handle.port != requested_port else "",
    }
    if handle.port != requested_port and existing_problem_id:
        info["warning"] = (
            f"requested dashboard URL is already serving {existing_problem_id}; "
            f"use dashboard.url for this run"
        )
        print(
            f"Albilich dashboard: {handle.url} "
            f"(requested {info['requested_url']} is already serving {existing_problem_id})",
            file=sys.stderr,
            flush=True,
        )
    else:
        print(f"Albilich dashboard: {handle.url}", file=sys.stderr, flush=True)
    return info, handle


def _probe_dashboard_problem(host: str, port: int) -> str:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/console", timeout=0.4) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    monitor = payload.get("_monitor")
    if isinstance(monitor, dict):
        return str(monitor.get("problem_id") or payload.get("problem_id") or "")
    return str(payload.get("problem_id") or "")


def _resolve_model_for_backend(args: argparse.Namespace) -> str:
    """Pick a sane default model for the Claude backend when --model was left as the codex default."""
    if getattr(args, "backend", "codex") == "claude" and args.model == DEFAULT_CODEX_MODEL:
        return DEFAULT_CLAUDE_MODEL
    return args.model


def _executor_for(args: argparse.Namespace) -> Optional[Callable[..., Any]]:
    if getattr(args, "backend", "codex") != "claude":
        return None
    return make_claude_executor(
        model=_resolve_model_for_backend(args),
        claude_bin=args.claude_bin,
        permission_mode=args.claude_permission_mode,
        max_turns=args.claude_max_turns,
        effort=getattr(args, "reasoning_effort", None) or None,
        timeout_sec=args.timeout_sec,
    )


def _apply_cas_assets(args: argparse.Namespace) -> None:
    """Apply whole-run CAS policy and expose approved assets to context_builder."""
    os.environ["ALBILICH_CAS_ENABLED"] = "0" if getattr(args, "cas_mode", "on") == "off" else "1"
    assets = getattr(args, "cas_asset", None)
    if assets:
        # Newline-separated: paths/descriptions can contain ':' (os.pathsep) and
        # use '::' as the path/description delimiter, so os.pathsep would mangle them.
        os.environ["ALBILICH_CAS_ASSETS"] = "\n".join(assets)


def _store(problem: str, explicit_problem_id: str | None = None) -> ProofStateStore:
    if explicit_problem_id:
        return ProofStateStore(explicit_problem_id)
    return ProofStateStore(_problem_id_for(problem))


def _problem_id_for(problem: str) -> str:
    normalized = problem.replace("\\", "/")
    marker = "agents/generation/data/"
    if marker in normalized:
        return problem_id_from_file("data/" + normalized.split(marker, 1)[1])
    try:
        return problem_id_from_file(normalized)
    except ValueError:
        return sanitize_problem_id(problem)


def _read_root_statement(problem: str) -> str:
    path = Path(problem)
    if not path.is_absolute() and not path.exists():
        path = GENERATION_ROOT / path
    if not path.exists():
        raise FileNotFoundError(path)
    return read_bounded_text(
        path,
        max_bytes=MAX_PROBLEM_DOCUMENT_BYTES,
        label="problem document",
    ).strip()


def _ensure_initialized_if_problem_file(
    store: ProofStateStore,
    problem: str,
    *,
    total_token_budget: int | None = None,
    reserved_verification_budget: int | None = None,
    max_reduction_depth: int | None = None,
) -> None:
    try:
        store.get_revision()
        return
    except ValueError as exc:
        if str(exc) != "problem state is not initialized":
            raise
    path = Path(problem)
    normalized = problem.replace("\\", "/")
    looks_like_problem_file = normalized.endswith(".md") and (normalized.startswith("data/") or "agents/generation/data/" in normalized or path.exists())
    if looks_like_problem_file:
        kwargs: Dict[str, Any] = {}
        if total_token_budget is not None:
            kwargs["total_token_budget"] = total_token_budget
        if reserved_verification_budget is not None:
            kwargs["reserved_verification_budget"] = reserved_verification_budget
        if max_reduction_depth is not None:
            kwargs["max_reduction_depth"] = max_reduction_depth
        root_statement = _read_root_statement(problem)
        store.init_problem(root_statement, **kwargs)
        record_root_intent_resolution(store, markdown=root_statement)


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
