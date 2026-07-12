from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from .result_status import normalize_result_relation

RESEARCH_MODES = {
    "independent",
    "proof_first",
    "balanced",
    "hard_problem",
    "citation_first",
    "citation_pass",
    # Conservative referee mode (2026-07-09 TODO 6): audit a submitted proof
    # document instead of proving the statement; see phase2/audit.py.
    "paper_solution_audit",
}
DEFAULT_RESEARCH_MODE = "hard_problem"
DEFAULT_WEB_SEARCH = "live"
RESEARCH_MODE_ALIASES = {
    "citation_first": "balanced",
}
# Per-session work modes (rethlas-style online/offline loop plus CAS), used by
# both adversarial mathematicians: the researcher (prover) and the villain
# (refuter) run the same loop with separate histories and directives — the
# Nagata working mode, both agents equally capable. Distinct from the run-level
# research_mode strategy and from the action verb mode.
RESEARCHER_WORK_MODES = {"online", "offline", "cas"}
RESEARCHER_WORK_MODE_CYCLE = ("online", "offline", "cas")
# The refuter leads with computation: bounded example sweeps are the fastest
# claim-killers, hand-construction second, published-counterexample hunts third.
VILLAIN_WORK_MODE_CYCLE = ("cas", "offline", "online")
ADVISOR_MODE_DIRECTIVE_KEY = "directed_researcher_mode"
ADVISOR_MODE_DIRECTIVE_REASON_KEY = "directed_researcher_mode_reason"
ADVISOR_MODE_DIRECTIVE_STEPS_KEY = "directed_researcher_mode_steps"
ADVISOR_VILLAIN_DIRECTIVE_KEY = "directed_villain_mode"
ADVISOR_VILLAIN_DIRECTIVE_REASON_KEY = "directed_villain_mode_reason"
ADVISOR_VILLAIN_DIRECTIVE_STEPS_KEY = "directed_villain_mode_steps"
MAX_ADVISOR_MODE_DIRECTIVE_STEPS = 3
# A directive is immediate steering, not a standing policy: void it once the
# proof state has moved this many revisions past the advisor_report, so a
# consumed directive can never resurrect when its consuming runs age out of the
# bounded recent_runs window (observed live 2026-07-04: zombie cas directive).
ADVISOR_DIRECTIVE_TTL_REVISIONS = 48
# Actions that hard-reserve the pass for local theorem work: these always run
# offline (advisor directives still outrank them).
STRONG_OFFLINE_BIAS_ACTION_FLAGS = (
    "bottleneck_lock_required",
    "decisive_theorem_test_required",
    "creative_proof_attack_required",
    "proof_route_conversion_required",
    "obstruction_route_conversion_required",
)
# Actions that prefer offline thinking but yield to the rotation override when
# the loop has been stuck in one mode too long — otherwise mature runs never
# rotate at all (measured live: structural 61, rotation 0).
WEAK_OFFLINE_BIAS_ACTION_FLAGS = (
    "research_synthesis_required",
    "global_synthesis_required",
    "theorem_building_synthesis_required",
    "proof_architecture_required",
    "advisor_followup_required",
    "no_result_search_synthesis_required",
)
OFFLINE_BIAS_ACTION_FLAGS = STRONG_OFFLINE_BIAS_ACTION_FLAGS + WEAK_OFFLINE_BIAS_ACTION_FLAGS
# After this many consecutive same-mode primary passes, a weak bias yields to
# the next mode in the cycle so online/cas exposure is guaranteed over time.
ROTATION_STALENESS_WINDOW = 3
RETRIEVAL_RELATION_LADDER = {
    "direct_match": 0,
    "stronger_match": 1,
    "equivalent_reformulation": 2,
    "conditional_match": 3,
    "partial_match": 4,
    "method_match": 5,
    "obstructing": 6,
    "candidate_counterexample": 7,
    "background": 8,
    "irrelevant": 9,
    "no_useful_result_found": 10,
}
LEGACY_RETRIEVAL_CLASSIFICATIONS = {
    "known_exact": "direct_match",
    "known_stronger": "stronger_match",
    "known_partial": "partial_match",
    "probably_open": "obstructing",
}
USEFUL_RETRIEVAL_CLASSIFICATIONS = {
    "direct_match",
    "stronger_match",
    "equivalent_reformulation",
    "conditional_match",
    "partial_match",
    "method_match",
    "obstructing",
    "candidate_counterexample",
}
LIBRARIAN_LEVELS = {"scout", "reader", "research_librarian"}


