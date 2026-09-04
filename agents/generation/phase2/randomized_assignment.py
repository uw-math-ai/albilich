from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from .decision_policy import DECISION_POLICY_SEMANTIC_SHA256
from .parallel_admission import PARALLEL_POLICY_SEMANTIC_SHA256


RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION = 1
WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION = 2
BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION = 3
WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS = frozenset({2, 3})
RANDOMIZED_ASSIGNMENT_ALGORITHM = "sha256_rejection_uniform_v1"
BLOCK_RANDOMIZED_ASSIGNMENT_ALGORITHM = "sha256_fisher_yates_rejection_v1"
BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM = (
    "sha256_registered_randomness_block_seed_v1"
)
MAX_RANDOMIZED_ASSIGNMENT_ARMS = 32
MAX_RANDOMIZED_ASSIGNMENT_LABEL_LENGTH = 160
MAX_RANDOMIZED_BLOCK_SEED = (1 << 256) - 1

_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_CERTIFICATE_FIELDS_V1 = frozenset(
    {
        "protocol_version",
        "algorithm",
        "experiment_id",
        "preregistration_sha256",
        "registration_receipt_sha256",
        "assignment_unit_id",
        "exploration_stratum",
        "entropy_source",
        "entropy_sha256",
        "arms",
        "assignment_input_sha256",
        "accepted_draw_counter",
        "accepted_draw_sha256",
        "selected_arm_id",
        "selected_policy_version",
        "assignment_probability",
        "candidate_set_sha256",
        "dispatched_action_sha256",
        "certificate_sha256",
    }
)
_CERTIFICATE_FIELDS_V2 = _CERTIFICATE_FIELDS_V1 | {
    "assignment_scope",
    "exposure_index",
}
_CERTIFICATE_FIELDS_V3 = frozenset(
    {
        "protocol_version",
        "algorithm",
        "experiment_id",
        "preregistration_sha256",
        "registration_receipt_sha256",
        "assignment_schedule_sha256",
        "randomization_receipt_sha256",
        "randomness_source",
        "randomness_event_id",
        "randomness_sha256",
        "assignment_unit_id",
        "assignment_unit_ids",
        "assignment_scope",
        "exploration_stratum",
        "problem_id",
        "problem_sha256",
        "repeat_index",
        "random_seed",
        "arms",
        "condition_order",
        "execution_order",
        "block_assignment_sha256",
        "assignment_input_sha256",
        "selected_arm_id",
        "selected_policy_version",
        "assignment_probability",
        "exposure_index",
        "candidate_set_sha256",
        "dispatched_action_sha256",
        "certificate_sha256",
    }
)
_ARM_FIELDS = frozenset(
    {
        "arm_id",
        "policy_family",
        "selection_policy_version",
        "policy_semantics_sha256",
    }
)
_POLICY_SEMANTICS = {
    "decision": DECISION_POLICY_SEMANTIC_SHA256,
    "parallel_admission": PARALLEL_POLICY_SEMANTIC_SHA256,
}


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and _LOWERCASE_SHA256.fullmatch(value) is not None


def _valid_label(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= MAX_RANDOMIZED_ASSIGNMENT_LABEL_LENGTH
        and _LABEL.fullmatch(value) is not None
    )


