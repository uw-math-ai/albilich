from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from .models import fingerprint_text, json_loads, normalize_text

VERIFIED_VALIDATION_STATUSES = {"informally_verified", "formally_verified"}
UNRESOLVED_VALIDATION_STATUSES = {"untested", "plausible", "challenged"}
RETIRED_CLAIM_LIFECYCLES = {"superseded", "abandoned"}
DECOMPOSITION_MODES = {"reduce", "weaken", "strengthen"}
PROOF_WORK_MODES = {"prove", "integrate", "formalize", "validate_counterexample", "refute", "write"}
FAR_FROM_ROOT_DISTANCE = 5
PAUSED_ROUTE_STATUSES = {"low_yield", "stalled", "blocked", "abandoned", "superseded"}
FRONTIER_PRESSURE_CLAIM_CAP = 18
FRONTIER_PRESSURE_COMPRESSION_CAP = 30
BOOKKEEPING_TERMS = {
    "schema",
    "json",
    "validator",
    "serialization",
    "serialisation",
    "metadata",
    "manifest",
    "inventory",
    "bookkeeping",
}
CLAIM_SIGNATURE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "let",
    "no",
    "not",
    "of",
    "on",
    "or",
    "that",
    "the",
    "then",
    "there",
    "this",
    "to",
    "with",
    "whose",
    "while",
}
CLAIM_RESTATEMENT_NOVELTY_STOPWORDS = {
    "finite",
    "group",
    "have",
    "image",
    "let",
    "size",
    "sym",
    "then",
    "top",
}


def claim_parent_ids(row: Mapping[str, Any]) -> list[str]:
    value = row.get("parent_ids_json", row.get("parent_ids", []))
    parent_ids = json_loads(value) if isinstance(value, str) else value
    return [str(item) for item in parent_ids or [] if str(item)]


def claim_is_unresolved(row: Mapping[str, Any]) -> bool:
    return (
        row.get("lifecycle_status") == "active"
        and row.get("validation_status") in UNRESOLVED_VALIDATION_STATUSES
    )


