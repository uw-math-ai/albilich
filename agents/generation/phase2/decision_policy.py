from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Dict, Mapping, Sequence

from .action_contract import (
    scheduler_action_contract_errors,
    scheduler_action_contract_trace_binding,
    scheduler_action_contract_trace_errors,
)
from .parallel_admission import parallel_wave_admission_errors
from .scheduler_registry import (
    CANDIDATE_GENERATOR_BOUND_DECISION_POLICY_VERSION,
    candidate_generator_trace_errors,
)


DECISION_POLICY_VERSION = 7
SUPPORTED_DECISION_POLICY_VERSIONS = (4, 5, 6, 7, 8)
_CANDIDATE_COMMITMENT_FIELDS = (
    "candidate_id",
    "domain",
    "comparison_action_sha256",
    "base_policy_trace_sha256",
    "policy_tier",
    "ordinal_priority",
    "admissible",
    "mandatory_constraint",
    "admissibility_reason",
    "consecutive_deferrals",
    "deferral_limit",
)


def action_sha256(action: Mapping[str, Any]) -> str:
    """Hash the exact JSON-like action, excluding its self-referential trace."""

    payload = {
        str(key): value
        for key, value in action.items()
        if str(key) != "decision_trace"
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def policy_trace_sha256(trace: Mapping[str, Any]) -> str:
    """Hash a complete nested policy trace with canonical JSON encoding."""

    return hashlib.sha256(
        json.dumps(
            trace,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def candidate_observations_in_trace(
    trace: Mapping[str, Any],
    *,
    ancestors_selected: bool = True,
    _observations: Dict[str, tuple[Mapping[str, Any], bool]] | None = None,
) -> Dict[str, tuple[Mapping[str, Any], bool]]:
    """Index candidates and whether every comparison ancestor selected them."""

    observations = _observations if _observations is not None else {}
    for item in trace.get("candidates", []):
        if not isinstance(item, Mapping):
            continue
        candidate_id = str(item.get("candidate_id") or "")
        if not candidate_id:
            continue
        if candidate_id in observations:
            raise ValueError(
                "decision trace candidate identifiers must be unique across "
                f"all nested comparisons: {candidate_id}"
            )
        observations[candidate_id] = (item, ancestors_selected)
    nested_traces = trace.get("nested_policy_traces")
    if isinstance(nested_traces, Mapping):
        parent_rows = {
            str(item.get("candidate_id") or ""): item
            for item in trace.get("candidates", [])
            if isinstance(item, Mapping) and str(item.get("candidate_id") or "")
        }
        for raw_parent_id, nested_trace in nested_traces.items():
            parent_id = str(raw_parent_id or "")
            parent_row = parent_rows.get(parent_id)
            if parent_row is None or not isinstance(nested_trace, Mapping):
                continue
            observations.update(
                candidate_observations_in_trace(
                    nested_trace,
                    ancestors_selected=(
                        ancestors_selected
                        and str(parent_row.get("disposition") or "") == "selected"
                    ),
                    _observations=observations,
                )
            )
        return observations

    nested = trace.get("base_policy_trace")
    if isinstance(nested, Mapping):
        nested_digest = policy_trace_sha256(nested)
        parent_row = next(
            (
                item
                for item in trace.get("candidates", [])
                if isinstance(item, Mapping)
                and str(item.get("base_policy_trace_sha256") or "")
                == nested_digest
            ),
            None,
        )
        parent_selected = (
            str(parent_row.get("disposition") or "") == "selected"
            if parent_row is not None
            else str(trace.get("selected_candidate_id") or "")
            == "base:sequential_planner"
        )
        observations.update(
            candidate_observations_in_trace(
                nested,
                ancestors_selected=ancestors_selected and parent_selected,
                _observations=observations,
            )
        )
    return observations


def decision_trace_is_parallel_companion(trace: Mapping[str, Any]) -> bool:
    """Identify a companion wrapper without classifying primary wave traces."""

    wave = trace.get("parallel_wave_admission")
    if not isinstance(wave, Mapping):
        return False
    binding_id = trace.get("parallel_wave_candidate_id")
    if binding_id not in {None, "parallel:primary"}:
        return True
    rows = trace.get("candidates")
    return (
        binding_id is None
        and isinstance(rows, list)
        and bool(rows)
        and all(
            isinstance(row, Mapping) and row.get("domain") == "parallel_wave"
            for row in rows
        )
    )


def decision_candidate_deferral_counts_from_state(
    stored_counts: Mapping[str, Any], candidate_ids: Sequence[str]
) -> Dict[str, int]:
    """Read compact authenticated generic-comparison counters."""

    counts: Dict[str, int] = {}
    for candidate_id in candidate_ids:
        value = stored_counts.get(candidate_id, 0)
        if type(value) is not int or value < 0:
            raise ValueError(
                "decision candidate deferral state must contain nonnegative integers"
            )
        counts[candidate_id] = value
    return counts


def decision_rejection_is_fairness_eligible(disposition: str) -> bool:
    """Return whether another rejection should advance within-stratum fairness."""

    return disposition in {
        "rejected_by_ordinal_comparison",
        "rejected_by_fairness_constraint",
    }


def decision_deferral_state_after_trace(
    stored_counts: Mapping[str, Any],
    trace: Mapping[str, Any],
    *,
    enforce_prior_counts: bool = True,
) -> Dict[str, int]:
    """Apply one complete primary comparison to compact deferral state."""

    observations = candidate_observations_in_trace(trace)
    prior = decision_candidate_deferral_counts_from_state(
        stored_counts, list(observations)
    )
    updated: Dict[str, int] = {}
    for candidate_id, (row, ancestors_selected) in observations.items():
        row_count = row.get("consecutive_deferrals")
        if type(row_count) is not int or row_count < 0:
            raise ValueError(
                f"decision trace has an invalid deferral count for {candidate_id}"
            )
        if enforce_prior_counts and row_count != prior[candidate_id]:
            raise ValueError(
                "decision trace deferral input disagrees with authenticated "
                f"scheduler state for {candidate_id}"
            )
        if row.get("admissible") is not True:
            continue
        disposition = str(row.get("disposition") or "")
        if ancestors_selected and disposition == "selected":
            continue
        if ancestors_selected and not decision_rejection_is_fairness_eligible(
            disposition
        ):
            continue
        updated[candidate_id] = row_count + 1
    return updated


def bind_dispatched_action(
    action: Mapping[str, Any], trace: Mapping[str, Any]
) -> Dict[str, Any]:
    """Bind post-comparison enrichment to the decision trace stored with a run."""

    bound_trace = dict(trace)
    dispatched_hash = action_sha256(action)
    selected_id = str(bound_trace.get("selected_candidate_id") or "")
    selected_comparison_hash = next(
        (
            str(row.get("comparison_action_sha256") or "")
            for row in bound_trace.get("candidates", [])
            if isinstance(row, Mapping)
            and str(row.get("candidate_id") or "") == selected_id
        ),
        "",
    )
    bound_trace["dispatched_action_sha256"] = dispatched_hash
    bound_trace["post_comparison_transformation"] = (
        dispatched_hash != selected_comparison_hash
    )
    return bound_trace


@dataclass(frozen=True)
class ActionCandidate:
    """One host-generated scheduler candidate with an auditable lexicographic rank."""

    candidate_id: str
    domain: str
    action: Mapping[str, Any]
    ordinal_priority: float
    admissible: bool = True
    mandatory_constraint: bool = False
    admissibility_reason: str = ""
    consecutive_deferrals: int = 0
    deferral_limit: int = 0
    policy_tier: int = 0


def candidate_rows_sha256(
    rows: Sequence[Mapping[str, Any]],
    *,
    decision_policy_version: int = DECISION_POLICY_VERSION,
) -> str:
    """Hash canonical candidate commitment rows from generation or a trace."""

    fields = tuple(
        field
        for field in _CANDIDATE_COMMITMENT_FIELDS
        if not (field == "policy_tier" and decision_policy_version < 5)
        and not (
            field == "base_policy_trace_sha256"
            and decision_policy_version < 6
        )
    )
    canonical = [
        {field: row.get(field) for field in fields}
        for row in sorted(rows, key=lambda item: str(item.get("candidate_id") or ""))
    ]
    return hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def candidate_set_sha256(candidates: Sequence[ActionCandidate]) -> str:
    """Hash the comparison inputs in canonical candidate-id order.

    The digest is independent of generator traversal order. It commits to the
    exact actions and all fields that can change selection, so a stored trace
    can be matched to the candidate set that was actually compared.
    """

    rows = [
        {
            "candidate_id": candidate.candidate_id,
            "domain": candidate.domain,
            "comparison_action_sha256": action_sha256(candidate.action),
            "base_policy_trace_sha256": str(
                candidate.action.get("base_policy_trace_sha256") or ""
            ),
            "policy_tier": int(candidate.policy_tier),
            "ordinal_priority": float(candidate.ordinal_priority),
            "admissible": bool(candidate.admissible),
            "mandatory_constraint": bool(candidate.mandatory_constraint),
            "admissibility_reason": candidate.admissibility_reason,
            "consecutive_deferrals": int(candidate.consecutive_deferrals),
            "deferral_limit": int(candidate.deferral_limit),
        }
        for candidate in sorted(candidates, key=lambda item: item.candidate_id)
    ]
    return candidate_rows_sha256(rows)


def decision_outcomes(
    rows: Sequence[Mapping[str, Any]],
    *,
    policy_version: int = DECISION_POLICY_VERSION,
) -> tuple[str, Dict[str, str]]:
    """Apply the pure mandatory/tier/fairness comparison transition."""

    admissible = [row for row in rows if row.get("admissible") is True]
    if not admissible:
        raise ValueError("scheduler candidate set has no admissible action")
    mandatory = [
        row for row in admissible if row.get("mandatory_constraint") is True
    ]
    constrained = mandatory or admissible

    def policy_tier(row: Mapping[str, Any]) -> int:
        return int(row.get("policy_tier") or 0) if policy_version >= 5 else 0

    maximal_tier = max(policy_tier(row) for row in constrained)
    tier_pool = [row for row in constrained if policy_tier(row) == maximal_tier]
    fairness_due = [
        row
        for row in tier_pool
        if int(row.get("deferral_limit") or 0) > 0
        and int(row.get("consecutive_deferrals") or 0)
        >= int(row.get("deferral_limit") or 0)
    ]
    pool = fairness_due or tier_pool
    tier_candidate_ids = {
        str(row.get("candidate_id") or "") for row in tier_pool
    }
    fairness_candidate_ids = {
        str(row.get("candidate_id") or "") for row in fairness_due
    }
    selected = max(
        pool,
        key=lambda row: (
            int(row.get("consecutive_deferrals") or 0) if fairness_due else 0,
            float(row.get("ordinal_priority") or 0.0),
            str(row.get("candidate_id") or ""),
        ),
    )
    selected_id = str(selected.get("candidate_id") or "")
    dispositions: Dict[str, str] = {}
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        if row.get("admissible") is not True:
            disposition = "rejected_inadmissible"
        elif candidate_id == selected_id:
            disposition = "selected"
        elif mandatory and row.get("mandatory_constraint") is not True:
            disposition = "rejected_by_mandatory_constraint"
        elif candidate_id not in tier_candidate_ids:
            disposition = "rejected_by_policy_tier"
        elif fairness_due and candidate_id not in fairness_candidate_ids:
            disposition = "rejected_by_fairness_constraint"
        else:
            disposition = "rejected_by_ordinal_comparison"
        dispositions[candidate_id] = disposition
    return selected_id, dispositions


def decision_policy_semantic_sha256(policy_version: int) -> str:
    """Hash canonical selection and replay-contract scenarios for one epoch."""

    if policy_version not in SUPPORTED_DECISION_POLICY_VERSIONS:
        raise ValueError(f"unsupported decision policy {policy_version}")

    def row(
        candidate_id: str,
        *,
        priority: float,
        tier: int = 0,
        admissible: bool = True,
        mandatory: bool = False,
        deferrals: int = 0,
        limit: int = 3,
    ) -> Dict[str, Any]:
        return {
            "candidate_id": candidate_id,
            "ordinal_priority": priority,
            "policy_tier": tier,
            "admissible": admissible,
            "mandatory_constraint": mandatory,
            "consecutive_deferrals": deferrals,
            "deferral_limit": limit,
        }

    scenarios = {
        "mandatory": [
            row("ordinary", priority=100, tier=100),
            row("mandatory", priority=0, tier=0, mandatory=True),
        ],
        "policy_tier": [
            row("high-priority-low-tier", priority=100, tier=0),
            row("low-priority-high-tier", priority=0, tier=1),
        ],
        "bounded_deferral": [
            row("fresh", priority=100, tier=1),
            row("aged", priority=0, tier=1, deferrals=3),
        ],
        "inadmissible": [
            row("inadmissible", priority=1_000, tier=10, admissible=False),
            row("admissible", priority=0, tier=0),
        ],
        "canonical_tie": [
            row("candidate-a", priority=1, tier=1),
            row("candidate-b", priority=1, tier=1),
        ],
    }
    observations = []
    for name, rows in sorted(scenarios.items()):
        selected_id, dispositions = decision_outcomes(
            rows,
            policy_version=policy_version,
        )
        observations.append(
            {
                "scenario": name,
                "selected_candidate_id": selected_id,
                "dispositions": dict(sorted(dispositions.items())),
            }
        )

    def trace_for_rows(
        rows: Sequence[Mapping[str, Any]],
        *,
        version: int,
        nested_policy_traces: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        trace_rows = [dict(row) for row in rows]
        selected_id, dispositions = decision_outcomes(
            trace_rows,
            policy_version=version,
        )
        for trace_row in trace_rows:
            trace_row["disposition"] = dispositions[
                str(trace_row["candidate_id"])
            ]
        trace: Dict[str, Any] = {
            "decision_policy_version": version,
            "candidate_set_sha256": candidate_rows_sha256(
                trace_rows,
                decision_policy_version=version,
            ),
            "candidate_set_complete": True,
            "candidate_set_scope": "semantic conformance fixture",
            "selected_candidate_id": selected_id,
            "candidates": trace_rows,
        }
        if nested_policy_traces is not None:
            trace["nested_policy_traces"] = dict(nested_policy_traces)
        return trace

    def committed_row(
        candidate_id: str,
        *,
        priority: float,
        tier: int = 1,
        base_policy_trace_sha256: str = "",
    ) -> Dict[str, Any]:
        return {
            "candidate_id": candidate_id,
            "domain": "semantic_conformance",
            "comparison_action_sha256": hashlib.sha256(
                candidate_id.encode("utf-8")
            ).hexdigest(),
            "base_policy_trace_sha256": base_policy_trace_sha256,
            "policy_tier": tier,
            "ordinal_priority": priority,
            "admissible": True,
            "mandatory_constraint": False,
            "admissibility_reason": "",
            "consecutive_deferrals": 0,
            "deferral_limit": 3,
        }

    schema_row = committed_row("schema-probe", priority=1)
    tier_mutation = dict(schema_row, policy_tier=2)
    base_commitment_mutation = dict(
        schema_row,
        base_policy_trace_sha256="b" * 64,
    )
    schema_hash = candidate_rows_sha256(
        [schema_row], decision_policy_version=policy_version
    )

    nested_left = trace_for_rows(
        [committed_row("nested-left-leaf", priority=1)], version=4
    )
    nested_right = trace_for_rows(
        [committed_row("nested-right-leaf", priority=1)], version=4
    )
    indexed_rows = [
        committed_row(
            "outer-left",
            priority=2,
            base_policy_trace_sha256=policy_trace_sha256(nested_left),
        ),
        committed_row(
            "outer-right",
            priority=1,
            base_policy_trace_sha256=policy_trace_sha256(nested_right),
        ),
    ]
    indexed_trace = trace_for_rows(
        indexed_rows,
        version=policy_version,
        nested_policy_traces={
            "outer-left": nested_left,
            "outer-right": nested_right,
        },
    )
    plain_trace = trace_for_rows(
        [committed_row("plain-probe", priority=1)],
        version=policy_version,
    )
    observations.append(
        {
            "scenario": "replay_contract",
            "policy_tier_is_committed": schema_hash
            != candidate_rows_sha256(
                [tier_mutation], decision_policy_version=policy_version
            ),
            "base_policy_trace_is_committed": schema_hash
            != candidate_rows_sha256(
                [base_commitment_mutation],
                decision_policy_version=policy_version,
            ),
            "plain_trace_errors": decision_trace_errors(plain_trace),
            "indexed_nested_trace_errors": decision_trace_errors(indexed_trace),
        }
    )
    return hashlib.sha256(
        json.dumps(
            observations,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def decision_trace_errors(
    trace: Mapping[str, Any],
    *,
    _seen_trace_ids: set[int] | None = None,
) -> list[str]:
    """Validate that a persisted trace is internally consistent."""

    if not isinstance(trace, Mapping):
        return ["decision trace must be an object"]
    root_trace = _seen_trace_ids is None
    # Copy the ancestor set at each level: a repeated immutable subtree is
    # harmless, while an object that refers to one of its ancestors is cyclic.
    _seen_trace_ids = set(_seen_trace_ids or ())
    trace_object_id = id(trace)
    if trace_object_id in _seen_trace_ids:
        return ["decision trace contains a cyclic or repeated nested object"]
    _seen_trace_ids.add(trace_object_id)

    errors: list[str] = []
    errors.extend(candidate_generator_trace_errors(trace))
    errors.extend(scheduler_action_contract_trace_errors(trace))
    nested_digest_cache: dict[int, str | None] = {}

    def canonical_nested_digest(
        value: Mapping[str, Any], *, label: str
    ) -> str | None:
        object_id = id(value)
        if object_id in nested_digest_cache:
            return nested_digest_cache[object_id]
        try:
            digest = policy_trace_sha256(value)
        except (TypeError, ValueError, OverflowError, RecursionError):
            errors.append(f"{label} is not canonical JSON")
            digest = None
        nested_digest_cache[object_id] = digest
        return digest

    parallel_wave = trace.get("parallel_wave_admission")
    if parallel_wave is not None:
        if not isinstance(parallel_wave, Mapping):
            errors.append(
                "decision trace parallel_wave_admission must be an object"
            )
        else:
            errors.extend(
                f"parallel wave admission: {error}"
                for error in parallel_wave_admission_errors(parallel_wave)
            )
    validated_nested_digests: set[str] = set()
    nested = trace.get("base_policy_trace")
    if nested is not None:
        if not isinstance(nested, Mapping):
            errors.append("decision trace base_policy_trace must be an object")
        else:
            nested_digest = canonical_nested_digest(
                nested, label="decision trace base_policy_trace"
            )
            if nested_digest is not None:
                validated_nested_digests.add(nested_digest)
            errors.extend(
                f"base policy trace: {error}"
                for error in decision_trace_errors(
                    nested, _seen_trace_ids=_seen_trace_ids
                )
            )
    raw_rows = trace.get("candidates")
    if not isinstance(raw_rows, list) or not raw_rows:
        return errors + ["decision trace candidates must be a nonempty list"]
    if any(not isinstance(row, Mapping) for row in raw_rows):
        return errors + ["decision trace candidates must contain only objects"]
    rows = list(raw_rows)
    raw_policy_version = trace.get("decision_policy_version")
    if type(raw_policy_version) is not int:
        policy_version = DECISION_POLICY_VERSION
        errors.append("decision trace policy version must be an integer")
    elif raw_policy_version not in SUPPORTED_DECISION_POLICY_VERSIONS:
        policy_version = DECISION_POLICY_VERSION
        errors.append("decision trace policy version is not supported")
    else:
        policy_version = raw_policy_version
    if policy_version >= CANDIDATE_GENERATOR_BOUND_DECISION_POLICY_VERSION and (
        trace.get("candidate_generator_manifest_version") != 2
        or trace.get("candidate_generator_scope_id") is None
        or type(trace.get("candidate_generator_graph_version")) is not int
        or int(trace.get("candidate_generator_graph_version") or 0) < 3
    ):
        errors.append(
            "decision trace policy version requires current candidate-generator provenance"
        )
    candidate_ids = [row.get("candidate_id") for row in rows]
    candidate_ids_valid = all(
        isinstance(candidate_id, str) and bool(candidate_id)
        for candidate_id in candidate_ids
    )
    if not candidate_ids_valid:
        errors.append("decision trace candidate identifiers must be nonempty strings")
    elif len(candidate_ids) != len(set(candidate_ids)):
        errors.append("decision trace candidate identifiers must be unique")
    if type(trace.get("candidate_set_complete")) is not bool:
        errors.append("decision trace candidate-set completeness must be boolean")
    if not isinstance(trace.get("candidate_set_scope"), str) or not str(
        trace.get("candidate_set_scope") or ""
    ).strip():
        errors.append("decision trace candidate-set scope must be a nonempty string")
    selected_candidate_id = trace.get("selected_candidate_id")
    if not isinstance(selected_candidate_id, str) or not selected_candidate_id:
        errors.append("decision trace selected candidate identifier must be a nonempty string")
    candidate_digest = trace.get("candidate_set_sha256")
    if not isinstance(candidate_digest, str) or len(candidate_digest) != 64 or any(
        character not in "0123456789abcdef" for character in candidate_digest
    ):
        errors.append("decision trace candidate-set commitment must be a SHA-256 digest")
    dispatched_digest = trace.get("dispatched_action_sha256")
    if dispatched_digest is not None and (
        not isinstance(dispatched_digest, str)
        or len(dispatched_digest) != 64
        or any(character not in "0123456789abcdef" for character in dispatched_digest)
    ):
        errors.append("decision trace dispatched-action commitment must be a SHA-256 digest")
    if "post_comparison_transformation" in trace and type(
        trace.get("post_comparison_transformation")
    ) is not bool:
        errors.append("decision trace transformation flag must be boolean")
    for row in rows:
        domain = row.get("domain")
        if not isinstance(domain, str) or not domain:
            errors.append("decision trace candidate domains must be nonempty strings")
        priority = row.get("ordinal_priority")
        if isinstance(priority, bool) or not isinstance(priority, (int, float)):
            errors.append("decision trace priorities must be numeric")
        elif not math.isfinite(float(priority)):
            errors.append("decision trace priorities must be finite")
        for field in ("admissible", "mandatory_constraint"):
            if type(row.get(field)) is not bool:
                errors.append(f"decision trace {field} must be boolean")
        if not isinstance(row.get("admissibility_reason"), str):
            errors.append("decision trace admissibility_reason must be a string")
        comparison_digest = row.get("comparison_action_sha256")
        if (
            not isinstance(comparison_digest, str)
            or len(comparison_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in comparison_digest
            )
        ):
            errors.append(
                "decision trace comparison-action commitment must be a SHA-256 digest"
            )
        base_trace_digest = row.get("base_policy_trace_sha256")
        if base_trace_digest is None and policy_version < 6:
            base_trace_digest = ""
        elif not isinstance(base_trace_digest, str):
            errors.append("decision trace base-policy commitment must be a string")
            base_trace_digest = ""
        if policy_version >= 6 and base_trace_digest and (
            len(base_trace_digest) != 64
            or any(character not in "0123456789abcdef" for character in base_trace_digest)
        ):
            errors.append(
                "decision trace base-policy commitment must be a lowercase SHA-256 digest"
            )
        policy_tier = row.get("policy_tier")
        if policy_version >= 5 and (
            isinstance(policy_tier, bool) or not isinstance(policy_tier, int)
        ):
            errors.append("decision trace policy_tier must be an integer")
        for field in ("consecutive_deferrals", "deferral_limit"):
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append(f"decision trace {field} must be a nonnegative integer")
        if not isinstance(row.get("disposition"), str):
            errors.append("decision trace dispositions must be strings")
    if (
        isinstance(dispatched_digest, str)
        and len(dispatched_digest) == 64
        and isinstance(selected_candidate_id, str)
    ):
        selected_rows = [
            row
            for row in rows
            if row.get("candidate_id") == selected_candidate_id
        ]
        if len(selected_rows) == 1:
            transformation_flag = trace.get("post_comparison_transformation")
            if type(transformation_flag) is not bool:
                errors.append(
                    "decision trace with a dispatched action must declare its transformation flag"
                )
            elif transformation_flag != (
                dispatched_digest
                != selected_rows[0].get("comparison_action_sha256")
            ):
                errors.append(
                    "decision trace transformation flag disagrees with its action commitments"
                )
    # v3 waves predate cross-layer bindings and remain replay-compatible.
    # Every v4-or-newer wave must identify the exact admitted input row.
    if (
        isinstance(parallel_wave, Mapping)
        and type(parallel_wave.get("policy_version")) is int
        and int(parallel_wave.get("policy_version")) >= 4
    ):
        wave_binding_id = trace.get("parallel_wave_candidate_id")
        if not isinstance(wave_binding_id, str) or not wave_binding_id:
            errors.append(
                "decision trace parallel-wave candidate binding must be a nonempty string"
            )
        wave_input_digest = trace.get("parallel_wave_input_action_sha256")
        if (
            not isinstance(wave_input_digest, str)
            or len(wave_input_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in wave_input_digest
            )
        ):
            errors.append(
                "decision trace parallel-wave input binding must be a SHA-256 digest"
            )
        raw_wave_rows = parallel_wave.get("candidates")
        matching_wave_rows = (
            [
                row
                for row in raw_wave_rows
                if isinstance(row, Mapping)
                and row.get("candidate_id") == wave_binding_id
            ]
            if isinstance(raw_wave_rows, list)
            and isinstance(wave_binding_id, str)
            else []
        )
        if len(matching_wave_rows) != 1:
            errors.append(
                "decision trace parallel-wave candidate binding is not unique in the wave"
            )
        else:
            bound_wave_row = matching_wave_rows[0]
            if bound_wave_row.get("disposition") not in {
                "fixed_primary",
                "selected",
            }:
                errors.append(
                    "decision trace parallel-wave candidate binding was not admitted"
                )
            if (
                isinstance(wave_input_digest, str)
                and bound_wave_row.get("comparison_action_sha256")
                != wave_input_digest
            ):
                errors.append(
                    "decision trace parallel-wave input binding disagrees with the wave"
                )
        parallel_domain_rows = [
            row for row in rows if row.get("domain") == "parallel_wave"
        ]
        if wave_binding_id == "parallel:primary":
            if parallel_domain_rows:
                errors.append(
                    "primary decision trace cannot identify itself as a companion"
                )
        elif (
            len(rows) != 1
            or len(parallel_domain_rows) != 1
            or selected_candidate_id != wave_binding_id
        ):
            errors.append(
                "companion decision trace does not select its bound wave candidate"
            )
    if policy_version >= 6:
        committed_nested_digests = {
            str(row.get("candidate_id") or ""): str(
                row.get("base_policy_trace_sha256") or ""
            )
            for row in rows
            if str(row.get("base_policy_trace_sha256") or "")
        }
        if policy_version < 7:
            committed_digest_values = list(committed_nested_digests.values())
            if isinstance(nested, Mapping):
                expected_nested_digest = canonical_nested_digest(
                    nested, label="decision trace base_policy_trace"
                )
                if (
                    expected_nested_digest is not None
                    and committed_digest_values != [expected_nested_digest]
                ):
                    errors.append(
                        "decision trace base policy trace disagrees with its candidate commitment"
                    )
            elif committed_digest_values:
                errors.append(
                    "decision trace omits a base policy trace committed by a candidate"
                )
        else:
            raw_nested_traces = trace.get("nested_policy_traces")
            nested_traces: dict[str, Mapping[str, Any]] = {}
            if raw_nested_traces is not None:
                if not isinstance(raw_nested_traces, Mapping):
                    errors.append(
                        "decision trace nested_policy_traces must be an object"
                    )
                else:
                    for raw_candidate_id, raw_nested_trace in raw_nested_traces.items():
                        candidate_id = str(raw_candidate_id or "")
                        if not candidate_id:
                            errors.append(
                                "decision trace nested policy candidate identifiers must be nonempty"
                            )
                            continue
                        if candidate_id not in candidate_ids:
                            errors.append(
                                f"decision trace has a nested policy trace for unknown candidate {candidate_id}"
                            )
                            continue
                        if not isinstance(raw_nested_trace, Mapping):
                            errors.append(
                                f"decision trace nested policy trace for {candidate_id} must be an object"
                            )
                            continue
                        nested_traces[candidate_id] = raw_nested_trace
                        nested_digest = canonical_nested_digest(
                            raw_nested_trace,
                            label=(
                                "decision trace nested policy trace for "
                                f"{candidate_id}"
                            ),
                        )
                        if (
                            nested_digest is not None
                            and nested_digest not in validated_nested_digests
                        ):
                            validated_nested_digests.add(nested_digest)
                            errors.extend(
                                f"nested policy trace {candidate_id}: {error}"
                                for error in decision_trace_errors(
                                    raw_nested_trace,
                                    _seen_trace_ids=_seen_trace_ids,
                                )
                            )
                        if (
                            nested_digest is not None
                            and committed_nested_digests.get(candidate_id)
                            != nested_digest
                        ):
                            errors.append(
                                f"decision trace nested policy trace for {candidate_id} disagrees with its candidate commitment"
                            )

            selected_candidate_id = str(
                trace.get("selected_candidate_id") or ""
            )
            for candidate_id in committed_nested_digests:
                if candidate_id in nested_traces:
                    continue
                if (
                    candidate_id == selected_candidate_id
                    and isinstance(nested, Mapping)
                    and (
                        selected_alias_digest := canonical_nested_digest(
                            nested, label="decision trace base_policy_trace"
                        )
                    )
                    == committed_nested_digests[candidate_id]
                ):
                    # Accept the single-selected-nested shape emitted by v6
                    # callers that were upgraded in place to policy version 7.
                    continue
                errors.append(
                    f"decision trace omits the nested policy trace committed by candidate {candidate_id}"
                )
            for candidate_id in nested_traces:
                if candidate_id not in committed_nested_digests:
                    errors.append(
                        f"decision trace nested policy trace for {candidate_id} has no candidate commitment"
                    )
            if isinstance(nested, Mapping):
                base_alias_digest = canonical_nested_digest(
                    nested, label="decision trace base_policy_trace"
                )
                if (
                    base_alias_digest is not None
                    and base_alias_digest
                    not in set(committed_nested_digests.values())
                ):
                    errors.append(
                        "decision trace base_policy_trace alias has no candidate commitment"
                    )
            if isinstance(nested, Mapping) and selected_candidate_id in nested_traces:
                base_alias_digest = canonical_nested_digest(
                    nested, label="decision trace base_policy_trace"
                )
                selected_nested_digest = canonical_nested_digest(
                    nested_traces[selected_candidate_id],
                    label=(
                        "decision trace nested policy trace for "
                        f"{selected_candidate_id}"
                    ),
                )
                if (
                    base_alias_digest is not None
                    and selected_nested_digest is not None
                    and base_alias_digest != selected_nested_digest
                ):
                    errors.append(
                        "decision trace base_policy_trace alias disagrees with the selected nested policy trace"
                    )
    if root_trace and not errors:
        try:
            candidate_observations_in_trace(trace)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        return errors
    if not any(row.get("admissible") is True for row in rows):
        errors.append("decision trace has no admissible candidate")
        return errors
    expected_selected_id, expected_dispositions = decision_outcomes(
        rows,
        policy_version=policy_version,
    )
    if str(trace.get("selected_candidate_id") or "") != expected_selected_id:
        errors.append("decision trace selected candidate disagrees with the selection rule")
    for row in rows:
        expected = expected_dispositions[str(row.get("candidate_id") or "")]
        if str(row.get("disposition") or "") != expected:
            errors.append(
                f"decision trace disposition for {row.get('candidate_id') or '<missing>'} is inconsistent"
            )
    expected_hash = str(trace.get("candidate_set_sha256") or "")
    if candidate_rows_sha256(
        rows,
        decision_policy_version=policy_version,
    ) != expected_hash:
        errors.append("decision trace candidate-set hash is inconsistent")
    return errors


DECISION_POLICY_SEMANTIC_SHA256: Mapping[int, str] = MappingProxyType(
    {
        # Executable conformance digests. Published entries are immutable;
        # add a policy epoch for future changes.
        4: "9a54dda08002a92bfb399ad67e85197ea953951e12caf2454be2c572a4f8b831",
        5: "08a094df56274c9826dd87ddf7433eb8ca7cc2a046a40b2d3a0d2ba59394ea16",
        6: "39dd764fb07dcfb5c08b07f6cef46ff0be938458fa93a142083b610f7d4a1f3b",
        7: "411a5ad2dc33ceef90ce52149192d0c96cdf62b7c5c01fea77b9c19c316f989d",
        8: "859c4157c3f86f4d86bdf14fc6633097ae9a84264bb0018ce07415a6a67e1e2b",
    }
)


def decision_policy_semantic_errors() -> list[str]:
    """Detect missing or changed published decision semantics."""

    errors: list[str] = []
    supported = set(SUPPORTED_DECISION_POLICY_VERSIONS)
    committed = set(DECISION_POLICY_SEMANTIC_SHA256)
    for version in sorted(supported - committed):
        errors.append(
            f"decision policy v{version} has no semantic conformance commitment"
        )
    for version in sorted(committed - supported):
        errors.append(
            f"decision semantic commitment names unsupported policy v{version}"
        )
    for version in sorted(supported & committed):
        if decision_policy_semantic_sha256(version) != (
            DECISION_POLICY_SEMANTIC_SHA256[version]
        ):
            errors.append(
                f"decision policy v{version} changed without a new version"
            )
    return errors


_DECISION_POLICY_SEMANTIC_ERRORS = tuple(decision_policy_semantic_errors())
if _DECISION_POLICY_SEMANTIC_ERRORS:
    raise RuntimeError(
        "invalid decision policy semantics: "
        + "; ".join(_DECISION_POLICY_SEMANTIC_ERRORS)
    )


def select_action_candidate(
    candidates: Sequence[ActionCandidate],
    *,
    candidate_set_complete: bool,
    candidate_set_scope: str = "",
    nested_policy_traces: Mapping[str, Mapping[str, Any]] | None = None,
    _nested_policy_traces_already_validated: bool = False,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Select deterministically and return the complete comparison trace supplied.

    A mandatory constraint takes precedence over policy tiers. The maximal
    policy tier is then selected before bounded-deferral fairness is applied
    within that tier. Finally, the greatest ordinal priority wins and the
    candidate identifier is the canonical tie-breaker. The
    caller must state honestly whether its generators materialized the complete
    admissible set within the declared scope. Completeness of a registered
    generator boundary is not proof that the registry contains every useful
    policy or mathematically imaginable action.
    """

    if not candidates:
        raise ValueError("scheduler candidate set must be non-empty")
    if type(candidate_set_complete) is not bool:
        raise ValueError("scheduler candidate-set completeness must be boolean")
    if not isinstance(candidate_set_scope, str):
        raise ValueError("scheduler candidate-set scope must be a string")
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    if any(not isinstance(candidate_id, str) or not candidate_id for candidate_id in candidate_ids):
        raise ValueError("scheduler candidate identifiers must be non-empty strings")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("scheduler candidate identifiers must be unique")
    if any(
        isinstance(candidate.ordinal_priority, bool)
        or not isinstance(candidate.ordinal_priority, (int, float))
        or not math.isfinite(float(candidate.ordinal_priority))
        for candidate in candidates
    ):
        raise ValueError("scheduler candidate priorities must be finite")
    if any(
        isinstance(candidate.policy_tier, bool)
        or not isinstance(candidate.policy_tier, int)
        for candidate in candidates
    ):
        raise ValueError("scheduler policy tiers must be integers")
    if any(not isinstance(candidate.action, Mapping) for candidate in candidates):
        raise ValueError("scheduler candidate actions must be mappings")
    if any(
        not isinstance(candidate.domain, str) or not candidate.domain
        for candidate in candidates
    ):
        raise ValueError("scheduler candidate domains must be non-empty strings")
    if any(
        type(candidate.admissible) is not bool
        or type(candidate.mandatory_constraint) is not bool
        or not isinstance(candidate.admissibility_reason, str)
        for candidate in candidates
    ):
        raise ValueError("scheduler candidate flags and reasons have invalid types")
    invalid_action_errors = [
        error
        for candidate in candidates
        for error in scheduler_action_contract_errors(candidate.action)
    ]
    if invalid_action_errors:
        raise ValueError(
            "scheduler candidate action violates the routing contract: "
            + invalid_action_errors[0]
        )
    if any(
        isinstance(candidate.consecutive_deferrals, bool)
        or not isinstance(candidate.consecutive_deferrals, int)
        or candidate.consecutive_deferrals < 0
        or isinstance(candidate.deferral_limit, bool)
        or not isinstance(candidate.deferral_limit, int)
        or candidate.deferral_limit < 0
        for candidate in candidates
    ):
        raise ValueError("scheduler deferral counts and limits must be nonnegative integers")

    nested_policy_traces = dict(nested_policy_traces or {})
    candidate_id_set = set(candidate_ids)
    unknown_nested_ids = set(nested_policy_traces) - candidate_id_set
    if unknown_nested_ids:
        raise ValueError(
            "nested policy traces reference unknown candidates: "
            + ", ".join(sorted(unknown_nested_ids))
        )
    effective_candidates: list[ActionCandidate] = []
    for candidate in candidates:
        nested_trace = nested_policy_traces.get(candidate.candidate_id)
        if nested_trace is None:
            effective_candidates.append(candidate)
            continue
        if not isinstance(nested_trace, Mapping):
            raise ValueError("nested policy traces must be mappings")
        if not _nested_policy_traces_already_validated:
            nested_errors = decision_trace_errors(nested_trace)
            if nested_errors:
                raise ValueError(
                    f"nested policy trace for {candidate.candidate_id} is invalid: "
                    + "; ".join(nested_errors)
                )
        digest = policy_trace_sha256(nested_trace)
        action = dict(candidate.action)
        existing_digest = str(action.get("base_policy_trace_sha256") or "")
        if existing_digest and existing_digest != digest:
            raise ValueError(
                f"candidate {candidate.candidate_id} has a conflicting nested policy trace commitment"
            )
        action["base_policy_trace_sha256"] = digest
        effective_candidates.append(replace(candidate, action=action))
    candidates = effective_candidates
    rows: list[Dict[str, Any]] = []
    for candidate in candidates:
        # Persist only selection inputs, their action commitment, and the
        # validator-checkable disposition. Mode/target/route/policy labels
        # are committed by comparison_action_sha256 and remain on the
        # selected run.
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "domain": candidate.domain,
                "base_policy_trace_sha256": str(
                    candidate.action.get("base_policy_trace_sha256") or ""
                ),
                "policy_tier": int(candidate.policy_tier),
                "ordinal_priority": float(candidate.ordinal_priority),
                "comparison_action_sha256": action_sha256(candidate.action),
                "admissible": candidate.admissible,
                "mandatory_constraint": candidate.mandatory_constraint,
                "admissibility_reason": candidate.admissibility_reason,
                "consecutive_deferrals": candidate.consecutive_deferrals,
                "deferral_limit": candidate.deferral_limit,
            }
        )
    selected_id, dispositions = decision_outcomes(rows)
    for row in rows:
        row["disposition"] = dispositions[str(row["candidate_id"])]
    selected = next(
        candidate for candidate in candidates if candidate.candidate_id == selected_id
    )
    trace = {
        "decision_policy_version": DECISION_POLICY_VERSION,
        **scheduler_action_contract_trace_binding(),
        # The trace rows contain the exact commitment fields. Hash them once
        # instead of serializing every candidate action a second time.
        "candidate_set_sha256": candidate_rows_sha256(rows),
        "candidate_set_complete": bool(candidate_set_complete),
        "candidate_set_scope": (
            candidate_set_scope
            or (
                "all registered generators"
                if candidate_set_complete
                else "top-level comparison only; one or more generators have not materialized every latent alternative"
            )
        ),
        "selected_candidate_id": selected.candidate_id,
        "selection_rule": (
            "admissibility, mandatory constraints, maximal policy tier, bounded deferrals within that tier, ordinal priority, then canonical candidate identifier"
        ),
        "candidate_row_schema": (
            "selection inputs plus comparison_action_sha256 and validator-checkable disposition; "
            "the selected run stores its dispatched mode, target, route, and policy labels"
        ),
        "candidates": rows,
    }
    if nested_policy_traces:
        trace["nested_policy_traces"] = {
            candidate_id: dict(nested_policy_traces[candidate_id])
            for candidate_id in sorted(nested_policy_traces)
        }
    # Fairness state is keyed by candidate identifier across the complete
    # comparison tree, so a child cannot silently alias an ancestor or sibling.
    candidate_observations_in_trace(trace)
    return dict(selected.action), trace


def trace_single_mandatory_action(
    action: Mapping[str, Any],
    *,
    domain: str,
    reason: str,
    base_policy_trace: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Attach a truthful trace when a mandatory constraint terminates planning."""

    selected, trace = select_action_candidate(
        [
            ActionCandidate(
                candidate_id="base:mandatory_constraint",
                domain=domain,
                action=action,
                ordinal_priority=0.0,
                mandatory_constraint=True,
                admissibility_reason=reason,
            )
        ],
        candidate_set_complete=False,
        nested_policy_traces=(
            {"base:mandatory_constraint": base_policy_trace}
            if base_policy_trace is not None
            else None
        ),
    )
    trace["mandatory_constraint_reason"] = reason
    selected["decision_trace"] = bind_dispatched_action(selected, trace)
    return selected
