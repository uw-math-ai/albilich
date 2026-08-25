from __future__ import annotations

import hashlib
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from agents.generation.phase2 import scope_state
from agents.generation.phase2.invariants import validate_conn
from agents.generation.phase2.models import fingerprint_text, json_dumps, normalize_text
from agents.generation.phase2.scope_state import import_certified_scope
from agents.generation.phase2.store import ProofStateStore, utc_now


class ScopeStateImportTests(unittest.TestCase):
    def _store(self, root: Path, problem_id: str, statement: str) -> ProofStateStore:
        store = ProofStateStore(problem_id, generation_root=root)
        store.init_problem(statement)
        with store.connect() as conn:
            conn.execute("UPDATE problem_state SET run_status = 'stopped'")
            conn.commit()
        return store

    def _artifact(
        self,
        store: ProofStateStore,
        conn,
        artifact_id: str,
        *,
        producer_role: str,
        artifact_type: str,
        metadata: dict | None = None,
    ) -> None:
        path = store.state_dir / "artifacts" / f"{artifact_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"# {artifact_id}\n"
        path.write_text(content, encoding="utf-8")
        conn.execute(
            """
            INSERT INTO artifacts(
                artifact_id, artifact_type, path, sha256, producer_role, run_id,
                state_revision, content_summary, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, 'test-run', 1, ?, ?, ?)
            """,
            (
                artifact_id,
                artifact_type,
                str(path.resolve()),
                hashlib.sha256(content.encode("utf-8")).hexdigest(),
                producer_role,
                artifact_id,
                json_dumps(metadata or {}),
                utc_now(),
            ),
        )

    def _integrated_claim(
        self,
        conn,
        claim_id: str,
        *,
        proof_artifact_id: str,
        verification_artifact_id: str,
        premise_claim_ids: tuple[str, ...] = (),
    ) -> None:
        now = utc_now()
        statement = f"Certified theorem {claim_id}."
        conn.execute(
            """
            INSERT INTO claims(
                claim_id, kind, statement, normalized_statement, fingerprint,
                hypotheses, conditions_json, validation_status, lifecycle_status,
                root_impact, reduction_depth, parent_ids_json, source_ids_json,
                tags_json, evidence_artifact_ids_json, created_at, updated_at
            ) VALUES (?, 'lemma', ?, ?, ?, '', '[]', 'informally_verified',
                      'integrated', 0.5, 1, '["root"]', '[]', '[]', ?, ?, ?)
            """,
            (
                claim_id,
                statement,
                normalize_text(statement),
                fingerprint_text(statement),
                json_dumps([proof_artifact_id, verification_artifact_id]),
                now,
                now,
            ),
        )
        route_id = f"route_{claim_id}"
        inference_id = f"inference_{claim_id}"
        conn.execute(
            """
            INSERT INTO routes(
                route_id, conclusion_claim_id, label, strategy, status,
                relation_to_parent, assumptions_json, conditions_json,
                evidence_artifact_ids_json, failure_fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, 'certified import', 'integrated', 'sufficient',
                      '[]', '[]', ?, '', ?, ?)
            """,
            (route_id, claim_id, route_id, json_dumps([proof_artifact_id]), now, now),
        )
        conn.execute(
            """
            INSERT INTO inferences(
                inference_id, route_id, conclusion_claim_id, explanation,
                conditions_json, condition_claim_ids_json, validation_status,
                evidence_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, 'verified inference', '[]', '[]',
                      'informally_verified', ?, ?, ?)
            """,
            (
                inference_id,
                route_id,
                claim_id,
                json_dumps([verification_artifact_id]),
                now,
                now,
            ),
        )
        for position, premise_id in enumerate(premise_claim_ids):
            conn.execute(
                "INSERT INTO inference_premises(inference_id, premise_claim_id, position) VALUES (?, ?, ?)",
                (inference_id, premise_id, position),
            )

    def test_import_keeps_target_root_and_certified_dependency_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/full", "Classify all admissible families.")
            target = self._store(generation_root, "target/family", "Classify the selected family only.")
            with source.connect() as conn:
                for stem in ("reduction", "selected_family", "excluded_family"):
                    self._artifact(
                        source,
                        conn,
                        f"art_{stem}_proof",
                        producer_role="researcher",
                        artifact_type="proof_dossier",
                        metadata={"target_id": f"claim_{stem}"},
                    )
                    self._artifact(
                        source,
                        conn,
                        f"art_{stem}_verification",
                        producer_role="strict_informal_verifier",
                        artifact_type="verification_report",
                        metadata={"verdict": "correct_no_gaps", "target_id": f"claim_{stem}"},
                    )
                self._integrated_claim(
                    conn,
                    "claim_structural_reduction",
                    proof_artifact_id="art_reduction_proof",
                    verification_artifact_id="art_reduction_verification",
                )
                self._integrated_claim(
                    conn,
                    "claim_selected_family_witness",
                    proof_artifact_id="art_selected_family_proof",
                    verification_artifact_id="art_selected_family_verification",
                    premise_claim_ids=("claim_structural_reduction",),
                )
                self._integrated_claim(
                    conn,
                    "claim_excluded_family_lemma",
                    proof_artifact_id="art_excluded_family_proof",
                    verification_artifact_id="art_excluded_family_verification",
                )
                self._artifact(
                    source,
                    conn,
                    "art_stale_scheduler_directive",
                    producer_role="phd_advisor",
                    artifact_type="advisor_report",
                    metadata={
                        "target_id": "claim_selected_family_witness",
                        "next_target_id": "inference_claim_selected_family_witness",
                    },
                )
                conn.execute(
                    """
                    INSERT INTO debts(
                        debt_id, owner_type, owner_id, obligation, fingerprint,
                        debt_type, severity, status, first_seen, last_seen,
                        repeated_count, source_artifact_ids_json,
                        suggested_next_target, resolution_evidence_json
                    ) VALUES (
                        'debt_old_root_research', 'claim', 'claim_selected_family_witness',
                        'Reopen this already certified theorem for the old root.',
                        'old-root-debt', 'gap', 'major', 'active', ?, ?, 1,
                        '[]', 'claim_selected_family_witness', '[]'
                    )
                    """,
                    (utc_now(), utc_now()),
                )
                conn.execute("UPDATE problem_state SET current_revision = 1")
                conn.commit()
                self.assertEqual(validate_conn(conn), [])

            result = import_certified_scope(
                source,
                target,
                claim_id_patterns=["selected_family"],
                include_claim_ids=["claim_structural_reduction"],
                artifact_patterns=["selected_family", "reduction"],
                exclude_patterns=["excluded_family", "omitted_family"],
            )

            self.assertTrue(result["target_root_preserved"])
            self.assertEqual(result["claim_count"], 2)
            with target.connect() as conn:
                state = conn.execute("SELECT root_statement, current_revision FROM problem_state").fetchone()
                self.assertEqual(state["root_statement"], "Classify the selected family only.")
                self.assertEqual(state["current_revision"], 1)
                claim_ids = {row[0] for row in conn.execute("SELECT claim_id FROM claims")}
                self.assertEqual(
                    claim_ids,
                    {"root", "claim_selected_family_witness", "claim_structural_reduction"},
                )
                self.assertEqual(validate_conn(conn), [])
                event = conn.execute(
                    "SELECT event_type, payload_json FROM events WHERE event_type = 'scope_import'"
                ).fetchone()
                self.assertIsNotNone(event)
                self.assertNotIn("excluded_family", event["payload_json"].lower())
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM debts").fetchone()[0], 0)
            self.assertTrue((target.state_dir / "artifacts" / "art_selected_family_proof.md").is_file())
            self.assertFalse((target.state_dir / "artifacts" / "art_excluded_family_proof.md").exists())
            self.assertFalse(
                (target.state_dir / "artifacts" / "art_stale_scheduler_directive.md").exists()
            )

    def test_repeated_import_skips_artifacts_already_present_in_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/repeated", "Source theorem.")
            target = self._store(generation_root, "target/repeated", "Target theorem.")
            with source.connect() as conn:
                self._artifact(
                    source,
                    conn,
                    "art_repeated_proof",
                    producer_role="researcher",
                    artifact_type="proof_dossier",
                    metadata={"target_id": "claim_repeated"},
                )
                self._artifact(
                    source,
                    conn,
                    "art_repeated_verification",
                    producer_role="strict_informal_verifier",
                    artifact_type="verification_report",
                    metadata={"verdict": "correct_no_gaps", "target_id": "claim_repeated"},
                )
                self._integrated_claim(
                    conn,
                    "claim_repeated",
                    proof_artifact_id="art_repeated_proof",
                    verification_artifact_id="art_repeated_verification",
                )
                conn.execute("UPDATE problem_state SET current_revision = 1")
                conn.commit()

            first = import_certified_scope(source, target, claim_id_patterns=["repeated"])
            second = import_certified_scope(source, target, claim_id_patterns=["repeated"])

            self.assertEqual(first["artifact_count"], 2)
            self.assertEqual(second["artifact_count"], 0)
            with target.connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT current_revision FROM problem_state").fetchone()[0], 2)
                self.assertEqual(validate_conn(conn), [])

    def test_repeated_import_still_validates_existing_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/repeated-hash", "Source theorem.")
            target = self._store(generation_root, "target/repeated-hash", "Target theorem.")
            with source.connect() as conn:
                self._artifact(
                    source,
                    conn,
                    "art_repeated_hash_proof",
                    producer_role="researcher",
                    artifact_type="proof_dossier",
                    metadata={"target_id": "claim_repeated_hash"},
                )
                self._artifact(
                    source,
                    conn,
                    "art_repeated_hash_verification",
                    producer_role="strict_informal_verifier",
                    artifact_type="verification_report",
                    metadata={"verdict": "correct_no_gaps", "target_id": "claim_repeated_hash"},
                )
                self._integrated_claim(
                    conn,
                    "claim_repeated_hash",
                    proof_artifact_id="art_repeated_hash_proof",
                    verification_artifact_id="art_repeated_hash_verification",
                )
                conn.commit()

            import_certified_scope(source, target, claim_id_patterns=["repeated_hash"])
            target_path = target.state_dir / "artifacts" / "art_repeated_hash_proof.md"
            target_path.write_text("tampered after first import\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "target artifact hash mismatch: art_repeated_hash_proof",
            ):
                import_certified_scope(source, target, claim_id_patterns=["repeated_hash"])

    def test_import_rejects_running_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/full", "Source theorem.")
            target = self._store(generation_root, "target/family", "Target theorem.")
            with target.connect() as conn:
                conn.execute("UPDATE problem_state SET run_status = 'running'")
                conn.commit()
            with self.assertRaisesRegex(ValueError, "target proof state must be paused"):
                import_certified_scope(source, target, claim_id_patterns=["selected_family"])

    def test_import_rejects_artifact_whose_file_no_longer_matches_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/hash", "Source theorem.")
            target = self._store(generation_root, "target/hash", "Target theorem.")
            with source.connect() as conn:
                self._artifact(
                    source,
                    conn,
                    "art_hash_proof",
                    producer_role="researcher",
                    artifact_type="proof_dossier",
                    metadata={"target_id": "claim_hash"},
                )
                self._artifact(
                    source,
                    conn,
                    "art_hash_verification",
                    producer_role="strict_informal_verifier",
                    artifact_type="verification_report",
                    metadata={"verdict": "correct_no_gaps", "target_id": "claim_hash"},
                )
                self._integrated_claim(
                    conn,
                    "claim_hash",
                    proof_artifact_id="art_hash_proof",
                    verification_artifact_id="art_hash_verification",
                )
                conn.commit()
            source_path = source.state_dir / "artifacts" / "art_hash_proof.md"
            source_path.write_text("tampered after certification\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "source artifact hash mismatch: art_hash_proof"):
                import_certified_scope(source, target, claim_id_patterns=["claim_hash"])

            self.assertFalse((target.state_dir / "artifacts" / "art_hash_proof.md").exists())

    def test_import_rejects_inference_depending_on_different_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/root-dependent", "Every object has property P.")
            target = self._store(generation_root, "target/unrelated", "Every object has unrelated property Q.")
            with source.connect() as conn:
                self._artifact(
                    source,
                    conn,
                    "art_root_dependent_proof",
                    producer_role="researcher",
                    artifact_type="proof_dossier",
                    metadata={"target_id": "claim_root_dependent"},
                )
                self._artifact(
                    source,
                    conn,
                    "art_root_dependent_verification",
                    producer_role="strict_informal_verifier",
                    artifact_type="verification_report",
                    metadata={"verdict": "correct_no_gaps", "target_id": "claim_root_dependent"},
                )
                conn.execute("UPDATE claims SET validation_status = 'informally_verified' WHERE claim_id = 'root'")
                self._integrated_claim(
                    conn,
                    "claim_root_dependent",
                    proof_artifact_id="art_root_dependent_proof",
                    verification_artifact_id="art_root_dependent_verification",
                    premise_claim_ids=("root",),
                )
                conn.commit()
                self.assertEqual(validate_conn(conn), [])

            with self.assertRaisesRegex(ValueError, "depends on the source root"):
                import_certified_scope(source, target, claim_id_patterns=["root_dependent"])

            with target.connect() as conn:
                self.assertIsNone(
                    conn.execute("SELECT 1 FROM claims WHERE claim_id = 'claim_root_dependent'").fetchone()
                )

    def test_import_serializes_resume_after_scope_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/quiescent", "Source theorem.")
            target = self._store(generation_root, "target/quiescent", "Target theorem.")
            with source.connect() as conn:
                self._artifact(
                    source,
                    conn,
                    "art_quiescent_proof",
                    producer_role="researcher",
                    artifact_type="proof_dossier",
                    metadata={"target_id": "claim_quiescent"},
                )
                self._artifact(
                    source,
                    conn,
                    "art_quiescent_verification",
                    producer_role="strict_informal_verifier",
                    artifact_type="verification_report",
                    metadata={"verdict": "correct_no_gaps", "target_id": "claim_quiescent"},
                )
                self._integrated_claim(
                    conn,
                    "claim_quiescent",
                    proof_artifact_id="art_quiescent_proof",
                    verification_artifact_id="art_quiescent_verification",
                )
                conn.commit()

            resume_started = threading.Event()
            resume_done = threading.Event()
            resume_errors: list[Exception] = []
            resume_threads: list[threading.Thread] = []
            original_copy = scope_state._copy_artifacts

            def resume_target() -> None:
                resume_started.set()
                try:
                    target.set_run_status("running", reason="concurrency regression", source="test")
                except Exception as exc:  # pragma: no cover - asserted below
                    resume_errors.append(exc)
                finally:
                    resume_done.set()

            def copy_while_resume_waits(*args, **kwargs):
                rows = original_copy(*args, **kwargs)
                thread = threading.Thread(target=resume_target)
                resume_threads.append(thread)
                thread.start()
                self.assertTrue(resume_started.wait(timeout=2))
                time.sleep(0.05)
                self.assertFalse(resume_done.is_set())
                return rows

            with mock.patch.object(scope_state, "_copy_artifacts", side_effect=copy_while_resume_waits):
                result = import_certified_scope(source, target, claim_id_patterns=["claim_quiescent"])

            for thread in resume_threads:
                thread.join(timeout=5)
            self.assertTrue(result["target_root_preserved"])
            self.assertFalse(resume_errors)
            self.assertTrue(resume_done.is_set())
            with target.connect() as conn:
                event_types = [
                    row[0]
                    for row in conn.execute(
                        "SELECT event_type FROM events "
                        "WHERE event_type IN ('scope_import', 'run_control') ORDER BY event_id"
                    )
                ]
                self.assertEqual(event_types, ["scope_import", "run_control"])


if __name__ == "__main__":
    unittest.main()
