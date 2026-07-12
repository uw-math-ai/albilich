from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from .models import json_loads
from .store import ProofStateStore

SOLVED_RELATIONS = {"exact", "equivalent", "stronger"}
PARTIAL_RELATIONS = {"weaker", "conditional", "partial", "method", "background", "orthogonal", "unknown"}

# Report-facing outcome vocabulary (2026-07-09 TODO 7): the final report must
# distinguish these five outcomes (plus in_progress while the run is live).
REPORT_CLASSIFICATIONS = {
    "full_theorem_solved",
    "weaker_theorem_proved",
    "conditional_proof",
    "partial_progress",
    "statement_likely_false",
    "in_progress",
}


def classify_result(store: ProofStateStore) -> Dict[str, Any]:
    """Classify public progress without weakening the root theorem."""
    state = store.get_state()
    return classify_state(state)


def classify_state(state: Mapping[str, Any]) -> Dict[str, Any]:
    problem = state["problem_state"]
    root = next((row for row in state["claims"] if row["claim_id"] == "root"), {})
    final_artifact = _final_proof_artifact(state)
    integration = _root_integration_artifact(state)
    relation = _root_relation(integration)
    proved_statement = _proved_statement(integration, root.get("statement") or problem["root_statement"])
    partials = _certified_partials(state)

    if final_artifact and root.get("lifecycle_status") == "integrated" and relation in SOLVED_RELATIONS:
        public_status = "solved"
        result_kind = relation
        summary = _solved_summary(relation)
    elif root.get("lifecycle_status") == "integrated" and relation in SOLVED_RELATIONS:
        public_status = "solved_pending_final_writer"
        result_kind = relation
        summary = _writer_pending_summary(relation)
    elif partials:
        public_status = "certified_partial_progress"
        result_kind = "partial"
        summary = "The root theorem is not solved; verified non-root claims are available as certified partial progress."
    elif any(row["status"] == "active" for row in state.get("debts", [])):
        public_status = "unresolved_with_debt"
        result_kind = "unresolved"
        summary = "The root theorem is unresolved and active proof debt remains."
    else:
        public_status = "in_progress"
        result_kind = "unresolved"
        summary = "The root theorem is still in progress."

    return {
        "public_status": public_status,
        "result_kind": result_kind,
        "relation_to_target": relation,
        "target_statement": problem["root_statement"],
        "proved_statement": proved_statement,
        "summary": summary,
        "report_classification": _report_classification(public_status, root, partials),
        "final_artifact_id": final_artifact.get("artifact_id", "") if final_artifact else "",
        "integration_artifact_id": integration.get("artifact_id", "") if integration else "",
        "certified_partial_results": partials,
        "remaining_obligations": _remaining_obligations(state, public_status),
    }


def _report_classification(public_status: str, root: Mapping[str, Any], partials: list[Dict[str, Any]]) -> str:
    """Five-way report outcome (TODO 7): full theorem solved, weaker theorem
    proved, conditional proof, partial progress, or statement likely false."""
    if str(root.get("validation_status") or "") == "refuted":
        return "statement_likely_false"
    if public_status in {"solved", "solved_pending_final_writer"}:
        return "full_theorem_solved"
    if partials:
        relations = {str(row.get("relation_to_target") or "") for row in partials}
        if "weaker" in relations:
            return "weaker_theorem_proved"
        if relations and relations <= {"conditional"}:
            return "conditional_proof"
        return "partial_progress"
    return "in_progress"


