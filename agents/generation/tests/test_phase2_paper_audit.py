from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.audit import (
    AUDIT_CLAIM_STATUSES,
    AUDIT_SUBJECT_ARTIFACT_ID,
    AUDIT_SUBJECT_ARTIFACT_TYPE,
    AUDIT_WARNING_LINE,
    PAPER_AUDIT_DOCUMENT_INTEGRATION_MARKER,
    PAPER_AUDIT_DOCUMENT_REVIEW_MARKER,
    PAPER_AUDIT_REFEREE_REPORT_MARKER,
    PAPER_AUDIT_RESEARCH_MODE,
    REFEREE_REPORT_ARTIFACT_TYPE,
    audit_confidence_summary,
    build_referee_report_lines,
    ingest_paper_audit,
    is_audit_state,
    is_paper_audit_mode,
    paper_claims,
)
from agents.generation.phase2.codex_runner import actor_role_for_action, build_session_prompt
from agents.generation.phase2.completion_policy import latest_root_intent_resolution
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.report import build_markdown_report
from agents.generation.phase2.research_policy import (
    RESEARCH_MODES,
    normalize_research_mode,
    should_run_librarian,
)
from agents.generation.phase2.scheduler import (
    multi_branch_research_actions,
    next_action,
    parallel_companion_actions,
)
from agents.generation.phase2.store import ProofStateStore

# A synthetic submitted "proof" with a known hidden gap: step 2 silently
# assumes the group is abelian, which the hypotheses never grant.
SYNTHETIC_PROOF_WITH_GAP = """# Every periodic widget group is bounded

Theorem 1. Every periodic widget group G is bounded.

Proof.
Step 1: Since G is periodic, every element has finite order.
Step 2: Because xy = yx for all x, y in G, the orders multiply, so the exponent is finite.
Step 3: A group of finite exponent is bounded. QED.
"""

FINAL_PROOF_CONTENT = """# Final Proof

Theorem. The root theorem holds.

Proof. We argue directly. Every hypothesis is satisfied by construction, and the conclusion follows. QED.

## References

The reference list is empty; this report was written by the Albilich writer from internal artifacts.
"""


def make_solved_store(tmpdir: Path, problem_id: str) -> ProofStateStore:
    """Store with an integrated root plus a final_proof certificate."""
    store = ProofStateStore(problem_id, generation_root=tmpdir / "generation")
    store.init_problem("prove the root theorem")
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "INSERT INTO routes(route_id, conclusion_claim_id, label, strategy, status, relation_to_parent,"
            " assumptions_json, conditions_json, evidence_artifact_ids_json, failure_fingerprint, created_at, updated_at)"
            " VALUES ('route-root', 'root', 'root route', 'direct', 'integrated', 'sufficient',"
            " '[]', '[]', '[]', '', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )
        conn.execute(
            "UPDATE claims SET lifecycle_status='integrated', validation_status='informally_verified'"
            " WHERE claim_id='root'"
        )
        conn.commit()
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
                    "artifact_id": "final-proof-1",
                    "artifact_type": "final_proof",
                    "content": FINAL_PROOF_CONTENT,
                    "metadata": {"claim_id": "root", "route_id": "route-root"},
                }
            ],
            "rationale": "write final proof",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)
    return store


def ingest_fixture(tmpdir: Path, problem_id: str) -> ProofStateStore:
    document = tmpdir / "submitted_proof.md"
    document.write_text(SYNTHETIC_PROOF_WITH_GAP, encoding="utf-8")
    store = ProofStateStore(problem_id, generation_root=tmpdir / "generation")
    ingest_paper_audit(store, document)
    return store


