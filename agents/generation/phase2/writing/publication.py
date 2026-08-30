"""Durable state for the terminal writer--referee publication loop.

The paper itself remains an artifact.  Every referee decision additionally has
one row in ``publication_reviews`` so scheduling and the dashboard do not need
to infer a review round from prose.  This module deliberately contains no
scheduler imports.  Patch application can register a decision atomically with
its referee report, while the scheduler can later mark a route-error decision
as escalated back to research.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Mapping

from ..models import compact_dict, utc_now


PUBLICATION_REVIEW_MARKER = "publication_review"
PUBLICATION_REFEREE_LENS = "publication_referee"
REFEREE_VERDICTS = {"accept", "revise", "major_proof_route_error"}
REFEREE_DECISION_TOKENS = {
    "accept": "[accept]",
    "revise": "[revise]",
    "major_proof_route_error": "[major-proof-route-error]",
}


def prepare_referee_report_metadata(
    conn: sqlite3.Connection,
    *,
    actor_role: str,
    artifact_type: str,
    metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate and canonicalize a publication referee report.

    ``referee_report`` predates the publication loop and is also used by the
    paper-audit mode.  Only reports produced by the ``referee`` role enter this
    contract.  Legacy writer-produced audit reports pass through unchanged.
    """

    result = dict(metadata)
    if artifact_type != "referee_report" or actor_role != "referee":
        return result

    verdict = str(result.get("verdict") or "").strip().lower().replace("-", "_")
    if verdict not in REFEREE_VERDICTS:
        raise ValueError(
            "publication referee_report metadata.verdict must be one of "
            + ", ".join(sorted(REFEREE_VERDICTS))
        )
    paper_id = str(
        result.get("reviewed_paper_artifact_id")
        or result.get("artifact_reviewed")
        or ""
    ).strip()
    paper = conn.execute(
        "SELECT artifact_type, metadata_json FROM artifacts WHERE artifact_id = ?",
        (paper_id,),
    ).fetchone()
    if paper is None or str(paper["artifact_type"] or "") != "final_paper":
        raise ValueError(
            "publication referee_report requires metadata.reviewed_paper_artifact_id "
            "naming an existing final_paper"
        )
    paper_metadata = _json_object(paper["metadata_json"])
    certificate_id = str(
        result.get("certificate_artifact_id")
        or paper_metadata.get("certificate_artifact_id")
        or ""
    ).strip()
    certificate = conn.execute(
        "SELECT artifact_type FROM artifacts WHERE artifact_id = ?",
        (certificate_id,),
    ).fetchone()
    if certificate is None or str(certificate["artifact_type"] or "") not in {
        "final_proof",
        "verified_blueprint",
    }:
        raise ValueError(
            "publication referee_report requires metadata.certificate_artifact_id "
            "naming the internal final proof certificate"
        )

    prior = conn.execute(
        "SELECT review_id FROM publication_reviews ORDER BY round_number DESC LIMIT 1"
    ).fetchone()
    round_number = int(
        conn.execute("SELECT COUNT(*) AS n FROM publication_reviews").fetchone()["n"]
    ) + 1
    findings = result.get("findings")
    finding_count = len(findings) if isinstance(findings, list) else int(result.get("finding_count") or 0)
    if verdict == "revise" and finding_count <= 0:
        raise ValueError(
            "a [revise] referee report requires metadata.findings with at least one located finding"
        )
    if verdict == "revise":
        for index, finding in enumerate(findings if isinstance(findings, list) else [], start=1):
            if not isinstance(finding, Mapping) or any(
                not str(finding.get(field) or "").strip()
                for field in ("severity", "location", "problem", "required_fix")
            ):
                raise ValueError(
                    f"referee finding {index} requires severity, location, problem, and required_fix"
                )

    route_id = str(result.get("affected_route_id") or "").strip()
    falsified_step = str(result.get("falsified_step") or "").strip()
    mathematical_evidence = str(result.get("mathematical_evidence") or "").strip()
    if verdict == "major_proof_route_error":
        route = conn.execute(
            "SELECT conclusion_claim_id FROM routes WHERE route_id = ?",
            (route_id,),
        ).fetchone()
        if route is None or str(route["conclusion_claim_id"] or "") != "root":
            raise ValueError(
                "[major-proof-route-error] requires metadata.affected_route_id naming a root proof route"
            )
        if len(falsified_step) < 20 or len(mathematical_evidence) < 80:
            raise ValueError(
                "[major-proof-route-error] requires a precise falsified_step and substantive mathematical_evidence"
            )
    elif route_id or falsified_step or mathematical_evidence:
        raise ValueError(
            "route-falsification metadata is reserved for verdict=major_proof_route_error"
        )

    result.update(
        {
            PUBLICATION_REVIEW_MARKER: True,
            "lens": PUBLICATION_REFEREE_LENS,
            "verdict": verdict,
            "decision_token": REFEREE_DECISION_TOKENS[verdict],
            "artifact_reviewed": paper_id,
            "reviewed_paper_artifact_id": paper_id,
            "certificate_artifact_id": certificate_id,
            "round_number": round_number,
            "previous_referee_report_id": str(prior["review_id"] or "") if prior else "",
            "finding_count": finding_count,
            "affected_route_id": route_id,
            "falsified_step": falsified_step,
            "mathematical_evidence": mathematical_evidence,
        }
    )
    return result


