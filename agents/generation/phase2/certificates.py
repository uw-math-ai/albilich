from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Dict, Iterable, Mapping, Sequence

from .models import json_dumps, json_loads, utc_now


CERTIFICATE_ARTIFACT_TYPES = {
    "verification_report",
    "integration_report",
    "formal_backend_result",
    "confirmed_counterexample",
}
CERTIFIED_ENTITY_STATUSES = {
    "informally_verified",
    "formally_verified",
    "refuted",
    "integrated",
}


def entity_subject_digest(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> str:
    if entity_type == "claim":
        row = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (entity_id,)).fetchone()
        if row is None:
            return ""
        payload = {
            "entity_type": "claim",
            "claim_id": entity_id,
            "kind": row["kind"],
            "statement": row["statement"],
            "hypotheses": row["hypotheses"],
            "conditions": json_loads(row["conditions_json"]),
            "parent_ids": json_loads(row["parent_ids_json"]),
        }
    elif entity_type == "inference":
        row = conn.execute("SELECT * FROM inferences WHERE inference_id = ?", (entity_id,)).fetchone()
        if row is None:
            return ""
        premises = [
            str(item["premise_claim_id"])
            for item in conn.execute(
                "SELECT premise_claim_id FROM inference_premises WHERE inference_id = ? ORDER BY position, premise_claim_id",
                (entity_id,),
            )
        ]
        payload = {
            "entity_type": "inference",
            "inference_id": entity_id,
            "route_id": row["route_id"],
            "conclusion_claim_id": row["conclusion_claim_id"],
            "premise_claim_ids": premises,
            "explanation": row["explanation"],
            "conditions": json_loads(row["conditions_json"]),
            "condition_claim_ids": json_loads(row["condition_claim_ids_json"]),
        }
    elif entity_type == "route":
        row = conn.execute("SELECT * FROM routes WHERE route_id = ?", (entity_id,)).fetchone()
        if row is None:
            return ""
        payload = {
            "entity_type": "route",
            "route_id": entity_id,
            "conclusion_claim_id": row["conclusion_claim_id"],
            "strategy": row["strategy"],
            "relation_to_parent": row["relation_to_parent"],
            "assumptions": json_loads(row["assumptions_json"]),
            "conditions": json_loads(row["conditions_json"]),
        }
    elif entity_type in {"debt", "proof_obligation"}:
        row = conn.execute("SELECT * FROM debts WHERE debt_id = ?", (entity_id,)).fetchone()
        if row is None:
            return ""
        payload = {
            "entity_type": "proof_obligation",
            "proof_obligation_id": entity_id,
            "owner_type": row["owner_type"],
            "owner_id": row["owner_id"],
            "obligation": row["obligation"],
            "obligation_type": row["debt_type"],
        }
    else:
        return ""
    return _digest(payload)


