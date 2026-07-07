from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generation.phase2.claude_runner import build_claude_command
from agents.generation.phase2.codex_runner import actor_role_for_action, build_session_prompt, prepare_session, run_metrics_operation
from agents.generation.phase2.console import build_run_console_payload, build_run_console
from agents.generation.phase2.context_builder import build_context_manifest
from agents.generation.phase2.models import SCHEMA_VERSION
from agents.generation.phase2.monitor import build_monitor_payload
from agents.generation.phase2.patches import apply_patch
from agents.generation.phase2.research_policy import (
    RESEARCHER_WORK_MODES,
    action_expects_researcher_session,
    advisor_mode_directive,
    researcher_mode_summary,
    researcher_work_mode_decision,
    search_policy_for_action,
    stamp_researcher_work_mode,
)
from agents.generation.phase2.role_capabilities import session_cas_enabled
from agents.generation.phase2.scheduler import next_action
from agents.generation.phase2.store import ProofStateStore


def _make_store(tmpdir: str, problem_id: str) -> ProofStateStore:
    store = ProofStateStore(problem_id, generation_root=Path(tmpdir) / "generation")
    store.init_problem("Target theorem.")
    return store


def _record_mode_run(
    store: ProofStateStore,
    *,
    run_id: str,
    mode: str = "prove",
    actor_role: str = "researcher",
    researcher_work_mode: str = "",
    work_mode_source: str = "",
    search_intent: str = "",
) -> None:
    action: dict[str, Any] = {
        "mode": mode,
        "target_id": "root",
        "route_id": "",
        "budget": {"requested_tokens": 0},
    }
    if researcher_work_mode:
        action["researcher_work_mode"] = researcher_work_mode
        action["work_mode_source"] = work_mode_source or "rotation"
    session_plan = {
        "actor_role": actor_role,
        "state_revision": store.get_revision(),
        "model_profile": "test",
        "context_hash": f"context-{run_id}",
    }
    op = run_metrics_operation(
        run_id=run_id,
        action=action,
        session_plan=session_plan,
        usage_payload={},
        status="completed",
        wall_time_seconds=1.0,
        model="test-model",
    )
    op["search_intent"] = search_intent
    outcome = apply_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "scheduler",
            "target_id": "root",
            "operations": [op],
            "rationale": "record synthetic run metrics",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


def _attach_advisor_directive(
    store: ProofStateStore,
    *,
    artifact_id: str,
    directed_mode: str,
    reason: str = "supervision test",
    steps: int | None = None,
) -> None:
    metadata: dict[str, Any] = {
        "directed_researcher_mode": directed_mode,
        "directed_researcher_mode_reason": reason,
        "recommended_next_action": "follow the directed mode",
        "advisor_followup_required": True,
    }
    if steps is not None:
        metadata["directed_researcher_mode_steps"] = steps
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
                    "artifact_id": artifact_id,
                    "artifact_type": "advisor_report",
                    "content": f"Advisor directs the researcher to work {directed_mode}.",
                    "metadata": metadata,
                }
            ],
            "rationale": "advisor supervision directive",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)


