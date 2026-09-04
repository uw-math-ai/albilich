from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .artifacts import artifact_hash
from .authority import PatchAuthority
from .invariants import VERIFIED_STATUSES, validate_conn
from .models import json_dumps, json_loads
from .patches import (
    MAX_COPIED_ARTIFACT_BYTES,
    PatchRejected,
    _ArtifactFileJournal,
    _run_provenance_hash,
    _state_delta,
    _state_journal_projection,
    _state_projection_hash,
    append_applied_patch_entry,
)
from .store import ProofStateStore, utc_now


SAFE_IMPORT_STATUSES = {"paused", "stopped", "completed"}


def import_certified_scope(
    source: ProofStateStore,
    target: ProofStateStore,
    *,
    claim_id_patterns: Sequence[str],
    include_claim_ids: Sequence[str] = (),
    artifact_patterns: Sequence[str] = (),
    exclude_patterns: Sequence[str] = (),
) -> dict[str, Any]:
    """Merge a certified theorem subgraph into a differently rooted state.

    Only integrated claims matching ``claim_id_patterns`` are seed claims.
    Verified premise/condition claims and their valid integrated routes are
    pulled in recursively, so the imported graph remains independently valid.
    Run/session/patch history is deliberately not copied.  Evidence artifacts
    are copied into the target artifact directory and their paths are rewritten.

    Both stores must be quiescent.  The target root is immutable and is never
    replaced by the source root; imported source claims that named ``root`` as a
    parent therefore become children of the target theorem.
    """

    if source.problem_id == target.problem_id:
        raise ValueError("source and target proof states must differ")
    claim_regexes = _compile_patterns(claim_id_patterns, label="claim id")
    artifact_regexes = _compile_patterns(artifact_patterns, label="artifact")
    exclude_regexes = _compile_patterns(exclude_patterns, label="exclude")
    explicit = {str(item).strip() for item in include_claim_ids if str(item).strip()}
    if not claim_regexes and not explicit:
        raise ValueError("at least one claim id pattern or explicit claim id is required")

    with source.connect() as source_conn, target.connect() as target_conn:
        # Lock both stores in a process-independent canonical order.  The status
        # and revision checks below must describe the same quiescent snapshots
        # that are used for the import; otherwise resume or another import can
        # race between validation and mutation.
        lock_order = sorted(
            (
                (str(source.db_path.resolve()), source_conn),
                (str(target.db_path.resolve()), target_conn),
            ),
            key=lambda item: item[0],
        )
        for _, conn in lock_order:
            conn.execute("BEGIN IMMEDIATE")

        source_state = source_conn.execute("SELECT * FROM problem_state").fetchone()
        target_state = target_conn.execute("SELECT * FROM problem_state").fetchone()
        if source_state is None or target_state is None:
            raise ValueError("source and target must both be initialized")
        _require_quiescent(source_state, label="source")
        _require_quiescent(target_state, label="target")

        source_seal = source.current_state_seal(source_conn)
        if not source_seal["valid"]:
            raise ValueError(
                "source current-state seal is invalid: "
                + "; ".join(str(error) for error in source_seal["errors"][:8])
            )
        target_seal = target.current_state_seal(target_conn)
        if not target_seal["valid"]:
            raise ValueError(
                "target current-state seal is invalid: "
                + "; ".join(str(error) for error in target_seal["errors"][:8])
            )

        source_errors = validate_conn(source_conn)
        if source_errors:
            raise ValueError("source proof state is invalid: " + "; ".join(source_errors))
        target_errors = validate_conn(target_conn)
        if target_errors:
            raise ValueError("target proof state is invalid: " + "; ".join(target_errors))
        target_state_before = _state_journal_projection(target_conn)

        claims = {row["claim_id"]: dict(row) for row in source_conn.execute("SELECT * FROM claims")}
        routes = {row["route_id"]: dict(row) for row in source_conn.execute("SELECT * FROM routes")}
        inferences = {
            row["inference_id"]: dict(row) for row in source_conn.execute("SELECT * FROM inferences")
        }
        premises_by_inference: dict[str, list[dict[str, Any]]] = {}
        for row in source_conn.execute("SELECT * FROM inference_premises ORDER BY position"):
            premises_by_inference.setdefault(str(row["inference_id"]), []).append(dict(row))

        seed_claim_ids = {
            claim_id
            for claim_id, row in claims.items()
            if claim_id != "root"
            and row["lifecycle_status"] == "integrated"
            and _matches_any(claim_id, claim_regexes)
            and not _matches_any(_row_text(row), exclude_regexes)
        }
        for claim_id in explicit:
            row = claims.get(claim_id)
            if row is None:
                raise ValueError(f"explicit source claim does not exist: {claim_id}")
            if row["lifecycle_status"] != "integrated" or row["validation_status"] not in VERIFIED_STATUSES:
                raise ValueError(f"explicit source claim is not certified and integrated: {claim_id}")
            if _matches_any(_row_text(row), exclude_regexes):
                raise ValueError(f"explicit source claim is excluded by scope: {claim_id}")
            seed_claim_ids.add(claim_id)
        if not seed_claim_ids:
            raise ValueError("scope selector matched no integrated source claims")

        selected_claim_ids, selected_route_ids, selected_inference_ids = _dependency_closure(
            claims,
            routes,
            inferences,
            premises_by_inference,
            seed_claim_ids,
            exclude_regexes=exclude_regexes,
        )

        if str(source_state["root_statement"]) != str(target_state["root_statement"]):
            root_dependent_inferences = sorted(
                inference_id
                for inference_id in selected_inference_ids
                if "root"
                in {
                    *(
                        str(row["premise_claim_id"])
                        for row in premises_by_inference.get(inference_id, [])
                    ),
                    *(
                        str(item)
                        for item in json_loads(
                            inferences[inference_id]["condition_claim_ids_json"], []
                        )
                    ),
                }
            )
            if root_dependent_inferences:
                raise ValueError(
                    "certified dependency closure depends on the source root and cannot be rebound "
                    "to a different target root: " + ", ".join(root_dependent_inferences)
                )

        selected_debts = _selected_debts(
            source_conn,
            claim_ids=selected_claim_ids,
            route_ids=selected_route_ids,
            inference_ids=selected_inference_ids,
        )
        selected_artifact_ids = _graph_artifact_ids(
            claims,
            routes,
            inferences,
            selected_debts,
            claim_ids=selected_claim_ids,
            route_ids=selected_route_ids,
            inference_ids=selected_inference_ids,
        )

        all_artifacts = {row["artifact_id"]: dict(row) for row in source_conn.execute("SELECT * FROM artifacts")}
        for artifact_id, row in all_artifacts.items():
            text = _row_text(row)
            if _matches_any(text, exclude_regexes):
                continue
            if _matches_any(artifact_id + " " + str(row.get("path") or ""), artifact_regexes):
                selected_artifact_ids.add(artifact_id)

        missing_artifacts = sorted(selected_artifact_ids - set(all_artifacts))
        if missing_artifacts:
            raise ValueError("source graph has missing artifact rows: " + ", ".join(missing_artifacts))
        leaked_artifacts = sorted(
            artifact_id
            for artifact_id in selected_artifact_ids
            if _matches_any(_row_text(all_artifacts[artifact_id]), exclude_regexes)
        )
        if leaked_artifacts:
            raise ValueError("certified dependency closure reaches excluded artifacts: " + ", ".join(leaked_artifacts))

        artifact_files = _ArtifactFileJournal()
        try:
            from .storage_policy import audit_local_storage

            existing_target_artifacts = {
                str(row["artifact_id"]): dict(row)
                for row in target_conn.execute("SELECT * FROM artifacts")
            }
            existing_target_artifact_ids = set(existing_target_artifacts)
            _validate_existing_artifacts(
                all_artifacts,
                existing_target_artifacts,
                selected_artifact_ids & existing_target_artifact_ids,
            )
            incoming_artifact_bytes = sum(
                int(Path(str(all_artifacts[artifact_id]["path"])).stat().st_size)
                for artifact_id in selected_artifact_ids - existing_target_artifact_ids
            )
            storage_before = audit_local_storage(target)
            if int(storage_before["total_local_bytes"]) + incoming_artifact_bytes >= int(
                storage_before["hard_limit_bytes"]
            ):
                raise ValueError(
                    "scope import would reach the configured local storage hard limit"
                )
            artifact_rows = _copy_artifacts(
                all_artifacts,
                selected_artifact_ids - existing_target_artifact_ids,
                target,
                artifact_files=artifact_files,
            )
            if not audit_local_storage(target)["within_hard_limit"]:
                raise ValueError(
                    "scope import reached the configured local storage hard limit"
                )
            target_revision = int(target_state["current_revision"]) + 1
            _insert_claims(
                target_conn,
                claims,
                selected_claim_ids,
                selected_artifact_ids=selected_artifact_ids,
            )
            _insert_rows(target_conn, "routes", [routes[item] for item in sorted(selected_route_ids)])
            _insert_rows(target_conn, "inferences", [inferences[item] for item in sorted(selected_inference_ids)])
            _insert_rows(
                target_conn,
                "inference_premises",
                [
                    row
                    for inference_id in sorted(selected_inference_ids)
                    for row in premises_by_inference.get(inference_id, [])
                ],
            )
            _insert_rows(target_conn, "debts", selected_debts)
            for row in artifact_rows:
                row["state_revision"] = target_revision
                row["run_id"] = f"scope-import:{source.problem_id}"
            _insert_rows(target_conn, "artifacts", artifact_rows)

            retrieval_count = _copy_filtered_memory_rows(
                source_conn,
                target_conn,
                "retrieval_cards",
                include_regexes=[*claim_regexes, *artifact_regexes],
                exclude_regexes=exclude_regexes,
            )
            theorem_count = _copy_filtered_memory_rows(
                source_conn,
                target_conn,
                "theorem_library_entries",
                include_regexes=[*claim_regexes, *artifact_regexes],
                exclude_regexes=exclude_regexes,
            )

            now = utc_now()
            payload = {
                "source_problem_id": source.problem_id,
                "seed_claim_ids": sorted(seed_claim_ids),
                "imported_claim_ids": sorted(selected_claim_ids),
                "imported_route_ids": sorted(selected_route_ids),
                "imported_inference_ids": sorted(selected_inference_ids),
                "artifact_count": len(artifact_rows),
                "debt_count": len(selected_debts),
                "retrieval_card_count": retrieval_count,
                "theorem_library_count": theorem_count,
                "history_copied": False,
            }
            target_conn.execute(
                "UPDATE problem_state SET current_revision = ?, updated_at = ? WHERE problem_id = ?",
                (target_revision, now, target.problem_id),
            )
            target_state_after = _state_journal_projection(target_conn)
            state_delta = _state_delta(target_state_before, target_state_after)
            state_hash_before = _state_projection_hash(target_state_before)
            state_hash_after = _state_projection_hash(target_state_after)
            patch_id = f"scope-import-{source.problem_id}-{target_revision}"
            authority = PatchAuthority(
                source="operator",
                actor_role="scope_import",
                mode="scope_import",
                target_id="root",
                context_revision=int(target_state["current_revision"]),
            )
            journal_entry_hash = append_applied_patch_entry(
                target_conn,
                patch_id=patch_id,
                problem_id=target.problem_id,
                base_revision=int(target_state["current_revision"]),
                actor_role="scope_import",
                target_id="root",
                operations=[{"op": "import_certified_scope", **payload}],
                evidence_artifact_ids=[],
                rationale="explicitly import a certified dependency-closed theorem subgraph",
                created_at=now,
                applied_revision=target_revision,
                authority=authority,
                state_delta=state_delta,
                state_hash_before=state_hash_before,
                state_hash_after=state_hash_after,
            )
            target_conn.execute(
                "UPDATE problem_state SET proof_state_hash = ?, "
                "run_provenance_hash = ?, patch_journal_head = ? "
                "WHERE problem_id = ?",
                (
                    state_hash_after,
                    _run_provenance_hash(target_conn),
                    journal_entry_hash,
                    target.problem_id,
                ),
            )
            target.write_event(
                target_conn,
                target_revision,
                "scope_import",
                {
                    **payload,
                    "patch_id": patch_id,
                    "state_hash_before": state_hash_before,
                    "state_hash_after": state_hash_after,
                    "journal_entry_hash": journal_entry_hash,
                },
            )
            errors = validate_conn(target_conn)
            if errors:
                raise ValueError("scoped target would be invalid: " + "; ".join(errors))
            target_conn.commit()
            artifact_files.commit()
        except BaseException:  # intentional-boundary: rollback and remove copied evidence before propagating
            target_conn.rollback()
            artifact_files.rollback()
            raise

    target.write_snapshot()
    return {
        "source_problem_id": source.problem_id,
        "target_problem_id": target.problem_id,
        "target_root_preserved": True,
        "revision": target_revision,
        "seed_claim_ids": sorted(seed_claim_ids),
        "claim_count": len(selected_claim_ids),
        "route_count": len(selected_route_ids),
        "inference_count": len(selected_inference_ids),
        "debt_count": len(selected_debts),
        "artifact_count": len(artifact_rows),
        "retrieval_card_count": retrieval_count,
        "theorem_library_count": theorem_count,
        "history_copied": False,
    }


