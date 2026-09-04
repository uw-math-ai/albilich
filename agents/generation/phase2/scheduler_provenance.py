from __future__ import annotations

"""Authenticated append-only index for scheduler execution history."""

import sqlite3
from typing import Any, Dict, Mapping

from .audit_chain import GENESIS_HASH
from .models import json_dumps, sha256_text


SCHEDULER_PROVENANCE_VERSION = 1
ONLINE_RETRIEVAL_COUNT_INTENTS = ("citation_pass",)

_RECORD_SPECS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "run",
        "runs",
        "run_id",
        (
            "run_id",
            "selection_design",
            "assignment_probability",
            "exploration_stratum",
            "candidate_set_hash",
            "selection_policy_version",
            "decision_trace_json",
            "decision_state_revision",
            "scheduler_dispatch_id",
            "dispatched_action_hash",
        ),
    ),
    (
        "dispatch",
        "scheduler_dispatches",
        "dispatch_id",
        (
            "dispatch_id",
            "dispatch_group_id",
            "dispatch_position",
            "is_companion",
            "actor_role",
            "mode",
            "target_id",
            "route_id",
            "decision_state_revision",
            "proof_state_hash",
            "prior_run_provenance_hash",
            "selection_design",
            "candidate_set_hash",
            "selection_policy_version",
            "decision_trace_json",
            "dispatched_action_hash",
            "execution_contract_json",
            "committed_at",
        ),
    ),
    (
        "attempt",
        "scheduler_dispatch_attempts",
        "attempt_id",
        (
            "attempt_id",
            "dispatch_id",
            "attempt_number",
            "session_plan_hash",
            "executor_identity",
            "claimed_at",
            "event_id",
        ),
    ),
    (
        "result",
        "scheduler_dispatch_results",
        "result_id",
        (
            "result_id",
            "dispatch_id",
            "attempt_id",
            "run_id",
            "result_hash",
            "completed_at",
            "event_id",
        ),
    ),
)

_SPEC_BY_KIND = {spec[0]: spec for spec in _RECORD_SPECS}


def _legacy_v16_scheduler_history_guard_sql() -> Dict[str, str]:
    """Return the guards used before trigger-maintained source commitments."""

    tables = tuple(spec[1] for spec in _RECORD_SPECS) + (
        "scheduler_provenance_entries",
    )
    return {
        f"guard_{table}_{operation}": (
            f"CREATE TRIGGER IF NOT EXISTS guard_{table}_{operation} "
            f"BEFORE {operation.upper()} ON {table} "
            "BEGIN SELECT RAISE(ABORT, "
            "'scheduler history is append-only'); END"
        )
        for table in tables
        for operation in ("update", "delete")
    }


def _v18_scheduler_history_guard_sql() -> Dict[str, str]:
    """Return guards used before compact run/patch statistics."""

    guards = _legacy_v16_scheduler_history_guard_sql()
    for record_kind, table, key, _ in _RECORD_SPECS:
        guards[f"capture_{table}_scheduler_source_insert"] = (
            f"CREATE TRIGGER IF NOT EXISTS capture_{table}_scheduler_source_insert "
            f"AFTER INSERT ON {table} BEGIN "
            "INSERT INTO scheduler_source_entries(record_kind, record_id) "
            f"VALUES ('{record_kind}', NEW.{key}); END"
        )
    guards["guard_scheduler_provenance_entries_insert"] = (
        "CREATE TRIGGER IF NOT EXISTS guard_scheduler_provenance_entries_insert "
        "BEFORE INSERT ON scheduler_provenance_entries WHEN NOT EXISTS ("
        "SELECT 1 FROM scheduler_source_entries "
        "WHERE sequence = NEW.sequence "
        "AND record_kind = NEW.record_kind "
        "AND record_id = NEW.record_id) "
        "BEGIN SELECT RAISE(ABORT, "
        "'scheduler provenance has no matching source insertion'); END"
    )
    for operation in ("update", "delete"):
        guards[f"guard_scheduler_source_entries_{operation}"] = (
            "CREATE TRIGGER IF NOT EXISTS "
            f"guard_scheduler_source_entries_{operation} "
            f"BEFORE {operation.upper()} ON scheduler_source_entries "
            "BEGIN SELECT RAISE(ABORT, "
            "'scheduler source history is append-only'); END"
        )
    return guards


