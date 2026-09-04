from __future__ import annotations

"""Pure policy and validation for bounded parallel scheduler waves.

This module deliberately has no dependency on :mod:`scheduler` or
:mod:`decision_policy`.  Persisted decision traces can therefore be validated
without importing the large scheduler module, and the scheduler can reuse exactly
the same ordering, conflict, and replay rules that the validator applies.
"""

import hashlib
import heapq
import json
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Dict, Mapping, NamedTuple, Sequence

from .scheduler_registry import candidate_generator_trace_errors

from .budget import MIN_STEP_BUDGET
from .models import fingerprint_text
from .parallel_relaxation import (
    grouped_relaxed_value,
    grouped_relaxed_rows,
    grouped_suffix_values,
    resource_relaxed_value,
)


MULTI_BRANCH_MIN_WORKERS = 2
MULTI_BRANCH_MAX_WORKERS = 5
PARALLEL_WAVE_ADMISSION_POLICY_VERSION = 25
SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS = (
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
)
PARALLEL_WAVE_DEFERRAL_LIMIT = 3
PARALLEL_WAVE_ROLE_DIVERSE_EXTRA_SLOTS = 2
PARALLEL_ADMISSION_SEARCH_VERSION = 1
PARALLEL_ADMISSION_BOUND_CERTIFICATE_VERSION = 2
PARALLEL_ADMISSION_ALLOCATION_CERTIFICATE_VERSION = 3
PARALLEL_ADMISSION_CLASS_BOUND_CERTIFICATE_VERSION = 4
PARALLEL_ADMISSION_RESOURCE_BOUND_CERTIFICATE_VERSION = 5
PARALLEL_ADMISSION_CLIQUE_BOUND_CERTIFICATE_VERSION = 6
PARALLEL_ADMISSION_CERTIFICATION_CLIQUE_BOUND_CERTIFICATE_VERSION = 7
PARALLEL_ADMISSION_CLASS_CLIQUE_BOUND_CERTIFICATE_VERSION = 8
PARALLEL_ADMISSION_EQUIVALENCE_BOUND_CERTIFICATE_VERSION = 9
PARALLEL_ADMISSION_NEIGHBORHOOD_BOUND_CERTIFICATE_VERSION = 10
PARALLEL_ADMISSION_CANONICAL_BOUND_CERTIFICATE_VERSION = 11
PARALLEL_ADMISSION_CANONICAL_SUFFIX_BOUND_CERTIFICATE_VERSION = 12
PARALLEL_ADMISSION_DOMINANCE_BOUND_CERTIFICATE_VERSION = 13
PARALLEL_ADMISSION_ANYTIME_BOUND_CERTIFICATE_VERSION = 14
PARALLEL_ADMISSION_INTRINSIC_FILTER_CERTIFICATE_VERSION = 15
PARALLEL_ADMISSION_FRONTIER_COMPLETION_CERTIFICATE_VERSION = 16
PARALLEL_ADMISSION_BOUNDED_FRONTIER_CERTIFICATE_VERSION = 17
PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH = 64
PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH = 128
PARALLEL_ADMISSION_WIDE_BEAM_MAX_CANDIDATES = 128
PARALLEL_ADMISSION_NEIGHBORHOOD_QUOTIENT_MAX_CANDIDATES = 4_096
PARALLEL_ADMISSION_CANONICAL_SUFFIX_MAX_CARDINALITY = 32
PARALLEL_ADMISSION_DOMINANCE_MAX_FRONTIER = 32
PARALLEL_ADMISSION_ANYTIME_STATE_LIMIT = 20_000
PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT = 20_000

PARALLEL_EXCLUSIVE_MODES = frozenset(
    {
        "await_human",
        "stop_with_partial_results",
        "stop_solved",
        "write",
        "review_writing",
        "formalize",
        "validate_counterexample",
    }
)

PARALLEL_OBJECT_IDENTITY_FIELDS = (
    "proof_obligation_id",
    "debt_id",  # Legacy persisted field; new interfaces use proof_obligation_id.
    "search_request_artifact_id",
    "search_request_id",
    "support_lemma_label",
    "decomposition_plan_artifact_id",
    "decomposition_plan_id",
    "advisor_report_id",
    "proof_candidate_artifact_id",
    "source_artifact_id",
    "route_decision_artifact_id",
    "obstruction_cluster_id",
    "counterexample_artifact_id",
)
PARALLEL_IDENTITY_ACTION_FIELDS = (
    "mode",
    "target_id",
    "route_id",
    "search_intent",
    "multi_branch_worker",
)
PARALLEL_SEMANTIC_PAYLOAD_EXCLUDED_FIELDS = frozenset(
    {
        # Allocation may change without changing the mathematical task whose
        # bounded-service history is being tracked. ``reason`` is intentionally
        # included because prompt construction may use it as the task or query.
        "budget",
        # Derived scheduling/presentation placement does not alter the
        # mathematical task. These annotations may be absent on direct callers
        # and present on the same action when produced by the main planner.
        "display_mode",
        "integration_parallel_safe",
        "parallel_companion",
        "parallel_companion_index",
        "scheduler_policy_id",
        # These fields are attached only after admission and bind execution to
        # the already committed wave; including them would be recursive.
        "decision_trace",
        "parallel_wave_admission",
        "parallel_wave_candidate_id",
        "parallel_wave_input_action_sha256",
    }
)
PARALLEL_CANDIDATE_COMMITMENT_FIELDS = (
    "candidate_id",
    "admission_priority",
    "action_class",
    "mode",
    "target_id",
    "route_id",
    "search_intent",
    "semantic_identity",
    "consecutive_deferrals",
    "deferral_limit",
    "budget_allowed",
    "requested_tokens",
    "comparison_action_sha256",
)
FAIRNESS_ELIGIBLE_OUTCOME_CODES = frozenset(
    {
        "sibling_conflict_queue",
        "total_capacity_queue",
        "class_capacity_queue",
        "aggregate_allocation_queue",
        "minimum_useful_allocation_queue",
        "bounded_search_queue",
    }
)
PRIMARY_SERIALIZATION_OUTCOME_CODE = "primary_serialization_queue"


class ParallelAdmissionOutcome(NamedTuple):
    """Typed result emitted directly by the admission transition."""

    disposition: str
    reason: str
    outcome_code: str
    admitted_tokens: int


class _BeamAdmissionState(NamedTuple):
    """One deterministic partial solution in the bounded admission search."""

    selected_positions: tuple[int, ...]
    selected_candidate_ids: tuple[str, ...]
    selected_identities: tuple[tuple[str, ...], ...]
    route_clique_keys: tuple[tuple[str, ...], ...]
    research_mixed_route_clique_keys: tuple[tuple[str, ...], ...]
    adversarial_mixed_route_clique_keys: tuple[tuple[str, ...], ...]
    target_clique_keys: tuple[tuple[str, ...], ...]
    grants: tuple[int, ...]
    class_counts: tuple[tuple[str, int], ...]
    remaining_protected_tokens: int
    remaining_unreserved_tokens: int
    fairness_value: int
    priority_value: int


def _beam_admission_score(
    state: _BeamAdmissionState,
) -> tuple[int, int, int, int]:
    """Return the scheduler's lexicographic value for a partial wave."""

    return (
        state.fairness_value,
        state.priority_value,
        len(state.selected_positions),
        state.remaining_protected_tokens + state.remaining_unreserved_tokens,
    )


def _parallel_nondominated_states(
    states: Sequence[_BeamAdmissionState],
    *,
    suffix_conflict_masks: Sequence[int],
    next_position: int,
) -> tuple[list[_BeamAdmissionState], int]:
    """Return the canonical Pareto frontier at one exact-conflict layer.

    A continuation feasible from a dominated state is also feasible from its
    representative when the representative has used no more total or per-class
    capacity, retains at least as much of both token pools, and blocks a subset
    of the suffix. Applying the same continuation preserves a strict objective
    advantage. At equal value, selected cardinalities agree, so candidate-ID
    order is preserved when a common suffix is appended.
    """

    blocked_by_state: Dict[_BeamAdmissionState, int] = {}
    for state in states:
        blocked = 0
        for selected_position in state.selected_positions:
            blocked |= suffix_conflict_masks[selected_position]
        blocked_by_state[state] = blocked & (-1 << next_position)

    def dominates(
        left: _BeamAdmissionState,
        right: _BeamAdmissionState,
    ) -> bool:
        left_score = _beam_admission_score(left)
        right_score = _beam_admission_score(right)
        if left_score < right_score:
            return False
        if len(left.selected_positions) > len(right.selected_positions):
            return False
        if any(
            left_key != right_key or left_count > right_count
            for (left_key, left_count), (right_key, right_count) in zip(
                left.class_counts, right.class_counts
            )
        ) or len(left.class_counts) != len(right.class_counts):
            return False
        if (
            left.remaining_protected_tokens
            < right.remaining_protected_tokens
            or left.remaining_unreserved_tokens
            < right.remaining_unreserved_tokens
        ):
            return False
        if blocked_by_state[left] & ~blocked_by_state[right]:
            return False
        return not (
            left_score == right_score
            and left.selected_candidate_ids > right.selected_candidate_ids
        )

    nondominated: list[_BeamAdmissionState] = []
    removed = 0
    for state in states:
        if any(dominates(representative, state) for representative in nondominated):
            removed += 1
            continue
        retained: list[_BeamAdmissionState] = []
        for representative in nondominated:
            if dominates(state, representative):
                removed += 1
            else:
                retained.append(representative)
        retained.append(state)
        nondominated = retained
    return nondominated, removed


def parallel_rejection_is_fairness_eligible(reason: str) -> bool:
    """Legacy text classifier for traces predating outcome codes."""

    return reason.startswith(
        "queued behind conflicting companion: "
    ) or reason == "total wave capacity reached" or reason.endswith(
        " capacity reached"
    ) or reason in {
        "aggregate wave token allocation exhausted",
        "aggregate token allocation is below the minimum useful step size",
    }


def parallel_outcome_code(
    disposition: str,
    reason: str,
    *,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
) -> str:
    """Return the version-6 machine code implied by one policy outcome."""

    if disposition == "fixed_primary":
        return "fixed_primary"
    if disposition == "selected":
        if reason.startswith("admitted with token grant reduced"):
            return "selected_reduced_allocation"
        if "bounded-deferral fairness within" in reason:
            return "selected_fairness_within_class"
        if "bounded-deferral fairness across" in reason:
            return "selected_fairness_across_classes"
        if "max-weight fairness" in reason:
            return "selected_fairness_search"
        if "fixed-compute global admission search" in reason:
            return "selected_search"
        return "selected_priority"
    if disposition != "rejected":
        return "invalid_disposition"
    if reason.startswith("queued behind conflicting companion: "):
        return "sibling_conflict_queue"
    if reason == "total wave capacity reached":
        return "total_capacity_queue"
    if reason.endswith(" capacity reached"):
        return "class_capacity_queue"
    if reason == "aggregate wave token allocation exhausted":
        return "aggregate_allocation_queue"
    if reason == "aggregate token allocation is below the minimum useful step size":
        return "minimum_useful_allocation_queue"
    if reason == "candidate budget does not authorize dispatch":
        return "budget_unauthorized"
    if reason == (
        "candidate was not selected by the fixed-compute global admission search"
    ):
        return "bounded_search_queue"
    if policy_version >= 8 and reason in {
        "another mutating action owns the same proof route",
        "verification and integration may not mutate certification state concurrently",
        "another certification action owns the same conclusion claim",
        "proof search and certification may not update the same claim concurrently",
    }:
        return PRIMARY_SERIALIZATION_OUTCOME_CODE
    if reason:
        return "primary_or_structural_conflict"
    return "invalid_reason"


def parallel_outcome_is_fairness_eligible(
    row: Mapping[str, Any],
    *,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
) -> bool:
    """Classify a validated outcome without inspecting current-policy prose."""

    if str(row.get("disposition") or "") != "rejected":
        return False
    if policy_version >= 6:
        outcome_code = row.get("outcome_code")
        return outcome_code in FAIRNESS_ELIGIBLE_OUTCOME_CODES or (
            policy_version >= 8
            and outcome_code == PRIMARY_SERIALIZATION_OUTCOME_CODE
        )
    return parallel_rejection_is_fairness_eligible(
        str(row.get("reason") or "")
    )


# Compatibility for tests and older internal callers; new code uses the public
# mathematical name above.
_rejection_is_fairness_eligible = parallel_rejection_is_fairness_eligible


def _unambiguous_candidate_aliases(
    candidate_ids: Sequence[str],
    candidate_aliases: Mapping[str, Sequence[str]] | None,
) -> Dict[str, tuple[str, ...]]:
    candidate_id_set = set(candidate_ids)
    alias_owners: Dict[str, set[str]] = {
        candidate_id: {candidate_id} for candidate_id in candidate_id_set
    }
    for candidate_id, aliases in (candidate_aliases or {}).items():
        if candidate_id not in candidate_id_set:
            continue
        for alias in aliases:
            if isinstance(alias, str) and alias:
                alias_owners.setdefault(alias, set()).add(candidate_id)
    return {
        candidate_id: tuple(
            alias
            for alias in (candidate_aliases or {}).get(candidate_id, ())
            if alias_owners.get(alias) == {candidate_id}
        )
        for candidate_id in candidate_id_set
    }


def parallel_candidate_deferral_counts_from_state(
    stored_counts: Mapping[str, Any],
    candidate_ids: Sequence[str],
    *,
    candidate_aliases: Mapping[str, Sequence[str]] | None = None,
) -> Dict[str, int]:
    """Resolve compact authenticated counters, using only unique legacy aliases."""

    aliases = _unambiguous_candidate_aliases(candidate_ids, candidate_aliases)
    counts: Dict[str, int] = {}
    for candidate_id in candidate_ids:
        sources = (candidate_id, *aliases.get(candidate_id, ()))
        value = next(
            (stored_counts[source] for source in sources if source in stored_counts),
            0,
        )
        if type(value) is not int or value < 0:
            raise ValueError(
                "parallel candidate deferral state must contain nonnegative integers"
            )
        counts[candidate_id] = value
    return counts


def normalize_parallel_branches(value: Any) -> int:
    """Return zero when disabled, else a worker count clamped to 2..5."""

    try:
        workers = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    if workers < MULTI_BRANCH_MIN_WORKERS:
        return 0
    return min(workers, MULTI_BRANCH_MAX_WORKERS)


def parallel_action_identity(
    action: Mapping[str, Any],
    *,
    action_class: str,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
) -> tuple[str, ...]:
    """Build a semantic identity from the versioned declarative schema."""

    object_values = {
        key: str(action.get(key) or "") for key in PARALLEL_OBJECT_IDENTITY_FIELDS
    }
    if policy_version == 3:
        # Retained only to identify candidates in already-persisted v3 waves.
        object_identity = "|".join(object_values.values())
    elif policy_version in SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS:
        object_identity = json.dumps(
            object_values,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        raise ValueError(f"unsupported parallel admission policy {policy_version}")
    action_dimensions = tuple(
        str(action.get(key) or "") for key in PARALLEL_IDENTITY_ACTION_FIELDS
    )
    legacy_dimensions = (str(action_class), *action_dimensions, object_identity)
    if policy_version < 7:
        return legacy_dimensions
    if any(not isinstance(key, str) for key in action):
        raise ValueError("parallel action fields must have string names")
    semantic_payload = {
        key: value
        for key, value in action.items()
        if key not in PARALLEL_SEMANTIC_PAYLOAD_EXCLUDED_FIELDS
    }
    return (*legacy_dimensions, _canonical_sha256(semantic_payload))


def _canonical_sha256(value: Any, *, length: int = 64) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def parallel_candidate_id(
    identity: Sequence[str],
    *,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
) -> str:
    payload = {"identity": list(identity)}
    if policy_version == 3:
        digest = fingerprint_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            length=24,
        )
    elif policy_version in SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS:
        digest = _canonical_sha256(payload, length=24)
    else:
        raise ValueError(f"unsupported parallel admission policy {policy_version}")
    return f"parallel:{digest}"


def parallel_v3_candidate_alias(identity: Sequence[str]) -> str:
    """Recover the legacy v3 identifier from a canonical v4+ identity."""

    if len(identity) not in {7, 8} or any(
        not isinstance(item, str) for item in identity
    ):
        return ""
    try:
        object_values = json.loads(identity[6])
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(object_values, Mapping) or set(object_values) != set(
        PARALLEL_OBJECT_IDENTITY_FIELDS
    ):
        return ""
    if any(not isinstance(object_values.get(key), str) for key in PARALLEL_OBJECT_IDENTITY_FIELDS):
        return ""
    legacy_identity = (
        *tuple(identity[:6]),
        "|".join(object_values[key] for key in PARALLEL_OBJECT_IDENTITY_FIELDS),
    )
    return parallel_candidate_id(legacy_identity, policy_version=3)


def parallel_wave_id(
    *,
    candidate_set_sha256: str,
    candidate_set_scope: str,
    state_revision: int,
    proof_state_hash: str,
    run_provenance_hash: str,
    configured_proof_search_workers: int,
    total_wave_capacity: int,
    class_capacities: Mapping[str, int],
    aggregate_budget_enforced: bool,
    initial_remaining_token_budget: int | None,
    initial_reserved_verification_budget: int | None,
    candidate_generator_manifest_sha256: str = "",
    admission_search: Mapping[str, Any] | None = None,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
) -> str:
    """Commit a wave to its snapshot, candidates, configuration, and allocation."""

    if policy_version not in SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS:
        raise ValueError(f"unsupported parallel admission policy {policy_version}")
    payload = {
        "policy_version": policy_version,
        "candidate_set_sha256": candidate_set_sha256,
        "candidate_set_scope": candidate_set_scope,
        "state_revision": state_revision,
        "proof_state_hash": proof_state_hash,
        "run_provenance_hash": run_provenance_hash,
        "configured_proof_search_workers": configured_proof_search_workers,
        "total_wave_capacity": total_wave_capacity,
        "class_capacities": dict(class_capacities),
        "aggregate_budget_enforced": aggregate_budget_enforced,
        "initial_remaining_token_budget": initial_remaining_token_budget,
        "initial_reserved_verification_budget": (
            initial_reserved_verification_budget
        ),
    }
    if policy_version >= 5:
        payload["candidate_generator_manifest_sha256"] = (
            candidate_generator_manifest_sha256
        )
    if policy_version >= 9:
        payload["admission_search"] = dict(admission_search or {})
    return _canonical_sha256(
        payload
    )


def parallel_admission_priority_for(action_class: str, intent: str) -> int:
    base = {
        "integration": 600,
        "verification": 500,
        "literature": 400,
        "advisory": 300,
        "adversarial": 200,
        "research": 100,
    }[action_class]
    if action_class == "literature" and intent in {
        "exact_theorem_search",
        "support_lemma_precheck",
    }:
        base += 20
    return base


