from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

from .executable_attestation import attest_executable, attested_executable_unchanged
from .sandbox_runtime import SANDBOX_NPROC_LIMIT, append_runtime_mounts, sandbox_runtime_mounts


MAX_PROGRAM_BYTES = 200_000
MAX_CAPTURE_BYTES = 2_000_000
MAX_TIMEOUT_SECONDS = 60
REPRODUCTION_REPEATS = 2


def reproduce_computation(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    """Rerun a bounded computation without network or repository access."""

    request = metadata.get("reproduction_request")
    if not isinstance(request, Mapping):
        return {"status": "missing_request", "reproduced": False}
    kind = str(request.get("kind") or "program").strip().lower()
    if kind == "manual":
        return {
            "status": "not_applicable_manual_calculation",
            "reproduced": False,
            "proof_authority": False,
        }
    language = str(request.get("language") or "").strip().lower()
    program = str(request.get("program") or metadata.get("code_or_calculation") or "")
    expected = str(request.get("observed_stdout_sha256") or "").strip().lower()
    deterministic = request.get("deterministic") is True
    try:
        timeout = min(MAX_TIMEOUT_SECONDS, max(1, int(request.get("timeout_seconds") or 30)))
    except (TypeError, ValueError):
        timeout = 30
    errors: list[str] = []
    if language not in {"python", "julia", "macaulay2"}:
        errors.append("reproduction_request.language must be python, julia, or macaulay2")
    if not program.strip():
        errors.append("reproduction_request.program must be nonempty")
    if len(program.encode("utf-8")) > MAX_PROGRAM_BYTES:
        errors.append(f"reproduction program exceeds {MAX_PROGRAM_BYTES} bytes")
    if not deterministic:
        errors.append("reproduction_request.deterministic must be true")
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        errors.append("reproduction_request.observed_stdout_sha256 must be a SHA-256 digest")
    if errors:
        return {"status": "invalid_request", "reproduced": False, "errors": errors}

    backend = _backend_command(language)
    if not backend:
        return {
            "status": "backend_unavailable",
            "reproduced": False,
            "language": language,
        }
    bwrap = shutil.which("bwrap")
    prlimit = shutil.which("prlimit")
    if not bwrap or not prlimit:
        return {
            "status": "sandbox_unavailable",
            "reproduced": False,
            "language": language,
        }

    backend_command, version_args, minimum_version, maximum_version = backend
    attestation = attest_executable(
        backend_command[0],
        version_args=version_args,
        minimum_version=minimum_version,
        maximum_version=maximum_version,
    )
    if not attestation["valid"]:
        return {
            "status": "backend_attestation_failed",
            "reproduced": False,
            "proof_authority": False,
            "language": language,
            "executable_attestation": attestation,
        }
    backend_command[0] = str(attestation["executable_path"])
    try:
        runtime_mounts, sandbox_executable, runtime_root = sandbox_runtime_mounts(
            backend_command[0]
        )
    except OSError as exc:
        return {
            "status": "backend_mount_failed",
            "reproduced": False,
            "proof_authority": False,
            "language": language,
            "error": str(exc),
            "executable_attestation": attestation,
        }
    backend_command[0] = sandbox_executable

    command = [
        prlimit,
        "--as=1073741824",
        "--cpu=60",
        # Counted across the host uid until bubblewrap creates its PID
        # namespace; lower values can prevent the sandbox itself from starting
        # on shared runners.
        f"--nproc={SANDBOX_NPROC_LIMIT}",
        "--fsize=4194304",
        "--",
        bwrap,
        "--die-with-parent",
        "--new-session",
        "--unshare-net",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-pid",
        "--clearenv",
        "--setenv",
        "HOME",
        "/tmp",
        "--setenv",
        "PATH",
        "/usr/bin:/bin",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/work",
        "--chdir",
        "/work",
    ]
    for directory in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
        if Path(directory).exists():
            command.extend(["--ro-bind", directory, directory])
    append_runtime_mounts(command, runtime_mounts)
    command.extend(["--", *backend_command])

    run_records: list[dict[str, Any]] = []
    stdout = b""
    stderr = b""
    for _ in range(REPRODUCTION_REPEATS):
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                completed = subprocess.run(
                    command,
                    input=program.encode("utf-8"),
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=timeout,
                    check=False,
                    env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                )
                timed_out = False
                returncode = int(completed.returncode)
            except subprocess.TimeoutExpired:
                timed_out = True
                returncode = -1
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read(MAX_CAPTURE_BYTES + 1)
            stderr = stderr_file.read(MAX_CAPTURE_BYTES + 1)
        run_records.append(
            {
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                "returncode": returncode,
                "timed_out": timed_out,
                "output_truncated": len(stdout) > MAX_CAPTURE_BYTES
                or len(stderr) > MAX_CAPTURE_BYTES,
            }
        )

    actual = str(run_records[0]["stdout_sha256"])
    program_sha = hashlib.sha256(program.encode("utf-8")).hexdigest()
    output_truncated = any(bool(row["output_truncated"]) for row in run_records)
    timed_out = any(bool(row["timed_out"]) for row in run_records)
    returncode = int(run_records[-1]["returncode"])
    stable_stdout = len(
        {str(row["stdout_sha256"]) for row in run_records}
    ) == 1
    stable_stderr = len(
        {str(row["stderr_sha256"]) for row in run_records}
    ) == 1
    all_runs_succeeded = all(
        int(row["returncode"]) == 0
        and not bool(row["timed_out"])
        and not bool(row["output_truncated"])
        for row in run_records
    )
    stable_runs = stable_stdout and stable_stderr and all_runs_succeeded
    executable_unchanged = attested_executable_unchanged(attestation)
    reproduced = bool(
        all_runs_succeeded
        and actual == expected
        and stable_runs
        and executable_unchanged
    )
    return {
        "status": "reproduced" if reproduced else "mismatch",
        "reproduced": reproduced,
        "proof_authority": False,
        "language": language,
        "backend_executable": attestation["executable_path"],
        "sandbox_runtime_root": runtime_root,
        "executable_attestation": attestation,
        "program_sha256": program_sha,
        "expected_stdout_sha256": expected,
        "actual_stdout_sha256": actual,
        "reproduction_repeats": REPRODUCTION_REPEATS,
        "stable_across_repeats": stable_runs,
        "stable_stdout_across_repeats": stable_stdout,
        "stable_stderr_across_repeats": stable_stderr,
        "all_runs_succeeded": all_runs_succeeded,
        "run_records": run_records,
        "returncode": returncode,
        "timed_out": timed_out,
        "output_truncated": output_truncated,
        "executable_unchanged_after_run": executable_unchanged,
        "stderr_excerpt": stderr[:4_000].decode("utf-8", errors="replace"),
    }


def _backend_command(
    language: str,
) -> tuple[list[str], list[str], tuple[int, ...], tuple[int, ...]] | None:
    if language == "python":
        executable = shutil.which("python3")
        return (
            [executable, "-I", "-S", "-"],
            ["--version"],
            (3, 10),
            (3, 14, 99),
        ) if executable else None
    if language == "julia":
        executable = shutil.which("julia")
        return (
            [executable, "--startup-file=no", "--history-file=no", "--project=@stdlib", "-"],
            ["--version"],
            (1, 6),
            (1, 12, 99),
        ) if executable else None
    if language == "macaulay2":
        executable = shutil.which("M2")
        return (
            [executable, "--script", "/dev/stdin"],
            ["--version"],
            (1, 20),
            (1, 26, 99),
        ) if executable else None
    return None
