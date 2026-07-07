from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

from .budget import plan_action_budget, plan_step_budget
from .debt_canonicalizer import central_debt_clusters, central_obstruction_for_debt
from .graph_policy import (
    FAR_FROM_ROOT_DISTANCE,
    _compact_text,
    active_frontier_pressure,
    decomposition_cooldown_active,
    decisive_theorem_test_signal,
    frontier_claim_ids,
    integrated_claim_covering_debt_id,
    maturity_rank,
    paused_route_ids,
    proof_trunk_maturity,
    route_scoreboard,
    root_distance_for_claim_id,
)
from .invariants import validate_conn
from .research_policy import (
    DEFAULT_RESEARCH_MODE,
    DEFAULT_WEB_SEARCH,
    action_expects_researcher_session,
    action_expects_villain_session,
    normalize_research_mode,
    normalize_retrieval_relation,
    researcher_mode_summary,
    should_run_librarian,
    stamp_researcher_work_mode,
)
from .store import ProofStateStore
from . import steering

ADVISOR_EARLY_ITERATION = 12
ADVISOR_MANDATORY_ITERATION = 20
ADVISOR_EVIDENCE_SYNTHESIS_BUDGET = 60_000
# Anti-circling breaker: a strict, broad stall detector that escalates to the advisor
# (decompose / re-route) and the human, instead of re-issuing the same research pass.
CIRCLING_MIN_PASSES = 3
CIRCLING_RESEARCH_MODES = {
    "prove", "reduce", "retrieve", "audit_definitions", "synthesize_sources",
    "refute", "weaken", "strengthen", "triage_routes", "regulate_decomposition",
}
CIRCLING_ADVISOR_MODES = {"triage_routes", "regulate_decomposition"}
CIRCLING_ADVISOR_MAX = 2
CIRCLING_INTENT = "circling_breaker"
DEFAULT_MAX_SCHEDULABLE_REDUCTION_DEPTH = 4
RECURSIVE_META_DEPTH = 7
RECURSIVE_META_ITEM_COUNT = 4
ACTIVE_MAIN_TRUNK_CAP = 3
MAX_PARALLEL_DECOMPOSITION_COMPANIONS = 2
DUPLICATE_WORK_WINDOW = 6
DUPLICATE_WORK_REPEAT_THRESHOLD = 2
RETRIEVE_REDUCE_LOOP_WINDOW = 6
RETRIEVE_REDUCE_LOOP_MIN_COUNT = 3
PARALLEL_SYNTHESIS_WINDOW = 6
PARALLEL_SYNTHESIS_MIN_CATEGORIES = 2
NO_RESULT_SEARCH_SYNTHESIS_THRESHOLD = 2
GLOBAL_SYNTHESIS_WINDOW = 10
ADVISOR_EVIDENCE_SYNTHESIS_INTENT = "advisor_evidence_synthesis"
ADVISOR_FOLLOWUP_RESEARCH_INTENT = "advisor_followup_research"
ADVISOR_EVIDENCE_SYNTHESIS_WINDOW = 8
VERIFY_READY_ROUTE_INTENT = "verify_ready_route"
STRICT_VERIFIER_RECENT_WINDOW = 8
VERIFIER_LOOP_CLASSIFICATION_INTENT = "verifier_loop_classification"
OBSTRUCTION_ROUTE_CONVERSION_INTENT = "obstruction_route_conversion"
RESEARCHER_TIMEOUT_REDIRECT_WINDOW = 8
STREAM_RETRY_STALL_FRAGMENT = "Codex stream retry stalled"
STREAM_RETRY_RECOVERY_INTENT = "stream_stall_recovery"
PROOF_CANDIDATE_ROUTE_CONVERSION_INTENT = "proof_candidate_route_conversion"
GLOBAL_SYNTHESIS_INTENT = "global_synthesis"
PROOF_ARCHITECTURE_PRESSURE_INTENT = "proof_architecture_pressure"
DECISIVE_THEOREM_TEST_INTENT = "decisive_theorem_test"
BOTTLENECK_LOCK_INTENT = "bottleneck_lock_theorem_attack"
EXECUTIVE_ADVISOR_LOCK_INTENT = "executive_advisor_bottleneck_lock"
NEAR_SOLUTION_SPINE_SYNTHESIS_INTENT = "near_solution_spine_synthesis"
BOTTLENECK_LOCK_REPEAT_THRESHOLD = 2
BOTTLENECK_LOCK_MIN_DIAGNOSTIC_ARTIFACTS = 2
NEAR_SOLUTION_MIN_PARTIAL_CREDIT = 5
NEAR_SOLUTION_MIN_PROOF_ARTIFACTS = 5
PROOF_SPINE_MODE_INTENT = "proof_spine_compression"
POST_INTEGRATION_PROOF_SPINE_INTENT = "post_integration_proof_spine"
EXACT_THEOREM_SEARCH_INTENT = "exact_theorem_search"
SUPPORT_LEMMA_PRECHECK_INTENT = "support_lemma_precheck"
FRESH_NARROWED_DEBT_ROIS = {
    "bottleneck_narrowed",
    "source_or_cas_changed_next_step",
    "route_blocked_or_abandoned",
    "failed_method_do_not_retry",
}
PROOF_SPINE_ARTIFACT_TYPES = {
    "proof_dossier",
    "proof_blueprint",
    "route_obstruction",
    "construction_failure",
    "necessary_condition",
    "cas_experiment_report",
    "source_adaptation_notes",
    "source_synthesis_report",
    "advisor_report",
}
PROOF_ARCHITECTURE_SIGNAL_WINDOW = 12
PROOF_ARCHITECTURE_MIN_SIGNAL_ARTIFACTS = 3
CREATIVE_PROOF_ATTACK_INTENT = "creative_proof_attack"
CREATIVE_ATTACK_WINDOW = 10
CREATIVE_ATTACK_MIN_PARTIAL_CREDIT = 2
CREATIVE_ATTACK_MIN_BOTTLENECK_SIGNALS = 2
ROUTE_OBSTRUCTION_ARTIFACT_TYPES = {
    "route_obstruction",
    "hypothesis_gap",
    "construction_failure",
    "necessary_condition",
}
OBSTRUCTION_SIGNAL_ARTIFACT_TYPES = {
    "candidate_counterexample",
    "research_diagnostic",
    "cas_experiment_report",
    "proof_dossier",
    *ROUTE_OBSTRUCTION_ARTIFACT_TYPES,
}
PROOF_CANDIDATE_ARTIFACT_TYPES = {"proof_dossier", "proof_blueprint", "advisor_report"}
NON_PROOF_CANDIDATE_ARTIFACT_ROIS = {
    "route_blocked_or_abandoned",
    "bottleneck_narrowed",
    "failed_method_do_not_retry",
}
ADVISOR_EVIDENCE_ARTIFACT_TYPES = {
    "proof_dossier",
    "proof_blueprint",
    "research_notebook",
    "research_diagnostic",
    "source_adaptation_notes",
    "source_synthesis_report",
    "candidate_counterexample",
    "cas_experiment_report",
    "decomposition_plan",
    "failed_decomposition_plan",
    "key_failure_analysis",
    "route_triage_report",
}
PROOF_CANDIDATE_SUBSUMPTION_SIGNATURES = (
    {
        "claim_id": "root_no_large_alternating_chief_factor_fixed_pq",
        "artifact_terms": (
            "alternating chief factor",
            "a_n^t",
        ),
        "claim_terms": (
            "chief factor",
            "a_n^t",
        ),
    },
)
ROUTE_PROOF_CONSTRUCTION_INTENT = "route_proof_construction"
BRIDGE_LEMMA_WORKBENCH_INTENT = "bridge_lemma_workbench"
PARALLEL_ROUTE_PROOF_CONSTRUCTION_INTENT = "parallel_route_proof_construction"
DIRECT_PROOF_AFTER_NO_CONTENT_INTENT = "direct_proof_after_no_content"
NO_CONTENT_RESEARCH_WINDOW = 8
NO_CONTENT_RESEARCH_THRESHOLD = 2
CONTENTFUL_RESEARCH_ARTIFACT_TYPES = {
    "proof_dossier",
    "proof_blueprint",
    "source_adaptation_notes",
    "source_synthesis_report",
    "research_diagnostic",
    "candidate_counterexample",
    *ROUTE_OBSTRUCTION_ARTIFACT_TYPES,
    "decomposition_plan",
    "cas_experiment_report",
    "literature_search_request",
    "route_triage_report",
}
COUNTEREXAMPLE_ROOT_LOCAL_IMPACT = 0.7
SEARCH_REQUEST_ARTIFACT_TYPES = {"literature_search_request"}
SOURCE_HANDOFF_ARTIFACT_TYPES = {"source_adaptation_notes", "source_synthesis_report"}
DECOMPOSITION_PLAN_ARTIFACT_TYPE = "decomposition_plan"
FAILED_DECOMPOSITION_ARTIFACT_TYPE = "failed_decomposition_plan"
KEY_FAILURE_ARTIFACT_TYPE = "key_failure_analysis"
ADVISOR_REPORT_ARTIFACT_TYPE = "advisor_report"
PROOF_ARCHITECTURE_SIGNAL_TYPES = {
    *CONTENTFUL_RESEARCH_ARTIFACT_TYPES,
    ADVISOR_REPORT_ARTIFACT_TYPE,
    "route_triage_report",
}
BOTTLENECK_DIAGNOSTIC_ARTIFACT_TYPES = {
    "research_diagnostic",
    "research_notebook",
    "route_triage_report",
    "advisor_report",
    "failed_decomposition_plan",
    "key_failure_analysis",
}

META_BOOKKEEPING_HARD_PHRASES = (
    "json schema",
    "patch schema",
    "row contract",
    "metadata envelope",
    "candidate inventory",
    "proof-state schema",
    "context manifest",
    "serialization format",
    "serialisation format",
)
META_BOOKKEEPING_TERMS = (
    "schema",
    "json",
    "validator",
    "validation harness",
    "serialization",
    "serialisation",
    "envelope",
    "inventory",
    "bookkeeping",
    "metadata",
    "manifest",
    "sqlite",
    "database row",
    "patch format",
    "artifact id",
)
EXACT_CITATION_DEBT_CUES = (
    "precise citation",
    "precise cited theorem",
    "locatable citation",
    "missing_reference",
    "missing reference",
    "published theorem",
    "source location",
    "theorem number",
    "cite a theorem",
    "cited theorem",
)
COMPUTATION_AUDIT_DEBT_CUES = (
    "auditable finite computation",
    "finite computation",
    "bounded exhaustive computation",
    "exhaustive computation",
    "explicit code",
    "code/query transcript",
    "generated-subgroup test",
    "class sizes",
    "cas",
    "computation transcript",
)
SUPPORT_LEMMA_THEOREM_TERMS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "lang_shintani",
        ("lang-shintani", "lang shintani", "steinberg", "h^1", "h1", "first cohomology", "graph-field", "graph field"),
        "finite Lang-Shintani / Steinberg H^1-triviality theorem for graph-field automorphisms",
    ),
    (
        "wall_primary_decomposition",
        ("wall", "primary-decomposition", "primary decomposition", "orthogonal similitude", "finite orthogonal"),
        "Wall primary-decomposition theorem for finite orthogonal similitudes",
    ),
    (
        "hilbert_90",
        ("hilbert-90", "hilbert 90", "hilbert's theorem 90"),
        "Hilbert 90 theorem with hypotheses matching the local obligation",
    ),
    (
        "witt_transitivity",
        ("witt transitivity", "witt extension", "witt's extension", "witt theorem"),
        "Witt extension/transitivity theorem with exact field and form hypotheses",
    ),
    (
        "spinor_norm",
        ("spinor norm", "determinant/spinor", "spinor/determinant", "orthogonal stabilizer"),
        "spinor norm and determinant image theorem for orthogonal stabilizers",
    ),
)


def advisor_should_run(
    *,
    iteration: int,
    iterations_since_new_accepted_claim: int,
    last_advisor_iteration: Optional[int] = None,
    early_iteration: int = ADVISOR_EARLY_ITERATION,
    mandatory_iteration: int = ADVISOR_MANDATORY_ITERATION,
) -> Dict[str, Any]:
    since_advisor = iteration if last_advisor_iteration is None else iteration - last_advisor_iteration
    if since_advisor >= mandatory_iteration:
        return {"run": True, "reason": f"mandatory advisor cadence reached at {mandatory_iteration} iterations"}
    if iteration >= early_iteration and iterations_since_new_accepted_claim >= early_iteration:
        return {"run": True, "reason": f"no accepted progress for {iterations_since_new_accepted_claim} iterations"}
    return {"run": False, "reason": "advisor not due"}


def next_action(
    store: ProofStateStore,
    *,
    requested_tokens: Optional[int] = None,
    research_mode: str | None = DEFAULT_RESEARCH_MODE,
    web_search: str | None = DEFAULT_WEB_SEARCH,
) -> Dict[str, Any]:
    action = _plan_next_action(
        store,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        web_search=web_search,
    )
    if action_expects_researcher_session(action) or action_expects_villain_session(action):
        stamp_researcher_work_mode(
            store.get_scheduler_state(),
            action,
            research_mode=research_mode,
            web_search=web_search,
        )
    return action


def _plan_next_action(
    store: ProofStateStore,
    *,
    requested_tokens: Optional[int] = None,
    research_mode: str | None = DEFAULT_RESEARCH_MODE,
    web_search: str | None = DEFAULT_WEB_SEARCH,
) -> Dict[str, Any]:
    research_mode = normalize_research_mode(research_mode)
    state = store.get_scheduler_state()
    problem = state["problem_state"]
    invariant_errors = _invariant_errors(store)
    if invariant_errors:
        mode = "stop_with_partial_results"
        budget = plan_step_budget(problem, mode, requested_tokens)
        return _action(mode, "root", "", "state invariant violation", budget, errors=invariant_errors, research_mode=research_mode)

    root = _claim(state, "root")
    if root and root["lifecycle_status"] == "integrated":
        final_artifact = _final_proof_artifact(state, "root")
        if not final_artifact:
            mode = "write"
            route_id = _integrated_route_for_claim(state, "root")
            return _action(
                mode,
                "root",
                route_id,
                "root is integrated; write final proof artifact",
                plan_step_budget(problem, mode, requested_tokens),
                research_mode=research_mode,
                final_output_required=True,
                terminal_classification="solved_but_not_written",
            )
        citation_decision = should_run_librarian(
            state,
            research_mode=research_mode,
            web_search=web_search,
            target_id="root",
            phase="post_integration",
        )
        if citation_decision.get("run"):
            mode = "retrieve"
            return _action(
                mode,
                str(citation_decision.get("target_id") or "root"),
                "",
                str(citation_decision.get("reason") or "citation-pass literature scan"),
                plan_step_budget(problem, mode, requested_tokens),
                research_mode=research_mode,
                retrieval_required=True,
                search_permission=citation_decision.get("search_permission", "live"),
                search_intent=citation_decision.get("search_intent", "citation_pass"),
            )
        return _action(
            "stop_solved",
            "root",
            _integrated_route_for_claim(state, "root"),
            "root is integrated and final proof artifact exists",
            plan_step_budget(problem, "stop_solved", 0),
            research_mode=research_mode,
            terminal_classification="solved_final",
            final_artifact_id=final_artifact.get("artifact_id", ""),
        )

    # Highest priority after a solved/integrated root: if the root has been refuted by a
    # confirmed counterexample, stop trying to prove it — revise the goal and surface it.
    refuted_root_guard = _refuted_root_revision_action(
        store, state, problem=problem, requested_tokens=requested_tokens, research_mode=research_mode,
    )
    if refuted_root_guard:
        return refuted_root_guard

    integration_candidate = _integration_candidate(state)
    if integration_candidate:
        mode = "integrate"
        return _action(
            mode,
            integration_candidate["conclusion_claim_id"],
            integration_candidate["route_id"],
            "verified sufficient route can be integrated",
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
        )

    parent_implication_ready = bool(
        (parent_step := _active_decomposition_plan_step(state))
        and parent_step.get("parent_implication_required")
    )
    post_integration_spine = _post_integration_proof_spine_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if post_integration_spine and not parent_implication_ready:
        return post_integration_spine

    support_precheck = _support_lemma_precheck_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        web_search=web_search,
        parallel_companion=False,
    )
    if support_precheck and not parent_implication_ready:
        return support_precheck

    verifier_candidate = _verifier_candidate_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        parallel_companion=False,
    )
    if verifier_candidate and not parent_implication_ready:
        verifier_candidate["reason"] = (
            "verifier-ready proof route should be checked before citation, "
            "retrieval, counterexample, or decomposition work"
        )
        verifier_candidate["search_intent"] = verifier_candidate.get("search_intent") or "verify_ready_route"
        verifier_candidate["verify_ready_route_policy"] = True
        return verifier_candidate

    # The villain's job is to disprove the root: when it has flagged a candidate
    # counterexample, validate it promptly (root-threats first) instead of letting it
    # sit uncertified while we keep proving. Confirmation routes to _refuted_root_revision.
    counterexample_guard = _counterexample_validation_action(
        store, state, problem=problem, requested_tokens=requested_tokens, research_mode=research_mode,
    )
    if counterexample_guard and not parent_implication_ready:
        return counterexample_guard

    # No hanging proven-but-unrouted claims: if a claim already has a proof dossier but
    # no route concludes it, assemble the route now (make it verifier-ready) before doing
    # any new proving — otherwise the proof sits in limbo and the verifier never runs.
    unrouted_proof_guard = _unrouted_proof_claim_action(
        store, state, problem=problem, requested_tokens=requested_tokens, research_mode=research_mode,
    )
    if unrouted_proof_guard and not parent_implication_ready:
        return unrouted_proof_guard

    # The open cases against the root are really claims that refine it: when obstructions
    # (definitional mismatch / over-broad scope / a counterexample family) pile up on the
    # root, auto-refine it — schedule the agent to draft a corrected, scope-restricted
    # restatement instead of endlessly trying to prove the over-broad version.
    root_refinement_guard = _root_refinement_action(
        store, state, problem=problem, requested_tokens=requested_tokens, research_mode=research_mode,
    )
    if root_refinement_guard and not parent_implication_ready:
        return root_refinement_guard

    executive_advisor_lock = _executive_advisor_bottleneck_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if executive_advisor_lock and not parent_implication_ready:
        return executive_advisor_lock

    near_solution_spine = _near_solution_spine_synthesis_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if near_solution_spine and not parent_implication_ready:
        return near_solution_spine

    proof_candidate_conversion = _proof_candidate_route_conversion_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if proof_candidate_conversion and not parent_implication_ready:
        return proof_candidate_conversion

    stream_stall_recovery = _stream_stall_recovery_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if stream_stall_recovery and not parent_implication_ready:
        return stream_stall_recovery

    citation_candidate = _external_citation_candidate(state, target_id="root")
    if citation_candidate:
        mode = "prove"
        if not _recent_intent_seen(state, "citation_triage", window=4):
            budget_action = {
                "target_id": "root",
                "citation_triage_required": True,
                "search_intent": "citation_triage",
            }
            return _action(
                mode,
                "root",
                "",
                "quick verifier triage for an exact external citation candidate",
                plan_action_budget(problem, mode, budget_action, requested_tokens),
                research_mode=research_mode,
                citation_triage_required=True,
                citation_verification_standard="reasonable_citation_triage",
                retrieval_card_id=citation_candidate["card_id"],
                citation_relation=citation_candidate["relation"],
                search_intent="citation_triage",
            )
        budget_action = {
            "target_id": "root",
            "citation_certification_required": True,
            "search_intent": "citation_certification",
        }
        return _action(
            mode,
            "root",
            "",
            "exact external citation candidate can certify the root theorem",
            plan_action_budget(problem, mode, budget_action, requested_tokens),
            research_mode=research_mode,
            citation_certification_required=True,
            citation_verification_standard="reasonable_citation_with_local_deduction",
            retrieval_card_id=citation_candidate["card_id"],
            citation_relation=citation_candidate["relation"],
            search_intent="citation_certification",
        )

    definition_audit = _definition_audit_candidate(state, target_id="root")
    if definition_audit:
        mode = "audit_definitions"
        return _action(
            mode,
            "root",
            "",
            definition_audit["reason"],
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            definition_audit_required=True,
            retrieval_card_id=definition_audit["card_id"],
            definition_audit_reason=definition_audit["reason"],
            search_intent="definition_audit",
        )

    exact_theorem_search = _verifier_blocked_citation_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        web_search=web_search,
    )
    if exact_theorem_search and not parent_implication_ready:
        return exact_theorem_search

    bottleneck_lock = _bottleneck_lock_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )

    advisor_followup = _advisor_followup_research_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if (
        advisor_followup
        and not parent_implication_ready
        and _advisor_followup_can_preempt_bottleneck(advisor_followup, bottleneck_lock)
    ):
        return advisor_followup

    verifier_loop_classification = _verifier_loop_classification_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if verifier_loop_classification and not parent_implication_ready:
        return verifier_loop_classification

    duplicate_guard = _duplicate_work_suppression_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if duplicate_guard:
        return duplicate_guard

    retrieve_reduce_guard = _retrieve_reduce_loop_advisor_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if retrieve_reduce_guard:
        return retrieve_reduce_guard

    no_content_guard = _no_content_research_guard_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if no_content_guard:
        return no_content_guard

    early_blocking_debt = _first_blocking_debt(state)
    if early_blocking_debt and _is_source_like_debt(early_blocking_debt):
        debt_action = _blocking_debt_action(
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            frontier_pressure=active_frontier_pressure(state),
            blocking_debt=early_blocking_debt,
        )
        if debt_action:
            debt_action["reason"] = "source-like blocking debt should be answered before obstruction conversion or more route checking"
            return debt_action

    if bottleneck_lock and not parent_implication_ready:
        return bottleneck_lock

    architecture_pressure = _proof_architecture_pressure_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if architecture_pressure:
        return architecture_pressure

    creative_attack = _creative_proof_attack_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if creative_attack:
        return creative_attack

    parallel_synthesis = _parallel_wave_synthesis_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if parallel_synthesis:
        return parallel_synthesis

    global_synthesis = _global_synthesis_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if global_synthesis:
        return global_synthesis

    no_result_synthesis = _no_result_search_synthesis_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if no_result_synthesis:
        return no_result_synthesis

    central_workbench = _central_obstruction_workbench_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if central_workbench:
        return central_workbench

    search_request = _pending_literature_search_request(state)
    if search_request:
        mode = "retrieve"
        return _action(
            mode,
            search_request["target_id"],
            search_request.get("route_id", ""),
            "researcher requested targeted literature/theorem search",
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            retrieval_required=True,
            search_request_id=search_request["search_request_id"],
            search_request_artifact_id=search_request["artifact_id"],
            requested_query=search_request.get("query", ""),
            local_theorem_search_allowed=True,
            search_permission="live" if web_search == "live" else "local",
            search_intent="researcher_search_request",
            librarian_level=search_request.get("librarian_level", "reader"),
        )

    active_trunk_pressure = _active_main_trunk_pressure(state)
    source_synthesis = _source_synthesis_candidate(state, target_id="root")
    if source_synthesis:
        mode = "synthesize_sources"
        return _action(
            mode,
            "root",
            "",
            source_synthesis["reason"],
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            source_synthesis_required=True,
            source_synthesis_reason=source_synthesis["reason"],
            search_intent="source_synthesis",
        )

    source_digest = _pending_source_handoff_digest(state)
    if source_digest:
        mode = "reduce"
        budget_action = {
            "target_id": source_digest["target_id"],
            "source_adaptation_digest_required": True,
            "search_intent": "source_adaptation_digest",
        }
        return _action(
            mode,
            source_digest["target_id"],
            source_digest.get("route_id", ""),
            "digest new literature handoff into a local proof dossier",
            plan_action_budget(problem, mode, budget_action, requested_tokens),
            research_mode=research_mode,
            source_adaptation_digest_required=True,
            source_artifact_id=source_digest["artifact_id"],
            source_artifact_type=source_digest["artifact_type"],
            search_request_id=source_digest.get("search_request_id", ""),
            needs_proof_dossier=True,
            search_intent="source_adaptation_digest",
        )

    route_decision_triage = _route_decision_triage_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if route_decision_triage:
        return route_decision_triage

    route_pause_replacement = _route_pause_replacement_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if route_pause_replacement:
        return route_pause_replacement

    frontier_pressure = active_frontier_pressure(state)
    blocking_debt = _first_blocking_debt(state)

    obstruction_conversion = _obstruction_route_conversion_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if obstruction_conversion and (
        not blocking_debt or _obstruction_conversion_matches_blocking_debt(state, obstruction_conversion, blocking_debt)
    ):
        return obstruction_conversion

    if blocking_debt:
        debt_action = _blocking_debt_action(
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            frontier_pressure=frontier_pressure,
            blocking_debt=blocking_debt,
        )
        if debt_action:
            debt_action["reason"] = "active blocking proof debt should be repaired after newer obstruction signals are converted"
            return debt_action

    if obstruction_conversion:
        return obstruction_conversion

    verifier_candidate = _verifier_candidate_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        parallel_companion=False,
    )
    if verifier_candidate and not active_trunk_pressure.get("over_trunk_cap") and not parent_implication_ready:
        verifier_candidate["reason"] = "verifier-ready proof route should be checked before more research or decomposition"
        return verifier_candidate

    if not active_trunk_pressure.get("over_trunk_cap"):
        proof_quota = _route_proof_construction_quota_action(
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
        )
        if proof_quota:
            return proof_quota

    failed_plan = _pending_key_failure_analysis(state)
    if failed_plan:
        mode = "regulate_decomposition"
        return _action(
            mode,
            failed_plan["target_id"],
            failed_plan.get("route_id", ""),
            "regulate failed decomposition before proposing another generation",
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            decomposition_regulator_required=True,
            failed_decomposition_artifact_id=failed_plan["artifact_id"],
            decomposition_plan_id=failed_plan.get("decomposition_plan_id", ""),
            decomposition_plan_artifact_id=failed_plan.get("decomposition_plan_artifact_id", ""),
            search_intent="decomposition_regulator",
        )

    blocked_plan = _blocked_decomposition_plan_candidate(state)
    if blocked_plan:
        mode = "regulate_decomposition"
        return _action(
            mode,
            blocked_plan["target_id"],
            blocked_plan.get("route_id", ""),
            blocked_plan["reason"],
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            decomposition_regulator_required=True,
            decomposition_plan_id=blocked_plan.get("decomposition_plan_id", ""),
            decomposition_plan_artifact_id=blocked_plan.get("artifact_id", ""),
            blocked_branch_ids=blocked_plan.get("blocked_branch_ids", []),
            search_intent="decomposition_regulator",
        )

    circling_guard = _circling_redirect_action(
        store,
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if circling_guard:
        return circling_guard

    decomposition_step = _active_decomposition_plan_step(state)
    if decomposition_step:
        mode = decomposition_step["mode"]
        budget_action = {
            "target_id": decomposition_step["target_id"],
            "route_id": decomposition_step.get("route_id", ""),
            "proof_construction_required": bool(decomposition_step.get("proof_construction_required")),
            "search_intent": ROUTE_PROOF_CONSTRUCTION_INTENT if decomposition_step.get("proof_construction_required") else "decomposition_plan_work",
        }
        return _action(
            mode,
            decomposition_step["target_id"],
            decomposition_step.get("route_id", ""),
            decomposition_step["reason"],
            plan_action_budget(problem, mode, budget_action, requested_tokens),
            research_mode=research_mode,
            decomposition_step_required=True,
            decomposition_plan_id=decomposition_step["decomposition_plan_id"],
            decomposition_plan_artifact_id=decomposition_step["artifact_id"],
            decomposition_parent_id=decomposition_step.get("parent_id", ""),
            decomposition_dependencies=decomposition_step.get("dependencies", []),
            decomposition_parallel_group=decomposition_step.get("parallel_group", ""),
            decomposition_rank_policy=decomposition_step.get("rank_policy", ""),
            parent_implication_required=bool(decomposition_step.get("parent_implication_required")),
            direct_solve_required=bool(decomposition_step.get("direct_solve_required")),
            proof_construction_required=bool(decomposition_step.get("proof_construction_required")),
            citation_allowed_in_proof=bool(decomposition_step.get("citation_allowed_in_proof")),
            needs_proof_dossier=bool(decomposition_step.get("needs_proof_dossier", mode == "reduce")),
            search_intent=budget_action["search_intent"],
        )

    route_triage = _route_triage_candidate(state, active_trunk_pressure=active_trunk_pressure)
    if route_triage:
        mode = "triage_routes"
        return _action(
            mode,
            "root",
            route_triage.get("route_id", ""),
            route_triage["reason"],
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            route_triage_required=True,
            route_triage_reason=route_triage["reason"],
            active_trunk_pressure=active_trunk_pressure,
            search_intent="route_triage",
        )

    decomposition_drift = _recursive_meta_drift(state)
    if decomposition_drift:
        mode = "stop_with_partial_results"
        budget = plan_step_budget(problem, mode, requested_tokens)
        return _action(
            mode,
            "root",
            "",
            decomposition_drift["reason"],
            budget,
            research_mode=research_mode,
            terminal_classification="scope_drift_partial",
            decomposition_drift=decomposition_drift,
        )

    research_decision = should_run_librarian(state, research_mode=research_mode, web_search=web_search, target_id="root")
    if research_decision.get("run"):
        mode = "retrieve"
        return _action(
            mode,
            str(research_decision.get("target_id") or "root"),
            "",
            str(research_decision.get("reason") or "research-mode literature scan"),
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            retrieval_required=True,
            search_permission=research_decision.get("search_permission", "live"),
            search_intent=research_decision.get("search_intent", "literature_scoping"),
            librarian_level=research_decision.get("librarian_level", "scout"),
        )

    root_audit = _root_alignment_audit_candidate(state)
    if root_audit:
        mode = "integrate"
        return _action(
            mode,
            root_audit["conclusion_claim_id"],
            root_audit["route_id"],
            "periodic root-alignment audit for the current proof route",
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            root_alignment_audit=True,
            search_intent="root_alignment_audit",
        )

    compression = _proof_compression_candidate(state)
    if compression:
        mode = "write"
        return _action(
            mode,
            compression["conclusion_claim_id"],
            compression["route_id"],
            "compress verified progress into a shorter route outline",
            plan_step_budget(problem, mode, requested_tokens),
            research_mode=research_mode,
            proof_compression_required=True,
            search_intent="proof_compression",
        )

    pressure_action = _frontier_pressure_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        frontier_pressure=frontier_pressure,
    )
    if pressure_action:
        return pressure_action

    route_without_inference = _route_without_inference(state)
    if route_without_inference:
        return _route_proof_construction_action(
            state,
            route_without_inference,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            reason="active route lacks inference evidence; researcher should try to prove the route before reducing further",
        )

    untested_claim = _next_unverified_claim(state)
    if untested_claim:
        mode, route_id = _work_mode_for_claim(state, untested_claim["claim_id"])
        direct_solve = mode == "prove" and not route_id
        proof_construction = bool(route_id and mode == "reduce")
        return _action(
            mode,
            untested_claim["claim_id"],
            route_id,
            "highest-impact active unverified claim",
            plan_action_budget(
                problem,
                mode,
                {
                    "target_id": untested_claim["claim_id"],
                    "route_id": route_id,
                    "proof_construction_required": proof_construction,
                    "search_intent": ROUTE_PROOF_CONSTRUCTION_INTENT if proof_construction else ("direct_solve" if direct_solve else ""),
                },
                requested_tokens,
            ),
            research_mode=research_mode,
            direct_solve_required=direct_solve,
            proof_construction_required=proof_construction,
            citation_allowed_in_proof=proof_construction,
            research_diagnostic_required=False if direct_solve else (mode == "reduce"),
            needs_proof_dossier=direct_solve or (mode == "reduce"),
            search_intent="direct_solve" if direct_solve else (ROUTE_PROOF_CONSTRUCTION_INTENT if proof_construction else ""),
        )

    mode = "retrieve"
    return _action(
        mode,
        "root",
        "",
        "no active route selected; retrieve references or propose reduction",
        plan_step_budget(problem, mode, requested_tokens),
        research_mode=research_mode,
    )


