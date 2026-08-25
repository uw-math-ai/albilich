import datetime
import tempfile
import warnings
import unittest

from agents.generation.phase2.steering import (
    _now,
    approach_alignment_card,
    mark_approach_alignment_completed,
    mark_approach_alignment_processing,
    mark_consumed,
    mark_delivered,
    request_approach_alignment,
    snapshot,
    submit_steering,
)


class SteeringTest(unittest.TestCase):
    def test_now_is_parseable_utc_without_deprecation_warning(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            timestamp = _now()

        self.assertTrue(timestamp.endswith("Z"))
        parsed = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        self.assertEqual(parsed.utcoffset(), datetime.timedelta(0))

    def test_snapshot_distinguishes_queued_processing_and_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queued = submit_steering(tmpdir, "queued directive")
            processing = submit_steering(tmpdir, "processing directive")

            self.assertEqual(mark_delivered(tmpdir, [processing["id"]], revision=17), 1)
            first = snapshot(tmpdir)
            by_id = {row["id"]: row for row in first["recent_inbox"]}
            self.assertEqual(first["queued_count"], 1)
            self.assertEqual(first["processing_count"], 1)
            self.assertEqual(by_id[queued["id"]]["delivery_status"], "queued")
            self.assertEqual(by_id[processing["id"]]["delivery_status"], "processing")
            self.assertEqual(by_id[processing["id"]]["delivered_revision"], 17)
            self.assertEqual(by_id[processing["id"]]["delivery_attempts"], 1)
            self.assertFalse(by_id[processing["id"]]["consumed"])

            self.assertEqual(mark_consumed(tmpdir, [processing["id"]]), 1)
            final = snapshot(tmpdir)
            by_id = {row["id"]: row for row in final["recent_inbox"]}
            self.assertEqual(final["queued_count"], 1)
            self.assertEqual(final["processing_count"], 0)
            self.assertEqual(by_id[processing["id"]]["delivery_status"], "consumed")
            self.assertTrue(by_id[processing["id"]]["consumed"])
            self.assertEqual(by_id[processing["id"]]["approach_alignment_status"], "pending")
            self.assertEqual(final["approach_alignment_pending_count"], 1)

    def test_processed_general_steer_requires_and_completes_portfolio_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            message = submit_steering(tmpdir, "The new example raises the sharp lower bound.")
            self.assertTrue(message["approach_alignment_required"])
            self.assertEqual(message["approach_alignment_status"], "awaiting_processing")

            mark_consumed(tmpdir, [message["id"]])
            card = approach_alignment_card(tmpdir)
            self.assertTrue(card["required"])
            self.assertEqual(card["source_steering_ids"], [message["id"]])

            self.assertEqual(mark_approach_alignment_processing(tmpdir, [message["id"]]), 1)
            self.assertEqual(snapshot(tmpdir)["approach_alignment_processing_count"], 1)
            self.assertEqual(
                mark_approach_alignment_completed(
                    tmpdir,
                    [message["id"]],
                    artifact_id="portfolio-refresh-1",
                    revision=23,
                ),
                1,
            )
            final = snapshot(tmpdir)
            row = next(item for item in final["recent_inbox"] if item["id"] == message["id"])
            self.assertEqual(final["approach_alignment_pending_count"], 0)
            self.assertEqual(row["approach_alignment_status"], "completed")
            self.assertEqual(row["approach_alignment_artifact_id"], "portfolio-refresh-1")
            self.assertEqual(row["approach_alignment_revision"], 23)

    def test_blocker_answer_does_not_refresh_global_portfolio_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            message = submit_steering(tmpdir, "Use notation A.", blocker_id="blocker-writing")
            mark_consumed(tmpdir, [message["id"]])
            self.assertFalse(message["approach_alignment_required"])
            self.assertFalse(approach_alignment_card(tmpdir)["required"])

    def test_legacy_message_can_be_queued_for_alignment_without_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            message = submit_steering(
                tmpdir,
                "Legacy steer",
                requires_approach_alignment=False,
            )
            mark_consumed(tmpdir, [message["id"]])
            self.assertEqual(request_approach_alignment(tmpdir, [message["id"]]), 1)
            card = approach_alignment_card(tmpdir)
            self.assertEqual(card["pending_count"], 1)
            self.assertEqual(card["source_steering_ids"], [message["id"]])


if __name__ == "__main__":
    unittest.main()
