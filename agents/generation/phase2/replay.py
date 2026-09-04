from __future__ import annotations

import copy
import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from .audit_chain import (
    GENESIS_HASH,
    POLICY_EVENT_TYPES,
    event_entry_hash,
    patch_entry_hash,
)
from .models import json_loads
from .patches import (
    _STATE_JOURNAL_TABLE_KEYS,
    _legacy_v14_run_provenance_hash,
    _legacy_v14_state_journal_projection,
    _run_provenance_hash,
    _state_journal_projection,
    _state_projection_hash,
)
from .store import (
    ProofStateStore,
    _event_history_guard_errors,
    _event_source_sequence_errors,
    _patch_history_guard_errors,
    _policy_projection_payload_errors,
    _projection_baseline_guard_errors,
)


def _journal_int(
    value: Any,
    *,
    label: str,
    errors: list[str],
    default: int = 0,
    minimum: int | None = None,
) -> int:
    """Parse a persisted integer while keeping verification read-only and total."""

    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{label} is not an integer")
        return default
    if minimum is not None and value < minimum:
        errors.append(f"{label} is below its minimum value {minimum}")
        return default
    return value


def _safe_projection_hash(
    projection: Mapping[str, Any], *, label: str, errors: list[str]
) -> str:
    try:
        return _state_projection_hash(projection)
    except (TypeError, ValueError, OverflowError) as exc:
        errors.append(f"{label} is malformed: {exc}")
        return ""


def _state_delta_shape_errors(
    delta: list[Any], *, patch_id: str
) -> list[str]:
    """Validate an authenticated legacy delta without claiming row replay."""

    errors: list[str] = []
    key_columns_by_table = dict(_STATE_JOURNAL_TABLE_KEYS)
    for index, change in enumerate(delta):
        label = f"patch {patch_id} state delta {index}"
        if not isinstance(change, Mapping):
            errors.append(f"{label} is not an object")
            continue
        table = str(change.get("table") or "")
        key_columns = key_columns_by_table.get(table)
        if not key_columns:
            errors.append(f"{label} names unsupported table {table!r}")
            continue
        key = change.get("key")
        if not isinstance(key, Mapping) or any(
            column not in key or key.get(column) in (None, "")
            for column in key_columns
        ):
            errors.append(f"{label} has an invalid row key")
        before = change.get("before")
        after = change.get("after")
        kind = str(change.get("op") or "")
        if kind == "insert_row":
            valid_images = before is None and isinstance(after, Mapping)
        elif kind == "update_row":
            valid_images = isinstance(before, Mapping) and isinstance(after, Mapping)
        elif kind == "delete_row":
            valid_images = isinstance(before, Mapping) and after is None
        else:
            errors.append(f"{label} has unknown operation {kind!r}")
            continue
        if not valid_images:
            errors.append(f"{label} has invalid before/after row images")
    return errors


def _patch_journal_snapshot(
    conn: sqlite3.Connection,
    problem_id: str,
    *,
    projection_builder: Callable[
        [sqlite3.Connection], Dict[str, list[Dict[str, Any]]]
    ] = _state_journal_projection,
    run_provenance_builder: Callable[
        [sqlite3.Connection], str
    ] = _run_provenance_hash,
) -> tuple[
    Dict[str, list[Dict[str, Any]]],
    list[Dict[str, Any]],
    Dict[str, Any],
    Dict[str, Any],
    str,
    str,
]:
    """Read every replay input from one caller-owned SQLite snapshot."""

    projection = projection_builder(conn)
    all_patches = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM patches WHERE status = 'applied' "
            "ORDER BY applied_revision, patch_id"
        ).fetchall()
    ]
    projection_baseline_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' "
        "AND name = 'projection_audit_baselines'"
    ).fetchone()
    baseline_row = (
        conn.execute(
            "SELECT * FROM projection_audit_baselines WHERE problem_id = ?",
            (problem_id,),
        ).fetchone()
        if projection_baseline_exists is not None
        else None
    )
    if baseline_row is None:
        baseline_row = conn.execute(
            "SELECT * FROM audit_baselines WHERE problem_id = ?",
            (problem_id,),
        ).fetchone()
    baseline = dict(baseline_row) if baseline_row else {}
    seal_row = conn.execute(
        "SELECT proof_state_hash, run_provenance_hash, patch_journal_head "
        "FROM problem_state WHERE problem_id = ?",
        (problem_id,),
    ).fetchone()
    seal_state = dict(seal_row) if seal_row else {}
    try:
        run_provenance_hash = run_provenance_builder(conn)
        run_provenance_error = ""
    except (sqlite3.Error, TypeError, ValueError, OverflowError) as exc:
        run_provenance_hash = ""
        run_provenance_error = str(exc)
    return (
        projection,
        all_patches,
        baseline,
        seal_state,
        run_provenance_hash,
        run_provenance_error,
    )


