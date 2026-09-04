from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Mapping, Set

from .artifacts import artifact_hash
from .assurance import claim_assurance_errors
from .certificates import artifact_has_current_binding
from .decision_policy import (
    action_sha256,
    candidate_rows_sha256,
    decision_deferral_state_after_trace,
    decision_trace_is_parallel_companion,
    decision_trace_errors,
)
from .dispatch_execution import (
    durable_path_source_identity_errors,
    dispatch_json_sha256,
    dispatch_result_sha256,
    execution_contract_errors,
)
from .parallel_admission import parallel_outcome_is_fairness_eligible
from .randomized_assignment import (
    WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS,
    randomized_assignment_cohort_errors,
    randomized_assignment_errors,
    randomized_assignment_metadata,
)
from .models import (
    DEBT_SEVERITIES,
    DEBT_STATUSES,
    INFERENCE_STATUSES,
    LIFECYCLE_STATUSES,
    ROUTE_RELATIONS,
    ROUTE_STATUSES,
    SCHEMA_VERSION,
    VALIDATION_STATUSES,
    json_dumps,
    json_loads,
)
from .verification import ZERO_GAP_VERIFICATION_VERDICTS, clean_verification_metadata

VERIFIED_STATUSES = {"informally_verified", "formally_verified"}


def validate_conn(
    conn: sqlite3.Connection,
    *,
    pending_run_ids: Set[str] | None = None,
    pending_dispatch_ids: Set[str] | None = None,
    immutable_history_sealed: bool = False,
) -> List[str]:
    errors: List[str] = []
    state = conn.execute("SELECT * FROM problem_state").fetchone()
    if state is None:
        return ["problem_state missing"]
    if int(state["schema_version"]) != SCHEMA_VERSION:
        errors.append(f"problem_state schema_version {state['schema_version']} != {SCHEMA_VERSION}")
    # Local import avoids a module-initialization cycle: patches imports this
    # validator and the store imports patches only at runtime.
    from .store import (
        randomized_assignment_index_errors,
        scheduler_dispatch_tail_index_errors,
    )

    errors.extend(randomized_assignment_index_errors(conn))
    errors.extend(scheduler_dispatch_tail_index_errors(conn))

    root = conn.execute("SELECT * FROM claims WHERE claim_id = 'root'").fetchone()
    if root is None:
        errors.append("root claim missing")
    elif root["statement"] != state["root_statement"]:
        errors.append("exact root statement changed")

    claim_ids: Set[str] = {row["claim_id"] for row in conn.execute("SELECT claim_id FROM claims")}
    route_ids: Set[str] = {row["route_id"] for row in conn.execute("SELECT route_id FROM routes")}
    inference_ids: Set[str] = {row["inference_id"] for row in conn.execute("SELECT inference_id FROM inferences")}
    artifact_ids: Set[str] = {row["artifact_id"] for row in conn.execute("SELECT artifact_id FROM artifacts")}
    errors.extend(_typed_relation_mirror_errors(conn))
    errors.extend(
        _run_assignment_provenance_errors(
            conn,
            pending_run_ids=pending_run_ids or set(),
            run_ids=(pending_run_ids or set()) if immutable_history_sealed else None,
        )
    )
    errors.extend(
        _scheduler_dispatch_errors(
            conn,
            pending_dispatch_ids=pending_dispatch_ids or set(),
            only_dispatch_ids=(
                pending_dispatch_ids or set()
                if immutable_history_sealed
                else None
            ),
        )
    )
    errors.extend(_scheduler_fairness_state_errors(conn))
    errors.extend(_scheduler_decision_fairness_state_errors(conn))

    dependency_edges: Dict[str, Set[str]] = {claim_id: set() for claim_id in claim_ids}
    for inference in conn.execute(
        "SELECT inference_id, conclusion_claim_id FROM inferences"
    ):
        conclusion_id = str(inference["conclusion_claim_id"] or "")
        if conclusion_id not in dependency_edges:
            continue
        dependency_edges[conclusion_id].update(
            str(row["premise_claim_id"])
            for row in conn.execute(
                "SELECT premise_claim_id FROM inference_premises WHERE inference_id = ?",
                (inference["inference_id"],),
            )
            if str(row["premise_claim_id"])
        )
        dependency_edges[conclusion_id].update(
            str(row["condition_claim_id"])
            for row in conn.execute(
                "SELECT condition_claim_id FROM inference_condition_claims "
                "WHERE inference_id = ? ORDER BY position",
                (inference["inference_id"],),
            )
            if str(row["condition_claim_id"])
        )
    errors.extend(_directed_cycle_errors(dependency_edges, relation="proof dependency"))

    parent_edges: Dict[str, Set[str]] = {claim_id: set() for claim_id in claim_ids}
    for claim in conn.execute("SELECT claim_id FROM claims"):
        parent_edges[str(claim["claim_id"])].update(
            str(row["parent_claim_id"])
            for row in conn.execute(
                "SELECT parent_claim_id FROM claim_parent_relations "
                "WHERE claim_id = ? ORDER BY position",
                (claim["claim_id"],),
            )
            if str(row["parent_claim_id"])
        )
    errors.extend(_directed_cycle_errors(parent_edges, relation="claim parent"))

    for artifact in conn.execute("SELECT artifact_id, path, sha256, metadata_json FROM artifacts"):
        metadata = json_loads(artifact["metadata_json"], {})
        integrity = metadata.get("integrity", {}) if isinstance(metadata, dict) else {}
        if not isinstance(integrity, dict) or integrity.get("scope") != "file_bytes":
            continue
        path = Path(str(artifact["path"] or ""))
        if not path.is_file():
            errors.append(f"artifact {artifact['artifact_id']} integrity file is missing")
            continue
        try:
            observed_hash = artifact_hash(path=path)
        except (OSError, ValueError) as exc:
            errors.append(
                f"artifact {artifact['artifact_id']} integrity file cannot be read safely: {exc}"
            )
            continue
        if observed_hash != str(artifact["sha256"] or ""):
            errors.append(f"artifact {artifact['artifact_id']} file hash does not match recorded sha256")

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
        if route["status"] == "integrated":
            route_evidence_ids = json_loads(route["evidence_artifact_ids_json"])
            # Integration reports are commonly attached to the claim rather
            # than duplicated on the route row; inspect both exact stores.
            conclusion_evidence_row = conn.execute(
                "SELECT evidence_artifact_ids_json FROM claims WHERE claim_id = ?",
                (route["conclusion_claim_id"],),
            ).fetchone()
            if conclusion_evidence_row:
                route_evidence_ids.extend(json_loads(conclusion_evidence_row["evidence_artifact_ids_json"]))
            if not _has_current_certificate(
                conn,
                route_evidence_ids,
                entity_type="route",
                entity_id=str(route["route_id"]),
                artifact_types={"integration_report"},
            ):
                errors.append(f"integrated route {route['route_id']} has no current host-bound integration certificate")
            conclusion = conn.execute(
                "SELECT validation_status, lifecycle_status FROM claims WHERE claim_id = ?",
                (route["conclusion_claim_id"],),
            ).fetchone()
            if route["relation_to_parent"] != "sufficient":
                errors.append(f"integrated route {route['route_id']} is not sufficient")
            if conclusion and conclusion["lifecycle_status"] != "integrated":
                errors.append(
                    f"integrated route {route['route_id']} concludes non-integrated claim "
                    f"{route['conclusion_claim_id']}"
                )
            if conclusion and conclusion["validation_status"] not in VERIFIED_STATUSES:
                errors.append(
                    f"integrated route {route['route_id']} concludes unverified claim "
                    f"{route['conclusion_claim_id']}"
                )
            terminal_verified = False
            grounding_memo: Dict[str, bool] = {}
            route_inference_ids: List[str] = []
            for inference in conn.execute(
                "SELECT inference_id, conclusion_claim_id, validation_status FROM inferences WHERE route_id = ?",
                (route["route_id"],),
            ):
                route_inference_ids.append(str(inference["inference_id"]))
                if (
                    inference["conclusion_claim_id"] != route["conclusion_claim_id"]
                    or inference["validation_status"] not in VERIFIED_STATUSES
                ):
                    continue
                if _inference_is_grounded(
                    conn,
                    str(inference["inference_id"]),
                    memo=grounding_memo,
                    visiting=set(),
                ):
                    terminal_verified = True
            if not terminal_verified:
                errors.append(
                    f"integrated route {route['route_id']} has no recursively grounded verified terminal inference"
                )
            blocker_owner_ids = [str(route["route_id"]), *route_inference_ids]
            if blocker_owner_ids:
                placeholders = ", ".join("?" for _ in blocker_owner_ids)
                blocker = conn.execute(
                    f"""
                    SELECT debt_id FROM debts
                    WHERE owner_id IN ({placeholders})
                      AND status = 'active'
                      AND severity = 'blocking'
                    LIMIT 1
                    """,
                    blocker_owner_ids,
                ).fetchone()
                if blocker:
                    errors.append(
                        f"integrated route {route['route_id']} carries active blocking debt "
                        f"{blocker['debt_id']}"
                    )

    for inf in conn.execute("SELECT * FROM inferences"):
        if inf["validation_status"] not in INFERENCE_STATUSES:
            errors.append(f"inference {inf['inference_id']} has invalid validation_status {inf['validation_status']}")
        if inf["validation_status"] in VERIFIED_STATUSES and not _has_current_certificate(
            conn,
            json_loads(inf["evidence_artifact_ids_json"]),
            entity_type="inference",
            entity_id=str(inf["inference_id"]),
            artifact_types={"verification_report", "formal_backend_result"},
        ):
            errors.append(f"verified inference {inf['inference_id']} has no current host-bound certificate")
        if inf["validation_status"] == "formally_verified" and not _has_successful_formal_check(
            conn, json_loads(inf["evidence_artifact_ids_json"])
        ):
            errors.append(f"inference {inf['inference_id']} formally verified without a successful host checker run")
        if inf["route_id"] not in route_ids:
            errors.append(f"inference {inf['inference_id']} has dangling route")
        if inf["conclusion_claim_id"] not in claim_ids:
            errors.append(f"inference {inf['inference_id']} has dangling conclusion")
        premises = [row["premise_claim_id"] for row in conn.execute("SELECT premise_claim_id FROM inference_premises WHERE inference_id = ?", (inf["inference_id"],))]
        if (
            inf["validation_status"] in VERIFIED_STATUSES
            and not premises
            and inf["conclusion_claim_id"] != "root"
            and not _has_verification_evidence(
                conn,
                json_loads(inf["evidence_artifact_ids_json"]),
                outcome="positive",
            )
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
        for condition_id in condition_ids:
            condition = conn.execute("SELECT validation_status FROM claims WHERE claim_id = ?", (condition_id,)).fetchone()
            if condition is None:
                errors.append(f"inference {inf['inference_id']} has dangling condition {condition_id}")
            elif (
                inf["validation_status"] in VERIFIED_STATUSES
                and condition["validation_status"] not in VERIFIED_STATUSES
            ):
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
        if owner_type == "artifact" and owner_id not in artifact_ids:
            errors.append(f"debt {debt['debt_id']} has dangling artifact owner")
        for aid in json_loads(debt["source_artifact_ids_json"]):
            if aid not in artifact_ids:
                errors.append(f"debt {debt['debt_id']} has dangling source artifact {aid}")
        if debt["status"] == "refuted":
            resolution = json_loads(debt["resolution_evidence_json"], {})
            resolution_ids = (
                resolution.get("resolution_evidence_artifact_ids")
                or resolution.get("evidence_artifact_ids")
                or []
                if isinstance(resolution, dict)
                else []
            )
            if not _has_current_certificate(
                conn,
                resolution_ids,
                entity_type="proof_obligation",
                entity_id=str(debt["debt_id"]),
                artifact_types={"confirmed_counterexample", "verification_report"},
            ):
                errors.append(
                    f"refuted proof obligation {debt['debt_id']} has no current host-bound refutation certificate"
                )

    for claim in conn.execute("SELECT * FROM claims"):
        if claim["validation_status"] not in VALIDATION_STATUSES:
            errors.append(f"claim {claim['claim_id']} has invalid validation_status {claim['validation_status']}")
        if claim["lifecycle_status"] not in LIFECYCLE_STATUSES:
            errors.append(f"claim {claim['claim_id']} has invalid lifecycle_status {claim['lifecycle_status']}")
        try:
            reduction_depth = int(claim["reduction_depth"])
        except (TypeError, ValueError):
            reduction_depth = -1
        if reduction_depth < 0:
            errors.append(f"claim {claim['claim_id']} has negative reduction_depth")
        try:
            root_impact = float(claim["root_impact"])
        except (TypeError, ValueError):
            root_impact = math.nan
        if not math.isfinite(root_impact) or not 0.0 <= root_impact <= 1.0:
            errors.append(f"claim {claim['claim_id']} has invalid root_impact {claim['root_impact']}")
        for parent_id in [str(item) for item in json_loads(claim["parent_ids_json"]) if str(item)]:
            if parent_id not in claim_ids:
                errors.append(f"claim {claim['claim_id']} has dangling parent {parent_id}")
        for aid in json_loads(claim["evidence_artifact_ids_json"]):
            if aid not in artifact_ids:
                errors.append(f"claim {claim['claim_id']} has dangling artifact {aid}")
        evidence_ids = json_loads(claim["evidence_artifact_ids_json"])
        if claim["validation_status"] in VERIFIED_STATUSES and not _has_current_certificate(
            conn,
            evidence_ids,
            entity_type="claim",
            entity_id=str(claim["claim_id"]),
            artifact_types={
                "verification_report",
                "formal_backend_result",
                *({"integration_report"} if claim["lifecycle_status"] == "integrated" else set()),
            },
        ):
            errors.append(f"verified claim {claim['claim_id']} has no current host-bound certificate")
        if claim["validation_status"] == "formally_verified":
            if not _has_successful_formal_check(conn, evidence_ids):
                errors.append(f"claim {claim['claim_id']} formally verified without a successful host checker run")
        if claim["validation_status"] == "refuted":
            if not _has_current_certificate(
                conn,
                evidence_ids,
                entity_type="claim",
                entity_id=str(claim["claim_id"]),
                artifact_types={"confirmed_counterexample", "verification_report"},
            ):
                errors.append(f"claim {claim['claim_id']} refuted without confirmed counterexample or strict verification evidence")
        if claim["lifecycle_status"] == "integrated":
            if claim["validation_status"] not in VERIFIED_STATUSES:
                errors.append(f"claim {claim['claim_id']} integrated without verified validation status")
            routes = list(conn.execute("SELECT route_id FROM routes WHERE conclusion_claim_id = ? AND relation_to_parent = 'sufficient' AND status = 'integrated'", (claim["claim_id"],)))
            if not routes:
                errors.append(f"claim {claim['claim_id']} integrated without integrated sufficient route")
            for integrated_route in routes:
                errors.extend(
                    claim_assurance_errors(
                        conn,
                        claim_id=str(claim["claim_id"]),
                        route_id=str(integrated_route["route_id"]),
                    )
                )

    for request in conn.execute("SELECT * FROM context_requests"):
        request_id = str(request["request_id"] or "")
        status = str(request["status"] or "")
        fulfilled_revision = int(request["fulfilled_revision"] or 0)
        if status == "pending" and (
            fulfilled_revision != 0 or str(request["fulfilled_at"] or "")
        ):
            errors.append(
                f"pending context request {request_id} has fulfillment metadata"
            )
        if status == "cancelled" and (
            fulfilled_revision != 0 or str(request["fulfilled_at"] or "")
        ):
            errors.append(
                f"cancelled context request {request_id} has fulfillment metadata"
            )
        if status == "fulfilled" and (
            fulfilled_revision <= 0
            or fulfilled_revision > int(state["current_revision"] or 0)
            or not str(request["fulfilled_at"] or "")
        ):
            errors.append(
                f"fulfilled context request {request_id} has invalid fulfillment metadata"
            )

    return errors


def _scheduler_fairness_state_errors(conn: sqlite3.Connection) -> List[str]:
    """Check the compact counters against the last authenticated wave record."""

    errors: List[str] = []
    meta_rows = conn.execute(
        "SELECT last_wave_id, last_state_revision, policy_version, updated_run_id, "
        "updated_dispatch_id "
        "FROM scheduler_fairness_meta ORDER BY singleton"
    ).fetchall()
    counter_rows = conn.execute(
        "SELECT candidate_id, consecutive_capacity_deferrals, last_wave_id, "
        "policy_version, updated_run_id, updated_dispatch_id "
        "FROM scheduler_candidate_deferrals "
        "ORDER BY candidate_id"
    ).fetchall()
    if len(meta_rows) > 1:
        return ["scheduler fairness state has more than one metadata row"]
    if not meta_rows:
        if counter_rows:
            errors.append("scheduler fairness counters have no metadata row")
        return errors
    meta = meta_rows[0]
    wave_id = str(meta["last_wave_id"] or "")
    run_id = str(meta["updated_run_id"] or "")
    dispatch_id = str(meta["updated_dispatch_id"] or "")
    if len(wave_id) != 64 or any(
        character not in "0123456789abcdef" for character in wave_id
    ):
        errors.append("scheduler fairness metadata has an invalid wave identifier")
    if bool(run_id) == bool(dispatch_id):
        errors.append("scheduler fairness metadata has invalid provenance")
        return errors
    if dispatch_id:
        provenance = conn.execute(
            "SELECT decision_trace_json FROM scheduler_dispatches "
            "WHERE dispatch_id = ?",
            (dispatch_id,),
        ).fetchone()
        provenance_label = "dispatch"
    else:
        provenance = conn.execute(
            "SELECT decision_trace_json FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        provenance_label = "run"
    if provenance is None:
        errors.append(
            f"scheduler fairness metadata references a missing {provenance_label}"
        )
        return errors
    trace = json_loads(provenance["decision_trace_json"], {})
    wave = (
        trace.get("parallel_wave_admission")
        if isinstance(trace, dict)
        else None
    )
    if not isinstance(wave, dict) or str(wave.get("wave_id") or "") != wave_id:
        errors.append(
            f"scheduler fairness metadata disagrees with its {provenance_label} wave"
        )
        return errors
    if (
        type(meta["last_state_revision"]) is not int
        or int(meta["last_state_revision"]) < 0
        or type(meta["policy_version"]) is not int
        or int(meta["policy_version"]) <= 0
    ):
        errors.append("scheduler fairness metadata has invalid numeric fields")
        return errors
    state_revision = int(meta["last_state_revision"])
    policy_version = int(meta["policy_version"])
    wave_state_revision = wave.get("state_revision")
    wave_policy_version = wave.get("policy_version")
    if type(wave_policy_version) is not int or wave_policy_version <= 0:
        errors.append("scheduler fairness run wave has an invalid policy version")
        return errors
    if wave_policy_version >= 4:
        if type(wave_state_revision) is not int or wave_state_revision < 0:
            errors.append("scheduler fairness run wave has an invalid state revision")
            return errors
        if state_revision != wave_state_revision:
            errors.append("scheduler fairness state revision disagrees with its wave")
    elif state_revision != 0:
        errors.append("legacy scheduler fairness state revision must be zero")
    if policy_version != wave_policy_version:
        errors.append("scheduler fairness policy version disagrees with its wave")
    expected: Dict[str, int] = {}
    for row in wave.get("candidates", []):
        if not isinstance(row, dict):
            continue
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id == "parallel:primary":
            continue
        if str(row.get("disposition") or "") == "rejected" and (
            parallel_outcome_is_fairness_eligible(
                row,
                policy_version=wave_policy_version,
            )
        ):
            prior_count = row.get("consecutive_deferrals")
            if type(prior_count) is not int or prior_count < 0:
                errors.append(
                    f"scheduler fairness wave has an invalid deferral count for {candidate_id}"
                )
                continue
            expected[candidate_id] = prior_count + 1
    observed: Dict[str, int] = {}
    for row in counter_rows:
        candidate_id = row["candidate_id"]
        count = row["consecutive_capacity_deferrals"]
        if not isinstance(candidate_id, str) or not candidate_id:
            errors.append("scheduler fairness counter has an invalid candidate identifier")
            continue
        if type(count) is not int or count <= 0:
            errors.append(
                f"scheduler fairness counter is not a positive integer for {candidate_id}"
            )
            continue
        observed[candidate_id] = count
    if observed != expected:
        errors.append("scheduler fairness counters disagree with the last wave")
    for row in counter_rows:
        row_policy_version = row["policy_version"]
        if (
            str(row["last_wave_id"] or "") != wave_id
            or type(row_policy_version) is not int
            or row_policy_version != policy_version
            or str(row["updated_run_id"] or "") != run_id
            or str(row["updated_dispatch_id"] or "") != dispatch_id
        ):
            errors.append(
                f"scheduler fairness counter metadata is inconsistent for {row['candidate_id']}"
            )
    return errors


def _scheduler_decision_fairness_state_errors(
    conn: sqlite3.Connection,
) -> List[str]:
    """Check generic/nested counters against their last primary decision."""

    errors: List[str] = []
    meta_rows = conn.execute(
        "SELECT last_decision_id, last_state_revision, policy_version, "
        "updated_run_id, updated_dispatch_id "
        "FROM scheduler_decision_fairness_meta ORDER BY singleton"
    ).fetchall()
    counter_rows = conn.execute(
        "SELECT candidate_id, consecutive_deferrals, last_decision_id, "
        "policy_version, updated_run_id, updated_dispatch_id "
        "FROM scheduler_decision_deferrals "
        "ORDER BY candidate_id"
    ).fetchall()
    if len(meta_rows) > 1:
        return ["scheduler decision fairness state has multiple metadata rows"]
    if not meta_rows:
        if counter_rows:
            errors.append("scheduler decision fairness counters have no metadata row")
        return errors
    meta = meta_rows[0]
    decision_id = meta["last_decision_id"]
    run_id = str(meta["updated_run_id"] or "")
    dispatch_id = str(meta["updated_dispatch_id"] or "")
    state_revision = meta["last_state_revision"]
    policy_version = meta["policy_version"]
    if not isinstance(decision_id, str) or not decision_id:
        errors.append("scheduler decision fairness identifier is invalid")
    if bool(run_id) == bool(dispatch_id):
        errors.append("scheduler decision fairness provenance is invalid")
        return errors
    if type(policy_version) is not int or policy_version <= 0:
        errors.append("scheduler decision fairness policy version is invalid")
        return errors
    if type(state_revision) is not int or state_revision < 0:
        errors.append("scheduler decision fairness state revision is invalid")
        return errors
    if dispatch_id:
        provenance = conn.execute(
            "SELECT decision_state_revision AS state_revision, decision_trace_json "
            "FROM scheduler_dispatches WHERE dispatch_id = ?",
            (dispatch_id,),
        ).fetchone()
        provenance_label = "dispatch"
        provenance_id = dispatch_id
    else:
        provenance = conn.execute(
            "SELECT state_revision, decision_trace_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        provenance_label = "run"
        provenance_id = run_id
    if provenance is None:
        errors.append(
            "scheduler decision fairness metadata references a missing "
            f"{provenance_label}"
        )
        return errors
    trace = json_loads(provenance["decision_trace_json"], {})
    if not isinstance(trace, dict):
        errors.append("scheduler decision fairness run trace is malformed")
        return errors
    if decision_trace_is_parallel_companion(trace):
        errors.append(
            "scheduler decision fairness metadata references a companion "
            f"{provenance_label}"
        )
        return errors
    wave = trace.get("parallel_wave_admission")
    expected_decision_id = (
        str(wave.get("wave_id") or "")
        if isinstance(wave, dict)
        else provenance_id
    )
    if decision_id != expected_decision_id:
        errors.append(
            "scheduler decision fairness metadata disagrees with its "
            f"{provenance_label}"
        )
    if state_revision != provenance["state_revision"]:
        errors.append(
            "scheduler decision fairness state revision disagrees with its "
            f"{provenance_label}"
        )
    if trace.get("decision_policy_version") != policy_version:
        errors.append(
            "scheduler decision fairness policy version disagrees with its "
            f"{provenance_label}"
        )
    try:
        expected = decision_deferral_state_after_trace(
            {}, trace, enforce_prior_counts=False
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        errors.append(f"scheduler decision fairness run trace is invalid: {exc}")
        return errors
    observed: Dict[str, int] = {}
    for row in counter_rows:
        candidate_id = row["candidate_id"]
        count = row["consecutive_deferrals"]
        if not isinstance(candidate_id, str) or not candidate_id:
            errors.append(
                "scheduler decision fairness counter has an invalid candidate identifier"
            )
            continue
        if type(count) is not int or count <= 0:
            errors.append(
                f"scheduler decision fairness counter is invalid for {candidate_id}"
            )
            continue
        observed[candidate_id] = count
        if (
            row["last_decision_id"] != decision_id
            or row["policy_version"] != policy_version
            or str(row["updated_run_id"] or "") != run_id
            or str(row["updated_dispatch_id"] or "") != dispatch_id
        ):
            errors.append(
                f"scheduler decision fairness counter metadata is inconsistent for {candidate_id}"
            )
    if observed != expected:
        errors.append("scheduler decision fairness counters disagree with the last decision")
    return errors


def _typed_relation_mirror_errors(conn: sqlite3.Connection) -> List[str]:
    """Require compatibility JSON and FK-backed relations to agree exactly."""

    errors: List[str] = []
    specs = (
        ("claims", "claim_id", "parent_ids_json", "claim_parent_relations", "claim_id", "parent_claim_id"),
        (
            "inferences",
            "inference_id",
            "condition_claim_ids_json",
            "inference_condition_claims",
            "inference_id",
            "condition_claim_id",
        ),
        ("claims", "claim_id", "evidence_artifact_ids_json", "claim_evidence_artifacts", "claim_id", "artifact_id"),
        ("routes", "route_id", "evidence_artifact_ids_json", "route_evidence_artifacts", "route_id", "artifact_id"),
        (
            "inferences",
            "inference_id",
            "evidence_artifact_ids_json",
            "inference_evidence_artifacts",
            "inference_id",
            "artifact_id",
        ),
        (
            "theorem_library_entries",
            "entry_id",
            "evidence_artifact_ids_json",
            "theorem_library_evidence_artifacts",
            "entry_id",
            "artifact_id",
        ),
        (
            "debts",
            "debt_id",
            "source_artifact_ids_json",
            "proof_obligation_source_artifacts",
            "proof_obligation_id",
            "artifact_id",
        ),
    )
    for source, source_key, json_column, relation, relation_key, target_column in specs:
        for row in conn.execute(
            f"SELECT {source_key}, {json_column} FROM {source} ORDER BY {source_key}"
        ):
            expected_raw = json_loads(row[json_column], None)
            if not isinstance(expected_raw, list):
                errors.append(
                    f"{source}.{json_column} for {row[source_key]} is not a JSON list"
                )
                continue
            expected = [str(item) for item in expected_raw]
            actual = [
                str(item[target_column])
                for item in conn.execute(
                    f"SELECT {target_column} FROM {relation} WHERE {relation_key} = ? ORDER BY position",
                    (row[source_key],),
                )
            ]
            if expected != actual:
                errors.append(
                    f"typed relation {relation} disagrees with {source}.{json_column} for {row[source_key]}"
                )

    for row in conn.execute(
        "SELECT debt_id, resolution_evidence_json FROM debts ORDER BY debt_id"
    ):
        payload = json_loads(row["resolution_evidence_json"], {})
        if not isinstance(payload, dict):
            errors.append(
                f"proof obligation {row['debt_id']} has non-object resolution evidence"
            )
            continue
        expected_raw = payload.get("resolution_evidence_artifact_ids")
        if expected_raw is None:
            expected_raw = payload.get("evidence_artifact_ids", [])
        expected = [str(item) for item in expected_raw] if isinstance(expected_raw, list) else []
        actual = [
            str(item["artifact_id"])
            for item in conn.execute(
                "SELECT artifact_id FROM proof_obligation_resolution_artifacts "
                "WHERE proof_obligation_id = ? ORDER BY position",
                (row["debt_id"],),
            )
        ]
        if expected != actual:
            errors.append(
                "typed proof-obligation resolution evidence disagrees with compatibility JSON "
                f"for {row['debt_id']}"
            )

    for row in conn.execute(
        "SELECT debt_id, owner_type, owner_id FROM debts ORDER BY debt_id"
    ):
        owner = conn.execute(
            "SELECT * FROM proof_obligation_owners WHERE proof_obligation_id = ?",
            (row["debt_id"],),
        ).fetchone()
        expected_column = {
            "claim": "owner_claim_id",
            "route": "owner_route_id",
            "inference": "owner_inference_id",
            "artifact": "owner_artifact_id",
        }.get(str(row["owner_type"] or ""))
        if owner is None or expected_column is None or str(owner[expected_column] or "") != str(
            row["owner_id"] or ""
        ):
            errors.append(
                f"typed proof-obligation owner disagrees with compatibility columns for {row['debt_id']}"
            )
    return errors


def _scheduler_dispatch_errors(
    conn: sqlite3.Connection,
    *,
    pending_dispatch_ids: Set[str],
    only_dispatch_ids: Set[str] | None = None,
) -> List[str]:
    """Validate durable dispatch rows and their hash-chained operations."""

    errors: List[str] = []
    recorded: Dict[str, Dict[str, Any]] = {}
    validated_actions: Dict[str, tuple[str, Dict[str, Any]]] = {}
    if only_dispatch_ids is None:
        for patch in conn.execute(
            "SELECT operations_json FROM patches WHERE status = 'applied' "
            "ORDER BY applied_revision"
        ):
            for operation in json_loads(patch["operations_json"], []):
                if not isinstance(operation, dict) or str(
                    operation.get("op") or ""
                ) != "record_scheduler_dispatch":
                    continue
                dispatch_id = str(operation.get("dispatch_id") or "")
                if dispatch_id in recorded:
                    errors.append(
                        f"scheduler dispatch {dispatch_id} has more than one record operation"
                    )
                recorded[dispatch_id] = operation
    if only_dispatch_ids is not None and not only_dispatch_ids:
        return errors
    groups: Dict[str, list[sqlite3.Row]] = {}
    randomized_certificates: list[Any] = []
    if only_dispatch_ids is None:
        dispatch_query = (
            "SELECT * FROM scheduler_dispatches "
            "ORDER BY dispatch_group_id, dispatch_position"
        )
        dispatch_parameters: tuple[str, ...] = ()
    else:
        requested_dispatch_ids = tuple(sorted(only_dispatch_ids))
        placeholders = ", ".join("?" for _ in requested_dispatch_ids)
        dispatch_query = (
            f"SELECT * FROM scheduler_dispatches WHERE dispatch_id IN ({placeholders}) "
            "ORDER BY dispatch_group_id, dispatch_position"
        )
        dispatch_parameters = requested_dispatch_ids
    for row in conn.execute(dispatch_query, dispatch_parameters):
        dispatch_id = str(row["dispatch_id"] or "")
        group_id = str(row["dispatch_group_id"] or "")
        groups.setdefault(group_id, []).append(row)
        operation = recorded.get(dispatch_id)
        trace = json_loads(row["decision_trace_json"], {})
        raw_dispatched_action = row["dispatched_action_json"]
        execution_contract = json_loads(row["execution_contract_json"], None)
        action_hash = str(row["dispatched_action_hash"] or "")
        cached_action = validated_actions.get(action_hash)
        if cached_action is not None and cached_action[0] == raw_dispatched_action:
            dispatched_action = cached_action[1]
        else:
            dispatched_action = json_loads(raw_dispatched_action, None)
        trace_errors = decision_trace_errors(trace) if isinstance(trace, dict) else [
            "decision trace is not an object"
        ]
        if trace_errors:
            errors.append(
                f"scheduler dispatch {dispatch_id} has invalid decision provenance"
            )
        design = str(row["selection_design"] or "")
        if (
            not isinstance(trace, dict)
            or str(trace.get("candidate_set_sha256") or "")
            != str(row["candidate_set_hash"] or "")
            or trace.get("decision_policy_version")
            != row["selection_policy_version"]
            or str(trace.get("dispatched_action_sha256") or "")
            != str(row["dispatched_action_hash"] or "")
            or decision_trace_is_parallel_companion(trace)
            != bool(row["is_companion"])
        ):
            errors.append(
                f"scheduler dispatch {dispatch_id} disagrees with its decision trace"
            )
        if design == "deterministic":
            if isinstance(trace, dict) and trace.get("randomized_assignment") is not None:
                errors.append(
                    f"deterministic scheduler dispatch {dispatch_id} contains randomized assignment"
                )
        elif design == "randomized":
            if isinstance(trace, dict):
                if int(row["dispatch_position"] or 0) == 0:
                    randomized_certificates.append(
                        trace.get("randomized_assignment")
                    )
                assignment_wave = trace.get("parallel_wave_admission")
                assignment_errors = randomized_assignment_errors(
                    trace.get("randomized_assignment"),
                    candidate_set_sha256=str(row["candidate_set_hash"] or ""),
                    selection_policy_version=int(
                        row["selection_policy_version"] or 0
                    ),
                    dispatched_action_sha256=str(
                        row["dispatched_action_hash"] or ""
                    ),
                    parallel_admission_policy_version=(
                        assignment_wave.get("policy_version")
                        if isinstance(assignment_wave, dict)
                        and type(assignment_wave.get("policy_version")) is int
                        else None
                    ),
                )
                try:
                    assignment_metadata = randomized_assignment_metadata(trace)
                except ValueError:
                    assignment_metadata = None
                if (
                    assignment_errors
                    or assignment_metadata is None
                    or assignment_metadata["candidate_set_hash"]
                    != str(row["candidate_set_hash"] or "")
                    or assignment_metadata["selection_policy_version"]
                    != int(row["selection_policy_version"] or 0)
                ):
                    errors.append(
                        f"randomized scheduler dispatch {dispatch_id} has invalid assignment provenance"
                    )
        else:
            errors.append(
                f"scheduler dispatch {dispatch_id} has invalid selection design {design}"
            )
        if dispatched_action is not None:
            try:
                action_hash_matches = (
                    isinstance(dispatched_action, dict)
                    and "decision_trace" not in dispatched_action
                    and action_sha256(dispatched_action)
                    == str(row["dispatched_action_hash"] or "")
                )
            except (TypeError, ValueError, OverflowError):
                action_hash_matches = False
            if (
                not action_hash_matches
                or str(dispatched_action.get("mode") or "")
                != str(row["mode"] or "")
                or str(dispatched_action.get("target_id") or "")
                != str(row["target_id"] or "")
                or str(dispatched_action.get("route_id") or "")
                != str(row["route_id"] or "")
            ):
                errors.append(
                    f"scheduler dispatch {dispatch_id} has an invalid recovery action"
                )
            elif isinstance(dispatched_action, dict):
                validated_actions[action_hash] = (
                    str(raw_dispatched_action),
                    dispatched_action,
                )
        if execution_contract is not None and execution_contract_errors(
            execution_contract
        ):
            errors.append(
                f"scheduler dispatch {dispatch_id} has an invalid execution contract"
            )
        if operation is None:
            if dispatch_id not in pending_dispatch_ids:
                errors.append(
                    f"scheduler dispatch {dispatch_id} has no hash-chained record operation"
                )
        else:
            expected = {
                "dispatch_group_id": str(operation.get("dispatch_group_id") or ""),
                "dispatch_position": operation.get("dispatch_position"),
                "is_companion": int(bool(operation.get("is_companion"))),
                "actor_role": str(operation.get("actor_role") or ""),
                "mode": str(operation.get("mode") or ""),
                "target_id": str(operation.get("target_id") or ""),
                "route_id": str(operation.get("route_id") or ""),
                "decision_state_revision": operation.get("decision_state_revision"),
                "proof_state_hash": str(operation.get("proof_state_hash") or ""),
                "prior_run_provenance_hash": str(
                    operation.get("prior_run_provenance_hash") or ""
                ),
                "selection_design": str(operation.get("selection_design") or ""),
                "candidate_set_hash": str(operation.get("candidate_set_hash") or ""),
                "selection_policy_version": operation.get(
                    "selection_policy_version"
                ),
                "dispatched_action_hash": str(
                    operation.get("dispatched_action_hash") or ""
                ),
                "committed_at": str(operation.get("committed_at") or ""),
            }
            operation_action = operation.get("dispatched_action")
            if isinstance(operation_action, Mapping):
                if dict(operation_action) != dispatched_action:
                    errors.append(
                        f"scheduler dispatch {dispatch_id} recovery action "
                        "disagrees with its hash-chained operation"
                    )
            elif row["dispatched_action_json"] is not None:
                errors.append(
                    f"scheduler dispatch {dispatch_id} has a recovery action "
                    "without a hash-chained operation"
                )
            if operation.get("decision_trace") != trace:
                errors.append(
                    f"scheduler dispatch {dispatch_id} decision trace "
                    "disagrees with its hash-chained operation"
                )
            operation_contract = operation.get("execution_contract")
            if isinstance(operation_contract, Mapping):
                if dict(operation_contract) != execution_contract:
                    errors.append(
                        f"scheduler dispatch {dispatch_id} execution contract "
                        "disagrees with its hash-chained operation"
                    )
            elif row["execution_contract_json"] is not None:
                errors.append(
                    f"scheduler dispatch {dispatch_id} has an execution contract "
                    "without a hash-chained operation"
                )
            for field, value in expected.items():
                if row[field] != value:
                    errors.append(
                        f"scheduler dispatch {dispatch_id} field {field} "
                        "disagrees with its hash-chained operation"
                    )
    # Cohort properties (unit/exposure uniqueness, contiguity, and fixed
    # design) require the complete history. Incremental validation receives
    # only the newly inserted group; the transactional patch validator enforces
    # the corresponding transition against indexed prior state.
    if only_dispatch_ids is None:
        errors.extend(randomized_assignment_cohort_errors(randomized_certificates))
        active_workflow_assignment = ""
        for sequence_row in conn.execute(
            "SELECT d.dispatch_id, d.decision_trace_json "
            "FROM scheduler_source_entries AS s "
            "JOIN scheduler_dispatches AS d ON d.dispatch_id = s.record_id "
            "WHERE s.record_kind = 'dispatch' AND d.dispatch_position = 0 "
            "ORDER BY s.sequence"
        ):
            sequence_trace = json_loads(
                sequence_row["decision_trace_json"], {}
            )
            sequence_certificate = (
                sequence_trace.get("randomized_assignment")
                if isinstance(sequence_trace, dict)
                else None
            )
            sequence_assignment = (
                str(sequence_certificate.get("assignment_input_sha256") or "")
                if isinstance(sequence_certificate, dict)
                and sequence_certificate.get("protocol_version")
                in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
                else ""
            )
            if active_workflow_assignment and (
                sequence_assignment != active_workflow_assignment
            ):
                errors.append(
                    "active workflow randomized assignment does not govern "
                    f"scheduler dispatch {sequence_row['dispatch_id']}"
                )
            elif sequence_assignment:
                active_workflow_assignment = sequence_assignment
    for group_id, rows in groups.items():
        randomized_group_certificates = []
        for row in rows:
            if str(row["selection_design"] or "") != "randomized":
                continue
            group_trace = json_loads(row["decision_trace_json"], {})
            if isinstance(group_trace, dict) and isinstance(
                group_trace.get("randomized_assignment"), dict
            ):
                randomized_group_certificates.append(
                    group_trace["randomized_assignment"]
                )
        if randomized_group_certificates:
            if len(randomized_group_certificates) != len(rows):
                errors.append(
                    f"scheduler dispatch group {group_id} mixes randomized and deterministic provenance"
                )
            else:
                core_fields = (
                    "protocol_version",
                    "experiment_id",
                    "assignment_unit_id",
                    "assignment_scope",
                    "exposure_index",
                    "assignment_input_sha256",
                    "selected_arm_id",
                    "selected_policy_version",
                )
                first = randomized_group_certificates[0]
                if any(
                    any(certificate.get(field) != first.get(field) for field in core_fields)
                    for certificate in randomized_group_certificates[1:]
                ):
                    errors.append(
                        f"scheduler dispatch group {group_id} has inconsistent randomized assignment"
                    )
        positions = [int(row["dispatch_position"]) for row in rows]
        if not group_id or positions != list(range(len(rows))):
            errors.append(
                f"scheduler dispatch group {group_id or '<empty>'} is not contiguous"
            )
        if sum(not bool(row["is_companion"]) for row in rows) != 1:
            errors.append(
                f"scheduler dispatch group {group_id or '<empty>'} has invalid primary membership"
            )
        snapshot_keys = {
            (
                row["decision_state_revision"],
                row["proof_state_hash"],
                row["prior_run_provenance_hash"],
                row["committed_at"],
            )
            for row in rows
        }
        if len(snapshot_keys) != 1:
            errors.append(
                f"scheduler dispatch group {group_id or '<empty>'} mixes planning snapshots"
            )
        wave_ids = set()
        wave_bindings: set[str] = set()
        group_waves: list[Mapping[str, Any]] = []
        for row in rows:
            trace = json_loads(row["decision_trace_json"], {})
            wave = (
                trace.get("parallel_wave_admission")
                if isinstance(trace, dict)
                else None
            )
            if isinstance(wave, dict):
                group_waves.append(wave)
                wave_ids.add(str(wave.get("wave_id") or ""))
                binding = trace.get("parallel_wave_candidate_id")
                if isinstance(binding, str) and binding:
                    wave_bindings.add(binding)
            else:
                wave_ids.add("")
        if len(rows) > 1 and (
            len(wave_ids) != 1 or not next(iter(wave_ids), "")
        ):
            errors.append(
                f"scheduler dispatch group {group_id or '<empty>'} mixes parallel waves"
            )
        if group_waves:
            primary_wave = group_waves[0]
            raw_candidates = primary_wave.get("candidates")
            expected_bindings = {
                str(candidate.get("candidate_id") or "")
                for candidate in raw_candidates
                if isinstance(candidate, Mapping)
                and candidate.get("disposition") in {"fixed_primary", "selected"}
            } if isinstance(raw_candidates, list) else set()
            if (
                len(group_waves) != len(rows)
                or not expected_bindings
                or wave_bindings != expected_bindings
            ):
                errors.append(
                    f"scheduler dispatch group {group_id or '<empty>'} does not contain exactly its admitted parallel wave"
                )
            for row in rows:
                trace = json_loads(row["decision_trace_json"], {})
                binding = (
                    str(trace.get("parallel_wave_candidate_id") or "")
                    if isinstance(trace, dict)
                    else ""
                )
                matching = [
                    candidate
                    for candidate in raw_candidates
                    if isinstance(candidate, Mapping)
                    and str(candidate.get("candidate_id") or "") == binding
                ] if isinstance(raw_candidates, list) else []
                dispatched_action = json_loads(row["dispatched_action_json"], None)
                if len(matching) != 1 or not isinstance(dispatched_action, dict):
                    continue
                source_action = dict(dispatched_action)
                source_action.pop("parallel_wave_admission", None)
                source_action.pop("parallel_wave_candidate_id", None)
                source_action.pop("parallel_companion_index", None)
                allocation = source_action.get("budget")
                if isinstance(allocation, Mapping) and allocation.get(
                    "wave_budget_adjusted"
                ) is True:
                    restored_allocation = dict(allocation)
                    original_request = restored_allocation.pop(
                        "wave_requested_tokens_before_admission", None
                    )
                    restored_allocation.pop("wave_budget_adjusted", None)
                    if type(original_request) is int and original_request >= 0:
                        restored_allocation["requested_tokens"] = original_request
                    source_action["budget"] = restored_allocation
                try:
                    source_digest = action_sha256(source_action)
                except (TypeError, ValueError, OverflowError):
                    source_digest = ""
                if source_digest != str(
                    matching[0].get("comparison_action_sha256") or ""
                ):
                    errors.append(
                        f"scheduler dispatch {row['dispatch_id']} action disagrees with its admitted parallel-wave input"
                    )
        elif len(rows) != 1:
            errors.append(
                f"scheduler dispatch group {group_id or '<empty>'} has multiple actions without a parallel wave"
            )
    if only_dispatch_ids is not None:
        return errors
    linked: Set[str] = set()
    for run in conn.execute(
        "SELECT run_id, scheduler_dispatch_id, dispatched_action_hash, "
        "state_revision, context_revision, decision_state_revision, actor_role, "
        "mode, target_id, route_id, "
        "selection_design, candidate_set_hash, selection_policy_version, "
        "decision_trace_json FROM runs WHERE scheduler_dispatch_id IS NOT NULL"
    ):
        dispatch_id = str(run["scheduler_dispatch_id"] or "")
        if dispatch_id in linked:
            errors.append(f"scheduler dispatch {dispatch_id} has multiple runs")
        linked.add(dispatch_id)
        dispatch = conn.execute(
            "SELECT * FROM scheduler_dispatches WHERE dispatch_id = ?",
            (dispatch_id,),
        ).fetchone()
        if dispatch is None:
            errors.append(
                f"run {run['run_id']} references a missing scheduler dispatch"
            )
            continue
        if (
            str(run["dispatched_action_hash"] or "")
            != str(dispatch["dispatched_action_hash"] or "")
            or run["decision_state_revision"]
            != dispatch["decision_state_revision"]
            or run["state_revision"] != run["context_revision"]
            or int(run["context_revision"] or 0)
            <= int(dispatch["decision_state_revision"] or 0)
            or run["actor_role"] != dispatch["actor_role"]
            or run["mode"] != dispatch["mode"]
            or run["target_id"] != dispatch["target_id"]
            or run["route_id"] != dispatch["route_id"]
            or run["selection_design"] != dispatch["selection_design"]
            or run["candidate_set_hash"] != dispatch["candidate_set_hash"]
            or run["selection_policy_version"]
            != dispatch["selection_policy_version"]
            or run["decision_trace_json"] != dispatch["decision_trace_json"]
        ):
            errors.append(
                f"run {run['run_id']} disagrees with scheduler dispatch {dispatch_id}"
            )
    errors.extend(_scheduler_dispatch_execution_errors(conn))
    provenance_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' "
        "AND name = 'scheduler_provenance_entries'"
    ).fetchone()
    provenance_version = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = 15"
    ).fetchone()
    if provenance_table is not None and provenance_version is not None:
        from .scheduler_provenance import scheduler_provenance_errors

        errors.extend(scheduler_provenance_errors(conn))
    return errors


def _scheduler_dispatch_execution_errors(conn: sqlite3.Connection) -> List[str]:
    """Validate attempt/result records against their hash-chained events."""

    errors: List[str] = []
    dispatch_records = {
        str(row["dispatch_id"] or ""): row
        for row in conn.execute(
            "SELECT dispatch_id, actor_role, mode, target_id, route_id, "
            "execution_contract_json FROM scheduler_dispatches"
        )
    }
    dispatch_contracts = {
        dispatch_id: json_loads(row["execution_contract_json"], None)
        for dispatch_id, row in dispatch_records.items()
    }
    execution_events = {
        int(row["event_id"]): row
        for row in conn.execute(
            "SELECT event_id, event_type, payload_json FROM events WHERE event_type IN ("
            "'scheduler_dispatch_attempt_claimed', "
            "'scheduler_dispatch_result_recorded')"
        )
        if isinstance(row["event_id"], int)
    }
    runs_by_dispatch = {
        str(row["scheduler_dispatch_id"] or ""): str(row["run_id"] or "")
        for row in conn.execute(
            "SELECT run_id, scheduler_dispatch_id FROM runs "
            "WHERE scheduler_dispatch_id IS NOT NULL"
        )
    }
    run_dispatch_by_id = {
        str(row["run_id"] or ""): str(row["scheduler_dispatch_id"] or "")
        for row in conn.execute(
            "SELECT run_id, scheduler_dispatch_id FROM runs"
        )
    }
    attempts_by_id: Dict[str, sqlite3.Row] = {}
    attempt_numbers: Dict[str, list[int]] = {}
    attempt_event_ids: Set[int] = set()
    for row in conn.execute(
        "SELECT * FROM scheduler_dispatch_attempts "
        "ORDER BY dispatch_id, attempt_number"
    ):
        attempt_id = str(row["attempt_id"] or "")
        dispatch_id = str(row["dispatch_id"] or "")
        attempt_number = _scheduler_execution_integer(
            row["attempt_number"],
            label=f"scheduler attempt {attempt_id or '<empty>'} number",
            errors=errors,
            minimum=1,
        )
        attempts_by_id[attempt_id] = row
        attempt_numbers.setdefault(dispatch_id, []).append(attempt_number)
        event_id = _scheduler_execution_integer(
            row["event_id"],
            label=f"scheduler attempt {attempt_id or '<empty>'} event id",
            errors=errors,
            minimum=1,
        )
        attempt_event_ids.add(event_id)
        contract = dispatch_contracts.get(dispatch_id)
        event = execution_events.get(event_id)
        try:
            payload = (
                json_loads(event["payload_json"], None)
                if event is not None
                else None
            )
        except (TypeError, ValueError, OverflowError):
            contract = None
            payload = None
        expected_payload = {
            "attempt_id": attempt_id,
            "dispatch_id": dispatch_id,
            "attempt_number": attempt_number,
            "session_plan_hash": str(row["session_plan_hash"] or ""),
            "executor_identity": str(row["executor_identity"] or ""),
            "claimed_at": str(row["claimed_at"] or ""),
        }
        if (
            dispatch_id not in dispatch_contracts
            or not attempt_id
            or attempt_id
            != f"attempt-{dispatch_id}-{attempt_number}"
            or attempt_number <= 0
            or len(str(row["session_plan_hash"] or "")) != 64
            or not isinstance(contract, dict)
            or str(contract.get("identity") or "")
            != str(row["executor_identity"] or "")
            or event is None
            or str(event["event_type"] or "")
            != "scheduler_dispatch_attempt_claimed"
            or payload != expected_payload
        ):
            errors.append(
                f"scheduler attempt {attempt_id or '<empty>'} has invalid provenance"
            )
    for dispatch_id, numbers in attempt_numbers.items():
        if numbers != list(range(1, len(numbers) + 1)):
            errors.append(
                f"scheduler dispatch {dispatch_id} has non-contiguous attempt numbers"
            )

    result_event_ids: Set[int] = set()
    for row in conn.execute(
        "SELECT * FROM scheduler_dispatch_results ORDER BY result_id"
    ):
        result_id = str(row["result_id"] or "")
        dispatch_id = str(row["dispatch_id"] or "")
        attempt_id = str(row["attempt_id"] or "")
        has_reserved_run_id = "run_id" in row.keys()
        recorded_run_id = (
            str(row["run_id"] or "")
            if has_reserved_run_id
            else ""
        )
        result_hash = str(row["result_hash"] or "")
        event_id = _scheduler_execution_integer(
            row["event_id"],
            label=f"scheduler result {result_id or '<empty>'} event id",
            errors=errors,
            minimum=1,
        )
        result_event_ids.add(event_id)
        attempt = attempts_by_id.get(attempt_id)
        dispatch = dispatch_records.get(dispatch_id)
        event = execution_events.get(event_id)
        try:
            plan = json_loads(row["session_plan_json"], None)
            execution = json_loads(row["execution_json"], None)
            validation_errors = json_loads(row["validation_errors_json"], None)
            event_payload = (
                json_loads(event["payload_json"], None)
                if event is not None
                else None
            )
            observed_hash = (
                dispatch_result_sha256(
                    dispatch_id=dispatch_id,
                    attempt_id=attempt_id,
                    session_plan=plan,
                    execution=execution,
                    validation_errors=validation_errors,
                )
                if isinstance(plan, dict)
                and isinstance(execution, dict)
                and isinstance(validation_errors, list)
                and all(isinstance(error, str) for error in validation_errors)
                else ""
            )
            observed_plan_hash = (
                dispatch_json_sha256(plan) if isinstance(plan, dict) else ""
            )
        except (TypeError, ValueError, OverflowError):
            plan = None
            execution = None
            validation_errors = None
            event_payload = None
            observed_hash = ""
            observed_plan_hash = ""
        expected_payload = {
            "result_id": result_id,
            "dispatch_id": dispatch_id,
            "attempt_id": attempt_id,
            "result_hash": result_hash,
            "completed_at": str(row["completed_at"] or ""),
        }
        run_id = runs_by_dispatch.get(dispatch_id)
        result_patch = (
            execution.get("patch") if isinstance(execution, dict) else None
        )
        source_identity_errors = (
            durable_path_source_identity_errors(
                execution,
                allow_unbound=bool(validation_errors),
            )
            if isinstance(execution, dict)
            and isinstance(validation_errors, list)
            else ["malformed scheduler result"]
        )
        if (
            attempt is None
            or str(attempt["dispatch_id"] or "") != dispatch_id
            or result_id != f"result-{dispatch_id}"
            or dispatch is None
            or not isinstance(plan, dict)
            or not isinstance(execution, dict)
            or str(plan.get("scheduler_dispatch_id") or "") != dispatch_id
            or str(plan.get("actor_role") or "")
            != str(dispatch["actor_role"] or "")
            or str(plan.get("mode") or "") != str(dispatch["mode"] or "")
            or str(plan.get("target_id") or "")
            != str(dispatch["target_id"] or "")
            or str(plan.get("route_id") or "")
            != str(dispatch["route_id"] or "")
            or observed_plan_hash != str(attempt["session_plan_hash"] or "")
            or observed_hash != result_hash
            or (has_reserved_run_id and not recorded_run_id)
            or (
                recorded_run_id in run_dispatch_by_id
                and run_dispatch_by_id[recorded_run_id] != dispatch_id
            )
            or (
                recorded_run_id
                and recorded_run_id != str(execution.get("run_id") or "")
            )
            or source_identity_errors
            or (
                isinstance(result_patch, dict)
                and str(result_patch.get("patch_id") or "")
                != f"dispatch-output-{dispatch_id}"
            )
            or event is None
            or str(event["event_type"] or "")
            != "scheduler_dispatch_result_recorded"
            or event_payload != expected_payload
            or (
                run_id is not None
                and run_id != str(execution.get("run_id") or "")
            )
        ):
            errors.append(
                f"scheduler result {result_id or '<empty>'} has invalid provenance"
            )

    for event in execution_events.values():
        event_id = _scheduler_execution_integer(
            event["event_id"],
            label="scheduler execution event id",
            errors=errors,
            minimum=1,
        )
        event_type = str(event["event_type"] or "")
        if (
            event_type == "scheduler_dispatch_attempt_claimed"
            and event_id not in attempt_event_ids
        ) or (
            event_type == "scheduler_dispatch_result_recorded"
            and event_id not in result_event_ids
        ):
            errors.append(
                f"scheduler execution event {event_id} has no corresponding record"
            )
    return errors


def _scheduler_execution_integer(
    value: Any,
    *,
    label: str,
    errors: List[str],
    minimum: int = 0,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{label} is not an integer")
        return minimum - 1
    if value < minimum:
        errors.append(f"{label} is below its minimum value {minimum}")
        return minimum - 1
    return value


def _run_assignment_provenance_errors(
    conn: sqlite3.Connection,
    *,
    pending_run_ids: Set[str],
    run_ids: Set[str] | None = None,
) -> List[str]:
    """Bind v4 assignment columns to the hash-chained host operation."""

    errors: List[str] = []
    recorded: Dict[str, Dict[str, Any]] = {}
    if run_ids is None:
        for patch in conn.execute(
            "SELECT patch_id, operations_json FROM patches WHERE status = 'applied' ORDER BY applied_revision"
        ):
            for operation in json_loads(patch["operations_json"], []):
                if not isinstance(operation, dict) or str(operation.get("op") or "") != "record_run_metrics":
                    continue
                run_id = str(operation.get("run_id") or "")
                if run_id in recorded:
                    errors.append(f"run {run_id} has more than one record_run_metrics operation")
                recorded[run_id] = operation
    if run_ids is not None and not run_ids:
        return errors
    run_query = (
        "SELECT run_id, state_revision, decision_state_revision, strategy_family, "
        "selection_design, assignment_probability, exploration_stratum, "
        "candidate_set_hash, selection_policy_version, decision_trace_json, "
        "scheduler_dispatch_id, dispatched_action_hash FROM runs"
    )
    run_parameters: tuple[str, ...] = ()
    if run_ids is not None:
        requested_run_ids = tuple(sorted(run_ids))
        placeholders = ", ".join("?" for _ in requested_run_ids)
        run_query += f" WHERE run_id IN ({placeholders})"
        run_parameters = requested_run_ids
    run_query += " ORDER BY run_id"
    for run in conn.execute(run_query, run_parameters):
        run_id = str(run["run_id"] or "")
        operation = recorded.get(run_id)
        design = str(run["selection_design"] or "observational")
        if design == "observational":
            if (
                float(run["assignment_probability"] or 0.0) != 0.0
                or str(run["exploration_stratum"] or "")
                or str(run["candidate_set_hash"] or "")
                or int(run["selection_policy_version"] or 0) != 0
            ):
                errors.append(f"observational run {run_id} claims randomized-assignment metadata")
        elif design == "deterministic":
            trace = json_loads(run["decision_trace_json"], {})
            trace_candidates = trace.get("candidates", []) if isinstance(trace, dict) else []
            trace_policy_version = -1
            if isinstance(trace, dict):
                try:
                    trace_policy_version = int(
                        trace.get("decision_policy_version") or 0
                    )
                except (TypeError, ValueError, OverflowError):
                    pass
            if (
                float(run["assignment_probability"] or 0.0) != 0.0
                or str(run["exploration_stratum"] or "")
                or len(str(run["candidate_set_hash"] or "")) != 64
                or int(run["selection_policy_version"] or 0) < 1
                or not isinstance(trace, dict)
                or str(trace.get("candidate_set_sha256") or "")
                != str(run["candidate_set_hash"] or "")
                or trace_policy_version != int(run["selection_policy_version"] or 0)
                or not isinstance(trace_candidates, list)
                or any(not isinstance(row, dict) for row in trace_candidates)
                or candidate_rows_sha256(
                    trace_candidates,
                    decision_policy_version=trace_policy_version,
                )
                != str(run["candidate_set_hash"] or "")
            ):
                errors.append(f"deterministic run {run_id} has invalid decision provenance")
            elif decision_trace_errors(trace):
                errors.append(f"deterministic run {run_id} has an inconsistent decision trace")
            else:
                wave = trace.get("parallel_wave_admission")
                if (
                    isinstance(wave, dict)
                    and int(wave.get("policy_version") or 0) >= 4
                    and wave.get("state_revision")
                    != run["decision_state_revision"]
                ):
                    errors.append(
                        f"deterministic run {run_id} has the wrong decision revision"
                    )
        elif design == "randomized":
            trace = json_loads(run["decision_trace_json"], {})
            trace_candidates = (
                trace.get("candidates", []) if isinstance(trace, dict) else []
            )
            trace_policy_version = -1
            if isinstance(trace, dict):
                try:
                    trace_policy_version = int(
                        trace.get("decision_policy_version") or 0
                    )
                except (TypeError, ValueError, OverflowError):
                    pass
            try:
                assignment_probability = float(
                    run["assignment_probability"] or 0.0
                )
            except (TypeError, ValueError, OverflowError):
                assignment_probability = float("nan")
            randomized_trace_invalid = (
                not math.isfinite(assignment_probability)
                or not str(run["exploration_stratum"] or "")
                or len(str(run["candidate_set_hash"] or "")) != 64
                or int(run["selection_policy_version"] or 0) < 1
                or not isinstance(trace, dict)
                or str(trace.get("candidate_set_sha256") or "")
                != str(run["candidate_set_hash"] or "")
                or trace_policy_version
                != int(run["selection_policy_version"] or 0)
                or not isinstance(trace_candidates, list)
                or any(not isinstance(row, dict) for row in trace_candidates)
                or not str(run["scheduler_dispatch_id"] or "")
            )
            if not randomized_trace_invalid:
                try:
                    assignment_metadata = randomized_assignment_metadata(trace)
                    randomized_trace_invalid = (
                        candidate_rows_sha256(
                            trace_candidates,
                            decision_policy_version=trace_policy_version,
                        )
                        != str(run["candidate_set_hash"] or "")
                        or bool(decision_trace_errors(trace))
                        or bool(
                            randomized_assignment_errors(
                                trace.get("randomized_assignment"),
                                candidate_set_sha256=str(
                                    run["candidate_set_hash"] or ""
                                ),
                                selection_policy_version=int(
                                    run["selection_policy_version"] or 0
                                ),
                                assignment_probability=assignment_probability,
                                exploration_stratum=str(
                                    run["exploration_stratum"] or ""
                                ),
                                dispatched_action_sha256=str(
                                    run["dispatched_action_hash"] or ""
                                ),
                                parallel_admission_policy_version=(
                                    trace["parallel_wave_admission"].get(
                                        "policy_version"
                                    )
                                    if isinstance(
                                        trace.get("parallel_wave_admission"),
                                        dict,
                                    )
                                    and type(
                                        trace["parallel_wave_admission"].get(
                                            "policy_version"
                                        )
                                    )
                                    is int
                                    else None
                                ),
                            )
                        )
                        or assignment_metadata["assignment_probability"]
                        != assignment_probability
                        or assignment_metadata["exploration_stratum"]
                        != str(run["exploration_stratum"] or "")
                        or assignment_metadata["candidate_set_hash"]
                        != str(run["candidate_set_hash"] or "")
                        or assignment_metadata["selection_policy_version"]
                        != int(run["selection_policy_version"] or 0)
                    )
                except (TypeError, ValueError, OverflowError):
                    randomized_trace_invalid = True
            if randomized_trace_invalid:
                errors.append(
                    f"randomized run {run_id} has invalid assignment provenance"
                )
        else:
            errors.append(f"run {run_id} has invalid selection_design {design}")
        if operation is None:
            # During apply_patch the run row exists one transaction step before
            # its enclosing patch-journal row. The writer supplies the exact
            # transient identifiers; state revision cannot identify them
            # because ordinary run telemetry is recorded after the child patch.
            if run_id in pending_run_ids:
                continue
            if str(run["strategy_family"] or "") != "legacy_unclassified":
                errors.append(
                    f"run {run_id} has no hash-chained record_run_metrics operation"
                )
            continue
        default_strategy_family = (
            "legacy_unclassified"
            if "strategy_family" not in operation
            and str(run["strategy_family"] or "") == "legacy_unclassified"
            else "unclassified"
        )
        expected = {
            "strategy_family": str(
                operation.get("strategy_family") or default_strategy_family
            ),
            "selection_design": str(operation.get("selection_design") or "observational"),
            "exploration_stratum": str(operation.get("exploration_stratum") or ""),
            "candidate_set_hash": str(operation.get("candidate_set_hash") or ""),
            "selection_policy_version": int(operation.get("selection_policy_version") or 0),
            "decision_trace_json": json_dumps(operation.get("decision_trace") or {}),
            "decision_state_revision": int(
                operation.get(
                    "decision_state_revision",
                    operation.get("state_revision", 0),
                )
                or 0
            ),
            "scheduler_dispatch_id": (
                str(operation.get("scheduler_dispatch_id"))
                if operation.get("scheduler_dispatch_id")
                else None
            ),
            "dispatched_action_hash": str(
                operation.get("dispatched_action_hash") or ""
            ),
        }
        for field, value in expected.items():
            if run[field] != value:
                errors.append(f"run {run_id} field {field} disagrees with its hash-chained operation")
        expected_probability = float(operation.get("assignment_probability") or 0.0)
        if not math.isclose(
            float(run["assignment_probability"] or 0.0),
            expected_probability,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            errors.append(
                f"run {run_id} assignment_probability disagrees with its hash-chained operation"
            )
    return errors


def _directed_cycle_errors(edges: Dict[str, Set[str]], *, relation: str) -> List[str]:
    """Return deterministic cycle errors for a directed graph."""

    color: Dict[str, int] = {}
    stack: List[str] = []
    reported: Set[tuple[str, ...]] = set()
    errors: List[str] = []

    def visit(node: str) -> None:
        color[node] = 1
        stack.append(node)
        for neighbor in sorted(edges.get(node, set())):
            if neighbor not in edges:
                continue
            if color.get(neighbor, 0) == 0:
                visit(neighbor)
            elif color.get(neighbor) == 1:
                start = stack.index(neighbor)
                cycle = stack[start:] + [neighbor]
                members = tuple(sorted(set(cycle[:-1])))
                if members not in reported:
                    reported.add(members)
                    errors.append(f"{relation} cycle: {' -> '.join(cycle)}")
        stack.pop()
        color[node] = 2

    for node in sorted(edges):
        if color.get(node, 0) == 0:
            visit(node)
    return errors


def _inference_is_grounded(
    conn: sqlite3.Connection,
    inference_id: str,
    *,
    memo: Dict[str, bool],
    visiting: Set[str],
) -> bool:
    inference = conn.execute(
        "SELECT validation_status, condition_claim_ids_json, evidence_artifact_ids_json FROM inferences WHERE inference_id = ?",
        (inference_id,),
    ).fetchone()
    if inference is None or inference["validation_status"] not in VERIFIED_STATUSES:
        return False
    evidence_ids = json_loads(inference["evidence_artifact_ids_json"])
    if not _has_current_certificate(
        conn,
        evidence_ids,
        entity_type="inference",
        entity_id=inference_id,
        artifact_types={"verification_report", "formal_backend_result"},
    ):
        return False
    dependency_ids = [
        str(row["premise_claim_id"])
        for row in conn.execute(
            "SELECT premise_claim_id FROM inference_premises WHERE inference_id = ? ORDER BY position",
            (inference_id,),
        )
    ]
    dependency_ids.extend(
        str(item) for item in json_loads(inference["condition_claim_ids_json"]) if str(item)
    )
    return all(
        _claim_is_grounded(conn, claim_id, memo=memo, visiting=visiting)
        for claim_id in dependency_ids
    )


def _claim_is_grounded(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    memo: Dict[str, bool],
    visiting: Set[str],
) -> bool:
    if claim_id in memo:
        return memo[claim_id]
    if claim_id in visiting:
        return False
    claim = conn.execute(
        "SELECT validation_status, evidence_artifact_ids_json FROM claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    if claim is None or claim["validation_status"] not in VERIFIED_STATUSES:
        memo[claim_id] = False
        return False
    visiting.add(claim_id)
    evidence_ids = json_loads(claim["evidence_artifact_ids_json"])
    directly_certified = _has_current_certificate(
        conn,
        evidence_ids,
        entity_type="claim",
        entity_id=claim_id,
        artifact_types={"verification_report", "formal_backend_result"},
    )
    grounded = False
    for row in conn.execute(
        "SELECT inference_id FROM inferences WHERE conclusion_claim_id = ? AND validation_status IN ('informally_verified', 'formally_verified') ORDER BY inference_id",
        (claim_id,),
    ):
        if _inference_is_grounded(
            conn,
            str(row["inference_id"]),
            memo=memo,
            visiting=visiting,
        ):
            grounded = True
            break
    # A verifier may certify a premise-free proof directly on the claim.  For
    # claims used as premises this is a legitimate leaf, but a bare status with
    # no certificate is never a leaf.
    grounded = grounded or directly_certified
    visiting.remove(claim_id)
    memo[claim_id] = grounded
    return grounded


def _artifact_type(conn: sqlite3.Connection, artifact_id: str) -> str:
    row = conn.execute("SELECT artifact_type FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return row["artifact_type"] if row else ""


def _has_successful_formal_check(
    conn: sqlite3.Connection, artifact_ids: List[str]
) -> bool:
    for artifact_id in artifact_ids:
        row = conn.execute(
            "SELECT artifact_type, producer_role, metadata_json FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if (
            row is None
            or str(row["artifact_type"] or "") != "formal_backend_result"
            or str(row["producer_role"] or "") != "formal_backend"
        ):
            continue
        metadata = json_loads(row["metadata_json"], {})
        host_check = metadata.get("host_formal_check") if isinstance(metadata, dict) else None
        if isinstance(host_check, dict) and host_check.get("host_checked") is True:
            return True
    return False


def _has_verification_evidence(
    conn: sqlite3.Connection,
    artifact_ids: List[str],
    *,
    outcome: str,
) -> bool:
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
        if clean_verification_metadata(metadata, outcome=outcome):
            return True
    return False


def _has_current_certificate(
    conn: sqlite3.Connection,
    artifact_ids: Iterable[str],
    *,
    entity_type: str,
    entity_id: str,
    artifact_types: Set[str],
) -> bool:
    for artifact_id in artifact_ids:
        row = conn.execute(
            "SELECT artifact_type FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if row is None or str(row["artifact_type"] or "") not in artifact_types:
            continue
        if artifact_has_current_binding(
            conn,
            str(artifact_id),
            entity_type=entity_type,
            entity_id=entity_id,
        ):
            return True
    return False
