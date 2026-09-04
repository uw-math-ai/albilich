from __future__ import annotations

"""Versioned declaration of scheduler candidate-generator ownership."""

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Sequence


CANDIDATE_GENERATOR_GRAPH_VERSION = 5
SUPPORTED_CANDIDATE_GENERATOR_GRAPH_VERSIONS = (1, 2, 3, 4, 5)
CANDIDATE_GENERATOR_MANIFEST_VERSION = 2
CANDIDATE_GENERATOR_BOUND_DECISION_POLICY_VERSION = 8
_SUPPORTED_CANDIDATE_GENERATOR_MANIFEST_VERSIONS = frozenset({1, 2})
_SKIP_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class CandidateGeneratorSpec:
    scope_id: str
    generator_id: str
    producer: str
    cardinality: str
    child_scope_id: str = ""


CANDIDATE_GENERATOR_GRAPH_V2: tuple[CandidateGeneratorSpec, ...] = (
    CandidateGeneratorSpec("top_level", "base_planner", "_plan_next_action", "exactly_one"),
    CandidateGeneratorSpec("top_level", "approach_portfolio", "approach_brainstorming_trigger", "zero_or_one"),
    CandidateGeneratorSpec("top_level", "reference_solution_reconstruction", "reference_solution_state", "zero_or_one"),
    CandidateGeneratorSpec("top_level", "approach_pilot", "selected_approach_candidate", "zero_or_one"),
    CandidateGeneratorSpec("top_level", "selected_bridge", "selected_bridge_candidate", "zero_or_one"),
    CandidateGeneratorSpec("top_level", "selected_conjecture", "selected_conjecture_candidate", "zero_or_one"),
    CandidateGeneratorSpec("top_level", "conceptual_invariant", "conceptual_invariant_trigger", "zero_or_one"),
    CandidateGeneratorSpec("top_level", "definition_invention", "active_invention_authorization", "zero_or_one"),
    CandidateGeneratorSpec("top_level", "proof_compression", "advisor_synthesis_trigger", "zero_or_one"),
    CandidateGeneratorSpec("top_level", "advisor_synthesis", "advisor_synthesis_trigger", "zero_or_one"),
    CandidateGeneratorSpec("parallel_wave", "peer_verification", "_verifier_candidate_actions", "zero_or_more"),
    CandidateGeneratorSpec("parallel_wave", "long_session_verification", "_verifier_candidate_action", "zero_or_one"),
    CandidateGeneratorSpec("parallel_wave", "support_theorem_precheck", "_support_lemma_precheck_actions", "zero_or_more"),
    CandidateGeneratorSpec("parallel_wave", "advisor_synthesis", "_advisor_evidence_synthesis_action", "zero_or_one"),
    CandidateGeneratorSpec("parallel_wave", "exact_support_theorem_search", "_verifier_blocked_citation_actions", "zero_or_more"),
    CandidateGeneratorSpec("parallel_wave", "counterexample_search", "_counterexample_companion_action", "zero_or_one"),
    CandidateGeneratorSpec("parallel_wave", "parallel_decomposition", "_parallel_decomposition_companion_actions", "zero_or_more"),
    CandidateGeneratorSpec("parallel_wave", "researcher", "_researcher_candidate_action", "zero_or_one"),
    CandidateGeneratorSpec("parallel_wave", "research_strategy", "next_strategy_operation", "zero_or_one"),
    CandidateGeneratorSpec("parallel_wave", "literature_scan", "should_run_librarian", "zero_or_one"),
    CandidateGeneratorSpec("parallel_wave", "independent_integration", "_integration_candidates", "zero_or_more"),
    CandidateGeneratorSpec("parallel_wave", "background_planner", "next_action", "zero_or_one"),
    CandidateGeneratorSpec("parallel_wave", "verifier_capacity", "_verifier_candidate_actions", "zero_or_more"),
    CandidateGeneratorSpec("parallel_wave", "multi_branch", "multi_branch_research_actions", "zero_or_more"),
    CandidateGeneratorSpec("parallel_wave", "caller_supplied", "_admit_parallel_companion_candidates", "zero_or_more"),
    CandidateGeneratorSpec("precondition", "context_request", "_pending_context_request_actions", "zero_or_more"),
    CandidateGeneratorSpec("precondition", "external_writing_revision", "_external_writing_revision_action", "zero_or_one"),
    CandidateGeneratorSpec("precondition", "paper_audit", "_paper_audit_verification_only_action", "zero_or_one"),
    CandidateGeneratorSpec("precondition", "publication_route_repair", "_publication_route_error_research_action", "zero_or_one"),
    CandidateGeneratorSpec("precondition", "formalization", "_requested_formalization_actions", "zero_or_more"),
    CandidateGeneratorSpec("solved_root", "final_proof_writing", "_final_proof_writing_action", "zero_or_one"),
    CandidateGeneratorSpec("solved_root", "post_integration_literature", "_post_integration_literature_action", "zero_or_one"),
    CandidateGeneratorSpec("solved_root", "document_delivery", "_writing_gate_action", "zero_or_one"),
    CandidateGeneratorSpec("solved_root", "terminal_completion", "_solved_root_terminal_action", "zero_or_one"),
    CandidateGeneratorSpec("integration", "verified_route", "_integration_action_for_candidate", "zero_or_more"),
    CandidateGeneratorSpec("verification", "advisor_strict_verification", "_advisor_requested_strict_verifier_action", "zero_or_one"),
    CandidateGeneratorSpec("verification", "fresh_proof_evidence", "_proof_evidence_handoff_actions", "zero_or_more"),
    CandidateGeneratorSpec("verification", "verifier_loop_classification", "_verifier_loop_classification_actions", "zero_or_more"),
    CandidateGeneratorSpec("verification", "support_theorem_precheck", "_support_lemma_precheck_actions", "zero_or_more"),
    CandidateGeneratorSpec("verification", "verifier_ready_route", "_verifier_candidate_actions", "zero_or_more"),
    CandidateGeneratorSpec("verification", "counterexample_validation", "_counterexample_validation_actions", "zero_or_more"),
    CandidateGeneratorSpec("verification", "dependency_threat_revalidation", "_threat_revalidation_actions", "zero_or_more"),
    CandidateGeneratorSpec("verification", "advisor_counterexample_validation", "_advisor_requested_validation_action", "zero_or_one"),
    CandidateGeneratorSpec("verification", "advisor_adversarial_review", "_advisor_requested_villain_action", "zero_or_one"),
    CandidateGeneratorSpec("verification", "unrouted_proof_assembly", "_unrouted_proof_claim_actions", "zero_or_more"),
    CandidateGeneratorSpec("evidence", "exact_support_theorem_search", "_verifier_blocked_citation_actions", "zero_or_more"),
    CandidateGeneratorSpec("evidence", "source_adaptation", "_source_adaptation_actions", "zero_or_more"),
    CandidateGeneratorSpec("evidence", "proved_lemma_extraction", "_proof_candidate_route_conversion_actions", "zero_or_more"),
    CandidateGeneratorSpec("evidence", "proof_draft_route_conversion", "_proof_candidate_route_conversion_actions", "zero_or_more"),
    CandidateGeneratorSpec("evidence", "executive_bottleneck_review", "_executive_advisor_bottleneck_action", "zero_or_one"),
    CandidateGeneratorSpec("evidence", "near_solution_proof_spine", "_near_solution_spine_synthesis_action", "zero_or_one"),
    CandidateGeneratorSpec("evidence", "stream_stall_recovery", "_stream_stall_recovery_action", "zero_or_one"),
    CandidateGeneratorSpec("evidence", "external_citation_check", "_external_citation_actions", "zero_or_more"),
    CandidateGeneratorSpec("evidence", "definition_audit", "_definition_audit_actions", "zero_or_more"),
    CandidateGeneratorSpec("recovery", "bottleneck_lock", "_bottleneck_lock_actions", "zero_or_more"),
    CandidateGeneratorSpec("recovery", "advisor_followup", "_advisor_followup_research_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "productive_branch_persistence", "_branch_persistence_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "duplicate_work_guard", "_duplicate_work_suppression_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "retrieve_reduce_circuit_breaker", "_retrieve_reduce_loop_advisor_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "no_content_guard", "_no_content_research_guard_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "proof_architecture", "_proof_architecture_pressure_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "creative_proof_attack", "_creative_proof_attack_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "parallel_wave_synthesis", "_parallel_wave_synthesis_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "global_synthesis", "_global_synthesis_action", "zero_or_one"),
    CandidateGeneratorSpec("recovery", "no_result_synthesis", "_no_result_search_synthesis_action", "zero_or_one"),
    CandidateGeneratorSpec("obligation", "blocking_obligation", "_blocking_debt_action", "zero_or_more"),
    CandidateGeneratorSpec("obligation", "requested_literature_search", "_requested_literature_actions", "zero_or_more"),
    CandidateGeneratorSpec("obligation", "source_synthesis", "_source_synthesis_action", "zero_or_one"),
    CandidateGeneratorSpec("obligation", "route_decision", "_route_decision_triage_actions", "zero_or_more"),
    CandidateGeneratorSpec("obligation", "paused_route_replacement", "_route_pause_replacement_action", "zero_or_one"),
    CandidateGeneratorSpec("obligation", "obstruction_conversion", "_obstruction_route_conversion_actions", "zero_or_more"),
    CandidateGeneratorSpec("obligation", "route_proof_quota", "_route_proof_construction_quota_actions", "zero_or_more"),
    CandidateGeneratorSpec("obligation", "failed_decomposition_regulation", "_failed_decomposition_actions", "zero_or_more"),
    CandidateGeneratorSpec("obligation", "blocked_decomposition_regulation", "_blocked_decomposition_actions", "zero_or_more"),
    CandidateGeneratorSpec("residual", "decomposition_step", "_decomposition_step_actions", "zero_or_more"),
    CandidateGeneratorSpec("residual", "route_triage", "_route_triage_actions", "zero_or_more"),
    CandidateGeneratorSpec("residual", "recursive_drift_stop", "_recursive_drift_stop_action", "zero_or_one"),
    CandidateGeneratorSpec("residual", "research_librarian", "_research_librarian_action", "zero_or_one"),
    CandidateGeneratorSpec("residual", "root_alignment", "_root_alignment_actions", "zero_or_more"),
    CandidateGeneratorSpec("residual", "proof_compression", "_proof_compression_actions", "zero_or_more"),
    CandidateGeneratorSpec("residual", "frontier_pressure", "_frontier_pressure_action", "zero_or_one"),
    CandidateGeneratorSpec("residual", "unverified_claim", "_next_unverified_claim_actions", "zero_or_more"),
    CandidateGeneratorSpec("residual", "fallback_retrieval", "_residual_fallback_action", "zero_or_one"),
    CandidateGeneratorSpec("open_problem", "refuted_root_revision", "_refuted_root_revision_action", "zero_or_one"),
    CandidateGeneratorSpec("open_problem", "verified_route_integration", "_integration_gate_action", "zero_or_one", "integration"),
    CandidateGeneratorSpec("open_problem", "post_integration_proof_spine", "_post_integration_proof_spine_action", "zero_or_one"),
    CandidateGeneratorSpec("open_problem", "periodic_mathematical_text", "_periodic_hmt_action", "zero_or_one"),
    CandidateGeneratorSpec("open_problem", "verification_handoff", "_verification_handoff_action", "zero_or_one", "verification"),
    CandidateGeneratorSpec("open_problem", "root_refinement", "_root_refinement_action", "zero_or_one"),
    CandidateGeneratorSpec("open_problem", "evidence_assimilation", "_evidence_assimilation_action", "zero_or_one", "evidence"),
    CandidateGeneratorSpec("open_problem", "researcher_circling_redirect", "_circling_redirect_action", "zero_or_one"),
    CandidateGeneratorSpec("open_problem", "recovery_synthesis", "_recovery_synthesis_action", "zero_or_one", "recovery"),
    CandidateGeneratorSpec("open_problem", "obligation_routing", "_obligation_routing_action", "zero_or_one", "obligation"),
    CandidateGeneratorSpec("open_problem", "general_circling_redirect", "_circling_redirect_action", "zero_or_one"),
    CandidateGeneratorSpec("open_problem", "residual_mathematical_work", "_residual_work_action", "exactly_one", "residual"),
)