class ResearcherWorkModeDecisionTest(unittest.TestCase):
    def test_first_pass_is_online_when_live_search_allowed(self) -> None:
        state = {"recent_runs": [], "research_artifacts": []}
        decision = researcher_work_mode_decision(state, {"mode": "prove"}, research_mode="hard_problem", web_search="live")
        self.assertEqual(decision["work_mode"], "online")
        self.assertEqual(decision["source"], "rotation")

    def test_rotation_cycles_online_offline_cas(self) -> None:
        def state_after(mode: str) -> dict[str, Any]:
            return {
                "recent_runs": [
                    {
                        "run_id": "r1",
                        "actor_role": "researcher",
                        "researcher_work_mode": mode,
                        "work_mode_source": "rotation",
                        "state_revision": 3,
                    }
                ],
                "research_artifacts": [],
            }

        action = {"mode": "prove"}
        self.assertEqual(
            researcher_work_mode_decision(state_after("online"), action, research_mode="hard_problem", web_search="live")["work_mode"],
            "offline",
        )
        self.assertEqual(
            researcher_work_mode_decision(state_after("offline"), action, research_mode="hard_problem", web_search="live")["work_mode"],
            "cas",
        )
        self.assertEqual(
            researcher_work_mode_decision(state_after("cas"), action, research_mode="hard_problem", web_search="live")["work_mode"],
            "online",
        )

    def test_rotation_skips_online_when_web_search_disabled(self) -> None:
        state = {"recent_runs": [], "research_artifacts": []}
        action = {"mode": "prove"}
        first = researcher_work_mode_decision(state, action, research_mode="hard_problem", web_search="disabled")
        self.assertEqual(first["work_mode"], "offline")
        state_cas = {
            "recent_runs": [
                {
                    "run_id": "r1",
                    "actor_role": "researcher",
                    "researcher_work_mode": "cas",
                    "work_mode_source": "rotation",
                    "state_revision": 3,
                }
            ],
            "research_artifacts": [],
        }
        wrapped = researcher_work_mode_decision(state_cas, action, research_mode="hard_problem", web_search="disabled")
        self.assertEqual(wrapped["work_mode"], "offline")

    def test_independent_mode_never_goes_online(self) -> None:
        state = {"recent_runs": [], "research_artifacts": []}
        decision = researcher_work_mode_decision(state, {"mode": "prove"}, research_mode="independent", web_search="live")
        self.assertNotEqual(decision["work_mode"], "online")

    def test_structural_flags_bias_modes(self) -> None:
        state = {"recent_runs": [], "research_artifacts": []}
        cas_decision = researcher_work_mode_decision(
            state, {"mode": "prove", "cas_check_recommended": True}, research_mode="hard_problem", web_search="live"
        )
        self.assertEqual(cas_decision["work_mode"], "cas")
        offline_decision = researcher_work_mode_decision(
            state, {"mode": "prove", "bottleneck_lock_required": True}, research_mode="hard_problem", web_search="live"
        )
        self.assertEqual(offline_decision["work_mode"], "offline")

    def test_weak_bias_yields_to_rotation_after_staleness_window(self) -> None:
        def offline_run(index: int) -> dict[str, Any]:
            return {
                "run_id": f"r{index}",
                "actor_role": "researcher",
                "researcher_work_mode": "offline",
                "work_mode_source": "structural",
                "state_revision": index,
                "status": "completed",
            }

        state = {"recent_runs": [offline_run(3), offline_run(2), offline_run(1)], "research_artifacts": []}
        weak_action = {"mode": "prove", "advisor_followup_required": True}
        decision = researcher_work_mode_decision(state, weak_action, research_mode="hard_problem", web_search="live")
        self.assertEqual(decision["work_mode"], "cas")  # cycle order: offline -> cas
        self.assertEqual(decision["source"], "rotation_override")
        # Strong biases keep priority even when stuck.
        strong_action = {"mode": "prove", "bottleneck_lock_required": True}
        strong = researcher_work_mode_decision(state, strong_action, research_mode="hard_problem", web_search="live")
        self.assertEqual(strong["work_mode"], "offline")
        # A weak bias while stuck on cas is fine: offline itself breaks the streak.
        def cas_run(index: int) -> dict[str, Any]:
            return {
                "run_id": f"c{index}",
                "actor_role": "researcher",
                "researcher_work_mode": "cas",
                "work_mode_source": "structural",
                "state_revision": index,
                "status": "completed",
            }

        cas_state = {"recent_runs": [cas_run(3), cas_run(2), cas_run(1)], "research_artifacts": []}
        broken = researcher_work_mode_decision(cas_state, weak_action, research_mode="hard_problem", web_search="live")
        self.assertEqual(broken["work_mode"], "offline")
        self.assertEqual(broken["source"], "structural")
        # And with no bias at all, plain rotation moves cas -> online.
        plain = researcher_work_mode_decision(cas_state, {"mode": "prove"}, research_mode="hard_problem", web_search="live")
        self.assertEqual(plain["work_mode"], "online")

    def test_weak_bias_holds_before_staleness_window(self) -> None:
        state = {
            "recent_runs": [
                {
                    "run_id": "r1",
                    "actor_role": "researcher",
                    "researcher_work_mode": "offline",
                    "work_mode_source": "structural",
                    "state_revision": 5,
                    "status": "completed",
                }
            ],
            "research_artifacts": [],
        }
        decision = researcher_work_mode_decision(
            state, {"mode": "prove", "research_synthesis_required": True}, research_mode="hard_problem", web_search="live"
        )
        self.assertEqual(decision["work_mode"], "offline")
        self.assertEqual(decision["source"], "structural")

    def test_companion_actions_default_offline(self) -> None:
        state = {"recent_runs": [], "research_artifacts": []}
        decision = researcher_work_mode_decision(
            state, {"mode": "prove", "parallel_companion": True}, research_mode="hard_problem", web_search="live"
        )
        self.assertEqual(decision["work_mode"], "offline")
        self.assertEqual(decision["source"], "companion_default")

    def test_advisor_directive_overrides_rotation_and_structural_bias(self) -> None:
        state = {
            "recent_runs": [],
            "research_artifacts": [
                {
                    "artifact_id": "adv-1",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 7,
                    "metadata_json": json.dumps({"directed_researcher_mode": "cas", "directed_researcher_mode_reason": "compute chain-closures"}),
                }
            ],
        }
        decision = researcher_work_mode_decision(
            state, {"mode": "prove", "bottleneck_lock_required": True}, research_mode="hard_problem", web_search="live"
        )
        self.assertEqual(decision["work_mode"], "cas")
        self.assertEqual(decision["source"], "advisor_directive")
        self.assertEqual(decision["advisor_mode_directive_artifact_id"], "adv-1")

    def test_failed_directed_pass_does_not_consume_directive(self) -> None:
        state = {
            "recent_runs": [
                {
                    "run_id": "r-timeout",
                    "actor_role": "researcher",
                    "researcher_work_mode": "cas",
                    "work_mode_source": "advisor_directive",
                    "state_revision": 8,
                    "status": "timeout",
                }
            ],
            "research_artifacts": [
                {
                    "artifact_id": "adv-1",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 7,
                    "metadata_json": json.dumps({"directed_researcher_mode": "cas"}),
                }
            ],
        }
        directive = advisor_mode_directive(state)
        self.assertIsNotNone(directive)
        assert directive is not None
        self.assertEqual(directive["steps_remaining"], 1)

    def test_advisor_directive_expires_after_consumption(self) -> None:
        state = {
            "recent_runs": [
                {
                    "run_id": "r-consume",
                    "actor_role": "researcher",
                    "researcher_work_mode": "cas",
                    "work_mode_source": "advisor_directive",
                    "state_revision": 8,
                    "status": "completed",
                }
            ],
            "research_artifacts": [
                {
                    "artifact_id": "adv-1",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 7,
                    "metadata_json": json.dumps({"directed_researcher_mode": "cas"}),
                }
            ],
        }
        self.assertIsNone(advisor_mode_directive(state))
        decision = researcher_work_mode_decision(state, {"mode": "prove"}, research_mode="hard_problem", web_search="live")
        self.assertEqual(decision["source"], "rotation")
        self.assertEqual(decision["work_mode"], "online")

    def test_stale_directive_expires_by_revision_ttl(self) -> None:
        state = {
            "problem_state": {"current_revision": 200},
            "recent_runs": [],
            "research_artifacts": [
                {
                    "artifact_id": "adv-old",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 100,
                    "metadata_json": json.dumps({"directed_researcher_mode": "cas"}),
                }
            ],
        }
        # 100 revisions old: void, even though no consuming run is in the window
        # (this is the zombie-directive regression observed live on 2026-07-04).
        self.assertIsNone(advisor_mode_directive(state))
        fresh = dict(state, problem_state={"current_revision": 120})
        directive = advisor_mode_directive(fresh)
        self.assertIsNotNone(directive)
        assert directive is not None
        self.assertEqual(directive["work_mode"], "cas")

    def test_advisor_directive_steps_cover_multiple_passes(self) -> None:
        artifacts = [
            {
                "artifact_id": "adv-1",
                "artifact_type": "advisor_report",
                "producer_role": "phd_advisor",
                "state_revision": 7,
                "metadata_json": json.dumps({"directed_researcher_mode": "offline", "directed_researcher_mode_steps": 2}),
            }
        ]
        one_consumed = {
            "recent_runs": [
                {
                    "run_id": "r-consume",
                    "actor_role": "researcher",
                    "researcher_work_mode": "offline",
                    "work_mode_source": "advisor_directive",
                    "state_revision": 8,
                    "status": "completed",
                }
            ],
            "research_artifacts": artifacts,
        }
        directive = advisor_mode_directive(one_consumed)
        self.assertIsNotNone(directive)
        assert directive is not None
        self.assertEqual(directive["steps_remaining"], 1)

    def test_online_directive_downgrades_when_search_disabled(self) -> None:
        state = {
            "recent_runs": [],
            "research_artifacts": [
                {
                    "artifact_id": "adv-1",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 7,
                    "metadata_json": json.dumps({"directed_researcher_mode": "online"}),
                }
            ],
        }
        decision = researcher_work_mode_decision(state, {"mode": "prove"}, research_mode="hard_problem", web_search="disabled")
        self.assertEqual(decision["work_mode"], "offline")
        self.assertEqual(decision["source"], "advisor_directive_downgraded")

    def test_stamp_only_touches_researcher_actions(self) -> None:
        state = {"recent_runs": [], "research_artifacts": []}
        verifier_action = {"mode": "prove", "route_id": "route-1"}
        stamp_researcher_work_mode(state, verifier_action, research_mode="hard_problem", web_search="live")
        self.assertNotIn("researcher_work_mode", verifier_action)
        librarian_action = {"mode": "retrieve"}
        stamp_researcher_work_mode(state, librarian_action, research_mode="hard_problem", web_search="live")
        self.assertNotIn("researcher_work_mode", librarian_action)
        researcher_action = {"mode": "prove"}
        stamp_researcher_work_mode(state, researcher_action, research_mode="hard_problem", web_search="live")
        self.assertIn(researcher_action["researcher_work_mode"], RESEARCHER_WORK_MODES)

    def test_researcher_session_predicate_matches_actor_role_routing(self) -> None:
        actions = [
            {"mode": "prove"},
            {"mode": "prove", "route_id": "route-1"},
            {"mode": "prove", "citation_triage_required": True},
            {"mode": "prove", "citation_certification_required": True},
            {"mode": "reduce"},
            {"mode": "reduce", "debt_id": "debt-1"},
            {"mode": "reduce", "debt_id": "debt-1", "proof_repair_required": True},
            {"mode": "reduce", "debt_id": "debt-1", "route_id": "route-1"},
            {"mode": "weaken"},
            {"mode": "strengthen", "debt_id": "debt-1", "research_diagnostic_required": True},
            {"mode": "retrieve"},
            {"mode": "refute"},
            {"mode": "triage_routes"},
            {"mode": "integrate"},
            {"mode": "write"},
            {"mode": "validate_counterexample"},
            {"mode": "synthesize_sources"},
            {"mode": "audit_definitions"},
            {"mode": "regulate_decomposition"},
            {"mode": "formalize"},
        ]
        for action in actions:
            with self.subTest(action=action):
                self.assertEqual(
                    action_expects_researcher_session(action),
                    actor_role_for_action(action) == "researcher",
                )


