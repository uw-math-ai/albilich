from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2 import cli as cli_mod
from agents.generation.phase2 import workflow as workflow_mod
from agents.generation.phase2.branch_summary import (
    BRANCH_STATUSES,
    build_branch_summaries,
    build_branch_summary,
    render_branch_summary,
)
from agents.generation.phase2.context_builder import build_context_manifest, render_manifest
from agents.generation.phase2.memory_policy import (
    MEMORY_STATUSES,
    artifact_is_raw_log,
    artifact_memory_status,
    canonicalize_debts,
    canonicalize_retrieval_cards,
    claim_memory_status,
    debt_memory_status,
    inference_memory_status,
    route_memory_status,
)
from agents.generation.phase2.models import SCHEMA_VERSION, utc_now
from agents.generation.phase2.monitor import INDEX_HTML
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.report import build_markdown_report
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import _record_execution_metrics, run_workflow


def _make_store(tmpdir: str, problem_id: str) -> ProofStateStore:
    store = ProofStateStore(problem_id, generation_root=Path(tmpdir) / "generation")
    store.init_problem("Target theorem.")
    return store


def _apply(store: ProofStateStore, operations: list[dict], *, actor_role: str = "researcher") -> None:
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": actor_role,
            "target_id": "root",
            "operations": operations,
            "rationale": "test setup",
        },
    )
    if not outcome.accepted:
        raise AssertionError(f"setup patch rejected: {outcome.errors}")


def _completed_execution(store: ProofStateStore, action: dict, session_plan: dict, *, tag: str) -> dict:
    return {
        "run_id": f"run-{tag}",
        "actor_role": "researcher",
        "status": "completed",
        "returncode": 0,
        "wall_time_seconds": 2.0,
        "peak_memory_mb": 1.0,
        "usage": {"input_tokens": 10, "output_tokens": 5, "reasoning_output_tokens": 0, "total_tokens": 15},
        "session_id": f"session-{tag}",
        "patch": {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": session_plan["state_revision"],
            "actor_role": "researcher",
            "target_id": action.get("target_id", "root"),
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": f"dossier-{tag}",
                    "artifact_type": "proof_dossier",
                    "content": f"Progress notes for pass {tag}.",
                    "metadata": {"target_id": action.get("target_id", "root")},
                }
            ],
        },
        "patch_error": "",
        "output_artifact_ids": [f"dossier-{tag}"],
        "final_message_path": "",
        "log_path": "",
        "model": "fake",
        "reasoning_effort": "xhigh",
        "sandbox": "workspace-write",
        "web_search": "disabled",
    }


