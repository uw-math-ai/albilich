from __future__ import annotations

"""Paper solution audit mode (2026-07-09 TODO 6): a conservative referee.

``--research-mode paper_solution_audit`` (or the ``audit-paper`` CLI command)
turns a submitted LaTeX/markdown/pasted proof into the AUDIT SUBJECT: the
root statement becomes "audit the submitted proof of X", not "prove X". The
existing roles are reused at the directive level:

- researcher/verifier decompose the document into paper_claims (existing
  claims tagged with the conventions below), check local implications first,
  and mark each claim with the audit status vocabulary;
- the villain hunts hidden hypotheses, counterexamples, and notation
  mismatches in the submitted argument;
- the literature researcher checks citations exactly (source + theorem number
  + hypotheses) through the existing retrieval machinery;
- the writer's deliverable is a referee-style report, never a polished proof,
  and the writing gate's paper authoring never fires in this mode.

Claim metadata convention (no schema change — tags on existing claims):

    tags = ["paper_claim",
            "audit_status:<status>",        # audit vocabulary below
            "source_location:<Section 3, Theorem 3.2, paragraph 2>"]

Repairs are PROPOSED, clearly separated from the audit verdict: repair
artifacts use artifact_type ``proposed_repair`` and are rendered in their own
report section, never merged into the claim map.
"""

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .models import json_dumps, json_loads, sha256_text, utc_now

PAPER_AUDIT_RESEARCH_MODE = "paper_solution_audit"
AUDIT_SUBJECT_ARTIFACT_TYPE = "audit_subject"
AUDIT_SUBJECT_ARTIFACT_ID = "audit_subject_root"
PROPOSED_REPAIR_ARTIFACT_TYPE = "proposed_repair"
REFEREE_REPORT_ARTIFACT_TYPE = "referee_report"
PAPER_AUDIT_INGESTED_EVENT = "paper_audit_ingested"

PAPER_CLAIM_TAG = "paper_claim"
AUDIT_STATUS_TAG_PREFIX = "audit_status:"
SOURCE_LOCATION_TAG_PREFIX = "source_location:"

# The referee's per-claim status vocabulary, mapped conservatively onto the
# existing validation_status vocabulary (the tag keeps the fine distinction).
AUDIT_CLAIM_STATUSES = (
    "checked",
    "probably_correct",
    "needs_detail",
    "gap",
    "overclaim",
    "citation_needed",
    "false_or_counterexample_risk",
    "out_of_scope",
)
AUDIT_STATUS_TO_VALIDATION = {
    "checked": "informally_verified",
    "probably_correct": "plausible",
    "needs_detail": "untested",
    "gap": "challenged",
    "overclaim": "challenged",
    "citation_needed": "untested",
    "false_or_counterexample_risk": "challenged",
    "out_of_scope": "untested",
}

AUDIT_CONFIDENCE_SUMMARIES = (
    "appears_correct_modulo_minor_details",
    "major_gaps",
    "not_verified",
    "likely_false",
)

AUDIT_WARNING_LINE = (
    "WARNING: this is an AI audit, not a formal proof. No claim below is formally verified unless a "
    "formal verifier checked it; treat 'checked' as careful machine-assisted review, not certification."
)


def is_paper_audit_mode(research_mode: str | None) -> bool:
    return str(research_mode or "") == PAPER_AUDIT_RESEARCH_MODE


