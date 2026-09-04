from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional

from .action_contract import (
    RESEARCH_MANAGEMENT_MODES,
    VERIFICATION_BUDGET_MODES,
    scheduler_budget_class_for_action,
)

VERIFICATION_MODES = VERIFICATION_BUDGET_MODES
VERIFICATION_RESERVE_ACTOR_ROLES = {"strict_informal_verifier"}
DEFAULT_STEP_BUDGET = 200_000
DEFAULT_RESEARCH_MANAGEMENT_BUDGET = 120_000
MIN_STEP_BUDGET = 10_000
MAX_STEP_BUDGET = 1_200_000
FAST_RESEARCH_STEP_BUDGET = 90_000
COUNTEREXAMPLE_STEP_BUDGET = 80_000
CITATION_TRIAGE_STEP_BUDGET = 60_000
CITATION_CERTIFICATION_STEP_BUDGET = 120_000
SOURCE_DIGEST_STEP_BUDGET = 140_000
ROOT_RESEARCH_STEP_BUDGET = 180_000
ROUTE_PROOF_CONSTRUCTION_STEP_BUDGET = 420_000
DEEP_RESEARCH_STEP_BUDGET = 650_000
HARD_THEOREM_WORKBENCH_STEP_BUDGET = 780_000


def estimate_tokens_from_text(text: str) -> int:
    """Conservative local estimate used only for context planning."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def parse_token_usage(payload: Any) -> Dict[str, int]:
    """Parse token usage from Codex/OpenAI-like payloads without assuming a model."""
    if payload is None:
        return _empty_usage()
    if not isinstance(payload, Mapping):
        return _empty_usage()

    usage = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else payload
    input_tokens = _first_int(usage, "input_tokens", "prompt_tokens", "input", "prompt")
    output_tokens = _first_int(usage, "output_tokens", "completion_tokens", "output", "completion")
    cached_input_tokens = _first_int(usage, "cached_input_tokens", "cached_prompt_tokens", "cache_read_input_tokens")
    reasoning_output_tokens = _first_int(usage, "reasoning_output_tokens", "reasoning_tokens")

    input_details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), Mapping) else {}
    prompt_details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), Mapping) else {}
    output_details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), Mapping) else {}
    completion_details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), Mapping) else {}

    cached_input_tokens = max(
        cached_input_tokens,
        _first_int(input_details, "cached_tokens", "cache_read_tokens"),
        _first_int(prompt_details, "cached_tokens", "cache_read_tokens"),
    )
    reasoning_output_tokens = max(
        reasoning_output_tokens,
        _first_int(output_details, "reasoning_tokens"),
        _first_int(completion_details, "reasoning_tokens"),
    )
    # A malformed or lossy provider envelope must never make a component
    # larger than the aggregate against which it is charged.
    input_tokens = max(input_tokens, cached_input_tokens)
    output_tokens = max(output_tokens, reasoning_output_tokens)

    total_tokens = _first_int(usage, "total_tokens", "total")
    total_tokens = max(total_tokens, input_tokens + output_tokens)

    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": total_tokens,
    }


def plan_step_budget(problem_state: Mapping[str, Any], mode: str, requested_tokens: Optional[int] = None) -> Dict[str, Any]:
    remaining = int(problem_state.get("remaining_token_budget", 0))
    reserve = int(problem_state.get("reserved_verification_budget", 0))
    spendable = remaining if mode in VERIFICATION_MODES else max(0, remaining - reserve)
    default_budget = DEFAULT_RESEARCH_MANAGEMENT_BUDGET if mode in RESEARCH_MANAGEMENT_MODES else DEFAULT_STEP_BUDGET
    desired = int(requested_tokens or default_budget)
    desired = max(MIN_STEP_BUDGET, min(MAX_STEP_BUDGET, desired))

    if spendable <= 0:
        return {
            "allowed": False,
            "requested_tokens": 0,
            "request_limit_tokens": desired,
            "spendable_tokens": spendable,
            "remaining_token_budget": remaining,
            "reserved_verification_budget": reserve,
            "reason": "token reserve reached; stop or run a verification/integration action only",
        }

    granted = min(desired, spendable)
    allowed = granted >= MIN_STEP_BUDGET
    if allowed:
        reason = "ok"
    elif granted > 0 and mode in VERIFICATION_MODES:
        reason = "remaining verification allocation is below the minimum useful step size"
    elif granted > 0:
        reason = "remaining non-verification budget is below the minimum useful step size; stop or run a verification/integration action only"
    else:
        reason = "no spendable tokens"
    return {
        "allowed": allowed,
        "requested_tokens": granted,
        "request_limit_tokens": desired,
        "spendable_tokens": spendable,
        "remaining_token_budget": remaining,
        "reserved_verification_budget": reserve,
        "reason": reason,
    }


def plan_action_budget(
    problem_state: Mapping[str, Any],
    mode: str,
    action: Optional[Mapping[str, Any]] = None,
    requested_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Choose conservative per-action budgets without weakening hard proof checks."""
    if requested_tokens is not None:
        return plan_step_budget(problem_state, mode, requested_tokens)

    action = action or {}
    desired: Optional[int] = None
    policy = "default"
    search_intent = str(action.get("search_intent") or "")

    if action.get("citation_triage_required"):
        desired = CITATION_TRIAGE_STEP_BUDGET
        policy = "citation_triage"
    elif action.get("citation_certification_required"):
        desired = CITATION_CERTIFICATION_STEP_BUDGET
        policy = "citation_certification"
    elif action.get("hard_theorem_attack_required") or action.get("theorem_workbench_required") or action.get("research_attack_stage") in {
        "hard_theorem_workbench",
        "bottleneck_lock",
        "decisive_theorem_test",
        "proof_spine",
    }:
        desired = HARD_THEOREM_WORKBENCH_STEP_BUDGET
        policy = "hard_theorem_workbench"
    elif mode == "refute" or action.get("counterexample_search_required"):
        desired = COUNTEREXAMPLE_STEP_BUDGET
        policy = "counterexample_stress_test"
    elif action.get("source_adaptation_digest_required"):
        desired = SOURCE_DIGEST_STEP_BUDGET
        policy = "source_digest"
    elif (
        action.get("deep_research_required")
        or action.get("long_mathematical_session_required")
        or action.get("research_attack_stage") == "deep"
    ):
        desired = DEEP_RESEARCH_STEP_BUDGET
        policy = "deep_research_pass"
    elif action.get("research_attack_stage") == "fast" or search_intent in {"parallel_independent_solve", "parallel_direct_solve"}:
        desired = FAST_RESEARCH_STEP_BUDGET
        policy = "fast_research_pass"
    elif action.get("proof_construction_required"):
        desired = ROUTE_PROOF_CONSTRUCTION_STEP_BUDGET
        policy = "route_proof_construction"
    elif mode == "reduce" and str(action.get("target_id") or "") == "root":
        desired = ROOT_RESEARCH_STEP_BUDGET
        policy = "root_research"

    budget = plan_step_budget(problem_state, mode, desired)
    if policy != "default":
        budget["policy"] = policy
    return budget


