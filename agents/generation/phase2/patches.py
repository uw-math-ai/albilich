from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .action_contract import (
    EXECUTABLE_RUN_MODES,
    scheduler_actor_role_for_action,
    scheduler_action_contract_errors,
    scheduler_action_contract_trace_errors,
    scheduler_budget_class_for_action,
    scheduler_dispatch_action_errors,
)
from .artifacts import artifact_hash, artifact_summary
from .authority import (
    PatchAuthority,
    authority_contract_errors,
    operator_authority,
    system_authority,
)
from .audit_chain import GENESIS_HASH, patch_entry_hash
from .assurance import claim_assurance_errors
from .decision_policy import (
    action_sha256,
    candidate_rows_sha256,
    decision_deferral_state_after_trace,
    decision_trace_is_parallel_companion,
    decision_trace_errors,
)
from .dispatch_execution import execution_contract_errors
from .parallel_admission import (
    parallel_candidate_deferral_counts_from_state,
    parallel_outcome_is_fairness_eligible,
    parallel_v3_candidate_alias,
)
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
    SCHEMA_VERSION,
    VALIDATION_STATUSES,
    NON_VERIFYING_ROLES,
    VERIFYING_ROLES,
    PatchOutcome,
    fingerprint_text,
    json_dumps,
    json_loads,
    normalize_text,
    sha256_text,
    statement_is_interrogative_problem,
    utc_now,
)
from .memory_policy import artifact_is_raw_log
from .budget import (
    parse_token_usage,
    run_may_use_verification_reserve,
    run_spend_from_operation,
)
from .bounded_io import read_bounded_text, stable_file_sha256_size
from .cas_reproduction import reproduce_computation
from .formal_reproduction import check_formal_artifact
from .certificates import (
    artifact_has_current_binding,
    bind_new_certificates,
    entity_subject_digest,
    invalidate_dependents,
    invalidate_stale_refuted_obligations,
)
from .receipt import compile_latex_artifact, format_partial_receipt_appendix, receipt_appendix_present, write_latex_pdf_sidecars
from .research_intelligence import validate_state_independent_artifact_metadata
from .research_strategy import STRATEGIC_MARKDOWN_ARTIFACT_TYPES, strategic_artifact_errors
from .research_policy import normalize_retrieval_relation, theorem_matching_confidence
from .randomized_assignment import (
    WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS,
    randomized_assignment_design_sha256,
    randomized_assignment_errors,
    randomized_assignment_metadata,
)
from .result_status import SOLVED_RELATIONS, root_alignment_from_metadata
from .store import ProofStateStore
from .scheduler_provenance import (
    append_scheduler_provenance_entry,
    scheduler_provenance_summary,
)
from .verification import (
    POSITIVE_VERIFICATION_VERDICTS,
    clean_verification_metadata,
    evidence_matches_target,
    evidence_targets,
    verification_blockers,
)
from .writing.latex_template import normalize_paper_template
from .writing.linter import run_paper_lint, run_residue_scan
from .writing.paper_contract import SUPPORTED_WRITING_REVIEW_LENSES
from .writing.publication import (
    REFEREE_VERDICTS,
    mark_route_error_escalated,
    prepare_final_paper_metadata,
    prepare_referee_report_metadata,
    record_referee_report,
)
from .writing.revision import (
    REVISION_DOCUMENT_ARTIFACT_TYPE,
    revision_document_metadata,
)


class PatchRejected(Exception):
    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class _ArtifactFileJournal:
    """Undo filesystem mutations when the enclosing SQLite patch rolls back."""

    def __init__(self) -> None:
        self._before: Dict[Path, Optional[Path]] = {}
        self._backup_dir: Optional[tempfile.TemporaryDirectory[str]] = None

    def capture(self, path: Path) -> None:
        path = path.parent.resolve() / path.name
        if path not in self._before:
            if path.is_symlink():
                raise PatchRejected(
                    [f"artifact destination must not be a symbolic link: {path}"]
                )
            if path.is_file():
                if self._backup_dir is None:
                    self._backup_dir = tempfile.TemporaryDirectory(
                        prefix="albilich-artifact-rollback-"
                    )
                backup = Path(self._backup_dir.name) / f"{len(self._before):08d}.bak"
                shutil.copy2(path, backup)
                self._before[path] = backup
            elif path.exists():
                raise PatchRejected(
                    [f"artifact destination is not a regular file: {path}"]
                )
            else:
                self._before[path] = None

    def write_text(self, path: Path, content: str) -> None:
        self.write_bytes(path, content.encode("utf-8"))

    def write_bytes(self, path: Path, content: bytes) -> None:
        path = path.parent.resolve() / path.name
        self.capture(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_temporary_path = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".write", dir=path.parent
        )
        temporary_path = Path(raw_temporary_path)
        try:
            offset = 0
            while offset < len(content):
                offset += os.write(descriptor, content[offset:])
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary_path, path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary_path.unlink(missing_ok=True)

    def copy_stable_file(
        self,
        destination: Path,
        source: Path,
        *,
        max_bytes: int,
        expected_sha256: str = "",
        expected_size: Optional[int] = None,
    ) -> int:
        """Copy one stable regular file without following its final symlink."""

        destination = destination.parent.resolve() / destination.name
        self.capture(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            source_descriptor = os.open(source, flags)
        except OSError as exc:
            raise PatchRejected([f"could not open artifact source {source}: {exc}"]) from exc
        temporary_descriptor = -1
        temporary_path: Optional[Path] = None
        try:
            before = os.fstat(source_descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise PatchRejected([f"artifact source is not a regular file: {source}"])
            if before.st_size > max_bytes:
                raise PatchRejected(
                    [
                        f"artifact source is {before.st_size} bytes; copied artifacts "
                        f"are limited to {max_bytes} bytes"
                    ]
                )
            if expected_size is not None and before.st_size != expected_size:
                raise PatchRejected(
                    [f"artifact source size changed since result persistence: {source}"]
                )
            temporary_descriptor, raw_temporary_path = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".copy",
                dir=destination.parent,
            )
            temporary_path = Path(raw_temporary_path)
            copied = 0
            digest = hashlib.sha256()
            while True:
                block = os.read(source_descriptor, 1024 * 1024)
                if not block:
                    break
                copied += len(block)
                if copied > max_bytes:
                    raise PatchRejected(
                        [f"artifact source grew beyond the {max_bytes}-byte copy limit"]
                    )
                digest.update(block)
                offset = 0
                while offset < len(block):
                    offset += os.write(temporary_descriptor, block[offset:])
            after = os.fstat(source_descriptor)
            if (
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or copied != after.st_size
            ):
                raise PatchRejected([f"artifact source changed while it was copied: {source}"])
            if expected_sha256 and digest.hexdigest() != expected_sha256:
                raise PatchRejected(
                    [f"artifact source content changed since result persistence: {source}"]
                )
            os.fsync(temporary_descriptor)
            os.close(temporary_descriptor)
            temporary_descriptor = -1
            os.replace(temporary_path, destination)
            temporary_path = None
            return copied
        finally:
            os.close(source_descriptor)
            if temporary_descriptor >= 0:
                os.close(temporary_descriptor)
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def rollback(self) -> None:
        for path, backup in reversed(list(self._before.items())):
            if backup is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                descriptor, raw_restore_path = tempfile.mkstemp(
                    prefix=f".{path.name}.", suffix=".restore", dir=path.parent
                )
                os.close(descriptor)
                restore_path = Path(raw_restore_path)
                try:
                    shutil.copy2(backup, restore_path)
                    os.replace(restore_path, path)
                finally:
                    restore_path.unlink(missing_ok=True)
        self._before.clear()
        if self._backup_dir is not None:
            self._backup_dir.cleanup()
            self._backup_dir = None

    def commit(self) -> None:
        self._before.clear()
        if self._backup_dir is not None:
            self._backup_dir.cleanup()
            self._backup_dir = None


ARTIFACT_PRODUCER_ROLES = {
    "audit_subject": {"human_operator"},
    "branch_workbench": {"scheduler"},
    "verification_report": {"strict_informal_verifier"},
    "formal_backend_result": {"formal_backend"},
    "confirmed_counterexample": {"counterexample_validator"},
    "integration_report": {"integration_verifier"},
    "referee_report": {"writer", "referee"},
    "writing_review": {"writing_critic"},
    "final_paper": {"writer"},
    "human_readable_mathematical_text": {"writer"},
    # The immutable source manuscript is submitted by the human operator;
    # later revision_document artifacts are produced by the writer and pass
    # the lineage checks in _prepare_revision_document_metadata.
    REVISION_DOCUMENT_ARTIFACT_TYPE: {"human_operator", "writer"},
    "advisor_synthesis": {"phd_advisor", "advisor"},
    "invention_authorization": {"phd_advisor", "advisor"},
    "approach_portfolio": {"researcher"},
    "bridge_lemma_search": {"researcher"},
    "conjecture_portfolio": {"researcher", "adversarial_reviewer", "villain"},
    "definition_candidate": {"researcher"},
    "deep_session_report": {"researcher"},
    "proof_compression": {"researcher", "phd_advisor", "advisor"},
    "reference_solution": {"human_operator"},
    "run_interruption_event": {"human_operator"},
}
STRICT_VERIFIER_ARTIFACT_TYPES = {"verification_report"}
WRITING_CRITIC_ROLE = "writing_critic"
WRITING_CRITIC_ARTIFACT_TYPES = {"writing_review"}
REFEREE_ROLE = "referee"
REFEREE_ARTIFACT_TYPES = {"referee_report"}
WRITING_REVIEW_VERDICTS = {"pass", "fail"}
# "editor" is the single lens the scheduler dispatches; the legacy three-lens
# names stay accepted so old review data still parses.
WRITING_CRITIC_LENSES = set(SUPPORTED_WRITING_REVIEW_LENSES)
# Writer artifact types scanned for generation residue (rule L1-CITE-03) at
# patch time; residue in the shipped exposition is always rejected.
WRITER_RESIDUE_SCANNED_ARTIFACT_TYPES = {
    "final_proof",
    "partial_proof_report",
    "final_paper",
    "human_readable_mathematical_text",
    REVISION_DOCUMENT_ARTIFACT_TYPE,
}
# Artifact types whose file extension is not the markdown/txt default; the
# final_paper's content IS complete LaTeX source, so it ships as a .tex file
# that the attach-time sidecar compiles directly (no markdown->LaTeX pass).
ARTIFACT_CONTENT_EXTENSIONS = {
    "branch_workbench": ".json",
    "final_paper": ".tex",
    "human_readable_mathematical_text": ".tex",
}
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
MAX_INLINE_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_COPIED_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_PATCH_OPERATIONS = 512
MAX_PATCH_NESTING_DEPTH = 40
MAX_PATCH_JSON_NODES = 100_000
MAX_PATCH_TOTAL_UTF8_BYTES = 16 * 1024 * 1024
MAX_PATCH_STRING_BYTES = 8 * 1024 * 1024
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

_STATE_JOURNAL_TABLE_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("problem_state", ("problem_id",)),
    ("claims", ("claim_id",)),
    ("routes", ("route_id",)),
    ("inferences", ("inference_id",)),
    ("inference_premises", ("inference_id", "premise_claim_id")),
    ("debts", ("debt_id",)),
    ("artifacts", ("artifact_id",)),
    ("runs", ("run_id",)),
    ("scheduler_dispatches", ("dispatch_id",)),
    ("retrieval_cards", ("card_id",)),
    ("theorem_library_entries", ("entry_id",)),
    ("publication_reviews", ("review_id",)),
    ("context_requests", ("request_id",)),
    ("claim_assurance", ("claim_id",)),
)


def _patch_resource_errors(patch: Mapping[str, Any]) -> List[str]:
    """Reject non-JSON or computationally unbounded patch structures early."""

    errors: List[str] = []
    operations = patch.get("operations")
    if isinstance(operations, list) and len(operations) > MAX_PATCH_OPERATIONS:
        errors.append(
            f"patch has {len(operations)} operations; limit is {MAX_PATCH_OPERATIONS}"
        )

    stack: list[tuple[Any, int]] = [(patch, 0)]
    nodes = 0
    utf8_bytes = 0
    while stack and not errors:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_PATCH_JSON_NODES:
            errors.append(
                f"patch JSON exceeds the {MAX_PATCH_JSON_NODES}-node structural limit"
            )
            break
        if depth > MAX_PATCH_NESTING_DEPTH:
            errors.append(
                f"patch JSON exceeds the {MAX_PATCH_NESTING_DEPTH}-level nesting limit"
            )
            break
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    errors.append("patch JSON object keys must be strings")
                    break
                key_bytes = len(key.encode("utf-8"))
                if key_bytes > MAX_PATCH_STRING_BYTES:
                    errors.append("patch JSON contains an oversized object key")
                    break
                utf8_bytes += key_bytes
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            value_bytes = len(value.encode("utf-8"))
            if value_bytes > MAX_PATCH_STRING_BYTES:
                errors.append(
                    f"patch JSON string exceeds the {MAX_PATCH_STRING_BYTES}-byte limit"
                )
                break
            utf8_bytes += value_bytes
        elif isinstance(value, float):
            if not math.isfinite(value):
                errors.append("patch JSON contains a non-finite number")
                break
        elif isinstance(value, int):
            if not isinstance(value, bool) and value.bit_length() > 1024:
                errors.append("patch JSON contains an oversized integer")
                break
        elif value is not None:
            errors.append(
                f"patch contains a non-JSON value of type {type(value).__name__}"
            )
            break
        if utf8_bytes > MAX_PATCH_TOTAL_UTF8_BYTES:
            errors.append(
                "patch JSON strings exceed the aggregate "
                f"{MAX_PATCH_TOTAL_UTF8_BYTES}-byte limit"
            )
            break
    return errors


