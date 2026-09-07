from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.generation.phase2.scheduler import _root_alignment_audit_candidates
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_operator_patch


class RootAlignmentAuditTests(unittest.TestCase):
    def state(self):
        before, audited = "2026-09-07T01:00:00+00:00", "2026-09-07T02:00:00+00:00"
        return {
            "run_count": 80, "recent_runs": [],
            "claims": [{"claim_id": cid, "updated_at": before} for cid in ("root", "lemma", "premise", "unrelated")],
            "routes": [{"route_id": "route", "conclusion_claim_id": "lemma", "updated_at": before}],
            "inferences": [{"inference_id": "inf", "route_id": "route", "premise_claim_ids": ["premise"], "updated_at": before}],
            "audit_artifacts": [{
                "artifact_id": "audit", "artifact_type": "root_alignment_audit",
                "producer_role": "integration_verifier", "created_at": audited,
                "metadata_json": json.dumps({"claim_id": "lemma", "route_id": "route"}),
            }],
        }

    def candidates(self, state):
        with patch("agents.generation.phase2.scheduler.route_scoreboard", return_value=[
            {"route_id": "route", "scoreboard_status": "verified_part"},
        ]):
            return _root_alignment_audit_candidates(state)

    def test_unchanged_audit_does_not_repeat_at_later_cadences(self):
        state = self.state()
        for count in (80, 88, 160):
            state["run_count"] = count
            self.assertEqual([], self.candidates(state))
        state["claims"][-1]["updated_at"] = "2026-09-07T03:00:00+00:00"
        self.assertEqual([], self.candidates(state))

    def test_changed_root_route_or_recursive_dependency_reopens_audit(self):
        for table, index in (("claims", 0), ("claims", 1), ("claims", 2), ("routes", 0), ("inferences", 0)):
            with self.subTest(table=table, index=index):
                state = copy.deepcopy(self.state())
                state[table][index]["updated_at"] = "2026-09-07T03:00:00+00:00"
                self.assertEqual(1, len(self.candidates(state)))

    def test_unaudited_route_and_untrusted_report_do_not_suppress_audit(self):
        state = {**self.state(), "audit_artifacts": []}
        self.assertEqual(1, len(self.candidates(state)))
        state = self.state()
        state["audit_artifacts"][0]["producer_role"] = "researcher"
        self.assertEqual(1, len(self.candidates(state)))

    def test_scheduler_snapshot_retains_alignment_audits(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofStateStore("audit-history", generation_root=Path(tmp))
            store.init_problem("Root theorem.")
            result = apply_operator_patch(store, {
                "schema_version": SCHEMA_VERSION, "problem_id": store.problem_id,
                "base_revision": 0, "actor_role": "integration_verifier", "target_id": "root",
                "operations": [{"op": "attach_artifact", "artifact_id": "audit",
                    "artifact_type": "root_alignment_audit", "content": "Partial route only.",
                    "metadata": {"route_id": "route", "claim_id": "lemma"}}],
            })
            self.assertTrue(result.accepted, result.errors)
            audits = store.get_scheduler_state()["audit_artifacts"]
            self.assertIn("audit", [row["artifact_id"] for row in audits])