def _compact_text(text: str, max_chars: int) -> str:
    one_line = " ".join(str(text or "").split())
    if len(one_line) <= max_chars:
        return one_line
    return one_line[: max(0, max_chars - 3)].rstrip() + "..."


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    loaded = json_loads(value, {})
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _json_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        invalid = object()
        loaded = json_loads(stripped, invalid)
        if isinstance(loaded, list):
            return [str(item).strip() for item in loaded if str(item).strip()]
        if isinstance(loaded, Mapping):
            return [str(item).strip() for item in loaded.values() if str(item).strip()]
        return [part.strip() for part in stripped.split(",") if part.strip()]
    if isinstance(value, Mapping):
        return [str(item).strip() for item in value.values() if str(item).strip()]
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _metadata_strings(metadata: Mapping[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        values.extend(_json_strings(metadata.get(key)))
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _artifact_rows(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for key in ("artifacts", "research_artifacts"):
        for row in state.get(key, []):
            artifact_id = str(row.get("artifact_id") or "")
            if artifact_id and artifact_id in seen:
                continue
            if artifact_id:
                seen.add(artifact_id)
            rows.append(row)
    return rows


def _revision_number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _latest_route_work_directives(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the newest explicit pause/keep decision for each route.

    Route-triage artifacts are historical evidence, not permanent locks.  A
    later advisor report that keeps, repairs, resumes, or reopens an active
    route must supersede an older pause and may deliberately override the
    scoreboard's heuristic stall classification.
    """
    pause_keys = (
        "paused_or_abandoned_route_ids",
        "paused_route_ids",
        "abandoned_route_ids",
        "blocked_route_ids",
        "stale_route_ids",
    )
    keep_keys = (
        "kept_route_ids",
        "recommended_kept_route_ids",
        "active_route_ids",
        "resumed_route_ids",
        "reopened_route_ids",
    )
    pause_terms = ("block", "pause", "abandon", "stale", "low_yield", "kill", "retire")
    keep_terms = ("keep", "repair", "resume", "reopen", "reactivate", "continue", "active")
    directives: dict[str, dict[str, Any]] = {}

    def record(route_id: str, *, paused: bool, artifact: Mapping[str, Any], reason: str) -> None:
        if not route_id:
            return
        rank = (
            _revision_number(artifact.get("state_revision")),
            str(artifact.get("created_at") or ""),
            str(artifact.get("artifact_id") or ""),
        )
        existing = directives.get(route_id)
        if existing and tuple(existing["rank"]) > rank:
            return
        directives[route_id] = {
            "paused": paused,
            "source_id": str(artifact.get("artifact_id") or ""),
            "reason": reason,
            "rank": rank,
        }

    for artifact in _artifact_rows(state):
        metadata = _json_object(artifact.get("metadata_json", artifact.get("metadata")))
        if not metadata:
            continue
        for route_id in _metadata_strings(metadata, *pause_keys):
            record(route_id, paused=True, artifact=artifact, reason="explicit pause or abandonment directive")
        for route_id in _metadata_strings(metadata, *keep_keys):
            record(route_id, paused=False, artifact=artifact, reason="explicit keep or resume directive")

        raw_decisions = metadata.get("route_decisions") or []
        decisions: list[tuple[str, str]] = []
        if isinstance(raw_decisions, Mapping):
            for route_id, payload in raw_decisions.items():
                if isinstance(payload, Mapping):
                    decision = str(payload.get("decision") or payload.get("status") or "")
                    route_id = str(payload.get("route_id") or route_id or "")
                else:
                    decision = str(payload or "")
                decisions.append((str(route_id or ""), decision))
        elif isinstance(raw_decisions, Iterable) and not isinstance(raw_decisions, (str, bytes)):
            for payload in raw_decisions:
                if not isinstance(payload, Mapping):
                    continue
                decisions.append(
                    (
                        str(payload.get("route_id") or payload.get("id") or ""),
                        str(payload.get("decision") or payload.get("status") or ""),
                    )
                )
        for route_id, decision in decisions:
            normalized = decision.strip().lower()
            if any(term in normalized for term in pause_terms):
                record(route_id, paused=True, artifact=artifact, reason=f"route decision: {decision}")
            elif any(term in normalized for term in keep_terms):
                record(route_id, paused=False, artifact=artifact, reason=f"route decision: {decision}")
    return directives


def _explicitly_refuted_debt_ids(state: Mapping[str, Any]) -> set[str]:
    """Debts defeated by a validator-confirmed counterexample artifact."""
    refuted: set[str] = set()
    for artifact in _artifact_rows(state):
        if str(artifact.get("artifact_type") or "") != "confirmed_counterexample":
            continue
        metadata = _json_object(artifact.get("metadata_json", artifact.get("metadata")))
        refuted.update(
            _metadata_strings(
                metadata,
                "refuted_obligation_id",
                "refuted_obligation_ids",
                "refuted_debt_id",
                "refuted_debt_ids",
            )
        )
    return refuted


def supersession_index(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Return derived stale/superseded graph ids.

    Supersession is deliberately metadata-driven. A repaired mathematical statement
    should displace the stale wording without needing a brittle ad hoc scheduler
    rule, while ordinary paused routes remain distinct from truly abandoned ones.
    """
    claims = claim_map(state)
    routes = {str(row.get("route_id") or ""): row for row in state.get("routes", [])}
    route_ids_by_conclusion: dict[str, list[str]] = {}
    for route in state.get("routes", []):
        route_ids_by_conclusion.setdefault(str(route.get("conclusion_claim_id") or ""), []).append(str(route.get("route_id") or ""))

    superseded_claims: dict[str, dict[str, Any]] = {}
    superseded_routes: dict[str, dict[str, Any]] = {}
    stale_routes: dict[str, dict[str, Any]] = {}

    def mark_claim(old_id: str, *, replacement_ids: list[str], reason: str, source_id: str) -> None:
        if not old_id or old_id == "root" or old_id not in claims:
            return
        record = superseded_claims.setdefault(
            old_id,
            {
                "claim_id": old_id,
                "replacement_claim_ids": [],
                "reason": reason,
                "source_ids": [],
            },
        )
        for replacement_id in replacement_ids:
            if replacement_id and replacement_id not in record["replacement_claim_ids"]:
                record["replacement_claim_ids"].append(replacement_id)
        if source_id and source_id not in record["source_ids"]:
            record["source_ids"].append(source_id)
        for route_id in route_ids_by_conclusion.get(old_id, []):
            mark_route(route_id, replacement_route_ids=[], reason=reason, source_id=source_id, superseded=True)

    def mark_route(
        route_id: str,
        *,
        replacement_route_ids: list[str],
        reason: str,
        source_id: str,
        superseded: bool,
    ) -> None:
        if not route_id or route_id not in routes:
            return
        bucket = superseded_routes if superseded else stale_routes
        record = bucket.setdefault(
            route_id,
            {
                "route_id": route_id,
                "replacement_route_ids": [],
                "reason": reason,
                "source_ids": [],
            },
        )
        for replacement_id in replacement_route_ids:
            if replacement_id and replacement_id not in record["replacement_route_ids"]:
                record["replacement_route_ids"].append(replacement_id)
        if source_id and source_id not in record["source_ids"]:
            record["source_ids"].append(source_id)

    for claim in state.get("claims", []):
        claim_id = str(claim.get("claim_id") or "")
        tags = set(_json_strings(claim.get("tags_json", claim.get("tags", []))))
        validation = str(claim.get("validation_status") or "")
        lifecycle = str(claim.get("lifecycle_status") or "")
        if "statement_repair" in tags and (
            validation in VERIFIED_VALIDATION_STATUSES or lifecycle in {"integrated", "superseded"}
        ):
            for parent_id in claim_parent_ids(claim):
                mark_claim(
                    parent_id,
                    replacement_ids=[claim_id],
                    reason="verified statement_repair claim supersedes older wording",
                    source_id=claim_id,
                )

    explicit_claim_keys = (
        "supersedes_claim_id",
        "supersedes_claim_ids",
        "superseded_claim_id",
        "superseded_claim_ids",
        "obsolete_claim_id",
        "obsolete_claim_ids",
        "old_claim_id",
        "old_claim_ids",
        "replaced_claim_id",
        "replaced_claim_ids",
    )
    explicit_route_keys = (
        "supersedes_route_id",
        "supersedes_route_ids",
        "superseded_route_id",
        "superseded_route_ids",
        "obsolete_route_id",
        "obsolete_route_ids",
        "old_route_id",
        "old_route_ids",
        "replaced_route_id",
        "replaced_route_ids",
    )
    replacement_claim_keys = (
        "replacement_claim_id",
        "replacement_claim_ids",
        "repaired_claim_id",
        "repaired_claim_ids",
        "new_claim_id",
        "new_claim_ids",
        "next_target_id",
    )
    replacement_route_keys = (
        "replacement_route_id",
        "replacement_route_ids",
        "repaired_route_id",
        "repaired_route_ids",
        "new_route_id",
        "new_route_ids",
        "kept_route_ids",
    )
    for artifact in _artifact_rows(state):
        metadata = _json_object(artifact.get("metadata_json"))
        if not metadata:
            continue
        source_id = str(artifact.get("artifact_id") or "")
        replacement_claims = [claim_id for claim_id in _metadata_strings(metadata, *replacement_claim_keys) if claim_id in claims]
        replacement_routes = [route_id for route_id in _metadata_strings(metadata, *replacement_route_keys) if route_id in routes]
        for old_id in _metadata_strings(metadata, *explicit_claim_keys):
            mark_claim(
                old_id,
                replacement_ids=replacement_claims,
                reason="artifact metadata marks this claim as superseded by repaired work",
                source_id=source_id,
            )
        for old_route_id in _metadata_strings(metadata, *explicit_route_keys):
            mark_route(
                old_route_id,
                replacement_route_ids=replacement_routes,
                reason="artifact metadata marks this route as superseded by repaired work",
                source_id=source_id,
                superseded=True,
            )
    for route_id, directive in _latest_route_work_directives(state).items():
        if not directive["paused"]:
            continue
        mark_route(
            route_id,
            replacement_route_ids=[],
            reason="latest advisor or triage directive says this route should not receive ordinary proof work",
            source_id=str(directive.get("source_id") or ""),
            superseded=False,
        )

    return {
        "policy": "metadata-and-statement-repair-supersession",
        "superseded_claim_ids": sorted(superseded_claims),
        "superseded_route_ids": sorted(superseded_routes),
        "stale_route_ids": sorted(stale_routes),
        "claims": [superseded_claims[key] for key in sorted(superseded_claims)],
        "routes": [superseded_routes[key] for key in sorted(superseded_routes)],
        "stale_routes": [stale_routes[key] for key in sorted(stale_routes)],
    }


def claim_is_retired(row: Mapping[str, Any]) -> bool:
    """Return whether a claim is historical rather than part of the live proof."""
    return (
        row.get("lifecycle_status") in RETIRED_CLAIM_LIFECYCLES
        or row.get("validation_status") == "refuted"
    )


def claim_is_verified(row: Mapping[str, Any]) -> bool:
    """Return whether a current claim has a positive verification verdict."""
    return (
        not claim_is_retired(row)
        and row.get("validation_status") in VERIFIED_VALIDATION_STATUSES
    )


def claim_map(state: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("claim_id")): row for row in state.get("claims", [])}


def root_distance_for_claim_id(state: Mapping[str, Any], claim_id: str) -> int:
    if claim_id == "root":
        return 0
    claims = claim_map(state)
    row = claims.get(claim_id)
    if row is None:
        return 99

    seen = {claim_id}
    frontier = [(claim_id, 0)]
    while frontier:
        current_id, distance = frontier.pop(0)
        current = claims.get(current_id)
        if current is None:
            continue
        for parent_id in claim_parent_ids(current):
            if parent_id == "root":
                return distance + 1
            if parent_id not in seen:
                seen.add(parent_id)
                frontier.append((parent_id, distance + 1))

    try:
        depth = int(row.get("reduction_depth", 99))
    except Exception:
        depth = 99
    return depth if depth >= 0 else 99


def frontier_claim_ids(state: Mapping[str, Any], *, max_items: int = 12) -> set[str]:
    """Return claims that are closest to closing an active route to root."""
    claims = claim_map(state)
    superseded_claim_ids = set(supersession_index(state).get("superseded_claim_ids", []))
    route_inferences: dict[str, list[Mapping[str, Any]]] = {}
    for inf in state.get("inferences", []):
        route_inferences.setdefault(str(inf.get("route_id") or ""), []).append(inf)

    selected: list[str] = []

    def add_claim(claim_id: str) -> None:
        row = claims.get(claim_id)
        if row and claim_id not in superseded_claim_ids and claim_is_unresolved(row) and claim_id not in selected:
            selected.append(claim_id)

    for route in state.get("routes", []):
        if route.get("status") != "active" or route.get("relation_to_parent") != "sufficient":
            continue
        conclusion = str(route.get("conclusion_claim_id") or "")
        if conclusion != "root" and root_distance_for_claim_id(state, conclusion) > FAR_FROM_ROOT_DISTANCE:
            continue
        inferences = route_inferences.get(str(route.get("route_id") or ""), [])
        if not inferences:
            add_claim(conclusion)
            continue
        for inf in inferences:
            for premise_id in inf.get("premise_claim_ids", []):
                add_claim(str(premise_id))
            if inf.get("validation_status") not in VERIFIED_VALIDATION_STATUSES:
                add_claim(str(inf.get("conclusion_claim_id") or conclusion))

    for debt in state.get("debts", []):
        if debt.get("status") != "active":
            continue
        target_id = str(debt.get("suggested_next_target") or debt.get("owner_id") or "")
        if root_distance_for_claim_id(state, target_id) <= FAR_FROM_ROOT_DISTANCE:
            add_claim(target_id)

    if not selected:
        candidates = [row for row in state.get("claims", []) if claim_is_unresolved(row)]
        candidates.sort(
            key=lambda row: (
                root_distance_for_claim_id(state, str(row.get("claim_id") or "")),
                -float(row.get("root_impact", 0.0)),
                int(row.get("reduction_depth", 99)),
                str(row.get("claim_id") or ""),
            )
        )
        for row in candidates:
            add_claim(str(row.get("claim_id") or ""))
            if len(selected) >= max_items:
                break

    return set(selected[:max_items])


def active_frontier_pressure(
    state: Mapping[str, Any],
    *,
    claim_cap: int = FRONTIER_PRESSURE_CLAIM_CAP,
    compression_cap: int = FRONTIER_PRESSURE_COMPRESSION_CAP,
) -> Dict[str, Any]:
    """Summarize whether root-local unresolved claims are getting too wide."""
    unresolved: list[Dict[str, Any]] = []
    root_local: list[Dict[str, Any]] = []
    superseded_claim_ids = set(supersession_index(state).get("superseded_claim_ids", []))
    for row in state.get("claims", []):
        claim_id = str(row.get("claim_id") or "")
        if claim_id == "root" or claim_id in superseded_claim_ids or not claim_is_unresolved(row):
            continue
        root_distance = root_distance_for_claim_id(state, claim_id)
        item = {
            "claim_id": claim_id,
            "root_distance": root_distance,
            "root_impact": float(row.get("root_impact", 0.0) or 0.0),
            "maturity": proof_trunk_maturity(state, claim_id),
        }
        unresolved.append(item)
        if root_distance <= FAR_FROM_ROOT_DISTANCE:
            root_local.append(item)

    root_local.sort(key=lambda item: (int(item["root_distance"]), -float(item["root_impact"]), str(item["claim_id"])))
    over_cap = len(root_local) >= claim_cap
    compression_preferred = len(root_local) >= compression_cap
    return {
        "policy": "active-frontier-pressure",
        "active_unverified_claim_count": len(unresolved),
        "active_root_local_unverified_claim_count": len(root_local),
        "claim_cap": claim_cap,
        "compression_cap": compression_cap,
        "over_claim_cap": over_cap,
        "compression_preferred": compression_preferred,
        "sample_claim_ids": [str(item["claim_id"]) for item in root_local[:12]],
        "directive": (
            "work_existing_proof_route_before_new_decomposition"
            if over_cap
            else "decomposition_width_ok"
        ),
    }


def proof_trunk_maturity(state: Mapping[str, Any], claim_id: str) -> str:
    claims = claim_map(state)
    claim = claims.get(claim_id)
    if claim is None:
        return "unknown"
    if claim_id in set(supersession_index(state).get("superseded_claim_ids", [])):
        return "superseded"
    if claim.get("lifecycle_status") == "integrated":
        return "integrated"
    if claim.get("lifecycle_status") == "superseded":
        return "superseded"
    if claim.get("lifecycle_status") == "abandoned":
        return "abandoned"
    if claim_is_verified(claim):
        return "verified"
    if any(
        debt.get("status") == "active"
        and debt.get("severity") == "blocking"
        and str(debt.get("owner_id") or "") == claim_id
        for debt in state.get("debts", [])
    ):
        return "verifier_gap"
    if any(str(run.get("target_id") or "") == claim_id for run in state.get("runs", []) + state.get("recent_runs", [])):
        return "attempted"
    if any(route.get("conclusion_claim_id") == claim_id for route in state.get("routes", [])):
        return "routed"
    return "proposed"


def maturity_rank(maturity: str) -> int:
    return {
        "verifier_gap": 0,
        "attempted": 1,
        "routed": 2,
        "proposed": 3,
        "verified": 4,
        "integrated": 5,
        "abandoned": 6,
        "superseded": 6,
        "unknown": 7,
    }.get(maturity, 7)


def claim_type_label(state: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    claim_id = str(row.get("claim_id") or "")
    if claim_id == "root":
        return "root_theorem"
    text = " ".join(str(row.get(field) or "") for field in ("claim_id", "kind", "statement", "hypotheses"))
    if is_bookkeeping_text(text):
        return "bookkeeping"
    tags = json_loads(row.get("tags_json", row.get("tags", [])))
    kind = str(row.get("kind") or "")
    if kind == "reference" or "literature" in tags or "retrieval" in tags:
        return "literature_fact"
    if claim_is_verified(row):
        return "partial_result"
    root_distance = root_distance_for_claim_id(state, claim_id)
    root_impact = float(row.get("root_impact", 0.0))
    if root_distance <= 1 or root_impact >= 0.75:
        return "main_trunk"
    if row.get("hypotheses") or json_loads(row.get("conditions_json", row.get("conditions", []))):
        return "technical_condition"
    if root_distance <= FAR_FROM_ROOT_DISTANCE:
        return "supporting_lemma"
    return "auxiliary"


def is_bookkeeping_text(text: str) -> bool:
    normalized = normalize_text(text)
    return sum(1 for term in BOOKKEEPING_TERMS if term in normalized) >= 2


def decomposition_cooldown_active(state: Mapping[str, Any]) -> bool:
    recent = recent_substantive_runs(state)
    if not recent:
        return False
    for run in recent:
        mode = str(run.get("mode") or "")
        if mode in PROOF_WORK_MODES:
            return False
        if mode in DECOMPOSITION_MODES:
            return True
    return False


def recent_substantive_runs(state: Mapping[str, Any], *, limit: int = 8) -> list[Mapping[str, Any]]:
    rows = list(state.get("recent_runs") or state.get("runs") or [])
    rows = [row for row in rows if str(row.get("mode") or "")]
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows[:limit]


def route_repair_pending_verifier(
    state: Mapping[str, Any],
    *,
    route_id: str,
    conclusion_id: str,
    debt: Mapping[str, Any],
) -> bool:
    """Whether a newer route-local proof asks the verifier to judge ``debt``.

    The debt ledger intentionally retains historical blockers.  Once a proof
    dossier explicitly repairs a route and requests verification, those rows
    must travel with the verifier packet instead of making the route look
    stalled and therefore unschedulable.
    """

    debt_last_seen = str(debt.get("last_seen") or "")
    artifacts = state.get("research_artifacts")
    if not isinstance(artifacts, list):
        artifacts = state.get("artifacts", [])
    for artifact in artifacts:
        if str(artifact.get("artifact_type") or "") not in {"proof_dossier", "deep_session_report"}:
            continue
        metadata = artifact.get("metadata_json", artifact.get("metadata", {}))
        if isinstance(metadata, str):
            metadata = json_loads(metadata, {})
        if not isinstance(metadata, Mapping):
            continue
        if str(metadata.get("artifact_roi") or "") not in {"route_repaired", "verifier_ready_route"}:
            continue
        artifact_route_id = str(metadata.get("route_id") or "")
        artifact_target_id = str(metadata.get("target_id") or "")
        if artifact_route_id and artifact_route_id != route_id:
            continue
        if artifact_target_id and artifact_target_id != conclusion_id:
            continue
        next_action = str(
            metadata.get("next_decisive_action")
            or metadata.get("next_decisive_step")
            or metadata.get("next_decisive_test")
            or ""
        ).lower()
        if "verif" not in next_action:
            continue
        created_at = str(artifact.get("created_at") or "")
        if debt_last_seen and created_at and created_at <= debt_last_seen:
            continue
        return True
    return False


def route_scoreboard(state: Mapping[str, Any], *, limit: int | None = None) -> list[Dict[str, Any]]:
    claims = claim_map(state)
    supersession = supersession_index(state)
    superseded_route_ids = set(supersession.get("superseded_route_ids", []))
    stale_route_ids = set(supersession.get("stale_route_ids", []))
    route_work_directives = _latest_route_work_directives(state)
    inferences_by_route: dict[str, list[Mapping[str, Any]]] = {}
    for inf in state.get("inferences", []):
        inferences_by_route.setdefault(str(inf.get("route_id") or ""), []).append(inf)

    rows: list[Dict[str, Any]] = []
    for route in state.get("routes", []):
        route_id = str(route.get("route_id") or "")
        conclusion_id = str(route.get("conclusion_claim_id") or "")
        conclusion = claims.get(conclusion_id, {})
        inferences = inferences_by_route.get(route_id, [])
        verified_inferences = [
            inf for inf in inferences
            if inf.get("validation_status") in VERIFIED_VALIDATION_STATUSES
        ]
        blocking_debts = [
            debt for debt in state.get("debts", [])
            if debt.get("status") == "active"
            and debt.get("severity") == "blocking"
            and str(debt.get("owner_id") or "") in {route_id, conclusion_id}
            and not debt_covered_by_integrated_claim(state, debt)
            and not route_repair_pending_verifier(
                state,
                route_id=route_id,
                conclusion_id=conclusion_id,
                debt=debt,
            )
        ]
        root_distance = root_distance_for_claim_id(state, conclusion_id)
        root_impact = float(conclusion.get("root_impact", 0.0) or 0.0)
        repeated_blockers = sum(int(debt.get("repeated_count") or 0) for debt in blocking_debts)
        if route_id in superseded_route_ids:
            status, reasons = "superseded", ["route is superseded by repaired proof-state work"]
        elif route_id in stale_route_ids:
            status, reasons = "stalled", ["advisor or triage report paused this stale route"]
        elif (
            route_work_directives.get(route_id, {}).get("paused") is False
            and str(route.get("status") or "") == "active"
        ):
            status, reasons = "promising", []
        else:
            status, reasons = _route_score_status(
                route,
                inference_count=len(inferences),
                verified_inference_count=len(verified_inferences),
                blocking_debt_count=len(blocking_debts),
                repeated_blockers=repeated_blockers,
                root_distance=root_distance,
                root_impact=root_impact,
            )
        score = _route_score(
            status=status,
            root_distance=root_distance,
            root_impact=root_impact,
            inference_count=len(inferences),
            verified_inference_count=len(verified_inferences),
            blocking_debt_count=len(blocking_debts),
            repeated_blockers=repeated_blockers,
        )
        rows.append(
            {
                "route_id": route_id,
                "conclusion_claim_id": conclusion_id,
                "label": route.get("label", route_id),
                "scoreboard_status": status,
                "score": score,
                "root_distance": root_distance,
                "root_impact": root_impact,
                "inference_count": len(inferences),
                "verified_inference_count": len(verified_inferences),
                "blocking_debt_count": len(blocking_debts),
                "repeated_blocker_count": repeated_blockers,
                "kill_reasons": reasons,
            }
        )
    rows.sort(key=lambda row: (-float(row["score"]), row["root_distance"], row["route_id"]))
    return rows[:limit] if limit is not None else rows


def paused_route_ids(state: Mapping[str, Any]) -> set[str]:
    supersession = supersession_index(state)
    paused = {
        row["route_id"]
        for row in route_scoreboard(state)
        if row["scoreboard_status"] in PAUSED_ROUTE_STATUSES
    }
    paused.update(str(route_id) for route_id in supersession.get("superseded_route_ids", []))
    paused.update(str(route_id) for route_id in supersession.get("stale_route_ids", []))
    return paused


def route_is_paused(state: Mapping[str, Any], route_id: str) -> bool:
    return route_id in paused_route_ids(state)


def _route_score_status(
    route: Mapping[str, Any],
    *,
    inference_count: int,
    verified_inference_count: int,
    blocking_debt_count: int,
    repeated_blockers: int,
    root_distance: int,
    root_impact: float,
) -> tuple[str, list[str]]:
    route_status = str(route.get("status") or "")
    if route_status == "abandoned":
        return "abandoned", ["route is abandoned"]
    if route_status == "superseded":
        return "superseded", ["route is superseded by repaired proof-state work"]
    if route_status == "blocked":
        return "blocked", ["route is blocked pending a central obstruction or proof debt"]
    reasons: list[str] = []
    if root_distance > FAR_FROM_ROOT_DISTANCE and root_impact < 0.35:
        reasons.append("far from root with low root impact")
    if repeated_blockers >= 3:
        reasons.append("blocking debt repeated without progress")
    if route.get("failure_fingerprint") and verified_inference_count == 0:
        reasons.append("route has a prior failure fingerprint and no verified inference")
    if reasons:
        status = "low_yield" if reasons[0].startswith("far from root") else "stalled"
        return status, reasons
    if inference_count and verified_inference_count == inference_count:
        return "verified_part", []
    if verified_inference_count > 0 or root_distance <= 2 or root_impact >= 0.7:
        return "promising", []
    return "active", []


def _route_score(
    *,
    status: str,
    root_distance: int,
    root_impact: float,
    inference_count: int,
    verified_inference_count: int,
    blocking_debt_count: int,
    repeated_blockers: int,
) -> float:
    score = 1.0 + root_impact - (0.08 * max(0, root_distance))
    if inference_count:
        score += 0.4 * (verified_inference_count / inference_count)
    score -= 0.25 * blocking_debt_count
    score -= 0.08 * repeated_blockers
    if status == "verified_part":
        score += 0.5
    if status == "promising":
        score += 0.25
    if status in PAUSED_ROUTE_STATUSES:
        score -= 1.0
    if status == "superseded":
        score -= 1.0
    return round(score, 3)


DECISIVE_DEBT_TYPES = {
    "blocking_bridge",
    "missing_bridge",
    "proof_obligation",
    "counterexample_validation",
    "statement_repair_blocker",
}


DECISIVE_TEXT_MARKERS = (
    "prove or refute",
    "prove or disprove",
    "either prove",
    "decide whether",
    "decide if",
    "decide the",
    "exact theorem",
    "counterexample test",
    "classification theorem",
)


DECISIVE_OBJECT_MARKERS = (
    "theorem",
    "lemma",
    "criterion",
    "bridge",
    "classification",
    "counterexample",
)


def _graph_owner_distance(state: Mapping[str, Any], owner_id: str, *, fallback_target_id: str = "root") -> int:
    if not owner_id:
        return root_distance_for_claim_id(state, fallback_target_id)
    if owner_id in claim_map(state):
        return root_distance_for_claim_id(state, owner_id)
    for route in state.get("routes", []):
        if str(route.get("route_id") or "") == owner_id:
            return root_distance_for_claim_id(state, str(route.get("conclusion_claim_id") or fallback_target_id))
    for inference in state.get("inferences", []):
        if str(inference.get("inference_id") or "") == owner_id:
            return root_distance_for_claim_id(state, str(inference.get("conclusion_claim_id") or fallback_target_id))
    return root_distance_for_claim_id(state, fallback_target_id)


def decisive_theorem_test_signal(
    state: Mapping[str, Any],
    *,
    target_id: str = "root",
    debt_id: str = "",
) -> Dict[str, Any]:
    """Pick one theorem-level obligation that should decide the next branch."""
    superseded_claim_ids = set(supersession_index(state).get("superseded_claim_ids", []))
    refuted_debt_ids = _explicitly_refuted_debt_ids(state)
    candidates: list[tuple[float, Mapping[str, Any]]] = []
    for debt in state.get("debts", []):
        if debt.get("status") != "active" or debt.get("severity") != "blocking":
            continue
        if str(debt.get("debt_id") or "") in refuted_debt_ids:
            continue
        if debt_id and str(debt.get("debt_id") or "") != debt_id:
            continue
        owner_id = str(debt.get("owner_id") or "")
        suggested = str(debt.get("suggested_next_target") or "")
        local_target = suggested or owner_id or target_id
        if owner_id in superseded_claim_ids or local_target in superseded_claim_ids:
            continue
        distances = [_graph_owner_distance(state, owner_id, fallback_target_id=target_id)]
        if suggested:
            distances.append(root_distance_for_claim_id(state, suggested))
        distance = min(distances)
        if distance > FAR_FROM_ROOT_DISTANCE and owner_id != "root":
            continue
        obligation = str(debt.get("obligation") or "")
        debt_type = str(debt.get("debt_type") or "")
        obligation_lower = obligation.lower()
        has_decision_marker = any(term in obligation_lower for term in DECISIVE_TEXT_MARKERS)
        has_object_marker = any(term in obligation_lower for term in DECISIVE_OBJECT_MARKERS)
        theoremish = has_decision_marker and (debt_type in DECISIVE_DEBT_TYPES or has_object_marker)
        if not theoremish:
            continue
        score = (
            2.0
            - (0.12 * max(0, distance))
            + (0.2 * int(debt.get("repeated_count") or 0))
            + (0.4 if owner_id == "root" or suggested == "root" else 0.0)
        )
        candidates.append((score, debt))
    if not candidates:
        return {}
    candidates.sort(key=lambda item: (-item[0], str(item[1].get("debt_id") or "")))
    debt = candidates[0][1]
    owner_id = str(debt.get("owner_id") or "")
    suggested = str(debt.get("suggested_next_target") or "")
    signal_target = suggested if suggested and root_distance_for_claim_id(state, suggested) < 99 else owner_id or target_id
    if signal_target not in claim_map(state):
        signal_target = target_id
    obligation = _compact_text(str(debt.get("obligation") or ""), 900)
    return {
        "policy": "decisive-theorem-test",
        "target_id": signal_target,
        "debt_id": str(debt.get("debt_id") or ""),
        "owner_id": owner_id,
        "debt_type": str(debt.get("debt_type") or ""),
        "theorem_obligation": obligation,
        "why_decisive": (
            "This active root-local blocking obligation is theorem-shaped; deciding it should either unlock the current proof "
            "branch, kill it cleanly, or replace it with a strictly narrower theorem."
        ),
        "acceptance_criteria": [
            "State the exact theorem or counterexample test in local notation.",
            "Either prove it, refute it, or cite a precise theorem with checked hypotheses.",
            "If it cannot be decided, emit one strictly narrower theorem-level debt with clear acceptance criteria.",
            "Do not produce broad route inventories or generic status summaries.",
        ],
    }


def _action_decisive_theorem_test_signal(
    state: Mapping[str, Any],
    action: Optional[Mapping[str, Any]],
    *,
    target_id: str,
) -> Dict[str, Any]:
    """Prefer the theorem explicitly selected by the current workflow action."""
    if not action:
        return {}
    explicit = action.get("decisive_theorem_test")
    if isinstance(explicit, Mapping) and str(explicit.get("theorem_obligation") or "").strip():
        return dict(explicit)
    if action.get("verify_ready_route_policy") or action.get("strict_verifier_scope"):
        action_target = str(action.get("target_id") or target_id)
        target_claim = claim_map(state).get(action_target, {})
        obligation = _compact_text(str(target_claim.get("statement") or ""), 900)
        if obligation:
            return {
                "policy": "selected-route-verification-test",
                "target_id": action_target,
                "debt_id": "",
                "owner_id": action_target,
                "debt_type": "route_verification",
                "theorem_obligation": obligation,
                "why_decisive": (
                    "This child is a bounded strict verification of the selected route; its conclusion claim "
                    "supersedes advisor research bottlenecks for this session."
                ),
                "acceptance_criteria": [
                    "Check the selected route against its exact conclusion claim and listed evidence.",
                    "Verify only if the route proves the claim with no gaps or hidden hypotheses.",
                    "Otherwise attach a verification report and add precise local gap debts.",
                ],
            }
    obligation = _compact_text(str(action.get("advisor_decisive_missing_statement") or ""), 900)
    if not obligation:
        return {}
    acceptance_criteria = [
        str(item).strip()
        for item in action.get("validation_acceptance_criteria", [])
        if str(item).strip()
    ]
    if not acceptance_criteria:
        acceptance_criteria = [
            "State the exact theorem or counterexample test in local notation.",
            "Either prove it, refute it, or cite a precise theorem with checked hypotheses.",
            "If it cannot be decided, emit one strictly narrower theorem-level debt with clear acceptance criteria.",
            "Do not produce broad route inventories or generic status summaries.",
        ]
    action_target = str(action.get("target_id") or target_id)
    return {
        "policy": "advisor-decisive-theorem-test",
        "target_id": action_target,
        "debt_id": str(action.get("debt_id") or ""),
        "owner_id": action_target,
        "debt_type": "advisor_bottleneck",
        "theorem_obligation": obligation,
        "why_decisive": (
            "The current advisor-directed workflow action selected this theorem as the decisive bottleneck; "
            "it supersedes generic ranking among older active debts for this child session."
        ),
        "acceptance_criteria": acceptance_criteria,
    }


def build_proof_spine(
    state: Mapping[str, Any],
    *,
    action: Optional[Mapping[str, Any]] = None,
    target_id: str = "root",
) -> Dict[str, Any]:
    supersession = supersession_index(state)
    superseded_claim_ids = set(supersession.get("superseded_claim_ids", []))
    refuted_debt_ids = _explicitly_refuted_debt_ids(state)
    verified: list[Dict[str, Any]] = []
    for claim in state.get("claims", []):
        claim_id = str(claim.get("claim_id") or "")
        if claim_id == "root" or claim_id in superseded_claim_ids:
            continue
        if claim.get("validation_status") not in VERIFIED_VALIDATION_STATUSES:
            continue
        if root_distance_for_claim_id(state, claim_id) > FAR_FROM_ROOT_DISTANCE and float(claim.get("root_impact", 0.0) or 0.0) < 0.5:
            continue
        verified.append(
            {
                "claim_id": claim_id,
                "lifecycle_status": claim.get("lifecycle_status", ""),
                "root_distance": root_distance_for_claim_id(state, claim_id),
                "statement": _compact_text(str(claim.get("statement") or ""), 260),
            }
        )
    verified.sort(key=lambda row: (row["root_distance"], row["claim_id"]))

    blocking_debts: list[Dict[str, Any]] = []
    for debt in state.get("debts", []):
        if debt.get("status") != "active" or debt.get("severity") != "blocking":
            continue
        if str(debt.get("debt_id") or "") in refuted_debt_ids:
            continue
        owner_id = str(debt.get("owner_id") or "")
        suggested = str(debt.get("suggested_next_target") or "")
        if owner_id in superseded_claim_ids or suggested in superseded_claim_ids:
            continue
        distances = [_graph_owner_distance(state, owner_id, fallback_target_id=target_id)]
        if suggested:
            distances.append(root_distance_for_claim_id(state, suggested))
        distance = min(distances)
        if distance > FAR_FROM_ROOT_DISTANCE and owner_id != "root":
            continue
        blocking_debts.append(
            {
                "debt_id": str(debt.get("debt_id") or ""),
                "owner_id": owner_id,
                "suggested_next_target": suggested,
                "debt_type": str(debt.get("debt_type") or ""),
                "repeated_count": int(debt.get("repeated_count") or 0),
                "obligation": _compact_text(str(debt.get("obligation") or ""), 280),
            }
        )
    blocking_debts.sort(key=lambda row: (-row["repeated_count"], row["debt_id"]))

    route_rows = route_scoreboard(state, limit=8)
    decisive = _action_decisive_theorem_test_signal(
        state, action, target_id=target_id
    ) or decisive_theorem_test_signal(state, target_id=target_id)
    return {
        "policy": "always-current-proof-spine",
        "target_id": target_id,
        "purpose": (
            "Compact working memory for the next math child: what is already certified, what should not be retried, "
            "and which theorem-level obligation is currently decisive."
        ),
        "verified_partial_results": verified[:8],
        "current_bottlenecks": blocking_debts[:6],
        "route_scoreboard": route_rows[:6],
        "supersession": {
            "superseded_claim_ids": list(supersession.get("superseded_claim_ids", []))[:8],
            "superseded_route_ids": list(supersession.get("superseded_route_ids", []))[:8],
            "stale_route_ids": list(supersession.get("stale_route_ids", []))[:8],
            "claims": list(supersession.get("claims", []))[:4],
            "routes": list(supersession.get("routes", []))[:4],
            "stale_routes": list(supersession.get("stale_routes", []))[:4],
        },
        "decisive_theorem_test": decisive,
        "math_first_rules": [
            "Do not retry superseded claims or stale route wording unless explicitly repairing the supersession record.",
            "Prefer proving, refuting, citing, or narrowing the decisive theorem test over writing broad inventories.",
            "When a verifier finds an exact-statement mismatch, create the repaired theorem and supersede the stale wording.",
        ],
        "workflow_action": {
            "search_intent": str((action or {}).get("search_intent") or ""),
            "mode": str((action or {}).get("mode") or ""),
            "target_id": str((action or {}).get("target_id") or target_id),
        },
    }


def claim_core_fingerprint(statement: str) -> str:
    normalized = normalize_text(statement)
    normalized = re.sub(r"^(claim|lemma|theorem|proposition|corollary)\s+[a-z0-9._-]*\s*", "", normalized)
    normalized = re.sub(r"^(prove|show|establish|verify)\s+(that\s+)?", "", normalized)
    normalized = re.sub(r"^it\s+(remains|suffices)\s+to\s+(prove|show)\s+(that\s+)?", "", normalized)
    normalized = re.sub(r"\b(albilich|v1)\b", "", normalized)
    normalized = " ".join(normalized.split())
    return fingerprint_text(normalized, length=20)


def _claim_signature_tokens(statement: str) -> set[str]:
    tokens: set[str] = set()
    for token in normalize_text(statement).split():
        if len(token) < 2 or token.isdigit() or token in CLAIM_SIGNATURE_STOPWORDS:
            continue
        if len(token) > 5 and token.endswith("ies"):
            token = token[:-3] + "y"
        elif len(token) > 5 and token.endswith("ing"):
            token = token[:-3]
        elif len(token) > 5 and token.endswith("ed"):
            token = token[:-2]
        elif len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        tokens.add(token)
    # ``normalize_text`` deliberately removes mathematical punctuation, but
    # doing so turns family names such as ``A_n`` into the stopword-sized
    # tokens ``a`` and ``n``.  Preserve subscripted identifiers as signature
    # tokens so theorem templates for different mathematical objects do not
    # look like restatements merely because their quantifiers and conclusions
    # have the same prose shape.
    tokens.update(
        match.group(0).lower()
        for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9]+\b", str(statement or ""))
    )
    return tokens


def _is_integrated_claim_row(row: Mapping[str, Any]) -> bool:
    return str(row.get("lifecycle_status") or "") == "integrated"


def _near_integrated_claim_restatement(
    *,
    statement: str,
    existing_statement: str,
) -> bool:
    new_tokens = _claim_signature_tokens(statement)
    existing_tokens = _claim_signature_tokens(existing_statement)
    if len(new_tokens) < 15 or len(existing_tokens) < 15:
        return False
    shared = new_tokens & existing_tokens
    if len(shared) < 12:
        return False
    novel_tokens = new_tokens - existing_tokens - CLAIM_RESTATEMENT_NOVELTY_STOPWORDS
    new_coverage = len(shared) / max(1, len(new_tokens))
    existing_coverage = len(shared) / max(1, len(existing_tokens))
    size_ratio = len(existing_tokens) / max(1, len(new_tokens))
    # Short closing qualifications such as "in the proper ... branch" can add a
    # handful of surface tokens without changing the theorem.  Permit that only
    # when the two signatures otherwise have strong bidirectional overlap; this
    # keeps genuinely strengthened statements out of the duplicate guard.
    if len(novel_tokens) >= 4 and not (
        len(novel_tokens) <= 5
        and new_coverage >= 0.75
        and existing_coverage >= 0.75
    ):
        return False
    # The common quantified-theorem template can dominate a much shorter claim
    # about a different object.  Require meaningful coverage in the existing
    # theorem as well; otherwise a new special-family theorem can be rejected
    # merely for sharing words such as ``Aut``, ``wr``, ``order``, and
    # ``proper subgroup`` with an integrated theorem.
    return new_coverage >= 0.62 and existing_coverage >= 0.70 and size_ratio <= 2.75


def integrated_claim_covering_debt_id(
    existing_claims: Iterable[Mapping[str, Any]],
    *,
    obligation: str,
) -> str:
    debt_tokens = _claim_signature_tokens(obligation)
    if len(debt_tokens) < 20:
        return ""
    for row in existing_claims:
        if not _is_integrated_claim_row(row):
            continue
        claim_tokens = _claim_signature_tokens(str(row.get("statement") or ""))
        if len(claim_tokens) < 15:
            continue
        shared = debt_tokens & claim_tokens
        if len(shared) < 16:
            continue
        debt_coverage = len(shared) / max(1, len(debt_tokens))
        claim_coverage = len(shared) / max(1, len(claim_tokens))
        if debt_coverage >= 0.34 and claim_coverage >= 0.25:
            return str(row.get("claim_id") or "")
    return ""


def debt_covered_by_integrated_claim(
    state: Mapping[str, Any],
    debt: Mapping[str, Any],
) -> bool:
    """Return whether an active-looking debt belongs to an integrated result.

    Debts are retained as an audit ledger after their branch closes.  Consumers
    deciding what is still open must therefore check both graph ownership and
    semantic coverage instead of treating every ``status=active`` row as a live
    proof obligation.
    """
    graph_ids = {
        str(debt.get("owner_id") or ""),
        str(debt.get("suggested_next_target") or ""),
    }
    target_ids = set(graph_ids)
    target_ids.update(
        str(row.get("conclusion_claim_id") or "")
        for row in state.get("routes", [])
        if str(row.get("route_id") or "") in graph_ids
    )
    target_ids.update(
        str(row.get("conclusion_claim_id") or "")
        for row in state.get("inferences", [])
        if str(row.get("inference_id") or "") in graph_ids
    )
    if any(
        str(claim.get("claim_id") or "") in target_ids
        and str(claim.get("lifecycle_status") or "") == "integrated"
        for claim in state.get("claims", [])
    ):
        return True
    debt_id = str(debt.get("debt_id") or "")
    debt_prefix = next((prefix for prefix in ("debt_", "debt-") if debt_id.startswith(prefix)), "")
    if debt_prefix:
        debt_subject = debt_id.removeprefix(debt_prefix)
        if any(
            any(
                str(claim.get("claim_id") or "").removeprefix(prefix) == debt_subject
                for prefix in ("claim_", "claim-")
                if str(claim.get("claim_id") or "").startswith(prefix)
            )
            and str(claim.get("lifecycle_status") or "") == "integrated"
            for claim in state.get("claims", [])
        ):
            return True
    obligation = " ".join(
        str(debt.get(key) or "")
        for key in ("debt_id", "debt_type", "obligation", "suggested_next_target")
    ).lower()
    return bool(integrated_claim_covering_debt_id(state.get("claims", []), obligation=obligation))


def obvious_duplicate_claim_id(
    existing_claims: Iterable[Mapping[str, Any]],
    *,
    statement: str,
    fingerprint: str = "",
) -> str:
    normalized = normalize_text(statement)
    core = claim_core_fingerprint(statement)
    for row in existing_claims:
        existing_id = str(row.get("claim_id") or "")
        if fingerprint and row.get("fingerprint") == fingerprint:
            return existing_id
        if normalize_text(str(row.get("statement") or "")) == normalized:
            return existing_id
        if core and claim_core_fingerprint(str(row.get("statement") or "")) == core:
            return existing_id
        if _is_integrated_claim_row(row) and _near_integrated_claim_restatement(
            statement=statement,
            existing_statement=str(row.get("statement") or ""),
        ):
            return existing_id
    return ""


def obvious_duplicate_route_id(
    existing_routes: Sequence[Mapping[str, Any]],
    *,
    conclusion_claim_id: str,
    relation_to_parent: str,
    strategy: str,
) -> str:
    strategy_fingerprint = fingerprint_text(strategy, length=20)
    for row in existing_routes:
        if row.get("conclusion_claim_id") != conclusion_claim_id:
            continue
        if row.get("relation_to_parent") != relation_to_parent:
            continue
        if fingerprint_text(str(row.get("strategy") or ""), length=20) == strategy_fingerprint:
            return str(row.get("route_id") or "")
    return ""
