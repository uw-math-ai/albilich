from __future__ import annotations

"""Versioned routing contract for scheduler actions.

The scheduler still represents actions as JSON-like mappings, but every mode
and its cross-layer classification is declared once here.  Construction,
selection, budgeting, role assignment, dispatch, and telemetry can therefore
share one exhaustive vocabulary while migration toward a fully typed action
sum proceeds incrementally.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping


SCHEDULER_ACTION_CONTRACT_VERSION = 5
SUPPORTED_SCHEDULER_ACTION_CONTRACT_VERSIONS = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class ActionModeSpec:
    mode: str
    executable: bool
    budget_class: str
    role_class: str


ACTION_MODE_SPECS_V1: Mapping[str, ActionModeSpec] = MappingProxyType(
    {
        "prove": ActionModeSpec("prove", True, "research", "adaptive_proof"),
        "refute": ActionModeSpec("refute", True, "research", "adversarial"),
        "validate_counterexample": ActionModeSpec(
            "validate_counterexample",
            True,
            "verification",
            "counterexample_validation",
        ),
        "reduce": ActionModeSpec("reduce", True, "research", "adaptive_research"),
        "weaken": ActionModeSpec("weaken", True, "research", "adaptive_research"),
        "strengthen": ActionModeSpec(
            "strengthen", True, "research", "adaptive_research"
        ),
        "retrieve": ActionModeSpec("retrieve", True, "research", "literature"),
        "synthesize_sources": ActionModeSpec(
            "synthesize_sources", True, "management", "literature"
        ),
        "audit_definitions": ActionModeSpec(
            "audit_definitions", True, "management", "literature"
        ),
        "triage_routes": ActionModeSpec(
            "triage_routes", True, "management", "advisor"
        ),
        "regulate_decomposition": ActionModeSpec(
            "regulate_decomposition", True, "management", "advisor"
        ),
        "integrate": ActionModeSpec(
            "integrate", True, "verification", "integration"
        ),
        "formalize": ActionModeSpec("formalize", True, "verification", "formal"),
        "write": ActionModeSpec("write", True, "verification", "writing"),
        "review_writing": ActionModeSpec(
            "review_writing", True, "verification", "writing_review"
        ),
        "await_human": ActionModeSpec(
            "await_human", False, "terminal", "terminal"
        ),
        "stop_with_partial_results": ActionModeSpec(
            "stop_with_partial_results", False, "terminal", "terminal"
        ),
        "stop_solved": ActionModeSpec(
            "stop_solved", False, "terminal", "terminal"
        ),
    }
)

# Version 2 preserves the v1 mode vocabulary and adds a committed, pure
# action-to-role routing function.  Keep a separate snapshot so a future mode
# change can add v3 without silently redefining replayed v1/v2 semantics.
ACTION_MODE_SPECS_V2: Mapping[str, ActionModeSpec] = MappingProxyType(
    dict(ACTION_MODE_SPECS_V1)
)
ACTION_MODE_SPECS_V3: Mapping[str, ActionModeSpec] = MappingProxyType(
    dict(ACTION_MODE_SPECS_V2)
)
ACTION_MODE_SPECS_V4: Mapping[str, ActionModeSpec] = MappingProxyType(
    dict(ACTION_MODE_SPECS_V3)
)
ACTION_MODE_SPECS_V5: Mapping[str, ActionModeSpec] = MappingProxyType(
    dict(ACTION_MODE_SPECS_V4)
)
ACTION_MODE_SPECS_BY_VERSION: Mapping[int, Mapping[str, ActionModeSpec]] = (
    MappingProxyType(
        {
            1: ACTION_MODE_SPECS_V1,
            2: ACTION_MODE_SPECS_V2,
            3: ACTION_MODE_SPECS_V3,
            4: ACTION_MODE_SPECS_V4,
            5: ACTION_MODE_SPECS_V5,
        }
    )
)
ACTION_MODE_SPECS = ACTION_MODE_SPECS_BY_VERSION[
    SCHEDULER_ACTION_CONTRACT_VERSION
]

RUN_MODES = frozenset(ACTION_MODE_SPECS)
EXECUTABLE_RUN_MODES = frozenset(
    mode for mode, spec in ACTION_MODE_SPECS.items() if spec.executable
)
VERIFICATION_BUDGET_MODES = frozenset(
    mode
    for mode, spec in ACTION_MODE_SPECS.items()
    if spec.budget_class == "verification"
)
RESEARCH_MANAGEMENT_MODES = frozenset(
    mode for mode, spec in ACTION_MODE_SPECS.items() if spec.budget_class == "management"
)
LITERATURE_SEARCH_MODES = frozenset(
    mode for mode, spec in ACTION_MODE_SPECS.items() if spec.role_class == "literature"
)


def scheduler_action_contract_errors(
    action: Mapping[str, Any],
    *,
    require_target: bool = False,
    executable: bool = False,
) -> list[str]:
    """Validate the routing fields shared by every scheduler layer."""

    return _scheduler_action_contract_errors(
        action,
        specs=ACTION_MODE_SPECS,
        require_target=require_target,
        executable=executable,
    )


def _scheduler_action_contract_errors(
    action: Mapping[str, Any],
    *,
    specs: Mapping[str, ActionModeSpec],
    require_target: bool,
    executable: bool,
) -> list[str]:
    """Version-parametric implementation used by semantic replay vectors."""

    if not isinstance(action, Mapping):
        return ["scheduler action must be an object"]
    errors: list[str] = []
    mode = action.get("mode")
    if not isinstance(mode, str) or mode not in specs:
        errors.append("scheduler action mode is not supported")
    elif mode != mode.strip():
        errors.append("scheduler action mode is not canonical")
    elif executable and not specs[mode].executable:
        errors.append("scheduler action mode is not executable")

    target = action.get("target_id")
    if target is None and not require_target:
        pass
    elif not isinstance(target, str) or not target.strip():
        errors.append("scheduler action target must be a nonempty string")
    elif target != target.strip():
        errors.append("scheduler action target is not canonical")

    route = action.get("route_id")
    if route is not None:
        if not isinstance(route, str):
            errors.append("scheduler action route must be a string")
        elif route != route.strip():
            errors.append("scheduler action route is not canonical")
    return errors


def scheduler_actor_role_for_action(action: Mapping[str, Any]) -> str:
    """Resolve the execution role from the current action contract.

    Availability policy (for example, whether the optional advisor is
    enabled) remains a scheduler gate.  This function is deliberately pure so
    dispatch persistence can independently reproduce role assignment.
    """

    return _scheduler_actor_role_for_action(action, specs=ACTION_MODE_SPECS)


def scheduler_dispatch_action_errors(action: Mapping[str, Any]) -> list[str]:
    """Validate routing and resource allocation for a durable dispatch."""

    errors = _scheduler_action_contract_errors(
        action,
        specs=ACTION_MODE_SPECS,
        require_target=True,
        executable=True,
    )
    errors.extend(
        _scheduler_resource_allocation_errors(
            action,
            specs=ACTION_MODE_SPECS,
            contract_version=SCHEDULER_ACTION_CONTRACT_VERSION,
        )
    )
    return errors


def _scheduler_resource_allocation_errors(
    action: Mapping[str, Any],
    *,
    specs: Mapping[str, ActionModeSpec],
    contract_version: int,
) -> list[str]:
    """Check the arithmetic allocation invariant for one executable action."""

    allocation = action.get("budget")
    if not isinstance(allocation, Mapping):
        return ["scheduler dispatch resource allocation must be an object"]
    errors: list[str] = []
    if allocation.get("allowed") is not True:
        errors.append("scheduler dispatch resource allocation must be allowed")
    integer_fields = (
        "requested_tokens",
        "spendable_tokens",
        "remaining_token_budget",
        "reserved_verification_budget",
    )
    values: dict[str, int] = {}
    for field in integer_fields:
        value = allocation.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(
                f"scheduler dispatch resource allocation {field} must be a nonnegative integer"
            )
        else:
            values[field] = value
    reason = allocation.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append(
            "scheduler dispatch resource allocation reason must be a nonempty string"
        )
    policy = allocation.get("policy")
    if policy is not None and (
        not isinstance(policy, str) or not policy.strip()
    ):
        errors.append(
            "scheduler dispatch resource allocation policy must be a nonempty string"
        )
    request_limit = allocation.get("request_limit_tokens")
    if contract_version >= 5:
        if (
            isinstance(request_limit, bool)
            or not isinstance(request_limit, int)
            or request_limit <= 0
        ):
            errors.append(
                "scheduler dispatch resource allocation request_limit_tokens "
                "must be a positive integer"
            )
    if len(values) != len(integer_fields):
        return errors
    requested = values["requested_tokens"]
    spendable = values["spendable_tokens"]
    remaining = values["remaining_token_budget"]
    reserve = values["reserved_verification_budget"]
    if reserve > remaining:
        errors.append(
            "scheduler dispatch verification reserve exceeds the remaining allocation"
        )
    if requested <= 0 or requested > spendable or spendable > remaining:
        errors.append(
            "scheduler dispatch resource allocation must satisfy 0 < requested <= spendable <= remaining"
        )
    if contract_version >= 5 and isinstance(request_limit, int) and not isinstance(
        request_limit, bool
    ) and requested > request_limit:
        errors.append(
            "scheduler dispatch requested allocation exceeds its request limit"
        )
    mode = action.get("mode")
    spec = specs.get(mode) if isinstance(mode, str) else None
    if spec is not None:
        budget_class = (
            _scheduler_budget_class_for_action(action, specs=specs)
            if contract_version >= 4
            else spec.budget_class
        )
        expected_spendable = (
            remaining
            if budget_class == "verification"
            else max(0, remaining - reserve)
        )
        if spendable != expected_spendable:
            errors.append(
                "scheduler dispatch spendable allocation disagrees with its mode budget class"
            )
    return errors


def scheduler_budget_class_for_action(action: Mapping[str, Any]) -> str:
    """Resolve an action's resource class, including polymorphic proof work."""

    return _scheduler_budget_class_for_action(action, specs=ACTION_MODE_SPECS)


