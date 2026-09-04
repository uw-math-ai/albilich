#!/usr/bin/env python3
"""Reproducible scheduler and bounded-history microbenchmarks."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.generation.phase2.scheduler import (
    _evidence_assimilation_action,
    _enable_scheduler_planning_cache,
    _generated_policy_deferrals,
    _obligation_routing_action,
    _parallel_wave_admission_errors,
    _verification_handoff_action,
    next_action,
    parallel_companion_actions,
)
from agents.generation.phase2.decision_policy import decision_trace_errors
from agents.generation.phase2.codex_runner import run_metrics_operation
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.parallel_admission import (
    PARALLEL_ADMISSION_ANYTIME_STATE_LIMIT,
    PARALLEL_ADMISSION_BOUNDED_FRONTIER_CERTIFICATE_VERSION,
    PARALLEL_ADMISSION_CANONICAL_SUFFIX_MAX_CARDINALITY,
    PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT,
    PARALLEL_ADMISSION_DOMINANCE_MAX_FRONTIER,
    PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
    PARALLEL_WAVE_DEFERRAL_LIMIT,
    parallel_admission_order_key,
    parallel_admission_outcomes,
    parallel_admission_priority_for,
)
from agents.generation.phase2.patches import apply_system_patch
from agents.generation.phase2.research_intelligence import strategy_family
from agents.generation.phase2.store import (
    ProofStateStore,
    SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT,
    SCHEDULER_RECENT_RUN_LIMIT,
)
from agents.generation.phase2.workflow import (
    _record_scheduler_attempts,
    _record_scheduler_dispatches,
    _record_scheduler_result,
)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def _dense_parallel_certificate_errors(metric: object) -> list[str]:
    """Reject a fast dense run whose current-policy certificate regressed."""

    if not isinstance(metric, dict):
        return ["dense parallel-search benchmark result is not an object"]
    errors: list[str] = []
    if metric.get("policy_version") != PARALLEL_WAVE_ADMISSION_POLICY_VERSION:
        errors.append("dense parallel-search benchmark used the wrong policy epoch")
    evidence = metric.get("search_evidence")
    if not isinstance(evidence, dict):
        return [*errors, "dense parallel-search evidence is not an object"]
    if (
        evidence.get("version")
        != PARALLEL_ADMISSION_BOUNDED_FRONTIER_CERTIFICATE_VERSION
    ):
        errors.append("dense parallel-search evidence used the wrong certificate version")
    if evidence.get("optimality_certified") is not True:
        errors.append("dense parallel-search optimum is not certified")
    if evidence.get("optimality") != "exact":
        errors.append("dense parallel-search optimality label is not exact")
    quotient_applied = evidence.get("future_equivalence_quotient_applied")
    merged_states = evidence.get("states_merged_by_future_equivalence")
    if type(quotient_applied) is not bool:
        errors.append("dense parallel-search quotient flag is not boolean")
    if type(merged_states) is not int or merged_states < 0:
        errors.append("dense parallel-search quotient count is not a nonnegative integer")
    canonical_selection_certified = evidence.get("canonical_selection_certified")
    if type(canonical_selection_certified) is not bool:
        errors.append("dense parallel-search canonicality flag is not boolean")
    elif canonical_selection_certified is not True:
        errors.append("dense parallel-search canonical selection is not certified")
    if evidence.get("canonical_tie_break") != (
        "lexicographically_minimum_selected_candidate_ids"
    ):
        errors.append("dense parallel-search canonical tie rule is invalid")
    if evidence.get("canonical_lower_bound") != (
        "lexicographically_minimum_suffix_subsequence_at_objective_cardinality"
    ):
        errors.append("dense parallel-search canonical lower-bound rule is invalid")
    canonical_bound_prunes = evidence.get("states_pruned_by_canonical_bound")
    if type(canonical_bound_prunes) is not int or canonical_bound_prunes < 0:
        errors.append(
            "dense parallel-search canonical-bound prune count is not a nonnegative integer"
        )
    discarded_canonical_bound = evidence.get(
        "discarded_canonical_lower_bound_candidate_ids"
    )
    if discarded_canonical_bound is not None and (
        not isinstance(discarded_canonical_bound, list)
        or any(not isinstance(value, str) for value in discarded_canonical_bound)
    ):
        errors.append("dense parallel-search discarded canonical bound is invalid")
    discarded_objective_bound = evidence.get(
        "discarded_upper_bound_objective_value"
    )
    if discarded_objective_bound is not None and (
        not isinstance(discarded_objective_bound, list)
        or len(discarded_objective_bound) != 4
        or any(type(value) is not int for value in discarded_objective_bound)
    ):
        errors.append("dense parallel-search discarded objective bound is invalid")
    if (discarded_canonical_bound is None) != (discarded_objective_bound is None):
        errors.append("dense parallel-search discarded canonical bounds are incomplete")
    candidate_count = evidence.get("candidate_count")
    if type(candidate_count) is not int or candidate_count < 0:
        errors.append("dense parallel-search candidate count is not a nonnegative integer")
    elif candidate_count != metric.get("candidate_count"):
        errors.append("dense parallel-search candidate count is inconsistent")
    search_candidate_count = evidence.get("search_candidate_count")
    infeasible_candidate_count = evidence.get(
        "intrinsically_infeasible_candidate_count"
    )
    if (
        type(search_candidate_count) is not int
        or search_candidate_count < 0
        or type(candidate_count) is not int
        or search_candidate_count > candidate_count
    ):
        errors.append("dense parallel-search searchable candidate count is invalid")
    if (
        type(infeasible_candidate_count) is not int
        or infeasible_candidate_count < 0
        or type(candidate_count) is not int
        or type(search_candidate_count) is not int
        or infeasible_candidate_count != candidate_count - search_candidate_count
    ):
        errors.append("dense parallel-search infeasible candidate count is invalid")
    if evidence.get("intrinsic_candidate_filter") != (
        "authorization_primary_conflict_class_capacity_minimum_grant_and_"
        "available_token_feasibility"
    ):
        errors.append("dense parallel-search intrinsic candidate filter is invalid")
    canonical_cardinality_limit = evidence.get(
        "canonical_suffix_cardinality_limit"
    )
    if (
        type(canonical_cardinality_limit) is not int
        or canonical_cardinality_limit < 0
        or type(candidate_count) is not int
        or canonical_cardinality_limit > candidate_count
    ):
        errors.append("dense parallel-search canonical suffix limit is invalid")
    if evidence.get("canonical_suffix_cardinality_cap") != (
        PARALLEL_ADMISSION_CANONICAL_SUFFIX_MAX_CARDINALITY
    ):
        errors.append("dense parallel-search canonical suffix cap is invalid")
    if evidence.get("canonical_suffix_cardinality_complete") is not True:
        errors.append("dense parallel-search canonical suffix table is incomplete")
    if evidence.get("state_dominance") != (
        "componentwise_capacity_resources_and_exact_suffix_conflict_inclusion"
    ):
        errors.append("dense parallel-search dominance rule is invalid")
    dominance_applied = evidence.get("state_dominance_applied")
    if type(dominance_applied) is not bool:
        errors.append("dense parallel-search dominance flag is not boolean")
    dominance_prunes = evidence.get("states_pruned_by_dominance")
    if type(dominance_prunes) is not int or dominance_prunes < 0:
        errors.append(
            "dense parallel-search dominance prune count is not a nonnegative integer"
        )
    elif dominance_applied is False and dominance_prunes != 0:
        errors.append("disabled dense parallel-search dominance pruned states")
    if evidence.get("state_dominance_frontier_limit") != (
        PARALLEL_ADMISSION_DOMINANCE_MAX_FRONTIER
    ):
        errors.append("dense parallel-search dominance frontier limit is invalid")
    anytime_triggered = evidence.get("anytime_completion_triggered")
    if type(anytime_triggered) is not bool:
        errors.append("dense parallel-search anytime trigger is not boolean")
    anytime_status = evidence.get("anytime_completion_status")
    if anytime_status not in {"not_needed", "exact", "state_limit_reached"}:
        errors.append("dense parallel-search anytime status is invalid")
    if evidence.get("anytime_state_limit") != PARALLEL_ADMISSION_ANYTIME_STATE_LIMIT:
        errors.append("dense parallel-search anytime state limit is invalid")
    anytime_expanded = evidence.get("anytime_states_expanded")
    anytime_merged = evidence.get(
        "anytime_states_merged_by_future_equivalence"
    )
    anytime_frontier = evidence.get("anytime_frontier_size")
    for value, message in (
        (anytime_expanded, "dense parallel-search anytime expansion count is invalid"),
        (anytime_merged, "dense parallel-search anytime merge count is invalid"),
        (anytime_frontier, "dense parallel-search anytime frontier size is invalid"),
    ):
        if type(value) is not int or value < 0:
            errors.append(message)
    anytime_improved = evidence.get("anytime_improved_selection")
    if type(anytime_improved) is not bool:
        errors.append("dense parallel-search anytime improvement flag is not boolean")
    if anytime_status == "not_needed" and (
        anytime_triggered is not False
        or anytime_expanded != 0
        or anytime_merged != 0
        or anytime_frontier != 0
        or anytime_improved is not False
    ):
        errors.append("dense parallel-search unused anytime evidence is inconsistent")
    if anytime_status == "exact" and (
        anytime_triggered is not True or anytime_frontier != 0
    ):
        errors.append("dense parallel-search exact anytime evidence is inconsistent")
    if anytime_status == "state_limit_reached" and (
        anytime_triggered is not True
        or anytime_expanded != PARALLEL_ADMISSION_ANYTIME_STATE_LIMIT
        or type(anytime_frontier) is not int
        or anytime_frontier <= 0
    ):
        errors.append("dense parallel-search bounded anytime evidence is inconsistent")
    frontier_source = evidence.get("anytime_completion_frontier_source")
    if frontier_source not in {
        "pruned_beam_frontier",
        "root_restart_after_frontier_limit",
    }:
        errors.append("dense parallel-search completion frontier source is invalid")
    discarded_frontier_size = evidence.get("beam_discarded_frontier_size")
    if type(discarded_frontier_size) is not int or discarded_frontier_size < 0:
        errors.append("dense parallel-search discarded frontier size is invalid")
    elif (
        anytime_triggered is True
        and frontier_source == "pruned_beam_frontier"
        and discarded_frontier_size <= 0
    ):
        errors.append("triggered dense parallel-search completion has no frontier")
    discarded_frontier_count = evidence.get(
        "beam_discarded_frontier_state_count"
    )
    discarded_frontier_limit = evidence.get(
        "beam_discarded_frontier_state_limit"
    )
    discarded_frontier_limit_reached = evidence.get(
        "beam_discarded_frontier_limit_reached"
    )
    if (
        type(discarded_frontier_count) is not int
        or discarded_frontier_count < 0
        or type(discarded_frontier_size) is not int
        or discarded_frontier_count < discarded_frontier_size
    ):
        errors.append("dense parallel-search discarded frontier count is invalid")
    if discarded_frontier_limit != PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT:
        errors.append("dense parallel-search discarded frontier limit is invalid")
    if type(discarded_frontier_limit_reached) is not bool:
        errors.append("dense parallel-search discarded frontier limit flag is invalid")
    elif discarded_frontier_limit_reached:
        if (
            frontier_source != "root_restart_after_frontier_limit"
            or discarded_frontier_size != 0
            or type(discarded_frontier_count) is not int
            or discarded_frontier_count
            <= PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT
        ):
            errors.append("dense parallel-search frontier overflow evidence is inconsistent")
    elif (
        frontier_source != "pruned_beam_frontier"
        or discarded_frontier_count != discarded_frontier_size
        or type(discarded_frontier_size) is not int
        or discarded_frontier_size
        > PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT
    ):
        errors.append("dense parallel-search retained frontier evidence is inconsistent")
    if metric.get("equivalent_conflicts") is True:
        if quotient_applied is not True:
            errors.append("equivalent-conflict search did not apply its quotient")
        if type(merged_states) is int and merged_states <= 0:
            errors.append("equivalent-conflict search did not merge any states")
    if metric.get("suffix_neighborhood_conflicts") is True:
        if evidence.get("future_equivalence_basis") != (
            "exact_suffix_conflict_neighborhood"
        ):
            errors.append("suffix-neighborhood search used the wrong quotient basis")
        if type(merged_states) is int and merged_states <= 0:
            errors.append("suffix-neighborhood search did not merge any states")
    objective = evidence.get("objective_value")
    upper_bound = evidence.get("upper_bound_objective_value")
    if (
        not isinstance(objective, list)
        or len(objective) != 4
        or any(type(value) is not int for value in objective)
    ):
        errors.append("dense parallel-search objective is not a four-integer vector")
    if (
        not isinstance(upper_bound, list)
        or len(upper_bound) != 4
        or any(type(value) is not int for value in upper_bound)
    ):
        errors.append("dense parallel-search upper bound is not a four-integer vector")
    elif objective != upper_bound:
        errors.append("dense parallel-search objective does not meet its upper bound")
    beam_objective = evidence.get("beam_objective_value")
    beam_upper_bound = evidence.get("beam_upper_bound_objective_value")
    for value, message in (
        (beam_objective, "dense parallel-search beam objective is invalid"),
        (beam_upper_bound, "dense parallel-search beam upper bound is invalid"),
    ):
        if (
            not isinstance(value, list)
            or len(value) != 4
            or any(type(coordinate) is not int for coordinate in value)
        ):
            errors.append(message)
    if (
        isinstance(beam_objective, list)
        and len(beam_objective) == 4
        and isinstance(objective, list)
        and len(objective) == 4
        and isinstance(beam_upper_bound, list)
        and len(beam_upper_bound) == 4
        and not (beam_objective <= objective <= beam_upper_bound)
    ):
        errors.append("dense parallel-search anytime objective interval is inconsistent")
    beam_discarded_objective = evidence.get(
        "beam_discarded_upper_bound_objective_value"
    )
    beam_discarded_canonical = evidence.get(
        "beam_discarded_canonical_lower_bound_candidate_ids"
    )
    if beam_discarded_objective is not None and (
        not isinstance(beam_discarded_objective, list)
        or len(beam_discarded_objective) != 4
        or any(type(coordinate) is not int for coordinate in beam_discarded_objective)
    ):
        errors.append("dense parallel-search discarded beam objective is invalid")
    if beam_discarded_canonical is not None and (
        not isinstance(beam_discarded_canonical, list)
        or any(not isinstance(value, str) for value in beam_discarded_canonical)
    ):
        errors.append("dense parallel-search discarded beam canonical bound is invalid")
    if (beam_discarded_objective is None) != (beam_discarded_canonical is None):
        errors.append("dense parallel-search discarded beam bounds are incomplete")
    selected_ids = evidence.get("selected_companion_ids")
    if not isinstance(selected_ids, list) or any(
        not isinstance(value, str) for value in selected_ids
    ):
        errors.append("dense parallel-search selected candidate IDs are invalid")
    elif (
        isinstance(discarded_canonical_bound, list)
        and discarded_objective_bound == objective
        and discarded_canonical_bound < selected_ids
    ):
        errors.append("dense parallel-search discarded canonical bound beats selection")
    if (
        isinstance(objective, list)
        and len(objective) == 4
        and type(objective[2]) is int
        and type(metric.get("selected_companion_count")) is int
        and objective[2] != metric["selected_companion_count"]
    ):
        errors.append("dense parallel-search selected count disagrees with its objective")
    if evidence.get("upper_bound_relaxation") != (
        "primary_conflicts_minimum_token_resources_class_certification_"
        "filtered_mixed_route_target_cliques_and_exact_suffix_conflict_"
        "neighborhoods"
    ):
        errors.append("dense parallel-search evidence used the wrong upper-bound relaxation")
    return errors


def _latency_summary(samples_ms: list[float]) -> dict[str, float]:
    return {
        "mean_ms": round(statistics.fmean(samples_ms), 4),
        "median_ms": round(statistics.median(samples_ms), 4),
        "p95_ms": round(_percentile(samples_ms, 0.95), 4),
        "p99_ms": round(_percentile(samples_ms, 0.99), 4),
        "max_ms": round(max(samples_ms), 4),
    }


def _deferral_history_benchmark(
    *, iterations: int, warmup: int, candidate_count: int, run_count: int
) -> dict[str, object]:
    if candidate_count <= 0 or run_count <= 0:
        raise ValueError("history candidate and run counts must be positive")
    generated = [
        (
            f"policy-{index:03d}",
            {"mode": "prove", "target_id": f"claim-{index:03d}"},
        )
        for index in range(candidate_count)
    ]
    trace_text = json.dumps(
        {
            "candidates": [
                {
                    "candidate_id": f"benchmark:policy-{index:03d}",
                    "admissible": True,
                    "disposition": "rejected_by_ordinal_comparison",
                }
                for index in range(candidate_count)
            ]
        },
        separators=(",", ":"),
    )
    state = {
        "recent_runs": [
            {"decision_trace_json": trace_text} for _ in range(run_count)
        ]
    }
    for _ in range(warmup):
        _generated_policy_deferrals(state, "benchmark", generated)
    samples_ms: list[float] = []
    counts: dict[str, int] = {}
    for _ in range(iterations):
        started = time.perf_counter_ns()
        counts = _generated_policy_deferrals(state, "benchmark", generated)
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
    return {
        "benchmark": "bounded_deferral_history",
        "iterations": iterations,
        "warmup": warmup,
        "candidate_count": candidate_count,
        "run_count": run_count,
        "trace_json_bytes": len(trace_text.encode("utf-8")),
        "observed_deferral_count": min(counts.values()),
        **_latency_summary(samples_ms),
    }


def _durable_deferral_state_benchmark(
    *, iterations: int, warmup: int, candidate_count: int, deferral_count: int
) -> dict[str, object]:
    """Measure the authenticated compact-state path used in production."""

    if candidate_count <= 0 or deferral_count < 0:
        raise ValueError(
            "durable fairness candidates must be positive and count nonnegative"
        )
    generated = [
        (
            f"policy-{index:03d}",
            {"mode": "prove", "target_id": f"claim-{index:03d}"},
        )
        for index in range(candidate_count)
    ]
    state = {
        "decision_candidate_deferrals": {
            f"benchmark:policy-{index:03d}": deferral_count
            for index in range(candidate_count)
        },
        # A populated legacy history must not be parsed when compact state is
        # present. This sentinel would fail if treated as a valid trace row.
        "recent_runs": [{"decision_trace_json": "not-json"}],
    }
    for _ in range(warmup):
        _generated_policy_deferrals(state, "benchmark", generated)
    samples_ms: list[float] = []
    counts: dict[str, int] = {}
    for _ in range(iterations):
        started = time.perf_counter_ns()
        counts = _generated_policy_deferrals(state, "benchmark", generated)
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
    return {
        "benchmark": "durable_deferral_state",
        "iterations": iterations,
        "warmup": warmup,
        "candidate_count": candidate_count,
        "observed_deferral_count": min(counts.values()),
        **_latency_summary(samples_ms),
    }


def _durable_dispatch_benchmark(*, iterations: int, warmup: int) -> dict[str, object]:
    """Measure crash-durable scheduler commit cost over a growing journal."""

    if iterations <= 0 or warmup < 0:
        raise ValueError("dispatch iterations must be positive and warmup nonnegative")
    with tempfile.TemporaryDirectory(
        prefix="albilich-scheduler-dispatch-benchmark-"
    ) as tmpdir:
        store = ProofStateStore(
            "scheduler-dispatch-benchmark",
            generation_root=Path(tmpdir) / "generation",
        )
        store.init_problem("Prove the dispatch benchmark theorem.")
        samples_ms: list[float] = []
        decision_samples_ms: list[float] = []
        attempt_samples_ms: list[float] = []
        result_samples_ms: list[float] = []
        completion_samples_ms: list[float] = []
        for index in range(warmup + iterations):
            decision_started = time.perf_counter_ns()
            action = next_action(store, web_search="disabled")
            decision_elapsed_ms = (
                time.perf_counter_ns() - decision_started
            ) / 1_000_000.0
            heads = store.audit_chain_heads()
            started = time.perf_counter_ns()
            dispatches, _ = _record_scheduler_dispatches(
                store,
                [action],
                heads,
                execution_contract={
                    "version": 1,
                    "driver": "builtin_codex",
                    "identity": "codex:benchmark",
                    "recovery_capability": "supervised_process",
                },
            )
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
            if index >= warmup:
                decision_samples_ms.append(decision_elapsed_ms)
                samples_ms.append(elapsed_ms)
            dispatch = dispatches[0]
            session_plan = {
                "actor_role": dispatch["actor_role"],
                "mode": dispatch["mode"],
                "target_id": dispatch["target_id"],
                "route_id": dispatch["route_id"],
                "state_revision": store.get_revision(),
                "scheduler_decision_state_revision": dispatch[
                    "decision_state_revision"
                ],
                "scheduler_dispatch_id": dispatch["dispatch_id"],
                "dispatched_action_hash": dispatch["dispatched_action_hash"],
                "context_hash": "",
                "search_intent": str(action.get("search_intent") or ""),
                "strategy_family": strategy_family(action),
                "model_profile": "default",
                "web_search": "disabled",
            }
            scheduled_item = {
                "action": action,
                "session_plan": session_plan,
                "session_web_search": "disabled",
                "is_companion": False,
            }
            attempt_started = time.perf_counter_ns()
            _record_scheduler_attempts(store, [scheduled_item])
            attempt_elapsed_ms = (
                time.perf_counter_ns() - attempt_started
            ) / 1_000_000.0
            execution = {
                "run_id": f"dispatch-benchmark-run-{index:05d}",
                "actor_role": dispatch["actor_role"],
                "status": "failed",
                "returncode": 1,
                "wall_time_seconds": 0.0,
                "peak_memory_mb": 0.0,
                "usage": {},
                "session_id": "",
                "patch": None,
                "patch_error": "synthetic benchmark result",
                "output_artifact_ids": [],
                "model": "benchmark",
                "reasoning_effort": "none",
                "sandbox": "none",
                "web_search": "disabled",
                "failure_kind": "benchmark",
            }
            scheduled_item["execution"] = execution
            result_started = time.perf_counter_ns()
            _record_scheduler_result(
                store,
                scheduled_item,
                validation_errors=[],
            )
            result_elapsed_ms = (
                time.perf_counter_ns() - result_started
            ) / 1_000_000.0
            if index >= warmup:
                attempt_samples_ms.append(attempt_elapsed_ms)
                result_samples_ms.append(result_elapsed_ms)
            completion_started = time.perf_counter_ns()
            metrics_operation = run_metrics_operation(
                run_id=f"dispatch-benchmark-run-{index:05d}",
                action=action,
                session_plan=session_plan,
                usage_payload={},
                status="failed",
                model="benchmark",
            )
            metrics_operation.update(
                {
                    "reasoning_effort": "none",
                    "search_setting": "disabled",
                    "sandbox_setting": "none",
                    "failure_kind": "benchmark",
                    "output_artifact_ids": [],
                }
            )
            completion = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "scheduler",
                    "target_id": str(action.get("target_id") or "root"),
                    "operations": [metrics_operation],
                    "rationale": "complete the scheduler dispatch benchmark row",
                },
            )
            completion_elapsed_ms = (
                time.perf_counter_ns() - completion_started
            ) / 1_000_000.0
            if not completion.accepted:
                raise RuntimeError(
                    "dispatch benchmark completion was rejected: "
                    + "; ".join(completion.errors)
                )
            if index >= warmup:
                completion_samples_ms.append(completion_elapsed_ms)
        with store.connect() as conn:
            dispatch_count = int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM scheduler_dispatches"
                ).fetchone()["count"]
            )
            run_count = int(
                conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()[
                    "count"
                ]
            )
            attempt_count = int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM scheduler_dispatch_attempts"
                ).fetchone()["count"]
            )
            result_count = int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM scheduler_dispatch_results"
                ).fetchone()["count"]
            )
        tail_window = min(50, iterations)
        return {
            "benchmark": "durable_scheduler_dispatch",
            "iterations": iterations,
            "warmup": warmup,
            "dispatch_count": dispatch_count,
            "run_count": run_count,
            "attempt_count": attempt_count,
            "result_count": result_count,
            "decision": _latency_summary(decision_samples_ms),
            "attempt_claim": _latency_summary(attempt_samples_ms),
            "result_record": _latency_summary(result_samples_ms),
            "completion": _latency_summary(completion_samples_ms),
            "long_history_tail": {
                "window": tail_window,
                "decision": _latency_summary(decision_samples_ms[-tail_window:]),
                "dispatch": _latency_summary(samples_ms[-tail_window:]),
                "attempt_claim": _latency_summary(
                    attempt_samples_ms[-tail_window:]
                ),
                "result_record": _latency_summary(
                    result_samples_ms[-tail_window:]
                ),
                "completion": _latency_summary(
                    completion_samples_ms[-tail_window:]
                ),
            },
            **_latency_summary(samples_ms),
        }


def _seed_large_valid_state(
    store: ProofStateStore,
    *,
    claim_count: int,
    parent_chain: bool = False,
) -> float:
    """Populate an invariant-valid proof graph through the patch kernel."""

    if claim_count <= 0:
        raise ValueError("large-state claim count must be positive")
    started = time.perf_counter()
    operations: list[dict[str, object]] = []
    for index in range(claim_count):
        claim_id = f"benchmark-lemma-{index:05d}"
        route_id = f"benchmark-route-{index:05d}"
        parent_id = (
            f"benchmark-lemma-{index - 1:05d}"
            if parent_chain and index > 0
            else "root"
        )
        operations.extend(
            [
                {
                    "op": "add_claim",
                    "claim_id": claim_id,
                    "kind": "lemma",
                    "statement": f"Benchmark lemma {index} holds.",
                    "parent_ids": [parent_id],
                    "root_impact": 0.25 + (index % 50) / 100.0,
                    "reduction_depth": index + 1 if parent_chain else 1,
                },
                {
                    "op": "add_route",
                    "route_id": route_id,
                    "conclusion_claim_id": claim_id,
                    "relation_to_parent": "sufficient",
                    "strategy": f"Benchmark route {index} requires a proof.",
                },
                {
                    "op": "add_proof_obligation",
                    "proof_obligation_id": f"benchmark-obligation-{index:05d}",
                    "owner_type": "claim",
                    "owner_id": claim_id,
                    "obligation_type": "conceptual_question",
                    "severity": "minor",
                    "status": "active",
                    "obligation": f"Resolve the local condition in benchmark lemma {index}.",
                    "suggested_next_target": claim_id,
                },
            ]
        )
        if len(operations) >= 510 or index == claim_count - 1:
            outcome = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": operations,
                    "rationale": "seed an invariant-valid scheduler scale benchmark",
                },
            )
            if not outcome.accepted:
                raise RuntimeError(
                    "large-state benchmark fixture was rejected: "
                    + "; ".join(outcome.errors)
                )
            operations = []
    return time.perf_counter() - started


def _large_state_benchmark(
    *,
    iterations: int,
    warmup: int,
    claim_count: int,
    parent_chain: bool = False,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(
        prefix="albilich-scheduler-large-state-benchmark-"
    ) as tmpdir:
        store = ProofStateStore(
            "scheduler-large-state-benchmark",
            generation_root=Path(tmpdir) / "generation",
        )
        store.init_problem("Prove the large-state benchmark theorem.")
        setup_seconds = _seed_large_valid_state(
            store,
            claim_count=claim_count,
            parent_chain=parent_chain,
        )
        for _ in range(warmup):
            next_action(store, web_search="disabled")
        samples_ms: list[float] = []
        action: dict[str, object] = {}
        for _ in range(iterations):
            started = time.perf_counter_ns()
            action = next_action(store, web_search="disabled")
            samples_ms.append(
                (time.perf_counter_ns() - started) / 1_000_000.0
            )
        return {
            "benchmark": (
                "deep_valid_proof_state"
                if parent_chain
                else "wide_valid_proof_state"
            ),
            "iterations": iterations,
            "warmup": warmup,
            "claim_count": claim_count,
            "route_count": claim_count,
            "proof_obligation_count": claim_count,
            "setup_seconds": round(setup_seconds, 4),
            "selected_mode": str(action.get("mode") or ""),
            "selected_target_id": str(action.get("target_id") or ""),
            **_latency_summary(samples_ms),
        }


def _dense_verification_state(route_count: int) -> dict[str, object]:
    """Build a dense, verifier-ready snapshot without timing fixture setup."""
    if route_count <= 0:
        raise ValueError("dense verification route count must be positive")
    claims: list[dict[str, object]] = [
        {
            "claim_id": "root",
            "parent_ids_json": "[]",
            "lifecycle_status": "active",
            "validation_status": "plausible",
            "root_impact": 1.0,
        }
    ]
    routes: list[dict[str, object]] = []
    inferences: list[dict[str, object]] = []
    artifacts: list[dict[str, object]] = []
    for index in range(route_count):
        claim_id = f"verification-lemma-{index:05d}"
        route_id = f"verification-route-{index:05d}"
        inference_id = f"verification-inference-{index:05d}"
        artifact_id = f"verification-proof-{index:05d}"
        claims.append(
            {
                "claim_id": claim_id,
                "parent_ids_json": '["root"]',
                "lifecycle_status": "active",
                "validation_status": "plausible",
                "root_impact": 0.75,
            }
        )
        routes.append(
            {
                "route_id": route_id,
                "conclusion_claim_id": claim_id,
                "status": "active",
                "relation_to_parent": "sufficient",
                "strategy": "Apply the route-local proof dossier.",
                "evidence_artifact_ids_json": json.dumps([artifact_id]),
            }
        )
        inferences.append(
            {
                "inference_id": inference_id,
                "route_id": route_id,
                "conclusion_claim_id": claim_id,
                "premise_claim_ids": [],
                "validation_status": "plausible",
                "explanation": "The dossier proves the benchmark lemma.",
                "evidence_artifact_ids_json": json.dumps([artifact_id]),
            }
        )
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": "proof_dossier",
                "producer_role": "researcher",
                "state_revision": 1,
                "content_summary": "Verifier-ready route-local proof.",
                "metadata_json": json.dumps(
                    {"target_id": claim_id, "ready_for_verifier": True}
                ),
            }
        )
    return {
        "problem_state": {"current_revision": 1},
        "claims": claims,
        "routes": routes,
        "inferences": inferences,
        "research_artifacts": artifacts,
        "debts": [],
        "recent_runs": [],
        "retrieval_cards": [],
        "theorem_library_entries": [],
    }


def _dense_verification_benchmark(
    *, iterations: int, warmup: int, route_count: int
) -> dict[str, object]:
    state = _dense_verification_state(route_count)

    def plan() -> dict[str, object]:
        _enable_scheduler_planning_cache(state)
        action = _verification_handoff_action(
            None,
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="balanced",
            web_search="disabled",
        )
        if action is None:
            raise RuntimeError("dense verification fixture produced no action")
        return action

    for _ in range(warmup):
        plan()
    samples_ms: list[float] = []
    action: dict[str, object] = {}
    for _ in range(iterations):
        started = time.perf_counter_ns()
        action = plan()
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
    trace = action.get("_base_policy_trace") or {}
    validation_samples_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        errors = decision_trace_errors(trace)
        validation_samples_ms.append(
            (time.perf_counter_ns() - started) / 1_000_000.0
        )
        if errors:
            raise RuntimeError(
                "dense verification trace failed validation: "
                + "; ".join(errors)
            )
    trace_text = json.dumps(trace, separators=(",", ":"))
    trace_bytes = len(trace_text.encode("utf-8"))
    included_trace_count = max(
        1,
        min(
            SCHEDULER_RECENT_RUN_LIMIT,
            SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT // trace_bytes,
        ),
    )
    state["recent_runs"] = [
        {
            "decision_trace_json": trace_text,
            "decision_trace_history_included": True,
        }
        for _ in range(included_trace_count)
    ] + [
        {
            "decision_trace_json": "{}",
            "decision_trace_history_included": False,
        }
        for _ in range(
            SCHEDULER_RECENT_RUN_LIMIT - included_trace_count
        )
    ]
    history_samples_ms: list[float] = []
    for _ in range(min(iterations, 10)):
        started = time.perf_counter_ns()
        plan()
        history_samples_ms.append(
            (time.perf_counter_ns() - started) / 1_000_000.0
        )
    return {
        "benchmark": "dense_verification_candidate_enumeration",
        "iterations": iterations,
        "warmup": warmup,
        "claim_count": route_count + 1,
        "route_count": route_count,
        "inference_count": route_count,
        "artifact_count": route_count,
        "candidate_count": len(trace.get("candidates") or []),
        "candidate_set_complete": bool(trace.get("candidate_set_complete")),
        "trace_validation": _latency_summary(validation_samples_ms),
        "bounded_history_replay": {
            "population_count": SCHEDULER_RECENT_RUN_LIMIT,
            "included_trace_count": included_trace_count,
            "trace_bytes": trace_bytes,
            "byte_limit": SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT,
            **_latency_summary(history_samples_ms),
        },
        **_latency_summary(samples_ms),
    }


def _dense_evidence_state(object_count: int) -> dict[str, object]:
    """Build equally sized evidence queues without timing fixture creation."""
    if object_count <= 0:
        raise ValueError("dense evidence object count must be positive")
    debts: list[dict[str, object]] = []
    artifacts: list[dict[str, object]] = []
    cards: list[dict[str, object]] = []
    for index in range(object_count):
        suffix = f"{index:05d}"
        debts.append(
            {
                "debt_id": f"evidence-citation-{suffix}",
                "owner_type": "claim",
                "owner_id": "root",
                "debt_type": "missing_reference",
                "severity": "blocking",
                "status": "active",
                "obligation": f"Locate exact benchmark theorem {suffix}.",
            }
        )
        artifacts.extend(
            [
                {
                    "artifact_id": f"evidence-source-{suffix}",
                    "artifact_type": "source_adaptation_notes",
                    "state_revision": index + 1,
                    "created_at": f"2026-01-01T00:00:{index % 60:02d}+00:00",
                    "metadata_json": {"target_id": "root"},
                },
                {
                    "artifact_id": f"evidence-proof-{suffix}",
                    "artifact_type": "proof_dossier",
                    "state_revision": object_count + index + 1,
                    "content_summary": "Verifier-ready benchmark proof candidate.",
                    "metadata_json": {
                        "proof_candidate": True,
                        "target_id": "root",
                    },
                },
            ]
        )
        cards.extend(
            [
                {
                    "card_id": f"evidence-external-{suffix}",
                    "applicability_json": {
                        "target_id": "root",
                        "classification": "direct_match",
                        "implication_to_target_verified": True,
                        "program_victory_candidate": True,
                    },
                    "missing_hypotheses_json": [],
                },
                {
                    "card_id": f"evidence-audit-{suffix}",
                    "applicability_json": {
                        "target_id": "root",
                        "classification": "conditional_match",
                    },
                    "missing_hypotheses_json": ["definition mismatch"],
                },
            ]
        )
    return {
        "problem_state": {"current_revision": object_count * 2},
        "claims": [
            {
                "claim_id": "root",
                "parent_ids_json": [],
                "lifecycle_status": "active",
                "validation_status": "plausible",
                "root_impact": 1.0,
            }
        ],
        "routes": [],
        "inferences": [],
        "research_artifacts": artifacts,
        "debts": debts,
        "recent_runs": [],
        "retrieval_cards": cards,
        "theorem_library_entries": [],
    }


def _dense_evidence_benchmark(
    *, iterations: int, warmup: int, object_count: int
) -> dict[str, object]:
    state = _dense_evidence_state(object_count)

    def plan() -> dict[str, object]:
        _enable_scheduler_planning_cache(state)
        action = _evidence_assimilation_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="balanced",
            web_search="disabled",
            parent_implication_ready=False,
        )
        if action is None:
            raise RuntimeError("dense evidence fixture produced no action")
        return action

    for _ in range(warmup):
        plan()
    samples_ms: list[float] = []
    action: dict[str, object] = {}
    for _ in range(iterations):
        started = time.perf_counter_ns()
        action = plan()
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
    trace = action.get("_base_policy_trace") or {}
    validation_samples_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        errors = decision_trace_errors(trace)
        validation_samples_ms.append(
            (time.perf_counter_ns() - started) / 1_000_000.0
        )
        if errors:
            raise RuntimeError(
                "dense evidence trace failed validation: " + "; ".join(errors)
            )
    trace_text = json.dumps(trace, separators=(",", ":"))
    trace_bytes = len(trace_text.encode("utf-8"))
    included_trace_count = max(
        1,
        min(
            SCHEDULER_RECENT_RUN_LIMIT,
            SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT // trace_bytes,
        ),
    )
    state["recent_runs"] = [
        {
            "decision_trace_json": trace_text,
            "decision_trace_history_included": True,
        }
        for _ in range(included_trace_count)
    ] + [
        {
            "decision_trace_json": "{}",
            "decision_trace_history_included": False,
        }
        for _ in range(SCHEDULER_RECENT_RUN_LIMIT - included_trace_count)
    ]
    history_samples_ms: list[float] = []
    for _ in range(min(iterations, 10)):
        started = time.perf_counter_ns()
        plan()
        history_samples_ms.append(
            (time.perf_counter_ns() - started) / 1_000_000.0
        )
    return {
        "benchmark": "dense_evidence_candidate_enumeration",
        "iterations": iterations,
        "warmup": warmup,
        "objects_per_queue": object_count,
        "proof_obligation_count": object_count,
        "artifact_count": object_count * 2,
        "retrieval_card_count": object_count * 2,
        "candidate_count": len(trace.get("candidates") or []),
        "candidate_set_complete": bool(trace.get("candidate_set_complete")),
        "trace_validation": _latency_summary(validation_samples_ms),
        "bounded_history_replay": {
            "population_count": SCHEDULER_RECENT_RUN_LIMIT,
            "included_trace_count": included_trace_count,
            "trace_bytes": trace_bytes,
            "byte_limit": SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT,
            **_latency_summary(history_samples_ms),
        },
        **_latency_summary(samples_ms),
    }


def _dense_obligation_state(object_count: int) -> dict[str, object]:
    """Build equal routing queues without timing fixture construction."""

    if object_count <= 0:
        raise ValueError("dense obligation object count must be positive")
    claims: list[dict[str, object]] = [
        {
            "claim_id": "root",
            "statement": "Benchmark root theorem.",
            "hypotheses": "",
            "parent_ids_json": "[]",
            "evidence_artifact_ids_json": "[]",
            "root_impact": 1.0,
            "reduction_depth": 0,
            "validation_status": "untested",
            "lifecycle_status": "active",
        }
    ]
    routes: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []
    artifacts: list[dict[str, object]] = []
    for index in range(object_count):
        suffix = f"{index:05d}"
        claim_id = f"obligation-lemma-{suffix}"
        route_id = f"obligation-route-{suffix}"
        claims.append(
            {
                "claim_id": claim_id,
                "statement": f"Benchmark routing lemma {index}.",
                "hypotheses": "",
                "parent_ids_json": '["root"]',
                "evidence_artifact_ids_json": "[]",
                "root_impact": 0.8,
                "reduction_depth": 1,
                "validation_status": "untested",
                "lifecycle_status": "active",
            }
        )
        routes.append(
            {
                "route_id": route_id,
                "conclusion_claim_id": claim_id,
                "relation_to_parent": "sufficient",
                "status": "active",
                "evidence_artifact_ids_json": "[]",
            }
        )
        obligations.append(
            {
                "debt_id": f"routing-obligation-{suffix}",
                "owner_type": "claim",
                "owner_id": claim_id,
                "suggested_next_target": claim_id,
                "debt_type": "gap",
                "severity": "blocking",
                "status": "active",
                "obligation": f"Prove distinct routing lemma {index}.",
                "source_artifact_ids_json": "[]",
                "repeated_count": 0,
                "last_seen": f"2026-01-01T00:{index % 60:02d}:00Z",
            }
        )
        artifacts.extend(
            [
                {
                    "artifact_id": f"routing-request-{suffix}",
                    "artifact_type": "literature_search_request",
                    "state_revision": index + 1,
                    "content_summary": f"Find exact routing theorem {index}.",
                    "metadata_json": {
                        "search_request_id": f"routing-search-{suffix}",
                        "target_id": claim_id,
                        "route_id": route_id,
                        "query": f"Exact routing theorem {index}",
                    },
                },
                {
                    "artifact_id": f"routing-decision-{suffix}",
                    "artifact_type": "proof_dossier",
                    "state_revision": object_count + index + 1,
                    "content_summary": "A route-killing obstruction gives a route decision.",
                    "metadata_json": {
                        "target_id": claim_id,
                        "route_id": route_id,
                        "classification": "route_killing_obstruction",
                        "route_decision": "pause",
                    },
                },
                {
                    "artifact_id": f"routing-obstruction-{suffix}",
                    "artifact_type": "route_obstruction",
                    "state_revision": object_count * 2 + index + 1,
                    "content_summary": "Independent route obstruction.",
                    "metadata_json": {"target_id": claim_id, "route_id": route_id},
                },
                {
                    "artifact_id": f"routing-failed-plan-{suffix}",
                    "artifact_type": "failed_decomposition_plan",
                    "state_revision": object_count * 3 + index + 1,
                    "metadata_json": {
                        "target_id": claim_id,
                        "route_id": route_id,
                        "decomposition_plan_id": f"routing-plan-{suffix}",
                    },
                },
            ]
        )
    return {
        "problem_state": {"current_revision": object_count * 4},
        "claims": claims,
        "routes": routes,
        "inferences": [],
        "debts": obligations,
        "research_artifacts": artifacts,
        "recent_runs": [],
        "retrieval_cards": [],
        "theorem_library_entries": [],
    }


def _dense_obligation_benchmark(
    *, iterations: int, warmup: int, object_count: int
) -> dict[str, object]:
    state = _dense_obligation_state(object_count)

    def plan() -> dict[str, object]:
        _enable_scheduler_planning_cache(state)
        action = _obligation_routing_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="balanced",
            web_search="disabled",
            active_trunk_pressure={"over_trunk_cap": False},
            frontier_pressure={},
        )
        if action is None:
            raise RuntimeError("dense obligation fixture produced no action")
        return action

    for _ in range(warmup):
        plan()
    samples_ms: list[float] = []
    action: dict[str, object] = {}
    for _ in range(iterations):
        started = time.perf_counter_ns()
        action = plan()
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
    trace = action.get("_base_policy_trace") or {}
    validation_samples_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        errors = decision_trace_errors(trace)
        validation_samples_ms.append(
            (time.perf_counter_ns() - started) / 1_000_000.0
        )
        if errors:
            raise RuntimeError(
                "dense obligation trace failed validation: " + "; ".join(errors)
            )
    trace_text = json.dumps(trace, separators=(",", ":"))
    trace_bytes = len(trace_text.encode("utf-8"))
    included_trace_count = max(
        1,
        min(
            SCHEDULER_RECENT_RUN_LIMIT,
            SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT // trace_bytes,
        ),
    )
    state["recent_runs"] = [
        {
            "decision_trace_json": trace_text,
            "decision_trace_history_included": True,
        }
        for _ in range(included_trace_count)
    ] + [
        {
            "decision_trace_json": "{}",
            "decision_trace_history_included": False,
        }
        for _ in range(SCHEDULER_RECENT_RUN_LIMIT - included_trace_count)
    ]
    history_samples_ms: list[float] = []
    for _ in range(min(iterations, 10)):
        started = time.perf_counter_ns()
        plan()
        history_samples_ms.append(
            (time.perf_counter_ns() - started) / 1_000_000.0
        )
    return {
        "benchmark": "dense_obligation_candidate_enumeration",
        "iterations": iterations,
        "warmup": warmup,
        "objects_per_queue": object_count,
        "claim_count": object_count + 1,
        "route_count": object_count,
        "proof_obligation_count": object_count,
        "artifact_count": object_count * 4,
        "candidate_count": len(trace.get("candidates") or []),
        "candidate_set_complete": bool(trace.get("candidate_set_complete")),
        "trace_validation": _latency_summary(validation_samples_ms),
        "bounded_history_replay": {
            "population_count": SCHEDULER_RECENT_RUN_LIMIT,
            "included_trace_count": included_trace_count,
            "trace_bytes": trace_bytes,
            "byte_limit": SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT,
            **_latency_summary(history_samples_ms),
        },
        **_latency_summary(samples_ms),
    }


def _dense_parallel_search_benchmark(
    *,
    iterations: int,
    warmup: int,
    candidate_count: int,
    resource_constrained: bool = False,
    sibling_clique: bool = False,
    equivalent_conflicts: bool = False,
    suffix_neighborhood_conflicts: bool = False,
) -> dict[str, object]:
    """Measure the bounded non-greedy admission transition directly."""

    if iterations <= 0 or warmup < 0 or candidate_count <= 0:
        raise ValueError("dense parallel-search benchmark inputs are invalid")
    action_classes = (
        "integration",
        "verification",
        "literature",
        "adversarial",
        "research",
    )
    modes = {
        "integration": "integrate",
        "verification": "prove",
        "literature": "retrieve",
        "adversarial": "refute",
        "research": "reduce",
    }
    equivalence_specifications = (
        ("integration", "t2", "r2", 5),
        ("verification", "t0", "r0", 5),
        ("adversarial", "t2", "r3", 5),
        ("adversarial", "t3", "r2", 5),
        ("research", "t1", "r3", 5),
        ("verification", "t1", "r1", 3),
        ("adversarial", "t0", "r3", 3),
        ("research", "t1", "r1", 3),
        ("research", "t1", "r2", 3),
        ("integration", "t3", "r1", 0),
        ("verification", "t3", "r3", 0),
        ("research", "t2", "r0", 0),
    )
    neighborhood_specifications = (
        ("integration", "t2", "r3", 5),
        ("integration", "t3", "r6", 5),
        ("integration", "t8", "r9", 5),
        ("literature", "t1", "r8", 5),
        ("literature", "t2", "r5", 5),
        ("literature", "t5", "r5", 5),
        ("literature", "t7", "r1", 5),
        ("adversarial", "t8", "r7", 5),
        ("research", "t1", "r5", 5),
        ("research", "t11", "r5", 5),
        ("research", "t2", "r11", 5),
        ("research", "t3", "r4", 5),
    )

    def row(index: int, action_class: str) -> dict[str, object]:
        if suffix_neighborhood_conflicts:
            action_class, target_id, route_id, deferrals = (
                neighborhood_specifications[index % len(neighborhood_specifications)]
            )
        elif equivalent_conflicts:
            action_class, target_id, route_id, deferrals = (
                equivalence_specifications[index % len(equivalence_specifications)]
            )
        else:
            target_id = f"target-{index % 509:04d}"
            route_id = (
                "shared-clique-route"
                if sibling_clique
                else f"route-{index % 503:04d}"
            )
            deferrals = PARALLEL_WAVE_DEFERRAL_LIMIT if index % 4 == 0 else 0
        candidate_id = f"parallel:{index + 1:024x}"
        identity = (
            action_class,
            modes[action_class],
            target_id,
            route_id,
            "dense_parallel_search",
            "",
            "{}",
            f"{index + 1:064x}",
        )
        return {
            "candidate_id": candidate_id,
            "admission_priority": parallel_admission_priority_for(
                action_class, "dense_parallel_search"
            ),
            "action_class": action_class,
            "mode": modes[action_class],
            "target_id": identity[2],
            "route_id": identity[3],
            "search_intent": identity[4],
            "semantic_identity": list(identity),
            "consecutive_deferrals": deferrals,
            "deferral_limit": PARALLEL_WAVE_DEFERRAL_LIMIT,
            "budget_allowed": True,
            "requested_tokens": 20_000 if resource_constrained else 0,
            "comparison_action_sha256": f"{index + 1:064x}",
        }

    primary = row(-1, "research")
    primary.update(
        candidate_id="parallel:primary",
        admission_priority=1_000_000,
        action_class=(
            "advisory"
            if equivalent_conflicts or suffix_neighborhood_conflicts
            else "research"
        ),
        mode=(
            "triage_routes"
            if equivalent_conflicts or suffix_neighborhood_conflicts
            else "reduce"
        ),
        target_id="benchmark-primary",
        route_id="benchmark-primary-route",
        semantic_identity=[
            (
                "advisory"
                if equivalent_conflicts or suffix_neighborhood_conflicts
                else "research"
            ),
            (
                "triage_routes"
                if equivalent_conflicts or suffix_neighborhood_conflicts
                else "reduce"
            ),
            "benchmark-primary",
            "benchmark-primary-route",
            "dense_parallel_search",
            "",
            "{}",
            "0" * 64,
        ],
        consecutive_deferrals=0,
        deferral_limit=0,
        requested_tokens=0,
    )
    candidates = [
        row(
            index,
            "research"
            if sibling_clique
            or equivalent_conflicts
            or suffix_neighborhood_conflicts
            else action_classes[index % len(action_classes)],
        )
        for index in range(candidate_count)
    ]
    candidates.sort(key=parallel_admission_order_key)
    rows = [primary, *candidates]
    capacities = {
        "research_or_adversarial": 3 if equivalent_conflicts else 5,
        "verification": 3 if equivalent_conflicts else 5,
        "integration": 3 if equivalent_conflicts else 5,
        "literature": 1,
        "advisory": 1,
    }
    metadata: dict[str, object] = {}
    for _ in range(warmup):
        parallel_admission_outcomes(
            rows,
            total_capacity=(
                7
                if suffix_neighborhood_conflicts
                else 6
                if equivalent_conflicts
                else 7
            ),
            class_capacities=capacities,
            aggregate_budget_enforced=resource_constrained,
            initial_remaining_token_budget=20_000 if resource_constrained else 0,
            initial_reserved_verification_budget=(
                10_000 if resource_constrained else 0
            ),
            search_metadata_out=metadata,
        )
    samples_ms: list[float] = []
    outcomes = {}
    for _ in range(iterations):
        started = time.perf_counter_ns()
        outcomes, _remaining = parallel_admission_outcomes(
            rows,
            total_capacity=(
                7
                if suffix_neighborhood_conflicts
                else 6
                if equivalent_conflicts
                else 7
            ),
            class_capacities=capacities,
            aggregate_budget_enforced=resource_constrained,
            initial_remaining_token_budget=20_000 if resource_constrained else 0,
            initial_reserved_verification_budget=(
                10_000 if resource_constrained else 0
            ),
            search_metadata_out=metadata,
        )
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
    metric = {
        "benchmark": (
            "dense_parallel_resource_fixed_width_search"
            if resource_constrained
            else "dense_parallel_suffix_neighborhood_fixed_width_search"
            if suffix_neighborhood_conflicts
            else "dense_parallel_equivalent_conflict_fixed_width_search"
            if equivalent_conflicts
            else "dense_parallel_route_clique_fixed_width_search"
            if sibling_clique
            else "dense_parallel_fixed_width_search"
        ),
        "resource_constrained": resource_constrained,
        "sibling_clique": sibling_clique,
        "equivalent_conflicts": equivalent_conflicts,
        "suffix_neighborhood_conflicts": suffix_neighborhood_conflicts,
        "policy_version": PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
        "iterations": iterations,
        "warmup": warmup,
        "candidate_count": candidate_count,
        "beam_width": metadata.get("beam_width"),
        "selected_companion_count": sum(
            outcome.disposition == "selected" for outcome in outcomes.values()
        ),
        "search_evidence": dict(metadata),
        **_latency_summary(samples_ms),
    }
    metric["certificate_errors"] = _dense_parallel_certificate_errors(metric)
    return metric


def benchmark(
    *,
    iterations: int,
    warmup: int,
    history_candidates: int = 64,
    history_runs: int = 96,
    large_state_claims: int = 512,
    large_state_iterations: int = 50,
    deep_state_claims: int = 512,
    deep_state_iterations: int = 50,
    dense_verification_routes: int = 512,
    dense_verification_iterations: int = 30,
    dense_evidence_objects: int = 256,
    dense_evidence_iterations: int = 30,
    dense_obligation_objects: int = 256,
    dense_obligation_iterations: int = 30,
    dense_parallel_candidates: int = 512,
    dense_parallel_iterations: int = 20,
    dense_parallel_resource_candidates: int = 512,
    dense_parallel_resource_iterations: int = 20,
    dense_parallel_clique_candidates: int = 512,
    dense_parallel_clique_iterations: int = 20,
    dense_parallel_equivalence_candidates: int = 512,
    dense_parallel_equivalence_iterations: int = 20,
    dense_parallel_neighborhood_iterations: int = 20,
    dispatch_iterations: int = 20,
) -> dict[str, object]:
    if iterations <= 0 or warmup < 0:
        raise ValueError("iterations must be positive and warmup must be nonnegative")
    with tempfile.TemporaryDirectory(prefix="albilich-scheduler-benchmark-") as tmpdir:
        store = ProofStateStore(
            "scheduler-benchmark", generation_root=Path(tmpdir) / "generation"
        )
        store.init_problem("Prove the benchmark theorem.")
        for _ in range(warmup):
            next_action(store, web_search="disabled")
        samples_ms: list[float] = []
        action: dict[str, object] = {}
        for _ in range(iterations):
            started = time.perf_counter_ns()
            action = next_action(store, web_search="disabled")
            samples_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
        trace = action.get("decision_trace") if isinstance(action, dict) else {}
        trace = trace if isinstance(trace, dict) else {}
        result = {
            "benchmark": "unchanged_state_next_action",
            "iterations": iterations,
            "warmup": warmup,
            **_latency_summary(samples_ms),
            "selected_policy_id": str(action.get("scheduler_policy_id") or ""),
            "candidate_count": len(trace.get("candidates") or []),
            "candidate_set_complete": bool(trace.get("candidate_set_complete")),
            "decision_policy_version": int(trace.get("decision_policy_version") or 0),
            "scope": "microbenchmark only; not an end-to-end mathematical performance result",
        }
        primary = next_action(store, web_search="live")
        for _ in range(warmup):
            parallel_companion_actions(
                store,
                primary,
                web_search="live",
                parallel_branches=5,
            )
        wave_samples_ms: list[float] = []
        companions: list[dict[str, object]] = []
        for _ in range(iterations):
            started = time.perf_counter_ns()
            companions = parallel_companion_actions(
                store,
                primary,
                web_search="live",
                parallel_branches=5,
            )
            wave_samples_ms.append(
                (time.perf_counter_ns() - started) / 1_000_000.0
            )
        admission = (
            companions[0].get("parallel_wave_admission", {})
            if companions
            else {}
        )
        admission_errors = (
            _parallel_wave_admission_errors(admission)
            if admission
            else ["parallel wave produced no auditable admission record"]
        )
        if admission_errors:
            raise RuntimeError(
                "parallel wave admission failed validation: "
                + "; ".join(admission_errors)
            )
        result["parallel_wave"] = {
            "benchmark": "parallel_wave_planning",
            "iterations": iterations,
            "warmup": warmup,
            "parallel_branches": 5,
            "companion_count": len(companions),
            "candidate_count": len(admission.get("candidates") or []),
            "candidate_set_complete": bool(
                admission.get("candidate_set_complete")
            ),
            "policy_version": int(admission.get("policy_version") or 0),
            "trace_validation_errors": admission_errors,
            **_latency_summary(wave_samples_ms),
        }
    result["bounded_history"] = _deferral_history_benchmark(
        iterations=iterations,
        warmup=warmup,
        candidate_count=history_candidates,
        run_count=history_runs,
    )
    result["durable_fairness"] = _durable_deferral_state_benchmark(
        iterations=iterations,
        warmup=warmup,
        candidate_count=history_candidates,
        deferral_count=history_runs,
    )
    result["durable_dispatch"] = _durable_dispatch_benchmark(
        iterations=dispatch_iterations,
        warmup=min(warmup, 5),
    )
    result["large_state"] = _large_state_benchmark(
        iterations=large_state_iterations,
        warmup=min(warmup, 5),
        claim_count=large_state_claims,
    )
    result["deep_state"] = _large_state_benchmark(
        iterations=deep_state_iterations,
        warmup=min(warmup, 5),
        claim_count=deep_state_claims,
        parent_chain=True,
    )
    result["dense_verification"] = _dense_verification_benchmark(
        iterations=dense_verification_iterations,
        warmup=min(warmup, 5),
        route_count=dense_verification_routes,
    )
    result["dense_evidence"] = _dense_evidence_benchmark(
        iterations=dense_evidence_iterations,
        warmup=min(warmup, 5),
        object_count=dense_evidence_objects,
    )
    result["dense_obligation"] = _dense_obligation_benchmark(
        iterations=dense_obligation_iterations,
        warmup=min(warmup, 5),
        object_count=dense_obligation_objects,
    )
    result["dense_parallel_search"] = _dense_parallel_search_benchmark(
        iterations=dense_parallel_iterations,
        warmup=min(warmup, 3),
        candidate_count=dense_parallel_candidates,
    )
    result["dense_parallel_resource_search"] = _dense_parallel_search_benchmark(
        iterations=dense_parallel_resource_iterations,
        warmup=min(warmup, 3),
        candidate_count=dense_parallel_resource_candidates,
        resource_constrained=True,
    )
    result["dense_parallel_clique_search"] = _dense_parallel_search_benchmark(
        iterations=dense_parallel_clique_iterations,
        warmup=min(warmup, 3),
        candidate_count=dense_parallel_clique_candidates,
        sibling_clique=True,
    )
    result["dense_parallel_equivalence_search"] = _dense_parallel_search_benchmark(
        iterations=dense_parallel_equivalence_iterations,
        warmup=min(warmup, 3),
        candidate_count=dense_parallel_equivalence_candidates,
        equivalent_conflicts=True,
    )
    result["dense_parallel_neighborhood_search"] = _dense_parallel_search_benchmark(
        iterations=dense_parallel_neighborhood_iterations,
        warmup=min(warmup, 3),
        candidate_count=12,
        suffix_neighborhood_conflicts=True,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--max-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-history-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-durable-fairness-p95-ms", type=float, default=0.0)
    parser.add_argument("--dispatch-iterations", type=int, default=20)
    parser.add_argument("--max-durable-dispatch-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-dispatch-attempt-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-dispatch-result-p95-ms", type=float, default=0.0)
    parser.add_argument(
        "--max-durable-decision-tail-p95-ms", type=float, default=0.0
    )
    parser.add_argument(
        "--max-durable-dispatch-tail-p95-ms", type=float, default=0.0
    )
    parser.add_argument(
        "--max-durable-attempt-tail-p95-ms", type=float, default=0.0
    )
    parser.add_argument(
        "--max-durable-result-tail-p95-ms", type=float, default=0.0
    )
    parser.add_argument(
        "--max-durable-completion-tail-p95-ms", type=float, default=0.0
    )
    parser.add_argument("--max-wave-p95-ms", type=float, default=0.0)
    parser.add_argument("--history-candidates", type=int, default=64)
    parser.add_argument("--history-runs", type=int, default=96)
    parser.add_argument("--large-state-claims", type=int, default=512)
    parser.add_argument("--large-state-iterations", type=int, default=50)
    parser.add_argument("--max-large-state-p95-ms", type=float, default=0.0)
    parser.add_argument("--deep-state-claims", type=int, default=512)
    parser.add_argument("--deep-state-iterations", type=int, default=50)
    parser.add_argument("--max-deep-state-p95-ms", type=float, default=0.0)
    parser.add_argument("--dense-verification-routes", type=int, default=512)
    parser.add_argument("--dense-verification-iterations", type=int, default=30)
    parser.add_argument("--max-dense-verification-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-dense-trace-validation-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-dense-history-p95-ms", type=float, default=0.0)
    parser.add_argument("--dense-evidence-objects", type=int, default=256)
    parser.add_argument("--dense-evidence-iterations", type=int, default=30)
    parser.add_argument("--max-dense-evidence-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-dense-evidence-validation-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-dense-evidence-history-p95-ms", type=float, default=0.0)
    parser.add_argument("--dense-obligation-objects", type=int, default=256)
    parser.add_argument("--dense-obligation-iterations", type=int, default=30)
    parser.add_argument("--max-dense-obligation-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-dense-obligation-validation-p95-ms", type=float, default=0.0)
    parser.add_argument("--max-dense-obligation-history-p95-ms", type=float, default=0.0)
    parser.add_argument("--dense-parallel-candidates", type=int, default=512)
    parser.add_argument("--dense-parallel-iterations", type=int, default=20)
    parser.add_argument("--max-dense-parallel-p95-ms", type=float, default=0.0)
    parser.add_argument("--dense-parallel-resource-candidates", type=int, default=512)
    parser.add_argument("--dense-parallel-resource-iterations", type=int, default=20)
    parser.add_argument(
        "--max-dense-parallel-resource-p95-ms", type=float, default=0.0
    )
    parser.add_argument("--dense-parallel-clique-candidates", type=int, default=512)
    parser.add_argument("--dense-parallel-clique-iterations", type=int, default=20)
    parser.add_argument(
        "--max-dense-parallel-clique-p95-ms", type=float, default=0.0
    )
    parser.add_argument(
        "--dense-parallel-equivalence-candidates", type=int, default=512
    )
    parser.add_argument(
        "--dense-parallel-equivalence-iterations", type=int, default=20
    )
    parser.add_argument(
        "--max-dense-parallel-equivalence-p95-ms", type=float, default=0.0
    )
    parser.add_argument(
        "--dense-parallel-neighborhood-iterations", type=int, default=20
    )
    parser.add_argument(
        "--max-dense-parallel-neighborhood-p95-ms", type=float, default=0.0
    )
    args = parser.parse_args()
    result = benchmark(
        iterations=args.iterations,
        warmup=args.warmup,
        history_candidates=args.history_candidates,
        history_runs=args.history_runs,
        large_state_claims=args.large_state_claims,
        large_state_iterations=args.large_state_iterations,
        deep_state_claims=args.deep_state_claims,
        deep_state_iterations=args.deep_state_iterations,
        dense_verification_routes=args.dense_verification_routes,
        dense_verification_iterations=args.dense_verification_iterations,
        dense_evidence_objects=args.dense_evidence_objects,
        dense_evidence_iterations=args.dense_evidence_iterations,
        dense_obligation_objects=args.dense_obligation_objects,
        dense_obligation_iterations=args.dense_obligation_iterations,
        dense_parallel_candidates=args.dense_parallel_candidates,
        dense_parallel_iterations=args.dense_parallel_iterations,
        dense_parallel_resource_candidates=args.dense_parallel_resource_candidates,
        dense_parallel_resource_iterations=args.dense_parallel_resource_iterations,
        dense_parallel_clique_candidates=args.dense_parallel_clique_candidates,
        dense_parallel_clique_iterations=args.dense_parallel_clique_iterations,
        dense_parallel_equivalence_candidates=(
            args.dense_parallel_equivalence_candidates
        ),
        dense_parallel_equivalence_iterations=(
            args.dense_parallel_equivalence_iterations
        ),
        dense_parallel_neighborhood_iterations=(
            args.dense_parallel_neighborhood_iterations
        ),
        dispatch_iterations=args.dispatch_iterations,
    )
    print(json.dumps(result, sort_keys=True))
    if args.max_p95_ms > 0 and float(result["p95_ms"]) > args.max_p95_ms:
        return 1
    history = result.get("bounded_history") or {}
    if (
        args.max_history_p95_ms > 0
        and isinstance(history, dict)
        and float(history.get("p95_ms") or 0.0) > args.max_history_p95_ms
    ):
        return 1
    durable_dispatch = result.get("durable_dispatch") or {}
    durable_attempt = (
        durable_dispatch.get("attempt_claim")
        if isinstance(durable_dispatch, dict)
        else {}
    ) or {}
    if (
        args.max_dispatch_attempt_p95_ms > 0
        and isinstance(durable_attempt, dict)
        and float(durable_attempt.get("p95_ms") or 0.0)
        > args.max_dispatch_attempt_p95_ms
    ):
        return 1
    durable_result = (
        durable_dispatch.get("result_record")
        if isinstance(durable_dispatch, dict)
        else {}
    ) or {}
    if (
        args.max_dispatch_result_p95_ms > 0
        and isinstance(durable_result, dict)
        and float(durable_result.get("p95_ms") or 0.0)
        > args.max_dispatch_result_p95_ms
    ):
        return 1
    durable_tail = (
        durable_dispatch.get("long_history_tail")
        if isinstance(durable_dispatch, dict)
        else {}
    ) or {}
    for threshold, field in (
        (args.max_durable_decision_tail_p95_ms, "decision"),
        (args.max_durable_dispatch_tail_p95_ms, "dispatch"),
        (args.max_durable_attempt_tail_p95_ms, "attempt_claim"),
        (args.max_durable_result_tail_p95_ms, "result_record"),
        (args.max_durable_completion_tail_p95_ms, "completion"),
    ):
        metric = durable_tail.get(field) if isinstance(durable_tail, dict) else {}
        if (
            threshold > 0
            and isinstance(metric, dict)
            and float(metric.get("p95_ms") or 0.0) > threshold
        ):
            return 1
    durable_fairness = result.get("durable_fairness") or {}
    if (
        args.max_durable_fairness_p95_ms > 0
        and isinstance(durable_fairness, dict)
        and float(durable_fairness.get("p95_ms") or 0.0)
        > args.max_durable_fairness_p95_ms
    ):
        return 1
    if (
        args.max_durable_dispatch_p95_ms > 0
        and isinstance(durable_dispatch, dict)
        and float(durable_dispatch.get("p95_ms") or 0.0)
        > args.max_durable_dispatch_p95_ms
    ):
        return 1
    wave = result.get("parallel_wave") or {}
    if (
        args.max_wave_p95_ms > 0
        and isinstance(wave, dict)
        and float(wave.get("p95_ms") or 0.0) > args.max_wave_p95_ms
    ):
        return 1
    large_state = result.get("large_state") or {}
    if (
        args.max_large_state_p95_ms > 0
        and isinstance(large_state, dict)
        and float(large_state.get("p95_ms") or 0.0)
        > args.max_large_state_p95_ms
    ):
        return 1
    deep_state = result.get("deep_state") or {}
    if (
        args.max_deep_state_p95_ms > 0
        and isinstance(deep_state, dict)
        and float(deep_state.get("p95_ms") or 0.0)
        > args.max_deep_state_p95_ms
    ):
        return 1
    dense_verification = result.get("dense_verification") or {}
    if (
        args.max_dense_verification_p95_ms > 0
        and isinstance(dense_verification, dict)
        and float(dense_verification.get("p95_ms") or 0.0)
        > args.max_dense_verification_p95_ms
    ):
        return 1
    dense_trace_validation = (
        dense_verification.get("trace_validation")
        if isinstance(dense_verification, dict)
        else {}
    ) or {}
    if (
        args.max_dense_trace_validation_p95_ms > 0
        and isinstance(dense_trace_validation, dict)
        and float(dense_trace_validation.get("p95_ms") or 0.0)
        > args.max_dense_trace_validation_p95_ms
    ):
        return 1
    dense_history = (
        dense_verification.get("bounded_history_replay")
        if isinstance(dense_verification, dict)
        else {}
    ) or {}
    if (
        args.max_dense_history_p95_ms > 0
        and isinstance(dense_history, dict)
        and float(dense_history.get("p95_ms") or 0.0)
        > args.max_dense_history_p95_ms
    ):
        return 1
    dense_evidence = result.get("dense_evidence") or {}
    if (
        args.max_dense_evidence_p95_ms > 0
        and isinstance(dense_evidence, dict)
        and float(dense_evidence.get("p95_ms") or 0.0)
        > args.max_dense_evidence_p95_ms
    ):
        return 1
    dense_evidence_validation = (
        dense_evidence.get("trace_validation")
        if isinstance(dense_evidence, dict)
        else {}
    ) or {}
    if (
        args.max_dense_evidence_validation_p95_ms > 0
        and isinstance(dense_evidence_validation, dict)
        and float(dense_evidence_validation.get("p95_ms") or 0.0)
        > args.max_dense_evidence_validation_p95_ms
    ):
        return 1
    dense_evidence_history = (
        dense_evidence.get("bounded_history_replay")
        if isinstance(dense_evidence, dict)
        else {}
    ) or {}
    if (
        args.max_dense_evidence_history_p95_ms > 0
        and isinstance(dense_evidence_history, dict)
        and float(dense_evidence_history.get("p95_ms") or 0.0)
        > args.max_dense_evidence_history_p95_ms
    ):
        return 1
    dense_obligation = result.get("dense_obligation") or {}
    if (
        args.max_dense_obligation_p95_ms > 0
        and isinstance(dense_obligation, dict)
        and float(dense_obligation.get("p95_ms") or 0.0)
        > args.max_dense_obligation_p95_ms
    ):
        return 1
    dense_obligation_validation = (
        dense_obligation.get("trace_validation")
        if isinstance(dense_obligation, dict)
        else {}
    ) or {}
    if (
        args.max_dense_obligation_validation_p95_ms > 0
        and isinstance(dense_obligation_validation, dict)
        and float(dense_obligation_validation.get("p95_ms") or 0.0)
        > args.max_dense_obligation_validation_p95_ms
    ):
        return 1
    dense_obligation_history = (
        dense_obligation.get("bounded_history_replay")
        if isinstance(dense_obligation, dict)
        else {}
    ) or {}
    if (
        args.max_dense_obligation_history_p95_ms > 0
        and isinstance(dense_obligation_history, dict)
        and float(dense_obligation_history.get("p95_ms") or 0.0)
        > args.max_dense_obligation_history_p95_ms
    ):
        return 1
    dense_parallel = result.get("dense_parallel_search") or {}
    if (
        args.max_dense_parallel_p95_ms > 0
        and isinstance(dense_parallel, dict)
        and float(dense_parallel.get("p95_ms") or 0.0)
        > args.max_dense_parallel_p95_ms
    ):
        return 1
    if _dense_parallel_certificate_errors(dense_parallel):
        return 1
    dense_parallel_resource = result.get("dense_parallel_resource_search") or {}
    if (
        args.max_dense_parallel_resource_p95_ms > 0
        and isinstance(dense_parallel_resource, dict)
        and float(dense_parallel_resource.get("p95_ms") or 0.0)
        > args.max_dense_parallel_resource_p95_ms
    ):
        return 1
    if _dense_parallel_certificate_errors(dense_parallel_resource):
        return 1
    dense_parallel_clique = result.get("dense_parallel_clique_search") or {}
    if (
        args.max_dense_parallel_clique_p95_ms > 0
        and isinstance(dense_parallel_clique, dict)
        and float(dense_parallel_clique.get("p95_ms") or 0.0)
        > args.max_dense_parallel_clique_p95_ms
    ):
        return 1
    if _dense_parallel_certificate_errors(dense_parallel_clique):
        return 1
    dense_parallel_equivalence = (
        result.get("dense_parallel_equivalence_search") or {}
    )
    if (
        args.max_dense_parallel_equivalence_p95_ms > 0
        and isinstance(dense_parallel_equivalence, dict)
        and float(dense_parallel_equivalence.get("p95_ms") or 0.0)
        > args.max_dense_parallel_equivalence_p95_ms
    ):
        return 1
    if _dense_parallel_certificate_errors(dense_parallel_equivalence):
        return 1
    dense_parallel_neighborhood = (
        result.get("dense_parallel_neighborhood_search") or {}
    )
    if (
        args.max_dense_parallel_neighborhood_p95_ms > 0
        and isinstance(dense_parallel_neighborhood, dict)
        and float(dense_parallel_neighborhood.get("p95_ms") or 0.0)
        > args.max_dense_parallel_neighborhood_p95_ms
    ):
        return 1
    if _dense_parallel_certificate_errors(dense_parallel_neighborhood):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