def apply_audit_claims(store: ProofStateStore) -> None:
    """Simulate the audit decomposition: one checked step, one gap (the known
    hidden abelian assumption), one citation check."""
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
                    "op": "add_claim",
                    "claim_id": "paper-step-1",
                    "statement": "Step 1: every element of a periodic widget group has finite order.",
                    "parent_ids": ["root"],
                    "root_impact": 0.4,
                    "reduction_depth": 1,
                    "validation_status": "plausible",
                    "tags": ["paper_claim", "audit_status:probably_correct", "source_location:Theorem 1, Step 1"],
                },
                {
                    "op": "add_claim",
                    "claim_id": "paper-step-2",
                    "statement": "Step 2 silently assumes G is abelian (xy = yx), which the hypotheses never grant.",
                    "parent_ids": ["root"],
                    "root_impact": 0.9,
                    "reduction_depth": 1,
                    "validation_status": "challenged",
                    "tags": ["paper_claim", "audit_status:gap", "source_location:Theorem 1, Step 2"],
                },
                {
                    "op": "add_claim",
                    "claim_id": "paper-step-3",
                    "statement": "Step 3 cites the bounded-exponent theorem without a source.",
                    "parent_ids": ["root"],
                    "root_impact": 0.5,
                    "reduction_depth": 1,
                    "validation_status": "untested",
                    "tags": ["paper_claim", "audit_status:citation_needed", "source_location:Theorem 1, Step 3"],
                },
                {
                    "op": "attach_artifact",
                    "artifact_id": "repair-abelian-hypothesis",
                    "artifact_type": "proposed_repair",
                    "content": "Proposed repair: add the hypothesis that G is abelian, or replace Step 2 with a commutator-bound argument.",
                    "metadata": {"repairs_claim_id": "paper-step-2", "proposal": True},
                },
            ],
            "rationale": "audit decomposition of the submitted proof",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


def apply_audit_proof_packet(store: ProofStateStore) -> None:
    """Simulate the researcher transcribing one author proof into the normal
    claim -> route -> inference verification pipeline."""
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "researcher",
            "target_id": "paper-theorem-1",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "paper-proof-packet-1",
                    "artifact_type": "proof_dossier",
                    "content": "Statement: Every periodic widget group is bounded.\n\nAuthor proof: Step 1; Step 2; Step 3.",
                    "metadata": {
                        "paper_audit_packet": True,
                        "audit_subject_artifact_id": AUDIT_SUBJECT_ARTIFACT_ID,
                        "claim_id": "paper-theorem-1",
                        "route_id": "paper-route-1",
                        "source_location": "Theorem 1",
                        "artifact_roi": "verifier_ready_route",
                    },
                },
                {
                    "op": "add_claim",
                    "claim_id": "paper-theorem-1-hypothesis",
                    "kind": "hypothesis",
                    "statement": "G is a periodic widget group.",
                    "parent_ids": ["paper-theorem-1"],
                    "root_impact": 0.6,
                    "reduction_depth": 2,
                    "validation_status": "plausible",
                    "evidence_artifact_ids": ["paper-proof-packet-1"],
                    "tags": [
                        "paper_claim",
                        "audit_status:probably_correct",
                        "source_location:Theorem 1 hypothesis",
                    ],
                },
                {
                    "op": "add_claim",
                    "claim_id": "paper-theorem-1",
                    "kind": "theorem",
                    "statement": "Every periodic widget group is bounded.",
                    "parent_ids": ["root"],
                    "root_impact": 1.0,
                    "reduction_depth": 1,
                    "validation_status": "plausible",
                    "evidence_artifact_ids": ["paper-proof-packet-1"],
                    "tags": [
                        "paper_claim",
                        "audit_status:probably_correct",
                        "source_location:Theorem 1",
                    ],
                },
                {
                    "op": "add_route",
                    "route_id": "paper-route-1",
                    "conclusion_claim_id": "paper-theorem-1",
                    "relation_to_parent": "sufficient",
                    "strategy": "Verify the submitted author proof as written.",
                    "evidence_artifact_ids": ["paper-proof-packet-1"],
                },
                {
                    "op": "add_inference",
                    "inference_id": "paper-inference-1",
                    "route_id": "paper-route-1",
                    "conclusion_claim_id": "paper-theorem-1",
                    "premise_claim_ids": ["paper-theorem-1-hypothesis"],
                    "validation_status": "plausible",
                    "explanation": "The author proof purports to establish Theorem 1.",
                    "evidence_artifact_ids": ["paper-proof-packet-1"],
                },
            ],
            "rationale": "transcribe the author proof into a verifier-ready audit packet",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


