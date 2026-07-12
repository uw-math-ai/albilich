from __future__ import annotations

"""Compact per-route branch summaries and workbenches (2026-07-09 TODOs 1+4).

Branch definition (update-advice open question 1, decided 2026-07-10): a
*branch* is a route-anchored cluster. ``branch_id`` IS the ``route_id`` of the
anchor route; the cluster is that route's conclusion claim, the claims tied to
it through the route's inferences (premises and conditions), the active debts
owned by those claims or the route, and the branch-relevant sources/artifacts.
This keeps branch identity stable across sessions (routes are persisted rows)
while still meaning "one mathematical proof direction" rather than one claim.

``build_branch_summary`` produces exactly the update-advice format:

    Branch / Goal / Status / Verified facts / Candidate facts /
    Active blockers / Failed methods / Useful sources / Next recommended lemma

``build_branch_workbench`` (TODO 1) extends the summary into the full branch
workbench: similar lemmas worth trying next, failed methods that must not be
retried unchanged (from the negative-result ledger artifacts), the last useful
mathematical delta plus the stale pass count since it, and the explicit
stop/merge/rotate condition. Workbenches are persisted as small
``branch_workbench`` JSON artifacts (producer ``scheduler``) by
``sync_branch_workbenches`` — updated idempotently like the writing lint-debt
sync — so they survive across sessions and are visible in manifests.

Status heuristic (deliberately simple and documented; a fresh advisor branch
adjudication — see ``advisor_branch_directive`` — always overrides it):

1. ``pause_or_merge`` — the route is paused on the scoreboard (blocked,
   stalled, low_yield, abandoned, superseded), or a blocking debt has repeated
   3+ times with no verified inference on the route: stuck and repeating.
2. ``needs_source`` — otherwise, the highest-priority active blocker asks for
   a missing theorem, citation, or literature (by debt_type or obligation
   wording): the branch is waiting on the librarian.
3. ``needs_cas`` — otherwise, the highest-priority active blocker asks for a
   bounded computation, enumeration, or example search: the branch is waiting
   on a CAS experiment.
4. ``keep_exploiting`` — default: recent inference/debt activity is ordinary
   mathematical work; keep proving nearby lemmas on this branch.

Blockers are scanned in severity order (blocking first, then most-repeated),
and the first source/CAS hint wins, so one noisy minor debt cannot flip the
branch directive.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .graph_policy import route_scoreboard
from .memory_policy import FAILED_ARTIFACT_TYPES, VERIFIED_VALIDATION_STATUSES, claim_memory_status
from .models import json_dumps, json_loads, normalize_text, sha256_text, utc_now
from .store import ProofStateStore

BRANCH_STATUSES = {"keep_exploiting", "needs_source", "needs_cas", "pause_or_merge"}
PAUSED_SCOREBOARD_STATUSES = {"blocked", "stalled", "low_yield", "abandoned", "superseded"}

# --- Branch persistence policy constants (TODO 1) -------------------------
# Rotate away from a branch only on: the same failure fingerprint repeating,
# no useful mathematical delta for this many branch passes, or an explicit
# advisor pause_or_merge adjudication.
BRANCH_STALE_PASS_LIMIT = 3
BRANCH_FAILURE_REPEAT_LIMIT = 2
# Advisor branch adjudication contract (TODO 1.3): the PhD advisor attaches
# metadata.branch_states = {<branch_id>: {"state": <one of BRANCH_STATUSES>,
# "reason": ...}} (a bare state string is also accepted) on an advisor_report.
# A directive is honored while fresh (within the revision TTL) and overrides
# the branch-status heuristic and the rotation heuristic in both directions.
BRANCH_STATES_METADATA_KEY = "branch_states"
BRANCH_DIRECTIVE_TTL_REVISIONS = 48
BRANCH_WORKBENCH_ARTIFACT_TYPE = "branch_workbench"
# Delta kinds strong enough to call a blocked branch "stuck but productive"
# (verified mathematics or a clean, reusable negative result), as opposed to
# architecture churn that merely reshapes the route.
STRONG_DELTA_KINDS = {
    "verified_inference",
    "verified_claim",
    "debt_resolved",
    "debt_narrowed",
    "usable_source",
    "clean_obstruction",
}
RESEARCH_PASS_MODES = {"prove", "reduce", "weaken", "strengthen", "refute"}

# Single-word hints match whole tokens of the normalized obligation; phrase
# hints match normalized substrings (so "case" never matches "cas").
SOURCE_HINT_TOKENS = {
    "literature",
    "citation",
    "citations",
    "cite",
    "source",
    "sources",
    "reference",
    "references",
    "retrieval",
    "librarian",
    "bibliography",
}
SOURCE_HINT_PHRASES = ("known theorem", "look up")
CAS_HINT_TOKENS = {
    "cas",
    "computation",
    "computational",
    "compute",
    "computed",
    "macaulay",
    "macaulay2",
    "sagemath",
    "julia",
    "numerical",
    "numerically",
    "enumerate",
    "enumeration",
}
CAS_HINT_PHRASES = ("example search", "counterexample search", "bounded computation")

_FACT_CHARS = 180
_ITEM_LIMIT = 4
_SOURCE_LIMIT = 3
_STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "by", "for", "from", "has",
    "if", "in", "is", "it", "its", "let", "not", "of", "on", "or", "over", "such",
    "that", "the", "then", "there", "this", "to", "we", "which", "with",
}


def build_branch_summary(
    store: ProofStateStore,
    route_id: str,
    *,
    state: Optional[Mapping[str, Any]] = None,
    fact_graph: Optional[Any] = None,
) -> Dict[str, Any]:
    """Summarize one proof branch (route) in the update-advice format."""
    state = state if state is not None else store.get_state()
    route = next(
        (row for row in state.get("routes", []) if str(row.get("route_id") or "") == route_id),
        None,
    )
    if route is None:
        raise ValueError(f"unknown route: {route_id}")
    claims_by_id = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    inferences = [
        row for row in state.get("inferences", [])
        if str(row.get("route_id") or "") == route_id
    ]

    conclusion_id = str(route.get("conclusion_claim_id") or "")
    branch_claim_ids = branch_cluster_claim_ids(state, route_id)

    # Fact-graph pilot (2026-07-09 TODO 3, first use): the verified/candidate
    # fact lists come from the generated read-only fact_graph view. The
    # classification boundary is identical by construction — both the graph
    # and the old direct query classify through claim_memory_status — and the
    # graph keeps the cluster (branch_cluster_claim_ids) order.
    from .fact_graph import build_fact_graph  # local import: fact_graph builds on this module

    graph = fact_graph if fact_graph is not None else build_fact_graph(store, state=state)
    verified_facts = [
        f"{fact.source_id}: {_clip(fact.statement)}"
        for fact in graph.facts_for_branch(route_id, verified_only=True)
    ]
    candidate_facts = [
        f"{fact.source_id}: {_clip(fact.statement)}"
        for fact in graph.facts_for_branch(route_id, verified_only=False)
        if fact.memory_status == "candidate"
    ]
    failed_methods: List[str] = []
    for claim_id in branch_claim_ids:
        claim = claims_by_id[claim_id]
        if claim_memory_status(claim) == "failed":
            failed_methods.append(f"refuted/abandoned {claim_id}: {_clip(claim.get('statement'))}")

    blockers = _active_branch_debts(state, route_id, branch_claim_ids)
    active_blockers = [
        f"{debt.get('debt_id')} ({debt.get('severity')}): {_clip(debt.get('obligation'))}"
        for debt in blockers[:_ITEM_LIMIT]
    ]

    if str(route.get("failure_fingerprint") or ""):
        failed_methods.append(
            f"route {route_id} carries failure fingerprint {route.get('failure_fingerprint')}"
        )
    failed_methods.extend(_failed_method_artifacts(state, route_id))

    goal = _clip(
        claims_by_id.get(conclusion_id, {}).get("statement")
        or route.get("strategy")
        or route.get("label"),
        max_chars=260,
    )
    verified_inference_count = sum(
        1
        for inference in inferences
        if str(inference.get("validation_status") or "") in {"informally_verified", "formally_verified"}
    )
    status = _branch_status(
        state,
        route_id=route_id,
        blockers=blockers,
        verified_inference_count=verified_inference_count,
    )

    return {
        "branch": route_id,
        "goal": goal,
        "status": status,
        "verified_facts": verified_facts[:_ITEM_LIMIT],
        "candidate_facts": candidate_facts[:_ITEM_LIMIT],
        "active_blockers": active_blockers,
        "failed_methods": failed_methods[:_ITEM_LIMIT],
        "useful_sources": _useful_sources(state, goal),
        "next_recommended_lemma": _next_recommended_lemma(
            claims_by_id, blockers, candidate_facts, goal
        ),
    }


def build_branch_summaries(
    store: ProofStateStore,
    *,
    limit: int = 4,
    state: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Summaries for the top ``limit`` routes by scoreboard score."""
    state = state if state is not None else store.get_state()
    from .fact_graph import build_fact_graph  # local import: fact_graph builds on this module

    graph = build_fact_graph(store, state=state)
    summaries: List[Dict[str, Any]] = []
    for row in route_scoreboard(state, limit=limit):
        route_id = str(row.get("route_id") or "")
        if not route_id:
            continue
        summaries.append(build_branch_summary(store, route_id, state=state, fact_graph=graph))
    return summaries


