from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .claude_runner import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_CLAUDE_PERMISSION_MODE,
    make_claude_executor,
)
from .codex_runner import DEFAULT_CHILD_TIMEOUT_SECONDS, DEFAULT_CODEX_MODEL, DEFAULT_REASONING_EFFORT, DEFAULT_SANDBOX, prepare_session
from .console import build_run_console, write_run_console
from .context_builder import build_context_manifest
from .formal_handoff import write_formalization_manifest
from .invariants import validate_conn
from .metrics import compute_metrics
from .models import problem_id_from_file, sanitize_problem_id
from .monitor import BackgroundMonitor, start_background_monitor
from .patches import apply_patch
from .report import build_markdown_report, write_markdown_report
from .result_status import classify_result
from .research_policy import DEFAULT_RESEARCH_MODE, DEFAULT_WEB_SEARCH, RESEARCH_MODES
from .scheduler import next_action
from .store import GENERATION_ROOT, ProofStateStore
from .workflow import run_workflow

DEFAULT_ATTEMPT_STEPS = 48
DEFAULT_ATTEMPT_WALL_SECONDS = 24 * 60 * 60
DEFAULT_INIT_TOTAL_TOKEN_BUDGET = 80_000_000
DEFAULT_INIT_VERIFICATION_RESERVE = 12_000_000
DEFAULT_ATTEMPT_TOTAL_TOKEN_BUDGET = 80_000_000
DEFAULT_ATTEMPT_VERIFICATION_RESERVE = 12_000_000
DEFAULT_ATTEMPT_MAX_REDUCTION_DEPTH = 4


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Albilich v1 proof-state workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize Albilich v1 state for a data/*.md problem")
    p_init.add_argument("problem")
    p_init.add_argument("--problem-id")
    p_init.add_argument("--total-token-budget", type=int, default=DEFAULT_INIT_TOTAL_TOKEN_BUDGET)
    p_init.add_argument("--reserved-verification-budget", type=int, default=DEFAULT_INIT_VERIFICATION_RESERVE)
    p_init.add_argument("--max-reduction-depth", type=int, default=DEFAULT_ATTEMPT_MAX_REDUCTION_DEPTH)

    p_status = sub.add_parser("status", help="print proof-state metrics")
    p_status.add_argument("problem")

    p_check = sub.add_parser("check", help="run invariant checks")
    p_check.add_argument("problem")

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
    p_run.add_argument("--sandbox", default=DEFAULT_SANDBOX)
    p_run.add_argument("--web-search", choices=["disabled", "live"], default=DEFAULT_WEB_SEARCH, help="Codex web_search policy for executed sessions")
    p_run.add_argument("--research-mode", choices=sorted(RESEARCH_MODES), default=DEFAULT_RESEARCH_MODE)
    p_run.add_argument("--timeout-sec", type=int, default=DEFAULT_CHILD_TIMEOUT_SECONDS)
    p_run.add_argument("--max-wall-sec", type=int, help="optional whole-workflow wall-clock cap in seconds")
    p_run.add_argument("--parallel-librarian-verifier", dest="parallel_librarian_verifier", action="store_true", default=True)
    p_run.add_argument("--no-parallel-librarian-verifier", dest="parallel_librarian_verifier", action="store_false")
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
    p_attempt.add_argument("--steps", type=int, default=DEFAULT_ATTEMPT_STEPS)
    p_attempt.add_argument("--dry-run", action="store_true", help="plan sessions without launching Codex")
    p_attempt.add_argument("--max-context-chars", type=int, default=12_000)
    p_attempt.add_argument("--model-profile", default="default")
    p_attempt.add_argument("--model", default=DEFAULT_CODEX_MODEL)
    p_attempt.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    p_attempt.add_argument("--codex-bin", default="codex")
    _add_backend_args(p_attempt)
    p_attempt.add_argument("--sandbox", default=DEFAULT_SANDBOX)
    p_attempt.add_argument("--web-search", choices=["disabled", "live"], default=DEFAULT_WEB_SEARCH)
    p_attempt.add_argument("--research-mode", choices=sorted(RESEARCH_MODES), default=DEFAULT_RESEARCH_MODE)
    p_attempt.add_argument("--timeout-sec", type=int, default=DEFAULT_CHILD_TIMEOUT_SECONDS)
    p_attempt.add_argument("--max-wall-sec", type=int, default=DEFAULT_ATTEMPT_WALL_SECONDS)
    p_attempt.add_argument("--parallel-librarian-verifier", dest="parallel_librarian_verifier", action="store_true", default=True)
    p_attempt.add_argument("--no-parallel-librarian-verifier", dest="parallel_librarian_verifier", action="store_false")
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

    p_patch = sub.add_parser("apply-patch", help="apply a structured Albilich v1 patch JSON file")
    p_patch.add_argument("problem")
    p_patch.add_argument("patch_json")

    p_report = sub.add_parser("report", help="write or print a markdown report")
    p_report.add_argument("problem")
    p_report.add_argument("--write", action="store_true")

    p_console = sub.add_parser("console", help="write or print the consolidated Albilich run console")
    p_console.add_argument("problem")
    p_console.add_argument("--write", action="store_true")

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
        _print(
            store.init_problem(
                root_statement,
                total_token_budget=args.total_token_budget,
                reserved_verification_budget=args.reserved_verification_budget,
                max_reduction_depth=args.max_reduction_depth,
            )
        )
        return

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

    if args.command == "status":
        payload = compute_metrics(store)
        payload["result_status"] = classify_result(store)
        _print(payload)
    elif args.command == "check":
        with store.connect() as conn:
            errors = validate_conn(conn)
        _print({"ok": not errors, "errors": errors})
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
            stop_on_rejection=args.stop_on_rejection,
            session_resume=args.session_resume,
            write_on_stop=args.write_on_stop,
            write_report=args.write_report,
            write_console=args.write_console,
            executor=_executor_for(args),
        )
        if dashboard:
            result["dashboard"] = dashboard
        _print(result)
    elif args.command == "attempt":
        _apply_cas_assets(args)
        dashboard, _dashboard_handle = _maybe_start_run_dashboard(args, store)
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
            stop_on_rejection=args.stop_on_rejection,
            session_resume=args.session_resume,
            write_on_stop=args.write_on_stop,
            write_report=args.write_report,
            write_console=args.write_console,
            executor=_executor_for(args),
        )
        if dashboard:
            result["dashboard"] = dashboard
        _print(result)
    elif args.command == "apply-patch":
        patch = json.loads(Path(args.patch_json).read_text(encoding="utf-8"))
        _print(apply_patch(store, patch).to_dict())
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
        help="Claude Code --permission-mode for executed sessions (default bypassPermissions so CAS/file tool calls run headlessly)",
    )
    parser.add_argument("--claude-max-turns", type=int, default=None, help="optional Claude Code --max-turns cap per session")
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
    except Exception as exc:
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
    """Expose --cas-asset paths to context_builder via the environment."""
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
    return path.read_text(encoding="utf-8").strip()


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
    except Exception:
        pass
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
        store.init_problem(_read_root_statement(problem), **kwargs)


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