class MemoryStatusClassifierTests(unittest.TestCase):
    def test_classifier_uses_the_advice_vocabulary(self) -> None:
        self.assertEqual(claim_memory_status({"validation_status": "informally_verified", "lifecycle_status": "active"}), "verified")
        self.assertEqual(claim_memory_status({"validation_status": "refuted", "lifecycle_status": "active"}), "failed")
        self.assertEqual(claim_memory_status({"validation_status": "plausible", "lifecycle_status": "superseded"}), "superseded")
        self.assertEqual(claim_memory_status({"validation_status": "plausible", "lifecycle_status": "abandoned"}), "failed")
        self.assertEqual(claim_memory_status({"validation_status": "challenged", "lifecycle_status": "active"}), "blocked")
        self.assertEqual(claim_memory_status({"validation_status": "untested", "lifecycle_status": "active"}), "candidate")

        self.assertEqual(route_memory_status({"status": "integrated"}), "verified")
        self.assertEqual(route_memory_status({"status": "blocked"}), "blocked")
        self.assertEqual(route_memory_status({"status": "abandoned"}), "failed")
        self.assertEqual(route_memory_status({"status": "superseded"}), "superseded")
        self.assertEqual(route_memory_status({"status": "active"}), "candidate")

        self.assertEqual(inference_memory_status({"validation_status": "formally_verified"}), "verified")
        self.assertEqual(inference_memory_status({"validation_status": "refuted"}), "failed")

        self.assertEqual(debt_memory_status({"status": "active", "severity": "blocking"}), "blocked")
        self.assertEqual(debt_memory_status({"status": "resolved", "severity": "blocking"}), "superseded")
        self.assertEqual(debt_memory_status({"status": "discarded", "severity": "minor"}), "stale")

        self.assertEqual(artifact_memory_status({"artifact_type": "final_proof"}), "verified")
        self.assertEqual(artifact_memory_status({"artifact_type": "construction_failure"}), "failed")
        self.assertEqual(artifact_memory_status({"artifact_type": "advisor_report"}), "background")
        self.assertEqual(artifact_memory_status({"artifact_type": "proof_dossier"}), "candidate")
        self.assertEqual(artifact_memory_status({"artifact_type": "session_failure_report"}), "failed")
        self.assertEqual(
            artifact_memory_status({"artifact_type": "research_notebook", "state_revision": 1}, current_revision=99),
            "stale",
        )
        self.assertTrue(artifact_is_raw_log({"artifact_type": "session_failure_report"}))
        self.assertTrue(artifact_is_raw_log({"artifact_type": "proof_dossier", "artifact_id": "session_failure_run_7"}))
        self.assertFalse(artifact_is_raw_log({"artifact_type": "proof_dossier", "artifact_id": "dossier-1"}))

    def test_every_manifest_item_carries_memory_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "memory-status-manifest-test")
            _apply(
                store,
                [
                    {"op": "attach_artifact", "artifact_id": "lemma-dossier", "artifact_type": "proof_dossier", "content": "Lemma dossier.", "metadata": {"target_id": "root"}},
                    {"op": "add_claim", "claim_id": "lemma-a", "kind": "lemma", "statement": "Auxiliary lemma A holds.", "parent_ids": ["root"], "evidence_artifact_ids": ["lemma-dossier"]},
                    {"op": "add_route", "route_id": "route-a", "conclusion_claim_id": "lemma-a", "strategy": "prove lemma A directly"},
                    {
                        "op": "add_inference",
                        "inference_id": "inf-a",
                        "route_id": "route-a",
                        "conclusion_claim_id": "lemma-a",
                        "premise_claim_ids": [],
                        "validation_status": "plausible",
                        "explanation": "The dossier proves lemma A.",
                        "evidence_artifact_ids": ["lemma-dossier"],
                    },
                    {
                        "op": "add_debt",
                        "debt_id": "debt-a",
                        "owner_type": "claim",
                        "owner_id": "lemma-a",
                        "debt_type": "proof_obligation",
                        "severity": "blocking",
                        "status": "active",
                        "obligation": "Close the remaining boundary case of lemma A.",
                        "suggested_next_target": "lemma-a",
                    },
                ],
            )
            _apply(
                store,
                [
                    {
                        "op": "cache_retrieval_card",
                        "card_id": "card-a",
                        "target_id": "root",
                        "exact_statement": "Known theorem: every widget factors through a gadget.",
                        "source_identifiers": {"title": "Widget Theory"},
                        "source_version": "unit-test",
                        "source_location": "Theorem 2.1",
                        "hypotheses": [],
                        "local_definitions": [],
                        "missing_hypotheses": [],
                        "applicability": {"target_id": "root", "classification": "partial_match"},
                    },
                ],
                actor_role="literature_researcher",
            )
            manifest = build_context_manifest(store, target_id="lemma-a", route_id="route-a", max_chars=80_000)
            for section in ("claims", "routes", "inferences", "debts", "artifacts", "retrieval_cards"):
                items = manifest.get(section) or []
                self.assertTrue(items, f"expected items in manifest.{section}")
                for item in items:
                    self.assertIn(item.get("memory_status"), MEMORY_STATUSES, f"{section} item lacks memory_status: {item}")

    def test_session_failure_artifacts_never_enter_role_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "session-failure-exclusion-test")
            # Realistic path: a failed child session persists a session_failure_*
            # artifact through the metrics recorder.
            outcome = _record_execution_metrics(
                store,
                action={"mode": "prove", "target_id": "root"},
                session_plan={
                    "actor_role": "researcher",
                    "state_revision": store.get_revision(),
                    "context_hash": "ctx",
                    "search_intent": "parallel_direct_solve",
                },
                execution={
                    "run_id": "failed-run-1",
                    "actor_role": "researcher",
                    "status": "failed",
                    "returncode": 1,
                    "wall_time_seconds": 2.0,
                    "peak_memory_mb": 1.0,
                    "usage": {"input_tokens": 1, "output_tokens": 1, "reasoning_output_tokens": 0, "total_tokens": 2},
                    "patch_error": "child session crashed mid-flight",
                    "log_path": "/tmp/child.log",
                    "final_message_path": "",
                },
                status="failed",
                model="fake",
                reasoning_effort="xhigh",
                sandbox="workspace-write",
                web_search="disabled",
            )
            self.assertTrue(outcome["accepted"], outcome["errors"])
            with closing(store.connect()) as conn:
                row = conn.execute(
                    "SELECT artifact_id FROM artifacts WHERE artifact_type = 'session_failure_report'"
                ).fetchone()
            self.assertIsNotNone(row)
            failure_artifact_id = row["artifact_id"]
            # Even a debt that (wrongly) cites the raw log as evidence must not
            # pull it into a role manifest.
            _apply(
                store,
                [
                    {
                        "op": "add_debt",
                        "debt_id": "debt-from-failure",
                        "owner_type": "claim",
                        "owner_id": "root",
                        "debt_type": "proof_obligation",
                        "severity": "blocking",
                        "status": "active",
                        "obligation": "Rerun the failed construction with a bounded certificate.",
                        "suggested_next_target": "root",
                        "source_artifact_ids": [failure_artifact_id],
                    }
                ],
            )
            manifest = build_context_manifest(
                store,
                max_chars=120_000,
                action={"mode": "prove", "target_id": "root", "reason": "test"},
            )
            rendered = render_manifest(manifest)
            self.assertNotIn(failure_artifact_id, rendered)
            self.assertNotIn("session_failure_report", rendered)
            for artifact in manifest.get("artifacts", []):
                self.assertFalse(artifact_is_raw_log(artifact))