def render_branch_summary(summary: Mapping[str, Any]) -> str:
    """Render one summary in the update-advice text block format."""
    lines = [
        f"Branch: {summary.get('branch', '')}",
        f"Goal: {summary.get('goal', '')}",
        f"Status: {summary.get('status', '')}",
        f"Verified facts: {_render_items(summary.get('verified_facts'))}",
        f"Candidate facts: {_render_items(summary.get('candidate_facts'))}",
        f"Active blockers: {_render_items(summary.get('active_blockers'))}",
        f"Failed methods: {_render_items(summary.get('failed_methods'))}",
        f"Useful sources: {_render_items(summary.get('useful_sources'))}",
        f"Next recommended lemma: {summary.get('next_recommended_lemma', '')}",
    ]
    return "\n".join(lines)


def _render_items(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "none recorded"
    return "; ".join(str(item) for item in items)


def _clip(value: Any, *, max_chars: int = _FACT_CHARS) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _active_branch_debts(
    state: Mapping[str, Any],
    route_id: str,
    branch_claim_ids: List[str],
) -> List[Mapping[str, Any]]:
    owners = set(branch_claim_ids) | {route_id}
    rows = [
        row for row in state.get("debts", [])
        if str(row.get("status") or "") == "active"
        and (
            str(row.get("owner_id") or "") in owners
            or str(row.get("suggested_next_target") or "") in owners
        )
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("severity") or "") != "blocking",
            -int(row.get("repeated_count") or 0),
            str(row.get("debt_id") or ""),
        )
    )
    return rows