def _require_quiescent(row: Mapping[str, Any], *, label: str) -> None:
    status = str(row["run_status"] or "")
    if status not in SAFE_IMPORT_STATUSES:
        raise ValueError(f"{label} proof state must be paused/stopped/completed, found {status!r}")


def _compile_patterns(patterns: Sequence[str], *, label: str) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        if not str(pattern).strip():
            continue
        try:
            compiled.append(re.compile(str(pattern), re.IGNORECASE))
        except re.error as exc:
            raise ValueError(f"invalid {label} pattern {pattern!r}: {exc}") from exc
    return compiled


def _matches_any(text: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _row_text(row: Mapping[str, Any]) -> str:
    semantic_values: list[str] = []
    opaque_fields = {
        "sha256",
        "fingerprint",
        "failure_fingerprint",
        "content_hash",
        "created_at",
        "updated_at",
        "retrieved_at",
        "first_seen",
        "last_seen",
    }
    for key, value in row.items():
        if key in opaque_fields:
            continue
        if key == "path":
            value = Path(str(value or "")).name
        semantic_values.append(str(value or ""))
    return " ".join(semantic_values)


def _dependency_closure(
    claims: Mapping[str, Mapping[str, Any]],
    routes: Mapping[str, Mapping[str, Any]],
    inferences: Mapping[str, Mapping[str, Any]],
    premises_by_inference: Mapping[str, Sequence[Mapping[str, Any]]],
    seed_claim_ids: set[str],
    *,
    exclude_regexes: Sequence[re.Pattern[str]],
) -> tuple[set[str], set[str], set[str]]:
    claim_ids = set(seed_claim_ids)
    route_ids: set[str] = set()
    inference_ids: set[str] = set()
    pending = list(seed_claim_ids)
    while pending:
        claim_id = pending.pop()
        claim = claims.get(claim_id)
        if claim is None:
            raise ValueError(f"certified dependency claim is missing: {claim_id}")
        if _matches_any(_row_text(claim), exclude_regexes):
            raise ValueError(f"certified dependency closure reaches excluded claim: {claim_id}")
        if claim["validation_status"] not in VERIFIED_STATUSES:
            raise ValueError(f"certified dependency is not verified: {claim_id}")

        if claim["lifecycle_status"] != "integrated":
            continue
        integrated_routes = [
            route
            for route in routes.values()
            if route["conclusion_claim_id"] == claim_id
            and route["relation_to_parent"] == "sufficient"
            and route["status"] == "integrated"
        ]
        if not integrated_routes:
            raise ValueError(f"integrated claim has no valid integrated route: {claim_id}")
        for route in integrated_routes:
            route_id = str(route["route_id"])
            if _matches_any(_row_text(route), exclude_regexes):
                raise ValueError(f"certified dependency closure reaches excluded route: {route_id}")
            route_ids.add(route_id)
            verified_inferences = [
                inference
                for inference in inferences.values()
                if inference["route_id"] == route_id
                and inference["validation_status"] in VERIFIED_STATUSES
            ]
            for inference in verified_inferences:
                inference_id = str(inference["inference_id"])
                if _matches_any(_row_text(inference), exclude_regexes):
                    raise ValueError(f"certified dependency closure reaches excluded inference: {inference_id}")
                inference_ids.add(inference_id)
                dependency_ids = [
                    str(row["premise_claim_id"])
                    for row in premises_by_inference.get(inference_id, [])
                ]
                dependency_ids.extend(str(item) for item in json_loads(inference["condition_claim_ids_json"], []))
                for dependency_id in dependency_ids:
                    if dependency_id == "root" or dependency_id in claim_ids:
                        continue
                    claim_ids.add(dependency_id)
                    pending.append(dependency_id)
    return claim_ids, route_ids, inference_ids


def _selected_debts(
    conn: Any,
    *,
    claim_ids: set[str],
    route_ids: set[str],
    inference_ids: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in conn.execute("SELECT * FROM debts"):
        # A scope import freezes certified premises.  Resolved debts retain the
        # audit trail; active research debts belong to the old root project and
        # must not reopen an imported theorem in the new scheduler.
        if str(row["status"]) == "active":
            continue
        owner_type = str(row["owner_type"])
        owner_id = str(row["owner_id"])
        if (
            (owner_type == "claim" and owner_id in claim_ids)
            or (owner_type == "route" and owner_id in route_ids)
            or (owner_type == "inference" and owner_id in inference_ids)
        ):
            selected.append(dict(row))
    return selected


def _graph_artifact_ids(
    claims: Mapping[str, Mapping[str, Any]],
    routes: Mapping[str, Mapping[str, Any]],
    inferences: Mapping[str, Mapping[str, Any]],
    debts: Sequence[Mapping[str, Any]],
    *,
    claim_ids: set[str],
    route_ids: set[str],
    inference_ids: set[str],
) -> set[str]:
    artifact_ids: set[str] = set()
    for claim_id in claim_ids:
        artifact_ids.update(str(item) for item in json_loads(claims[claim_id]["evidence_artifact_ids_json"], []))
    for route_id in route_ids:
        artifact_ids.update(str(item) for item in json_loads(routes[route_id]["evidence_artifact_ids_json"], []))
    for inference_id in inference_ids:
        artifact_ids.update(str(item) for item in json_loads(inferences[inference_id]["evidence_artifact_ids_json"], []))
    for debt in debts:
        artifact_ids.update(str(item) for item in json_loads(debt["source_artifact_ids_json"], []))
        resolution = json_loads(debt["resolution_evidence_json"], [])
        artifact_ids.update(_artifact_ids_from_value(resolution))
    return {item for item in artifact_ids if item}


def _artifact_ids_from_value(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str) and value.startswith("art_"):
        found.add(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            found.update(_artifact_ids_from_value(item))
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for item in value:
            found.update(_artifact_ids_from_value(item))
    return found


def _copy_artifacts(
    artifacts: Mapping[str, Mapping[str, Any]],
    artifact_ids: set[str],
    target: ProofStateStore,
    *,
    artifact_files: _ArtifactFileJournal,
) -> list[dict[str, Any]]:
    destination_dir = target.state_dir / "artifacts"
    destination_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for artifact_id in sorted(artifact_ids):
        row = dict(artifacts[artifact_id])
        source_path = Path(str(row["path"]))
        expected_hash = str(row.get("sha256") or "")
        destination_path = destination_dir / source_path.name
        if destination_path.exists():
            if destination_path.is_symlink():
                raise ValueError(
                    f"artifact destination must not be a symbolic link: {destination_path}"
                )
            if artifact_hash(path=destination_path) != expected_hash:
                raise ValueError(f"artifact filename collision in target: {destination_path.name}")
        else:
            try:
                artifact_files.copy_stable_file(
                    destination_path,
                    source_path,
                    max_bytes=MAX_COPIED_ARTIFACT_BYTES,
                )
            except PatchRejected as exc:
                raise ValueError(str(exc)) from exc
        row["path"] = str(destination_path.resolve())
        if artifact_hash(path=destination_path) != expected_hash:
            raise ValueError(f"copied artifact hash mismatch: {artifact_id} at {destination_path}")
        rows.append(row)
    return rows


def _validate_existing_artifacts(
    source_artifacts: Mapping[str, Mapping[str, Any]],
    target_artifacts: Mapping[str, Mapping[str, Any]],
    artifact_ids: set[str],
) -> None:
    stable_fields = (
        "artifact_type",
        "sha256",
        "producer_role",
        "content_summary",
        "metadata_json",
        "created_at",
    )
    for artifact_id in sorted(artifact_ids):
        source_row = source_artifacts[artifact_id]
        target_row = target_artifacts[artifact_id]
        for label, row in (("source", source_row), ("target", target_row)):
            path = Path(str(row["path"]))
            if not path.is_file():
                raise ValueError(f"{label} artifact file is missing: {artifact_id} at {path}")
            if artifact_hash(path=path) != str(row.get("sha256") or ""):
                raise ValueError(f"{label} artifact hash mismatch: {artifact_id} at {path}")
        if any(source_row[field] != target_row[field] for field in stable_fields):
            raise ValueError(f"conflicting target artifact row: {artifact_id}")


def _insert_claims(
    conn: Any,
    claims: Mapping[str, Mapping[str, Any]],
    claim_ids: set[str],
    *,
    selected_artifact_ids: set[str],
) -> None:
    rows: list[dict[str, Any]] = []
    allowed_claim_ids = {*claim_ids, "root"}
    for claim_id in sorted(claim_ids):
        row = dict(claims[claim_id])
        for field in ("parent_ids_json", "source_ids_json"):
            row[field] = json_dumps(
                [item for item in json_loads(row[field], []) if str(item) in allowed_claim_ids]
            )
        row["evidence_artifact_ids_json"] = json_dumps(
            [
                item
                for item in json_loads(row["evidence_artifact_ids_json"], [])
                if str(item) in selected_artifact_ids
            ]
        )
        rows.append(row)
    _insert_rows(conn, "claims", rows)


def _insert_rows(conn: Any, table: str, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        return
    columns = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    for row in rows:
        existing_key = _primary_key_columns(conn, table)
        where = " AND ".join(f"{column} = ?" for column in existing_key)
        key_values = [row[column] for column in existing_key]
        existing = conn.execute(f"SELECT * FROM {table} WHERE {where}", key_values).fetchone()
        if existing is not None:
            if any(existing[column] != row[column] for column in columns):
                key = ", ".join(f"{column}={row[column]!r}" for column in existing_key)
                raise ValueError(f"conflicting target row in {table}: {key}")
            continue
        conn.execute(sql, [row[column] for column in columns])


def _primary_key_columns(conn: Any, table: str) -> list[str]:
    rows = list(conn.execute(f"PRAGMA table_info({table})"))
    keys = [str(row[1]) for row in sorted(rows, key=lambda item: int(item[5]) or 10_000) if int(row[5])]
    if not keys:
        raise ValueError(f"table {table} has no primary key")
    return keys


def _copy_filtered_memory_rows(
    source_conn: Any,
    target_conn: Any,
    table: str,
    *,
    include_regexes: Sequence[re.Pattern[str]],
    exclude_regexes: Sequence[re.Pattern[str]],
) -> int:
    rows = [
        dict(row)
        for row in source_conn.execute(f"SELECT * FROM {table}")
        if _matches_any(_row_text(dict(row)), include_regexes)
        and not _matches_any(_row_text(dict(row)), exclude_regexes)
    ]
    _insert_rows(target_conn, table, rows)
    return len(rows)
