"""Claude Code CLI backend for Albilich v1 sessions.

This mirrors :mod:`codex_runner` but drives the ``claude`` command instead of
``codex``. It produces an execution dict with exactly the same shape as
:func:`codex_runner.execute_session`, so it can be passed to
``run_workflow(..., executor=...)`` as a drop-in backend.

The context manifest, session prompt, patch extraction, actor-role routing, and
run-metrics recording are all backend-agnostic and reused directly from
``codex_runner``. The only Claude-specific logic here is command construction
and parsing the ``--output-format json`` envelope.
"""

from __future__ import annotations

import json
import os
import pty
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .codex_runner import (
    DEFAULT_CHILD_TIMEOUT_SECONDS,
    DEFAULT_PROGRESS_INTERVAL_SECONDS,
    ProgressCallback,
    _join_log_samples,
    _process_tree_rss_mb,
    _progress_interval_seconds,
    _read_text_head,
    _read_text_tail,
    _run_id,
    _terminate_process,
    actor_role_for_action,
    attached_artifact_ids,
    build_session_prompt,
    extract_patch_from_text,
    _persist_normalized_final_patch,
)
from .models import utc_now
from .patches import preflight_patch_errors
from .role_capabilities import role_can_use_cas, session_cas_enabled
from .store import ProofStateStore

# "opus" is the high-reasoning alias the Claude Code CLI resolves to the current
# Opus model; it is the right default for hard proof construction and strict
# verification. Override with --model on the CLI when a cheaper tier is wanted.
DEFAULT_CLAUDE_MODEL = "opus"
# Headless math research needs to read manifests/sources and run CAS (M2) via
# tool calls with no interactive approval prompt, so the runner defaults to
# bypassing permission checks. Narrow this with --claude-permission-mode.
DEFAULT_CLAUDE_PERMISSION_MODE = "bypassPermissions"


def build_claude_command(
    *,
    prompt: str,
    claude_bin: str = "claude",
    model: str | None = None,
    permission_mode: str | None = DEFAULT_CLAUDE_PERMISSION_MODE,
    output_format: str = "stream-json",
    max_turns: int | None = None,
    effort: str | None = None,
    add_dirs: Sequence[Path | str] | None = None,
    allowed_tools: Sequence[str] | None = None,
    disallowed_tools: Sequence[str] | None = None,
    include_partial_messages: bool = False,
    extra_args: Sequence[str] | None = None,
    resume_session_id: str | None = None,
) -> list[str]:
    """Build a scoped Claude Code command for one Albilich v1 session.

    When ``resume_session_id`` is set, continue that prior session (``--resume``) so the
    same agent keeps its already-read artifacts in context instead of cold-starting.
    """
    argv: list[str] = [claude_bin, "-p"]
    if resume_session_id:
        argv.extend(["--resume", resume_session_id])
    if output_format:
        argv.extend(["--output-format", output_format])
        # stream-json with --print requires --verbose; it also lets us salvage
        # the last assistant message if the session is killed at the timeout.
        if output_format == "stream-json":
            argv.append("--verbose")
            # Partial messages flush incremental output to the log so the live
            # monitor sees movement during a long step instead of one final blob.
            if include_partial_messages:
                argv.append("--include-partial-messages")
    if model:
        argv.extend(["--model", model])
    if effort:
        argv.extend(["--effort", effort])
    if permission_mode:
        argv.extend(["--permission-mode", permission_mode])
    if max_turns is not None:
        argv.extend(["--max-turns", str(max_turns)])
    for directory in add_dirs or []:
        argv.extend(["--add-dir", str(directory)])
    # Tool lists are passed as one comma-joined value: the CLI flags are
    # variadic, so separate tokens would swallow extra_args and the trailing
    # positional prompt.
    if allowed_tools:
        argv.extend(["--allowedTools", ",".join(allowed_tools)])
    if disallowed_tools:
        argv.extend(["--disallowedTools", ",".join(disallowed_tools)])
    argv.extend(extra_args or [])
    # Prompt is the trailing positional argument.
    argv.append(prompt)
    return argv