def _failed_method_artifacts(state: Mapping[str, Any], route_id: str) -> List[str]:
    lines: List[str] = []
    for artifact in state.get("artifacts", []):
        if str(artifact.get("artifact_type") or "") not in FAILED_ARTIFACT_TYPES:
            continue
        metadata = json_loads(artifact.get("metadata_json"), {})
        if not isinstance(metadata, Mapping):
            continue
        linked = {str(metadata.get(key) or "") for key in ("route_id", "blocking_route_id")}
        for value in metadata.get("route_ids") or []:
            linked.add(str(value))
        if route_id in linked:
            lines.append(
                f"{artifact.get('artifact_id')} ({artifact.get('artifact_type')}): "
                f"{_clip(artifact.get('content_summary'))}"
            )
    return lines


def branch_cluster_claim_ids(state: Mapping[str, Any], route_id: str) -> List[str]:
    """Claims in the route-anchored branch cluster (branch definition above):
    the route's conclusion plus every claim tied in through its inferences."""
    claims_by_id = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    route = next(
        (row for row in state.get("routes", []) if str(row.get("route_id") or "") == route_id),
        None,
    )
    branch_claim_ids: List[str] = []

    def add_claim(claim_id: Any) -> None:
        text = str(claim_id or "")
        if text and text in claims_by_id and text not in branch_claim_ids:
            branch_claim_ids.append(text)

    if route is not None:
        add_claim(route.get("conclusion_claim_id"))
    for inference in state.get("inferences", []):
        if str(inference.get("route_id") or "") != route_id:
            continue
        add_claim(inference.get("conclusion_claim_id"))
        for premise_id in inference.get("premise_claim_ids", []) or json_loads(inference.get("premise_claim_ids_json")):
            add_claim(premise_id)
        for condition_id in json_loads(inference.get("condition_claim_ids_json")):
            add_claim(condition_id)
    return branch_claim_ids


def _branch_status(
    state: Mapping[str, Any],
    *,
    route_id: str,
    blockers: List[Mapping[str, Any]],
    verified_inference_count: int,
) -> str:
    directive = advisor_branch_directive(state, route_id)
    if directive:
        return str(directive["state"])
    scoreboard_status = next(
        (
            str(row.get("scoreboard_status") or "")
            for row in route_scoreboard(state)
            if str(row.get("route_id") or "") == route_id
        ),
        "",
    )
    repeated = max((int(row.get("repeated_count") or 0) for row in blockers), default=0)
    if scoreboard_status in PAUSED_SCOREBOARD_STATUSES:
        return "pause_or_merge"
    if repeated >= 3 and verified_inference_count == 0:
        return "pause_or_merge"
    for debt in blockers:
        hint = _debt_directive_hint(debt)
        if hint:
            return hint
    return "keep_exploiting"


def _debt_directive_hint(debt: Mapping[str, Any]) -> str:
    debt_type = str(debt.get("debt_type") or "").lower()
    normalized = normalize_text(str(debt.get("obligation") or ""))
    tokens = set(normalized.split())
    if any(term in debt_type for term in ("citation", "missing_theorem", "literature", "source")):
        return "needs_source"
    if any(term in debt_type.split("_") for term in ("cas",)) or "computation" in debt_type:
        return "needs_cas"
    if tokens & SOURCE_HINT_TOKENS or any(phrase in normalized for phrase in SOURCE_HINT_PHRASES):
        return "needs_source"
    if tokens & CAS_HINT_TOKENS or any(phrase in normalized for phrase in CAS_HINT_PHRASES):
        return "needs_cas"
    return ""


def _keywords(text: str) -> set[str]:
    return {
        token
        for token in normalize_text(text).split()
        if len(token) > 2 and token not in _STOPWORDS
    }


