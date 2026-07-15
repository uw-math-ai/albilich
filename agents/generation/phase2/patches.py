from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .artifacts import artifact_hash, artifact_summary
from .graph_policy import obvious_duplicate_claim_id, obvious_duplicate_route_id
from .invariants import VERIFIED_STATUSES, validate_conn
from .models import (
    CLAIM_KINDS,
    DEBT_SEVERITIES,
    DEBT_STATUSES,
    INFERENCE_STATUSES,
    LIFECYCLE_STATUSES,
    ROUTE_RELATIONS,
    ROUTE_STATUSES,
    RUN_MODES,
    SCHEMA_VERSION,
    VALIDATION_STATUSES,
    NON_VERIFYING_ROLES,
    VERIFYING_ROLES,
    PatchOutcome,
    fingerprint_text,
    json_dumps,
    json_loads,
    normalize_text,
    statement_is_interrogative_problem,
    utc_now,
)
from .budget import run_spend_from_operation
from .receipt import compile_latex_artifact, format_partial_receipt_appendix, receipt_appendix_present, write_latex_pdf_sidecars
from .research_strategy import STRATEGIC_MARKDOWN_ARTIFACT_TYPES, strategic_artifact_errors
from .research_policy import normalize_retrieval_relation, theorem_matching_confidence
from .result_status import SOLVED_RELATIONS, root_alignment_from_metadata
from .store import ProofStateStore
from .writing.latex_template import normalize_paper_template
from .writing.linter import run_paper_lint, run_residue_scan


class PatchRejected(Exception):
    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


ARTIFACT_PRODUCER_ROLES = {
    "verification_report": {"strict_informal_verifier"},
    "formal_backend_result": {"formal_backend"},
    "confirmed_counterexample": {"counterexample_validator"},
    "integration_report": {"integration_verifier"},
    "referee_report": {"writer"},
    "writing_review": {"writing_critic"},
    "final_paper": {"writer"},
    "advisor_synthesis": {"phd_advisor", "advisor"},
    "invention_authorization": {"phd_advisor", "advisor"},
    "bridge_lemma_search": {"researcher"},
    "conjecture_portfolio": {"researcher", "villain"},
    "definition_candidate": {"researcher"},
    "deep_session_report": {"researcher"},
    "proof_compression": {"researcher", "phd_advisor", "advisor"},
}
STRICT_VERIFIER_ARTIFACT_TYPES = {"verification_report"}
WRITING_CRITIC_ROLE = "writing_critic"
WRITING_CRITIC_ARTIFACT_TYPES = {"writing_review"}
WRITING_REVIEW_VERDICTS = {"pass", "fail"}
# "editor" is the single lens the scheduler dispatches; the legacy three-lens
# names stay accepted so old review data still parses.
WRITING_CRITIC_LENSES = {"editor", "confused_reader", "skeptical_editor", "provenance_auditor"}
# Writer artifact types scanned for generation residue (rule L1-CITE-03) at
# patch time; residue in the shipped exposition is always rejected.
WRITER_RESIDUE_SCANNED_ARTIFACT_TYPES = {"final_proof", "partial_proof_report", "final_paper"}
# Artifact types whose file extension is not the markdown/txt default; the
# final_paper's content IS complete LaTeX source, so it ships as a .tex file
# that the attach-time sidecar compiles directly (no markdown->LaTeX pass).
ARTIFACT_CONTENT_EXTENSIONS = {"final_paper": ".tex"}
LITERATURE_RESEARCHER_ROLE = "literature_researcher"
GRAPH_OWNER_ROLE_NAMES = VERIFYING_ROLES | NON_VERIFYING_ROLES | {
    "strict_verifier",
    "phd_advisor",
    "advisor",
}
WRITER_REFERENCE_REQUIRED_ARTIFACT_TYPES = {
    "final_proof",
    "partial_proof_report",
    "proof_compression_report",
    "stop_summary_report",
    "writer_report",
}
# Writer artifact types that may be attached BY PATH instead of inline content
# (final_paper especially): the writer authors the document as a real file
# under state_dir/artifacts/ — recommended staging path
# state_dir/artifacts/staging/<artifact_id>.tex, which _validated_artifact_path
# already permits because it resolves under the artifacts root — and attaches
# with {"op": "attach_artifact", "path": ...} and NO content field, so the
# LaTeX never passes through JSON string escaping. The staged file is loaded
# (size-capped), run through the full writer guard chain exactly as inline
# content, then COPIED to the standard artifacts/<artifact_id>.<ext> location;
# the recorded artifact never points at the mutable staging file.
WRITER_PATH_ATTACH_ARTIFACT_TYPES = (
    WRITER_RESIDUE_SCANNED_ARTIFACT_TYPES | WRITER_REFERENCE_REQUIRED_ARTIFACT_TYPES
)
WRITER_PATH_ATTACH_MAX_BYTES = 2 * 1024 * 1024
REFERENCE_SECTION_RE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s+References|References|\\section\*?\{References\})\s*$"
)
FINAL_PROOF_RE = re.compile(r"(?im)(?:^|\n)\s*(?:(?:#{1,6}\s+)?[*_]{0,2}Proof(?:\.|\b)[*_]{0,2}|\\begin\{proof\})")
WRITER_RAW_LEDGER_MARKERS = (
    '"schema_version"',
    '"problem_id"',
    '"base_revision"',
    '"operations"',
    '"claims"',
    '"routes"',
    '"inferences"',
    '"metadata_json"',
    '"parent_ids_json"',
    '"evidence_artifact_ids_json"',
    '"lifecycle_status"',
)
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def preflight_patch_errors(patch: Mapping[str, Any], actor_role: str) -> List[str]:
    """Runner-side contract checks that predict certain guard rejections.

    Only violations that are decidable from the patch alone are flagged, so the
    session that produced the patch can repair it in place instead of losing the
    whole step to a workflow rejection. Anything that needs store state stays
    with apply_patch.
    """
    try:
        normalized = _normalize_patch_aliases(dict(patch))
    except Exception:
        return []
    operations = [op for op in normalized.get("operations") or [] if isinstance(op, Mapping)]
    attached_ops = {
        str(op.get("artifact_id") or ""): op
        for op in operations
        if str(op.get("op") or "") in {"attach_artifact", "add_artifact"}
    }
    errors: List[str] = []
    for op in operations:
        if str(op.get("op") or "") != "propose_status_transition":
            continue
        new_status = str(op.get("new_status") or "")
        target_id = str(op.get("target_id") or "")
        if not target_id:
            errors.append(
                "propose_status_transition is missing its target: set target_id (or claim_id/inference_id/route_id)"
            )
            continue
        if not new_status:
            errors.append(
                f"propose_status_transition for {target_id} is missing new_status (set new_status plus status_type validation|lifecycle)"
            )
            continue
        if new_status in {"informally_verified", "formally_verified", "refuted"} and actor_role not in VERIFYING_ROLES:
            errors.append(
                f"actor_role={actor_role} may not propose new_status={new_status}; attach the evidence artifact and "
                "let a verifying role certify the transition"
            )
            continue
        if new_status == "integrated" and actor_role != "integration_verifier":
            errors.append("integrated lifecycle transitions require the integration_verifier role")
            continue
        if new_status == "informally_verified" and actor_role == "strict_informal_verifier":
            evidence_ids = [
                str(item)
                for item in (op.get("evidence_artifact_ids") or normalized.get("evidence_artifact_ids") or [])
                if str(item or "")
            ]
            if not evidence_ids:
                errors.append(
                    f"transition of {target_id} to informally_verified cites no evidence_artifact_ids; attach your "
                    "verification_report and reference it"
                )
                continue
            same_patch = [attached_ops[e] for e in evidence_ids if e in attached_ops]
            external = [e for e in evidence_ids if e not in attached_ops]
            if external and not same_patch:
                continue  # store-side evidence: apply_patch decides
            clean = False
            dirty_reason = ""
            for attach_op in same_patch:
                if str(attach_op.get("artifact_type") or "") != "verification_report":
                    continue
                metadata = attach_op.get("metadata") if isinstance(attach_op.get("metadata"), Mapping) else {}
                report = (
                    metadata.get("verification_report")
                    if isinstance(metadata.get("verification_report"), Mapping)
                    else {}
                )
                verdict = str(metadata.get("verdict") or report.get("verdict") or "").strip().lower()
                if verdict not in ZERO_GAP_VERIFICATION_VERDICTS:
                    dirty_reason = (
                        f"verification_report verdict '{verdict or 'missing'}' does not certify; use one of "
                        f"{sorted(ZERO_GAP_VERIFICATION_VERDICTS)} only when errors and gaps are genuinely empty"
                    )
                    continue
                if report.get("critical_errors") or report.get("gaps") or report.get("blocking_gap"):
                    dirty_reason = (
                        "verification_report still lists critical_errors/gaps/blocking_gap; do not propose "
                        "informally_verified — attach the report and add precise debts instead"
                    )
                    continue
                clean = True
                break
            if not clean:
                errors.append(
                    dirty_reason
                    or f"transition of {target_id} to informally_verified does not cite a clean verification_report "
                    "attached in this patch"
                )
    return errors


# Op kinds that only add rows or propose guarded transitions; safe to rebase
# onto a newer revision when row-disjoint from the intervening patches, because
# every apply-time guard re-runs against the current state anyway.
SAFE_REBASE_OP_KINDS = {
    "attach_artifact",
    "add_artifact",
    "add_claim",
    "add_route",
    "add_inference",
    "update_inference",
    "add_debt",
    "update_debt",
    "resolve_debt",
    "cache_retrieval_card",
    "record_run_metrics",
    "propose_status_transition",
}
NON_VERIFYING_TRANSITION_STATUSES = {"untested", "plausible", "challenged", "active", "blocked", "abandoned"}
REBASE_SAFE_VERIFYING_TRANSITIONS = {
    ("strict_informal_verifier", "informally_verified"),
    ("strict_informal_verifier", "refuted"),
    ("formal_backend", "formally_verified"),
    ("counterexample_validator", "refuted"),
}


def _op_touched_ids(op: Mapping[str, Any]) -> tuple[set[str], bool]:
    """Rows one operation writes, as type-prefixed ids; True means unknown scope."""
    kind = str(op.get("op") or "")
    ids: set[str] = set()

    def _add(prefix: str, value: Any) -> bool:
        text = str(value or "")
        if not text:
            return False
        ids.add(f"{prefix}:{text}")
        return True

    if kind in {"attach_artifact", "add_artifact"}:
        if not _add("artifact", op.get("artifact_id")):
            return ids, True
    elif kind in {"add_claim", "update_claim", "set_claim_status"}:
        if not _add("claim", op.get("claim_id") or op.get("target_id")):
            return ids, True
    elif kind in {"add_route", "update_route", "abandon_route", "reactivate_route"}:
        if not _add("route", op.get("route_id")):
            return ids, True
        _add("claim", op.get("conclusion_claim_id"))
    elif kind in {"add_inference", "update_inference", "set_inference_status"}:
        if not _add("inference", op.get("inference_id") or op.get("target_id")):
            return ids, True
        _add("route", op.get("route_id"))
    elif kind in {"add_debt", "update_debt", "resolve_debt"}:
        if not _add("debt", op.get("debt_id")):
            return ids, True
    elif kind == "propose_status_transition":
        target = op.get("target_id") or op.get("claim_id") or op.get("inference_id") or op.get("route_id")
        target_type = str(op.get("target_type") or "claim")
        if not _add(target_type, target):
            return ids, True
    elif kind == "cache_retrieval_card":
        if not _add("card", op.get("card_id")):
            return ids, True
    elif kind == "certify_external_citation":
        if not _add("card", op.get("card_id")):
            return ids, True
        _add("claim", op.get("target_id"))
    elif kind == "record_run_metrics":
        if not _add("run", op.get("run_id")):
            return ids, True
    else:
        return ids, True
    return ids, False


def _patch_touched_ids(operations: Any) -> tuple[set[str], bool]:
    ids: set[str] = set()
    unknown = False
    for op in operations or []:
        if not isinstance(op, Mapping):
            unknown = True
            continue
        op_ids, op_unknown = _op_touched_ids(op)
        ids |= op_ids
        unknown = unknown or op_unknown
    return ids, unknown


def _is_commutative_inference_update(op: Mapping[str, Any]) -> bool:
    """Whether an inference update is an append-only merge operation."""
    if str(op.get("op") or "") != "update_inference":
        return False
    allowed = {
        "op",
        "inference_id",
        "target_id",
        "add_evidence_artifact_ids",
        "evidence_artifact_ids",
        "explanation_append",
        "argument_summary_append",
    }
    return bool(op.get("inference_id") or op.get("target_id")) and set(op).issubset(allowed)


