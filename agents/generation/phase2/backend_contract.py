"""Runtime attestation for model CLI process boundaries.

The harness relies on security flags whose spelling and semantics belong to
external CLIs.  A command that was safe for one release must not be launched
silently by an untested release.  This module therefore combines a narrow
version interval, a capability probe, an executable digest, and a final argv
check.  Production runners call it before starting a child process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from .sandbox_runtime import SANDBOX_NPROC_LIMIT, append_runtime_mounts, sandbox_runtime_mounts


BACKEND_CONTRACT_VERSION = 1
SUPPORTED_VERSION_INTERVALS = {
    # The permission-profile command surface is exercised against 0.152.x in
    # CI and against 0.153.0 by the local networkless executable-boundary test.
    "codex": ((0, 152, 0), (0, 154, 0)),
    # Claude remains unavailable in the development container.  The 2.1.x
    # interval is capability-tested with a deterministic CLI double in CI;
    # release claims must distinguish that from a live authenticated run.
    "claude": ((2, 1, 0), (2, 2, 0)),
}
REQUIRED_HELP_FLAGS = {
    "codex": {
        "--config",
        "--disable",
        "--ignore-user-config",
        "--output-last-message",
        "--strict-config",
    },
    "claude": {
        "--add-dir",
        "--disallowedTools",
        "--output-format",
        "--permission-mode",
        "--setting-sources",
        "--settings",
        "--strict-mcp-config",
        "--tools",
        "--verbose",
    },
}
_ATTESTATION_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
MAX_PROBE_OUTPUT_BYTES = 1_048_576


class BackendContractError(RuntimeError):
    """Raised before launch when an external CLI is outside its tested contract."""


def _resolve_executable(binary: str) -> Path:
    resolved = shutil.which(str(Path(binary).expanduser()))
    if not resolved:
        raise BackendContractError(f"backend executable is unavailable: {binary}")
    path = Path(resolved).resolve()
    try:
        info = path.stat()
    except OSError as exc:
        raise BackendContractError(f"cannot stat backend executable {path}: {exc}") from exc
    if not stat.S_ISREG(info.st_mode) or not os.access(path, os.X_OK):
        raise BackendContractError(f"backend executable is not a runnable regular file: {path}")
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise BackendContractError(
            f"backend executable is group- or world-writable: {path}"
        )
    return path


def _probe(argv: Sequence[str], *, timeout: float = 10.0) -> str:
    if not argv:
        raise BackendContractError("backend capability probe command is empty")
    prlimit = shutil.which("prlimit")
    bwrap = shutil.which("bwrap")
    if not prlimit or not bwrap:
        raise BackendContractError(
            "prlimit and bubblewrap are required for a bounded, networkless backend probe"
        )
    executable = Path(str(argv[0])).resolve()
    try:
        runtime_mounts, sandbox_executable, _runtime_root = sandbox_runtime_mounts(
            executable
        )
    except OSError as exc:
        raise BackendContractError(
            f"backend capability probe cannot mount its executable: {exc}"
        ) from exc
    command = [
        prlimit,
        "--as=2147483648",
        "--cpu=10",
        f"--nproc={SANDBOX_NPROC_LIMIT}",
        f"--fsize={MAX_PROBE_OUTPUT_BYTES + 1}",
        "--",
        bwrap,
        "--die-with-parent",
        "--new-session",
        "--unshare-net",
        "--clearenv",
        "--setenv",
        "HOME",
        "/tmp",
        "--setenv",
        "PATH",
        "/usr/bin:/bin",
        "--setenv",
        "NO_COLOR",
        "1",
        "--setenv",
        "DISABLE_AUTOUPDATER",
        "1",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
    ]
    for directory in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
        if Path(directory).exists():
            command.extend(["--ro-bind", directory, directory])
    append_runtime_mounts(command, runtime_mounts)
    command.extend(
        ["--", sandbox_executable, *[str(item) for item in argv[1:]]]
    )
    try:
        with tempfile.TemporaryFile() as output_file:
            completed = subprocess.run(
                command,
                check=False,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
            output_file.seek(0)
            output_bytes = output_file.read(MAX_PROBE_OUTPUT_BYTES + 1)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BackendContractError(f"backend capability probe failed: {exc}") from exc
    if len(output_bytes) > MAX_PROBE_OUTPUT_BYTES:
        raise BackendContractError(
            f"backend capability probe exceeded {MAX_PROBE_OUTPUT_BYTES} output bytes"
        )
    output = output_bytes.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise BackendContractError(
            f"backend capability probe exited {completed.returncode}: {output[-300:].strip()}"
        )
    return output


def parse_backend_version(backend: str, output: str) -> tuple[int, int, int]:
    if backend not in SUPPORTED_VERSION_INTERVALS:
        raise BackendContractError(f"unsupported backend: {backend}")
    match = re.search(r"(?<![0-9])(\d+)\.(\d+)\.(\d+)(?![0-9])", output)
    if match is None:
        raise BackendContractError(
            f"could not parse {backend} semantic version from --version output"
        )
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _codex_companion_paths(path: Path) -> list[Path]:
    """Locate the native 0.153 bundle, including official npm layouts."""
    if path.name != "codex.js":
        return [path.parent / "codex-code-mode-host"]
    architecture = {"aarch64": "arm64", "arm64": "arm64", "x86_64": "x64"}.get(
        platform.machine()
    )
    if sys.platform != "linux" or architecture is None:
        raise BackendContractError("Codex npm companion discovery requires supported Linux")
    triple = (
        "aarch64-unknown-linux-musl" if architecture == "arm64"
        else "x86_64-unknown-linux-musl"
    )
    package_root = path.parent.parent
    package_name = f"codex-linux-{architecture}"
    for vendor in (
        package_root / "node_modules" / "@openai" / package_name / "vendor",
        package_root.parent / package_name / "vendor",
        package_root / "vendor",
    ):
        native = vendor / triple / "bin" / "codex"
        if native.is_file():
            return [native, native.with_name("codex-code-mode-host")]
    raise BackendContractError(
        "Codex npm native bundle is missing; reinstall the matching platform package "
        "or pass --codex-bin with the native executable"
    )


def attest_backend(binary: str, backend: str) -> dict[str, Any]:
    """Return a reproducible attestation or fail before any model process starts."""

    path = _resolve_executable(binary)
    # Hash before consulting the cache.  File size and mtime can be restored by
    # an attacker and therefore are not suitable cache identities.
    executable_sha256 = _sha256_file(path)
    cache_key = (backend, str(path), executable_sha256)
    cached = _ATTESTATION_CACHE.get(cache_key)
    if cached is not None and attested_backend_unchanged(cached):
        return dict(cached)

    version_output = _probe([str(path), "--version"]).strip()
    version = parse_backend_version(backend, version_output)
    lower, upper = SUPPORTED_VERSION_INTERVALS[backend]
    if not lower <= version < upper:
        raise BackendContractError(
            f"untested {backend} CLI version {'.'.join(map(str, version))}; "
            f"required interval is [{'.'.join(map(str, lower))}, {'.'.join(map(str, upper))})"
        )
    companions: list[dict[str, str]] = []
    if backend == "codex" and version >= (0, 153, 0):
        # Standalone release archives contain only the main CLI. Code-mode
        # tool execution also needs this sibling from the matching release.
        # Do not silently fall back to an unrelated helper on PATH.
        for launch_path in _codex_companion_paths(path):
            helper = _resolve_executable(str(launch_path))
            companions.append(
                {
                    "launch_path": str(launch_path),
                    "executable_path": str(helper),
                    "executable_sha256": _sha256_file(helper),
                }
            )
    help_argv = [str(path), "exec", "--help"] if backend == "codex" else [str(path), "--help"]
    help_output = _probe(help_argv)
    missing = sorted(flag for flag in REQUIRED_HELP_FLAGS[backend] if flag not in help_output)
    if missing:
        raise BackendContractError(
            f"{backend} CLI {version_output!r} lacks required security capabilities: "
            + ", ".join(missing)
        )
    if _sha256_file(path) != executable_sha256:
        raise BackendContractError(
            "backend executable changed during its version/capability probes"
        )
    capability_lines = sorted(
        flag for flag in REQUIRED_HELP_FLAGS[backend] if flag in help_output
    )
    payload: dict[str, Any] = {
        "backend_contract_version": BACKEND_CONTRACT_VERSION,
        "backend": backend,
        "version": ".".join(map(str, version)),
        "version_output": version_output[:200],
        "executable_path": str(path),
        "executable_sha256": executable_sha256,
        "required_capabilities": capability_lines,
        "capability_probe_sha256": hashlib.sha256(help_output.encode()).hexdigest(),
    }
    if companions:
        payload["companion_executables"] = companions
        if not attested_backend_unchanged(payload):
            raise BackendContractError("backend companion changed during capability probes")
    payload["attestation_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    _ATTESTATION_CACHE[cache_key] = dict(payload)
    return payload


def attested_backend_unchanged(attestation: Mapping[str, Any]) -> bool:
    """Re-hash an attested model CLI at a process-boundary checkpoint."""

    expected_path = str(attestation.get("executable_path") or "")
    expected_digest = str(attestation.get("executable_sha256") or "")
    if not expected_path or len(expected_digest) != 64:
        return False
    try:
        path = _resolve_executable(expected_path)
        if str(path) != expected_path:
            return False
        if _sha256_file(path) != expected_digest:
            return False
        for companion in attestation.get("companion_executables", []):
            helper = _resolve_executable(
                str(companion.get("launch_path") or companion["executable_path"])
            )
            if (
                str(helper) != companion["executable_path"]
                or _sha256_file(helper) != companion["executable_sha256"]
            ):
                return False
        return True
    except (BackendContractError, OSError):
        return False


def _value_after(argv: Sequence[str], flag: str) -> str:
    try:
        index = argv.index(flag)
    except ValueError as exc:
        raise BackendContractError(f"launch command omits required flag {flag}") from exc
    if index + 1 >= len(argv):
        raise BackendContractError(f"launch command has no value for {flag}")
    return str(argv[index + 1])


def validate_launch_command(
    backend: str,
    argv: Sequence[str],
    attestation: Mapping[str, Any],
) -> None:
    """Verify the exact process argv against the attested security contract."""

    if not argv:
        raise BackendContractError("backend launch command is empty")
    if str(attestation.get("backend") or "") != backend:
        raise BackendContractError("launch backend differs from the attested backend")
    if not attested_backend_unchanged(attestation):
        raise BackendContractError("attested backend executable changed before launch")
    if Path(str(argv[0])).resolve() != Path(str(attestation.get("executable_path") or "")).resolve():
        raise BackendContractError("launch executable differs from the attested executable")
    forbidden = {
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-skip-permissions",
        "--allow-dangerously-skip-permissions",
        "--no-sandbox",
    }
    present_forbidden = sorted(forbidden & set(argv))
    if present_forbidden:
        raise BackendContractError(
            "unsafe backend launch flags are forbidden: " + ", ".join(present_forbidden)
        )

    if backend == "codex":
        if len(argv) < 2 or argv[1] != "exec":
            raise BackendContractError("Codex child must use the noninteractive exec command")
        for flag in ("--strict-config", "--ignore-user-config", "-C", "--output-last-message"):
            if flag not in argv:
                raise BackendContractError(f"Codex launch omits required isolation flag {flag}")
        config_values = [
            str(argv[index + 1])
            for index, token in enumerate(argv[:-1])
            if token == "--config"
        ]
        if not any(value.startswith("permissions.albilich-evidence-capsule=") for value in config_values):
            raise BackendContractError("Codex launch omits the evidence-capsule permission profile")
        if 'default_permissions="albilich-evidence-capsule"' not in config_values:
            raise BackendContractError("Codex launch does not select the evidence-capsule profile")
    elif backend == "claude":
        for flag in (
            "-p",
            "--setting-sources",
            "--settings",
            "--strict-mcp-config",
            "--tools",
            "--permission-mode",
            "--output-format",
        ):
            if flag not in argv:
                raise BackendContractError(f"Claude launch omits required isolation flag {flag}")
        if _value_after(argv, "--setting-sources") != "":
            raise BackendContractError("Claude launch must disable user and project setting sources")
        if _value_after(argv, "--permission-mode") not in {"dontAsk", "plan"}:
            raise BackendContractError("Claude launch permission mode is not fail-closed")
        try:
            settings = json.loads(_value_after(argv, "--settings"))
        except json.JSONDecodeError as exc:
            raise BackendContractError("Claude launch settings are not valid JSON") from exc
        sandbox = settings.get("sandbox") if isinstance(settings, Mapping) else None
        if not isinstance(sandbox, Mapping) or sandbox.get("enabled") is not True:
            raise BackendContractError("Claude launch does not enable its OS sandbox")
        if sandbox.get("failIfUnavailable") is not True or sandbox.get("allowUnsandboxedCommands") is not False:
            raise BackendContractError("Claude launch sandbox is not fail-closed")
    else:
        raise BackendContractError(f"unsupported backend: {backend}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Attest an Albilich model CLI boundary")
    parser.add_argument("backend", choices=sorted(SUPPORTED_VERSION_INTERVALS))
    parser.add_argument("--binary", default="")
    args = parser.parse_args(argv)
    binary = args.binary or args.backend
    try:
        result = attest_backend(binary, args.backend)
    except BackendContractError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"valid": True, **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
