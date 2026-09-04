from __future__ import annotations

from pathlib import Path
from typing import Sequence


_SYSTEM_RUNTIME_ROOTS = tuple(
    Path(item).resolve() for item in ("/usr", "/bin", "/lib", "/lib64") if Path(item).exists()
)
_BROAD_RUNTIME_ROOTS = {
    Path("/").resolve(),
    Path("/tmp").resolve(),
    Path("/var").resolve(),
    Path("/home").resolve(),
}

# RLIMIT_NPROC is charged to the host UID before bubblewrap creates the PID
# namespace. A very small value therefore fails nondeterministically on shared
# CI/agent hosts even when the sandbox itself has only one process. Keep a
# finite ceiling with enough headroom for unrelated same-UID jobs.
SANDBOX_NPROC_LIMIT = 1024


def sandbox_runtime_mounts(
    executable: str | Path,
    *,
    mount_target: str = "/albilich-backend",
) -> tuple[list[str], str, str]:
    """Return read-only bubblewrap mounts and the in-sandbox executable path.

    System executables are already covered by the caller's read-only system
    mounts.  A self-contained executable is mounted at ``mount_target``.  For
    a non-system toolchain, its conventional installation prefix (the parent
    of ``bin``) is mounted at the same absolute path so relative shared-library
    and standard-library lookup continues to work.  Broad roots and any prefix
    containing the current project are never exposed merely to make a backend
    runnable.
    """

    resolved = Path(executable).resolve(strict=True)
    if any(resolved.is_relative_to(root) for root in _SYSTEM_RUNTIME_ROOTS):
        return [], str(resolved), "system"

    prefix = resolved.parent.parent.resolve()
    working_directory = Path.cwd().resolve()
    prefix_is_broad = (
        prefix in _BROAD_RUNTIME_ROOTS
        or prefix == Path.home().resolve()
        or working_directory.is_relative_to(prefix)
    )
    if not prefix_is_broad and prefix != resolved.parent:
        return ["--ro-bind", str(prefix), str(prefix)], str(resolved), str(prefix)

    return ["--ro-bind", str(resolved), mount_target], mount_target, "executable-only"


def append_runtime_mounts(command: list[str], mounts: Sequence[str]) -> None:
    """Append a prevalidated flat bubblewrap mount argument sequence."""

    command.extend(str(item) for item in mounts)
