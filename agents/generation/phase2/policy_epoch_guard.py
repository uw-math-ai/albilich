from __future__ import annotations

"""Enforce append-only semantic commitments for published scheduler policies."""

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PolicyEpochContract:
    active_version: int
    supported_versions: tuple[int, ...]
    semantic_commitments: Mapping[int, str]


POLICY_FILES = (
    (
        "scheduler action contract",
        Path("agents/generation/phase2/action_contract.py"),
        "SCHEDULER_ACTION_CONTRACT_VERSION",
        "SUPPORTED_SCHEDULER_ACTION_CONTRACT_VERSIONS",
        "SCHEDULER_ACTION_CONTRACT_SHA256",
    ),
    (
        "candidate-generator graph",
        Path("agents/generation/phase2/scheduler_registry.py"),
        "CANDIDATE_GENERATOR_GRAPH_VERSION",
        "SUPPORTED_CANDIDATE_GENERATOR_GRAPH_VERSIONS",
        "CANDIDATE_GENERATOR_GRAPH_SHA256",
    ),
    (
        "parallel admission",
        Path("agents/generation/phase2/parallel_admission.py"),
        "PARALLEL_WAVE_ADMISSION_POLICY_VERSION",
        "SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS",
        "PARALLEL_POLICY_SEMANTIC_SHA256",
    ),
    (
        "generic decision",
        Path("agents/generation/phase2/decision_policy.py"),
        "DECISION_POLICY_VERSION",
        "SUPPORTED_DECISION_POLICY_VERSIONS",
        "DECISION_POLICY_SEMANTIC_SHA256",
    ),
)


def _assignment_value(tree: ast.Module, name: str) -> ast.AST:
    stored_names = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Store)
        and node.id == name
    ]
    if len(stored_names) != 1:
        raise ValueError(
            f"policy contract constant {name} must have exactly one direct assignment"
        )
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in statement.targets
        ):
            return statement.value
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == name
            and statement.value is not None
        ):
            return statement.value
    raise ValueError(
        f"policy contract constant {name} must be assigned directly at module scope"
    )


def _literal(value: ast.AST, *, name: str) -> Any:
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "MappingProxyType"
        and len(value.args) == 1
        and not value.keywords
    ):
        value = value.args[0]
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError) as exc:
        raise ValueError(f"policy contract constant {name} is not literal") from exc


def parse_policy_epoch_contract(
    source: str,
    *,
    active_name: str,
    supported_name: str,
    commitments_name: str,
) -> PolicyEpochContract:
    """Parse the three review-critical constants without importing the module."""

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError("policy source is not valid Python") from exc
    raw_active = _literal(
        _assignment_value(tree, active_name),
        name=active_name,
    )
    raw_supported = _literal(
        _assignment_value(tree, supported_name),
        name=supported_name,
    )
    raw_commitments = _literal(
        _assignment_value(tree, commitments_name),
        name=commitments_name,
    )
    if (
        not isinstance(raw_supported, (tuple, list))
        or not raw_supported
        or any(type(version) is not int or version <= 0 for version in raw_supported)
        or len(raw_supported) != len(set(raw_supported))
        or tuple(raw_supported) != tuple(sorted(raw_supported))
    ):
        raise ValueError(
            f"policy contract {supported_name} must be unique increasing positive integers"
        )
    if tuple(raw_supported) != tuple(
        range(int(raw_supported[0]), int(raw_supported[-1]) + 1)
    ):
        raise ValueError(
            f"policy contract {supported_name} must be a contiguous epoch sequence"
        )
    if type(raw_active) is not int or raw_active not in raw_supported:
        raise ValueError(
            f"policy contract {active_name} must name a supported epoch"
        )
    if not isinstance(raw_commitments, dict):
        raise ValueError(f"policy contract {commitments_name} must be a literal mapping")
    commitments: dict[int, str] = {}
    for version, digest in raw_commitments.items():
        if type(version) is not int or version <= 0:
            raise ValueError(f"policy contract {commitments_name} has an invalid version")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(
                f"policy contract {commitments_name} has an invalid SHA-256 digest"
            )
        commitments[version] = digest
    if set(commitments) != set(raw_supported):
        raise ValueError(
            f"policy contract {commitments_name} must cover every supported version exactly"
        )
    return PolicyEpochContract(raw_active, tuple(raw_supported), commitments)