class VillainWorkModeTest(unittest.TestCase):
    def test_villain_rotation_is_computation_first(self) -> None:
        state = {"recent_runs": [], "research_artifacts": []}
        action = {"mode": "refute", "parallel_companion": True}
        first = researcher_work_mode_decision(state, action, research_mode="hard_problem", web_search="live")
        self.assertEqual(first["work_mode"], "cas")
        self.assertEqual(first["source"], "rotation")

        def villain_run(mode: str) -> dict[str, Any]:
            return {
                "run_id": f"v-{mode}",
                "actor_role": "villain",
                "researcher_work_mode": mode,
                "work_mode_source": "rotation",
                "state_revision": 5,
                "status": "completed",
            }

        after_cas = {"recent_runs": [villain_run("cas")], "research_artifacts": []}
        self.assertEqual(
            researcher_work_mode_decision(after_cas, action, research_mode="hard_problem", web_search="live")["work_mode"],
            "offline",
        )
        after_offline = {"recent_runs": [villain_run("offline")], "research_artifacts": []}
        self.assertEqual(
            researcher_work_mode_decision(after_offline, action, research_mode="hard_problem", web_search="live")["work_mode"],
            "online",
        )
        # With web search off, the villain cycle drops online.
        self.assertEqual(
            researcher_work_mode_decision(after_offline, action, research_mode="hard_problem", web_search="disabled")["work_mode"],
            "cas",
        )

    def test_villain_history_is_independent_of_researcher_history(self) -> None:
        state = {
            "recent_runs": [
                {
                    "run_id": "r-online",
                    "actor_role": "researcher",
                    "researcher_work_mode": "online",
                    "work_mode_source": "rotation",
                    "state_revision": 6,
                    "status": "completed",
                }
            ],
            "research_artifacts": [],
        }
        decision = researcher_work_mode_decision(
            state, {"mode": "refute", "parallel_companion": True}, research_mode="hard_problem", web_search="live"
        )
        self.assertEqual(decision["work_mode"], "cas")  # villain cycle start, unaffected by researcher history

    def test_advisor_villain_directive_is_honored_and_independent(self) -> None:
        state = {
            "recent_runs": [],
            "research_artifacts": [
                {
                    "artifact_id": "adv-v1",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 9,
                    "metadata_json": json.dumps(
                        {
                            "directed_villain_mode": "online",
                            "directed_villain_mode_reason": "hunt published counterexample families",
                        }
                    ),
                }
            ],
        }
        villain_action = {"mode": "refute", "parallel_companion": True}
        decision = researcher_work_mode_decision(state, villain_action, research_mode="hard_problem", web_search="live")
        self.assertEqual(decision["work_mode"], "online")
        self.assertEqual(decision["source"], "advisor_directive")
        self.assertEqual(decision["advisor_mode_directive_artifact_id"], "adv-v1")
        # The researcher is NOT affected by a villain directive.
        researcher_decision = researcher_work_mode_decision(
            state, {"mode": "prove"}, research_mode="hard_problem", web_search="live"
        )
        self.assertEqual(researcher_decision["source"], "rotation")
        # And a researcher directive does not bind the villain.
        state2 = {
            "recent_runs": [],
            "research_artifacts": [
                {
                    "artifact_id": "adv-r1",
                    "artifact_type": "advisor_report",
                    "producer_role": "phd_advisor",
                    "state_revision": 9,
                    "metadata_json": json.dumps({"directed_researcher_mode": "offline"}),
                }
            ],
        }
        villain_decision = researcher_work_mode_decision(state2, villain_action, research_mode="hard_problem", web_search="live")
        self.assertEqual(villain_decision["source"], "rotation")

    def test_villain_online_pass_gets_live_search(self) -> None:
        online_villain = {"mode": "refute", "researcher_work_mode": "online"}
        self.assertEqual(
            search_policy_for_action(online_villain, research_mode="hard_problem", web_search="live"), "live"
        )
        offline_villain = {"mode": "refute", "researcher_work_mode": "offline"}
        self.assertEqual(
            search_policy_for_action(offline_villain, research_mode="hard_problem", web_search="live"), "disabled"
        )

    def test_villain_prompt_carries_work_mode_contract(self) -> None:
        base = {"mode": "refute", "target_id": "root", "route_id": ""}
        online_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={**base, "researcher_work_mode": "online", "work_mode_source": "rotation"},
            actor_role="villain",
        )
        self.assertIn("ONLINE refutation pass", online_prompt)
        self.assertIn("VILLAIN WORK MODE: online", online_prompt)
        cas_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={**base, "researcher_work_mode": "cas", "work_mode_source": "rotation"},
            actor_role="villain",
        )
        self.assertIn("CAS REFUTATION pass", cas_prompt)
        offline_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={**base, "researcher_work_mode": "offline", "work_mode_source": "rotation"},
            actor_role="villain",
        )
        self.assertIn("OFFLINE refutation pass", offline_prompt)
        self.assertIn("not available in this villain work mode", offline_prompt)

    def test_stamp_covers_refute_actions(self) -> None:
        state = {"recent_runs": [], "research_artifacts": []}
        villain_action = {"mode": "refute", "parallel_companion": True}
        stamp_researcher_work_mode(state, villain_action, research_mode="hard_problem", web_search="live")
        self.assertIn(villain_action["researcher_work_mode"], RESEARCHER_WORK_MODES)

    def test_summary_includes_villain_block(self) -> None:
        state = {
            "recent_runs": [
                {
                    "run_id": "v-cas",
                    "actor_role": "villain",
                    "researcher_work_mode": "cas",
                    "work_mode_source": "rotation",
                    "state_revision": 4,
                    "status": "completed",
                }
            ],
            "research_artifacts": [],
        }
        summary = researcher_mode_summary(state)
        self.assertEqual(summary["villain"]["current"]["work_mode"], "cas")
        self.assertEqual(summary["villain"]["cycle"], ["cas", "offline", "online"])


