from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from .models import fingerprint_text, normalize_text
from .store import ProofStateStore


CERTIFIED_MEMORY_VERSION = 1
_STOPWORDS = {
    "a", "an", "and", "are", "as", "be", "by", "for", "from", "has", "if",
    "in", "is", "it", "let", "of", "on", "or", "that", "the", "then", "to",
    "with", "all", "any", "every", "there", "exists", "such", "true",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", normalize_text(text))
        if len(token) > 2 and token not in _STOPWORDS
    }


def _similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _readonly_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA busy_timeout = 100")
    return conn


def _candidate_databases(store: ProofStateStore, *, limit: int) -> Iterable[Path]:
    results_root = store.generation_root / "results"
    if not results_root.is_dir():
        return []
    # Do not rglob through artifact/workflow trees: every problem directory has
    # a phase2 boundary, so stop descending as soon as that directory is seen.
    paths: list[Path] = []
    stack = [results_root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name == "phase2":
                candidate = Path(entry.path) / "proof_state.sqlite3"
                if candidate.is_file():
                    paths.append(candidate)
                continue
            stack.append(Path(entry.path))
    paths.sort(
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    return [path for path in paths if path.resolve() != store.db_path.resolve()][:limit]


def certified_cross_run_candidates(
    store: ProofStateStore,
    state: Mapping[str, Any] | None = None,
    *,
    limit: int = 5,
    database_limit: int = 64,
    minimum_similarity: float = 0.30,
) -> Dict[str, Any]:
    """Nominate certified theorems from other runs without importing them.

    The result is deliberately an index card, not evidence.  A theorem becomes
    usable in the target graph only through the existing explicit
    ``scope-import`` dependency-closure and verification path.
    """

    state = state or store.get_state()
    root_statement = str(state.get("problem_state", {}).get("root_statement") or "")
    root_fingerprint = fingerprint_text(root_statement)
    candidates: list[Dict[str, Any]] = []
    scanned = 0
    unreadable = 0
    for db_path in _candidate_databases(store, limit=database_limit):
        scanned += 1
        try:
            with closing(_readonly_connect(db_path)) as conn:
                problem = conn.execute(
                    "SELECT problem_id, root_statement, status, current_revision FROM problem_state LIMIT 1"
                ).fetchone()
                if problem is None:
                    continue
                rows = conn.execute(
                    """
                    SELECT claim_id, statement, fingerprint, validation_status,
                           lifecycle_status, evidence_artifact_ids_json
                    FROM claims
                    WHERE validation_status IN ('informally_verified', 'formally_verified')
                       OR lifecycle_status = 'integrated'
                    """
                ).fetchall()
        except (OSError, sqlite3.DatabaseError):
            unreadable += 1
            continue
        for row in rows:
            statement = str(row["statement"] or "")
            exact = str(row["fingerprint"] or "") == root_fingerprint
            score = 1.0 if exact else _similarity(root_statement, statement)
            if not exact and score < minimum_similarity:
                continue
            try:
                evidence_ids = json.loads(str(row["evidence_artifact_ids_json"] or "[]"))
            except (TypeError, ValueError):
                evidence_ids = []
            candidates.append(
                {
                    "source_problem_id": str(problem["problem_id"] or ""),
                    "source_claim_id": str(row["claim_id"] or ""),
                    "statement": statement,
                    "validation_status": str(row["validation_status"] or ""),
                    "lifecycle_status": str(row["lifecycle_status"] or ""),
                    "evidence_artifact_ids": [str(item) for item in evidence_ids if str(item)],
                    "exact_statement_fingerprint": exact,
                    "structural_similarity": round(score, 4),
                    "source_problem_status": str(problem["status"] or ""),
                    "source_revision": int(problem["current_revision"] or 0),
                    "verification_authority": False,
                    "explicit_scope_import_required": True,
                }
            )
    candidates.sort(
        key=lambda row: (
            not bool(row["exact_statement_fingerprint"]),
            -float(row["structural_similarity"]),
            str(row["source_problem_id"]),
            str(row["source_claim_id"]),
        )
    )
    return {
        "certified_memory_version": CERTIFIED_MEMORY_VERSION,
        "target_problem_id": store.problem_id,
        "target_statement_fingerprint": root_fingerprint,
        "candidates": candidates[:limit],
        "databases_scanned": scanned,
        "unreadable_databases": unreadable,
        "automatic_import": False,
        "verification_authority": False,
        "policy": (
            "Use this index only to avoid rediscovery and nominate an explicit scope-import; "
            "recheck statement identity, hypotheses, definitions, and dependency closure before reuse."
        ),
    }
