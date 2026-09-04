from __future__ import annotations

"""Human reference-solution ingestion for an existing theorem run.

The source is copied into runtime proof state as advisory material.  It never
changes a claim status and never bypasses the ordinary reconstruction, strict
verification, and integration gates.
"""

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

from .executable_attestation import (
    attest_executable_identity,
    attested_executable_unchanged,
)
from .bounded_io import read_bounded_bytes
from .models import SCHEMA_VERSION, sha256_text
from .research_strategy import REFERENCE_SOLUTION_ARTIFACT_TYPE
from .sandbox_runtime import SANDBOX_NPROC_LIMIT, append_runtime_mounts, sandbox_runtime_mounts

REFERENCE_SOLUTION_INGESTED_EVENT = "reference_solution_ingested"
SUPPORTED_TEXT_SUFFIXES = {".md", ".tex", ".txt"}
MAX_REFERENCE_DOCUMENT_BYTES = 64 * 1024 * 1024
MAX_REFERENCE_TEXT_BYTES = 8 * 1024 * 1024
MAX_REFERENCE_ERROR_BYTES = 64 * 1024
REFERENCE_EXTRACTION_TIMEOUT_SECONDS = 60


def _reference_text(
    document: Path,
    *,
    source_bytes: bytes | None = None,
) -> tuple[str, str]:
    if source_bytes is None:
        source_bytes = read_bounded_bytes(
            document,
            max_bytes=MAX_REFERENCE_DOCUMENT_BYTES,
            label="reference solution",
        )
    suffix = document.suffix.lower()
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        if len(source_bytes) > MAX_REFERENCE_TEXT_BYTES:
            raise ValueError(
                "reference solution text exceeds the "
                f"{MAX_REFERENCE_TEXT_BYTES}-byte extracted-text limit"
            )
        try:
            return source_bytes.decode("utf-8"), suffix
        except UnicodeDecodeError as exc:
            raise ValueError("reference solution text must be valid UTF-8") from exc
    if suffix == ".pdf":
        converter = shutil.which("pdftotext")
        if not converter:
            raise ValueError(
                "PDF reference solutions require the pdftotext executable; "
                "otherwise convert the source to Markdown, LaTeX, or plain text first"
            )
        bwrap = shutil.which("bwrap")
        prlimit = shutil.which("prlimit")
        if not bwrap or not prlimit:
            raise ValueError(
                "PDF reference extraction requires bubblewrap and prlimit for bounded isolation"
            )
        attestation = attest_executable_identity(converter)
        if not attestation.get("valid"):
            raise ValueError(
                "pdftotext executable attestation failed: "
                + str(attestation.get("error") or "unknown executable")
            )
        runtime_mounts, sandbox_converter, _runtime_root = sandbox_runtime_mounts(
            str(attestation["executable_path"]),
            mount_target="/albilich-pdftotext",
        )
        with (
            tempfile.TemporaryDirectory(
                prefix="albilich-reference-pdf-"
            ) as temporary_directory,
            tempfile.TemporaryFile() as stdout_file,
            tempfile.TemporaryFile() as stderr_file,
        ):
            source_directory = Path(temporary_directory)
            (source_directory / "input.pdf").write_bytes(source_bytes)
            command = [
                prlimit,
                "--as=1073741824",
                f"--cpu={REFERENCE_EXTRACTION_TIMEOUT_SECONDS}",
                f"--nproc={SANDBOX_NPROC_LIMIT}",
                f"--fsize={MAX_REFERENCE_TEXT_BYTES + 1}",
                "--",
                bwrap,
                "--die-with-parent",
                "--new-session",
                "--unshare-net",
                "--unshare-ipc",
                "--unshare-uts",
                "--unshare-pid",
                "--clearenv",
                "--setenv",
                "HOME",
                "/tmp",
                "--setenv",
                "PATH",
                "/usr/bin:/bin",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                "--ro-bind",
                str(source_directory),
                "/work",
                "--chdir",
                "/work",
            ]
            for directory in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
                if Path(directory).exists():
                    command.extend(["--ro-bind", directory, directory])
            append_runtime_mounts(command, runtime_mounts)
            command.extend(
                ["--", sandbox_converter, "-layout", "/work/input.pdf", "-"]
            )
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=REFERENCE_EXTRACTION_TIMEOUT_SECONDS,
                    env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ValueError(f"PDF reference extraction failed safely: {exc}") from exc
            stdout_file.seek(0)
            stderr_file.seek(0)
            output = stdout_file.read(MAX_REFERENCE_TEXT_BYTES + 1)
            error_output = stderr_file.read(MAX_REFERENCE_ERROR_BYTES + 1)
        if len(output) > MAX_REFERENCE_TEXT_BYTES:
            raise ValueError(
                "extracted PDF reference text exceeds the "
                f"{MAX_REFERENCE_TEXT_BYTES}-byte limit"
            )
        if len(error_output) > MAX_REFERENCE_ERROR_BYTES:
            raise ValueError("pdftotext diagnostic output exceeded its bounded limit")
        if not attested_executable_unchanged(attestation):
            raise ValueError("pdftotext executable changed during extraction")
        try:
            extracted = output.decode("utf-8")
            diagnostic = error_output.decode("utf-8", errors="replace").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("extracted PDF reference text is not valid UTF-8") from exc
        if completed.returncode != 0 or not extracted.strip():
            detail = diagnostic or "no extractable text"
            raise ValueError(f"could not extract PDF reference solution: {detail}")
        return extracted, ".txt"
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
    source_bytes = read_bounded_bytes(
        document,
        max_bytes=MAX_REFERENCE_DOCUMENT_BYTES,
        label="reference solution",
    )
    source_file_sha256 = hashlib.sha256(source_bytes).hexdigest()
    text, stored_suffix = _reference_text(document, source_bytes=source_bytes)
    stored_text = text if text.endswith("\n") else text + "\n"
    digest = sha256_text(stored_text)
    artifact_id = f"reference_solution_{digest[:16]}"

    resolved_title = title.strip() or document.stem.replace("_", " ").replace("-", " ")
    metadata = {
        "title": resolved_title,
        "source_statement": source_statement.strip(),
        "source_file": str(document),
        "source_format": document.suffix.lower().lstrip("."),
        "stored_format": stored_suffix.lstrip("."),
        "source_sha256": source_file_sha256,
        "source_digest_scope": "source_file_bytes",
        "extracted_text_sha256": sha256_text(text),
        "role": "human_reference_solution",
        "advisory_only": True,
        "verification_authority": False,
        "requires_local_reconstruction": True,
        "requires_strict_verifier": True,
    }
    created = False
    with store.connect() as conn:
        existing = conn.execute(
            "SELECT artifact_id, artifact_type, path FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if existing is not None and str(existing["artifact_type"] or "") != REFERENCE_SOLUTION_ARTIFACT_TYPE:
        raise ValueError(f"artifact id collision for reference solution {artifact_id}")
    if existing is None:
        from .patches import apply_operator_patch

        outcome = apply_operator_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": store.get_revision(),
                "actor_role": "human_operator",
                "target_id": artifact_id,
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": artifact_id,
                        "artifact_type": REFERENCE_SOLUTION_ARTIFACT_TYPE,
                        "content": stored_text,
                        "content_summary": f"Human-supplied reference solution: {resolved_title}"[:500],
                        "metadata": metadata,
                    }
                ],
                "evidence_artifact_ids": [],
                "rationale": "ingest a human-supplied advisory reference solution",
            },
        )
        if not outcome.accepted:
            raise RuntimeError("reference-solution patch rejected: " + "; ".join(outcome.errors))
        created = True
        with store.connect() as conn:
            store.write_event(
                conn,
                outcome.revision,
                REFERENCE_SOLUTION_INGESTED_EVENT,
                {
                    "artifact_id": artifact_id,
                    "title": resolved_title,
                    "source_file": str(document),
                    "verification_authority": False,
                    "patch_id": outcome.patch_id,
                },
            )
            conn.commit()
    with store.connect() as conn:
        artifact = conn.execute(
            "SELECT path FROM artifacts WHERE artifact_id = ?", (artifact_id,)
        ).fetchone()
    artifact_path = Path(str(artifact["path"]))
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