class MemoryCanonicalizationTests(unittest.TestCase):
    def test_duplicate_debts_are_reported_not_silently_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "duplicate-debt-test")
            obligation = "Prove the bridge lemma for all bounded sections."
            now = utc_now()
            with closing(store.connect()) as conn:
                for debt_id, fingerprint, first_seen in (
                    ("debt-dup-b", "fp-variant-b", "2026-07-02T00:00:00+00:00"),
                    ("debt-dup-a", "fp-variant-a", "2026-07-01T00:00:00+00:00"),
                ):
                    conn.execute(
                        """
                        INSERT INTO debts(
                            debt_id, owner_type, owner_id, obligation, fingerprint, debt_type,
                            severity, status, first_seen, last_seen, repeated_count,
                            source_artifact_ids_json, suggested_next_target, resolution_evidence_json
                        ) VALUES (?, 'claim', 'root', ?, ?, 'proof_obligation', 'blocking', 'active', ?, ?, 0, '[]', 'root', '[]')
                        """,
                        (debt_id, obligation, fingerprint, first_seen, now),
                    )
                conn.commit()

            canonical, duplicates = canonicalize_debts(store.get_state()["debts"])
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(duplicates[0]["canonical_debt_id"], "debt-dup-a")
            self.assertEqual(duplicates[0]["duplicate_debt_ids"], ["debt-dup-b"])
            self.assertEqual(
                sum(1 for row in canonical if str(row.get("obligation")) == obligation), 1
            )

            manifest = build_context_manifest(store, max_chars=80_000)
            debt_ids = [row["debt_id"] for row in manifest.get("debts", [])]
            self.assertIn("debt-dup-a", debt_ids)
            self.assertNotIn("debt-dup-b", debt_ids)
            hygiene = manifest.get("memory_hygiene", {})
            self.assertEqual(hygiene.get("duplicate_debts", [{}])[0].get("canonical_debt_id"), "debt-dup-a")

    def test_duplicate_retrieval_cards_are_reported_and_collapsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "duplicate-card-test")
            statement = "Every widget factors through a gadget (Widget Theory, Thm 2.1)."
            for index in (1, 2):
                _apply(
                    store,
                    [
                        {
                            "op": "cache_retrieval_card",
                            "card_id": f"card-dup-{index}",
                            "target_id": "root",
                            "exact_statement": statement,
                            "source_identifiers": {"title": "Widget Theory", "copy": index},
                            "source_version": f"v{index}",
                            "source_location": "Theorem 2.1",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {"target_id": "root", "classification": "partial_match"},
                        }
                    ],
                    actor_role="literature_researcher",
                )
            rows = store.get_state()["retrieval_cards"]
            canonical, duplicates = canonicalize_retrieval_cards(rows)
            self.assertEqual(len(canonical), 1)
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(duplicates[0]["duplicate_card_ids"], ["card-dup-2"])

            manifest = build_context_manifest(store, max_chars=80_000)
            card_ids = [row["card_id"] for row in manifest.get("retrieval_cards", [])]
            self.assertEqual(card_ids.count("card-dup-1") + card_ids.count("card-dup-2"), 1)
            hygiene = manifest.get("memory_hygiene", {})
            self.assertTrue(hygiene.get("duplicate_retrieval_cards"))


class BranchSummaryTests(unittest.TestCase):
    def _seed_branch(self, store: ProofStateStore, *, debt_obligation: str, route_status_blocked: bool = False) -> None:
        _apply(
            store,
            [
                {"op": "attach_artifact", "artifact_id": "branch-dossier", "artifact_type": "proof_dossier", "content": "Branch dossier.", "metadata": {"target_id": "lemma-branch"}},
                {"op": "add_claim", "claim_id": "lemma-branch", "kind": "lemma", "statement": "The branch lemma about comb constructions holds.", "parent_ids": ["root"], "evidence_artifact_ids": ["branch-dossier"]},
                {"op": "add_route", "route_id": "route-branch", "conclusion_claim_id": "lemma-branch", "strategy": "attack via labelled comb constructions"},
                {
                    "op": "add_inference",
                    "inference_id": "inf-branch",
                    "route_id": "route-branch",
                    "conclusion_claim_id": "lemma-branch",
                    "premise_claim_ids": [],
                    "validation_status": "plausible",
                    "explanation": "The dossier proves the branch lemma.",
                    "evidence_artifact_ids": ["branch-dossier"],
                },
                {
                    "op": "add_debt",
                    "debt_id": "debt-branch",
                    "owner_type": "route",
                    "owner_id": "route-branch",
                    "debt_type": "proof_obligation",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": debt_obligation,
                    "suggested_next_target": "lemma-branch",
                },
            ],
        )
        if route_status_blocked:
            with closing(store.connect()) as conn:
                conn.execute("UPDATE routes SET status = 'blocked' WHERE route_id = 'route-branch'")
                conn.commit()

    def test_branch_summary_has_exactly_the_doc_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-summary-format-test")
            self._seed_branch(store, debt_obligation="Close the remaining comb-labelling case.")
            summary = build_branch_summary(store, "route-branch")
            self.assertEqual(
                list(summary.keys()),
                [
                    "branch",
                    "goal",
                    "status",
                    "verified_facts",
                    "candidate_facts",
                    "active_blockers",
                    "failed_methods",
                    "useful_sources",
                    "next_recommended_lemma",
                ],
            )
            self.assertEqual(summary["branch"], "route-branch")
            self.assertIn(summary["status"], BRANCH_STATUSES)
            self.assertTrue(any("lemma-branch" in fact for fact in summary["candidate_facts"]))
            self.assertTrue(any("debt-branch" in blocker for blocker in summary["active_blockers"]))
            self.assertIn("lemma-branch", summary["next_recommended_lemma"])
            rendered = render_branch_summary(summary)
            for label in ("Branch:", "Goal:", "Status:", "Verified facts:", "Candidate facts:", "Active blockers:", "Failed methods:", "Useful sources:", "Next recommended lemma:"):
                self.assertIn(label, rendered)

    def test_branch_status_heuristics(self) -> None:
        cases = [
            ("Find a literature citation for the comb factorization theorem.", False, "needs_source"),
            ("Run a bounded CAS computation to enumerate small comb examples.", False, "needs_cas"),
            ("Close the remaining comb-labelling case.", False, "keep_exploiting"),
            ("Close the remaining comb-labelling case.", True, "pause_or_merge"),
        ]
        for obligation, blocked, expected in cases:
            with tempfile.TemporaryDirectory() as tmpdir:
                store = _make_store(tmpdir, "branch-status-heuristic-test")
                self._seed_branch(store, debt_obligation=obligation, route_status_blocked=blocked)
                summary = build_branch_summary(store, "route-branch")
                self.assertEqual(summary["status"], expected, f"obligation={obligation!r} blocked={blocked}")

    def test_manifest_and_report_surface_branch_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-summary-surfacing-test")
            self._seed_branch(store, debt_obligation="Close the remaining comb-labelling case.")
            manifest = build_context_manifest(store, max_chars=120_000)
            summaries = manifest.get("branch_summaries", [])
            self.assertTrue(summaries)
            self.assertLessEqual(len(summaries), 4)
            self.assertEqual(summaries[0]["branch"], "route-branch")
            self.assertEqual(len(build_branch_summaries(store, limit=4)), len(summaries))
            report = build_markdown_report(store)
            self.assertIn("## Branches", report)
            self.assertIn("Branch: route-branch", report)
            self.assertIn("Next recommended lemma:", report)

    def test_irrelevant_prior_artifacts_do_not_enter_branch_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "irrelevant-artifact-exclusion-test")
            self._seed_branch(store, debt_obligation="Close the remaining comb-labelling case.")
            # Prior unrelated work: many orphan claims far from the branch, each
            # with its own working-note artifact.
            operations: list[dict] = []
            for index in range(18):
                operations.append(
                    {
                        "op": "attach_artifact",
                        "artifact_id": f"unrelated-note-{index}",
                        "artifact_type": "research_notebook",
                        "content": f"Old unrelated exploration {index}.",
                        "metadata": {"target_id": f"unrelated-{index}"},
                    }
                )
                operations.append(
                    {
                        "op": "add_claim",
                        "claim_id": f"unrelated-{index}",
                        "kind": "lemma",
                        "statement": f"Unrelated exploratory statement number {index}.",
                        "parent_ids": [],
                        "evidence_artifact_ids": [f"unrelated-note-{index}"],
                    }
                )
            _apply(store, operations)
            manifest = build_context_manifest(
                store,
                target_id="lemma-branch",
                route_id="route-branch",
                max_chars=120_000,
                action={"mode": "prove", "target_id": "lemma-branch", "route_id": "route-branch"},
            )
            artifact_ids = {row["artifact_id"] for row in manifest.get("artifacts", [])}
            self.assertIn("branch-dossier", artifact_ids)
            unrelated_in_manifest = {aid for aid in artifact_ids if aid.startswith("unrelated-note-")}
            self.assertFalse(
                unrelated_in_manifest,
                f"irrelevant prior artifacts leaked into the branch manifest: {sorted(unrelated_in_manifest)}",
            )


class PauseSemanticsTests(unittest.TestCase):
    def test_unexpected_workflow_exception_marks_run_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "abnormal-workflow-exit-test")

            def executor(**_: object) -> dict:
                raise RuntimeError("synthetic executor crash")

            with self.assertRaisesRegex(RuntimeError, "synthetic executor crash"):
                run_workflow(
                    store,
                    steps=1,
                    execute=True,
                    parallel_librarian_verifier=False,
                    write_on_stop=False,
                    write_console=False,
                    executor=executor,
                )

            self.assertEqual(store.get_run_status(), "stopped")
            with closing(store.connect()) as conn:
                event = conn.execute(
                    "SELECT payload_json FROM events WHERE event_type = 'workflow_aborted' ORDER BY event_id DESC LIMIT 1"
                ).fetchone()
            self.assertIsNotNone(event)
            self.assertIn("synthetic executor crash", event["payload_json"])

    def test_attempt_signal_guard_converts_termination_signal(self) -> None:
        installed: dict[int, object] = {}

        def fake_getsignal(signum: int) -> object:
            return f"previous-{int(signum)}"

        def fake_signal(signum: int, handler: object) -> None:
            installed[int(signum)] = handler

        with patch.object(cli_mod.signal, "getsignal", side_effect=fake_getsignal), patch.object(
            cli_mod.signal, "signal", side_effect=fake_signal
        ):
            with self.assertRaises(cli_mod._WorkflowTerminationSignal):
                with cli_mod._workflow_termination_guard():
                    handler = installed[int(cli_mod.signal.SIGTERM)]
                    self.assertTrue(callable(handler))
                    handler(cli_mod.signal.SIGTERM, None)

        self.assertEqual(installed[int(cli_mod.signal.SIGTERM)], f"previous-{int(cli_mod.signal.SIGTERM)}")

    def test_pause_requested_blocks_new_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "pause-blocks-dispatch-test")
            store.request_pause(reason="operator pause", source="test")
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                return _completed_execution(store, action, session_plan, tag=str(calls["count"]))

            result = run_workflow(
                store,
                steps=3,
                execute=True,
                parallel_librarian_verifier=False,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            self.assertEqual(calls["count"], 0)
            self.assertEqual(store.get_run_status(), "paused")
            last = result["steps"][-1]
            self.assertEqual(last["action"]["mode"], "pause_run")
            self.assertEqual(last["terminal_classification"], "paused")
            timing = store.get_run_timing()
            self.assertTrue(any(event["to"] == "paused" for event in timing["run_control_events"]))

    def test_soft_pause_finishes_current_child_then_pauses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "soft-pause-mid-run-test")
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                # Operator pauses while the first child session is in flight.
                store.request_pause(reason="pause during child", source="test")
                return _completed_execution(store, action, session_plan, tag=str(calls["count"]))

            result = run_workflow(
                store,
                steps=4,
                execute=True,
                parallel_librarian_verifier=False,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            # The in-flight child finished (its patch landed), then no further
            # actions were dispatched.
            self.assertEqual(calls["count"], 1)
            self.assertEqual(store.get_run_status(), "paused")
            self.assertGreaterEqual(store.get_revision(), 1)
            self.assertEqual(result["steps"][-1]["action"]["mode"], "pause_run")

    def test_hard_stop_records_interruption_event_and_blocks_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "hard-stop-test")
            result = store.request_stop(hard=True, reason="operator hard stop", source="test")
            artifact_id = result["interruption_artifact_id"]
            with closing(store.connect()) as conn:
                artifact = conn.execute(
                    "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
                ).fetchone()
                self.assertIsNotNone(artifact)
                self.assertEqual(artifact["artifact_type"], "run_interruption_event")
                self.assertTrue(Path(artifact["path"]).exists())
                interrupted = conn.execute(
                    "SELECT COUNT(*) AS n FROM events WHERE event_type = 'run_interrupted'"
                ).fetchone()["n"]
            self.assertEqual(int(interrupted), 1)

            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                return _completed_execution(store, action, session_plan, tag=str(calls["count"]))

            run_workflow(
                store,
                steps=2,
                execute=True,
                parallel_librarian_verifier=False,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            self.assertEqual(calls["count"], 0)
            self.assertEqual(store.get_run_status(), "stopped")

    def test_hard_stop_watcher_terminates_active_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "hard-stop-watcher-test")
            observed = {"stop_event_set": False}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, stop_event=None, **_: object) -> dict:
                threading.Timer(
                    0.05, lambda: store.request_stop(hard=True, reason="mid-child hard stop", source="test")
                ).start()
                observed["stop_event_set"] = bool(stop_event is not None and stop_event.wait(timeout=10))
                return {
                    "run_id": "hard-stopped-child",
                    "actor_role": "researcher",
                    "status": "cancelled",
                    "returncode": -15,
                    "wall_time_seconds": 0.2,
                    "peak_memory_mb": 1.0,
                    "usage": {"input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 0},
                    "session_id": "",
                    "patch": None,
                    "patch_error": "session terminated by hard stop",
                    "output_artifact_ids": [],
                    "final_message_path": "",
                    "log_path": "",
                    "model": "fake",
                    "reasoning_effort": "xhigh",
                    "sandbox": "workspace-write",
                    "web_search": "disabled",
                }

            old_poll = workflow_mod.RUN_CONTROL_POLL_SECONDS
            workflow_mod.RUN_CONTROL_POLL_SECONDS = 0.05
            try:
                result = run_workflow(
                    store,
                    steps=3,
                    execute=True,
                    parallel_librarian_verifier=False,
                    write_on_stop=True,
                    write_console=False,
                    executor=executor,
                )
            finally:
                workflow_mod.RUN_CONTROL_POLL_SECONDS = old_poll

            self.assertTrue(observed["stop_event_set"], "watcher never set the stop_event for the active child")
            self.assertEqual(store.get_run_status(), "stopped")
            last = result["steps"][-1]
            self.assertEqual(last.get("terminal_classification"), "interrupted")
            # A hard stop must not launch a stop-writer child session.
            self.assertNotIn("stop_writer", last)

    def test_run_timing_separates_wall_active_and_paused(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "run-timing-test")
            _apply(
                store,
                [
                    {
                        "op": "record_run_metrics",
                        "run_id": "timing-run-1",
                        "actor_role": "researcher",
                        "mode": "prove",
                        "target_id": "root",
                        "state_revision": 0,
                        "context_revision": 0,
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "reasoning_output_tokens": 0,
                        "total_tokens": 15,
                        "wall_time_seconds": 30.0,
                        "peak_memory_mb": 1.0,
                        "status": "completed",
                    }
                ],
                actor_role="scheduler",
            )
            with closing(store.connect()) as conn:
                for created_at, payload in (
                    ("2026-07-09T00:00:10+00:00", {"from": "pause_requested", "to": "paused", "reason": "test pause", "source": "test"}),
                    ("2026-07-09T00:00:25+00:00", {"from": "paused", "to": "running", "reason": "test resume", "source": "test"}),
                ):
                    conn.execute(
                        "INSERT INTO events(revision, event_type, payload_json, created_at) VALUES (?, 'run_control', ?, ?)",
                        (store.get_revision(conn), json.dumps(payload), created_at),
                    )
                conn.commit()
            timing = store.get_run_timing()
            self.assertEqual(timing["active_compute_seconds"], 30.0)
            self.assertEqual(timing["paused_seconds"], 15.0)
            self.assertEqual(timing["pause_count"], 1)
            self.assertGreaterEqual(timing["wall_clock_seconds"], 0.0)

            report = build_markdown_report(store)
            self.assertIn("Wall-clock elapsed since run start:", report)
            self.assertIn("Active backend compute (child-session wall time):", report)
            self.assertIn("Paused time (excluded from active compute):", report)
            self.assertIn("| Wall-clock elapsed (seconds) |", report)
            self.assertIn("| Active compute wall time (seconds) | 30.000 |", report)
            self.assertIn("| Paused time (seconds) | 15.000 |", report)
            self.assertIn("## Run Control Events", report)
            self.assertIn("`paused -> running`", report)

    def test_resume_continues_from_latest_accepted_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "resume-revision-test")
            calls = {"count": 0}

            def executor(*, store: ProofStateStore, action: dict, session_plan: dict, **_: object) -> dict:
                calls["count"] += 1
                return _completed_execution(store, action, session_plan, tag=str(calls["count"]))

            run_workflow(
                store,
                steps=2,
                execute=True,
                parallel_librarian_verifier=False,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            revision_after_run = store.get_revision()
            self.assertGreaterEqual(revision_after_run, 2)
            store.request_pause(reason="pause before resume", source="test")
            # Honor the pause (workflow parks the run as paused).
            run_workflow(
                store,
                steps=1,
                execute=True,
                parallel_librarian_verifier=False,
                write_on_stop=False,
                write_console=False,
                executor=executor,
            )
            self.assertEqual(store.get_run_status(), "paused")
            resumed = store.resume_run(reason="resume for planning", source="test")
            self.assertEqual(resumed["run_status"], "running")
            # The next planned session builds on the latest accepted revision,
            # not on any dashboard or cached state.
            plan = run_workflow(store, steps=1, execute=False, write_console=False)
            planned = plan["steps"][0]["session_plan"]
            self.assertEqual(int(planned["state_revision"]), store.get_revision())
            self.assertEqual(int(planned["state_revision"]), revision_after_run)

    def test_cli_pause_resume_and_hard_stop_verbs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "cli-run-control-test")
            with patch.object(cli_mod, "_store", lambda problem, explicit=None: store):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    cli_mod.main(["pause", "cli-run-control-test"])
                self.assertEqual(store.get_run_status(), "pause_requested")
                payload = json.loads(buffer.getvalue())
                self.assertIn("run_timing", payload)

                with redirect_stdout(io.StringIO()):
                    cli_mod.main(["resume", "cli-run-control-test"])
                self.assertEqual(store.get_run_status(), "running")

                with redirect_stdout(io.StringIO()):
                    cli_mod.main(["stop", "cli-run-control-test", "--hard", "--reason", "cli hard stop"])
                self.assertEqual(store.get_run_status(), "stopping")
                with closing(store.connect()) as conn:
                    count = conn.execute(
                        "SELECT COUNT(*) AS n FROM artifacts WHERE artifact_type = 'run_interruption_event'"
                    ).fetchone()["n"]
                self.assertEqual(int(count), 1)

    def test_dashboard_pause_is_labeled_display_only(self) -> None:
        self.assertIn("Pause dashboard", INDEX_HTML)
        self.assertIn("Dashboard paused; Albilich run is still active.", INDEX_HTML)
        # The dashboard points at the CLI for a true run pause.
        self.assertIn("cli pause", INDEX_HTML)


if __name__ == "__main__":
    unittest.main()
