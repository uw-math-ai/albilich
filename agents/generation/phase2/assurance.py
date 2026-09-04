from __future__ import annotations

import sqlite3
from typing import Any, Mapping

from .certificates import artifact_has_current_binding, entity_subject_digest
from .authority import reviewer_independence_class
from .models import json_loads


STANDARD_ASSURANCE = "standard"
HETEROGENEOUS_REVIEW = "heterogeneous_review"


def assurance_backend_conflict(
    action: Mapping[str, Any], *, backend: str, model: str
) -> dict[str, str] | None:
    """Return a pre-launch conflict when a review would reuse a seen family."""

    if not action.get("assurance_review_required"):
        return None
    observed = {
        str(item)
        for item in action.get("observed_reviewer_independence_classes", []) or []
        if str(item)
    }
    current = reviewer_independence_class(backend, model)
    if current and current in observed:
        return {
            "failure_kind": "heterogeneous_backend_required",
            "backend": backend,
            "model": model,
            "independence_class": current,
            "message": (
                f"enhanced assurance requires a reviewer outside {sorted(observed)}; "
                f"configured backend/model belongs to already-observed class {current!r}"
            ),
        }
    return None


def claim_assurance_summary(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    route_id: str,
) -> dict[str, Any]:
    designation = conn.execute(
        "SELECT assurance_level, rationale FROM claim_assurance WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    level = (
        str(designation["assurance_level"] or STANDARD_ASSURANCE)
        if designation
        else STANDARD_ASSURANCE
    )
    if level != HETEROGENEOUS_REVIEW:
        return {
            "claim_id": claim_id,
            "assurance_level": level,
            "satisfied": True,
            "basis": "standard review policy",
            "independence_classes": [],
            "review_artifact_ids": [],
        }

    inference_ids = {
        str(row["inference_id"])
        for row in conn.execute(
            "SELECT inference_id FROM inferences WHERE route_id = ?", (route_id,)
        )
    }
    relevant_keys = {f"claim:{claim_id}"} | {
        f"inference:{item}" for item in inference_ids
    }
    coverage_by_class: dict[str, set[str]] = {}
    review_artifact_ids: list[str] = []
    formal_artifact_ids: list[str] = []
    human_artifact_ids_by_class: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT artifact_id, artifact_type, metadata_json FROM artifacts "
        "WHERE artifact_type IN ('verification_report', 'formal_backend_result') "
        "ORDER BY state_revision, artifact_id"
    ):
        artifact_id = str(row["artifact_id"] or "")
        metadata = json_loads(row["metadata_json"], {})
        if not isinstance(metadata, Mapping):
            continue
        bindings = metadata.get("host_certificate_bindings")
        if not isinstance(bindings, Mapping):
            continue
        current_keys: set[str] = set()
        for key in relevant_keys & set(str(item) for item in bindings):
            entity_type, _, entity_id = key.partition(":")
            if artifact_has_current_binding(
                conn,
                artifact_id,
                entity_type=entity_type,
                entity_id=entity_id,
            ):
                current_keys.add(key)
        if not current_keys:
            continue
        review_artifact_ids.append(artifact_id)
        provenance = metadata.get("host_reviewer_provenance")
        provenance = provenance if isinstance(provenance, Mapping) else {}
        independence_class = str(provenance.get("independence_class") or "")
        if independence_class:
            coverage_by_class.setdefault(independence_class, set()).update(
                current_keys
            )
        if independence_class.startswith("human:"):
            human_artifact_ids_by_class.setdefault(
                independence_class, []
            ).append(artifact_id)
        host_formal = metadata.get("host_formal_check")
        formal_target = metadata.get("host_formal_target_binding")
        if (
            str(row["artifact_type"] or "") == "formal_backend_result"
            and isinstance(host_formal, Mapping)
            and host_formal.get("host_checked") is True
            and isinstance(formal_target, Mapping)
            and f"claim:{claim_id}" in current_keys
            and str(formal_target.get("target_type") or "") == "claim"
            and str(formal_target.get("target_id") or "") == claim_id
            and str(formal_target.get("subject_digest") or "")
            == entity_subject_digest(conn, "claim", claim_id)
        ):
            formal_artifact_ids.append(artifact_id)

    complete_classes = {
        reviewer_class
        for reviewer_class, coverage in coverage_by_class.items()
        if relevant_keys <= coverage
    }
    model_classes = {
        item
        for item in complete_classes
        if item and not item.startswith("human:") and not item.startswith("formal:")
    }
    complete_human_classes = {
        item for item in complete_classes if item.startswith("human:")
    }
    human_artifact_ids = sorted(
        {
            artifact_id
            for reviewer_class in complete_human_classes
            for artifact_id in human_artifact_ids_by_class.get(
                reviewer_class, []
            )
        }
    )
    partial_classes = set(coverage_by_class) - complete_classes
    if formal_artifact_ids:
        satisfied = True
        basis = "successful formal checker certificate"
    elif complete_human_classes:
        satisfied = True
        basis = "explicit human-operated verification checkpoint"
    elif len(model_classes) >= 2:
        satisfied = True
        basis = "two distinct model-family review classes"
    else:
        satisfied = False
        basis = (
            "requires two distinct model-family reviews or one human/formal checkpoint"
        )
    return {
        "claim_id": claim_id,
        "route_id": route_id,
        "assurance_level": level,
        "rationale": str(designation["rationale"] or "") if designation else "",
        "satisfied": satisfied,
        "basis": basis,
        "required_binding_keys": sorted(relevant_keys),
        "independence_classes": sorted(complete_classes),
        "partial_independence_classes": sorted(partial_classes),
        "review_coverage_by_class": {
            reviewer_class: sorted(coverage)
            for reviewer_class, coverage in sorted(coverage_by_class.items())
        },
        "model_independence_classes": sorted(model_classes),
        "review_artifact_ids": review_artifact_ids,
        "human_artifact_ids": human_artifact_ids,
        "formal_artifact_ids": formal_artifact_ids,
    }