def _useful_sources(state: Mapping[str, Any], goal: str) -> List[str]:
    goal_keywords = _keywords(goal)
    scored: List[tuple[int, str, str]] = []
    for card in state.get("retrieval_cards", []):
        statement = str(card.get("exact_statement") or "")
        overlap = len(goal_keywords & _keywords(statement))
        if overlap:
            scored.append((-overlap, str(card.get("card_id") or ""), f"{card.get('card_id')}: {_clip(statement)}"))
    for entry in state.get("theorem_library_entries", []):
        statement = str(entry.get("statement") or "")
        overlap = len(goal_keywords & _keywords(statement))
        if overlap:
            scored.append((-overlap, str(entry.get("entry_id") or ""), f"{entry.get('entry_id')}: {_clip(statement)}"))
    scored.sort()
    return [line for _, _, line in scored[:_SOURCE_LIMIT]]


def _next_recommended_lemma(
    claims_by_id: Mapping[str, Mapping[str, Any]],
    blockers: List[Mapping[str, Any]],
    candidate_facts: List[str],
    goal: str,
) -> str:
    for debt in blockers:
        suggested = str(debt.get("suggested_next_target") or "")
        claim = claims_by_id.get(suggested)
        if claim is not None:
            return f"prove {suggested}: {_clip(claim.get('statement'))}"
    if blockers:
        first = blockers[0]
        return f"discharge {first.get('debt_id')}: {_clip(first.get('obligation'))}"
    if candidate_facts:
        return f"verify candidate {candidate_facts[0]}"
    return f"extend the verified chain toward the branch goal: {goal}"


# ---------------------------------------------------------------------------
# Advisor branch adjudication (TODO 1.3)
# ---------------------------------------------------------------------------


def advisor_branch_directive(state: Mapping[str, Any], route_id: str) -> Optional[Dict[str, Any]]:
    """Newest fresh advisor adjudication for one branch, or None.

    Contract: the PhD advisor sets ``metadata.branch_states`` on an
    advisor_report to a mapping ``{branch_id: {"state": keep_exploiting |
    needs_source | needs_cas | pause_or_merge, "reason": ...}}`` (a bare state
    string is accepted too). A directive is fresh while the proof state is
    within ``BRANCH_DIRECTIVE_TTL_REVISIONS`` revisions of the report; the
    scheduler honors a fresh directive over its own heuristics.
    """
    rows = state.get("research_artifacts")
    if not isinstance(rows, list):
        rows = [row for row in state.get("artifacts", []) if isinstance(row, Mapping)]
    candidates: List[tuple[int, str, str, str]] = []
    for artifact in rows:
        if str(artifact.get("artifact_type") or "") != "advisor_report":
            continue
        if str(artifact.get("producer_role") or "") not in {"phd_advisor", "advisor"}:
            continue
        metadata = artifact.get("metadata_json", artifact.get("metadata", {}))
        if isinstance(metadata, str):
            metadata = json_loads(metadata, {})
        if not isinstance(metadata, Mapping):
            continue
        branch_states = metadata.get(BRANCH_STATES_METADATA_KEY)
        if not isinstance(branch_states, Mapping):
            continue
        entry = branch_states.get(route_id)
        if entry is None:
            continue
        if isinstance(entry, Mapping):
            branch_state = str(entry.get("state") or entry.get("status") or "").strip().lower()
            reason = str(entry.get("reason") or "").strip()
        else:
            branch_state = str(entry or "").strip().lower()
            reason = ""
        if branch_state not in BRANCH_STATUSES:
            continue
        try:
            revision = int(artifact.get("state_revision"))
        except (TypeError, ValueError):
            revision = -1
        candidates.append((revision, str(artifact.get("artifact_id") or ""), branch_state, reason))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    revision, artifact_id, branch_state, reason = candidates[0]
    problem = state.get("problem_state") if isinstance(state.get("problem_state"), Mapping) else {}
    try:
        current_revision = int((problem or {}).get("current_revision"))
    except (TypeError, ValueError):
        current_revision = -1
    if current_revision >= 0 and revision >= 0 and current_revision - revision > BRANCH_DIRECTIVE_TTL_REVISIONS:
        return None
    return {
        "state": branch_state,
        "reason": reason,
        "artifact_id": artifact_id,
        "state_revision": revision,
    }


# ---------------------------------------------------------------------------
# Useful mathematical delta + branch rotation decision (TODO 1.2)
# ---------------------------------------------------------------------------


