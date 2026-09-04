"""Human-in-the-loop steering channel for an Albilich run.

Two file-based queues live in the run's ``state_dir`` so the live run (reader /
consumer) and the monitor server (writer) can exchange messages **without halting
the run**:

  ``steering_blockers.jsonl`` — system -> human: open blockers / questions the
      advisor or the circling guard raised, awaiting a human decision.
  ``steering_inbox.jsonl``    — human -> system: steering messages the
      mathematician typed in the dashboard; consumed by the run and injected into
      the next agent's context.

Both are append-mostly JSONL; status changes (resolve a blocker, consume an inbox
message) rewrite the file under an ``flock``. Concurrency is low (one run process,
one monitor process, occasional human input) so a coarse sidecar lock is fine.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import secrets
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .bounded_io import read_bounded_text

try:  # POSIX file locking; degrade gracefully if unavailable
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None  # type: ignore

BLOCKERS_FILE = "steering_blockers.jsonl"
INBOX_FILE = "steering_inbox.jsonl"
MAX_STEERING_TEXT_BYTES = 48 * 1024
MAX_STEERING_IDENTIFIER_BYTES = 512
MAX_BLOCKER_EVENT_BYTES = 64 * 1024
MAX_LEGACY_SIDECAR_BYTES = 4 * 1024 * 1024

_AUTHENTICATED_STEERING_EVENT_TYPES = frozenset(
    {
        "operator_steering",
        "steering_delivered",
        "steering_consumed",
        "steering_alignment_requested",
        "steering_alignment_processing",
        "steering_alignment_completed",
        "steering_blocker_raised",
    }
)


class SteeringIntegrityError(RuntimeError):
    """The authenticated steering view cannot be reconstructed safely."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _path(state_dir: os.PathLike | str, name: str) -> Path:
    return Path(state_dir) / name


