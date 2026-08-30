from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agents.generation.phase2.codex_runner import actor_role_for_action, prepare_session
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch, preflight_patch_errors
from agents.generation.phase2.report import build_markdown_report
from agents.generation.phase2.scheduler import (
    PUBLICATION_REFEREE_INTENT,
    PUBLICATION_ROUTE_ERROR_RESEARCH_INTENT,
    PUBLICATION_WRITER_REVISION_INTENT,
    next_action,
)
from agents.generation.tests.test_phase2_writing_gate import (
    CLEAN_FINAL_PAPER,
    CLEAN_FINAL_PROOF,
    attach_final_proof,
    insert_final_paper,
    make_solved_store,
)


ROUTE_ERROR_EVIDENCE = (
    "Take the object used in the asserted implication with the stated hypotheses. "
    "Its invariant equals one on the source and zero on the claimed target, so the "
    "map cannot preserve the invariant and the implication fails in this case."
)


def attach_referee_report(
    store,
    *,
    report_id: str,
    paper_id: str,
    verdict: str,
    findings: list[dict[str, str]] | None = None,
    route_error: bool = False,
):
    metadata: dict[str, object] = {
        "verdict": verdict,
        "reviewed_paper_artifact_id": paper_id,
        "certificate_artifact_id": "final-proof-1",
        "findings": findings or [],
    }
    token = {
        "accept": "[accept]",
        "revise": "[revise]",
        "major_proof_route_error": "[major-proof-route-error]",
    }[verdict]
    operations: list[dict[str, object]] = [
        {
            "op": "attach_artifact",
            "artifact_id": report_id,
            "artifact_type": "referee_report",
            "content": f"{token}\n\nThe report gives a complete mathematical and editorial assessment.",
            "metadata": metadata,
        }
    ]
    if verdict == "revise":
        for index, finding in enumerate(findings or [], start=1):
            operations.append(
                {
                    "op": "add_debt",
                    "debt_id": f"{report_id}-finding-{index}",
                    "owner_type": "artifact",
                    "owner_id": paper_id,
                    "debt_type": "writing",
                    "severity": finding["severity"],
                    "status": "active",
                    "obligation": (
                        f"At {finding['location']}, {finding['problem']} "
                        f"Required revision: {finding['required_fix']}"
                    ),
                    "source_artifact_ids": [report_id],
                }
            )
    if route_error:
        metadata.update(
            {
                "affected_route_id": "route-root",
                "falsified_step": "The terminal implication from the constructed invariant to the root claim fails.",
                "mathematical_evidence": ROUTE_ERROR_EVIDENCE,
            }
        )
    return apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "referee",
            "target_id": "root",
            "operations": operations,
            "rationale": "independent journal referee report",
        },
    )


