from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.cli import _apply_completion_policy
from agents.generation.phase2.codex_runner import build_session_prompt
from agents.generation.phase2.completion_policy import (
    CANONICAL_STOP_REASON_CODES,
    LANGUAGE_DEBT_TYPES,
    classify_stop_reason,
    detect_soft_wording,
    evaluate_partial_stop,
    latest_root_intent_resolution,
    normalize_completion_policy,
    parse_root_intent,
    partial_stop_progress_signals,
    record_root_intent_resolution,
)
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.report import build_markdown_report
from agents.generation.phase2.result_status import classify_state
from agents.generation.phase2.scheduler import _action, next_action
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import _step_limit_action, _stop_writer_action, _wall_limit_action

SOFT_MARKDOWN = (
    "## Problem\n\n"
    "Prove that every strongly labelled comb admits a very-free rational tooth.\n\n"
    "Try to find any partial result if possible; partial progress is acceptable, and any indication "
    "of the general mechanism would already be interesting.\n"
)


def _synthetic_state(
    *,
    policy: str = "full_proof_first",
    remaining_tokens: int = 1_000_000,
    run_status: str = "running",
    claims: list[dict[str, Any]] | None = None,
    routes: list[dict[str, Any]] | None = None,
    inferences: list[dict[str, Any]] | None = None,
    debts: list[dict[str, Any]] | None = None,
    research_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "problem_state": {
            "problem_id": "policy-test",
            "root_statement": "Target theorem.",
            "completion_policy": policy,
            "remaining_token_budget": remaining_tokens,
            "run_status": run_status,
            "current_revision": 3,
            "max_reduction_depth": 4,
        },
        "claims": claims if claims is not None else [_claim("root", 0, root_impact=1.0)],
        "routes": routes or [],
        "inferences": inferences or [],
        "debts": debts or [],
        "runs": [],
        "recent_runs": [],
        "retrieval_cards": [],
        "theorem_library_entries": [],
        "final_artifacts": [],
        "research_artifacts": research_artifacts or [],
    }


def _claim(claim_id: str, depth: int, *, root_impact: float = 0.5, validation_status: str = "untested") -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "statement": claim_id,
        "hypotheses": "",
        "conditions_json": "[]",
        "tags_json": "[]",
        "root_impact": root_impact,
        "reduction_depth": depth,
        "validation_status": validation_status,
        "lifecycle_status": "active",
        "parent_ids_json": json.dumps(["root"] if claim_id != "root" else []),
    }


class CompletionPolicyParsingTest(unittest.TestCase):
    def test_normalize_and_reject(self) -> None:
        self.assertEqual("full_proof_first", normalize_completion_policy(None))
        self.assertEqual("partial_ok", normalize_completion_policy("partial-ok"))
        self.assertEqual("publication_ready", normalize_completion_policy("publication-ready"))
        with self.assertRaises(ValueError):
            normalize_completion_policy("whatever_mode")

    def test_soft_wording_detected_but_never_flips_policy(self) -> None:
        phrases = detect_soft_wording(SOFT_MARKDOWN)
        self.assertIn("any partial result", phrases)
        self.assertIn("partial progress is acceptable", phrases)
        self.assertIn("any indication", phrases)

        resolution = parse_root_intent(SOFT_MARKDOWN, completion_policy="full_proof_first")
        self.assertEqual("prove_full_statement", resolution["resolved_intent"])
        self.assertTrue(resolution["soft_wording_detected"])
        self.assertFalse(resolution["policy_flipped_by_wording"])
        self.assertEqual("full_proof_first", resolution["completion_policy"])

    def test_explicit_flag_resolves_exploratory_intent(self) -> None:
        resolution = parse_root_intent(SOFT_MARKDOWN, completion_policy="partial_ok")
        self.assertEqual("explore_partial_results", resolution["resolved_intent"])
        audit = parse_root_intent("Audit this.", completion_policy="full_proof_first", research_mode="paper_solution_audit")
        self.assertEqual("audit_or_problem_refinement", audit["resolved_intent"])

    def test_hard_wording_has_no_soft_phrases(self) -> None:
        self.assertEqual([], detect_soft_wording("Prove the full classification theorem."))


