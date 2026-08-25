"""Non-blocking Human-Readable Mathematical Text snapshots.

Periodic HMT papers are presentation artifacts, not proof-state mutations.  This
module keeps their source, PDF, catalog, and usage outside the versioned proof
database so authoring cannot consume the research budget, advance the proof
revision, stale a research patch, or become the scheduler's primary action.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .budget import plan_step_budget
from .models import utc_now
from .receipt import compile_latex_artifact
from .store import ProofStateStore
from .writing.latex_template import normalize_paper_template

HMT_ARTIFACT_TYPE = "human_readable_mathematical_text"
HMT_INTEGRATED_CLAIM_INTERVAL_ENV = "ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL"
LEGACY_HMT_INTERVAL_ENV = "ALBILICH_HMT_REVISION_INTERVAL"
DEFAULT_HMT_INTEGRATED_CLAIM_INTERVAL = 10
CATALOG_VERSION = 2


def hmt_integrated_claim_interval() -> int:
    """Return the number of newly integrated claims between HMT snapshots.

    ``ALBILICH_HMT_REVISION_INTERVAL`` remains a compatibility alias so
    existing launchers that set it to ``0`` continue to disable the writer.
    """
    raw_interval = os.environ.get(HMT_INTEGRATED_CLAIM_INTERVAL_ENV, "").strip()
    if not raw_interval:
        raw_interval = os.environ.get(LEGACY_HMT_INTERVAL_ENV, "").strip()
    try:
        return (
            max(0, int(raw_interval))
            if raw_interval
            else DEFAULT_HMT_INTEGRATED_CLAIM_INTERVAL
        )
    except ValueError:
        return DEFAULT_HMT_INTEGRATED_CLAIM_INTERVAL


def integrated_claim_count(state: Mapping[str, Any]) -> int:
    return sum(
        1
        for claim in state.get("claims", [])
        if str(claim.get("lifecycle_status") or "") == "integrated"
    )


def _last_hmt_integrated_claim_count(
    prior_rows: list[Mapping[str, Any]],
) -> int:
    """Read the latest claim-count checkpoint, including catalog v1 rows.

    Catalog v1 recorded only a source revision.  That cannot be converted into
    an exact integrated-claim count.  Such a row therefore contributes no
    checkpoint; the first due v2 snapshot seeds the new claim-count cadence.
    This can produce one migration snapshot, but cannot suppress the writer
    indefinitely as the integrated-claim count grows.
    """
    recorded_counts = [
        int(row.get("source_integrated_claim_count") or 0)
        for row in prior_rows
        if row.get("source_integrated_claim_count") is not None
    ]
    return max(recorded_counts, default=0)


def hmt_sidecar_dir(store: ProofStateStore) -> Path:
    return store.state_dir / "hmt_snapshots"


def hmt_catalog_path(store: ProofStateStore) -> Path:
    return hmt_sidecar_dir(store) / "catalog.json"


def read_hmt_catalog(store: ProofStateStore) -> list[Dict[str, Any]]:
    """Return only catalog entries whose source and compiled PDF still exist."""
    path = hmt_catalog_path(store)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("papers", []) if isinstance(payload, Mapping) else []
    root = hmt_sidecar_dir(store).resolve()
    valid: list[Dict[str, Any]] = []
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        try:
            tex_path = Path(str(row.get("tex_path") or "")).resolve()
            pdf_path = Path(str(row.get("pdf_path") or "")).resolve()
            tex_path.relative_to(root)
            pdf_path.relative_to(root)
        except (OSError, ValueError):
            continue
        if not tex_path.is_file() or not pdf_path.is_file():
            continue
        row["tex_path"] = str(tex_path)
        row["pdf_path"] = str(pdf_path)
        valid.append(row)
    valid.sort(
        key=lambda row: (
            int(row.get("source_revision") or 0),
            int(row.get("sequence") or 0),
            str(row.get("created_at") or ""),
            str(row.get("artifact_id") or ""),
        )
    )
    return valid


def hmt_paper_by_id(store: ProofStateStore, artifact_id: str) -> Optional[Dict[str, Any]]:
    return next(
        (row for row in read_hmt_catalog(store) if str(row.get("artifact_id") or "") == artifact_id),
        None,
    )


def periodic_hmt_sidecar_action(
    store: ProofStateStore,
    *,
    requested_tokens: Optional[int] = None,
    research_mode: str = "hard_problem",
) -> Optional[Dict[str, Any]]:
    """Plan a due HMT without placing it on the proof scheduler's main lane."""
    interval = hmt_integrated_claim_interval()
    state = store.get_scheduler_state()
    problem = state["problem_state"]
    current_revision = int(problem.get("current_revision") or 0)
    current_integrated_claim_count = integrated_claim_count(state)
    if interval <= 0 or current_integrated_claim_count < interval:
        return None

    with store.connect() as conn:
        legacy_artifacts = [
            dict(row)
            for row in conn.execute(
                """
                SELECT artifact_type, state_revision, metadata_json
                FROM artifacts
                WHERE artifact_type = ?
                """,
                (HMT_ARTIFACT_TYPE,),
            ).fetchall()
        ]
    prior_rows: list[Mapping[str, Any]] = list(read_hmt_catalog(store))
    # Backward compatibility: papers accepted before the sidecar split also
    # count toward the cadence, but future sidecar papers never enter this DB.
    for artifact in legacy_artifacts:
        try:
            metadata = json.loads(str(artifact.get("metadata_json") or "{}"))
        except json.JSONDecodeError:
            metadata = {}
        prior_rows.append(
            {
                "source_revision": int(
                    metadata.get("source_revision") or artifact.get("state_revision") or 0
                ),
                "source_integrated_claim_count": metadata.get(
                    "source_integrated_claim_count"
                ),
            }
        )
    last_integrated_claim_count = _last_hmt_integrated_claim_count(prior_rows)
    if prior_rows and current_integrated_claim_count - last_integrated_claim_count < interval:
        return None

    sequence = len(prior_rows) + 1
    return {
        "mode": "write",
        "target_id": "root",
        "route_id": "",
        "reason": (
            "non-blocking HMT sidecar snapshot from accepted proof state "
            f"revision {current_revision}"
        ),
        "budget": plan_step_budget(problem, "write", requested_tokens),
        "research_mode": research_mode,
        "periodic_hmt": True,
        "hmt_sidecar": True,
        "human_readable_text_required": True,
        "hmt_source_revision": current_revision,
        "hmt_source_integrated_claim_count": current_integrated_claim_count,
        "hmt_sequence": sequence,
        "hmt_integrated_claim_interval": interval,
        "search_intent": "periodic_human_readable_mathematical_text",
    }


