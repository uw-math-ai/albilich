from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Set

from .models import (
    DEBT_SEVERITIES,
    DEBT_STATUSES,
    INFERENCE_STATUSES,
    LIFECYCLE_STATUSES,
    ROUTE_RELATIONS,
    ROUTE_STATUSES,
    SCHEMA_VERSION,
    VALIDATION_STATUSES,
    json_loads,
)

VERIFIED_STATUSES = {"informally_verified", "formally_verified"}


def validate_conn(conn: sqlite3.Connection) -> List[str]:
    errors: List[str] = []
    state = conn.execute("SELECT * FROM problem_state").fetchone()
    if state is None:
        return ["problem_state missing"]
    if int(state["schema_version"]) != SCHEMA_VERSION:
        errors.append(f"problem_state schema_version {state['schema_version']} != {SCHEMA_VERSION}")

    root = conn.execute("SELECT * FROM claims WHERE claim_id = 'root'").fetchone()
    if root is None:
        errors.append("root claim missing")
    elif root["statement"] != state["root_statement"]:
        errors.append("exact root statement changed")

    claim_ids: Set[str] = {row["claim_id"] for row in conn.execute("SELECT claim_id FROM claims")}
    route_ids: Set[str] = {row["route_id"] for row in conn.execute("SELECT route_id FROM routes")}
    inference_ids: Set[str] = {row["inference_id"] for row in conn.execute("SELECT inference_id FROM inferences")}
    artifact_ids: Set[str] = {row["artifact_id"] for row in conn.execute("SELECT artifact_id FROM artifacts")}

    for route in conn.execute("SELECT * FROM routes"):
        if route["status"] not in ROUTE_STATUSES:
            errors.append(f"route {route['route_id']} has invalid status {route['status']}")
        if route["relation_to_parent"] not in ROUTE_RELATIONS:
            errors.append(f"route {route['route_id']} has invalid relation_to_parent {route['relation_to_parent']}")
        if route["conclusion_claim_id"] not in claim_ids:
            errors.append(f"route {route['route_id']} has dangling conclusion")
        for aid in json_loads(route["evidence_artifact_ids_json"]):
            if aid not in artifact_ids:
                errors.append(f"route {route['route_id']} has dangling artifact {aid}")

    for inf in conn.execute("SELECT * FROM inferences"):
        if inf["validation_status"] not in INFERENCE_STATUSES:
            errors.append(f"inference {inf['inference_id']} has invalid validation_status {inf['validation_status']}")
        if inf["route_id"] not in route_ids:
            errors.append(f"inference {inf['inference_id']} has dangling route")
        if inf["conclusion_claim_id"] not in claim_ids:
            errors.append(f"inference {inf['inference_id']} has dangling conclusion")
        premises = [row["premise_claim_id"] for row in conn.execute("SELECT premise_claim_id FROM inference_premises WHERE inference_id = ?", (inf["inference_id"],))]
        if (
            inf["validation_status"] in VERIFIED_STATUSES
            and not premises
            and inf["conclusion_claim_id"] != "root"
            and not _has_premiseless_verification_evidence(conn, json_loads(inf["evidence_artifact_ids_json"]))
        ):
            errors.append(f"verified inference {inf['inference_id']} has no premises")
        for premise_id in premises:
            if premise_id not in claim_ids:
                errors.append(f"inference {inf['inference_id']} has dangling premise {premise_id}")
                continue
            premise = conn.execute("SELECT validation_status FROM claims WHERE claim_id = ?", (premise_id,)).fetchone()
            if premise and premise["validation_status"] == "refuted" and inf["validation_status"] in VERIFIED_STATUSES:
                errors.append(f"verified inference {inf['inference_id']} depends on refuted premise {premise_id}")
        condition_ids = json_loads(inf["condition_claim_ids_json"])
        if inf["validation_status"] in VERIFIED_STATUSES:
            for condition_id in condition_ids:
                condition = conn.execute("SELECT validation_status FROM claims WHERE claim_id = ?", (condition_id,)).fetchone()
                if condition is None:
                    errors.append(f"inference {inf['inference_id']} has dangling condition {condition_id}")
                elif condition["validation_status"] not in VERIFIED_STATUSES:
                    errors.append(f"verified inference {inf['inference_id']} uses unverified condition {condition_id}")
        for aid in json_loads(inf["evidence_artifact_ids_json"]):
            if aid not in artifact_ids:
                errors.append(f"inference {inf['inference_id']} has dangling artifact {aid}")

    for debt in conn.execute("SELECT * FROM debts"):
        owner_type = debt["owner_type"]
        owner_id = debt["owner_id"]
        if debt["severity"] not in DEBT_SEVERITIES:
            errors.append(f"debt {debt['debt_id']} has invalid severity {debt['severity']}")
        if debt["status"] not in DEBT_STATUSES:
            errors.append(f"debt {debt['debt_id']} has invalid status {debt['status']}")
        if owner_type == "claim" and owner_id not in claim_ids:
            errors.append(f"debt {debt['debt_id']} has dangling claim owner")
        if owner_type == "route" and owner_id not in route_ids:
            errors.append(f"debt {debt['debt_id']} has dangling route owner")
        if owner_type == "inference" and owner_id not in inference_ids:
            errors.append(f"debt {debt['debt_id']} has dangling inference owner")
        for aid in json_loads(debt["source_artifact_ids_json"]):
            if aid not in artifact_ids:
                errors.append(f"debt {debt['debt_id']} has dangling source artifact {aid}")

    for claim in conn.execute("SELECT * FROM claims"):
        if claim["validation_status"] not in VALIDATION_STATUSES:
            errors.append(f"claim {claim['claim_id']} has invalid validation_status {claim['validation_status']}")
        if claim["lifecycle_status"] not in LIFECYCLE_STATUSES:
            errors.append(f"claim {claim['claim_id']} has invalid lifecycle_status {claim['lifecycle_status']}")
        evidence_ids = json_loads(claim["evidence_artifact_ids_json"])
        if claim["validation_status"] == "formally_verified":
            if not any(_artifact_type(conn, aid) == "formal_backend_result" for aid in evidence_ids):
                errors.append(f"claim {claim['claim_id']} formally verified without formal evidence")
        if claim["validation_status"] == "refuted":
            if not any(_artifact_type(conn, aid) == "confirmed_counterexample" for aid in evidence_ids) and not _has_premiseless_verification_evidence(conn, evidence_ids):
                errors.append(f"claim {claim['claim_id']} refuted without confirmed counterexample or strict verification evidence")
        if claim["lifecycle_status"] == "integrated":
            routes = list(conn.execute("SELECT route_id FROM routes WHERE conclusion_claim_id = ? AND relation_to_parent = 'sufficient' AND status = 'integrated'", (claim["claim_id"],)))
            if not routes:
                errors.append(f"claim {claim['claim_id']} integrated without integrated sufficient route")

    return errors


def _artifact_type(conn: sqlite3.Connection, artifact_id: str) -> str:
    row = conn.execute("SELECT artifact_type FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return row["artifact_type"] if row else ""


ZERO_GAP_VERIFICATION_VERDICTS = {"correct", "correct_no_gaps", "correct_refutation", "informally_verified", "verified"}


def _has_premiseless_verification_evidence(conn: sqlite3.Connection, artifact_ids: List[str]) -> bool:
    for artifact_id in artifact_ids:
        row = conn.execute(
            "SELECT artifact_type, producer_role, metadata_json FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if not row or row["artifact_type"] != "verification_report" or row["producer_role"] != "strict_informal_verifier":
            continue
        metadata = json_loads(row["metadata_json"], {})
        if not isinstance(metadata, dict):
            continue
        report = metadata.get("verification_report", {})
        if not isinstance(report, dict):
            report = {}
        verdict = str(metadata.get("verdict") or report.get("verdict") or "").strip().lower()
        if verdict in ZERO_GAP_VERIFICATION_VERDICTS and not report.get("critical_errors") and not report.get("gaps") and not report.get("blocking_gap"):
            return True
    return False