class CompletionPolicyStoreTest(unittest.TestCase):
    def test_column_migration_default_and_explicit_setter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("policy-store-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")

            self.assertEqual("full_proof_first", store.get_completion_policy())
            state = store.get_state()
            self.assertEqual("full_proof_first", state["problem_state"]["completion_policy"])

            result = store.set_completion_policy("partial_ok", reason="operator asked", source="cli")
            self.assertEqual("partial_ok", store.get_completion_policy())
            self.assertEqual("full_proof_first", result["previous"])
            with self.assertRaises(ValueError):
                store.set_completion_policy("laziness")

            with store.connect() as conn:
                events = conn.execute(
                    "SELECT payload_json FROM events WHERE event_type = 'completion_policy'"
                ).fetchall()
            self.assertEqual(1, len(events))
            payload = json.loads(events[0]["payload_json"])
            self.assertEqual("partial_ok", payload["to"])

    def test_root_intent_resolution_recorded_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("root-intent-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(SOFT_MARKDOWN)

            first = record_root_intent_resolution(store)
            self.assertEqual("prove_full_statement", first["resolved_intent"])
            self.assertTrue(first["soft_phrases"])

            second = record_root_intent_resolution(store)
            self.assertTrue(second.get("already_recorded"))

            latest = latest_root_intent_resolution(store)
            self.assertEqual("prove_full_statement", latest["resolved_intent"])
            self.assertIn("never flips", latest["note"])

    def test_cli_helper_persists_explicit_flag_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("cli-policy-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(SOFT_MARKDOWN)

            _apply_completion_policy(store, argparse.Namespace())
            self.assertEqual("full_proof_first", store.get_completion_policy())

            _apply_completion_policy(store, argparse.Namespace(completion_policy=None))
            self.assertEqual("full_proof_first", store.get_completion_policy())

            _apply_completion_policy(store, argparse.Namespace(completion_policy="partial_ok"))
            self.assertEqual("partial_ok", store.get_completion_policy())
            self.assertEqual("explore_partial_results", latest_root_intent_resolution(store)["resolved_intent"])


class PartialStopGuardTest(unittest.TestCase):
    def test_active_plausible_route_blocks_stop(self) -> None:
        state = _synthetic_state(
            claims=[_claim("root", 0, root_impact=1.0), _claim("lemma", 1)],
            routes=[{"route_id": "r1", "conclusion_claim_id": "lemma", "status": "active", "relation_to_parent": "sufficient", "label": "r1", "failure_fingerprint": ""}],
            inferences=[{"inference_id": "i1", "route_id": "r1", "conclusion_claim_id": "lemma", "validation_status": "plausible", "premise_claim_ids": []}],
        )
        decision = evaluate_partial_stop(state)
        self.assertFalse(decision["allow"])
        self.assertIn("r1", decision["progress_signals"]["active_plausible_routes"])

    def test_verifier_ready_route_blocks_stop(self) -> None:
        state = _synthetic_state()
        decision = evaluate_partial_stop(state, verifier_ready_routes=[{"route_id": "r-ready"}])
        self.assertFalse(decision["allow"])
        self.assertEqual(["r-ready"], decision["progress_signals"]["verifier_ready_routes"])

    def test_actionable_narrowed_blocker_blocks_stop(self) -> None:
        state = _synthetic_state(
            debts=[
                {
                    "debt_id": "d1",
                    "owner_type": "claim",
                    "owner_id": "root",
                    "status": "active",
                    "severity": "major",
                    "debt_type": "gap",
                    "obligation": "Narrowed bottleneck: prove the comb-smoothing lemma.",
                    "suggested_next_target": "root",
                    "repeated_count": 0,
                }
            ]
        )
        decision = evaluate_partial_stop(state)
        self.assertFalse(decision["allow"])
        self.assertIn("d1", decision["progress_signals"]["narrowed_actionable_blockers"])

    def test_productive_branch_keep_exploiting_blocks_stop(self) -> None:
        state = _synthetic_state(
            claims=[_claim("root", 0, root_impact=1.0), _claim("lemma", 1, validation_status="informally_verified")],
            routes=[{"route_id": "r2", "conclusion_claim_id": "lemma", "status": "active", "relation_to_parent": "sufficient", "label": "r2", "failure_fingerprint": ""}],
            inferences=[{"inference_id": "i2", "route_id": "r2", "conclusion_claim_id": "lemma", "validation_status": "informally_verified", "premise_claim_ids": []}],
        )
        signals = partial_stop_progress_signals(state)
        self.assertIn("r2", signals["productive_branches"])
        decision = evaluate_partial_stop(state)
        self.assertFalse(decision["allow"])

    def test_untried_high_score_route_blocks_stop(self) -> None:
        state = _synthetic_state(
            routes=[{"route_id": "r-untried", "conclusion_claim_id": "root", "status": "active", "relation_to_parent": "sufficient", "label": "fresh", "failure_fingerprint": ""}],
        )
        signals = partial_stop_progress_signals(state)
        self.assertIn("r-untried", signals["untried_high_score_routes"])
        decision = evaluate_partial_stop(state)
        self.assertFalse(decision["allow"])

    def test_partial_ok_policy_allows_stop_despite_signals(self) -> None:
        state = _synthetic_state(policy="partial_ok")
        decision = evaluate_partial_stop(state, verifier_ready_routes=[{"route_id": "r-ready"}])
        self.assertTrue(decision["allow"])
        self.assertEqual("user_partial_mode", decision["stop_reason_code"])

    def test_exhausted_budget_allows_stop_despite_signals(self) -> None:
        state = _synthetic_state(remaining_tokens=0)
        decision = evaluate_partial_stop(state, verifier_ready_routes=[{"route_id": "r-ready"}])
        self.assertTrue(decision["allow"])
        self.assertEqual("exhausted_budget", decision["stop_reason_code"])

        blocked_budget = evaluate_partial_stop(_synthetic_state(), budget_allowed=False)
        self.assertTrue(blocked_budget["allow"])
        self.assertEqual("exhausted_budget", blocked_budget["stop_reason_code"])

    def test_operator_stop_allows_stop(self) -> None:
        state = _synthetic_state(run_status="stopping")
        decision = evaluate_partial_stop(state, verifier_ready_routes=[{"route_id": "r-ready"}])
        self.assertTrue(decision["allow"])
        self.assertEqual("operator_stop", decision["stop_reason_code"])

    def test_advisor_partial_transition_allows_stop_with_recorded_code(self) -> None:
        state = _synthetic_state(
            research_artifacts=[
                {
                    "artifact_id": "adv-1",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 3,
                    "metadata_json": json.dumps(
                        {
                            "partial_mode_transition": True,
                            "partial_mode_transition_reason": "every route family is exhausted",
                            "partial_mode_stop_reason_code": "failed_route_family",
                        }
                    ),
                }
            ],
        )
        decision = evaluate_partial_stop(state, verifier_ready_routes=[])
        self.assertTrue(decision["allow"])
        self.assertEqual("failed_route_family", decision["stop_reason_code"])
        self.assertEqual("adv-1", decision["advisor_partial_transition"]["artifact_id"])

    def test_classifier_codes(self) -> None:
        refuted = _synthetic_state(claims=[_claim("root", 0, root_impact=1.0, validation_status="refuted")])
        self.assertEqual("refuted_statement", classify_stop_reason(refuted))

        citation = _synthetic_state(
            debts=[
                {
                    "debt_id": "d-cite",
                    "owner_type": "claim",
                    "owner_id": "root",
                    "status": "active",
                    "severity": "blocking",
                    "debt_type": "missing_reference",
                    "obligation": "Locate the published theorem with a precise citation.",
                    "suggested_next_target": "",
                    "repeated_count": 0,
                }
            ]
        )
        self.assertEqual("missing_external_theorem", classify_stop_reason(citation))

        dead_routes = _synthetic_state(
            routes=[{"route_id": "r-dead", "conclusion_claim_id": "root", "status": "abandoned", "relation_to_parent": "sufficient", "label": "r", "failure_fingerprint": "f"}],
        )
        self.assertEqual("failed_route_family", classify_stop_reason(dead_routes))

        bare = _synthetic_state()
        self.assertEqual("unresolved_construction", classify_stop_reason(bare))
        self.assertTrue(classify_stop_reason(bare) in CANONICAL_STOP_REASON_CODES)


class SchedulerPartialStopGuardTest(unittest.TestCase):
    """Soft markdown + drift conditions: the guard decides whether the drift
    stop actually fires, based only on the explicit policy."""

    def _drift_store(self, tmpdir: str, *, with_actionable_blocker: bool) -> ProofStateStore:
        store = ProofStateStore(
            "scheduler-partial-stop-guard" + ("-blocked" if with_actionable_blocker else "-open"),
            generation_root=Path(tmpdir) / "generation",
        )
        store.init_problem(SOFT_MARKDOWN)
        operations: list[dict[str, Any]] = [
            {
                "op": "add_claim",
                "claim_id": f"meta-{index}",
                "statement": (
                    f"Repair the JSON schema validator and patch schema metadata envelope for inventory step {index}."
                ),
                "parent_ids": ["root"],
                "root_impact": 0.2,
                "reduction_depth": 8,
            }
            for index in range(4)
        ]
        if with_actionable_blocker:
            operations.append(
                {
                    "op": "add_debt",
                    "debt_id": "narrowed-bottleneck",
                    "owner_type": "claim",
                    "owner_id": "root",
                    "debt_type": "gap",
                    "severity": "major",
                    "obligation": "Narrowed bottleneck: prove the comb-smoothing lemma for the root theorem.",
                    "suggested_next_target": "root",
                }
            )
        outcome = apply_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 0,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": operations,
                "rationale": "synthetic recursive bookkeeping drift",
            },
        )
        if not outcome.accepted:
            raise AssertionError(outcome.errors)
        return store

    def test_drift_stop_blocked_under_full_proof_first_with_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._drift_store(tmpdir, with_actionable_blocker=True)
            resolution = record_root_intent_resolution(store)
            self.assertTrue(resolution["soft_wording_detected"])
            self.assertEqual("prove_full_statement", resolution["resolved_intent"])

            action = next_action(store)

            self.assertNotEqual("stop_with_partial_results", action["mode"])

    def test_drift_stop_allowed_under_explicit_partial_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._drift_store(tmpdir, with_actionable_blocker=True)
            store.set_completion_policy("partial_ok", reason="explicit flag", source="cli")

            action = next_action(store)

            self.assertEqual("stop_with_partial_results", action["mode"])
            self.assertEqual("user_partial_mode", action["stop_reason_code"])
            self.assertEqual("partial_ok", action["completion_policy"])
            self.assertEqual("scope_drift_partial", action["terminal_classification"])

    def test_drift_stop_allowed_without_signals_records_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._drift_store(tmpdir, with_actionable_blocker=False)

            action = next_action(store)

            self.assertEqual("stop_with_partial_results", action["mode"])
            self.assertIn(action["stop_reason_code"], CANONICAL_STOP_REASON_CODES)
            self.assertEqual("full_proof_first", action["completion_policy"])


