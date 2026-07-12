from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.console import build_run_console_payload
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.receipt import format_receipt_latex
from agents.generation.phase2.report import build_markdown_report
from agents.generation.phase2.store import ProofStateStore


def add_debt_patch(*, problem_id: str, base_revision: int, debt_id: str, obligation: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": problem_id,
        "base_revision": base_revision,
        "actor_role": "strict_informal_verifier",
        "target_id": "root",
        "operations": [
            {
                "op": "add_debt",
                "debt_id": debt_id,
                "owner_type": "claim",
                "owner_id": "root",
                "debt_type": "gap",
                "severity": "blocking",
                "status": "active",
                "obligation": obligation,
                "suggested_next_target": "root",
            }
        ],
        "rationale": "test debt patch",
    }


class Phase2PatchDebtTest(unittest.TestCase):
    def test_interrogative_root_cannot_be_marked_refuted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-question-root-refutation-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Does an absolute bound exist? Find its minimum value.")
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
                            "artifact_id": "confirmed-lower-bound-example",
                            "artifact_type": "confirmed_counterexample",
                            "content": "The checked example rules out the proposed bound two.",
                            "metadata": {"confirmed": True, "failed_hypothesis": "k is at most two"},
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "refuted",
                            "confirmed_root_counterexample": True,
                            "evidence_artifact_ids": ["confirmed-lower-bound-example"],
                        },
                    ],
                    "rationale": "incorrectly treat lower-bound evidence as refuting a question",
                },
            )

        self.assertFalse(outcome.accepted)
        self.assertTrue(any("interrogative root problem" in error for error in outcome.errors))

    def test_debt_sources_drop_retrieval_card_ids_from_literature_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-debt-retrieval-card-source-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")
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
                            "card_id": "retrieval-source-card",
                            "target_id": "root",
                            "exact_statement": "A useful source theorem.",
                            "source_identifiers": {"arxiv": "arXiv:0000.00001"},
                            "source_version": "arXiv:0000.00001",
                            "source_location": "Theorem 1",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {"classification": "partial_match"},
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "source-adaptation",
                            "artifact_type": "source_adaptation_notes",
                            "content": "The source almost applies, but one hypothesis remains.",
                            "metadata": {"retrieval_card_id": "retrieval-source-card"},
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-source-card-mixed",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "missing_hypothesis",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Certify the remaining source hypothesis.",
                            "source_artifact_ids": ["retrieval-source-card", "source-adaptation"],
                            "suggested_next_target": "root",
                        },
                    ],
                    "rationale": "record partial source match",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT source_artifact_ids_json FROM debts WHERE debt_id = 'debt-source-card-mixed'").fetchone()

            self.assertEqual(json.loads(row["source_artifact_ids_json"]), ["source-adaptation"])

    def test_debt_severity_high_is_normalized_to_major(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-debt-high-severity-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")
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
                            "op": "add_debt",
                            "debt_id": "debt-high-severity",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "high",
                            "status": "open",
                            "obligation": "Bridge a useful source to the target.",
                            "suggested_next_target": "root",
                        }
                    ],
                    "rationale": "record literature gap",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT severity FROM debts WHERE debt_id = 'debt-high-severity'").fetchone()

            self.assertEqual(row["severity"], "major")

    def test_strict_verifier_cannot_attach_fresh_proof_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-strict-verifier-artifact-boundary-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")
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
                            "op": "attach_artifact",
                            "artifact_id": "verifier-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "The verifier tries to create new proof evidence.",
                        }
                    ],
                    "rationale": "strict verifier overstepped its role",
                },
            )

        self.assertFalse(outcome.accepted)
        self.assertIn("strict_informal_verifier cannot attach proof_dossier", outcome.errors[0])

    def test_console_usage_summary_combines_stopped_and_current_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-usage-summary-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem", total_token_budget=10_000)
            artifact_dir = store.state_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "stored-note.txt").write_text("abc", encoding="utf-8")

            prior = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "prior-stopped-run",
                            "actor_role": "researcher",
                            "mode": "prove",
                            "target_id": "root",
                            "state_revision": 0,
                            "context_revision": 0,
                            "input_tokens": 1,
                            "cached_input_tokens": 1,
                            "output_tokens": 2,
                            "reasoning_output_tokens": 3,
                            "total_tokens": 123,
                            "wall_time_seconds": 7.5,
                            "peak_memory_mb": 111.5,
                            "status": "completed",
                        }
                    ],
                    "rationale": "record prior stopped usage",
                },
            )
            self.assertTrue(prior.accepted, prior.errors)

            current = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "scheduler",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "current-run",
                            "actor_role": "researcher",
                            "mode": "reduce",
                            "target_id": "root",
                            "state_revision": store.get_revision(),
                            "context_revision": store.get_revision(),
                            "input_tokens": 4,
                            "output_tokens": 5,
                            "total_tokens": 456,
                            "wall_time_seconds": 8.5,
                            "peak_memory_mb": 222.5,
                            "status": "completed",
                        }
                    ],
                    "rationale": "record current usage",
                },
            )
            self.assertTrue(current.accepted, current.errors)

            payload = build_run_console_payload(
                store,
                history=[{"action_results": [{"execution": {"run_id": "current-run"}}]}],
            )
            usage = payload["usage_summary"]
            self.assertEqual(usage["total_recorded"]["total_tokens"], 579)
            self.assertEqual(usage["total_recorded"]["cached_input_tokens"], 1)
            self.assertNotIn("prior_stopped_carryover", usage)
            self.assertNotIn("current_invocation", usage)
            self.assertEqual(usage["total_recorded"]["peak_memory_mb"], 222.5)
            self.assertGreaterEqual(payload["storage_summary"]["stored_memory_artifacts_bytes"], 3)

            report = build_markdown_report(store)
            self.assertIn("## Benchmark Quantitative Snapshot", report)
            self.assertNotIn("## Continuation Accounting", report)
            self.assertNotIn("Prior/stopped carry-over", report)
            self.assertIn("| Stored memory artifacts |", report)
            self.assertIn("| Reported tokens | 579 |", report)

    def test_console_verifier_audit_counts_report_artifacts_without_run_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-console-verifier-audit-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")
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
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the proof dossier.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "validation_status": "plausible",
                            "explanation": "The dossier proves the root.",
                        },
                    ],
                    "rationale": "seed route",
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
                            "artifact_id": "vr-root-ok",
                            "artifact_type": "verification_report",
                            "content": "verdict: informally_verified\ncritical_errors: []\ngaps: []",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {"critical_errors": [], "gaps": [], "blocking_gap": False},
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["vr-root-ok"],
                        },
                    ],
                    "rationale": "verify route inference without a workflow run row",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            payload = build_run_console_payload(store)
            audit = payload["verifier_audit"]

        self.assertEqual(audit["verifier_run_count"], 0)
        self.assertEqual(audit["strict_verifier_report_count"], 1)
        self.assertEqual(audit["strict_verifier_report_artifact_ids"], ["vr-root-ok"])
        self.assertEqual(audit["verified_inference_count"], 1)

    def test_console_verifier_audit_separates_failed_launches_from_zero_token_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-console-verifier-launch-health-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")
            recorded = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "record_run_metrics",
                            "run_id": "verifier-failed-before-sampling",
                            "actor_role": "strict_informal_verifier",
                            "mode": "prove",
                            "target_id": "root",
                            "status": "failed",
                            "total_tokens": 0,
                            "output_artifact_ids": [],
                            "error_artifact_id": "session_failure_verifier-failed-before-sampling",
                        },
                    ],
                    "rationale": "record failed verifier launch",
                },
            )
            self.assertTrue(recorded.accepted, recorded.errors)

            payload = build_run_console_payload(store)
            audit = payload["verifier_audit"]

        self.assertEqual(audit["zero_token_verifier_runs"], [])
        self.assertEqual(audit["failed_verifier_launches"], ["verifier-failed-before-sampling"])
        self.assertEqual(audit["warnings"], [])

    def test_add_artifact_operation_alias_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-add-artifact-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "op": "add_artifact",
                            "artifact": {
                                "artifact_id": "alias-proof-dossier",
                                "artifact_type": "proof_dossier",
                                "metadata": {"target_id": "root"},
                                "content": "Alias artifact content.",
                            },
                        }
                    ],
                    "rationale": "agent emitted add_artifact alias",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT artifact_type, path, metadata_json FROM artifacts WHERE artifact_id = ?",
                    ("alias-proof-dossier",),
                ).fetchone()
            self.assertEqual(row[0], "proof_dossier")
            self.assertIn("Alias artifact content.", Path(row[1]).read_text(encoding="utf-8"))
            self.assertEqual(json.loads(row[2])["target_id"], "root")

    def test_nested_attach_artifact_operation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-nested-attach-artifact-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact": {
                                "artifact_id": "nested-proof-dossier",
                                "artifact_type": "proof_dossier",
                                "metadata": {"target_id": "root", "route_id": "route-root"},
                                "content": {
                                    "summary": "Nested attach artifact content.",
                                    "status_request": "send to verifier",
                                },
                            },
                        }
                    ],
                    "rationale": "agent emitted nested attach_artifact payload",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT artifact_type, path, metadata_json FROM artifacts WHERE artifact_id = ?",
                    ("nested-proof-dossier",),
                ).fetchone()
            self.assertEqual(row[0], "proof_dossier")
            content = Path(row[1]).read_text(encoding="utf-8")
            self.assertIn('"summary": "Nested attach artifact content."', content)
            metadata = json.loads(row[2])
            self.assertEqual(metadata["target_id"], "root")
            self.assertEqual(metadata["route_id"], "route-root")

    def test_bare_artifact_operation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-bare-artifact-operation-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "bare-advisor-report",
                            "artifact_type": "advisor_report",
                            "content": "Advisor report without an explicit op.",
                            "metadata": {"target_id": "root", "advisor_followup_required": True},
                        }
                    ],
                    "rationale": "agent emitted a bare artifact operation",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT artifact_type, path, producer_role FROM artifacts WHERE artifact_id = ?",
                    ("bare-advisor-report",),
                ).fetchone()
            self.assertEqual(row[0], "advisor_report")
            self.assertEqual(row[2], "phd_advisor")
            self.assertIn("Advisor report", Path(row[1]).read_text(encoding="utf-8"))

    def test_attach_artifact_missing_id_gets_deterministic_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-derived-artifact-id-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_type": "advisor_report",
                            "title": "Post-integration proof spine compression",
                            "content": "Compress the proof spine and send one theorem-level task.",
                            "metadata": {"target_id": "root", "advisor_followup_required": True},
                        }
                    ],
                    "rationale": "agent omitted an artifact id",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT artifact_id, artifact_type, path FROM artifacts WHERE producer_role = ?",
                    ("phd_advisor",),
                ).fetchone()
            self.assertTrue(row[0].startswith("art_auto_phd_advisor_root_advisor_report_"))
            self.assertEqual(row[1], "advisor_report")
            self.assertIn("Compress the proof spine", Path(row[2]).read_text(encoding="utf-8"))

    def test_nested_add_claim_operation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-nested-add-claim-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "claim": {
                                "claim_id": "nested-local-lemma",
                                "kind": "lemma",
                                "statement": "A useful local lemma.",
                                "parent_ids": ["root"],
                                "validation_status": "untested",
                                "lifecycle_status": "active",
                                "root_impact": 0.4,
                                "reduction_depth": 1,
                                "tags": ["local"],
                            },
                        }
                    ],
                    "rationale": "agent emitted nested add_claim payload",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT kind, statement, parent_ids_json, tags_json FROM claims WHERE claim_id = ?",
                    ("nested-local-lemma",),
                ).fetchone()
            self.assertEqual(row[0], "lemma")
            self.assertEqual(row[1], "A useful local lemma.")
            self.assertEqual(json.loads(row[2]), ["root"])
            self.assertEqual(json.loads(row[3]), ["local"])

    def test_failed_proof_dossier_does_not_auto_route_theorem_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-failed-proof-auto-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "claim_id": "lemma-failed-proof",
                            "kind": "lemma",
                            "statement": "A lemma whose attempted proof failed.",
                            "parent_ids": ["root"],
                            "root_impact": 0.5,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "label": "root route",
                            "strategy": "prove root",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "failed-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "Failed proof: this does not prove the lemma and is not verifier-ready.",
                            "metadata": {"target_id": "lemma-failed-proof"},
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-failed-proof",
                            "route_id": "route-root",
                            "conclusion_claim_id": "lemma-failed-proof",
                            "premise_claim_ids": [],
                            "validation_status": "untested",
                            "explanation": "Attempted proof failed.",
                            "evidence_artifact_ids": ["failed-proof-dossier"],
                        },
                    ],
                    "rationale": "failed proof should not be auto-routed",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                route = conn.execute("SELECT 1 FROM routes WHERE route_id = 'route-auto-lemma-failed-proof'").fetchone()
                inference_route = conn.execute(
                    "SELECT route_id FROM inferences WHERE inference_id = 'inf-failed-proof'"
                ).fetchone()[0]
            self.assertIsNone(route)
            self.assertEqual(inference_route, "route-root")

    def test_obstruction_evidence_auto_routes_obstruction_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-obstruction-auto-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "claim_id": "obs-root",
                            "kind": "obstruction",
                            "statement": "A structural obstruction threatens the root route.",
                            "parent_ids": ["root"],
                            "root_impact": 0.8,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "label": "root route",
                            "strategy": "prove root",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "route-obstruction-report",
                            "artifact_type": "route_obstruction",
                            "content": "Proof of a necessary obstruction condition.",
                            "metadata": {"target_id": "root"},
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-obs-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "obs-root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The obstruction follows from the report.",
                            "evidence_artifact_ids": ["route-obstruction-report"],
                        },
                    ],
                    "rationale": "obstruction proof should be routed for verification",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                route = conn.execute(
                    "SELECT conclusion_claim_id, strategy FROM routes WHERE route_id = 'route-auto-obs-root'"
                ).fetchone()
                inference_route = conn.execute(
                    "SELECT route_id FROM inferences WHERE inference_id = 'inf-obs-root'"
                ).fetchone()[0]
            self.assertEqual(route[0], "obs-root")
            self.assertEqual(route[1], "auto_assembled_from_dossier")
            self.assertEqual(inference_route, "route-auto-obs-root")

    def test_nested_add_route_operation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-nested-add-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "claim_id": "nested-route-claim",
                            "kind": "lemma",
                            "statement": "A route target claim.",
                            "parent_ids": ["root"],
                            "root_impact": 0.4,
                            "reduction_depth": 1,
                        }
                    ],
                    "rationale": "claim setup",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)

            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route": {
                                "route_id": "nested-route",
                                "conclusion_claim_id": "nested-route-claim",
                                "label": "nested route",
                                "strategy": "Use the nested route payload.",
                                "relation_to_parent": "sufficient",
                                "status": "active",
                                "evidence_artifact_ids": [],
                            },
                        }
                    ],
                    "rationale": "agent emitted nested route payload",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT label, strategy, relation_to_parent FROM routes WHERE route_id = ?",
                    ("nested-route",),
                ).fetchone()
            self.assertEqual(row[0], "nested route")
            self.assertEqual(row[1], "Use the nested route payload.")
            self.assertEqual(row[2], "sufficient")

    def test_route_and_inference_target_claim_aliases_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-target-claim-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "claim_id": "alias-target",
                            "kind": "lemma",
                            "statement": "A schedulable obstruction lemma.",
                            "parent_ids": ["root"],
                            "root_impact": 0.5,
                            "reduction_depth": 1,
                        }
                    ],
                    "rationale": "claim setup",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)

            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-alias-target",
                            "target_claim_id": "alias-target",
                            "proof_obligation": "Check the obstruction proof.",
                            "evidence_artifact_ids": [],
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-alias-target",
                            "route_id": "route-alias-target",
                            "target_claim_id": "alias-target",
                            "premise_claim_ids": [],
                            "validation_status": "untested",
                            "argument_summary": "The obstruction follows from the dossier.",
                            "evidence_artifact_ids": [],
                        },
                    ],
                    "rationale": "agent used target_claim_id alias",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                route = conn.execute(
                    "SELECT conclusion_claim_id, strategy FROM routes WHERE route_id = ?",
                    ("route-alias-target",),
                ).fetchone()
                inference = conn.execute(
                    "SELECT conclusion_claim_id, explanation FROM inferences WHERE inference_id = ?",
                    ("inf-alias-target",),
                ).fetchone()
            self.assertEqual(route[0], "alias-target")
            self.assertEqual(route[1], "Check the obstruction proof.")
            self.assertEqual(inference[0], "alias-target")
            self.assertEqual(inference[1], "The obstruction follows from the dossier.")

    def test_structured_artifact_content_metadata_is_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-content-metadata-promotion-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "op": "attach_artifact",
                            "artifact_id": "structured-source-notes",
                            "artifact_type": "source_adaptation_notes",
                            "content": {
                                "metadata": {"target_id": "root", "route_id": "route-root"},
                                "adaptation": "Use the cited theorem for the height-one route.",
                            },
                        }
                    ],
                    "rationale": "agent put scheduling metadata in structured content",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT metadata_json FROM artifacts WHERE artifact_id = ?",
                    ("structured-source-notes",),
                ).fetchone()
            metadata = json.loads(row[0])
            self.assertEqual(metadata["target_id"], "root")
            self.assertEqual(metadata["route_id"], "route-root")

    def test_flat_add_artifact_operation_alias_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-flat-add-artifact-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "op": "add_artifact",
                            "artifact_id": "flat-alias-counterexample",
                            "artifact_type": "candidate_counterexample",
                            "metadata": {"target_id": "root"},
                            "content": "Flat alias artifact content.",
                        }
                    ],
                    "rationale": "agent emitted flat add_artifact alias",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT artifact_type, path, metadata_json FROM artifacts WHERE artifact_id = ?",
                    ("flat-alias-counterexample",),
                ).fetchone()
            self.assertEqual(row[0], "candidate_counterexample")
            self.assertIn("Flat alias artifact content.", Path(row[1]).read_text(encoding="utf-8"))
            self.assertEqual(json.loads(row[2])["target_id"], "root")

    def test_nested_add_debt_operation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-nested-debt-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "debt": {
                                "debt_id": "nested-root-gap",
                                "owner_type": "claim",
                                "owner_id": "root",
                                "debt_type": "gap",
                                "severity": "blocking",
                                "status": "active",
                                "obligation": "Nested debt content must be recorded.",
                                "suggested_next_target": "root",
                            },
                        }
                    ],
                    "rationale": "agent emitted nested debt payload",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute("SELECT obligation FROM debts WHERE debt_id = ?", ("nested-root-gap",)).fetchone()
            self.assertEqual(row[0], "Nested debt content must be recorded.")

    def test_add_debt_can_reference_route_added_later_in_same_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-forward-route-debt-owner-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "op": "add_debt",
                            "debt_id": "route-gap",
                            "owner_type": "route",
                            "owner_id": "route-later",
                            "debt_type": "missing_hypothesis",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Route still needs a compatibility lemma.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-later",
                            "conclusion_claim_id": "root",
                            "label": "Route added after its debt",
                            "status": "active",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use a later-added route owner.",
                        },
                    ],
                    "rationale": "agent emitted route debt before the route operation",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute("SELECT owner_type, owner_id FROM debts WHERE debt_id = ?", ("route-gap",)).fetchone()
            self.assertEqual(("route", "route-later"), tuple(row))

    def test_nested_add_inference_operation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-nested-inference-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "op": "add_route",
                            "route_id": "route-root-proof",
                            "conclusion_claim_id": "root",
                            "strategy": "direct proof",
                            "status": "active",
                        }
                    ],
                    "rationale": "route setup",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)

            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_inference",
                            "inference": {
                                "inference_id": "nested-root-inference",
                                "route_id": "route-root-proof",
                                "conclusion_claim_id": "root",
                                "premise_claim_ids": [],
                                "condition_claim_ids": [],
                                "conditions": ["The local hypotheses hold."],
                                "evidence_artifact_ids": [],
                                "explanation": "Nested inference content must be recorded.",
                                "validation_status": "plausible",
                            },
                        }
                    ],
                    "rationale": "agent emitted nested inference payload",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT explanation, validation_status FROM inferences WHERE inference_id = ?",
                    ("nested-root-inference",),
                ).fetchone()
            self.assertEqual(row[0], "Nested inference content must be recorded.")
            self.assertEqual(row[1], "plausible")

    def test_operation_type_retrieval_card_alias_is_normalized_before_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-retrieval-card-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "operation_type": "cache_retrieval_card",
                            "retrieval_card_id": "retrieval-no-useful-result",
                            "target_id": "root",
                            "exact_statement": "No useful theorem was found in the allowed local scope.",
                            "source_identifiers": {"title": "Local source"},
                            "hypotheses": [],
                            "local_definitions": {},
                            "applicability": {"classification": "no_useful_result_found"},
                            "missing_hypotheses": ["missing compatibility theorem"],
                            "source_location": "local files",
                            "source_version": "test",
                            "content_hash": "hash-retrieval-no-useful-result",
                        }
                    ],
                    "rationale": "agent emitted retrieval card aliases",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT exact_statement FROM retrieval_cards WHERE card_id = ?",
                    ("retrieval-no-useful-result",),
                ).fetchone()
            self.assertEqual(row[0], "No useful theorem was found in the allowed local scope.")

    def test_retrieval_card_artifact_id_alias_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-retrieval-card-artifact-id-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "retrieval-card-from-artifact-id",
                            "target_id": "root",
                            "exact_statement": "A theorem matches the requested local construction.",
                            "source_identifiers": {"title": "Source"},
                            "source_version": "test",
                            "source_location": "Lemma 1",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {"classification": "direct_match"},
                        }
                    ],
                    "rationale": "agent used artifact_id for retrieval card id",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT exact_statement FROM retrieval_cards WHERE card_id = ?",
                    ("retrieval-card-from-artifact-id",),
                ).fetchone()
            self.assertEqual(row[0], "A theorem matches the requested local construction.")

    def test_retrieval_card_empty_sha256_content_hash_is_rejected(self) -> None:
        empty_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        for content_hash in (empty_sha, {"pdf_sha256": empty_sha, "text_sha256": "abc123"}):
            with self.subTest(content_hash=content_hash):
                with tempfile.TemporaryDirectory() as tmpdir:
                    store = ProofStateStore("patch-empty-retrieval-hash-test", generation_root=Path(tmpdir) / "generation")
                    store.init_problem("prove the root theorem")

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
                                    "card_id": "empty-hash-card",
                                    "exact_statement": "A source theorem was allegedly retrieved.",
                                    "source_identifiers": {"title": "Source"},
                                    "source_version": "test",
                                    "source_location": "PDF",
                                    "hypotheses": [],
                                    "local_definitions": [],
                                    "missing_hypotheses": [],
                                    "applicability": {"classification": "method_match"},
                                    "content_hash": content_hash,
                                }
                            ],
                            "rationale": "agent supplied an empty download hash",
                        },
                    )

                    self.assertFalse(outcome.accepted)
                    self.assertIn("SHA-256 of empty content", outcome.errors[0])

    def test_nested_retrieval_card_operation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-nested-retrieval-card-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "card": {
                                "card_id": "retrieval-nested-card",
                                "exact_statement": "A cited theorem directly closes the construction debt.",
                                "source_identifiers": {"author": "A. Mathematician", "title": "A useful theorem"},
                                "source_version": "test",
                                "source_location": "Corollary 2.4",
                                "hypotheses": ["hypothesis checked"],
                                "local_definitions": [],
                                "missing_hypotheses": [],
                                "applicability": {
                                    "classification": "direct_match",
                                    "target_id": "root",
                                    "program_victory_candidate": True,
                                },
                            },
                            "query": "prescribed generic formal fiber",
                        }
                    ],
                    "rationale": "agent emitted nested retrieval card payload",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT normalized_query, exact_statement, applicability_json FROM retrieval_cards WHERE card_id = ?",
                    ("retrieval-nested-card",),
                ).fetchone()
            self.assertEqual(row[0], "prescribed generic formal fiber")
            self.assertEqual(row[1], "A cited theorem directly closes the construction debt.")
            self.assertTrue(json.loads(row[2])["program_victory_candidate"])

    def test_operation_alias_is_normalized_before_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-operation-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "operation": "attach_artifact",
                            "artifact_id": "operation-alias-dossier",
                            "artifact_type": "proof_dossier",
                            "metadata": {"target_id": "root"},
                            "content": "Operation alias artifact content.",
                        }
                    ],
                    "rationale": "agent emitted operation alias",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT artifact_type, path FROM artifacts WHERE artifact_id = ?",
                    ("operation-alias-dossier",),
                ).fetchone()
            self.assertEqual(row[0], "proof_dossier")
            self.assertIn("Operation alias artifact content.", Path(row[1]).read_text(encoding="utf-8"))

    def test_operation_name_alias_is_normalized_before_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-operation-name-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "operation_name": "attach_artifact",
                            "artifact": {
                                "artifact_id": "operation-name-alias-report",
                                "artifact_type": "route_triage_report",
                                "metadata": {"target_id": "root"},
                                "content": "Operation-name alias artifact content.",
                            },
                        }
                    ],
                    "rationale": "agent emitted operation_name alias",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT artifact_type, path FROM artifacts WHERE artifact_id = ?",
                    ("operation-name-alias-report",),
                ).fetchone()
            self.assertEqual(row[0], "route_triage_report")
            self.assertIn("Operation-name alias artifact content.", Path(row[1]).read_text(encoding="utf-8"))

    def test_structured_artifact_content_is_written_to_store_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-structured-artifact-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "structured-diagnostic",
                            "artifact_type": "research_diagnostic",
                            "content": {
                                "summary": "Structured content must be serialized.",
                                "checks": ["finite examples", "quotient obstruction"],
                            },
                        }
                    ],
                    "rationale": "structured artifact regression",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT path, content_summary FROM artifacts WHERE artifact_id = 'structured-diagnostic'").fetchone()
            self.assertTrue(row["path"])
            content = Path(row["path"]).read_text(encoding="utf-8")
            self.assertIn('"summary": "Structured content must be serialized."', content)
            self.assertIn("finite examples", content)
            self.assertTrue(content.endswith("\n"))
            self.assertIn("Structured content must be serialized.", row["content_summary"])

    def test_retrieval_card_accepts_prose_applicability(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-retrieval-prose-applicability-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "card_id": "card-prose-applicability",
                            "target_id": "root",
                            "exact_statement": "A theorem covers a useful subcase.",
                            "source_identifiers": ["Example Source"],
                            "source_version": "v1",
                            "source_location": "Section 1",
                            "hypotheses": ["subcase hypothesis"],
                            "local_definitions": [],
                            "missing_hypotheses": ["root hypothesis"],
                            "applicability": "Useful partial match but not the root theorem.",
                        }
                    ],
                    "rationale": "prose applicability regression",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT applicability_json FROM retrieval_cards WHERE card_id = 'card-prose-applicability'").fetchone()
            applicability = json.loads(row["applicability_json"])
            self.assertEqual(applicability["notes"], "Useful partial match but not the root theorem.")
            self.assertIn("classification", applicability)

    def test_verifier_can_verify_direct_citation_inference_without_premises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-direct-citation-verifier-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "claim_id": "claim_direct_citation",
                            "kind": "theorem",
                            "statement": "A cited theorem proves this side claim directly.",
                            "validation_status": "plausible",
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route_direct_citation",
                            "conclusion_claim_id": "claim_direct_citation",
                            "label": "direct citation",
                            "strategy": "Apply the cited theorem directly.",
                            "relation_to_parent": "sufficient",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf_direct_citation",
                            "route_id": "route_direct_citation",
                            "conclusion_claim_id": "claim_direct_citation",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The cited theorem directly gives the claim.",
                        },
                    ],
                    "rationale": "set up a direct citation route",
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
                    "target_id": "claim_direct_citation",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "vr_direct_citation",
                            "artifact_type": "verification_report",
                            "content": "verdict: informally_verified\ncritical_errors: []\ngaps: []",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {
                                    "checked_items": ["The citation statement matches the side claim."],
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf_direct_citation",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["vr_direct_citation"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "claim_direct_citation",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["vr_direct_citation"],
                        },
                    ],
                    "rationale": "strict verifier certifies the direct citation route",
                },
            )

            self.assertTrue(verified.accepted, verified.errors)

    def test_repeated_debt_id_with_new_wording_refreshes_existing_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-debt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

            first = apply_patch(
                store,
                add_debt_patch(
                    problem_id=store.problem_id,
                    base_revision=0,
                    debt_id="debt-repeated-gap",
                    obligation="Prove the missing fixed-source smoothing lemma.",
                ),
            )
            self.assertTrue(first.accepted, first.errors)

            second = apply_patch(
                store,
                add_debt_patch(
                    problem_id=store.problem_id,
                    base_revision=1,
                    debt_id="debt-repeated-gap",
                    obligation="Prove the same missing fixed-source smoothing lemma with refined hypotheses.",
                ),
            )
            self.assertTrue(second.accepted, second.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = list(conn.execute("SELECT debt_id, repeated_count, severity, status FROM debts"))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["debt_id"], "debt-repeated-gap")
            self.assertEqual(rows[0]["repeated_count"], 2)
            self.assertEqual(rows[0]["severity"], "blocking")
            self.assertEqual(rows[0]["status"], "active")

    def test_non_verifier_repair_submission_does_not_resolve_blocking_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-debt-repair-submitted-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

            first = apply_patch(
                store,
                add_debt_patch(
                    problem_id=store.problem_id,
                    base_revision=0,
                    debt_id="debt-gap",
                    obligation="Repair the local proof gap.",
                ),
            )
            self.assertTrue(first.accepted, first.errors)

            researcher_repair = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "resolve_debt",
                            "debt_id": "debt-gap",
                            "resolution_evidence": {"artifact_id": "repair-dossier"},
                        }
                    ],
                    "rationale": "submit a candidate repair",
                },
            )
            self.assertTrue(researcher_repair.accepted, researcher_repair.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT status, resolution_evidence_json FROM debts WHERE debt_id = 'debt-gap'").fetchone()

            self.assertEqual(row["status"], "active")
            evidence = json.loads(row["resolution_evidence_json"])
            self.assertEqual(evidence["repair_submitted_by"], "researcher")
            self.assertEqual(evidence["resolution_status"], "repair_submitted_pending_verifier")

            verifier_close = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "resolve_debt",
                            "debt_id": "debt-gap",
                            "resolution_evidence": {"artifact_id": "verification-report"},
                        }
                    ],
                    "rationale": "verifier accepts the repair",
                },
            )
            self.assertTrue(verifier_close.accepted, verifier_close.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT status FROM debts WHERE debt_id = 'debt-gap'").fetchone()

            self.assertEqual(row["status"], "resolved")

    def test_debt_bearing_route_cannot_be_abandoned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-protect-debt-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "claim_id": "repair-target",
                            "kind": "lemma",
                            "statement": "Repair this concrete proof subcase.",
                            "root_impact": 0.9,
                            "reduction_depth": 2,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-repair-target",
                            "conclusion_claim_id": "repair-target",
                            "relation_to_parent": "sufficient",
                            "strategy": "Prove the concrete subcase.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-repair-target",
                            "owner_type": "claim",
                            "owner_id": "repair-target",
                            "debt_type": "gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Close the concrete proof gap.",
                            "suggested_next_target": "repair-target",
                        },
                    ],
                    "rationale": "seed protected route",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)

            abandoned = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "phd_advisor",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "abandon_route",
                            "route_id": "route-repair-target",
                        }
                    ],
                    "rationale": "bad triage should be rejected",
                },
            )

            self.assertFalse(abandoned.accepted)
            self.assertIn("carries active blocking debt", abandoned.errors[0])

    def test_writer_accepts_starred_latex_references_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("writer-starred-references-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "writer-stop-summary",
                            "artifact_type": "stop_summary_report",
                            "content": (
                                "\\section*{Stop Summary Report}\n"
                                "The run stopped before an integrated proof, so this report records no theorem as proved.\n\n"
                                "\\section*{References}\n"
                                "The reference list is empty; this report was written from internal artifacts.\n"
                            ),
                            "metadata": {
                                "claim_id": "root",
                                "proof_status": "stopped_without_integrated_route",
                                "result_kind": "unresolved",
                                "relation_to_target": "partial",
                            },
                        }
                    ],
                    "rationale": "write stop summary",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)