def claim_assurance_errors(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    route_id: str,
) -> list[str]:
    summary = claim_assurance_summary(
        conn, claim_id=claim_id, route_id=route_id
    )
    if summary["satisfied"]:
        return []
    observed = ", ".join(summary["independence_classes"]) or "none"
    return [
        f"claim {claim_id} is designated heterogeneous_review but its independent "
        f"review requirement is unsatisfied (observed classes: {observed}); "
        "obtain two distinct model-family reviews or one human/formal checkpoint"
    ]


def state_assurance_summary(
    state: Mapping[str, Any], *, claim_id: str, route_id: str
) -> dict[str, Any]:
    """Conservative scheduler view; the kernel repeats the authoritative check."""

    designation = next(
        (
            row
            for row in state.get("claim_assurance", [])
            if str(row.get("claim_id") or "") == claim_id
        ),
        None,
    )
    level = str((designation or {}).get("assurance_level") or STANDARD_ASSURANCE)
    if level != HETEROGENEOUS_REVIEW:
        return {
            "assurance_level": level,
            "satisfied": True,
            "independence_classes": [],
            "review_artifact_ids": [],
        }
    inference_ids = {
        str(row.get("inference_id") or "")
        for row in state.get("inferences", [])
        if str(row.get("route_id") or "") == route_id
    }
    relevant_keys = {f"claim:{claim_id}"} | {
        f"inference:{item}" for item in inference_ids if item
    }
    classes: set[str] = set()
    artifacts: list[str] = []
    formal = False
    human = False
    candidates = [
        *state.get("audit_artifacts", []),
        *state.get("artifacts", []),
    ]
    seen: set[str] = set()
    for row in candidates:
        artifact_id = str(row.get("artifact_id") or "")
        if not artifact_id or artifact_id in seen:
            continue
        seen.add(artifact_id)
        if str(row.get("artifact_type") or "") not in {
            "verification_report",
            "formal_backend_result",
        }:
            continue
        metadata = json_loads(row.get("metadata_json"), {})
        if not isinstance(metadata, Mapping):
            continue
        bindings = metadata.get("host_certificate_bindings")
        if not isinstance(bindings, Mapping) or not (
            relevant_keys & set(str(item) for item in bindings)
        ):
            continue
        artifacts.append(artifact_id)
        provenance = metadata.get("host_reviewer_provenance")
        provenance = provenance if isinstance(provenance, Mapping) else {}
        reviewer_class = str(provenance.get("independence_class") or "")
        if reviewer_class:
            classes.add(reviewer_class)
        human = human or reviewer_class.startswith("human:")
        host_formal = metadata.get("host_formal_check")
        formal = formal or (
            str(row.get("artifact_type") or "") == "formal_backend_result"
            and isinstance(host_formal, Mapping)
            and host_formal.get("host_checked") is True
        )
    model_classes = {
        item
        for item in classes
        if item and not item.startswith("human:") and not item.startswith("formal:")
    }
    return {
        "assurance_level": level,
        # A detached state mapping cannot recompute current certificate and
        # dependency digests. Never turn this display projection into an
        # authorization decision; claim_assurance_summary(conn, ...) is the
        # only satisfiability check.
        "satisfied": False,
        "authoritative_check_required": True,
        "independence_classes": sorted(classes),
        "model_independence_classes": sorted(model_classes),
        "review_artifact_ids": artifacts,
        "unverified_human_checkpoint_marker": human,
        "unverified_formal_checkpoint_marker": formal,
    }