# Published graph versions are immutable replay contracts. Add a new tuple and
# mapping entry instead of editing an older declaration after release.
PARALLEL_INTERNAL_GENERATOR_IDS = frozenset(
    {
        "peer_verification",
        "long_session_verification",
        "support_theorem_precheck",
        "advisor_synthesis",
        "exact_support_theorem_search",
        "counterexample_search",
        "parallel_decomposition",
        "researcher",
        "research_strategy",
        "literature_scan",
    }
)
PARALLEL_COMPANION_GENERATOR_IDS = (
    PARALLEL_INTERNAL_GENERATOR_IDS
    | {"independent_integration", "background_planner", "verifier_capacity"}
)
_v1_specs: list[CandidateGeneratorSpec] = []
_v1_parallel_inserted = False
for _spec in CANDIDATE_GENERATOR_GRAPH_V2:
    if _spec.scope_id == "solved_root":
        continue
    if (
        _spec.scope_id == "parallel_wave"
        and _spec.generator_id in PARALLEL_INTERNAL_GENERATOR_IDS
    ):
        if not _v1_parallel_inserted:
            _v1_specs.append(
                CandidateGeneratorSpec(
                    "parallel_wave",
                    "companion_plan",
                    "_plan_parallel_companion_actions",
                    "zero_or_more",
                )
            )
            _v1_parallel_inserted = True
        continue
    if _spec.scope_id == "top_level" and _spec.generator_id == "base_planner":
        _v1_specs.append(
            CandidateGeneratorSpec(
                "top_level",
                "base_planner",
                "_plan_next_action",
                "exactly_one",
                "open_problem",
            )
        )
        continue
    _v1_specs.append(_spec)
