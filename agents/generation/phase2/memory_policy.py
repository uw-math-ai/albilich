from __future__ import annotations

"""Normalized memory-status policy for phase2 manifests (2026-07-09 TODO 4).

Every proof-state row an agent can see is classified into one normalized
``memory_status`` from the update-advice vocabulary:

    verified | candidate | blocked | failed | superseded | stale | background

The mapping is deliberately a pure function of existing columns — no schema
change. It is used by context_builder so every packet item carries an explicit
status, and by the manifest hygiene pass that (a) keeps raw session logs out of
role manifests and (b) reports duplicate debts/retrieval cards instead of
silently dropping them.
"""

from typing import Any, Dict, Iterable, List, Mapping, Tuple

from .models import fingerprint_text, json_loads, normalize_text

MEMORY_STATUSES = {
    "verified",
    "candidate",
    "blocked",
    "failed",
    "superseded",
    "stale",
    "background",
}

VERIFIED_VALIDATION_STATUSES = {"informally_verified", "formally_verified"}

# Raw run/session logs and transcripts: evidence for humans debugging a run,
# never curated mathematics. These must NEVER enter a role manifest or packet.
RAW_LOG_ARTIFACT_TYPES = {
    "session_failure_report",
    "session_log",
    "session_transcript",
    "raw_transcript",
    "child_session_transcript",
    "run_log",
}
RAW_LOG_ARTIFACT_ID_PREFIXES = ("session_failure_",)

VERIFIED_ARTIFACT_TYPES = {
    "final_proof",
    "final_paper",
    "verified_blueprint",
    "verification_report",
    "integration_report",
    "formal_backend_result",
    "confirmed_counterexample",
}
FAILED_ARTIFACT_TYPES = {
    "failed_decomposition_plan",
    "construction_failure",
    "key_failure_analysis",
    "route_obstruction",
    "hypothesis_gap",
}
BACKGROUND_ARTIFACT_TYPES = {
    "advisor_report",
    "route_triage_report",
    "definition_audit_report",
    "literature_search_request",
    "stop_summary_report",
    "run_interruption_event",
    "writing_review",
    "writer_report",
    # Scheduler-maintained per-branch workbench digests (TODO 1): curated
    # context, never proof evidence.
    "branch_workbench",
}
# Working notes go stale by age; proofs/blueprints stay candidate until
# superseded through the proof graph itself.
WORKING_NOTE_ARTIFACT_TYPES = {
    "research_notebook",
    "research_diagnostic",
    "decomposition_plan",
}
STALE_ARTIFACT_REVISION_GAP = 40

# Retrieval-card applicability classifications that make a source an active
# candidate proof input rather than background reading.
CANDIDATE_RETRIEVAL_RELATIONS = {
    "direct_match",
    "stronger_match",
    "equivalent_reformulation",
    "conditional_match",
    "partial_match",
    "method_match",
}


def claim_memory_status(row: Mapping[str, Any]) -> str:
    lifecycle = str(row.get("lifecycle_status") or "")
    validation = str(row.get("validation_status") or "")
    if lifecycle == "superseded":
        return "superseded"
    if validation == "refuted" or lifecycle == "abandoned":
        return "failed"
    if validation in VERIFIED_VALIDATION_STATUSES:
        return "verified"
    if lifecycle == "blocked" or validation == "challenged":
        return "blocked"
    return "candidate"


def route_memory_status(row: Mapping[str, Any]) -> str:
    status = str(row.get("status") or "")
    if status == "superseded":
        return "superseded"
    if status == "abandoned":
        return "failed"
    if status == "blocked":
        return "blocked"
    if status == "integrated":
        return "verified"
    return "candidate"


def inference_memory_status(row: Mapping[str, Any]) -> str:
    validation = str(row.get("validation_status") or "")
    if validation == "refuted":
        return "failed"
    if validation in VERIFIED_VALIDATION_STATUSES:
        return "verified"
    if validation == "challenged":
        return "blocked"
    return "candidate"


def debt_memory_status(row: Mapping[str, Any]) -> str:
    status = str(row.get("status") or "")
    severity = str(row.get("severity") or "")
    if status == "resolved":
        return "superseded"
    if status == "discarded" or severity == "discarded":
        return "stale"
    return "blocked"


