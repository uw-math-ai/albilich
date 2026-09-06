import base64
import json
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from argparse import Namespace
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path

from agents.generation.phase2.cli import _maybe_start_run_dashboard
from agents.generation.phase2.console import _run_timeline
import agents.generation.phase2.monitor as monitor_mod
from agents.generation.phase2.monitor import (
    INDEX_HTML,
    _claim_verification_history,
    _make_handler,
    _monitor_refresh_interval_seconds,
    _publication_workflow_payload,
    build_monitor_payload,
    start_background_monitor,
)
from agents.generation.phase2.models import utc_now
from agents.generation.phase2.steering import MAX_STEERING_TEXT_BYTES
from agents.generation.phase2.store import ProofStateStore


class MonitorTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is needed for dashboard JavaScript regressions")
    def test_math_startup_retry_queue_and_detached_nodes(self) -> None:
        start = INDEX_HTML.index("function typesetPending(")
        source = INDEX_HTML[start:INDEX_HTML.index("window.addEventListener('load'", start)]
        script = r"""
const assert = require('node:assert/strict');
let mathJaxQueue = Promise.resolve();
const window = {};
function node(){
  return {pending: true, failed: false, isConnected: true,
    removeAttribute(){this.pending=false;},
    classList: {add(){}, remove(){}}};
}
const first = node(), retired = node(), second = node();
const root = items => ({querySelectorAll: () => items.filter(n => n.pending)});
const document = root([first, retired]);
""" + source + r"""
(async () => {
  await typesetPending(document);
  assert(first.pending, 'early poll must remain eligible for startup retry');
  let active = 0, calls = [];
  window.MathJax = {typesetPromise: async nodes => {
    assert.equal(++active, 1, 'typesetting must be serialized');
    calls.push(nodes);
    await new Promise(resolve => setTimeout(resolve, 5));
    active--;
  }};
  const a = typesetPending(document);
  retired.isConnected = false;
  const b = typesetPending(root([second]));
  await Promise.all([a,b]);
  assert.deepEqual(calls, [[first],[second]]);
  assert(!first.pending);
})().catch(error => {console.error(error); process.exitCode=1;});
"""
        subprocess.run([shutil.which("node"), "-e", script], check=True, capture_output=True, text=True)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed for dashboard JavaScript regressions")
    def test_display_math_stays_paired_across_markdown_blank_lines(self) -> None:
        math_start = INDEX_HTML.index("const UNICODE_MATH_GLYPHS")
        math_source = INDEX_HTML[math_start:INDEX_HTML.index("let mathJaxQueue", math_start)]
        start = INDEX_HTML.index("function readableDocumentHTML(")
        source = INDEX_HTML[start:INDEX_HTML.index("async function openArtifact(", start)]
        script = r"""
const assert = require('node:assert/strict');
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
""" + math_source + source + r"""
const block = String.raw`\[
\displaystyle\sum_{i=1}^n i

- x < y
\]`;
const dollars = '$$\\displaystyle\\frac{1}{2}\n\n+z$$';
const html = readableDocumentHTML('# Heading\n\nBefore\n'+block+'\nAfter\n'+dollars);
assert.equal((html.match(/class="math-block"/g)||[]).length, 2);
assert(html.includes(esc(block)));
assert(html.includes(esc(dollars)));
assert(!html.includes('•'));
assert(html.includes('<h3>'));
assert(!readableDocumentHTML('\\[x <script>alert(1)</script>\\]').includes('<script>'));
assert(readableDocumentHTML('\\documentclass{article}').startsWith('<pre>'));
"""
        subprocess.run([shutil.which("node"), "-e", script], check=True, capture_output=True, text=True)

    def test_verification_history_recovers_legacy_blocking_report_target(self) -> None:
        state = {
            "runs": [{"run_id": "verify-lemma", "target_id": "claim-lemma"}],
            "artifacts": [
                {
                    "artifact_id": "verification-gap",
                    "artifact_type": "verification_report",
                    "run_id": "verify-lemma",
                    "state_revision": 12,
                    "metadata_json": json.dumps(
                        {
                            "verdict": "gap_found",
                            "verification_report": {
                                "critical_errors": [],
                                "gaps": ["missing premise"],
                                "blocking_gap": True,
                            },
                        }
                    ),
                }
            ],
        }

        history = _claim_verification_history(state)

        self.assertTrue(history["claim-lemma"]["blocking_gap"])
        self.assertEqual(history["claim-lemma"]["latest_state_revision"], 12)

    def test_authoritative_refresh_is_decoupled_from_browser_polling(self) -> None:
        with patch.dict(os.environ, {"ALBILICH_MONITOR_REFRESH_INTERVAL_SECONDS": ""}):
            self.assertEqual(_monitor_refresh_interval_seconds(3000), 60.0)
            self.assertEqual(_monitor_refresh_interval_seconds(120000), 120.0)

    def test_dashboard_serializes_slow_browser_refresh_work(self) -> None:
        self.assertIn("let tickInFlight = false;", INDEX_HTML)
        self.assertIn("if (paused || tickInFlight || document.hidden) return;", INDEX_HTML)
        self.assertIn("signal:controller.signal", INDEX_HTML)
        self.assertIn("await typesetPending(document);", INDEX_HTML)
        self.assertIn("let mathJaxQueue = Promise.resolve();", INDEX_HTML)
        self.assertIn("let tailFetchInFlight = false;", INDEX_HTML)

    def test_dashboard_releases_replaced_math_and_skips_unchanged_heavy_renders(self) -> None:
        clear_call = "window.MathJax.typesetClear([node])"
        replace_call = "node.innerHTML = html;"
        self.assertIn(clear_call, INDEX_HTML)
        self.assertLess(INDEX_HTML.index(clear_call), INDEX_HTML.index(replace_call))
        self.assertIn("let lastProofRevision = null;", INDEX_HTML)
        self.assertIn("const proofStateChanged = forceHeavy || lastProofRevision !== revisionKey;", INDEX_HTML)
        self.assertIn('document.addEventListener("visibilitychange"', INDEX_HTML)
        self.assertGreaterEqual(INDEX_HTML.count("if (document.hidden) return;"), 4)
        self.assertIn("if (proofStateChanged){\n      renderArtifacts(p.artifact_catalog);", INDEX_HTML)
        self.assertEqual(INDEX_HTML.count("renderArtifacts(p.artifact_catalog)"), 1)
        self.assertIn("rmode.adversarial_reviewer || rmode.villain", INDEX_HTML)
        self.assertNotIn("budget spend excludes cached input", INDEX_HTML)
        self.assertIn(".artifact-shell { grid-template-columns: minmax(0, 1fr); }", INDEX_HTML)
        self.assertIn(".artifact-list { min-width: 0;", INDEX_HTML)

    def test_orphan_display_delimiters_are_rendered_as_literal_tokens(self) -> None:
        self.assertIn("const literalDelimiters = part", INDEX_HTML)
        self.assertIn(r"String.raw`\(\backslash\mathtt{]}\)`", INDEX_HTML)
        self.assertIn(r"String.raw`\(\backslash\mathtt{[}\)`", INDEX_HTML)

    def _store(self, tmpdir: str) -> ProofStateStore:
        store = ProofStateStore("monitor-test", generation_root=Path(tmpdir) / "generation")
        store.init_problem("Prove the root theorem.")
        return store

    def test_build_payload_has_monitor_metadata_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            payload = build_monitor_payload(store)
            self.assertIn("snapshot", payload)
            self.assertIn("_monitor", payload)
            self.assertEqual(payload["_monitor"]["problem_id"], "monitor-test")
            self.assertIn(payload["_monitor"]["source"], {"store", "store+console"})
            self.assertIn("live", payload["_monitor"])

    def test_publication_workflow_exposes_paper_and_referee_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            artifact_dir = store.state_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            proof_path = artifact_dir / "proof.md"
            paper_path = artifact_dir / "paper.tex"
            paper_pdf_path = artifact_dir / "paper.pdf"
            report_path = artifact_dir / "report.md"
            proof_path.write_text("A complete proof.", encoding="utf-8")
            paper_path.write_text("\\documentclass{article}\\begin{document}A paper.\\end{document}", encoding="utf-8")
            paper_pdf_path.write_bytes(b"%PDF-1.4\n")
            report_path.write_text("[accept]\n\nThe proof and paper are correct.", encoding="utf-8")
            now = utc_now()
            report_metadata = {
                "title": "Journal referee report",
                "findings": [],
                "reviewed_paper_artifact_id": "paper-1",
            }
            with store.connect() as conn:
                conn.execute(
                    """INSERT INTO artifacts(
                           artifact_id, artifact_type, path, sha256, producer_role, run_id,
                           state_revision, content_summary, metadata_json, created_at
                       ) VALUES ('proof-1', 'final_proof', ?, 'proof-sha', 'writer', '', 1,
                                 'The root theorem is proved.', '{}', ?)""",
                    (str(proof_path), now),
                )
                conn.execute(
                    """INSERT INTO artifacts(
                           artifact_id, artifact_type, path, sha256, producer_role, run_id,
                           state_revision, content_summary, metadata_json, created_at
                       ) VALUES ('paper-1', 'final_paper', ?, 'paper-sha', 'writer', '', 2,
                                 'A journal-ready proof of the root theorem.', ?, ?)""",
                    (
                        str(paper_path),
                        json.dumps(
                            {
                                "title": "A proof of the root theorem",
                                "publication_workflow": "writer_referee",
                                "paper_version": 1,
                                "certificate_artifact_id": "proof-1",
                                "pdf_path": str(paper_pdf_path),
                            }
                        ),
                        now,
                    ),
                )
                conn.execute(
                    """INSERT INTO artifacts(
                           artifact_id, artifact_type, path, sha256, producer_role, run_id,
                           state_revision, content_summary, metadata_json, created_at
                       ) VALUES ('report-1', 'referee_report', ?, 'report-sha', 'referee', '', 3,
                                 'The referee accepts the paper.', ?, ?)""",
                    (str(report_path), json.dumps(report_metadata), now),
                )
                conn.execute(
                    """INSERT INTO publication_reviews(
                           review_id, round_number, paper_artifact_id, certificate_artifact_id,
                           verdict, decision_token, affected_route_id, falsified_step,
                           mathematical_evidence, finding_count, metadata_json, state_revision,
                           created_at, escalated_at
                       ) VALUES ('report-1', 1, 'paper-1', 'proof-1', 'accept', '[accept]',
                                 '', '', '', 0, ?, 3, ?, '')""",
                    (json.dumps(report_metadata), now),
                )
                conn.commit()

            workflow = _publication_workflow_payload(store)

            self.assertEqual("accepted", workflow["status"])
            self.assertEqual("complete", workflow["current_role"])
            self.assertEqual(1, workflow["paper_count"])
            self.assertEqual("[accept]", workflow["papers"][0]["reviews"][0]["decision_token"])
            self.assertEqual("/api/paper?id=paper-1", workflow["papers"][0]["pdf_url"])
            payload = build_monitor_payload(store)
            self.assertEqual("accepted", payload["publication_workflow"]["status"])
            self.assertIn("✓ PUBLICATION ACCEPTED", INDEX_HTML)
            self.assertIn('String((publication||{}).status || "") === "accepted"', INDEX_HTML)
            self.assertIn('"publication_accepted"', INDEX_HTML)

        self.assertIn('id="publicationCard"', INDEX_HTML)
        self.assertIn("function renderPublicationWorkflow", INDEX_HTML)
        self.assertIn("renderPublicationWorkflow(p.publication_workflow)", INDEX_HTML)
        self.assertIn("Writer</div>", INDEX_HTML)
        self.assertIn("Referee</div>", INDEX_HTML)

    def test_live_writer_overrides_derived_awaiting_referee_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            artifact_dir = store.state_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            paper_path = artifact_dir / "paper.tex"
            paper_path.write_text("\\documentclass{article}\\begin{document}Paper.\\end{document}", encoding="utf-8")
            with store.connect() as conn:
                conn.execute(
                    """INSERT INTO artifacts(
                           artifact_id, artifact_type, path, sha256, producer_role, run_id,
                           state_revision, content_summary, metadata_json, created_at
                       ) VALUES ('paper-live', 'final_paper', ?, 'paper-sha', 'writer', '', 2,
                                 'A paper under revision.', ?, ?)""",
                    (
                        str(paper_path),
                        json.dumps(
                            {
                                "publication_workflow": "writer_referee",
                                "paper_version": 1,
                                "publication_only_test": True,
                            }
                        ),
                        utc_now(),
                    ),
                )
                conn.commit()
            (store.state_dir / "albilich_run_console.json").write_text(
                json.dumps(
                    {
                        "live_logs": [
                            {
                                "run_id": "writer-live",
                                "actor_role": "writer",
                                "mode": "write",
                                "status": "running",
                                "updated_at": utc_now(),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            workflow = build_monitor_payload(store)["publication_workflow"]

            self.assertEqual("writer_working", workflow["status"])
            self.assertEqual("writer", workflow["current_role"])
            self.assertTrue(workflow["publication_only_test"])
            self.assertIn("pauses this publication-only test", workflow["loop_policy"])

    def test_open_case_counts_exclude_debts_covered_by_integrated_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            now = utc_now()
            with store.connect() as conn:
                conn.execute(
                    """INSERT INTO claims(
                           claim_id, kind, statement, normalized_statement, fingerprint,
                           hypotheses, conditions_json, validation_status, lifecycle_status,
                           root_impact, reduction_depth, parent_ids_json, source_ids_json,
                           tags_json, evidence_artifact_ids_json, created_at, updated_at
                       ) VALUES (?, 'lemma', ?, ?, 'fp-integrated-lemma', '', '[]',
                                 'informally_verified', 'integrated', 0.8, 1, '[\"root\"]',
                                 '[]', '[]', '[]', ?, ?)""",
                    (
                        "integrated-lemma",
                        "The completed branch lemma.",
                        "the completed branch lemma",
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """INSERT INTO debts(
                           debt_id, owner_type, owner_id, obligation, fingerprint, debt_type,
                           severity, status, first_seen, last_seen, repeated_count,
                           source_artifact_ids_json, suggested_next_target, resolution_evidence_json
                       ) VALUES (?, 'claim', 'integrated-lemma', ?, 'fp-stale-debt', 'gap',
                                 'blocking', 'active', ?, ?, 1, '[]', 'integrated-lemma', '{}')""",
                    ("debt-integrated-lemma", "An old obligation retained for audit history.", now, now),
                )
                conn.commit()

            payload = build_monitor_payload(store)

        self.assertEqual(payload["snapshot"]["open_case_count"], 0)
        self.assertEqual(payload["snapshot"]["open_blocking_case_count"], 0)
        self.assertEqual(payload["snapshot"]["ledger_active_debt_count"], 1)
        self.assertEqual(payload["snapshot"]["ledger_blocking_debt_count"], 1)
        self.assertFalse(any(payload["open_cases"].values()))
        self.assertEqual(payload["snapshot"]["root_local_blocking_debt_count"], 0)

    def test_open_case_counts_match_root_debt_to_integrated_claim_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            now = utc_now()
            with store.connect() as conn:
                conn.execute(
                    """INSERT INTO claims(
                           claim_id, kind, statement, normalized_statement, fingerprint,
                           hypotheses, conditions_json, validation_status, lifecycle_status,
                           root_impact, reduction_depth, parent_ids_json, source_ids_json,
                           tags_json, evidence_artifact_ids_json, created_at, updated_at
                       ) VALUES ('claim-psl-bridge', 'lemma', 'The completed PSL bridge.',
                                 'the completed psl bridge', 'fp-psl-bridge', '', '[]',
                                 'informally_verified', 'integrated', 0.8, 1, '["root"]',
                                 '[]', '[]', '[]', ?, ?)""",
                    (now, now),
                )
                conn.execute(
                    """INSERT INTO debts(
                           debt_id, owner_type, owner_id, obligation, fingerprint, debt_type,
                           severity, status, first_seen, last_seen, repeated_count,
                           source_artifact_ids_json, suggested_next_target, resolution_evidence_json
                       ) VALUES ('debt-psl-bridge', 'claim', 'root',
                                 'Prove the PSL bridge in all outer cosets.', 'fp-psl-debt', 'gap',
                                 'blocking', 'active', ?, ?, 1, '[]', 'root', '{}')""",
                    (now, now),
                )
                conn.commit()

            payload = build_monitor_payload(store)

        self.assertEqual(payload["snapshot"]["open_case_count"], 0)
        self.assertEqual(payload["snapshot"]["open_blocking_case_count"], 0)
        self.assertEqual(payload["snapshot"]["ledger_active_debt_count"], 1)
        self.assertFalse(any(payload["open_cases"].values()))

    def test_dashboard_keeps_refuted_discarded_and_resolved_debts_visible_but_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            now = utc_now()
            with store.connect() as conn:
                for status in ("active", "refuted", "discarded", "resolved"):
                    conn.execute(
                        """INSERT INTO artifacts(
                               artifact_id, artifact_type, path, sha256, producer_role,
                               run_id, state_revision, content_summary, metadata_json, created_at
                           ) VALUES (?, 'verification_report', '', ?, 'strict_informal_verifier',
                                     'monitor-fixture', 0, ?, '{}', ?)""",
                        (
                            f"evidence-{status}",
                            "a" * 64,
                            f"Evidence classifying the obligation as {status}.",
                            now,
                        ),
                    )
                    conn.execute(
                        """INSERT INTO debts(
                               debt_id, owner_type, owner_id, obligation, fingerprint, debt_type,
                               severity, status, first_seen, last_seen, repeated_count,
                               source_artifact_ids_json, suggested_next_target, resolution_evidence_json
                           ) VALUES (?, 'claim', 'root', ?, ?, 'gap', 'blocking', ?, ?, ?, 1,
                                     '[]', 'root', ?)""",
                        (
                            f"debt-{status}",
                            f"The {status} obligation.",
                            f"fp-{status}",
                            status,
                            now,
                            now,
                            json.dumps(
                                {
                                    "resolution_note": f"Classified as {status}.",
                                    "resolution_evidence_artifact_ids": [f"evidence-{status}"],
                                }
                            ),
                        ),
                    )
                conn.commit()

            payload = build_monitor_payload(store)

        self.assertEqual(sum(map(len, payload["open_cases"].values())), 1)
        self.assertEqual(
            {group: [row["debt_id"] for row in rows] for group, rows in payload["closed_cases"].items()},
            {
                "Refuted": ["debt-refuted"],
                "Discarded": ["debt-discarded"],
                "Resolved": ["debt-resolved"],
            },
        )
        self.assertEqual(payload["closed_cases"]["Refuted"][0]["resolution_note"], "Classified as refuted.")
        self.assertEqual(
            payload["closed_cases"]["Refuted"][0]["resolution_evidence_artifact_ids"],
            ["evidence-refuted"],
        )
        self.assertIn("Proof Obligations", INDEX_HTML)
        self.assertIn("Closed proof obligations", INDEX_HTML)
        self.assertIn("renderDebts(p.open_cases, p.closed_cases);", INDEX_HTML)

    def test_token_ui_distinguishes_processed_from_budget_spend(self) -> None:
        self.assertIn('cached/input*100', INDEX_HTML)
        self.assertIn('>Processed</th>', INDEX_HTML)
        self.assertIn('Gross input plus output, including cached input. Reasoning is already part of output', INDEX_HTML)

    def test_dashboard_exposes_approach_portfolio_contributions_and_controls(self) -> None:
        self.assertIn('id="approachPortfolio"', INDEX_HTML)
        self.assertIn("function renderApproachPortfolio", INDEX_HTML)
        self.assertIn("Root effect", INDEX_HTML)
        self.assertIn("Decisive test", INDEX_HTML)
        self.assertIn("50% exploit", INDEX_HTML)
        self.assertIn("30% explore", INDEX_HTML)
        self.assertIn("20% adversarial", INDEX_HTML)
        self.assertIn("Generate new approaches", INDEX_HTML)
        self.assertIn("Ideas are advisory; research questions are nonblocking; proof obligations remain exact.", INDEX_HTML)
        self.assertIn("Portfolio refresh queued", INDEX_HTML)
        self.assertIn("Root effect${alignmentPending?' (stale)':''}", INDEX_HTML)
        self.assertIn("Steering impact", INDEX_HTML)
        self.assertIn("brainstorming now", INDEX_HTML)
        self.assertIn("retry queued", INDEX_HTML)
        self.assertIn("produced no usable portfolio", INDEX_HTML)

    def test_steering_ui_distinguishes_queued_processing_and_processed(self) -> None:
        self.assertIn('`${processing} processing`', INDEX_HTML)
        self.assertIn('m.delivery_status === "processing"', INDEX_HTML)
        self.assertIn('status === "processed"', INDEX_HTML)
        self.assertIn("portfolio refresh pending", INDEX_HTML)
        self.assertIn("portfolio aligned", INDEX_HTML)

    def test_run_timeline_marks_integration_failures_recovered_by_later_success(self) -> None:
        runs = [
            {
                "run_id": "reject-1", "actor_role": "integration_verifier", "mode": "integrate",
                "target_id": "claim-a", "route_id": "route-a", "status": "patch_rejected",
            },
            {
                "run_id": "reject-other", "actor_role": "integration_verifier", "mode": "integrate",
                "target_id": "claim-b", "route_id": "route-b", "status": "patch_rejected",
            },
            {
                "run_id": "accept-1", "actor_role": "integration_verifier", "mode": "integrate",
                "target_id": "claim-a", "route_id": "route-a", "status": "completed",
            },
        ]

        timeline = _run_timeline(runs)

        self.assertTrue(timeline[0]["failure_recovered"])
        self.assertEqual(timeline[0]["recovered_by_run_id"], "accept-1")
        self.assertNotIn("failure_recovered", timeline[1])
        self.assertIn("recovered later", INDEX_HTML)

    def test_run_timeline_marks_strict_verifier_rejection_recovered_by_accepted_replay(self) -> None:
        runs = [
            {
                "run_id": "strict-reject", "actor_role": "strict_informal_verifier", "mode": "prove",
                "target_id": "claim-a", "route_id": "route-a", "status": "patch_rejected",
            },
            {
                "run_id": "villain-success", "actor_role": "villain", "mode": "refute",
                "target_id": "claim-a", "route_id": "route-a", "status": "completed",
            },
            {
                "run_id": "strict-recovery", "actor_role": "strict_informal_verifier", "mode": "prove",
                "target_id": "claim-a", "route_id": "route-a", "status": "completed",
            },
        ]

        timeline = _run_timeline(runs)

        self.assertTrue(timeline[0]["failure_recovered"])
        self.assertEqual(timeline[0]["recovered_by_run_id"], "strict-recovery")
        self.assertNotIn("failure_recovered", timeline[1])

    def test_run_timeline_distinguishes_stream_stall_from_deadline_timeout(self) -> None:
        timeline = _run_timeline(
            [
                {
                    "run_id": "transport-stall",
                    "actor_role": "researcher",
                    "mode": "prove",
                    "status": "timeout",
                    "failure_kind": "stale_stream",
                },
                {
                    "run_id": "deadline",
                    "actor_role": "researcher",
                    "mode": "prove",
                    "status": "timeout",
                    "failure_kind": "deadline",
                },
            ]
        )

        self.assertEqual(timeline[0]["status"], "timeout")
        self.assertEqual(timeline[0]["display_status"], "stream stalled")
        self.assertIn("not the configured session time limit", timeline[0]["status_detail"])
        self.assertEqual(timeline[1]["display_status"], "time limit reached")
        self.assertIn("configured Albilich time limit", timeline[1]["status_detail"])
        self.assertIn("r.display_status || r.status", INDEX_HTML)

    def test_claim_ledger_prioritizes_retired_lifecycle_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            with store.connect() as conn:
                conn.execute(
                    """UPDATE claims
                       SET lifecycle_status = 'superseded', validation_status = 'informally_verified'
                       WHERE claim_id = 'root'"""
                )
                conn.commit()

            payload = build_monitor_payload(store)

        root = next(row for row in payload["claims"] if row["claim_id"] == "root")
        self.assertEqual(root["validation_status"], "informally_verified")
        self.assertEqual(root["display_validation_status"], "superseded")
        self.assertFalse(root["verified"])
        self.assertTrue(root["retired"])
        self.assertEqual(payload["verified_claim_total"], 0)
        self.assertEqual(payload["snapshot"]["current_claim_count"], 0)
        self.assertEqual(payload["snapshot"]["retired_claim_count"], 1)
        self.assertEqual(payload["snapshot"]["verified_claim_count"], 0)
        self.assertEqual(root["reduction_depth"], 0)
        self.assertIn("superseded · stronger result", INDEX_HTML)
        self.assertIn("Retired / superseded / falsified claims", INDEX_HTML)
        self.assertIn("Current proof tree", INDEX_HTML)
        self.assertIn("status-superseded", INDEX_HTML)
        self.assertIn("status-plausible", INDEX_HTML)
        self.assertIn("status-active", INDEX_HTML)
        self.assertIn('class=\"claim-tree-children\"', INDEX_HTML)

    def test_claim_ledger_exposes_superseding_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            now = utc_now()
            with store.connect() as conn:
                conn.execute(
                    """INSERT INTO claims(
                           claim_id, kind, statement, normalized_statement, fingerprint,
                           hypotheses, conditions_json, validation_status, lifecycle_status,
                           root_impact, reduction_depth, parent_ids_json, source_ids_json,
                           tags_json, evidence_artifact_ids_json, created_at, updated_at
                       ) VALUES (?, 'lemma', ?, 'a strictly stronger lower bound',
                                 'fp-stronger', '', '[]', 'informally_verified', 'integrated',
                                 1.0, 1, '[\"root\"]', '[]', '[]', '[]', ?, ?)""",
                    ("claim-stronger", "A strictly stronger lower bound.", now, now),
                )
                conn.execute(
                    """INSERT INTO claims(
                           claim_id, kind, statement, normalized_statement, fingerprint,
                           hypotheses, conditions_json, validation_status, lifecycle_status,
                           root_impact, reduction_depth, parent_ids_json, source_ids_json,
                           tags_json, evidence_artifact_ids_json, created_at, updated_at
                       ) VALUES (?, 'lemma', ?, 'a weaker lower bound', 'fp-weaker', '', '[]',
                                 'informally_verified', 'superseded', 0.5, 1, '[\"root\"]',
                                 '[]', '[]', '[]', ?, ?)""",
                    ("claim-weaker", "A weaker lower bound.", now, now),
                )
                conn.execute(
                    """INSERT INTO artifacts(
                           artifact_id, artifact_type, path, sha256, producer_role, run_id,
                           state_revision, content_summary, metadata_json, created_at
                       ) VALUES (?, 'advisor_report', '', '', 'phd_advisor', '', 1,
                                 'Supersession audit.', ?, ?)""",
                    (
                        "advisor-lower-bound-supersession",
                        json.dumps({
                            "superseded_claim_ids": ["claim-weaker"],
                            "replacement_claim_id": "claim-stronger",
                        }),
                        now,
                    ),
                )
                conn.commit()

            payload = build_monitor_payload(store)

        weaker = next(row for row in payload["claims"] if row["claim_id"] == "claim-weaker")
        self.assertEqual(weaker["superseded_by_claim_ids"], ["claim-stronger"])
        self.assertIn('relationPill("superseded by"', INDEX_HTML)

    def test_payload_exposes_bottleneck_frontier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            now = "2026-01-01T00:00:00+00:00"
            with store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO debts(
                        debt_id, owner_type, owner_id, obligation, fingerprint, debt_type,
                        severity, status, first_seen, last_seen, repeated_count,
                        source_artifact_ids_json, suggested_next_target, resolution_evidence_json
                    ) VALUES (?, 'claim', 'root', ?, 'fp-bottleneck', 'blocking_bridge',
                              'blocking', 'active', ?, ?, 3, '[]', 'root', '{}')
                    """,
                    ("debt-root-bottleneck", "Prove or refute the exact bridge lemma.", now, now),
                )
                conn.commit()

            payload = build_monitor_payload(store)
            frontier = payload["bottleneck_frontier"]

        self.assertTrue(frontier["locked"])
        self.assertEqual(frontier["current_bottleneck"]["debt_id"], "debt-root-bottleneck")
        self.assertEqual(frontier["current_bottleneck"]["repeated_count"], 3)

    def test_dry_run_console_write_does_not_mark_run_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            (store.state_dir / "albilich_run_console.json").write_text(
                json.dumps(
                    {
                        "current_invocation": [
                            {
                                "step": 1,
                                "execution_phase": "planned",
                                "primary_action_summary": {"mode": "retrieve", "target_id": "root"},
                            }
                        ],
                        "live_logs": [],
                    }
                ),
                encoding="utf-8",
            )

            payload = build_monitor_payload(store)

        self.assertFalse(payload["_monitor"]["live"])
        self.assertEqual(payload["_monitor"]["run_state"], "idle")

    def test_terminal_invocation_overrides_recent_child_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            run_dir = store.state_dir / "workflow_runs" / "v1_recent_child"
            run_dir.mkdir(parents=True)
            (run_dir / "codex.log").write_text("recent completed child output", encoding="utf-8")
            (store.state_dir / "albilich_run_console.json").write_text(
                json.dumps(
                    {
                        "current_invocation": [
                            {
                                "step": 1,
                                "execution_phase": "completed",
                                "patch_summary": "accepted=True",
                            },
                            {
                                "step": 2,
                                "stop_reason": "workflow step limit reached (1 steps)",
                                "terminal_classification": "step_limited_partial",
                            },
                        ],
                        "live_logs": [
                            {
                                "run_id": "v1_recent_child",
                                "status": "completed",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = build_monitor_payload(store)

        self.assertFalse(payload["_monitor"]["live"])
        self.assertEqual(payload["_monitor"]["run_state"], "stopped")

    def test_recent_live_child_telemetry_overrides_quiet_child_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            run_dir = store.state_dir / "workflow_runs" / "v1_quiet_running_child"
            run_dir.mkdir(parents=True)
            log_path = run_dir / "codex.log"
            log_path.write_text("child sampled quietly after this write", encoding="utf-8")
            old = time.time() - 240
            os.utime(log_path, (old, old))
            live_update = {
                "run_id": "v1_quiet_running_child",
                "status": "running",
                "updated_at": utc_now(),
                "elapsed_seconds": 240,
                "usage": {"total_tokens": 12345},
            }
            (store.state_dir / "albilich_run_console.json").write_text(
                json.dumps(
                    {
                        "current_invocation": [
                            {
                                "step": 1,
                                "execution_phase": "running",
                                "live_session_updates": [live_update],
                            }
                        ],
                        "live_logs": [live_update],
                    }
                ),
                encoding="utf-8",
            )

            payload = build_monitor_payload(store)

        self.assertTrue(payload["_monitor"]["live"])
        self.assertEqual(payload["_monitor"]["run_state"], "running")

    def test_durable_run_status_reconciles_stale_running_live_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            now = utc_now()
            with store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO runs(
                        run_id, actor_role, mode, target_id, route_id, state_revision,
                        context_revision, session_id, model_profile, model, reasoning_effort,
                        search_setting, search_intent, sandbox_setting, budget_requested,
                        input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens,
                        total_tokens, wall_time_seconds, peak_memory_mb, status,
                        prompt_context_hash, output_artifact_ids_json, error_artifact_id,
                        created_at, researcher_work_mode, work_mode_source, failure_kind
                    ) VALUES (
                        'finished-integration', 'integration_verifier', 'integrate', 'claim-a',
                        'route-a', 1, 1, '', 'default', 'fake', 'xhigh', 'disabled', '',
                        'workspace-write', 1000, 10, 0, 5, 0, 15, 2.0, 1.0, 'completed',
                        '', '[]', '', ?, '', '', ''
                    )
                    """,
                    (now,),
                )
                conn.commit()
            stale_integration = {
                "run_id": "finished-integration",
                "actor_role": "integration_verifier",
                "mode": "integrate",
                "status": "running",
                "phase": "heartbeat",
                "updated_at": now,
            }
            current_researcher = {
                "run_id": "current-researcher",
                "actor_role": "researcher",
                "mode": "prove",
                "status": "running",
                "phase": "heartbeat",
                "updated_at": now,
            }
            (store.state_dir / "albilich_run_console.json").write_text(
                json.dumps(
                    {
                        "current_invocation": [
                            {"step": 1, "live_session_updates": [stale_integration]},
                            {"step": 2, "live_session_updates": [current_researcher]},
                        ],
                        "live_logs": [stale_integration, current_researcher],
                    }
                ),
                encoding="utf-8",
            )

            payload = build_monitor_payload(store)

        live_by_run = {row["run_id"]: row for row in payload["live_logs"]}
        self.assertEqual(live_by_run["finished-integration"]["status"], "completed")
        self.assertEqual(live_by_run["finished-integration"]["phase"], "completed")
        self.assertEqual(live_by_run["current-researcher"]["status"], "running")
        self.assertIn("const ll = latestInvocationSessions(payload);", INDEX_HTML)
        self.assertIn("liveStatus(l.status) && liveUpdateRecent(l)", INDEX_HTML)

    def test_endpoints_serve_html_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            handler = _make_handler(store, poll_ms=2000)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
                    html = resp.read().decode("utf-8")
                    self.assertEqual(resp.status, 200)
                self.assertIn("Albilich", html)
                self.assertIn("monitor-test", html)
                self.assertIn("2000", html)  # poll interval injected
                self.assertIn("sessionCards", html)
                self.assertIn("session-card", html)
                self.assertIn("Bottleneck Frontier", html)
                self.assertIn("bottleneckFrontier", html)
                self.assertIn("Proof Graph", html)
                self.assertIn("proofGraph", html)
                self.assertNotIn("__STEERING_TOKEN_JSON__", html)
                self.assertNotIn("__SCRIPT_NONCE__", html)
                self.assertNotIn("cdn.jsdelivr.net", html)
                self.assertIn("Content-Security-Policy", resp.headers)
                self.assertIn("script-src 'nonce-", resp.headers["Content-Security-Policy"])
                scripts = re.findall(r"<script\b([^>]*)>", html)
                self.assertEqual(len(scripts), 3)
                nonce = re.search(r"script-src 'nonce-([^']+)'", resp.headers["Content-Security-Policy"])[1]
                self.assertTrue(all(f'nonce="{nonce}"' in tag for tag in scripts))
                self.assertEqual(re.findall(r'<script[^>]+src="([^"]+)"', html), [monitor_mod.MATHJAX_ASSET_URL])
                self.assertIn("typeset: false", html)
                self.assertIn("options: {enableMenu: false}", html)
                packages = re.search(r"packages: \[([^\]]+)\]", html)[1]
                for disabled in ("require", "autoload", "html", "setoptions"):
                    self.assertNotIn(f"'{disabled}'", packages)

                with urllib.request.urlopen(f"http://127.0.0.1:{port}{monitor_mod.MATHJAX_ASSET_URL}") as resp:
                    renderer = resp.read()
                    self.assertEqual(resp.status, 200)
                    self.assertEqual(resp.headers.get_content_type(), "application/javascript")
                    self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(hashlib.sha256(renderer).hexdigest(), "a4354ff94fd868aea0cc6eaaa79a57fda0588646fc46ee3700a349ee0a11cbe6")
                digest = base64.b64encode(hashlib.sha384(renderer).digest()).decode("ascii")
                self.assertIn(f'integrity="sha384-{digest}"', html)
                for path in ("/static/../monitor.py", "/static/mathjax-3.2.2/../LICENSE", "/static/unknown.js"):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(f"http://127.0.0.1:{port}{path}")
                    self.assertEqual(error.exception.code, 404)

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/console") as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(resp.status, 200)
                self.assertEqual(data["_monitor"]["problem_id"], "monitor-test")
                self.assertIn("snapshot", data)
                self.assertIn("proof_graph", data)
                self.assertIn("bottleneck_frontier", data)

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz") as resp:
                    self.assertEqual(resp.status, 200)
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/files") as resp:
                    files = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(resp.status, 200)
                self.assertIn("files", files)
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/proof-graph") as resp:
                    graph = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(resp.status, 200)
                self.assertIn("nodes", graph)
                self.assertIn("edges", graph)
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_steering_post_requires_instance_token_and_has_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            token = "monitor-test-steering-token"
            handler = _make_handler(store, poll_ms=2000, steering_token=token)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{port}/api/steer"
            body = json.dumps({"text": "Check the endpoint case first."}).encode(
                "utf-8"
            )
            try:
                missing = urllib.request.Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(missing)
                self.assertEqual(403, rejected.exception.code)
                rejected.exception.close()

                oversized = urllib.request.Request(
                    url,
                    data=b"{}",
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(64 * 1024 + 1),
                        "X-Albilich-Steering-Token": token,
                    },
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(oversized)
                self.assertEqual(413, rejected.exception.code)
                rejected.exception.close()

                oversized_text = urllib.request.Request(
                    url,
                    data=json.dumps(
                        {"text": "x" * (MAX_STEERING_TEXT_BYTES + 1)}
                    ).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Albilich-Steering-Token": token,
                    },
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(oversized_text)
                self.assertEqual(413, rejected.exception.code)
                rejected.exception.close()

                wrong_alignment_type = urllib.request.Request(
                    url,
                    data=json.dumps(
                        {
                            "text": "Check the endpoint case first.",
                            "requires_approach_alignment": "false",
                        }
                    ).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Albilich-Steering-Token": token,
                    },
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(wrong_alignment_type)
                self.assertEqual(400, rejected.exception.code)
                rejected.exception.close()

                accepted = urllib.request.Request(
                    url,
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Albilich-Steering-Token": token,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(accepted) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/steering"
                ) as response:
                    steering_view = json.loads(response.read().decode("utf-8"))
                self.assertEqual("verified_event_journal", steering_view["source"])
                self.assertEqual(
                    "Check the endpoint case first.",
                    steering_view["recent_inbox"][0]["text"],
                )
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_console_endpoint_coalesces_payload_rebuilds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            payload = {"_monitor": {"problem_id": "monitor-test"}, "snapshot": {"revision": 0}}
            with patch.object(monitor_mod, "build_monitor_payload", return_value=payload) as build:
                handler = _make_handler(store, poll_ms=2000)
                httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = httpd.server_address[1]
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    for _ in range(2):
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/console") as resp:
                            self.assertEqual(json.loads(resp.read().decode("utf-8")), payload)
                    self.assertEqual(build.call_count, 1)
                finally:
                    httpd.shutdown()
                    httpd.server_close()

    def test_console_endpoint_serves_persisted_state_while_refreshing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            persisted = {
                "problem_id": "monitor-test",
                "snapshot": {"revision": 7},
                "live_logs": [],
                "current_invocation": [],
            }
            (store.state_dir / "albilich_run_console.json").write_text(json.dumps(persisted), encoding="utf-8")
            refresh_started = threading.Event()
            release_refresh = threading.Event()

            def slow_refresh(_store: ProofStateStore) -> dict:
                refresh_started.set()
                release_refresh.wait(timeout=5)
                return {"_monitor": {"source": "store"}, "snapshot": {"revision": 8}}

            with patch.object(monitor_mod, "build_monitor_payload", side_effect=slow_refresh):
                handler = _make_handler(store, poll_ms=2000)
                httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = httpd.server_address[1]
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/console") as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(data["snapshot"]["revision"], 7)
                    self.assertEqual(data["_monitor"]["source"], "console-fallback")
                    self.assertTrue(refresh_started.wait(timeout=1))
                finally:
                    release_refresh.set()
                    httpd.shutdown()
                    httpd.server_close()

    def test_proof_graph_marks_verifier_ready_routes_and_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            now = "2026-01-01T00:00:00+00:00"
            with store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO claims(
                        claim_id, kind, statement, normalized_statement, fingerprint, hypotheses,
                        conditions_json, validation_status, lifecycle_status, root_impact,
                        reduction_depth, parent_ids_json, source_ids_json, tags_json,
                        evidence_artifact_ids_json, created_at, updated_at
                    ) VALUES (?, 'lemma', ?, ?, ?, '', '[]', 'untested', 'active', 0.7, 1, ?, '[]', '[]', '[]', ?, ?)
                    """,
                    ("lemma-a", "Lemma A closes the root route.", "lemma a closes root route", "fp-lemma-a", '["root"]', now, now),
                )
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        artifact_id, artifact_type, path, sha256, producer_role, run_id,
                        state_revision, content_summary, metadata_json, created_at
                    ) VALUES (?, 'proof_dossier', ?, 'sha', 'researcher', 'run-1', 1, ?, '{}', ?)
                    """,
                    ("artifact-proof", str(store.state_dir / "artifacts" / "artifact-proof.md"), "Proof dossier summary.", now),
                )
                conn.execute(
                    """
                    INSERT INTO routes(
                        route_id, conclusion_claim_id, label, strategy, status, relation_to_parent,
                        assumptions_json, conditions_json, evidence_artifact_ids_json,
                        failure_fingerprint, created_at, updated_at
                    ) VALUES (?, 'lemma-a', 'Route A', 'Prove lemma A from root evidence.', 'active', 'sufficient', '[]', '[]', ?, '', ?, ?)
                    """,
                    ("route-a", '["artifact-proof"]', now, now),
                )
                conn.execute(
                    """
                    INSERT INTO routes(
                        route_id, conclusion_claim_id, label, strategy, status, relation_to_parent,
                        assumptions_json, conditions_json, evidence_artifact_ids_json,
                        failure_fingerprint, created_at, updated_at
                    ) VALUES (?, 'root', 'Route B', 'Clean direct root route.', 'active', 'sufficient', '[]', '[]', ?, '', ?, ?)
                    """,
                    ("route-b", '["artifact-proof"]', now, now),
                )
                conn.execute(
                    """
                    INSERT INTO inferences(
                        inference_id, route_id, conclusion_claim_id, explanation, conditions_json,
                        condition_claim_ids_json, validation_status, evidence_artifact_ids_json,
                        created_at, updated_at
                    ) VALUES (?, 'route-a', 'lemma-a', 'Inference needs strict verification.', '[]', '[]', 'untested', ?, ?, ?)
                    """,
                    ("inf-a", '["artifact-proof"]', now, now),
                )
                conn.execute(
                    """
                    INSERT INTO inferences(
                        inference_id, route_id, conclusion_claim_id, explanation, conditions_json,
                        condition_claim_ids_json, validation_status, evidence_artifact_ids_json,
                        created_at, updated_at
                    ) VALUES (?, 'route-b', 'root', 'Clean route needs strict verification.', '[]', '[]', 'untested', ?, ?, ?)
                    """,
                    ("inf-b", '["artifact-proof"]', now, now),
                )
                conn.execute(
                    "INSERT INTO inference_premises(inference_id, premise_claim_id, position) VALUES ('inf-a', 'root', 0)"
                )
                conn.execute(
                    """
                    INSERT INTO debts(
                        debt_id, owner_type, owner_id, obligation, fingerprint, debt_type,
                        severity, status, first_seen, last_seen, repeated_count,
                        source_artifact_ids_json, suggested_next_target, resolution_evidence_json
                    ) VALUES (?, 'route', 'route-a', 'Strict verifier has not checked this route.', 'fp-debt', 'verifier_gap',
                              'blocking', 'active', ?, ?, 2, ?, 'lemma-a', '{}')
                    """,
                    ("debt-route-a", now, now, '["artifact-proof"]'),
                )
                conn.commit()

            payload = build_monitor_payload(store)
            graph = payload["proof_graph"]

        self.assertEqual(graph["summary"]["verifier_ready_route_count"], 1)
        self.assertEqual(graph["summary"]["blocking_debt_count"], 1)
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertIn("route:route-a", node_ids)
        self.assertIn("route:route-b", node_ids)
        self.assertIn("debt:debt-route-a", node_ids)
        self.assertIn("artifact:artifact-proof", node_ids)
        self.assertTrue(graph["summary"]["artifact_nodes_compact"])
        artifact_node = next(node for node in graph["nodes"] if node["id"] == "artifact:artifact-proof")
        self.assertEqual(artifact_node["label"], "A1 R")
        self.assertEqual(artifact_node["full_label"], "artifact-proof")
        self.assertEqual(artifact_node["artifact_ref"], "A1")
        self.assertEqual(artifact_node["producer_role_code"], "R")
        route_node = next(node for node in graph["nodes"] if node["id"] == "route:route-a")
        self.assertFalse(route_node["verifier_ready"])
        self.assertIn("active_blocking_debt", route_node["verifier_missing_checks"])
        self.assertEqual(route_node["blocking_debt_count"], 1)
        route_b_node = next(node for node in graph["nodes"] if node["id"] == "route:route-b")
        self.assertTrue(route_b_node["verifier_ready"])
        self.assertEqual(route_b_node["verifier_readiness_level"], "verifier_ready")
        self.assertTrue(
            any(
                edge["source"] == "route:route-a"
                and edge["target"] == "debt:debt-route-a"
                and edge["strength"] == "blocking"
                for edge in graph["edges"]
            )
        )
        claims = {row["claim_id"]: row for row in payload["claims"]}
        self.assertEqual(claims["root"]["contains_subclaim_ids"], ["lemma-a"])
        self.assertEqual(claims["root"]["supports_claim_ids"], ["lemma-a"])
        self.assertEqual(claims["lemma-a"]["subclaim_of_claim_ids"], ["root"])
        self.assertEqual(claims["lemma-a"]["supported_by_claim_ids"], ["root"])
        self.assertTrue(
            any(
                edge["source"] == "claim:root"
                and edge["target"] == "claim:lemma-a"
                and edge["relation"] == "supports claim"
                for edge in graph["edges"]
            )
        )
        self.assertIn("subclaim of", INDEX_HTML)
        self.assertIn("supported by", INDEX_HTML)

    def test_tail_endpoint_and_path_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            (store.state_dir / "phase2_report.md").write_text("REPORT TAIL CONTENT", encoding="utf-8")
            handler = _make_handler(store, poll_ms=2000)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tail?path=phase2_report.md&bytes=4000") as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self.assertIn("REPORT TAIL CONTENT", data["text"])
                # Path traversal must be rejected.
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tail?path=../../../etc/hosts&bytes=100") as resp:
                    blocked = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(blocked["text"], "")
                self.assertIn("error", blocked)
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_cumulative_paper_and_artifact_endpoints_are_safe_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            artifact_dir = store.state_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            tex_path = artifact_dir / "hmt-rev-10.tex"
            pdf_path = artifact_dir / "hmt-rev-10.pdf"
            dossier_path = artifact_dir / "proof-dossier.md"
            tex_path.write_text("\\documentclass{article}\\begin{document}Partial theorem.\\end{document}", encoding="utf-8")
            pdf_bytes = b"%PDF-1.4\n% dashboard fixture\n"
            pdf_path.write_bytes(pdf_bytes)
            dossier_path.write_text(
                "# A useful lemma\n\nIf $G$ is cyclic, then every subgroup of $G$ is normal.",
                encoding="utf-8",
            )
            sidecar_dir = store.state_dir / "hmt_snapshots"
            sidecar_dir.mkdir(parents=True, exist_ok=True)
            sidecar_tex = sidecar_dir / "hmt-sidecar.tex"
            sidecar_pdf = sidecar_dir / "hmt-sidecar.pdf"
            sidecar_tex.write_text("\\documentclass{article}\\begin{document}Sidecar.\\end{document}", encoding="utf-8")
            sidecar_pdf_bytes = b"%PDF-1.4\n% sidecar fixture\n"
            sidecar_pdf.write_bytes(sidecar_pdf_bytes)
            (sidecar_dir / "catalog.json").write_text(
                json.dumps(
                    {
                        "catalog_version": 1,
                        "papers": [
                            {
                                "artifact_id": "hmt-sidecar",
                                "artifact_type": "human_readable_mathematical_text",
                                "title": "A non-blocking sidecar paper",
                                "source_revision": 20,
                                "sequence": 2,
                                "created_at": utc_now(),
                                "tex_path": str(sidecar_tex),
                                "pdf_path": str(sidecar_pdf),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            now = utc_now()
            with store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        artifact_id, artifact_type, path, sha256, producer_role, run_id,
                        state_revision, content_summary, metadata_json, created_at
                    ) VALUES (?, ?, ?, 'sha-hmt', 'writer', 'writer-1', 10, ?, ?, ?)
                    """,
                    (
                        "hmt-rev-10",
                        "human_readable_mathematical_text",
                        str(tex_path),
                        "The cyclic case satisfies the target property.",
                        json.dumps(
                            {
                                "title": "Partial classification in the cyclic case",
                                "source_revision": 10,
                                "sequence": 1,
                                "pdf_status": "compiled",
                                "pdf_path": str(pdf_path),
                            }
                        ),
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO artifacts(
                        artifact_id, artifact_type, path, sha256, producer_role, run_id,
                        state_revision, content_summary, metadata_json, created_at
                    ) VALUES (?, 'proof_dossier', ?, ?, 'researcher', 'research-1', 9, ?, ?, ?)
                    """,
                    (
                        "proof-dossier",
                        str(dossier_path),
                        hashlib.sha256(dossier_path.read_bytes()).hexdigest(),
                        "Every subgroup of a cyclic group is normal.",
                        json.dumps({"title": "Normality of subgroups of a cyclic group"}),
                        now,
                    ),
                )
                conn.commit()

            handler = _make_handler(store, poll_ms=2000)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/papers") as response:
                    papers = json.loads(response.read().decode("utf-8"))["papers"]
                self.assertEqual(len(papers), 2)
                self.assertEqual(papers[0]["source_revision"], 10)
                self.assertEqual(papers[0]["title"], "Partial classification in the cyclic case")
                self.assertTrue(papers[1]["non_blocking"])
                self.assertEqual(papers[1]["title"], "A non-blocking sidecar paper")

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/artifacts") as response:
                    artifacts = json.loads(response.read().decode("utf-8"))["artifacts"]
                self.assertEqual({row["artifact_id"] for row in artifacts}, {"hmt-rev-10", "proof-dossier"})
                dossier_card = next(row for row in artifacts if row["artifact_id"] == "proof-dossier")
                self.assertEqual(dossier_card["display_title"], "Normality of subgroups of a cyclic group")

                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/paper?id=hmt-rev-10"
                ) as response:
                    self.assertEqual(response.headers.get_content_type(), "application/pdf")
                    self.assertEqual(response.read(), pdf_bytes)

                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/paper?id=hmt-sidecar"
                ) as response:
                    self.assertEqual(response.headers.get_content_type(), "application/pdf")
                    self.assertEqual(response.read(), sidecar_pdf_bytes)

                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/artifact?id=proof-dossier"
                ) as response:
                    document = json.loads(response.read().decode("utf-8"))
                self.assertEqual(document["title"], "Normality of subgroups of a cyclic group")
                self.assertIn("every subgroup of $G$", document["content"])
                self.assertEqual("verified", document["integrity_status"])

                dossier_path.write_text("tampered dashboard bytes", encoding="utf-8")
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/artifact?id=proof-dossier"
                ) as response:
                    tampered_document = json.loads(response.read().decode("utf-8"))
                self.assertEqual("", tampered_document["content"])
                self.assertEqual("invalid", tampered_document["integrity_status"])

                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/paper?id=proof-dossier"
                    )
                self.assertEqual(rejected.exception.code, 404)
                rejected.exception.close()
            finally:
                httpd.shutdown()
                httpd.server_close()

        self.assertIn('id="paperFrame"', INDEX_HTML)
        self.assertIn('id="paperSelect"', INDEX_HTML)
        self.assertIn("Mathematical Artifact Library", INDEX_HTML)
        self.assertNotIn("https://cdn.jsdelivr.net", INDEX_HTML)
        self.assertIn("function latexCompat", INDEX_HTML)
        self.assertIn("function typesetPending", INDEX_HTML)
        self.assertIn("function setStableHTML", INDEX_HTML)
        self.assertIn('.math-tex[data-math-pending="1"]', INDEX_HTML)
        self.assertIn("UNICODE_MATH_GLYPHS", INDEX_HTML)
        self.assertIn("mathHTML(a.mathematical_statement)", INDEX_HTML)
        self.assertIn("mathHTML(r.conclusion_statement)", INDEX_HTML)

    def test_background_monitor_starts_on_ephemeral_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            monitor = start_background_monitor(store, port=0, open_browser=False, poll_ms=1000)
            try:
                self.assertTrue(monitor.thread.is_alive())
                self.assertIn("monitor-test", monitor.thread.name)
                with urllib.request.urlopen(f"{monitor.url}healthz") as resp:
                    self.assertEqual(resp.status, 200)
            finally:
                monitor.stop()

        self.assertFalse(monitor.thread.is_alive())

    def test_background_monitor_refuses_non_loopback_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            with self.assertRaisesRegex(ValueError, "loopback"):
                start_background_monitor(
                    store,
                    host="0.0.0.0",
                    port=0,
                    open_browser=False,
                )

    def test_run_dashboard_helper_is_enabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            args = Namespace(
                serve_dashboard=True,
                dashboard_host="127.0.0.1",
                dashboard_port=8765,
                dashboard_interval=3.0,
                open_dashboard=False,
            )

            with patch("agents.generation.phase2.cli.start_background_monitor") as start:
                start.return_value.url = "http://127.0.0.1:8765/"
                start.return_value.host = "127.0.0.1"
                start.return_value.port = 8765
                info, handle = _maybe_start_run_dashboard(args, store)

        self.assertIs(handle, start.return_value)
        self.assertTrue(info["enabled"])
        self.assertEqual(info["url"], "http://127.0.0.1:8765/")
        start.assert_called_once()

    def test_run_dashboard_helper_reports_stale_default_port_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._store(tmpdir)
            args = Namespace(
                serve_dashboard=True,
                dashboard_host="127.0.0.1",
                dashboard_port=8765,
                dashboard_interval=3.0,
                open_dashboard=False,
            )

            with patch("agents.generation.phase2.cli._probe_dashboard_problem", return_value="old/problem"):
                with patch("agents.generation.phase2.cli.start_background_monitor") as start:
                    start.return_value.url = "http://127.0.0.1:8766/"
                    start.return_value.host = "127.0.0.1"
                    start.return_value.port = 8766
                    info, handle = _maybe_start_run_dashboard(args, store)

        self.assertIs(handle, start.return_value)
        self.assertTrue(info["enabled"])
        self.assertEqual(info["url"], "http://127.0.0.1:8766/")
        self.assertEqual(info["requested_url"], "http://127.0.0.1:8765/")
        self.assertTrue(info["requested_port_occupied"])
        self.assertEqual(info["existing_problem_id"], "old/problem")
        self.assertIn("old/problem", info["warning"])


if __name__ == "__main__":
    unittest.main()