def dependency_closure_ids(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
) -> list[str]:
    """Canonical transitive proof dependencies for one certified entity."""

    ordered: list[str] = []
    seen: set[str] = set()

    def add(kind: str, identifier: str) -> None:
        key = f"{kind}:{identifier}"
        if not identifier or key in seen:
            return
        seen.add(key)
        ordered.append(key)
        if kind == "route":
            for row in conn.execute(
                "SELECT inference_id FROM inferences WHERE route_id = ? ORDER BY inference_id",
                (identifier,),
            ):
                add("inference", str(row["inference_id"]))
        elif kind == "claim":
            # Bind to every currently certified derivation of this premise.
            for row in conn.execute(
                """
                SELECT inference_id FROM inferences
                WHERE conclusion_claim_id = ?
                  AND validation_status IN ('informally_verified', 'formally_verified')
                ORDER BY inference_id
                """,
                (identifier,),
            ):
                add("inference", str(row["inference_id"]))
        elif kind == "inference":
            row = conn.execute(
                "SELECT condition_claim_ids_json FROM inferences WHERE inference_id = ?",
                (identifier,),
            ).fetchone()
            if row is None:
                return
            dependency_ids = [
                str(item["premise_claim_id"])
                for item in conn.execute(
                    "SELECT premise_claim_id FROM inference_premises WHERE inference_id = ? ORDER BY position, premise_claim_id",
                    (identifier,),
                )
            ]
            dependency_ids.extend(
                str(item) for item in json_loads(row["condition_claim_ids_json"]) if str(item)
            )
            for dependency_id in dependency_ids:
                add("claim", dependency_id)

    if entity_type == "route":
        add("route", entity_id)
    elif entity_type == "inference":
        # The subject itself is stored separately; only its dependencies belong
        # in the closure.
        row = conn.execute(
            "SELECT condition_claim_ids_json FROM inferences WHERE inference_id = ?",
            (entity_id,),
        ).fetchone()
        if row is not None:
            dependencies = [
                str(item["premise_claim_id"])
                for item in conn.execute(
                    "SELECT premise_claim_id FROM inference_premises WHERE inference_id = ? ORDER BY position, premise_claim_id",
                    (entity_id,),
                )
            ]
            dependencies.extend(str(item) for item in json_loads(row["condition_claim_ids_json"]) if str(item))
            for dependency_id in dependencies:
                add("claim", dependency_id)
    elif entity_type == "claim":
        for row in conn.execute(
            """
            SELECT inference_id FROM inferences
            WHERE conclusion_claim_id = ?
              AND validation_status IN ('informally_verified', 'formally_verified')
            ORDER BY inference_id
            """,
            (entity_id,),
        ):
            add("inference", str(row["inference_id"]))
    elif entity_type in {"debt", "proof_obligation"}:
        row = conn.execute(
            "SELECT owner_type, owner_id, resolution_evidence_json FROM debts WHERE debt_id = ?",
            (entity_id,),
        ).fetchone()
        if row is None:
            return []
        owner_type = str(row["owner_type"] or "")
        owner_id = str(row["owner_id"] or "")
        if owner_type in {"claim", "route", "inference"}:
            add(owner_type, owner_id)
        resolution = json_loads(row["resolution_evidence_json"], {})
        if isinstance(resolution, Mapping):
            for key, kind in (
                ("claim_ids", "claim"),
                ("inference_ids", "inference"),
                ("route_ids", "route"),
            ):
                raw = resolution.get(key) or []
                if isinstance(raw, str):
                    raw = [raw]
                if isinstance(raw, Sequence):
                    for identifier in raw:
                        add(kind, str(identifier or ""))
    return sorted(ordered)


def dependency_digest(conn: sqlite3.Connection, dependency_ids: Sequence[str]) -> str:
    payload: list[Dict[str, Any]] = []
    for key in sorted(set(str(item) for item in dependency_ids if str(item))):
        kind, separator, identifier = key.partition(":")
        if not separator:
            continue
        status = _entity_status(conn, kind, identifier)
        payload.append(
            {
                "entity": key,
                "subject_digest": entity_subject_digest(conn, kind, identifier),
                "status": status,
            }
        )
    return _digest(payload)