def _verify_patch_journal(
    store: ProofStateStore,
    *,
    conn: sqlite3.Connection | None = None,
    check_patch_guards: bool = True,
    check_projection_baseline_guards: bool = True,
    projection_builder: Callable[
        [sqlite3.Connection], Dict[str, list[Dict[str, Any]]]
    ] = _state_journal_projection,
    run_provenance_builder: Callable[
        [sqlite3.Connection], str
    ] = _run_provenance_hash,
    replay_state_rows: bool = True,
) -> Dict[str, Any]:
    """Implement current replay and the migration-only v14 chain check.

    This is read-only.  Starting from the current database, every recorded row
    change is inverted to the authenticated baseline and then applied forward
    again in revision order.  Both endpoints of every transition are checked.
    It detects an unjournaled mutation, a modified or non-reversible delta, a
    missing revision, and a broken hash link without trusting the child-authored
    operation list. The override arguments are migration-only compatibility
    hooks. In particular, v14 mixed asynchronously changing scheduler rows into
    its proof digest, so that migration authenticates every patch-chain entry
    but cannot honestly claim row-semantic replay across those control-plane
    transitions. Current stores always use complete reverse/forward row replay.
    This verifier does not claim that current kernel code re-executed historical
    external effects.
    """

    errors: list[str] = []
    if conn is None:
        with store.connect() as owned_conn:
            owned_conn.execute("BEGIN")
            (
                projection,
                all_patches,
                baseline,
                seal_state,
                current_run_provenance_hash,
                run_provenance_error,
            ) = _patch_journal_snapshot(
                owned_conn,
                store.problem_id,
                projection_builder=projection_builder,
                run_provenance_builder=run_provenance_builder,
            )
            dispatch_errors = _full_dispatch_audit_errors(owned_conn)
            baseline_guard_errors = (
                _projection_baseline_guard_errors(owned_conn)
                if check_projection_baseline_guards
                else []
            )
            patch_guard_errors = (
                _patch_history_guard_errors(owned_conn)
                if check_patch_guards
                else []
            )
    else:
        if not conn.in_transaction:
            raise ValueError("verify_patch_journal shared connection requires a transaction")
        (
            projection,
            all_patches,
            baseline,
            seal_state,
            current_run_provenance_hash,
            run_provenance_error,
        ) = _patch_journal_snapshot(
            conn,
            store.problem_id,
            projection_builder=projection_builder,
            run_provenance_builder=run_provenance_builder,
        )
        dispatch_errors = _full_dispatch_audit_errors(conn)
        baseline_guard_errors = (
            _projection_baseline_guard_errors(conn)
            if check_projection_baseline_guards
            else []
        )
        patch_guard_errors = (
            _patch_history_guard_errors(conn) if check_patch_guards else []
        )
    errors.extend(
        f"scheduler dispatch: {error}" for error in dispatch_errors
    )
    errors.extend(baseline_guard_errors)
    errors.extend(patch_guard_errors)

    problem_rows = projection.get("problem_state", [])
    current_revision = (
        _journal_int(
            problem_rows[0].get("current_revision"),
            label="current proof revision",
            errors=errors,
            minimum=0,
        )
        if problem_rows
        else 0
    )
    start_revision = _journal_int(
        baseline.get("baseline_revision", 0),
        label="audit baseline revision",
        errors=errors,
        minimum=0,
    )
    start_state_hash = str(baseline.get("baseline_state_hash") or "")
    start_entry_hash = str(
        baseline.get("patch_journal_head") or GENESIS_HASH
    )
    patch_revisions = {
        id(row): _journal_int(
            row.get("applied_revision"),
            label=f"patch {row.get('patch_id') or '<unknown>'} applied_revision",
            errors=errors,
            default=-1,
            minimum=0,
        )
        for row in all_patches
    }
    legacy_patches = [
        row for row in all_patches if patch_revisions[id(row)] <= start_revision
    ]
    patches = [
        row for row in all_patches if patch_revisions[id(row)] > start_revision
    ]
    if baseline:
        if start_revision > current_revision:
            errors.append("audit baseline revision exceeds current proof revision")
        recorded_legacy_count = _journal_int(
            baseline.get("legacy_patch_count", 0),
            label="audit baseline legacy patch count",
            errors=errors,
            minimum=0,
        )
        if len(legacy_patches) != recorded_legacy_count:
            errors.append("legacy patch count does not match the audit baseline")
        observed_legacy_head = (
            str(legacy_patches[-1].get("journal_entry_hash") or GENESIS_HASH)
            if legacy_patches
            else GENESIS_HASH
        )
        if observed_legacy_head != start_entry_hash:
            errors.append("legacy patch head does not match the audit baseline")
        errors.extend(_legacy_baseline_file_errors(store, baseline))
    revisions = [patch_revisions[id(row)] for row in patches]
    # A native v3 store starts at revision zero. A migrated pre-v3 store starts
    # at an explicit post-migration baseline and never pretends that the older
    # semantic transitions acquired row-exact deltas retrospectively.
    expected = list(range(start_revision + 1, current_revision + 1))
    if revisions != expected:
        errors.append(
            "applied patch revisions do not cover the proof-state history: "
            f"found {revisions}, expected {expected}"
        )

    previous_entry_hash = start_entry_hash
    for patch in patches:
        patch_id = str(patch.get("patch_id") or "")
        recorded_previous = str(patch.get("previous_entry_hash") or "")
        recorded_hash = str(patch.get("journal_entry_hash") or "")
        if recorded_previous != previous_entry_hash:
            errors.append(
                f"patch {patch_id} journal predecessor mismatch: "
                f"{recorded_previous or '<missing>'} != {previous_entry_hash}"
            )
        try:
            expected_hash = patch_entry_hash(
                patch, previous_entry_hash=previous_entry_hash
            )
        except (TypeError, ValueError, OverflowError) as exc:
            expected_hash = ""
            errors.append(f"patch {patch_id} journal entry is malformed: {exc}")
        if recorded_hash != expected_hash:
            errors.append(
                f"patch {patch_id} journal-entry hash mismatch: "
                f"{recorded_hash or '<missing>'} != {expected_hash}"
            )
        previous_entry_hash = recorded_hash or expected_hash

        if not replay_state_rows:
            delta = json_loads(patch.get("state_delta_json"), None)
            if not isinstance(delta, list):
                errors.append(f"patch {patch_id} has malformed state_delta_json")
            else:
                errors.extend(_state_delta_shape_errors(delta, patch_id=patch_id))
            for field in ("state_hash_before", "state_hash_after"):
                value = str(patch.get(field) or "")
                if len(value) != 64 or any(
                    character not in "0123456789abcdef" for character in value
                ):
                    errors.append(f"patch {patch_id} has invalid {field}")

    current_projection = copy.deepcopy(projection)
    current_hash = _safe_projection_hash(
        projection, label="current proof-state projection", errors=errors
    )
    if str(seal_state.get("proof_state_hash") or "") != current_hash:
        errors.append(
            "current proof state does not match its recorded current-state seal"
        )
    if run_provenance_error:
        errors.append(
            "current run-selection provenance is malformed: "
            + run_provenance_error
        )
    if (
        str(seal_state.get("run_provenance_hash") or "")
        != current_run_provenance_hash
    ):
        errors.append(
            "current run-selection provenance does not match its recorded seal"
        )
    if replay_state_rows:
        if patches:
            if current_hash != str(patches[-1].get("state_hash_after") or ""):
                errors.append(
                    "current proof state does not match the latest patch "
                    "state_hash_after"
                )
        elif baseline and current_hash != start_state_hash:
            errors.append(
                "current proof state does not match the migration audit baseline"
            )
    elif not patches and baseline and current_hash != start_state_hash:
        errors.append("current proof state does not match the migration audit baseline")
    errors.extend(_artifact_file_errors(store, projection.get("artifacts", [])))

    verified = 0
    for patch in reversed(patches) if replay_state_rows else ():
        patch_id = str(patch.get("patch_id") or "")
        after_hash = str(patch.get("state_hash_after") or "")
        before_hash = str(patch.get("state_hash_before") or "")
        if not before_hash or not after_hash:
            errors.append(f"patch {patch_id} has no replay hashes")
            break
        observed_after = _safe_projection_hash(
            projection,
            label=f"patch {patch_id} reverse after-projection",
            errors=errors,
        )
        if observed_after != after_hash:
            errors.append(
                f"patch {patch_id} after-hash mismatch: {observed_after} != {after_hash}"
            )
            break
        delta = json_loads(patch.get("state_delta_json"), None)
        if not isinstance(delta, list):
            errors.append(f"patch {patch_id} has malformed state_delta_json")
            break
        step_errors = _invert_state_delta(projection, delta, patch_id=patch_id)
        errors.extend(step_errors)
        if step_errors:
            break
        observed_before = _safe_projection_hash(
            projection,
            label=f"patch {patch_id} reverse before-projection",
            errors=errors,
        )
        if observed_before != before_hash:
            errors.append(
                f"patch {patch_id} before-hash mismatch: {observed_before} != {before_hash}"
            )
            break
        verified += 1

    initial_hash = (
        _safe_projection_hash(
            projection,
            label="replayed initial proof-state projection",
            errors=errors,
        )
        if replay_state_rows
        else start_state_hash
    )
    if replay_state_rows and baseline and initial_hash != start_state_hash:
        errors.append(
            "replayed v3 suffix does not terminate at the migration audit baseline"
        )

    forward_verified = 0
    forward_projection = copy.deepcopy(projection)
    if replay_state_rows and verified == len(patches):
        for patch in patches:
            patch_id = str(patch.get("patch_id") or "")
            before_hash = str(patch.get("state_hash_before") or "")
            after_hash = str(patch.get("state_hash_after") or "")
            observed_before = _safe_projection_hash(
                forward_projection,
                label=f"patch {patch_id} forward before-projection",
                errors=errors,
            )
            if observed_before != before_hash:
                errors.append(
                    f"patch {patch_id} forward before-hash mismatch: "
                    f"{observed_before} != {before_hash}"
                )
                break
            delta = json_loads(patch.get("state_delta_json"), None)
            if not isinstance(delta, list):
                errors.append(f"patch {patch_id} has malformed state_delta_json")
                break
            step_errors = _apply_state_delta(
                forward_projection, delta, patch_id=patch_id
            )
            errors.extend(step_errors)
            if step_errors:
                break
            observed_after = _safe_projection_hash(
                forward_projection,
                label=f"patch {patch_id} forward after-projection",
                errors=errors,
            )
            if observed_after != after_hash:
                errors.append(
                    f"patch {patch_id} forward after-hash mismatch: "
                    f"{observed_after} != {after_hash}"
                )
                break
            forward_verified += 1
        if forward_projection != current_projection:
            errors.append("forward row replay does not reproduce the current proof state")

    if str(seal_state.get("patch_journal_head") or GENESIS_HASH) != previous_entry_hash:
        errors.append("current patch-journal head does not match full replay")

    return {
        "valid": not errors,
        "problem_id": store.problem_id,
        "patch_count": len(patches),
        "total_patch_count": len(all_patches),
        "legacy_patch_count": len(legacy_patches),
        "journal_start_revision": start_revision,
        "journal_start_state_hash": start_state_hash or initial_hash,
        "journal_start_entry_hash": start_entry_hash,
        "prior_history_status": str(
            baseline.get("prior_history_status")
            or "replay_verified_from_genesis"
        ),
        "migration_backup_sha256": str(
            baseline.get("migration_backup_sha256") or ""
        ),
        "verified_patch_count": verified,
        "checked_chain_entry_count": len(patches),
        "forward_verified_patch_count": forward_verified,
        "verification_mode": (
            "row_semantic_replay" if replay_state_rows else "authenticated_chain"
        ),
        "current_state_hash": current_hash,
        "current_run_provenance_hash": current_run_provenance_hash,
        "journal_entry_head": previous_entry_hash,
        "initial_state_hash": initial_hash,
        "errors": errors,
    }


