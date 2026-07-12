"""Live web monitor for an Albilich v1 run.

A dependency-free dashboard (Python stdlib ``http.server`` only) that renders the
rich run-console payload with auto-refresh, so a run can be watched in a browser
instead of tailing ``albilich_run_console.md``.

Data source per poll:
  1. the live ``albilich_run_console.json`` the workflow writes during a run
     (preferred: it carries in-flight session logs and the current invocation);
  2. otherwise a fresh rebuild from the WAL-mode SQLite store (DB snapshot
     without in-memory live logs).

Launch with ``python -m agents.generation.phase2.cli monitor <problem>``.
"""

from __future__ import annotations

import json
import os
import errno
import threading
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Mapping
from urllib.parse import parse_qs, urlparse

from .console import build_run_console_payload
from .graph_policy import claim_is_retired, supersession_index
from .models import statement_is_interrogative_problem, utc_now
from .scheduler import bottleneck_frontier_summary, proof_spine_summary, route_verifier_readiness
from .research_strategy import strategy_observability
from .store import ProofStateStore
from . import steering

_LIVE_STATUSES = {"running", "started", "heartbeat", "planned"}
_LIVE_TELEMETRY_STALE_SECONDS = 180.0
MONITOR_REFRESH_INTERVAL_ENV = "ALBILICH_MONITOR_REFRESH_INTERVAL_SECONDS"
DEFAULT_MONITOR_REFRESH_INTERVAL_SECONDS = 60.0


def _monitor_refresh_interval_seconds(poll_ms: int) -> float:
    raw = os.environ.get(MONITOR_REFRESH_INTERVAL_ENV, "").strip()
    try:
        configured = float(raw) if raw else DEFAULT_MONITOR_REFRESH_INTERVAL_SECONDS
    except ValueError:
        configured = DEFAULT_MONITOR_REFRESH_INTERVAL_SECONDS
    return max(float(poll_ms) / 1000.0, configured, 5.0)