def normalize_research_mode(value: str | None) -> str:
    mode = value or DEFAULT_RESEARCH_MODE
    mode = RESEARCH_MODE_ALIASES.get(mode, mode)
    if mode not in RESEARCH_MODES:
        allowed = ", ".join(sorted(RESEARCH_MODES))
        raise ValueError(f"unsupported research_mode: {mode}; expected one of {allowed}")
    return mode


def should_run_librarian(
    state: Mapping[str, Any],
    *,
    research_mode: str | None,
    web_search: str | None,
    target_id: str = "root",
    phase: str = "initial",
) -> Dict[str, Any]:
    """Decide whether a research-oriented run should begin with literature lookup."""
    mode = normalize_research_mode(research_mode)
    if mode in {"independent", "proof_first"}:
        return {"run": False, "reason": f"{mode} mode does not force a literature scan"}
    if mode == "citation_pass" and phase != "post_integration":
        return {"run": False, "reason": "citation_pass waits until an independent proof is integrated"}
    search_setting = normalize_web_search(web_search)
    if search_setting != "live":
        return {"run": False, "reason": "literature scan requires --web-search live"}
    useful = _useful_retrieval_cards(state, target_id=target_id)
    if useful:
        return {"run": False, "reason": "a useful retrieval card is already cached", "card_id": useful[0].get("card_id", "")}
    if phase == "initial" and _retrieve_run_count(state) > 0:
        return {"run": False, "reason": "an initial literature scan has already been attempted"}
    if phase == "post_integration" and _retrieve_run_count(state, intent="citation_pass") > 0:
        return {"run": False, "reason": "a citation-pass literature scan has already been attempted"}

    if mode == "citation_pass":
        reason = "citation_pass adds literature context after independent integration"
    elif mode == "hard_problem":
        reason = "hard_problem mode starts literature scouting alongside a serious researcher attack"
    elif mode == "paper_solution_audit":
        reason = "paper_solution_audit starts a citation-audit scan: external theorems used by the submitted proof need exact source/theorem/hypothesis checks"
    else:
        reason = "balanced mode starts a literature scout alongside direct research"
    return {
        "run": True,
        "reason": reason,
        "target_id": target_id,
        "search_permission": "live",
        "search_intent": "citation_pass" if mode == "citation_pass" else "literature_scoping",
        "librarian_level": librarian_level_for_state(state, target_id=target_id, phase=phase),
    }


def normalize_web_search(value: str | None) -> str:
    search_setting = value or DEFAULT_WEB_SEARCH
    if search_setting not in {"disabled", "live"}:
        raise ValueError(f"unsupported web_search policy: {search_setting}")
    return search_setting


def normalize_researcher_work_mode(value: str | None) -> str:
    work_mode = str(value or "").strip().lower()
    if work_mode not in RESEARCHER_WORK_MODES:
        allowed = ", ".join(sorted(RESEARCHER_WORK_MODES))
        raise ValueError(f"unsupported researcher work mode: {value}; expected one of {allowed}")
    return work_mode


def action_expects_researcher_session(action: Mapping[str, Any] | None) -> bool:
    """Mirror codex_runner.actor_role_for_action for the researcher role only.

    Kept in sync by test coverage so the work-mode stamp and the runner role
    routing can never disagree about which sessions are researcher sessions.
    """
    action = action or {}
    mode = str(action.get("mode") or "prove")
    route_id = str(action.get("route_id") or "")
    if mode == "prove":
        return not (route_id or action.get("citation_certification_required") or action.get("citation_triage_required"))
    if mode in {"reduce", "weaken", "strengthen"}:
        if action.get("debt_id"):
            return bool(route_id or action.get("proof_repair_required") or action.get("research_diagnostic_required"))
        return True
    return False


def action_expects_villain_session(action: Mapping[str, Any] | None) -> bool:
    """Mirror codex_runner.actor_role_for_action for the villain role."""
    return str((action or {}).get("mode") or "") == "refute"


def _work_mode_role_for_action(action: Mapping[str, Any] | None) -> str:
    if action_expects_researcher_session(action):
        return "researcher"
    if action_expects_villain_session(action):
        return "villain"
    return ""