class PublicationLoopTest(unittest.TestCase):
    def _paper_store(self, tmpdir: str, problem_id: str):
        store = make_solved_store(Path(tmpdir), problem_id)
        attach_final_proof(store, "final-proof-1", CLEAN_FINAL_PROOF)
        insert_final_paper(store, "final-paper-1", CLEAN_FINAL_PAPER)
        with sqlite3.connect(store.db_path) as conn:
            metadata = json.loads(
                conn.execute(
                    "SELECT metadata_json FROM artifacts WHERE artifact_id = 'final-paper-1'"
                ).fetchone()[0]
            )
            metadata["publication_workflow"] = "writer_referee"
            metadata["paper_version"] = 1
            conn.execute(
                "UPDATE artifacts SET metadata_json = ? WHERE artifact_id = 'final-paper-1'",
                (json.dumps(metadata),),
            )
            conn.commit()
        return store

    def test_clean_paper_dispatches_domain_referee_with_full_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._paper_store(tmpdir, "publication-referee-dispatch")
            action = next_action(store, web_search="disabled")

            self.assertEqual("review_writing", action["mode"])
            self.assertEqual(PUBLICATION_REFEREE_INTENT, action["search_intent"])
            self.assertTrue(action["publication_referee"])
            self.assertEqual("referee", actor_role_for_action(action))
            manifest = build_context_manifest(store, action=action, max_chars=120_000)
            packet = manifest["writing_review_packet"]
            self.assertEqual("publication_referee", packet["packet_type"])
            self.assertEqual("final-paper-1", packet["paper"]["artifact_id"])
            self.assertEqual("final-proof-1", packet["certificate"]["artifact_id"])
            self.assertEqual("route-root", packet["integrated_route"]["route_id"])

            session = prepare_session(store, action, max_context_chars=120_000)
            instructions = Path(session["codex_workdir"]) / "AGENTS.md"
            self.assertTrue(instructions.is_file())
            self.assertIn("## Publication loop", instructions.read_text(encoding="utf-8"))

    def test_revise_persists_report_and_schedules_unbounded_writer_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._paper_store(tmpdir, "publication-revision-round")
            finding = {
                "severity": "major",
                "location": "Theorem 2.1, proof, second paragraph",
                "problem": "the implication omits the normality hypothesis",
                "required_fix": "state the hypothesis and prove it before invoking the quotient argument",
            }
            outcome = attach_referee_report(
                store,
                report_id="referee-report-1",
                paper_id="final-paper-1",
                verdict="revise",
                findings=[finding],
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            state = store.get_scheduler_state()
            self.assertEqual("revise", state["publication_reviews"][0]["verdict"])
            self.assertEqual(1, state["publication_reviews"][0]["finding_count"])

            action = next_action(store, web_search="disabled")
            self.assertEqual("write", action["mode"])
            self.assertEqual(PUBLICATION_WRITER_REVISION_INTENT, action["search_intent"])
            self.assertEqual("referee-report-1", action["referee_report_artifact_id"])
            self.assertEqual("writer", actor_role_for_action(action))
            manifest = build_context_manifest(store, action=action, max_chars=120_000)
            report = manifest["writing_revision_packet"]["referee_report"]
            self.assertEqual("referee-report-1", report["artifact_id"])
            self.assertIn("complete mathematical", report["content"])

    def test_accept_is_bound_to_current_paper_and_terminates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._paper_store(tmpdir, "publication-accept")
            outcome = attach_referee_report(
                store,
                report_id="referee-report-accept",
                paper_id="final-paper-1",
                verdict="accept",
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            action = next_action(store, web_search="disabled")
            self.assertEqual("stop_solved", action["mode"], action)
            self.assertEqual("final-paper-1", action["final_paper_artifact_id"])

            insert_final_paper(
                store,
                "final-paper-2",
                CLEAN_FINAL_PAPER.replace("present note", "revised note"),
                created_at="2026-01-05T00:00:00+00:00",
            )
            with sqlite3.connect(store.db_path) as conn:
                metadata = json.loads(
                    conn.execute(
                        "SELECT metadata_json FROM artifacts WHERE artifact_id = 'final-paper-2'"
                    ).fetchone()[0]
                )
                metadata.update(
                    {
                        "publication_workflow": "writer_referee",
                        "paper_version": 2,
                        "revision_of_artifact_id": "final-paper-1",
                    }
                )
                conn.execute(
                    "UPDATE artifacts SET metadata_json = ? WHERE artifact_id = 'final-paper-2'",
                    (json.dumps(metadata),),
                )
                conn.commit()
            action = next_action(store, web_search="disabled")
            self.assertEqual("review_writing", action["mode"], action)
            self.assertEqual("final-paper-2", action["artifact_reviewed"])

    def test_major_route_error_is_logged_and_reopens_research(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._paper_store(tmpdir, "publication-route-error")
            outcome = attach_referee_report(
                store,
                report_id="referee-report-route-error",
                paper_id="final-paper-1",
                verdict="major_proof_route_error",
                route_error=True,
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            action = next_action(store, web_search="disabled")
            self.assertEqual("reduce", action["mode"], action)
            self.assertEqual(PUBLICATION_ROUTE_ERROR_RESEARCH_INTENT, action["search_intent"])
            self.assertTrue(action["referee_route_error_research"])

            state = store.get_scheduler_state()
            root = next(row for row in state["claims"] if row["claim_id"] == "root")
            route = next(row for row in state["routes"] if row["route_id"] == "route-root")
            inference = next(row for row in state["inferences"] if row["inference_id"] == "inf-root")
            self.assertEqual("active", root["lifecycle_status"])
            self.assertEqual("challenged", root["validation_status"])
            self.assertEqual("blocked", route["status"])
            self.assertEqual("challenged", inference["validation_status"])
            self.assertTrue(state["publication_reviews"][0]["escalated_at"])
            route_debts = [d for d in state["debts"] if d["debt_type"] == "referee_route_error"]
            self.assertEqual(1, len(route_debts))
            self.assertIn("referee-report-route-error", json.loads(route_debts[0]["source_artifact_ids_json"]))
            report = build_markdown_report(store)
            self.assertIn("Writer--Referee Publication Loop", report)
            self.assertIn("[major-proof-route-error]", report)
            self.assertIn("returned to research=yes", report)

    def test_repaired_route_requires_a_new_certificate_and_paper(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._paper_store(tmpdir, "publication-repaired-route")
            outcome = attach_referee_report(
                store,
                report_id="referee-report-route-error",
                paper_id="final-paper-1",
                verdict="major_proof_route_error",
                route_error=True,
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            next_action(store, web_search="disabled")  # persist escalation
            now = "2026-01-08T00:00:00+00:00"
            with sqlite3.connect(store.db_path) as conn:
                conn.execute(
                    """INSERT INTO routes(
                           route_id, conclusion_claim_id, label, strategy, status,
                           relation_to_parent, assumptions_json, conditions_json,
                           evidence_artifact_ids_json, failure_fingerprint, created_at, updated_at
                       ) VALUES ('route-replacement', 'root', 'Replacement proof route',
                                 'Use a different invariant that avoids the refuted implication.',
                                 'integrated', 'sufficient', '[]', '[]', '[]', '', ?, ?)""",
                    (now, now),
                )
                conn.execute(
                    "UPDATE claims SET lifecycle_status='integrated', validation_status='informally_verified' WHERE claim_id='root'"
                )
                conn.execute(
                    """INSERT INTO inferences(
                           inference_id, route_id, conclusion_claim_id, explanation,
                           conditions_json, condition_claim_ids_json, validation_status,
                           evidence_artifact_ids_json, created_at, updated_at
                       ) VALUES ('inf-replacement', 'route-replacement', 'root',
                                 'The replacement invariant proves the root claim without the refuted implication.',
                                 '[]', '[]', 'informally_verified', '[]', ?, ?)""",
                    (now, now),
                )
                conn.commit()

            action = next_action(store, web_search="disabled")
            self.assertEqual("write", action["mode"], action)
            self.assertTrue(action["final_output_required"])
            self.assertNotIn("certificate_artifact_id", action)

            proof_path = store.state_dir / "artifacts" / "final-proof-2.md"
            proof_path.write_text(CLEAN_FINAL_PROOF, encoding="utf-8")
            with sqlite3.connect(store.db_path) as conn:
                conn.execute(
                    """INSERT INTO artifacts(
                           artifact_id, artifact_type, path, sha256, producer_role, run_id,
                           state_revision, content_summary, metadata_json, created_at
                       ) VALUES ('final-proof-2', 'final_proof', ?, 'new-proof-sha', 'writer', '',
                                 10, 'The replacement route proves the root theorem.', ?, ?)""",
                    (
                        str(proof_path),
                        json.dumps({"claim_id": "root", "route_id": "route-replacement"}),
                        now,
                    ),
                )
                conn.commit()

            action = next_action(store, web_search="disabled")
            self.assertEqual("write", action["mode"], action)
            self.assertTrue(action["paper_authoring"])
            self.assertEqual("final-proof-2", action["certificate_artifact_id"])

    def test_referee_contract_rejects_unlocated_or_mutating_reports(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "p",
            "base_revision": 0,
            "actor_role": "referee",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "r",
                    "artifact_type": "referee_report",
                    "content": "[revise]",
                    "metadata": {
                        "verdict": "revise",
                        "reviewed_paper_artifact_id": "paper",
                        "certificate_artifact_id": "proof",
                    },
                },
                {
                    "op": "propose_status_transition",
                    "target_type": "claim",
                    "target_id": "root",
                    "status_type": "validation",
                    "new_status": "challenged",
                },
            ],
        }
        errors = preflight_patch_errors(patch, "referee")
        self.assertTrue(any("at least one" in error for error in errors), errors)
        self.assertTrue(any("invalid operations" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