def apply_unrelated_audit_finding(store: ProofStateStore) -> None:
    """Add a sibling finding that must not leak into another claim's verifier packet."""
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "villain",
            "target_id": "root",
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": "unrelated-counterexample-1",
                    "artifact_type": "candidate_counterexample",
                    "content": "A sibling paper claim has a boundary counterexample.",
                    "metadata": {
                        "target_id": "paper-unrelated-claim",
                        "source_location": "Theorem 9",
                    },
                },
                {
                    "op": "add_claim",
                    "claim_id": "paper-unrelated-claim",
                    "kind": "theorem",
                    "statement": "An unrelated theorem from another part of the paper.",
                    "parent_ids": ["root"],
                    "root_impact": 0.8,
                    "reduction_depth": 1,
                    "validation_status": "challenged",
                    "evidence_artifact_ids": ["unrelated-counterexample-1"],
                    "tags": [
                        "paper_claim",
                        "audit_status:false_or_counterexample_risk",
                        "source_location:Theorem 9",
                    ],
                },
                {
                    "op": "add_debt",
                    "debt_id": "unrelated-counterexample-debt",
                    "owner_type": "claim",
                    "owner_id": "paper-unrelated-claim",
                    "debt_type": "counterexample_risk",
                    "severity": "blocking",
                    "status": "active",
                    "obligation": "Validate the unrelated boundary counterexample.",
                    "source_artifact_ids": ["unrelated-counterexample-1"],
                    "suggested_next_target": "paper-unrelated-claim",
                },
            ],
            "rationale": "exercise strict packet isolation from a sibling audit finding",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


class PaperAuditModePlumbingTest(unittest.TestCase):
    def test_research_mode_registered(self) -> None:
        self.assertIn(PAPER_AUDIT_RESEARCH_MODE, RESEARCH_MODES)
        self.assertEqual(PAPER_AUDIT_RESEARCH_MODE, normalize_research_mode(PAPER_AUDIT_RESEARCH_MODE))
        self.assertTrue(is_paper_audit_mode(PAPER_AUDIT_RESEARCH_MODE))
        self.assertFalse(is_paper_audit_mode("hard_problem"))

    def test_audit_mode_runs_citation_audit_scan(self) -> None:
        state = {"problem_state": {}, "retrieval_cards": [], "runs": [], "debts": []}
        decision = should_run_librarian(state, research_mode=PAPER_AUDIT_RESEARCH_MODE, web_search="live")
        self.assertTrue(decision["run"])
        self.assertIn("citation-audit", decision["reason"])


class PaperAuditIngestionTest(unittest.TestCase):
    def test_ingest_creates_audit_problem_and_subject_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-ingest-test")
            state = store.get_state()

            self.assertTrue(is_audit_state(state))
            root_statement = state["problem_state"]["root_statement"]
            self.assertTrue(root_statement.startswith("Audit the submitted proof of:"))
            self.assertIn("Every periodic widget group is bounded", root_statement)
            self.assertIn("not to prove the theorem independently", root_statement)

            subject = next(
                row for row in state["artifacts"] if row["artifact_type"] == AUDIT_SUBJECT_ARTIFACT_TYPE
            )
            self.assertEqual(AUDIT_SUBJECT_ARTIFACT_ID, subject["artifact_id"])
            self.assertIn("xy = yx", Path(subject["path"]).read_text(encoding="utf-8"))

            with store.connect() as conn:
                events = conn.execute(
                    "SELECT payload_json FROM events WHERE event_type = 'paper_audit_ingested'"
                ).fetchall()
            self.assertEqual(1, len(events))
            self.assertEqual(
                "audit_or_problem_refinement",
                latest_root_intent_resolution(store)["resolved_intent"],
            )

    def test_reingest_same_document_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            document = Path(tmpdir) / "submitted_proof.md"
            document.write_text(SYNTHETIC_PROOF_WITH_GAP, encoding="utf-8")
            store = ProofStateStore("audit-reingest-test", generation_root=Path(tmpdir) / "generation")
            first = ingest_paper_audit(store, document)
            second = ingest_paper_audit(store, document)
            self.assertEqual(first["root_statement"], second["root_statement"])
            state = store.get_state()
            subjects = [row for row in state["artifacts"] if row["artifact_type"] == AUDIT_SUBJECT_ARTIFACT_TYPE]
            self.assertEqual(1, len(subjects))