def preflight_patch_errors(
    patch: Mapping[str, Any], actor_role: str, *, authority: PatchAuthority | None = None,
    problem_id: str | None = None,
) -> List[str]:
    """Runner-side contract checks that predict certain guard rejections.

    Only violations that are decidable from the patch alone are flagged, so the
    session that produced the patch can repair it in place instead of losing the
    whole step to a workflow rejection. Anything that needs store state stays
    with apply_patch.
    """
    resource_errors = _patch_resource_errors(patch)
    if resource_errors:
        return resource_errors
    try:
        normalized = _normalize_patch_aliases(dict(patch))
    except (TypeError, ValueError):
        return []
    normalized_resource_errors = _patch_resource_errors(normalized)
    if normalized_resource_errors:
        return normalized_resource_errors
    operations = [op for op in normalized.get("operations") or [] if isinstance(op, Mapping)]
    attached_ops = {
        str(op.get("artifact_id") or ""): op
        for op in operations
        if str(op.get("op") or "") in {"attach_artifact", "add_artifact"}
    }
    errors: List[str] = []
    if authority is not None:
        errors.extend(authority_contract_errors(normalized, authority))
    if problem_id is not None and normalized.get("problem_id") != problem_id:
        errors.append(f"patch problem_id must equal {problem_id!r}")
    from .research_strategy import STRATEGY_SCHEMA_VERSION, proof_compression_shape_errors

    for op in attached_ops.values():
        if str(op.get("artifact_type") or "") != "proof_compression":
            continue
        metadata = op.get("metadata") if isinstance(op.get("metadata"), Mapping) else {}
        if metadata.get("strategy_schema_version") != STRATEGY_SCHEMA_VERSION:
            errors.append(f"proof_compression requires strategy_schema_version={STRATEGY_SCHEMA_VERSION}")
        errors.extend(proof_compression_shape_errors(metadata))
    if actor_role == REFEREE_ROLE:
        reports = [
            op
            for op in attached_ops.values()
            if str(op.get("artifact_type") or "") == "referee_report"
        ]
        if len(reports) != 1:
            errors.append("referee patches must attach exactly one referee_report")
        allowed_ops = {"attach_artifact", "add_artifact", "add_debt", "record_run_metrics"}
        invalid = sorted(
            {
                str(op.get("op") or "")
                for op in operations
                if str(op.get("op") or "") not in allowed_ops
            }
        )
        if invalid:
            errors.append(
                "referee patches may only attach a referee report, add located writing debts, and record metrics; "
                f"invalid operations: {invalid}"
            )
        if reports:
            metadata = reports[0].get("metadata") if isinstance(reports[0].get("metadata"), Mapping) else {}
            verdict = str(metadata.get("verdict") or "").strip().lower().replace("-", "_")
            if verdict not in REFEREE_VERDICTS:
                errors.append(
                    "referee_report metadata.verdict must be accept, revise, or major_proof_route_error"
                )
            debt_ops = [op for op in operations if str(op.get("op") or "") == "add_debt"]
            if verdict == "accept" and debt_ops:
                errors.append("an [accept] referee decision may not open writing debts")
            if verdict == "revise" and not debt_ops:
                errors.append("a [revise] referee decision must open at least one located writing debt")
            if verdict == "major_proof_route_error" and debt_ops:
                errors.append(
                    "a [major-proof-route-error] decision records route evidence in the report; "
                    "the scheduler creates the research debt"
                )
            reviewed_paper_id = str(
                metadata.get("reviewed_paper_artifact_id")
                or metadata.get("artifact_reviewed")
                or ""
            )
            for debt_op in debt_ops:
                if (
                    str(debt_op.get("owner_type") or "") != "artifact"
                    or str(debt_op.get("owner_id") or "") != reviewed_paper_id
                    or str(debt_op.get("debt_type") or "") != "writing"
                ):
                    errors.append(
                        "referee findings must be writing debts owned by the reviewed final_paper artifact"
                    )
    if actor_role == "writer":
        revised_papers = []
        for op in attached_ops.values():
            if str(op.get("artifact_type") or "") != "final_paper":
                continue
            metadata = op.get("metadata") if isinstance(op.get("metadata"), Mapping) else {}
            if str(metadata.get("revision_of_artifact_id") or ""):
                revised_papers.append(op)
        resolves_writing_debt = any(
            str(op.get("op") or "") == "update_debt"
            and str(op.get("status") or "") == "resolved"
            and bool(op.get("resolution_evidence_artifact_ids"))
            for op in operations
        )
        if revised_papers and not resolves_writing_debt:
            errors.append(
                "a revised final_paper must resolve the named writing debts with update_debt operations "
                "and resolution_evidence_artifact_ids naming the revised paper"
            )
    for op in attached_ops.values():
        metadata = op.get("metadata") if isinstance(op.get("metadata"), Mapping) else {}
        errors.extend(
            validate_state_independent_artifact_metadata(
                artifact_type=str(op.get("artifact_type") or ""),
                metadata=metadata,
                content=op.get("content"),
            )
        )
        if str(op.get("artifact_type") or "") not in {"proof_dossier", "proof_blueprint"}:
            continue
        if (
            actor_role == "researcher"
            and str(metadata.get("mathematical_delta_kind") or "") == "proved_lemma"
            and metadata.get("changed_proof_state") is True
        ):
            artifact_id = str(op.get("artifact_id") or "")
            linked_inference = any(
                str(candidate.get("op") or "") in {"add_inference", "update_inference"}
                and artifact_id in {str(item) for item in candidate.get("evidence_artifact_ids") or []}
                for candidate in operations
            )
            if not linked_inference:
                errors.append(
                    f"proved_lemma artifact {artifact_id} is not materialized in the proof graph: add or update an "
                    "inference whose evidence_artifact_ids cites it (and add the exact lemma claim and sufficient "
                    "route when they do not already exist); otherwise use a non-proof delta kind such as "
                    "narrowed_obligation"
                )
        try:
            owner_version = int(metadata.get("canonical_route_owner_version") or 0)
        except (TypeError, ValueError):
            errors.append("canonical_route_owner_version must be an integer")
            continue
        if owner_version != 1:
            continue
        for field in (
            "canonical_route_id",
            "root_implication_update",
            "root_cut_signature_before",
            "root_cut_signature_after",
            "creates_parallel_dossier",
        ):
            if field not in metadata or metadata.get(field) in (None, ""):
                errors.append(f"canonical route dossier requires {field}")
        if metadata.get("creates_parallel_dossier") is not False:
            errors.append("canonical route dossier requires creates_parallel_dossier=false")
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
                if verdict not in POSITIVE_VERIFICATION_VERDICTS:
                    dirty_reason = (
                        f"verification_report verdict '{verdict or 'missing'}' does not certify; use one of "
                        f"{sorted(POSITIVE_VERIFICATION_VERDICTS)} only when errors and gaps are genuinely empty"
                    )
                    continue
                if verification_blockers(metadata):
                    dirty_reason = (
                        "verification_report still lists critical_errors/gaps/blocking_gap; do not propose "
                        "informally_verified — attach the report and add precise debts instead"
                    )
                    continue
                if not evidence_matches_target(
                    metadata,
                    target_type=str(op.get("target_type") or "claim"),
                    target_id=target_id,
                ):
                    dirty_reason = (
                        f"verification_report is not bound to {op.get('target_type') or 'claim'} {target_id}"
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
    # Independent integrations produced by one parallel wave touch distinct
    # claim/route/debt rows and rerun every integration guard after rebasing.
    ("integration_verifier", "integrated"),
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
        if (
            target_type == "claim"
            and str(op.get("status_type") or "validation") == "lifecycle"
            and str(op.get("new_status") or "") == "integrated"
        ):
            # Integration also mutates the selected route and every explicitly
            # resolved debt.  Include those implicit writes in stale-patch
            # conflict detection so only truly row-disjoint integrations rebase.
            if not _add("route", op.get("route_id")):
                return ids, True
            for debt_id in op.get("resolved_debt_ids") or []:
                if not _add("debt", debt_id):
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


def apply_patch_with_stale_retry(
    store: ProofStateStore,
    patch: Dict[str, Any],
    *,
    authority: PatchAuthority,
    max_retries: int = 3,
) -> PatchOutcome:
    """apply_patch, but auto-rebase provably safe patches past staleness.

    Parallel companions and long researcher sessions routinely go stale because
    advisor/metrics patches land mid-flight; when the stale patch is additive
    and row-disjoint or commutative with everything that landed in between,
    retry it instead of discarding the whole session's work.
    """
    original_base_revision = int(patch.get("base_revision") or 0)
    outcome = apply_patch(
        store,
        patch,
        authority=authority,
        original_base_revision=original_base_revision,
    )
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
            except (OSError, sqlite3.Error, TypeError, ValueError):
                # Diagnostic event failure cannot change the already-declined
                # mathematical mutation; the returned rejection remains authoritative.
                pass
            break
        patch = dict(patch)
        patch["base_revision"] = assessment["current_revision"]
        outcome = apply_patch(
            store,
            patch,
            authority=authority,
            original_base_revision=original_base_revision,
        )
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
            except (OSError, sqlite3.Error, TypeError, ValueError):
                # Diagnostic event failure cannot reverse an accepted, committed patch.
                pass
    return outcome


def _record_patch_rejection(store: ProofStateStore, patch: Mapping[str, Any], patch_id: str, errors: List[str], *, kind: str) -> None:
    """Persist a patch_rejected event so failed sessions are diagnosable post-hoc."""
    try:
        payload = {
            "patch_id": str(patch_id)[:512],
            "actor_role": str(patch.get("actor_role") or ""),
            "target_id": str(patch.get("target_id") or ""),
            "base_revision": patch.get("base_revision"),
            "kind": kind,
            "op_kinds": [
                str(op.get("op") or "")
                for op in (
                    patch.get("operations")
                    if isinstance(patch.get("operations"), list)
                    else []
                )
                if isinstance(op, Mapping)
            ][:16],
            "errors": [str(error)[:400] for error in (errors or [])][:8],
        }
        with store.connect() as conn:
            store.write_event(conn, store.get_revision(conn), "patch_rejected", payload)
            conn.commit()
    except (OSError, sqlite3.Error, TypeError, ValueError):
        # intentional-boundary: rejection telemetry is best-effort and has no proof authority
        pass


def _state_journal_projection(conn: sqlite3.Connection) -> Dict[str, list[Dict[str, Any]]]:
    """Canonical projection of mathematical state and resource constraints.

    Scheduler dispatch and run telemetry have their own authenticated,
    append-only history. Keeping those ever-growing control-plane rows in the
    proof-state digest made every later mathematical transition linear in the
    lifetime execution count. Empty compatibility components preserve the
    revision-zero hash used by stores created before migration v15.
    """

    projection: Dict[str, list[Dict[str, Any]]] = {}
    for table, key_columns in _STATE_JOURNAL_TABLE_KEYS:
        if table == "runs":
            projection[table] = []
            continue
        if table == "scheduler_dispatches":
            continue
        order = ", ".join(key_columns)
        columns = "*"
        if table == "problem_state":
            # Run-control/UI policy fields change outside proof revisions and
            # are intentionally not part of mathematical replay identity.
            columns = (
                "problem_id, schema_version, current_revision, root_statement, status, "
                "total_token_budget, remaining_token_budget, reserved_verification_budget, "
                "max_reduction_depth"
            )
        rows = [
            dict(row)
            for row in conn.execute(f"SELECT {columns} FROM {table} ORDER BY {order}").fetchall()
        ]
        # Preserve every pre-v11 proof-state hash when the newly introduced
        # table is empty.  Once a dispatch exists it is a native replay row.
        if table == "scheduler_dispatches" and not rows:
            continue
        projection[table] = rows
    return projection


def _legacy_v14_state_journal_projection(
    conn: sqlite3.Connection,
) -> Dict[str, list[Dict[str, Any]]]:
    """Reproduce the proof projection used through store migration v14."""

    projection = _state_journal_projection(conn)
    projection["runs"] = [
        dict(row)
        for row in conn.execute(
            "SELECT run_id, actor_role, mode, target_id, route_id, state_revision, "
            "context_revision, session_id, model_profile, model, reasoning_effort, "
            "search_setting, search_intent, strategy_family, researcher_work_mode, "
            "work_mode_source, failure_kind, sandbox_setting, budget_requested, "
            "input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens, "
            "total_tokens, wall_time_seconds, peak_memory_mb, status, prompt_context_hash, "
            "output_artifact_ids_json, error_artifact_id, created_at, "
            "budget_overrun_tokens FROM runs ORDER BY run_id"
        ).fetchall()
    ]
    dispatches = [
        dict(row)
        for row in conn.execute(
            "SELECT dispatch_id, dispatch_group_id, dispatch_position, is_companion, "
            "actor_role, mode, target_id, route_id, decision_state_revision, "
            "proof_state_hash, prior_run_provenance_hash, selection_design, "
            "candidate_set_hash, selection_policy_version, decision_trace_json, "
            "dispatched_action_hash, committed_at FROM scheduler_dispatches "
            "ORDER BY dispatch_id"
        ).fetchall()
    ]
    if dispatches:
        projection["scheduler_dispatches"] = dispatches
    return projection


def _state_projection_hash(projection: Mapping[str, Any]) -> str:
    return sha256_text(json_dumps(projection))


def _run_provenance_hash(
    conn: sqlite3.Connection,
    *,
    include_dispatch_execution: bool = True,
    include_result_run_id: bool = True,
    use_incremental: bool = True,
) -> str:
    """Hash run-selection fields excluded from legacy row-replay identity.

    Migration v4 added these columns after native replay hashes already
    existed.  Rewriting that history would invalidate genuine checkpoints, so
    v9 binds the live values with a companion seal instead.
    """

    incremental_available = (
        use_incremental
        and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'scheduler_provenance_entries'"
        ).fetchone()
        is not None
        and conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = 15"
        ).fetchone()
        is not None
    )
    candidate_deferrals = [
        dict(row)
        for row in conn.execute(
            "SELECT candidate_id, consecutive_capacity_deferrals, last_wave_id, "
            "policy_version, updated_run_id, updated_dispatch_id "
            "FROM scheduler_candidate_deferrals ORDER BY candidate_id"
        ).fetchall()
    ]
    fairness_meta = [
        dict(row)
        for row in conn.execute(
            "SELECT singleton, last_wave_id, last_state_revision, policy_version, "
            "updated_run_id, updated_dispatch_id FROM scheduler_fairness_meta "
            "ORDER BY singleton"
        ).fetchall()
    ]
    decision_deferrals = [
        dict(row)
        for row in conn.execute(
            "SELECT candidate_id, consecutive_deferrals, last_decision_id, "
            "policy_version, updated_run_id, updated_dispatch_id "
            "FROM scheduler_decision_deferrals ORDER BY candidate_id"
        ).fetchall()
    ]
    decision_fairness_meta = [
        dict(row)
        for row in conn.execute(
            "SELECT singleton, last_decision_id, last_state_revision, "
            "policy_version, updated_run_id, updated_dispatch_id "
            "FROM scheduler_decision_fairness_meta ORDER BY singleton"
        ).fetchall()
    ]
    projection = {
        "scheduler_candidate_deferrals": candidate_deferrals,
        "scheduler_fairness_meta": fairness_meta,
        "scheduler_decision_deferrals": decision_deferrals,
        "scheduler_decision_fairness_meta": decision_fairness_meta,
    }
    if incremental_available:
        projection["scheduler_provenance"] = scheduler_provenance_summary(conn)
    else:
        projection["runs"] = [
            dict(row)
            for row in conn.execute(
                "SELECT run_id, selection_design, assignment_probability, "
                "exploration_stratum, candidate_set_hash, selection_policy_version, "
                "decision_trace_json, decision_state_revision, scheduler_dispatch_id, "
                "dispatched_action_hash FROM runs ORDER BY run_id"
            ).fetchall()
        ]
        projection["scheduler_dispatches"] = [
            dict(row)
            for row in conn.execute(
                # The action digest commits to the canonical recovery body.
                "SELECT dispatch_id, dispatch_group_id, dispatch_position, is_companion, "
                "actor_role, mode, target_id, route_id, decision_state_revision, "
                "proof_state_hash, prior_run_provenance_hash, selection_design, "
                "candidate_set_hash, selection_policy_version, decision_trace_json, "
                "dispatched_action_hash, execution_contract_json, committed_at "
                "FROM scheduler_dispatches ORDER BY dispatch_id"
            ).fetchall()
        ]
    if include_dispatch_execution and not incremental_available:
        # The potentially large result body is committed by result_hash and
        # checked before recovery/full audit.  Keeping only that digest in the
        # current-state seal avoids making every later proof patch rehash a
        # multi-megabyte model response.
        projection["scheduler_dispatch_attempts"] = [
            dict(row)
            for row in conn.execute(
                "SELECT attempt_id, dispatch_id, attempt_number, "
                "session_plan_hash, executor_identity, claimed_at, event_id "
                "FROM scheduler_dispatch_attempts ORDER BY attempt_id"
            ).fetchall()
        ]
        result_columns = (
            "result_id, dispatch_id, attempt_id, run_id, result_hash, "
            if include_result_run_id
            else "result_id, dispatch_id, attempt_id, result_hash, "
        )
        projection["scheduler_dispatch_results"] = [
            dict(row)
            for row in conn.execute(
                "SELECT "
                + result_columns
                + "completed_at, event_id FROM scheduler_dispatch_results "
                "ORDER BY result_id"
            ).fetchall()
        ]
    return sha256_text(json_dumps(projection))


def _legacy_v12_run_provenance_hash(conn: sqlite3.Connection) -> str:
    """Reproduce the v12 seal before durable attempt/result records existed."""

    return _run_provenance_hash(
        conn,
        include_dispatch_execution=False,
        use_incremental=False,
    )


def _legacy_v13_run_provenance_hash(conn: sqlite3.Connection) -> str:
    """Reproduce the v13 seal before result run IDs were reserved."""

    return _run_provenance_hash(
        conn,
        include_dispatch_execution=True,
        include_result_run_id=False,
        use_incremental=False,
    )


def _legacy_v14_run_provenance_hash(conn: sqlite3.Connection) -> str:
    """Reproduce the exact v14 full-history seal for migration checks."""

    return _run_provenance_hash(conn, use_incremental=False)


def _legacy_v9_run_provenance_hash(conn: sqlite3.Connection) -> str:
    """Reproduce the exact pre-v10 run-selection seal for migration checks."""

    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT run_id, selection_design, assignment_probability, "
            "exploration_stratum, candidate_set_hash, selection_policy_version, "
            "decision_trace_json FROM runs ORDER BY run_id"
        ).fetchall()
    ]
    return sha256_text(json_dumps(rows))


def _legacy_v10_run_provenance_hash(conn: sqlite3.Connection) -> str:
    """Reproduce the exact pre-v11 scheduler/run seal for migration checks."""

    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT run_id, selection_design, assignment_probability, "
            "exploration_stratum, candidate_set_hash, selection_policy_version, "
            "decision_trace_json FROM runs ORDER BY run_id"
        ).fetchall()
    ]
    candidate_deferrals = [
        dict(row)
        for row in conn.execute(
            "SELECT candidate_id, consecutive_capacity_deferrals, last_wave_id, "
            "policy_version, updated_run_id "
            "FROM scheduler_candidate_deferrals ORDER BY candidate_id"
        ).fetchall()
    ]
    fairness_meta = [
        dict(row)
        for row in conn.execute(
            "SELECT singleton, last_wave_id, last_state_revision, policy_version, "
            "updated_run_id FROM scheduler_fairness_meta ORDER BY singleton"
        ).fetchall()
    ]
    decision_deferrals = [
        dict(row)
        for row in conn.execute(
            "SELECT candidate_id, consecutive_deferrals, last_decision_id, "
            "policy_version, updated_run_id "
            "FROM scheduler_decision_deferrals ORDER BY candidate_id"
        ).fetchall()
    ]
    decision_fairness_meta = [
        dict(row)
        for row in conn.execute(
            "SELECT singleton, last_decision_id, last_state_revision, "
            "policy_version, updated_run_id "
            "FROM scheduler_decision_fairness_meta ORDER BY singleton"
        ).fetchall()
    ]
    return sha256_text(
        json_dumps(
            {
                "runs": rows,
                "scheduler_candidate_deferrals": candidate_deferrals,
                "scheduler_fairness_meta": fairness_meta,
                "scheduler_decision_deferrals": decision_deferrals,
                "scheduler_decision_fairness_meta": decision_fairness_meta,
            }
        )
    )


def _legacy_v11_run_provenance_hash(conn: sqlite3.Connection) -> str:
    """Reproduce the exact pre-v12 dispatch/run seal for migration checks."""

    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT run_id, selection_design, assignment_probability, "
            "exploration_stratum, candidate_set_hash, selection_policy_version, "
            "decision_trace_json, decision_state_revision, scheduler_dispatch_id, "
            "dispatched_action_hash FROM runs ORDER BY run_id"
        ).fetchall()
    ]
    dispatches = [
        dict(row)
        for row in conn.execute(
            "SELECT dispatch_id, dispatch_group_id, dispatch_position, is_companion, "
            "actor_role, mode, target_id, route_id, decision_state_revision, "
            "proof_state_hash, prior_run_provenance_hash, selection_design, "
            "candidate_set_hash, selection_policy_version, decision_trace_json, "
            "dispatched_action_hash, committed_at "
            "FROM scheduler_dispatches ORDER BY dispatch_id"
        ).fetchall()
    ]
    candidate_deferrals = [
        dict(row)
        for row in conn.execute(
            "SELECT candidate_id, consecutive_capacity_deferrals, last_wave_id, "
            "policy_version, updated_run_id, updated_dispatch_id "
            "FROM scheduler_candidate_deferrals ORDER BY candidate_id"
        ).fetchall()
    ]
    fairness_meta = [
        dict(row)
        for row in conn.execute(
            "SELECT singleton, last_wave_id, last_state_revision, policy_version, "
            "updated_run_id, updated_dispatch_id FROM scheduler_fairness_meta "
            "ORDER BY singleton"
        ).fetchall()
    ]
    decision_deferrals = [
        dict(row)
        for row in conn.execute(
            "SELECT candidate_id, consecutive_deferrals, last_decision_id, "
            "policy_version, updated_run_id, updated_dispatch_id "
            "FROM scheduler_decision_deferrals ORDER BY candidate_id"
        ).fetchall()
    ]
    decision_fairness_meta = [
        dict(row)
        for row in conn.execute(
            "SELECT singleton, last_decision_id, last_state_revision, "
            "policy_version, updated_run_id, updated_dispatch_id "
            "FROM scheduler_decision_fairness_meta ORDER BY singleton"
        ).fetchall()
    ]
    return sha256_text(
        json_dumps(
            {
                "runs": rows,
                "scheduler_dispatches": dispatches,
                "scheduler_candidate_deferrals": candidate_deferrals,
                "scheduler_fairness_meta": fairness_meta,
                "scheduler_decision_deferrals": decision_deferrals,
                "scheduler_decision_fairness_meta": decision_fairness_meta,
            }
        )
    )


def _state_delta(
    before: Mapping[str, list[Mapping[str, Any]]],
    after: Mapping[str, list[Mapping[str, Any]]],
) -> list[Dict[str, Any]]:
    """Return row-exact changes sufficient to replay one accepted revision."""

    changes: list[Dict[str, Any]] = []
    for table, key_columns in _STATE_JOURNAL_TABLE_KEYS:
        def key_for(row: Mapping[str, Any]) -> tuple[str, ...]:
            return tuple(str(row.get(column) or "") for column in key_columns)

        before_rows = {key_for(row): dict(row) for row in before.get(table, [])}
        after_rows = {key_for(row): dict(row) for row in after.get(table, [])}
        for row_key in sorted(set(before_rows) | set(after_rows)):
            old = before_rows.get(row_key)
            new = after_rows.get(row_key)
            if old == new:
                continue
            key_card = {column: row_key[index] for index, column in enumerate(key_columns)}
            if old is None:
                changes.append({"op": "insert_row", "table": table, "key": key_card, "after": new})
            elif new is None:
                changes.append({"op": "delete_row", "table": table, "key": key_card, "before": old})
            else:
                changes.append(
                    {
                        "op": "update_row",
                        "table": table,
                        "key": key_card,
                        "before": old,
                        "after": new,
                    }
                )
    return changes


