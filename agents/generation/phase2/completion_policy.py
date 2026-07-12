from __future__ import annotations

"""Full-proof-first completion policy (2026-07-09 TODO 7).

The run-level ``completion_policy`` decides how willing the scheduler is to
stop with partial results:

- ``full_proof_first`` (default): the root theorem stays the target; a
  ``stop_with_partial_results`` action is blocked while genuine progress
  signals remain (active plausible route, verifier-ready route, actionable
  narrowed blocker, productive branch, untried high-score route) unless the
  token budget is exhausted, an operator stop was requested, or the PhD
  advisor recorded an explicit partial-mode transition justification.
- ``publication_ready``: applies the same full-proof discipline, then opts
  into the post-solve paper authoring and editorial gate before termination.
- ``partial_ok``: the user explicitly asked for partial results as an
  acceptable main deliverable; stops are allowed (``user_partial_mode``).
- ``exploratory``: exploration is the point; stops are allowed the same way.

Soft wording in the problem markdown ("possible partial results", "any
indication", "try to find", ...) NEVER flips the policy by itself: the
root-intent parser only records a ``root_intent_resolution`` event separating
the exploratory phrasing from the formal target. Only the explicit
``--completion-policy`` flag changes the policy.

When a stop IS allowed, the action records one explicit ``stop_reason_code``
from ``CANONICAL_STOP_REASON_CODES`` (plus a few infrastructure codes for
non-mathematical stops such as invariant violations).
"""

import re
from typing import Any, Dict, List, Mapping, Optional

from .branch_summary import build_branch_summaries
from .graph_policy import route_scoreboard
from .models import COMPLETION_POLICIES, DEFAULT_COMPLETION_POLICY, json_loads

# The three run intents from the update advice. Soft wording maps to
# prove_full_statement unless the explicit policy flag says otherwise; the
# paper_solution_audit research mode maps to audit_or_problem_refinement.
RUN_INTENTS = {"prove_full_statement", "explore_partial_results", "audit_or_problem_refinement"}

ROOT_INTENT_EVENT_TYPE = "root_intent_resolution"

# Explicit stop-reason vocabulary. The canonical six explain WHY the full
# theorem was not reached; the extra codes cover infrastructure stops that are
# outside the completion policy's jurisdiction.
CANONICAL_STOP_REASON_CODES = {
    "exhausted_budget",
    "refuted_statement",
    "missing_external_theorem",
    "unresolved_construction",
    "failed_route_family",
    "user_partial_mode",
}
INFRA_STOP_REASON_CODES = {
    "state_invariant_violation",
    "execution_failure",
    "operator_stop",
}
STOP_REASON_CODES = CANONICAL_STOP_REASON_CODES | INFRA_STOP_REASON_CODES

# Language/formulation problems become precise debts, never permission to
# weaken the target (TODO 7 item 6). These are debt_type values (or obligation
# prefixes) matching the existing free-text debt_type convention.
LANGUAGE_DEBT_TYPES = {
    "ambiguous_hypothesis",
    "overbroad_statement",
    "missing_quantifier",
    "root_scope_mismatch",
}

# Advisor partial-mode transition contract (TODO 7 item 4): the advisor may
# justify moving from full-proof pursuit to partial-report mode by attaching an
# advisor_report whose metadata carries these keys; the scheduler guard honors
# it as an explicit, recorded allowance.
ADVISOR_PARTIAL_TRANSITION_KEY = "partial_mode_transition"
ADVISOR_PARTIAL_TRANSITION_REASON_KEY = "partial_mode_transition_reason"
ADVISOR_PARTIAL_TRANSITION_CODE_KEY = "partial_mode_stop_reason_code"

# Soft/exploratory wording that must not flip the policy on its own.
SOFT_WORDING_PATTERNS: tuple[tuple[str, str], ...] = (
    ("possible partial results", r"possible\s+partial\s+results?"),
    ("partial progress is acceptable", r"partial\s+(?:progress|results?)\s+(?:is|are|would\s+be)\s+(?:acceptable|welcome|fine|enough|ok(?:ay)?)"),
    ("any partial result", r"any\s+partial\s+(?:results?|progress)"),
    ("any indication", r"any\s+indication"),
    ("try to find", r"try\s+to\s+(?:find|get|obtain|prove|show)"),
    ("even a partial", r"even\s+a\s+partial"),
    ("if possible", r"if\s+(?:at\s+all\s+)?possible"),
    ("would be interesting", r"would\s+(?:already\s+)?be\s+(?:interesting|useful|valuable|nice)"),
    ("see how far", r"see\s+how\s+far"),
    ("explore", r"\bexplor(?:e|ing|atory)\b"),
)