class PaperAuditSchedulerTest(unittest.TestCase):
    def test_paper_authoring_gate_suppressed_in_audit_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = make_solved_store(Path(tmpdir), "audit-gate-suppressed-test")
            store.set_completion_policy("publication_ready", reason="exercise paper gate suppression", source="test")

            default_action = next_action(store, web_search="disabled")
            self.assertEqual("write", default_action["mode"])
            self.assertTrue(default_action.get("paper_authoring"))

            audit_action = next_action(store, research_mode=PAPER_AUDIT_RESEARCH_MODE, web_search="disabled")
            self.assertEqual("stop_solved", audit_action["mode"])
            self.assertFalse(audit_action.get("paper_authoring", False))

    def test_audit_starts_with_one_direct_strict_review_and_no_research_companions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-verifier-only-start-test")
            action = next_action(
                store,
                research_mode=PAPER_AUDIT_RESEARCH_MODE,
                web_search="disabled",
            )

            self.assertEqual("prove", action["mode"])
            self.assertEqual("root", action["target_id"])
            self.assertEqual("", action["route_id"])
            self.assertTrue(action["paper_audit_verification_only"])
            self.assertTrue(action["paper_audit_document_review_required"])
            self.assertEqual("strict_informal_verifier", actor_role_for_action(action))
            self.assertEqual(
                [],
                parallel_companion_actions(
                    store,
                    action,
                    research_mode=PAPER_AUDIT_RESEARCH_MODE,
                    web_search="disabled",
                ),
            )
            self.assertEqual(
                [],
                multi_branch_research_actions(
                    store,
                    action,
                    [],
                    parallel_branches=3,
                    research_mode=PAPER_AUDIT_RESEARCH_MODE,
                    web_search="disabled",
                ),
            )

            manifest = build_context_manifest(store, action=action, max_chars=100_000)
            self.assertEqual(
                [(AUDIT_SUBJECT_ARTIFACT_ID, AUDIT_SUBJECT_ARTIFACT_TYPE)],
                [(row["artifact_id"], row["artifact_type"]) for row in manifest["artifacts"]],
            )
            self.assertEqual([], manifest["routes"])
            self.assertEqual([], manifest["inferences"])
            self.assertEqual([], manifest["debts"])
            self.assertEqual([], manifest["retrieval_cards"])
            self.assertEqual([], manifest["theorem_library"])
            self.assertEqual("strict_verifier", manifest["patch_contract"]["context_role"])
            self.assertEqual(
                ["attach_artifact"],
                [row["op"] for row in manifest["patch_contract"]["operation_templates"]],
            )

    def test_audit_advances_strict_to_integration_to_referee_report_then_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-verifier-only-sequence-test")
            strict_id = "paper-document-strict-report"
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": strict_id,
                            "artifact_type": "verification_report",
                            "content": "# Strict document review\n\nTheorem 1, Step 2 uses an unstated commutativity hypothesis.",
                            "metadata": {
                                PAPER_AUDIT_DOCUMENT_REVIEW_MARKER: True,
                                "audit_subject_artifact_id": AUDIT_SUBJECT_ARTIFACT_ID,
                                "verdict": "major_gaps",
                                "verification_report": {
                                    "summary": "The submitted proof has a fatal local gap.",
                                    "checked_items": ["Theorem 1, Steps 1-3"],
                                    "critical_errors": ["Step 2 assumes commutativity."],
                                    "gaps": [],
                                    "blocking_gap": "Theorem 1, Step 2",
                                },
                            },
                        }
                    ],
                    "rationale": "record the verifier-only whole-document review",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            integration_action = next_action(
                store,
                research_mode=PAPER_AUDIT_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("integrate", integration_action["mode"])
            self.assertTrue(integration_action["paper_audit_document_integration_required"])
            self.assertEqual("integration_verifier", actor_role_for_action(integration_action))
            self.assertEqual([], parallel_companion_actions(store, integration_action))
            integration_manifest = build_context_manifest(
                store,
                action=integration_action,
                max_chars=100_000,
            )
            self.assertEqual(
                {AUDIT_SUBJECT_ARTIFACT_ID, strict_id},
                {row["artifact_id"] for row in integration_manifest["artifacts"]},
            )
            self.assertEqual(
                ["attach_artifact"],
                [row["op"] for row in integration_manifest["patch_contract"]["operation_templates"]],
            )

            integration_id = "paper-document-integration-report"
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "integration_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": integration_id,
                            "artifact_type": "integration_report",
                            "content": "# Dependency review\n\nThe fatal Step 2 gap prevents Theorem 1 from integrating.",
                            "metadata": {
                                PAPER_AUDIT_DOCUMENT_INTEGRATION_MARKER: True,
                                "strict_report_artifact_id": strict_id,
                                "integrates": False,
                                "outcome": "does_not_integrate",
                                "missing": ["A valid replacement for Theorem 1, Step 2"],
                            },
                        }
                    ],
                    "rationale": "record the verifier-only dependency review",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            writer_action = next_action(
                store,
                research_mode=PAPER_AUDIT_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("write", writer_action["mode"])
            self.assertTrue(writer_action["paper_audit_referee_report_required"])
            self.assertEqual("writer", actor_role_for_action(writer_action))
            writer_manifest = build_context_manifest(store, action=writer_action, max_chars=100_000)
            self.assertEqual(
                {AUDIT_SUBJECT_ARTIFACT_ID, strict_id, integration_id},
                {row["artifact_id"] for row in writer_manifest["artifacts"]},
            )
            self.assertEqual(
                ["attach_artifact"],
                [row["op"] for row in writer_manifest["patch_contract"]["operation_templates"]],
            )

            referee_id = "paper-document-referee-report"
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
                            "artifact_id": referee_id,
                            "artifact_type": REFEREE_REPORT_ARTIFACT_TYPE,
                            "content": (
                                f"{AUDIT_WARNING_LINE}\n\n"
                                "# Verdict\n\nThe submitted proof has a major gap at Theorem 1, Step 2."
                            ),
                            "metadata": {
                                PAPER_AUDIT_REFEREE_REPORT_MARKER: True,
                                "strict_report_artifact_id": strict_id,
                                "integration_report_artifact_id": integration_id,
                                "source_artifact_ids": [
                                    AUDIT_SUBJECT_ARTIFACT_ID,
                                    strict_id,
                                    integration_id,
                                ],
                            },
                        }
                    ],
                    "rationale": "compose the final verifier-only referee report",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            stop_action = next_action(
                store,
                research_mode=PAPER_AUDIT_RESEARCH_MODE,
                web_search="disabled",
            )
            self.assertEqual("stop_solved", stop_action["mode"])
            self.assertEqual("paper_audit_complete", stop_action["terminal_classification"])
            self.assertEqual(referee_id, stop_action["final_artifact_id"])

            report = build_markdown_report(store)
            self.assertIn("The submitted proof has a major gap at Theorem 1, Step 2.", report)
            self.assertNotIn("### Proposed Repairs", report)


