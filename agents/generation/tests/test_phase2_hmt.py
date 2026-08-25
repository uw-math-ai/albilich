from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.generation.phase2.codex_runner import (
    actor_role_for_action,
    build_session_prompt,
    execute_session,
    prepare_session,
)
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.budget import run_spend_from_operation
from agents.generation.phase2.hmt_sidecar import (
    periodic_hmt_sidecar_action,
    publish_hmt_sidecar,
    read_hmt_catalog,
)
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.scheduler import next_action
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import run_workflow


HMT_LATEX = r"""\documentclass[11pt]{article}
\usepackage{amsmath,amssymb,amsthm}
\newtheorem{theorem}{Theorem}
\title{A cumulative partial result}
\author{Albilich}
\begin{document}
\maketitle
\begin{abstract}
We record a verified elementary case and state the remaining gap precisely.
\end{abstract}
\section{Problem and partial result}
\begin{theorem}
The target statement holds in the trivial case.
\end{theorem}
\begin{proof}
The defining hypothesis gives the conclusion directly.
\end{proof}
\section{Remaining gap}
The general case remains open because the reduction step has not been proved.
\end{document}
"""


class HumanReadableMathematicalTextTest(unittest.TestCase):
    def _store(self, tmpdir: str) -> ProofStateStore:
        store = ProofStateStore("hmt-test", generation_root=Path(tmpdir) / "generation")
        store.init_problem("Classify all finite groups with the target closure property.")
        return store

    @staticmethod
    def _set_revision(store: ProofStateStore, revision: int) -> None:
        with store.connect() as conn:
            conn.execute(
                "UPDATE problem_state SET current_revision=? WHERE problem_id=?",
                (revision, store.problem_id),
            )
            conn.commit()

    @staticmethod
    def _set_integrated_claim_count(store: ProofStateStore, count: int) -> None:
        now = "2026-01-01T00:00:00+00:00"
        with store.connect() as conn:
            conn.execute("DELETE FROM claims WHERE claim_id LIKE 'hmt-integrated-%'")
            conn.executemany(
                """
                INSERT INTO claims(
                    claim_id, kind, statement, normalized_statement, fingerprint,
                    hypotheses, conditions_json, validation_status, lifecycle_status,
                    root_impact, reduction_depth, parent_ids_json, source_ids_json,
                    tags_json, evidence_artifact_ids_json, created_at, updated_at
                ) VALUES (?, 'lemma', ?, ?, ?, '', '[]', 'formally_verified',
                          'integrated', 0.1, 1, '["root"]', '[]', '[]', '[]', ?, ?)
                """,
                [
                    (
                        f"hmt-integrated-{index}",
                        f"Integrated HMT test claim {index}.",
                        f"integrated hmt test claim {index}",
                        f"hmt-integrated-fingerprint-{index}",
                        now,
                        now,
                    )
                    for index in range(1, count + 1)
                ],
            )
            conn.commit()

    def test_scheduler_emits_one_hmt_action_per_integrated_claim_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 100)

            with patch(
                "agents.generation.phase2.scheduler.integrated_claim_count",
                return_value=9,
            ):
                not_yet_due = next_action(store)
            self.assertFalse(not_yet_due.get("periodic_hmt", False))

            with patch(
                "agents.generation.phase2.scheduler.integrated_claim_count",
                return_value=10,
            ):
                action = next_action(store)

            self.assertEqual(action["mode"], "write")
            self.assertTrue(action["periodic_hmt"])
            self.assertEqual(action["hmt_source_revision"], 100)
            self.assertEqual(action["hmt_source_integrated_claim_count"], 10)
            self.assertEqual(action["hmt_integrated_claim_interval"], 10)
            self.assertEqual(action["hmt_sequence"], 1)
            self.assertEqual(actor_role_for_action(action), "writer")

            artifact_path = store.state_dir / "artifacts" / "hmt-1.tex"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(HMT_LATEX, encoding="utf-8")
            with store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        artifact_id, artifact_type, path, sha256, producer_role, run_id,
                        state_revision, content_summary, metadata_json, created_at
                    ) VALUES ('hmt-1', 'human_readable_mathematical_text', ?, 'sha',
                              'writer', 'write-1', 100, 'The trivial case is proved.', ?,
                              '2026-01-01T00:00:00+00:00')
                    """,
                    (
                        str(artifact_path),
                        json.dumps(
                            {
                                "source_revision": 100,
                                "source_integrated_claim_count": 10,
                                "integrated_claim_interval": 10,
                                "sequence": 1,
                            }
                        ),
                    ),
                )
                conn.commit()

            self._set_revision(store, 999)
            not_due = next_action(store)
            self.assertFalse(not_due.get("periodic_hmt", False))

            with patch(
                "agents.generation.phase2.scheduler.integrated_claim_count",
                return_value=19,
            ):
                not_due_at_nineteen = next_action(store)
            self.assertFalse(not_due_at_nineteen.get("periodic_hmt", False))

            with patch(
                "agents.generation.phase2.scheduler.integrated_claim_count",
                return_value=20,
            ):
                due_again = next_action(store)
            self.assertTrue(due_again["periodic_hmt"])
            self.assertEqual(due_again["hmt_source_integrated_claim_count"], 20)
            self.assertEqual(due_again["hmt_sequence"], 2)

    def test_legacy_revision_interval_zero_still_disables_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {
                "ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "",
                "ALBILICH_HMT_REVISION_INTERVAL": "0",
            },
        ):
            store = self._store(tmpdir)
            self._set_integrated_claim_count(store, 10)

            self.assertIsNone(periodic_hmt_sidecar_action(store))

    def test_revision_only_legacy_paper_gets_one_claim_cadence_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 50)
            self._set_integrated_claim_count(store, 10)
            artifact_path = store.state_dir / "artifacts" / "legacy-hmt.tex"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(HMT_LATEX, encoding="utf-8")
            with store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        artifact_id, artifact_type, path, sha256, producer_role, run_id,
                        state_revision, content_summary, metadata_json, created_at
                    ) VALUES ('legacy-hmt', 'human_readable_mathematical_text', ?, 'sha',
                              'writer', 'legacy-write', 40, 'Legacy paper.', ?,
                              '2026-01-01T00:00:00+00:00')
                    """,
                    (
                        str(artifact_path),
                        json.dumps({"source_revision": 40, "sequence": 1}),
                    ),
                )
                conn.commit()

            action = periodic_hmt_sidecar_action(store)

            self.assertIsNotNone(action)
            assert action is not None
            self.assertEqual(action["hmt_source_integrated_claim_count"], 10)
            self.assertEqual(action["hmt_sequence"], 2)

    def test_main_scheduler_can_skip_due_hmt_without_losing_research_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 10)

            with patch(
                "agents.generation.phase2.hmt_sidecar.integrated_claim_count",
                return_value=10,
            ):
                sidecar = periodic_hmt_sidecar_action(store)
            research = next_action(store, include_periodic_hmt=False)

        self.assertTrue(sidecar["periodic_hmt"])
        self.assertTrue(sidecar["hmt_sidecar"])
        self.assertFalse(research.get("periodic_hmt", False))
        self.assertNotEqual(research["search_intent"], "periodic_human_readable_mathematical_text")

    def test_sidecar_publication_does_not_mutate_revision_or_research_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 10)
            self._set_integrated_claim_count(store, 10)
            staging = store.state_dir / "artifacts" / "staging" / "hmt-sidecar.tex"
            staging.parent.mkdir(parents=True, exist_ok=True)
            staging.write_text(HMT_LATEX, encoding="utf-8")
            action = periodic_hmt_sidecar_action(store)
            before = store.get_state()["problem_state"]
            outcome = publish_hmt_sidecar(
                store,
                action=action,
                execution={
                    "run_id": "hmt-sidecar-run",
                    "status": "completed",
                    "usage": {"total_tokens": 5000},
                    "patch": {
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": "hmt-sidecar",
                                "artifact_type": "human_readable_mathematical_text",
                                "path": str(staging),
                                "content_summary": "The trivial case is proved and the reduction remains open.",
                                "metadata": {"title": "A sidecar partial paper"},
                            }
                        ]
                    },
                },
            )
            after = store.get_state()["problem_state"]

            self.assertTrue(outcome["accepted"], outcome)
            self.assertEqual(after["current_revision"], before["current_revision"])
            self.assertEqual(after["remaining_token_budget"], before["remaining_token_budget"])
            self.assertEqual(store.get_state()["artifacts"], [])
            self.assertEqual(read_hmt_catalog(store)[0]["artifact_id"], "hmt-sidecar")
            self.assertEqual(
                read_hmt_catalog(store)[0]["source_integrated_claim_count"], 10
            )
            self.assertTrue(Path(read_hmt_catalog(store)[0]["pdf_path"]).is_file())

    def test_hmt_usage_is_never_charged_to_research_budget(self) -> None:
        self.assertEqual(
            run_spend_from_operation(
                {
                    "search_intent": "periodic_human_readable_mathematical_text",
                    "input_tokens": 1000,
                    "cached_input_tokens": 100,
                    "output_tokens": 200,
                    "reasoning_output_tokens": 50,
                }
            ),
            0,
        )

    def test_workflow_hmt_sidecar_never_replaces_or_blocks_research(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 10)
            hmt_started = threading.Event()
            research_actions: list[dict] = []

            def executor(
                *,
                store: ProofStateStore,
                action: dict,
                session_plan: dict,
                stop_event: threading.Event | None = None,
                **_: object,
            ) -> dict:
                if action.get("periodic_hmt"):
                    hmt_started.set()
                    if stop_event is not None:
                        stop_event.wait(2.0)
                    return {
                        "run_id": "blocked-hmt-sidecar",
                        "actor_role": "writer",
                        "status": "failed",
                        "returncode": -1,
                        "patch": None,
                        "patch_error": "cancelled with the research workflow",
                        "usage": {"total_tokens": 999_999},
                    }
                research_actions.append(dict(action))
                self.assertTrue(hmt_started.wait(1.0), "research began without starting the due sidecar")
                actor_role = str(session_plan.get("actor_role") or actor_role_for_action(action))
                artifact_id = "research-continued-while-hmt-waited"
                return {
                    "run_id": "primary-research-run",
                    "actor_role": actor_role,
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 0.01,
                    "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
                    "patch": {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"],
                        "actor_role": actor_role,
                        "target_id": action.get("target_id", "root"),
                        "operations": [
                            {
                                "op": "attach_artifact",
                                "artifact_id": artifact_id,
                                "artifact_type": "source_synthesis_report",
                                "content": "The primary research lane continued while exposition remained pending.",
                                "content_summary": "Primary mathematical research continued independently of HMT authoring.",
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": [artifact_id],
                }

            started = time.monotonic()
            with patch(
                "agents.generation.phase2.hmt_sidecar.integrated_claim_count",
                return_value=10,
            ):
                result = run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=executor,
                )
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 1.0, "the workflow waited for its HMT sidecar")
            self.assertEqual(len(research_actions), 1)
            self.assertFalse(research_actions[0].get("periodic_hmt", False))
            self.assertEqual(result["steps"][0]["hmt_sidecar_status"], "cancelled_on_research_stop")
            self.assertFalse(any(
                artifact.get("artifact_type") == "human_readable_mathematical_text"
                for artifact in store.get_state()["artifacts"]
            ))
            self.assertFalse(any(
                run.get("search_intent") == "periodic_human_readable_mathematical_text"
                for run in store.get_state()["runs"]
            ))

    def test_hmt_manifest_and_prompt_are_one_shot_and_non_certifying(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 10)
            self._set_integrated_claim_count(store, 10)
            action = periodic_hmt_sidecar_action(store)
            assert action is not None

            manifest = build_context_manifest(store, action=action, max_chars=100_000)
            prompt = build_session_prompt(
                context_path=Path("/tmp/hmt-context.json"),
                action=action,
                actor_role="writer",
            )
            staging_created = Path(manifest["human_readable_text_packet"]["staging_dir"]).is_dir()

        packet = manifest["human_readable_text_packet"]
        self.assertEqual(packet["source_revision"], 10)
        self.assertEqual(packet["source_integrated_claim_count"], 10)
        self.assertEqual(packet["integrated_claim_interval"], 10)
        self.assertEqual(packet["root_statement"], "Classify all finite groups with the target closure property.")
        self.assertTrue(packet["staging_dir"].endswith("/artifacts/staging"))
        self.assertTrue(staging_created)
        self.assertIn("ONE-SHOT exposition pass", prompt)
        self.assertIn("non-certifying", prompt)
        self.assertIn("artifact_type='human_readable_mathematical_text'", prompt)
        self.assertIn("remaining gap", prompt)
        self.assertIn("verify that exact file exists", prompt)
        self.assertIn("Do not include record_run_metrics", prompt)
        self.assertIn("Encode mathematical notation as LaTeX", prompt)
        self.assertIn("Do not use Unicode mathematical operators", prompt)

    def test_hmt_writer_receives_writable_staging_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            root = Path(tmpdir)
            store = self._store(tmpdir)
            self._set_revision(store, 10)
            self._set_integrated_claim_count(store, 10)
            action = periodic_hmt_sidecar_action(store)
            assert action is not None
            plan = prepare_session(store, action)
            fake_codex = root / "fake_hmt_codex.py"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json, pathlib, sys\n"
                "args = sys.argv\n"
                "staging = pathlib.Path(args[args.index('--add-dir') + 1])\n"
                "assert staging.is_dir()\n"
                "(staging / 'writer-could-write.txt').write_text('ok')\n"
                "out = pathlib.Path(args[args.index('--output-last-message') + 1])\n"
                "payload = {'schema_version':1,'problem_id':'hmt-test','base_revision':10,"
                "'actor_role':'writer','target_id':'root','operations':["
                "{'op':'record_run_metrics','metrics':{'staging_probe':1}}]}\n"
                "out.write_text(json.dumps(payload))\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)

            result = execute_session(
                store,
                action,
                plan,
                codex_bin=str(fake_codex),
                timeout_sec=10,
            )

            staging = store.state_dir / "artifacts" / "staging"
            self.assertEqual(result["status"], "completed", result)
            self.assertTrue((staging / "writer-could-write.txt").is_file())

    def test_hmt_is_stored_as_tex_and_pdf_metadata_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            staging = store.state_dir / "artifacts" / "staging" / "hmt-snapshot.tex"
            staging.parent.mkdir(parents=True, exist_ok=True)
            staging.write_text(HMT_LATEX, encoding="utf-8")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "writer",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "hmt-snapshot",
                            "artifact_type": "human_readable_mathematical_text",
                            "path": str(staging),
                            "content_summary": "The target statement is proved in the trivial case, while the reduction step remains open.",
                            "metadata": {
                                "title": "A cumulative partial result",
                                "source_revision": 0,
                                "sequence": 1,
                                "snapshot_kind": "cumulative_partial_paper",
                                "non_certifying": True,
                            },
                        }
                    ],
                    "rationale": "write one periodic HMT snapshot",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            state = store.get_state()
            artifact = next(row for row in state["artifacts"] if row["artifact_id"] == "hmt-snapshot")
            metadata = json.loads(artifact["metadata_json"])
            self.assertTrue(artifact["path"].endswith(".tex"))
            self.assertIn(metadata.get("pdf_status"), {"compiled", "pdflatex_missing"})
            if metadata.get("pdf_status") == "compiled":
                self.assertEqual(metadata["pdf_path"], str(Path(artifact["path"]).with_suffix(".pdf")))
                self.assertTrue(Path(metadata["pdf_path"]).is_file())

    def test_hmt_staged_in_writer_context_is_safely_copied_to_artifact_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            context_staging = (
                store.state_dir
                / "contexts"
                / "rev0_write_root_test"
                / "hmt-context-snapshot.tex"
            )
            context_staging.parent.mkdir(parents=True, exist_ok=True)
            context_staging.write_text(HMT_LATEX, encoding="utf-8")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "writer",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "hmt-context-snapshot",
                            "artifact_type": "human_readable_mathematical_text",
                            "path": str(context_staging),
                            "content_summary": "The trivial case is proved and the general reduction remains open.",
                            "metadata": {
                                "title": "A cumulative partial result",
                                "source_revision": 0,
                                "sequence": 1,
                                "snapshot_kind": "cumulative_partial_paper",
                                "non_certifying": True,
                            },
                        }
                    ],
                    "rationale": "accept the writer's sandbox-local staging file",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            state = store.get_state()
            artifact = next(
                row for row in state["artifacts"] if row["artifact_id"] == "hmt-context-snapshot"
            )

        self.assertEqual(
            Path(artifact["path"]).parent,
            store.state_dir / "artifacts",
        )
        self.assertNotEqual(Path(artifact["path"]), context_staging)

    def test_writer_context_staging_filename_must_match_artifact_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            context_staging = store.state_dir / "contexts" / "rev0_write_root_test" / "wrong-name.tex"
            context_staging.parent.mkdir(parents=True, exist_ok=True)
            context_staging.write_text(HMT_LATEX, encoding="utf-8")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "writer",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "hmt-context-snapshot",
                            "artifact_type": "human_readable_mathematical_text",
                            "path": str(context_staging),
                            "content_summary": "The trivial case is proved and the general reduction remains open.",
                            "metadata": {
                                "title": "A cumulative partial result",
                                "source_revision": 0,
                                "sequence": 1,
                                "snapshot_kind": "cumulative_partial_paper",
                                "non_certifying": True,
                            },
                        }
                    ],
                    "rationale": "reject unrelated context evidence as writer staging",
                },
            )

        self.assertFalse(outcome.accepted)
        self.assertTrue(any("matching <artifact_id> file" in error for error in outcome.errors))


if __name__ == "__main__":
    unittest.main()