def parallel_admission_order_key(
    row: Mapping[str, Any],
    *,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
) -> tuple[Any, ...]:
    def safe_int(value: Any) -> int:
        if isinstance(value, bool):
            return 0
        try:
            return int(value or 0)
        except (TypeError, ValueError, OverflowError):
            return 0

    deferrals = safe_int(row.get("consecutive_deferrals"))
    limit = safe_int(row.get("deferral_limit"))
    fairness_due = limit > 0 and deferrals >= limit
    raw_identity = row.get("semantic_identity")
    identity = raw_identity if isinstance(raw_identity, (list, tuple)) else ()
    priority = safe_int(row.get("admission_priority"))
    stable_suffix = (
        tuple(str(item) for item in identity),
        str(row.get("candidate_id") or ""),
    )
    if policy_version == 3:
        return (
            -priority,
            -int(fairness_due),
            -deferrals if fairness_due else 0,
            *stable_suffix,
        )
    if policy_version in SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS:
        # A stable candidate that has waited for the declared bound precedes
        # fresh candidates, irrespective of action class.  Safety is retained:
        # only candidates already admitted by the host's phase and budget
        # constraints enter this comparison, and ownership conflicts are still
        # rejected during replay/admission.
        return (
            -int(fairness_due),
            -deferrals if fairness_due else 0,
            -priority,
            *stable_suffix,
        )
    raise ValueError(f"unsupported parallel admission policy {policy_version}")


def parallel_candidate_deferral_counts(
    recent_runs: Sequence[Mapping[str, Any]],
    candidate_ids: Sequence[str],
    *,
    candidate_aliases: Mapping[str, Sequence[str]] | None = None,
) -> Dict[str, int]:
    """Count consecutive rejected decisions once per distinct wave."""

    counts = {candidate_id: 0 for candidate_id in candidate_ids}
    unresolved = set(counts)
    unambiguous_aliases = _unambiguous_candidate_aliases(
        candidate_ids, candidate_aliases
    )
    seen_wave_ids: set[str] = set()
    waves_by_trace_text: Dict[str, Mapping[str, Any] | None] = {}
    for run in recent_runs:
        if not unresolved or run.get("decision_trace_history_included") is False:
            break
        raw_trace = run.get("decision_trace_json") or run.get("decision_trace")
        if isinstance(raw_trace, str):
            if raw_trace in waves_by_trace_text:
                wave = waves_by_trace_text[raw_trace]
            else:
                try:
                    trace = json.loads(raw_trace)
                except (TypeError, ValueError, json.JSONDecodeError):
                    break
                wave = (
                    trace.get("parallel_wave_admission")
                    if isinstance(trace, Mapping)
                    else None
                )
                waves_by_trace_text[raw_trace] = (
                    wave if isinstance(wave, Mapping) else None
                )
        else:
            trace = raw_trace
            if not isinstance(trace, Mapping):
                break
            wave = trace.get("parallel_wave_admission")
        if not isinstance(wave, Mapping):
            continue
        try:
            policy_version = int(wave.get("policy_version") or 0)
        except (TypeError, ValueError, OverflowError):
            break
        if policy_version >= 6 and parallel_wave_admission_errors(wave):
            # Current traces are self-contained and replay-validatable. Never
            # derive durable priority from an unauthenticated outcome code.
            break
        wave_id = str(wave.get("wave_id") or "")
        if not wave_id:
            break
        if wave_id in seen_wave_ids:
            continue
        seen_wave_ids.add(wave_id)
        observations = {
            str(row.get("candidate_id") or ""): row
            for row in wave.get("candidates", [])
            if isinstance(row, Mapping) and str(row.get("candidate_id") or "")
        }
        for candidate_id in tuple(unresolved):
            observation = observations.get(candidate_id)
            if observation is None and candidate_aliases:
                observation = next(
                    (
                        observations[alias]
                        for alias in unambiguous_aliases.get(candidate_id, ())
                        if alias in observations
                    ),
                    None,
                )
            if observation is None:
                unresolved.remove(candidate_id)
                continue
            disposition = str(observation.get("disposition") or "")
            if disposition in {"selected", "fixed_primary"}:
                unresolved.remove(candidate_id)
            elif disposition == "rejected" and parallel_outcome_is_fairness_eligible(
                observation,
                policy_version=policy_version,
            ):
                counts[candidate_id] += 1
            else:
                unresolved.remove(candidate_id)
    return counts