class ResearcherWorkModeGatesTest(unittest.TestCase):
    def test_search_policy_grants_live_only_to_online_researcher(self) -> None:
        online = {"mode": "prove", "researcher_work_mode": "online"}
        offline = {"mode": "prove", "researcher_work_mode": "offline"}
        cas = {"mode": "prove", "researcher_work_mode": "cas"}
        retrieve = {"mode": "retrieve"}
        self.assertEqual(search_policy_for_action(online, research_mode="hard_problem", web_search="live"), "live")
        self.assertEqual(search_policy_for_action(offline, research_mode="hard_problem", web_search="live"), "disabled")
        self.assertEqual(search_policy_for_action(cas, research_mode="hard_problem", web_search="live"), "disabled")
        self.assertEqual(search_policy_for_action(retrieve, research_mode="hard_problem", web_search="live"), "live")
        self.assertEqual(search_policy_for_action(online, research_mode="independent", web_search="live"), "disabled")
        self.assertEqual(search_policy_for_action(online, research_mode="hard_problem", web_search="disabled"), "disabled")
        verifier = {"mode": "prove", "route_id": "route-1", "researcher_work_mode": "online"}
        self.assertEqual(search_policy_for_action(verifier, research_mode="hard_problem", web_search="live"), "disabled")

    def test_session_cas_enabled_matrix(self) -> None:
        self.assertTrue(session_cas_enabled("researcher", {"researcher_work_mode": "cas"}))
        self.assertTrue(session_cas_enabled("researcher", {}))  # legacy unstamped actions keep CAS
        self.assertFalse(session_cas_enabled("researcher", {"researcher_work_mode": "online"}))
        self.assertFalse(session_cas_enabled("researcher", {"researcher_work_mode": "offline"}))
        # The villain runs the same mode-gated loop.
        self.assertTrue(session_cas_enabled("villain", {"researcher_work_mode": "cas"}))
        self.assertTrue(session_cas_enabled("villain", {}))  # legacy unstamped actions keep CAS
        self.assertFalse(session_cas_enabled("villain", {"researcher_work_mode": "offline"}))
        self.assertFalse(session_cas_enabled("villain", {"researcher_work_mode": "online"}))
        self.assertFalse(session_cas_enabled("strict_informal_verifier", {"researcher_work_mode": "cas"}))

    def test_researcher_prompt_carries_work_mode_contract(self) -> None:
        base = {"mode": "prove", "target_id": "root", "route_id": ""}
        online_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={**base, "researcher_work_mode": "online", "work_mode_source": "rotation"},
            actor_role="researcher",
        )
        self.assertIn("ONLINE pass", online_prompt)
        self.assertIn("RESEARCHER WORK MODE: online", online_prompt)
        offline_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={**base, "researcher_work_mode": "offline", "work_mode_source": "rotation"},
            actor_role="researcher",
        )
        self.assertIn("OFFLINE pass", offline_prompt)
        self.assertIn("not available in this researcher work mode", offline_prompt)
        cas_prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={**base, "researcher_work_mode": "cas", "work_mode_source": "advisor_directive"},
            actor_role="researcher",
        )
        self.assertIn("CAS EXPERIMENT pass", cas_prompt)
        self.assertIn("cas_experiment_report", cas_prompt)

    def test_advisor_prompt_documents_mode_directive(self) -> None:
        prompt = build_session_prompt(
            context_path=Path("/tmp/context.json"),
            action={"mode": "triage_routes", "target_id": "root"},
            actor_role="phd_advisor",
        )
        self.assertIn("directed_researcher_mode", prompt)
        self.assertIn("search more", prompt)

    def test_claude_command_denies_web_tools_and_joins_tool_lists(self) -> None:
        command = build_claude_command(
            prompt="do the thing",
            disallowed_tools=("WebSearch", "WebFetch"),
            allowed_tools=("Bash", "Read"),
            extra_args=["--foo"],
        )
        self.assertIn("--disallowedTools", command)
        self.assertEqual(command[command.index("--disallowedTools") + 1], "WebSearch,WebFetch")
        self.assertEqual(command[command.index("--allowedTools") + 1], "Bash,Read")
        self.assertEqual(command[-1], "do the thing")


