from __future__ import annotations

from typing import Any, Dict, Mapping

from .models import SCHEMA_VERSION, fingerprint_text
from .store import ProofStateStore


def candidate_counterexample_patch(
    store: ProofStateStore,
    *,
    claim_id: str,
    description: str,
    metadata: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    artifact_id = f"candidate-counterexample-{fingerprint_text(claim_id + description, length=16)}"
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": store.problem_id,
        "base_revision": store.get_revision(),
        "actor_role": "villain",
        "target_id": claim_id,
        "operations": [
            {
                "op": "attach_artifact",
                "artifact_id": artifact_id,
                "artifact_type": "candidate_counterexample",
                "content_summary": description,
                "metadata": dict(metadata or {}, description=description),
            },
            {
                "op": "propose_status_transition",
                "target_type": "claim",
                "target_id": claim_id,
                "status_type": "validation",
                "new_status": "challenged",
                "evidence_artifact_ids": [artifact_id],
            },
        ],
        "rationale": "record candidate counterexample for independent validation",
    }


def confirmed_counterexample_patch(
    store: ProofStateStore,
    *,
    claim_id: str,
    description: str,
    metadata: Mapping[str, Any] | None = None,
    allow_root: bool = False,
) -> Dict[str, Any]:
    artifact_id = f"confirmed-counterexample-{fingerprint_text(claim_id + description, length=16)}"
    op = {
        "op": "propose_status_transition",
        "target_type": "claim",
        "target_id": claim_id,
        "status_type": "validation",
        "new_status": "refuted",
        "evidence_artifact_ids": [artifact_id],
    }
    if allow_root:
        op["confirmed_root_counterexample"] = True
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": store.problem_id,
        "base_revision": store.get_revision(),
        "actor_role": "counterexample_validator",
        "target_id": claim_id,
        "operations": [
            {
                "op": "attach_artifact",
                "artifact_id": artifact_id,
                "artifact_type": "confirmed_counterexample",
                "content_summary": description,
                "metadata": dict(metadata or {}, description=description, confirmed=True),
            },
            op,
        ],
        "rationale": "independent counterexample validation",
    }
