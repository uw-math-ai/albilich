from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence


DISPATCH_EXECUTION_RECORD_VERSION = 1
CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE = "albilich_executor_concurrency"
CUSTOM_EXECUTOR_PARALLEL_CAPABILITY = "thread_safe_cancellable_v1"
CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE = "albilich_executor_resource_supervision"
CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY = "aggregate_process_tree_rss_v1"


def execution_contract_errors(value: Any) -> list[str]:
    """Validate durable executor identity and local resource semantics.

    Version 1 remains readable for historical dispatch recovery. Version 2
    makes aggregate local-child memory enforcement explicit and distinguishes
    it from resource policy delegated to an unverified external executor.
    """

    if not isinstance(value, Mapping):
        return ["execution contract is not an object"]
    version = value.get("version")
    driver = str(value.get("driver") or "")
    recovery = str(value.get("recovery_capability") or "")
    errors: list[str] = []
    if type(version) is not int or version not in {1, 2}:
        errors.append("execution contract version is unsupported")
    if driver not in {"builtin_codex", "custom"}:
        errors.append("execution contract driver is invalid")
    if recovery not in {
        "supervised_process",
        "idempotent_by_scheduler_dispatch_id",
        "none",
    }:
        errors.append("execution recovery capability is invalid")
    if version != 2 or errors:
        return errors

    identity = str(value.get("identity") or "").strip()
    concurrency = str(value.get("concurrency_capability") or "")
    if concurrency not in {"serial", CUSTOM_EXECUTOR_PARALLEL_CAPABILITY}:
        errors.append("execution concurrency capability is invalid")
    if driver == "builtin_codex":
        if recovery != "supervised_process" or not identity:
            errors.append("built-in execution identity or recovery mode is invalid")
        if str(value.get("aggregate_process_tree_rss_enforcement") or "") != (
            "local_supervisor"
        ):
            errors.append("built-in aggregate RSS enforcement mode is invalid")
        if concurrency != CUSTOM_EXECUTOR_PARALLEL_CAPABILITY:
            errors.append("built-in execution must retain cancellable parallelism")
        aggregate_limit = value.get(
            "max_aggregate_child_process_tree_rss_mb"
        )
        if isinstance(aggregate_limit, bool):
            errors.append("aggregate child RSS limit is invalid")
        else:
            try:
                numeric_limit = float(aggregate_limit)
            except (TypeError, ValueError, OverflowError):
                numeric_limit = 0.0
            if not math.isfinite(numeric_limit) or numeric_limit <= 0.0:
                errors.append("aggregate child RSS limit is invalid")
    elif driver == "custom":
        if recovery == "supervised_process":
            errors.append("custom executor cannot claim built-in process recovery")
        if recovery == "idempotent_by_scheduler_dispatch_id" and not identity:
            errors.append("idempotent custom executor identity is missing")
        enforcement = str(
            value.get("aggregate_process_tree_rss_enforcement") or ""
        )
        aggregate_limit = value.get(
            "max_aggregate_child_process_tree_rss_mb"
        )
        if enforcement == "local_supervisor":
            if isinstance(aggregate_limit, bool):
                errors.append("aggregate child RSS limit is invalid")
            else:
                try:
                    numeric_limit = float(aggregate_limit)
                except (TypeError, ValueError, OverflowError):
                    numeric_limit = 0.0
                if not math.isfinite(numeric_limit) or numeric_limit <= 0.0:
                    errors.append("aggregate child RSS limit is invalid")
        elif enforcement == "external_executor_unverified":
            if aggregate_limit is not None:
                errors.append(
                    "unverified external executor cannot claim a local RSS limit"
                )
        else:
            errors.append("external aggregate RSS enforcement status is invalid")
        if (
            concurrency == CUSTOM_EXECUTOR_PARALLEL_CAPABILITY
            and enforcement != "local_supervisor"
        ):
            errors.append(
                "parallel custom execution requires local aggregate RSS supervision"
            )
    return errors