def _scheduler_budget_class_for_action(
    action: Mapping[str, Any],
    *,
    specs: Mapping[str, ActionModeSpec],
) -> str:
    mode = action.get("mode")
    if not isinstance(mode, str) or mode not in specs:
        raise ValueError(
            "cannot resolve a budget class for an unsupported scheduler mode"
        )
    # ``prove`` represents both constructive research and strict checking.
    # Role resolution has the full action discriminant needed to distinguish
    # them, whereas a mode-only lookup does not.
    if _scheduler_actor_role_for_action(action, specs=specs) == (
        "strict_informal_verifier"
    ):
        return "verification"
    return specs[mode].budget_class


def _scheduler_actor_role_for_action(
    action: Mapping[str, Any],
    *,
    specs: Mapping[str, ActionModeSpec],
) -> str:
    """Version-parametric role resolver used by semantic replay vectors."""

    mode = action.get("mode")
    if not isinstance(mode, str) or mode not in specs:
        raise ValueError("cannot resolve an actor role for an unsupported mode")
    if action.get("context_retrieval"):
        requested_role = action.get("requested_actor_role")
        if requested_role in {
            "researcher",
            "adversarial_reviewer",
            "literature_researcher",
            "phd_advisor",
            "advisor",
        }:
            return str(requested_role)
    role_class = specs[mode].role_class
    fixed_roles = {
        "integration": "integration_verifier",
        "formal": "formal_backend",
        "counterexample_validation": "counterexample_validator",
        "literature": "literature_researcher",
        "advisor": "phd_advisor",
        "adversarial": "adversarial_reviewer",
        "writing": "writer",
    }
    if role_class in fixed_roles:
        return fixed_roles[role_class]
    if role_class == "writing_review":
        return "referee" if action.get("publication_referee") else "writing_critic"
    if role_class == "adaptive_proof" and (
        action.get("route_id")
        or action.get("citation_certification_required")
        or action.get("citation_triage_required")
        or action.get("paper_audit_document_review_required")
    ):
        return "strict_informal_verifier"
    if role_class == "adaptive_research" and action.get("debt_id"):
        if (
            action.get("route_id")
            or action.get("proof_repair_required")
            or action.get("research_diagnostic_required")
        ):
            return "researcher"
        return "phd_advisor"
    return "researcher"