class PaperAuditContractTest(unittest.TestCase):
    def _prompt(self, actor_role: str, action: dict[str, Any] | None = None) -> str:
        base = {"mode": "reduce", "target_id": "root", "research_mode": PAPER_AUDIT_RESEARCH_MODE}
        base.update(action or {})
        return build_session_prompt(context_path=Path("/tmp/ctx.json"), action=base, actor_role=actor_role)

    def test_researcher_directive_carries_audit_contract(self) -> None:
        prompt = self._prompt("researcher")
        self.assertIn("PAPER SOLUTION AUDIT MODE", prompt)
        self.assertIn("paper_claim", prompt)
        self.assertIn("audit_status:<status>", prompt)
        self.assertIn("source_location:<section/theorem number/paragraph>", prompt)
        for status in AUDIT_CLAIM_STATUSES:
            self.assertIn(status, prompt)
        self.assertIn("no claim ever becomes 'checked' merely because the global proof sounds plausible", prompt)
        self.assertIn("proposed_repair", prompt)

    def test_villain_directive_hunts_hidden_hypotheses(self) -> None:
        prompt = self._prompt("villain", {"mode": "refute"})
        self.assertIn("hidden hypotheses", prompt)
        self.assertIn("notation mismatches", prompt)

    def test_verifier_directive_uses_bounded_packets(self) -> None:
        prompt = self._prompt("strict_informal_verifier", {"mode": "prove", "route_id": "r1"})
        self.assertIn("Verify one paper claim at a time", prompt)
        self.assertIn("proof_dossier attached by the researcher", prompt)
        self.assertIn("Never use proposed_repair artifacts as evidence", prompt)

    def test_verifier_only_document_directives_forbid_repair_and_packaging(self) -> None:
        prompt = self._prompt(
            "strict_informal_verifier",
            {
                "mode": "prove",
                "paper_audit_verification_only": True,
                "paper_audit_document_review_required": True,
            },
        )
        self.assertIn("VERIFIER-ONLY DOCUMENT REVIEW", prompt)
        self.assertIn("do not request proof_dossier packaging", prompt)
        self.assertIn("Attach exactly one verification_report", prompt)
        self.assertIn("Do not use errata", prompt)

    def test_verifier_only_integration_and_writer_directives_use_reports_only(self) -> None:
        integration_prompt = self._prompt(
            "integration_verifier",
            {
                "mode": "integrate",
                "paper_audit_verification_only": True,
                "paper_audit_document_integration_required": True,
                "strict_report_artifact_id": "strict-report-1",
            },
        )
        self.assertIn("VERIFIER-ONLY DEPENDENCY REVIEW", integration_prompt)
        self.assertIn("Attach exactly one integration_report", integration_prompt)
        self.assertIn("Do not repair or rewrite", integration_prompt)

        writer_prompt = self._prompt(
            "writer",
            {
                "mode": "write",
                "paper_audit_verification_only": True,
                "paper_audit_referee_report_required": True,
            },
        )
        self.assertIn("VERIFIER-ONLY FINAL REPORT", writer_prompt)
        self.assertIn("Attach exactly one referee_report", writer_prompt)
        self.assertIn("Include no proposed-repair section", writer_prompt)

    def test_researcher_directive_requires_normal_proof_route_packet(self) -> None:
        prompt = self._prompt("researcher")
        self.assertIn("attach one proof_dossier", prompt)
        self.assertIn("add one active sufficient route", prompt)
        self.assertIn("add a terminal plausible inference", prompt)
        self.assertIn("premise_claim_ids", prompt)

    def test_integration_directive_checks_verified_paper_dependencies(self) -> None:
        prompt = self._prompt("integration_verifier", {"mode": "integrate", "route_id": "paper-route-1"})
        self.assertIn("run only after strict local verification", prompt)
        self.assertIn("complete paper dependency route", prompt)
        self.assertIn("integrates=false", prompt)
        self.assertIn("Integration never repairs or rewrites", prompt)

    def test_librarian_directive_requires_exact_citation_checks(self) -> None:
        prompt = self._prompt("literature_researcher", {"mode": "retrieve"})
        self.assertIn("theorem/proposition number or page/section", prompt)
        self.assertIn("citation_needed", prompt)

    def test_writer_directive_is_referee_report_not_polished_proof(self) -> None:
        prompt = self._prompt("writer", {"mode": "write"})
        self.assertIn("REFEREE-STYLE AUDIT REPORT", prompt)
        self.assertIn("referee_report", prompt)
        self.assertIn("appears_correct_modulo_minor_details | major_gaps | not_verified | likely_false", prompt)
        self.assertIn("Do not write a final_proof or final_paper in this mode.", prompt)
        self.assertIn(AUDIT_WARNING_LINE, prompt)

    def test_default_mode_has_no_audit_prefix(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/ctx.json"),
            action={"mode": "reduce", "target_id": "root", "research_mode": "hard_problem"},
            actor_role="researcher",
        )
        self.assertNotIn("PAPER SOLUTION AUDIT MODE", prompt)

    def test_manifest_carries_audit_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-manifest-test")
            manifest = build_context_manifest(store, max_chars=40_000)
            card = manifest["paper_audit"]
            self.assertEqual(AUDIT_SUBJECT_ARTIFACT_ID, card["audit_subject_artifact_id"])
            self.assertEqual(list(AUDIT_CLAIM_STATUSES), card["status_vocabulary"])
            self.assertIn("referee-style audit report", card["deliverable"])
            self.assertEqual(
                ["researcher_packet", "strict_informal_verifier", "integration_verifier"],
                card["verification_pipeline"]["stages"],
            )
            self.assertIn(
                card["audit_subject_path"],
                manifest["local_search_policy"]["allowed_local_evidence_paths"],
            )
            self.assertTrue(any("paper_solution_audit" in line for line in manifest["instructions"]))