def execution_resource_result_errors(
    execution_contract: Any,
    execution: Any,
) -> list[str]:
    """Bind built-in supervisor observations to the committed v2 contract."""

    if not isinstance(execution_contract, Mapping):
        return ["execution resource contract is unavailable"]
    if execution_contract.get("version") != 2 or str(
        execution_contract.get("aggregate_process_tree_rss_enforcement") or ""
    ) != "local_supervisor":
        return []
    if not isinstance(execution, Mapping):
        return ["locally supervised execution resource result is unavailable"]
    limits = execution.get("resource_limits")
    if not isinstance(limits, Mapping):
        return ["locally supervised execution result has no resource limits"]

    committed_limit = execution_contract.get(
        "max_aggregate_child_process_tree_rss_mb"
    )
    reported_limit = limits.get(
        "max_aggregate_child_process_tree_rss_mb"
    )
    errors: list[str] = []
    try:
        committed_numeric = float(committed_limit)
        reported_numeric = float(reported_limit)
    except (TypeError, ValueError, OverflowError):
        errors.append("locally supervised aggregate child RSS limit is not numeric")
    else:
        if (
            not math.isfinite(committed_numeric)
            or not math.isfinite(reported_numeric)
            or not math.isclose(
                committed_numeric,
                reported_numeric,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        ):
            errors.append(
                "locally supervised aggregate child RSS limit differs from its dispatch contract"
            )
    peak = execution.get("observed_aggregate_peak_memory_mb")
    if isinstance(peak, bool):
        errors.append("observed aggregate child RSS peak is invalid")
    else:
        try:
            peak_numeric = float(peak)
        except (TypeError, ValueError, OverflowError):
            peak_numeric = -1.0
        if not math.isfinite(peak_numeric) or peak_numeric < 0.0:
            errors.append("observed aggregate child RSS peak is invalid")
    return errors


def canonical_dispatch_json(value: Any) -> str:
    """Encode execution records with the same strict representation everywhere."""

    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def dispatch_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_dispatch_json(value).encode("utf-8")).hexdigest()


def dispatch_result_sha256(
    *,
    dispatch_id: str,
    attempt_id: str,
    session_plan: Mapping[str, Any],
    execution: Mapping[str, Any],
    validation_errors: Sequence[str],
) -> str:
    return dispatch_json_sha256(
        {
            "version": DISPATCH_EXECUTION_RECORD_VERSION,
            "dispatch_id": str(dispatch_id),
            "attempt_id": str(attempt_id),
            "session_plan": dict(session_plan),
            "execution": dict(execution),
            "validation_errors": [str(error) for error in validation_errors],
        }
    )


def durable_path_source_identity_errors(
    execution: Mapping[str, Any],
    *,
    allow_unbound: bool,
) -> list[str]:
    """Validate host-bound identities for path-based artifact operations."""

    patch = execution.get("patch")
    if not isinstance(patch, Mapping):
        return []
    operations = patch.get("operations")
    if not isinstance(operations, list):
        return []
    errors: list[str] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping):
            continue
        has_digest = "source_file_sha256" in operation
        has_size = "source_file_size_bytes" in operation
        path_attach = (
            str(operation.get("op") or "")
            in {"attach_artifact", "add_artifact"}
            and bool(str(operation.get("path") or "").strip())
            and "content" not in operation
        )
        if has_digest != has_size:
            errors.append(
                f"operation {index} has an incomplete staged-source identity"
            )
            continue
        if (has_digest or has_size) and not path_attach:
            errors.append(
                f"operation {index} has a staged-source identity without a path attach"
            )
            continue
        if path_attach and not has_digest:
            if not allow_unbound:
                errors.append(
                    f"operation {index} path attach is not bound to staged file bytes"
                )
            continue
        if not has_digest:
            continue
        digest = operation.get("source_file_sha256")
        size = operation.get("source_file_size_bytes")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or type(size) is not int
            or size < 0
        ):
            errors.append(f"operation {index} has a malformed staged-source identity")
    return errors