def scheduler_history_guard_sql() -> Dict[str, str]:
    """Return the sole canonical definition of scheduler-history triggers."""

    guards = _v18_scheduler_history_guard_sql()
    statistic_triggers = {
        "capture_runs_total_statistic": (
            "CREATE TRIGGER IF NOT EXISTS capture_runs_total_statistic "
            "AFTER INSERT ON runs BEGIN "
            "INSERT INTO scheduler_statistics(statistic_kind, statistic_key, value) "
            "VALUES ('total_run', '', 1) ON CONFLICT(statistic_kind, statistic_key) "
            "DO UPDATE SET value = value + 1; END"
        ),
        "capture_runs_outcome_statistic": (
            "CREATE TRIGGER IF NOT EXISTS capture_runs_outcome_statistic "
            "AFTER INSERT ON runs WHEN NEW.actor_role IN ("
            "'researcher', 'adversarial_reviewer', 'villain', "
            "'literature_researcher') BEGIN "
            "INSERT INTO scheduler_statistics(statistic_kind, statistic_key, value) "
            "VALUES ('outcome_run', '', 1) ON CONFLICT(statistic_kind, statistic_key) "
            "DO UPDATE SET value = value + 1; END"
        ),
        "capture_runs_retrieval_total_statistic": (
            "CREATE TRIGGER IF NOT EXISTS capture_runs_retrieval_total_statistic "
            "AFTER INSERT ON runs WHEN NEW.mode = 'retrieve' BEGIN "
            "INSERT INTO scheduler_statistics(statistic_kind, statistic_key, value) "
            "VALUES ('retrieve_total', '', 1) "
            "ON CONFLICT(statistic_kind, statistic_key) "
            "DO UPDATE SET value = value + 1; END"
        ),
        "capture_patches_session_statistic": (
            "CREATE TRIGGER IF NOT EXISTS capture_patches_session_statistic "
            "AFTER INSERT ON patches WHEN NEW.status = 'applied' "
            "AND NEW.authority_source = 'session' BEGIN "
            "INSERT INTO scheduler_statistics(statistic_kind, statistic_key, value) "
            "VALUES ('session_patch', '', 1) "
            "ON CONFLICT(statistic_kind, statistic_key) "
            "DO UPDATE SET value = value + 1; END"
        ),
    }
    for index, intent in enumerate(ONLINE_RETRIEVAL_COUNT_INTENTS):
        quoted_intent = intent.replace("'", "''")
        statistic_triggers[f"capture_runs_retrieval_intent_{index}_statistic"] = (
            "CREATE TRIGGER IF NOT EXISTS "
            f"capture_runs_retrieval_intent_{index}_statistic "
            "AFTER INSERT ON runs WHEN NEW.mode = 'retrieve' "
            f"AND NEW.search_intent = '{quoted_intent}' BEGIN "
            "INSERT INTO scheduler_statistics(statistic_kind, statistic_key, value) "
            f"VALUES ('retrieve_intent', '{quoted_intent}', 1) "
            "ON CONFLICT(statistic_kind, statistic_key) "
            "DO UPDATE SET value = value + 1; END"
        )
    guards.update(statistic_triggers)
    return guards


SCHEDULER_HISTORY_GUARD_NAMES = tuple(scheduler_history_guard_sql())


def _canonical_trigger_sql(sql: Any) -> str:
    """Normalize SQLite's omission of ``IF NOT EXISTS`` in sqlite_master."""

    return " ".join(str(sql or "").split()).replace(
        "CREATE TRIGGER IF NOT EXISTS ",
        "CREATE TRIGGER ",
        1,
    )