class PaperAuditVerificationPipelineTest(unittest.TestCase):
    def test_strict_verifier_packet_excludes_sibling_audit_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-strict-packet-isolation-test")
            apply_audit_proof_packet(store)
            apply_unrelated_audit_finding(store)
            action = {
                "mode": "prove",
                "target_id": "paper-theorem-1",
                "route_id": "paper-route-1",
                "research_mode": PAPER_AUDIT_RESEARCH_MODE,
                "verify_ready_route_policy": True,
                "strict_verifier_scope": "single_route_verification_packet",
                "strict_verifier_no_fresh_evidence": True,
                "verifier_evidence_artifact_ids": ["paper-proof-packet-1"],
            }

            manifest = build_context_manifest(
                store,
                target_id="paper-theorem-1",
                route_id="paper-route-1",
                action=action,
                max_chars=100_000,
            )

            self.assertEqual(
                {AUDIT_SUBJECT_ARTIFACT_ID, "paper-proof-packet-1"},
                {artifact["artifact_id"] for artifact in manifest["artifacts"]},
            )
            self.assertEqual([], manifest["debts"])
            self.assertEqual([], manifest["retrieval_cards"])
            self.assertEqual([], manifest["theorem_library"])
            self.assertEqual(
                ["paper-proof-packet-1"],
                [
                    artifact["artifact_id"]
                    for artifact in manifest["verification_packet"]["proof_artifacts"]
                ],
            )
            self.assertEqual([], manifest["verification_packet"]["active_debts"])
            serialized = json.dumps(manifest, sort_keys=True)
            self.assertNotIn("unrelated-counterexample-1", serialized)
            self.assertNotIn("unrelated-counterexample-debt", serialized)
            self.assertIn(
                manifest["paper_audit"]["audit_subject_path"],
                manifest["local_search_policy"]["allowed_local_evidence_paths"],
            )

    def test_researcher_packet_still_schedules_route_verifiers_outside_terminal_audit_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-verification-pipeline-test")
            apply_audit_proof_packet(store)

            strict_action = next_action(
                store,
                research_mode="hard_problem",
                web_search="disabled",
            )
            self.assertEqual("prove", strict_action["mode"])
            self.assertEqual("paper-theorem-1", strict_action["target_id"])
            self.assertEqual("paper-route-1", strict_action["route_id"])
            self.assertEqual("strict_informal_verifier", actor_role_for_action(strict_action))

            with store.connect() as conn:
                conn.execute(
                    "UPDATE claims SET validation_status='informally_verified' "
                    "WHERE claim_id IN ('paper-theorem-1', 'paper-theorem-1-hypothesis')"
                )
                conn.execute(
                    "UPDATE inferences SET validation_status='informally_verified' "
                    "WHERE inference_id='paper-inference-1'"
                )
                conn.commit()

            integration_action = next_action(
                store,
                research_mode="hard_problem",
                web_search="disabled",
            )
            self.assertEqual("integrate", integration_action["mode"])
            self.assertEqual("paper-theorem-1", integration_action["target_id"])
            self.assertEqual("paper-route-1", integration_action["route_id"])
            self.assertEqual("integration_verifier", actor_role_for_action(integration_action))