def _commutative_inference_ids(operations: Sequence[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    conflicting: set[str] = set()
    for op in operations:
        touched, _ = _op_touched_ids(op)
        inference_ids = {item for item in touched if item.startswith("inference:")}
        if not inference_ids:
            continue
        if _is_commutative_inference_update(op):
            ids |= inference_ids
        else:
            conflicting |= inference_ids
    return ids - conflicting


def _commutative_status_transition_signatures(
    operations: Sequence[Mapping[str, Any]],
) -> Dict[str, tuple[str, str, str]]:
    """Return rows touched only by one idempotent status transition.

    Repeating the same transition is safe because ``_status_transition`` unions
    evidence ids and apply-time verification guards run again after rebasing.
    Any other operation on the row, or competing transition targets, makes the
    row non-commutative.
    """
    signatures: Dict[str, set[tuple[str, str, str]]] = {}
    conflicting: set[str] = set()
    for op in operations:
        touched, unknown = _op_touched_ids(op)
        if unknown or not touched:
            continue
        if str(op.get("op") or "") != "propose_status_transition" or len(touched) != 1:
            conflicting |= touched
            continue
        row_id = next(iter(touched))
        signature = (
            str(op.get("target_type") or "claim"),
            str(op.get("status_type") or "validation"),
            str(op.get("new_status") or ""),
        )
        if not signature[2]:
            conflicting.add(row_id)
            continue
        signatures.setdefault(row_id, set()).add(signature)
    return {
        row_id: next(iter(row_signatures))
        for row_id, row_signatures in signatures.items()
        if row_id not in conflicting and len(row_signatures) == 1
    }


def _stale_rebase_assessment(store: ProofStateStore, patch: Mapping[str, Any]) -> Dict[str, Any]:
    """Decide whether a stale patch can be retried against the current revision.

    Requires (1) every op of the stale patch to be a safe additive/non-verifying
    kind, and (2) row-disjointness or a narrowly proven commutative overlap with
    intervening patches. Apply-time guards still re-validate the whole patch.
    """
    normalized = _normalize_patch_aliases(dict(patch))
    operations = normalized.get("operations") or []
    actor_role = str(normalized.get("actor_role") or "")
    for op in operations:
        if not isinstance(op, Mapping):
            return {"ok": False, "reason": "malformed operation"}
        kind = str(op.get("op") or "")
        if kind not in SAFE_REBASE_OP_KINDS:
            return {"ok": False, "reason": f"op kind {kind} is not rebase-safe"}
        if kind == "propose_status_transition":
            new_status = str(op.get("new_status") or "")
            if (
                new_status not in NON_VERIFYING_TRANSITION_STATUSES
                and (actor_role, new_status) not in REBASE_SAFE_VERIFYING_TRANSITIONS
            ):
                return {"ok": False, "reason": f"transition to {new_status} is not rebase-safe"}
    patch_ids, patch_unknown = _patch_touched_ids(operations)
    if patch_unknown:
        return {"ok": False, "reason": "patch touches rows that cannot be attributed"}
    base_revision = int(normalized.get("base_revision") or 0)
    with store.connect() as conn:
        current_revision = store.get_revision(conn)
        rows = conn.execute(
            "SELECT operations_json FROM patches WHERE applied_revision > ? ORDER BY applied_revision",
            (base_revision,),
        ).fetchall()
    intervening_ids: set[str] = set()
    intervening_operations: list[Mapping[str, Any]] = []
    for row in rows:
        ops = json_loads(row["operations_json"], default=[])
        row_ids, row_unknown = _patch_touched_ids(ops)
        if row_unknown:
            return {"ok": False, "reason": "an intervening patch touches rows that cannot be attributed"}
        intervening_ids |= row_ids
        intervening_operations.extend(op for op in ops if isinstance(op, Mapping))
    overlap = patch_ids & intervening_ids
    if overlap:
        # Evidence and explanation appends to the same inference are merged by
        # _update_inference (set-union plus append).  Allow those operations to
        # rebase even though they touch the same row; status, premise, route,
        # or conclusion changes remain conflicting.
        patch_commutative = _commutative_inference_ids(
            [op for op in operations if isinstance(op, Mapping)]
        )
        intervening_commutative = _commutative_inference_ids(intervening_operations)
        overlap -= patch_commutative & intervening_commutative
    if overlap:
        # Parallel verifiers may both certify a shared premise while only one
        # of them also carries a route-local report/inference update. Identical
        # transitions are idempotent and merge their evidence, so they must not
        # cause the second verifier's otherwise unique work to be discarded.
        patch_transitions = _commutative_status_transition_signatures(
            [op for op in operations if isinstance(op, Mapping)]
        )
        intervening_transitions = _commutative_status_transition_signatures(intervening_operations)
        overlap -= {
            row_id
            for row_id in overlap
            if patch_transitions.get(row_id) == intervening_transitions.get(row_id)
            and patch_transitions.get(row_id) is not None
        }
    if overlap:
        return {"ok": False, "reason": f"row overlap with intervening patches: {sorted(overlap)[:4]}"}
    return {"ok": True, "current_revision": current_revision, "reason": "row-disjoint or commutative patch"}


def apply_patch_with_stale_retry(store: ProofStateStore, patch: Dict[str, Any], *, max_retries: int = 3) -> PatchOutcome:
    """apply_patch, but auto-rebase provably safe patches past staleness.

    Parallel companions and long researcher sessions routinely go stale because
    advisor/metrics patches land mid-flight; when the stale patch is additive
    and row-disjoint or commutative with everything that landed in between,
    retry it instead of discarding the whole session's work.
    """
    outcome = apply_patch(store, patch)
    retries = 0
    while (
        not outcome.accepted
        and retries < max_retries
        and any("stale patch" in str(error) for error in outcome.errors)
    ):
        assessment = _stale_rebase_assessment(store, patch)
        if not assessment.get("ok"):
            try:
                with store.connect() as conn:
                    store.write_event(
                        conn,
                        store.get_revision(conn),
                        "stale_rebase_declined",
                        {
                            "patch_id": outcome.patch_id,
                            "actor_role": str(patch.get("actor_role") or ""),
                            "reason": str(assessment.get("reason") or ""),
                        },
                    )
                    conn.commit()
            except Exception:
                pass
            break
        patch = dict(patch)
        patch["base_revision"] = assessment["current_revision"]
        outcome = apply_patch(store, patch)
        retries += 1
        if outcome.accepted:
            try:
                with store.connect() as conn:
                    store.write_event(
                        conn,
                        store.get_revision(conn),
                        "stale_rebase_applied",
                        {
                            "patch_id": outcome.patch_id,
                            "actor_role": str(patch.get("actor_role") or ""),
                            "rebased_to_revision": assessment["current_revision"],
                            "retries": retries,
                        },
                    )
                    conn.commit()
            except Exception:
                pass
    return outcome


def _record_patch_rejection(store: ProofStateStore, patch: Mapping[str, Any], patch_id: str, errors: List[str], *, kind: str) -> None:
    """Persist a patch_rejected event so failed sessions are diagnosable post-hoc."""
    try:
        payload = {
            "patch_id": patch_id,
            "actor_role": str(patch.get("actor_role") or ""),
            "target_id": str(patch.get("target_id") or ""),
            "base_revision": patch.get("base_revision"),
            "kind": kind,
            "op_kinds": [
                str(op.get("op") or "")
                for op in (patch.get("operations") or [])
                if isinstance(op, Mapping)
            ][:16],
            "errors": [str(error)[:400] for error in (errors or [])][:8],
        }
        with store.connect() as conn:
            store.write_event(conn, store.get_revision(conn), "patch_rejected", payload)
            conn.commit()
    except Exception:
        pass


def apply_patch(store: ProofStateStore, patch: Dict[str, Any]) -> PatchOutcome:
    patch = _normalize_patch_aliases(patch)
    patch_id = str(patch.get("patch_id") or f"patch-{uuid.uuid4().hex[:12]}")
    errors = _validate_patch_shape(store.problem_id, patch)
    if errors:
        _record_patch_rejection(store, patch, patch_id, errors, kind="invalid_shape")
        return PatchOutcome(False, _safe_revision(store), patch_id, errors)

    with store.connect() as conn:
        current_revision = store.get_revision(conn)
        if int(patch["base_revision"]) != current_revision:
            stale_errors = [f"stale patch: base_revision {patch['base_revision']} != current_revision {current_revision}"]
            _record_patch_rejection(store, patch, patch_id, stale_errors, kind="stale_base_revision")
            return PatchOutcome(False, current_revision, patch_id, stale_errors)

        try:
            conn.execute("BEGIN IMMEDIATE")
            verification_debt_reconciliations = _resolve_stale_verified_entity_debts(conn)
            pending_owners = _owners_created_by_patch(patch["operations"])
            for op in patch["operations"]:
                _apply_operation(conn, store, patch, op, pending_owners=pending_owners)

            # No-hanging-proofs invariant: every proven claim is kept verifier-ready.
            _ensure_proven_claims_routed(conn)
            _ensure_verified_statement_repairs_supersede_stale_work(conn)
            verification_debt_reconciliations.extend(_resolve_stale_verified_entity_debts(conn))
            integration_reconciliations = _reconcile_invalid_integrations(conn)

            invariant_errors = validate_conn(conn)
            if invariant_errors:
                raise PatchRejected(invariant_errors)

            new_revision = current_revision + 1
            now = utc_now()
            conn.execute(
                "UPDATE problem_state SET current_revision = ?, updated_at = ? WHERE problem_id = ?",
                (new_revision, now, store.problem_id),
            )
            conn.execute(
                """
                INSERT INTO patches(
                    patch_id, schema_version, problem_id, base_revision, actor_role,
                    target_id, operations_json, evidence_artifact_ids_json, rationale,
                    status, rejection_reason, created_at, applied_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'applied', '', ?, ?)
                """,
                (
                    patch_id,
                    SCHEMA_VERSION,
                    store.problem_id,
                    int(patch["base_revision"]),
                    patch["actor_role"],
                    patch.get("target_id", ""),
                    json_dumps(patch["operations"]),
                    json_dumps(patch.get("evidence_artifact_ids", [])),
                    patch.get("rationale", ""),
                    now,
                    new_revision,
                ),
            )
            store.write_event(conn, new_revision, "patch_applied", {"patch_id": patch_id, "actor_role": patch["actor_role"]})
            if integration_reconciliations:
                store.write_event(
                    conn,
                    new_revision,
                    "integration_invalidated",
                    {"changes": integration_reconciliations},
                )
            if verification_debt_reconciliations:
                store.write_event(
                    conn,
                    new_revision,
                    "stale_verification_debt_resolved",
                    {"changes": verification_debt_reconciliations},
                )
            conn.commit()
        except PatchRejected as exc:
            conn.rollback()
            _record_patch_rejection(store, patch, patch_id, exc.errors, kind="guard_rejected")
            return PatchOutcome(False, current_revision, patch_id, exc.errors)
        except Exception as exc:  # keep caller-facing error structured
            conn.rollback()
            _record_patch_rejection(store, patch, patch_id, [str(exc)], kind="exception")
            return PatchOutcome(False, current_revision, patch_id, [str(exc)])

    if store.auto_snapshot:
        store.write_snapshot()
    return PatchOutcome(True, new_revision, patch_id, [])


def reconcile_integrated_claims(store: ProofStateStore) -> Dict[str, Any]:
    """Repair legacy verification debt and integration lifecycle state.

    Normal patch application performs the same reconciliation automatically.
    This explicit entry point exists for proof databases created before that
    behavior was introduced, so a paused run can be repaired without inventing
    a synthetic mathematical patch.
    """

    patch_id = f"integration-reconcile-{uuid.uuid4().hex[:12]}"
    with store.connect() as conn:
        current_revision = store.get_revision(conn)
        try:
            conn.execute("BEGIN IMMEDIATE")
            changes = _resolve_stale_verified_entity_debts(conn)
            changes.extend(_reconcile_invalid_integrations(conn))
            if not changes:
                conn.rollback()
                return {
                    "changed": False,
                    "revision": current_revision,
                    "patch_id": "",
                    "changes": [],
                }

            invariant_errors = validate_conn(conn)
            if invariant_errors:
                raise PatchRejected(invariant_errors)

            new_revision = current_revision + 1
            now = utc_now()
            conn.execute(
                "UPDATE problem_state SET current_revision = ?, updated_at = ? WHERE problem_id = ?",
                (new_revision, now, store.problem_id),
            )
            conn.execute(
                """
                INSERT INTO patches(
                    patch_id, schema_version, problem_id, base_revision, actor_role,
                    target_id, operations_json, evidence_artifact_ids_json, rationale,
                    status, rejection_reason, created_at, applied_revision
                ) VALUES (?, ?, ?, ?, 'system', 'integration_reconciliation', ?, '[]', ?,
                          'applied', '', ?, ?)
                """,
                (
                    patch_id,
                    SCHEMA_VERSION,
                    store.problem_id,
                    current_revision,
                    json_dumps(changes),
                    "reconcile stale verification debt and integration lifecycle with current proof obligations",
                    now,
                    new_revision,
                ),
            )
            store.write_event(
                conn,
                new_revision,
                "integration_reconciled",
                {"patch_id": patch_id, "changes": changes},
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    if store.auto_snapshot:
        store.write_snapshot()
    return {
        "changed": True,
        "revision": new_revision,
        "patch_id": patch_id,
        "changes": changes,
    }


def _safe_revision(store: ProofStateStore) -> int:
    try:
        return store.get_revision()
    except Exception:
        return -1


_VERIFICATION_EVIDENCE_ARTIFACT_TYPES = {
    "verification_report",
    "integration_report",
    "confirmed_counterexample",
    "formal_backend_result",
}


def _op_kind(op: Mapping[str, Any]) -> Optional[str]:
    """Resolve an operation's kind, tolerating op/operation_type/operation/etc."""
    for key in ("op", "operation_type", "operation", "operation_name", "type"):
        value = op.get(key)
        if isinstance(value, str) and value:
            return value
    if isinstance(op.get("artifact_id"), str) and isinstance(op.get("artifact_type"), str):
        return "attach_artifact"
    return None


def _flatten_nested(op: Dict[str, Any], nested_key: str) -> None:
    """Hoist fields from a nested object (e.g. attach_artifact.artifact) to the top."""
    nested = op.get(nested_key)
    if isinstance(nested, dict):
        for key, value in nested.items():
            op.setdefault(key, value)
        op.pop(nested_key, None)


def _nested_payload_op(op: Dict[str, Any], nested_key: str, kind: str) -> Dict[str, Any]:
    """Return an operation with a nested claim/route/inference payload hoisted."""
    nested = op.get(nested_key)
    if not isinstance(nested, dict):
        return op
    normalized = dict(nested)
    for key, value in op.items():
        if key not in {"op", nested_key} and key not in normalized:
            normalized[key] = value
    normalized["op"] = kind
    return normalized


def _normalize_debt_fields(op: Dict[str, Any], *, patch_target_id: str = "") -> None:
    """Map agent debt shapes (owner/description/blocking_claim_id) to the schema."""
    if not op.get("obligation"):
        for alt in ("description", "obligation_text", "detail", "statement", "summary"):
            if op.get(alt):
                op["obligation"] = op[alt]
                break
    if not op.get("source_artifact_ids") and isinstance(op.get("evidence_artifact_ids"), list):
        op["source_artifact_ids"] = op["evidence_artifact_ids"]
    _remove_retrieval_cards_from_debt_sources(op)
    def _first(v):
        return (v[0] if v else None) if isinstance(v, (list, tuple)) else v
    op_target_id = str(op.get("target_id") or patch_target_id or "").strip()
    claim_owner = (op.get("blocking_claim_id") or op.get("owner_claim_id")
                   or op.get("claim_id") or _first(op.get("blocking_claim_ids")))
    inf_owner = op.get("inference_id")
    # Agents commonly name a debt's owner via the route(s) it blocks.
    route_owner = (op.get("route_id") or op.get("blocking_route_id")
                   or _first(op.get("blocking_route_ids")))
    owner_id = str(op.get("owner_id") or "").strip()
    owner_is_role = _is_graph_role_name(owner_id)
    if not owner_id or owner_is_role:
        if owner_is_role and route_owner:
            op["owner_type"] = "route"
            op["owner_id"] = route_owner
        elif owner_is_role and claim_owner:
            op["owner_type"] = "claim"
            op["owner_id"] = claim_owner
        elif owner_is_role and inf_owner:
            op["owner_type"] = "inference"
            op["owner_id"] = inf_owner
        elif owner_is_role and op_target_id:
            op["owner_type"] = "claim"
            op["owner_id"] = op_target_id
        else:
            owner = claim_owner or op.get("owner") or inf_owner or route_owner or op_target_id
            if owner:
                op["owner_id"] = owner
    if _is_graph_role_name(str(op.get("suggested_next_target") or "")):
        fallback_target = str(op.get("owner_id") or op_target_id or "").strip()
        if fallback_target:
            op["suggested_next_target"] = fallback_target
    if not op.get("owner_type"):
        oid = op.get("owner_id")
        if claim_owner and oid == claim_owner:
            op["owner_type"] = "claim"
        elif inf_owner and oid == inf_owner:
            op["owner_type"] = "inference"
        elif route_owner and oid == route_owner:
            op["owner_type"] = "route"
        elif oid:
            op["owner_type"] = _infer_owner_type_from_id(oid)
    else:
        oid = str(op.get("owner_id") or "").strip()
        inferred_owner_type = _infer_owner_type_from_id(oid)
        explicit_claim_match = bool(claim_owner and oid == str(claim_owner))
        if op.get("owner_type") == "claim" and inferred_owner_type in {"route", "inference"} and not explicit_claim_match:
            op["owner_type"] = inferred_owner_type
    op["severity"] = _normalize_debt_severity(op.get("severity", "blocking"))
    op["status"] = _normalize_debt_status(op.get("status", "active"))


def _remove_retrieval_cards_from_debt_sources(op: Dict[str, Any]) -> None:
    """Keep debt source_artifact_ids limited to actual artifact ids.

    Literature passes often create a retrieval card and then cite that card in a
    debt's source_artifact_ids. Retrieval cards are useful evidence, but they
    are not rows in the artifacts table, so leaving them in source_artifact_ids
    makes the invariant checker reject the whole patch. The companion
    source_adaptation_notes artifact carries the retrieval-card metadata; the
    graph edge should point to that artifact.
    """
    source_ids = op.get("source_artifact_ids")
    if not isinstance(source_ids, list):
        return
    kept: list[Any] = []
    retrieval_ids: list[str] = []
    for raw_id in source_ids:
        text = str(raw_id or "").strip()
        if _looks_like_retrieval_card_id(text):
            retrieval_ids.append(text)
        else:
            kept.append(raw_id)
    if len(kept) != len(source_ids):
        op["source_artifact_ids"] = kept
    if retrieval_ids:
        for key in ("source_retrieval_card_ids", "retrieval_card_ids"):
            existing = op.get(key)
            if isinstance(existing, list):
                merged = list(dict.fromkeys([*(str(item) for item in existing if str(item)), *retrieval_ids]))
                op[key] = merged
                break
        else:
            op["source_retrieval_card_ids"] = retrieval_ids


def _looks_like_retrieval_card_id(value: str) -> bool:
    text = value.strip().lower()
    return text.startswith(("retrieval_", "retrieval-", "card-retrieval-", "card_retrieval_"))


def _is_graph_role_name(value: str) -> bool:
    return value.strip().lower() in GRAPH_OWNER_ROLE_NAMES


def _infer_owner_type_from_id(owner_id: Any) -> str:
    """Infer a missing debt owner_type from unambiguous graph-id prefixes."""
    value = str(owner_id or "").strip().lower()
    if value.startswith(("route_", "route-")):
        return "route"
    if value.startswith(("inf_", "inf-", "inference_", "inference-")):
        return "inference"
    return "claim"


def _normalize_patch_aliases(patch: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(patch)
    operations = normalized.get("operations")
    if not isinstance(operations, list):
        return normalized

    # Verification evidence attached in this same patch, so an aliased status
    # transition (update_claim/update_inference -> propose_status_transition) can
    # cite it for the informally_verified/refuted/integrated gates.
    verification_evidence_ids = [
        str(_artifact_op_field(op, "artifact_id"))
        for op in operations
        if isinstance(op, dict)
        and _op_kind(op) == "attach_artifact"
        and str(_artifact_op_field(op, "artifact_type") or "") in _VERIFICATION_EVIDENCE_ARTIFACT_TYPES
        and _artifact_op_field(op, "artifact_id")
    ]

    normalized_operations: list[Any] = []
    integration_evidence_ids: list[str] = []
    blocking_verification_evidence_ids: list[str] = []
    for op in operations:
        if not isinstance(op, dict):
            normalized_operations.append(op)
            continue
        normalized_op = dict(op)
        kind = _op_kind(normalized_op)
        if kind:
            normalized_op["op"] = kind
        if kind == "set_claim_validation_status":
            normalized_op["op"] = "set_claim_status"
            kind = "set_claim_status"
        elif kind == "set_inference_validation_status":
            normalized_op["op"] = "set_inference_status"
            kind = "set_inference_status"
        elif kind == "set_debt_status":
            normalized_op["op"] = "update_debt"
            kind = "update_debt"
        elif kind == "attach_artifact" and normalized_op.get("artifact_type") == "cache_retrieval_card":
            normalized_op["op"] = "cache_retrieval_card"
            kind = "cache_retrieval_card"
        if kind == "propose_lifecycle":
            normalized_op["op"] = "propose_status_transition"
            normalized_op.setdefault("target_type", "claim")
            if "target_id" not in normalized_op and "claim_id" in normalized_op:
                normalized_op["target_id"] = normalized_op["claim_id"]
            normalized_op.setdefault("status_type", "lifecycle")
            if "new_status" not in normalized_op and "lifecycle_status" in normalized_op:
                normalized_op["new_status"] = normalized_op["lifecycle_status"]
            kind = normalized_op.get("op")
        if kind == "cache_retrieval_card":
            # Agents nest the card body under "card" or "retrieval_card"; lift it
            # to the op level so its fields (including the id) become visible.
            for wrapper in ("card", "retrieval_card", "content"):
                if isinstance(normalized_op.get(wrapper), dict):
                    card = dict(normalized_op[wrapper])
                    for key, value in normalized_op.items():
                        if key not in {"op", wrapper} and key not in card:
                            card[key] = value
                    normalized_op = card
                    normalized_op["op"] = kind
                    break
            if "card_id" not in normalized_op and "retrieval_card_id" in normalized_op:
                normalized_op["card_id"] = normalized_op["retrieval_card_id"]
            if "card_id" not in normalized_op and "artifact_id" in normalized_op:
                normalized_op["card_id"] = normalized_op["artifact_id"]
            # Last resort: derive a stable id from the dedup hash or title so a
            # well-formed card is never rejected purely for a missing id.
            if "card_id" not in normalized_op:
                seed = str(normalized_op.get("content_hash") or normalized_op.get("title") or "").strip()
                if seed:
                    normalized_op["card_id"] = "card-" + fingerprint_text(seed, length=16)
        if kind == "attach_artifact":
            # Agents sometimes nest the artifact under an "artifact" object.
            if "artifact_id" not in normalized_op and isinstance(normalized_op.get("artifact"), dict):
                _flatten_nested(normalized_op, "artifact")
            if "artifact_id" not in normalized_op and normalized_op.get("id"):
                normalized_op["artifact_id"] = normalized_op["id"]
            if "artifact_id" not in normalized_op:
                artifact_id = _derive_artifact_id(normalized_op, normalized)
                if artifact_id:
                    normalized_op["artifact_id"] = artifact_id
            if normalized_op.get("artifact_type") == "verification_report":
                _backfill_verification_metadata(normalized_op)
                metadata = normalized_op.get("metadata") if isinstance(normalized_op.get("metadata"), Mapping) else {}
                report = (
                    metadata.get("verification_report")
                    if isinstance(metadata.get("verification_report"), Mapping)
                    else {}
                )
                if (
                    metadata.get("blocking_gap")
                    or metadata.get("critical_errors")
                    or metadata.get("gaps")
                    or report.get("blocking_gap")
                    or report.get("critical_errors")
                    or report.get("gaps")
                ):
                    artifact_id = str(normalized_op.get("artifact_id") or "")
                    if artifact_id:
                        blocking_verification_evidence_ids.append(artifact_id)
            if normalized_op.get("artifact_type") == "integration_report" and normalized_op.get("artifact_id"):
                integration_evidence_ids.append(str(normalized_op["artifact_id"]))
        if kind in {"add_claim", "add_route", "add_inference"}:
            nested_key = {"add_claim": "claim", "add_route": "route", "add_inference": "inference"}[kind]
            if isinstance(normalized_op.get(nested_key), dict):
                normalized_op = _nested_payload_op(normalized_op, nested_key, kind)
            if kind == "add_route":
                _normalize_route_fields(normalized_op)
            elif kind == "add_inference":
                _normalize_inference_fields(normalized_op)
        if kind in {"add_debt", "update_debt"}:
            if isinstance(normalized_op.get("debt"), dict):
                _flatten_nested(normalized_op, "debt")
            _normalize_debt_fields(normalized_op, patch_target_id=str(normalized.get("target_id") or ""))
        if kind in {"update_claim", "update_inference", "set_claim_status", "set_inference_status"}:
            # Models frequently express an update as {"patch": {...}} or
            # {"updates": {...}}.  Leaving either wrapper nested makes the op
            # look valid while silently applying none of its evidence/text.
            for wrapper in ("patch", "updates"):
                _flatten_nested(normalized_op, wrapper)
            nested_key = "claim" if kind in {"update_claim", "set_claim_status"} else "inference"
            if isinstance(normalized_op.get(nested_key), dict):
                normalized_op = _nested_payload_op(normalized_op, nested_key, kind)
            if kind == "update_inference":
                if (
                    not normalized_op.get("add_evidence_artifact_ids")
                    and isinstance(normalized_op.get("evidence_artifact_ids"), list)
                ):
                    normalized_op["add_evidence_artifact_ids"] = list(normalized_op["evidence_artifact_ids"])
                if not normalized_op.get("explanation_append") and normalized_op.get("explanation"):
                    normalized_op["explanation_append"] = normalized_op["explanation"]
            normalized_operations.extend(_expand_status_update(normalized_op, kind, verification_evidence_ids))
            continue
        if kind == "propose_status_transition":
            _normalize_status_transition_fields(normalized_op)
            if (
                normalized_op.get("status_type") == "validation"
                and normalized_op.get("new_status") in {"informally_verified", "formally_verified", "refuted"}
                and not normalized_op.get("evidence_artifact_ids")
                and verification_evidence_ids
            ):
                normalized_op["evidence_artifact_ids"] = list(verification_evidence_ids)
            if (
                normalized_op.get("target_type") == "claim"
                and normalized_op.get("status_type") == "lifecycle"
                and normalized_op.get("new_status") == "integrated"
                and not normalized_op.get("evidence_artifact_ids")
                and integration_evidence_ids
            ):
                normalized_op["evidence_artifact_ids"] = list(integration_evidence_ids)
        normalized_operations.append(normalized_op)
    if str(normalized.get("actor_role") or "") == "strict_informal_verifier" and blocking_verification_evidence_ids:
        target_id = str(normalized.get("target_id") or "")
        already_challenged = any(
            isinstance(op, Mapping)
            and str(op.get("op") or "") == "propose_status_transition"
            and str(op.get("target_type") or "claim") == "claim"
            and str(op.get("target_id") or "") == target_id
            and str(op.get("status_type") or "validation") == "validation"
            and str(op.get("new_status") or "") == "challenged"
            for op in normalized_operations
        )
        if target_id and not already_challenged:
            normalized_operations.append(
                {
                    "op": "propose_status_transition",
                    "target_type": "claim",
                    "target_id": target_id,
                    "status_type": "validation",
                    "new_status": "challenged",
                    "evidence_artifact_ids": list(dict.fromkeys(blocking_verification_evidence_ids)),
                    "reason": "strict verification found a blocking error or gap",
                }
            )
    normalized["operations"] = normalized_operations
    return normalized


def _derive_artifact_id(op: Mapping[str, Any], patch: Mapping[str, Any]) -> str:
    artifact_type = str(op.get("artifact_type") or "").strip()
    seed_parts = [
        str(op.get("title") or "").strip(),
        str(op.get("content") or "").strip(),
        json_dumps(op.get("metadata", {})) if isinstance(op.get("metadata"), dict) else "",
    ]
    seed = "\n".join(part for part in seed_parts if part)
    if not artifact_type or not seed:
        return ""
    actor = str(patch.get("actor_role") or "actor").strip()
    target = str(op.get("target_id") or patch.get("target_id") or "target").strip()
    prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"art_auto_{actor}_{target}_{artifact_type}").strip("._")
    return f"{prefix[:80]}_{fingerprint_text(seed, length=12)}"


def _artifact_op_field(op: Mapping[str, Any], key: str) -> Any:
    if key in op:
        return op.get(key)
    artifact = op.get("artifact")
    if isinstance(artifact, Mapping):
        return artifact.get(key)
    return None


def _normalize_status_transition_fields(op: Dict[str, Any]) -> None:
    if "target_type" not in op and "entity_type" in op:
        op["target_type"] = op["entity_type"]
    if "target_type" not in op and "target_kind" in op:
        op["target_type"] = op["target_kind"]
    if "target_type" not in op and "object_type" in op:
        op["target_type"] = op["object_type"]
    if "target_id" not in op and "entity_id" in op:
        op["target_id"] = op["entity_id"]
    if "target_id" not in op and "object_id" in op:
        op["target_id"] = op["object_id"]
    # Agents (notably the integration verifier) often name the target with the
    # concrete graph-id field instead of target_id; accept the common aliases.
    if "target_id" not in op and op.get("claim_id"):
        op["target_id"] = op["claim_id"]
        op.setdefault("target_type", "claim")
    if "target_id" not in op and op.get("inference_id"):
        op["target_id"] = op["inference_id"]
        op.setdefault("target_type", "inference")
    if "target_id" not in op and op.get("route_id"):
        op["target_id"] = op["route_id"]
        op.setdefault("target_type", "route")
    if "status_type" not in op and "status_field" in op:
        status_field = str(op["status_field"] or "")
        if status_field.endswith("_status"):
            status_field = status_field[: -len("_status")]
        op["status_type"] = status_field or op["status_field"]
    if "new_status" not in op and "to_status" in op:
        op["new_status"] = op["to_status"]
    if "new_status" not in op and "proposed_status" in op:
        op["new_status"] = op["proposed_status"]
    if "new_status" not in op and str(op.get("status") or "") in (
        VALIDATION_STATUSES | LIFECYCLE_STATUSES | ROUTE_STATUSES
    ):
        # Agents sometimes write plain `status:` on a transition op; in this op
        # kind it is unambiguous (observed live: integration rejected with
        # 'new_status is required').
        op["new_status"] = op["status"]
    if "new_status" not in op and "lifecycle_status" in op:
        op["new_status"] = op["lifecycle_status"]
        op.setdefault("status_type", "lifecycle")
    if "new_status" not in op and "validation_status" in op:
        op["new_status"] = op["validation_status"]
        op.setdefault("status_type", "validation")
    if "status_type" not in op and "new_status" in op:
        new_status = str(op.get("new_status") or "")
        if new_status in LIFECYCLE_STATUSES:
            op["status_type"] = "lifecycle"
        elif new_status in VALIDATION_STATUSES:
            op["status_type"] = "validation"


_EMPTY_SECTION_MARKERS = {"", "[]", "none", "none.", "n/a", "na", "null", "false", "-", "no", "no gaps", "no gaps.", "no critical errors", "no critical errors.", "no errors", "no errors.", "no blocking gap", "no blocking gap."}


def _markdown_sections(content: str) -> Dict[str, str]:
    """Split a markdown report into {lowercased '## header': body} sections."""
    sections: Dict[str, str] = {}
    current: Optional[str] = None
    body: List[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            if current is not None:
                sections[current] = "\n".join(body).strip()
            current = stripped.lstrip("#").strip().lower()
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        sections[current] = "\n".join(body).strip()
    return sections


def _section_is_empty(body: str) -> bool:
    cleaned = body.strip().strip("`").strip().lower()
    if cleaned in _EMPTY_SECTION_MARKERS:
        return True
    # A bullet list with no real items, or a lone "[]".
    return cleaned.replace("[", "").replace("]", "").strip() == ""


def _backfill_verification_metadata(op: Dict[str, Any]) -> None:
    """Populate verification_report metadata from markdown content when missing.

    Verifiers often render verdict/critical_errors/gaps/blocking_gap as markdown
    sections with empty structured metadata, but the informally_verified gate reads
    metadata. Parse the content into metadata CONSERVATIVELY: a zero-gap verdict is
    only recorded when the errors/gaps/blocking sections are explicitly empty; any
    other content is treated as a real gap so the gate still rejects.
    """
    metadata = op.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    report = metadata.get("verification_report") if isinstance(metadata.get("verification_report"), dict) else {}
    # Respect agent-provided structured metadata; only backfill what is missing.
    if metadata.get("verdict") or report.get("verdict"):
        return
    content = op.get("content")
    if isinstance(content, dict):
        verdict = str(content.get("verdict") or "").strip()
        if not verdict:
            return
        backfilled = dict(metadata)
        backfilled["verdict"] = verdict
        existing_report = backfilled.get("verification_report") if isinstance(backfilled.get("verification_report"), dict) else {}
        backfilled["verification_report"] = {
            **existing_report,
            "critical_errors": content.get("critical_errors") or [],
            "gaps": content.get("gaps") or [],
            "blocking_gap": bool(content.get("blocking_gap")),
        }
        op["metadata"] = backfilled
        return
    if not isinstance(content, str) or not content.strip():
        return
    parsed_content = json_loads(content, None)
    if isinstance(parsed_content, dict):
        op["content"] = parsed_content
        _backfill_verification_metadata(op)
        op["content"] = content
        return
    sections = _markdown_sections(content)
    verdict = ""
    if "verdict" in sections:
        first_line = next((ln.strip() for ln in sections["verdict"].splitlines() if ln.strip()), "")
        verdict = first_line.strip().strip("`").strip()
    if not verdict:
        return
    critical_errors: List[str] = [] if _section_is_empty(sections.get("critical errors", "")) else [sections.get("critical errors", "").strip()]
    gaps: List[str] = [] if _section_is_empty(sections.get("gaps", "")) else [sections.get("gaps", "").strip()]
    blocking_gap = not _section_is_empty(sections.get("blocking gap", ""))
    backfilled = dict(metadata)
    backfilled["verdict"] = verdict
    backfilled.setdefault("verification_report", {})
    if isinstance(backfilled["verification_report"], dict):
        backfilled["verification_report"] = {
            **backfilled["verification_report"],
            "critical_errors": critical_errors,
            "gaps": gaps,
            "blocking_gap": blocking_gap,
        }
    op["metadata"] = backfilled


def _normalize_route_fields(op: Dict[str, Any]) -> None:
    if "conclusion_claim_id" not in op:
        for alias in ("target_claim_id", "claim_id", "target_id"):
            value = op.get(alias)
            if isinstance(value, str) and value:
                op["conclusion_claim_id"] = value
                break
    if "strategy" not in op:
        for alias in ("proof_obligation", "argument_summary", "summary"):
            value = op.get(alias)
            if isinstance(value, str) and value.strip():
                op["strategy"] = value
                break
    if "label" not in op:
        for alias in ("title", "name"):
            value = op.get(alias)
            if isinstance(value, str) and value.strip():
                op["label"] = value
                break


def _normalize_inference_fields(op: Dict[str, Any]) -> None:
    if "conclusion_claim_id" not in op:
        for alias in ("target_claim_id", "claim_id", "target_id"):
            value = op.get(alias)
            if isinstance(value, str) and value:
                op["conclusion_claim_id"] = value
                break
    if "explanation" not in op:
        for alias in ("argument_summary", "proof_obligation", "summary"):
            value = op.get(alias)
            if isinstance(value, str) and value.strip():
                op["explanation"] = value
                break


def _expand_status_update(op: Dict[str, Any], kind: str, evidence_ids: List[str]) -> List[Dict[str, Any]]:
    """Map agent-emitted status aliases to propose_status_transition.

    Agents sometimes emit ``update_*`` or ``set_*_status`` (not real ops) to
    set validation/lifecycle status. Translate to the supported transition,
    carrying any verification_report attached in the same patch as evidence so
    the informally_verified/refuted/integrated gates pass.
    """
    target_type = "claim" if kind in {"update_claim", "set_claim_status"} else "inference"
    target_id = op.get("claim_id") if target_type == "claim" else op.get("inference_id")
    target_id = target_id or op.get("target_id")

    fields: Dict[str, Any] = {}
    updates = op.get("updates")
    if isinstance(updates, dict):
        fields.update(updates)
    for key in ("validation_status", "lifecycle_status"):
        if key in op:
            fields.setdefault(key, op[key])

    validation = fields.get("validation_status")
    lifecycle = fields.get("lifecycle_status")
    if validation is None and lifecycle is None and op.get("new_status"):
        if op.get("status_type") == "lifecycle":
            lifecycle = op["new_status"]
        else:
            validation = op["new_status"]

    op_evidence = list(op.get("evidence_artifact_ids") or []) or list(evidence_ids)
    transitions: List[Dict[str, Any]] = []
    if validation is not None:
        transition: Dict[str, Any] = {
            "op": "propose_status_transition",
            "target_type": target_type,
            "target_id": target_id,
            "status_type": "validation",
            "new_status": validation,
        }
        if op_evidence:
            transition["evidence_artifact_ids"] = op_evidence
        transitions.append(transition)
    if lifecycle is not None and target_type == "claim":
        transition = {
            "op": "propose_status_transition",
            "target_type": "claim",
            "target_id": target_id,
            "status_type": "lifecycle",
            "new_status": lifecycle,
        }
        if op.get("route_id"):
            transition["route_id"] = op["route_id"]
        if op_evidence:
            transition["evidence_artifact_ids"] = op_evidence
        if op.get("resolved_debt_ids"):
            transition["resolved_debt_ids"] = op["resolved_debt_ids"]
        transitions.append(transition)
    if transitions and target_type == "inference":
        # An update_inference alias may combine a status change with real
        # inference edits; expanding it to transitions alone silently dropped
        # the explanation/evidence appends. Keep them as a companion update op.
        residual_keys = ("explanation_append", "add_evidence_artifact_ids", "explanation")
        residual = {key: op[key] for key in residual_keys if op.get(key)}
        updates = op.get("updates") if isinstance(op.get("updates"), dict) else {}
        for key in residual_keys:
            if updates.get(key) and key not in residual:
                residual[key] = updates[key]
        if residual:
            transitions.append({"op": "update_inference", "inference_id": target_id, **residual})
    # If we could not interpret it, keep the original so it fails with a clear error.
    return transitions or [op]


def _validate_patch_shape(problem_id: str, patch: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if patch.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if patch.get("problem_id") != problem_id:
        errors.append(f"problem_id must be {problem_id}")
    if "base_revision" not in patch:
        errors.append("base_revision missing")
    if not isinstance(patch.get("actor_role"), str) or not patch.get("actor_role"):
        errors.append("actor_role missing")
    if not isinstance(patch.get("operations"), list) or not patch.get("operations"):
        errors.append("operations must be a non-empty list")
    for index, op in enumerate(patch.get("operations", []) if isinstance(patch.get("operations"), list) else []):
        if not isinstance(op, dict):
            errors.append(f"operation {index} must be an object")
        elif "op" not in op:
            errors.append(f"operation {index} missing op")
    return errors


def _owners_created_by_patch(operations: Sequence[Any]) -> Dict[str, set[str]]:
    owners: Dict[str, set[str]] = {"claim": set(), "route": set(), "inference": set()}
    for op in operations:
        if not isinstance(op, dict):
            continue
        kind = str(op.get("op") or "")
        payload = op
        if kind == "add_claim" and isinstance(op.get("claim"), dict):
            payload = op["claim"]
        elif kind == "add_route" and isinstance(op.get("route"), dict):
            payload = op["route"]
        elif kind == "add_inference" and isinstance(op.get("inference"), dict):
            payload = op["inference"]
        if kind == "add_claim" and isinstance(payload.get("claim_id"), str):
            owners["claim"].add(str(payload["claim_id"]))
        elif kind == "add_route" and isinstance(payload.get("route_id"), str):
            owners["route"].add(str(payload["route_id"]))
        elif kind == "add_inference" and isinstance(payload.get("inference_id"), str):
            owners["inference"].add(str(payload["inference_id"]))
    return owners


def _apply_operation(
    conn: sqlite3.Connection,
    store: ProofStateStore,
    patch: Dict[str, Any],
    op: Dict[str, Any],
    *,
    pending_owners: Mapping[str, set[str]] | None = None,
) -> None:
    kind = op["op"]
    if kind == "attach_artifact":
        _attach_artifact(conn, store, patch, _normalize_artifact_operation(op))
    elif kind == "add_artifact":
        _attach_artifact(conn, store, patch, _normalize_artifact_operation(op))
    elif kind == "add_claim":
        if isinstance(op.get("claim"), dict):
            normalized = dict(op["claim"])
            for key, value in op.items():
                if key not in {"op", "claim"} and key not in normalized:
                    normalized[key] = value
            normalized["op"] = kind
            op = normalized
        _add_claim(conn, op)
    elif kind == "add_route":
        op = _nested_payload_op(op, "route", kind)
        _add_route(conn, op)
    elif kind == "add_inference":
        op = _nested_payload_op(op, "inference", kind)
        _add_inference(conn, op)
    elif kind == "update_inference":
        _update_inference(conn, op)
    elif kind == "update_route":
        if isinstance(op.get("route"), dict):
            op = _nested_payload_op(op, "route", kind)
        _update_route(conn, op)
    elif kind in {"add_debt", "update_debt", "resolve_debt"}:
        if isinstance(op.get("debt"), dict):
            normalized = dict(op["debt"])
            normalized["op"] = kind
            op = normalized
        _debt_operation(conn, patch, op, pending_owners=pending_owners)
    elif kind == "propose_status_transition":
        _status_transition(conn, patch, op)
    elif kind == "record_run_metrics":
        _record_run(conn, op, problem_id=str(patch.get("problem_id") or store.problem_id))
    elif kind == "abandon_route":
        _guard_debt_bearing_route_not_abandoned(conn, _required(op, "route_id"))
        _set_route_status(conn, op, "abandoned")
    elif kind == "reactivate_route":
        _set_route_status(conn, op, "active")
    elif kind == "cache_retrieval_card":
        if patch["actor_role"] != LITERATURE_RESEARCHER_ROLE:
            raise PatchRejected(["cache_retrieval_card requires literature_researcher actor"])
        _cache_retrieval_card(conn, op)
    elif kind == "certify_external_citation":
        if patch["actor_role"] != "strict_informal_verifier":
            raise PatchRejected(["certify_external_citation requires strict_informal_verifier actor"])
        _certify_external_citation(conn, store, patch, op)
    else:
        raise PatchRejected([f"unknown operation: {kind}"])


def _normalize_artifact_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    artifact = op.get("artifact")
    if isinstance(artifact, dict):
        normalized = dict(artifact)
        for key, value in op.items():
            if key not in {"op", "artifact"} and key not in normalized:
                normalized[key] = value
    else:
        normalized = {key: value for key, value in op.items() if key != "op"}
    normalized["op"] = "attach_artifact"

    metadata = normalized.get("metadata")
    content = normalized.get("content")
    if not isinstance(metadata, dict) and isinstance(content, dict) and isinstance(content.get("metadata"), dict):
        metadata = dict(content["metadata"])
        normalized["metadata"] = metadata
    if isinstance(metadata, dict):
        augmented_metadata = dict(metadata)
        for key in ("target_id", "route_id", "debt_id"):
            if key in normalized and key not in augmented_metadata:
                augmented_metadata[key] = normalized[key]
        if augmented_metadata:
            normalized["metadata"] = augmented_metadata
    return normalized


def _certify_external_citation(
    conn: sqlite3.Connection,
    store: ProofStateStore,
    patch: Dict[str, Any],
    op: Dict[str, Any],
) -> None:
    """Turn an exact, checked theorem citation into ordinary verifier evidence.

    The operation deliberately records external certification as a verification
    report plus a sufficient route/inference. Integration and final writing still
    happen through the usual gates, so cited theorems do not bypass root
    alignment or the writer's reference discipline.
    """
    target_id = _required(op, "target_id")
    target = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (target_id,)).fetchone()
    if target is None:
        raise PatchRejected([f"unknown claim: {target_id}"])
    card_id = _required(op, "card_id")
    card = conn.execute("SELECT * FROM retrieval_cards WHERE card_id = ?", (card_id,)).fetchone()
    if card is None:
        raise PatchRejected([f"unknown retrieval card: {card_id}"])

    applicability = json_loads(card["applicability_json"], {})
    if not isinstance(applicability, Mapping):
        applicability = {}
    missing = json_loads(card["missing_hypotheses_json"])
    if missing:
        raise PatchRejected(["external citation certification requires an empty missing_hypotheses list"])
    retrieval_relation = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation"))
    if retrieval_relation not in {"direct_match", "stronger_match", "equivalent_reformulation"}:
        raise PatchRejected([f"external citation certification requires direct/stronger/equivalent retrieval relation, got {retrieval_relation}"])

    relation = _normalize_citation_relation(op.get("relation_to_target") or applicability.get("relation_to_target") or retrieval_relation)
    if relation not in SOLVED_RELATIONS:
        raise PatchRejected([f"external citation relation_to_target must be exact, equivalent, or stronger; got {relation}"])
    if relation == "exact" and retrieval_relation != "direct_match":
        raise PatchRejected(["relation_to_target=exact requires a direct_match retrieval card"])
    if relation == "stronger" and retrieval_relation not in {"direct_match", "stronger_match"}:
        raise PatchRejected(["relation_to_target=stronger requires a direct or stronger retrieval card"])
    if relation == "equivalent" and retrieval_relation not in {"direct_match", "equivalent_reformulation"}:
        raise PatchRejected(["relation_to_target=equivalent requires a direct or equivalent retrieval card"])
    if not bool(op.get("implication_verified") or applicability.get("implication_to_target_verified")):
        raise PatchRejected(["external citation certification requires implication_verified=true"])
    if op.get("hidden_assumptions") is True or op.get("extra_assumptions"):
        raise PatchRejected(["external citation certification cannot introduce hidden or extra assumptions"])

    source_ids = json_loads(card["source_identifiers_json"], {})
    if not isinstance(source_ids, Mapping):
        source_ids = {}
    source_errors = _citation_source_errors(source_ids, card)
    if source_errors:
        raise PatchRejected(source_errors)

    digest = fingerprint_text(f"{target_id} {card_id} {relation}", length=16)
    artifact_id = str(op.get("artifact_id") or f"citation-verification-{digest}")
    route_id = str(op.get("route_id") or f"route-citation-{digest}")
    inference_id = str(op.get("inference_id") or f"inf-citation-{digest}")
    if conn.execute("SELECT 1 FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone():
        raise PatchRejected([f"artifact already exists: {artifact_id}"])

    target_statement = target["statement"]
    exact_statement = card["exact_statement"]
    location = str(card["source_location"] or source_ids.get("theorem_number") or source_ids.get("section") or "")
    checked_items = list(op.get("checked_items") or [])
    if not checked_items:
        checked_items = [
            f"Matched retrieval card {card_id} to claim {target_id}.",
            f"Checked source location: {location or 'specified theorem location'}.",
            "Checked that the cited theorem has no missing hypotheses for this target.",
            f"Checked that the cited result is {relation} relative to the target statement.",
        ]
    summary = str(
        op.get("summary")
        or f"Externally certified claim {target_id} using retrieval card {card_id}; relation_to_target={relation}."
    )
    metadata = {
        "verdict": "correct",
        "certification_type": "external_citation",
        "target_id": target_id,
        "retrieval_card_id": card_id,
        "relation_to_target": relation,
        "retrieval_relation": retrieval_relation,
        "target_statement": target_statement,
        "proved_statement": exact_statement if relation != "exact" else target_statement,
        "exact_cited_statement": exact_statement,
        "source_identifiers": dict(source_ids),
        "source_version": card["source_version"],
        "source_location": card["source_location"],
        "hypotheses_checked": json_loads(card["hypotheses_json"]),
        "local_definitions_checked": json_loads(card["local_definitions_json"]),
        "implication_verified": True,
        "hidden_assumptions": False,
        "extra_assumptions": [],
        "verification_report": {
            "summary": summary,
            "checked_items": checked_items,
            "critical_errors": [],
            "gaps": [],
            "notes": str(op.get("notes") or "Certification uses an exact published theorem citation, not an internal reconstruction."),
        },
    }
    content = _external_citation_report_content(metadata)
    _attach_artifact(
        conn,
        store,
        patch,
        {
            "op": "attach_artifact",
            "artifact_id": artifact_id,
            "artifact_type": "verification_report",
            "content": content,
            "metadata": metadata,
            "content_summary": summary,
        },
    )

    now = utc_now()
    if not conn.execute("SELECT 1 FROM routes WHERE route_id = ?", (route_id,)).fetchone():
        conn.execute(
            """
            INSERT INTO routes(
                route_id, conclusion_claim_id, label, strategy, status, relation_to_parent,
                assumptions_json, conditions_json, evidence_artifact_ids_json,
                failure_fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'active', 'sufficient', '[]', '[]', ?, '', ?, ?)
            """,
            (
                route_id,
                target_id,
                f"External citation via {card_id}",
                f"Use the externally certified theorem recorded in retrieval card {card_id}.",
                json_dumps([artifact_id]),
                now,
                now,
            ),
        )
    else:
        conn.execute(
            "UPDATE routes SET evidence_artifact_ids_json = ?, updated_at = ? WHERE route_id = ?",
            (json_dumps(sorted(set(_route_evidence(conn, route_id) + [artifact_id]))), now, route_id),
        )

    if not conn.execute("SELECT 1 FROM inferences WHERE inference_id = ?", (inference_id,)).fetchone():
        conn.execute(
            """
            INSERT INTO inferences(
                inference_id, route_id, conclusion_claim_id, explanation,
                conditions_json, condition_claim_ids_json, validation_status,
                evidence_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, '[]', '[]', 'informally_verified', ?, ?, ?)
            """,
            (
                inference_id,
                route_id,
                target_id,
                f"The exact cited theorem in retrieval card {card_id} proves the target claim as an external citation.",
                json_dumps([artifact_id]),
                now,
                now,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE inferences
            SET validation_status = 'informally_verified',
                evidence_artifact_ids_json = ?,
                updated_at = ?
            WHERE inference_id = ?
            """,
            (json_dumps(sorted(set(_inference_evidence(conn, inference_id) + [artifact_id]))), now, inference_id),
        )

    conn.execute(
        """
        UPDATE claims
        SET validation_status = 'informally_verified',
            evidence_artifact_ids_json = ?,
            updated_at = ?
        WHERE claim_id = ?
        """,
        (json_dumps(sorted(set(_claim_evidence(conn, target_id) + [artifact_id]))), now, target_id),
    )
    if op.get("resolve_target_blocking_debts", True):
        _resolve_external_citation_debts(conn, target_id, route_id, artifact_id, card_id, applicability)
    _upsert_theorem_library_entry(
        conn,
        entry_id=str(op.get("library_entry_id") or f"library-{digest}"),
        statement=exact_statement,
        source_identifiers=source_ids,
        source_version=str(card["source_version"] or ""),
        source_location=str(card["source_location"] or ""),
        certification_type="external_citation",
        relation_to_target=relation,
        evidence_artifact_ids=[artifact_id],
        tags=["external_citation", f"target:{target_id}", f"retrieval:{card_id}"],
    )


def _resolve_external_citation_debts(
    conn: sqlite3.Connection,
    target_id: str,
    citation_route_id: str,
    artifact_id: str,
    card_id: str,
    applicability: Mapping[str, Any],
) -> None:
    related_claim_ids = {target_id}
    related_route_ids = {citation_route_id}
    app_route_id = str(applicability.get("route_id") or "").strip()
    if app_route_id:
        related_route_ids.add(app_route_id)
    for row in conn.execute("SELECT route_id FROM routes WHERE conclusion_claim_id = ?", (target_id,)).fetchall():
        related_route_ids.add(str(row["route_id"]))
    for route_id in sorted(related_route_ids):
        for row in conn.execute(
            """
            SELECT premise_claim_id
            FROM inference_premises
            JOIN inferences USING(inference_id)
            WHERE inferences.route_id = ?
            """,
            (route_id,),
        ).fetchall():
            related_claim_ids.add(str(row["premise_claim_id"]))

    now = utc_now()
    evidence = json_dumps({"resolved_by": "external_citation", "artifact_id": artifact_id, "retrieval_card_id": card_id})
    for claim_id in sorted(related_claim_ids):
        conn.execute(
            """
            UPDATE debts
            SET status = 'resolved',
                last_seen = ?,
                resolution_evidence_json = ?
            WHERE status = 'active'
              AND severity = 'blocking'
              AND (owner_id = ? OR suggested_next_target = ?)
            """,
            (now, evidence, claim_id, claim_id),
        )
    for route_id in sorted(related_route_ids):
        conn.execute(
            """
            UPDATE debts
            SET status = 'resolved',
                last_seen = ?,
                resolution_evidence_json = ?
            WHERE status = 'active'
              AND severity = 'blocking'
              AND owner_type = 'route'
              AND owner_id = ?
            """,
            (now, evidence, route_id),
        )


def _attach_artifact(conn: sqlite3.Connection, store: ProofStateStore, patch: Dict[str, Any], op: Dict[str, Any]) -> None:
    artifact_id = _required(op, "artifact_id")
    if store.row_exists(conn, "artifacts", "artifact_id", artifact_id):
        raise PatchRejected([f"artifact already exists: {artifact_id}"])
    actor = patch["actor_role"]
    if "producer_role" in op and op.get("producer_role") != actor:
        raise PatchRejected(["artifact producer_role must match patch actor_role"])
    artifact_type = _required(op, "artifact_type")
    _guard_artifact_actor(actor, artifact_type, artifact_id)
    metadata = op.get("metadata", {})
    if not isinstance(metadata, dict):
        raise PatchRejected(["artifact metadata must be an object"])
    metadata = _compact_artifact_metadata(artifact_type, metadata)
    strategy_errors = strategic_artifact_errors(
        conn,
        artifact_type=artifact_type,
        metadata=metadata,
        actor_role=actor,
        base_revision=int(patch["base_revision"]),
    )
    if strategy_errors:
        raise PatchRejected(strategy_errors)
    content = _artifact_inline_content(op)
    path = _validated_artifact_path(store, op.get("path", ""))
    if content is not None and path:
        raise PatchRejected(["attach_artifact with inline content must omit path; the proof-state store writes artifacts under state_dir/artifacts"])
    staged_from_path = False
    if content is None and path and actor == "writer" and artifact_type in WRITER_PATH_ATTACH_ARTIFACT_TYPES:
        # Path-based writer attach: load the staged file so the full writer
        # guard chain below runs on it exactly as for inline content.
        content = _load_writer_staged_content(path)
        staged_from_path = True
    if content is not None and not content.endswith("\n"):
        content += "\n"
    content, content_augmented = _augment_writer_partial_receipt_content(conn, actor, artifact_type, metadata, content)
    content = _normalize_writer_latex_escaping(artifact_type, content)
    content = _normalize_writer_paper_template(artifact_type, content)
    _guard_writer_references(actor, artifact_type, content)
    _guard_writer_mathematical_exposition(actor, artifact_type, content)
    _guard_writer_generation_residue(actor, artifact_type, content)
    _guard_writer_paper_register(artifact_type, content)
    _guard_writing_review_metadata(artifact_type, artifact_id, metadata)
    # Always recompute the digest: a caller-supplied sha256 was trusted verbatim
    # here, letting an agent bypass duplicate-artifact rejection with a bogus hash.
    digest = artifact_hash(content=content, metadata=metadata)
    if _should_dedupe_artifact(artifact_type, metadata):
        duplicate = conn.execute(
            """
            SELECT artifact_id FROM artifacts
            WHERE artifact_type = ? AND producer_role = ? AND sha256 = ?
            ORDER BY created_at ASC LIMIT 1
            """,
            (artifact_type, actor, digest),
        ).fetchone()
        if duplicate:
            raise PatchRejected([f"duplicate {artifact_type} artifact content matches existing artifact {duplicate['artifact_id']}; reuse that artifact_id"])
    if content is not None and (not path or staged_from_path):
        # Inline content, or a writer's staged file: the recorded artifact must
        # point at the store-managed copy under state_dir/artifacts with the
        # standard naming/extension, never at the mutable staging file.
        path = str(_write_artifact_content(store, artifact_id, artifact_type, content))
    if actor == "writer" and content is not None and path:
        if artifact_type == "final_paper":
            # The final_paper's content IS LaTeX source already stored as .tex;
            # compile it directly — no markdown->LaTeX conversion pass.
            sidecars = compile_latex_artifact(Path(path), Path(path).with_suffix(".pdf"))
        else:
            sidecars = write_latex_pdf_sidecars(path, content, title=_writer_artifact_title(artifact_id, artifact_type))
        # Persist the LaTeX compile outcome so the writing gate can tell whether
        # the shipped .tex actually compiled without re-running pdflatex. Merged
        # after the digest so it does not affect content-dedup hashing.
        pdf_status = str(sidecars.get("pdf_status") or "")
        if pdf_status:
            metadata = {**metadata, "pdf_status": pdf_status}
            log_path = str(sidecars.get("latex_log_path") or "")
            if log_path:
                metadata["latex_log_path"] = log_path
    conn.execute(
        """
        INSERT INTO artifacts(
            artifact_id, artifact_type, path, sha256, producer_role, run_id,
            state_revision, content_summary, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            artifact_type,
            path,
            digest,
            actor,
            op.get("run_id", ""),
            int(op.get("state_revision", patch["base_revision"])),
            op.get("content_summary") or artifact_summary(metadata, fallback=content or ""),
            json_dumps(metadata),
            utc_now(),
        ),
    )


def _artifact_inline_content(op: Mapping[str, Any]) -> Optional[str]:
    if "content" not in op:
        return None
    raw_content = op.get("content")
    if isinstance(raw_content, str):
        return raw_content
    return json.dumps(raw_content, indent=2, sort_keys=True, ensure_ascii=False)


def _load_writer_staged_content(path: str) -> str:
    """Load a writer-staged document for a path-based attach_artifact.

    ``path`` has already passed _validated_artifact_path, so it is a real file
    under state_dir/artifacts (recommended staging location:
    state_dir/artifacts/staging/<artifact_id>.tex). Size-capped so a runaway
    staging file cannot be slurped into the guards whole.
    """
    staged = Path(path)
    try:
        size = staged.stat().st_size
    except OSError as exc:
        raise PatchRejected([f"could not stat staged artifact file {path}: {exc}"])
    if size > WRITER_PATH_ATTACH_MAX_BYTES:
        raise PatchRejected(
            [
                f"staged artifact file {path} is {size} bytes; path-based attach_artifact accepts at most "
                f"{WRITER_PATH_ATTACH_MAX_BYTES} bytes"
            ]
        )
    try:
        return staged.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PatchRejected([f"could not read staged artifact file {path} as UTF-8 text: {exc}"])


def _augment_writer_partial_receipt_content(
    conn: sqlite3.Connection,
    actor: str,
    artifact_type: str,
    metadata: Dict[str, Any],
    content: Optional[str],
) -> tuple[Optional[str], bool]:
    if actor != "writer" or content is None:
        return content, False
    if artifact_type not in {"stop_summary_report", "partial_proof_report"}:
        return content, False
    result_kind = str(metadata.get("public_result_kind") or metadata.get("result_kind") or "").strip().lower()
    if result_kind in SOLVED_RELATIONS:
        return content, False
    if receipt_appendix_present(content):
        return content, False
    claims = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM claims ORDER BY reduction_depth ASC, claim_id ASC"
        ).fetchall()
    ]
    artifacts = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM artifacts ORDER BY state_revision ASC, artifact_id ASC"
        ).fetchall()
    ]
    appendix = format_partial_receipt_appendix(claims, artifacts=artifacts)
    return _insert_before_references(content.rstrip(), appendix), True


def _guard_writer_references(actor: str, artifact_type: str, content: Optional[str]) -> None:
    if actor != "writer" or content is None:
        return
    if artifact_type not in WRITER_REFERENCE_REQUIRED_ARTIFACT_TYPES:
        return
    if not REFERENCE_SECTION_RE.search(content):
        raise PatchRejected(
            [
                (
                    f"writer {artifact_type} artifacts must include a writer-authored References section "
                    "with cited sources/artifacts and exact theorem locations, or an explicit empty reference list"
                )
            ]
        )


def _guard_writer_mathematical_exposition(actor: str, artifact_type: str, content: Optional[str]) -> None:
    if actor != "writer" or content is None:
        return
    if artifact_type not in WRITER_REFERENCE_REQUIRED_ARTIFACT_TYPES:
        return
    if _looks_like_raw_writer_ledger_dump(content):
        raise PatchRejected(
            [
                (
                    f"writer {artifact_type} artifacts must be mathematical exposition, not raw proof-state "
                    "JSON or lifecycle bookkeeping dumps"
                )
            ]
        )
    if artifact_type == "final_proof" and not FINAL_PROOF_RE.search(content):
        raise PatchRejected(["writer final_proof artifacts must contain an explicit Proof section or proof environment"])


def _guard_writer_generation_residue(actor: str, artifact_type: str, content: Optional[str]) -> None:
    """Reject writer exposition that still carries generation residue (L1-CITE-03).

    Mirrors the _guard_writer_* style above: deterministic, patch-time, and
    scoped to the artifact types that ship as the public mathematical text.
    """
    if actor != "writer" or content is None:
        return
    if artifact_type not in WRITER_RESIDUE_SCANNED_ARTIFACT_TYPES:
        return
    findings = run_residue_scan(content)
    if not findings:
        return
    details = "; ".join(
        f"{finding.rule_id} line {finding.line}: {finding.message} ({finding.excerpt[:80]!r})"
        for finding in findings[:6]
    )
    raise PatchRejected(
        [
            (
                f"writer {artifact_type} artifacts must not contain generation residue "
                f"(rule L1-CITE-03); remove the residue and re-attach: {details}"
            )
        ]
    )


def _normalize_writer_latex_escaping(artifact_type: str, content: Optional[str]) -> Optional[str]:
    """Repair a fully double-escaped final_paper before the guards run.

    Some writer sessions over-escape the JSON patch, so the parsed LaTeX arrives
    with every backslash doubled (\\\\documentclass...). That document is
    unambiguous garbage as LaTeX, and rejecting it costs a whole authoring
    session, so unescape deterministically instead. Detection is strict: the
    doubled form of \\documentclass must be present and the single form absent,
    which cannot occur in a correctly escaped paper. Quadruple backslashes
    (doubled tabular row breaks) are protected so they collapse back to the
    row-break double backslash.
    """
    if artifact_type != "final_paper" or not content:
        return content
    if "\\\\documentclass" not in content:
        return content
    if content.replace("\\\\documentclass", "").find("\\documentclass") != -1:
        return content
    sentinel = "\x00ROWBREAK\x00"
    repaired = content.replace("\\\\\\\\", sentinel).replace("\\\\", "\\").replace(sentinel, "\\\\")
    return repaired


def _normalize_writer_paper_template(artifact_type: str, content: Optional[str]) -> Optional[str]:
    """Normalize a final_paper onto the house LaTeX template before the guards.

    Layout must not depend on model compliance: the deterministic normalizer
    (writing/latex_template.py) rewrites a non-house preamble to the house
    package set and converts every tabular to canonical booktabs rules. The
    stored .tex, the compile sidecar, and the writing gate all see the
    normalized document. Idempotent: an already-house paper is unchanged.
    """
    if artifact_type != "final_paper" or not content:
        return content
    return normalize_paper_template(content)


def _guard_writer_paper_register(artifact_type: str, content: Optional[str]) -> None:
    """Reject a final_paper that fails the deterministic paper-register lint.

    Mirrors the residue guard style: patch-time, deterministic, and scoped to
    the shipped paper. Any L5-PAPER-01 (markdown residue), L5-PAPER-02
    (internal system register in the main text), or L5-PAPER-03 (missing
    article structure) finding rejects the attach outright — a document that
    trips these is not a paper, so no gate cycle should be spent on it.

    Anti-slop findings (run_slop_lint, L4-SLOP-*/L4-HOUSE-03) are deliberately
    NOT checked here: slop is a writing debt synced by the scheduler's gate
    (majors force the single revision), never an attach-rejection.
    """
    if artifact_type != "final_paper" or content is None:
        return
    findings = run_paper_lint(content)
    if not findings:
        return
    details = "; ".join(
        f"{finding.rule_id} line {finding.line}: {finding.message} ({finding.excerpt[:80]!r})"
        for finding in findings[:6]
    )
    raise PatchRejected(
        [
            (
                "writer final_paper artifacts must pass the paper-register lint "
                f"(rules L5-PAPER-01/02/03); fix the findings and re-attach: {details}"
            )
        ]
    )


def _guard_writing_review_metadata(artifact_type: str, artifact_id: str, metadata: Mapping[str, Any]) -> None:
    """writing_review artifacts must carry a decidable verdict + lens.

    Mirrors the verification_report verdict guard: the scheduler's writing gate
    keys lens convergence off this metadata, so a review without it is useless.
    """
    if artifact_type not in WRITING_CRITIC_ARTIFACT_TYPES:
        return
    verdict = str(metadata.get("verdict") or "").strip().lower()
    if verdict not in WRITING_REVIEW_VERDICTS:
        raise PatchRejected(
            [
                f"writing_review artifact {artifact_id} requires metadata.verdict in "
                f"{sorted(WRITING_REVIEW_VERDICTS)}; got {verdict or 'missing'}"
            ]
        )
    lens = str(metadata.get("lens") or "").strip().lower()
    if lens not in WRITING_CRITIC_LENSES:
        raise PatchRejected(
            [
                f"writing_review artifact {artifact_id} requires metadata.lens in "
                f"{sorted(WRITING_CRITIC_LENSES)}; got {lens or 'missing'}"
            ]
        )
    if not str(metadata.get("artifact_reviewed") or "").strip():
        raise PatchRejected(
            [
                f"writing_review artifact {artifact_id} requires metadata.artifact_reviewed naming the reviewed "
                "final_proof or final_paper"
            ]
        )


def _looks_like_raw_writer_ledger_dump(content: str) -> bool:
    stripped = content.lstrip()
    marker_count = sum(1 for marker in WRITER_RAW_LEDGER_MARKERS if marker in content)
    if marker_count < 3:
        return False
    lower = content.lower()
    return (
        stripped.startswith("{")
        or stripped.startswith("[")
        or "```json" in lower
        or '"operations": [' in lower
        or '"claims": [' in lower
        or '"routes": [' in lower
        or '"inferences": [' in lower
    )


def _insert_before_references(content: str, appendix: str) -> str:
    match = REFERENCE_SECTION_RE.search(content)
    if not match:
        return content.rstrip() + "\n\n" + appendix
    before = content[: match.start()].rstrip()
    after = content[match.start() :].lstrip()
    return before + "\n\n" + appendix.rstrip() + "\n\n" + after


def _writer_artifact_title(artifact_id: str, artifact_type: str) -> str:
    labels = {
        "final_proof": "Albilich v1 Final Proof",
        "proof_compression_report": "Albilich v1 Proof Compression Report",
        "partial_proof_report": "Albilich v1 Partial Proof Report",
        "stop_summary_report": "Albilich v1 Stop Summary",
        "writer_report": "Albilich v1 Writer Report",
    }
    label = labels.get(artifact_type, "Albilich v1 Writer Artifact")
    return f"{label}: {artifact_id}"


def _add_claim(conn: sqlite3.Connection, op: Dict[str, Any]) -> None:
    claim_id = _required(op, "claim_id")
    if claim_id == "root":
        raise PatchRejected(["root claim is immutable and may not be recreated"])
    if conn.execute("SELECT 1 FROM claims WHERE claim_id = ?", (claim_id,)).fetchone():
        raise PatchRejected([f"claim already exists: {claim_id}"])
    kind = op.get("kind", "lemma")
    if kind not in CLAIM_KINDS:
        raise PatchRejected([f"invalid claim kind: {kind}"])
    statement = _required(op, "statement")
    fingerprint = op.get("fingerprint") or fingerprint_text(statement)
    existing_claims = [
        dict(row)
        for row in conn.execute(
            """
            SELECT claim_id, statement, fingerprint, validation_status, lifecycle_status
            FROM claims
            ORDER BY created_at ASC
            """
        ).fetchall()
    ]
    duplicate_id = obvious_duplicate_claim_id(existing_claims, statement=statement, fingerprint=fingerprint)
    if duplicate_id:
        raise PatchRejected([f"duplicate claim statement or obvious restatement matches existing claim {duplicate_id}; reuse that claim_id"])
    validation = op.get("validation_status", "untested")
    lifecycle = op.get("lifecycle_status", "active")
    if validation not in VALIDATION_STATUSES or lifecycle not in LIFECYCLE_STATUSES:
        raise PatchRejected(["invalid claim status"])
    if validation in {"informally_verified", "formally_verified", "refuted"}:
        raise PatchRejected(["new claims must be created as untested, plausible, or challenged; use an evidence-gated transition to verify or refute"])
    now = utc_now()
    conn.execute(
        """
        INSERT INTO claims(
            claim_id, kind, statement, normalized_statement, fingerprint, hypotheses,
            conditions_json, validation_status, lifecycle_status, root_impact,
            reduction_depth, parent_ids_json, source_ids_json, tags_json,
            evidence_artifact_ids_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            claim_id,
            kind,
            statement,
            normalize_text(statement),
            fingerprint,
            op.get("hypotheses", ""),
            json_dumps(op.get("conditions", [])),
            validation,
            lifecycle,
            float(op.get("root_impact", 0.5)),
            int(op.get("reduction_depth", 0)),
            json_dumps(op.get("parent_ids", [])),
            json_dumps(op.get("source_ids", [])),
            json_dumps(op.get("tags", [])),
            json_dumps(op.get("evidence_artifact_ids", [])),
            now,
            now,
        ),
    )


ROUTE_READY_EVIDENCE_ARTIFACT_TYPES = {
    "proof_dossier",
    "proof_blueprint",
    "route_obstruction",
    "hypothesis_gap",
    "construction_failure",
    "necessary_condition",
}
NEGATIVE_ROUTE_READY_TERMS = (
    "failed proof",
    "proof failed",
    "not verifier-ready",
    "not verifier ready",
    "does not prove",
    "cannot close",
    "no proof",
)


def _route_ready_inference_evidence(conn: sqlite3.Connection, claim_id: str, ev_json: str) -> bool:
    """Return whether evidence can safely auto-create a route to verifier/adjudicator."""
    claim = conn.execute("SELECT kind FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    claim_kind = str(claim["kind"] if claim else "")
    try:
        evidence_ids = [str(item) for item in json.loads(ev_json or "[]") if str(item)]
    except (ValueError, TypeError):
        evidence_ids = []
    for evidence_id in evidence_ids:
        row = conn.execute(
            "SELECT artifact_type, content_summary FROM artifacts WHERE artifact_id = ?",
            (evidence_id,),
        ).fetchone()
        if row is None:
            # Backward-compatible fallback for older proof states that only encoded names.
            if ("dossier" in evidence_id or "proof" in evidence_id) and claim_kind in {"obstruction", "counterexample"}:
                return True
            continue
        artifact_type = str(row["artifact_type"] or "")
        summary = str(row["content_summary"] or "").lower()
        if artifact_type not in ROUTE_READY_EVIDENCE_ARTIFACT_TYPES:
            continue
        if claim_kind in {"obstruction", "counterexample"}:
            return True
        if not any(term in summary for term in NEGATIVE_ROUTE_READY_TERMS):
            return True
    return False


def _ensure_proven_claims_routed(conn: sqlite3.Connection) -> None:
    """Deterministic no-hanging-proofs invariant, enforced on every patch apply.

    A claim that already has a proof-dossier-backed inference concluding it can only be
    verified through an active route that *concludes it* — but agents often attach such
    inferences to a parent/sibling route (e.g. the package lemma's route), leaving the
    claim with no route of its own, so the verifier is never scheduled and the proof
    hangs. Here we close that gap structurally: for any non-terminal claim that has a
    dossier-backed inference but no active route concluding it, auto-create one route
    concluding the claim and move that inference onto it. No agent required.
    """
    routed = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT conclusion_claim_id FROM routes WHERE status = 'active'"
        ).fetchall()
    }
    for claim_id, vstatus in conn.execute(
        "SELECT claim_id, validation_status FROM claims"
    ).fetchall():
        if vstatus in ("informally_verified", "formally_verified", "refuted"):
            continue
        if claim_id in routed:
            continue
        dossier_inf = None
        for inf_id, ev_json in conn.execute(
            "SELECT inference_id, evidence_artifact_ids_json FROM inferences WHERE conclusion_claim_id = ?",
            (claim_id,),
        ).fetchall():
            if _route_ready_inference_evidence(conn, claim_id, ev_json):
                dossier_inf = inf_id
                break
        if not dossier_inf:
            continue
        route_id = f"route-auto-{claim_id}"
        if conn.execute("SELECT 1 FROM routes WHERE route_id = ?", (route_id,)).fetchone():
            continue
        now = utc_now()
        conn.execute(
            """
            INSERT INTO routes(
                route_id, conclusion_claim_id, label, strategy, status, relation_to_parent,
                assumptions_json, conditions_json, evidence_artifact_ids_json,
                failure_fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                route_id,
                claim_id,
                f"auto-assembled route for {claim_id}",
                "auto_assembled_from_dossier",
                "active",
                "sufficient",
                "[]",
                "[]",
                "[]",
                "",
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE inferences SET route_id = ?, updated_at = ? WHERE inference_id = ?",
            (route_id, now, dossier_inf),
        )
        routed.add(claim_id)


def _ensure_verified_statement_repairs_supersede_stale_work(conn: sqlite3.Connection) -> None:
    """Mark stale exact-wording claims/routes superseded after a verified repair.

    A common research pattern is: a verifier rejects the old exact statement,
    the researcher creates a tagged ``statement_repair`` child, and the verifier
    certifies that corrected theorem. At that point the old unverified wording
    should stop receiving ordinary proof work.
    """
    now = utc_now()
    for claim in conn.execute(
        """
        SELECT claim_id, parent_ids_json, tags_json, validation_status, lifecycle_status
        FROM claims
        """
    ).fetchall():
        tags = set(json_loads(claim["tags_json"]))
        if "statement_repair" not in tags:
            continue
        if claim["validation_status"] not in {"informally_verified", "formally_verified"} and claim["lifecycle_status"] != "integrated":
            continue
        for parent_id in [str(item) for item in json_loads(claim["parent_ids_json"]) if str(item)]:
            if parent_id == "root":
                continue
            parent = conn.execute(
                "SELECT validation_status, lifecycle_status FROM claims WHERE claim_id = ?",
                (parent_id,),
            ).fetchone()
            if parent is None:
                continue
            if parent["lifecycle_status"] in {"active", "blocked"} and parent["validation_status"] not in {"informally_verified", "formally_verified", "refuted"}:
                conn.execute(
                    "UPDATE claims SET lifecycle_status = 'superseded', updated_at = ? WHERE claim_id = ?",
                    (now, parent_id),
                )
            for route in conn.execute(
                "SELECT route_id, status FROM routes WHERE conclusion_claim_id = ?",
                (parent_id,),
            ).fetchall():
                if route["status"] not in {"active", "blocked"}:
                    continue
                verified_inference = conn.execute(
                    """
                    SELECT 1 FROM inferences
                    WHERE route_id = ?
                    AND validation_status IN ('informally_verified', 'formally_verified')
                    LIMIT 1
                    """,
                    (route["route_id"],),
                ).fetchone()
                if verified_inference:
                    continue
                conn.execute(
                    "UPDATE routes SET status = 'superseded', updated_at = ? WHERE route_id = ?",
                    (now, route["route_id"]),
                )


def _add_route(conn: sqlite3.Connection, op: Dict[str, Any]) -> None:
    route_id = _required(op, "route_id")
    if conn.execute("SELECT 1 FROM routes WHERE route_id = ?", (route_id,)).fetchone():
        raise PatchRejected([f"route already exists: {route_id}"])
    conclusion = _required(op, "conclusion_claim_id")
    claim_row = conn.execute(
        "SELECT lifecycle_status FROM claims WHERE claim_id = ?",
        (conclusion,),
    ).fetchone()
    if not claim_row:
        raise PatchRejected([f"route has dangling conclusion: {conclusion}"])
    relation = op.get("relation_to_parent", "sufficient")
    status = op.get("status", "active")
    if relation not in ROUTE_RELATIONS or status not in ROUTE_STATUSES:
        raise PatchRejected(["invalid route status or relation"])
    if claim_row["lifecycle_status"] == "integrated" and relation == "sufficient" and status == "active":
        raise PatchRejected([
            f"claim {conclusion} is already integrated; add evidence to an existing route/inference or work a root-synthesis debt instead of opening a new active sufficient route"
        ])
    strategy = op.get("strategy", "")
    if strategy.strip():
        existing_routes = [
            dict(row)
            for row in conn.execute(
                "SELECT route_id, conclusion_claim_id, relation_to_parent, strategy FROM routes WHERE conclusion_claim_id = ?",
                (conclusion,),
            ).fetchall()
        ]
        duplicate_route = obvious_duplicate_route_id(
            existing_routes,
            conclusion_claim_id=conclusion,
            relation_to_parent=relation,
            strategy=strategy,
        )
        if duplicate_route:
            raise PatchRejected([f"duplicate route strategy matches existing route {duplicate_route}; reuse or repair that route"])
    now = utc_now()
    conn.execute(
        """
        INSERT INTO routes(
            route_id, conclusion_claim_id, label, strategy, status, relation_to_parent,
            assumptions_json, conditions_json, evidence_artifact_ids_json,
            failure_fingerprint, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            route_id,
            conclusion,
            op.get("label", route_id),
            strategy,
            status,
            relation,
            json_dumps(op.get("assumptions", [])),
            json_dumps(op.get("conditions", [])),
            json_dumps(op.get("evidence_artifact_ids", [])),
            op.get("failure_fingerprint", ""),
            now,
            now,
        ),
    )


def _add_inference(conn: sqlite3.Connection, op: Dict[str, Any]) -> None:
    inference_id = _required(op, "inference_id")
    if conn.execute("SELECT 1 FROM inferences WHERE inference_id = ?", (inference_id,)).fetchone():
        raise PatchRejected([f"inference already exists: {inference_id}"])
    route_id = _required(op, "route_id")
    conclusion = _required(op, "conclusion_claim_id")
    if not conn.execute("SELECT 1 FROM routes WHERE route_id = ?", (route_id,)).fetchone():
        raise PatchRejected([f"dangling route: {route_id}"])
    if not conn.execute("SELECT 1 FROM claims WHERE claim_id = ?", (conclusion,)).fetchone():
        raise PatchRejected([f"dangling conclusion: {conclusion}"])
    validation = op.get("validation_status", "untested")
    if validation not in INFERENCE_STATUSES:
        raise PatchRejected([f"invalid inference validation_status: {validation}"])
    if validation in {"informally_verified", "formally_verified", "refuted"}:
        raise PatchRejected(["new inferences must be created as untested, plausible, or challenged; use an evidence-gated transition to verify or refute"])
    premise_ids = op.get("premise_claim_ids", [])
    if not isinstance(premise_ids, list):
        raise PatchRejected(["premise_claim_ids must be a list"])
    for premise_id in premise_ids:
        if not conn.execute("SELECT 1 FROM claims WHERE claim_id = ?", (premise_id,)).fetchone():
            raise PatchRejected([f"dangling premise: {premise_id}"])
    now = utc_now()
    conn.execute(
        """
        INSERT INTO inferences(
            inference_id, route_id, conclusion_claim_id, explanation,
            conditions_json, condition_claim_ids_json, validation_status,
            evidence_artifact_ids_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            inference_id,
            route_id,
            conclusion,
            op.get("explanation", ""),
            json_dumps(op.get("conditions", [])),
            json_dumps(op.get("condition_claim_ids", [])),
            validation,
            json_dumps(op.get("evidence_artifact_ids", [])),
            now,
            now,
        ),
    )
    for index, premise_id in enumerate(premise_ids):
        conn.execute(
            "INSERT INTO inference_premises(inference_id, premise_claim_id, position) VALUES (?, ?, ?)",
            (inference_id, premise_id, index),
        )


def _update_inference(conn: sqlite3.Connection, op: Dict[str, Any]) -> None:
    inference_id = _required(op, "inference_id")
    row = conn.execute("SELECT * FROM inferences WHERE inference_id = ?", (inference_id,)).fetchone()
    if row is None:
        raise PatchRejected([f"unknown inference: {inference_id}"])

    evidence_ids = op.get("add_evidence_artifact_ids", op.get("evidence_artifact_ids", []))
    if not isinstance(evidence_ids, list):
        raise PatchRejected(["update_inference evidence ids must be a list"])
    for artifact_id in evidence_ids:
        if not conn.execute("SELECT 1 FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone():
            raise PatchRejected([f"unknown evidence artifact: {artifact_id}"])

    explanation = str(row["explanation"] or "")
    append = str(op.get("explanation_append") or op.get("argument_summary_append") or "").strip()
    if append:
        explanation = f"{explanation.rstrip()}\n\n{append}" if explanation.strip() else append

    conn.execute(
        """
        UPDATE inferences
        SET explanation = ?,
            evidence_artifact_ids_json = ?,
            updated_at = ?
        WHERE inference_id = ?
        """,
        (
            explanation,
            json_dumps(sorted(set(_inference_evidence(conn, inference_id) + [str(aid) for aid in evidence_ids]))),
            utc_now(),
            inference_id,
        ),
    )


def _debt_operation(
    conn: sqlite3.Connection,
    patch: Dict[str, Any],
    op: Dict[str, Any],
    *,
    pending_owners: Mapping[str, set[str]] | None = None,
) -> None:
    kind = op["op"]
    if kind == "resolve_debt":
        debt_id = _required(op, "debt_id")
        row = conn.execute("SELECT * FROM debts WHERE debt_id = ?", (debt_id,)).fetchone()
        if row is None:
            raise PatchRejected([f"unknown debt: {debt_id}"])
        evidence = dict(op.get("resolution_evidence", {}))
        actor = str(patch.get("actor_role") or "")
        if actor not in VERIFYING_ROLES:
            evidence.setdefault("repair_submitted_by", actor)
            evidence.setdefault("resolution_status", "repair_submitted_pending_verifier")
            conn.execute(
                """
                UPDATE debts
                SET status = 'active',
                    last_seen = ?,
                    suggested_next_target = ?,
                    resolution_evidence_json = ?
                WHERE debt_id = ?
                """,
                (
                    utc_now(),
                    op.get("suggested_next_target", row["suggested_next_target"]),
                    json_dumps(evidence),
                    debt_id,
                ),
            )
            return
        conn.execute(
            "UPDATE debts SET status = 'resolved', last_seen = ?, resolution_evidence_json = ? WHERE debt_id = ?",
            (utc_now(), json_dumps(evidence), debt_id),
        )
        return

    if kind == "update_debt":
        debt_id = _required(op, "debt_id")
        row = conn.execute("SELECT * FROM debts WHERE debt_id = ?", (debt_id,)).fetchone()
        if row is None:
            raise PatchRejected([f"unknown debt: {debt_id}"])
        status = _normalize_debt_status(op.get("status", row["status"]))
        severity = _normalize_debt_severity(op.get("severity", row["severity"]))
        if status not in DEBT_STATUSES or severity not in DEBT_SEVERITIES:
            raise PatchRejected(["invalid debt status or severity"])
        resolution_json = row["resolution_evidence_json"]
        resolution_note = str(op.get("resolution_note") or "").strip()
        resolution_ids = [str(item) for item in (op.get("resolution_evidence_artifact_ids") or []) if str(item or "")]
        resolution_extra = op.get("resolution_evidence") if isinstance(op.get("resolution_evidence"), Mapping) else {}
        if resolution_note or resolution_ids or resolution_extra:
            evidence = json_loads(resolution_json, {})
            if not isinstance(evidence, dict):
                evidence = {}
            evidence.update(resolution_extra)
            if resolution_note:
                evidence["resolution_note"] = resolution_note
            if resolution_ids:
                evidence["resolution_evidence_artifact_ids"] = sorted(
                    set(list(evidence.get("resolution_evidence_artifact_ids", [])) + resolution_ids)
                )
            resolution_json = json_dumps(evidence)
        conn.execute(
            "UPDATE debts SET status = ?, severity = ?, last_seen = ?, suggested_next_target = ?, resolution_evidence_json = ? WHERE debt_id = ?",
            (status, severity, utc_now(), op.get("suggested_next_target", row["suggested_next_target"]), resolution_json, debt_id),
        )
        return

    owner_type = _required(op, "owner_type")
    owner_id = _required(op, "owner_id")
    _check_owner_exists(conn, owner_type, owner_id, pending_owners=pending_owners)
    obligation = _required(op, "obligation")
    fingerprint = op.get("fingerprint") or fingerprint_text(obligation)
    severity = _normalize_debt_severity(op.get("severity", "major"))
    status = _normalize_debt_status(op.get("status", "active"))
    if severity not in DEBT_SEVERITIES or status not in DEBT_STATUSES:
        raise PatchRejected(["invalid debt status or severity"])
    existing = conn.execute(
        "SELECT * FROM debts WHERE owner_type = ? AND owner_id = ? AND fingerprint = ?",
        (owner_type, owner_id, fingerprint),
    ).fetchone()
    now = utc_now()
    if existing:
        _refresh_existing_debt(conn, existing, op, now, severity=severity, status=status)
        return
    debt_id = op.get("debt_id") or f"debt-{fingerprint}"
    existing_by_id = conn.execute("SELECT * FROM debts WHERE debt_id = ?", (debt_id,)).fetchone()
    if existing_by_id:
        if existing_by_id["owner_type"] != owner_type or existing_by_id["owner_id"] != owner_id:
            raise PatchRejected([f"debt_id {debt_id} already exists for a different owner"])
        _refresh_existing_debt(conn, existing_by_id, op, now, severity=severity, status=status)
        return
    conn.execute(
        """
        INSERT INTO debts(
            debt_id, owner_type, owner_id, obligation, fingerprint, debt_type,
            severity, status, first_seen, last_seen, repeated_count,
            source_artifact_ids_json, suggested_next_target, resolution_evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, '{}')
        """,
        (
            debt_id,
            owner_type,
            owner_id,
            obligation,
            fingerprint,
            op.get("debt_type", "gap"),
            severity,
            status,
            now,
            now,
            json_dumps(op.get("source_artifact_ids", [])),
            op.get("suggested_next_target", owner_id),
        ),
    )


def _refresh_existing_debt(
    conn: sqlite3.Connection,
    existing: sqlite3.Row,
    op: Dict[str, Any],
    now: str,
    *,
    severity: str,
    status: str,
) -> None:
    source_ids = sorted(set(json_loads(existing["source_artifact_ids_json"]) + list(op.get("source_artifact_ids", []))))
    conn.execute(
        """
        UPDATE debts
        SET last_seen = ?,
            repeated_count = repeated_count + 1,
            source_artifact_ids_json = ?,
            severity = ?,
            status = ?,
            suggested_next_target = ?
        WHERE debt_id = ?
        """,
        (
            now,
            json_dumps(source_ids),
            _stronger_debt_severity(existing["severity"], severity),
            status,
            op.get("suggested_next_target", existing["suggested_next_target"]),
            existing["debt_id"],
        ),
    )


def _stronger_debt_severity(current: str, proposed: str) -> str:
    rank = {"minor": 0, "major": 1, "blocking": 2}
    return proposed if rank.get(proposed, -1) > rank.get(current, -1) else current


def _normalize_debt_severity(value: Any) -> str:
    text = str(value or "major").strip().lower()
    aliases = {
        "critical": "blocking",
        "severe": "blocking",
        "blocker": "blocking",
        "blocked": "blocking",
        "high": "major",
        "medium": "major",
        "normal": "major",
        "low": "minor",
    }
    return aliases.get(text, text)


def _normalize_debt_status(value: Any) -> str:
    text = str(value or "active").strip().lower()
    aliases = {
        "open": "active",
        "opened": "active",
        "pending": "active",
        "todo": "active",
        "to_do": "active",
        "unresolved": "active",
        "blocked": "active",
        "blocking": "active",
        "closed": "resolved",
        "done": "resolved",
        "fixed": "resolved",
        "complete": "resolved",
        "completed": "resolved",
        "discard": "discarded",
        "abandoned": "discarded",
        "irrelevant": "discarded",
    }
    return aliases.get(text, text)


def _status_transition(conn: sqlite3.Connection, patch: Dict[str, Any], op: Dict[str, Any]) -> None:
    target_type = op.get("target_type", "claim")
    target_id = _required(op, "target_id")
    status_type = op.get("status_type", "validation")
    new_status = _required(op, "new_status")
    actor = patch["actor_role"]
    evidence_ids = list(op.get("evidence_artifact_ids") or patch.get("evidence_artifact_ids", []))

    if actor == WRITING_CRITIC_ROLE:
        raise PatchRejected([
            "writing_critic may not transition claim, inference, or route statuses; "
            "report findings as writing debts and writing_review artifacts only"
        ])
    if target_type not in {"claim", "inference", "route"}:
        raise PatchRejected([f"unsupported transition target_type: {target_type}"])
    if target_type == "route":
        if status_type not in {"validation", "route"}:
            raise PatchRejected([f"unsupported status_type for route transition: {status_type}"])
        if new_status not in ROUTE_STATUSES:
            raise PatchRejected([f"invalid route status: {new_status}"])
        if new_status == "integrated":
            raise PatchRejected(["route integration must be performed by the claim integration workflow"])
        if new_status == "abandoned":
            _guard_debt_bearing_route_not_abandoned(conn, target_id)
        _set_route_status(conn, {"route_id": target_id}, new_status)
        return
    if status_type not in {"validation", "lifecycle"}:
        raise PatchRejected([f"unsupported status_type: {status_type}"])
    if status_type == "validation" and new_status not in VALIDATION_STATUSES:
        raise PatchRejected([f"invalid validation status: {new_status}"])
    if status_type == "lifecycle" and new_status not in LIFECYCLE_STATUSES:
        raise PatchRejected([f"invalid lifecycle status: {new_status}"])

    if new_status in {"informally_verified", "formally_verified", "refuted"}:
        _guard_verifying_actor(actor, new_status, target_type, target_id)
    if new_status == "informally_verified" and not _has_correct_verification(conn, evidence_ids, producer_role="strict_informal_verifier"):
        raise PatchRejected(["informally_verified requires a strict_informal_verifier verification_report artifact with zero errors and gaps"])
    if new_status == "formally_verified" and not _has_artifact_type(conn, evidence_ids, "formal_backend_result", producer_role="formal_backend"):
        raise PatchRejected(["formally_verified requires formal_backend_result evidence produced by formal_backend"])
    if new_status == "refuted":
        has_confirmed_counterexample = _has_artifact_type(conn, evidence_ids, "confirmed_counterexample", producer_role="counterexample_validator")
        has_strict_refutation_report = (
            actor == "strict_informal_verifier"
            and _has_correct_verification(conn, evidence_ids, producer_role="strict_informal_verifier")
        )
        if not has_confirmed_counterexample and not has_strict_refutation_report:
            raise PatchRejected(["refuted requires confirmed_counterexample evidence or a zero-gap strict_informal_verifier verification_report"])

    if status_type == "lifecycle" and new_status == "integrated":
        if actor != "integration_verifier":
            raise PatchRejected(["integrated lifecycle transition requires integration_verifier actor"])
        if target_type != "claim":
            raise PatchRejected(["only claims can receive integrated lifecycle status"])
        resolved_debt_ids = _integration_resolved_debt_ids(conn, op, evidence_ids)
        _guard_integration(conn, target_id, op.get("route_id"), evidence_ids, resolved_debt_ids=resolved_debt_ids)
        conn.execute("UPDATE routes SET status = 'integrated', updated_at = ? WHERE route_id = ?", (utc_now(), op.get("route_id")))
        _resolve_integration_debts(
            conn,
            resolved_debt_ids,
            claim_id=target_id,
            route_id=str(op.get("route_id") or ""),
            evidence_ids=evidence_ids,
        )

    if target_type == "claim":
        if not conn.execute("SELECT 1 FROM claims WHERE claim_id = ?", (target_id,)).fetchone():
            raise PatchRejected([f"unknown claim: {target_id}"])
        if target_id == "root" and status_type == "validation" and new_status == "refuted" and not op.get("confirmed_root_counterexample"):
            raise PatchRejected(["root theorem refutation requires confirmed_root_counterexample=true"])
        if target_id == "root" and status_type == "validation" and new_status == "refuted":
            root_row = conn.execute("SELECT statement FROM claims WHERE claim_id = 'root'").fetchone()
            if root_row and statement_is_interrogative_problem(str(root_row[0] or "")):
                raise PatchRejected(["an interrogative root problem cannot be marked refuted; record the checked example as partial evidence and keep the root active"])
        col = "validation_status" if status_type == "validation" else "lifecycle_status"
        conn.execute(
            f"UPDATE claims SET {col} = ?, evidence_artifact_ids_json = ?, updated_at = ? WHERE claim_id = ?",
            (new_status, json_dumps(sorted(set(_claim_evidence(conn, target_id) + evidence_ids))), utc_now(), target_id),
        )
    elif target_type == "inference":
        if not conn.execute("SELECT 1 FROM inferences WHERE inference_id = ?", (target_id,)).fetchone():
            raise PatchRejected([f"unknown inference: {target_id}"])
        if status_type != "validation":
            raise PatchRejected(["inferences support validation transitions only"])
        conn.execute(
            "UPDATE inferences SET validation_status = ?, evidence_artifact_ids_json = ?, updated_at = ? WHERE inference_id = ?",
            (new_status, json_dumps(sorted(set(_inference_evidence(conn, target_id) + evidence_ids))), utc_now(), target_id),
        )


def _guard_verifying_actor(actor: str, new_status: str, target_type: str, target_id: str) -> None:
    expected_by_status = {
        "informally_verified": {"strict_informal_verifier"},
        "formally_verified": {"formal_backend"},
        "refuted": {"counterexample_validator", "strict_informal_verifier"},
    }
    allowed = expected_by_status.get(new_status, set())
    if actor not in allowed:
        expected = ", ".join(sorted(allowed)) or "a verifying role"
        raise PatchRejected([f"{actor} cannot mark {target_type} {target_id} as {new_status}; expected {expected}"])


def _guard_integration(
    conn: sqlite3.Connection,
    claim_id: str,
    route_id: Optional[str],
    evidence_ids: Sequence[str],
    *,
    resolved_debt_ids: Sequence[str] = (),
) -> None:
    if not route_id:
        raise PatchRejected(["integration requires route_id"])
    route = conn.execute("SELECT * FROM routes WHERE route_id = ?", (route_id,)).fetchone()
    if route is None:
        raise PatchRejected([f"unknown route: {route_id}"])
    if route["conclusion_claim_id"] != claim_id:
        raise PatchRejected(["integration route conclusion does not match target claim"])
    if route["relation_to_parent"] != "sufficient":
        raise PatchRejected(["only sufficient routes can support integration"])
    conclusion = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if conclusion is None or conclusion["validation_status"] not in VERIFIED_STATUSES:
        raise PatchRejected([f"claim {claim_id} is not verified"])
    integration_errors = _integration_report_errors(conn, evidence_ids, claim_id=claim_id, route=route, producer_role="integration_verifier")
    if integration_errors:
        raise PatchRejected(integration_errors)
    inferences = list(conn.execute("SELECT * FROM inferences WHERE route_id = ?", (route_id,)))
    if not inferences:
        raise PatchRejected(["integration route has no inferences"])
    blocker_owner_ids = [claim_id, route_id, *[str(inf["inference_id"]) for inf in inferences]]
    placeholders = ", ".join("?" for _ in blocker_owner_ids)
    blockers = list(
        conn.execute(
            f"SELECT * FROM debts WHERE owner_id IN ({placeholders}) AND status = 'active' AND severity = 'blocking'",
            blocker_owner_ids,
        )
    )
    resolved = set(resolved_debt_ids)
    clean_verification_by_owner = _clean_verification_times_for_route(conn, conclusion, inferences)
    if any(
        _debt_blocks_integration(
            row,
            claim_id=claim_id,
            clean_verification_by_owner=clean_verification_by_owner,
        )
        for row in blockers
        if row["debt_id"] not in resolved
    ):
        raise PatchRejected(["active blocking debt prevents integration"])
    verified_terminal_inferences = []
    for inf in inferences:
        if (
            str(inf["conclusion_claim_id"] or "") != claim_id
            or inf["validation_status"] not in VERIFIED_STATUSES
        ):
            continue
        premises_verified = True
        for premise in conn.execute(
            "SELECT premise_claim_id FROM inference_premises WHERE inference_id = ?",
            (inf["inference_id"],),
        ):
            claim = conn.execute(
                "SELECT validation_status FROM claims WHERE claim_id = ?",
                (premise["premise_claim_id"],),
            ).fetchone()
            if claim is None or claim["validation_status"] not in VERIFIED_STATUSES:
                premises_verified = False
                break
        if premises_verified:
            verified_terminal_inferences.append(str(inf["inference_id"]))
    if not verified_terminal_inferences:
        raise PatchRejected([
            "integration route has no verified terminal inference with verified premises"
        ])


def _integration_resolved_debt_ids(conn: sqlite3.Connection, op: Mapping[str, Any], evidence_ids: Sequence[str]) -> List[str]:
    ids = _string_list(op.get("resolved_debt_ids"))
    if ids:
        return sorted(set(ids))
    for aid in evidence_ids:
        row = conn.execute("SELECT artifact_type, metadata_json FROM artifacts WHERE artifact_id = ?", (aid,)).fetchone()
        if not row or row["artifact_type"] != "integration_report":
            continue
        metadata = json_loads(row["metadata_json"], {})
        ids.extend(_string_list(metadata.get("resolved_debt_ids")))
    return sorted(set(ids))


def _resolve_integration_debts(
    conn: sqlite3.Connection,
    debt_ids: Sequence[str],
    *,
    claim_id: str,
    route_id: str,
    evidence_ids: Sequence[str],
) -> None:
    if not debt_ids:
        return
    route_inference_ids = {
        row["inference_id"]
        for row in conn.execute("SELECT inference_id FROM inferences WHERE route_id = ?", (route_id,))
    }
    allowed_owner_ids = {claim_id, route_id, *route_inference_ids}
    now = utc_now()
    for debt_id in debt_ids:
        row = conn.execute("SELECT * FROM debts WHERE debt_id = ?", (debt_id,)).fetchone()
        if row is None:
            raise PatchRejected([f"unknown resolved_debt_id for integration: {debt_id}"])
        suggested = str(row["suggested_next_target"] or "")
        owner_id = str(row["owner_id"] or "")
        if owner_id not in allowed_owner_ids and suggested not in {claim_id, route_id, *route_inference_ids}:
            raise PatchRejected([f"integration cannot resolve unrelated debt: {debt_id}"])
        evidence = json_loads(row["resolution_evidence_json"], {})
        if not isinstance(evidence, dict):
            evidence = {}
        evidence.update(
            {
                "resolved_by": "integration_verifier",
                "resolution_status": "closed_by_integrated_route",
                "claim_id": claim_id,
                "route_id": route_id,
                "evidence_artifact_ids": list(evidence_ids),
            }
        )
        conn.execute(
            "UPDATE debts SET status = 'resolved', last_seen = ?, resolution_evidence_json = ? WHERE debt_id = ?",
            (now, json_dumps(evidence), debt_id),
        )


def _latest_clean_claim_verification_at(
    conn: sqlite3.Connection,
    evidence_ids: Sequence[str],
) -> str:
    """Timestamp of the newest clean verifier/formal certificate on an entity."""
    latest = ""
    for artifact_id in evidence_ids:
        row = conn.execute(
            "SELECT artifact_type, producer_role, created_at FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if not row:
            continue
        artifact_type = str(row["artifact_type"] or "")
        producer_role = str(row["producer_role"] or "")
        clean = (
            artifact_type == "verification_report"
            and producer_role == "strict_informal_verifier"
            and _has_correct_verification(
                conn,
                [artifact_id],
                producer_role="strict_informal_verifier",
            )
        ) or (
            artifact_type == "formal_backend_result"
            and producer_role == "formal_backend"
        )
        if clean:
            latest = max(latest, str(row["created_at"] or ""))
    return latest


def _clean_verification_times_for_route(
    conn: sqlite3.Connection,
    claim: sqlite3.Row | None,
    inferences: Sequence[sqlite3.Row],
) -> Dict[str, str]:
    times: Dict[str, str] = {}
    if claim is not None:
        times[str(claim["claim_id"] or "")] = _latest_clean_claim_verification_at(
            conn,
            json_loads(claim["evidence_artifact_ids_json"], []),
        )
    for inference in inferences:
        times[str(inference["inference_id"] or "")] = _latest_clean_claim_verification_at(
            conn,
            json_loads(inference["evidence_artifact_ids_json"], []),
        )
    return times


def _resolve_stale_verified_entity_debts(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Resolve blockers superseded by a later zero-gap entity verification.

    Claim and inference verification are entity-local.  They may supersede an
    older blocker owned by that exact entity, but never route-level assembly or
    source-to-target bridge debt.
    """

    changes: List[Dict[str, Any]] = []
    for owner_type, table, id_column in (
        ("claim", "claims", "claim_id"),
        ("inference", "inferences", "inference_id"),
    ):
        rows = conn.execute(
            f"""
            SELECT {id_column} AS entity_id, evidence_artifact_ids_json
            FROM {table}
            WHERE validation_status IN ('informally_verified', 'formally_verified')
            """
        )
        for row in rows:
            entity_id = str(row["entity_id"] or "")
            clean_verification_at = _latest_clean_claim_verification_at(
                conn,
                json_loads(row["evidence_artifact_ids_json"], []),
            )
            if not clean_verification_at:
                continue
            debts = list(
                conn.execute(
                    """
                    SELECT * FROM debts
                    WHERE owner_type = ?
                      AND owner_id = ?
                      AND status = 'active'
                      AND severity = 'blocking'
                      AND last_seen < ?
                    """,
                    (owner_type, entity_id, clean_verification_at),
                )
            )
            for debt in debts:
                evidence = json_loads(debt["resolution_evidence_json"], {})
                if not isinstance(evidence, dict):
                    evidence = {}
                evidence.update(
                    {
                        "resolved_by": "system",
                        "resolution_status": "superseded_by_later_clean_verification",
                        "owner_type": owner_type,
                        "owner_id": entity_id,
                        "verification_at": clean_verification_at,
                    }
                )
                conn.execute(
                    "UPDATE debts SET status = 'resolved', resolution_evidence_json = ? WHERE debt_id = ?",
                    (json_dumps(evidence), debt["debt_id"]),
                )
                changes.append(
                    {
                        "entity_type": "debt",
                        "entity_id": str(debt["debt_id"] or ""),
                        "owner_type": owner_type,
                        "owner_id": entity_id,
                        "from_status": "active",
                        "to_status": "resolved",
                        "reason": "superseded by later clean verification of the same entity",
                        "verification_at": clean_verification_at,
                    }
                )
    return changes


def _debt_blocks_integration(
    debt: sqlite3.Row,
    *,
    claim_id: str,
    clean_verification_by_owner: Mapping[str, str] | None = None,
) -> bool:
    owner_type = str(debt["owner_type"] or "")
    owner_id = str(debt["owner_id"] or "")
    clean_verification_at = str((clean_verification_by_owner or {}).get(owner_id) or "")
    if (
        owner_type in {"claim", "inference"}
        and clean_verification_at
        and clean_verification_at > str(debt["last_seen"] or "")
    ):
        return False
    if owner_type != "claim" or owner_id != claim_id:
        return True
    debt_type = str(debt["debt_type"] or "")
    if debt_type == "missing_proof_or_counterexample":
        return False
    if debt_type == "blocking_bridge" and _looks_like_downstream_claim_debt(debt):
        return False
    # A later zero-gap strict/formal certificate adjudicates the exact claim
    # after this debt was recorded.  The old debt may still describe useful
    # downstream root work, but it must not trap the already verified claim in
    # an endless integration-rejection loop.  Any blocker added or refreshed
    # after the certificate remains binding.
    return True


def _route_integration_health(conn: sqlite3.Connection, route: sqlite3.Row) -> Dict[str, Any]:
    """Return the current structural integration verdict for one route."""

    route_id = str(route["route_id"] or "")
    claim_id = str(route["conclusion_claim_id"] or "")
    issues: List[str] = []
    if str(route["relation_to_parent"] or "") != "sufficient":
        issues.append("route is not sufficient")

    claim = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if claim is None:
        issues.append("conclusion claim is missing")
    else:
        if str(claim["validation_status"] or "") not in VERIFIED_STATUSES:
            issues.append("conclusion claim is not verified")

    inferences = list(conn.execute("SELECT * FROM inferences WHERE route_id = ?", (route_id,)))
    if not inferences:
        issues.append("route has no inferences")

    verified_terminal_ids: List[str] = []
    for inference in inferences:
        if (
            str(inference["conclusion_claim_id"] or "") != claim_id
            or str(inference["validation_status"] or "") not in VERIFIED_STATUSES
        ):
            continue
        premises_verified = True
        for premise in conn.execute(
            "SELECT premise_claim_id FROM inference_premises WHERE inference_id = ?",
            (inference["inference_id"],),
        ):
            premise_claim = conn.execute(
                "SELECT validation_status FROM claims WHERE claim_id = ?",
                (premise["premise_claim_id"],),
            ).fetchone()
            if premise_claim is None or str(premise_claim["validation_status"] or "") not in VERIFIED_STATUSES:
                premises_verified = False
                break
        if premises_verified:
            verified_terminal_ids.append(str(inference["inference_id"] or ""))
    if not verified_terminal_ids:
        issues.append("route has no verified terminal inference with verified premises")

    owner_ids = {claim_id, route_id, *[str(row["inference_id"] or "") for row in inferences]}
    clean_verification_by_owner = _clean_verification_times_for_route(conn, claim, inferences)
    blocking_debt_ids = [
        str(debt["debt_id"] or "")
        for debt in conn.execute(
            "SELECT * FROM debts WHERE status = 'active' AND severity = 'blocking'"
        )
        if str(debt["owner_id"] or "") in owner_ids
        and _debt_blocks_integration(
            debt,
            claim_id=claim_id,
            clean_verification_by_owner=clean_verification_by_owner,
        )
    ]
    if blocking_debt_ids:
        issues.append("active blocking debt")

    return {
        "route_id": route_id,
        "claim_id": claim_id,
        "valid": not issues,
        "issues": issues,
        "blocking_debt_ids": sorted(blocking_debt_ids),
        "verified_terminal_inference_ids": sorted(verified_terminal_ids),
    }


def _reconcile_invalid_integrations(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Demote integrated routes and claims invalidated by later proof-state changes."""

    now = utc_now()
    changes: List[Dict[str, Any]] = []
    invalidated_claim_modes: Dict[str, str] = {}
    integrated_routes = list(conn.execute("SELECT * FROM routes WHERE status = 'integrated'"))
    for route in integrated_routes:
        health = _route_integration_health(conn, route)
        claim = conn.execute(
            "SELECT lifecycle_status FROM claims WHERE claim_id = ?",
            (health["claim_id"],),
        ).fetchone()
        if claim is None or str(claim["lifecycle_status"] or "") != "integrated":
            health["valid"] = False
            health["issues"] = [*health["issues"], "conclusion claim is not integrated"]
        if health["valid"]:
            continue

        new_route_status = "blocked" if health["blocking_debt_ids"] else "active"
        conn.execute(
            "UPDATE routes SET status = ?, updated_at = ? WHERE route_id = ?",
            (new_route_status, now, health["route_id"]),
        )
        if health["claim_id"]:
            previous = invalidated_claim_modes.get(health["claim_id"], "active")
            invalidated_claim_modes[health["claim_id"]] = (
                "blocked" if new_route_status == "blocked" or previous == "blocked" else "active"
            )
        changes.append(
            {
                "entity_type": "route",
                "entity_id": health["route_id"],
                "claim_id": health["claim_id"],
                "from_status": "integrated",
                "to_status": new_route_status,
                "reasons": health["issues"],
                "blocking_debt_ids": health["blocking_debt_ids"],
            }
        )

    integrated_claims = list(conn.execute("SELECT * FROM claims WHERE lifecycle_status = 'integrated'"))
    for claim in integrated_claims:
        claim_id = str(claim["claim_id"] or "")
        remaining = conn.execute(
            """
            SELECT 1 FROM routes
            WHERE conclusion_claim_id = ?
              AND relation_to_parent = 'sufficient'
              AND status = 'integrated'
            LIMIT 1
            """,
            (claim_id,),
        ).fetchone()
        if remaining:
            continue
        new_claim_status = invalidated_claim_modes.get(claim_id, "active")
        conn.execute(
            "UPDATE claims SET lifecycle_status = ?, updated_at = ? WHERE claim_id = ?",
            (new_claim_status, now, claim_id),
        )
        changes.append(
            {
                "entity_type": "claim",
                "entity_id": claim_id,
                "from_status": "integrated",
                "to_status": new_claim_status,
                "reasons": ["no currently valid integrated sufficient route"],
            }
        )

    reactivated_claim_ids: set[str] = set()
    for route in list(
        conn.execute(
            "SELECT * FROM routes WHERE status = 'blocked' AND relation_to_parent = 'sufficient'"
        )
    ):
        health = _route_integration_health(conn, route)
        if not health["valid"]:
            continue
        claim = conn.execute(
            "SELECT lifecycle_status FROM claims WHERE claim_id = ?",
            (health["claim_id"],),
        ).fetchone()
        if claim is None or str(claim["lifecycle_status"] or "") == "integrated":
            continue
        conn.execute(
            "UPDATE routes SET status = 'active', updated_at = ? WHERE route_id = ?",
            (now, health["route_id"]),
        )
        reactivated_claim_ids.add(health["claim_id"])
        changes.append(
            {
                "entity_type": "route",
                "entity_id": health["route_id"],
                "claim_id": health["claim_id"],
                "from_status": "blocked",
                "to_status": "active",
                "reasons": ["blocking obligations cleared; integration verification may be retried"],
            }
        )

    for claim_id in sorted(reactivated_claim_ids):
        claim = conn.execute(
            "SELECT lifecycle_status FROM claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if claim is None or str(claim["lifecycle_status"] or "") != "blocked":
            continue
        conn.execute(
            "UPDATE claims SET lifecycle_status = 'active', updated_at = ? WHERE claim_id = ?",
            (now, claim_id),
        )
        changes.append(
            {
                "entity_type": "claim",
                "entity_id": claim_id,
                "from_status": "blocked",
                "to_status": "active",
                "reasons": ["a sufficient route is verification-ready again"],
            }
        )

    return changes


def _looks_like_downstream_claim_debt(debt: sqlite3.Row) -> bool:
    text = " ".join(
        str(debt[key] or "").lower()
        for key in ("debt_id", "obligation", "suggested_next_target")
    )
    downstream_cues = (
        "after",
        "remaining",
        "now forced",
        "once",
        "downstream",
        "bottleneck",
    )
    local_gap_cues = (
        "gap in the proof",
        "missing proof",
        "missing hypothesis",
        "unjustified",
        "not justified",
        "verify the claim",
        "verify this claim",
    )
    return any(cue in text for cue in downstream_cues) and not any(cue in text for cue in local_gap_cues)


def _record_run(conn: sqlite3.Connection, op: Dict[str, Any], *, problem_id: str = "") -> None:
    run_id = _required(op, "run_id")
    mode = _required(op, "mode")
    if mode not in RUN_MODES:
        raise PatchRejected([f"invalid run mode: {mode}"])
    conn.execute(
        """
        INSERT OR REPLACE INTO runs(
            run_id, actor_role, mode, target_id, route_id, state_revision, context_revision,
            session_id, model_profile, model, reasoning_effort, search_setting,
            search_intent, researcher_work_mode, work_mode_source, failure_kind,
            sandbox_setting, budget_requested, input_tokens, cached_input_tokens,
            output_tokens, reasoning_output_tokens, total_tokens, wall_time_seconds,
            peak_memory_mb, status,
            prompt_context_hash, output_artifact_ids_json, error_artifact_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            op.get("actor_role", ""),
            mode,
            op.get("target_id", ""),
            op.get("route_id", ""),
            int(op.get("state_revision", 0)),
            int(op.get("context_revision", 0)),
            op.get("session_id", ""),
            op.get("model_profile", "standard"),
            op.get("model", ""),
            op.get("reasoning_effort", ""),
            op.get("search_setting", "disabled"),
            op.get("search_intent", ""),
            op.get("researcher_work_mode", ""),
            op.get("work_mode_source", ""),
            op.get("failure_kind", ""),
            op.get("sandbox_setting", "workspace-write"),
            int(op.get("budget_requested", 0)),
            int(op.get("input_tokens", 0)),
            int(op.get("cached_input_tokens", 0)),
            int(op.get("output_tokens", 0)),
            int(op.get("reasoning_output_tokens", 0)),
            int(op.get("total_tokens", 0)),
            float(op.get("wall_time_seconds", 0.0)),
            float(op.get("peak_memory_mb", 0.0)),
            op.get("status", "completed"),
            op.get("prompt_context_hash", ""),
            json_dumps(op.get("output_artifact_ids", [])),
            op.get("error_artifact_id", ""),
            utc_now(),
        ),
    )
    spent = run_spend_from_operation(op)
    if spent:
        if problem_id:
            row = conn.execute(
                "SELECT remaining_token_budget FROM problem_state WHERE problem_id = ?", (problem_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT remaining_token_budget FROM problem_state").fetchone()
        remaining = int(row["remaining_token_budget"]) if row else 0
        if problem_id:
            conn.execute(
                "UPDATE problem_state SET remaining_token_budget = ?, updated_at = ? WHERE problem_id = ?",
                (max(0, remaining - spent), utc_now(), problem_id),
            )
        else:
            conn.execute(
                "UPDATE problem_state SET remaining_token_budget = ?, updated_at = ?",
                (max(0, remaining - spent), utc_now()),
            )


def _set_route_status(conn: sqlite3.Connection, op: Dict[str, Any], status: str) -> None:
    route_id = _required(op, "route_id")
    if status not in ROUTE_STATUSES:
        raise PatchRejected([f"invalid route status: {status}"])
    if not conn.execute("SELECT 1 FROM routes WHERE route_id = ?", (route_id,)).fetchone():
        raise PatchRejected([f"unknown route: {route_id}"])
    conn.execute("UPDATE routes SET status = ?, updated_at = ? WHERE route_id = ?", (status, utc_now(), route_id))


def _update_route(conn: sqlite3.Connection, op: Dict[str, Any]) -> None:
    route_id = _required(op, "route_id")
    row = conn.execute("SELECT * FROM routes WHERE route_id = ?", (route_id,)).fetchone()
    if row is None:
        raise PatchRejected([f"unknown route: {route_id}"])

    status = op.get("status")
    if status is not None:
        if status not in ROUTE_STATUSES:
            raise PatchRejected([f"invalid route status: {status}"])
        if status == "integrated":
            raise PatchRejected(["route integration must be performed by the claim integration workflow"])
        if status == "abandoned":
            _guard_debt_bearing_route_not_abandoned(conn, route_id)

    evidence_ids = sorted(set(json_loads(row["evidence_artifact_ids_json"]) + list(op.get("evidence_artifact_ids", []))))
    new_failure_fingerprint = str(op.get("failure_fingerprint") or row["failure_fingerprint"] or "")
    conn.execute(
        """
        UPDATE routes
        SET status = COALESCE(?, status),
            failure_fingerprint = ?,
            evidence_artifact_ids_json = ?,
            updated_at = ?
        WHERE route_id = ?
        """,
        (
            status,
            new_failure_fingerprint,
            json_dumps(evidence_ids),
            utc_now(),
            route_id,
        ),
    )


def _guard_debt_bearing_route_not_abandoned(conn: sqlite3.Connection, route_id: str) -> None:
    route = conn.execute(
        "SELECT route_id, conclusion_claim_id FROM routes WHERE route_id = ?",
        (route_id,),
    ).fetchone()
    if not route:
        raise PatchRejected([f"unknown route: {route_id}"])
    conclusion_claim_id = str(route["conclusion_claim_id"] or "")
    debt = conn.execute(
        """
        SELECT debt_id
        FROM debts
        WHERE status = 'active'
          AND severity = 'blocking'
          AND (
            owner_id IN (?, ?)
            OR suggested_next_target IN (?, ?)
          )
        ORDER BY debt_id
        LIMIT 1
        """,
        (route_id, conclusion_claim_id, route_id, conclusion_claim_id),
    ).fetchone()
    if debt:
        raise PatchRejected([
            f"route {route_id} carries active blocking debt {debt['debt_id']}; "
            "resolve the debt or keep the route active for proof repair instead of abandoning it"
        ])


def _cache_retrieval_card(conn: sqlite3.Connection, op: Dict[str, Any]) -> None:
    card_id = _required(op, "card_id")
    exact = _required(op, "exact_statement")
    supplied_content_hash = op.get("content_hash")
    if _contains_empty_sha256(supplied_content_hash):
        raise PatchRejected(["cache_retrieval_card content_hash appears to be the SHA-256 of empty content"])
    content_hash = _sqlite_text(op.get("content_hash") or fingerprint_text(json.dumps(op, sort_keys=True), length=64))
    duplicate = conn.execute(
        "SELECT card_id FROM retrieval_cards WHERE content_hash = ? ORDER BY retrieved_at ASC LIMIT 1",
        (content_hash,),
    ).fetchone()
    if duplicate and duplicate["card_id"] != card_id:
        return
    applicability = _coerce_json_object(op.get("applicability", {}), note_key="notes")
    applicability.setdefault("target_id", op.get("target_id", "root"))
    relation = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation"))
    applicability["classification"] = relation
    applicability.setdefault("relation", relation)
    applicability.setdefault("theorem_matching_status", "unverified_literature_card")
    applicability.setdefault("implication_to_target_verified", False)
    applicability.setdefault(
        "theorem_matching_confidence",
        theorem_matching_confidence(applicability, missing_hypotheses=op.get("missing_hypotheses", [])),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO retrieval_cards(
            card_id, normalized_query, source_version, exact_statement,
            source_identifiers_json, hypotheses_json, local_definitions_json,
            applicability_json, missing_hypotheses_json, source_location,
            content_hash, retrieved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            card_id,
            normalize_text(op.get("query", exact)),
            _sqlite_text(op.get("source_version", "unknown")),
            _sqlite_text(exact),
            json_dumps(op.get("source_identifiers", {})),
            json_dumps(op.get("hypotheses", [])),
            json_dumps(op.get("local_definitions", [])),
            json_dumps(applicability),
            json_dumps(op.get("missing_hypotheses", [])),
            _sqlite_text(op.get("source_location", "")),
            content_hash,
            utc_now(),
        ),
    )


def _contains_empty_sha256(value: Any) -> bool:
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped == EMPTY_SHA256:
            return True
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return False
        return _contains_empty_sha256(decoded)
    if isinstance(value, Mapping):
        return any(_contains_empty_sha256(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_empty_sha256(item) for item in value)
    return False


def _sqlite_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple)):
        return json_dumps(value)
    return str(value)


def _coerce_json_object(value: Any, *, note_key: str) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value in (None, ""):
        return {}
    return {note_key: _sqlite_text(value)}


def _normalize_citation_relation(value: Any) -> str:
    relation = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "direct": "exact",
        "direct_match": "exact",
        "known_exact": "exact",
        "same": "exact",
        "stronger_match": "stronger",
        "known_stronger": "stronger",
        "equivalent_reformulation": "equivalent",
        "known_equivalent": "equivalent",
    }
    return aliases.get(relation, relation)


def _citation_source_errors(source_ids: Mapping[str, Any], card: sqlite3.Row) -> List[str]:
    source_ids = _primary_citation_source_ids(source_ids)
    errors: list[str] = []
    if not str(source_ids.get("author") or source_ids.get("authors") or "").strip():
        errors.append("external citation certification requires source_identifiers.author or authors")
    if not str(source_ids.get("title") or "").strip():
        errors.append("external citation certification requires source_identifiers.title")
    exact_location = next(
        (
            source_ids.get(key)
            for key in (
                "theorem_number",
                "proposition_number",
                "lemma_number",
                "corollary_number",
                "section",
                "page",
                "section/page",
            )
            if str(source_ids.get(key) or "").strip()
        ),
        "",
    )
    if not str(exact_location or card["source_location"] or "").strip():
        errors.append("external citation certification requires an exact theorem/proposition/lemma/corollary number, section, page, or source_location")
    if not (
        str(source_ids.get("arxiv") or "").strip()
        or str(source_ids.get("doi") or "").strip()
        or str(source_ids.get("url") or "").strip()
        or str(card["source_version"] or "").strip()
    ):
        errors.append("external citation certification requires arXiv, DOI, URL, or source_version")
    return errors


def _primary_citation_source_ids(source_ids: Mapping[str, Any]) -> Dict[str, Any]:
    if str(source_ids.get("author") or source_ids.get("authors") or "").strip() and str(source_ids.get("title") or "").strip():
        return dict(source_ids)
    preferred_keys = (
        "primary_theorem",
        "primary_source",
        "main_source",
        "theorem",
        "source",
        "cited_theorem",
    )
    for key in preferred_keys:
        value = source_ids.get(key)
        if isinstance(value, Mapping) and str(value.get("author") or value.get("authors") or "").strip() and str(value.get("title") or "").strip():
            return dict(value)
    for value in source_ids.values():
        if isinstance(value, Mapping) and str(value.get("author") or value.get("authors") or "").strip() and str(value.get("title") or "").strip():
            return dict(value)
    return dict(source_ids)


def _external_citation_report_content(metadata: Mapping[str, Any]) -> str:
    source_ids = metadata.get("source_identifiers", {})
    if not isinstance(source_ids, Mapping):
        source_ids = {}
    source_ids = _primary_citation_source_ids(source_ids)
    author = source_ids.get("author") or source_ids.get("authors") or "Unknown author"
    title = source_ids.get("title") or "Unknown title"
    location = (
        source_ids.get("theorem_number")
        or source_ids.get("proposition_number")
        or source_ids.get("lemma_number")
        or source_ids.get("corollary_number")
        or source_ids.get("section")
        or source_ids.get("page")
        or source_ids.get("section/page")
        or metadata.get("source_location")
        or "specified theorem location"
    )
    link = source_ids.get("arxiv") or source_ids.get("doi") or source_ids.get("url") or metadata.get("source_version") or ""
    checked_items = metadata.get("verification_report", {}).get("checked_items", []) if isinstance(metadata.get("verification_report"), Mapping) else []
    lines = [
        "# External Citation Verification",
        "",
        f"Claim: `{metadata.get('target_id', '')}`",
        f"Certification type: `{metadata.get('certification_type', 'external_citation')}`",
        f"Relation to target: `{metadata.get('relation_to_target', '')}`",
        f"Retrieval card: `{metadata.get('retrieval_card_id', '')}`",
        "",
        "## Target Statement",
        "",
        str(metadata.get("target_statement") or ""),
        "",
        "## Cited Statement",
        "",
        str(metadata.get("exact_cited_statement") or metadata.get("proved_statement") or ""),
        "",
        "## Source",
        "",
        f"{author}, {title}, {location}" + (f", {link}" if link else "") + ".",
        "",
        "## Verification Checks",
        "",
    ]
    if checked_items:
        lines.extend(f"- {item}" for item in checked_items)
    else:
        lines.append("- The cited theorem was checked against the target statement.")
    lines.extend(
        [
            "",
            "No critical errors or gaps were found in the citation match. This certifies the claim by external citation; it does not reconstruct the proof internally.",
        ]
    )
    return "\n".join(lines) + "\n"


def _upsert_theorem_library_entry(
    conn: sqlite3.Connection,
    *,
    entry_id: str,
    statement: str,
    source_identifiers: Mapping[str, Any],
    source_version: str,
    source_location: str,
    certification_type: str,
    relation_to_target: str,
    evidence_artifact_ids: Sequence[str],
    tags: Sequence[str],
) -> None:
    existing = conn.execute(
        "SELECT evidence_artifact_ids_json, tags_json FROM theorem_library_entries WHERE entry_id = ?",
        (entry_id,),
    ).fetchone()
    now = utc_now()
    if existing:
        evidence = sorted(set(json_loads(existing["evidence_artifact_ids_json"]) + list(evidence_artifact_ids)))
        merged_tags = sorted(set(json_loads(existing["tags_json"]) + list(tags)))
        conn.execute(
            """
            UPDATE theorem_library_entries
            SET statement = ?,
                normalized_statement = ?,
                source_identifiers_json = ?,
                source_version = ?,
                source_location = ?,
                certification_type = ?,
                relation_to_target = ?,
                evidence_artifact_ids_json = ?,
                tags_json = ?,
                updated_at = ?
            WHERE entry_id = ?
            """,
            (
                statement,
                normalize_text(statement),
                json_dumps(dict(source_identifiers)),
                source_version,
                source_location,
                certification_type,
                relation_to_target,
                json_dumps(evidence),
                json_dumps(merged_tags),
                now,
                entry_id,
            ),
        )
        return
    conn.execute(
        """
        INSERT INTO theorem_library_entries(
            entry_id, statement, normalized_statement, source_identifiers_json,
            source_version, source_location, certification_type, relation_to_target,
            evidence_artifact_ids_json, tags_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            statement,
            normalize_text(statement),
            json_dumps(dict(source_identifiers)),
            source_version,
            source_location,
            certification_type,
            relation_to_target,
            json_dumps(list(evidence_artifact_ids)),
            json_dumps(list(tags)),
            now,
            now,
        ),
    )


def _compact_artifact_metadata(artifact_type: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    if artifact_type == "verification_report":
        return _compact_verification_metadata(metadata)
    if artifact_type == "integration_report":
        compact = dict(metadata)
        compact["missing"] = _compact_list(compact.get("missing", []), item_chars=260, max_items=8)
        compact["resolved_debt_ids"] = _compact_list(compact.get("resolved_debt_ids", []), item_chars=120, max_items=20)
        alignment = root_alignment_from_metadata(compact)
        if alignment.get("relation_to_root") != "unknown":
            compact["root_alignment"] = {
                "relation_to_root": alignment.get("relation_to_root", "unknown"),
                "target_statement": _compact_text(alignment.get("target_statement", ""), 900),
                "proved_statement": _compact_text(alignment.get("proved_statement", ""), 900),
                "implication_verified": bool(alignment.get("implication_verified")),
                "hidden_assumptions": bool(alignment.get("hidden_assumptions")),
                "extra_assumptions": _compact_list(alignment.get("extra_assumptions", []), item_chars=240, max_items=8),
                "notes": _compact_text(alignment.get("notes", ""), 600),
            }
        if "notes" in compact:
            compact["notes"] = _compact_text(compact["notes"], 600)
        return compact
    if artifact_type in {"final_proof", "final_paper"}:
        compact = dict(metadata)
        compact["source_artifact_ids"] = _compact_list(compact.get("source_artifact_ids", []), item_chars=120, max_items=24)
        return compact
    return metadata


def _should_dedupe_artifact(artifact_type: str, metadata: Dict[str, Any]) -> bool:
    if artifact_type != "verification_report":
        return True
    report = metadata.get("verification_report", {})
    if not isinstance(report, dict):
        report = {}
    return bool(
        metadata.get("proof_hash")
        or metadata.get("checked_item_hash")
        or report.get("checked_items")
        or report.get("proof_hash")
    )


def _compact_verification_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    compact = dict(metadata)
    report = compact.get("verification_report", {})
    if not isinstance(report, dict):
        report = {}
    compact_report = {
        "summary": _compact_text(report.get("summary", compact.get("summary", "")), 900),
        "checked_items": _compact_list(report.get("checked_items", []), item_chars=160, max_items=12),
        "critical_errors": _compact_list(report.get("critical_errors", []), item_chars=500, max_items=8),
        "gaps": _compact_list(report.get("gaps", []), item_chars=500, max_items=8),
    }
    notes = report.get("notes")
    if notes:
        compact_report["notes"] = _compact_text(notes, 700)
    blocking_gap = compact.get("blocking_gap") or report.get("blocking_gap")
    if not blocking_gap:
        blocking_gap = _first_nonempty(compact_report["critical_errors"]) or _first_nonempty(compact_report["gaps"])
    if blocking_gap:
        compact_report["blocking_gap"] = _compact_text(blocking_gap, 500)
    repair_hints = compact.get("repair_hints") or report.get("repair_hints") or report.get("repair_hint")
    if repair_hints:
        compact["repair_hints"] = _compact_text(repair_hints, 700)
    compact["verification_report"] = compact_report
    if "full_report" in compact:
        compact.pop("full_report")
        compact["full_report_omitted"] = True
    compact["metadata_compacted"] = True
    return compact


def _compact_list(value: Any, *, item_chars: int, max_items: int) -> List[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        value = [value]
    items = [_compact_text(item, item_chars) for item in value[:max_items]]
    omitted = len(value) - len(items)
    if omitted > 0:
        items.append(f"[{omitted} additional item(s) omitted]")
    return items


def _string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, list):
        raw_values = value
    elif isinstance(value, tuple):
        raw_values = list(value)
    else:
        raw_values = []
    return [str(item).strip() for item in raw_values if str(item).strip()]


def _compact_text(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 24)].rstrip() + " ... [truncated]"


def _first_nonempty(values: Any) -> str:
    if isinstance(values, list):
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
    return ""


def _write_artifact_content(store: ProofStateStore, artifact_id: str, artifact_type: str, content: str) -> str:
    markdown_types = {
        "final_proof",
        "proof_blueprint",
        "proof_dossier",
        "research_notebook",
        "research_diagnostic",
        "writer_report",
        "verification_report",
        "integration_report",
        "referee_report",
        "literature_search_request",
        "decomposition_plan",
        "failed_decomposition_plan",
        "key_failure_analysis",
        "source_adaptation_notes",
        "source_synthesis_report",
        "cas_experiment_report",
        "definition_audit_report",
        "route_triage_report",
        "advisor_report",
        "writing_review",
        *STRATEGIC_MARKDOWN_ARTIFACT_TYPES,
    }
    suffix = ARTIFACT_CONTENT_EXTENSIONS.get(
        artifact_type, ".md" if artifact_type in markdown_types else ".txt"
    )
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", artifact_id).strip("._") or "artifact"
    artifact_dir = store.state_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{safe_id}{suffix}"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _validated_artifact_path(store: ProofStateStore, raw_path: Any) -> str:
    if raw_path in (None, ""):
        return ""
    text = str(raw_path).strip()
    if not text:
        return ""
    artifact_root = (store.state_dir / "artifacts").resolve()
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = store.state_dir / candidate
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(artifact_root)
    except (OSError, ValueError):
        raise PatchRejected([f"artifact path must resolve under proof-state artifacts directory: {artifact_root}"])
    if not resolved.is_file():
        raise PatchRejected([f"artifact path does not exist under proof-state artifacts directory: {resolved}"])
    return str(resolved)


def _guard_artifact_actor(actor: str, artifact_type: str, artifact_id: str) -> None:
    if actor == "strict_informal_verifier" and artifact_type not in STRICT_VERIFIER_ARTIFACT_TYPES:
        raise PatchRejected([
            f"strict_informal_verifier cannot attach {artifact_type} artifact {artifact_id}; "
            "strict verification may only attach verification_report artifacts"
        ])
    if actor == WRITING_CRITIC_ROLE and artifact_type not in WRITING_CRITIC_ARTIFACT_TYPES:
        raise PatchRejected([
            f"writing_critic cannot attach {artifact_type} artifact {artifact_id}; "
            "writing review may only attach writing_review artifacts"
        ])
    allowed = ARTIFACT_PRODUCER_ROLES.get(artifact_type)
    if allowed and actor not in allowed:
        expected = ", ".join(sorted(allowed))
        raise PatchRejected([f"{actor} cannot attach {artifact_type} artifact {artifact_id}; expected {expected}"])


def _has_artifact_type(
    conn: sqlite3.Connection,
    evidence_ids: Sequence[str],
    artifact_type: str,
    *,
    producer_role: Optional[str] = None,
) -> bool:
    for aid in evidence_ids:
        row = conn.execute("SELECT artifact_type, producer_role FROM artifacts WHERE artifact_id = ?", (aid,)).fetchone()
        if not row or row["artifact_type"] != artifact_type:
            continue
        if producer_role is not None and row["producer_role"] != producer_role:
            continue
        return True
    return False


ZERO_GAP_VERIFICATION_VERDICTS = {
    "correct",
    "correct_no_gaps",
    "correct_refutation",
    "informally_verified",
    "pass",
    "verified",
}


def _has_correct_verification(conn: sqlite3.Connection, evidence_ids: Sequence[str], *, producer_role: Optional[str] = None) -> bool:
    for aid in evidence_ids:
        row = conn.execute("SELECT artifact_type, producer_role, metadata_json FROM artifacts WHERE artifact_id = ?", (aid,)).fetchone()
        if not row or row["artifact_type"] != "verification_report":
            continue
        if producer_role is not None and row["producer_role"] != producer_role:
            continue
        metadata = json_loads(row["metadata_json"], {})
        report = metadata.get("verification_report", {}) if isinstance(metadata, dict) else {}
        verdict = str(metadata.get("verdict") or report.get("verdict") or "").strip().lower()
        if verdict in ZERO_GAP_VERIFICATION_VERDICTS and not report.get("critical_errors") and not report.get("gaps") and not report.get("blocking_gap"):
            return True
    return False


def _integration_report_errors(
    conn: sqlite3.Connection,
    evidence_ids: Sequence[str],
    *,
    claim_id: str,
    route: sqlite3.Row,
    producer_role: Optional[str] = None,
) -> List[str]:
    saw_report = False
    for aid in evidence_ids:
        row = conn.execute("SELECT artifact_type, producer_role, metadata_json FROM artifacts WHERE artifact_id = ?", (aid,)).fetchone()
        if not row or row["artifact_type"] != "integration_report":
            continue
        if producer_role is not None and row["producer_role"] != producer_role:
            continue
        saw_report = True
        metadata = json_loads(row["metadata_json"], {})
        if not (metadata.get("integrates") is True or metadata.get("outcome") == "integrates"):
            continue
        if claim_id != "root":
            return []
        alignment = root_alignment_from_metadata(metadata)
        relation = alignment["relation_to_root"]
        if relation not in SOLVED_RELATIONS:
            return [f"root integration requires exact, equivalent, or stronger root_alignment; got {relation}"]
        if not alignment["implication_verified"]:
            return ["root integration requires root_alignment.implication_verified=true"]
        if alignment["hidden_assumptions"] or alignment["extra_assumptions"]:
            return ["root integration cannot add hidden or extra assumptions; report partial/conditional progress instead"]
        target_statement = alignment.get("target_statement", "")
        if target_statement:
            root_row = conn.execute("SELECT root_statement FROM problem_state").fetchone()
            if root_row and not _root_alignment_target_matches(target_statement, root_row["root_statement"]):
                return ["root_alignment.target_statement does not match immutable root statement"]
        if json_loads(route["assumptions_json"]) or json_loads(route["conditions_json"]):
            return ["root integration route has extra assumptions or conditions; prove they are part of the root statement or keep the result partial"]
        return []
    if saw_report:
        return ["integration_report evidence did not certify integrates=true"]
    return ["integration requires an integration_verifier integration_report artifact with integrates=true"]


def _root_alignment_target_matches(target_statement: str, root_statement: str) -> bool:
    target_norm = normalize_text(target_statement)
    root_norm = normalize_text(root_statement)
    if not target_norm:
        return False
    first_paragraph = normalize_text(root_statement.strip().split("\n\n", 1)[0])
    candidates = {root_norm}
    if first_paragraph:
        candidates.add(first_paragraph)
    # Notebook-style problem files often start with an H1 title, making the
    # first-paragraph candidate just the title line; accept the '## Problem'
    # section body and its question paragraph verbatim as well.
    problem_section = _markdown_sections(root_statement).get("problem", "")
    if problem_section.strip():
        candidates.add(normalize_text(problem_section))
        for paragraph in problem_section.split("\n\n"):
            if "?" in paragraph and normalize_text(paragraph):
                candidates.add(normalize_text(paragraph))
    for marker in (
        " definitions ",
        " this experiment ",
        " online lookup ",
        " do not use online search ",
        " user override ",
        " fresh run instruction ",
    ):
        if marker in root_norm:
            candidates.add(root_norm.split(marker, 1)[0].strip())
    expanded = set(candidates)
    for candidate in list(candidates):
        for prefix in ("prove that ", "show that ", "prove "):
            if candidate.startswith(prefix):
                expanded.add(candidate[len(prefix) :].strip())
    if target_norm in expanded:
        return True
    for candidate in expanded:
        if candidate and (
            target_norm.startswith(f"{candidate} ")
            or target_norm.startswith(f"{candidate},")
            or target_norm.startswith(f"{candidate};")
        ):
            return True
    return False


def _claim_evidence(conn: sqlite3.Connection, claim_id: str) -> List[str]:
    row = conn.execute("SELECT evidence_artifact_ids_json FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    return list(json_loads(row["evidence_artifact_ids_json"])) if row else []


def _route_evidence(conn: sqlite3.Connection, route_id: str) -> List[str]:
    row = conn.execute("SELECT evidence_artifact_ids_json FROM routes WHERE route_id = ?", (route_id,)).fetchone()
    return list(json_loads(row["evidence_artifact_ids_json"])) if row else []


def _inference_evidence(conn: sqlite3.Connection, inference_id: str) -> List[str]:
    row = conn.execute("SELECT evidence_artifact_ids_json FROM inferences WHERE inference_id = ?", (inference_id,)).fetchone()
    return list(json_loads(row["evidence_artifact_ids_json"])) if row else []


def _check_owner_exists(
    conn: sqlite3.Connection,
    owner_type: str,
    owner_id: str,
    *,
    pending_owners: Mapping[str, set[str]] | None = None,
) -> None:
    table = {"claim": "claims", "route": "routes", "inference": "inferences", "artifact": "artifacts"}.get(owner_type)
    key = {"claim": "claim_id", "route": "route_id", "inference": "inference_id", "artifact": "artifact_id"}.get(owner_type)
    if not table or not key:
        raise PatchRejected([f"invalid owner_type: {owner_type}"])
    if owner_id in (pending_owners or {}).get(owner_type, set()):
        return
    if not conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (owner_id,)).fetchone():
        raise PatchRejected([f"dangling {owner_type} owner: {owner_id}"])


def _required(mapping: Dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PatchRejected([f"{key} is required"])
    return value.strip()