def prepare_final_paper_metadata(
    conn: sqlite3.Connection,
    *,
    actor_role: str,
    artifact_type: str,
    metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    """Add immutable certificate and paper-version lineage to writer output."""

    result = dict(metadata)
    if artifact_type != "final_paper" or actor_role != "writer":
        return result
    predecessor = conn.execute(
        "SELECT artifact_id, metadata_json FROM artifacts "
        "WHERE artifact_type = 'final_paper' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    predecessor_id = str(result.get("revision_of_artifact_id") or "").strip()
    if predecessor_id:
        explicit = conn.execute(
            "SELECT artifact_type, metadata_json FROM artifacts WHERE artifact_id = ?",
            (predecessor_id,),
        ).fetchone()
        if explicit is None or str(explicit["artifact_type"] or "") != "final_paper":
            raise ValueError("final_paper metadata.revision_of_artifact_id must name an existing final_paper")
        predecessor = explicit
    elif predecessor is not None:
        predecessor_id = str(predecessor["artifact_id"] or "")

    predecessor_metadata = _json_object(predecessor["metadata_json"]) if predecessor else {}
    certificate_id = str(
        result.get("certificate_artifact_id")
        or predecessor_metadata.get("certificate_artifact_id")
        or ""
    ).strip()
    if not certificate_id:
        certificate = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE artifact_type IN ('final_proof', 'verified_blueprint') "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        certificate_id = str(certificate["artifact_id"] or "") if certificate else ""
    if certificate_id:
        certificate = conn.execute(
            "SELECT artifact_type FROM artifacts WHERE artifact_id = ?",
            (certificate_id,),
        ).fetchone()
        # Paper-guard fixtures and imports may carry a forward reference to a
        # certificate that is not present in this store.  The publication
        # referee contract below is the point at which that reference becomes
        # mandatory and is checked strictly.  If the referenced artifact is
        # present already, however, it must be a genuine proof certificate.
        if certificate is not None and str(certificate["artifact_type"] or "") not in {
            "final_proof",
            "verified_blueprint",
        }:
            raise ValueError("final_paper metadata.certificate_artifact_id must name a final proof certificate")

    addressed_report_id = str(result.get("addresses_referee_report_id") or "").strip()
    if predecessor_id and not addressed_report_id:
        report = conn.execute(
            "SELECT review_id FROM publication_reviews WHERE paper_artifact_id = ? "
            "ORDER BY round_number DESC LIMIT 1",
            (predecessor_id,),
        ).fetchone()
        addressed_report_id = str(report["review_id"] or "") if report else ""
    paper_version = int(
        conn.execute("SELECT COUNT(*) AS n FROM artifacts WHERE artifact_type = 'final_paper'").fetchone()["n"]
    ) + 1
    result.update(
        {
            "certificate_artifact_id": certificate_id,
            "revision_of_artifact_id": predecessor_id,
            "addresses_referee_report_id": addressed_report_id,
            "paper_version": paper_version,
            "publication_workflow": "writer_referee",
        }
    )
    return result


def record_referee_report(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    metadata: Mapping[str, Any],
    state_revision: int,
    created_at: str,
) -> None:
    """Insert the SQL review row for a canonical publication report."""

    if metadata.get(PUBLICATION_REVIEW_MARKER) is not True:
        return
    conn.execute(
        """
        INSERT INTO publication_reviews(
            review_id, round_number, paper_artifact_id, certificate_artifact_id,
            verdict, decision_token, affected_route_id, falsified_step,
            mathematical_evidence, finding_count, metadata_json, state_revision,
            created_at, escalated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
        """,
        (
            artifact_id,
            int(metadata.get("round_number") or 0),
            str(metadata.get("reviewed_paper_artifact_id") or ""),
            str(metadata.get("certificate_artifact_id") or ""),
            str(metadata.get("verdict") or ""),
            str(metadata.get("decision_token") or ""),
            str(metadata.get("affected_route_id") or ""),
            str(metadata.get("falsified_step") or ""),
            str(metadata.get("mathematical_evidence") or ""),
            int(metadata.get("finding_count") or 0),
            json.dumps(dict(metadata), sort_keys=True, ensure_ascii=False),
            int(state_revision),
            created_at,
        ),
    )


def latest_review_for_paper(
    state: Mapping[str, Any], paper_artifact_id: str
) -> Dict[str, Any] | None:
    rows = [
        dict(row)
        for row in state.get("publication_reviews", [])
        if str(row.get("paper_artifact_id") or "") == paper_artifact_id
    ]
    rows.sort(
        key=lambda row: (
            int(row.get("round_number") or 0),
            int(row.get("state_revision") or 0),
            str(row.get("created_at") or ""),
        ),
        reverse=True,
    )
    return rows[0] if rows else None


def pending_route_error_review(state: Mapping[str, Any]) -> Dict[str, Any] | None:
    rows = [
        dict(row)
        for row in state.get("publication_reviews", [])
        if str(row.get("verdict") or "") == "major_proof_route_error"
        and not str(row.get("escalated_at") or "")
    ]
    rows.sort(key=lambda row: int(row.get("round_number") or 0), reverse=True)
    return rows[0] if rows else None


def mark_route_error_escalated(conn: sqlite3.Connection, review_id: str) -> str:
    at = utc_now()
    conn.execute(
        "UPDATE publication_reviews SET escalated_at = ? WHERE review_id = ?",
        (at, review_id),
    )
    return at


def publication_review_rows(conn: sqlite3.Connection) -> list[Dict[str, Any]]:
    return [
        compact_dict(row)
        for row in conn.execute(
            "SELECT * FROM publication_reviews ORDER BY round_number ASC, created_at ASC"
        ).fetchall()
    ]


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}