class Phase2ExternalCitationTest(unittest.TestCase):
    def test_retrieval_card_serializes_structured_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("retrieval-structured-source-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "card_id": "structured-source-card",
                            "target_id": "root",
                            "exact_statement": "A structured source card should be cached.",
                            "source_identifiers": [
                                {
                                    "author": "A. Author",
                                    "title": "A source",
                                    "theorem_number": "Theorem 1",
                                }
                            ],
                            "source_version": {"url": "https://example.invalid/source.pdf", "accessed": "2026-06-23"},
                            "content_hash": {"pdf_sha256": "abc123", "text_sha256": "def456"},
                            "source_location": {
                                "url": "https://example.invalid/source.pdf",
                                "pages": "1-2",
                                "web_extraction_lines": "10-20",
                            },
                            "hypotheses": ["No extra hypotheses."],
                            "local_definitions": ["Definitions match."],
                            "missing_hypotheses": [],
                            "applicability": {
                                "classification": "method_match",
                                "implication_to_target_verified": False,
                            },
                        }
                    ],
                    "rationale": "cache structured source metadata",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT source_identifiers_json, source_version, source_location, content_hash FROM retrieval_cards WHERE card_id = 'structured-source-card'"
                ).fetchone()
            self.assertEqual(json.loads(row["source_identifiers_json"])[0]["theorem_number"], "Theorem 1")
            self.assertEqual(json.loads(row["source_version"])["accessed"], "2026-06-23")
            self.assertEqual(json.loads(row["source_location"])["pages"], "1-2")
            self.assertEqual(json.loads(row["content_hash"])["pdf_sha256"], "abc123")

    def test_informally_verified_report_can_certify_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("verification-verdict-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Direct proof.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "premise_claim_ids": [],
                            "conclusion_claim_id": "root",
                            "route_id": "route-root",
                            "argument_summary": "The route proves the root theorem.",
                        },
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)

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
                            "artifact_id": "verification-report",
                            "artifact_type": "verification_report",
                            "content": "verdict: informally_verified\ncritical_errors: []\ngaps: []\n",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {
                                    "summary": "No gaps.",
                                    "checked_items": ["Checked the complete local proof packet."],
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                    ],
                    "rationale": "strict verifier accepts the proof",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                root = conn.execute("SELECT validation_status FROM claims WHERE claim_id = 'root'").fetchone()
                inference = conn.execute("SELECT validation_status FROM inferences WHERE inference_id = 'inf-root'").fetchone()
            self.assertEqual(root["validation_status"], "informally_verified")
            self.assertEqual(inference["validation_status"], "informally_verified")

    def test_researcher_can_append_evidence_to_existing_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("update-inference-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Direct proof.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "premise_claim_ids": [],
                            "conclusion_claim_id": "root",
                            "route_id": "route-root",
                            "validation_status": "plausible",
                            "explanation": "Original route evidence.",
                        },
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)

            update = apply_patch(
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
                            "artifact_id": "repair-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "This repairs a local obstruction without verifying the route.\n",
                        },
                        {
                            "op": "update_inference",
                            "inference_id": "inf-root",
                            "add_evidence_artifact_ids": ["repair-dossier"],
                            "explanation_append": "Added the repair dossier as route evidence.",
                        },
                    ],
                    "rationale": "append route evidence",
                },
            )
            self.assertTrue(update.accepted, update.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                inference = conn.execute(
                    "SELECT explanation, validation_status, evidence_artifact_ids_json FROM inferences WHERE inference_id = 'inf-root'"
                ).fetchone()
            self.assertEqual(inference["validation_status"], "plausible")
            self.assertIn("Original route evidence.", inference["explanation"])
            self.assertIn("Added the repair dossier", inference["explanation"])
            self.assertEqual(json.loads(inference["evidence_artifact_ids_json"]), ["repair-dossier"])

    def test_root_integration_accepts_theorem_sentence_from_instructional_root_text(self) -> None:
        theorem = "There exists a weakly quasi-complete Noetherian local ring that is not quasi-complete."
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("integration-root-statement-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(
                "Prove that there exists a weakly quasi-complete Noetherian local ring that is not quasi-complete.\n\n"
                "Definitions. Let (R, m) be a Noetherian local ring. R is quasi-complete if ..."
            )

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
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Construct a Noetherian local domain witness.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The route proves the root theorem.",
                        },
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)

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
                            "artifact_id": "verification-report",
                            "artifact_type": "verification_report",
                            "content": "Verdict: informally_verified. No gaps.",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                    ],
                    "rationale": "strict verifier accepts the proof",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            integrated = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "integration_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "integration-report",
                            "artifact_type": "integration_report",
                            "content": "The route proves a stronger Noetherian local domain witness.",
                            "metadata": {
                                "integrates": True,
                                "root_alignment": {
                                    "relation_to_root": "stronger",
                                    "target_statement": theorem,
                                    "proved_statement": "There exists a Noetherian local domain that is weakly quasi-complete and not quasi-complete.",
                                    "implication_verified": True,
                                    "hidden_assumptions": False,
                                    "extra_assumptions": [],
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "lifecycle",
                            "new_status": "integrated",
                            "route_id": "route-root",
                            "evidence_artifact_ids": ["integration-report"],
                        },
                    ],
                    "rationale": "integration verifier accepts stronger theorem sentence alignment",
                },
            )
            self.assertTrue(integrated.accepted, integrated.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                root = conn.execute("SELECT lifecycle_status FROM claims WHERE claim_id = 'root'").fetchone()
                route = conn.execute("SELECT status FROM routes WHERE route_id = 'route-root'").fetchone()
            self.assertEqual(root["lifecycle_status"], "integrated")
            self.assertEqual(route["status"], "integrated")

    def test_root_integration_accepts_first_paragraph_theorem_from_benchmark_prompt(self) -> None:
        theorem = "There are infinitely many primes congruent to 1 modulo 4."
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("integration-benchmark-prompt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(
                "Prove that there are infinitely many primes congruent to 1 modulo 4.\n\n"
                "This experiment is intended to test whether the system can solve the problem from standard mathematical reasoning. "
                "Online lookup is allowed if it is genuinely useful."
            )

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
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the Euclid square-plus-one argument.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The route proves the root theorem.",
                        },
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)

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
                            "artifact_id": "verification-report",
                            "artifact_type": "verification_report",
                            "content": "Verdict: informally_verified. No gaps.",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                    ],
                    "rationale": "strict verifier accepts the proof",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            integrated = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "integration_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "integration-report",
                            "artifact_type": "integration_report",
                            "content": "The route proves the theorem sentence in the benchmark prompt.",
                            "metadata": {
                                "integrates": True,
                                "root_alignment": {
                                    "relation_to_root": "exact",
                                    "target_statement": theorem,
                                    "proved_statement": theorem,
                                    "implication_verified": True,
                                    "hidden_assumptions": False,
                                    "extra_assumptions": [],
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "lifecycle",
                            "new_status": "integrated",
                            "route_id": "route-root",
                            "evidence_artifact_ids": ["integration-report"],
                        },
                    ],
                    "rationale": "integration verifier accepts theorem sentence alignment",
                },
            )
            self.assertTrue(integrated.accepted, integrated.errors)

    def _assert_zero_gap_verdict_can_certify_claim(self, verdict: str) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(f"verification-{verdict}-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Direct proof.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The route proves the root theorem.",
                        },
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)

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
                            "artifact_id": "verification-report",
                            "artifact_type": "verification_report",
                            "content": f"verdict: {verdict}\ncritical_errors: []\ngaps: []\n",
                            "metadata": {
                                "verdict": verdict,
                                "summary": "No gaps.",
                                "checked_items": ["Checked the complete local proof packet."],
                                "critical_errors": [],
                                "gaps": [],
                                "blocking_gap": None,
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                    ],
                    "rationale": "strict verifier accepts the proof",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                root = conn.execute("SELECT validation_status FROM claims WHERE claim_id = 'root'").fetchone()
                inference = conn.execute("SELECT validation_status FROM inferences WHERE inference_id = 'inf-root'").fetchone()
            self.assertEqual(root["validation_status"], "informally_verified")
            self.assertEqual(inference["validation_status"], "informally_verified")

    def test_correct_no_gaps_report_can_certify_claim(self) -> None:
        self._assert_zero_gap_verdict_can_certify_claim("correct_no_gaps")

    def test_pass_report_can_certify_claim(self) -> None:
        self._assert_zero_gap_verdict_can_certify_claim("pass")

    def test_exact_external_citation_certifies_root_and_resolves_root_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("citation-cert-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("There exists a weakly quasi-complete Noetherian local ring that is not quasi-complete.")

            debt_outcome = apply_patch(
                store,
                add_debt_patch(
                    problem_id=store.problem_id,
                    base_revision=0,
                    debt_id="debt-root-construction",
                    obligation="Reconstruct the formal-fiber construction internally.",
                ),
            )
            self.assertTrue(debt_outcome.accepted, debt_outcome.errors)

            retrieval_outcome = apply_patch(
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
                            "card_id": "retrieval-direct-theorem",
                            "target_id": "root",
                            "exact_statement": "There exists a weakly quasi-complete Noetherian local ring that is not quasi-complete.",
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Weakly quasi-complete rings",
                                "theorem_number": "Theorem 6",
                                "arxiv": "arXiv:2604.03789v1",
                            },
                            "source_version": "arXiv:2604.03789v1",
                            "source_location": "Theorem 6",
                            "hypotheses": [],
                            "local_definitions": ["weakly quasi-complete and quasi-complete agree with the target statement"],
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
            self.assertTrue(retrieval_outcome.accepted, retrieval_outcome.errors)

            cert_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "certify_external_citation",
                            "card_id": "retrieval-direct-theorem",
                            "target_id": "root",
                            "relation_to_target": "exact",
                            "implication_verified": True,
                            "hidden_assumptions": False,
                            "checked_items": [
                                "The cited theorem statement exactly matches the immutable root statement.",
                                "The theorem has no additional hypotheses.",
                            ],
                        }
                    ],
                    "rationale": "certify exact cited theorem",
                },
            )
            self.assertTrue(cert_outcome.accepted, cert_outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                root = conn.execute("SELECT validation_status, evidence_artifact_ids_json FROM claims WHERE claim_id = 'root'").fetchone()
                route = conn.execute("SELECT * FROM routes WHERE conclusion_claim_id = 'root'").fetchone()
                inference = conn.execute("SELECT * FROM inferences WHERE conclusion_claim_id = 'root'").fetchone()
                debt = conn.execute("SELECT status FROM debts WHERE debt_id = 'debt-root-construction'").fetchone()
                artifact = conn.execute("SELECT metadata_json FROM artifacts WHERE artifact_type = 'verification_report'").fetchone()
                library_entry = conn.execute("SELECT * FROM theorem_library_entries").fetchone()

            self.assertEqual(root["validation_status"], "informally_verified")
            self.assertIsNotNone(route)
            self.assertEqual(route["relation_to_parent"], "sufficient")
            self.assertIsNotNone(inference)
            self.assertEqual(inference["validation_status"], "informally_verified")
            self.assertEqual(debt["status"], "resolved")
            metadata = json.loads(artifact["metadata_json"])
            self.assertEqual(metadata["certification_type"], "external_citation")
            self.assertEqual(metadata["retrieval_card_id"], "retrieval-direct-theorem")
            self.assertIsNotNone(library_entry)
            self.assertEqual(library_entry["certification_type"], "external_citation")
            self.assertIn("weakly quasi-complete", library_entry["statement"])

    def test_structured_external_citation_resolves_route_premise_debt(self) -> None:
        theorem = "There exists a weakly quasi-complete Noetherian local ring that is not quasi-complete."
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("structured-citation-cert-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(theorem)

            setup_outcome = apply_patch(
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
                            "claim_id": "claim-construction",
                            "kind": "lemma",
                            "statement": "There is a formal-fiber construction satisfying the route hypotheses.",
                            "validation_status": "untested",
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-formal-fiber",
                            "conclusion_claim_id": "root",
                            "label": "Formal-fiber route",
                            "strategy": "Use the construction claim to prove the root theorem.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-formal-fiber",
                            "route_id": "route-formal-fiber",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": ["claim-construction"],
                            "validation_status": "plausible",
                            "explanation": "The construction implies the root theorem.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-construction",
                            "owner_type": "claim",
                            "owner_id": "claim-construction",
                            "debt_type": "missing_construction_or_citation",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Find the formal-fiber construction.",
                            "suggested_next_target": "claim-construction",
                        },
                    ],
                    "rationale": "setup routed construction debt",
                },
            )
            self.assertTrue(setup_outcome.accepted, setup_outcome.errors)

            retrieval_outcome = apply_patch(
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
                            "card_id": "retrieval-structured-source",
                            "target_id": "root",
                            "exact_statement": theorem,
                            "source_identifiers": {
                                "primary_theorem": {
                                    "author": "David Jensen",
                                    "title": "Completions of UFDs with Semi-Local Formal Fibers",
                                    "corollary_number": "Corollary 2.4",
                                    "section/page": "p. 353",
                                    "doi": "10.1080/00927870500346321",
                                },
                                "auxiliary_fact": {
                                    "author": "Robin Hartshorne",
                                    "title": "Algebraic Geometry",
                                    "section/page": "Example II.6.5.2",
                                    "doi": "10.1007/978-1-4757-3849-0",
                                },
                            },
                            "source_version": "publisher PDF",
                            "source_location": "Jensen Corollary 2.4; Hartshorne Example II.6.5.2",
                            "hypotheses": [],
                            "local_definitions": ["source definitions match the target route"],
                            "missing_hypotheses": [],
                            "applicability": {
                                "target_id": "root",
                                "route_id": "route-formal-fiber",
                                "classification": "direct_match",
                                "theorem_matching_status": "checked_composite_match",
                                "implication_to_target_verified": True,
                            },
                        }
                    ],
                    "rationale": "cache structured source theorem",
                },
            )
            self.assertTrue(retrieval_outcome.accepted, retrieval_outcome.errors)

            cert_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "certify_external_citation",
                            "card_id": "retrieval-structured-source",
                            "target_id": "root",
                            "relation_to_target": "direct_match",
                            "implication_verified": True,
                            "hidden_assumptions": False,
                            "checked_items": ["The structured primary theorem is locatable and implies the target."],
                        }
                    ],
                    "rationale": "certify structured source citation",
                },
            )
            self.assertTrue(cert_outcome.accepted, cert_outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                debt = conn.execute("SELECT status, resolution_evidence_json FROM debts WHERE debt_id = 'debt-construction'").fetchone()
                artifact = conn.execute("SELECT path FROM artifacts WHERE artifact_type = 'verification_report'").fetchone()

            self.assertEqual(debt["status"], "resolved")
            self.assertIn("retrieval-structured-source", debt["resolution_evidence_json"])
            report_text = Path(artifact["path"]).read_text(encoding="utf-8")
            self.assertIn("David Jensen", report_text)
            self.assertIn("Completions of UFDs", report_text)

    def test_propose_lifecycle_alias_integrates_verified_citation_route(self) -> None:
        theorem = "There exists a weakly quasi-complete Noetherian local ring that is not quasi-complete."
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("citation-lifecycle-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(theorem)

            retrieval_outcome = apply_patch(
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
                            "card_id": "retrieval-direct-theorem",
                            "target_id": "root",
                            "exact_statement": theorem,
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Weakly quasi-complete rings",
                                "theorem_number": "Theorem 6",
                                "arxiv": "arXiv:2604.03789v1",
                            },
                            "source_version": "arXiv:2604.03789v1",
                            "source_location": "Theorem 6",
                            "hypotheses": [],
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
            self.assertTrue(retrieval_outcome.accepted, retrieval_outcome.errors)

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
                            "card_id": "retrieval-direct-theorem",
                            "target_id": "root",
                            "relation_to_target": "exact",
                            "implication_verified": True,
                            "hidden_assumptions": False,
                            "checked_items": ["The cited theorem exactly matches the root statement."],
                        }
                    ],
                    "rationale": "certify exact cited theorem",
                },
            )
            self.assertTrue(cert_outcome.accepted, cert_outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                route = conn.execute("SELECT route_id FROM routes WHERE conclusion_claim_id = 'root'").fetchone()
            self.assertIsNotNone(route)

            integrated = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "integration_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "integration-report",
                            "artifact_type": "integration_report",
                            "content": "The verified citation route exactly proves the root theorem.",
                            "metadata": {
                                "integrates": True,
                                "route_id": route["route_id"],
                                "claim_id": "root",
                                "root_alignment": {
                                    "relation_to_root": "exact",
                                    "target_statement": theorem,
                                    "proved_statement": theorem,
                                    "implication_verified": True,
                                    "hidden_assumptions": False,
                                    "extra_assumptions": [],
                                },
                            },
                        },
                        {
                            "op": "propose_lifecycle",
                            "claim_id": "root",
                            "lifecycle_status": "integrated",
                            "route_id": route["route_id"],
                            "evidence_artifact_ids": ["integration-report"],
                        },
                    ],
                    "rationale": "agent emitted lifecycle alias",
                },
            )
            self.assertTrue(integrated.accepted, integrated.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                root = conn.execute("SELECT lifecycle_status FROM claims WHERE claim_id = 'root'").fetchone()
                route_row = conn.execute("SELECT status FROM routes WHERE route_id = ?", (route["route_id"],)).fetchone()
            self.assertEqual(root["lifecycle_status"], "integrated")
            self.assertEqual(route_row["status"], "integrated")

    def test_older_claim_debt_does_not_block_after_clean_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("integration-downstream-debt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
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
                            "op": "attach_artifact",
                            "artifact_id": "bridge-proof",
                            "artifact_type": "proof_dossier",
                            "content": "Complete proof of the side bridge.",
                        },
                        {
                            "op": "add_claim",
                            "claim_id": "side-bridge",
                            "statement": "Side bridge lemma.",
                            "parent_ids": ["root"],
                            "root_impact": 0.7,
                            "reduction_depth": 1,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-side-bridge",
                            "conclusion_claim_id": "side-bridge",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use bridge-proof.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-side-bridge",
                            "route_id": "route-side-bridge",
                            "conclusion_claim_id": "side-bridge",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof dossier proves the side bridge.",
                            "evidence_artifact_ids": ["bridge-proof"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-before-side-bridge-verification",
                            "owner_type": "claim",
                            "owner_id": "side-bridge",
                            "debt_type": "proof_gap",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Prove the exact side bridge without hidden assumptions.",
                            "suggested_next_target": "side-bridge",
                        },
                    ],
                    "rationale": "seed side-bridge candidate plus downstream debt",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)

            verified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "side-bridge",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "verif-side-bridge",
                            "artifact_type": "verification_report",
                            "content": "{\"verdict\":\"verified\",\"critical_errors\":[],\"gaps\":[],\"blocking_gap\":false}",
                            "metadata": {
                                "verdict": "verified",
                                "verification_report": {
                                    "verdict": "verified",
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "side-bridge",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verif-side-bridge"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-side-bridge",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verif-side-bridge"],
                        },
                    ],
                    "rationale": "verify side bridge",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            integrated = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "integration_verifier",
                    "target_id": "side-bridge",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "integration-side-bridge",
                            "artifact_type": "integration_report",
                            "content": "The side bridge integrates despite a downstream root bottleneck.",
                            "metadata": {
                                "integrates": True,
                                "route_id": "route-side-bridge",
                                "claim_id": "side-bridge",
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "side-bridge",
                            "status_type": "lifecycle",
                            "new_status": "integrated",
                            "route_id": "route-side-bridge",
                            "evidence_artifact_ids": ["integration-side-bridge", "verif-side-bridge"],
                        },
                    ],
                    "rationale": "integrate side bridge",
                },
            )
            self.assertTrue(integrated.accepted, integrated.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                claim = conn.execute("SELECT lifecycle_status FROM claims WHERE claim_id = 'side-bridge'").fetchone()
                route = conn.execute("SELECT status FROM routes WHERE route_id = 'route-side-bridge'").fetchone()
                debt = conn.execute(
                    "SELECT status FROM debts WHERE debt_id = 'debt-before-side-bridge-verification'"
                ).fetchone()

        self.assertEqual(claim["lifecycle_status"], "integrated")
        self.assertEqual(route["status"], "integrated")
        self.assertEqual(debt["status"], "active")

    def test_rejects_new_active_sufficient_route_to_integrated_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("integrated-claim-route-spam-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
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
                            "claim_id": "closed-lemma",
                            "kind": "lemma",
                            "statement": "The closed lemma is true.",
                            "root_impact": 0.7,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-closed-lemma",
                            "conclusion_claim_id": "closed-lemma",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the original proof.",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "proof-closed-lemma",
                            "artifact_type": "proof_dossier",
                            "content": "Proof of the closed lemma.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-closed-lemma",
                            "route_id": "route-closed-lemma",
                            "conclusion_claim_id": "closed-lemma",
                            "validation_status": "plausible",
                            "explanation": "The dossier proves it.",
                            "evidence_artifact_ids": ["proof-closed-lemma"],
                        },
                    ],
                    "rationale": "seed closable side lemma",
                },
            )
            self.assertTrue(seed.accepted, seed.errors)

            verified = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "strict_informal_verifier",
                    "target_id": "closed-lemma",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "verif-closed-lemma",
                            "artifact_type": "verification_report",
                            "content": "Verified.",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-closed-lemma",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verif-closed-lemma"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "closed-lemma",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verif-closed-lemma"],
                        },
                    ],
                    "rationale": "verify side lemma",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            integrated = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "integration_verifier",
                    "target_id": "closed-lemma",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "integration-closed-lemma",
                            "artifact_type": "integration_report",
                            "content": "Integrates the side lemma.",
                            "metadata": {
                                "integrates": True,
                                "route_id": "route-closed-lemma",
                                "claim_id": "closed-lemma",
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "closed-lemma",
                            "status_type": "lifecycle",
                            "new_status": "integrated",
                            "route_id": "route-closed-lemma",
                            "evidence_artifact_ids": ["integration-closed-lemma", "verif-closed-lemma"],
                        },
                    ],
                    "rationale": "integrate side lemma",
                },
            )
            self.assertTrue(integrated.accepted, integrated.errors)

            duplicate_route = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 3,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "add_route",
                            "route_id": "route-closed-lemma-duplicate",
                            "conclusion_claim_id": "closed-lemma",
                            "relation_to_parent": "sufficient",
                            "status": "active",
                            "strategy": "",
                        }
                    ],
                    "rationale": "try to reopen a closed proof branch",
                },
            )
            self.assertFalse(duplicate_route.accepted)
            self.assertIn("already integrated", " ".join(duplicate_route.errors))

    def test_status_transition_aliases_infer_same_patch_integration_report(self) -> None:
        theorem = "Every compact integration packet stays visible."
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("integration-status-transition-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(theorem)
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
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Direct verified route.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The route proves the root theorem.",
                        },
                    ],
                    "rationale": "seed route",
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
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "verification-report",
                            "artifact_type": "verification_report",
                            "content": "verified",
                            "metadata": {
                                "verdict": "verified",
                                "verification_report": {
                                    "checked_items": ["Checked root route."],
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                    ],
                    "rationale": "verify root route",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)
            integrated = apply_patch(
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
                            "artifact_id": "integration-report",
                            "artifact_type": "integration_report",
                            "content": "The verified route exactly proves the root theorem.",
                            "metadata": {
                                "integrates": True,
                                "route_id": "route-root",
                                "claim_id": "root",
                                "missing": [],
                                "root_alignment": {
                                    "relation_to_root": "exact",
                                    "target_statement": theorem,
                                    "proved_statement": theorem,
                                    "implication_verified": True,
                                    "hidden_assumptions": False,
                                    "extra_assumptions": [],
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "entity_type": "claim",
                            "entity_id": "root",
                            "lifecycle_status": "integrated",
                            "route_id": "route-root",
                        },
                    ],
                    "rationale": "agent emitted lifecycle status transition alias without explicit evidence ids",
                },
            )
            self.assertTrue(integrated.accepted, integrated.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                root = conn.execute("SELECT lifecycle_status FROM claims WHERE claim_id = 'root'").fetchone()
                route_row = conn.execute("SELECT status FROM routes WHERE route_id = 'route-root'").fetchone()
            self.assertEqual(root["lifecycle_status"], "integrated")
            self.assertEqual(route_row["status"], "integrated")

    def test_status_transitions_infer_same_patch_verification_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("verification-status-transition-evidence-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")
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
                            "claim_id": "lemma-frattini",
                            "kind": "lemma",
                            "statement": "Frattini lifting preserves the selected invariable generators.",
                            "parent_ids": ["root"],
                            "validation_status": "untested",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-frattini",
                            "conclusion_claim_id": "lemma-frattini",
                            "relation_to_parent": "sufficient",
                            "strategy": "Direct Frattini lifting proof.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-frattini",
                            "route_id": "route-frattini",
                            "conclusion_claim_id": "lemma-frattini",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The route proves the lemma.",
                        },
                    ],
                    "rationale": "seed verifier-ready lemma",
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
                    "target_id": "lemma-frattini",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "verification-frattini",
                            "artifact_type": "verification_report",
                            "content": "{\"verdict\":\"verified\",\"critical_errors\":[],\"gaps\":[],\"blocking_gap\":false}",
                            "metadata": {
                                "verdict": "verified",
                                "verification_report": {
                                    "critical_errors": [],
                                    "gaps": [],
                                    "blocking_gap": False,
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_kind": "inference",
                            "target_id": "inf-frattini",
                            "to_status": "informally_verified",
                        },
                        {
                            "op": "propose_status_transition",
                            "object_type": "claim",
                            "object_id": "lemma-frattini",
                            "proposed_status": "informally_verified",
                        },
                    ],
                    "rationale": "agent emitted direct status transitions without explicit evidence ids",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                claim = conn.execute("SELECT validation_status, evidence_artifact_ids_json FROM claims WHERE claim_id = 'lemma-frattini'").fetchone()
                inference = conn.execute("SELECT validation_status, evidence_artifact_ids_json FROM inferences WHERE inference_id = 'inf-frattini'").fetchone()
            self.assertEqual(claim["validation_status"], "informally_verified")
            self.assertEqual(inference["validation_status"], "informally_verified")
            self.assertEqual(json.loads(claim["evidence_artifact_ids_json"]), ["verification-frattini"])
            self.assertEqual(json.loads(inference["evidence_artifact_ids_json"]), ["verification-frattini"])

    def test_root_integration_accepts_target_statement_with_definition_qualifier(self) -> None:
        theorem = (
            "Prove that there exists a weakly quasi-complete Noetherian local ring that is not quasi-complete.\n\n"
            "Definitions. Let (R,m) be a Noetherian local ring."
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("citation-qualified-root-alignment-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(theorem)

            retrieval_outcome = apply_patch(
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
                            "card_id": "retrieval-qualified-root",
                            "target_id": "root",
                            "exact_statement": "A constructed ring is weakly quasi-complete and not quasi-complete.",
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Qualified root theorem",
                                "theorem_number": "Theorem 1",
                                "doi": "10.0000/example",
                            },
                            "source_version": "publisher version",
                            "source_location": "Theorem 1",
                            "hypotheses": [],
                            "missing_hypotheses": [],
                            "applicability": {
                                "target_id": "root",
                                "classification": "stronger_match",
                                "implication_to_target_verified": True,
                            },
                        }
                    ],
                    "rationale": "cache stronger theorem",
                },
            )
            self.assertTrue(retrieval_outcome.accepted, retrieval_outcome.errors)

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
                            "card_id": "retrieval-qualified-root",
                            "target_id": "root",
                            "relation_to_target": "stronger",
                            "implication_verified": True,
                            "hidden_assumptions": False,
                            "checked_items": ["The stronger theorem implies the root theorem."],
                        }
                    ],
                    "rationale": "certify stronger cited theorem",
                },
            )
            self.assertTrue(cert_outcome.accepted, cert_outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                route = conn.execute("SELECT route_id FROM routes WHERE conclusion_claim_id = 'root'").fetchone()
            self.assertIsNotNone(route)

            integrated = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "integration_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "integration-qualified-root",
                            "artifact_type": "integration_report",
                            "content": "The verified stronger theorem implies the root theorem.",
                            "metadata": {
                                "integrates": True,
                                "route_id": route["route_id"],
                                "claim_id": "root",
                                "root_alignment": {
                                    "relation_to_root": "stronger",
                                    "target_statement": (
                                        "There exists a weakly quasi-complete Noetherian local ring that is not quasi-complete, "
                                        "with weakly quasi-complete and quasi-complete as defined in the manifest."
                                    ),
                                    "proved_statement": "A constructed ring is weakly quasi-complete and not quasi-complete.",
                                    "implication_verified": True,
                                    "hidden_assumptions": False,
                                    "extra_assumptions": [],
                                },
                            },
                        },
                        {
                            "op": "propose_lifecycle",
                            "claim_id": "root",
                            "lifecycle_status": "integrated",
                            "route_id": route["route_id"],
                            "evidence_artifact_ids": ["integration-qualified-root"],
                        },
                    ],
                    "rationale": "integrate with qualified target statement",
                },
            )
            self.assertTrue(integrated.accepted, integrated.errors)

    def test_external_citation_requires_exact_source_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("citation-source-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Target theorem.")

            retrieval_outcome = apply_patch(
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
                            "card_id": "retrieval-vague-source",
                            "target_id": "root",
                            "exact_statement": "Target theorem.",
                            "source_identifiers": {
                                "author": "A. Author",
                                "title": "Vague Source",
                                "arxiv": "arXiv:0000.00000",
                            },
                            "source_version": "arXiv:0000.00000",
                            "hypotheses": [],
                            "local_definitions": [],
                            "missing_hypotheses": [],
                            "applicability": {
                                "target_id": "root",
                                "classification": "direct_match",
                                "implication_to_target_verified": True,
                            },
                        }
                    ],
                    "rationale": "cache vague source",
                },
            )
            self.assertTrue(retrieval_outcome.accepted, retrieval_outcome.errors)

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
                            "card_id": "retrieval-vague-source",
                            "target_id": "root",
                            "relation_to_target": "exact",
                            "implication_verified": True,
                        }
                    ],
                    "rationale": "try to certify vague source",
                },
            )
            self.assertFalse(cert_outcome.accepted)
            self.assertIn("exact theorem", cert_outcome.errors[0])