def _claude_usage(envelope: Mapping[str, Any]) -> Dict[str, int]:
    """Map a Claude Code result envelope's usage to the Albilich usage shape.

    Codex semantics treat ``input_tokens`` as the full prompt-side count with
    ``cached_input_tokens`` a subset of it. Claude reports the *uncached* new
    input separately from cache reads/creates, so we sum them back together to
    keep budget accounting honest and consistent across backends.
    """
    raw = envelope.get("usage")
    if not isinstance(raw, Mapping):
        return {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
            "total_tokens": 0,
        }

    def _int(key: str) -> int:
        try:
            return int(raw.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    new_input = _int("input_tokens")
    cache_read = _int("cache_read_input_tokens")
    cache_create = _int("cache_creation_input_tokens")
    output_tokens = _int("output_tokens")
    full_input = new_input + cache_read + cache_create
    return {
        "input_tokens": full_input,
        # Only cache *reads* are the cheap, reused portion. Cache *creation* is
        # billed near full price, so it counts as new work for the budget.
        "cached_input_tokens": cache_read,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": 0,
        "total_tokens": full_input + output_tokens,
    }


def parse_claude_envelope(text: str) -> Dict[str, Any]:
    """Extract the single ``type=result`` JSON object from Claude stdout."""
    stripped = text.strip()
    if not stripped:
        return {}
    # The common case: stdout is exactly one JSON object.
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Fallback: scan lines from the end for a result object (stream-json or
    # interleaved stderr).
    for line in reversed(stripped.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "result":
            return obj
        if isinstance(obj, dict) and "result" in obj:
            return obj
    return {}


def stream_activity_tail(text: str, *, max_lines: int = 30) -> str:
    """Render a human-readable activity tail from Claude stream-json events.

    Turns the raw event log into lines like ``⏵ Bash: M2 …`` (tool calls) and
    assistant prose snippets, so the live monitor shows what the agent is doing
    rather than raw JSON.
    """
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        etype = event.get("type")
        if etype == "assistant":
            message = event.get("message")
            blocks = message.get("content") if isinstance(message, dict) else None
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and str(block.get("text") or "").strip():
                    lines.append(str(block["text"]).strip())
                elif block.get("type") == "tool_use":
                    name = block.get("name") or "tool"
                    inp = block.get("input")
                    detail = ""
                    if isinstance(inp, dict):
                        detail = str(inp.get("command") or inp.get("file_path") or inp.get("description") or inp.get("query") or "")
                    lines.append(f"⏵ {name}: {detail}".strip()[:200])
        elif etype == "result":
            lines.append("✓ session result emitted")
    return "\n".join(lines[-max_lines:])[-4000:]


def latest_stream_usage(text: str) -> Dict[str, int]:
    """Best-effort in-flight token usage from a partial Claude stream.

    Scans the event log for the most token-heavy ``usage`` object (assistant
    message, message_delta, or result), so the monitor can show tokens climbing
    while a step is still running. Requires unbuffered (PTY) streaming to be
    meaningful mid-step.
    """
    best = _claude_usage({})
    best_total = -1
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        candidates = [event.get("usage")]
        message = event.get("message")
        if isinstance(message, dict):
            candidates.append(message.get("usage"))
        inner = event.get("event")
        if isinstance(inner, dict):
            candidates.append(inner.get("usage"))
            inner_msg = inner.get("message")
            if isinstance(inner_msg, dict):
                candidates.append(inner_msg.get("usage"))
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            usage = _claude_usage({"usage": cand})
            if usage["total_tokens"] > best_total:
                best, best_total = usage, usage["total_tokens"]
    return best


def _spawn_pty_session(
    command: list[str],
    *,
    cwd: Path,
    raw_path: Path,
    log_file: Any,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.Popen[bytes], threading.Thread]:
    """Spawn Claude with stdout on a PTY so it streams line-buffered.

    Claude buffers stdout to a non-TTY until process exit, which kills live
    streaming, in-flight token counts, and timeout salvage. A pseudo-terminal
    makes it flush incrementally. A reader thread copies the master side to
    ``raw_path`` as events arrive, so the file is live and present at kill time.
    stdin is DEVNULL so Claude never waits on terminal input.
    """
    master_fd, slave_fd = pty.openpty()
    try:
        process = subprocess.Popen(  # type: ignore[call-overload]
            command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=slave_fd,
            stderr=log_file,
            close_fds=True,
            env=env,
            start_new_session=True,
        )
    finally:
        os.close(slave_fd)

    def _pump() -> None:
        with raw_path.open("wb") as out:
            while True:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                out.write(chunk)
                out.flush()
        try:
            os.close(master_fd)
        except OSError:
            pass

    reader = threading.Thread(target=_pump, daemon=True)
    reader.start()
    return process, reader


def parse_stream_events(text: str) -> Dict[str, Any]:
    """Parse Claude ``stream-json`` output, salvaging the final patch.

    Returns ``{result, session_id, usage, is_error}``. The final patch text is
    taken from the terminal ``result`` event when present; otherwise it falls
    back to the text blocks of the last ``assistant`` message, so a session that
    is killed at the timeout before emitting its result event still yields the
    work it had already produced.
    """
    result_text = ""
    last_assistant = ""
    session_id = ""
    usage_event: Dict[str, Any] | None = None
    is_error = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if isinstance(event.get("session_id"), str) and event["session_id"]:
            session_id = event["session_id"]
        etype = event.get("type")
        if etype == "assistant":
            message = event.get("message")
            blocks = message.get("content") if isinstance(message, dict) else None
            if isinstance(blocks, list):
                texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
                joined = "".join(texts).strip()
                if joined:
                    last_assistant = joined
        elif etype == "result":
            if isinstance(event.get("result"), str) and event["result"].strip():
                result_text = event["result"]
            if isinstance(event.get("usage"), dict):
                usage_event = event
            is_error = bool(event.get("is_error"))
    return {
        "result": result_text or last_assistant,
        "session_id": session_id,
        "usage": _claude_usage(usage_event or {}),
        "is_error": is_error,
    }


def execute_claude_session(
    store: ProofStateStore,
    action: Mapping[str, Any],
    session_plan: Mapping[str, Any],
    *,
    model: str = DEFAULT_CLAUDE_MODEL,
    claude_bin: str = "claude",
    permission_mode: str = DEFAULT_CLAUDE_PERMISSION_MODE,
    max_turns: int | None = None,
    effort: str | None = None,
    timeout_sec: int = DEFAULT_CHILD_TIMEOUT_SECONDS,
    claude_workdir: Path | None = None,
    extra_args: Sequence[str] | None = None,
    progress_callback: ProgressCallback | None = None,
    stop_event: threading.Event | None = None,
) -> Dict[str, Any]:
    """Run one Albilich v1 session through the Claude Code CLI.

    Returns the same execution dict shape as ``codex_runner.execute_session``.
    """
    actor_role = str(session_plan.get("actor_role") or actor_role_for_action(action))
    mode = str(action.get("mode") or "step")
    target_id = str(action.get("target_id") or "root")
    run_id = _run_id(mode, target_id)
    run_dir = store.state_dir / "workflow_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    final_path = run_dir / "final_patch.json"
    raw_path = run_dir / "claude_output.jsonl"
    log_path = run_dir / "claude.log"
    context_path = Path(str(session_plan["context_path"]))
    workdir = claude_workdir or store.generation_root.parents[1]
    resume_session_id = str(session_plan.get("resume_session_id") or "")
    prompt = build_session_prompt(context_path=context_path, action=action, actor_role=actor_role, resume=bool(resume_session_id))
    # Enforce the per-action web policy computed by the workflow: sessions not
    # granted live search have the web tools denied instead of silently keeping
    # them (the Claude CLI has no web_search config toggle like Codex).
    session_web_search = str(session_plan.get("web_search") or "disabled")
    command = build_claude_command(
        prompt=prompt,
        claude_bin=claude_bin,
        resume_session_id=resume_session_id or None,
        model=model,
        permission_mode=permission_mode,
        output_format="stream-json",
        max_turns=max_turns,
        effort=effort,
        # Do NOT pass --add-dir for the repo root: Claude indexes the whole tree
        # at startup, and this repo has ~28k files (.venv, results/, experiment
        # data/), which stalls every session past its timeout with zero output.
        # cwd=workdir already grants read access to everything under the repo.
        add_dirs=None,
        disallowed_tools=None if session_web_search == "live" else ("WebSearch", "WebFetch"),
        include_partial_messages=True,
        extra_args=extra_args,
    )

    started = time.monotonic()
    returncode = -1
    status = "failed"
    failure_kind = ""
    process: subprocess.Popen[bytes] | None = None
    reader: threading.Thread | None = None
    peak_memory_mb = 0.0

    def sample_peak_memory_mb() -> float:
        nonlocal peak_memory_mb
        if process is not None:
            peak_memory_mb = max(peak_memory_mb, _process_tree_rss_mb(process.pid))
        return peak_memory_mb

    def emit_progress(phase: str, *, progress_status: str = "running", current_returncode: int | str = "") -> None:
        if progress_callback is None:
            return
        # Live activity + in-flight usage come from the streamed event log (stdout).
        tail = _read_text_tail(raw_path, max_bytes=48_000)
        activity = stream_activity_tail(tail)
        if not activity:
            activity = _read_text_tail(log_path, max_bytes=4_000).strip()[-4_000:]
        payload = {
            "run_id": run_id,
            "actor_role": actor_role,
            "mode": mode,
            "target_id": target_id,
            "route_id": str(action.get("route_id") or ""),
            "researcher_work_mode": str(action.get("researcher_work_mode") or ""),
            "phase": phase,
            "status": progress_status,
            "returncode": current_returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "peak_memory_mb": round(sample_peak_memory_mb(), 1),
            "updated_at": utc_now(),
            "context_path": str(context_path),
            "log_path": str(log_path),
            "final_message_path": str(final_path),
            "log_tail": activity,
            "usage": latest_stream_usage(tail),
        }
        try:
            progress_callback(payload)
        except Exception:
            pass

    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            if stop_event is not None and stop_event.is_set():
                status = "cancelled"
                log_file.write("[albilich] claude session cancelled before launch.\n")
                emit_progress("cancelled", progress_status=status, current_returncode=returncode)
            else:
                process, reader = _spawn_pty_session(
                    command,
                    cwd=workdir,
                    raw_path=raw_path,
                    log_file=log_file,
                    env=_claude_child_env(actor_role, cas_enabled=session_cas_enabled(actor_role, action)),
                )
                emit_progress("started")
                deadline = time.monotonic() + max(1, timeout_sec)
                progress_interval = _progress_interval_seconds() if progress_callback else DEFAULT_PROGRESS_INTERVAL_SECONDS
                while True:
                    if stop_event is not None and stop_event.is_set():
                        status = "cancelled"
                        failure_kind = "cancelled"
                        _terminate_process(process)
                        returncode = process.returncode if process.returncode is not None else -1
                        log_file.write("\n[albilich] claude session cancelled and was terminated.\n")
                        emit_progress("cancelled", progress_status=status, current_returncode=returncode)
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        status = "timeout"
                        failure_kind = "deadline"
                        _terminate_process(process)
                        returncode = process.returncode if process.returncode is not None else -1
                        log_file.write("\n[albilich] claude session timed out and was terminated.\n")
                        emit_progress("timeout", progress_status=status, current_returncode=returncode)
                        break
                    try:
                        wait_timeout = min(progress_interval, remaining)
                        if stop_event is not None:
                            wait_timeout = min(wait_timeout, 1.0)
                        returncode = process.wait(timeout=wait_timeout)
                        status = "completed" if returncode == 0 else "failed"
                        emit_progress("completed", progress_status=status, current_returncode=returncode)
                        break
                    except subprocess.TimeoutExpired:
                        emit_progress("heartbeat")
    except OSError as exc:
        log_path.write_text(f"[albilich] failed to launch Claude session: {exc}\n", encoding="utf-8")
        emit_progress("failed_to_launch", progress_status="failed", current_returncode=returncode)
    except BaseException:
        if process is not None and process.poll() is None:
            _terminate_process(process)
            returncode = process.returncode if process.returncode is not None else -1
            try:
                with log_path.open("a", encoding="utf-8") as log_file:
                    log_file.write("\n[albilich] claude session interrupted and was terminated.\n")
            except OSError:
                pass
            emit_progress("interrupted", progress_status="cancelled", current_returncode=returncode)
        raise
    finally:
        if reader is not None:
            reader.join(timeout=5)
    wall = time.monotonic() - started
    sample_peak_memory_mb()

    # Tail captures the terminal result event; head keeps the session/init line.
    parsed = parse_stream_events(_read_text_head(raw_path) + "\n" + _read_text_tail(raw_path))
    result_text = str(parsed.get("result") or "")
    if result_text:
        final_path.write_text(result_text, encoding="utf-8")
    patch, patch_error = extract_patch_from_text(result_text) if result_text else (None, "empty claude result")
    _persist_normalized_final_patch(final_path, result_text, patch)
    session_id = str(parsed.get("session_id") or "")
    usage = parsed.get("usage") or _claude_usage({})
    if not usage.get("total_tokens"):
        # A killed session (timeout/cancel) never emits the terminal result
        # event; salvage in-flight usage from the streamed events so budget
        # accounting does not undercount deep steps.
        salvaged = latest_stream_usage(_read_text_tail(raw_path, max_bytes=96_000))
        if isinstance(salvaged, Mapping) and salvaged.get("total_tokens"):
            usage = dict(salvaged)
    if parsed.get("is_error") and status == "completed":
        status = "failed"
        if not patch_error:
            patch_error = "claude reported is_error"
    preflight_repair: dict[str, Any] = {}
    if patch is not None and status == "completed":
        preflight_errors = preflight_patch_errors(patch, actor_role)
        if preflight_errors:
            # Detection only on the claude backend (no in-session repair yet):
            # surface the violations so the console explains the coming rejection.
            preflight_repair = {"attempted": False, "errors_before": preflight_errors}
    output_artifact_ids = attached_artifact_ids(patch) if patch else []
    if patch is None and status == "completed":
        status = "no_patch"
    return {
        "preflight_repair": preflight_repair,
        "run_id": run_id,
        "actor_role": actor_role,
        "status": status,
        "returncode": returncode,
        "wall_time_seconds": round(wall, 3),
        "peak_memory_mb": round(peak_memory_mb, 1),
        "usage": usage,
        "session_id": session_id,
        "patch": patch,
        "patch_error": patch_error,
        "output_artifact_ids": output_artifact_ids,
        "final_message_path": str(final_path),
        "log_path": str(log_path),
        "command": command,
        "model": model,
        "reasoning_effort": effort or "",
        "sandbox": permission_mode,
        "web_search": session_web_search,
        "failure_kind": failure_kind,
    }


def _claude_child_env(actor_role: str, cas_enabled: bool | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["ALBILICH_CAS_ROLE"] = actor_role
    if cas_enabled is None:
        cas_enabled = role_can_use_cas(actor_role)
    env["ALBILICH_CAS_ENABLED"] = "1" if cas_enabled else "0"
    return env


def make_claude_executor(
    *,
    model: str = DEFAULT_CLAUDE_MODEL,
    claude_bin: str = "claude",
    permission_mode: str = DEFAULT_CLAUDE_PERMISSION_MODE,
    max_turns: int | None = None,
    effort: str | None = None,
    timeout_sec: int = DEFAULT_CHILD_TIMEOUT_SECONDS,
    extra_args: Sequence[str] | None = None,
):
    """Return an ``executor(store, action, session_plan)`` for ``run_workflow``."""

    def executor(
        *,
        store: ProofStateStore,
        action: Mapping[str, Any],
        session_plan: Mapping[str, Any],
        progress_callback: ProgressCallback | None = None,
        stop_event: threading.Event | None = None,
    ) -> Dict[str, Any]:
        return execute_claude_session(
            store,
            action,
            session_plan,
            model=model,
            claude_bin=claude_bin,
            permission_mode=permission_mode,
            max_turns=max_turns,
            effort=effort,
            timeout_sec=timeout_sec,
            extra_args=extra_args,
            progress_callback=progress_callback,
            stop_event=stop_event,
        )

    return executor
