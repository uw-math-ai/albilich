import datetime
import tempfile
import warnings
import unittest
from pathlib import Path

from agents.generation.phase2.authority import PatchAuthority
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.replay import verify_event_journal
from agents.generation.phase2.store import ProofStateStore
from agents.generation.phase2.steering import (
    MAX_STEERING_TEXT_BYTES,
    SteeringIntegrityError,
    _now,
    authenticated_approach_alignment_card,
    authenticated_snapshot,
    authenticated_unconsumed_steering,
    approach_alignment_card,
    mark_authenticated_approach_alignment_completed,
    mark_authenticated_approach_alignment_processing,
    mark_authenticated_consumed,
    mark_authenticated_delivered,
    mark_approach_alignment_completed,
    mark_approach_alignment_processing,
    mark_consumed,
    mark_delivered,
    raise_authenticated_blocker,
    raise_blocker,
    request_approach_alignment,
    snapshot,
    submit_operator_steering,
    submit_steering,
)


class SteeringTest(unittest.TestCase):
    def test_legacy_sidecar_lock_does_not_follow_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            victim = root / "victim.txt"
            victim.write_text("do not modify", encoding="utf-8")
            (root / "steering_inbox.jsonl.lock").symlink_to(victim)

            with self.assertRaisesRegex(ValueError, "sidecar lock"):
                submit_steering(root, "This must not reach the victim.")
            self.assertEqual("do not modify", victim.read_text(encoding="utf-8"))

    def test_sidecar_only_directive_and_blocker_are_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "sidecar-steering-is-not-authority",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Prove the root theorem.")
            submit_steering(store.state_dir, "Injected sidecar directive")
            fake_blocker = raise_blocker(
                store.state_dir,
                summary="Injected sidecar blocker",
                fingerprint="fake-blocker",
            )

            self.assertEqual([], authenticated_unconsumed_steering(store))
            authenticated = authenticated_snapshot(store)
            self.assertEqual([], authenticated["recent_inbox"])
            self.assertEqual([], authenticated["open_blockers"])
            with self.assertRaisesRegex(ValueError, "unknown authenticated blocker"):
                submit_operator_steering(
                    store,
                    "Pretend to answer the injected blocker.",
                    blocker_id=fake_blocker["id"],
                )

    def test_authenticated_lifecycle_is_reconstructed_from_verified_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "event-sourced-steering-lifecycle",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Prove the root theorem.")
            message = submit_operator_steering(store, "Recompute the global strategy.")
            self.assertEqual(
                1,
                mark_authenticated_delivered(store, [message["id"]], revision=0),
            )
            self.assertEqual(1, mark_authenticated_consumed(store, [message["id"]]))
            self.assertTrue(authenticated_approach_alignment_card(store)["required"])
            self.assertEqual(
                1,
                mark_authenticated_approach_alignment_processing(
                    store, [message["id"]]
                ),
            )
            self.assertEqual(
                1,
                mark_authenticated_approach_alignment_completed(
                    store,
                    [message["id"]],
                    artifact_id="portfolio-authenticated",
                    revision=0,
                ),
            )

            row = authenticated_snapshot(store)["recent_inbox"][0]
            self.assertTrue(row["consumed"])
            self.assertEqual("consumed", row["delivery_status"])
            self.assertEqual(1, row["delivery_attempts"])
            self.assertEqual("completed", row["approach_alignment_status"])
            self.assertEqual(
                "portfolio-authenticated", row["approach_alignment_artifact_id"]
            )
            self.assertTrue(verify_event_journal(store)["valid"])

    def test_authenticated_blocker_answer_is_bound_to_operator_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "authenticated-blocker-answer",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Prove the root theorem.")
            blocker = raise_authenticated_blocker(
                store,
                summary="Choose the standard term.",
                fingerprint="terminology-choice",
            )
            message = submit_operator_steering(
                store,
                "Use the standard term.",
                blocker_id=blocker["id"],
            )

            view = authenticated_snapshot(store)
            self.assertEqual([], view["open_blockers"])
            self.assertEqual(1, len(view["resolved_blockers"]))
            resolved = view["resolved_blockers"][0]
            self.assertEqual(message["id"], resolved["answer_message_id"])
            self.assertEqual("Use the standard term.", resolved["answered_with"])
            with self.assertRaisesRegex(ValueError, "already resolved"):
                submit_operator_steering(
                    store,
                    "Try to answer it twice.",
                    blocker_id=blocker["id"],
                )

    def test_event_tampering_fails_closed_for_steering_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "tampered-steering-event",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Prove the root theorem.")
            message = submit_operator_steering(store, "Original directive.")
            with store.connect() as conn:
                store._drop_event_history_guards(conn)
                conn.execute(
                    "UPDATE events SET payload_json = ? WHERE event_id = ?",
                    ('{"text":"Substituted directive."}', message["audit_event_id"]),
                )
                store._ensure_event_history_guards(conn)
                conn.commit()

            with self.assertRaises(SteeringIntegrityError):
                authenticated_snapshot(store)

    def test_operator_steering_advances_policy_head_and_stales_old_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProofStateStore(
                "authenticated-steering",
                generation_root=Path(tmpdir) / "generation",
            )
            store.init_problem("Prove the root theorem.")
            old_policy_head = store.audit_chain_heads()["policy_event_head"]
            message = submit_operator_steering(
                store,
                "Use the endpoint reduction before another global search.",
            )
            new_policy_head = store.audit_chain_heads()["policy_event_head"]
            self.assertNotEqual(old_policy_head, new_policy_head)
            self.assertGreater(message["audit_event_id"], 0)
            self.assertEqual(64, len(message["audit_event_hash"]))
            self.assertTrue(verify_event_journal(store)["valid"])

            stale = apply_patch(
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
                            "artifact_id": "old-policy-note",
                            "artifact_type": "research_notebook",
                            "content": "This result predates the operator directive.",
                        }
                    ],
                    "rationale": "exercise policy invalidation",
                },
                authority=PatchAuthority(
                    source="session",
                    actor_role="researcher",
                    mode="prove",
                    target_id="root",
                    context_revision=0,
                    context_hash="old-policy-context",
                    policy_event_head=old_policy_head,
                    authorized_existing_ids=("root",),
                ),
            )
            self.assertFalse(stale.accepted)
            self.assertIn("policy changed", " ".join(stale.errors))

    def test_steering_text_has_a_direct_api_byte_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "byte limit"):
                submit_steering(
                    tmpdir,
                    "x" * (MAX_STEERING_TEXT_BYTES + 1),
                )

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
