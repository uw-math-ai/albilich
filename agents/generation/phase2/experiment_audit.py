from __future__ import annotations

import base64
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import stat
from statistics import NormalDist
from typing import Any, Dict, Mapping

from .audit_checkpoint import (
    canonical_signature_payload,
    public_key_der,
    verify_ed25519,
)
from .decision_policy import action_sha256, decision_trace_errors
from .parallel_admission import PARALLEL_POLICY_SEMANTIC_SHA256
from .randomized_assignment import (
    BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM,
    BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION,
    MAX_RANDOMIZED_BLOCK_SEED,
    randomized_assignment_errors,
    randomized_block_seed,
    randomized_block_assignment_cohort_errors,
    randomized_condition_order,
)


VALID_ARCHIVE_STATUSES = {"historical_unvalidated", "protocol_validated"}
SUPPORTED_PROTOCOL_VERSIONS = frozenset({3, 4, 5, 6})
REQUIRED_PROTOCOL_FIELDS = {
    "protocol_version",
    "problem_selection_rule",
    "problem_file",
    "problem_sha256",
    "prompt_files",
    "prompt_problem_file",
    "environment_file",
    "random_seed",
    "model",
    "stopping_rule",
    "run_log_file",
    "event_log_file",
    "proof_snapshot_file",
    "independent_grade_file",
    "scoreboard_file",
    "agent_visible_files",
    "reference_answer_files",
    "file_sha256",
    "evidence_scope",
}
VALID_EVIDENCE_SCOPES = {
    "case_study",
    "general_performance",
    "novelty_and_performance",
}
GENERAL_EVIDENCE_FILE_FIELDS = {
    "preregistration_file",
    "selection_rule_file",
    "analysis_plan_file",
    "assignment_schedule_file",
    "registration_receipt_file",
    "trial_manifest_file",
    "statistical_analysis_file",
    "grader_protocol_file",
    "rubric_file",
}
MAX_STRUCTURED_FILE_BYTES = 64 * 1024 * 1024
MAX_TEXT_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_COMBINED_TEXT_BYTES = 64 * 1024 * 1024
MAX_CHECKSUM_FILE_BYTES = 16 * 1024 * 1024
MAX_JSONL_LINE_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_LIST_ENTRIES = 100_000
MAX_BOOTSTRAP_DRAWS = 5_000_000
PAIRED_PROBLEM_POWER_METHOD = "normal_approximation_paired_problem_means_v1"
PAIRED_PROBLEM_POWER_FIELDS = frozenset(
    {
        "method",
        "analysis_unit",
        "alternative",
        "alpha",
        "desired_power",
        "minimum_detectable_effect",
        "assumed_problem_mean_difference_standard_deviation",
        "standard_deviation_basis",
        "required_problem_count",
    }
)
STANDARD_DEVIATION_BASES = frozenset(
    {
        "external_pilot",
        "mathematical_upper_bound",
        "preregistered_design_assumption",
    }
)


def paired_problem_power_required_count(
    *,
    alpha: Any,
    desired_power: Any,
    minimum_detectable_effect: Any,
    assumed_standard_deviation: Any,
) -> int:
    """Return the two-sided normal-approximation size for paired problem means."""

    raw_values = (
        alpha,
        desired_power,
        minimum_detectable_effect,
        assumed_standard_deviation,
    )
    if any(isinstance(value, bool) for value in raw_values):
        raise ValueError("power-analysis parameters must be finite real numbers")
    try:
        alpha_value = float(alpha)
        power_value = float(desired_power)
        effect_value = float(minimum_detectable_effect)
        standard_deviation_value = float(assumed_standard_deviation)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "power-analysis parameters must be finite real numbers"
        ) from exc
    if not all(
        math.isfinite(value)
        for value in (
            alpha_value,
            power_value,
            effect_value,
            standard_deviation_value,
        )
    ):
        raise ValueError("power-analysis parameters must be finite real numbers")
    if not 0.0 < alpha_value <= 0.10:
        raise ValueError("power-analysis alpha must lie in (0, 0.10]")
    if not 0.5 < power_value < 1.0:
        raise ValueError("power-analysis desired power must lie in (0.5, 1)")
    if not 0.0 < effect_value <= 1.0:
        raise ValueError(
            "power-analysis minimum detectable effect must lie in (0, 1]"
        )
    if not 0.0 < standard_deviation_value <= 1.0:
        raise ValueError(
            "power-analysis assumed standard deviation must lie in (0, 1]"
        )
    normal = NormalDist()
    critical_value = normal.inv_cdf(1.0 - alpha_value / 2.0)
    power_quantile = normal.inv_cdf(power_value)
    raw_count = (
        (critical_value + power_quantile)
        * standard_deviation_value
        / effect_value
    ) ** 2
    # Never subtract a floating-point tolerance here: an extra problem is
    # conservative, whereas rounding below the analytical bound is not.
    return max(1, int(math.ceil(raw_count)))


def audit_experiment_archives(
    experiments_root: Path,
    *,
    trusted_registration_keys: Mapping[str, Path] | None = None,
    trusted_randomization_keys: Mapping[str, Path] | None = None,
    trusted_trace_keys: Mapping[str, Path] | None = None,
    trusted_grader_keys: Mapping[str, Path] | None = None,
) -> Dict[str, Any]:
    """Audit archive registration and the reproducibility contract.

    Historical archives remain readable but receive no validation authority.
    A future archive may use ``protocol_validated`` only when its manifest is
    complete and every declared file hash matches.
    """

    root = experiments_root.resolve()
    registry_path = root / "archive_status.json"
    errors: list[str] = []
    try:
        registry = _load_bounded_json(registry_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {"valid": False, "errors": [f"invalid archive registry: {exc}"], "archives": {}}
    statuses = registry.get("archives") if isinstance(registry, Mapping) else None
    if not isinstance(statuses, Mapping):
        return {"valid": False, "errors": ["archive registry requires an archives object"], "archives": {}}

    discovered = {
        str(path.parent.resolve().relative_to(root))
        for path in root.rglob("SHA256SUMS")
        if path.is_file()
    }
    registered = {str(key) for key in statuses}
    for missing in sorted(discovered - registered):
        errors.append(f"archive with SHA256SUMS is unregistered: {missing}")
    for extra in sorted(registered - discovered):
        errors.append(f"registered archive has no SHA256SUMS: {extra}")

    results: Dict[str, Any] = {}
    for relative in sorted(discovered & registered):
        status = str(statuses.get(relative) or "")
        if status not in VALID_ARCHIVE_STATUSES:
            errors.append(f"{relative}: invalid archive status {status!r}")
            continue
        archive = (root / relative).resolve()
        if not archive.is_relative_to(root):
            errors.append(f"{relative}: path escapes experiments root")
            continue
        archive_errors = _audit_checksum_file(archive)
        if status == "protocol_validated":
            archive_errors.extend(
                _audit_protocol_manifest(
                    archive,
                    trusted_registration_keys=trusted_registration_keys or {},
                    trusted_randomization_keys=trusted_randomization_keys or {},
                    trusted_trace_keys=trusted_trace_keys or {},
                    trusted_grader_keys=trusted_grader_keys or {},
                )
            )
        manifest = _read_json(archive / "protocol_manifest.json")
        evidence_scope = (
            str(manifest.get("evidence_scope") or "")
            if isinstance(manifest, Mapping)
            else ""
        )
        protocol_valid = status == "protocol_validated" and not archive_errors
        results[relative] = {
            "status": status,
            "protocol_validated": protocol_valid,
            "evidence_scope": evidence_scope,
            "general_performance_evidence": protocol_valid
            and evidence_scope
            in {"general_performance", "novelty_and_performance"},
            "novelty_evidence": protocol_valid
            and evidence_scope == "novelty_and_performance",
            "errors": archive_errors,
        }
        errors.extend(f"{relative}: {error}" for error in archive_errors)
    return {"valid": not errors, "errors": errors, "archives": results}


def _audit_checksum_file(archive: Path) -> list[str]:
    errors: list[str] = []
    checksum_path = archive / "SHA256SUMS"
    try:
        text = _bounded_text(
            checksum_path,
            maximum_bytes=MAX_CHECKSUM_FILE_BYTES,
        )
        lines = text.splitlines()
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [f"cannot read SHA256SUMS: {exc}"]
    seen_targets: set[str] = set()
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        digest, separator, relative = line.partition("  ")
        if (
            not separator
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.lower())
        ):
            errors.append(f"malformed SHA256SUMS line {line_number}")
            continue
        normalized_relative = relative.lstrip("*")
        if normalized_relative in seen_targets:
            errors.append(f"duplicate SHA256SUMS target: {normalized_relative}")
            continue
        seen_targets.add(normalized_relative)
        path = _archive_file(archive, normalized_relative)
        if path is None:
            errors.append(f"checksum path is unsafe or escapes archive: {relative}")
            continue
        if not path.is_file():
            errors.append(f"checksum target is missing: {relative}")
            continue
        actual, hash_error = _sha256_file(path)
        if hash_error:
            errors.append(f"cannot hash checksum target {relative}: {hash_error}")
            continue
        if actual != digest.lower():
            errors.append(f"checksum mismatch: {relative}")
    return errors


def _audit_protocol_manifest(
    archive: Path,
    *,
    trusted_registration_keys: Mapping[str, Path],
    trusted_randomization_keys: Mapping[str, Path],
    trusted_trace_keys: Mapping[str, Path],
    trusted_grader_keys: Mapping[str, Path],
) -> list[str]:
    path = archive / "protocol_manifest.json"
    try:
        manifest = _load_bounded_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"invalid protocol_manifest.json: {exc}"]
    if not isinstance(manifest, Mapping):
        return ["protocol manifest must be an object"]
    errors = [f"protocol manifest missing {key}" for key in sorted(REQUIRED_PROTOCOL_FIELDS - set(manifest))]
    raw_protocol_version = manifest.get("protocol_version")
    if type(raw_protocol_version) is not int:
        errors.append("protocol_version must be an integer")
        protocol_version = 0
    else:
        protocol_version = raw_protocol_version
    if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        errors.append("protocol_version is unsupported")
    evidence_scope = str(manifest.get("evidence_scope") or "")
    if evidence_scope not in VALID_EVIDENCE_SCOPES:
        errors.append(
            "evidence_scope must be case_study, general_performance, or "
            "novelty_and_performance"
        )
    for key in ("problem_selection_rule", "model", "stopping_rule"):
        if not str(manifest.get(key) or "").strip():
            errors.append(f"{key} must be nonempty")
    file_hashes = manifest.get("file_sha256")
    if not isinstance(file_hashes, Mapping):
        return [*errors, "file_sha256 must be an object"]
    for relative, expected in file_hashes.items():
        target = _archive_file(archive, relative)
        if target is None or not target.is_file():
            errors.append(f"declared protocol file is missing or escapes archive: {relative}")
            continue
        actual, hash_error = _sha256_file(target)
        if hash_error:
            errors.append(f"cannot hash declared protocol file {relative}: {hash_error}")
            continue
        if actual != str(expected).lower():
            errors.append(f"protocol file hash mismatch: {relative}")

    scalar_file_fields = {
        "problem_file",
        "prompt_problem_file",
        "environment_file",
        "run_log_file",
        "event_log_file",
        "proof_snapshot_file",
        "independent_grade_file",
        "scoreboard_file",
    }
    if evidence_scope in {"general_performance", "novelty_and_performance"}:
        scalar_file_fields.update(GENERAL_EVIDENCE_FILE_FIELDS)
        if protocol_version >= 6:
            scalar_file_fields.add("randomization_receipt_file")
            scalar_file_fields.add("scheduler_trace_audit_file")
            scalar_file_fields.add("blinded_grading_manifest_file")
    list_file_fields = {
        "prompt_files",
        "agent_visible_files",
        "reference_answer_files",
    }
    declared_files: set[str] = set()
    for field in scalar_file_fields:
        relative = str(manifest.get(field) or "")
        if relative:
            declared_files.add(relative)
        else:
            errors.append(f"{field} must name a file")
    for field in list_file_fields:
        values = manifest.get(field)
        if not isinstance(values, list):
            errors.append(f"{field} must be a list")
            continue
        if len(values) > MAX_MANIFEST_LIST_ENTRIES:
            errors.append(
                f"{field} exceeds the {MAX_MANIFEST_LIST_ENTRIES}-entry audit limit"
            )
            values = values[:MAX_MANIFEST_LIST_ENTRIES]
        if field == "prompt_files" and not values:
            errors.append("prompt_files must be nonempty")
        declared_files.update(str(value) for value in values if str(value))
    for relative in sorted(declared_files):
        if relative not in file_hashes:
            errors.append(f"declared protocol file is absent from file_sha256: {relative}")

    problem_file = _archive_file(archive, manifest.get("problem_file"))
    prompt_problem_file = _archive_file(archive, manifest.get("prompt_problem_file"))
    if problem_file and problem_file.is_file():
        actual_problem_hash, problem_hash_error = _sha256_file(problem_file)
        if problem_hash_error:
            errors.append(f"cannot hash problem_file: {problem_hash_error}")
        if actual_problem_hash != str(manifest.get("problem_sha256") or "").lower():
            errors.append("problem_sha256 does not match problem_file")
    if (
        problem_file
        and prompt_problem_file
        and problem_file.is_file()
        and prompt_problem_file.is_file()
        and not _files_equal(problem_file, prompt_problem_file)
    ):
        errors.append("prompt problem does not exactly match the selected problem")

    prompt_files = {
        str(item) for item in manifest.get("prompt_files", []) or [] if str(item)
    }
    visible_files = {
        str(item)
        for item in manifest.get("agent_visible_files", []) or []
        if str(item)
    }
    reference_files = {
        str(item)
        for item in manifest.get("reference_answer_files", []) or []
        if str(item)
    }
    leaked_paths = reference_files & (prompt_files | visible_files)
    for relative in sorted(leaked_paths):
        errors.append(f"reference answer was agent-visible: {relative}")
    visible_text, visible_errors = _combined_text(
        archive,
        sorted(prompt_files | visible_files),
        label="agent-visible material",
    )
    errors.extend(visible_errors)
    normalized_visible = " ".join(visible_text.split()).casefold()
    for relative in sorted(reference_files):
        answer_text, answer_errors = _combined_text(
            archive,
            [relative],
            label=f"reference answer {relative}",
        )
        errors.extend(answer_errors)
        answer = " ".join(answer_text.split()).casefold()
        if len(answer) >= 40 and answer in normalized_visible:
            errors.append(f"reference answer content appears in agent-visible material: {relative}")

    grade = _read_json(_archive_file(archive, manifest.get("independent_grade_file")))
    scoreboard = _read_json(_archive_file(archive, manifest.get("scoreboard_file")))
    if not isinstance(grade, Mapping) or grade.get("independent") is not True:
        errors.append("independent grade must set independent=true")
    if not isinstance(grade, Mapping) or not str(grade.get("grader_identity") or "").strip():
        errors.append("independent grade must name grader_identity")
    graded_labels = grade.get("run_labels") if isinstance(grade, Mapping) else None
    scoreboard_labels = scoreboard.get("labels") if isinstance(scoreboard, Mapping) else None
    if not isinstance(graded_labels, Mapping):
        errors.append("independent grade must contain a run_labels object")
    if not isinstance(scoreboard_labels, Mapping):
        errors.append("scoreboard must contain a labels object")
    if isinstance(graded_labels, Mapping) and isinstance(scoreboard_labels, Mapping):
        for run_id, label in scoreboard_labels.items():
            if graded_labels.get(run_id) != label:
                errors.append(
                    f"scoreboard label lacks an identical independent grade: {run_id}"
                )

    checksum_targets = _checksum_target_names(archive / "SHA256SUMS")
    archive_files: set[str] = set()
    for archive_path in archive.rglob("*"):
        if archive_path.is_symlink():
            errors.append(
                f"protocol archive contains a symbolic link: {archive_path.relative_to(archive)}"
            )
            continue
        if archive_path.is_file() and archive_path.name != "SHA256SUMS":
            archive_files.add(str(archive_path.relative_to(archive)))
    for relative in sorted(archive_files - checksum_targets):
        errors.append(f"protocol archive file is absent from SHA256SUMS: {relative}")
    ablation = manifest.get("ablation")
    if isinstance(ablation, Mapping):
        if _safe_nonnegative_int(ablation.get("repeated_trials")) < 3:
            errors.append("ablation requires at least three repeated trials per condition")
        if ablation.get("matched_controls") is not True:
            errors.append("ablation requires matched problem, prompt, model, budget, and stopping rule")
    if evidence_scope in {"general_performance", "novelty_and_performance"}:
        errors.extend(
            _audit_general_evidence_design(
                archive,
                manifest,
                novelty_required=evidence_scope == "novelty_and_performance",
                trusted_registration_keys=trusted_registration_keys,
                trusted_randomization_keys=trusted_randomization_keys,
                trusted_trace_keys=trusted_trace_keys,
                trusted_grader_keys=trusted_grader_keys,
            )
        )
    return errors