def scheduler_action_contract_semantic_sha256(version: int) -> str:
    """Hash the declared modes and observable routing validation behavior."""

    if version not in SUPPORTED_SCHEDULER_ACTION_CONTRACT_VERSIONS:
        raise ValueError(f"unsupported scheduler action contract {version}")
    specs = ACTION_MODE_SPECS_BY_VERSION[version]
    scenarios = (
        ("valid", {"mode": "reduce", "target_id": "root", "route_id": ""}, True, True),
        ("unknown_mode", {"mode": "unknown", "target_id": "root"}, True, True),
        ("terminal_dispatch", {"mode": "stop_solved", "target_id": "root"}, True, True),
        ("missing_abstract_target", {"mode": "prove"}, False, False),
        ("missing_dispatch_target", {"mode": "prove"}, True, True),
        ("noncanonical_target", {"mode": "prove", "target_id": " root "}, True, True),
        ("nonstring_route", {"mode": "prove", "target_id": "root", "route_id": 1}, True, True),
        (
            "decomposition_management",
            {"mode": "regulate_decomposition", "target_id": "root"},
            True,
            True,
        ),
    )
    payload = {
        "specs": [
            asdict(specs[mode]) for mode in sorted(specs)
        ],
        "derived": {
            "run_modes": sorted(specs),
            "executable_run_modes": sorted(
                mode for mode, spec in specs.items() if spec.executable
            ),
            "verification_budget_modes": sorted(
                mode
                for mode, spec in specs.items()
                if spec.budget_class == "verification"
            ),
            "research_management_modes": sorted(
                mode
                for mode, spec in specs.items()
                if spec.budget_class == "management"
            ),
            "literature_search_modes": sorted(
                mode
                for mode, spec in specs.items()
                if spec.role_class == "literature"
            ),
        },
        "scenarios": [
            {
                "name": name,
                "errors": _scheduler_action_contract_errors(
                    action,
                    specs=specs,
                    require_target=require_target,
                    executable=must_execute,
                ),
            }
            for name, action, require_target, must_execute in scenarios
        ],
    }
    if version >= 2:
        role_scenarios = (
            ("research", {"mode": "reduce"}),
            ("research_advisor", {"mode": "reduce", "debt_id": "d"}),
            (
                "research_repair",
                {"mode": "reduce", "debt_id": "d", "proof_repair_required": True},
            ),
            ("proof", {"mode": "prove"}),
            ("proof_route", {"mode": "prove", "route_id": "r"}),
            ("literature", {"mode": "retrieve"}),
            ("advisor", {"mode": "triage_routes"}),
            ("integration", {"mode": "integrate"}),
            ("formal", {"mode": "formalize"}),
            ("writing", {"mode": "write"}),
            ("writing_review", {"mode": "review_writing"}),
            (
                "publication_review",
                {"mode": "review_writing", "publication_referee": True},
            ),
            (
                "context_override",
                {
                    "mode": "reduce",
                    "context_retrieval": True,
                    "requested_actor_role": "literature_researcher",
                },
            ),
        )
        payload["actor_role_scenarios"] = [
            {
                "name": name,
                "actor_role": _scheduler_actor_role_for_action(
                    action, specs=specs
                ),
            }
            for name, action in role_scenarios
        ]
    if version >= 3:
        allocation_scenarios = (
            (
                "valid_research",
                {
                    "mode": "reduce",
                    "target_id": "root",
                    "budget": {
                        "allowed": True,
                        "requested_tokens": 40,
                        "spendable_tokens": 80,
                        "remaining_token_budget": 100,
                        "reserved_verification_budget": 20,
                        "reason": "ok",
                    },
                },
            ),
            (
                "valid_verification",
                {
                    "mode": "formalize",
                    "target_id": "claim",
                    "budget": {
                        "allowed": True,
                        "requested_tokens": 90,
                        "spendable_tokens": 100,
                        "remaining_token_budget": 100,
                        "reserved_verification_budget": 20,
                        "reason": "ok",
                    },
                },
            ),
            ("missing_allocation", {"mode": "reduce", "target_id": "root"}),
            (
                "overallocated",
                {
                    "mode": "reduce",
                    "target_id": "root",
                    "budget": {
                        "allowed": True,
                        "requested_tokens": 90,
                        "spendable_tokens": 80,
                        "remaining_token_budget": 100,
                        "reserved_verification_budget": 20,
                        "reason": "ok",
                    },
                },
            ),
            (
                "wrong_budget_class",
                {
                    "mode": "formalize",
                    "target_id": "claim",
                    "budget": {
                        "allowed": True,
                        "requested_tokens": 70,
                        "spendable_tokens": 80,
                        "remaining_token_budget": 100,
                        "reserved_verification_budget": 20,
                        "reason": "ok",
                    },
                },
            ),
        )
        versioned_allocation_scenarios = allocation_scenarios
        if version >= 5:
            versioned_allocation_scenarios = tuple(
                (
                    name,
                    {
                        **action,
                        **(
                            {
                                "budget": {
                                    **action["budget"],
                                    "request_limit_tokens": int(
                                        action["budget"]["requested_tokens"]
                                    ),
                                }
                            }
                            if isinstance(action.get("budget"), Mapping)
                            else {}
                        ),
                    },
                )
                for name, action in allocation_scenarios
            )
        payload["resource_allocation_scenarios"] = [
            {
                "name": name,
                "errors": [
                    *_scheduler_action_contract_errors(
                        action,
                        specs=specs,
                        require_target=True,
                        executable=True,
                    ),
                    *_scheduler_resource_allocation_errors(
                        action,
                        specs=specs,
                        contract_version=version,
                    ),
                ],
            }
            for name, action in versioned_allocation_scenarios
        ]
    if version >= 4:
        budget_class_scenarios = (
            ("direct_proof", {"mode": "prove", "target_id": "root"}),
            (
                "strict_route_verification",
                {"mode": "prove", "target_id": "claim", "route_id": "route"},
            ),
            (
                "citation_verification",
                {
                    "mode": "prove",
                    "target_id": "claim",
                    "citation_certification_required": True,
                },
            ),
            ("formal_verification", {"mode": "formalize", "target_id": "claim"}),
            ("research_reduction", {"mode": "reduce", "target_id": "claim"}),
        )
        payload["budget_class_scenarios"] = [
            {
                "name": name,
                "budget_class": _scheduler_budget_class_for_action(
                    action, specs=specs
                ),
            }
            for name, action in budget_class_scenarios
        ]
    if version >= 5:
        request_limit_scenarios = (
            (
                "valid_request_limit",
                {
                    "mode": "reduce",
                    "target_id": "root",
                    "budget": {
                        "allowed": True,
                        "requested_tokens": 40,
                        "request_limit_tokens": 60,
                        "spendable_tokens": 80,
                        "remaining_token_budget": 100,
                        "reserved_verification_budget": 20,
                        "reason": "ok",
                    },
                },
            ),
            (
                "missing_request_limit",
                {
                    "mode": "reduce",
                    "target_id": "root",
                    "budget": {
                        "allowed": True,
                        "requested_tokens": 40,
                        "spendable_tokens": 80,
                        "remaining_token_budget": 100,
                        "reserved_verification_budget": 20,
                        "reason": "ok",
                    },
                },
            ),
            (
                "request_exceeds_limit",
                {
                    "mode": "reduce",
                    "target_id": "root",
                    "budget": {
                        "allowed": True,
                        "requested_tokens": 40,
                        "request_limit_tokens": 20,
                        "spendable_tokens": 80,
                        "remaining_token_budget": 100,
                        "reserved_verification_budget": 20,
                        "reason": "ok",
                    },
                },
            ),
        )
        payload["request_limit_scenarios"] = [
            {
                "name": name,
                "errors": [
                    *_scheduler_action_contract_errors(
                        action,
                        specs=specs,
                        require_target=True,
                        executable=True,
                    ),
                    *_scheduler_resource_allocation_errors(
                        action,
                        specs=specs,
                        contract_version=version,
                    ),
                ],
            }
            for name, action in request_limit_scenarios
        ]
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