class Phase2PatchWriterReceiptTest(unittest.TestCase):
    def test_latex_renderer_distinguishes_math_from_prose(self) -> None:
        latex = format_receipt_latex(
            "Statement: If M^sm=M^s and Br(M^sm)=Z/hZ, then K_M=-2hTheta. "
            "The writer keeps `claim-id` as code."
        )

        self.assertIn(r"\ensuremath{M^{\mathrm{sm}}=M^s}", latex)
        self.assertIn(r"\operatorname{Br}(M^{\mathrm{sm}})", latex)
        self.assertIn(r"\mathbb{Z}/h\mathbb{Z}", latex)
        self.assertIn(r"\Theta", latex)
        self.assertIn(r"\texttt{claim-id}", latex)

    def test_latex_renderer_formats_claims_as_math_report_blocks(self) -> None:
        latex = format_receipt_latex(
            """## Verified Side Lemmas

Count: 1

- `lem-demo` validation=informally_verified lifecycle=active relation=partial kind=lemma depth=1 root_impact=0.5
  Statement: Let M=SU_C(r,L), Br(M^sm)=Z/hZ, and K_M = -2 h Theta.
  Parent claims: ["root"]
  Evidence artifacts: ["proof-art"]
  Proof material:
  - `proof-art` type=verification_report producer=strict_informal_verifier revision=7
    Summary: Proves d delta = h k mod r.
    Content:

Proof: The congruence d delta = h k mod r gives the required label.
  Tags: ["demo"]
"""
        )

        self.assertIn(r"\claimheading{lemma lem-demo}", latex)
        self.assertIn(r"\fieldlabel{Statement}", latex)
        self.assertIn(r"\fieldlabel{Proof}", latex)
        self.assertIn(r"\artifactheading{Evidence source}", latex)
        self.assertIn("Certification: informally verified", latex)
        self.assertNotIn("depth 1", latex)
        self.assertNotIn("impact 0.5", latex)
        self.assertNotIn(r"\fieldlabel{Parent claims}", latex)
        self.assertNotIn(r"\fieldlabel{Evidence artifacts}", latex)
        self.assertNotIn(r"\fieldlabel{Tags}", latex)
        self.assertIn(r"\ensuremath{\operatorname{Br}(M^{\mathrm{sm}})=\mathbb{Z}/h\mathbb{Z}}", latex)
        self.assertIn(r"\ensuremath{K_M = -2 h \Theta}", latex)
        self.assertIn(r"\ensuremath{d \delta = h k \bmod r}", latex)

    def test_latex_renderer_keeps_artifact_headings_inside_claim_blocks(self) -> None:
        latex = format_receipt_latex(
            """## Verified Side Lemmas

Count: 1

- `lem-demo` validation=informally_verified lifecycle=active relation=partial kind=lemma depth=1 root_impact=0.5
  Statement: Br(M^sm)=Z/hZ.
  Proof material:
  - `proof-art` type=proof_blueprint producer=researcher revision=7
    Content:

# Internal Proof Heading

Proof: K_M=-2hTheta.
"""
        )

        self.assertNotIn(r"\section{Internal Proof Heading}", latex)
        self.assertIn(r"\paragraph{Internal Proof Heading}", latex)
        self.assertIn(r"\ensuremath{K_M=-2h\Theta}", latex)

    def test_partial_writer_artifact_appends_claim_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("writer-receipt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "claim_id": "lem-side",
                            "kind": "lemma",
                            "statement": "This side lemma is proved.",
                            "validation_status": "untested",
                            "lifecycle_status": "active",
                            "root_impact": 0.8,
                            "reduction_depth": 1,
                            "parent_ids": ["root"],
                            "tags": ["root-local"],
                        }
                    ],
                    "rationale": "seed side lemma",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            with store.connect() as conn:
                proof_path = store.state_dir / "artifacts" / "side-proof.txt"
                proof_path.parent.mkdir(parents=True, exist_ok=True)
                proof_path.write_text("Proof body for the side lemma.", encoding="utf-8")
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        artifact_id, artifact_type, path, sha256, producer_role, run_id,
                        state_revision, content_summary, metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "side-proof-artifact",
                        "verification_report",
                        str(proof_path),
                        "sha",
                        "strict_informal_verifier",
                        "",
                        1,
                        "side lemma verification",
                        "{}",
                        "2026-01-01T00:00:00+00:00",
                    ),
                )
                conn.execute(
                    """
                    UPDATE claims
                    SET validation_status = 'informally_verified',
                        evidence_artifact_ids_json = ?
                    WHERE claim_id = 'lem-side'
                    """,
                    (json.dumps(["side-proof-artifact"]),),
                )
                conn.commit()

            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "writer",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "partial-receipt-test",
                            "artifact_type": "stop_summary_report",
                            "content": (
                                "Partial receipt body.\n\n"
                                "## References\n\n"
                                "No external references; written by the Albilich writer from internal artifacts."
                            ),
                            "metadata": {"public_result_kind": "partial"},
                        }
                    ],
                    "rationale": "write partial receipt",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                artifact = conn.execute(
                    "SELECT path FROM artifacts WHERE artifact_id = 'partial-receipt-test'"
                ).fetchone()

            text = Path(artifact["path"]).read_text(encoding="utf-8")
            self.assertIn("## Verified Side Lemmas", text)
            self.assertIn("`lem-side` validation=informally_verified", text)
            self.assertIn("Proof body for the side lemma.", text)
            self.assertIn("## Claim Status Ledger", text)
            self.assertIn("`root` validation=untested", text)
            self.assertGreater(text.rfind("## References"), text.rfind("## Claim Status Ledger"))
            self.assertTrue(Path(artifact["path"]).with_suffix(".tex").exists())
            if shutil.which("pdflatex"):
                self.assertTrue(Path(artifact["path"]).with_suffix(".pdf").exists())

    def test_writer_artifact_requires_writer_authored_references_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("writer-reference-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "writer-report-missing-references",
                            "artifact_type": "writer_report",
                            "content": "Writer report body without a references section.",
                            "metadata": {"public_result_kind": "partial"},
                        }
                    ],
                    "rationale": "write writer report",
                },
            )

            self.assertFalse(outcome.accepted)
            self.assertIn("References section", outcome.errors[0])

    def test_writer_artifact_rejects_raw_proof_state_json_dump(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("writer-json-dump-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "writer-json-dump",
                            "artifact_type": "writer_report",
                            "content": (
                                "```json\n"
                                "{\"schema_version\": 2, \"problem_id\": \"p\", \"operations\": [], "
                                "\"claims\": [], \"routes\": [], \"lifecycle_status\": \"integrated\"}\n"
                                "```\n\n"
                                "## References\n\n"
                                "No external references; written by the Albilich writer from internal artifacts."
                            ),
                            "metadata": {"public_result_kind": "partial"},
                        }
                    ],
                    "rationale": "write raw json report",
                },
            )

            self.assertFalse(outcome.accepted)
            self.assertIn("raw proof-state JSON", outcome.errors[0])

    def test_final_proof_requires_explicit_proof_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("writer-final-proof-section-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "writer-final-no-proof",
                            "artifact_type": "final_proof",
                            "content": (
                                "The root theorem follows from the integrated route.\n\n"
                                "## References\n\n"
                                "No external references; written by the Albilich writer from internal artifacts."
                            ),
                            "metadata": {
                                "claim_id": "root",
                                "route_id": "route-root",
                                "proof_status": "written_from_integrated_route",
                            },
                        }
                    ],
                    "rationale": "write final proof without proof section",
                },
            )

            self.assertFalse(outcome.accepted)
            self.assertIn("explicit Proof section", outcome.errors[0])

    def test_final_proof_accepts_bold_markdown_proof_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("writer-final-bold-proof-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "writer-final-bold-proof",
                            "artifact_type": "final_proof",
                            "content": (
                                "# Final Proof\n\n"
                                "**Proof.** The root theorem follows from the integrated route.\n\n"
                                "## References\n\n"
                                "No external references; written by the Albilich writer from internal artifacts."
                            ),
                            "metadata": {
                                "claim_id": "root",
                                "route_id": "route-root",
                                "proof_status": "written_from_integrated_route",
                            },
                        }
                    ],
                    "rationale": "write final proof with bold proof heading",
                },
            )

            self.assertTrue(outcome.accepted, outcome.errors)

    def test_all_writer_artifacts_with_content_get_latex_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("writer-sidecar-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("prove the root theorem")

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
                            "artifact_id": "writer-report-test",
                            "artifact_type": "writer_report",
                            "content": (
                                "Writer report body with inline `claim-id`.\n\n"
                                "## References\n\n"
                                "No external references; written by the Albilich writer from internal artifacts."
                            ),
                            "metadata": {"public_result_kind": "partial"},
                        }
                    ],
                    "rationale": "write writer report",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                artifact = conn.execute(
                    "SELECT path FROM artifacts WHERE artifact_id = 'writer-report-test'"
                ).fetchone()

            artifact_path = Path(artifact["path"])
            self.assertTrue(artifact_path.exists())
            self.assertTrue(artifact_path.with_suffix(".tex").exists())
            if shutil.which("pdflatex"):
                self.assertTrue(artifact_path.with_suffix(".pdf").exists())