class ResearcherWorkModeSchedulerTest(unittest.TestCase):
    def test_next_action_stamps_researcher_work_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-stamp-test")
            # A prior retrieve run so the initial librarian scan does not preempt research.
            _record_mode_run(store, run_id="run-retrieve", mode="retrieve", actor_role="literature_researcher")
            action = next_action(store, research_mode="hard_problem", web_search="live")
            self.assertTrue(action_expects_researcher_session(action), action)
            self.assertEqual(action["researcher_work_mode"], "online")
            self.assertEqual(action["work_mode_source"], "rotation")
            self.assertTrue(action["researcher_work_mode_reason"])

    def test_recorded_mode_history_rotates_next_scheduled_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-rotation-test")
            _record_mode_run(store, run_id="run-retrieve", mode="retrieve", actor_role="literature_researcher")
            _record_mode_run(
                store,
                run_id="run-online",
                researcher_work_mode="online",
                work_mode_source="rotation",
                search_intent="online_researcher_attack",
            )
            action = next_action(store, research_mode="hard_problem", web_search="live")
            self.assertTrue(action_expects_researcher_session(action), action)
            self.assertEqual(action["researcher_work_mode"], "offline")

    def test_advisor_directive_is_honored_by_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-directive-test")
            _record_mode_run(store, run_id="run-retrieve", mode="retrieve", actor_role="literature_researcher")
            _attach_advisor_directive(store, artifact_id="adv-mode-1", directed_mode="cas", reason="run the finite check on the smallest cases")
            action = next_action(store, research_mode="hard_problem", web_search="live")
            self.assertTrue(action_expects_researcher_session(action), action)
            self.assertEqual(action["researcher_work_mode"], "cas")
            self.assertEqual(action["work_mode_source"], "advisor_directive")
            self.assertEqual(action["advisor_mode_directive_artifact_id"], "adv-mode-1")

    def test_run_rows_persist_work_mode_for_scheduler_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-persist-test")
            _record_mode_run(
                store,
                run_id="run-online",
                researcher_work_mode="online",
                work_mode_source="rotation",
                search_intent="online_researcher_attack",
            )
            state = store.get_scheduler_state()
            row = next(run for run in state["recent_runs"] if run["run_id"] == "run-online")
            self.assertEqual(row["researcher_work_mode"], "online")
            self.assertEqual(row["work_mode_source"], "rotation")
            self.assertIn("search_setting", row)
            summary = researcher_mode_summary(state)
            self.assertEqual(summary["current"]["work_mode"], "online")
            # The full store snapshot shape works too (console/manifest path).
            summary_from_snapshot = researcher_mode_summary(store.get_state())
            self.assertEqual(summary_from_snapshot["current"]["work_mode"], "online")

    def test_prepare_session_carries_work_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-session-test")
            action = {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "researcher_work_mode": "cas",
                "work_mode_source": "rotation",
                "researcher_work_mode_reason": "test",
            }
            plan = prepare_session(store, action)
            self.assertEqual(plan["researcher_work_mode"], "cas")
            self.assertEqual(plan["work_mode_source"], "rotation")