# Filled from the canonical vector above; published entries are immutable.
SCHEDULER_ACTION_CONTRACT_SHA256: Mapping[int, str] = MappingProxyType(
    {
        1: "78cb9fb65eae63f0fc56004eca19c66a0e00a99cee48c2906c0a5fddc4e2faa6",
        2: "3741bc100c1e89c1f67afb0e30425e22721c81cbcecf5d77cfbc6cde5b3cfd43",
        3: "2032afb56f74aca4a14abe3cc32b1d738a7be8860519daefccd3955c7162f597",
        4: "793ada1bfa706de81709e0fbcd0339b0905ca85560c613ec40dd2a603893ff8b",
        5: "72f5dde702634e7f538cef81d3e3d1ba598035289532d6fae1f68d9751c29840",
    }
)


def scheduler_action_contract_semantic_errors() -> list[str]:
    errors: list[str] = []
    supported = set(SUPPORTED_SCHEDULER_ACTION_CONTRACT_VERSIONS)
    committed = set(SCHEDULER_ACTION_CONTRACT_SHA256)
    if supported != committed:
        errors.append(
            "scheduler action commitments must cover every supported version exactly"
        )
    for version in sorted(supported & committed):
        if scheduler_action_contract_semantic_sha256(version) != (
            SCHEDULER_ACTION_CONTRACT_SHA256[version]
        ):
            errors.append(
                f"scheduler action contract v{version} changed without a new version"
            )
    return errors