def _html_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def _report_has_items(value: Any) -> bool:
    if isinstance(value, (list, tuple, set)):
        return any(str(item or "").strip() for item in value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized not in {"", "[]", "none", "null", "false"}
    return bool(value)


def _claim_verification_history(
    state: Mapping[str, Any], *, artifact_target_overrides: Mapping[str, str] | None = None
) -> dict[str, dict[str, Any]]:
    """Summarize strict reports even when legacy patches left claims `untested`."""
    run_targets = {
        str(run.get("run_id") or ""): str(run.get("target_id") or "")
        for run in state.get("runs", [])
        if str(run.get("run_id") or "")
    }
    history: dict[str, dict[str, Any]] = {}
    target_overrides = artifact_target_overrides or {}
    for artifact in state.get("artifacts", []):
        if str(artifact.get("artifact_type") or "") != "verification_report":
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        target_id = str(
            metadata.get("target_id")
            or metadata.get("claim_id")
            or target_overrides.get(str(artifact.get("artifact_id") or ""), "")
            or run_targets.get(str(artifact.get("run_id") or ""), "")
            or ""
        )
        if not target_id:
            continue
        report = _json_object(metadata.get("verification_report"))
        blocking = bool(metadata.get("blocking_gap") or report.get("blocking_gap"))
        blocking = blocking or _report_has_items(metadata.get("critical_errors"))
        blocking = blocking or _report_has_items(metadata.get("gaps"))
        blocking = blocking or _report_has_items(report.get("critical_errors"))
        blocking = blocking or _report_has_items(report.get("gaps"))
        revision = int(artifact.get("state_revision") or 0)
        current = history.get(target_id)
        if current and int(current.get("latest_state_revision") or 0) > revision:
            current["report_count"] = int(current.get("report_count") or 0) + 1
            continue
        history[target_id] = {
            "report_count": int(current.get("report_count") or 0) + 1 if current else 1,
            "latest_state_revision": revision,
            "latest_artifact_id": str(artifact.get("artifact_id") or ""),
            "latest_verdict": str(metadata.get("verdict") or report.get("verdict") or ""),
            "blocking_gap": blocking,
        }
    return history


def _short_text(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _producer_role_code(role: str) -> str:
    normalized = str(role or "").strip().lower()
    return {
        "researcher": "R",
        "villain": "V",
        "literature_researcher": "LR",
        "phd_advisor": "PA",
        "strict_informal_verifier": "SV",
        "integration_verifier": "IV",
        "writer": "W",
    }.get(normalized, "".join(part[:1].upper() for part in normalized.split("_") if part)[:2] or "A")


def _proof_graph_payload(store: ProofStateStore, *, state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build a compact graph view from the current proof state.

    This is deliberately derived, not persisted: the dashboard should reveal the
    live proof frontier without introducing another graph store to keep in sync.
    """
    state = state if state is not None else store.get_state()
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    routes = {str(row.get("route_id") or ""): row for row in state.get("routes", [])}
    inferences = {str(row.get("inference_id") or ""): row for row in state.get("inferences", [])}
    artifacts = {str(row.get("artifact_id") or ""): row for row in state.get("artifacts", [])}
    debts = [row for row in state.get("debts", []) if str(row.get("status") or "") == "active"]

    route_counts_by_claim: dict[str, int] = {}
    inference_counts_by_route: dict[str, int] = {}
    verified_inference_counts_by_route: dict[str, int] = {}
    active_debts_by_owner: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    evidence_ids: set[str] = set()

    for route in routes.values():
        route_counts_by_claim[str(route.get("conclusion_claim_id") or "")] = (
            route_counts_by_claim.get(str(route.get("conclusion_claim_id") or ""), 0) + 1
        )
        evidence_ids.update(str(item) for item in _json_list(route.get("evidence_artifact_ids_json")) if item)
    for inf in inferences.values():
        route_id = str(inf.get("route_id") or "")
        inference_counts_by_route[route_id] = inference_counts_by_route.get(route_id, 0) + 1
        if str(inf.get("validation_status") or "") in {"informally_verified", "formally_verified"}:
            verified_inference_counts_by_route[route_id] = verified_inference_counts_by_route.get(route_id, 0) + 1
        evidence_ids.update(str(item) for item in _json_list(inf.get("evidence_artifact_ids_json")) if item)
    for claim in claims.values():
        evidence_ids.update(str(item) for item in _json_list(claim.get("evidence_artifact_ids_json")) if item)
    for debt in debts:
        owner_type = str(debt.get("owner_type") or "")
        owner_id = str(debt.get("owner_id") or "")
        active_debts_by_owner.setdefault((owner_type, owner_id), []).append(debt)
        evidence_ids.update(str(item) for item in _json_list(debt.get("source_artifact_ids_json")) if item)

    def owner_debt_count(owner_type: str, owner_id: str, *, blocking_only: bool = False) -> int:
        rows = active_debts_by_owner.get((owner_type, owner_id), [])
        if not blocking_only:
            return len(rows)
        return sum(1 for row in rows if str(row.get("severity") or "") == "blocking")

    nodes: list[Dict[str, Any]] = []
    edges: list[Dict[str, Any]] = []

    def add_node(node: Dict[str, Any]) -> None:
        if not any(existing["id"] == node["id"] for existing in nodes):
            nodes.append(node)

    def add_edge(source: str, target: str, relation: str, strength: str = "normal") -> None:
        edge = {"source": source, "target": target, "relation": relation, "strength": strength}
        if source and target and source != target and edge not in edges:
            edges.append(edge)

    for claim_id, claim in sorted(
        claims.items(),
        key=lambda item: (int(item[1].get("reduction_depth") or 0), item[0]),
    ):
        add_node(
            {
                "id": f"claim:{claim_id}",
                "kind": "claim",
                "label": claim_id,
                "status": str(claim.get("validation_status") or ""),
                "lifecycle_status": str(claim.get("lifecycle_status") or ""),
                "summary": _short_text(claim.get("statement"), 260),
                "root_distance": int(claim.get("reduction_depth") or 0),
                "root_impact": float(claim.get("root_impact") or 0.0),
                "route_count": route_counts_by_claim.get(claim_id, 0),
                "active_debt_count": owner_debt_count("claim", claim_id),
                "blocking_debt_count": owner_debt_count("claim", claim_id, blocking_only=True),
            }
        )
        for parent_id in _json_list(claim.get("parent_ids_json")):
            if str(parent_id) in claims:
                add_edge(f"claim:{parent_id}", f"claim:{claim_id}", "contains subclaim")

    for route_id, route in sorted(routes.items()):
        inf_count = inference_counts_by_route.get(route_id, 0)
        verified_count = verified_inference_counts_by_route.get(route_id, 0)
        readiness = route_verifier_readiness(state, route_id)
        verifier_ready = bool(readiness.get("verifier_ready"))
        add_node(
            {
                "id": f"route:{route_id}",
                "kind": "route",
                "label": route_id,
                "status": str(route.get("status") or ""),
                "summary": _short_text(route.get("strategy") or route.get("label"), 260),
                "conclusion_claim_id": str(route.get("conclusion_claim_id") or ""),
                "relation_to_parent": str(route.get("relation_to_parent") or ""),
                "inference_count": inf_count,
                "verified_inference_count": verified_count,
                "verifier_ready": verifier_ready,
                "verifier_readiness_level": str(readiness.get("level") or ""),
                "verifier_readiness_score": int(readiness.get("score", 0) or 0),
                "verifier_missing_checks": readiness.get("missing_checks", []),
                "active_debt_count": owner_debt_count("route", route_id),
                "blocking_debt_count": owner_debt_count("route", route_id, blocking_only=True),
            }
        )
        add_edge(f"route:{route_id}", f"claim:{route.get('conclusion_claim_id')}", "proves", "strong")

    for inference_id, inf in sorted(inferences.items()):
        add_node(
            {
                "id": f"inference:{inference_id}",
                "kind": "inference",
                "label": inference_id,
                "status": str(inf.get("validation_status") or ""),
                "summary": _short_text(inf.get("explanation"), 260),
                "route_id": str(inf.get("route_id") or ""),
                "conclusion_claim_id": str(inf.get("conclusion_claim_id") or ""),
                "premise_count": len(inf.get("premise_claim_ids") or []),
                "active_debt_count": owner_debt_count("inference", inference_id),
                "blocking_debt_count": owner_debt_count("inference", inference_id, blocking_only=True),
            }
        )
        add_edge(f"route:{inf.get('route_id')}", f"inference:{inference_id}", "has inference")
        add_edge(f"inference:{inference_id}", f"claim:{inf.get('conclusion_claim_id')}", "concludes", "strong")
        for premise_id in inf.get("premise_claim_ids") or []:
            if str(premise_id) in claims:
                add_edge(f"claim:{premise_id}", f"inference:{inference_id}", "premise")
                conclusion_id = str(inf.get("conclusion_claim_id") or "")
                if conclusion_id in claims:
                    add_edge(f"claim:{premise_id}", f"claim:{conclusion_id}", "supports claim", "strong")

    for debt in sorted(debts, key=lambda row: (0 if str(row.get("severity") or "") == "blocking" else 1, str(row.get("debt_id") or "")))[:30]:
        debt_id = str(debt.get("debt_id") or "")
        owner_type = str(debt.get("owner_type") or "")
        owner_id = str(debt.get("owner_id") or "")
        add_node(
            {
                "id": f"debt:{debt_id}",
                "kind": "debt",
                "label": debt_id,
                "status": str(debt.get("severity") or ""),
                "summary": _short_text(debt.get("obligation"), 260),
                "owner_type": owner_type,
                "owner_id": owner_id,
                "debt_type": str(debt.get("debt_type") or ""),
                "repeated_count": int(debt.get("repeated_count") or 0),
            }
        )
        if owner_type in {"claim", "route", "inference"}:
            add_edge(f"{owner_type}:{owner_id}", f"debt:{debt_id}", "blocked by", "blocking")
        suggested = str(debt.get("suggested_next_target") or "")
        if suggested in claims:
            add_edge(f"debt:{debt_id}", f"claim:{suggested}", "next target")

    recent_artifacts = sorted(
        artifacts.values(),
        key=lambda row: (int(row.get("state_revision") or 0), str(row.get("created_at") or "")),
        reverse=True,
    )
    all_artifact_ids = list(dict.fromkeys([*evidence_ids, *(str(row.get("artifact_id") or "") for row in recent_artifacts[:8])]))
    artifact_ids = all_artifact_ids[:24]
    for ref_index, artifact_id in enumerate(artifact_ids, start=1):
        artifact = artifacts.get(artifact_id)
        if not artifact:
            continue
        producer_role = str(artifact.get("producer_role") or "")
        role_code = _producer_role_code(producer_role)
        state_revision = int(artifact.get("state_revision") or 0)
        add_node(
            {
                "id": f"artifact:{artifact_id}",
                "kind": "artifact",
                "label": f"A{ref_index} {role_code}",
                "full_label": artifact_id,
                "artifact_ref": f"A{ref_index}",
                "artifact_ref_index": ref_index,
                "producer_role_code": role_code,
                "status": str(artifact.get("artifact_type") or ""),
                "summary": _short_text(artifact.get("content_summary") or artifact.get("metadata_json"), 220),
                "producer_role": producer_role,
                "state_revision": state_revision,
                "compact": True,
            }
        )

    def link_evidence(owner_kind: str, owner_id: str, raw_ids: Any) -> None:
        for artifact_id in _json_list(raw_ids):
            artifact_node = f"artifact:{artifact_id}"
            if any(node["id"] == artifact_node for node in nodes):
                add_edge(artifact_node, f"{owner_kind}:{owner_id}", "evidence")

    for claim_id, claim in claims.items():
        link_evidence("claim", claim_id, claim.get("evidence_artifact_ids_json"))
    for route_id, route in routes.items():
        link_evidence("route", route_id, route.get("evidence_artifact_ids_json"))
    for inference_id, inf in inferences.items():
        link_evidence("inference", inference_id, inf.get("evidence_artifact_ids_json"))
    for debt in debts:
        link_evidence("debt", str(debt.get("debt_id") or ""), debt.get("source_artifact_ids_json"))

    kind_order = {"claim": 0, "route": 1, "inference": 2, "debt": 3, "artifact": 4}

    def node_sort_key(node: Mapping[str, Any]) -> tuple[int, int, str]:
        kind = str(node.get("kind") or "")
        artifact_index = int(node.get("artifact_ref_index") or 0) if kind == "artifact" else 0
        return (kind_order.get(kind, 99), artifact_index, str(node.get("label") or ""))

    nodes.sort(key=node_sort_key)
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "claim_count": len(claims),
            "route_count": len(routes),
            "inference_count": len(inferences),
            "active_debt_count": len(debts),
            "artifact_node_count": sum(1 for node in nodes if node["kind"] == "artifact"),
            "artifact_node_limit": len(artifact_ids),
            "omitted_artifact_node_count": max(0, len(all_artifact_ids) - len(artifact_ids)),
            "artifact_nodes_compact": True,
            "verifier_ready_route_count": sum(1 for node in nodes if node.get("kind") == "route" and node.get("verifier_ready")),
            "blocking_debt_count": sum(1 for row in debts if str(row.get("severity") or "") == "blocking"),
        },
    }


_LIVE_OVERLAY_KEYS = ("live_logs", "current_invocation")


def build_monitor_payload(store: ProofStateStore) -> Dict[str, Any]:
    """Return the console payload plus monitor metadata (source, live flag).

    The snapshot/budget/claims/routes are always rebuilt fresh from the
    authoritative WAL-mode store (so the budget panel can never go stale or miss
    fields written by an older workflow process). The in-flight session logs and
    live token usage are overlaid from the ``albilich_run_console.json`` the
    running workflow maintains, since those come from its in-memory history.
    """
    state = store.get_state()
    payload = build_run_console_payload(store, state=state)
    source = "store"
    console_json = store.state_dir / "albilich_run_console.json"
    file_payload: Dict[str, Any] | None = None
    if console_json.exists():
        try:
            file_payload = json.loads(console_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            file_payload = None
    if isinstance(file_payload, dict):
        source = "store+console"
        for key in _LIVE_OVERLAY_KEYS:
            value = file_payload.get(key)
            if value:
                payload[key] = value
        live_children = (file_payload.get("usage_summary") or {}).get("active_live_children")
        if isinstance(live_children, dict):
            payload.setdefault("usage_summary", {})["active_live_children"] = live_children
    # All claims (statement only), verified ones marked — the headline output ledger.
    try:
        claims = state.get("claims", [])
        verified_statuses = {"informally_verified", "formally_verified"}
        artifact_target_overrides: dict[str, str] = {}
        try:
            with store.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT p.target_id,
                           json_extract(op.value, '$.artifact_id') AS artifact_id
                    FROM patches p, json_each(p.operations_json) AS op
                    WHERE p.actor_role = 'strict_informal_verifier'
                      AND json_extract(op.value, '$.artifact_type') = 'verification_report'
                    """
                ).fetchall()
            artifact_target_overrides = {
                str(row["artifact_id"] or ""): str(row["target_id"] or "")
                for row in rows
                if str(row["artifact_id"] or "") and str(row["target_id"] or "")
            }
        except Exception:
            artifact_target_overrides = {}
        verification_history = _claim_verification_history(
            state, artifact_target_overrides=artifact_target_overrides
        )
        supersession = supersession_index(state)
        supersession_by_claim = {
            str(row.get("claim_id") or ""): row
            for row in supersession.get("claims", [])
        }
        claim_ids = {str(c.get("claim_id") or "") for c in claims}
        subclaim_of: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
        contains_subclaims: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
        supports_claims: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
        supported_by_claims: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
        for claim in claims:
            claim_id = str(claim.get("claim_id") or "")
            for parent_id in _json_list(claim.get("parent_ids_json")):
                parent_id = str(parent_id or "")
                if parent_id in claim_ids and parent_id != claim_id:
                    subclaim_of[claim_id].add(parent_id)
                    contains_subclaims[parent_id].add(claim_id)
        for inference in state.get("inferences", []):
            conclusion_id = str(inference.get("conclusion_claim_id") or "")
            if conclusion_id not in claim_ids:
                continue
            for premise_id in inference.get("premise_claim_ids") or []:
                premise_id = str(premise_id or "")
                if premise_id in claim_ids and premise_id != conclusion_id:
                    supports_claims[premise_id].add(conclusion_id)
                    supported_by_claims[conclusion_id].add(premise_id)

        def _is_verified(c: Mapping[str, Any]) -> bool:
            return (
                not claim_is_retired(c)
                and (
                    str(c.get("validation_status") or "") in verified_statuses
                    or str(c.get("lifecycle_status") or "") == "integrated"
                )
            )

        rows = []
        for c in claims:
            claim_id = str(c.get("claim_id") or "")
            persisted_status = str(c.get("validation_status") or "")
            lifecycle_status = str(c.get("lifecycle_status") or "")
            report = verification_history.get(claim_id, {})
            superseded = supersession_by_claim.get(claim_id, {})
            display_status = persisted_status
            if lifecycle_status in {"superseded", "abandoned", "blocked"}:
                # Lifecycle retirement takes precedence over stale validation
                # labels such as "untested" in the claims ledger.
                display_status = lifecycle_status
            elif (
                claim_id == "root"
                and lifecycle_status == "active"
                and statement_is_interrogative_problem(str(c.get("statement") or ""))
            ):
                display_status = "active_question"
            elif persisted_status in {"untested", "plausible", "challenged"} and report:
                display_status = "challenged" if report.get("blocking_gap") else "checked_pending_transition"
            rows.append({
                "claim_id": str(c.get("claim_id") or ""),
                "statement": str(c.get("statement") or ""),
                "validation_status": persisted_status,
                "display_validation_status": display_status,
                "lifecycle_status": lifecycle_status,
                "verified": _is_verified(c),
                "retired": claim_is_retired(c),
                "verification_report_count": int(report.get("report_count") or 0),
                "latest_verification_revision": int(report.get("latest_state_revision") or 0),
                "latest_verification_artifact_id": str(report.get("latest_artifact_id") or ""),
                "reduction_depth": int(c.get("reduction_depth") or 0),
                "root_impact": float(c.get("root_impact") or 0.0),
                "subclaim_of_claim_ids": sorted(subclaim_of.get(claim_id, set())),
                "contains_subclaim_ids": sorted(contains_subclaims.get(claim_id, set())),
                "supports_claim_ids": sorted(supports_claims.get(claim_id, set())),
                "supported_by_claim_ids": sorted(supported_by_claims.get(claim_id, set())),
                "superseded_by_claim_ids": sorted(
                    str(item) for item in superseded.get("replacement_claim_ids", []) if str(item)
                ),
                "retirement_reason": str(superseded.get("reason") or ""),
            })
        # Verified first, then the rest; stable within each group.
        rows.sort(key=lambda r: 0 if r["verified"] else 1)
        payload["claims"] = rows
        payload["verified_claim_total"] = sum(1 for r in rows if r["verified"])
    except Exception:
        payload["claims"] = []
        payload["verified_claim_total"] = 0
    try:
        payload["proof_graph"] = _proof_graph_payload(store, state=state)
    except Exception:
        payload["proof_graph"] = {"nodes": [], "edges": [], "summary": {}}
    try:
        scheduler_state = store.get_scheduler_state()
    except Exception:
        scheduler_state = {}
    try:
        payload["bottleneck_frontier"] = bottleneck_frontier_summary(scheduler_state)
    except Exception:
        payload["bottleneck_frontier"] = {}
    try:
        payload["proof_spine_status"] = proof_spine_summary(scheduler_state)
        root_claim = next(
            (claim for claim in state.get("claims", []) if str(claim.get("claim_id") or "") == "root"),
            {},
        )
        if (
            str(root_claim.get("lifecycle_status") or "") == "active"
            and statement_is_interrogative_problem(str(root_claim.get("statement") or ""))
        ):
            payload["proof_spine_status"]["root_status"] = "active_question"
    except Exception:
        payload["proof_spine_status"] = {}
    try:
        payload["research_strategy"] = strategy_observability(scheduler_state)
    except Exception:
        payload["research_strategy"] = {}
    live = _has_live_child(payload)
    # Robust liveness from real write-activity (survives the run process dying: when
    # it exits no new files are written, so this goes stale and the dashboard says
    # STOPPED instead of freezing on the last 'running' log).
    seconds_since_activity, run_state = _run_activity_state(store)
    if live and run_state in {"stalled", "stopped"}:
        run_state = "running"
    elif not live and _has_terminal_invocation(payload):
        run_state = "stopped"
    console_mtime = ""
    if file_payload:
        try:
            console_mtime = datetime.fromtimestamp(console_json.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            console_mtime = ""
    payload["_monitor"] = {
        "served_at": utc_now(),
        "source": source,
        "console_mtime": console_mtime,
        "live": live,
        "seconds_since_activity": seconds_since_activity,
        "run_state": run_state,
        "problem_id": store.problem_id,
        "state_dir": str(store.state_dir),
    }
    return payload


def _has_live_child(payload: Mapping[str, Any]) -> bool:
    for entry in payload.get("live_logs", []) or []:
        if (
            isinstance(entry, dict)
            and str(entry.get("status") or "").lower() in _LIVE_STATUSES
            and _live_update_is_recent(entry)
        ):
            return True
    return False


def _live_update_is_recent(entry: Mapping[str, Any]) -> bool:
    raw = str(entry.get("updated_at") or "").strip()
    if not raw:
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    return age <= _LIVE_TELEMETRY_STALE_SECONDS


def _has_terminal_invocation(payload: Mapping[str, Any]) -> bool:
    """Return true when the live console records a terminal scheduler stop.

    Recent child log mtimes are useful while children are running, but after a
    bounded workflow stop they remain fresh for a few minutes. The terminal
    invocation entry is the authoritative signal that the workflow has stopped.
    """
    entries = payload.get("current_invocation", [])
    if not isinstance(entries, list) or not entries:
        return False
    last = entries[-1]
    if not isinstance(last, Mapping):
        return False
    return bool(last.get("stop_reason") or last.get("terminal_classification"))


def _run_activity_state(store: ProofStateStore) -> tuple[float | None, str]:
    """Return (seconds_since_last_write, run_state) from child workflow files.

    The console JSON is also written by dry-run planning and ordinary dashboard
    refreshes, so it is not enough evidence that a child agent is alive. Use only
    files under ``workflow_runs``: session logs, streamed JSONL progress, and
    final patches. ``run_state`` is idle (no child run yet) / running (<2m) /
    stalled (<10m) / stopped.
    """
    try:
        latest = 0.0
        runs_dir = store.state_dir / "workflow_runs"
        if runs_dir.is_dir():
            run_dirs = [p for p in runs_dir.glob("v1_*") if p.is_dir()]
            newest = max(run_dirs, key=lambda p: p.stat().st_mtime, default=None) if run_dirs else None
            if newest is not None:
                for pattern in ("*.jsonl", "*.log"):
                    files = newest.glob(pattern)
                    for f in files:
                        try:
                            latest = max(latest, f.stat().st_mtime)
                        except OSError:
                            pass
                for f in (newest / "final_patch.json",):
                    try:
                        latest = max(latest, f.stat().st_mtime)
                    except OSError:
                        pass
        if not latest:
            return None, "idle"
        secs = max(0.0, time.time() - latest)
        if secs < 120:
            state = "running"
        elif secs < 600:
            state = "stalled"
        else:
            state = "stopped"
        return secs, state
    except Exception:
        return None, "unknown"


def _inspectable_files(store: ProofStateStore) -> list[Dict[str, Any]]:
    """Curated list of files the dashboard can stream the tail of."""
    state = store.state_dir
    entries: list[Dict[str, Any]] = []

    def add(path: Path, label: str, kind: str) -> None:
        try:
            if path.is_file():
                st = path.stat()
                entries.append(
                    {
                        "path": str(path.relative_to(state)),
                        "label": label,
                        "kind": kind,
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                    }
                )
        except (OSError, ValueError):
            pass

    add(state / "albilich_run_console.md", "Run console (markdown)", "report")
    add(state / "phase2_report.md", "Phase2 report", "report")
    # Newest workflow-run logs first.
    run_dirs = sorted(
        (p for p in (state / "workflow_runs").glob("*") if p.is_dir()),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )[:6]
    for d in run_dirs:
        tag = d.name.replace("v1_", "")
        for fname, kind in (("claude_output.jsonl", "stream"), ("claude.log", "log"), ("codex.log", "log"), ("final_patch.json", "patch")):
            add(d / fname, f"{tag} · {fname}", kind)
    # Newest artifacts.
    arts = sorted(
        (p for p in (state / "artifacts").glob("*") if p.is_file()),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )[:12]
    for a in arts:
        add(a, f"artifact · {a.name}", "artifact")
    return entries


def _safe_tail(store: ProofStateStore, rel_path: str, max_bytes: int) -> Dict[str, Any]:
    """Return the tail of a file, restricted to within the run state dir."""
    state = store.state_dir.resolve()
    target = (store.state_dir / rel_path).resolve()
    if state not in target.parents and target != state:
        return {"error": "path outside run directory", "text": ""}
    if not target.is_file():
        return {"error": "not a file", "text": ""}
    max_bytes = max(1_000, min(int(max_bytes or 40_000), 400_000))
    try:
        size = target.stat().st_size
        with target.open("rb") as fh:
            if size > max_bytes:
                fh.seek(-max_bytes, os.SEEK_END)
            data = fh.read()
        return {"path": rel_path, "size": size, "truncated": size > max_bytes, "text": data.decode("utf-8", errors="replace")}
    except OSError as exc:
        return {"error": str(exc), "text": ""}


def _make_handler(store: ProofStateStore, poll_ms: int):
    index_html = INDEX_HTML.replace("__POLL_MS__", str(poll_ms)).replace(
        "__PROBLEM_ID__", _html_escape(store.problem_id)
    )
    # Building the full console payload is intentionally authoritative but can
    # take a couple of seconds for a long run. Multiple open dashboard tabs used
    # to start overlapping rebuilds every poll, saturating the monitor and
    # leaving every tab on "Connecting…". Serialize rebuilds and share one
    # short-lived JSON body across clients.
    console_cache_lock = threading.Lock()
    console_cache_body = b""
    console_cache_at = 0.0
    console_refreshing = False
    # A full authoritative rebuild is CPU-heavy on mature proof databases.
    # The page may poll more frequently, but proof-state panels only need a
    # rebuild every few polls; live tails remain available through /api/tail.
    console_cache_ttl = _monitor_refresh_interval_seconds(poll_ms)

    def _persisted_console_body() -> bytes:
        """Cheap initial response while the authoritative rebuild runs."""

        path = store.state_dir / "albilich_run_console.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return b""
        if not isinstance(payload, dict):
            return b""
        live = _has_live_child(payload)
        seconds_since_activity, run_state = _run_activity_state(store)
        if live and run_state in {"stalled", "stopped"}:
            run_state = "running"
        try:
            console_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            console_mtime = ""
        payload["_monitor"] = {
            "served_at": utc_now(),
            "source": "console-fallback",
            "console_mtime": console_mtime,
            "live": live,
            "seconds_since_activity": seconds_since_activity,
            "run_state": run_state,
            "problem_id": store.problem_id,
            "state_dir": str(store.state_dir),
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def _refresh_console_body() -> None:
        nonlocal console_cache_body, console_cache_at, console_refreshing
        try:
            payload = build_monitor_payload(store)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            with console_cache_lock:
                console_cache_body = body
                console_cache_at = time.monotonic()
        except Exception:
            # Keep serving the last valid body; the next poll will retry.
            pass
        finally:
            with console_cache_lock:
                console_refreshing = False

    def _console_body() -> bytes:
        nonlocal console_cache_body, console_cache_at, console_refreshing
        start_refresh = False
        with console_cache_lock:
            now = time.monotonic()
            if console_cache_body and now - console_cache_at < console_cache_ttl:
                return console_cache_body
            if not console_cache_body:
                console_cache_body = _persisted_console_body()
                console_cache_at = now
            if console_cache_body:
                if not console_refreshing:
                    console_refreshing = True
                    start_refresh = True
                body = console_cache_body
            else:
                # Fresh stores used by tests and first-run dashboards have no
                # persisted console yet; one synchronous build is unavoidable.
                payload = build_monitor_payload(store)
                console_cache_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                console_cache_at = time.monotonic()
                return console_cache_body
        if start_refresh:
            threading.Thread(
                target=_refresh_console_body,
                name=f"albilich-monitor-refresh-{store.problem_id}",
                daemon=True,
            ).start()
        return body

    class Handler(BaseHTTPRequestHandler):
        # Silence default stderr request logging; keep the console clean.
        def log_message(self, *args: Any) -> None:  # noqa: D401, N802
            return

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            try:
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # A polling tab can disappear while an authoritative payload is
                # being built. That is a normal client disconnect, not a server
                # error and must not trigger a second attempted response.
                return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                self._send(200, index_html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/healthz":
                self._send(200, b'{"ok":true}', "application/json")
                return
            if path == "/api/files":
                body = json.dumps({"files": _inspectable_files(store)}, ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if path == "/api/tail":
                qs = parse_qs(parsed.query)
                rel = (qs.get("path") or [""])[0]
                nbytes = (qs.get("bytes") or ["40000"])[0]
                try:
                    nbytes_i = int(nbytes)
                except ValueError:
                    nbytes_i = 40_000
                body = json.dumps(_safe_tail(store, rel, nbytes_i), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if path == "/api/steering":
                try:
                    body = json.dumps(steering.snapshot(store.state_dir), ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:  # pragma: no cover - defensive
                    self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")
                return
            if path == "/api/console":
                try:
                    body = _console_body()
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:  # pragma: no cover - defensive
                    err = json.dumps({"error": str(exc)}).encode("utf-8")
                    self._send(500, err, "application/json")
                return
            if path == "/api/proof-graph":
                try:
                    body = json.dumps(_proof_graph_payload(store), ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:  # pragma: no cover - defensive
                    err = json.dumps({"error": str(exc)}).encode("utf-8")
                    self._send(500, err, "application/json")
                return
            self._send(404, b'{"error":"not found"}', "application/json")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/steer":
                self._send(404, b'{"error":"not found"}', "application/json")
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length > 0 else b"{}"
                data = json.loads(raw.decode("utf-8") or "{}")
                text = str(data.get("text") or "").strip()
                blocker_id = data.get("blocker_id") or None
                if not text:
                    self._send(400, b'{"error":"empty steering text"}', "application/json")
                    return
                msg = steering.submit_steering(store.state_dir, text, blocker_id=blocker_id)
                self._send(200, json.dumps({"ok": True, "message": msg}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            except Exception as exc:  # pragma: no cover - defensive
                self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")

    return Handler


@dataclass
class BackgroundMonitor:
    store: ProofStateStore
    httpd: ThreadingHTTPServer
    thread: threading.Thread
    url: str
    host: str
    port: int

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2.0)


def start_background_monitor(
    store: ProofStateStore,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    poll_ms: int = 3000,
    open_browser: bool = True,
) -> BackgroundMonitor:
    handler = _make_handler(store, poll_ms)
    httpd = _bind_server(host, port, handler, port_search_limit=50)
    actual_host, actual_port = httpd.server_address[:2]
    display_host = host or str(actual_host)
    if display_host == "0.0.0.0":
        display_host = "127.0.0.1"
    url = f"http://{display_host}:{actual_port}/"
    thread = threading.Thread(target=httpd.serve_forever, name=f"albilich-monitor-{store.problem_id}", daemon=True)
    thread.start()
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    return BackgroundMonitor(store=store, httpd=httpd, thread=thread, url=url, host=display_host, port=int(actual_port))


def serve(
    store: ProofStateStore,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    poll_ms: int = 3000,
    open_browser: bool = True,
) -> None:
    monitor = start_background_monitor(store, host=host, port=port, poll_ms=poll_ms, open_browser=open_browser)
    print(f"Albilich monitor for '{store.problem_id}' on {monitor.url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        while monitor.thread.is_alive():
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping monitor.")
    finally:
        monitor.stop()


def _bind_server(
    host: str,
    port: int,
    handler: type[BaseHTTPRequestHandler],
    *,
    port_search_limit: int,
) -> ThreadingHTTPServer:
    last_error: OSError | None = None
    candidate_ports = [port] if port == 0 else range(port, port + max(1, port_search_limit))
    for candidate_port in candidate_ports:
        try:
            return ThreadingHTTPServer((host, candidate_port), handler)
        except OSError as exc:
            last_error = exc
            if port == 0 or exc.errno not in {errno.EADDRINUSE, 48, 98}:
                raise
    assert last_error is not None
    raise last_error


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Albilich Monitor · __PROBLEM_ID__</title>
<!-- No external font fetch: the dashboard must render fully offline; the CSS
     font stacks fall back to high-quality system fonts. -->
<style>
  /* ===== UW Math AI Lab palette: purple #4b2e83 + gold #b7a57a ===== */
  :root {
    --uw-purple: #4b2e83;
    --uw-purple-2: #6a48b4;
    --uw-gold: #b7a57a;
    --uw-gold-deep: #85754d;
    --good: #1f8b5f;
    --warn: #b07d12;
    --bad: #c0392b;
    --info: var(--uw-purple);
    --sans: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    --mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    --radius: 16px;
    --radius-sm: 10px;
  }
  /* Light (default, like the lab site 7am–7pm) */
  :root, [data-theme="light"] {
    --bg: #f4f2f8;
    --bg-accent: linear-gradient(180deg, #efeaf7 0%, #f4f2f8 240px);
    --surface: #ffffff;
    --surface-2: #faf9fc;
    --border: #e7e3f0;
    --border-strong: #d7d1e6;
    --text: #20203a;
    --muted: #5d5b78;
    --faint: #8f8ca6;
    --brand-fg: var(--uw-purple);
    --accent: var(--uw-purple);
    --accent-soft: rgba(75,46,131,.08);
    --shadow: 0 1px 2px rgba(31,28,60,.04), 0 8px 24px rgba(75,46,131,.07);
    --shadow-sm: 0 1px 2px rgba(31,28,60,.05);
    --log-bg: #faf9fc;
    --log-fg: #3b3850;
    --track: #ece8f5;
  }
  [data-theme="dark"] {
    --bg: #141019;
    --bg-accent: radial-gradient(1100px 520px at 82% -8%, #2a1d44 0%, #141019 60%);
    --surface: #1d1830;
    --surface-2: #191428;
    --border: #2d2543;
    --border-strong: #3a3056;
    --text: #ece9f6;
    --muted: #a99fc4;
    --faint: #786f93;
    --brand-fg: #c9b6f5;
    --accent: #b9a3ee;
    --accent-soft: rgba(185,163,238,.12);
    --shadow: 0 10px 34px rgba(0,0,0,.42);
    --shadow-sm: 0 2px 10px rgba(0,0,0,.3);
    --log-bg: #100c1a;
    --log-fg: #d6cfe8;
    --track: #100c1a;
    --uw-purple: #9b7fdc;
    --good: #46cf99;
    --warn: #e0b455;
    --bad: #f0796f;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; }
  body {
    background: var(--bg-accent), var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px; line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    transition: background .4s ease, color .25s ease;
  }
  a { color: var(--accent); text-decoration: none; }
  .wrap { max-width: 1480px; margin: 0 auto; padding: 0 26px 72px; }

  /* ===== Header ===== */
  header.topbar {
    position: sticky; top: 0; z-index: 30;
    display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
    padding: 15px 26px; margin: 0 -26px 22px;
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    backdrop-filter: saturate(140%) blur(12px);
    border-bottom: 1px solid var(--border);
  }
  .brand { display: flex; align-items: center; gap: 12px; }
  .mark {
    width: 34px; height: 34px; border-radius: 9px; flex: none;
    background: linear-gradient(135deg, var(--uw-purple) 0%, var(--uw-purple-2) 60%, var(--uw-gold) 160%);
    display: grid; place-items: center; color: #fff; font-weight: 800; font-size: 17px;
    box-shadow: 0 4px 14px rgba(75,46,131,.32); letter-spacing: -.5px;
  }
  .brand .titles { display: flex; flex-direction: column; line-height: 1.15; }
  .brand .lab { font-weight: 700; font-size: 15px; letter-spacing: -.2px; }
  .brand .lab .dot { color: var(--uw-gold-deep); }
  .brand .pid { font-family: var(--mono); color: var(--muted); font-size: 11.5px; max-width: 52ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .spacer { flex: 1 1 auto; }
  .ctl { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
  .live { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--muted); font-family: var(--mono); }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--faint); }
  .dot.on { background: var(--good); animation: pulse 1.7s infinite; }
  @keyframes pulse { 0%{box-shadow:0 0 0 0 color-mix(in srgb, var(--good) 60%, transparent);} 70%{box-shadow:0 0 0 9px transparent;} 100%{box-shadow:0 0 0 0 transparent;} }
  .btn {
    font: inherit; font-size: 12px; font-weight: 500; color: var(--text);
    background: var(--surface); border: 1px solid var(--border-strong); border-radius: 9px;
    padding: 7px 12px; cursor: pointer; transition: all .15s; display: inline-flex; align-items: center; gap: 6px;
  }
  .btn:hover { border-color: var(--accent); color: var(--accent); }
  .btn.primary { color: #fff; background: var(--uw-purple); border-color: var(--uw-purple); }
  [data-theme="dark"] .btn.primary { color: #1a1330; }
  .updated { font-size: 11px; color: var(--faint); font-family: var(--mono); min-width: 92px; }

  .badge {
    display: inline-flex; align-items: center; gap: 6px;
    font-family: var(--mono); font-size: 11px; font-weight: 600; letter-spacing: .2px;
    padding: 5px 11px; border-radius: 999px; border: 1px solid transparent; text-transform: lowercase;
  }
  .badge.good { color: var(--good); background: color-mix(in srgb, var(--good) 13%, transparent); border-color: color-mix(in srgb, var(--good) 32%, transparent); }
  .badge.warn { color: var(--warn); background: color-mix(in srgb, var(--warn) 14%, transparent); border-color: color-mix(in srgb, var(--warn) 32%, transparent); }
  .badge.bad  { color: var(--bad);  background: color-mix(in srgb, var(--bad) 13%, transparent);  border-color: color-mix(in srgb, var(--bad) 32%, transparent); }
  .badge.info { color: var(--uw-purple); background: var(--accent-soft); border-color: color-mix(in srgb, var(--uw-purple) 30%, transparent); }
  .badge.mut  { color: var(--muted); background: color-mix(in srgb, var(--muted) 12%, transparent); border-color: var(--border-strong); }

  /* ===== Big run-status banner: unmistakable RUNNING / STALLED / STOPPED ===== */
  .runbar { display: flex; align-items: center; gap: 13px; padding: 15px 20px; margin: 0 0 18px; border-radius: 14px; font-size: 17px; font-weight: 800; letter-spacing: -.2px; border: 1px solid var(--border); background: var(--surface); box-shadow: var(--shadow-sm); transition: background .3s, color .3s, border-color .3s; }
  .runbar .rdot { width: 15px; height: 15px; border-radius: 50%; flex: none; background: var(--faint); }
  .runbar .rsub { margin-left: auto; font-weight: 500; font-size: 13px; font-family: var(--mono); color: var(--muted); letter-spacing: 0; }
  .runbar.running { color: var(--good); background: color-mix(in srgb, var(--good) 12%, var(--surface)); border-color: color-mix(in srgb, var(--good) 38%, transparent); }
  .runbar.running .rdot { background: var(--good); box-shadow: 0 0 0 0 color-mix(in srgb, var(--good) 60%, transparent); animation: pulse 1.5s infinite; }
  .runbar.stalled { color: var(--warn); background: color-mix(in srgb, var(--warn) 14%, var(--surface)); border-color: color-mix(in srgb, var(--warn) 45%, transparent); }
  .runbar.stalled .rdot { background: var(--warn); animation: pulse 2.4s infinite; }
  .runbar.stopped { color: var(--bad); background: color-mix(in srgb, var(--bad) 14%, var(--surface)); border-color: color-mix(in srgb, var(--bad) 50%, transparent); }
  .runbar.stopped .rdot { background: var(--bad); }
  .runbar.disconnected { color: var(--bad); background: color-mix(in srgb, var(--bad) 10%, var(--surface)); border-color: color-mix(in srgb, var(--bad) 40%, transparent); }
  .runbar.disconnected .rdot { background: var(--bad); }

  /* ===== KPI band ===== */
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap: 16px; margin-bottom: 18px; }
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; box-shadow: var(--shadow-sm); }
  .kpi .label { font-size: 10.5px; text-transform: uppercase; letter-spacing: .8px; color: var(--faint); margin-bottom: 9px; font-weight: 600; }
  .kpi .value { font-size: 27px; font-weight: 700; line-height: 1.05; letter-spacing: -.5px; }
  .kpi .value small { font-size: 15px; font-weight: 500; color: var(--muted); letter-spacing: 0; }
  .kpi .sub { font-size: 11.5px; color: var(--muted); margin-top: 7px; font-family: var(--mono); }
  .bar { height: 8px; border-radius: 6px; background: var(--track); margin-top: 11px; overflow: hidden; }
  .bar > i { display: block; height: 100%; background: linear-gradient(90deg, var(--uw-purple), var(--uw-gold)); border-radius: 6px; transition: width .5s cubic-bezier(.4,0,.2,1); }

  /* ===== Token panel ===== */
  .tokens { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); padding: 20px 22px; margin-bottom: 20px; }
  .tokens .top { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; flex-wrap: wrap; }
  .tokens .lead { font-size: 11px; text-transform: uppercase; letter-spacing: .8px; color: var(--faint); font-weight: 600; margin-bottom: 6px; }
  .tokens .big { font-size: 34px; font-weight: 800; letter-spacing: -1px; line-height: 1; }
  .tokens .big small { font-size: 17px; font-weight: 500; color: var(--muted); letter-spacing: 0; }
  .tokens .pctchip { font-family: var(--mono); font-size: 12px; color: var(--uw-purple); background: var(--accent-soft); padding: 6px 12px; border-radius: 999px; font-weight: 600; }
  .tokens .bigbar { height: 14px; border-radius: 8px; background: var(--track); margin: 16px 0 4px; overflow: hidden; position: relative; display: flex; }
  .tokens .bigbar > i { display: block; height: 100%; transition: width .6s cubic-bezier(.4,0,.2,1); }
  .tokens .bigbar > i.spent { background: linear-gradient(90deg, var(--uw-purple) 0%, var(--uw-purple-2) 55%, var(--uw-gold) 100%); border-radius: 8px 0 0 8px; }
  .tokens .bigbar > i.inflight { background: repeating-linear-gradient(45deg, color-mix(in srgb, var(--uw-gold) 78%, #fff) 0 7px, color-mix(in srgb, var(--uw-gold) 38%, transparent) 7px 14px); animation: shift 1.1s linear infinite; }
  @keyframes shift { from { background-position: 0 0; } to { background-position: 28px 0; } }
  .tokens .inflight-tag { font-family: var(--mono); font-size: 12px; color: var(--uw-gold-deep); background: color-mix(in srgb, var(--uw-gold) 18%, transparent); padding: 6px 12px; border-radius: 999px; font-weight: 600; }
  [data-theme="dark"] .tokens .inflight-tag { color: var(--uw-gold); }
  .tokens .scale { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 10.5px; color: var(--faint); }
  .chips { display: grid; grid-template-columns: repeat(auto-fit, minmax(118px,1fr)); gap: 12px; margin-top: 18px; }
  .chip { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 11px 13px; }
  .chip .k { font-size: 10px; text-transform: uppercase; letter-spacing: .6px; color: var(--faint); font-weight: 600; }
  .chip .v { font-size: 18px; font-weight: 700; margin-top: 4px; font-family: var(--mono); letter-spacing: -.3px; }
  .chip .v.accent { color: var(--uw-purple); }

  /* ===== Pipeline flowchart ===== */
  .flow { display: flex; flex-direction: column; align-items: center; gap: 10px; }
  .conn { color: var(--faint); font-size: 16px; line-height: 1; }
  .flowrow { display: grid; grid-template-columns: repeat(auto-fit, minmax(132px,1fr)); gap: 11px; width: 100%; }
  .node { position: relative; border: 1px solid var(--border); border-radius: 12px; padding: 12px 13px; background: var(--surface-2); text-align: center; transition: box-shadow .3s, border-color .3s, background .3s; }
  .node .nl { font-weight: 700; font-size: 12.5px; letter-spacing: -.1px; }
  .node .nm { font-size: 10px; color: var(--muted); font-family: var(--mono); margin-top: 4px; line-height: 1.4; }
  .node .nowtag { position: absolute; top: -9px; left: 50%; transform: translateX(-50%); background: var(--uw-purple); color: #fff; font-size: 9px; font-weight: 700; padding: 2px 8px; border-radius: 999px; letter-spacing: .4px; display: none; white-space: nowrap; }
  [data-theme="dark"] .node .nowtag { color: #1a1330; }
  .node.active { border-color: var(--uw-purple); background: var(--accent-soft); box-shadow: 0 0 0 3px color-mix(in srgb, var(--uw-purple) 20%, transparent); }
  .node.active .nl { color: var(--uw-purple); }
  .node.active .nowtag { display: inline-block; }
  .node.active::after { content: ""; position: absolute; right: 9px; top: 9px; width: 7px; height: 7px; border-radius: 50%; background: var(--good); animation: pulse 1.7s infinite; }
  .hub { min-width: 220px; border: none; color: #fff; background: linear-gradient(135deg, var(--uw-purple) 0%, var(--uw-purple-2) 70%, var(--uw-gold) 170%); box-shadow: 0 6px 18px rgba(75,46,131,.3); }
  .hub .nl, .hub.active .nl { color: #fff; } .hub .nm { color: rgba(255,255,255,.82); }
  .hub.active { box-shadow: 0 6px 18px rgba(75,46,131,.3), 0 0 0 3px color-mix(in srgb, var(--uw-gold) 55%, transparent); }
  .nodecat { display: inline-block; width: 8px; height: 8px; border-radius: 3px; margin-right: 6px; vertical-align: middle; }
  .cat-lit{background:#3aa0c9} .cat-res{background:var(--uw-purple)} .cat-vil{background:var(--bad)} .cat-ver{background:var(--good)} .cat-int{background:var(--uw-gold-deep)} .cat-adv{background:var(--warn)} .cat-wri{background:#8a7bc8}
  .pipenow { font-family: var(--mono); font-size: 11px; }

  /* ===== Live tail viewer ===== */
  .tailbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 11px; }
  select.tailsel { font: inherit; font-size: 12px; font-family: var(--mono); color: var(--text); background: var(--surface); border: 1px solid var(--border-strong); border-radius: 9px; padding: 7px 11px; max-width: 60ch; cursor: pointer; }
  select.tailsel:hover { border-color: var(--accent); }
  .checklabel { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); font-family: var(--mono); cursor: pointer; }
  .tailmeta { font-family: var(--mono); font-size: 11px; color: var(--faint); margin-left: auto; }
  .tailview { background: var(--log-bg); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 13px 15px; font-family: var(--mono); font-size: 12px; line-height: 1.5; color: var(--log-fg); white-space: pre-wrap; word-break: break-word; height: 380px; overflow: auto; }
  .tailview::-webkit-scrollbar { width: 10px; } .tailview::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 8px; }

  /* ===== Cards / grid ===== */
  .grid { display: grid; grid-template-columns: 1.55fr 1fr; gap: 20px; align-items: start; }
  @media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
  .grid > *, .card, .card .body { min-width: 0; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-sm); margin-bottom: 20px; overflow: hidden; }
  .card > h2 { margin: 0; padding: 15px 18px; font-size: 12px; letter-spacing: .6px; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 9px; font-weight: 700; }
  .card > h2::before { content: ""; width: 7px; height: 7px; border-radius: 2px; background: var(--uw-gold); }
  .card > h2 .count { margin-left: auto; font-family: var(--mono); font-size: 11px; color: var(--faint); text-transform: none; font-weight: 500; }
  .card .body { padding: 16px 18px; }
  .card .body.tight { padding: 8px 10px; }
  /* Cap tall list/table panels so neither column dominates; scroll within. */
  .card .body.cap { max-height: 360px; overflow: auto; }
  .card .body.cap::-webkit-scrollbar { width: 9px; } .card .body.cap::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 8px; }
  .empty { color: var(--faint); font-style: italic; padding: 10px 6px; }
  /* Brought-up "Current Session" card + its always-on live agent stream */
  .card.now { border-color: color-mix(in srgb, var(--uw-purple) 42%, var(--border)); box-shadow: 0 0 0 1px color-mix(in srgb, var(--uw-purple) 22%, transparent), var(--shadow); }
  .card.now > h2 { color: var(--uw-purple); background: var(--accent-soft); }
  .card.now > h2::before { background: var(--uw-purple); }
  .livestream { min-height: 130px; max-height: 440px; margin-top: 12px; }
  /* Human steering panel */
  .card.steer { border-color: color-mix(in srgb, var(--uw-gold-deep) 40%, var(--border)); }
  .card.steer > h2 { color: var(--uw-gold-deep); }
  .card.steer > h2::before { background: var(--uw-gold); }
  [data-theme="dark"] .card.steer > h2 { color: var(--uw-gold); }
  .blocker { border: 1px solid color-mix(in srgb, var(--warn) 40%, var(--border)); border-left: 3px solid var(--warn); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--warn) 7%, var(--surface-2)); padding: 11px 13px; margin-bottom: 10px; }
  .blocker .bhead { font-weight: 600; font-size: 13px; color: var(--text); }
  .blocker .bdetail { font-size: 12px; color: var(--muted); margin-top: 5px; line-height: 1.5; }
  .blocker .bopts { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 9px; }
  .btn.chiplike { font-size: 11px; padding: 5px 10px; border-radius: 999px; }
  .steerform { margin-top: 6px; }
  .steerinput { width: 100%; font: inherit; font-size: 13px; color: var(--text); background: var(--surface-2); border: 1px solid var(--border-strong); border-radius: var(--radius-sm); padding: 10px 12px; resize: vertical; box-sizing: border-box; }
  .steerinput:focus { outline: none; border-color: var(--accent); }
  .steeractions { display: flex; align-items: center; gap: 9px; margin-top: 8px; flex-wrap: wrap; }

  /* Claim tree */
  .claim-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-bottom: 16px; padding: 9px 11px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); }
  .claim-legend .label { color: var(--faint); font-size: 10px; font-weight: 700; letter-spacing: .7px; text-transform: uppercase; margin-right: 2px; }
  .claim-section + .claim-section { margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--border); }
  .claim-section-title { display: flex; align-items: center; gap: 9px; margin: 0 0 12px; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .65px; text-transform: uppercase; }
  .claim-section-title::before { content: ""; width: 8px; height: 8px; border-radius: 3px; background: var(--uw-purple); }
  .claim-section.retired .claim-section-title::before { background: var(--muted); }
  .claim-section-title .count { margin-left: auto; color: var(--faint); font-family: var(--mono); font-size: 10px; font-weight: 500; letter-spacing: 0; text-transform: none; }
  .claim-tree-node { position: relative; }
  .claim-tree-children { position: relative; margin: -2px 0 11px 20px; padding-left: 18px; border-left: 1px solid color-mix(in srgb, var(--uw-purple) 32%, var(--border)); }
  .claim-tree-children > .claim-tree-node::before { content: ""; position: absolute; top: 22px; left: -18px; width: 13px; border-top: 1px solid color-mix(in srgb, var(--uw-purple) 32%, var(--border)); }
  .claim-tree-children .claim-tree-children { margin-left: 14px; padding-left: 16px; }
  .retired-claims { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 10px; }
  .retired-claims .vclaim { margin-bottom: 0; }
  @media (max-width: 720px) {
    .claim-tree-children, .claim-tree-children .claim-tree-children { margin-left: 8px; padding-left: 12px; }
    .claim-tree-children > .claim-tree-node::before { left: -12px; width: 9px; }
    .retired-claims { grid-template-columns: 1fr; }
  }
  .vclaim { border: 1px solid var(--border); border-left: 4px solid var(--border-strong); border-radius: var(--radius-sm); background: var(--surface-2); padding: 12px 15px; margin-bottom: 11px; box-shadow: 0 1px 0 color-mix(in srgb, var(--border) 65%, transparent); }
  .vclaim.status-integrated, .vclaim.status-verified { border-left-color: var(--good); background: color-mix(in srgb, var(--good) 4%, var(--surface-2)); }
  .vclaim.status-active { border-left-color: var(--uw-purple); background: color-mix(in srgb, var(--uw-purple) 7%, var(--surface-2)); }
  .vclaim.status-plausible { border-left-color: var(--warn); background: color-mix(in srgb, var(--warn) 9%, var(--surface-2)); }
  .vclaim.status-challenged, .vclaim.status-blocked { border-left-color: var(--bad); background: color-mix(in srgb, var(--bad) 7%, var(--surface-2)); }
  .vclaim.status-superseded, .vclaim.status-abandoned { border-left-color: var(--muted); background: color-mix(in srgb, var(--muted) 7%, var(--surface-2)); opacity: .88; }
  .vclaim.status-refuted { border-left-color: var(--bad); background: color-mix(in srgb, var(--bad) 11%, var(--surface-2)); }
  .vclaim.status-superseded .vstmt, .vclaim.status-abandoned .vstmt { color: var(--muted); }
  .vclaim:last-child { margin-bottom: 0; }
  .vclaim .vhead { display: flex; align-items: center; gap: 9px; margin-bottom: 7px; flex-wrap: wrap; }
  .vclaim .vstmt { font-size: 13.5px; line-height: 1.55; color: var(--text); white-space: pre-wrap; word-break: break-word; }
  .vclaim .vrel { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
  .vclaim .vrel .pill { max-width: min(100%, 560px); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .badge.plausible { color: var(--warn); background: color-mix(in srgb, var(--warn) 15%, transparent); border-color: color-mix(in srgb, var(--warn) 38%, transparent); }
  .badge.active { color: var(--uw-purple); background: var(--accent-soft); border-color: color-mix(in srgb, var(--uw-purple) 38%, transparent); }
  .badge.superseded { color: var(--muted); background: color-mix(in srgb, var(--muted) 14%, transparent); border-color: var(--border-strong); }
  .integration-health { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; padding: 8px 10px; border-bottom: 1px solid var(--border); background: var(--surface-2); font-size: 11px; color: var(--muted); }
  .badge.integrated { color: #fff; background: var(--good); border-color: var(--good); }
  [data-theme="dark"] .badge.integrated { color: #08130d; }

  .sessmeta { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; }
  .sessmeta .pair { font-size: 12.5px; color: var(--muted); }
  .sessmeta .pair b { color: var(--text); font-weight: 600; }
  .summary { color: var(--muted); font-size: 12.5px; margin-top: 4px; }
  .session-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin-bottom: 12px; }
  .session-card {
    appearance: none; width: 100%; text-align: left; cursor: pointer;
    background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 10px 12px; min-height: 92px;
    transition: border-color .15s, box-shadow .15s, background .15s;
  }
  .session-card:hover { border-color: var(--accent); }
  .session-card.selected { border-color: var(--uw-purple); background: var(--accent-soft); box-shadow: 0 0 0 2px color-mix(in srgb, var(--uw-purple) 18%, transparent); }
  .session-card.running { border-left: 3px solid var(--good); }
  .session-card.completed { border-left: 3px solid var(--uw-gold); }
  .session-card.failed, .session-card.timeout, .session-card.patch_rejected { border-left: 3px solid var(--bad); }
  .session-card .s-top { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; margin-bottom: 7px; }
  .session-card .s-role { font-weight: 700; font-size: 12.5px; color: var(--text); }
  .session-card .s-mode { font-family: var(--mono); color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }
  .session-card .s-metrics { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; font-family: var(--mono); font-size: 10.5px; color: var(--faint); }
  .session-card .s-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--faint); flex: none; }
  .session-card.running .s-dot { background: var(--good); animation: pulse 1.7s infinite; }
  .idle-banner { font-family: var(--mono); font-size: 11px; color: var(--muted); background: color-mix(in srgb, var(--uw-gold) 12%, transparent); border: 1px dashed color-mix(in srgb, var(--uw-gold-deep) 45%, transparent); border-radius: 8px; padding: 7px 11px; margin-bottom: 11px; }
  [data-theme="dark"] .idle-banner { color: var(--uw-gold); }
  .log { background: var(--log-bg); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; font-family: var(--mono); font-size: 12px; color: var(--log-fg); white-space: pre-wrap; word-break: break-word; max-height: 320px; overflow: auto; margin-top: 6px; }
  .log::-webkit-scrollbar { width: 9px; } .log::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 8px; }

  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th, td { text-align: left; padding: 9px 11px; border-bottom: 1px solid var(--border); vertical-align: top; }
  th { font-size: 10px; text-transform: uppercase; letter-spacing: .6px; color: var(--faint); position: sticky; top: 0; background: var(--surface); font-weight: 700; }
  tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: var(--surface-2); }
  td.num, th.num { text-align: right; font-family: var(--mono); }
  .mono { font-family: var(--mono); }
  .mid { color: var(--accent); font-family: var(--mono); font-size: 11.5px; overflow-wrap: anywhere; word-break: break-word; }
  .pill { font-family: var(--mono); font-size: 10.5px; padding: 3px 8px; border-radius: 7px; background: color-mix(in srgb, var(--muted) 11%, transparent); border: 1px solid var(--border-strong); color: var(--muted); white-space: nowrap; }
  .pill.good { color: var(--good); border-color: color-mix(in srgb, var(--good) 34%, transparent); background: color-mix(in srgb, var(--good) 10%, transparent); }
  .pill.warn { color: var(--warn); border-color: color-mix(in srgb, var(--warn) 34%, transparent); background: color-mix(in srgb, var(--warn) 10%, transparent); }
  .pill.bad  { color: var(--bad);  border-color: color-mix(in srgb, var(--bad) 34%, transparent);  background: color-mix(in srgb, var(--bad) 10%, transparent); }
  .pill.info { color: var(--uw-purple); border-color: color-mix(in srgb, var(--uw-purple) 34%, transparent); background: var(--accent-soft); }

  .debt { padding: 11px 13px; border: 1px solid var(--border); border-radius: var(--radius-sm); margin-bottom: 10px; background: var(--surface-2); }
  .debt .head { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; flex-wrap: wrap; }
  .debt .oblig { font-size: 12px; color: var(--muted); line-height: 1.5; overflow-wrap: anywhere; word-break: break-word; }
  .debt.blocking { border-left: 3px solid var(--bad); }
  .group-h { font-size: 10.5px; text-transform: uppercase; letter-spacing: .6px; color: var(--faint); margin: 8px 0 8px; font-weight: 600; }

  .bottleneck-panel { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, .9fr); gap: 14px; align-items: stretch; }
  .bottleneck-main, .bottleneck-side { border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); padding: 13px 15px; min-width: 0; }
  .bottleneck-title { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
  .bottleneck-title b { font-size: 13.5px; overflow-wrap: anywhere; }
  .bottleneck-obligation { color: var(--muted); line-height: 1.5; font-size: 12.5px; white-space: pre-wrap; overflow-wrap: anywhere; }
  .bottleneck-metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .bmetric { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 9px 10px; background: var(--surface); min-width: 0; }
  .bmetric .bk { color: var(--faint); font-size: 10px; text-transform: uppercase; letter-spacing: .5px; }
  .bmetric .bv { font-family: var(--mono); font-size: 16px; margin-top: 4px; color: var(--text); overflow-wrap: anywhere; }
  .bottleneck-list { margin-top: 10px; display: grid; gap: 7px; }
  .bmini { font-family: var(--mono); font-size: 11px; color: var(--muted); overflow-wrap: anywhere; }
  .spine-panel { display: grid; grid-template-columns: minmax(0, 1fr) minmax(240px, .72fr); gap: 14px; align-items: stretch; }
  .spine-main, .spine-side { border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); padding: 13px 15px; min-width: 0; }
  .spine-list { display: grid; gap: 7px; margin-top: 10px; }
  .spine-item { border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); padding: 8px 10px; font-size: 12px; color: var(--muted); overflow-wrap: anywhere; }
  .spine-item b { color: var(--text); font-size: 12.5px; }
  .spine-rule { color: var(--muted); line-height: 1.5; font-size: 12.5px; margin-top: 8px; }

  .sig { display: grid; grid-template-columns: minmax(0, 132px) minmax(0, 1fr); gap: 4px 11px; padding: 9px 5px; border-bottom: 1px solid var(--border); font-size: 12px; }
  .sig > div { min-width: 0; }
  .sig .pill { white-space: normal; overflow-wrap: anywhere; word-break: break-word; }
  .sig-summary, .sig-evidence { overflow-wrap: anywhere; word-break: break-word; }
  .sig:last-child { border-bottom: none; }

  .scorebar { display: inline-block; width: 56px; height: 6px; border-radius: 4px; background: var(--track); vertical-align: middle; overflow: hidden; }
  .scorebar > i { display: block; height: 100%; }
  .routes-table { table-layout: fixed; min-width: 0; }
  .routes-table th, .routes-table td { overflow-wrap: anywhere; word-break: break-word; }
  .routes-table .route-id { width: 42%; }
  .routes-table .route-status { width: 19%; }
  .routes-table .route-score { width: 17%; }
  .routes-table .route-root, .routes-table .route-verified { width: 11%; }
  .routes-table .scorebar { width: min(56px, 42%); }
  /* Proof graph */
  .graphwrap { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 14px; align-items: stretch; }
  .graphstage { position: relative; min-height: 360px; overflow: auto; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); }
  .graphcanvas { position: relative; min-width: 1380px; min-height: 360px; }
  .graphedges { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
  .gedge { stroke: color-mix(in srgb, var(--muted) 34%, transparent); stroke-width: 1.2; }
  .gedge.strong { stroke: color-mix(in srgb, var(--good) 70%, transparent); stroke-width: 1.8; }
  .gedge.blocking { stroke: color-mix(in srgb, var(--bad) 72%, transparent); stroke-width: 1.8; stroke-dasharray: 5 4; }
  .gnode {
    position: absolute; width: 220px; height: 78px; text-align: left; cursor: pointer;
    border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
    background: var(--surface); color: var(--text); padding: 10px 11px;
    box-shadow: var(--shadow-sm); transition: transform .12s, border-color .12s, box-shadow .12s;
    overflow: hidden;
  }
  .gnode:hover, .gnode.selected { transform: translateY(-1px); border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--uw-purple) 16%, transparent), var(--shadow-sm); }
  .gnode.blocking { border-left: 4px solid var(--bad); }
  .gnode.verifier-ready { border-left: 4px solid var(--warn); }
  .gnode.verified { border-left: 4px solid var(--good); }
  .gnode.refuted { border-left: 4px solid var(--bad); background: color-mix(in srgb, var(--bad) 7%, var(--surface)); }
  .gnode .gkind { font-family: var(--mono); font-size: 10px; color: var(--faint); text-transform: uppercase; letter-spacing: .5px; }
  .gnode .glabel {
    font-size: 12.2px; font-weight: 700; overflow-wrap: anywhere; line-height: 1.25; margin-top: 2px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }
  .gnode .gmeta { font-family: var(--mono); color: var(--muted); font-size: 10.5px; margin-top: 5px; line-height: 1.35; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .gnode.artifact {
    width: 48px; height: 48px; min-height: 48px; border-radius: 999px; padding: 6px;
    display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;
  }
  .gnode.artifact .gkind { display: none; }
  .gnode.artifact .glabel { margin: 0; font-size: 10.5px; line-height: 1.1; -webkit-line-clamp: 2; }
  .gnode.artifact .gmeta { display: none; }
  .graphlegend { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 10px; align-items: center; }
  .graphdetail { border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); padding: 12px 13px; min-height: 360px; overflow: auto; }
  .graphdetail .dtitle { font-weight: 800; overflow-wrap: anywhere; line-height: 1.25; margin-bottom: 8px; }
  .graphdetail .dsummary { color: var(--muted); font-size: 12.5px; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.5; }
  .graphdetail .dgrid { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 5px 10px; font-size: 11.5px; margin: 10px 0; }
  .graphdetail .dgrid span:nth-child(odd) { color: var(--faint); text-transform: uppercase; letter-spacing: .4px; font-size: 10px; }
  .graphdetail .dgrid span:nth-child(even) { font-family: var(--mono); overflow-wrap: anywhere; }
  @media (max-width: 1000px) {
    .graphwrap { grid-template-columns: 1fr; }
    .graphdetail { min-height: 180px; }
    .bottleneck-panel { grid-template-columns: 1fr; }
    .spine-panel { grid-template-columns: 1fr; }
  }
  @media (max-width: 720px) {
    .wrap { padding-left: 14px; padding-right: 14px; }
    header.topbar { padding-left: 14px; padding-right: 14px; margin-left: -14px; margin-right: -14px; }
    th, td { padding: 8px 7px; }
    .routes-table { font-size: 11.5px; }
    .routes-table .route-id { width: 36%; }
    .routes-table .route-status { width: 20%; }
    .routes-table .route-score { width: 20%; }
    .routes-table .route-root, .routes-table .route-verified { width: 12%; }
  }

  .errbar { display: none; background: color-mix(in srgb, var(--bad) 12%, transparent); border: 1px solid color-mix(in srgb, var(--bad) 35%, transparent); color: var(--bad); padding: 10px 14px; border-radius: var(--radius-sm); margin-bottom: 18px; font-family: var(--mono); font-size: 12px; }
  .foot { margin-top: 30px; color: var(--faint); font-size: 11px; font-family: var(--mono); text-align: center; }
</style>
</head>
<body>
<div class="wrap">
  <header class="topbar">
    <div class="brand">
      <div class="mark">A</div>
      <div class="titles">
        <span class="lab">Math AI Lab <span class="dot">·</span> Albilich Monitor</span>
        <span class="pid" id="pid">__PROBLEM_ID__</span>
      </div>
    </div>
    <div class="spacer"></div>
    <div class="ctl">
      <span id="statusBadge" class="badge mut">—</span>
      <span class="badge mut" id="revBadge">rev —</span>
      <span class="live"><span class="dot" id="liveDot"></span><span id="liveText">connecting…</span></span>
      <button class="btn" id="themeBtn" title="Toggle theme">◐ Auto</button>
      <button class="btn primary" id="pauseBtn" title="Display-only: freezes dashboard refreshes. The Albilich run keeps running. To pause the run itself: python -m agents.generation.phase2.cli pause <problem>">⏸ Pause dashboard</button>
      <button class="btn" id="refreshBtn">↻</button>
      <span class="updated" id="updated"></span>
    </div>
  </header>

  <div class="runbar unknown" id="runbar"><span class="rdot"></span><span>Connecting…</span></div>

  <div class="errbar" id="errbar"></div>

  <div class="kpis" id="kpis"></div>

  <div class="card">
    <h2>Pipeline · current action <span class="count pipenow" id="pipeNow"></span></h2>
    <div class="body" id="pipeline"></div>
  </div>

  <div class="card">
    <h2>Active Proof Spine <span class="count" id="spineCount"></span></h2>
    <div class="body" id="proofSpine"><div class="empty">No proof spine yet.</div></div>
  </div>

  <div class="card">
    <h2>Bottleneck Frontier <span class="count" id="bottleneckCount"></span></h2>
    <div class="body" id="bottleneckFrontier"><div class="empty">No active bottleneck.</div></div>
  </div>

  <div class="card">
    <h2>Work Modes · researcher &amp; villain <span class="count" id="rmodeCount"></span></h2>
    <div class="body" id="researcherMode"><div class="empty">No researcher or villain passes yet.</div></div>
  </div>

  <div class="card now">
    <h2>Current Session · live agent stream <span class="count" id="sessCount"></span></h2>
    <div class="body">
      <div class="session-grid" id="sessionCards"></div>
      <div id="sessMeta"></div>
      <div class="log livestream" id="liveStream" data-autoscroll="1"><div class="empty">Waiting for the agent's live stream…</div></div>
    </div>
  </div>

  <div class="card steer">
    <h2>Human Steering <span class="count" id="steerCount"></span></h2>
    <div class="body">
      <div id="steerBlockers"></div>
      <div class="steerform">
        <textarea id="steerText" class="steerinput" rows="2" placeholder="Type guidance for the researcher/advisor — e.g. 'decompose to the realizable case first' or 'drop Hard Lefschetz; attack the rank-4 endpoint inequality instead'. The run picks it up on the next step (it never halts)."></textarea>
        <div class="steeractions">
          <select class="tailsel" id="steerBlockerSel"><option value="">general steer</option></select>
          <button class="btn primary" id="steerSend">Send steering ▸</button>
          <span class="tailmeta" id="steerMsg"></span>
        </div>
      </div>
      <div id="steerLog"></div>
    </div>
  </div>

  <div class="tokens" id="tokens"></div>

  <div class="card" id="verifiedCard" style="display:none">
    <h2>Claims <span class="count" id="verifiedCount"></span></h2>
    <div class="body" id="verified"></div>
  </div>

  <div class="card">
    <h2>Proof Graph <span class="count" id="graphCount"></span></h2>
    <div class="body">
      <div class="graphlegend" id="graphLegend"></div>
      <div class="graphwrap">
        <div class="graphstage">
          <div class="graphcanvas" id="proofGraph"><div class="empty">No proof graph yet.</div></div>
        </div>
        <div class="graphdetail" id="graphDetail"><div class="empty">Select a graph node to inspect its evidence, blockers, and proof role.</div></div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Live Tail · logs &amp; reports <span class="count" id="tailCount"></span></h2>
    <div class="body">
      <div class="tailbar">
        <select class="tailsel" id="tailFile"></select>
        <label class="checklabel"><input type="checkbox" id="tailFollow" checked /> follow</label>
        <button class="btn" id="tailRefresh">↻</button>
        <span class="tailmeta" id="tailInfo"></span>
      </div>
      <div class="tailview" id="tailView"><div class="empty">Select a file to stream its tail…</div></div>
    </div>
  </div>

  <div class="grid">
    <div class="col-left">
      <div class="card">
        <h2>Route Scoreboard <span class="count" id="routeCount"></span></h2>
        <div class="body tight cap" id="routes"><div class="empty">No routes yet.</div></div>
      </div>
      <div class="card">
        <h2>Recent Research Artifacts <span class="count" id="artCount"></span></h2>
        <div class="body tight cap" id="artifacts"><div class="empty">No artifacts yet.</div></div>
      </div>
    </div>
    <div class="col-right">
      <div class="card">
        <h2>Open Cases <span class="count" id="debtCount"></span></h2>
        <div class="body cap" id="debts"><div class="empty">No active debts.</div></div>
      </div>
      <div class="card">
        <h2>Parallel Exchange <span class="count" id="sigCount"></span></h2>
        <div class="body tight cap" id="signals"><div class="empty">No branch signals.</div></div>
      </div>
      <div class="card">
        <h2>Run Timeline <span class="count" id="timelineCount"></span></h2>
        <div class="body tight cap" id="timeline"><div class="empty">No runs yet.</div></div>
      </div>
    </div>
  </div>

  <div class="foot" id="foot"></div>
</div>

<script>
const POLL_MS = __POLL_MS__;
let paused = false, lastOk = 0;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (n) => (Number(n)||0).toLocaleString();
function compact(n){ n=Number(n)||0; if(n>=1e9) return (n/1e9).toFixed(2)+"B"; if(n>=1e6) return (n/1e6).toFixed(2)+"M"; if(n>=1e3) return (n/1e3).toFixed(1)+"K"; return String(n); }
function fmtSec(s){ s=Number(s)||0; if(s<60) return s.toFixed(0)+"s"; const m=Math.floor(s/60),x=Math.round(s%60); if(m<60) return m+"m "+x+"s"; const h=Math.floor(m/60); return h+"h "+(m%60)+"m"; }
function fmtBytes(b){ b=Number(b)||0; const u=["B","KB","MB","GB"]; let i=0; while(b>=1024&&i<u.length-1){b/=1024;i++;} return b.toFixed(b<10&&i>0?1:0)+u[i]; }
function ago(){ if(!lastOk) return ""; const s=Math.round((Date.now()-lastOk)/1000); return "updated "+s+"s ago"; }

/* ===== theme: auto (light 7–19, dark otherwise) like the lab site, with manual override ===== */
function autoTheme(){ const h=new Date().getHours(); return (h>=7 && h<19) ? "light" : "dark"; }
function applyTheme(){
  const pref = localStorage.getItem("alb-theme") || "auto";
  const t = pref==="auto" ? autoTheme() : pref;
  document.documentElement.setAttribute("data-theme", t);
  $("themeBtn").textContent = pref==="auto" ? "◐ Auto" : (t==="dark" ? "☾ Dark" : "☀ Light");
}
$("themeBtn").addEventListener("click", () => {
  const order = ["auto","light","dark"];
  const cur = localStorage.getItem("alb-theme") || "auto";
  localStorage.setItem("alb-theme", order[(order.indexOf(cur)+1)%order.length]);
  applyTheme();
});
applyTheme();
setInterval(applyTheme, 60000);

const STATUS_CLASS = (s) => {
  s = String(s||"").toLowerCase();
  if (s.includes("integrat") || s.includes("solved") || s.includes("proved") || s === "verified") return "good";
  if (s.includes("refut") || s.includes("fail") || s.includes("error")) return "bad";
  if (s.includes("debt") || s.includes("partial") || s.includes("unresolved") || s.includes("stalled")) return "warn";
  if (s.includes("run") || s.includes("progress") || s.includes("active")) return "info";
  return "mut";
};
const PILL = (s) => {
  s = String(s||"").toLowerCase();
  if (s.includes("verified")||s.includes("complete")||s.includes("ready")||s==="good") return "good";
  if (s.includes("fail")||s.includes("refut")||s.includes("error")||s.includes("blocking")||s.includes("blocked")||s.includes("timeout")||s.includes("stalled")) return "bad";
  if (s.includes("active")||s.includes("running")||s.includes("started")||s.includes("heartbeat")) return "info";
  if (s.includes("partial")||s.includes("pending")||s.includes("plausible")||s.includes("challenged")) return "warn";
  return "";
};

function kpiCard(label, value, sub, bar){
  return `<div class="kpi"><div class="label">${esc(label)}</div><div class="value">${value}</div>${sub?`<div class="sub">${sub}</div>`:""}${bar!=null?`<div class="bar"><i style="width:${Math.max(0,Math.min(100,bar))}%"></i></div>`:""}</div>`;
}
function renderKpis(snap){
  const claimTot = snap.current_claim_count ?? snap.claim_count ?? 0, claimV = snap.verified_claim_count||0;
  const retiredClaims = snap.retired_claim_count||0;
  const openCases = snap.open_case_count ?? snap.active_debt_count ?? 0;
  const openBlocking = snap.open_blocking_case_count ?? snap.blocking_debt_count ?? 0;
  const ledgerActive = snap.ledger_active_debt_count ?? snap.active_debt_count ?? 0;
  const ledgerBlocking = snap.ledger_blocking_debt_count ?? snap.blocking_debt_count ?? 0;
  const solvedLike = String(snap.public_status||"").includes("solved");
  const openCaseSub = solvedLike && (ledgerActive || ledgerBlocking)
    ? `<span>ledger ${num(ledgerActive)} · ${num(ledgerBlocking)} blocking</span>`
    : `<span style="color:var(--bad)">${num(openBlocking)} blocking</span>`;
  $("kpis").innerHTML = [
    kpiCard("Status", `<span class="badge ${STATUS_CLASS(snap.public_status)}">${esc(snap.public_status||"—")}</span>`,
            esc(snap.relation_to_target||"") + (snap.result_kind?` · ${esc(snap.result_kind)}`:"")),
    kpiCard("Claims verified", `${num(claimV)}<small>/${num(claimTot)}</small>`, `${num(snap.integrated_claim_count||0)} integrated${retiredClaims?` · ${num(retiredClaims)} retired`:""}`, claimTot?claimV/claimTot*100:0),
    kpiCard("Root progress", `${num(snap.root_progress_score||0)}`, `${num(snap.verified_root_adjacent_claim_count||0)} near-root verified · ${num(snap.root_local_blocking_debt_count||0)} blockers`),
    kpiCard("Routes active", `${num(snap.active_route_count||0)}<small>/${num(snap.route_count||0)}</small>`, "proof trunks"),
    kpiCard("Open cases", `${num(openCases)}`, openCaseSub),
    kpiCard("Child wall", `${fmtSec(snap.recorded_wall_seconds)}`, `${(Number(snap.recorded_peak_memory_mb)||0).toFixed(0)}MB peak`),
  ].join("");
}

function renderTokens(snap, usage){
  const reserved = snap.tokens_reserved_verification||0;
  const rem = snap.tokens_remaining||0;
  // Budget bar uses effective spend (cached input not charged) for consistency
  // with how remaining_token_budget is decremented.
  const total = Number(snap.tokens_total)|| (Number(snap.tokens_spent_reported||0)+rem);
  const spent = Number(snap.tokens_budget_spent!=null ? snap.tokens_budget_spent : Math.max(0,total-rem));
  const tot = usage.total_recorded || {};
  const live = usage.active_live_children || {};
  const inflight = Number(live.total_tokens)||0;
  const liveRuns = Number(live.run_count)||0;
  const processed = Number(tot.total_tokens)||0;       // full tokens incl cached
  const input = Number(tot.input_tokens)||0;
  const cached = Number(tot.cached_input_tokens)||0;
  const cacheRatio = input ? (cached/input*100) : 0;
  const pctSpent = total ? (spent/total*100) : 0;
  const pctInflight = total ? Math.min(100-pctSpent, inflight/total*100) : 0;
  const runs = tot.run_count||0;
  const avg = runs ? Math.round(processed/runs) : 0;
  const inflightTag = inflight > 0
    ? `<span class="inflight-tag">+${compact(inflight)} in-flight</span>`
    : (liveRuns > 0 ? `<span class="pill info">${liveRuns} live session(s) · tokens post at step end</span>` : "");
  const chips = [
    ["Budget spent", compact(spent), true],
    ["Processed (incl cached)", compact(processed), false],
    ["Cached (free)", compact(cached), false],
    ["Cache ratio", cacheRatio.toFixed(0)+"%", false],
    ["Output", compact(tot.output_tokens), false],
    ["Reasoning", compact(tot.reasoning_output_tokens), false],
    ["In-flight (live)", inflight>0?compact(inflight):"—", inflight>0],
    ["Runs", num(runs), false],
    ["Avg / run", compact(avg), false],
    ["Reserved (verify)", compact(reserved), false],
  ];
  $("tokens").innerHTML = `
    <div class="top">
      <div>
        <div class="lead">Token budget · spent (cached excluded)${inflight>0?" · live":""}</div>
        <div class="big">${compact(spent)}<small> / ${compact(total)} budget · ${compact(processed)} processed</small></div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">${inflightTag}<span class="pctchip">${pctSpent.toFixed(1)}% used · ${compact(rem)} left</span></div>
    </div>
    <div class="bigbar">
      <i class="spent" style="width:${Math.max(0,Math.min(100,pctSpent))}%"></i>
      <i class="inflight" style="width:${Math.max(0,Math.min(100,pctInflight))}%"></i>
    </div>
    <div class="scale"><span>0</span><span>${compact(total)} budget</span></div>
    <div class="chips">${chips.map(c=>`<div class="chip"><div class="k">${c[0]}</div><div class="v ${c[2]?"accent":""}">${c[1]}</div></div>`).join("")}</div>
  `;
}

/* ===== Architecture pipeline (README roles + scheduler loop) ===== */
const PIPE = [
  {role:"literature_researcher", label:"Literature", modes:"retrieve · synthesize · digest", cat:"lit"},
  {role:"researcher", label:"Researcher", modes:"prove · reduce · decompose", cat:"res"},
  {role:"villain", label:"Villain", modes:"refute · counterexample", cat:"vil"},
  {role:"strict_informal_verifier", label:"Strict Verifier", modes:"citations · route check", cat:"ver"},
  {role:"counterexample_validator", label:"CX Validator", modes:"validate counterexample", cat:"ver"},
  {role:"integration_verifier", label:"Integration", modes:"root alignment", cat:"int"},
  {role:"phd_advisor", label:"PhD Advisor", modes:"triage · synthesize · regulate", cat:"adv"},
  {role:"writer", label:"Writer", modes:"final proof · report", cat:"wri"},
];
function liveStatus(s){
  return ["running","started","heartbeat","planned"].includes(String(s||"").toLowerCase());
}
function activeStep(payload){
  const ll = payload.live_logs || [];
  const active = ll.filter(l => liveStatus(l.status));
  if (active.length){
    const s = active[active.length-1];
    return {role:s.actor_role, mode:s.mode, work_mode:s.researcher_work_mode||"", target:s.target_id, elapsed:s.elapsed_seconds, live:true, active_roles:new Set(active.map(x => String(x.actor_role||"")))};
  }
  for (let i=ll.length-1; i>=0; i--){
    const s = String(ll[i].status||"").toLowerCase();
    if (["running","started","heartbeat","planned"].includes(s))
      return {role:ll[i].actor_role, mode:ll[i].mode, work_mode:ll[i].researcher_work_mode||"", target:ll[i].target_id, elapsed:ll[i].elapsed_seconds, live:true};
  }
  const tl = payload.run_timeline || [];
  if (tl.length){ const r = tl[tl.length-1]; return {role:r.actor_role, mode:r.mode, work_mode:r.researcher_work_mode||"", target:r.target_id, live:false}; }
  return {role:"", mode:"", work_mode:"", live:false};
}
function renderPipeline(payload, step){
  const role = step.role || "";
  const activeRoles = step.active_roles || new Set(role ? [role] : []);
  const hubActive = !step.live;  // between steps → scheduler is choosing the next action
  const hub = `<div class="node hub ${hubActive?"active":""}"><span class="nowtag">planning</span>
      <div class="nl">⚙ SCHEDULER</div><div class="nm">deterministic next action · README order</div></div>`;
  const workMode = String(step.work_mode||"");
  const cells = PIPE.map(n => {
    const on = step.live && activeRoles.has(n.role);
    let modesText = n.modes;
    if (n.role === "researcher"){
      modesText = ["online","offline","cas"].map(m =>
        (on && workMode === m) ? `<b style="color:var(--uw-purple)">${m}</b>` : m
      ).join(" · ");
    } else if (n.role === "villain"){
      modesText = ["cas","offline","online"].map(m =>
        (on && workMode === m) ? `<b style="color:var(--uw-purple)">${m}</b>` : m
      ).join(" · ");
    }
    const modeChip = ((n.role==="researcher" || n.role==="villain") && on && workMode)
      ? ` <span class="pill">${esc(workMode)}</span>` : "";
    return `<div class="node ${on?"active":""}" title="${n.role}">
      <span class="nowtag">▶ now</span>
      <div class="nl"><span class="nodecat cat-${n.cat}"></span>${n.label}${modeChip}</div>
      <div class="nm">${modesText}</div></div>`;
  }).join("");
  $("pipeline").innerHTML = `<div class="flow">${hub}<div class="conn">▼ &nbsp; ↻ patch → re-plan</div><div class="flowrow">${cells}</div></div>`;
  const workChip = ((role === "researcher" || role === "villain") && workMode) ? ` · <b>${esc(workMode)}</b>` : "";
  if (step.live){
    $("pipeNow").innerHTML = `▶ <b style="color:var(--uw-purple)">${esc(role||"?")}</b>${workChip} · ${esc(step.mode||"")}${step.target?` · ${esc(step.target)}`:""} · ${fmtSec(step.elapsed)}`;
  } else {
    $("pipeNow").innerHTML = role ? `idle · last: ${esc(role)}${workChip} · ${esc(step.mode||"")}` : "idle · awaiting next step";
  }
}

function renderBottleneck(frontier){
  frontier = frontier || {};
  const current = frontier.current_bottleneck || {};
  const cooldown = frontier.diagnostic_cooldown || {};
  const compute = frontier.compute_shape || {};
  const top = frontier.top_bottleneck_debts || [];
  if (!current.debt_id){
    $("bottleneckCount").textContent = "";
    $("bottleneckFrontier").innerHTML = `<div class="empty">No active root-local bottleneck.</div>`;
    return;
  }
  $("bottleneckCount").innerHTML = frontier.locked
    ? `<span class="pill bad">lock armed</span>`
    : `<span class="pill warn">watching</span>`;
  const diagIds = cooldown.artifact_ids || [];
  const sourceIds = current.source_artifact_ids || [];
  $("bottleneckFrontier").innerHTML = `
    <div class="bottleneck-panel">
      <div class="bottleneck-main">
        <div class="bottleneck-title">
          <span class="pill ${frontier.locked?"bad":"warn"}">${frontier.locked?"bottleneck lock armed":"frontier"}</span>
          <b>${esc(current.debt_id)}</b>
          <span class="pill mut">${esc(current.target_id||"root")}</span>
          ${Number(current.repeated_count)>0?`<span class="pill bad">repeat ${num(current.repeated_count)}</span>`:""}
          ${Number(current.fresh_narrowing_score)>0?`<span class="pill info">fresh ${num(current.fresh_narrowing_score)}</span>`:""}
        </div>
        <div class="bottleneck-obligation">${esc(current.obligation || "No obligation summary.")}</div>
        ${sourceIds.length?`<div class="bottleneck-list">${sourceIds.map(id => `<span class="pill mut">${esc(id)}</span>`).join(" ")}</div>`:""}
        ${top.length>1?`<div class="bottleneck-list">${top.slice(1,4).map(d => `<div class="bmini">${esc(d.debt_id)} · repeat ${num(d.repeated_count)} · fresh ${num(d.fresh_narrowing_score||0)} · ${esc(String(d.obligation||"").slice(0,120))}</div>`).join("")}</div>`:""}
      </div>
      <div class="bottleneck-side">
        <div class="bottleneck-metrics">
          <div class="bmetric"><div class="bk">proof runs</div><div class="bv">${num(compute.recent_proof_attack_runs||0)}</div></div>
          <div class="bmetric"><div class="bk">diagnostics</div><div class="bv">${num(cooldown.recent_diagnostic_count||0)}</div></div>
          <div class="bmetric"><div class="bk">side targets</div><div class="bv">${num(compute.recent_side_target_runs||0)}</div></div>
          <div class="bmetric"><div class="bk">cooldown</div><div class="bv">${cooldown.active?"on":"off"}</div></div>
        </div>
        ${diagIds.length?`<div class="bottleneck-list">${diagIds.map(id => `<span class="pill mut">${esc(id)}</span>`).join(" ")}</div>`:""}
      </div>
    </div>`;
}

function renderWorkModeColumn(title, hints, block, emptyNote){
  block = block || {};
  const current = block.current || {};
  const history = block.history || [];
  const directive = block.advisor_directive || {};
  const predicted = block.predicted_next || {};
  const activeMode = String(current.work_mode || predicted.work_mode || "");
  const cycle = (block.cycle && block.cycle.length ? block.cycle : Object.keys(hints)).map(m => {
    const on = m === activeMode;
    return `<div class="node ${on?"active":""}" title="${esc(hints[m]||m)}">
      <div class="nl">${on?"▶ ":""}${esc(m)}</div><div class="nm">${esc(hints[m]||"")}</div></div>`;
  }).join("");
  const trail = history.slice(0,10).reverse().map(h => {
    const letter = {online:"O", offline:"F", cas:"C"}[h.work_mode] || "?";
    const hover = `${h.work_mode} · ${h.source||""} · ${h.status||""} · ${h.search_intent||""}`;
    const cls = h.source && h.source.indexOf("advisor")===0 ? "bad" : "mut";
    return `<span class="pill ${cls}" title="${esc(hover)}">${letter}</span>`;
  }).join(" ");
  const directiveHtml = directive.work_mode
    ? `<div class="bottleneck-title" style="margin-top:8px">
        <span class="pill bad">ADVISOR DIRECTIVE</span>
        <b>${esc(directive.work_mode)}</b>
        <span class="pill warn">${num(directive.steps_remaining||directive.steps||1)} pass(es) left</span>
       </div>
       <div class="bottleneck-obligation">${esc(directive.reason || "advisor override of the default rotation")}</div>`
    : `<div class="bottleneck-obligation" style="margin-top:8px">No active directive — default rotation.</div>`;
  const body = (current.work_mode || history.length || directive.work_mode)
    ? `<div class="flow"><div class="flowrow">${cycle}</div></div>
       <div class="bottleneck-title" style="margin-top:8px">
         ${current.work_mode?`<span class="pill info">last pass: ${esc(current.work_mode)}</span><span class="pill mut">${esc(current.source||"")}</span><span class="pill mut">${esc(current.status||"")}</span>`:""}
         ${predicted.work_mode?`<span class="pill mut">next default: ${esc(predicted.work_mode)}</span>`:""}
       </div>
       ${directiveHtml}
       ${trail?`<div style="margin-top:8px">trail (oldest → newest): ${trail}</div>`:""}`
    : `<div class="flow"><div class="flowrow">${cycle}</div></div>
       <div class="empty" style="margin-top:8px">${esc(emptyNote)}</div>`;
  return `<div style="flex:1 1 340px; min-width:300px">
    <div class="bottleneck-title"><b>${esc(title)}</b></div>
    ${body}
  </div>`;
}

function renderResearcherMode(rmode){
  rmode = rmode || {};
  const researcher = {
    cycle: rmode.cycle, current: rmode.current, history: rmode.history,
    advisor_directive: rmode.advisor_directive, predicted_next: rmode.predicted_next,
  };
  const villain = rmode.villain || {};
  const rDirective = (rmode.advisor_directive||{}).work_mode;
  const vDirective = (villain.advisor_directive||{}).work_mode;
  const rMode = String((rmode.current||{}).work_mode || (rmode.predicted_next||{}).work_mode || "");
  const vMode = String((villain.current||{}).work_mode || (villain.predicted_next||{}).work_mode || "");
  const badges = [];
  if (rDirective) badges.push(`<span class="pill bad">R directive: ${esc(rDirective)}</span>`);
  else if (rMode) badges.push(`<span class="pill info">R: ${esc(rMode)}</span>`);
  if (vDirective) badges.push(`<span class="pill bad">V directive: ${esc(vDirective)}</span>`);
  else if (vMode) badges.push(`<span class="pill info">V: ${esc(vMode)}</span>`);
  $("rmodeCount").innerHTML = badges.join(" ");
  // Prover and refuter are equals (Nagata working mode): two symmetric columns.
  $("researcherMode").innerHTML = `<div style="display:flex; gap:16px; flex-wrap:wrap">
    ${renderWorkModeColumn(
      "Researcher · prover",
      {online:"search & read", offline:"think & prove", cas:"compute & experiment"},
      researcher,
      "No researcher passes yet — the loop starts online → offline → cas.")}
    ${renderWorkModeColumn(
      "Villain · refuter",
      {cas:"compute & sweep", offline:"construct & stress", online:"hunt prior art"},
      villain,
      "No villain passes yet — the refuter loop starts cas → offline → online.")}
  </div>`;
}

function renderProofSpine(spine){
  spine = spine || {};
  const claims = spine.verified_trunk_claims || [];
  const routes = spine.active_routes || [];
  const arts = spine.recent_spine_artifacts || [];
  const ready = spine.verifier_ready_routes || [];
  const bottleneck = spine.current_bottleneck || {};
  if (!claims.length && !routes.length && !arts.length && !bottleneck.debt_id){
    $("spineCount").textContent = "";
    $("proofSpine").innerHTML = `<div class="empty">No compact proof spine yet.</div>`;
    return;
  }
  $("spineCount").innerHTML = `${claims.length} trunk · ${ready.length} verifier-ready`;
  $("proofSpine").innerHTML = `
    <div class="spine-panel">
      <div class="spine-main">
        <div class="bottleneck-title">
          <span class="pill info">proof spine</span>
          <span class="pill mut">root ${esc(spine.root_status||"untested")}</span>
          ${ready.length?`<span class="pill good">${ready.length} verifier-ready</span>`:`<span class="pill warn">route conversion needed</span>`}
        </div>
        <div class="spine-rule">${esc(spine.next_workflow_rule || "")}</div>
        <div class="spine-list">
          ${claims.slice(0,5).map(c => `<div class="spine-item"><b>${esc(c.claim_id)}</b> · impact ${Number(c.root_impact||0).toFixed(2)} · d${num(c.root_distance||0)}<br>${esc(c.statement||"")}</div>`).join("")}
          ${bottleneck.debt_id?`<div class="spine-item"><b>Current bottleneck</b> · ${esc(bottleneck.debt_id)}<br>${esc(bottleneck.obligation||"")}</div>`:""}
        </div>
      </div>
      <div class="spine-side">
        <div class="group-h">Routes</div>
        <div class="spine-list">${routes.slice(0,4).map(r => `<div class="spine-item"><b>${esc(r.route_id||"")}</b> · ${esc(r.status||"")} · score ${num(r.score||0)}<br>${esc(r.summary||"")}</div>`).join("") || `<div class="empty">No active route spine.</div>`}</div>
        <div class="group-h">Recent Proof Artifacts</div>
        <div class="spine-list">${arts.slice(0,4).map(a => `<div class="spine-item"><b>${esc(a.artifact_id||"")}</b> · ${esc(a.artifact_type||"")} · ${esc(a.producer_role||"")}<br>${esc(a.next_decisive_action || a.summary || "")}</div>`).join("") || `<div class="empty">No recent spine artifacts.</div>`}</div>
      </div>
    </div>`;
}

/* Live agent stream: keep the window stable and always populated. The backend
   only fills log_tail on heartbeat polls, so we cache the last non-empty streamed
   text per session and update the window in place (never blanking, scroll-preserving). */
const sessTail = {};                          // session-key -> last non-empty streamed tail
let selectedSessionKey = "", selectedSessionUserPicked = false, lastStreamText = "", lastMetaHTML = "", lastSessionPayload = null;
function sessionKey(l){ return String((l&&l.run_id)||`${(l&&l.actor_role)||""}|${(l&&l.mode)||""}|${(l&&l.target_id)||""}`); }
function latestInvocationSessions(payload){
  const inv = payload.current_invocation || [];
  for (let i=inv.length-1; i>=0; i--){
    const updates = inv[i] && inv[i].live_session_updates;
    if (Array.isArray(updates) && updates.length) return updates;
  }
  return payload.live_logs || [];
}
function selectDefaultSession(sessions){
  if (!sessions.length) return null;
  const running = sessions.filter(s => liveStatus(s.status));
  return (running.length ? running[running.length-1] : sessions[sessions.length-1]);
}
function renderSessionCards(sessions, activeKey){
  const box = $("sessionCards");
  if (!box) return;
  if (!sessions.length){ box.innerHTML = ""; return; }
  box.innerHTML = sessions.map((s, idx) => {
    const key = sessionKey(s);
    const status = String(s.status || "");
    const statusClass = status.toLowerCase().replace(/[^a-z0-9_-]/g, "_");
    const tokens = Number((s.usage||{}).total_tokens || 0);
    return `<button type="button" class="session-card ${statusClass} ${key===activeKey?"selected":""}" data-key="${esc(key)}" title="${esc(s.run_id||key)}">
      <div class="s-top"><span class="s-dot"></span><span class="s-role">${esc(s.actor_role||"role")}</span><span class="pill ${PILL(status)}">${esc(status||"—")}</span></div>
      <div class="s-mode">${esc(s.mode||"")}${s.target_id?` · ${esc(s.target_id)}`:""}</div>
      <div class="s-metrics"><span>${fmtSec(s.elapsed_seconds)}</span>${tokens?`<span>${compact(tokens)} tok</span>`:""}${Number(s.peak_memory_mb)>0?`<span>${Number(s.peak_memory_mb).toFixed(0)}MB</span>`:""}</div>
    </button>`;
  }).join("");
  box.querySelectorAll(".session-card").forEach(btn => btn.addEventListener("click", () => {
    selectedSessionKey = btn.getAttribute("data-key") || "";
    selectedSessionUserPicked = true;
    if (lastSessionPayload) renderSession(lastSessionPayload);
  }));
}
function renderSession(payload){
  lastSessionPayload = payload;
  const logs = payload.live_logs || [], inv = payload.current_invocation || [];
  for (const l of logs){ const t = String(l.log_tail||"").trim(); if (t) sessTail[sessionKey(l)] = t; }
  const sessions = latestInvocationSessions(payload);
  for (const l of sessions){ const t = String(l.log_tail||"").trim(); if (t) sessTail[sessionKey(l)] = t; }
  const liveN = sessions.filter(s => liveStatus(s.status)).length;
  $("sessCount").textContent = sessions.length ? `${liveN}/${sessions.length} live` : (lastMetaHTML ? "idle" : "");

  if (selectedSessionKey && !sessions.some(s => sessionKey(s) === selectedSessionKey)){
    selectedSessionKey = "";
    selectedSessionUserPicked = false;
  }
  if (!selectedSessionKey || !selectedSessionUserPicked){
    const preferred = selectDefaultSession(sessions);
    selectedSessionKey = preferred ? sessionKey(preferred) : "";
  }
  const active = sessions.find(s => sessionKey(s) === selectedSessionKey) || selectDefaultSession(sessions);
  const activeKey = active ? sessionKey(active) : "";
  renderSessionCards(sessions, activeKey);

  // --- meta header (small; rebuilt each poll, no scroll to disturb) ---
  let meta = "";
  const latestInv = inv.length ? inv[inv.length-1] : null;
  if (latestInv){
    meta += `<div class="sessmeta">
      <span class="pair">step <b>${esc(latestInv.step)}</b></span>
      <span class="pill ${PILL(latestInv.execution_phase)}">${esc(latestInv.execution_phase||"—")}</span>
      <span class="pair">${esc(latestInv.primary_action_summary||"")}</span></div>`;
    if (latestInv.execution_summary) meta += `<div class="summary">${esc(latestInv.execution_summary)}</div>`;
  }
  if (active){
    meta += `<div class="sessmeta" style="margin-top:10px">
      <span class="pill ${PILL(active.actor_role)}">${esc(active.actor_role||"role")}</span>
      ${active.mode?`<span class="pair">mode <b>${esc(active.mode)}</b></span>`:""}
      ${active.target_id?`<span class="pair">target <b class="mono">${esc(active.target_id)}</b></span>`:""}
      <span class="pill ${PILL(active.status)}">${esc(active.status||"")}</span>
      ${active.phase?`<span class="pair">phase <b>${esc(active.phase)}</b></span>`:""}
      <span class="pair">elapsed <b>${fmtSec(active.elapsed_seconds)}</b></span>
      ${Number(active.peak_memory_mb)>0?`<span class="pair">mem <b>${(Number(active.peak_memory_mb)).toFixed(0)}MB</b></span>`:""}</div>`;
    lastMetaHTML = meta;
  } else if (lastMetaHTML){
    meta = `<div class="idle-banner">⏸ between steps — showing the last live stream (until the next step starts)</div>` + lastMetaHTML;
  }
  $("sessMeta").innerHTML = meta || `<div class="empty">No live session yet — the agent's reasoning and tool calls stream here while a step runs.</div>`;

  // --- streaming window: update textContent IN PLACE (stable, never blank, follow only if at bottom) ---
  const key = active ? sessionKey(active) : null;
  let streamText = (active && String(active.log_tail||"").trim()) || (key && sessTail[key]) || "";
  if (!streamText && !sessions.length) streamText = lastStreamText || "";
  if (streamText && (!key || key === activeKey)) lastStreamText = streamText;
  const el = $("liveStream");
  if (el){
    const role = active ? `${active.actor_role||"agent"}` : "agent";
    const show = streamText || `Waiting for ${role}'s first streamed output…`;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (el.textContent !== show){ el.textContent = show; if (atBottom) el.scrollTop = el.scrollHeight; }
  }
}

function scoreColor(s){ s=Number(s); if(s>0) return "var(--good)"; if(s<0) return "var(--bad)"; return "var(--muted)"; }
function routeStatusHint(r){
  const status = String(r.scoreboard_status||"");
  const reasons = Array.isArray(r.kill_reasons) && r.kill_reasons.length ? ` Reasons: ${r.kill_reasons.join("; ")}` : "";
  if (status === "blocked") return `Explicit route.status=blocked; paused pending an obstruction or proof debt.${reasons}`;
  if (status === "stalled") return `Heuristic stalled label from repeated blockers or failed route health checks; the route may need repair before reuse.${reasons}`;
  return reasons.trim() || status;
}
function renderRoutes(rows){
  rows = rows || [];
  $("routeCount").textContent = rows.length ? `${rows.length}` : "";
  if (!rows.length){ $("routes").innerHTML = `<div class="empty">No routes recorded.</div>`; return; }
  let h = `<table class="routes-table"><thead><tr><th class="route-id">Route</th><th class="route-status">Status</th><th class="num route-score">Score</th><th class="num route-root">Root d</th><th class="num route-verified">Verified</th></tr></thead><tbody>`;
  for (const r of rows){
    const sc = Number(r.score)||0, mag = Math.min(100, Math.abs(sc)*16);
    h += `<tr><td class="mid route-id" title="${esc(r.route_id)}">${esc(r.route_id)}</td>
      <td class="route-status" title="${esc(routeStatusHint(r))}"><span class="pill ${PILL(r.scoreboard_status)}">${esc(r.scoreboard_status||"")}</span></td>
      <td class="num route-score"><span class="scorebar"><i style="width:${mag}%;background:${scoreColor(sc)}"></i></span> ${sc.toFixed(2)}</td>
      <td class="num route-root">${esc(r.root_distance)}</td>
      <td class="num route-verified">${r.verified_inference_count||0}/${r.inference_count||0}</td></tr>`;
  }
  $("routes").innerHTML = h + `</tbody></table>`;
}

function renderDebts(groups){
  groups = groups || {};
  const order = ["Blocking","Citation / Hypothesis","Verifier Repair","Decomposition / Regulator","Other"];
  let total = 0; order.forEach(g => total += (groups[g]||[]).length);
  $("debtCount").textContent = total ? `${total}` : "";
  if (!total){ $("debts").innerHTML = `<div class="empty">No active proof debts.</div>`; return; }
  let h = "";
  for (const g of order){
    const list = groups[g] || [];
    if (!list.length) continue;
    h += `<div class="group-h">${esc(g)} · ${list.length}</div>`;
    for (const d of list.slice(0,10)){
      const blocking = String(d.severity||"").toLowerCase()==="blocking";
      h += `<div class="debt ${blocking?"blocking":""}">
        <div class="head"><span class="mid">${esc(d.debt_id)}</span>
          <span class="pill ${blocking?"bad":"warn"}">${esc(d.severity||"")}</span>
          ${Number(d.repeated_count)>1?`<span class="pill bad">×${esc(d.repeated_count)}</span>`:""}
          <span class="pair" style="color:var(--faint);font-size:11px">→ ${esc(d.suggested_next_target||"?")}</span></div>
        <div class="oblig">${esc(String(d.obligation||"").slice(0,260))}${String(d.obligation||"").length>260?"…":""}</div></div>`;
    }
  }
  $("debts").innerHTML = h;
}

function renderSignals(rows){
  rows = (rows||[]).slice(-12).reverse();
  $("sigCount").textContent = rows.length ? `${rows.length}` : "";
  if (!rows.length){ $("signals").innerHTML = `<div class="empty">No parallel branch signals yet.</div>`; return; }
  let h = "";
  for (const s of rows){
    h += `<div class="sig"><span class="pill ${PILL(s.relation)}">${esc(s.signal_type||"signal")}</span>
      <div><div><b class="mono">${esc(s.actor_role||"")}</b> <span class="pair" style="color:var(--faint)">${esc(s.created_at||"")}</span> ${s.confidence?`· conf ${esc(s.confidence)}`:""}</div>
        <div class="sig-summary" style="color:var(--muted)">${esc(String(s.summary||"").slice(0,200))}</div>
        ${s.evidence?`<div class="pair sig-evidence" style="color:var(--faint);font-size:11px">evidence: ${esc(s.evidence)}</div>`:""}</div></div>`;
  }
  $("signals").innerHTML = h;
}

function renderTimeline(rows){
  const allRows = rows || [];
  const integrationRows = allRows.filter(r => r.actor_role === "integration_verifier" && r.mode === "integrate");
  const integrationFailures = integrationRows.filter(r => ["patch_rejected","failed","no_patch"].includes(String(r.status||"")));
  const recoveredFailures = integrationFailures.filter(r => r.failure_recovered);
  const unresolvedFailures = integrationFailures.length - recoveredFailures.length;
  const latestIntegration = integrationRows.length ? integrationRows[integrationRows.length - 1] : null;
  rows = allRows.slice(-14).reverse();
  $("timelineCount").textContent = rows.length ? `${rows.length}` : "";
  if (!rows.length){ $("timeline").innerHTML = `<div class="empty">No recorded runs yet.</div>`; return; }
  let h = "";
  if (integrationRows.length){
    const latestOK = latestIntegration && latestIntegration.status === "completed";
    h += `<div class="integration-health"><b>Recent integration verifier</b>
      <span class="pill ${latestOK?"good":"warn"}">latest ${esc(latestIntegration.status||"")}</span>
      <span>${integrationRows.filter(r => r.status === "completed").length} completed</span>
      <span>${integrationFailures.length} failed/rejected</span>
      ${recoveredFailures.length?`<span class="pill info">${recoveredFailures.length} recovered later</span>`:""}
      ${unresolvedFailures?`<span class="pill bad">${unresolvedFailures} unresolved</span>`:""}</div>`;
  }
  h += `<table><thead><tr><th>Run</th><th>Actor</th><th>Mode</th><th>Status</th><th class="num" title="Provider-reported input plus output; budget spend excludes cached input and includes reasoning.">Processed</th><th class="num">Wall</th></tr></thead><tbody>`;
  for (const r of rows){
    const recovered = Boolean(r.failure_recovered);
    const statusText = `${r.status||""}${recovered?" · recovered":""}`;
    const statusTitle = recovered ? `Recovered by later integration ${r.recovered_by_run_id||""}` : "";
    h += `<tr><td class="mid" title="${esc(r.run_id)}">${esc(String(r.run_id||"").replace(/^v1_/,""))}</td>
      <td><span class="pill ${PILL(r.actor_role)}">${esc(r.actor_role||"")}</span></td>
      <td class="mono" style="font-size:11px">${esc(r.mode||"")}</td>
      <td><span class="pill ${recovered?"info":PILL(r.status)}" title="${esc(statusTitle)}">${esc(statusText)}</span></td>
      <td class="num">${num(r.total_tokens||0)}</td><td class="num">${fmtSec(r.wall_time_seconds)}</td></tr>`;
  }
  $("timeline").innerHTML = h + `</tbody></table>`;
}

function renderArtifacts(rows){
  rows = (rows||[]).slice(0,16);
  $("artCount").textContent = rows.length ? `${rows.length}` : "";
  if (!rows.length){ $("artifacts").innerHTML = `<div class="empty">No research artifacts yet.</div>`; return; }
  let h = `<table><thead><tr><th>Artifact</th><th>Type</th><th>By</th><th class="num">rev</th></tr></thead><tbody>`;
  for (const a of rows){
    const summary = a.metadata_summary || a.content_summary || "";
    h += `<tr><td class="mid" title="${esc(a.path||a.artifact_id)}">${esc(a.artifact_id)}${summary?`<div class="pair" style="color:var(--faint);font-size:11px;white-space:normal">${esc(String(summary).slice(0,90))}</div>`:""}</td>
      <td><span class="pill info">${esc(a.artifact_type||"")}</span></td>
      <td class="mono" style="font-size:11px">${esc(a.producer_role||"")}</td>
      <td class="num">${esc(a.state_revision)}</td></tr>`;
  }
  $("artifacts").innerHTML = h + `</tbody></table>`;
}

function renderClaims(rows){
  rows = rows || [];
  const card = $("verifiedCard");
  if (!rows.length){ card.style.display = "none"; return; }
  card.style.display = "";
  const relationPill = (label, ids) => {
    ids = ids || [];
    if (!ids.length) return "";
    const shown = ids.slice(0,2).join(", ");
    const extra = ids.length > 2 ? ` +${ids.length-2}` : "";
    return `<span class="pill info" title="${esc(ids.join(", "))}">${esc(label)} ${esc(shown)}${esc(extra)}</span>`;
  };
  const visualStatus = c => {
    const integrated = String(c.lifecycle_status||"").toLowerCase() === "integrated";
    const vs = String(c.display_validation_status||c.validation_status||"").toLowerCase();
    const lifecycle = String(c.lifecycle_status||"").toLowerCase();
    if (vs === "refuted") return "refuted";
    if (["superseded","abandoned"].includes(lifecycle)) return lifecycle;
    if (integrated) return "integrated";
    if (vs === "plausible") return "plausible";
    if (vs === "challenged") return "challenged";
    if (vs === "blocked") return "blocked";
    if (lifecycle === "active" || vs === "active_question") return "active";
    if (c.verified) return "verified";
    return "untested";
  };
  const claimBadge = c => {
    const integrated = String(c.lifecycle_status||"").toLowerCase() === "integrated";
    const lifecycle = String(c.lifecycle_status||"").toLowerCase();
    const vs = String(c.display_validation_status||c.validation_status||"").toLowerCase();
    let badge;
    if (vs === "superseded") badge = `<span class="badge superseded">superseded · stronger result</span>`;
    else if (vs === "abandoned") badge = `<span class="badge mut">abandoned</span>`;
    else if (vs === "blocked") badge = `<span class="badge warn">blocked</span>`;
    else if (vs === "refuted") badge = `<span class="badge bad">refuted</span>`;
    else if (integrated) badge = `<span class="badge integrated">integrated</span>`;
    else if (c.verified) badge = `<span class="badge good">✓ ${esc(c.validation_status||"verified")}</span>`;
    else if (vs === "challenged" && Number(c.verification_report_count||0) > 0)
      badge = `<span class="badge bad" title="strict verification report at revision ${num(c.latest_verification_revision||0)}">tested · gaps</span>`;
    else if (vs === "plausible") badge = `<span class="badge plausible">plausible</span>`;
    else if (vs === "active_question") badge = `<span class="badge active">active question</span>`;
    else if (lifecycle === "active") badge = `<span class="badge active">active · ${esc(c.validation_status||"untested")}</span>`;
    else if (vs === "checked_pending_transition") badge = `<span class="badge info">tested · status pending</span>`;
    else badge = `<span class="badge mut">${esc(c.validation_status||"unverified")}</span>`;
    return badge;
  };
  const renderClaimCard = c => {
    const badge = claimBadge(c);
    const relations = [
      relationPill("subclaim of", c.subclaim_of_claim_ids),
      relationPill("supports", c.supports_claim_ids),
      relationPill("supported by", c.supported_by_claim_ids),
      relationPill("contains", c.contains_subclaim_ids),
      relationPill("superseded by", c.superseded_by_claim_ids),
    ].filter(Boolean).join("");
    const status = visualStatus(c);
    return `<div class="vclaim status-${esc(status)}${c.verified?"":" unverified"}" data-claim-id="${esc(c.claim_id)}" data-claim-status="${esc(status)}">
      <div class="vhead">${badge}<span class="mid" title="${esc(c.claim_id)}">${esc(c.claim_id)}</span></div>
      <div class="vstmt">${esc(c.statement||"(no statement)")}</div>
      ${relations?`<div class="vrel">${relations}</div>`:""}
    </div>`;
  };
  const retiredStatuses = new Set(["superseded","abandoned","refuted"]);
  const retiredRows = rows.filter(c => retiredStatuses.has(visualStatus(c)));
  const currentRows = rows.filter(c => !retiredStatuses.has(visualStatus(c)));
  const nver = currentRows.filter(c => c.verified).length;
  $("verifiedCount").textContent = `${nver}/${currentRows.length} current verified · ${retiredRows.length} retired`;
  const currentMap = new Map(currentRows.map(c => [String(c.claim_id||""), c]));
  const children = new Map(currentRows.map(c => [String(c.claim_id||""), []]));
  const roots = [];
  const parentFor = c => {
    const parents = (c.subclaim_of_claim_ids||[]).map(id => currentMap.get(String(id))).filter(Boolean);
    if (!parents.length) return null;
    const depth = Number(c.reduction_depth||0);
    const nearer = parents.filter(p => Number(p.reduction_depth||0) < depth)
      .sort((a,b) => Number(b.reduction_depth||0)-Number(a.reduction_depth||0) || String(a.claim_id).localeCompare(String(b.claim_id)));
    return nearer[0] || parents.find(p => p.claim_id === "root") || parents[0];
  };
  for (const c of currentRows){
    const parent = parentFor(c);
    if (parent && parent.claim_id !== c.claim_id) children.get(String(parent.claim_id)).push(c);
    else roots.push(c);
  }
  const rank = c => {
    if (c.claim_id === "root") return -10;
    return ({active:0, plausible:1, challenged:2, blocked:3, verified:4, integrated:5, untested:6})[visualStatus(c)] ?? 7;
  };
  const sortClaims = list => list.sort((a,b) => rank(a)-rank(b) || Number(b.root_impact||0)-Number(a.root_impact||0) || String(a.claim_id).localeCompare(String(b.claim_id)));
  const visited = new Set();
  const renderTreeNode = c => {
    const claimId = String(c.claim_id||"");
    if (visited.has(claimId)) return "";
    visited.add(claimId);
    const nested = sortClaims(children.get(claimId)||[]).map(renderTreeNode).join("");
    return `<div class="claim-tree-node" data-tree-claim-id="${esc(claimId)}">${renderClaimCard(c)}${nested?`<div class="claim-tree-children">${nested}</div>`:""}</div>`;
  };
  let treeHtml = sortClaims(roots).map(renderTreeNode).join("");
  treeHtml += sortClaims(currentRows.filter(c => !visited.has(String(c.claim_id||"")))).map(renderTreeNode).join("");
  const legend = `<div class="claim-legend"><span class="label">status colors</span>
    <span class="badge active">active</span><span class="badge plausible">plausible</span>
    <span class="badge bad">challenged / refuted</span><span class="badge integrated">integrated</span>
    <span class="badge superseded">superseded</span></div>`;
  let h = `${legend}<section class="claim-section current"><div class="claim-section-title">Current proof tree <span class="count">${currentRows.length} claims</span></div>${treeHtml}</section>`;
  if (retiredRows.length){
    const retiredHtml = sortClaims(retiredRows).map(renderClaimCard).join("");
    h += `<section class="claim-section retired"><div class="claim-section-title">Retired / superseded / falsified claims <span class="count">${retiredRows.length} claims</span></div><div class="retired-claims">${retiredHtml}</div></section>`;
  }
  $("verified").innerHTML = h;
}

let selectedGraphNode = "";
function graphNodeClass(n){
  const status = String(n.status||"").toLowerCase();
  const cls = ["gnode", String(n.kind||"")];
  if (Number(n.blocking_debt_count||0) > 0 || (n.kind === "debt" && status === "blocking")) cls.push("blocking");
  if (n.verifier_ready) cls.push("verifier-ready");
  if (status.includes("verified") || String(n.lifecycle_status||"") === "integrated") cls.push("verified");
  if (status.includes("refuted")) cls.push("refuted");
  if (selectedGraphNode === n.id) cls.push("selected");
  return cls.join(" ");
}
function graphMeta(n){
  if (n.kind === "claim") return `d=${n.root_distance ?? "?"} · impact=${Number(n.root_impact||0).toFixed(2)} · routes=${n.route_count||0}`;
  if (n.kind === "route") return `${n.verified_inference_count||0}/${n.inference_count||0} inf · ${n.verifier_readiness_level||"needs work"}`;
  if (n.kind === "inference") return `${n.premise_count||0} premise(s) · route ${n.route_id||""}`;
  if (n.kind === "debt") return `${n.debt_type||"debt"} · repeat ${n.repeated_count||0}`;
  if (n.kind === "artifact") return `${n.producer_role||"artifact"} · rev ${n.state_revision ?? ""}`;
  return "";
}
function graphNodeSize(n){
  return n.kind === "artifact" ? {w:48, h:48} : {w:220, h:78};
}
function graphDetailHTML(n, graph){
  if (!n) return `<div class="empty">Select a graph node to inspect its evidence, blockers, and proof role.</div>`;
  const incoming = (graph.edges||[]).filter(e => e.target === n.id).slice(0, 8);
  const outgoing = (graph.edges||[]).filter(e => e.source === n.id).slice(0, 8);
  const rows = [
    ["kind", n.kind],
    ["status", n.status || n.lifecycle_status || "—"],
    ["ref", n.kind === "artifact" ? `${n.artifact_ref || ""} ${n.producer_role_code || ""}`.trim() : ""],
    ["producer", n.kind === "artifact" ? n.producer_role || "" : ""],
    ["revision", n.kind === "artifact" ? n.state_revision ?? "" : ""],
    ["blockers", n.blocking_debt_count != null ? `${n.blocking_debt_count} blocking / ${n.active_debt_count||0} active` : ""],
    ["verifier", n.kind === "route" ? `${n.verifier_ready ? "ready for strict check" : (n.verifier_readiness_level || "not ready")} · score ${n.verifier_readiness_score ?? 0}` : ""],
    ["missing", Array.isArray(n.verifier_missing_checks) ? n.verifier_missing_checks.join(", ") : ""],
    ["incoming", incoming.map(e => `${e.relation}: ${e.source}`).join("\n")],
    ["outgoing", outgoing.map(e => `${e.relation}: ${e.target}`).join("\n")],
  ].filter(r => r[1] !== "" && r[1] != null);
  return `<div class="dtitle">${esc(n.full_label||n.label||n.id)}</div>
    <div class="dgrid">${rows.map(r => `<span>${esc(r[0])}</span><span>${esc(r[1])}</span>`).join("")}</div>
    <div class="dsummary">${esc(n.summary||"")}</div>`;
}
function renderProofGraph(graph){
  graph = graph || {nodes:[], edges:[], summary:{}};
  const nodes = graph.nodes || [], edges = graph.edges || [], summary = graph.summary || {};
  $("graphCount").textContent = nodes.length ? `${nodes.length} nodes · ${edges.length} links` : "";
  $("graphLegend").innerHTML = [
    `<span class="pill info">${summary.claim_count||0} claims</span>`,
    `<span class="pill info">${summary.route_count||0} routes</span>`,
    `<span class="pill warn">${summary.verifier_ready_route_count||0} verifier-ready</span>`,
    `<span class="pill bad">${summary.blocking_debt_count||0} blocking</span>`,
    `<span class="pill mut">${summary.artifact_node_count||0} evidence refs${summary.omitted_artifact_node_count ? ` · ${summary.omitted_artifact_node_count} hidden` : ""}</span>`,
  ].join("");
  const canvas = $("proofGraph");
  if (!nodes.length){
    canvas.innerHTML = `<div class="empty">No proof graph yet.</div>`;
    $("graphDetail").innerHTML = graphDetailHTML(null, graph);
    return;
  }
  const cols = {claim: 30, route: 300, inference: 570, debt: 840, artifact: 1110};
  const labels = {claim:"Claims", route:"Routes", inference:"Inferences", debt:"Open Cases", artifact:"Evidence"};
  const buckets = {claim:[], route:[], inference:[], debt:[], artifact:[]};
  for (const n of nodes) (buckets[n.kind] || (buckets[n.kind]=[])).push(n);
  const positions = {};
  const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]));
  const maxRows = Math.max(1, ...Object.values(buckets).map(v => v.length));
  const height = Math.max(360, 58 + maxRows * 96);
  const width = 1360;
  let html = `<svg class="graphedges" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">`;
  for (const kind of Object.keys(cols)){
    html += `<text x="${cols[kind]+4}" y="24" fill="currentColor" opacity=".55" style="font: 700 11px var(--mono); letter-spacing:.7px; text-transform:uppercase">${esc(labels[kind]||kind)}</text>`;
  }
  for (const kind of Object.keys(buckets)){
    buckets[kind].forEach((n, i) => {
      positions[n.id] = {x: cols[kind], y: 42 + i * 96};
    });
  }
  for (const e of edges){
    const a = positions[e.source], b = positions[e.target];
    if (!a || !b) continue;
    const sourceNode = nodeById[e.source] || {};
    const targetNode = nodeById[e.target] || {};
    const as = graphNodeSize(sourceNode), bs = graphNodeSize(targetNode);
    const x1 = a.x + as.w, y1 = a.y + as.h / 2, x2 = b.x, y2 = b.y + bs.h / 2;
    const mid = Math.max(x1 + 22, (x1 + x2) / 2);
    const cls = e.strength === "blocking" ? "blocking" : (e.strength === "strong" ? "strong" : "");
    html += `<path class="gedge ${cls}" d="M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}" fill="none"></path>`;
  }
  html += `</svg>`;
  for (const n of nodes){
    const p = positions[n.id] || {x:30, y:42};
    html += `<button type="button" class="${esc(graphNodeClass(n))}" data-node="${esc(n.id)}" style="left:${p.x}px;top:${p.y}px" title="${esc(n.full_label||n.summary||n.label||n.id)}">
      <div class="gkind">${esc(n.kind||"")}${n.verifier_ready ? " · verifier-ready" : ""}</div>
      <div class="glabel">${esc(n.label||n.id)}</div>
      <div class="gmeta">${esc(graphMeta(n))}</div>
    </button>`;
  }
  canvas.style.minHeight = `${height}px`;
  canvas.innerHTML = html;
  const selected = nodes.find(n => n.id === selectedGraphNode) || nodes.find(n => n.verifier_ready) || nodes.find(n => Number(n.blocking_debt_count||0)>0) || nodes[0];
  selectedGraphNode = selected ? selected.id : "";
  $("graphDetail").innerHTML = graphDetailHTML(selected, graph);
  canvas.querySelectorAll(".gnode").forEach(btn => btn.addEventListener("click", () => {
    selectedGraphNode = btn.getAttribute("data-node") || "";
    renderProofGraph(graph);
  }));
}

/* ===== Live tail viewer (stream any log/report/artifact) ===== */
let tailFiles = [], tailSel = "", tailUserPicked = false;
async function refreshTailFiles(){
  try {
    const r = await fetch("/api/files", {cache:"no-store"});
    const j = await r.json();
    tailFiles = j.files || [];
    $("tailCount").textContent = tailFiles.length ? `${tailFiles.length} files` : "";
    const sel = $("tailFile");
    const prev = sel.value;
    sel.innerHTML = tailFiles.map(f => `<option value="${esc(f.path)}">${esc(f.label)} · ${fmtBytes(f.size)}</option>`).join("");
    if (tailUserPicked && tailFiles.some(f => f.path === prev)){
      tailSel = prev;
    } else if (!tailUserPicked || !tailFiles.some(f => f.path === tailSel)){
      // Default to the run console (always populated, updated live every poll);
      // then any non-empty completed-step output. The live claude_output.jsonl
      // is buffered until step exit, so it is selectable but not the default.
      const pref = tailFiles.find(f => f.kind === "report" && f.size > 0)
        || tailFiles.find(f => f.path.endsWith("claude_output.jsonl") && f.size > 0)
        || tailFiles.find(f => f.size > 0)
        || tailFiles[0];
      tailSel = pref ? pref.path : "";
    }
    if (tailSel) sel.value = tailSel;
  } catch (e) {}
}
const tailCache = {};
async function fetchTail(){
  if (!tailSel){ return; }
  try {
    const r = await fetch(`/api/tail?path=${encodeURIComponent(tailSel)}&bytes=60000`, {cache:"no-store"});
    const j = await r.json();
    const v = $("tailView");
    if (j.error){ v.innerHTML = `<div class="empty">${esc(j.error)}</div>`; $("tailInfo").textContent = ""; return; }
    const atBottom = v.scrollHeight - v.scrollTop - v.clientHeight < 50;
    let text;
    if (j.text && j.text.length){ text = j.text; tailCache[tailSel] = text; }   // remember last good content
    else if (tailCache[tailSel]){ text = tailCache[tailSel]; }                   // keep it; don't blank out
    else { text = "(empty — no content yet; a buffered session flushes at step end)"; }
    if (v.textContent !== text){ v.textContent = text; }
    $("tailInfo").textContent = `${fmtBytes(j.size)}${j.truncated ? " · showing tail" : ""}`;
    if ($("tailFollow").checked && atBottom) v.scrollTop = v.scrollHeight;
  } catch (e) {}
}
$("tailFile").addEventListener("change", e => { tailUserPicked = true; tailSel = e.target.value; const v=$("tailView"); v.textContent=""; fetchTail(); });
$("tailRefresh").addEventListener("click", () => { refreshTailFiles().then(fetchTail); });
refreshTailFiles().then(fetchTail);
setInterval(refreshTailFiles, 12000);

/* ===== Human steering (see blockers + type guidance, without halting the run) ===== */
async function refreshSteering(){
  try {
    const r = await fetch("/api/steering", {cache:"no-store"});
    const j = await r.json();
    const blk = j.open_blockers || [];
    $("steerCount").textContent = blk.length ? `${blk.length} open blocker(s)` : (j.unconsumed_count ? `${j.unconsumed_count} queued` : "");
    $("steerBlockers").innerHTML = blk.length
      ? blk.map(b => `<div class="blocker"><div class="bhead">⚑ ${esc(b.summary||"")}</div>${b.detail?`<div class="bdetail">${esc(b.detail)}</div>`:""}${(b.options||[]).length?`<div class="bopts">${b.options.map(o=>`<button class="btn chiplike" data-blk="${esc(b.id)}" data-opt="${esc(o)}">${esc(o)}</button>`).join("")}</div>`:""}</div>`).join("")
      : `<div class="empty">No open blockers — the run is proceeding autonomously. Type guidance any time; it is delivered on the next step.</div>`;
    const sel = $("steerBlockerSel"); const cur = sel.value;
    sel.innerHTML = `<option value="">general steer</option>` + blk.map(b => `<option value="${esc(b.id)}">answer: ${esc((b.summary||"").slice(0,44))}…</option>`).join("");
    if (blk.some(b => b.id === cur)) sel.value = cur;
    const inbox = (j.recent_inbox || []).slice(-6).reverse();
    $("steerLog").innerHTML = inbox.length
      ? `<div class="group-h">recent steering</div>` + inbox.map(m => `<div class="sig"><span class="pill ${m.consumed?'good':'warn'}">${m.consumed?'delivered':'queued'}</span><div style="color:var(--muted)">${esc(m.text)}</div></div>`).join("")
      : "";
    document.querySelectorAll('#steerBlockers .chiplike').forEach(btn => btn.addEventListener('click', () => {
      $("steerText").value = btn.dataset.opt === '(type your own guidance)' ? '' : btn.dataset.opt;
      $("steerBlockerSel").value = btn.dataset.blk; $("steerText").focus();
    }));
  } catch (e) {}
}
async function sendSteering(){
  const text = $("steerText").value.trim();
  if (!text){ $("steerMsg").textContent = "type some guidance first"; return; }
  $("steerMsg").textContent = "sending…";
  try {
    const r = await fetch("/api/steer", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({text, blocker_id: $("steerBlockerSel").value || null})});
    const j = await r.json();
    if (j.ok){ $("steerText").value = ""; $("steerMsg").textContent = "✓ sent — the run picks it up on the next step"; refreshSteering(); }
    else { $("steerMsg").textContent = j.error || "error"; }
  } catch (e){ $("steerMsg").textContent = "send failed"; }
}
$("steerSend").addEventListener("click", sendSteering);
$("steerText").addEventListener("keydown", e => { if ((e.metaKey||e.ctrlKey) && e.key === "Enter") sendSteering(); });
refreshSteering();
setInterval(refreshSteering, 5000);

