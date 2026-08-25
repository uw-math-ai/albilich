from __future__ import annotations

from typing import Any, Iterable, Mapping


POSITIVE_VERIFICATION_VERDICTS = {
    "correct",
    "correct_no_gaps",
    "informally_verified",
    "pass",
    "verified",
}

REFUTATION_VERIFICATION_VERDICTS = {
    "correct_refutation",
    "refuted",
}

# Backward-compatible name for callers that mean a positive proof certificate.
ZERO_GAP_VERIFICATION_VERDICTS = POSITIVE_VERIFICATION_VERDICTS


def verification_report(metadata: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    report = metadata.get("verification_report", {})
    return report if isinstance(report, Mapping) else {}


def verification_verdict(metadata: Mapping[str, Any] | None) -> str:
    if not isinstance(metadata, Mapping):
        return ""
    report = verification_report(metadata)
    return str(metadata.get("verdict") or report.get("verdict") or "").strip().lower()


def verification_blockers(metadata: Mapping[str, Any] | None) -> list[str]:
    """Return blockers from both supported verifier metadata layouts."""

    if not isinstance(metadata, Mapping):
        return []
    report = verification_report(metadata)
    blockers: list[str] = []
    for container in (metadata, report):
        for key in ("critical_errors", "gaps"):
            value = container.get(key)
            if isinstance(value, (list, tuple, set)):
                blockers.extend(str(item).strip() for item in value if str(item).strip())
            elif value not in (None, "", False, []):
                blockers.append(str(value).strip())
        blocking_gap = container.get("blocking_gap")
        if blocking_gap not in (None, "", False, []):
            blockers.append(str(blocking_gap).strip() if not isinstance(blocking_gap, bool) else "blocking_gap")
    return list(dict.fromkeys(item for item in blockers if item))


def clean_verification_metadata(metadata: Mapping[str, Any] | None, *, outcome: str) -> bool:
    verdicts = (
        POSITIVE_VERIFICATION_VERDICTS
        if outcome == "positive"
        else REFUTATION_VERIFICATION_VERDICTS
        if outcome == "refutation"
        else set()
    )
    return verification_verdict(metadata) in verdicts and not verification_blockers(metadata)


def evidence_targets(metadata: Mapping[str, Any] | None) -> list[dict[str, str]]:
    """Normalize explicit target declarations carried by an evidence artifact."""

    if not isinstance(metadata, Mapping):
        return []
    result: list[dict[str, str]] = []
    raw_targets = metadata.get("evidence_targets", [])
    if isinstance(raw_targets, Mapping):
        raw_targets = [raw_targets]
    if isinstance(raw_targets, Iterable) and not isinstance(raw_targets, (str, bytes)):
        for raw in raw_targets:
            if not isinstance(raw, Mapping):
                continue
            target_id = str(raw.get("target_id") or "").strip()
            if not target_id:
                continue
            result.append(
                {
                    "target_type": str(raw.get("target_type") or "claim").strip() or "claim",
                    "target_id": target_id,
                    "route_id": str(raw.get("route_id") or "").strip(),
                }
            )

    alias_groups = (
        ("claim", ("target_id", "target_claim_id", "claim_id")),
        ("inference", ("target_inference_id", "inference_id")),
        ("route", ("target_route_id",)),
    )
    route_id = str(metadata.get("route_id") or "").strip()
    for target_type, aliases in alias_groups:
        for alias in aliases:
            value = str(metadata.get(alias) or "").strip()
            if value:
                result.append({"target_type": target_type, "target_id": value, "route_id": route_id})

    target_ids = metadata.get("target_ids", [])
    if isinstance(target_ids, str):
        target_ids = [target_ids]
    if isinstance(target_ids, Iterable):
        for value in target_ids:
            target_id = str(value or "").strip()
            if target_id:
                result.append({"target_type": "claim", "target_id": target_id, "route_id": route_id})

    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in result:
        key = (item["target_type"], item["target_id"], item["route_id"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def evidence_matches_target(
    metadata: Mapping[str, Any] | None,
    *,
    target_type: str,
    target_id: str,
    route_id: str = "",
) -> bool:
    targets = evidence_targets(metadata)
    for target in targets:
        if target["target_type"] != target_type or target["target_id"] != target_id:
            continue
        declared_route = target["route_id"]
        if route_id and declared_route != route_id:
            continue
        return True
    return False
