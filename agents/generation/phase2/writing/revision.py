from __future__ import annotations

"""Ingestion and state helpers for external-document writing revision.

An external manuscript is *writing input*, never proof evidence. The
``revision_document`` artifact therefore lives beside ``final_paper`` without
pretending that its mathematical claims have passed Albilich's proof gates.
The scheduler detects this artifact and runs only the writing-quality gate.
"""

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ..models import json_dumps, sha256_text, utc_now

WRITING_REVISION_RESEARCH_MODE = "writing_revision"
REVISION_DOCUMENT_ARTIFACT_TYPE = "revision_document"
REVISION_DOCUMENT_ARTIFACT_ID = "revision_document_root"
WRITING_REVISION_INGESTED_EVENT = "writing_revision_ingested"
SUPPORTED_REVISION_SUFFIXES = {".md": "md", ".tex": "tex"}
MAX_REVISION_DOCUMENT_BYTES = 2 * 1024 * 1024


def document_format_from_suffix(suffix: str) -> str:
    try:
        return SUPPORTED_REVISION_SUFFIXES[suffix.lower()]
    except KeyError as exc:
        allowed = ", ".join(sorted(SUPPORTED_REVISION_SUFFIXES))
        raise ValueError(f"unsupported writing document {suffix!r}; expected one of {allowed}") from exc


def revision_document_metadata(artifact: Mapping[str, Any]) -> Dict[str, Any]:
    raw = artifact.get("metadata_json", artifact.get("metadata", {}))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def revision_document_format(artifact: Mapping[str, Any]) -> str:
    metadata = revision_document_metadata(artifact)
    value = str(metadata.get("document_format") or "").strip().lower()
    return value if value in set(SUPPORTED_REVISION_SUFFIXES.values()) else ""


def latest_revision_document(state: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    rows = [
        row
        for row in list(state.get("final_artifacts", [])) + list(state.get("artifacts", []))
        if str(row.get("artifact_type") or "") == REVISION_DOCUMENT_ARTIFACT_TYPE
    ]
    if not rows:
        return None
    # Scheduler snapshots expose the row in final_artifacts; full snapshots
    # expose it in artifacts. Deduplicate before selecting the latest revision.
    by_id = {str(row.get("artifact_id") or ""): row for row in rows}
    return max(
        by_id.values(),
        key=lambda row: (int(row.get("state_revision") or 0), str(row.get("created_at") or "")),
    )


def is_writing_revision_state(state: Mapping[str, Any]) -> bool:
    return latest_revision_document(state) is not None


def _document_title(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("\\title") and "{" in stripped and "}" in stripped:
            inner = stripped.split("{", 1)[1].rsplit("}", 1)[0].strip()
            if inner:
                return inner
        if stripped.startswith("#"):
            inner = stripped.lstrip("#").strip()
            if inner:
                return inner
    return fallback


def writing_revision_root_statement(title: str) -> str:
    return (
        f"Revise the external manuscript {title!r} for mathematical exposition quality. "
        "Preserve its mathematical claims, notation, authorial voice, and source format; make only "
        "audited, diff-minimal writing changes. This is a writing revision, not proof verification: "
        "do not treat the submitted manuscript as a certified proof and do not strengthen its claims."
    )


def ingest_writing_revision(
    store: Any,
    document: Path,
    *,
    title: str = "",
    total_token_budget: int | None = None,
    reserved_verification_budget: int | None = None,
) -> Dict[str, Any]:
    """Create a fresh writing-only run from an external Markdown/LaTeX file."""

    document = Path(document).expanduser().resolve()
    if not document.is_file():
        raise FileNotFoundError(document)
    document_format = document_format_from_suffix(document.suffix)
    size = document.stat().st_size
    if size > MAX_REVISION_DOCUMENT_BYTES:
        raise ValueError(
            f"writing document is {size} bytes; maximum supported size is {MAX_REVISION_DOCUMENT_BYTES} bytes"
        )
    text = document.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("writing document is empty")
    with store.connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM problem_state WHERE problem_id = ? LIMIT 1",
            (store.problem_id,),
        ).fetchone()
    if existing is not None:
        raise ValueError(
            f"writing revision problem {store.problem_id!r} already exists; "
            "choose a new --problem-id rather than overwriting its source lineage"
        )
    resolved_title = title.strip() or _document_title(text, fallback=document.stem.replace("_", " "))
    root_statement = writing_revision_root_statement(resolved_title)
    init_kwargs: Dict[str, Any] = {}
    if total_token_budget is not None:
        init_kwargs["total_token_budget"] = total_token_budget
    if reserved_verification_budget is not None:
        init_kwargs["reserved_verification_budget"] = reserved_verification_budget
    store.init_problem(root_statement, **init_kwargs)
    store.set_completion_policy(
        "publication_ready",
        reason="external manuscript revision requires the writing quality gate",
        source="revise-paper",
    )

    original_sha256 = sha256_text(text)
    artifact_dir = store.state_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{REVISION_DOCUMENT_ARTIFACT_ID}{document.suffix.lower()}"
    stored_text = text if text.endswith("\n") else text + "\n"
    artifact_path.write_text(stored_text, encoding="utf-8")
    now = utc_now()
    metadata = {
        "source_file": str(document),
        "title": resolved_title,
        "document_format": document_format,
        "original_sha256": original_sha256,
        "revision_mode": True,
        "revision_number": 0,
        "diff_minimal": True,
        "voice_preserving": True,
        "mathematical_status": "not_verified_by_writing_harness",
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
                REVISION_DOCUMENT_ARTIFACT_ID,
                REVISION_DOCUMENT_ARTIFACT_TYPE,
                str(artifact_path),
                sha256_text(stored_text),
                revision,
                f"External {document_format} manuscript for writing revision: {resolved_title}"[:500],
                json_dumps(metadata),
                now,
            ),
        )
        store.write_event(
            conn,
            revision,
            WRITING_REVISION_INGESTED_EVENT,
            {
                "artifact_id": REVISION_DOCUMENT_ARTIFACT_ID,
                "title": resolved_title,
                "document_format": document_format,
                "original_sha256": original_sha256,
            },
        )
        conn.commit()
    return {
        "problem_id": store.problem_id,
        "artifact_id": REVISION_DOCUMENT_ARTIFACT_ID,
        "artifact_path": str(artifact_path),
        "title": resolved_title,
        "document_format": document_format,
        "original_sha256": original_sha256,
        "root_statement": root_statement,
        "research_mode": WRITING_REVISION_RESEARCH_MODE,
    }