def verify_patch_journal(
    store: ProofStateStore,
    *,
    conn: sqlite3.Connection | None = None,
    check_patch_guards: bool = True,
) -> Dict[str, Any]:
    """Verify the current accepted patch chain by reverse/forward row replay."""

    return _verify_patch_journal(
        store,
        conn=conn,
        check_patch_guards=check_patch_guards,
    )


def verify_legacy_v14_patch_history(
    store: ProofStateStore,
    *,
    conn: sqlite3.Connection,
) -> Dict[str, Any]:
    """Authenticate v14 patch history before separating control telemetry.

    V14 proof hashes included scheduler rows that could change between patches,
    so reconstructing every historical row endpoint would require information
    that v14 did not record. This verifies all information that format did
    authenticate, including every patch-chain entry and both current-state
    seals, before migration records an explicit projection baseline and backup.
    """

    return _verify_patch_journal(
        store,
        conn=conn,
        check_patch_guards=False,
        check_projection_baseline_guards=False,
        projection_builder=_legacy_v14_state_journal_projection,
        run_provenance_builder=_legacy_v14_run_provenance_hash,
        replay_state_rows=False,
    )


def _full_dispatch_audit_errors(conn: sqlite3.Connection) -> list[str]:
    """Run expensive semantic dispatch checks only in explicit full replay."""

    from .invariants import _scheduler_dispatch_errors

    try:
        return _scheduler_dispatch_errors(conn, pending_dispatch_ids=set())
    except (sqlite3.Error, TypeError, ValueError, OverflowError) as exc:
        return [f"dispatch audit is malformed: {exc}"]


