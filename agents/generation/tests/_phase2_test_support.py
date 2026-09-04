from __future__ import annotations

import sqlite3
from typing import Any, Callable

from agents.generation.phase2.authority import PatchAuthority
from agents.generation.phase2.invariants import validate_conn
from agents.generation.phase2.models import SCHEMA_VERSION, utc_now
from agents.generation.phase2.patches import (
    _state_delta,
    _state_journal_projection,
    _state_projection_hash,
    _run_provenance_hash,
    append_applied_patch_entry,
    apply_operator_patch,
)
from agents.generation.phase2.store import ProofStateStore


def journal_legacy_fixture_mutation(
    store: ProofStateStore,
    mutation: Callable[[sqlite3.Connection, int], None],
    *,
    fixture_id: str,
) -> int:
    """Record a deliberately pre-guard test fixture as an exact replay delta.

    A few scheduler tests need malformed historical documents that the current
    writer guard correctly refuses to create.  They may model that legacy
    input, but they must not bypass the journal or invalidate the state seal.
    This helper is test-only and records the complete row delta under explicit
    migration authority.
    """

    with store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current_revision = store.get_revision(conn)
        seal = store.current_state_seal(conn)
        if not seal["valid"]:
            conn.rollback()
            raise AssertionError(seal["errors"])
        state_before = _state_journal_projection(conn)
        new_revision = current_revision + 1
        mutation(conn, new_revision)
        errors = validate_conn(conn)
        if errors:
            conn.rollback()
            raise AssertionError(errors)
        now = utc_now()
        conn.execute(
            "UPDATE problem_state SET current_revision = ?, updated_at = ? "
            "WHERE problem_id = ?",
            (new_revision, now, store.problem_id),
        )
        state_after = _state_journal_projection(conn)
        state_hash_before = _state_projection_hash(state_before)
        state_hash_after = _state_projection_hash(state_after)
        run_provenance_hash = _run_provenance_hash(conn)
        authority = PatchAuthority(
            source="migration",
            actor_role="test_fixture_migration",
            mode="fixture_import",
            target_id="root",
            context_revision=current_revision,
        )
        patch_id = f"fixture-{fixture_id}-{new_revision}"
        journal_head = append_applied_patch_entry(
            conn,
            patch_id=patch_id,
            problem_id=store.problem_id,
            base_revision=current_revision,
            actor_role=authority.actor_role,
            target_id="root",
            operations=[{"op": "legacy_fixture_import", "fixture_id": fixture_id}],
            evidence_artifact_ids=[],
            rationale="test-only import of an explicitly legacy pre-guard fixture",
            created_at=now,
            applied_revision=new_revision,
            authority=authority,
            state_delta=_state_delta(state_before, state_after),
            state_hash_before=state_hash_before,
            state_hash_after=state_hash_after,
        )
        conn.execute(
            "UPDATE problem_state SET proof_state_hash = ?, run_provenance_hash = ?, "
            "patch_journal_head = ? "
            "WHERE problem_id = ?",
            (
                state_hash_after,
                run_provenance_hash,
                journal_head,
                store.problem_id,
            ),
        )
        store.write_event(
            conn,
            new_revision,
            "legacy_fixture_imported",
            {"fixture_id": fixture_id, "journal_entry_hash": journal_head},
        )
        conn.commit()
    return new_revision


def strictly_verify_entities(
    store: ProofStateStore,
    *,
    target_id: str,
    claim_ids: list[str],
    inference_ids: list[str],
    artifact_id: str,
) -> str:
    """Verify several fixture entities with one real zero-gap report."""

    operations: list[dict[str, Any]] = [
        {
            "op": "attach_artifact",
            "artifact_id": artifact_id,
            "artifact_type": "verification_report",
            "content": (
                f"Verdict: informally verified for {target_id}. "
                "Critical errors: none. Gaps: none."
            ),
            "metadata": {
                "verdict": "informally_verified",
                "verification_report": {
                    "checked_items": ["all named fixture entities"],
                    "critical_errors": [],
                    "gaps": [],
                    "blocking_gap": False,
                },
            },
        }
    ]
    # Premise claims must be certified before a dependent inference is
    # transitioned.  The entire patch is still atomic, but this ordering also
    # satisfies the apply-time recursive-grounding check.
    for claim_id in claim_ids:
        operations.append(
            {
                "op": "propose_status_transition",
                "target_type": "claim",
                "target_id": claim_id,
                "status_type": "validation",
                "new_status": "informally_verified",
                "evidence_artifact_ids": [artifact_id],
            }
        )
    for inference_id in inference_ids:
        operations.append(
            {
                "op": "propose_status_transition",
                "target_type": "inference",
                "target_id": inference_id,
                "status_type": "validation",
                "new_status": "informally_verified",
                "evidence_artifact_ids": [artifact_id],
            }
        )
    outcome = apply_operator_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "strict_informal_verifier",
            "target_id": target_id,
            "operations": operations,
            "rationale": "strictly verify a sound test fixture",
        },
    )
    if not outcome.accepted:
        raise AssertionError(outcome.errors)
    return artifact_id


