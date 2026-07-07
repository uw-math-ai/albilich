from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from .models import SCHEMA_VERSION, fingerprint_text, normalize_text
from .research_policy import normalize_retrieval_relation
from .store import ProofStateStore


def retrieval_card_operation(
    *,
    query: str,
    exact_statement: str,
    target_id: str = "root",
    source_identifiers: Mapping[str, Any] | None = None,
    hypotheses: Sequence[str] | None = None,
    local_definitions: Sequence[str] | None = None,
    applicability: Mapping[str, Any] | None = None,
    missing_hypotheses: Sequence[str] | None = None,
    source_location: str = "",
    source_version: str = "manual",
) -> Dict[str, Any]:
    content_hash = fingerprint_text(exact_statement + source_location, length=32)
    applicability_payload = dict(applicability or {})
    applicability_payload.setdefault("target_id", target_id)
    relation = normalize_retrieval_relation(applicability_payload.get("relation") or applicability_payload.get("classification"))
    applicability_payload["classification"] = relation
    applicability_payload.setdefault("relation", relation)
    applicability_payload.setdefault("theorem_matching_status", "unverified_literature_card")
    applicability_payload.setdefault("implication_to_target_verified", False)
    return {
        "op": "cache_retrieval_card",
        "card_id": f"retrieval-{content_hash[:16]}",
        "query": query,
        "target_id": target_id,
        "normalized_query": normalize_text(query),
        "source_version": source_version,
        "exact_statement": exact_statement,
        "source_identifiers": dict(source_identifiers or {}),
        "hypotheses": list(hypotheses or []),
        "local_definitions": list(local_definitions or []),
        "applicability": applicability_payload,
        "missing_hypotheses": list(missing_hypotheses or []),
        "source_location": source_location,
        "content_hash": content_hash,
    }


def retrieval_patch(store: ProofStateStore, *, target_id: str, cards: Sequence[Mapping[str, Any]], rationale: str = "cache retrieval cards") -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": store.problem_id,
        "base_revision": store.get_revision(),
        "actor_role": "literature_researcher",
        "target_id": target_id,
        "operations": [dict(card) for card in cards],
        "rationale": rationale,
    }