class PaperAuditGapFixtureTest(unittest.TestCase):
    def test_known_hidden_gap_recorded_as_gap_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-gap-fixture-test")
            apply_audit_claims(store)
            state = store.get_state()

            claims = paper_claims(state)
            self.assertEqual(3, len(claims))
            gap = next(row for row in claims if row["claim_id"] == "paper-step-2")
            self.assertEqual("gap", gap["audit_status"])
            self.assertEqual("Theorem 1, Step 2", gap["source_location"])
            self.assertEqual("challenged", gap["validation_status"])
            self.assertEqual("major_gaps", audit_confidence_summary(state))

    def test_confidence_summary_is_conservative(self) -> None:
        def state_with(statuses: list[str]) -> dict[str, Any]:
            claims = [
                {
                    "claim_id": f"c{i}",
                    "statement": f"claim {i}",
                    "validation_status": "plausible",
                    "lifecycle_status": "active",
                    "tags_json": json.dumps(["paper_claim", f"audit_status:{status}", "source_location:S"]),
                }
                for i, status in enumerate(statuses)
            ]
            return {
                "claims": claims,
                "artifacts": [{"artifact_id": "a", "artifact_type": AUDIT_SUBJECT_ARTIFACT_TYPE, "metadata_json": "{}"}],
            }

        self.assertEqual("not_verified", audit_confidence_summary(state_with([])))
        self.assertEqual("not_verified", audit_confidence_summary(state_with(["needs_detail", "probably_correct"])))
        self.assertEqual("not_verified", audit_confidence_summary(state_with(["checked", "needs_detail"])))
        self.assertEqual("major_gaps", audit_confidence_summary(state_with(["checked", "gap"])))
        self.assertEqual("major_gaps", audit_confidence_summary(state_with(["checked", "overclaim"])))
        self.assertEqual(
            "likely_false",
            audit_confidence_summary(state_with(["checked", "gap", "false_or_counterexample_risk"])),
        )

        verified = state_with(["checked", "checked"])
        for claim in verified["claims"]:
            claim["validation_status"] = "informally_verified"
            claim["lifecycle_status"] = "integrated"
        self.assertEqual("appears_correct_modulo_minor_details", audit_confidence_summary(verified))

        refuted = state_with(["probably_correct"])
        refuted["claims"][0]["validation_status"] = "refuted"
        self.assertEqual("likely_false", audit_confidence_summary(refuted))