def normalize_resource_allocation_for_action(
    action: Mapping[str, Any],
    allocation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Resolve a provisional mode allocation against the completed action.

    Mode-only planning cannot distinguish direct proof construction from a
    strict route-verification action because both use ``prove``.  The central
    action constructor calls this after adding the route and discriminating
    flags.  The explicit request limit preserves the allocator's original
    request if the verification reserve changes the spendable amount.
    """

    result = dict(allocation)
    try:
        budget_class = scheduler_budget_class_for_action(action)
    except ValueError:
        return result
    if budget_class != "verification":
        return result
    remaining = result.get("remaining_token_budget")
    reserve = result.get("reserved_verification_budget")
    if (
        isinstance(remaining, bool)
        or not isinstance(remaining, int)
        or remaining < 0
        or isinstance(reserve, bool)
        or not isinstance(reserve, int)
        or reserve < 0
    ):
        return result
    desired = result.get("request_limit_tokens")
    if isinstance(desired, bool) or not isinstance(desired, int) or desired <= 0:
        requested = result.get("requested_tokens")
        desired = (
            requested
            if not isinstance(requested, bool)
            and isinstance(requested, int)
            and requested > 0
            else DEFAULT_STEP_BUDGET
        )
    desired = max(MIN_STEP_BUDGET, min(MAX_STEP_BUDGET, desired))
    granted = min(desired, remaining)
    result.update(
        allowed=granted >= MIN_STEP_BUDGET,
        requested_tokens=granted,
        request_limit_tokens=desired,
        spendable_tokens=remaining,
        reason=(
            "ok"
            if granted >= MIN_STEP_BUDGET
            else "remaining verification allocation is below the minimum useful step size"
            if granted > 0
            else "no spendable tokens"
        ),
    )
    return result


def summarize_runs(runs: list[Mapping[str, Any]]) -> Dict[str, Any]:
    input_tokens = sum(int(row.get("input_tokens", 0)) for row in runs)
    cached_input_tokens = sum(int(row.get("cached_input_tokens", 0)) for row in runs)
    output_tokens = sum(int(row.get("output_tokens", 0)) for row in runs)
    reasoning_output_tokens = sum(int(row.get("reasoning_output_tokens", 0)) for row in runs)
    total_tokens = sum(_run_total_tokens(row) for row in runs)
    charged_tokens = sum(run_spend_from_operation(row) for row in runs)
    wall_time_seconds = sum(float(row.get("wall_time_seconds", 0.0) or 0.0) for row in runs)
    peak_memory_mb = max((float(row.get("peak_memory_mb", 0.0) or 0.0) for row in runs), default=0.0)
    cache_ratio = (cached_input_tokens / input_tokens) if input_tokens else 0.0
    return {
        "run_count": len(runs),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": total_tokens,
        "charged_tokens": charged_tokens,
        "wall_time_seconds": round(wall_time_seconds, 3),
        "peak_memory_mb": round(peak_memory_mb, 1),
        "cache_ratio": round(cache_ratio, 4),
    }


def run_spend_from_operation(op: Mapping[str, Any]) -> int:
    """Gross model tokens charged against the allocation for one run.

    Gross usage is the larger of provider ``total_tokens`` and input plus
    output. Cached input remains input, and reasoning tokens are already a
    subset of output, so neither is subtracted or added a second time. Taking
    the maximum prevents an inconsistent provider envelope from undercharging.
    """
    # Periodic HMT is an expository sidecar, not mathematical research.  Keep
    # its usage visible in the sidecar catalog without consuming the proof
    # run's token allocation if an older workflow records such a run in SQLite.
    if str(op.get("search_intent") or "") == "periodic_human_readable_mathematical_text":
        return 0
    total = _first_int(op, "total_tokens")
    components = _first_int(op, "input_tokens") + _first_int(
        op, "output_tokens"
    )
    return max(total, components)


def run_may_use_verification_reserve(op: Mapping[str, Any]) -> bool:
    """Whether recorded work is part of verification/delivery, not exploration."""

    return (
        str(op.get("mode") or "") in VERIFICATION_MODES
        or str(op.get("actor_role") or "") in VERIFICATION_RESERVE_ACTOR_ROLES
    )


def _run_total_tokens(row: Mapping[str, Any]) -> int:
    explicit = _first_int(row, "total_tokens")
    components = (
        _first_int(row, "input_tokens")
        + _first_int(row, "output_tokens")
    )
    return max(explicit, components)


def _first_int(mapping: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, float):
            return max(0, int(value))
        if isinstance(value, str) and value.strip().isdigit():
            return max(0, int(value.strip()))
    return 0


def _empty_usage() -> Dict[str, int]:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }
