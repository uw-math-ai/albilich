from __future__ import annotations

"""Acceptance tests for the 2026-07-09 update-advice TODOs 1 and 2:

TODO 1 — branch workbench + branch persistence: a productive branch stays
active across next_action calls (nearby-lemma dispatch instead of circling),
the workbench answers proved/blocked/next-lemma and is persisted idempotently
as a branch_workbench artifact, and "stuck but productive" is distinguished
from "stuck and repeating" (same failure fingerprint twice). The advisor
adjudicates branches through metadata.branch_states.

TODO 2 — multi_branch_research: up to N branch-scoped workers per step window
with disjoint branch packets, verified cross-branch facts visible in packets,
one compact all-branches report, and deterministic duplicate-goal suppression.
"""

import json
import argparse
import inspect
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.branch_summary import (
    BRANCH_WORKBENCH_ARTIFACT_TYPE,
    advisor_branch_directive,
    branch_rotation_decision,
    branch_workbench_artifact_id,
    build_branch_workbench,
    render_branch_workbench,
    sync_branch_workbenches,
)
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.cli import _add_parallel_branches_arg
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.report import build_markdown_report
from agents.generation.phase2.research_policy import (
    action_expects_researcher_session,
    action_expects_villain_session,
)
from agents.generation.phase2.scheduler import (
    CIRCLING_INTENT,
    DEFAULT_MULTI_BRANCH_WORKERS,
    MULTI_BRANCH_RESEARCH_MODE_NAME,
    NEARBY_LEMMA_INTENT,
    _branch_goal_fingerprints,
    multi_branch_research_actions,
    next_action,
    normalize_parallel_branches,
)
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import run_workflow


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


def _insert_run(
    store: ProofStateStore,
    *,
    run_id: str,
    mode: str,
    target_id: str,
    route_id: str = "",
    actor_role: str = "researcher",
    search_intent: str = "route_proof_construction",
    status: str = "completed",
    created_at: str,
    output_artifact_ids: list[str] | None = None,
    researcher_work_mode: str = "offline",
) -> None:
    with closing(store.connect()) as conn:
        conn.execute(
            """
            INSERT INTO runs(
                run_id, actor_role, mode, target_id, route_id, state_revision, context_revision,
                session_id, model_profile, model, reasoning_effort, search_setting, search_intent,
                sandbox_setting, budget_requested, input_tokens, cached_input_tokens, output_tokens,
                reasoning_output_tokens, total_tokens, wall_time_seconds, peak_memory_mb, status,
                prompt_context_hash, output_artifact_ids_json, error_artifact_id, created_at,
                researcher_work_mode, work_mode_source, failure_kind
            ) VALUES (?, ?, ?, ?, ?, 1, 1, '', 'default', 'fake', 'xhigh', 'disabled', ?, 'workspace-write',
                      1000, 10, 0, 5, 0, 15, 2.0, 1.0, ?, '', ?, '', ?, ?, 'rotation', '')
            """,
            (
                run_id,
                actor_role,
                mode,
                target_id,
                route_id,
                search_intent,
                status,
                json.dumps(output_artifact_ids or []),
                created_at,
                researcher_work_mode,
            ),
        )
        conn.commit()


def _set_claim_verified(store: ProofStateStore, claim_id: str) -> None:
    with closing(store.connect()) as conn:
        conn.execute(
            "UPDATE claims SET validation_status = 'informally_verified' WHERE claim_id = ?",
            (claim_id,),
        )
        conn.commit()


def _seed_productive_blocked_branch(store: ProofStateStore, *, verified_support: bool = True) -> None:
    """Branch route-main -> lemma-main: blocking debt on the main target plus
    (optionally) a verified support lemma inside the branch cluster."""
    _apply(
        store,
        [
            {"op": "attach_artifact", "artifact_id": "main-dossier", "artifact_type": "proof_dossier", "content": "Main dossier.", "metadata": {"target_id": "lemma-main", "route_id": "route-main"}},
            {"op": "add_claim", "claim_id": "lemma-main", "kind": "lemma", "statement": "The main comb construction lemma holds.", "parent_ids": ["root"], "evidence_artifact_ids": ["main-dossier"]},
            {"op": "add_claim", "claim_id": "lemma-done", "kind": "lemma", "statement": "The labelled comb base case holds.", "parent_ids": ["lemma-main"]},
            {"op": "add_route", "route_id": "route-main", "conclusion_claim_id": "lemma-main", "strategy": "labelled comb constructions"},
            {
                "op": "add_inference",
                "inference_id": "inf-main",
                "route_id": "route-main",
                "conclusion_claim_id": "lemma-main",
                "premise_claim_ids": ["lemma-done"],
                "validation_status": "plausible",
                "explanation": "The dossier reduces the main lemma to the base case.",
                "evidence_artifact_ids": ["main-dossier"],
            },
            {
                "op": "add_debt",
                "debt_id": "debt-main",
                "owner_type": "route",
                "owner_id": "route-main",
                "debt_type": "proof_obligation",
                "severity": "blocking",
                "status": "active",
                "obligation": "Close the remaining comb-labelling degeneration for the main lemma.",
                "suggested_next_target": "lemma-main",
            },
        ],
    )
    if verified_support:
        _set_claim_verified(store, "lemma-done")
    # Two recent researcher passes hammered the main target with real content
    # but did not close it.
    for index in (1, 2):
        _insert_run(
            store,
            run_id=f"run-main-{index}",
            mode="reduce",
            target_id="lemma-main",
            route_id="route-main",
            created_at=f"2020-01-01T00:00:0{index}+00:00",
            output_artifact_ids=["main-dossier"],
        )


def _seed_repeating_failure(store: ProofStateStore) -> None:
    _apply(
        store,
        [
            {
                "op": "attach_artifact",
                "artifact_id": f"obstruction-{index}",
                "artifact_type": "route_obstruction",
                "content": f"Comb collapse obstruction {index}.",
                "metadata": {
                    "target_id": "lemma-main",
                    "route_id": "route-main",
                    "failure_fingerprint": "comb-collapse",
                },
            }
            for index in (1, 2)
        ],
    )


def _seed_multi_branch_problem(store: ProofStateStore, *, routes: int = 4) -> None:
    """Several independent branches (route-a -> claim-a, ...) plus a blocker
    on the spine whose support lemma is another branch's conclusion."""
    letters = "abcde"[:routes]
    operations: list[dict] = []
    for letter in letters:
        operations.append(
            {
                "op": "add_claim",
                "claim_id": f"claim-{letter}",
                "kind": "lemma",
                "statement": f"Branch lemma {letter} about distinct construction {letter} holds.",
                "parent_ids": ["root"],
            }
        )
        operations.append(
            {
                "op": "add_route",
                "route_id": f"route-{letter}",
                "conclusion_claim_id": f"claim-{letter}",
                "strategy": f"construction family {letter}",
            }
        )
    operations.append(
        {
            "op": "add_debt",
            "debt_id": "debt-spine",
            "owner_type": "route",
            "owner_id": "route-a",
            "debt_type": "proof_obligation",
            "severity": "blocking",
            "status": "active",
            "obligation": "Prove the technical support lemma feeding the spine.",
            "suggested_next_target": "claim-b",
        }
    )
    _apply(store, operations)
    _apply(
        store,
        [
            {
                "op": "cache_retrieval_card",
                "card_id": "card-lit",
                "target_id": "root",
                "exact_statement": "A survey theorem about distinct construction families.",
                "source_identifiers": {"title": "Survey"},
                "source_version": "v1",
                "source_location": "Theorem 1",
                "hypotheses": [],
                "local_definitions": [],
                "missing_hypotheses": [],
                "applicability": {"classification": "method_match", "target_id": "root"},
            }
        ],
        actor_role="literature_researcher",
    )


class BranchPersistenceTests(unittest.TestCase):
    def test_productive_branch_stays_active_with_nearby_lemma_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-persistence-productive")
            _seed_productive_blocked_branch(store)
            for _ in range(3):
                action = next_action(store)
                self.assertNotEqual(action.get("search_intent"), CIRCLING_INTENT)
                self.assertNotEqual(action.get("mode"), "triage_routes")
                self.assertEqual(action.get("search_intent"), NEARBY_LEMMA_INTENT, action)
                self.assertEqual(action.get("branch_focus"), "route-main")
                self.assertEqual(action.get("target_id"), "lemma-main")
                directive = action.get("nearby_lemma_directive") or {}
                self.assertIn("bridge lemmas", str(directive.get("instruction") or ""))
                self.assertTrue(directive.get("next_recommended_lemma"))

    def test_stuck_but_productive_vs_stuck_and_repeating(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-persistence-productive-class")
            _seed_productive_blocked_branch(store)
            decision = branch_rotation_decision(store.get_scheduler_state(), "route-main")
            self.assertTrue(decision["continue_branch"])
            self.assertEqual(decision["classification"], "stuck_but_productive")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-persistence-repeating")
            _seed_productive_blocked_branch(store, verified_support=False)
            _seed_repeating_failure(store)
            decision = branch_rotation_decision(store.get_scheduler_state(), "route-main")
            self.assertFalse(decision["continue_branch"])
            self.assertEqual(decision["classification"], "stuck_and_repeating")
            self.assertEqual(decision["repeated_failure_fingerprint"], "comb-collapse")
            action = next_action(store)
            self.assertNotEqual(action.get("search_intent"), NEARBY_LEMMA_INTENT, action)

    def test_rotation_on_no_useful_delta_for_n_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-persistence-stale")
            _seed_productive_blocked_branch(store)
            # Three passes AFTER the last useful delta: the branch goes stale.
            for index in (3, 4, 5):
                _insert_run(
                    store,
                    run_id=f"run-late-{index}",
                    mode="reduce",
                    target_id="lemma-main",
                    route_id="route-main",
                    created_at=f"2099-01-01T00:00:0{index}+00:00",
                    output_artifact_ids=["main-dossier"],
                )
            decision = branch_rotation_decision(store.get_scheduler_state(), "route-main")
            self.assertFalse(decision["continue_branch"])
            self.assertEqual(decision["classification"], "stale")
            self.assertGreaterEqual(decision["passes_since_useful_delta"], 3)


class BranchWorkbenchTests(unittest.TestCase):
    def test_workbench_answers_proved_blocked_and_next_lemma(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-workbench-content")
            _seed_productive_blocked_branch(store)
            workbench = build_branch_workbench(store, "route-main")
            self.assertEqual(workbench["branch_id"], "route-main")
            self.assertTrue(any("lemma-done" in fact for fact in workbench["verified_facts"]))
            self.assertTrue(any("debt-main" in blocker for blocker in workbench["active_blockers"]))
            self.assertTrue(workbench["next_recommended_lemma"])
            self.assertTrue(workbench["similar_lemmas"])
            self.assertTrue(workbench["last_useful_delta"].get("kind"))
            self.assertIn("pause_or_merge", workbench["stop_or_merge_condition"])
            rendered = render_branch_workbench(workbench)
            for label in (
                "Branch:",
                "Similar lemmas worth trying:",
                "Failed methods (do not retry unchanged):",
                "Last useful delta:",
                "Passes since useful delta:",
                "Rotation:",
                "Stop/merge/rotate condition:",
            ):
                self.assertIn(label, rendered)

    def test_workbench_records_failed_methods_not_to_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-workbench-negative-ledger")
            _seed_productive_blocked_branch(store, verified_support=False)
            _seed_repeating_failure(store)
            workbench = build_branch_workbench(store, "route-main")
            self.assertTrue(
                any("comb-collapse" in line for line in workbench["failed_methods_do_not_retry"]),
                workbench["failed_methods_do_not_retry"],
            )

    def test_workbench_persists_idempotently_and_shows_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "branch-workbench-persistence")
            _seed_productive_blocked_branch(store)
            first = sync_branch_workbenches(store)
            artifact_id = branch_workbench_artifact_id("route-main")
            self.assertIn(artifact_id, first["updated"])
            with closing(store.connect()) as conn:
                row = conn.execute(
                    "SELECT artifact_type, producer_role, path FROM artifacts WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["artifact_type"], BRANCH_WORKBENCH_ARTIFACT_TYPE)
            self.assertEqual(row["producer_role"], "scheduler")
            payload = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["branch_id"], "route-main")
            revision_before = store.get_revision()
            second = sync_branch_workbenches(store)
            self.assertEqual(second["updated"], [])
            self.assertIn(artifact_id, second["unchanged"])
            self.assertEqual(store.get_revision(), revision_before)
            manifest = build_context_manifest(
                store,
                target_id="lemma-main",
                route_id="route-main",
                max_chars=120_000,
                action={
                    "mode": "reduce",
                    "target_id": "lemma-main",
                    "route_id": "route-main",
                    "branch_focus": "route-main",
                },
            )
            self.assertEqual(manifest["branch_workbench"]["branch_id"], "route-main")


class AdvisorBranchAdjudicationTests(unittest.TestCase):
    def _attach_advisor_states(self, store: ProofStateStore, states: dict) -> None:
        _apply(
            store,
            [
                {
                    "op": "attach_artifact",
                    "artifact_id": "advisor-branches",
                    "artifact_type": "advisor_report",
                    "content": "Branch adjudication.",
                    "metadata": {"branch_states": states},
                }
            ],
            actor_role="phd_advisor",
        )

    def test_advisor_pause_or_merge_overrides_productive_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "advisor-pause-overrides")
            _seed_productive_blocked_branch(store)
            self._attach_advisor_states(
                store, {"route-main": {"state": "pause_or_merge", "reason": "method exhausted"}}
            )
            state = store.get_scheduler_state()
            directive = advisor_branch_directive(state, "route-main")
            self.assertEqual(directive["state"], "pause_or_merge")
            decision = branch_rotation_decision(state, "route-main")
            self.assertFalse(decision["continue_branch"])
            self.assertEqual(decision["classification"], "exhausted")
            summary = build_branch_workbench(store, "route-main")
            self.assertEqual(summary["status"], "pause_or_merge")
            action = next_action(store)
            self.assertNotEqual(action.get("search_intent"), NEARBY_LEMMA_INTENT, action)

    def test_advisor_keep_exploiting_overrides_repeating_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "advisor-keep-overrides")
            _seed_productive_blocked_branch(store, verified_support=False)
            _seed_repeating_failure(store)
            self._attach_advisor_states(store, {"route-main": "keep_exploiting"})
            decision = branch_rotation_decision(store.get_scheduler_state(), "route-main")
            self.assertTrue(decision["continue_branch"])
            self.assertEqual(decision["advisor_state"], "keep_exploiting")

    def test_stale_advisor_directive_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "advisor-stale-directive")
            _seed_productive_blocked_branch(store)
            self._attach_advisor_states(store, {"route-main": "pause_or_merge"})
            with closing(store.connect()) as conn:
                conn.execute(
                    "UPDATE problem_state SET current_revision = current_revision + 200 WHERE problem_id = ?",
                    (store.problem_id,),
                )
                conn.commit()
            state = store.get_scheduler_state()
            self.assertIsNone(advisor_branch_directive(state, "route-main"))
            decision = branch_rotation_decision(state, "route-main")
            self.assertEqual(decision["advisor_state"], "")


class MultiBranchResearchTests(unittest.TestCase):
    def test_closure_pipeline_does_not_fill_slots_with_exploratory_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "multi-branch-closure-lock")
            _seed_multi_branch_problem(store, routes=4)
            primary = {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "",
                "closure_pipeline_required": True,
                "closure_debt_id": "debt-root",
            }
            planned = multi_branch_research_actions(store, primary, [], parallel_branches=4)
            self.assertEqual(planned, [])

    def test_long_mathematical_session_does_not_get_generic_filler_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "multi-branch-long-session")
            _seed_multi_branch_problem(store, routes=4)
            primary = {
                "mode": "reduce",
                "target_id": "root",
                "route_id": "",
                "long_mathematical_session_required": True,
                "conceptual_invariant_discovery_required": True,
            }
            planned = multi_branch_research_actions(store, primary, [], parallel_branches=4)
            self.assertEqual(planned, [])

    def test_four_workers_planned_with_disjoint_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "multi-branch-four-workers")
            _seed_multi_branch_problem(store, routes=4)
            primary = {"mode": "retrieve", "target_id": "root", "route_id": ""}
            planned = multi_branch_research_actions(store, primary, [], parallel_branches=4)
            self.assertEqual(len(planned), 4, [a.get("multi_branch_worker") for a in planned])
            workers = [str(action.get("multi_branch_worker")) for action in planned]
            self.assertEqual(len(set(workers)), 4)
            self.assertIn("spine", workers)
            self.assertIn("villain_toy_model", workers)
            philosophies = {str(action.get("research_philosophy") or "") for action in planned}
            self.assertIn("main_spine_construction", philosophies)
            self.assertIn("adversarial_probe", philosophies)
            families = {
                str((action.get("branch_diversity_contract") or {}).get("strategy_family") or "")
                for action in planned
            }
            self.assertEqual(len(families), len(planned))
            self.assertNotIn("", families)
            owned_claims: set[str] = set()
            owned_debts: set[str] = set()
            for action in planned:
                self.assertTrue(action.get("parallel_companion"))
                self.assertEqual(action.get("multi_branch_mode"), MULTI_BRANCH_RESEARCH_MODE_NAME)
                self.assertTrue(action.get("branch_focus"))
                self.assertIn("researcher_work_mode", action)
                self.assertIn("information_gain_score", action)
                self.assertIn("expected_value_score", action["information_gain_score"])
                packet = action.get("branch_packet") or {}
                claim_ids = {str(cid) for cid in packet.get("claim_ids", []) if str(cid) != "root"}
                debt_ids = {str(did) for did in packet.get("debt_ids", [])}
                self.assertFalse(claim_ids & owned_claims, f"overlapping claim ownership: {claim_ids & owned_claims}")
                self.assertFalse(debt_ids & owned_debts, f"overlapping debt ownership: {debt_ids & owned_debts}")
                owned_claims |= claim_ids
                owned_debts |= debt_ids

    def test_duplicate_goal_fingerprint_suppresses_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "multi-branch-duplicate-suppression")
            _apply(
                store,
                [
                    {"op": "add_claim", "claim_id": "claim-a", "kind": "lemma", "statement": "Only branch lemma.", "parent_ids": ["root"]},
                    {"op": "add_route", "route_id": "route-a", "conclusion_claim_id": "claim-a", "strategy": "only construction"},
                ],
            )
            state = store.get_scheduler_state()
            unclaimed = multi_branch_research_actions(
                store, {"mode": "retrieve", "target_id": "root", "route_id": ""}, [], parallel_branches=3
            )
            self.assertTrue(unclaimed)
            duplicate_wave_action = {"mode": "reduce", "target_id": "claim-a", "route_id": "route-a"}
            planned = multi_branch_research_actions(
                store,
                {"mode": "retrieve", "target_id": "root", "route_id": ""},
                [duplicate_wave_action],
                parallel_branches=3,
            )
            wave_fingerprints = _branch_goal_fingerprints(state, duplicate_wave_action)
            for action in planned:
                self.assertFalse(
                    _branch_goal_fingerprints(state, action) & wave_fingerprints,
                    f"duplicate goal dispatched: {action}",
                )

    def test_verified_lemma_from_branch_a_visible_in_branch_b_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "multi-branch-cross-visibility")
            _apply(
                store,
                [
                    {"op": "add_claim", "claim_id": "lemma-a", "kind": "lemma", "statement": "Branch A support lemma.", "parent_ids": ["root"]},
                    {"op": "add_claim", "claim_id": "lemma-b", "kind": "lemma", "statement": "Branch B target lemma.", "parent_ids": ["root"]},
                    {"op": "add_claim", "claim_id": "lemma-z", "kind": "lemma", "statement": "Unrelated stray exploration.", "parent_ids": []},
                    {"op": "add_route", "route_id": "route-a", "conclusion_claim_id": "lemma-a", "strategy": "branch A"},
                    {"op": "add_route", "route_id": "route-b", "conclusion_claim_id": "lemma-b", "strategy": "branch B"},
                    {
                        "op": "add_inference",
                        "inference_id": "inf-b",
                        "route_id": "route-b",
                        "conclusion_claim_id": "lemma-b",
                        "premise_claim_ids": ["lemma-a"],
                        "validation_status": "plausible",
                        "explanation": "Branch B consumes branch A's lemma.",
                    },
                ],
            )
            _set_claim_verified(store, "lemma-a")
            manifest = build_context_manifest(
                store,
                target_id="lemma-b",
                route_id="route-b",
                max_chars=120_000,
                action={
                    "mode": "reduce",
                    "target_id": "lemma-b",
                    "route_id": "route-b",
                    "branch_focus": "route-b",
                    "multi_branch_worker": "spine",
                },
            )
            claims = {str(card.get("claim_id")): card for card in manifest.get("claims", [])}
            self.assertIn("lemma-a", claims)
            self.assertEqual(claims["lemma-a"].get("memory_status"), "verified")
            self.assertIn("lemma-b", claims)
            self.assertNotIn("lemma-z", claims, "branch packet leaked an unrelated claim")

    def test_all_branches_compact_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "multi-branch-report")
            _seed_multi_branch_problem(store, routes=4)
            store.set_parallel_branches(4, source="test")
            report = build_markdown_report(store)
            self.assertIn("## Branches", report)
            self.assertIn("multi_branch_research", report)
            self.assertIn("up to 4 simultaneous branch workers", report)
            self.assertGreaterEqual(report.count("Branch: route-"), 2)
            self.assertIn("Rotation:", report)
            self.assertIn("Stop/merge/rotate condition:", report)


class ParallelBranchModeWiringTests(unittest.TestCase):
    def test_multi_branch_defaults_to_three_with_explicit_opt_out(self) -> None:
        parser = argparse.ArgumentParser()
        _add_parallel_branches_arg(parser)

        self.assertEqual(DEFAULT_MULTI_BRANCH_WORKERS, 3)
        self.assertEqual(parser.parse_args([]).parallel_branches, 3)
        self.assertEqual(parser.parse_args(["--parallel-branches", "0"]).parallel_branches, 0)
        self.assertEqual(
            inspect.signature(run_workflow).parameters["parallel_branches"].default,
            DEFAULT_MULTI_BRANCH_WORKERS,
        )

    def test_normalize_and_persist_parallel_branch_mode(self) -> None:
        self.assertEqual(normalize_parallel_branches(0), 0)
        self.assertEqual(normalize_parallel_branches(1), 0)
        self.assertEqual(normalize_parallel_branches(4), 4)
        self.assertEqual(normalize_parallel_branches(9), 5)
        self.assertEqual(normalize_parallel_branches("nope"), 0)
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "parallel-branch-mode-recording")
            result = store.set_parallel_branches(4, source="test")
            self.assertEqual(result["research_parallel_mode"], "multi_branch_research")
            with closing(store.connect()) as conn:
                row = store.get_problem_row(conn)
                event = conn.execute(
                    "SELECT payload_json FROM events WHERE event_type = 'parallel_branch_mode' ORDER BY event_id DESC LIMIT 1"
                ).fetchone()
            self.assertEqual(int(row["parallel_branches"]), 4)
            self.assertEqual(row["research_parallel_mode"], "multi_branch_research")
            self.assertIsNotNone(event)
            self.assertEqual(json.loads(event["payload_json"])["mode"], "multi_branch_research")
            self.assertTrue(store.set_parallel_branches(4, source="test").get("unchanged"))
            with self.assertRaises(ValueError):
                store.set_parallel_branches(1, source="test")
            cleared = store.set_parallel_branches(0, source="test")
            self.assertEqual(cleared["research_parallel_mode"], "")

    def test_workflow_plans_multi_branch_wave_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "parallel-branch-workflow-wave")
            _seed_multi_branch_problem(store, routes=4)
            result = run_workflow(store, steps=1, execute=False, parallel_branches=4)
            self.assertEqual(result["parallel_branches"], 4)
            entry = result["steps"][0]
            parallel_actions = entry.get("parallel_actions", [])
            multi_branch = [a for a in parallel_actions if a.get("multi_branch_worker")]
            self.assertTrue(multi_branch, f"no multi-branch workers planned: {parallel_actions}")
            session_count = sum(
                1
                for a in [entry["action"], *parallel_actions]
                if action_expects_researcher_session(a) or action_expects_villain_session(a)
            )
            self.assertLessEqual(session_count, 4, "the wave exceeded the parallel-branches worker cap")


if __name__ == "__main__":
    unittest.main()