class RefereeReportRenderingTest(unittest.TestCase):
    def test_report_renders_referee_sections_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-report-test")
            apply_audit_claims(store)
            report = build_markdown_report(store)

        self.assertIn("## Referee Audit Report", report)
        self.assertIn("AI audit, not a formal proof", report)
        self.assertIn("### Claim Map", report)
        self.assertIn(
            "`paper-step-2` `gap` strict=`challenged` integration=`active` (Theorem 1, Step 2)",
            report,
        )
        self.assertIn("### Gap List", report)
        self.assertIn("### Citation Audit", report)
        self.assertIn("`paper-step-3`", report)
        self.assertIn("### Overclaim Report", report)
        self.assertIn("### Local Correctness Report", report)
        self.assertIn("### Proposed Repairs (separate from the audit verdict)", report)
        self.assertIn("`repair-abelian-hypothesis`", report)
        self.assertIn("Confidence summary (conservative): `major_gaps`", report)

    def test_non_audit_report_has_no_referee_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("non-audit-report-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Prove the root theorem.")
            report = build_markdown_report(store)
        self.assertNotIn("Referee Audit Report", report)

    def test_referee_lines_for_bare_audit_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-bare-report-test")
            lines = build_referee_report_lines(store.get_state())
        text = "\n".join(lines)
        self.assertIn("No paper claims recorded yet", text)
        self.assertIn("`not_verified`", text)
        self.assertIn(AUDIT_WARNING_LINE, text)


if __name__ == "__main__":
    unittest.main()