def audit_subject_artifact(state: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """The submitted document under audit, if this problem is an audit run."""
    rows = list(state.get("artifacts", [])) + list(state.get("research_artifacts", []))
    for artifact in rows:
        if str(artifact.get("artifact_type") or "") == AUDIT_SUBJECT_ARTIFACT_TYPE:
            return artifact
    return None


def is_audit_state(state: Mapping[str, Any]) -> bool:
    return audit_subject_artifact(state) is not None


def audit_root_statement(title: str, *, artifact_id: str = AUDIT_SUBJECT_ARTIFACT_ID) -> str:
    """Root statement for an audit run: audit the submitted proof, do not
    solve a different problem."""
    return (
        f"Audit the submitted proof of: {title}. The submitted document is stored as artifact "
        f"{artifact_id} and is the AUDIT SUBJECT. The goal is a conservative referee-style audit of "
        "the author's argument as written — decompose it into paper claims, check local implications, "
        "audit citations exactly, and report gaps/overclaims at precise locations — not to prove the "
        "theorem independently or to rewrite the proof."
    )


def document_title(text: str, *, fallback: str) -> str:
    """Best-effort title: LaTeX \\title{...}, first markdown heading, or filename."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("\\title"):
            inner = stripped.split("{", 1)[-1].rsplit("}", 1)[0].strip()
            if inner:
                return inner
        if stripped.startswith("#"):
            inner = stripped.lstrip("#").strip()
            if inner:
                return inner
    return fallback


def ingest_paper_audit(
    store: Any,
    document: Path,
    *,
    title: str = "",
    total_token_budget: int | None = None,
    reserved_verification_budget: int | None = None,
) -> Dict[str, Any]:
    """Ingest a proof document as the audit subject of a fresh audit problem.

    Initializes the problem with the audit root statement, stores the document
    as an ``audit_subject`` artifact, and records the ingestion event plus an
    ``audit_or_problem_refinement`` root-intent note.
    """
    from .completion_policy import record_root_intent_resolution

    document = Path(document)
    text = document.read_text(encoding="utf-8")
    resolved_title = title.strip() or document_title(text, fallback=document.stem.replace("_", " "))
    root_statement = audit_root_statement(resolved_title)
    init_kwargs: Dict[str, Any] = {}
    if total_token_budget is not None:
        init_kwargs["total_token_budget"] = total_token_budget
    if reserved_verification_budget is not None:
        init_kwargs["reserved_verification_budget"] = reserved_verification_budget
    store.init_problem(root_statement, **init_kwargs)

    suffix = document.suffix.lower() if document.suffix.lower() in {".tex", ".md", ".txt"} else ".md"
    artifact_dir = store.state_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{AUDIT_SUBJECT_ARTIFACT_ID}{suffix}"
    artifact_path.write_text(text, encoding="utf-8")
    now = utc_now()
    metadata = {
        "source_file": str(document),
        "title": resolved_title,
        "format": suffix.lstrip("."),
        "role": "audit_subject",
        "note": "This document is the object under audit, not proof-state evidence produced by the run.",
    }
    with store.connect() as conn:
        revision = int(store.get_problem_row(conn)["current_revision"])
        conn.execute(
            """
            INSERT OR REPLACE INTO artifacts(
                artifact_id, artifact_type, path, sha256, producer_role, run_id,
                state_revision, content_summary, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, 'human_operator', '', ?, ?, ?, ?)
            """,
            (
                AUDIT_SUBJECT_ARTIFACT_ID,
                AUDIT_SUBJECT_ARTIFACT_TYPE,
                str(artifact_path),
                sha256_text(text),
                revision,
                f"Submitted proof document under audit: {resolved_title}"[:500],
                json_dumps(metadata),
                now,
            ),
        )
        store.write_event(
            conn,
            revision,
            PAPER_AUDIT_INGESTED_EVENT,
            {"artifact_id": AUDIT_SUBJECT_ARTIFACT_ID, "title": resolved_title, "source_file": str(document)},
        )
        conn.commit()
    intent = record_root_intent_resolution(store, research_mode=PAPER_AUDIT_RESEARCH_MODE)
    return {
        "problem_id": store.problem_id,
        "artifact_id": AUDIT_SUBJECT_ARTIFACT_ID,
        "artifact_path": str(artifact_path),
        "title": resolved_title,
        "root_statement": root_statement,
        "root_intent": intent,
        "research_mode": PAPER_AUDIT_RESEARCH_MODE,
    }


def _claim_tags(claim: Mapping[str, Any]) -> List[str]:
    tags = claim.get("tags")
    if not isinstance(tags, list):
        tags = json_loads(claim.get("tags_json"))
    return [str(tag) for tag in tags if str(tag)]


def audit_status_for_claim(claim: Mapping[str, Any]) -> str:
    for tag in _claim_tags(claim):
        if tag.startswith(AUDIT_STATUS_TAG_PREFIX):
            status = tag[len(AUDIT_STATUS_TAG_PREFIX):].strip()
            if status in AUDIT_CLAIM_STATUSES:
                return status
    return ""


def source_location_for_claim(claim: Mapping[str, Any]) -> str:
    for tag in _claim_tags(claim):
        if tag.startswith(SOURCE_LOCATION_TAG_PREFIX):
            return tag[len(SOURCE_LOCATION_TAG_PREFIX):].strip()
    return ""


def paper_claims(state: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Claims decomposed from the audit subject, with their audit metadata."""
    rows: List[Dict[str, Any]] = []
    for claim in state.get("claims", []):
        if PAPER_CLAIM_TAG not in _claim_tags(claim):
            continue
        rows.append(
            {
                "claim_id": str(claim.get("claim_id") or ""),
                "statement": str(claim.get("statement") or ""),
                "audit_status": audit_status_for_claim(claim),
                "source_location": source_location_for_claim(claim),
                "validation_status": str(claim.get("validation_status") or ""),
            }
        )
    rows.sort(key=lambda row: (row["source_location"], row["claim_id"]))
    return rows


def proposed_repairs(state: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for artifact in state.get("artifacts", []):
        if str(artifact.get("artifact_type") or "") != PROPOSED_REPAIR_ARTIFACT_TYPE:
            continue
        rows.append(
            {
                "artifact_id": str(artifact.get("artifact_id") or ""),
                "summary": str(artifact.get("content_summary") or ""),
            }
        )
    return rows


def audit_confidence_summary(state: Mapping[str, Any]) -> str:
    """Conservative overall classification of the submitted proof."""
    claims = paper_claims(state)
    if not claims:
        return "not_verified"
    statuses = {row["audit_status"] for row in claims}
    if "false_or_counterexample_risk" in statuses:
        return "likely_false"
    if "gap" in statuses or "overclaim" in statuses:
        return "major_gaps"
    if "checked" in statuses:
        return "appears_correct_modulo_minor_details"
    return "not_verified"


def paper_audit_context_card(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Compact audit contract carried in every session manifest of an audit run."""
    subject = audit_subject_artifact(state)
    if subject is None:
        return {}
    return {
        "research_mode": PAPER_AUDIT_RESEARCH_MODE,
        "audit_subject_artifact_id": str(subject.get("artifact_id") or ""),
        "audit_subject_path": str(subject.get("path") or ""),
        "claim_tag_convention": [
            PAPER_CLAIM_TAG,
            f"{AUDIT_STATUS_TAG_PREFIX}<status>",
            f"{SOURCE_LOCATION_TAG_PREFIX}<section/theorem number/paragraph>",
        ],
        "status_vocabulary": list(AUDIT_CLAIM_STATUSES),
        "status_to_validation": dict(AUDIT_STATUS_TO_VALIDATION),
        "conservative_defaults": (
            "No claim becomes checked from global plausibility; check local implications first; "
            "repairs are PROPOSED (artifact_type proposed_repair) and stay separate from the audit verdict."
        ),
        "deliverable": "referee-style audit report, not a polished proof",
        "warning": AUDIT_WARNING_LINE,
    }


def build_referee_report_lines(state: Mapping[str, Any]) -> List[str]:
    """Referee-style audit sections for the markdown report."""
    subject = audit_subject_artifact(state)
    if subject is None:
        return []
    metadata = subject.get("metadata_json", {})
    if isinstance(metadata, str):
        metadata = json_loads(metadata, {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    claims = paper_claims(state)
    lines = [
        "## Referee Audit Report",
        "",
        AUDIT_WARNING_LINE,
        "",
        f"- Audit subject: `{subject.get('artifact_id', '')}` ({metadata.get('title', 'untitled submission')})",
        f"- Confidence summary (conservative): `{audit_confidence_summary(state)}`",
        "",
        "### Claim Map",
        "",
    ]
    if claims:
        for row in claims:
            location = row["source_location"] or "location not recorded"
            status = row["audit_status"] or "unaudited"
            lines.append(f"- `{row['claim_id']}` `{status}` ({location}): {row['statement']}")
    else:
        lines.append("No paper claims recorded yet; the audit decomposition has not run.")
    lines.append("")

    def _section(title: str, statuses: set[str], empty: str) -> None:
        lines.extend([f"### {title}", ""])
        matching = [row for row in claims if row["audit_status"] in statuses]
        if matching:
            for row in matching:
                location = row["source_location"] or "location not recorded"
                lines.append(f"- `{row['claim_id']}` ({location}): {row['statement']}")
        else:
            lines.append(empty)
        lines.append("")

    _section("Gap List", {"gap", "needs_detail"}, "No gaps or missing details recorded.")
    _section(
        "Citation Audit",
        {"citation_needed"},
        "No unresolved citation checks recorded; see Retrieval Cards for checked sources.",
    )
    _section("Overclaim Report", {"overclaim"}, "No overclaims recorded.")
    _section(
        "Counterexample Risks",
        {"false_or_counterexample_risk"},
        "No false-or-counterexample risks recorded.",
    )
    _section(
        "Local Correctness Report",
        {"checked", "probably_correct"},
        "No locally checked steps recorded yet.",
    )

    lines.extend(["### Proposed Repairs (separate from the audit verdict)", ""])
    repairs = proposed_repairs(state)
    if repairs:
        lines.append(
            "The following repairs are PROPOSED by the audit run; they are suggestions, not part of "
            "the author's checked proof."
        )
        for repair in repairs:
            lines.append(f"- `{repair['artifact_id']}`: {repair['summary']}")
    else:
        lines.append("No repairs proposed.")
    lines.append("")
    return lines
