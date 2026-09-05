from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .audit_chain import (
    GENESIS_HASH,
    POLICY_EVENT_TYPES,
    backfill_event_chain,
    backfill_patch_entry_chain,
    event_entry_hash,
)
from .models import (
    CLAIM_KINDS,
    COMPLETION_POLICIES,
    DEFAULT_COMPLETION_POLICY,
    LIFECYCLE_STATUSES,
    ROUTE_RELATIONS,
    ROUTE_STATUSES,
    RUN_STATUSES,
    SCHEMA_VERSION,
    STORE_MIGRATION_VERSION,
    VALIDATION_STATUSES,
    compact_dict,
    fingerprint_text,
    normalize_text,
    json_dumps,
    json_loads,
    sanitize_problem_id,
    sha256_text,
    utc_now,
)
from .scheduler_provenance import (
    ONLINE_RETRIEVAL_COUNT_INTENTS,
    SCHEDULER_HISTORY_GUARD_NAMES,
    rebuild_scheduler_provenance,
    rebuild_scheduler_source_entries,
    rebuild_scheduler_statistics,
    scheduler_provenance_errors,
    scheduler_history_guard_sql,
)

GENERATION_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = GENERATION_ROOT / "results"
SCHEDULER_RECENT_RUN_LIMIT = 96
SCHEDULER_SESSION_PATCH_LIMIT = 384
SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT = 16 * 1024 * 1024


class ValidatedCommitSuperseded(RuntimeError):
    """A committed dispatch was superseded; recover it before replanning."""


EVENT_HISTORY_GUARD_NAMES = (
    "guard_events_update",
    "guard_events_delete",
    "capture_events_source_insert",
    "guard_event_source_entries_update",
    "guard_event_source_entries_delete",
)

PROJECTION_BASELINE_GUARD_NAMES = (
    "guard_projection_audit_baselines_update",
    "guard_projection_audit_baselines_delete",
)

PATCH_HISTORY_GUARD_NAMES = (
    "guard_patches_insert",
    "guard_patches_update",
    "guard_patches_delete",
)
PATCH_HISTORY_UNIQUE_INDEX = "idx_patches_applied_revision_unique"
RANDOMIZED_ASSIGNMENT_UNIT_INDEX = (
    "idx_scheduler_randomized_experiment_unit_unique"
)
SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX = "idx_scheduler_source_kind_sequence"


def _legacy_v17_event_history_guard_sql() -> Dict[str, str]:
    unchanged = " AND ".join(
        f"NEW.{column} IS OLD.{column}"
        for column in (
            "event_id",
            "revision",
            "event_type",
            "payload_json",
            "created_at",
            "previous_event_hash",
        )
    )
    return {
        "guard_events_update": (
            "CREATE TRIGGER IF NOT EXISTS guard_events_update "
            "BEFORE UPDATE ON events WHEN NOT ("
            "OLD.event_hash = '' AND NEW.event_hash <> '' AND "
            + unchanged
            + ") BEGIN SELECT RAISE(ABORT, 'event history is append-only'); END"
        ),
        "guard_events_delete": (
            "CREATE TRIGGER IF NOT EXISTS guard_events_delete "
            "BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, "
            "'event history is append-only'); END"
        ),
    }


def _event_history_guard_sql() -> Dict[str, str]:
    guards = _legacy_v17_event_history_guard_sql()
    guards["capture_events_source_insert"] = (
        "CREATE TRIGGER IF NOT EXISTS capture_events_source_insert "
        "AFTER INSERT ON events BEGIN "
        "INSERT INTO event_source_entries(event_id) VALUES (NEW.event_id); END"
    )
    for operation in ("update", "delete"):
        guards[f"guard_event_source_entries_{operation}"] = (
            "CREATE TRIGGER IF NOT EXISTS "
            f"guard_event_source_entries_{operation} "
            f"BEFORE {operation.upper()} ON event_source_entries "
            "BEGIN SELECT RAISE(ABORT, "
            "'event source history is append-only'); END"
        )
    return guards


def _projection_baseline_guard_sql() -> Dict[str, str]:
    return {
        f"guard_projection_audit_baselines_{operation}": (
            "CREATE TRIGGER IF NOT EXISTS "
            f"guard_projection_audit_baselines_{operation} "
            f"BEFORE {operation.upper()} ON projection_audit_baselines "
            "BEGIN SELECT RAISE(ABORT, "
            "'projection audit baseline is append-only'); END"
        )
        for operation in ("update", "delete")
    }


def _patch_history_guard_sql() -> Dict[str, str]:
    return {
        "guard_patches_insert": (
            "CREATE TRIGGER IF NOT EXISTS guard_patches_insert "
            "BEFORE INSERT ON patches WHEN NOT ("
            "NEW.status = 'applied' "
            "AND typeof(NEW.applied_revision) = 'integer' "
            "AND NEW.applied_revision > 0 "
            "AND NEW.base_revision = NEW.applied_revision - 1 "
            "AND NEW.applied_revision = ("
            "SELECT current_revision FROM problem_state "
            "WHERE problem_id = NEW.problem_id) "
            "AND NEW.previous_entry_hash = ("
            "SELECT patch_journal_head FROM problem_state "
            "WHERE problem_id = NEW.problem_id) "
            "AND NEW.applied_revision > COALESCE("
            "(SELECT baseline_revision FROM projection_audit_baselines "
            "WHERE problem_id = NEW.problem_id), "
            "(SELECT baseline_revision FROM audit_baselines "
            "WHERE problem_id = NEW.problem_id), 0)"
            ") BEGIN SELECT RAISE(ABORT, "
            "'patch history insertion is invalid'); END"
        ),
        "guard_patches_update": (
            "CREATE TRIGGER IF NOT EXISTS guard_patches_update "
            "BEFORE UPDATE ON patches BEGIN SELECT RAISE(ABORT, "
            "'patch history is append-only'); END"
        ),
        "guard_patches_delete": (
            "CREATE TRIGGER IF NOT EXISTS guard_patches_delete "
            "BEFORE DELETE ON patches BEGIN SELECT RAISE(ABORT, "
            "'patch history is append-only'); END"
        ),
    }


def _patch_history_index_sql() -> str:
    return (
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        f"{PATCH_HISTORY_UNIQUE_INDEX} ON patches(applied_revision) "
        "WHERE status = 'applied'"
    )


def _randomized_assignment_v20_unit_index_sql() -> str:
    return (
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        f"{RANDOMIZED_ASSIGNMENT_UNIT_INDEX} ON scheduler_dispatches("
        "json_extract(decision_trace_json, "
        "'$.randomized_assignment.experiment_id'), "
        "json_extract(decision_trace_json, "
        "'$.randomized_assignment.assignment_unit_id')) "
        "WHERE selection_design = 'randomized' AND dispatch_position = 0"
    )


def _randomized_assignment_unit_index_sql() -> str:
    return (
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        f"{RANDOMIZED_ASSIGNMENT_UNIT_INDEX} ON scheduler_dispatches("
        "json_extract(decision_trace_json, "
        "'$.randomized_assignment.experiment_id'), "
        "json_extract(decision_trace_json, "
        "'$.randomized_assignment.assignment_unit_id'), "
        "COALESCE(json_extract(decision_trace_json, "
        "'$.randomized_assignment.exposure_index'), -1)) "
        "WHERE selection_design = 'randomized' AND dispatch_position = 0"
    )


def _scheduler_source_kind_sequence_index_sql() -> str:
    return (
        "CREATE INDEX IF NOT EXISTS "
        f"{SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX} "
        "ON scheduler_source_entries(record_kind, sequence DESC)"
    )


def _canonical_trigger_sql(sql: Any) -> str:
    """Normalize SQLite's omission of ``IF NOT EXISTS`` in sqlite_master."""

    return " ".join(str(sql or "").split()).replace(
        "CREATE TRIGGER IF NOT EXISTS ",
        "CREATE TRIGGER ",
        1,
    ).replace(
        "CREATE UNIQUE INDEX IF NOT EXISTS ",
        "CREATE UNIQUE INDEX ",
        1,
    ).replace(
        "CREATE INDEX IF NOT EXISTS ",
        "CREATE INDEX ",
        1,
    )


def _guard_definition_errors(
    conn: sqlite3.Connection,
    *,
    expected: Mapping[str, str],
    label: str,
) -> List[str]:
    names = tuple(expected)
    observed = {
        str(row["name"] or ""): _canonical_trigger_sql(row["sql"])
        for row in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
            "AND name IN ("
            + ",".join("?" for _ in names)
            + ") ORDER BY name",
            names,
        ).fetchall()
    }
    return [
        f"{label} guard {name} is missing or altered"
        for name, sql in expected.items()
        if observed.get(name) != _canonical_trigger_sql(sql)
    ]


def _event_history_guard_errors(conn: sqlite3.Connection) -> List[str]:
    expected = (
        _event_history_guard_sql()
        if _event_source_tracking_available(conn)
        else _legacy_v17_event_history_guard_sql()
    )
    return _guard_definition_errors(
        conn,
        expected=expected,
        label="event-history",
    )


def _event_source_tracking_available(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'event_source_entries'"
        ).fetchone()
        is not None
        and conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = 18"
        ).fetchone()
        is not None
    )


def _event_source_sequence_errors(conn: sqlite3.Connection) -> List[str]:
    if not _event_source_tracking_available(conn):
        return []
    event_ids = [
        int(row["event_id"])
        for row in conn.execute(
            "SELECT event_id FROM events ORDER BY event_id"
        ).fetchall()
    ]
    source_ids = [
        int(row["event_id"])
        for row in conn.execute(
            "SELECT event_id FROM event_source_entries ORDER BY sequence"
        ).fetchall()
    ]
    return (
        []
        if event_ids == source_ids
        else ["event source insertion sequence does not match the event journal"]
    )


def _projection_baseline_guard_errors(conn: sqlite3.Connection) -> List[str]:
    return _guard_definition_errors(
        conn,
        expected=_projection_baseline_guard_sql(),
        label="projection-audit-baseline",
    )


def _patch_history_guard_errors(conn: sqlite3.Connection) -> List[str]:
    errors = _guard_definition_errors(
        conn,
        expected=_patch_history_guard_sql(),
        label="patch-history",
    )
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        (PATCH_HISTORY_UNIQUE_INDEX,),
    ).fetchone()
    observed = _canonical_trigger_sql(row["sql"]) if row is not None else ""
    expected = _canonical_trigger_sql(_patch_history_index_sql())
    if observed != expected:
        errors.append(
            f"patch-history index {PATCH_HISTORY_UNIQUE_INDEX} is missing or altered"
        )
    return errors


def randomized_assignment_index_errors(conn: sqlite3.Connection) -> List[str]:
    """Check the indexed uniqueness contract used by randomized dispatches."""

    available = conn.execute(
        "SELECT MAX(version) AS version FROM schema_migrations "
        "WHERE version IN (20, 21)"
    ).fetchone()
    available_version = int(available["version"] or 0) if available else 0
    if available_version == 0:
        return []
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        (RANDOMIZED_ASSIGNMENT_UNIT_INDEX,),
    ).fetchone()
    observed = _canonical_trigger_sql(row["sql"]) if row is not None else ""
    expected_sql = (
        _randomized_assignment_unit_index_sql()
        if available_version >= 21
        else _randomized_assignment_v20_unit_index_sql()
    )
    expected = _canonical_trigger_sql(expected_sql)
    if observed == expected:
        return []
    return [
        "randomized-assignment uniqueness index "
        f"{RANDOMIZED_ASSIGNMENT_UNIT_INDEX} is missing or altered"
    ]


def scheduler_dispatch_tail_index_errors(conn: sqlite3.Connection) -> List[str]:
    """Check the index supporting the constant-window unresolved-wave test."""

    available = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = 20"
    ).fetchone()
    if available is None:
        return []
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        (SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX,),
    ).fetchone()
    observed = _canonical_trigger_sql(row["sql"]) if row is not None else ""
    expected = _canonical_trigger_sql(
        _scheduler_source_kind_sequence_index_sql()
    )
    if observed == expected:
        return []
    return [
        "scheduler dispatch-tail index "
        f"{SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX} is missing or altered"
    ]


def _sealed_db_integer(
    value: Any,
    *,
    label: str,
    errors: List[str],
    default: int = 0,
    minimum: int | None = None,
) -> int:
    """Decode one SQLite integer without letting corruption escape a seal."""

    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{label} is not an integer")
        return default
    if minimum is not None and value < minimum:
        errors.append(f"{label} is below its minimum value {minimum}")
        return default
    return value


def _policy_projection_payload_errors(
    event_type: str, payload: Mapping[str, Any]
) -> List[str]:
    """Validate events whose payload is projected into live configuration."""

    errors: List[str] = []
    if event_type == "completion_policy":
        target = payload.get("to")
        if not isinstance(target, str) or target not in COMPLETION_POLICIES:
            errors.append("completion_policy requires a valid string field 'to'")
    elif event_type == "parallel_branch_mode":
        workers = payload.get("to")
        if isinstance(workers, bool) or not isinstance(workers, int):
            errors.append("parallel_branch_mode requires an integer field 'to'")
        elif workers != 0 and not 2 <= workers <= 5:
            errors.append("parallel_branch_mode worker count must be 0 or between 2 and 5")
        else:
            expected_mode = "multi_branch_research" if workers >= 2 else ""
            if payload.get("mode") != expected_mode:
                errors.append(
                    "parallel_branch_mode field 'mode' does not match its worker count"
                )
    elif event_type == "run_control_policy":
        target = payload.get("to")
        if not isinstance(target, str) or target not in RUN_STATUSES:
            errors.append("run_control_policy requires a valid string field 'to'")
        linked_event_id = payload.get("run_control_event_id")
        if (
            isinstance(linked_event_id, bool)
            or not isinstance(linked_event_id, int)
            or linked_event_id <= 0
        ):
            errors.append(
                "run_control_policy requires a positive integer run_control_event_id"
            )
    return errors


def _run_control_policy_link_errors(
    conn: sqlite3.Connection, payload: Mapping[str, Any]
) -> List[str]:
    """Check that a policy companion binds one exact authenticated event."""

    linked_event_id = payload.get("run_control_event_id")
    if (
        isinstance(linked_event_id, bool)
        or not isinstance(linked_event_id, int)
        or linked_event_id <= 0
    ):
        return []  # The payload-schema error already reports this case.
    linked_raw = conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (linked_event_id,)
    ).fetchone()
    if linked_raw is None or str(linked_raw["event_type"] or "") != "run_control":
        return ["run_control_policy does not identify a run_control event"]
    linked = dict(linked_raw)
    errors: List[str] = []
    try:
        expected_hash = event_entry_hash(linked)
    except (TypeError, ValueError, OverflowError) as exc:
        expected_hash = ""
        errors.append(f"linked run_control event is malformed: {exc}")
    if str(linked.get("event_hash") or "") != expected_hash:
        errors.append("linked run_control event hash is invalid")
    linked_payload = json_loads(linked.get("payload_json"), None)
    expected_payload = {
        key: value for key, value in payload.items() if key != "run_control_event_id"
    }
    if linked_payload != expected_payload:
        errors.append("run_control_policy does not match its linked run_control event")
    return errors


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        suppress = super().__exit__(exc_type, exc, tb)
        self.close()
        return bool(suppress)


def phase2_dir(problem_id: str, *, generation_root: Path = GENERATION_ROOT) -> Path:
    safe_id = sanitize_problem_id(problem_id)
    path = generation_root / "results" / safe_id / "phase2"
    root = (generation_root / "results").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("problem_id resolves outside results root")
    return resolved


