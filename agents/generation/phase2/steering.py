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
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

try:  # POSIX file locking; degrade gracefully if unavailable
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None  # type: ignore

BLOCKERS_FILE = "steering_blockers.jsonl"
INBOX_FILE = "steering_inbox.jsonl"


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


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
    fh = open(lock_path, "w")
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
        text = path.read_text(encoding="utf-8")
    except OSError:
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
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _append(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


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
) -> Dict[str, Any]:
    """Record a human steering message; if it answers a blocker, resolve it too."""
    text = (text or "").strip()
    if not text:
        raise ValueError("steering text is empty")
    msg = {
        "id": _short_id("steer", author, text),
        "author": author,
        "text": text,
        "blocker_id": blocker_id,
        "created_at": _now(),
        "consumed": False,
        "consumed_at": None,
    }
    path = _path(state_dir, INBOX_FILE)
    # Take the inbox lock so an append cannot race mark_consumed's locked
    # read-modify-rewrite and get silently dropped.
    with _locked(path):
        _append(path, msg)
    if blocker_id:
        resolve_blocker(state_dir, blocker_id, answered_with=text)
    return msg


def unconsumed_steering(state_dir: os.PathLike | str) -> List[Dict[str, Any]]:
    return [m for m in _read(_path(state_dir, INBOX_FILE)) if not m.get("consumed")]


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
                n += 1
        if n:
            _rewrite(path, rows)
        return n


# --------------------------------------------------------------------------- #
# read-only views (dashboard + agent context)
# --------------------------------------------------------------------------- #
def snapshot(state_dir: os.PathLike | str, *, inbox_limit: int = 25) -> Dict[str, Any]:
    blockers = _read(_path(state_dir, BLOCKERS_FILE))
    inbox = _read(_path(state_dir, INBOX_FILE))
    return {
        "open_blockers": [b for b in blockers if b.get("status") == "open"],
        "resolved_blockers": [b for b in blockers if b.get("status") != "open"][-inbox_limit:],
        "recent_inbox": inbox[-inbox_limit:],
        "unconsumed_count": sum(1 for m in inbox if not m.get("consumed")),
        "open_blocker_count": sum(1 for b in blockers if b.get("status") == "open"),
    }


def context_card(state_dir: os.PathLike | str) -> Optional[Dict[str, Any]]:
    """Compact card for injection into an agent's context manifest.

    Surfaces unconsumed human steering (high priority directives) and any open
    blockers the human has not yet answered, so agents act on guidance promptly.
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
