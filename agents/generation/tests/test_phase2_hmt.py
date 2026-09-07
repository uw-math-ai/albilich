from __future__ import annotations

import json
import hashlib
import functools
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
from agents.generation.phase2.dispatch_execution import (
    CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY,
    CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE,
    CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
    CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE,
)
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import (
    apply_operator_patch as apply_patch,
    apply_system_patch,
)
from agents.generation.phase2.scheduler import next_action
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import run_workflow
from agents.generation.tests._phase2_test_support import (
    journal_legacy_fixture_mutation,
    strictly_verify_entities,
)


def _declare_parallel_local_executor(executor):
    @functools.wraps(executor)
    def supervised(*args, aggregate_rss_governor=None, **kwargs):
        result = dict(executor(*args, **kwargs))
        snapshot = (
            aggregate_rss_governor.snapshot()
            if aggregate_rss_governor is not None
            else {"peak_mb": 0.0}
        )
        result["observed_aggregate_peak_memory_mb"] = float(
            snapshot["peak_mb"]
        )
        result["resource_limits"] = {
            "max_aggregate_child_process_tree_rss_mb": (
                aggregate_rss_governor.limit_mb
                if aggregate_rss_governor is not None
                else None
            )
        }
        return result

    setattr(
        supervised,
        CUSTOM_EXECUTOR_CONCURRENCY_ATTRIBUTE,
        CUSTOM_EXECUTOR_PARALLEL_CAPABILITY,
    )
    setattr(
        supervised,
        CUSTOM_EXECUTOR_RESOURCE_ATTRIBUTE,
        CUSTOM_EXECUTOR_AGGREGATE_RSS_CAPABILITY,
    )
    return supervised


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
        while store.get_revision() < revision:
            current = store.get_revision()
            outcome = apply_system_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": current,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": f"hmt-test-revision-{current + 1}",
                            "artifact_type": "test_fixture_revision_marker",
                            "content": f"Test fixture revision marker {current + 1}.",
                            "content_summary": "Test-only revision marker.",
                        }
                    ],
                    "rationale": "advance the test fixture through the authenticated patch journal",
                },
            )
            if not outcome.accepted:
                raise AssertionError(outcome.errors)

    @staticmethod
    def _set_integrated_claim_count(store: ProofStateStore, count: int) -> None:
        if count <= 0:
            return
        claim_ids = [f"hmt-integrated-{index}" for index in range(1, count + 1)]
        inference_ids = [f"hmt-inference-{index}" for index in range(1, count + 1)]
        seed_operations: list[dict] = []
        for index, (claim_id, inference_id) in enumerate(
            zip(claim_ids, inference_ids), start=1
        ):
            route_id = f"hmt-route-{index}"
            seed_operations.extend(
                [
                    {
                        "op": "add_claim",
                        "claim_id": claim_id,
                        "kind": "lemma",
                        "statement": f"Integrated HMT test claim {index}.",
                        "parent_ids": ["root"],
                        "root_impact": 0.1,
                        "reduction_depth": 1,
                    },
                    {
                        "op": "add_route",
                        "route_id": route_id,
                        "conclusion_claim_id": claim_id,
                        "relation_to_parent": "sufficient",
                        "strategy": "A direct certified fixture argument.",
                    },
                    {
                        "op": "add_inference",
                        "inference_id": inference_id,
                        "route_id": route_id,
                        "conclusion_claim_id": claim_id,
                        "premise_claim_ids": [],
                        "validation_status": "plausible",
                        "explanation": "The direct fixture argument proves the claim.",
                    },
                ]
            )
        seeded = apply_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": store.get_revision(),
                "actor_role": "researcher",
                "target_id": "root",
                "operations": seed_operations,
                "rationale": "seed genuinely certifiable HMT fixture claims",
            },
        )
        if not seeded.accepted:
            raise AssertionError(seeded.errors)
        verification_id = "hmt-fixture-verification"
        strictly_verify_entities(
            store,
            target_id="root",
            claim_ids=claim_ids,
            inference_ids=inference_ids,
            artifact_id=verification_id,
        )
        integration_operations: list[dict] = []
        for index, claim_id in enumerate(claim_ids, start=1):
            route_id = f"hmt-route-{index}"
            artifact_id = f"hmt-integration-{index}"
            integration_operations.extend(
                [
                    {
                        "op": "attach_artifact",
                        "artifact_id": artifact_id,
                        "artifact_type": "integration_report",
                        "content": f"The certified route {route_id} proves {claim_id}.",
                        "metadata": {
                            "integrates": True,
                            "route_id": route_id,
                            "claim_id": claim_id,
                        },
                    },
                    {
                        "op": "propose_status_transition",
                        "target_type": "claim",
                        "target_id": claim_id,
                        "status_type": "lifecycle",
                        "new_status": "integrated",
                        "route_id": route_id,
                        "evidence_artifact_ids": [artifact_id],
                    },
                ]
            )
        integrated = apply_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": store.get_revision(),
                "actor_role": "integration_verifier",
                "target_id": "root",
                "operations": integration_operations,
                "rationale": "integrate the strictly verified HMT fixture claims",
            },
        )
        if not integrated.accepted:
            raise AssertionError(integrated.errors)

    def test_scheduler_emits_one_hmt_action_per_integrated_claim_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 1)

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
            self.assertEqual(action["hmt_source_revision"], 1)
            self.assertEqual(action["hmt_source_integrated_claim_count"], 10)
            self.assertEqual(action["hmt_integrated_claim_interval"], 10)
            self.assertEqual(action["hmt_sequence"], 1)
            self.assertEqual(actor_role_for_action(action), "writer")

            artifact_path = store.state_dir / "artifacts" / "hmt-1.tex"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(HMT_LATEX, encoding="utf-8")
            def insert_hmt(conn, state_revision: int) -> None:
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        artifact_id, artifact_type, path, sha256, producer_role, run_id,
                        state_revision, content_summary, metadata_json, created_at
                    ) VALUES ('hmt-1', 'human_readable_mathematical_text', ?, ?,
                              'writer', 'write-1', ?, 'The trivial case is proved.', ?,
                              '2026-01-01T00:00:00+00:00')
                    """,
                    (
                        str(artifact_path),
                        hashlib.sha256(HMT_LATEX.encode("utf-8")).hexdigest(),
                        state_revision,
                        json.dumps(
                            {
                                "source_revision": 1,
                                "source_integrated_claim_count": 10,
                                "integrated_claim_interval": 10,
                                "sequence": 1,
                            }
                        ),
                    ),
                )
            journal_legacy_fixture_mutation(
                store, insert_hmt, fixture_id="hmt-cadence-record"
            )

            self._set_revision(store, 2)
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
            self._set_revision(store, 1)
            self._set_integrated_claim_count(store, 10)
            artifact_path = store.state_dir / "artifacts" / "legacy-hmt.tex"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(HMT_LATEX, encoding="utf-8")
            def insert_legacy_hmt(conn, state_revision: int) -> None:
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        artifact_id, artifact_type, path, sha256, producer_role, run_id,
                        state_revision, content_summary, metadata_json, created_at
                    ) VALUES ('legacy-hmt', 'human_readable_mathematical_text', ?, ?,
                              'writer', 'legacy-write', ?, 'Legacy paper.', ?,
                              '2026-01-01T00:00:00+00:00')
                    """,
                    (
                        str(artifact_path),
                        hashlib.sha256(HMT_LATEX.encode("utf-8")).hexdigest(),
                        state_revision,
                        json.dumps({"source_revision": 0, "sequence": 1}),
                    ),
                )
            journal_legacy_fixture_mutation(
                store, insert_legacy_hmt, fixture_id="legacy-hmt-cadence-record"
            )

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
            self._set_revision(store, 1)

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
            self._set_revision(store, 1)
            self._set_integrated_claim_count(store, 10)
            staging = store.state_dir / "artifacts" / "staging" / "hmt-sidecar.tex"
            staging.parent.mkdir(parents=True, exist_ok=True)
            staging.write_text(HMT_LATEX, encoding="utf-8")
            action = periodic_hmt_sidecar_action(store)
            state_before = store.get_state()
            before = state_before["problem_state"]
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
            self.assertEqual(store.get_state()["artifacts"], state_before["artifacts"])
            self.assertEqual(read_hmt_catalog(store)[0]["artifact_id"], "hmt-sidecar")
            self.assertEqual(
                read_hmt_catalog(store)[0]["source_integrated_claim_count"], 10
            )
            pdf_path = Path(read_hmt_catalog(store)[0]["pdf_path"])
            self.assertTrue(pdf_path.is_file())
            with pdf_path.open("ab") as handle:
                handle.write(b"tampered")
            self.assertEqual(read_hmt_catalog(store), [])

    def test_sidecar_publication_allocates_sequence_against_live_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            staging = store.state_dir / "artifacts" / "staging"
            staging.mkdir(parents=True, exist_ok=True)

            def publish(artifact_id: str, source_count: int) -> dict:
                source = staging / f"{artifact_id}.tex"
                source.write_text(HMT_LATEX, encoding="utf-8")
                return publish_hmt_sidecar(
                    store,
                    action={
                        "hmt_source_revision": source_count,
                        "hmt_source_integrated_claim_count": source_count,
                        "hmt_integrated_claim_interval": 10,
                        # Both actions were planned before either publication.
                        "hmt_sequence": 1,
                    },
                    execution={
                        "run_id": f"run-{artifact_id}",
                        "status": "completed",
                        "patch": {
                            "operations": [
                                {
                                    "op": "attach_artifact",
                                    "artifact_id": artifact_id,
                                    "artifact_type": "human_readable_mathematical_text",
                                    "path": str(source),
                                    "content_summary": "A cumulative partial result.",
                                    "metadata": {"title": f"Snapshot at {source_count}"},
                                }
                            ]
                        },
                    },
                )

            self.assertTrue(publish("hmt-at-20", 20)["accepted"])
            # Recover the older completed paper after the newer one has
            # already entered the catalog.
            self.assertTrue(publish("hmt-at-10", 10)["accepted"])

            papers = read_hmt_catalog(store)
            self.assertEqual([paper["sequence"] for paper in papers], [1, 2])
            self.assertEqual(
                [paper["source_integrated_claim_count"] for paper in papers],
                [10, 20],
            )

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
            self._set_revision(store, 1)
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
                    executor=_declare_parallel_local_executor(executor),
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

    def test_hmt_is_deferred_for_undeclared_serial_executor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 1)
            calls: list[dict] = []

            def serial_executor(*, action, **_kwargs):
                calls.append(dict(action))
                return {
                    "run_id": "serial-research-only",
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 0.01,
                    "peak_memory_mb": 1.0,
                    "usage": {"total_tokens": 1},
                    "patch": None,
                    "patch_error": "synthetic stop",
                    "failure_kind": "test_failure",
                    "output_artifact_ids": [],
                }

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
                    executor=serial_executor,
                )

            self.assertEqual(1, len(calls))
            self.assertFalse(calls[0].get("periodic_hmt", False))
            self.assertEqual(
                "deferred_serial_executor",
                result["steps"][0]["hmt_sidecar_status"],
            )

    def test_completed_hmt_publishes_before_research_step_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            self._set_revision(store, 1)
            research_started = threading.Event()
            published = threading.Event()
            observed_during_research = []

            def executor(*, store, action, session_plan, **kwargs):
                actor_role = str(session_plan["actor_role"])
                if action.get("periodic_hmt"):
                    self.assertTrue(research_started.wait(2))
                    source = store.state_dir / "artifacts/staging/early-hmt.tex"
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text(HMT_LATEX, encoding="utf-8")
                    operations = [{
                        "op": "attach_artifact", "artifact_id": "early-hmt",
                        "artifact_type": "human_readable_mathematical_text",
                        "path": str(source), "content_summary": "Cumulative partial result.",
                    }]
                else:
                    research_started.set()
                    observed_during_research.append(published.wait(5))
                    operations = [{
                        "op": "attach_artifact", "artifact_id": "research-after-hmt",
                        "artifact_type": "source_synthesis_report",
                        "content": "Research remained active after the HMT was published.",
                        "content_summary": "Research did not gate HMT publication.",
                    }]
                return {
                    "run_id": f"early-hmt-{actor_role}", "actor_role": actor_role,
                    "status": "completed", "returncode": 0, "usage": {}, "patch_error": "",
                    "patch": {
                        "schema_version": SCHEMA_VERSION, "problem_id": store.problem_id,
                        "base_revision": session_plan["state_revision"], "actor_role": actor_role,
                        "target_id": "root", "operations": operations,
                    },
                }

            def publish(*args, **kwargs):
                outcome = publish_hmt_sidecar(*args, **kwargs)
                if outcome.get("accepted"):
                    published.set()
                return outcome

            with (
                patch("agents.generation.phase2.hmt_sidecar.integrated_claim_count", return_value=10),
                patch("agents.generation.phase2.workflow.publish_hmt_sidecar", side_effect=publish),
            ):
                result = run_workflow(
                    store, steps=1, execute=True, parallel_librarian_verifier=False,
                    parallel_branches=0, write_on_stop=False, write_console=False,
                    executor=_declare_parallel_local_executor(executor),
                )
            self.assertEqual([True], observed_during_research)
            self.assertEqual("early-hmt", read_hmt_catalog(store)[0]["artifact_id"])
            self.assertEqual("completed", result["steps"][0]["hmt_sidecar_status"])

    def test_late_hmt_progress_does_not_resurrect_finished_owner_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 1)
            second_research_started = threading.Event()
            hmt_returning = threading.Event()
            research_calls = 0

            def executor(
                *,
                store: ProofStateStore,
                action: dict,
                session_plan: dict,
                **_: object,
            ) -> dict:
                nonlocal research_calls
                if action.get("periodic_hmt"):
                    self.assertTrue(
                        second_research_started.wait(2.0),
                        "the HMT did not remain pending past its owner step",
                    )
                    hmt_returning.set()
                    return {
                        "run_id": "late-hmt-sidecar",
                        "actor_role": "writer",
                        "status": "failed",
                        "returncode": -1,
                        "patch": None,
                        "patch_error": "synthetic late completion",
                        "usage": {},
                    }

                research_calls += 1
                if research_calls == 2:
                    second_research_started.set()
                    self.assertTrue(hmt_returning.wait(1.0))
                    time.sleep(0.05)
                actor_role = str(session_plan.get("actor_role") or actor_role_for_action(action))
                artifact_id = f"research-step-{research_calls}"
                return {
                    "run_id": artifact_id,
                    "actor_role": actor_role,
                    "status": "completed",
                    "returncode": 0,
                    "wall_time_seconds": 0.01,
                    "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
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
                                "content": "Research continued while the HMT completed asynchronously.",
                                "content_summary": "Synthetic regression evidence.",
                            }
                        ],
                    },
                    "patch_error": "",
                    "output_artifact_ids": [artifact_id],
                }

            with patch(
                "agents.generation.phase2.hmt_sidecar.integrated_claim_count",
                return_value=10,
            ):
                result = run_workflow(
                    store,
                    steps=2,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=_declare_parallel_local_executor(executor),
                )

            self.assertEqual(research_calls, 2)
            self.assertEqual(result["steps"][0]["execution_phase"], "completed")
            self.assertEqual(result["steps"][0]["hmt_sidecar_status"], "failed")

    def test_failed_hmt_retries_before_the_next_claim_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 1)
            hmt_calls = 0
            hmt_finished = threading.Event()
            hmt_published = threading.Event()
            research_calls = 0

            def publish(*args, **kwargs):
                outcome = publish_hmt_sidecar(*args, **kwargs)
                if outcome.get("accepted"):
                    hmt_published.set()
                return outcome

            def executor(
                *,
                store: ProofStateStore,
                action: dict,
                session_plan: dict,
                **_: object,
            ) -> dict:
                nonlocal hmt_calls, research_calls
                if action.get("periodic_hmt"):
                    hmt_calls += 1
                    if hmt_calls == 1:
                        hmt_finished.set()
                        return {
                            "run_id": "failed-hmt",
                            "actor_role": "writer",
                            "status": "failed",
                            "returncode": 1,
                            "patch": None,
                            "patch_error": "synthetic transient failure",
                            "usage": {},
                        }
                    source = store.state_dir / "artifacts" / "staging" / "retried-hmt.tex"
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text(HMT_LATEX, encoding="utf-8")
                    hmt_finished.set()
                    return {
                        "run_id": "retried-hmt",
                        "actor_role": "writer",
                        "status": "completed",
                        "returncode": 0,
                        "patch_error": "",
                        "usage": {},
                        "patch": {
                            "schema_version": SCHEMA_VERSION,
                            "problem_id": store.problem_id,
                            "base_revision": session_plan["state_revision"],
                            "actor_role": "writer",
                            "target_id": "root",
                            "operations": [
                                {
                                    "op": "attach_artifact",
                                    "artifact_id": "retried-hmt",
                                    "artifact_type": "human_readable_mathematical_text",
                                    "path": str(source),
                                    "content_summary": "The retry records the cumulative partial result.",
                                    "metadata": {"title": "Retried HMT"},
                                }
                            ],
                        },
                    }

                research_calls += 1
                if research_calls in {1, 3}:
                    self.assertTrue(hmt_finished.wait(1.0))
                    hmt_finished.clear()
                if research_calls == 3:
                    # Compilation is now asynchronous too. Keep research
                    # active long enough to observe the successful retry.
                    self.assertTrue(hmt_published.wait(5.0))
                actor_role = str(session_plan.get("actor_role") or actor_role_for_action(action))
                artifact_id = f"research-during-hmt-retry-{research_calls}"
                return {
                    "run_id": artifact_id,
                    "actor_role": actor_role,
                    "status": "completed",
                    "returncode": 0,
                    "usage": {},
                    "patch_error": "",
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
                                "content": "Research continued while HMT authoring retried.",
                                "content_summary": "Synthetic retry regression evidence.",
                            }
                        ],
                    },
                }

            with (
                patch("agents.generation.phase2.hmt_sidecar.integrated_claim_count", return_value=10),
                patch("agents.generation.phase2.workflow.publish_hmt_sidecar", side_effect=publish),
            ):
                result = run_workflow(
                    store,
                    steps=3,
                    execute=True,
                    parallel_librarian_verifier=False,
                    parallel_branches=0,
                    write_on_stop=False,
                    write_console=False,
                    executor=_declare_parallel_local_executor(executor),
                )

            self.assertEqual(hmt_calls, 2)
            self.assertEqual(
                [item["status"] for item in result["hmt_sidecar_results"]],
                ["failed", "completed"],
            )
            self.assertEqual(read_hmt_catalog(store)[0]["artifact_id"], "retried-hmt")

    def test_hmt_manifest_and_prompt_are_one_shot_and_non_certifying(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ, {"ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL": "10"}
        ):
            store = self._store(tmpdir)
            self._set_revision(store, 1)
            self._set_integrated_claim_count(store, 10)
            source_revision = store.get_revision()
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
        self.assertEqual(packet["source_revision"], source_revision)
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
            self._set_revision(store, 1)
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
                f"payload = {{'schema_version':{SCHEMA_VERSION},'problem_id':'hmt-test','base_revision':1,"
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
                enforce_backend_contract=False,
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