CANDIDATE_GENERATOR_GRAPH_V1 = tuple(_v1_specs)
del _spec, _v1_specs, _v1_parallel_inserted

# Version 3 intentionally retains the version-2 declaration.  The new graph
# epoch makes manifest-v2 evaluation provenance mandatory for newly emitted
# traces without invalidating graph-v2 traces persisted before that manifest
# schema existed.
CANDIDATE_GENERATOR_GRAPH_V3 = CANDIDATE_GENERATOR_GRAPH_V2
CANDIDATE_GENERATOR_GRAPH_V4 = (
    *CANDIDATE_GENERATOR_GRAPH_V3,
    CandidateGeneratorSpec(
        "parallel_leader",
        "scheduled_primary",
        "_parallel_leader_candidate_actions",
        "exactly_one",
    ),
    CandidateGeneratorSpec(
        "parallel_leader",
        "serialized_candidate",
        "_parallel_leader_candidate_actions",
        "zero_or_more",
    ),
)
# Version 4 incorrectly attributed the scheduled-primary leader row to the
# helper that emits only serialized candidates. Preserve that declaration for
# replay and publish the corrected producer provenance as a new graph epoch.
CANDIDATE_GENERATOR_GRAPH_V5 = tuple(
    CandidateGeneratorSpec(
        spec.scope_id,
        spec.generator_id,
        (
            "_scheduled_parallel_leader_action"
            if spec.scope_id == "parallel_leader"
            and spec.generator_id == "scheduled_primary"
            else spec.producer
        ),
        spec.cardinality,
        spec.child_scope_id,
    )
    for spec in CANDIDATE_GENERATOR_GRAPH_V4
)