def publish_hmt_sidecar(
    store: ProofStateStore,
    *,
    action: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate and publish a completed writer result without touching SQLite."""
    if str(execution.get("status") or "") != "completed":
        return {"accepted": False, "errors": [str(execution.get("patch_error") or "writer did not complete")]}
    patch = execution.get("patch")
    if not isinstance(patch, Mapping):
        return {"accepted": False, "errors": [str(execution.get("patch_error") or "missing HMT patch")]}
    operations = [op for op in patch.get("operations", []) if isinstance(op, Mapping)]
    attachments = [op for op in operations if str(op.get("op") or "") == "attach_artifact"]
    unexpected = [op for op in operations if str(op.get("op") or "") != "attach_artifact"]
    if len(attachments) != 1 or unexpected:
        return {"accepted": False, "errors": ["HMT sidecar requires exactly one attach_artifact operation"]}
    attachment = attachments[0]
    if str(attachment.get("artifact_type") or "") != HMT_ARTIFACT_TYPE:
        return {"accepted": False, "errors": ["HMT sidecar attachment has the wrong artifact_type"]}

    staging_root = (store.state_dir / "artifacts" / "staging").resolve()
    try:
        source_path = Path(str(attachment.get("path") or "")).resolve()
        source_path.relative_to(staging_root)
    except (OSError, ValueError):
        return {"accepted": False, "errors": ["HMT source path is outside the approved staging directory"]}
    if source_path.suffix.lower() != ".tex" or not source_path.is_file():
        return {"accepted": False, "errors": ["HMT source path is not an existing .tex file"]}
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"accepted": False, "errors": [f"could not read HMT source: {exc}"]}
    source = normalize_paper_template(source)
    if "\\documentclass" not in source or "\\begin{document}" not in source or "\\end{document}" not in source:
        return {"accepted": False, "errors": ["HMT source is not a complete standalone LaTeX article"]}

    raw_id = str(attachment.get("artifact_id") or "hmt-snapshot")
    artifact_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw_id).strip(".-") or "hmt-snapshot"
    sidecar_dir = hmt_sidecar_dir(store)
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    tex_path = sidecar_dir / f"{artifact_id}.tex"
    pdf_path = sidecar_dir / f"{artifact_id}.pdf"
    tmp_path = tex_path.with_suffix(".tex.tmp")
    tmp_path.write_text(source, encoding="utf-8")
    os.replace(tmp_path, tex_path)
    compile_result = compile_latex_artifact(tex_path, pdf_path)
    if str(compile_result.get("pdf_status") or "") != "compiled" or not pdf_path.is_file():
        return {
            "accepted": False,
            "errors": ["HMT LaTeX did not compile"],
            "compile": dict(compile_result),
        }

    metadata = attachment.get("metadata") if isinstance(attachment.get("metadata"), Mapping) else {}
    source_revision = int(action.get("hmt_source_revision") or metadata.get("source_revision") or 0)
    source_integrated_claim_count = int(
        action.get("hmt_source_integrated_claim_count")
        or metadata.get("source_integrated_claim_count")
        or 0
    )
    integrated_claim_interval = int(
        action.get("hmt_integrated_claim_interval")
        or metadata.get("integrated_claim_interval")
        or DEFAULT_HMT_INTEGRATED_CLAIM_INTERVAL
    )
    sequence = int(action.get("hmt_sequence") or metadata.get("sequence") or 1)
    row = {
        "artifact_id": artifact_id,
        "artifact_type": HMT_ARTIFACT_TYPE,
        "title": str(metadata.get("title") or "Cumulative Human-Readable Mathematical Text"),
        "source_revision": source_revision,
        "source_integrated_claim_count": source_integrated_claim_count,
        "integrated_claim_interval": integrated_claim_interval,
        "sequence": sequence,
        "created_at": utc_now(),
        "tex_path": str(tex_path.resolve()),
        "pdf_path": str(pdf_path.resolve()),
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "content_summary": str(attachment.get("content_summary") or ""),
        "run_id": str(execution.get("run_id") or ""),
        "usage": dict(execution.get("usage") or {}),
        "non_certifying": True,
    }
    papers = [
        existing for existing in read_hmt_catalog(store)
        if str(existing.get("artifact_id") or "") != artifact_id
    ]
    papers.append(row)
    payload = {"catalog_version": CATALOG_VERSION, "papers": papers}
    catalog = hmt_catalog_path(store)
    catalog_tmp = catalog.with_suffix(".json.tmp")
    catalog_tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(catalog_tmp, catalog)
    return {"accepted": True, "paper": row, "proof_state_revision_unchanged": store.get_revision()}