class Phase2VerifierPatchAliasTest(unittest.TestCase):
    def _seed_route_with_inference(self, store: ProofStateStore) -> None:
        outcome = apply_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": store.get_revision(),
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {"op": "add_claim", "claim_id": "lemma-x", "kind": "lemma", "statement": "If P then Q.", "parent_ids": ["root"], "root_impact": 0.8, "reduction_depth": 1},
                    {"op": "add_route", "route_id": "route-x", "conclusion_claim_id": "lemma-x", "relation_to_parent": "sufficient", "strategy": "direct"},
                    {"op": "attach_artifact", "artifact_id": "dossier-x", "artifact_type": "proof_dossier", "metadata": {"claim_id": "lemma-x", "route_id": "route-x"}, "content": "Proof: pure dimension count."},
                    {"op": "add_inference", "inference_id": "inf-x", "route_id": "route-x", "conclusion_claim_id": "lemma-x", "premise_claim_ids": [], "validation_status": "plausible", "explanation": "step", "evidence_artifact_ids": ["dossier-x"]},
                ],
                "rationale": "seed",
            },
        )
        self.assertTrue(outcome.accepted, outcome.errors)

    def _verifier_patch(self, store: ProofStateStore, *, gaps_section: str) -> dict:
        # Markdown report with EMPTY structured metadata and update_* aliases,
        # exactly the shape a verifier emitted in practice.
        content = "\n".join([
            "# Verification report", "", "## Verdict", "", "informally_verified", "",
            "## Critical errors", "", "[]", "", "## Gaps", "", gaps_section, "",
            "## Blocking gap", "", "null", "",
        ])
        return {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "strict_informal_verifier",
            "target_id": "lemma-x",
            "route_id": "route-x",
            "operations": [
                {"op": "attach_artifact", "artifact_id": "vr-x", "artifact_type": "verification_report", "metadata": {}, "content": content},
                {"op": "update_inference", "inference_id": "inf-x", "updates": {"validation_status": "informally_verified"}},
                {"op": "update_claim", "claim_id": "lemma-x", "updates": {"validation_status": "informally_verified"}},
            ],
            "rationale": "verify lemma",
        }

    def test_update_aliases_and_metadata_backfill_verify_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("verifier-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            self._seed_route_with_inference(store)
            outcome = apply_patch(store, self._verifier_patch(store, gaps_section="[]"))
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                claim = conn.execute("SELECT validation_status FROM claims WHERE claim_id='lemma-x'").fetchone()
                inf = conn.execute("SELECT validation_status FROM inferences WHERE inference_id='inf-x'").fetchone()
            self.assertEqual(claim["validation_status"], "informally_verified")
            self.assertEqual(inf["validation_status"], "informally_verified")

    def test_json_string_verification_report_allows_update_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("verifier-json-string-report-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            self._seed_route_with_inference(store)
            content = json.dumps(
                {
                    "verdict": "verified",
                    "checked_items": ["Checked lemma-x and inf-x."],
                    "summary": "The verifier found no gaps.",
                    "critical_errors": [],
                    "gaps": [],
                    "blocking_gap": False,
                    "repair_hints": [],
                }
            )
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "strict_informal_verifier",
                    "target_id": "lemma-x",
                    "route_id": "route-x",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact": {
                                "artifact_id": "vr-json-string-x",
                                "artifact_type": "verification_report",
                                "metadata": {},
                                "content_summary": "verified",
                                "content": content,
                            },
                        },
                        {
                            "op": "update_inference",
                            "inference_id": "inf-x",
                            "validation_status": "informally_verified",
                            "evidence_artifact_ids": ["vr-json-string-x"],
                        },
                        {
                            "op": "update_claim",
                            "claim_id": "lemma-x",
                            "validation_status": "informally_verified",
                            "evidence_artifact_ids": ["vr-json-string-x"],
                        },
                    ],
                    "rationale": "verify lemma from JSON-string verifier report",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                claim = conn.execute("SELECT validation_status FROM claims WHERE claim_id='lemma-x'").fetchone()
                inf = conn.execute("SELECT validation_status FROM inferences WHERE inference_id='inf-x'").fetchone()
                artifact = conn.execute(
                    "SELECT metadata_json FROM artifacts WHERE artifact_id='vr-json-string-x'"
                ).fetchone()
            metadata = json.loads(artifact["metadata_json"])
            self.assertEqual(metadata["verdict"], "verified")
            self.assertEqual(metadata["verification_report"]["critical_errors"], [])
            self.assertEqual(metadata["verification_report"]["gaps"], [])
            self.assertEqual(claim["validation_status"], "informally_verified")
            self.assertEqual(inf["validation_status"], "informally_verified")

    def test_set_status_aliases_verify_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("verifier-set-status-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            self._seed_route_with_inference(store)
            content = "\n".join([
                "# Verification report", "", "## Verdict", "", "informally_verified", "",
                "## Critical errors", "", "[]", "", "## Gaps", "", "[]", "",
            ])
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "strict_informal_verifier",
                    "target_id": "lemma-x",
                    "route_id": "route-x",
                    "operations": [
                        {"op": "attach_artifact", "artifact_id": "vr-set-x", "artifact_type": "verification_report", "metadata": {}, "content": content},
                        {"op": "set_inference_status", "inference_id": "inf-x", "validation_status": "informally_verified", "evidence_artifact_ids": ["vr-set-x"]},
                        {"op": "set_claim_status", "claim_id": "lemma-x", "validation_status": "informally_verified", "evidence_artifact_ids": ["vr-set-x"]},
                    ],
                    "rationale": "verify lemma with set status aliases",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                claim = conn.execute("SELECT validation_status FROM claims WHERE claim_id=?", ("lemma-x",)).fetchone()
                inf = conn.execute("SELECT validation_status FROM inferences WHERE inference_id=?", ("inf-x",)).fetchone()
            self.assertEqual(claim["validation_status"], "informally_verified")
            self.assertEqual(inf["validation_status"], "informally_verified")

    def test_explicit_validation_and_debt_status_aliases_accept_strict_refutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("verifier-explicit-status-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            self._seed_route_with_inference(store)
            debt_outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "researcher",
                    "target_id": "lemma-x",
                    "operations": [
                        {
                            "op": "add_debt",
                            "debt_id": "debt-lemma-x",
                            "owner_type": "claim",
                            "owner_id": "lemma-x",
                            "debt_type": "missing_proof_or_counterexample",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Prove or refute lemma-x.",
                            "suggested_next_target": "lemma-x",
                        }
                    ],
                    "rationale": "seed prove-or-refute debt",
                },
            )
            self.assertTrue(debt_outcome.accepted, debt_outcome.errors)
            content = {
                "verdict": "correct_refutation",
                "critical_errors": [],
                "gaps": [],
                "blocking_gap": False,
                "summary": "Strict verifier proved the negation of lemma-x.",
            }
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "strict_informal_verifier",
                    "target_id": "lemma-x",
                    "route_id": "route-x",
                    "operations": [
                        {"op": "attach_artifact", "artifact_id": "vr-refute-x", "artifact_type": "verification_report", "metadata": {}, "content": content},
                        {"op": "set_inference_validation_status", "inference_id": "inf-x", "validation_status": "informally_verified", "evidence_artifact_ids": ["vr-refute-x"]},
                        {"op": "set_claim_validation_status", "claim_id": "lemma-x", "validation_status": "refuted", "evidence_artifact_ids": ["vr-refute-x"]},
                        {"op": "set_debt_status", "debt_id": "debt-lemma-x", "status": "resolved", "resolution": "Strict verifier proved the negation."},
                    ],
                    "rationale": "verify refutation with explicit aliases",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                claim = conn.execute("SELECT validation_status FROM claims WHERE claim_id=?", ("lemma-x",)).fetchone()
                inf = conn.execute("SELECT validation_status FROM inferences WHERE inference_id=?", ("inf-x",)).fetchone()
                debt = conn.execute("SELECT status FROM debts WHERE debt_id=?", ("debt-lemma-x",)).fetchone()
            self.assertEqual(claim["validation_status"], "refuted")
            self.assertEqual(inf["validation_status"], "informally_verified")
            self.assertEqual(debt["status"], "resolved")

    def test_report_with_real_gap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("verifier-gap-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            self._seed_route_with_inference(store)
            # A non-empty gaps section must NOT pass the informally_verified gate.
            outcome = apply_patch(store, self._verifier_patch(store, gaps_section="- Missing construction for case d=3."))
            self.assertFalse(outcome.accepted)
            self.assertTrue(any("informally_verified requires" in e for e in outcome.errors))


class Phase2PatchShapeAliasTest(unittest.TestCase):
    def test_attach_artifact_cache_retrieval_card_shape_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-cache-card-shape-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
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
                            "op": "attach_artifact",
                            "artifact_id": "retrieval-card-a",
                            "artifact_type": "cache_retrieval_card",
                            "content_hash": "stable-source-a",
                            "exact_statement": "Source A supplies a method match.",
                            "source_version": "source-a-v1",
                            "applicability": {"classification": "method_match", "target_id": "root"},
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "retrieval-card-b",
                            "artifact_type": "cache_retrieval_card",
                            "content": {
                                "content_hash": "stable-source-b",
                                "exact_statement": "Source B supplies a no-hit audit.",
                                "source_version": "source-b-v1",
                                "applicability": {"classification": "no_useful_result_found", "target_id": "root"},
                            },
                        },
                    ],
                    "rationale": "cache cards emitted through artifact-shaped operations",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                cards = conn.execute("SELECT card_id FROM retrieval_cards ORDER BY card_id").fetchall()
                artifact_count = conn.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_type='cache_retrieval_card'").fetchone()[0]
            self.assertEqual([row[0] for row in cards], ["retrieval-card-a", "retrieval-card-b"])
            self.assertEqual(artifact_count, 0)

    def test_update_route_sets_status_failure_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-update-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            setup = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {"op": "add_route", "route_id": "route-root", "conclusion_claim_id": "root", "relation_to_parent": "sufficient", "strategy": "try route"},
                        {"op": "attach_artifact", "artifact_id": "route-blocker", "artifact_type": "route_obstruction", "content": "Route blocker."},
                    ],
                    "rationale": "seed route",
                },
            )
            self.assertTrue(setup.accepted, setup.errors)

            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 1,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "update_route",
                            "route_id": "route-root",
                            "status": "blocked",
                            "failure_fingerprint": "common maximal subgroup obstruction",
                            "evidence_artifact_ids": ["route-blocker"],
                        }
                    ],
                    "rationale": "block route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                route = conn.execute("SELECT status, failure_fingerprint, evidence_artifact_ids_json FROM routes WHERE route_id=?", ("route-root",)).fetchone()
            self.assertEqual(route["status"], "blocked")
            self.assertEqual(route["failure_fingerprint"], "common maximal subgroup obstruction")
            self.assertIn("route-blocker", json.loads(route["evidence_artifact_ids_json"]))

    def test_add_debt_owner_and_description_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("debt-shape-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    # Agent shape: owner/description/blocking_claim_id, no owner_type/obligation.
                    "operations": [
                        {"op": "add_debt", "debt_id": "d1", "debt_type": "gap", "description": "Missing lemma.", "blocking_claim_id": "root", "suggested_next_target": "root", "owner": "root"}
                    ],
                    "rationale": "debt shape",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute("SELECT owner_type, owner_id, obligation FROM debts WHERE debt_id='d1'").fetchone()
            self.assertEqual(row[0], "claim")
            self.assertEqual(row[1], "root")
            self.assertEqual(row[2], "Missing lemma.")

    def test_add_debt_role_owner_alias_is_repaired_to_route_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("debt-role-owner-route-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
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
                            "artifact_id": "triage-report",
                            "artifact_type": "route_triage_report",
                            "content": "The route is blocked on one bridge lemma.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-bridge",
                            "debt_type": "proof_obstruction",
                            "target_id": "claim-local",
                            "route_id": "route-root",
                            "owner": "researcher",
                            "owner_type": "claim",
                            "owner_id": "researcher",
                            "summary": "Prove the missing bridge lemma.",
                            "severity": "blocking",
                            "status": "active",
                            "suggested_next_target": "researcher",
                            "evidence_artifact_ids": ["triage-report"],
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "label": "Route with advisor debt",
                            "status": "active",
                            "relation_to_parent": "sufficient",
                            "strategy": "Prove the bridge lemma.",
                        },
                    ],
                    "rationale": "advisor emitted role-name owner",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT owner_type, owner_id, obligation, source_artifact_ids_json, suggested_next_target, status FROM debts WHERE debt_id='debt-bridge'"
                ).fetchone()
            self.assertEqual(row[0], "route")
            self.assertEqual(row[1], "route-root")
            self.assertEqual(row[2], "Prove the missing bridge lemma.")
            self.assertIn("triage-report", json.loads(row[3]))
            self.assertEqual(row[4], "route-root")
            self.assertEqual(row[5], "active")

    def test_update_debt_status_aliases_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("debt-status-alias-update-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            created = apply_patch(
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
                            "debt_id": "debt-status",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "gap",
                            "severity": "blocker",
                            "status": "open",
                            "obligation": "Close the gap.",
                        }
                    ],
                    "rationale": "create debt with aliases",
                },
            )
            self.assertTrue(created.accepted, created.errors)
            updated = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "strict_informal_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "update_debt",
                            "debt_id": "debt-status",
                            "severity": "low",
                            "status": "closed",
                        }
                    ],
                    "rationale": "update debt with aliases",
                },
            )
            self.assertTrue(updated.accepted, updated.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute("SELECT severity, status FROM debts WHERE debt_id='debt-status'").fetchone()
            self.assertEqual(tuple(row), ("minor", "resolved"))

    def test_add_debt_route_owner_id_with_wrong_claim_owner_type_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("debt-route-owner-id-inference-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            route_id = "route_claim_order_ideal_by_normal_quotient_surplus"
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
                            "op": "add_route",
                            "route_id": route_id,
                            "conclusion_claim_id": "root",
                            "label": "Order-ideal route",
                            "relation_to_parent": "sufficient",
                            "status": "active",
                            "strategy": "Use a normal quotient surplus argument.",
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt_route_claim_order_ideal_bridge",
                            "owner_type": "claim",
                            "owner_id": route_id,
                            "target_id": "claim_order_ideal_separation_non_simple",
                            "debt_type": "proof_obstruction",
                            "severity": "blocking",
                            "status": "open",
                            "statement": "The route still needs the minimal-normal surplus bridge.",
                            "suggested_next_target": route_id,
                        },
                    ],
                    "rationale": "advisor emitted route-like owner_id with a claim owner_type",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute(
                    "SELECT owner_type, owner_id, status, obligation, suggested_next_target FROM debts WHERE debt_id='debt_route_claim_order_ideal_bridge'"
                ).fetchone()
            self.assertEqual(tuple(row), ("route", route_id, "active", "The route still needs the minimal-normal surplus bridge.", route_id))

    def test_add_debt_role_owner_alias_falls_back_to_patch_target_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("debt-role-owner-target-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
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
                            "op": "add_debt",
                            "debt_id": "debt-root-bridge",
                            "debt_type": "proof_obstruction",
                            "owner": "phd_advisor",
                            "owner_type": "claim",
                            "owner_id": "phd_advisor",
                            "summary": "Root still needs a bridge lemma.",
                            "severity": "blocking",
                            "status": "active",
                        }
                    ],
                    "rationale": "advisor emitted role-name owner without route",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                row = conn.execute("SELECT owner_type, owner_id, obligation FROM debts WHERE debt_id='debt-root-bridge'").fetchone()
            self.assertEqual(tuple(row), ("claim", "root", "Root still needs a bridge lemma."))

    def test_operation_alias_with_nested_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("op-alias-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    # 'operation' (not 'op') + nested 'debt'.
                    "operations": [
                        {"operation": "add_debt", "debt": {"debt_id": "d2", "debt_type": "gap", "obligation": "Nested.", "owner": "root"}}
                    ],
                    "rationale": "op alias nested",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                self.assertIsNotNone(conn.execute("SELECT 1 FROM debts WHERE debt_id='d2'").fetchone())

    def test_attach_artifact_nested_artifact_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("attach-nested-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 0,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {"op": "attach_artifact", "artifact": {"artifact_id": "a-nested", "artifact_type": "research_notebook", "content": "note"}}
                    ],
                    "rationale": "nested artifact",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                self.assertIsNotNone(conn.execute("SELECT 1 FROM artifacts WHERE artifact_id='a-nested'").fetchone())


class Phase2IntegratedDuplicateClaimTest(unittest.TestCase):
    def test_add_claim_rejects_near_restatement_of_integrated_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("integrated-claim-duplicate-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
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
                            "claim_id": "closed-psl2-branch",
                            "kind": "lemma",
                            "statement": (
                                "Let ell>=5 be an odd prime, S=PSL_2(ell), and let Gamma be S when ell=3 mod 4 "
                                "and PGL_2(ell) when ell=1 mod 4. Let |Omega|>1 and let K satisfy "
                                "S^Omega <= K <= Gamma wr P with P transitive on Omega. Then no pair x,y in K "
                                "of orders 2 and ell invariably generates K."
                            ),
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                        }
                    ],
                    "rationale": "seed closed branch",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.execute(
                    """
                    UPDATE claims
                    SET validation_status='informally_verified', lifecycle_status='integrated'
                    WHERE claim_id='closed-psl2-branch'
                    """
                )

            duplicate = apply_patch(
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
                            "claim_id": "new-psl2-restatement",
                            "kind": "lemma",
                            "statement": (
                                "Let ell>=5 be an odd prime, S=PSL_2(ell), and Gamma=S if ell=3 mod 4 "
                                "while Gamma=PGL_2(ell) if ell=1 mod 4. Let Omega have size >1, and let K be "
                                "a finite group with S^Omega <= K <= Gamma wr Sym(Omega) whose top image P is "
                                "transitive on Omega. Then no pair x,y in K with |x|=2 and |y|=ell invariably generates K."
                            ),
                            "parent_ids": ["root"],
                            "root_impact": 0.9,
                        }
                    ],
                    "rationale": "try duplicate closed branch",
                },
            )

            self.assertFalse(duplicate.accepted)
            self.assertIn("duplicate claim", " ".join(duplicate.errors))
            self.assertIn("closed-psl2-branch", " ".join(duplicate.errors))

    def test_add_claim_allows_substantive_extension_of_integrated_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("integrated-claim-extension-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
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
                            "claim_id": "closed-inner-c1",
                            "kind": "lemma",
                            "statement": (
                                "Fix distinct primes p and q and put L=lcm(1,2,...,2max(p,q)). For all sufficiently large "
                                "natural dimensions n, if S=PSp(V) or PSU(V) and S<=Gamma<=Inndiag(S), then the C1 "
                                "stabilizer in Gamma of a nondegenerate L-subspace is proper, maps onto Gamma/S, and "
                                "meets every S-conjugacy class of elements of orders p and q."
                            ),
                            "parent_ids": ["root"],
                            "root_impact": 0.8,
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-closed-inner-c1",
                            "conclusion_claim_id": "closed-inner-c1",
                            "relation_to_parent": "sufficient",
                            "strategy": "seed route",
                        },
                        {
                            "op": "attach_artifact",
                            "artifact_id": "dossier-closed-inner-c1",
                            "artifact_type": "proof_dossier",
                            "metadata": {"claim_id": "closed-inner-c1", "route_id": "route-closed-inner-c1"},
                            "content": "Seed proof dossier.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-closed-inner-c1",
                            "route_id": "route-closed-inner-c1",
                            "conclusion_claim_id": "closed-inner-c1",
                            "evidence_artifact_ids": ["dossier-closed-inner-c1"],
                            "explanation": "seed inference",
                        },
                    ],
                    "rationale": "seed integrated inner C1 claim",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.execute(
                    """
                    UPDATE claims
                    SET validation_status='informally_verified', lifecycle_status='integrated'
                    WHERE claim_id='closed-inner-c1'
                    """
                )
                conn.execute("UPDATE routes SET status='integrated' WHERE route_id='route-closed-inner-c1'")

            extension = apply_patch(
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
                            "claim_id": "new-diagonal-field-c1",
                            "kind": "lemma",
                            "statement": (
                                "Fix distinct primes p,q and put L=lcm(1,2,...,2max(p,q)). For all sufficiently large "
                                "natural dimensions n, let V be a finite symplectic or unitary space, let S=PSp(V) or "
                                "PSU(V), and let S<=Gamma<=P Gamma Sp(V) or P Gamma U(V) have outer image contained in "
                                "the diagonal-field subgroup. Then for a fixed nondegenerate L-subspace W<=V, "
                                "R=N_Gamma(W) maps onto Gamma/S and every element of Gamma of order p or q is "
                                "Gamma-conjugate into R."
                            ),
                            "parent_ids": ["root"],
                            "root_impact": 0.8,
                        }
                    ],
                    "rationale": "new field-semilinear extension",
                },
            )

            self.assertTrue(extension.accepted, extension.errors)

    def test_integration_transition_resolves_connected_debt_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            theorem = "Target theorem."
            store = ProofStateStore("patch-integration-resolves-debt-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem(theorem)
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
                            "artifact_id": "root-proof-dossier",
                            "artifact_type": "proof_dossier",
                            "content": "A complete root proof route.",
                        },
                        {
                            "op": "add_route",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "relation_to_parent": "sufficient",
                            "strategy": "Use the root proof dossier.",
                        },
                        {
                            "op": "add_inference",
                            "inference_id": "inf-root",
                            "route_id": "route-root",
                            "conclusion_claim_id": "root",
                            "premise_claim_ids": [],
                            "validation_status": "plausible",
                            "explanation": "The proof dossier proves the theorem.",
                            "evidence_artifact_ids": ["root-proof-dossier"],
                        },
                        {
                            "op": "add_debt",
                            "debt_id": "debt-root-integration-citation",
                            "owner_type": "claim",
                            "owner_id": "root",
                            "debt_type": "missing_reference",
                            "severity": "blocking",
                            "status": "active",
                            "obligation": "Integration must cite the exact theorem used by the verified route.",
                            "suggested_next_target": "root",
                        },
                    ],
                    "rationale": "seed verified-route candidate with a debt integration can close",
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
                            "artifact_id": "verification-report",
                            "artifact_type": "verification_report",
                            "content": "verdict: informally_verified\ncritical_errors: []\ngaps: []",
                            "metadata": {
                                "verdict": "informally_verified",
                                "verification_report": {"critical_errors": [], "gaps": [], "blocking_gap": False},
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "inference",
                            "target_id": "inf-root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                            "evidence_artifact_ids": ["verification-report"],
                        },
                    ],
                    "rationale": "strict verifier accepts the route",
                },
            )
            self.assertTrue(verified.accepted, verified.errors)

            integrated = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 2,
                    "actor_role": "integration_verifier",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "attach_artifact",
                            "artifact_id": "integration-report",
                            "artifact_type": "integration_report",
                            "content": "The verified route integrates and closes the root citation debt.",
                            "metadata": {
                                "integrates": True,
                                "resolved_debt_ids": ["debt-root-integration-citation"],
                                "root_alignment": {
                                    "relation_to_root": "exact",
                                    "target_statement": theorem,
                                    "proved_statement": theorem,
                                    "implication_verified": True,
                                    "hidden_assumptions": False,
                                    "extra_assumptions": [],
                                },
                            },
                        },
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "lifecycle",
                            "new_status": "integrated",
                            "route_id": "route-root",
                            "evidence_artifact_ids": ["integration-report"],
                            "resolved_debt_ids": ["debt-root-integration-citation"],
                        },
                    ],
                    "rationale": "integration verifier accepts and closes connected debt",
                },
            )
            self.assertTrue(integrated.accepted, integrated.errors)

            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                debt_row = conn.execute("SELECT status, resolution_evidence_json FROM debts WHERE debt_id = ?", ("debt-root-integration-citation",)).fetchone()
                route_row = conn.execute("SELECT status FROM routes WHERE route_id = ?", ("route-root",)).fetchone()
            self.assertEqual(debt_row["status"], "resolved")
            self.assertEqual(route_row["status"], "integrated")
            self.assertIn("closed_by_integrated_route", debt_row["resolution_evidence_json"])