def parallel_candidate_set_sha256(
    rows: Sequence[Mapping[str, Any]],
    *,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
) -> str:
    commitments = [
        {field: row.get(field) for field in PARALLEL_CANDIDATE_COMMITMENT_FIELDS}
        for row in sorted(rows, key=lambda row: str(row.get("candidate_id") or ""))
    ]
    if policy_version == 3:
        return fingerprint_text(
            json.dumps(
                commitments,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    if policy_version in SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS:
        return _canonical_sha256(commitments)
    raise ValueError(f"unsupported parallel admission policy {policy_version}")


def parallel_identity_conflict(
    identity: tuple[str, ...],
    admitted_identities: Sequence[tuple[str, ...]],
) -> tuple[str, bool]:
    """Return a conflict and whether serial execution can resolve it."""

    if identity[1] in PARALLEL_EXCLUSIVE_MODES:
        return "exclusive or terminal action cannot be a parallel companion", False
    candidate_class = identity[0]
    candidate_target = identity[2]
    candidate_route = identity[3]
    certification_classes = {"verification", "integration"}
    discovery_classes = {"research", "adversarial"}
    for existing_identity in admitted_identities:
        existing_class = existing_identity[0]
        if existing_identity[1] in PARALLEL_EXCLUSIVE_MODES:
            return "exclusive or terminal primary action cannot admit companions", False
        existing_target = existing_identity[2]
        existing_route = existing_identity[3]
        if identity == existing_identity:
            return "duplicate semantic action", False
        if candidate_route and candidate_route == existing_route and (
            candidate_class in certification_classes
            or existing_class in certification_classes
            or candidate_class == existing_class
            and candidate_class in discovery_classes
        ):
            return "another mutating action owns the same proof route", True
        if {candidate_class, existing_class} == certification_classes:
            return (
                "verification and integration may not mutate certification "
                "state concurrently",
                True,
            )
        if (
            candidate_class in certification_classes
            and existing_class in certification_classes
            and candidate_target
            and candidate_target == existing_target
        ):
            return "another certification action owns the same conclusion claim", True
        if (
            candidate_target
            and candidate_target == existing_target
            and (
                candidate_class in certification_classes
                and existing_class in discovery_classes
                or existing_class in certification_classes
                and candidate_class in discovery_classes
            )
        ):
            return (
                "proof search and certification may not update the same claim "
                "concurrently",
                True,
            )
    return "", False


def parallel_identity_conflict_reason(
    identity: tuple[str, ...],
    admitted_identities: Sequence[tuple[str, ...]],
) -> str:
    """Return the deterministic ownership conflict for semantic identities."""

    return parallel_identity_conflict(identity, admitted_identities)[0]


def _parallel_suffix_conflict_masks(
    identities: Sequence[tuple[str, ...]],
) -> tuple[int, ...]:
    """Index each identity's exact conflicts with later candidates as a bitset."""

    certification_classes = {"verification", "integration"}
    discovery_classes = {"research", "adversarial"}
    exact_masks: Dict[tuple[str, ...], int] = {}
    route_masks: Dict[str, int] = {}
    route_certification_masks: Dict[str, int] = {}
    route_discovery_class_masks: Dict[tuple[str, str], int] = {}
    class_masks: Dict[str, int] = {}
    target_certification_masks: Dict[str, int] = {}
    target_discovery_masks: Dict[str, int] = {}
    exclusive_mask = 0
    all_mask = (1 << len(identities)) - 1

    for position, identity in enumerate(identities):
        bit = 1 << position
        action_class, mode, target_id, route_id = identity[:4]
        exact_masks[identity] = exact_masks.get(identity, 0) | bit
        class_masks[action_class] = class_masks.get(action_class, 0) | bit
        if mode in PARALLEL_EXCLUSIVE_MODES:
            exclusive_mask |= bit
        if route_id:
            route_masks[route_id] = route_masks.get(route_id, 0) | bit
            if action_class in certification_classes:
                route_certification_masks[route_id] = (
                    route_certification_masks.get(route_id, 0) | bit
                )
            if action_class in discovery_classes:
                route_class = (route_id, action_class)
                route_discovery_class_masks[route_class] = (
                    route_discovery_class_masks.get(route_class, 0) | bit
                )
        if target_id and action_class in certification_classes:
            target_certification_masks[target_id] = (
                target_certification_masks.get(target_id, 0) | bit
            )
        if target_id and action_class in discovery_classes:
            target_discovery_masks[target_id] = (
                target_discovery_masks.get(target_id, 0) | bit
            )

    result: list[int] = []
    for position, identity in enumerate(identities):
        action_class, mode, target_id, route_id = identity[:4]
        if mode in PARALLEL_EXCLUSIVE_MODES:
            conflict_mask = all_mask
        else:
            conflict_mask = exclusive_mask | exact_masks[identity]
            if route_id:
                conflict_mask |= route_certification_masks.get(route_id, 0)
                if action_class in certification_classes:
                    conflict_mask |= route_masks.get(route_id, 0)
                elif action_class in discovery_classes:
                    conflict_mask |= route_discovery_class_masks.get(
                        (route_id, action_class), 0
                    )
            if action_class == "verification":
                conflict_mask |= class_masks.get("integration", 0)
            elif action_class == "integration":
                conflict_mask |= class_masks.get("verification", 0)
            if target_id and action_class in certification_classes:
                conflict_mask |= target_certification_masks.get(target_id, 0)
                conflict_mask |= target_discovery_masks.get(target_id, 0)
            elif target_id and action_class in discovery_classes:
                conflict_mask |= target_certification_masks.get(target_id, 0)
        result.append(conflict_mask & (all_mask << (position + 1)))
    return tuple(result)


def _parallel_route_clique_key(
    identity: tuple[str, ...],
) -> tuple[str, ...] | None:
    """Identify a same-route set whose members are pairwise conflicting."""

    action_class = identity[0]
    route_id = identity[3]
    if not route_id:
        return None
    if action_class in {"verification", "integration"}:
        return ("certification_route", route_id)
    if action_class in {"research", "adversarial"}:
        return ("discovery_route", action_class, route_id)
    return None


def _parallel_certification_target_clique_key(
    identity: tuple[str, ...],
) -> tuple[str, ...] | None:
    """Identify a same-target certification set that is pairwise conflicting."""

    target_id = identity[2]
    if target_id and identity[0] in {"verification", "integration"}:
        return ("certification_target", target_id)
    return None


def _parallel_mixed_route_clique_key(
    identity: tuple[str, ...],
    *,
    discovery_class: str,
) -> tuple[str, ...] | None:
    """Merge one same-route discovery class with certification actions."""

    action_class = identity[0]
    route_id = identity[3]
    if not route_id:
        return None
    if action_class in {"verification", "integration", discovery_class}:
        return ("mixed_route", discovery_class, route_id)
    if action_class in {"research", "adversarial"}:
        return ("discovery_route", action_class, route_id)
    return None


def _parallel_capacity_class(row: Mapping[str, Any]) -> str:
    action_class = str(row.get("action_class") or "")
    return (
        "research_or_adversarial"
        if action_class in {"research", "adversarial"}
        else action_class
    )


def _parallel_uses_protected_budget(row: Mapping[str, Any]) -> bool:
    return str(row.get("action_class") or "") in {
        "verification",
        "integration",
    } or str(row.get("mode") or "") in {
        "formalize",
        "validate_counterexample",
        "write",
        "review_writing",
    }


def _max_min_token_top_up(
    grants: Mapping[int, int],
    requests: Mapping[int, int],
    eligible_positions: Sequence[int],
    available: int,
) -> tuple[Dict[int, int], int]:
    """Max--min allocate integer tokens without exceeding request caps."""

    if type(available) is not int or available < 0:
        raise ValueError("available token allocation must be a nonnegative integer")
    positions = tuple(eligible_positions)
    if len(positions) != len(set(positions)):
        raise ValueError("max-min allocation positions must be unique")
    result = dict(grants)
    for position in positions:
        grant = result.get(position)
        request = requests.get(position)
        if (
            type(position) is not int
            or type(grant) is not int
            or type(request) is not int
            or grant < 0
            or request < grant
        ):
            raise ValueError("max-min allocation inputs are inconsistent")
    active = [
        position
        for position in positions
        if result[position] < requests[position]
    ]
    while available > 0 and active:
        level_value = min(result[position] for position in active)
        level = [
            position for position in active if result[position] == level_value
        ]
        higher_levels = [
            result[position]
            for position in active
            if result[position] > level_value
        ]
        target = min(requests[position] for position in level)
        if higher_levels:
            target = min(target, min(higher_levels))
        increment = target - level_value
        if increment <= 0:
            active = [
                position
                for position in active
                if result[position] < requests[position]
            ]
            continue
        cost = increment * len(level)
        if cost <= available:
            for position in level:
                result[position] += increment
            available -= cost
        else:
            quotient, remainder = divmod(available, len(level))
            for offset, position in enumerate(level):
                result[position] += quotient + int(offset < remainder)
            available = 0
        active = [
            position
            for position in active
            if result[position] < requests[position]
        ]
    return result, available


def _parallel_search_outcomes(
    rows: Sequence[Mapping[str, Any]],
    *,
    total_capacity: int,
    class_capacities: Mapping[str, int],
    aggregate_budget_enforced: bool,
    initial_remaining_token_budget: int,
    initial_reserved_verification_budget: int,
    policy_version: int,
) -> tuple[
    Dict[str, ParallelAdmissionOutcome],
    int,
    Dict[str, Any],
]:
    """Select a globally stronger companion set with bounded deterministic search.

    The value function is entirely host-defined. It first maximizes service of
    candidates whose authenticated deferral bound is due, then the sum of
    fixed admission priorities, then useful parallelism. No model self-score
    or unverified claim about mathematical quality enters the comparison.
    """

    primary = rows[0]
    all_companion_rows = list(rows[1:])
    companion_rows = all_companion_rows
    capacity_keys = tuple(sorted(str(key) for key in class_capacities))
    initial_class_counts = {key: 0 for key in capacity_keys}
    primary_capacity_class = _parallel_capacity_class(primary)
    if primary_capacity_class in initial_class_counts:
        initial_class_counts[primary_capacity_class] += 1

    if aggregate_budget_enforced:
        remaining_total = max(0, int(initial_remaining_token_budget))
        protected = min(
            remaining_total,
            max(0, int(initial_reserved_verification_budget)),
        )
        unreserved = max(0, remaining_total - protected)
        primary_request = max(0, int(primary.get("requested_tokens") or 0))
        remaining_total = max(0, remaining_total - primary_request)
        if _parallel_uses_protected_budget(primary):
            protected_spend = min(primary_request, protected)
            protected -= protected_spend
            unreserved = max(0, unreserved - (primary_request - protected_spend))
        else:
            unreserved = max(0, unreserved - primary_request)
        # A fixed primary is admitted before this comparison. Keep the two
        # pools consistent even if an upstream caller supplied an impossible
        # primary request; the trace conservation check will still reject it.
        protected = min(protected, remaining_total)
        unreserved = max(0, remaining_total - protected)
    else:
        protected = 0
        unreserved = 0

    max_companions = max(0, total_capacity - 1)

    def intrinsically_searchable(row: Mapping[str, Any]) -> bool:
        if max_companions <= 0 or row.get("budget_allowed") is not True:
            return False
        if parallel_identity_conflict_reason(
            tuple(row["semantic_identity"]),
            [tuple(primary["semantic_identity"])],
        ):
            return False
        capacity_key = _parallel_capacity_class(row)
        if (
            capacity_key in class_capacities
            and initial_class_counts.get(capacity_key, 0)
            >= int(class_capacities[capacity_key])
        ):
            return False
        request = max(0, int(row.get("requested_tokens") or 0))
        if not aggregate_budget_enforced or request == 0:
            return True
        if request < MIN_STEP_BUDGET:
            return False
        available = (
            protected + unreserved
            if _parallel_uses_protected_budget(row)
            else unreserved
        )
        return available >= MIN_STEP_BUDGET

    if policy_version >= 23:
        companion_rows = [
            row for row in all_companion_rows if intrinsically_searchable(row)
        ]

    conflict_projections = [
        (
            str(row["semantic_identity"][0]),
            str(row["semantic_identity"][1]),
            str(row["semantic_identity"][2]),
            str(row["semantic_identity"][3]),
        )
        for row in companion_rows
    ]
    quotient_by_conflict_projection = (
        policy_version >= 17
        and len(set(conflict_projections)) < len(conflict_projections)
    )
    quotient_by_suffix_conflict_neighborhood = (
        policy_version >= 18
        and len(companion_rows)
        <= PARALLEL_ADMISSION_NEIGHBORHOOD_QUOTIENT_MAX_CANDIDATES
    )
    quotient_equivalent_states = (
        quotient_by_conflict_projection
        or quotient_by_suffix_conflict_neighborhood
    )
    exact_state_dominance_available = (
        policy_version >= 21
        and quotient_by_suffix_conflict_neighborhood
    )
    search_beam_width = (
        PARALLEL_ADMISSION_NEIGHBORHOOD_SEARCH_BEAM_WIDTH
        if quotient_by_suffix_conflict_neighborhood
        and len(companion_rows) <= PARALLEL_ADMISSION_WIDE_BEAM_MAX_CANDIDATES
        else PARALLEL_ADMISSION_SEARCH_BEAM_WIDTH
    )
    retain_equal_objective_bounds = (
        policy_version == 19
        and len(companion_rows) <= PARALLEL_ADMISSION_WIDE_BEAM_MAX_CANDIDATES
    )
    last_identity_position: Dict[tuple[str, ...], int] = {}
    if quotient_by_conflict_projection:
        last_identity_position = {
            tuple(row["semantic_identity"]): position
            for position, row in enumerate(companion_rows)
        }
    suffix_conflict_masks: tuple[int, ...] = ()
    if quotient_by_suffix_conflict_neighborhood:
        suffix_conflict_masks = _parallel_suffix_conflict_masks(
            tuple(tuple(row["semantic_identity"]) for row in companion_rows)
        )

    initial = _BeamAdmissionState(
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        tuple(sorted(initial_class_counts.items())),
        protected,
        unreserved,
        0,
        0,
    )

    def fairness_weight(row: Mapping[str, Any]) -> int:
        deferrals = int(row.get("consecutive_deferrals") or 0)
        limit = int(row.get("deferral_limit") or 0)
        return deferrals + 1 if limit > 0 and deferrals >= limit else 0

    def score(state: _BeamAdmissionState) -> tuple[int, int, int, int]:
        return _beam_admission_score(state)

    def future_equivalence_key(
        state: _BeamAdmissionState,
        next_position: int,
    ) -> tuple[Any, ...]:
        """Identify partial states with identical value and future transitions.

        Pairwise feasibility depends on the first four identity coordinates,
        except for exact duplicate identities.  Class counts and the two token
        pools determine the remaining resource constraints.  Exact identities
        are retained only while an identical suffix row remains.  Consequently,
        states with this key have identical feasible continuations and objective
        increments; the preceding candidate-id sort chooses the canonical
        representative without changing the lexicographic optimum.
        """

        if quotient_by_suffix_conflict_neighborhood:
            blocked_suffix = 0
            for selected_position in state.selected_positions:
                blocked_suffix |= suffix_conflict_masks[selected_position]
            conflict_signature: object = blocked_suffix >> next_position
        else:
            structural_conflicts = tuple(
                sorted(
                    {
                        (
                            identity[0],
                            identity[1],
                            identity[2],
                            identity[3],
                        )
                        for identity in state.selected_identities
                    }
                )
            )
            active_exact_conflicts = tuple(
                sorted(
                    identity
                    for identity in state.selected_identities
                    if last_identity_position.get(identity, -1) >= next_position
                )
            )
            conflict_signature = (
                structural_conflicts,
                active_exact_conflicts,
            )
        return (
            score(state),
            state.class_counts,
            state.remaining_protected_tokens,
            state.remaining_unreserved_tokens,
            conflict_signature,
        )

    full_canonical_selection_limit = min(max_companions, len(companion_rows))
    canonical_selection_limit = (
        min(
            full_canonical_selection_limit,
            PARALLEL_ADMISSION_CANONICAL_SUFFIX_MAX_CARDINALITY,
        )
        if policy_version >= 21
        else full_canonical_selection_limit
    )
    suffix_lexicographic_ids: list[list[tuple[str, ...] | None]] = []
    if policy_version >= 20:
        suffix_lexicographic_ids = [
            [None] * (canonical_selection_limit + 1)
            for _ in range(len(companion_rows) + 1)
        ]
        suffix_lexicographic_ids[len(companion_rows)][0] = ()
        for position in range(len(companion_rows) - 1, -1, -1):
            suffix_lexicographic_ids[position][0] = ()
            candidate_id = str(companion_rows[position].get("candidate_id") or "")
            for count in range(1, canonical_selection_limit + 1):
                skipped = suffix_lexicographic_ids[position + 1][count]
                included_suffix = suffix_lexicographic_ids[position + 1][count - 1]
                included = (
                    (candidate_id, *included_suffix)
                    if included_suffix is not None
                    else None
                )
                suffix_lexicographic_ids[position][count] = (
                    included
                    if skipped is None
                    else skipped
                    if included is None
                    else min(included, skipped)
                )

    def canonical_candidate_id_lower_bound(
        state: _BeamAdmissionState,
        next_position: int,
        objective_bound: tuple[int, int, int, int],
    ) -> tuple[str, ...]:
        """Lower-bound the selected-ID tuple at one objective upper bound."""

        required = objective_bound[2] - len(state.selected_positions)
        if (
            required < 0
            or required > canonical_selection_limit
            or not suffix_lexicographic_ids
        ):
            return ()
        suffix = suffix_lexicographic_ids[next_position][required]
        if suffix is None:
            return ()
        return (*state.selected_candidate_ids, *suffix)

    # Optimistic suffix sums make beam retention globally informed rather than
    # ranking only the prefix already selected. The two sums are deliberately
    # independent, so this remains a valid upper bound under the lexicographic
    # objective even when one row cannot realize both components.
    suffix_fairness: list[tuple[int, ...]] = [()] * (len(companion_rows) + 1)
    suffix_priority: list[tuple[int, ...]] = [()] * (len(companion_rows) + 1)
    suffix_class_counts: list[Dict[str, int]] = [
        {} for _ in range(len(companion_rows) + 1)
    ]
    suffix_class_values: list[Dict[str, tuple[tuple[int, int], ...]]] = [
        {} for _ in range(len(companion_rows) + 1)
    ]
    suffix_class_resource_values: list[
        Dict[str, Dict[str, tuple[tuple[int, int], ...]]]
    ] = [{} for _ in range(len(companion_rows) + 1)]
    route_grouped_rows: list[tuple[int, int, tuple[str, ...]] | None] = [
        None
    ] * len(companion_rows) if policy_version >= 14 else []
    target_grouped_rows: list[tuple[int, int, tuple[str, ...]] | None] = [
        None
    ] * len(companion_rows) if policy_version >= 14 else []
    certification_filtered_route_rows = (
        {
            forbidden: list(route_grouped_rows)
            for forbidden in ("integration", "verification")
        }
        if policy_version == 15
        else {}
    )
    certification_filtered_target_rows = (
        {
            forbidden: list(target_grouped_rows)
            for forbidden in ("integration", "verification")
        }
        if policy_version == 15
        else {}
    )
    grouped_capacity_keys = tuple(
        sorted(
            {
                *capacity_keys,
                *(
                    _parallel_capacity_class(row)
                    for row in companion_rows
                ),
            }
        )
    ) if policy_version >= 16 else ()
    class_filtered_route_rows = (
        {
            forbidden: {
                capacity_key: list(route_grouped_rows)
                for capacity_key in grouped_capacity_keys
            }
            for forbidden in ("integration", "verification")
        }
        if policy_version >= 16
        else {}
    )
    class_filtered_target_rows = (
        {
            forbidden: {
                capacity_key: list(target_grouped_rows)
                for capacity_key in grouped_capacity_keys
            }
            for forbidden in ("integration", "verification")
        }
        if policy_version >= 16
        else {}
    )
    mixed_class_filtered_route_rows = (
        {
            discovery_class: {
                forbidden: {
                    capacity_key: list(route_grouped_rows)
                    for capacity_key in grouped_capacity_keys
                }
                for forbidden in ("integration", "verification")
            }
            for discovery_class in ("research", "adversarial")
        }
        if policy_version >= 16
        else {}
    )
    fair_values: list[int] = []
    priority_values: list[int] = []
    class_population: Dict[str, int] = {}
    class_values: Dict[str, tuple[tuple[int, int], ...]] = {}
    class_resource_values: Dict[
        str, Dict[str, tuple[tuple[int, int], ...]]
    ] = {}
    for position in range(len(companion_rows) - 1, -1, -1):
        capacity_key = _parallel_capacity_class(companion_rows[position])
        class_population = dict(class_population)
        class_population[capacity_key] = class_population.get(capacity_key, 0) + 1
        suffix_class_counts[position] = class_population
        fair_values = sorted(
            [*fair_values, fairness_weight(companion_rows[position])],
            reverse=True,
        )[:max_companions]
        priority_values = sorted(
            [
                *priority_values,
                int(companion_rows[position].get("admission_priority") or 0),
            ],
            reverse=True,
        )[:max_companions]
        suffix_fairness[position] = tuple(fair_values)
        suffix_priority[position] = tuple(priority_values)
        if policy_version == 12:
            class_values = dict(class_values)
            values = [
                *class_values.get(capacity_key, ()),
                (
                    fairness_weight(companion_rows[position]),
                    int(
                        companion_rows[position].get("admission_priority") or 0
                    ),
                ),
            ]
            values.sort(reverse=True)
            class_values[capacity_key] = tuple(values[:max_companions])
            suffix_class_values[position] = class_values
        elif policy_version >= 13:
            if aggregate_budget_enforced:
                class_resource_values = {
                    key: dict(groups)
                    for key, groups in class_resource_values.items()
                }
            row = companion_rows[position]
            request = max(0, int(row.get("requested_tokens") or 0))
            intrinsically_eligible = (
                row.get("budget_allowed") is True
                and not parallel_identity_conflict_reason(
                    tuple(row["semantic_identity"]),
                    [tuple(primary["semantic_identity"])],
                )
                and (
                    not aggregate_budget_enforced
                    or request == 0
                    or request >= MIN_STEP_BUDGET
                )
            )
            if intrinsically_eligible:
                row_value = (
                    fairness_weight(row),
                    int(row.get("admission_priority") or 0),
                )
                class_values = dict(class_values)
                unclassified_values = [
                    *class_values.get(capacity_key, ()),
                    row_value,
                ]
                unclassified_values.sort(reverse=True)
                class_values[capacity_key] = tuple(
                    unclassified_values[:max_companions]
                )
                if aggregate_budget_enforced:
                    resource_class = (
                        "free"
                        if request == 0
                        else "reserved_eligible"
                        if _parallel_uses_protected_budget(row)
                        else "shared_only"
                    )
                    groups = dict(class_resource_values.get(capacity_key, {}))
                    values = [
                        *groups.get(resource_class, ()),
                        row_value,
                    ]
                    values.sort(reverse=True)
                    groups[resource_class] = tuple(values[:max_companions])
                    class_resource_values[capacity_key] = groups
                if policy_version >= 14:
                    identity = tuple(row["semantic_identity"])
                    route_key = _parallel_route_clique_key(identity) or (
                        "route_singleton",
                        str(position),
                    )
                    target_key = _parallel_certification_target_clique_key(
                        identity
                    ) or ("target_singleton", str(position))
                    route_grouped_rows[position] = (*row_value, route_key)
                    target_grouped_rows[position] = (*row_value, target_key)
                    if policy_version >= 15:
                        for forbidden in ("integration", "verification"):
                            if identity[0] != forbidden:
                                if policy_version == 15:
                                    certification_filtered_route_rows[forbidden][
                                        position
                                    ] = (*row_value, route_key)
                                    certification_filtered_target_rows[forbidden][
                                        position
                                    ] = (*row_value, target_key)
                                else:
                                    class_filtered_route_rows[forbidden][capacity_key][
                                        position
                                    ] = (*row_value, route_key)
                                    class_filtered_target_rows[forbidden][capacity_key][
                                        position
                                    ] = (*row_value, target_key)
                                    for discovery_class in (
                                        "research",
                                        "adversarial",
                                    ):
                                        mixed_route_key = (
                                            _parallel_mixed_route_clique_key(
                                                identity,
                                                discovery_class=discovery_class,
                                            )
                                            or (
                                                "mixed_route_singleton",
                                                discovery_class,
                                                str(position),
                                            )
                                        )
                                        mixed_class_filtered_route_rows[
                                            discovery_class
                                        ][forbidden][capacity_key][position] = (
                                            *row_value,
                                            mixed_route_key,
                                        )
            suffix_class_values[position] = class_values
            if aggregate_budget_enforced:
                suffix_class_resource_values[position] = class_resource_values

    route_grouped_suffixes = (
        grouped_suffix_values(
            route_grouped_rows,
            selection_limit=max_companions,
        )
        if policy_version == 14
        else []
    )
    target_grouped_suffixes = (
        grouped_suffix_values(
            target_grouped_rows,
            selection_limit=max_companions,
        )
        if policy_version == 14
        else []
    )
    certification_filtered_route_suffixes = (
        {
            forbidden: grouped_suffix_values(
                rows,
                selection_limit=max_companions,
            )
            for forbidden, rows in certification_filtered_route_rows.items()
        }
        if policy_version == 15
        else {}
    )
    certification_filtered_target_suffixes = (
        {
            forbidden: grouped_suffix_values(
                rows,
                selection_limit=max_companions,
            )
            for forbidden, rows in certification_filtered_target_rows.items()
        }
        if policy_version == 15
        else {}
    )
    class_filtered_route_suffixes = (
        {
            forbidden: {
                capacity_key: grouped_suffix_values(
                    rows,
                    selection_limit=max_companions,
                )
                for capacity_key, rows in rows_by_class.items()
            }
            for forbidden, rows_by_class in class_filtered_route_rows.items()
        }
        if policy_version >= 16
        else {}
    )
    class_filtered_target_suffixes = (
        {
            forbidden: {
                capacity_key: grouped_suffix_values(
                    rows,
                    selection_limit=max_companions,
                )
                for capacity_key, rows in rows_by_class.items()
            }
            for forbidden, rows_by_class in class_filtered_target_rows.items()
        }
        if policy_version >= 16
        else {}
    )
    mixed_class_filtered_route_suffixes = (
        {
            discovery_class: {
                forbidden: {
                    capacity_key: grouped_suffix_values(
                        rows,
                        selection_limit=max_companions,
                    )
                    for capacity_key, rows in rows_by_class.items()
                }
                for forbidden, rows_by_class in rows_by_forbidden.items()
            }
            for discovery_class, rows_by_forbidden in (
                mixed_class_filtered_route_rows.items()
            )
        }
        if policy_version >= 16
        else {}
    )

    @lru_cache(maxsize=None)
    def class_relaxed_suffix_value(
        next_position: int,
        slots: int,
        class_counts: tuple[tuple[str, int], ...],
        remaining_protected_tokens: int,
        remaining_unreserved_tokens: int,
    ) -> tuple[int, int, int, int]:
        """Bound a suffix by class, certification, and current resource limits."""

        if slots <= 0:
            return (0, 0, 0, 0)
        counts = dict(class_counts)
        values_by_class = suffix_class_values[next_position]

        def solve(forbidden_class: str) -> tuple[int, int, int]:
            # dp[k] is the best relaxed value using exactly k further slots.
            dp: list[tuple[int, int, int] | None] = [None] * (slots + 1)
            dp[0] = (0, 0, 0)
            for capacity_key in sorted(values_by_class):
                values = values_by_class[capacity_key]
                limit = min(
                    slots,
                    len(values),
                    (
                        max(
                            0,
                            int(class_capacities[capacity_key])
                            - counts.get(capacity_key, 0),
                        )
                        if capacity_key in class_capacities
                        else slots
                    ),
                )
                if capacity_key == forbidden_class:
                    limit = 0
                options = [(0, 0, 0)]
                fairness_sum = 0
                priority_sum = 0
                for count, (fairness, priority) in enumerate(
                    values[:limit], start=1
                ):
                    fairness_sum += fairness
                    priority_sum += priority
                    options.append((fairness_sum, priority_sum, count))
                updated: list[tuple[int, int, int] | None] = [None] * (
                    slots + 1
                )
                for used, base_value in enumerate(dp):
                    if base_value is None:
                        continue
                    for option in options[: slots - used + 1]:
                        candidate = (
                            base_value[0] + option[0],
                            base_value[1] + option[1],
                            base_value[2] + option[2],
                        )
                        destination = used + option[2]
                        if (
                            updated[destination] is None
                            or candidate > updated[destination]
                        ):
                            updated[destination] = candidate
                dp = updated
            return max(value for value in dp if value is not None)

        if counts.get("verification", 0) > 0:
            forbidden_class = "integration"
        elif counts.get("integration", 0) > 0:
            forbidden_class = "verification"
        else:
            forbidden_class = ""
        if policy_version >= 13 and aggregate_budget_enforced:
            def solve_resource(forbidden: str) -> tuple[int, int, int, int]:
                return resource_relaxed_value(
                    suffix_class_resource_values[next_position],
                    slots=slots,
                    class_capacities=class_capacities,
                    class_counts=counts,
                    forbidden_class=forbidden,
                    remaining_reserved_tokens=remaining_protected_tokens,
                    remaining_shared_tokens=remaining_unreserved_tokens,
                    minimum_grant_tokens=MIN_STEP_BUDGET,
                )

            if forbidden_class:
                return solve_resource(forbidden_class)
            return max(
                solve_resource("integration"),
                solve_resource("verification"),
            )
        if forbidden_class:
            return (*solve(forbidden_class), 0)
        return (*max(solve("integration"), solve("verification")), 0)

    def optimistic_score(
        state: _BeamAdmissionState, next_position: int
    ) -> tuple[int, int, int, int]:
        current = score(state)
        total_slots = max(0, max_companions - len(state.selected_positions))
        if policy_version >= 12:
            suffix_value = class_relaxed_suffix_value(
                next_position,
                total_slots,
                state.class_counts,
                state.remaining_protected_tokens,
                state.remaining_unreserved_tokens,
            )
            class_resource_bound = (
                current[0] + suffix_value[0],
                current[1] + suffix_value[1],
                current[2] + suffix_value[2],
                current[3] + suffix_value[3],
            )
            if policy_version < 14:
                return class_resource_bound

            if policy_version == 14:
                route_value = grouped_relaxed_value(
                    route_grouped_suffixes[next_position],
                    slots=total_slots,
                    occupied_groups=state.route_clique_keys,
                )
                target_value = grouped_relaxed_value(
                    target_grouped_suffixes[next_position],
                    slots=total_slots,
                    occupied_groups=state.target_clique_keys,
                )
            elif policy_version == 15:
                counts = dict(state.class_counts)

                def certification_filtered_value(
                    suffixes_by_forbidden: Mapping[
                        str, Sequence[Sequence[tuple[int, int, Any]]]
                    ],
                    occupied_groups: Sequence[tuple[str, ...]],
                ) -> tuple[int, int, int]:
                    if counts.get("verification", 0) > 0:
                        forbidden_classes = ("integration",)
                    elif counts.get("integration", 0) > 0:
                        forbidden_classes = ("verification",)
                    else:
                        forbidden_classes = ("integration", "verification")
                    return max(
                        grouped_relaxed_value(
                            suffixes_by_forbidden[forbidden][next_position],
                            slots=total_slots,
                            occupied_groups=occupied_groups,
                        )
                        for forbidden in forbidden_classes
                    )

                route_value = certification_filtered_value(
                    certification_filtered_route_suffixes,
                    state.route_clique_keys,
                )
                target_value = certification_filtered_value(
                    certification_filtered_target_suffixes,
                    state.target_clique_keys,
                )
            else:
                counts = dict(state.class_counts)

                def class_filtered_value(
                    suffixes_by_forbidden: Mapping[
                        str,
                        Mapping[str, Sequence[Sequence[tuple[int, int, Any]]]],
                    ],
                    occupied_groups: Sequence[tuple[str, ...]],
                ) -> tuple[int, int, int]:
                    if counts.get("verification", 0) > 0:
                        forbidden_classes = ("integration",)
                    elif counts.get("integration", 0) > 0:
                        forbidden_classes = ("verification",)
                    else:
                        forbidden_classes = ("integration", "verification")
                    results: list[tuple[int, int, int]] = []
                    for forbidden in forbidden_classes:
                        available: list[tuple[int, int]] = []
                        for capacity_key, suffixes in suffixes_by_forbidden[
                            forbidden
                        ].items():
                            class_limit = min(
                                total_slots,
                                (
                                    max(
                                        0,
                                        int(class_capacities[capacity_key])
                                        - counts.get(capacity_key, 0),
                                    )
                                    if capacity_key in class_capacities
                                    else total_slots
                                ),
                            )
                            available.extend(
                                grouped_relaxed_rows(
                                    suffixes[next_position],
                                    slots=class_limit,
                                    occupied_groups=occupied_groups,
                                )
                            )
                        selected = sorted(available, reverse=True)[:total_slots]
                        results.append(
                            (
                                sum(value[0] for value in selected),
                                sum(value[1] for value in selected),
                                len(selected),
                            )
                        )
                    return max(results)

                route_value = min(
                    class_filtered_value(
                        class_filtered_route_suffixes,
                        state.route_clique_keys,
                    ),
                    *(
                        class_filtered_value(
                            mixed_class_filtered_route_suffixes[discovery_class],
                            occupied_groups=(
                                state.research_mixed_route_clique_keys
                                if discovery_class == "research"
                                else state.adversarial_mixed_route_clique_keys
                            ),
                        )
                        for discovery_class in ("research", "adversarial")
                    ),
                )
                target_value = class_filtered_value(
                    class_filtered_target_suffixes,
                    state.target_clique_keys,
                )
            return min(
                class_resource_bound,
                (
                    current[0] + route_value[0],
                    current[1] + route_value[1],
                    current[2] + route_value[2],
                    current[3],
                ),
                (
                    current[0] + target_value[0],
                    current[1] + target_value[1],
                    current[2] + target_value[2],
                    current[3],
                ),
            )
        counts = dict(state.class_counts)
        class_slots = sum(
            (
                min(
                    max(
                        0,
                        int(class_capacities[key]) - counts.get(key, 0),
                    ),
                    population,
                )
                if key in class_capacities
                else population
            )
            for key, population in suffix_class_counts[next_position].items()
        )
        slots = min(total_slots, class_slots)
        return (
            current[0] + sum(suffix_fairness[next_position][:slots]),
            current[1] + sum(suffix_priority[next_position][:slots]),
            current[2] + min(slots, len(companion_rows) - next_position),
            current[3],
        )

    def include(
        state: _BeamAdmissionState, position: int
    ) -> _BeamAdmissionState | None:
        row = companion_rows[position]
        if row.get("budget_allowed") is not True:
            return None
        identity = tuple(row["semantic_identity"])
        if parallel_identity_conflict_reason(
            identity,
            [
                tuple(primary["semantic_identity"]),
                *state.selected_identities,
            ],
        ):
            return None
        if len(state.selected_positions) >= max_companions:
            return None
        counts = dict(state.class_counts)
        capacity_key = _parallel_capacity_class(row)
        if (
            capacity_key in class_capacities
            and counts.get(capacity_key, 0) >= int(class_capacities[capacity_key])
        ):
            return None

        protected_tokens = state.remaining_protected_tokens
        unreserved_tokens = state.remaining_unreserved_tokens
        request = max(0, int(row.get("requested_tokens") or 0))
        grant = request
        if aggregate_budget_enforced and request:
            available = (
                protected_tokens + unreserved_tokens
                if _parallel_uses_protected_budget(row)
                else unreserved_tokens
            )
            if request < MIN_STEP_BUDGET or available < MIN_STEP_BUDGET:
                return None
            grant = (
                MIN_STEP_BUDGET
                if policy_version >= 11
                else min(request, available)
            )
            if _parallel_uses_protected_budget(row):
                protected_spend = min(grant, protected_tokens)
                protected_tokens -= protected_spend
                unreserved_tokens -= grant - protected_spend
            else:
                unreserved_tokens -= grant
        if capacity_key in counts:
            counts[capacity_key] += 1
        route_clique_key = _parallel_route_clique_key(identity)
        research_mixed_route_clique_key = _parallel_mixed_route_clique_key(
            identity,
            discovery_class="research",
        )
        adversarial_mixed_route_clique_key = _parallel_mixed_route_clique_key(
            identity,
            discovery_class="adversarial",
        )
        target_clique_key = _parallel_certification_target_clique_key(identity)
        return _BeamAdmissionState(
            (*state.selected_positions, position),
            (
                *state.selected_candidate_ids,
                str(row.get("candidate_id") or ""),
            ),
            (*state.selected_identities, identity),
            (
                *state.route_clique_keys,
                *((route_clique_key,) if route_clique_key is not None else ()),
            ),
            (
                *state.research_mixed_route_clique_keys,
                *(
                    (research_mixed_route_clique_key,)
                    if research_mixed_route_clique_key is not None
                    else ()
                ),
            ),
            (
                *state.adversarial_mixed_route_clique_keys,
                *(
                    (adversarial_mixed_route_clique_key,)
                    if adversarial_mixed_route_clique_key is not None
                    else ()
                ),
            ),
            (
                *state.target_clique_keys,
                *((target_clique_key,) if target_clique_key is not None else ()),
            ),
            (*state.grants, grant),
            tuple(sorted(counts.items())),
            protected_tokens,
            unreserved_tokens,
            state.fairness_value + fairness_weight(row),
            state.priority_value + int(row.get("admission_priority") or 0),
        )

    def anytime_completion(
        starting_incumbent: _BeamAdmissionState,
        *,
        starting_frontier: Sequence[
            tuple[_BeamAdmissionState, int]
        ] | None = None,
    ) -> tuple[
        _BeamAdmissionState,
        int,
        int,
        int,
        tuple[int, int, int, int] | None,
        tuple[str, ...] | None,
    ]:
        """Continue branch-and-bound best-first under a deterministic node limit."""

        best = starting_incumbent
        queue: list[
            tuple[
                tuple[int, int, int, int],
                tuple[str, ...],
                int,
                int,
                _BeamAdmissionState,
                tuple[Any, ...] | None,
                tuple[int, int, int, int],
            ]
        ] = []
        representatives: Dict[tuple[Any, ...], tuple[str, ...]] = {}
        serial = 0
        merged = 0

        def better_than_best(state: _BeamAdmissionState) -> bool:
            state_score = score(state)
            best_score = score(best)
            return state_score > best_score or (
                state_score == best_score
                and state.selected_candidate_ids < best.selected_candidate_ids
            )

        def enqueue(state: _BeamAdmissionState, next_position: int) -> None:
            nonlocal serial, merged
            bound = optimistic_score(state, next_position)
            best_score = score(best)
            canonical_bound = canonical_candidate_id_lower_bound(
                state, next_position, bound
            )
            if bound < best_score or (
                bound == best_score
                and canonical_bound >= best.selected_candidate_ids
            ):
                return
            equivalence_key: tuple[Any, ...] | None = None
            if quotient_equivalent_states:
                equivalence_key = (
                    next_position,
                    future_equivalence_key(state, next_position),
                )
                representative_ids = representatives.get(equivalence_key)
                if (
                    representative_ids is not None
                    and representative_ids <= state.selected_candidate_ids
                ):
                    merged += 1
                    return
                if representative_ids is not None:
                    merged += 1
                representatives[equivalence_key] = state.selected_candidate_ids
            heapq.heappush(
                queue,
                (
                    tuple(-value for value in bound),
                    canonical_bound,
                    next_position,
                    serial,
                    state,
                    equivalence_key,
                    bound,
                ),
            )
            serial += 1

        for frontier_state, next_position in (
            starting_frontier
            if starting_frontier
            else ((initial, 0),)
        ):
            enqueue(frontier_state, next_position)
        expanded = 0
        while queue and expanded < PARALLEL_ADMISSION_ANYTIME_STATE_LIMIT:
            (
                _priority,
                canonical_bound,
                next_position,
                _serial,
                state,
                equivalence_key,
                bound,
            ) = heapq.heappop(queue)
            expanded += 1
            if (
                equivalence_key is not None
                and representatives.get(equivalence_key)
                != state.selected_candidate_ids
            ):
                continue
            best_score = score(best)
            if bound < best_score or (
                bound == best_score
                and canonical_bound >= best.selected_candidate_ids
            ):
                continue
            if next_position >= len(companion_rows):
                if better_than_best(state):
                    best = state
                continue
            following_position = next_position + 1
            children = [state]
            admitted = include(state, next_position)
            if admitted is not None:
                children.append(admitted)
            for child in children:
                if better_than_best(child):
                    best = child
                enqueue(child, following_position)

        best_score = score(best)
        viable_frontier: list[
            tuple[tuple[int, int, int, int], tuple[str, ...]]
        ] = []
        for (
            _priority,
            canonical_bound,
            _next_position,
            _serial,
            state,
            equivalence_key,
            bound,
        ) in queue:
            if (
                equivalence_key is not None
                and representatives.get(equivalence_key)
                != state.selected_candidate_ids
            ):
                continue
            if bound < best_score or (
                bound == best_score
                and canonical_bound >= best.selected_candidate_ids
            ):
                continue
            viable_frontier.append((bound, canonical_bound))
        if not viable_frontier:
            return best, expanded, merged, 0, None, None
        frontier_upper_bound = max(bound for bound, _canonical in viable_frontier)
        frontier_canonical_bound = min(
            canonical
            for bound, canonical in viable_frontier
            if bound == frontier_upper_bound
        )
        return (
            best,
            expanded,
            merged,
            len(viable_frontier),
            frontier_upper_bound,
            frontier_canonical_bound,
        )

    beam = [initial]
    incumbent = initial
    states_expanded = 0
    states_pruned_by_bound = 0
    states_pruned_at_incumbent_bound = 0
    states_pruned_by_canonical_bound = 0
    states_merged_by_future_equivalence = 0
    states_pruned_by_dominance = 0
    state_dominance_applied = False
    retained_peak = 1
    beam_truncated = False
    discarded_upper_bound: tuple[int, int, int, int] | None = None
    discarded_canonical_lower_bound: tuple[str, ...] | None = None
    discarded_frontier: list[tuple[_BeamAdmissionState, int]] = []
    discarded_frontier_state_count = 0
    discarded_frontier_limit_reached = False
    for position in range(len(companion_rows)):
        expanded: list[_BeamAdmissionState] = []
        for state in beam:
            expanded.append(state)
            states_expanded += 1
            admitted = include(state, position)
            if admitted is not None:
                expanded.append(admitted)
                states_expanded += 1
        # Canonicalize ties before both incumbent selection and the stable
        # descending upper-bound sort.
        expanded.sort(key=lambda state: state.selected_candidate_ids)
        if quotient_equivalent_states:
            representatives: Dict[tuple[Any, ...], _BeamAdmissionState] = {}
            for state in expanded:
                representatives.setdefault(
                    future_equivalence_key(state, position + 1),
                    state,
                )
            states_merged_by_future_equivalence += len(expanded) - len(
                representatives
            )
            expanded = list(representatives.values())
        if exact_state_dominance_available and (
            len(companion_rows) <= PARALLEL_ADMISSION_WIDE_BEAM_MAX_CANDIDATES
            or len(expanded) <= PARALLEL_ADMISSION_DOMINANCE_MAX_FRONTIER
        ):
            state_dominance_applied = True
            expanded, removed = _parallel_nondominated_states(
                expanded,
                suffix_conflict_masks=suffix_conflict_masks,
                next_position=position + 1,
            )
            states_pruned_by_dominance += removed
        iteration_best = max(expanded, key=score)
        if score(iteration_best) > score(incumbent) or (
            score(iteration_best) == score(incumbent)
            and iteration_best.selected_candidate_ids
            < incumbent.selected_candidate_ids
        ):
            incumbent = iteration_best
        incumbent_score = score(incumbent)
        if policy_version >= 19 and position + 1 == len(companion_rows):
            # Every terminal state has already participated in the incumbent
            # comparison. There is no suffix to retain, prune, or truncate.
            beam = []
            break
        bounded_states = [
            (optimistic_score(state, position + 1), state) for state in expanded
        ]
        if policy_version >= 19 and not retain_equal_objective_bounds:
            states_pruned_at_incumbent_bound += sum(
                bound == incumbent_score for bound, _state in bounded_states
            )
        viable: list[
            tuple[tuple[int, int, int, int], _BeamAdmissionState]
        ] = []
        for bounded_state in bounded_states:
            bound, state = bounded_state
            if policy_version >= 20:
                retain = bound > incumbent_score or (
                    bound == incumbent_score
                    and canonical_candidate_id_lower_bound(
                        state, position + 1, bound
                    )
                    < incumbent.selected_candidate_ids
                )
                if bound == incumbent_score and not retain:
                    states_pruned_by_canonical_bound += 1
            else:
                retain = (
                    bound >= incumbent_score
                    if retain_equal_objective_bounds
                    else bound > incumbent_score
                )
            if retain:
                viable.append(bounded_state)
        states_pruned_by_bound += len(bounded_states) - len(viable)
        if not viable:
            beam = []
            break
        if policy_version >= 20:
            viable.sort(
                key=lambda bounded_state: canonical_candidate_id_lower_bound(
                    bounded_state[1], position + 1, bounded_state[0]
                )
            )
        viable.sort(key=lambda bounded_state: bounded_state[0], reverse=True)
        if len(viable) > search_beam_width:
            beam_truncated = True
            if policy_version >= 10:
                first_discarded_bound = viable[
                    search_beam_width
                ][0]
                if policy_version >= 20:
                    discarded_tie_bound = min(
                        canonical_candidate_id_lower_bound(
                            state, position + 1, bound
                        )
                        for bound, state in viable[search_beam_width:]
                        if bound == first_discarded_bound
                    )
                    if (
                        discarded_upper_bound is None
                        or first_discarded_bound > discarded_upper_bound
                    ):
                        discarded_canonical_lower_bound = discarded_tie_bound
                    elif first_discarded_bound == discarded_upper_bound:
                        discarded_canonical_lower_bound = min(
                            (
                                discarded_canonical_lower_bound
                                if discarded_canonical_lower_bound is not None
                                else discarded_tie_bound
                            ),
                            discarded_tie_bound,
                        )
                discarded_upper_bound = max(
                    discarded_upper_bound or first_discarded_bound,
                    first_discarded_bound,
                )
            if policy_version >= 24:
                new_discarded_frontier = [
                    (state, position + 1)
                    for _bound, state in viable[search_beam_width:]
                ]
                discarded_frontier_state_count += len(new_discarded_frontier)
                if policy_version == 24:
                    discarded_frontier.extend(new_discarded_frontier)
                elif not discarded_frontier_limit_reached:
                    if (
                        len(discarded_frontier) + len(new_discarded_frontier)
                        <= PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT
                    ):
                        discarded_frontier.extend(new_discarded_frontier)
                    else:
                        discarded_frontier.clear()
                        discarded_frontier_limit_reached = True
            del viable[search_beam_width:]
        beam = [state for _bound, state in viable]
        retained_peak = max(retained_peak, len(beam))

    selected_state = incumbent
    if policy_version >= 11:
        baseline_outcomes, _baseline_remaining = _parallel_admission_outcomes_impl(
            rows,
            total_capacity=total_capacity,
            class_capacities=class_capacities,
            aggregate_budget_enforced=aggregate_budget_enforced,
            initial_remaining_token_budget=initial_remaining_token_budget,
            initial_reserved_verification_budget=(
                initial_reserved_verification_budget
            ),
            policy_version=8,
        )
        baseline_selected_ids = [
            str(row.get("candidate_id") or "")
            for row in companion_rows
            if baseline_outcomes[str(row.get("candidate_id") or "")].disposition
            == "selected"
        ]
        baseline_selected_id_set = set(baseline_selected_ids)
        baseline_state = initial
        for position, row in enumerate(companion_rows):
            if str(row.get("candidate_id") or "") not in baseline_selected_id_set:
                continue
            admitted = include(baseline_state, position)
            if admitted is None:
                raise RuntimeError(
                    "the policy-v8 lower bound is infeasible under policy-v11 "
                    "minimum-grant admission"
                )
            baseline_state = admitted
        baseline_objective = score(baseline_state)
        search_objective = score(selected_state)
        selected_policy = "beam_search"
        if baseline_objective > search_objective or (
            policy_version >= 19
            and baseline_objective == search_objective
            and baseline_state.selected_candidate_ids
            < selected_state.selected_candidate_ids
        ):
            # Beam truncation must never make the new epoch worse than the
            # feasible subset selected by the historical deterministic policy.
            selected_state = baseline_state
            search_objective = baseline_objective
            selected_policy = "greedy_lower_bound"

        beam_selected_objective = search_objective
        beam_discarded_upper_bound = discarded_upper_bound
        beam_upper_bound = max(
            search_objective,
            discarded_upper_bound or search_objective,
        )
        beam_discarded_canonical_lower_bound = discarded_canonical_lower_bound
        anytime_completion_status = "not_needed"
        anytime_states_expanded = 0
        anytime_states_merged = 0
        anytime_frontier_size = 0
        anytime_improved_selection = False
        needs_anytime_completion = beam_upper_bound > search_objective or (
            beam_upper_bound == search_objective
            and discarded_upper_bound == search_objective
            and discarded_canonical_lower_bound is not None
            and discarded_canonical_lower_bound
            < selected_state.selected_candidate_ids
        )
        if policy_version >= 22 and needs_anytime_completion:
            prior_state = selected_state
            (
                selected_state,
                anytime_states_expanded,
                anytime_states_merged,
                anytime_frontier_size,
                discarded_upper_bound,
                discarded_canonical_lower_bound,
            ) = anytime_completion(
                selected_state,
                starting_frontier=(
                    discarded_frontier
                    if policy_version >= 24
                    and not discarded_frontier_limit_reached
                    else None
                ),
            )
            search_objective = score(selected_state)
            anytime_improved_selection = (
                score(selected_state) > score(prior_state)
                or selected_state.selected_candidate_ids
                < prior_state.selected_candidate_ids
            )
            if anytime_improved_selection:
                selected_policy = "anytime_completion"
            anytime_completion_status = (
                "exact"
                if discarded_upper_bound is None
                else "state_limit_reached"
            )

        selected_positions = list(selected_state.selected_positions)
        selected_rows = [companion_rows[position] for position in selected_positions]
        grant_by_position = dict(zip(selected_positions, selected_state.grants))
        remaining_protected = selected_state.remaining_protected_tokens
        remaining_unreserved = selected_state.remaining_unreserved_tokens
        if aggregate_budget_enforced:
            # Reserved verification capacity cannot help an unprotected task,
            # so distribute it among protected tasks first. The shared pool is
            # then max-min allocated across all selected tasks. Both passes are
            # deterministic and never change the certified companion subset.
            selected_requests = {
                position: int(
                    companion_rows[position].get("requested_tokens") or 0
                )
                for position in selected_positions
            }
            grant_by_position, remaining_protected = _max_min_token_top_up(
                grant_by_position,
                selected_requests,
                [
                    position
                    for position in selected_positions
                    if _parallel_uses_protected_budget(companion_rows[position])
                ],
                remaining_protected,
            )
            grant_by_position, remaining_unreserved = _max_min_token_top_up(
                grant_by_position,
                selected_requests,
                selected_positions,
                remaining_unreserved,
            )
        grant_by_candidate_id = {
            str(companion_rows[position].get("candidate_id") or ""): grant
            for position, grant in grant_by_position.items()
        }

        selected_id_set = {
            str(row.get("candidate_id") or "") for row in selected_rows
        }
        outcomes: Dict[str, ParallelAdmissionOutcome] = {
            str(primary["candidate_id"]): ParallelAdmissionOutcome(
                "fixed_primary",
                "the primary action was selected by the main scheduler",
                "fixed_primary",
                max(0, int(primary.get("requested_tokens") or 0)),
            )
        }
        final_counts = dict(selected_state.class_counts)
        admitted_identities = [
            tuple(row["semantic_identity"]) for row in selected_rows
        ]
        for row in all_companion_rows:
            candidate_id = str(row["candidate_id"])
            request = max(0, int(row.get("requested_tokens") or 0))
            if candidate_id in selected_id_set:
                grant = grant_by_candidate_id[candidate_id]
                due = fairness_weight(row) > 0
                if grant != request:
                    reason = (
                        "admitted with token grant reduced by the fixed-compute "
                        "global admission search"
                    )
                    outcome_code = "selected_reduced_allocation"
                elif due:
                    reason = (
                        "admitted by max-weight fairness in the fixed-compute "
                        "global admission search"
                    )
                    outcome_code = "selected_fairness_search"
                else:
                    reason = "admitted by the fixed-compute global admission search"
                    outcome_code = "selected_search"
                outcomes[candidate_id] = ParallelAdmissionOutcome(
                    "selected", reason, outcome_code, grant
                )
                continue

            identity = tuple(row["semantic_identity"])
            rejection, primary_conflict_is_serializable = parallel_identity_conflict(
                identity, [tuple(primary["semantic_identity"])]
            )
            if rejection:
                rejection_code = (
                    PRIMARY_SERIALIZATION_OUTCOME_CODE
                    if primary_conflict_is_serializable
                    else "primary_or_structural_conflict"
                )
            elif row.get("budget_allowed") is not True:
                rejection = "candidate budget does not authorize dispatch"
                rejection_code = "budget_unauthorized"
            else:
                sibling_conflict = parallel_identity_conflict_reason(
                    identity, admitted_identities
                )
                if sibling_conflict:
                    rejection = "queued behind conflicting companion: " + sibling_conflict
                    rejection_code = "sibling_conflict_queue"
                elif len(selected_rows) >= max_companions:
                    rejection = "total wave capacity reached"
                    rejection_code = "total_capacity_queue"
                else:
                    capacity_key = _parallel_capacity_class(row)
                    if (
                        capacity_key in class_capacities
                        and final_counts.get(capacity_key, 0)
                        >= int(class_capacities[capacity_key])
                    ):
                        rejection = f"{capacity_key} capacity reached"
                        rejection_code = "class_capacity_queue"
                    elif aggregate_budget_enforced and request:
                        available = (
                            remaining_protected + remaining_unreserved
                            if _parallel_uses_protected_budget(row)
                            else remaining_unreserved
                        )
                        if available <= 0:
                            rejection = "aggregate wave token allocation exhausted"
                            rejection_code = "aggregate_allocation_queue"
                        elif request < MIN_STEP_BUDGET or available < MIN_STEP_BUDGET:
                            rejection = (
                                "aggregate token allocation is below the minimum "
                                "useful step size"
                            )
                            rejection_code = "minimum_useful_allocation_queue"
                        else:
                            rejection = (
                                "candidate was not selected by the fixed-compute "
                                "global admission search"
                            )
                            rejection_code = "bounded_search_queue"
                    else:
                        rejection = (
                            "candidate was not selected by the fixed-compute "
                            "global admission search"
                        )
                        rejection_code = "bounded_search_queue"
            outcomes[candidate_id] = ParallelAdmissionOutcome(
                "rejected", rejection, rejection_code, 0
            )

        selected_ids = list(selected_state.selected_candidate_ids)
        remaining = (
            remaining_protected + remaining_unreserved
            if aggregate_budget_enforced
            else 0
        )
        certified_upper_bound = max(
            search_objective,
            discarded_upper_bound or search_objective,
        )
        optimality_certified = certified_upper_bound <= search_objective
        metadata = {
            "version": (
                PARALLEL_ADMISSION_BOUNDED_FRONTIER_CERTIFICATE_VERSION
                if policy_version >= 25
                else PARALLEL_ADMISSION_FRONTIER_COMPLETION_CERTIFICATE_VERSION
                if policy_version >= 24
                else PARALLEL_ADMISSION_INTRINSIC_FILTER_CERTIFICATE_VERSION
                if policy_version >= 23
                else PARALLEL_ADMISSION_ANYTIME_BOUND_CERTIFICATE_VERSION
                if policy_version >= 22
                else PARALLEL_ADMISSION_DOMINANCE_BOUND_CERTIFICATE_VERSION
                if policy_version >= 21
                else PARALLEL_ADMISSION_CANONICAL_SUFFIX_BOUND_CERTIFICATE_VERSION
                if policy_version >= 20
                else PARALLEL_ADMISSION_CANONICAL_BOUND_CERTIFICATE_VERSION
                if policy_version >= 19
                else PARALLEL_ADMISSION_NEIGHBORHOOD_BOUND_CERTIFICATE_VERSION
                if policy_version >= 18
                else PARALLEL_ADMISSION_EQUIVALENCE_BOUND_CERTIFICATE_VERSION
                if policy_version >= 17
                else PARALLEL_ADMISSION_CLASS_CLIQUE_BOUND_CERTIFICATE_VERSION
                if policy_version >= 16
                else PARALLEL_ADMISSION_CERTIFICATION_CLIQUE_BOUND_CERTIFICATE_VERSION
                if policy_version >= 15
                else PARALLEL_ADMISSION_CLIQUE_BOUND_CERTIFICATE_VERSION
                if policy_version >= 14
                else PARALLEL_ADMISSION_RESOURCE_BOUND_CERTIFICATE_VERSION
                if policy_version >= 13
                else PARALLEL_ADMISSION_CLASS_BOUND_CERTIFICATE_VERSION
                if policy_version >= 12
                else PARALLEL_ADMISSION_ALLOCATION_CERTIFICATE_VERSION
            ),
            "algorithm": (
                "intrinsic_feasibility_filtered_deterministic_beam_branch_bound_"
                "with_bounded_memory_certificate_triggered_best_first_adaptive_"
                "pruned_frontier_completion_adaptive_exact_state_dominance_"
                "canonical_suffix_bound_exact_conflict_neighborhood_quotient_"
                "class_resource_and_class_certification_filtered_mixed_route_"
                "target_clique_relaxations_minimum_grant_feasibility_and_greedy_"
                "lower_bound"
                if policy_version >= 25
                else "intrinsic_feasibility_filtered_deterministic_beam_branch_bound_"
                "with_certificate_triggered_best_first_pruned_frontier_completion_"
                "adaptive_exact_state_dominance_canonical_suffix_bound_exact_"
                "conflict_neighborhood_quotient_class_resource_and_class_"
                "certification_filtered_mixed_route_target_clique_relaxations_"
                "minimum_grant_feasibility_and_greedy_lower_bound"
                if policy_version >= 24
                else "intrinsic_feasibility_filtered_deterministic_beam_branch_bound_"
                "with_certificate_triggered_best_first_anytime_completion_"
                "adaptive_exact_state_dominance_canonical_suffix_bound_exact_"
                "conflict_neighborhood_quotient_class_resource_and_class_"
                "certification_filtered_mixed_route_target_clique_relaxations_"
                "minimum_grant_feasibility_and_greedy_lower_bound"
                if policy_version >= 23
                else "deterministic_beam_branch_bound_with_certificate_triggered_"
                "best_first_anytime_completion_adaptive_exact_state_dominance_"
                "canonical_suffix_bound_exact_conflict_neighborhood_quotient_"
                "class_resource_and_class_certification_filtered_mixed_route_"
                "target_clique_relaxations_minimum_grant_feasibility_and_greedy_"
                "lower_bound"
                if policy_version >= 22
                else "deterministic_beam_branch_bound_with_adaptive_exact_state_"
                "dominance_"
                "canonical_suffix_bound_exact_conflict_neighborhood_quotient_"
                "class_resource_and_class_certification_filtered_mixed_route_"
                "target_clique_relaxations_minimum_grant_feasibility_and_greedy_"
                "lower_bound"
                if policy_version >= 21
                else "deterministic_beam_branch_bound_with_canonical_suffix_bound_"
                "exact_conflict_neighborhood_quotient_class_resource_and_class_"
                "certification_filtered_mixed_route_target_clique_relaxations_"
                "minimum_grant_feasibility_and_greedy_lower_bound"
                if policy_version >= 20
                else "deterministic_beam_branch_bound_with_canonical_tie_retention_"
                "exact_suffix_conflict_neighborhood_quotient_class_resource_and_"
                "class_certification_filtered_mixed_route_target_clique_"
                "relaxations_minimum_grant_feasibility_and_greedy_lower_bound"
                if policy_version >= 19
                else "deterministic_beam_branch_bound_with_exact_suffix_conflict_"
                "neighborhood_quotient_class_resource_and_class_certification_"
                "filtered_mixed_route_target_clique_relaxations_minimum_grant_"
                "feasibility_and_greedy_lower_bound"
                if policy_version >= 18
                else "deterministic_beam_branch_bound_with_future_conflict_"
                "equivalence_quotient_class_resource_and_class_certification_"
                "filtered_mixed_route_target_clique_relaxations_minimum_grant_"
                "feasibility_and_greedy_lower_bound"
                if policy_version >= 17
                else "deterministic_beam_branch_bound_with_class_resource_and_"
                "class_certification_filtered_mixed_route_target_clique_"
                "relaxations_"
                "minimum_grant_feasibility_and_greedy_lower_bound"
                if policy_version >= 16
                else "deterministic_beam_branch_bound_with_class_resource_and_"
                "certification_filtered_route_target_clique_relaxations_"
                "minimum_grant_feasibility_and_greedy_lower_bound"
                if policy_version >= 15
                else "deterministic_beam_branch_bound_with_class_resource_route_"
                "and_certification_target_clique_relaxations_minimum_grant_"
                "feasibility_and_greedy_lower_bound"
                if policy_version >= 14
                else "deterministic_beam_branch_bound_with_class_resource_conflict_"
                "relaxation_minimum_grant_feasibility_and_greedy_lower_bound"
                if policy_version >= 13
                else
                "deterministic_beam_branch_bound_with_class_conflict_"
                "relaxation_minimum_grant_feasibility_and_greedy_lower_bound"
                if policy_version >= 12
                else "deterministic_beam_branch_bound_with_minimum_grant_"
                "feasibility_and_greedy_lower_bound"
            ),
            "beam_width": search_beam_width,
            "candidate_count": len(all_companion_rows),
            **(
                {
                    "search_candidate_count": len(companion_rows),
                    "intrinsically_infeasible_candidate_count": (
                        len(all_companion_rows) - len(companion_rows)
                    ),
                    "intrinsic_candidate_filter": (
                        "authorization_primary_conflict_class_capacity_"
                        "minimum_grant_and_available_token_feasibility"
                    ),
                }
                if policy_version >= 23
                else {}
            ),
            "states_expanded": states_expanded,
            "states_pruned_by_bound": states_pruned_by_bound,
            **(
                {
                    "future_equivalence_quotient_applied": (
                        quotient_equivalent_states
                    ),
                    "states_merged_by_future_equivalence": (
                        states_merged_by_future_equivalence
                    ),
                    **(
                        {
                            "future_equivalence_basis": (
                                "exact_suffix_conflict_neighborhood"
                                if quotient_by_suffix_conflict_neighborhood
                                else "semantic_conflict_projection"
                                if quotient_by_conflict_projection
                                else "disabled"
                            )
                        }
                        if policy_version >= 18
                        else {}
                    ),
                }
                if policy_version >= 17
                else {}
            ),
            "states_retained_peak": retained_peak,
            "pruned": beam_truncated,
            "optimality": (
                "exact" if optimality_certified else "bounded_approximation"
            ),
            "optimality_certified": optimality_certified,
            "objective": (
                "lexicographic(max_weight_fairness, admission_priority_sum, "
                "selected_count, remaining_tokens_after_minimum_grants)"
            ),
            "objective_value": list(search_objective),
            "upper_bound_objective_value": list(certified_upper_bound),
            "selected_companion_ids": selected_ids,
            "minimum_useful_grant_tokens": MIN_STEP_BUDGET,
            "allocation_strategy": (
                "minimum_feasible_grants_then_reserved_and_max_min_fair_top_up"
            ),
            "greedy_baseline_policy_version": 8,
            "greedy_baseline_objective_value": list(baseline_objective),
            "selected_policy": selected_policy,
            "dominates_or_equals_greedy_baseline": True,
            "model_self_scores_used": False,
        }
        if policy_version >= 20:
            canonical_selection_certified = optimality_certified and (
                discarded_upper_bound is None
                or discarded_upper_bound < search_objective
                or (
                    discarded_upper_bound == search_objective
                    and discarded_canonical_lower_bound is not None
                    and discarded_canonical_lower_bound
                    >= selected_state.selected_candidate_ids
                )
            )
            metadata.update(
                {
                    "canonical_tie_break": (
                        "lexicographically_minimum_selected_candidate_ids"
                    ),
                    "canonical_selection_certified": (
                        canonical_selection_certified
                    ),
                    "canonical_lower_bound": (
                        "lexicographically_minimum_suffix_subsequence_at_"
                        "objective_cardinality"
                    ),
                    "canonical_suffix_cardinality_limit": (
                        canonical_selection_limit
                    ),
                    **(
                        {
                            "canonical_suffix_cardinality_cap": (
                                PARALLEL_ADMISSION_CANONICAL_SUFFIX_MAX_CARDINALITY
                            ),
                            "canonical_suffix_cardinality_complete": (
                                canonical_selection_limit
                                == full_canonical_selection_limit
                            ),
                        }
                        if policy_version >= 21
                        else {}
                    ),
                    "discarded_canonical_lower_bound_candidate_ids": (
                        list(discarded_canonical_lower_bound)
                        if discarded_canonical_lower_bound is not None
                        else None
                    ),
                    "discarded_upper_bound_objective_value": (
                        list(discarded_upper_bound)
                        if discarded_upper_bound is not None
                        else None
                    ),
                    "states_pruned_by_canonical_bound": (
                        states_pruned_by_canonical_bound
                    ),
                    **(
                        {
                            "state_dominance": (
                                "componentwise_capacity_resources_and_exact_"
                                "suffix_conflict_inclusion"
                            ),
                            "state_dominance_applied": (
                                state_dominance_applied
                            ),
                            "state_dominance_frontier_limit": (
                                PARALLEL_ADMISSION_DOMINANCE_MAX_FRONTIER
                            ),
                            "states_pruned_by_dominance": (
                                states_pruned_by_dominance
                            ),
                            **(
                                {
                                    "anytime_completion_status": (
                                        anytime_completion_status
                                    ),
                                    "anytime_completion_triggered": (
                                        needs_anytime_completion
                                    ),
                                    "anytime_state_limit": (
                                        PARALLEL_ADMISSION_ANYTIME_STATE_LIMIT
                                    ),
                                    "anytime_states_expanded": (
                                        anytime_states_expanded
                                    ),
                                    "anytime_states_merged_by_future_equivalence": (
                                        anytime_states_merged
                                    ),
                                    "anytime_frontier_size": (
                                        anytime_frontier_size
                                    ),
                                    "anytime_improved_selection": (
                                        anytime_improved_selection
                                    ),
                                    "beam_objective_value": list(
                                        beam_selected_objective
                                    ),
                                    "beam_upper_bound_objective_value": list(
                                        beam_upper_bound
                                    ),
                                    "beam_discarded_canonical_lower_bound_candidate_ids": (
                                        list(beam_discarded_canonical_lower_bound)
                                        if beam_discarded_canonical_lower_bound
                                        is not None
                                        else None
                                    ),
                                    "beam_discarded_upper_bound_objective_value": (
                                        list(beam_discarded_upper_bound)
                                        if beam_discarded_upper_bound is not None
                                        else None
                                    ),
                                    **(
                                        {
                                            "anytime_completion_frontier_source": (
                                                "root_restart_after_frontier_limit"
                                                if discarded_frontier_limit_reached
                                                else "pruned_beam_frontier"
                                            ),
                                            "beam_discarded_frontier_size": len(
                                                discarded_frontier
                                            ),
                                            **(
                                                {
                                                    "beam_discarded_frontier_state_count": (
                                                        discarded_frontier_state_count
                                                    ),
                                                    "beam_discarded_frontier_state_limit": (
                                                        PARALLEL_ADMISSION_COMPLETION_FRONTIER_STATE_LIMIT
                                                    ),
                                                    "beam_discarded_frontier_limit_reached": (
                                                        discarded_frontier_limit_reached
                                                    ),
                                                }
                                                if policy_version >= 25
                                                else {}
                                            ),
                                        }
                                        if policy_version >= 24
                                        else {}
                                    ),
                                }
                                if policy_version >= 22
                                else {}
                            ),
                        }
                        if policy_version >= 21
                        else {}
                    ),
                }
            )
        elif policy_version >= 19:
            metadata.update(
                {
                    "canonical_tie_break": (
                        "lexicographically_minimum_selected_candidate_ids"
                    ),
                    "canonical_selection_certified": (
                        optimality_certified
                        and states_pruned_at_incumbent_bound == 0
                        and (
                            discarded_upper_bound is None
                            or discarded_upper_bound < search_objective
                        )
                    ),
                    "equal_objective_bound_retention": (
                        retain_equal_objective_bounds
                    ),
                    "states_pruned_at_incumbent_bound": (
                        states_pruned_at_incumbent_bound
                    ),
                }
            )
        if policy_version >= 18:
            metadata["upper_bound_relaxation"] = (
                "primary_conflicts_minimum_token_resources_class_certification_"
                "filtered_mixed_route_target_cliques_and_exact_suffix_conflict_"
                "neighborhoods"
            )
        elif policy_version >= 17:
            metadata["upper_bound_relaxation"] = (
                "primary_conflicts_minimum_token_resources_class_certification_"
                "filtered_mixed_route_target_cliques_and_future_conflict_"
                "equivalence"
            )
        elif policy_version >= 16:
            metadata["upper_bound_relaxation"] = (
                "primary_conflicts_minimum_token_resources_and_class_"
                "certification_filtered_mixed_route_and_target_cliques"
            )
        elif policy_version >= 15:
            metadata["upper_bound_relaxation"] = (
                "class_capacities_primary_conflicts_minimum_token_resources_"
                "and_certification_filtered_route_and_target_cliques"
            )
        elif policy_version >= 14:
            metadata["upper_bound_relaxation"] = (
                "class_capacities_verification_integration_exclusion_primary_"
                "conflicts_minimum_token_resources_route_cliques_and_"
                "certification_target_cliques"
            )
        elif policy_version >= 13:
            metadata["upper_bound_relaxation"] = (
                "class_capacities_verification_integration_exclusion_primary_"
                "conflicts_and_minimum_token_resources"
            )
        elif policy_version >= 12:
            metadata["upper_bound_relaxation"] = (
                "class_capacities_and_verification_integration_exclusion"
            )
        return outcomes, remaining, metadata

    selected_grants = dict(
        zip(selected_state.selected_positions, selected_state.grants)
    )
    selected_rows = [
        companion_rows[position] for position in selected_state.selected_positions
    ]
    selected_id_set = {
        str(row.get("candidate_id") or "") for row in selected_rows
    }

    outcomes: Dict[str, ParallelAdmissionOutcome] = {
        str(primary["candidate_id"]): ParallelAdmissionOutcome(
            "fixed_primary",
            "the primary action was selected by the main scheduler",
            "fixed_primary",
            max(0, int(primary.get("requested_tokens") or 0)),
        )
    }
    final_counts = dict(selected_state.class_counts)
    admitted_identities = [tuple(row["semantic_identity"]) for row in selected_rows]
    for position, row in enumerate(companion_rows):
        candidate_id = str(row["candidate_id"])
        request = max(0, int(row.get("requested_tokens") or 0))
        if candidate_id in selected_id_set:
            grant = selected_grants[position]
            due = fairness_weight(row) > 0
            if grant != request:
                reason = (
                    "admitted with token grant reduced by the fixed-compute global admission search"
                )
                outcome_code = "selected_reduced_allocation"
            elif due:
                reason = "admitted by max-weight fairness in the fixed-compute global admission search"
                outcome_code = "selected_fairness_search"
            else:
                reason = "admitted by the fixed-compute global admission search"
                outcome_code = "selected_search"
            outcomes[candidate_id] = ParallelAdmissionOutcome(
                "selected", reason, outcome_code, grant
            )
            continue

        identity = tuple(row["semantic_identity"])
        rejection, primary_conflict_is_serializable = parallel_identity_conflict(
            identity, [tuple(primary["semantic_identity"])]
        )
        if rejection:
            rejection_code = (
                PRIMARY_SERIALIZATION_OUTCOME_CODE
                if primary_conflict_is_serializable
                else "primary_or_structural_conflict"
            )
        elif row.get("budget_allowed") is not True:
            rejection = "candidate budget does not authorize dispatch"
            rejection_code = "budget_unauthorized"
        else:
            sibling_conflict = parallel_identity_conflict_reason(
                identity, admitted_identities
            )
            if sibling_conflict:
                rejection = "queued behind conflicting companion: " + sibling_conflict
                rejection_code = "sibling_conflict_queue"
            elif len(selected_rows) >= max_companions:
                rejection = "total wave capacity reached"
                rejection_code = "total_capacity_queue"
            else:
                capacity_key = _parallel_capacity_class(row)
                if (
                    capacity_key in class_capacities
                    and final_counts.get(capacity_key, 0)
                    >= int(class_capacities[capacity_key])
                ):
                    rejection = f"{capacity_key} capacity reached"
                    rejection_code = "class_capacity_queue"
                elif aggregate_budget_enforced and request:
                    available = (
                        selected_state.remaining_protected_tokens
                        + selected_state.remaining_unreserved_tokens
                        if _parallel_uses_protected_budget(row)
                        else selected_state.remaining_unreserved_tokens
                    )
                    if available <= 0:
                        rejection = "aggregate wave token allocation exhausted"
                        rejection_code = "aggregate_allocation_queue"
                    elif min(request, available) < MIN_STEP_BUDGET:
                        rejection = (
                            "aggregate token allocation is below the minimum useful step size"
                        )
                        rejection_code = "minimum_useful_allocation_queue"
                    else:
                        rejection = (
                            "candidate was not selected by the fixed-compute global admission search"
                        )
                        rejection_code = "bounded_search_queue"
                else:
                    rejection = (
                        "candidate was not selected by the fixed-compute global admission search"
                    )
                    rejection_code = "bounded_search_queue"
        outcomes[candidate_id] = ParallelAdmissionOutcome(
            "rejected", rejection, rejection_code, 0
        )

    selected_ids = list(selected_state.selected_candidate_ids)
    remaining = (
        selected_state.remaining_protected_tokens
        + selected_state.remaining_unreserved_tokens
        if aggregate_budget_enforced
        else 0
    )
    search_objective = score(selected_state)
    baseline_outcomes, baseline_remaining = _parallel_admission_outcomes_impl(
        rows,
        total_capacity=total_capacity,
        class_capacities=class_capacities,
        aggregate_budget_enforced=aggregate_budget_enforced,
        initial_remaining_token_budget=initial_remaining_token_budget,
        initial_reserved_verification_budget=initial_reserved_verification_budget,
        policy_version=8,
    )
    baseline_selected_ids = [
        str(row.get("candidate_id") or "")
        for row in companion_rows
        if baseline_outcomes[str(row.get("candidate_id") or "")].disposition
        == "selected"
    ]
    baseline_selected_id_set = set(baseline_selected_ids)
    baseline_selected_rows = [
        row
        for row in companion_rows
        if str(row.get("candidate_id") or "") in baseline_selected_id_set
    ]
    baseline_objective = (
        sum(fairness_weight(row) for row in baseline_selected_rows),
        sum(
            int(row.get("admission_priority") or 0)
            for row in baseline_selected_rows
        ),
        len(baseline_selected_rows),
        baseline_remaining,
    )
    selected_policy = "beam_search"
    if baseline_objective > search_objective:
        # A bounded search is allowed to be approximate, but never to regress
        # beneath the prior deterministic policy under its own declared
        # objective. Policy v8 therefore acts as an executable lower bound.
        outcomes = baseline_outcomes
        remaining = baseline_remaining
        selected_ids = baseline_selected_ids
        search_objective = baseline_objective
        selected_policy = "greedy_lower_bound"

    certified_upper_bound = max(
        search_objective,
        discarded_upper_bound or search_objective,
    )
    optimality_certified = certified_upper_bound <= search_objective

    metadata = {
        "version": PARALLEL_ADMISSION_SEARCH_VERSION,
        "algorithm": "deterministic_beam_search_with_greedy_lower_bound",
        "beam_width": search_beam_width,
        "candidate_count": len(companion_rows),
        "states_expanded": states_expanded,
        "states_pruned_by_bound": states_pruned_by_bound,
        "states_retained_peak": retained_peak,
        "pruned": beam_truncated,
        "optimality": "bounded_approximation" if beam_truncated else "exact",
        "objective": (
            "lexicographic(max_weight_fairness, admission_priority_sum, "
            "selected_count, remaining_tokens)"
        ),
        "objective_value": list(search_objective),
        "selected_companion_ids": selected_ids,
        "greedy_baseline_policy_version": 8,
        "greedy_baseline_objective_value": list(baseline_objective),
        "selected_policy": selected_policy,
        "dominates_or_equals_greedy_baseline": True,
        "model_self_scores_used": False,
    }
    if policy_version >= 10:
        metadata.update(
            {
                "version": PARALLEL_ADMISSION_BOUND_CERTIFICATE_VERSION,
                "algorithm": (
                    "deterministic_beam_branch_bound_certificate_with_"
                    "greedy_lower_bound"
                ),
                "optimality": (
                    "exact" if optimality_certified else "bounded_approximation"
                ),
                "optimality_certified": optimality_certified,
                "upper_bound_objective_value": list(certified_upper_bound),
            }
        )
    return outcomes, remaining, metadata


def _parallel_admission_outcomes_impl(
    rows: Sequence[Mapping[str, Any]],
    *,
    total_capacity: int,
    class_capacities: Mapping[str, int],
    aggregate_budget_enforced: bool,
    initial_remaining_token_budget: int = 0,
    initial_reserved_verification_budget: int = 0,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
    search_metadata_out: Dict[str, Any] | None = None,
) -> tuple[Dict[str, ParallelAdmissionOutcome], int]:
    """Apply the pure admission transition to canonical descriptor rows.

    The returned mapping contains a typed disposition, explanation, machine
    outcome code, and token grant for every descriptor. Generation and
    persisted-trace replay both call this function, so there is only one
    executable definition of the policy.
    """

    if policy_version not in SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS:
        raise ValueError(f"unsupported parallel admission policy {policy_version}")
    if policy_version >= 9:
        outcomes, remaining, metadata = _parallel_search_outcomes(
            rows,
            total_capacity=total_capacity,
            class_capacities=class_capacities,
            aggregate_budget_enforced=aggregate_budget_enforced,
            initial_remaining_token_budget=initial_remaining_token_budget,
            initial_reserved_verification_budget=(
                initial_reserved_verification_budget
            ),
            policy_version=policy_version,
        )
        if search_metadata_out is not None:
            search_metadata_out.clear()
            search_metadata_out.update(metadata)
        return outcomes, remaining
    if search_metadata_out is not None:
        search_metadata_out.clear()

    remaining_total_tokens = (
        int(initial_remaining_token_budget) if aggregate_budget_enforced else 0
    )
    remaining_protected_tokens = (
        min(
            remaining_total_tokens,
            int(initial_reserved_verification_budget),
        )
        if aggregate_budget_enforced
        else 0
    )
    remaining_unreserved_tokens = max(
        0, remaining_total_tokens - remaining_protected_tokens
    )

    def capacity_class(row: Mapping[str, Any]) -> str:
        action_class = str(row.get("action_class") or "")
        return (
            "research_or_adversarial"
            if action_class in {"research", "adversarial"}
            else action_class
        )

    def uses_protected_budget(row: Mapping[str, Any]) -> bool:
        return str(row.get("action_class") or "") in {
            "verification",
            "integration",
        } or str(row.get("mode") or "") in {
            "formalize",
            "validate_counterexample",
            "write",
            "review_writing",
        }

    def reserve_tokens(row: Mapping[str, Any], grant: int) -> None:
        nonlocal remaining_total_tokens
        nonlocal remaining_protected_tokens
        nonlocal remaining_unreserved_tokens
        if not aggregate_budget_enforced or grant <= 0:
            return
        remaining_total_tokens = max(0, remaining_total_tokens - grant)
        if uses_protected_budget(row):
            protected_spend = min(grant, remaining_protected_tokens)
            remaining_protected_tokens -= protected_spend
            remaining_unreserved_tokens = max(
                0, remaining_unreserved_tokens - (grant - protected_spend)
            )
        else:
            remaining_unreserved_tokens = max(0, remaining_unreserved_tokens - grant)

    expected: Dict[str, ParallelAdmissionOutcome] = {}
    primary = rows[0]
    primary_request = int(primary.get("requested_tokens") or 0)
    expected[str(primary["candidate_id"])] = ParallelAdmissionOutcome(
        "fixed_primary",
        "the primary action was selected by the main scheduler",
        "fixed_primary",
        primary_request,
    )
    reserve_tokens(primary, primary_request)
    admitted_rows: list[Mapping[str, Any]] = [primary]
    class_counts = {key: 0 for key in class_capacities}
    primary_capacity_class = capacity_class(primary)
    if primary_capacity_class in class_counts:
        class_counts[primary_capacity_class] += 1
    pending_unprotected_token_demand = sum(
        int(row.get("requested_tokens") or 0)
        for row in rows[1:]
        if not uses_protected_budget(row)
    )
    selected_rows: list[Mapping[str, Any]] = []

    def projected_unprotected_demand(
        current_row: Mapping[str, Any],
        future_rows: Sequence[Mapping[str, Any]],
    ) -> int:
        """Reserve only demand a future structural admission can consume.

        This is the deterministic greedy continuation conditioned on admitting
        ``current_row``. It prevents unauthorized, conflicting, or
        capacity-excess candidates from withholding allocation from an earlier
        protected action.
        """

        shadow_admitted = [primary, *selected_rows, current_row]
        shadow_class_counts = dict(class_counts)
        current_capacity_key = capacity_class(current_row)
        if current_capacity_key in shadow_class_counts:
            shadow_class_counts[current_capacity_key] += 1
        projected = 0
        for future in future_rows:
            if len(shadow_admitted) >= total_capacity:
                break
            if future.get("budget_allowed") is not True:
                continue
            future_identity = tuple(future["semantic_identity"])
            if parallel_identity_conflict_reason(
                future_identity,
                [tuple(item["semantic_identity"]) for item in shadow_admitted],
            ):
                continue
            future_capacity_key = capacity_class(future)
            if (
                future_capacity_key in class_capacities
                and shadow_class_counts[future_capacity_key]
                >= class_capacities[future_capacity_key]
            ):
                continue
            shadow_admitted.append(future)
            if future_capacity_key in shadow_class_counts:
                shadow_class_counts[future_capacity_key] += 1
            if not uses_protected_budget(future):
                projected += int(future.get("requested_tokens") or 0)
        return projected

    companion_rows = rows[1:]
    for position, row in enumerate(companion_rows):
        original_request = int(row.get("requested_tokens") or 0)
        if not uses_protected_budget(row):
            pending_unprotected_token_demand = max(
                0, pending_unprotected_token_demand - original_request
            )
        identity = tuple(row["semantic_identity"])
        if policy_version >= 6:
            # A conflict with the fixed primary is an admissibility failure for
            # this wave. A conflict only with an already selected companion is
            # queueing: it is safe to run in a later wave and must accrue
            # bounded-deferral priority so canonical order cannot starve it.
            rejection, primary_conflict_is_serializable = parallel_identity_conflict(
                identity,
                [tuple(primary["semantic_identity"])],
            )
            rejection_code = (
                PRIMARY_SERIALIZATION_OUTCOME_CODE
                if rejection
                and primary_conflict_is_serializable
                and policy_version >= 8
                else "primary_or_structural_conflict"
                if rejection
                else ""
            )
            if not rejection and row.get("budget_allowed") is not True:
                rejection = "candidate budget does not authorize dispatch"
                rejection_code = "budget_unauthorized"
            if not rejection:
                companion_conflict = parallel_identity_conflict_reason(
                    identity,
                    [
                        tuple(item["semantic_identity"])
                        for item in selected_rows
                    ],
                )
                if companion_conflict:
                    rejection = (
                        "queued behind conflicting companion: "
                        + companion_conflict
                    )
                    rejection_code = "sibling_conflict_queue"
        else:
            rejection = parallel_identity_conflict_reason(
                identity,
                [tuple(item["semantic_identity"]) for item in admitted_rows],
            )
            rejection_code = (
                "primary_or_structural_conflict" if rejection else ""
            )
        capacity_key = capacity_class(row)
        if not rejection and row.get("budget_allowed") is not True:
            rejection = "candidate budget does not authorize dispatch"
            rejection_code = "budget_unauthorized"
        if not rejection and len(admitted_rows) >= total_capacity:
            rejection = "total wave capacity reached"
            rejection_code = "total_capacity_queue"
        if (
            not rejection
            and capacity_key in class_capacities
            and class_counts[capacity_key] >= class_capacities[capacity_key]
        ):
            rejection = f"{capacity_key} capacity reached"
            rejection_code = "class_capacity_queue"
        grant = original_request
        if not rejection and aggregate_budget_enforced and original_request:
            reserved_future_demand = (
                projected_unprotected_demand(
                    row,
                    companion_rows[position + 1 :],
                )
                if policy_version >= 7 and uses_protected_budget(row)
                else pending_unprotected_token_demand
            )
            available = (
                max(
                    0,
                    remaining_total_tokens
                    - min(
                        remaining_unreserved_tokens,
                        reserved_future_demand,
                    ),
                )
                if uses_protected_budget(row)
                else remaining_unreserved_tokens
            )
            if available <= 0:
                rejection = "aggregate wave token allocation exhausted"
                rejection_code = "aggregate_allocation_queue"
            elif min(original_request, available) < MIN_STEP_BUDGET:
                rejection = (
                    "aggregate token allocation is below the minimum useful step size"
                )
                rejection_code = "minimum_useful_allocation_queue"
            else:
                grant = min(original_request, available)
        candidate_id = str(row["candidate_id"])
        if rejection:
            expected[candidate_id] = ParallelAdmissionOutcome(
                "rejected", rejection, rejection_code, 0
            )
            continue
        fairness_due = (
            int(row.get("deferral_limit") or 0) > 0
            and int(row.get("consecutive_deferrals") or 0)
            >= int(row.get("deferral_limit") or 0)
        )
        if grant != original_request:
            reason = (
                "admitted with token grant reduced to the remaining aggregate allocation"
            )
            outcome_code = "selected_reduced_allocation"
        elif fairness_due:
            if policy_version == 3:
                reason = (
                    "admitted by bounded-deferral fairness within its priority class"
                )
                outcome_code = "selected_fairness_within_class"
            else:
                reason = (
                    "admitted by bounded-deferral fairness across admission classes"
                )
                outcome_code = "selected_fairness_across_classes"
        else:
            reason = (
                "admitted by explicit priority with canonical semantic-identity tie-break"
            )
            outcome_code = "selected_priority"
        expected[candidate_id] = ParallelAdmissionOutcome(
            "selected", reason, outcome_code, grant
        )
        admitted_rows.append(row)
        selected_rows.append(row)
        reserve_tokens(row, grant)
        if capacity_key in class_counts:
            class_counts[capacity_key] += 1

    if aggregate_budget_enforced and remaining_total_tokens > 0:
        for row in selected_rows:
            if not uses_protected_budget(row) or remaining_total_tokens <= 0:
                continue
            candidate_id = str(row["candidate_id"])
            outcome = expected[candidate_id]
            top_up = min(
                max(
                    0,
                    int(row.get("requested_tokens") or 0)
                    - outcome.admitted_tokens,
                ),
                remaining_total_tokens,
            )
            if top_up <= 0:
                continue
            reserve_tokens(row, top_up)
            expected[candidate_id] = ParallelAdmissionOutcome(
                outcome.disposition,
                outcome.reason,
                outcome.outcome_code,
                outcome.admitted_tokens + top_up,
            )

    return expected, remaining_total_tokens


def parallel_admission_outcomes(
    rows: Sequence[Mapping[str, Any]],
    *,
    total_capacity: int,
    class_capacities: Mapping[str, int],
    aggregate_budget_enforced: bool,
    initial_remaining_token_budget: int = 0,
    initial_reserved_verification_budget: int = 0,
    policy_version: int = PARALLEL_WAVE_ADMISSION_POLICY_VERSION,
    search_metadata_out: Dict[str, Any] | None = None,
) -> tuple[Dict[str, ParallelAdmissionOutcome], int]:
    """Apply exactly one versioned admission transition.

    Policy v9 internally evaluates the immutable v8 transition as a certified
    lower bound, without exposing that implementation detail as a second live
    or replay entry point.
    """

    return _parallel_admission_outcomes_impl(
        rows,
        total_capacity=total_capacity,
        class_capacities=class_capacities,
        aggregate_budget_enforced=aggregate_budget_enforced,
        initial_remaining_token_budget=initial_remaining_token_budget,
        initial_reserved_verification_budget=(
            initial_reserved_verification_budget
        ),
        policy_version=policy_version,
        search_metadata_out=search_metadata_out,
    )


def parallel_policy_semantic_sha256(policy_version: int) -> str:
    """Hash canonical conformance scenarios for one immutable policy epoch."""

    if policy_version not in SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS:
        raise ValueError(f"unsupported parallel admission policy {policy_version}")

    def row(
        candidate_id: str,
        *,
        action_class: str,
        mode: str,
        target_id: str,
        route_id: str = "",
        budget_allowed: bool = True,
        requested_tokens: int = 0,
        deferrals: int = 0,
        identity_nonce: str = "0" * 64,
    ) -> Dict[str, Any]:
        identity = (
            action_class,
            mode,
            target_id,
            route_id,
            "semantic_conformance",
            "",
            "{}",
        )
        if policy_version >= 7:
            identity = (*identity, identity_nonce)
        return {
            "candidate_id": candidate_id,
            "admission_priority": parallel_admission_priority_for(
                action_class, "semantic_conformance"
            ),
            "action_class": action_class,
            "mode": mode,
            "target_id": target_id,
            "route_id": route_id,
            "search_intent": "semantic_conformance",
            "semantic_identity": list(identity),
            "consecutive_deferrals": deferrals,
            "deferral_limit": PARALLEL_WAVE_DEFERRAL_LIMIT,
            "budget_allowed": budget_allowed,
            "requested_tokens": requested_tokens,
            "comparison_action_sha256": identity_nonce,
        }

    def primary(*, requested_tokens: int = 0) -> Dict[str, Any]:
        result = row(
            "parallel:primary",
            action_class="advisory",
            mode="triage_routes",
            target_id="primary",
            requested_tokens=requested_tokens,
        )
        result.update(
            admission_priority=1_000_000,
            consecutive_deferrals=0,
            deferral_limit=0,
        )
        return result

    def serialization_primary() -> Dict[str, Any]:
        result = row(
            "parallel:primary",
            action_class="research",
            mode="reduce",
            target_id="primary-target",
            route_id="shared-route",
        )
        result.update(
            admission_priority=1_000_000,
            consecutive_deferrals=0,
            deferral_limit=0,
        )
        return result

    future_equivalence_specifications = (
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
    suffix_neighborhood_specifications = (
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
    canonical_tie_specifications = (
        (
            "parallel:000000000000000000096fa5",
            "integration",
            "t1",
            "r0",
        ),
        (
            "parallel:00000000000000000002293f",
            "integration",
            "t3",
            "r3",
        ),
        (
            "parallel:0000000000000000000103c9",
            "adversarial",
            "t2",
            "r1",
        ),
        (
            "parallel:00000000000000000008481e",
            "research",
            "t0",
            "r4",
        ),
        (
            "parallel:000000000000000000050279",
            "research",
            "t4",
            "r4",
        ),
    )
    dominance_specifications = (
        ("parallel:0000000000000000000005fd", "integration", "t1", "r6", 5),
        ("parallel:0000000000000000000005fb", "integration", "t5", "r3", 5),
        ("parallel:0000000000000000000005f8", "adversarial", "t0", "r0", 5),
        ("parallel:0000000000000000000005f3", "research", "t2", "r0", 5),
        ("parallel:0000000000000000000005ff", "research", "t6", "r7", 5),
        ("parallel:0000000000000000000005f9", "integration", "t3", "r6", 3),
        ("parallel:0000000000000000000005f2", "literature", "t1", "r3", 3),
        ("parallel:000000000000000000000600", "research", "t0", "r0", 3),
        ("parallel:0000000000000000000005f6", "research", "t5", "r7", 3),
        ("parallel:0000000000000000000005f1", "research", "t6", "r6", 3),
        ("parallel:0000000000000000000005fe", "integration", "t4", "r5", 0),
        ("parallel:0000000000000000000005f4", "integration", "t6", "r6", 0),
        ("parallel:0000000000000000000005fc", "integration", "t7", "r4", 0),
        ("parallel:0000000000000000000005f7", "verification", "t4", "r1", 0),
        ("parallel:0000000000000000000005f5", "literature", "t0", "r3", 0),
        ("parallel:0000000000000000000005fa", "research", "t5", "r2", 0),
    )

    def anytime_conformance_row(index: int) -> Dict[str, Any]:
        digest = hashlib.sha256(f"39:{index}".encode("ascii")).digest()
        action_classes = (
            "research",
            "adversarial",
            "verification",
            "integration",
            "literature",
        )
        modes = {
            "research": "reduce",
            "adversarial": "refute",
            "verification": "prove",
            "integration": "integrate",
            "literature": "retrieve",
        }
        action_class = action_classes[digest[0] % len(action_classes)]
        identity_nonce = hashlib.sha256(
            f"id:39:{index}".encode("ascii")
        ).hexdigest()
        result = row(
            f"parallel:{identity_nonce[:24]}",
            action_class=action_class,
            mode=modes[action_class],
            target_id=f"t{digest[1] % 10}",
            route_id=f"r{digest[2] % 10}",
            deferrals=(0, 0, 3, 5)[digest[3] % 4],
            identity_nonce=identity_nonce,
        )
        result["admission_priority"] = (digest[4] % 11) * 100
        return result

    scenarios = ([
        (
            "certificate_triggered_anytime_completion",
            [
                primary(),
                *sorted(
                    [anytime_conformance_row(index) for index in range(129)],
                    key=lambda candidate: parallel_admission_order_key(
                        candidate, policy_version=policy_version
                    ),
                ),
            ],
            False,
            0,
            0,
            7,
            {
                "research_or_adversarial": 2,
                "verification": 4,
                "integration": 4,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 22 else []) + ([
        (
            "exact_partial_state_dominance",
            [
                primary(),
                *sorted(
                    [
                        row(
                            candidate_id,
                            action_class=action_class,
                            mode={
                                "research": "reduce",
                                "adversarial": "refute",
                                "verification": "prove",
                                "integration": "integrate",
                                "literature": "retrieve",
                            }[action_class],
                            target_id=target_id,
                            route_id=route_id,
                            deferrals=deferrals,
                            identity_nonce=f"{index + 1:064x}",
                        )
                        for index, (
                            candidate_id,
                            action_class,
                            target_id,
                            route_id,
                            deferrals,
                        ) in enumerate(dominance_specifications)
                    ],
                    key=lambda candidate: parallel_admission_order_key(
                        candidate, policy_version=policy_version
                    ),
                ),
            ],
            False,
            0,
            0,
            7,
            {
                "research_or_adversarial": 5,
                "verification": 5,
                "integration": 5,
                "literature": 2,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 21 else []) + ([
        (
            "canonical_equal_objective_tie",
            [
                primary(),
                *sorted(
                    [
                        row(
                            candidate_id,
                            action_class=action_class,
                            mode={
                                "research": "reduce",
                                "adversarial": "refute",
                                "integration": "integrate",
                            }[action_class],
                            target_id=target_id,
                            route_id=route_id,
                            identity_nonce=f"{index + 1:064x}",
                        )
                        for index, (
                            candidate_id,
                            action_class,
                            target_id,
                            route_id,
                        ) in enumerate(canonical_tie_specifications)
                    ],
                    key=lambda candidate: parallel_admission_order_key(
                        candidate, policy_version=policy_version
                    ),
                ),
            ],
            False,
            0,
            0,
            7,
            {
                "research_or_adversarial": 5,
                "verification": 5,
                "integration": 5,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 19 else []) + ([
        (
            "exact_suffix_conflict_neighborhood_quotient",
            [
                primary(),
                *sorted(
                    [
                        row(
                            f"suffix-neighborhood-{index:02d}",
                            action_class=action_class,
                            mode={
                                "research": "reduce",
                                "adversarial": "refute",
                                "verification": "prove",
                                "integration": "integrate",
                                "literature": "retrieve",
                            }[action_class],
                            target_id=target_id,
                            route_id=route_id,
                            deferrals=deferrals,
                            identity_nonce=f"{index + 1:064x}",
                        )
                        for index, (
                            action_class,
                            target_id,
                            route_id,
                            deferrals,
                        ) in enumerate(suffix_neighborhood_specifications)
                    ],
                    key=lambda candidate: parallel_admission_order_key(
                        candidate, policy_version=policy_version
                    ),
                ),
            ],
            False,
            0,
            0,
            7,
            {
                "research_or_adversarial": 5,
                "verification": 5,
                "integration": 5,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 18 else []) + ([
        (
            "future_conflict_equivalence_quotient",
            [
                primary(),
                *sorted(
                    [
                        row(
                            f"future-equivalence-{index}",
                            action_class=action_class,
                            mode={
                                "research": "reduce",
                                "adversarial": "refute",
                                "verification": "prove",
                                "integration": "integrate",
                            }[action_class],
                            target_id=target_id,
                            route_id=route_id,
                            deferrals=deferrals,
                            identity_nonce=f"{index + 1:064x}",
                        )
                        for index in range(48)
                        for action_class, target_id, route_id, deferrals in (
                            future_equivalence_specifications[
                                index % len(future_equivalence_specifications)
                            ],
                        )
                    ],
                    key=lambda candidate: parallel_admission_order_key(
                        candidate, policy_version=policy_version
                    ),
                ),
            ],
            False,
            0,
            0,
            6,
            {
                "research_or_adversarial": 3,
                "verification": 3,
                "integration": 3,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 17 else []) + ([
        (
            "certification_filtered_clique_upper_bound",
            [
                primary(),
                *[
                    row(
                        f"certification-clique-{index}",
                        action_class=action_class,
                        mode={
                            "research": "reduce",
                            "adversarial": "refute",
                            "verification": "prove",
                            "integration": "integrate",
                        }[action_class],
                        target_id=target_id,
                        route_id=route_id,
                        deferrals=deferrals,
                    )
                    for index, (
                        action_class,
                        target_id,
                        route_id,
                        deferrals,
                    ) in enumerate(
                        (
                            ("integration", "t3", "r2", 5),
                            ("adversarial", "t2", "r1", 5),
                            ("research", "t0", "r2", 5),
                            ("verification", "t1", "r1", 3),
                            ("verification", "t1", "r1", 3),
                            ("verification", "t1", "r2", 3),
                            ("adversarial", "t0", "r2", 3),
                            ("research", "t0", "r1", 3),
                            ("integration", "t3", "r1", 0),
                            ("integration", "t3", "r1", 0),
                            ("verification", "t3", "r3", 0),
                            ("adversarial", "t2", "r1", 0),
                        )
                    )
                ],
            ],
            False,
            0,
            0,
            6,
            {
                "research_or_adversarial": 3,
                "verification": 3,
                "integration": 3,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 15 else []) + ([
        (
            "same_route_clique_upper_bound",
            [
                primary(),
                *[
                    row(
                        f"route-clique-{index}",
                        action_class="research",
                        mode="reduce",
                        target_id=f"route-clique-target-{index}",
                        route_id="shared-clique-route",
                        deferrals=PARALLEL_WAVE_DEFERRAL_LIMIT,
                    )
                    for index in range(100)
                ],
            ],
            False,
            0,
            0,
            7,
            {
                "research_or_adversarial": 6,
                "verification": 5,
                "integration": 5,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 14 else []) + ([
        (
            "minimum_token_resource_upper_bound",
            [
                primary(),
                *[
                    row(
                        f"resource-bound-{index}",
                        action_class="research",
                        mode="reduce",
                        target_id=f"resource-bound-{index}",
                        requested_tokens=20_000,
                    )
                    for index in range(40)
                ],
            ],
            True,
            20_000,
            0,
            7,
            {
                "research_or_adversarial": 6,
                "verification": 5,
                "integration": 5,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 13 else []) + ([
        (
            "class_conflict_upper_bound",
            [
                primary(),
                *[
                    row(
                        f"integration-bound-{index}",
                        action_class="integration",
                        mode="integrate",
                        target_id=f"integration-bound-{index}",
                        deferrals=PARALLEL_WAVE_DEFERRAL_LIMIT,
                    )
                    for index in range(10)
                ],
                *[
                    row(
                        f"verification-bound-{index}",
                        action_class="verification",
                        mode="prove",
                        target_id=f"verification-bound-{index}",
                        deferrals=PARALLEL_WAVE_DEFERRAL_LIMIT,
                    )
                    for index in range(10)
                ],
                *[
                    row(
                        f"literature-bound-{index}",
                        action_class="literature",
                        mode="retrieve",
                        target_id=f"literature-bound-{index}",
                        deferrals=PARALLEL_WAVE_DEFERRAL_LIMIT,
                    )
                    for index in range(10)
                ],
                *[
                    row(
                        f"research-bound-{index}",
                        action_class="research",
                        mode="reduce",
                        target_id=f"research-bound-{index}",
                        deferrals=PARALLEL_WAVE_DEFERRAL_LIMIT,
                    )
                    for index in range(10)
                ],
            ],
            False,
            0,
            0,
            5,
            {
                "research_or_adversarial": 1,
                "verification": 2,
                "integration": 2,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 12 else []) + ([
        (
            "minimum_grant_joint_admission",
            [
                primary(),
                row(
                    "research-a",
                    action_class="research",
                    mode="reduce",
                    target_id="allocation-a",
                    requested_tokens=20_000,
                ),
                row(
                    "research-b",
                    action_class="research",
                    mode="reduce",
                    target_id="allocation-b",
                    requested_tokens=20_000,
                ),
            ],
            True,
            20_000,
            0,
            3,
            {
                "research_or_adversarial": 2,
                "verification": 1,
                "integration": 1,
                "literature": 1,
                "advisory": 1,
            },
        ),
        (
            "reserved_and_shared_max_min_top_up",
            [
                primary(requested_tokens=60_000),
                row(
                    "verification-top-up",
                    action_class="verification",
                    mode="prove",
                    target_id="verification-top-up",
                    requested_tokens=60_000,
                ),
                row(
                    "research-top-up",
                    action_class="research",
                    mode="reduce",
                    target_id="research-top-up",
                    requested_tokens=60_000,
                ),
            ],
            True,
            150_000,
            50_000,
            3,
            {
                "research_or_adversarial": 2,
                "verification": 1,
                "integration": 1,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 11 else []) + ([
        (
            "global_search_beats_greedy_prefix",
            [
                primary(),
                row(
                    "integration",
                    action_class="integration",
                    mode="integrate",
                    target_id="integration-target",
                    route_id="integration-route",
                ),
                row(
                    "verification-a",
                    action_class="verification",
                    mode="prove",
                    target_id="verification-a",
                    route_id="verification-route-a",
                ),
                row(
                    "verification-b",
                    action_class="verification",
                    mode="prove",
                    target_id="verification-b",
                    route_id="verification-route-b",
                ),
            ],
            False,
            0,
            0,
            3,
            {
                "research_or_adversarial": 2,
                "verification": 2,
                "integration": 2,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 9 else []) + ([
        (
            "primary_serialization_conflict",
            [
                serialization_primary(),
                row(
                    "serialized-research",
                    action_class="research",
                    mode="reduce",
                    target_id="other-target",
                    route_id="shared-route",
                ),
            ],
            False,
            0,
            0,
            3,
            {
                "research_or_adversarial": 2,
                "verification": 2,
                "integration": 2,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ] if policy_version >= 8 else []) + [
        (
            "sibling_conflict",
            [
                primary(),
                row(
                    "verification",
                    action_class="verification",
                    mode="prove",
                    target_id="shared",
                    route_id="verification-route",
                ),
                row(
                    "research",
                    action_class="research",
                    mode="reduce",
                    target_id="shared",
                    route_id="research-route",
                ),
            ],
            False,
            0,
            0,
            4,
            {
                "research_or_adversarial": 2,
                "verification": 2,
                "integration": 2,
                "literature": 1,
                "advisory": 1,
            },
        ),
        (
            "unauthorized_conflict",
            [
                primary(),
                row(
                    "verification",
                    action_class="verification",
                    mode="prove",
                    target_id="shared",
                    route_id="verification-route",
                ),
                row(
                    "research",
                    action_class="research",
                    mode="reduce",
                    target_id="shared",
                    route_id="research-route",
                    budget_allowed=False,
                    requested_tokens=20_000,
                ),
            ],
            False,
            0,
            0,
            4,
            {
                "research_or_adversarial": 2,
                "verification": 2,
                "integration": 2,
                "literature": 1,
                "advisory": 1,
            },
        ),
        (
            "feasible_demand_projection",
            [
                primary(),
                row(
                    "verification",
                    action_class="verification",
                    mode="prove",
                    target_id="shared",
                    route_id="verification-route",
                    requested_tokens=20_000,
                ),
                row(
                    "research",
                    action_class="research",
                    mode="reduce",
                    target_id="shared",
                    route_id="research-route",
                    requested_tokens=20_000,
                ),
            ],
            True,
            20_000,
            0,
            4,
            {
                "research_or_adversarial": 2,
                "verification": 2,
                "integration": 2,
                "literature": 1,
                "advisory": 1,
            },
        ),
        (
            "cross_class_fairness_and_capacity",
            [
                primary(),
                row(
                    "aged-research",
                    action_class="research",
                    mode="reduce",
                    target_id="research-a",
                    deferrals=PARALLEL_WAVE_DEFERRAL_LIMIT,
                ),
                row(
                    "integration",
                    action_class="integration",
                    mode="integrate",
                    target_id="integration-a",
                ),
                row(
                    "fresh-research",
                    action_class="research",
                    mode="reduce",
                    target_id="research-b",
                ),
            ],
            False,
            0,
            0,
            2,
            {
                "research_or_adversarial": 1,
                "verification": 1,
                "integration": 1,
                "literature": 1,
                "advisory": 1,
            },
        ),
    ]
    observed: list[Dict[str, Any]] = []
    for (
        name,
        rows,
        aggregate_budget_enforced,
        initial_total,
        initial_reserve,
        total_capacity,
        class_capacities,
    ) in scenarios:
        search_metadata: Dict[str, Any] = {}
        outcomes, remaining = parallel_admission_outcomes(
            rows,
            total_capacity=total_capacity,
            class_capacities=class_capacities,
            aggregate_budget_enforced=aggregate_budget_enforced,
            initial_remaining_token_budget=initial_total,
            initial_reserved_verification_budget=initial_reserve,
            policy_version=policy_version,
            search_metadata_out=search_metadata,
        )
        observed.append(
            {
                "scenario": name,
                "outcomes": {
                    candidate_id: dict(outcome._asdict())
                    for candidate_id, outcome in sorted(outcomes.items())
                },
                "remaining_tokens": remaining,
                **(
                    {"admission_search": search_metadata}
                    if policy_version >= 9
                    else {}
                ),
            }
        )
    return _canonical_sha256(observed)


PARALLEL_POLICY_SEMANTIC_SHA256: Mapping[int, str] = MappingProxyType(
    {
        3: "03fa3467597c4873e9b348e0b1f992777a1162eba2df31179261145c4328748e",
        4: "4216f3ff65e6889399db1bde1f815b7f690c5c0861d739f768037e1a1bd67c3d",
        5: "4216f3ff65e6889399db1bde1f815b7f690c5c0861d739f768037e1a1bd67c3d",
        6: "75c1395bb219e97eff7bdd9e36722f2e7659f440bcdc4e49429310f56f3c9151",
        7: "7c953705ce076d0a6da12ed7b55a02dccd079a8019b4b66f930551d2808c5b03",
        8: "07a8f75d1f9f8d11393cb7a81368636393ba85f0d1b026e36d456d74663d71a9",
        9: "bc56f012e1fa9f52b10b4851ed36019a2e1db1f980204222c5a1f6865db0e552",
        10: "a8abe0ffc9553a833f04ec362acf2c609110a128022da68a4499caa02ac7beed",
        11: "1e1ecb973663f2d28753b6a133923486f3c7f8c588cfa068bf1c77887ec899ce",
        12: "402083ab775ae7434c385d3dafbe1b3d23fc4aab36bb91f0f2f17f8608350130",
        13: "c512a22dca8c5814f13ee3b181eeda4b52c6d5d09080add4743aa171fd9b31be",
        14: "261e8f3a1b67d21181a5afa81fd48834824335963bd65bf786d02f2448b8cae9",
        15: "81a3a323939bb95f82b7041fa4597c0e5fcdda26eb2ea739f3250fbf20fb5fb4",
        16: "5d3210249087b7afc29dce31a2fcaa1b2947dc00894157ed05e23245475e247d",
        17: "a2e2f5a085511f87a50844e33259bf04e3e03676cc1c77a5f33ab1c076091c6c",
        18: "b72fd13fa727000aacae00fe3aeb3b697b880ec2f8e9c7cf12707443754ca05d",
        19: "77c241e35b7fd94983b49bb09cd65e000e7e79dd58e6ec3a3f26793a51c2b10a",
        20: "b5d5045fc6da38358083efd964fdfb2509811f916aec3ea626d8594838bd10de",
        21: "a8e884a1196f4b1d73f2e0deace8ab77c4aa4c52f0c24fa97b6b9e6c8066d16c",
        22: "3c5abf56c3c03f619def9b03095a4c46ac30523e58371123a823b9f88e352254",
        23: "0a0739bfaa47dcca2447f140b68caf9bcb3566a557a82d16acf764f6c94157fe",
        24: "28f4ba18ba889ff11b4cf78124bfaec518126a85192ceaa5ac946acd8136204b",
        25: "d3a4fbbc592fbaa0acd4cc7fb793bc953ec274083f09dc860af52c8d41be2d03",
    }
)


def parallel_policy_semantic_errors() -> list[str]:
    """Detect a changed or missing published policy conformance vector."""

    errors: list[str] = []
    supported = set(SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS)
    committed = set(PARALLEL_POLICY_SEMANTIC_SHA256)
    for version in sorted(supported - committed):
        errors.append(
            f"parallel policy v{version} has no semantic conformance commitment"
        )
    for version in sorted(committed - supported):
        errors.append(
            f"parallel semantic commitment names unsupported policy v{version}"
        )
    for version in sorted(supported & committed):
        observed = parallel_policy_semantic_sha256(version)
        if observed != PARALLEL_POLICY_SEMANTIC_SHA256[version]:
            errors.append(
                f"parallel policy v{version} changed without a new version "
                f"(observed {observed})"
            )
    return errors


_PARALLEL_POLICY_SEMANTIC_ERRORS = tuple(parallel_policy_semantic_errors())
if _PARALLEL_POLICY_SEMANTIC_ERRORS:
    raise RuntimeError(
        "invalid parallel policy semantics: "
        + "; ".join(_PARALLEL_POLICY_SEMANTIC_ERRORS)
    )


def _parallel_wave_replay_errors(trace: Mapping[str, Any]) -> list[str]:
    """Replay the versioned admission policy from committed descriptors."""

    rows = trace["candidates"]
    aggregate_budget_enforced = bool(trace["aggregate_budget_enforced"])
    expected_search: Dict[str, Any] = {}
    expected, remaining_total_tokens = parallel_admission_outcomes(
        rows,
        total_capacity=int(trace["total_wave_capacity"]),
        class_capacities={
            str(key): int(value)
            for key, value in trace["class_capacities"].items()
        },
        aggregate_budget_enforced=aggregate_budget_enforced,
        initial_remaining_token_budget=(
            int(trace["initial_remaining_token_budget"])
            if aggregate_budget_enforced
            else 0
        ),
        initial_reserved_verification_budget=(
            int(trace["initial_reserved_verification_budget"])
            if aggregate_budget_enforced
            else 0
        ),
        policy_version=int(trace["policy_version"]),
        search_metadata_out=expected_search,
    )
    errors: list[str] = []
    if int(trace["policy_version"]) >= 9 and trace.get(
        "admission_search"
    ) != expected_search:
        errors.append(
            "parallel wave admission-search evidence is inconsistent with replay"
        )
    for row in rows:
        candidate_id = str(row["candidate_id"])
        expected_outcome = expected[candidate_id]
        expected_disposition = expected_outcome.disposition
        expected_reason = expected_outcome.reason
        expected_grant = expected_outcome.admitted_tokens
        if str(row.get("disposition") or "") != expected_disposition:
            errors.append(
                f"parallel wave disposition is not policy-optimal for {candidate_id}"
            )
        if str(row.get("reason") or "") != expected_reason:
            errors.append(f"parallel wave reason is inconsistent for {candidate_id}")
        if int(trace.get("policy_version") or 0) >= 6 and row.get(
            "outcome_code"
        ) != expected_outcome.outcome_code:
            errors.append(
                f"parallel wave outcome code is inconsistent for {candidate_id}"
            )
        if int(row.get("admitted_tokens") or 0) != expected_grant:
            errors.append(
                f"parallel wave token grant is not policy-optimal for {candidate_id}"
            )
    if aggregate_budget_enforced and int(
        trace.get("remaining_uncommitted_token_budget") or 0
    ) != remaining_total_tokens:
        errors.append(
            "parallel wave remaining token allocation is inconsistent with replay"
        )
    return errors


def parallel_wave_admission_errors(trace: Mapping[str, Any]) -> list[str]:
    """Validate a complete, independently auditable wave-admission record."""

    if not isinstance(trace, Mapping):
        return ["parallel wave admission trace must be an object"]
    errors: list[str] = candidate_generator_trace_errors(trace)

    def safe_int(value: Any, default: int = 0) -> int:
        if isinstance(value, bool):
            return default
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return default

    raw_policy_version = trace.get("policy_version")
    policy_version_valid = (
        type(raw_policy_version) is int
        and raw_policy_version in SUPPORTED_PARALLEL_WAVE_POLICY_VERSIONS
    )
    if not policy_version_valid:
        errors.append("parallel wave policy version is not supported")
        policy_version = PARALLEL_WAVE_ADMISSION_POLICY_VERSION
    else:
        policy_version = raw_policy_version
    binding_fields_valid = True
    generator_manifest_binding_valid = True
    admission_search_valid = True
    if policy_version >= 4:
        if type(trace.get("state_revision")) is not int or int(
            trace.get("state_revision") or 0
        ) < 0:
            errors.append("parallel wave state revision must be a nonnegative integer")
            binding_fields_valid = False
        for field in ("proof_state_hash", "run_provenance_hash"):
            digest = trace.get(field)
            if not isinstance(digest, str) or digest and (
                len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                errors.append(
                    f"parallel wave {field} must be empty or a lowercase SHA-256 digest"
                )
                binding_fields_valid = False
    generator_manifest_digest = str(
        trace.get("candidate_generator_manifest_sha256") or ""
    )
    if policy_version >= 5:
        if (
            trace.get("candidate_generator_scope_id") != "parallel_wave"
            or trace.get("candidate_generator_manifest_version") != 2
            or type(trace.get("candidate_generator_graph_version")) is not int
            or int(trace.get("candidate_generator_graph_version") or 0) < 3
        ):
            errors.append(
                "parallel wave requires current candidate-generator evaluation provenance"
            )
            generator_manifest_binding_valid = False
    admission_search = trace.get("admission_search")
    if policy_version >= 9:
        if not isinstance(admission_search, Mapping):
            errors.append("parallel wave admission-search evidence must be an object")
            admission_search_valid = False
    elif admission_search is not None:
        errors.append(
            "parallel wave admission-search evidence is unavailable before policy v9"
        )
        admission_search_valid = False
        if len(generator_manifest_digest) != 64 or any(
            character not in "0123456789abcdef"
            for character in generator_manifest_digest
        ):
            errors.append(
                "parallel wave candidate-generator manifest commitment is invalid"
            )
            generator_manifest_binding_valid = False
    wave_id = str(trace.get("wave_id") or "")
    if len(wave_id) != 64 or any(
        character not in "0123456789abcdef" for character in wave_id
    ):
        errors.append("parallel wave identifier is not a SHA-256 digest")
    if trace.get("candidate_set_complete") is not True:
        errors.append("parallel wave candidate set is not marked complete")
    if not str(trace.get("candidate_set_scope") or "").strip():
        errors.append("parallel wave candidate-set scope is missing")
    rows = trace.get("candidates")
    if not isinstance(rows, list) or not rows or any(
        not isinstance(row, Mapping) for row in rows
    ):
        return errors + ["parallel wave candidates must be a nonempty object list"]
    candidate_ids = [str(row.get("candidate_id") or "") for row in rows]
    if any(not candidate_id for candidate_id in candidate_ids):
        errors.append("parallel wave candidate identifiers must be nonempty")
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("parallel wave candidate identifiers must be unique")
    primary_rows = [
        row
        for row in rows
        if str(row.get("candidate_id") or "") == "parallel:primary"
    ]
    if len(primary_rows) != 1 or rows[0] is not primary_rows[0]:
        errors.append("parallel wave must contain one leading primary candidate")
    elif str(primary_rows[0].get("disposition") or "") != "fixed_primary":
        errors.append("parallel wave primary candidate must be fixed")
    elif (
        primary_rows[0].get("budget_allowed") is not True
        and str(primary_rows[0].get("mode") or "")
        not in {"await_human", "stop_with_partial_results", "stop_solved"}
    ):
        errors.append(
            "parallel wave nonterminal primary is not authorized by its budget"
        )

    for row in rows:
        action_class = str(row.get("action_class") or "")
        intent = str(row.get("search_intent") or "")
        identity = row.get("semantic_identity")
        expected_identity_length = 8 if policy_version >= 7 else 7
        identity_valid = not (
            not isinstance(identity, list)
            or len(identity) != expected_identity_length
            or any(not isinstance(item, str) for item in identity)
        )
        if not identity_valid:
            errors.append("parallel wave semantic identity is malformed")
        elif identity[:5] != [
            action_class,
            str(row.get("mode") or ""),
            str(row.get("target_id") or ""),
            str(row.get("route_id") or ""),
            intent,
        ]:
            errors.append("parallel wave semantic identity is inconsistent")
        elif policy_version >= 4:
            try:
                object_identity = json.loads(identity[6])
            except (TypeError, ValueError, json.JSONDecodeError):
                object_identity = None
            if (
                not isinstance(object_identity, Mapping)
                or set(object_identity) != set(PARALLEL_OBJECT_IDENTITY_FIELDS)
                or any(
                    not isinstance(object_identity.get(key), str)
                    for key in PARALLEL_OBJECT_IDENTITY_FIELDS
                )
            ):
                errors.append(
                    "parallel wave semantic object identity is malformed"
                )
        if identity_valid and policy_version >= 7 and (
            len(identity[7]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in identity[7]
            )
        ):
            errors.append(
                "parallel wave semantic payload commitment is not a SHA-256 digest"
            )
        try:
            if type(row.get("admission_priority")) is not int:
                raise TypeError
            if type(row.get("requested_tokens")) is not int:
                raise TypeError
            if type(row.get("admitted_tokens")) is not int:
                raise TypeError
            if type(row.get("consecutive_deferrals")) is not int:
                raise TypeError
            if type(row.get("deferral_limit")) is not int:
                raise TypeError
            if type(row.get("budget_allowed")) is not bool:
                raise TypeError
            priority = int(row.get("admission_priority"))
            requested = int(row.get("requested_tokens") or 0)
            admitted = int(row.get("admitted_tokens") or 0)
            deferrals = int(row.get("consecutive_deferrals") or 0)
            deferral_limit = int(row.get("deferral_limit") or 0)
        except (TypeError, ValueError, OverflowError):
            errors.append(
                "parallel wave priorities, deferrals, budget authorization, and "
                "token counts have invalid types"
            )
            continue
        if requested < 0 or admitted < 0 or admitted > requested:
            errors.append("parallel wave token grants must lie within each request")
        if deferrals < 0 or deferral_limit < 0:
            errors.append("parallel wave deferral values must be nonnegative integers")
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id == "parallel:primary":
            if priority != 1_000_000:
                errors.append("parallel wave primary priority is inconsistent")
            if deferrals != 0 or deferral_limit != 0:
                errors.append("parallel wave primary cannot carry companion deferrals")
        else:
            try:
                expected_priority = parallel_admission_priority_for(
                    action_class, intent
                )
            except KeyError:
                errors.append("parallel wave candidate has an unknown action class")
            else:
                if priority != expected_priority:
                    errors.append("parallel wave candidate priority is inconsistent")
            if deferral_limit != PARALLEL_WAVE_DEFERRAL_LIMIT:
                errors.append("parallel wave candidate deferral limit is inconsistent")
        action_digest = str(row.get("comparison_action_sha256") or "")
        if len(action_digest) != 64 or any(
            character not in "0123456789abcdef" for character in action_digest
        ):
            errors.append("parallel wave action commitment is not a SHA-256 digest")
        disposition = str(row.get("disposition") or "")
        if disposition not in {"fixed_primary", "selected", "rejected"}:
            errors.append("parallel wave candidate has an invalid disposition")
        if policy_version >= 6:
            outcome_code = row.get("outcome_code")
            if not isinstance(outcome_code, str) or not outcome_code:
                errors.append("parallel wave outcome code must be nonempty")
            elif outcome_code != parallel_outcome_code(
                disposition,
                str(row.get("reason") or ""),
                policy_version=policy_version,
            ):
                errors.append("parallel wave outcome code is inconsistent")
        if disposition == "rejected" and admitted != 0:
            errors.append("parallel wave rejected candidate received tokens")
        if candidate_id != "parallel:primary" and identity_valid:
            expected_id = parallel_candidate_id(
                identity,
                policy_version=policy_version,
            )
            if candidate_id != expected_id:
                errors.append("parallel wave candidate identifier is inconsistent")

    expected_order = sorted(
        rows[1:],
        key=lambda row: parallel_admission_order_key(
            row,
            policy_version=policy_version,
        ),
    )
    if list(rows[1:]) != expected_order:
        errors.append("parallel wave candidates are not in canonical admission order")
    try:
        observed_candidate_set_hash = parallel_candidate_set_sha256(
            rows,
            policy_version=policy_version,
        )
    except (TypeError, ValueError, OverflowError, RecursionError):
        observed_candidate_set_hash = ""
        errors.append("parallel wave candidate commitments are not canonical JSON")
    if observed_candidate_set_hash != str(trace.get("candidate_set_sha256") or ""):
        errors.append("parallel wave candidate-set hash is inconsistent")

    selected_ids = [
        str(row.get("candidate_id") or "")
        for row in rows
        if str(row.get("disposition") or "") in {"fixed_primary", "selected"}
    ]
    if trace.get("selected_candidate_ids") != selected_ids:
        errors.append("parallel wave selected candidate identifiers are inconsistent")
    try:
        if type(trace.get("total_wave_capacity")) is not int:
            raise TypeError
        total_capacity = int(trace.get("total_wave_capacity") or 0)
    except (TypeError, ValueError, OverflowError):
        total_capacity = -1
        errors.append("parallel wave total capacity must be an integer")
    if total_capacity < 1 or len(selected_ids) > total_capacity:
        errors.append("parallel wave exceeds total capacity")
    raw_configured_workers = trace.get("configured_proof_search_workers")
    try:
        if type(raw_configured_workers) is not int:
            raise TypeError
        configured_workers = int(raw_configured_workers)
    except (TypeError, ValueError, OverflowError):
        configured_workers = -1
        errors.append("parallel wave configured worker count must be an integer")
    if normalize_parallel_branches(configured_workers) != configured_workers:
        errors.append("parallel wave configured worker count is not normalized")
    expected_total_capacity = max(
        3,
        max(0, configured_workers) + PARALLEL_WAVE_ROLE_DIVERSE_EXTRA_SLOTS,
    )
    if total_capacity != expected_total_capacity:
        errors.append("parallel wave total capacity is inconsistent")
    expected_class_capacities = {
        "research_or_adversarial": configured_workers or 2,
        "verification": configured_workers or 1,
        "integration": configured_workers or 2,
        "literature": 1,
        "advisory": 1,
    }
    raw_class_capacities = trace.get("class_capacities")
    if not isinstance(raw_class_capacities, Mapping):
        errors.append("parallel wave class capacities must be an object")
    else:
        try:
            normalized_class_capacities = {
                str(key): int(value)
                for key, value in raw_class_capacities.items()
                if type(value) is int
            }
        except (TypeError, ValueError, OverflowError):
            normalized_class_capacities = {}
        if normalized_class_capacities != expected_class_capacities:
            errors.append("parallel wave class capacities are inconsistent")
        class_counts: Dict[str, int] = {}
        for row in rows:
            if str(row.get("disposition") or "") not in {
                "fixed_primary",
                "selected",
            }:
                continue
            action_class = str(row.get("action_class") or "")
            capacity_class = (
                "research_or_adversarial"
                if action_class in {"research", "adversarial"}
                else action_class
            )
            class_counts[capacity_class] = class_counts.get(capacity_class, 0) + 1
        for capacity_class, count in class_counts.items():
            try:
                capacity = int(raw_class_capacities.get(capacity_class) or 0)
            except (TypeError, ValueError, OverflowError):
                errors.append("parallel wave class capacity must be an integer")
                continue
            if count > capacity:
                errors.append(f"parallel wave exceeds {capacity_class} capacity")

    admitted_total = sum(
        safe_int(row.get("admitted_tokens"))
        for row in rows
        if isinstance(row, Mapping)
    )
    if admitted_total != safe_int(trace.get("admitted_token_budget")):
        errors.append("parallel wave admitted token total is inconsistent")
    budget_fields_valid = True
    if trace.get("aggregate_budget_enforced") is True:
        budget_values: Dict[str, int] = {}
        for field in (
            "initial_remaining_token_budget",
            "initial_reserved_verification_budget",
            "admitted_token_budget",
            "remaining_uncommitted_token_budget",
        ):
            value = trace.get(field)
            if type(value) is not int or value < 0:
                errors.append(
                    f"parallel wave budget field {field} must be a nonnegative integer"
                )
                budget_fields_valid = False
            else:
                budget_values[field] = value
        initial_total = budget_values.get("initial_remaining_token_budget", 0)
        remaining = budget_values.get("remaining_uncommitted_token_budget", 0)
        if budget_values.get("initial_reserved_verification_budget", 0) > initial_total:
            errors.append(
                "parallel wave protected reserve exceeds the initial allocation"
            )
            budget_fields_valid = False
        if admitted_total + remaining != initial_total:
            errors.append("parallel wave token allocation is not conserved")
    elif trace.get("aggregate_budget_enforced") is not False:
        errors.append("parallel wave aggregate-budget flag must be boolean")
        budget_fields_valid = False
    else:
        for field in (
            "initial_remaining_token_budget",
            "initial_reserved_verification_budget",
            "remaining_uncommitted_token_budget",
        ):
            if trace.get(field) is not None:
                errors.append(
                    f"parallel wave budget field {field} must be null when unenforced"
                )
                budget_fields_valid = False

    if (
        policy_version >= 4
        and binding_fields_valid
        and generator_manifest_binding_valid
        and admission_search_valid
        and isinstance(raw_class_capacities, Mapping)
        and normalized_class_capacities == expected_class_capacities
        and budget_fields_valid
    ):
        try:
            expected_wave_id = parallel_wave_id(
                candidate_set_sha256=str(trace.get("candidate_set_sha256") or ""),
                candidate_set_scope=str(trace.get("candidate_set_scope") or ""),
                state_revision=int(trace.get("state_revision") or 0),
                proof_state_hash=str(trace.get("proof_state_hash") or ""),
                run_provenance_hash=str(trace.get("run_provenance_hash") or ""),
                configured_proof_search_workers=configured_workers,
                total_wave_capacity=total_capacity,
                class_capacities=normalized_class_capacities,
                aggregate_budget_enforced=bool(trace.get("aggregate_budget_enforced")),
                initial_remaining_token_budget=trace.get(
                    "initial_remaining_token_budget"
                ),
                initial_reserved_verification_budget=trace.get(
                    "initial_reserved_verification_budget"
                ),
                candidate_generator_manifest_sha256=(
                    generator_manifest_digest if policy_version >= 5 else ""
                ),
                admission_search=(
                    admission_search
                    if policy_version >= 9 and isinstance(admission_search, Mapping)
                    else None
                ),
                policy_version=policy_version,
            )
        except (TypeError, ValueError, OverflowError, RecursionError):
            expected_wave_id = ""
            errors.append(
                "parallel wave admission-search evidence is not canonical JSON"
            )
        if wave_id != expected_wave_id:
            errors.append("parallel wave identifier does not bind its admission inputs")

    replay_blocking_prefixes = (
        "parallel wave semantic identity",
        "parallel wave priorities",
        "parallel wave deferral",
        "parallel wave primary cannot carry",
        "parallel wave token grants",
        "parallel wave candidate identifier",
        "parallel wave outcome code",
        "parallel wave candidate has an unknown action class",
        "parallel wave class capacit",
        "parallel wave configured worker",
        "parallel wave total capacity",
    )
    if policy_version_valid and budget_fields_valid and not any(
        message.startswith(replay_blocking_prefixes) for message in errors
    ):
        errors.extend(_parallel_wave_replay_errors(trace))
    return errors