def parallel_companion_actions(
    store: ProofStateStore,
    primary_action: Mapping[str, Any],
    *,
    requested_tokens: Optional[int] = None,
    research_mode: str | None = DEFAULT_RESEARCH_MODE,
    web_search: str | None = DEFAULT_WEB_SEARCH,
) -> list[Dict[str, Any]]:
    companions = _plan_parallel_companion_actions(
        store,
        primary_action,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        web_search=web_search,
    )
    if any(
        action_expects_researcher_session(companion) or action_expects_villain_session(companion)
        for companion in companions
    ):
        state = store.get_scheduler_state()
        for companion in companions:
            if action_expects_researcher_session(companion) or action_expects_villain_session(companion):
                stamp_researcher_work_mode(
                    state,
                    companion,
                    research_mode=research_mode,
                    web_search=web_search,
                )
    return companions


def _plan_parallel_companion_actions(
    store: ProofStateStore,
    primary_action: Mapping[str, Any],
    *,
    requested_tokens: Optional[int] = None,
    research_mode: str | None = DEFAULT_RESEARCH_MODE,
    web_search: str | None = DEFAULT_WEB_SEARCH,
) -> list[Dict[str, Any]]:
    """Plan safe companion actions for literature/research/verifier overlap."""
    mode = str(primary_action.get("mode") or "")
    if mode in {"stop_with_partial_results", "stop_solved", "integrate", "write"}:
        return []
    research_mode = normalize_research_mode(research_mode)
    state = store.get_scheduler_state()
    problem = state["problem_state"]

    if _is_verifier_action(primary_action):
        return []
    support_precheck = _support_lemma_precheck_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        web_search=web_search,
        parallel_companion=True,
    )
    advisor = _advisor_evidence_synthesis_action(
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        primary_action=primary_action,
        parallel_companion=True,
    )
    verifier = None
    if not support_precheck:
        verifier = _verifier_candidate_action(
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            parallel_companion=True,
        )

    if primary_action.get("bottleneck_lock_required"):
        companions: list[Dict[str, Any]] = []
        exact_search = _verifier_blocked_citation_action(
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            web_search=web_search,
            parallel_companion=True,
        )
        if exact_search:
            companions.append(exact_search)
        elif support_precheck:
            companions.append(support_precheck)
        elif verifier:
            companions.append(verifier)
        counterexample = _counterexample_companion_action(
            primary_action,
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
        )
        if counterexample:
            companions.append(counterexample)
        return companions

    decomposition_companions = _parallel_decomposition_companion_actions(
        primary_action,
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    if decomposition_companions:
        return ([verifier] if verifier else []) + decomposition_companions

    if mode == "retrieve":
        if verifier:
            return [verifier]
        researcher = _researcher_candidate_action(
            primary_action,
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
        )
        if not researcher:
            return []
        companions = [researcher]
        counterexample = _counterexample_companion_action(
            researcher,
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
        )
        if counterexample:
            companions.append(counterexample)
        if advisor:
            companions.append(advisor)
        return companions

    if primary_action.get("proof_construction_required"):
        companions: list[Dict[str, Any]] = []
        if support_precheck and mode != "retrieve":
            companions.append(support_precheck)
        elif verifier:
            companions.append(verifier)
        decision = should_run_librarian(
            state,
            research_mode=research_mode,
            web_search=web_search,
            target_id=str(primary_action.get("target_id") or "root"),
        )
        if decision.get("run"):
            companions.append(
                _action(
                    "retrieve",
                    str(decision.get("target_id") or primary_action.get("target_id") or "root"),
                    "",
                    "parallel literature scan while researcher constructs the proof route",
                    plan_step_budget(problem, "retrieve", requested_tokens),
                    research_mode=research_mode,
                    retrieval_required=True,
                    search_permission=decision.get("search_permission", "live"),
                    search_intent=decision.get("search_intent", "literature_scoping"),
                    librarian_level=decision.get("librarian_level", "scout"),
                    parallel_companion=True,
                )
            )
        counterexample = _counterexample_companion_action(
            primary_action,
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
        )
        if counterexample:
            companions.append(counterexample)
        if advisor:
            companions.append(advisor)
        return companions

    counterexample = _counterexample_companion_action(
        primary_action,
        state,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
    )
    companions = [verifier] if verifier else []
    if counterexample:
        companions.append(counterexample)
    if advisor:
        companions.append(advisor)
    return companions


def _is_verifier_action(action: Mapping[str, Any]) -> bool:
    return str(action.get("mode") or "") == "prove" and bool(action.get("route_id"))


def route_verifier_readiness(state: Mapping[str, Any], route_id: str) -> Dict[str, Any]:
    """Return the scheduler's strict route-readiness scorecard for UI/audits."""
    return _route_readiness_scorecard(state, route_id)


def verifier_ready_route_summaries(state: Mapping[str, Any]) -> list[Dict[str, Any]]:
    """Summarize routes that the scheduler considers ready for strict verification."""
    paused = paused_route_ids(state)
    summaries: list[Dict[str, Any]] = []
    for route in state.get("routes", []):
        route_id = str(route.get("route_id") or "")
        if not route_id or route_id in paused or str(route.get("status") or "") != "active":
            continue
        target_id = str(route.get("conclusion_claim_id") or "")
        readiness = _route_readiness_scorecard(state, route_id)
        if not readiness.get("verifier_ready"):
            continue
        summaries.append(
            {
                "route_id": route_id,
                "target_id": target_id,
                "inference_count": int(readiness.get("inference_count", 0) or 0),
                "evidence_artifact_count": int(readiness.get("evidence_artifact_count", 0) or 0),
                "score": int(readiness.get("score", 0) or 0),
                "level": str(readiness.get("level") or ""),
            }
        )
    summaries.sort(key=lambda row: (str(row["target_id"]) != "root", -int(row["score"]), str(row["route_id"])))
    return summaries


def _route_readiness_scorecard(state: Mapping[str, Any], route_id: str) -> Dict[str, Any]:
    route = _route(state, route_id)
    if not route:
        return {
            "route_id": route_id,
            "score": 0,
            "level": "missing",
            "verifier_ready": False,
            "ready_checks": [],
            "missing_checks": ["route is absent"],
        }
    conclusion_id = str(route.get("conclusion_claim_id") or "")
    claim_by_id = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    conclusion_claim = claim_by_id.get(conclusion_id)
    conclusion_verifiable = bool(
        conclusion_claim
        and str(conclusion_claim.get("lifecycle_status") or "") == "active"
        and str(conclusion_claim.get("validation_status") or "") in {"untested", "plausible", "challenged"}
    )
    inferences = [row for row in state.get("inferences", []) if row.get("route_id") == route_id]
    route_or_claim_owner_ids = {route_id, conclusion_id}
    inference_ids = {str(row.get("inference_id") or "") for row in inferences}
    evidence_ids = set(str(item or "") for item in _json_list(route.get("evidence_artifact_ids_json")))
    premise_ids: set[str] = set()
    for inference in inferences:
        evidence_ids.update(str(item or "") for item in _json_list(inference.get("evidence_artifact_ids_json")))
        premise_ids.update(str(item or "") for item in inference.get("premise_claim_ids", []) if str(item or ""))
    route_blocker_owner_ids = route_or_claim_owner_ids | inference_ids | premise_ids
    blockers = [
        row for row in state.get("debts", [])
        if row.get("status") == "active"
        and row.get("severity") == "blocking"
        and (
            str(row.get("owner_id") or "") in route_blocker_owner_ids
            or str(row.get("suggested_next_target") or "") in premise_ids
        )
        and _debt_blocks_route_verification(row, conclusion_id=conclusion_id)
    ]

    ready_checks: list[str] = []
    missing_checks: list[str] = []
    score = 0
    if conclusion_verifiable:
        ready_checks.append("conclusion_claim_verifiable")
    else:
        missing_checks.append("conclusion_claim_not_verifiable")
    if route.get("status") == "active":
        score += 1
        ready_checks.append("route_active")
    else:
        missing_checks.append("route_not_active")
    if route.get("relation_to_parent") == "sufficient":
        score += 1
        ready_checks.append("sufficient_route")
    else:
        missing_checks.append("route_not_marked_sufficient")
    if inferences:
        score += 2
        ready_checks.append("has_route_inference")
    else:
        missing_checks.append("no_route_inference")
    if evidence_ids:
        score += 1
        ready_checks.append("has_evidence_artifact")
    else:
        missing_checks.append("no_evidence_artifact")
    if blockers:
        score -= 2
        missing_checks.append("active_blocking_debt")
    else:
        score += 1
        ready_checks.append("no_active_blocking_debt")
    if conclusion_id == "root" or root_distance_for_claim_id(state, conclusion_id) <= 2:
        score += 1
        ready_checks.append("root_local")
    else:
        missing_checks.append("far_from_root")
    if not premise_ids:
        score += 1
        ready_checks.append("no_unverified_premises")
    elif all(claim_by_id.get(premise_id, {}).get("validation_status") in {"informally_verified", "formally_verified"} for premise_id in premise_ids):
        score += 1
        ready_checks.append("premises_verified")
    else:
        missing_checks.append("unverified_premises")

    verifier_ready = conclusion_verifiable and bool(inferences) and not blockers and score >= 6
    if verifier_ready:
        level = "verifier_ready"
    elif blockers:
        level = "blocked"
    elif inferences:
        level = "candidate_needs_artifact_or_premise"
    else:
        level = "needs_researcher_inference"
    return {
        "route_id": route_id,
        "conclusion_claim_id": conclusion_id,
        "score": score,
        "level": level,
        "verifier_ready": verifier_ready,
        "inference_count": len(inferences),
        "evidence_artifact_count": len([item for item in evidence_ids if item]),
        "blocking_debt_count": len(blockers),
        "ready_checks": ready_checks,
        "missing_checks": missing_checks,
    }


def _debt_blocks_route_verification(debt: Mapping[str, Any], *, conclusion_id: str) -> bool:
    """Claim-level prove-or-refute debts are what a verifier-ready route should resolve."""
    if _debt_repair_pending_verifier(debt):
        # A debt whose repair is submitted and pending the verifier is the
        # reason to DISPATCH verification, not a veto on it: the packet still
        # carries the debt, and the strict verifier judges the repair. Without
        # this, repaired routes could never reach the verifier (observed live:
        # the p=7 audit chain self-blocked for 300+ revisions).
        return False
    if str(debt.get("owner_type") or "") != "claim":
        return True
    if str(debt.get("owner_id") or "") != conclusion_id:
        return True
    debt_type = str(debt.get("debt_type") or "")
    if debt_type in {"missing_proof_or_counterexample"}:
        return False
    if debt_type == "blocking_bridge" and _looks_like_downstream_claim_debt(debt):
        return False
    return True


def _debt_repair_pending_verifier(debt: Mapping[str, Any]) -> bool:
    evidence = debt.get("resolution_evidence") or debt.get("resolution_evidence_json")
    if isinstance(evidence, str):
        evidence = _json_object(evidence)
    if not isinstance(evidence, Mapping):
        return False
    return str(evidence.get("resolution_status") or "") == "repair_submitted_pending_verifier"


def _looks_like_downstream_claim_debt(debt: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(debt.get(key) or "").lower()
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


def _verifier_candidate_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
    parallel_companion: bool = True,
) -> Optional[Dict[str, Any]]:
    candidates = _verifier_ready_route_candidates(state)
    if not candidates:
        return None
    candidate = candidates[0]
    readiness = candidate["route_readiness"]
    route_id = str(candidate["route_id"])
    target_id = str(candidate["target_id"])
    extra = {"parallel_companion": True} if parallel_companion else {}
    return _action(
        "prove",
        target_id,
        route_id,
        "strict verifier check for an existing verifier-ready proof route",
        plan_step_budget(problem, "prove", requested_tokens),
        research_mode=research_mode,
        route_readiness=readiness,
        verify_ready_route_policy=True,
        strict_verifier_scope="single_route_verification_packet",
        verifier_evidence_artifact_ids=candidate["evidence_artifact_ids"],
        verifier_evidence_state_revision=candidate["evidence_state_revision"],
        strict_verifier_no_fresh_evidence=True,
        strict_verifier_no_cas=True,
        search_intent=VERIFY_READY_ROUTE_INTENT,
        **extra,
    )


def _verifier_ready_route_candidates(state: Mapping[str, Any]) -> list[Dict[str, Any]]:
    paused = paused_route_ids(state)
    candidates: list[Dict[str, Any]] = []
    for route in state.get("routes", []):
        route_id = str(route.get("route_id") or "")
        if not route_id or route_id in paused:
            continue
        if str(route.get("status") or "") != "active":
            continue
        target_id = str(route.get("conclusion_claim_id") or "")
        claim = _claim(state, target_id)
        if not claim or str(claim.get("lifecycle_status") or "") != "active":
            continue
        if str(claim.get("validation_status") or "") not in {"untested", "plausible", "challenged"}:
            continue
        readiness = _route_readiness_scorecard(state, route_id)
        if not readiness.get("verifier_ready"):
            continue
        evidence_ids = _route_evidence_artifact_ids(state, route_id)
        evidence_revision = _route_evidence_state_revision(state, evidence_ids)
        if _strict_verifier_recently_checked_route(state, route_id, evidence_revision):
            continue
        candidates.append(
            {
                "target_id": target_id,
                "route_id": route_id,
                "route_readiness": readiness,
                "claim": claim,
                "evidence_artifact_ids": evidence_ids,
                "evidence_state_revision": evidence_revision,
            }
        )

    def priority(item: Mapping[str, Any]) -> tuple[int, int, float, int, int, str]:
        claim = item["claim"]
        target_id = str(item["target_id"])
        readiness = item["route_readiness"]
        return (
            root_distance_for_claim_id(state, target_id),
            int(target_id != "root"),
            -float(claim.get("root_impact", 0.0) or 0.0),
            -int(readiness.get("score", 0) or 0),
            -int(item.get("evidence_state_revision", 0) or 0),
            str(item["route_id"]),
        )

    candidates.sort(key=priority)
    return candidates


def _route_evidence_artifact_ids(state: Mapping[str, Any], route_id: str) -> list[str]:
    route = _route(state, route_id)
    evidence_ids: list[str] = []

    def add_many(raw_ids: Any) -> None:
        for raw in _json_list(raw_ids):
            artifact_id = str(raw or "").strip()
            if artifact_id and artifact_id not in evidence_ids:
                evidence_ids.append(artifact_id)

    if route:
        add_many(route.get("evidence_artifact_ids_json"))
    for inference in state.get("inferences", []):
        if str(inference.get("route_id") or "") == route_id:
            add_many(inference.get("evidence_artifact_ids_json"))
    return evidence_ids


def _route_evidence_state_revision(state: Mapping[str, Any], evidence_ids: list[str]) -> int:
    artifact_revisions = {
        str(artifact.get("artifact_id") or ""): _revision_number(artifact.get("state_revision"))
        for artifact in state.get("research_artifacts", [])
    }
    revisions = [artifact_revisions[artifact_id] for artifact_id in evidence_ids if artifact_id in artifact_revisions]
    if revisions:
        return max(revisions)
    return 0


def _strict_verifier_recently_checked_route(state: Mapping[str, Any], route_id: str, evidence_revision: int) -> bool:
    for row in list(state.get("recent_runs", []))[:STRICT_VERIFIER_RECENT_WINDOW]:
        if str(row.get("actor_role") or "") != "strict_informal_verifier":
            continue
        if str(row.get("mode") or "") != "prove":
            continue
        if str(row.get("route_id") or "") != route_id:
            continue
        if str(row.get("status") or "") in {"failed", "timeout", "no_patch", "cancelled", "patch_rejected"}:
            continue
        if _revision_number(row.get("state_revision")) >= evidence_revision:
            return True
    return False


def _post_integration_proof_spine_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    last_integration = _last_mode_run(state, "integrate")
    if not last_integration or str(last_integration.get("status") or "") not in {"completed", "patch_accepted"}:
        return None
    if _recent_intent_seen(state, POST_INTEGRATION_PROOF_SPINE_INTENT, window=6):
        return None
    if _recent_intent_seen(state, "root_alignment_audit", window=3):
        return None
    target_id = str(last_integration.get("target_id") or "root")
    route_id = str(last_integration.get("route_id") or "")
    if not _claim(state, target_id):
        target_id = "root"
    return _action(
        "triage_routes",
        "root",
        route_id,
        "recent integration changed the proof graph; compress the current proof spine and remaining bottleneck before more local search",
        plan_step_budget(problem, "triage_routes", requested_tokens),
        research_mode=research_mode,
        advisor_evidence_synthesis_required=True,
        proof_spine_mode_required=True,
        proof_spine_compression_required=True,
        post_integration_compression_required=True,
        recently_integrated_target_id=target_id,
        recently_integrated_route_id=route_id,
        search_intent=POST_INTEGRATION_PROOF_SPINE_INTENT,
    )


def _support_lemma_precheck_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
    web_search: str | None,
    parallel_companion: bool = False,
) -> Optional[Dict[str, Any]]:
    candidates = _verifier_ready_route_candidates(state)
    for candidate in candidates:
        route_id = str(candidate["route_id"])
        if _recent_support_precheck_for_route(state, route_id):
            continue
        support = _route_named_support_gap(state, candidate)
        if not support:
            continue
        target_id = str(candidate["target_id"])
        query = _support_theorem_query(state, candidate, support)
        return _action(
            "retrieve",
            target_id,
            route_id,
            "verifier-ready route cites a named support theorem without a visible source card; retrieve the exact theorem before strict verification",
            plan_action_budget(
                problem,
                "retrieve",
                {
                    "target_id": target_id,
                    "route_id": route_id,
                    "support_lemma_precheck_required": True,
                    "search_intent": SUPPORT_LEMMA_PRECHECK_INTENT,
                },
                requested_tokens,
            ),
            research_mode=research_mode,
            retrieval_required=True,
            support_lemma_precheck_required=True,
            exact_theorem_search_required=True,
            support_lemma_label=support["label"],
            support_lemma_query=support["query"],
            requested_query=query,
            missing_theorem=support["query"],
            local_theorem_search_allowed=True,
            search_permission="live" if str(web_search or DEFAULT_WEB_SEARCH) == "live" else "local",
            search_intent=SUPPORT_LEMMA_PRECHECK_INTENT,
            librarian_level="research_librarian",
            parallel_companion=parallel_companion,
        )
    return None


def _verifier_blocked_citation_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
    web_search: str | None,
    parallel_companion: bool = False,
) -> Optional[Dict[str, Any]]:
    debts = [
        row for row in state.get("debts", [])
        if row.get("status") == "active"
        and row.get("severity") == "blocking"
        and _is_exact_citation_debt(row)
        and not _debt_covered_by_integrated_claim(state, row)
    ]
    if not debts:
        return None

    def priority(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
        target_id = _claim_target_for_debt(state, row) or str(row.get("owner_id") or "root")
        return (
            root_distance_for_claim_id(state, target_id),
            -int(row.get("repeated_count") or 0),
            -_iso_sort_number(row.get("last_seen")),
            str(row.get("debt_id") or ""),
        )

    debts.sort(key=priority)
    for debt in debts:
        target_id = _claim_target_for_debt(state, debt) or str(debt.get("owner_id") or "root")
        if not _claim(state, target_id):
            target_id = "root"
        route_id = _route_for_debt(state, debt, target_id, allow_paused=True)
        if _recent_exact_search_for_debt_target(state, target_id=target_id, route_id=route_id):
            continue
        query = _exact_citation_query(debt)
        return _action(
            "retrieve",
            target_id,
            route_id,
            "strict verifier found a citation/local-theorem debt; run an exact theorem search before more proof repair",
            plan_action_budget(
                problem,
                "retrieve",
                {
                    "target_id": target_id,
                    "route_id": route_id,
                    "debt_id": str(debt.get("debt_id") or ""),
                    "exact_theorem_search_required": True,
                    "search_intent": EXACT_THEOREM_SEARCH_INTENT,
                },
                requested_tokens,
            ),
            research_mode=research_mode,
            retrieval_required=True,
            exact_theorem_search_required=True,
            verifier_blocked_citation_search=True,
            debt_id=str(debt.get("debt_id") or ""),
            requested_query=query,
            missing_theorem=query,
            local_theorem_search_allowed=True,
            search_permission="live" if str(web_search or DEFAULT_WEB_SEARCH) == "live" else "local",
            search_intent=EXACT_THEOREM_SEARCH_INTENT,
            librarian_level="research_librarian",
            parallel_companion=parallel_companion,
        )
    return None


def _is_exact_citation_debt(debt: Mapping[str, Any]) -> bool:
    text = _debt_math_text(debt)
    debt_type = str(debt.get("debt_type") or "").lower()
    if debt_type in {"missing_reference", "source_gap"}:
        return True
    if _is_computation_audit_debt(debt):
        return False
    return any(cue in text for cue in EXACT_CITATION_DEBT_CUES)


def _is_computation_audit_debt(debt: Mapping[str, Any]) -> bool:
    text = _debt_math_text(debt)
    return any(cue in text for cue in COMPUTATION_AUDIT_DEBT_CUES)


def _exact_citation_query(debt: Mapping[str, Any]) -> str:
    obligation = _compact_text(str(debt.get("obligation") or ""), 700)
    debt_type = str(debt.get("debt_type") or "proof obligation")
    return (
        f"Exact theorem search for {debt_type}: {obligation}. "
        "Find a locatable theorem/proposition/lemma with source, theorem number or page/section, statement, hypotheses, "
        "and explain whether it closes this local proof obligation."
    )


def _recent_exact_search_for_debt_target(state: Mapping[str, Any], *, target_id: str, route_id: str) -> bool:
    for row in list(state.get("recent_runs", []))[:8]:
        if str(row.get("search_intent") or "") != EXACT_THEOREM_SEARCH_INTENT:
            continue
        if str(row.get("target_id") or "") == target_id:
            return True
        if route_id and str(row.get("route_id") or "") == route_id:
            return True
    return False


def _recent_support_precheck_for_route(state: Mapping[str, Any], route_id: str) -> bool:
    for row in list(state.get("recent_runs", []))[:8]:
        if str(row.get("search_intent") or "") != SUPPORT_LEMMA_PRECHECK_INTENT:
            continue
        if str(row.get("route_id") or "") == route_id:
            return True
    return False


def _route_named_support_gap(state: Mapping[str, Any], candidate: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    route_id = str(candidate["route_id"])
    evidence_ids = list(candidate.get("evidence_artifact_ids") or [])
    text = _route_support_text(state, route_id, evidence_ids)
    if not text:
        return None
    for label, terms, query in SUPPORT_LEMMA_THEOREM_TERMS:
        if not any(term in text for term in terms):
            continue
        if _support_term_already_sourced(state, terms):
            continue
        return {"label": label, "terms": list(terms), "query": query}
    return None


def _route_support_text(state: Mapping[str, Any], route_id: str, evidence_ids: list[str]) -> str:
    route = _route(state, route_id)
    pieces: list[str] = []
    if route:
        pieces.extend(
            str(route.get(key) or "")
            for key in ("route_id", "label", "strategy", "relation_to_parent", "failure_fingerprint")
        )
    for inference in state.get("inferences", []):
        if str(inference.get("route_id") or "") != route_id:
            continue
        pieces.extend(
            str(inference.get(key) or "")
            for key in ("inference_id", "conclusion_claim_id", "explanation")
        )
        evidence_ids.extend(str(item or "") for item in _json_list(inference.get("evidence_artifact_ids_json")))
    artifact_index = _artifact_index(state)
    for artifact_id in dict.fromkeys(evidence_ids):
        artifact = artifact_index.get(str(artifact_id or ""))
        if not artifact:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        pieces.extend(
            [
                str(artifact.get("artifact_id") or ""),
                str(artifact.get("artifact_type") or ""),
                str(artifact.get("content_summary") or ""),
                json.dumps(metadata, sort_keys=True),
            ]
        )
    return " ".join(pieces).lower()


def _support_term_already_sourced(state: Mapping[str, Any], terms: tuple[str, ...]) -> bool:
    rows: list[Mapping[str, Any]] = []
    rows.extend(state.get("retrieval_cards", []))
    rows.extend(state.get("theorem_library_entries", []))
    rows.extend(
        row for row in state.get("research_artifacts", [])
        if row.get("artifact_type") in SOURCE_HANDOFF_ARTIFACT_TYPES
    )
    for row in rows:
        text = " ".join(str(value or "") for value in row.values()).lower()
        if any(term in text for term in terms):
            return True
    return False


def _support_theorem_query(
    state: Mapping[str, Any],
    candidate: Mapping[str, Any],
    support: Mapping[str, Any],
) -> str:
    route_id = str(candidate["route_id"])
    target_id = str(candidate["target_id"])
    claim = _claim(state, target_id)
    statement = _compact_text(str((claim or {}).get("statement") or target_id), 500)
    return (
        f"Support-lemma precheck for verifier-ready route {route_id} proving {target_id}: "
        f"find the exact cited theorem for {support['query']}. Target statement: {statement}. "
        "Return a retrieval card or source handoff only if the source gives a locatable theorem and its hypotheses can be checked."
    )


def _verifier_loop_classification_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    for route in state.get("routes", []):
        route_id = str(route.get("route_id") or "")
        if not route_id or str(route.get("status") or "") != "active":
            continue
        target_id = str(route.get("conclusion_claim_id") or "root")
        if _recent_verifier_loop_classification_seen(state, route_id):
            continue
        debt_ids = _active_route_gap_debt_ids(state, route_id, target_id)
        if not debt_ids:
            continue
        evidence_revision = _route_evidence_state_revision(state, _route_evidence_artifact_ids(state, route_id))
        verifier_runs = _recent_strict_verifier_runs_for_route(
            state,
            route_id=route_id,
            min_state_revision=evidence_revision,
        )
        if len(verifier_runs) < 2:
            continue
        budget_action = {
            "target_id": target_id,
            "route_id": route_id,
            "verifier_loop_classification_required": True,
            "search_intent": VERIFIER_LOOP_CLASSIFICATION_INTENT,
        }
        return _action(
            "triage_routes",
            target_id,
            route_id,
            "same route has repeated strict-verifier gap reports; PhD advisor must classify the loop before another repair pass",
            plan_action_budget(problem, "triage_routes", budget_action, requested_tokens),
            research_mode=research_mode,
            route_triage_required=True,
            verifier_loop_classification_required=True,
            verifier_loop_route_id=route_id,
            verifier_loop_claim_id=target_id,
            verifier_gap_debt_ids=debt_ids,
            recent_verifier_run_ids=[str(row.get("run_id") or "") for row in verifier_runs[:4]],
            verifier_loop_classification_options=[
                "local_repair_or_typo",
                "missing_theorem",
                "bad_strategy",
                "abandon_or_pause_route",
            ],
            advisor_evidence_synthesis_required=True,
            search_intent=VERIFIER_LOOP_CLASSIFICATION_INTENT,
        )
    return None


def _recent_strict_verifier_runs_for_route(
    state: Mapping[str, Any],
    *,
    route_id: str,
    min_state_revision: int,
) -> list[Mapping[str, Any]]:
    runs: list[Mapping[str, Any]] = []
    for row in list(state.get("recent_runs", []))[:STRICT_VERIFIER_RECENT_WINDOW]:
        if str(row.get("actor_role") or "") != "strict_informal_verifier":
            continue
        if str(row.get("mode") or "") != "prove":
            continue
        if str(row.get("route_id") or "") != route_id:
            continue
        if str(row.get("status") or "") in {"failed", "timeout", "no_patch", "cancelled", "patch_rejected"}:
            continue
        if _revision_number(row.get("state_revision")) < min_state_revision:
            continue
        runs.append(row)
    return runs


def _recent_verifier_loop_classification_seen(state: Mapping[str, Any], route_id: str) -> bool:
    for row in list(state.get("recent_runs", []))[:STRICT_VERIFIER_RECENT_WINDOW]:
        if str(row.get("search_intent") or "") != VERIFIER_LOOP_CLASSIFICATION_INTENT:
            continue
        if str(row.get("route_id") or "") == route_id:
            return True
    return False


def _active_route_gap_debt_ids(state: Mapping[str, Any], route_id: str, target_id: str) -> list[str]:
    inference_ids = {
        str(row.get("inference_id") or "")
        for row in state.get("inferences", [])
        if str(row.get("route_id") or "") == route_id
    }
    debt_ids: list[str] = []
    for debt in state.get("debts", []):
        if str(debt.get("status") or "") != "active":
            continue
        debt_type = str(debt.get("debt_type") or "")
        if debt_type and debt_type in {"missing_reference", "citation_verification"}:
            continue
        owner_type = str(debt.get("owner_type") or "")
        owner_id = str(debt.get("owner_id") or "")
        suggested = str(debt.get("suggested_next_target") or "")
        route_scoped = (
            (owner_type == "route" and owner_id == route_id)
            or (owner_type == "inference" and owner_id in inference_ids)
            or (owner_type == "claim" and owner_id == target_id and _active_route_for_claim(state, target_id) == route_id)
            or suggested in {route_id, target_id}
        )
        if route_scoped:
            debt_id = str(debt.get("debt_id") or "")
            if debt_id and debt_id not in debt_ids:
                debt_ids.append(debt_id)
    return debt_ids


def _executive_advisor_bottleneck_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if verifier_ready_route_summaries(state):
        return None
    if _recent_intent_seen(state, EXECUTIVE_ADVISOR_LOCK_INTENT, window=3):
        return None
    report = _advisor_followup_report(state)
    if not report:
        return None
    metadata = _json_object(report.get("metadata_json"))
    if not _advisor_report_declares_executive_bottleneck(metadata):
        return None

    debt_ids = _advisor_referenced_debt_ids(metadata)
    debt = _first_active_debt_by_ids(state, debt_ids)
    explicit_target_id = _explicit_advisor_next_target_id(state, metadata)
    target_id = explicit_target_id or (str(_claim_target_for_debt(state, debt)) if debt else "")
    if not target_id or not _claim(state, target_id):
        target_id = _target_id_from_metadata(state, metadata, fallback="root")
    if not _claim(state, target_id):
        target_id = "root"
    route_id = _route_for_debt(state, debt, target_id) if debt else _advisor_followup_route_id(
        state,
        metadata,
        target_id,
        explicit_target=bool(explicit_target_id),
    )
    mode = "reduce" if route_id else "prove"
    recommended = str(metadata.get("recommended_next_action") or metadata.get("next_decisive_task") or "").strip()
    remaining = metadata.get("remaining_gaps") or metadata.get("remaining_gap") or metadata.get("gaps") or []
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "deep_research_required": True,
        "hard_theorem_attack_required": True,
        "executive_advisor_lock_required": True,
        "research_attack_stage": "hard_theorem_workbench",
        "search_intent": EXECUTIVE_ADVISOR_LOCK_INTENT,
    }
    return _action(
        mode,
        target_id,
        route_id,
        "PhD advisor declared a decisive bottleneck; lock the next research pass onto that theorem-level obligation before older local repairs",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        executive_advisor_lock_required=True,
        advisor_followup_required=True,
        advisor_report_id=str(report.get("artifact_id") or ""),
        advisor_recommended_next_action=recommended,
        advisor_remaining_gaps=remaining,
        advisor_referenced_debt_ids=debt_ids,
        debt_id=str((debt or {}).get("debt_id") or (debt_ids[0] if debt_ids else "")),
        direct_solve_required=(mode == "prove"),
        proof_construction_required=bool(route_id),
        citation_allowed_in_proof=bool(route_id),
        needs_proof_dossier=True,
        deep_research_required=True,
        hard_theorem_attack_required=True,
        theorem_workbench_required=True,
        proof_spine_mode_required=True,
        global_synthesis_required=True,
        research_synthesis_required=True,
        closure_pressure_required=True,
        obligation_reduction_required=True,
        speculative_proof_required=True,
        negative_result_ledger_required=True,
        near_miss_memory_required=True,
        duplicate_math_guard_required=True,
        paperwork_throttle_required=True,
        route_cooldown_enforced=True,
        hard_theorem_attack_contract={
            "prove_or_refute_first": True,
            "allowed_terminal_outputs": [
                "verifier-ready route/inference",
                "route-killing obstruction",
                "one strictly narrower theorem-level debt",
            ],
            "forbidden_outputs": [
                "route inventory",
                "broad literature request",
                "management-only research_notebook",
            ],
        },
        research_attack_stage="hard_theorem_workbench",
        search_intent=EXECUTIVE_ADVISOR_LOCK_INTENT,
    )


def _advisor_report_declares_executive_bottleneck(metadata: Mapping[str, Any]) -> bool:
    if _metadata_flag_false(metadata, "advisor_followup_required"):
        return False
    text = json.dumps(metadata, sort_keys=True).lower()
    if any(
        marker in text
        for marker in (
            "decisive_root_bottleneck",
            "decisive root bottleneck",
            "decisive_root",
            "root_bottleneck",
            "decisive bottleneck",
        )
    ):
        return True
    has_bottleneck = bool(metadata.get("bottleneck_obligation"))
    has_decisive = bool(metadata.get("next_decisive_task") or metadata.get("next_decisive_action"))
    if has_bottleneck and has_decisive and "root" in text:
        return True
    recommended = " ".join(
        str(metadata.get(key) or "")
        for key in ("recommended_next_action", "next_decisive_task", "next_decisive_action")
    ).lower()
    return bool(has_bottleneck and "decisive" in recommended)


def _first_active_debt_by_ids(state: Mapping[str, Any], debt_ids: list[str]) -> Optional[Mapping[str, Any]]:
    for debt_id in debt_ids:
        for debt in state.get("debts", []):
            if str(debt.get("debt_id") or "") == debt_id and str(debt.get("status") or "") == "active":
                return debt
    return None


def _fresh_advisor_suppression(state: Mapping[str, Any]) -> tuple[int, set[str], set[str]]:
    reports = [
        artifact for artifact in state.get("research_artifacts", [])
        if str(artifact.get("artifact_type") or "") == ADVISOR_REPORT_ARTIFACT_TYPE
        and str(artifact.get("producer_role") or "") == "phd_advisor"
    ]
    reports.sort(key=lambda row: (_revision_number(row.get("state_revision")), str(row.get("artifact_id") or "")), reverse=True)
    for report in reports:
        metadata = _json_object(report.get("metadata_json"))
        if not _advisor_report_declares_executive_bottleneck(metadata):
            continue
        revision = _revision_number(report.get("state_revision"))
        route_ids = {str(item or "") for item in _as_list(metadata.get("paused_or_abandoned_route_ids")) if str(item or "")}
        for decision in _as_list(metadata.get("route_decisions")):
            if not isinstance(decision, Mapping):
                continue
            decision_text = str(decision.get("decision") or "").lower()
            if not any(term in decision_text for term in ("block", "pause", "abandon", "stale", "low_yield")):
                continue
            route_id = str(decision.get("route_id") or decision.get("id") or "")
            if route_id:
                route_ids.add(route_id)
        target_ids: set[str] = set()
        for route_id in route_ids:
            route = _route(state, route_id)
            if route:
                target_ids.add(str(route.get("conclusion_claim_id") or ""))
        return revision, {route_id for route_id in route_ids if route_id}, {target_id for target_id in target_ids if target_id}
    return -1, set(), set()


def _near_solution_spine_synthesis_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if _recent_intent_seen(state, NEAR_SOLUTION_SPINE_SYNTHESIS_INTENT, window=6):
        return None
    signal = _near_solution_spine_signal(state)
    if not signal:
        return None
    route_id = str(signal.get("route_id") or "")
    mode = "reduce" if route_id else "prove"
    budget_action = {
        "target_id": "root",
        "route_id": route_id,
        "deep_research_required": True,
        "hard_theorem_attack_required": True,
        "research_attack_stage": "proof_spine",
        "search_intent": NEAR_SOLUTION_SPINE_SYNTHESIS_INTENT,
    }
    return _action(
        mode,
        "root",
        route_id,
        "near-solution proof portfolio should be assembled into a root proof spine before more local cleanup",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        near_solution_spine_synthesis_required=True,
        proof_spine_mode_required=True,
        proof_spine_min_lemmas=3,
        proof_spine_max_lemmas=6,
        global_synthesis_required=True,
        research_synthesis_required=True,
        theorem_building_synthesis_required=True,
        hard_theorem_attack_required=True,
        theorem_workbench_required=True,
        direct_solve_required=(mode == "prove"),
        proof_construction_required=bool(route_id),
        citation_allowed_in_proof=bool(route_id),
        needs_proof_dossier=True,
        deep_research_required=True,
        closure_pressure_required=True,
        obligation_reduction_required=True,
        speculative_proof_required=True,
        negative_result_ledger_required=True,
        near_miss_memory_required=True,
        route_cooldown_enforced=True,
        paperwork_throttle_required=True,
        near_solution_spine_signal=signal,
        research_attack_stage="proof_spine",
        search_intent=NEAR_SOLUTION_SPINE_SYNTHESIS_INTENT,
    )


def _near_solution_spine_signal(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if verifier_ready_route_summaries(state):
        return None
    root = _claim(state, "root")
    if root and str(root.get("lifecycle_status") or "") == "integrated":
        return None
    partial_credit = [
        claim for claim in state.get("claims", [])
        if str(claim.get("claim_id") or "") != "root"
        and root_distance_for_claim_id(state, str(claim.get("claim_id") or "")) <= 3
        and float(claim.get("root_impact", 0.0) or 0.0) >= 0.35
        and (
            str(claim.get("validation_status") or "") in {"informally_verified", "formally_verified"}
            or str(claim.get("lifecycle_status") or "") == "integrated"
        )
    ]
    proof_artifacts = [
        artifact for artifact in state.get("research_artifacts", [])
        if str(artifact.get("artifact_type") or "") in PROOF_SPINE_ARTIFACT_TYPES
        and root_distance_for_claim_id(
            state,
            _target_id_from_metadata(state, _json_object(artifact.get("metadata_json")), fallback="root"),
        ) <= 3
    ]
    active_root_debts = [
        debt for debt in state.get("debts", [])
        if str(debt.get("status") or "") == "active"
        and str(debt.get("severity") or "") in {"blocking", "major"}
        and (
            str(debt.get("owner_id") or "") == "root"
            or str(debt.get("suggested_next_target") or "") == "root"
            or root_distance_for_claim_id(state, _claim_target_for_debt(state, debt)) <= 3
        )
    ]
    if len({str(row.get("claim_id") or "") for row in partial_credit}) < NEAR_SOLUTION_MIN_PARTIAL_CREDIT:
        return None
    if len(proof_artifacts) < NEAR_SOLUTION_MIN_PROOF_ARTIFACTS:
        return None
    if not active_root_debts:
        return None
    active_root_debts.sort(key=lambda debt: (str(debt.get("owner_id") or "") != "root", str(debt.get("debt_id") or "")))
    debt = active_root_debts[0]
    target_id = _claim_target_for_debt(state, debt)
    route_id = _route_for_debt(state, debt, target_id)
    return {
        "policy": "near-solution-proof-spine",
        "target_id": "root",
        "route_id": route_id,
        "partial_credit_claim_ids": [str(row.get("claim_id") or "") for row in partial_credit[:10]],
        "proof_artifact_ids": [str(row.get("artifact_id") or "") for row in proof_artifacts[:10]],
        "blocking_debt_ids": [str(row.get("debt_id") or "") for row in active_root_debts[:8]],
        "selected_debt_id": str(debt.get("debt_id") or ""),
        "instruction": "Assemble a short root proof spine and attack exactly the selected remaining theorem-level gap.",
    }


def _proof_candidate_route_conversion_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    candidate = _unrouted_proof_candidate(state)
    if not candidate:
        return None
    target_id = str(candidate.get("target_id") or "root")
    route_id = str(candidate.get("route_id") or "")
    artifact_id = str(candidate.get("artifact_id") or "")
    mode = "reduce" if route_id else "prove"
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "proof_route_conversion_required": True,
        "proof_candidate_artifact_id": artifact_id,
        "research_attack_stage": "synthesis",
        "search_intent": PROOF_CANDIDATE_ROUTE_CONVERSION_INTENT,
    }
    return _action(
        mode,
        target_id,
        route_id,
        "proof-like artifact needs immediate route/inference conversion before more research",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        proof_route_conversion_required=True,
        proof_candidate_artifact_id=artifact_id,
        proof_candidate_summary=str(candidate.get("summary") or ""),
        needs_proof_dossier=False,
        research_synthesis_required=True,
        proof_spine_mode_required=True,
        route_conversion_attempt_required=True,
        research_attack_stage="synthesis",
        search_intent=PROOF_CANDIDATE_ROUTE_CONVERSION_INTENT,
    )


def _advisor_followup_research_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    report = _advisor_followup_report(state)
    if not report:
        return None
    metadata = _json_object(report.get("metadata_json"))
    explicit_target_id = _explicit_advisor_next_target_id(state, metadata)
    target_id = explicit_target_id or _target_id_from_metadata(state, metadata, fallback="root")
    route_id = _advisor_followup_route_id(
        state,
        metadata,
        target_id,
        explicit_target=bool(explicit_target_id),
    )
    mode = "reduce" if route_id else "prove"
    recommended = str(metadata.get("recommended_next_action") or metadata.get("next_action") or "").strip()
    remaining = metadata.get("remaining_gaps") or metadata.get("remaining_gap") or metadata.get("gaps") or []
    advisor_debt_ids = _advisor_referenced_debt_ids(metadata)
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "advisor_followup_required": True,
        "advisor_report_id": report["artifact_id"],
        "research_attack_stage": "synthesis",
        "proof_construction_required": bool(route_id),
        "search_intent": ADVISOR_FOLLOWUP_RESEARCH_INTENT,
    }
    return _action(
        mode,
        target_id,
        route_id,
        "PhD advisor report has an immediate mathematical recommendation; researcher should turn it into a proof dossier, route repair, or sharper blocker",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        advisor_followup_required=True,
        advisor_report_id=report["artifact_id"],
        advisor_recommended_next_action=recommended,
        advisor_remaining_gaps=remaining,
        advisor_referenced_debt_ids=advisor_debt_ids,
        advisor_proof_candidate=bool(metadata.get("proof_candidate") or metadata.get("candidate_full_proof")),
        proof_spine_manager_required=True,
        active_proof_spine_required=True,
        research_synthesis_required=True,
        direct_solve_required=(mode == "prove"),
        proof_construction_required=bool(route_id),
        citation_allowed_in_proof=bool(route_id),
        needs_proof_dossier=True,
        research_attack_stage="synthesis",
        search_intent=ADVISOR_FOLLOWUP_RESEARCH_INTENT,
    )