class Phase2StatusTransitionGraphIdAliasTest(unittest.TestCase):
    """propose_status_transition must accept concrete graph-id fields as target aliases.

    Observed live (2026-07-03, problem 20.2): the integration verifier emitted
    claim_id/route_id instead of target_id and the whole integrate patch was
    rejected for a missing target.
    """

    def test_claim_id_wins_over_route_id_and_sets_target_type(self) -> None:
        from agents.generation.phase2.patches import _normalize_status_transition_fields

        op = {
            "op": "propose_status_transition",
            "claim_id": "clm-x",
            "route_id": "route-x",
            "lifecycle_status": "integrated",
            "new_status": "integrated",
            "status_type": "lifecycle",
        }
        _normalize_status_transition_fields(op)
        self.assertEqual(op["target_id"], "clm-x")
        self.assertEqual(op["target_type"], "claim")

    def test_inference_and_route_aliases(self) -> None:
        from agents.generation.phase2.patches import _normalize_status_transition_fields

        inference_op = {"op": "propose_status_transition", "inference_id": "inf-x", "new_status": "informally_verified"}
        _normalize_status_transition_fields(inference_op)
        self.assertEqual(inference_op["target_id"], "inf-x")
        self.assertEqual(inference_op["target_type"], "inference")

        route_op = {"op": "propose_status_transition", "route_id": "route-x", "new_status": "blocked"}
        _normalize_status_transition_fields(route_op)
        self.assertEqual(route_op["target_id"], "route-x")
        self.assertEqual(route_op["target_type"], "route")

    def test_explicit_target_id_is_untouched(self) -> None:
        from agents.generation.phase2.patches import _normalize_status_transition_fields

        op = {
            "op": "propose_status_transition",
            "target_type": "inference",
            "target_id": "inf-y",
            "claim_id": "clm-x",
            "new_status": "informally_verified",
        }
        _normalize_status_transition_fields(op)
        self.assertEqual(op["target_id"], "inf-y")
        self.assertEqual(op["target_type"], "inference")

    def test_plain_status_field_aliases_to_new_status(self) -> None:
        from agents.generation.phase2.patches import _normalize_status_transition_fields

        op = {
            "op": "propose_status_transition",
            "target_type": "claim",
            "target_id": "clm-x",
            "status_type": "lifecycle",
            "status": "integrated",
        }
        _normalize_status_transition_fields(op)
        self.assertEqual(op["new_status"], "integrated")
        # Non-status junk in `status` is not aliased.
        junk = {"op": "propose_status_transition", "target_id": "clm-x", "status": "done"}
        _normalize_status_transition_fields(junk)
        self.assertNotIn("new_status", junk)

    def test_preflight_flags_missing_new_status(self) -> None:
        from agents.generation.phase2.patches import preflight_patch_errors

        patch = {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "p",
            "base_revision": 3,
            "actor_role": "integration_verifier",
            "target_id": "clm-x",
            "operations": [
                {"op": "propose_status_transition", "target_type": "claim", "target_id": "clm-x", "status_type": "lifecycle"}
            ],
            "rationale": "integrate",
        }
        errors = preflight_patch_errors(patch, "integration_verifier")
        self.assertTrue(errors)
        self.assertIn("missing new_status", errors[0])


