from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .models import json_dumps, json_loads


GENESIS_HASH = "0" * 64


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json_dumps(dict(payload)).encode("utf-8")).hexdigest()


def _decoded_json(value: Any, default: Any) -> Any:
    decoded = json_loads(value, default)
    return decoded if isinstance(decoded, type(default)) else default


def patch_entry_payload(
    row: Mapping[str, Any], *, previous_entry_hash: str | None = None
) -> dict[str, Any]:
    """Canonical, semantic content of one accepted patch-journal entry.

    State endpoint hashes alone deliberately say nothing about annotations.
    This payload binds all authority and explanatory fields as well as the
    exact operation and row-delta semantics into a separate append-only chain.
    JSON values are decoded before hashing so insignificant whitespace is not
    confused with a semantic change.
    """

    previous = (
        str(previous_entry_hash)
        if previous_entry_hash is not None
        else str(row.get("previous_entry_hash") or GENESIS_HASH)
    )
    return {
        "patch_id": str(row.get("patch_id") or ""),
        "schema_version": int(row.get("schema_version") or 0),
        "problem_id": str(row.get("problem_id") or ""),
        "base_revision": int(row.get("base_revision") or 0),
        "actor_role": str(row.get("actor_role") or ""),
        "target_id": str(row.get("target_id") or ""),
        "operations": _decoded_json(row.get("operations_json"), []),
        "evidence_artifact_ids": _decoded_json(
            row.get("evidence_artifact_ids_json"), []
        ),
        "rationale": str(row.get("rationale") or ""),
        "status": str(row.get("status") or ""),
        "rejection_reason": str(row.get("rejection_reason") or ""),
        "created_at": str(row.get("created_at") or ""),
        "applied_revision": int(row.get("applied_revision") or 0),
        "authority_source": str(row.get("authority_source") or ""),
        "authority": _decoded_json(row.get("authority_json"), {}),
        "state_delta": _decoded_json(row.get("state_delta_json"), []),
        "state_hash_before": str(row.get("state_hash_before") or ""),
        "state_hash_after": str(row.get("state_hash_after") or ""),
        "previous_entry_hash": previous,
    }


def patch_entry_hash(
    row: Mapping[str, Any], *, previous_entry_hash: str | None = None
) -> str:
    return _canonical_hash(
        patch_entry_payload(row, previous_entry_hash=previous_entry_hash)
    )


def event_entry_payload(
    row: Mapping[str, Any], *, previous_event_hash: str | None = None
) -> dict[str, Any]:
    previous = (
        str(previous_event_hash)
        if previous_event_hash is not None
        else str(row.get("previous_event_hash") or GENESIS_HASH)
    )
    return {
        "event_id": int(row.get("event_id") or 0),
        "revision": int(row.get("revision") or 0),
        "event_type": str(row.get("event_type") or ""),
        "payload": _decoded_json(row.get("payload_json"), {}),
        "created_at": str(row.get("created_at") or ""),
        "previous_event_hash": previous,
    }


def event_entry_hash(
    row: Mapping[str, Any], *, previous_event_hash: str | None = None
) -> str:
    return _canonical_hash(
        event_entry_payload(row, previous_event_hash=previous_event_hash)
    )


def backfill_patch_entry_chain(conn: Any) -> tuple[int, str]:
    """Establish a migration-time chain for entries predating hash columns.

    This function is intentionally called only when the columns are first
    introduced.  Calling it during ordinary opens would silently bless later
    tampering.
    """

    previous = GENESIS_HASH
    count = 0
    rows = conn.execute(
        "SELECT * FROM patches WHERE status = 'applied' "
        "ORDER BY applied_revision ASC, patch_id ASC"
    ).fetchall()
    for raw_row in rows:
        row = dict(raw_row)
        digest = patch_entry_hash(row, previous_entry_hash=previous)
        conn.execute(
            "UPDATE patches SET previous_entry_hash = ?, journal_entry_hash = ? "
            "WHERE patch_id = ?",
            (previous, digest, row["patch_id"]),
        )
        previous = digest
        count += 1
    return count, previous


def backfill_event_chain(conn: Any, *, problem_id: str) -> tuple[int, str, str]:
    """Establish the event chain exactly once during schema migration."""

    previous = GENESIS_HASH
    policy_head = GENESIS_HASH
    count = 0
    for raw_row in conn.execute("SELECT * FROM events ORDER BY event_id ASC").fetchall():
        row = dict(raw_row)
        digest = event_entry_hash(row, previous_event_hash=previous)
        conn.execute(
            "UPDATE events SET previous_event_hash = ?, event_hash = ? WHERE event_id = ?",
            (previous, digest, row["event_id"]),
        )
        if str(row.get("event_type") or "") in POLICY_EVENT_TYPES:
            policy_head = digest
        previous = digest
        count += 1
    conn.execute(
        "UPDATE problem_state SET event_chain_length = ?, event_chain_head = ?, "
        "policy_event_head = ? WHERE problem_id = ?",
        (count, previous, policy_head, problem_id),
    )
    return count, previous, policy_head


# These events can alter later scheduling or stopping semantics.  Ordinary run
# telemetry is in the full event chain but does not invalidate an already
# running model session.
POLICY_EVENT_TYPES = frozenset(
    {
        "completion_policy",
        "parallel_branch_mode",
        "root_intent_resolution",
        "operator_steering",
        # Historical run_control telemetry predates policy-head binding, so it
        # cannot be added here without changing the computed head of every old
        # database.  New run-status transitions emit a companion event of this
        # type, which advances the policy head without rewriting history.
        "run_control_policy",
    }
)
