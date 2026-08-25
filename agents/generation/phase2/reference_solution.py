from __future__ import annotations

"""Human reference-solution ingestion for an existing theorem run.

The source is copied into runtime proof state as advisory material.  It never
changes a claim status and never bypasses the ordinary reconstruction, strict
verification, and integration gates.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from .models import json_dumps, sha256_text, utc_now
from .research_strategy import REFERENCE_SOLUTION_ARTIFACT_TYPE

REFERENCE_SOLUTION_INGESTED_EVENT = "reference_solution_ingested"
SUPPORTED_TEXT_SUFFIXES = {".md", ".tex", ".txt"}


def _reference_text(document: Path) -> tuple[str, str]:
    suffix = document.suffix.lower()
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        return document.read_text(encoding="utf-8"), suffix
    if suffix == ".pdf":
        converter = shutil.which("pdftotext")
        if not converter:
            raise ValueError(
                "PDF reference solutions require the pdftotext executable; "
                "otherwise convert the source to Markdown, LaTeX, or plain text first"
            )
        completed = subprocess.run(
            [converter, "-layout", str(document), "-"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            detail = completed.stderr.strip() or "no extractable text"
            raise ValueError(f"could not extract PDF reference solution: {detail}")
        return completed.stdout, ".txt"
    raise ValueError("reference solution must be .md, .tex, .txt, or a text-extractable .pdf")


def ingest_reference_solution(
    store: Any,
    document: Path,
    *,
    title: str = "",
    source_statement: str = "",
) -> Dict[str, Any]:
    document = Path(document).expanduser().resolve()
    if not document.is_file():
        raise ValueError(f"reference solution does not exist: {document}")
    text, stored_suffix = _reference_text(document)
    digest = sha256_text(text)
    artifact_id = f"reference_solution_{digest[:16]}"
    artifact_dir = store.state_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{artifact_id}{stored_suffix}"
    if not artifact_path.exists():
        artifact_path.write_text(text, encoding="utf-8")

    resolved_title = title.strip() or document.stem.replace("_", " ").replace("-", " ")
    metadata = {
        "title": resolved_title,
        "source_statement": source_statement.strip(),
        "source_file": str(document),
        "source_format": document.suffix.lower().lstrip("."),
        "stored_format": stored_suffix.lstrip("."),
        "role": "human_reference_solution",
        "advisory_only": True,
        "verification_authority": False,
        "requires_local_reconstruction": True,
        "requires_strict_verifier": True,
    }
    now = utc_now()
    created = False
    with store.connect() as conn:
        problem = store.get_problem_row(conn)
        revision = int(problem["current_revision"])
        existing = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if not existing:
            conn.execute(
                """
                INSERT INTO artifacts(
                    artifact_id, artifact_type, path, sha256, producer_role, run_id,
                    state_revision, content_summary, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, 'human_operator', '', ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    REFERENCE_SOLUTION_ARTIFACT_TYPE,
                    str(artifact_path),
                    digest,
                    revision,
                    f"Human-supplied reference solution: {resolved_title}"[:500],
                    json_dumps(metadata),
                    now,
                ),
            )
            store.write_event(
                conn,
                revision,
                REFERENCE_SOLUTION_INGESTED_EVENT,
                {
                    "artifact_id": artifact_id,
                    "title": resolved_title,
                    "source_file": str(document),
                    "verification_authority": False,
                },
            )
            created = True
        conn.commit()
    return {
        "problem_id": store.problem_id,
        "artifact_id": artifact_id,
        "artifact_path": str(artifact_path),
        "title": resolved_title,
        "created": created,
        "advisory_only": True,
        "verification_authority": False,
        "next_action": "reference_solution_reconstruction",
    }