_UNTRIED_HIGH_SCORE_MIN = 2


def normalize_completion_policy(value: Optional[str]) -> str:
    policy = str(value or DEFAULT_COMPLETION_POLICY).strip().lower().replace("-", "_")
    if policy not in COMPLETION_POLICIES:
        allowed = ", ".join(sorted(COMPLETION_POLICIES))
        raise ValueError(f"unsupported completion_policy: {value}; expected one of {allowed}")
    return policy


def completion_policy_for_state(state: Mapping[str, Any]) -> str:
    problem = state.get("problem_state") if isinstance(state.get("problem_state"), Mapping) else {}
    raw = str((problem or {}).get("completion_policy") or DEFAULT_COMPLETION_POLICY)
    try:
        return normalize_completion_policy(raw)
    except ValueError:
        return DEFAULT_COMPLETION_POLICY


def detect_soft_wording(markdown: str) -> List[str]:
    """Return the soft/exploratory phrases present in the problem markdown."""
    text = " ".join(str(markdown or "").lower().split())
    found: List[str] = []
    for label, pattern in SOFT_WORDING_PATTERNS:
        if re.search(pattern, text):
            found.append(label)
    return found


def resolve_run_intent(*, completion_policy: str, research_mode: str | None = None) -> str:
    """Only the explicit policy flag (or audit research mode) sets the intent."""
    if str(research_mode or "") == "paper_solution_audit":
        return "audit_or_problem_refinement"
    policy = normalize_completion_policy(completion_policy)
    if policy in {"partial_ok", "exploratory"}:
        return "explore_partial_results"
    return "prove_full_statement"


def parse_root_intent(
    markdown: str,
    *,
    completion_policy: str | None = None,
    research_mode: str | None = None,
) -> Dict[str, Any]:
    """Separate exploratory user phrasing from the formal mathematical target.

    Soft wording is recorded but NEVER flips the policy: the resolved intent
    follows only the explicit completion_policy flag (and the audit research
    mode). The result is the payload of the ``root_intent_resolution`` note.
    """
    policy = normalize_completion_policy(completion_policy)
    soft_phrases = detect_soft_wording(markdown)
    resolved = resolve_run_intent(completion_policy=policy, research_mode=research_mode)
    if soft_phrases and resolved == "prove_full_statement":
        note = (
            "Problem markdown contains soft/exploratory wording, but soft wording never flips the "
            "completion policy by itself: the formal root statement remains the default full-proof "
            "target. Only an explicit --completion-policy flag selects a partial-results deliverable."
        )
    elif soft_phrases:
        note = (
            "Problem markdown contains soft/exploratory wording and the operator explicitly selected "
            f"completion_policy={policy}; partial results are an accepted deliverable for this run."
        )
    else:
        note = "No soft/exploratory wording detected; the formal root statement is the target."
    return {
        "resolved_intent": resolved,
        "completion_policy": policy,
        "soft_phrases": soft_phrases,
        "soft_wording_detected": bool(soft_phrases),
        "policy_flipped_by_wording": False,
        "note": note,
    }


def record_root_intent_resolution(
    store: Any,
    *,
    completion_policy: str | None = None,
    research_mode: str | None = None,
    markdown: str | None = None,
) -> Dict[str, Any]:
    """Record the root-intent resolution note as a proof-state event (once).

    The event is the codebase's pattern for run-level notes (run_control,
    init); it never mutates the root statement or the policy.
    """
    with store.connect() as conn:
        problem = store.get_problem_row(conn)
        existing = conn.execute(
            "SELECT payload_json FROM events WHERE event_type = ? ORDER BY event_id DESC LIMIT 1",
            (ROOT_INTENT_EVENT_TYPE,),
        ).fetchone()
        policy = normalize_completion_policy(
            completion_policy if completion_policy is not None else problem.get("completion_policy")
        )
        payload = parse_root_intent(
            markdown if markdown is not None else str(problem.get("root_statement") or ""),
            completion_policy=policy,
            research_mode=research_mode,
        )
        if existing is not None:
            previous = json_loads(existing["payload_json"], {})
            if isinstance(previous, dict) and previous.get("completion_policy") == payload["completion_policy"]:
                payload["already_recorded"] = True
                return payload
        store.write_event(conn, int(problem["current_revision"]), ROOT_INTENT_EVENT_TYPE, payload)
        conn.commit()
    return payload