def _canonical_record(row: Mapping[str, Any], fields: tuple[str, ...]) -> Dict[str, Any]:
    return {field: row[field] for field in fields}


def scheduler_record_payload(
    conn: sqlite3.Connection,
    *,
    record_kind: str,
    record_id: str,
) -> Dict[str, Any]:
    spec = _SPEC_BY_KIND.get(record_kind)
    if spec is None:
        raise ValueError(f"unknown scheduler provenance record kind: {record_kind}")
    _, table, key, fields = spec
    row = conn.execute(
        f"SELECT {', '.join(fields)} FROM {table} WHERE {key} = ?",
        (record_id,),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"missing {record_kind} record for scheduler provenance: {record_id}"
        )
    return _canonical_record(row, fields)


def append_scheduler_provenance_entry(
    conn: sqlite3.Connection,
    *,
    record_kind: str,
    record_id: str,
) -> str:
    """Append one compact record commitment in the caller's transaction."""

    payload_hash = sha256_text(
        json_dumps(
            scheduler_record_payload(
                conn,
                record_kind=record_kind,
                record_id=record_id,
            )
        )
    )
    tail = conn.execute(
        "SELECT sequence, entry_hash FROM scheduler_provenance_entries "
        "ORDER BY sequence DESC LIMIT 1"
    ).fetchone()
    sequence = int(tail["sequence"] or 0) + 1 if tail is not None else 1
    previous_hash = (
        str(tail["entry_hash"] or GENESIS_HASH)
        if tail is not None
        else GENESIS_HASH
    )
    entry_hash = sha256_text(
        json_dumps(
            {
                "version": SCHEDULER_PROVENANCE_VERSION,
                "sequence": sequence,
                "record_kind": record_kind,
                "record_id": record_id,
                "payload_hash": payload_hash,
                "previous_hash": previous_hash,
            }
        )
    )
    conn.execute(
        "INSERT INTO scheduler_provenance_entries("
        "sequence, record_kind, record_id, payload_hash, previous_hash, entry_hash) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            sequence,
            record_kind,
            record_id,
            payload_hash,
            previous_hash,
            entry_hash,
        ),
    )
    return entry_hash


def rebuild_scheduler_provenance(conn: sqlite3.Connection) -> None:
    """Build the v15 index once from a fully validated v14 history."""

    conn.execute("DELETE FROM scheduler_provenance_entries")
    for record_kind, table, key, _ in _RECORD_SPECS:
        for row in conn.execute(
            f"SELECT {key} FROM {table} ORDER BY {key}"
        ).fetchall():
            append_scheduler_provenance_entry(
                conn,
                record_kind=record_kind,
                record_id=str(row[key] or ""),
            )


def rebuild_scheduler_source_entries(conn: sqlite3.Connection) -> None:
    """Backfill the trigger-maintained source sequence from validated v16 data."""

    conn.execute("DELETE FROM scheduler_source_entries")
    conn.executemany(
        "INSERT INTO scheduler_source_entries(sequence, record_kind, record_id) "
        "VALUES (?, ?, ?)",
        (
            (
                int(row["sequence"]),
                str(row["record_kind"] or ""),
                str(row["record_id"] or ""),
            )
            for row in conn.execute(
                "SELECT sequence, record_kind, record_id "
                "FROM scheduler_provenance_entries ORDER BY sequence"
            ).fetchall()
        ),
    )


def _expected_scheduler_statistics(conn: sqlite3.Connection) -> Dict[tuple[str, str], int]:
    statistics: Dict[tuple[str, str], int] = {}
    total_runs = int(conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"])
    if total_runs:
        statistics[("total_run", "")] = total_runs
    outcome_runs = int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE actor_role IN ("
            "'researcher', 'adversarial_reviewer', 'villain', "
            "'literature_researcher')"
        ).fetchone()["n"]
    )
    if outcome_runs:
        statistics[("outcome_run", "")] = outcome_runs
    retrieval_runs = int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE mode = 'retrieve'"
        ).fetchone()["n"]
    )
    if retrieval_runs:
        statistics[("retrieve_total", "")] = retrieval_runs
    for intent in ONLINE_RETRIEVAL_COUNT_INTENTS:
        intent_runs = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM runs WHERE mode = 'retrieve' "
                "AND search_intent = ?",
                (intent,),
            ).fetchone()["n"]
        )
        if intent_runs:
            statistics[("retrieve_intent", intent)] = intent_runs
    session_patches = int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM patches WHERE status = 'applied' "
            "AND authority_source = 'session'"
        ).fetchone()["n"]
    )
    if session_patches:
        statistics[("session_patch", "")] = session_patches
    return statistics


