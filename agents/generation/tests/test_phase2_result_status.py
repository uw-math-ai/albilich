import json
import unittest

from agents.generation.phase2.result_status import classify_state


class Phase2ResultStatusTest(unittest.TestCase):
    def test_strictly_verified_root_waits_for_integration_not_another_route(self) -> None:
        state = {
            "problem_state": {"root_statement": "Prove the target theorem."},
            "claims": [
                {
                    "claim_id": "root",
                    "statement": "Prove the target theorem.",
                    "validation_status": "informally_verified",
                    "lifecycle_status": "active",
                },
                {
                    "claim_id": "verified-partial",
                    "statement": "A useful partial theorem.",
                    "validation_status": "informally_verified",
                    "lifecycle_status": "active",
                    "conditions_json": "[]",
                    "tags_json": "[]",
                },
            ],
            "artifacts": [],
            "debts": [],
        }

        result = classify_state(state)

        self.assertEqual(result["public_status"], "verified_pending_integration")
        self.assertEqual(result["report_classification"], "in_progress")
        self.assertEqual(
            result["remaining_obligations"],
            ["Run the integration verifier on the strictly verified sufficient root route."],
        )
        self.assertNotIn("requires an exact", result["summary"])

    def test_solved_route_obligations_ignore_stale_active_debts(self) -> None:
        state = {
            "problem_state": {"root_statement": "Prove the target theorem."},
            "claims": [
                {
                    "claim_id": "root",
                    "statement": "Prove the target theorem.",
                    "validation_status": "informally_verified",
                    "lifecycle_status": "integrated",
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "integration-report",
                    "artifact_type": "integration_report",
                    "created_at": "2026-06-24T00:00:00Z",
                    "metadata_json": json.dumps(
                        {
                            "integrates": True,
                            "claim_id": "root",
                            "root_alignment": {
                                "relation_to_root": "stronger",
                                "target_statement": "Prove the target theorem.",
                                "proved_statement": "A stronger theorem.",
                                "implication_verified": True,
                                "hidden_assumptions": False,
                                "extra_assumptions": [],
                            },
                        }
                    ),
                }
            ],
            "debts": [
                {
                    "status": "active",
                    "severity": "blocking",
                    "obligation": "Old abandoned route still has a local gap.",
                }
            ],
        }

        pending = classify_state(state)
        self.assertEqual(pending["public_status"], "solved_pending_final_writer")
        self.assertEqual(pending["remaining_obligations"], ["Run the writer/closer to emit the final_proof artifact."])

        state["artifacts"].append(
            {
                "artifact_id": "final-proof",
                "artifact_type": "final_proof",
                "created_at": "2026-06-24T00:01:00Z",
                "metadata_json": json.dumps({"claim_id": "root"}),
            }
        )
        solved = classify_state(state)
        self.assertEqual(solved["public_status"], "solved")
        self.assertEqual(solved["remaining_obligations"], [])


if __name__ == "__main__":
    unittest.main()
