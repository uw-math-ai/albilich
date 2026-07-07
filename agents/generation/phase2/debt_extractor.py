from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .models import fingerprint_text

ERROR_KEYS = ("critical_errors", "errors", "fatal_errors")
GAP_KEYS = ("gaps", "missing_steps", "missing_lemmas")
WARNING_KEYS = ("warnings", "objections", "concerns")
HINT_KEYS = ("repair_hints", "hints", "suggestions")


def extract_debts_from_report(
    *,
    owner_type: str,
    owner_id: str,
    report: Mapping[str, Any],
    source_artifact_ids: Sequence[str] | None = None,
) -> List[Dict[str, Any]]:
    """Convert verifier objections into stable proof-debt operations."""
    source_ids = list(source_artifact_ids or [])
    operations: List[Dict[str, Any]] = []

    for text in _items(report, ERROR_KEYS):
        operations.append(_debt_op(owner_type, owner_id, text, "error", "blocking", source_ids))
    for text in _items(report, GAP_KEYS):
        operations.append(_debt_op(owner_type, owner_id, text, "gap", "blocking", source_ids))
    for text in _items(report, WARNING_KEYS):
        operations.append(_debt_op(owner_type, owner_id, text, "objection", "major", source_ids))

    hint_text = "\n".join(_items(report, HINT_KEYS))
    if hint_text and operations:
        for op in operations:
            op["suggested_next_target"] = owner_id
            op.setdefault("metadata", {})["repair_hints"] = hint_text

    return _dedupe(operations)


def proof_debt_patch_operations(
    *,
    owner_type: str,
    owner_id: str,
    verification_artifact_id: str,
    report: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    return extract_debts_from_report(
        owner_type=owner_type,
        owner_id=owner_id,
        report=report,
        source_artifact_ids=[verification_artifact_id],
    )


def _debt_op(owner_type: str, owner_id: str, text: str, debt_type: str, severity: str, source_ids: List[str]) -> Dict[str, Any]:
    obligation = _clean(text)
    fingerprint = fingerprint_text(f"{owner_type}:{owner_id}:{debt_type}:{obligation}", length=24)
    return {
        "op": "add_debt",
        "owner_type": owner_type,
        "owner_id": owner_id,
        "obligation": obligation,
        "fingerprint": fingerprint,
        "debt_type": debt_type,
        "severity": severity,
        "status": "active",
        "source_artifact_ids": source_ids,
        "suggested_next_target": owner_id,
    }


def _items(report: Mapping[str, Any], keys: Iterable[str]) -> List[str]:
    found: List[str] = []
    for key in keys:
        value = report.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                found.append(value.strip())
        elif isinstance(value, Mapping):
            found.extend(_items(value, value.keys()))
        elif isinstance(value, Iterable):
            for item in value:
                if isinstance(item, str) and item.strip():
                    found.append(item.strip())
                elif isinstance(item, Mapping):
                    summary = item.get("message") or item.get("text") or item.get("obligation") or str(dict(item))
                    if str(summary).strip():
                        found.append(str(summary).strip())
    return found


def _clean(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def _dedupe(ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique: List[Dict[str, Any]] = []
    for op in ops:
        key = op["fingerprint"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(op)
    return unique