def _short_id(prefix: str, *seeds: Any) -> str:
    h = hashlib.sha1(("|".join(str(s) for s in seeds) + _now()).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{h}"


@contextmanager
def _locked(path: Path):
    """Coarse advisory lock on a sidecar file around a read-modify-write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise ValueError(f"could not open steering sidecar lock: {exc}") from exc
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("steering sidecar lock must be a regular file")
    fh = os.fdopen(descriptor, "r+")
    try:
        if fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if fcntl is not None:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def _read(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        text = read_bounded_text(
            path,
            max_bytes=MAX_LEGACY_SIDECAR_BYTES,
            label="legacy steering sidecar",
        )
    except (OSError, ValueError):
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _rewrite(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, ensure_ascii=False) + "\n" for row in rows
    ).encode("utf-8")
    if len(payload) > MAX_LEGACY_SIDECAR_BYTES:
        raise ValueError(
            f"legacy steering sidecar exceeds the {MAX_LEGACY_SIDECAR_BYTES}-byte limit"
        )
    descriptor, raw_tmp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(descriptor, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _append(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ValueError(f"could not open legacy steering sidecar: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("legacy steering sidecar must be a regular file")
        if before.st_size + len(payload) > MAX_LEGACY_SIDECAR_BYTES:
            raise ValueError(
                f"legacy steering sidecar exceeds the {MAX_LEGACY_SIDECAR_BYTES}-byte limit"
            )
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


# --------------------------------------------------------------------------- #
# system -> human : blockers / questions
# --------------------------------------------------------------------------- #
def raise_blocker(
    state_dir: os.PathLike | str,
    *,
    summary: str,
    kind: str = "blocker",
    target_id: str = "root",
    options: Optional[Sequence[str]] = None,
    detail: str = "",
    fingerprint: Optional[str] = None,
    revision: Optional[int] = None,
) -> Dict[str, Any]:
    """Raise (or refresh) an open blocker for the human. Deduped by ``fingerprint``.

    If an open blocker with the same fingerprint already exists, its ``last_seen``
    and ``seen_count`` are bumped instead of creating a duplicate.
    """
    path = _path(state_dir, BLOCKERS_FILE)
    fp = fingerprint or hashlib.sha1(f"{kind}|{target_id}|{summary}".encode("utf-8")).hexdigest()[:16]
    with _locked(path):
        rows = _read(path)
        for row in rows:
            if row.get("fingerprint") == fp and row.get("status") == "open":
                row["last_seen"] = _now()
                row["seen_count"] = int(row.get("seen_count", 1)) + 1
                if revision is not None:
                    row["last_revision"] = revision
                _rewrite(path, rows)
                return row
        blocker = {
            "id": _short_id("blk", kind, target_id, summary),
            "kind": kind,
            "status": "open",
            "target_id": target_id,
            "summary": summary,
            "detail": detail,
            "options": list(options or []),
            "fingerprint": fp,
            "created_at": _now(),
            "last_seen": _now(),
            "seen_count": 1,
            "revision": revision,
            "last_revision": revision,
            "answered_with": None,
            "answered_at": None,
        }
        rows.append(blocker)
        _rewrite(path, rows)
        return blocker


def open_blockers(state_dir: os.PathLike | str) -> List[Dict[str, Any]]:
    return [b for b in _read(_path(state_dir, BLOCKERS_FILE)) if b.get("status") == "open"]


def resolve_blocker(
    state_dir: os.PathLike | str,
    blocker_id: str,
    *,
    answered_with: Optional[str] = None,
    status: str = "answered",
) -> Optional[Dict[str, Any]]:
    path = _path(state_dir, BLOCKERS_FILE)
    with _locked(path):
        rows = _read(path)
        hit = None
        for row in rows:
            if row.get("id") == blocker_id and row.get("status") == "open":
                row["status"] = status
                row["answered_with"] = answered_with
                row["answered_at"] = _now()
                hit = row
                break
        if hit is not None:
            _rewrite(path, rows)
        return hit


# --------------------------------------------------------------------------- #
# human -> system : steering inbox
# --------------------------------------------------------------------------- #
def submit_steering(
    state_dir: os.PathLike | str,
    text: str,
    *,
    blocker_id: Optional[str] = None,
    author: str = "human",
    requires_approach_alignment: Optional[bool] = None,
    audit_event_id: Optional[int] = None,
    audit_event_hash: str = "",
) -> Dict[str, Any]:
    """Record a human steering message; if it answers a blocker, resolve it too."""
    text = (text or "").strip()
    if not text:
        raise ValueError("steering text is empty")
    if len(text.encode("utf-8")) > MAX_STEERING_TEXT_BYTES:
        raise ValueError(
            f"steering text exceeds the {MAX_STEERING_TEXT_BYTES}-byte limit"
        )
    # A general research steer may change the mathematical landscape seen by
    # every speculative approach.  Once the directive has been processed, the
    # scheduler therefore owes the user one dedicated portfolio-alignment pass.
    # Answers to narrow blockers default to no global refresh; callers can opt
    # them in explicitly when the answer really changes the root strategy.
    alignment_required = bool(blocker_id is None) if requires_approach_alignment is None else bool(
        requires_approach_alignment
    )
    msg = {
        "id": _short_id("steer", author, text),
        "author": author,
        "text": text,
        "blocker_id": blocker_id,
        "created_at": _now(),
        "delivery_status": "queued",
        "delivered_at": None,
        "delivery_attempts": 0,
        "delivered_revision": None,
        "consumed": False,
        "consumed_at": None,
        "approach_alignment_required": alignment_required,
        "approach_alignment_status": "awaiting_processing" if alignment_required else "not_required",
        "approach_alignment_started_at": None,
        "approach_alignment_completed_at": None,
        "approach_alignment_artifact_id": None,
        "approach_alignment_revision": None,
        "audit_event_id": int(audit_event_id or 0),
        "audit_event_hash": str(audit_event_hash or ""),
    }
    path = _path(state_dir, INBOX_FILE)
    # Take the inbox lock so an append cannot race mark_consumed's locked
    # read-modify-rewrite and get silently dropped.
    with _locked(path):
        _append(path, msg)
    if blocker_id:
        resolve_blocker(state_dir, blocker_id, answered_with=text)
    return msg


def submit_operator_steering(
    store: Any,
    text: str,
    *,
    blocker_id: Optional[str] = None,
    author: str = "human",
    requires_approach_alignment: Optional[bool] = None,
) -> Dict[str, Any]:
    """Atomically append an operator directive to the authenticated event journal.

    The event journal is the source of truth.  JSONL files are retained only for
    compatibility with old standalone tooling and are deliberately not written
    here: splitting authorization and delivery across SQLite and a sidecar made
    it possible for a crash to record a directive without ever delivering it.
    """

    normalized = (text or "").strip()
    if not normalized:
        raise ValueError("steering text is empty")
    if len(normalized.encode("utf-8")) > MAX_STEERING_TEXT_BYTES:
        raise ValueError(
            f"steering text exceeds the {MAX_STEERING_TEXT_BYTES}-byte limit"
        )
    alignment_required = (
        bool(blocker_id is None)
        if requires_approach_alignment is None
        else bool(requires_approach_alignment)
    )
    normalized_author = str(author or "human").strip() or "human"
    normalized_blocker_id = str(blocker_id or "").strip()
    _validate_identifier(normalized_author, field="steering author")
    if normalized_blocker_id:
        _validate_identifier(normalized_blocker_id, field="blocker id")
    message_id = f"steer-{secrets.token_hex(10)}"
    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if normalized_blocker_id:
            authenticated = _authenticated_state_from_conn(store, conn)
            blocker = authenticated["blockers"].get(normalized_blocker_id)
            if blocker is None:
                raise ValueError(f"unknown authenticated blocker: {normalized_blocker_id}")
            if str(blocker.get("status") or "") != "open":
                raise ValueError(f"blocker is already resolved: {normalized_blocker_id}")
        revision = store.get_revision(conn)
        event_id = store.write_event(
            conn,
            revision,
            "operator_steering",
            {
                "steering_schema": 1,
                "message_id": message_id,
                "author": normalized_author,
                "text": normalized,
                "blocker_id": normalized_blocker_id,
                "requires_approach_alignment": alignment_required,
            },
        )
        row = conn.execute(
            "SELECT created_at, event_hash FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            raise SteeringIntegrityError("operator steering event disappeared before commit")
        conn.commit()
    return _new_authenticated_message(
        message_id=message_id,
        author=normalized_author,
        text=normalized,
        blocker_id=normalized_blocker_id,
        created_at=str(row["created_at"] or ""),
        alignment_required=alignment_required,
        event_id=event_id,
        event_hash=str(row["event_hash"] or ""),
    )


def _validate_identifier(value: str, *, field: str) -> None:
    if not value:
        raise ValueError(f"{field} is empty")
    if len(value.encode("utf-8")) > MAX_STEERING_IDENTIFIER_BYTES:
        raise ValueError(
            f"{field} exceeds the {MAX_STEERING_IDENTIFIER_BYTES}-byte limit"
        )


def _new_authenticated_message(
    *,
    message_id: str,
    author: str,
    text: str,
    blocker_id: str,
    created_at: str,
    alignment_required: bool,
    event_id: int,
    event_hash: str,
) -> Dict[str, Any]:
    return {
        "id": message_id,
        "author": author,
        "text": text,
        "blocker_id": blocker_id or None,
        "created_at": created_at,
        "delivery_status": "queued",
        "delivered_at": None,
        "delivery_attempts": 0,
        "delivered_revision": None,
        "consumed": False,
        "consumed_at": None,
        "approach_alignment_required": bool(alignment_required),
        "approach_alignment_status": (
            "awaiting_processing" if alignment_required else "not_required"
        ),
        "approach_alignment_started_at": None,
        "approach_alignment_completed_at": None,
        "approach_alignment_artifact_id": None,
        "approach_alignment_revision": None,
        "audit_event_id": int(event_id),
        "audit_event_hash": event_hash,
        "authentication_status": "authenticated",
    }


def _event_payload(row: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        payload = json.loads(str(row.get("payload_json") or "{}"))
    except (TypeError, json.JSONDecodeError) as exc:
        raise SteeringIntegrityError(
            f"steering event {row.get('event_id')} has invalid JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise SteeringIntegrityError(
            f"steering event {row.get('event_id')} payload is not an object"
        )
    return payload


def _transition_message_ids(
    row: Mapping[str, Any], payload: Mapping[str, Any]
) -> List[str]:
    raw_ids = payload.get("message_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise SteeringIntegrityError(
            f"steering event {row.get('event_id')} has no message_ids list"
        )
    ids: List[str] = []
    for raw in raw_ids:
        message_id = str(raw or "").strip()
        try:
            _validate_identifier(message_id, field="message id")
        except ValueError as exc:
            raise SteeringIntegrityError(
                f"steering event {row.get('event_id')} has an invalid message id: {exc}"
            ) from exc
        if message_id not in ids:
            ids.append(message_id)
    return ids


def _authenticated_state_from_conn(store: Any, conn: Any) -> Dict[str, Any]:
    """Reconstruct steering from an append-only, tail-verified event snapshot."""

    if not conn.in_transaction:
        raise ValueError("authenticated steering reconstruction requires a transaction")
    verification = store.current_event_seal(conn)
    if not verification.get("valid"):
        errors = verification.get("errors") or ["unknown event-journal error"]
        raise SteeringIntegrityError(
            "cannot trust operator steering because the event journal is invalid: "
            + "; ".join(str(item) for item in errors[:8])
        )
    event_types = tuple(sorted(_AUTHENTICATED_STEERING_EVENT_TYPES))
    event_rows = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM events WHERE event_type IN ("
            + ",".join("?" for _ in event_types)
            + ") ORDER BY event_id ASC",
            event_types,
        ).fetchall()
    ]
    messages: Dict[str, Dict[str, Any]] = {}
    blockers: Dict[str, Dict[str, Any]] = {}

    for row in event_rows:
        event_type = str(row.get("event_type") or "")
        payload = _event_payload(row)
        event_id = int(row.get("event_id") or 0)
        event_hash = str(row.get("event_hash") or "")
        created_at = str(row.get("created_at") or "")

        if event_type == "steering_blocker_raised":
            blocker_id = str(payload.get("blocker_id") or "").strip()
            fingerprint = str(payload.get("fingerprint") or "").strip()
            try:
                _validate_identifier(blocker_id, field="blocker id")
                _validate_identifier(fingerprint, field="blocker fingerprint")
            except ValueError as exc:
                raise SteeringIntegrityError(
                    f"steering blocker event {event_id} is malformed: {exc}"
                ) from exc
            if blocker_id in blockers:
                raise SteeringIntegrityError(
                    f"duplicate authenticated blocker id {blocker_id!r}"
                )
            options = payload.get("options") or []
            if not isinstance(options, list):
                raise SteeringIntegrityError(
                    f"steering blocker event {event_id} options are not a list"
                )
            blockers[blocker_id] = {
                "id": blocker_id,
                "kind": str(payload.get("kind") or "blocker"),
                "status": "open",
                "target_id": str(payload.get("target_id") or "root"),
                "summary": str(payload.get("summary") or ""),
                "detail": str(payload.get("detail") or ""),
                "options": [str(item) for item in options],
                "fingerprint": fingerprint,
                "created_at": created_at,
                "last_seen": created_at,
                "seen_count": 1,
                "revision": payload.get("revision"),
                "last_revision": payload.get("revision"),
                "answered_with": None,
                "answered_at": None,
                "audit_event_id": event_id,
                "audit_event_hash": event_hash,
                "authentication_status": "authenticated",
            }
            continue

        if event_type == "operator_steering":
            text = str(payload.get("text") or "").strip()
            author = str(payload.get("author") or "human").strip() or "human"
            blocker_id = str(payload.get("blocker_id") or "").strip()
            # The deterministic fallback preserves directives written during the
            # brief pre-schema implementation, whose event did not carry an ID.
            message_id = str(payload.get("message_id") or f"steer-event-{event_id}").strip()
            try:
                _validate_identifier(message_id, field="message id")
                _validate_identifier(author, field="steering author")
                if blocker_id:
                    _validate_identifier(blocker_id, field="blocker id")
            except ValueError as exc:
                raise SteeringIntegrityError(
                    f"operator steering event {event_id} is malformed: {exc}"
                ) from exc
            if not text or len(text.encode("utf-8")) > MAX_STEERING_TEXT_BYTES:
                raise SteeringIntegrityError(
                    f"operator steering event {event_id} has invalid text length"
                )
            if message_id in messages:
                raise SteeringIntegrityError(
                    f"duplicate authenticated steering id {message_id!r}"
                )
            message = _new_authenticated_message(
                message_id=message_id,
                author=author,
                text=text,
                blocker_id=blocker_id,
                created_at=created_at,
                alignment_required=bool(payload.get("requires_approach_alignment")),
                event_id=event_id,
                event_hash=event_hash,
            )
            messages[message_id] = message
            blocker = blockers.get(blocker_id)
            if blocker is not None and blocker.get("status") == "open":
                blocker["status"] = "answered"
                blocker["answered_with"] = text
                blocker["answered_at"] = created_at
                blocker["answer_message_id"] = message_id
            continue

        ids = _transition_message_ids(row, payload)
        unknown = [message_id for message_id in ids if message_id not in messages]
        if unknown:
            raise SteeringIntegrityError(
                f"steering event {event_id} references unknown message(s): "
                + ", ".join(unknown[:8])
            )
        for message_id in ids:
            message = messages[message_id]
            if event_type == "steering_delivered":
                if not message.get("consumed"):
                    message["delivery_status"] = "processing"
                    message["delivered_at"] = created_at
                    message["delivery_attempts"] = int(message.get("delivery_attempts") or 0) + 1
                    message["delivered_revision"] = payload.get("revision")
            elif event_type == "steering_consumed":
                if not message.get("consumed"):
                    message["consumed"] = True
                    message["consumed_at"] = created_at
                    message["delivery_status"] = "consumed"
                    if message.get("approach_alignment_required"):
                        message["approach_alignment_status"] = "pending"
            elif event_type == "steering_alignment_requested":
                message["approach_alignment_required"] = True
                message["approach_alignment_status"] = (
                    "pending" if message.get("consumed") else "awaiting_processing"
                )
            elif event_type == "steering_alignment_processing":
                if message.get("consumed") and message.get("approach_alignment_required"):
                    message["approach_alignment_status"] = "processing"
                    message["approach_alignment_started_at"] = created_at
            elif event_type == "steering_alignment_completed":
                artifact_id = str(payload.get("artifact_id") or "").strip()
                if not artifact_id:
                    raise SteeringIntegrityError(
                        f"steering alignment event {event_id} has no artifact id"
                    )
                message["approach_alignment_required"] = True
                message["approach_alignment_status"] = "completed"
                message["approach_alignment_completed_at"] = created_at
                message["approach_alignment_artifact_id"] = artifact_id
                message["approach_alignment_revision"] = payload.get("revision")

    return {
        "messages": messages,
        "blockers": blockers,
        "event_verification": verification,
    }


def _authenticated_state(store: Any, *, conn: Any = None) -> Dict[str, Any]:
    if conn is not None:
        return _authenticated_state_from_conn(store, conn)
    with store.connect() as owned_conn:
        owned_conn.execute("BEGIN")
        return _authenticated_state_from_conn(store, owned_conn)


def authenticated_unconsumed_steering(
    store: Any, *, conn: Any = None
) -> List[Dict[str, Any]]:
    state = _authenticated_state(store, conn=conn)
    return [dict(row) for row in state["messages"].values() if not row.get("consumed")]


def _normalized_message_ids(ids: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    for raw in ids:
        message_id = str(raw or "").strip()
        if not message_id:
            continue
        _validate_identifier(message_id, field="message id")
        if message_id not in normalized:
            normalized.append(message_id)
    return normalized


def _record_authenticated_transition(
    store: Any,
    event_type: str,
    ids: Iterable[str],
    *,
    eligible: Any,
    extra_payload: Optional[Mapping[str, Any]] = None,
) -> int:
    normalized = _normalized_message_ids(ids)
    if not normalized:
        return 0
    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        state = _authenticated_state_from_conn(store, conn)
        selected = [
            message_id
            for message_id in normalized
            if message_id in state["messages"] and eligible(state["messages"][message_id])
        ]
        if not selected:
            conn.rollback()
            return 0
        payload = {"steering_schema": 1, "message_ids": selected}
        payload.update(dict(extra_payload or {}))
        store.write_event(
            conn,
            store.get_revision(conn),
            event_type,
            payload,
        )
        conn.commit()
    return len(selected)


def mark_authenticated_delivered(
    store: Any, ids: Iterable[str], *, revision: Optional[int] = None
) -> int:
    delivered_revision = store.get_revision() if revision is None else int(revision)
    return _record_authenticated_transition(
        store,
        "steering_delivered",
        ids,
        eligible=lambda row: not row.get("consumed"),
        extra_payload={"revision": delivered_revision},
    )


def mark_authenticated_consumed(store: Any, ids: Iterable[str]) -> int:
    return _record_authenticated_transition(
        store,
        "steering_consumed",
        ids,
        eligible=lambda row: not row.get("consumed"),
    )


def request_authenticated_approach_alignment(store: Any, ids: Iterable[str]) -> int:
    return _record_authenticated_transition(
        store,
        "steering_alignment_requested",
        ids,
        eligible=lambda _row: True,
    )


def mark_authenticated_approach_alignment_processing(
    store: Any, ids: Iterable[str]
) -> int:
    return _record_authenticated_transition(
        store,
        "steering_alignment_processing",
        ids,
        eligible=lambda row: (
            row.get("consumed")
            and row.get("approach_alignment_required")
            and str(row.get("approach_alignment_status") or "pending")
            in {"pending", "processing"}
        ),
    )


def mark_authenticated_approach_alignment_completed(
    store: Any,
    ids: Iterable[str],
    *,
    artifact_id: str,
    revision: Optional[int] = None,
) -> int:
    normalized_artifact_id = str(artifact_id or "").strip()
    _validate_identifier(normalized_artifact_id, field="alignment artifact id")
    completed_revision = store.get_revision() if revision is None else int(revision)
    return _record_authenticated_transition(
        store,
        "steering_alignment_completed",
        ids,
        eligible=lambda row: bool(row.get("approach_alignment_required")),
        extra_payload={
            "artifact_id": normalized_artifact_id,
            "revision": completed_revision,
        },
    )


def raise_authenticated_blocker(
    store: Any,
    *,
    summary: str,
    kind: str = "blocker",
    target_id: str = "root",
    options: Optional[Sequence[str]] = None,
    detail: str = "",
    fingerprint: Optional[str] = None,
    revision: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a deduplicated blocker whose immutable content is journal-bound."""

    normalized_summary = str(summary or "").strip()
    if not normalized_summary:
        raise ValueError("blocker summary is empty")
    normalized_kind = str(kind or "blocker").strip() or "blocker"
    normalized_target = str(target_id or "root").strip() or "root"
    normalized_detail = str(detail or "")
    normalized_options = [str(item) for item in (options or [])]
    if len(normalized_options) > 32:
        raise ValueError("blocker has more than 32 options")
    normalized_fingerprint = str(
        fingerprint
        or hashlib.sha256(
            f"{normalized_kind}|{normalized_target}|{normalized_summary}".encode("utf-8")
        ).hexdigest()[:24]
    ).strip()
    for field, value in (
        ("blocker kind", normalized_kind),
        ("blocker target id", normalized_target),
        ("blocker fingerprint", normalized_fingerprint),
    ):
        _validate_identifier(value, field=field)
    payload_base = {
        "steering_schema": 1,
        "kind": normalized_kind,
        "target_id": normalized_target,
        "summary": normalized_summary,
        "detail": normalized_detail,
        "options": normalized_options,
        "fingerprint": normalized_fingerprint,
        "revision": revision,
    }
    if len(json.dumps(payload_base, ensure_ascii=False).encode("utf-8")) > MAX_BLOCKER_EVENT_BYTES:
        raise ValueError(
            f"blocker content exceeds the {MAX_BLOCKER_EVENT_BYTES}-byte limit"
        )
    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        state = _authenticated_state_from_conn(store, conn)
        existing = next(
            (
                row
                for row in state["blockers"].values()
                if row.get("fingerprint") == normalized_fingerprint
                and row.get("status") == "open"
            ),
            None,
        )
        if existing is not None:
            conn.rollback()
            return dict(existing)
        blocker_id = f"blk-{secrets.token_hex(10)}"
        payload = dict(payload_base)
        payload["blocker_id"] = blocker_id
        event_id = store.write_event(
            conn,
            store.get_revision(conn) if revision is None else int(revision),
            "steering_blocker_raised",
            payload,
        )
        event_row = conn.execute(
            "SELECT created_at, event_hash FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if event_row is None:
            raise SteeringIntegrityError("steering blocker event disappeared before commit")
        conn.commit()
    return {
        "id": blocker_id,
        "kind": normalized_kind,
        "status": "open",
        "target_id": normalized_target,
        "summary": normalized_summary,
        "detail": normalized_detail,
        "options": normalized_options,
        "fingerprint": normalized_fingerprint,
        "created_at": str(event_row["created_at"] or ""),
        "last_seen": str(event_row["created_at"] or ""),
        "seen_count": 1,
        "revision": revision,
        "last_revision": revision,
        "answered_with": None,
        "answered_at": None,
        "audit_event_id": event_id,
        "audit_event_hash": str(event_row["event_hash"] or ""),
        "authentication_status": "authenticated",
    }


def unconsumed_steering(state_dir: os.PathLike | str) -> List[Dict[str, Any]]:
    return [m for m in _read(_path(state_dir, INBOX_FILE)) if not m.get("consumed")]


def mark_delivered(
    state_dir: os.PathLike | str,
    ids: Iterable[str],
    *,
    revision: Optional[int] = None,
) -> int:
    """Mark pending steering as inserted into an executing agent context.

    Delivery is intentionally distinct from consumption: a failed child leaves
    the message unconsumed so a later step can retry it, while the dashboard can
    still report that the current child is processing the directive.
    """
    ids = set(ids)
    if not ids:
        return 0
    path = _path(state_dir, INBOX_FILE)
    with _locked(path):
        rows = _read(path)
        n = 0
        delivered_at = _now()
        for row in rows:
            if row.get("id") in ids and not row.get("consumed"):
                row["delivery_status"] = "processing"
                row["delivered_at"] = delivered_at
                row["delivery_attempts"] = int(row.get("delivery_attempts") or 0) + 1
                row["delivered_revision"] = revision
                n += 1
        if n:
            _rewrite(path, rows)
        return n


def mark_consumed(state_dir: os.PathLike | str, ids: Iterable[str]) -> int:
    ids = set(ids)
    if not ids:
        return 0
    path = _path(state_dir, INBOX_FILE)
    with _locked(path):
        rows = _read(path)
        n = 0
        for row in rows:
            if row.get("id") in ids and not row.get("consumed"):
                row["consumed"] = True
                row["consumed_at"] = _now()
                row["delivery_status"] = "consumed"
                if row.get("approach_alignment_required"):
                    row["approach_alignment_status"] = "pending"
                n += 1
        if n:
            _rewrite(path, rows)
        return n


def request_approach_alignment(state_dir: os.PathLike | str, ids: Iterable[str]) -> int:
    """Queue a portfolio-alignment pass for existing steering messages.

    This is primarily a recovery hook for messages created before the automatic
    alignment fields existed.  It preserves the original message and delivery
    history rather than injecting a duplicate steer.
    """
    ids = set(ids)
    if not ids:
        return 0
    path = _path(state_dir, INBOX_FILE)
    with _locked(path):
        rows = _read(path)
        n = 0
        for row in rows:
            if row.get("id") not in ids:
                continue
            row["approach_alignment_required"] = True
            row["approach_alignment_status"] = "pending" if row.get("consumed") else "awaiting_processing"
            row.setdefault("approach_alignment_started_at", None)
            row.setdefault("approach_alignment_completed_at", None)
            row.setdefault("approach_alignment_artifact_id", None)
            row.setdefault("approach_alignment_revision", None)
            n += 1
        if n:
            _rewrite(path, rows)
        return n


def pending_approach_alignment(state_dir: os.PathLike | str) -> List[Dict[str, Any]]:
    """Return processed steers whose global approach effects are not reconciled."""
    return [
        row
        for row in _read(_path(state_dir, INBOX_FILE))
        if row.get("consumed")
        and row.get("approach_alignment_required")
        and str(row.get("approach_alignment_status") or "pending") in {"pending", "processing"}
    ]


def approach_alignment_card(state_dir: os.PathLike | str) -> Dict[str, Any]:
    pending = pending_approach_alignment(state_dir)
    return {
        "required": bool(pending),
        "pending_count": len(pending),
        "source_steering_ids": [str(row.get("id") or "") for row in pending if str(row.get("id") or "")],
        "directives": [
            {
                "id": str(row.get("id") or ""),
                "text": str(row.get("text") or ""),
                "created_at": str(row.get("created_at") or ""),
            }
            for row in pending
        ],
    }


def mark_approach_alignment_processing(state_dir: os.PathLike | str, ids: Iterable[str]) -> int:
    ids = set(ids)
    if not ids:
        return 0
    path = _path(state_dir, INBOX_FILE)
    with _locked(path):
        rows = _read(path)
        n = 0
        started_at = _now()
        for row in rows:
            if (
                row.get("id") in ids
                and row.get("consumed")
                and row.get("approach_alignment_required")
                and str(row.get("approach_alignment_status") or "pending") in {"pending", "processing"}
            ):
                row["approach_alignment_status"] = "processing"
                row["approach_alignment_started_at"] = started_at
                n += 1
        if n:
            _rewrite(path, rows)
        return n


def mark_approach_alignment_completed(
    state_dir: os.PathLike | str,
    ids: Iterable[str],
    *,
    artifact_id: str,
    revision: Optional[int] = None,
) -> int:
    ids = set(ids)
    if not ids or not str(artifact_id or "").strip():
        return 0
    path = _path(state_dir, INBOX_FILE)
    with _locked(path):
        rows = _read(path)
        n = 0
        completed_at = _now()
        for row in rows:
            if row.get("id") in ids and row.get("approach_alignment_required"):
                row["approach_alignment_status"] = "completed"
                row["approach_alignment_completed_at"] = completed_at
                row["approach_alignment_artifact_id"] = str(artifact_id)
                row["approach_alignment_revision"] = revision
                n += 1
        if n:
            _rewrite(path, rows)
        return n


# --------------------------------------------------------------------------- #
# read-only views (dashboard + agent context)
# --------------------------------------------------------------------------- #
def snapshot(state_dir: os.PathLike | str, *, inbox_limit: int = 25) -> Dict[str, Any]:
    """Return the legacy JSONL view.

    This path-only API has no event journal with which to authenticate its
    contents. Production scheduling, prompt construction, and monitoring use
    :func:`authenticated_snapshot` instead.
    """
    blockers = _read(_path(state_dir, BLOCKERS_FILE))
    inbox = []
    for raw in _read(_path(state_dir, INBOX_FILE)):
        row = dict(raw)
        if row.get("consumed"):
            row["delivery_status"] = "consumed"
        elif row.get("delivery_status") == "processing" or row.get("delivered_at"):
            row["delivery_status"] = "processing"
        else:
            row["delivery_status"] = "queued"
        inbox.append(row)
    queued_count = sum(1 for m in inbox if m.get("delivery_status") == "queued")
    processing_count = sum(1 for m in inbox if m.get("delivery_status") == "processing")
    alignment_pending_count = sum(
        1
        for m in inbox
        if m.get("approach_alignment_required")
        and str(m.get("approach_alignment_status") or "") in {"pending", "processing"}
    )
    alignment_processing_count = sum(
        1 for m in inbox if str(m.get("approach_alignment_status") or "") == "processing"
    )
    return {
        "open_blockers": [b for b in blockers if b.get("status") == "open"],
        "resolved_blockers": [b for b in blockers if b.get("status") != "open"][-inbox_limit:],
        "recent_inbox": inbox[-inbox_limit:],
        "unconsumed_count": sum(1 for m in inbox if not m.get("consumed")),
        "queued_count": queued_count,
        "processing_count": processing_count,
        "approach_alignment_pending_count": alignment_pending_count,
        "approach_alignment_processing_count": alignment_processing_count,
        "open_blocker_count": sum(1 for b in blockers if b.get("status") == "open"),
    }


def authenticated_snapshot(
    store: Any, *, inbox_limit: int = 25, conn: Any = None
) -> Dict[str, Any]:
    state = _authenticated_state(store, conn=conn)
    blockers = list(state["blockers"].values())
    inbox = list(state["messages"].values())
    queued_count = sum(1 for row in inbox if row.get("delivery_status") == "queued")
    processing_count = sum(
        1 for row in inbox if row.get("delivery_status") == "processing"
    )
    alignment_pending_count = sum(
        1
        for row in inbox
        if row.get("approach_alignment_required")
        and str(row.get("approach_alignment_status") or "") in {"pending", "processing"}
    )
    alignment_processing_count = sum(
        1
        for row in inbox
        if str(row.get("approach_alignment_status") or "") == "processing"
    )
    return {
        "source": "verified_event_journal",
        "event_journal_valid": True,
        "open_blockers": [row for row in blockers if row.get("status") == "open"],
        "resolved_blockers": [
            row for row in blockers if row.get("status") != "open"
        ][-inbox_limit:],
        "recent_inbox": inbox[-inbox_limit:],
        "unconsumed_count": sum(1 for row in inbox if not row.get("consumed")),
        "queued_count": queued_count,
        "processing_count": processing_count,
        "approach_alignment_pending_count": alignment_pending_count,
        "approach_alignment_processing_count": alignment_processing_count,
        "open_blocker_count": sum(
            1 for row in blockers if row.get("status") == "open"
        ),
    }


def authenticated_approach_alignment_card(
    store: Any, *, conn: Any = None
) -> Dict[str, Any]:
    state = _authenticated_state(store, conn=conn)
    pending = [
        row
        for row in state["messages"].values()
        if row.get("consumed")
        and row.get("approach_alignment_required")
        and str(row.get("approach_alignment_status") or "pending")
        in {"pending", "processing"}
    ]
    return {
        "required": bool(pending),
        "pending_count": len(pending),
        "source_steering_ids": [str(row.get("id") or "") for row in pending],
        "directives": [
            {
                "id": str(row.get("id") or ""),
                "text": str(row.get("text") or ""),
                "created_at": str(row.get("created_at") or ""),
            }
            for row in pending
        ],
        "source": "verified_event_journal",
    }


def authenticated_context_card(
    store: Any, *, conn: Any = None
) -> Optional[Dict[str, Any]]:
    state = _authenticated_state(store, conn=conn)
    pending = [row for row in state["messages"].values() if not row.get("consumed")]
    blockers = [
        row for row in state["blockers"].values() if row.get("status") == "open"
    ]
    if not pending and not blockers:
        return None
    return {
        "instruction": (
            "AUTHENTICATED HUMAN STEERING from the supervising mathematician. "
            "Treat unconsumed directives as high-priority guidance that overrides "
            "the default plan. If an open blocker is unanswered, keep making "
            "progress on other fronts; do not halt."
        ),
        "source": "verified_event_journal",
        "human_directives": [
            {
                "id": row.get("id"),
                "text": row.get("text"),
                "at": row.get("created_at"),
                "answers_blocker": row.get("blocker_id"),
                "audit_event_id": row.get("audit_event_id"),
                "audit_event_hash": row.get("audit_event_hash"),
            }
            for row in pending
        ],
        "open_blockers": [
            {
                "id": row.get("id"),
                "summary": row.get("summary"),
                "target_id": row.get("target_id"),
                "options": row.get("options"),
                "audit_event_id": row.get("audit_event_id"),
                "audit_event_hash": row.get("audit_event_hash"),
            }
            for row in blockers
        ],
    }


def context_card(state_dir: os.PathLike | str) -> Optional[Dict[str, Any]]:
    """Compact unauthenticated compatibility card for standalone sidecar users.

    Production context construction must call :func:`authenticated_context_card`.
    """
    pending = unconsumed_steering(state_dir)
    blockers = open_blockers(state_dir)
    if not pending and not blockers:
        return None
    return {
        "instruction": (
            "HUMAN STEERING from the supervising mathematician. Treat unconsumed "
            "directives as high-priority guidance that overrides the default plan. "
            "If an open blocker is still unanswered, keep making progress on other "
            "fronts; do not halt."
        ),
        "human_directives": [
            {"id": m.get("id"), "text": m.get("text"), "at": m.get("created_at"), "answers_blocker": m.get("blocker_id")}
            for m in pending
        ],
        "open_blockers": [
            {"id": b.get("id"), "summary": b.get("summary"), "target_id": b.get("target_id"), "options": b.get("options")}
            for b in blockers
        ],
    }
