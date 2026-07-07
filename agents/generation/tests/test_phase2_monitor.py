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
from agents.generation.phase2.monitor import _make_handler, build_monitor_payload, start_background_monitor
from agents.generation.phase2.models import utc_now
from agents.generation.phase2.store import ProofStateStore


class MonitorTest(unittest.TestCase):
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