def certify_and_integrate_claim(
    store: ProofStateStore,
    *,
    claim_id: str = "root",
    statement: str = "",
    route_id: str = "",
    inference_id: str = "",
    parent_ids: list[str] | None = None,
    premise_claim_ids: list[str] | None = None,
    proof_artifact_id: str = "",
    verification_artifact_id: str = "",
    integration_artifact_id: str = "",
) -> dict[str, str]:
    """Create a genuinely certified sufficient route for a test fixture.

    Tests that exercise post-proof behavior must not manufacture a verified
    database with direct SQL: doing so would make the fixture invalid under the
    same certificate invariants that production uses.  This helper traverses
    the ordinary researcher, strict-verifier, and integration-verifier patch
    boundaries and therefore receives real host-computed certificate bindings.
    """

    route_id = route_id or f"route-{claim_id}"
    inference_id = inference_id or f"inf-{claim_id}"
    verification_id = verification_artifact_id or f"verification-{claim_id}"
    integration_id = integration_artifact_id or f"integration-{claim_id}"
    state = store.get_state()
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    if claim_id in claims:
        claim_statement = str(claims[claim_id].get("statement") or statement or claim_id)
    else:
        claim_statement = statement or f"Certified theorem {claim_id}."

    seed_operations: list[dict[str, Any]] = []
    if claim_id not in claims:
        seed_operations.append(
            {
                "op": "add_claim",
                "claim_id": claim_id,
                "kind": "lemma",
                "statement": claim_statement,
                "parent_ids": list(parent_ids or ["root"]),
                "root_impact": 0.5,
                "reduction_depth": 1,
            }
        )
    if proof_artifact_id:
        seed_operations.append(
            {
                "op": "attach_artifact",
                "artifact_id": proof_artifact_id,
                "artifact_type": "proof_dossier",
                "content": f"# {proof_artifact_id}\n\nA complete proof dossier for {claim_id}.",
                "metadata": {"target_id": claim_id, "route_id": route_id},
            }
        )
    seed_operations.extend(
        [
            {
                "op": "add_route",
                "route_id": route_id,
                "conclusion_claim_id": claim_id,
                "relation_to_parent": "sufficient",
                "strategy": "Direct proof used by the test fixture.",
            },
            {
                "op": "add_inference",
                "inference_id": inference_id,
                "route_id": route_id,
                "conclusion_claim_id": claim_id,
                "premise_claim_ids": list(premise_claim_ids or []),
                "validation_status": "plausible",
                "explanation": "A complete direct proof of the stated claim.",
                "evidence_artifact_ids": [proof_artifact_id] if proof_artifact_id else [],
            },
        ]
    )
    seed = apply_operator_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "researcher",
            "target_id": claim_id,
            "operations": seed_operations,
            "rationale": "seed a proof route for a sound test fixture",
        },
    )
    if not seed.accepted:
        raise AssertionError(seed.errors)

    strictly_verify_entities(
        store,
        target_id=claim_id,
        claim_ids=[claim_id],
        inference_ids=[inference_id],
        artifact_id=verification_id,
    )

    integration_metadata: dict[str, Any] = {
        "integrates": True,
        "route_id": route_id,
        "claim_id": claim_id,
    }
    if claim_id == "root":
        integration_metadata["root_alignment"] = {
            "relation_to_root": "exact",
            "target_statement": claim_statement,
            "proved_statement": claim_statement,
            "implication_verified": True,
            "hidden_assumptions": False,
            "extra_assumptions": [],
        }
    integrated = apply_operator_patch(
        store,
        {
            "schema_version": SCHEMA_VERSION,
            "problem_id": store.problem_id,
            "base_revision": store.get_revision(),
            "actor_role": "integration_verifier",
            "target_id": claim_id,
            "operations": [
                {
                    "op": "attach_artifact",
                    "artifact_id": integration_id,
                    "artifact_type": "integration_report",
                    "content": f"The certified route {route_id} proves exactly {claim_id}.",
                    "metadata": integration_metadata,
                },
                {
                    "op": "propose_status_transition",
                    "target_type": "claim",
                    "target_id": claim_id,
                    "status_type": "lifecycle",
                    "new_status": "integrated",
                    "route_id": route_id,
                    "evidence_artifact_ids": [integration_id],
                },
            ],
            "rationale": "integrate the certified test fixture",
        },
    )
    if not integrated.accepted:
        raise AssertionError(integrated.errors)
    return {
        "claim_id": claim_id,
        "route_id": route_id,
        "inference_id": inference_id,
        "verification_artifact_id": verification_id,
        "integration_artifact_id": integration_id,
    }