class StopReasonAnnotationTest(unittest.TestCase):
    def test_budget_conversion_records_exhausted_budget(self) -> None:
        action = _action("prove", "root", "", "keep going", {"allowed": False, "reason": "no spendable tokens"})
        self.assertEqual("stop_with_partial_results", action["mode"])
        self.assertEqual("exhausted_budget", action["stop_reason_code"])

    def test_workflow_limit_actions_record_exhausted_budget(self) -> None:
        self.assertEqual("exhausted_budget", _step_limit_action(12)["stop_reason_code"])
        self.assertEqual("exhausted_budget", _wall_limit_action(3600)["stop_reason_code"])

    def test_stop_writer_action_carries_stop_reason_code(self) -> None:
        writer_action = _stop_writer_action(
            {"reason": "workflow step limit reached (12 steps)", "stop_reason_code": "exhausted_budget", "terminal_classification": "step_limited_partial"}
        )
        self.assertEqual("exhausted_budget", writer_action["stop_reason_code"])
        self.assertTrue(writer_action["write_existing_proofs_on_stop"])


class ReportClassificationTest(unittest.TestCase):
    def _state(self, claims: list[dict[str, Any]], artifacts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {
            "problem_state": {"root_statement": "Target theorem.", "completion_policy": "full_proof_first"},
            "claims": claims,
            "artifacts": artifacts or [],
            "debts": [],
        }

    def test_statement_likely_false(self) -> None:
        state = self._state([_claim("root", 0, validation_status="refuted")])
        self.assertEqual("statement_likely_false", classify_state(state)["report_classification"])

    def test_weaker_theorem_proved(self) -> None:
        weaker = _claim("weak-lemma", 1, validation_status="informally_verified")
        weaker["tags_json"] = json.dumps(["relation:weaker"])
        state = self._state([_claim("root", 0), weaker])
        result = classify_state(state)
        self.assertEqual("weaker_theorem_proved", result["report_classification"])

    def test_conditional_proof(self) -> None:
        conditional = _claim("cond-lemma", 1, validation_status="informally_verified")
        conditional["conditions_json"] = json.dumps(["assuming the Riemann hypothesis"])
        state = self._state([_claim("root", 0), conditional])
        self.assertEqual("conditional_proof", classify_state(state)["report_classification"])

    def test_partial_progress_and_in_progress(self) -> None:
        partial = _claim("side-lemma", 1, validation_status="informally_verified")
        state = self._state([_claim("root", 0), partial])
        self.assertEqual("partial_progress", classify_state(state)["report_classification"])
        self.assertEqual("in_progress", classify_state(self._state([_claim("root", 0)]))["report_classification"])

    def test_full_theorem_solved(self) -> None:
        root = _claim("root", 0, validation_status="informally_verified")
        root["lifecycle_status"] = "integrated"
        artifacts = [
            {
                "artifact_id": "int-1",
                "artifact_type": "integration_report",
                "created_at": "2026-07-09T00:00:00+00:00",
                "metadata_json": json.dumps(
                    {
                        "claim_id": "root",
                        "integrates": True,
                        "root_alignment": {
                            "relation_to_root": "exact",
                            "target_statement": "Target theorem.",
                            "proved_statement": "Target theorem.",
                            "implication_verified": True,
                        },
                    }
                ),
            },
            {
                "artifact_id": "final-1",
                "artifact_type": "final_proof",
                "created_at": "2026-07-09T00:00:01+00:00",
                "metadata_json": json.dumps({"claim_id": "root"}),
            },
        ]
        result = classify_state(self._state([root], artifacts))
        self.assertEqual("full_theorem_solved", result["report_classification"])
        self.assertEqual("solved", result["public_status"])

    def test_report_renders_classification_and_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("policy-report-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(SOFT_MARKDOWN)
            report = build_markdown_report(store)
        self.assertIn("- Result classification: in_progress", report)
        self.assertIn("- Completion policy: full_proof_first", report)


class CompletionPolicyDirectiveTest(unittest.TestCase):
    def _prompt(self, action: dict[str, Any], actor_role: str) -> str:
        return build_session_prompt(context_path=Path("/tmp/ctx.json"), action=action, actor_role=actor_role)

    def test_advisor_requires_partial_transition_justification(self) -> None:
        prompt = self._prompt({"mode": "triage_routes", "target_id": "root"}, "phd_advisor")
        self.assertIn("partial_mode_transition", prompt)
        self.assertIn("partial_mode_stop_reason_code", prompt)
        self.assertIn("soft wording never", prompt.lower())
        for debt_type in LANGUAGE_DEBT_TYPES:
            self.assertIn(debt_type, prompt)

    def test_default_advisor_block_also_carries_directive(self) -> None:
        prompt = self._prompt({"mode": "reduce", "target_id": "root", "debt_id": "d1"}, "phd_advisor")
        self.assertIn("partial_mode_transition", prompt)

    def test_integration_verifier_requires_weaker_to_root_implication(self) -> None:
        prompt = self._prompt({"mode": "integrate", "target_id": "root", "route_id": "r1"}, "integration_verifier")
        self.assertIn("WEAKER-STATEMENT DISCIPLINE", prompt)
        self.assertIn("implication check from the weaker statement to the root", prompt)
        self.assertIn("root_scope_mismatch", prompt)

    def test_writer_stop_directive_requires_recorded_stop_reason(self) -> None:
        prompt = self._prompt(
            {"mode": "write", "target_id": "root", "write_existing_proofs_on_stop": True, "stop_reason": "x", "stop_reason_code": "exhausted_budget"},
            "writer",
        )
        self.assertIn("never present a partial proof as the final answer unless the stop reason is explicit", prompt)
        self.assertIn("stop_reason_code", prompt)
        self.assertIn("weaker theorem", prompt)

    def test_researcher_language_debt_discipline(self) -> None:
        prompt = self._prompt({"mode": "reduce", "target_id": "root"}, "researcher")
        self.assertIn("never permission to settle for a weaker statement", prompt)
        for debt_type in LANGUAGE_DEBT_TYPES:
            self.assertIn(debt_type, prompt)


class CompletionPolicyManifestTest(unittest.TestCase):
    def test_manifest_carries_policy_card_and_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("policy-manifest-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(SOFT_MARKDOWN)
            manifest = build_context_manifest(store, max_chars=40_000)
            self.assertEqual("full_proof_first", manifest["completion_policy"]["policy"])
            self.assertTrue(
                any("full_proof_first" in instruction for instruction in manifest["instructions"])
            )

            store.set_completion_policy("exploratory")
            manifest = build_context_manifest(store, max_chars=40_000)
            self.assertEqual("exploratory", manifest["completion_policy"]["policy"])


if __name__ == "__main__":
    unittest.main()
