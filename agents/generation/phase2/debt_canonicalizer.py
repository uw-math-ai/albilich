from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence

from .models import normalize_text

CENTRAL_OBSTRUCTION_MIN_ALIAS_COUNT = 2

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "must",
    "of",
    "or",
    "over",
    "prove",
    "show",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
}

_ANCHOR_TERMS = {
    "chained",
    "bridge",
    "class",
    "compatibility",
    "construction",
    "crown",
    "rank",
    "extension",
    "bridge",
    "hd",
    "hinv",
    "interior",
    "lemma",
    "local",
    "combinatorial",
    "maximal",
    "seq",
    "nonsplit",
    "non-split",
    "toy",
    "pure",
    "rank",
    "stars",
    "subgroup",
    "union",
    "wreath",
}


def central_debt_clusters(
    debts: Sequence[Mapping[str, Any]],
    *,
    min_alias_count: int = CENTRAL_OBSTRUCTION_MIN_ALIAS_COUNT,
) -> list[Dict[str, Any]]:
    """Cluster active blocking debts that describe the same mathematical obstruction.

    The interface intentionally returns computed cards rather than mutating proof state.
    This lets the scheduler and context builder promote a central obstruction without a
    database migration or a new proof-state object type.
    """
    candidates = [_debt_card(row) for row in debts if _is_active_blocking_debt(row)]
    if len(candidates) < min_alias_count:
        return []

    clusters: list[list[Dict[str, Any]]] = []
    for debt in candidates:
        placed = False
        for cluster in clusters:
            if any(_same_central_obstruction(debt, existing) for existing in cluster):
                cluster.append(debt)
                placed = True
                break
        if not placed:
            clusters.append([debt])

    cards = [
        _cluster_card(cluster)
        for cluster in clusters
        if len(cluster) >= min_alias_count
    ]
    cards.sort(
        key=lambda row: (
            -int(row["alias_count"]),
            -int(row["total_repeated_count"]),
            row["target_id"],
            row["primary_debt_id"],
        )
    )
    return cards


def central_obstruction_for_debt(
    debts: Sequence[Mapping[str, Any]],
    debt: Mapping[str, Any],
    *,
    min_alias_count: int = CENTRAL_OBSTRUCTION_MIN_ALIAS_COUNT,
) -> Dict[str, Any]:
    debt_id = str(debt.get("debt_id") or "")
    for cluster in central_debt_clusters(debts, min_alias_count=min_alias_count):
        if debt_id in set(cluster.get("alias_debt_ids", [])):
            return cluster
    return {}


def _is_active_blocking_debt(row: Mapping[str, Any]) -> bool:
    return str(row.get("status") or "active") == "active" and str(row.get("severity") or "") == "blocking"


def _debt_card(row: Mapping[str, Any]) -> Dict[str, Any]:
    obligation = str(row.get("obligation") or "")
    keywords = _keywords(obligation)
    return {
        "debt_id": str(row.get("debt_id") or ""),
        "owner_type": str(row.get("owner_type") or ""),
        "owner_id": str(row.get("owner_id") or ""),
        "target_id": _target_id(row),
        "debt_type": str(row.get("debt_type") or ""),
        "obligation": obligation,
        "repeated_count": int(row.get("repeated_count", 0) or 0),
        "keywords": keywords,
        "anchors": keywords.intersection(_ANCHOR_TERMS),
        "source_artifact_ids": _jsonish_list(row.get("source_artifact_ids_json", row.get("source_artifact_ids", []))),
    }


def _target_id(row: Mapping[str, Any]) -> str:
    return str(row.get("suggested_next_target") or row.get("owner_id") or "root")


def _same_central_obstruction(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if left.get("target_id") != right.get("target_id"):
        return False
    left_keywords = set(left.get("keywords") or [])
    right_keywords = set(right.get("keywords") or [])
    if not left_keywords or not right_keywords:
        return False
    shared = left_keywords.intersection(right_keywords)
    shared_anchors = set(left.get("anchors") or []).intersection(set(right.get("anchors") or []))
    union = left_keywords.union(right_keywords)
    similarity = len(shared) / max(1, len(union))
    return len(shared_anchors) >= 2 or (len(shared) >= 3 and similarity >= 0.22)


def _cluster_card(cluster: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(
        cluster,
        key=lambda row: (
            -int(row.get("repeated_count", 0) or 0),
            -len(row.get("anchors") or []),
            str(row.get("debt_id") or ""),
        ),
    )
    primary = ordered[0]
    all_keywords = sorted(set().union(*(set(row.get("keywords") or []) for row in ordered)))
    anchors = sorted(set().union(*(set(row.get("anchors") or []) for row in ordered)))
    source_ids = sorted(
        {
            str(source_id)
            for row in ordered
            for source_id in row.get("source_artifact_ids", [])
            if str(source_id)
        }
    )
    return {
        "policy": "central-debt-canonicalizer",
        "central_obstruction_id": "central-" + "-".join(anchors[:4] or [str(primary.get("primary_debt_id") or primary.get("debt_id"))]),
        "target_id": str(primary.get("target_id") or "root"),
        "primary_debt_id": str(primary.get("debt_id") or ""),
        "alias_debt_ids": sorted({str(row.get("debt_id") or "") for row in ordered if str(row.get("debt_id") or "")}),
        "alias_count": len(ordered),
        "total_repeated_count": sum(int(row.get("repeated_count", 0) or 0) for row in ordered),
        "keywords": all_keywords[:20],
        "anchor_terms": anchors[:12],
        "obligation": str(primary.get("obligation") or ""),
        "obligation_summaries": [str(row.get("obligation") or "")[:500] for row in ordered[:6]],
        "source_artifact_ids": source_ids,
        "acceptance_criteria": [
            "State the central bridge lemma in local notation.",
            "List exact hypotheses and convention choices.",
            "Prove it, refute it, or split it into strictly sharper sub-bridges.",
            "Run bounded examples or CAS checks when a construction or obstruction can be tested.",
            "Return one proof_dossier, construction_failure, route_obstruction, or verifier-ready route/inference.",
        ],
    }


def _keywords(text: str) -> set[str]:
    compact = (
        text.replace("hinv", "hinv")
        .replace("hinv", "hinv")
        .replace("hinv", "hinv")
        .replace("hinv", "hinv")
        .replace("h_d", "hd")
        .replace("h d", "hd")
        .replace("non split", "nonsplit")
        .replace("non-split", "nonsplit")
        .replace("class-avoidance", "class")
    )
    words = normalize_text(compact).split()
    return {
        word
        for word in words
        if len(word) >= 3 and word not in _STOPWORDS
    }


def _jsonish_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            import json

            value = json.loads(value)
        except Exception:
            return [value] if value else []
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return [str(item) for item in value if str(item)]
    return []
