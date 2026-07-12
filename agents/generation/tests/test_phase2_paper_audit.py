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
    PAPER_AUDIT_RESEARCH_MODE,
    audit_confidence_summary,
    build_referee_report_lines,
    ingest_paper_audit,
    is_audit_state,
    is_paper_audit_mode,
    paper_claims,
)
from agents.generation.phase2.codex_runner import build_session_prompt
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
from agents.generation.phase2.scheduler import next_action
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
        self.assertIn("one paper claim or one proof segment at a time", prompt)

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
            self.assertTrue(any("paper_solution_audit" in line for line in manifest["instructions"]))


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
        self.assertEqual(
            "appears_correct_modulo_minor_details",
            audit_confidence_summary(state_with(["checked", "needs_detail"])),
        )
        self.assertEqual("major_gaps", audit_confidence_summary(state_with(["checked", "gap"])))
        self.assertEqual("major_gaps", audit_confidence_summary(state_with(["checked", "overclaim"])))
        self.assertEqual(
            "likely_false",
            audit_confidence_summary(state_with(["checked", "gap", "false_or_counterexample_risk"])),
        )


class RefereeReportRenderingTest(unittest.TestCase):
    def test_report_renders_referee_sections_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ingest_fixture(Path(tmpdir), "audit-report-test")
            apply_audit_claims(store)
            report = build_markdown_report(store)

        self.assertIn("## Referee Audit Report", report)
        self.assertIn("AI audit, not a formal proof", report)
        self.assertIn("### Claim Map", report)
        self.assertIn("`paper-step-2` `gap` (Theorem 1, Step 2)", report)
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
