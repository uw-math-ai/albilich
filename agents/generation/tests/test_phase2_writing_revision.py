from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2 import cli as cli_mod
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.result_status import classify_result
from agents.generation.phase2.scheduler import (
    WRITING_GATE_REVIEW_INTENT_PREFIX,
    next_action,
)
from agents.generation.phase2.steering import snapshot, submit_steering
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import run_workflow
from agents.generation.phase2.writing.paper_contract import (
    HUMAN_TERMINOLOGY_CONSULTATION_MARKER,
    REQUIRED_WRITING_REVIEW_LENSES,
)
from agents.generation.phase2.writing.revision import (
    REVISION_DOCUMENT_ARTIFACT_ID,
    WRITING_REVISION_RESEARCH_MODE,
    ingest_writing_revision,
    revision_document_metadata,
)


CLEAN_EXTERNAL_MD = """# A direct singleton argument

## Introduction

The smallest group illustrates how an algebraic axiom and a cardinality hypothesis divide the work in a proof. We show that a trivial group has exactly one element. The identity axiom first supplies an element, while the singleton hypothesis then identifies every element with that identity. This division gives the whole proof and explains why the same argument applies to trivial monoids.

## Proof

Let $G$ be a trivial group and let $e$ be its identity. The identity axiom shows that $G$ is nonempty. If $x$ belongs to $G$, then the singleton hypothesis gives $x=e$. Thus $G$ has at most one element and at least one element, so it has exactly one element.

## References

No external result is used in this elementary argument.
"""


def make_store(tmpdir: Path, problem_id: str) -> ProofStateStore:
    return ProofStateStore(problem_id, generation_root=tmpdir / "generation")


def ingest_markdown(store: ProofStateStore, tmpdir: Path) -> dict:
    source = tmpdir / "submitted.md"
    source.write_text(CLEAN_EXTERNAL_MD, encoding="utf-8")
    return ingest_writing_revision(store, source)


def attach_pass_review(store: ProofStateStore, action: dict) -> None:
    lens = str(action["critic_lens"])
    artifact_id = str(action["artifact_reviewed"])
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "writing_critic",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": f"review-{lens}-{artifact_id}",
                    "artifact_type": "writing_review",
                    "content": f"Independent {lens} audit of {artifact_id}: pass.",
                    "metadata": {
                        "verdict": "pass",
                        "lens": lens,
                        "artifact_reviewed": artifact_id,
                        "state_revision_reviewed": action["state_revision_reviewed"],
                    },
                },
                {
                    "op": "record_run_metrics",
                    "run_id": f"run-{lens}-{artifact_id}",
                    "mode": "review_writing",
                    "target_id": "root",
                    "search_intent": f"{WRITING_GATE_REVIEW_INTENT_PREFIX}{lens}",
                    "state_revision": store.get_revision(),
                    "status": "completed",
                },
            ],
            "rationale": f"complete the independent {lens} audit",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


def add_terminology_consultation(store: ProofStateStore) -> None:
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "writing_critic",
            "target_id": "root",
            "operations": [
                {
                    "op": "add_debt",
                    "debt_id": "writing-term-consultation",
                    "owner_type": "artifact",
                    "owner_id": REVISION_DOCUMENT_ARTIFACT_ID,
                    "debt_type": "writing",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": (
                        "L3-TERM-03: "
                        f"{HUMAN_TERMINOLOGY_CONSULTATION_MARKER} At Introduction paragraph 1, "
                        "should ‘identity witness’ be replaced by the standard term ‘identity element’?"
                    ),
                }
            ],
            "rationale": "terminology evidence is ambiguous and requires expert steering",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