class ResearcherWorkModeManifestTest(unittest.TestCase):
    def test_manifest_exposes_mode_and_gates_cas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-manifest-test")
            offline_action = {
                "mode": "prove",
                "target_id": "root",
                "route_id": "",
                "researcher_work_mode": "offline",
                "work_mode_source": "rotation",
                "researcher_work_mode_reason": "think hard",
            }
            manifest = build_context_manifest(store, target_id="root", action=offline_action, max_chars=60_000)
            self.assertEqual(manifest["workflow_action"]["researcher_work_mode"], "offline")
            self.assertEqual(manifest["workflow_action"]["work_mode_source"], "rotation")
            self.assertFalse(manifest["role_context_policy"]["cas_access"])
            self.assertNotIn("cas_tooling", manifest)
            packet = manifest.get("researcher_packet", {})
            policy = packet.get("researcher_mode_policy", {})
            self.assertEqual(policy.get("work_mode"), "offline")
            self.assertEqual(packet.get("cas_trigger_policy"), {})

            cas_action = dict(offline_action, researcher_work_mode="cas")
            cas_manifest = build_context_manifest(store, target_id="root", action=cas_action, max_chars=60_000)
            self.assertTrue(cas_manifest["role_context_policy"]["cas_access"])
            cas_policy = cas_manifest.get("researcher_packet", {}).get("researcher_mode_policy", {})
            self.assertEqual(cas_policy.get("work_mode"), "cas")

    def test_villain_manifest_cas_follows_work_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-villain-test")
            unstamped = {"mode": "refute", "target_id": "root", "route_id": ""}
            manifest = build_context_manifest(store, target_id="root", action=unstamped, max_chars=60_000)
            self.assertTrue(manifest["role_context_policy"]["cas_access"])
            cas_action = dict(unstamped, researcher_work_mode="cas", work_mode_source="rotation")
            cas_manifest = build_context_manifest(store, target_id="root", action=cas_action, max_chars=60_000)
            self.assertTrue(cas_manifest["role_context_policy"]["cas_access"])
            policy = cas_manifest.get("researcher_packet", {}).get("researcher_mode_policy", {})
            self.assertEqual(policy.get("work_mode"), "cas")
            self.assertIn("villain", policy.get("policy", ""))
            offline_action = dict(unstamped, researcher_work_mode="offline", work_mode_source="rotation")
            offline_manifest = build_context_manifest(store, target_id="root", action=offline_action, max_chars=60_000)
            self.assertFalse(offline_manifest["role_context_policy"]["cas_access"])

    def test_advisor_manifest_shows_researcher_mode_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-advisor-test")
            _record_mode_run(store, run_id="run-online", researcher_work_mode="online", work_mode_source="rotation")
            action = {"mode": "triage_routes", "target_id": "root", "route_id": ""}
            manifest = build_context_manifest(store, target_id="root", action=action)
            mode_state = manifest.get("researcher_mode_state", {})
            self.assertEqual(mode_state.get("current", {}).get("work_mode"), "online")
            self.assertTrue(any("directed_researcher_mode" in item for item in manifest["instructions"]))