def bind_new_certificates(
    conn: sqlite3.Connection,
    *,
    applied_revision: int,
) -> None:
    """Attach host-computed bindings to certificate artifacts from this patch."""

    rows = conn.execute(
        """
        SELECT artifact_id, artifact_type, sha256, metadata_json
        FROM artifacts
        WHERE state_revision = ?
          AND artifact_type IN ('verification_report', 'integration_report', 'formal_backend_result', 'confirmed_counterexample')
        ORDER BY artifact_id
        """,
        (applied_revision,),
    ).fetchall()
    for artifact in rows:
        artifact_id = str(artifact["artifact_id"])
        metadata = json_loads(artifact["metadata_json"], {})
        if not isinstance(metadata, dict):
            metadata = {}
        reviewer = metadata.get("host_reviewer_provenance")
        reviewer = dict(reviewer) if isinstance(reviewer, Mapping) else {}
        bindings = dict(metadata.get("host_certificate_bindings") or {})
        targets = _certified_targets_using_artifact(conn, artifact_id, metadata)
        for entity_type, entity_id in targets:
            subject = entity_subject_digest(conn, entity_type, entity_id)
            if not subject:
                continue
            closure = dependency_closure_ids(conn, entity_type, entity_id)
            bindings[f"{entity_type}:{entity_id}"] = {
                "binding_version": 1,
                "subject_digest": subject,
                "dependency_digest": dependency_digest(conn, closure),
                "dependency_entity_ids": closure,
                "artifact_sha256": str(artifact["sha256"] or ""),
                "certified_status": _entity_status(conn, entity_type, entity_id),
                "bound_revision": applied_revision,
                "reviewer_identity": str(reviewer.get("reviewer_identity") or ""),
                "reviewer_independence_class": str(
                    reviewer.get("independence_class") or ""
                ),
                "reviewer_backend": str(reviewer.get("backend") or ""),
                "reviewer_backend_version": str(reviewer.get("backend_version") or ""),
                "backend_contract_hash": str(reviewer.get("backend_contract_hash") or ""),
                "reviewer_model": str(reviewer.get("model") or ""),
            }
        if bindings:
            metadata["host_certificate_bindings"] = bindings
            conn.execute(
                "UPDATE artifacts SET metadata_json = ? WHERE artifact_id = ?",
                (json_dumps(metadata), artifact_id),
            )