class Phase2RootAlignmentMatcherTest(unittest.TestCase):
    ROOT = (
        "# Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type\n\n"
        "## Problem\n\n"
        "Let G be a permutation group; define the k-closure as usual.\n\n"
        "**Question (Problem 20.2).** Are there any nonabelian simple groups of Lie type\n"
        "which are totally 3-closed?\n\n"
        "## Instructions\n\n"
        "Treat this as a serious research problem.\n"
    )

    def test_h1_title_files_accept_problem_section_and_question_paragraph(self) -> None:
        from agents.generation.phase2.patches import _root_alignment_target_matches

        self.assertTrue(_root_alignment_target_matches(self.ROOT, self.ROOT))
        question = "**Question (Problem 20.2).** Are there any nonabelian simple groups of Lie type\nwhich are totally 3-closed?"
        self.assertTrue(_root_alignment_target_matches(question, self.ROOT))
        section = "Let G be a permutation group; define the k-closure as usual.\n\n" + question
        self.assertTrue(_root_alignment_target_matches(section, self.ROOT))
        self.assertTrue(
            _root_alignment_target_matches("Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type", self.ROOT)
        )
        # Paraphrases still fail.
        self.assertFalse(
            _root_alignment_target_matches(
                "Does there exist a totally 3-closed nonabelian simple group of Lie type?", self.ROOT
            )
        )