def scheduler_action_contract_trace_binding() -> dict[str, Any]:
    """Return the exact semantic identity persisted by new scheduler traces."""

    return {
        "scheduler_action_contract_version": SCHEDULER_ACTION_CONTRACT_VERSION,
        "scheduler_action_contract_sha256": SCHEDULER_ACTION_CONTRACT_SHA256[
            SCHEDULER_ACTION_CONTRACT_VERSION
        ],
    }


def scheduler_action_contract_trace_errors(
    trace: Mapping[str, Any],
    *,
    required: bool = False,
) -> list[str]:
    """Validate an action-semantics binding while accepting legacy absence.

    Old decision traces predate this cross-layer binding and remain replayable.
    Every new deterministic persistence operation passes ``required=True``.
    """

    if not isinstance(trace, Mapping):
        return ["scheduler action-contract trace must be an object"]
    version_present = "scheduler_action_contract_version" in trace
    digest_present = "scheduler_action_contract_sha256" in trace
    if not version_present and not digest_present:
        return (
            ["decision trace does not identify its scheduler action contract"]
            if required
            else []
        )
    errors: list[str] = []
    if version_present != digest_present:
        errors.append(
            "decision trace scheduler action-contract binding is incomplete"
        )
    raw_version = trace.get("scheduler_action_contract_version")
    if type(raw_version) is not int:
        errors.append(
            "decision trace scheduler action-contract version must be an integer"
        )
        return errors
    if raw_version not in SUPPORTED_SCHEDULER_ACTION_CONTRACT_VERSIONS:
        errors.append(
            "decision trace scheduler action-contract version is not supported"
        )
        return errors
    if required and raw_version != SCHEDULER_ACTION_CONTRACT_VERSION:
        errors.append(
            "new scheduler records require the current action-contract version"
        )
    if trace.get("scheduler_action_contract_sha256") != (
        SCHEDULER_ACTION_CONTRACT_SHA256[raw_version]
    ):
        errors.append(
            "decision trace scheduler action-contract commitment is inconsistent"
        )
    return errors


_ACTION_CONTRACT_ERRORS = tuple(scheduler_action_contract_semantic_errors())
if _ACTION_CONTRACT_ERRORS:
    raise RuntimeError(
        "invalid scheduler action contract: " + "; ".join(_ACTION_CONTRACT_ERRORS)
    )