function renderRunbar(mon){
  const bar = $("runbar");
  const st = String(mon.run_state || "unknown");
  const live = !!mon.live;
  const secs = Number(mon.seconds_since_activity);
  const ageTxt = isFinite(secs) ? fmtSec(secs)+" ago" : "—";
  let cls, label, sub;
  if (st === "running"){ cls="running"; label="● SYSTEM RUNNING"; sub="live agent active · last write "+ageTxt; }
  else if (st === "stalled" && live){ cls="running"; label="◑ DEEP STEP ACTIVE"; sub="live child running · quiet output for "+ageTxt+" · tokens may post at step end"; }
  else if (st === "stalled"){ cls="stalled"; label="◐ SYSTEM STALLED?"; sub="no write for "+ageTxt+" · no live child heartbeat found"; }
  else if (st === "stopped"){ cls="stopped"; label="■ SYSTEM STOPPED"; sub="no activity for "+ageTxt+" · the run has exited — needs a resume"; }
  else { cls="unknown"; label="… status unknown"; sub="no run activity found yet"; }
  bar.className = "runbar "+cls;
  bar.innerHTML = `<span class="rdot"></span><span>${label}</span><span class="rsub">${esc(sub)}</span>`;
}

async function tick(){
  if (paused) return;
  try {
    const res = await fetch("/api/console", {cache:"no-store"});
    if (!res.ok) throw new Error("HTTP "+res.status);
    const p = await res.json();
    lastOk = Date.now();
    $("errbar").style.display = "none";
    const snap = p.snapshot || {}, mon = p._monitor || {};
    $("pid").textContent = mon.problem_id || p.problem_id || "";
    document.title = `${(snap.public_status||"run")} · Albilich Monitor`;
    const sb = $("statusBadge"); sb.className = "badge "+STATUS_CLASS(snap.public_status); sb.textContent = snap.public_status || "—";
    $("revBadge").textContent = "rev " + (snap.revision!=null?snap.revision:"—");
    const live = !!mon.live;
    $("liveDot").className = "dot " + (live?"on":"");
    $("liveText").textContent = live ? "live" : (mon.source==="console_file"?"idle":"snapshot");
    renderRunbar(mon);
    renderKpis(snap);
    renderPipeline(p, activeStep(p));
    renderProofSpine(p.proof_spine_status);
    renderBottleneck(p.bottleneck_frontier);
    renderResearcherMode(p.researcher_mode_state);
    renderTokens(snap, p.usage_summary || {});
    renderClaims(p.claims);
    renderProofGraph(p.proof_graph);
    renderSession(p);
    renderRoutes(p.route_scoreboard);
    renderDebts(p.open_cases);
    renderSignals(p.parallel_exchange);
    renderTimeline(p.run_timeline);
    renderArtifacts(p.recent_research_artifacts);
    if (!paused) fetchTail();
    $("foot").textContent = `source: ${mon.source||"?"} · ${snap.summary||""} · ${snap.verifier_health||""}`;
  } catch (e){
    const bar = $("errbar"); bar.style.display = "block"; bar.textContent = "connection lost: "+e.message+" — retrying… "+ago();
    $("liveDot").className = "dot"; $("liveText").textContent = "disconnected";
    const rb = $("runbar"); rb.className = "runbar disconnected";
    rb.innerHTML = `<span class="rdot"></span><span>■ MONITOR UNREACHABLE</span><span class="rsub">cannot reach the monitor server — retrying…</span>`;
  } finally { $("updated").textContent = ago(); }
}

// Dashboard pause is DISPLAY-ONLY: it freezes browser refreshes and never
// touches the backend. A true run pause goes through the CLI:
//   python -m agents.generation.phase2.cli pause <problem>   (soft pause)
//   python -m agents.generation.phase2.cli stop --hard <problem>
$("pauseBtn").addEventListener("click", () => {
  paused = !paused;
  $("pauseBtn").textContent = paused ? "▶ Resume dashboard" : "⏸ Pause dashboard";
  if (paused){
    const rb = $("runbar"); rb.className = "runbar stalled";
    rb.innerHTML = `<span class="rdot"></span><span>⏸ DASHBOARD PAUSED</span><span class="rsub">Dashboard paused; Albilich run is still active. Display refresh only — to pause the run itself use: python -m agents.generation.phase2.cli pause &lt;problem&gt;</span>`;
  } else {
    tick();
  }
});
$("refreshBtn").addEventListener("click", tick);
setInterval(() => $("updated").textContent = ago(), 1000);
tick();
setInterval(tick, POLL_MS);
</script>
</body>
</html>
"""