def _artifact_metadata(artifact: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = artifact.get("metadata_json", artifact.get("metadata", {}))
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    return metadata if isinstance(metadata, Mapping) else {}


def _revision_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _recent_run_rows(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Recent run rows, newest first, from either state snapshot shape.

    Scheduler state carries `recent_runs`; the full store snapshot only carries
    the complete `runs` table (whose retrieve-only scheduler twin lacks run_id).
    """
    rows = state.get("recent_runs")
    if isinstance(rows, list):
        return rows
    rows = [row for row in state.get("runs", []) if isinstance(row, Mapping) and row.get("run_id")]
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows[:32]


def _advisor_artifact_rows(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = state.get("research_artifacts")
    if isinstance(rows, list):
        return rows
    return [row for row in state.get("artifacts", []) if isinstance(row, Mapping)]


_ROLE_DIRECTIVE_KEYS = {
    "researcher": (ADVISOR_MODE_DIRECTIVE_KEY, ADVISOR_MODE_DIRECTIVE_REASON_KEY, ADVISOR_MODE_DIRECTIVE_STEPS_KEY),
    "villain": (ADVISOR_VILLAIN_DIRECTIVE_KEY, ADVISOR_VILLAIN_DIRECTIVE_REASON_KEY, ADVISOR_VILLAIN_DIRECTIVE_STEPS_KEY),
}


def advisor_mode_directive(state: Mapping[str, Any], *, role: str = "researcher") -> Dict[str, Any] | None:
    """Return the newest still-active advisor work-mode directive for one role.

    The PhD advisor supervises both work-mode loops by writing
    metadata.directed_researcher_mode / metadata.directed_villain_mode on an
    advisor_report. A directive covers *_steps upcoming passes of that role
    (default 1, capped) and expires once that many completed runs of the role
    have consumed it. The two roles' directives are fully independent.
    """
    directive_key, reason_key, steps_key = _ROLE_DIRECTIVE_KEYS.get(role, _ROLE_DIRECTIVE_KEYS["researcher"])
    candidates: list[tuple[int, str, Mapping[str, Any], str, Mapping[str, Any]]] = []
    for artifact in _advisor_artifact_rows(state):
        if str(artifact.get("artifact_type") or "") != "advisor_report":
            continue
        if str(artifact.get("producer_role") or "") != "phd_advisor":
            continue
        metadata = _artifact_metadata(artifact)
        directed = str(metadata.get(directive_key) or "").strip().lower()
        if directed not in RESEARCHER_WORK_MODES:
            continue
        revision = _revision_int(artifact.get("state_revision"))
        candidates.append((revision, str(artifact.get("artifact_id") or ""), artifact, directed, metadata))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    revision, artifact_id, _artifact, directed, metadata = candidates[0]
    problem_state = state.get("problem_state") if isinstance(state.get("problem_state"), Mapping) else {}
    current_revision = _revision_int(problem_state.get("current_revision"))
    if current_revision >= 0 and revision >= 0 and current_revision - revision > ADVISOR_DIRECTIVE_TTL_REVISIONS:
        return None
    try:
        steps = int(metadata.get(steps_key) or 1)
    except (TypeError, ValueError):
        steps = 1
    steps = max(1, min(MAX_ADVISOR_MODE_DIRECTIVE_STEPS, steps))
    consumed = 0
    for run in _recent_run_rows(state):
        if str(run.get("actor_role") or "") != role:
            continue
        if str(run.get("work_mode_source") or "") not in {"advisor_directive", "advisor_directive_downgraded"}:
            continue
        # Only a completed pass consumes supervision: a stall-killed, timed-out,
        # or rejected session never delivered the directed work.
        if str(run.get("status") or "") != "completed":
            continue
        if _revision_int(run.get("state_revision")) >= revision:
            consumed += 1
    steps_remaining = steps - consumed
    if steps_remaining <= 0:
        return None
    return {
        "work_mode": directed,
        "artifact_id": artifact_id,
        "reason": str(metadata.get(reason_key) or "").strip(),
        "steps": steps,
        "steps_remaining": steps_remaining,
        "state_revision": revision,
    }


def _researcher_work_mode_history(
    state: Mapping[str, Any], *, actor_role: str = "researcher", include_companions: bool = False
) -> list[Dict[str, Any]]:
    """Recent work modes for one role's sessions, newest first."""
    history: list[Dict[str, Any]] = []
    for run in _recent_run_rows(state):
        if str(run.get("actor_role") or "") != actor_role:
            continue
        work_mode = str(run.get("researcher_work_mode") or "").strip().lower()
        if work_mode not in RESEARCHER_WORK_MODES:
            continue
        source = str(run.get("work_mode_source") or "")
        if not include_companions and source == "companion_default":
            continue
        history.append(
            {
                "run_id": str(run.get("run_id") or ""),
                "work_mode": work_mode,
                "source": source,
                "search_intent": str(run.get("search_intent") or ""),
                "status": str(run.get("status") or ""),
                "created_at": str(run.get("created_at") or ""),
            }
        )
    return history


def researcher_work_mode_decision(
    state: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    research_mode: str | None,
    web_search: str | None,
) -> Dict[str, Any]:
    """Choose the researcher work mode for one session.

    Priority: explicit action stamp, companion rotation, advisor directive,
    structural action bias, then the clean online -> offline -> cas rotation.
    """
    mode = normalize_research_mode(research_mode)
    online_allowed = normalize_web_search(web_search) == "live" and mode != "independent"
    explicit = str(action.get("researcher_work_mode") or "").strip().lower()
    if explicit in RESEARCHER_WORK_MODES:
        return {
            "work_mode": explicit,
            "source": str(action.get("work_mode_source") or "action_explicit"),
            "reason": str(action.get("researcher_work_mode_reason") or "work mode fixed by the scheduler action"),
        }
    if action_expects_villain_session(action):
        return _villain_work_mode_decision(state, action, online_allowed=online_allowed)
    if action.get("parallel_companion"):
        if action.get("cas_check_recommended"):
            return {
                "work_mode": "cas",
                "source": "companion_structural",
                "reason": "parallel researcher companion has a bounded computation assigned",
            }
        cycle = [m for m in RESEARCHER_WORK_MODE_CYCLE if m != "online" or online_allowed]
        history = _researcher_work_mode_history(state, include_companions=True)
        last = history[0]["work_mode"] if history else ""
        start = (cycle.index(last) + 1) % len(cycle) if last in cycle else 0
        try:
            slot = max(0, int(action.get("parallel_companion_index") or 0))
        except (TypeError, ValueError):
            slot = 0
        companion_mode = cycle[(start + slot) % len(cycle)]
        return {
            "work_mode": companion_mode,
            "source": "companion_rotation",
            "reason": (
                "parallel researcher companions rotate across search, proof, and computation modes; "
                f"companion slot {slot + 1} selected {companion_mode}"
            ),
        }
    directive = advisor_mode_directive(state)
    if directive:
        directed = str(directive.get("work_mode") or "")
        if directed == "online" and not online_allowed:
            return {
                "work_mode": "offline",
                "source": "advisor_directive_downgraded",
                "reason": "advisor directed an online search pass but live web search is unavailable for this run; falling back to offline thinking",
                "advisor_mode_directive_artifact_id": str(directive.get("artifact_id") or ""),
            }
        return {
            "work_mode": directed,
            "source": "advisor_directive",
            "reason": directive.get("reason")
            or f"PhD advisor directed the researcher to work in {directed} mode",
            "advisor_mode_directive_artifact_id": str(directive.get("artifact_id") or ""),
        }
    if action.get("cas_check_recommended"):
        return {
            "work_mode": "cas",
            "source": "structural",
            "reason": "the scheduled action recommends a bounded CAS computation",
        }
    cycle = [m for m in RESEARCHER_WORK_MODE_CYCLE if m != "online" or online_allowed]
    history = _researcher_work_mode_history(state)
    strong_flags = [flag for flag in STRONG_OFFLINE_BIAS_ACTION_FLAGS if action.get(flag)]
    if strong_flags:
        return {
            "work_mode": "offline",
            "source": "structural",
            "reason": f"the scheduled action reserves this pass for hard local proof work ({strong_flags[0]})",
        }
    weak_flags = [flag for flag in WEAK_OFFLINE_BIAS_ACTION_FLAGS if action.get(flag)]
    recent = [item["work_mode"] for item in history[:ROTATION_STALENESS_WINDOW]]
    stuck = len(recent) >= ROTATION_STALENESS_WINDOW and len(set(recent)) == 1
    if weak_flags and not (stuck and recent[0] == "offline"):
        return {
            "work_mode": "offline",
            "source": "structural",
            "reason": f"the scheduled action prefers offline proof work ({weak_flags[0]})",
        }
    last = history[0]["work_mode"] if history else ""
    if stuck and last in cycle:
        next_mode = cycle[(cycle.index(last) + 1) % len(cycle)]
        return {
            "work_mode": next_mode,
            "source": "rotation_override",
            "reason": (
                f"the last {ROTATION_STALENESS_WINDOW} researcher passes all ran {last}; rotating to {next_mode} "
                "to keep search/think/experiment exposure balanced"
            ),
        }
    if last in cycle:
        next_mode = cycle[(cycle.index(last) + 1) % len(cycle)]
    else:
        next_mode = cycle[0]
    return {
        "work_mode": next_mode,
        "source": "rotation",
        "reason": "default researcher loop rotates cleanly through " + " -> ".join(cycle),
    }


def _villain_work_mode_decision(
    state: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    online_allowed: bool,
) -> Dict[str, Any]:
    """Work mode for a refutation pass — same loop, refuter-flavored defaults.

    Villain sessions are almost always parallel companions, so unlike
    researcher companions they rotate on their own history (there is no primary
    villain stream for rotation to act on otherwise).
    """
    directive = advisor_mode_directive(state, role="villain")
    if directive:
        directed = str(directive.get("work_mode") or "")
        if directed == "online" and not online_allowed:
            return {
                "work_mode": "offline",
                "source": "advisor_directive_downgraded",
                "reason": "advisor directed an online counterexample hunt but live web search is unavailable for this run; falling back to offline construction",
                "advisor_mode_directive_artifact_id": str(directive.get("artifact_id") or ""),
            }
        return {
            "work_mode": directed,
            "source": "advisor_directive",
            "reason": directive.get("reason") or f"PhD advisor directed the villain to work in {directed} mode",
            "advisor_mode_directive_artifact_id": str(directive.get("artifact_id") or ""),
        }
    if action.get("cas_check_recommended"):
        return {
            "work_mode": "cas",
            "source": "structural",
            "reason": "the scheduled refutation action recommends a bounded CAS computation",
        }
    cycle = [m for m in VILLAIN_WORK_MODE_CYCLE if m != "online" or online_allowed]
    history = _researcher_work_mode_history(state, actor_role="villain", include_companions=True)
    last = history[0]["work_mode"] if history else ""
    if last in cycle:
        next_mode = cycle[(cycle.index(last) + 1) % len(cycle)]
    else:
        next_mode = cycle[0]
    return {
        "work_mode": next_mode,
        "source": "rotation",
        "reason": "refuter loop rotates through " + " -> ".join(cycle) + " (computation-first for counterexample sweeps)",
    }


def stamp_researcher_work_mode(
    state: Mapping[str, Any],
    action: Any,
    *,
    research_mode: str | None,
    web_search: str | None,
) -> Any:
    """Attach the work mode to a scheduled researcher or villain action in place."""
    if not isinstance(action, dict):
        return action
    if str(action.get("mode") or "") in {"stop_with_partial_results", "stop_solved"}:
        return action
    if not _work_mode_role_for_action(action):
        return action
    decision = researcher_work_mode_decision(state, action, research_mode=research_mode, web_search=web_search)
    action["researcher_work_mode"] = decision["work_mode"]
    action["researcher_work_mode_reason"] = decision["reason"]
    action["work_mode_source"] = decision["source"]
    directive_artifact = str(decision.get("advisor_mode_directive_artifact_id") or "")
    if directive_artifact:
        action["advisor_mode_directive_artifact_id"] = directive_artifact
    return action


def researcher_mode_summary(
    state: Mapping[str, Any],
    *,
    research_mode: str | None = None,
    web_search: str | None = None,
) -> Dict[str, Any]:
    """Compact work-mode state for the console, dashboard, and advisor."""
    history = _researcher_work_mode_history(state, include_companions=True)
    primary_history = [item for item in history if item.get("source") != "companion_default"]
    directive = advisor_mode_directive(state)
    villain_history = _researcher_work_mode_history(state, actor_role="villain", include_companions=True)
    villain_directive = advisor_mode_directive(state, role="villain")
    try:
        predicted = researcher_work_mode_decision(
            state,
            {"mode": "prove"},
            research_mode=research_mode,
            web_search=web_search,
        )
    except ValueError:
        predicted = {}
    try:
        villain_predicted = researcher_work_mode_decision(
            state,
            {"mode": "refute", "parallel_companion": True},
            research_mode=research_mode,
            web_search=web_search,
        )
    except ValueError:
        villain_predicted = {}
    return {
        "policy": "researcher and villain online/offline/cas work-mode loops with PhD-advisor supervision",
        "cycle": list(RESEARCHER_WORK_MODE_CYCLE),
        "current": primary_history[0] if primary_history else {},
        "history": history[:10],
        "advisor_directive": directive or {},
        "predicted_next": predicted,
        "villain": {
            "cycle": list(VILLAIN_WORK_MODE_CYCLE),
            "current": villain_history[0] if villain_history else {},
            "history": villain_history[:10],
            "advisor_directive": villain_directive or {},
            "predicted_next": villain_predicted,
        },
    }


def search_policy_for_action(
    action: Mapping[str, Any],
    *,
    research_mode: str | None,
    web_search: str | None,
) -> str | None:
    """Return the web-search setting for one Codex session.

    In opt-in research modes, live search goes to literature-researcher sessions
    and to researcher sessions running in the online work mode. The historical
    proof_first mode preserves the caller's global setting for compatibility
    with earlier experiments.
    """
    mode = str(action.get("mode") or "")
    requested = normalize_web_search(web_search)
    research = normalize_research_mode(research_mode)
    if research == "independent":
        return "disabled"
    if research == "proof_first":
        return requested
    if mode == "retrieve" and requested == "live":
        return "live"
    if (
        requested == "live"
        and str(action.get("researcher_work_mode") or "") == "online"
        and _work_mode_role_for_action(action)
    ):
        return "live"
    return "disabled"


def research_intent_for_action(
    action: Mapping[str, Any],
    *,
    research_mode: str | None,
    session_web_search: str | None,
) -> str:
    explicit_intent = str(action.get("search_intent") or "").strip()
    if explicit_intent:
        return explicit_intent
    mode = str(action.get("mode") or "")
    research = normalize_research_mode(research_mode)
    search = normalize_web_search(session_web_search)
    if mode == "retrieve":
        if research == "citation_pass":
            return "citation_pass"
        return "literature_scoping" if search == "live" else "local_retrieval"
    if search == "live":
        if str(action.get("researcher_work_mode") or "") == "online":
            return "online_researcher_attack"
        return "legacy_live_search"
    return "independent_solve"


def _retrieve_run_count(state: Mapping[str, Any], *, intent: str | None = None) -> int:
    count = 0
    for row in state.get("runs", []):
        if row.get("mode") != "retrieve":
            continue
        if intent is not None and row.get("search_intent") != intent:
            continue
        count += 1
    return count


def _useful_retrieval_cards(state: Mapping[str, Any], *, target_id: str) -> list[Mapping[str, Any]]:
    useful: list[Mapping[str, Any]] = []
    for row in state.get("retrieval_cards", []):
        applicability = row.get("applicability", row.get("applicability_json", {}))
        if isinstance(applicability, str):
            try:
                applicability = json.loads(applicability)
            except json.JSONDecodeError:
                applicability = {}
        if not isinstance(applicability, Mapping):
            applicability = {}
        card_target = str(applicability.get("target_id") or target_id)
        if card_target not in {target_id, "root"}:
            continue
        classification = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation") or "")
        if classification in USEFUL_RETRIEVAL_CLASSIFICATIONS:
            useful.append(row)
    return useful


def normalize_retrieval_relation(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    text = LEGACY_RETRIEVAL_CLASSIFICATIONS.get(text, text)
    if text in RETRIEVAL_RELATION_LADDER:
        return text
    root_relation = normalize_result_relation(text)
    if root_relation == "exact":
        return "direct_match"
    if root_relation == "stronger":
        return "stronger_match"
    if root_relation == "equivalent":
        return "equivalent_reformulation"
    if root_relation == "conditional":
        return "conditional_match"
    if root_relation == "partial":
        return "partial_match"
    if root_relation == "method":
        return "method_match"
    return "no_useful_result_found" if text in {"", "none", "unknown"} else text


def theorem_matching_confidence(
    applicability: Mapping[str, Any],
    *,
    missing_hypotheses: Any = None,
) -> Dict[str, Any]:
    relation = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation") or "")
    base_scores = {
        "direct_match": 0.9,
        "stronger_match": 0.86,
        "equivalent_reformulation": 0.86,
        "conditional_match": 0.62,
        "partial_match": 0.48,
        "method_match": 0.34,
        "obstructing": 0.58,
        "candidate_counterexample": 0.5,
        "background": 0.22,
        "irrelevant": 0.05,
        "no_useful_result_found": 0.0,
    }
    score = base_scores.get(relation, 0.15)
    status = str(applicability.get("theorem_matching_status") or "").lower()
    if "verified" in status and "unverified" not in status:
        score += 0.08
    if "unverified" in status or "unknown" in status:
        score -= 0.08
    if applicability.get("implication_to_target_verified") is True:
        score += 0.08
    missing = missing_hypotheses
    if missing is None:
        missing = applicability.get("missing_hypotheses", [])
    if isinstance(missing, str):
        try:
            missing = json.loads(missing)
        except json.JSONDecodeError:
            missing = [missing] if missing else []
    missing_count = len(missing or []) if isinstance(missing, list) else 0
    score -= min(0.2, 0.05 * missing_count)
    score = max(0.0, min(1.0, score))
    if score >= 0.78:
        level = "high"
    elif score >= 0.5:
        level = "medium"
    elif score > 0:
        level = "low"
    else:
        level = "none"
    return {
        "level": level,
        "score": round(score, 2),
        "relation": relation,
        "missing_hypothesis_count": missing_count,
    }


def librarian_level_for_state(state: Mapping[str, Any], *, target_id: str = "root", phase: str = "initial") -> str:
    """Use cheap search by default and escalate only when matching is valuable."""
    if phase == "post_integration":
        return "reader"
    active_debts = [row for row in state.get("debts", []) if row.get("status") == "active"]
    blocking = [row for row in active_debts if row.get("severity") == "blocking"]
    if blocking:
        return "research_librarian"
    cards = _target_retrieval_cards(state, target_id=target_id)
    if any(normalize_retrieval_relation(_applicability(row).get("classification") or _applicability(row).get("relation")) in {"direct_match", "stronger_match", "equivalent_reformulation", "conditional_match"} for row in cards):
        return "research_librarian"
    if cards:
        return "reader"
    return "scout"


def librarian_escalation_policy(level: str) -> Dict[str, Any]:
    if level not in LIBRARIAN_LEVELS:
        level = "scout"
    if level == "research_librarian":
        return {
            "level": level,
            "purpose": "Resolve hard theorem matching, hypothesis translation, and implication-to-target questions.",
            "allowed_depth": "deep_read_selected_sources",
            "escalation_triggers": [
                "candidate source appears to directly prove, strengthen, or equivalently reformulate the target",
                "candidate source may close an active blocking proof debt",
                "hypothesis or notation translation is nontrivial",
                "the workflow is stuck and a source may certify a partial theorem",
            ],
        }
    if level == "reader":
        return {
            "level": level,
            "purpose": "Read promising sources enough to extract theorem cards and hypotheses.",
            "allowed_depth": "read_relevant_sections",
            "escalation_triggers": [
                "the theorem statement shape matches the target",
                "source contains a plausible stronger or equivalent result",
                "missing hypotheses must be checked carefully",
            ],
        }
    return {
        "level": level,
        "purpose": "Search cheaply for candidate names, sources, and statement shapes.",
        "allowed_depth": "skim_search_results",
        "escalation_triggers": [
            "same theorem name or same quantifier/conclusion pattern appears",
            "source is canonical or formalized",
            "source mentions a route that can close a current debt",
        ],
    }


def _target_retrieval_cards(state: Mapping[str, Any], *, target_id: str) -> list[Mapping[str, Any]]:
    cards: list[Mapping[str, Any]] = []
    for row in state.get("retrieval_cards", []):
        applicability = _applicability(row)
        card_target = str(applicability.get("target_id") or target_id)
        if card_target in {target_id, "root"}:
            cards.append(row)
    return cards


def _applicability(row: Mapping[str, Any]) -> Mapping[str, Any]:
    applicability = row.get("applicability", row.get("applicability_json", {}))
    if isinstance(applicability, str):
        try:
            applicability = json.loads(applicability)
        except json.JSONDecodeError:
            applicability = {}
    return applicability if isinstance(applicability, Mapping) else {}