def policy_epoch_history_errors(
    base: PolicyEpochContract,
    current: PolicyEpochContract,
    *,
    label: str,
) -> list[str]:
    """Reject removal or mutation of any commitment published by the base."""

    errors: list[str] = []
    current_versions = set(current.supported_versions)
    for version in base.supported_versions:
        if version not in current_versions:
            errors.append(f"{label} policy v{version} was removed")
            continue
        if (
            current.semantic_commitments.get(version)
            != base.semantic_commitments[version]
        ):
            errors.append(
                f"{label} policy v{version} semantic commitment was modified; add a new epoch instead"
            )
    if current.supported_versions[: len(base.supported_versions)] != (
        base.supported_versions
    ):
        errors.append(
            f"{label} policy versions are not an append-only extension of the base"
        )
    if current.active_version < base.active_version:
        errors.append(
            f"{label} active policy was downgraded from v{base.active_version} "
            f"to v{current.active_version}"
        )
    return errors


def _git_show(base_ref: str, path: Path) -> str | None:
    listing = subprocess.run(
        ["git", "ls-tree", "--full-tree", "-z", base_ref, "--", path.as_posix()],
        check=False,
        capture_output=True,
        text=True,
    )
    if listing.returncode != 0:
        raise RuntimeError(
            f"cannot inspect {path.as_posix()} at Git base {base_ref}"
        )
    if not listing.stdout:
        # A newly introduced policy file has no published in-repository
        # contract to compare.
        return None
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{path.as_posix()}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout
    raise RuntimeError(f"cannot read {path.as_posix()} at Git base {base_ref}")


def check_repository_policy_epochs(base_ref: str) -> list[str]:
    """Compare current policy commitments with an immutable Git base."""

    if not base_ref or set(base_ref) == {"0"}:
        return ["policy epoch guard requires a nonzero Git base revision"]
    verified = subprocess.run(
        ["git", "rev-parse", "--verify", f"{base_ref}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if verified.returncode != 0:
        return [f"policy epoch guard cannot resolve Git base {base_ref}"]
    repository = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if repository.returncode != 0 or not repository.stdout.strip():
        return ["policy epoch guard cannot resolve the Git repository root"]
    repository_root = Path(repository.stdout.strip())
    errors: list[str] = []
    for label, path, active_name, supported_name, commitments_name in POLICY_FILES:
        try:
            current = parse_policy_epoch_contract(
                (repository_root / path).read_text(encoding="utf-8"),
                active_name=active_name,
                supported_name=supported_name,
                commitments_name=commitments_name,
            )
        except (OSError, ValueError) as exc:
            errors.append(f"{label}: {exc}")
            continue
        try:
            base_source = _git_show(base_ref, path)
        except RuntimeError as exc:
            errors.append(f"{label}: {exc}")
            continue
        if base_source is None:
            continue
        try:
            base = parse_policy_epoch_contract(
                base_source,
                active_name=active_name,
                supported_name=supported_name,
                commitments_name=commitments_name,
            )
        except ValueError as exc:
            errors.append(f"{label} base contract: {exc}")
            continue
        errors.extend(policy_epoch_history_errors(base, current, label=label))
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reject edits to semantic commitments of published scheduler policy epochs."
    )
    parser.add_argument("--base-ref", required=True)
    args = parser.parse_args(argv)
    errors = check_repository_policy_epochs(args.base_ref)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"policy epoch history is append-only relative to {args.base_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