class ProofStateStore:
    """Versioned SQLite proof-state store.

    The store is the authoritative Albilich v1 state. Existing JSONL memory remains
    an evidence/archive layer.
    """

    def __init__(self, problem_id: str, *, generation_root: Optional[Path] = None, auto_snapshot: bool = False) -> None:
        self.problem_id = sanitize_problem_id(problem_id)
        self.generation_root = generation_root or GENERATION_ROOT
        self.state_dir = phase2_dir(self.problem_id, generation_root=self.generation_root)
        self.db_path = self.state_dir / "proof_state.sqlite3"
        self.snapshot_path = self.state_dir / "proof_state_snapshot.json"
        self.auto_snapshot = auto_snapshot

    def connect(self) -> sqlite3.Connection:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, factory=_ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        try:
            self.migrate(conn)
        except BaseException:  # intentional-boundary: close a partially initialized connection before propagating
            conn.close()
            raise
        return conn

    def migrate(self, conn: sqlite3.Connection) -> None:
        """Upgrade an existing proof store atomically and retain a backup.

        Proof-state migrations can change certification semantics, so an
        existing older database is backed up before any DDL or data rewrite.
        Every migration step then runs in one explicit transaction.
        """

        previous_migration_version = self._current_migration_version(conn)
        backup_path = self._backup_before_migration(conn)
        try:
            conn.execute("BEGIN IMMEDIATE")
            if previous_migration_version < 13:
                for table in (
                    "scheduler_dispatch_attempts",
                    "scheduler_dispatch_results",
                ):
                    if self._table_exists(conn, table) and conn.execute(
                        f"SELECT 1 FROM {table} LIMIT 1"
                    ).fetchone():
                        raise RuntimeError(
                            "cannot migrate: v13 scheduler execution records "
                            f"are present in a store labelled v{previous_migration_version}"
                        )
            if 9 <= previous_migration_version < 10:
                from .patches import _legacy_v9_run_provenance_hash

                recorded = conn.execute(
                    "SELECT run_provenance_hash FROM problem_state "
                    "WHERE problem_id = ?",
                    (self.problem_id,),
                ).fetchone()
                expected = _legacy_v9_run_provenance_hash(conn)
                if recorded is None or str(
                    recorded["run_provenance_hash"] or ""
                ) != expected:
                    raise RuntimeError(
                        "cannot migrate: run selection history differs from "
                        "its v9 current-state seal"
                    )
            if previous_migration_version == 10:
                from .patches import _legacy_v10_run_provenance_hash

                recorded = conn.execute(
                    "SELECT run_provenance_hash FROM problem_state "
                    "WHERE problem_id = ?",
                    (self.problem_id,),
                ).fetchone()
                expected = _legacy_v10_run_provenance_hash(conn)
                if recorded is None or str(
                    recorded["run_provenance_hash"] or ""
                ) != expected:
                    raise RuntimeError(
                        "cannot migrate: scheduler history differs from its "
                        "v10 current-state seal"
                    )
            if previous_migration_version == 11:
                from .patches import _legacy_v11_run_provenance_hash

                recorded = conn.execute(
                    "SELECT run_provenance_hash FROM problem_state "
                    "WHERE problem_id = ?",
                    (self.problem_id,),
                ).fetchone()
                expected = _legacy_v11_run_provenance_hash(conn)
                if recorded is None or str(
                    recorded["run_provenance_hash"] or ""
                ) != expected:
                    raise RuntimeError(
                        "cannot migrate: dispatch history differs from its "
                        "v11 current-state seal"
                    )
            if previous_migration_version == 12:
                from .patches import _legacy_v12_run_provenance_hash

                recorded = conn.execute(
                    "SELECT run_provenance_hash FROM problem_state "
                    "WHERE problem_id = ?",
                    (self.problem_id,),
                ).fetchone()
                expected = _legacy_v12_run_provenance_hash(conn)
                if recorded is None or str(
                    recorded["run_provenance_hash"] or ""
                ) != expected:
                    raise RuntimeError(
                        "cannot migrate: dispatch recovery history differs from "
                        "its v12 current-state seal"
                    )
            if previous_migration_version == 13:
                from .invariants import validate_conn
                from .patches import _legacy_v13_run_provenance_hash

                recorded = conn.execute(
                    "SELECT run_provenance_hash FROM problem_state "
                    "WHERE problem_id = ?",
                    (self.problem_id,),
                ).fetchone()
                expected = _legacy_v13_run_provenance_hash(conn)
                if recorded is None or str(
                    recorded["run_provenance_hash"] or ""
                ) != expected:
                    raise RuntimeError(
                        "cannot migrate: returned-result history differs from "
                        "its v13 current-state seal"
                    )
                integrity_errors = validate_conn(conn)
                if integrity_errors:
                    raise RuntimeError(
                        "cannot migrate: v13 state fails full validation: "
                        + "; ".join(str(error) for error in integrity_errors[:8])
                    )
            if previous_migration_version == 14:
                from .invariants import validate_conn
                from .patches import _legacy_v14_run_provenance_hash
                from .replay import verify_legacy_v14_patch_history

                recorded = conn.execute(
                    "SELECT run_provenance_hash FROM problem_state "
                    "WHERE problem_id = ?",
                    (self.problem_id,),
                ).fetchone()
                expected = _legacy_v14_run_provenance_hash(conn)
                if recorded is None or str(
                    recorded["run_provenance_hash"] or ""
                ) != expected:
                    raise RuntimeError(
                        "cannot migrate: scheduler execution history differs "
                        "from its v14 current-state seal"
                    )
                integrity_errors = validate_conn(conn)
                if integrity_errors:
                    raise RuntimeError(
                        "cannot migrate: v14 state fails full validation: "
                        + "; ".join(str(error) for error in integrity_errors[:8])
                    )
                legacy_history = verify_legacy_v14_patch_history(
                    self,
                    conn=conn,
                )
                if not legacy_history["valid"]:
                    raise RuntimeError(
                        "cannot migrate: v14 patch history fails authenticated "
                        "chain validation: "
                        + "; ".join(
                            str(error) for error in legacy_history["errors"][:8]
                        )
                    )
            if previous_migration_version == 15:
                from .replay import verify_patch_journal

                replay = verify_patch_journal(
                    self,
                    conn=conn,
                    check_patch_guards=False,
                )
                if not replay["valid"]:
                    raise RuntimeError(
                        "cannot migrate: v15 patch journal fails full replay: "
                        + "; ".join(str(error) for error in replay["errors"][:8])
                    )
            if 16 <= previous_migration_version <= 19:
                seal = self.current_state_seal(conn)
                if not seal["valid"]:
                    raise RuntimeError(
                        f"cannot migrate: v{previous_migration_version} "
                        "current-state seal is invalid: "
                        + "; ".join(str(error) for error in seal["errors"][:8])
                    )
            self._migrate_in_transaction(
                conn,
                backup_path=backup_path,
                previous_migration_version=previous_migration_version,
            )
            if backup_path and self._table_exists(conn, "events"):
                row = conn.execute(
                    "SELECT current_revision FROM problem_state WHERE problem_id = ?",
                    (self.problem_id,),
                ).fetchone()
                if row is not None:
                    self.write_event(
                        conn,
                        int(row["current_revision"]),
                        "schema_migrated",
                        {
                            "schema_version": SCHEMA_VERSION,
                            "backup_path": str(backup_path),
                            "backup_sha256": self._sha256_file(backup_path),
                            "prior_migration_version": previous_migration_version,
                        },
                    )
            if backup_path and previous_migration_version < 3:
                self._establish_legacy_audit_baseline(
                    conn,
                    backup_path=backup_path,
                    previous_migration_version=previous_migration_version,
                )
            if previous_migration_version < STORE_MIGRATION_VERSION:
                # Run after a pre-v3 semantic migration has established its
                # explicit baseline.  Initializing inside the DDL routine would
                # compare intentionally demoted legacy rows with their old
                # patch endpoint and incorrectly reject the migration.
                self._initialize_current_state_seals(
                    conn,
                    require_existing_proof_seal=previous_migration_version >= 8,
                )
            conn.commit()
        except BaseException:  # intentional-boundary: every migration failure must roll back atomically
            conn.rollback()
            raise

    def _migrate_in_transaction(
        self,
        conn: sqlite3.Connection,
        *,
        backup_path: Path | None,
        previous_migration_version: int,
    ) -> None:
        typed_relation_tables = {
            "claim_parent_relations",
            "inference_condition_claims",
            "claim_evidence_artifacts",
            "route_evidence_artifacts",
            "inference_evidence_artifacts",
            "theorem_library_evidence_artifacts",
            "proof_obligation_source_artifacts",
            "proof_obligation_resolution_artifacts",
            "proof_obligation_owners",
        }
        typed_relations_added = any(
            not self._table_exists(conn, table) for table in typed_relation_tables
        )
        self._execute_ddl_script(
            conn,
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_baselines (
                problem_id TEXT PRIMARY KEY REFERENCES problem_state(problem_id),
                baseline_revision INTEGER NOT NULL CHECK(baseline_revision >= 0),
                baseline_state_hash TEXT NOT NULL,
                patch_journal_head TEXT NOT NULL,
                legacy_patch_count INTEGER NOT NULL CHECK(legacy_patch_count >= 0),
                prior_history_status TEXT NOT NULL,
                prior_migration_version INTEGER NOT NULL,
                migration_backup_path TEXT NOT NULL,
                migration_backup_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projection_audit_baselines (
                problem_id TEXT PRIMARY KEY REFERENCES problem_state(problem_id),
                baseline_revision INTEGER NOT NULL CHECK(baseline_revision >= 0),
                baseline_state_hash TEXT NOT NULL,
                prior_state_hash TEXT NOT NULL,
                patch_journal_head TEXT NOT NULL,
                legacy_patch_count INTEGER NOT NULL CHECK(legacy_patch_count >= 0),
                prior_history_status TEXT NOT NULL,
                prior_migration_version INTEGER NOT NULL,
                migration_backup_path TEXT NOT NULL,
                migration_backup_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS problem_state (
                problem_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                current_revision INTEGER NOT NULL,
                root_statement TEXT NOT NULL,
                status TEXT NOT NULL,
                total_token_budget INTEGER NOT NULL,
                remaining_token_budget INTEGER NOT NULL,
                reserved_verification_budget INTEGER NOT NULL,
                max_reduction_depth INTEGER NOT NULL,
                event_chain_length INTEGER NOT NULL DEFAULT 0,
                event_chain_head TEXT NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000',
                policy_event_head TEXT NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000',
                proof_state_hash TEXT NOT NULL DEFAULT '',
                run_provenance_hash TEXT NOT NULL DEFAULT '',
                patch_journal_head TEXT NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS claims (
                claim_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                statement TEXT NOT NULL,
                normalized_statement TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                hypotheses TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                lifecycle_status TEXT NOT NULL,
                root_impact REAL NOT NULL,
                reduction_depth INTEGER NOT NULL,
                parent_ids_json TEXT NOT NULL,
                source_ids_json TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS routes (
                route_id TEXT PRIMARY KEY,
                conclusion_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
                label TEXT NOT NULL,
                strategy TEXT NOT NULL,
                status TEXT NOT NULL,
                relation_to_parent TEXT NOT NULL,
                assumptions_json TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                failure_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inferences (
                inference_id TEXT PRIMARY KEY,
                route_id TEXT NOT NULL REFERENCES routes(route_id),
                conclusion_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
                explanation TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                condition_claim_ids_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inference_premises (
                inference_id TEXT NOT NULL REFERENCES inferences(inference_id) ON DELETE CASCADE,
                premise_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
                position INTEGER NOT NULL,
                PRIMARY KEY (inference_id, premise_claim_id)
            );
            CREATE TABLE IF NOT EXISTS debts (
                debt_id TEXT PRIMARY KEY,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                obligation TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                debt_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                repeated_count INTEGER NOT NULL,
                source_artifact_ids_json TEXT NOT NULL,
                suggested_next_target TEXT NOT NULL,
                resolution_evidence_json TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_debts_owner_fingerprint
                ON debts(owner_type, owner_id, fingerprint);
            CREATE VIEW IF NOT EXISTS proof_obligations AS
                SELECT debt_id AS proof_obligation_id,
                       owner_type,
                       owner_id,
                       obligation,
                       fingerprint,
                       debt_type AS obligation_type,
                       severity,
                       status,
                       first_seen,
                       last_seen,
                       repeated_count AS repetition_count,
                       source_artifact_ids_json,
                       suggested_next_target,
                       resolution_evidence_json
                FROM debts;
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                producer_role TEXT NOT NULL,
                run_id TEXT NOT NULL,
                state_revision INTEGER NOT NULL,
                content_summary TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                actor_role TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL,
                target_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                state_revision INTEGER NOT NULL,
                context_revision INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                model_profile TEXT NOT NULL,
                model TEXT NOT NULL,
                reasoning_effort TEXT NOT NULL,
                search_setting TEXT NOT NULL,
                search_intent TEXT NOT NULL DEFAULT '',
                strategy_family TEXT NOT NULL DEFAULT 'unclassified',
                selection_design TEXT NOT NULL DEFAULT 'observational',
                assignment_probability REAL NOT NULL DEFAULT 0.0,
                exploration_stratum TEXT NOT NULL DEFAULT '',
                candidate_set_hash TEXT NOT NULL DEFAULT '',
                selection_policy_version INTEGER NOT NULL DEFAULT 0,
                decision_trace_json TEXT NOT NULL DEFAULT '{}',
                sandbox_setting TEXT NOT NULL,
                budget_requested INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                cached_input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                reasoning_output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                wall_time_seconds REAL NOT NULL,
                peak_memory_mb REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL,
                prompt_context_hash TEXT NOT NULL,
                output_artifact_ids_json TEXT NOT NULL,
                error_artifact_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scheduler_dispatches (
                dispatch_id TEXT PRIMARY KEY,
                dispatch_group_id TEXT NOT NULL,
                dispatch_position INTEGER NOT NULL CHECK(dispatch_position >= 0),
                is_companion INTEGER NOT NULL CHECK(is_companion IN (0, 1)),
                actor_role TEXT NOT NULL,
                mode TEXT NOT NULL,
                target_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                decision_state_revision INTEGER NOT NULL
                    CHECK(decision_state_revision >= 0),
                proof_state_hash TEXT NOT NULL,
                prior_run_provenance_hash TEXT NOT NULL,
                selection_design TEXT NOT NULL,
                candidate_set_hash TEXT NOT NULL,
                selection_policy_version INTEGER NOT NULL,
                decision_trace_json TEXT NOT NULL,
                dispatched_action_hash TEXT NOT NULL,
                dispatched_action_json TEXT,
                execution_contract_json TEXT,
                committed_at TEXT NOT NULL,
                UNIQUE(dispatch_group_id, dispatch_position)
            );
            CREATE TABLE IF NOT EXISTS scheduler_dispatch_attempts (
                attempt_id TEXT PRIMARY KEY,
                dispatch_id TEXT NOT NULL REFERENCES scheduler_dispatches(dispatch_id),
                attempt_number INTEGER NOT NULL CHECK(attempt_number > 0),
                session_plan_hash TEXT NOT NULL,
                executor_identity TEXT NOT NULL,
                claimed_at TEXT NOT NULL,
                event_id INTEGER NOT NULL UNIQUE REFERENCES events(event_id),
                UNIQUE(dispatch_id, attempt_number)
            );
            CREATE TABLE IF NOT EXISTS scheduler_dispatch_results (
                result_id TEXT PRIMARY KEY,
                dispatch_id TEXT NOT NULL UNIQUE REFERENCES scheduler_dispatches(dispatch_id),
                attempt_id TEXT NOT NULL UNIQUE REFERENCES scheduler_dispatch_attempts(attempt_id),
                run_id TEXT NOT NULL UNIQUE,
                session_plan_json TEXT NOT NULL,
                execution_json TEXT NOT NULL,
                validation_errors_json TEXT NOT NULL,
                result_hash TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                event_id INTEGER NOT NULL UNIQUE REFERENCES events(event_id)
            );
            CREATE TABLE IF NOT EXISTS scheduler_provenance_entries (
                sequence INTEGER PRIMARY KEY CHECK(sequence > 0),
                record_kind TEXT NOT NULL
                    CHECK(record_kind IN ('run', 'dispatch', 'attempt', 'result')),
                record_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                UNIQUE(record_kind, record_id)
            );
            CREATE TABLE IF NOT EXISTS scheduler_source_entries (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                record_kind TEXT NOT NULL
                    CHECK(record_kind IN ('run', 'dispatch', 'attempt', 'result')),
                record_id TEXT NOT NULL,
                UNIQUE(record_kind, record_id)
            );
            CREATE TABLE IF NOT EXISTS scheduler_statistics (
                statistic_kind TEXT NOT NULL CHECK(statistic_kind IN (
                    'total_run', 'outcome_run', 'retrieve_total',
                    'retrieve_intent', 'session_patch'
                )),
                statistic_key TEXT NOT NULL,
                value INTEGER NOT NULL CHECK(value > 0),
                PRIMARY KEY(statistic_kind, statistic_key)
            );
            CREATE TABLE IF NOT EXISTS scheduler_candidate_deferrals (
                candidate_id TEXT PRIMARY KEY,
                consecutive_capacity_deferrals INTEGER NOT NULL
                    CHECK(consecutive_capacity_deferrals > 0),
                last_wave_id TEXT NOT NULL,
                policy_version INTEGER NOT NULL CHECK(policy_version > 0),
                updated_run_id TEXT REFERENCES runs(run_id),
                updated_dispatch_id TEXT REFERENCES scheduler_dispatches(dispatch_id),
                CHECK ((updated_run_id IS NULL) != (updated_dispatch_id IS NULL))
            );
            CREATE TABLE IF NOT EXISTS scheduler_fairness_meta (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                last_wave_id TEXT NOT NULL,
                last_state_revision INTEGER NOT NULL
                    CHECK(last_state_revision >= 0),
                policy_version INTEGER NOT NULL CHECK(policy_version > 0),
                updated_run_id TEXT REFERENCES runs(run_id),
                updated_dispatch_id TEXT REFERENCES scheduler_dispatches(dispatch_id),
                CHECK ((updated_run_id IS NULL) != (updated_dispatch_id IS NULL))
            );
            CREATE TABLE IF NOT EXISTS scheduler_decision_deferrals (
                candidate_id TEXT PRIMARY KEY,
                consecutive_deferrals INTEGER NOT NULL
                    CHECK(consecutive_deferrals > 0),
                last_decision_id TEXT NOT NULL,
                policy_version INTEGER NOT NULL CHECK(policy_version > 0),
                updated_run_id TEXT REFERENCES runs(run_id),
                updated_dispatch_id TEXT REFERENCES scheduler_dispatches(dispatch_id),
                CHECK ((updated_run_id IS NULL) != (updated_dispatch_id IS NULL))
            );
            CREATE TABLE IF NOT EXISTS scheduler_decision_fairness_meta (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                last_decision_id TEXT NOT NULL,
                last_state_revision INTEGER NOT NULL
                    CHECK(last_state_revision >= 0),
                policy_version INTEGER NOT NULL CHECK(policy_version > 0),
                updated_run_id TEXT REFERENCES runs(run_id),
                updated_dispatch_id TEXT REFERENCES scheduler_dispatches(dispatch_id),
                CHECK ((updated_run_id IS NULL) != (updated_dispatch_id IS NULL))
            );
            CREATE TABLE IF NOT EXISTS patches (
                patch_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                problem_id TEXT NOT NULL,
                base_revision INTEGER NOT NULL,
                actor_role TEXT NOT NULL,
                target_id TEXT NOT NULL,
                operations_json TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                rationale TEXT NOT NULL,
                status TEXT NOT NULL,
                rejection_reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                applied_revision INTEGER NOT NULL,
                authority_source TEXT NOT NULL DEFAULT '',
                authority_json TEXT NOT NULL DEFAULT '{}',
                state_delta_json TEXT NOT NULL DEFAULT '[]',
                state_hash_before TEXT NOT NULL DEFAULT '',
                state_hash_after TEXT NOT NULL DEFAULT '',
                previous_entry_hash TEXT NOT NULL DEFAULT '',
                journal_entry_hash TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                revision INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                previous_event_hash TEXT NOT NULL DEFAULT '',
                event_hash TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS event_source_entries (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL UNIQUE REFERENCES events(event_id)
            );
            CREATE TABLE IF NOT EXISTS context_requests (
                request_id TEXT PRIMARY KEY,
                requested_entity_type TEXT NOT NULL CHECK (
                    requested_entity_type IN (
                        'claim', 'route', 'inference', 'proof_obligation',
                        'artifact', 'retrieval_card', 'theorem_library_entry'
                    )
                ),
                requested_claim_id TEXT REFERENCES claims(claim_id),
                requested_route_id TEXT REFERENCES routes(route_id),
                requested_inference_id TEXT REFERENCES inferences(inference_id),
                requested_proof_obligation_id TEXT REFERENCES debts(debt_id),
                requested_artifact_id TEXT REFERENCES artifacts(artifact_id),
                requested_retrieval_card_id TEXT REFERENCES retrieval_cards(card_id),
                requested_theorem_library_entry_id TEXT REFERENCES theorem_library_entries(entry_id),
                requester_role TEXT NOT NULL,
                request_mode TEXT NOT NULL,
                original_target_id TEXT NOT NULL,
                original_route_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'fulfilled', 'cancelled')),
                requested_at TEXT NOT NULL,
                fulfilled_at TEXT NOT NULL DEFAULT '',
                fulfilled_revision INTEGER NOT NULL DEFAULT 0,
                CHECK (
                    (requested_claim_id IS NOT NULL) +
                    (requested_route_id IS NOT NULL) +
                    (requested_inference_id IS NOT NULL) +
                    (requested_proof_obligation_id IS NOT NULL) +
                    (requested_artifact_id IS NOT NULL) +
                    (requested_retrieval_card_id IS NOT NULL) +
                    (requested_theorem_library_entry_id IS NOT NULL) = 1
                )
            );
            CREATE TABLE IF NOT EXISTS claim_assurance (
                claim_id TEXT PRIMARY KEY REFERENCES claims(claim_id) ON DELETE CASCADE,
                assurance_level TEXT NOT NULL CHECK (
                    assurance_level IN ('standard', 'heterogeneous_review')
                ),
                rationale TEXT NOT NULL,
                designated_by TEXT NOT NULL,
                designated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS retrieval_cards (
                card_id TEXT PRIMARY KEY,
                normalized_query TEXT NOT NULL,
                source_version TEXT NOT NULL,
                exact_statement TEXT NOT NULL,
                source_identifiers_json TEXT NOT NULL,
                hypotheses_json TEXT NOT NULL,
                local_definitions_json TEXT NOT NULL,
                applicability_json TEXT NOT NULL,
                missing_hypotheses_json TEXT NOT NULL,
                source_location TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                retrieved_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS theorem_library_entries (
                entry_id TEXT PRIMARY KEY,
                statement TEXT NOT NULL,
                normalized_statement TEXT NOT NULL,
                source_identifiers_json TEXT NOT NULL,
                source_version TEXT NOT NULL,
                source_location TEXT NOT NULL,
                certification_type TEXT NOT NULL,
                relation_to_target TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS publication_reviews (
                review_id TEXT PRIMARY KEY REFERENCES artifacts(artifact_id),
                round_number INTEGER NOT NULL,
                paper_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                certificate_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                verdict TEXT NOT NULL,
                decision_token TEXT NOT NULL,
                affected_route_id TEXT NOT NULL,
                falsified_step TEXT NOT NULL,
                mathematical_evidence TEXT NOT NULL,
                finding_count INTEGER NOT NULL,
                metadata_json TEXT NOT NULL,
                state_revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                escalated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS claim_parent_relations (
                claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                parent_claim_id TEXT NOT NULL REFERENCES claims(claim_id)
                    DEFERRABLE INITIALLY DEFERRED,
                position INTEGER NOT NULL,
                PRIMARY KEY (claim_id, parent_claim_id),
                UNIQUE (claim_id, position)
            );
            CREATE TABLE IF NOT EXISTS inference_condition_claims (
                inference_id TEXT NOT NULL REFERENCES inferences(inference_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                condition_claim_id TEXT NOT NULL REFERENCES claims(claim_id)
                    DEFERRABLE INITIALLY DEFERRED,
                position INTEGER NOT NULL,
                PRIMARY KEY (inference_id, condition_claim_id),
                UNIQUE (inference_id, position)
            );
            CREATE TABLE IF NOT EXISTS claim_evidence_artifacts (
                claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id)
                    DEFERRABLE INITIALLY DEFERRED,
                position INTEGER NOT NULL,
                PRIMARY KEY (claim_id, artifact_id),
                UNIQUE (claim_id, position)
            );
            CREATE TABLE IF NOT EXISTS route_evidence_artifacts (
                route_id TEXT NOT NULL REFERENCES routes(route_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id)
                    DEFERRABLE INITIALLY DEFERRED,
                position INTEGER NOT NULL,
                PRIMARY KEY (route_id, artifact_id),
                UNIQUE (route_id, position)
            );
            CREATE TABLE IF NOT EXISTS inference_evidence_artifacts (
                inference_id TEXT NOT NULL REFERENCES inferences(inference_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id)
                    DEFERRABLE INITIALLY DEFERRED,
                position INTEGER NOT NULL,
                PRIMARY KEY (inference_id, artifact_id),
                UNIQUE (inference_id, position)
            );
            CREATE TABLE IF NOT EXISTS theorem_library_evidence_artifacts (
                entry_id TEXT NOT NULL REFERENCES theorem_library_entries(entry_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id)
                    DEFERRABLE INITIALLY DEFERRED,
                position INTEGER NOT NULL,
                PRIMARY KEY (entry_id, artifact_id),
                UNIQUE (entry_id, position)
            );
            CREATE TABLE IF NOT EXISTS proof_obligation_source_artifacts (
                proof_obligation_id TEXT NOT NULL REFERENCES debts(debt_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id)
                    DEFERRABLE INITIALLY DEFERRED,
                position INTEGER NOT NULL,
                PRIMARY KEY (proof_obligation_id, artifact_id),
                UNIQUE (proof_obligation_id, position)
            );
            CREATE TABLE IF NOT EXISTS proof_obligation_resolution_artifacts (
                proof_obligation_id TEXT NOT NULL REFERENCES debts(debt_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id)
                    DEFERRABLE INITIALLY DEFERRED,
                position INTEGER NOT NULL,
                PRIMARY KEY (proof_obligation_id, artifact_id),
                UNIQUE (proof_obligation_id, position)
            );
            CREATE TABLE IF NOT EXISTS proof_obligation_owners (
                proof_obligation_id TEXT PRIMARY KEY REFERENCES debts(debt_id) ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED,
                owner_claim_id TEXT REFERENCES claims(claim_id) DEFERRABLE INITIALLY DEFERRED,
                owner_route_id TEXT REFERENCES routes(route_id) DEFERRABLE INITIALLY DEFERRED,
                owner_inference_id TEXT REFERENCES inferences(inference_id) DEFERRABLE INITIALLY DEFERRED,
                owner_artifact_id TEXT REFERENCES artifacts(artifact_id) DEFERRABLE INITIALLY DEFERRED,
                CHECK (
                    (owner_claim_id IS NOT NULL) +
                    (owner_route_id IS NOT NULL) +
                    (owner_inference_id IS NOT NULL) +
                    (owner_artifact_id IS NOT NULL) = 1
                )
            );
            """
        )
        self._ensure_typed_relation_triggers(conn)
        if typed_relations_added:
            self._backfill_typed_relations(conn)
        self._ensure_column(conn, "runs", "search_intent", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "actor_role", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "strategy_family", "TEXT NOT NULL DEFAULT 'unclassified'")
        self._ensure_column(
            conn, "runs", "selection_design", "TEXT NOT NULL DEFAULT 'observational'"
        )
        self._ensure_column(
            conn, "runs", "assignment_probability", "REAL NOT NULL DEFAULT 0.0"
        )
        self._ensure_column(conn, "runs", "exploration_stratum", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "candidate_set_hash", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(
            conn, "runs", "selection_policy_version", "INTEGER NOT NULL DEFAULT 0"
        )
        self._ensure_column(conn, "runs", "decision_trace_json", "TEXT NOT NULL DEFAULT '{}'")
        decision_state_revision_added = self._ensure_column(
            conn,
            "runs",
            "decision_state_revision",
            "INTEGER NOT NULL DEFAULT 0",
        )
        if decision_state_revision_added:
            conn.execute(
                "UPDATE runs SET decision_state_revision = state_revision"
            )
        self._ensure_column(
            conn,
            "runs",
            "scheduler_dispatch_id",
            "TEXT REFERENCES scheduler_dispatches(dispatch_id)",
        )
        self._ensure_column(
            conn, "runs", "dispatched_action_hash", "TEXT NOT NULL DEFAULT ''"
        )
        # Null is reserved for v11 dispatches, whose historical journal did
        # not contain a recoverable action body. Every v12 record operation
        # must supply a canonical object and invariants enforce that rule.
        self._ensure_column(
            conn, "scheduler_dispatches", "dispatched_action_json", "TEXT"
        )
        self._ensure_column(
            conn, "scheduler_dispatches", "execution_contract_json", "TEXT"
        )
        result_run_id_added = self._ensure_column(
            conn,
            "scheduler_dispatch_results",
            "run_id",
            "TEXT NOT NULL DEFAULT ''",
        )
        if result_run_id_added:
            self._backfill_scheduler_result_run_ids(conn)
        # Whole-run control state: running | dashboard_paused |
        # pause_requested | paused | stopping | stopped | completed.
        self._ensure_column(conn, "problem_state", "run_status", "TEXT NOT NULL DEFAULT 'running'")
        # Run-level completion policy: full_proof_first |
        # partial_ok | exploratory. Only the explicit CLI flag changes it; soft
        # wording in the problem markdown never flips it.
        self._ensure_column(conn, "problem_state", "completion_policy", "TEXT NOT NULL DEFAULT 'full_proof_first'")
        # Parallel branch research mode: worker count for
        # the multi_branch_research work mode (0 = off, 2..5 = on) plus the
        # recorded mode name; set only by the explicit --parallel-branches flag.
        self._ensure_column(conn, "problem_state", "parallel_branches", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "problem_state", "research_parallel_mode", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "problem_state", "event_chain_length", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(
            conn,
            "problem_state",
            "event_chain_head",
            f"TEXT NOT NULL DEFAULT '{GENESIS_HASH}'",
        )
        self._ensure_column(
            conn,
            "problem_state",
            "policy_event_head",
            f"TEXT NOT NULL DEFAULT '{GENESIS_HASH}'",
        )
        self._ensure_column(
            conn,
            "problem_state",
            "proof_state_hash",
            "TEXT NOT NULL DEFAULT ''",
        )
        self._ensure_column(
            conn,
            "problem_state",
            "run_provenance_hash",
            "TEXT NOT NULL DEFAULT ''",
        )
        self._ensure_column(
            conn,
            "problem_state",
            "patch_journal_head",
            f"TEXT NOT NULL DEFAULT '{GENESIS_HASH}'",
        )
        total_tokens_added = self._ensure_column(conn, "runs", "total_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "runs", "peak_memory_mb", "REAL NOT NULL DEFAULT 0.0")
        self._ensure_column(conn, "runs", "researcher_work_mode", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "work_mode_source", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "failure_kind", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "budget_overrun_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "patches", "authority_source", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "patches", "authority_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column(conn, "patches", "state_delta_json", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(conn, "patches", "state_hash_before", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "patches", "state_hash_after", "TEXT NOT NULL DEFAULT ''")
        patch_previous_added = self._ensure_column(
            conn, "patches", "previous_entry_hash", "TEXT NOT NULL DEFAULT ''"
        )
        patch_hash_added = self._ensure_column(
            conn, "patches", "journal_entry_hash", "TEXT NOT NULL DEFAULT ''"
        )
        event_previous_added = self._ensure_column(
            conn, "events", "previous_event_hash", "TEXT NOT NULL DEFAULT ''"
        )
        event_hash_added = self._ensure_column(
            conn, "events", "event_hash", "TEXT NOT NULL DEFAULT ''"
        )
        if patch_previous_added or patch_hash_added:
            backfill_patch_entry_chain(conn)
        if event_previous_added or event_hash_added:
            backfill_event_chain(conn, problem_id=self.problem_id)
        if total_tokens_added:
            # One-time backfill when the column first appears; running it on
            # every connect was wasted work.
            conn.execute(
                """
                UPDATE runs
                SET total_tokens = input_tokens + output_tokens
                WHERE total_tokens <= 0
                """
            )
        self._execute_ddl_script(
            conn,
            """
            CREATE INDEX IF NOT EXISTS idx_claims_fingerprint
                ON claims(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_artifacts_type_role_sha
                ON artifacts(artifact_type, producer_role, sha256);
            CREATE INDEX IF NOT EXISTS idx_retrieval_content_hash
                ON retrieval_cards(content_hash);
            CREATE INDEX IF NOT EXISTS idx_theorem_library_statement
                ON theorem_library_entries(normalized_statement);
            CREATE INDEX IF NOT EXISTS idx_publication_reviews_paper_round
                ON publication_reviews(paper_artifact_id, round_number);
            CREATE INDEX IF NOT EXISTS idx_context_requests_status_requested
                ON context_requests(status, requested_at, request_id);
            CREATE INDEX IF NOT EXISTS idx_events_type_id
                ON events(event_type, event_id);
            CREATE INDEX IF NOT EXISTS idx_patches_status_revision
                ON patches(status, applied_revision);
            CREATE INDEX IF NOT EXISTS idx_patches_applied_session_revision
                ON patches(applied_revision DESC, patch_id DESC)
                WHERE status = 'applied' AND authority_source = 'session';
            CREATE INDEX IF NOT EXISTS idx_runs_created
                ON runs(created_at DESC, run_id DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_actor_created
                ON runs(actor_role, created_at DESC, run_id DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_mode_intent
                ON runs(mode, search_intent);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_scheduler_dispatch
                ON runs(scheduler_dispatch_id)
                WHERE scheduler_dispatch_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_scheduler_dispatch_group
                ON scheduler_dispatches(dispatch_group_id, dispatch_position);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_scheduler_randomized_experiment_unit_unique
                ON scheduler_dispatches(
                    json_extract(decision_trace_json, '$.randomized_assignment.experiment_id'),
                    json_extract(decision_trace_json, '$.randomized_assignment.assignment_unit_id')
                )
                WHERE selection_design = 'randomized' AND dispatch_position = 0;
            CREATE INDEX IF NOT EXISTS idx_scheduler_source_kind_sequence
                ON scheduler_source_entries(record_kind, sequence DESC);
            CREATE INDEX IF NOT EXISTS idx_scheduler_dispatch_attempt
                ON scheduler_dispatch_attempts(dispatch_id, attempt_number);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_scheduler_result_run
                ON scheduler_dispatch_results(run_id);
            """
        )
        applied_versions = {
            int(row["version"])
            for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        }
        if 1 not in applied_versions:
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (1, ?)",
                (utc_now(),),
            )
            applied_versions.add(1)
        if 2 not in applied_versions:
            # Version 2 introduces host-bound certificates.  A legacy LLM
            # verdict cannot be grandfathered into that stronger meaning, so
            # preserve its evidence while returning its status to challenged.
            conn.execute(
                "UPDATE inferences SET validation_status = 'challenged' "
                "WHERE validation_status IN ('informally_verified', 'formally_verified', 'refuted')"
            )
            conn.execute(
                """
                UPDATE claims
                SET validation_status = CASE
                        WHEN validation_status IN ('informally_verified', 'formally_verified', 'refuted') THEN 'challenged'
                        ELSE validation_status
                    END,
                    lifecycle_status = CASE
                        WHEN lifecycle_status = 'integrated' THEN 'active'
                        ELSE lifecycle_status
                    END
                WHERE validation_status IN ('informally_verified', 'formally_verified', 'refuted')
                   OR lifecycle_status = 'integrated'
                """
            )
            conn.execute("UPDATE routes SET status = 'active' WHERE status = 'integrated'")
            for row in conn.execute("SELECT artifact_id, metadata_json FROM artifacts").fetchall():
                metadata = json_loads(row["metadata_json"], {})
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata["legacy_schema_version"] = 1
                metadata["legacy_revision_semantics"] = True
                conn.execute(
                    "UPDATE artifacts SET metadata_json = ? WHERE artifact_id = ?",
                    (json_dumps(metadata), row["artifact_id"]),
                )
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (2, ?)",
                (utc_now(),),
            )
            applied_versions.add(2)
        if 3 not in applied_versions:
            # Strategy families became explicit outcome telemetry in v3. Do
            # not fabricate classifications for historical keyword-only rows.
            conn.execute(
                "UPDATE runs SET strategy_family = 'legacy_unclassified' "
                "WHERE strategy_family = '' OR strategy_family = 'unclassified'"
            )
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (3, ?)",
                (utc_now(),),
            )
            applied_versions.add(3)
        if 4 not in applied_versions:
            # Version 4 makes assignment provenance explicit. Historical and
            # ordinary scheduler choices are observational and therefore may
            # be summarized descriptively but cannot alter action ranking.
            conn.execute(
                """
                UPDATE runs
                SET selection_design = 'observational',
                    assignment_probability = 0.0,
                    exploration_stratum = '',
                    candidate_set_hash = '',
                    selection_policy_version = 0
                """
            )
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (4, ?)",
                (utc_now(),),
            )
            applied_versions.add(4)
        if 5 not in applied_versions:
            # Version 5 adds FK-backed relational mirrors for graph edges,
            # evidence, and proof-obligation ownership. Compatibility JSON is
            # retained for old patches, but triggers and invariants require an
            # exact match with the typed relations.
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (5, ?)",
                (utc_now(),),
            )
            applied_versions.add(5)
        if 6 not in applied_versions:
            # Version 6 introduces an explicit replay baseline for migrated
            # pre-v3 histories. It records no retrospective proof claim: the
            # old database backup is hashed and the post-migration state is a
            # new local audit genesis that must be signed externally.
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (6, ?)",
                (utc_now(),),
            )
            applied_versions.add(6)
        if 7 not in applied_versions:
            # Version 7 persists the host scheduler's comparison trace beside
            # each run. Historical rows receive an explicit empty trace; no
            # rejected alternatives are reconstructed retrospectively.
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (7, ?)",
                (utc_now(),),
            )
            applied_versions.add(7)
        if 8 not in applied_versions:
            # Version 8 adds an incrementally checkable seal for the current
            # proof-state projection.  Existing stores are accepted only when
            # their projection already agrees with the latest replay endpoint
            # (or migration baseline); migration must not bless a discrepancy.
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (8, ?)",
                (utc_now(),),
            )
            applied_versions.add(8)
        if 9 not in applied_versions:
            # Version 9 seals the assignment and decision-trace columns that
            # intentionally remain outside the historical row-replay
            # projection.  This adds current-state tamper detection without
            # rewriting or weakening older replay hashes.
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (9, ?)",
                (utc_now(),),
            )
            applied_versions.add(9)
        if 10 not in applied_versions:
            # Version 10 replaces fairness reconstruction from the bounded
            # online trace window with compact, system-maintained counters.
            # Seed only the latest continuous wave suffix; no retrospective
            # liveness claim is made for omitted or malformed history.
            self._initialize_scheduler_fairness_state(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (10, ?)",
                (utc_now(),),
            )
            applied_versions.add(10)
        if 11 not in applied_versions:
            # Version 11 separates durable scheduler dispatch from eventual
            # execution telemetry.  Fairness therefore advances before a
            # child can be launched and survives an orchestrator crash.
            self._migrate_scheduler_fairness_provenance(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (11, ?)",
                (utc_now(),),
            )
            applied_versions.add(11)
        if 12 not in applied_versions:
            # Version 12 makes newly committed dispatches replayable after an
            # orchestrator restart by retaining the exact hash-bound action.
            # Historical v11 rows remain explicitly non-recoverable because
            # their action bodies cannot be reconstructed from a digest.
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (12, ?)",
                (utc_now(),),
            )
            applied_versions.add(12)
        if 13 not in applied_versions:
            # Version 13 records each executor claim and each returned result
            # before proof-state application.  A restart can consume a sealed
            # result without invoking the external executor again.
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (13, ?)",
                (utc_now(),),
            )
            applied_versions.add(13)
        if 14 not in applied_versions:
            # Version 14 reserves each returned run identifier in the result
            # transaction, before later telemetry can contend for the global
            # runs primary key.
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (14, ?)",
                (utc_now(),),
            )
            applied_versions.add(14)
        if 15 not in applied_versions:
            # Version 15 replaces repeated full-history materialization on
            # every scheduler transition with an authenticated append-only
            # index. Migration first validates the v14 seal, then commits one
            # digest per immutable history row. Explicit audit still
            # recomputes every digest from the authoritative tables.
            # A database produced by v14 has no guards. Dropping names here
            # also makes downgrade fixtures deterministic without weakening
            # the pre-migration v14 seal and full-integrity checks above.
            from .patches import (
                _legacy_v14_state_journal_projection,
                _state_journal_projection,
                _state_projection_hash,
            )

            state = conn.execute(
                "SELECT current_revision, proof_state_hash, patch_journal_head "
                "FROM problem_state WHERE problem_id = ?",
                (self.problem_id,),
            ).fetchone()
            legacy_state_hash = ""
            current_state_hash = ""
            if state is not None:
                legacy_state_hash = _state_projection_hash(
                    _legacy_v14_state_journal_projection(conn)
                )
                if (
                    previous_migration_version >= 8
                    and str(state["proof_state_hash"] or "")
                    != legacy_state_hash
                ):
                    raise RuntimeError(
                        "cannot migrate: proof state differs from its v14 "
                        "current-state seal"
                    )
                current_state_hash = _state_projection_hash(
                    _state_journal_projection(conn)
                )
            self._drop_scheduler_history_guards(conn)
            rebuild_scheduler_provenance(conn)
            if state is not None and legacy_state_hash != current_state_hash:
                if backup_path is None:
                    raise RuntimeError(
                        "cannot migrate proof projection without an immutable backup"
                    )
                patch_count = int(
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM patches WHERE status = 'applied'"
                    ).fetchone()["n"]
                )
                conn.execute(
                    "INSERT INTO projection_audit_baselines("
                    "problem_id, baseline_revision, baseline_state_hash, "
                    "prior_state_hash, patch_journal_head, legacy_patch_count, "
                    "prior_history_status, prior_migration_version, "
                    "migration_backup_path, migration_backup_sha256, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        self.problem_id,
                        int(state["current_revision"] or 0),
                        current_state_hash,
                        legacy_state_hash,
                        str(state["patch_journal_head"] or GENESIS_HASH),
                        patch_count,
                        "authenticated_pre_v15_projection_in_migration_backup",
                        previous_migration_version,
                        str(backup_path.resolve()),
                        self._sha256_file(backup_path),
                        utc_now(),
                    ),
                )
                conn.execute(
                    "UPDATE problem_state SET proof_state_hash = ? "
                    "WHERE problem_id = ?",
                    (current_state_hash, self.problem_id),
                )
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (15, ?)",
                (utc_now(),),
            )
            applied_versions.add(15)
            # Establish the new compact seal before a later migration audits
            # the effective v15 replay interval in this same transaction.
            self._ensure_scheduler_history_guards(conn)
            if state is not None:
                from .patches import _run_provenance_hash

                conn.execute(
                    "UPDATE problem_state SET run_provenance_hash = ? "
                    "WHERE problem_id = ?",
                    (_run_provenance_hash(conn), self.problem_id),
                )
        if 16 not in applied_versions:
            # Version 16 validates the complete v15 patch journal before
            # making every accepted row immutable. A constrained insert
            # trigger and partial unique index then preserve the one-row-per-
            # revision invariant, so online checks need inspect only chain
            # endpoints; explicit replay still authenticates every row.
            state_exists = conn.execute(
                "SELECT 1 FROM problem_state WHERE problem_id = ?",
                (self.problem_id,),
            ).fetchone()
            if previous_migration_version >= 8 and state_exists is not None:
                from .replay import verify_patch_journal

                replay = verify_patch_journal(
                    self,
                    conn=conn,
                    check_patch_guards=False,
                )
                if not replay["valid"]:
                    raise RuntimeError(
                        "cannot migrate: effective v15 patch journal fails full replay: "
                        + "; ".join(str(error) for error in replay["errors"][:8])
                    )
            self._ensure_patch_history_guards(conn)
            patch_guard_errors = _patch_history_guard_errors(conn)
            if patch_guard_errors:
                raise RuntimeError(
                    "cannot migrate: v16 patch-history guards are invalid: "
                    + "; ".join(patch_guard_errors)
                )
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (16, ?)",
                (utc_now(),),
            )
            applied_versions.add(16)
        if 17 not in applied_versions:
            # Version 17 replaces source-table COUNT scans in the online
            # scheduler seal with a trigger-maintained append-only insertion
            # sequence. The v16 index is fully recomputed first; thereafter a
            # source row and its provenance entry must occupy the same ordinal.
            provenance_errors = scheduler_provenance_errors(conn)
            if provenance_errors:
                raise RuntimeError(
                    "cannot migrate: v16 scheduler provenance fails full audit: "
                    + "; ".join(provenance_errors[:8])
                )
            self._drop_scheduler_history_guards(conn)
            rebuild_scheduler_source_entries(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (17, ?)",
                (utc_now(),),
            )
            applied_versions.add(17)
            self._ensure_scheduler_history_guards(conn)
            provenance_errors = scheduler_provenance_errors(conn)
            if provenance_errors:
                raise RuntimeError(
                    "cannot migrate: v17 scheduler provenance backfill is invalid: "
                    + "; ".join(provenance_errors[:8])
                )
        if 18 not in applied_versions:
            # Version 18 replaces the final event-table COUNT scan in online
            # decisions with a trigger-maintained insertion sequence. Full
            # event replay validates the pre-migration chain before backfill.
            self._ensure_event_history_guards(conn)
            state_exists = conn.execute(
                "SELECT 1 FROM problem_state WHERE problem_id = ?",
                (self.problem_id,),
            ).fetchone()
            if state_exists is not None:
                from .replay import verify_event_journal

                event_audit = verify_event_journal(self, conn=conn)
                if not event_audit["valid"]:
                    raise RuntimeError(
                        "cannot migrate: v17 event journal fails full replay: "
                        + "; ".join(str(error) for error in event_audit["errors"][:8])
                    )
            self._drop_event_history_guards(conn)
            conn.execute("DELETE FROM event_source_entries")
            conn.executemany(
                "INSERT INTO event_source_entries(sequence, event_id) VALUES (?, ?)",
                (
                    (index, int(row["event_id"]))
                    for index, row in enumerate(
                        conn.execute(
                            "SELECT event_id FROM events ORDER BY event_id"
                        ).fetchall(),
                        start=1,
                    )
                ),
            )
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (18, ?)",
                (utc_now(),),
            )
            applied_versions.add(18)
            self._ensure_event_history_guards(conn)
            event_errors = _event_source_sequence_errors(conn)
            event_errors.extend(_event_history_guard_errors(conn))
            if event_errors:
                raise RuntimeError(
                    "cannot migrate: v18 event source backfill is invalid: "
                    + "; ".join(event_errors[:8])
                )
        if 19 not in applied_versions:
            # Version 19 replaces online full-history aggregates for total,
            # outcome, retrieval, registered-intent, and session-patch counts with sufficient
            # statistics maintained by exact, seal-bound insertion triggers.
            state_exists = conn.execute(
                "SELECT 1 FROM problem_state WHERE problem_id = ?",
                (self.problem_id,),
            ).fetchone()
            if previous_migration_version >= 18 and state_exists is not None:
                seal = self.current_state_seal(conn)
                if not seal["valid"]:
                    raise RuntimeError(
                        "cannot migrate: v18 current-state seal is invalid: "
                        + "; ".join(str(error) for error in seal["errors"][:8])
                    )
            provenance_errors = scheduler_provenance_errors(conn)
            if provenance_errors:
                raise RuntimeError(
                    "cannot migrate: v18 scheduler provenance fails full audit: "
                    + "; ".join(provenance_errors[:8])
                )
            self._drop_scheduler_history_guards(conn)
            rebuild_scheduler_statistics(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (19, ?)",
                (utc_now(),),
            )
            applied_versions.add(19)
            self._ensure_scheduler_history_guards(conn)
            provenance_errors = scheduler_provenance_errors(conn)
            if provenance_errors:
                raise RuntimeError(
                    "cannot migrate: v19 scheduler statistics are invalid: "
                    + "; ".join(provenance_errors[:8])
                )
        if 20 not in applied_versions:
            # Version 20 gives randomized assignment units an exact indexed
            # uniqueness boundary and indexes the latest source row by record
            # kind. Full audit still replays every certificate and history
            # row; online dispatch no longer scans accumulated history.
            conn.execute(
                f"DROP INDEX IF EXISTS {RANDOMIZED_ASSIGNMENT_UNIT_INDEX}"
            )
            conn.execute(_randomized_assignment_v20_unit_index_sql())
            conn.execute(
                f"DROP INDEX IF EXISTS {SCHEDULER_SOURCE_KIND_SEQUENCE_INDEX}"
            )
            conn.execute(_scheduler_source_kind_sequence_index_sql())
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (20, ?)",
                (utc_now(),),
            )
            applied_versions.add(20)
            index_errors = randomized_assignment_index_errors(conn)
            index_errors.extend(scheduler_dispatch_tail_index_errors(conn))
            if index_errors:
                raise RuntimeError(
                    "cannot migrate: v20 randomized-assignment index is invalid: "
                    + "; ".join(index_errors[:8])
                )
        if 21 not in applied_versions:
            # Version 21 permits a workflow-scoped assignment to be exposed on
            # successive dispatch groups while preserving exact uniqueness for
            # each (experiment, unit, exposure) tuple. Protocol-v1 assignments
            # have no exposure index and retain their one-group uniqueness.
            conn.execute(
                f"DROP INDEX IF EXISTS {RANDOMIZED_ASSIGNMENT_UNIT_INDEX}"
            )
            conn.execute(_randomized_assignment_unit_index_sql())
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (21, ?)",
                (utc_now(),),
            )
            applied_versions.add(21)
            index_errors = randomized_assignment_index_errors(conn)
            if index_errors:
                raise RuntimeError(
                    "cannot migrate: v21 randomized-assignment index is invalid: "
                    + "; ".join(index_errors[:8])
                )
        self._ensure_scheduler_history_guards(conn)
        self._ensure_projection_baseline_guards(conn)
        self._ensure_event_history_guards(conn)
        self._ensure_patch_history_guards(conn)
        index_errors = randomized_assignment_index_errors(conn)
        index_errors.extend(scheduler_dispatch_tail_index_errors(conn))
        if index_errors:
            raise RuntimeError("; ".join(index_errors))
        conn.execute(
            "UPDATE problem_state SET schema_version = ? WHERE schema_version < ?",
            (SCHEMA_VERSION, SCHEMA_VERSION),
        )

    @staticmethod
    def _execute_ddl_script(conn: sqlite3.Connection, script: str) -> None:
        """Execute this module's simple semicolon-delimited DDL in-place."""

        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)

    @staticmethod
    def _ensure_scheduler_history_guards(conn: sqlite3.Connection) -> None:
        """Make authenticated scheduler history immutable after insertion."""

        for sql in scheduler_history_guard_sql().values():
            conn.execute(sql)

    @staticmethod
    def _drop_scheduler_history_guards(conn: sqlite3.Connection) -> None:
        """Remove v15 guards only inside a validated pre-v15 migration."""

        for name in SCHEDULER_HISTORY_GUARD_NAMES:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")

    @staticmethod
    def _ensure_projection_baseline_guards(conn: sqlite3.Connection) -> None:
        """Prevent an authenticated projection transition from being rewritten."""

        for sql in _projection_baseline_guard_sql().values():
            conn.execute(sql)

    @staticmethod
    def _ensure_event_history_guards(conn: sqlite3.Connection) -> None:
        """Permit only the writer's one-time empty-to-final hash transition."""

        for sql in _event_history_guard_sql().values():
            conn.execute(sql)

    @staticmethod
    def _ensure_patch_history_guards(conn: sqlite3.Connection) -> None:
        """Preserve the fully validated one-applied-patch-per-revision chain."""

        conn.execute(_patch_history_index_sql())
        for sql in _patch_history_guard_sql().values():
            conn.execute(sql)

    @staticmethod
    def _drop_patch_history_guards(conn: sqlite3.Connection) -> None:
        """Support authenticated v15 migration and adversarial audit fixtures."""

        for name in PATCH_HISTORY_GUARD_NAMES:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(f"DROP INDEX IF EXISTS {PATCH_HISTORY_UNIQUE_INDEX}")

    @staticmethod
    def _drop_event_history_guards(conn: sqlite3.Connection) -> None:
        """Support construction of adversarial pre-guard audit fixtures."""

        for name in EVENT_HISTORY_GUARD_NAMES:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")

    def _initialize_scheduler_fairness_state(
        self, conn: sqlite3.Connection
    ) -> None:
        """Seed compact counters from the same bounded suffix used before v10."""

        from .decision_policy import (
            decision_deferral_state_after_trace,
            decision_trace_is_parallel_companion,
        )
        from .parallel_admission import parallel_candidate_deferral_counts

        conn.execute("DELETE FROM scheduler_candidate_deferrals")
        conn.execute("DELETE FROM scheduler_fairness_meta")
        conn.execute("DELETE FROM scheduler_decision_deferrals")
        conn.execute("DELETE FROM scheduler_decision_fairness_meta")
        raw_runs = conn.execute(
            "SELECT run_id, state_revision, decision_trace_json FROM runs "
            "ORDER BY rowid DESC LIMIT ?",
            (SCHEDULER_RECENT_RUN_LIMIT,),
        ).fetchall()
        cumulative_bytes = 0
        recent_runs: list[Dict[str, Any]] = []
        latest_wave: Mapping[str, Any] | None = None
        latest_run_id = ""
        latest_primary_trace: Mapping[str, Any] | None = None
        latest_primary_run_id = ""
        latest_primary_state_revision = 0
        for index, row in enumerate(raw_runs):
            trace_text = str(row["decision_trace_json"] or "{}")
            trace_bytes = len(trace_text.encode("utf-8"))
            cumulative_bytes += trace_bytes
            included = (
                cumulative_bytes <= SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT
                or index == 0
            )
            recent_runs.append(
                {
                    "decision_trace_json": trace_text,
                    "decision_trace_history_included": included,
                }
            )
            if latest_wave is None:
                trace = json_loads(trace_text, {})
                wave = (
                    trace.get("parallel_wave_admission")
                    if isinstance(trace, Mapping)
                    else None
                )
                if isinstance(wave, Mapping):
                    latest_wave = wave
                    latest_run_id = str(row["run_id"] or "")
            if latest_primary_trace is None:
                trace = json_loads(trace_text, {})
                if isinstance(trace, Mapping) and isinstance(
                    trace.get("candidates"), list
                ) and trace.get("candidates"):
                    if not decision_trace_is_parallel_companion(trace):
                        latest_primary_trace = trace
                        latest_primary_run_id = str(row["run_id"] or "")
                        latest_primary_state_revision = max(
                            0, int(row["state_revision"] or 0)
                        )
        if latest_primary_trace is not None:
            decision_counts = decision_deferral_state_after_trace(
                {}, latest_primary_trace, enforce_prior_counts=False
            )
            trace_wave = latest_primary_trace.get("parallel_wave_admission")
            decision_id = (
                str(trace_wave.get("wave_id") or "")
                if isinstance(trace_wave, Mapping)
                else latest_primary_run_id
            )
            decision_policy_version = int(
                latest_primary_trace.get("decision_policy_version") or 1
            )
            for candidate_id, count in decision_counts.items():
                if count <= 0:
                    continue
                conn.execute(
                    "INSERT INTO scheduler_decision_deferrals("
                    "candidate_id, consecutive_deferrals, last_decision_id, "
                    "policy_version, updated_run_id) VALUES (?, ?, ?, ?, ?)",
                    (
                        candidate_id,
                        count,
                        decision_id,
                        decision_policy_version,
                        latest_primary_run_id,
                    ),
                )
            conn.execute(
                "INSERT INTO scheduler_decision_fairness_meta("
                "singleton, last_decision_id, last_state_revision, "
                "policy_version, updated_run_id) VALUES (1, ?, ?, ?, ?)",
                (
                    decision_id,
                    latest_primary_state_revision,
                    decision_policy_version,
                    latest_primary_run_id,
                ),
            )
        if latest_wave is None:
            return
        candidate_ids = [
            str(row.get("candidate_id") or "")
            for row in latest_wave.get("candidates", [])
            if isinstance(row, Mapping)
            and str(row.get("candidate_id") or "")
            and str(row.get("candidate_id") or "") != "parallel:primary"
        ]
        counts = parallel_candidate_deferral_counts(recent_runs, candidate_ids)
        wave_id = str(latest_wave.get("wave_id") or "")
        policy_version = int(latest_wave.get("policy_version") or 1)
        state_revision = (
            int(latest_wave.get("state_revision") or 0)
            if policy_version >= 4
            else 0
        )
        if not wave_id:
            return
        for candidate_id, count in counts.items():
            if count <= 0:
                continue
            conn.execute(
                    "INSERT INTO scheduler_candidate_deferrals("
                "candidate_id, consecutive_capacity_deferrals, last_wave_id, "
                "policy_version, updated_run_id) VALUES (?, ?, ?, ?, ?)",
                (candidate_id, count, wave_id, policy_version, latest_run_id),
            )
        conn.execute(
            "INSERT INTO scheduler_fairness_meta("
            "singleton, last_wave_id, last_state_revision, policy_version, "
            "updated_run_id) VALUES (1, ?, ?, ?, ?)",
            (wave_id, state_revision, policy_version, latest_run_id),
        )

    def _migrate_scheduler_fairness_provenance(
        self, conn: sqlite3.Connection
    ) -> None:
        """Allow compact fairness state to cite either legacy runs or dispatches."""

        tables = (
            (
                "scheduler_candidate_deferrals",
                "candidate_id TEXT PRIMARY KEY, "
                "consecutive_capacity_deferrals INTEGER NOT NULL "
                "CHECK(consecutive_capacity_deferrals > 0), "
                "last_wave_id TEXT NOT NULL, "
                "policy_version INTEGER NOT NULL CHECK(policy_version > 0), "
                "updated_run_id TEXT REFERENCES runs(run_id), "
                "updated_dispatch_id TEXT REFERENCES scheduler_dispatches(dispatch_id), "
                "CHECK ((updated_run_id IS NULL) != (updated_dispatch_id IS NULL))",
            ),
            (
                "scheduler_fairness_meta",
                "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
                "last_wave_id TEXT NOT NULL, "
                "last_state_revision INTEGER NOT NULL CHECK(last_state_revision >= 0), "
                "policy_version INTEGER NOT NULL CHECK(policy_version > 0), "
                "updated_run_id TEXT REFERENCES runs(run_id), "
                "updated_dispatch_id TEXT REFERENCES scheduler_dispatches(dispatch_id), "
                "CHECK ((updated_run_id IS NULL) != (updated_dispatch_id IS NULL))",
            ),
            (
                "scheduler_decision_deferrals",
                "candidate_id TEXT PRIMARY KEY, "
                "consecutive_deferrals INTEGER NOT NULL "
                "CHECK(consecutive_deferrals > 0), "
                "last_decision_id TEXT NOT NULL, "
                "policy_version INTEGER NOT NULL CHECK(policy_version > 0), "
                "updated_run_id TEXT REFERENCES runs(run_id), "
                "updated_dispatch_id TEXT REFERENCES scheduler_dispatches(dispatch_id), "
                "CHECK ((updated_run_id IS NULL) != (updated_dispatch_id IS NULL))",
            ),
            (
                "scheduler_decision_fairness_meta",
                "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
                "last_decision_id TEXT NOT NULL, "
                "last_state_revision INTEGER NOT NULL CHECK(last_state_revision >= 0), "
                "policy_version INTEGER NOT NULL CHECK(policy_version > 0), "
                "updated_run_id TEXT REFERENCES runs(run_id), "
                "updated_dispatch_id TEXT REFERENCES scheduler_dispatches(dispatch_id), "
                "CHECK ((updated_run_id IS NULL) != (updated_dispatch_id IS NULL))",
            ),
        )
        for table, definition in tables:
            columns = {
                str(row["name"])
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if "updated_dispatch_id" in columns:
                continue
            legacy = f"{table}_v10"
            conn.execute(f"ALTER TABLE {table} RENAME TO {legacy}")
            conn.execute(f"CREATE TABLE {table} ({definition})")
            legacy_columns = [
                str(row["name"])
                for row in conn.execute(f"PRAGMA table_info({legacy})").fetchall()
            ]
            selected = ", ".join(legacy_columns)
            conn.execute(
                f"INSERT INTO {table} ({selected}, updated_dispatch_id) "
                f"SELECT {selected}, NULL FROM {legacy}"
            )
            conn.execute(f"DROP TABLE {legacy}")

    @staticmethod
    def _backfill_scheduler_result_run_ids(conn: sqlite3.Connection) -> None:
        """Populate the v14 run-ID reservation without inventing history."""

        run_owners = {
            str(row["run_id"] or ""): str(row["scheduler_dispatch_id"] or "")
            for row in conn.execute(
                "SELECT run_id, scheduler_dispatch_id FROM runs"
            ).fetchall()
        }
        result_owners: Dict[str, str] = {}
        for row in conn.execute(
            "SELECT result_id, dispatch_id, execution_json "
            "FROM scheduler_dispatch_results ORDER BY result_id"
        ).fetchall():
            result_id = str(row["result_id"] or "")
            dispatch_id = str(row["dispatch_id"] or "")
            try:
                execution = json.loads(str(row["execution_json"] or ""))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"cannot migrate: scheduler result {result_id} is malformed"
                ) from exc
            run_id = (
                str(execution.get("run_id") or "")
                if isinstance(execution, dict)
                else ""
            )
            if not run_id:
                raise RuntimeError(
                    f"cannot migrate: scheduler result {result_id} has no run_id"
                )
            prior_result_dispatch = result_owners.get(run_id)
            if (
                prior_result_dispatch is not None
                and prior_result_dispatch != dispatch_id
            ):
                raise RuntimeError(
                    "cannot migrate: two scheduler results claim run_id "
                    f"{run_id!r}"
                )
            linked_dispatch = run_owners.get(run_id)
            if linked_dispatch is not None and linked_dispatch != dispatch_id:
                raise RuntimeError(
                    "cannot migrate: scheduler result run_id is already linked "
                    f"to another dispatch: {run_id!r}"
                )
            result_owners[run_id] = dispatch_id
            conn.execute(
                "UPDATE scheduler_dispatch_results SET run_id = ? "
                "WHERE result_id = ?",
                (run_id, result_id),
            )

    @staticmethod
    def _typed_relation_specs() -> tuple[tuple[str, str, str, str, str], ...]:
        """(relation table, source table, source key, JSON expression, target column)."""

        return (
            (
                "claim_parent_relations",
                "claims",
                "claim_id",
                "NEW.parent_ids_json",
                "parent_claim_id",
            ),
            (
                "inference_condition_claims",
                "inferences",
                "inference_id",
                "NEW.condition_claim_ids_json",
                "condition_claim_id",
            ),
            (
                "claim_evidence_artifacts",
                "claims",
                "claim_id",
                "NEW.evidence_artifact_ids_json",
                "artifact_id",
            ),
            (
                "route_evidence_artifacts",
                "routes",
                "route_id",
                "NEW.evidence_artifact_ids_json",
                "artifact_id",
            ),
            (
                "inference_evidence_artifacts",
                "inferences",
                "inference_id",
                "NEW.evidence_artifact_ids_json",
                "artifact_id",
            ),
            (
                "theorem_library_evidence_artifacts",
                "theorem_library_entries",
                "entry_id",
                "NEW.evidence_artifact_ids_json",
                "artifact_id",
            ),
            (
                "proof_obligation_source_artifacts",
                "debts",
                "debt_id",
                "NEW.source_artifact_ids_json",
                "artifact_id",
            ),
            (
                "proof_obligation_resolution_artifacts",
                "debts",
                "debt_id",
                "COALESCE(json_extract(NEW.resolution_evidence_json, "
                "'$.resolution_evidence_artifact_ids'), "
                "json_extract(NEW.resolution_evidence_json, '$.evidence_artifact_ids'))",
                "artifact_id",
            ),
        )

    @classmethod
    def _ensure_typed_relation_triggers(cls, conn: sqlite3.Connection) -> None:
        for relation, source, source_key, json_expression, target_column in cls._typed_relation_specs():
            for event in ("INSERT", "UPDATE"):
                trigger = f"sync_{relation}_{event.lower()}"
                conn.execute(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {trigger}
                    AFTER {event} ON {source}
                    BEGIN
                        DELETE FROM {relation} WHERE {source_key if source != 'debts' else 'proof_obligation_id'} = NEW.{source_key};
                        INSERT INTO {relation}(
                            {source_key if source != 'debts' else 'proof_obligation_id'},
                            {target_column}, position
                        )
                        SELECT NEW.{source_key}, CAST(value AS TEXT), CAST(key AS INTEGER)
                        FROM json_each({json_expression});
                    END
                    """
                )
        for event in ("INSERT", "UPDATE"):
            conn.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS sync_proof_obligation_owner_{event.lower()}
                AFTER {event} ON debts
                BEGIN
                    DELETE FROM proof_obligation_owners
                    WHERE proof_obligation_id = NEW.debt_id;
                    INSERT INTO proof_obligation_owners(
                        proof_obligation_id, owner_claim_id, owner_route_id,
                        owner_inference_id, owner_artifact_id
                    ) VALUES (
                        NEW.debt_id,
                        CASE WHEN NEW.owner_type = 'claim' THEN NEW.owner_id END,
                        CASE WHEN NEW.owner_type = 'route' THEN NEW.owner_id END,
                        CASE WHEN NEW.owner_type = 'inference' THEN NEW.owner_id END,
                        CASE WHEN NEW.owner_type = 'artifact' THEN NEW.owner_id END
                    );
                END
                """
            )

    @classmethod
    def _backfill_typed_relations(cls, conn: sqlite3.Connection) -> None:
        """One-time strict backfill; invalid legacy references abort migration."""

        for relation, source, source_key, json_expression, target_column in cls._typed_relation_specs():
            expression = json_expression.replace("NEW.", f"{source}.")
            relation_key = source_key if source != "debts" else "proof_obligation_id"
            conn.execute(f"DELETE FROM {relation}")
            conn.execute(
                f"""
                INSERT INTO {relation}({relation_key}, {target_column}, position)
                SELECT {source}.{source_key}, CAST(j.value AS TEXT), CAST(j.key AS INTEGER)
                FROM {source}, json_each({expression}) AS j
                """
            )
        conn.execute("DELETE FROM proof_obligation_owners")
        conn.execute(
            """
            INSERT INTO proof_obligation_owners(
                proof_obligation_id, owner_claim_id, owner_route_id,
                owner_inference_id, owner_artifact_id
            )
            SELECT debt_id,
                   CASE WHEN owner_type = 'claim' THEN owner_id END,
                   CASE WHEN owner_type = 'route' THEN owner_id END,
                   CASE WHEN owner_type = 'inference' THEN owner_id END,
                   CASE WHEN owner_type = 'artifact' THEN owner_id END
            FROM debts
            """
        )

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone() is not None

    def _backup_before_migration(self, conn: sqlite3.Connection) -> Optional[Path]:
        """Return a consistent backup path when an existing store needs upgrade."""

        if not self._table_exists(conn, "problem_state"):
            return None
        current_version = 0
        if self._table_exists(conn, "schema_migrations"):
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
            current_version = int(row["version"] if row else 0)
        if current_version >= STORE_MIGRATION_VERSION:
            return None
        backup_dir = self.state_dir / "migration_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_path = backup_dir / f"proof_state.schema-v{current_version}.{timestamp}.sqlite3"
        backup_conn = sqlite3.connect(backup_path)
        try:
            conn.backup(backup_conn)
            backup_conn.commit()
        finally:
            backup_conn.close()
        return backup_path

    def _current_migration_version(self, conn: sqlite3.Connection) -> int:
        if not self._table_exists(conn, "schema_migrations"):
            return 0
        try:
            versions = [
                int(row["version"])
                for row in conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ]
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("schema migration history is malformed") from exc
        maximum = versions[-1] if versions else 0
        if maximum > STORE_MIGRATION_VERSION:
            raise RuntimeError(
                f"store migration version {maximum} is newer than supported "
                f"version {STORE_MIGRATION_VERSION}"
            )
        if versions != list(range(1, maximum + 1)):
            raise RuntimeError("schema migration history is not contiguous")
        return maximum

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
        return digest.hexdigest()

    def _establish_legacy_audit_baseline(
        self,
        conn: sqlite3.Connection,
        *,
        backup_path: Path,
        previous_migration_version: int,
    ) -> None:
        """Quarantine old semantics and establish a replayable v3 suffix."""

        if conn.execute(
            "SELECT 1 FROM audit_baselines WHERE problem_id = ?",
            (self.problem_id,),
        ).fetchone():
            return
        state = conn.execute(
            "SELECT current_revision FROM problem_state WHERE problem_id = ?",
            (self.problem_id,),
        ).fetchone()
        if state is None:
            return
        # Local import avoids a module cycle at import time: patches depends
        # on ProofStateStore, while this migration needs the same canonical
        # projection used by new patch journal entries.
        from .patches import (
            _state_journal_projection,
            _state_projection_hash,
        )

        projection = _state_journal_projection(conn)
        baseline_state_hash = _state_projection_hash(projection)
        legacy_rows = conn.execute(
            "SELECT journal_entry_hash FROM patches WHERE status = 'applied' "
            "ORDER BY applied_revision ASC, patch_id ASC"
        ).fetchall()
        patch_head = (
            str(legacy_rows[-1]["journal_entry_hash"] or GENESIS_HASH)
            if legacy_rows
            else GENESIS_HASH
        )
        conn.execute(
            """
            INSERT INTO audit_baselines(
                problem_id, baseline_revision, baseline_state_hash,
                patch_journal_head, legacy_patch_count, prior_history_status,
                prior_migration_version, migration_backup_path,
                migration_backup_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.problem_id,
                int(state["current_revision"] or 0),
                baseline_state_hash,
                patch_head,
                len(legacy_rows),
                "legacy_pre_v3_nonreplayable_before_signed_migration_baseline",
                int(previous_migration_version),
                str(backup_path.resolve()),
                self._sha256_file(backup_path),
                utc_now(),
            ),
        )

    def _effective_audit_baseline(
        self,
        conn: sqlite3.Connection,
        *,
        problem_id: str | None = None,
    ) -> sqlite3.Row | None:
        """Return the newest explicit replay origin for the active projection."""

        selected_problem_id = problem_id or self.problem_id
        if self._table_exists(conn, "projection_audit_baselines"):
            row = conn.execute(
                "SELECT * FROM projection_audit_baselines WHERE problem_id = ?",
                (selected_problem_id,),
            ).fetchone()
            if row is not None:
                return row
        return conn.execute(
            "SELECT * FROM audit_baselines WHERE problem_id = ?",
            (selected_problem_id,),
        ).fetchone()

    def _initialize_current_state_seals(
        self,
        conn: sqlite3.Connection,
        *,
        require_existing_proof_seal: bool = False,
    ) -> None:
        """Establish v8 seals without concealing a pre-existing mismatch."""

        from .audit_chain import patch_entry_hash
        from .patches import (
            _run_provenance_hash,
            _state_journal_projection,
            _state_projection_hash,
        )

        for raw_state in conn.execute(
            "SELECT problem_id, current_revision, proof_state_hash "
            "FROM problem_state ORDER BY problem_id"
        ).fetchall():
            problem_id = str(raw_state["problem_id"] or "")
            current_revision = int(raw_state["current_revision"] or 0)
            projection_hash = _state_projection_hash(_state_journal_projection(conn))
            if (
                require_existing_proof_seal
                and str(raw_state["proof_state_hash"] or "") != projection_hash
            ):
                raise RuntimeError(
                    "cannot migrate: current proof state differs from its v8 current-state seal"
                )
            provenance_hash = _run_provenance_hash(conn)
            latest = conn.execute(
                "SELECT * FROM patches WHERE status = 'applied' AND applied_revision = ? "
                "ORDER BY patch_id DESC LIMIT 1",
                (current_revision,),
            ).fetchone()
            baseline = self._effective_audit_baseline(
                conn,
                problem_id=problem_id,
            )
            if baseline is not None and int(baseline["baseline_revision"] or 0) == current_revision:
                if str(baseline["baseline_state_hash"] or "") != projection_hash:
                    raise RuntimeError(
                        "cannot migrate: current proof state differs from its migration baseline"
                    )
                journal_head = str(baseline["patch_journal_head"] or GENESIS_HASH)
            elif latest is not None:
                latest_row = dict(latest)
                if str(latest_row.get("state_hash_after") or "") != projection_hash:
                    raise RuntimeError(
                        "cannot migrate: current proof state differs from its latest patch endpoint"
                    )
                expected_entry_hash = patch_entry_hash(latest_row)
                journal_head = str(latest_row.get("journal_entry_hash") or "")
                if journal_head != expected_entry_hash:
                    raise RuntimeError(
                        "cannot migrate: latest patch journal entry hash is invalid"
                    )
            elif current_revision == 0:
                journal_head = GENESIS_HASH
            else:
                raise RuntimeError(
                    "cannot migrate: current proof revision has no patch endpoint or audit baseline"
                )
            conn.execute(
                "UPDATE problem_state SET proof_state_hash = ?, run_provenance_hash = ?, "
                "patch_journal_head = ? "
                "WHERE problem_id = ?",
                (projection_hash, provenance_hash, journal_head, problem_id),
            )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> bool:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            return True
        return False

    def init_problem(
        self,
        root_statement: str,
        *,
        total_token_budget: int = 80_000_000,
        reserved_verification_budget: int = 12_000_000,
        max_reduction_depth: int = 4,
    ) -> Dict[str, Any]:
        if not root_statement.strip():
            raise ValueError("root_statement must be non-empty")
        now = utc_now()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT root_statement FROM problem_state WHERE problem_id = ?", (self.problem_id,)
            ).fetchone()
            if existing:
                if existing["root_statement"] != root_statement:
                    raise ValueError("root theorem statement is immutable and differs from existing state")
            else:
                conn.execute(
                    """
                    INSERT INTO problem_state(
                        problem_id, schema_version, current_revision, root_statement, status,
                        total_token_budget, remaining_token_budget, reserved_verification_budget,
                        max_reduction_depth, created_at, updated_at
                    ) VALUES (?, ?, 0, ?, 'active', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.problem_id,
                        SCHEMA_VERSION,
                        root_statement,
                        total_token_budget,
                        total_token_budget,
                        reserved_verification_budget,
                        max_reduction_depth,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO claims(
                        claim_id, kind, statement, normalized_statement, fingerprint, hypotheses,
                        conditions_json, validation_status, lifecycle_status, root_impact,
                        reduction_depth, parent_ids_json, source_ids_json, tags_json,
                        evidence_artifact_ids_json, created_at, updated_at
                    ) VALUES (?, 'theorem', ?, ?, ?, '', '[]', 'untested', 'active', 1.0, 0, '[]', '[]', ?, '[]', ?, ?)
                    """,
                    (
                        "root",
                        root_statement,
                        normalize_text(root_statement),
                        fingerprint_text(root_statement),
                        json_dumps(["root"]),
                        now,
                        now,
                    ),
                )
                self.write_event(
                    conn,
                    0,
                    "init",
                    {"problem_id": self.problem_id},
                )
                # The root row is the native revision-zero replay endpoint.
                # Seal it after all projection rows exist; event-chain fields
                # are intentionally outside the mathematical projection.
                from .patches import (
                    _run_provenance_hash,
                    _state_journal_projection,
                    _state_projection_hash,
                )

                initial_state_hash = _state_projection_hash(
                    _state_journal_projection(conn)
                )
                initial_run_provenance_hash = _run_provenance_hash(conn)
                conn.execute(
                    "UPDATE problem_state SET proof_state_hash = ?, "
                    "run_provenance_hash = ?, patch_journal_head = ? "
                    "WHERE problem_id = ?",
                    (
                        initial_state_hash,
                        initial_run_provenance_hash,
                        GENESIS_HASH,
                        self.problem_id,
                    ),
                )
            conn.commit()
        self._ensure_sidecar_files()
        if self.auto_snapshot:
            self.write_snapshot()
        return self.get_state()

    def _ensure_sidecar_files(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("parallel_exchange.jsonl",):
            path = self.state_dir / filename
            path.touch(exist_ok=True)

    def get_scheduler_state(
        self, *, conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Return only the rows needed for deterministic scheduling.

        The full proof state remains available through get_state() and SQLite.
        Scheduler decisions do not need artifact metadata or full retrieval-card
        bodies, so this avoids materializing bulky research/log state on every
        workflow step.
        """
        external_connection = conn is not None
        manager = nullcontext(conn) if external_connection else self.connect()
        with manager as scheduler_conn:
            if scheduler_conn is None:
                raise RuntimeError("scheduler state connection is unavailable")
            conn = scheduler_conn
            # Keep every scheduler query on one WAL snapshot.  Without an
            # explicit read transaction a concurrent patch can advance between
            # SELECTs, yielding an old current_revision mixed with new claims.
            if external_connection:
                if not conn.in_transaction:
                    raise ValueError(
                        "get_scheduler_state requires an active transaction when a connection is supplied"
                    )
            else:
                conn.execute("BEGIN")
            state = self.get_problem_row(conn)
            parallel_candidate_deferrals = {
                str(row["candidate_id"]): int(
                    row["consecutive_capacity_deferrals"]
                )
                for row in conn.execute(
                    "SELECT candidate_id, consecutive_capacity_deferrals "
                    "FROM scheduler_candidate_deferrals ORDER BY candidate_id"
                ).fetchall()
            }
            fairness_meta_row = conn.execute(
                "SELECT last_wave_id, last_state_revision, policy_version, "
                "updated_run_id FROM scheduler_fairness_meta WHERE singleton = 1"
            ).fetchone()
            parallel_fairness_state = (
                compact_dict(fairness_meta_row)
                if fairness_meta_row is not None
                else {
                    "last_wave_id": "",
                    "last_state_revision": 0,
                    "policy_version": 0,
                    "updated_run_id": "",
                }
            )
            decision_candidate_deferrals = {
                str(row["candidate_id"]): int(row["consecutive_deferrals"])
                for row in conn.execute(
                    "SELECT candidate_id, consecutive_deferrals "
                    "FROM scheduler_decision_deferrals ORDER BY candidate_id"
                ).fetchall()
            }
            decision_meta_row = conn.execute(
                "SELECT last_decision_id, last_state_revision, policy_version, "
                "updated_run_id "
                "FROM scheduler_decision_fairness_meta WHERE singleton = 1"
            ).fetchone()
            decision_fairness_state = (
                compact_dict(decision_meta_row)
                if decision_meta_row is not None
                else {
                    "last_decision_id": "",
                    "last_state_revision": 0,
                    "policy_version": 0,
                    "updated_run_id": "",
                }
            )
            claims = self.fetch_all(conn, "claims")
            routes = self.fetch_all(conn, "routes")
            inferences = self.fetch_all(conn, "inferences")
            debts = [compact_dict(row) for row in conn.execute("SELECT * FROM debts WHERE status = 'active'").fetchall()]
            premises = self.fetch_all(conn, "inference_premises")
            retrieval_cards = [
                compact_dict(row)
                for row in conn.execute(
                    "SELECT card_id, applicability_json, exact_statement, missing_hypotheses_json FROM retrieval_cards"
                ).fetchall()
            ]
            theorem_library_entries = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT entry_id, statement, source_identifiers_json, source_version,
                           source_location, certification_type, relation_to_target,
                           evidence_artifact_ids_json, tags_json
                    FROM theorem_library_entries
                    ORDER BY updated_at DESC, entry_id ASC
                    LIMIT 32
                    """
                ).fetchall()
            ]
            final_artifacts = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, artifact_type, path, state_revision, metadata_json, created_at
                    FROM artifacts
                    WHERE artifact_type IN ('final_proof', 'verified_blueprint', 'final_paper', 'revision_document')
                    ORDER BY created_at DESC, artifact_id DESC
                    """
                ).fetchall()
            ]
            research_artifacts = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, artifact_type, producer_role, state_revision,
                           content_summary, metadata_json, path, created_at
                    FROM artifacts
                    WHERE artifact_type IN (
                        'proof_dossier',
                        'proof_blueprint',
                        'research_notebook',
                        'research_diagnostic',
                        'candidate_counterexample',
                        'route_obstruction',
                        'hypothesis_gap',
                        'construction_failure',
                        'necessary_condition',
                        'literature_search_request',
                        'decomposition_plan',
                        'failed_decomposition_plan',
                        'key_failure_analysis',
                        'source_adaptation_notes',
                        'source_synthesis_report',
                        'cas_experiment_report',
                        'definition_audit_report',
                        'route_triage_report',
                        'advisor_report',
                        'approach_portfolio',
                        'advisor_synthesis',
                        'bridge_lemma_search',
                        'conjecture_portfolio',
                        'deep_session_report',
                        'definition_candidate',
                        'invention_authorization',
                        'proof_compression',
                        'conceptual_invariant_report',
                        'reference_solution'
                    )
                    ORDER BY state_revision DESC, created_at DESC, artifact_id DESC
                    LIMIT 48
                    """
                ).fetchall()
            ]
            # Global synthesis is intentionally infrequent, so its latest
            # artifact can fall outside the recent-artifact window.  Keep it
            # in scheduler state: the next advisor must see the exact artifact
            # id that the database lineage guard requires it to supersede.
            latest_advisor_synthesis = conn.execute(
                """
                SELECT artifact_id, artifact_type, producer_role, state_revision,
                       content_summary, metadata_json, path, created_at
                FROM artifacts
                WHERE artifact_type = 'advisor_synthesis'
                ORDER BY state_revision DESC, created_at DESC, artifact_id DESC
                LIMIT 1
                """
            ).fetchone()
            if latest_advisor_synthesis and not any(
                row["artifact_id"] == latest_advisor_synthesis["artifact_id"]
                for row in research_artifacts
            ):
                research_artifacts.append(compact_dict(latest_advisor_synthesis))
            # The active approach portfolio is a durable research-policy
            # input, not merely a recent artifact. Keep it visible after a
            # long local branch has filled the ordinary artifact window.
            latest_approach_portfolio = conn.execute(
                """
                SELECT artifact_id, artifact_type, producer_role, state_revision,
                       content_summary, metadata_json, path, created_at
                FROM artifacts
                WHERE artifact_type = 'approach_portfolio'
                ORDER BY state_revision DESC, created_at DESC, artifact_id DESC
                LIMIT 1
                """
            ).fetchone()
            if latest_approach_portfolio and not any(
                row["artifact_id"] == latest_approach_portfolio["artifact_id"]
                for row in research_artifacts
            ):
                research_artifacts.append(compact_dict(latest_approach_portfolio))
            # A human reference must remain visible until its reconstruction
            # is complete even when a busy run has produced more than the
            # ordinary recent-artifact window.
            latest_reference_solution = conn.execute(
                """
                SELECT artifact_id, artifact_type, producer_role, state_revision,
                       content_summary, metadata_json, path, created_at
                FROM artifacts
                WHERE artifact_type = 'reference_solution'
                ORDER BY state_revision DESC, created_at DESC, artifact_id DESC
                LIMIT 1
                """
            ).fetchone()
            if latest_reference_solution and not any(
                row["artifact_id"] == latest_reference_solution["artifact_id"]
                for row in research_artifacts
            ):
                research_artifacts.append(compact_dict(latest_reference_solution))
            hmt_artifacts = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, state_revision, metadata_json, created_at
                    FROM artifacts
                    WHERE artifact_type = 'human_readable_mathematical_text'
                    ORDER BY state_revision ASC, created_at ASC, artifact_id ASC
                    """
                ).fetchall()
            ]
            confirmed_counterexamples = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, artifact_type, producer_role, state_revision,
                           content_summary, metadata_json, path, created_at
                    FROM artifacts
                    WHERE artifact_type = 'confirmed_counterexample'
                    ORDER BY state_revision DESC, created_at DESC, artifact_id DESC
                    """
                ).fetchall()
            ]
            audit_artifacts = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, artifact_type, producer_role, state_revision,
                           content_summary, metadata_json, path, created_at
                    FROM artifacts
                    WHERE artifact_type IN (
                        'audit_subject', 'verification_report', 'integration_report',
                        'formal_backend_result', 'referee_report'
                    )
                    ORDER BY state_revision DESC, created_at DESC, artifact_id DESC
                    """
                ).fetchall()
            ]
            scheduler_statistics = {
                (str(row["statistic_kind"] or ""), str(row["statistic_key"] or "")): int(
                    row["value"] or 0
                )
                for row in conn.execute(
                    "SELECT statistic_kind, statistic_key, value "
                    "FROM scheduler_statistics"
                ).fetchall()
            }
            retrieval_run_counts = {
                key: value
                for (kind, key), value in scheduler_statistics.items()
                if kind == "retrieve_intent"
            }
            retrieval_run_total = scheduler_statistics.get(
                ("retrieve_total", ""),
                0,
            )
            untracked_retrieval_run_count = max(
                0,
                retrieval_run_total - sum(retrieval_run_counts.values()),
            )
            runs: list[Dict[str, Any]] = []
            recent_run_rows = [
                dict(row)
                for row in conn.execute(
                    """
                    WITH recent AS (
                        SELECT *
                        FROM runs
                        ORDER BY created_at DESC, run_id DESC
                        LIMIT ?
                    ), budgeted AS (
                        SELECT recent.*,
                               LENGTH(CAST(recent.decision_trace_json AS BLOB))
                                   AS decision_trace_bytes,
                               SUM(LENGTH(CAST(recent.decision_trace_json AS BLOB))) OVER (
                                   ORDER BY recent.created_at DESC, recent.run_id DESC
                                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                               ) AS cumulative_decision_trace_bytes
                        FROM recent
                    )
                    SELECT r.run_id, r.actor_role, r.mode, r.target_id, r.route_id, r.state_revision,
                           r.status, r.search_intent, r.strategy_family, r.search_setting, r.researcher_work_mode,
                           r.work_mode_source, r.failure_kind, r.output_artifact_ids_json, r.total_tokens,
                           r.selection_design, r.assignment_probability, r.exploration_stratum,
                           r.candidate_set_hash, r.selection_policy_version,
                           CASE
                               WHEN r.cumulative_decision_trace_bytes <= ?
                                    OR r.cumulative_decision_trace_bytes = r.decision_trace_bytes
                               THEN r.decision_trace_json
                               ELSE '{}'
                           END AS decision_trace_json,
                           r.decision_trace_bytes,
                           r.cumulative_decision_trace_bytes,
                           r.error_artifact_id, COALESCE(a.content_summary, '') AS error_summary,
                           r.created_at
                    FROM budgeted r
                    LEFT JOIN artifacts a ON a.artifact_id = r.error_artifact_id
                    ORDER BY r.created_at DESC, r.run_id DESC
                    """,
                    (
                        SCHEDULER_RECENT_RUN_LIMIT,
                        SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT,
                    ),
                ).fetchall()
            ]
            included_trace_count = sum(
                1
                for row in recent_run_rows
                if int(row.get("cumulative_decision_trace_bytes") or 0)
                <= SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT
                or int(row.get("cumulative_decision_trace_bytes") or 0)
                == int(row.get("decision_trace_bytes") or 0)
            )
            included_trace_bytes = sum(
                int(row.get("decision_trace_bytes") or 0)
                for row in recent_run_rows[:included_trace_count]
            )
            recent_window_trace_bytes = sum(
                int(row.get("decision_trace_bytes") or 0)
                for row in recent_run_rows
            )
            recent_runs = []
            for row in recent_run_rows:
                row["decision_trace_history_included"] = bool(
                    int(row.get("cumulative_decision_trace_bytes") or 0)
                    <= SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT
                    or int(row.get("cumulative_decision_trace_bytes") or 0)
                    == int(row.get("decision_trace_bytes") or 0)
                )
                row.pop("decision_trace_bytes", None)
                row.pop("cumulative_decision_trace_bytes", None)
                recent_runs.append(compact_dict(row))
            # Online scheduling uses a bounded descriptive history. Historical
            # outcomes are not causal and have no ranking effect, so loading
            # the complete run table here only made decision latency grow
            # without bound. Complete lifetime analysis belongs in reporting.
            outcome_roles = {
                "researcher",
                "adversarial_reviewer",
                "villain",
                "literature_researcher",
            }
            outcome_runs = [
                row
                for row in reversed(recent_runs)
                if str(row.get("actor_role") or "") in outcome_roles
            ]
            outcome_run_population_count = scheduler_statistics.get(
                ("outcome_run", ""),
                0,
            )
            session_patch_rows = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT patch_id, applied_revision, authority_json, state_delta_json
                    FROM patches INDEXED BY idx_patches_applied_session_revision
                    WHERE status = 'applied' AND authority_source = 'session'
                    ORDER BY applied_revision DESC, patch_id DESC
                    LIMIT ?
                    """,
                    (SCHEDULER_SESSION_PATCH_LIMIT,),
                ).fetchall()
            ]
            session_patch_population_count = scheduler_statistics.get(
                ("session_patch", ""),
                0,
            )
            run_count = scheduler_statistics.get(("total_run", ""), 0)
            publication_reviews = self.fetch_all(conn, "publication_reviews")
            context_requests = self.fetch_all(conn, "context_requests")
            claim_assurance = self.fetch_all(conn, "claim_assurance")

        # Keep only causal, host-observed mathematical row changes.  A child
        # cannot manufacture this summary in artifact metadata: the run_id is
        # taken from the host-issued patch authority and the changes from the
        # replay journal produced after invariant validation.
        mathematical_tables = {
            "claims",
            "routes",
            "inferences",
            "inference_premises",
            "debts",
            "retrieval_cards",
            "theorem_library_entries",
        }
        accepted_mathematical_deltas: list[Dict[str, Any]] = []
        for row in session_patch_rows:
            authority = json_loads(row.get("authority_json"), {})
            if not isinstance(authority, dict):
                continue
            run_id = str(authority.get("run_id") or "")
            if not run_id:
                continue
            raw_delta = json_loads(row.get("state_delta_json"), [])
            if not isinstance(raw_delta, list):
                continue
            changes = [
                {
                    "op": str(change.get("op") or ""),
                    "table": str(change.get("table") or ""),
                    "key": dict(change.get("key") or {}),
                }
                for change in raw_delta
                if isinstance(change, dict)
                and str(change.get("table") or "") in mathematical_tables
            ]
            if changes:
                accepted_mathematical_deltas.append(
                    {
                        "run_id": run_id,
                        "patch_id": str(row.get("patch_id") or ""),
                        "applied_revision": int(row.get("applied_revision") or 0),
                        "changes": changes,
                    }
                )

        premise_map: Dict[str, List[str]] = {}
        for item in sorted(premises, key=lambda x: (x["inference_id"], x["position"])):
            premise_map.setdefault(item["inference_id"], []).append(item["premise_claim_id"])
        for inf in inferences:
            inf["premise_claim_ids"] = premise_map.get(inf["inference_id"], [])

        return {
            "problem_state": state,
            "claims": claims,
            "routes": routes,
            "inferences": inferences,
            "debts": debts,
            "runs": runs,
            "run_counts": {
                "retrieve_total": retrieval_run_total,
                "retrieve_by_intent": retrieval_run_counts,
                "retrieve_by_intent_complete": untracked_retrieval_run_count == 0,
                "retrieve_untracked_total": untracked_retrieval_run_count,
                "registered_retrieval_intents": list(
                    ONLINE_RETRIEVAL_COUNT_INTENTS
                ),
            },
            "recent_runs": recent_runs,
            "parallel_candidate_deferrals": parallel_candidate_deferrals,
            "parallel_fairness_state": parallel_fairness_state,
            "decision_candidate_deferrals": decision_candidate_deferrals,
            "decision_fairness_state": decision_fairness_state,
            "decision_trace_history": {
                "population_count": run_count,
                "recent_window_run_count": len(recent_run_rows),
                "included_trace_count": included_trace_count,
                "included_trace_bytes": included_trace_bytes,
                "recent_window_trace_bytes": recent_window_trace_bytes,
                "run_limit": SCHEDULER_RECENT_RUN_LIMIT,
                "byte_limit": SCHEDULER_DECISION_TRACE_HISTORY_BYTE_LIMIT,
                "recent_window_complete": (
                    included_trace_count == len(recent_run_rows)
                ),
                "complete": (
                    run_count <= SCHEDULER_RECENT_RUN_LIMIT
                    and included_trace_count == len(recent_run_rows)
                ),
            },
            "outcome_runs": outcome_runs,
            "outcome_history": {
                "population_count": outcome_run_population_count,
                "included_count": len(outcome_runs),
                "complete": outcome_run_population_count <= len(outcome_runs),
                "online_limit": SCHEDULER_RECENT_RUN_LIMIT,
                "ranking_effect": "disabled",
            },
            "accepted_mathematical_deltas": accepted_mathematical_deltas,
            "accepted_delta_history": {
                "session_patch_population_count": session_patch_population_count,
                "included_patch_count": len(session_patch_rows),
                "complete": session_patch_population_count <= len(session_patch_rows),
                "online_limit": SCHEDULER_SESSION_PATCH_LIMIT,
            },
            "run_count": run_count,
            "retrieval_cards": retrieval_cards,
            "theorem_library_entries": theorem_library_entries,
            "final_artifacts": final_artifacts,
            "research_artifacts": research_artifacts,
            "hmt_artifacts": hmt_artifacts,
            "confirmed_counterexamples": confirmed_counterexamples,
            "audit_artifacts": audit_artifacts,
            "publication_reviews": publication_reviews,
            "context_requests": context_requests,
            "claim_assurance": claim_assurance,
        }

    def get_revision(self, conn: Optional[sqlite3.Connection] = None) -> int:
        close = conn is None
        conn = conn or self.connect()
        try:
            row = conn.execute(
                "SELECT current_revision FROM problem_state WHERE problem_id = ?", (self.problem_id,)
            ).fetchone()
            if row is None:
                raise ValueError("problem state is not initialized")
            revision = row["current_revision"]
            if (
                isinstance(revision, bool)
                or not isinstance(revision, int)
                or revision < 0
            ):
                raise ValueError("current_revision is not a nonnegative integer")
            return revision
        finally:
            if close:
                conn.close()

    def get_problem_row(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        row = conn.execute("SELECT * FROM problem_state WHERE problem_id = ?", (self.problem_id,)).fetchone()
        if row is None:
            raise ValueError("problem state is not initialized")
        return compact_dict(row)

    def fetch_all(self, conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
        return [compact_dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]

    def get_state(self) -> Dict[str, Any]:
        with self.connect() as conn:
            conn.execute("BEGIN")
            return self.snapshot_from_conn(conn)

    def snapshot_from_conn(
        self,
        conn: sqlite3.Connection,
        *,
        include_audit_journal: bool = True,
    ) -> Dict[str, Any]:
        if not conn.in_transaction:
            raise ValueError("snapshot_from_conn requires an active read transaction")
        state = self.get_problem_row(conn)
        claims = self.fetch_all(conn, "claims")
        routes = self.fetch_all(conn, "routes")
        inferences = self.fetch_all(conn, "inferences")
        debts = self.fetch_all(conn, "debts")
        artifacts = self.fetch_all(conn, "artifacts")
        runs = self.fetch_all(conn, "runs")
        cards = self.fetch_all(conn, "retrieval_cards")
        library_entries = self.fetch_all(conn, "theorem_library_entries")
        premises = self.fetch_all(conn, "inference_premises")
        publication_reviews = self.fetch_all(conn, "publication_reviews")
        context_requests = self.fetch_all(conn, "context_requests")
        claim_assurance = self.fetch_all(conn, "claim_assurance")
        # Ordinary model contexts do not consume the full audit journals.
        # Long attempts can contain many large row-delta/event records, so
        # materializing them on every session would make context construction
        # grow with total run age even though none of those rows is emitted.
        # Replay and resume retain the complete default view.
        patches = self.fetch_all(conn, "patches") if include_audit_journal else []
        events = self.fetch_all(conn, "events") if include_audit_journal else []

        premise_map: Dict[str, List[str]] = {}
        for item in sorted(premises, key=lambda x: (x["inference_id"], x["position"])):
            premise_map.setdefault(item["inference_id"], []).append(item["premise_claim_id"])
        for inf in inferences:
            inf["premise_claim_ids"] = premise_map.get(inf["inference_id"], [])

        return {
            "problem_state": state,
            "claims": claims,
            "routes": routes,
            "inferences": inferences,
            "debts": debts,
            "artifacts": artifacts,
            "runs": runs,
            "retrieval_cards": cards,
            "theorem_library_entries": library_entries,
            "publication_reviews": publication_reviews,
            "context_requests": context_requests,
            "claim_assurance": claim_assurance,
            "patches": patches,
            "events": events,
        }

    def write_snapshot(self) -> Dict[str, Any]:
        with self.connect() as conn:
            conn.execute("BEGIN")
            seal = self.current_state_seal(conn)
            if not seal["valid"]:
                raise RuntimeError(
                    "refusing to snapshot an invalid current state: "
                    + "; ".join(str(error) for error in seal["errors"][:8])
                )
            snapshot = self.snapshot_from_conn(conn)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self.snapshot_path.is_symlink():
            raise ValueError("proof-state snapshot destination must not be a symbolic link")
        encoded = json.dumps(
            snapshot,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        descriptor, raw_temporary_path = tempfile.mkstemp(
            prefix=f".{self.snapshot_path.name}.",
            suffix=".tmp",
            dir=self.snapshot_path.parent,
        )
        temporary_path = Path(raw_temporary_path)
        try:
            offset = 0
            while offset < len(encoded):
                offset += os.write(descriptor, encoded[offset:])
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary_path, self.snapshot_path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary_path.unlink(missing_ok=True)
        return snapshot

    def write_event(
        self,
        conn: sqlite3.Connection,
        revision: int,
        event_type: str,
        payload: Dict[str, Any],
    ) -> int:
        """Append one host event and advance its independently verifiable chain."""

        payload_errors = _policy_projection_payload_errors(str(event_type), payload)
        if payload_errors:
            raise ValueError(
                f"invalid {event_type} event payload: " + "; ".join(payload_errors)
            )

        # Several event-only callers read diagnostic state and then append an
        # event without first changing another table.  A plain SELECT does not
        # reserve SQLite's writer lock, so two processes could otherwise read
        # the same predecessor and create a fork.  Acquire the write lock
        # before reading the chain head.  Callers already inside a patch or
        # migration transaction have obtained that lock through their prior
        # write/BEGIN IMMEDIATE and retain it here.
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")

        event_seal = self.current_event_seal(
            conn,
            check_policy_projection=False,
        )
        if not event_seal["valid"]:
            raise RuntimeError(
                "current event-journal seal is invalid: "
                + "; ".join(str(error) for error in event_seal["errors"][:8])
            )
        if str(event_type) == "run_control_policy":
            link_errors = _run_control_policy_link_errors(conn, payload)
            if link_errors:
                raise ValueError(
                    "invalid run_control_policy event payload: "
                    + "; ".join(link_errors)
                )

        chain_state = conn.execute(
            "SELECT event_chain_length, event_chain_head, policy_event_head "
            "FROM problem_state WHERE problem_id = ?",
            (self.problem_id,),
        ).fetchone()
        if chain_state is None:
            raise ValueError("cannot append an event before problem_state exists")
        previous = str(chain_state["event_chain_head"] or GENESIS_HASH)
        policy_head = str(chain_state["policy_event_head"] or GENESIS_HASH)
        created_at = utc_now()
        cursor = conn.execute(
            "INSERT INTO events(revision, event_type, payload_json, created_at, "
            "previous_event_hash, event_hash) VALUES (?, ?, ?, ?, ?, '')",
            (int(revision), str(event_type), json_dumps(payload), created_at, previous),
        )
        event_id = int(cursor.lastrowid)
        digest = event_entry_hash(
            {
                "event_id": event_id,
                "revision": int(revision),
                "event_type": str(event_type),
                "payload_json": json_dumps(payload),
                "created_at": created_at,
                "previous_event_hash": previous,
            }
        )
        conn.execute(
            "UPDATE events SET event_hash = ? WHERE event_id = ?",
            (digest, event_id),
        )
        if str(event_type) in POLICY_EVENT_TYPES:
            policy_head = digest
        conn.execute(
            "UPDATE problem_state SET event_chain_length = ?, event_chain_head = ?, "
            "policy_event_head = ? WHERE problem_id = ?",
            (
                int(chain_state["event_chain_length"] or 0) + 1,
                digest,
                policy_head,
                self.problem_id,
            ),
        )
        return event_id

    def current_event_seal(
        self,
        conn: Optional[sqlite3.Connection] = None,
        *,
        check_policy_projection: bool = True,
    ) -> Dict[str, Any]:
        """Check the current event tail and policy projection incrementally.

        This validates the recorded count, current tail entry, predecessor,
        latest policy entry, and persisted configuration values.  It is not a
        replacement for full event-journal replay, which is still required to
        authenticate every historical entry.
        """

        if conn is None:
            with self.connect() as owned_conn:
                owned_conn.execute("BEGIN")
                return self.current_event_seal(
                    owned_conn,
                    check_policy_projection=check_policy_projection,
                )
        if not conn.in_transaction:
            raise ValueError("current_event_seal shared connection requires a transaction")

        errors: List[str] = []
        state_row = conn.execute(
            "SELECT completion_policy, parallel_branches, research_parallel_mode, "
            "run_status, event_chain_length, event_chain_head, policy_event_head "
            "FROM problem_state WHERE problem_id = ?",
            (self.problem_id,),
        ).fetchone()
        if state_row is None:
            return {
                "valid": False,
                "event_count": 0,
                "event_chain_head": GENESIS_HASH,
                "policy_event_head": GENESIS_HASH,
                "errors": ["problem state is not initialized"],
            }

        errors.extend(_event_history_guard_errors(conn))

        recorded_count = _sealed_db_integer(
            state_row["event_chain_length"],
            label="recorded event-chain length",
            errors=errors,
            minimum=0,
        )
        recorded_head = str(state_row["event_chain_head"] or GENESIS_HASH)
        recorded_policy_head = str(
            state_row["policy_event_head"] or GENESIS_HASH
        )
        source_tracking = _event_source_tracking_available(conn)
        source_tail = (
            conn.execute(
                "SELECT sequence, event_id FROM event_source_entries "
                "ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if source_tracking
            else None
        )
        if source_tracking:
            observed_count = (
                int(source_tail["sequence"] or 0)
                if source_tail is not None
                else 0
            )
        else:
            observed_count = int(
                conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()[
                    "count"
                ]
            )
        if observed_count != recorded_count:
            errors.append(
                "event row count does not match the recorded event-chain length"
            )

        tail_rows = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM events ORDER BY event_id DESC LIMIT 2"
            ).fetchall()
        ]
        observed_head = GENESIS_HASH
        if tail_rows:
            latest = tail_rows[0]
            if source_tracking and (
                source_tail is None
                or int(source_tail["event_id"] or 0)
                != int(latest.get("event_id") or 0)
            ):
                errors.append(
                    "event source insertion tail does not match the event-journal tail"
                )
            observed_head = str(latest.get("event_hash") or "")
            try:
                expected_latest_hash = event_entry_hash(latest)
            except (TypeError, ValueError, OverflowError) as exc:
                expected_latest_hash = ""
                errors.append(f"current event-chain head entry is malformed: {exc}")
            if observed_head != expected_latest_hash:
                errors.append("current event-chain head entry hash is invalid")
            expected_previous = (
                str(tail_rows[1].get("event_hash") or "")
                if len(tail_rows) > 1
                else GENESIS_HASH
            )
            if str(latest.get("previous_event_hash") or "") != expected_previous:
                errors.append("current event-chain head has the wrong predecessor")
        elif source_tracking and source_tail is not None:
            errors.append("event source insertion sequence exists without an event")
        if recorded_head != observed_head:
            errors.append("recorded event-chain head does not match the current tail")

        policy_types = sorted(POLICY_EVENT_TYPES)
        placeholders = ",".join("?" for _ in policy_types)
        latest_policy_row = conn.execute(
            f"SELECT * FROM events WHERE event_type IN ({placeholders}) "
            "ORDER BY event_id DESC LIMIT 1",
            policy_types,
        ).fetchone()
        observed_policy_head = GENESIS_HASH
        if latest_policy_row is not None:
            latest_policy = dict(latest_policy_row)
            observed_policy_head = str(latest_policy.get("event_hash") or "")
            try:
                expected_policy_hash = event_entry_hash(latest_policy)
            except (TypeError, ValueError, OverflowError) as exc:
                expected_policy_hash = ""
                errors.append(f"latest policy event entry is malformed: {exc}")
            if observed_policy_head != expected_policy_hash:
                errors.append("latest policy event entry hash is invalid")
        if recorded_policy_head != observed_policy_head:
            errors.append("recorded policy-event head does not match the current policy tail")

        if check_policy_projection:
            latest_by_type: Dict[str, Dict[str, Any]] = {}
            for event_type in (
                "completion_policy",
                "parallel_branch_mode",
                "run_control_policy",
            ):
                row = conn.execute(
                    "SELECT * FROM events WHERE event_type = ? "
                    "ORDER BY event_id DESC LIMIT 1",
                    (event_type,),
                ).fetchone()
                if row is not None:
                    latest_by_type[event_type] = dict(row)

            def payload_for(event_type: str) -> Dict[str, Any]:
                row = latest_by_type.get(event_type)
                if row is None:
                    return {}
                payload = json_loads(row.get("payload_json"), None)
                if not isinstance(payload, dict):
                    errors.append(f"latest {event_type} payload is not an object")
                    return {}
                errors.extend(
                    f"latest {event_type} payload: {error}"
                    for error in _policy_projection_payload_errors(
                        event_type, payload
                    )
                )
                try:
                    expected_hash = event_entry_hash(row)
                except (TypeError, ValueError, OverflowError) as exc:
                    expected_hash = ""
                    errors.append(f"latest {event_type} event entry is malformed: {exc}")
                if str(row.get("event_hash") or "") != expected_hash:
                    errors.append(f"latest {event_type} event entry hash is invalid")
                return payload

            completion = payload_for("completion_policy")
            completion_present = "completion_policy" in latest_by_type
            completion_value = str(
                state_row["completion_policy"] or DEFAULT_COMPLETION_POLICY
            )
            if completion_present:
                if str(completion.get("to") or "") != completion_value:
                    errors.append(
                        "completion_policy state does not match its latest current event"
                    )
            elif completion_value != DEFAULT_COMPLETION_POLICY:
                errors.append("nondefault completion_policy has no current event")

            parallel = payload_for("parallel_branch_mode")
            parallel_present = "parallel_branch_mode" in latest_by_type
            parallel_workers = _sealed_db_integer(
                state_row["parallel_branches"],
                label="parallel_branches state",
                errors=errors,
                minimum=0,
            )
            parallel_mode = str(state_row["research_parallel_mode"] or "")
            if parallel_present:
                event_workers = parallel.get("to")
                if isinstance(event_workers, bool) or not isinstance(
                    event_workers, int
                ):
                    errors.append(
                        "latest parallel_branch_mode worker count is not an integer"
                    )
                elif event_workers != parallel_workers:
                    errors.append(
                        "parallel_branches state does not match its latest current event"
                    )
                if str(parallel.get("mode") or "") != parallel_mode:
                    errors.append(
                        "research_parallel_mode state does not match its latest current event"
                    )
            elif parallel_workers != 0 or parallel_mode:
                errors.append("nondefault parallel-branch state has no current event")

            run_control = payload_for("run_control_policy")
            run_control_present = "run_control_policy" in latest_by_type
            run_status = str(state_row["run_status"] or "running")
            if run_control_present:
                if str(run_control.get("to") or "") != run_status:
                    errors.append(
                        "run_status state does not match its latest current policy event"
                    )
                linked_event_id = run_control.get("run_control_event_id")
                if (
                    isinstance(linked_event_id, int)
                    and not isinstance(linked_event_id, bool)
                    and linked_event_id > 0
                ):
                    errors.extend(
                        f"latest run_control_policy payload: {error}"
                        for error in _run_control_policy_link_errors(
                            conn, run_control
                        )
                    )
            elif run_status != "running":
                errors.append("nondefault run_status has no current policy event")

        return {
            "valid": not errors,
            "event_count": observed_count,
            "recorded_event_count": recorded_count,
            "event_chain_head": observed_head,
            "recorded_event_chain_head": recorded_head,
            "policy_event_head": observed_policy_head,
            "recorded_policy_event_head": recorded_policy_head,
            "errors": errors,
        }

    def current_state_seal(
        self,
        conn: Optional[sqlite3.Connection] = None,
        *,
        include_projection: bool = False,
    ) -> Dict[str, Any]:
        """Check the live projection against its current replay endpoint.

        This is deliberately an incremental boundary check, not a substitute
        for :func:`verify_patch_journal`.  It detects unjournaled current-state
        changes, missing revisions, and corruption of the head entry in time
        proportional to the current state rather than the entire history.
        """

        if conn is None:
            with self.connect() as owned_conn:
                owned_conn.execute("BEGIN")
                return self.current_state_seal(
                    owned_conn,
                    include_projection=include_projection,
                )
        if not conn.in_transaction:
            raise ValueError("current_state_seal shared connection requires a transaction")

        from .audit_chain import patch_entry_hash
        from .patches import (
            _run_provenance_hash,
            _state_journal_projection,
            _state_projection_hash,
        )

        errors: List[str] = []
        state_row = conn.execute(
            "SELECT current_revision, proof_state_hash, run_provenance_hash, "
            "patch_journal_head "
            "FROM problem_state WHERE problem_id = ?",
            (self.problem_id,),
        ).fetchone()
        if state_row is None:
            return {
                "valid": False,
                "proof_revision": 0,
                "proof_state_hash": "",
                "run_provenance_hash": "",
                "patch_journal_head": GENESIS_HASH,
                "errors": ["problem state is not initialized"],
            }

        current_revision = _sealed_db_integer(
            state_row["current_revision"],
            label="current proof revision",
            errors=errors,
            minimum=0,
        )
        recorded_state_hash = str(state_row["proof_state_hash"] or "")
        recorded_run_provenance_hash = str(
            state_row["run_provenance_hash"] or ""
        )
        recorded_journal_head = str(
            state_row["patch_journal_head"] or GENESIS_HASH
        )
        observed_projection: Dict[str, list[Dict[str, Any]]] | None = None
        try:
            observed_projection = _state_journal_projection(conn)
            observed_state_hash = _state_projection_hash(observed_projection)
        except (sqlite3.Error, TypeError, ValueError, OverflowError) as exc:
            observed_state_hash = ""
            errors.append(f"live proof-state projection is malformed: {exc}")
        if recorded_state_hash != observed_state_hash:
            errors.append(
                "live proof-state projection does not match its recorded current-state seal"
            )
        try:
            observed_run_provenance_hash = _run_provenance_hash(conn)
        except (sqlite3.Error, TypeError, ValueError, OverflowError) as exc:
            observed_run_provenance_hash = ""
            errors.append(f"live run-selection provenance is malformed: {exc}")
        if recorded_run_provenance_hash != observed_run_provenance_hash:
            errors.append(
                "live run-selection provenance does not match its recorded current-state seal"
            )

        baseline = self._effective_audit_baseline(conn)
        errors.extend(_projection_baseline_guard_errors(conn))
        errors.extend(_patch_history_guard_errors(conn))
        errors.extend(randomized_assignment_index_errors(conn))
        errors.extend(scheduler_dispatch_tail_index_errors(conn))
        start_revision = (
            _sealed_db_integer(
                baseline["baseline_revision"],
                label="audit baseline revision",
                errors=errors,
                minimum=0,
            )
            if baseline
            else 0
        )
        start_head = (
            str(baseline["patch_journal_head"] or GENESIS_HASH)
            if baseline
            else GENESIS_HASH
        )
        if start_revision > current_revision:
            errors.append("audit baseline revision exceeds current proof revision")

        expected_count = max(0, current_revision - start_revision)
        future = conn.execute(
            "SELECT applied_revision FROM patches WHERE status = 'applied' "
            "AND applied_revision > ? LIMIT 1",
            (current_revision,),
        ).fetchone()
        if future is not None:
            errors.append("applied patch history extends beyond the current proof revision")

        expected_head = start_head
        if expected_count:
            first = conn.execute(
                "SELECT previous_entry_hash FROM patches WHERE status = 'applied' "
                "AND applied_revision = ? ORDER BY patch_id ASC LIMIT 1",
                (start_revision + 1,),
            ).fetchone()
            if first is None or str(first["previous_entry_hash"] or "") != start_head:
                errors.append("first current-journal patch does not extend the audit baseline")

            latest_raw = conn.execute(
                "SELECT * FROM patches WHERE status = 'applied' AND applied_revision = ? "
                "ORDER BY patch_id DESC LIMIT 1",
                (current_revision,),
            ).fetchone()
            if latest_raw is None:
                errors.append("current proof revision has no patch-journal head entry")
            else:
                latest = dict(latest_raw)
                try:
                    expected_latest_hash = patch_entry_hash(latest)
                except (TypeError, ValueError, OverflowError) as exc:
                    expected_latest_hash = ""
                    errors.append(f"current patch-journal head entry is malformed: {exc}")
                expected_head = str(latest.get("journal_entry_hash") or "")
                if expected_head != expected_latest_hash:
                    errors.append("current patch-journal head entry hash is invalid")
                if str(latest.get("state_hash_after") or "") != observed_state_hash:
                    errors.append(
                        "live proof-state projection does not match the current patch endpoint"
                    )
                predecessor = conn.execute(
                    "SELECT journal_entry_hash FROM patches WHERE status = 'applied' "
                    "AND applied_revision = ? LIMIT 1",
                    (current_revision - 1,),
                ).fetchone()
                expected_previous = (
                    str(predecessor["journal_entry_hash"] or "")
                    if predecessor is not None
                    else start_head
                )
                if str(latest.get("previous_entry_hash") or "") != expected_previous:
                    errors.append("current patch-journal head has the wrong predecessor")

        if recorded_journal_head != expected_head:
            errors.append("recorded patch-journal head does not match the current revision")
        event_seal = self.current_event_seal(conn)
        errors.extend(
            f"event journal: {error}" for error in event_seal["errors"]
        )
        result = {
            "valid": not errors,
            "proof_revision": current_revision,
            "proof_state_hash": observed_state_hash,
            "recorded_proof_state_hash": recorded_state_hash,
            "run_provenance_hash": observed_run_provenance_hash,
            "recorded_run_provenance_hash": recorded_run_provenance_hash,
            "patch_journal_head": expected_head,
            "recorded_patch_journal_head": recorded_journal_head,
            "journal_start_revision": start_revision,
            "event_seal": event_seal,
            "errors": errors,
        }
        if include_projection and observed_projection is not None:
            # Internal patch writers can reuse the exact sealed snapshot
            # rather than materializing and serializing the same state twice.
            result["_proof_state_projection"] = observed_projection
        return result

    def audit_chain_heads(
        self, conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Return roots that bind a child packet to current audit/config history."""

        if conn is None:
            with self.connect() as owned_conn:
                owned_conn.execute("BEGIN")
                return self.audit_chain_heads(owned_conn)
        if not conn.in_transaction:
            raise ValueError("audit_chain_heads shared connection requires a transaction")
        seal = self.current_state_seal(conn)
        if not seal["valid"]:
            raise RuntimeError(
                "current proof-state seal is invalid: "
                + "; ".join(str(error) for error in seal["errors"][:8])
            )
        state = conn.execute(
            "SELECT current_revision, event_chain_length, event_chain_head, "
            "policy_event_head FROM problem_state WHERE problem_id = ?",
            (self.problem_id,),
        ).fetchone()
        patch = conn.execute(
            "SELECT applied_revision, journal_entry_hash FROM patches WHERE status = 'applied' "
            "ORDER BY applied_revision DESC, patch_id DESC LIMIT 1"
        ).fetchone()
        baseline = self._effective_audit_baseline(conn)
        if state is None:
            raise ValueError("problem state is not initialized")
        current_revision = int(state["current_revision"] or 0)
        patch_matches_revision = bool(
            patch and int(patch["applied_revision"] or 0) == current_revision
        )
        baseline_matches_revision = bool(
            baseline and int(baseline["baseline_revision"] or 0) == current_revision
        )
        if current_revision and not (
            patch_matches_revision or baseline_matches_revision
        ):
            raise RuntimeError(
                "proof revision and patch-journal head are inconsistent in the audit snapshot"
            )
        patch_head = (
            str(patch["journal_entry_hash"] or GENESIS_HASH)
            if patch_matches_revision
            else str(baseline["patch_journal_head"] or GENESIS_HASH)
            if baseline_matches_revision
            else GENESIS_HASH
        )
        return {
            "proof_revision": current_revision,
            "patch_journal_head": patch_head,
            "proof_state_hash": str(seal["proof_state_hash"]),
            "run_provenance_hash": str(seal["run_provenance_hash"]),
            "event_chain_length": int(state["event_chain_length"] or 0),
            "event_chain_head": str(state["event_chain_head"] or GENESIS_HASH),
            "policy_event_head": str(state["policy_event_head"] or GENESIS_HASH),
        }

    def audit_chain_heads_after_validated_commit(
        self,
        *,
        expected_revision: int,
    ) -> Dict[str, Any]:
        """Read heads produced by the immediately preceding validated patch.

        The patch kernel has already checked the pre-state, validated the
        resulting invariants, and committed all heads atomically. This narrow
        handoff verifies the new patch and event tails without reserializing
        the complete proof state a second time. A concurrent later revision
        fails closed so its scheduler must replan.
        """

        from .audit_chain import patch_entry_hash

        with self.connect() as conn:
            conn.execute("BEGIN")
            state = conn.execute(
                "SELECT current_revision, proof_state_hash, run_provenance_hash, "
                "patch_journal_head, event_chain_length, event_chain_head, "
                "policy_event_head FROM problem_state WHERE problem_id = ?",
                (self.problem_id,),
            ).fetchone()
            if state is None:
                raise RuntimeError("validated scheduler commit lost problem state")
            current_revision = int(state["current_revision"] or 0)
            if current_revision > expected_revision:
                raise ValidatedCommitSuperseded(
                    f"proof state advanced from dispatch revision {expected_revision} "
                    f"to {current_revision}; recover before execution"
                )
            if current_revision < expected_revision:
                raise RuntimeError(
                    f"validated scheduler revision {expected_revision} is not visible "
                    f"(current revision {current_revision}); check database storage"
                )
            patch_raw = conn.execute(
                "SELECT * FROM patches WHERE status = 'applied' "
                "AND applied_revision = ? ORDER BY patch_id DESC LIMIT 1",
                (current_revision,),
            ).fetchone()
            if patch_raw is None:
                raise RuntimeError("validated scheduler commit has no patch-journal row")
            patch = dict(patch_raw)
            patch_head = str(patch.get("journal_entry_hash") or "")
            if (
                patch_head != patch_entry_hash(patch)
                or patch_head != str(state["patch_journal_head"] or "")
            ):
                raise RuntimeError("validated scheduler commit has an invalid patch tail")
            event_raw = conn.execute(
                "SELECT * FROM events ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
            event_head = GENESIS_HASH
            if event_raw is not None:
                event = dict(event_raw)
                event_head = str(event.get("event_hash") or "")
                if event_head != event_entry_hash(event):
                    raise RuntimeError(
                        "validated scheduler commit has an invalid event tail"
                    )
            if event_head != str(state["event_chain_head"] or GENESIS_HASH):
                raise RuntimeError(
                    "validated scheduler commit event head disagrees with state"
                )
            return {
                "proof_revision": current_revision,
                "patch_journal_head": patch_head,
                "proof_state_hash": str(state["proof_state_hash"] or ""),
                "run_provenance_hash": str(state["run_provenance_hash"] or ""),
                "event_chain_length": int(state["event_chain_length"] or 0),
                "event_chain_head": event_head,
                "policy_event_head": str(
                    state["policy_event_head"] or GENESIS_HASH
                ),
            }

    def row_exists(self, conn: sqlite3.Connection, table: str, key: str, value: str) -> bool:
        row = conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (value,)).fetchone()
        return row is not None

    def get_claim(self, conn: sqlite3.Connection, claim_id: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        return compact_dict(row) if row else None

    def get_route(self, conn: sqlite3.Connection, route_id: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM routes WHERE route_id = ?", (route_id,)).fetchone()
        return compact_dict(row) if row else None

    def get_artifact(self, conn: sqlite3.Connection, artifact_id: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        return compact_dict(row) if row else None

    def active_blocking_debts(self, conn: sqlite3.Connection, owner_ids: Sequence[str]) -> List[Dict[str, Any]]:
        if not owner_ids:
            return []
        placeholders = ",".join("?" for _ in owner_ids)
        rows = conn.execute(
            f"SELECT * FROM debts WHERE owner_id IN ({placeholders}) AND status = 'active' AND severity = 'blocking'",
            list(owner_ids),
        ).fetchall()
        return [compact_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Completion policy: run-level full-proof-first vs
    # partial-results policy persisted on problem_state.
    # ------------------------------------------------------------------

    def get_completion_policy(self, conn: Optional[sqlite3.Connection] = None) -> str:
        close = conn is None
        conn = conn or self.connect()
        try:
            row = conn.execute(
                "SELECT completion_policy FROM problem_state WHERE problem_id = ?", (self.problem_id,)
            ).fetchone()
            if row is None:
                raise ValueError("problem state is not initialized")
            return str(row["completion_policy"] or DEFAULT_COMPLETION_POLICY)
        finally:
            if close:
                conn.close()

    def set_completion_policy(self, policy: str, *, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Persist the explicit run-level completion policy and record an event.

        Only this explicit setter changes the policy; soft wording in the
        problem markdown never flips it.
        """
        if policy not in COMPLETION_POLICIES:
            allowed = ", ".join(sorted(COMPLETION_POLICIES))
            raise ValueError(f"invalid completion_policy: {policy}; expected one of {allowed}")
        now = utc_now()
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            previous = str(state.get("completion_policy") or DEFAULT_COMPLETION_POLICY)
            if previous == policy:
                return {"problem_id": self.problem_id, "previous": previous, "completion_policy": policy, "unchanged": True}
            conn.execute(
                "UPDATE problem_state SET completion_policy = ?, updated_at = ? WHERE problem_id = ?",
                (policy, now, self.problem_id),
            )
            self.write_event(
                conn,
                int(state["current_revision"]),
                "completion_policy",
                {"from": previous, "to": policy, "reason": reason, "source": source},
            )
            conn.commit()
        return {"problem_id": self.problem_id, "previous": previous, "completion_policy": policy, "at": now}

    # ------------------------------------------------------------------
    # Parallel branch mode: explicit multi_branch_research
    # worker count persisted on problem_state.
    # ------------------------------------------------------------------

    def set_parallel_branches(self, workers: int, *, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Persist the multi_branch_research worker count (0 off, 2..5 on).

        Records the mode name on problem_state.research_parallel_mode and a
        parallel_branch_mode event; a no-op when the value is unchanged.
        """
        workers = int(workers or 0)
        if workers != 0 and not (2 <= workers <= 5):
            raise ValueError("parallel_branches must be 0 (off) or between 2 and 5")
        mode = "multi_branch_research" if workers >= 2 else ""
        now = utc_now()
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            previous = int(state.get("parallel_branches") or 0)
            if previous == workers:
                return {
                    "problem_id": self.problem_id,
                    "previous": previous,
                    "parallel_branches": workers,
                    "research_parallel_mode": mode,
                    "unchanged": True,
                }
            conn.execute(
                "UPDATE problem_state SET parallel_branches = ?, research_parallel_mode = ?, updated_at = ? "
                "WHERE problem_id = ?",
                (workers, mode, now, self.problem_id),
            )
            self.write_event(
                conn,
                int(state["current_revision"]),
                "parallel_branch_mode",
                {"from": previous, "to": workers, "mode": mode, "reason": reason, "source": source},
            )
            conn.commit()
        return {
            "problem_id": self.problem_id,
            "previous": previous,
            "parallel_branches": workers,
            "research_parallel_mode": mode,
            "at": now,
        }

    # ------------------------------------------------------------------
    # Run control: persisted pause/stop semantics and
    # wall-clock vs active-compute vs paused-time accounting.
    # ------------------------------------------------------------------

    def get_run_status(self, conn: Optional[sqlite3.Connection] = None) -> str:
        close = conn is None
        conn = conn or self.connect()
        try:
            row = conn.execute(
                "SELECT run_status FROM problem_state WHERE problem_id = ?", (self.problem_id,)
            ).fetchone()
            if row is None:
                raise ValueError("problem state is not initialized")
            return str(row["run_status"] or "running")
        finally:
            if close:
                conn.close()

    def peek_run_control(self) -> Dict[str, Any]:
        """Cheap, migration-free read of the current run-control state.

        Safe to poll from a watcher thread while a child session runs: it never
        migrates, never raises, and returns {} when the state is unreadable
        (e.g. run_status column not yet migrated).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT run_status FROM problem_state WHERE problem_id = ?", (self.problem_id,)
                ).fetchone()
                if row is None:
                    return {}
                event = conn.execute(
                    "SELECT payload_json FROM events WHERE event_type = 'run_control' ORDER BY event_id DESC LIMIT 1"
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return {}
        payload = json_loads(event["payload_json"] if event else None, {})
        if not isinstance(payload, dict):
            payload = {}
        return {"run_status": str(row["run_status"] or "running"), "hard": bool(payload.get("hard"))}

    def set_run_status(
        self,
        new_status: str,
        *,
        reason: str = "",
        source: str = "cli",
        hard: bool = False,
    ) -> Dict[str, Any]:
        """Transition run status and bind the change into session policy identity.

        ``run_control`` remains the compatibility/telemetry event consumed by
        timing reports.  ``run_control_policy`` is a chained companion used by
        new databases to invalidate a model session whose context predates a
        pause, stop, or resume decision.  Keeping the event types separate
        avoids retrospectively changing policy heads in historical databases.
        """
        if new_status not in RUN_STATUSES:
            raise ValueError(f"invalid run_status: {new_status}")
        now = utc_now()
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            previous = str(state.get("run_status") or "running")
            conn.execute(
                "UPDATE problem_state SET run_status = ?, updated_at = ? WHERE problem_id = ?",
                (new_status, now, self.problem_id),
            )
            payload = {
                "from": previous,
                "to": new_status,
                "reason": reason,
                "source": source,
                "hard": bool(hard),
            }
            run_control_event_id = self.write_event(
                conn, int(state["current_revision"]), "run_control", payload
            )
            self.write_event(
                conn,
                int(state["current_revision"]),
                "run_control_policy",
                {**payload, "run_control_event_id": run_control_event_id},
            )
            conn.commit()
        return {"problem_id": self.problem_id, "previous": previous, "run_status": new_status, "at": now}

    def request_pause(self, *, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Soft pause: the workflow finishes the current child session, then
        stops dispatching new actions and parks the run as 'paused'."""
        current = self.get_run_status()
        if current in {"paused", "pause_requested"}:
            return {"problem_id": self.problem_id, "previous": current, "run_status": current, "unchanged": True}
        return self.set_run_status(
            "pause_requested",
            reason=reason or "run pause requested; finish the current child session, then stop dispatching",
            source=source,
        )

    def resume_run(self, *, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Clear a pause/stop so the workflow may continue from the latest
        accepted proof-state revision."""
        current = self.get_run_status()
        if current == "running":
            return {"problem_id": self.problem_id, "previous": current, "run_status": current, "unchanged": True}
        return self.set_run_status(
            "running",
            reason=reason or f"run resumed from {current}; continuing from the latest accepted proof-state revision",
            source=source,
        )

    def request_stop(self, *, hard: bool = False, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Stop the run. Soft stop finishes the current child session first;
        hard stop also terminates the active child session (the workflow's
        run-control watcher observes 'stopping' with hard=True) and records an
        interruption event artifact."""
        result = self.set_run_status(
            "stopping",
            reason=reason or ("hard stop requested" if hard else "soft stop requested"),
            source=source,
            hard=hard,
        )
        if hard:
            result["interruption_artifact_id"] = self.record_interruption_artifact(
                reason=reason or "hard stop requested; active child sessions terminated",
                source=source,
            )
        return result

    def record_interruption_artifact(self, *, reason: str, source: str = "cli") -> str:
        """Record a replayable interruption artifact for a hard stop."""
        now = utc_now()
        stamp = now.replace(":", "").replace("-", "").replace("+0000", "Z").replace(".", "_")
        artifact_id = f"run_interruption_{stamp}"
        content = (
            f"# Run interruption event\n\n"
            f"- problem_id: {self.problem_id}\n"
            f"- at: {now}\n"
            f"- source: {source}\n"
            f"- reason: {reason}\n\n"
            "The active child session (if any) was terminated by a hard stop request. "
            "No mathematical assertion was changed; this event advances the artifact journal by one revision.\n"
        )
        # Local import avoids the module cycle: patches imports ProofStateStore.
        from .patches import apply_operator_patch

        revision = self.get_revision()
        outcome = apply_operator_patch(
            self,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": self.problem_id,
                "base_revision": revision,
                "actor_role": "human_operator",
                "target_id": artifact_id,
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": artifact_id,
                        "artifact_type": "run_interruption_event",
                        "content": content,
                        "content_summary": f"Hard stop interruption: {reason}"[:500],
                        "metadata": {"reason": reason, "source": source},
                    }
                ],
                "evidence_artifact_ids": [],
                "rationale": "record the operator-requested hard-stop interruption",
            },
        )
        if not outcome.accepted:
            raise RuntimeError("interruption artifact patch rejected: " + "; ".join(outcome.errors))
        with self.connect() as conn:
            self.write_event(
                conn,
                outcome.revision,
                "run_interrupted",
                {
                    "artifact_id": artifact_id,
                    "reason": reason,
                    "source": source,
                    "patch_id": outcome.patch_id,
                },
            )
            conn.commit()
        return artifact_id

    def get_run_timing(self) -> Dict[str, Any]:
        """Three separated timing numbers for reports/benchmarks.

        - wall_clock_seconds: elapsed from problem init to the last recorded
          activity (or now while the run is live).
        - active_compute_seconds: recorded child-session wall time (the runs
          table); scheduler overhead is deliberately not attributed here.
        - paused_seconds: total time inside explicit paused intervals derived
          from run_control events (paused -> next non-paused transition).
        """
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            events = [
                compact_dict(row)
                for row in conn.execute(
                    "SELECT event_id, event_type, payload_json, created_at FROM events "
                    "WHERE event_type IN ('run_control', 'run_interrupted') ORDER BY event_id ASC"
                ).fetchall()
            ]
            runs_wall = conn.execute(
                "SELECT COALESCE(SUM(wall_time_seconds), 0.0) AS total FROM runs"
            ).fetchone()["total"]
            last_activity = conn.execute("SELECT MAX(created_at) AS latest FROM events").fetchone()["latest"]

        run_status = str(state.get("run_status") or "running")
        started_at = _parse_timestamp(str(state.get("created_at") or ""))
        now = datetime.now(timezone.utc)
        if run_status in {"stopped", "awaiting_human", "completed"}:
            end_candidates = [
                _parse_timestamp(str(last_activity or "")),
                _parse_timestamp(str(state.get("updated_at") or "")),
            ]
            end_time = max((ts for ts in end_candidates if ts is not None), default=now)
        else:
            end_time = now

        paused_seconds = 0.0
        pause_count = 0
        pause_started: Optional[datetime] = None
        control_events: List[Dict[str, Any]] = []
        for event in events:
            payload = json_loads(event.get("payload_json"), {})
            if not isinstance(payload, dict):
                payload = {}
            created = _parse_timestamp(str(event.get("created_at") or ""))
            control_events.append(
                {
                    "event_type": str(event.get("event_type") or ""),
                    "from": str(payload.get("from") or ""),
                    "to": str(payload.get("to") or ""),
                    "reason": str(payload.get("reason") or ""),
                    "source": str(payload.get("source") or ""),
                    "hard": bool(payload.get("hard")),
                    "at": str(event.get("created_at") or ""),
                }
            )
            if str(event.get("event_type") or "") != "run_control" or created is None:
                continue
            to_status = str(payload.get("to") or "")
            if to_status == "paused" and pause_started is None:
                pause_started = created
                pause_count += 1
            elif to_status not in {"paused", ""} and pause_started is not None:
                paused_seconds += max(0.0, (created - pause_started).total_seconds())
                pause_started = None
        if pause_started is not None:
            paused_seconds += max(0.0, (end_time - pause_started).total_seconds())

        wall_clock = 0.0
        if started_at is not None:
            wall_clock = max(0.0, (end_time - started_at).total_seconds())
        return {
            "run_status": run_status,
            "wall_clock_seconds": round(wall_clock, 3),
            "active_compute_seconds": round(float(runs_wall or 0.0), 3),
            "paused_seconds": round(paused_seconds, 3),
            "pause_count": pause_count,
            "run_control_events": control_events,
        }


def _parse_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
