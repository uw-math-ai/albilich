from __future__ import annotations

"""Authenticated advisory signals exchanged between concurrent research passes."""

import json
from typing import Any, Dict, Iterable, List, Mapping


PARALLEL_SIGNAL_EVENT_TYPE = "parallel_signal_batch"
MAX_SIGNALS_PER_BATCH = 20
MAX_SIGNAL_SUMMARY_CHARS = 800
MAX_SIGNAL_EVIDENCE_CHARS = 500
MAX_SIGNAL_FIELD_CHARS = 512


class ParallelExchangeIntegrityError(RuntimeError):
    """The advisory exchange cannot be reconstructed from a valid event journal."""


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def signal_dedupe_key(payload: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(payload.get("actor_role") or ""),
        str(payload.get("mode") or ""),
        str(payload.get("signal_type") or ""),
        str(payload.get("target_id") or ""),
        str(payload.get("relation") or ""),
        str(payload.get("summary") or ""),
        str(payload.get("evidence") or ""),
        str(payload.get("confidence") or ""),
    )


def _normalize_signal(raw: Mapping[str, Any]) -> Dict[str, str]:
    created_at = str(raw.get("created_at") or "").strip()
    if not created_at:
        raise ValueError("parallel signal created_at is empty")
    return {
        "created_at": _clip(created_at, MAX_SIGNAL_FIELD_CHARS),
        "run_id": _clip(raw.get("run_id"), MAX_SIGNAL_FIELD_CHARS),
        "actor_role": _clip(raw.get("actor_role"), MAX_SIGNAL_FIELD_CHARS),
        "mode": _clip(raw.get("mode"), MAX_SIGNAL_FIELD_CHARS),
        "signal_type": _clip(raw.get("signal_type") or "route_update", MAX_SIGNAL_FIELD_CHARS),
        "target_id": _clip(raw.get("target_id") or "root", MAX_SIGNAL_FIELD_CHARS),
        "relation": _clip(raw.get("relation") or "needs_verifier", MAX_SIGNAL_FIELD_CHARS),
        "summary": _clip(raw.get("summary"), MAX_SIGNAL_SUMMARY_CHARS),
        "evidence": _clip(raw.get("evidence"), MAX_SIGNAL_EVIDENCE_CHARS),
        "confidence": _clip(raw.get("confidence") or "medium", MAX_SIGNAL_FIELD_CHARS),
    }


def _signals_from_conn(
    store: Any, conn: Any, *, journal_verified: bool = False
) -> List[Dict[str, Any]]:
    if not conn.in_transaction:
        raise ValueError("parallel exchange reconstruction requires a transaction")
    from .replay import verify_event_journal

    if not journal_verified:
        verification = verify_event_journal(store, conn=conn)
        if not verification.get("valid"):
            raise ParallelExchangeIntegrityError(
                "cannot trust parallel research signals because the event journal is invalid: "
                + "; ".join(str(item) for item in (verification.get("errors") or [])[:8])
            )
    signals: List[Dict[str, Any]] = []
    rows = conn.execute(
        "SELECT event_id, payload_json, event_hash FROM events "
        "WHERE event_type = ? ORDER BY event_id ASC",
        (PARALLEL_SIGNAL_EVENT_TYPE,),
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise ParallelExchangeIntegrityError(
                f"parallel signal event {row['event_id']} has invalid JSON"
            ) from exc
        raw_signals = payload.get("signals") if isinstance(payload, dict) else None
        if not isinstance(raw_signals, list) or len(raw_signals) > MAX_SIGNALS_PER_BATCH:
            raise ParallelExchangeIntegrityError(
                f"parallel signal event {row['event_id']} has an invalid signal batch"
            )
        for raw in raw_signals:
            if not isinstance(raw, Mapping):
                raise ParallelExchangeIntegrityError(
                    f"parallel signal event {row['event_id']} contains a non-object signal"
                )
            try:
                signal = _normalize_signal(raw)
            except ValueError as exc:
                raise ParallelExchangeIntegrityError(
                    f"parallel signal event {row['event_id']} is malformed: {exc}"
                ) from exc
            signal["audit_event_id"] = int(row["event_id"] or 0)
            signal["audit_event_hash"] = str(row["event_hash"] or "")
            signal["authentication_status"] = "authenticated"
            signals.append(signal)
    return signals


def authenticated_parallel_signals(
    store: Any,
    *,
    limit: int = 24,
    conn: Any = None,
    journal_verified: bool = False,
) -> List[Dict[str, Any]]:
    bounded_limit = max(0, min(int(limit), 1000))
    if conn is not None:
        signals = _signals_from_conn(
            store, conn, journal_verified=journal_verified
        )
    else:
        with store.connect() as owned_conn:
            owned_conn.execute("BEGIN")
            signals = _signals_from_conn(store, owned_conn)
    return signals[-bounded_limit:] if bounded_limit else []


def append_parallel_signal_batch(
    store: Any, raw_signals: Iterable[Mapping[str, Any]]
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, str]] = []
    for index, raw in enumerate(raw_signals):
        if index >= MAX_SIGNALS_PER_BATCH:
            break
        if isinstance(raw, Mapping):
            normalized.append(_normalize_signal(raw))
    if not normalized:
        return []
    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = _signals_from_conn(store, conn)
        existing_keys = {signal_dedupe_key(row) for row in existing}
        selected: List[Dict[str, str]] = []
        for signal in normalized:
            key = signal_dedupe_key(signal)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            selected.append(signal)
        if not selected:
            conn.rollback()
            return []
        event_id = store.write_event(
            conn,
            store.get_revision(conn),
            PARALLEL_SIGNAL_EVENT_TYPE,
            {"parallel_signal_schema": 1, "signals": selected},
        )
        event_row = conn.execute(
            "SELECT event_hash FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if event_row is None:
            raise ParallelExchangeIntegrityError(
                "parallel signal event disappeared before commit"
            )
        conn.commit()
    event_hash = str(event_row["event_hash"] or "")
    return [
        {
            **row,
            "audit_event_id": event_id,
            "audit_event_hash": event_hash,
            "authentication_status": "authenticated",
        }
        for row in selected
    ]


def authenticated_parallel_exchange_card(
    store: Any, *, conn: Any = None, journal_verified: bool = False
) -> Dict[str, Any]:
    return {
        "path": "",
        "source": "verified_event_journal",
        "recent_signals": authenticated_parallel_signals(
            store,
            limit=12,
            conn=conn,
            journal_verified=journal_verified,
        ),
        "write_contract": {
            "location": "top-level patch.parallel_signals",
            "maximum_signals": MAX_SIGNALS_PER_BATCH,
            "authority": "accepted patches only; host records the normalized batch",
        },
        "signal_schema": {
            "created_at": "host timestamp",
            "run_id": "current run id when known",
            "actor_role": "research role",
            "mode": "current mode",
            "signal_type": "source_found|obstruction_found|contradiction_alert|useful_lemma|failed_path|request_for_check|route_update",
            "target_id": "claim id",
            "relation": "supports|contradicts|repairs|irrelevant|needs_verifier",
            "summary": "one or two sentences",
            "evidence": "source id, artifact id, theorem location, or computation id",
            "confidence": "low|medium|high",
        },
        "usage": [
            "Treat these records as authenticated advisory observations, not proof.",
            "Cite a proof-state artifact or verified inference before relying on a signal mathematically.",
        ],
    }