def append_applied_patch_entry(
    conn: sqlite3.Connection,
    *,
    patch_id: str,
    problem_id: str,
    base_revision: int,
    actor_role: str,
    target_id: str,
    operations: Any,
    evidence_artifact_ids: Any,
    rationale: str,
    created_at: str,
    applied_revision: int,
    authority: PatchAuthority,
    state_delta: Any,
    state_hash_before: str,
    state_hash_after: str,
) -> str:
    """Append one accepted patch with a hash over its complete audit record."""

    previous_row = conn.execute(
        "SELECT journal_entry_hash FROM patches WHERE status = 'applied' "
        "ORDER BY applied_revision DESC, patch_id DESC LIMIT 1"
    ).fetchone()
    previous = (
        str(previous_row["journal_entry_hash"] or GENESIS_HASH)
        if previous_row
        else GENESIS_HASH
    )
    operations_json = json_dumps(operations)
    evidence_json = json_dumps(evidence_artifact_ids)
    authority_json = json_dumps(authority.to_audit_dict())
    state_delta_json = json_dumps(state_delta)
    row = {
        "patch_id": patch_id,
        "schema_version": SCHEMA_VERSION,
        "problem_id": problem_id,
        "base_revision": int(base_revision),
        "actor_role": actor_role,
        "target_id": target_id,
        "operations_json": operations_json,
        "evidence_artifact_ids_json": evidence_json,
        "rationale": rationale,
        "status": "applied",
        "rejection_reason": "",
        "created_at": created_at,
        "applied_revision": int(applied_revision),
        "authority_source": authority.source,
        "authority_json": authority_json,
        "state_delta_json": state_delta_json,
        "state_hash_before": state_hash_before,
        "state_hash_after": state_hash_after,
        "previous_entry_hash": previous,
    }
    digest = patch_entry_hash(row)
    conn.execute(
        """
        INSERT INTO patches(
            patch_id, schema_version, problem_id, base_revision, actor_role,
            target_id, operations_json, evidence_artifact_ids_json, rationale,
            status, rejection_reason, created_at, applied_revision,
            authority_source, authority_json, state_delta_json,
            state_hash_before, state_hash_after, previous_entry_hash,
            journal_entry_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'applied', '', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            patch_id,
            SCHEMA_VERSION,
            problem_id,
            int(base_revision),
            actor_role,
            target_id,
            operations_json,
            evidence_json,
            rationale,
            created_at,
            int(applied_revision),
            authority.source,
            authority_json,
            state_delta_json,
            state_hash_before,
            state_hash_after,
            previous,
            digest,
        ),
    )
    return digest


def apply_patch(
    store: ProofStateStore,
    patch: Dict[str, Any],
    *,
    authority: PatchAuthority | None = None,
    original_base_revision: int | None = None,
) -> PatchOutcome:
    """Apply a patch under host-issued authority.

    This is the proof-state kernel boundary.  Callers processing model output
    must pass a session authority.  Human CLI code should use
    :func:`apply_operator_patch`; deterministic host code should use
    :func:`apply_system_patch`.
    """

    patch_id = str(patch.get("patch_id") or f"patch-{uuid.uuid4().hex[:12]}")
    resource_errors = _patch_resource_errors(patch)
    if resource_errors:
        _record_patch_rejection(
            store,
            patch,
            patch_id,
            resource_errors,
            kind="resource_limit",
        )
        return PatchOutcome(False, _safe_revision(store), patch_id, resource_errors)
    try:
        patch = _normalize_patch_aliases(patch)
    except (TypeError, ValueError) as exc:
        errors = [f"patch normalization failed: {exc}"]
        _record_patch_rejection(
            store,
            patch,
            patch_id,
            errors,
            kind="invalid_shape",
        )
        return PatchOutcome(False, _safe_revision(store), patch_id, errors)
    normalized_resource_errors = _patch_resource_errors(patch)
    if normalized_resource_errors:
        _record_patch_rejection(
            store,
            patch,
            patch_id,
            normalized_resource_errors,
            kind="resource_limit",
        )
        return PatchOutcome(
            False,
            _safe_revision(store),
            patch_id,
            normalized_resource_errors,
        )
    if authority is None:
        errors = ["host-issued patch authority is required"]
        _record_patch_rejection(store, patch, patch_id, errors, kind="missing_authority")
        return PatchOutcome(False, _safe_revision(store), patch_id, errors)
    errors = _validate_patch_shape(store.problem_id, patch)
    errors.extend(
        authority_contract_errors(
            patch,
            authority,
            original_base_revision=original_base_revision,
        )
    )
    if errors:
        _record_patch_rejection(store, patch, patch_id, errors, kind="invalid_shape")
        return PatchOutcome(False, _safe_revision(store), patch_id, errors)

    artifact_files = _ArtifactFileJournal()
    with store.connect() as conn:
        # Serialize the revision check with the mutation.  Reading the revision
        # before taking the write lock lets two simultaneous patches both accept
        # the same base revision and then commit conflicting revision N+1 rows.
        try:
            conn.execute("BEGIN IMMEDIATE")
            current_revision = store.get_revision(conn)
        except (sqlite3.Error, TypeError, ValueError, OverflowError) as exc:
            conn.rollback()
            current_revision = _safe_revision(store)
            lock_errors = [str(exc)]
            _record_patch_rejection(store, patch, patch_id, lock_errors, kind="exception")
            return PatchOutcome(False, current_revision, patch_id, lock_errors)
        current_seal = store.current_state_seal(
            conn,
            include_projection=True,
        )
        if not current_seal["valid"]:
            seal_errors = [
                "current proof-state seal is invalid: " + str(error)
                for error in current_seal["errors"]
            ]
            conn.rollback()
            _record_patch_rejection(
                store, patch, patch_id, seal_errors, kind="state_seal_invalid"
            )
            return PatchOutcome(False, current_revision, patch_id, seal_errors)
        state_before = current_seal.pop("_proof_state_projection", None)
        if not isinstance(state_before, dict):
            conn.rollback()
            seal_errors = [
                "current proof-state seal did not return its authenticated projection"
            ]
            _record_patch_rejection(
                store,
                patch,
                patch_id,
                seal_errors,
                kind="state_seal_invalid",
            )
            return PatchOutcome(False, current_revision, patch_id, seal_errors)
        if authority.source == "session":
            policy_row = conn.execute(
                "SELECT policy_event_head FROM problem_state WHERE problem_id = ?",
                (store.problem_id,),
            ).fetchone()
            current_policy_head = (
                str(policy_row["policy_event_head"] or "") if policy_row else ""
            )
            if current_policy_head != authority.policy_event_head:
                policy_errors = [
                    "session policy changed after context construction: "
                    f"{authority.policy_event_head} != {current_policy_head}"
                ]
                conn.rollback()
                _record_patch_rejection(
                    store,
                    patch,
                    patch_id,
                    policy_errors,
                    kind="stale_policy_context",
                )
                return PatchOutcome(
                    False, current_revision, patch_id, policy_errors
                )
        if int(patch["base_revision"]) != current_revision:
            stale_errors = [f"stale patch: base_revision {patch['base_revision']} != current_revision {current_revision}"]
            conn.rollback()
            _record_patch_rejection(store, patch, patch_id, stale_errors, kind="stale_base_revision")
            return PatchOutcome(False, current_revision, patch_id, stale_errors)

        try:
            verification_debt_reconciliations: list[Dict[str, Any]] = []
            counterexample_debt_reconciliations: list[Dict[str, Any]] = []
            pending_owners = _owners_created_by_patch(patch["operations"])
            for op in patch["operations"]:
                _apply_operation(
                    conn,
                    store,
                    patch,
                    op,
                    authority=authority,
                    pending_owners=pending_owners,
                    artifact_files=artifact_files,
                )

            if authority.context_request_ids:
                _mark_context_requests_fulfilled(
                    conn,
                    authority.context_request_ids,
                    # The requested packet was constructed from this exact
                    # pre-patch revision; record delivery at that revision.
                    fulfilled_revision=current_revision,
                )

            # Certificate invalidation is deterministic kernel behavior. Other
            # convenience changes (auto-routing, heuristic obligation closure,
            # and tag-driven supersession) are deliberately not inferred here;
            # they must arrive as explicit operations.
            integration_reconciliations = _reconcile_invalid_integrations(conn)

            bind_new_certificates(conn, applied_revision=current_revision + 1)
            certificate_revocations = invalidate_stale_refuted_obligations(conn)

            pending_run_ids = {
                str(op.get("run_id") or "")
                for op in patch["operations"]
                if isinstance(op, Mapping)
                and str(op.get("op") or "") == "record_run_metrics"
                and str(op.get("run_id") or "")
            }
            pending_dispatch_ids = {
                str(op.get("dispatch_id") or "")
                for op in patch["operations"]
                if isinstance(op, Mapping)
                and str(op.get("op") or "") == "record_scheduler_dispatch"
                and str(op.get("dispatch_id") or "")
            }
            invariant_errors = validate_conn(
                conn,
                pending_run_ids=pending_run_ids,
                pending_dispatch_ids=pending_dispatch_ids,
                # current_state_seal was verified immediately above and the
                # run/dispatch tables are append-only. Revalidate only rows
                # created by this transaction; explicit audits retain the
                # full-history path.
                immutable_history_sealed=True,
            )
            if invariant_errors:
                raise PatchRejected(invariant_errors)

            new_revision = current_revision + 1
            now = utc_now()
            conn.execute(
                "UPDATE problem_state SET current_revision = ?, updated_at = ? WHERE problem_id = ?",
                (new_revision, now, store.problem_id),
            )
            state_after = _state_journal_projection(conn)
            state_delta = _state_delta(state_before, state_after)
            state_hash_before = str(current_seal["proof_state_hash"])
            state_hash_after = _state_projection_hash(state_after)
            journal_entry_hash = append_applied_patch_entry(
                conn,
                patch_id=patch_id,
                problem_id=store.problem_id,
                base_revision=int(patch["base_revision"]),
                actor_role=str(patch["actor_role"]),
                target_id=str(patch.get("target_id") or ""),
                operations=patch["operations"],
                evidence_artifact_ids=patch.get("evidence_artifact_ids", []),
                rationale=str(patch.get("rationale") or ""),
                created_at=now,
                applied_revision=new_revision,
                authority=authority,
                state_delta=state_delta,
                state_hash_before=state_hash_before,
                state_hash_after=state_hash_after,
            )
            # Session-patch population is maintained by an AFTER INSERT
            # statistic trigger, so compute the companion seal only after the
            # patch journal row exists.
            run_provenance_hash = _run_provenance_hash(conn)
            conn.execute(
                "UPDATE problem_state SET proof_state_hash = ?, "
                "run_provenance_hash = ?, patch_journal_head = ? WHERE problem_id = ?",
                (
                    state_hash_after,
                    run_provenance_hash,
                    journal_entry_hash,
                    store.problem_id,
                ),
            )
            store.write_event(
                conn,
                new_revision,
                "patch_applied",
                {
                    "patch_id": patch_id,
                    "actor_role": authority.actor_role,
                    "authority": authority.to_audit_dict(),
                    "state_hash_before": state_hash_before,
                    "state_hash_after": state_hash_after,
                    "state_delta_operation_count": len(state_delta),
                    "journal_entry_hash": journal_entry_hash,
                },
            )
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
            if counterexample_debt_reconciliations:
                store.write_event(
                    conn,
                    new_revision,
                    "confirmed_counterexample_debt_resolved",
                    {"changes": counterexample_debt_reconciliations},
                )
            if certificate_revocations:
                store.write_event(
                    conn,
                    new_revision,
                    "certificate_revoked",
                    {"changes": certificate_revocations},
                )
            conn.commit()
            artifact_files.commit()
        except PatchRejected as exc:
            conn.rollback()
            artifact_files.rollback()
            _record_patch_rejection(store, patch, patch_id, exc.errors, kind="guard_rejected")
            return PatchOutcome(False, current_revision, patch_id, exc.errors)
        except (OSError, sqlite3.Error, TypeError, ValueError, KeyError) as exc:
            conn.rollback()
            artifact_files.rollback()
            _record_patch_rejection(store, patch, patch_id, [str(exc)], kind="exception")
            return PatchOutcome(False, current_revision, patch_id, [str(exc)])
        except BaseException:  # intentional-boundary: clean staged files before propagating programmer errors/signals
            conn.rollback()
            artifact_files.rollback()
            raise

    if store.auto_snapshot:
        store.write_snapshot()
    return PatchOutcome(True, new_revision, patch_id, [])


def apply_operator_patch(store: ProofStateStore, patch: Dict[str, Any]) -> PatchOutcome:
    """Apply a patch explicitly submitted by the local human operator."""

    return apply_patch(store, patch, authority=operator_authority(patch))


def apply_system_patch(
    store: ProofStateStore,
    patch: Dict[str, Any],
    *,
    mode: str = "",
    route_id: str = "",
) -> PatchOutcome:
    """Apply a deterministic orchestrator patch, never model-generated JSON."""

    return apply_patch(
        store,
        patch,
        authority=system_authority(
            actor_role=str(patch.get("actor_role") or "scheduler"),
            mode=mode,
            target_id=str(patch.get("target_id") or "root"),
            route_id=route_id,
            context_revision=int(patch.get("base_revision") or 0),
        ),
    )


def apply_operator_patch_with_stale_retry(
    store: ProofStateStore,
    patch: Dict[str, Any],
    *,
    max_retries: int = 3,
) -> PatchOutcome:
    """Compatibility helper for explicit local/operator test patches."""

    return apply_patch_with_stale_retry(
        store,
        patch,
        authority=operator_authority(patch),
        max_retries=max_retries,
    )


def reconcile_integrated_claims(store: ProofStateStore) -> Dict[str, Any]:
    """Explicitly repair legacy obligation and integration lifecycle state."""

    patch_id = f"integration-reconcile-{uuid.uuid4().hex[:12]}"
    with store.connect() as conn:
        try:
            # Reconciliation writes a synthetic patch and advances the same
            # revision counter as normal patches, so its revision read must be
            # serialized with those writers as well.
            conn.execute("BEGIN IMMEDIATE")
            current_revision = store.get_revision(conn)
            state_before = _state_journal_projection(conn)
            current_seal = store.current_state_seal(conn)
            if not current_seal["valid"]:
                raise RuntimeError(
                    "current proof-state seal is invalid: "
                    + "; ".join(
                        str(error) for error in current_seal["errors"][:8]
                    )
                )
            # Reconciliation is conservative: it may revoke an invalid
            # integration, but it never guesses that an active proof
            # obligation has been discharged.  Discharge/refutation always
            # requires an explicit operation naming exact evidence.
            changes = _reconcile_invalid_integrations(conn)
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
            state_after = _state_journal_projection(conn)
            state_delta = _state_delta(state_before, state_after)
            state_hash_before = _state_projection_hash(state_before)
            state_hash_after = _state_projection_hash(state_after)
            run_provenance_hash = _run_provenance_hash(conn)
            authority = system_authority(
                actor_role="system",
                mode="integrate",
                target_id="integration_reconciliation",
                context_revision=current_revision,
            )
            journal_entry_hash = append_applied_patch_entry(
                conn,
                patch_id=patch_id,
                problem_id=store.problem_id,
                base_revision=current_revision,
                actor_role="system",
                target_id="integration_reconciliation",
                operations=changes,
                evidence_artifact_ids=[],
                rationale=(
                    "reconcile stale verification obligations and integration "
                    "lifecycle with current proof obligations"
                ),
                created_at=now,
                applied_revision=new_revision,
                authority=authority,
                state_delta=state_delta,
                state_hash_before=state_hash_before,
                state_hash_after=state_hash_after,
            )
            conn.execute(
                "UPDATE problem_state SET proof_state_hash = ?, "
                "run_provenance_hash = ?, patch_journal_head = ? WHERE problem_id = ?",
                (
                    state_hash_after,
                    run_provenance_hash,
                    journal_entry_hash,
                    store.problem_id,
                ),
            )
            store.write_event(
                conn,
                new_revision,
                "integration_reconciled",
                {
                    "patch_id": patch_id,
                    "changes": changes,
                    "state_hash_before": state_hash_before,
                    "state_hash_after": state_hash_after,
                    "journal_entry_hash": journal_entry_hash,
                },
            )
            conn.commit()
        except BaseException:  # intentional-boundary: preserve transactional rollback on interruption
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
    except (OSError, sqlite3.Error, TypeError, ValueError):
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
    if not op.get("resolution_note") and op.get("resolution"):
        op["resolution_note"] = op["resolution"]
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
    integration_resolved_debt_ids: list[str] = []
    blocking_verification_evidence_ids: list[str] = []
    for op in operations:
        if not isinstance(op, dict):
            normalized_operations.append(op)
            continue
        normalized_op = dict(op)
        kind = _op_kind(normalized_op)
        kind = {
            "add_proof_obligation": "add_debt",
            "update_proof_obligation": "update_debt",
            "resolve_proof_obligation": "resolve_debt",
            "refute_proof_obligation": "update_debt",
        }.get(str(kind or ""), kind)
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
            # Public/model-facing terminology uses proof_draft.  Preserve the
            # historical database value so old queries and archives remain
            # readable without silently rewriting persisted provenance.
            if normalized_op.get("artifact_type") == "proof_draft":
                normalized_op["artifact_type"] = "proof_dossier"
            if "artifact_id" not in normalized_op and normalized_op.get("id"):
                normalized_op["artifact_id"] = normalized_op["id"]
            if "artifact_id" not in normalized_op:
                artifact_id = _derive_artifact_id(normalized_op, normalized)
                if artifact_id:
                    normalized_op["artifact_id"] = artifact_id
            if isinstance(normalized_op.get("metadata"), Mapping):
                metadata = dict(normalized_op["metadata"])
                for public_key, legacy_key in (
                    (
                        "directed_adversarial_review_mode",
                        "directed_villain_mode",
                    ),
                    (
                        "directed_adversarial_review_mode_reason",
                        "directed_villain_mode_reason",
                    ),
                    (
                        "directed_adversarial_review_mode_steps",
                        "directed_villain_mode_steps",
                    ),
                ):
                    if legacy_key not in metadata and metadata.get(public_key) is not None:
                        metadata[legacy_key] = metadata[public_key]
                    metadata.pop(public_key, None)
                if (
                    "creates_parallel_dossier" not in metadata
                    and metadata.get("creates_parallel_proof_draft") is not None
                ):
                    metadata["creates_parallel_dossier"] = metadata[
                        "creates_parallel_proof_draft"
                    ]
                metadata.pop("creates_parallel_proof_draft", None)
                if "resolved_debt_ids" not in metadata and metadata.get("resolved_proof_obligation_ids") is not None:
                    metadata["resolved_debt_ids"] = metadata["resolved_proof_obligation_ids"]
                if (
                    "resolved_debt_justifications" not in metadata
                    and metadata.get("resolved_proof_obligation_justifications") is not None
                ):
                    metadata["resolved_debt_justifications"] = metadata[
                        "resolved_proof_obligation_justifications"
                    ]
                normalized_op["metadata"] = metadata
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
                metadata = normalized_op.get("metadata")
                if isinstance(metadata, Mapping):
                    integration_resolved_debt_ids.extend(_string_list(metadata.get("resolved_debt_ids")))
        if kind in {"add_claim", "add_route", "add_inference"}:
            nested_key = {"add_claim": "claim", "add_route": "route", "add_inference": "inference"}[kind]
            if isinstance(normalized_op.get(nested_key), dict):
                normalized_op = _nested_payload_op(normalized_op, nested_key, kind)
            if kind == "add_route":
                _normalize_route_fields(normalized_op)
            elif kind == "add_inference":
                _normalize_inference_fields(normalized_op)
        if kind in {"add_debt", "update_debt", "resolve_debt"}:
            if isinstance(normalized_op.get("proof_obligation"), dict):
                _flatten_nested(normalized_op, "proof_obligation")
            if isinstance(normalized_op.get("debt"), dict):
                _flatten_nested(normalized_op, "debt")
            if "debt_id" not in normalized_op and normalized_op.get("proof_obligation_id"):
                normalized_op["debt_id"] = normalized_op["proof_obligation_id"]
            if "debt_type" not in normalized_op and normalized_op.get("obligation_type"):
                normalized_op["debt_type"] = normalized_op["obligation_type"]
            if str(_op_kind(op) or "") == "refute_proof_obligation":
                normalized_op["status"] = "refuted"
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
            if (
                normalized_op.get("target_type") == "claim"
                and normalized_op.get("status_type") == "lifecycle"
                and normalized_op.get("new_status") == "integrated"
                and not normalized_op.get("resolved_debt_ids")
                and integration_resolved_debt_ids
            ):
                # Keep stale-row conflict detection aligned with the apply-time
                # fallback that reads resolved ids from integration metadata.
                normalized_op["resolved_debt_ids"] = sorted(set(integration_resolved_debt_ids))
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
    _bind_evidence_targets(normalized_operations, normalized)
    normalized["operations"] = normalized_operations
    return normalized


def _bind_evidence_targets(operations: Sequence[Any], patch: Mapping[str, Any]) -> None:
    """Stamp evidence with the exact entities it is allowed to certify.

    The stamp is derived only from transitions that cite the artifact.  This
    preserves convenient same-patch verifier output while preventing a report
    from being replayed later against an unrelated claim, inference, or debt.
    """

    transitions = [
        op
        for op in operations
        if isinstance(op, dict) and str(op.get("op") or "") == "propose_status_transition"
    ]
    debt_transitions = [
        op
        for op in operations
        if isinstance(op, dict)
        and (
            str(op.get("op") or "") == "resolve_debt"
            or (
                str(op.get("op") or "") == "update_debt"
                and str(op.get("status") or "") == "refuted"
            )
        )
    ]
    patch_evidence = {str(item) for item in (patch.get("evidence_artifact_ids") or []) if str(item)}
    for op in operations:
        if not isinstance(op, dict) or str(op.get("op") or "") not in {"attach_artifact", "add_artifact"}:
            continue
        if str(op.get("artifact_type") or "") not in _VERIFICATION_EVIDENCE_ARTIFACT_TYPES:
            continue
        artifact_id = str(op.get("artifact_id") or "")
        if not artifact_id:
            continue
        metadata = dict(op.get("metadata") or {}) if isinstance(op.get("metadata"), Mapping) else {}
        targets = list(evidence_targets(metadata))
        for transition in transitions:
            cited = {
                str(item)
                for item in (transition.get("evidence_artifact_ids") or patch_evidence)
                if str(item)
            }
            if artifact_id not in cited:
                continue
            target_id = str(transition.get("target_id") or "").strip()
            if not target_id:
                continue
            targets.append(
                {
                    "target_type": str(transition.get("target_type") or "claim"),
                    "target_id": target_id,
                    "route_id": str(transition.get("route_id") or ""),
                }
            )
        for debt_op in debt_transitions:
            cited = {
                str(item)
                for item in (
                    debt_op.get("resolution_evidence_artifact_ids")
                    or debt_op.get("evidence_artifact_ids")
                    or patch_evidence
                )
                if str(item)
            }
            if artifact_id not in cited:
                continue
            debt_id = str(debt_op.get("debt_id") or "").strip()
            if debt_id:
                targets.append({"target_type": "debt", "target_id": debt_id, "route_id": ""})
        if not targets:
            patch_target = str(op.get("target_id") or patch.get("target_id") or "").strip()
            if patch_target:
                targets.append(
                    {
                        "target_type": "claim",
                        "target_id": patch_target,
                        "route_id": str(op.get("route_id") or patch.get("route_id") or ""),
                    }
                )
        if targets:
            unique = {
                (
                    str(target.get("target_type") or "claim"),
                    str(target.get("target_id") or ""),
                    str(target.get("route_id") or ""),
                )
                for target in targets
                if str(target.get("target_id") or "")
            }
            metadata["evidence_targets"] = [
                {"target_type": target_type, "target_id": target_id, "route_id": route_id}
                for target_type, target_id, route_id in sorted(unique)
            ]
            op["metadata"] = metadata


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
    if "resolved_debt_ids" not in op and op.get("resolved_proof_obligation_ids") is not None:
        op["resolved_debt_ids"] = op["resolved_proof_obligation_ids"]
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
        for alias in ("conclusion_id", "target_claim_id", "claim_id", "target_id"):
            value = op.get(alias)
            if isinstance(value, str) and value:
                op["conclusion_claim_id"] = value
                break
    if "strategy" not in op:
        for alias in ("proof_obligation", "argument_summary", "summary", "description", "method", "justification"):
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
    if "relation_to_parent" not in op:
        for alias in ("sufficiency", "relation_to_target"):
            value = op.get(alias)
            if isinstance(value, str) and value.strip() in ROUTE_RELATIONS:
                op["relation_to_parent"] = value.strip()
                break
    if "status" not in op:
        value = op.get("lifecycle_status")
        if isinstance(value, str) and value.strip() in ROUTE_STATUSES:
            op["status"] = value.strip()


def _normalize_inference_fields(op: Dict[str, Any]) -> None:
    if "conclusion_claim_id" not in op:
        for alias in ("conclusion_id", "target_claim_id", "claim_id", "target_id"):
            value = op.get(alias)
            if isinstance(value, str) and value:
                op["conclusion_claim_id"] = value
                break
    if "explanation" not in op:
        for alias in ("argument_summary", "proof_obligation", "summary", "description", "method", "justification"):
            value = op.get(alias)
            if isinstance(value, str) and value.strip():
                op["explanation"] = value
                break
    if "premise_claim_ids" not in op and isinstance(op.get("premise_ids"), list):
        op["premise_claim_ids"] = list(op["premise_ids"])
    if "validation_status" not in op:
        for alias in ("status", "lifecycle_status"):
            value = op.get(alias)
            if isinstance(value, str) and value.strip() in INFERENCE_STATUSES:
                op["validation_status"] = value.strip()
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
    authority: PatchAuthority,
    pending_owners: Mapping[str, set[str]] | None = None,
    artifact_files: _ArtifactFileJournal,
) -> None:
    kind = op["op"]
    if kind == "attach_artifact":
        _attach_artifact(
            conn,
            store,
            patch,
            _normalize_artifact_operation(op),
            authority=authority,
            artifact_files=artifact_files,
        )
    elif kind == "add_artifact":
        _attach_artifact(
            conn,
            store,
            patch,
            _normalize_artifact_operation(op),
            authority=authority,
            artifact_files=artifact_files,
        )
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
        if authority.source != "system":
            raise PatchRejected(["record_run_metrics is host telemetry and requires system authority"])
        _record_run(
            conn,
            op,
            problem_id=str(patch.get("problem_id") or store.problem_id),
            authority=authority,
        )
    elif kind == "record_scheduler_dispatch":
        if authority.source != "system":
            raise PatchRejected(
                ["record_scheduler_dispatch requires system authority"]
            )
        _record_scheduler_dispatch(conn, op, authority=authority)
    elif kind == "mark_publication_review_escalated":
        if authority.source != "system":
            raise PatchRejected(
                ["mark_publication_review_escalated requires deterministic system authority"]
            )
        review_id = _required(op, "review_id")
        review = conn.execute(
            "SELECT escalated_at FROM publication_reviews WHERE review_id = ?", (review_id,)
        ).fetchone()
        if review is None:
            raise PatchRejected([f"publication review does not exist: {review_id}"])
        if str(review["escalated_at"] or ""):
            raise PatchRejected([f"publication review is already escalated: {review_id}"])
        mark_route_error_escalated(conn, review_id)
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
        _certify_external_citation(
            conn,
            store,
            patch,
            op,
            authority=authority,
            artifact_files=artifact_files,
        )
    elif kind == "request_context_entity":
        _request_context_entity(conn, patch, op, authority=authority)
    elif kind == "cancel_context_request":
        _cancel_context_request(conn, op, authority=authority)
    elif kind == "set_claim_assurance":
        _set_claim_assurance(conn, op, authority=authority)
    else:
        raise PatchRejected([f"unknown operation: {kind}"])


_CONTEXT_REQUEST_TARGETS: tuple[tuple[str, str, str, str], ...] = (
    ("claim", "claims", "claim_id", "requested_claim_id"),
    ("route", "routes", "route_id", "requested_route_id"),
    ("inference", "inferences", "inference_id", "requested_inference_id"),
    (
        "proof_obligation",
        "debts",
        "debt_id",
        "requested_proof_obligation_id",
    ),
    ("artifact", "artifacts", "artifact_id", "requested_artifact_id"),
    (
        "retrieval_card",
        "retrieval_cards",
        "card_id",
        "requested_retrieval_card_id",
    ),
    (
        "theorem_library_entry",
        "theorem_library_entries",
        "entry_id",
        "requested_theorem_library_entry_id",
    ),
)


def _request_context_entity(
    conn: sqlite3.Connection,
    patch: Mapping[str, Any],
    op: Mapping[str, Any],
    *,
    authority: PatchAuthority,
) -> None:
    """Persist a non-certifying request for one omitted proof-state object."""

    allowed_roles = {
        "researcher",
        "adversarial_reviewer",
        "literature_researcher",
        "phd_advisor",
        "advisor",
    }
    actor = str(patch.get("actor_role") or "")
    if authority.source != "session" or actor not in allowed_roles:
        raise PatchRejected(
            ["request_context_entity requires an active research session"]
        )
    request_id = _required(op, "request_id")
    entity_id = _required(op, "requested_entity_id")
    if len(request_id) > 180 or not re.fullmatch(r"[A-Za-z0-9_.:/-]+", request_id):
        raise PatchRejected(["context request_id contains unsupported characters"])
    if len(entity_id) > 500:
        raise PatchRejected(["requested_entity_id is too long"])
    if conn.execute(
        "SELECT 1 FROM context_requests WHERE request_id = ?", (request_id,)
    ).fetchone():
        raise PatchRejected([f"context request already exists: {request_id}"])
    pending_count = int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM context_requests WHERE status = 'pending'"
        ).fetchone()["n"]
    )
    if pending_count >= 32:
        raise PatchRejected(
            ["too many pending context requests; process or cancel existing requests"]
        )

    requested_type = str(op.get("requested_entity_type") or "")
    match: tuple[str, str, str, str] | None = None
    matched_row: Mapping[str, Any] | None = None
    for candidate in _CONTEXT_REQUEST_TARGETS:
        entity_type, table, key_column, _typed_column = candidate
        if requested_type and requested_type != entity_type:
            continue
        row = conn.execute(
            f"SELECT * FROM {table} WHERE {key_column} = ?", (entity_id,)
        ).fetchone()
        if row is not None:
            match = candidate
            matched_row = dict(row)
            break
    if match is None:
        label = requested_type or "known requestable"
        raise PatchRejected([f"unknown {label} entity: {entity_id}"])
    entity_type, _table, _key_column, typed_column = match
    if entity_type == "artifact" and matched_row is not None and artifact_is_raw_log(
        matched_row
    ):
        raise PatchRejected(["raw run logs and transcripts are never requestable context"])
    if conn.execute(
        f"SELECT 1 FROM context_requests WHERE status = 'pending' "
        f"AND {typed_column} = ? AND requester_role = ?",
        (entity_id, actor),
    ).fetchone():
        raise PatchRejected(
            [f"a pending context request already covers {entity_type} {entity_id}"]
        )

    typed_values = {column: None for *_prefix, column in _CONTEXT_REQUEST_TARGETS}
    typed_values[typed_column] = entity_id
    now = utc_now()
    conn.execute(
        """
        INSERT INTO context_requests(
            request_id, requested_entity_type,
            requested_claim_id, requested_route_id, requested_inference_id,
            requested_proof_obligation_id, requested_artifact_id,
            requested_retrieval_card_id, requested_theorem_library_entry_id,
            requester_role, request_mode, original_target_id, original_route_id,
            status, requested_at, fulfilled_at, fulfilled_revision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, '', 0)
        """,
        (
            request_id,
            entity_type,
            typed_values["requested_claim_id"],
            typed_values["requested_route_id"],
            typed_values["requested_inference_id"],
            typed_values["requested_proof_obligation_id"],
            typed_values["requested_artifact_id"],
            typed_values["requested_retrieval_card_id"],
            typed_values["requested_theorem_library_entry_id"],
            actor,
            str(authority.mode or "prove"),
            str(authority.target_id or patch.get("target_id") or "root"),
            str(authority.route_id or ""),
            now,
        ),
    )


def _mark_context_requests_fulfilled(
    conn: sqlite3.Connection,
    request_ids: Sequence[str],
    *,
    fulfilled_revision: int,
) -> None:
    now = utc_now()
    for request_id in request_ids:
        row = conn.execute(
            "SELECT status FROM context_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise PatchRejected([f"scheduled context request is missing: {request_id}"])
        if str(row["status"] or "") != "pending":
            raise PatchRejected(
                [f"scheduled context request is no longer pending: {request_id}"]
            )
        conn.execute(
            "UPDATE context_requests SET status='fulfilled', fulfilled_at=?, "
            "fulfilled_revision=? WHERE request_id=?",
            (now, int(fulfilled_revision), request_id),
        )


def _cancel_context_request(
    conn: sqlite3.Connection,
    op: Mapping[str, Any],
    *,
    authority: PatchAuthority,
) -> None:
    """Cancel an unusable pending request under explicit host/operator authority."""

    if authority.source not in {"operator", "system"}:
        raise PatchRejected(
            ["cancel_context_request requires operator or deterministic system authority"]
        )
    request_id = _required(op, "request_id")
    row = conn.execute(
        "SELECT status FROM context_requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    if row is None:
        raise PatchRejected([f"context request does not exist: {request_id}"])
    if str(row["status"] or "") != "pending":
        raise PatchRejected(
            [f"only a pending context request can be cancelled: {request_id}"]
        )
    conn.execute(
        "UPDATE context_requests SET status='cancelled' WHERE request_id = ?",
        (request_id,),
    )


def _set_claim_assurance(
    conn: sqlite3.Connection,
    op: Mapping[str, Any],
    *,
    authority: PatchAuthority,
) -> None:
    if authority.source not in {"operator", "system"}:
        raise PatchRejected(
            ["claim assurance can be designated only by an operator or host policy"]
        )
    claim_id = _required(op, "claim_id")
    level = _required(op, "assurance_level")
    if level not in {"standard", "heterogeneous_review"}:
        raise PatchRejected([f"unsupported claim assurance level: {level}"])
    if not conn.execute(
        "SELECT 1 FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone():
        raise PatchRejected([f"unknown claim for assurance designation: {claim_id}"])
    rationale = str(op.get("rationale") or "").strip()
    if len(rationale) < 12:
        raise PatchRejected(
            ["claim assurance designation requires a concrete rationale"]
        )
    existing = conn.execute(
        "SELECT assurance_level FROM claim_assurance WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    if (
        existing
        and str(existing["assurance_level"] or "") == "heterogeneous_review"
        and level == "standard"
        and op.get("allow_assurance_downgrade") is not True
    ):
        raise PatchRejected(
            [
                "downgrading heterogeneous review requires "
                "allow_assurance_downgrade=true"
            ]
        )
    now = utc_now()
    conn.execute(
        """
        INSERT INTO claim_assurance(
            claim_id, assurance_level, rationale, designated_by,
            designated_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(claim_id) DO UPDATE SET
            assurance_level=excluded.assurance_level,
            rationale=excluded.rationale,
            designated_by=excluded.designated_by,
            updated_at=excluded.updated_at
        """,
        (
            claim_id,
            level,
            rationale,
            authority.reviewer_identity or authority.source,
            now,
            now,
        ),
    )


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
    *,
    authority: PatchAuthority,
    artifact_files: _ArtifactFileJournal,
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
        "evidence_targets": [
            {"target_type": "claim", "target_id": target_id, "route_id": route_id},
            {"target_type": "inference", "target_id": inference_id, "route_id": route_id},
        ],
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
        authority=authority,
        artifact_files=artifact_files,
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
    if "resolve_target_blocking_debts" in op:
        raise PatchRejected(
            [
                "resolve_target_blocking_debts is no longer supported; name each discharged proof obligation "
                "in a separate resolve_proof_obligation operation with exact evidence"
            ]
        )
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
def _attach_artifact(
    conn: sqlite3.Connection,
    store: ProofStateStore,
    patch: Dict[str, Any],
    op: Dict[str, Any],
    *,
    authority: PatchAuthority,
    artifact_files: _ArtifactFileJournal,
) -> None:
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
    forbidden_host_metadata = {
        key
        for key in (
            "host_reproduction",
            "host_formal_check",
            "host_formal_target_binding",
            "host_certificate_bindings",
            "host_reviewer_provenance",
            "pdf_status",
            "pdf_path",
            "pdf_sha256",
            "pdf_size_bytes",
            "latex_compiler_sha256",
            "latex_compilation_sandboxed",
        )
        if key in metadata
    }
    if forbidden_host_metadata:
        raise PatchRejected(
            [
                "host-computed artifact metadata is host-managed and must be omitted: "
                + ", ".join(sorted(forbidden_host_metadata))
            ]
        )
    metadata = _compact_artifact_metadata(artifact_type, metadata)
    if artifact_type == "cas_experiment_report":
        reproduction = reproduce_computation(metadata)
        metadata = {**metadata, "host_reproduction": reproduction}
    if artifact_type == "formal_backend_result":
        target_type = str(metadata.get("target_type") or "claim")
        target_id = str(metadata.get("target_id") or patch.get("target_id") or "")
        subject_digest = entity_subject_digest(conn, target_type, target_id)
        metadata = {
            **metadata,
            "host_formal_check": check_formal_artifact(metadata),
            "host_formal_target_binding": {
                "binding_version": 1,
                "target_type": target_type,
                "target_id": target_id,
                "subject_digest": subject_digest,
            },
        }
    if artifact_type in {
        "verification_report",
        "integration_report",
        "formal_backend_result",
        "confirmed_counterexample",
    }:
        metadata = {
            **metadata,
            "host_reviewer_provenance": {
                "source": authority.source,
                "reviewer_identity": authority.reviewer_identity,
                "independence_class": authority.reviewer_independence_class,
                "backend": authority.reviewer_backend,
                "backend_version": authority.reviewer_backend_version,
                "backend_contract_hash": authority.backend_contract_hash,
                "model": authority.reviewer_model,
                "run_id": authority.run_id,
                "session_id": authority.session_id,
                "context_hash": authority.context_hash,
            },
        }
    metadata = _prepare_revision_document_metadata(conn, actor, artifact_type, metadata)
    try:
        metadata = prepare_final_paper_metadata(
            conn,
            actor_role=actor,
            artifact_type=artifact_type,
            metadata=metadata,
        )
        metadata = prepare_referee_report_metadata(
            conn,
            actor_role=actor,
            artifact_type=artifact_type,
            metadata=metadata,
        )
    except ValueError as exc:
        raise PatchRejected([str(exc)]) from exc
    content = _artifact_inline_content(op)
    if content is not None and len(content.encode("utf-8")) > MAX_INLINE_ARTIFACT_BYTES:
        raise PatchRejected(
            [
                f"inline artifact content exceeds the {MAX_INLINE_ARTIFACT_BYTES}-byte limit; "
                "store large reproducible data outside the patch and attach a bounded report"
            ]
        )
    strategy_errors = strategic_artifact_errors(
        conn,
        artifact_type=artifact_type,
        metadata=metadata,
        content=content,
        actor_role=actor,
        base_revision=int(patch["base_revision"]),
    )
    if strategy_errors:
        raise PatchRejected(strategy_errors)
    path = _validated_artifact_path(
        store,
        op.get("path", ""),
        allow_writer_context_staging=(
            actor == "writer" and artifact_type in WRITER_PATH_ATTACH_ARTIFACT_TYPES
        ),
        artifact_id=artifact_id,
    )
    if content is not None and path:
        raise PatchRejected(["attach_artifact with inline content must omit path; the proof-state store writes artifacts under state_dir/artifacts"])
    expected_source_sha256 = str(op.get("source_file_sha256") or "")
    expected_source_size_raw = op.get("source_file_size_bytes")
    if bool(expected_source_sha256) != (expected_source_size_raw is not None):
        raise PatchRejected(
            [
                "path-based artifact source identity requires both "
                "source_file_sha256 and source_file_size_bytes"
            ]
        )
    expected_source_size: Optional[int] = None
    if expected_source_sha256:
        if (
            len(expected_source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_source_sha256
            )
            or type(expected_source_size_raw) is not int
            or expected_source_size_raw < 0
        ):
            raise PatchRejected(["path-based artifact source identity is malformed"])
        if content is not None or not path:
            raise PatchRejected(
                ["artifact source identity is valid only for a path-based attach"]
            )
        expected_source_size = expected_source_size_raw
    if path and actor == "writer" and artifact_type == REVISION_DOCUMENT_ARTIFACT_TYPE:
        expected_suffix = f".{metadata['document_format']}"
        actual_suffix = Path(path).suffix.lower()
        if actual_suffix != expected_suffix:
            raise PatchRejected(
                [
                    "revision_document staged path must preserve source format "
                    f"{expected_suffix!r}; got {actual_suffix or '<no suffix>'!r}"
                ]
            )
    staged_from_path = False
    if content is None and path and actor == "writer" and artifact_type in WRITER_PATH_ATTACH_ARTIFACT_TYPES:
        # Path-based writer attach: load the staged file so the full writer
        # guard chain below runs on it exactly as for inline content.
        content = _load_writer_staged_content(path)
        staged_from_path = True
        if expected_source_size is not None:
            source_bytes = content.encode("utf-8")
            if len(source_bytes) != expected_source_size:
                raise PatchRejected(
                    [
                        "artifact source size changed since result persistence: "
                        f"{path}"
                    ]
                )
            if hashlib.sha256(source_bytes).hexdigest() != expected_source_sha256:
                raise PatchRejected(
                    [
                        "artifact source content changed since result persistence: "
                        f"{path}"
                    ]
                )
    if content is not None and not content.endswith("\n"):
        content += "\n"
    incoming_bytes = (
        len(content.encode("utf-8"))
        if content is not None
        else int(Path(path).stat().st_size)
        if path
        else 0
    )
    # Import locally to avoid a module cycle through replay.py. The check is
    # deterministic over local files and runs before the artifact is copied.
    from .storage_policy import StoragePolicyError, audit_local_storage

    try:
        storage_report = audit_local_storage(store)
    except StoragePolicyError as exc:
        raise PatchRejected([str(exc)]) from exc
    if int(storage_report["total_local_bytes"]) + incoming_bytes >= int(
        storage_report["hard_limit_bytes"]
    ):
        raise PatchRejected(
            [
                "artifact would exceed the configured local proof-state storage hard limit; "
                "archive eligible session material or increase the explicit operator limit"
            ]
        )
    if actor == REFEREE_ROLE and artifact_type == "referee_report":
        expected_token = str(metadata.get("decision_token") or "")
        if not content or not content.lstrip().startswith(expected_token):
            raise PatchRejected(
                [f"publication referee_report content must begin with its decision token {expected_token}"]
            )
    content, content_augmented = _augment_writer_partial_receipt_content(conn, actor, artifact_type, metadata, content)
    content = _normalize_writer_latex_escaping(artifact_type, content)
    content = _normalize_writer_paper_template(artifact_type, content)
    _guard_writer_references(actor, artifact_type, content)
    _guard_writer_mathematical_exposition(actor, artifact_type, content)
    _guard_writer_generation_residue(actor, artifact_type, content)
    _guard_writer_paper_register(artifact_type, content)
    _guard_writing_review_metadata(artifact_type, artifact_id, metadata)
    if content is not None and len(content.encode("utf-8")) > MAX_INLINE_ARTIFACT_BYTES:
        raise PatchRejected(
            [
                "artifact content exceeds the inline byte limit after host-side "
                "normalization or partial-result augmentation"
            ]
        )
    if content is not None or path:
        metadata = {
            **metadata,
            "integrity": {"algorithm": "sha256", "scope": "file_bytes", "version": 1},
        }
    if content is None and path:
        # Copy first and hash the immutable store-managed result. Hashing the
        # staging path and copying it later admitted a check/use race in which
        # the recorded digest described bytes other than the accepted artifact.
        path = str(
            _copy_artifact_file(
                store,
                artifact_id,
                artifact_type,
                Path(path),
                artifact_files=artifact_files,
                expected_sha256=expected_source_sha256,
                expected_size=expected_source_size,
            )
        )
        try:
            storage_after_copy = audit_local_storage(store)
        except StoragePolicyError as exc:
            raise PatchRejected([str(exc)]) from exc
        if not storage_after_copy["within_hard_limit"]:
            raise PatchRejected(
                [
                    "copied artifact reached the configured local proof-state storage "
                    "hard limit; the staged copy will be rolled back"
                ]
            )
    # Always recompute the digest: a caller-supplied sha256 was trusted verbatim
    # here, letting an agent bypass duplicate-artifact rejection with a bogus hash.
    digest = artifact_hash(
        path=Path(path) if path and content is None else None,
        content=content,
        metadata=metadata,
    )
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
        path = str(
            _write_artifact_content(
                store,
                artifact_id,
                artifact_type,
                content,
                metadata=metadata,
                artifact_files=artifact_files,
            )
        )
    if actor == "writer" and content is not None and path:
        artifact_path = Path(path)
        for sidecar_path in (
            artifact_path.with_suffix(".tex"),
            artifact_path.with_suffix(".pdf"),
            artifact_path.with_suffix(".latex.log"),
        ):
            artifact_files.capture(sidecar_path)
        if artifact_type in {"final_paper", "human_readable_mathematical_text"} or (
            artifact_type == REVISION_DOCUMENT_ARTIFACT_TYPE
            and str(metadata.get("document_format") or "") == "tex"
        ):
            # The final_paper's content IS LaTeX source already stored as .tex;
            # compile it directly — no markdown->LaTeX conversion pass.
            sidecars = compile_latex_artifact(artifact_path, artifact_path.with_suffix(".pdf"))
        else:
            sidecars = write_latex_pdf_sidecars(path, content, title=_writer_artifact_title(artifact_id, artifact_type))
        # Persist the LaTeX compile outcome so the writing gate can tell whether
        # the shipped .tex actually compiled without re-running pdflatex. Merged
        # after the digest so it does not affect content-dedup hashing.
        pdf_status = str(sidecars.get("pdf_status") or "")
        if pdf_status:
            metadata = {**metadata, "pdf_status": pdf_status}
            for key in (
                "pdf_path",
                "pdf_sha256",
                "pdf_size_bytes",
                "latex_compiler_sha256",
                "latex_compilation_sandboxed",
            ):
                value = sidecars.get(key)
                if value not in (None, ""):
                    metadata[key] = value
            log_path = str(sidecars.get("latex_log_path") or "")
            if log_path:
                metadata["latex_log_path"] = log_path
    created_at = utc_now()
    if "state_revision" in op:
        raise PatchRejected(["artifact state_revision is host-managed and must be omitted"])
    asserted_run_id = str(op.get("run_id") or "")
    if authority.source == "session":
        if not authority.run_id:
            raise PatchRejected(["session artifact authority is missing the host run_id"])
        if asserted_run_id and asserted_run_id != authority.run_id:
            raise PatchRejected(["artifact run_id does not match the host-issued execution run_id"])
        artifact_run_id = authority.run_id
    else:
        artifact_run_id = asserted_run_id
    # The artifact becomes visible in the revision committed by this patch,
    # not in the revision from which the child read context.
    artifact_state_revision = int(patch["base_revision"]) + 1
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
            artifact_run_id,
            artifact_state_revision,
            op.get("content_summary") or artifact_summary(metadata, fallback=content or ""),
            json_dumps(metadata),
            created_at,
        ),
    )
    if artifact_type == "referee_report" and actor == REFEREE_ROLE:
        record_referee_report(
            conn,
            artifact_id=artifact_id,
            metadata=metadata,
            state_revision=artifact_state_revision,
            created_at=created_at,
        )


def _prepare_revision_document_metadata(
    conn: sqlite3.Connection,
    actor: str,
    artifact_type: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate immutable format/source lineage for external revisions."""

    if artifact_type != REVISION_DOCUMENT_ARTIFACT_TYPE:
        return metadata
    if actor != "writer":
        return metadata
    revision_of = str(metadata.get("revision_of_artifact_id") or "").strip()
    if not revision_of:
        raise PatchRejected(["writer revision_document requires metadata.revision_of_artifact_id"])
    row = conn.execute(
        "SELECT artifact_type, metadata_json FROM artifacts WHERE artifact_id = ?",
        (revision_of,),
    ).fetchone()
    if row is None or str(row["artifact_type"] or "") != REVISION_DOCUMENT_ARTIFACT_TYPE:
        raise PatchRejected(
            [f"revision_document predecessor {revision_of!r} does not exist or is not a revision_document"]
        )
    previous = revision_document_metadata({"metadata_json": row["metadata_json"]})
    previous_format = str(previous.get("document_format") or "").strip().lower()
    document_format = str(metadata.get("document_format") or "").strip().lower()
    if document_format not in {"md", "tex"}:
        raise PatchRejected(["revision_document metadata.document_format must be 'md' or 'tex'"])
    if document_format != previous_format:
        raise PatchRejected(
            [f"revision_document must preserve source format {previous_format!r}; got {document_format!r}"]
        )
    original_sha256 = str(metadata.get("original_sha256") or "").strip().lower()
    expected_sha256 = str(previous.get("original_sha256") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", original_sha256) or original_sha256 != expected_sha256:
        raise PatchRejected(["revision_document must preserve the predecessor's metadata.original_sha256"])
    if metadata.get("revision_mode") is not True:
        raise PatchRejected(["revision_document requires metadata.revision_mode=true"])
    return {
        **previous,
        **metadata,
        "document_format": document_format,
        "original_sha256": expected_sha256,
        "revision_of_artifact_id": revision_of,
        "revision_number": int(previous.get("revision_number") or 0) + 1,
        "revision_mode": True,
        "diff_minimal": True,
        "voice_preserving": True,
        "mathematical_status": "not_verified_by_writing_harness",
    }


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
    try:
        return read_bounded_text(
            Path(path),
            max_bytes=WRITER_PATH_ATTACH_MAX_BYTES,
            label="writer-staged artifact",
        )
    except ValueError as exc:
        raise PatchRejected([str(exc)]) from exc


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
    if artifact_type not in (
        WRITER_REFERENCE_REQUIRED_ARTIFACT_TYPES | {"human_readable_mathematical_text"}
    ):
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
    if artifact_type not in {"final_paper", "human_readable_mathematical_text"} or not content:
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
    if artifact_type not in {"final_paper", "human_readable_mathematical_text"} or not content:
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
                "final_proof, final_paper, or revision_document"
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
    fingerprint = fingerprint_text(statement)
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
    if append and row["validation_status"] in {"informally_verified", "formally_verified"}:
        invalidate_dependents(conn, changed_inference_ids=[inference_id])


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
        evidence_ids = list(
            dict.fromkeys(
                [
                    str(item)
                    for item in (
                        op.get("resolution_evidence_artifact_ids")
                        or op.get("evidence_artifact_ids")
                        or []
                    )
                    if str(item or "")
                ]
                + [str(item) for item in (patch.get("evidence_artifact_ids") or []) if str(item or "")]
            )
        )
        actor = str(patch.get("actor_role") or "")
        if row["status"] == "refuted":
            existing_evidence = json_loads(row["resolution_evidence_json"], {})
            if not isinstance(existing_evidence, dict):
                existing_evidence = {}
            existing_evidence.update(evidence)
            conn.execute(
                "UPDATE debts SET last_seen = ?, resolution_evidence_json = ? WHERE debt_id = ?",
                (utc_now(), json_dumps(existing_evidence), debt_id),
            )
            return
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
        has_evidence = False
        if actor == "strict_informal_verifier":
            has_evidence = _has_clean_verification(
                conn,
                evidence_ids,
                outcome="positive",
                target_type="debt",
                target_id=debt_id,
                producer_role="strict_informal_verifier",
            )
        elif actor == "formal_backend":
            has_evidence = _has_valid_formal_backend_result(
                conn,
                evidence_ids,
                target_type="debt",
                target_id=debt_id,
            )
        elif actor == "counterexample_validator":
            has_evidence = _has_artifact_type(
                conn,
                evidence_ids,
                "confirmed_counterexample",
                target_type="debt",
                target_id=debt_id,
                producer_role="counterexample_validator",
            )
        if not has_evidence:
            raise PatchRejected(
                [
                    f"resolving proof obligation {debt_id} requires current evidence bound to that obligation: "
                    "a clean strict verification report, a host-checked formal result, or a confirmed counterexample"
                ]
            )
        evidence["resolution_evidence_artifact_ids"] = evidence_ids
        evidence["resolved_by"] = actor
        evidence["resolution_status"] = "closed_by_explicit_verification"
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
        actor = str(patch.get("actor_role") or "")
        if row["status"] == "refuted" and status != "refuted":
            raise PatchRejected(
                [
                    f"refuted debt {debt_id} cannot be reclassified as {status}; create a corrected obligation as a new debt"
                ]
            )
        resolution_json = row["resolution_evidence_json"]
        resolution_note = str(op.get("resolution_note") or "").strip()
        resolution_ids = [str(item) for item in (op.get("resolution_evidence_artifact_ids") or []) if str(item or "")]
        resolution_extra = op.get("resolution_evidence") if isinstance(op.get("resolution_evidence"), Mapping) else {}
        if status == "refuted":
            if actor not in {"strict_informal_verifier", "counterexample_validator"}:
                raise PatchRejected(
                    [
                        f"{actor} cannot mark debt {debt_id} as refuted; expected counterexample_validator or strict_informal_verifier"
                    ]
                )
            evidence_ids = list(
                dict.fromkeys(
                    resolution_ids
                    + [str(item) for item in (op.get("evidence_artifact_ids") or []) if str(item or "")]
                    + [str(item) for item in (patch.get("evidence_artifact_ids") or []) if str(item or "")]
                )
            )
            has_confirmed_counterexample = _has_artifact_type(
                conn,
                evidence_ids,
                "confirmed_counterexample",
                target_type="debt",
                target_id=debt_id,
                producer_role="counterexample_validator",
            )
            has_strict_refutation_report = (
                actor == "strict_informal_verifier"
                and _has_clean_verification(
                    conn,
                    evidence_ids,
                    outcome="refutation",
                    target_type="debt",
                    target_id=debt_id,
                    producer_role="strict_informal_verifier",
                )
            )
            if not has_confirmed_counterexample and not has_strict_refutation_report:
                raise PatchRejected(
                    [
                        "refuted debt status requires debt-bound confirmed_counterexample evidence or a "
                        "zero-gap strict_informal_verifier verification_report"
                    ]
                )
            resolution_extra = dict(resolution_extra)
            resolution_extra.update(
                {
                    "classification": "refuted",
                    "resolution_status": "closed_by_refutation",
                    "refuted_by": actor,
                }
            )
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
    if status == "refuted":
        raise PatchRejected(["new debts must be created as active; use an evidence-gated update_debt to refute an existing debt"])
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
    # A duplicate add_debt operation must not silently resurrect a verifier-
    # refuted obligation.  A materially corrected obligation needs a new
    # fingerprint and therefore a new debt row.
    if existing["status"] == "refuted":
        status = "refuted"
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

    if actor in {WRITING_CRITIC_ROLE, REFEREE_ROLE}:
        raise PatchRejected([
            f"{actor} may not transition claim, inference, or route statuses; "
            "the scheduler alone escalates a referee's route-error decision back to research"
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
    if new_status == "informally_verified" and not _has_clean_verification(
        conn,
        evidence_ids,
        outcome="positive",
        target_type=target_type,
        target_id=target_id,
        producer_role="strict_informal_verifier",
    ):
        raise PatchRejected(["informally_verified requires a strict_informal_verifier verification_report artifact with zero errors and gaps"])
    if new_status == "formally_verified" and not _has_valid_formal_backend_result(
        conn,
        evidence_ids,
        target_type=target_type,
        target_id=target_id,
    ):
        raise PatchRejected([
            "formally_verified requires a host-executed, successful formal_backend_result from an allowlisted proof checker"
        ])
    if new_status == "formally_verified":
        status_table = {
            "claim": ("claims", "claim_id"),
            "inference": ("inferences", "inference_id"),
        }.get(target_type)
        if status_table is None:
            raise PatchRejected(
                ["formal verification is supported only for claims and inferences"]
            )
        table, identifier_column = status_table
        previous_status_row = conn.execute(
            f"SELECT validation_status FROM {table} WHERE {identifier_column} = ?",
            (target_id,),
        ).fetchone()
        previous_status = str(
            previous_status_row["validation_status"] if previous_status_row else ""
        )
        if previous_status not in {"informally_verified", "formally_verified"}:
            raise PatchRejected(
                [
                    "formal verification may upgrade only a claim or inference that already passed "
                    "strict informal verification; this prevents an unrelated formal encoding from "
                    "certifying an otherwise unchecked mathematical statement"
                ]
            )
    if new_status == "refuted":
        has_confirmed_counterexample = _has_artifact_type(
            conn,
            evidence_ids,
            "confirmed_counterexample",
            target_type=target_type,
            target_id=target_id,
            producer_role="counterexample_validator",
        )
        has_strict_refutation_report = (
            actor == "strict_informal_verifier"
            and _has_clean_verification(
                conn,
                evidence_ids,
                outcome="refutation",
                target_type=target_type,
                target_id=target_id,
                producer_role="strict_informal_verifier",
            )
        )
        if not has_confirmed_counterexample and not has_strict_refutation_report:
            raise PatchRejected(["refuted requires confirmed_counterexample evidence or a zero-gap strict_informal_verifier verification_report"])

    if status_type == "lifecycle" and new_status == "integrated":
        if actor != "integration_verifier":
            raise PatchRejected(["integrated lifecycle transition requires integration_verifier actor"])
        if target_type != "claim":
            raise PatchRejected(["only claims can receive integrated lifecycle status"])
        resolved_debt_ids = _integration_resolved_debt_ids(conn, op, evidence_ids)
        resolved_debt_justifications = _integration_resolved_debt_justifications(
            conn,
            evidence_ids,
        )
        _guard_integration(
            conn,
            target_id,
            op.get("route_id"),
            evidence_ids,
            resolved_debt_ids=resolved_debt_ids,
            resolved_debt_justifications=resolved_debt_justifications,
        )
        route_id = str(op.get("route_id") or "")
        # The integration report certifies both the claim transition and the
        # exact sufficient route.  Persist that provenance on the route itself
        # so the host can bind and later revoke the route certificate without
        # guessing from artifact prose or optional metadata.
        conn.execute(
            "UPDATE routes SET status = 'integrated', evidence_artifact_ids_json = ?, updated_at = ? WHERE route_id = ?",
            (
                json_dumps(sorted(set(_route_evidence(conn, route_id) + evidence_ids))),
                utc_now(),
                route_id,
            ),
        )
        _resolve_integration_debts(
            conn,
            resolved_debt_ids,
            claim_id=target_id,
            route_id=route_id,
            evidence_ids=evidence_ids,
            resolved_debt_justifications=resolved_debt_justifications,
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
        if new_status in {"refuted", "superseded"}:
            invalidate_dependents(conn, changed_claim_ids=[target_id])
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
    resolved_debt_justifications: Mapping[str, str] | None = None,
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
    assurance_errors = claim_assurance_errors(
        conn, claim_id=claim_id, route_id=str(route_id)
    )
    if assurance_errors:
        raise PatchRejected(assurance_errors)
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
    justifications = resolved_debt_justifications or {}
    route_inference_ids = {str(inf["inference_id"] or "") for inf in inferences}
    for debt_id in sorted(resolved):
        debt = conn.execute(
            "SELECT * FROM debts WHERE debt_id = ?",
            (debt_id,),
        ).fetchone()
        if debt is None:
            raise PatchRejected([f"unknown resolved_debt_id for integration: {debt_id}"])
        _guard_integration_debt_resolution(
            debt,
            claim_id=claim_id,
            route_id=route_id,
            route_inference_ids=route_inference_ids,
            justification=str(justifications.get(debt_id) or ""),
        )
    if any(row["debt_id"] not in resolved for row in blockers):
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


def _integration_resolved_debt_justifications(
    conn: sqlite3.Connection,
    evidence_ids: Sequence[str],
) -> Dict[str, str]:
    """Read verifier-authored debt explanations from integration evidence."""

    result: Dict[str, str] = {}
    for artifact_id in evidence_ids:
        row = conn.execute(
            "SELECT artifact_type, metadata_json FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if not row or row["artifact_type"] != "integration_report":
            continue
        metadata = json_loads(row["metadata_json"], {})
        raw = metadata.get("resolved_debt_justifications") if isinstance(metadata, Mapping) else None
        if not isinstance(raw, Mapping):
            continue
        for debt_id, explanation in raw.items():
            text = str(explanation or "").strip()
            if text:
                result[str(debt_id)] = text
    return result


def _guard_integration_debt_resolution(
    debt: sqlite3.Row,
    *,
    claim_id: str,
    route_id: str,
    route_inference_ids: set[str],
    justification: str,
) -> None:
    debt_id = str(debt["debt_id"] or "")
    owner_id = str(debt["owner_id"] or "")
    suggested = str(debt["suggested_next_target"] or "")
    directly_owned = owner_id in {claim_id, route_id, *route_inference_ids} or suggested in {
        claim_id,
        route_id,
        *route_inference_ids,
    }
    if directly_owned:
        return
    root_owned = owner_id == "root" or suggested == "root"
    if not root_owned:
        raise PatchRejected([f"integration cannot resolve unrelated debt: {debt_id}"])
    if len(" ".join(justification.split())) < 40:
        raise PatchRejected(
            [
                f"integration resolving upstream/root debt {debt_id} requires a precise "
                "integration_report metadata.resolved_debt_justifications explanation"
            ]
        )


def _resolve_integration_debts(
    conn: sqlite3.Connection,
    debt_ids: Sequence[str],
    *,
    claim_id: str,
    route_id: str,
    evidence_ids: Sequence[str],
    resolved_debt_justifications: Mapping[str, str] | None = None,
) -> None:
    if not debt_ids:
        return
    route_inference_ids = {
        row["inference_id"]
        for row in conn.execute("SELECT inference_id FROM inferences WHERE route_id = ?", (route_id,))
    }
    justifications = resolved_debt_justifications or {}
    now = utc_now()
    for debt_id in debt_ids:
        row = conn.execute("SELECT * FROM debts WHERE debt_id = ?", (debt_id,)).fetchone()
        if row is None:
            raise PatchRejected([f"unknown resolved_debt_id for integration: {debt_id}"])
        suggested = str(row["suggested_next_target"] or "")
        owner_id = str(row["owner_id"] or "")
        _guard_integration_debt_resolution(
            row,
            claim_id=claim_id,
            route_id=route_id,
            route_inference_ids={str(item) for item in route_inference_ids},
            justification=str(justifications.get(str(debt_id)) or ""),
        )
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
                "resolution_justification": str(justifications.get(str(debt_id)) or ""),
            }
        )
        conn.execute(
            "UPDATE debts SET status = 'resolved', last_seen = ?, resolution_evidence_json = ? WHERE debt_id = ?",
            (now, json_dumps(evidence), debt_id),
        )


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
    blocking_debt_ids = [
        str(debt["debt_id"] or "")
        for debt in conn.execute(
            "SELECT * FROM debts WHERE status = 'active' AND severity = 'blocking'"
        )
        if str(debt["owner_id"] or "") in owner_ids
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


def _update_scheduler_fairness_state(
    conn: sqlite3.Connection,
    *,
    decision_trace: Mapping[str, Any],
    selection_design: str,
    run_id: str = "",
    dispatch_id: str = "",
) -> None:
    """Advance authenticated compact deferral counters exactly once per wave."""

    if bool(run_id) == bool(dispatch_id):
        raise PatchRejected(
            ["scheduler fairness update requires exactly one provenance source"]
        )

    wave = decision_trace.get("parallel_wave_admission")
    if wave is None:
        return
    if not isinstance(wave, Mapping) or selection_design not in {
        "deterministic",
        "randomized",
    }:
        raise PatchRejected(
            ["parallel wave fairness state requires auditable decision provenance"]
        )
    wave_id = str(wave.get("wave_id") or "")
    policy_version = int(wave.get("policy_version") or 0)
    state_revision = (
        int(wave.get("state_revision") or 0) if policy_version >= 4 else 0
    )
    meta = conn.execute(
        "SELECT last_wave_id, last_state_revision FROM scheduler_fairness_meta "
        "WHERE singleton = 1"
    ).fetchone()
    if meta is not None and str(meta["last_wave_id"] or "") == wave_id:
        return
    if meta is not None and state_revision <= int(
        meta["last_state_revision"] or 0
    ):
        # Another decision from this snapshot (or a newer one) reached the
        # store first. Preserve this run's telemetry without replaying stale
        # fairness input over the current compact state.
        return
    rows = wave.get("candidates")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise PatchRejected(["parallel wave fairness candidates are malformed"])
    companion_rows = [
        row
        for row in rows
        if str(row.get("candidate_id") or "") != "parallel:primary"
    ]
    candidate_ids = [str(row.get("candidate_id") or "") for row in companion_rows]
    aliases: Dict[str, tuple[str, ...]] = {}
    if 4 <= policy_version < 7:
        for candidate_id, row in zip(candidate_ids, companion_rows):
            identity = (
                row.get("semantic_identity")
                if isinstance(row.get("semantic_identity"), list)
                else ()
            )
            candidate_aliases = tuple(
                alias
                for alias in (parallel_v3_candidate_alias(identity),)
                if alias
            )
            if candidate_aliases:
                aliases[candidate_id] = candidate_aliases
    stored_counts = {
        str(row["candidate_id"]): int(row["consecutive_capacity_deferrals"])
        for row in conn.execute(
            "SELECT candidate_id, consecutive_capacity_deferrals "
            "FROM scheduler_candidate_deferrals"
        ).fetchall()
    }
    try:
        prior_counts = parallel_candidate_deferral_counts_from_state(
            stored_counts,
            candidate_ids,
            candidate_aliases=aliases,
        )
    except ValueError as exc:
        raise PatchRejected([str(exc)]) from exc
    for row in companion_rows:
        candidate_id = str(row.get("candidate_id") or "")
        if int(row.get("consecutive_deferrals") or 0) != prior_counts[candidate_id]:
            raise PatchRejected(
                [
                    "parallel wave deferral input disagrees with authenticated "
                    f"scheduler state for {candidate_id}"
                ]
            )

    conn.execute("DELETE FROM scheduler_candidate_deferrals")
    for row in companion_rows:
        if str(row.get("disposition") or "") != "rejected" or not (
            parallel_outcome_is_fairness_eligible(
                row,
                policy_version=policy_version,
            )
        ):
            continue
        candidate_id = str(row.get("candidate_id") or "")
        conn.execute(
            "INSERT INTO scheduler_candidate_deferrals("
            "candidate_id, consecutive_capacity_deferrals, last_wave_id, "
            "policy_version, updated_run_id, updated_dispatch_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                candidate_id,
                prior_counts[candidate_id] + 1,
                wave_id,
                policy_version,
                run_id or None,
                dispatch_id or None,
            ),
        )
    conn.execute(
        "INSERT INTO scheduler_fairness_meta("
        "singleton, last_wave_id, last_state_revision, policy_version, "
        "updated_run_id, updated_dispatch_id) VALUES (1, ?, ?, ?, ?, ?) "
        "ON CONFLICT(singleton) DO UPDATE SET "
        "last_wave_id = excluded.last_wave_id, "
        "last_state_revision = excluded.last_state_revision, "
        "policy_version = excluded.policy_version, "
        "updated_run_id = excluded.updated_run_id, "
        "updated_dispatch_id = excluded.updated_dispatch_id",
        (
            wave_id,
            state_revision,
            policy_version,
            run_id or None,
            dispatch_id or None,
        ),
    )


def _update_scheduler_decision_fairness_state(
    conn: sqlite3.Connection,
    *,
    decision_trace: Mapping[str, Any],
    selection_design: str,
    state_revision: int,
    run_id: str = "",
    dispatch_id: str = "",
) -> None:
    """Advance generic/nested fairness only for a primary scheduler decision."""

    if bool(run_id) == bool(dispatch_id):
        raise PatchRejected(
            ["scheduler decision fairness update requires exactly one provenance source"]
        )

    rows = decision_trace.get("candidates")
    if selection_design not in {"deterministic", "randomized"} or not isinstance(
        rows, list
    ) or not rows:
        return
    wave = decision_trace.get("parallel_wave_admission")
    if decision_trace_is_parallel_companion(decision_trace):
        return
    if isinstance(wave, Mapping):
        decision_id = str(wave.get("wave_id") or "")
    else:
        decision_id = dispatch_id or run_id
    if not decision_id:
        raise PatchRejected(["scheduler decision fairness identifier is missing"])
    meta = conn.execute(
        "SELECT last_decision_id, last_state_revision "
        "FROM scheduler_decision_fairness_meta "
        "WHERE singleton = 1"
    ).fetchone()
    if meta is not None and str(meta["last_decision_id"] or "") == decision_id:
        return
    if meta is not None and state_revision <= int(meta["last_state_revision"] or 0):
        # Concurrent or late completion from an already-consumed snapshot.
        # Its run record remains authoritative telemetry, but it cannot apply
        # stale comparison input to current fairness state.
        return
    stored_counts = {
        str(row["candidate_id"]): int(row["consecutive_deferrals"])
        for row in conn.execute(
            "SELECT candidate_id, consecutive_deferrals "
            "FROM scheduler_decision_deferrals"
        ).fetchall()
    }
    try:
        updated_counts = decision_deferral_state_after_trace(
            stored_counts, decision_trace
        )
    except ValueError as exc:
        raise PatchRejected([str(exc)]) from exc
    policy_version = int(decision_trace.get("decision_policy_version") or 0)
    conn.execute("DELETE FROM scheduler_decision_deferrals")
    for candidate_id, count in updated_counts.items():
        conn.execute(
            "INSERT INTO scheduler_decision_deferrals("
            "candidate_id, consecutive_deferrals, last_decision_id, "
            "policy_version, updated_run_id, updated_dispatch_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                candidate_id,
                count,
                decision_id,
                policy_version,
                run_id or None,
                dispatch_id or None,
            ),
        )
    conn.execute(
        "INSERT INTO scheduler_decision_fairness_meta("
        "singleton, last_decision_id, last_state_revision, policy_version, "
        "updated_run_id, updated_dispatch_id) VALUES (1, ?, ?, ?, ?, ?) "
        "ON CONFLICT(singleton) DO UPDATE SET "
        "last_decision_id = excluded.last_decision_id, "
        "last_state_revision = excluded.last_state_revision, "
        "policy_version = excluded.policy_version, "
        "updated_run_id = excluded.updated_run_id, "
        "updated_dispatch_id = excluded.updated_dispatch_id",
        (
            decision_id,
            state_revision,
            policy_version,
            run_id or None,
            dispatch_id or None,
        ),
    )


def _record_scheduler_dispatch(
    conn: sqlite3.Connection,
    op: Dict[str, Any],
    *,
    authority: PatchAuthority,
) -> None:
    """Persist one exact scheduler allocation before external execution."""

    if authority.source != "system":
        raise PatchRejected(["scheduler dispatch requires system authority"])
    dispatch_id = _required(op, "dispatch_id")
    if conn.execute(
        "SELECT 1 FROM scheduler_dispatches WHERE dispatch_id = ?",
        (dispatch_id,),
    ).fetchone():
        raise PatchRejected([f"scheduler dispatch is append-only: {dispatch_id}"])
    group_id = _required(op, "dispatch_group_id")
    latest_dispatch = conn.execute(
        "SELECT d.dispatch_group_id FROM scheduler_source_entries AS s "
        "JOIN scheduler_dispatches AS d ON d.dispatch_id = s.record_id "
        "WHERE s.record_kind = 'dispatch' ORDER BY s.sequence DESC LIMIT 1"
    ).fetchone()
    latest_group_id = (
        str(latest_dispatch["dispatch_group_id"] or "")
        if latest_dispatch is not None
        else ""
    )
    unresolved_other_group = None
    if latest_group_id and latest_group_id != group_id:
        unresolved_other_group = conn.execute(
            "SELECT d.dispatch_id FROM scheduler_dispatches AS d "
            "LEFT JOIN runs AS r ON r.scheduler_dispatch_id = d.dispatch_id "
            "WHERE d.dispatch_group_id = ? AND r.run_id IS NULL LIMIT 1",
            (latest_group_id,),
        ).fetchone()
    if unresolved_other_group is not None:
        raise PatchRejected(
            [
                "a new scheduler wave cannot be committed while an earlier "
                "dispatch group remains unresolved"
            ]
        )
    actor_role = _required(op, "actor_role")
    target_id = _required(op, "target_id")
    committed_at = _required(op, "committed_at")
    position = op.get("dispatch_position")
    if type(position) is not int or position < 0:
        raise PatchRejected(["scheduler dispatch position must be nonnegative"])
    is_companion = op.get("is_companion")
    if type(is_companion) is not bool:
        raise PatchRejected(["scheduler dispatch companion flag must be boolean"])
    if (position > 0) != is_companion:
        raise PatchRejected(
            ["scheduler dispatch position and companion flag disagree"]
        )
    mode = _required(op, "mode")
    if mode not in EXECUTABLE_RUN_MODES:
        raise PatchRejected([f"invalid executable scheduler dispatch mode: {mode}"])
    state_revision = op.get("decision_state_revision")
    if type(state_revision) is not int or state_revision < 0:
        raise PatchRejected(
            ["scheduler dispatch state revision must be nonnegative"]
        )
    state = conn.execute(
        "SELECT current_revision, proof_state_hash, run_provenance_hash, "
        "remaining_token_budget, reserved_verification_budget "
        "FROM problem_state"
    ).fetchone()
    if state is None:
        raise PatchRejected(["problem state is missing"])
    if (
        state_revision != int(state["current_revision"])
        or str(op.get("proof_state_hash") or "") != str(state["proof_state_hash"] or "")
        or str(op.get("prior_run_provenance_hash") or "")
        != str(state["run_provenance_hash"] or "")
    ):
        raise PatchRejected(
            ["scheduler dispatch does not match the authenticated planning snapshot"]
        )
    selection_design = str(op.get("selection_design") or "")
    if selection_design not in {"deterministic", "randomized"}:
        raise PatchRejected(
            ["scheduler dispatch must have deterministic or randomized provenance"]
        )
    decision_trace = op.get("decision_trace")
    if not isinstance(decision_trace, Mapping):
        raise PatchRejected(["scheduler dispatch decision trace must be an object"])
    candidate_set_hash = str(op.get("candidate_set_hash") or "")
    policy_version = op.get("selection_policy_version")
    if type(policy_version) is not int or policy_version <= 0:
        raise PatchRejected(["scheduler dispatch policy version must be positive"])
    if (
        str(decision_trace.get("candidate_set_sha256") or "") != candidate_set_hash
        or decision_trace.get("decision_policy_version") != policy_version
    ):
        raise PatchRejected(
            ["scheduler dispatch provenance disagrees with its decision trace"]
        )
    trace_errors = decision_trace_errors(decision_trace)
    if trace_errors:
        raise PatchRejected(trace_errors)
    contract_trace_errors = scheduler_action_contract_trace_errors(
        decision_trace, required=True
    )
    if contract_trace_errors:
        raise PatchRejected(contract_trace_errors)
    action_hash = str(op.get("dispatched_action_hash") or "")
    if (
        len(action_hash) != 64
        or any(character not in "0123456789abcdef" for character in action_hash)
        or str(decision_trace.get("dispatched_action_sha256") or "") != action_hash
    ):
        raise PatchRejected(
            ["scheduler dispatch action hash disagrees with its decision trace"]
        )
    if position == 0:
        prior_primary_row = conn.execute(
            "SELECT d.decision_trace_json FROM scheduler_source_entries AS s "
            "JOIN scheduler_dispatches AS d ON d.dispatch_id = s.record_id "
            "WHERE s.record_kind = 'dispatch' AND d.dispatch_position = 0 "
            "ORDER BY s.sequence DESC LIMIT 1"
        ).fetchone()
        if prior_primary_row is not None:
            prior_primary_trace = json_loads(
                prior_primary_row["decision_trace_json"], None
            )
            prior_primary_certificate = (
                prior_primary_trace.get("randomized_assignment")
                if isinstance(prior_primary_trace, Mapping)
                else None
            )
            if (
                isinstance(prior_primary_certificate, Mapping)
                and prior_primary_certificate.get("protocol_version")
                in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
            ):
                current_primary_certificate = decision_trace.get(
                    "randomized_assignment"
                )
                if (
                    selection_design != "randomized"
                    or not isinstance(current_primary_certificate, Mapping)
                    or current_primary_certificate.get("protocol_version")
                    not in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
                    or current_primary_certificate.get(
                        "assignment_input_sha256"
                    )
                    != prior_primary_certificate.get(
                        "assignment_input_sha256"
                    )
                ):
                    raise PatchRejected(
                        [
                            "an active workflow randomized assignment must govern "
                            "every subsequent dispatch wave"
                        ]
                    )
    if selection_design == "randomized":
        assignment_wave = decision_trace.get("parallel_wave_admission")
        assignment_errors = randomized_assignment_errors(
            decision_trace.get("randomized_assignment"),
            candidate_set_sha256=candidate_set_hash,
            selection_policy_version=policy_version,
            dispatched_action_sha256=action_hash,
            parallel_admission_policy_version=(
                assignment_wave.get("policy_version")
                if isinstance(assignment_wave, Mapping)
                and type(assignment_wave.get("policy_version")) is int
                else None
            ),
        )
        if assignment_errors:
            raise PatchRejected(assignment_errors)
        try:
            assignment_metadata = randomized_assignment_metadata(
                decision_trace
            )
        except ValueError as exc:
            raise PatchRejected([str(exc)]) from exc
        if (
            assignment_metadata["candidate_set_hash"] != candidate_set_hash
            or assignment_metadata["selection_policy_version"] != policy_version
        ):
            raise PatchRejected(
                ["randomized scheduler dispatch metadata is inconsistent"]
            )
        current_certificate = decision_trace["randomized_assignment"]
        group_row = conn.execute(
            "SELECT decision_trace_json FROM scheduler_dispatches "
            "WHERE dispatch_group_id = ? AND selection_design = 'randomized' "
            "ORDER BY dispatch_position LIMIT 1",
            (group_id,),
        ).fetchone()
        if group_row is not None:
            group_trace = json_loads(group_row["decision_trace_json"], None)
            group_certificate = (
                group_trace.get("randomized_assignment")
                if isinstance(group_trace, Mapping)
                else None
            )
            if not isinstance(group_certificate, Mapping):
                raise PatchRejected(
                    ["randomized scheduler dispatch group has invalid provenance"]
                )
            for field in (
                "protocol_version",
                "experiment_id",
                "assignment_unit_id",
                "assignment_scope",
                "exposure_index",
                "assignment_input_sha256",
                "selected_arm_id",
                "selected_policy_version",
            ):
                if group_certificate.get(field) != current_certificate.get(field):
                    raise PatchRejected(
                        [
                            "randomized scheduler dispatch group contains "
                            "inconsistent assignment certificates"
                        ]
                    )
            if position == 0:
                raise PatchRejected(
                    ["randomized scheduler dispatch group has multiple primary actions"]
                )
        else:
            if position != 0:
                raise PatchRejected(
                    [
                        "randomized scheduler dispatch companions require their "
                        "primary action to be committed first"
                    ]
                )
            experiment_id = str(current_certificate["experiment_id"])
            assignment_unit_id = str(
                current_certificate["assignment_unit_id"]
            )
            prior_unit_row = conn.execute(
                "SELECT decision_trace_json FROM scheduler_dispatches "
                "WHERE selection_design = 'randomized' AND dispatch_position = 0 "
                "AND json_extract(decision_trace_json, "
                "'$.randomized_assignment.experiment_id') = ? "
                "AND json_extract(decision_trace_json, "
                "'$.randomized_assignment.assignment_unit_id') = ? "
                "ORDER BY COALESCE(json_extract(decision_trace_json, "
                "'$.randomized_assignment.exposure_index'), -1) DESC LIMIT 1",
                (experiment_id, assignment_unit_id),
            ).fetchone()
            current_protocol_version = int(
                current_certificate["protocol_version"]
            )
            if prior_unit_row is None:
                if (
                    current_protocol_version
                    in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
                    and current_certificate["exposure_index"] != 0
                ):
                    raise PatchRejected(
                        [
                            "workflow randomized assignment exposures must begin "
                            "at index zero"
                        ]
                    )
            else:
                prior_unit_trace = json_loads(
                    prior_unit_row["decision_trace_json"], None
                )
                prior_unit_certificate = (
                    prior_unit_trace.get("randomized_assignment")
                    if isinstance(prior_unit_trace, Mapping)
                    else None
                )
                if (
                    current_protocol_version
                    not in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
                ):
                    raise PatchRejected(
                        [
                            "randomized assignment unit is duplicated within "
                            f"experiment {experiment_id}: {assignment_unit_id}"
                        ]
                    )
                if (
                    not isinstance(prior_unit_certificate, Mapping)
                    or prior_unit_certificate.get("protocol_version")
                    not in WORKFLOW_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSIONS
                    or prior_unit_certificate.get("assignment_input_sha256")
                    != current_certificate.get("assignment_input_sha256")
                    or prior_unit_certificate.get("selected_arm_id")
                    != current_certificate.get("selected_arm_id")
                    or prior_unit_certificate.get("selected_policy_version")
                    != current_certificate.get("selected_policy_version")
                ):
                    raise PatchRejected(
                        [
                            "workflow randomized assignment changes within "
                            f"experimental unit {experiment_id}: {assignment_unit_id}"
                        ]
                    )
                prior_exposure_index = prior_unit_certificate.get(
                    "exposure_index"
                )
                if (
                    type(prior_exposure_index) is not int
                    or current_certificate["exposure_index"]
                    != prior_exposure_index + 1
                ):
                    raise PatchRejected(
                        [
                            "workflow randomized assignment exposure index must "
                            "be the next contiguous value"
                        ]
                    )
            prior_experiment = conn.execute(
                "SELECT decision_trace_json FROM scheduler_dispatches "
                "WHERE selection_design = 'randomized' AND dispatch_position = 0 "
                "AND json_extract(decision_trace_json, "
                "'$.randomized_assignment.experiment_id') = ? LIMIT 1",
                (experiment_id,),
            ).fetchone()
            if prior_experiment is not None:
                prior_trace = json_loads(
                    prior_experiment["decision_trace_json"], None
                )
                prior_certificate = (
                    prior_trace.get("randomized_assignment")
                    if isinstance(prior_trace, Mapping)
                    else None
                )
                try:
                    prior_design = randomized_assignment_design_sha256(
                        prior_certificate
                    )
                    current_design = randomized_assignment_design_sha256(
                        current_certificate
                    )
                except ValueError as exc:
                    raise PatchRejected(
                        [
                            "randomized scheduler experiment has invalid prior "
                            f"provenance: {exc}"
                        ]
                    ) from exc
                if prior_design != current_design:
                    raise PatchRejected(
                        [
                            "randomized assignment design changes within "
                            f"experiment {experiment_id}"
                        ]
                    )
    elif decision_trace.get("randomized_assignment") is not None:
        raise PatchRejected(
            ["deterministic scheduler dispatch cannot contain randomized assignment"]
        )
    dispatched_action = op.get("dispatched_action")
    if not isinstance(dispatched_action, Mapping):
        raise PatchRejected(
            ["scheduler dispatch requires a recoverable action object"]
        )
    if "decision_trace" in dispatched_action:
        raise PatchRejected(
            ["scheduler dispatch action body must exclude its decision trace"]
        )
    routing_errors = scheduler_dispatch_action_errors(dispatched_action)
    if routing_errors:
        raise PatchRejected(routing_errors)
    try:
        observed_action_hash = action_sha256(dispatched_action)
        dispatched_action_json = json_dumps(dispatched_action)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PatchRejected(
            [f"scheduler dispatch action body is not canonical JSON: {exc}"]
        )
    if observed_action_hash != action_hash:
        raise PatchRejected(
            ["scheduler dispatch action body does not match its action hash"]
        )
    if (
        str(dispatched_action.get("mode") or "") != mode
        or str(dispatched_action.get("target_id") or "") != target_id
        or str(dispatched_action.get("route_id") or "")
        != str(op.get("route_id") or "")
    ):
        raise PatchRejected(
            ["scheduler dispatch action body disagrees with its routing fields"]
        )
    expected_actor_role = scheduler_actor_role_for_action(dispatched_action)
    if actor_role != expected_actor_role:
        raise PatchRejected(
            [
                "scheduler dispatch actor role disagrees with the versioned "
                "action contract"
            ]
        )
    allocation = dispatched_action["budget"]
    actual_remaining = int(state["remaining_token_budget"])
    actual_reserve = int(state["reserved_verification_budget"])
    if (
        int(allocation["remaining_token_budget"]) != actual_remaining
        or int(allocation["reserved_verification_budget"]) != actual_reserve
    ):
        raise PatchRejected(
            [
                "scheduler dispatch resource allocation disagrees with the "
                "authenticated planning state"
            ]
        )
    group_actions: list[Mapping[str, Any]] = []
    for row in conn.execute(
        "SELECT dispatched_action_json FROM scheduler_dispatches "
        "WHERE dispatch_group_id = ? ORDER BY dispatch_position",
        (group_id,),
    ).fetchall():
        prior_action = json_loads(row["dispatched_action_json"], None)
        if not isinstance(prior_action, Mapping):
            raise PatchRejected(
                ["scheduler dispatch group contains an invalid action body"]
            )
        group_actions.append(prior_action)
    group_actions.append(dispatched_action)
    total_requested = 0
    nonverification_requested = 0
    for group_action in group_actions:
        group_allocation = group_action.get("budget")
        if not isinstance(group_allocation, Mapping):
            raise PatchRejected(
                ["scheduler dispatch group contains an invalid resource allocation"]
            )
        requested = int(group_allocation.get("requested_tokens") or 0)
        total_requested += requested
        if scheduler_budget_class_for_action(group_action) != "verification":
            nonverification_requested += requested
    if total_requested > actual_remaining:
        raise PatchRejected(
            [
                "scheduler dispatch group requests more than the remaining "
                "resource allocation"
            ]
        )
    if nonverification_requested > max(0, actual_remaining - actual_reserve):
        raise PatchRejected(
            [
                "scheduler dispatch group assigns protected verification "
                "resources to non-verification work"
            ]
        )
    execution_contract = op.get("execution_contract")
    if not isinstance(execution_contract, Mapping):
        raise PatchRejected(
            ["scheduler dispatch requires an execution recovery contract"]
        )
    try:
        execution_contract_json = json_dumps(execution_contract)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PatchRejected(
            [f"scheduler dispatch execution contract is not canonical JSON: {exc}"]
        )
    contract_errors = execution_contract_errors(execution_contract)
    if contract_errors:
        raise PatchRejected(
            [
                "scheduler dispatch execution contract is invalid: "
                + "; ".join(contract_errors)
            ]
        )
    if decision_trace_is_parallel_companion(decision_trace) != is_companion:
        raise PatchRejected(
            ["scheduler dispatch companion flag disagrees with its decision trace"]
        )
    wave = decision_trace.get("parallel_wave_admission")
    if (
        isinstance(wave, Mapping)
        and int(wave.get("policy_version") or 0) >= 4
        and wave.get("state_revision") != state_revision
    ):
        raise PatchRejected(
            ["scheduler dispatch state revision disagrees with its parallel wave"]
        )
    conn.execute(
        "INSERT INTO scheduler_dispatches("
        "dispatch_id, dispatch_group_id, dispatch_position, is_companion, "
        "actor_role, mode, target_id, route_id, decision_state_revision, "
        "proof_state_hash, prior_run_provenance_hash, selection_design, "
        "candidate_set_hash, selection_policy_version, decision_trace_json, "
        "dispatched_action_hash, dispatched_action_json, execution_contract_json, "
        "committed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            dispatch_id,
            group_id,
            position,
            int(is_companion),
            actor_role,
            mode,
            target_id,
            str(op.get("route_id") or ""),
            state_revision,
            str(op.get("proof_state_hash") or ""),
            str(op.get("prior_run_provenance_hash") or ""),
            selection_design,
            candidate_set_hash,
            policy_version,
            json_dumps(decision_trace),
            action_hash,
            dispatched_action_json,
            execution_contract_json,
            committed_at,
        ),
    )
    _update_scheduler_fairness_state(
        conn,
        decision_trace=decision_trace,
        dispatch_id=dispatch_id,
        selection_design=selection_design,
    )
    _update_scheduler_decision_fairness_state(
        conn,
        decision_trace=decision_trace,
        dispatch_id=dispatch_id,
        selection_design=selection_design,
        state_revision=state_revision,
    )
    append_scheduler_provenance_entry(
        conn,
        record_kind="dispatch",
        record_id=dispatch_id,
    )


def _record_run(
    conn: sqlite3.Connection,
    op: Dict[str, Any],
    *,
    problem_id: str = "",
    authority: PatchAuthority,
) -> None:
    if authority.source != "system":
        raise PatchRejected(["run telemetry requires system authority"])
    run_id = _required(op, "run_id")
    mode = _required(op, "mode")
    if mode not in EXECUTABLE_RUN_MODES:
        raise PatchRejected([f"invalid executable run mode: {mode}"])
    if conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone():
        raise PatchRejected([f"run telemetry is append-only; duplicate run_id: {run_id}"])
    selection_design = str(op.get("selection_design") or "observational")
    state_revision = op.get("state_revision", 0)
    context_revision = op.get("context_revision", 0)
    decision_state_revision = op.get("decision_state_revision", state_revision)
    if type(state_revision) is not int or state_revision < 0:
        raise PatchRejected(["run state_revision must be a nonnegative integer"])
    if type(context_revision) is not int or context_revision < 0:
        raise PatchRejected(["run context_revision must be a nonnegative integer"])
    if type(decision_state_revision) is not int or decision_state_revision < 0:
        raise PatchRejected(
            ["run decision_state_revision must be a nonnegative integer"]
        )
    raw_assignment_probability = op.get("assignment_probability") or 0.0
    if isinstance(raw_assignment_probability, bool):
        raise PatchRejected(["run assignment_probability must be finite numeric data"])
    try:
        assignment_probability = float(raw_assignment_probability)
    except (TypeError, ValueError, OverflowError):
        raise PatchRejected(
            ["run assignment_probability must be finite numeric data"]
        )
    if not math.isfinite(assignment_probability):
        raise PatchRejected(["run assignment_probability must be finite numeric data"])
    exploration_stratum = str(op.get("exploration_stratum") or "")
    candidate_set_hash = str(op.get("candidate_set_hash") or "")
    selection_policy_version = int(op.get("selection_policy_version") or 0)
    decision_trace = op.get("decision_trace") or {}
    if not isinstance(decision_trace, Mapping):
        raise PatchRejected(["decision_trace must be an object"])
    if selection_design not in {"observational", "deterministic", "randomized"}:
        raise PatchRejected([f"invalid selection_design: {selection_design}"])
    if selection_design == "observational":
        if (
            assignment_probability != 0.0
            or exploration_stratum
            or candidate_set_hash
            or selection_policy_version != 0
        ):
            raise PatchRejected(
                ["observational run telemetry cannot claim randomized-assignment metadata"]
            )
    elif selection_design in {"deterministic", "randomized"}:
        if (
            len(candidate_set_hash) != 64
            or any(character not in "0123456789abcdef" for character in candidate_set_hash)
            or selection_policy_version < 1
            or not decision_trace
        ):
            raise PatchRejected(
                [
                    f"{selection_design} run telemetry requires a lowercase SHA-256 "
                    "candidate-set hash, a positive policy version, and a decision trace"
                ]
            )
        raw_trace_policy_version = decision_trace.get("decision_policy_version")
        try:
            trace_policy_version = int(raw_trace_policy_version or 0)
        except (TypeError, ValueError, OverflowError):
            raise PatchRejected(["decision trace policy version must be an integer"])
        if (
            str(decision_trace.get("candidate_set_sha256") or "") != candidate_set_hash
            or trace_policy_version != selection_policy_version
        ):
            raise PatchRejected(
                ["deterministic run provenance disagrees with its decision trace"]
            )
        trace_candidates = decision_trace.get("candidates")
        if not isinstance(trace_candidates, list) or any(
            not isinstance(row, Mapping) for row in trace_candidates
        ):
            raise PatchRejected(
                ["deterministic decision trace candidates must be a list of objects"]
            )
        if candidate_rows_sha256(
            trace_candidates,
            decision_policy_version=trace_policy_version,
        ) != candidate_set_hash:
            raise PatchRejected(
                ["deterministic candidate-set hash does not match the trace candidates"]
            )
        trace_errors = decision_trace_errors(decision_trace)
        if trace_errors:
            raise PatchRejected(trace_errors)
        contract_trace_errors = scheduler_action_contract_trace_errors(
            decision_trace, required=True
        )
        if contract_trace_errors:
            raise PatchRejected(contract_trace_errors)
        wave = decision_trace.get("parallel_wave_admission")
        if (
            isinstance(wave, Mapping)
            and int(wave.get("policy_version") or 0) >= 4
            and wave.get("state_revision") != decision_state_revision
        ):
            raise PatchRejected(
                [
                    "run decision state revision disagrees with its parallel "
                    "wave snapshot"
                ]
            )
        if selection_design == "deterministic":
            if assignment_probability != 0.0 or exploration_stratum:
                raise PatchRejected(
                    [
                        "deterministic run telemetry requires zero assignment "
                        "probability and no exploration stratum"
                    ]
                )
            if decision_trace.get("randomized_assignment") is not None:
                raise PatchRejected(
                    ["deterministic run telemetry cannot contain randomized assignment"]
                )
        else:
            assignment_wave = decision_trace.get("parallel_wave_admission")
            assignment_errors = randomized_assignment_errors(
                decision_trace.get("randomized_assignment"),
                candidate_set_sha256=candidate_set_hash,
                selection_policy_version=selection_policy_version,
                assignment_probability=assignment_probability,
                exploration_stratum=exploration_stratum,
                dispatched_action_sha256=str(
                    decision_trace.get("dispatched_action_sha256") or ""
                ),
                parallel_admission_policy_version=(
                    assignment_wave.get("policy_version")
                    if isinstance(assignment_wave, Mapping)
                    and type(assignment_wave.get("policy_version")) is int
                    else None
                ),
            )
            if assignment_errors:
                raise PatchRejected(assignment_errors)
            try:
                assignment_metadata = randomized_assignment_metadata(
                    decision_trace
                )
            except ValueError as exc:
                raise PatchRejected([str(exc)]) from exc
            if (
                assignment_metadata["assignment_probability"]
                != assignment_probability
                or assignment_metadata["exploration_stratum"]
                != exploration_stratum
                or assignment_metadata["candidate_set_hash"]
                != candidate_set_hash
                or assignment_metadata["selection_policy_version"]
                != selection_policy_version
            ):
                raise PatchRejected(
                    ["randomized run telemetry metadata is inconsistent"]
                )
    scheduler_dispatch_id = str(op.get("scheduler_dispatch_id") or "")
    dispatched_action_hash = str(op.get("dispatched_action_hash") or "")
    if selection_design in {"deterministic", "randomized"} and not scheduler_dispatch_id:
        raise PatchRejected(
            [
                f"new {selection_design} run telemetry requires a prior durable "
                "scheduler dispatch"
            ]
        )
    result_reserving_run_id = conn.execute(
        "SELECT dispatch_id FROM scheduler_dispatch_results WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if result_reserving_run_id is not None and str(
        result_reserving_run_id["dispatch_id"] or ""
    ) != scheduler_dispatch_id:
        raise PatchRejected(
            [
                "run_id is reserved by a different durable scheduler result: "
                f"{run_id}"
            ]
        )
    reserved_result = None
    if scheduler_dispatch_id:
        reserved_result = conn.execute(
            "SELECT run_id, session_plan_json, execution_json, "
            "validation_errors_json "
            "FROM scheduler_dispatch_results WHERE dispatch_id = ?",
            (scheduler_dispatch_id,),
        ).fetchone()
    if reserved_result is not None and str(
        reserved_result["run_id"] or ""
    ) != run_id:
        raise PatchRejected(
            [
                "run telemetry run_id disagrees with its durable scheduler "
                "result"
            ]
        )
    if scheduler_dispatch_id:
        dispatch = conn.execute(
            "SELECT * FROM scheduler_dispatches WHERE dispatch_id = ?",
            (scheduler_dispatch_id,),
        ).fetchone()
        if dispatch is None:
            raise PatchRejected(
                ["run telemetry references a missing scheduler dispatch"]
            )
        dispatch_trace = json_loads(dispatch["decision_trace_json"], None)
        if (
            not dispatched_action_hash
            or dispatch_trace != dict(decision_trace)
            or dispatched_action_hash
            != str(dispatch["dispatched_action_hash"] or "")
            or selection_design != str(dispatch["selection_design"] or "")
            or candidate_set_hash != str(dispatch["candidate_set_hash"] or "")
            or selection_policy_version
            != int(dispatch["selection_policy_version"] or 0)
            or decision_state_revision
            != int(dispatch["decision_state_revision"] or 0)
            or mode != str(dispatch["mode"] or "")
            or str(op.get("target_id") or "")
            != str(dispatch["target_id"] or "")
            or str(op.get("route_id") or "")
            != str(dispatch["route_id"] or "")
            or str(op.get("actor_role") or "")
            != str(dispatch["actor_role"] or "")
        ):
            raise PatchRejected(
                ["run telemetry disagrees with its scheduler dispatch"]
            )
        dispatched_action = json_loads(dispatch["dispatched_action_json"], None)
        if not isinstance(dispatched_action, Mapping):
            raise PatchRejected(
                ["run telemetry scheduler dispatch has no recoverable action"]
            )
        dispatched_allocation = dispatched_action.get("budget")
        budget_requested = op.get("budget_requested")
        if (
            not isinstance(dispatched_allocation, Mapping)
            or isinstance(budget_requested, bool)
            or not isinstance(budget_requested, int)
            or budget_requested < 0
            or budget_requested
            != dispatched_allocation.get("requested_tokens")
        ):
            raise PatchRejected(
                [
                    "run telemetry requested allocation disagrees with its "
                    "scheduler dispatch"
                ]
            )
        for field in ("researcher_work_mode", "work_mode_source"):
            if str(op.get(field) or "") != str(
                dispatched_action.get(field) or ""
            ):
                raise PatchRejected(
                    [
                        f"run telemetry {field} disagrees with its scheduler "
                        "dispatch"
                    ]
                )
        action_search_intent = str(
            dispatched_action.get("search_intent") or ""
        )
        if action_search_intent and str(op.get("search_intent") or "") != (
            action_search_intent
        ):
            raise PatchRejected(
                [
                    "run telemetry search intent disagrees with its scheduler "
                    "dispatch"
                ]
            )
        if reserved_result is None:
            raise PatchRejected(
                [
                    "run telemetry requires a prior durable scheduler result "
                    "for its dispatch"
                ]
            )
        result_plan = json_loads(reserved_result["session_plan_json"], None)
        result_execution = json_loads(
            reserved_result["execution_json"], None
        )
        result_validation_errors = json_loads(
            reserved_result["validation_errors_json"], None
        )
        if not isinstance(result_plan, Mapping) or not isinstance(
            result_execution, Mapping
        ) or not isinstance(result_validation_errors, list) or not all(
            isinstance(error, str) for error in result_validation_errors
        ):
            raise PatchRejected(
                ["run telemetry has a malformed durable scheduler result"]
            )
        expected_usage = parse_token_usage(result_execution.get("usage"))
        # ``run_metrics_operation`` deliberately treats a provider's
        # total-only usage footer as input usage.  Authenticate against
        # that same conservative normalization rather than the less
        # informative raw representation.
        if (
            expected_usage["total_tokens"]
            and not expected_usage["input_tokens"]
            and not expected_usage["output_tokens"]
        ):
            expected_usage["input_tokens"] = expected_usage[
                "total_tokens"
            ]
        for field, expected_value in expected_usage.items():
            observed_value = op.get(field)
            if (
                isinstance(observed_value, bool)
                or not isinstance(observed_value, int)
                or observed_value != expected_value
            ):
                raise PatchRejected(
                    [
                        f"run telemetry {field} disagrees with its durable "
                        "scheduler result"
                    ]
                )
        for field in ("wall_time_seconds", "peak_memory_mb"):
            if isinstance(op.get(field), bool):
                raise PatchRejected(
                    [f"run telemetry {field} is not finite numeric data"]
                )
            try:
                observed_value = float(op.get(field) or 0.0)
                expected_value = float(result_execution.get(field) or 0.0)
            except (TypeError, ValueError, OverflowError):
                raise PatchRejected(
                    [f"run telemetry {field} is not finite numeric data"]
                )
            if not math.isfinite(observed_value) or not math.isclose(
                observed_value,
                expected_value,
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise PatchRejected(
                    [
                        f"run telemetry {field} disagrees with its durable "
                        "scheduler result"
                    ]
                )
        execution_contract = json_loads(
            dispatch["execution_contract_json"], None
        )
        if not isinstance(execution_contract, Mapping):
            raise PatchRejected(
                ["run telemetry scheduler execution contract is malformed"]
            )
        expected_text_fields = {
            "session_id": result_execution.get("session_id", ""),
            "model_profile": result_plan.get("model_profile", "default"),
            "model": result_execution.get("model")
            or execution_contract.get("model", ""),
            "reasoning_effort": result_execution.get("reasoning_effort")
            or execution_contract.get("reasoning_effort", ""),
            "sandbox_setting": result_execution.get("sandbox")
            or execution_contract.get("sandbox", ""),
            "search_setting": result_execution.get("web_search")
            or result_plan.get("web_search")
            or "disabled",
            "prompt_context_hash": result_plan.get("context_hash", ""),
            "search_intent": result_plan.get("search_intent", ""),
            "strategy_family": result_plan.get("strategy_family", ""),
            "failure_kind": result_execution.get("failure_kind", ""),
        }
        for field, expected_value in expected_text_fields.items():
            if str(op.get(field) or "") != str(expected_value or ""):
                raise PatchRejected(
                    [
                        f"run telemetry {field} disagrees with its durable "
                        "scheduler result"
                    ]
                )
        result_patch = result_execution.get("patch")
        patch_accepted = False
        if not result_validation_errors and isinstance(result_patch, Mapping):
            result_patch_id = str(result_patch.get("patch_id") or "")
            patch_row = conn.execute(
                "SELECT status FROM patches WHERE patch_id = ?",
                (result_patch_id,),
            ).fetchone()
            patch_accepted = bool(
                patch_row is not None
                and str(patch_row["status"] or "") == "applied"
            )
        expected_status = str(result_execution.get("status") or "completed")
        if not patch_accepted and expected_status not in {
            "failed",
            "timeout",
            "no_patch",
            "cancelled",
            "blocked",
        }:
            expected_status = "patch_rejected"
        if str(op.get("status") or "completed") != expected_status:
            raise PatchRejected(
                [
                    "run telemetry status disagrees with its durable scheduler "
                    "result and patch outcome"
                ]
            )

        expected_output_ids: list[str] = []
        if patch_accepted and isinstance(result_patch, Mapping):
            for operation in result_patch.get("operations", []):
                if not isinstance(operation, Mapping):
                    continue
                operation_kind = next(
                    (
                        str(operation.get(key))
                        for key in (
                            "op",
                            "operation_type",
                            "operation",
                            "operation_name",
                            "type",
                        )
                        if isinstance(operation.get(key), str)
                        and operation.get(key)
                    ),
                    "",
                )
                if operation_kind not in {"attach_artifact", "add_artifact"}:
                    continue
                artifact = operation.get("artifact")
                artifact_id = (
                    artifact.get("artifact_id")
                    if isinstance(artifact, Mapping)
                    else operation.get("artifact_id")
                )
                if isinstance(artifact_id, str):
                    expected_output_ids.append(artifact_id)
        if op.get("output_artifact_ids", []) != expected_output_ids:
            raise PatchRejected(
                [
                    "run telemetry output artifact identifiers disagree with "
                    "its durable scheduler result"
                ]
            )
        if state_revision != context_revision:
            raise PatchRejected(
                ["dispatched run state and context revisions must agree"]
            )
        if context_revision <= decision_state_revision:
            raise PatchRejected(
                [
                    "dispatched run context must include the durable dispatch "
                    "revision"
                ]
            )
    elif dispatched_action_hash:
        raise PatchRejected(
            ["run action hash requires a scheduler dispatch identifier"]
        )
    spent = run_spend_from_operation(op)
    budget_overrun = 0
    new_remaining: int | None = None
    if spent:
        if problem_id:
            row = conn.execute(
                "SELECT remaining_token_budget, reserved_verification_budget "
                "FROM problem_state WHERE problem_id = ?",
                (problem_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT remaining_token_budget, reserved_verification_budget "
                "FROM problem_state"
            ).fetchone()
        remaining = int(row["remaining_token_budget"]) if row else 0
        reserve = int(row["reserved_verification_budget"]) if row else 0
        requested = max(0, int(op.get("budget_requested", 0)))
        if run_may_use_verification_reserve(op):
            new_remaining = max(0, remaining - spent)
            reserve_overrun = 0
        else:
            spendable = max(0, remaining - reserve)
            new_remaining = max(reserve, remaining - min(spent, spendable))
            reserve_overrun = max(0, spent - spendable)
        budget_overrun = max(
            reserve_overrun,
            max(0, spent - requested) if requested else 0,
        )
    conn.execute(
        """
        INSERT INTO runs(
            run_id, actor_role, mode, target_id, route_id, state_revision, context_revision,
            session_id, model_profile, model, reasoning_effort, search_setting,
            search_intent, strategy_family, researcher_work_mode, work_mode_source, failure_kind,
            selection_design, assignment_probability, exploration_stratum,
            candidate_set_hash, selection_policy_version,
            decision_trace_json,
            sandbox_setting, budget_requested, input_tokens, cached_input_tokens,
            output_tokens, reasoning_output_tokens, total_tokens, wall_time_seconds,
            peak_memory_mb, status,
            prompt_context_hash, output_artifact_ids_json, error_artifact_id, created_at,
            decision_state_revision, scheduler_dispatch_id, dispatched_action_hash,
            budget_overrun_tokens
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            op.get("actor_role", ""),
            mode,
            op.get("target_id", ""),
            op.get("route_id", ""),
            state_revision,
            context_revision,
            op.get("session_id", ""),
            op.get("model_profile", "standard"),
            op.get("model", ""),
            op.get("reasoning_effort", ""),
            op.get("search_setting", "disabled"),
            op.get("search_intent", ""),
            op.get("strategy_family", "unclassified"),
            op.get("researcher_work_mode", ""),
            op.get("work_mode_source", ""),
            op.get("failure_kind", ""),
            selection_design,
            assignment_probability,
            exploration_stratum,
            candidate_set_hash,
            selection_policy_version,
            json_dumps(decision_trace),
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
            str(op.get("created_at") or utc_now()),
            decision_state_revision,
            scheduler_dispatch_id or None,
            dispatched_action_hash,
            budget_overrun,
        ),
    )
    if not scheduler_dispatch_id:
        # Direct/legacy telemetry still advances fairness.  Normal workflow
        # executions cite a prior dispatch and cannot apply it twice.
        _update_scheduler_fairness_state(
            conn,
            decision_trace=decision_trace,
            run_id=run_id,
            selection_design=selection_design,
        )
        _update_scheduler_decision_fairness_state(
            conn,
            decision_trace=decision_trace,
            run_id=run_id,
            selection_design=selection_design,
            state_revision=decision_state_revision,
        )
    append_scheduler_provenance_entry(
        conn,
        record_kind="run",
        record_id=run_id,
    )
    if spent and new_remaining is not None:
        if problem_id:
            conn.execute(
                "UPDATE problem_state SET remaining_token_budget = ?, updated_at = ? WHERE problem_id = ?",
                (new_remaining, utc_now(), problem_id),
            )
        else:
            conn.execute(
                "UPDATE problem_state SET remaining_token_budget = ?, updated_at = ?",
                (new_remaining, utc_now()),
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

    relation = op.get("relation_to_parent")
    if relation is not None and relation not in ROUTE_RELATIONS:
        raise PatchRejected([f"invalid route relation: {relation}"])

    strategy = op.get("strategy")
    if isinstance(strategy, str) and strategy.strip() and strategy != row["strategy"]:
        existing_routes = [
            dict(existing)
            for existing in conn.execute(
                "SELECT route_id, conclusion_claim_id, relation_to_parent, strategy FROM routes WHERE conclusion_claim_id = ? AND route_id != ?",
                (row["conclusion_claim_id"], route_id),
            ).fetchall()
        ]
        duplicate_route = obvious_duplicate_route_id(
            existing_routes,
            conclusion_claim_id=row["conclusion_claim_id"],
            relation_to_parent=relation or row["relation_to_parent"],
            strategy=strategy,
        )
        if duplicate_route:
            raise PatchRejected([f"duplicate route strategy matches existing route {duplicate_route}; reuse or repair that route"])

    evidence_ids = sorted(set(json_loads(row["evidence_artifact_ids_json"]) + list(op.get("evidence_artifact_ids", []))))
    new_failure_fingerprint = str(op.get("failure_fingerprint") or row["failure_fingerprint"] or "")
    conn.execute(
        """
        UPDATE routes
        SET status = COALESCE(?, status),
            label = COALESCE(?, label),
            strategy = COALESCE(?, strategy),
            relation_to_parent = COALESCE(?, relation_to_parent),
            failure_fingerprint = ?,
            evidence_artifact_ids_json = ?,
            updated_at = ?
        WHERE route_id = ?
        """,
        (
            status,
            op.get("label"),
            strategy,
            relation,
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
    if artifact_type in {
        "final_proof",
        "final_paper",
        "human_readable_mathematical_text",
        REVISION_DOCUMENT_ARTIFACT_TYPE,
    }:
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
    critical_errors = [*_string_list(compact.get("critical_errors")), *_string_list(report.get("critical_errors"))]
    gaps = [*_string_list(compact.get("gaps")), *_string_list(report.get("gaps"))]
    compact_report = {
        "summary": _compact_text(report.get("summary", compact.get("summary", "")), 900),
        "checked_items": _compact_list(report.get("checked_items", []), item_chars=160, max_items=12),
        "critical_errors": _compact_list(critical_errors, item_chars=500, max_items=8),
        "gaps": _compact_list(gaps, item_chars=500, max_items=8),
    }
    if report.get("verdict"):
        compact_report["verdict"] = str(report["verdict"])
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


def _write_artifact_content(
    store: ProofStateStore,
    artifact_id: str,
    artifact_type: str,
    content: str,
    *,
    artifact_files: _ArtifactFileJournal,
    metadata: Optional[Mapping[str, Any]] = None,
) -> str:
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
    if artifact_type == REVISION_DOCUMENT_ARTIFACT_TYPE:
        document_format = str((metadata or {}).get("document_format") or "").strip().lower()
        suffix = ".tex" if document_format == "tex" else ".md"
    elif artifact_type in {"audit_subject", "reference_solution"}:
        source_format = str(
            (metadata or {}).get("format")
            or (metadata or {}).get("stored_format")
            or ""
        ).strip().lower()
        suffix = f".{source_format}" if source_format in {"md", "tex", "txt"} else ".md"
    else:
        suffix = ARTIFACT_CONTENT_EXTENSIONS.get(
            artifact_type, ".md" if artifact_type in markdown_types else ".txt"
        )
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", artifact_id).strip("._") or "artifact"
    artifact_dir = store.state_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{safe_id}{suffix}"
    artifact_files.write_text(path, content)
    return str(path)


def _copy_artifact_file(
    store: ProofStateStore,
    artifact_id: str,
    artifact_type: str,
    source_path: Path,
    *,
    artifact_files: _ArtifactFileJournal,
    expected_sha256: str = "",
    expected_size: Optional[int] = None,
) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", artifact_id).strip("._") or "artifact"
    suffix = ARTIFACT_CONTENT_EXTENSIONS.get(artifact_type) or source_path.suffix or ".txt"
    destination = store.state_dir / "artifacts" / f"{safe_id}{suffix}"
    if source_path.resolve() != destination.resolve():
        artifact_files.copy_stable_file(
            destination,
            source_path,
            max_bytes=MAX_COPIED_ARTIFACT_BYTES,
            expected_sha256=expected_sha256,
            expected_size=expected_size,
        )
    else:
        try:
            source_sha256, source_size = stable_file_sha256_size(
                source_path,
                max_bytes=MAX_COPIED_ARTIFACT_BYTES,
                label="artifact source",
            )
        except ValueError as exc:
            raise PatchRejected(
                [str(exc)]
            ) from exc
        if expected_size is not None and source_size != expected_size:
            raise PatchRejected(
                [
                    "artifact source size changed since result persistence: "
                    f"{source_path}"
                ]
            )
        if expected_sha256 and source_sha256 != expected_sha256:
            raise PatchRejected(
                [
                    "artifact source content changed since result persistence: "
                    f"{source_path}"
                ]
            )
    return destination.resolve()


def _validated_artifact_path(
    store: ProofStateStore,
    raw_path: Any,
    *,
    allow_writer_context_staging: bool = False,
    artifact_id: str = "",
) -> str:
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
    except OSError:
        raise PatchRejected([f"artifact path cannot be resolved: {candidate}"])
    under_artifact_root = True
    try:
        resolved.relative_to(artifact_root)
    except ValueError:
        under_artifact_root = False
    if not under_artifact_root:
        context_root = (store.state_dir / "contexts").resolve()
        try:
            context_relative = resolved.relative_to(context_root)
        except ValueError:
            context_relative = None
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", artifact_id).strip("._") or "artifact"
        context_staging_is_safe = bool(
            allow_writer_context_staging
            and context_relative is not None
            and len(context_relative.parts) >= 2
            and resolved.stem == safe_id
        )
        if not context_staging_is_safe:
            raise PatchRejected(
                [
                    "artifact path must resolve under the proof-state artifacts directory, or for a path-based "
                    f"writer artifact use a matching <artifact_id> file under {context_root}"
                ]
            )
    if not resolved.is_file():
        raise PatchRejected([f"artifact path does not exist in an allowed proof-state staging directory: {resolved}"])
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
    if actor == REFEREE_ROLE and artifact_type not in REFEREE_ARTIFACT_TYPES:
        raise PatchRejected([
            f"referee cannot attach {artifact_type} artifact {artifact_id}; "
            "publication review may only attach referee_report artifacts"
        ])
    allowed = ARTIFACT_PRODUCER_ROLES.get(artifact_type)
    if allowed and actor not in allowed:
        expected = ", ".join(sorted(allowed))
        raise PatchRejected([f"{actor} cannot attach {artifact_type} artifact {artifact_id}; expected {expected}"])


def _has_valid_formal_backend_result(
    conn: sqlite3.Connection,
    evidence_ids: Sequence[str],
    *,
    target_type: str,
    target_id: str,
) -> bool:
    for artifact_id in evidence_ids:
        row = conn.execute(
            "SELECT artifact_type, producer_role, metadata_json FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if (
            row is None
            or str(row["artifact_type"] or "") != "formal_backend_result"
            or str(row["producer_role"] or "") != "formal_backend"
        ):
            continue
        metadata = json_loads(row["metadata_json"], {})
        host_check = metadata.get("host_formal_check") if isinstance(metadata, Mapping) else None
        if not isinstance(host_check, Mapping) or host_check.get("host_checked") is not True:
            continue
        target_binding = (
            metadata.get("host_formal_target_binding")
            if isinstance(metadata, Mapping)
            else None
        )
        if not isinstance(target_binding, Mapping):
            continue
        if (
            str(target_binding.get("target_type") or "") != target_type
            or str(target_binding.get("target_id") or "") != target_id
            or str(target_binding.get("subject_digest") or "")
            != entity_subject_digest(conn, target_type, target_id)
        ):
            continue
        if _artifact_is_bound_to_entity(
            conn,
            str(artifact_id),
            metadata,
            target_type=target_type,
            target_id=target_id,
        ):
            return True
    return False


def _has_artifact_type(
    conn: sqlite3.Connection,
    evidence_ids: Sequence[str],
    artifact_type: str,
    *,
    target_type: str,
    target_id: str,
    producer_role: Optional[str] = None,
) -> bool:
    for aid in evidence_ids:
        row = conn.execute(
            "SELECT artifact_type, producer_role, metadata_json FROM artifacts WHERE artifact_id = ?",
            (aid,),
        ).fetchone()
        if not row or row["artifact_type"] != artifact_type:
            continue
        if producer_role is not None and row["producer_role"] != producer_role:
            continue
        metadata = json_loads(row["metadata_json"], {})
        if not _artifact_is_bound_to_entity(conn, aid, metadata, target_type=target_type, target_id=target_id):
            continue
        return True
    return False


def _has_clean_verification(
    conn: sqlite3.Connection,
    evidence_ids: Sequence[str],
    *,
    outcome: str,
    target_type: str,
    target_id: str,
    producer_role: Optional[str] = None,
) -> bool:
    for aid in evidence_ids:
        row = conn.execute("SELECT artifact_type, producer_role, metadata_json FROM artifacts WHERE artifact_id = ?", (aid,)).fetchone()
        if not row or row["artifact_type"] != "verification_report":
            continue
        if producer_role is not None and row["producer_role"] != producer_role:
            continue
        metadata = json_loads(row["metadata_json"], {})
        if not _artifact_is_bound_to_entity(conn, aid, metadata, target_type=target_type, target_id=target_id):
            continue
        if clean_verification_metadata(metadata, outcome=outcome):
            return True
    return False


def _artifact_is_bound_to_entity(
    conn: sqlite3.Connection,
    artifact_id: str,
    metadata: Mapping[str, Any],
    *,
    target_type: str,
    target_id: str,
) -> bool:
    if artifact_has_current_binding(
        conn,
        artifact_id,
        entity_type=target_type,
        entity_id=target_id,
    ):
        return True
    artifact_row = conn.execute(
        "SELECT state_revision FROM artifacts WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()
    current_row = conn.execute("SELECT current_revision FROM problem_state").fetchone()
    is_new_in_current_patch = bool(
        artifact_row
        and current_row
        and int(artifact_row["state_revision"] or 0) == int(current_row["current_revision"] or 0) + 1
    )
    if not is_new_in_current_patch:
        return False
    declared_targets = evidence_targets(metadata)
    if declared_targets:
        return evidence_matches_target(metadata, target_type=target_type, target_id=target_id)
    table_info = {
        "claim": ("claims", "claim_id"),
        "inference": ("inferences", "inference_id"),
        "route": ("routes", "route_id"),
    }.get(target_type)
    if table_info is None:
        return False
    table, id_column = table_info
    row = conn.execute(
        f"SELECT evidence_artifact_ids_json FROM {table} WHERE {id_column} = ?",
        (target_id,),
    ).fetchone()
    return bool(row and artifact_id in json_loads(row["evidence_artifact_ids_json"], []))


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
        route_id = str(route["route_id"] or "")
        bound = evidence_matches_target(
            metadata,
            target_type="claim",
            target_id=claim_id,
            route_id=route_id,
        )
        if not bound:
            route_evidence = json_loads(route["evidence_artifact_ids_json"], [])
            bound = aid in route_evidence and _artifact_is_bound_to_entity(
                conn,
                aid,
                metadata,
                target_type="claim",
                target_id=claim_id,
            )
        if not bound:
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
        return ["integration_report evidence did not certify integrates=true for this exact claim and route"]
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
