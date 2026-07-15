import json
import os
import tempfile
import threading
import time
import unittest
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
    build_monitor_payload,
    start_background_monitor,
)
from agents.generation.phase2.models import utc_now
from agents.generation.phase2.store import ProofStateStore


class MonitorTest(unittest.TestCase):
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

    def test_token_ui_distinguishes_processed_from_budget_spend(self) -> None:
        self.assertIn('cached/input*100', INDEX_HTML)
        self.assertIn('>Processed</th>', INDEX_HTML)
        self.assertIn('budget spend excludes cached input and includes reasoning', INDEX_HTML)

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
