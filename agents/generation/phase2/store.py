from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import (
    CLAIM_KINDS,
    COMPLETION_POLICIES,
    DEFAULT_COMPLETION_POLICY,
    LIFECYCLE_STATUSES,
    ROUTE_RELATIONS,
    ROUTE_STATUSES,
    RUN_STATUSES,
    SCHEMA_VERSION,
    VALIDATION_STATUSES,
    compact_dict,
    fingerprint_text,
    normalize_text,
    json_dumps,
    json_loads,
    sanitize_problem_id,
    sha256_text,
    utc_now,
)

GENERATION_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = GENERATION_ROOT / "results"


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        suppress = super().__exit__(exc_type, exc, tb)
        self.close()
        return bool(suppress)


def phase2_dir(problem_id: str, *, generation_root: Path = GENERATION_ROOT) -> Path:
    safe_id = sanitize_problem_id(problem_id)
    path = generation_root / "results" / safe_id / "phase2"
    root = (generation_root / "results").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("problem_id resolves outside results root")
    return resolved


class ProofStateStore:
    """Versioned SQLite proof-state store.

    The store is the authoritative Albilich v1 state. Existing JSONL memory remains
    an evidence/archive layer.
    """

    def __init__(self, problem_id: str, *, generation_root: Optional[Path] = None, auto_snapshot: bool = False) -> None:
        self.problem_id = sanitize_problem_id(problem_id)
        self.generation_root = generation_root or GENERATION_ROOT
        self.state_dir = phase2_dir(self.problem_id, generation_root=self.generation_root)
        self.db_path = self.state_dir / "proof_state.sqlite3"
        self.snapshot_path = self.state_dir / "proof_state_snapshot.json"
        self.auto_snapshot = auto_snapshot

    def connect(self) -> sqlite3.Connection:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, factory=_ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        self.migrate(conn)
        return conn

    def migrate(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS problem_state (
                problem_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                current_revision INTEGER NOT NULL,
                root_statement TEXT NOT NULL,
                status TEXT NOT NULL,
                total_token_budget INTEGER NOT NULL,
                remaining_token_budget INTEGER NOT NULL,
                reserved_verification_budget INTEGER NOT NULL,
                max_reduction_depth INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS claims (
                claim_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                statement TEXT NOT NULL,
                normalized_statement TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                hypotheses TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                lifecycle_status TEXT NOT NULL,
                root_impact REAL NOT NULL,
                reduction_depth INTEGER NOT NULL,
                parent_ids_json TEXT NOT NULL,
                source_ids_json TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS routes (
                route_id TEXT PRIMARY KEY,
                conclusion_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
                label TEXT NOT NULL,
                strategy TEXT NOT NULL,
                status TEXT NOT NULL,
                relation_to_parent TEXT NOT NULL,
                assumptions_json TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                failure_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inferences (
                inference_id TEXT PRIMARY KEY,
                route_id TEXT NOT NULL REFERENCES routes(route_id),
                conclusion_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
                explanation TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                condition_claim_ids_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inference_premises (
                inference_id TEXT NOT NULL REFERENCES inferences(inference_id) ON DELETE CASCADE,
                premise_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
                position INTEGER NOT NULL,
                PRIMARY KEY (inference_id, premise_claim_id)
            );
            CREATE TABLE IF NOT EXISTS debts (
                debt_id TEXT PRIMARY KEY,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                obligation TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                debt_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                repeated_count INTEGER NOT NULL,
                source_artifact_ids_json TEXT NOT NULL,
                suggested_next_target TEXT NOT NULL,
                resolution_evidence_json TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_debts_owner_fingerprint
                ON debts(owner_type, owner_id, fingerprint);
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                producer_role TEXT NOT NULL,
                run_id TEXT NOT NULL,
                state_revision INTEGER NOT NULL,
                content_summary TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                actor_role TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL,
                target_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                state_revision INTEGER NOT NULL,
                context_revision INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                model_profile TEXT NOT NULL,
                model TEXT NOT NULL,
                reasoning_effort TEXT NOT NULL,
                search_setting TEXT NOT NULL,
                search_intent TEXT NOT NULL DEFAULT '',
                sandbox_setting TEXT NOT NULL,
                budget_requested INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                cached_input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                reasoning_output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                wall_time_seconds REAL NOT NULL,
                peak_memory_mb REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL,
                prompt_context_hash TEXT NOT NULL,
                output_artifact_ids_json TEXT NOT NULL,
                error_artifact_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patches (
                patch_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                problem_id TEXT NOT NULL,
                base_revision INTEGER NOT NULL,
                actor_role TEXT NOT NULL,
                target_id TEXT NOT NULL,
                operations_json TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                rationale TEXT NOT NULL,
                status TEXT NOT NULL,
                rejection_reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                applied_revision INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                revision INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS retrieval_cards (
                card_id TEXT PRIMARY KEY,
                normalized_query TEXT NOT NULL,
                source_version TEXT NOT NULL,
                exact_statement TEXT NOT NULL,
                source_identifiers_json TEXT NOT NULL,
                hypotheses_json TEXT NOT NULL,
                local_definitions_json TEXT NOT NULL,
                applicability_json TEXT NOT NULL,
                missing_hypotheses_json TEXT NOT NULL,
                source_location TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                retrieved_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS theorem_library_entries (
                entry_id TEXT PRIMARY KEY,
                statement TEXT NOT NULL,
                normalized_statement TEXT NOT NULL,
                source_identifiers_json TEXT NOT NULL,
                source_version TEXT NOT NULL,
                source_location TEXT NOT NULL,
                certification_type TEXT NOT NULL,
                relation_to_target TEXT NOT NULL,
                evidence_artifact_ids_json TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._ensure_column(conn, "runs", "search_intent", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "actor_role", "TEXT NOT NULL DEFAULT ''")
        # Whole-run control state (2026-07-09 TODO 5): running | dashboard_paused |
        # pause_requested | paused | stopping | stopped | completed.
        self._ensure_column(conn, "problem_state", "run_status", "TEXT NOT NULL DEFAULT 'running'")
        # Run-level completion policy (2026-07-09 TODO 7): full_proof_first |
        # partial_ok | exploratory. Only the explicit CLI flag changes it; soft
        # wording in the problem markdown never flips it.
        self._ensure_column(conn, "problem_state", "completion_policy", "TEXT NOT NULL DEFAULT 'full_proof_first'")
        # Parallel branch research mode (2026-07-09 TODO 2): worker count for
        # the multi_branch_research work mode (0 = off, 2..5 = on) plus the
        # recorded mode name; set only by the explicit --parallel-branches flag.
        self._ensure_column(conn, "problem_state", "parallel_branches", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "problem_state", "research_parallel_mode", "TEXT NOT NULL DEFAULT ''")
        total_tokens_added = self._ensure_column(conn, "runs", "total_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "runs", "peak_memory_mb", "REAL NOT NULL DEFAULT 0.0")
        self._ensure_column(conn, "runs", "researcher_work_mode", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "work_mode_source", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "runs", "failure_kind", "TEXT NOT NULL DEFAULT ''")
        if total_tokens_added:
            # One-time backfill when the column first appears; running it on
            # every connect was wasted work.
            conn.execute(
                """
                UPDATE runs
                SET total_tokens = input_tokens + output_tokens + reasoning_output_tokens
                WHERE total_tokens <= 0
                """
            )
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_claims_fingerprint
                ON claims(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_artifacts_type_role_sha
                ON artifacts(artifact_type, producer_role, sha256);
            CREATE INDEX IF NOT EXISTS idx_retrieval_content_hash
                ON retrieval_cards(content_hash);
            CREATE INDEX IF NOT EXISTS idx_theorem_library_statement
                ON theorem_library_entries(normalized_statement);
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, utc_now()),
        )
        conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> bool:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            return True
        return False

    def init_problem(
        self,
        root_statement: str,
        *,
        total_token_budget: int = 80_000_000,
        reserved_verification_budget: int = 12_000_000,
        max_reduction_depth: int = 4,
    ) -> Dict[str, Any]:
        if not root_statement.strip():
            raise ValueError("root_statement must be non-empty")
        now = utc_now()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT root_statement FROM problem_state WHERE problem_id = ?", (self.problem_id,)
            ).fetchone()
            if existing:
                if existing["root_statement"] != root_statement:
                    raise ValueError("root theorem statement is immutable and differs from existing state")
            else:
                conn.execute(
                    """
                    INSERT INTO problem_state(
                        problem_id, schema_version, current_revision, root_statement, status,
                        total_token_budget, remaining_token_budget, reserved_verification_budget,
                        max_reduction_depth, created_at, updated_at
                    ) VALUES (?, ?, 0, ?, 'active', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.problem_id,
                        SCHEMA_VERSION,
                        root_statement,
                        total_token_budget,
                        total_token_budget,
                        reserved_verification_budget,
                        max_reduction_depth,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO claims(
                        claim_id, kind, statement, normalized_statement, fingerprint, hypotheses,
                        conditions_json, validation_status, lifecycle_status, root_impact,
                        reduction_depth, parent_ids_json, source_ids_json, tags_json,
                        evidence_artifact_ids_json, created_at, updated_at
                    ) VALUES (?, 'theorem', ?, ?, ?, '', '[]', 'untested', 'active', 1.0, 0, '[]', '[]', ?, '[]', ?, ?)
                    """,
                    (
                        "root",
                        root_statement,
                        normalize_text(root_statement),
                        fingerprint_text(root_statement),
                        json_dumps(["root"]),
                        now,
                        now,
                    ),
                )
                conn.execute(
                    "INSERT INTO events(revision, event_type, payload_json, created_at) VALUES (0, 'init', ?, ?)",
                    (json_dumps({"problem_id": self.problem_id}), now),
                )
            conn.commit()
        self._ensure_sidecar_files()
        if self.auto_snapshot:
            self.write_snapshot()
        return self.get_state()

    def _ensure_sidecar_files(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("parallel_exchange.jsonl",):
            path = self.state_dir / filename
            path.touch(exist_ok=True)

    def get_scheduler_state(self) -> Dict[str, Any]:
        """Return only the rows needed for deterministic scheduling.

        The full proof state remains available through get_state() and SQLite.
        Scheduler decisions do not need artifact metadata or full retrieval-card
        bodies, so this avoids materializing bulky research/log state on every
        workflow step.
        """
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            claims = self.fetch_all(conn, "claims")
            routes = self.fetch_all(conn, "routes")
            inferences = self.fetch_all(conn, "inferences")
            debts = [compact_dict(row) for row in conn.execute("SELECT * FROM debts WHERE status = 'active'").fetchall()]
            premises = self.fetch_all(conn, "inference_premises")
            retrieval_cards = [
                compact_dict(row)
                for row in conn.execute(
                    "SELECT card_id, applicability_json, exact_statement, missing_hypotheses_json FROM retrieval_cards"
                ).fetchall()
            ]
            theorem_library_entries = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT entry_id, statement, source_identifiers_json, source_version,
                           source_location, certification_type, relation_to_target,
                           evidence_artifact_ids_json, tags_json
                    FROM theorem_library_entries
                    ORDER BY updated_at DESC, entry_id ASC
                    LIMIT 32
                    """
                ).fetchall()
            ]
            final_artifacts = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, artifact_type, path, state_revision, metadata_json, created_at
                    FROM artifacts
                    WHERE artifact_type IN ('final_proof', 'verified_blueprint', 'final_paper', 'revision_document')
                    ORDER BY created_at DESC
                    """
                ).fetchall()
            ]
            research_artifacts = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, artifact_type, producer_role, state_revision,
                           content_summary, metadata_json, path, created_at
                    FROM artifacts
                    WHERE artifact_type IN (
                        'proof_dossier',
                        'proof_blueprint',
                        'research_notebook',
                        'research_diagnostic',
                        'candidate_counterexample',
                        'route_obstruction',
                        'hypothesis_gap',
                        'construction_failure',
                        'necessary_condition',
                        'literature_search_request',
                        'decomposition_plan',
                        'failed_decomposition_plan',
                        'key_failure_analysis',
                        'source_adaptation_notes',
                        'source_synthesis_report',
                        'cas_experiment_report',
                        'definition_audit_report',
                        'route_triage_report',
                        'advisor_report',
                        'advisor_synthesis',
                        'bridge_lemma_search',
                        'conjecture_portfolio',
                        'deep_session_report',
                        'definition_candidate',
                        'invention_authorization',
                        'proof_compression'
                    )
                    ORDER BY state_revision DESC, created_at DESC
                    LIMIT 48
                    """
                ).fetchall()
            ]
            # Global synthesis is intentionally infrequent, so its latest
            # artifact can fall outside the recent-artifact window.  Keep it
            # in scheduler state: the next advisor must see the exact artifact
            # id that the database lineage guard requires it to supersede.
            latest_advisor_synthesis = conn.execute(
                """
                SELECT artifact_id, artifact_type, producer_role, state_revision,
                       content_summary, metadata_json, path, created_at
                FROM artifacts
                WHERE artifact_type = 'advisor_synthesis'
                ORDER BY state_revision DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()
            if latest_advisor_synthesis and not any(
                row["artifact_id"] == latest_advisor_synthesis["artifact_id"]
                for row in research_artifacts
            ):
                research_artifacts.append(compact_dict(latest_advisor_synthesis))
            confirmed_counterexamples = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, artifact_type, producer_role, state_revision,
                           content_summary, metadata_json, path, created_at
                    FROM artifacts
                    WHERE artifact_type = 'confirmed_counterexample'
                    ORDER BY state_revision DESC, created_at DESC
                    """
                ).fetchall()
            ]
            audit_artifacts = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT artifact_id, artifact_type, producer_role, state_revision,
                           content_summary, metadata_json, path, created_at
                    FROM artifacts
                    WHERE artifact_type IN (
                        'audit_subject', 'verification_report', 'integration_report', 'referee_report'
                    )
                    ORDER BY state_revision DESC, created_at DESC
                    """
                ).fetchall()
            ]
            runs = [
                compact_dict(row)
                for row in conn.execute("SELECT mode, search_intent FROM runs WHERE mode = 'retrieve'").fetchall()
            ]
            recent_runs = [
                compact_dict(row)
                for row in conn.execute(
                    """
                    SELECT r.run_id, r.actor_role, r.mode, r.target_id, r.route_id, r.state_revision,
                           r.status, r.search_intent, r.search_setting, r.researcher_work_mode,
                           r.work_mode_source, r.failure_kind, r.output_artifact_ids_json, r.total_tokens,
                           r.error_artifact_id, COALESCE(a.content_summary, '') AS error_summary,
                           r.created_at
                    FROM runs r
                    LEFT JOIN artifacts a ON a.artifact_id = r.error_artifact_id
                    ORDER BY r.created_at DESC
                    LIMIT 96
                    """
                ).fetchall()
            ]
            run_count = int(conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"])

        premise_map: Dict[str, List[str]] = {}
        for item in sorted(premises, key=lambda x: (x["inference_id"], x["position"])):
            premise_map.setdefault(item["inference_id"], []).append(item["premise_claim_id"])
        for inf in inferences:
            inf["premise_claim_ids"] = premise_map.get(inf["inference_id"], [])

        return {
            "problem_state": state,
            "claims": claims,
            "routes": routes,
            "inferences": inferences,
            "debts": debts,
            "runs": runs,
            "recent_runs": recent_runs,
            "run_count": run_count,
            "retrieval_cards": retrieval_cards,
            "theorem_library_entries": theorem_library_entries,
            "final_artifacts": final_artifacts,
            "research_artifacts": research_artifacts,
            "confirmed_counterexamples": confirmed_counterexamples,
            "audit_artifacts": audit_artifacts,
        }

    def get_revision(self, conn: Optional[sqlite3.Connection] = None) -> int:
        close = conn is None
        conn = conn or self.connect()
        try:
            row = conn.execute(
                "SELECT current_revision FROM problem_state WHERE problem_id = ?", (self.problem_id,)
            ).fetchone()
            if row is None:
                raise ValueError("problem state is not initialized")
            return int(row["current_revision"])
        finally:
            if close:
                conn.close()

    def get_problem_row(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        row = conn.execute("SELECT * FROM problem_state WHERE problem_id = ?", (self.problem_id,)).fetchone()
        if row is None:
            raise ValueError("problem state is not initialized")
        return compact_dict(row)

    def fetch_all(self, conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
        return [compact_dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]

    def get_state(self) -> Dict[str, Any]:
        with self.connect() as conn:
            return self.snapshot_from_conn(conn)

    def snapshot_from_conn(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        state = self.get_problem_row(conn)
        claims = self.fetch_all(conn, "claims")
        routes = self.fetch_all(conn, "routes")
        inferences = self.fetch_all(conn, "inferences")
        debts = self.fetch_all(conn, "debts")
        artifacts = self.fetch_all(conn, "artifacts")
        runs = self.fetch_all(conn, "runs")
        cards = self.fetch_all(conn, "retrieval_cards")
        library_entries = self.fetch_all(conn, "theorem_library_entries")
        premises = self.fetch_all(conn, "inference_premises")

        premise_map: Dict[str, List[str]] = {}
        for item in sorted(premises, key=lambda x: (x["inference_id"], x["position"])):
            premise_map.setdefault(item["inference_id"], []).append(item["premise_claim_id"])
        for inf in inferences:
            inf["premise_claim_ids"] = premise_map.get(inf["inference_id"], [])

        return {
            "problem_state": state,
            "claims": claims,
            "routes": routes,
            "inferences": inferences,
            "debts": debts,
            "artifacts": artifacts,
            "runs": runs,
            "retrieval_cards": cards,
            "theorem_library_entries": library_entries,
        }

    def write_snapshot(self) -> Dict[str, Any]:
        snapshot = self.get_state()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        return snapshot

    def write_event(self, conn: sqlite3.Connection, revision: int, event_type: str, payload: Dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO events(revision, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (revision, event_type, json_dumps(payload), utc_now()),
        )

    def row_exists(self, conn: sqlite3.Connection, table: str, key: str, value: str) -> bool:
        row = conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (value,)).fetchone()
        return row is not None

    def get_claim(self, conn: sqlite3.Connection, claim_id: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        return compact_dict(row) if row else None

    def get_route(self, conn: sqlite3.Connection, route_id: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM routes WHERE route_id = ?", (route_id,)).fetchone()
        return compact_dict(row) if row else None

    def get_artifact(self, conn: sqlite3.Connection, artifact_id: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        return compact_dict(row) if row else None

    def active_blocking_debts(self, conn: sqlite3.Connection, owner_ids: Sequence[str]) -> List[Dict[str, Any]]:
        if not owner_ids:
            return []
        placeholders = ",".join("?" for _ in owner_ids)
        rows = conn.execute(
            f"SELECT * FROM debts WHERE owner_id IN ({placeholders}) AND status = 'active' AND severity = 'blocking'",
            list(owner_ids),
        ).fetchall()
        return [compact_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Completion policy (2026-07-09 TODO 7): run-level full-proof-first vs
    # partial-results policy persisted on problem_state.
    # ------------------------------------------------------------------

    def get_completion_policy(self, conn: Optional[sqlite3.Connection] = None) -> str:
        close = conn is None
        conn = conn or self.connect()
        try:
            row = conn.execute(
                "SELECT completion_policy FROM problem_state WHERE problem_id = ?", (self.problem_id,)
            ).fetchone()
            if row is None:
                raise ValueError("problem state is not initialized")
            return str(row["completion_policy"] or DEFAULT_COMPLETION_POLICY)
        finally:
            if close:
                conn.close()

    def set_completion_policy(self, policy: str, *, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Persist the explicit run-level completion policy and record an event.

        Only this explicit setter changes the policy; soft wording in the
        problem markdown never flips it.
        """
        if policy not in COMPLETION_POLICIES:
            allowed = ", ".join(sorted(COMPLETION_POLICIES))
            raise ValueError(f"invalid completion_policy: {policy}; expected one of {allowed}")
        now = utc_now()
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            previous = str(state.get("completion_policy") or DEFAULT_COMPLETION_POLICY)
            if previous == policy:
                return {"problem_id": self.problem_id, "previous": previous, "completion_policy": policy, "unchanged": True}
            conn.execute(
                "UPDATE problem_state SET completion_policy = ?, updated_at = ? WHERE problem_id = ?",
                (policy, now, self.problem_id),
            )
            self.write_event(
                conn,
                int(state["current_revision"]),
                "completion_policy",
                {"from": previous, "to": policy, "reason": reason, "source": source},
            )
            conn.commit()
        return {"problem_id": self.problem_id, "previous": previous, "completion_policy": policy, "at": now}

    # ------------------------------------------------------------------
    # Parallel branch mode (2026-07-09 TODO 2): explicit multi_branch_research
    # worker count persisted on problem_state.
    # ------------------------------------------------------------------

    def set_parallel_branches(self, workers: int, *, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Persist the multi_branch_research worker count (0 off, 2..5 on).

        Records the mode name on problem_state.research_parallel_mode and a
        parallel_branch_mode event; a no-op when the value is unchanged.
        """
        workers = int(workers or 0)
        if workers != 0 and not (2 <= workers <= 5):
            raise ValueError("parallel_branches must be 0 (off) or between 2 and 5")
        mode = "multi_branch_research" if workers >= 2 else ""
        now = utc_now()
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            previous = int(state.get("parallel_branches") or 0)
            if previous == workers:
                return {
                    "problem_id": self.problem_id,
                    "previous": previous,
                    "parallel_branches": workers,
                    "research_parallel_mode": mode,
                    "unchanged": True,
                }
            conn.execute(
                "UPDATE problem_state SET parallel_branches = ?, research_parallel_mode = ?, updated_at = ? "
                "WHERE problem_id = ?",
                (workers, mode, now, self.problem_id),
            )
            self.write_event(
                conn,
                int(state["current_revision"]),
                "parallel_branch_mode",
                {"from": previous, "to": workers, "mode": mode, "reason": reason, "source": source},
            )
            conn.commit()
        return {
            "problem_id": self.problem_id,
            "previous": previous,
            "parallel_branches": workers,
            "research_parallel_mode": mode,
            "at": now,
        }

    # ------------------------------------------------------------------
    # Run control (2026-07-09 TODO 5): persisted pause/stop semantics and
    # wall-clock vs active-compute vs paused-time accounting.
    # ------------------------------------------------------------------

    def get_run_status(self, conn: Optional[sqlite3.Connection] = None) -> str:
        close = conn is None
        conn = conn or self.connect()
        try:
            row = conn.execute(
                "SELECT run_status FROM problem_state WHERE problem_id = ?", (self.problem_id,)
            ).fetchone()
            if row is None:
                raise ValueError("problem state is not initialized")
            return str(row["run_status"] or "running")
        finally:
            if close:
                conn.close()

    def peek_run_control(self) -> Dict[str, Any]:
        """Cheap, migration-free read of the current run-control state.

        Safe to poll from a watcher thread while a child session runs: it never
        migrates, never raises, and returns {} when the state is unreadable
        (e.g. run_status column not yet migrated).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT run_status FROM problem_state WHERE problem_id = ?", (self.problem_id,)
                ).fetchone()
                if row is None:
                    return {}
                event = conn.execute(
                    "SELECT payload_json FROM events WHERE event_type = 'run_control' ORDER BY event_id DESC LIMIT 1"
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return {}
        payload = json_loads(event["payload_json"] if event else None, {})
        if not isinstance(payload, dict):
            payload = {}
        return {"run_status": str(row["run_status"] or "running"), "hard": bool(payload.get("hard"))}

    def set_run_status(
        self,
        new_status: str,
        *,
        reason: str = "",
        source: str = "cli",
        hard: bool = False,
    ) -> Dict[str, Any]:
        """Transition problem_state.run_status and record a run_control event."""
        if new_status not in RUN_STATUSES:
            raise ValueError(f"invalid run_status: {new_status}")
        now = utc_now()
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            previous = str(state.get("run_status") or "running")
            conn.execute(
                "UPDATE problem_state SET run_status = ?, updated_at = ? WHERE problem_id = ?",
                (new_status, now, self.problem_id),
            )
            payload = {
                "from": previous,
                "to": new_status,
                "reason": reason,
                "source": source,
                "hard": bool(hard),
            }
            self.write_event(conn, int(state["current_revision"]), "run_control", payload)
            conn.commit()
        return {"problem_id": self.problem_id, "previous": previous, "run_status": new_status, "at": now}

    def request_pause(self, *, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Soft pause: the workflow finishes the current child session, then
        stops dispatching new actions and parks the run as 'paused'."""
        current = self.get_run_status()
        if current in {"paused", "pause_requested"}:
            return {"problem_id": self.problem_id, "previous": current, "run_status": current, "unchanged": True}
        return self.set_run_status(
            "pause_requested",
            reason=reason or "run pause requested; finish the current child session, then stop dispatching",
            source=source,
        )

    def resume_run(self, *, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Clear a pause/stop so the workflow may continue from the latest
        accepted proof-state revision."""
        current = self.get_run_status()
        if current == "running":
            return {"problem_id": self.problem_id, "previous": current, "run_status": current, "unchanged": True}
        return self.set_run_status(
            "running",
            reason=reason or f"run resumed from {current}; continuing from the latest accepted proof-state revision",
            source=source,
        )

    def request_stop(self, *, hard: bool = False, reason: str = "", source: str = "cli") -> Dict[str, Any]:
        """Stop the run. Soft stop finishes the current child session first;
        hard stop also terminates the active child session (the workflow's
        run-control watcher observes 'stopping' with hard=True) and records an
        interruption event artifact."""
        result = self.set_run_status(
            "stopping",
            reason=reason or ("hard stop requested" if hard else "soft stop requested"),
            source=source,
            hard=hard,
        )
        if hard:
            result["interruption_artifact_id"] = self.record_interruption_artifact(
                reason=reason or "hard stop requested; active child sessions terminated",
                source=source,
            )
        return result

    def record_interruption_artifact(self, *, reason: str, source: str = "cli") -> str:
        """Record a clean interruption event artifact for a hard stop."""
        now = utc_now()
        stamp = now.replace(":", "").replace("-", "").replace("+0000", "Z").replace(".", "_")
        artifact_id = f"run_interruption_{stamp}"
        content = (
            f"# Run interruption event\n\n"
            f"- problem_id: {self.problem_id}\n"
            f"- at: {now}\n"
            f"- source: {source}\n"
            f"- reason: {reason}\n\n"
            "The active child session (if any) was terminated by a hard stop request. "
            "The proof state is unaffected; resume continues from the latest accepted revision.\n"
        )
        artifact_dir = self.state_dir / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"{artifact_id}.md"
        path.write_text(content, encoding="utf-8")
        with self.connect() as conn:
            revision = int(self.get_problem_row(conn)["current_revision"])
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts(
                    artifact_id, artifact_type, path, sha256, producer_role, run_id,
                    state_revision, content_summary, metadata_json, created_at
                ) VALUES (?, 'run_interruption_event', ?, ?, 'human_operator', '', ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    str(path),
                    sha256_text(content),
                    revision,
                    f"Hard stop interruption: {reason}"[:500],
                    json_dumps({"reason": reason, "source": source}),
                    now,
                ),
            )
            self.write_event(conn, revision, "run_interrupted", {"artifact_id": artifact_id, "reason": reason, "source": source})
            conn.commit()
        return artifact_id

    def get_run_timing(self) -> Dict[str, Any]:
        """Three separated timing numbers for reports/benchmarks.

        - wall_clock_seconds: elapsed from problem init to the last recorded
          activity (or now while the run is live).
        - active_compute_seconds: recorded child-session wall time (the runs
          table); scheduler overhead is deliberately not attributed here.
        - paused_seconds: total time inside explicit paused intervals derived
          from run_control events (paused -> next non-paused transition).
        """
        with self.connect() as conn:
            state = self.get_problem_row(conn)
            events = [
                compact_dict(row)
                for row in conn.execute(
                    "SELECT event_id, event_type, payload_json, created_at FROM events "
                    "WHERE event_type IN ('run_control', 'run_interrupted') ORDER BY event_id ASC"
                ).fetchall()
            ]
            runs_wall = conn.execute(
                "SELECT COALESCE(SUM(wall_time_seconds), 0.0) AS total FROM runs"
            ).fetchone()["total"]
            last_activity = conn.execute("SELECT MAX(created_at) AS latest FROM events").fetchone()["latest"]

        run_status = str(state.get("run_status") or "running")
        started_at = _parse_timestamp(str(state.get("created_at") or ""))
        now = datetime.now(timezone.utc)
        if run_status in {"stopped", "awaiting_human", "completed"}:
            end_candidates = [
                _parse_timestamp(str(last_activity or "")),
                _parse_timestamp(str(state.get("updated_at") or "")),
            ]
            end_time = max((ts for ts in end_candidates if ts is not None), default=now)
        else:
            end_time = now

        paused_seconds = 0.0
        pause_count = 0
        pause_started: Optional[datetime] = None
        control_events: List[Dict[str, Any]] = []
        for event in events:
            payload = json_loads(event.get("payload_json"), {})
            if not isinstance(payload, dict):
                payload = {}
            created = _parse_timestamp(str(event.get("created_at") or ""))
            control_events.append(
                {
                    "event_type": str(event.get("event_type") or ""),
                    "from": str(payload.get("from") or ""),
                    "to": str(payload.get("to") or ""),
                    "reason": str(payload.get("reason") or ""),
                    "source": str(payload.get("source") or ""),
                    "hard": bool(payload.get("hard")),
                    "at": str(event.get("created_at") or ""),
                }
            )
            if str(event.get("event_type") or "") != "run_control" or created is None:
                continue
            to_status = str(payload.get("to") or "")
            if to_status == "paused" and pause_started is None:
                pause_started = created
                pause_count += 1
            elif to_status not in {"paused", ""} and pause_started is not None:
                paused_seconds += max(0.0, (created - pause_started).total_seconds())
                pause_started = None
        if pause_started is not None:
            paused_seconds += max(0.0, (end_time - pause_started).total_seconds())

        wall_clock = 0.0
        if started_at is not None:
            wall_clock = max(0.0, (end_time - started_at).total_seconds())
        return {
            "run_status": run_status,
            "wall_clock_seconds": round(wall_clock, 3),
            "active_compute_seconds": round(float(runs_wall or 0.0), 3),
            "paused_seconds": round(paused_seconds, 3),
            "pause_count": pause_count,
            "run_control_events": control_events,
        }


def _parse_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