def randomized_condition_order(
    conditions: list[str],
    *,
    problem_id: str,
    repeat_index: int,
    random_seed: int,
) -> list[str]:
    """Return an exactly uniform block order under a uniform SHA-256 model."""

    if (
        len(conditions) < 2
        or conditions != sorted(conditions)
        or len(set(conditions)) != len(conditions)
        or type(repeat_index) is not int
        or repeat_index < 1
        or type(random_seed) is not int
        or random_seed < 0
        or random_seed > MAX_RANDOMIZED_BLOCK_SEED
        or not problem_id
    ):
        raise ValueError("invalid randomized condition-order inputs")
    order = list(conditions)
    for upper in range(len(order) - 1, 0, -1):
        range_size = 1 << 256
        modulus = upper + 1
        acceptance_limit = range_size - (range_size % modulus)
        rejection_counter = 0
        while True:
            digest = hashlib.sha256(
                json.dumps(
                    {
                        "algorithm": BLOCK_RANDOMIZED_ASSIGNMENT_ALGORITHM,
                        "conditions": conditions,
                        "problem_id": problem_id,
                        "repeat_index": repeat_index,
                        "random_seed": random_seed,
                        "upper": upper,
                        "rejection_counter": rejection_counter,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            value = int(digest, 16)
            if value < acceptance_limit:
                swap_index = value % modulus
                break
            rejection_counter += 1
        order[upper], order[swap_index] = order[swap_index], order[upper]
    return order


def randomized_block_seed(
    *,
    randomness_sha256: str,
    problem_id: str,
    repeat_index: int,
) -> int:
    """Derive an independent block seed from registered external randomness."""

    if not _valid_digest(randomness_sha256):
        raise ValueError(
            "randomness commitment must be a lowercase SHA-256 digest"
        )
    if not _valid_label(problem_id):
        raise ValueError(
            "randomized block problem identifier must be a bounded canonical label"
        )
    if type(repeat_index) is not int or repeat_index < 1:
        raise ValueError("randomized block repeat index must be a positive integer")
    digest = _canonical_sha256(
        {
            "algorithm": BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM,
            "randomness_sha256": randomness_sha256,
            "problem_id": problem_id,
            "repeat_index": repeat_index,
        }
    )
    return int(digest, 16)


def _canonical_arms(
    arms: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "arm_id": str(arm["arm_id"]),
            "policy_family": str(arm["policy_family"]),
            "selection_policy_version": int(arm["selection_policy_version"]),
            "policy_semantics_sha256": str(arm["policy_semantics_sha256"]),
        }
        for arm in sorted(arms, key=lambda item: str(item["arm_id"]))
    ]


def _assignment_input(
    *,
    protocol_version: int,
    experiment_id: str,
    preregistration_sha256: str,
    registration_receipt_sha256: str,
    assignment_unit_id: str,
    exploration_stratum: str,
    entropy_source: str,
    entropy_sha256: str,
    arms: Sequence[Mapping[str, Any]],
    assignment_scope: str | None = None,
) -> dict[str, Any]:
    value = {
        "protocol_version": protocol_version,
        "algorithm": RANDOMIZED_ASSIGNMENT_ALGORITHM,
        "experiment_id": experiment_id,
        "preregistration_sha256": preregistration_sha256,
        "registration_receipt_sha256": registration_receipt_sha256,
        "assignment_unit_id": assignment_unit_id,
        "exploration_stratum": exploration_stratum,
        "entropy_source": entropy_source,
        "entropy_sha256": entropy_sha256,
        "arms": [dict(arm) for arm in arms],
    }
    if protocol_version >= WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION:
        value["assignment_scope"] = assignment_scope
    return value


def _uniform_draw(assignment_input_sha256: str, arm_count: int) -> tuple[int, str, int]:
    """Return an exactly uniform arm index under a uniform SHA-256 model.

    Rejection sampling removes the small bias introduced by reducing the full
    SHA-256 range modulo an arm count that does not divide ``2**256``.
    """

    range_size = 1 << 256
    acceptance_limit = range_size - (range_size % arm_count)
    counter = 0
    while True:
        draw_sha256 = _canonical_sha256(
            {
                "assignment_input_sha256": assignment_input_sha256,
                "draw_counter": counter,
            }
        )
        draw = int(draw_sha256, 16)
        if draw < acceptance_limit:
            return counter, draw_sha256, draw % arm_count
        counter += 1


def randomized_policy_arm(
    arm_id: str,
    selection_policy_version: int,
    *,
    policy_family: str = "decision",
) -> dict[str, Any]:
    """Describe one immutable decision-policy arm for an experiment."""

    if not _valid_label(arm_id):
        raise ValueError(
            "randomized assignment arm identifier must be a bounded canonical label"
        )
    if type(selection_policy_version) is not int:
        raise ValueError("randomized assignment policy version must be an integer")
    semantics = _POLICY_SEMANTICS.get(policy_family)
    if semantics is None:
        raise ValueError(f"unsupported scheduler policy family: {policy_family}")
    semantics_sha256 = semantics.get(selection_policy_version)
    if semantics_sha256 is None:
        raise ValueError(
            f"unsupported decision-policy version: {selection_policy_version}"
        )
    return {
        "arm_id": arm_id,
        "policy_family": policy_family,
        "selection_policy_version": selection_policy_version,
        "policy_semantics_sha256": semantics_sha256,
    }


def randomized_arm_assignment(
    *,
    experiment_id: str,
    preregistration_sha256: str,
    registration_receipt_sha256: str,
    assignment_unit_id: str,
    exploration_stratum: str,
    entropy_source: str,
    entropy_sha256: str,
    arms: Sequence[Mapping[str, Any]],
    assignment_scope: str = "dispatch_group",
) -> dict[str, Any]:
    """Construct a reproducible, unbound uniform experimental-arm assignment.

    The caller must obtain ``entropy_sha256`` from the source named by
    ``entropy_source`` after registration.  This module verifies internal
    integrity; an archive auditor must separately authenticate the registration
    receipt and entropy source.
    """

    if assignment_scope == "dispatch_group":
        protocol_version = RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
    elif assignment_scope == "workflow":
        protocol_version = WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
    else:
        raise ValueError(
            "randomized assignment scope must be dispatch_group or workflow"
        )
    errors = _assignment_input_errors(
        experiment_id=experiment_id,
        preregistration_sha256=preregistration_sha256,
        registration_receipt_sha256=registration_receipt_sha256,
        assignment_unit_id=assignment_unit_id,
        exploration_stratum=exploration_stratum,
        entropy_source=entropy_source,
        entropy_sha256=entropy_sha256,
        arms=arms,
    )
    if errors:
        raise ValueError("; ".join(errors))
    canonical_arms = _canonical_arms(arms)
    assignment_input_sha256 = _canonical_sha256(
        _assignment_input(
            protocol_version=protocol_version,
            experiment_id=experiment_id,
            preregistration_sha256=preregistration_sha256,
            registration_receipt_sha256=registration_receipt_sha256,
            assignment_unit_id=assignment_unit_id,
            exploration_stratum=exploration_stratum,
            entropy_source=entropy_source,
            entropy_sha256=entropy_sha256,
            arms=canonical_arms,
            assignment_scope=(
                assignment_scope
                if protocol_version
                == WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
                else None
            ),
        )
    )
    counter, draw_sha256, selected_index = _uniform_draw(
        assignment_input_sha256, len(canonical_arms)
    )
    selected = canonical_arms[selected_index]
    assignment = {
        "protocol_version": protocol_version,
        "algorithm": RANDOMIZED_ASSIGNMENT_ALGORITHM,
        "experiment_id": experiment_id,
        "preregistration_sha256": preregistration_sha256,
        "registration_receipt_sha256": registration_receipt_sha256,
        "assignment_unit_id": assignment_unit_id,
        "exploration_stratum": exploration_stratum,
        "entropy_source": entropy_source,
        "entropy_sha256": entropy_sha256,
        "arms": canonical_arms,
        "assignment_input_sha256": assignment_input_sha256,
        "accepted_draw_counter": counter,
        "accepted_draw_sha256": draw_sha256,
        "selected_arm_id": selected["arm_id"],
        "selected_policy_version": selected["selection_policy_version"],
        "assignment_probability": 1.0 / len(canonical_arms),
    }
    if protocol_version in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS:
        assignment["assignment_scope"] = "workflow"
    return assignment


def randomized_block_workflow_assignments(
    *,
    experiment_id: str,
    preregistration_sha256: str,
    registration_receipt_sha256: str,
    assignment_schedule_sha256: str,
    randomization_receipt_sha256: str,
    randomness_source: str,
    randomness_event_id: str,
    randomness_sha256: str,
    problem_id: str,
    problem_sha256: str,
    repeat_index: int,
    exploration_stratum: str,
    assignment_unit_ids: Mapping[str, str],
    arms: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Construct one workflow assignment for every arm in a randomized block.

    The random variable is the complete within-block execution order. Each arm
    occurs exactly once, avoiding post-selection of independently sampled unit
    identifiers to manufacture a desired condition.
    """

    errors = _assignment_input_errors(
        experiment_id=experiment_id,
        preregistration_sha256=preregistration_sha256,
        registration_receipt_sha256=registration_receipt_sha256,
        assignment_unit_id="block-assignment-probe",
        exploration_stratum=exploration_stratum,
        entropy_source="registered-block-schedule",
        entropy_sha256=assignment_schedule_sha256,
        arms=arms,
    )
    if not _valid_label(problem_id):
        errors.append(
            "randomized block problem identifier must be a bounded canonical label"
        )
    if not _valid_digest(problem_sha256):
        errors.append(
            "randomized block problem commitment must be a lowercase SHA-256 digest"
        )
    if type(repeat_index) is not int or repeat_index < 1:
        errors.append("randomized block repeat index must be a positive integer")
    if not _valid_digest(randomization_receipt_sha256):
        errors.append(
            "randomization receipt commitment must be a lowercase SHA-256 digest"
        )
    if not _valid_label(randomness_source):
        errors.append(
            "randomness source must be a bounded canonical label"
        )
    if not _valid_label(randomness_event_id):
        errors.append(
            "randomness event identifier must be a bounded canonical label"
        )
    if not _valid_digest(randomness_sha256):
        errors.append(
            "randomness commitment must be a lowercase SHA-256 digest"
        )
    if not isinstance(assignment_unit_ids, Mapping):
        errors.append("randomized block assignment units must be an object")
        assignment_unit_ids = {}
    if errors:
        raise ValueError("; ".join(errors))
    canonical_arms = _canonical_arms(arms)
    arm_ids = [str(arm["arm_id"]) for arm in canonical_arms]
    if set(assignment_unit_ids) != set(arm_ids) or any(
        not _valid_label(assignment_unit_ids.get(arm_id))
        for arm_id in arm_ids
    ):
        raise ValueError(
            "randomized block must map every arm to one bounded assignment-unit identifier"
        )
    unit_ids = [str(assignment_unit_ids[arm_id]) for arm_id in arm_ids]
    if len(set(unit_ids)) != len(unit_ids):
        raise ValueError("randomized block assignment-unit identifiers must be unique")
    canonical_assignment_unit_ids = {
        arm_id: str(assignment_unit_ids[arm_id]) for arm_id in arm_ids
    }
    random_seed = randomized_block_seed(
        randomness_sha256=randomness_sha256,
        problem_id=problem_id,
        repeat_index=repeat_index,
    )
    condition_order = randomized_condition_order(
        arm_ids,
        problem_id=problem_id,
        repeat_index=repeat_index,
        random_seed=random_seed,
    )
    block_input = {
        "protocol_version": BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION,
        "algorithm": BLOCK_RANDOMIZED_ASSIGNMENT_ALGORITHM,
        "experiment_id": experiment_id,
        "preregistration_sha256": preregistration_sha256,
        "registration_receipt_sha256": registration_receipt_sha256,
        "assignment_schedule_sha256": assignment_schedule_sha256,
        "randomization_receipt_sha256": randomization_receipt_sha256,
        "randomness_source": randomness_source,
        "randomness_event_id": randomness_event_id,
        "randomness_sha256": randomness_sha256,
        "assignment_unit_ids": canonical_assignment_unit_ids,
        "exploration_stratum": exploration_stratum,
        "problem_id": problem_id,
        "problem_sha256": problem_sha256,
        "repeat_index": repeat_index,
        "random_seed": random_seed,
        "arms": canonical_arms,
        "condition_order": condition_order,
    }
    block_assignment_sha256 = _canonical_sha256(block_input)
    arm_by_id = {str(arm["arm_id"]): arm for arm in canonical_arms}
    assignments: list[dict[str, Any]] = []
    for execution_order, arm_id in enumerate(condition_order):
        selected = arm_by_id[arm_id]
        assignment_unit_id = str(assignment_unit_ids[arm_id])
        assignment_input_sha256 = _canonical_sha256(
            {
                "block_assignment_sha256": block_assignment_sha256,
                "assignment_unit_id": assignment_unit_id,
                "execution_order": execution_order,
                "selected_arm_id": arm_id,
            }
        )
        assignments.append(
            {
                **block_input,
                "assignment_unit_id": assignment_unit_id,
                "assignment_scope": "workflow",
                "execution_order": execution_order,
                "block_assignment_sha256": block_assignment_sha256,
                "assignment_input_sha256": assignment_input_sha256,
                "selected_arm_id": arm_id,
                "selected_policy_version": selected[
                    "selection_policy_version"
                ],
                # At a fixed execution position, each arm has marginal
                # probability 1/k under the uniform random permutation.
                "assignment_probability": 1.0 / len(canonical_arms),
            }
        )
    return assignments


def bind_randomized_assignment(
    assignment: Mapping[str, Any],
    *,
    candidate_set_sha256: str,
    dispatched_action_sha256: str,
    exposure_index: int | None = None,
) -> dict[str, Any]:
    """Bind an assignment to the exact trace and action produced by its arm."""

    bound = dict(assignment)
    bound["candidate_set_sha256"] = candidate_set_sha256
    bound["dispatched_action_sha256"] = dispatched_action_sha256
    protocol_version = bound.get("protocol_version")
    if protocol_version in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS:
        if type(exposure_index) is not int or exposure_index < 0:
            raise ValueError(
                "workflow randomized assignment requires a nonnegative exposure index"
            )
        bound["exposure_index"] = exposure_index
    elif exposure_index is not None:
        raise ValueError(
            "dispatch-group randomized assignment cannot contain an exposure index"
        )
    bound["certificate_sha256"] = _canonical_sha256(bound)
    bound_arms = bound.get("arms")
    policy_family = (
        str(bound_arms[0].get("policy_family") or "")
        if isinstance(bound_arms, list)
        and bound_arms
        and isinstance(bound_arms[0], Mapping)
        else ""
    )
    selected_policy_version = bound.get("selected_policy_version")
    errors = randomized_assignment_errors(
        bound,
        selection_policy_version=(
            selected_policy_version if policy_family == "decision" else None
        ),
        parallel_admission_policy_version=(
            selected_policy_version
            if policy_family == "parallel_admission"
            else None
        ),
    )
    if errors:
        raise ValueError("; ".join(errors))
    return bound


def workflow_assignment_from_certificate(
    certificate: Mapping[str, Any],
) -> dict[str, Any]:
    """Recover the immutable workflow assignment from one valid exposure."""

    errors = randomized_assignment_errors(certificate)
    if errors:
        raise ValueError("; ".join(errors))
    if (
        certificate.get("protocol_version")
        not in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
    ):
        raise ValueError(
            "only a workflow-scoped randomized certificate can be continued"
        )
    return {
        str(key): value
        for key, value in certificate.items()
        if key
        not in {
            "candidate_set_sha256",
            "dispatched_action_sha256",
            "exposure_index",
            "certificate_sha256",
        }
    }


def _assignment_input_errors(
    *,
    experiment_id: Any,
    preregistration_sha256: Any,
    registration_receipt_sha256: Any,
    assignment_unit_id: Any,
    exploration_stratum: Any,
    entropy_source: Any,
    entropy_sha256: Any,
    arms: Any,
) -> list[str]:
    errors: list[str] = []
    for label, value in (
        ("experiment identifier", experiment_id),
        ("assignment-unit identifier", assignment_unit_id),
        ("exploration stratum", exploration_stratum),
        ("entropy source", entropy_source),
    ):
        if not _valid_label(value):
            errors.append(
                f"randomized assignment {label} must be a bounded canonical label"
            )
    for label, value in (
        ("preregistration", preregistration_sha256),
        ("registration receipt", registration_receipt_sha256),
        ("entropy", entropy_sha256),
    ):
        if not _valid_digest(value):
            errors.append(
                f"randomized assignment {label} commitment must be a lowercase SHA-256 digest"
            )
    if not isinstance(arms, list) or not 2 <= len(arms) <= MAX_RANDOMIZED_ASSIGNMENT_ARMS:
        errors.append(
            "randomized assignment arms must be a list containing between two and "
            f"{MAX_RANDOMIZED_ASSIGNMENT_ARMS} entries"
        )
        return errors
    arm_ids: list[str] = []
    policy_versions: list[int] = []
    for arm in arms:
        if not isinstance(arm, Mapping) or set(arm) != _ARM_FIELDS:
            errors.append(
                "randomized assignment arms must contain exactly arm_id, "
                "policy_family, selection_policy_version, and policy_semantics_sha256"
            )
            continue
        arm_id = arm.get("arm_id")
        policy_family = arm.get("policy_family")
        version = arm.get("selection_policy_version")
        semantics_sha256 = arm.get("policy_semantics_sha256")
        if not _valid_label(arm_id):
            errors.append("randomized assignment arm identifiers must be bounded canonical labels")
        else:
            arm_ids.append(arm_id)
        if type(version) is not int or version <= 0:
            errors.append("randomized assignment policy versions must be positive integers")
        else:
            policy_versions.append(version)
            family_semantics = _POLICY_SEMANTICS.get(str(policy_family or ""))
            expected_semantics = (
                family_semantics.get(version)
                if family_semantics is not None
                else None
            )
            if expected_semantics is None:
                errors.append(
                    "randomized assignment arms must name a supported policy family and version"
                )
            elif semantics_sha256 != expected_semantics:
                errors.append(
                    "randomized assignment arm semantic commitment disagrees with its policy version"
                )
    if len(arm_ids) == len(arms):
        if len(set(arm_ids)) != len(arm_ids):
            errors.append("randomized assignment arm identifiers must be unique")
        if arm_ids != sorted(arm_ids):
            errors.append("randomized assignment arms must be sorted by arm identifier")
    if len(policy_versions) == len(arms) and len(set(policy_versions)) != len(
        policy_versions
    ):
        errors.append("randomized assignment arms must name distinct policy versions")
    policy_families = {
        str(arm.get("policy_family") or "")
        for arm in arms
        if isinstance(arm, Mapping)
    }
    if len(policy_families) != 1:
        errors.append("randomized assignment arms must use one policy family")
    return errors


def _block_assignment_certificate_errors(
    certificate: Mapping[str, Any],
    *,
    candidate_set_sha256: str | None,
    selection_policy_version: int | None,
    assignment_probability: float | None,
    exploration_stratum: str | None,
    dispatched_action_sha256: str | None,
    parallel_admission_policy_version: int | None,
) -> list[str]:
    """Replay a protocol-v3 registered randomized-block assignment."""

    errors: list[str] = []
    if set(certificate) != _CERTIFICATE_FIELDS_V3:
        errors.append(
            "randomized assignment certificate fields do not match protocol version 3"
        )
    if certificate.get("algorithm") != BLOCK_RANDOMIZED_ASSIGNMENT_ALGORITHM:
        errors.append("randomized block assignment algorithm is unsupported")
    if certificate.get("assignment_scope") != "workflow":
        errors.append("randomized block assignment scope must equal workflow")
    errors.extend(
        _assignment_input_errors(
            experiment_id=certificate.get("experiment_id"),
            preregistration_sha256=certificate.get("preregistration_sha256"),
            registration_receipt_sha256=certificate.get(
                "registration_receipt_sha256"
            ),
            assignment_unit_id=certificate.get("assignment_unit_id"),
            exploration_stratum=certificate.get("exploration_stratum"),
            entropy_source="registered-block-schedule",
            entropy_sha256=certificate.get("assignment_schedule_sha256"),
            arms=certificate.get("arms"),
        )
    )
    problem_id = certificate.get("problem_id")
    problem_sha256 = certificate.get("problem_sha256")
    randomization_receipt_sha256 = certificate.get(
        "randomization_receipt_sha256"
    )
    randomness_source = certificate.get("randomness_source")
    randomness_event_id = certificate.get("randomness_event_id")
    randomness_sha256 = certificate.get("randomness_sha256")
    assignment_unit_ids = certificate.get("assignment_unit_ids")
    repeat_index = certificate.get("repeat_index")
    random_seed = certificate.get("random_seed")
    execution_order = certificate.get("execution_order")
    exposure_index = certificate.get("exposure_index")
    if not _valid_label(problem_id):
        errors.append(
            "randomized block problem identifier must be a bounded canonical label"
        )
    if not _valid_digest(problem_sha256):
        errors.append(
            "randomized block problem commitment must be a lowercase SHA-256 digest"
        )
    if not _valid_digest(randomization_receipt_sha256):
        errors.append(
            "randomization receipt commitment must be a lowercase SHA-256 digest"
        )
    if not _valid_label(randomness_source):
        errors.append("randomness source must be a bounded canonical label")
    if not _valid_label(randomness_event_id):
        errors.append(
            "randomness event identifier must be a bounded canonical label"
        )
    if not _valid_digest(randomness_sha256):
        errors.append(
            "randomness commitment must be a lowercase SHA-256 digest"
        )
    if not isinstance(assignment_unit_ids, Mapping):
        errors.append("randomized block assignment units must be an object")
    if type(repeat_index) is not int or repeat_index < 1:
        errors.append("randomized block repeat index must be a positive integer")
    if (
        type(random_seed) is not int
        or random_seed < 0
        or random_seed > MAX_RANDOMIZED_BLOCK_SEED
    ):
        errors.append("randomized block seed must be an unsigned 256-bit integer")
    if type(execution_order) is not int or execution_order < 0:
        errors.append(
            "randomized block execution order must be a nonnegative integer"
        )
    if type(exposure_index) is not int or exposure_index < 0:
        errors.append(
            "workflow randomized assignment exposure index must be nonnegative"
        )
    if errors:
        return errors
    canonical_arms = _canonical_arms(certificate["arms"])
    arm_ids = [str(arm["arm_id"]) for arm in canonical_arms]
    if set(assignment_unit_ids) != set(arm_ids) or any(
        not _valid_label(assignment_unit_ids.get(arm_id))
        for arm_id in arm_ids
    ):
        errors.append(
            "randomized block must map every arm to one bounded assignment-unit identifier"
        )
        canonical_assignment_unit_ids = {}
    else:
        canonical_assignment_unit_ids = {
            arm_id: str(assignment_unit_ids[arm_id]) for arm_id in arm_ids
        }
        if len(set(canonical_assignment_unit_ids.values())) != len(arm_ids):
            errors.append(
                "randomized block assignment-unit identifiers must be unique"
            )
    try:
        expected_seed = randomized_block_seed(
            randomness_sha256=str(randomness_sha256),
            problem_id=str(problem_id),
            repeat_index=int(repeat_index),
        )
        expected_order = randomized_condition_order(
            arm_ids,
            problem_id=str(problem_id),
            repeat_index=int(repeat_index),
            random_seed=expected_seed,
        )
    except ValueError as exc:
        return [str(exc)]
    if certificate.get("condition_order") != expected_order:
        errors.append("randomized block condition order is inconsistent")
    if random_seed != expected_seed:
        errors.append(
            "randomized block seed does not match the registered randomness"
        )
    if execution_order >= len(expected_order):
        errors.append("randomized block execution order is out of range")
        selected_arm_id = ""
    else:
        selected_arm_id = expected_order[execution_order]
        if certificate.get("selected_arm_id") != selected_arm_id:
            errors.append("randomized block selected arm is inconsistent")
    block_input = {
        "protocol_version": BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION,
        "algorithm": BLOCK_RANDOMIZED_ASSIGNMENT_ALGORITHM,
        "experiment_id": certificate["experiment_id"],
        "preregistration_sha256": certificate["preregistration_sha256"],
        "registration_receipt_sha256": certificate[
            "registration_receipt_sha256"
        ],
        "assignment_schedule_sha256": certificate[
            "assignment_schedule_sha256"
        ],
        "randomization_receipt_sha256": randomization_receipt_sha256,
        "randomness_source": randomness_source,
        "randomness_event_id": randomness_event_id,
        "randomness_sha256": randomness_sha256,
        "assignment_unit_ids": canonical_assignment_unit_ids,
        "exploration_stratum": certificate["exploration_stratum"],
        "problem_id": problem_id,
        "problem_sha256": problem_sha256,
        "repeat_index": repeat_index,
        "random_seed": random_seed,
        "arms": canonical_arms,
        "condition_order": expected_order,
    }
    expected_block_sha256 = _canonical_sha256(block_input)
    if certificate.get("block_assignment_sha256") != expected_block_sha256:
        errors.append("randomized block assignment commitment is inconsistent")
    if canonical_assignment_unit_ids.get(selected_arm_id) != certificate.get(
        "assignment_unit_id"
    ):
        errors.append(
            "randomized block selected arm does not match its registered assignment unit"
        )
    expected_input_sha256 = _canonical_sha256(
        {
            "block_assignment_sha256": expected_block_sha256,
            "assignment_unit_id": certificate["assignment_unit_id"],
            "execution_order": execution_order,
            "selected_arm_id": selected_arm_id,
        }
    )
    if certificate.get("assignment_input_sha256") != expected_input_sha256:
        errors.append("randomized assignment input commitment is inconsistent")
    selected = next(
        (arm for arm in canonical_arms if arm["arm_id"] == selected_arm_id),
        None,
    )
    if selected is None or (
        type(certificate.get("selected_policy_version")) is not int
        or certificate.get("selected_policy_version")
        != selected["selection_policy_version"]
    ):
        errors.append("randomized assignment selected policy version is inconsistent")
    expected_probability = 1.0 / len(canonical_arms)
    raw_probability = certificate.get("assignment_probability")
    try:
        observed_probability = (
            float("nan")
            if isinstance(raw_probability, bool)
            else float(raw_probability)
        )
    except (TypeError, ValueError, OverflowError):
        observed_probability = float("nan")
    if not math.isfinite(observed_probability) or not math.isclose(
        observed_probability,
        expected_probability,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        errors.append("randomized assignment probability is inconsistent")
    for label in (
        "candidate_set_sha256",
        "dispatched_action_sha256",
        "block_assignment_sha256",
        "assignment_input_sha256",
    ):
        if not _valid_digest(certificate.get(label)):
            errors.append(
                f"randomized assignment {label} must be a lowercase SHA-256 digest"
            )
    certificate_sha256 = certificate.get("certificate_sha256")
    if not _valid_digest(certificate_sha256):
        errors.append(
            "randomized assignment certificate commitment must be a lowercase SHA-256 digest"
        )
    else:
        try:
            expected_certificate_sha256 = _canonical_sha256(
                {
                    key: value
                    for key, value in certificate.items()
                    if key != "certificate_sha256"
                }
            )
        except (TypeError, ValueError, OverflowError, RecursionError):
            errors.append("randomized assignment certificate is not canonical JSON")
        else:
            if certificate_sha256 != expected_certificate_sha256:
                errors.append(
                    "randomized assignment certificate commitment is inconsistent"
                )
    policy_family = str(selected.get("policy_family") or "") if selected else ""
    external_checks = (
        (
            candidate_set_sha256,
            certificate.get("candidate_set_sha256"),
            "candidate-set commitment",
        ),
        (
            selection_policy_version if policy_family == "decision" else None,
            certificate.get("selected_policy_version"),
            "selected policy version",
        ),
        (
            parallel_admission_policy_version
            if policy_family == "parallel_admission"
            else None,
            certificate.get("selected_policy_version"),
            "selected parallel-admission policy version",
        ),
        (
            exploration_stratum,
            certificate.get("exploration_stratum"),
            "exploration stratum",
        ),
        (
            dispatched_action_sha256,
            certificate.get("dispatched_action_sha256"),
            "dispatched-action commitment",
        ),
    )
    for expected, observed, label in external_checks:
        if expected is not None and expected != observed:
            errors.append(f"randomized assignment {label} disagrees with telemetry")
    if assignment_probability is not None:
        try:
            external_probability = float(assignment_probability)
        except (TypeError, ValueError, OverflowError):
            external_probability = float("nan")
        if not math.isfinite(external_probability) or not math.isclose(
            external_probability,
            expected_probability,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            errors.append(
                "randomized assignment probability disagrees with telemetry"
            )
    return errors


def randomized_assignment_errors(
    certificate: Any,
    *,
    candidate_set_sha256: str | None = None,
    selection_policy_version: int | None = None,
    assignment_probability: float | None = None,
    exploration_stratum: str | None = None,
    dispatched_action_sha256: str | None = None,
    parallel_admission_policy_version: int | None = None,
) -> list[str]:
    """Validate and replay a complete randomized-assignment certificate."""

    if not isinstance(certificate, Mapping):
        return ["randomized assignment certificate must be an object"]
    errors: list[str] = []
    protocol_version = certificate.get("protocol_version")
    if protocol_version == BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION:
        return _block_assignment_certificate_errors(
            certificate,
            candidate_set_sha256=candidate_set_sha256,
            selection_policy_version=selection_policy_version,
            assignment_probability=assignment_probability,
            exploration_stratum=exploration_stratum,
            dispatched_action_sha256=dispatched_action_sha256,
            parallel_admission_policy_version=parallel_admission_policy_version,
        )
    expected_fields = (
        {
            RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION: _CERTIFICATE_FIELDS_V1,
            WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION: _CERTIFICATE_FIELDS_V2,
        }.get(protocol_version)
        if type(protocol_version) is int
        else None
    )
    if expected_fields is None:
        errors.append("randomized assignment protocol version is unsupported")
    elif set(certificate) != expected_fields:
        errors.append(
            "randomized assignment certificate fields do not match protocol version "
            f"{protocol_version}"
        )
    if certificate.get("algorithm") != RANDOMIZED_ASSIGNMENT_ALGORITHM:
        errors.append("randomized assignment algorithm is unsupported")
    if protocol_version == WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION:
        if certificate.get("assignment_scope") != "workflow":
            errors.append(
                "workflow randomized assignment scope must equal workflow"
            )
        exposure_index = certificate.get("exposure_index")
        if type(exposure_index) is not int or exposure_index < 0:
            errors.append(
                "workflow randomized assignment exposure index must be nonnegative"
            )
    arms = certificate.get("arms")
    errors.extend(
        _assignment_input_errors(
            experiment_id=certificate.get("experiment_id"),
            preregistration_sha256=certificate.get("preregistration_sha256"),
            registration_receipt_sha256=certificate.get(
                "registration_receipt_sha256"
            ),
            assignment_unit_id=certificate.get("assignment_unit_id"),
            exploration_stratum=certificate.get("exploration_stratum"),
            entropy_source=certificate.get("entropy_source"),
            entropy_sha256=certificate.get("entropy_sha256"),
            arms=arms,
        )
    )
    if errors:
        return errors
    canonical_arms = _canonical_arms(arms)
    expected_input_sha256 = _canonical_sha256(
        _assignment_input(
            protocol_version=int(protocol_version),
            experiment_id=certificate["experiment_id"],
            preregistration_sha256=certificate["preregistration_sha256"],
            registration_receipt_sha256=certificate["registration_receipt_sha256"],
            assignment_unit_id=certificate["assignment_unit_id"],
            exploration_stratum=certificate["exploration_stratum"],
            entropy_source=certificate["entropy_source"],
            entropy_sha256=certificate["entropy_sha256"],
            arms=canonical_arms,
            assignment_scope=(
                str(certificate.get("assignment_scope") or "")
                if protocol_version
                == WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
                else None
            ),
        )
    )
    if certificate.get("assignment_input_sha256") != expected_input_sha256:
        errors.append("randomized assignment input commitment is inconsistent")
    expected_counter, expected_draw_sha256, selected_index = _uniform_draw(
        expected_input_sha256, len(canonical_arms)
    )
    if (
        type(certificate.get("accepted_draw_counter")) is not int
        or certificate.get("accepted_draw_counter") != expected_counter
    ):
        errors.append("randomized assignment accepted draw counter is inconsistent")
    if certificate.get("accepted_draw_sha256") != expected_draw_sha256:
        errors.append("randomized assignment accepted draw commitment is inconsistent")
    selected = canonical_arms[selected_index]
    if certificate.get("selected_arm_id") != selected["arm_id"]:
        errors.append("randomized assignment selected arm is inconsistent")
    if (
        type(certificate.get("selected_policy_version")) is not int
        or certificate.get("selected_policy_version")
        != selected["selection_policy_version"]
    ):
        errors.append("randomized assignment selected policy version is inconsistent")
    raw_probability = certificate.get("assignment_probability")
    if isinstance(raw_probability, bool):
        observed_probability = float("nan")
    else:
        try:
            observed_probability = float(raw_probability)
        except (TypeError, ValueError, OverflowError):
            observed_probability = float("nan")
    expected_probability = 1.0 / len(canonical_arms)
    if not math.isfinite(observed_probability) or not math.isclose(
        observed_probability,
        expected_probability,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        errors.append("randomized assignment probability is inconsistent")
    for label in ("candidate_set_sha256", "dispatched_action_sha256"):
        if not _valid_digest(certificate.get(label)):
            errors.append(
                f"randomized assignment {label} must be a lowercase SHA-256 digest"
            )
    certificate_sha256 = certificate.get("certificate_sha256")
    if not _valid_digest(certificate_sha256):
        errors.append(
            "randomized assignment certificate commitment must be a lowercase SHA-256 digest"
        )
    else:
        try:
            expected_certificate_sha256 = _canonical_sha256(
                {
                    key: value
                    for key, value in certificate.items()
                    if key != "certificate_sha256"
                }
            )
        except (TypeError, ValueError, OverflowError, RecursionError):
            errors.append("randomized assignment certificate is not canonical JSON")
        else:
            if certificate_sha256 != expected_certificate_sha256:
                errors.append(
                    "randomized assignment certificate commitment is inconsistent"
                )
    policy_family = str(selected.get("policy_family") or "")
    expected_decision_version = (
        selection_policy_version if policy_family == "decision" else None
    )
    expected_parallel_version = (
        parallel_admission_policy_version
        if policy_family == "parallel_admission"
        else None
    )
    external_checks = (
        (
            candidate_set_sha256,
            certificate.get("candidate_set_sha256"),
            "candidate-set commitment",
        ),
        (
            expected_decision_version,
            certificate.get("selected_policy_version"),
            "selected policy version",
        ),
        (
            expected_parallel_version,
            certificate.get("selected_policy_version"),
            "selected parallel-admission policy version",
        ),
        (
            exploration_stratum,
            certificate.get("exploration_stratum"),
            "exploration stratum",
        ),
        (
            dispatched_action_sha256,
            certificate.get("dispatched_action_sha256"),
            "dispatched-action commitment",
        ),
    )
    for expected, observed, label in external_checks:
        if expected is not None and expected != observed:
            errors.append(f"randomized assignment {label} disagrees with telemetry")
    if assignment_probability is not None:
        try:
            external_probability = float(assignment_probability)
        except (TypeError, ValueError, OverflowError):
            external_probability = float("nan")
        if not math.isfinite(external_probability) or not math.isclose(
            external_probability,
            expected_probability,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            errors.append(
                "randomized assignment probability disagrees with telemetry"
            )
    return errors


def randomized_assignment_metadata(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Return validated scalar telemetry for a trace with an assignment."""

    trace_policy_version = trace.get("decision_policy_version")
    if type(trace_policy_version) is not int or trace_policy_version <= 0:
        raise ValueError(
            "randomized scheduler trace requires a positive decision-policy version"
        )
    certificate = trace.get("randomized_assignment")
    wave = trace.get("parallel_wave_admission")
    certificate_arms = (
        certificate.get("arms") if isinstance(certificate, Mapping) else None
    )
    policy_family = (
        str(certificate_arms[0].get("policy_family") or "")
        if isinstance(certificate_arms, list)
        and certificate_arms
        and isinstance(certificate_arms[0], Mapping)
        else ""
    )
    errors = randomized_assignment_errors(
        certificate,
        candidate_set_sha256=str(trace.get("candidate_set_sha256") or ""),
        selection_policy_version=(
            trace_policy_version
            if type(trace_policy_version) is int
            else -1
        ),
        dispatched_action_sha256=str(
            trace.get("dispatched_action_sha256") or ""
        ),
        parallel_admission_policy_version=(
            wave.get("policy_version")
            if policy_family == "parallel_admission"
            and isinstance(wave, Mapping)
            and type(wave.get("policy_version")) is int
            else -1 if policy_family == "parallel_admission" else None
        ),
    )
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "selection_design": "randomized",
        "assignment_probability": float(certificate["assignment_probability"]),
        "exploration_stratum": str(certificate["exploration_stratum"]),
        "candidate_set_hash": str(certificate["candidate_set_sha256"]),
        "selection_policy_version": trace_policy_version,
        "assignment_scope": str(
            certificate.get("assignment_scope") or "dispatch_group"
        ),
        "exposure_index": (
            int(certificate["exposure_index"])
            if certificate.get("protocol_version")
            in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
            else None
        ),
    }


def randomized_assignment_design_sha256(certificate: Any) -> str:
    """Return the fixed-design commitment shared by one experiment cohort."""

    errors = randomized_assignment_errors(certificate)
    if errors:
        raise ValueError("; ".join(errors))
    if (
        certificate["protocol_version"]
        == BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
    ):
        return _canonical_sha256(
            {
                "protocol_version": certificate["protocol_version"],
                "algorithm": certificate["algorithm"],
                "preregistration_sha256": certificate[
                    "preregistration_sha256"
                ],
                "registration_receipt_sha256": certificate[
                    "registration_receipt_sha256"
                ],
                "assignment_schedule_sha256": certificate[
                    "assignment_schedule_sha256"
                ],
                "randomization_receipt_sha256": certificate[
                    "randomization_receipt_sha256"
                ],
                "randomness_source": certificate["randomness_source"],
                "randomness_event_id": certificate["randomness_event_id"],
                "randomness_sha256": certificate["randomness_sha256"],
                "arms": certificate["arms"],
                "assignment_scope": certificate["assignment_scope"],
            }
        )
    design = {
            "protocol_version": certificate["protocol_version"],
            "algorithm": certificate["algorithm"],
            "preregistration_sha256": certificate["preregistration_sha256"],
            "registration_receipt_sha256": certificate[
                "registration_receipt_sha256"
            ],
            "entropy_source": certificate["entropy_source"],
            "entropy_sha256": certificate["entropy_sha256"],
            "arms": certificate["arms"],
    }
    if (
        certificate["protocol_version"]
        == WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
    ):
        design["assignment_scope"] = certificate["assignment_scope"]
    return _canonical_sha256(design)


def randomized_assignment_cohort_errors(
    certificates: Sequence[Any],
) -> list[str]:
    """Validate uniqueness and fixed design within each named experiment."""

    errors: list[str] = []
    exposures: set[tuple[str, str, int]] = set()
    design_by_experiment: dict[str, str] = {}
    assignment_by_unit: dict[tuple[str, str], str] = {}
    exposure_indices_by_unit: dict[tuple[str, str], set[int]] = {}
    for index, certificate in enumerate(certificates):
        certificate_errors = randomized_assignment_errors(certificate)
        if certificate_errors:
            errors.append(
                f"randomized assignment certificate {index} is invalid"
            )
            continue
        experiment_id = str(certificate["experiment_id"])
        assignment_unit_id = str(certificate["assignment_unit_id"])
        unit = (experiment_id, assignment_unit_id)
        protocol_version = int(certificate["protocol_version"])
        exposure_index = (
            int(certificate["exposure_index"])
            if protocol_version
            in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
            else -1
        )
        exposure = (*unit, exposure_index)
        if exposure in exposures:
            errors.append(
                "randomized assignment exposure is duplicated within experiment "
                f"{experiment_id}: {assignment_unit_id}/{exposure_index}"
            )
        exposures.add(exposure)
        prior_assignment = assignment_by_unit.setdefault(
            unit, str(certificate["assignment_input_sha256"])
        )
        if prior_assignment != certificate["assignment_input_sha256"]:
            errors.append(
                "randomized assignment changes within experimental unit "
                f"{experiment_id}: {assignment_unit_id}"
            )
        if protocol_version in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS:
            exposure_indices_by_unit.setdefault(unit, set()).add(exposure_index)
        design_sha256 = randomized_assignment_design_sha256(certificate)
        prior_design = design_by_experiment.setdefault(
            experiment_id, design_sha256
        )
        if prior_design != design_sha256:
            errors.append(
                "randomized assignment design changes within experiment "
                f"{experiment_id}"
            )
    for (experiment_id, assignment_unit_id), indices in (
        exposure_indices_by_unit.items()
    ):
        if indices != set(range(max(indices) + 1)):
            errors.append(
                "workflow randomized assignment exposures are not contiguous from zero "
                f"within experimental unit {experiment_id}: {assignment_unit_id}"
            )
    return errors


def randomized_block_assignment_cohort_errors(
    certificates: Sequence[Any],
) -> list[str]:
    """Validate complete randomized blocks across archived workflow stores."""

    if not certificates:
        return ["randomized block archive contains no assignment certificates"]
    errors = randomized_assignment_cohort_errors(certificates)
    representatives: dict[tuple[str, str], Mapping[str, Any]] = {}
    blocks: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for index, certificate in enumerate(certificates):
        if not isinstance(certificate, Mapping) or (
            certificate.get("protocol_version")
            != BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
        ):
            errors.append(
                f"randomized block certificate {index} does not use protocol version 3"
            )
            continue
        if randomized_assignment_errors(certificate):
            continue
        unit = (
            str(certificate["experiment_id"]),
            str(certificate["assignment_unit_id"]),
        )
        if int(certificate["exposure_index"]) == 0:
            if unit in representatives:
                errors.append(
                    "randomized block assignment unit has multiple initial exposures "
                    f"{unit[0]}: {unit[1]}"
                )
            representatives[unit] = certificate
    for certificate in representatives.values():
        block = (
            str(certificate["experiment_id"]),
            str(certificate["block_assignment_sha256"]),
        )
        blocks.setdefault(block, []).append(certificate)
    for (experiment_id, block_sha256), members in blocks.items():
        first = members[0]
        condition_order = list(first["condition_order"])
        expected_positions = set(range(len(condition_order)))
        observed_positions = {
            int(member["execution_order"]) for member in members
        }
        observed_arms = {
            str(member["selected_arm_id"]) for member in members
        }
        if len(members) != len(condition_order):
            errors.append(
                "randomized block does not contain exactly one workflow for every arm "
                f"{experiment_id}: {block_sha256}"
            )
        if observed_positions != expected_positions:
            errors.append(
                "randomized block execution positions are incomplete or duplicated "
                f"{experiment_id}: {block_sha256}"
            )
        if observed_arms != set(condition_order):
            errors.append(
                "randomized block arms are incomplete or duplicated "
                f"{experiment_id}: {block_sha256}"
            )
        invariant_fields = (
            "problem_id",
            "problem_sha256",
            "repeat_index",
            "random_seed",
            "randomization_receipt_sha256",
            "randomness_source",
            "randomness_event_id",
            "randomness_sha256",
            "assignment_unit_ids",
            "condition_order",
            "arms",
            "assignment_schedule_sha256",
        )
        if any(
            any(member.get(field) != first.get(field) for field in invariant_fields)
            for member in members[1:]
        ):
            errors.append(
                "randomized block workflows disagree on their registered block inputs "
                f"{experiment_id}: {block_sha256}"
            )
    return errors