class PendingRepairVerifierDispatchTest(unittest.TestCase):
    def test_repair_pending_debt_does_not_veto_verifier_readiness(self) -> None:
        from agents.generation.phase2.scheduler import route_verifier_readiness

        def state_with_debt(resolution_evidence: dict) -> dict:
            return {
                "problem_state": {"current_revision": 10},
                "claims": [
                    {"claim_id": "root", "statement": "root", "validation_status": "untested", "lifecycle_status": "active", "parent_ids": [], "root_impact": 1.0, "reduction_depth": 0},
                ],
                "routes": [
                    {"route_id": "route-aff", "conclusion_claim_id": "root", "status": "active", "relation_to_parent": "sufficient"},
                ],
                "inferences": [
                    {"inference_id": "inf-aff", "route_id": "route-aff", "conclusion_claim_id": "root", "validation_status": "untested", "premise_claim_ids": [], "evidence_artifact_ids_json": json.dumps(["cert-1"])},
                ],
                "debts": [
                    {
                        "debt_id": "debt-cert",
                        "owner_type": "route",
                        "owner_id": "route-aff",
                        "severity": "blocking",
                        "status": "active",
                        "obligation": "audit the certificate",
                        "resolution_evidence_json": json.dumps(resolution_evidence),
                    }
                ],
                "recent_runs": [],
                "research_artifacts": [],
                "retrieval_cards": [],
                "runs": [],
            }

        unrepaired = route_verifier_readiness(state_with_debt({}), "route-aff")
        self.assertFalse(unrepaired["verifier_ready"])
        repaired = route_verifier_readiness(
            state_with_debt({"resolution_status": "repair_submitted_pending_verifier", "repair_submitted_by": "researcher"}),
            "route-aff",
        )
        # The pending repair is the reason to dispatch the verifier, not a veto.
        self.assertTrue(repaired["verifier_ready"], repaired)
        self.assertEqual(repaired["blocking_debt_count"], 0)


class ResearcherWorkModeConsoleTest(unittest.TestCase):
    def test_console_payload_and_markdown_show_mode_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = _make_store(tmpdir, "work-mode-console-test")
            _record_mode_run(store, run_id="run-online", researcher_work_mode="online", work_mode_source="rotation")
            _attach_advisor_directive(store, artifact_id="adv-mode-2", directed_mode="offline", reason="stop searching; prove")
            payload = build_run_console_payload(store)
            mode_state = payload["researcher_mode_state"]
            self.assertEqual(mode_state["current"]["work_mode"], "online")
            self.assertEqual(mode_state["advisor_directive"]["work_mode"], "offline")
            markdown = build_run_console(store)
            self.assertIn("Researcher Mode & Advisor Supervision", markdown)
            self.assertIn("ACTIVE ADVISOR DIRECTIVE", markdown)
            monitor_payload = build_monitor_payload(store)
            self.assertIn("researcher_mode_state", monitor_payload)


if __name__ == "__main__":
    unittest.main()