def artifact_memory_status(row: Mapping[str, Any], *, current_revision: int | None = None) -> str:
    if artifact_is_raw_log(row):
        return "failed"
    artifact_type = str(row.get("artifact_type") or "")
    if artifact_type in VERIFIED_ARTIFACT_TYPES:
        return "verified"
    if artifact_type in FAILED_ARTIFACT_TYPES:
        return "failed"
    if artifact_type in BACKGROUND_ARTIFACT_TYPES:
        return "background"
    if current_revision is not None and artifact_type in WORKING_NOTE_ARTIFACT_TYPES:
        try:
            revision = int(row.get("state_revision") or 0)
        except (TypeError, ValueError):
            revision = 0
        if int(current_revision) - revision > STALE_ARTIFACT_REVISION_GAP:
            return "stale"
    return "candidate"


def retrieval_card_memory_status(row: Mapping[str, Any]) -> str:
    applicability = row.get("applicability")
    if not isinstance(applicability, Mapping):
        applicability = json_loads(row.get("applicability_json"), {})
        if not isinstance(applicability, Mapping):
            applicability = {}
    relation = str(applicability.get("classification") or applicability.get("relation") or "")
    if relation in CANDIDATE_RETRIEVAL_RELATIONS:
        return "candidate"
    return "background"


def theorem_library_memory_status(row: Mapping[str, Any]) -> str:
    certification = str(row.get("certification_type") or "")
    if certification == "external_citation" or "certif" in certification or "verified" in certification:
        return "verified"
    return "background"


def artifact_is_raw_log(row: Mapping[str, Any]) -> bool:
    """True for raw session logs/transcripts that must stay out of manifests."""
    artifact_type = str(row.get("artifact_type") or "")
    if artifact_type in RAW_LOG_ARTIFACT_TYPES:
        return True
    artifact_id = str(row.get("artifact_id") or "")
    return artifact_id.startswith(RAW_LOG_ARTIFACT_ID_PREFIXES)


_DEBT_SEMANTIC_STOPWORDS = {
    "and", "are", "for", "from", "into", "must", "of", "or", "prove",
    "show", "supply", "that", "the", "their", "this", "to", "verify", "with",
}


def _debt_dedupe_key(row: Mapping[str, Any]) -> Tuple[str, str]:
    obligation = str(row.get("obligation") or "")
    fingerprint = fingerprint_text(obligation) or str(row.get("fingerprint") or "")
    return (str(row.get("owner_id") or ""), fingerprint)


def _debt_semantic_scope(row: Mapping[str, Any]) -> str:
    return str(row.get("suggested_next_target") or row.get("owner_id") or "")


def _debt_type_family(row: Mapping[str, Any]) -> str:
    debt_type = str(row.get("debt_type") or "").lower()
    if debt_type in {"missing_reference", "source_gap", "citation_verification"}:
        return "source"
    if debt_type in {"counterexample_risk", "counterexample_validation"}:
        return "counterexample"
    return "proof"


def _debt_semantic_terms(row: Mapping[str, Any]) -> set[str]:
    return {
        term
        for term in normalize_text(str(row.get("obligation") or "")).split()
        if len(term) >= 4 and term not in _DEBT_SEMANTIC_STOPWORDS
    }