def _legacy_baseline_file_errors(
    store: ProofStateStore, baseline: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []
    raw_path = str(baseline.get("migration_backup_path") or "")
    expected = str(baseline.get("migration_backup_sha256") or "").lower()
    if len(expected) != 64:
        errors.append("migration audit baseline has an invalid backup SHA-256")
        return errors
    path = Path(raw_path)
    backup_root = (store.state_dir / "migration_backups").resolve()
    if path.is_symlink():
        return ["migration baseline backup is not a regular non-symlink file"]
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(backup_root)
    except (OSError, ValueError):
        return ["migration baseline backup is missing or outside migration_backups"]
    if not resolved.is_file():
        return ["migration baseline backup is not a regular non-symlink file"]
    digest = hashlib.sha256()
    try:
        with resolved.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        return [f"migration baseline backup could not be read: {exc}"]
    if digest.hexdigest() != expected:
        errors.append("migration baseline backup SHA-256 does not match")
    return errors


def _event_journal_snapshot(
    conn: sqlite3.Connection, problem_id: str
) -> tuple[sqlite3.Row | None, list[Dict[str, Any]]]:
    state_row = conn.execute(
        "SELECT current_revision, completion_policy, parallel_branches, "
        "research_parallel_mode, run_status, event_chain_length, "
        "event_chain_head, policy_event_head FROM problem_state "
        "WHERE problem_id = ?",
        (problem_id,),
    ).fetchone()
    events = [
        dict(row)
        for row in conn.execute("SELECT * FROM events ORDER BY event_id ASC").fetchall()
    ]
    return state_row, events


def verify_event_journal(
    store: ProofStateStore, *, conn: sqlite3.Connection | None = None
) -> Dict[str, Any]:
    """Verify the append-only operator/configuration and telemetry event chain."""

    errors: list[str] = []
    if conn is None:
        with store.connect() as owned_conn:
            owned_conn.execute("BEGIN")
            state_row, events = _event_journal_snapshot(
                owned_conn, store.problem_id
            )
            event_guard_errors = _event_history_guard_errors(owned_conn)
            event_source_errors = _event_source_sequence_errors(owned_conn)
    else:
        if not conn.in_transaction:
            raise ValueError("verify_event_journal shared connection requires a transaction")
        state_row, events = _event_journal_snapshot(conn, store.problem_id)
        event_guard_errors = _event_history_guard_errors(conn)
        event_source_errors = _event_source_sequence_errors(conn)
    errors.extend(event_guard_errors)
    errors.extend(event_source_errors)
    if state_row is None:
        return {
            "valid": False,
            "problem_id": store.problem_id,
            "event_count": 0,
            "event_chain_head": GENESIS_HASH,
            "policy_event_head": GENESIS_HASH,
            "errors": ["problem_state row is missing"],
        }
    state = dict(state_row)
    previous = GENESIS_HASH
    policy_head = GENESIS_HASH
    latest_by_type: dict[str, Mapping[str, Any]] = {}
    previous_event_type = ""
    previous_event_id = 0
    previous_event_payload: Mapping[str, Any] = {}
    current_revision = _journal_int(
        state.get("current_revision"),
        label="current proof revision",
        errors=errors,
        minimum=0,
    )
    for event in events:
        event_id = _journal_int(
            event.get("event_id"),
            label="event identifier",
            errors=errors,
            default=-1,
            minimum=1,
        )
        event_type = str(event.get("event_type") or "")
        recorded_previous = str(event.get("previous_event_hash") or "")
        recorded_hash = str(event.get("event_hash") or "")
        if recorded_previous != previous:
            errors.append(
                f"event {event_id} predecessor mismatch: "
                f"{recorded_previous or '<missing>'} != {previous}"
            )
        try:
            expected_hash = event_entry_hash(
                event, previous_event_hash=previous
            )
        except (TypeError, ValueError, OverflowError) as exc:
            expected_hash = ""
            errors.append(f"event {event_id} entry is malformed: {exc}")
        if recorded_hash != expected_hash:
            errors.append(
                f"event {event_id} entry hash mismatch: "
                f"{recorded_hash or '<missing>'} != {expected_hash}"
            )
        revision = _journal_int(
            event.get("revision"),
            label=f"event {event_id} proof revision",
            errors=errors,
            default=-1,
            minimum=0,
        )
        if revision < 0 or revision > current_revision:
            errors.append(
                f"event {event_id} has impossible proof revision {revision} "
                f"for current revision {current_revision}"
            )
        payload = json_loads(event.get("payload_json"), None)
        if not isinstance(payload, dict):
            errors.append(f"event {event_id} payload_json is not an object")
            payload = {}
        errors.extend(
            f"event {event_id} payload: {error}"
            for error in _policy_projection_payload_errors(event_type, payload)
        )
        latest_by_type[event_type] = payload
        if event_type == "run_control_policy":
            referenced_event_id = payload.get("run_control_event_id")
            if (
                previous_event_type != "run_control"
                or not isinstance(referenced_event_id, int)
                or isinstance(referenced_event_id, bool)
                or referenced_event_id != previous_event_id
            ):
                errors.append(
                    f"event {event_id} is not paired with its immediately preceding run_control event"
                )
            policy_transition = {
                key: value
                for key, value in payload.items()
                if key != "run_control_event_id"
            }
            if dict(previous_event_payload) != policy_transition:
                errors.append(
                    f"event {event_id} run-control policy payload differs from its telemetry event"
                )
        if event_type in POLICY_EVENT_TYPES:
            policy_head = recorded_hash or expected_hash
        previous = recorded_hash or expected_hash
        previous_event_type = event_type
        previous_event_id = event_id
        previous_event_payload = payload

    recorded_count = _journal_int(
        state.get("event_chain_length"),
        label="recorded event-chain length",
        errors=errors,
        minimum=0,
    )
    if recorded_count != len(events):
        errors.append(
            f"event chain length mismatch: problem_state records {recorded_count}, "
            f"database contains {len(events)}"
        )
    recorded_head = str(state.get("event_chain_head") or GENESIS_HASH)
    if recorded_head != previous:
        errors.append(
            f"event chain head mismatch: {recorded_head} != {previous}"
        )
    recorded_policy_head = str(state.get("policy_event_head") or GENESIS_HASH)
    if recorded_policy_head != policy_head:
        errors.append(
            f"policy event head mismatch: {recorded_policy_head} != {policy_head}"
        )

    completion = latest_by_type.get("completion_policy")
    if completion is not None and str(completion.get("to") or "") != str(
        state.get("completion_policy") or ""
    ):
        errors.append("completion_policy state does not match its latest chained event")
    parallel = latest_by_type.get("parallel_branch_mode")
    if parallel is not None:
        event_workers = parallel.get("to")
        state_workers = _journal_int(
            state.get("parallel_branches"),
            label="parallel_branches state",
            errors=errors,
            minimum=0,
        )
        if (
            isinstance(event_workers, int)
            and not isinstance(event_workers, bool)
            and event_workers != state_workers
        ):
            errors.append("parallel_branches state does not match its latest chained event")
        if str(parallel.get("mode") or "") != str(
            state.get("research_parallel_mode") or ""
        ):
            errors.append(
                "research_parallel_mode state does not match its latest chained event"
            )
    run_control = latest_by_type.get("run_control")
    if run_control is not None and str(run_control.get("to") or "") != str(
        state.get("run_status") or ""
    ):
        errors.append("run_status state does not match its latest chained event")
    run_control_policy = latest_by_type.get("run_control_policy")
    if run_control_policy is not None and str(run_control_policy.get("to") or "") != str(
        state.get("run_status") or ""
    ):
        errors.append(
            "run_status state does not match its latest policy-bound run-control event"
        )

    return {
        "valid": not errors,
        "problem_id": store.problem_id,
        "event_count": len(events),
        "event_chain_head": previous,
        "policy_event_head": policy_head,
        "errors": errors,
    }


def _artifact_file_errors(
    store: ProofStateStore, artifacts: list[Mapping[str, Any]]
) -> list[str]:
    """Check that every file-backed artifact still has its recorded bytes."""

    errors: list[str] = []
    artifact_root = (store.state_dir / "artifacts").resolve()
    for artifact in artifacts:
        artifact_id = str(artifact.get("artifact_id") or "")
        raw_path = str(artifact.get("path") or "").strip()
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.is_symlink():
            errors.append(f"artifact {artifact_id} path is now a symbolic link")
            continue
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(artifact_root)
        except (OSError, ValueError):
            errors.append(
                f"artifact {artifact_id} file is missing or outside the artifact store: {raw_path}"
            )
            continue
        if not resolved.is_file():
            errors.append(f"artifact {artifact_id} path is not a regular file: {raw_path}")
            continue
        digest = hashlib.sha256()
        try:
            with resolved.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            errors.append(f"artifact {artifact_id} could not be read: {exc}")
            continue
        expected = str(artifact.get("sha256") or "").lower()
        actual = digest.hexdigest()
        if actual != expected:
            errors.append(
                f"artifact {artifact_id} file hash mismatch: {actual} != {expected}"
            )
    return errors


def _invert_state_delta(
    projection: Dict[str, list[Dict[str, Any]]],
    delta: list[Any],
    *,
    patch_id: str,
) -> list[str]:
    errors: list[str] = []
    key_columns_by_table = dict(_STATE_JOURNAL_TABLE_KEYS)
    for change in reversed(delta):
        if not isinstance(change, Mapping):
            errors.append(f"patch {patch_id} contains a non-object state delta")
            continue
        table = str(change.get("table") or "")
        key_columns = key_columns_by_table.get(table)
        if not key_columns:
            errors.append(f"patch {patch_id} state delta names unsupported table {table!r}")
            continue
        key = change.get("key") if isinstance(change.get("key"), Mapping) else {}
        row_key = tuple(str(key.get(column) or "") for column in key_columns)
        rows = projection.setdefault(table, [])

        def key_for(row: Mapping[str, Any]) -> tuple[str, ...]:
            return tuple(str(row.get(column) or "") for column in key_columns)

        index = next((i for i, row in enumerate(rows) if key_for(row) == row_key), None)
        kind = str(change.get("op") or "")
        before = dict(change["before"]) if isinstance(change.get("before"), Mapping) else None
        after = dict(change["after"]) if isinstance(change.get("after"), Mapping) else None
        if kind == "insert_row":
            if index is None or rows[index] != after:
                errors.append(f"patch {patch_id} inserted row {table}:{row_key} does not match current state")
                continue
            rows.pop(index)
        elif kind == "update_row":
            if index is None or rows[index] != after or before is None:
                errors.append(f"patch {patch_id} updated row {table}:{row_key} does not match current state")
                continue
            rows[index] = before
        elif kind == "delete_row":
            if index is not None or before is None:
                errors.append(f"patch {patch_id} deleted row {table}:{row_key} is inconsistent")
                continue
            rows.append(before)
        else:
            errors.append(f"patch {patch_id} has unknown row delta operation {kind!r}")
            continue
        rows.sort(key=key_for)
    if not projection.get("scheduler_dispatches"):
        # Empty dispatch storage was absent from every pre-v11 projection;
        # retain that canonical representation at the reverse boundary.
        projection.pop("scheduler_dispatches", None)
    return errors


def _apply_state_delta(
    projection: Dict[str, list[Dict[str, Any]]],
    delta: list[Any],
    *,
    patch_id: str,
) -> list[str]:
    """Apply one authenticated row delta to an in-memory state projection."""

    errors: list[str] = []
    key_columns_by_table = dict(_STATE_JOURNAL_TABLE_KEYS)
    for change in delta:
        if not isinstance(change, Mapping):
            errors.append(f"patch {patch_id} contains a non-object state delta")
            continue
        table = str(change.get("table") or "")
        key_columns = key_columns_by_table.get(table)
        if not key_columns:
            errors.append(
                f"patch {patch_id} state delta names unsupported table {table!r}"
            )
            continue
        key = change.get("key") if isinstance(change.get("key"), Mapping) else {}
        row_key = tuple(str(key.get(column) or "") for column in key_columns)
        rows = projection.setdefault(table, [])

        def key_for(row: Mapping[str, Any]) -> tuple[str, ...]:
            return tuple(str(row.get(column) or "") for column in key_columns)

        index = next(
            (i for i, row in enumerate(rows) if key_for(row) == row_key), None
        )
        kind = str(change.get("op") or "")
        before = (
            dict(change["before"])
            if isinstance(change.get("before"), Mapping)
            else None
        )
        after = (
            dict(change["after"])
            if isinstance(change.get("after"), Mapping)
            else None
        )
        if kind == "insert_row":
            if index is not None or after is None:
                errors.append(
                    f"patch {patch_id} inserted row {table}:{row_key} already exists or has no after image"
                )
                continue
            rows.append(after)
        elif kind == "update_row":
            if index is None or rows[index] != before or after is None:
                errors.append(
                    f"patch {patch_id} updated row {table}:{row_key} does not match its before image"
                )
                continue
            rows[index] = after
        elif kind == "delete_row":
            if index is None or rows[index] != before:
                errors.append(
                    f"patch {patch_id} deleted row {table}:{row_key} does not match its before image"
                )
                continue
            rows.pop(index)
        else:
            errors.append(
                f"patch {patch_id} has unknown row delta operation {kind!r}"
            )
            continue
        rows.sort(key=key_for)
    return errors