def branch_useful_delta(
    state: Mapping[str, Any],
    route_id: str,
    *,
    branch_claim_ids: Optional[List[str]] = None,
    goal: str = "",
) -> Dict[str, Any]:
    """The newest useful mathematical delta on the branch, or {}.

    "Useful delta" (from the persisted proof-state history): a verified
    inference or verified branch claim, a resolved or narrowed branch debt, a
    usable retrieval card matching the branch goal, a clean recorded
    obstruction, or improved local architecture (a new route inference or a
    new branch claim, which is also what raises the route score).
    """
    claim_ids = branch_claim_ids if branch_claim_ids is not None else branch_cluster_claim_ids(state, route_id)
    claim_id_set = set(claim_ids)
    owners = claim_id_set | {route_id}
    deltas: List[tuple[str, str, str, int]] = []  # (at, kind, detail, strength)

    def add(at: Any, kind: str, detail: str) -> None:
        stamp = str(at or "")
        if stamp:
            deltas.append((stamp, kind, detail, int(kind in STRONG_DELTA_KINDS)))

    claims_by_id = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    for inference in state.get("inferences", []):
        if str(inference.get("route_id") or "") != route_id:
            continue
        inference_id = str(inference.get("inference_id") or "")
        if str(inference.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES:
            add(
                inference.get("updated_at") or inference.get("created_at"),
                "verified_inference",
                f"inference {inference_id} verified",
            )
        add(inference.get("created_at"), "architecture_improved", f"inference {inference_id} added")
    for claim_id in claim_ids:
        claim = claims_by_id.get(claim_id) or {}
        if claim_id != "root":
            add(claim.get("created_at"), "architecture_improved", f"claim {claim_id} added")
        if str(claim.get("validation_status") or "") in VERIFIED_VALIDATION_STATUSES:
            add(claim.get("updated_at") or claim.get("created_at"), "verified_claim", f"claim {claim_id} verified")
    for debt in state.get("debts", []):
        if str(debt.get("owner_id") or "") not in owners and str(debt.get("suggested_next_target") or "") not in owners:
            continue
        debt_id = str(debt.get("debt_id") or "")
        status = str(debt.get("status") or "")
        if status in {"resolved", "discarded"}:
            add(debt.get("last_seen"), "debt_resolved", f"debt {debt_id} {status}")
            continue
        evidence = debt.get("resolution_evidence") or debt.get("resolution_evidence_json")
        if isinstance(evidence, str):
            evidence = json_loads(evidence, {})
        if isinstance(evidence, Mapping) and evidence:
            add(debt.get("last_seen"), "debt_narrowed", f"debt {debt_id} narrowed (resolution evidence recorded)")
    goal_keywords = _keywords(goal)
    if goal_keywords:
        for card in state.get("retrieval_cards", []):
            statement = str(card.get("exact_statement") or "")
            if goal_keywords & _keywords(statement):
                add(card.get("retrieved_at"), "usable_source", f"retrieval card {card.get('card_id')} matches the branch goal")
    for artifact in _branch_linked_artifacts(state, route_id, claim_id_set):
        if str(artifact.get("artifact_type") or "") in FAILED_ARTIFACT_TYPES:
            add(
                artifact.get("created_at"),
                "clean_obstruction",
                f"{artifact.get('artifact_type')} {artifact.get('artifact_id')} recorded",
            )
    if not deltas:
        return {}
    # Newest first; a strong delta wins a timestamp tie.
    deltas.sort(key=lambda item: (item[0], item[3]), reverse=True)
    at, kind, detail, strength = deltas[0]
    strong = next((item for item in deltas if item[3]), None)
    result = {"at": at, "kind": kind, "detail": detail, "strong": bool(strength)}
    if strong is not None:
        result["last_strong_delta"] = {"at": strong[0], "kind": strong[1], "detail": strong[2]}
    return result


def _branch_linked_artifacts(
    state: Mapping[str, Any],
    route_id: str,
    claim_id_set: set[str],
) -> List[Mapping[str, Any]]:
    rows = state.get("research_artifacts")
    if not isinstance(rows, list):
        rows = [row for row in state.get("artifacts", []) if isinstance(row, Mapping)]
    linked: List[Mapping[str, Any]] = []
    for artifact in rows:
        metadata = artifact.get("metadata_json", artifact.get("metadata", {}))
        if isinstance(metadata, str):
            metadata = json_loads(metadata, {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        route_links = {str(metadata.get(key) or "") for key in ("route_id", "blocking_route_id")}
        for value in metadata.get("route_ids") or []:
            route_links.add(str(value))
        target = str(metadata.get("target_id") or metadata.get("claim_id") or "")
        if route_id in route_links or (target and target in claim_id_set):
            linked.append(artifact)
    return linked


def _branch_pass_rows(state: Mapping[str, Any], route_id: str, claim_id_set: set[str]) -> List[Mapping[str, Any]]:
    """Researcher/villain passes on this branch, newest first."""
    rows = state.get("recent_runs")
    if not isinstance(rows, list):
        rows = [row for row in state.get("runs", []) if isinstance(row, Mapping) and row.get("created_at")]
        rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    passes: List[Mapping[str, Any]] = []
    for run in rows:
        if str(run.get("mode") or "") not in RESEARCH_PASS_MODES:
            continue
        run_route = str(run.get("route_id") or "")
        run_target = str(run.get("target_id") or "")
        if run_route == route_id or run_target in claim_id_set:
            passes.append(run)
    return passes


def _repeated_failure_fingerprint(
    state: Mapping[str, Any],
    route: Mapping[str, Any],
    claim_id_set: set[str],
) -> str:
    """A failure fingerprint recorded BRANCH_FAILURE_REPEAT_LIMIT+ times on the
    branch (route row + negative-result artifacts), else ''. Fingerprint match
    is the "stuck and repeating" signal: the same failure, not a new one."""
    route_id = str(route.get("route_id") or "")
    counts: Dict[str, int] = {}
    route_fingerprint = str(route.get("failure_fingerprint") or "").strip()
    if route_fingerprint:
        counts[route_fingerprint] = counts.get(route_fingerprint, 0) + 1
    for artifact in _branch_linked_artifacts(state, route_id, claim_id_set):
        if str(artifact.get("artifact_type") or "") not in FAILED_ARTIFACT_TYPES:
            continue
        metadata = artifact.get("metadata_json", artifact.get("metadata", {}))
        if isinstance(metadata, str):
            metadata = json_loads(metadata, {})
        if not isinstance(metadata, Mapping):
            continue
        fingerprint = str(metadata.get("failure_fingerprint") or metadata.get("obstruction_type") or "").strip()
        if fingerprint:
            counts[fingerprint] = counts.get(fingerprint, 0) + 1
    repeated = [fp for fp, count in counts.items() if count >= BRANCH_FAILURE_REPEAT_LIMIT]
    return sorted(repeated)[0] if repeated else ""


def branch_rotation_decision(
    state: Mapping[str, Any],
    route_id: str,
    *,
    stale_pass_limit: int = BRANCH_STALE_PASS_LIMIT,
) -> Dict[str, Any]:
    """Continue-or-rotate decision for one branch (TODO 1.2).

    Continue while the last few passes produced a useful delta (verified
    lemma, narrowed/resolved debt, usable source, clean obstruction, improved
    architecture). Rotate only on: repeated same-failure fingerprint, no
    useful delta for ``stale_pass_limit`` passes, or an advisor
    pause_or_merge adjudication. A fresh advisor directive overrides the
    heuristic in both directions.

    ``classification`` distinguishes "stuck_but_productive" (verified new
    mathematics but the main target is still blocked — keep exploiting with
    nearby lemmas) from "stuck_and_repeating" (same failure fingerprint again)
    and "stale" (no useful delta for several passes).
    """
    route = next(
        (row for row in state.get("routes", []) if str(row.get("route_id") or "") == route_id),
        None,
    )
    if route is None:
        return {"branch": route_id, "continue_branch": False, "action": "rotate", "classification": "missing", "reason": f"unknown route {route_id}"}
    claim_ids = branch_cluster_claim_ids(state, route_id)
    claim_id_set = set(claim_ids)
    conclusion_id = str(route.get("conclusion_claim_id") or "")
    claims_by_id = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    conclusion = claims_by_id.get(conclusion_id) or {}
    goal = _clip(conclusion.get("statement") or route.get("strategy") or route.get("label"), max_chars=260)

    blockers = _active_branch_debts(state, route_id, claim_ids)
    main_target_blocked = (
        str(conclusion.get("validation_status") or "") not in VERIFIED_VALIDATION_STATUSES
        and (
            str(conclusion.get("validation_status") or "") == "challenged"
            or any(
                str(debt.get("severity") or "") == "blocking"
                and str(debt.get("owner_id") or "") in {route_id, conclusion_id}
                for debt in blockers
            )
        )
    )
    delta = branch_useful_delta(state, route_id, branch_claim_ids=claim_ids, goal=goal)
    passes = _branch_pass_rows(state, route_id, claim_id_set)
    since = str(delta.get("at") or "")
    passes_since = sum(1 for run in passes if str(run.get("created_at") or "") > since) if since else len(passes)
    has_strong_delta = bool(delta.get("strong") or delta.get("last_strong_delta"))

    decision: Dict[str, Any] = {
        "branch": route_id,
        "target_id": conclusion_id,
        "useful_delta": delta,
        "passes_since_useful_delta": passes_since,
        "main_target_blocked": main_target_blocked,
        "repeated_failure_fingerprint": "",
        "advisor_state": "",
    }

    directive = advisor_branch_directive(state, route_id)
    if directive:
        decision["advisor_state"] = directive["state"]
        decision["advisor_directive"] = directive
        if directive["state"] == "pause_or_merge":
            decision.update(
                action="rotate",
                continue_branch=False,
                classification="exhausted",
                reason=directive.get("reason") or "advisor adjudicated this branch pause_or_merge",
            )
        else:
            decision.update(
                action="continue",
                continue_branch=True,
                classification="stuck_but_productive" if main_target_blocked else "productive",
                reason=directive.get("reason") or f"advisor adjudicated this branch {directive['state']}",
            )
        return decision

    repeated_fingerprint = _repeated_failure_fingerprint(state, route, claim_id_set)
    if repeated_fingerprint:
        decision.update(
            action="rotate",
            continue_branch=False,
            classification="stuck_and_repeating",
            repeated_failure_fingerprint=repeated_fingerprint,
            reason=(
                f"the same failure fingerprint '{repeated_fingerprint}' has been recorded "
                f"{BRANCH_FAILURE_REPEAT_LIMIT}+ times on this branch"
            ),
        )
        return decision

    if (delta and passes_since >= stale_pass_limit) or (not delta and len(passes) >= stale_pass_limit):
        decision.update(
            action="rotate",
            continue_branch=False,
            classification="stale",
            reason=f"no useful mathematical delta in the last {stale_pass_limit} branch passes",
        )
        return decision

    classification = "productive"
    if main_target_blocked and has_strong_delta:
        classification = "stuck_but_productive"
    decision.update(
        action="continue",
        continue_branch=True,
        classification=classification,
        reason=(
            f"recent branch passes produced a useful delta ({delta.get('kind')}: {delta.get('detail')})"
            if delta
            else "young branch: give it its first research passes before judging"
        ),
    )
    return decision


# ---------------------------------------------------------------------------
# Branch workbench (TODO 1.1)
# ---------------------------------------------------------------------------


def build_branch_workbench(
    store: Optional[ProofStateStore],
    route_id: str,
    *,
    state: Optional[Mapping[str, Any]] = None,
    fact_graph: Optional[Any] = None,
) -> Dict[str, Any]:
    """The full branch workbench: summary + persistence fields (TODO 1)."""
    if state is None:
        if store is None:
            raise ValueError("build_branch_workbench needs a store or a state snapshot")
        state = store.get_state()
    summary = build_branch_summary(store, route_id, state=state, fact_graph=fact_graph)
    decision = branch_rotation_decision(state, route_id)
    claim_ids = branch_cluster_claim_ids(state, route_id)
    claims_by_id = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    blockers = _active_branch_debts(state, route_id, claim_ids)
    workbench: Dict[str, Any] = {"branch_id": route_id, **summary}
    workbench.update(
        {
            "route_id": route_id,
            "target_id": str(decision.get("target_id") or ""),
            "similar_lemmas": _similar_lemmas(claims_by_id, claim_ids, blockers, str(summary.get("goal") or "")),
            "failed_methods_do_not_retry": _failed_methods_do_not_retry(state, route_id, set(claim_ids)),
            "last_useful_delta": decision.get("useful_delta") or {},
            "passes_since_useful_delta": int(decision.get("passes_since_useful_delta") or 0),
            "rotation_decision": {
                "action": decision.get("action"),
                "classification": decision.get("classification"),
                "reason": decision.get("reason"),
            },
            "advisor_state": str(decision.get("advisor_state") or ""),
            "stop_or_merge_condition": (
                f"rotate/pause this branch when the same failure fingerprint repeats {BRANCH_FAILURE_REPEAT_LIMIT}+ "
                f"times, when {BRANCH_STALE_PASS_LIMIT} branch passes produce no useful delta, or when the advisor "
                "adjudicates it pause_or_merge"
            ),
        }
    )
    return workbench


def build_branch_workbenches(
    store: Optional[ProofStateStore],
    *,
    limit: int = 5,
    state: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if state is None:
        if store is None:
            raise ValueError("build_branch_workbenches needs a store or a state snapshot")
        state = store.get_state()
    from .fact_graph import build_fact_graph  # local import: fact_graph builds on this module

    graph = build_fact_graph(store, state=state)
    workbenches: List[Dict[str, Any]] = []
    for row in route_scoreboard(state, limit=limit):
        route_id = str(row.get("route_id") or "")
        if not route_id:
            continue
        workbenches.append(build_branch_workbench(store, route_id, state=state, fact_graph=graph))
    return workbenches


def render_branch_workbench(workbench: Mapping[str, Any]) -> str:
    """Summary block plus the workbench persistence fields (report/advisor)."""
    delta = workbench.get("last_useful_delta") or {}
    rotation = workbench.get("rotation_decision") or {}
    delta_text = (
        f"{delta.get('kind')}: {delta.get('detail')} (at {delta.get('at')})" if delta else "none recorded"
    )
    lines = [
        render_branch_summary(workbench),
        f"Similar lemmas worth trying: {_render_items(workbench.get('similar_lemmas'))}",
        f"Failed methods (do not retry unchanged): {_render_items(workbench.get('failed_methods_do_not_retry'))}",
        f"Last useful delta: {delta_text}",
        f"Passes since useful delta: {workbench.get('passes_since_useful_delta', 0)}",
        f"Rotation: {rotation.get('action', '')} ({rotation.get('classification', '')}) — {rotation.get('reason', '')}",
        f"Advisor state: {workbench.get('advisor_state') or 'none'}",
        f"Stop/merge/rotate condition: {workbench.get('stop_or_merge_condition', '')}",
    ]
    return "\n".join(lines)


def _similar_lemmas(
    claims_by_id: Mapping[str, Mapping[str, Any]],
    branch_claim_ids: List[str],
    blockers: List[Mapping[str, Any]],
    goal: str,
) -> List[str]:
    """Nearby lemmas worth trying next: blocker targets, unverified branch
    claims, then generic analogue/special-case/bridge templates on the goal."""
    suggestions: List[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        if text and text not in seen and len(suggestions) < _ITEM_LIMIT:
            seen.add(text)
            suggestions.append(text)

    for debt in blockers:
        suggested = str(debt.get("suggested_next_target") or "")
        claim = claims_by_id.get(suggested)
        if claim is not None and str(claim.get("validation_status") or "") not in VERIFIED_VALIDATION_STATUSES:
            add(f"prove {suggested}: {_clip(claim.get('statement'))}")
    for claim_id in branch_claim_ids:
        claim = claims_by_id.get(claim_id) or {}
        if claim_memory_status(claim) == "candidate" and claim_id != "root":
            add(f"prove {claim_id}: {_clip(claim.get('statement'))}")
    add(f"prove a special case of the branch goal first: {goal}")
    add(f"prove a bridge lemma connecting the verified branch facts to: {goal}")
    return suggestions


def _failed_methods_do_not_retry(
    state: Mapping[str, Any],
    route_id: str,
    claim_id_set: set[str],
) -> List[str]:
    """Failed methods from the negative-result ledger artifacts on the branch:
    never retry these unchanged."""
    lines: List[str] = []
    for artifact in _branch_linked_artifacts(state, route_id, claim_id_set):
        if str(artifact.get("artifact_type") or "") not in FAILED_ARTIFACT_TYPES:
            continue
        metadata = artifact.get("metadata_json", artifact.get("metadata", {}))
        if isinstance(metadata, str):
            metadata = json_loads(metadata, {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        method = _clip(
            metadata.get("do_not_retry")
            or metadata.get("attempted_method")
            or metadata.get("failed_method")
            or metadata.get("ruled_out")
            or artifact.get("content_summary"),
            max_chars=160,
        )
        fingerprint = str(metadata.get("failure_fingerprint") or metadata.get("obstruction_type") or "")
        line = f"{artifact.get('artifact_id')}: {method}"
        if fingerprint:
            line += f" [fingerprint {fingerprint}]"
        lines.append(line)
        if len(lines) >= _ITEM_LIMIT:
            break
    return lines


# ---------------------------------------------------------------------------
# Workbench persistence (TODO 1.1): small JSON artifact per branch, producer
# scheduler, updated idempotently (no write when the content is unchanged).
# ---------------------------------------------------------------------------


def branch_workbench_artifact_id(route_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", route_id)
    return f"branch_workbench_{slug}"


def sync_branch_workbenches(
    store: ProofStateStore,
    *,
    limit: int = 5,
    state: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist one branch_workbench JSON artifact per active branch.

    Follows the deterministic-sync pattern (compute desired rows, diff against
    existing, no-op when unchanged). Rows are written directly by the
    scheduler (like store.record_interruption_artifact) because attach_artifact
    patches are append-only while a workbench must be updatable in place.
    """
    if state is None:
        state = store.get_state()
    workbenches = build_branch_workbenches(store, limit=limit, state=state)
    updated: List[str] = []
    unchanged: List[str] = []
    if not workbenches:
        return {"updated": updated, "unchanged": unchanged}
    artifact_dir = store.state_dir / "artifacts"
    with store.connect() as conn:
        revision = int(store.get_problem_row(conn)["current_revision"])
        for workbench in workbenches:
            route_id = str(workbench.get("branch_id") or "")
            artifact_id = branch_workbench_artifact_id(route_id)
            content = json.dumps(workbench, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            digest = sha256_text(content)
            existing = conn.execute(
                "SELECT sha256, created_at FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            if existing is not None and str(existing["sha256"]) == digest:
                unchanged.append(artifact_id)
                continue
            artifact_dir.mkdir(parents=True, exist_ok=True)
            path = artifact_dir / f"{artifact_id}.json"
            path.write_text(content, encoding="utf-8")
            now = utc_now()
            created_at = str(existing["created_at"]) if existing is not None else now
            summary = (
                f"Branch workbench for {route_id}: status={workbench.get('status')}, "
                f"next={workbench.get('next_recommended_lemma')}"
            )[:500]
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts(
                    artifact_id, artifact_type, path, sha256, producer_role, run_id,
                    state_revision, content_summary, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, 'scheduler', '', ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    BRANCH_WORKBENCH_ARTIFACT_TYPE,
                    str(path),
                    digest,
                    revision,
                    summary,
                    json_dumps(
                        {
                            "branch_id": route_id,
                            "route_id": route_id,
                            "target_id": str(workbench.get("target_id") or ""),
                            "status": str(workbench.get("status") or ""),
                            "updated_at": now,
                        }
                    ),
                    created_at,
                ),
            )
            updated.append(artifact_id)
        if updated:
            store.write_event(
                conn,
                revision,
                "branch_workbench_sync",
                {"updated": updated, "unchanged_count": len(unchanged)},
            )
        conn.commit()
    return {"updated": updated, "unchanged": unchanged}
