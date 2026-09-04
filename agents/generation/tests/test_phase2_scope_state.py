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
from agents.generation.phase2.models import json_dumps
from agents.generation.phase2.scope_state import import_certified_scope
from agents.generation.phase2.store import ProofStateStore, utc_now
from agents.generation.tests._phase2_test_support import (
    certify_and_integrate_claim,
    journal_legacy_fixture_mutation,
    strictly_verify_entities,
)


class ScopeStateImportTests(unittest.TestCase):
    def _store(self, root: Path, problem_id: str, statement: str) -> ProofStateStore:
        store = ProofStateStore(problem_id, generation_root=root)
        store.init_problem(statement)
        store.set_run_status("stopped", reason="quiescent scope-import fixture", source="test")
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

    def _certified_claim(
        self,
        store: ProofStateStore,
        claim_id: str,
        *,
        artifact_stem: str,
        premise_claim_ids: tuple[str, ...] = (),
    ) -> None:
        certify_and_integrate_claim(
            store,
            claim_id=claim_id,
            statement=f"Certified theorem {claim_id}.",
            route_id=f"route_{claim_id}",
            inference_id=f"inference_{claim_id}",
            premise_claim_ids=list(premise_claim_ids),
            proof_artifact_id=f"art_{artifact_stem}_proof",
            verification_artifact_id=f"art_{artifact_stem}_verification",
            integration_artifact_id=f"art_{artifact_stem}_integration",
        )

    def test_import_keeps_target_root_and_certified_dependency_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/full", "Classify all admissible families.")
            target = self._store(generation_root, "target/family", "Classify the selected family only.")
            self._certified_claim(
                source,
                "claim_structural_reduction",
                artifact_stem="reduction",
            )
            self._certified_claim(
                source,
                "claim_selected_family_witness",
                artifact_stem="selected_family",
                premise_claim_ids=("claim_structural_reduction",),
            )
            self._certified_claim(
                source,
                "claim_excluded_family_lemma",
                artifact_stem="excluded_family",
            )
            def add_legacy_scheduler_rows(conn, _state_revision: int) -> None:
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
                        '[]', 'claim_selected_family_witness', '{}'
                    )
                    """,
                    (utc_now(), utc_now()),
                )
            journal_legacy_fixture_mutation(
                source,
                add_legacy_scheduler_rows,
                fixture_id="scope-old-root-scheduler-state",
            )
            with source.connect() as conn:
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
            self._certified_claim(source, "claim_repeated", artifact_stem="repeated")

            first = import_certified_scope(source, target, claim_id_patterns=["repeated"])
            second = import_certified_scope(source, target, claim_id_patterns=["repeated"])

            self.assertEqual(first["artifact_count"], 3)
            self.assertEqual(second["artifact_count"], 0)
            with target.connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0], 3)
                self.assertEqual(conn.execute("SELECT current_revision FROM problem_state").fetchone()[0], 2)
                self.assertEqual(validate_conn(conn), [])

    def test_repeated_import_still_validates_existing_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/repeated-hash", "Source theorem.")
            target = self._store(generation_root, "target/repeated-hash", "Target theorem.")
            self._certified_claim(
                source,
                "claim_repeated_hash",
                artifact_stem="repeated_hash",
            )

            import_certified_scope(source, target, claim_id_patterns=["repeated_hash"])
            target_path = target.state_dir / "artifacts" / "art_repeated_hash_proof.md"
            target_path.write_text("tampered after first import\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "artifact art_repeated_hash_proof file hash does not match recorded sha256",
            ):
                import_certified_scope(source, target, claim_id_patterns=["repeated_hash"])

    def test_import_rejects_running_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/full", "Source theorem.")
            target = self._store(generation_root, "target/family", "Target theorem.")
            target.set_run_status("running", reason="exercise running-target guard", source="test")
            with self.assertRaisesRegex(ValueError, "target proof state must be paused"):
                import_certified_scope(source, target, claim_id_patterns=["selected_family"])

    def test_import_rejects_artifact_whose_file_no_longer_matches_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/hash", "Source theorem.")
            target = self._store(generation_root, "target/hash", "Target theorem.")
            self._certified_claim(source, "claim_hash", artifact_stem="hash")
            source_path = source.state_dir / "artifacts" / "art_hash_proof.md"
            source_path.write_text("tampered after certification\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "artifact art_hash_proof file hash does not match recorded sha256",
            ):
                import_certified_scope(source, target, claim_id_patterns=["claim_hash"])

            self.assertFalse((target.state_dir / "artifacts" / "art_hash_proof.md").exists())

    def test_import_does_not_follow_a_target_artifact_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/symlink", "Source theorem.")
            target = self._store(generation_root, "target/symlink", "Target theorem.")
            self._certified_claim(source, "claim_symlink", artifact_stem="symlink")

            protected = generation_root / "protected.md"
            protected.write_text("operator-owned material\n", encoding="utf-8")
            destination = target.state_dir / "artifacts" / "art_symlink_proof.md"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(protected)

            # Isolate the copy boundary: the independent retention-tree scan
            # also rejects symlinks, but the importer must remain safe even if
            # that earlier admission layer is unavailable or refactored.
            storage_status = {
                "total_local_bytes": 0,
                "hard_limit_bytes": 1_000_000_000,
                "within_hard_limit": True,
            }
            with mock.patch(
                "agents.generation.phase2.storage_policy.audit_local_storage",
                return_value=storage_status,
            ):
                with self.assertRaisesRegex(ValueError, "must not be a symbolic link"):
                    import_certified_scope(
                        source,
                        target,
                        claim_id_patterns=["claim_symlink"],
                    )

            self.assertEqual(
                "operator-owned material\n", protected.read_text(encoding="utf-8")
            )
            self.assertTrue(destination.is_symlink())
            with target.connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0], 0)

    def test_import_rejects_inference_depending_on_different_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generation_root = Path(tmp)
            source = self._store(generation_root, "source/root-dependent", "Every object has property P.")
            target = self._store(generation_root, "target/unrelated", "Every object has unrelated property Q.")
            strictly_verify_entities(
                source,
                target_id="root",
                claim_ids=["root"],
                inference_ids=[],
                artifact_id="art_source_root_verification",
            )
            self._certified_claim(
                source,
                "claim_root_dependent",
                artifact_stem="root_dependent",
                premise_claim_ids=("root",),
            )
            with source.connect() as conn:
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
            self._certified_claim(source, "claim_quiescent", artifact_stem="quiescent")

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
                self.assertEqual(event_types[-2:], ["scope_import", "run_control"])


if __name__ == "__main__":
    unittest.main()