class WritingRevisionIngestionTest(unittest.TestCase):
    def test_ingests_markdown_as_nonverified_writing_input(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmpdir:
            tmpdir = Path(raw_tmpdir)
            store = make_store(tmpdir, "writing-revision-ingest")
            result = ingest_markdown(store, tmpdir)

            self.assertEqual("md", result["document_format"])
            self.assertEqual(WRITING_REVISION_RESEARCH_MODE, result["research_mode"])
            self.assertIn("not proof verification", result["root_statement"])
            state = store.get_state()
            artifact = next(
                row for row in state["artifacts"]
                if row["artifact_id"] == REVISION_DOCUMENT_ARTIFACT_ID
            )
            metadata = revision_document_metadata(artifact)
            self.assertEqual("human_operator", artifact["producer_role"])
            self.assertEqual("revision_document", artifact["artifact_type"])
            self.assertEqual(".md", Path(artifact["path"]).suffix)
            self.assertEqual("not_verified_by_writing_harness", metadata["mathematical_status"])
            self.assertTrue(metadata["diff_minimal"])
            self.assertTrue(metadata["voice_preserving"])
            self.assertEqual(0, metadata["revision_number"])
            self.assertEqual(64, len(metadata["original_sha256"]))

    def test_ingests_latex_without_converting_its_source_format(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmpdir:
            tmpdir = Path(raw_tmpdir)
            source = tmpdir / "submitted.tex"
            source.write_text(
                "\\documentclass{article}\n\\title{An external note}\n\\begin{document}Text.\\end{document}\n",
                encoding="utf-8",
            )
            store = make_store(tmpdir, "writing-revision-tex")

            result = ingest_writing_revision(store, source)

            self.assertEqual("tex", result["document_format"])
            artifact = next(
                row for row in store.get_state()["artifacts"]
                if row["artifact_id"] == REVISION_DOCUMENT_ARTIFACT_ID
            )
            self.assertEqual(".tex", Path(artifact["path"]).suffix)
            self.assertEqual(source.read_text(encoding="utf-8"), Path(artifact["path"]).read_text(encoding="utf-8"))

    def test_reingestion_cannot_overwrite_existing_source_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmpdir:
            tmpdir = Path(raw_tmpdir)
            store = make_store(tmpdir, "writing-revision-no-overwrite")
            ingest_markdown(store, tmpdir)

            with self.assertRaisesRegex(ValueError, "already exists"):
                ingest_markdown(store, tmpdir)

    def test_cli_revise_paper_initializes_the_writing_only_run(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmpdir:
            tmpdir = Path(raw_tmpdir)
            source = tmpdir / "submitted.md"
            source.write_text(CLEAN_EXTERNAL_MD, encoding="utf-8")
            store = make_store(tmpdir, "writing/cli-revision")
            output = io.StringIO()

            with patch.object(cli_mod, "ProofStateStore", lambda _problem_id: store):
                with redirect_stdout(output):
                    cli_mod.main(
                        [
                            "revise-paper",
                            str(source),
                            "--problem-id",
                            store.problem_id,
                        ]
                    )

            payload = json.loads(output.getvalue())
            self.assertEqual("md", payload["document_format"])
            self.assertIn("--research-mode writing_revision", payload["next_step"])
            self.assertIn("--completion-policy publication_ready", payload["next_step"])


class WritingRevisionWorkflowTest(unittest.TestCase):
    def test_runs_terminology_then_introduction_then_whole_paper_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmpdir:
            tmpdir = Path(raw_tmpdir)
            store = make_store(tmpdir, "writing-revision-sequence")
            ingestion = ingest_markdown(store, tmpdir)

            observed_lenses = []
            for expected_lens in REQUIRED_WRITING_REVIEW_LENSES:
                action = next_action(
                    store,
                    research_mode=WRITING_REVISION_RESEARCH_MODE,
                    web_search="disabled",
                )
                self.assertEqual("review_writing", action["mode"], action)
                self.assertTrue(action["external_writing_review"])
                self.assertFalse(action["paper_review"])
                self.assertEqual("md", action["document_format"])
                self.assertEqual(expected_lens, action["critic_lens"])
                observed_lenses.append(action["critic_lens"])
                packet = build_context_manifest(
                    store,
                    target_id="root",
                    max_chars=200_000,
                    action=action,
                )["writing_review_packet"]
                self.assertEqual("revision_document", packet["reviewed_artifact_type"])
                self.assertEqual("md", packet["document_format"])
                self.assertIn("smallest group", packet["final_proof"]["content"])
                attach_pass_review(store, action)

            self.assertEqual(list(REQUIRED_WRITING_REVIEW_LENSES), observed_lenses)
            done = next_action(
                store,
                research_mode=WRITING_REVISION_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("stop_solved", done["mode"], done)
            self.assertTrue(done["writing_revision_only"])
            self.assertEqual("writing_revision_complete", done["terminal_classification"])
            result = classify_result(store)
            self.assertEqual("writing_revision_complete", result["report_classification"])
            self.assertEqual("not_applicable", result["relation_to_target"])
            self.assertEqual("", result["proved_statement"])

            # Any later writer revision invalidates the old whole-paper pass
            # until the actual latest source receives editor confirmation.
            revised = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "writer",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "revision-after-audits",
                            "artifact_type": "revision_document",
                            "content": CLEAN_EXTERNAL_MD.replace(
                                "gives the whole proof",
                                "describes the whole proof",
                            ),
                            "metadata": {
                                "revision_of_artifact_id": REVISION_DOCUMENT_ARTIFACT_ID,
                                "document_format": "md",
                                "original_sha256": ingestion["original_sha256"],
                                "revision_mode": True,
                            },
                        }
                    ],
                    "rationale": "simulate an audited late local revision",
                },
            )
            self.assertTrue(revised.accepted, revised.errors)
            status = classify_result(store)
            self.assertEqual("writing_revision_in_progress", status["report_classification"])
            self.assertFalse(status["latest_document_editor_confirmed"])
            confirmation = next_action(
                store,
                research_mode=WRITING_REVISION_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("review_writing", confirmation["mode"], confirmation)
            self.assertEqual("editor", confirmation["critic_lens"])
            self.assertTrue(confirmation["final_editor_confirmation"])
            self.assertEqual("revision-after-audits", confirmation["artifact_reviewed"])
            attach_pass_review(store, confirmation)
            self.assertEqual(
                "writing_revision_complete",
                classify_result(store)["report_classification"],
            )

    def test_completed_review_runs_keep_public_status_in_sync_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmpdir:
            tmpdir = Path(raw_tmpdir)
            store = make_store(tmpdir, "writing-revision-run-only-status")
            ingest_markdown(store, tmpdir)
            operations = [
                {
                    "op": "record_run_metrics",
                    "run_id": f"run-only-{lens}",
                    "mode": "review_writing",
                    "target_id": "root",
                    "search_intent": f"{WRITING_GATE_REVIEW_INTENT_PREFIX}{lens}",
                    "state_revision": store.get_revision(),
                    "status": "completed",
                }
                for lens in REQUIRED_WRITING_REVIEW_LENSES
            ]
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": operations,
                    "rationale": "record completed critic runs without redundant review artifacts",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            done = next_action(
                store,
                research_mode=WRITING_REVISION_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("stop_solved", done["mode"], done)
            self.assertEqual(
                "writing_revision_complete",
                classify_result(store)["report_classification"],
            )

    def test_uncertain_terminology_pauses_for_human_then_enters_revision(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmpdir:
            tmpdir = Path(raw_tmpdir)
            store = make_store(tmpdir, "writing-revision-consultation")
            ingestion = ingest_markdown(store, tmpdir)
            add_terminology_consultation(store)

            blocked = next_action(
                store,
                research_mode=WRITING_REVISION_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("await_human", blocked["mode"], blocked)
            self.assertEqual(
                "writing_terminology_consultation_required",
                blocked["terminal_classification"],
            )
            self.assertEqual("writing-term-consultation", blocked["terminology_debt_id"])
            self.assertEqual(1, len(snapshot(store.state_dir)["open_blockers"]))
            self.assertEqual(
                "writing_revision_awaiting_human",
                classify_result(store)["report_classification"],
            )
            run_workflow(
                store,
                steps=1,
                execute=True,
                write_on_stop=False,
                write_console=False,
                research_mode=WRITING_REVISION_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("awaiting_human", store.get_run_status())

            submit_steering(
                store.state_dir,
                "Use the standard term ‘identity element’ throughout.",
                blocker_id=blocked["human_blocker_id"],
            )
            # Relaunching after the answer clears the persisted wait state;
            # scheduler state and the accepted human message remain intact.
            planned = run_workflow(
                store,
                steps=1,
                execute=False,
                write_on_stop=False,
                write_console=False,
                research_mode=WRITING_REVISION_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("write", planned["steps"][0]["action"]["mode"])
            revision = next_action(
                store,
                research_mode=WRITING_REVISION_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("write", revision["mode"], revision)
            self.assertTrue(revision["external_writing_revision"])
            self.assertFalse(revision["paper_revision"])
            self.assertEqual("md", revision["document_format"])
            packet = build_context_manifest(
                store,
                target_id="root",
                max_chars=200_000,
                action=revision,
            )["writing_revision_packet"]
            self.assertEqual("revision_document", packet["revised_artifact_type"])
            self.assertEqual("md", packet["document_format"])
            self.assertEqual(ingestion["original_sha256"], packet["source_lineage"]["original_sha256"])
            self.assertIn("diff-minimally", packet["revision_contract"])
            self.assertIn("Never convert", packet["revision_contract"])
            self.assertIn("not_verified", json.dumps(store.get_state()["artifacts"]))

    def test_writer_revision_preserves_format_and_immutable_source_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmpdir:
            tmpdir = Path(raw_tmpdir)
            store = make_store(tmpdir, "writing-revision-lineage")
            ingestion = ingest_markdown(store, tmpdir)
            revised_content = CLEAN_EXTERNAL_MD.replace(
                "The smallest group illustrates",
                "A group of order one illustrates",
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "writer",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "revision-document-1",
                            "artifact_type": "revision_document",
                            "content": revised_content,
                            "metadata": {
                                "revision_of_artifact_id": REVISION_DOCUMENT_ARTIFACT_ID,
                                "document_format": "md",
                                "original_sha256": ingestion["original_sha256"],
                                "revision_mode": True,
                            },
                        }
                    ],
                    "rationale": "make one audited, voice-preserving local edit",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            state = store.get_state()
            artifact = next(
                row for row in state["artifacts"]
                if row["artifact_id"] == "revision-document-1"
            )
            metadata = revision_document_metadata(artifact)
            self.assertEqual(".md", Path(artifact["path"]).suffix)
            self.assertEqual(ingestion["original_sha256"], metadata["original_sha256"])
            self.assertEqual(REVISION_DOCUMENT_ARTIFACT_ID, metadata["revision_of_artifact_id"])
            self.assertEqual(1, metadata["revision_number"])
            self.assertTrue(metadata["diff_minimal"])
            self.assertTrue(metadata["voice_preserving"])
            self.assertEqual("not_verified_by_writing_harness", metadata["mathematical_status"])

            mismatch = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "writer",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "revision-document-format-mismatch",
                            "artifact_type": "revision_document",
                            "content": revised_content,
                            "metadata": {
                                "revision_of_artifact_id": "revision-document-1",
                                "document_format": "tex",
                                "original_sha256": ingestion["original_sha256"],
                                "revision_mode": True,
                            },
                        }
                    ],
                    "rationale": "attempt an invalid format conversion",
                },
            )
            self.assertFalse(mismatch.accepted)
            self.assertTrue(any("preserve source format" in error for error in mismatch.errors))

            staging_dir = store.state_dir / "artifacts" / "staging"
            staging_dir.mkdir(parents=True, exist_ok=True)
            mislabeled_path = staging_dir / "revision-document-2.tex"
            mislabeled_path.write_text(revised_content, encoding="utf-8")
            mislabeled = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "writer",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "revision-document-mislabeled-path",
                            "artifact_type": "revision_document",
                            "path": str(mislabeled_path),
                            "metadata": {
                                "revision_of_artifact_id": "revision-document-1",
                                "document_format": "md",
                                "original_sha256": ingestion["original_sha256"],
                                "revision_mode": True,
                            },
                        }
                    ],
                    "rationale": "attempt a mislabeled staged source file",
                },
            )
            self.assertFalse(mislabeled.accepted)
            self.assertTrue(any("staged path" in error for error in mislabeled.errors))


if __name__ == "__main__":
    unittest.main()