CANDIDATE_GENERATOR_GRAPHS: Mapping[
    int, tuple[CandidateGeneratorSpec, ...]
] = MappingProxyType({
    1: CANDIDATE_GENERATOR_GRAPH_V1,
    2: CANDIDATE_GENERATOR_GRAPH_V2,
    3: CANDIDATE_GENERATOR_GRAPH_V3,
    4: CANDIDATE_GENERATOR_GRAPH_V4,
    5: CANDIDATE_GENERATOR_GRAPH_V5,
})
CANDIDATE_GENERATOR_GRAPH_SHA256: Mapping[int, str] = MappingProxyType(
    {
        1: "c4c9a4e291a8d758e0f5b4e2bf30090ddd9e7c691b0f1465b7ab77edf2ae5014",
        2: "d0ba9673715b1eb884fef044319a89cba69c7d2cb7056fca295af1d7a025db7f",
        3: "d0ba9673715b1eb884fef044319a89cba69c7d2cb7056fca295af1d7a025db7f",
        4: "a2180e790dac7451a332a4ff56847ce9b5feca4ceae25c17ce100436ab14df56",
        5: "6d32e9ed485c235a8aa3aca8b24ca335588cd6cd07d88ef6f6a720f361a03b8d",
    }
)
CANDIDATE_GENERATOR_GRAPH = CANDIDATE_GENERATOR_GRAPHS[
    CANDIDATE_GENERATOR_GRAPH_VERSION
]