def latest_root_intent_resolution(store: Any) -> Dict[str, Any]:
    with store.connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM events WHERE event_type = ? ORDER BY event_id DESC LIMIT 1",
            (ROOT_INTENT_EVENT_TYPE,),
        ).fetchone()
    payload = json_loads(row["payload_json"] if row else None, {})
    return payload if isinstance(payload, dict) else {}


# ---------------------------------------------------------------------------
# Scheduler stop guard
# ---------------------------------------------------------------------------


def partial_stop_progress_signals(
    state: Mapping[str, Any],
    *,
    verifier_ready_routes: Optional[List[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Progress signals that block a premature partial stop under
    full_proof_first: active plausible routes, verifier-ready routes,
    narrowed/actionable blockers, productive branches (branch_summary status
    keep_exploiting), and untried high-score routes."""
    plausible_routes = _active_plausible_route_ids(state)
    ready = [dict(row) for row in (verifier_ready_routes or [])]
    narrowed = _actionable_narrowed_blockers(state)
    productive = _productive_branch_ids(state)
    untried = _untried_high_score_route_ids(state)
    signals = {
        "active_plausible_routes": plausible_routes,
        "verifier_ready_routes": [str(row.get("route_id") or "") for row in ready],
        "narrowed_actionable_blockers": narrowed,
        "productive_branches": productive,
        "untried_high_score_routes": untried,
    }
    signals["any"] = any(bool(value) for value in signals.values())
    return signals


def advisor_partial_transition(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Newest advisor_report justifying a transition to partial-report mode."""
    candidates: List[tuple[int, str, Dict[str, Any]]] = []
    rows = state.get("research_artifacts")
    if not isinstance(rows, list):
        rows = [row for row in state.get("artifacts", []) if isinstance(row, Mapping)]
    for artifact in rows:
        if str(artifact.get("artifact_type") or "") != "advisor_report":
            continue
        if str(artifact.get("producer_role") or "") not in {"phd_advisor", "advisor"}:
            continue
        metadata = artifact.get("metadata_json", {})
        if isinstance(metadata, str):
            metadata = json_loads(metadata, {})
        if not isinstance(metadata, Mapping) or not metadata.get(ADVISOR_PARTIAL_TRANSITION_KEY):
            continue
        code = str(metadata.get(ADVISOR_PARTIAL_TRANSITION_CODE_KEY) or "").strip()
        if code not in CANONICAL_STOP_REASON_CODES:
            code = "unresolved_construction"
        try:
            revision = int(artifact.get("state_revision"))
        except (TypeError, ValueError):
            revision = -1
        candidates.append(
            (
                revision,
                str(artifact.get("artifact_id") or ""),
                {
                    "artifact_id": str(artifact.get("artifact_id") or ""),
                    "stop_reason_code": code,
                    "reason": str(metadata.get(ADVISOR_PARTIAL_TRANSITION_REASON_KEY) or ""),
                },
            )
        )
    if not candidates:
        return {}
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def classify_stop_reason(state: Mapping[str, Any]) -> str:
    """Best canonical explanation for why the full theorem was not reached."""
    root = next(
        (row for row in state.get("claims", []) if str(row.get("claim_id") or "") == "root"),
        {},
    )
    if str(root.get("validation_status") or "") == "refuted":
        return "refuted_statement"
    active_blocking = [
        row for row in state.get("debts", [])
        if str(row.get("status") or "") == "active" and str(row.get("severity") or "") == "blocking"
    ]
    for debt in active_blocking:
        text = f"{debt.get('debt_type', '')} {debt.get('obligation', '')}".lower()
        if any(cue in text for cue in ("missing_reference", "missing reference", "citation", "published theorem", "known theorem", "literature")):
            return "missing_external_theorem"
    for debt in active_blocking:
        text = f"{debt.get('debt_type', '')} {debt.get('obligation', '')}".lower()
        if "construction" in text or "construct" in text:
            return "unresolved_construction"
    routes = list(state.get("routes", []))
    if routes and all(str(row.get("status") or "") in {"blocked", "abandoned", "superseded"} for row in routes):
        return "failed_route_family"
    return "unresolved_construction"


def evaluate_partial_stop(
    state: Mapping[str, Any],
    *,
    verifier_ready_routes: Optional[List[Mapping[str, Any]]] = None,
    budget_allowed: bool = True,
    proposed_reason: str = "",
) -> Dict[str, Any]:
    """Decide whether a stop_with_partial_results action is allowed right now.

    Returns {"allow", "stop_reason_code", "policy", "blockers"/"progress_signals"}.
    Under full_proof_first the stop is blocked while progress signals exist,
    unless the token budget is exhausted, an operator stop was requested, or
    the advisor recorded an explicit partial-mode transition justification.
    """
    policy = completion_policy_for_state(state)
    problem = state.get("problem_state") if isinstance(state.get("problem_state"), Mapping) else {}
    decision: Dict[str, Any] = {"policy": policy, "proposed_reason": proposed_reason}
    if policy in {"partial_ok", "exploratory"}:
        decision.update({"allow": True, "stop_reason_code": "user_partial_mode"})
        return decision
    run_status = str((problem or {}).get("run_status") or "running")
    if run_status in {"stopping", "stopped"}:
        decision.update(
            {
                "allow": True,
                "stop_reason_code": "operator_stop",
                "note": "operator stop requested; the completion policy does not override a hard stop",
            }
        )
        return decision
    remaining = _int_or_none((problem or {}).get("remaining_token_budget"))
    if not budget_allowed or (remaining is not None and remaining <= 0):
        decision.update({"allow": True, "stop_reason_code": "exhausted_budget"})
        return decision
    transition = advisor_partial_transition(state)
    if transition:
        decision.update(
            {
                "allow": True,
                "stop_reason_code": transition["stop_reason_code"],
                "advisor_partial_transition": transition,
            }
        )
        return decision
    signals = partial_stop_progress_signals(state, verifier_ready_routes=verifier_ready_routes)
    if signals["any"]:
        decision.update(
            {
                "allow": False,
                "stop_reason_code": "",
                "progress_signals": signals,
                "note": (
                    "full_proof_first blocks stop_with_partial_results while productive proof work "
                    "remains; continue exploiting the recorded progress signals"
                ),
            }
        )
        return decision
    decision.update({"allow": True, "stop_reason_code": classify_stop_reason(state)})
    return decision


def _active_plausible_route_ids(state: Mapping[str, Any]) -> List[str]:
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    plausible_route_ids: List[str] = []
    inference_status_by_route: Dict[str, List[str]] = {}
    for inference in state.get("inferences", []):
        inference_status_by_route.setdefault(str(inference.get("route_id") or ""), []).append(
            str(inference.get("validation_status") or "")
        )
    for route in state.get("routes", []):
        if str(route.get("status") or "") != "active":
            continue
        route_id = str(route.get("route_id") or "")
        conclusion = claims.get(str(route.get("conclusion_claim_id") or ""), {})
        statuses = inference_status_by_route.get(route_id, [])
        if "plausible" in statuses or str(conclusion.get("validation_status") or "") == "plausible":
            plausible_route_ids.append(route_id)
    return plausible_route_ids


def _actionable_narrowed_blockers(state: Mapping[str, Any]) -> List[str]:
    """Active blockers that are narrowed enough to act on: they name a next
    target or ask for a precise source/computation step."""
    claim_ids = {str(row.get("claim_id") or "") for row in state.get("claims", [])}
    route_ids = {str(row.get("route_id") or "") for row in state.get("routes", [])}
    actionable: List[str] = []
    for debt in state.get("debts", []):
        if str(debt.get("status") or "") != "active":
            continue
        if str(debt.get("severity") or "") not in {"blocking", "major"}:
            continue
        suggested = str(debt.get("suggested_next_target") or "")
        text = f"{debt.get('debt_type', '')} {debt.get('obligation', '')}".lower()
        if (suggested and (suggested in claim_ids or suggested in route_ids)) or any(
            cue in text
            for cue in (
                "missing_reference",
                "missing_hypothesis",
                "citation",
                "bounded computation",
                "narrowed",
                "bottleneck",
            )
        ):
            actionable.append(str(debt.get("debt_id") or ""))
    return actionable


def _productive_branch_ids(state: Mapping[str, Any]) -> List[str]:
    try:
        summaries = build_branch_summaries(None, state=state)  # type: ignore[arg-type]
    except Exception:
        return []
    return [
        str(summary.get("branch") or "")
        for summary in summaries
        if str(summary.get("status") or "") == "keep_exploiting"
    ]


def _untried_high_score_route_ids(state: Mapping[str, Any]) -> List[str]:
    untried: List[str] = []
    for row in route_scoreboard(state):
        if str(row.get("scoreboard_status") or "") in {"blocked", "stalled", "low_yield", "abandoned", "superseded"}:
            continue
        if int(row.get("inference_count") or 0) > 0:
            continue
        if float(row.get("score") or 0.0) >= _UNTRIED_HIGH_SCORE_MIN:
            untried.append(str(row.get("route_id") or ""))
    return untried


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
