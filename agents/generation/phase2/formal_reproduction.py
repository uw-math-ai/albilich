from __future__ import annotations

import hashlib
import os
import re
import secrets
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

from .executable_attestation import (
    attest_executable,
    attest_executable_identity,
    attested_executable_unchanged,
)
from .sandbox_runtime import SANDBOX_NPROC_LIMIT, append_runtime_mounts, sandbox_runtime_mounts


MAX_FORMAL_SOURCE_BYTES = 1_000_000
MAX_CAPTURE_BYTES = 2_000_000
MAX_TIMEOUT_SECONDS = 120
TRUSTED_LEAN_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})
FORBIDDEN_LEAN_AXIOMS = frozenset({"sorryAx"})


def check_formal_artifact(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    """Run an allowlisted proof checker in a networkless filesystem sandbox."""

    request = metadata.get("formal_check_request")
    if not isinstance(request, Mapping):
        return {"status": "missing_request", "host_checked": False}
    backend = str(request.get("backend") or "").strip().lower()
    source = str(request.get("source") or "")
    target_declaration = str(request.get("target_declaration") or "").strip()
    raw_allowed_axioms = request.get("allowed_axioms")
    allowed_axioms = (
        sorted({str(item).strip() for item in raw_allowed_axioms if str(item).strip()})
        if isinstance(raw_allowed_axioms, list)
        else []
    )
    try:
        timeout = min(MAX_TIMEOUT_SECONDS, max(1, int(request.get("timeout_seconds") or 60)))
    except (TypeError, ValueError):
        timeout = 60
    suffix_and_command = _backend_command(backend)
    errors: list[str] = []
    if backend not in {"lean4", "rocq", "coq", "agda"}:
        errors.append("formal_check_request.backend must be lean4, rocq, coq, or agda")
    if not source.strip():
        errors.append("formal_check_request.source must contain the complete checked source")
    if len(source.encode("utf-8")) > MAX_FORMAL_SOURCE_BYTES:
        errors.append(f"formal source exceeds {MAX_FORMAL_SOURCE_BYTES} bytes")
    if not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*",
        target_declaration,
    ):
        errors.append(
            "formal_check_request.target_declaration must be a qualified ASCII identifier"
        )
    if not isinstance(raw_allowed_axioms, list) or any(
        not isinstance(item, str) or not item.strip() for item in raw_allowed_axioms or []
    ):
        errors.append("formal_check_request.allowed_axioms must be a list of nonempty names")
    elif backend == "lean4":
        invalid_axiom_names = [
            name
            for name in allowed_axioms
            if not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*",
                name,
            )
        ]
        unsupported_axioms = sorted(set(allowed_axioms) - TRUSTED_LEAN_AXIOMS)
        if invalid_axiom_names:
            errors.append(
                "Lean allowed_axioms contains a syntactically invalid declaration name"
            )
        if unsupported_axioms:
            errors.append(
                "Lean certification permits only the standard logical axioms "
                "propext, Classical.choice, and Quot.sound; unsupported: "
                + ", ".join(unsupported_axioms)
            )
        errors.extend(_lean_source_policy_errors(source))
    if backend in {"rocq", "coq", "agda"} and allowed_axioms:
        errors.append(
            f"{backend} certification currently requires allowed_axioms=[]"
        )
    if backend == "agda" and target_declaration and not _agda_declares_target(
        source, target_declaration
    ):
        errors.append(
            "Agda source does not contain a declaration signature for target_declaration"
        )
    if errors:
        return {"status": "invalid_request", "host_checked": False, "errors": errors}
    if not suffix_and_command:
        return {"status": "backend_unavailable", "host_checked": False, "backend": backend}
    bwrap = shutil.which("bwrap")
    prlimit = shutil.which("prlimit")
    if not bwrap or not prlimit:
        return {"status": "sandbox_unavailable", "host_checked": False, "backend": backend}

    suffix, checker, version_args, minimum_version, maximum_version, canonical_backend = suffix_and_command
    attestation = attest_executable(
        checker[0],
        version_args=version_args,
        minimum_version=minimum_version,
        maximum_version=maximum_version,
    )
    if not attestation["valid"]:
        return {
            "status": "backend_attestation_failed",
            "host_checked": False,
            "backend": canonical_backend,
            "executable_attestation": attestation,
        }
    checker[0] = str(attestation["executable_path"])
    try:
        runtime_mounts, sandbox_executable, runtime_root = sandbox_runtime_mounts(
            checker[0]
        )
    except OSError as exc:
        return {
            "status": "backend_mount_failed",
            "host_checked": False,
            "backend": canonical_backend,
            "error": str(exc),
            "executable_attestation": attestation,
        }
    checker[0] = sandbox_executable
    independent_checker_attestation: Dict[str, Any] = {}
    independent_checker_mounts: list[str] = []
    independent_checker_command = ""
    if canonical_backend == "lean4":
        companion_path = Path(str(attestation["executable_path"])).with_name(
            "lean4checker"
        )
        independent_checker_attestation = attest_executable_identity(
            str(companion_path)
        )
        if not independent_checker_attestation.get("valid"):
            return {
                "status": "independent_checker_unavailable",
                "host_checked": False,
                "backend": canonical_backend,
                "executable_attestation": attestation,
                "independent_checker_attestation": independent_checker_attestation,
            }
        try:
            (
                independent_checker_mounts,
                independent_checker_command,
                _independent_runtime_root,
            ) = sandbox_runtime_mounts(
                str(independent_checker_attestation["executable_path"]),
                mount_target="/albilich-lean4checker",
            )
        except OSError as exc:
            return {
                "status": "independent_checker_mount_failed",
                "host_checked": False,
                "backend": canonical_backend,
                "error": str(exc),
                "executable_attestation": attestation,
                "independent_checker_attestation": independent_checker_attestation,
            }
    assumption_audit_marker = (
        secrets.token_hex(16)
        if canonical_backend in {"lean4", "rocq"}
        else ""
    )
    checked_source = _source_with_assumption_audit(
        canonical_backend,
        source,
        target_declaration=target_declaration,
        audit_marker=assumption_audit_marker,
    )
    with tempfile.TemporaryDirectory(prefix="albilich-formal-") as temporary_dir:
        source_path = Path(temporary_dir) / f"Main{suffix}"
        source_path.write_text(checked_source, encoding="utf-8")
        command = [
            prlimit,
            "--as=2147483648",
            "--cpu=120",
            f"--nproc={SANDBOX_NPROC_LIMIT}",
            "--fsize=8388608",
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
            "--ro-bind",
            str(source_path),
            f"/work/Main{suffix}",
            "--chdir",
            "/work",
        ]
        for directory in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
            if Path(directory).exists():
                command.extend(["--ro-bind", directory, directory])
        append_runtime_mounts(command, runtime_mounts)
        if independent_checker_mounts != runtime_mounts:
            append_runtime_mounts(command, independent_checker_mounts)
        if canonical_backend == "lean4":
            lean_command = [
                *checker,
                "-o",
                "/work/Main.olean",
                f"/work/Main{suffix}",
            ]
            kernel_command = [independent_checker_command, "/work/Main.olean"]
            command.extend(
                [
                    "--",
                    "/bin/sh",
                    "-c",
                    shlex.join(lean_command)
                    + " && "
                    + shlex.join(kernel_command),
                ]
            )
        else:
            command.extend(["--", *checker, f"/work/Main{suffix}"])
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                completed = subprocess.run(
                    command,
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

    output_truncated = len(stdout) > MAX_CAPTURE_BYTES or len(stderr) > MAX_CAPTURE_BYTES
    independent_checker_unchanged = bool(
        not independent_checker_attestation
        or attested_executable_unchanged(independent_checker_attestation)
    )
    executable_unchanged = bool(
        attested_executable_unchanged(attestation)
        and independent_checker_unchanged
    )
    assumption_audit = _audit_assumptions(
        canonical_backend,
        (stdout + b"\n" + stderr).decode("utf-8", errors="replace"),
        allowed_axioms=allowed_axioms,
        audit_marker=assumption_audit_marker,
    )
    host_checked = bool(
        returncode == 0
        and not timed_out
        and not output_truncated
        and executable_unchanged
        and assumption_audit["verified"]
    )
    status = "checked" if host_checked else "checker_failed"
    if (
        returncode == 0
        and not timed_out
        and not output_truncated
        and executable_unchanged
        and not assumption_audit["verified"]
    ):
        status = "assumption_audit_failed"
    return {
        "status": status,
        "host_checked": host_checked,
        "backend": canonical_backend,
        "checker_executable": attestation["executable_path"],
        "sandbox_runtime_root": runtime_root,
        "executable_attestation": attestation,
        "independent_checker_attestation": independent_checker_attestation,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "checked_source_sha256": hashlib.sha256(
            checked_source.encode("utf-8")
        ).hexdigest(),
        "target_declaration": target_declaration,
        "assumption_audit": assumption_audit,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "returncode": returncode,
        "timed_out": timed_out,
        "output_truncated": output_truncated,
        "executable_unchanged_after_check": executable_unchanged,
        "independent_checker_unchanged_after_check": independent_checker_unchanged,
        "stdout_excerpt": stdout[:4_000].decode("utf-8", errors="replace"),
        "stderr_excerpt": stderr[:4_000].decode("utf-8", errors="replace"),
    }


def _backend_command(
    backend: str,
) -> tuple[str, list[str], list[str], tuple[int, ...], tuple[int, ...], str] | None:
    if backend == "lean4":
        executable = shutil.which("lean")
        return (
            ".lean",
            [executable, "-DwarningAsError=true"],
            ["--version"],
            (4, 0),
            (4, 33, 99),
            "lean4",
        ) if executable else None
    if backend in {"rocq", "coq"}:
        executable = shutil.which("rocq")
        if executable:
            return (
                ".v",
                [executable, "compile", "-q"],
                ["--version"],
                (9, 0),
                (9, 2, 99),
                "rocq",
            )
        executable = shutil.which("coqc")
        return (
            ".v",
            [executable, "-q"],
            ["--version"],
            (8, 0),
            (8, 20, 99),
            "rocq",
        ) if executable else None
    if backend == "agda":
        executable = shutil.which("agda")
        return (
            ".agda",
            [executable, "--no-libraries", "--safe"],
            ["--numeric-version"],
            (2, 6),
            (2, 8, 99),
            "agda",
        ) if executable else None
    return None


def _source_with_assumption_audit(
    backend: str,
    source: str,
    *,
    target_declaration: str,
    audit_marker: str = "",
) -> str:
    if backend == "lean4":
        begin = f"ALBILICH_AXIOM_AUDIT_BEGIN_{audit_marker}"
        end = f"ALBILICH_AXIOM_AUDIT_END_{audit_marker}"
        return (
            source.rstrip()
            + f'\n\n#check {target_declaration}\n#eval IO.println "{begin}"\n'
            + f"#print axioms {target_declaration}\n"
            + f'#eval IO.println "{end}"\n'
        )
    if backend == "rocq":
        begin = f"ALBILICH_AXIOM_AUDIT_BEGIN_{audit_marker}"
        end = f"ALBILICH_AXIOM_AUDIT_END_{audit_marker}"
        return (
            source.rstrip()
            + f'\n\nGoal True. idtac "{begin}". exact I. Qed.\n'
            + f"Check {target_declaration}.\n"
            + f"Print Assumptions {target_declaration}.\n"
            + f'Goal True. idtac "{end}". exact I. Qed.\n'
        )
    return source


def _audit_assumptions(
    backend: str,
    output: str,
    *,
    allowed_axioms: list[str],
    audit_marker: str = "",
) -> Dict[str, Any]:
    if backend == "agda":
        return {
            "verified": not allowed_axioms,
            "method": "agda --safe",
            "observed_axioms": [],
            "allowed_axioms": allowed_axioms,
        }
    if backend == "lean4":
        marker_verified = True
        audited_output = output
        if audit_marker:
            begin = f"ALBILICH_AXIOM_AUDIT_BEGIN_{audit_marker}"
            end = f"ALBILICH_AXIOM_AUDIT_END_{audit_marker}"
            marker_verified = output.count(begin) == 1 and output.count(end) == 1
            begin_index = output.find(begin)
            end_index = output.find(end, begin_index + len(begin))
            if marker_verified and 0 <= begin_index < end_index:
                audited_output = output[begin_index + len(begin) : end_index]
            else:
                audited_output = ""
        matches = list(
            re.finditer(
                r"depends on axioms:\s*\[([^\]]*)\]",
                audited_output,
                re.DOTALL,
            )
        )
        if matches:
            observed = sorted(
                {
                    item.strip()
                    for item in matches[-1].group(1).split(",")
                    if item.strip()
                }
            )
            parsed = True
        elif "does not depend on any axioms" in audited_output:
            observed = []
            parsed = True
        else:
            observed = []
            parsed = False
        forbidden = sorted(set(observed) & FORBIDDEN_LEAN_AXIOMS)
        return {
            "verified": (
                marker_verified
                and parsed
                and observed == allowed_axioms
                and not forbidden
            ),
            "method": "Lean #print axioms in a host-delimited output segment",
            "parsed": parsed,
            "audit_markers_verified": marker_verified,
            "observed_axioms": observed,
            "allowed_axioms": allowed_axioms,
            "unexpected_axioms": sorted(set(observed) - set(allowed_axioms)),
            "missing_declared_axioms": sorted(set(allowed_axioms) - set(observed)),
            "forbidden_axioms": forbidden,
        }
    marker_verified = True
    audited_output = output
    if audit_marker:
        begin = f"ALBILICH_AXIOM_AUDIT_BEGIN_{audit_marker}"
        end = f"ALBILICH_AXIOM_AUDIT_END_{audit_marker}"
        marker_verified = output.count(begin) == 1 and output.count(end) == 1
        begin_index = output.find(begin)
        end_index = output.find(end, begin_index + len(begin))
        if marker_verified and 0 <= begin_index < end_index:
            audited_output = output[begin_index + len(begin) : end_index]
        else:
            audited_output = ""
    closed = "Closed under the global context" in audited_output
    open_assumptions = bool(re.search(r"(?m)^\s*Axioms:\s*$", audited_output))
    return {
        "verified": (
            marker_verified
            and closed
            and not open_assumptions
            and not allowed_axioms
        ),
        "method": "Rocq Print Assumptions in a host-delimited output segment",
        "parsed": marker_verified and (closed or open_assumptions),
        "audit_markers_verified": marker_verified,
        "observed_axioms": (
            ["nonempty_global_assumptions"] if open_assumptions else []
        ),
        "allowed_axioms": allowed_axioms,
    }


def _agda_declares_target(source: str, target_declaration: str) -> bool:
    """Bind an Agda request to a top-level declaration in ``Main``.

    The checked file is materialized as ``Main.agda``.  Accepting only an
    unqualified name or ``Main.<name>`` avoids treating ``Other.result`` as the
    same target merely because a nested or unrelated declaration is also named
    ``result``.
    """

    stripped: list[str] = []
    index = 0
    block_depth = 0
    while index < len(source):
        pair = source[index : index + 2]
        if block_depth:
            if pair == "{-":
                block_depth += 1
                index += 2
            elif pair == "-}":
                block_depth -= 1
                index += 2
            else:
                stripped.append("\n" if source[index] == "\n" else " ")
                index += 1
            continue
        if pair == "{-":
            block_depth = 1
            stripped.extend("  ")
            index += 2
            continue
        if pair == "--":
            newline = source.find("\n", index + 2)
            if newline < 0:
                break
            stripped.append("\n")
            index = newline + 1
            continue
        stripped.append(source[index])
        index += 1
    stripped_source = "".join(stripped)
    parts = target_declaration.split(".")
    if len(parts) > 2 or (len(parts) == 2 and parts[0] != "Main"):
        return False
    name = parts[-1]
    module_headers = re.findall(
        r"(?m)^module\s+([A-Za-z_][A-Za-z0-9_']*)\s+where\s*$",
        stripped_source,
    )
    if module_headers and module_headers[0] != "Main":
        return False
    if len(parts) == 2 and (not module_headers or module_headers[0] != "Main"):
        return False
    # Column-zero is deliberate: an indented signature can belong to a nested
    # module or local block and is not the requested top-level theorem.
    return re.search(
        rf"(?m)^{re.escape(name)}\s*:",
        stripped_source,
    ) is not None


def _lean_source_policy_errors(source: str) -> list[str]:
    """Reject source-defined command machinery that could spoof host audits.

    Ordinary theorem declarations and tactics remain legal.  Certification
    source may not redefine parsers/elaborators, run compile-time programs, or
    locally turn off the warning that exposes ``sorry``.  The Lean kernel is
    still the ultimate checker; this policy protects the harness's appended
    target/axiom audit from source-controlled output and command semantics.
    """

    stripped = _strip_lean_comments_and_strings(source)
    forbidden_patterns = (
        (r"(?m)^\s*(?:local\s+)?(?:syntax|macro|macro_rules|elab|elab_rules)\b", "source-defined Lean syntax or elaborators"),
        (r"\b(?:initialize|builtin_initialize)\b", "Lean initializers"),
        (r"\brun_tac\b", "Lean run_tac metaprograms"),
        (r"(?m)^\s*#(?:eval|print|check|reduce|compile)\b", "source-controlled Lean diagnostic commands"),
        (r"\b(?:unsafe|partial)\s+(?:def|theorem|opaque|abbrev|instance)\b", "unsafe or partial Lean declarations"),
        (r"\bset_option\s+warningAsError\s+false\b", "disabling warningAsError"),
        (r"\bcommand_elab\b", "custom Lean command elaboration"),
    )
    return [
        f"Lean certification source forbids {description}"
        for pattern, description in forbidden_patterns
        if re.search(pattern, stripped)
    ]


def _strip_lean_comments_and_strings(source: str) -> str:
    """Blank nested Lean comments and string literals while preserving lines."""

    result: list[str] = []
    index = 0
    block_depth = 0
    in_string = False
    escaped = False
    while index < len(source):
        pair = source[index : index + 2]
        character = source[index]
        if block_depth:
            if pair == "/-":
                block_depth += 1
                result.extend("  ")
                index += 2
            elif pair == "-/":
                block_depth -= 1
                result.extend("  ")
                index += 2
            else:
                result.append("\n" if character == "\n" else " ")
                index += 1
            continue
        if in_string:
            result.append("\n" if character == "\n" else " ")
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if pair == "/-":
            block_depth = 1
            result.extend("  ")
            index += 2
            continue
        if pair == "--":
            newline = source.find("\n", index + 2)
            if newline < 0:
                result.extend(" " * (len(source) - index))
                break
            result.extend(" " * (newline - index))
            result.append("\n")
            index = newline + 1
            continue
        if character == '"':
            in_string = True
            result.append(" ")
            index += 1
            continue
        result.append(character)
        index += 1
    return "".join(result)
