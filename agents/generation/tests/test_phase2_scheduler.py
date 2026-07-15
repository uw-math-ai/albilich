from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.graph_policy import active_frontier_pressure, build_proof_spine, decomposition_cooldown_active, obvious_duplicate_claim_id, route_scoreboard, supersession_index
from agents.generation.phase2.codex_runner import _persist_normalized_final_patch, actor_role_for_action, attached_artifact_ids, build_session_prompt, extract_patch_from_text, prepare_session, run_metrics_operation
from agents.generation.phase2.context_builder import _fit_manifest, _retrieval_card, _select_artifacts, build_context_manifest, build_resume_delta_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.receipt import build_partial_receipt_inventory, format_partial_receipt_appendix
from agents.generation.phase2.research_policy import DEFAULT_RESEARCH_MODE, normalize_research_mode, theorem_matching_confidence
from agents.generation.phase2.scheduler import _active_main_trunk_pressure, _active_route_for_claim, _advisor_followup_report, _advisor_requested_strict_verifier_action, _advisor_requested_validation_action, _advisor_requested_villain_action, _bottleneck_lock_action, _bottleneck_lock_debt_candidates, _branch_packet_card, _central_obstruction_payload, _claim_target_for_debt, _cooldown_proof_action, _executive_advisor_bottleneck_action, _first_blocking_debt, _frontier_pressure_action, _integration_candidates, _is_exact_citation_debt, _near_solution_spine_synthesis_action, _next_unverified_claim, _proof_architecture_pressure_action, _recursive_meta_drift, _root_refinement_signals, _route_without_inference, _unrouted_proof_candidate, _unrouted_proof_claim_action, _verifier_blocked_citation_action, bottleneck_frontier_summary, next_action, parallel_companion_actions, proof_spine_summary, route_verifier_readiness, verifier_ready_route_summaries
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.workflow import _evidence_boundary_errors, _stop_writer_action, _stop_writer_safety_blocker


def claim(
    claim_id: str,
    depth: int,
    *,
    statement: str = "",
    root_impact: float = 0.5,
    validation_status: str = "untested",
    lifecycle_status: str = "active",
    parent_ids: list[str] | None = None,
) -> dict[str, Any]:
    parent_ids = parent_ids or []
    return {
        "claim_id": claim_id,
        "statement": statement or claim_id,
        "hypotheses": "",
        "root_impact": root_impact,
        "reduction_depth": depth,
        "validation_status": validation_status,
        "lifecycle_status": lifecycle_status,
        "parent_ids": parent_ids,
        "parent_ids_json": json.dumps(parent_ids),
    }


def debt(
    debt_id: str,
    *,
    owner_id: str,
    owner_type: str = "claim",
    suggested_next_target: str = "",
    repeated_count: int = 0,
    last_seen: str = "2026-01-01T00:00:00+00:00",
    severity: str = "blocking",
    status: str = "active",
    obligation: str = "",
    debt_type: str = "gap",
) -> dict[str, Any]:
    return {
        "debt_id": debt_id,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "suggested_next_target": suggested_next_target,
        "repeated_count": repeated_count,
        "last_seen": last_seen,
        "severity": severity,
        "status": status,
        "obligation": obligation or debt_id,
        "debt_type": debt_type,
    }


def route(
    route_id: str,
    *,
    conclusion_claim_id: str,
    status: str = "active",
    relation_to_parent: str = "sufficient",
    failure_fingerprint: str = "",
) -> dict[str, Any]:
    return {
        "route_id": route_id,
        "conclusion_claim_id": conclusion_claim_id,
        "status": status,
        "relation_to_parent": relation_to_parent,
        "failure_fingerprint": failure_fingerprint,
        "label": route_id,
    }


def inference(
    inference_id: str,
    *,
    route_id: str,
    conclusion_claim_id: str,
    validation_status: str = "untested",
) -> dict[str, Any]:
    return {
        "inference_id": inference_id,
        "route_id": route_id,
        "conclusion_claim_id": conclusion_claim_id,
        "validation_status": validation_status,
        "premise_claim_ids": [],
    }


def record_run(
    store: ProofStateStore,
    *,
    base_revision: int,
    run_id: str,
    mode: str,
    target_id: str,
    route_id: str = "",
    search_intent: str = "",
    actor_role: str = "researcher",
    status: str = "completed",
    error_summary: str = "",
) -> None:
    action = {
        "mode": mode,
        "target_id": target_id,
        "route_id": route_id,
        "budget": {"requested_tokens": 0},
    }
    session_plan = {
        "actor_role": actor_role,
        "state_revision": base_revision,
        "model_profile": "test",
        "context_hash": f"context-{run_id}",
    }
    op = run_metrics_operation(
        run_id=run_id,
        action=action,
        session_plan=session_plan,
        usage_payload={},
        status=status,
        wall_time_seconds=1.0,
        model="test-model",
    )
    op["search_intent"] = search_intent
    operations: list[dict[str, Any]] = []
    if error_summary:
        error_artifact_id = f"session_failure_{run_id.replace(':', '_').replace('/', '_')}"
        op["error_artifact_id"] = error_artifact_id
        operations.append(
            {
                "op": "attach_artifact",
                "artifact_id": error_artifact_id,
                "artifact_type": "session_failure_report",
                "content": error_summary,
                "content_summary": error_summary,
                "metadata": {
                    "run_id": run_id,
                    "actor_role": actor_role,
                    "mode": mode,
                    "target_id": target_id,
                    "route_id": route_id,
                    "status": status,
                },
            }
        )
    operations.append(op)
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": base_revision,
            "actor_role": "scheduler",
            "target_id": target_id,
            "operations": operations,
            "rationale": "record synthetic run metrics",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


class Phase2CodexRunnerParsingTest(unittest.TestCase):
    def test_extract_patch_repairs_invalid_latex_json_escape(self) -> None:
        text = r'{"schema_version":1,"operations":[{"op":"attach_artifact","content":"Since \(q\mid N\), continue."}]}'

        patch, error = extract_patch_from_text(text)

        self.assertEqual("", error)
        self.assertIsNotNone(patch)
        assert patch is not None
        self.assertEqual(r"Since \(q\mid N\), continue.", patch["operations"][0]["content"])

    def test_extract_patch_repairs_more_than_64_invalid_latex_json_escapes(self) -> None:
        content = " ".join(rf"\(x_{{{index}}}\)" for index in range(70))
        text = (
            '{"schema_version":1,"operations":[{"op":"attach_artifact","content":"'
            + content
            + '"}]}'
        )

        patch, error = extract_patch_from_text(text)

        self.assertEqual("", error)
        self.assertIsNotNone(patch)
        assert patch is not None
        self.assertEqual(content, patch["operations"][0]["content"])

    def test_extract_patch_repairs_latex_commands_with_valid_json_escape_prefixes(self) -> None:
        text = r'{"schema_version":1,"operations":[{"op":"attach_artifact","content":"\\[\nK=G/C,\qquad J=M/C,\quad \bigwedge\nolimits^2 V,\quad \beta:T\times T\longrightarrow A\\]"}]}'

        patch, error = extract_patch_from_text(text)

        self.assertEqual("", error)
        self.assertIsNotNone(patch)
        assert patch is not None
        content = patch["operations"][0]["content"]
        self.assertIn(r"\qquad", content)
        self.assertIn(r"\bigwedge", content)
        self.assertIn(r"\nolimits", content)
        self.assertIn(r"\beta", content)

    def test_extract_patch_repairs_extra_object_close_before_parallel_signals(self) -> None:
        text = (
            '{"schema_version":1,"operations":[{"op":"cache_retrieval_card",'
            '"metadata":{"content_hashes":{"source":"sha256:abc"}}}],'
            '"parallel_signals":[{"signal_type":"no_hit"}],"rationale":"ok"}'
        )
        malformed = text.replace('"}}}],', '"}}}}],')

        patch, error = extract_patch_from_text(malformed)

        self.assertEqual("", error)
        self.assertIsNotNone(patch)
        assert patch is not None
        self.assertEqual("cache_retrieval_card", patch["operations"][0]["op"])
        self.assertEqual("no_hit", patch["parallel_signals"][0]["signal_type"])

    def test_extract_patch_repairs_extra_object_close_between_operations(self) -> None:
        text = (
            '{"schema_version":1,"operations":[{"op":"cache_retrieval_card",'
            '"card_id":"card-a","exact_statement":"A","source_cache_status":"metadata_only"},'
            '{"op":"attach_artifact","artifact_id":"note-a","artifact_type":"source_adaptation_notes",'
            '"content":"ok"}],"rationale":"ok"}'
        )
        malformed = text.replace('"metadata_only"},{"op"', '"metadata_only"}},{"op"')

        patch, error = extract_patch_from_text(malformed)

        self.assertEqual("", error)
        self.assertIsNotNone(patch)
        assert patch is not None
        self.assertEqual("card-a", patch["operations"][0]["card_id"])
        self.assertEqual("note-a", patch["operations"][1]["artifact_id"])

    def test_persist_normalized_final_patch_keeps_raw_repaired_response(self) -> None:
        text = (
            '{"schema_version":1,"operations":[{"op":"cache_retrieval_card",'
            '"card_id":"card-a","exact_statement":"A","source_cache_status":"metadata_only"},'
            '{"op":"attach_artifact","artifact_id":"note-a","artifact_type":"source_adaptation_notes",'
            '"content":"ok"}],"rationale":"ok"}'
        )
        malformed = text.replace('"metadata_only"},{"op"', '"metadata_only"}},{"op"')
        patch, error = extract_patch_from_text(malformed)
        self.assertEqual("", error)
        self.assertIsNotNone(patch)
        assert patch is not None
        with tempfile.TemporaryDirectory() as tmpdir:
            final_path = Path(tmpdir) / "final_patch.json"
            final_path.write_text(malformed, encoding="utf-8")

            _persist_normalized_final_patch(final_path, malformed, patch)

            self.assertEqual(patch, json.loads(final_path.read_text(encoding="utf-8")))
            self.assertEqual(malformed, (final_path.parent / "final_patch.raw.txt").read_text(encoding="utf-8"))

    def test_persist_normalized_final_patch_canonicalizes_operation_aliases(self) -> None:
        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "p",
            "base_revision": 0,
            "actor_role": "researcher",
            "target_id": "root",
            "operations": [
                {
                    "operation": "attach_artifact",
                    "artifact": {
                        "artifact_id": "nested-note",
                        "artifact_type": "research_notebook",
                        "content": "notes",
                    },
                }
            ],
            "rationale": "canonicalize aliases",
        }
        raw = json.dumps(patch)
        with tempfile.TemporaryDirectory() as tmpdir:
            final_path = Path(tmpdir) / "final_patch.json"

            _persist_normalized_final_patch(final_path, raw, patch)

            stored = json.loads(final_path.read_text(encoding="utf-8"))
            self.assertEqual("attach_artifact", stored["operations"][0]["op"])
            self.assertEqual("nested-note", stored["operations"][0]["artifact_id"])

    def test_attached_artifact_ids_handles_operation_alias_and_nested_artifact(self) -> None:
        patch = {
            "operations": [
                {"operation": "attach_artifact", "artifact": {"artifact_id": "nested-note"}},
                {"op": "add_artifact", "artifact_id": "flat-note"},
            ]
        }

        self.assertEqual(["nested-note", "flat-note"], attached_artifact_ids(patch))


class Phase2PartialReceiptTest(unittest.TestCase):
    def test_partial_receipt_lists_verified_side_lemmas_and_other_claims(self) -> None:
        claims = [
            claim("root", 0, validation_status="untested"),
            claim("lem-a", 1, validation_status="informally_verified"),
            claim("lem-b", 1, validation_status="untested"),
            claim("lem-c", 2, validation_status="formally_verified"),
        ]

        inventory = build_partial_receipt_inventory(claims)

        self.assertEqual([row["claim_id"] for row in inventory["verified_side_lemmas"]], ["lem-a", "lem-c"])
        self.assertEqual([row["claim_id"] for row in inventory["other_claims"]], ["root", "lem-b"])
        appendix = format_partial_receipt_appendix(claims)
        self.assertIn("## Verified Side Lemmas", appendix)
        self.assertIn("`lem-a` validation=informally_verified", appendix)
        self.assertIn("`lem-c` validation=formally_verified", appendix)
        self.assertIn("## Claim Status Ledger", appendix)
        self.assertIn("`root` validation=untested", appendix)
        self.assertIn("`lem-b` validation=untested", appendix)