def rebuild_scheduler_statistics(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM scheduler_statistics")
    conn.executemany(
        "INSERT INTO scheduler_statistics(statistic_kind, statistic_key, value) "
        "VALUES (?, ?, ?)",
        (
            (kind, key, value)
            for (kind, key), value in sorted(
                _expected_scheduler_statistics(conn).items()
            )
        ),
    )


def _source_tracking_available(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'scheduler_source_entries'"
        ).fetchone()
        is not None
        and conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = 17"
        ).fetchone()
        is not None
    )


def _statistics_available(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'scheduler_statistics'"
        ).fetchone()
        is not None
        and conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = 19"
        ).fetchone()
        is not None
    )


def _expected_history_guards(conn: sqlite3.Connection) -> Dict[str, str]:
    if _statistics_available(conn):
        return scheduler_history_guard_sql()
    if _source_tracking_available(conn):
        return _v18_scheduler_history_guard_sql()
    return _legacy_v16_scheduler_history_guard_sql()


def scheduler_provenance_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Return the constant-size online seal projection."""

    tail = conn.execute(
        "SELECT sequence, entry_hash FROM scheduler_provenance_entries "
        "ORDER BY sequence DESC LIMIT 1"
    ).fetchone()
    source_tracking = _source_tracking_available(conn)
    statistics_available = _statistics_available(conn)
    expected_guards = _expected_history_guards(conn)
    guards = [
        dict(row)
        for row in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
            "AND name IN ("
            + ",".join("?" for _ in expected_guards)
            + ") ORDER BY name",
            tuple(expected_guards),
        ).fetchall()
    ]
    summary = {
        "version": SCHEDULER_PROVENANCE_VERSION,
        "entry_count": int(tail["sequence"] or 0) if tail is not None else 0,
        "entry_hash": str(tail["entry_hash"] or GENESIS_HASH)
        if tail is not None
        else GENESIS_HASH,
        "history_guards": guards,
    }
    if source_tracking:
        source_tail = conn.execute(
            "SELECT sequence, record_kind, record_id "
            "FROM scheduler_source_entries ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        summary["source_tracking_version"] = 1
        summary["source_entry_count"] = (
            int(source_tail["sequence"] or 0) if source_tail is not None else 0
        )
        summary["source_tail_kind"] = (
            str(source_tail["record_kind"] or "") if source_tail is not None else ""
        )
        summary["source_tail_id"] = (
            str(source_tail["record_id"] or "") if source_tail is not None else ""
        )
    else:
        summary["record_counts"] = {
            table: int(
                conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            )
            for _, table, _, _ in _RECORD_SPECS
        }
    if statistics_available:
        summary["statistics_version"] = 1
        summary["statistics"] = [
            dict(row)
            for row in conn.execute(
                "SELECT statistic_kind, statistic_key, value "
                "FROM scheduler_statistics ORDER BY statistic_kind, statistic_key"
            ).fetchall()
        ]
    return summary


def scheduler_provenance_errors(conn: sqlite3.Connection) -> list[str]:
    """Recompute the complete index for explicit audit/replay."""

    tables = {
        record_kind: {
            str(row[key] or ""): _canonical_record(row, fields)
            for row in conn.execute(
                f"SELECT {', '.join(fields)} FROM {table} ORDER BY {key}"
            ).fetchall()
        }
        for record_kind, table, key, fields in _RECORD_SPECS
    }
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    previous_hash = GENESIS_HASH
    expected_sequence = 1
    for row in conn.execute(
        "SELECT * FROM scheduler_provenance_entries ORDER BY sequence"
    ).fetchall():
        sequence = row["sequence"]
        record_kind = str(row["record_kind"] or "")
        record_id = str(row["record_id"] or "")
        key = (record_kind, record_id)
        payload = tables.get(record_kind, {}).get(record_id)
        payload_hash = sha256_text(json_dumps(payload)) if payload is not None else ""
        expected_hash = sha256_text(
            json_dumps(
                {
                    "version": SCHEDULER_PROVENANCE_VERSION,
                    "sequence": expected_sequence,
                    "record_kind": record_kind,
                    "record_id": record_id,
                    "payload_hash": payload_hash,
                    "previous_hash": previous_hash,
                }
            )
        )
        if (
            type(sequence) is not int
            or sequence != expected_sequence
            or record_kind not in tables
            or payload is None
            or key in seen
            or str(row["payload_hash"] or "") != payload_hash
            or str(row["previous_hash"] or "") != previous_hash
            or str(row["entry_hash"] or "") != expected_hash
        ):
            errors.append(
                f"scheduler provenance entry {sequence!r} for "
                f"{record_kind}:{record_id} is invalid"
            )
        seen.add(key)
        previous_hash = str(row["entry_hash"] or "")
        expected_sequence += 1
    expected = {
        (record_kind, record_id)
        for record_kind, records in tables.items()
        for record_id in records
    }
    missing = sorted(expected - seen)
    extra = sorted(seen - expected)
    if missing:
        errors.append(
            "scheduler provenance is missing record commitments: "
            + ", ".join(f"{kind}:{record_id}" for kind, record_id in missing[:8])
        )
    if extra:
        errors.append(
            "scheduler provenance has unknown record commitments: "
            + ", ".join(f"{kind}:{record_id}" for kind, record_id in extra[:8])
        )
    source_tracking = _source_tracking_available(conn)
    if source_tracking:
        source_rows = [
            (
                int(row["sequence"]),
                str(row["record_kind"] or ""),
                str(row["record_id"] or ""),
            )
            for row in conn.execute(
                "SELECT sequence, record_kind, record_id "
                "FROM scheduler_source_entries ORDER BY sequence"
            ).fetchall()
        ]
        provenance_rows = [
            (
                int(row["sequence"]),
                str(row["record_kind"] or ""),
                str(row["record_id"] or ""),
            )
            for row in conn.execute(
                "SELECT sequence, record_kind, record_id "
                "FROM scheduler_provenance_entries ORDER BY sequence"
            ).fetchall()
        ]
        if source_rows != provenance_rows:
            errors.append(
                "scheduler source insertion sequence does not match provenance entries"
            )
    statistics_available = _statistics_available(conn)
    if statistics_available:
        observed_statistics: Dict[tuple[str, str], int] = {}
        for row in conn.execute(
            "SELECT statistic_kind, statistic_key, value "
            "FROM scheduler_statistics"
        ).fetchall():
            key = (
                str(row["statistic_kind"] or ""),
                str(row["statistic_key"] or ""),
            )
            value = row["value"]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                errors.append(
                    f"scheduler compact statistic {key[0]}:{key[1]} is invalid"
                )
                continue
            observed_statistics[key] = value
        if observed_statistics != _expected_scheduler_statistics(conn):
            errors.append(
                "scheduler compact statistics do not match authoritative history"
            )
    expected_guards = _expected_history_guards(conn)
    observed_guards = {
        str(row["name"] or ""): _canonical_trigger_sql(row["sql"])
        for row in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
            "AND name IN ("
            + ",".join("?" for _ in expected_guards)
            + ") ORDER BY name",
            tuple(expected_guards),
        ).fetchall()
    }
    for name, sql in expected_guards.items():
        if observed_guards.get(name) != _canonical_trigger_sql(sql):
            errors.append(
                f"scheduler provenance append-only guard {name} is missing or altered"
            )
    return errors