def candidate_generator_graph_sha256(
    graph: Sequence[CandidateGeneratorSpec],
) -> str:
    return hashlib.sha256(
        json.dumps(
            [asdict(spec) for spec in graph],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def generator_specs(
    scope_id: str,
    *,
    graph_version: int = CANDIDATE_GENERATOR_GRAPH_VERSION,
) -> tuple[CandidateGeneratorSpec, ...]:
    graph = CANDIDATE_GENERATOR_GRAPHS.get(graph_version, ())
    return tuple(
        spec for spec in graph if spec.scope_id == scope_id
    )


def generator_ids(
    scope_id: str,
    *,
    graph_version: int = CANDIDATE_GENERATOR_GRAPH_VERSION,
) -> tuple[str, ...]:
    return tuple(
        spec.generator_id
        for spec in generator_specs(scope_id, graph_version=graph_version)
    )


def candidate_generator_graph_errors(
    graph: Sequence[CandidateGeneratorSpec] = CANDIDATE_GENERATOR_GRAPH,
) -> list[str]:
    errors: list[str] = []
    keys = [(spec.scope_id, spec.generator_id) for spec in graph]
    if len(keys) != len(set(keys)):
        errors.append("candidate-generator identifiers must be unique within a scope")
    scopes = {spec.scope_id for spec in graph}
    for spec in graph:
        if not spec.scope_id or not spec.generator_id or not spec.producer:
            errors.append("candidate-generator declarations must be nonempty")
        if spec.cardinality not in {"zero_or_one", "zero_or_more", "exactly_one"}:
            errors.append(
                f"candidate generator {spec.scope_id}:{spec.generator_id} has invalid cardinality"
            )
        if spec.child_scope_id and spec.child_scope_id not in scopes:
            errors.append(
                f"candidate generator {spec.scope_id}:{spec.generator_id} names unknown child scope {spec.child_scope_id}"
            )
    edges = {
        spec.scope_id: {
            child.child_scope_id
            for child in graph
            if child.scope_id == spec.scope_id and child.child_scope_id
        }
        for spec in graph
    }
    for root in scopes:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(scope: str) -> None:
            if scope in visiting:
                errors.append(f"candidate-generator graph contains a cycle at {scope}")
                return
            if scope in visited:
                return
            visiting.add(scope)
            for child_scope in edges.get(scope, set()):
                visit(child_scope)
            visiting.remove(scope)
            visited.add(scope)

        visit(root)
    return errors


_GRAPH_ERRORS = tuple(
    f"v{version}: {error}"
    for version, graph in CANDIDATE_GENERATOR_GRAPHS.items()
    for error in candidate_generator_graph_errors(graph)
) + tuple(
    f"v{version}: candidate-generator declaration digest changed"
    for version, graph in CANDIDATE_GENERATOR_GRAPHS.items()
    if candidate_generator_graph_sha256(graph)
    != CANDIDATE_GENERATOR_GRAPH_SHA256.get(version)
)
if set(CANDIDATE_GENERATOR_GRAPHS) != set(
    SUPPORTED_CANDIDATE_GENERATOR_GRAPH_VERSIONS
):
    _GRAPH_ERRORS += (
        "supported candidate-generator graph versions disagree with the registry",
    )
if set(CANDIDATE_GENERATOR_GRAPH_SHA256) != set(
    SUPPORTED_CANDIDATE_GENERATOR_GRAPH_VERSIONS
):
    _GRAPH_ERRORS += (
        "candidate-generator graph commitments do not cover every supported version",
    )
if CANDIDATE_GENERATOR_GRAPH_VERSION not in (
    SUPPORTED_CANDIDATE_GENERATOR_GRAPH_VERSIONS
):
    _GRAPH_ERRORS += (
        "active candidate-generator graph version is not supported",
    )
if _GRAPH_ERRORS:
    raise RuntimeError("invalid candidate-generator graph: " + "; ".join(_GRAPH_ERRORS))


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _assignment_runs(
    assignments: Sequence[Sequence[str]],
) -> list[Dict[str, Any]]:
    runs: list[Dict[str, Any]] = []
    for index, assignment in enumerate(assignments):
        generator_ids = list(assignment)
        if runs and runs[-1]["generator_ids"] == generator_ids:
            runs[-1]["candidate_count"] += 1
            continue
        runs.append(
            {
                "start_index": index,
                "candidate_count": 1,
                "generator_ids": generator_ids,
            }
        )
    return runs


def new_parallel_generator_evaluation() -> Dict[str, Any]:
    """Create a mutable wave-local record for the admission boundary."""

    return {"evaluated": set(), "skipped": {}}


def mark_candidate_generators_evaluated(
    evaluation: Dict[str, Any], generator_ids: Iterable[str]
) -> None:
    evaluated = evaluation.setdefault("evaluated", set())
    skipped = evaluation.setdefault("skipped", {})
    if not isinstance(evaluated, set) or not isinstance(skipped, dict):
        raise ValueError("parallel candidate-generator evaluation state is invalid")
    for generator_id in generator_ids:
        evaluated.add(generator_id)
        skipped.pop(generator_id, None)


def mark_candidate_generators_skipped(
    evaluation: Dict[str, Any],
    generator_ids: Iterable[str],
    reason_code: str,
) -> None:
    evaluated = evaluation.setdefault("evaluated", set())
    skipped = evaluation.setdefault("skipped", {})
    if not isinstance(evaluated, set) or not isinstance(skipped, dict):
        raise ValueError("parallel candidate-generator evaluation state is invalid")
    for generator_id in generator_ids:
        if generator_id not in evaluated:
            skipped.setdefault(generator_id, reason_code)


def bind_candidate_generator_registry(
    trace: Dict[str, Any],
    *,
    scope_id: str,
    active_generator_ids: Sequence[str],
    evaluated_generator_ids: Sequence[str],
    skipped_generator_reasons: Mapping[str, str],
    candidate_generator_assignments: Sequence[Sequence[str]] | None = None,
    graph_version: int = CANDIDATE_GENERATOR_GRAPH_VERSION,
) -> Dict[str, Any]:
    """Commit generation, evaluation, and phase-exclusion provenance.

    A zero count is not enough to show whether a policy was considered.  New
    manifests therefore partition the immutable declaration into policies
    whose applicability was evaluated and policies skipped by an enclosing
    phase or feature gate.  Version-1 manifests remain replayable, but this
    binder only emits the stronger version-2 contract.
    """

    if graph_version not in CANDIDATE_GENERATOR_GRAPHS:
        raise ValueError(
            f"unsupported candidate-generator graph version: {graph_version}"
        )
    specs = generator_specs(scope_id, graph_version=graph_version)
    if not specs:
        raise ValueError(f"unknown candidate-generator scope: {scope_id}")
    declared = {spec.generator_id for spec in specs}
    if any(
        not isinstance(generator_id, str) or not generator_id
        for generator_id in evaluated_generator_ids
    ):
        raise ValueError(
            "evaluated candidate-generator identifiers must be nonempty strings"
        )
    evaluated = tuple(sorted(set(evaluated_generator_ids)))
    unknown_evaluated = sorted(set(evaluated) - declared)
    if unknown_evaluated:
        raise ValueError(
            f"unregistered evaluated candidate generators in {scope_id}: "
            + ", ".join(unknown_evaluated)
        )
    if not isinstance(skipped_generator_reasons, Mapping) or any(
        not isinstance(generator_id, str)
        or generator_id not in declared
        or not isinstance(reason, str)
        or _SKIP_REASON_PATTERN.fullmatch(reason) is None
        for generator_id, reason in skipped_generator_reasons.items()
    ):
        raise ValueError(
            "candidate-generator skip reasons must map declared identifiers "
            "to nonempty snake-case reason codes"
        )
    skipped = {
        generator_id: skipped_generator_reasons[generator_id]
        for generator_id in sorted(skipped_generator_reasons)
    }
    overlap = sorted(set(evaluated) & set(skipped))
    missing = sorted(declared - set(evaluated) - set(skipped))
    if overlap or missing:
        details = []
        if overlap:
            details.append("both evaluated and skipped: " + ", ".join(overlap))
        if missing:
            details.append("neither evaluated nor skipped: " + ", ".join(missing))
        raise ValueError(
            "candidate-generator evaluation must partition the declaration ("
            + "; ".join(details)
            + ")"
        )
    raw_candidates = trace.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("candidate-generator binding requires comparison rows")
    expected_assignment_count = len(raw_candidates) - (
        1 if scope_id == "parallel_wave" else 0
    )
    if candidate_generator_assignments is None:
        assignments = tuple((generator_id,) for generator_id in active_generator_ids)
    else:
        raw_assignments = tuple(candidate_generator_assignments)
        if any(
            not isinstance(assignment, Sequence)
            or isinstance(assignment, (str, bytes))
            or any(
                not isinstance(generator_id, str) or not generator_id
                for generator_id in assignment
            )
            for assignment in raw_assignments
        ):
            raise ValueError(
                "candidate-generator assignments must contain nonempty string identifiers"
            )
        assignments = tuple(
            tuple(sorted(set(assignment))) for assignment in raw_assignments
        )
    if len(assignments) != expected_assignment_count or any(
        not assignment for assignment in assignments
    ):
        raise ValueError(
            "candidate-generator assignments must cover every generated comparison row"
        )
    generated_ids = tuple(
        generator_id
        for assignment in assignments
        for generator_id in assignment
    )
    if any(not isinstance(item, str) or not item for item in generated_ids):
        raise ValueError("candidate-generator identifiers must be nonempty strings")
    active = tuple(sorted(set(generated_ids)))
    unknown = sorted(set(active) - declared)
    if unknown:
        raise ValueError(
            f"unregistered active candidate generators in {scope_id}: "
            + ", ".join(unknown)
        )
    unevaluated_active = sorted(set(active) - set(evaluated))
    if unevaluated_active:
        raise ValueError(
            f"active candidate generators were not evaluated in {scope_id}: "
            + ", ".join(unevaluated_active)
        )
    counts = {
        spec.generator_id: generated_ids.count(spec.generator_id)
        for spec in specs
    }
    for spec in specs:
        if spec.cardinality in {"zero_or_one", "exactly_one"} and counts[
            spec.generator_id
        ] > 1:
            raise ValueError(
                f"candidate generator {scope_id}:{spec.generator_id} exceeded "
                f"its {spec.cardinality} cardinality"
            )
        if spec.cardinality == "exactly_one" and counts[spec.generator_id] != 1:
            raise ValueError(
                f"candidate generator {scope_id}:{spec.generator_id} did not "
                "produce exactly one candidate"
            )
        if spec.generator_id in skipped and counts[spec.generator_id] != 0:
            raise ValueError(
                f"skipped candidate generator {scope_id}:{spec.generator_id} "
                "produced a comparison row"
            )
    registry = [asdict(spec) for spec in specs]
    assignment_runs = _assignment_runs(assignments)
    trace["candidate_generator_manifest_version"] = (
        CANDIDATE_GENERATOR_MANIFEST_VERSION
    )
    trace["candidate_generator_graph_version"] = graph_version
    trace["candidate_generator_scope_id"] = scope_id
    trace["active_candidate_generator_ids"] = list(active)
    trace["evaluated_candidate_generator_ids"] = list(evaluated)
    trace["candidate_generator_skip_reasons"] = skipped
    trace["candidate_generator_counts"] = counts
    trace["candidate_generator_assignment_runs"] = assignment_runs
    trace["candidate_generator_registry_sha256"] = hashlib.sha256(
        _canonical_json(registry).encode("utf-8")
    ).hexdigest()
    trace["candidate_generator_manifest_sha256"] = hashlib.sha256(
        _canonical_json(
            {
                "manifest_version": CANDIDATE_GENERATOR_MANIFEST_VERSION,
                "graph_version": graph_version,
                "scope_id": scope_id,
                "registry_sha256": trace["candidate_generator_registry_sha256"],
                "counts": counts,
                "assignment_runs": assignment_runs,
                "evaluated_generator_ids": list(evaluated),
                "skipped_generator_reasons": skipped,
            }
        ).encode("utf-8")
    ).hexdigest()
    # Generic comparisons are initially produced under decision policy v7.
    # Advancing only registered comparisons to v8 makes manifest presence a
    # validator-enforced contract, while non-registry and historical traces
    # keep their original replay semantics. Parallel waves use their separate
    # admission policy epoch and therefore have no decision_policy_version.
    if "decision_policy_version" in trace and graph_version >= 3:
        trace["decision_policy_version"] = (
            CANDIDATE_GENERATOR_BOUND_DECISION_POLICY_VERSION
        )
    return trace


def candidate_generator_trace_errors(trace: Mapping[str, Any]) -> list[str]:
    """Validate a manifest against its immutable versioned declaration."""

    if "candidate_generator_scope_id" not in trace:
        manifest_fields = {
            key
            for key in trace
            if str(key).startswith("candidate_generator_")
            or key
            in {
                "active_candidate_generator_ids",
                "evaluated_candidate_generator_ids",
            }
        }
        if manifest_fields:
            return [
                "decision trace candidate-generator provenance is incomplete without a scope"
            ]
        return []
    errors: list[str] = []
    manifest_version = trace.get("candidate_generator_manifest_version", 1)
    manifest_version_valid = (
        type(manifest_version) is int
        and manifest_version
        in _SUPPORTED_CANDIDATE_GENERATOR_MANIFEST_VERSIONS
    )
    if not manifest_version_valid:
        errors.append(
            "decision trace candidate-generator manifest version is unsupported"
        )
    graph_version = trace.get("candidate_generator_graph_version")
    version_valid = (
        type(graph_version) is int
        and graph_version in CANDIDATE_GENERATOR_GRAPHS
    )
    if not version_valid:
        errors.append("decision trace candidate-generator graph version is unsupported")
    elif graph_version >= 3 and manifest_version != 2:
        errors.append(
            "decision trace candidate-generator graph version requires manifest version 2"
        )
    scope_id = trace.get("candidate_generator_scope_id")
    scope_valid = isinstance(scope_id, str) and bool(scope_id)
    if not scope_valid:
        errors.append("decision trace candidate-generator scope must be nonempty")
    version_specs = (
        CANDIDATE_GENERATOR_GRAPHS.get(graph_version, ())
        if version_valid
        else ()
    )
    expected_specs = (
        tuple(
            spec
            for spec in version_specs
            if spec.scope_id == scope_id
        )
        if scope_valid
        else ()
    )
    if version_valid and scope_valid and not expected_specs:
        errors.append("decision trace candidate-generator scope is not declared")
    expected_registry = [asdict(spec) for spec in expected_specs]
    declared = {spec.generator_id for spec in expected_specs}
    expected_registry_digest = hashlib.sha256(
        _canonical_json(expected_registry).encode("utf-8")
    ).hexdigest()
    if trace.get("candidate_generator_registry_sha256") != expected_registry_digest:
        errors.append(
            "decision trace candidate-generator registry digest does not match its versioned declaration"
        )
    embedded_registry = trace.get("candidate_generator_registry")
    if embedded_registry is not None and embedded_registry != expected_registry:
        errors.append(
            "decision trace embedded candidate-generator registry does not match its versioned declaration"
        )
    active = trace.get("active_candidate_generator_ids")
    if not isinstance(active, list) or any(
        not isinstance(item, str) or not item for item in active
    ):
        errors.append("decision trace active candidate-generator identifiers are invalid")
    elif active != sorted(set(active)):
        errors.append("decision trace active candidate-generator identifiers are not canonical")
    elif not set(active).issubset(declared):
        errors.append("decision trace names an unregistered active candidate generator")
    raw_counts = trace.get("candidate_generator_counts")
    counts_valid = (
        isinstance(raw_counts, Mapping)
        and set(raw_counts) == declared
        and all(type(value) is int and value >= 0 for value in raw_counts.values())
    )
    if not counts_valid:
        errors.append("decision trace candidate-generator counts are invalid")
    else:
        counted_active = sorted(
            generator_id
            for generator_id, count in raw_counts.items()
            if count > 0
        )
        if active != counted_active:
            errors.append(
                "decision trace active candidate-generator identifiers disagree with counts"
            )
        specs_by_id = {spec.generator_id: spec for spec in expected_specs}
        for generator_id, count in raw_counts.items():
            cardinality = specs_by_id.get(generator_id)
            if cardinality is None:
                continue
            if cardinality.cardinality in {"zero_or_one", "exactly_one"} and count > 1:
                errors.append(
                    f"decision trace candidate generator {generator_id} exceeds its declared cardinality"
                )
            if cardinality.cardinality == "exactly_one" and count != 1:
                errors.append(
                    f"decision trace candidate generator {generator_id} violates exactly-one cardinality"
                )
    raw_evaluated: Any = None
    raw_skipped: Any = None
    evaluated_valid = False
    skipped_valid = False
    if manifest_version == 1:
        if (
            "evaluated_candidate_generator_ids" in trace
            or "candidate_generator_skip_reasons" in trace
        ):
            errors.append(
                "legacy candidate-generator manifest contains version-2 evaluation fields"
            )
    elif manifest_version == 2:
        raw_evaluated = trace.get("evaluated_candidate_generator_ids")
        evaluated_valid = (
            isinstance(raw_evaluated, list)
            and all(
                isinstance(generator_id, str) and bool(generator_id)
                for generator_id in raw_evaluated
            )
            and raw_evaluated == sorted(set(raw_evaluated))
            and set(raw_evaluated).issubset(declared)
        )
        if not evaluated_valid:
            errors.append(
                "decision trace evaluated candidate-generator identifiers are invalid"
            )
        raw_skipped = trace.get("candidate_generator_skip_reasons")
        skipped_valid = (
            isinstance(raw_skipped, Mapping)
            and list(raw_skipped) == sorted(raw_skipped)
            and all(
                isinstance(generator_id, str)
                and generator_id in declared
                and isinstance(reason, str)
                and _SKIP_REASON_PATTERN.fullmatch(reason) is not None
                for generator_id, reason in raw_skipped.items()
            )
        )
        if not skipped_valid:
            errors.append(
                "decision trace candidate-generator skip reasons are invalid"
            )
        if evaluated_valid and skipped_valid:
            evaluated_set = set(raw_evaluated)
            skipped_set = set(raw_skipped)
            if evaluated_set & skipped_set or evaluated_set | skipped_set != declared:
                errors.append(
                    "decision trace candidate-generator evaluation does not partition its declaration"
                )
            if isinstance(active, list) and not set(active).issubset(evaluated_set):
                errors.append(
                    "decision trace active candidate generators were not evaluated"
                )
            if counts_valid and any(
                raw_counts[generator_id] != 0 for generator_id in skipped_set
            ):
                errors.append(
                    "decision trace skipped candidate generator has a nonzero count"
                )
    raw_assignment_runs = trace.get("candidate_generator_assignment_runs")
    raw_candidates = trace.get("candidates")
    expected_assignment_count = (
        len(raw_candidates) - (1 if scope_id == "parallel_wave" else 0)
        if isinstance(raw_candidates, list) and raw_candidates
        else -1
    )
    assignment_runs_valid = isinstance(raw_assignment_runs, list)
    assigned_counts = {generator_id: 0 for generator_id in declared}
    covered_candidates = 0
    if assignment_runs_valid:
        for run in raw_assignment_runs:
            if not isinstance(run, Mapping) or set(run) != {
                "start_index",
                "candidate_count",
                "generator_ids",
            }:
                assignment_runs_valid = False
                continue
            start_index = run.get("start_index")
            candidate_count = run.get("candidate_count")
            generator_ids = run.get("generator_ids")
            if (
                type(start_index) is not int
                or start_index != covered_candidates
                or type(candidate_count) is not int
                or candidate_count <= 0
                or not isinstance(generator_ids, list)
                or not generator_ids
                or not all(
                    isinstance(generator_id, str)
                    and generator_id in declared
                    for generator_id in generator_ids
                )
                or generator_ids != sorted(set(generator_ids))
            ):
                assignment_runs_valid = False
                continue
            for generator_id in generator_ids:
                assigned_counts[generator_id] += candidate_count
            covered_candidates += candidate_count
    if covered_candidates != expected_assignment_count:
        assignment_runs_valid = False
    if not assignment_runs_valid:
        errors.append("decision trace candidate-generator assignment runs are invalid")
    elif counts_valid:
        if dict(raw_counts) != assigned_counts:
            errors.append(
                "decision trace candidate-generator counts disagree with row assignments"
            )
    try:
        manifest_payload = {
            "graph_version": graph_version,
            "scope_id": scope_id,
            "registry_sha256": trace.get(
                "candidate_generator_registry_sha256"
            ),
            "counts": raw_counts,
            "assignment_runs": raw_assignment_runs,
        }
        if manifest_version == 2:
            manifest_payload = {
                "manifest_version": manifest_version,
                **manifest_payload,
                "evaluated_generator_ids": raw_evaluated,
                "skipped_generator_reasons": raw_skipped,
            }
        expected_manifest_digest = hashlib.sha256(
            _canonical_json(manifest_payload).encode("utf-8")
        ).hexdigest()
    except (TypeError, ValueError, OverflowError, RecursionError):
        expected_manifest_digest = ""
        errors.append("decision trace candidate-generator manifest is not canonical JSON")
    if trace.get("candidate_generator_manifest_sha256") != expected_manifest_digest:
        errors.append("decision trace candidate-generator manifest digest is invalid")
    return errors


def generator_producers_by_scope() -> Dict[str, frozenset[str]]:
    return {
        scope: frozenset(spec.producer for spec in generator_specs(scope))
        for scope in sorted({spec.scope_id for spec in CANDIDATE_GENERATOR_GRAPH})
    }
