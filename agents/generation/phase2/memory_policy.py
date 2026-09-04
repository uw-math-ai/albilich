from __future__ import annotations

"""Normalized memory-status policy for phase2 manifests.

Every proof-state row an agent can see is classified into one normalized
``memory_status`` from the update-advice vocabulary:

    verified | candidate | blocked | failed | superseded | stale | background

The mapping is deliberately a pure function of existing columns — no schema
change. It is used by context_builder so every packet item carries an explicit
status, and by the manifest hygiene pass that (a) keeps raw session logs out of
role manifests and (b) reports duplicate debts/retrieval cards instead of
silently dropping them.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from .models import fingerprint_text, json_loads, normalize_text
from .verification import clean_verification_metadata

MEMORY_STATUSES = {
    "verified",
    "candidate",
    "blocked",
    "failed",
    "superseded",
    "stale",
    "background",
}


def role_memory_view_policy(context_role: str) -> Dict[str, Any]:
    """Describe the zero-paperwork memory lens for one epistemic role.

    The rows remain in the single proof-state store; this policy only controls
    how they may be used.  It prevents conjectural work from becoming an
    implicit premise without asking workers to maintain separate notebooks.
    """

    role = str(context_role or "general")
    if role in {"strict_verifier", "integration_verifier", "counterexample_validator"}:
        return {
            "role": role,
            "settled_premise_statuses": ["verified"],
            "candidate_use": "audit target only; never supplement the bounded evidence packet",
            "failed_use": "test whether the submitted proof repeats a known failure",
            "authoritative_boundary": "role packet",
        }
    if role in {"adversarial_reviewer", "villain"}:
        return {
            "role": role,
            "settled_premise_statuses": ["verified"],
            "candidate_use": "targets for refutation, not settled premises",
            "failed_use": "reusable counterexample and obstruction regression library",
            "authoritative_boundary": "target plus adversarial workbench",
        }
    if role in {"phd_advisor", "advisor"}:
        return {
            "role": role,
            "settled_premise_statuses": ["verified"],
            "candidate_use": "route evidence with explicit uncertainty",
            "failed_use": "route-selection evidence and do-not-retry conditions",
            "authoritative_boundary": "global proof graph",
        }
    if role == "literature_researcher":
        return {
            "role": role,
            "settled_premise_statuses": ["verified"],
            "candidate_use": "theorem-matching leads requiring source certification",
            "failed_use": "known applicability failures",
            "authoritative_boundary": "research task and source ledger",
        }
    return {
        "role": role,
        "settled_premise_statuses": ["verified"],
        "candidate_use": "advisory conjectural context only",
        "failed_use": "regression tests and forbidden unchanged routes",
        "authoritative_boundary": "research workbench",
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

CERTIFICATE_ARTIFACT_TYPES = {
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
    # Scheduler-maintained per-branch workbench digests: curated
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
    if status == "refuted":
        return "failed"
    if status == "resolved":
        return "superseded"
    if status == "discarded" or severity == "discarded":
        return "stale"
    return "blocked"


def current_certificate_artifact_ids(state: Mapping[str, Any]) -> set[str]:
    """Certificate ids currently supporting a verified graph entity.

    Store invariants require every such entity to have a current host binding,
    so this context-derived set is stronger than trusting certificate metadata
    in isolation.
    """

    result: set[str] = set()
    for claim in state.get("claims", []) or []:
        if (
            str(claim.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES
            or str(claim.get("lifecycle_status") or "") == "integrated"
        ):
            result.update(str(item) for item in json_loads(claim.get("evidence_artifact_ids_json")) if str(item))
    for inference in state.get("inferences", []) or []:
        if str(inference.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES:
            result.update(str(item) for item in json_loads(inference.get("evidence_artifact_ids_json")) if str(item))
    for route in state.get("routes", []) or []:
        if str(route.get("status") or "") == "integrated":
            result.update(str(item) for item in json_loads(route.get("evidence_artifact_ids_json")) if str(item))
    return result


def artifact_memory_status(
    row: Mapping[str, Any],
    *,
    current_revision: int | None = None,
    current_certificate_ids: set[str] | None = None,
) -> str:
    if artifact_is_raw_log(row):
        return "failed"
    artifact_type = str(row.get("artifact_type") or "")
    metadata = row.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = json_loads(row.get("metadata_json"), {})
        if not isinstance(metadata, Mapping):
            metadata = {}
    if metadata.get("certificate_revoked") is True or metadata.get("stale") is True:
        return "stale"
    if artifact_type in CERTIFICATE_ARTIFACT_TYPES:
        artifact_id = str(row.get("artifact_id") or "")
        if current_certificate_ids is None:
            # A row-local view cannot recompute dependency digests.  Do not
            # advertise an old certificate as current merely because its
            # historical binding remains in metadata.
            return "candidate" if metadata.get("host_certificate_bindings") else "background"
        if artifact_id not in current_certificate_ids:
            return "stale" if metadata.get("host_certificate_bindings") else "background"
        return _certificate_artifact_memory_status(row, metadata)
    if artifact_type in {"final_proof", "final_paper", "verified_blueprint"}:
        # Expository or proposed proof artifacts are never certificates in
        # their own right. Their mathematical claims are settled only through
        # separately indexed, host-bound verification entities.
        return "candidate"
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


def _certificate_artifact_memory_status(
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> str:
    artifact_type = str(row.get("artifact_type") or "")
    producer = str(row.get("producer_role") or "")
    bindings = metadata.get("host_certificate_bindings")
    if not isinstance(bindings, Mapping) or not bindings:
        return "background"
    if artifact_type == "verification_report":
        if producer != "strict_informal_verifier":
            return "failed"
        if clean_verification_metadata(metadata, outcome="positive"):
            return "verified"
        return "failed" if metadata.get("verdict") else "background"
    if artifact_type == "integration_report":
        if producer != "integration_verifier":
            return "failed"
        integrates = metadata.get("integrates") is True
        no_gaps = not list(metadata.get("critical_errors") or []) and not list(metadata.get("gaps") or [])
        return "verified" if integrates and no_gaps else "failed"
    if artifact_type == "formal_backend_result":
        if producer != "formal_backend":
            return "failed"
        host_check = metadata.get("host_formal_check")
        checked = isinstance(host_check, Mapping) and host_check.get("host_checked") is True
        return "verified" if checked else "failed"
    if artifact_type == "confirmed_counterexample":
        if producer != "counterexample_validator":
            return "failed"
        confirmed = metadata.get("confirmed") is True or str(metadata.get("validation_result") or "") == "confirmed"
        return "verified" if confirmed else "failed"
    return "background"


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
    certification = str(row.get("certification_type") or "").strip().lower()
    if certification in {
        "external_citation",
        "independently_reviewed",
        "informally_verified",
        "formally_verified",
        "machine_checked",
    }:
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


@dataclass(frozen=True)
class _DebtMatchSignature:
    dedupe_key: Tuple[str, str]
    is_writing: bool
    status: str
    semantic_scope: str
    type_family: str
    semantic_terms: frozenset[str]


def _debt_match_signature(row: Mapping[str, Any]) -> _DebtMatchSignature:
    return _DebtMatchSignature(
        dedupe_key=_debt_dedupe_key(row),
        is_writing=str(row.get("debt_type") or "") == "writing",
        status=str(row.get("status") or "active"),
        semantic_scope=_debt_semantic_scope(row),
        type_family=_debt_type_family(row),
        semantic_terms=frozenset(_debt_semantic_terms(row)),
    )


def _same_debt_signature(
    left: _DebtMatchSignature,
    right: _DebtMatchSignature,
) -> bool:
    if left.dedupe_key == right.dedupe_key:
        return True
    if left.is_writing or right.is_writing:
        return False
    if left.status != right.status:
        return False
    if left.semantic_scope != right.semantic_scope:
        return False
    if left.type_family != right.type_family:
        return False
    left_terms = left.semantic_terms
    right_terms = right.semantic_terms
    if min(len(left_terms), len(right_terms)) < 7:
        return False
    shared = left_terms & right_terms
    union = left_terms | right_terms
    jaccard = len(shared) / max(1, len(union))
    containment = len(shared) / max(1, min(len(left_terms), len(right_terms)))
    return (len(shared) >= 8 and jaccard >= 0.48) or containment >= 0.82


def _same_debt_obligation(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    # Writing debts are LOCATION-ANCHORED: one debt per violating place in the
    # document. The precomputed signature keeps that exact policy while
    # avoiding repeated normalization for every pair in a large proof state.
    return _same_debt_signature(
        _debt_match_signature(left),
        _debt_match_signature(right),
    )


def canonicalize_debts(
    rows: Iterable[Mapping[str, Any]],
) -> Tuple[List[Mapping[str, Any]], List[Dict[str, Any]]]:
    """Collapse debts with identical owner+obligation fingerprints.

    The canonical row is deterministic: earliest first_seen, then smallest
    debt_id. Returns (canonical rows in input order, duplicate report cards) so
    manifests can report duplicates instead of silently dropping them.
    """
    rows = list(rows)
    groups: List[List[Mapping[str, Any]]] = []
    signature_groups: List[List[_DebtMatchSignature]] = []
    for row in rows:
        signature = _debt_match_signature(row)
        for index, group in enumerate(groups):
            if any(
                _same_debt_signature(signature, existing)
                for existing in signature_groups[index]
            ):
                group.append(row)
                signature_groups[index].append(signature)
                break
        else:
            groups.append([row])
            signature_groups.append([signature])

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
