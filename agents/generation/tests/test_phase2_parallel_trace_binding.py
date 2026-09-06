from __future__ import annotations

import copy
import unittest

from agents.generation.phase2.decision_policy import (
    ActionCandidate,
    bind_dispatched_action,
    decision_trace_errors,
    policy_trace_sha256,
    select_action_candidate,
)
from agents.generation.phase2.scheduler import (
    _admit_parallel_companion_candidates,
    _bind_parallel_wave_decision,
)


class ParallelTraceBindingTests(unittest.TestCase):
    def test_background_planner_keeps_its_complete_nested_comparison(self) -> None:
        background = {"mode": "reduce", "target_id": "root", "search_intent": "approach_portfolio_refresh"}
        _, inner = select_action_candidate(
            [ActionCandidate("inner:refresh", "research", background, 1.0)],
            candidate_set_complete=True,
        )
        background, original = select_action_candidate(
            [ActionCandidate("base:planner", "planner", background, 1.0)],
            candidate_set_complete=True,
            nested_policy_traces={"base:planner": inner},
        )
        background["decision_trace"] = bind_dispatched_action(background, original)
        original = copy.deepcopy(background["decision_trace"])
        background["parallel_companion"] = True
        background["integration_parallel_safe"] = True
        selected, wave = _admit_parallel_companion_candidates(
            {"mode": "integrate", "target_id": "lemma", "route_id": "lemma-route"},
            [background],
            problem={"parallel_branches": 3},
        )
        self.assertEqual(1, len(selected))
        bound = _bind_parallel_wave_decision(selected[0], wave)
        trace = bound["decision_trace"]
        self.assertEqual([], decision_trace_errors(trace))
        candidate_id = bound["parallel_wave_candidate_id"]
        self.assertEqual(original, trace["nested_policy_traces"][candidate_id])
        self.assertEqual(policy_trace_sha256(original), bound["base_policy_trace_sha256"])
        self.assertEqual(
            wave["candidates"][1]["comparison_action_sha256"],
            trace["parallel_wave_input_action_sha256"],
        )
        tampered = copy.deepcopy(trace)
        tampered["nested_policy_traces"][candidate_id]["selected_candidate_id"] = "forged"
        self.assertTrue(decision_trace_errors(tampered))

    def test_plain_companion_needs_no_nested_planner_trace(self) -> None:
        selected, wave = _admit_parallel_companion_candidates(
            {"mode": "integrate", "target_id": "lemma", "route_id": "lemma-route"},
            [{"mode": "reduce", "target_id": "root", "parallel_companion": True}],
            problem={"parallel_branches": 3},
        )
        bound = _bind_parallel_wave_decision(selected[0], wave)
        self.assertEqual([], decision_trace_errors(bound["decision_trace"]))
        self.assertNotIn("nested_policy_traces", bound["decision_trace"])


if __name__ == "__main__":
    unittest.main()