def _advisor_referenced_debt_ids(metadata: Mapping[str, Any]) -> list[str]:
    raw: list[Any] = []
    for key in (
        "debt_id",
        "central_debt_id",
        "locked_debt_id",
        "recommended_debt_id",
        "next_debt_id",
        "debt_ids",
        "central_debt_alias_ids",
        "remaining_debt_ids",
        "obstruction_debts",
        "blocking_debt_ids",
        "active_blocking_debt_ids",
        "repeated_blocking_debt_ids",
    ):
        value = metadata.get(key)
        if isinstance(value, list):
            raw.extend(value)
        elif value:
            raw.append(value)
    debt_ids: list[str] = []
    for item in raw:
        value = str(item or "").strip()
        if value and value not in debt_ids:
            debt_ids.append(value)
    return debt_ids


def _advisor_followup_can_preempt_bottleneck(
    advisor_action: Mapping[str, Any] | None,
    bottleneck_action: Mapping[str, Any] | None,
) -> bool:
    if not advisor_action:
        return False
    if not bottleneck_action:
        return True
    if advisor_action.get("advisor_proof_candidate"):
        return True
    lock_signal = _as_mapping(bottleneck_action.get("bottleneck_lock_signal"))
    locked_ids = {
        str(lock_signal.get("debt_id") or ""),
        str(bottleneck_action.get("debt_id") or ""),
        str(bottleneck_action.get("central_debt_id") or ""),
    }
    locked_ids.update(str(item or "") for item in _as_list(bottleneck_action.get("central_debt_alias_ids")))
    locked_ids = {item for item in locked_ids if item}
    if not locked_ids:
        return False
    advisor_ids = {str(item or "") for item in _as_list(advisor_action.get("advisor_referenced_debt_ids"))}
    if locked_ids & advisor_ids:
        return True
    advisor_text = json.dumps(
        {
            "report": advisor_action.get("advisor_report_id", ""),
            "recommended": advisor_action.get("advisor_recommended_next_action", ""),
            "remaining": advisor_action.get("advisor_remaining_gaps", []),
        },
        sort_keys=True,
    )
    return any(debt_id and debt_id in advisor_text for debt_id in locked_ids)