def _same_debt_obligation(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if _debt_dedupe_key(left) == _debt_dedupe_key(right):
        return True
    # Writing debts are LOCATION-ANCHORED: one debt per violating place in the
    # document, and same-rule obligations differ only in section title / line /
    # excerpt (three sections missing their L4-HOUSE-07 opener are three
    # distinct debts). Term-overlap merging would collapse them and truncate
    # the writing-gate checklists, so only the exact owner+obligation
    # fingerprint above may dedupe them.
    if str(left.get("debt_type") or "") == "writing" or str(right.get("debt_type") or "") == "writing":
        return False
    if str(left.get("status") or "active") != str(right.get("status") or "active"):
        return False
    if _debt_semantic_scope(left) != _debt_semantic_scope(right):
        return False
    if _debt_type_family(left) != _debt_type_family(right):
        return False
    left_terms = _debt_semantic_terms(left)
    right_terms = _debt_semantic_terms(right)
    if min(len(left_terms), len(right_terms)) < 7:
        return False
    shared = left_terms & right_terms
    union = left_terms | right_terms
    jaccard = len(shared) / max(1, len(union))
    containment = len(shared) / max(1, min(len(left_terms), len(right_terms)))
    return (len(shared) >= 8 and jaccard >= 0.48) or containment >= 0.82


def canonicalize_debts(
    rows: Iterable[Mapping[str, Any]],
) -> Tuple[List[Mapping[str, Any]], List[Dict[str, Any]]]:
    """Collapse debts with identical owner+obligation fingerprints.

    The canonical row is deterministic: earliest first_seen, then smallest
    debt_id. Returns (canonical rows in input order, duplicate report cards) so
    manifests can report duplicates instead of silently dropping them.
    """
    groups: List[List[Mapping[str, Any]]] = []
    for row in rows:
        for group in groups:
            if any(_same_debt_obligation(row, existing) for existing in group):
                group.append(row)
                break
        else:
            groups.append([row])

    canonical_by_debt_id: Dict[str, Mapping[str, Any]] = {}
    duplicate_ids: set[str] = set()
    duplicates: List[Dict[str, Any]] = []
    for raw_group in groups:
        group = sorted(
            raw_group,
            key=lambda row: (str(row.get("first_seen") or ""), str(row.get("debt_id") or "")),
        )
        canonical_row = dict(group[0])
        canonical_id = str(canonical_row.get("debt_id") or "")
        alias_ids = [str(row.get("debt_id") or "") for row in group[1:]]
        if alias_ids:
            canonical_row["canonical_alias_debt_ids"] = alias_ids
            canonical_row["repeated_count"] = sum(int(row.get("repeated_count") or 0) for row in group)
        canonical_by_debt_id[canonical_id] = canonical_row
        if len(group) > 1:
            duplicate_ids.update(alias_ids)
            duplicates.append(
                {
                    "kind": "debt",
                    "canonical_debt_id": canonical_id,
                    "duplicate_debt_ids": alias_ids,
                    "owner_id": str(group[0].get("owner_id") or ""),
                    "obligation_fingerprint": fingerprint_text(str(group[0].get("obligation") or "")),
                    "semantic_match": any(
                        _debt_dedupe_key(group[0]) != _debt_dedupe_key(row) for row in group[1:]
                    ),
                }
            )

    canonical: List[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        debt_id = str(row.get("debt_id") or "")
        if debt_id in duplicate_ids:
            continue
        if debt_id in seen:
            continue
        seen.add(debt_id)
        canonical.append(canonical_by_debt_id.get(debt_id, row))
    return canonical, duplicates


def canonicalize_retrieval_cards(
    rows: Iterable[Mapping[str, Any]],
) -> Tuple[List[Mapping[str, Any]], List[Dict[str, Any]]]:
    """Collapse retrieval cards with identical statement fingerprints.

    ``rows`` should arrive rank-ordered (best first): the canonical card is the
    best-ranked one, with card_id as the deterministic tiebreak inside a
    fingerprint group. Returns (canonical rows, duplicate report cards).
    """
    groups: Dict[str, List[Mapping[str, Any]]] = {}
    order: List[str] = []
    unfingerprinted: List[Mapping[str, Any]] = []
    for row in rows:
        fingerprint = fingerprint_text(str(row.get("exact_statement") or ""))
        if not fingerprint:
            unfingerprinted.append(row)
            continue
        if fingerprint not in groups:
            groups[fingerprint] = []
            order.append(fingerprint)
        groups[fingerprint].append(row)

    canonical: List[Mapping[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    consumed: set[int] = set()
    for row in rows:
        if id(row) in consumed:
            continue
        fingerprint = fingerprint_text(str(row.get("exact_statement") or ""))
        if not fingerprint:
            canonical.append(row)
            consumed.add(id(row))
            continue
        group = groups.get(fingerprint, [row])
        for member in group:
            consumed.add(id(member))
        canonical.append(group[0])
        if len(group) > 1:
            duplicates.append(
                {
                    "kind": "retrieval_card",
                    "canonical_card_id": str(group[0].get("card_id") or ""),
                    "duplicate_card_ids": sorted(str(member.get("card_id") or "") for member in group[1:]),
                    "statement_fingerprint": fingerprint,
                }
            )
    return canonical, duplicates
