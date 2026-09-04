from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .sandbox_runtime import SANDBOX_NPROC_LIMIT, append_runtime_mounts, sandbox_runtime_mounts


EXECUTABLE_ATTESTATION_VERSION = 1
MAX_VERSION_OUTPUT_BYTES = 16_384


def attest_executable(
    executable: str,
    *,
    version_args: Sequence[str],
    minimum_version: tuple[int, ...],
    maximum_version: tuple[int, ...],
) -> Dict[str, Any]:
    """Bind an executable to its bytes and a supported semantic-version range."""

    path = Path(executable)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": f"executable cannot be resolved: {exc}",
        }
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": "resolved executable is not an executable regular file",
            "executable_path": str(resolved),
        }
    try:
        executable_stat = resolved.stat()
    except OSError as exc:
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": f"executable cannot be statted: {exc}",
            "executable_path": str(resolved),
        }
    if executable_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": "resolved executable is group- or world-writable",
            "executable_path": str(resolved),
        }
    digest = hashlib.sha256()
    prlimit = shutil.which("prlimit")
    bwrap = shutil.which("bwrap")
    if not prlimit or not bwrap:
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": (
                "prlimit and bubblewrap are required for a bounded, networkless "
                "executable version probe"
            ),
            "executable_path": str(resolved),
        }
    try:
        with resolved.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        initial_digest = digest.hexdigest()
        runtime_mounts, sandbox_executable, runtime_root = sandbox_runtime_mounts(
            resolved,
            mount_target="/albilich-version-probe",
        )
        command = [
            prlimit,
            "--as=536870912",
            "--cpu=10",
            f"--nproc={SANDBOX_NPROC_LIMIT}",
            f"--fsize={MAX_VERSION_OUTPUT_BYTES + 1}",
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
        ]
        for directory in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
            if Path(directory).exists():
                command.extend(["--ro-bind", directory, directory])
        append_runtime_mounts(command, runtime_mounts)
        command.extend(["--", sandbox_executable, *version_args])
        with tempfile.TemporaryFile() as output_file:
            completed = subprocess.run(
                command,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
                env={"PATH": "/usr/bin:/bin"},
            )
            output_file.seek(0)
            output_bytes = output_file.read(MAX_VERSION_OUTPUT_BYTES + 1)
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": f"version probe failed: {exc}",
            "executable_path": str(resolved),
            "executable_sha256": digest.hexdigest(),
        }
    output = output_bytes[:MAX_VERSION_OUTPUT_BYTES].decode("utf-8", errors="replace").strip()
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)+)(?!\d)", output)
    parsed = tuple(int(part) for part in match.group(1).split(".")) if match else ()
    post_probe_digest = _sha256_file(resolved)
    executable_unchanged = post_probe_digest == initial_digest
    supported = bool(
        completed.returncode == 0
        and len(output_bytes) <= MAX_VERSION_OUTPUT_BYTES
        and parsed
        and _version_at_least(parsed, minimum_version)
        and _version_at_most(parsed, maximum_version)
        and executable_unchanged
    )
    return {
        "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
        "valid": supported,
        "executable_path": str(resolved),
        "executable_sha256": initial_digest,
        "version_output": output,
        "parsed_version": ".".join(str(part) for part in parsed),
        "supported_range": {
            "minimum": ".".join(str(part) for part in minimum_version),
            "maximum": ".".join(str(part) for part in maximum_version),
        },
        "probe_returncode": int(completed.returncode),
        "version_probe_networkless": True,
        "sandbox_runtime_root": runtime_root,
        "output_truncated": len(output_bytes) > MAX_VERSION_OUTPUT_BYTES,
        "executable_unchanged_after_probe": executable_unchanged,
        "error": (
            ""
            if supported
            else "unparseable, failed, oversized, changed, or unsupported executable version"
        ),
    }


def attested_executable_unchanged(attestation: Mapping[str, Any]) -> bool:
    """Recheck executable bytes after a backend run to detect ordinary swaps."""

    path = Path(str(attestation.get("executable_path") or ""))
    expected = str(attestation.get("executable_sha256") or "")
    if len(expected) != 64 or not path.is_file():
        return False
    try:
        info = path.stat()
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return False
        observed = _sha256_file(path)
    except OSError:
        return False
    return observed == expected


def attest_executable_identity(executable: str) -> Dict[str, Any]:
    """Attest executable bytes and permissions without executing the program."""

    try:
        resolved = Path(executable).resolve(strict=True)
        info = resolved.stat()
    except OSError as exc:
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": f"executable cannot be resolved or statted: {exc}",
        }
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": "resolved executable is not an executable regular file",
            "executable_path": str(resolved),
        }
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": "resolved executable is group- or world-writable",
            "executable_path": str(resolved),
        }
    try:
        digest = _sha256_file(resolved)
    except OSError as exc:
        return {
            "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
            "valid": False,
            "error": f"executable cannot be hashed: {exc}",
            "executable_path": str(resolved),
        }
    return {
        "attestation_version": EXECUTABLE_ATTESTATION_VERSION,
        "valid": True,
        "executable_path": str(resolved),
        "executable_sha256": digest,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _version_at_least(observed: tuple[int, ...], boundary: tuple[int, ...]) -> bool:
    width = max(len(observed), len(boundary))
    return observed + (0,) * (width - len(observed)) >= boundary + (0,) * (width - len(boundary))


def _version_at_most(observed: tuple[int, ...], boundary: tuple[int, ...]) -> bool:
    width = max(len(observed), len(boundary))
    return observed + (0,) * (width - len(observed)) <= boundary + (0,) * (width - len(boundary))
