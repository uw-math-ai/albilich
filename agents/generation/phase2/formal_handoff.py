from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .models import utc_now
from .store import ProofStateStore

VERIFIED = {"informally_verified", "formally_verified"}


def build_formalization_manifest(store: ProofStateStore, *, claim_id: str = "root", route_id: Optional[str] = None) -> Dict[str, Any]:
    state = store.get_state()
    claim = next((row for row in state["claims"] if row["claim_id"] == claim_id), None)
    if claim is None:
        raise ValueError(f"unknown claim: {claim_id}")
    if route_id is None:
        route = next((row for row in state["routes"] if row["conclusion_claim_id"] == claim_id and row["status"] == "integrated"), None)
        if route is None:
            route = next((row for row in state["routes"] if row["conclusion_claim_id"] == claim_id), None)
    else:
        route = next((row for row in state["routes"] if row["route_id"] == route_id), None)
    route_id = route["route_id"] if route else ""
    return {
        "manifest_version": 1,
        "created_at": utc_now(),
        "problem_id": store.problem_id,
        "state_revision": state["problem_state"]["current_revision"],
        "claim": _claim_card(claim),
        "route": route,
        "verified_claims": [_claim_card(row) for row in state["claims"] if row["validation_status"] in VERIFIED],
        "verified_inferences": [row for row in state["inferences"] if row["route_id"] == route_id and row["validation_status"] in VERIFIED],
        "artifacts": state["artifacts"],
        "notes": [
            "This is a formalization handoff manifest, not a formal proof certificate.",
            "A backend-specific artifact must be attached before any formally_verified transition.",
        ],
    }


def write_formalization_manifest(store: ProofStateStore, *, claim_id: str = "root", route_id: Optional[str] = None) -> Path:
    manifest = build_formalization_manifest(store, claim_id=claim_id, route_id=route_id)
    path = store.state_dir / "formal_handoff" / f"{claim_id}_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return path


def _claim_card(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "claim_id": row["claim_id"],
        "kind": row["kind"],
        "statement": row["statement"],
        "validation_status": row["validation_status"],
        "lifecycle_status": row["lifecycle_status"],
        "conditions_json": row.get("conditions_json", "[]"),
        "evidence_artifact_ids_json": row.get("evidence_artifact_ids_json", "[]"),
    }