def artifact_has_current_binding(
    conn: sqlite3.Connection,
    artifact_id: str,
    *,
    entity_type: str,
    entity_id: str,
) -> bool:
    row = conn.execute(
        "SELECT sha256, metadata_json FROM artifacts WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()
    if row is None:
        return False
    metadata = json_loads(row["metadata_json"], {})
    if not isinstance(metadata, Mapping):
        return False
    binding = (metadata.get("host_certificate_bindings") or {}).get(f"{entity_type}:{entity_id}")
    if not isinstance(binding, Mapping) or int(binding.get("binding_version") or 0) != 1:
        return False
    dependency_ids = binding.get("dependency_entity_ids")
    if not isinstance(dependency_ids, list):
        return False
    return bool(
        str(binding.get("artifact_sha256") or "") == str(row["sha256"] or "")
        and str(binding.get("subject_digest") or "")
        == entity_subject_digest(conn, entity_type, entity_id)
        and str(binding.get("dependency_digest") or "")
        == dependency_digest(conn, dependency_ids)
        and _binding_status_is_current(
            conn,
            entity_type,
            entity_id,
            str(binding.get("certified_status") or ""),
        )
    )


def _binding_status_is_current(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    bound_status: str,
) -> bool:
    """Respect the two independent claim-status coordinates.

    A strict-review certificate binds the claim's validation status. Promoting
    the separately stored lifecycle status to ``integrated`` must not erase
    that review; integration is certified independently on the sufficient
    route. Conversely, an integrated binding is not current if validation has
    subsequently been revoked.
    """

    if entity_type != "claim":
        return bound_status == _entity_status(conn, entity_type, entity_id)
    row = conn.execute(
        "SELECT validation_status, lifecycle_status FROM claims WHERE claim_id = ?",
        (entity_id,),
    ).fetchone()
    if row is None:
        return False
    validation_status = str(row["validation_status"] or "")
    lifecycle_status = str(row["lifecycle_status"] or "")
    if lifecycle_status == "integrated":
        return (
            validation_status in {"informally_verified", "formally_verified"}
            and bound_status in {validation_status, "integrated"}
        )
    return bound_status == validation_status


def invalidate_dependents(
    conn: sqlite3.Connection,
    *,
    changed_claim_ids: Iterable[str] = (),
    changed_inference_ids: Iterable[str] = (),
) -> list[Dict[str, str]]:
    """Conservatively revoke downstream certification after proof-content change."""

    queue = [str(item) for item in changed_claim_ids if str(item)]
    changed_inferences = {str(item) for item in changed_inference_ids if str(item)}
    changes: list[Dict[str, str]] = []
    now_status = "challenged"
    now = utc_now()

    for inference_id in sorted(changed_inferences):
        row = conn.execute(
            "SELECT conclusion_claim_id, validation_status FROM inferences WHERE inference_id = ?",
            (inference_id,),
        ).fetchone()
        if row is None:
            continue
        if row["validation_status"] in {"informally_verified", "formally_verified"}:
            conn.execute(
                "UPDATE inferences SET validation_status = ?, updated_at = ? WHERE inference_id = ?",
                (now_status, now, inference_id),
            )
            changes.append({"entity_type": "inference", "entity_id": inference_id, "new_status": now_status})
        queue.append(str(row["conclusion_claim_id"]))

    seen_claims: set[str] = set()
    while queue:
        claim_id = queue.pop(0)
        if claim_id in seen_claims:
            continue
        seen_claims.add(claim_id)
        claim = conn.execute(
            "SELECT validation_status, lifecycle_status FROM claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if claim and claim["validation_status"] in {"informally_verified", "formally_verified"}:
            conn.execute(
                "UPDATE claims SET validation_status = 'challenged', lifecycle_status = CASE WHEN lifecycle_status='integrated' THEN 'active' ELSE lifecycle_status END, updated_at = ? WHERE claim_id = ?",
                (now, claim_id),
            )
            changes.append({"entity_type": "claim", "entity_id": claim_id, "new_status": "challenged"})
        conn.execute(
            "UPDATE routes SET status = 'active', updated_at = ? WHERE conclusion_claim_id = ? AND status = 'integrated'",
            (now, claim_id),
        )
        for row in _dependent_inference_rows(conn, claim_id):
            inference_id = str(row["inference_id"])
            if row["validation_status"] in {"informally_verified", "formally_verified"}:
                conn.execute(
                    "UPDATE inferences SET validation_status = 'challenged', updated_at = ? WHERE inference_id = ?",
                    (now, inference_id),
                )
                changes.append({"entity_type": "inference", "entity_id": inference_id, "new_status": "challenged"})
            queue.append(str(row["conclusion_claim_id"]))
    return changes


def _dependent_inference_rows(conn: sqlite3.Connection, claim_id: str) -> list[sqlite3.Row]:
    """Return exact premise/condition dependents; never use JSON substrings."""

    rows: Dict[str, sqlite3.Row] = {}
    for row in conn.execute(
        """
        SELECT DISTINCT i.inference_id, i.conclusion_claim_id, i.validation_status
        FROM inferences i
        JOIN inference_premises p ON p.inference_id = i.inference_id
        WHERE p.premise_claim_id = ?
        """,
        (claim_id,),
    ):
        rows[str(row["inference_id"])] = row
    for row in conn.execute(
        """
        SELECT inference_id, conclusion_claim_id, validation_status, condition_claim_ids_json
        FROM inferences
        WHERE condition_claim_ids_json != '[]'
        """
    ):
        condition_ids = {str(item) for item in json_loads(row["condition_claim_ids_json"], [])}
        if claim_id in condition_ids:
            rows[str(row["inference_id"])] = row
    return [rows[key] for key in sorted(rows)]


def invalidate_stale_refuted_obligations(conn: sqlite3.Connection) -> list[Dict[str, str]]:
    """Reopen refuted obligations whose host certificate is no longer current."""

    changes: list[Dict[str, str]] = []
    now = utc_now()
    for row in conn.execute(
        "SELECT debt_id, resolution_evidence_json FROM debts WHERE status = 'refuted' ORDER BY debt_id"
    ):
        obligation_id = str(row["debt_id"])
        resolution = json_loads(row["resolution_evidence_json"], {})
        if not isinstance(resolution, Mapping):
            resolution = {}
        evidence_ids = [
            str(item)
            for item in (
                resolution.get("resolution_evidence_artifact_ids")
                or resolution.get("evidence_artifact_ids")
                or []
            )
            if str(item)
        ]
        if any(
            artifact_has_current_binding(
                conn,
                artifact_id,
                entity_type="proof_obligation",
                entity_id=obligation_id,
            )
            for artifact_id in evidence_ids
        ):
            continue
        conn.execute(
            "UPDATE debts SET status = 'active', last_seen = ? WHERE debt_id = ?",
            (now, obligation_id),
        )
        changes.append(
            {"entity_type": "proof_obligation", "entity_id": obligation_id, "new_status": "active"}
        )
    return changes


def _certified_targets_using_artifact(
    conn: sqlite3.Connection,
    artifact_id: str,
    metadata: Mapping[str, Any],
) -> list[tuple[str, str]]:
    targets: set[tuple[str, str]] = set()
    for row in conn.execute("SELECT claim_id, validation_status, lifecycle_status, evidence_artifact_ids_json FROM claims"):
        status = "integrated" if row["lifecycle_status"] == "integrated" else str(row["validation_status"])
        if status in CERTIFIED_ENTITY_STATUSES and artifact_id in json_loads(row["evidence_artifact_ids_json"]):
            targets.add(("claim", str(row["claim_id"])))
    for row in conn.execute("SELECT inference_id, validation_status, evidence_artifact_ids_json FROM inferences"):
        if row["validation_status"] in CERTIFIED_ENTITY_STATUSES and artifact_id in json_loads(row["evidence_artifact_ids_json"]):
            targets.add(("inference", str(row["inference_id"])))
    for row in conn.execute("SELECT route_id, status, evidence_artifact_ids_json FROM routes"):
        if row["status"] == "integrated" and artifact_id in json_loads(row["evidence_artifact_ids_json"]):
            targets.add(("route", str(row["route_id"])))
    for row in conn.execute("SELECT debt_id, status, resolution_evidence_json FROM debts"):
        if str(row["status"] or "") != "refuted":
            continue
        resolution = json_loads(row["resolution_evidence_json"], {})
        if not isinstance(resolution, Mapping):
            continue
        evidence_ids = {
            str(item)
            for item in (
                resolution.get("resolution_evidence_artifact_ids")
                or resolution.get("evidence_artifact_ids")
                or []
            )
            if str(item)
        }
        if artifact_id in evidence_ids:
            targets.add(("proof_obligation", str(row["debt_id"])))
    route_id = str(metadata.get("route_id") or metadata.get("target_route_id") or "")
    if route_id:
        route = conn.execute("SELECT status FROM routes WHERE route_id = ?", (route_id,)).fetchone()
        if route is not None and route["status"] == "integrated":
            targets.add(("route", route_id))
    return sorted(targets)


def _entity_status(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> str:
    if entity_type == "claim":
        row = conn.execute(
            "SELECT validation_status, lifecycle_status FROM claims WHERE claim_id = ?",
            (entity_id,),
        ).fetchone()
        if row is None:
            return "missing"
        return "integrated" if row["lifecycle_status"] == "integrated" else str(row["validation_status"])
    if entity_type == "inference":
        row = conn.execute("SELECT validation_status FROM inferences WHERE inference_id = ?", (entity_id,)).fetchone()
        return str(row["validation_status"]) if row else "missing"
    if entity_type == "route":
        row = conn.execute("SELECT status FROM routes WHERE route_id = ?", (entity_id,)).fetchone()
        return str(row["status"]) if row else "missing"
    if entity_type in {"debt", "proof_obligation"}:
        row = conn.execute("SELECT status FROM debts WHERE debt_id = ?", (entity_id,)).fetchone()
        return str(row["status"]) if row else "missing"
    return "missing"


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