def root_alignment_from_metadata(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    raw = metadata.get("root_alignment") or metadata.get("statement_alignment") or {}
    if not isinstance(raw, Mapping):
        raw = {}
    relation = str(raw.get("relation_to_root") or raw.get("relation") or metadata.get("relation_to_root") or "unknown")
    relation = normalize_result_relation(relation)
    return {
        "relation_to_root": relation,
        "target_statement": str(raw.get("target_statement") or metadata.get("target_statement") or ""),
        "proved_statement": str(raw.get("proved_statement") or metadata.get("proved_statement") or ""),
        "implication_verified": bool(raw.get("implication_verified") or metadata.get("implication_verified") or relation == "exact"),
        "hidden_assumptions": bool(raw.get("hidden_assumptions") or metadata.get("hidden_assumptions") or False),
        "extra_assumptions": list(raw.get("extra_assumptions") or metadata.get("extra_assumptions") or []),
        "notes": str(raw.get("notes") or metadata.get("alignment_notes") or ""),
    }


def normalize_result_relation(value: str) -> str:
    text = (value or "unknown").strip().lower().replace("-", "_")
    aliases = {
        "same": "exact",
        "direct": "exact",
        "direct_match": "exact",
        "known_exact": "exact",
        "equivalent_reformulation": "equivalent",
        "known_equivalent": "equivalent",
        "known_stronger": "stronger",
        "stronger_match": "stronger",
        "known_partial": "partial",
        "partial_match": "partial",
        "conditional_match": "conditional",
        "method_match": "method",
        "irrelevant": "orthogonal",
    }
    text = aliases.get(text, text)
    if text in SOLVED_RELATIONS | PARTIAL_RELATIONS:
        return text
    return "unknown"


def _solved_summary(relation: str) -> str:
    if relation == "stronger":
        return "Solved by a verified stronger theorem whose implication to the target was checked."
    if relation == "equivalent":
        return "Solved by a verified equivalent reformulation of the target theorem."
    return "Solved exactly: the verified result matches the target theorem."


def _writer_pending_summary(relation: str) -> str:
    if relation == "stronger":
        return "Root theorem solved by a stronger verified route; final proof writer is still pending."
    if relation == "equivalent":
        return "Root theorem solved by an equivalent verified route; final proof writer is still pending."
    return "Root theorem solved exactly by a verified route; final proof writer is still pending."


def _final_proof_artifact(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    artifacts = [row for row in state.get("artifacts", []) if row.get("artifact_type") in {"final_proof", "verified_blueprint"}]
    for artifact in sorted(artifacts, key=lambda row: row.get("created_at", ""), reverse=True):
        metadata = _metadata(artifact)
        if str(metadata.get("claim_id") or "root") == "root":
            return artifact
    return None


def _root_integration_artifact(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    artifacts = [row for row in state.get("artifacts", []) if row.get("artifact_type") == "integration_report"]
    for artifact in sorted(artifacts, key=lambda row: row.get("created_at", ""), reverse=True):
        metadata = _metadata(artifact)
        if str(metadata.get("claim_id") or "root") == "root" and (metadata.get("integrates") is True or metadata.get("outcome") == "integrates"):
            return artifact
    return None


def _root_relation(integration: Mapping[str, Any] | None) -> str:
    if not integration:
        return "unknown"
    alignment = root_alignment_from_metadata(_metadata(integration))
    return alignment["relation_to_root"]


def _proved_statement(integration: Mapping[str, Any] | None, fallback: str) -> str:
    if not integration:
        return ""
    alignment = root_alignment_from_metadata(_metadata(integration))
    return alignment.get("proved_statement") or fallback


def _certified_partials(state: Mapping[str, Any]) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for claim in state.get("claims", []):
        if claim.get("claim_id") == "root":
            continue
        if claim.get("validation_status") not in {"informally_verified", "formally_verified"}:
            continue
        relation = _claim_relation(claim)
        rows.append(
            {
                "claim_id": claim["claim_id"],
                "statement": claim["statement"],
                "relation_to_target": relation,
                "status": claim["validation_status"],
                "conditions": json_loads(claim.get("conditions_json")),
            }
        )
    rows.sort(key=lambda row: (row["relation_to_target"] != "partial", row["claim_id"]))
    return rows


def _claim_relation(claim: Mapping[str, Any]) -> str:
    tags = {str(tag).lower() for tag in json_loads(claim.get("tags_json"))}
    for relation in ("stronger", "equivalent", "partial", "conditional", "weaker", "method", "orthogonal"):
        if relation in tags or f"relation:{relation}" in tags:
            return relation
    if claim.get("conditions_json") not in {"[]", "", None}:
        return "conditional"
    return "partial"


def _remaining_obligations(state: Mapping[str, Any], public_status: str) -> list[str]:
    obligations: list[str] = []
    if public_status == "solved":
        return obligations
    if public_status == "solved_pending_final_writer":
        obligations.append("Run the writer/closer to emit the final_proof artifact.")
        return obligations
    active_debts = [row for row in state.get("debts", []) if row.get("status") == "active"]
    for debt in active_debts[:8]:
        obligations.append(f"{debt.get('severity', 'debt')}: {debt.get('obligation', '')}")
    if public_status == "certified_partial_progress":
        obligations.append("The root theorem still requires an exact, equivalent, or stronger verified route.")
    return obligations


def _metadata(artifact: Mapping[str, Any]) -> Dict[str, Any]:
    raw = artifact.get("metadata_json", {})
    if isinstance(raw, str):
        return json_loads(raw, {})
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}