class Phase2SchedulerDebtSelectionTest(unittest.TestCase):
    def test_citation_first_is_balanced_compatibility_alias(self) -> None:
        self.assertEqual(normalize_research_mode("citation_first"), "balanced")

    def test_default_research_mode_is_hard_problem(self) -> None:
        self.assertEqual(DEFAULT_RESEARCH_MODE, "hard_problem")
        self.assertEqual(normalize_research_mode(None), "hard_problem")

    def test_verified_statement_repair_supersedes_stale_parent_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("statement-repair-supersession-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {"op": "add_claim", "claim_id": "old-wording", "kind": "lemma", "statement": "The old maximal wording.", "parent_ids": ["root"]},
                        {"op": "add_route", "route_id": "route-old-wording", "conclusion_claim_id": "old-wording", "strategy": "prove old wording"},
                    ],
                    "rationale": "seed stale wording",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            repair = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": setup.revision,
                    "actor_role": "researcher",
                    "target_id": "old-wording",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "repair-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "Proof of corrected wording.",
                            "metadata": {"target_id": "repaired-wording", "artifact_roi": "route_repaired"},
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "repaired-wording",
                            "kind": "lemma",
                            "statement": "The repaired proper-subgroup wording.",
                            "parent_ids": ["old-wording"],
                            "tags": ["statement_repair"],
                            "evidence_artifact_ids": ["repair-dossier"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-repaired-wording",
                            "conclusion_claim_id": "repaired-wording",
                            "strategy": "prove repaired wording",
                            "evidence_artifact_ids": ["repair-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-repaired-wording",
                            "route_id": "route-repaired-wording",
                            "conclusion_claim_id": "repaired-wording",
                            "evidence_artifact_ids": ["repair-dossier"],
                            "explanation": "The dossier proves the repaired statement.",
                            "validation_status": "plausible",
                        },
                    ],
                    "rationale": "repair stale wording",
                },
            )
            self.assertTrue(repair.accepted, repair.errors)
            verified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": repair.revision,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "repaired-wording",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "verif-repaired-wording",
                            "artifact_type": "verification_report",
                            "content": "verified",
                            "metadata": {
                                "verdict": "verified",
                                "verification_report": {"critical_errors": [], "gaps": [], "blocking_gap": False},
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-repaired-wording",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verif-repaired-wording"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "repaired-wording",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verif-repaired-wording"],
                        },
                    ],
                    "rationale": "verify repaired wording",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)
            state = store.get_state()

        claims = {row["claim_id"]: row for row in state["claims"]}
        routes = {row["route_id"]: row for row in state["routes"]}
        self.assertEqual(claims["old-wording"]["lifecycle_status"], "superseded")
        self.assertEqual(routes["route-old-wording"]["status"], "superseded")
        supersession = supersession_index(state)
        self.assertIn("old-wording", supersession["superseded_claim_ids"])
        self.assertIn("route-old-wording", supersession["superseded_route_ids"])

    def test_manifest_proof_spine_exposes_verified_facts_supersession_and_decisive_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("proof-spine-context-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-decide-bridge",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "blocking_bridge",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Prove or refute the exact bridge theorem.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "seed decisive bridge",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            action = {
                "mode": "prove",
                "target_id": "root",
                "decisive_theorem_test_required": True,
                "search_intent": "decisive_theorem_test",
            }
            manifest = build_context_manifest(store, action=action, max_chars=30_000)

        self.assertIn("proof_spine", manifest)
        self.assertEqual(manifest["proof_spine"]["decisive_theorem_test"]["debt_id"], "debt-decide-bridge")
        self.assertEqual(manifest["researcher_packet"]["proof_spine"]["decisive_theorem_test"]["debt_id"], "debt-decide-bridge")

    def test_manifest_proof_spine_prefers_advisor_bottleneck_over_older_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("advisor-proof-spine-context-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-obsolete-classification",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "blocking_bridge",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Prove or refute the obsolete classification theorem.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "seed an older theorem-shaped debt",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            advisor_obligation = "No second exceptional elementary-abelian lift exists."
            manifest = build_context_manifest(
                store,
                action={
                    "mode": "prove",
                    "target_id": "root",
                    "search_intent": "executive_advisor_bottleneck_lock",
                    "advisor_decisive_missing_statement": advisor_obligation,
                },
                max_chars=30_000,
            )

        decisive = manifest["proof_spine"]["decisive_theorem_test"]
        self.assertEqual(decisive["policy"], "advisor-decisive-theorem-test")
        self.assertEqual(decisive["theorem_obligation"], advisor_obligation)
        self.assertNotEqual(decisive["debt_id"], "debt-obsolete-classification")
        self.assertEqual(
            manifest["researcher_packet"]["proof_spine"]["decisive_theorem_test"]["theorem_obligation"],
            advisor_obligation,
        )

    def test_proof_spine_verifier_targets_selected_claim_not_advisor_bottleneck(self) -> None:
        state = {
            "claims": [
                claim("root", 0, statement="Root theorem."),
                claim("local-lemma", 1, statement="Exact local lemma to verify.", parent_ids=["root"]),
            ],
            "debts": [],
            "routes": [],
            "inferences": [],
        }

        spine = build_proof_spine(
            state,
            action={
                "mode": "prove",
                "target_id": "local-lemma",
                "search_intent": "verify_ready_route",
                "verify_ready_route_policy": True,
                "strict_verifier_scope": "single_route_verification_packet",
                "advisor_decisive_missing_statement": "Different root-level advisor theorem.",
            },
            target_id="local-lemma",
        )

        decisive = spine["decisive_theorem_test"]
        self.assertEqual(decisive["policy"], "selected-route-verification-test")
        self.assertEqual(decisive["target_id"], "local-lemma")
        self.assertEqual(decisive["theorem_obligation"], "Exact local lemma to verify.")

    def test_proof_spine_suppresses_debt_explicitly_refuted_by_confirmed_counterexample(self) -> None:
        state = {
            "claims": [claim("root", 0, statement="Root theorem.")],
            "debts": [
                {
                    "debt_id": "debt-refuted-classification",
                    "owner_id": "root",
                    "debt_type": "gap",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Prove or refute the obsolete classification theorem.",
                    "suggested_next_target": "root",
                },
                {
                    "debt_id": "debt-live-theorem",
                    "owner_id": "root",
                    "debt_type": "gap",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Prove or refute the live replacement theorem.",
                    "suggested_next_target": "root",
                },
            ],
            "routes": [],
            "inferences": [],
            "artifacts": [
                {
                    "artifact_id": "confirmed-counterexample",
                    "artifact_type": "confirmed_counterexample",
                    "metadata_json": {"refuted_obligation_id": "debt-refuted-classification"},
                }
            ],
        }

        spine = build_proof_spine(state, action={"mode": "prove", "target_id": "root"}, target_id="root")

        self.assertEqual(spine["decisive_theorem_test"]["debt_id"], "debt-live-theorem")
        self.assertNotIn(
            "debt-refuted-classification",
            {row["debt_id"] for row in spine["current_bottlenecks"]},
        )

    def test_decisive_theorem_test_action_precedes_broad_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("decisive-theorem-test-scheduler", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-rank-one-reservoir",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "blocking_bridge",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Decide the rank-one simple reservoir theorem: prove or refute infinitely many factors.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "seed decisive theorem",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["search_intent"], "decisive_theorem_test")
        self.assertTrue(action["decisive_theorem_test_required"])
        self.assertEqual(action["decisive_theorem_test"]["debt_id"], "debt-rank-one-reservoir")
        self.assertTrue(action["bridge_lemma_workbench_required"])

    def test_hard_problem_default_uses_deep_initial_researcher_companion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-hard-default-research-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            action = next_action(store, web_search="live")
            companions = parallel_companion_actions(store, action, web_search="live")

        self.assertEqual(action["mode"], "retrieve")
        researcher = next(item for item in companions if item["mode"] == "prove")
        self.assertEqual(researcher["research_mode"], "hard_problem")
        self.assertEqual(researcher["research_attack_stage"], "deep")
        self.assertTrue(researcher["deep_research_required"])
        self.assertEqual(researcher["budget"]["policy"], "deep_research_pass")
        self.assertEqual(researcher["budget"]["requested_tokens"], 650_000)

    def test_initial_literature_scan_pairs_direct_research_companion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-parallel-research-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            action = next_action(store, research_mode="balanced", web_search="live")
            companions = parallel_companion_actions(store, action, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "retrieve")
        self.assertEqual(action["search_intent"], "literature_scoping")
        self.assertEqual(len(companions), 2)
        for planned in companions:
            self.assertIn("information_gain_score", planned)
            self.assertIn("expected_value_score", planned["information_gain_score"])
        companion = next(item for item in companions if item["mode"] == "prove")
        counterexample = next(item for item in companions if item["mode"] == "refute")
        self.assertEqual(companion["mode"], "prove")
        self.assertEqual(companion["target_id"], "root")
        self.assertEqual(companion["route_id"], "")
        self.assertEqual(companion["search_intent"], "parallel_direct_solve")
        self.assertEqual(companion["research_attack_stage"], "fast")
        self.assertTrue(companion["direct_solve_required"])
        self.assertEqual(companion["budget"]["requested_tokens"], 90_000)
        self.assertTrue(companion["parallel_companion"])
        self.assertEqual(actor_role_for_action(companion), "researcher")
        self.assertEqual(counterexample["target_id"], "root")
        self.assertEqual(counterexample["search_intent"], "parallel_counterexample_search")
        self.assertTrue(counterexample["counterexample_search_required"])
        self.assertEqual(counterexample["research_attack_stage"], "counterexample")
        self.assertEqual(counterexample["budget"]["requested_tokens"], 80_000)
        self.assertEqual(actor_role_for_action(counterexample), "villain")

    def test_parallel_attack_wave_schedules_researcher_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-parallel-wave-synthesis-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="run-wave-retrieve",
                mode="retrieve",
                target_id="root",
                search_intent="literature_scoping",
                actor_role="literature_researcher",
            )
            record_run(
                store,
                base_revision=1,
                run_id="run-wave-direct",
                mode="prove",
                target_id="root",
                search_intent="parallel_direct_solve",
                actor_role="researcher",
            )
            record_run(
                store,
                base_revision=2,
                run_id="run-wave-counterexample",
                mode="refute",
                target_id="root",
                search_intent="parallel_counterexample_search",
                actor_role="villain",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "parallel_wave_synthesis")
        self.assertTrue(action["research_synthesis_required"])
        self.assertTrue(action["approach_portfolio_synthesis_required"])
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertIn("proof_attack", action["parallel_wave_summary"]["categories"])
        self.assertIn("counterexample_attack", action["parallel_wave_summary"]["categories"])
        self.assertTrue(manifest["researcher_packet"]["staged_attack_policy"]["research_synthesis_required"])
        self.assertTrue(manifest["researcher_packet"]["staged_attack_policy"]["approach_portfolio_synthesis_required"])

    def test_parallel_companion_adds_advisor_after_significant_research_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-advisor-evidence-companion-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "research-note-promising-route",
                            "artifact_type": "research_notebook",
                            "content": "A promising route emerged, but the bridge lemma is still missing.",
                            "metadata": {
                                "target_id": "root",
                                "recommended_next_action": "try to prove the bridge lemma",
                            },
                        }
                    ],
                    "rationale": "record durable research evidence",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            primary = {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "direct_solve_required": True,
                "search_intent": "direct_solve",
            }
            companions = parallel_companion_actions(store, primary, research_mode="balanced", web_search="disabled")
            advisor = next(item for item in companions if item["mode"] == "triage_routes")
            manifest = build_context_manifest(store, action=advisor)

        self.assertEqual(actor_role_for_action(advisor), "phd_advisor")
        self.assertEqual(advisor["search_intent"], "advisor_evidence_synthesis")
        self.assertTrue(advisor["advisor_evidence_synthesis_required"])
        self.assertTrue(advisor["advisor_async_short_budget"])
        self.assertEqual(advisor["budget"]["requested_tokens"], 60000)
        self.assertTrue(advisor["parallel_companion"])
        self.assertIn("research-note-promising-route", advisor["advisor_evidence_signal"]["artifact_ids"])
        self.assertTrue(manifest["workflow_action"]["advisor_evidence_synthesis_required"])
        self.assertIn("advisor_evidence_signal", manifest["workflow_action"])
        manifest_artifact_ids = {artifact["artifact_id"] for artifact in manifest["artifacts"]}
        self.assertIn("research-note-promising-route", manifest_artifact_ids)

    def test_post_integration_advisor_consumes_evidence_synthesis_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "scheduler-post-integration-advisor-watermark-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "research-note-before-integration-advisor",
                            "artifact_type": "research_notebook",
                            "content": "Fresh evidence that the post-integration advisor will synthesize.",
                            "metadata": {"target_id": "root"},
                        }
                    ],
                    "rationale": "record pre-advisor evidence",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            revision = int(store.get_scheduler_state()["problem_state"]["current_revision"])
            record_run(
                store,
                base_revision=revision,
                run_id="run-post-integration-advisor",
                mode="triage_routes",
                target_id="root",
                search_intent="post_integration_proof_spine",
                actor_role="phd_advisor",
            )

            primary = {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "direct_solve_required": True,
                "search_intent": "direct_solve",
            }
            companions = parallel_companion_actions(store, primary, research_mode="balanced", web_search="disabled")

            self.assertFalse(
                any(item.get("search_intent") == "advisor_evidence_synthesis" for item in companions)
            )

            revision = int(store.get_scheduler_state()["problem_state"]["current_revision"])
            newer = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": revision,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "research-note-after-integration-advisor",
                            "artifact_type": "research_notebook",
                            "content": "Genuinely newer evidence requiring another synthesis.",
                            "metadata": {"target_id": "root"},
                        }
                    ],
                    "rationale": "record post-advisor evidence",
                },
            )
            self.assertTrue(newer.accepted, newer.errors)
            companions = parallel_companion_actions(store, primary, research_mode="balanced", web_search="disabled")

        self.assertTrue(
            any(item.get("search_intent") == "advisor_evidence_synthesis" for item in companions)
        )

    def test_post_integration_proof_spine_runs_once_per_integration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "scheduler-post-integration-once-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="run-first-integration",
                mode="integrate",
                target_id="root",
                route_id="route-first",
                actor_role="integration_verifier",
            )

            first = next_action(store, research_mode="balanced", web_search="disabled")
            self.assertEqual(first["search_intent"], "post_integration_proof_spine")

            revision = int(store.get_scheduler_state()["problem_state"]["current_revision"])
            record_run(
                store,
                base_revision=revision,
                run_id="run-first-post-integration-spine",
                mode="triage_routes",
                target_id="root",
                route_id="route-first",
                search_intent="post_integration_proof_spine",
                actor_role="phd_advisor",
            )
            for index in range(8):
                revision = int(store.get_scheduler_state()["problem_state"]["current_revision"])
                record_run(
                    store,
                    base_revision=revision,
                    run_id=f"run-unrelated-{index}",
                    mode="retrieve",
                    target_id="root",
                    search_intent=f"unrelated-{index}",
                    actor_role="literature_researcher",
                )

            consumed = next_action(store, research_mode="balanced", web_search="disabled")
            self.assertNotEqual(consumed.get("search_intent"), "post_integration_proof_spine")

            revision = int(store.get_scheduler_state()["problem_state"]["current_revision"])
            record_run(
                store,
                base_revision=revision,
                run_id="run-second-integration",
                mode="integrate",
                target_id="root",
                route_id="route-second",
                actor_role="integration_verifier",
            )
            rearmed = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(rearmed["search_intent"], "post_integration_proof_spine")
        self.assertEqual(rearmed["recently_integrated_route_id"], "route-second")

    def test_advisor_proof_candidate_report_schedules_researcher_route_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-advisor-proof-candidate-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-report-proof-shape",
                            "artifact_type": "advisor_report",
                            "content": "This is a proof candidate strategy for the root theorem; the researcher should formalize the route.",
                            "metadata": {
                                "target_id": "root",
                                "proof_candidate": True,
                                "advisor_followup_required": True,
                                "recommended_next_action": "turn this proof sketch into a route and inference",
                            },
                        }
                    ],
                    "rationale": "advisor found a proof-shaped strategy",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertEqual(action["search_intent"], "proof_candidate_route_conversion")
        self.assertEqual(action["proof_candidate_artifact_id"], "advisor-report-proof-shape")

    def test_newer_proof_candidate_supersedes_older_nonproof_advisor_directive(self) -> None:
        state = {
            "recent_runs": [],
            "research_artifacts": [
                {
                    "artifact_id": "older-directive",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 4,
                    "metadata_json": json.dumps(
                        {
                            "advisor_followup_required": True,
                            "recommended_next_action": "repeat the old experiment",
                        }
                    ),
                },
                {
                    "artifact_id": "newer-proof-shape",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 8,
                    "metadata_json": json.dumps(
                        {
                            "advisor_followup_required": True,
                            "proof_candidate": True,
                            "recommended_next_action": "convert the new proof shape",
                        }
                    ),
                },
            ],
        }

        self.assertIsNone(_advisor_followup_report(state))

    def test_advisor_report_with_explicit_gap_is_not_proof_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-advisor-gap-not-proof-candidate-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-report-gap",
                            "artifact_type": "advisor_report",
                            "content": "This is not verifier-ready; the researcher should close the bridge before any verifier pass.",
                            "metadata": {
                                "target_id": "root",
                                "proof_candidate": False,
                                "advisor_followup_required": True,
                                "remaining_gaps": ["close the bridge"],
                                "recommended_next_action": "attack the bridge directly",
                            },
                        }
                    ],
                    "rationale": "advisor found a gap, not a proof",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["search_intent"], "advisor_followup_research")
        self.assertEqual(action["advisor_report_id"], "advisor-report-gap")
        self.assertNotIn("proof_candidate_artifact_id", action)

    def test_advisor_followup_report_schedules_immediate_researcher_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-advisor-followup-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-report-next-gap",
                            "artifact_type": "advisor_report",
                            "content": "The route is plausible, but the exact bridge lemma remains open.",
                            "metadata": {
                                "target_id": "root",
                                "advisor_followup_required": True,
                                "remaining_gaps": ["prove the bridge lemma"],
                                "recommended_next_action": "researcher should attack the bridge lemma directly",
                            },
                        }
                    ],
                    "rationale": "advisor gives immediate consulting",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertEqual(action["search_intent"], "advisor_followup_research")
        self.assertTrue(action["advisor_followup_required"])
        self.assertEqual(action["advisor_report_id"], "advisor-report-next-gap")
        self.assertTrue(manifest["workflow_action"]["advisor_followup_required"])

    def test_nonproof_advisor_followup_does_not_preempt_armed_bottleneck(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-advisor-bottleneck-gate-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-root-locked",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "central_obstruction",
                            "severity": "blocking",
                            "obligation": "Prove or refute the locked root bottleneck theorem.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "diag-lock-a",
                            "artifact_type": "research_diagnostic",
                            "content": "Remaining bottleneck: locked theorem is not verifier-ready.",
                            "metadata": {"target_id": "root"},
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "diag-lock-b",
                            "artifact_type": "research_diagnostic",
                            "content": "Next decisive obstruction: locked theorem still blocks the proof.",
                            "metadata": {"target_id": "root"},
                        },
                    ],
                    "rationale": "arm the bottleneck lock",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            advisor = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-report-side-gap",
                            "artifact_type": "advisor_report",
                            "content": "There is a side gap worth considering.",
                            "metadata": {
                                "target_id": "root",
                                "advisor_followup_required": True,
                                "recommended_next_action": "consider a side synthesis before proving the locked theorem",
                            },
                        }
                    ],
                    "rationale": "advisor gives non-proof consulting",
                },
            )
            self.assertTrue(advisor.accepted, advisor.errors)

            action = next_action(store, research_mode="hard_problem", web_search="disabled")

        self.assertEqual(action["search_intent"], "bottleneck_lock_theorem_attack")
        self.assertEqual(action["debt_id"], "debt-root-locked")
        self.assertTrue(action["proof_spine_mode_required"])

    def test_advisor_followup_prefers_named_next_target_over_root_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-advisor-next-target-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "local-bridge",
                            "statement": "Local bridge theorem.",
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-stale",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Old root route.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-local-bridge",
                            "conclusion_claim_id": "local-bridge",
                            "relation_to_parent": "sufficient",
                            "strategy": "Work the advisor's named local bridge.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-report-local-bridge",
                            "artifact_type": "advisor_report",
                            "content": "The root route is stale; work the local bridge next.",
                            "metadata": {
                                "target_id": "root",
                                "next_target_id": "local-bridge",
                                "advisor_followup_required": True,
                                "recommended_next_action": "researcher should prove or break the local bridge",
                            },
                        },
                    ],
                    "rationale": "advisor points at local bridge",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["target_id"], "local-bridge")
        self.assertEqual(action["route_id"], "route-local-bridge")
        self.assertEqual(action["search_intent"], "advisor_followup_research")

    def test_advisor_followup_next_target_overrides_stale_context_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-advisor-stale-route-next-target-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "finished-local-bridge",
                            "statement": "Finished local bridge.",
                            "parent_ids": ["root"],
                            "root_impact": 0.8,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-finished-local-bridge",
                            "conclusion_claim_id": "finished-local-bridge",
                            "relation_to_parent": "sufficient",
                            "strategy": "Already enough support; do not repair this route again.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-report-move-back-to-root",
                            "artifact_type": "advisor_report",
                            "content": "Stop repairing the local bridge; move the root work to the central bottleneck.",
                            "metadata": {
                                "target_id": "finished-local-bridge",
                                "route_id": "route-finished-local-bridge",
                                "next_target_id": "root",
                                "advisor_followup_required": True,
                                "recommended_next_action": "researcher should work the root bottleneck, not the stale route",
                            },
                        },
                    ],
                    "rationale": "advisor uses an old route only as context",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "")
        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["search_intent"], "advisor_followup_research")
        self.assertEqual(actor_role_for_action(action), "researcher")

    def test_downstream_claim_debt_does_not_block_route_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-downstream-debt-verifier-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "local-bridge-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete proof of the local bridge lemma.",
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "local-bridge",
                            "statement": "Local bridge lemma.",
                            "parent_ids": ["root"],
                            "root_impact": 0.8,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-local-bridge",
                            "conclusion_claim_id": "local-bridge",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the local bridge dossier.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-local-bridge",
                            "route_id": "route-local-bridge",
                            "conclusion_claim_id": "local-bridge",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The dossier proves the local bridge.",
                            "evidence_artifact_ids": ["local-bridge-dossier"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-downstream-after-bridge",
                            "owner_type": "claim",
                            "owner_id": "local-bridge",
                            "debt_type": "blocking_bridge",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "After this bridge is proved, decide the remaining downstream bottleneck for the root theorem.",
                            "suggested_next_target": "local-bridge",
                        },
                    ],
                    "rationale": "seed local bridge plus downstream root debt",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            state = store.get_scheduler_state()
            readiness = route_verifier_readiness(state, "route-local-bridge")
            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertTrue(readiness["verifier_ready"], readiness)
        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "local-bridge")
        self.assertEqual(action["route_id"], "route-local-bridge")
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")

    def test_unrouted_proof_candidate_schedules_route_conversion_before_more_research(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-proof-candidate-route-conversion-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "pd-root-proof-candidate",
                            "artifact_type": "proof_dossier",
                            "content": "This is a verifier-ready proof candidate for the root claim.",
                            "metadata": {
                                "target_id": "root",
                                "selected_next_action": "verify_this_candidate",
                            },
                        }
                    ],
                    "rationale": "seed unrouted proof candidate",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action)

            self.assertEqual(action["mode"], "prove")
            self.assertEqual(action["target_id"], "root")
            self.assertEqual(action["route_id"], "")
            self.assertEqual(action["search_intent"], "proof_candidate_route_conversion")
            self.assertTrue(action["proof_route_conversion_required"])
            self.assertEqual(action["proof_candidate_artifact_id"], "pd-root-proof-candidate")
            self.assertEqual(actor_role_for_action(action), "researcher")
            self.assertTrue(manifest["workflow_action"]["proof_route_conversion_required"])
            self.assertEqual(manifest["workflow_action"]["proof_candidate_artifact_id"], "pd-root-proof-candidate")
            self.assertTrue(manifest["researcher_packet"]["staged_attack_policy"]["proof_route_conversion_required"])
            self.assertIn("pd-root-proof-candidate", {row["artifact_id"] for row in manifest["artifacts"]})

            record_run(
                store,
                base_revision=1,
                run_id="run-proof-candidate-conversion",
                mode="prove",
                target_id="root",
                search_intent="proof_candidate_route_conversion",
                actor_role="researcher",
            )
            next_after_conversion = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertNotEqual(next_after_conversion.get("search_intent"), "proof_candidate_route_conversion")

    def test_blocked_route_dossier_does_not_schedule_proof_candidate_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-blocked-route-dossier-proof-candidate-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "stale-local-claim",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "pd-stale-local-claim-repair-note",
                            "artifact_type": "proof_dossier",
                            "content": "Do not verify the stale local wording; retire this route and return to root.",
                            "metadata": {
                                "target_id": "stale-local-claim",
                                "artifact_roi": "route_blocked_or_abandoned",
                                "next_decisive_action": "Return root work to the remaining bottleneck.",
                            },
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-root-remaining-bottleneck",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Solve the remaining root bottleneck.",
                            "suggested_next_target": "root",
                        },
                    ],
                    "rationale": "seed blocked-route dossier",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertNotEqual(action.get("search_intent"), "proof_candidate_route_conversion")
        self.assertNotEqual(action.get("proof_candidate_artifact_id"), "pd-stale-local-claim-repair-note")

    def test_converted_proof_candidate_schedules_strict_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-converted-proof-candidate-verifier-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "pd-root-proof-candidate",
                            "artifact_type": "proof_dossier",
                            "content": "Verifier-ready proof candidate for the root claim.",
                            "metadata": {"target_id": "root", "ready_for_verifier": True},
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-proof-candidate",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the proof candidate dossier to prove the root theorem.",
                            "evidence_artifact_ids": ["pd-root-proof-candidate"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-proof-candidate",
                            "route_id": "route-root-proof-candidate",
                            "conclusion_claim_id": "root",
                            "explanation": "The proof candidate dossier supplies the local argument.",
                            "validation_status": "untested",
                            "evidence_artifact_ids": ["pd-root-proof-candidate"],
                        },
                    ],
                    "rationale": "seed converted proof candidate route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "route-root-proof-candidate")
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")
        self.assertNotEqual(action.get("search_intent"), "proof_candidate_route_conversion")

    def test_repeated_verifier_gap_schedules_advisor_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-loop-classification-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "pd-root-loop",
                            "artifact_type": "proof_dossier",
                            "content": "A proof candidate with a stubborn local gap.",
                            "metadata": {"target_id": "root", "route_id": "route-root-loop", "ready_for_verifier": True},
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-loop",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the proof dossier.",
                            "evidence_artifact_ids": ["pd-root-loop"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-loop",
                            "route_id": "route-root-loop",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof candidate should prove the root if the local gap is repaired.",
                            "evidence_artifact_ids": ["pd-root-loop"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-root-loop-gap",
                            "owner_type": "inference",
                            "owner_id": "inf-root-loop",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Resolve the repeated verifier objection.",
                            "suggested_next_target": "root",
                        },
                    ],
                    "rationale": "seed route with a repeated verifier gap",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            record_run(
                store,
                base_revision=store.get_revision(),
                run_id="strict-verifier-loop-1",
                mode="prove",
                target_id="root",
                route_id="route-root-loop",
                search_intent="verify_ready_route",
                actor_role="strict_informal_verifier",
            )
            record_run(
                store,
                base_revision=store.get_revision(),
                run_id="strict-verifier-loop-2",
                mode="prove",
                target_id="root",
                route_id="route-root-loop",
                search_intent="verify_ready_route",
                actor_role="strict_informal_verifier",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "triage_routes")
        self.assertEqual(action["route_id"], "route-root-loop")
        self.assertEqual(action["search_intent"], "verifier_loop_classification")
        self.assertEqual(actor_role_for_action(action), "phd_advisor")
        self.assertTrue(action["verifier_loop_classification_required"])
        self.assertEqual(action["verifier_gap_debt_ids"], ["debt-root-loop-gap"])
        self.assertEqual(set(action["recent_verifier_run_ids"]), {"strict-verifier-loop-1", "strict-verifier-loop-2"})

    def test_subsumed_alternating_chief_factor_candidate_is_not_rescheduled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-subsumed-proof-candidate-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "root_no_large_alternating_chief_factor_fixed_pq",
                            "statement": "For fixed primes p,q, no large alternating chief factor A_n^t can occur.",
                            "parent_ids": ["root"],
                            "root_impact": 0.78,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "pd-old-alt-chief-obstruction",
                            "artifact_type": "proof_dossier",
                            "content": (
                                "Verifier-ready product-action extension: a p,q-invariably generated host has "
                                "no alternating chief factor A_n^t."
                            ),
                            "metadata": {"target_id": "root", "ready_for_verifier": True},
                        },
                    ],
                    "rationale": "seed an old candidate and the side claim it matches",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            verified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root_no_large_alternating_chief_factor_fixed_pq",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "vr-alt-chief-ok",
                            "artifact_type": "verification_report",
                            "content": "verdict: informally_verified\ncritical_errors: []\ngaps: []",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {"critical_errors": [], "gaps": [], "blocking_gap": False},
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root_no_large_alternating_chief_factor_fixed_pq",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["vr-alt-chief-ok"],
                        },
                    ],
                    "rationale": "verify the side claim represented by the old proof dossier",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertNotEqual(action.get("search_intent"), "proof_candidate_route_conversion")
        self.assertNotEqual(action.get("proof_candidate_artifact_id"), "pd-old-alt-chief-obstruction")

    def test_stop_writer_blocks_unverified_proof_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-stop-writer-proof-candidate-blocker-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "pd-root-proof-candidate",
                            "artifact_type": "proof_dossier",
                            "content": "This is a verifier-ready proof candidate for the root claim.",
                            "metadata": {"target_id": "root", "recommended_next_action": "verify"},
                        }
                    ],
                    "rationale": "seed proof candidate before stop writer",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            blocker = _stop_writer_safety_blocker(store, research_mode="balanced", web_search="disabled")

        self.assertIn("proof-candidate route conversion", blocker["reason"])
        self.assertEqual(blocker["recommended_action"]["search_intent"], "proof_candidate_route_conversion")
        self.assertEqual(blocker["proof_candidate_artifacts"][0]["artifact_id"], "pd-root-proof-candidate")

    def test_stale_parallel_wave_does_not_preempt_new_blocking_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-stale-wave-debt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="run-wave-retrieve",
                mode="retrieve",
                target_id="root",
                search_intent="literature_scoping",
                actor_role="literature_researcher",
            )
            record_run(
                store,
                base_revision=1,
                run_id="run-wave-direct",
                mode="prove",
                target_id="root",
                search_intent="parallel_direct_solve",
                actor_role="researcher",
            )
            record_run(
                store,
                base_revision=2,
                run_id="run-wave-counterexample",
                mode="refute",
                target_id="root",
                search_intent="parallel_counterexample_search",
                actor_role="villain",
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 3,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-new-proof-gap",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Repair the proof after later evidence exposed a contradiction.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "seed later proof debt",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            record_run(
                store,
                base_revision=4,
                run_id="run-later-source-search",
                mode="retrieve",
                target_id="root",
                search_intent="blocking_debt_source_search",
                actor_role="literature_researcher",
            )

            action = next_action(store, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["debt_id"], "debt-new-proof-gap")
        self.assertEqual(action["search_intent"], "direct_solve_debt_repair")
        self.assertNotEqual(action.get("search_intent"), "parallel_wave_synthesis")

    def test_repeated_no_result_search_cards_force_researcher_synthesis_before_more_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-no-result-synthesis-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            cards = []
            for index in range(2):
                cards.append(
                    {
                        "op": "cache_retrieval_card",
                        "card_id": f"retrieval-no-result-{index}",
                        "target_id": "root",
                        "exact_statement": "No useful exact theorem was found for the requested root theorem.",
                        "source_identifiers": {"title": "local search"},
                        "source_version": "unit-test",
                        "source_location": "local corpus",
                        "hypotheses": [],
                        "local_definitions": [],
                        "missing_hypotheses": ["missing construction theorem"],
                        "applicability": {
                            "target_id": "root",
                            "classification": "no_useful_result_found",
                            "theorem_matching_status": "checked_no_useful_result_found",
                        },
                    }
                )
            card_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": cards,
                    "rationale": "cache repeated no-result cards",
                },
            )
            self.assertTrue(card_outcome.accepted, card_outcome.errors)
            request_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "search-request-after-no-results",
                            "artifact_type": "literature_search_request",
                            "content": "Search again for the same exact theorem.",
                            "metadata": {
                                "search_request_id": "req-after-no-results",
                                "target_id": "root",
                                "query": "same exact theorem",
                            },
                        }
                    ],
                    "rationale": "ask for another search after no-result cards",
                },
            )
            self.assertTrue(request_outcome.accepted, request_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "no_result_search_synthesis")
        self.assertTrue(action["no_result_search_synthesis_required"])
        self.assertEqual(action["no_result_search_cluster"]["count"], 2)
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertTrue(manifest["workflow_action"]["no_result_search_synthesis_required"])
        self.assertEqual(manifest["workflow_action"]["no_result_card_ids"], ["retrieval-no-result-0", "retrieval-no-result-1"])

    def test_endpoint_obstructions_and_no_result_cards_force_global_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-global-synthesis-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            cards = []
            for index in range(2):
                cards.append(
                    {
                        "op": "cache_retrieval_card",
                        "card_id": f"retrieval-no-result-{index}",
                        "target_id": "root",
                        "exact_statement": "No exact bridge theorem was found.",
                        "source_identifiers": {"title": "local search"},
                        "source_version": "unit-test",
                        "source_location": "local corpus",
                        "hypotheses": [],
                        "local_definitions": [],
                        "missing_hypotheses": ["bounded-section bridge theorem"],
                        "applicability": {
                            "target_id": "root",
                            "classification": "no_useful_result_found",
                            "theorem_matching_status": "checked_no_useful_result_found",
                        },
                    }
                )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": cards,
                    "rationale": "cache repeated no-result cards",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            artifact_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "pd-root-endpoint-bridge",
                            "artifact_type": "proof_dossier",
                            "content": (
                                "Endpoint obstruction portfolio: alternating obstruction and classical obstruction are available. "
                                "The chief-factor bridge suggests a bounded-section compatibility theorem is the missing theorem."
                            ),
                            "metadata": {
                                "target_id": "root",
                                "remaining_gap": "prove the bounded-section bridge theorem from endpoint obstructions",
                            },
                        }
                    ],
                    "rationale": "seed endpoint obstruction and bridge dossier",
                },
            )
            self.assertTrue(artifact_outcome.accepted, artifact_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "global_synthesis")
        self.assertTrue(action["global_synthesis_required"])
        self.assertTrue(action["theorem_building_synthesis_required"])
        self.assertTrue(action["deep_research_required"])
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertTrue(manifest["workflow_action"]["global_synthesis_required"])
        self.assertTrue(manifest["researcher_packet"]["staged_attack_policy"]["global_synthesis_required"])

    def test_verified_partial_obstruction_and_bridge_debt_force_global_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-partial-root-closure-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "root-no-large-chief-factor-partial",
                            "kind": "lemma",
                            "statement": "A verified partial obstruction excludes large chief factors in any root counterexample host.",
                            "validation_status": "plausible",
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-root-bridge-from-partial-obstruction",
                            "claim_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "obligation": (
                                "Prove the root-closing bridge theorem: every hypothetical host for a hard finite object "
                                "must force the verified chief factor obstruction."
                            ),
                        },
                    ],
                    "rationale": "seed partial result and root bridge debt",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            verified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root-no-large-chief-factor-partial",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "vr-partial-chief-factor",
                            "artifact_type": "verification_report",
                            "content": "The partial obstruction proof checks out.",
                            "metadata": {
                                "target_id": "root-no-large-chief-factor-partial",
                                "verdict": "informally_verified",
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root-no-large-chief-factor-partial",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["vr-partial-chief-factor"],
                        },
                    ],
                    "rationale": "verify the partial result",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            action = next_action(store, research_mode="balanced", web_search="live")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "global_synthesis")
        self.assertTrue(action["global_synthesis_required"])
        self.assertTrue(action["theorem_building_synthesis_required"])
        self.assertEqual(action["global_synthesis_signal"]["partial_closure_signal"]["policy"], "verified-partial-root-closure")
        self.assertIn(
            "root-no-large-chief-factor-partial",
            action["global_synthesis_signal"]["partial_closure_signal"]["partial_claim_ids"],
        )
        self.assertIn("debt-root-bridge-from-partial-obstruction", action["global_synthesis_signal"]["bridge_artifact_ids"])
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertTrue(manifest["workflow_action"]["global_synthesis_required"])

    def test_villain_obstruction_schedules_researcher_route_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-obstruction-conversion-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "villain-candidate-obstruction",
                            "artifact_type": "candidate_counterexample",
                            "content": "A boundary family appears to violate the target unless hypothesis H is strengthened.",
                            "metadata": {
                                "target_id": "root",
                                "obstruction_type": "missing_hypothesis",
                                "example_family": "boundary family",
                            },
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "obs-root-hypothesis",
                            "kind": "obstruction",
                            "statement": "The boundary family threatens the root theorem without hypothesis H.",
                            "validation_status": "plausible",
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "evidence_artifact_ids": ["villain-candidate-obstruction"],
                        },
                    ],
                    "rationale": "villain records a serious obstruction",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "obstruction_route_conversion")
        self.assertTrue(action["research_synthesis_required"])
        self.assertTrue(action["obstruction_route_conversion_required"])
        self.assertTrue(action["global_obstruction_architecture_required"])
        self.assertEqual(action["obstruction_claim_ids"], ["obs-root-hypothesis"])
        self.assertIn("villain-candidate-obstruction", action["obstruction_artifact_ids"])
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertTrue(manifest["workflow_action"]["obstruction_route_conversion_required"])
        self.assertTrue(manifest["workflow_action"]["global_obstruction_architecture_required"])
        self.assertIn("candidate_counterexample_needs_validation", manifest["workflow_action"]["obstruction_cluster"]["conversion_choices"])

    def test_route_obstruction_artifact_from_snapshot_schedules_route_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-route-obstruction-artifact-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "villain-route-obstruction",
                            "artifact_type": "route_obstruction",
                            "content": "The proposed route fails unless hypothesis H is added.",
                            "metadata": {
                                "target_id": "root",
                                "obstruction_type": "missing_hypothesis",
                            },
                        }
                    ],
                    "rationale": "villain records a route-level obstruction",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            snapshot_ids = {str(artifact.get("artifact_id") or "") for artifact in store.get_scheduler_state().get("research_artifacts", [])}
            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertIn("villain-route-obstruction", snapshot_ids)
        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["search_intent"], "obstruction_route_conversion")
        self.assertTrue(action["obstruction_route_conversion_required"])
        self.assertIn("villain-route-obstruction", action["obstruction_artifact_ids"])

    def test_fresh_obstruction_after_researcher_timeout_redirects_to_advisor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-obstruction-timeout-advisor-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="researcher-obstruction-timeout",
                mode="prove",
                target_id="root",
                search_intent="obstruction_route_conversion",
                actor_role="researcher",
                status="timeout",
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "villain-fresh-route-obstruction",
                            "artifact_type": "route_obstruction",
                            "content": "A fresh construction obstruction needs route-level triage.",
                            "metadata": {
                                "target_id": "root",
                                "obstruction_type": "route_killing_obstruction",
                            },
                        }
                    ],
                    "rationale": "villain records a fresh route-level obstruction after the researcher stalled",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "triage_routes")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "obstruction_route_conversion")
        self.assertEqual(actor_role_for_action(action), "phd_advisor")
        self.assertTrue(action["advisor_obstruction_conversion_required"])
        self.assertTrue(action["obstruction_route_conversion_required"])
        self.assertEqual(action["recent_researcher_timeout_run_id"], "researcher-obstruction-timeout")
        self.assertIn("villain-fresh-route-obstruction", action["obstruction_artifact_ids"])

    def test_researcher_stream_retry_stall_routes_to_advisor_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-stream-stall-advisor-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="researcher-stream-stall",
                mode="prove",
                target_id="root",
                search_intent="global_synthesis",
                actor_role="researcher",
                status="timeout",
                error_summary="Codex stream retry stalled with no further log/token progress before a patch was produced.",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "triage_routes")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "stream_stall_recovery")
        self.assertEqual(actor_role_for_action(action), "phd_advisor")
        self.assertTrue(action["stream_stall_recovery_required"])
        self.assertTrue(action["advisor_evidence_synthesis_required"])
        self.assertEqual(action["recent_researcher_timeout_run_id"], "researcher-stream-stall")

    def test_stream_retry_stall_recovery_does_not_repeat_after_advisor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-stream-stall-advisor-once-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="researcher-stream-stall",
                mode="prove",
                target_id="root",
                search_intent="global_synthesis",
                actor_role="researcher",
                status="timeout",
                error_summary="Codex stream retry stalled with no further log/token progress before a patch was produced.",
            )
            record_run(
                store,
                base_revision=1,
                run_id="advisor-stream-recovery",
                mode="triage_routes",
                target_id="root",
                search_intent="stream_stall_recovery",
                actor_role="phd_advisor",
                status="completed",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertNotEqual(action["search_intent"], "stream_stall_recovery")

    def test_concrete_candidate_counterexample_schedules_validator(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-concrete-counterexample-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "villain-concrete-counterexample",
                            "artifact_type": "candidate_counterexample",
                            "content": "Concrete finite object K violates the root statement.",
                            "metadata": {
                                "target_id": "root",
                                "obstruction_type": "candidate_counterexample",
                                "concrete_instance": "K",
                            },
                        }
                    ],
                    "rationale": "villain records a concrete candidate counterexample",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

            manifest = build_context_manifest(store, action=action, max_chars=40_000)

        self.assertEqual(action["mode"], "validate_counterexample")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "counterexample_validation")
        self.assertTrue(action["counterexample_validation_required"])
        self.assertEqual(action["candidate_counterexample_artifact_id"], "villain-concrete-counterexample")
        self.assertEqual(actor_role_for_action(action), "counterexample_validator")
        self.assertTrue(manifest["workflow_action"]["counterexample_validation_required"])
        self.assertEqual("counterexample_validator", manifest["role_context_policy"]["context_role"])
        operation_templates = manifest["patch_contract"]["operation_templates"]
        self.assertTrue(
            any(
                template["op"] == "propose_status_transition" and "new_status=refuted" in template["fields"]
                for template in operation_templates
            )
        )
        self.assertEqual(
            manifest["workflow_action"]["candidate_counterexample_artifact_id"],
            "villain-concrete-counterexample",
        )
        self.assertIn(
            "villain-concrete-counterexample",
            {artifact["artifact_id"] for artifact in manifest["artifacts"]},
        )

    def test_new_candidate_is_not_suppressed_by_older_validation_of_same_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-new-counterexample-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="older-root-validation",
                mode="validate_counterexample",
                target_id="root",
                search_intent="counterexample_validation",
                actor_role="counterexample_validator",
                status="completed",
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "newer-root-counterexample",
                            "artifact_type": "candidate_counterexample",
                            "content": "A different concrete finite object violates the root statement.",
                            "metadata": {
                                "target_id": "root",
                                "obstruction_type": "candidate_counterexample",
                                "concrete_instance": "L",
                            },
                        }
                    ],
                    "rationale": "record a root counterexample discovered after the earlier validation",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "validate_counterexample")
        self.assertEqual(action["candidate_counterexample_artifact_id"], "newer-root-counterexample")

    def test_counterexample_to_interrogative_root_does_not_authorize_root_refutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-question-counterexample-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Does there exist a bound? Find the minimum bound.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "question-lower-bound-example",
                            "artifact_type": "candidate_counterexample",
                            "content": "This example disproves only the proposed bound two.",
                            "metadata": {
                                "target_id": "root",
                                "failed_hypothesis": "the proposed bound is at most two",
                                "concrete_instance": "K",
                            },
                        }
                    ],
                    "rationale": "record root-level lower-bound evidence",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "validate_counterexample")
        self.assertTrue(action["root_is_interrogative_problem"])
        self.assertFalse(action["allow_root_refutation"])
        self.assertIn("keep the root question active", action["reason"])
        self.assertNotIn("propose refuted", action["reason"])

    def test_confirmed_counterexample_without_refuted_status_schedules_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "scheduler-counterexample-reconciliation-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Every finite widget is blue.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "counterexample_validator",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "confirmed-red-widget",
                            "artifact_type": "confirmed_counterexample",
                            "content": "A checked finite red widget falsifies the root.",
                            "metadata": {
                                "target_claim_id": "root",
                                "validation_result": "confirmed",
                                "confirmed": True,
                            },
                        }
                    ],
                    "rationale": "simulate a confirmation whose status transition was omitted",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action, max_chars=12_000)

        self.assertEqual("validate_counterexample", action["mode"])
        self.assertEqual("counterexample_status_reconciliation", action["search_intent"])
        self.assertTrue(action["counterexample_status_reconciliation_required"])
        self.assertEqual("confirmed-red-widget", action["confirmed_counterexample_artifact_id"])
        self.assertEqual(["confirmed-red-widget"], action["validation_evidence_artifact_ids"])
        self.assertTrue(manifest["workflow_action"]["counterexample_status_reconciliation_required"])
        self.assertIn(
            "propose_status_transition",
            manifest["patch_contract"].get("allowed_operation_names", []),
        )
        self.assertIn(
            "confirmed-red-widget",
            {artifact["artifact_id"] for artifact in manifest["artifacts"]},
        )

    def test_failed_validation_does_not_suppress_candidate_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-failed-validation-retry-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "candidate-needing-retry",
                            "artifact_type": "candidate_counterexample",
                            "content": "A concrete candidate.",
                            "metadata": {"target_id": "root", "concrete_instance": "K"},
                        }
                    ],
                    "rationale": "record candidate",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            record_run(
                store,
                base_revision=1,
                run_id="failed-validation",
                mode="validate_counterexample",
                target_id="root",
                search_intent="counterexample_validation",
                actor_role="counterexample_validator",
                status="failed",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "validate_counterexample")
        self.assertEqual(action["candidate_counterexample_artifact_id"], "candidate-needing-retry")

    def test_confirmed_candidate_stays_suppressed_after_recent_run_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-durable-confirmation-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Does the bound exist?")
            candidate = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "durably-confirmed-candidate",
                            "artifact_type": "candidate_counterexample",
                            "content": "A concrete lower-bound example.",
                            "metadata": {"target_id": "root", "concrete_instance": "K"},
                        }
                    ],
                    "rationale": "record candidate",
                },
            )
            self.assertTrue(candidate.accepted, candidate.errors)
            confirmation = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "counterexample_validator",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "durable-confirmation",
                            "artifact_type": "confirmed_counterexample",
                            "content": "The example is independently checked.",
                            "metadata": {
                                "candidate_artifact_id": "durably-confirmed-candidate",
                                "confirmed": True,
                            },
                        }
                    ],
                    "rationale": "record confirmation without refuting an interrogative root",
                },
            )
            self.assertTrue(confirmation.accepted, confirmation.errors)
            revision = 2
            for index in range(10):
                record_run(
                    store,
                    base_revision=revision,
                    run_id=f"later-run-{index}",
                    mode="triage_routes",
                    target_id="root",
                    search_intent=f"later-{index}",
                    actor_role="phd_advisor",
                    status="completed",
                )
                revision += 1

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertNotEqual(action["mode"], "validate_counterexample")

    def test_route_level_counterexamples_do_not_trigger_root_refinement(self) -> None:
        route_level_artifacts = [
            {
                "artifact_id": "gap-two-route-killer",
                "artifact_type": "candidate_counterexample",
                "metadata_json": json.dumps(
                    {
                        "target_id": "root",
                        "obstruction_type": "explicit_gap_two_counterexample_and_route_killer",
                        "failed_hypothesis": "The candidate bound k=1.",
                    }
                ),
            },
            {
                "artifact_id": "terminal-classification-route-killer",
                "artifact_type": "candidate_counterexample",
                "metadata_json": json.dumps(
                    {
                        "target_id": "root",
                        "obstruction_type": "route_killing",
                        "threatened_obligation": "debt-terminal-classification",
                    }
                ),
            },
        ]

        self.assertEqual(_root_refinement_signals({"debts": [], "research_artifacts": route_level_artifacts}), [])

    def test_nonroot_missing_hypotheses_do_not_trigger_root_refinement(self) -> None:
        debts = [
            {
                "debt_id": "debt-local-missing-hypothesis",
                "owner_id": "claim-local-lemma",
                "status": "active",
                "obligation": "The local lemma has a missing hypothesis.",
            },
            {
                "debt_id": "debt-root-overbroad",
                "owner_id": "root",
                "status": "active",
                "obligation": "The root scope is explicitly over-broad.",
            },
        ]

        self.assertEqual(
            _root_refinement_signals({"debts": debts, "research_artifacts": []}),
            ["debt-root-overbroad"],
        )

    def test_two_actual_root_counterexamples_can_trigger_root_refinement(self) -> None:
        root_counterexamples = [
            {
                "artifact_id": f"root-counterexample-{index}",
                "artifact_type": "candidate_counterexample",
                "metadata_json": json.dumps(
                    {
                        "target_id": "root",
                        "obstruction_type": "candidate_counterexample",
                        "concrete_instance": f"K{index}",
                    }
                ),
            }
            for index in range(2)
        ]

        self.assertEqual(
            _root_refinement_signals({"debts": [], "research_artifacts": root_counterexamples}),
            ["root-counterexample-0", "root-counterexample-1"],
        )

    def test_villain_obstruction_repairs_existing_route_and_does_not_repeat_after_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-obstruction-route-repair-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            route_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root-main",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "status": "active",
                            "strategy": "Use the standard construction.",
                        }
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(route_outcome.accepted, route_outcome.errors)
            obstruction_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "villain-route-obstruction",
                            "artifact_type": "research_diagnostic",
                            "content": "Obstruction: the standard construction fails on the singular boundary case.",
                            "metadata": {
                                "target_id": "root",
                                "route_id": "route-root-main",
                                "status": "obstruction_found",
                                "obstruction_type": "route_repair_signal",
                            },
                        }
                    ],
                    "rationale": "villain records route obstruction",
                },
            )
            self.assertTrue(obstruction_outcome.accepted, obstruction_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            self.assertEqual(action["mode"], "reduce")
            self.assertEqual(action["route_id"], "route-root-main")
            self.assertEqual(action["search_intent"], "obstruction_route_conversion")
            self.assertTrue(action["proof_repair_required"])
            self.assertEqual(actor_role_for_action(action), "researcher")

            record_run(
                store,
                base_revision=2,
                run_id="obstruction-conversion-run",
                mode="reduce",
                target_id="root",
                route_id="route-root-main",
                search_intent="obstruction_route_conversion",
                actor_role="researcher",
            )
            next_after_conversion = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertNotEqual(next_after_conversion.get("search_intent"), "obstruction_route_conversion")

    def test_researcher_obstruction_dossier_preempts_repeated_blocking_debt_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-researcher-obstruction-dossier-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            route_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root-main",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "status": "active",
                            "strategy": "Use a prescribed construction.",
                        }
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(route_outcome.accepted, route_outcome.errors)
            debt_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-route-killing-obstruction",
                            "owner_type": "route",
                            "owner_id": "route-root-main",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Replace the prescribed construction because the current premise is obstructed.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "seed blocking route debt",
                },
            )
            self.assertTrue(debt_outcome.accepted, debt_outcome.errors)
            dossier_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "researcher-route-obstruction-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "Obstruction: the prescribed construction is false as stated and must be replaced.",
                            "metadata": {
                                "target_id": "root",
                                "route_id": "route-root-main",
                                "obstruction_classification": "route_killing_obstruction",
                            },
                        }
                    ],
                    "rationale": "researcher found a route-killing obstruction",
                },
            )
            self.assertTrue(dossier_outcome.accepted, dossier_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "route-root-main")
        self.assertEqual(action["search_intent"], "obstruction_route_conversion")
        self.assertTrue(action["obstruction_route_conversion_required"])
        self.assertIn("researcher-route-obstruction-dossier", action["obstruction_artifact_ids"])
        self.assertNotEqual(action.get("search_intent"), "route_proof_construction")

    def test_route_killing_conversion_artifact_schedules_advisor_triage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-route-killing-artifact-triage-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            route_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root-main",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "status": "active",
                            "strategy": "Use a prescribed construction.",
                        }
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(route_outcome.accepted, route_outcome.errors)
            artifact_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "route-decision-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "Route-killing obstruction: this route is false as stated.",
                            "metadata": {
                                "target_id": "root",
                                "route_id": "route-root-main",
                                "classification": "route_killing_obstruction",
                                "route_decision": "abandon_as_stated",
                            },
                        }
                    ],
                    "rationale": "convert obstruction into route decision",
                },
            )
            self.assertTrue(artifact_outcome.accepted, artifact_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "triage_routes")
        self.assertEqual(action["route_id"], "route-root-main")
        self.assertEqual(action["search_intent"], "route_triage")
        self.assertTrue(action["route_triage_required"])
        self.assertEqual(action["route_decision_artifact_id"], "route-decision-dossier")
        self.assertEqual(actor_role_for_action(action), "phd_advisor")

    def test_route_triage_report_pauses_route_for_blocking_debt_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-route-triage-pauses-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            route_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root-main",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "status": "active",
                            "strategy": "Use a prescribed construction.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-route-blocker",
                            "owner_type": "route",
                            "owner_id": "route-root-main",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Replace the paused route premise.",
                            "suggested_next_target": "root",
                        },
                    ],
                    "rationale": "seed route and blocker",
                },
            )
            self.assertTrue(route_outcome.accepted, route_outcome.errors)
            triage_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "route-triage-pauses-main",
                            "artifact_type": "route_triage_report",
                            "content": "Pause route-root-main as stated.",
                            "metadata": {
                                "target_id": "root",
                                "paused_or_abandoned_route_ids": ["route-root-main"],
                            },
                        }
                    ],
                    "rationale": "advisor pauses route",
                },
            )
            self.assertTrue(triage_outcome.accepted, triage_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "")
        self.assertEqual(action["search_intent"], "direct_solve_after_route_pause")
        self.assertTrue(action["route_replacement_required"])
        self.assertEqual(action["route_triage_report_id"], "route-triage-pauses-main")
        self.assertEqual(action["paused_route_ids"], ["route-root-main"])

    def test_exact_retrieval_card_schedules_citation_certification_before_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-citation-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")

            debt_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-root",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Internal construction is still missing.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "seed root debt",
                },
            )
            self.assertTrue(debt_outcome.accepted, debt_outcome.errors)

            card_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "cache_retrieval_card",
                            "card_id": "retrieval-exact-root",
                            "target_id": "root",
                            "exact_statement": "Target theorem.",
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Exact Paper",
                                "theorem_number": "Theorem 1",
                                "arxiv": "arXiv:0000.00001",
                            },
                            "source_version": "arXiv:0000.00001",
                            "source_location": "Theorem 1",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {
                                "target_id": "root",
                                "classification": "direct_match",
                                "theorem_matching_status": "verified_statement_match",
                                "implication_to_target_verified": True,
                                "program_victory_candidate": True,
                            },
                        }
                    ],
                    "rationale": "cache exact root theorem",
                },
            )
            self.assertTrue(card_outcome.accepted, card_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")
            record_run(
                store,
                base_revision=2,
                run_id="triage-exact-root",
                mode="prove",
                target_id="root",
                search_intent="citation_triage",
                actor_role="strict_informal_verifier",
            )
            certification = next_action(store, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertTrue(action["citation_triage_required"])
        self.assertEqual(action["retrieval_card_id"], "retrieval-exact-root")
        self.assertEqual(action["search_intent"], "citation_triage")
        self.assertEqual(action["budget"]["requested_tokens"], 60_000)
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")
        self.assertEqual(certification["mode"], "prove")
        self.assertEqual(certification["target_id"], "root")
        self.assertTrue(certification["citation_certification_required"])
        self.assertEqual(certification["retrieval_card_id"], "retrieval-exact-root")
        self.assertEqual(certification["search_intent"], "citation_certification")
        self.assertEqual(certification["budget"]["requested_tokens"], 120_000)
        self.assertEqual(actor_role_for_action(certification), "strict_informal_verifier")

    def test_local_only_retrieval_card_does_not_schedule_root_citation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-local-citation-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "cache_retrieval_card",
                            "card_id": "retrieval-local-lemma-only",
                            "target_id": "root",
                            "exact_statement": "A local lemma used by one branch.",
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Local Lemma Paper",
                                "theorem_number": "Theorem 2",
                            },
                            "source_version": "published",
                            "source_location": "Theorem 2",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {
                                "target_id": "root",
                                "classification": "direct_match",
                                "theorem_matching_status": "checked_match",
                                "implication_to_target_verified": False,
                                "program_victory_candidate": False,
                                "root_relevance": "supports_only_local_proof_obligation",
                            },
                        }
                    ],
                    "rationale": "cache a source that proves only a local obligation",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")

        self.assertFalse(action.get("citation_triage_required", False))
        self.assertFalse(action.get("citation_certification_required", False))
        self.assertNotIn(action.get("search_intent"), {"citation_triage", "citation_certification"})

    def test_citation_manifest_preserves_requested_retrieval_card_under_trimming(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("citation-context-trim-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")

            operations = []
            for index in range(8):
                operations.append(
                    {
                        "op": "cache_retrieval_card",
                        "card_id": f"card-{index:02d}",
                        "target_id": "root",
                        "exact_statement": f"Auxiliary theorem {index}.",
                        "source_identifiers": {
                            "author": "A. Author",
                            "title": f"Auxiliary Paper {index}",
                            "theorem_number": f"Theorem {index}",
                            "arxiv": f"arXiv:0000.0000{index}",
                        },
                        "source_version": f"arXiv:0000.0000{index}",
                        "source_location": f"Theorem {index}",
                        "hypotheses": [],
                        "local_definitions": [],
                        "missing_hypotheses": [],
                        "applicability": {
                            "target_id": "root",
                            "classification": "direct_match",
                            "implication_to_target_verified": True,
                        },
                    }
                )
            operations.append(
                {
                    "op": "cache_retrieval_card",
                    "card_id": "zz-needed-card",
                    "target_id": "root",
                    "exact_statement": "Target theorem. " + ("This exact source card is required for citation verification. " * 20),
                    "source_identifiers": {
                        "author": "Needed Author",
                        "title": "Needed Paper",
                        "theorem_number": "Theorem N",
                        "doi": "10.0000/needed",
                    },
                    "source_version": "doi:10.0000/needed",
                    "source_location": "Theorem N",
                    "hypotheses": [],
                    "local_definitions": [],
                    "missing_hypotheses": [],
                    "applicability": {
                        "target_id": "root",
                        "classification": "direct_match",
                        "theorem_matching_status": "verified_statement_match",
                        "implication_to_target_verified": True,
                    },
                }
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": operations,
                    "rationale": "seed many cards with one verifier-required card outside normal ranking",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = {
                "mode": "prove",
                "target_id": "root",
                "citation_triage_required": True,
                "retrieval_card_id": "zz-needed-card",
                "search_intent": "citation_triage",
            }
            manifest = build_context_manifest(store, action=action, max_chars=1_000)

        self.assertTrue(
            any(card["card_id"] == "zz-needed-card" for card in manifest["retrieval_cards"]),
            manifest.get("retrieval_cards"),
        )

    def test_villain_manifest_exposes_staged_counterexample_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-counterexample-manifest-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            action = {
                "mode": "refute",
                "target_id": "root",
                "counterexample_search_required": True,
                "research_attack_stage": "counterexample",
                "search_intent": "parallel_counterexample_search",
            }

            manifest = build_context_manifest(store, action=action)

        self.assertEqual(manifest["workflow_action"]["research_attack_stage"], "counterexample")
        self.assertTrue(manifest["workflow_action"]["counterexample_search_required"])
        self.assertEqual(manifest["role_context_policy"]["context_role"], "villain")
        packet = manifest["researcher_packet"]
        self.assertEqual(packet["role_contract"], "villain_refutation_researcher")
        self.assertEqual(packet["staged_attack_policy"]["research_attack_stage"], "counterexample")
        self.assertTrue(packet["staged_attack_policy"]["counterexample_search_required"])
        self.assertTrue(packet["citation_policy"]["citations_are_allowed"])
        self.assertIn("properly cited theorem", packet["citation_policy"]["verifier_expectation"])

    def test_control_packets_survive_tiny_villain_context_trim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-trimmed-villain-context-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            action = {
                "mode": "refute",
                "target_id": "root",
                "counterexample_search_required": True,
                "research_attack_stage": "counterexample",
                "search_intent": "parallel_counterexample_search",
            }

            manifest = build_context_manifest(store, action=action, max_chars=900)

        self.assertIn("patch_contract", manifest)
        self.assertIn("parallel_exchange", manifest)
        self.assertIn("local_search_policy", manifest)
        self.assertIn("role_context_policy", manifest)
        self.assertEqual(manifest["role_context_policy"]["context_role"], "villain")
        self.assertTrue(manifest["patch_contract"].get("compact"))
        self.assertTrue(manifest["parallel_exchange"].get("compact"))
        self.assertTrue(manifest["local_search_policy"].get("compact"))
        self.assertIn("allowed_local_evidence_paths", manifest["local_search_policy"])
        self.assertIn("never run `find .`", manifest["local_search_policy"]["local_shell_rule"].lower())
        self.assertIn("Never construct artifact paths", manifest["local_search_policy"]["local_shell_rule"])

    def test_direct_researcher_manifest_exposes_patch_contract_and_exchange(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-direct-prove-manifest-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            action = {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "direct_solve_required": True,
                "research_attack_stage": "fast",
                "search_intent": "parallel_direct_solve",
            }

            manifest = build_context_manifest(store, action=action, max_chars=60_000)
            prompt = build_session_prompt(
                context_path=Path(manifest["parallel_exchange"]["path"]).with_name("context.json"),
                action=action,
                actor_role=actor_role_for_action(action),
            )

        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertEqual(manifest["role_context_policy"]["context_role"], "researcher")
        self.assertEqual(manifest["role_context_policy"]["authoritative_packet"], "researcher_packet")
        self.assertTrue(manifest["workflow_action"]["direct_solve_required"])
        self.assertTrue(manifest["researcher_packet"]["staged_attack_policy"]["direct_solve_required"])
        self.assertEqual(manifest["researcher_packet"]["paperwork_budget_policy"]["policy"], "math-first-compact-reporting")
        self.assertTrue(manifest["researcher_packet"]["paperwork_budget_policy"]["artifact_roi_required"])
        self.assertTrue(manifest["researcher_packet"]["paperwork_budget_policy"]["compact_by_default"])
        self.assertIn("Spend most tokens", manifest["researcher_packet"]["paperwork_budget_policy"]["primary_token_rule"])
        self.assertIn("patch_contract", manifest)
        self.assertIn("parallel_exchange", manifest)
        self.assertIn("local_search_policy", manifest)
        self.assertIn("download_scope_rule", manifest["local_search_policy"])
        self.assertIn("allowed_local_evidence_paths", manifest["local_search_policy"])
        self.assertEqual(manifest["local_search_policy"]["allowed_local_evidence_paths"], [])
        self.assertIn("never run `find .`", manifest["local_search_policy"]["local_shell_rule"].lower())
        self.assertNotIn("agents/generation/downloads", manifest["local_search_policy"]["prefer"])
        self.assertIn("Do not recursively search the whole downloads tree", manifest["local_search_policy"]["download_scope_rule"])
        self.assertIn("parallel_signals", manifest["patch_contract"]["common"]["parallel_signal_rule"])
        self.assertIn(
            "update_inference",
            {template["op"] for template in manifest["patch_contract"]["operation_templates"]},
        )
        self.assertIn("direct-solve researcher action", prompt)
        self.assertIn("manifest.parallel_exchange", prompt)
        self.assertIn("do not sweep the whole global downloads tree", prompt)
        self.assertIn("allowed_local_evidence_paths", prompt)
        self.assertIn("never run `find .`", prompt.lower())
        self.assertIn("Never construct artifact paths", prompt)

    def test_branch_packet_debt_survives_global_debt_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-branch-debt-priority-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            operations = [
                {
                    "op": "add_claim",
                    "claim_id": "branch-claim",
                    "kind": "lemma",
                    "statement": "A branch theorem needing one exact hypothesis repair.",
                    "parent_ids": ["root"],
                },
                {
                    "op": "add_route",
                    "route_id": "branch-route",
                    "conclusion_claim_id": "branch-claim",
                    "strategy": "repair the exact branch theorem",
                },
                {
                    "op": "add_inference",
                    "inference_id": "branch-inference",
                    "route_id": "branch-route",
                    "conclusion_claim_id": "branch-claim",
                    "validation_status": "challenged",
                    "explanation": "The branch proof needs an exact equivariance repair.",
                },
            ]
            for index in range(13):
                operations.append(
                    {
                        "op": "add_debt",
                        "debt_id": f"root-debt-{index:02d}",
                        "owner_type": "claim",
                        "owner_id": "root",
                        "debt_type": "gap",
                        "severity": "blocking",
                        "status": "active",
                        "obligation": f"Unrelated root obligation {index}.",
                    }
                )
            operations.append(
                {
                    "op": "add_debt",
                    "debt_id": "branch-repair-debt",
                    "owner_type": "claim",
                    "owner_id": "branch-claim",
                    "debt_type": "missing_hypothesis",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Add the missing nonzero-source hypothesis before retrying the branch.",
                    "suggested_next_target": "branch-claim",
                }
            )
            operations.append(
                {
                    "op": "add_debt",
                    "debt_id": "branch-inference-debt",
                    "owner_type": "inference",
                    "owner_id": "branch-inference",
                    "debt_type": "missing_hypothesis",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Prove the action is equivariant before using the inference.",
                    "suggested_next_target": "branch-inference",
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
                    "rationale": "seed a branch repair hidden behind many root debts",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            branch_packet = _branch_packet_card(
                store.get_scheduler_state(),
                "branch-route",
                "branch-claim",
                "spine",
            )
            action = {
                "mode": "reduce",
                "target_id": "branch-claim",
                "route_id": "branch-route",
                "branch_focus": "branch-route",
                "parallel_companion": True,
                "branch_packet": branch_packet,
            }
            manifest = build_context_manifest(store, action=action, max_chars=12_000)

        packet_debt_ids = [row["debt_id"] for row in manifest["researcher_packet"]["active_debts"]]
        self.assertIn("branch-repair-debt", packet_debt_ids)
        self.assertIn("branch-inference-debt", packet_debt_ids)
        self.assertIn("branch-repair-debt", manifest["researcher_packet"]["protected_debt_ids"])
        self.assertIn("branch-inference-debt", manifest["researcher_packet"]["protected_debt_ids"])
        self.assertIn("branch-inference", branch_packet["inference_ids"])

    def test_evidence_boundary_rejects_unlisted_download_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            context_path = root / "context.json"
            log_path = root / "codex.log"
            context_path.write_text(
                json.dumps({"local_search_policy": {"allowed_local_evidence_paths": []}}),
                encoding="utf-8",
            )
            log_path.write_text(
                "exec\n"
                "/bin/zsh -lc 'find agents/generation/downloads -type f' in /tmp/work\n"
                " succeeded in 0ms:\n"
                "./agents/generation/downloads\n"
                "agents/generation/downloads/higher_genus/unrelated/source.tex\n",
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertTrue(errors)
            self.assertIn("unlisted local evidence path", errors[0])

    def test_evidence_boundary_allows_manifest_listed_download_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            context_path = root / "context.json"
            log_path = root / "codex.log"
            context_path.write_text(
                json.dumps(
                    {
                        "local_search_policy": {
                            "allowed_local_evidence_paths": [
                                "agents/generation/downloads/current_problem/source_pack"
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            log_path.write_text(
                "exec\n"
                "/bin/zsh -lc 'cat agents/generation/downloads/current_problem/source_pack/theorem.txt' in /tmp/work\n"
                " succeeded in 0ms:\n"
                "agents/generation/downloads/current_problem/source_pack/theorem.txt\n",
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertEqual(errors, [])

    def test_evidence_boundary_rejects_unlisted_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            context_path = root / "context.json"
            log_path = root / "codex.log"
            context_path.write_text(
                json.dumps(
                    {
                        "local_search_policy": {
                            "allowed_local_evidence_paths": [
                                str(root / "agents/generation/results/demo/phase2/artifacts/current.md")
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            log_path.write_text(
                "exec\n"
                f"/bin/zsh -lc 'cat {root / 'agents/generation/results/demo/phase2/artifacts/stale.md'}' in /tmp/work\n"
                " succeeded in 0ms:\n"
                + str(root / "agents/generation/results/demo/phase2/artifacts/stale.md")
                + "\n",
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertTrue(errors)
            self.assertIn("stale.md", errors[0])

    def test_evidence_boundary_allows_manifest_listed_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact_path = root / "agents/generation/results/demo/phase2/artifacts/current.md"
            context_path = root / "context.json"
            log_path = root / "codex.log"
            context_path.write_text(
                json.dumps({"local_search_policy": {"allowed_local_evidence_paths": [str(artifact_path)]}}),
                encoding="utf-8",
            )
            log_path.write_text(
                "exec\n"
                f"/bin/zsh -lc 'cat {artifact_path}' in /tmp/work\n"
                " succeeded in 0ms:\n"
                f"{artifact_path}\n",
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertEqual(errors, [])

    def test_evidence_boundary_ignores_prompt_policy_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            context_path = root / "context.json"
            log_path = root / "codex.log"
            context_path.write_text(
                json.dumps({"local_search_policy": {"allowed_local_evidence_paths": []}}),
                encoding="utf-8",
            )
            log_path.write_text(
                "Follow manifest.local_search_policy and never sweep agents/generation/downloads.\n"
                "codex\n"
                '{"source_location":{"web_sources":["https://example.test"],'
                '"manifest_paths":["agents/generation/downloads/not-accessed/source.tex"]}}\n',
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertEqual(errors, [])

    def test_evidence_boundary_ignores_manifest_policy_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            context_path = root / "context.json"
            log_path = root / "codex.log"
            context_path.write_text(
                json.dumps({"local_search_policy": {"allowed_local_evidence_paths": []}}),
                encoding="utf-8",
            )
            log_path.write_text(
                "exec\n"
                f"/bin/zsh -lc 'sed -n 1,120p {context_path}' in /tmp/work\n"
                " succeeded in 0ms:\n"
                "{\n"
                '  "download_scope_rule": "Treat agents/generation/downloads as a container, not an approved corpus.",\n'
                '  "local_shell_rule": "Never run broad find over agents/generation/downloads."\n'
                "}\n",
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertEqual(errors, [])

    def test_evidence_boundary_ignores_manifest_artifact_path_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            context_path = root / "context.json"
            log_path = root / "codex.log"
            artifact_path = root / "agents/generation/results/demo/phase2/artifacts/old.md"
            context_path.write_text(
                json.dumps({"local_search_policy": {"allowed_local_evidence_paths": []}}),
                encoding="utf-8",
            )
            log_path.write_text(
                "exec\n"
                f"/bin/zsh -lc 'jq . context.json' in {root}\n"
                " succeeded in 0ms:\n"
                "{\n"
                f'  "path": "{artifact_path}"\n'
                "}\n",
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertEqual(errors, [])

    def test_evidence_boundary_ignores_provenance_paths_quoted_by_allowed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            context_dir = root / "contexts" / "rev9"
            evidence_path = context_dir / "evidence" / "current-proof.md"
            context_path = context_dir / "context.json"
            log_path = root / "codex.log"
            evidence_path.parent.mkdir(parents=True)
            context_path.write_text(
                json.dumps(
                    {
                        "local_search_policy": {
                            "allowed_local_evidence_paths": [str(evidence_path)]
                        }
                    }
                ),
                encoding="utf-8",
            )
            log_path.write_text(
                "exec\n"
                f"/bin/zsh -lc 'sed -n 1,120p evidence/current-proof.md' in {context_dir}\n"
                " succeeded in 0ms:\n"
                "- Original source: `agents/generation/results/older_problem/phase2/artifacts/old-proof.md`\n"
                "- Historical checkout: `/Users/other/Documents/GitHub/Rethlas-CAS/agents/generation/results/older_problem/phase2/artifacts/report.md`\n",
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertEqual(errors, [])

    def test_evidence_boundary_still_checks_explicit_access_beside_allowed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            context_dir = root / "contexts" / "rev9"
            evidence_path = context_dir / "evidence" / "current-proof.md"
            context_path = context_dir / "context.json"
            log_path = root / "codex.log"
            evidence_path.parent.mkdir(parents=True)
            context_path.write_text(
                json.dumps(
                    {
                        "local_search_policy": {
                            "allowed_local_evidence_paths": [str(evidence_path)]
                        }
                    }
                ),
                encoding="utf-8",
            )
            stale_path = "agents/generation/results/older_problem/phase2/artifacts/old-proof.md"
            log_path.write_text(
                "exec\n"
                f"/bin/zsh -lc 'cat evidence/current-proof.md {stale_path}' in {context_dir}\n"
                " succeeded in 0ms:\n",
                encoding="utf-8",
            )

            errors = _evidence_boundary_errors(
                {"log_path": str(log_path)},
                {"context_path": str(context_path)},
            )

            self.assertTrue(errors)
            self.assertIn("old-proof.md", errors[0])

    def test_manifest_prioritizes_current_inference_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-artifact-priority-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            old_ids = [f"old-target-note-{index:02d}" for index in range(14)]
            operations: list[dict[str, Any]] = [
                {
                    "op": "attach_artifact",
                    "artifact_id": artifact_id,
                    "artifact_type": "research_notebook",
                    "content": f"Old target note {artifact_id}.",
                    "metadata": {"target_id": "claim-a"},
                }
                for artifact_id in old_ids
            ]
            operations.extend(
                [
                    {
                        "op": "attach_artifact",
                        "artifact_id": "current-inference-dossier",
                        "artifact_type": "proof_dossier",
                        "content": "Current route dossier.",
                        "metadata": {"target_id": "claim-a", "route_id": "route-a"},
                    },
                    {
                        "op": "add_claim",
                        "claim_id": "claim-a",
                        "kind": "lemma",
                        "statement": "A useful target claim.",
                        "parent_ids": ["root"],
                        "evidence_artifact_ids": old_ids,
                    },
                    {
                        "op": "add_route",
                        "route_id": "route-a",
                        "conclusion_claim_id": "claim-a",
                        "strategy": "Use the current dossier.",
                    },
                    {
                        "op": "add_inference",
                        "inference_id": "inf-a",
                        "route_id": "route-a",
                        "conclusion_claim_id": "claim-a",
                        "premise_claim_ids": [],
                        "validation_status": "plausible",
                        "explanation": "Current dossier proves claim-a.",
                        "evidence_artifact_ids": ["current-inference-dossier"],
                    },
                ]
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "claim-a",
                    "operations": operations,
                    "rationale": "seed old and current artifacts",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            manifest = build_context_manifest(store, target_id="claim-a", route_id="route-a", max_chars=60_000)

        artifact_ids = [artifact["artifact_id"] for artifact in manifest["artifacts"]]
        self.assertIn("current-inference-dossier", artifact_ids)
        self.assertLess(artifact_ids.index("current-inference-dossier"), artifact_ids.index(old_ids[0]))
        allowed_paths = manifest["local_search_policy"]["allowed_local_evidence_paths"]
        self.assertTrue(any(path.endswith("current-inference-dossier.md") for path in allowed_paths))

    def test_root_synthesis_manifest_exposes_recent_root_obstructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-root-synthesis-obstruction-context-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "root-obstruction-context",
                            "artifact_type": "route_obstruction",
                            "content": "A root-adjacent obstruction that future synthesis must account for.",
                            "metadata": {
                                "target_id": "root",
                                "route_id": "route-root-h2",
                                "obstruction_type": "route_killing_obstruction",
                            },
                        }
                    ],
                    "rationale": "seed root obstruction artifact",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = {
                "mode": "prove",
                "target_id": "root",
                "search_intent": "executive_advisor_bottleneck_lock",
                "proof_spine_mode_required": True,
                "global_synthesis_required": True,
            }
            manifest = build_context_manifest(store, action=action, max_chars=60_000)

        artifact_ids = [artifact["artifact_id"] for artifact in manifest["artifacts"]]
        self.assertIn("root-obstruction-context", artifact_ids)
        allowed_paths = manifest["local_search_policy"]["allowed_local_evidence_paths"]
        self.assertTrue(any(path.endswith("root-obstruction-context.txt") for path in allowed_paths))
        packet_artifacts = manifest["researcher_packet"]["proof_dossier_artifacts"]
        self.assertIn("root-obstruction-context", [artifact["artifact_id"] for artifact in packet_artifacts])

    def test_verified_root_route_integrates_before_unrelated_blocking_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-integrate-before-debt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")

            card_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "cache_retrieval_card",
                            "card_id": "retrieval-exact-root",
                            "target_id": "root",
                            "exact_statement": "Target theorem.",
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Exact Paper",
                                "theorem_number": "Theorem 1",
                                "arxiv": "arXiv:0000.00001",
                            },
                            "source_version": "arXiv:0000.00001",
                            "source_location": "Theorem 1",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {
                                "target_id": "root",
                                "classification": "direct_match",
                                "theorem_matching_status": "verified_statement_match",
                                "implication_to_target_verified": True,
                            },
                        }
                    ],
                    "rationale": "cache exact theorem",
                },
            )
            self.assertTrue(card_outcome.accepted, card_outcome.errors)

            cert_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "certify_external_citation",
                            "card_id": "retrieval-exact-root",
                            "target_id": "root",
                            "relation_to_target": "exact",
                            "implication_verified": True,
                        }
                    ],
                    "rationale": "certify exact cited theorem",
                },
            )
            self.assertTrue(cert_outcome.accepted, cert_outcome.errors)

            claim_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "old-construction-branch",
                            "kind": "lemma",
                            "statement": "An old construction branch remains unresolved.",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        }
                    ],
                    "rationale": "seed old branch",
                },
            )
            self.assertTrue(claim_outcome.accepted, claim_outcome.errors)

            debt_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 3,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "old-construction-branch",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-old-branch",
                            "owner_type": "claim",
                            "owner_id": "old-construction-branch",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Old branch is still missing an internal construction.",
                            "suggested_next_target": "old-construction-branch",
                        }
                    ],
                    "rationale": "seed unrelated debt",
                },
            )
            self.assertTrue(debt_outcome.accepted, debt_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")
            root_integration_companions = parallel_companion_actions(
                store,
                action,
                research_mode="balanced",
                web_search="live",
            )

        self.assertEqual(action["mode"], "integrate")
        self.assertEqual(action["target_id"], "root")
        self.assertTrue(action["route_id"].startswith("route-citation-"))
        self.assertEqual(root_integration_companions, [])

    def test_integration_candidates_skip_new_route_claim_and_inference_blockers(self) -> None:
        verified_claim = claim(
            "ready-lemma",
            1,
            validation_status="informally_verified",
            parent_ids=["root"],
        )
        verified_claim["evidence_artifact_ids_json"] = json.dumps(["verification-ready-lemma"])
        ready_route = route("route-ready-lemma", conclusion_claim_id="ready-lemma")
        ready_inference = inference(
            "inf-ready-lemma",
            route_id="route-ready-lemma",
            conclusion_claim_id="ready-lemma",
            validation_status="informally_verified",
        )
        verification_artifact = {
            "artifact_id": "verification-ready-lemma",
            "artifact_type": "verification_report",
            "producer_role": "strict_informal_verifier",
            "created_at": "2026-01-02T00:00:00+00:00",
            "metadata_json": json.dumps(
                {
                    "verdict": "verified",
                    "verification_report": {
                        "critical_errors": [],
                        "gaps": [],
                        "blocking_gap": False,
                    },
                }
            ),
        }
        for owner_type, owner_id in (
            ("route", "route-ready-lemma"),
            ("claim", "ready-lemma"),
            ("inference", "inf-ready-lemma"),
        ):
            with self.subTest(owner_type=owner_type):
                state = {
                    "claims": [verified_claim],
                    "routes": [ready_route],
                    "inferences": [ready_inference],
                    "debts": [
                        debt(
                            f"debt-after-verification-{owner_type}",
                            owner_type=owner_type,
                            owner_id=owner_id,
                            last_seen="2026-01-03T00:00:00+00:00",
                        )
                    ],
                    "artifacts": [verification_artifact],
                }

                self.assertEqual(_integration_candidates(state), [])

    def test_integration_candidates_allow_older_entity_debt_but_keep_route_debt(self) -> None:
        verified_claim = claim(
            "ready-lemma",
            1,
            validation_status="informally_verified",
            parent_ids=["root"],
        )
        verified_claim["evidence_artifact_ids_json"] = json.dumps(["verification-ready-lemma"])
        verified_inference = inference(
            "inf-ready-lemma",
            route_id="route-ready-lemma",
            conclusion_claim_id="ready-lemma",
            validation_status="informally_verified",
        )
        verified_inference["evidence_artifact_ids_json"] = json.dumps(["verification-ready-lemma"])
        verification_artifact = {
            "artifact_id": "verification-ready-lemma",
            "artifact_type": "verification_report",
            "producer_role": "strict_informal_verifier",
            "created_at": "2026-01-02T00:00:00+00:00",
            "metadata_json": json.dumps(
                {
                    "verdict": "correct_no_gaps",
                    "verification_report": {
                        "critical_errors": [],
                        "gaps": [],
                        "blocking_gap": False,
                    },
                }
            ),
        }
        for owner_type, owner_id, should_integrate in (
            ("claim", "ready-lemma", True),
            ("inference", "inf-ready-lemma", True),
            ("route", "route-ready-lemma", False),
        ):
            with self.subTest(owner_type=owner_type):
                state = {
                    "claims": [verified_claim],
                    "routes": [route("route-ready-lemma", conclusion_claim_id="ready-lemma")],
                    "inferences": [verified_inference],
                    "debts": [
                        debt(
                            "debt-before-verification",
                            owner_type=owner_type,
                            owner_id=owner_id,
                            last_seen="2026-01-01T00:00:00+00:00",
                        )
                    ],
                    "artifacts": [verification_artifact],
                }

                candidates = _integration_candidates(state)

                self.assertEqual(bool(candidates), should_integrate)

    def test_verified_side_route_integrates_while_unrelated_work_continues_in_parallel(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "scheduler-parallel-integration-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            store.set_parallel_branches(3, reason="exercise parallel integration")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "researcher",
                    "target_id": "ready-lemma",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "verified-premise",
                            "kind": "lemma",
                            "statement": "A verified premise.",
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "ready-lemma",
                            "kind": "lemma",
                            "statement": "A ready side lemma.",
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-ready-lemma",
                            "conclusion_claim_id": "ready-lemma",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the verified terminal inference.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-ready-terminal",
                            "route_id": "route-ready-lemma",
                            "conclusion_claim_id": "ready-lemma",
                            "premise_claim_ids": ["verified-premise"],
                            "validation_status": "untested",
                            "explanation": "The verified premise proves the side lemma.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-stale-alternative",
                            "route_id": "route-ready-lemma",
                            "conclusion_claim_id": "ready-lemma",
                            "premise_claim_ids": [],
                            "validation_status": "untested",
                            "explanation": "An older alternative attempt.",
                        },
                    ],
                    "rationale": "seed an integration-ready side route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                conn.execute(
                    "UPDATE claims SET validation_status='informally_verified' "
                    "WHERE claim_id IN ('verified-premise', 'ready-lemma')"
                )
                conn.execute(
                    "UPDATE inferences SET validation_status='informally_verified' "
                    "WHERE inference_id='inf-ready-terminal'"
                )
                conn.commit()

            action = next_action(store, research_mode="balanced", web_search="disabled")
            companions = parallel_companion_actions(
                store,
                action,
                research_mode="balanced",
                web_search="disabled",
            )
            strict_primary = {
                "mode": "prove",
                "target_id": "root",
                "route_id": "route-strict-check",
            }
            strict_companions = parallel_companion_actions(
                store,
                strict_primary,
                research_mode="balanced",
                web_search="disabled",
            )

        self.assertEqual(action["mode"], "integrate")
        self.assertEqual(action["target_id"], "ready-lemma")
        self.assertEqual(action["integration_terminal_inference_ids"], ["inf-ready-terminal"])
        self.assertTrue(companions)
        self.assertTrue(all(item["target_id"] != "ready-lemma" for item in companions))
        self.assertTrue(all(item.get("integration_parallel_safe") for item in companions))
        self.assertFalse(any(item["mode"] == "integrate" for item in strict_companions))

    def test_definition_uncertainty_schedules_definition_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-definition-audit-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "cache_retrieval_card",
                            "card_id": "retrieval-near-exact-defs",
                            "target_id": "root",
                            "exact_statement": "Target theorem with source terminology.",
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Near Exact Paper",
                                "theorem_number": "Theorem 2",
                                "arxiv": "arXiv:0000.00002",
                            },
                            "source_version": "arXiv:0000.00002",
                            "source_location": "Theorem 2",
                            "hypotheses": [],
                            "local_definitions": ["source uses a possibly different definition"],
                            "missing_hypotheses": ["definition match for the main terminology"],
                            "applicability": {
                                "target_id": "root",
                                "classification": "direct_match",
                                "theorem_matching_status": "unverified_definition_match",
                                "implication_to_target_verified": False,
                            },
                        }
                    ],
                    "rationale": "cache near-exact theorem with definition uncertainty",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "audit_definitions")
        self.assertTrue(action["definition_audit_required"])
        self.assertEqual(action["retrieval_card_id"], "retrieval-near-exact-defs")
        self.assertEqual(actor_role_for_action(action), "literature_researcher")

    def test_multiple_partial_cards_schedule_source_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-source-synthesis-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            for index, relation in enumerate(["partial_match", "method_match"]):
                outcome = apply_patch(
                    store,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": index,
                        "actor_role": "literature_researcher",
                        "target_id": "root",
                        "operations": [
                            {
                                "op": "cache_retrieval_card",
                                "card_id": f"retrieval-partial-{index}",
                                "target_id": "root",
                                "exact_statement": f"Partial source theorem {index}.",
                                "source_identifiers": {
                                    "author": "A. Author",
                                    "title": f"Partial Paper {index}",
                                    "theorem_number": f"Theorem {index + 1}",
                                    "arxiv": f"arXiv:0000.0001{index}",
                                },
                                "source_version": f"arXiv:0000.0001{index}",
                                "source_location": f"Theorem {index + 1}",
                                "hypotheses": [],
                                "local_definitions": [],
                                "missing_hypotheses": [],
                                "applicability": {
                                    "target_id": "root",
                                    "classification": relation,
                                    "theorem_matching_status": "partial_match_checked",
                                },
                            }
                        ],
                        "rationale": "cache partial source",
                    },
                )
                self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "synthesize_sources")
        self.assertTrue(action["source_synthesis_required"])
        self.assertEqual(actor_role_for_action(action), "literature_researcher")

    def test_verifier_citation_debt_schedules_exact_theorem_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-exact-citation-debt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-lang-shintani-reference",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "missing_reference",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Provide a precise citation or complete local proof for finite Lang-Shintani H^1-triviality.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "strict verifier requests exact citation",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="hard_problem", web_search="live")
            manifest = build_context_manifest(store, action=action)
            compact_manifest = build_context_manifest(store, action=action, max_chars=1200)

        self.assertEqual(action["mode"], "retrieve")
        self.assertEqual(action["search_intent"], "exact_theorem_search")
        self.assertTrue(action["exact_theorem_search_required"])
        self.assertEqual(action["debt_id"], "debt-lang-shintani-reference")
        self.assertEqual(action["search_permission"], "live")
        self.assertIn("Lang-Shintani", action["requested_query"])
        self.assertEqual(manifest["research_task"]["exact_lookup_policy"]["max_primary_retrieval_cards"], 1)
        self.assertTrue(manifest["research_task"]["exact_lookup_policy"]["stop_after_first_checked_match"])
        self.assertIn("one decisive retrieval card", manifest["research_task"]["stop_rule"])
        self.assertEqual(compact_manifest["role_context_policy"]["authoritative_packet"], "research_task")
        self.assertIn("exact_lookup_policy", compact_manifest["research_task"])
        self.assertEqual(actor_role_for_action(action), "literature_researcher")

    def test_verifier_citation_debt_does_not_reopen_integrated_claim(self) -> None:
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim(
                    "integrated-classical-branch",
                    1,
                    validation_status="informally_verified",
                    lifecycle_status="integrated",
                    parent_ids=["root"],
                ),
            ],
            "routes": [],
            "inferences": [],
            "debts": [
                debt(
                    "stale-classification-source-debt",
                    owner_id="integrated-classical-branch",
                    suggested_next_target="integrated-classical-branch",
                    debt_type="missing_reference",
                    obligation="Supply the exact automorphism classification source used by the old route.",
                )
            ],
            "research_artifacts": [],
            "recent_runs": [],
        }

        action = _verifier_blocked_citation_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="hard_problem",
            web_search="live",
        )

        self.assertIsNone(action)

    def test_artifact_packet_prefers_recent_inference_evidence_over_storage_order(self) -> None:
        artifacts = [
            {
                "artifact_id": f"artifact-{index:02d}",
                "artifact_type": "proof_dossier",
                "producer_role": "researcher",
                "state_revision": index,
                "created_at": f"2026-01-01T00:{index:02d}:00+00:00",
                "content_summary": f"Evidence revision {index}.",
                "sha256": f"sha-{index}",
                "path": f"/tmp/artifact-{index:02d}.md",
            }
            for index in range(14)
        ]
        state = {
            "problem_state": {"current_revision": 14},
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [],
            "inferences": [],
            "debts": [],
            "artifacts": artifacts,
        }
        selected = _select_artifacts(
            state,
            ["root"],
            None,
            [
                {
                    **inference("inf-root", route_id="route-root", conclusion_claim_id="root"),
                    # This mirrors the alphabetized set-union persisted by the store.
                    "evidence_artifact_ids": [row["artifact_id"] for row in artifacts],
                }
            ],
            [],
            target_id="root",
            action={"mode": "retrieve", "target_id": "root"},
        )

        selected_ids = [row["artifact_id"] for row in selected]
        self.assertEqual(len(selected_ids), 12)
        self.assertEqual(selected_ids[0], "artifact-13")
        self.assertIn("artifact-12", selected_ids)
        self.assertNotIn("artifact-00", selected_ids)

    def test_computation_audit_debt_is_not_exact_theorem_search(self) -> None:
        debt_row = debt(
            "debt-q0-generation-audit",
            owner_id="root",
            debt_type="proof_obligation",
            obligation=(
                "Provide a complete local proof or auditable finite computation for Q0=U semidirect S5. "
                "The evidence must include explicit code/query transcript, finite scope, class sizes, "
                "generated-subgroup test, output, and the deduction to order 1920."
            ),
        )

        self.assertFalse(_is_exact_citation_debt(debt_row))

    def test_named_support_precheck_runs_before_strict_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-support-precheck-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "pd-lang-shintani-route",
                            "artifact_type": "proof_dossier",
                            "content": "The route reduces the theorem to Lang-Shintani H^1 triviality for a finite graph-field automorphism.",
                            "metadata": {"target_id": "root", "route_id": "route-lang-shintani"},
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-lang-shintani",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the Lang-Shintani theorem to close the finite graph-field case.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-lang-shintani",
                            "route_id": "route-lang-shintani",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "Apply Lang-Shintani H^1 triviality.",
                            "evidence_artifact_ids": ["pd-lang-shintani-route"],
                        },
                    ],
                    "rationale": "seed verifier-ready route with named theorem dependency",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="hard_problem", web_search="live")

        self.assertEqual(action["mode"], "retrieve")
        self.assertEqual(action["route_id"], "route-lang-shintani")
        self.assertEqual(action["search_intent"], "support_lemma_precheck")
        self.assertTrue(action["support_lemma_precheck_required"])
        self.assertTrue(action["exact_theorem_search_required"])
        self.assertEqual(action["support_lemma_label"], "lang_shintani")
        self.assertEqual(actor_role_for_action(action), "literature_researcher")

    def test_researcher_literature_request_schedules_targeted_retrieval_before_generic_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-search-request-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            debt = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-local-proof-gap",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Find a theorem identifying the obstruction group.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "seed proof gap",
                },
            )
            self.assertTrue(debt.accepted, debt.errors)
            request = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "search-request-obstruction",
                            "artifact_type": "literature_search_request",
                            "content": "Search for a theorem identifying the obstruction group in the local notation.",
                            "metadata": {
                                "search_request_id": "req-obstruction",
                                "target_id": "root",
                                "query": "obstruction group identification theorem",
                                "missing_theorem": "A source theorem identifying the obstruction group.",
                                "proof_obligation": "Close debt-local-proof-gap.",
                                "acceptance_criteria": ["exact theorem location", "hypotheses translated to local notation"],
                                "librarian_level": "reader",
                            },
                        }
                    ],
                    "rationale": "ask librarian for targeted theorem search",
                },
            )
            self.assertTrue(request.accepted, request.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "retrieve")
        self.assertEqual(actor_role_for_action(action), "literature_researcher")
        self.assertEqual(action["search_intent"], "researcher_search_request")
        self.assertEqual(action["search_request_id"], "req-obstruction")
        self.assertEqual(action["search_permission"], "local")
        self.assertTrue(action["local_theorem_search_allowed"])

    def test_source_adaptation_answering_search_request_returns_to_researcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-source-digest-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            request = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "search-request-method",
                            "artifact_type": "literature_search_request",
                            "content": "Search for a method theorem that could prove the root.",
                            "metadata": {
                                "search_request_id": "req-method",
                                "target_id": "root",
                                "query": "method theorem for target",
                            },
                        }
                    ],
                    "rationale": "ask for method source",
                },
            )
            self.assertTrue(request.accepted, request.errors)
            advisor = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "advisor-root-bottleneck-before-source",
                            "artifact_type": "advisor_report",
                            "content": "Keep the root theorem as the decisive bottleneck.",
                            "metadata": {
                                "advisor_followup_required": True,
                                "triage_status": "decisive_root_bottleneck",
                                "bottleneck_obligation": "Prove the root theorem.",
                                "next_decisive_task": "Attack the root theorem.",
                                "next_role": "researcher",
                                "next_target_id": "root",
                            },
                        }
                    ],
                    "rationale": "record advisor lock before librarian returns",
                },
            )
            self.assertTrue(advisor.accepted, advisor.errors)
            handoff = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "cache_retrieval_card",
                            "card_id": "retrieval-method-source",
                            "target_id": "root",
                            "exact_statement": "A method theorem that proves a related local target.",
                            "source_identifiers": {"author": "A. Author", "title": "Method Paper", "theorem_number": "Theorem 3"},
                            "source_version": "unit-test",
                            "source_location": "Theorem 3",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {
                                "target_id": "root",
                                "classification": "method_match",
                                "search_request_id": "req-method",
                                "source_request_artifact_id": "search-request-method",
                            },
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "source-adaptation-method",
                            "artifact_type": "source_adaptation_notes",
                            "content": "The source theorem translates into a local proof strategy for the root.",
                            "metadata": {
                                "target_id": "root",
                                "search_request_id": "req-method",
                                "source_request_artifact_id": "search-request-method",
                                "checked_hypotheses": [],
                                "missing_hypotheses": [],
                            },
                        },
                    ],
                    "rationale": "answer search request with source handoff",
                },
            )
            self.assertTrue(handoff.accepted, handoff.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertTrue(action["source_adaptation_digest_required"])
        self.assertEqual(action["source_artifact_id"], "source-adaptation-method")
        self.assertEqual(manifest["workflow_action"]["search_request_id"], "req-method")
        self.assertTrue(any(row["artifact_id"] == "source-adaptation-method" for row in manifest["researcher_packet"]["proof_dossier_artifacts"]))

    def test_source_adaptation_digest_prioritizes_fresh_debt_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-source-digest-priority-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "big-old-dossier-1",
                            "artifact_type": "proof_dossier",
                            "content": "old route context\n" + ("A" * 9000),
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "big-old-dossier-2",
                            "artifact_type": "proof_dossier",
                            "content": "older route context\n" + ("B" * 9000),
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "fresh-source-synthesis",
                            "artifact_type": "source_synthesis_report",
                            "content": "Fresh synthesis that created the new compatibility debt.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "fresh-source-adaptation",
                            "artifact_type": "source_adaptation_notes",
                            "content": "Fresh source adaptation to digest into the proof route.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "aaa-old-proof-debt",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Old route gap.",
                            "source_artifact_ids": ["big-old-dossier-1", "big-old-dossier-2"],
                            "suggested_next_target": "root",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "zzz-fresh-source-debt",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "missing_hypothesis",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Digest fresh source synthesis.",
                            "source_artifact_ids": ["fresh-source-synthesis", "fresh-source-adaptation"],
                            "suggested_next_target": "root",
                        },
                    ],
                    "rationale": "create source digest context",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            manifest = build_context_manifest(
                store,
                action={
                    "mode": "reduce",
                    "target_id": "root",
                    "source_adaptation_digest_required": True,
                    "source_artifact_id": "fresh-source-adaptation",
                },
            )

        loaded_ids = [row["artifact_id"] for row in manifest["researcher_packet"]["proof_dossier_artifacts"]]
        self.assertIn("fresh-source-adaptation", loaded_ids)
        self.assertIn("fresh-source-synthesis", loaded_ids)
        self.assertLess(loaded_ids.index("fresh-source-adaptation"), loaded_ids.index("big-old-dossier-1"))
        self.assertLess(loaded_ids.index("fresh-source-synthesis"), loaded_ids.index("big-old-dossier-1"))

    def test_retrieve_manifest_includes_researcher_search_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-search-request-context-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "search-request-context",
                            "artifact_type": "literature_search_request",
                            "content": "Find an exact theorem with no forbidden solved-result source.",
                            "metadata": {
                                "search_request_id": "req-context",
                                "target_id": "root",
                                "query": "exact theorem avoiding forbidden source",
                                "forbidden_sources": ["paper with the result"],
                            },
                        }
                    ],
                    "rationale": "ask targeted search",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action)

        request = manifest["research_task"]["researcher_search_request"]
        self.assertEqual(request["search_request_id"], "req-context")
        self.assertIn("forbidden", request["content"])
        self.assertIn("paper with the result", request["forbidden_sources"])

    def test_active_decomposition_plan_schedules_subgoal_work_before_new_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-decomposition-plan-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-root",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan: prove lemma-a, then use it to prove the root.",
                            "metadata": {
                                "decomposition_plan_id": "plan-root-a",
                                "parent_claim_id": "root",
                                "subgoal_claim_ids": ["lemma-a"],
                                "direct_attempts": ["direct proof stalls at obstruction A"],
                                "failure_point": "obstruction A",
                                "why_subgoals_imply_parent": "lemma-a removes obstruction A",
                                "acceptance_criteria": ["lemma-a verified", "parent implication verified"],
                            },
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "lemma-a",
                            "statement": "Lemma A removes the obstruction in the target theorem.",
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                        },
                    ],
                    "rationale": "create decomposition plan",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, target_id=action["target_id"], action=action)

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "lemma-a")
        self.assertTrue(action["direct_solve_required"])
        self.assertTrue(action["decomposition_step_required"])
        self.assertEqual(action["decomposition_plan_id"], "plan-root-a")
        self.assertTrue(any(row["artifact_id"] == "decomp-plan-root" for row in manifest["researcher_packet"]["decomposition_artifacts"]))

    def test_verifier_ready_route_preempts_decomposition_branch_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-preempts-decomposition-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root-proof",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the assembled proof dossier.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-proof",
                            "route_id": "route-root-proof",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The repaired root proof is ready for strict checking.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-root",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan: prove lemma-a, then use it to prove the root.",
                            "metadata": {
                                "decomposition_plan_id": "plan-root-a",
                                "parent_claim_id": "root",
                                "subgoal_claim_ids": ["lemma-a"],
                                "assembly_argument": "lemma-a implies root",
                            },
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "lemma-a",
                            "statement": "Lemma A removes the obstruction in the target theorem.",
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                        },
                    ],
                    "rationale": "seed verifier-ready root route and decomposition plan",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "route-root-proof")
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")
        self.assertFalse(action.get("decomposition_step_required", False))
        self.assertEqual(action["route_readiness"]["level"], "verifier_ready")
        self.assertTrue(action["route_readiness"]["verifier_ready"])

    def test_verifier_ready_route_preempts_exact_citation_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-preempts-citation-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            route_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "direct-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete direct proof of the target theorem.",
                            "metadata": {"target_id": "root", "route_id": "route-root-direct"},
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-direct",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the direct proof dossier.",
                            "evidence_artifact_ids": ["direct-proof-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-direct",
                            "route_id": "route-root-direct",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The direct proof dossier proves the root theorem.",
                            "evidence_artifact_ids": ["direct-proof-dossier"],
                        },
                    ],
                    "rationale": "seed verifier-ready direct route",
                },
            )
            self.assertTrue(route_outcome.accepted, route_outcome.errors)
            card_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "literature_researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "cache_retrieval_card",
                            "card_id": "retrieval-exact-root",
                            "target_id": "root",
                            "exact_statement": "Target theorem.",
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Exact Paper",
                                "theorem_number": "Theorem 1",
                                "doi": "10.0000/exact",
                            },
                            "source_version": "doi:10.0000/exact",
                            "source_location": "Theorem 1",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {
                                "target_id": "root",
                                "classification": "direct_match",
                                "theorem_matching_status": "verified_statement_match",
                                "implication_to_target_verified": True,
                            },
                        }
                    ],
                    "rationale": "seed exact citation candidate",
                },
            )
            self.assertTrue(card_outcome.accepted, card_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")
            companions = parallel_companion_actions(store, action, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "route-root-direct")
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")
        self.assertTrue(action["verify_ready_route_policy"])
        self.assertNotIn("citation_triage_required", action)
        self.assertNotIn("retrieval_card_id", action)
        self.assertEqual(companions, [])

    def test_verifier_action_does_not_spawn_literature_companion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-no-literature-companion-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "direct-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete direct proof of the target theorem.",
                            "metadata": {"target_id": "root", "route_id": "route-root-direct"},
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-direct",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the direct proof dossier.",
                            "evidence_artifact_ids": ["direct-proof-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-direct",
                            "route_id": "route-root-direct",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The direct proof dossier proves the root theorem.",
                            "evidence_artifact_ids": ["direct-proof-dossier"],
                        },
                    ],
                    "rationale": "seed verifier-ready direct route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")
            companions = parallel_companion_actions(store, action, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["route_id"], "route-root-direct")
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")
        self.assertEqual(companions, [])

    def test_verifier_action_spawns_distinct_ready_verifier_companions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "scheduler-parallel-ready-verifiers-test",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Target theorem.")
            operations = []
            for index in range(3):
                claim_id = f"lemma-{index}"
                route_id = f"route-{index}"
                artifact_id = f"dossier-{index}"
                operations.extend(
                    [
                        {
                            "op": "attach_artifact",
                            "artifact_id": artifact_id,
                            "artifact_type": "proof_dossier",
                            "content": f"Complete proof of lemma {index}.",
                            "metadata": {"target_id": claim_id, "route_id": route_id},
                        },
                        {
                            "op": "add_claim",
                            "claim_id": claim_id,
                            "kind": "lemma",
                            "statement": f"Lemma {index}.",
                            "parent_ids": ["root"],
                            "evidence_artifact_ids": [artifact_id],
                        },
                        {
                            "op": "add_route",
                            "route_id": route_id,
                            "conclusion_claim_id": claim_id,
                            "relation_to_parent": "sufficient",
                            "strategy": f"Use dossier {index}.",
                            "evidence_artifact_ids": [artifact_id],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": f"inf-{index}",
                            "route_id": route_id,
                            "conclusion_claim_id": claim_id,
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": f"The dossier proves lemma {index}.",
                            "evidence_artifact_ids": [artifact_id],
                        },
                    ]
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
                    "rationale": "seed three independent verifier-ready routes",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            store.set_parallel_branches(3, reason="test parallel verifier wave", source="test")

            primary = {
                "mode": "prove",
                "target_id": "lemma-0",
                "route_id": "route-0",
                "verify_ready_route_policy": True,
            }
            companions = parallel_companion_actions(
                store,
                primary,
                research_mode="balanced",
                web_search="disabled",
            )
            advisor_companions = parallel_companion_actions(
                store,
                {
                    "mode": "triage_routes",
                    "target_id": "root",
                    "route_id": "",
                    "search_intent": "advisor_evidence_synthesis",
                },
                research_mode="balanced",
                web_search="disabled",
            )

        self.assertEqual([item["route_id"] for item in companions], ["route-1", "route-2"])
        self.assertTrue(all(actor_role_for_action(item) == "strict_informal_verifier" for item in companions))
        self.assertTrue(all(item["parallel_companion"] for item in companions))
        self.assertTrue(all(item["strict_verifier_scope"] == "single_route_verification_packet" for item in companions))
        advisor_verifiers = [
            item
            for item in advisor_companions
            if actor_role_for_action(item) == "strict_informal_verifier"
        ]
        self.assertEqual(
            [item["route_id"] for item in advisor_verifiers],
            ["route-0", "route-1", "route-2"],
        )

    def test_parallel_companion_adds_strict_verifier_for_ready_route_during_advisor_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-parallel-verifier-during-advisor-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "direct-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete direct proof of the target theorem.",
                            "metadata": {"target_id": "root", "route_id": "route-root-direct"},
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-direct",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the direct proof dossier.",
                            "evidence_artifact_ids": ["direct-proof-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-direct",
                            "route_id": "route-root-direct",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The direct proof dossier proves the root theorem.",
                            "evidence_artifact_ids": ["direct-proof-dossier"],
                        },
                    ],
                    "rationale": "seed verifier-ready direct route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            primary = {
                "mode": "triage_routes",
                "target_id": "root",
                "route_id": "",
                "search_intent": "advisor_evidence_synthesis",
            }
            companions = parallel_companion_actions(store, primary, research_mode="balanced", web_search="disabled")

        verifier = next(item for item in companions if actor_role_for_action(item) == "strict_informal_verifier")
        self.assertEqual(verifier["route_id"], "route-root-direct")
        self.assertEqual(verifier["search_intent"], "verify_ready_route")
        self.assertEqual(verifier["strict_verifier_scope"], "single_route_verification_packet")
        self.assertEqual(verifier["verifier_evidence_artifact_ids"], ["direct-proof-dossier"])
        self.assertTrue(verifier["strict_verifier_no_fresh_evidence"])
        self.assertTrue(verifier["strict_verifier_no_cas"])
        self.assertTrue(verifier["parallel_companion"])

    def test_verifier_ready_summaries_skip_refuted_conclusion_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-ready-summary-refuted-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "refuted-lemma",
                            "statement": "Refuted lemma.",
                            "validation_status": "plausible",
                            "parent_ids": ["root"],
                            "root_impact": 0.8,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "open-lemma",
                            "statement": "Open lemma.",
                            "validation_status": "untested",
                            "parent_ids": ["root"],
                            "root_impact": 0.8,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "route-proof",
                            "artifact_type": "proof_dossier",
                            "content": "A route proof candidate.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-refuted-lemma",
                            "conclusion_claim_id": "refuted-lemma",
                            "relation_to_parent": "sufficient",
                            "strategy": "Prove a claim that is already refuted.",
                            "evidence_artifact_ids": ["route-proof"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-refuted-lemma",
                            "route_id": "route-refuted-lemma",
                            "conclusion_claim_id": "refuted-lemma",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "Evidence for the refuted claim.",
                            "evidence_artifact_ids": ["route-proof"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-open-lemma",
                            "conclusion_claim_id": "open-lemma",
                            "relation_to_parent": "sufficient",
                            "strategy": "Prove an open claim.",
                            "evidence_artifact_ids": ["route-proof"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-open-lemma",
                            "route_id": "route-open-lemma",
                            "conclusion_claim_id": "open-lemma",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "Evidence for the open claim.",
                            "evidence_artifact_ids": ["route-proof"],
                        },
                    ],
                    "rationale": "seed ready and non-ready routes",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with store.connect() as conn:
                conn.execute("UPDATE claims SET validation_status='refuted' WHERE claim_id='refuted-lemma'")
                conn.commit()
            state = store.get_scheduler_state()

        refuted_readiness = route_verifier_readiness(state, "route-refuted-lemma")
        summaries = verifier_ready_route_summaries(state)

        self.assertFalse(refuted_readiness["verifier_ready"])
        self.assertIn("conclusion_claim_not_verifiable", refuted_readiness["missing_checks"])
        self.assertEqual([row["route_id"] for row in summaries], ["route-open-lemma"])

    def test_parallel_verifier_dedupes_same_route_evidence_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-parallel-verifier-dedupe-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "direct-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete direct proof of the target theorem.",
                            "metadata": {"target_id": "root", "route_id": "route-root-direct"},
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-direct",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the direct proof dossier.",
                            "evidence_artifact_ids": ["direct-proof-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-direct",
                            "route_id": "route-root-direct",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The direct proof dossier proves the root theorem.",
                            "evidence_artifact_ids": ["direct-proof-dossier"],
                        },
                    ],
                    "rationale": "seed verifier-ready direct route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            record_run(
                store,
                base_revision=store.get_revision(),
                run_id="strict-verifier-direct",
                mode="prove",
                target_id="root",
                route_id="route-root-direct",
                search_intent="verify_ready_route",
                actor_role="strict_informal_verifier",
            )

            primary = {"mode": "triage_routes", "target_id": "root", "route_id": ""}
            companions = parallel_companion_actions(store, primary, research_mode="balanced", web_search="disabled")

        self.assertFalse(any(actor_role_for_action(item) == "strict_informal_verifier" for item in companions))

    def test_explicit_repair_dossier_allows_verifier_to_adjudicate_old_debt(self) -> None:
        state = {
            "claims": [
                {
                    "claim_id": "root",
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "root_impact": 1.0,
                },
                {
                    "claim_id": "old-unverified-premise",
                    "lifecycle_status": "active",
                    "validation_status": "untested",
                    "root_impact": 0.1,
                },
            ],
            "routes": [
                {
                    "route_id": "route-root-repaired",
                    "conclusion_claim_id": "root",
                    "status": "active",
                    "relation_to_parent": "sufficient",
                    "evidence_artifact_ids_json": json.dumps(["repair-dossier"]),
                }
            ],
            "inferences": [
                {
                    "inference_id": "inf-root-old",
                    "route_id": "route-root-repaired",
                    "conclusion_claim_id": "root",
                    "premise_claim_ids": ["old-unverified-premise"],
                    "evidence_artifact_ids_json": json.dumps(["old-dossier"]),
                },
                {
                    "inference_id": "inf-root-dependency-free",
                    "route_id": "route-root-repaired",
                    "conclusion_claim_id": "root",
                    "premise_claim_ids": [],
                    "evidence_artifact_ids_json": json.dumps(["repair-dossier"]),
                },
            ],
            "debts": [
                {
                    "debt_id": "debt-root-old-gap",
                    "owner_type": "claim",
                    "owner_id": "root",
                    "status": "active",
                    "severity": "blocking",
                    "debt_type": "proof_gap",
                    "last_seen": "2026-01-01T00:00:00+00:00",
                }
            ],
            "research_artifacts": [
                {
                    "artifact_id": "repair-dossier",
                    "artifact_type": "proof_dossier",
                    "created_at": "2026-01-02T00:00:00+00:00",
                    "metadata_json": json.dumps(
                        {
                            "artifact_roi": "verifier_ready_route",
                            "route_id": "route-root-repaired",
                            "target_id": "root",
                            "next_decisive_action": "Run strict verification on the repaired route.",
                        }
                    ),
                }
            ],
        }

        readiness = route_verifier_readiness(state, "route-root-repaired")

        self.assertTrue(readiness["verifier_ready"], readiness)
        self.assertEqual(readiness["blocking_debt_count"], 0)
        self.assertIn("one_inference_has_verified_premises", readiness["ready_checks"])

    def test_deep_session_repair_allows_verifier_to_adjudicate_old_debt(self) -> None:
        route_row = route("route-root-deep-repair", conclusion_claim_id="root")
        route_row["evidence_artifact_ids_json"] = json.dumps(["deep-repair"])
        inference_row = inference(
            "inf-root-deep-repair",
            route_id="route-root-deep-repair",
            conclusion_claim_id="root",
            validation_status="plausible",
        )
        inference_row["evidence_artifact_ids_json"] = json.dumps(["deep-repair"])
        state = {
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [route_row],
            "inferences": [inference_row],
            "debts": [
                debt(
                    "debt-root-before-deep-repair",
                    owner_id="inf-root-deep-repair",
                    owner_type="inference",
                    last_seen="2026-01-01T00:00:00+00:00",
                )
            ],
            "research_artifacts": [
                {
                    "artifact_id": "deep-repair",
                    "artifact_type": "deep_session_report",
                    "created_at": "2026-01-02T00:00:00+00:00",
                    "metadata_json": json.dumps(
                        {
                            "artifact_roi": "verifier_ready_route",
                            "route_id": "route-root-deep-repair",
                            "target_id": "root",
                            "next_decisive_step": "Send the repaired root route to strict verification.",
                        }
                    ),
                }
            ],
        }

        readiness = route_verifier_readiness(state, "route-root-deep-repair")

        self.assertTrue(readiness["verifier_ready"], readiness)
        self.assertEqual(readiness["blocking_debt_count"], 0)

    def test_route_without_inference_gets_research_companion_not_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-route-needs-inference-companion-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root-needs-inference",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "A route skeleton exists but no inference evidence has been written.",
                        }
                    ],
                    "rationale": "seed route skeleton",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")
            companions = parallel_companion_actions(store, action, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(action["display_mode"], "researcher_prove")
        self.assertEqual(action["route_id"], "route-root-needs-inference")
        self.assertEqual(action["search_intent"], "route_proof_construction")
        self.assertTrue(action["proof_construction_required"])
        self.assertTrue(action["citation_allowed_in_proof"])
        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertTrue(action["long_mathematical_session_required"])
        self.assertEqual(len(companions), 1)
        counterexample = next(item for item in companions if item["mode"] == "refute")
        self.assertEqual(counterexample["target_id"], "root")
        self.assertTrue(counterexample["counterexample_search_required"])
        self.assertTrue(counterexample["counterexample_probe_required"])
        self.assertEqual(actor_role_for_action(counterexample), "villain")

    def test_duplicate_research_loop_schedules_route_triage_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-duplicate-work-guard-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="run-duplicate-root-1",
                mode="reduce",
                target_id="root",
                search_intent="independent_solve",
            )
            record_run(
                store,
                base_revision=1,
                run_id="run-duplicate-root-2",
                mode="reduce",
                target_id="root",
                search_intent="independent_solve",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "triage_routes")
        self.assertTrue(action["duplicate_work_guard"])
        self.assertEqual(action["duplicate_work_count"], 2)
        self.assertEqual(actor_role_for_action(action), "phd_advisor")

    def test_no_content_research_runs_force_route_proof_construction(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-no-content-research-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root-no-content",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "A plausible route skeleton exists.",
                        }
                    ],
                    "rationale": "seed route skeleton",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            record_run(
                store,
                base_revision=1,
                run_id="run-no-content-a",
                mode="reduce",
                target_id="root",
                route_id="route-root-no-content",
                search_intent="attempt_without_artifact_a",
            )
            record_run(
                store,
                base_revision=2,
                run_id="run-no-content-b",
                mode="reduce",
                target_id="root",
                route_id="route-root-no-content",
                search_intent="attempt_without_artifact_b",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(action["display_mode"], "researcher_prove")
        self.assertEqual(action["route_id"], "route-root-no-content")
        self.assertEqual(action["search_intent"], "route_proof_construction")
        self.assertTrue(action["proof_construction_required"])
        self.assertTrue(action["no_content_research_guard"])
        self.assertEqual(action["no_content_research_cluster"]["count"], 2)
        self.assertTrue(manifest["workflow_action"]["no_content_research_guard"])
        self.assertEqual(actor_role_for_action(action), "researcher")

    def test_retrieve_reduce_loop_schedules_advisor_circuit_breaker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-retrieve-reduce-loop-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="run-loop-retrieve-1",
                mode="retrieve",
                target_id="root",
                search_intent="literature_scoping",
                actor_role="literature_researcher",
            )
            record_run(
                store,
                base_revision=1,
                run_id="run-loop-reduce-1",
                mode="reduce",
                target_id="root",
                search_intent="route_repair_after_search",
            )
            record_run(
                store,
                base_revision=2,
                run_id="run-loop-retrieve-2",
                mode="retrieve",
                target_id="root",
                search_intent="literature_scoping",
                actor_role="literature_researcher",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "triage_routes")
        self.assertTrue(action["retrieve_reduce_loop_guard"])
        self.assertTrue(action["strategy_advisor_required"])
        self.assertEqual(action["search_intent"], "retrieve_reduce_circuit_breaker")
        self.assertEqual(action["retrieve_reduce_loop"]["recent_modes"], ["retrieve", "reduce", "retrieve"])
        self.assertEqual(actor_role_for_action(action), "phd_advisor")

    def test_retrieve_reduce_loop_preempts_pending_search_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-retrieve-reduce-loop-search-request-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            record_run(
                store,
                base_revision=0,
                run_id="run-loop-retrieve-1",
                mode="retrieve",
                target_id="root",
                route_id="route-root",
                search_intent="researcher_search_request",
                actor_role="literature_researcher",
            )
            record_run(
                store,
                base_revision=1,
                run_id="run-loop-reduce-1",
                mode="reduce",
                target_id="root",
                route_id="route-root",
                search_intent="source_adaptation_digest",
            )
            record_run(
                store,
                base_revision=2,
                run_id="run-loop-retrieve-2",
                mode="retrieve",
                target_id="root",
                route_id="route-root",
                search_intent="researcher_search_request",
                actor_role="literature_researcher",
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "search-request-loop",
                            "artifact_type": "literature_search_request",
                            "content": "Find one more exact theorem.",
                            "metadata": {
                                "search_request_id": "req-loop",
                                "target_id": "root",
                                "route_id": "route-root",
                                "query": "another exact theorem",
                            },
                        }
                    ],
                    "rationale": "ask targeted search during a retrieve/reduce loop",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "triage_routes")
        self.assertTrue(action["retrieve_reduce_loop_guard"])
        self.assertTrue(action["strategy_advisor_required"])
        self.assertEqual(action["search_intent"], "retrieve_reduce_circuit_breaker")
        self.assertEqual(actor_role_for_action(action), "phd_advisor")

    def test_duplicate_decomposition_branch_schedules_regulator_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-duplicate-branch-regulator-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-loop",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan: prove lemma-loop.",
                            "metadata": {
                                "decomposition_plan_id": "plan-loop",
                                "parent_claim_id": "root",
                                "subgoal_claim_ids": ["lemma-loop"],
                                "assembly_argument": "lemma-loop implies root",
                            },
                        },
                        {"op": "add_claim", "claim_id": "lemma-loop", "statement": "Lemma loop.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                    ],
                    "rationale": "seed decomposition branch",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            record_run(
                store,
                base_revision=1,
                run_id="run-branch-loop-1",
                mode="reduce",
                target_id="lemma-loop",
                search_intent="decomposition_plan_work",
            )
            record_run(
                store,
                base_revision=2,
                run_id="run-branch-loop-2",
                mode="reduce",
                target_id="lemma-loop",
                search_intent="decomposition_plan_work",
            )

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "regulate_decomposition")
        self.assertTrue(action["duplicate_work_guard"])
        self.assertEqual(action["decomposition_plan_id"], "plan-loop")
        self.assertEqual(action["blocked_branch_ids"], ["lemma-loop"])

    def test_decomposition_plan_respects_dependencies_before_parallel_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-decomposition-dependency-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-dependent",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan: prove lemma-a before lemma-b.",
                            "metadata": {
                                "decomposition_plan_id": "plan-dependent",
                                "parent_claim_id": "root",
                                "subgoal_claim_ids": ["lemma-b", "lemma-a"],
                                "dependency_edges": [{"from": "lemma-a", "to": "lemma-b"}],
                                "assembly_argument": "lemma-a and lemma-b imply root",
                            },
                        },
                        {"op": "add_claim", "claim_id": "lemma-a", "statement": "Lemma A.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                        {"op": "add_claim", "claim_id": "lemma-b", "statement": "Lemma B depends on Lemma A.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                    ],
                    "rationale": "create dependent plan",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "lemma-a")
        self.assertTrue(action["direct_solve_required"])
        self.assertEqual(action["decomposition_plan_id"], "plan-dependent")

    def test_decomposition_ready_branches_are_scheduler_ranked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-ranked-decomposition-branches-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-ranked",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan lists a lower-impact branch first, but both branches are ready.",
                            "metadata": {
                                "decomposition_plan_id": "plan-ranked",
                                "parent_claim_id": "root",
                                "subgoal_claim_ids": ["low-impact-branch", "high-impact-branch"],
                                "assembly_argument": "Both branches feed the parent proof.",
                            },
                        },
                        {"op": "add_claim", "claim_id": "low-impact-branch", "statement": "Low impact branch.", "parent_ids": ["root"], "root_impact": 0.25, "reduction_depth": 1},
                        {"op": "add_claim", "claim_id": "high-impact-branch", "statement": "High impact branch.", "parent_ids": ["root"], "root_impact": 0.95, "reduction_depth": 1},
                    ],
                    "rationale": "create ranked plan",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "high-impact-branch")
        self.assertEqual(action["decomposition_rank_policy"], "scheduler_ranked_dependency_ready_branch")

    def test_independent_decomposition_branches_schedule_parallel_companion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-parallel-decomposition-branches-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-parallel",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan: prove two independent branches.",
                            "metadata": {
                                "decomposition_plan_id": "plan-parallel",
                                "parent_claim_id": "root",
                                "plan_kind": "parallel_ingredients",
                                "subgoal_claim_ids": ["lemma-a", "lemma-b"],
                                "parallelizable_groups": [{"group_id": "ingredients", "members": ["lemma-a", "lemma-b"]}],
                                "assembly_argument": "lemma-a and lemma-b imply root",
                            },
                        },
                        {"op": "add_claim", "claim_id": "lemma-a", "statement": "Lemma A.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                        {"op": "add_claim", "claim_id": "lemma-b", "statement": "Lemma B.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                    ],
                    "rationale": "create parallel plan",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            companions = parallel_companion_actions(store, action, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "lemma-a")
        self.assertTrue(action["direct_solve_required"])
        self.assertEqual(len(companions), 1)
        self.assertEqual(companions[0]["mode"], "prove")
        self.assertEqual(companions[0]["target_id"], "lemma-b")
        self.assertTrue(companions[0]["direct_solve_required"])
        self.assertEqual(companions[0]["search_intent"], "parallel_decomposition_branch")
        self.assertEqual(companions[0]["decomposition_parallel_group"], "ingredients")

    def test_decomposition_branches_without_parallel_group_do_not_spawn_branch_companion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-serial-decomposition-branches-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-serial",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan: prove two branches, but no independence metadata is supplied.",
                            "metadata": {
                                "decomposition_plan_id": "plan-serial",
                                "parent_claim_id": "root",
                                "subgoal_claim_ids": ["lemma-a", "lemma-b"],
                                "assembly_argument": "lemma-a and lemma-b imply root",
                            },
                        },
                        {"op": "add_claim", "claim_id": "lemma-a", "statement": "Lemma A.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                        {"op": "add_claim", "claim_id": "lemma-b", "statement": "Lemma B.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                    ],
                    "rationale": "create serial plan",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")
            companions = parallel_companion_actions(store, action, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "lemma-a")
        self.assertTrue(action["direct_solve_required"])
        self.assertEqual(len(companions), 1)
        self.assertEqual(companions[0]["mode"], "refute")
        self.assertEqual(companions[0]["search_intent"], "parallel_counterexample_search")
        self.assertEqual(actor_role_for_action(companions[0]), "villain")
        self.assertNotEqual(companions[0].get("search_intent"), "parallel_decomposition_branch")

    def test_high_impact_root_local_branch_gets_counterexample_companion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-high-impact-counterexample-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "high-impact-branch",
                            "statement": "A high-impact root-local branch.",
                            "parent_ids": ["root"],
                            "root_impact": 0.85,
                            "reduction_depth": 1,
                        }
                    ],
                    "rationale": "seed high-impact branch",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            primary = {
                "mode": "prove",
                "target_id": "high-impact-branch",
                "route_id": "",
                "direct_solve_required": True,
            }

            companions = parallel_companion_actions(store, primary, research_mode="balanced", web_search="disabled")

        self.assertEqual(len(companions), 1)
        self.assertEqual(companions[0]["mode"], "refute")
        self.assertEqual(companions[0]["target_id"], "high-impact-branch")
        self.assertTrue(companions[0]["counterexample_search_required"])
        self.assertEqual(actor_role_for_action(companions[0]), "villain")

    def test_blocked_decomposition_plan_schedules_advisor_regulator(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-blocked-decomposition-regulator-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-blocked",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan: lemma-b depends on a missing branch.",
                            "metadata": {
                                "decomposition_plan_id": "plan-blocked",
                                "parent_claim_id": "root",
                                "subgoal_claim_ids": ["lemma-b"],
                                "dependency_edges": [{"from": "missing-lemma", "to": "lemma-b"}],
                            },
                        },
                        {"op": "add_claim", "claim_id": "lemma-b", "statement": "Lemma B.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                    ],
                    "rationale": "create blocked plan",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "regulate_decomposition")
        self.assertEqual(actor_role_for_action(action), "phd_advisor")
        self.assertTrue(action["decomposition_regulator_required"])
        self.assertEqual(action["decomposition_plan_id"], "plan-blocked")
        self.assertEqual(action["blocked_branch_ids"], ["lemma-b"])

    def test_failed_decomposition_plan_requires_advisor_regulation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-key-failure-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "failed-decomp-root",
                            "artifact_type": "failed_decomposition_plan",
                            "content": "The previous decomposition failed because both branches require the same missing lifting lemma.",
                            "metadata": {
                                "decomposition_plan_id": "plan-root-old",
                                "decomposition_plan_artifact_id": "decomp-plan-old",
                                "parent_claim_id": "root",
                                "failed_subgoal_ids": ["old-a", "old-b"],
                            },
                        }
                    ],
                    "rationale": "record failed decomposition",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "regulate_decomposition")
        self.assertEqual(actor_role_for_action(action), "phd_advisor")
        self.assertTrue(action["decomposition_regulator_required"])
        self.assertEqual(action["failed_decomposition_artifact_id"], "failed-decomp-root")
        self.assertEqual(action["decomposition_plan_id"], "plan-root-old")

    def test_completed_decomposition_subgoals_schedule_parent_implication_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-parent-implication-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "decomp-plan-parent",
                            "artifact_type": "decomposition_plan",
                            "content": "Plan: lemma-a implies the root via route-root.",
                            "metadata": {
                                "decomposition_plan_id": "plan-parent",
                                "parent_claim_id": "root",
                                "route_id": "route-root",
                                "subgoal_claim_ids": ["lemma-a"],
                            },
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "lemma-a",
                            "statement": "Lemma A supplies the needed parent implication.",
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use lemma-a to prove the root.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-from-lemma-a",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": ["lemma-a"],
                            "validation_status": "plausible",
                            "explanation": "The decomposition plan says lemma-a implies the root.",
                        },
                    ],
                    "rationale": "seed completed decomposition plan",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            verified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "lemma-a",
                    "operations": [
                        {"op": "attach_artifact", "artifact_id": "lemma-a-ok", "artifact_type": "verification_report", "metadata": {"verdict": "correct", "verification_report": {"critical_errors": [], "gaps": []}}},
                        {"op": "propose_status_transition", "target_type": "claim", "target_id": "lemma-a", "status_type": "validation", "new_status": "informally_verified", "evidence_artifact_ids": ["lemma-a-ok"]},
                    ],
                    "rationale": "verify subgoal",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "route-root")
        self.assertTrue(action["parent_implication_required"])
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")

    def test_too_many_active_main_trunks_schedule_route_triage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-route-triage-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            for index in range(4):
                outcome = apply_patch(
                    store,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "problem_id": store.problem_id,
                        "base_revision": index,
                        "actor_role": "researcher",
                        "target_id": "root",
                        "operations": [
                            {
                                "op": "add_claim",
                                "claim_id": f"trunk-{index}",
                                "kind": "lemma",
                                "statement": f"Main proof trunk {index}.",
                                "root_impact": 0.9,
                                "reduction_depth": 1,
                                "parent_ids": ["root"],
                            },
                            {
                                "op": "add_route",
                                "route_id": f"route-trunk-{index}",
                                "conclusion_claim_id": f"trunk-{index}",
                                "relation_to_parent": "sufficient",
                                "strategy": f"Prove main trunk {index}.",
                            },
                        ],
                        "rationale": "seed active trunk",
                    },
                )
                self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="independent", web_search="disabled")

        self.assertEqual(action["mode"], "triage_routes")
        self.assertTrue(action["route_triage_required"])
        self.assertEqual(actor_role_for_action(action), "phd_advisor")
        self.assertTrue(action["active_trunk_pressure"]["over_trunk_cap"])

    def test_debt_protected_routes_do_not_force_main_trunk_triage(self) -> None:
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0),
                *[
                    claim(f"main-{index}", 1, root_impact=0.9, parent_ids=["root"])
                    for index in range(3)
                ],
                *[
                    claim(f"repair-{index}", 2, root_impact=0.9, parent_ids=["main-0"])
                    for index in range(3)
                ],
            ],
            "routes": [
                *[
                    route(f"route-main-{index}", conclusion_claim_id=f"main-{index}")
                    for index in range(3)
                ],
                *[
                    route(f"route-repair-{index}", conclusion_claim_id=f"repair-{index}")
                    for index in range(3)
                ],
            ],
            "inferences": [],
            "debts": [
                debt(f"debt-repair-{index}", owner_id=f"repair-{index}")
                for index in range(3)
            ],
        }

        pressure = _active_main_trunk_pressure(state)

        self.assertFalse(pressure["over_trunk_cap"])
        self.assertEqual(pressure["active_main_trunk_count"], 3)
        self.assertEqual(
            pressure["debt_protected_route_ids"],
            ["route-repair-0", "route-repair-1", "route-repair-2"],
        )

    def test_blocking_debt_on_routed_target_schedules_researcher_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-routed-debt-repair-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "repair-target",
                            "kind": "lemma",
                            "statement": "Repair the concrete construction subcase.",
                            "root_impact": 0.9,
                            "reduction_depth": 2,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-repair-target",
                            "conclusion_claim_id": "repair-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Fill the concrete subcase proof gap.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-repair-target",
                            "owner_type": "claim",
                            "owner_id": "repair-target",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Close the concrete subcase proof gap.",
                            "suggested_next_target": "repair-target",
                        },
                    ],
                    "rationale": "seed routed debt",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(action["target_id"], "repair-target")
        self.assertEqual(action["route_id"], "route-repair-target")
        self.assertEqual(action["debt_id"], "debt-repair-target")
        self.assertTrue(action["proof_repair_required"])
        self.assertEqual(actor_role_for_action(action), "researcher")

    def test_blocking_debt_on_routed_target_with_inference_schedules_repair_not_duplicate_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-routed-debt-verify-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "repair-target",
                            "kind": "lemma",
                            "statement": "Repair the concrete construction subcase.",
                            "root_impact": 0.9,
                            "reduction_depth": 2,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-repair-target",
                            "conclusion_claim_id": "repair-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Repair the concrete subcase proof gap.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-repair-target",
                            "route_id": "route-repair-target",
                            "conclusion_claim_id": "repair-target",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "A candidate proof blueprint is ready for strict checking.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-repair-target",
                            "owner_type": "claim",
                            "owner_id": "repair-target",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Repair the concrete subcase proof gap before strict checking again.",
                            "suggested_next_target": "repair-target",
                        },
                    ],
                    "rationale": "seed routed debt with inference evidence",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(action["target_id"], "repair-target")
        self.assertEqual(action["route_id"], "route-repair-target")
        self.assertEqual(action["debt_id"], "debt-repair-target")
        self.assertTrue(action["proof_repair_required"])
        self.assertTrue(action["needs_proof_dossier"])
        self.assertNotIn("proof_repair_verification_required", action)
        self.assertEqual(actor_role_for_action(action), "researcher")

    def test_prove_or_refute_debt_on_routed_target_schedules_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-prove-or-refute-debt-verifier-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "prove-or-refute-target",
                            "kind": "lemma",
                            "statement": "Either prove or refute this local target.",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-refute-target",
                            "conclusion_claim_id": "prove-or-refute-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Verifier should check the proposed refutation route.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-refute-target",
                            "route_id": "route-refute-target",
                            "conclusion_claim_id": "prove-or-refute-target",
                            "premise_claim_ids": [],
                            "validation_status": "untested",
                            "explanation": "A proof/refutation candidate is ready for strict checking.",
                            "evidence_artifact_ids": ["refutation-dossier"],
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "refutation-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "Verifier-ready refutation dossier.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-prove-or-refute-target",
                            "owner_type": "claim",
                            "owner_id": "prove-or-refute-target",
                            "debt_type": "missing_proof_or_counterexample",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Prove or refute this local target.",
                            "suggested_next_target": "prove-or-refute-target",
                        },
                    ],
                    "rationale": "seed verifier-ready prove-or-refute route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "prove-or-refute-target")
        self.assertEqual(action["route_id"], "route-refute-target")
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")
        self.assertEqual(action["route_readiness"]["level"], "verifier_ready")

    def test_blocking_debt_on_route_premise_schedules_debt_not_duplicate_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-premise-debt-verify-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "root-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "The root follows from the cited premise once it is sourced.\n",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "route-obstruction",
                            "artifact_type": "research_diagnostic",
                            "content": "Obstruction: the route still needs the external construction theorem.\n",
                            "metadata": {"target_id": "root", "route_id": "route-root"},
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "external-premise",
                            "kind": "lemma",
                            "statement": "A needed external construction theorem holds.",
                            "validation_status": "untested",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the external construction theorem.",
                            "evidence_artifact_ids": ["root-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": ["external-premise"],
                            "validation_status": "plausible",
                            "explanation": "The route is ready except for the external premise source.",
                            "evidence_artifact_ids": ["root-dossier"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-external-premise-source",
                            "owner_type": "claim",
                            "owner_id": "external-premise",
                            "debt_type": "citation_verification",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Find the external construction theorem before rechecking the root route.",
                            "suggested_next_target": "external-premise",
                        },
                    ],
                    "rationale": "seed root route with blocked premise",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "retrieve")
        self.assertEqual(action["target_id"], "external-premise")
        self.assertEqual(action["debt_id"], "debt-external-premise-source")
        self.assertEqual(action["search_intent"], "blocking_debt_source_search")
        self.assertTrue(action["retrieval_required"])
        self.assertNotEqual(action["route_id"], "route-root")
        self.assertEqual(actor_role_for_action(action), "literature_researcher")

    def test_fresh_gap_on_premise_beats_stale_source_debt_after_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-premise-gap-after-search-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "root-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "The root follows from the premise if the premise is coherent.\n",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "stale-route-obstruction",
                            "artifact_type": "research_diagnostic",
                            "content": "Obstruction: an older stress diagnostic warned this route may fail.",
                            "metadata": {"target_id": "root", "route_id": "route-root"},
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "external-premise",
                            "kind": "lemma",
                            "statement": "A needed external construction theorem holds.",
                            "validation_status": "untested",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the external construction theorem.",
                            "evidence_artifact_ids": ["root-dossier"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": ["external-premise"],
                            "validation_status": "plausible",
                            "explanation": "The route is ready except for the external premise.",
                            "evidence_artifact_ids": ["root-dossier"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-external-premise-source",
                            "owner_type": "claim",
                            "owner_id": "external-premise",
                            "debt_type": "citation_verification",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Find the external construction theorem before rechecking the root route.",
                            "suggested_next_target": "external-premise",
                        },
                    ],
                    "rationale": "seed root route with blocked premise",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            gap_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "literature_researcher",
                    "target_id": "external-premise",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "source-obstruction",
                            "artifact_type": "source_analysis_note",
                            "content": "The searched theorem contradicts the stated premise, so the premise must be revised.",
                            "metadata": {"target_id": "external-premise", "status": "obstruction_found"},
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-external-premise-gap",
                            "owner_type": "claim",
                            "owner_id": "external-premise",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Revise or replace the external premise after source search found a contradiction.",
                            "suggested_next_target": "external-premise",
                            "evidence_artifact_ids": ["source-obstruction"],
                        },
                    ],
                    "rationale": "source search found a mathematical contradiction",
                },
            )
            self.assertTrue(gap_outcome.accepted, gap_outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="live")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "external-premise")
        self.assertEqual(action["debt_id"], "debt-external-premise-gap")
        self.assertEqual(action["search_intent"], "direct_solve_debt_repair")
        self.assertTrue(action["direct_solve_required"])
        self.assertNotIn("retrieval_required", action)
        self.assertEqual(actor_role_for_action(action), "researcher")

    def test_claim_debt_suggesting_inference_targets_conclusion_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-inference-suggested-debt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Check the repaired root proof.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "A candidate proof dossier is ready for strict checking.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-root-proof-gap",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Verify the repaired root inference.",
                            "suggested_next_target": "inf-root",
                        },
                    ],
                    "rationale": "seed root debt that points directly at an inference",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "route-root")
        self.assertEqual(action["debt_id"], "debt-root-proof-gap")
        self.assertTrue(action["proof_repair_verification_required"])
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")

    def test_inference_owned_route_gap_schedules_researcher_repair_unless_suggested_target_is_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-inference-owned-route-gap-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "bad-premise",
                            "kind": "lemma",
                            "statement": "A premise used by the root route is impossible as stated.",
                            "validation_status": "untested",
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the bad premise.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": ["bad-premise"],
                            "validation_status": "plausible",
                            "explanation": "The root would follow from the premise.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-route-repair",
                            "owner_type": "inference",
                            "owner_id": "inf-root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Replace the root route or its impossible premise.",
                            "suggested_next_target": "bad-premise",
                        },
                    ],
                    "rationale": "seed inference-owned route repair debt",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            action = next_action(store, research_mode="balanced", web_search="disabled")

        self.assertEqual(action["mode"], "reduce")
        self.assertEqual(action["target_id"], "bad-premise")
        self.assertEqual(action["route_id"], "route-root")
        self.assertEqual(action["debt_id"], "debt-route-repair")
        self.assertTrue(action["proof_repair_required"])
        self.assertNotIn("proof_repair_verification_required", action)
        self.assertEqual(actor_role_for_action(action), "researcher")

    def test_verifier_manifest_includes_full_proof_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-packet-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "packet-target",
                            "kind": "lemma",
                            "statement": "The local packet target follows from the constructed object.",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the proof dossier argument.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "proof-artifact-packet",
                            "artifact_type": "proof_blueprint",
                            "metadata": {"claim_id": "packet-target", "route_id": "route-packet-target"},
                            "content": "UNIQUE PROOF PACKET TEXT: the proof uses the exact local construction.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-packet-target",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof dossier gives the local construction.",
                            "evidence_artifact_ids": ["proof-artifact-packet"],
                        },
                    ],
                    "rationale": "seed verifier packet",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            manifest = build_context_manifest(
                store,
                target_id="packet-target",
                route_id="route-packet-target",
                action={
                    "mode": "prove",
                    "target_id": "packet-target",
                    "route_id": "route-packet-target",
                    "proof_repair_verification_required": True,
                },
                max_chars=60_000,
            )

        packet = manifest["verification_packet"]
        self.assertEqual(packet["target_claim"]["claim_id"], "packet-target")
        self.assertEqual(packet["selected_route"]["route_id"], "route-packet-target")
        self.assertEqual(packet["proof_artifacts"][0]["artifact_id"], "proof-artifact-packet")
        self.assertIn("UNIQUE PROOF PACKET TEXT", packet["proof_artifacts"][0]["content"])

    def test_verifier_manifest_includes_metadata_linked_route_repair_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-metadata-linked-packet-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "packet-target",
                            "kind": "lemma",
                            "statement": "The packet target follows from the repaired proof artifact.",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "old-route-packet",
                            "artifact_type": "proof_dossier",
                            "metadata": {"claim_id": "packet-target", "route_id": "route-packet-target"},
                            "content": "OLD PACKET TEXT: useful but missing a repair lemma.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the repaired proof dossier argument.",
                            "evidence_artifact_ids": ["old-route-packet"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-packet-target",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "premise_claim_ids": [],
                            "validation_status": "untested",
                            "explanation": "The old packet was routed before the repair packet was written.",
                            "evidence_artifact_ids": ["old-route-packet"],
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "repaired-route-packet",
                            "artifact_type": "proof_dossier",
                            "metadata": {
                                "route_id": "route-packet-target",
                                "supports_inference_id": "inf-packet-target",
                                "purpose": "complete_local_proof_packet_for_existing_route",
                            },
                            "content": "REPAIRED PACKET TEXT: this later proof packet must reach the verifier.",
                        },
                    ],
                    "rationale": "seed route plus metadata-linked repair packet",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            manifest = build_context_manifest(
                store,
                target_id="packet-target",
                route_id="route-packet-target",
                action={
                    "mode": "prove",
                    "target_id": "packet-target",
                    "route_id": "route-packet-target",
                    "proof_repair_verification_required": True,
                },
                max_chars=60_000,
            )

        artifact_ids = {row["artifact_id"] for row in manifest["artifacts"]}
        self.assertIn("old-route-packet", artifact_ids)
        packet_artifacts = {row["artifact_id"]: row for row in manifest["verification_packet"]["proof_artifacts"]}
        self.assertIn("old-route-packet", packet_artifacts)
        self.assertIn("repaired-route-packet", packet_artifacts)
        self.assertIn("REPAIRED PACKET TEXT", packet_artifacts["repaired-route-packet"]["content"])

    def test_verifier_packet_prioritizes_direct_inference_evidence_over_metadata_linked_route_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-direct-evidence-priority-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "packet-target",
                            "kind": "lemma",
                            "statement": "The packet target follows from the direct proof artifact.",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the direct proof dossier argument.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "large-old-route-packet",
                            "artifact_type": "proof_dossier",
                            "metadata": {"route_id": "route-packet-target"},
                            "content": "OLD ROUTE PACKET TEXT. " * 1200,
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "direct-inference-packet",
                            "artifact_type": "proof_dossier",
                            "metadata": {"claim_id": "packet-target"},
                            "content": "DIRECT INFERENCE PACKET TEXT: the verifier must receive this proof.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-packet-target",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The direct proof dossier gives the local construction.",
                            "evidence_artifact_ids": ["direct-inference-packet"],
                        },
                    ],
                    "rationale": "seed verifier packet with oversized route-linked history",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            manifest = build_context_manifest(
                store,
                target_id="packet-target",
                route_id="route-packet-target",
                action={
                    "mode": "prove",
                    "target_id": "packet-target",
                    "route_id": "route-packet-target",
                    "proof_repair_verification_required": True,
                },
                max_chars=60_000,
            )

        packet = manifest["verification_packet"]
        self.assertEqual(packet["proof_artifacts"][0]["artifact_id"], "direct-inference-packet")
        self.assertIn("DIRECT INFERENCE PACKET TEXT", packet["proof_artifacts"][0]["content"])

    def test_verifier_packet_prioritizes_route_evidence_over_large_premise_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-route-before-premise-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "large-premise-packet",
                            "artifact_type": "proof_dossier",
                            "metadata": {"claim_id": "premise-claim"},
                            "content": "OLD PREMISE PACKET TEXT. " * 1400,
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "premise-claim",
                            "kind": "lemma",
                            "statement": "The premise has a large older proof packet.",
                            "root_impact": 0.5,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                            "evidence_artifact_ids": ["large-premise-packet"],
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "packet-target",
                            "kind": "lemma",
                            "statement": "The packet target follows from the current route dossier.",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "current-route-packet",
                            "artifact_type": "proof_dossier",
                            "metadata": {"route_id": "route-packet-target"},
                            "content": "CURRENT ROUTE PACKET TEXT: this selected route proof must reach the verifier.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the current route dossier.",
                            "evidence_artifact_ids": ["current-route-packet"],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-packet-target",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "premise_claim_ids": ["premise-claim"],
                            "validation_status": "plausible",
                            "explanation": "The current route dossier proves the local construction from the premise.",
                            "evidence_artifact_ids": ["current-route-packet"],
                        },
                    ],
                    "rationale": "seed verifier packet with oversized premise history",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            manifest = build_context_manifest(
                store,
                target_id="packet-target",
                route_id="route-packet-target",
                action={
                    "mode": "prove",
                    "target_id": "packet-target",
                    "route_id": "route-packet-target",
                    "proof_repair_verification_required": True,
                    "advisor_requested_verification": True,
                    "verification_focus_inference_id": "inf-packet-target",
                    "verifier_evidence_artifact_ids": ["current-route-packet"],
                },
                max_chars=60_000,
            )

        packet = manifest["verification_packet"]
        self.assertTrue(manifest["workflow_action"]["advisor_requested_verification"])
        self.assertEqual(
            manifest["workflow_action"]["verification_focus_inference_id"],
            "inf-packet-target",
        )
        self.assertEqual(packet["proof_artifacts"][0]["artifact_id"], "current-route-packet")
        self.assertIn("CURRENT ROUTE PACKET TEXT", packet["proof_artifacts"][0]["content"])

    def test_compacted_verifier_manifest_preserves_proof_packet_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-verifier-packet-trim-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            noisy_claims = [
                {
                    "op": "add_claim",
                    "claim_id": f"noise-{i}",
                    "kind": "lemma",
                    "statement": f"Auxiliary context {i}. " + ("This should be trimmed before proof packet content. " * 20),
                    "root_impact": 0.1,
                    "reduction_depth": 2,
                    "parent_ids": ["root"],
                }
                for i in range(20)
            ]
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "packet-target",
                            "kind": "lemma",
                            "statement": "The compact packet target follows from the proof artifact.",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        *noisy_claims,
                        {
                            "op": "add_route",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the proof dossier argument.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "proof-artifact-packet",
                            "artifact_type": "proof_blueprint",
                            "metadata": {"claim_id": "packet-target", "route_id": "route-packet-target"},
                            "content": "UNIQUE COMPACT PACKET TEXT: this local proof content must survive compaction.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-packet-target",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof dossier gives the local construction.",
                            "evidence_artifact_ids": ["proof-artifact-packet"],
                        },
                    ],
                    "rationale": "seed compact verifier packet",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            manifest = build_context_manifest(
                store,
                target_id="packet-target",
                route_id="route-packet-target",
                action={
                    "mode": "prove",
                    "target_id": "packet-target",
                    "route_id": "route-packet-target",
                    "proof_repair_verification_required": True,
                },
                max_chars=18_000,
            )

        self.assertLessEqual(len(json.dumps(manifest)), 18_000)
        packet = manifest["verification_packet"]
        self.assertEqual(packet["proof_artifacts"][0]["artifact_id"], "proof-artifact-packet")
        self.assertIn("UNIQUE COMPACT PACKET TEXT", packet["proof_artifacts"][0]["content"])

    def test_strict_verifier_compaction_trims_advisory_context_before_proof_content(self) -> None:
        proof_content = "BEGIN AUTHORITATIVE PROOF\n" + ("Check this exact proof step. " * 300) + "\nEND AUTHORITATIVE PROOF"
        manifest = {
            "manifest_version": 1,
            "problem_id": "verifier-fit-order-test",
            "state_revision": 7,
            "target_id": "root",
            "role_context_policy": {
                "context_role": "strict_verifier",
                "authoritative_packet": "verification_packet",
                "summary": "verify only the bounded packet",
            },
            "verification_packet": {
                "packet_type": "local_proof_verification",
                "proof_artifacts": [
                    {
                        "artifact_id": "authoritative-proof",
                        "artifact_type": "proof_dossier",
                        "content": proof_content,
                        "content_loaded": True,
                    }
                ],
            },
            "instructions": ["A" * 6_000, "B" * 6_000],
            "research_strategy": {"advisory_noise": "C" * 6_000},
            "retrieval_cards": [],
            "theorem_library": [],
            "artifacts": [],
            "claims": [],
            "inferences": [],
            "debts": [],
            "graph_focus": {},
            "proof_spine": {},
            "workflow_action": {},
        }

        fitted = _fit_manifest(manifest, max_chars=18_000)

        artifact = fitted["verification_packet"]["proof_artifacts"][0]
        self.assertEqual(artifact["content"], proof_content)
        self.assertNotIn("content_trimmed", artifact)
        self.assertLessEqual(len(json.dumps(fitted, sort_keys=True)), 18_000)

    def test_compacted_integration_manifest_preserves_verified_route_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-integration-packet-trim-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem. " * 120)
            noisy_claims = [
                {
                    "op": "add_claim",
                    "claim_id": f"noise-{i}",
                    "kind": "lemma",
                    "statement": f"Auxiliary branch {i}. " + ("This should trim before the integration packet. " * 18),
                    "root_impact": 0.1,
                    "reduction_depth": 2,
                    "parent_ids": ["root"],
                }
                for i in range(20)
            ]
            seed = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "packet-target",
                            "kind": "lemma",
                            "statement": "The verified packet target follows from the proof artifact.",
                            "root_impact": 0.9,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        *noisy_claims,
                        {
                            "op": "add_route",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the proof dossier argument.",
                            "evidence_artifact_ids": ["proof-artifact-packet"],
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "proof-artifact-packet",
                            "artifact_type": "proof_dossier",
                            "metadata": {"claim_id": "packet-target", "route_id": "route-packet-target"},
                            "content": "VERIFIED INTEGRATION PACKET TEXT: this local proof evidence must remain visible.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-packet-target",
                            "route_id": "route-packet-target",
                            "conclusion_claim_id": "packet-target",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof dossier gives the local construction.",
                            "evidence_artifact_ids": ["proof-artifact-packet"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-unrelated-root-route",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "theorem_gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Complete a different downstream root argument.",
                            "suggested_next_target": "root",
                        },
                    ],
                    "rationale": "seed integration packet",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)
            verified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "strict_informal_verifier",
                    "target_id": "packet-target",
                    "route_id": "route-packet-target",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "verif-packet-target",
                            "artifact_type": "verification_report",
                            "metadata": {
                                "verdict": "verified",
                                "verification_report": {
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                            "content": "verified",
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-packet-target",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verif-packet-target"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "packet-target",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verif-packet-target"],
                        },
                    ],
                    "rationale": "verify integration packet",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            fresh_debt = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "strict_informal_verifier",
                    "target_id": "inf-packet-target",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-local-integration-route",
                            "owner_type": "inference",
                            "owner_id": "inf-packet-target",
                            "debt_type": "missing_reference",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "A later audit found an unchecked reference on this exact route.",
                            "suggested_next_target": "inf-packet-target",
                        }
                    ],
                    "rationale": "record a fresh route-local integration blocker",
                },
            )
            self.assertTrue(fresh_debt.accepted, fresh_debt.errors)

            action = {"mode": "integrate", "target_id": "packet-target", "route_id": "route-packet-target"}
            full_manifest = build_context_manifest(
                store,
                target_id="packet-target",
                route_id="route-packet-target",
                action=action,
                max_chars=60_000,
            )
            manifest = build_context_manifest(
                store,
                target_id="packet-target",
                route_id="route-packet-target",
                action=action,
                max_chars=12_000,
            )
            resume_manifest = build_resume_delta_manifest(
                store,
                target_id="packet-target",
                route_id="route-packet-target",
                action=action,
                since_revision=0,
            )

        self.assertLessEqual(len(json.dumps(manifest)), 12_000)
        self.assertEqual(manifest["role_context_policy"]["context_role"], "integration_verifier")
        self.assertIn("packet-target", {row["claim_id"] for row in manifest["claims"]})
        self.assertIn("inf-packet-target", {row["inference_id"] for row in manifest["inferences"]})
        artifact_ids = {row["artifact_id"] for row in manifest["artifacts"]}
        self.assertIn("proof-artifact-packet", artifact_ids)
        self.assertIn("verif-packet-target", artifact_ids)
        self.assertEqual(
            {row["debt_id"] for row in manifest["debts"]},
            {"debt-local-integration-route"},
        )
        self.assertEqual(
            {row["debt_id"] for row in full_manifest["debts"]},
            {"debt-local-integration-route"},
        )
        self.assertNotIn(
            "debt-unrelated-root-route",
            {
                row["debt_id"]
                for row in full_manifest["proof_spine"].get("current_bottlenecks", [])
            },
        )
        self.assertEqual(
            {row["debt_id"] for row in resume_manifest["active_debts"]},
            {"debt-local-integration-route"},
        )
        self.assertTrue(
            any("only debt ids listed in manifest.debts" in item for item in full_manifest["instructions"])
        )
        self.assertEqual(
            manifest["patch_contract"]["allowed_operation_names"],
            ["attach_artifact", "propose_status_transition", "add_debt"],
        )

    def test_role_specific_context_policy_and_model_routing_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-role-context-policy-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-root-context",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use a local proof dossier.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-context",
                            "route_id": "route-root-context",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof dossier proves the root.",
                        },
                    ],
                    "rationale": "seed verifier-ready route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            action = next_action(store, research_mode="balanced", web_search="disabled")
            manifest = build_context_manifest(store, target_id="root", route_id="route-root-context", action=action)
            session_plan = prepare_session(store, action, max_context_chars=12_000, model_profile="default")

        self.assertEqual(action["mode"], "prove")
        self.assertEqual(manifest["role_context_policy"]["context_role"], "strict_verifier")
        self.assertEqual(manifest["role_context_policy"]["authoritative_packet"], "verification_packet")
        self.assertEqual(session_plan["model_routing_hint"]["tier"], "strong_math")

    def test_prepare_session_materializes_evidence_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-evidence-capsule-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            skill_path = store.generation_root / ".agents" / "skills" / "search-math-results" / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text("# Search math results\n", encoding="utf-8")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "current-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "Current proof dossier.",
                            "metadata": {"target_id": "root", "route_id": "route-root-capsule"},
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root-capsule",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the current proof dossier.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root-capsule",
                            "route_id": "route-root-capsule",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The dossier proves the root.",
                            "evidence_artifact_ids": ["current-dossier"],
                        },
                    ],
                    "rationale": "seed capsule evidence",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            session_plan = prepare_session(
                store,
                {"mode": "prove", "target_id": "root", "route_id": "route-root-capsule"},
                max_context_chars=60_000,
                model_profile="default",
            )
            child_manifest = json.loads(Path(session_plan["context_path"]).read_text(encoding="utf-8"))

            workdir = Path(session_plan["codex_workdir"])
            self.assertTrue(Path(session_plan["context_path"]).is_relative_to(workdir))
            artifact_path = Path(child_manifest["artifacts"][0]["path"])
            self.assertTrue(artifact_path.is_relative_to(workdir))
            self.assertTrue(artifact_path.exists())
            self.assertIn(str(artifact_path), child_manifest["local_search_policy"]["allowed_local_evidence_paths"])
            staged_skill = workdir / ".agents" / "skills" / "search-math-results" / "SKILL.md"
            self.assertEqual(staged_skill.read_text(encoding="utf-8"), "# Search math results\n")
            self.assertNotIn(str(staged_skill), child_manifest["local_search_policy"]["allowed_local_evidence_paths"])

    def test_prepare_session_materializes_negative_result_ledger_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-negative-ledger-capsule-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "villain",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "small-case-obstruction",
                            "artifact_type": "cas_experiment_report",
                            "content": "The small-case sweep did not find a counterexample.",
                            "metadata": {
                                "target_id": "root",
                                "failure_fingerprint": "small-case-sweep-no-break",
                                "next_decisive_action": "Test a structurally different family.",
                            },
                        }
                    ],
                    "rationale": "record a negative result",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            original_path = Path(
                next(
                    row["path"]
                    for row in store.get_state()["artifacts"]
                    if row["artifact_id"] == "small-case-obstruction"
                )
            )

            session_plan = prepare_session(
                store,
                {
                    "mode": "triage_routes",
                    "target_id": "root",
                    "route_id": "",
                    "route_triage_required": True,
                },
                max_context_chars=30_000,
                model_profile="default",
            )
            child_manifest = json.loads(Path(session_plan["context_path"]).read_text(encoding="utf-8"))

            workdir = Path(session_plan["codex_workdir"])
            ledger_path = Path(child_manifest["negative_result_ledger"][0]["path"])
            self.assertNotEqual(ledger_path, original_path)
            self.assertTrue(ledger_path.is_relative_to(workdir))
            self.assertEqual(ledger_path.read_text(encoding="utf-8"), original_path.read_text(encoding="utf-8"))

    def test_fresh_child_debt_beats_repeated_parent_debt(self) -> None:
        state = {
            "claims": [
                claim("parent", 2),
                claim("child", 3),
            ],
            "debts": [
                debt(
                    "stale-parent",
                    owner_id="parent",
                    suggested_next_target="child",
                    repeated_count=4,
                    last_seen="2026-01-01T00:00:00+00:00",
                ),
                debt(
                    "fresh-child",
                    owner_id="child",
                    repeated_count=0,
                    last_seen="2026-01-02T00:00:00+00:00",
                ),
            ],
        }

        self.assertEqual(_first_blocking_debt(state)["debt_id"], "fresh-child")

    def test_deeper_child_target_beats_parent_when_repeat_counts_match(self) -> None:
        state = {
            "claims": [
                claim("parent", 2),
                claim("child", 4),
            ],
            "debts": [
                debt(
                    "parent",
                    owner_id="parent",
                    repeated_count=1,
                    last_seen="2026-01-01T00:00:00+00:00",
                ),
                debt(
                    "child",
                    owner_id="parent",
                    suggested_next_target="child",
                    repeated_count=1,
                    last_seen="2026-01-02T00:00:00+00:00",
                ),
            ],
        }

        self.assertEqual(_first_blocking_debt(state)["debt_id"], "child")

    def test_deeper_repair_target_beats_frontier_parent_debt_when_fresh(self) -> None:
        state = {
            "claims": [
                claim("frontier-parent", 1, parent_ids=["root"]),
                claim("intermediate", 2, parent_ids=["frontier-parent"]),
                claim("deep-repair", 3, parent_ids=["intermediate"]),
            ],
            "debts": [
                debt(
                    "frontier-parent-debt",
                    owner_id="frontier-parent",
                    suggested_next_target="intermediate",
                    repeated_count=1,
                ),
                debt(
                    "deep-repair-debt",
                    owner_type="route",
                    owner_id="route-frontier-parent",
                    suggested_next_target="deep-repair",
                    repeated_count=1,
                ),
            ],
        }

        self.assertEqual(_first_blocking_debt(state)["debt_id"], "deep-repair-debt")

    def test_fresh_repair_debt_beats_repeated_frontier_blocker(self) -> None:
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("frontier", 1, parent_ids=["root"]),
                claim("repair", 6, root_impact=0.8),
            ],
            "debts": [
                debt(
                    "repeated-frontier",
                    owner_id="frontier",
                    suggested_next_target="frontier",
                    repeated_count=3,
                    last_seen="2026-01-02T00:00:00+00:00",
                ),
                debt(
                    "fresh-repair",
                    owner_id="repair",
                    suggested_next_target="repair",
                    repeated_count=0,
                    last_seen="2026-01-01T00:00:00+00:00",
                ),
            ],
        }

        self.assertEqual(_first_blocking_debt(state)["debt_id"], "fresh-repair")

    def test_fresh_gap_debt_beats_stale_source_debt_on_same_target(self) -> None:
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("premise", 1, parent_ids=["root"]),
            ],
            "debts": [
                debt(
                    "stale-source",
                    owner_id="premise",
                    suggested_next_target="premise",
                    debt_type="citation_verification",
                    repeated_count=1,
                    last_seen="2026-01-01T00:00:00+00:00",
                ),
                debt(
                    "fresh-gap",
                    owner_id="premise",
                    suggested_next_target="premise",
                    debt_type="gap",
                    repeated_count=1,
                    last_seen="2026-01-02T00:00:00+00:00",
                ),
            ],
        }

        self.assertEqual(_first_blocking_debt(state)["debt_id"], "fresh-gap")

    def test_route_level_repair_debt_beats_claim_local_contradiction_debt(self) -> None:
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("premise", 1, parent_ids=["root"]),
            ],
            "routes": [
                route("route-root", conclusion_claim_id="root"),
            ],
            "inferences": [
                inference("inf-root", route_id="route-root", conclusion_claim_id="root"),
            ],
            "debts": [
                debt(
                    "claim-local-contradiction",
                    owner_id="premise",
                    suggested_next_target="premise",
                    debt_type="gap",
                    repeated_count=1,
                    last_seen="2026-01-01T00:00:00+00:00",
                ),
                debt(
                    "route-repair",
                    owner_type="inference",
                    owner_id="inf-root",
                    suggested_next_target="premise",
                    debt_type="gap",
                    repeated_count=1,
                    last_seen="2026-01-02T00:00:00+00:00",
                ),
            ],
        }

        self.assertEqual(_first_blocking_debt(state)["debt_id"], "route-repair")

    def test_unverified_claim_skips_claim_with_only_paused_routes_when_alternative_exists(self) -> None:
        state = {
            "problem_state": {"max_reduction_depth": 4},
            "claims": [
                claim("root", 0, root_impact=1.0, validation_status="informally_verified"),
                claim("stalled-comb", 1, root_impact=0.96, parent_ids=["root"]),
                claim("mt-repair", 3, root_impact=0.9, parent_ids=["root"]),
            ],
            "routes": [
                route("route-stalled-comb", conclusion_claim_id="stalled-comb"),
            ],
            "inferences": [
                inference("inf-stalled-comb", route_id="route-stalled-comb", conclusion_claim_id="stalled-comb"),
            ],
            "debts": [
                debt("debt-stalled-comb", owner_id="stalled-comb", repeated_count=3),
            ],
        }

        self.assertEqual(_next_unverified_claim(state)["claim_id"], "mt-repair")

    def test_cooldown_skips_route_with_fresh_blocking_debt(self) -> None:
        state = {
            "problem_state": {
                "remaining_token_budget": 1_000_000,
                "reserved_verification_budget": 100_000,
                "max_reduction_depth": 4,
            },
            "claims": [
                claim("root", 0, root_impact=1.0, validation_status="informally_verified"),
                claim("recently-gapped-route", 1, root_impact=0.96, parent_ids=["root"]),
                claim("repair-target", 3, root_impact=0.9, parent_ids=["root"]),
                claim("deferred-target", 3, root_impact=0.9, parent_ids=["root"]),
            ],
            "routes": [
                route("route-recently-gapped", conclusion_claim_id="recently-gapped-route"),
            ],
            "inferences": [
                inference("inf-recently-gapped", route_id="route-recently-gapped", conclusion_claim_id="recently-gapped-route"),
            ],
            "debts": [
                debt("debt-fresh-route-gap", owner_type="route", owner_id="route-recently-gapped", repeated_count=1),
            ],
        }

        action = _cooldown_proof_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="balanced",
            deferred_debt=debt("deferred-debt", owner_id="deferred-target"),
            deferred_target_id="deferred-target",
        )

        assert action is not None
        self.assertEqual(action["target_id"], "repair-target")
        self.assertEqual(action["mode"], "prove")
        self.assertTrue(action["direct_solve_required"])

    def test_frontier_pressure_counts_root_local_unverified_claims(self) -> None:
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0),
                *[
                    claim(f"local-{idx:02d}", 1, parent_ids=["root"])
                    for idx in range(18)
                ],
                claim("verified-local", 1, parent_ids=["root"], validation_status="informally_verified"),
                claim("far-active", 9, root_impact=0.9),
            ],
            "routes": [],
            "inferences": [],
            "debts": [],
        }

        pressure = active_frontier_pressure(state)

        self.assertTrue(pressure["over_claim_cap"])
        self.assertEqual(pressure["active_root_local_unverified_claim_count"], 18)
        self.assertEqual(pressure["active_unverified_claim_count"], 19)
        self.assertNotIn("root", pressure["sample_claim_ids"])
        self.assertNotIn("verified-local", pressure["sample_claim_ids"])

    def test_frontier_pressure_prefers_existing_route_verification(self) -> None:
        state = {
            "problem_state": {
                "remaining_token_budget": 1_000_000,
                "reserved_verification_budget": 100_000,
                "max_reduction_depth": 4,
            },
            "claims": [
                claim("root", 0, root_impact=1.0, validation_status="informally_verified"),
                claim("routed-trunk", 1, root_impact=0.98, parent_ids=["root"]),
                claim("deferred-target", 1, root_impact=0.97, parent_ids=["root"]),
                *[
                    claim(f"local-{idx:02d}", 1, parent_ids=["root"])
                    for idx in range(17)
                ],
            ],
            "routes": [
                route("route-routed-trunk", conclusion_claim_id="routed-trunk"),
            ],
            "inferences": [
                inference("inf-routed-trunk", route_id="route-routed-trunk", conclusion_claim_id="routed-trunk"),
            ],
            "debts": [],
        }
        pressure = active_frontier_pressure(state)

        action = _frontier_pressure_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="balanced",
            frontier_pressure=pressure,
            deferred_debt=debt("deferred-debt", owner_id="deferred-target"),
            deferred_target_id="deferred-target",
        )

        assert action is not None
        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "routed-trunk")
        self.assertEqual(action["route_id"], "route-routed-trunk")
        self.assertEqual(action["deferred_debt_id"], "deferred-debt")
        self.assertTrue(action["frontier_pressure"]["over_claim_cap"])

    def test_unknown_target_does_not_get_artificial_depth_priority(self) -> None:
        state = {
            "claims": [
                claim("parent", 2),
                claim("child", 4),
            ],
            "debts": [
                debt(
                    "unknown-target",
                    owner_id="parent",
                    suggested_next_target="missing-claim",
                    repeated_count=0,
                    last_seen="2026-01-01T00:00:00+00:00",
                ),
                debt(
                    "known-child",
                    owner_id="parent",
                    suggested_next_target="child",
                    repeated_count=0,
                    last_seen="2026-01-02T00:00:00+00:00",
                ),
            ],
        }

        self.assertEqual(_first_blocking_debt(state)["debt_id"], "known-child")

    def test_route_owned_debt_targets_route_conclusion_claim(self) -> None:
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0),
            ],
            "routes": [
                route("route-root", conclusion_claim_id="root"),
            ],
            "inferences": [],
            "debts": [],
        }
        row = debt(
            "route-gap",
            owner_type="route",
            owner_id="route-root",
            suggested_next_target="route-root",
        )

        self.assertEqual(_claim_target_for_debt(state, row), "root")

    def test_bookkeeping_debt_is_deprioritized_when_math_debt_exists(self) -> None:
        state = {
            "problem_state": {"max_reduction_depth": 3},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("math-trunk", 2, statement="Prove the geometric vanishing lemma"),
                claim("json-validator-target", 8, statement="Construct the JSON schema validator envelope"),
            ],
            "debts": [
                debt(
                    "meta-debt",
                    owner_id="json-validator-target",
                    obligation="Specify the candidate inventory JSON schema validator",
                    repeated_count=0,
                    last_seen="2026-01-02T00:00:00+00:00",
                ),
                debt(
                    "math-debt",
                    owner_id="math-trunk",
                    obligation="Close the vanishing argument",
                    repeated_count=1,
                    last_seen="2026-01-01T00:00:00+00:00",
                ),
            ],
        }

        self.assertEqual(_first_blocking_debt(state)["debt_id"], "math-debt")

    def test_only_overdeep_bookkeeping_debt_is_not_scheduled(self) -> None:
        state = {
            "problem_state": {"max_reduction_depth": 3},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("json-validator-target", 8, statement="Construct the JSON schema validator envelope"),
            ],
            "debts": [
                debt(
                    "meta-debt",
                    owner_id="json-validator-target",
                    obligation="Specify the candidate inventory JSON schema validator",
                ),
            ],
        }

        self.assertIsNone(_first_blocking_debt(state))

    def test_unverified_claim_prefers_math_trunk_over_overdeep_bookkeeping(self) -> None:
        state = {
            "problem_state": {"max_reduction_depth": 3},
            "claims": [
                claim("root", 0, root_impact=1.0, validation_status="informally_verified"),
                claim(
                    "json-validator-target",
                    8,
                    statement="Build the candidate inventory JSON schema validator",
                    root_impact=0.99,
                ),
                claim("math-trunk", 2, statement="Prove the main vanishing lemma", root_impact=0.4),
            ],
        }

        self.assertEqual(_next_unverified_claim(state)["claim_id"], "math-trunk")

    def test_root_local_claim_beats_far_high_impact_claim(self) -> None:
        state = {
            "problem_state": {"max_reduction_depth": 6},
            "claims": [
                claim("root", 0, root_impact=1.0, validation_status="informally_verified"),
                claim("near-trunk", 1, statement="Close the root-local vanishing lemma", root_impact=0.4, parent_ids=["root"]),
                claim("far-topic", 8, statement="Develop a remote auxiliary theory", root_impact=0.99),
            ],
            "routes": [],
            "inferences": [],
            "debts": [],
        }

        self.assertEqual(_next_unverified_claim(state)["claim_id"], "near-trunk")

    def test_decomposition_cooldown_requires_proof_work_after_reduce(self) -> None:
        self.assertTrue(
            decomposition_cooldown_active(
                {
                    "recent_runs": [
                        {"mode": "reduce", "target_id": "claim-a", "created_at": "2026-01-02T00:00:00+00:00"},
                        {"mode": "retrieve", "target_id": "root", "created_at": "2026-01-01T00:00:00+00:00"},
                    ]
                }
            )
        )
        self.assertFalse(
            decomposition_cooldown_active(
                {
                    "recent_runs": [
                        {"mode": "prove", "target_id": "claim-a", "created_at": "2026-01-03T00:00:00+00:00"},
                        {"mode": "reduce", "target_id": "claim-a", "created_at": "2026-01-02T00:00:00+00:00"},
                    ]
                }
            )
        )

    def test_obvious_claim_restatement_is_duplicate(self) -> None:
        existing = [{"claim_id": "claim-a", "statement": "Prove that every smooth curve has property P.", "fingerprint": ""}]

        self.assertEqual(
            obvious_duplicate_claim_id(existing, statement="Show every smooth curve has property P."),
            "claim-a",
        )

    def test_near_restatement_of_integrated_claim_is_duplicate(self) -> None:
        existing = [
            {
                "claim_id": "closed-psl2-branch",
                "statement": (
                    "Let ell>=5 be an odd prime, S=PSL_2(ell), and let Gamma be S when ell=3 mod 4 "
                    "and PGL_2(ell) when ell=1 mod 4. Let |Omega|>1 and let K satisfy "
                    "S^Omega <= K <= Gamma wr P with P transitive on Omega. Then no pair x,y in K "
                    "of orders 2 and ell invariably generates K."
                ),
                "fingerprint": "",
                "validation_status": "informally_verified",
                "lifecycle_status": "integrated",
            }
        ]

        self.assertEqual(
            obvious_duplicate_claim_id(
                existing,
                statement=(
                    "Let ell>=5 be an odd prime, S=PSL_2(ell), and Gamma=S if ell=3 mod 4 "
                    "while Gamma=PGL_2(ell) if ell=1 mod 4. Let Omega have size >1, and let K be "
                    "a finite group with S^Omega <= K <= Gamma wr Sym(Omega) whose top image P is "
                    "transitive on Omega. Then no pair x,y in K with |x|=2 and |y|=ell invariably generates K."
                ),
            ),
            "closed-psl2-branch",
        )

    def test_integrated_claim_closing_qualification_is_duplicate(self) -> None:
        existing = [
            {
                "claim_id": "proper-two-anchor",
                "statement": (
                    "Let G be a finite group, let A be normal in G, let M<G, let D be normal in M, and put K=AD. "
                    "Let C<=M and let X be normal in G, with C<=X, G=MX, and X/C a nonzero irreducible M-module. "
                    "Assume K is M-normal and N_G(K)=M. If x is in X and m is in M, writing y=x^m, and if "
                    "xC!=yC and [d,y][d,x]^(-1) lies in A for every d in D, then K^x=K^y and N_G(K)=G, "
                    "contradicting N_G(K)=M. Thus no such x,m occur."
                ),
                "fingerprint": "",
                "validation_status": "informally_verified",
                "lifecycle_status": "integrated",
            }
        ]

        self.assertEqual(
            obvious_duplicate_claim_id(
                existing,
                statement=(
                    "Let G be a finite group, let A be normal in G, let M<G, let D be normal in M, and put K=AD. "
                    "Let C<=M and X be normal in G, with C<=X, G=MX, and X/C a nonzero irreducible M-module. "
                    "Assume K is M-normal and N_G(K)=M. If x is in X and m is in M, writing y=x^m, and if "
                    "xC!=yC and [d,y][d,x]^(-1) lies in A for every d in D, then K^x=K^y and N_G(K)=G!=M. "
                    "Thus no such x,m can occur in the proper restricted-normalizer branch."
                ),
            ),
            "proper-two-anchor",
        )

    def test_distinct_group_family_template_is_not_duplicate(self) -> None:
        existing = [
            {
                "claim_id": "orthogonal-common-overgroup",
                "statement": (
                    "Fix distinct primes p and q, put R=max(p,q), E=4 lcm(1,2,...,2R), and n0=4RE. "
                    "Let S=P Omega(V,Q) be a finite simple orthogonal group of natural dimension n>=n0. "
                    "For every t>=1 and every X with S^t<=X<=Aut(S) wr Sym(t), elements of respective "
                    "orders p and q have independent S^t-conjugates in one common proper subgroup of X."
                ),
                "fingerprint": "",
                "validation_status": "informally_verified",
                "lifecycle_status": "integrated",
            }
        ]

        self.assertEqual(
            obvious_duplicate_claim_id(
                existing,
                statement=(
                    "Fix distinct primes p,q and put L=lcm(p,q). For every n>=max(7,L+1), every t>=1, "
                    "every X with A_n^t<=X<=Aut(A_n) wr Sym(t), and every elements x,y in X of respective "
                    "orders p,q, there are independent A_n^t-conjugates of x and y contained in one common "
                    "proper subgroup of X."
                ),
            ),
            "",
        )

    def test_near_restatement_of_active_claim_is_not_duplicate(self) -> None:
        existing = [
            {
                "claim_id": "active-branch",
                "statement": (
                    "Let ell>=5 be an odd prime, S=PSL_2(ell), and let Gamma be S when ell=3 mod 4 "
                    "and PGL_2(ell) when ell=1 mod 4. Let |Omega|>1 and let K satisfy "
                    "S^Omega <= K <= Gamma wr P with P transitive on Omega."
                ),
                "fingerprint": "",
                "validation_status": "plausible",
                "lifecycle_status": "active",
            }
        ]

        self.assertEqual(
            obvious_duplicate_claim_id(
                existing,
                statement=(
                    "Let ell>=5 be an odd prime, S=PSL_2(ell), and Gamma=S if ell=3 mod 4 "
                    "while Gamma=PGL_2(ell) if ell=1 mod 4. Let Omega have size >1, and let K be "
                    "a finite group with S^Omega <= K <= Gamma wr Sym(Omega) whose top image P is transitive."
                ),
            ),
            "",
        )

    def test_substantive_extension_of_integrated_claim_is_not_duplicate(self) -> None:
        existing = [
            {
                "claim_id": "closed-inner-c1",
                "statement": (
                    "Fix distinct primes p and q and put L=lcm(1,2,...,2max(p,q)). For all sufficiently large natural "
                    "dimensions n, if S=PSp(V) or PSU(V) and S<=Gamma<=Inndiag(S), then the C1 stabilizer in Gamma "
                    "of a nondegenerate L-subspace is proper, has intersection with S proper, maps onto Gamma/S, and "
                    "meets every S-conjugacy class of elements of orders p and q."
                ),
                "fingerprint": "",
                "validation_status": "informally_verified",
                "lifecycle_status": "integrated",
            }
        ]

        self.assertEqual(
            obvious_duplicate_claim_id(
                existing,
                statement=(
                    "Fix distinct primes p,q and put L=lcm(1,2,...,2max(p,q)). For all sufficiently large natural "
                    "dimensions n, let V be a finite symplectic or unitary space, let S=PSp(V) or PSU(V), and let "
                    "S<=Gamma<=P Gamma Sp(V) or P Gamma U(V) have outer image contained in the diagonal-field subgroup. "
                    "Then for a fixed nondegenerate L-subspace W<=V, R=N_Gamma(W) maps onto Gamma/S and every element "
                    "of Gamma of order p or q is Gamma-conjugate into R."
                ),
            ),
            "",
        )

    def test_bottleneck_lock_skips_debt_covered_by_integrated_claim(self) -> None:
        covered = debt(
            "covered-psl2-debt",
            owner_id="root",
            debt_type="proof_obligation",
            obligation=(
                "For the remaining p=2, q=ell PSL2 residue with S=PSL_2(ell) and Gamma as in the viable parity "
                "cases, prove the mixed-label transitive crown theorem: for every K with S^Omega <= K <= Gamma wr P "
                "and every order-2/order-ell candidate pair, construct a proper component subgroup system satisfying "
                "the transport and fixed-label top gate."
            ),
        )
        open_debt = debt(
            "open-r-rank-debt",
            owner_id="root",
            debt_type="proof_obligation",
            obligation="Resolve the remaining off-prime r-rank bridge for prescribed-prime invariable hosts.",
        )
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0, validation_status="informally_verified"),
                claim(
                    "closed-psl2-branch",
                    1,
                    statement=(
                        "Fix an odd prime ell>=5, let S=PSL_2(ell), and let Gamma be the viable envelope Gamma=S "
                        "for ell=3 mod 4 and Gamma=PGL_2(ell) for ell=1 mod 4. Let |Omega|>1, let P be transitive "
                        "on Omega, and let K satisfy S^Omega <= K <= Gamma wr P. If x,y in K have orders 2 and ell, "
                        "then x and y do not invariably generate K. More precisely, unless their top images already "
                        "fail the quotient invariable-generation gate, independent S^Omega-conjugates of x and y lie "
                        "in K cap (R^Omega semidirect P) for a single proper subgroup R<Gamma with R cap S<S; thus "
                        "the rev313 component-system trap holds for the conjugated labels with constant R_omega=R."
                    ),
                    validation_status="informally_verified",
                    lifecycle_status="integrated",
                    parent_ids=["root"],
                ),
            ],
            "routes": [],
            "inferences": [],
            "debts": [covered, open_debt],
            "research_artifacts": [],
        }

        self.assertEqual(
            [row["debt_id"] for row in _bottleneck_lock_debt_candidates(state)],
            ["open-r-rank-debt"],
        )
        self.assertEqual(_first_blocking_debt(state)["debt_id"], "open-r-rank-debt")

    def test_route_scoreboard_pauses_repeated_blocker(self) -> None:
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("branch", 1, root_impact=0.8, parent_ids=["root"]),
            ],
            "routes": [route("route-branch", conclusion_claim_id="branch")],
            "inferences": [inference("inf-branch", route_id="route-branch", conclusion_claim_id="branch")],
            "debts": [debt("debt-branch", owner_id="branch", repeated_count=3)],
        }

        row = route_scoreboard(state)[0]
        self.assertEqual(row["scoreboard_status"], "stalled")
        self.assertIn("blocking debt repeated", row["kill_reasons"][0])

    def test_route_scoreboard_keeps_repaired_route_schedulable_for_verifier(self) -> None:
        state = {
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [route("route-root", conclusion_claim_id="root")],
            "inferences": [inference("inf-root", route_id="route-root", conclusion_claim_id="root")],
            "debts": [
                debt(
                    "debt-old-root-branch",
                    owner_id="root",
                    repeated_count=5,
                    last_seen="2026-01-01T00:00:00+00:00",
                )
            ],
            "research_artifacts": [
                {
                    "artifact_id": "root-repair",
                    "artifact_type": "proof_dossier",
                    "producer_role": "researcher",
                    "state_revision": 10,
                    "created_at": "2026-01-02T00:00:00+00:00",
                    "metadata_json": json.dumps(
                        {
                            "artifact_roi": "verifier_ready_route",
                            "target_id": "root",
                            "route_id": "route-root",
                            "next_decisive_step": "Send the repaired root route to strict verification.",
                        }
                    ),
                }
            ],
        }

        row = route_scoreboard(state)[0]

        self.assertEqual(row["scoreboard_status"], "promising")
        self.assertEqual(row["blocking_debt_count"], 0)
        self.assertEqual(_active_route_for_claim(state, "root"), "route-root")

    def test_route_scoreboard_stalls_when_blocker_is_newer_than_repair(self) -> None:
        state = {
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [route("route-root", conclusion_claim_id="root")],
            "inferences": [inference("inf-root", route_id="route-root", conclusion_claim_id="root")],
            "debts": [
                debt(
                    "debt-new-root-gap",
                    owner_id="root",
                    repeated_count=3,
                    last_seen="2026-01-03T00:00:00+00:00",
                )
            ],
            "research_artifacts": [
                {
                    "artifact_id": "stale-root-repair",
                    "artifact_type": "proof_dossier",
                    "producer_role": "researcher",
                    "state_revision": 10,
                    "created_at": "2026-01-02T00:00:00+00:00",
                    "metadata_json": json.dumps(
                        {
                            "artifact_roi": "verifier_ready_route",
                            "target_id": "root",
                            "route_id": "route-root",
                            "next_decisive_step": "Send the repaired root route to strict verification.",
                        }
                    ),
                }
            ],
        }

        row = route_scoreboard(state)[0]

        self.assertEqual(row["scoreboard_status"], "stalled")
        self.assertEqual(row["blocking_debt_count"], 1)

    def test_paused_route_is_not_selected_as_ordinary_construction(self) -> None:
        state = {
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("branch", 1, root_impact=0.8, parent_ids=["root"]),
            ],
            "routes": [route("route-branch", conclusion_claim_id="branch")],
            "inferences": [],
            "debts": [debt("debt-branch", owner_id="branch", repeated_count=3)],
        }

        self.assertEqual(route_scoreboard(state)[0]["scoreboard_status"], "stalled")
        self.assertEqual(_active_route_for_claim(state, "branch"), "")
        self.assertIsNone(_route_without_inference(state))

    def test_repeated_evidence_pressure_schedules_proof_architecture_pass(self) -> None:
        state = {
            "problem_state": {},
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [route("route-root", conclusion_claim_id="root")],
            "inferences": [],
            "debts": [
                debt("debt-root-a", owner_id="root", repeated_count=2),
                debt("debt-root-b", owner_id="route-root", owner_type="route"),
            ],
            "research_artifacts": [
                {
                    "artifact_id": "diag-a",
                    "artifact_type": "research_diagnostic",
                    "producer_role": "researcher",
                    "state_revision": 3,
                    "created_at": "2026-01-03T00:00:00+00:00",
                    "metadata_json": "{}",
                },
                {
                    "artifact_id": "obs-a",
                    "artifact_type": "route_obstruction",
                    "producer_role": "villain",
                    "state_revision": 2,
                    "created_at": "2026-01-02T00:00:00+00:00",
                    "metadata_json": "{}",
                },
                {
                    "artifact_id": "advisor-a",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 1,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "metadata_json": "{}",
                },
            ],
            "recent_runs": [],
        }

        action = _proof_architecture_pressure_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="balanced",
        )
        assert action is not None

        self.assertEqual(action["search_intent"], "proof_architecture_pressure")
        self.assertTrue(action["proof_architecture_required"])
        self.assertTrue(action["route_contract_required"])
        self.assertTrue(action["obligation_reduction_required"])
        self.assertTrue(action["speculative_proof_required"])
        self.assertTrue(action["repair_loop_required"])
        self.assertEqual(
            action["proof_architecture_signal"]["signal_artifact_ids"],
            ["diag-a", "obs-a", "advisor-a"],
        )

        hard_action = _proof_architecture_pressure_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="hard_problem",
        )
        assert hard_action is not None

        self.assertEqual(hard_action["search_intent"], "proof_architecture_pressure")
        self.assertEqual(hard_action["research_attack_stage"], "creative")
        self.assertTrue(hard_action["creative_proof_attack_required"])
        self.assertTrue(hard_action["wild_mathematician_mode"])
        self.assertTrue(hard_action["obstruction_inversion_required"])
        self.assertTrue(hard_action["paperwork_throttle_required"])

    def test_repeated_bottleneck_debt_schedules_lock_before_more_synthesis(self) -> None:
        state = {
            "problem_state": {},
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [],
            "inferences": [],
            "debts": [
                debt(
                    "debt-root-lock",
                    owner_id="root",
                    repeated_count=3,
                    debt_type="blocking_bridge",
                    obligation="Prove or refute the exact bridge lemma that unlocks the root route.",
                )
            ],
            "research_artifacts": [
                {
                    "artifact_id": "diag-lock",
                    "artifact_type": "research_diagnostic",
                    "producer_role": "researcher",
                    "state_revision": 4,
                    "created_at": "2026-01-04T00:00:00+00:00",
                    "content_summary": "Remaining bottleneck: exact bridge lemma is not verifier-ready.",
                    "metadata_json": "{}",
                }
            ],
            "recent_runs": [],
        }

        action = _bottleneck_lock_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="hard_problem",
        )
        assert action is not None

        self.assertEqual(action["search_intent"], "bottleneck_lock_theorem_attack")
        self.assertTrue(action["bottleneck_lock_required"])
        self.assertTrue(action["decisive_theorem_test_required"])
        self.assertTrue(action["sublemma_extraction_required"])
        self.assertTrue(action["side_branch_roi_cap_active"])
        self.assertFalse(action["research_diagnostic_required"])
        self.assertIn("broad research_diagnostic", action["forbidden_outputs"])

        summary = bottleneck_frontier_summary(state)
        self.assertTrue(summary["locked"])
        self.assertEqual(summary["current_bottleneck"]["debt_id"], "debt-root-lock")
        self.assertEqual(summary["diagnostic_cooldown"]["recent_diagnostic_count"], 1)

    def test_bottleneck_lock_prefers_fresh_narrowed_child_debt_over_stale_ancestor(self) -> None:
        state = {
            "problem_state": {},
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [],
            "inferences": [],
            "debts": [
                debt(
                    "debt-root-broad-ancestor",
                    owner_id="root",
                    repeated_count=6,
                    last_seen="2026-01-01T00:00:00+00:00",
                    debt_type="central_obstruction",
                    obligation="Resolve the broad ancestor obstruction for the root theorem.",
                ),
                {
                    **debt(
                        "debt-root-fresh-child-rev10",
                        owner_id="root",
                        repeated_count=1,
                        last_seen="2026-01-04T00:00:00+00:00",
                        debt_type="proof_obligation",
                        obligation="Prove or refute the exact narrowed child theorem extracted from the bottleneck.",
                    ),
                    "source_artifact_ids_json": json.dumps(["art-root-fresh-child"]),
                },
            ],
            "research_artifacts": [
                {
                    "artifact_id": "diag-lock",
                    "artifact_type": "research_diagnostic",
                    "producer_role": "researcher",
                    "state_revision": 4,
                    "created_at": "2026-01-04T00:00:00+00:00",
                    "content_summary": "Remaining bottleneck: broad obstruction is not verifier-ready.",
                    "metadata_json": "{}",
                },
                {
                    "artifact_id": "art-root-fresh-child",
                    "artifact_type": "proof_dossier",
                    "producer_role": "researcher",
                    "state_revision": 10,
                    "created_at": "2026-01-04T00:01:00+00:00",
                    "content_summary": "A bottleneck pass narrows the ancestor obstruction to one child theorem.",
                    "metadata_json": json.dumps(
                        {
                            "artifact_roi": "bottleneck_narrowed",
                            "central_debt_id": "debt-root-broad-ancestor",
                            "next_decisive_action": "Prove the narrowed child theorem.",
                            "what_changed": "The broad obstruction now has one exact child obligation.",
                        }
                    ),
                },
            ],
            "recent_runs": [],
        }

        action = _bottleneck_lock_action(
            state,
            problem={},
            requested_tokens=None,
            research_mode="hard_problem",
        )
        assert action is not None
        summary = bottleneck_frontier_summary(state)

        self.assertEqual(action["debt_id"], "debt-root-fresh-child-rev10")
        self.assertTrue(action["proof_spine_mode_required"])
        self.assertTrue(action["duplicate_math_guard_required"])
        self.assertEqual(summary["current_bottleneck"]["debt_id"], "debt-root-fresh-child-rev10")
        self.assertGreater(summary["current_bottleneck"]["fresh_narrowing_score"], 0)

    def test_proof_spine_summary_is_compact_trunk_view(self) -> None:
        state = {
            "problem_state": {},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim(
                    "trunk-lemma",
                    1,
                    root_impact=0.9,
                    validation_status="informally_verified",
                    lifecycle_status="integrated",
                    statement="A verified trunk lemma close to the root.",
                    parent_ids=["root"],
                ),
            ],
            "routes": [],
            "inferences": [],
            "debts": [
                debt(
                    "debt-root-spine-gap",
                    owner_id="root",
                    debt_type="proof_obligation",
                    obligation="One exact theorem-level proof gap remains.",
                )
            ],
            "research_artifacts": [
                {
                    "artifact_id": "spine-art",
                    "artifact_type": "proof_dossier",
                    "producer_role": "researcher",
                    "state_revision": 2,
                    "created_at": "2026-01-02T00:00:00+00:00",
                    "content_summary": "Proof dossier with the next decisive action.",
                    "metadata_json": json.dumps(
                        {"artifact_roi": "bottleneck_narrowed", "next_decisive_action": "Prove the last gap."}
                    ),
                },
            ],
            "recent_runs": [],
        }

        summary = proof_spine_summary(state)

        self.assertEqual(summary["verified_trunk_claims"][0]["claim_id"], "trunk-lemma")
        self.assertEqual(summary["recent_spine_artifacts"][0]["artifact_id"], "spine-art")
        self.assertEqual(summary["current_bottleneck"]["debt_id"], "debt-root-spine-gap")

    def test_proof_spine_summary_sends_verified_root_to_integration(self) -> None:
        state = {
            "problem_state": {},
            "claims": [
                claim(
                    "root",
                    0,
                    root_impact=1.0,
                    validation_status="informally_verified",
                    lifecycle_status="active",
                ),
            ],
            "routes": [],
            "inferences": [],
            "debts": [
                debt(
                    "debt-stale-side-branch",
                    owner_id="root",
                    debt_type="proof_obligation",
                    obligation="An older alternative route has a local gap.",
                )
            ],
            "research_artifacts": [],
            "recent_runs": [],
        }

        summary = proof_spine_summary(state)

        self.assertTrue(summary["root_integration_pending"])
        self.assertEqual(summary["current_bottleneck"], {})
        self.assertIn("integration verifier", summary["next_workflow_rule"])
        self.assertNotIn("Convert proof-like artifacts", summary["next_workflow_rule"])

    def test_executive_advisor_bottleneck_suppresses_older_local_proof_candidate(self) -> None:
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("claim-field-local", 1, root_impact=0.45, parent_ids=["root"]),
            ],
            "routes": [
                route("route-h2-root", conclusion_claim_id="root"),
                route("route-field-local", conclusion_claim_id="claim-field-local"),
            ],
            "inferences": [],
            "debts": [
                debt(
                    "debt-h2-capacity",
                    owner_type="route",
                    owner_id="route-h2-root",
                    suggested_next_target="root",
                    obligation="Decide the H2 capacity fork.",
                )
            ],
            "research_artifacts": [
                {
                    "artifact_id": "old-field-advisor-proof",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 5,
                    "created_at": "2026-01-04T00:00:00+00:00",
                    "content_summary": "Proof-like local field repair.",
                    "metadata_json": json.dumps({"proof_candidate": True, "target_id": "claim-field-local"}),
                },
                {
                    "artifact_id": "advisor-root-lock",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 10,
                    "created_at": "2026-01-04T00:02:00+00:00",
                    "content_summary": "The H2 fork is the decisive root bottleneck.",
                    "metadata_json": json.dumps(
                        {
                            "advisor_followup_required": True,
                            "triage_status": "decisive_root_bottleneck",
                            "bottleneck_obligation": "Decide H2 capacity.",
                            "next_decisive_task": "Prove or refute the H2 capacity theorem.",
                            "next_role": "researcher",
                            "next_target_id": "root",
                            "obstruction_debts": ["debt-h2-capacity"],
                            "paused_or_abandoned_route_ids": ["route-field-local"],
                            "route_decisions": [
                                {"route_id": "route-field-local", "decision": "blocked"}
                            ],
                            "recommended_next_action": "Send researcher to root H2 fork.",
                        }
                    ),
                },
            ],
            "recent_runs": [],
            "retrieval_cards": [],
            "theorem_library_entries": [],
        }

        self.assertIsNone(_unrouted_proof_candidate(state))
        action = _executive_advisor_bottleneck_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="hard_problem",
        )

        assert action is not None
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "route-h2-root")
        self.assertEqual(action["debt_id"], "debt-h2-capacity")
        self.assertEqual(action["search_intent"], "executive_advisor_bottleneck_lock")
        self.assertTrue(action["executive_advisor_lock_required"])
        self.assertTrue(action["hard_theorem_attack_required"])
        self.assertEqual(action["budget"]["policy"], "hard_theorem_workbench")

    def test_superseded_claim_is_not_reassembled_from_old_dossier(self) -> None:
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim(
                    "stale-wording",
                    1,
                    lifecycle_status="superseded",
                    validation_status="challenged",
                    parent_ids=["root"],
                ),
                claim(
                    "refuted-wording",
                    1,
                    lifecycle_status="active",
                    validation_status="refuted",
                    parent_ids=["root"],
                ),
            ],
            "routes": [route("route-stale-wording", conclusion_claim_id="stale-wording", status="superseded")],
            "inferences": [
                {
                    **inference(
                        "inf-stale-wording",
                        route_id="route-stale-wording",
                        conclusion_claim_id="stale-wording",
                        validation_status="challenged",
                    ),
                    "evidence_artifact_ids_json": json.dumps(["old-proof-dossier"]),
                }
            ],
            "debts": [],
            "recent_runs": [],
        }

        action = _unrouted_proof_claim_action(
            None,
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="hard_problem",
        )

        self.assertIsNone(action)

    def test_executive_advisor_lock_falls_back_from_superseded_target(self) -> None:
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim(
                    "stale-wording",
                    1,
                    lifecycle_status="superseded",
                    validation_status="challenged",
                    parent_ids=["root"],
                ),
            ],
            "routes": [route("route-stale-wording", conclusion_claim_id="stale-wording", status="superseded")],
            "inferences": [],
            "debts": [],
            "research_artifacts": [
                {
                    "artifact_id": "advisor-stale-lock",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 10,
                    "created_at": "2026-01-04T00:02:00+00:00",
                    "content_summary": "Retire the stale wording and continue the root theorem.",
                    "metadata_json": json.dumps(
                        {
                            "advisor_followup_required": True,
                            "triage_status": "decisive_root_bottleneck",
                            "bottleneck_obligation": "Continue the root theorem after retiring stale wording.",
                            "next_decisive_task": "Work the remaining root bottleneck.",
                            "next_role": "researcher",
                            "next_target_id": "stale-wording",
                            "recommended_next_action": "Do not reactivate the superseded claim.",
                        }
                    ),
                }
            ],
            "recent_runs": [],
            "retrieval_cards": [],
            "theorem_library_entries": [],
        }

        action = _executive_advisor_bottleneck_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="hard_problem",
        )

        assert action is not None
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "")

    def test_executive_advisor_lock_does_not_reopen_refuted_target(self) -> None:
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim(
                    "refuted-paper-claim",
                    1,
                    lifecycle_status="active",
                    validation_status="refuted",
                    parent_ids=["root"],
                ),
            ],
            "routes": [route("route-refuted-paper-claim", conclusion_claim_id="refuted-paper-claim")],
            "inferences": [],
            "debts": [
                debt(
                    "debt-refuted-paper-claim",
                    owner_id="refuted-paper-claim",
                    obligation="Old debt superseded by a confirmed counterexample.",
                )
            ],
            "research_artifacts": [
                {
                    "artifact_id": "advisor-stale-refuted-lock",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 10,
                    "created_at": "2026-01-04T00:02:00+00:00",
                    "content_summary": "Verify the paper claim before the counterexample was confirmed.",
                    "metadata_json": json.dumps(
                        {
                            "advisor_followup_required": True,
                            "triage_status": "decisive_root_bottleneck",
                            "bottleneck_obligation": "Adjudicate the paper claim.",
                            "next_decisive_task": "Prove the old paper route.",
                            "next_role": "researcher",
                            "next_target_id": "refuted-paper-claim",
                            "obstruction_debts": ["debt-refuted-paper-claim"],
                        }
                    ),
                }
            ],
            "recent_runs": [],
            "retrieval_cards": [],
            "theorem_library_entries": [],
        }

        action = _executive_advisor_bottleneck_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="paper_solution_audit",
        )

        self.assertIsNone(action)

    def test_blocking_debt_selector_skips_retired_graph_debts(self) -> None:
        state = {
            "problem_state": {"max_reduction_depth": 8},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim(
                    "stale-wording",
                    1,
                    lifecycle_status="superseded",
                    validation_status="challenged",
                    parent_ids=["root"],
                ),
            ],
            "routes": [route("route-stale-wording", conclusion_claim_id="stale-wording", status="superseded")],
            "inferences": [
                inference(
                    "inf-stale-wording",
                    route_id="route-stale-wording",
                    conclusion_claim_id="stale-wording",
                    validation_status="challenged",
                )
            ],
            "debts": [
                debt(
                    "stale-inference-debt",
                    owner_type="inference",
                    owner_id="inf-stale-wording",
                    suggested_next_target="inf-stale-wording",
                ),
                debt(
                    "refuted-claim-debt",
                    owner_type="claim",
                    owner_id="refuted-wording",
                    suggested_next_target="refuted-wording",
                ),
                debt("live-root-debt", owner_type="claim", owner_id="root", suggested_next_target="root"),
            ],
            "research_artifacts": [],
        }

        selected = _first_blocking_debt(state)

        assert selected is not None
        self.assertEqual(selected["debt_id"], "live-root-debt")
        self.assertEqual(
            [row["debt_id"] for row in _bottleneck_lock_debt_candidates(state)],
            ["live-root-debt"],
        )

    def test_advisor_requested_candidate_validation_preempts_more_proving(self) -> None:
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [],
            "inferences": [],
            "debts": [],
            "research_artifacts": [
                {
                    "artifact_id": "advisor-candidate-validation",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 12,
                    "created_at": "2026-01-04T00:02:00+00:00",
                    "content_summary": "Validate the concrete candidate before pivoting.",
                    "metadata_json": json.dumps(
                        {
                            "advisor_followup_required": True,
                            "classification": "candidate_counterexample_needing_validator",
                            "next_role": "verifier",
                            "next_target_id": "root",
                            "next_decisive_task": "Validate the candidate construction.",
                            "next_task_acceptance_criteria": ["Check every asserted property."],
                        }
                    ),
                },
                {
                    "artifact_id": "candidate-terminal-c3",
                    "artifact_type": "candidate_counterexample",
                    "producer_role": "villain",
                    "state_revision": 14,
                    "created_at": "2026-01-04T00:04:00+00:00",
                    "content_summary": "Concrete terminal-C3 counterexample.",
                    "metadata_json": json.dumps(
                        {
                            "target_id": "root",
                            "threatened_obligation": "debt-terminal-classification",
                            "obstruction_type": "route_killing",
                        }
                    ),
                },
                {
                    "artifact_id": "deep-session-terminal-c3",
                    "artifact_type": "deep_session_report",
                    "producer_role": "researcher",
                    "state_revision": 13,
                    "created_at": "2026-01-04T00:03:00+00:00",
                    "content_summary": "Full proof packet for the candidate.",
                    "metadata_json": json.dumps({"artifact_roi": "bottleneck_narrowed"}),
                },
            ],
            "recent_runs": [],
            "retrieval_cards": [],
            "theorem_library_entries": [],
        }

        action = _advisor_requested_validation_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="hard_problem",
        )

        assert action is not None
        self.assertEqual(action["mode"], "validate_counterexample")
        self.assertEqual(action["target_id"], "root")
        self.assertTrue(action["advisor_requested_validation"])
        self.assertEqual(action["candidate_counterexample_artifact_id"], "candidate-terminal-c3")
        self.assertEqual(
            action["validation_evidence_artifact_ids"],
            ["candidate-terminal-c3", "deep-session-terminal-c3"],
        )
        self.assertEqual(actor_role_for_action(action), "counterexample_validator")

    def test_advisor_strict_verifier_handoff_resolves_inference_target(self) -> None:
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [claim("root", 0, root_impact=1.0, validation_status="challenged")],
            "routes": [
                {
                    **route("route-root", conclusion_claim_id="root"),
                    "evidence_artifact_ids_json": '["old-route-plan"]',
                }
            ],
            "inferences": [
                {
                    **inference(
                        "inf-root",
                        route_id="route-root",
                        conclusion_claim_id="root",
                    ),
                    "evidence_artifact_ids_json": '["root-proof"]',
                }
            ],
            "debts": [],
            "research_artifacts": [
                {
                    "artifact_id": "old-route-plan",
                    "artifact_type": "decomposition_plan",
                    "producer_role": "researcher",
                    "state_revision": 1,
                    "created_at": "2026-01-04T00:00:00+00:00",
                    "content_summary": "An obsolete route decomposition.",
                    "metadata_json": json.dumps({"route_id": "route-root"}),
                },
                {
                    "artifact_id": "root-proof",
                    "artifact_type": "proof_dossier",
                    "producer_role": "researcher",
                    "state_revision": 10,
                    "created_at": "2026-01-04T00:01:00+00:00",
                    "content_summary": "Root proof packet.",
                    "metadata_json": json.dumps({"target_id": "root", "route_id": "route-root"}),
                },
                {
                    "artifact_id": "advisor-verifier-handoff",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 12,
                    "created_at": "2026-01-04T00:02:00+00:00",
                    "content_summary": "Verify the decisive inference.",
                    "metadata_json": json.dumps(
                        {
                            "advisor_followup_required": True,
                            "proof_candidate": True,
                            "next_role": "strict_informal_verifier",
                            "next_target_id": "inf-root",
                            "recommended_next_action": "Check the exact theorem splice.",
                            "next_task_acceptance_criteria": ["Check every hypothesis."],
                            "kept_route_ids": ["route-root"],
                        }
                    ),
                },
            ],
            "recent_runs": [],
            "retrieval_cards": [],
            "theorem_library_entries": [],
        }

        action = _advisor_requested_strict_verifier_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="hard_problem",
        )

        assert action is not None
        self.assertEqual(action["mode"], "prove")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["route_id"], "route-root")
        self.assertEqual(action["verification_focus_inference_id"], "inf-root")
        self.assertEqual(action["advisor_report_id"], "advisor-verifier-handoff")
        self.assertEqual(action["validation_acceptance_criteria"], ["Check every hypothesis."])
        self.assertEqual(action["strict_verifier_scope"], "single_route_verification_packet")
        self.assertEqual(action["verifier_evidence_artifact_ids"], ["root-proof", "old-route-plan"])
        self.assertEqual(actor_role_for_action(action), "strict_informal_verifier")

    def test_advisor_requested_villain_task_preempts_researcher_lock(self) -> None:
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [claim("root", 0, root_impact=1.0)],
            "routes": [],
            "inferences": [],
            "debts": [],
            "research_artifacts": [
                {
                    "artifact_id": "advisor-villain-cas",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 20,
                    "created_at": "2026-01-04T00:05:00+00:00",
                    "content_summary": "Run the exact adversarial extension test.",
                    "metadata_json": json.dumps(
                        {
                            "advisor_followup_required": True,
                            "next_role": "villain",
                            "next_target_id": "root",
                            "directed_villain_mode": "cas",
                            "next_decisive_task": "Classify the finite extension family.",
                            "recommended_next_action": "Dispatch one villain CAS pass.",
                            "next_task_acceptance_criteria": ["Cover every extension class."],
                        }
                    ),
                }
            ],
            "recent_runs": [],
            "retrieval_cards": [],
            "theorem_library_entries": [],
        }

        action = _advisor_requested_villain_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="hard_problem",
        )

        assert action is not None
        self.assertEqual(action["mode"], "refute")
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["advisor_report_id"], "advisor-villain-cas")
        self.assertTrue(action["counterexample_search_required"])
        self.assertTrue(action["cas_check_recommended"])
        self.assertEqual(actor_role_for_action(action), "villain")

    def test_near_solution_portfolio_schedules_root_spine_synthesis(self) -> None:
        proof_artifacts = [
            {
                "artifact_id": f"spine-art-{index}",
                "artifact_type": "proof_dossier",
                "producer_role": "researcher",
                "state_revision": index,
                "created_at": f"2026-01-04T00:0{index}:00+00:00",
                "content_summary": "Durable proof packet.",
                "metadata_json": json.dumps({"target_id": "root", "artifact_roi": "bottleneck_narrowed"}),
            }
            for index in range(5)
        ]
        state = {
            "problem_state": {"remaining_token_budget": 10_000_000, "reserved_verification_budget": 0},
            "claims": [
                claim("root", 0, root_impact=1.0),
                *[
                    claim(
                        f"trunk-{index}",
                        1,
                        root_impact=0.55,
                        validation_status="informally_verified",
                        parent_ids=["root"],
                    )
                    for index in range(5)
                ],
            ],
            "routes": [],
            "inferences": [],
            "debts": [
                debt(
                    "debt-root-last-gap",
                    owner_id="root",
                    obligation="One final theorem-level gap remains.",
                )
            ],
            "research_artifacts": proof_artifacts,
            "recent_runs": [],
            "retrieval_cards": [],
            "theorem_library_entries": [],
        }

        action = _near_solution_spine_synthesis_action(
            state,
            problem=state["problem_state"],
            requested_tokens=None,
            research_mode="hard_problem",
        )

        assert action is not None
        self.assertEqual(action["target_id"], "root")
        self.assertEqual(action["search_intent"], "near_solution_spine_synthesis")
        self.assertTrue(action["near_solution_spine_synthesis_required"])
        self.assertTrue(action["closure_pipeline_required"])
        self.assertEqual(action["closure_debt_id"], "debt-root-last-gap")
        self.assertTrue(action["canonical_proof_update_required"])
        self.assertEqual(action["canonical_proof_artifact_id"], "spine-art-4")
        self.assertTrue(action["proof_spine_mode_required"])
        self.assertTrue(action["hard_theorem_attack_required"])
        self.assertEqual(action["near_solution_spine_signal"]["selected_debt_id"], "debt-root-last-gap")
        self.assertEqual(action["budget"]["policy"], "hard_theorem_workbench")

    def test_source_obstruction_does_not_recommend_cas(self) -> None:
        first = debt(
            "debt-source-a",
            owner_id="root",
            suggested_next_target="root",
            debt_type="missing_reference",
            obligation="Cite the exact high rank orthogonal automorphism classification theorem with scalar kernel.",
        )
        second = debt(
            "debt-source-b",
            owner_id="root",
            suggested_next_target="root",
            debt_type="missing_reference",
            obligation="Supply the precise high rank orthogonal automorphism classification source and scalar kernel theorem.",
        )
        payload = _central_obstruction_payload(
            {"claims": [claim("root", 0, root_impact=1.0)], "routes": [], "inferences": [], "debts": [first, second]},
            first,
        )
        self.assertTrue(payload["closure_pressure_required"])
        self.assertFalse(payload["cas_check_recommended"])
        self.assertFalse(payload["experiment_decision_gate_required"])

    def test_certified_partial_progress_with_bottleneck_schedules_creative_attack(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("scheduler-creative-proof-attack-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_claim",
                            "claim_id": "partial-lemma-a",
                            "statement": "First certified side lemma near the root.",
                            "parent_ids": ["root"],
                            "root_impact": 0.8,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "partial-lemma-b",
                            "statement": "Second certified side lemma near the root.",
                            "parent_ids": ["root"],
                            "root_impact": 0.75,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "root-obstruction-a",
                            "artifact_type": "route_obstruction",
                            "content": "The strongest route still runs into a central bridge obstruction.",
                            "metadata": {"target_id": "root", "obstruction_type": "central_bridge"},
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "root-obstruction-b",
                            "artifact_type": "construction_failure",
                            "content": "The natural construction fails unless the bridge theorem is strengthened.",
                            "metadata": {"target_id": "root", "attempted_method": "natural construction"},
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-root-central-bridge",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Decide the central bridge theorem that would assemble the partial lemmas into the root proof.",
                            "source_artifact_ids": ["root-obstruction-a", "root-obstruction-b"],
                            "suggested_next_target": "root",
                        },
                    ],
                    "rationale": "seed partial progress and bottleneck signals",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)
            verified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "vr-partials",
                            "artifact_type": "verification_report",
                            "content": "Both side lemmas are checked; critical_errors=[]; gaps=[]",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {"critical_errors": [], "gaps": [], "blocking_gap": False},
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "partial-lemma-a",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["vr-partials"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "partial-lemma-b",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["vr-partials"],
                        },
                    ],
                    "rationale": "verify side lemmas",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            action = next_action(store, research_mode="hard_problem", web_search="disabled")
            manifest = build_context_manifest(store, action=action)

        self.assertEqual(actor_role_for_action(action), "researcher")
        self.assertEqual(action["search_intent"], "creative_proof_attack")
        self.assertTrue(action["creative_proof_attack_required"])
        self.assertTrue(action["wild_mathematician_mode"])
        self.assertTrue(action["obstruction_inversion_required"])
        self.assertTrue(action["paperwork_throttle_required"])
        self.assertEqual(action["budget"]["policy"], "deep_research_pass")
        self.assertEqual(action["budget"]["requested_tokens"], 650_000)
        self.assertIn("partial-lemma-a", action["creative_attack_signal"]["partial_credit_claim_ids"])
        self.assertIn("root-obstruction-a", action["creative_attack_signal"]["obstruction_artifact_ids"])
        self.assertTrue(manifest["workflow_action"]["creative_proof_attack_required"])
        self.assertTrue(manifest["researcher_packet"]["staged_attack_policy"]["creative_proof_attack_required"])
        self.assertIn("creative_proof_attack_rule", manifest["researcher_packet"]["staged_attack_policy"])
        self.assertIn("creative_attack_override", manifest["researcher_packet"]["paperwork_budget_policy"])

    def test_theorem_matching_confidence_high_for_verified_direct_match(self) -> None:
        confidence = theorem_matching_confidence(
            {
                "classification": "direct_match",
                "theorem_matching_status": "verified_statement_match",
                "implication_to_target_verified": True,
            },
            missing_hypotheses=[],
        )

        self.assertEqual(confidence["level"], "high")
        self.assertGreater(confidence["score"], 0.9)

    def test_recursive_meta_drift_stops_when_frontier_is_bookkeeping(self) -> None:
        state = {
            "problem_state": {"max_reduction_depth": 3},
            "claims": [
                claim("root", 0, root_impact=1.0),
                claim("meta-1", 7, statement="Define the candidate inventory JSON schema"),
                claim("meta-2", 8, statement="Validate the metadata envelope serialization"),
                claim("meta-3", 8, statement="Check the context manifest row contract"),
                claim("meta-4", 9, statement="Build the proof-state schema validator"),
            ],
            "debts": [],
        }

        drift = _recursive_meta_drift(state)
        self.assertIsNotNone(drift)
        assert drift is not None
        self.assertIn("recursive bookkeeping decomposition", drift["reason"])
        self.assertGreaterEqual(drift["deepest_reduction_depth"], 7)

    def test_stop_writer_action_preserves_terminal_context(self) -> None:
        action = _stop_writer_action(
            {
                "mode": "stop_with_partial_results",
                "reason": "workflow step limit reached",
                "terminal_classification": "step_limited_partial",
            }
        )

        self.assertEqual(action["mode"], "write")
        self.assertTrue(action["write_existing_proofs_on_stop"])
        self.assertEqual(action["stop_reason"], "workflow step limit reached")
        self.assertEqual(action["terminal_classification"], "step_limited_partial")

    def test_writer_prompt_requires_reference_section(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "write", "target_id": "root"},
            actor_role="writer",
        )

        self.assertIn("End every final_proof", prompt)
        self.assertIn("'References' section written by the writer", prompt)
        self.assertIn("theorem/proposition/lemma numbers", prompt)
        self.assertIn("Author(s), title of paper/book", prompt)
        self.assertIn("arXiv/DOI/URL if available", prompt)
        self.assertIn("keep the artifact content compact and JSON-safe", prompt)
        self.assertIn("under roughly 8000 characters", prompt)

    def test_child_prompt_forbids_plugin_discovery_tools(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "prove", "target_id": "root"},
            actor_role="researcher",
        )

        self.assertIn("Do not call tool_search", prompt)
        self.assertIn("plugin discovery", prompt)
        self.assertIn("can corrupt structured patch output", prompt)

    def test_non_cas_roles_are_told_to_request_cas_artifacts(self) -> None:
        advisor_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "triage_routes", "target_id": "root"},
            actor_role="phd_advisor",
        )
        verifier_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "prove", "target_id": "root", "route_id": "route-1"},
            actor_role="strict_informal_verifier",
        )
        researcher_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "prove", "target_id": "root"},
            actor_role="researcher",
        )

        self.assertIn("CAS lifecycle tools and CAS/data asset execution are not available", advisor_prompt)
        self.assertIn("Do not call discover_cas_backends", advisor_prompt)
        self.assertIn("request a bounded researcher or villain CAS check", advisor_prompt)
        self.assertIn("Do not compute independently", verifier_prompt)
        self.assertIn("cas_experiment_report artifacts", verifier_prompt)
        self.assertIn("Use CAS lifecycle tools", researcher_prompt)
        self.assertNotIn("CAS lifecycle tools and CAS/data asset execution are not available", researcher_prompt)

    def test_researcher_prompt_respects_frontier_pressure(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "reduce", "target_id": "branch"},
            actor_role="researcher",
        )

        self.assertIn("manifest.workflow_action.frontier_pressure.over_claim_cap=true", prompt)
        self.assertIn("do not add new route-less claims", prompt)
        self.assertIn("working mathematician", prompt)
        self.assertIn("Albilich-native research loop", prompt)
        self.assertIn("proof_dossier", prompt)
        self.assertIn("research_diagnostic", prompt)
        self.assertIn("decomposition_plan", prompt)
        self.assertIn("failed_decomposition_plan", prompt)
        self.assertIn("natural_case_split", prompt)
        self.assertIn("dependency_edges", prompt)
        self.assertIn("parallelizable_groups", prompt)
        self.assertIn("decomposition_regulator_required", prompt)
        self.assertIn("Cite external mathematics responsibly", prompt)
        self.assertIn("Use CAS tools", prompt)
        self.assertIn("cas_experiment_report", prompt)
        self.assertIn("staged attacks", prompt)
        self.assertIn("research_notebook", prompt)
        self.assertIn("Spend most tokens on the mathematical", prompt)
        self.assertIn("artifact_roi", prompt)
        self.assertIn("ornamental paperwork", prompt)
        self.assertIn("Stop a research pass", prompt)

    def test_researcher_prompt_explains_checkpointed_synthesis(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={
                "mode": "reduce",
                "target_id": "root",
                "route_id": "route-root",
                "checkpointed_synthesis_required": True,
            },
            actor_role="researcher",
        )

        self.assertIn("workflow_action.checkpointed_synthesis_required=true", prompt)
        self.assertIn("preserve one natural mathematical checkpoint", prompt)
        self.assertIn("global_context_summary", prompt)
        self.assertIn("local_obligation", prompt)
        self.assertIn("what_changed", prompt)
        self.assertIn("next_decisive_action", prompt)
        self.assertIn("not an invitation to split the problem into tiny formal fragments", prompt)

    def test_phd_advisor_regulator_prompt_classifies_decomposition_failures(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "regulate_decomposition", "target_id": "root"},
            actor_role="phd_advisor",
        )

        self.assertIn("decomposition regulator", prompt)
        self.assertIn("proof_execution_error", prompt)
        self.assertIn("plan_gap", prompt)
        self.assertIn("strategy_failure", prompt)
        self.assertIn("branch_incompatibility", prompt)
        self.assertIn("Revise_Proof", prompt)

    def test_phd_advisor_evidence_synthesis_prompt_keeps_original_problem_in_view(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "triage_routes", "target_id": "root", "advisor_evidence_synthesis_required": True},
            actor_role="phd_advisor",
        )

        self.assertIn("parallel evidence-synthesis advisor", prompt)
        self.assertIn("original root problem", prompt)
        self.assertIn("candidate_full_proof_strategy", prompt)
        self.assertIn("compact advisor_report", prompt)
        self.assertIn("current_best_plan", prompt)
        self.assertIn("bottleneck_obligation", prompt)
        self.assertIn("remaining_gaps", prompt)
        self.assertIn("next_task_acceptance_criteria", prompt)
        self.assertIn("proof_candidate=true", prompt)
        self.assertIn("do not verify", prompt)

    def test_phd_advisor_global_synthesis_prompt_uses_exact_nested_keys(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "triage_routes", "target_id": "root", "advisor_global_synthesis_required": True},
            actor_role="phd_advisor",
        )

        self.assertIn("manifest.advisor_synthesis_contract exactly", prompt)
        self.assertIn("metadata.advisor_synthesis", prompt)
        self.assertIn("exact_root_status", prompt)
        self.assertIn("evidence_that_would_change_strategy", prompt)
        self.assertIn("recommended_next_actions", prompt)
        self.assertIn("budget_distribution", prompt)
        self.assertIn("synthesis_confidence", prompt)

    def test_researcher_proof_compression_prompt_uses_exact_nested_keys(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "reduce", "target_id": "root", "proof_compression_operation_required": True},
            actor_role="researcher",
        )

        self.assertIn("manifest.proof_compression_contract exactly", prompt)
        self.assertIn("metadata.minimal_proof_skeleton", prompt)
        self.assertIn("essential_verified_facts", prompt)
        self.assertIn("essential_routes", prompt)
        self.assertIn("conditional_steps", prompt)
        self.assertIn("unused_or_low_value_branches", prompt)
        self.assertIn("shortest_known_route", prompt)
        self.assertIn("weakest_sufficient_new_statement", prompt)
        self.assertIn("may be empty when the state has no verified claims", prompt)

    def test_cas_mode_prompt_uses_exact_experiment_keys(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "reduce", "target_id": "root", "researcher_work_mode": "cas"},
            actor_role="researcher",
        )

        self.assertIn("manifest.cas_experiment_contract exactly", prompt)
        self.assertIn("mathematical_question", prompt)
        self.assertIn("competing_hypotheses", prompt)
        self.assertIn("backend_or_manual_method", prompt)
        self.assertIn("expected_decisive_outputs", prompt)
        self.assertIn("decision_changed", prompt)

    def test_phd_advisor_prompt_classifies_repeated_verifier_loops(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "triage_routes", "target_id": "root", "verifier_loop_classification_required": True},
            actor_role="phd_advisor",
        )

        self.assertIn("verifier_loop_classification_required=true", prompt)
        self.assertIn("local_repair_or_typo", prompt)
        self.assertIn("missing_theorem", prompt)
        self.assertIn("bad_strategy", prompt)
        self.assertIn("abandon_or_pause_route", prompt)
        self.assertIn("verifier_gap_debt_ids", prompt)
        self.assertIn("Do not certify the proof yourself", prompt)

    def test_phd_advisor_prompt_classifies_obstruction_after_researcher_timeout(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "triage_routes", "target_id": "root", "advisor_obstruction_conversion_required": True},
            actor_role="phd_advisor",
        )

        self.assertIn("advisor_obstruction_conversion_required=true", prompt)
        self.assertIn("researcher already stalled", prompt)
        self.assertIn("route_killing_obstruction", prompt)
        self.assertIn("generalized_construction_needed", prompt)
        self.assertIn("one next role/task", prompt)
        self.assertIn("Do not ask for the same broad researcher synthesis again", prompt)

    def test_researcher_prompt_acts_on_advisor_followup_without_verifying(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "prove", "target_id": "root", "advisor_followup_required": True, "advisor_proof_candidate": True},
            actor_role="researcher",
        )

        self.assertIn("advisor_report", prompt)
        self.assertIn("immediate consulting", prompt)
        self.assertIn("route/inference", prompt)
        self.assertIn("strict verification", prompt)
        self.assertIn("Do not mark it verified yourself", prompt)

    def test_researcher_prompt_requires_current_best_plan_for_architecture_pressure(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={
                "mode": "prove",
                "target_id": "root",
                "proof_architecture_required": True,
                "route_contract_required": True,
                "obligation_reduction_required": True,
                "speculative_proof_required": True,
                "repair_loop_required": True,
                "dead_route_suppression_required": True,
            },
            actor_role="researcher",
        )

        self.assertIn("workflow_action.proof_architecture_required=true", prompt)
        self.assertIn("current_best_plan", prompt)
        self.assertIn("route_contracts", prompt)
        self.assertIn("bottleneck_obligation", prompt)
        self.assertIn("speculative_proof_attempt", prompt)
        self.assertIn("paused_route_ids_respected", prompt)

    def test_researcher_prompt_requires_creative_math_attack_not_paperwork(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={
                "mode": "prove",
                "target_id": "root",
                "creative_proof_attack_required": True,
                "wild_mathematician_mode": True,
                "obstruction_inversion_required": True,
                "failure_autopsy_required": True,
                "paperwork_throttle_required": True,
            },
            actor_role="researcher",
        )

        self.assertIn("workflow_action.creative_proof_attack_required=true", prompt)
        self.assertIn("wild-but-disciplined mathematician mode", prompt)
        self.assertIn("full proof", prompt)
        self.assertIn("invert the central obstruction", prompt)
        self.assertIn("management-only research_notebook", prompt)
        self.assertIn("Do not mark anything verified yourself", prompt)

    def test_researcher_bridge_workbench_prompt_requires_debt_sharpening(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={
                "mode": "prove",
                "target_id": "root",
                "bridge_lemma_workbench_required": True,
                "closure_pressure_required": True,
                "central_debt_id": "debt-root-bridge",
            },
            actor_role="researcher",
        )

        self.assertIn("workflow_action.bridge_lemma_workbench_required=true", prompt)
        self.assertIn("If the output is an obstruction, construction_failure, or sharper sub-bridge", prompt)
        self.assertIn("include an update_debt for workflow_action.central_debt_id", prompt)
        self.assertIn("one new precise blocking add_debt", prompt)
        self.assertIn("narrowed obligation instead of repeating this pass", prompt)
        self.assertIn("never emit forward_support=[]", prompt)

    def test_researcher_prompt_enforces_bottleneck_lock_contract(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={
                "mode": "prove",
                "target_id": "root",
                "bottleneck_lock_required": True,
                "sublemma_extraction_required": True,
                "side_branch_roi_cap_active": True,
                "proof_spine_mode_required": True,
                "duplicate_math_guard_required": True,
                "near_miss_memory_required": True,
                "villain_obstruction_to_lemma_required": True,
                "executive_advisor_lock_required": True,
                "hard_theorem_attack_required": True,
                "theorem_workbench_required": True,
                "near_solution_spine_synthesis_required": True,
            },
            actor_role="researcher",
        )

        self.assertIn("workflow_action.bottleneck_lock_required=true", prompt)
        self.assertIn("diagnostic cooldown is active", prompt)
        self.assertIn("verifier-checkable sublemma", prompt)
        self.assertIn("ROI cap", prompt)
        self.assertIn("management-only research_notebook", prompt)
        self.assertIn("short proof spine", prompt)
        self.assertIn("duplicate_math_guard_required", prompt)
        self.assertIn("near_miss_memory_required", prompt)
        self.assertIn("villain_obstruction_to_lemma_required", prompt)
        self.assertIn("executive_advisor_lock_required=true", prompt)
        self.assertIn("binding steering decision", prompt)
        self.assertIn("hard theorem workbench", prompt)
        self.assertIn("near-proof portfolio", prompt)

    def test_villain_refute_mode_records_candidate_counterexamples_only(self) -> None:
        action = {"mode": "refute", "target_id": "root"}
        self.assertEqual(actor_role_for_action(action), "villain")
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action=action,
            actor_role="villain",
        )

        self.assertIn("Act as the villain", prompt)
        self.assertIn("candidate_counterexample", prompt)
        self.assertIn("counterexample_validator", prompt)
        self.assertIn("CAS tools", prompt)
        self.assertIn("cas_experiment_report", prompt)
        self.assertIn("bounded adversarial", prompt)

    def test_counterexample_validator_prompt_requires_same_patch_refutation(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "validate_counterexample", "target_id": "claim-candidate"},
            actor_role="counterexample_validator",
        )

        self.assertIn("confirmed_counterexample", prompt)
        self.assertIn("validation_status=refuted", prompt)
        self.assertIn("in the same patch", prompt)
        self.assertIn("do not leave a confirmed falsification merely challenged", prompt)

    def test_counterexample_reconciliation_prompt_reuses_confirmation(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={
                "mode": "validate_counterexample",
                "target_id": "claim-candidate",
                "counterexample_status_reconciliation_required": True,
                "confirmed_counterexample_artifact_id": "confirmed-candidate",
            },
            actor_role="counterexample_validator",
        )

        self.assertIn("Reuse workflow_action.confirmed_counterexample_artifact_id", prompt)
        self.assertIn("Do not attach a duplicate", prompt)
        self.assertIn("validation_status=refuted", prompt)

    def test_session_prompt_forbids_broad_process_control_and_sympy_assumption(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "refute", "target_id": "root"},
            actor_role="villain",
        )

        self.assertIn("never use broad process-control commands", prompt)
        self.assertIn("pkill", prompt)
        self.assertIn("killall", prompt)
        self.assertIn("cas_stop", prompt)
        self.assertIn("Do not assume optional Python packages such as sympy", prompt)

    def test_verifier_prompt_allows_exact_cited_theorems_as_evidence(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "prove", "target_id": "root", "citation_certification_required": True},
            actor_role="strict_informal_verifier",
        )

        self.assertIn("External mathematics may discharge a step", prompt)
        self.assertIn("reasonable citation", prompt)
        self.assertIn("citation_triage_required", prompt)
        self.assertIn("certify_external_citation", prompt)
        self.assertIn("missing_reference", prompt)
        self.assertIn("do not demand an internal reproof", prompt)
        self.assertIn("CAS experiment reports", prompt)

    def test_verifier_prompt_checks_decomposition_parent_implication(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "prove", "target_id": "root", "route_id": "route-root", "parent_implication_required": True},
            actor_role="strict_informal_verifier",
        )

        self.assertIn("parent_implication_required", prompt)
        self.assertIn("subgoals", prompt)
        self.assertIn("parent claim", prompt)
        self.assertIn("dependency_edges must be acyclic", prompt)
        self.assertIn("case split", prompt)

    def test_literature_researcher_source_synthesis_prompt_requests_compatibility_table_without_verifying(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "synthesize_sources", "target_id": "root"},
            actor_role="literature_researcher",
        )

        self.assertIn("Make a table", prompt)
        self.assertIn("compatibility lemma", prompt)
        self.assertIn("Do not mark claims verified", prompt)

    def test_literature_researcher_prompt_requests_source_adaptation_notes(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "retrieve", "target_id": "root"},
            actor_role="literature_researcher",
        )

        self.assertIn("source_adaptation_notes", prompt)
        self.assertIn("local statement translation", prompt)
        self.assertIn("handoff to the researcher", prompt)
        self.assertIn("researcher_search_request", prompt)
        self.assertIn("search_request_id", prompt)
        self.assertIn("program_victory_candidate=true", prompt)
        self.assertIn("stop searching", prompt)
        self.assertIn("use the Codex web-search/source-view capability", prompt)
        self.assertIn("do not use shell network commands such as curl", prompt)

    def test_researcher_prompt_can_request_targeted_literature_search_and_digest_sources(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "reduce", "target_id": "root", "source_adaptation_digest_required": True},
            actor_role="researcher",
        )

        self.assertIn("source_adaptation_digest_required", prompt)
        self.assertIn("literature_search_request", prompt)
        self.assertIn("acceptance_criteria", prompt)

    def test_session_prompt_forbids_prior_result_artifacts_as_evidence(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "reduce", "target_id": "root"},
            actor_role="researcher",
        )

        self.assertIn("Stay inside the evidence boundary", prompt)
        self.assertIn("Do not search or read prior results", prompt)
        self.assertIn("agents/generation/results", prompt)
        self.assertIn("workflow_runs", prompt)
        self.assertIn("codex.log", prompt)
        self.assertIn("proof_state.sqlite3", prompt)
        self.assertIn("raw SQLite proof databases", prompt)
        self.assertIn("raw prior session transcripts", prompt)

    def test_retrieval_card_preserves_reference_metadata_for_writer(self) -> None:
        card = _retrieval_card(
            {
                "card_id": "cite-demo",
                "exact_statement": "Exact theorem statement.",
                "source_identifiers_json": json.dumps(
                    {
                        "author": "A. Author",
                        "title": "Useful Paper",
                        "theorem_number": "Theorem 2.3",
                    }
                ),
                "source_version": "arXiv:1234.5678v2",
                "hypotheses_json": json.dumps(["smooth projective curve"]),
                "local_definitions_json": json.dumps(["M is the fixed-determinant moduli space"]),
                "applicability_json": json.dumps(
                    {
                        "classification": "direct_match",
                        "theorem_matching_status": "verified_statement_match",
                        "implication_to_target_verified": True,
                    }
                ),
                "missing_hypotheses_json": json.dumps([]),
                "source_location": "Theorem 2.3, p. 17",
            }
        )

        self.assertEqual(card["source_version"], "arXiv:1234.5678v2")
        self.assertEqual(card["source_identifiers"]["theorem_number"], "Theorem 2.3")
        self.assertEqual(card["hypotheses"], ["smooth projective curve"])
        self.assertEqual(card["local_definitions"], ["M is the fixed-determinant moduli space"])


if __name__ == "__main__":
    unittest.main()
