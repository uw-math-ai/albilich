from __future__ import annotations

from typing import Any, Dict, Mapping

from .models import SCHEMA_VERSION, fingerprint_text
from .store import ProofStateStore

VERIFIED = {"informally_verified", "formally_verified"}


def evaluate_route_for_integration(store: ProofStateStore, route_id: str) -> Dict[str, Any]:
    state = store.get_state()
    route = next((row for row in state["routes"] if row["route_id"] == route_id), None)
    if route is None:
        raise ValueError(f"unknown route: {route_id}")
    missing: list[str] = []
    if route["relation_to_parent"] != "sufficient":
        missing.append("route is not sufficient")
    claim_status = {row["claim_id"]: row["validation_status"] for row in state["claims"]}
    if claim_status.get(route["conclusion_claim_id"]) not in VERIFIED:
        missing.append(f"claim {route['conclusion_claim_id']} is not verified")
    debts = [row for row in state["debts"] if row["status"] == "active" and row["severity"] == "blocking" and row["owner_id"] in {route_id, route["conclusion_claim_id"]}]
    if debts:
        missing.append("active blocking debt")
    route_inferences = [row for row in state["inferences"] if row["route_id"] == route_id]
    if not route_inferences:
        missing.append("route has no inferences")
    terminal_inferences = [
        inf
        for inf in route_inferences
        if str(inf.get("conclusion_claim_id") or "") == str(route["conclusion_claim_id"])
        and inf["validation_status"] in VERIFIED
        and all(claim_status.get(premise_id) in VERIFIED for premise_id in inf.get("premise_claim_ids", []))
    ]
    if route_inferences and not terminal_inferences:
        missing.append("route has no verified terminal inference with verified premises")
    return {
        "route_id": route_id,
        "claim_id": route["conclusion_claim_id"],
        "integrates": not missing,
        "missing": missing,
        "terminal_inference_ids": sorted(
            str(inf["inference_id"]) for inf in terminal_inferences
        ),
    }


def integration_patch(store: ProofStateStore, *, route_id: str, report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    evaluation = evaluate_route_for_integration(store, route_id)
    claim_id = evaluation["claim_id"]
    artifact_id = f"integration-report-{fingerprint_text(route_id + str(evaluation), length=16)}"
    metadata = dict(report or {})
    metadata.update(evaluation)
    metadata["integrates"] = bool(evaluation["integrates"])
    if claim_id == "root":
        alignment = metadata.get("root_alignment") or metadata.get("statement_alignment")
        if not isinstance(alignment, Mapping):
            raise ValueError("root integration requires explicit root_alignment metadata from the integration verifier")
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": store.problem_id,
        "base_revision": store.get_revision(),
        "actor_role": "integration_verifier",
        "target_id": claim_id,
        "operations": [
            {
                "op": "attach_artifact",
                "artifact_id": artifact_id,
                "artifact_type": "integration_report",
                "content_summary": "integration check for route " + route_id,
                "metadata": metadata,
            },
            {
                "op": "propose_status_transition",
                "target_type": "claim",
                "target_id": claim_id,
                "status_type": "lifecycle",
                "new_status": "integrated",
                "route_id": route_id,
                "evidence_artifact_ids": [artifact_id],
            },
        ],
        "rationale": "integrate verified sufficient route into parent proof state",
    }