def _audit_general_evidence_design(
    archive: Path,
    manifest: Mapping[str, Any],
    *,
    novelty_required: bool,
    trusted_registration_keys: Mapping[str, Path],
    trusted_randomization_keys: Mapping[str, Path],
    trusted_trace_keys: Mapping[str, Path],
    trusted_grader_keys: Mapping[str, Path],
) -> list[str]:
    """Reject one-off or self-graded runs as general empirical evidence."""

    errors: list[str] = []
    if _safe_nonnegative_int(manifest.get("protocol_version")) < 4:
        errors.append("general evidence requires protocol_version at least 4")
    preregistration = _read_json(
        _archive_file(archive, manifest.get("preregistration_file"))
    )
    trial_manifest = _read_json(
        _archive_file(archive, manifest.get("trial_manifest_file"))
    )
    analysis = _read_json(
        _archive_file(archive, manifest.get("statistical_analysis_file"))
    )
    analysis_plan = _read_json(
        _archive_file(archive, manifest.get("analysis_plan_file"))
    )
    selection_rule = _read_json(
        _archive_file(archive, manifest.get("selection_rule_file"))
    )
    registration_receipt = _read_json(
        _archive_file(archive, manifest.get("registration_receipt_file"))
    )
    randomization_receipt = (
        _read_json(
            _archive_file(archive, manifest.get("randomization_receipt_file"))
        )
        if _safe_nonnegative_int(manifest.get("protocol_version")) >= 6
        else None
    )
    scheduler_trace_audit = (
        _read_json(
            _archive_file(archive, manifest.get("scheduler_trace_audit_file"))
        )
        if _safe_nonnegative_int(manifest.get("protocol_version")) >= 6
        else None
    )
    blinded_grading_manifest = (
        _read_json(
            _archive_file(
                archive, manifest.get("blinded_grading_manifest_file")
            )
        )
        if _safe_nonnegative_int(manifest.get("protocol_version")) >= 6
        else None
    )
    assignment_schedule = _read_json(
        _archive_file(archive, manifest.get("assignment_schedule_file"))
    )
    grader_protocol = _read_json(
        _archive_file(archive, manifest.get("grader_protocol_file"))
    )
    grade = _read_json(
        _archive_file(archive, manifest.get("independent_grade_file"))
    )

    if not isinstance(preregistration, Mapping):
        errors.append("general evidence requires a readable preregistration")
        preregistration = {}
    if not isinstance(analysis_plan, Mapping):
        errors.append("general evidence requires a readable analysis plan")
        analysis_plan = {}
    if not isinstance(selection_rule, Mapping):
        errors.append("general evidence requires a readable selection rule")
        selection_rule = {}
    if not isinstance(assignment_schedule, Mapping):
        errors.append("general evidence requires a readable assignment schedule")
        assignment_schedule = {}
    errors.extend(
        _registration_receipt_errors(
            archive,
            manifest,
            preregistration=preregistration,
            receipt=registration_receipt,
            trusted_registration_keys=trusted_registration_keys,
        )
    )
    if _safe_nonnegative_int(manifest.get("protocol_version")) >= 6:
        errors.extend(
            _randomization_receipt_errors(
                archive,
                manifest,
                preregistration=preregistration,
                registration_receipt=registration_receipt,
                randomization_receipt=randomization_receipt,
                trusted_randomization_keys=trusted_randomization_keys,
            )
        )
    if preregistration.get("registered_before_execution") is not True:
        errors.append("preregistration must certify registration before execution")
    if preregistration.get("held_out_problem_selection") is not True:
        errors.append("general evidence requires held-out problem selection")
    conditions = preregistration.get("conditions")
    if (
        not isinstance(conditions, list)
        or len(conditions) < 2
        or any(not isinstance(item, str) or not item.strip() for item in conditions)
        or len(set(conditions)) != len(conditions)
    ):
        errors.append(
            "general evidence preregistration requires at least two distinct named conditions"
        )
        conditions = []
    elif conditions != sorted(conditions):
        errors.append("preregistered conditions must be in canonical sorted order")
    condition_definitions = selection_rule.get("conditions")
    defined_conditions: set[str] = set()
    condition_spec_by_id: dict[str, Mapping[str, Any]] = {}
    if not isinstance(condition_definitions, list) or not condition_definitions:
        errors.append("selection rule must define every experimental condition")
    else:
        environment_path = _archive_file(
            archive, manifest.get("environment_file")
        )
        environment_sha256, environment_hash_error = (
            _sha256_file(environment_path)
            if environment_path is not None
            else ("", "missing or unsafe path")
        )
        if environment_hash_error:
            errors.append(
                f"cannot hash the registered environment file: {environment_hash_error}"
            )
        condition_spec_files: set[str] = set()
        condition_spec_hashes: set[str] = set()
        for definition in condition_definitions:
            if not isinstance(definition, Mapping):
                errors.append("selection-rule condition definitions must be objects")
                continue
            condition_id = str(definition.get("condition_id") or "")
            condition_spec_file = str(
                definition.get("condition_spec_file") or ""
            )
            condition_spec_sha256 = str(
                definition.get("condition_spec_sha256") or ""
            )
            if not condition_id or condition_id in defined_conditions:
                errors.append(
                    "selection-rule condition identifiers must be nonempty and unique"
                )
                continue
            defined_conditions.add(condition_id)
            if condition_spec_file in condition_spec_files:
                errors.append("experimental conditions must use distinct specification files")
            condition_spec_files.add(condition_spec_file)
            if condition_spec_sha256 in condition_spec_hashes:
                errors.append("experimental conditions must have distinct specifications")
            condition_spec_hashes.add(condition_spec_sha256)
            condition_spec_path = _archive_file(
                archive, condition_spec_file
            )
            if condition_spec_path is None:
                errors.append(
                    f"condition {condition_id} specification file is missing or unsafe"
                )
                continue
            observed_spec_sha256, spec_hash_error = _sha256_file(
                condition_spec_path
            )
            if spec_hash_error or observed_spec_sha256 != condition_spec_sha256:
                errors.append(
                    f"condition {condition_id} specification commitment is inconsistent"
                )
            condition_spec = _read_json(condition_spec_path)
            if not isinstance(condition_spec, Mapping) or (
                condition_spec.get("condition_id") != condition_id
            ):
                errors.append(
                    f"condition {condition_id} specification does not identify its condition"
                )
            else:
                condition_spec_by_id[condition_id] = condition_spec
            file_hashes = manifest.get("file_sha256")
            if not isinstance(file_hashes, Mapping) or (
                file_hashes.get(condition_spec_file) != condition_spec_sha256
            ):
                errors.append(
                    f"condition {condition_id} specification is not bound by the protocol manifest"
                )
            if definition.get("environment_sha256") != environment_sha256:
                errors.append(
                    f"condition {condition_id} environment commitment is inconsistent"
                )
    if defined_conditions != set(conditions):
        errors.append(
            "selection-rule conditions do not exactly match the preregistration"
        )
    if (
        selection_rule.get("execution_order_algorithm")
        != "sha256_fisher_yates_rejection_v1"
    ):
        errors.append("selection rule execution-order algorithm is unsupported")
    endpoints = preregistration.get("primary_endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        errors.append("preregistration must declare nonempty primary_endpoints")
        endpoints = []
    elif len(endpoints) != 1:
        errors.append(
            "protocol version 4 requires exactly one primary endpoint to avoid unmodelled multiplicity"
        )
    contrasts = preregistration.get("primary_contrasts")
    contrast_by_endpoint: dict[str, Mapping[str, Any]] = {}
    if not isinstance(contrasts, list) or not contrasts:
        errors.append("preregistration must declare nonempty primary_contrasts")
    else:
        for contrast in contrasts:
            if not isinstance(contrast, Mapping):
                errors.append("preregistered primary contrasts must be objects")
                continue
            endpoint = str(contrast.get("endpoint") or "")
            treatment = str(contrast.get("treatment_condition") or "")
            control = str(contrast.get("control_condition") or "")
            if (
                not endpoint
                or endpoint in contrast_by_endpoint
                or treatment == control
                or treatment not in conditions
                or control not in conditions
                or contrast.get("estimand")
                != "problem_mean_success_difference"
            ):
                errors.append("preregistered primary contrast is malformed")
                continue
            contrast_by_endpoint[endpoint] = contrast
    if set(str(endpoint) for endpoint in endpoints) != set(
        contrast_by_endpoint
    ):
        errors.append(
            "primary_contrasts must define every primary endpoint exactly once"
        )
    for key, manifest_field in (
        ("selection_rule_sha256", "selection_rule_file"),
        ("analysis_plan_sha256", "analysis_plan_file"),
        ("assignment_schedule_sha256", "assignment_schedule_file"),
        ("grader_protocol_sha256", "grader_protocol_file"),
        ("rubric_sha256", "rubric_file"),
    ):
        value = str(preregistration.get(key) or "")
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value.lower()):
            errors.append(f"preregistration {key} must be a SHA-256 digest")
            continue
        plan_file = _archive_file(archive, manifest.get(manifest_field))
        if plan_file is None:
            errors.append(f"{manifest_field} is missing or unsafe")
            continue
        actual, hash_error = _sha256_file(plan_file)
        if hash_error:
            errors.append(f"cannot hash {manifest_field}: {hash_error}")
        elif actual != value:
            errors.append(
                f"preregistration {key} does not match {manifest_field}"
            )
    target_problem_count = _safe_nonnegative_int(
        preregistration.get("target_problem_count")
    )
    repeated_trials = _safe_nonnegative_int(
        preregistration.get("repeated_trials_per_condition")
    )
    if target_problem_count < 10:
        errors.append("general evidence preregistration requires at least ten held-out problems")
    if repeated_trials < 3:
        errors.append("general evidence requires at least three trials per problem/condition")
    power_analysis = preregistration.get("power_analysis")
    if not isinstance(power_analysis, Mapping):
        errors.append("preregistration must contain a power_analysis object")
        power_analysis = {}
    required_problem_count = _safe_nonnegative_int(
        power_analysis.get("required_problem_count")
    )
    raw_power_alpha = power_analysis.get("alpha")
    try:
        power_alpha = (
            float("nan")
            if isinstance(raw_power_alpha, bool)
            else float(raw_power_alpha)
        )
    except (TypeError, ValueError, OverflowError):
        power_alpha = float("nan")
    protocol_version = _safe_nonnegative_int(manifest.get("protocol_version"))
    if protocol_version >= 6 and preregistration.get("experiment_kind") != (
        "parallel_admission_scheduler_calibration"
    ):
        errors.append(
            "protocol v6 requires experiment_kind parallel_admission_scheduler_calibration"
        )
    if protocol_version >= 6 and preregistration.get(
        "scheduler_assignment_protocol_version"
    ) != BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION:
        errors.append(
            "protocol v6 requires scheduler_assignment_protocol_version 3"
        )
    scheduler_experiment_id = str(
        preregistration.get("scheduler_experiment_id") or ""
    )
    scheduler_exploration_stratum = str(
        preregistration.get("scheduler_exploration_stratum") or ""
    )
    if protocol_version >= 6 and (
        not scheduler_experiment_id or not scheduler_exploration_stratum
    ):
        errors.append(
            "protocol v6 must preregister scheduler experiment and stratum identifiers"
        )
    if protocol_version >= 6:
        if not str(preregistration.get("randomness_source") or ""):
            errors.append("protocol v6 must preregister a randomness source")
        if not str(preregistration.get("randomness_event_id") or ""):
            errors.append("protocol v6 must preregister a randomness event identifier")
        if preregistration.get("randomization_authority_separate") is not True:
            errors.append(
                "protocol v6 requires a role-separated randomization authority"
            )
        if preregistration.get(
            "block_seed_derivation_algorithm"
        ) != BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM:
            errors.append("protocol v6 block seed derivation algorithm is unsupported")
    if protocol_version >= 6:
        scheduler_condition_fields = {
            "condition_id",
            "condition_kind",
            "policy_family",
            "selection_policy_version",
            "policy_semantics_sha256",
        }
        observed_policy_versions: set[int] = set()
        for condition_id in conditions:
            condition_spec = condition_spec_by_id.get(condition_id)
            if not isinstance(condition_spec, Mapping) or set(
                condition_spec
            ) != scheduler_condition_fields:
                errors.append(
                    f"scheduler condition {condition_id} has a noncanonical specification"
                )
                continue
            policy_version = condition_spec.get("selection_policy_version")
            if (
                condition_spec.get("condition_kind")
                != "parallel_admission_policy"
                or condition_spec.get("policy_family") != "parallel_admission"
                or type(policy_version) is not int
                or condition_id != f"parallel-v{policy_version}"
                or policy_version not in PARALLEL_POLICY_SEMANTIC_SHA256
                or condition_spec.get("policy_semantics_sha256")
                != PARALLEL_POLICY_SEMANTIC_SHA256.get(policy_version)
            ):
                errors.append(
                    f"scheduler condition {condition_id} does not bind a supported parallel policy"
                )
                continue
            observed_policy_versions.add(policy_version)
        if len(observed_policy_versions) != len(conditions):
            errors.append(
                "scheduler calibration conditions must use distinct policy versions"
            )
    if protocol_version >= 5:
        if set(power_analysis) != PAIRED_PROBLEM_POWER_FIELDS:
            errors.append(
                "power_analysis fields do not match the paired-problem protocol"
            )
        if power_analysis.get("method") != PAIRED_PROBLEM_POWER_METHOD:
            errors.append("power_analysis method is unsupported")
        if power_analysis.get("analysis_unit") != "problem":
            errors.append("power_analysis analysis_unit must be problem")
        if power_analysis.get("alternative") != "two_sided":
            errors.append("power_analysis alternative must be two_sided")
        standard_deviation_basis = str(
            power_analysis.get("standard_deviation_basis") or ""
        )
        if standard_deviation_basis not in STANDARD_DEVIATION_BASES:
            errors.append(
                "power_analysis standard_deviation_basis is unsupported"
            )
        try:
            computed_required_problem_count = (
                paired_problem_power_required_count(
                    alpha=power_analysis.get("alpha"),
                    desired_power=power_analysis.get("desired_power"),
                    minimum_detectable_effect=power_analysis.get(
                        "minimum_detectable_effect"
                    ),
                    assumed_standard_deviation=power_analysis.get(
                        "assumed_problem_mean_difference_standard_deviation"
                    ),
                )
            )
        except ValueError as exc:
            computed_required_problem_count = 0
            errors.append(str(exc))
        if required_problem_count != computed_required_problem_count:
            errors.append(
                "power_analysis required_problem_count does not match the "
                "registered paired-problem calculation"
            )
    else:
        # Protocol v4 accepted a declared simulation result. Preserve that
        # weaker historical meaning for replay; only v5 may claim the stronger
        # recomputed sample-size contract.
        if not str(power_analysis.get("method") or "").strip():
            errors.append("power_analysis must name its method")
        raw_values = (
            power_analysis.get("alpha"),
            power_analysis.get("desired_power"),
            power_analysis.get("minimum_detectable_effect"),
        )
        if any(isinstance(value, bool) for value in raw_values):
            desired_power = minimum_effect = float("nan")
        else:
            try:
                desired_power = float(raw_values[1])
                minimum_effect = float(raw_values[2])
            except (TypeError, ValueError, OverflowError):
                desired_power = minimum_effect = float("nan")
        if not (math.isfinite(power_alpha) and 0.0 < power_alpha <= 0.10):
            errors.append("power_analysis alpha must lie in (0, 0.10]")
        if not (
            math.isfinite(desired_power) and 0.5 < desired_power < 1.0
        ):
            errors.append("power_analysis desired_power must lie in (0.5, 1)")
        if not (math.isfinite(minimum_effect) and minimum_effect > 0.0):
            errors.append(
                "power_analysis minimum_detectable_effect must be positive"
            )
    if required_problem_count < 1 or target_problem_count < required_problem_count:
        errors.append(
            "target_problem_count must meet the preregistered power_analysis requirement"
        )
    bootstrap_method = str(analysis_plan.get("method") or "")
    bootstrap_seed_sha256 = str(
        analysis_plan.get("bootstrap_seed_sha256") or ""
    )
    bootstrap_replicates = _safe_nonnegative_int(
        analysis_plan.get("bootstrap_replicates")
    )
    bootstrap_quantile_rule = str(
        analysis_plan.get("quantile_rule") or ""
    )
    if bootstrap_method != "sha256 problem-cluster bootstrap percentile v1":
        errors.append("analysis plan must use the supported cluster-bootstrap method")
    if (
        len(bootstrap_seed_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in bootstrap_seed_sha256
        )
    ):
        errors.append("analysis plan bootstrap seed must be a lowercase SHA-256 digest")
    if not 1_000 <= bootstrap_replicates <= 100_000:
        errors.append("analysis plan bootstrap_replicates must lie in [1000, 100000]")
    if bootstrap_quantile_rule != "outer_order_statistics_v1":
        errors.append("analysis plan quantile rule is unsupported")

    trials = (
        trial_manifest.get("trials")
        if isinstance(trial_manifest, Mapping)
        else None
    )
    if not isinstance(trials, list) or not trials:
        errors.append("trial manifest must contain a nonempty trials list")
        trials = []
    elif len(trials) > MAX_MANIFEST_LIST_ENTRIES:
        errors.append(
            "trial manifest exceeds the "
            f"{MAX_MANIFEST_LIST_ENTRIES}-trial audit limit"
        )
        trials = trials[:MAX_MANIFEST_LIST_ENTRIES]
    required_trial_fields = {
        "run_id",
        "problem_id",
        "condition",
        "repeat_index",
        "random_seed",
        "execution_order",
        "problem_sha256",
        "prompt_sha256",
        "token_budget",
        "stopping_rule",
        "problem_file",
        "prompt_file",
        "event_log_file",
        "event_log_sha256",
        "proof_snapshot_file",
        "proof_snapshot_sha256",
        "result_file",
        "result_sha256",
    }
    if protocol_version >= 6:
        required_trial_fields.update(
            {
                "scheduler_assignment_file",
                "scheduler_assignment_sha256",
                "grading_artifact_file",
                "grading_artifact_sha256",
            }
        )
    run_ids: set[str] = set()
    trial_by_run_id: dict[str, Mapping[str, Any]] = {}
    repetitions: dict[tuple[str, str], set[int]] = {}
    trials_by_block: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    problem_hash_by_id: dict[str, str] = {}
    per_run_paths: dict[str, set[str]] = {
        "event_log_file": set(),
        "proof_snapshot_file": set(),
        "result_file": set(),
    }
    if protocol_version >= 6:
        per_run_paths["scheduler_assignment_file"] = set()
        per_run_paths["grading_artifact_file"] = set()
    per_run_file_identities: dict[str, set[tuple[int, int]]] = {
        "event_log_file": set(),
        "proof_snapshot_file": set(),
        "result_file": set(),
    }
    if protocol_version >= 6:
        per_run_file_identities["scheduler_assignment_file"] = set()
        per_run_file_identities["grading_artifact_file"] = set()
    for index, raw_trial in enumerate(trials):
        if not isinstance(raw_trial, Mapping):
            errors.append(f"trial {index} must be an object")
            continue
        missing = required_trial_fields - set(raw_trial)
        if missing:
            errors.append(
                f"trial {index} is missing fields: {', '.join(sorted(missing))}"
            )
            continue
        if protocol_version >= 6 and set(raw_trial) != required_trial_fields:
            errors.append(f"trial {index} fields are noncanonical for protocol v6")
        run_id = str(raw_trial.get("run_id") or "")
        if not run_id or run_id in run_ids:
            errors.append(f"trial {index} has an empty or duplicate run_id")
        if protocol_version >= 6 and any(
            str(condition).casefold() in run_id.casefold()
            for condition in conditions
            if str(condition)
        ):
            errors.append(
                f"trial {index} evaluation identifier reveals its condition"
            )
        run_ids.add(run_id)
        if run_id:
            trial_by_run_id[run_id] = raw_trial
        key = (
            str(raw_trial.get("problem_id") or ""),
            str(raw_trial.get("condition") or ""),
        )
        if not key[0] or not key[1]:
            errors.append(f"trial {index} requires nonempty problem and condition identifiers")
        repeat_index = raw_trial.get("repeat_index")
        random_seed = raw_trial.get("random_seed")
        token_budget = raw_trial.get("token_budget")
        if type(repeat_index) is not int or repeat_index < 1:
            errors.append(f"trial {index} repeat_index must be a positive integer")
        if (
            type(random_seed) is not int
            or random_seed < 0
            or random_seed > MAX_RANDOMIZED_BLOCK_SEED
        ):
            errors.append(
                f"trial {index} random_seed must be an unsigned 256-bit integer"
            )
        if type(token_budget) is not int or token_budget <= 0:
            errors.append(f"trial {index} token_budget must be a positive integer")
        execution_order = raw_trial.get("execution_order")
        if type(execution_order) is not int or execution_order < 0:
            errors.append(f"trial {index} execution_order must be a nonnegative integer")
        if not str(raw_trial.get("stopping_rule") or "").strip():
            errors.append(f"trial {index} stopping_rule must be nonempty")
        problem_hash = str(raw_trial.get("problem_sha256") or "").lower()
        previous_problem_hash = problem_hash_by_id.setdefault(key[0], problem_hash)
        if previous_problem_hash != problem_hash:
            errors.append(f"problem {key[0]!r} has inconsistent content hashes")
        repetitions.setdefault(key, set()).add(
            _safe_nonnegative_int(raw_trial.get("repeat_index"))
        )
        trials_by_block.setdefault(
            (
                key[0],
                _safe_nonnegative_int(raw_trial.get("repeat_index")),
            ),
            [],
        ).append(raw_trial)
        for file_field, digest_field in (
            ("problem_file", "problem_sha256"),
            ("prompt_file", "prompt_sha256"),
            ("event_log_file", "event_log_sha256"),
            ("proof_snapshot_file", "proof_snapshot_sha256"),
            ("result_file", "result_sha256"),
            *(
                (("scheduler_assignment_file", "scheduler_assignment_sha256"),)
                if protocol_version >= 6
                else ()
            ),
            *(
                (("grading_artifact_file", "grading_artifact_sha256"),)
                if protocol_version >= 6
                else ()
            ),
        ):
            relative = str(raw_trial.get(file_field) or "")
            target = _archive_file(archive, relative)
            if target is None or not target.is_file():
                errors.append(f"trial {index} {file_field} is missing or unsafe")
                continue
            actual, hash_error = _sha256_file(target)
            if hash_error:
                errors.append(
                    f"trial {index} cannot hash {file_field}: {hash_error}"
                )
                continue
            if actual != str(raw_trial.get(digest_field) or "").lower():
                errors.append(
                    f"trial {index} {digest_field} does not match {file_field}"
                )
            file_hashes = manifest.get("file_sha256")
            if not isinstance(file_hashes, Mapping) or relative not in file_hashes:
                errors.append(f"trial {index} {file_field} is absent from file_sha256")
            if file_field in per_run_paths:
                if relative in per_run_paths[file_field]:
                    errors.append(
                        f"trial {index} reuses {file_field}; each run requires its own immutable record"
                    )
                per_run_paths[file_field].add(relative)
                try:
                    file_stat = target.stat()
                    identity = (int(file_stat.st_dev), int(file_stat.st_ino))
                except OSError as exc:
                    errors.append(
                        f"trial {index} cannot stat {file_field}: {exc}"
                    )
                else:
                    if identity in per_run_file_identities[file_field]:
                        errors.append(
                            f"trial {index} aliases another run's {file_field}; "
                            "each run requires a distinct regular file"
                        )
                    per_run_file_identities[file_field].add(identity)

        event_rows, event_errors = _read_json_lines(
            _archive_file(archive, raw_trial.get("event_log_file")),
            label=f"trial {index} event log",
        )
        errors.extend(event_errors)
        event_types: set[str] = set()
        for event_row in event_rows:
            if not isinstance(event_row, Mapping):
                errors.append(f"trial {index} event log records must be objects")
                continue
            if str(event_row.get("run_id") or "") != run_id:
                errors.append(f"trial {index} event log contains a foreign run_id")
            event_types.add(str(event_row.get("event") or ""))
        if "start" not in event_types or not event_types.intersection(
            {"completed", "failed", "stopped"}
        ):
            errors.append(
                f"trial {index} event log requires start and terminal events"
            )
        snapshot = _read_json(
            _archive_file(archive, raw_trial.get("proof_snapshot_file"))
        )
        if not isinstance(snapshot, Mapping):
            errors.append(f"trial {index} proof snapshot must be a JSON object")
        else:
            if str(snapshot.get("run_id") or "") != run_id:
                errors.append(f"trial {index} proof snapshot run_id disagrees")
            state_hash = str(snapshot.get("state_hash") or "").lower()
            if len(state_hash) != 64 or any(
                character not in "0123456789abcdef" for character in state_hash
            ):
                errors.append(f"trial {index} proof snapshot requires a state_hash")
            if _safe_nonnegative_int(snapshot.get("current_revision")) < 1:
                errors.append(
                    f"trial {index} proof snapshot requires a positive current_revision"
                )
        result_path = _archive_file(archive, raw_trial.get("result_file"))
        try:
            result_nonempty = bool(
                result_path is not None
                and result_path.is_file()
                and result_path.stat().st_size > 0
            )
        except OSError:
            result_nonempty = False
        if not result_nonempty:
            errors.append(f"trial {index} result_file must be nonempty")
        if protocol_version >= 6:
            grading_artifact = _read_json(
                _archive_file(archive, raw_trial.get("grading_artifact_file"))
            )
            if not isinstance(grading_artifact, Mapping) or set(
                grading_artifact
            ) != {"artifact_version", "evaluation_id", "solution"}:
                errors.append(
                    f"trial {index} blinded grading artifact is noncanonical"
                )
            else:
                solution = str(grading_artifact.get("solution") or "")
                if (
                    grading_artifact.get("artifact_version") != 1
                    or grading_artifact.get("evaluation_id") != run_id
                    or not solution.strip()
                ):
                    errors.append(
                        f"trial {index} blinded grading artifact is inconsistent"
                    )
                normalized_solution = solution.casefold()
                if any(
                    str(condition).casefold() in normalized_solution
                    for condition in conditions
                    if str(condition)
                ):
                    errors.append(
                        f"trial {index} blinded grading artifact reveals its condition"
                    )

    run_log_rows, run_log_errors = _read_json_lines(
        _archive_file(archive, manifest.get("run_log_file")),
        label="general evidence run log",
    )
    errors.extend(run_log_errors)
    logged_by_run_id: dict[str, Mapping[str, Any]] = {}
    required_run_log_fields = {
        "run_id",
        "problem_id",
        "condition",
        "repeat_index",
        "random_seed",
        "execution_order",
        "problem_sha256",
        "prompt_sha256",
        "token_budget",
        "status",
        "event_log_sha256",
        "proof_snapshot_sha256",
        "result_sha256",
    }
    if protocol_version >= 6:
        required_run_log_fields.add("scheduler_assignment_sha256")
        required_run_log_fields.add("grading_artifact_sha256")
    for index, row in enumerate(run_log_rows):
        if not isinstance(row, Mapping):
            errors.append(f"run log row {index} must be an object")
            continue
        missing = required_run_log_fields - set(row)
        if missing:
            errors.append(
                f"run log row {index} is missing fields: {', '.join(sorted(missing))}"
            )
            continue
        if protocol_version >= 6 and set(row) != required_run_log_fields:
            errors.append(
                f"run log row {index} fields are noncanonical for protocol v6"
            )
        run_id = str(row.get("run_id") or "")
        if not run_id or run_id in logged_by_run_id:
            errors.append(f"run log row {index} has an empty or duplicate run_id")
            continue
        logged_by_run_id[run_id] = row
    if set(logged_by_run_id) != run_ids:
        errors.append("run log run_ids must exactly equal the registered trial run_ids")
    for run_id in sorted(run_ids & set(logged_by_run_id)):
        trial = trial_by_run_id.get(run_id, {})
        logged = logged_by_run_id[run_id]
        for field in (
            "problem_id",
            "condition",
            "repeat_index",
            "random_seed",
            "execution_order",
            "problem_sha256",
            "prompt_sha256",
            "token_budget",
            "event_log_sha256",
            "proof_snapshot_sha256",
            "result_sha256",
            *(
                ("scheduler_assignment_sha256",)
                if protocol_version >= 6
                else ()
            ),
            *(
                ("grading_artifact_sha256",)
                if protocol_version >= 6
                else ()
            ),
        ):
            if logged.get(field) != trial.get(field):
                errors.append(f"run log field {field} disagrees with trial {run_id}")
        if not str(logged.get("status") or "").strip():
            errors.append(f"run log trial {run_id} has an empty status")

    if protocol_version >= 6:
        expected_blinded_grading_manifest = {
            "manifest_version": 1,
            "evaluations": [
                {
                    "evaluation_id": str(trial.get("run_id") or ""),
                    "problem_sha256": trial.get("problem_sha256"),
                    "grading_artifact_sha256": trial.get(
                        "grading_artifact_sha256"
                    ),
                }
                for trial in sorted(
                    trials,
                    key=lambda item: (
                        str(item.get("run_id") or "")
                        if isinstance(item, Mapping)
                        else ""
                    ),
                )
                if isinstance(trial, Mapping)
            ],
        }
        if blinded_grading_manifest != expected_blinded_grading_manifest:
            errors.append(
                "blinded grading manifest does not exactly match the registered evaluations"
            )

    trial_prompt_text, trial_prompt_errors = _combined_text(
        archive,
        [str(trial.get("prompt_file") or "") for trial in trial_by_run_id.values()],
        label="registered trial prompts",
    )
    errors.extend(trial_prompt_errors)
    normalized_trial_prompts = " ".join(trial_prompt_text.split()).casefold()
    for relative in sorted(
        str(item)
        for item in manifest.get("reference_answer_files", []) or []
        if str(item)
    ):
        answer_text, answer_errors = _combined_text(
            archive,
            [relative],
            label=f"reference answer {relative}",
        )
        errors.extend(answer_errors)
        answer = " ".join(answer_text.split()).casefold()
        if len(answer) >= 40 and answer in normalized_trial_prompts:
            errors.append(
                f"reference answer content appears in a registered trial prompt: {relative}"
            )
    problem_ids = {key[0] for key in repetitions if key[0]}
    if len(set(problem_hash_by_id.values())) != len(problem_hash_by_id):
        errors.append("distinct held-out problem ids must not alias identical problem bytes")
    if len(problem_ids) < target_problem_count:
        errors.append("trial manifest does not meet the preregistered held-out problem count")
    for key, repeats in sorted(repetitions.items()):
        if repeats != set(range(1, repeated_trials + 1)):
            errors.append(
                f"trial manifest repeats do not exactly match the preregistration for problem/condition {key}"
            )
    observed_conditions = {key[1] for key in repetitions if key[1]}
    if observed_conditions != set(conditions):
        errors.append(
            "trial manifest conditions do not exactly match the preregistration"
        )
    for block, block_trials in sorted(trials_by_block.items()):
        block_conditions = [str(row.get("condition") or "") for row in block_trials]
        if len(block_trials) != len(conditions) or set(block_conditions) != set(
            conditions
        ):
            errors.append(
                f"trial block {block} does not contain every preregistered condition exactly once"
            )
            continue
        for field in (
            "problem_sha256",
            "prompt_sha256",
            "token_budget",
            "stopping_rule",
            "random_seed",
        ):
            if len({json.dumps(row.get(field), sort_keys=True) for row in block_trials}) != 1:
                errors.append(
                    f"trial block {block} is not matched on {field} across conditions"
                )
        block_seed = block_trials[0].get("random_seed")
        try:
            expected_order = randomized_condition_order(
                conditions,
                problem_id=block[0],
                repeat_index=block[1],
                random_seed=block_seed,
            )
        except (TypeError, ValueError):
            expected_order = []
        observed_order = {
            str(row.get("condition") or ""): row.get("execution_order")
            for row in block_trials
        }
        if expected_order and observed_order != {
            condition: index for index, condition in enumerate(expected_order)
        }:
            errors.append(
                f"trial block {block} execution order does not match its preregistered randomization"
            )
    expected_schedule_blocks = [
        (
            {
                "problem_id": block[0],
                "problem_sha256": block_trials[0].get("problem_sha256"),
                "prompt_sha256": block_trials[0].get("prompt_sha256"),
                "repeat_index": block[1],
                "assignment_unit_ids": {
                    str(trial.get("condition") or ""): str(
                        trial.get("run_id") or ""
                    )
                    for trial in sorted(
                        block_trials,
                        key=lambda item: str(item.get("condition") or ""),
                    )
                },
                "token_budget": block_trials[0].get("token_budget"),
                "stopping_rule": block_trials[0].get("stopping_rule"),
            }
            if protocol_version >= 6
            else {
                "problem_id": block[0],
                "repeat_index": block[1],
                "random_seed": block_trials[0].get("random_seed"),
                "condition_order": randomized_condition_order(
                    conditions,
                    problem_id=block[0],
                    repeat_index=block[1],
                    random_seed=block_trials[0].get("random_seed"),
                ),
            }
        )
        for block, block_trials in sorted(trials_by_block.items())
        if block_trials
        and len(conditions) >= 2
        and type(block_trials[0].get("random_seed")) is int
        and block_trials[0].get("random_seed") >= 0
        and block_trials[0].get("random_seed") <= MAX_RANDOMIZED_BLOCK_SEED
        and block[0]
        and block[1] >= 1
    ]
    if assignment_schedule.get("algorithm") != "sha256_fisher_yates_rejection_v1":
        errors.append("assignment schedule algorithm is unsupported")
    if assignment_schedule.get("blocks") != expected_schedule_blocks:
        errors.append(
            "assignment schedule does not exactly match the registered trial blocks"
        )
    if protocol_version >= 6:
        expected_schedule_fields = {
            "algorithm",
            "block_seed_derivation_algorithm",
            "randomness_source",
            "randomness_event_id",
            "blocks",
        }
        if set(assignment_schedule) != expected_schedule_fields:
            errors.append("protocol v6 assignment schedule fields are noncanonical")
        for field in (
            "block_seed_derivation_algorithm",
            "randomness_source",
            "randomness_event_id",
        ):
            if assignment_schedule.get(field) != preregistration.get(field):
                errors.append(
                    f"protocol v6 assignment schedule {field} disagrees with the preregistration"
                )
        randomization_payload = (
            randomization_receipt.get("payload")
            if isinstance(randomization_receipt, Mapping)
            and isinstance(randomization_receipt.get("payload"), Mapping)
            else {}
        )
        randomness_sha256 = str(
            randomization_payload.get("randomness_sha256") or ""
        )
        for block, block_trials in sorted(trials_by_block.items()):
            if not block_trials:
                continue
            try:
                expected_seed = randomized_block_seed(
                    randomness_sha256=randomness_sha256,
                    problem_id=block[0],
                    repeat_index=block[1],
                )
            except ValueError:
                continue
            if any(
                trial.get("random_seed") != expected_seed
                for trial in block_trials
            ):
                errors.append(
                    f"trial block {block} seed does not derive from the registered randomness"
                )
    if protocol_version >= 6:
        errors.extend(
            _scheduler_calibration_assignment_errors(
                archive,
                manifest,
                trials=[trial for trial in trials if isinstance(trial, Mapping)],
                condition_spec_by_id=condition_spec_by_id,
                experiment_id=scheduler_experiment_id,
                exploration_stratum=scheduler_exploration_stratum,
                randomization_receipt=randomization_receipt,
            )
        )
    bootstrap_draws = bootstrap_replicates * len(problem_ids)
    if bootstrap_draws > MAX_BOOTSTRAP_DRAWS:
        errors.append(
            "preregistered bootstrap exceeds the bounded audit work limit"
        )

    if not isinstance(grader_protocol, Mapping):
        errors.append("general evidence requires a readable grader protocol")
        grader_protocol = {}
    for field in (
        "blinded_to_condition",
        "generator_excluded",
        "selector_excluded",
    ):
        if grader_protocol.get(field) is not True:
            errors.append(f"grader protocol must set {field}=true")
    if protocol_version >= 6:
        for field in (
            "condition_key_withheld_from_graders",
            "labels_finalized_before_trace_review",
            "trace_auditor_excluded_from_grading",
            "blinded_grading_artifact_only",
        ):
            if grader_protocol.get(field) is not True:
                errors.append(f"protocol v6 grader protocol must set {field}=true")
    if _safe_nonnegative_int(
        grader_protocol.get("minimum_independent_graders")
    ) < 2:
        errors.append("grader protocol requires at least two independent graders")
    rubric_sha = str(grader_protocol.get("rubric_sha256") or "")
    rubric_path = _archive_file(archive, manifest.get("rubric_file"))
    observed_rubric_sha, rubric_hash_error = (
        _sha256_file(rubric_path)
        if rubric_path is not None
        else ("", "missing or unsafe path")
    )
    if not _valid_sha256(rubric_sha):
        errors.append("grader protocol rubric_sha256 must be a SHA-256 digest")
    elif rubric_hash_error or observed_rubric_sha != rubric_sha:
        errors.append("grader protocol rubric_sha256 does not match rubric_file")

    graders = grade.get("graders") if isinstance(grade, Mapping) else None
    if not isinstance(graders, list):
        errors.append("independent grade must list its graders")
        graders = []
    grader_ids = {
        str(item.get("grader_identity") or "")
        for item in graders
        if isinstance(item, Mapping)
        and item.get("independent") is True
        and item.get("generator") is False
        and item.get("selector") is False
    }
    grader_ids.discard("")
    grader_record_by_id = {
        str(item.get("grader_identity") or ""): item
        for item in graders
        if isinstance(item, Mapping)
        and str(item.get("grader_identity") or "")
    }
    grader_key_ids = [
        str(item.get("signature", {}).get("key_id_sha256") or "")
        for item in grader_record_by_id.values()
        if isinstance(item.get("signature"), Mapping)
    ]
    if (
        len(grader_key_ids) != len(grader_ids)
        or "" in grader_key_ids
        or len(set(grader_key_ids)) != len(grader_key_ids)
    ):
        errors.append("independent graders must use distinct trusted signing keys")
    if protocol_version >= 6:
        registration_signature = (
            registration_receipt.get("signature")
            if isinstance(registration_receipt, Mapping)
            and isinstance(registration_receipt.get("signature"), Mapping)
            else {}
        )
        registration_key_id = str(
            registration_signature.get("key_id_sha256") or ""
        )
        if registration_key_id and registration_key_id in grader_key_ids:
            errors.append(
                "registration authority must use a key distinct from every grader"
            )
        randomization_signature = (
            randomization_receipt.get("signature")
            if isinstance(randomization_receipt, Mapping)
            and isinstance(randomization_receipt.get("signature"), Mapping)
            else {}
        )
        randomization_key_id = str(
            randomization_signature.get("key_id_sha256") or ""
        )
        if randomization_key_id and randomization_key_id in grader_key_ids:
            errors.append(
                "randomization authority must use a key distinct from every grader"
            )
        errors.extend(
            _scheduler_trace_audit_errors(
                archive,
                manifest,
                scheduler_trace_audit=scheduler_trace_audit,
                registration_receipt=registration_receipt,
                randomization_receipt=randomization_receipt,
                expected_run_count=len(run_ids),
                grader_key_ids=set(grader_key_ids),
                trusted_trace_keys=trusted_trace_keys,
            )
        )
    if len(grader_ids) < 2:
        errors.append(
            "general evidence requires two named, role-separated independent graders"
        )
    labels = grade.get("run_labels") if isinstance(grade, Mapping) else None
    if isinstance(labels, Mapping):
        labelled_run_ids = {str(item) for item in labels}
        if labelled_run_ids != run_ids:
            errors.append("independent grade run_ids must exactly equal the registered trials")
        if novelty_required:
            required_novelty_fields = {
                "correctness",
                "usefulness",
                "novelty",
                "non_rediscovery",
                "eventual_proof_contribution",
            }
            for run_id, label in labels.items():
                if not isinstance(label, Mapping) or not required_novelty_fields <= set(label):
                    errors.append(
                        f"novelty grade for {run_id} lacks the complete independent rubric"
                    )
                    break
    scoreboard = _read_json(
        _archive_file(archive, manifest.get("scoreboard_file"))
    )
    scoreboard_labels = (
        scoreboard.get("labels") if isinstance(scoreboard, Mapping) else None
    )
    if isinstance(scoreboard_labels, Mapping) and {
        str(item) for item in scoreboard_labels
    } != run_ids:
        errors.append("scoreboard run_ids must exactly equal the registered trials")

    grader_labels = grade.get("grader_labels") if isinstance(grade, Mapping) else None
    if not isinstance(grader_labels, Mapping):
        errors.append("general evidence requires separate labels from each independent grader")
        grader_labels = {}
    blinded_grading_manifest_sha256: str | None = None
    if protocol_version >= 6:
        blinded_manifest_path = _archive_file(
            archive, manifest.get("blinded_grading_manifest_file")
        )
        blinded_grading_manifest_sha256, blinded_manifest_hash_error = (
            _sha256_file(blinded_manifest_path)
            if blinded_manifest_path is not None
            else ("", "missing or unsafe path")
        )
        if blinded_manifest_hash_error:
            errors.append("cannot hash the blinded grading manifest")
            blinded_grading_manifest_sha256 = ""
    for grader_id in sorted(grader_ids):
        individual = grader_labels.get(grader_id)
        if not isinstance(individual, Mapping):
            errors.append(f"independent grader {grader_id} has no separate run_labels object")
            continue
        if {str(item) for item in individual} != run_ids:
            errors.append(
                f"independent grader {grader_id} labels do not exactly cover registered trials"
            )
        elif isinstance(labels, Mapping):
            disagreements = [
                run_id
                for run_id in run_ids
                if individual.get(run_id) != labels.get(run_id)
            ]
            if disagreements:
                errors.append(
                    f"independent grader {grader_id} labels disagree with the adjudicated labels"
                )
        receipt_path = _archive_file(
            archive, manifest.get("registration_receipt_file")
        )
        receipt_sha256, receipt_hash_error = (
            _sha256_file(receipt_path)
            if receipt_path is not None
            else ("", "missing or unsafe path")
        )
        if receipt_hash_error:
            errors.append(
                f"cannot hash registration receipt for grader {grader_id}"
            )
        else:
            errors.extend(
                _grader_signature_errors(
                    archive,
                    grader_record_by_id.get(grader_id),
                    grader_identity=grader_id,
                    labels=individual,
                    rubric_sha256=rubric_sha,
                    registration_receipt_sha256=receipt_sha256,
                    blinded_grading_attested=(
                        True if protocol_version >= 6 else None
                    ),
                    blinded_grading_manifest_sha256=(
                        blinded_grading_manifest_sha256
                        if protocol_version >= 6
                        else None
                    ),
                    trusted_grader_keys=trusted_grader_keys,
                )
            )

    outcomes: dict[tuple[str, str], list[float]] = {}
    if isinstance(labels, Mapping):
        for run_id, trial in trial_by_run_id.items():
            outcome = _binary_success_label(labels.get(run_id))
            if outcome is None:
                errors.append(
                    f"adjudicated label for {run_id} is not a recognized binary success outcome"
                )
                continue
            outcomes.setdefault(
                (
                    str(trial.get("problem_id") or ""),
                    str(trial.get("condition") or ""),
                ),
                [],
            ).append(outcome)

    intervals = (
        analysis.get("confidence_intervals")
        if isinstance(analysis, Mapping)
        else None
    )
    if not isinstance(intervals, Mapping):
        errors.append("statistical analysis must contain confidence_intervals")
        intervals = {}
    for endpoint in endpoints:
        interval = intervals.get(str(endpoint))
        if not isinstance(interval, Mapping):
            errors.append(f"statistical analysis lacks interval for endpoint {endpoint}")
            continue
        try:
            estimate = float(interval["estimate"])
            lower = float(interval["lower"])
            upper = float(interval["upper"])
            n_problems = int(interval["n_problems"])
            n_trials = int(interval["n_trials"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"confidence interval for {endpoint} is malformed")
            continue
        if not all(math.isfinite(value) for value in (estimate, lower, upper)):
            errors.append(f"confidence interval for {endpoint} contains a non-finite value")
        elif not (-1.0 <= lower <= estimate <= upper <= 1.0):
            errors.append(f"confidence interval for {endpoint} has invalid bounds")
        if n_problems != len(problem_ids) or n_trials != len(trials):
            errors.append(
                f"confidence interval for {endpoint} has inconsistent problem/trial counts"
            )
        if str(interval.get("unit_of_analysis") or "") != "problem":
            errors.append(
                f"confidence interval for {endpoint} must use problem as the unit of analysis"
            )
        if repeated_trials > 1 and not str(
            interval.get("dependence_adjustment") or ""
        ):
            errors.append(
                f"confidence interval for {endpoint} must account for repeated-trial dependence"
            )
        if not str(interval.get("method") or ""):
            errors.append(f"confidence interval for {endpoint} must name its method")
        elif str(interval.get("method") or "") != bootstrap_method:
            errors.append(
                f"confidence interval for {endpoint} disagrees with the analysis-plan method"
            )
        contrast = contrast_by_endpoint.get(str(endpoint))
        if contrast is not None and problem_ids:
            treatment = str(contrast["treatment_condition"])
            control = str(contrast["control_condition"])
            problem_effects: list[float] = []
            for problem_id in sorted(problem_ids):
                treatment_outcomes = outcomes.get((problem_id, treatment), [])
                control_outcomes = outcomes.get((problem_id, control), [])
                if not treatment_outcomes or not control_outcomes:
                    continue
                problem_effects.append(
                    sum(treatment_outcomes) / len(treatment_outcomes)
                    - sum(control_outcomes) / len(control_outcomes)
                )
            if len(problem_effects) != len(problem_ids):
                errors.append(
                    f"statistical analysis cannot reconstruct every problem-level effect for {endpoint}"
                )
            else:
                reconstructed = sum(problem_effects) / len(problem_effects)
                if not math.isclose(
                    estimate,
                    reconstructed,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    errors.append(
                        f"statistical analysis estimate for {endpoint} does not match the registered outcomes"
                    )
                if (
                    _valid_sha256(bootstrap_seed_sha256)
                    and 1_000 <= bootstrap_replicates <= 100_000
                    and bootstrap_replicates * len(problem_ids)
                    <= MAX_BOOTSTRAP_DRAWS
                    and bootstrap_quantile_rule
                    == "outer_order_statistics_v1"
                    and math.isfinite(power_alpha)
                    and 0.0 < power_alpha <= 0.10
                ):
                    expected_lower, expected_upper = (
                        _reproducible_cluster_bootstrap_interval(
                            problem_effects,
                            seed_sha256=bootstrap_seed_sha256,
                            endpoint=str(endpoint),
                            replicates=bootstrap_replicates,
                            alpha=power_alpha,
                        )
                    )
                    if not (
                        math.isclose(
                            lower,
                            expected_lower,
                            rel_tol=0.0,
                            abs_tol=1e-12,
                        )
                        and math.isclose(
                            upper,
                            expected_upper,
                            rel_tol=0.0,
                            abs_tol=1e-12,
                        )
                    ):
                        errors.append(
                            f"statistical analysis interval for {endpoint} does not match the registered outcomes and analysis plan"
                        )
    return errors


def _scheduler_calibration_assignment_errors(
    archive: Path,
    manifest: Mapping[str, Any],
    *,
    trials: list[Mapping[str, Any]],
    condition_spec_by_id: Mapping[str, Mapping[str, Any]],
    experiment_id: str,
    exploration_stratum: str,
    randomization_receipt: Any,
) -> list[str]:
    """Join registered trial conditions to replayable runtime assignments."""

    errors: list[str] = []
    preregistration_path = _archive_file(
        archive, manifest.get("preregistration_file")
    )
    receipt_path = _archive_file(
        archive, manifest.get("registration_receipt_file")
    )
    schedule_path = _archive_file(
        archive, manifest.get("assignment_schedule_file")
    )
    preregistration_sha256, preregistration_error = (
        _sha256_file(preregistration_path)
        if preregistration_path is not None
        else ("", "missing or unsafe path")
    )
    receipt_sha256, receipt_error = (
        _sha256_file(receipt_path)
        if receipt_path is not None
        else ("", "missing or unsafe path")
    )
    schedule_sha256, schedule_error = (
        _sha256_file(schedule_path)
        if schedule_path is not None
        else ("", "missing or unsafe path")
    )
    if preregistration_error or receipt_error or schedule_error:
        return [
            "scheduler calibration cannot hash its preregistration, receipt, and schedule"
        ]
    randomization_receipt_path = _archive_file(
        archive, manifest.get("randomization_receipt_file")
    )
    randomization_receipt_sha256, randomization_receipt_error = (
        _sha256_file(randomization_receipt_path)
        if randomization_receipt_path is not None
        else ("", "missing or unsafe path")
    )
    randomization_payload = (
        randomization_receipt.get("payload")
        if isinstance(randomization_receipt, Mapping)
        and isinstance(randomization_receipt.get("payload"), Mapping)
        else {}
    )
    if randomization_receipt_error:
        errors.append("scheduler calibration cannot hash its randomization receipt")
    expected_arms = [
        {
            "arm_id": condition_id,
            "policy_family": "parallel_admission",
            "selection_policy_version": int(
                condition_spec_by_id[condition_id]["selection_policy_version"]
            ),
            "policy_semantics_sha256": str(
                condition_spec_by_id[condition_id]["policy_semantics_sha256"]
            ),
        }
        for condition_id in sorted(condition_spec_by_id)
        if type(
            condition_spec_by_id[condition_id].get("selection_policy_version")
        )
        is int
    ]
    if len(expected_arms) != len(condition_spec_by_id):
        return ["scheduler calibration condition specifications are incomplete"]
    assignment_units_by_block: dict[tuple[str, int], dict[str, str]] = {}
    for trial in trials:
        block = (
            str(trial.get("problem_id") or ""),
            _safe_nonnegative_int(trial.get("repeat_index")),
        )
        assignment_units_by_block.setdefault(block, {})[
            str(trial.get("condition") or "")
        ] = str(trial.get("run_id") or "")
    all_certificates: list[Any] = []
    for index, trial in enumerate(trials):
        assignment_document = _read_json(
            _archive_file(archive, trial.get("scheduler_assignment_file"))
        )
        if not isinstance(assignment_document, Mapping) or set(
            assignment_document
        ) != {"trace_version", "run_id", "dispatches", "finalization"}:
            errors.append(
                f"trial {index} scheduler assignment document is noncanonical"
            )
            continue
        if assignment_document.get("trace_version") != 2:
            errors.append(
                f"trial {index} scheduler assignment trace version is unsupported"
            )
        run_id = str(trial.get("run_id") or "")
        if assignment_document.get("run_id") != run_id:
            errors.append(
                f"trial {index} scheduler assignment run_id disagrees"
            )
        dispatches = assignment_document.get("dispatches")
        if not isinstance(dispatches, list) or not dispatches:
            errors.append(
                f"trial {index} scheduler assignment requires at least one exposure"
            )
            continue
        if len(dispatches) > MAX_MANIFEST_LIST_ENTRIES:
            errors.append(
                f"trial {index} scheduler assignment exceeds the audit limit"
            )
            dispatches = dispatches[:MAX_MANIFEST_LIST_ENTRIES]
        condition_id = str(trial.get("condition") or "")
        condition_spec = condition_spec_by_id.get(condition_id, {})
        expected_policy_version = condition_spec.get(
            "selection_policy_version"
        )
        unit_inputs: set[str] = set()
        exposure_indices: set[int] = set()
        for exposure_position, dispatch in enumerate(dispatches):
            if not isinstance(dispatch, Mapping) or set(dispatch) != {
                "decision_trace",
                "dispatched_action",
            }:
                errors.append(
                    f"trial {index} scheduler dispatch {exposure_position} is noncanonical"
                )
                continue
            decision_trace = dispatch.get("decision_trace")
            dispatched_action = dispatch.get("dispatched_action")
            if not isinstance(decision_trace, Mapping) or not isinstance(
                dispatched_action, Mapping
            ):
                errors.append(
                    f"trial {index} scheduler dispatch {exposure_position} lacks trace or action"
                )
                continue
            try:
                observed_action_sha256 = action_sha256(dispatched_action)
            except (TypeError, ValueError, OverflowError, RecursionError):
                observed_action_sha256 = ""
            trace_errors = decision_trace_errors(decision_trace)
            if trace_errors:
                errors.append(
                    f"trial {index} scheduler dispatch {exposure_position} has an invalid decision trace: "
                    + "; ".join(trace_errors)
                )
            certificate = decision_trace.get("randomized_assignment")
            wave = decision_trace.get("parallel_wave_admission")
            observed_parallel_version = (
                wave.get("policy_version")
                if isinstance(wave, Mapping)
                and type(wave.get("policy_version")) is int
                else -1
            )
            if (
                observed_action_sha256
                != decision_trace.get("dispatched_action_sha256")
            ):
                errors.append(
                    f"trial {index} scheduler dispatch {exposure_position} action commitment is inconsistent"
                )
            if observed_parallel_version != expected_policy_version:
                errors.append(
                    f"trial {index} scheduler dispatch {exposure_position} executed the wrong parallel policy"
                )
            certificate_errors = randomized_assignment_errors(
                certificate,
                candidate_set_sha256=str(
                    decision_trace.get("candidate_set_sha256") or ""
                ),
                dispatched_action_sha256=observed_action_sha256,
                parallel_admission_policy_version=(
                    expected_policy_version
                    if type(expected_policy_version) is int
                    else -1
                ),
            )
            if certificate_errors:
                errors.append(
                    f"trial {index} scheduler assignment exposure {exposure_position} is invalid: "
                    + "; ".join(certificate_errors)
                )
                continue
            if (
                certificate.get("protocol_version")
                != BLOCK_RANDOMIZED_ASSIGNMENT_PROTOCOL_VERSION
                or certificate.get("assignment_unit_id") != run_id
                or certificate.get("experiment_id") != experiment_id
                or certificate.get("exploration_stratum")
                != exploration_stratum
                or certificate.get("problem_id") != trial.get("problem_id")
                or certificate.get("problem_sha256")
                != trial.get("problem_sha256")
                or certificate.get("assignment_unit_ids")
                != assignment_units_by_block.get(
                    (
                        str(trial.get("problem_id") or ""),
                        _safe_nonnegative_int(trial.get("repeat_index")),
                    ),
                    {},
                )
                or certificate.get("repeat_index") != trial.get("repeat_index")
                or certificate.get("random_seed") != trial.get("random_seed")
                or certificate.get("execution_order")
                != trial.get("execution_order")
                or certificate.get("selected_arm_id") != condition_id
                or certificate.get("preregistration_sha256")
                != preregistration_sha256
                or certificate.get("registration_receipt_sha256")
                != receipt_sha256
                or certificate.get("assignment_schedule_sha256")
                != schedule_sha256
                or certificate.get("randomization_receipt_sha256")
                != randomization_receipt_sha256
                or certificate.get("randomness_source")
                != randomization_payload.get("randomness_source")
                or certificate.get("randomness_event_id")
                != randomization_payload.get("randomness_event_id")
                or certificate.get("randomness_sha256")
                != randomization_payload.get("randomness_sha256")
                or certificate.get("arms") != expected_arms
            ):
                errors.append(
                    f"trial {index} scheduler assignment does not match its registered condition"
                )
            unit_inputs.add(str(certificate.get("assignment_input_sha256") or ""))
            exposure_index = certificate.get("exposure_index")
            if type(exposure_index) is int:
                exposure_indices.add(exposure_index)
            all_certificates.append(certificate)
        finalization = assignment_document.get("finalization")
        finalization_fields = {
            "finalization_version",
            "complete",
            "dispatch_count",
            "last_exposure_index",
            "assignment_input_sha256",
            "dispatches_sha256",
            "event_log_sha256",
            "proof_snapshot_sha256",
            "result_sha256",
        }
        if not isinstance(finalization, Mapping) or set(
            finalization
        ) != finalization_fields:
            errors.append(
                f"trial {index} scheduler trace finalization is noncanonical"
            )
        else:
            try:
                dispatches_sha256 = hashlib.sha256(
                    canonical_signature_payload(dispatches)
                ).hexdigest()
            except (TypeError, ValueError, OverflowError, RecursionError):
                dispatches_sha256 = ""
            expected_assignment_input = (
                next(iter(unit_inputs)) if len(unit_inputs) == 1 else ""
            )
            finalization_checks = (
                finalization.get("finalization_version") == 1,
                finalization.get("complete") is True,
                type(finalization.get("dispatch_count")) is int
                and finalization.get("dispatch_count") == len(dispatches),
                type(finalization.get("last_exposure_index")) is int
                and finalization.get("last_exposure_index")
                == len(dispatches) - 1,
                finalization.get("assignment_input_sha256")
                == expected_assignment_input,
                finalization.get("dispatches_sha256") == dispatches_sha256,
                finalization.get("event_log_sha256")
                == trial.get("event_log_sha256"),
                finalization.get("proof_snapshot_sha256")
                == trial.get("proof_snapshot_sha256"),
                finalization.get("result_sha256") == trial.get("result_sha256"),
            )
            if not all(finalization_checks):
                errors.append(
                    f"trial {index} scheduler trace finalization is inconsistent"
                )
        if len(unit_inputs) != 1:
            errors.append(
                f"trial {index} scheduler assignment changes within the workflow"
            )
        if exposure_indices != set(range(len(dispatches))):
            errors.append(
                f"trial {index} scheduler assignment exposures are not contiguous from zero"
            )
    block_errors = randomized_block_assignment_cohort_errors(all_certificates)
    errors.extend(
        f"scheduler calibration: {error}" for error in block_errors
    )
    return errors


def _scheduler_trace_audit_errors(
    archive: Path,
    manifest: Mapping[str, Any],
    *,
    scheduler_trace_audit: Any,
    registration_receipt: Any,
    randomization_receipt: Any,
    expected_run_count: int,
    grader_key_ids: set[str],
    trusted_trace_keys: Mapping[str, Path],
) -> list[str]:
    """Authenticate a role-separated audit of the complete scheduler traces."""

    if not isinstance(scheduler_trace_audit, Mapping):
        return ["protocol v6 requires a readable scheduler trace audit receipt"]
    payload = scheduler_trace_audit.get("payload")
    signature_card = scheduler_trace_audit.get("signature")
    if not isinstance(payload, Mapping) or not isinstance(signature_card, Mapping):
        return ["scheduler trace audit payload and signature must be objects"]
    errors: list[str] = []
    required_payload_fields = {
        "receipt_version",
        "issued_at",
        "registration_receipt_sha256",
        "randomization_receipt_sha256",
        "trial_manifest_sha256",
        "blinded_grading_manifest_sha256",
        "independent_grade_sha256",
        "scheduler_trace_completeness_attested",
        "labels_finalized_before_trace_review_attested",
        "trace_auditor_excluded_from_grading",
        "reviewed_run_count",
    }
    if set(payload) != required_payload_fields:
        errors.append("scheduler trace audit payload fields are not canonical")
    if payload.get("receipt_version") != 1:
        errors.append("scheduler trace audit receipt version is unsupported")
    for field in (
        "scheduler_trace_completeness_attested",
        "labels_finalized_before_trace_review_attested",
        "trace_auditor_excluded_from_grading",
    ):
        if payload.get(field) is not True:
            errors.append(f"scheduler trace audit must set {field}=true")
    if (
        type(payload.get("reviewed_run_count")) is not int
        or payload.get("reviewed_run_count") != expected_run_count
    ):
        errors.append("scheduler trace audit reviewed_run_count is inconsistent")
    for payload_field, manifest_field in (
        ("registration_receipt_sha256", "registration_receipt_file"),
        ("randomization_receipt_sha256", "randomization_receipt_file"),
        ("trial_manifest_sha256", "trial_manifest_file"),
        (
            "blinded_grading_manifest_sha256",
            "blinded_grading_manifest_file",
        ),
        ("independent_grade_sha256", "independent_grade_file"),
    ):
        target = _archive_file(archive, manifest.get(manifest_field))
        observed_sha256, hash_error = (
            _sha256_file(target)
            if target is not None
            else ("", "missing or unsafe path")
        )
        if hash_error or payload.get(payload_field) != observed_sha256:
            errors.append(
                f"scheduler trace audit {payload_field} does not match {manifest_field}"
            )
    randomization_payload = (
        randomization_receipt.get("payload")
        if isinstance(randomization_receipt, Mapping)
        and isinstance(randomization_receipt.get("payload"), Mapping)
        else {}
    )
    try:
        randomization_time = datetime.fromisoformat(
            str(randomization_payload.get("issued_at") or "").replace("Z", "+00:00")
        )
        trace_audit_time = datetime.fromisoformat(
            str(payload.get("issued_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        randomization_time = trace_audit_time = None
    if (
        randomization_time is None
        or trace_audit_time is None
        or randomization_time.tzinfo is None
        or trace_audit_time.tzinfo is None
        or trace_audit_time <= randomization_time
    ):
        errors.append(
            "scheduler trace audit must have a timezone-aware timestamp after randomization"
        )
    if set(signature_card) != {"algorithm", "key_id_sha256", "value_base64"}:
        errors.append("scheduler trace audit signature fields are not canonical")
    if signature_card.get("algorithm") != "ed25519":
        errors.append("scheduler trace audit signature algorithm must be ed25519")
    key_id = str(signature_card.get("key_id_sha256") or "")
    registration_signature = (
        registration_receipt.get("signature")
        if isinstance(registration_receipt, Mapping)
        and isinstance(registration_receipt.get("signature"), Mapping)
        else {}
    )
    randomization_signature = (
        randomization_receipt.get("signature")
        if isinstance(randomization_receipt, Mapping)
        and isinstance(randomization_receipt.get("signature"), Mapping)
        else {}
    )
    disallowed_key_ids = {
        str(registration_signature.get("key_id_sha256") or ""),
        str(randomization_signature.get("key_id_sha256") or ""),
        *grader_key_ids,
    }
    disallowed_key_ids.discard("")
    if key_id and key_id in disallowed_key_ids:
        errors.append(
            "scheduler trace auditor must use a key distinct from registration, randomization, and grading"
        )
    public_key_source = trusted_trace_keys.get(key_id)
    if public_key_source is None:
        errors.append(
            "scheduler trace audit key is not present in the out-of-band trust set"
        )
        return errors
    source = Path(public_key_source).expanduser()
    try:
        if source.is_symlink() or not source.is_file():
            raise ValueError("trusted scheduler trace audit key is not a regular file")
        public_key = source.resolve(strict=True)
        if public_key == archive or public_key.is_relative_to(archive):
            raise ValueError(
                "trusted scheduler trace audit key must be held outside the experiment archive"
            )
        observed_key_id = hashlib.sha256(public_key_der(public_key)).hexdigest()
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(f"cannot read trusted scheduler trace audit key: {exc}")
        return errors
    if observed_key_id != key_id:
        errors.append("trusted scheduler trace audit key identifier is inconsistent")
        return errors
    try:
        signature = base64.b64decode(
            str(signature_card.get("value_base64") or ""), validate=True
        )
    except (ValueError, TypeError):
        errors.append("scheduler trace audit signature is not valid base64")
        return errors
    try:
        signature_valid = verify_ed25519(
            canonical_signature_payload(payload), signature, public_key
        )
    except (OSError, RuntimeError, ValueError):
        signature_valid = False
    if not signature_valid:
        errors.append("scheduler trace audit Ed25519 signature is invalid")
    return errors


def _randomization_receipt_errors(
    archive: Path,
    manifest: Mapping[str, Any],
    *,
    preregistration: Any,
    registration_receipt: Any,
    randomization_receipt: Any,
    trusted_randomization_keys: Mapping[str, Path],
) -> list[str]:
    """Authenticate post-registration randomness and its block-seed rule."""

    if not isinstance(randomization_receipt, Mapping):
        return ["protocol v6 requires a readable randomization receipt"]
    payload = randomization_receipt.get("payload")
    signature_card = randomization_receipt.get("signature")
    if not isinstance(payload, Mapping) or not isinstance(signature_card, Mapping):
        return ["randomization receipt payload and signature must be objects"]
    errors: list[str] = []
    required_payload_fields = {
        "receipt_version",
        "issued_at",
        "registration_receipt_sha256",
        "assignment_schedule_sha256",
        "randomness_source",
        "randomness_event_id",
        "randomness_sha256",
        "block_seed_derivation_algorithm",
    }
    if set(payload) != required_payload_fields:
        errors.append("randomization receipt payload fields are not canonical")
    if payload.get("receipt_version") != 1:
        errors.append("randomization receipt version is unsupported")
    if payload.get(
        "block_seed_derivation_algorithm"
    ) != BLOCK_RANDOMIZED_SEED_DERIVATION_ALGORITHM:
        errors.append("randomization receipt seed derivation algorithm is unsupported")
    if not _valid_sha256(str(payload.get("randomness_sha256") or "")):
        errors.append("randomization receipt randomness_sha256 is invalid")
    if isinstance(preregistration, Mapping):
        for field in (
            "randomness_source",
            "randomness_event_id",
            "block_seed_derivation_algorithm",
        ):
            if payload.get(field) != preregistration.get(field):
                errors.append(
                    f"randomization receipt {field} disagrees with the preregistration"
                )
    registration_path = _archive_file(
        archive, manifest.get("registration_receipt_file")
    )
    registration_sha256, registration_hash_error = (
        _sha256_file(registration_path)
        if registration_path is not None
        else ("", "missing or unsafe path")
    )
    schedule_path = _archive_file(archive, manifest.get("assignment_schedule_file"))
    schedule_sha256, schedule_hash_error = (
        _sha256_file(schedule_path)
        if schedule_path is not None
        else ("", "missing or unsafe path")
    )
    if (
        registration_hash_error
        or payload.get("registration_receipt_sha256") != registration_sha256
    ):
        errors.append(
            "randomization receipt does not bind the registered preregistration receipt"
        )
    if (
        schedule_hash_error
        or payload.get("assignment_schedule_sha256") != schedule_sha256
    ):
        errors.append("randomization receipt does not bind the assignment schedule")
    registration_payload = (
        registration_receipt.get("payload")
        if isinstance(registration_receipt, Mapping)
        and isinstance(registration_receipt.get("payload"), Mapping)
        else {}
    )
    try:
        registration_time = datetime.fromisoformat(
            str(registration_payload.get("issued_at") or "").replace("Z", "+00:00")
        )
        randomization_time = datetime.fromisoformat(
            str(payload.get("issued_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        registration_time = randomization_time = None
    if (
        registration_time is None
        or randomization_time is None
        or registration_time.tzinfo is None
        or randomization_time.tzinfo is None
        or randomization_time <= registration_time
    ):
        errors.append(
            "randomization receipt must have a timezone-aware timestamp after registration"
        )
    if set(signature_card) != {"algorithm", "key_id_sha256", "value_base64"}:
        errors.append("randomization receipt signature fields are not canonical")
    if signature_card.get("algorithm") != "ed25519":
        errors.append("randomization receipt signature algorithm must be ed25519")
    key_id = str(signature_card.get("key_id_sha256") or "")
    registration_signature = (
        registration_receipt.get("signature")
        if isinstance(registration_receipt, Mapping)
        and isinstance(registration_receipt.get("signature"), Mapping)
        else {}
    )
    if key_id and key_id == registration_signature.get("key_id_sha256"):
        errors.append(
            "randomization authority must use a key distinct from the registration authority"
        )
    public_key_source = trusted_randomization_keys.get(key_id)
    if public_key_source is None:
        errors.append(
            "randomization receipt key is not present in the out-of-band trust set"
        )
        return errors
    source = Path(public_key_source).expanduser()
    try:
        if source.is_symlink() or not source.is_file():
            raise ValueError("trusted randomization key is not a regular file")
        public_key = source.resolve(strict=True)
        if public_key == archive or public_key.is_relative_to(archive):
            raise ValueError(
                "trusted randomization key must be held outside the experiment archive"
            )
        observed_key_id = hashlib.sha256(public_key_der(public_key)).hexdigest()
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(f"cannot read trusted randomization key: {exc}")
        return errors
    if observed_key_id != key_id:
        errors.append("trusted randomization key identifier is inconsistent")
        return errors
    try:
        signature = base64.b64decode(
            str(signature_card.get("value_base64") or ""), validate=True
        )
    except (ValueError, TypeError):
        errors.append("randomization receipt signature is not valid base64")
        return errors
    try:
        signature_valid = verify_ed25519(
            canonical_signature_payload(payload), signature, public_key
        )
    except (OSError, RuntimeError, ValueError):
        signature_valid = False
    if not signature_valid:
        errors.append("randomization receipt Ed25519 signature is invalid")
    return errors


def _registration_receipt_errors(
    archive: Path,
    manifest: Mapping[str, Any],
    *,
    preregistration: Any,
    receipt: Any,
    trusted_registration_keys: Mapping[str, Path],
) -> list[str]:
    """Verify an out-of-band signature over the preregistered documents."""

    errors: list[str] = []
    if not isinstance(receipt, Mapping):
        return ["general evidence requires a readable registration receipt"]
    payload = receipt.get("payload")
    signature_card = receipt.get("signature")
    if not isinstance(payload, Mapping) or not isinstance(signature_card, Mapping):
        return ["registration receipt payload and signature must be objects"]
    required_payload_fields = {
        "receipt_version",
        "issued_at",
        "preregistration_sha256",
        "selection_rule_sha256",
        "analysis_plan_sha256",
        "assignment_schedule_sha256",
        "grader_protocol_sha256",
        "rubric_sha256",
    }
    if set(payload) != required_payload_fields:
        errors.append("registration receipt payload fields are not canonical")
    if payload.get("receipt_version") != 1:
        errors.append("registration receipt version is unsupported")
    issued_at = str(payload.get("issued_at") or "")
    try:
        parsed_issued_at = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
    except ValueError:
        parsed_issued_at = None
    if parsed_issued_at is None or parsed_issued_at.tzinfo is None:
        errors.append("registration receipt issued_at must be an ISO-8601 timestamp with timezone")
    document_fields = (
        ("preregistration_sha256", "preregistration_file"),
        ("selection_rule_sha256", "selection_rule_file"),
        ("analysis_plan_sha256", "analysis_plan_file"),
        ("assignment_schedule_sha256", "assignment_schedule_file"),
        ("grader_protocol_sha256", "grader_protocol_file"),
        ("rubric_sha256", "rubric_file"),
    )
    for payload_field, manifest_field in document_fields:
        document_path = _archive_file(archive, manifest.get(manifest_field))
        observed_sha256, hash_error = (
            _sha256_file(document_path)
            if document_path is not None
            else ("", "missing or unsafe path")
        )
        if hash_error or payload.get(payload_field) != observed_sha256:
            errors.append(
                f"registration receipt {payload_field} does not match {manifest_field}"
            )
    if isinstance(preregistration, Mapping):
        for field in (
            "selection_rule_sha256",
            "analysis_plan_sha256",
            "assignment_schedule_sha256",
            "grader_protocol_sha256",
            "rubric_sha256",
        ):
            if payload.get(field) != preregistration.get(field):
                errors.append(
                    f"registration receipt {field} disagrees with the preregistration"
                )
    if set(signature_card) != {"algorithm", "key_id_sha256", "value_base64"}:
        errors.append("registration receipt signature fields are not canonical")
    if signature_card.get("algorithm") != "ed25519":
        errors.append("registration receipt signature algorithm must be ed25519")
    key_id = str(signature_card.get("key_id_sha256") or "")
    public_key = trusted_registration_keys.get(key_id)
    if public_key is None:
        errors.append(
            "registration receipt key is not present in the out-of-band trust set"
        )
        return errors
    public_key_source = Path(public_key).expanduser()
    try:
        if public_key_source.is_symlink() or not public_key_source.is_file():
            raise ValueError("trusted registration key is not a regular file")
        public_key = public_key_source.resolve(strict=True)
        if public_key == archive or public_key.is_relative_to(archive):
            raise ValueError(
                "trusted registration key must be held outside the experiment archive"
            )
        observed_key_id = hashlib.sha256(public_key_der(public_key)).hexdigest()
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(f"cannot read trusted registration key: {exc}")
        return errors
    if observed_key_id != key_id:
        errors.append("trusted registration key identifier is inconsistent")
        return errors
    try:
        signature = base64.b64decode(
            str(signature_card.get("value_base64") or ""), validate=True
        )
    except (ValueError, TypeError):
        errors.append("registration receipt signature is not valid base64")
        return errors
    try:
        signature_valid = verify_ed25519(
            canonical_signature_payload(payload), signature, public_key
        )
    except (OSError, RuntimeError, ValueError):
        signature_valid = False
    if not signature_valid:
        errors.append("registration receipt Ed25519 signature is invalid")
    return errors


def _grader_signature_errors(
    archive: Path,
    grader_record: Any,
    *,
    grader_identity: str,
    labels: Mapping[str, Any],
    rubric_sha256: str,
    registration_receipt_sha256: str,
    blinded_grading_attested: bool | None,
    blinded_grading_manifest_sha256: str | None,
    trusted_grader_keys: Mapping[str, Path],
) -> list[str]:
    """Authenticate one grader's complete label map with an external key."""

    if not isinstance(grader_record, Mapping):
        return [f"independent grader {grader_identity} has no grader record"]
    signature_card = grader_record.get("signature")
    if not isinstance(signature_card, Mapping) or set(signature_card) != {
        "algorithm",
        "key_id_sha256",
        "value_base64",
    }:
        return [
            f"independent grader {grader_identity} signature fields are not canonical"
        ]
    errors: list[str] = []
    if signature_card.get("algorithm") != "ed25519":
        errors.append(
            f"independent grader {grader_identity} signature algorithm must be ed25519"
        )
    key_id = str(signature_card.get("key_id_sha256") or "")
    public_key_source = trusted_grader_keys.get(key_id)
    if public_key_source is None:
        errors.append(
            f"independent grader {grader_identity} key is not present in the out-of-band trust set"
        )
        return errors
    source = Path(public_key_source).expanduser()
    try:
        if source.is_symlink() or not source.is_file():
            raise ValueError("trusted grader key is not a regular file")
        public_key = source.resolve(strict=True)
        if public_key == archive or public_key.is_relative_to(archive):
            raise ValueError(
                "trusted grader key must be held outside the experiment archive"
            )
        observed_key_id = hashlib.sha256(public_key_der(public_key)).hexdigest()
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(
            f"cannot read trusted key for independent grader {grader_identity}: {exc}"
        )
        return errors
    if observed_key_id != key_id:
        errors.append(
            f"independent grader {grader_identity} key identifier is inconsistent"
        )
        return errors
    payload = {
        "signature_version": 2 if blinded_grading_attested is not None else 1,
        "grader_identity": grader_identity,
        "run_labels_sha256": hashlib.sha256(
            canonical_signature_payload(labels)
        ).hexdigest(),
        "rubric_sha256": rubric_sha256,
        "registration_receipt_sha256": registration_receipt_sha256,
    }
    if blinded_grading_attested is not None:
        payload["blinded_grading_attested"] = blinded_grading_attested
        payload["blinded_grading_manifest_sha256"] = (
            blinded_grading_manifest_sha256
        )
    try:
        signature = base64.b64decode(
            str(signature_card.get("value_base64") or ""), validate=True
        )
    except (ValueError, TypeError):
        errors.append(
            f"independent grader {grader_identity} signature is not valid base64"
        )
        return errors
    try:
        signature_valid = verify_ed25519(
            canonical_signature_payload(payload), signature, public_key
        )
    except (OSError, RuntimeError, ValueError):
        signature_valid = False
    if not signature_valid:
        errors.append(
            f"independent grader {grader_identity} Ed25519 signature is invalid"
        )
    return errors


def _binary_success_label(value: Any) -> float | None:
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"solved", "success", "correct"}:
            return 1.0
        if normalized in {"unsolved", "failed", "incorrect"}:
            return 0.0
        return None
    if isinstance(value, Mapping):
        correctness = str(value.get("correctness") or "").strip().casefold()
        if correctness == "correct":
            return 1.0
        if correctness in {"incorrect", "unsolved"}:
            return 0.0
    return None


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _uniform_index_from_sha256(
    *,
    seed_sha256: str,
    endpoint: str,
    replicate: int,
    draw: int,
    population_size: int,
) -> int:
    range_size = 1 << 256
    acceptance_limit = range_size - (range_size % population_size)
    counter = 0
    while True:
        digest = hashlib.sha256(
            json.dumps(
                {
                    "algorithm": "sha256 problem-cluster bootstrap percentile v1",
                    "seed_sha256": seed_sha256,
                    "endpoint": endpoint,
                    "replicate": replicate,
                    "draw": draw,
                    "rejection_counter": counter,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        value = int(digest, 16)
        if value < acceptance_limit:
            return value % population_size
        counter += 1


def _reproducible_cluster_bootstrap_interval(
    problem_effects: list[float],
    *,
    seed_sha256: str,
    endpoint: str,
    replicates: int,
    alpha: float,
) -> tuple[float, float]:
    """Recompute the preregistered paired problem-cluster percentile interval."""

    population_size = len(problem_effects)
    bootstrap_estimates: list[float] = []
    for replicate in range(replicates):
        total = 0.0
        for draw in range(population_size):
            index = _uniform_index_from_sha256(
                seed_sha256=seed_sha256,
                endpoint=endpoint,
                replicate=replicate,
                draw=draw,
                population_size=population_size,
            )
            total += problem_effects[index]
        bootstrap_estimates.append(total / population_size)
    bootstrap_estimates.sort()
    last = replicates - 1
    lower_index = math.floor((alpha / 2.0) * last)
    upper_index = math.ceil((1.0 - alpha / 2.0) * last)
    return (
        bootstrap_estimates[lower_index],
        bootstrap_estimates[upper_index],
    )


def _safe_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, result)


def _archive_file(archive: Path, relative: Any) -> Path | None:
    text = str(relative or "")
    if not text:
        return None
    relative_path = Path(text)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    current = archive
    try:
        for part in relative_path.parts:
            if part in {"", "."}:
                continue
            current = current / part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                break
            if stat.S_ISLNK(mode):
                return None
        path = (archive / relative_path).resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None
    return path if path.is_relative_to(archive) else None


def _bounded_text(
    path: Path,
    *,
    maximum_bytes: int,
    errors: str = "strict",
) -> str:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("path is not a regular file")
    if info.st_size > maximum_bytes:
        raise ValueError(
            f"file exceeds the {maximum_bytes}-byte audit limit"
        )
    with path.open("r", encoding="utf-8", errors=errors) as handle:
        text = handle.read(maximum_bytes + 1)
    if len(text.encode("utf-8", errors="replace")) > maximum_bytes:
        raise ValueError(f"file grew beyond the {maximum_bytes}-byte audit limit")
    return text


def _load_bounded_json(path: Path) -> Any:
    text = _bounded_text(path, maximum_bytes=MAX_STRUCTURED_FILE_BYTES)
    return json.loads(text)


def _sha256_file(path: Path) -> tuple[str, str]:
    digest = hashlib.sha256()
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            return "", "path is not a regular file"
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        return "", str(exc)
    return digest.hexdigest(), ""


def _files_equal(left: Path, right: Path) -> bool:
    try:
        left_info = left.lstat()
        right_info = right.lstat()
        if not stat.S_ISREG(left_info.st_mode) or not stat.S_ISREG(right_info.st_mode):
            return False
        if left_info.st_size != right_info.st_size:
            return False
        with left.open("rb") as left_handle, right.open("rb") as right_handle:
            while True:
                left_block = left_handle.read(1024 * 1024)
                right_block = right_handle.read(1024 * 1024)
                if left_block != right_block:
                    return False
                if not left_block:
                    return True
    except OSError:
        return False


def _combined_text(
    archive: Path,
    relative_paths: list[str],
    *,
    label: str,
) -> tuple[str, list[str]]:
    errors: list[str] = []
    chunks: list[str] = []
    total_bytes = 0
    for relative in sorted({item for item in relative_paths if item}):
        path = _archive_file(archive, relative)
        if path is None or not path.is_file():
            errors.append(f"{label} file is missing or unsafe: {relative}")
            continue
        try:
            size = path.lstat().st_size
            if size > MAX_TEXT_EVIDENCE_BYTES:
                raise ValueError(
                    f"file exceeds the {MAX_TEXT_EVIDENCE_BYTES}-byte text audit limit"
                )
            if total_bytes + size > MAX_COMBINED_TEXT_BYTES:
                raise ValueError(
                    f"combined text exceeds the {MAX_COMBINED_TEXT_BYTES}-byte audit limit"
                )
            chunks.append(
                _bounded_text(
                    path,
                    maximum_bytes=MAX_TEXT_EVIDENCE_BYTES,
                    errors="replace",
                )
            )
            total_bytes += size
        except (OSError, ValueError) as exc:
            errors.append(f"cannot audit {label} file {relative}: {exc}")
    return "\n".join(chunks), errors


def _read_json(path: Path | None) -> Any:
    if path is None or not path.is_file():
        return None
    try:
        return _load_bounded_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None


def _read_json_lines(
    path: Path | None, *, label: str = "JSONL file"
) -> tuple[list[Any], list[str]]:
    if path is None or not path.is_file():
        return [], [f"{label} is missing"]
    rows: list[Any] = []
    errors: list[str] = []
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            return [], [f"{label} is not a regular file"]
        if info.st_size > MAX_STRUCTURED_FILE_BYTES:
            return [], [
                f"{label} exceeds the {MAX_STRUCTURED_FILE_BYTES}-byte audit limit"
            ]
        with path.open("rb") as handle:
            for line_number, raw_bytes in enumerate(handle, start=1):
                if len(raw_bytes) > MAX_JSONL_LINE_BYTES:
                    errors.append(
                        f"{label} line {line_number} exceeds the "
                        f"{MAX_JSONL_LINE_BYTES}-byte audit limit"
                    )
                    continue
                if not raw_bytes.strip():
                    continue
                if len(rows) >= MAX_MANIFEST_LIST_ENTRIES:
                    errors.append(
                        f"{label} exceeds the {MAX_MANIFEST_LIST_ENTRIES}-record audit limit"
                    )
                    break
                try:
                    raw = raw_bytes.decode("utf-8")
                    rows.append(json.loads(raw))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    errors.append(f"{label} line {line_number} is not valid UTF-8 JSON")
    except OSError as exc:
        return [], [f"{label} is unreadable: {exc}"]
    if not rows:
        errors.append(f"{label} contains no records")
    return rows, errors


def _checksum_target_names(path: Path) -> set[str]:
    try:
        lines = _bounded_text(
            path,
            maximum_bytes=MAX_CHECKSUM_FILE_BYTES,
        ).splitlines()
    except (OSError, UnicodeDecodeError, ValueError):
        return set()
    result: set[str] = set()
    for raw in lines:
        _, separator, relative = raw.strip().partition("  ")
        if separator and relative:
            result.add(relative.lstrip("*"))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Audit Albilich experiment archives"
    )
    parser.add_argument(
        "--experiments-root",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "experiments",
    )
    parser.add_argument(
        "--trusted-registration-key",
        action="append",
        type=Path,
        default=[],
        help=(
            "out-of-band Ed25519 public key trusted to issue preregistration "
            "receipts; may be supplied more than once"
        ),
    )
    parser.add_argument(
        "--trusted-grader-key",
        action="append",
        type=Path,
        default=[],
        help=(
            "out-of-band Ed25519 public key trusted to authenticate one "
            "independent grader; may be supplied more than once"
        ),
    )
    parser.add_argument(
        "--trusted-randomization-key",
        action="append",
        type=Path,
        default=[],
        help=(
            "out-of-band Ed25519 public key trusted to authenticate a "
            "post-registration randomness receipt; may be supplied more than once"
        ),
    )
    parser.add_argument(
        "--trusted-trace-key",
        action="append",
        type=Path,
        default=[],
        help=(
            "out-of-band Ed25519 public key trusted to authenticate the "
            "unblinded scheduler trace audit; may be supplied more than once"
        ),
    )
    arguments = parser.parse_args()
    trusted_keys: dict[str, Path] = {}
    key_errors: list[str] = []
    for key_path in arguments.trusted_registration_key:
        try:
            resolved_key = key_path.expanduser().resolve(strict=True)
            key_id = hashlib.sha256(public_key_der(resolved_key)).hexdigest()
        except (OSError, RuntimeError, ValueError) as exc:
            key_errors.append(f"cannot load trusted registration key {key_path}: {exc}")
            continue
        if key_id in trusted_keys and trusted_keys[key_id] != resolved_key:
            key_errors.append(f"duplicate trusted registration key id: {key_id}")
            continue
        trusted_keys[key_id] = resolved_key
    trusted_grader_keys: dict[str, Path] = {}
    for key_path in arguments.trusted_grader_key:
        try:
            resolved_key = key_path.expanduser().resolve(strict=True)
            key_id = hashlib.sha256(public_key_der(resolved_key)).hexdigest()
        except (OSError, RuntimeError, ValueError) as exc:
            key_errors.append(f"cannot load trusted grader key {key_path}: {exc}")
            continue
        if key_id in trusted_grader_keys and trusted_grader_keys[key_id] != resolved_key:
            key_errors.append(f"duplicate trusted grader key id: {key_id}")
            continue
        trusted_grader_keys[key_id] = resolved_key
    trusted_randomization_keys: dict[str, Path] = {}
    for key_path in arguments.trusted_randomization_key:
        try:
            resolved_key = key_path.expanduser().resolve(strict=True)
            key_id = hashlib.sha256(public_key_der(resolved_key)).hexdigest()
        except (OSError, RuntimeError, ValueError) as exc:
            key_errors.append(
                f"cannot load trusted randomization key {key_path}: {exc}"
            )
            continue
        if (
            key_id in trusted_randomization_keys
            and trusted_randomization_keys[key_id] != resolved_key
        ):
            key_errors.append(f"duplicate trusted randomization key id: {key_id}")
            continue
        trusted_randomization_keys[key_id] = resolved_key
    trusted_trace_keys: dict[str, Path] = {}
    for key_path in arguments.trusted_trace_key:
        try:
            resolved_key = key_path.expanduser().resolve(strict=True)
            key_id = hashlib.sha256(public_key_der(resolved_key)).hexdigest()
        except (OSError, RuntimeError, ValueError) as exc:
            key_errors.append(f"cannot load trusted trace key {key_path}: {exc}")
            continue
        if key_id in trusted_trace_keys and trusted_trace_keys[key_id] != resolved_key:
            key_errors.append(f"duplicate trusted trace key id: {key_id}")
            continue
        trusted_trace_keys[key_id] = resolved_key
    report = audit_experiment_archives(
        arguments.experiments_root,
        trusted_registration_keys=trusted_keys,
        trusted_randomization_keys=trusted_randomization_keys,
        trusted_trace_keys=trusted_trace_keys,
        trusted_grader_keys=trusted_grader_keys,
    )
    if key_errors:
        report["errors"] = [*key_errors, *report["errors"]]
        report["valid"] = False
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["valid"] else 1)
