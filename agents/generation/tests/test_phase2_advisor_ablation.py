from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agents.generation.phase2.codex_runner import actor_role_for_action
from agents.generation.phase2.role_capabilities import advisor_enabled
from agents.generation.phase2.scheduler import _reallocate_advisor_action


class AdvisorAblationTests(unittest.TestCase):
    def test_advisor_is_enabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(advisor_enabled())

    def test_false_environment_spellings_disable_advisor(self) -> None:
        for value in ("0", "false", "FALSE", "no", "off"):
            with self.subTest(value=value):
                self.assertFalse(advisor_enabled({"ALBILICH_ADVISOR_ENABLED": value}))

    def test_non_false_environment_value_keeps_advisor_enabled(self) -> None:
        self.assertTrue(advisor_enabled({"ALBILICH_ADVISOR_ENABLED": "1"}))

    def test_disabled_advisor_action_is_reallocated_to_researcher_mode(self) -> None:
        advisor_action = {
            "mode": "triage_routes",
            "target_id": "root",
            "route_id": "",
            "reason": "global synthesis is due",
            "token_budget": 60_000,
        }
        with patch.dict(os.environ, {"ALBILICH_ADVISOR_ENABLED": "0"}):
            action = _reallocate_advisor_action(advisor_action)
            self.assertEqual(action["mode"], "reduce")
            self.assertEqual(action["token_budget"], 60_000)
            self.assertTrue(action["advisor_ablation_reallocation"])
            self.assertEqual(action["ablated_advisor_mode"], "triage_routes")
            self.assertEqual(actor_role_for_action(action), "researcher")

    def test_enabled_advisor_action_is_unchanged(self) -> None:
        advisor_action = {"mode": "regulate_decomposition", "target_id": "root"}
        with patch.dict(os.environ, {"ALBILICH_ADVISOR_ENABLED": "1"}):
            action = _reallocate_advisor_action(advisor_action)
            self.assertEqual(action, advisor_action)
            self.assertEqual(actor_role_for_action(action), "phd_advisor")

    def test_execution_guard_rejects_unsanitized_advisor_action(self) -> None:
        with patch.dict(os.environ, {"ALBILICH_ADVISOR_ENABLED": "0"}):
            with self.assertRaisesRegex(RuntimeError, "advisor-only action escaped"):
                actor_role_for_action({"mode": "triage_routes"})


if __name__ == "__main__":
    unittest.main()