class Phase2PreflightPatchTest(unittest.TestCase):
    def _verifier_patch(self, *, verdict: str, gaps: list, with_transition: bool = True) -> dict:
        operations: list[dict] = [
            {
                "op": "attach_artifact",
                "artifact_id": "vr-1",
                "artifact_type": "verification_report",
                "content": "report",
                "metadata": {"verdict": verdict, "verification_report": {"verdict": verdict, "critical_errors": [], "gaps": gaps, "blocking_gap": None}},
            }
        ]
        if with_transition:
            operations.append(
                {
                    "op": "propose_status_transition",
                    "target_type": "claim",
                    "target_id": "lemma-x",
                    "status_type": "validation",
                    "new_status": "informally_verified",
                    "evidence_artifact_ids": ["vr-1"],
                }
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "problem_id": "p",
            "base_revision": 3,
            "actor_role": "strict_informal_verifier",
            "target_id": "lemma-x",
            "operations": operations,
            "rationale": "verify",
        }

    def test_clean_report_passes_preflight(self) -> None:
        from agents.generation.phase2.patches import preflight_patch_errors

        errors = preflight_patch_errors(self._verifier_patch(verdict="correct", gaps=[]), "strict_informal_verifier")
        self.assertEqual(errors, [])

    def test_pass_report_passes_preflight(self) -> None:
        from agents.generation.phase2.patches import preflight_patch_errors

        errors = preflight_patch_errors(self._verifier_patch(verdict="pass", gaps=[]), "strict_informal_verifier")
        self.assertEqual(errors, [])

    def test_gappy_report_with_verified_transition_fails_preflight(self) -> None:
        from agents.generation.phase2.patches import preflight_patch_errors

        errors = preflight_patch_errors(
            self._verifier_patch(verdict="correct", gaps=["missing normalizer reduction"]),
            "strict_informal_verifier",
        )
        self.assertTrue(errors)
        self.assertIn("gaps", errors[0])

    def test_non_verifier_proposing_verified_fails_preflight(self) -> None:
        from agents.generation.phase2.patches import preflight_patch_errors

        patch = self._verifier_patch(verdict="correct", gaps=[])
        patch["actor_role"] = "researcher"
        errors = preflight_patch_errors(patch, "researcher")
        self.assertTrue(errors)
        self.assertIn("may not propose", errors[0])

    def test_report_without_transition_passes_preflight(self) -> None:
        from agents.generation.phase2.patches import preflight_patch_errors

        errors = preflight_patch_errors(
            self._verifier_patch(verdict="not_verified", gaps=["gap"], with_transition=False),
            "strict_informal_verifier",
        )
        self.assertEqual(errors, [])

    def test_blocking_verification_report_marks_claim_challenged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("patch-blocking-report-status-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("Prove the target theorem.")
            patch = self._verifier_patch(
                verdict="not_verified",
                gaps=["the normalizer step is missing"],
                with_transition=False,
            )
            patch["problem_id"] = store.problem_id
            patch["base_revision"] = 0
            patch["target_id"] = "root"
            patch["operations"][0]["metadata"]["verification_report"]["blocking_gap"] = True
            outcome = apply_patch(store, patch)
            state = store.get_state()

        self.assertTrue(outcome.accepted, outcome.errors)
        root = next(row for row in state["claims"] if row["claim_id"] == "root")
        self.assertEqual(root["validation_status"], "challenged")

    def test_external_evidence_is_left_to_apply_patch(self) -> None:
        from agents.generation.phase2.patches import preflight_patch_errors

        patch = self._verifier_patch(verdict="correct", gaps=[])
        patch["operations"] = [patch["operations"][1]]
        patch["operations"][0]["evidence_artifact_ids"] = ["vr-already-in-store"]
        errors = preflight_patch_errors(patch, "strict_informal_verifier")
        self.assertEqual(errors, [])


class Phase2StaleRebaseRetryTest(unittest.TestCase):
    def _seed(self, store: ProofStateStore) -> None:
        outcome = apply_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": 0,
                "actor_role": "researcher",
                "target_id": "root",
                "operations": [
                    {"op": "add_claim", "claim_id": "lemma-a", "kind": "lemma", "statement": "A.", "parent_ids": ["root"]},
                ],
                "rationale": "seed",
            },
        )
        self.assertTrue(outcome.accepted, outcome.errors)

    def _bump_with_unrelated_patch(self, store: ProofStateStore) -> None:
        outcome = apply_patch(
            store,
            {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": store.get_revision(),
                "actor_role": "phd_advisor",
                "target_id": "root",
                "operations": [
                    {
                        "op": "attach_artifact",
                        "artifact_id": f"adv-note-{store.get_revision()}",
                        "artifact_type": "advisor_report",
                        "content": f"advisor note at revision {store.get_revision()}",
                        "metadata": {"recommended_next_action": "continue"},
                    }
                ],
                "rationale": "intervening advisor note",
            },
        )
        self.assertTrue(outcome.accepted, outcome.errors)

    def test_row_disjoint_additive_patch_is_rebased(self) -> None:
        from agents.generation.phase2.patches import apply_patch_with_stale_retry

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("stale-rebase-ok-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            self._seed(store)
            stale_base = store.get_revision()
            self._bump_with_unrelated_patch(store)
            self._bump_with_unrelated_patch(store)
            stale_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": stale_base,
                "actor_role": "researcher",
                "target_id": "lemma-a",
                "operations": [
                    {"op": "attach_artifact", "artifact_id": "dossier-b", "artifact_type": "proof_dossier", "content": "Proof of B."},
                    {"op": "add_claim", "claim_id": "lemma-b", "kind": "lemma", "statement": "B.", "parent_ids": ["root"], "evidence_artifact_ids": ["dossier-b"]},
                    {"op": "add_debt", "debt_id": "debt-b", "owner_type": "claim", "owner_id": "lemma-b", "debt_type": "gap", "severity": "blocking", "status": "active", "obligation": "prove B fully"},
                ],
                "rationale": "long researcher session finishing after companions landed",
            }
            outcome = apply_patch_with_stale_retry(store, stale_patch)
            self.assertTrue(outcome.accepted, outcome.errors)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                self.assertIsNotNone(conn.execute("SELECT 1 FROM claims WHERE claim_id='lemma-b'").fetchone())
                events = conn.execute("SELECT payload_json FROM events WHERE event_type='stale_rebase_applied'").fetchall()
            self.assertEqual(len(events), 1)

    def test_row_overlap_declines_rebase(self) -> None:
        from agents.generation.phase2.patches import apply_patch_with_stale_retry

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("stale-rebase-overlap-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            self._seed(store)
            stale_base = store.get_revision()
            # Intervening patch touches lemma-a itself.
            outcome = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "villain",
                    "target_id": "lemma-a",
                    "operations": [
                        {"op": "propose_status_transition", "target_type": "claim", "target_id": "lemma-a", "status_type": "validation", "new_status": "challenged", "evidence_artifact_ids": []},
                    ],
                    "rationale": "villain challenge",
                },
            )
            self.assertTrue(outcome.accepted, outcome.errors)
            stale_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": stale_base,
                "actor_role": "researcher",
                "target_id": "lemma-a",
                "operations": [
                    {"op": "propose_status_transition", "target_type": "claim", "target_id": "lemma-a", "status_type": "validation", "new_status": "plausible", "evidence_artifact_ids": []},
                ],
                "rationale": "stale status proposal against a row that changed",
            }
            outcome = apply_patch_with_stale_retry(store, stale_patch)
            self.assertFalse(outcome.accepted)
            self.assertTrue(any("stale patch" in e for e in outcome.errors))

    def test_verifying_transition_is_never_rebased(self) -> None:
        from agents.generation.phase2.patches import apply_patch_with_stale_retry

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("stale-rebase-verify-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            self._seed(store)
            stale_base = store.get_revision()
            self._bump_with_unrelated_patch(store)
            stale_patch = {
                "schema_version": SCHEMA_VERSION,
                "problem_id": store.problem_id,
                "base_revision": stale_base,
                "actor_role": "strict_informal_verifier",
                "target_id": "lemma-a",
                "operations": [
                    {"op": "propose_status_transition", "target_type": "claim", "target_id": "lemma-a", "status_type": "validation", "new_status": "informally_verified", "evidence_artifact_ids": []},
                ],
                "rationale": "stale verification must not silently rebase",
            }
            outcome = apply_patch_with_stale_retry(store, stale_patch)
            self.assertFalse(outcome.accepted)


class Phase2PatchRejectionEventTest(unittest.TestCase):
    def test_stale_and_guard_rejections_are_persisted_as_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore("rejection-event-test", generation_root=Path(tmpdir) / "generation")
            store.init_problem("root")
            stale = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": 99,
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [{"op": "attach_artifact", "artifact_id": "a1", "artifact_type": "proof_dossier", "content": "x"}],
                    "rationale": "stale on purpose",
                },
            )
            self.assertFalse(stale.accepted)
            guard = apply_patch(
                store,
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_id": store.problem_id,
                    "base_revision": store.get_revision(),
                    "actor_role": "researcher",
                    "target_id": "root",
                    "operations": [
                        {
                            "op": "propose_status_transition",
                            "target_type": "claim",
                            "target_id": "root",
                            "status_type": "validation",
                            "new_status": "informally_verified",
                        }
                    ],
                    "rationale": "researcher cannot verify",
                },
            )
            self.assertFalse(guard.accepted)
            with sqlite3.connect(store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT payload_json FROM events WHERE event_type='patch_rejected' ORDER BY event_id"
                ).fetchall()
            self.assertEqual(len(rows), 2)
            payloads = [json.loads(row["payload_json"]) for row in rows]
            self.assertEqual(payloads[0]["kind"], "stale_base_revision")
            self.assertIn("stale patch", payloads[0]["errors"][0])
            self.assertEqual(payloads[1]["kind"], "guard_rejected")
            self.assertEqual(payloads[1]["actor_role"], "researcher")


if __name__ == "__main__":
    unittest.main()
