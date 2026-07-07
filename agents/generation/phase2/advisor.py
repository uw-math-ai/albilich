from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from .models import SCHEMA_VERSION
from .scheduler import advisor_should_run
from .store import ProofStateStore


def advisor_due(*, iteration: int, iterations_since_new_accepted_claim: int, last_advisor_iteration: int | None = None) -> Dict[str, Any]:
    return advisor_should_run(
        iteration=iteration,
        iterations_since_new_accepted_claim=iterations_since_new_accepted_claim,
        last_advisor_iteration=last_advisor_iteration,
    )


def phd_advisor_patch(
    store: ProofStateStore,
    *,
    operations: Sequence[Mapping[str, Any]],
    rationale: str,
    target_id: str = "root",
) -> Dict[str, Any]:
    """Wrap advisor recommendations as proposals, never as verification gates."""
    allowed = {"add_claim", "add_route", "add_debt", "update_debt", "abandon_route", "reactivate_route"}
    sanitized_ops = []
    for op in operations:
        if op.get("op") == "propose_status_transition" and op.get("new_status") in {"informally_verified", "formally_verified", "refuted"}:
            raise ValueError("phd_advisor cannot propose verified/refuted status transitions")
        if op.get("op") not in allowed and op.get("op") != "propose_status_transition":
            raise ValueError(f"phd_advisor operation is not allowed: {op.get('op')}")
        sanitized_ops.append(dict(op))
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": store.problem_id,
        "base_revision": store.get_revision(),
        "actor_role": "phd_advisor",
        "target_id": target_id,
        "operations": sanitized_ops,
        "rationale": rationale,
    }