def _advisor_followup_report(state: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    last_followup = _last_intent_run(state, ADVISOR_FOLLOWUP_RESEARCH_INTENT)
    last_revision = _revision_number(last_followup.get("state_revision")) if last_followup else -1
    candidates: list[tuple[int, str, Mapping[str, Any]]] = []
    for artifact in state.get("research_artifacts", []):
        if str(artifact.get("artifact_type") or "") != ADVISOR_REPORT_ARTIFACT_TYPE:
            continue
        if str(artifact.get("producer_role") or "") != "phd_advisor":
            continue
        artifact_revision = _revision_number(artifact.get("state_revision"))
        if artifact_revision <= last_revision:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        if metadata.get("proof_candidate") or metadata.get("candidate_full_proof"):
            continue
        if not (
            metadata.get("advisor_followup_required")
            or metadata.get("evidence_synthesis_required")
            or metadata.get("recommended_next_action")
            or metadata.get("remaining_gaps")
            or metadata.get("directed_researcher_mode")
        ):
            continue
        candidates.append((artifact_revision, str(artifact.get("artifact_id") or ""), artifact))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def _explicit_advisor_next_target_id(state: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    for key in ("next_target_id", "next_claim_id", "recommended_target_id"):
        candidate = str(metadata.get(key) or "")
        if candidate and _claim(state, candidate):
            return candidate
    return ""


def _advisor_followup_route_id(
    state: Mapping[str, Any],
    metadata: Mapping[str, Any],
    target_id: str,
    *,
    explicit_target: bool,
) -> str:
    for key in ("next_route_id", "recommended_route_id"):
        route_id = str(metadata.get(key) or "")
        route = _route(state, route_id) if route_id else None
        if route and str(route.get("conclusion_claim_id") or "") == target_id:
            return route_id
    if not explicit_target:
        route_id = str(metadata.get("route_id") or "")
        route = _route(state, route_id) if route_id else None
        if route and str(route.get("conclusion_claim_id") or "") == target_id:
            return route_id
    return _active_route_for_claim(state, target_id) or ""


def _advisor_evidence_synthesis_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
    primary_action: Mapping[str, Any] | None = None,
    parallel_companion: bool = False,
) -> Optional[Dict[str, Any]]:
    if primary_action and str(primary_action.get("mode") or "") in {"triage_routes", "regulate_decomposition"}:
        return None
    if primary_action and primary_action.get("decomposition_step_required"):
        return None
    signal = _advisor_evidence_synthesis_signal(state)
    if not signal:
        return None
    target_id = str(signal.get("target_id") or "root")
    route_id = str(signal.get("route_id") or _active_route_for_claim(state, target_id) or "")
    extra = {"parallel_companion": True} if parallel_companion else {}
    advisor_budget = requested_tokens if requested_tokens is not None else ADVISOR_EVIDENCE_SYNTHESIS_BUDGET
    return _action(
        "triage_routes",
        target_id,
        route_id,
        "PhD advisor should synthesize fresh durable evidence, state what remains for a full proof, and send immediate guidance to the researcher",
        plan_step_budget(problem, "triage_routes", advisor_budget),
        research_mode=research_mode,
        advisor_evidence_synthesis_required=True,
        advisor_async_short_budget=True,
        advisor_evidence_signal=signal,
        advisor_followup_required=True,
        search_intent=ADVISOR_EVIDENCE_SYNTHESIS_INTENT,
        **extra,
    )


def _advisor_evidence_synthesis_signal(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    last_advisor = _last_intent_run(state, ADVISOR_EVIDENCE_SYNTHESIS_INTENT)
    last_revision = _revision_number(last_advisor.get("state_revision")) if last_advisor else -1
    last_time = str(last_advisor.get("created_at") or "") if last_advisor else ""
    if last_advisor and _recent_intent_seen(state, ADVISOR_EVIDENCE_SYNTHESIS_INTENT, window=ADVISOR_EVIDENCE_SYNTHESIS_WINDOW):
        has_newer_artifact = any(
            _revision_number(artifact.get("state_revision")) > last_revision
            and str(artifact.get("producer_role") or "") != "phd_advisor"
            and str(artifact.get("artifact_type") or "") in ADVISOR_EVIDENCE_ARTIFACT_TYPES
            for artifact in state.get("research_artifacts", [])
        )
        has_newer_graph = _new_graph_evidence_after(state, last_time)
        if not has_newer_artifact and not has_newer_graph:
            return None

    artifacts: list[Mapping[str, Any]] = []
    target_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    newest_revision = last_revision
    for artifact in state.get("research_artifacts", []):
        artifact_type = str(artifact.get("artifact_type") or "")
        if artifact_type not in ADVISOR_EVIDENCE_ARTIFACT_TYPES:
            continue
        if str(artifact.get("producer_role") or "") == "phd_advisor":
            continue
        artifact_revision = _revision_number(artifact.get("state_revision"))
        if artifact_revision <= last_revision:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        target_id = _target_id_from_metadata(state, metadata, fallback="root")
        route_id = str(metadata.get("route_id") or "")
        if route_id and not _route(state, route_id):
            route_id = ""
        target_counts[target_id] = target_counts.get(target_id, 0) + 1
        if route_id:
            route_counts[route_id] = route_counts.get(route_id, 0) + 1
        newest_revision = max(newest_revision, artifact_revision)
        artifacts.append(artifact)

    graph_delta = _new_graph_evidence_after(state, last_time)
    if not artifacts and not graph_delta:
        return None

    target_id = _most_common_key(target_counts) or "root"
    route_id = _most_common_key(route_counts) or _active_route_for_claim(state, target_id) or ""
    artifact_ids = [str(artifact.get("artifact_id") or "") for artifact in artifacts if str(artifact.get("artifact_id") or "")]
    artifact_types = sorted({str(artifact.get("artifact_type") or "") for artifact in artifacts if str(artifact.get("artifact_type") or "")})
    producer_roles = sorted({str(artifact.get("producer_role") or "") for artifact in artifacts if str(artifact.get("producer_role") or "")})
    return {
        "policy": "event-driven-advisor-evidence-synthesis",
        "target_id": target_id,
        "route_id": route_id,
        "newest_state_revision": newest_revision,
        "artifact_ids": artifact_ids[:12],
        "artifact_types": artifact_types,
        "producer_roles": producer_roles,
        "graph_delta": graph_delta,
        "instruction": (
            "Use the original problem and the fresh durable evidence to propose the nearest full-proof shape, "
            "remaining gaps, and immediate researcher/literature/villain follow-up. Do not verify or integrate."
        ),
    }


def _new_graph_evidence_after(state: Mapping[str, Any], since_iso: str) -> Dict[str, Any]:
    if not since_iso:
        return {}
    route_ids = [
        str(route.get("route_id") or "")
        for route in state.get("routes", [])
        if str(route.get("created_at") or "") > since_iso and str(route.get("route_id") or "")
    ]
    inference_ids = [
        str(inference.get("inference_id") or "")
        for inference in state.get("inferences", [])
        if str(inference.get("created_at") or "") > since_iso and str(inference.get("inference_id") or "")
    ]
    claim_ids = [
        str(claim.get("claim_id") or "")
        for claim in state.get("claims", [])
        if str(claim.get("claim_id") or "") != "root"
        and str(claim.get("created_at") or "") > since_iso
        and str(claim.get("claim_id") or "")
    ]
    delta: Dict[str, Any] = {}
    if route_ids:
        delta["route_ids"] = sorted(route_ids)[:8]
    if inference_ids:
        delta["inference_ids"] = sorted(inference_ids)[:8]
    if claim_ids:
        delta["claim_ids"] = sorted(claim_ids)[:8]
    return delta


def _unrouted_proof_candidate(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    last_conversion = _last_intent_run(state, PROOF_CANDIDATE_ROUTE_CONVERSION_INTENT)
    last_revision = _revision_number(last_conversion.get("state_revision")) if last_conversion else -1
    routed_artifact_ids = _routed_evidence_artifact_ids(state)
    suppression_revision, suppressed_route_ids, suppressed_target_ids = _fresh_advisor_suppression(state)
    candidates: list[tuple[int, str, Dict[str, Any]]] = []
    for artifact in state.get("research_artifacts", []):
        artifact_type = str(artifact.get("artifact_type") or "")
        if artifact_type not in PROOF_CANDIDATE_ARTIFACT_TYPES:
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        if not artifact_id or artifact_id in routed_artifact_ids:
            continue
        artifact_revision = _revision_number(artifact.get("state_revision"))
        if artifact_revision <= last_revision:
            continue
        if not _artifact_is_proof_candidate(artifact):
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        target_id = _target_id_from_metadata(state, metadata, fallback="root")
        route_id = _active_route_for_claim(state, target_id)
        if (
            suppression_revision >= 0
            and artifact_revision <= suppression_revision
            and (route_id in suppressed_route_ids or target_id in suppressed_target_ids)
        ):
            continue
        if route_id and route_verifier_readiness(state, route_id).get("verifier_ready"):
            continue
        if _proof_candidate_subsumed_by_verified_claim(state, artifact):
            continue
        candidates.append(
            (
                artifact_revision,
                artifact_id,
                {
                    "artifact_id": artifact_id,
                    "target_id": target_id,
                    "route_id": route_id,
                    "summary": str(artifact.get("content_summary") or ""),
                },
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def _proof_candidate_subsumed_by_verified_claim(state: Mapping[str, Any], artifact: Mapping[str, Any]) -> bool:
    text = _artifact_search_text(artifact)
    for signature in PROOF_CANDIDATE_SUBSUMPTION_SIGNATURES:
        artifact_terms = tuple(str(term).lower() for term in signature.get("artifact_terms", ()) if str(term))
        if not artifact_terms or not all(term in text for term in artifact_terms):
            continue
        claim_id = str(signature.get("claim_id") or "")
        claim = _claim(state, claim_id)
        if not claim or not _claim_has_mathematical_credit(claim):
            continue
        claim_text = _claim_search_text(claim)
        claim_terms = tuple(str(term).lower() for term in signature.get("claim_terms", ()) if str(term))
        if claim_terms and not all(term in claim_text for term in claim_terms):
            continue
        return True
    return False


def _claim_has_mathematical_credit(claim: Mapping[str, Any]) -> bool:
    return str(claim.get("validation_status") or "") in {"informally_verified", "formally_verified"} or str(
        claim.get("lifecycle_status") or ""
    ) in {"integrated", "proved", "closed"}


def _artifact_search_text(artifact: Mapping[str, Any]) -> str:
    metadata = _json_object(artifact.get("metadata_json"))
    return " ".join(
        [
            str(artifact.get("artifact_id") or ""),
            str(artifact.get("artifact_type") or ""),
            str(artifact.get("producer_role") or ""),
            str(artifact.get("content_summary") or ""),
            json.dumps(metadata, sort_keys=True),
        ]
    ).lower()


def _claim_search_text(claim: Mapping[str, Any]) -> str:
    metadata = _json_object(claim.get("metadata_json"))
    return " ".join(
        [
            str(claim.get("claim_id") or ""),
            str(claim.get("statement") or ""),
            str(claim.get("lifecycle_status") or ""),
            str(claim.get("validation_status") or ""),
            json.dumps(metadata, sort_keys=True),
        ]
    ).lower()


def _revision_number(value: Any) -> int:
    if value is None or value == "":
        return -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _routed_evidence_artifact_ids(state: Mapping[str, Any]) -> set[str]:
    artifact_ids: set[str] = set()
    for route in state.get("routes", []):
        artifact_ids.update(str(item) for item in _json_list(route.get("evidence_artifact_ids_json")) if str(item))
    for inference in state.get("inferences", []):
        artifact_ids.update(str(item) for item in _json_list(inference.get("evidence_artifact_ids_json")) if str(item))
    return artifact_ids


def _artifact_is_proof_candidate(artifact: Mapping[str, Any]) -> bool:
    metadata = _json_object(artifact.get("metadata_json"))
    artifact_type = str(artifact.get("artifact_type") or "")
    if _metadata_flag_false(metadata, "proof_candidate") or _metadata_flag_false(metadata, "ready_for_verifier"):
        return False
    artifact_roi = str(metadata.get("artifact_roi") or "").strip().lower()
    if artifact_roi in NON_PROOF_CANDIDATE_ARTIFACT_ROIS:
        return False
    if artifact_type == ADVISOR_REPORT_ARTIFACT_TYPE:
        return _metadata_flag_true(metadata, "proof_candidate") or _metadata_flag_true(metadata, "candidate_full_proof")
    metadata_text = json.dumps(metadata, sort_keys=True).lower()
    text = " ".join(
        [
            artifact_type,
            str(artifact.get("producer_role") or ""),
            str(artifact.get("content_summary") or ""),
            metadata_text,
        ]
    ).lower()
    negative_phrases = (
        "not verifier-ready",
        "not verifier ready",
        "no verifier-ready",
        "no verification status",
        "no verification status is asserted",
        "not marked verified",
        "no proof candidate",
        "not a proof candidate",
        "only a diagnostic",
    )
    if any(phrase in text for phrase in negative_phrases):
        return False
    positive_phrases = (
        "verifier-ready",
        "verifier ready",
        "ready_for_verifier",
        "ready for verifier",
        "proof_candidate",
        "proof candidate",
    )
    return any(phrase in text for phrase in positive_phrases) or "verify" in metadata_text or "verifier" in metadata_text


def _metadata_flag_true(metadata: Mapping[str, Any], key: str) -> bool:
    value = metadata.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return value in {1}


def _metadata_flag_false(metadata: Mapping[str, Any], key: str) -> bool:
    value = metadata.get(key)
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return value.strip().lower() in {"0", "false", "no", "n"}
    return value in {0}


def _researcher_candidate_action(
    primary_action: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    """Pair the initial literature scout with real mathematical attack."""
    if not primary_action.get("retrieval_required"):
        return None
    search_intent = str(primary_action.get("search_intent") or "literature_scoping")
    if search_intent not in {"", "literature_scoping", "local_retrieval"}:
        return None
    if primary_action.get("search_request_id") or primary_action.get("local_theorem_search_allowed"):
        return None
    root = _claim(state, "root")
    if root and root.get("lifecycle_status") == "integrated":
        return None

    debt = _first_blocking_debt(state)
    if debt:
        target_id = _claim_target_for_debt(state, debt) or "root"
        route_id = _active_route_for_claim(state, target_id)
        attack_stage = _initial_research_attack_stage(research_mode, str(target_id), state)
        if route_id:
            route = _route(state, route_id)
            if route:
                return _route_proof_construction_action(
                    state,
                    route,
                    problem=problem,
                    requested_tokens=requested_tokens,
                    research_mode=research_mode,
                    reason="parallel route proof construction while literature scout searches for matching theorems",
                    proof_repair_required=True,
                    parallel_companion=True,
                    extra={"debt_id": debt.get("debt_id", "")},
                )
            budget_action = {
                "target_id": target_id,
                "route_id": route_id,
                "search_intent": PARALLEL_ROUTE_PROOF_CONSTRUCTION_INTENT,
                "research_attack_stage": attack_stage,
                "proof_construction_required": True,
                "deep_research_required": attack_stage == "deep",
            }
            return _action(
                "reduce",
                target_id,
                route_id,
                "parallel route proof construction while literature scout searches for matching theorems",
                plan_action_budget(problem, "reduce", budget_action, requested_tokens),
                research_mode=research_mode,
                debt_id=debt.get("debt_id", ""),
                proof_repair_required=True,
                proof_construction_required=True,
                citation_allowed_in_proof=True,
                needs_proof_dossier=True,
                research_attack_stage=attack_stage,
                deep_research_required=attack_stage == "deep",
                search_intent=PARALLEL_ROUTE_PROOF_CONSTRUCTION_INTENT,
                parallel_companion=True,
            )
        budget_action = {
            "target_id": target_id,
            "search_intent": "parallel_direct_solve",
            "research_attack_stage": attack_stage,
            "deep_research_required": attack_stage == "deep",
        }
        return _action(
            "prove",
            target_id,
            "",
            "parallel direct proof attempt while literature scout searches for matching theorems",
            plan_action_budget(problem, "prove", budget_action, requested_tokens),
            research_mode=research_mode,
            debt_id=debt.get("debt_id", ""),
            direct_solve_required=True,
            research_diagnostic_required=False,
            needs_proof_dossier=True,
            research_attack_stage=attack_stage,
            deep_research_required=attack_stage == "deep",
            search_intent="parallel_direct_solve",
            parallel_companion=True,
        )

    excluded: set[str] = set()
    for _ in range(8):
        claim = _next_unverified_claim(state, exclude_ids=excluded)
        if not claim:
            return None
        route_id = _active_route_for_claim(state, claim["claim_id"])
        attack_stage = _initial_research_attack_stage(research_mode, str(claim["claim_id"]), state)
        if not route_id:
            budget_action = {
                "target_id": claim["claim_id"],
                "search_intent": "parallel_direct_solve",
                "research_attack_stage": attack_stage,
                "deep_research_required": attack_stage == "deep",
            }
            return _action(
                "prove",
                claim["claim_id"],
                "",
                "parallel direct proof attempt while literature scout searches for matching theorems",
                plan_action_budget(problem, "prove", budget_action, requested_tokens),
                research_mode=research_mode,
                direct_solve_required=True,
                research_diagnostic_required=False,
                needs_proof_dossier=True,
                research_attack_stage=attack_stage,
                deep_research_required=attack_stage == "deep",
                search_intent="parallel_direct_solve",
                parallel_companion=True,
            )
        if not _route_has_inference(state, route_id):
            route = _route(state, route_id)
            if route:
                return _route_proof_construction_action(
                    state,
                    route,
                    problem=problem,
                    requested_tokens=requested_tokens,
                    research_mode=research_mode,
                    reason="parallel researcher proof construction while literature scout searches",
                    parallel_companion=True,
                )
        excluded.add(claim["claim_id"])
    return None


def _initial_research_attack_stage(research_mode: str, target_id: str, state: Mapping[str, Any]) -> str:
    if research_mode != "hard_problem":
        return "fast"
    return "deep" if _should_deep_research(state, target_id) else "fast"


def _counterexample_companion_action(
    primary_action: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if primary_action.get("parallel_companion") and primary_action.get("counterexample_search_required"):
        return None
    if _recent_intent_seen(state, "parallel_counterexample_search", window=6):
        return None
    primary_mode = str(primary_action.get("mode") or "")
    if primary_mode not in {"prove", "reduce", "weaken", "strengthen"}:
        return None

    target_id = str(primary_action.get("target_id") or "root")
    claim = _claim(state, target_id)
    if not claim or claim.get("lifecycle_status") != "active":
        return None
    if claim.get("validation_status") not in {"untested", "plausible", "challenged"}:
        return None

    blocking_debt = _first_blocking_debt(state)
    debt_target = _claim_target_for_debt(state, blocking_debt) if blocking_debt else ""
    risky = (
        target_id == "root"
        or claim.get("validation_status") == "challenged"
        or bool(primary_action.get("duplicate_work_guard"))
        or bool(primary_action.get("research_diagnostic_required"))
        or debt_target == target_id
        or _is_root_local_high_impact_claim(state, claim)
    )
    if not risky:
        return None

    route_id = str(primary_action.get("route_id") or _active_route_for_claim(state, target_id) or "")
    budget_action = {
        "target_id": target_id,
        "counterexample_search_required": True,
        "research_attack_stage": "counterexample",
        "search_intent": "parallel_counterexample_search",
    }
    return _action(
        "refute",
        target_id,
        route_id,
        "parallel villain counterexample stress test while the main researcher tries proof/citation",
        plan_action_budget(problem, "refute", budget_action, requested_tokens),
        research_mode=research_mode,
        counterexample_search_required=True,
        research_attack_stage="counterexample",
        search_intent="parallel_counterexample_search",
        parallel_companion=True,
    )


def _is_root_local_high_impact_claim(state: Mapping[str, Any], claim: Mapping[str, Any]) -> bool:
    claim_id = str(claim.get("claim_id") or "")
    if not claim_id:
        return False
    try:
        root_impact = float(claim.get("root_impact", 0.0) or 0.0)
    except Exception:
        root_impact = 0.0
    return root_distance_for_claim_id(state, claim_id) <= 2 and root_impact >= COUNTEREXAMPLE_ROOT_LOCAL_IMPACT


def _retrieve_reduce_loop_advisor_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    loop = _recent_retrieve_reduce_loop(state)
    if not loop:
        return None

    target_id = str(loop.get("target_id") or "root")
    route_id = str(loop.get("route_id") or _active_route_for_claim(state, target_id) or "")
    reason = (
        "retrieve/reduce circuit breaker: repeated search-and-repair loop "
        "needs advisor strategy before another broad pass"
    )
    common = {
        "research_mode": research_mode,
        "strategy_advisor_required": True,
        "retrieve_reduce_loop_guard": True,
        "retrieve_reduce_loop": loop,
        "search_intent": "retrieve_reduce_circuit_breaker",
    }

    if route_id:
        readiness = _route_readiness_scorecard(state, route_id)
        if readiness.get("verifier_ready"):
            return _action(
                "prove",
                target_id,
                route_id,
                f"{reason}; verifier-ready route should be checked before advisor triage",
                plan_step_budget(problem, "prove", requested_tokens),
                route_readiness=readiness,
                **common,
            )

    decomposition_ref = _decomposition_reference_for_target(state, target_id)
    if decomposition_ref:
        return _action(
            "regulate_decomposition",
            decomposition_ref["parent_id"],
            decomposition_ref.get("route_id", ""),
            f"{reason}; regulate the stalled decomposition branch",
            plan_step_budget(problem, "regulate_decomposition", requested_tokens),
            decomposition_regulator_required=True,
            decomposition_plan_id=decomposition_ref["decomposition_plan_id"],
            decomposition_plan_artifact_id=decomposition_ref["artifact_id"],
            blocked_branch_ids=[target_id],
            **common,
        )

    return _action(
        "triage_routes",
        "root",
        route_id,
        f"{reason}; advisor should choose verify, repair, source synthesis, refute, or abandon",
        plan_step_budget(problem, "triage_routes", requested_tokens),
        route_triage_required=True,
        route_triage_reason=reason,
        **common,
    )


def _recent_retrieve_reduce_loop(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if _recent_intent_seen(state, "retrieve_reduce_circuit_breaker", window=RETRIEVE_REDUCE_LOOP_WINDOW):
        return None
    recent = []
    for row in list(state.get("recent_runs", []))[:RETRIEVE_REDUCE_LOOP_WINDOW]:
        mode = str(row.get("mode") or "")
        if mode not in {"retrieve", "reduce"}:
            break
        recent.append(row)
    if len(recent) < RETRIEVE_REDUCE_LOOP_MIN_COUNT:
        return None

    target_id = str(recent[0].get("target_id") or "root")
    route_id = str(recent[0].get("route_id") or "")
    same_target = [
        row for row in recent
        if str(row.get("target_id") or "root") == target_id
        and (not route_id or not str(row.get("route_id") or "") or str(row.get("route_id") or "") == route_id)
    ]
    if len(same_target) < RETRIEVE_REDUCE_LOOP_MIN_COUNT:
        return None
    modes = {str(row.get("mode") or "") for row in same_target}
    if not {"retrieve", "reduce"} <= modes:
        return None
    route_ids = [str(row.get("route_id") or "") for row in same_target if str(row.get("route_id") or "")]
    if not route_id and route_ids:
        route_id = route_ids[0]
    return {
        "policy": "retrieve-reduce-circuit-breaker",
        "window": RETRIEVE_REDUCE_LOOP_WINDOW,
        "minimum_count": RETRIEVE_REDUCE_LOOP_MIN_COUNT,
        "count": len(same_target),
        "target_id": target_id,
        "route_id": route_id,
        "recent_modes": [str(row.get("mode") or "") for row in same_target],
        "recent_search_intents": [str(row.get("search_intent") or "") for row in same_target],
    }


def _parallel_wave_synthesis_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    wave = _recent_parallel_attack_wave(state)
    if not wave:
        return None
    target_id = str(wave.get("target_id") or "root")
    route_id = str(wave.get("route_id") or _active_route_for_claim(state, target_id) or "")
    mode = "reduce" if route_id else "prove"
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "research_attack_stage": "synthesis",
        "search_intent": "parallel_wave_synthesis",
    }
    return _action(
        mode,
        target_id,
        route_id,
        "synthesize the recent parallel proof/literature/counterexample wave before scheduling more branch work",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        research_synthesis_required=True,
        approach_portfolio_synthesis_required=True,
        parallel_wave_summary=wave,
        needs_proof_dossier=True,
        research_attack_stage="synthesis",
        search_intent="parallel_wave_synthesis",
    )


def _recent_parallel_attack_wave(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if _recent_intent_seen(state, "parallel_wave_synthesis", window=PARALLEL_SYNTHESIS_WINDOW):
        return None
    if _recent_intent_seen(state, "route_triage", window=3) or _recent_intent_seen(state, "decomposition_regulator", window=3):
        return None

    relevant: list[Mapping[str, Any]] = []
    categories: dict[str, list[str]] = {}
    target_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    for row in list(state.get("recent_runs", []))[:PARALLEL_SYNTHESIS_WINDOW]:
        intent = str(row.get("search_intent") or "")
        category = _parallel_wave_category(intent)
        if not category:
            if relevant:
                break
            return None
        relevant.append(row)
        categories.setdefault(category, []).append(intent)
        target_id = str(row.get("target_id") or "root")
        route_id = str(row.get("route_id") or "")
        target_counts[target_id] = target_counts.get(target_id, 0) + 1
        if route_id:
            route_counts[route_id] = route_counts.get(route_id, 0) + 1

    if len(categories) < PARALLEL_SYNTHESIS_MIN_CATEGORIES:
        return None
    if not any(intent.startswith("parallel_") for intents in categories.values() for intent in intents):
        return None

    target_id = _most_common_key(target_counts) or "root"
    route_id = _most_common_key(route_counts)
    return {
        "policy": "parallel-attack-synthesis",
        "window": PARALLEL_SYNTHESIS_WINDOW,
        "category_count": len(categories),
        "categories": {key: sorted(set(value)) for key, value in categories.items()},
        "run_count": len(relevant),
        "target_id": target_id,
        "route_id": route_id,
        "recent_run_ids": [str(row.get("run_id") or "") for row in relevant],
        "recent_search_intents": [str(row.get("search_intent") or "") for row in relevant],
    }


def _parallel_wave_category(intent: str) -> str:
    if intent in {"literature_scoping", "researcher_search_request", "local_retrieval"}:
        return "literature"
    if intent in {"parallel_direct_solve", "parallel_independent_solve", "parallel_decomposition_branch", PARALLEL_ROUTE_PROOF_CONSTRUCTION_INTENT}:
        return "proof_attack"
    if intent == "parallel_counterexample_search":
        return "counterexample_attack"
    return ""


def _most_common_key(counts: Mapping[str, int]) -> str:
    candidates = [(count, key) for key, count in counts.items() if key]
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1]


def _no_result_search_synthesis_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if _recent_intent_seen(state, "no_result_search_synthesis", window=8):
        return None
    no_result = _no_result_search_cluster(state)
    if not no_result:
        return None
    target_id = str(no_result.get("target_id") or "root")
    route_id = str(no_result.get("route_id") or _active_route_for_claim(state, target_id) or "")
    mode = "reduce" if route_id else "prove"
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "research_attack_stage": "synthesis",
        "search_intent": "no_result_search_synthesis",
    }
    return _action(
        mode,
        target_id,
        route_id,
        "repeated no-useful-result theorem searches require researcher synthesis/proof invention before another search",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        research_synthesis_required=True,
        no_result_search_synthesis_required=True,
        bridge_lemma_workbench_required=True,
        closure_pressure_required=True,
        negative_result_ledger_required=True,
        proof_architecture_templates_required=True,
        cas_check_recommended=True,
        no_result_search_cluster=no_result,
        no_result_card_ids=no_result.get("card_ids", []),
        needs_proof_dossier=True,
        direct_solve_required=(mode == "prove"),
        research_attack_stage="synthesis",
        search_intent="no_result_search_synthesis",
    )


def _no_result_search_cluster(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for card in state.get("retrieval_cards", []):
        applicability = _json_object(card.get("applicability_json"))
        relation = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation") or "")
        status = str(applicability.get("theorem_matching_status") or "").lower()
        if relation != "no_useful_result_found" and "no_useful" not in status and "no useful" not in status:
            continue
        target_id = str(applicability.get("target_id") or "root")
        route_id = str(applicability.get("route_id") or "")
        grouped.setdefault((target_id, route_id), []).append(str(card.get("card_id") or ""))

    candidates = [
        (len(card_ids), target_id, route_id, sorted(card_ids))
        for (target_id, route_id), card_ids in grouped.items()
        if len(card_ids) >= NO_RESULT_SEARCH_SYNTHESIS_THRESHOLD
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    count, target_id, route_id, card_ids = candidates[0]
    return {
        "policy": "repeated-no-result-search-synthesis",
        "threshold": NO_RESULT_SEARCH_SYNTHESIS_THRESHOLD,
        "count": count,
        "target_id": target_id,
        "route_id": route_id,
        "card_ids": card_ids,
    }


def _proof_architecture_pressure_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if _recent_intent_seen(state, PROOF_ARCHITECTURE_PRESSURE_INTENT, window=PROOF_ARCHITECTURE_SIGNAL_WINDOW):
        return None
    signal = _proof_architecture_pressure_signal(state)
    if not signal:
        return None
    target_id = str(signal.get("target_id") or "root")
    creative_pressure = research_mode == "hard_problem"
    budget_action = {
        "target_id": target_id,
        "direct_solve_required": True,
        "deep_research_required": True,
        "research_attack_stage": "creative" if creative_pressure else "proof_architecture",
        "search_intent": PROOF_ARCHITECTURE_PRESSURE_INTENT,
    }
    return _action(
        "prove",
        target_id,
        "",
        "repeated mathematical evidence and blockers require a current proof architecture, not another isolated local pass",
        plan_action_budget(problem, "prove", budget_action, requested_tokens),
        research_mode=research_mode,
        creative_proof_attack_required=creative_pressure,
        wild_mathematician_mode=creative_pressure,
        direct_solve_required=True,
        needs_proof_dossier=True,
        deep_research_required=True,
        research_synthesis_required=True,
        proof_architecture_required=True,
        proof_pressure_scheduler_required=True,
        route_contract_required=True,
        obligation_reduction_required=True,
        speculative_proof_required=True,
        obstruction_inversion_required=creative_pressure,
        analogy_pass_required=creative_pressure,
        failure_autopsy_required=creative_pressure,
        bottleneck_ownership_required=creative_pressure,
        paperwork_throttle_required=creative_pressure,
        creative_attack_signal=signal if creative_pressure else {},
        repair_loop_required=True,
        current_best_plan_required=True,
        dead_route_suppression_required=True,
        proof_architecture_signal=signal,
        paused_route_ids=signal.get("paused_route_ids", []),
        blocked_route_ids=signal.get("blocked_route_ids", []),
        stalled_route_ids=signal.get("stalled_route_ids", []),
        route_status_semantics=signal.get("route_status_semantics", {}),
        research_attack_stage="creative" if creative_pressure else "proof_architecture",
        search_intent=PROOF_ARCHITECTURE_PRESSURE_INTENT,
    )


def _decisive_theorem_test_payload(
    signal: Mapping[str, Any],
    *,
    target_id: str,
    route_id: str,
    central_payload: Mapping[str, Any],
) -> Dict[str, Any]:
    if not signal:
        return {}
    payload: Dict[str, Any] = {
        "decisive_theorem_test_required": True,
        "decisive_theorem_test": dict(signal),
        "central_debt_id": str(signal.get("debt_id") or ""),
        "debt_id": str(signal.get("debt_id") or ""),
        "bridge_lemma_workbench_required": True,
        "closure_pressure_required": True,
        "obligation_reduction_required": True,
        "needs_proof_dossier": True,
        "deep_research_required": True,
        "paperwork_throttle_required": True,
        "negative_result_ledger_required": True,
        "proof_architecture_templates_required": True,
    }
    if not central_payload.get("central_obstruction"):
        payload["central_obstruction"] = {
            "policy": "decisive-theorem-test",
            "target_id": target_id,
            "route_id": route_id,
            "debt_id": str(signal.get("debt_id") or ""),
            "obligation": str(signal.get("theorem_obligation") or ""),
            "acceptance_criteria": list(signal.get("acceptance_criteria") or []),
        }
    return payload


def _bottleneck_lock_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    signal = _bottleneck_lock_signal(state)
    if not signal:
        return None

    debt_id = str(signal.get("debt_id") or "")
    blocking_debt = next(
        (row for row in state.get("debts", []) if str(row.get("debt_id") or "") == debt_id),
        None,
    )
    target_id = str(signal.get("target_id") or "root")
    if not _claim(state, target_id):
        target_id = "root"
    route_id = ""
    central_payload: Dict[str, Any] = {}
    if blocking_debt:
        route_id = _route_for_debt(state, blocking_debt, target_id)
        central_payload = _central_obstruction_payload(state, blocking_debt)
    if not route_id:
        route_id = _active_route_for_claim(state, target_id)
    mode = "reduce" if route_id else "prove"

    decisive_signal = decisive_theorem_test_signal(state, debt_id=debt_id) or _synthetic_bottleneck_decisive_signal(
        signal, blocking_debt
    )
    decisive_payload = _decisive_theorem_test_payload(
        decisive_signal,
        target_id=target_id,
        route_id=route_id,
        central_payload=central_payload,
    )
    combined_payload = {**central_payload, **decisive_payload}
    for duplicate_key in (
        "debt_id",
        "bridge_lemma_workbench_required",
        "closure_pressure_required",
        "obligation_reduction_required",
        "needs_proof_dossier",
        "deep_research_required",
        "paperwork_throttle_required",
    ):
        combined_payload.pop(duplicate_key, None)
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "direct_solve_required": mode == "prove",
        "proof_construction_required": mode == "reduce",
        "deep_research_required": True,
        "decisive_theorem_test_required": True,
        "bottleneck_lock_required": True,
        "proof_spine_mode_required": True,
        "rethlas_defeat_loop_required": True,
        "exact_librarian_companion_required": True,
        "advisor_compression_after_integration_required": True,
        "research_attack_stage": "bottleneck_lock",
        "search_intent": BOTTLENECK_LOCK_INTENT,
    }
    return _action(
        mode,
        target_id,
        route_id,
        "repeated bottleneck diagnostics have cooled down; force a decisive theorem attack before more synthesis or route inventories",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        debt_id=debt_id,
        proof_repair_required=bool(route_id),
        proof_construction_required=bool(route_id),
        direct_solve_required=not bool(route_id),
        citation_allowed_in_proof=bool(route_id),
        needs_proof_dossier=True,
        deep_research_required=True,
        research_attack_stage="bottleneck_lock",
        search_intent=BOTTLENECK_LOCK_INTENT,
        bottleneck_lock_required=True,
        bottleneck_lock_signal=signal,
        diagnostic_cooldown_active=True,
        diagnostic_artifact_ids=list(signal.get("diagnostic_artifact_ids") or []),
        research_diagnostic_required=False,
        proof_spine_mode_required=True,
        proof_spine_min_lemmas=3,
        proof_spine_max_lemmas=6,
        rethlas_defeat_loop_required=True,
        exact_librarian_companion_required=True,
        advisor_compression_after_integration_required=True,
        proof_route_conversion_required=True,
        duplicate_math_guard_required=True,
        villain_obstruction_to_lemma_required=True,
        near_miss_memory_required=True,
        bridge_lemma_workbench_required=True,
        closure_pressure_required=True,
        obligation_reduction_required=True,
        sublemma_extraction_required=True,
        side_branch_roi_cap_active=True,
        main_trunk_compute_reserved=True,
        bottleneck_ownership_required=True,
        paperwork_throttle_required=True,
        forbidden_outputs=[
            "broad research_diagnostic",
            "route inventory without proof attempt",
            "management-only research_notebook",
            "new decomposition without assembly argument",
            "restatement of an already accepted theorem without attacking the newest child debt",
        ],
        hard_theorem_attack_contract={
            "prove_budget_fraction": 0.70,
            "refute_budget_fraction": 0.20,
            "next_obligation_fraction": 0.10,
            "required_shape": "short proof spine plus one decisive theorem/counterexample outcome",
        },
        **combined_payload,
    )


def _bottleneck_lock_signal(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if verifier_ready_route_summaries(state):
        return None
    debts = _bottleneck_lock_debt_candidates(state)
    if not debts:
        return None
    diagnostics = _recent_bottleneck_diagnostic_artifacts(state)
    diagnostic_count = len(diagnostics)
    eligible: list[Mapping[str, Any]] = []
    for debt in debts:
        repeated = int(debt.get("repeated_count") or 0)
        decisive = bool(decisive_theorem_test_signal(state, debt_id=str(debt.get("debt_id") or "")))
        if repeated >= BOTTLENECK_LOCK_REPEAT_THRESHOLD:
            eligible.append(debt)
            continue
        if decisive and diagnostic_count >= 1:
            eligible.append(debt)
            continue
        if diagnostic_count >= BOTTLENECK_LOCK_MIN_DIAGNOSTIC_ARTIFACTS:
            eligible.append(debt)
    if not eligible:
        return None
    debt = eligible[0]
    target_id = _claim_target_for_debt(state, debt) or "root"
    if not _claim(state, target_id):
        target_id = "root"
    repeated_count = int(debt.get("repeated_count") or 0)
    trigger = "repeated_debt" if repeated_count >= BOTTLENECK_LOCK_REPEAT_THRESHOLD else "diagnostic_cooldown"
    return {
        "policy": "bottleneck-lock",
        "trigger": trigger,
        "target_id": target_id,
        "debt_id": str(debt.get("debt_id") or ""),
        "owner_type": str(debt.get("owner_type") or ""),
        "owner_id": str(debt.get("owner_id") or ""),
        "suggested_next_target": str(debt.get("suggested_next_target") or ""),
        "debt_type": str(debt.get("debt_type") or ""),
        "repeated_count": repeated_count,
        "obligation": _compact_text(str(debt.get("obligation") or ""), 900),
        "diagnostic_artifact_ids": [str(row.get("artifact_id") or "") for row in diagnostics[:6]],
        "diagnostic_count": diagnostic_count,
        "required_output": {
            "primary": "proof_dossier, proof_blueprint, route_obstruction, construction_failure, exact citation, or one narrower theorem-level debt",
            "forbidden": "broad diagnostic, route inventory, or management-only notebook as the main output",
            "sublemma_policy": "if the theorem is too large, extract one verifier-checkable sublemma with an assembly argument",
        },
    }


def bottleneck_frontier_summary(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Compact UI/metrics summary of the current root-local proof bottleneck."""
    debts = _bottleneck_lock_debt_candidates(state)
    diagnostics = _recent_bottleneck_diagnostic_artifacts(state)
    artifacts = _artifact_index(state)
    top = debts[0] if debts else {}
    target_id = _claim_target_for_debt(state, top) if top else ""
    if target_id and not _claim(state, target_id):
        target_id = "root"
    proof_runs = 0
    diagnostic_runs = 0
    side_runs = 0
    for run in state.get("recent_runs", []):
        intent = str(run.get("search_intent") or "")
        mode = str(run.get("mode") or "")
        run_target = str(run.get("target_id") or "")
        if intent in {BOTTLENECK_LOCK_INTENT, DECISIVE_THEOREM_TEST_INTENT, BRIDGE_LEMMA_WORKBENCH_INTENT, ROUTE_PROOF_CONSTRUCTION_INTENT}:
            proof_runs += 1
        if "diagnostic" in intent or mode in {"triage_routes", "regulate_decomposition"}:
            diagnostic_runs += 1
        if target_id and run_target and run_target != target_id:
            side_runs += 1
    return {
        "policy": "current-bottleneck-frontier",
        "locked": bool(_bottleneck_lock_signal(state)),
        "lock_state_label": "armed" if _bottleneck_lock_signal(state) else "watching",
        "current_bottleneck": {
            "debt_id": str(top.get("debt_id") or ""),
            "target_id": target_id,
            "owner_type": str(top.get("owner_type") or ""),
            "owner_id": str(top.get("owner_id") or ""),
            "debt_type": str(top.get("debt_type") or ""),
            "repeated_count": int(top.get("repeated_count") or 0) if top else 0,
            "fresh_narrowing_score": _fresh_narrowed_debt_score(top, artifacts) if top else 0,
            "source_artifact_ids": _debt_source_artifact_ids(top)[:6] if top else [],
            "obligation": _compact_text(str(top.get("obligation") or ""), 260) if top else "",
        },
        "diagnostic_cooldown": {
            "recent_diagnostic_count": len(diagnostics),
            "artifact_ids": [str(row.get("artifact_id") or "") for row in diagnostics[:6]],
            "active": len(diagnostics) >= BOTTLENECK_LOCK_MIN_DIAGNOSTIC_ARTIFACTS,
        },
        "compute_shape": {
            "recent_proof_attack_runs": proof_runs,
            "recent_diagnostic_runs": diagnostic_runs,
            "recent_side_target_runs": side_runs,
            "main_trunk_reserved_when_locked": True,
        },
        "top_bottleneck_debts": [
            {
                "debt_id": str(row.get("debt_id") or ""),
                "target_id": _claim_target_for_debt(state, row) or "root",
                "repeated_count": int(row.get("repeated_count") or 0),
                "fresh_narrowing_score": _fresh_narrowed_debt_score(row, artifacts),
                "obligation": _compact_text(str(row.get("obligation") or ""), 180),
            }
            for row in debts[:5]
        ],
    }


def proof_spine_summary(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Small active proof spine for UI and role prompts.

    This is deliberately not the whole proof graph. It highlights the trunk that
    should receive compute: verified near-root lemmas, best active routes, the
    currently armed bottleneck, and recent proof artifacts that changed the next
    mathematical obligation.
    """
    verified_claims: list[Mapping[str, Any]] = []
    for claim in state.get("claims", []):
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id or claim_id == "root":
            continue
        if str(claim.get("validation_status") or "") not in {"informally_verified", "formally_verified"}:
            continue
        if str(claim.get("lifecycle_status") or "") not in {"active", "integrated"}:
            continue
        distance = root_distance_for_claim_id(state, claim_id)
        if distance > 2 and float(claim.get("root_impact", 0.0) or 0.0) < 0.55:
            continue
        verified_claims.append(claim)
    verified_claims.sort(
        key=lambda row: (
            root_distance_for_claim_id(state, str(row.get("claim_id") or "")),
            -float(row.get("root_impact", 0.0) or 0.0),
            str(row.get("claim_id") or ""),
        )
    )

    routes = route_scoreboard(state, limit=8)
    active_routes = [
        {
            "route_id": str(row.get("route_id") or ""),
            "target_id": str(row.get("target_id") or row.get("conclusion_claim_id") or ""),
            "status": str(row.get("scoreboard_status") or row.get("status") or ""),
            "score": row.get("score", 0),
            "summary": _compact_text(str(row.get("summary") or row.get("strategy") or ""), 180),
        }
        for row in routes[:5]
    ]
    artifacts = _recent_proof_spine_artifacts(state, limit=6)
    bottleneck = bottleneck_frontier_summary(state).get("current_bottleneck", {})
    return {
        "policy": "active-proof-spine",
        "root_status": str((_claim(state, "root") or {}).get("validation_status") or "untested"),
        "verified_trunk_claims": [
            {
                "claim_id": str(row.get("claim_id") or ""),
                "root_impact": float(row.get("root_impact", 0.0) or 0.0),
                "root_distance": root_distance_for_claim_id(state, str(row.get("claim_id") or "")),
                "statement": _compact_text(str(row.get("statement") or ""), 180),
            }
            for row in verified_claims[:6]
        ],
        "active_routes": active_routes,
        "current_bottleneck": bottleneck,
        "verifier_ready_routes": verifier_ready_route_summaries(state)[:5],
        "recent_spine_artifacts": artifacts,
        "next_workflow_rule": (
            "Prefer a short verifier-checkable lemma chain. Convert proof-like artifacts into routes/inferences; "
            "if blocked, name exactly one next theorem-level debt."
        ),
    }


def _recent_proof_spine_artifacts(state: Mapping[str, Any], *, limit: int) -> list[Dict[str, Any]]:
    artifacts = state.get("research_artifacts")
    if not isinstance(artifacts, list):
        artifacts = state.get("artifacts", [])
    rows: list[Mapping[str, Any]] = []
    for artifact in artifacts:
        artifact_type = str(artifact.get("artifact_type") or "")
        if artifact_type not in PROOF_SPINE_ARTIFACT_TYPES:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        roi = str(metadata.get("artifact_roi") or "")
        if artifact_type in {"advisor_report"} and not (
            metadata.get("current_best_plan")
            or metadata.get("next_decisive_action")
            or metadata.get("recommended_next_action")
            or metadata.get("proof_candidate")
        ):
            continue
        if roi and roi not in FRESH_NARROWED_DEBT_ROIS and artifact_type not in {"proof_dossier", "proof_blueprint"}:
            continue
        rows.append(artifact)
    rows.sort(key=lambda row: (_revision_number(row.get("state_revision")), str(row.get("created_at") or "")), reverse=True)
    result: list[Dict[str, Any]] = []
    for row in rows[:limit]:
        metadata = _json_object(row.get("metadata_json"))
        result.append(
            {
                "artifact_id": str(row.get("artifact_id") or ""),
                "artifact_type": str(row.get("artifact_type") or ""),
                "producer_role": str(row.get("producer_role") or ""),
                "state_revision": _revision_number(row.get("state_revision")),
                "roi": str(metadata.get("artifact_roi") or ""),
                "next_decisive_action": _compact_text(
                    str(metadata.get("next_decisive_action") or metadata.get("recommended_next_action") or ""),
                    180,
                ),
                "summary": _compact_text(str(row.get("content_summary") or row.get("title") or ""), 180),
            }
        )
    return result


def _bottleneck_lock_debt_candidates(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    debts: list[Mapping[str, Any]] = []
    artifact_index = _artifact_index(state)
    for debt in state.get("debts", []):
        if str(debt.get("status") or "") != "active" or str(debt.get("severity") or "") != "blocking":
            continue
        if _debt_covered_by_integrated_claim(state, debt):
            continue
        target_id = _claim_target_for_debt(state, debt) or str(debt.get("owner_id") or "root")
        distance = root_distance_for_claim_id(state, target_id)
        if target_id != "root" and distance > FAR_FROM_ROOT_DISTANCE and _root_impact_for_target(state, target_id) < 0.5:
            continue
        debts.append(debt)

    def priority(row: Mapping[str, Any]) -> tuple[int, int, int, int, int, str]:
        target_id = _claim_target_for_debt(state, row) or str(row.get("owner_id") or "root")
        text = _debt_math_text(row)
        theoremish = int(
            any(term in text for term in ("theorem", "lemma", "criterion", "bridge", "classification", "construction", "obstruction"))
        )
        fresh_score = _fresh_narrowed_debt_score(row, artifact_index)
        return (
            -fresh_score,
            -int(row.get("repeated_count") or 0),
            -theoremish,
            root_distance_for_claim_id(state, target_id),
            -_iso_sort_number(row.get("last_seen")),
            str(row.get("debt_id") or ""),
        )

    debts.sort(key=priority)
    return debts


def _debt_covered_by_integrated_claim(state: Mapping[str, Any], debt: Mapping[str, Any]) -> bool:
    return bool(integrated_claim_covering_debt_id(state.get("claims", []), obligation=_debt_math_text(debt)))


def _artifact_index(state: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    artifacts = state.get("research_artifacts")
    if not isinstance(artifacts, list):
        artifacts = state.get("artifacts", [])
    return {
        str(row.get("artifact_id") or ""): row
        for row in artifacts
        if str(row.get("artifact_id") or "")
    }


def _fresh_narrowed_debt_score(
    debt: Mapping[str, Any],
    artifact_index: Mapping[str, Mapping[str, Any]],
) -> int:
    score = 0
    debt_type = str(debt.get("debt_type") or "")
    if debt_type in {"central_obstruction", "proof_obligation", "blocking_bridge", "missing_proof_or_counterexample"}:
        score += 2
    debt_id = str(debt.get("debt_id") or "").lower()
    text = _debt_math_text(debt)
    if any(term in text for term in ("remaining", "mixed", "component", "trap", "exact", "refute", "construct")):
        score += 1
    if "rev" in debt_id:
        score += 1
    source_ids = _debt_source_artifact_ids(debt)
    for artifact_id in source_ids:
        artifact = artifact_index.get(artifact_id)
        if not artifact:
            continue
        artifact_type = str(artifact.get("artifact_type") or "")
        metadata = _json_object(artifact.get("metadata_json"))
        roi = str(metadata.get("artifact_roi") or "")
        if roi in FRESH_NARROWED_DEBT_ROIS:
            score += 6
        if artifact_type in PROOF_SPINE_ARTIFACT_TYPES:
            score += 3
        if metadata.get("next_decisive_action") or metadata.get("what_changed"):
            score += 2
        if str(metadata.get("central_debt_id") or ""):
            score += 1
        score += min(3, _revision_number(artifact.get("state_revision")) // 100)
    if source_ids:
        score += 1
    return score


def _debt_source_artifact_ids(debt: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("source_artifact_ids", "source_artifact_ids_json", "evidence_artifact_ids", "evidence_artifact_ids_json"):
        value = debt.get(key)
        for item in _as_list(value) or _json_list(value):
            artifact_id = str(item or "").strip()
            if artifact_id and artifact_id not in ids:
                ids.append(artifact_id)
    return ids


def _iso_sort_number(value: Any) -> int:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits:
        return 0
    return int(digits[:14])


def _recent_bottleneck_diagnostic_artifacts(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    artifacts = list(state.get("research_artifacts") or state.get("artifacts") or [])
    rows: list[Mapping[str, Any]] = []
    for artifact in artifacts:
        artifact_type = str(artifact.get("artifact_type") or "")
        if artifact_type not in BOTTLENECK_DIAGNOSTIC_ARTIFACT_TYPES:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        target_id = _target_id_from_metadata(state, metadata, fallback="root")
        if target_id != "root" and _root_impact_for_target(state, target_id) < 0.5:
            continue
        text = " ".join(
            [
                str(artifact_type),
                str(artifact.get("content_summary") or ""),
                json.dumps(metadata, sort_keys=True),
            ]
        ).lower()
        if not any(
            cue in text
            for cue in (
                "bottleneck",
                "not route-ready",
                "not verifier-ready",
                "remaining gap",
                "missing",
                "failed",
                "obstruction",
                "next decisive",
                "narrower",
                "do not retry",
            )
        ):
            continue
        rows.append(artifact)
    rows.sort(key=lambda row: (_revision_number(row.get("state_revision")), str(row.get("created_at") or "")), reverse=True)
    return rows[:8]


def _synthetic_bottleneck_decisive_signal(
    signal: Mapping[str, Any],
    debt: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    obligation = str(signal.get("obligation") or (debt or {}).get("obligation") or "")
    return {
        "policy": "bottleneck-lock-theorem-test",
        "target_id": str(signal.get("target_id") or "root"),
        "debt_id": str(signal.get("debt_id") or ""),
        "owner_id": str(signal.get("owner_id") or (debt or {}).get("owner_id") or ""),
        "debt_type": str(signal.get("debt_type") or (debt or {}).get("debt_type") or ""),
        "theorem_obligation": _compact_text(obligation, 900),
        "why_decisive": (
            "This root-local blocking obligation has repeated or diagnostic pressure. Decide it directly so the run stops "
            "spending passes on broad synthesis around the same gap."
        ),
        "acceptance_criteria": [
            "State the exact theorem or counterexample test in local notation.",
            "Either prove it, refute it, or cite a precise theorem with checked hypotheses.",
            "If it is too large, extract one strictly narrower verifier-checkable sublemma plus an assembly argument.",
            "Do not produce broad route inventories or management-only diagnostics.",
        ],
    }


def _debt_math_text(debt: Mapping[str, Any]) -> str:
    return " ".join(
        str(debt.get(key) or "")
        for key in ("debt_id", "debt_type", "obligation", "suggested_next_target")
    ).lower()


def _proof_architecture_pressure_signal(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if verifier_ready_route_summaries(state):
        return None

    target_id = "root"
    scored_routes = route_scoreboard(state, limit=12)
    paused = paused_route_ids(state)
    blocked_route_ids = [
        str(row.get("route_id") or "")
        for row in scored_routes
        if str(row.get("scoreboard_status") or "") == "blocked"
    ]
    stalled_route_ids = [
        str(row.get("route_id") or "")
        for row in scored_routes
        if str(row.get("scoreboard_status") or "") == "stalled"
    ]
    active_blocking_debts = [
        row for row in state.get("debts", [])
        if str(row.get("status") or "") == "active" and str(row.get("severity") or "") == "blocking"
    ]

    relevant_artifacts: list[Mapping[str, Any]] = []
    for artifact in state.get("research_artifacts", []):
        artifact_type = str(artifact.get("artifact_type") or "")
        if artifact_type not in PROOF_ARCHITECTURE_SIGNAL_TYPES:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        artifact_target = str(
            metadata.get("target_id")
            or metadata.get("claim_id")
            or metadata.get("recommended_target_id")
            or target_id
        )
        if artifact_target and artifact_target != target_id and _root_impact_for_target(state, artifact_target) < 0.5:
            continue
        relevant_artifacts.append(artifact)

    relevant_artifacts.sort(
        key=lambda row: (int(row.get("state_revision") or 0), str(row.get("created_at") or "")),
        reverse=True,
    )
    signal_artifacts = relevant_artifacts[:8]
    repeated_debts = [
        row for row in active_blocking_debts
        if int(row.get("repeated_count") or 0) >= 2
    ]

    enough_evidence = len(signal_artifacts) >= PROOF_ARCHITECTURE_MIN_SIGNAL_ARTIFACTS
    enough_pressure = len(active_blocking_debts) >= 2 or bool(paused) or bool(repeated_debts)
    if not (enough_evidence and enough_pressure):
        return None

    return {
        "policy": "proof-architecture-pressure",
        "target_id": target_id,
        "signal_artifact_ids": [str(row.get("artifact_id") or "") for row in signal_artifacts],
        "signal_artifact_types": sorted({str(row.get("artifact_type") or "") for row in signal_artifacts if row.get("artifact_type")}),
        "signal_producer_roles": sorted({str(row.get("producer_role") or "") for row in signal_artifacts if row.get("producer_role")}),
        "active_blocking_debt_ids": [str(row.get("debt_id") or "") for row in active_blocking_debts[:10]],
        "repeated_blocking_debt_ids": [str(row.get("debt_id") or "") for row in repeated_debts[:10]],
        "paused_route_ids": sorted(str(route_id) for route_id in paused if route_id),
        "blocked_route_ids": sorted(route_id for route_id in blocked_route_ids if route_id),
        "stalled_route_ids": sorted(route_id for route_id in stalled_route_ids if route_id),
        "route_scoreboard": [
            {
                "route_id": str(row.get("route_id") or ""),
                "status": str(row.get("scoreboard_status") or ""),
                "score": row.get("score"),
                "root_distance": row.get("root_distance"),
                "root_impact": row.get("root_impact"),
                "kill_reasons": row.get("kill_reasons", []),
            }
            for row in scored_routes[:8]
        ],
        "route_status_semantics": {
            "blocked": "explicit route.status=blocked; the route is intentionally paused pending a central obstruction or proof debt",
            "stalled": "heuristic health label; the route is still active but repeated blockers or failed attempts make ordinary proof construction low-value",
        },
        "required_output": {
            "current_best_plan": "name exactly one proof architecture to pursue now",
            "route_contracts": "for each kept route, state hypotheses, proof obligation, evidence needed, acceptance criteria, and abandonment criteria",
            "bottleneck_obligation": "reduce the proof to the smallest named lemma/debt that would unlock the plan",
            "repair_attempt": "try to repair the best existing route before opening a new trunk",
            "speculative_proof_attempt": "write a clearly labeled possible proof skeleton and mark unproved steps",
        },
    }


def _creative_proof_attack_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if research_mode != "hard_problem":
        return None
    if _recent_intent_seen(state, CREATIVE_PROOF_ATTACK_INTENT, window=CREATIVE_ATTACK_WINDOW):
        return None
    signal = _creative_proof_attack_signal(state)
    if not signal:
        return None
    target_id = str(signal.get("target_id") or "root")
    route_id = str(signal.get("route_id") or _active_route_for_claim(state, target_id) or "")
    mode = "reduce" if route_id else "prove"
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "deep_research_required": True,
        "research_attack_stage": "creative",
        "creative_proof_attack_required": True,
        "search_intent": CREATIVE_PROOF_ATTACK_INTENT,
    }
    return _action(
        mode,
        target_id,
        route_id,
        "certified partial progress plus repeated bottleneck signals call for a creative full-proof attack before more local bookkeeping",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        creative_proof_attack_required=True,
        wild_mathematician_mode=True,
        direct_solve_required=(mode == "prove"),
        proof_construction_required=bool(route_id),
        citation_allowed_in_proof=bool(route_id),
        needs_proof_dossier=True,
        deep_research_required=True,
        research_synthesis_required=True,
        global_synthesis_required=True,
        proof_architecture_required=True,
        route_contract_required=True,
        obligation_reduction_required=True,
        speculative_proof_required=True,
        obstruction_inversion_required=True,
        analogy_pass_required=True,
        failure_autopsy_required=True,
        bottleneck_ownership_required=True,
        paperwork_throttle_required=True,
        creative_attack_signal=signal,
        research_attack_stage="creative",
        search_intent=CREATIVE_PROOF_ATTACK_INTENT,
    )


def _creative_proof_attack_signal(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if verifier_ready_route_summaries(state):
        return None

    root = _claim(state, "root")
    if root and str(root.get("lifecycle_status") or "") == "integrated":
        return None

    partial_claims = [
        row for row in state.get("claims", [])
        if str(row.get("claim_id") or "") != "root"
        and root_distance_for_claim_id(state, str(row.get("claim_id") or "")) <= 3
        and str(row.get("validation_status") or "") in {"informally_verified", "formally_verified"}
    ]
    integrated_claims = [
        row for row in state.get("claims", [])
        if str(row.get("claim_id") or "") != "root"
        and root_distance_for_claim_id(state, str(row.get("claim_id") or "")) <= 3
        and str(row.get("lifecycle_status") or "") == "integrated"
    ]
    partial_credit_ids = {
        str(row.get("claim_id") or "")
        for row in [*partial_claims, *integrated_claims]
        if str(row.get("claim_id") or "")
    }
    if len(partial_credit_ids) < CREATIVE_ATTACK_MIN_PARTIAL_CREDIT:
        return None

    active_blocking_debts = [
        row for row in state.get("debts", [])
        if str(row.get("status") or "") == "active"
        and str(row.get("severity") or "") == "blocking"
        and (
            str(row.get("owner_id") or "") == "root"
            or str(row.get("suggested_next_target") or "") == "root"
            or root_distance_for_claim_id(state, str(row.get("owner_id") or "")) <= 3
            or root_distance_for_claim_id(state, str(row.get("suggested_next_target") or "")) <= 3
        )
    ]
    repeated_debts = [row for row in active_blocking_debts if int(row.get("repeated_count") or 0) >= 2]
    obstruction_artifacts = _recent_creative_obstruction_artifacts(state)
    bottleneck_signal_count = len(repeated_debts) + len(obstruction_artifacts)
    if bottleneck_signal_count < CREATIVE_ATTACK_MIN_BOTTLENECK_SIGNALS:
        return None

    active_routes = [
        row for row in route_scoreboard(state, limit=8)
        if str(row.get("scoreboard_status") or "") in {"active", "blocked", "stalled"}
    ]
    target_id = _creative_attack_target_id(state, active_blocking_debts, partial_claims) or "root"
    route_id = _active_route_for_claim(state, target_id)
    return {
        "policy": "wild-but-disciplined-mathematician",
        "target_id": target_id,
        "route_id": route_id,
        "partial_credit_claim_ids": sorted(partial_credit_ids)[:12],
        "active_blocking_debt_ids": [str(row.get("debt_id") or "") for row in active_blocking_debts[:12]],
        "repeated_blocking_debt_ids": [str(row.get("debt_id") or "") for row in repeated_debts[:12]],
        "obstruction_artifact_ids": [str(row.get("artifact_id") or "") for row in obstruction_artifacts[:8]],
        "route_scoreboard": [
            {
                "route_id": str(row.get("route_id") or ""),
                "status": str(row.get("scoreboard_status") or ""),
                "score": row.get("score"),
                "root_distance": row.get("root_distance"),
                "root_impact": row.get("root_impact"),
                "kill_reasons": row.get("kill_reasons", []),
            }
            for row in active_routes[:8]
        ],
        "required_math_moves": [
            "draft one full proof attempt with explicit gaps",
            "invert the central obstruction: ask what construction or theorem would evade it",
            "generate speculative bridge theorems with exact hypotheses and failure modes",
            "own one bottleneck for the whole pass instead of scattering into many local debts",
            "compare one analogy from a nearby mathematical method and translate only if it yields a concrete lemma",
            "autopsy the strongest failed route and state the single reason it failed",
        ],
        "paperwork_throttle": {
            "max_new_claims_without_route": 2,
            "preferred_artifact_types": ["proof_dossier", "proof_blueprint", "route_obstruction", "construction_failure"],
            "forbidden_default": "management-only research_notebook or broad diagnostic with no proof move",
        },
    }


def _recent_creative_obstruction_artifacts(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    wanted_types = {
        "route_obstruction",
        "hypothesis_gap",
        "construction_failure",
        "necessary_condition",
        "candidate_counterexample",
        "key_failure_analysis",
        "failed_decomposition_plan",
        "research_diagnostic",
    }
    rows: list[Mapping[str, Any]] = []
    for artifact in state.get("research_artifacts", []):
        artifact_type = str(artifact.get("artifact_type") or "")
        if artifact_type not in wanted_types:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        target_id = _target_id_from_metadata(state, metadata, fallback="root")
        if target_id != "root" and _root_impact_for_target(state, target_id) < 0.5:
            continue
        rows.append(artifact)
    rows.sort(key=lambda row: (_revision_number(row.get("state_revision")), str(row.get("created_at") or "")), reverse=True)
    return rows[:8]


def _creative_attack_target_id(
    state: Mapping[str, Any],
    debts: list[Mapping[str, Any]],
    partial_claims: list[Mapping[str, Any]],
) -> str:
    for debt in sorted(
        debts,
        key=lambda row: (-int(row.get("repeated_count") or 0), root_distance_for_claim_id(state, _claim_target_for_debt(state, row) or "root")),
    ):
        target_id = _claim_target_for_debt(state, debt)
        if target_id and _claim(state, target_id):
            return target_id
    if partial_claims:
        ranked = sorted(
            partial_claims,
            key=lambda row: (root_distance_for_claim_id(state, str(row.get("claim_id") or "")), -float(row.get("root_impact", 0.0) or 0.0)),
        )
        return str(ranked[0].get("claim_id") or "")
    return "root"


def _global_synthesis_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if _recent_intent_seen(state, GLOBAL_SYNTHESIS_INTENT, window=GLOBAL_SYNTHESIS_WINDOW):
        return None
    signal = _global_synthesis_signal(state)
    if not signal:
        return None
    target_id = str(signal.get("target_id") or "root")
    route_id = str(signal.get("route_id") or _active_route_for_claim(state, target_id) or "")
    mode = "reduce" if route_id else "prove"
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "deep_research_required": True,
        "research_attack_stage": "deep",
        "search_intent": GLOBAL_SYNTHESIS_INTENT,
    }
    return _action(
        mode,
        target_id,
        route_id,
        "endpoint obstructions plus no-result searches call for theorem-building global synthesis, not another broad search",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        research_synthesis_required=True,
        global_synthesis_required=True,
        theorem_building_synthesis_required=True,
        global_synthesis_signal=signal,
        needs_proof_dossier=True,
        direct_solve_required=(mode == "prove"),
        proof_construction_required=bool(route_id),
        citation_allowed_in_proof=True,
        research_attack_stage="deep",
        deep_research_required=True,
        search_intent=GLOBAL_SYNTHESIS_INTENT,
    )


def _global_synthesis_signal(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    no_result = _no_result_search_cluster(state)
    partial_closure = _partial_root_closure_signal(state)
    if not no_result and not partial_closure:
        return None
    target_id = str((no_result or partial_closure or {}).get("target_id") or "root")
    artifact_hits = _global_synthesis_artifact_hits(state, target_id=target_id)
    if no_result and (
        not artifact_hits.get("bridge_artifact_ids")
        or not artifact_hits.get("endpoint_artifact_ids")
    ):
        return None
    bridge_ids = artifact_hits["bridge_artifact_ids"]
    endpoint_ids = artifact_hits["endpoint_artifact_ids"]
    if partial_closure:
        bridge_ids = sorted(set(bridge_ids + partial_closure.get("bridge_debt_ids", [])))[:6]
        endpoint_ids = sorted(set(endpoint_ids + partial_closure.get("partial_claim_ids", [])))[:8]
    if not bridge_ids or not endpoint_ids:
        return None
    return {
        "policy": "theorem-building-global-synthesis",
        "target_id": target_id,
        "route_id": str((no_result or partial_closure or {}).get("route_id") or _active_route_for_claim(state, target_id) or ""),
        "no_result_card_ids": (no_result or {}).get("card_ids", []),
        "bridge_artifact_ids": bridge_ids,
        "endpoint_artifact_ids": endpoint_ids,
        "partial_closure_signal": partial_closure or {},
        "candidate_missing_theorem": artifact_hits.get("candidate_missing_theorem", "")
        or (partial_closure or {}).get("candidate_missing_theorem", ""),
        "instruction": (
            "Attempt to prove the missing bridge theorem from the current endpoint obstructions and source handoffs. "
            "Use citations as components when appropriate, but do not treat absence of an exact theorem as a reason to search again."
        ),
    }


def _partial_root_closure_signal(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    partial_claims: list[Mapping[str, Any]] = []
    for claim in state.get("claims", []):
        if str(claim.get("claim_id") or "") == "root":
            continue
        if str(claim.get("validation_status") or "") not in {"informally_verified", "formally_verified"}:
            continue
        if str(claim.get("lifecycle_status") or "") not in {"active", "integrated"}:
            continue
        text = " ".join(
            [
                str(claim.get("claim_id") or ""),
                str(claim.get("kind") or ""),
                str(claim.get("statement") or ""),
            ]
        ).lower()
        if not any(
            term in text
            for term in (
                "partial",
                "obstruction",
                "necessary",
                "bounded",
                "chief factor",
                "composition factor",
                "counterexample",
            )
        ):
            continue
        partial_claims.append(claim)
    if not partial_claims:
        return None

    bridge_debts: list[Mapping[str, Any]] = []
    for debt in state.get("debts", []):
        if str(debt.get("status") or "") != "active":
            continue
        if str(debt.get("severity") or "") not in {"blocking", "major"}:
            continue
        target_id = str(_claim_target_for_debt(state, debt) or "root")
        if target_id != "root":
            continue
        text = " ".join(
            [
                str(debt.get("debt_id") or ""),
                str(debt.get("debt_type") or ""),
                str(debt.get("obligation") or ""),
                str(debt.get("suggested_next_target") or ""),
            ]
        ).lower()
        if not any(
            term in text
            for term in (
                "bridge",
                "root",
                "section",
                "composition factor",
                "chief factor",
                "bounded",
                "compatibility",
                "close",
                "counterexample",
            )
        ):
            continue
        bridge_debts.append(debt)
    if not bridge_debts:
        return None

    partial_claims = sorted(partial_claims, key=lambda c: (-float(c.get("root_impact", 0.0) or 0.0), str(c.get("claim_id") or "")))
    bridge_debts = sorted(bridge_debts, key=lambda d: str(d.get("debt_id") or ""))
    return {
        "policy": "verified-partial-root-closure",
        "target_id": "root",
        "route_id": "",
        "partial_claim_ids": [str(c.get("claim_id") or "") for c in partial_claims[:6]],
        "bridge_debt_ids": [str(d.get("debt_id") or "") for d in bridge_debts[:6]],
        "candidate_missing_theorem": str(bridge_debts[0].get("obligation") or "")[:500],
    }


def _global_synthesis_artifact_hits(state: Mapping[str, Any], *, target_id: str) -> Dict[str, Any]:
    bridge_terms = (
        "bounded-section",
        "bounded section",
        "section-forcing",
        "section forcing",
        "chief-factor bridge",
        "chief factor bridge",
        "crown",
        "composition factor",
        "global bridge",
        "missing theorem",
        "compatibility theorem",
    )
    endpoint_terms = (
        "endpoint obstruction",
        "alternating obstruction",
        "classical obstruction",
        "projective",
        "linear obstruction",
        "common maximal",
        "common stabilizer",
        "parabolic",
        "counterexample route",
    )
    useful_types = {
        "proof_dossier",
        "proof_blueprint",
        "source_adaptation_notes",
        "source_synthesis_report",
        "research_diagnostic",
        "cas_experiment_report",
    }
    bridge_ids: list[str] = []
    endpoint_ids: list[str] = []
    missing_theorem = ""
    for artifact in state.get("research_artifacts", []):
        if str(artifact.get("artifact_type") or "") not in useful_types:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        artifact_target = _target_id_from_metadata(state, metadata, fallback=target_id)
        if artifact_target != target_id:
            continue
        text = " ".join(
            [
                str(artifact.get("artifact_id") or ""),
                str(artifact.get("artifact_type") or ""),
                str(artifact.get("content_summary") or ""),
                json.dumps(metadata, sort_keys=True),
            ]
        ).lower()
        artifact_id = str(artifact.get("artifact_id") or "")
        if any(term in text for term in bridge_terms):
            bridge_ids.append(artifact_id)
            if not missing_theorem:
                missing_theorem = _extract_missing_theorem(metadata, text)
        if any(term in text for term in endpoint_terms):
            endpoint_ids.append(artifact_id)
    return {
        "bridge_artifact_ids": sorted(set(bridge_ids))[:6],
        "endpoint_artifact_ids": sorted(set(endpoint_ids))[:8],
        "candidate_missing_theorem": missing_theorem[:500],
    }


def _extract_missing_theorem(metadata: Mapping[str, Any], fallback_text: str) -> str:
    for key in ("missing_theorem", "proof_obligation", "candidate_missing_theorem", "remaining_gap"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    marker = "missing theorem"
    index = fallback_text.find(marker)
    if index < 0:
        return ""
    return fallback_text[index : index + 300]


def _route_decision_triage_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    last_triage = _last_intent_run(state, "route_triage")
    triage_revision = int(last_triage.get("state_revision", -1) or -1) if last_triage else -1
    for artifact in state.get("research_artifacts", []):
        if str(artifact.get("artifact_type") or "") not in {"proof_dossier", "research_diagnostic"}:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        route_decision = str(metadata.get("route_decision") or metadata.get("chosen_next_action") or "").lower()
        classification = str(
            metadata.get("classification")
            or metadata.get("obstruction_classification")
            or metadata.get("status")
            or ""
        ).lower()
        if "route_killing_obstruction" not in classification:
            continue
        if not any(term in route_decision for term in ("abandon", "pause", "replace")):
            continue
        artifact_revision = int(artifact.get("state_revision", -1) or -1)
        if triage_revision >= artifact_revision >= 0:
            continue
        route_id = str(metadata.get("route_id") or "")
        if not route_id or not _route(state, route_id):
            continue
        return _action(
            "triage_routes",
            "root",
            route_id,
            "route-killing obstruction dossier needs advisor decision before more proof search",
            plan_step_budget(problem, "triage_routes", requested_tokens),
            research_mode=research_mode,
            route_triage_required=True,
            route_triage_reason="route-killing obstruction dossier requested route pause, replacement, or abandonment",
            route_decision_artifact_id=str(artifact.get("artifact_id") or ""),
            route_decision=str(metadata.get("route_decision") or ""),
            route_decision_classification=str(metadata.get("classification") or metadata.get("obstruction_classification") or ""),
            search_intent="route_triage",
        )
    return None


def _route_pause_replacement_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if _recent_intent_seen(state, "direct_solve_after_route_pause", window=6):
        return None
    root = _claim(state, "root")
    if root and str(root.get("lifecycle_status") or "") == "integrated":
        return None
    paused = paused_route_ids(state)
    root_routes = [
        row for row in state.get("routes", [])
        if row.get("conclusion_claim_id") == "root" and row.get("status") == "active"
    ]
    if not root_routes or any(str(row.get("route_id") or "") not in paused for row in root_routes):
        return None
    report = _latest_route_pause_report(state)
    if not report:
        return None
    budget_action = {
        "target_id": "root",
        "direct_solve_required": True,
        "deep_research_required": True,
        "research_attack_stage": "deep",
        "search_intent": "direct_solve_after_route_pause",
    }
    return _action(
        "prove",
        "root",
        "",
        "advisor paused all active root routes; researcher should seek a replacement construction for the root theorem",
        plan_action_budget(problem, "prove", budget_action, requested_tokens),
        research_mode=research_mode,
        direct_solve_required=True,
        route_replacement_required=True,
        paused_route_ids=sorted(paused.intersection({str(row.get("route_id") or "") for row in root_routes})),
        route_triage_report_id=str(report.get("artifact_id") or ""),
        needs_proof_dossier=True,
        research_attack_stage="deep",
        deep_research_required=True,
        search_intent="direct_solve_after_route_pause",
    )


def _latest_route_pause_report(state: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    for artifact in state.get("research_artifacts", []):
        if str(artifact.get("artifact_type") or "") not in {"route_triage_report", "advisor_report"}:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        if metadata.get("paused_or_abandoned_route_ids"):
            return artifact
    return None


def _obstruction_route_conversion_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    cluster = _obstruction_route_conversion_cluster(state)
    if not cluster:
        return None
    target_id = str(cluster.get("target_id") or "root")
    route_id = str(cluster.get("route_id") or _active_route_for_claim(state, target_id) or "")
    mode = "reduce" if route_id else "prove"
    recent_timeout = _recent_researcher_timeout_for_intent(
        state,
        intent=OBSTRUCTION_ROUTE_CONVERSION_INTENT,
        target_id=target_id,
        route_id=route_id,
    )
    global_obstruction_architecture = target_id == "root" and (
        len(cluster.get("claim_ids", []) or [])
        + len(cluster.get("artifact_ids", []) or [])
        + len(cluster.get("debt_ids", []) or [])
    ) >= 1
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "research_attack_stage": "synthesis",
        "search_intent": OBSTRUCTION_ROUTE_CONVERSION_INTENT,
    }
    if recent_timeout:
        return _action(
            "triage_routes",
            target_id,
            route_id,
            "researcher obstruction conversion hit a stream-stall timeout; PhD advisor should make the compact route decision before replaying research",
            plan_action_budget(problem, "triage_routes", budget_action, requested_tokens),
            research_mode=research_mode,
            route_triage_required=True,
            obstruction_route_conversion_required=True,
            advisor_obstruction_conversion_required=True,
            obstruction_cluster=cluster,
            obstruction_claim_ids=cluster.get("claim_ids", []),
            obstruction_artifact_ids=cluster.get("artifact_ids", []),
            obstruction_debt_ids=cluster.get("debt_ids", []),
            recent_researcher_timeout_run_id=str(recent_timeout.get("run_id") or ""),
            advisor_evidence_synthesis_required=True,
            global_obstruction_architecture_required=global_obstruction_architecture,
            research_attack_stage="triage_after_researcher_timeout",
            search_intent=OBSTRUCTION_ROUTE_CONVERSION_INTENT,
        )
    return _action(
        mode,
        target_id,
        route_id,
        "convert a serious obstruction into a route decision before continuing proof search",
        plan_action_budget(problem, mode, budget_action, requested_tokens),
        research_mode=research_mode,
        research_synthesis_required=True,
        obstruction_route_conversion_required=True,
        obstruction_cluster=cluster,
        obstruction_claim_ids=cluster.get("claim_ids", []),
        obstruction_artifact_ids=cluster.get("artifact_ids", []),
        obstruction_debt_ids=cluster.get("debt_ids", []),
        proof_repair_required=bool(route_id),
        direct_solve_required=not bool(route_id),
        global_obstruction_architecture_required=global_obstruction_architecture,
        needs_proof_dossier=True,
        research_attack_stage="synthesis",
        search_intent=OBSTRUCTION_ROUTE_CONVERSION_INTENT,
    )


def _obstruction_conversion_matches_blocking_debt(
    state: Mapping[str, Any],
    action: Mapping[str, Any],
    blocking_debt: Mapping[str, Any],
) -> bool:
    debt_target_id = str(_claim_target_for_debt(state, blocking_debt) or "")
    debt_route_id = _route_for_debt(state, blocking_debt, debt_target_id)
    action_target_id = str(action.get("target_id") or "")
    action_route_id = str(action.get("route_id") or "")
    if debt_route_id and action_route_id == debt_route_id:
        return True
    if debt_target_id and action_target_id == debt_target_id:
        return True
    debt_id = str(blocking_debt.get("debt_id") or "")
    if debt_id and debt_id in {str(item) for item in action.get("obstruction_debt_ids", [])}:
        return True
    source_ids = {str(item) for item in _json_list(blocking_debt.get("source_artifact_ids_json")) if str(item)}
    evidence_ids = {str(item) for item in action.get("obstruction_artifact_ids", []) if str(item)}
    evidence_ids.update(str(item) for item in action.get("obstruction_cluster", {}).get("evidence_artifact_ids", []) if str(item))
    return bool(source_ids and source_ids.intersection(evidence_ids))


def _recent_researcher_timeout_for_intent(
    state: Mapping[str, Any],
    *,
    intent: str,
    target_id: str,
    route_id: str,
    window: int = RESEARCHER_TIMEOUT_REDIRECT_WINDOW,
) -> Optional[Mapping[str, Any]]:
    for row in list(state.get("recent_runs", []))[:window]:
        if str(row.get("actor_role") or "") != "researcher":
            continue
        if str(row.get("search_intent") or "") != intent:
            continue
        if str(row.get("status") or "") != "timeout":
            continue
        if str(row.get("target_id") or "root") != target_id:
            continue
        if str(row.get("route_id") or "") != route_id:
            continue
        return row
    return None


def _stream_stall_recovery_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    stall = _recent_researcher_stream_stall(state)
    if not stall:
        return None
    target_id = str(stall.get("target_id") or "root")
    route_id = str(stall.get("route_id") or _active_route_for_claim(state, target_id) or "")
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "stream_stall_recovery_required": True,
        "search_intent": STREAM_RETRY_RECOVERY_INTENT,
    }
    return _action(
        "triage_routes",
        target_id,
        route_id,
        "researcher session hit a Codex stream-retry stall before producing a patch; PhD advisor should compactly synthesize current evidence and choose the next narrower proof move before replaying a large researcher prompt",
        plan_action_budget(problem, "triage_routes", budget_action, requested_tokens),
        research_mode=research_mode,
        route_triage_required=True,
        advisor_evidence_synthesis_required=True,
        stream_stall_recovery_required=True,
        recent_researcher_timeout_run_id=str(stall.get("run_id") or ""),
        recent_researcher_timeout_intent=str(stall.get("search_intent") or ""),
        search_intent=STREAM_RETRY_RECOVERY_INTENT,
    )


def _recent_researcher_stream_stall(
    state: Mapping[str, Any],
    *,
    window: int = RESEARCHER_TIMEOUT_REDIRECT_WINDOW,
) -> Optional[Mapping[str, Any]]:
    recent = list(state.get("recent_runs", []))[:window]
    recovery_intents = {
        STREAM_RETRY_RECOVERY_INTENT,
        ADVISOR_EVIDENCE_SYNTHESIS_INTENT,
        VERIFIER_LOOP_CLASSIFICATION_INTENT,
        OBSTRUCTION_ROUTE_CONVERSION_INTENT,
        CIRCLING_INTENT,
    }
    for index, row in enumerate(recent):
        if str(row.get("actor_role") or "") != "researcher":
            continue
        if str(row.get("status") or "") != "timeout":
            continue
        error_summary = str(row.get("error_summary") or "")
        if STREAM_RETRY_STALL_FRAGMENT not in error_summary:
            continue
        if any(
            str(later.get("actor_role") or "") == "phd_advisor"
            and str(later.get("search_intent") or "") in recovery_intents
            for later in recent[:index]
        ):
            return None
        if _accepted_progress_since(state, str(row.get("created_at") or "")):
            return None
        return row
    return None


def _obstruction_route_conversion_cluster(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    signals = _unconverted_obstruction_signals(state)
    if not signals:
        return None
    grouped: dict[tuple[str, str], list[Dict[str, Any]]] = {}
    for signal in signals:
        target_id = str(signal.get("target_id") or "root")
        route_id = str(signal.get("route_id") or _active_route_for_claim(state, target_id) or "")
        grouped.setdefault((target_id, route_id), []).append(signal)

    candidates: list[tuple[float, int, int, bool, str, str, str, list[Dict[str, Any]]]] = []
    for (target_id, route_id), group in grouped.items():
        root_impact = max(float(item.get("root_impact", 0.0) or 0.0) for item in group)
        newest_revision = max(int(item.get("state_revision", -1) or -1) for item in group)
        tie_key = ",".join(
            sorted(
                str(item.get("claim_id") or item.get("artifact_id") or item.get("debt_id") or "")
                for item in group
            )
        )
        candidates.append((root_impact, newest_revision, len(group), target_id != "root", target_id, route_id, tie_key, group))
    candidates.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4], item[5], item[6]))
    root_impact, newest_revision, _count, _nonroot, target_id, route_id, _tie_key, group = candidates[0]
    return {
        "policy": "obstruction-to-route-conversion",
        "target_id": target_id,
        "route_id": route_id,
        "count": len(group),
        "max_root_impact": root_impact,
        "newest_state_revision": newest_revision,
        "signal_types": sorted({str(item.get("signal_type") or "") for item in group if item.get("signal_type")}),
        "claim_ids": sorted({str(item.get("claim_id") or "") for item in group if item.get("claim_id")}),
        "artifact_ids": sorted({str(item.get("artifact_id") or "") for item in group if item.get("artifact_id")}),
        "debt_ids": sorted({str(item.get("debt_id") or "") for item in group if item.get("debt_id")}),
        "evidence_artifact_ids": sorted(
            {
                str(evidence_id)
                for item in group
                for evidence_id in item.get("evidence_artifact_ids", [])
                if str(evidence_id)
            }
        ),
        "conversion_choices": [
            "route_killing_obstruction",
            "route_repair_signal",
            "missing_hypothesis",
            "generalized_construction_needed",
            "candidate_counterexample_needs_validation",
        ],
    }


def _unconverted_obstruction_signals(state: Mapping[str, Any]) -> list[Dict[str, Any]]:
    last_conversion = _last_intent_run(state, OBSTRUCTION_ROUTE_CONVERSION_INTENT)
    artifact_by_id = {
        str(row.get("artifact_id") or ""): row
        for row in state.get("research_artifacts", [])
        if str(row.get("artifact_id") or "")
    }
    signals: list[Dict[str, Any]] = []

    for claim in state.get("claims", []):
        if str(claim.get("kind") or "") not in {"obstruction", "counterexample"}:
            continue
        if str(claim.get("lifecycle_status") or "") != "active":
            continue
        if str(claim.get("validation_status") or "") in {"informally_verified", "formally_verified", "refuted"}:
            continue
        signal = _obstruction_claim_signal(state, claim, artifact_by_id)
        if signal and not _obstruction_signal_already_converted(signal, last_conversion):
            signals.append(signal)

    for artifact in state.get("research_artifacts", []):
        if str(artifact.get("artifact_type") or "") not in OBSTRUCTION_SIGNAL_ARTIFACT_TYPES:
            continue
        if not _artifact_is_obstruction_signal(artifact):
            continue
        signal = _obstruction_artifact_signal(state, artifact)
        if signal and not _obstruction_signal_already_converted(signal, last_conversion):
            signals.append(signal)

    for debt_row in state.get("debts", []):
        signal = _obstruction_debt_signal(state, debt_row, artifact_by_id)
        if signal and not _obstruction_signal_already_converted(signal, last_conversion):
            signals.append(signal)

    return signals


def _obstruction_claim_signal(
    state: Mapping[str, Any],
    claim: Mapping[str, Any],
    artifact_by_id: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    evidence_ids = [str(item) for item in _json_list(claim.get("evidence_artifact_ids_json")) if str(item)]
    parent_ids = [str(item) for item in _json_list(claim.get("parent_ids_json")) if _claim(state, str(item))]
    target_id = parent_ids[0] if parent_ids else "root"
    route_id = ""
    for evidence_id in evidence_ids:
        metadata = _json_object((artifact_by_id.get(evidence_id) or {}).get("metadata_json"))
        route_id = str(metadata.get("route_id") or "")
        if route_id and _route(state, route_id):
            break
    if not route_id:
        route_id = _active_route_for_claim(state, target_id)
    return {
        "signal_type": str(claim.get("kind") or "obstruction"),
        "claim_id": str(claim.get("claim_id") or ""),
        "target_id": target_id,
        "route_id": route_id,
        "root_impact": float(claim.get("root_impact", 0.0) or 0.0),
        "state_revision": max(
            [int((artifact_by_id.get(evidence_id) or {}).get("state_revision", -1) or -1) for evidence_id in evidence_ids] or [-1]
        ),
        "created_at": str(claim.get("created_at") or ""),
        "evidence_artifact_ids": evidence_ids,
    }


def _obstruction_artifact_signal(state: Mapping[str, Any], artifact: Mapping[str, Any]) -> Dict[str, Any]:
    metadata = _json_object(artifact.get("metadata_json"))
    target_id = _target_id_from_metadata(state, metadata, fallback="root")
    route_id = str(metadata.get("route_id") or "")
    if route_id and not _route(state, route_id):
        route_id = ""
    if not route_id:
        route_id = _active_route_for_claim(state, target_id)
    return {
        "signal_type": str(artifact.get("artifact_type") or "obstruction_artifact"),
        "artifact_id": str(artifact.get("artifact_id") or ""),
        "target_id": target_id,
        "route_id": route_id,
        "root_impact": _root_impact_for_target(state, target_id),
        "state_revision": int(artifact.get("state_revision", -1) or -1),
        "created_at": str(artifact.get("created_at") or ""),
        "evidence_artifact_ids": [str(artifact.get("artifact_id") or "")],
    }


def _obstruction_debt_signal(
    state: Mapping[str, Any],
    debt_row: Mapping[str, Any],
    artifact_by_id: Mapping[str, Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    if str(debt_row.get("status") or "") != "active":
        return None
    debt_type = str(debt_row.get("debt_type") or "")
    obligation = str(debt_row.get("obligation") or "").lower()
    if debt_type != "counterexample_risk" and not any(term in obligation for term in ("counterexample", "obstruction", "hypothesis mismatch")):
        return None
    evidence_ids = [str(item) for item in _json_list(debt_row.get("source_artifact_ids_json")) if str(item)]
    if debt_type != "counterexample_risk" and not any(_artifact_is_obstruction_signal(artifact_by_id.get(eid) or {}) for eid in evidence_ids):
        return None
    target_id = str(_claim_target_for_debt(state, debt_row) or "root")
    route_id = _route_for_debt(state, debt_row, target_id)
    return {
        "signal_type": "obstruction_debt",
        "debt_id": str(debt_row.get("debt_id") or ""),
        "target_id": target_id,
        "route_id": route_id,
        "root_impact": _root_impact_for_target(state, target_id),
        "state_revision": max(
            [int((artifact_by_id.get(evidence_id) or {}).get("state_revision", -1) or -1) for evidence_id in evidence_ids] or [-1]
        ),
        "created_at": str(debt_row.get("last_seen") or ""),
        "evidence_artifact_ids": evidence_ids,
    }


def _artifact_is_obstruction_signal(artifact: Mapping[str, Any]) -> bool:
    artifact_type = str(artifact.get("artifact_type") or "")
    if artifact_type == "candidate_counterexample":
        return True
    if artifact_type in ROUTE_OBSTRUCTION_ARTIFACT_TYPES:
        return True
    metadata = _json_object(artifact.get("metadata_json"))
    status = str(metadata.get("status") or metadata.get("classification") or metadata.get("conclusion") or "").lower()
    text = " ".join(
        [
            artifact_type,
            str(artifact.get("producer_role") or ""),
            str(artifact.get("content_summary") or ""),
            json.dumps(metadata, sort_keys=True),
        ]
    ).lower()
    negative_phrases = (
        "no obstruction",
        "no counterexample",
        "no hypothesis mismatch",
        "did not break",
        "does not break",
        "failed to find",
        "no serious obstruction",
    )
    if any(phrase in status for phrase in negative_phrases) or any(phrase in text for phrase in negative_phrases):
        return False
    positive_terms = (
        "obstruction",
        "counterexample",
        "hypothesis mismatch",
        "missing hypothesis",
        "false as stated",
        "breaks the claim",
        "candidate_refutation",
    )
    return any(term in status for term in positive_terms) or any(term in text for term in positive_terms)


SOFT_COUNTEREXAMPLE_OBSTRUCTION_TYPES = {
    "missing_hypothesis",
    "hypothesis_gap",
    "route_repair_signal",
    "route_killing_obstruction",
    "generalized_construction_needed",
    "necessary_condition",
    "construction_failure",
    "hypothesis_mismatch",
}


def _candidate_counterexample_requires_validation(artifact: Mapping[str, Any]) -> bool:
    """True for concrete falsifying candidates, false for route-level stress signals."""
    if str(artifact.get("artifact_type") or "") != "candidate_counterexample":
        return False
    metadata = _json_object(artifact.get("metadata_json"))
    if metadata.get("validation_required") is False:
        return False
    obstruction_type = str(
        metadata.get("obstruction_type")
        or metadata.get("classification")
        or metadata.get("relation")
        or ""
    ).lower()
    if obstruction_type in SOFT_COUNTEREXAMPLE_OBSTRUCTION_TYPES:
        return False
    text = " ".join(
        [
            obstruction_type,
            str(metadata.get("status") or ""),
            str(metadata.get("failed_hypothesis") or ""),
            str(metadata.get("example_family") or ""),
            str(artifact.get("content_summary") or ""),
        ]
    ).lower()
    if any(term in text for term in ("missing hypothesis", "hypothesis gap", "route repair", "necessary condition")):
        return False
    return True


def _target_id_from_metadata(state: Mapping[str, Any], metadata: Mapping[str, Any], *, fallback: str) -> str:
    route_id = str(metadata.get("next_route_id") or metadata.get("recommended_route_id") or metadata.get("route_id") or "")
    route = _route(state, route_id) if route_id else None
    if route:
        return str(route.get("conclusion_claim_id") or fallback)
    for key in (
        "next_target_id",
        "next_claim_id",
        "recommended_target_id",
        "target_id",
        "claim_id",
        "parent_claim_id",
        "conclusion_claim_id",
    ):
        candidate = str(metadata.get(key) or "")
        if candidate and _claim(state, candidate):
            return candidate
    return fallback


def _root_impact_for_target(state: Mapping[str, Any], target_id: str) -> float:
    claim = _claim(state, target_id)
    if not claim:
        return 0.0
    return float(claim.get("root_impact", 0.0) or 0.0)


def _last_intent_run(state: Mapping[str, Any], intent: str) -> Optional[Mapping[str, Any]]:
    return next((row for row in state.get("recent_runs", []) if row.get("search_intent") == intent), None)


def _last_mode_run(state: Mapping[str, Any], mode: str) -> Optional[Mapping[str, Any]]:
    return next((row for row in state.get("recent_runs", []) if row.get("mode") == mode), None)


def _obstruction_signal_already_converted(signal: Mapping[str, Any], last_conversion: Mapping[str, Any] | None) -> bool:
    if not last_conversion:
        return False
    signal_revision = int(signal.get("state_revision", -1) or -1)
    conversion_revision = int(last_conversion.get("state_revision", -1) or -1)
    if signal_revision >= 0 and conversion_revision >= signal_revision:
        return True
    signal_time = str(signal.get("created_at") or "")
    conversion_time = str(last_conversion.get("created_at") or "")
    return bool(signal_time and conversion_time and conversion_time >= signal_time)


def _route_proof_construction_action(
    state: Mapping[str, Any],
    route: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
    reason: str,
    proof_repair_required: bool = False,
    no_content_guard: bool = False,
    parallel_companion: bool = False,
    extra: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    target_id = str(route.get("conclusion_claim_id") or "root")
    route_id = str(route.get("route_id") or "")
    deep = (not parallel_companion) and _should_deep_research(state, target_id)
    search_intent = PARALLEL_ROUTE_PROOF_CONSTRUCTION_INTENT if parallel_companion else ROUTE_PROOF_CONSTRUCTION_INTENT
    budget_action = {
        "target_id": target_id,
        "route_id": route_id,
        "proof_construction_required": True,
        "deep_research_required": deep,
        "research_attack_stage": "fast" if parallel_companion else ("deep" if deep else "ordinary"),
        "search_intent": search_intent,
    }
    action = _action(
        "reduce",
        target_id,
        route_id,
        reason,
        plan_action_budget(problem, "reduce", budget_action, requested_tokens),
        research_mode=research_mode,
        needs_inference=True,
        needs_proof_dossier=True,
        proof_construction_required=True,
        proof_repair_required=proof_repair_required,
        citation_allowed_in_proof=True,
        reduce_scope="construct_or_repair_selected_route_proof",
        research_attack_stage=budget_action["research_attack_stage"],
        deep_research_required=deep,
        no_content_research_guard=no_content_guard,
        proof_attempt_quota="route proof construction before further reduction/decomposition",
        search_intent=search_intent,
        parallel_companion=parallel_companion,
    )
    if extra:
        action.update(dict(extra))
    return action


def _should_deep_research(state: Mapping[str, Any], target_id: str) -> bool:
    if target_id == "root":
        return True
    claim = _claim(state, target_id)
    if not claim:
        return False
    return root_distance_for_claim_id(state, target_id) <= 2 or float(claim.get("root_impact", 0.0) or 0.0) >= 0.75


def _route_proof_construction_quota_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    route = _route_without_inference(state)
    if not route:
        return None
    target_id = str(route.get("conclusion_claim_id") or "root")
    route_id = str(route.get("route_id") or "")
    if _recent_route_proof_attempt_seen(state, target_id=target_id, route_id=route_id, window=5):
        return None
    return _route_proof_construction_action(
        state,
        route,
        problem=problem,
        requested_tokens=requested_tokens,
        research_mode=research_mode,
        reason="proof-attempt quota: construct the active route proof before further reduction or decomposition",
    )


def _recent_route_proof_attempt_seen(state: Mapping[str, Any], *, target_id: str, route_id: str, window: int) -> bool:
    proof_intents = {
        ROUTE_PROOF_CONSTRUCTION_INTENT,
        PARALLEL_ROUTE_PROOF_CONSTRUCTION_INTENT,
        "parallel_independent_solve",
        "parallel_direct_solve",
        "direct_solve",
        "direct_solve_cooldown",
        "direct_solve_debt_repair",
    }
    for run in list(state.get("recent_runs", []))[:window]:
        if str(run.get("target_id") or "") != target_id:
            continue
        run_route_id = str(run.get("route_id") or "")
        if route_id and run_route_id and run_route_id != route_id:
            continue
        if str(run.get("search_intent") or "") in proof_intents:
            return True
    return False


def _accepted_progress_since(state: Mapping[str, Any], since_iso: str) -> bool:
    """True if a new (or newly verified) claim, inference, or route appeared after ``since_iso``.

    Used to decide whether recent same-target passes actually advanced the proof, or
    just churned. New non-root claims / inferences / routes count as structural progress
    (a decomposition or re-route landed); verifications count too.
    """
    if not since_iso:
        return False
    verified = {"informally_verified", "formally_verified"}
    for c in state.get("claims", []):
        cid = str(c.get("claim_id") or "")
        if cid and cid != "root" and str(c.get("created_at") or "") > since_iso:
            return True
        if str(c.get("updated_at") or "") > since_iso and (
            str(c.get("validation_status") or "") in verified
            or str(c.get("lifecycle_status") or "") == "integrated"
        ):
            return True
    for inf in state.get("inferences", []):
        if str(inf.get("created_at") or "") > since_iso:
            return True
        if str(inf.get("updated_at") or "") > since_iso and str(inf.get("validation_status") or "") in verified:
            return True
    for route in state.get("routes", []):
        if str(route.get("created_at") or "") > since_iso:
            return True
    return False


def _broad_circling_stall(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Detect K+ recent same-target research passes that produced no new accepted content.

    Unlike the retrieve/reduce circuit breaker, this spans every exploration mode
    (prove, audit, synthesize, refute, advisor passes, ...), so the common
    "keep hammering the same hard target" loop is caught. Built from persisted
    ``recent_runs`` + claim/inference/route timestamps, so it survives resumes.
    """
    recent = list(state.get("recent_runs", []))
    if len(recent) < CIRCLING_MIN_PASSES:
        return None
    streak: list = []
    target: Optional[str] = None
    for row in recent:
        if str(row.get("mode") or "") not in CIRCLING_RESEARCH_MODES:
            break
        tid = str(row.get("target_id") or "root")
        if target is None:
            target = tid
        elif tid != target:
            break
        streak.append(row)
    if len(streak) < CIRCLING_MIN_PASSES:
        return None
    since_iso = str(streak[-1].get("created_at") or "")
    if _accepted_progress_since(state, since_iso):
        return None
    return {
        "target_id": target or "root",
        "count": len(streak),
        "modes": [str(r.get("mode") or "") for r in streak],
        "route_id": next((str(r.get("route_id") or "") for r in streak if r.get("route_id")), ""),
        "since_iso": since_iso,
        "advisor_passes": sum(1 for r in streak if str(r.get("mode") or "") in CIRCLING_ADVISOR_MODES),
    }


def _circling_redirect_action(
    store: ProofStateStore,
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    """Anti-circling breaker.

    When the researcher has repeated the same pass on a target with no new verified
    result, (1) raise an async human blocker (the dashboard surfaces it; the human can
    steer without halting the run) and (2) force the advisor to *redirect* — decompose a
    tractable subgoal or abandon the route for a different construction — instead of the
    no-content guard's default of re-issuing another prove. If the advisor has already
    been handed the wheel ``CIRCLING_ADVISOR_MAX`` times without breaking the loop, stop
    forcing it (avoid ping-pong); the blocker stays open for the human and downstream
    guards proceed.
    """
    stall = _broad_circling_stall(state)
    if not stall:
        return None
    target_id = stall["target_id"]
    route_id = stall["route_id"] or _active_route_for_claim(state, target_id) or ""

    try:
        steering.raise_blocker(
            store.state_dir,
            kind="stall",
            target_id=target_id,
            summary=(
                f"{stall['count']} consecutive research passes on '{target_id}' with no new "
                "verified result — the researcher appears stuck."
            ),
            detail=(
                "Modes tried: " + ", ".join(dict.fromkeys(stall["modes"])) + ". "
                "Pick a direction: decompose into a tractable subgoal, abandon this route for a "
                "different construction, or type specific guidance."
            ),
            options=[
                "decompose into a tractable subgoal",
                "abandon route & try another construction",
                "(type your own guidance)",
            ],
            fingerprint=f"stall:{target_id}",
            revision=int(problem.get("current_revision") or 0),
        )
    except Exception:
        pass

    if stall["advisor_passes"] >= CIRCLING_ADVISOR_MAX:
        return None

    return _action(
        "triage_routes",
        target_id,
        route_id,
        "circling breaker: researcher repeated the same pass with no new verified result; "
        "advisor must redirect — decompose a tractable subgoal or abandon this route for another "
        "construction (incorporate any human steering directives in context).",
        plan_step_budget(problem, "triage_routes", requested_tokens),
        research_mode=research_mode,
        strategy_advisor_required=True,
        decompose_or_reroute=True,
        circling_stall=stall,
        search_intent=CIRCLING_INTENT,
    )


def _counterexample_validation_action(
    store: ProofStateStore,
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    """Force independent validation of a villain's candidate counterexample.

    The villain records a candidate_counterexample (marking the claim 'challenged'),
    but the counterexample_validator that would confirm it (claim -> 'refuted') was
    never scheduled — so root-threatening counterexamples sat uncertified while the
    system kept trying to prove the root. This schedules that validation promptly,
    root-threats first; a confirmation flips the claim to refuted, which the
    refuted-root guard then turns into a goal revision.
    """
    recent = list(state.get("recent_runs", []))[:8]
    recently_validated = {
        str(r.get("target_id") or "")
        for r in recent
        if str(r.get("mode") or "") == "validate_counterexample"
    }
    pending: list = []
    for art in state.get("research_artifacts", []):
        if not _candidate_counterexample_requires_validation(art):
            continue
        target = str(_json_object(art.get("metadata_json")).get("target_id") or "")
        claim = _claim(state, target) if target else None
        if not claim:
            continue
        if str(claim.get("validation_status") or "") in {"refuted", "informally_verified", "formally_verified"}:
            continue
        if target in recently_validated:
            continue
        pending.append((target, art))
    if not pending:
        return None
    pending.sort(key=lambda item: 0 if item[0] == "root" else 1)  # root-threats first
    target, art = pending[0]
    is_root = target == "root"
    return _action(
        "validate_counterexample",
        target,
        "",
        f"the villain flagged a candidate counterexample against '{target}'; validate it independently — "
        "construct/confirm a concrete instance and propose refuted, or reject it with reasons."
        + (" It targets the ROOT: if confirmed, the root must be revised, so resolve it before more proving." if is_root else ""),
        plan_step_budget(problem, "validate_counterexample", requested_tokens),
        research_mode=research_mode,
        counterexample_validation_required=True,
        candidate_counterexample_artifact_id=str(art.get("artifact_id") or ""),
        allow_root_refutation=is_root,
        search_intent="counterexample_validation",
    )


def _refuted_root_revision_action(
    store: ProofStateStore,
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    """When the root is refuted by a confirmed counterexample, stop proving it: raise a
    human blocker and propose a scope-restricted restatement instead of stalling."""
    root = _claim(state, "root")
    if not root or str(root.get("validation_status") or "") != "refuted":
        return None
    try:
        steering.raise_blocker(
            store.state_dir,
            kind="root_refuted",
            target_id="root",
            summary="The ROOT has been disproven by a confirmed counterexample — it needs revising.",
            detail=(
                "A confirmed counterexample refutes the root as stated. Decide how to restate it — e.g. "
                "restrict the scope to the locus where it holds — or confirm abandoning this root. The "
                "system is proposing a scope-restricted restatement; steer it if you want a specific scope."
            ),
            options=[
                "restrict the root's scope (weaken)",
                "restate the root (give a new statement)",
                "abandon this root",
            ],
            fingerprint="root_refuted",
            revision=int(problem.get("current_revision") or 0),
        )
    except Exception:
        pass
    recent = list(state.get("recent_runs", []))[:6]
    if any(str(r.get("mode") or "") == "weaken" and str(r.get("target_id") or "") == "root" for r in recent):
        return None
    return _action(
        "weaken",
        "root",
        "",
        "root refuted by a confirmed counterexample; propose a scope-restricted restatement of the root that "
        "excludes the counterexample family (incorporate any human steering on how to restate the goal).",
        plan_step_budget(problem, "weaken", requested_tokens),
        research_mode=research_mode,
        root_revision_required=True,
        search_intent="root_revision",
    )


def _unrouted_proof_claim_action(
    store: ProofStateStore,
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    """No hanging proven-but-unverified claims.

    A claim that already has a proof-dossier-backed inference but no active route
    *concluding it* can never be verified — the verifier is only scheduled on a
    verifier-ready route, so the proof sits in limbo (exactly what stranded g1/root/
    chow-ring on the package lemma's route). Promote it: assemble a route concluding
    the claim from its existing dossier, so the verifier then picks it up.
    """
    recent = list(state.get("recent_runs", []))[:8]
    recently_routed = {
        str(r.get("target_id") or "")
        for r in recent
        if str(r.get("mode") or "") in {"reduce", "triage_routes"}
    }
    concluding_routes: Dict[str, list] = {}
    for route in state.get("routes", []):
        if str(route.get("status") or "") == "active":
            concluding_routes.setdefault(str(route.get("conclusion_claim_id") or ""), []).append(route)
    dossier_claims: set = set()
    for inf in state.get("inferences", []):
        ev = _json_list(inf.get("evidence_artifact_ids_json"))
        if any("dossier" in str(e) or "proof" in str(e) for e in ev):
            dossier_claims.add(str(inf.get("conclusion_claim_id") or ""))
    for claim in state.get("claims", []):
        cid = str(claim.get("claim_id") or "")
        if not cid or cid not in dossier_claims:
            continue
        if str(claim.get("validation_status") or "") in {"informally_verified", "formally_verified", "refuted"}:
            continue
        if concluding_routes.get(cid):
            continue  # already routed; the verifier / readiness guards handle it
        if cid in recently_routed:
            continue  # gave it a routing attempt recently
        return _action(
            "triage_routes",
            cid,
            "",
            f"claim '{cid}' already has a proof dossier but no active route concludes it, so the verifier is "
            "never scheduled and the proof hangs. Assemble an active route concluding this claim from its "
            "existing dossier-backed inference to make it verifier-ready — do not re-derive the dossier.",
            plan_step_budget(problem, "triage_routes", requested_tokens),
            research_mode=research_mode,
            route_assembly_required=True,
            search_intent="route_assembly",
        )
    return None


def _root_refinement_signals(state: Mapping[str, Any]) -> list:
    """Obstruction signals that mean the root should be refined rather than re-proved:
    definitional mismatches, an explicitly over-broad scope, or a candidate counterexample
    family targeting the root. These open cases are really claims that refine the root."""
    signals: list = []
    for debt in state.get("debts", []):
        if str(debt.get("status") or "") != "active":
            continue
        ob = str(debt.get("obligation") or "").lower()
        if (("definition" in ob and "mismatch" in ob) or "definitions_mismatch" in ob
                or "unconditional over all" in ob or "too broad" in ob or "over-broad" in ob
                or "scope too broad" in ob or "missing hypothesis" in ob or "hypothesis gap" in ob):
            signals.append(str(debt.get("debt_id") or ""))
    for art in state.get("research_artifacts", []):
        if str(art.get("artifact_type") or "") != "candidate_counterexample":
            continue
        if str(_json_object(art.get("metadata_json")).get("target_id") or "") == "root":
            signals.append(str(art.get("artifact_id") or ""))
    return [s for s in signals if s]


def _root_refinement_action(
    store: ProofStateStore,
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    """Automate root refinement: when obstructions show the root is too broad or
    definitionally mismatched, schedule the agent to draft a corrected, scope-restricted
    restatement (and promote the key obstruction to a verifiable claim), rather than
    leaving the open cases hanging or hammering the over-broad root. The agent does the
    math; a human blocker surfaces it without halting the run."""
    root = _claim(state, "root")
    if not root:
        return None
    if str(root.get("validation_status") or "") in {"informally_verified", "formally_verified", "refuted"}:
        return None
    signals = _root_refinement_signals(state)
    if len(signals) < 2:  # require multiple converging obstruction signals
        return None
    recent = list(state.get("recent_runs", []))[:8]
    if any(str(r.get("mode") or "") in {"weaken", "strengthen"} and str(r.get("target_id") or "") == "root" for r in recent):
        return None
    try:
        steering.raise_blocker(
            store.state_dir,
            kind="root_refinement",
            target_id="root",
            summary="The root has accumulated obstructions (definitional mismatch / over-broad scope / a counterexample family) — auto-refining it into a corrected, scope-restricted restatement.",
            detail=(
                "The system is drafting a restricted root that resolves these obstructions by adding the missing "
                "hypotheses, restricting the scope, or replacing an over-broad formulation with the strongest "
                "surviving statement. Steer the scope if you want a specific restriction; otherwise it proceeds "
                "and the verifier/villain re-check it."
            ),
            options=[
                "accept the auto-restricted root",
                "specify the restriction scope",
                "keep the broad root",
            ],
            fingerprint="root_refinement",
            revision=int(problem.get("current_revision") or 0),
        )
    except Exception:
        pass
    return _action(
        "weaken",
        "root",
        "",
        "the root has accumulated obstructions showing it is too broad or definitionally mismatched (see "
        "manifest.debts / candidate counterexample): propose a corrected, scope-restricted restatement of the "
        "root that resolves them, and record the load-bearing obstruction as a verifiable claim. Restrict the "
        "scope exactly as the obstructions indicate while keeping the statement non-trivial; incorporate any "
        "human steering on the scope.",
        plan_step_budget(problem, "weaken", requested_tokens),
        research_mode=research_mode,
        root_revision_required=True,
        root_refinement_signals=signals,
        search_intent="root_refinement",
    )


def _no_content_research_guard_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    cluster = _recent_no_content_research_cluster(state)
    if not cluster:
        return None
    target_id = str(cluster.get("target_id") or "root")
    route_id = str(cluster.get("route_id") or _active_route_for_claim(state, target_id) or "")
    route = _route(state, route_id) if route_id else None
    if route:
        return _route_proof_construction_action(
            state,
            route,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            reason="recent researcher passes produced no durable mathematical artifact; construct the route proof dossier now",
            no_content_guard=True,
            extra={"no_content_research_cluster": cluster},
        )
    budget_action = {
        "target_id": target_id,
        "direct_solve_required": True,
        "deep_research_required": _should_deep_research(state, target_id),
        "research_attack_stage": "deep" if _should_deep_research(state, target_id) else "ordinary",
        "search_intent": DIRECT_PROOF_AFTER_NO_CONTENT_INTENT,
    }
    return _action(
        "prove",
        target_id,
        "",
        "recent researcher passes produced no durable mathematical artifact; make a direct proof attempt with a concrete dossier",
        plan_action_budget(problem, "prove", budget_action, requested_tokens),
        research_mode=research_mode,
        direct_solve_required=True,
        needs_proof_dossier=True,
        no_content_research_guard=True,
        no_content_research_cluster=cluster,
        research_attack_stage=budget_action["research_attack_stage"],
        deep_research_required=budget_action["deep_research_required"],
        search_intent=DIRECT_PROOF_AFTER_NO_CONTENT_INTENT,
    )


def _recent_no_content_research_cluster(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    artifact_by_id = {
        str(row.get("artifact_id") or ""): row
        for row in state.get("research_artifacts", [])
        if str(row.get("artifact_id") or "")
    }
    recent = [
        row for row in list(state.get("recent_runs", []))[:NO_CONTENT_RESEARCH_WINDOW]
        if str(row.get("actor_role") or "") == "researcher"
        and str(row.get("mode") or "") in {"prove", "reduce", "weaken", "strengthen"}
        and str(row.get("status") or "completed") == "completed"
        and str(row.get("search_intent") or "") not in {
            "duplicate_work_guard",
            "proof_compression",
            "route_triage",
            "decomposition_regulator",
            ROUTE_PROOF_CONSTRUCTION_INTENT,
            DIRECT_PROOF_AFTER_NO_CONTENT_INTENT,
        }
    ]
    if not recent:
        return None
    first_target = str(recent[0].get("target_id") or "root")
    first_route = str(recent[0].get("route_id") or "")
    cluster: list[Mapping[str, Any]] = []
    for row in recent:
        if str(row.get("target_id") or "root") != first_target:
            break
        if str(row.get("route_id") or "") != first_route:
            break
        if _run_has_contentful_artifact(row, artifact_by_id):
            break
        cluster.append(row)
    if len(cluster) < NO_CONTENT_RESEARCH_THRESHOLD:
        return None
    return {
        "policy": "no-content-research-guard",
        "window": NO_CONTENT_RESEARCH_WINDOW,
        "threshold": NO_CONTENT_RESEARCH_THRESHOLD,
        "count": len(cluster),
        "target_id": first_target,
        "route_id": first_route,
        "recent_search_intents": [str(row.get("search_intent") or "") for row in cluster],
        "recent_state_revisions": [int(row.get("state_revision", -1) or -1) for row in cluster],
    }


def _run_has_contentful_artifact(run: Mapping[str, Any], artifact_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    for artifact_id in _json_list(run.get("output_artifact_ids_json")):
        artifact = artifact_by_id.get(str(artifact_id))
        if artifact and str(artifact.get("artifact_type") or "") in CONTENTFUL_RESEARCH_ARTIFACT_TYPES:
            return True
    return False


def _duplicate_work_suppression_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    if _pending_key_failure_analysis(state) or _blocked_decomposition_plan_candidate(state):
        return None
    repeat = _recent_duplicate_work(state)
    if not repeat:
        return None
    mode = repeat["mode"]
    target_id = repeat["target_id"] or "root"
    route_id = repeat["route_id"] or _active_route_for_claim(state, target_id)
    blocking_debt = _first_blocking_debt(state)
    if blocking_debt:
        debt_target = _claim_target_for_debt(state, blocking_debt)
        debt_route = _route_for_debt(state, blocking_debt, str(debt_target))
        if target_id != str(debt_target) and (not route_id or route_id != debt_route):
            return None
    reason = (
        "duplicate-work guard: repeated equivalent task needs a sharper mathematical delta "
        f"after {repeat['count']} consecutive attempts"
    )
    common = {
        "research_mode": research_mode,
        "duplicate_work_guard": True,
        "duplicate_work_key": repeat["key"],
        "duplicate_work_count": repeat["count"],
        "search_intent": "duplicate_work_guard",
    }

    if route_id:
        readiness = _route_readiness_scorecard(state, route_id)
        if readiness.get("verifier_ready") and mode != "prove":
            return _action(
                "prove",
                target_id,
                route_id,
                f"{reason}; verifier-ready route should be checked now",
                plan_step_budget(problem, "prove", requested_tokens),
                route_readiness=readiness,
                **common,
            )
        if mode == "prove":
            route = _route(state, route_id)
            if route:
                action = _route_proof_construction_action(
                    state,
                    route,
                    problem=problem,
                    requested_tokens=requested_tokens,
                    research_mode=research_mode,
                    reason=f"{reason}; researcher must construct a different proof dossier for the verifier gap",
                    proof_repair_required=True,
                    extra=common,
                )
                action["research_diagnostic_required"] = True
                return action
            return _action(
                "reduce",
                target_id,
                route_id,
                f"{reason}; researcher must repair the verifier gap or produce a different proof dossier",
                plan_action_budget(
                    problem,
                    "reduce",
                    {"target_id": target_id, "route_id": route_id, "proof_construction_required": True},
                    requested_tokens,
                ),
                proof_repair_required=True,
                proof_construction_required=True,
                citation_allowed_in_proof=True,
                needs_proof_dossier=True,
                research_diagnostic_required=True,
                **common,
            )

    decomposition_ref = _decomposition_reference_for_target(state, target_id)
    if decomposition_ref:
        return _action(
            "regulate_decomposition",
            decomposition_ref["parent_id"],
            decomposition_ref.get("route_id", ""),
            f"{reason}; advisor should classify whether this branch is a proof-execution error, plan gap, incompatibility, or failed strategy",
            plan_step_budget(problem, "regulate_decomposition", requested_tokens),
            decomposition_regulator_required=True,
            decomposition_plan_id=decomposition_ref["decomposition_plan_id"],
            decomposition_plan_artifact_id=decomposition_ref["artifact_id"],
            blocked_branch_ids=[target_id],
            **common,
        )

    if mode == "retrieve":
        if state.get("retrieval_cards"):
            return _action(
                "synthesize_sources",
                target_id,
                route_id,
                f"{reason}; synthesize cached sources before searching again",
                plan_step_budget(problem, "synthesize_sources", requested_tokens),
                source_synthesis_required=True,
                source_synthesis_reason="duplicate retrieval attempts found cached literature that needs synthesis",
                **common,
            )
        next_mode = "reduce" if route_id else "prove"
        direct_solve = next_mode == "prove"
        return _action(
            next_mode,
            target_id,
            route_id,
            f"{reason}; researcher should move from search to a direct proof attempt, precise diagnostic, or search request",
            plan_action_budget(
                problem,
                next_mode,
                {
                    "target_id": target_id,
                    "route_id": route_id,
                    "proof_construction_required": bool(route_id),
                    "search_intent": ROUTE_PROOF_CONSTRUCTION_INTENT if route_id else "direct_solve_after_search",
                },
                requested_tokens,
            ),
            direct_solve_required=direct_solve,
            proof_construction_required=bool(route_id),
            citation_allowed_in_proof=bool(route_id),
            research_diagnostic_required=not direct_solve,
            needs_proof_dossier=True,
            search_intent="direct_solve_after_search" if direct_solve else ROUTE_PROOF_CONSTRUCTION_INTENT,
            **common,
        )

    if mode in {"reduce", "weaken", "strengthen"}:
        return _action(
            "triage_routes",
            "root",
            route_id,
            f"{reason}; advisor should choose a single next mathematical obstruction instead of another identical research pass",
            plan_step_budget(problem, "triage_routes", requested_tokens),
            route_triage_required=True,
            route_triage_reason=reason,
            **common,
        )
    return None


def _recent_duplicate_work(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    recent = [
        row for row in state.get("recent_runs", [])[:DUPLICATE_WORK_WINDOW]
        if str(row.get("mode") or "") in {"prove", "reduce", "weaken", "strengthen", "retrieve"}
        and str(row.get("search_intent") or "") not in {"duplicate_work_guard", "proof_compression", "route_triage"}
    ]
    if not recent:
        return None
    first_key = _run_work_key(recent[0])
    if not first_key[0]:
        return None
    count = 0
    for row in recent:
        if _run_work_key(row) != first_key:
            break
        count += 1
    if count < DUPLICATE_WORK_REPEAT_THRESHOLD:
        return None
    return {
        "key": list(first_key),
        "count": count,
        "mode": first_key[0],
        "target_id": first_key[1],
        "route_id": first_key[2],
        "search_intent": first_key[3],
    }


def _run_work_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    mode = str(row.get("mode") or "")
    target_id = str(row.get("target_id") or "")
    route_id = str(row.get("route_id") or "")
    search_intent = str(row.get("search_intent") or "")
    if not mode:
        return ("", "", "", "")
    return (mode, target_id, route_id, search_intent)


def _decomposition_reference_for_target(state: Mapping[str, Any], target_id: str) -> Optional[Dict[str, str]]:
    for _row, metadata, plan_id, artifact_id in _active_decomposition_plan_records(state):
        subgoal_ids = _metadata_strings(metadata, "subgoal_claim_ids", "subgoals", "claim_ids")
        if target_id not in subgoal_ids:
            continue
        return {
            "decomposition_plan_id": plan_id,
            "artifact_id": artifact_id,
            "parent_id": str(metadata.get("parent_claim_id") or metadata.get("target_id") or "root"),
            "route_id": str(metadata.get("route_id") or ""),
        }
    return None


def _invariant_errors(store: ProofStateStore) -> list[str]:
    with store.connect() as conn:
        return validate_conn(conn)


def _pending_literature_search_request(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    rows = [
        row for row in state.get("research_artifacts", [])
        if row.get("artifact_type") in SEARCH_REQUEST_ARTIFACT_TYPES
    ]
    rows.sort(key=lambda row: (int(row.get("state_revision", 0)), str(row.get("created_at") or "")), reverse=True)
    for row in rows:
        metadata = _json_object(row.get("metadata_json"))
        if str(metadata.get("status") or "").lower() in {"answered", "resolved", "discarded"}:
            continue
        request_id = str(
            metadata.get("search_request_id")
            or metadata.get("request_id")
            or row.get("artifact_id")
            or ""
        )
        artifact_id = str(row.get("artifact_id") or "")
        if _search_request_has_response(state, artifact_id=artifact_id, request_id=request_id):
            continue
        query = _first_metadata_text(
            metadata,
            "query",
            "search_query",
            "missing_theorem",
            "proof_obligation",
            "acceptance_criteria",
        )
        return {
            "artifact_id": artifact_id,
            "search_request_id": request_id,
            "target_id": str(metadata.get("target_id") or "root"),
            "route_id": str(metadata.get("route_id") or ""),
            "query": query or str(row.get("content_summary") or ""),
            "librarian_level": str(metadata.get("librarian_level") or "reader"),
        }
    return None


def _search_request_has_response(state: Mapping[str, Any], *, artifact_id: str, request_id: str) -> bool:
    for card in state.get("retrieval_cards", []):
        applicability = _json_object(card.get("applicability_json"))
        if _matches_search_request(applicability, artifact_id=artifact_id, request_id=request_id):
            return True
    for artifact in state.get("research_artifacts", []):
        if artifact.get("artifact_type") not in SOURCE_HANDOFF_ARTIFACT_TYPES:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        if _matches_search_request(metadata, artifact_id=artifact_id, request_id=request_id):
            return True
    return False


def _pending_source_handoff_digest(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    last_research_revision = -1
    for run in state.get("recent_runs", []):
        if run.get("actor_role") == "researcher" or run.get("mode") in {"reduce", "weaken", "strengthen"}:
            last_research_revision = max(last_research_revision, int(run.get("state_revision", -1)))
    rows = [
        row for row in state.get("research_artifacts", [])
        if row.get("artifact_type") in SOURCE_HANDOFF_ARTIFACT_TYPES
        and int(row.get("state_revision", 0)) > last_research_revision
    ]
    rows.sort(key=lambda row: (int(row.get("state_revision", 0)), str(row.get("created_at") or "")), reverse=True)
    if not rows:
        return None
    row = rows[0]
    metadata = _json_object(row.get("metadata_json"))
    return {
        "artifact_id": str(row.get("artifact_id") or ""),
        "artifact_type": str(row.get("artifact_type") or ""),
        "target_id": str(metadata.get("target_id") or metadata.get("claim_id") or "root"),
        "route_id": str(metadata.get("route_id") or ""),
        "search_request_id": str(metadata.get("search_request_id") or metadata.get("request_id") or ""),
    }


def _pending_key_failure_analysis(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    rows = [
        row for row in state.get("research_artifacts", [])
        if row.get("artifact_type") == FAILED_DECOMPOSITION_ARTIFACT_TYPE
    ]
    rows.sort(key=lambda row: (int(row.get("state_revision", 0)), str(row.get("created_at") or "")), reverse=True)
    for row in rows:
        metadata = _json_object(row.get("metadata_json"))
        if str(metadata.get("status") or "").lower() in {"analyzed", "resolved", "discarded"}:
            continue
        plan_id = str(metadata.get("decomposition_plan_id") or metadata.get("plan_id") or "")
        plan_artifact_id = str(metadata.get("decomposition_plan_artifact_id") or metadata.get("source_plan_artifact_id") or "")
        if _has_decomposition_regulator_response(
            state,
            plan_id=plan_id,
            plan_artifact_id=plan_artifact_id,
            failed_artifact_id=str(row.get("artifact_id") or ""),
        ):
            continue
        return {
            "artifact_id": str(row.get("artifact_id") or ""),
            "target_id": str(metadata.get("parent_claim_id") or metadata.get("target_id") or "root"),
            "route_id": str(metadata.get("route_id") or ""),
            "decomposition_plan_id": plan_id,
            "decomposition_plan_artifact_id": plan_artifact_id,
        }
    return None


def _active_decomposition_plan_step(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    steps = _decomposition_plan_ready_steps(state, include_parent=True)
    if steps:
        return steps[0]
    return None


def _parallel_decomposition_companion_actions(
    primary_action: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> list[Dict[str, Any]]:
    if not primary_action.get("decomposition_step_required"):
        return []
    plan_id = str(primary_action.get("decomposition_plan_id") or "")
    if not plan_id:
        return []
    primary_group = str(primary_action.get("decomposition_parallel_group") or "")
    if not primary_group:
        return []
    exclude_targets = {str(primary_action.get("target_id") or "")}
    steps = _decomposition_plan_ready_steps(
        state,
        plan_id=plan_id,
        exclude_targets=exclude_targets,
        include_parent=False,
    )
    companions: list[Dict[str, Any]] = []
    for step in steps:
        if str(step.get("parallel_group") or "") != primary_group:
            continue
        budget_action = {
            "target_id": step["target_id"],
            "route_id": step.get("route_id", ""),
            "proof_construction_required": bool(step.get("proof_construction_required")),
            "research_attack_stage": "fast",
            "search_intent": PARALLEL_ROUTE_PROOF_CONSTRUCTION_INTENT if step.get("proof_construction_required") else "parallel_decomposition_branch",
        }
        action = _action(
            step["mode"],
            step["target_id"],
            step.get("route_id", ""),
            "parallel independent decomposition branch",
            plan_action_budget(problem, step["mode"], budget_action, requested_tokens),
            research_mode=research_mode,
            decomposition_step_required=True,
            decomposition_plan_id=step["decomposition_plan_id"],
            decomposition_plan_artifact_id=step["artifact_id"],
            decomposition_parent_id=step.get("parent_id", ""),
            decomposition_dependencies=step.get("dependencies", []),
            decomposition_parallel_group=step.get("parallel_group", ""),
            decomposition_rank_policy=step.get("rank_policy", ""),
            direct_solve_required=bool(step.get("direct_solve_required")),
            proof_construction_required=bool(step.get("proof_construction_required")),
            citation_allowed_in_proof=bool(step.get("citation_allowed_in_proof")),
            needs_proof_dossier=bool(step.get("needs_proof_dossier", step["mode"] == "reduce")),
            research_attack_stage="fast",
            search_intent=budget_action["search_intent"],
            parallel_companion=True,
        )
        companions.append(action)
        if len(companions) >= MAX_PARALLEL_DECOMPOSITION_COMPANIONS:
            break
    return companions


def _decomposition_plan_ready_steps(
    state: Mapping[str, Any],
    *,
    plan_id: str = "",
    exclude_targets: set[str] | None = None,
    include_parent: bool,
) -> list[Dict[str, Any]]:
    exclude_targets = exclude_targets or set()
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    for row, metadata, current_plan_id, artifact_id in _active_decomposition_plan_records(state):
        if plan_id and current_plan_id != plan_id and artifact_id != plan_id:
            continue
        parent_id = str(metadata.get("parent_claim_id") or metadata.get("target_id") or "root")
        subgoal_ids = _metadata_strings(metadata, "subgoal_claim_ids", "subgoals", "claim_ids")
        dependency_map = _decomposition_dependency_map(metadata, subgoal_ids)
        parallel_group_map = _decomposition_parallel_group_map(metadata)
        ready: list[Dict[str, Any]] = []
        unresolved: list[str] = []
        for subgoal_id in subgoal_ids:
            claim = claims.get(subgoal_id)
            if not claim or claim.get("lifecycle_status") in {"abandoned", "integrated"}:
                continue
            if claim.get("validation_status") in {"informally_verified", "formally_verified"}:
                continue
            unresolved.append(subgoal_id)
            if subgoal_id in exclude_targets:
                continue
            dependencies = sorted(dependency_map.get(subgoal_id, set()))
            if not _decomposition_dependencies_verified(claims, dependencies):
                continue
            mode, route_id = _work_mode_for_claim(state, subgoal_id)
            direct_solve = mode == "prove" and not route_id
            ready.append(
                {
                    "mode": mode,
                    "target_id": subgoal_id,
                    "route_id": route_id or "",
                    "reason": "work active researcher decomposition plan before adding another split",
                    "artifact_id": artifact_id,
                    "decomposition_plan_id": current_plan_id,
                    "parent_id": parent_id,
                    "dependencies": dependencies,
                    "parallel_group": parallel_group_map.get(subgoal_id, ""),
                    "rank_policy": "scheduler_ranked_dependency_ready_branch",
                    "direct_solve_required": direct_solve,
                    "proof_construction_required": bool(route_id and mode == "reduce"),
                    "citation_allowed_in_proof": bool(route_id and mode == "reduce"),
                    "needs_proof_dossier": direct_solve or (mode == "reduce"),
                }
            )
        ready.sort(key=lambda step: _decomposition_ready_step_priority(state, step))
        if ready:
            return ready
        if unresolved:
            continue
        parent_route_id = str(metadata.get("route_id") or _active_route_for_claim(state, parent_id) or "")
        parent = claims.get(parent_id)
        if (
            include_parent
            and parent
            and parent_id not in exclude_targets
            and parent.get("validation_status") not in {"informally_verified", "formally_verified"}
        ):
            if parent_route_id:
                mode = "prove" if _route_has_inference(state, parent_route_id) else "reduce"
            else:
                mode = "prove"
            direct_solve = mode == "prove" and not parent_route_id
            return [
                {
                    "mode": mode,
                    "target_id": parent_id,
                    "route_id": parent_route_id,
                    "reason": "prove that completed decomposition subgoals imply the parent claim",
                    "artifact_id": artifact_id,
                    "decomposition_plan_id": current_plan_id,
                    "parent_id": parent_id,
                    "parent_implication_required": True,
                    "direct_solve_required": direct_solve,
                    "proof_construction_required": bool(parent_route_id and mode == "reduce"),
                    "citation_allowed_in_proof": bool(parent_route_id and mode == "reduce"),
                    "needs_proof_dossier": direct_solve or (mode == "reduce"),
                }
            ]
    return []


def _decomposition_ready_step_priority(state: Mapping[str, Any], step: Mapping[str, Any]) -> tuple[int, int, int, int, float, int, str]:
    target_id = str(step.get("target_id") or "")
    route_id = str(step.get("route_id") or "")
    claim = _claim(state, target_id) or {}
    readiness_score = 0
    verifier_ready = False
    if route_id:
        readiness = _route_readiness_scorecard(state, route_id)
        readiness_score = int(readiness.get("score", 0) or 0)
        verifier_ready = bool(readiness.get("verifier_ready"))
    try:
        root_impact = float(claim.get("root_impact", 0.0) or 0.0)
    except Exception:
        root_impact = 0.0
    return (
        int(not verifier_ready),
        maturity_rank(proof_trunk_maturity(state, target_id)),
        root_distance_for_claim_id(state, target_id),
        -readiness_score,
        -root_impact,
        int(claim.get("reduction_depth", 99) or 99),
        target_id,
    )


def _blocked_decomposition_plan_candidate(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    claims = {str(row.get("claim_id") or ""): row for row in state.get("claims", [])}
    for row, metadata, plan_id, artifact_id in _active_decomposition_plan_records(state):
        if _has_decomposition_regulator_response(state, plan_id=plan_id, plan_artifact_id=artifact_id):
            continue
        subgoal_ids = _metadata_strings(metadata, "subgoal_claim_ids", "subgoals", "claim_ids")
        if not subgoal_ids:
            return {
                "target_id": str(metadata.get("parent_claim_id") or metadata.get("target_id") or "root"),
                "route_id": str(metadata.get("route_id") or ""),
                "reason": "decomposition plan has no explicit subgoals; advisor must regulate the plan",
                "artifact_id": artifact_id,
                "decomposition_plan_id": plan_id,
                "blocked_branch_ids": [],
            }
        unresolved = [
            subgoal_id
            for subgoal_id in subgoal_ids
            if subgoal_id in claims
            and claims[subgoal_id].get("lifecycle_status") not in {"abandoned", "integrated"}
            and claims[subgoal_id].get("validation_status") not in {"informally_verified", "formally_verified"}
        ]
        if not unresolved:
            continue
        ready = _decomposition_plan_ready_steps(state, plan_id=plan_id, include_parent=False)
        if ready:
            continue
        return {
            "target_id": str(metadata.get("parent_claim_id") or metadata.get("target_id") or "root"),
            "route_id": str(metadata.get("route_id") or ""),
            "reason": "decomposition plan has unresolved branches but no dependency-ready branch; advisor must regulate the plan",
            "artifact_id": artifact_id,
            "decomposition_plan_id": plan_id,
            "blocked_branch_ids": unresolved,
        }
    return None


def _active_decomposition_plan_records(
    state: Mapping[str, Any],
) -> list[tuple[Mapping[str, Any], Dict[str, Any], str, str]]:
    rows = [
        row for row in state.get("research_artifacts", [])
        if row.get("artifact_type") == DECOMPOSITION_PLAN_ARTIFACT_TYPE
    ]
    rows.sort(key=lambda row: (int(row.get("state_revision", 0)), str(row.get("created_at") or "")), reverse=True)
    records: list[tuple[Mapping[str, Any], Dict[str, Any], str, str]] = []
    for row in rows:
        metadata = _json_object(row.get("metadata_json"))
        status = str(metadata.get("status") or "active").lower()
        if status in {"failed", "resolved", "discarded", "superseded"}:
            continue
        plan_id = str(metadata.get("decomposition_plan_id") or metadata.get("plan_id") or row.get("artifact_id") or "")
        artifact_id = str(row.get("artifact_id") or "")
        if _has_decomposition_response(state, FAILED_DECOMPOSITION_ARTIFACT_TYPE, plan_id=plan_id, plan_artifact_id=artifact_id):
            continue
        records.append((row, metadata, plan_id, artifact_id))
    return records


def _decomposition_dependency_map(metadata: Mapping[str, Any], subgoal_ids: list[str]) -> dict[str, set[str]]:
    dependencies: dict[str, set[str]] = {subgoal_id: set() for subgoal_id in subgoal_ids}
    for raw_edge in _json_list(metadata.get("dependency_edges")):
        before = ""
        after = ""
        if isinstance(raw_edge, Mapping):
            before = str(
                raw_edge.get("from")
                or raw_edge.get("source")
                or raw_edge.get("dependency")
                or raw_edge.get("prerequisite")
                or raw_edge.get("before")
                or ""
            )
            after = str(
                raw_edge.get("to")
                or raw_edge.get("target")
                or raw_edge.get("dependent")
                or raw_edge.get("after")
                or ""
            )
        elif isinstance(raw_edge, str) and "->" in raw_edge:
            before, after = [part.strip() for part in raw_edge.split("->", 1)]
        if before and after:
            dependencies.setdefault(after, set()).add(before)
    for raw_subgoal in _json_list(metadata.get("subgoals")):
        if not isinstance(raw_subgoal, Mapping):
            continue
        subgoal_id = str(raw_subgoal.get("claim_id") or raw_subgoal.get("id") or "")
        if not subgoal_id:
            continue
        for key in ("depends_on", "dependencies", "prerequisites"):
            for dependency in _json_list(raw_subgoal.get(key)):
                text = str(dependency or "").strip()
                if text:
                    dependencies.setdefault(subgoal_id, set()).add(text)
    return dependencies


def _decomposition_parallel_group_map(metadata: Mapping[str, Any]) -> dict[str, str]:
    groups: dict[str, str] = {}
    for index, raw_group in enumerate(_json_list(metadata.get("parallelizable_groups"))):
        group_id = f"group-{index + 1}"
        members: list[str] = []
        if isinstance(raw_group, Mapping):
            group_id = str(raw_group.get("group_id") or raw_group.get("id") or group_id)
            members = _metadata_strings(raw_group, "members", "claim_ids", "subgoal_claim_ids", "subgoals")
        elif isinstance(raw_group, list):
            members = [str(item or "").strip() for item in raw_group if str(item or "").strip()]
        elif isinstance(raw_group, str):
            members = [part.strip() for part in raw_group.split(",") if part.strip()]
        for member in members:
            groups[member] = group_id
    return groups


def _decomposition_dependencies_verified(claims: Mapping[str, Mapping[str, Any]], dependencies: list[str]) -> bool:
    for dependency in dependencies:
        claim = claims.get(dependency)
        if not claim or claim.get("validation_status") not in {"informally_verified", "formally_verified"}:
            return False
    return True


def _has_decomposition_response(
    state: Mapping[str, Any],
    artifact_type: str,
    *,
    plan_id: str,
    plan_artifact_id: str,
    failed_artifact_id: str = "",
) -> bool:
    for artifact in state.get("research_artifacts", []):
        if artifact.get("artifact_type") != artifact_type:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        if _matches_decomposition_reference(metadata, plan_id=plan_id, plan_artifact_id=plan_artifact_id, failed_artifact_id=failed_artifact_id):
            return True
    return False


def _has_decomposition_regulator_response(
    state: Mapping[str, Any],
    *,
    plan_id: str,
    plan_artifact_id: str,
    failed_artifact_id: str = "",
) -> bool:
    return any(
        _has_decomposition_response(
            state,
            artifact_type,
            plan_id=plan_id,
            plan_artifact_id=plan_artifact_id,
            failed_artifact_id=failed_artifact_id,
        )
        for artifact_type in {KEY_FAILURE_ARTIFACT_TYPE, ADVISOR_REPORT_ARTIFACT_TYPE}
    )


def _matches_decomposition_reference(
    payload: Mapping[str, Any],
    *,
    plan_id: str,
    plan_artifact_id: str,
    failed_artifact_id: str = "",
) -> bool:
    references = {
        str(payload.get("decomposition_plan_id") or ""),
        str(payload.get("plan_id") or ""),
        str(payload.get("source_decomposition_plan_id") or ""),
        str(payload.get("decomposition_plan_artifact_id") or ""),
        str(payload.get("source_plan_artifact_id") or ""),
        str(payload.get("failed_decomposition_artifact_id") or ""),
    }
    wanted = {value for value in {plan_id, plan_artifact_id, failed_artifact_id} if value}
    return bool(wanted & references)


def _metadata_strings(metadata: Mapping[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = metadata.get(key)
        if isinstance(raw, str):
            values.extend(part.strip() for part in raw.split(",") if part.strip())
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, Mapping):
                    text = str(item.get("claim_id") or item.get("id") or "").strip()
                else:
                    text = str(item or "").strip()
                if text:
                    values.append(text)
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _matches_search_request(payload: Mapping[str, Any], *, artifact_id: str, request_id: str) -> bool:
    return any(
        str(payload.get(key) or "") in {artifact_id, request_id}
        for key in (
            "search_request_id",
            "request_id",
            "source_request_artifact_id",
            "literature_search_request_id",
        )
    )


# NOTE: _json_object is defined once near the end of this module; an earlier
# duplicate definition with subtly different coercion semantics was removed
# because Python silently shadowed it module-wide anyway.


def _first_metadata_text(metadata: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            text = "; ".join(str(item).strip() for item in value if str(item).strip())
            if text:
                return text
    return ""


def _action(mode: str, target_id: str, route_id: str, reason: str, budget: Mapping[str, Any], **extra: Any) -> Dict[str, Any]:
    terminal_modes = {"stop_with_partial_results", "stop_solved"}
    if not budget.get("allowed", False) and mode not in terminal_modes:
        mode = "stop_with_partial_results"
        reason = budget.get("reason", reason)
    action = {
        "mode": mode,
        "target_id": target_id,
        "route_id": route_id or "",
        "reason": reason,
        "budget": dict(budget),
    }
    action.update(extra)
    if action.get("proof_construction_required") and action.get("mode") == "reduce":
        action.setdefault("display_mode", "researcher_prove")
    checkpoint_kind = _checkpointed_research_kind(action)
    if checkpoint_kind:
        action.setdefault("checkpointed_synthesis_required", True)
        action.setdefault("checkpoint_kind", checkpoint_kind)
        action.setdefault(
            "checkpoint_policy",
            {
                "purpose": "preserve global mathematical synthesis without splitting into arbitrary tiny proof fragments",
                "required_metadata": [
                    "checkpoint_kind",
                    "global_context_summary",
                    "local_obligation",
                    "what_changed",
                    "next_decisive_action",
                ],
            },
        )
    return action


def _checkpointed_research_kind(action: Mapping[str, Any]) -> str:
    mode = str(action.get("mode") or "")
    if mode not in {"prove", "reduce", "weaken", "strengthen"}:
        return ""
    if (
        action.get("strict_verifier_scope")
        or action.get("verify_ready_route_policy")
        or action.get("proof_repair_verification_required")
        or action.get("citation_certification_required")
        or action.get("citation_triage_required")
    ):
        return ""
    # In this scheduler, a routed prove action is reserved for strict verification.
    if mode == "prove" and str(action.get("route_id") or ""):
        return ""
    if action.get("proof_architecture_required") or action.get("global_synthesis_required"):
        return "global_proof_synthesis"
    if action.get("research_synthesis_required"):
        return "research_synthesis"
    if action.get("bridge_lemma_workbench_required"):
        return "bridge_workbench"
    if action.get("proof_construction_required") or action.get("proof_repair_required"):
        return "route_proof_construction"
    if action.get("direct_solve_required") or action.get("needs_proof_dossier"):
        return "direct_research_checkpoint"
    return ""


def _claim(state: Mapping[str, Any], claim_id: str) -> Optional[Mapping[str, Any]]:
    return next((row for row in state["claims"] if row["claim_id"] == claim_id), None)


def _route(state: Mapping[str, Any], route_id: str) -> Optional[Mapping[str, Any]]:
    return next((row for row in state["routes"] if row["route_id"] == route_id), None)


def _work_mode_for_claim(state: Mapping[str, Any], claim_id: str) -> tuple[str, str]:
    route_id = _active_route_for_claim(state, claim_id)
    if route_id and not _route_has_inference(state, route_id):
        return ("reduce", route_id)
    if route_id:
        return ("prove", route_id)
    return ("prove", "")


def _claim_target_for_debt(state: Mapping[str, Any], debt: Mapping[str, Any]) -> str:
    target_id = str(debt.get("suggested_next_target") or debt.get("owner_id") or "")
    if _claim(state, target_id):
        return target_id
    route = _route(state, target_id)
    if route:
        return str(route["conclusion_claim_id"])
    inference = next((row for row in state["inferences"] if row["inference_id"] == target_id), None)
    if inference:
        return str(inference["conclusion_claim_id"])

    if debt.get("owner_type") == "route":
        route = _route(state, str(debt.get("owner_id") or ""))
        if route:
            return str(route["conclusion_claim_id"])

    if debt.get("owner_type") == "inference":
        inference_id = str(debt.get("owner_id") or "")
        inference = next((row for row in state["inferences"] if row["inference_id"] == inference_id), None)
        if inference:
            return str(inference["conclusion_claim_id"])

    return target_id


def _first_blocking_debt(state: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    debts = [
        row for row in state["debts"]
        if row["status"] == "active"
        and row["severity"] == "blocking"
        and not _debt_covered_by_integrated_claim(state, row)
    ]
    claim_depth = {
        row["claim_id"]: int(row.get("reduction_depth", 99))
        for row in state["claims"]
    }
    max_depth = _max_schedulable_reduction_depth(state)
    frontier = frontier_claim_ids(state)

    schedulable = [
        row for row in debts
        if not _is_recursive_bookkeeping_debt(row, claim_depth, max_depth=max_depth)
    ]
    if schedulable:
        debts = schedulable
    elif debts:
        return None

    def priority(row: Mapping[str, Any]) -> tuple[int, int, int, int, int, int, int, str, str]:
        owner_id = str(row.get("owner_id") or "")
        owner_depth = claim_depth.get(owner_id, 0)
        target_id = str(row.get("suggested_next_target") or owner_id)
        target_depth = claim_depth.get(target_id, owner_depth)
        root_distance = root_distance_for_claim_id(state, target_id)
        frontier_penalty = int(target_id not in frontier and owner_id not in frontier)
        far_penalty = int(root_distance > FAR_FROM_ROOT_DISTANCE)
        repeated_count = int(row.get("repeated_count", 0))
        source_like_penalty = int(_is_source_like_debt(row))
        route_scope_penalty = int(str(row.get("owner_type") or "") not in {"route", "inference"})
        # Repeated debts are useful signals, but scheduling them first can trap
        # the workflow on a parent obstruction after child debts have been made.
        # Prefer fresh debts before frontier locality so a repeatedly rejected
        # root-local route does not starve a newer mathematical repair target.
        # Fresh mathematical gaps should also beat stale citation/source debts:
        # once source search finds a contradiction, the researcher must repair
        # the route instead of looping over older source obligations.
        # Among comparable debts, follow the deeper suggested child target
        # instead of re-summarizing the parent claim.
        return (
            min(repeated_count, 3),
            source_like_penalty,
            route_scope_penalty,
            far_penalty,
            -target_depth,
            frontier_penalty,
            root_distance,
            row["last_seen"],
            row["debt_id"],
        )

    debts.sort(key=priority)
    return debts[0] if debts else None


def _next_unverified_claim(
    state: Mapping[str, Any],
    *,
    exclude_ids: set[str] | None = None,
    require_unblocked_routes: bool = False,
) -> Optional[Mapping[str, Any]]:
    exclude_ids = exclude_ids or set()
    claims = [
        row for row in state["claims"]
        if row["claim_id"] not in exclude_ids
        and row["lifecycle_status"] == "active"
        and row["validation_status"] in {"untested", "plausible", "challenged"}
    ]
    paused_claim_ids = _claims_with_only_paused_routes(state)
    blocked_claim_ids = _claims_with_active_route_blockers(state)
    if require_unblocked_routes:
        claims = [row for row in claims if row["claim_id"] not in paused_claim_ids and row["claim_id"] not in blocked_claim_ids]
    unpaused_claims = [row for row in claims if row["claim_id"] not in paused_claim_ids]
    if unpaused_claims:
        claims = unpaused_claims
    max_depth = _max_schedulable_reduction_depth(state)
    frontier = frontier_claim_ids(state)

    def priority(row: Mapping[str, Any]) -> tuple[int, int, int, int, int, int, float, int, str]:
        claim_id = str(row["claim_id"])
        depth = int(row.get("reduction_depth", 99))
        root_distance = root_distance_for_claim_id(state, claim_id)
        root_impact = float(row.get("root_impact", 0.0))
        is_bookkeeping = _is_meta_bookkeeping_text(
            _joined_text(row, "claim_id", "statement", "hypotheses")
        )
        is_overdeep = claim_id != "root" and depth > max_depth
        is_far_low_impact = claim_id != "root" and root_distance > FAR_FROM_ROOT_DISTANCE and root_impact < 0.35
        return (
            int(claim_id not in frontier),
            int(is_far_low_impact),
            int(is_overdeep),
            int(is_bookkeeping),
            maturity_rank(proof_trunk_maturity(state, claim_id)),
            root_distance,
            -root_impact,
            depth,
            claim_id,
        )

    claims.sort(key=priority)
    return claims[0] if claims else None


def _cooldown_proof_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
    deferred_debt: Mapping[str, Any],
    deferred_target_id: str,
) -> Optional[Dict[str, Any]]:
    route_without_inference = _route_without_inference(state)
    if route_without_inference and route_without_inference["conclusion_claim_id"] != deferred_target_id:
        return _route_proof_construction_action(
            state,
            route_without_inference,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            reason="decomposition cooldown: construct an existing proof route before another advisor split",
            extra={"deferred_debt_id": deferred_debt["debt_id"]},
        )
    untested_claim = _next_unverified_claim(state, exclude_ids={deferred_target_id}, require_unblocked_routes=True)
    if not untested_claim:
        return None
    mode, route_id = _work_mode_for_claim(state, untested_claim["claim_id"])
    direct_solve = mode == "prove" and not route_id
    return _action(
        mode,
        untested_claim["claim_id"],
        route_id,
        "decomposition cooldown: attempt a current mathematical trunk before splitting again",
        plan_action_budget(
            problem,
            mode,
            {
                "target_id": untested_claim["claim_id"],
                "route_id": route_id,
                "proof_construction_required": bool(route_id and mode == "reduce"),
                "search_intent": ROUTE_PROOF_CONSTRUCTION_INTENT if route_id and mode == "reduce" else "direct_solve_cooldown",
            },
            requested_tokens,
        ),
        research_mode=research_mode,
        deferred_debt_id=deferred_debt["debt_id"],
        direct_solve_required=direct_solve,
        proof_construction_required=bool(route_id and mode == "reduce"),
        citation_allowed_in_proof=bool(route_id and mode == "reduce"),
        research_diagnostic_required=False if direct_solve else (mode == "reduce"),
        needs_proof_dossier=direct_solve or (mode == "reduce"),
        search_intent="direct_solve_cooldown" if direct_solve else (ROUTE_PROOF_CONSTRUCTION_INTENT if route_id and mode == "reduce" else ""),
    )


def _frontier_pressure_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
    frontier_pressure: Mapping[str, Any],
    deferred_debt: Mapping[str, Any] | None = None,
    deferred_target_id: str = "",
) -> Optional[Dict[str, Any]]:
    if not frontier_pressure.get("over_claim_cap"):
        return None

    common: dict[str, Any] = {
        "research_mode": research_mode,
        "frontier_pressure": dict(frontier_pressure),
    }
    if deferred_debt:
        common["deferred_debt_id"] = deferred_debt["debt_id"]

    if frontier_pressure.get("compression_preferred"):
        compression = _proof_compression_candidate(state, ignore_cadence=True)
        if compression:
            mode = "write"
            return _action(
                mode,
                compression["conclusion_claim_id"],
                compression["route_id"],
                "frontier pressure: compress verified route progress before adding more decomposition",
                plan_step_budget(problem, mode, requested_tokens),
                proof_compression_required=True,
                search_intent="proof_compression",
                **common,
            )

    route_without_inference = _route_without_inference(state)
    if route_without_inference and route_without_inference["conclusion_claim_id"] != deferred_target_id:
        return _route_proof_construction_action(
            state,
            route_without_inference,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            reason="frontier pressure: construct proof evidence for an existing route before another split",
            extra=common,
        )

    excluded = {deferred_target_id} if deferred_target_id else set()
    for _ in range(8):
        untested_claim = _next_unverified_claim(state, exclude_ids=excluded, require_unblocked_routes=True)
        if not untested_claim:
            break
        route_id = _active_route_for_claim(state, untested_claim["claim_id"])
        if route_id:
            mode = "prove"
            return _action(
                mode,
                untested_claim["claim_id"],
                route_id,
                "frontier pressure: verify an existing proof route before adding more decomposition",
                plan_step_budget(problem, mode, requested_tokens),
                **common,
            )
        excluded.add(untested_claim["claim_id"])

    compression = _proof_compression_candidate(state, ignore_cadence=True)
    if compression:
        mode = "write"
        return _action(
            mode,
            compression["conclusion_claim_id"],
            compression["route_id"],
            "frontier pressure: write a compact progress report before adding more decomposition",
            plan_step_budget(problem, mode, requested_tokens),
            proof_compression_required=True,
            search_intent="proof_compression",
            **common,
        )
    return None


def _blocking_debt_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
    frontier_pressure: Mapping[str, Any],
    blocking_debt: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    target_id = _claim_target_for_debt(state, blocking_debt)
    mode = "retrieve" if _is_source_like_debt(blocking_debt) else "reduce"
    central_payload = _central_obstruction_payload(state, blocking_debt)
    route_id = (
        _route_for_central_obstruction_debt(state, blocking_debt, str(target_id))
        if central_payload
        else _route_for_debt(state, blocking_debt, str(target_id))
    )
    if central_payload and mode == "retrieve":
        mode = "reduce"
    if central_payload and not route_id:
        route_id = _route_for_central_obstruction_debt(
            state,
            blocking_debt,
            str(target_id),
            allow_paused=True,
        )
    workbench_intent = BRIDGE_LEMMA_WORKBENCH_INTENT if central_payload and mode != "retrieve" else ROUTE_PROOF_CONSTRUCTION_INTENT
    if mode == "retrieve":
        return _action(
            mode,
            target_id,
            "",
            "active blocking source/citation debt",
            plan_step_budget(problem, mode, requested_tokens),
            debt_id=blocking_debt["debt_id"],
            research_mode=research_mode,
            retrieval_required=True,
            local_theorem_search_allowed=True,
            search_intent="blocking_debt_source_search",
            librarian_level="reader",
        )
    decisive_signal = {}
    if not _recent_intent_seen(state, DECISIVE_THEOREM_TEST_INTENT, window=6):
        decisive_signal = decisive_theorem_test_signal(state, debt_id=str(blocking_debt.get("debt_id") or ""))
    decisive_payload = _decisive_theorem_test_payload(
        decisive_signal,
        target_id=str(target_id),
        route_id=route_id,
        central_payload=central_payload,
    )
    combined_central_payload = {**central_payload, **decisive_payload}
    if mode == "reduce" and route_id:
        if _debt_explicitly_targets_inference(state, blocking_debt, route_id):
            verify_mode = "prove"
            return _action(
                verify_mode,
                target_id,
                route_id,
                "active blocking proof debt explicitly targets an inference for verification",
                plan_step_budget(problem, verify_mode, requested_tokens),
                debt_id=blocking_debt["debt_id"],
                proof_repair_verification_required=True,
                research_mode=research_mode,
            )
        if decisive_signal:
            decisive_budget_action = {
                "target_id": target_id,
                "route_id": route_id,
                "proof_construction_required": True,
                "decisive_theorem_test_required": True,
                "decisive_theorem_test": decisive_signal,
                "deep_research_required": True,
                "research_attack_stage": "decisive_theorem_test",
                "search_intent": DECISIVE_THEOREM_TEST_INTENT,
            }
            return _action(
                mode,
                target_id,
                route_id,
                "active blocking proof debt is an exact theorem/counterexample test; decide it before routine route repair",
                plan_action_budget(problem, mode, decisive_budget_action, requested_tokens),
                proof_repair_required=True,
                proof_construction_required=True,
                citation_allowed_in_proof=True,
                research_mode=research_mode,
                research_attack_stage="decisive_theorem_test",
                search_intent=DECISIVE_THEOREM_TEST_INTENT,
                **combined_central_payload,
            )
        return _action(
            mode,
            target_id,
            route_id,
            (
                "central bridge obstruction needs researcher construction workbench before another verifier or search pass"
                if central_payload
                else "active blocking proof debt needs route repair before another verifier pass"
            ),
            plan_action_budget(
                problem,
                mode,
                {
                    "target_id": target_id,
                    "route_id": route_id,
                    "proof_construction_required": True,
                    "deep_research_required": _should_deep_research(state, str(target_id)),
                    "research_attack_stage": "deep" if _should_deep_research(state, str(target_id)) else "ordinary",
                    "search_intent": workbench_intent,
                },
                requested_tokens,
            ),
            debt_id=blocking_debt["debt_id"],
            proof_repair_required=True,
            proof_construction_required=True,
            citation_allowed_in_proof=True,
            needs_proof_dossier=True,
            research_mode=research_mode,
            research_attack_stage="construction" if central_payload else ("deep" if _should_deep_research(state, str(target_id)) else "ordinary"),
            deep_research_required=_should_deep_research(state, str(target_id)),
            search_intent=workbench_intent,
            **central_payload,
        )
    if mode == "reduce" and not central_payload:
        pressure_action = _frontier_pressure_action(
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            frontier_pressure=frontier_pressure,
            deferred_debt=blocking_debt,
            deferred_target_id=str(target_id),
        )
        if pressure_action:
            return pressure_action
    if mode == "reduce" and not central_payload and decomposition_cooldown_active(state) and _last_run_target(state, "reduce") == str(target_id):
        cooldown_action = _cooldown_proof_action(
            state,
            problem=problem,
            requested_tokens=requested_tokens,
            research_mode=research_mode,
            deferred_debt=blocking_debt,
            deferred_target_id=str(target_id),
        )
        if cooldown_action:
            return cooldown_action
    if mode == "reduce" and not route_id:
        mode = "prove"
        if decisive_signal:
            decisive_budget_action = {
                "target_id": target_id,
                "route_id": "",
                "direct_solve_required": True,
                "decisive_theorem_test_required": True,
                "decisive_theorem_test": decisive_signal,
                "deep_research_required": True,
                "research_attack_stage": "decisive_theorem_test",
                "search_intent": DECISIVE_THEOREM_TEST_INTENT,
            }
            return _action(
                mode,
                target_id,
                "",
                "active blocking proof debt is an exact theorem/counterexample test; decide it directly before routine repair",
                plan_action_budget(problem, mode, decisive_budget_action, requested_tokens),
                research_mode=research_mode,
                direct_solve_required=True,
                research_diagnostic_required=False,
                research_attack_stage="decisive_theorem_test",
                search_intent=DECISIVE_THEOREM_TEST_INTENT,
                **combined_central_payload,
            )
        return _action(
            mode,
            target_id,
            "",
            (
                "central bridge obstruction on an unrouted target needs construction workbench"
                if central_payload
                else "active blocking proof debt on an unrouted target; try a direct proof/counterexample attack before reducing"
            ),
            plan_step_budget(problem, mode, requested_tokens),
            debt_id=blocking_debt["debt_id"],
            research_mode=research_mode,
            direct_solve_required=True,
            research_diagnostic_required=False,
            needs_proof_dossier=True,
            research_attack_stage="construction" if central_payload else "ordinary",
            search_intent=BRIDGE_LEMMA_WORKBENCH_INTENT if central_payload else "direct_solve_debt_repair",
            **central_payload,
        )
    if decisive_signal:
        decisive_budget_action = {
            "target_id": target_id,
            "route_id": route_id,
            "proof_construction_required": bool(route_id and mode == "reduce"),
            "decisive_theorem_test_required": True,
            "decisive_theorem_test": decisive_signal,
            "deep_research_required": True,
            "research_attack_stage": "decisive_theorem_test",
            "search_intent": DECISIVE_THEOREM_TEST_INTENT,
        }
        return _action(
            mode,
            target_id,
            route_id,
            "active blocking proof debt is an exact theorem/counterexample test",
            plan_action_budget(problem, mode, decisive_budget_action, requested_tokens),
            proof_construction_required=bool(route_id and mode == "reduce"),
            citation_allowed_in_proof=bool(route_id and mode == "reduce"),
            research_diagnostic_required=False,
            research_mode=research_mode,
            research_attack_stage="decisive_theorem_test",
            search_intent=DECISIVE_THEOREM_TEST_INTENT,
            **combined_central_payload,
        )
    return _action(
        mode,
        target_id,
        route_id,
        "active blocking proof debt",
        plan_action_budget(
            problem,
            mode,
            {
                "target_id": target_id,
                "route_id": route_id,
                "proof_construction_required": bool(route_id and mode == "reduce"),
                "search_intent": workbench_intent if route_id and mode == "reduce" else "",
            },
            requested_tokens,
        ),
        debt_id=blocking_debt["debt_id"],
        research_mode=research_mode,
        proof_construction_required=bool(route_id and mode == "reduce"),
        citation_allowed_in_proof=bool(route_id and mode == "reduce"),
        research_diagnostic_required=True,
        needs_proof_dossier=True,
        research_attack_stage="construction" if central_payload else "ordinary",
        search_intent=workbench_intent if route_id and mode == "reduce" else "",
        **central_payload,
    )


def _central_obstruction_workbench_action(
    state: Mapping[str, Any],
    *,
    problem: Mapping[str, Any],
    requested_tokens: Optional[int],
    research_mode: str,
) -> Optional[Dict[str, Any]]:
    clusters = central_debt_clusters(state.get("debts", []))
    if not clusters:
        return None
    active_debts = {
        str(row.get("debt_id") or ""): row
        for row in state.get("debts", [])
        if row.get("status") == "active" and row.get("severity") == "blocking"
    }
    for cluster in clusters:
        candidate_ids = [
            str(cluster.get("primary_debt_id") or ""),
            *[str(item) for item in cluster.get("alias_debt_ids", [])],
        ]
        for debt_id in candidate_ids:
            debt = active_debts.get(debt_id)
            if not debt:
                continue
            action = _blocking_debt_action(
                state,
                problem=problem,
                requested_tokens=requested_tokens,
                research_mode=research_mode,
                frontier_pressure=active_frontier_pressure(state),
                blocking_debt=debt,
            )
            if action:
                action["reason"] = "central bridge obstruction needs researcher construction workbench before another search request"
                return action
    return None


def _route_for_central_obstruction_debt(
    state: Mapping[str, Any],
    debt: Mapping[str, Any],
    target_id: str,
    *,
    allow_paused: bool = False,
) -> str:
    owner_route_id = _route_for_owner(state, str(debt.get("owner_id") or ""))
    paused = set() if allow_paused else paused_route_ids(state)
    if owner_route_id and owner_route_id not in paused and (_route(state, owner_route_id) or {}).get("status") == "active":
        return owner_route_id
    if target_id == "root":
        return ""
    return _route_for_debt(state, debt, target_id, allow_paused=allow_paused)


def _is_source_like_debt(debt: Mapping[str, Any]) -> bool:
    return str(debt.get("debt_type") or "") in {"missing_reference", "missing_hypothesis", "citation_verification"}


def _central_obstruction_payload(state: Mapping[str, Any], debt: Mapping[str, Any]) -> Dict[str, Any]:
    normalized_debts: list[Dict[str, Any]] = []
    selected_debt: Dict[str, Any] = dict(debt)
    for row in state.get("debts", []):
        normalized = dict(row)
        normalized["suggested_next_target"] = _claim_target_for_debt(state, row)
        normalized_debts.append(normalized)
        if str(row.get("debt_id") or "") == str(debt.get("debt_id") or ""):
            selected_debt = normalized
    central = central_obstruction_for_debt(normalized_debts, selected_debt)
    if not central:
        return {}
    return {
        "central_obstruction": central,
        "central_debt_id": str(central.get("primary_debt_id") or debt.get("debt_id") or ""),
        "central_debt_alias_ids": list(central.get("alias_debt_ids", [])),
        "bridge_lemma_workbench_required": True,
        "closure_pressure_required": True,
        "negative_result_ledger_required": True,
        "proof_architecture_templates_required": True,
        "cas_check_recommended": True,
    }


def _recursive_meta_drift(state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Stop when the active frontier is mostly recursive workflow bookkeeping.

    This does not ban mathematical reductions. It only catches the failure mode
    seen in v1 experiments where advisor sessions repeatedly decomposed JSON,
    schema, validator, or inventory targets instead of proving mathematical
    trunks.
    """
    claim_depth = {
        row["claim_id"]: int(row.get("reduction_depth", 99))
        for row in state["claims"]
    }
    max_depth = _max_schedulable_reduction_depth(state)
    blocking_debts = [
        row for row in state["debts"]
        if row.get("status") == "active" and row.get("severity") == "blocking"
    ]
    ordinary_debts = [
        row for row in blocking_debts
        if not _is_recursive_bookkeeping_debt(row, claim_depth, max_depth=max_depth)
    ]
    if ordinary_debts:
        return None

    active_claims = [
        row for row in state["claims"]
        if row.get("lifecycle_status") == "active"
        and row.get("validation_status") in {"untested", "plausible", "challenged"}
    ]
    ordinary_claims = [
        row for row in active_claims
        if row.get("claim_id") != "root"
        and not _is_recursive_bookkeeping_claim(row, max_depth=max_depth)
    ]
    if ordinary_claims:
        return None

    recursive_claims = [
        row for row in active_claims
        if _is_recursive_bookkeeping_claim(row, max_depth=max_depth)
    ]
    recursive_debts = [
        row for row in blocking_debts
        if _is_recursive_bookkeeping_debt(row, claim_depth, max_depth=max_depth)
    ]
    deepest_claim = max((int(row.get("reduction_depth", 0)) for row in recursive_claims), default=0)
    deepest_debt = max((_debt_target_depth(row, claim_depth) for row in recursive_debts), default=0)
    deepest = max(deepest_claim, deepest_debt)
    item_count = len(recursive_claims) + len(recursive_debts)
    if deepest >= RECURSIVE_META_DEPTH and item_count >= RECURSIVE_META_ITEM_COUNT:
        return {
            "reason": (
                "recursive bookkeeping decomposition detected; stop and report "
                "partial mathematical progress instead of pursuing schema, "
                "validator, inventory, or metadata subgoals"
            ),
            "deepest_reduction_depth": deepest,
            "recursive_item_count": item_count,
            "max_schedulable_reduction_depth": max_depth,
        }
    return None


def _is_recursive_bookkeeping_claim(row: Mapping[str, Any], *, max_depth: int) -> bool:
    depth = int(row.get("reduction_depth", 99))
    if row.get("claim_id") == "root":
        return False
    text = _joined_text(row, "claim_id", "statement", "hypotheses")
    return depth > max_depth and _is_meta_bookkeeping_text(text)


def _is_recursive_bookkeeping_debt(
    row: Mapping[str, Any],
    claim_depth: Mapping[str, int],
    *,
    max_depth: int,
) -> bool:
    depth = _debt_target_depth(row, claim_depth)
    text = _joined_text(row, "debt_id", "owner_id", "suggested_next_target", "obligation", "debt_type")
    return depth > max_depth and _is_meta_bookkeeping_text(text)


def _debt_target_depth(row: Mapping[str, Any], claim_depth: Mapping[str, int]) -> int:
    owner_id = str(row.get("owner_id") or "")
    owner_depth = claim_depth.get(owner_id, 0)
    target_id = str(row.get("suggested_next_target") or owner_id)
    return claim_depth.get(target_id, owner_depth)


def _is_meta_bookkeeping_text(text: str) -> bool:
    normalized = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
    if any(phrase in normalized for phrase in META_BOOKKEEPING_HARD_PHRASES):
        return True
    return sum(1 for term in META_BOOKKEEPING_TERMS if term in normalized) >= 2


def _joined_text(row: Mapping[str, Any], *fields: str) -> str:
    return " ".join(str(row.get(field) or "") for field in fields)


def _max_schedulable_reduction_depth(state: Mapping[str, Any]) -> int:
    problem = state.get("problem_state") or {}
    try:
        configured = int(problem.get("max_reduction_depth", DEFAULT_MAX_SCHEDULABLE_REDUCTION_DEPTH))
    except Exception:
        configured = DEFAULT_MAX_SCHEDULABLE_REDUCTION_DEPTH
    return max(1, configured)


def _active_route_for_claim(state: Mapping[str, Any], claim_id: str, *, allow_paused: bool = False) -> str:
    routes = [row for row in state["routes"] if row["conclusion_claim_id"] == claim_id and row["status"] == "active"]
    routes.sort(key=lambda row: (row["relation_to_parent"] != "sufficient", row["route_id"]))
    if allow_paused:
        return routes[0]["route_id"] if routes else ""
    paused = paused_route_ids(state)
    unpaused = [row for row in routes if row["route_id"] not in paused]
    return unpaused[0]["route_id"] if unpaused else ""


def _route_has_inference(state: Mapping[str, Any], route_id: str) -> bool:
    return any(row.get("route_id") == route_id for row in state.get("inferences", []))


def _debt_explicitly_targets_inference(state: Mapping[str, Any], debt: Mapping[str, Any], route_id: str) -> bool:
    candidate_ids = {
        str(debt.get("suggested_next_target") or ""),
    }
    candidate_ids.discard("")
    return any(
        str(row.get("route_id") or "") == route_id and str(row.get("inference_id") or "") in candidate_ids
        for row in state.get("inferences", [])
    )


def _claims_with_only_paused_routes(state: Mapping[str, Any]) -> set[str]:
    paused = paused_route_ids(state)
    active_by_claim: dict[str, list[str]] = {}
    for route in state.get("routes", []):
        if route["status"] != "active":
            continue
        active_by_claim.setdefault(route["conclusion_claim_id"], []).append(route["route_id"])
    return {
        claim_id
        for claim_id, route_ids in active_by_claim.items()
        if route_ids and all(route_id in paused for route_id in route_ids)
    }


def _claims_with_active_route_blockers(state: Mapping[str, Any]) -> set[str]:
    active_routes = {
        route["route_id"]: route["conclusion_claim_id"]
        for route in state.get("routes", [])
        if route["status"] == "active"
    }
    active_route_claims = set(active_routes.values())
    inference_claims = {
        inf["inference_id"]: active_routes[inf["route_id"]]
        for inf in state.get("inferences", [])
        if inf.get("route_id") in active_routes
    }
    blocked: set[str] = set()
    for debt in state.get("debts", []):
        if debt.get("status") != "active" or debt.get("severity") != "blocking":
            continue
        owner_type = debt.get("owner_type")
        owner_id = debt.get("owner_id")
        if owner_type == "route" and owner_id in active_routes:
            blocked.add(active_routes[owner_id])
        elif owner_type == "inference" and owner_id in inference_claims:
            blocked.add(inference_claims[owner_id])
        elif owner_type == "claim" and owner_id in active_route_claims:
            blocked.add(owner_id)
    return blocked


def _route_without_inference(state: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    with_inference = {row["route_id"] for row in state["inferences"]}
    routes = [row for row in state["routes"] if row["status"] == "active" and row["route_id"] not in with_inference]
    routes.sort(key=lambda row: (row["relation_to_parent"] != "sufficient", row["route_id"]))
    paused = paused_route_ids(state)
    unpaused = [row for row in routes if row["route_id"] not in paused]
    return unpaused[0] if unpaused else None


def _root_alignment_audit_candidate(state: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    run_count = int(state.get("run_count", 0) or 0)
    if run_count < 8 or run_count % 8 != 0:
        return None
    if _recent_intent_seen(state, "root_alignment_audit", window=6):
        return None
    routes = [row for row in route_scoreboard(state, limit=8) if row["scoreboard_status"] not in {"low_yield", "stalled", "blocked", "abandoned"}]
    if not routes:
        return None
    route_id = routes[0]["route_id"]
    return next((row for row in state["routes"] if row["route_id"] == route_id), None)


def _proof_compression_candidate(state: Mapping[str, Any], *, ignore_cadence: bool = False) -> Optional[Mapping[str, Any]]:
    run_count = int(state.get("run_count", 0) or 0)
    if not ignore_cadence and (run_count < 6 or run_count % 6 != 0):
        return None
    if _recent_intent_seen(state, "proof_compression", window=8):
        return None
    scored = route_scoreboard(state, limit=8)
    for score in scored:
        if score["scoreboard_status"] not in {"verified_part", "promising"}:
            continue
        if score["verified_inference_count"] < 2:
            continue
        route = next((row for row in state["routes"] if row["route_id"] == score["route_id"]), None)
        if route:
            return route
    return None


def _recent_intent_seen(state: Mapping[str, Any], intent: str, *, window: int) -> bool:
    recent = list(state.get("recent_runs", []))[:window]
    return any(row.get("search_intent") == intent for row in recent)


def _last_run_target(state: Mapping[str, Any], mode: str) -> str:
    for run in state.get("recent_runs", []):
        if run.get("mode") == mode:
            return str(run.get("target_id") or "")
    return ""


def _integration_candidate(state: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    verified = {"informally_verified", "formally_verified"}
    inferences_by_route: dict[str, list[Mapping[str, Any]]] = {}
    for inf in state["inferences"]:
        inferences_by_route.setdefault(inf["route_id"], []).append(inf)
    claim_status = {row["claim_id"]: row["validation_status"] for row in state["claims"]}
    for route in sorted(state["routes"], key=lambda row: row["route_id"]):
        if route["status"] != "active" or route["relation_to_parent"] != "sufficient":
            continue
        if claim_status.get(route["conclusion_claim_id"]) not in verified:
            continue
        inferences = inferences_by_route.get(route["route_id"], [])
        if not inferences:
            continue
        if any(inf["validation_status"] not in verified for inf in inferences):
            continue
        premises_ok = True
        for inf in inferences:
            for premise_id in inf.get("premise_claim_ids", []):
                if claim_status.get(premise_id) not in verified:
                    premises_ok = False
        if premises_ok:
            return route
    return None


def _external_citation_candidate(state: Mapping[str, Any], *, target_id: str) -> Optional[Dict[str, str]]:
    target = _claim(state, target_id)
    if not target:
        return None
    if target.get("validation_status") in {"informally_verified", "formally_verified", "refuted"}:
        return None
    if _recent_intent_seen(state, "citation_certification", window=4):
        return None
    relation_rank = {
        "direct_match": 0,
        "stronger_match": 1,
        "equivalent_reformulation": 2,
    }
    candidates: list[Dict[str, str]] = []
    for card in state.get("retrieval_cards", []):
        applicability = _json_object(card.get("applicability_json"))
        card_target = str(applicability.get("target_id") or target_id)
        if card_target not in {target_id, "root"}:
            continue
        relation = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation") or "")
        if relation not in relation_rank:
            continue
        missing = _json_list(card.get("missing_hypotheses_json"))
        if missing:
            continue
        candidates.append({"card_id": str(card["card_id"]), "relation": relation})
    candidates.sort(key=lambda row: (relation_rank.get(row["relation"], 99), row["card_id"]))
    return candidates[0] if candidates else None


def _definition_audit_candidate(state: Mapping[str, Any], *, target_id: str) -> Optional[Dict[str, str]]:
    if _recent_intent_seen(state, "definition_audit", window=6):
        return None
    candidate_relations = {"direct_match", "stronger_match", "equivalent_reformulation", "conditional_match"}
    for card in state.get("retrieval_cards", []):
        applicability = _json_object(card.get("applicability_json"))
        card_target = str(applicability.get("target_id") or target_id)
        if card_target not in {target_id, "root"}:
            continue
        relation = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation") or "")
        if relation not in candidate_relations:
            continue
        missing = [str(item).lower() for item in _json_list(card.get("missing_hypotheses_json"))]
        status = str(applicability.get("theorem_matching_status") or "").lower()
        if any("definition" in item or "terminology" in item or "hypoth" in item for item in missing):
            return {"card_id": str(card["card_id"]), "reason": "definition or hypothesis uncertainty blocks theorem matching"}
        if (
            relation in {"direct_match", "stronger_match", "equivalent_reformulation"}
            and status
            and ("verified" not in status or "unverified" in status)
        ):
            return {"card_id": str(card["card_id"]), "reason": "near-exact citation needs definition audit before certification"}
    return None


def _source_synthesis_candidate(state: Mapping[str, Any], *, target_id: str) -> Optional[Dict[str, str]]:
    if _recent_intent_seen(state, "source_synthesis", window=8):
        return None
    useful_nonterminal = []
    partialish = {"conditional_match", "partial_match", "method_match", "background"}
    hard_candidates_with_missing = []
    for card in state.get("retrieval_cards", []):
        applicability = _json_object(card.get("applicability_json"))
        card_target = str(applicability.get("target_id") or target_id)
        if card_target not in {target_id, "root"}:
            continue
        relation = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation") or "")
        missing = _json_list(card.get("missing_hypotheses_json"))
        if relation in partialish:
            useful_nonterminal.append(str(card["card_id"]))
        if relation in {"direct_match", "stronger_match", "equivalent_reformulation", "conditional_match"} and missing:
            hard_candidates_with_missing.append(str(card["card_id"]))
    if len(useful_nonterminal) >= 2:
        return {"reason": "multiple partial or method retrieval cards need source synthesis"}
    if hard_candidates_with_missing and any(row.get("status") == "active" for row in state.get("debts", [])):
        return {"reason": "candidate literature covers part of an active obstruction and needs synthesis"}
    return None


def _route_triage_candidate(
    state: Mapping[str, Any],
    *,
    active_trunk_pressure: Mapping[str, Any],
) -> Optional[Dict[str, str]]:
    if _recent_intent_seen(state, "route_triage", window=6):
        return None
    if active_trunk_pressure.get("over_trunk_cap"):
        return {"reason": "too many active main proof trunks; triage before adding more work"}
    for row in route_scoreboard(state, limit=8):
        if row["scoreboard_status"] in {"stalled", "low_yield"} and int(row.get("repeated_blocker_count", 0)) >= 3:
            return {
                "route_id": str(row["route_id"]),
                "reason": "route has repeated blocking debt and needs triage",
            }
    return None


def _active_main_trunk_pressure(state: Mapping[str, Any]) -> Dict[str, Any]:
    scored = route_scoreboard(state)
    protected_route_ids = _debt_protected_route_ids(state)
    active = [
        row for row in scored
        if row["scoreboard_status"] not in {"low_yield", "stalled", "blocked", "abandoned"}
        and (int(row["root_distance"]) <= 2 or float(row["root_impact"]) >= 0.75)
        and str(row["route_id"]) not in protected_route_ids
    ]
    active.sort(key=lambda row: (-float(row["score"]), int(row["root_distance"]), str(row["route_id"])))
    return {
        "policy": "active-main-trunk-cap",
        "active_main_trunk_count": len(active),
        "trunk_cap": ACTIVE_MAIN_TRUNK_CAP,
        "over_trunk_cap": len(active) > ACTIVE_MAIN_TRUNK_CAP,
        "recommended_kept_route_ids": [str(row["route_id"]) for row in active[:ACTIVE_MAIN_TRUNK_CAP]],
        "overflow_route_ids": [str(row["route_id"]) for row in active[ACTIVE_MAIN_TRUNK_CAP:]],
        "debt_protected_route_ids": sorted(protected_route_ids),
    }


def _route_for_owner(state: Mapping[str, Any], owner_id: str) -> str:
    if any(row["route_id"] == owner_id for row in state["routes"]):
        return owner_id
    for inf in state["inferences"]:
        if inf["inference_id"] == owner_id:
            return inf["route_id"]
    return ""


def _route_for_debt(state: Mapping[str, Any], debt: Mapping[str, Any], target_id: str, *, allow_paused: bool = False) -> str:
    paused = set() if allow_paused else paused_route_ids(state)
    owner_route_id = _route_for_owner(state, str(debt.get("owner_id") or ""))
    if owner_route_id and owner_route_id not in paused and (_route(state, owner_route_id) or {}).get("status") == "active":
        return owner_route_id

    candidate_claim_ids = [
        target_id,
        str(debt.get("suggested_next_target") or ""),
    ]
    if debt.get("owner_type") == "claim":
        candidate_claim_ids.append(str(debt.get("owner_id") or ""))
    for claim_id in candidate_claim_ids:
        if claim_id and _claim(state, claim_id):
            route_id = _active_route_for_claim(state, claim_id, allow_paused=allow_paused)
            if route_id and route_id not in paused:
                return route_id
    return ""


def _debt_protected_route_ids(state: Mapping[str, Any]) -> set[str]:
    protected_route_ids: set[str] = set()
    protected_claim_ids: set[str] = set()
    inference_routes = {
        str(row.get("inference_id") or ""): str(row.get("route_id") or "")
        for row in state.get("inferences", [])
    }
    claim_ids = {str(row.get("claim_id") or "") for row in state.get("claims", [])}

    for debt in state.get("debts", []):
        if debt.get("status") != "active" or debt.get("severity") != "blocking":
            continue
        owner_id = str(debt.get("owner_id") or "")
        suggested = str(debt.get("suggested_next_target") or "")
        if debt.get("owner_type") == "route":
            protected_route_ids.add(owner_id)
        elif debt.get("owner_type") == "inference" and owner_id in inference_routes:
            protected_route_ids.add(inference_routes[owner_id])
        if owner_id in claim_ids:
            protected_claim_ids.add(owner_id)
        if suggested in claim_ids:
            protected_claim_ids.add(suggested)

    for route in state.get("routes", []):
        if route.get("status") != "active":
            continue
        route_id = str(route.get("route_id") or "")
        conclusion_id = str(route.get("conclusion_claim_id") or "")
        if route_id in protected_route_ids or conclusion_id in protected_claim_ids:
            protected_route_ids.add(route_id)
    return protected_route_ids


def _integrated_route_for_claim(state: Mapping[str, Any], claim_id: str) -> str:
    routes = [
        row for row in state["routes"]
        if row["conclusion_claim_id"] == claim_id and row["relation_to_parent"] == "sufficient" and row["status"] == "integrated"
    ]
    routes.sort(key=lambda row: row["route_id"])
    return routes[0]["route_id"] if routes else ""


def _final_proof_artifact(state: Mapping[str, Any], claim_id: str) -> Optional[Mapping[str, Any]]:
    for artifact in state.get("final_artifacts", []):
        metadata = artifact.get("metadata_json", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        if not isinstance(metadata, Mapping):
            metadata = {}
        if str(metadata.get("claim_id") or "root") == claim_id:
            return artifact
    return None


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return [value] if value else []
        if isinstance(parsed, list):
            return parsed
        return [parsed] if parsed else []
    return []
