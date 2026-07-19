from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .audit import paper_audit_context_card
from .branch_summary import build_branch_summaries, build_branch_workbench
from .budget import estimate_tokens_from_text
from .completion_policy import DEFAULT_COMPLETION_POLICY
from .graph_policy import active_frontier_pressure, build_proof_spine, claim_type_label, frontier_claim_ids, proof_trunk_maturity, root_distance_for_claim_id, route_scoreboard
from .memory_policy import (
    artifact_is_raw_log,
    artifact_memory_status,
    canonicalize_debts,
    canonicalize_retrieval_cards,
    claim_memory_status,
    debt_memory_status,
    inference_memory_status,
    retrieval_card_memory_status,
    route_memory_status,
    theorem_library_memory_status,
)
from .models import fingerprint_text, json_loads, sha256_text, utc_now
from .receipt import build_partial_receipt_inventory
from .retrieval import (
    INFORMAL_SEARCH_ENABLE_ENV,
    MATLAS_BASE_URL_ENV,
    MATLAS_CONTRACT_VERSION,
    THEOREMSEARCH_BASE_URL_ENV,
    THEOREMSEARCH_CONTRACT_VERSION,
    execute_informal_theorem_search,
    informal_provider_names_for_action,
    informal_search_enabled,
    provider_content_policy_payload,
)
from .research_strategy import (
    ADVISOR_SYNTHESIS_REQUIRED_FIELDS,
    CONCEPTUAL_INVARIANT_REQUIRED_FIELDS,
    EXPERIMENT_REQUIRED_FIELDS,
    LEMMA_ROOT_LEVERAGE_GATE_FIELDS,
    PROOF_COMPRESSION_SKELETON_REQUIRED_FIELDS,
    apply_active_compression,
    strategy_context_card,
)
from .role_capabilities import role_can_use_cas, session_cas_enabled
from .research_policy import (
    RETRIEVAL_RELATION_LADDER,
    RESEARCHER_WORK_MODE_CYCLE,
    VILLAIN_WORK_MODE_CYCLE,
    librarian_escalation_policy,
    normalize_retrieval_relation,
    researcher_mode_summary,
    theorem_matching_confidence,
)
from .store import ProofStateStore
from .writing.linter import (
    REQUIRED_FIX_MARKER as WRITING_REQUIRED_FIX_MARKER,
    obligation_location as writing_obligation_location,
    required_fix_for_obligation as writing_required_fix_for_obligation,
)
from .writing.paper_contract import PAPER_CONTRACT, SUPPORTED_WRITING_REVIEW_LENSES
from .writing.revision import REVISION_DOCUMENT_ARTIFACT_TYPE, revision_document_format
from . import steering

FULL_PROOF_ARTIFACT_TYPES = {
    "final_proof",
    "partial_proof_report",
    "proof_blueprint",
    "proof_dossier",
    "research_notebook",
    "verified_blueprint",
}
SOURCE_ADAPTATION_ARTIFACT_TYPES = {
    "definition_audit_report",
    "source_adaptation_notes",
    "source_synthesis_report",
}
DECOMPOSITION_ARTIFACT_TYPES = {
    "decomposition_plan",
    "failed_decomposition_plan",
    "key_failure_analysis",
    "research_diagnostic",
    "route_obstruction",
    "hypothesis_gap",
    "construction_failure",
    "necessary_condition",
}
CAS_ARTIFACT_TYPES = {
    "cas_experiment_report",
}
ADVISOR_ARTIFACT_TYPES = {
    "advisor_report",
    "advisor_synthesis",
}
STRATEGY_ARTIFACT_TYPES = {
    "bridge_lemma_search",
    "conjecture_portfolio",
    "deep_session_report",
    "definition_candidate",
    "invention_authorization",
    "proof_compression",
    "conceptual_invariant_report",
}
RESEARCH_HANDOFF_ARTIFACT_TYPES = (
    SOURCE_ADAPTATION_ARTIFACT_TYPES
    | DECOMPOSITION_ARTIFACT_TYPES
    | CAS_ARTIFACT_TYPES
    | ADVISOR_ARTIFACT_TYPES
    | STRATEGY_ARTIFACT_TYPES
    | {"literature_search_request"}
)
ROOT_SYNTHESIS_CONTEXT_ARTIFACT_TYPES = {
    "route_obstruction",
    "construction_failure",
    "hypothesis_gap",
    "necessary_condition",
    "key_failure_analysis",
    "research_diagnostic",
    "advisor_report",
    "advisor_synthesis",
    "bridge_lemma_search",
    "conjecture_portfolio",
    "proof_compression",
    "conceptual_invariant_report",
}
VERIFICATION_PACKET_MAX_ARTIFACT_CHARS = 18_000
RESEARCHER_PACKET_MAX_ARTIFACT_CHARS = 12_000


def build_context_manifest(
    store: ProofStateStore,
    *,
    target_id: str = "root",
    route_id: Optional[str] = None,
    max_chars: int = 12_000,
    action: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    state = store.get_state()
    problem = state["problem_state"]
    # Memory hygiene (TODO 4): collapse duplicate debts before selection so a
    # packet never carries two copies of one obligation; report the collapse in
    # manifest.memory_hygiene instead of silently dropping rows.
    deduped_debts, duplicate_debts = canonicalize_debts(state["debts"])
    if duplicate_debts:
        state = dict(state)
        state["debts"] = list(deduped_debts)
    claims = {}
    for row in state["claims"]:
        card = _claim_card(row)
        card["proof_trunk_maturity"] = proof_trunk_maturity(state, row["claim_id"])
        card["root_distance"] = root_distance_for_claim_id(state, row["claim_id"])
        card["claim_type_label"] = claim_type_label(state, row)
        claims[row["claim_id"]] = card
    routes = {row["route_id"]: _route_card(row) for row in state["routes"]}
    target = claims.get(target_id)
    if target is None:
        raise ValueError(f"unknown target claim: {target_id}")

    verification_only_audit = bool(action and action.get("paper_audit_verification_only"))
    if verification_only_audit:
        selected_route = routes.get(route_id) if route_id else None
    else:
        selected_route = routes.get(route_id) if route_id else _best_route_for_target(routes.values(), target_id)
    selected_claim_ids = _select_claim_ids(state, target_id, selected_route)
    selected_inferences = _select_inferences(state, selected_claim_ids, selected_route)
    branch_focus = str((action or {}).get("branch_focus") or "")
    preferred_debt_ids = _branch_packet_debt_ids(action)
    selected_debts = _select_debts(
        state,
        selected_claim_ids,
        selected_route,
        inference_ids={str(row.get("inference_id") or "") for row in selected_inferences},
        preferred_debt_ids=preferred_debt_ids,
    )
    paper_audit_strict_packet = _is_paper_audit_strict_packet(state, action)
    if branch_focus:
        # Branch packet isolation (TODO 2): a branch-focused worker receives
        # only branch-relevant claims (Batch-1 _branch_relevant_claim_ids),
        # then debts/inferences are re-selected against that narrowed set —
        # never the full global memory.
        branch_ids = _branch_relevant_claim_ids(
            state, target_id, selected_route, selected_inferences, selected_debts
        )
        selected_claim_ids = [cid for cid in selected_claim_ids if cid in branch_ids]
        selected_inferences = _select_inferences(state, selected_claim_ids, selected_route)
        selected_debts = _select_debts(
            state,
            selected_claim_ids,
            selected_route,
            inference_ids={str(row.get("inference_id") or "") for row in selected_inferences},
            preferred_debt_ids=preferred_debt_ids,
        )
    active_compression: Dict[str, Any] = {}
    if not branch_focus and str((action or {}).get("mode") or "") in {"prove", "reduce", "weaken", "strengthen", "triage_routes", "regulate_decomposition"}:
        selected_claim_ids, active_compression = apply_active_compression(
            state,
            selected_claim_ids,
            target_id=target_id,
        )
        selected_inferences = _select_inferences(state, selected_claim_ids, selected_route)
        selected_debts = _select_debts(
            state,
            selected_claim_ids,
            selected_route,
            inference_ids={str(row.get("inference_id") or "") for row in selected_inferences},
        )
    if paper_audit_strict_packet:
        # Apply this after branch/compression reselection: those general context
        # layers may legitimately pull root-level sibling debts back in.
        selected_debts = _paper_audit_packet_debts(
            selected_debts,
            target_id=target_id,
            selected_route=selected_route,
            selected_inferences=selected_inferences,
        )
    ordinary_integration_packet = bool(
        action
        and str(action.get("mode") or "") == "integrate"
        and not action.get("paper_audit_document_integration_required")
    )
    if ordinary_integration_packet:
        # Integration certifies one already-verified sufficient route.  Root
        # and sibling debts are useful to researchers, but exposing them here
        # invites the integrator to list a semantically related upstream debt
        # in resolved_debt_ids.  The patch guard must then reject the entire
        # otherwise-valid transition because that debt is not owned by this
        # claim, route, or one of its inferences.  Keep the packet aligned with
        # the exact ownership relation enforced by _resolve_integration_debts.
        route_inference_ids = _integration_route_inference_ids(
            selected_route,
            selected_inferences,
        )
        selected_debts = _select_debts(
            state,
            [target_id],
            selected_route,
            inference_ids=route_inference_ids,
        )
    selected_artifacts = _select_artifacts(
        state,
        selected_claim_ids,
        selected_route,
        selected_inferences,
        selected_debts,
        target_id=target_id,
        action=action,
        include_stop_writer_artifacts=bool(action and action.get("write_existing_proofs_on_stop")),
    )
    if paper_audit_strict_packet:
        selected_artifacts = _paper_audit_packet_artifacts(
            state,
            selected_artifacts,
            action=action,
        )
    role_policy = _role_context_policy(action)
    patch_contract = _patch_contract(action, role_policy)
    parallel_exchange = _parallel_exchange_card(store)
    cas_enabled = session_cas_enabled(str(role_policy.get("context_role") or ""), action)
    role_policy["cas_access"] = cas_enabled
    cas_tooling = _cas_tooling_card() if cas_enabled else {}
    central_obstruction = dict((action or {}).get("central_obstruction") or {})
    negative_result_ledger = _negative_result_ledger(
        state,
        target_id=target_id,
        route_id=str(selected_route.get("route_id") if selected_route else route_id or ""),
        action=action,
    )
    proof_architecture_templates = _proof_architecture_templates(
        problem.get("root_statement", ""),
        action=action,
        central_obstruction=central_obstruction,
    )
    cas_trigger_policy = (
        _cas_trigger_policy(action, cas_tooling, central_obstruction=central_obstruction)
        if cas_enabled
        else {}
    )
    retrieval_cards, duplicate_retrieval_cards = _select_retrieval_cards(
        state["retrieval_cards"],
        target_id=target_id,
        limit=role_policy["retrieval_card_limit"],
        action=action,
    )
    theorem_library = [
        _theorem_library_entry(row)
        for row in _rank_theorem_library_entries(state.get("theorem_library_entries", []), target_id)[: role_policy["theorem_library_limit"]]
    ]
    if paper_audit_strict_packet:
        # Strict verification is deliberately local: no retrieval card or
        # theorem-library item may supplement the author's submitted proof.
        retrieval_cards = []
        duplicate_retrieval_cards = []
        theorem_library = []
    local_search_policy = _local_search_policy(
        cas_tooling,
        selected_artifacts=selected_artifacts,
        retrieval_cards=retrieval_cards,
        theorem_library=theorem_library,
        action=action,
    )
    proof_spine = build_proof_spine(state, action=action, target_id=target_id)
    if ordinary_integration_packet:
        proof_spine = _scope_integration_proof_spine(proof_spine, selected_debts)
    research_strategy = strategy_context_card(state, action or {})
    branch_summaries = build_branch_summaries(store, state=state, limit=4)
    memory_hygiene: Dict[str, Any] = {}
    if duplicate_debts:
        memory_hygiene["duplicate_debts"] = duplicate_debts
    if duplicate_retrieval_cards:
        memory_hygiene["duplicate_retrieval_cards"] = duplicate_retrieval_cards

    stop_writer = bool(action and action.get("write_existing_proofs_on_stop"))
    manifest = {
        "manifest_version": 1,
        "created_at": utc_now(),
        "problem_id": problem["problem_id"],
        "state_revision": problem["current_revision"],
        "target_id": target_id,
        "route_id": selected_route.get("route_id") if selected_route else "",
        "root_statement": problem["root_statement"],
        "budget": {
            "remaining_token_budget": problem["remaining_token_budget"],
            "reserved_verification_budget": problem["reserved_verification_budget"],
        },
        "claims": [claims[cid] for cid in selected_claim_ids if cid in claims],
        "routes": [selected_route] if selected_route else [],
        "inferences": selected_inferences,
        "debts": selected_debts,
        "artifacts": selected_artifacts,
        "retrieval_cards": retrieval_cards,
        "theorem_library": theorem_library,
        "graph_focus": _graph_focus(state, selected_claim_ids, selected_inferences, selected_debts),
        "proof_spine": proof_spine,
        "research_strategy": research_strategy,
        "active_context_compression": active_compression,
        "workflow_action": _workflow_action_card(action),
        "role_context_policy": role_policy,
        "patch_contract": patch_contract,
        "parallel_exchange": parallel_exchange,
        "local_search_policy": local_search_policy,
        "research_task": _research_task(action, target, selected_debts, state=state),
        "instructions": [
            "Treat this manifest as authoritative Albilich v1 state.",
            "Return proposed state changes only as an Albilich v1 patch JSON object.",
            "Use manifest.patch_contract for the patch shape; do not inspect framework code, schema files, README, or tests merely to learn patch syntax.",
            "Do not mark claims or inferences verified unless the role and evidence gate allow it.",
            "Do not paste full transcripts; cite artifact ids and exact statements.",
            "Use compact cards in this manifest for context; inspect only manifest-listed artifact paths when the current task needs them.",
            "Read manifest.proof_spine first: it is the compact current proof spine, including certified facts, stale/superseded work, and the current decisive theorem test.",
            "Follow manifest.local_search_policy: avoid prior results/logs/experiments and global download sweeps by default; prefer manifest.artifacts[].path, allowed_local_evidence_paths, problem-relevant manifest-listed downloads, theorem-library entries, and exact manifest paths.",
            "Use manifest.parallel_exchange as a live research blackboard for short evidence signals; signals are advisory and never verify proof state by themselves.",
            "Stay on the graph frontier: prefer root, target, local premises, active debts, and claims with small root_distance.",
            "Use manifest.role_context_policy to identify the authoritative packet for this role.",
            "Use manifest.research_strategy for bridge sufficiency, global synthesis, method-card, experiment, conjecture, invention, deep-session, information-gain, and proof-compression policy. Method cards and speculative artifacts are advisory and never proof premises.",
        ],
        "excluded_full_transcripts": True,
    }
    completion_policy = str(problem.get("completion_policy") or DEFAULT_COMPLETION_POLICY)
    manifest["completion_policy"] = {
        "policy": completion_policy,
        "run_intents": "prove_full_statement (default) | explore_partial_results | audit_or_problem_refinement",
        "note": (
            "Soft/exploratory wording in the problem file never flips this policy; only the explicit "
            "--completion-policy flag does."
        ),
    }
    if completion_policy in {"full_proof_first", "publication_ready"}:
        post_proof_note = (
            " Stop after the certified final proof is written."
            if completion_policy == "full_proof_first"
            else " After the certified final proof is written, continue through the explicit publication paper/editor gate."
        )
        manifest["instructions"].append(
            f"manifest.completion_policy={completion_policy}: the root theorem is the target; soft wording in the "
            "problem statement is not permission to stop with partial results, weaken the target, or report a "
            "weaker theorem as solving the root without a verified weaker-to-root implication. Language or "
            "formulation problems become ambiguous_hypothesis/overbroad_statement/missing_quantifier/"
            "root_scope_mismatch debts while work continues on the strongest corrected statement."
            + post_proof_note
        )
    else:
        manifest["instructions"].append(
            f"manifest.completion_policy={completion_policy}: the operator explicitly accepts partial results as "
            "a deliverable for this run; still label every result honestly (exact/weaker/conditional/partial)."
        )
    if ordinary_integration_packet:
        manifest["instructions"].append(
            "Integration debt isolation is active: only debt ids listed in manifest.debts may appear in "
            "resolved_debt_ids. Do not infer or close upstream/root/sibling debts from narrative artifacts or "
            "global proof summaries; those remain for the downstream route that owns them."
        )
    # State-driven: a stored audit_subject artifact marks the whole problem as
    # an audit run, whatever single action is being planned.
    paper_audit_card = paper_audit_context_card(state)
    if paper_audit_card:
        manifest["paper_audit"] = paper_audit_card
        # The immutable audit subject is the source document every audit role
        # is explicitly asked to inspect.  Keep its exact path inside the
        # evidence boundary even before the researcher has created the first
        # paper claim/route; otherwise the first proof-packet patch is rejected
        # merely for reading the ingested document.
        subject_path = str(paper_audit_card.get("audit_subject_path") or "").strip()
        allowed_paths = manifest["local_search_policy"].get("allowed_local_evidence_paths")
        allowed_paths = list(allowed_paths) if isinstance(allowed_paths, list) else []
        if subject_path and subject_path not in allowed_paths:
            allowed_paths.append(subject_path)
        manifest["local_search_policy"]["allowed_local_evidence_paths"] = allowed_paths
        manifest["instructions"].append(
            "manifest.paper_audit: this problem is a paper_solution_audit run — a conservative referee check of "
            "the submitted audit_subject document. Follow manifest.paper_audit.verification_pipeline: the "
            "researcher must turn each author statement/proof segment into a proof_dossier-backed paper claim, "
            "sufficient route, and terminal inference; the strict verifier checks that local packet; the "
            "integration verifier checks its verified dependencies. Keep repairs as separate proposed_repair "
            "artifacts, and never rewrite the author's proof into a different proof. This is an AI audit, not a "
            "formal proof."
        )
    if branch_summaries:
        manifest["branch_summaries"] = branch_summaries
        manifest["instructions"].append(
            "manifest.branch_summaries are compact per-branch digests (goal, status, verified vs candidate facts, "
            "blockers, failed methods, next lemma); use them to understand a branch without re-reading run history. "
            "Statuses: keep_exploiting | needs_source | needs_cas | pause_or_merge."
        )
    if branch_focus:
        try:
            manifest["branch_workbench"] = build_branch_workbench(store, branch_focus, state=state)
        except ValueError:
            manifest["branch_workbench"] = {"branch_id": branch_focus}
        manifest["instructions"].append(
            "This is a branch-scoped worker pass: manifest.branch_workbench is your branch packet "
            "(goal, verified vs candidate facts, blockers, similar lemmas, failed methods never to retry "
            "unchanged, last useful delta, stop/rotate condition). Work ONLY on this branch; submit results as "
            "ordinary patches to the shared store — it is the coordination layer, and you must not manage your "
            "own multi-agent memory. Treat facts from OTHER branches as settled proof input ONLY when their "
            "memory_status is verified (validation_status informally_verified/formally_verified); candidate "
            "facts and other workers' notes are advisory, never premises."
        )
    if memory_hygiene:
        manifest["memory_hygiene"] = memory_hygiene
        manifest["instructions"].append(
            "manifest.memory_hygiene lists duplicate debts/retrieval cards collapsed to a canonical row; "
            "reference the canonical ids and do not recreate the duplicates."
        )
    if cas_tooling:
        manifest["cas_tooling"] = cas_tooling
        manifest["instructions"].append(
            "manifest.cas_tooling lists approved CAS/data assets (Macaulay2 .m2, Julia .jl, and queryable datasets like "
            ".jsonl/.csv of h*-vectors): you MAY read, run (M2/julia/python), and query them through tool calls for "
            "bounded computations and example/counterexample search, even though their directory is otherwise excluded "
            "by local_search_policy; filter large datasets rather than loading them whole. When the computation matters, "
            "attach a cas_experiment_report with backend, code, finite scope, output summary, and the deduction to the step."
        )
    if central_obstruction:
        manifest["central_obstruction"] = central_obstruction
        manifest["instructions"].append(
            "manifest.central_obstruction is the promoted local theorem/debt all current work should target; do not create duplicate debts for it."
        )
    if negative_result_ledger or (action and action.get("negative_result_ledger_required")):
        manifest["negative_result_ledger"] = negative_result_ledger
        manifest["instructions"].append(
            "manifest.negative_result_ledger lists failed paths and obstruction fingerprints; do not reuse those ideas without directly repairing the recorded failure."
        )
    if proof_architecture_templates:
        manifest["proof_architecture_templates"] = proof_architecture_templates
        manifest["instructions"].append(
            "manifest.proof_architecture_templates are reusable proof patterns; use only templates that match the current mathematical domain."
        )
    if cas_trigger_policy:
        manifest["cas_trigger_policy"] = cas_trigger_policy
        manifest["instructions"].append(
            "manifest.cas_trigger_policy says when a bounded computation is expected; attach cas_experiment_report when the computation changes the proof state."
        )
    if active_compression:
        manifest["instructions"].append(
            "manifest.active_context_compression removes unused branches from the primary packet while preserving every historical row in storage; work from the explicit dependency closure and feed its weakest sufficient new statement into bridge search."
        )
    if action and action.get("bidirectional_bridge_search_required"):
        manifest["bridge_lemma_search_contract"] = {
            "artifact_type": "bridge_lemma_search",
            "metadata_shape": {
                "strategy_schema_version": 1,
                "target_id": "nonempty claim or root id",
                "bridge_candidates": [
                    {
                        "bridge_id": "unique nonempty id",
                        "statement": "exact proposed bridge statement",
                        "forward_support": ["verified claim or inference supporting the bridge"],
                        "target_route_id": "route id, or none_yet when no route exists",
                        "root_consequence": "exact deduction obtained if the bridge holds",
                        "estimated_difficulty": 0.5,
                        "estimated_root_leverage": 0.5,
                        "possible_methods": ["at least one concrete proof or experiment method"],
                        "falsifiability_plan": "specific counterexample or boundary test",
                        "status": "selected|viable|rejected|refuted",
                        "root_leverage_gate": {
                            "if_proved_major_case": True,
                            "if_refuted_information_gain": True,
                            "stronger_than_necessary": False,
                            "renames_current_gap": False,
                            "hypotheses_attainable": True,
                        },
                        "sufficiency_precheck": {
                            "materially_reduces_gap": True,
                            "would_reach_root": False,
                            "restates_root": False,
                            "creates_more_severe_obligations": False,
                            "hidden_obligations": [],
                        },
                    }
                ],
            },
            "candidate_count_rule": "provide one to three bridge_candidates and select at most two",
            "root_leverage_gate_fields": list(LEMMA_ROOT_LEVERAGE_GATE_FIELDS),
            "selection_rule": "reject gap renamings, overstrong statements, and unattainable hypotheses; select the weakest candidate that closes a major case and is informative if false",
            "nesting_rule": "put bridge_candidates directly under artifact metadata; do not rename it candidates or selected_candidate_ids",
        }
        manifest["instructions"].insert(1,
            "Run bidirectional bridge-lemma search now: use the verified forward frontier and backward root obligations, propose at most three candidates, temporarily assume each candidate, expose hidden obligations, reject gap-moving or duplicate statements, and attach one strategy_schema_version=1 bridge_lemma_search artifact selecting at most two candidates. Follow manifest.bridge_lemma_search_contract exactly; bridge_candidates must be nested directly under metadata."
        )
    if action and action.get("advisor_global_synthesis_required"):
        synthesis_trigger = (
            action.get("synthesis_trigger")
            if isinstance(action.get("synthesis_trigger"), Mapping)
            else {}
        )
        latest_synthesis_id = str(
            synthesis_trigger.get("latest_synthesis_artifact_id") or ""
        )
        manifest["advisor_synthesis_contract"] = {
            "artifact_type": "advisor_synthesis",
            "metadata_shape": {
                "strategy_schema_version": 1,
                "advisor_synthesis": {
                    "exact_root_status": "nonempty string",
                    "verified_core": ["at least one checked fact, or an explicit no-verified-core marker"],
                    "best_route": "nonempty route id, or none_yet",
                    "best_route_summary": "nonempty string",
                    "shortest_plausible_proof_skeleton": ["proof step"],
                    "decisive_missing_statement": "exactly one nonempty statement",
                    "alternate_routes": [],
                    "routes_to_continue": [],
                    "routes_to_pause": [],
                    "routes_to_abandon": [],
                    "duplicated_or_stagnant_work": [],
                    "evidence_that_would_change_strategy": ["nonempty item"],
                    "recommended_next_actions": ["nonempty item"],
                    "budget_distribution": {"workstream": 1.0},
                    "synthesis_confidence": 0.0,
                },
                "supersedes_synthesis_id": (
                    latest_synthesis_id
                    or "omit only when workflow_action.synthesis_trigger.latest_synthesis_artifact_id is empty"
                ),
            },
            "required_advisor_synthesis_fields": list(ADVISOR_SYNTHESIS_REQUIRED_FIELDS),
            "nesting_rule": "Put every required field under metadata.advisor_synthesis; do not rename or flatten these keys.",
        }
        manifest["instructions"].append(
            "This is the PhD advisor's global-synthesis mode, not tactical steering. Follow manifest.advisor_synthesis_contract exactly: attach one strategy_schema_version=1 advisor_synthesis artifact, put every required field under metadata.advisor_synthesis without renaming keys, supersede the latest synthesis id, identify one decisive missing statement, and pause or abandon stagnant routes through ordinary patch operations."
        )
        if latest_synthesis_id:
            manifest["instructions"].append(
                "Set metadata.supersedes_synthesis_id exactly to "
                f"{latest_synthesis_id}."
            )
    if action and action.get("proof_compression_operation_required"):
        manifest["proof_compression_contract"] = {
            "artifact_type": "proof_compression",
            "metadata_shape": {
                "strategy_schema_version": 1,
                "history_preserved": True,
                "minimal_proof_skeleton": {
                    "root": "root claim id",
                    "essential_verified_facts": [],
                    "essential_routes": ["route id or explicit none_yet marker"],
                    "unresolved_bridges": ["nonempty bridge statement"],
                    "conditional_steps": ["nonempty conditional proof step"],
                    "unused_or_low_value_branches": ["nonempty branch description"],
                    "shortest_known_route": ["nonempty proof step"],
                    "weakest_sufficient_new_statement": "nonempty theorem statement",
                    "single_decisive_missing_theorem": "exactly one theorem-sized gap",
                    "strongest_candidate_counterexample_architecture": "strongest live falsification architecture, or none_found",
                    "most_informative_failed_ideas": ["at most three failures with obstruction and revival condition"],
                },
            },
            "required_skeleton_fields": list(PROOF_COMPRESSION_SKELETON_REQUIRED_FIELDS),
            "nesting_rule": "Put every required skeleton field under metadata.minimal_proof_skeleton; do not rename or flatten these keys.",
            "verified_fact_rule": "Every essential_verified_facts entry must be an existing claim_id from manifest.claims; the list may be empty when the state has no verified claims.",
            "active_picture_rule": "Only the shortest spine, one decisive missing theorem, strongest counterexample architecture, and at most three informative failures remain active; history stays stored as background.",
        }
        manifest["instructions"].insert(1,
            "Perform canonical full-proof reconstruction and follow manifest.proof_compression_contract exactly: draft the entire shortest plausible proof in the artifact content, mark every unsupported sentence, isolate exactly one decisive missing theorem, retain only the strongest counterexample architecture and three informative failed ideas as active context, and keep all other history stored as background."
        )
    if action and action.get("conceptual_invariant_discovery_required"):
        manifest["conceptual_invariant_contract"] = {
            "artifact_type": "conceptual_invariant_report",
            "required_fields": list(CONCEPTUAL_INVARIANT_REQUIRED_FIELDS),
            "candidate_count": "one to three",
            "candidate_fields": [
                "invariant_id", "definition", "transformations_controlled", "local_lemmas_subsumed",
                "root_consequence", "falsification_example", "failure_modes", "status",
            ],
            "selection_rule": "select only an invariant that subsumes at least two local lemmas and has a concrete falsification test; selected_invariant_id may be none",
        }
        manifest["instructions"].append(
            "Run a conceptual-invariant session, not another local calculation. Compare a neighboring theorem with an explicit object/hypothesis dictionary; seek a functorial, quotient, action-kernel, restriction/induction, filtration, or universal-property object that makes several local lemmas consequences of one principle; attach one strategy_schema_version=1 conceptual_invariant_report following manifest.conceptual_invariant_contract."
        )
    if action and (
        action.get("experiment_workflow_required")
        or str(action.get("researcher_work_mode") or "") == "cas"
    ):
        manifest["cas_experiment_contract"] = {
            "artifact_type": "cas_experiment_report",
            "metadata_shape": {
                "experiment_workflow_version": 1,
                "mathematical_question": "nonempty decision question",
                "competing_hypotheses": ["hypothesis A", "hypothesis B"],
                "finite_scope": "nonempty exact finite scope",
                "backend_or_manual_method": "nonempty backend or manual method",
                "code_or_calculation": "nonempty code or calculation",
                "expected_decisive_outputs": ["at least one decisive output"],
                "observations": ["at least one structured observation"],
                "counterexamples": [],
                "interpretation": "nonempty mathematical interpretation",
                "next_proof_move": "nonempty next proof move",
                "decision_changed": "nonempty research consequence",
                "claims_infinite_statement_verified": False,
            },
            "required_fields": [*EXPERIMENT_REQUIRED_FIELDS, "decision_changed"],
            "list_rules": {
                "competing_hypotheses": "at least two nonempty entries",
                "expected_decisive_outputs": "at least one nonempty entry",
                "counterexamples": "a list, possibly empty",
            },
            "infinite_statement_rule": "CAS output may certify an infinite statement only when complete_finite_reduction_verified=true.",
        }
        manifest["instructions"].insert(1,
            "Use the experiment-conjecture-proof loop and follow manifest.cas_experiment_contract exactly whenever attaching a versioned cas_experiment_report. Before computing, state the mathematical decision question, competing hypotheses, finite scope, method, and decisive outputs; after computing, record observations, counterexamples, interpretation, decision_changed, and next_proof_move. Raw output alone cannot close a debt."
        )
    if action and action.get("definition_invention_required"):
        manifest["instructions"].append(
            "Definition or auxiliary-object invention is exceptionally authorized by the named advisor artifact. Stay within its candidate, pass, and token caps; attach a strategy_schema_version=1 definition_candidate artifact and reject it unless it is evaluable, nontrivial, proof-relevant, and supports an exact root-relevant bridge lemma."
        )
    if action and action.get("deep_session_required"):
        manifest["instructions"].append(
            "This root-critical branch receives one coherent long mathematical session, not fragmented lemma production. Try at least two materially different proof attacks unless the first closes the target; test examples, compare a neighboring theorem with an explicit dictionary, and attempt full-root assembly. Follow manifest.workflow_action.deep_session.required_deliverable exactly. Prefer a proof_dossier that changes the proof state; attach deep_session_report only as a fallback carrying a productive mathematical delta. A management-only report is not progress and must not be persisted. The session has no verification authority."
        )
    if action and action.get("decisive_obligation_frontier_required"):
        manifest["instructions"].append(
            "Treat manifest.workflow_action.decisive_obligation_frontier as the deterministic logical work frontier. Work the named decisive_obligation before an interesting side lemma. If it cannot be solved, replace it only with a strictly smaller obligation and explain the graph implication back to the selected sufficient route."
        )
    if action and action.get("representation_switch_required"):
        manifest["instructions"].append(
            "Follow manifest.workflow_action.representation_switch_contract: translate the decisive obligation into at least two materially different mathematical representations, check the implication or equivalence back to the original statement, and continue in the representation that strictly simplifies the missing step. Record the required representation-switch fields in the primary mathematical artifact metadata."
        )
    if action and action.get("theorem_adaptation_required"):
        manifest["instructions"].append(
            "Follow manifest.workflow_action.theorem_adaptation_contract. Return an exact theorem-adaptation packet, not a bibliography: source location and statement, local notation and definition dictionary, complete hypothesis map, checked and missing hypotheses, the exact local deduction, reusable proof moves from the source proof, and the boundary where adaptation fails."
        )
    if action and action.get("proof_interface_check_required"):
        manifest["instructions"].append(
            "Run the selective deterministic proof-interface checklist in manifest.workflow_action.proof_interface_contract. The verification or integration report metadata must set proof_interface_check_version=1 and explicitly record all required Boolean fields. A zero-gap verdict is allowed only when every field is true. Lean 4 is not required."
        )
    if action and action.get("counterexample_probe_required"):
        manifest["instructions"].append(
            "Counterexamples are mathematical probes: test the full original hypothesis, name at least two competing conjectures, and choose a construction or computation whose possible outcomes lead to different proof decisions. Tests of weakened shadows are diagnostic only and cannot refute the target."
        )
    context_role = str(role_policy.get("context_role") or "")
    work_mode = str((action or {}).get("researcher_work_mode") or "")
    if work_mode and context_role in {"researcher", "villain"}:
        manifest["instructions"].append(
            f"manifest.workflow_action.researcher_work_mode={work_mode}: this {context_role} pass runs in {work_mode} mode "
            "(online = live search and source reading, offline = pure thinking without web or CAS, cas = bounded "
            "computational experiments). Respect the mode; record any cross-mode needs as precise requests instead of "
            "switching mid-pass."
        )
    if context_role == "phd_advisor":
        manifest["researcher_mode_state"] = _compact_researcher_mode_state(
            researcher_mode_summary(state)
        )
        manifest["instructions"].insert(1,
            "manifest.researcher_mode_state shows the researcher's and the villain's recent online/offline/cas work modes "
            "and any active directives. If the researcher should search more, think more, or experiment more, set metadata "
            "directed_researcher_mode='online'|'offline'|'cas' (plus directed_researcher_mode_reason and optional "
            "directed_researcher_mode_steps, 1-3) on your advisor_report; use directed_villain_mode (+reason, +steps) the "
            "same way to steer the refuter; otherwise let the default rotations run."
        )
        manifest["instructions"].append(
            "Branch adjudication: you merge, redirect, pause, or kill proof branches. For each branch in "
            "manifest.branch_summaries that needs steering, set metadata.branch_states = {<branch route_id>: "
            "{'state': 'keep_exploiting'|'needs_source'|'needs_cas'|'pause_or_merge', 'reason': ...}} on your "
            "advisor_report. The scheduler honors a fresh adjudication over its own continue/rotate heuristic: "
            "keep_exploiting keeps the branch active even when blocked, pause_or_merge rotates away from it, "
            "needs_source/needs_cas route the next branch pass to the librarian/CAS."
        )
    steering_card = steering.context_card(store.state_dir)
    if steering_card:
        manifest["human_steering"] = steering_card
        manifest["instructions"].insert(
            1,
            "manifest.human_steering carries directives from the supervising mathematician. Treat "
            "unconsumed human directives as HIGH-PRIORITY guidance that overrides the default plan "
            "for this step, and address any open blocker it names. Never halt waiting for input.",
        )
    run_instruction = os.environ.get("ALBILICH_RUN_INSTRUCTION", "").strip()
    if run_instruction:
        manifest["run_instruction"] = _compact_text(run_instruction, 2_000)
        # Run-specific user constraints are high-priority context and must
        # survive emergency instruction trimming. Keep them beside the
        # authoritative-manifest instruction rather than at the tail.
        manifest["instructions"].insert(
            1,
            f"Additional run instruction for this execution: {manifest['run_instruction']}"
        )
    verification_packet = _verification_packet(
        state,
        target=target,
        selected_route=selected_route,
        selected_claim_ids=selected_claim_ids,
        selected_inferences=selected_inferences,
        selected_debts=selected_debts,
        action=action,
    )
    if verification_packet:
        manifest["verification_packet"] = verification_packet
        manifest["instructions"].append(
            "Strict local verification must use manifest.verification_packet; do not certify a route from compact graph summaries alone."
        )
    if paper_audit_strict_packet:
        _apply_paper_audit_strict_packet_isolation(manifest)
    researcher_packet = _researcher_packet(
        state,
        target=target,
        selected_route=selected_route,
        selected_claim_ids=selected_claim_ids,
        selected_inferences=selected_inferences,
        selected_debts=selected_debts,
        action=action,
    )
    if researcher_packet:
        manifest["researcher_packet"] = researcher_packet
        packet_instruction = (
            "Villain work should treat manifest.researcher_packet as the active adversarial workbench."
            if role_policy.get("context_role") == "villain"
            else "Researcher work should treat manifest.researcher_packet as the active proof dossier and mathematical workbench."
        )
        manifest["instructions"].append(packet_instruction)
    writing_review_packet = _writing_review_packet(state, action=action)
    if writing_review_packet:
        manifest["writing_review_packet"] = writing_review_packet
        _apply_writing_lens_isolation(manifest, str((action or {}).get("critic_lens") or ""))
        _permit_writing_review_artifact_path(manifest, writing_review_packet)
        manifest["instructions"].append(
            "Writing review must use manifest.writing_review_packet as the authoritative packet: "
            "writing_review_packet.final_proof.content is the document under review (see its "
            "reviewed_artifact_type and document_format) and is already inlined here, "
            "so you need not read it from disk; if you do, its own path is permitted. The rest of the manifest is "
            "deliberately reduced for lens isolation; do not ask for the missing proof-state context."
        )
    writing_revision_packet = _writing_revision_packet(state, action=action)
    if writing_revision_packet:
        manifest["writing_revision_packet"] = writing_revision_packet
        _permit_writing_review_artifact_path(manifest, writing_revision_packet)
        revised_type = str(writing_revision_packet.get("revised_artifact_type") or "final_proof")
        manifest["instructions"].append(
            "Writing revision must use manifest.writing_revision_packet: revise "
            "writing_revision_packet.final_proof.content DIFF-MINIMALLY to discharge exactly the listed "
            f"open_writing_debts, attach the revised {revised_type} (complete content, new artifact_id), "
            "and resolve each debt via update_debt. The exact current-document path is permitted for a full-file "
            "read when the inlined content is truncated."
        )
    writing_paper_packet = _writing_paper_packet(state, action=action)
    if writing_paper_packet:
        manifest["writing_paper_packet"] = writing_paper_packet
        manifest["instructions"].append(
            "Paper authoring must use manifest.writing_paper_packet: writing_paper_packet.certificate.content is "
            "the internal certificate and your sole source of mathematical truth; writing_paper_packet.literature "
            "lists the only works you may cite. Attach exactly one final_paper artifact whose content is the "
            "COMPLETE standalone LaTeX source, per the paper contract below."
        )
        manifest["instructions"].append(PAPER_CONTRACT)
    if str((action or {}).get("mode") or "") == "write" and (
        (action or {}).get("paper_authoring")
        or (action or {}).get("paper_revision")
        or (action or {}).get("external_writing_revision")
    ):
        staging_dir = _permit_writer_paper_staging_dir(manifest, store)
        if writing_paper_packet:
            writing_paper_packet["staging_dir"] = staging_dir
        if writing_revision_packet:
            writing_revision_packet["staging_dir"] = staging_dir
        if (action or {}).get("external_writing_revision"):
            document_format = str((action or {}).get("document_format") or "md")
            manifest["instructions"].append(
                "Revise the external manuscript as a real file: preserve its source format, write the COMPLETE "
                f"revised document to {staging_dir}/<artifact_id>.{document_format}, then attach it by path with "
                "artifact_type=revision_document and NO content field."
            )
        else:
            manifest["instructions"].append(
                "Author the final_paper as a real file, not a JSON string: write the COMPLETE LaTeX source to "
                f"{staging_dir}/<artifact_id>.tex via shell, then attach it by path (attach_artifact with path set and "
                "NO content field); this avoids all JSON escaping of LaTeX."
            )
    if stop_writer:
        manifest["partial_result_receipt"] = build_partial_receipt_inventory(
            state["claims"],
            artifacts=state["artifacts"],
            max_statement_chars=700,
            max_proof_chars=1_200,
        )
        manifest["instructions"].append(
            "For a partial stop-writer artifact, include every item in partial_result_receipt.verified_side_lemmas "
            "and every item in partial_result_receipt.other_claims; do not omit claims from the receipt ledger. "
            "For verified side lemmas, include the proof_artifacts material as the proof dossier, not merely the artifact ids."
        )
    if action and action.get("paper_audit_verification_only"):
        _apply_paper_audit_verification_only_isolation(manifest)
    manifest = _scrub_raw_log_references(manifest, _raw_log_artifact_ids(state))
    return _fit_manifest(manifest, max_chars=max_chars)


def build_resume_delta_manifest(
    store: ProofStateStore,
    *,
    target_id: str = "root",
    route_id: Optional[str] = None,
    action: Optional[Mapping[str, Any]] = None,
    since_revision: int = 0,
) -> Dict[str, Any]:
    """Compact continuation context for a RESUMED same-role session.

    The agent already holds the prior full manifest and the artifacts it read in its
    session history, so we send only what changed since ``since_revision`` (new
    artifacts, current active debts, the current target/route), the next action,
    human steering, and budget — plus a hard instruction not to re-read prior context.
    This is what makes same-role session resume cheap: no re-reading every step.
    """
    state = store.get_state()
    problem = state["problem_state"]
    cur = int(problem["current_revision"])
    since = int(since_revision or 0)
    claims = {row["claim_id"]: _claim_card(row) for row in state["claims"]}
    routes = {row["route_id"]: _route_card(row) for row in state["routes"]}
    target = claims.get(target_id) or claims.get("root")
    selected_route = routes.get(route_id) if route_id else None
    role_policy = _role_context_policy(action)
    changed_artifacts = [
        {
            "artifact_id": a["artifact_id"],
            "artifact_type": a["artifact_type"],
            "producer_role": a.get("producer_role"),
            "state_revision": a.get("state_revision"),
            "memory_status": artifact_memory_status(a, current_revision=cur),
            "content_summary": _compact_text(str(a.get("content_summary") or ""), 400),
            "path": a.get("path"),
        }
        for a in state["artifacts"]
        if int(a.get("state_revision") or 0) > since and not artifact_is_raw_log(a)
    ][-12:]
    active_debt_rows = list(state["debts"])
    if str((action or {}).get("mode") or "") == "integrate" and not (action or {}).get(
        "paper_audit_document_integration_required"
    ):
        integration_owner_ids = _integration_packet_owner_ids(
            target_id=target_id,
            selected_route=selected_route,
            selected_inferences=state["inferences"],
        )
        active_debt_rows = [
            debt
            for debt in active_debt_rows
            if str(debt.get("owner_id") or "") in integration_owner_ids
            or str(debt.get("suggested_next_target") or "") in integration_owner_ids
        ]
    active_debts = [
        {
            "debt_id": d["debt_id"],
            "severity": d.get("severity"),
            "memory_status": debt_memory_status(d),
            "obligation": _compact_text(str(d.get("obligation") or ""), 300),
            "suggested_next_target": d.get("suggested_next_target"),
        }
        for d in active_debt_rows
        if str(d.get("status") or "") == "active"
    ]
    manifest: Dict[str, Any] = {
        "manifest_version": 1,
        "resume_continuation": True,
        "created_at": utc_now(),
        "problem_id": problem["problem_id"],
        "state_revision": cur,
        "since_revision": since,
        "target_id": target_id,
        "route_id": selected_route.get("route_id") if selected_route else (route_id or ""),
        "budget": {
            "remaining_token_budget": problem["remaining_token_budget"],
            "reserved_verification_budget": problem["reserved_verification_budget"],
        },
        "workflow_action": _workflow_action_card(action),
        "patch_contract": _patch_contract(action, role_policy),
        "target_claim": target,
        "route": selected_route,
        "changed_artifacts_since_resume": changed_artifacts,
        "active_debts": active_debts,
        "instructions": [
            f"CONTINUATION of your prior session — the proof state is now at revision {cur}; your last turn was at revision {since}.",
            "You already hold the full context manifest and every artifact you read earlier in this session: DO NOT re-read those artifacts or re-open the manifest; rely on your existing context.",
            "Below is ONLY what changed since your last turn (new artifacts, current active debts, the current target/route, your next assigned action).",
            "Return exactly one Albilich v1 patch JSON object with base_revision equal to manifest.state_revision and this step's actor_role/target_id; use manifest.patch_contract for shape.",
            "Open a changed artifact's full file only if you genuinely need content not already in your context.",
        ],
    }
    if str((action or {}).get("mode") or "") == "integrate" and not (action or {}).get(
        "paper_audit_document_integration_required"
    ):
        manifest["instructions"].append(
            "For this resumed integration pass, current active_debts replaces any broader debt list from the "
            "earlier context. Only ids in active_debts may appear in resolved_debt_ids; never close an upstream, "
            "root, or sibling debt while integrating this selected route."
        )
    steering_card = steering.context_card(store.state_dir)
    if steering_card:
        manifest["human_steering"] = steering_card
        manifest["instructions"].insert(
            1,
            "manifest.human_steering carries HIGH-PRIORITY directives from the supervising mathematician; act on unconsumed ones now.",
        )
    return _scrub_raw_log_references(manifest, _raw_log_artifact_ids(state))


def _raw_log_artifact_ids(state: Mapping[str, Any]) -> set[str]:
    return {
        str(row.get("artifact_id") or "")
        for row in state.get("artifacts", [])
        if artifact_is_raw_log(row)
    }


def _scrub_raw_log_references(value: Any, raw_ids: set[str]) -> Any:
    """Strip references to raw session logs/transcripts from a manifest.

    The artifacts themselves are already excluded from selection; this removes
    dangling id references (e.g. a debt's source_artifact_ids citing a
    session_failure_* artifact) so raw run logs never surface in role context.
    """
    if not raw_ids:
        return value
    if isinstance(value, Mapping):
        return {
            key: ("" if isinstance(item, str) and item in raw_ids else _scrub_raw_log_references(item, raw_ids))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _scrub_raw_log_references(item, raw_ids)
            for item in value
            if not (isinstance(item, str) and item in raw_ids)
        ]
    return value


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    payload = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    return sha256_text(payload)


def render_manifest(manifest: Mapping[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)


def _researcher_mode_policy_card(action: Mapping[str, Any], *, packet_role: str = "researcher") -> Dict[str, Any]:
    work_mode = str(action.get("researcher_work_mode") or "")
    if not work_mode:
        return {}
    if packet_role == "villain":
        mode_contracts = {
            "online": "Live web search is enabled for this refutation pass: hunt published counterexample families, contradicting or constraining theorems, and prior art that settles the target either way; record decisive sources precisely and stop once you have a decisive lead.",
            "offline": "No web search and no CAS this pass: stress hypotheses and construct counterexamples by hand from the manifest and your own mathematics; record precise computation or source requests for later passes instead of stalling.",
            "cas": "Adversarial computation is the point of this pass: run bounded counterexample sweeps and hypothesis-failure checks (or enumerate the smallest cases by hand if no backend runs) and end with what was ruled out or exposed in a cas_experiment_report.",
        }
        cycle = list(VILLAIN_WORK_MODE_CYCLE)
        policy = "villain online/offline/cas work-mode loop (computation-first)"
        directive_key = "directed_villain_mode"
    elif packet_role == "researcher":
        mode_contracts = {
            "online": "Live web search is enabled for this pass: hunt for exact/stronger/equivalent theorems and methods, read the strongest sources, translate them into local notation, and stop searching once a usable result is in hand.",
            "offline": "No web search and no CAS this pass: think and prove from the manifest, cached cards, and your own mathematics; record precise literature or CAS requests for later passes instead of stalling.",
            "cas": "Computation is the point of this pass: run bounded decisive CAS experiments (or explicit hand computation of small cases if no backend runs) and end with a mathematical conclusion in a cas_experiment_report.",
        }
        cycle = list(RESEARCHER_WORK_MODE_CYCLE)
        policy = "researcher online/offline/cas work-mode loop"
        directive_key = "directed_researcher_mode"
    else:
        return {}
    return {
        "policy": policy,
        "work_mode": work_mode,
        "source": str(action.get("work_mode_source") or ""),
        "reason": str(action.get("researcher_work_mode_reason") or ""),
        "advisor_mode_directive_artifact_id": str(action.get("advisor_mode_directive_artifact_id") or ""),
        "cycle": cycle,
        "mode_contract": mode_contracts.get(work_mode, ""),
        "supervision": (
            "The PhD advisor supervises this loop and may direct the next mode via advisor_report metadata "
            f"{directive_key} when you should search more (online), think more (offline), or experiment more (cas)."
        ),
    }


def _compact_researcher_mode_state(summary: Mapping[str, Any]) -> Dict[str, Any]:
    history = [
        {
            "work_mode": str(item.get("work_mode") or ""),
            "source": str(item.get("source") or ""),
            "status": str(item.get("status") or ""),
            "search_intent": str(item.get("search_intent") or ""),
        }
        for item in list(summary.get("history") or [])[:8]
        if isinstance(item, Mapping)
    ]
    directive = summary.get("advisor_directive")
    villain = summary.get("villain") if isinstance(summary.get("villain"), Mapping) else {}
    villain_history = [
        {
            "work_mode": str(item.get("work_mode") or ""),
            "source": str(item.get("source") or ""),
            "status": str(item.get("status") or ""),
        }
        for item in list(villain.get("history") or [])[:6]
        if isinstance(item, Mapping)
    ]
    villain_directive = villain.get("advisor_directive")
    return {
        "policy": str(summary.get("policy") or ""),
        "cycle": list(summary.get("cycle") or RESEARCHER_WORK_MODE_CYCLE),
        "current": dict(summary.get("current") or {}),
        "history": history,
        "advisor_directive": dict(directive) if isinstance(directive, Mapping) else {},
        "villain": {
            "cycle": list(villain.get("cycle") or VILLAIN_WORK_MODE_CYCLE),
            "current": dict(villain.get("current") or {}),
            "history": villain_history,
            "advisor_directive": dict(villain_directive) if isinstance(villain_directive, Mapping) else {},
        },
    }


def _role_context_policy(action: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    mode = str((action or {}).get("mode") or "")
    if mode == "validate_counterexample":
        return {
            "context_role": "counterexample_validator",
            "retrieval_card_limit": 0,
            "theorem_library_limit": 0,
            "authoritative_packet": "candidate counterexample plus validation evidence",
            "summary": "independently validate one concrete counterexample and record the resulting refutation",
        }
    if mode == "prove":
        if (action or {}).get("paper_audit_document_review_required"):
            return {
                "context_role": "strict_verifier",
                "retrieval_card_limit": 0,
                "theorem_library_limit": 0,
                "authoritative_packet": "immutable audit_subject document",
                "summary": "review the complete submitted paper directly without proof search or repair",
            }
        if not (action or {}).get("route_id") and not (action or {}).get("citation_certification_required") and not (action or {}).get("citation_triage_required"):
            return {
                "context_role": "researcher",
                "retrieval_card_limit": 5,
                "theorem_library_limit": 6,
                "authoritative_packet": "researcher_packet",
                "summary": "direct proof attempt from proof workbench, debts, and source handoffs",
            }
        if (action or {}).get("citation_certification_required") or (action or {}).get("citation_triage_required"):
            return {
                "context_role": "citation_verifier",
                "retrieval_card_limit": 6,
                "theorem_library_limit": 8,
                "authoritative_packet": "retrieval_cards plus verification_packet",
                "summary": "triage or verify citations from source cards and bounded proof packet",
            }
        return {
            "context_role": "strict_verifier",
            "retrieval_card_limit": 3,
            "theorem_library_limit": 4,
            "authoritative_packet": "verification_packet",
            "summary": "verify from local verification_packet",
        }
    if mode == "refute":
        return {
            "context_role": "villain",
            "retrieval_card_limit": 5,
            "theorem_library_limit": 6,
            "authoritative_packet": "researcher_packet",
            "summary": "adversarial refutation work from proof workbench, debts, examples, and source handoffs",
        }
    if mode in {"reduce", "weaken", "strengthen"}:
        return {
            "context_role": "researcher",
            "retrieval_card_limit": 5,
            "theorem_library_limit": 6,
            "authoritative_packet": "researcher_packet",
            "summary": "work from proof workbench, debts, and source handoffs",
        }
    if mode in {"retrieve", "synthesize_sources", "audit_definitions"}:
        return {
            "context_role": "literature_researcher",
            "retrieval_card_limit": 8,
            "theorem_library_limit": 12,
            "authoritative_packet": "research_task",
            "summary": "answer research_task using cached and live literature",
        }
    if mode in {"triage_routes", "regulate_decomposition"}:
        return {
            "context_role": "phd_advisor",
            "retrieval_card_limit": 5,
            "theorem_library_limit": 8,
            "authoritative_packet": "compact graph focus plus workflow_action.advisor_evidence_signal and researcher_mode_state",
            "summary": "synthesize proof evidence, steer one concrete next research action, and supervise the researcher work-mode loop",
        }
    if mode == "integrate":
        if (action or {}).get("paper_audit_document_integration_required"):
            return {
                "context_role": "integration_verifier",
                "retrieval_card_limit": 0,
                "theorem_library_limit": 0,
                "authoritative_packet": "audit_subject plus strict document verification report",
                "summary": "check global dependency closure without repairing the submitted proof",
            }
        return {
            "context_role": "integration_verifier",
            "retrieval_card_limit": 3,
            "theorem_library_limit": 4,
            "authoritative_packet": "selected verified route packet",
            "summary": "integrate only after checking verified route evidence and root alignment",
        }
    if mode == "write":
        if (action or {}).get("paper_audit_referee_report_required"):
            return {
                "context_role": "writer",
                "retrieval_card_limit": 0,
                "theorem_library_limit": 0,
                "authoritative_packet": "audit_subject plus strict and integration verifier reports",
                "summary": "compose the final verifier-only referee report",
            }
        return {
            "context_role": "writer",
            "retrieval_card_limit": 8,
            "theorem_library_limit": 10,
            "authoritative_packet": "partial_result_receipt or integrated route packet",
            "summary": "write from verified route material and references",
        }
    if mode == "review_writing":
        lens = str(action.get("critic_lens") or "")
        # The editor checks bibliography reality against the literature ledger;
        # the legacy provenance_auditor kept the same access.
        sees_literature = lens in {"editor", "provenance_auditor"}
        return {
            "context_role": "writing_critic",
            "retrieval_card_limit": 8 if sees_literature else 0,
            "theorem_library_limit": 8 if sees_literature else 0,
            "authoritative_packet": "writing_review_packet",
            "summary": f"review the paper's exposition through the {lens or 'writing'} lens",
        }
    return {
        "context_role": "general",
        "retrieval_card_limit": 4,
        "theorem_library_limit": 6,
        "authoritative_packet": "compact graph focus",
        "summary": "use compact graph focus",
    }


def _patch_contract(action: Optional[Mapping[str, Any]], role_policy: Mapping[str, Any]) -> Dict[str, Any]:
    action = action or {}
    context_role = str(role_policy.get("context_role") or "general")
    mode = str(action.get("mode") or "")
    common = {
        "required_top_level": [
            "schema_version",
            "problem_id",
            "base_revision",
            "actor_role",
            "target_id",
            "operations",
            "rationale",
        ],
        "base_revision_rule": "Use manifest.state_revision exactly.",
        "artifact_rule": "Prefer inline content in attach_artifact; do not set producer_role; artifact paths must stay under the current proof-state artifacts directory.",
        "status_rule": "Only verifier/integration roles may propose verified, refuted, or integrated status transitions.",
        "closed_claim_rule": "Do not add a new active sufficient route whose conclusion_claim_id is already integrated. Add evidence to an existing route/inference only when repairing an explicit integration/root-synthesis debt, otherwise work the next root-level gap.",
        "debt_owner_rule": "For add_debt/update_debt, owner_id must be a concrete graph id copied from an existing or same-patch claim_id, route_id, or inference_id. Never use agent role names such as researcher, phd_advisor, advisor, verifier, or literature_researcher as owner_id; put the responsible role in prose or metadata instead.",
        "schema_discovery_rule": "Do not read agents/generation/phase2/*.py, schemas, tests, or README just to discover patch syntax; use these templates.",
        "parallel_signal_rule": "Optional top-level parallel_signals may summarize evidence for other live branches; signals are written to the exchange by the workflow and do not verify proof state.",
    }
    contracts: dict[str, list[dict[str, Any]]] = {
        "researcher": [
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=proof_dossier|research_notebook|research_diagnostic|literature_search_request|decomposition_plan|cas_experiment_report|bridge_lemma_search|conjecture_portfolio|proof_compression|conceptual_invariant_report|deep_session_report|definition_candidate", "content", "metadata(optional)"]},
            {"op": "add_claim", "fields": ["claim_id", "kind=lemma|theorem|definition|hypothesis|obstruction|counterexample|reference", "statement", "validation_status=untested|plausible|challenged", "parent_ids", "root_impact", "reduction_depth", "evidence_artifact_ids"]},
            {"op": "add_route", "fields": ["route_id", "conclusion_claim_id", "label", "strategy", "relation_to_parent=sufficient|necessary|diagnostic|variant", "evidence_artifact_ids"]},
            {"op": "add_inference", "fields": ["inference_id", "route_id", "conclusion_claim_id", "premise_claim_ids", "validation_status=untested|plausible|challenged", "explanation", "evidence_artifact_ids"]},
            {"op": "update_inference", "fields": ["inference_id", "add_evidence_artifact_ids", "explanation_append"], "rule": "Append route evidence or explanation only; this does not change validation status."},
            {"op": "add_debt", "fields": ["debt_id", "owner_type=claim|route|inference", "owner_id", "debt_type", "severity=blocking|major|minor", "status=active", "obligation", "source_artifact_ids", "suggested_next_target"]},
        ],
        "villain": [
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=candidate_counterexample|route_obstruction|hypothesis_gap|construction_failure|necessary_condition|research_notebook|research_diagnostic|cas_experiment_report|conjecture_portfolio", "content", "metadata(optional)"]},
            {"op": "add_claim", "fields": ["claim_id", "kind=obstruction|counterexample|lemma", "statement", "validation_status=untested|plausible|challenged", "parent_ids", "root_impact", "reduction_depth", "evidence_artifact_ids"]},
            {"op": "propose_status_transition", "fields": ["target_type=claim", "target_id", "status_type=validation", "new_status=challenged", "evidence_artifact_ids"]},
            {"op": "add_debt", "fields": ["debt_id", "owner_type=claim|route|inference", "owner_id", "debt_type=gap|missing_hypothesis|counterexample_risk", "severity=blocking|major|minor", "status=active", "obligation", "source_artifact_ids", "suggested_next_target"]},
        ],
        "literature_researcher": [
            {
                "op": "cache_retrieval_card",
                "fields": [
                    "card_id", "target_id", "exact_statement", "source_identifiers", "source_version", "source_location",
                    "hypotheses", "local_definitions", "missing_hypotheses",
                    "applicability.classification|applicability.family_coverage|applicability.characteristic_and_rank",
                    "applicability.exception_table|applicability.projectivization|applicability.kernel",
                    "applicability.local_implication|applicability.theorem_matching_status",
                ],
                "rule": (
                    "For an exact theorem search, return a certification packet, not a survey: quote the exact theorem interface, translate "
                    "notation, enumerate families/characteristics/ranks/exceptions, check quotient and kernel conventions, and state the one "
                    "local inference enabled. Leave theorem_matching_status unverified when any field is unresolved."
                ),
            },
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=source_adaptation_notes|source_synthesis_report|definition_audit_report", "content", "metadata"]},
            {"op": "add_debt", "fields": ["debt_id", "owner_type", "owner_id", "debt_type=missing_reference|missing_hypothesis|gap", "severity", "status=active", "obligation", "source_artifact_ids", "suggested_next_target"]},
        ],
        "strict_verifier": [
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=verification_report", "content", "metadata.verdict", "metadata.verification_report.checked_items", "metadata.verification_report.critical_errors", "metadata.verification_report.gaps"]},
            {"op": "propose_status_transition", "fields": ["target_type=claim|inference", "target_id", "status_type=validation", "new_status=informally_verified|formally_verified|refuted", "evidence_artifact_ids"]},
            {"op": "add_debt", "fields": ["debt_id", "owner_type=claim|route|inference", "owner_id", "debt_type=gap|missing_reference|missing_hypothesis", "severity=blocking|major|minor", "status=active", "obligation", "source_artifact_ids", "suggested_next_target"]},
        ],
        "citation_verifier": [
            {"op": "certify_external_citation", "fields": ["card_id", "target_id", "relation_to_target=exact|equivalent|stronger", "implication_verified=true", "hidden_assumptions=false", "checked_items", "summary"]},
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=verification_report", "content", "metadata"]},
            {"op": "add_debt", "fields": ["debt_id", "owner_type", "owner_id", "debt_type=missing_reference|missing_hypothesis", "severity", "status=active", "obligation"]},
        ],
        "counterexample_validator": [
            {
                "op": "attach_artifact",
                "fields": ["artifact_id", "artifact_type=confirmed_counterexample", "content", "metadata.confirmed=true", "metadata.target_claim_id", "metadata.validation_result=confirmed"],
                "rule": "Attach only after independently checking the concrete object, hypotheses, and failed conclusion.",
            },
            {
                "op": "propose_status_transition",
                "fields": ["target_type=claim", "target_id", "status_type=validation", "new_status=refuted", "evidence_artifact_ids=<same-patch confirmed_counterexample id>"],
                "rule": "A fully confirmed declarative counterexample must record refuted in the same patch; do not leave the claim merely challenged.",
            },
            {"op": "add_debt", "fields": ["debt_id", "owner_type=claim", "owner_id", "debt_type=counterexample_validation", "severity=blocking", "status=active", "obligation"], "rule": "Use only when validation remains incomplete; do not attach confirmed_counterexample."},
        ],
        "writer": [
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=final_proof|partial_proof_report|stop_summary_report|proof_compression_report|writer_report", "content", "metadata"]},
            {"op": "update_debt", "fields": ["debt_id", "status=resolved", "resolution_note", "resolution_evidence_artifact_ids"], "rule": "Writing-revision passes only: resolve exactly the open writing debts named in manifest.writing_revision_packet, citing the revised final_proof artifact."},
        ],
        "writing_critic": [
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=writing_review", "content", "metadata.verdict=pass|fail", "metadata.lens", "metadata.artifact_reviewed", "metadata.state_revision_reviewed"], "rule": "writing_review is the only artifact type a writing_critic may attach."},
            {"op": "add_debt", "fields": ["debt_id", "owner_type=artifact", "owner_id=<reviewed final_proof artifact_id>", "debt_type=writing", "severity=blocking|major|minor", "status=active", "obligation='<rule_id>: <finding> (line N)'"]},
            {"op": "update_debt", "fields": ["debt_id", "status", "severity", "suggested_next_target"], "rule": "Only sharpen debts you opened in this same session; never close another critic's or the linter's debts."},
            {"op": "record_run_metrics", "fields": ["run_id", "mode", "target_id", "status"]},
        ],
        "phd_advisor": [
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=advisor_report|advisor_synthesis|route_triage_report|key_failure_analysis|invention_authorization|proof_compression", "content", "metadata.current_best_plan|metadata.recommended_next_action|metadata.next_task_acceptance_criteria|metadata.directed_researcher_mode(online|offline|cas)|metadata.directed_researcher_mode_reason|metadata.directed_researcher_mode_steps(1-3)|metadata.directed_villain_mode(online|offline|cas)|metadata.directed_villain_mode_reason|metadata.directed_villain_mode_steps(1-3)"]},
            {"op": "abandon_route", "fields": ["route_id", "reason", "failure_fingerprint", "evidence_artifact_ids"], "rule": "Use for a globally synthesized route-to-abandon decision; preserve verified facts and explain the replacement bottleneck."},
            {"op": "add_debt", "fields": ["debt_id", "owner_type=claim|route|inference", "owner_id", "debt_type=gap|missing_hypothesis|counterexample_risk", "severity=blocking|major|minor", "status=active", "obligation", "source_artifact_ids", "suggested_next_target"]},
            {"op": "update_debt", "fields": ["debt_id", "status=active|blocked|paused", "resolution_note(optional)", "resolution_evidence_artifact_ids(optional)"], "rule": "Use only to sharpen or pause an existing proof obligation; do not close debts unless evidence already proves the obligation."},
        ],
        "general": [
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type", "content", "metadata(optional)"]},
            {"op": "add_debt", "fields": ["debt_id", "owner_type", "owner_id", "debt_type", "severity", "status=active", "obligation"]},
        ],
    }
    if action.get("closure_pipeline_required"):
        common["closure_pipeline_rule"] = (
            "Do not open a route or repeat the full proof. Work only closure_debt_id, supersede canonical_proof_artifact_id with one "
            "changed section, and repair the existing inference for verification."
        )
    if action.get("paper_audit_document_review_required"):
        contracts["strict_verifier"] = [
            {
                "op": "attach_artifact",
                "fields": [
                    "artifact_id",
                    "artifact_type=verification_report",
                    "content=<complete source-located document review>",
                    "metadata.paper_audit_document_review=true",
                    "metadata.audit_subject_artifact_id",
                    "metadata.verdict=verified|major_gaps|likely_false|not_verified",
                    "metadata.verification_report.summary",
                    "metadata.verification_report.checked_items",
                    "metadata.verification_report.critical_errors",
                    "metadata.verification_report.gaps",
                    "metadata.verification_report.blocking_gap",
                ],
                "rule": "Attach exactly one whole-document strict report; do not add graph operations, debts, or repairs.",
            }
        ]
    if action.get("paper_audit_document_integration_required"):
        contracts["integration_verifier"] = [
            {
                "op": "attach_artifact",
                "fields": [
                    "artifact_id",
                    "artifact_type=integration_report",
                    "content=<complete dependency-closure review>",
                    "metadata.paper_audit_document_integration=true",
                    "metadata.strict_report_artifact_id",
                    "metadata.integrates=true|false",
                    "metadata.outcome=integrates|does_not_integrate",
                    "metadata.missing",
                ],
                "rule": "Attach exactly one integration report; do not transition lifecycle, add debts, or repair the proof.",
            }
        ]
    if action.get("paper_audit_referee_report_required"):
        contracts["writer"] = [
            {
                "op": "attach_artifact",
                "fields": [
                    "artifact_id",
                    "artifact_type=referee_report",
                    "content=<complete final referee report>",
                    "metadata.paper_audit_referee_report=true",
                    "metadata.strict_report_artifact_id",
                    "metadata.integration_report_artifact_id",
                    "metadata.source_artifact_ids",
                ],
                "rule": "Attach exactly one verifier-only referee report with no proposed repairs or other operations.",
            }
        ]
    if mode == "write" and action.get("external_writing_revision"):
        document_format = str(action.get("document_format") or "md")
        contracts["writer"] = [
            {
                "op": "attach_artifact",
                "fields": [
                    "artifact_id",
                    "artifact_type=revision_document",
                    f"path=<staging .{document_format} file under <state_dir>/artifacts/staging/>",
                    "content=<COMPLETE revised source> (fallback only when path is not used)",
                    f"metadata.document_format={document_format}",
                    "metadata.revision_of_artifact_id",
                    "metadata.original_sha256",
                    "metadata.revision_mode=true",
                ],
                "rule": (
                    "Attach exactly one complete revision_document in the original source format. Preserve the "
                    "original_sha256 lineage and do not attach a diff, proof artifact, or converted format."
                ),
            },
            {
                "op": "update_debt",
                "fields": ["debt_id", "status=resolved", "resolution_note", "resolution_evidence_artifact_ids"],
                "rule": "Resolve exactly the open writing debts named in manifest.writing_revision_packet.",
            },
            {"op": "record_run_metrics", "fields": ["run_id", "mode", "target_id", "status"]},
        ]
    elif mode == "write" and (action.get("paper_authoring") or action.get("paper_revision")):
        contracts["writer"] = [
            {
                "op": "attach_artifact",
                "fields": [
                    "artifact_id",
                    "artifact_type=final_paper",
                    "path=<staging .tex file under <state_dir>/artifacts/staging/> (PREFERRED: write the file via shell, omit content)",
                    "content=<COMPLETE standalone LaTeX source> (fallback only when path is not used)",
                    "metadata(optional: certificate_artifact_id, source_artifact_ids)",
                ],
                "rule": (
                    "Attach exactly one final_paper; the document is the entire LaTeX article and must compile with "
                    "pdflatex. Prefer the path-based attach: write the .tex to the staging path via shell, then set "
                    "path with NO content field — this avoids all JSON escaping of LaTeX."
                ),
            },
            {
                "op": "update_debt",
                "fields": ["debt_id", "status=resolved", "resolution_note", "resolution_evidence_artifact_ids"],
                "rule": "Paper-revision passes only: resolve exactly the open writing debts named in manifest.writing_revision_packet, citing the revised final_paper artifact.",
            },
            {"op": "record_run_metrics", "fields": ["run_id", "mode", "target_id", "status"]},
        ]
    if mode == "integrate" and not action.get("paper_audit_document_integration_required"):
        context_role = "integration_verifier"
        contracts["integration_verifier"] = [
            {"op": "attach_artifact", "fields": ["artifact_id", "artifact_type=integration_report", "content", "metadata.integrates", "metadata.root_alignment"]},
            {"op": "propose_status_transition", "fields": ["target_type=claim", "target_id", "status_type=lifecycle", "new_status=integrated", "route_id", "evidence_artifact_ids"]},
            {"op": "add_debt", "fields": ["debt_id", "owner_type", "owner_id", "severity=blocking", "status=active", "obligation"]},
        ]
    return {
        "context_role": context_role,
        "common": common,
        "operation_templates": contracts.get(context_role, contracts["general"]),
        "examples_are_templates_not_required_output": True,
    }


def _cas_asset_meta(path: str) -> tuple[str, str]:
    """Infer (backend label, usage hint) for a CAS/data asset from its extension."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext == "m2":
        return "Macaulay2 (M2)", "Read, load, or adapt this Macaulay2 file and run it via the `M2` command through tool calls."
    if ext == "jl":
        return "Julia", "Read, load, or adapt this Julia script and run it via the `julia` command through tool calls (e.g. `julia <file>` or `julia -e ...`)."
    if ext in {"jsonl", "ndjson", "json", "csv", "tsv", "parquet"}:
        return "dataset", (
            "Reference dataset: query and filter it with tool calls (jq, julia, python, or grep) to find or check examples. "
            "It may be very large, so do NOT load the whole file into context — filter to the records you need (e.g. by "
            "rank/size, or by the palindromic/unimodal/log-concave flags)."
        )
    if ext in {"sage", "sagews"}:
        return "SageMath", "Read or run this SageMath file via the `sage` command through tool calls."
    if ext == "py":
        return "Python", "Read or run this Python helper via the `python3` command through tool calls."
    return "CAS asset", "Read, load, or adapt this file and run it via the relevant tool (M2, julia, sage, python) through tool calls."


def _cas_tooling_card() -> Dict[str, Any]:
    """Surface approved CAS/data assets (Macaulay2, Julia, datasets) as tool resources.

    Reads ``ALBILICH_CAS_ASSETS``: a newline-separated list of entries, each
    ``path`` or ``path::description``. Newline-separated (not os.pathsep) because
    paths/descriptions may contain ':'. Each path is named explicitly so the
    agent may use it through tool calls even when its directory is excluded by
    the default local search policy. The backend/usage is inferred per file
    (.m2 -> Macaulay2, .jl -> Julia, .jsonl/.csv -> queryable dataset).
    """
    raw = os.environ.get("ALBILICH_CAS_ASSETS", "").strip()
    if not raw:
        return {}
    assets: list[Dict[str, str]] = []
    backends: list[str] = []
    for entry in raw.splitlines():
        entry = entry.strip()
        if not entry:
            continue
        path, _, description = entry.partition("::")
        path = path.strip()
        if not path:
            continue
        backend, usage = _cas_asset_meta(path)
        if backend not in backends:
            backends.append(backend)
        assets.append(
            {
                "path": path,
                "backend": backend,
                "description": description.strip() or "approved CAS/data asset",
                "usage": usage,
            }
        )
    if not assets:
        return {}
    return {
        "backends": backends,
        "assets": assets,
        "policy": (
            "These CAS/data assets are approved tool resources for this run. You may read, query, and execute them via "
            "tool calls (M2 for Macaulay2 .m2, julia for Julia .jl, jq/julia/python for datasets) for bounded examples, "
            "normal forms, h-vector/Hilbert-function checks, Gorenstein/palindromicity checks, and counterexample or "
            "pattern search, even though their directory is otherwise excluded by local_search_policy. Filter large "
            "datasets rather than loading them whole. Treat any output as evidence or a checked finite computation, not "
            "a proof by itself, and record it in a cas_experiment_report."
        ),
    }


def _cas_trigger_policy(
    action: Optional[Mapping[str, Any]],
    cas_tooling: Optional[Mapping[str, Any]],
    *,
    central_obstruction: Mapping[str, Any],
) -> Dict[str, Any]:
    action = action or {}
    if not (
        action.get("cas_check_recommended")
        or action.get("counterexample_search_required")
        or action.get("bridge_lemma_workbench_required")
        or str(action.get("research_attack_stage") or "") in {"counterexample", "construction"}
    ):
        return {}
    assets = list((cas_tooling or {}).get("assets", []))
    triggers = [
        "a proposed construction lemma has small finite/toy instances",
        "a route obstruction can be stress-tested in examples",
        "a candidate counterexample has finite data to validate",
    ]
    if central_obstruction:
        triggers.insert(0, "the promoted central obstruction has toy cases or boundary cases worth checking")
    return {
        "policy": "cas-trigger-policy",
        "recommended": True,
        "assets_available": bool(assets),
        "asset_paths": [str(asset.get("path") or "") for asset in assets if asset.get("path")],
        "triggers": triggers,
        "boundedness_rule": "Run the smallest examples that can change the next mathematical decision; do not perform open-ended enumeration.",
        "report_rule": (
            "If a computation matters, attach cas_experiment_report with backend, exact code/query, finite scope, output summary, "
            "and proof relevance. CAS evidence is not a theorem proof unless the finite scope is exhaustive and justified."
        ),
    }


def _negative_result_ledger(
    state: Mapping[str, Any],
    *,
    target_id: str,
    route_id: str,
    action: Optional[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    if not action or not (
        action.get("negative_result_ledger_required")
        or action.get("bridge_lemma_workbench_required")
        or action.get("obstruction_route_conversion_required")
        or action.get("route_triage_required")
        or action.get("conceptual_invariant_discovery_required")
        or action.get("canonical_full_proof_reconstruction_required")
    ):
        return []
    wanted_types = {
        "route_obstruction",
        "construction_failure",
        "key_failure_analysis",
        "failed_decomposition_plan",
        "research_diagnostic",
        "candidate_counterexample",
        "cas_experiment_report",
    }
    rows: list[Dict[str, Any]] = []
    for artifact in state.get("artifacts", []):
        if str(artifact.get("artifact_type") or "") not in wanted_types:
            continue
        metadata = _json_object(artifact.get("metadata_json"))
        action_fields = {
            "lesson",
            "do_not_retry",
            "ruled_out",
            "rules_out",
            "failed_method",
            "attempted_method",
            "route_decision",
            "recommended_next_action",
            "next_decisive_action",
            "narrowed_obligation",
            "failure_fingerprint",
            "obstruction_type",
        }
        if str(artifact.get("artifact_type") or "") in {"research_diagnostic", "cas_experiment_report"} and not any(
            metadata.get(field) for field in action_fields
        ):
            continue
        artifact_target = str(metadata.get("target_id") or "root")
        artifact_route = str(metadata.get("route_id") or "")
        if artifact_target not in {target_id, "root"} and artifact_route != route_id:
            continue
        rows.append(
            {
                "artifact_id": str(artifact.get("artifact_id") or ""),
                "artifact_type": str(artifact.get("artifact_type") or ""),
                "producer_role": str(artifact.get("producer_role") or ""),
                "state_revision": artifact.get("state_revision", ""),
                "content_summary": _compact_text(str(artifact.get("content_summary") or ""), 280),
                "path": artifact.get("path", ""),
                "route_id": artifact_route,
                "target_id": artifact_target,
                "failure_fingerprint": str(metadata.get("failure_fingerprint") or metadata.get("obstruction_type") or ""),
                "attempted_method": _compact_text(str(metadata.get("attempted_method") or metadata.get("failed_method") or ""), 160),
                "ruled_out": _compact_text(str(metadata.get("ruled_out") or metadata.get("rules_out") or ""), 160),
                "do_not_retry": _compact_text(str(metadata.get("do_not_retry") or ""), 160),
                "lesson": _compact_text(
                    str(
                        metadata.get("lesson")
                        or metadata.get("narrowed_obligation")
                        or metadata.get("next_decisive_action")
                        or metadata.get("route_decision")
                        or metadata.get("recommended_next_action")
                        or metadata.get("summary")
                        or artifact.get("content_summary")
                        or ""
                    ),
                    220,
                ),
            }
        )
    rows.sort(key=lambda row: (int(row.get("state_revision") or 0), row.get("artifact_id", "")), reverse=True)
    # Keep only the three failures that are most likely to change the next
    # mathematical decision in active context.  Full history remains stored.
    return rows[:3]


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


def _proof_architecture_templates(
    root_statement: str,
    *,
    action: Optional[Mapping[str, Any]],
    central_obstruction: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    if not action or not (
        action.get("proof_architecture_templates_required")
        or action.get("bridge_lemma_workbench_required")
        or action.get("global_synthesis_required")
        or action.get("global_obstruction_architecture_required")
    ):
        return []
    text = " ".join(
        [
            root_statement,
            str(action.get("reason") or ""),
            " ".join(str(item) for item in central_obstruction.get("keywords", [])),
            str(central_obstruction.get("obligation") or ""),
        ]
    ).lower()
    templates: list[Dict[str, Any]] = [
        {
            "template_id": "bridge-lemma-workbench",
            "domain": "general",
            "when_to_use": "one central missing theorem or compatibility lemma blocks every route",
            "moves": [
                "state the bridge as a local theorem with exact hypotheses",
                "prove toy cases and boundary cases",
                "find necessary conditions or obstruction examples",
                "split only into sharper sub-bridges with explicit assembly",
                "write acceptance criteria for verifier, librarian, and CAS checks",
            ],
        }
    ]
    if any(term in text for term in ("group", "subgroup", "wreath", "crown", "frattini", "chief factor", "maximal")):
        templates.append(
            {
                "template_id": "finite-group-closure-patterns",
                "domain": "finite_group_theory",
                "when_to_use": "invariable generation, maximal-subgroup, crown, or non-split extension bridges",
                "moves": [
                    "maximal subgroup criterion: disprove generation by finding a common maximal subgroup meeting all chosen classes",
                    "Frattini/crown reduction: separate split, non-split, and crown-power cases",
                    "wreath/product-action stress: check top projections and diagonal/complement collapse",
                    "finite simple overgroup trick: test whether class choices are forced into a known proper overgroup",
                    "free product quotient check: try small p,q,H quotients before claiming a universal construction",
                ],
            }
        )
    if any(term in text for term in ("matroid", "hvector", "h-vector", "ehrhart", "alcoved", "dhr", "msss", "postnikov")):
        templates.append(
            {
                "template_id": "matroid-hvector-bridge-patterns",
                "domain": "matroid_hvector",
                "when_to_use": "DHR/Ehrhart/alcoved or h*-vector bridge lemmas",
                "moves": [
                    "separate convention checks such as P versus -P before using computations",
                    "test uniform and graphic matroid toy cases",
                    "identify denominator degree, top coefficient, and interior-point interpretation separately",
                    "distinguish termwise DHR evidence from a pure common-dimensional complex",
                    "turn method analogies into explicit hypotheses needed by a verifier",
                ],
            }
        )
    return templates


_LOCAL_EVIDENCE_PATH_RE = re.compile(
    r"(?:/[^\s\"'<>]+|(?:agents/generation/(?:downloads|results)/|\.refs/)[^\s\"'<>]+)"
)


def _local_search_policy(
    cas_tooling: Optional[Mapping[str, Any]] = None,
    *,
    selected_artifacts: Optional[Iterable[Mapping[str, Any]]] = None,
    retrieval_cards: Optional[Iterable[Mapping[str, Any]]] = None,
    theorem_library: Optional[Iterable[Mapping[str, Any]]] = None,
    action: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    allowed_paths = _allowed_local_evidence_paths(
        selected_artifacts=selected_artifacts or [],
        retrieval_cards=retrieval_cards or [],
        theorem_library=theorem_library or [],
        cas_tooling=cas_tooling or {},
        action=action or {},
    )
    policy: Dict[str, Any] = {
        "prefer": [
            "manifest proof-state artifact paths",
            "download/source paths explicitly named by the manifest, retrieval cards, theorem-library entries, or current search request",
            "theorem library entries in the manifest",
            ".refs or explicitly named source files",
        ],
        "download_scope_rule": (
            "Treat agents/generation/downloads as a container, not an approved corpus. "
            "Do not recursively search the whole downloads tree. Search/read only problem-relevant "
            "downloaded files or subdirectories explicitly named in the manifest, source cards, "
            "theorem-library entries, manifest.artifacts[].path, or the current search result being evaluated."
        ),
        "allowed_local_evidence_paths": allowed_paths,
        "local_shell_rule": (
            "Shell path searches may inspect only allowed_local_evidence_paths and their children. "
            "Never construct artifact paths from artifact ids, never run `find .` to discover downloads, and never run `find`, `rg`, `grep`, `ls`, or similar broad commands over "
            "agents/generation/downloads unless the command root is one of allowed_local_evidence_paths. "
            "If allowed_local_evidence_paths is empty for downloads, local downloads are not an approved corpus for this task. "
            "Unlisted local evidence paths are tainted and may be rejected even when they belong to this problem's result tree."
        ),
        "exclude_by_default": [
            "agents/generation/results/**",
            "agents/generation/downloads/** unless explicitly problem-relevant under download_scope_rule",
            "experiment output and raw data directories",
            "logs/**",
            "raw_run_logs/**",
            "older benchmark output packets",
            "agents/generation/phase2/*.py, schemas, and tests when only patch syntax is needed",
        ],
        "allowed_exception": "Read an excluded path only when the manifest explicitly lists it as a current proof-state artifact or the user asked for benchmark provenance/audit.",
    }
    asset_paths = [str(asset.get("path", "")) for asset in (cas_tooling or {}).get("assets", []) if asset.get("path")]
    if asset_paths:
        policy["allowed_cas_assets"] = asset_paths
        policy["allowed_exception"] += (
            " The manifest.cas_tooling assets listed in allowed_cas_assets are explicitly approved tool resources "
            "and may be read or executed even if they fall under an excluded directory."
        )
    return policy


def _allowed_local_evidence_paths(
    *,
    selected_artifacts: Iterable[Mapping[str, Any]],
    retrieval_cards: Iterable[Mapping[str, Any]],
    theorem_library: Iterable[Mapping[str, Any]],
    cas_tooling: Mapping[str, Any],
    action: Mapping[str, Any],
) -> List[str]:
    paths: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text or "*" in text:
            return
        if text not in seen:
            seen.add(text)
            paths.append(text)

    def scan(value: Any) -> None:
        if isinstance(value, Mapping):
            for item in value.values():
                scan(item)
            return
        if isinstance(value, list):
            for item in value:
                scan(item)
            return
        if not isinstance(value, str):
            return
        if "://" in value and "agents/generation/" not in value:
            return
        for match in _LOCAL_EVIDENCE_PATH_RE.findall(value):
            cleaned = match.rstrip(".,;:)]}")
            if cleaned.startswith("/") and "/agents/generation/" not in cleaned:
                continue
            if cleaned:
                add(cleaned)

    for artifact in selected_artifacts:
        add(artifact.get("path"))
    for card in retrieval_cards:
        scan(card.get("source_identifiers"))
        scan(card.get("source_location"))
        scan(card.get("source_version"))
    for entry in theorem_library:
        scan(entry.get("source_identifiers"))
        scan(entry.get("source_location"))
        scan(entry.get("source_version"))
    cas_assets = cas_tooling.get("assets", [])
    if not isinstance(cas_assets, list):
        cas_assets = []
    for asset in cas_assets:
        if isinstance(asset, Mapping):
            add(asset.get("path"))
    for key in ("source_path", "source_file", "reference_path", "local_source_path"):
        if key in action:
            scan(action.get(key))
    return paths[:40]


def _parallel_exchange_card(store: ProofStateStore) -> Dict[str, Any]:
    path = store.state_dir / "parallel_exchange.jsonl"
    return {
        "path": str(path),
        "recent_signals": _read_parallel_exchange(path, limit=12),
        "signal_schema": {
            "created_at": "ISO timestamp",
            "run_id": "current run id when known",
            "actor_role": "researcher|villain|literature_researcher|strict_informal_verifier",
            "mode": "current mode",
            "signal_type": "source_found|obstruction_found|contradiction_alert|useful_lemma|failed_path|request_for_check|route_update",
            "target_id": "claim id",
            "relation": "supports|contradicts|repairs|irrelevant|needs_verifier",
            "summary": "one or two sentences",
            "evidence": "source id, artifact id, theorem location, or computation id",
            "confidence": "low|medium|high",
        },
        "usage": [
            "When you find evidence that could change another parallel branch's work, include it only as top-level parallel_signals in the returned patch.",
            "Do not append to this path directly; the workflow writes accepted patch signals to the exchange and deduplicates them.",
            "Before final patch output, check recent_signals and account for any directly relevant supports or contradictions.",
            "Signals are not proof-state evidence until recorded in an Albilich patch and verified when required.",
        ],
    }


def _read_parallel_exchange(path: Path, *, limit: int) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    signals: list[dict[str, Any]] = []
    for line in lines[-max(limit * 3, limit):]:
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            signals.append(payload)
    return signals[-limit:]


def _claim_card(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "claim_id": row["claim_id"],
        "kind": row["kind"],
        "statement": _compact_text(row["statement"], 900),
        "validation_status": row["validation_status"],
        "lifecycle_status": row["lifecycle_status"],
        "memory_status": claim_memory_status(row),
        "root_impact": row["root_impact"],
        "reduction_depth": row["reduction_depth"],
        "parent_ids": json_loads(row.get("parent_ids_json")),
        "conditions": json_loads(row.get("conditions_json")),
        "evidence_artifact_ids": json_loads(row.get("evidence_artifact_ids_json")),
        "tags": json_loads(row.get("tags_json")),
    }


def _route_card(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "route_id": row["route_id"],
        "conclusion_claim_id": row["conclusion_claim_id"],
        "label": _compact_text(row["label"], 160),
        "strategy": _compact_text(row["strategy"], 900),
        "status": row["status"],
        "memory_status": route_memory_status(row),
        "relation_to_parent": row["relation_to_parent"],
        "assumptions": json_loads(row.get("assumptions_json")),
        "conditions": json_loads(row.get("conditions_json")),
        "evidence_artifact_ids": json_loads(row.get("evidence_artifact_ids_json")),
        "failure_fingerprint": row.get("failure_fingerprint", ""),
    }


def _inference_card(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "inference_id": row["inference_id"],
        "route_id": row["route_id"],
        "conclusion_claim_id": row["conclusion_claim_id"],
        "premise_claim_ids": row.get("premise_claim_ids", []),
        "explanation": _compact_text(row["explanation"], 1_000),
        "conditions": json_loads(row.get("conditions_json")),
        "condition_claim_ids": json_loads(row.get("condition_claim_ids_json")),
        "validation_status": row["validation_status"],
        "memory_status": inference_memory_status(row),
        "evidence_artifact_ids": json_loads(row.get("evidence_artifact_ids_json")),
    }


def _debt_card(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "debt_id": row["debt_id"],
        "owner_type": row["owner_type"],
        "owner_id": row["owner_id"],
        "obligation": _compact_text(row["obligation"], 700),
        "debt_type": row["debt_type"],
        "severity": row["severity"],
        "status": row["status"],
        "memory_status": debt_memory_status(row),
        "repeated_count": row["repeated_count"],
        "source_artifact_ids": json_loads(row.get("source_artifact_ids_json")),
        "suggested_next_target": row["suggested_next_target"],
    }


def _retrieval_card(row: Mapping[str, Any]) -> Dict[str, Any]:
    applicability = json_loads(row.get("applicability_json"), {})
    missing = json_loads(row.get("missing_hypotheses_json"))
    if "theorem_matching_confidence" not in applicability:
        applicability["theorem_matching_confidence"] = theorem_matching_confidence(applicability, missing_hypotheses=missing)
    return {
        "card_id": row["card_id"],
        "exact_statement": _compact_text(row["exact_statement"], 900),
        "memory_status": retrieval_card_memory_status(row),
        "source_identifiers": json_loads(row.get("source_identifiers_json"), {}),
        "source_version": row.get("source_version", "unknown"),
        "hypotheses": json_loads(row.get("hypotheses_json")),
        "local_definitions": json_loads(row.get("local_definitions_json")),
        "applicability": applicability,
        "theorem_matching_confidence": applicability.get("theorem_matching_confidence", {}),
        "missing_hypotheses": missing,
        "source_location": _compact_text(row["source_location"], 240),
    }


def _theorem_library_entry(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "entry_id": row["entry_id"],
        "statement": _compact_text(row["statement"], 900),
        "memory_status": theorem_library_memory_status(row),
        "source_identifiers": json_loads(row.get("source_identifiers_json"), {}),
        "source_version": row.get("source_version", ""),
        "source_location": _compact_text(row.get("source_location", ""), 220),
        "certification_type": row.get("certification_type", ""),
        "relation_to_target": row.get("relation_to_target", ""),
        "evidence_artifact_ids": json_loads(row.get("evidence_artifact_ids_json")),
        "tags": json_loads(row.get("tags_json")),
    }


def _best_route_for_target(routes: Iterable[Mapping[str, Any]], target_id: str) -> Optional[Dict[str, Any]]:
    candidates = [dict(row) for row in routes if row.get("conclusion_claim_id") == target_id and row.get("status") == "active"]
    if not candidates:
        candidates = [dict(row) for row in routes if row.get("conclusion_claim_id") == target_id]
    return sorted(candidates, key=lambda row: (row.get("status") != "active", row.get("route_id", "")))[0] if candidates else None


def _select_claim_ids(state: Mapping[str, Any], target_id: str, route: Optional[Mapping[str, Any]]) -> List[str]:
    claims_by_id = {row["claim_id"]: row for row in state["claims"]}
    selected: list[str] = []

    def add(claim_id: str) -> None:
        if claim_id in claims_by_id and claim_id not in selected:
            selected.append(claim_id)

    add("root")
    add(target_id)

    current_id = target_id
    seen = {current_id}
    for _ in range(6):
        row = claims_by_id.get(current_id)
        if not row:
            break
        parent_ids = json_loads(row.get("parent_ids_json"))
        if not parent_ids:
            break
        parent_id = str(parent_ids[0])
        if parent_id in seen:
            break
        add(parent_id)
        seen.add(parent_id)
        current_id = parent_id

    route_id = route.get("route_id") if route else ""
    for inf in state["inferences"]:
        if route_id and inf["route_id"] != route_id:
            continue
        add(inf["conclusion_claim_id"])
        for premise_id in inf.get("premise_claim_ids", []):
            add(premise_id)

    for debt in state["debts"]:
        if debt.get("status") != "active":
            continue
        owner_id = str(debt.get("owner_id") or "")
        target = str(debt.get("suggested_next_target") or owner_id)
        if owner_id in selected or target in selected or root_distance_for_claim_id(state, target) <= 5:
            add(owner_id)
            add(target)

    for claim_id in sorted(frontier_claim_ids(state), key=lambda cid: (root_distance_for_claim_id(state, cid), cid)):
        add(claim_id)

    for claim in sorted(
        state["claims"],
        key=lambda c: (
            root_distance_for_claim_id(state, c["claim_id"]),
            -float(c.get("root_impact", 0)),
            int(c.get("reduction_depth", 99)),
            c["claim_id"],
        ),
    ):
        if len(selected) >= 14:
            break
        add(claim["claim_id"])
    return selected[:14]


def _select_inferences(
    state: Mapping[str, Any],
    claim_ids: List[str],
    route: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    route_id = route.get("route_id") if route else ""
    selected = set(claim_ids)
    rows = [
        row for row in state["inferences"]
        if (route_id and row["route_id"] == route_id)
        or row["conclusion_claim_id"] in selected
        or any(premise_id in selected for premise_id in row.get("premise_claim_ids", []))
    ]
    rows.sort(key=lambda row: (row["route_id"] != route_id, row["validation_status"] in {"informally_verified", "formally_verified"}, row["inference_id"]))
    return [_inference_card(row) for row in rows[:12]]


def _select_debts(
    state: Mapping[str, Any],
    claim_ids: List[str],
    route: Optional[Mapping[str, Any]],
    *,
    inference_ids: Optional[set[str]] = None,
    preferred_debt_ids: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    owners = set(claim_ids)
    if route:
        owners.add(route["route_id"])
    owners.update(inference_id for inference_id in (inference_ids or set()) if inference_id)
    rows = [
        row for row in state["debts"]
        if row["status"] == "active"
        and (row["owner_id"] in owners or row.get("suggested_next_target") in owners)
    ]
    preferred = preferred_debt_ids or set()
    rows.sort(
        key=lambda row: (
            str(row.get("debt_id") or "") not in preferred,
            row["severity"] != "blocking",
            -int(row.get("repeated_count", 0)),
            row["debt_id"],
        )
    )
    return [_debt_card(row) for row in rows[:12]]


def _branch_packet_debt_ids(action: Optional[Mapping[str, Any]]) -> set[str]:
    branch_packet = (action or {}).get("branch_packet")
    if not isinstance(branch_packet, Mapping):
        return set()
    return {
        str(debt_id)
        for key in ("debt_ids", "incoming_debt_ids")
        for debt_id in branch_packet.get(key) or []
        if str(debt_id)
    }


def _branch_relevant_claim_ids(
    state: Mapping[str, Any],
    target_id: str,
    selected_route: Optional[Mapping[str, Any]],
    inferences: List[Mapping[str, Any]],
    debts: List[Mapping[str, Any]],
) -> set[str]:
    """Claims structurally tied to the current branch (target, its ancestor
    chain, route inferences, and selected debts).

    Evidence artifacts are pulled only from these claims: context-filler claims
    keep their compact cards, but their artifacts stay out of the branch
    manifest (memory hygiene: branch-local memory vs global memory)."""
    relevant = {"root", target_id}
    claims_by_id = {row["claim_id"]: row for row in state["claims"]}
    current_id = target_id
    for _ in range(6):
        row = claims_by_id.get(current_id)
        if not row:
            break
        parent_ids = json_loads(row.get("parent_ids_json"))
        if not parent_ids:
            break
        parent_id = str(parent_ids[0])
        if parent_id in relevant:
            break
        relevant.add(parent_id)
        current_id = parent_id
    if selected_route:
        relevant.add(str(selected_route.get("conclusion_claim_id") or ""))
    for inf in inferences:
        relevant.add(str(inf.get("conclusion_claim_id") or ""))
        relevant.update(str(item) for item in inf.get("premise_claim_ids", []) or [])
        condition_ids = inf.get("condition_claim_ids")
        if condition_ids is None:
            condition_ids = json_loads(inf.get("condition_claim_ids_json"))
        relevant.update(str(item) for item in condition_ids or [])
    for debt in debts:
        relevant.add(str(debt.get("owner_id") or ""))
        relevant.add(str(debt.get("suggested_next_target") or ""))
    relevant.discard("")
    return relevant


def _is_paper_audit_strict_packet(
    state: Mapping[str, Any],
    action: Optional[Mapping[str, Any]],
) -> bool:
    """Whether this action is the bounded strict-verifier stage of an audit.

    The ordinary strict verifier can legitimately see route-local obstruction
    evidence.  A paper audit is narrower: the object being adjudicated is the
    researcher's transcription of one author statement/proof segment.
    """
    if not paper_audit_context_card(state) or not action:
        return False
    if action.get("paper_audit_document_review_required"):
        return True
    return bool(
        str(action.get("mode") or "") == "prove"
        and str(action.get("route_id") or "")
        and (
            action.get("strict_verifier_no_fresh_evidence")
            or action.get("verify_ready_route_policy")
            or str(action.get("strict_verifier_scope") or "") == "single_route_verification_packet"
        )
    )


def _paper_audit_packet_owner_ids(
    *,
    target_id: str,
    selected_route: Optional[Mapping[str, Any]],
    selected_inferences: Iterable[Mapping[str, Any]],
) -> set[str]:
    owner_ids = {str(target_id or "")}
    if selected_route:
        owner_ids.add(str(selected_route.get("route_id") or ""))
        owner_ids.add(str(selected_route.get("conclusion_claim_id") or ""))
    for inference in selected_inferences:
        owner_ids.add(str(inference.get("inference_id") or ""))
        owner_ids.add(str(inference.get("conclusion_claim_id") or ""))
        owner_ids.update(_string_list(inference.get("premise_claim_ids")))
        owner_ids.update(_string_list(inference.get("condition_claim_ids")))
    owner_ids.discard("")
    return owner_ids


def _integration_route_inference_ids(
    selected_route: Optional[Mapping[str, Any]],
    selected_inferences: Iterable[Mapping[str, Any]],
) -> set[str]:
    route_id = str(selected_route.get("route_id") or "") if selected_route else ""
    if not route_id:
        return set()
    return {
        str(inference.get("inference_id") or "")
        for inference in selected_inferences
        if str(inference.get("route_id") or "") == route_id
        and str(inference.get("inference_id") or "")
    }


def _integration_packet_owner_ids(
    *,
    target_id: str,
    selected_route: Optional[Mapping[str, Any]],
    selected_inferences: Iterable[Mapping[str, Any]],
) -> set[str]:
    owner_ids = {str(target_id or "")}
    if selected_route:
        owner_ids.add(str(selected_route.get("route_id") or ""))
    owner_ids.update(
        _integration_route_inference_ids(selected_route, selected_inferences)
    )
    owner_ids.discard("")
    return owner_ids


def _scope_integration_proof_spine(
    proof_spine: Mapping[str, Any],
    selected_debts: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Remove debt prompts the selected integration route cannot resolve."""
    scoped = dict(proof_spine)
    allowed_debt_ids = {
        str(debt.get("debt_id") or "")
        for debt in selected_debts
        if str(debt.get("debt_id") or "")
    }
    bottlenecks = proof_spine.get("current_bottlenecks")
    if isinstance(bottlenecks, list):
        scoped["current_bottlenecks"] = [
            debt
            for debt in bottlenecks
            if isinstance(debt, Mapping)
            and str(debt.get("debt_id") or "") in allowed_debt_ids
        ]
    return scoped


def _paper_audit_packet_debts(
    debts: Iterable[Mapping[str, Any]],
    *,
    target_id: str,
    selected_route: Optional[Mapping[str, Any]],
    selected_inferences: Iterable[Mapping[str, Any]],
) -> List[Mapping[str, Any]]:
    owner_ids = _paper_audit_packet_owner_ids(
        target_id=target_id,
        selected_route=selected_route,
        selected_inferences=selected_inferences,
    )
    return [debt for debt in debts if str(debt.get("owner_id") or "") in owner_ids]


def _paper_audit_packet_artifacts(
    state: Mapping[str, Any],
    selected_artifacts: Iterable[Mapping[str, Any]],
    *,
    action: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep only the exact researcher dossier and immutable audit subject."""
    action = action or {}
    allowed_ids = set(_string_list(action.get("verifier_evidence_artifact_ids")))
    audit_card = paper_audit_context_card(state)
    subject_id = str(audit_card.get("audit_subject_artifact_id") or "")
    if subject_id:
        allowed_ids.add(subject_id)

    cards = [dict(card) for card in selected_artifacts if str(card.get("artifact_id") or "") in allowed_ids]
    present = {str(card.get("artifact_id") or "") for card in cards}
    if subject_id and subject_id not in present:
        subject = next(
            (row for row in state.get("artifacts", []) if str(row.get("artifact_id") or "") == subject_id),
            None,
        )
        if subject is not None and not artifact_is_raw_log(subject):
            current_revision = int(state.get("problem_state", {}).get("current_revision") or 0)
            cards.append(
                {
                    "artifact_id": subject["artifact_id"],
                    "artifact_type": subject["artifact_type"],
                    "producer_role": subject["producer_role"],
                    "state_revision": subject["state_revision"],
                    "memory_status": artifact_memory_status(subject, current_revision=current_revision),
                    "content_summary": _compact_text(subject["content_summary"], 700),
                    "sha256": subject["sha256"],
                    "path": subject["path"],
                }
            )
    return cards


def _apply_paper_audit_strict_packet_isolation(manifest: Dict[str, Any]) -> None:
    """Remove sibling audit evidence from a strict local verification lens."""
    action = manifest.get("workflow_action")
    action = action if isinstance(action, Mapping) else {}
    exact_evidence_ids = set(_string_list(action.get("verifier_evidence_artifact_ids")))
    paper_audit = manifest.get("paper_audit")
    paper_audit = paper_audit if isinstance(paper_audit, Mapping) else {}
    subject_id = str(paper_audit.get("audit_subject_artifact_id") or "")
    allowed_manifest_ids = set(exact_evidence_ids)
    if subject_id:
        allowed_manifest_ids.add(subject_id)

    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, list):
        manifest["artifacts"] = [
            artifact
            for artifact in artifacts
            if isinstance(artifact, Mapping)
            and str(artifact.get("artifact_id") or "") in allowed_manifest_ids
        ]

    relevant_claim_ids = {str(manifest.get("target_id") or "")}
    routes = manifest.get("routes")
    if isinstance(routes, list):
        for route in routes:
            if isinstance(route, Mapping):
                relevant_claim_ids.add(str(route.get("conclusion_claim_id") or ""))
    for inference in manifest.get("inferences", []):
        if not isinstance(inference, Mapping):
            continue
        relevant_claim_ids.add(str(inference.get("conclusion_claim_id") or ""))
        relevant_claim_ids.update(_string_list(inference.get("premise_claim_ids")))
        relevant_claim_ids.update(_string_list(inference.get("condition_claim_ids")))
    relevant_claim_ids.discard("")
    claims = manifest.get("claims")
    if isinstance(claims, list):
        manifest["claims"] = [
            claim
            for claim in claims
            if isinstance(claim, Mapping) and str(claim.get("claim_id") or "") in relevant_claim_ids
        ]

    relevant_owner_ids = set(relevant_claim_ids)
    relevant_owner_ids.add(str(manifest.get("route_id") or ""))
    for inference in manifest.get("inferences", []):
        if not isinstance(inference, Mapping):
            continue
        relevant_owner_ids.add(str(inference.get("inference_id") or ""))
    relevant_owner_ids.discard("")

    debts = manifest.get("debts")
    if isinstance(debts, list):
        manifest["debts"] = [
            debt
            for debt in debts
            if isinstance(debt, Mapping) and str(debt.get("owner_id") or "") in relevant_owner_ids
        ]

    packet = manifest.get("verification_packet")
    if isinstance(packet, dict):
        packet["active_debts"] = [
            debt
            for debt in packet.get("active_debts", [])
            if isinstance(debt, Mapping) and str(debt.get("owner_id") or "") in relevant_owner_ids
        ]
        packet["proof_artifacts"] = [
            artifact
            for artifact in packet.get("proof_artifacts", [])
            if isinstance(artifact, Mapping)
            and str(artifact.get("artifact_id") or "") in exact_evidence_ids
        ]

    parallel_exchange = manifest.get("parallel_exchange")
    if isinstance(parallel_exchange, dict):
        parallel_exchange["recent_signals"] = [
            signal
            for signal in parallel_exchange.get("recent_signals", [])
            if isinstance(signal, Mapping) and str(signal.get("target_id") or "") in relevant_claim_ids
        ]

    proof_spine = manifest.get("proof_spine")
    if isinstance(proof_spine, dict):
        proof_spine["current_bottlenecks"] = [
            debt
            for debt in proof_spine.get("current_bottlenecks", [])
            if isinstance(debt, Mapping) and str(debt.get("owner_id") or "") in relevant_owner_ids
        ]

    graph_focus = manifest.get("graph_focus")
    if isinstance(graph_focus, dict):
        graph_focus["frontier_claim_ids"] = [
            claim_id for claim_id in graph_focus.get("frontier_claim_ids", []) if str(claim_id) in relevant_claim_ids
        ]
        pressure = graph_focus.get("frontier_pressure")
        if isinstance(pressure, dict):
            pressure["sample_claim_ids"] = [
                claim_id for claim_id in pressure.get("sample_claim_ids", []) if str(claim_id) in relevant_claim_ids
            ]

    manifest["retrieval_cards"] = []
    manifest["theorem_library"] = []
    manifest.pop("negative_result_ledger", None)
    policy = manifest.get("local_search_policy")
    if isinstance(policy, dict):
        allowed_paths = [
            str(artifact.get("path") or "")
            for artifact in manifest.get("artifacts", [])
            if isinstance(artifact, Mapping) and str(artifact.get("path") or "")
        ]
        subject_path = str(paper_audit.get("audit_subject_path") or "")
        if subject_path and subject_path not in allowed_paths:
            allowed_paths.append(subject_path)
        policy["allowed_local_evidence_paths"] = allowed_paths
    manifest["instructions"].append(
        "Paper-audit strict-packet isolation is active: only the immutable audit_subject and the exact "
        "workflow_action.verifier_evidence_artifact_ids are readable evidence; sibling findings, proposed repairs, "
        "retrieval cards, theorem-library entries, and unrelated debts are excluded from this adjudication."
    )


def _apply_paper_audit_verification_only_isolation(manifest: Dict[str, Any]) -> None:
    """Expose only the immutable submission and prior verifier-stage reports."""
    action = manifest.get("workflow_action")
    action = action if isinstance(action, Mapping) else {}
    allowed_ids = set(_string_list(action.get("paper_audit_source_artifact_ids")))
    paper_audit = manifest.get("paper_audit")
    paper_audit = paper_audit if isinstance(paper_audit, Mapping) else {}
    subject_id = str(paper_audit.get("audit_subject_artifact_id") or "")
    if subject_id:
        allowed_ids.add(subject_id)

    manifest["artifacts"] = [
        artifact
        for artifact in manifest.get("artifacts", [])
        if isinstance(artifact, Mapping)
        and str(artifact.get("artifact_id") or "") in allowed_ids
    ]
    manifest["claims"] = [
        claim
        for claim in manifest.get("claims", [])
        if isinstance(claim, Mapping) and str(claim.get("claim_id") or "") == "root"
    ]
    manifest["routes"] = []
    manifest["inferences"] = []
    manifest["debts"] = []
    manifest["retrieval_cards"] = []
    manifest["theorem_library"] = []
    manifest.pop("negative_result_ledger", None)
    manifest.pop("researcher_packet", None)
    manifest.pop("verification_packet", None)
    manifest.pop("branch_summaries", None)

    parallel_exchange = manifest.get("parallel_exchange")
    if isinstance(parallel_exchange, dict):
        parallel_exchange["recent_signals"] = []

    policy = manifest.get("local_search_policy")
    if isinstance(policy, dict):
        policy["allowed_local_evidence_paths"] = [
            str(artifact.get("path") or "")
            for artifact in manifest["artifacts"]
            if str(artifact.get("path") or "")
        ]
    manifest["instructions"].append(
        "Verifier-only paper-audit isolation is active: the audit_subject and the exact prior-stage reports "
        "listed in workflow_action.paper_audit_source_artifact_ids are the complete evidence boundary. Do not "
        "read or use researcher, villain, advisor, literature, proposed-repair, prior-run, errata, or correction "
        "material. Produce only the report artifact required by workflow_action."
    )


def _select_artifacts(
    state: Mapping[str, Any],
    claim_ids: List[str],
    selected_route: Optional[Mapping[str, Any]],
    inferences: List[Mapping[str, Any]],
    debts: List[Mapping[str, Any]],
    *,
    target_id: str = "root",
    action: Optional[Mapping[str, Any]] = None,
    include_stop_writer_artifacts: bool = False,
) -> List[Dict[str, Any]]:
    wanted: list[str] = []
    wanted_seen: set[str] = set()
    artifacts_by_id = {str(art["artifact_id"]): art for art in state["artifacts"]}

    def add_wanted(ids: Iterable[Any], *, newest_first: bool = False) -> None:
        raw_ids = list(ids)
        if newest_first:
            raw_ids.sort(
                key=lambda raw_id: (
                    int(artifacts_by_id.get(str(raw_id or ""), {}).get("state_revision") or 0),
                    str(artifacts_by_id.get(str(raw_id or ""), {}).get("created_at") or ""),
                ),
                reverse=True,
            )
        for raw_id in raw_ids:
            artifact_id = str(raw_id or "").strip()
            if artifact_id and artifact_id not in wanted_seen:
                wanted_seen.add(artifact_id)
                wanted.append(artifact_id)

    if action:
        add_wanted(_action_artifact_ids(action))
    add_wanted(_root_synthesis_context_artifact_ids(state, action))
    if selected_route:
        add_wanted(selected_route.get("evidence_artifact_ids", []))
    for inf in inferences:
        # Evidence ids are stored as a deterministic set-union and therefore
        # commonly arrive alphabetized.  A fixed packet cap must not turn that
        # storage order into a preference for the oldest proof artifacts.
        add_wanted(inf.get("evidence_artifact_ids", []), newest_first=True)
    for debt in debts:
        add_wanted(debt.get("source_artifact_ids", []))
    branch_claim_ids = _branch_relevant_claim_ids(state, target_id, selected_route, inferences, debts)
    for claim in state["claims"]:
        if claim["claim_id"] in claim_ids and claim["claim_id"] in branch_claim_ids:
            add_wanted(json_loads(claim.get("evidence_artifact_ids_json")))
    cards = []
    seen: set[str] = set()
    current_revision = int(state.get("problem_state", {}).get("current_revision") or 0)

    def add_card(art: Mapping[str, Any]) -> None:
        artifact_id = str(art["artifact_id"])
        if artifact_id in seen:
            return
        seen.add(artifact_id)
        # Raw session logs/transcripts are run evidence, never role context.
        if artifact_is_raw_log(art):
            return
        cards.append({
            "artifact_id": art["artifact_id"],
            "artifact_type": art["artifact_type"],
            "producer_role": art["producer_role"],
            "state_revision": art["state_revision"],
            "memory_status": artifact_memory_status(art, current_revision=current_revision),
            "content_summary": _compact_text(art["content_summary"], 700),
            "sha256": art["sha256"],
            "path": art["path"],
        })

    for artifact_id in wanted:
        art = artifacts_by_id.get(artifact_id)
        if not art:
            continue
        add_card(art)
        if len(cards) >= 12:
            break
    if include_stop_writer_artifacts and len(cards) < 18:
        useful_types = {
            "final_proof",
            "verified_blueprint",
            "proof_compression_report",
            "verification_report",
            "integration_report",
            "writer_report",
            "partial_proof_report",
            "stop_summary_report",
            "source_synthesis_report",
            "definition_audit_report",
            "route_triage_report",
            "decomposition_plan",
            "failed_decomposition_plan",
            "key_failure_analysis",
            "research_diagnostic",
            "cas_experiment_report",
        }
        recent = [art for art in state["artifacts"] if art.get("artifact_type") in useful_types]
        recent.sort(key=lambda art: (int(art.get("state_revision", 0)), art.get("created_at", "")), reverse=True)
        for art in recent:
            add_card(art)
            if len(cards) >= 18:
                break
    return cards


def _action_artifact_ids(action: Mapping[str, Any]) -> List[str]:
    artifact_ids: list[str] = []
    seen: set[str] = set()

    def add(raw_id: Any) -> None:
        artifact_id = str(raw_id or "").strip()
        if artifact_id and artifact_id not in seen:
            seen.add(artifact_id)
            artifact_ids.append(artifact_id)

    def visit(key: str, value: Any) -> None:
        if key.endswith("artifact_id"):
            add(value)
            return
        if key.endswith("artifact_ids"):
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    add(item)
            else:
                add(value)
            return
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                visit(str(child_key), child_value)
            return
        if isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    for child_key, child_value in item.items():
                        visit(str(child_key), child_value)

    for key, value in action.items():
        visit(str(key), value)
    return artifact_ids


def _verification_packet(
    state: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    selected_route: Optional[Mapping[str, Any]],
    selected_claim_ids: List[str],
    selected_inferences: List[Mapping[str, Any]],
    selected_debts: List[Mapping[str, Any]],
    action: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    if not action or action.get("mode") != "prove" or not selected_route or action.get("citation_certification_required"):
        return {}
    route_id = str(selected_route.get("route_id") or "")
    route_inferences = [dict(row) for row in selected_inferences if row.get("route_id") == route_id]
    claim_by_id = {row["claim_id"]: row for row in state["claims"]}
    premise_ids: list[str] = []
    for inference in route_inferences:
        for premise_id in inference.get("premise_claim_ids", []):
            if premise_id not in premise_ids:
                premise_ids.append(premise_id)
    artifact_ids = _selected_artifact_ids_for_packet(
        state,
        selected_claim_ids=selected_claim_ids,
        selected_route=selected_route,
        selected_inferences=selected_inferences,
        selected_debts=selected_debts,
        action=action,
        include_recent_source_adaptations=True,
    )
    return {
        "packet_type": "local_proof_verification",
        "required": bool(action.get("proof_repair_verification_required") or route_inferences),
        "target_claim": _claim_packet_card(claim_by_id.get(str(target.get("claim_id"))) or target),
        "selected_route": dict(selected_route),
        "route_inferences": route_inferences,
        "premise_claims": [
            _claim_packet_card(claim_by_id[premise_id])
            for premise_id in premise_ids
            if premise_id in claim_by_id
        ],
        "active_debts": [dict(row) for row in selected_debts],
        "proof_artifacts": _artifact_content_cards(
            state,
            artifact_ids,
            max_chars=VERIFICATION_PACKET_MAX_ARTIFACT_CHARS,
            preferred_types=FULL_PROOF_ARTIFACT_TYPES | SOURCE_ADAPTATION_ARTIFACT_TYPES | DECOMPOSITION_ARTIFACT_TYPES | CAS_ARTIFACT_TYPES | {"verification_report"},
        ),
        "verifier_rule": (
            "Check only the exact target, route, premises, inferences, debts, and proof artifact contents included in this bounded packet. "
            "For decomposition parent checks, validate the subgoal tree/DAG structurally: no missing branches, no cyclic dependencies, "
            "case splits exhaustive, cited theorem hypotheses accounted for, and the assembly implication proves the parent. "
            "If essential artifact content is missing or truncated, reject with a precise debt requesting that content instead of reconstructing it from summaries."
            " The strict verifier must not run CAS, create new proof evidence, attach proof dossiers, or search for a new proof; it may only"
            " attach verification_report artifacts, propose allowed verification/refutation status changes, and add precise gap debts."
        ),
    }


def _researcher_packet(
    state: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    selected_route: Optional[Mapping[str, Any]],
    selected_claim_ids: List[str],
    selected_inferences: List[Mapping[str, Any]],
    selected_debts: List[Mapping[str, Any]],
    action: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    if not action or action.get("mode") not in {"prove", "reduce", "weaken", "strengthen", "refute"}:
        return {}
    if action.get("mode") == "prove" and (
        action.get("route_id")
        or action.get("citation_certification_required")
        or action.get("citation_triage_required")
    ):
        return {}
    claim_by_id = {row["claim_id"]: row for row in state["claims"]}
    artifact_ids = _selected_artifact_ids_for_packet(
        state,
        selected_claim_ids=selected_claim_ids,
        selected_route=selected_route,
        selected_inferences=selected_inferences,
        selected_debts=selected_debts,
        action=action,
        include_recent_source_adaptations=True,
    )
    proof_dossier_artifacts = _artifact_content_cards(
        state,
        artifact_ids,
        max_chars=RESEARCHER_PACKET_MAX_ARTIFACT_CHARS,
        preferred_types=FULL_PROOF_ARTIFACT_TYPES | RESEARCH_HANDOFF_ARTIFACT_TYPES,
    )
    central_obstruction = dict(action.get("central_obstruction") or {})
    selected_route_id = str(selected_route.get("route_id") if selected_route else action.get("route_id") or "")
    negative_ledger = _negative_result_ledger(
        state,
        target_id=str(target.get("claim_id") or action.get("target_id") or "root"),
        route_id=selected_route_id,
        action=action,
    )
    proof_templates = _proof_architecture_templates(
        state["problem_state"].get("root_statement", ""),
        action=action,
        central_obstruction=central_obstruction,
    )
    packet_role = "villain" if action.get("mode") == "refute" else "researcher"
    packet_cas_enabled = session_cas_enabled(packet_role, action)
    cas_policy = (
        _cas_trigger_policy(action, _cas_tooling_card(), central_obstruction=central_obstruction)
        if packet_cas_enabled
        else {}
    )
    return {
        "packet_type": "researcher_workbench",
        "role_contract": "villain_refutation_researcher" if action.get("mode") == "refute" else "working_mathematician",
        "researcher_mode_policy": _researcher_mode_policy_card(action, packet_role=packet_role),
        "target_claim": _claim_packet_card(claim_by_id.get(str(target.get("claim_id"))) or target),
        "selected_route": dict(selected_route) if selected_route else {},
        "current_inferences": [dict(row) for row in selected_inferences],
        "active_debts": [dict(row) for row in selected_debts],
        "protected_debt_ids": sorted(_branch_packet_debt_ids(action)),
        "proof_dossier_artifacts": proof_dossier_artifacts,
        "source_adaptation_artifacts": [
            _artifact_reference_card(row)
            for row in proof_dossier_artifacts
            if row.get("artifact_type") in SOURCE_ADAPTATION_ARTIFACT_TYPES
        ],
        "decomposition_artifacts": [
            _artifact_reference_card(row)
            for row in proof_dossier_artifacts
            if row.get("artifact_type") in DECOMPOSITION_ARTIFACT_TYPES
        ],
        "cas_experiment_artifacts": [
            _artifact_reference_card(row)
            for row in proof_dossier_artifacts
            if row.get("artifact_type") in CAS_ARTIFACT_TYPES
        ],
        "central_obstruction": central_obstruction,
        "negative_result_ledger": negative_ledger,
        "proof_architecture_templates": proof_templates,
        "proof_spine": build_proof_spine(state, action=action, target_id=str(target.get("claim_id") or action.get("target_id") or "root")),
        "cas_trigger_policy": cas_policy,
        "workbench_acceptance_criteria": list(central_obstruction.get("acceptance_criteria", [])),
        "paperwork_budget_policy": {
            "policy": "math-first-compact-reporting",
            "primary_token_rule": (
                "Spend most tokens on the actual mathematical attack: proof attempt, route repair, bottleneck lemma, citation adaptation, "
                "bounded counterexample/CAS check, or source deduction."
            ),
            "compact_by_default": not bool(action.get("proof_architecture_required")),
            "creative_attack_override": (
                "When creative_proof_attack_required=true, spend the pass on proof invention and synthesis. Management-only notes, broad "
                "inventories, and route status summaries are disallowed unless they are embedded in a proof_dossier/proof_blueprint that "
                "also contains a real full-proof attempt, obstruction inversion, or narrower theorem-level bottleneck."
            ),
            "ordinary_reporting_cap": (
                "For ordinary researcher passes, keep management metadata to at most five short fields. Do not write broad narrative reports "
                "when a proof_dossier, route repair, narrowed debt, or source/CAS check would move the proof."
            ),
            "artifact_roi_required": True,
            "artifact_roi_triggers": [
                "creates verifier-ready route or inference",
                "repairs, blocks, abandons, or sharply redirects a route",
                "narrows the bottleneck to a smaller named obligation",
                "closes or sharpens an active proof debt",
                "turns literature/CAS output into a local proof component or a precise next check",
                "records a failed method that should not be retried",
            ],
            "diagnostic_rule": (
                "Attach research_diagnostic or research_notebook only when it changes future behavior; include attempted_method, why_failed, "
                "ruled_out or do_not_retry when relevant, and next_decisive_action."
            ),
            "architecture_exception": (
                "Proof-architecture pressure may use a slightly richer proof_blueprint/research_notebook, but it must still name one current "
                "best plan, one bottleneck, and one next decisive mathematical move."
            ),
        },
        "staged_attack_policy": {
            "research_attack_stage": action.get("research_attack_stage", "ordinary"),
            "creative_proof_attack_required": bool(action.get("creative_proof_attack_required")),
            "wild_mathematician_mode": bool(action.get("wild_mathematician_mode")),
            "direct_solve_required": bool(action.get("direct_solve_required")),
            "proof_construction_required": bool(action.get("proof_construction_required")),
            "deep_research_required": bool(action.get("deep_research_required")),
            "long_mathematical_session_required": bool(action.get("long_mathematical_session_required")),
            "research_philosophy": action.get("research_philosophy", ""),
            "research_cycle": action.get("research_cycle", {}),
            "bridge_lemma_workbench_required": bool(action.get("bridge_lemma_workbench_required")),
            "closure_pressure_required": bool(action.get("closure_pressure_required")),
            **(
                {
                    "closure_pipeline_required": True,
                    "closure_debt_id": action.get("closure_debt_id", ""),
                    "canonical_proof_update_required": bool(action.get("canonical_proof_update_required")),
                    "canonical_proof_artifact_id": action.get("canonical_proof_artifact_id", ""),
                    "closure_pipeline_rule": (
                        "Freeze accepted premises; work only closure_debt_id; supersede the canonical proof with one changed section; "
                        "repair the existing inference."
                    ),
                }
                if action.get("closure_pipeline_required")
                else {}
            ),
            **(
                {
                    "canonical_full_proof_reconstruction_required": True,
                    "canonical_full_proof_reconstruction_rule": (
                        "Draft the entire shortest proof, quote every unsupported sentence, isolate one decisive theorem, and background all other branches."
                    ),
                }
                if action.get("canonical_full_proof_reconstruction_required")
                else {}
            ),
            **(
                {
                    "conceptual_invariant_discovery_required": True,
                    "conceptual_invariant_trigger": action.get("conceptual_invariant_trigger", {}),
                    "conceptual_invariant_rule": (
                        "Seek one object or invariant that subsumes multiple local lemmas and survives a concrete falsification test."
                    ),
                }
                if action.get("conceptual_invariant_discovery_required")
                else {}
            ),
            **(
                {
                    "counterexample_probe_required": True,
                    "counterexample_probe_contract": action.get("counterexample_probe_contract", {}),
                }
                if action.get("counterexample_probe_required")
                else {}
            ),
            **(
                {
                    "source_certification_packet_required": True,
                    "source_certification_packet_rule": (
                        "Record theorem number, exact statement, notation, hypotheses, coverage, exceptions, projectivization, kernel, "
                        "and local implication."
                    ),
                }
                if action.get("source_certification_packet_required")
                else {}
            ),
            **(
                {
                    "experiment_decision_gate_required": True,
                    "experiment_decision_gate_rule": (
                        "Run CAS only after naming competing hypotheses, a discriminating bounded experiment, and how each outcome "
                        "changes the next action."
                    ),
                }
                if action.get("experiment_decision_gate_required")
                else {}
            ),
            "bottleneck_lock_required": bool(action.get("bottleneck_lock_required")),
            "bottleneck_lock_signal": action.get("bottleneck_lock_signal", {}),
            "diagnostic_cooldown_active": bool(action.get("diagnostic_cooldown_active")),
            "diagnostic_artifact_ids": action.get("diagnostic_artifact_ids", []),
            "sublemma_extraction_required": bool(action.get("sublemma_extraction_required")),
            "side_branch_roi_cap_active": bool(action.get("side_branch_roi_cap_active")),
            "main_trunk_compute_reserved": bool(action.get("main_trunk_compute_reserved")),
            "forbidden_outputs": action.get("forbidden_outputs", []),
            "cas_check_recommended": bool(action.get("cas_check_recommended")),
            "proof_spine_mode_required": bool(action.get("proof_spine_mode_required")),
            "proof_spine_min_lemmas": action.get("proof_spine_min_lemmas", 0),
            "proof_spine_max_lemmas": action.get("proof_spine_max_lemmas", 0),
            "proof_spine_manager_required": bool(action.get("proof_spine_manager_required")),
            "active_proof_spine_required": bool(action.get("active_proof_spine_required")),
            "route_conversion_attempt_required": bool(action.get("route_conversion_attempt_required")),
            "duplicate_math_guard_required": bool(action.get("duplicate_math_guard_required")),
            "villain_obstruction_to_lemma_required": bool(action.get("villain_obstruction_to_lemma_required")),
            "near_miss_memory_required": bool(action.get("near_miss_memory_required")),
            "hard_theorem_attack_contract": action.get("hard_theorem_attack_contract", {}),
            "research_synthesis_required": bool(action.get("research_synthesis_required")),
            "approach_portfolio_synthesis_required": bool(action.get("approach_portfolio_synthesis_required")),
            "global_synthesis_required": bool(action.get("global_synthesis_required")),
            "theorem_building_synthesis_required": bool(action.get("theorem_building_synthesis_required")),
            "decisive_theorem_test_required": bool(action.get("decisive_theorem_test_required")),
            "decisive_theorem_test": action.get("decisive_theorem_test", {}),
            "proof_architecture_required": bool(action.get("proof_architecture_required")),
            "proof_pressure_scheduler_required": bool(action.get("proof_pressure_scheduler_required")),
            "route_contract_required": bool(action.get("route_contract_required")),
            "obligation_reduction_required": bool(action.get("obligation_reduction_required")),
            "speculative_proof_required": bool(action.get("speculative_proof_required")),
            "obstruction_inversion_required": bool(action.get("obstruction_inversion_required")),
            "analogy_pass_required": bool(action.get("analogy_pass_required")),
            "failure_autopsy_required": bool(action.get("failure_autopsy_required")),
            "bottleneck_ownership_required": bool(action.get("bottleneck_ownership_required")),
            "paperwork_throttle_required": bool(action.get("paperwork_throttle_required")),
            "repair_loop_required": bool(action.get("repair_loop_required")),
            "current_best_plan_required": bool(action.get("current_best_plan_required")),
            "dead_route_suppression_required": bool(action.get("dead_route_suppression_required")),
            "proof_architecture_signal": action.get("proof_architecture_signal", {}),
            "creative_attack_signal": action.get("creative_attack_signal", {}),
            "proof_route_conversion_required": bool(action.get("proof_route_conversion_required")),
            "proof_candidate_artifact_id": action.get("proof_candidate_artifact_id", ""),
            "no_result_search_synthesis_required": bool(action.get("no_result_search_synthesis_required")),
            "obstruction_route_conversion_required": bool(action.get("obstruction_route_conversion_required")),
            "global_obstruction_architecture_required": bool(action.get("global_obstruction_architecture_required")),
            "no_content_research_guard": bool(action.get("no_content_research_guard")),
            "parallel_wave_summary": action.get("parallel_wave_summary", {}),
            "no_result_search_cluster": action.get("no_result_search_cluster", {}),
            "obstruction_cluster": action.get("obstruction_cluster", {}),
            "no_content_research_cluster": action.get("no_content_research_cluster", {}),
            "direct_solve_first_rule": (
                "For direct-solve actions, first try to prove or refute the target itself in local notation: direct consequences, "
                "known theorem pattern matches, examples/counterexamples, and source handoffs. Do not reduce merely because reduction is "
                "available; reduce or decompose only after the direct attempt identifies a natural proof architecture, missing theorem, "
                "case split, construction, filtration, or obstruction."
            ),
            "proof_construction_rule": (
                "When proof_construction_required=true, treat the internal reduce mode as routed proof construction: write or repair the "
                "selected route's actual local proof, use citations responsibly when they shorten the proof, and emit verifier-ready "
                "inference evidence or a precise obstruction. Do not propose another decomposition unless the proof attempt identifies "
                "a mathematically necessary split."
            ),
            "synthesis_rule": (
                "When research_synthesis_required=true, act as the mathematical owner of the target: compare recent proof, literature, "
                "counterexample, CAS, and decomposition branches; identify what changed; kill or merge routes; then choose one next "
                "serious mathematical move. Do not emit another small isolated claim unless it changes the root route."
            ),
            "obstruction_conversion_rule": (
                "When obstruction_route_conversion_required=true, classify the obstruction or candidate counterexample as "
                "route-killing, route-repairing, missing-hypothesis, generalized-construction-needed, or validator-needed; then convert "
                "it into one route decision rather than ignoring it or merely restating it."
            ),
            "global_obstruction_architecture_rule": (
                "When global_obstruction_architecture_required=true, seriously consider that the original root may be false. Build a "
                "global obstruction architecture: identify unavoidable host/composition-factor/quotient constraints, turn obstruction "
                "lemmas into claims/routes for verification, and either produce a validator-ready concrete counterexample path or a "
                "verified negative/necessary-condition route. Do not keep repairing a positive construction route by default."
            ),
            "proof_route_conversion_rule": (
                "When proof_route_conversion_required=true, do not start a new proof search. Read proof_candidate_artifact_id, decide "
                "whether it contains a local verifier-ready argument, and create exactly one active sufficient route plus one untested "
                "or plausible route inference citing that artifact as evidence. If the artifact is not route-ready, attach one short "
                "research_diagnostic and add one precise proof debt instead. This pass exists to make strict verification schedulable."
            ),
            "global_synthesis_rule": (
                "When global_synthesis_required=true, treat the current artifacts as a near-proof portfolio. Do not request another broad "
                "literature search merely because no exact theorem was found. Try to assemble the missing bridge theorem from the endpoint "
                "obstructions, source handoffs, and local lemmas; write the proof attempt as a paper-like proof_dossier with explicit "
                "hypotheses, citations used, exact remaining gap if any, and a route/inference if it becomes verifier-ready."
            ),
            "creative_proof_attack_rule": (
                "When creative_proof_attack_required=true, work like a bold research mathematician under verifier discipline. Own one bottleneck "
                "for the whole pass. First draft the most plausible full proof, explicitly marking gaps; then invert the central obstruction "
                "by asking what construction, theorem, or hypothesis would evade it; then generate one or two speculative bridge theorems with "
                "exact hypotheses and known failure modes; then decide whether the result is a verifier-ready route, a narrower theorem-level "
                "debt, or a route-killing obstruction. Use an analogy from a nearby method only if it creates a concrete lemma or construction. "
                "Do not spend the pass on inventories, generic summaries, or administrative decomposition."
            ),
            "proof_architecture_rule": (
                "When proof_architecture_required=true, act as the research owner for the target. Produce a proof_dossier, proof_blueprint, "
                "or research_notebook with metadata current_best_plan, route_contracts, bottleneck_obligation, repair_attempt, "
                "speculative_proof_attempt, remaining_gaps, and next_decisive_action. Keep blocked or stalled routes paused unless the "
                "output gives a concrete repair contract."
            ),
            "obligation_reduction_rule": (
                "When obligation_reduction_required=true, reduce the current proof search to one smallest named mathematical obligation "
                "whose proof, refutation, or exact citation would most change the route scoreboard. Do not emit a long undifferentiated gap list."
            ),
            "bridge_lemma_workbench_rule": (
                "When bridge_lemma_workbench_required=true, stop broad synthesis. Promote the central_obstruction to a named local bridge "
                "lemma, attack it constructively, test toy and obstruction cases, consult negative_result_ledger before reusing ideas, and "
                "finish with a proof_dossier, route_obstruction, construction_failure, narrower sub-bridge, or verifier-ready inference. "
                "If the result is not verifier-ready, include update_debt for the current central_debt_id or add one precise blocking "
                "debt for the narrowed obligation so the next workbench does not repeat the same broad bridge pass."
            ),
            "bottleneck_lock_rule": (
                "When bottleneck_lock_required=true, diagnostic cooldown is active. Do not make a broad research_diagnostic, route inventory, "
                "or management-only notebook the main output. Own the named bottleneck for the whole pass: prove it, refute it, find an exact "
                "citation with checked hypotheses, or replace it with one strictly narrower theorem-level debt. If the obligation is too large, "
                "extract one verifier-checkable sublemma plus an assembly argument that explains how it would unlock the parent route."
            ),
            "proof_spine_rule": (
                "When proof_spine_mode_required=true, compress the work into a short proof spine rather than a branch inventory: list 3-6 named "
                "lemmas or steps, dependency arrows, the assembly implication to the target/root, and exactly one remaining theorem-level gap if "
                "the proof is not closed. If any step is already a local proof, create or repair a route/inference for strict verification."
            ),
            "duplicate_math_guard_rule": (
                "When duplicate_math_guard_required=true, compare the intended theorem against recent proof artifacts and debts. Do not restate "
                "an already accepted obstruction or lemma unless you explicitly use it to prove the newest child obligation."
            ),
            "near_miss_memory_rule": (
                "When near_miss_memory_required=true, record the strongest failed route in one sentence and ensure the new output either removes "
                "that exact obstruction, converts it into a lemma, or abandons the route with a precise reason."
            ),
            "villain_obstruction_to_lemma_rule": (
                "When villain_obstruction_to_lemma_required=true, treat counterexample and construction-failure artifacts as possible positive "
                "lemmas: state whether the obstruction can be promoted into a route obstruction, necessary condition, or proof step."
            ),
            "side_branch_roi_rule": (
                "When side_branch_roi_cap_active=true, side branches are allowed only if they can produce a concrete proof dossier, obstruction, "
                "counterexample, exact citation, bounded CAS result, or verifier-ready inference. Do not spend the pass expanding formal state "
                "around low-impact branches."
            ),
            "decisive_theorem_test_rule": (
                "When decisive_theorem_test_required=true, work only the theorem in decisive_theorem_test: state it exactly, then prove it, "
                "refute it, find a precise citation with checked hypotheses, or replace it with one strictly narrower theorem-level debt. "
                "Do not write a broad survey or split the problem into bookkeeping subgoals."
            ),
            "counterexample_search_required": bool(action.get("counterexample_search_required")),
            "fast_pass_stop_conditions": [
                "verifier-ready proof candidate",
                "precise literature_search_request",
                "named citation with checked local deduction",
                "candidate counterexample or obstruction",
                "natural decomposition_plan with assembly argument",
            ],
            "parallel_portfolio": (
                "When a literature scout or main researcher is running in parallel, keep this pass independent: proof/citation work "
                "should not wait for counterexample work, and counterexample work should report only serious obstructions."
            ),
        },
        "citation_policy": {
            "citations_are_allowed": True,
            "responsible_citation_rule": (
                "Use citations when they save time or avoid rediscovering known mathematics. Record source location, theorem number or "
                "precise page/section, hypotheses, definition translation, and the local deduction to the target."
            ),
            "verifier_expectation": (
                "A verifier may pass a properly cited theorem by checking the citation metadata, hypotheses, definitions, and local implication; "
                "the researcher need not reprove external theorems already cited precisely."
            ),
        },
        "research_diagnostic_gate": (
            "Decomposition is allowed as a natural proof architecture move, not only after a stall, but direct-solve actions must first "
            "record the direct attempt, pattern match, source handoff, example, or obstruction that makes the split mathematically natural. "
            "Use it for natural_case_split, approach_portfolio, "
            "standard_reduction, parallel_ingredients, construction_and_checks, citation_adaptation, induction_or_filtration, or "
            "equivalence_reformulation. A decomposition_plan must give precise subgoals, dependency_edges, any parallelizable_groups, "
            "case_exhaustiveness when relevant, and an assembly_argument explaining why the branches imply the parent. Do not attach another "
            "research_diagnostic unless it creates/repairs a route, kills or pauses a route, narrows a debt to a smaller named obligation, "
            "or records a failed method that future roles should not retry."
        ),
        "expected_output": (
            "Prefer a proof_dossier/proof_blueprint plus verifier-ready inferences. Add research_notebook only when attack branches, failed "
            "lemmas, citations considered, or CAS checks should change later choices; include the artifact ROI in metadata. Add "
            "source_adaptation_notes when literature is used, and cas_experiment_report when computation changes the next mathematical step. "
            "When decomposition is natural, attach a decomposition_plan with only the fields needed to assemble the parent: plan_kind, trigger, "
            "subgoal_claim_ids, dependency_edges, assembly_argument, and acceptance_criteria. If a plan failed, write a concise "
            "failed_decomposition_plan and let the advisor regulator classify the failure before the next generation. For creative proof "
            "attacks, the preferred successful output is one proof_dossier/proof_blueprint containing a full-proof attempt with gaps, "
            "obstruction inversion, speculative bridge theorem(s), failure autopsy, and one next verifier/librarian/CAS-ready action."
            " For bottleneck-lock actions, the preferred output is a proof_dossier/proof_blueprint, route_obstruction, construction_failure, "
            "exact citation handoff, or one narrower theorem-level debt with acceptance criteria and a parent assembly argument."
        ),
    }


WRITING_PACKET_MAX_ARTIFACT_CHARS = 200_000
# Three independent lenses are required; legacy lenses stay supported so old
# data and resumed prompts remain coherent.
WRITING_CRITIC_LENSES = SUPPORTED_WRITING_REVIEW_LENSES
# Documents the writing layer understands: internal certificate/paper plus an
# externally ingested source-preserving revision document.
WRITING_GATE_DOCUMENT_TYPES = ("final_proof", "final_paper", REVISION_DOCUMENT_ARTIFACT_TYPE)


def _latest_writer_document_row(
    state: Mapping[str, Any],
    artifact_id: str = "",
    *,
    preferred_types: tuple[str, ...] = ("final_proof",),
) -> Optional[Mapping[str, Any]]:
    """The writing-gate document to operate on: the row with ``artifact_id``
    when given (any gate document type), else the newest row of the first
    ``preferred_types`` entry that exists, else the newest gate document."""
    rows = [
        row
        for row in state.get("artifacts", [])
        if str(row.get("artifact_type") or "") in WRITING_GATE_DOCUMENT_TYPES
    ]
    if artifact_id:
        for row in rows:
            if str(row.get("artifact_id") or "") == artifact_id:
                return row
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    for artifact_type in preferred_types:
        for row in rows:
            if str(row.get("artifact_type") or "") == artifact_type:
                return row
    return rows[0] if rows else None


def _latest_final_proof_row(state: Mapping[str, Any], artifact_id: str = "") -> Optional[Mapping[str, Any]]:
    rows = [row for row in state.get("artifacts", []) if str(row.get("artifact_type") or "") == "final_proof"]
    if artifact_id:
        for row in rows:
            if str(row.get("artifact_id") or "") == artifact_id:
                return row
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows[0] if rows else None


def _open_writing_debt_cards(state: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """One card per ACTIVE writing debt — every debt, uncapped, mirroring the
    scheduler's debt cards: ``location``/``required_fix`` are split out so the
    300-char obligation compaction can never truncate the fix instruction."""
    cards: List[Dict[str, Any]] = []
    for debt in state.get("debts", []):
        if str(debt.get("status") or "") != "active":
            continue
        if str(debt.get("debt_type") or "") != "writing":
            continue
        obligation = str(debt.get("obligation") or "")
        defect = obligation.split(WRITING_REQUIRED_FIX_MARKER, 1)[0]
        cards.append(
            {
                "debt_id": str(debt.get("debt_id") or ""),
                "owner_id": str(debt.get("owner_id") or ""),
                "severity": str(debt.get("severity") or ""),
                "obligation": _compact_text(defect, 300),
                "location": writing_obligation_location(obligation),
                "required_fix": _compact_text(writing_required_fix_for_obligation(obligation), 300),
            }
        )
    return cards


def _claim_route_summary(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Compact claim/route cards: the skeptical_editor's framing evidence and
    the paper-authoring packet's map of what was actually established."""
    return {
        "claims": [
            {
                "claim_id": str(claim.get("claim_id") or ""),
                "statement": _compact_text(str(claim.get("statement") or ""), 280),
                "validation_status": str(claim.get("validation_status") or ""),
                "lifecycle_status": str(claim.get("lifecycle_status") or ""),
            }
            for claim in state.get("claims", [])[:24]
        ],
        "routes": [
            {
                "route_id": str(route.get("route_id") or ""),
                "label": _compact_text(str(route.get("label") or ""), 160),
                "status": str(route.get("status") or ""),
                "conclusion_claim_id": str(route.get("conclusion_claim_id") or ""),
            }
            for route in state.get("routes", [])[:12]
        ],
    }


def _writing_review_packet(
    state: Mapping[str, Any],
    *,
    action: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Lens-isolated packet for a writing_critic session.

    All lenses receive the reviewed document's content (a final_paper once one
    exists; the packet's ``final_proof`` key is the legacy container name for
    whatever document is under review — see ``reviewed_artifact_type``);
    everything else is gated by the lens (see _apply_writing_lens_isolation for
    what is removed from the rest of the manifest). For a final_paper review the
    provenance_auditor additionally receives the certificate content, so it can
    audit the paper's mathematics against the certificate and its bibliography
    against the literature ledger.
    """
    action = action or {}
    if str(action.get("mode") or "") != "review_writing":
        return {}
    lens = str(action.get("critic_lens") or "") or "confused_reader"
    if action.get("external_writing_review"):
        preferred = (REVISION_DOCUMENT_ARTIFACT_TYPE, "final_paper", "final_proof")
    elif action.get("paper_review"):
        preferred = ("final_paper", "final_proof", REVISION_DOCUMENT_ARTIFACT_TYPE)
    else:
        preferred = ("final_proof", "final_paper", REVISION_DOCUMENT_ARTIFACT_TYPE)
    row = _latest_writer_document_row(state, str(action.get("artifact_reviewed") or ""), preferred_types=preferred)
    if row is None:
        return {}
    reviewed_type = str(row.get("artifact_type") or "final_proof")
    content = _read_artifact_content(str(row.get("path") or ""), WRITING_PACKET_MAX_ARTIFACT_CHARS)
    packet: Dict[str, Any] = {
        "packet_type": "writing_review",
        "lens": lens,
        "artifact_reviewed": str(row.get("artifact_id") or ""),
        "reviewed_artifact_type": reviewed_type,
        "document_format": revision_document_format(row) if reviewed_type == REVISION_DOCUMENT_ARTIFACT_TYPE else (
            "tex" if reviewed_type == "final_paper" else "md"
        ),
        "state_revision_reviewed": int(action.get("state_revision_reviewed") or row.get("state_revision") or 0),
        "final_proof": {
            "artifact_id": str(row.get("artifact_id") or ""),
            "artifact_type": reviewed_type,
            "path": str(row.get("path") or ""),
            "content": content,
        },
        "open_writing_debts": _open_writing_debt_cards(state),
    }
    if lens in {"skeptical_editor", "introduction_editor", "editor"} and not action.get(
        "external_writing_review"
    ):
        packet["claim_route_summary"] = _claim_route_summary(state)
    if lens == "provenance_auditor":
        packet["artifact_ledger"] = [
            {
                "artifact_id": str(artifact.get("artifact_id") or ""),
                "artifact_type": str(artifact.get("artifact_type") or ""),
                "producer_role": str(artifact.get("producer_role") or ""),
                "content_summary": _compact_text(str(artifact.get("content_summary") or ""), 200),
            }
            for artifact in state.get("artifacts", [])[-48:]
        ]
        if reviewed_type == "final_paper":
            certificate = _latest_final_proof_row(state)
            if certificate is not None:
                packet["certificate"] = {
                    "artifact_id": str(certificate.get("artifact_id") or ""),
                    "path": str(certificate.get("path") or ""),
                    "content": _read_artifact_content(
                        str(certificate.get("path") or ""), WRITING_PACKET_MAX_ARTIFACT_CHARS
                    ),
                }
    return packet


def _permit_writing_review_artifact_path(manifest: Dict[str, Any], packet: Mapping[str, Any]) -> None:
    """Keep the reviewed paper's own path in the lens's allowed evidence list.

    Lens isolation strips every proof-state artifact path from the manifest, but
    the final_proof under review IS the critic's evidence: a critic that shell-reads
    the paper it was asked to review must not be scored as an evidence-boundary
    violation. Only the exact reviewed file is permitted (it is a file, so nothing
    is a child of it), so isolation of all other proof-state is preserved.
    """
    final_proof = packet.get("final_proof")
    path = str(final_proof.get("path") or "").strip() if isinstance(final_proof, Mapping) else ""
    if not path:
        return
    policy = manifest.get("local_search_policy")
    if not isinstance(policy, dict):
        return
    allowed = policy.get("allowed_local_evidence_paths")
    allowed = list(allowed) if isinstance(allowed, list) else []
    if path not in allowed:
        allowed.append(path)
    policy["allowed_local_evidence_paths"] = allowed


def _permit_writer_paper_staging_dir(manifest: Dict[str, Any], store: ProofStateStore) -> str:
    """Permit the writer's LaTeX staging directory in the evidence boundary.

    Path-based final_paper attaches (patches.WRITER_PATH_ATTACH_ARTIFACT_TYPES)
    have the writer author the .tex as a real file under
    state_dir/artifacts/staging/ and attach by path, so the writer's shell must
    be allowed to create and read files there; without this entry the
    evidence-boundary scorer would flag the staging path as an unlisted local
    evidence access. Mirrors _permit_writing_review_artifact_path above.
    """
    staging_dir = str(store.state_dir / "artifacts" / "staging")
    policy = manifest.get("local_search_policy")
    if isinstance(policy, dict):
        allowed = policy.get("allowed_local_evidence_paths")
        allowed = list(allowed) if isinstance(allowed, list) else []
        if staging_dir not in allowed:
            allowed.append(staging_dir)
        policy["allowed_local_evidence_paths"] = allowed
    return staging_dir


def _apply_writing_lens_isolation(manifest: Dict[str, Any], lens: str) -> None:
    """Context isolation for writing critics.

    The terminology editor and whole-paper editor keep the citation ledger
    (retrieval cards + theorem library) so they can check literature usage.
    Legacy lenses: confused_reader sees only the
    paper; skeptical_editor additionally keeps the packet's brief claim/route
    summary; provenance_auditor keeps the citation/artifact ledger. Everything
    below is proof-state context that must not leak into the review.
    """
    manifest["claims"] = []
    manifest["routes"] = []
    manifest["inferences"] = []
    manifest["debts"] = []
    manifest["artifacts"] = []
    manifest["graph_focus"] = {}
    manifest["proof_spine"] = {}
    manifest["research_task"] = {}
    manifest["parallel_exchange"] = {"policy": "disabled for writing-review lens isolation"}
    for key in (
        "verification_packet",
        "researcher_packet",
        "negative_result_ledger",
        "proof_architecture_templates",
        "cas_trigger_policy",
        "cas_tooling",
        "central_obstruction",
        "researcher_mode_state",
    ):
        manifest.pop(key, None)
    if lens not in ("terminology_editor", "editor", "provenance_auditor"):
        manifest["retrieval_cards"] = []
        manifest["theorem_library"] = []


def _writing_revision_packet(
    state: Mapping[str, Any],
    *,
    action: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Workbench for a diff-minimal writer revision pass: the current gated
    document (final_proof certificate or final_paper LaTeX article, see
    ``revised_artifact_type``; ``final_proof`` is the legacy container key)
    plus exactly the open writing debts to discharge."""
    action = action or {}
    if str(action.get("mode") or "") != "write" or not action.get("writing_revision"):
        return {}
    if action.get("external_writing_revision"):
        preferred = (REVISION_DOCUMENT_ARTIFACT_TYPE, "final_paper", "final_proof")
    elif action.get("paper_revision"):
        preferred = ("final_paper", "final_proof", REVISION_DOCUMENT_ARTIFACT_TYPE)
    else:
        preferred = ("final_proof", "final_paper", REVISION_DOCUMENT_ARTIFACT_TYPE)
    row = _latest_writer_document_row(state, str(action.get("revision_of_artifact_id") or ""), preferred_types=preferred)
    if row is None:
        return {}
    revised_type = str(row.get("artifact_type") or "final_proof")
    debts = action.get("writing_debts")
    debt_cards = [dict(debt) for debt in debts if isinstance(debt, Mapping)] if isinstance(debts, list) else []
    if not debt_cards:
        debt_cards = _open_writing_debt_cards(state)
    metadata = _json_object(row.get("metadata_json"))
    if revised_type == REVISION_DOCUMENT_ARTIFACT_TYPE:
        document_format = revision_document_format(row)
        revision_contract = (
            "Revise diff-minimally and preserve the author's voice, mathematical claims, notation, bibliography, "
            f"and {document_format} source format. Address exactly the listed writing debts; resolve each via "
            "update_debt naming the new revision_document; attach exactly one COMPLETE revision_document with a "
            "new artifact_id and preserve metadata.original_sha256. Never convert the manuscript into a different "
            "format or present it as mathematically verified."
        )
    elif revised_type == "final_paper":
        revision_contract = (
            "Revise diff-minimally and voice-preservingly; address exactly the listed writing debts; resolve each via "
            "update_debt with a resolution_note and resolution_evidence_artifact_ids naming the revised final_paper; "
            "attach exactly one revised final_paper with a new artifact_id whose content is the COMPLETE revised LaTeX "
            "source (it must still compile standalone with pdflatex); keep the bibliography intact."
        )
    else:
        revision_contract = (
            "Revise diff-minimally and voice-preservingly; address exactly the listed writing debts; resolve each via "
            "update_debt with a resolution_note and resolution_evidence_artifact_ids naming the revised final_proof; "
            "attach exactly one revised final_proof with a new artifact_id; keep the References section intact."
        )
    return {
        "packet_type": "writing_revision",
        "revision_of_artifact_id": str(row.get("artifact_id") or ""),
        "revised_artifact_type": revised_type,
        "document_format": revision_document_format(row) if revised_type == REVISION_DOCUMENT_ARTIFACT_TYPE else (
            "tex" if revised_type == "final_paper" else "md"
        ),
        "source_lineage": {
            "original_sha256": str(metadata.get("original_sha256") or ""),
            "revision_number": int(metadata.get("revision_number") or 0),
            "source_file": str(metadata.get("source_file") or ""),
        },
        "final_proof": {
            "artifact_id": str(row.get("artifact_id") or ""),
            "artifact_type": revised_type,
            "path": str(row.get("path") or ""),
            "content": _read_artifact_content(str(row.get("path") or ""), WRITING_PACKET_MAX_ARTIFACT_CHARS),
        },
        "open_writing_debts": debt_cards,
        "revision_contract": revision_contract,
    }


def _writing_paper_packet(
    state: Mapping[str, Any],
    *,
    action: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Workbench for a paper-authoring pass (mode=write + paper_authoring).

    The writer turns the internal certificate into a standalone LaTeX research
    article (artifact_type final_paper) under the paper contract: certificate
    content is the sole source of mathematical truth; the literature block
    (retrieval cards + theorem library, source data included) is the only pool
    of citable works; the claim/route summary maps what was actually
    established at which certification level.
    """
    action = action or {}
    if str(action.get("mode") or "") != "write" or not action.get("paper_authoring"):
        return {}
    certificate = _latest_final_proof_row(state, str(action.get("certificate_artifact_id") or ""))
    if certificate is None:
        return {}
    problem = state.get("problem_state", {})
    literature = {
        "retrieval_cards": [
            {
                "card_id": str(card.get("card_id") or ""),
                "statement": _compact_text(str(card.get("exact_statement") or ""), 600),
                "source_identifiers": json_loads(card.get("source_identifiers_json"), {}),
                "source_location": _compact_text(str(card.get("source_location") or ""), 240),
                "source_version": str(card.get("source_version") or ""),
            }
            for card in state.get("retrieval_cards", [])
        ],
        "theorem_library": [
            {
                "entry_id": str(entry.get("entry_id") or ""),
                "statement": _compact_text(str(entry.get("statement") or ""), 600),
                "source_identifiers": json_loads(entry.get("source_identifiers_json"), {}),
                "source_location": _compact_text(str(entry.get("source_location") or ""), 220),
                "certification_type": str(entry.get("certification_type") or ""),
            }
            for entry in state.get("theorem_library_entries", [])
        ],
    }
    return {
        "packet_type": "writing_paper",
        "certificate": {
            "artifact_id": str(certificate.get("artifact_id") or ""),
            "path": str(certificate.get("path") or ""),
            "content": _read_artifact_content(str(certificate.get("path") or ""), WRITING_PACKET_MAX_ARTIFACT_CHARS),
        },
        "root_statement": str(problem.get("root_statement") or ""),
        "claim_route_summary": _claim_route_summary(state),
        "literature": literature,
        "paper_contract": PAPER_CONTRACT,
    }


def _selected_artifact_ids_for_packet(
    state: Mapping[str, Any],
    *,
    selected_claim_ids: List[str],
    selected_route: Optional[Mapping[str, Any]],
    selected_inferences: List[Mapping[str, Any]],
    selected_debts: List[Mapping[str, Any]],
    action: Optional[Mapping[str, Any]] = None,
    include_recent_source_adaptations: bool,
) -> List[str]:
    claim_ids = set(selected_claim_ids)
    wanted: list[str] = []
    seen: set[str] = set()

    def add_many(ids: Iterable[Any]) -> None:
        for artifact_id in ids:
            text = str(artifact_id or "")
            if text and text not in seen:
                seen.add(text)
                wanted.append(text)

    source_artifact_id = str(action.get("source_artifact_id") or "") if action else ""
    if source_artifact_id:
        add_many([source_artifact_id])
        for debt in selected_debts:
            source_ids = debt.get("source_artifact_ids", [])
            if source_artifact_id in {str(item) for item in source_ids if str(item)}:
                add_many(source_ids)

    if action:
        add_many(_action_artifact_ids(action))
    add_many(_root_synthesis_context_artifact_ids(state, action))

    selected_route_id = str(selected_route.get("route_id") or "") if selected_route else ""
    if selected_route:
        add_many(selected_route.get("evidence_artifact_ids", []))
    for inference in selected_inferences:
        if selected_route_id and str(inference.get("route_id") or "") == selected_route_id:
            add_many(inference.get("evidence_artifact_ids", []))

    packet_target_id = str((action or {}).get("target_id") or (selected_claim_ids[1] if len(selected_claim_ids) > 1 else "root"))
    branch_claim_ids = _branch_relevant_claim_ids(state, packet_target_id, selected_route, selected_inferences, selected_debts)
    for claim in state["claims"]:
        if claim["claim_id"] in claim_ids and claim["claim_id"] in branch_claim_ids:
            add_many(json_loads(claim.get("evidence_artifact_ids_json")))
    metadata_linked_route_ids: list[str] = []
    if selected_route:
        metadata_linked_route_ids = _metadata_linked_route_artifact_ids(state, selected_route, selected_inferences)
    for inference in selected_inferences:
        if selected_route_id and str(inference.get("route_id") or "") == selected_route_id:
            continue
        add_many(inference.get("evidence_artifact_ids", []))
    for debt in selected_debts:
        add_many(debt.get("source_artifact_ids", []))
    add_many(metadata_linked_route_ids)
    if include_recent_source_adaptations:
        recent = [row for row in state["artifacts"] if row.get("artifact_type") in RESEARCH_HANDOFF_ARTIFACT_TYPES]
        recent.sort(key=lambda row: (int(row.get("state_revision", 0)), row.get("created_at", "")), reverse=True)
        add_many(row["artifact_id"] for row in recent[:6])
    return wanted


def _root_synthesis_context_artifact_ids(
    state: Mapping[str, Any],
    action: Optional[Mapping[str, Any]],
) -> List[str]:
    if not _needs_root_synthesis_context(action):
        return []
    route_by_id = {
        str(row.get("route_id") or ""): row
        for row in state.get("routes", [])
        if str(row.get("route_id") or "")
    }
    matches: list[Mapping[str, Any]] = []
    for artifact in state.get("artifacts", []):
        if artifact.get("artifact_type") not in ROOT_SYNTHESIS_CONTEXT_ARTIFACT_TYPES:
            continue
        if not _artifact_is_root_adjacent(artifact, route_by_id):
            continue
        matches.append(artifact)
    matches.sort(
        key=lambda row: (
            int(row.get("state_revision", 0)),
            row.get("created_at", ""),
            row.get("artifact_id", ""),
        ),
        reverse=True,
    )
    return [str(row["artifact_id"]) for row in matches[:6] if str(row.get("artifact_id") or "")]


def _needs_root_synthesis_context(action: Optional[Mapping[str, Any]]) -> bool:
    if not action:
        return False
    if str(action.get("target_id") or "") != "root":
        return False
    search_intent = str(action.get("search_intent") or "")
    if search_intent in {
        "executive_advisor_bottleneck_lock",
        "near_solution_spine_synthesis",
        "advisor_evidence_synthesis",
        "global_obstruction_architecture",
        "creative_bridge_attack",
    }:
        return True
    return any(
        bool(action.get(key))
        for key in (
            "near_solution_spine_synthesis_required",
            "global_synthesis_required",
            "research_synthesis_required",
            "theorem_building_synthesis_required",
            "proof_spine_mode_required",
            "bottleneck_lock_required",
            "executive_advisor_lock_required",
            "near_miss_memory_required",
            "global_obstruction_architecture_required",
            "creative_bridge_attack_required",
        )
    )


def _artifact_is_root_adjacent(
    artifact: Mapping[str, Any],
    route_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    metadata = json_loads(artifact.get("metadata_json"), {})
    if str(metadata.get("target_id") or "") == "root":
        return True
    route_id = str(metadata.get("route_id") or metadata.get("blocking_route_id") or "")
    if route_id and str(route_by_id.get(route_id, {}).get("conclusion_claim_id") or "") == "root":
        return True
    artifact_id = str(artifact.get("artifact_id") or "")
    return "_root_" in artifact_id or artifact_id.startswith("root_")


def _metadata_linked_route_artifact_ids(
    state: Mapping[str, Any],
    selected_route: Mapping[str, Any],
    selected_inferences: List[Mapping[str, Any]],
) -> List[str]:
    route_id = str(selected_route.get("route_id") or "")
    if not route_id:
        return []
    inference_ids = {str(row.get("inference_id") or "") for row in selected_inferences}
    route_keys = {"route_id", "route_ids", "supports_route_id", "blocking_route_id"}
    inference_keys = {"inference_id", "inference_ids", "supports_inference_id", "supports_inference_ids"}
    proof_types = FULL_PROOF_ARTIFACT_TYPES | RESEARCH_HANDOFF_ARTIFACT_TYPES | {"verification_report"}
    matches: list[Mapping[str, Any]] = []
    for artifact in state["artifacts"]:
        if artifact.get("artifact_type") not in proof_types:
            continue
        metadata = json_loads(artifact.get("metadata_json"), {})
        if route_id in _metadata_text_values(metadata, route_keys):
            matches.append(artifact)
            continue
        if inference_ids and (_metadata_text_values(metadata, inference_keys) & inference_ids):
            matches.append(artifact)
    matches.sort(key=lambda row: (int(row.get("state_revision", 0)), row.get("created_at", "")), reverse=True)
    return [str(row["artifact_id"]) for row in matches[:6]]


def _metadata_text_values(metadata: Mapping[str, Any], keys: set[str]) -> set[str]:
    values: set[str] = set()
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, list):
            values.update(str(item) for item in value if item)
        elif value:
            values.add(str(value))
    return values


def _artifact_content_cards(
    state: Mapping[str, Any],
    artifact_ids: List[str],
    *,
    max_chars: int,
    preferred_types: set[str],
) -> List[Dict[str, Any]]:
    artifacts_by_id = {str(row["artifact_id"]): row for row in state["artifacts"]}
    order = {artifact_id: index for index, artifact_id in enumerate(artifact_ids)}
    rows = [artifacts_by_id[artifact_id] for artifact_id in artifact_ids if artifact_id in artifacts_by_id]
    # Raw session logs/transcripts never enter role packets.
    rows = [row for row in rows if not artifact_is_raw_log(row)]
    rows.sort(key=lambda row: (0 if row.get("artifact_type") in preferred_types else 1, order.get(str(row["artifact_id"]), 10_000)))
    current_revision = int(state.get("problem_state", {}).get("current_revision") or 0)
    cards: list[Dict[str, Any]] = []
    remaining = max_chars
    for artifact in rows:
        if remaining <= 600:
            break
        content = _read_artifact_content(str(artifact.get("path") or ""), remaining)
        remaining -= len(content)
        cards.append({
            "artifact_id": artifact["artifact_id"],
            "artifact_type": artifact["artifact_type"],
            "producer_role": artifact["producer_role"],
            "state_revision": artifact["state_revision"],
            "memory_status": artifact_memory_status(artifact, current_revision=current_revision),
            "content_summary": _compact_text(artifact["content_summary"], 900),
            "sha256": artifact["sha256"],
            "path": artifact["path"],
            "content": content,
            "content_loaded": bool(content),
        })
    return cards


def _artifact_reference_card(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "artifact_id": row.get("artifact_id", ""),
        "artifact_type": row.get("artifact_type", ""),
        "producer_role": row.get("producer_role", ""),
        "state_revision": row.get("state_revision", 0),
        "memory_status": artifact_memory_status(row),
        "content_summary": row.get("content_summary", ""),
        "path": row.get("path", ""),
        "content_in": "proof_dossier_artifacts",
    }


def _read_artifact_content(path: str, max_chars: int) -> str:
    if not path:
        return ""
    try:
        file_path = Path(path)
        if not file_path.is_file():
            return ""
        return _compact_text(file_path.read_text(encoding="utf-8", errors="replace"), max_chars)
    except OSError:
        return ""


def _claim_packet_card(row: Mapping[str, Any]) -> Dict[str, Any]:
    parent_ids = row.get("parent_ids_json", row.get("parent_ids", []))
    conditions = row.get("conditions_json", row.get("conditions", []))
    return {
        "claim_id": row["claim_id"],
        "kind": row.get("kind", ""),
        "statement": _compact_text(row.get("statement", ""), 4_000),
        "validation_status": row.get("validation_status", ""),
        "lifecycle_status": row.get("lifecycle_status", ""),
        "memory_status": claim_memory_status(row),
        "root_impact": row.get("root_impact", 0),
        "reduction_depth": row.get("reduction_depth", 0),
        "parent_ids": parent_ids if isinstance(parent_ids, list) else json_loads(parent_ids),
        "conditions": conditions if isinstance(conditions, list) else json_loads(conditions),
    }


def _graph_focus(
    state: Mapping[str, Any],
    claim_ids: List[str],
    inferences: List[Mapping[str, Any]],
    debts: List[Mapping[str, Any]],
) -> Dict[str, Any]:
    frontier = sorted(frontier_claim_ids(state), key=lambda cid: (root_distance_for_claim_id(state, cid), cid))
    return {
        "policy": "root-local frontier context",
        "frontier_claim_ids": frontier[:12],
        "route_scoreboard": route_scoreboard(state, limit=8),
        "selected_claim_count": len(claim_ids),
        "selected_inference_count": len(inferences),
        "selected_debt_count": len(debts),
        "total_claim_count": len(state["claims"]),
        "total_route_count": len(state["routes"]),
        "total_active_debt_count": sum(1 for row in state["debts"] if row.get("status") == "active"),
        "frontier_pressure": active_frontier_pressure(state),
        "omits_unrelated_artifacts": True,
    }


def _workflow_action_card(action: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not action:
        return {}
    allowed = {
        "mode",
        "display_mode",
        "target_id",
        "route_id",
        "reason",
        "debt_id",
        "needs_inference",
        "retrieval_required",
        "root_alignment_audit",
        "proof_compression_required",
        "proof_compression_operation_required",
        "canonical_full_proof_reconstruction_required",
        "conceptual_invariant_discovery_required",
        "conceptual_invariant_trigger",
        "proof_spine_compression_required",
        "post_integration_compression_required",
        "recently_integrated_target_id",
        "recently_integrated_route_id",
        "citation_certification_required",
        "citation_triage_required",
        "citation_verification_standard",
        "exact_theorem_search_required",
        "verifier_blocked_citation_search",
        "support_lemma_precheck_required",
        "support_lemma_label",
        "support_lemma_query",
        "proof_repair_required",
        "proof_repair_verification_required",
        "direct_solve_required",
        "proof_construction_required",
        "bridge_lemma_workbench_required",
        "bidirectional_bridge_search_required",
        "bridge_search_context",
        "bridge_candidate_limit",
        "bridge_selection_limit",
        "selected_bridge_promotion_required",
        "selected_bridge",
        "selected_conjecture_proof_required",
        "selected_conjecture",
        "experiment_workflow_required",
        "definition_invention_required",
        "invention_authorization",
        "advisor_global_synthesis_required",
        "synthesis_trigger",
        "advisor_synthesis_artifact_id",
        "advisor_synthesis_revision",
        "advisor_decisive_missing_statement",
        "advisor_best_route",
        "deep_session_required",
        "deep_session",
        "deep_session_roi",
        "deep_session_suppressed",
        "forced_research_philosophy",
        "long_mathematical_session_required",
        "research_philosophy",
        "research_cycle",
        "decisive_obligation_frontier_required",
        "decisive_obligation_frontier",
        "decisive_obligation_id",
        "decisive_obligation_target_id",
        "decisive_obligation_statement",
        "representation_switch_required",
        "representation_switch_contract",
        "theorem_adaptation_required",
        "theorem_adaptation_contract",
        "proof_interface_check_required",
        "proof_interface_contract",
        "branch_diversity_contract",
        "method_card_ids",
        "method_retrieval_structural_features",
        "method_cards_are_proof_evidence",
        "information_gain_score",
        "closure_pressure_required",
        "bottleneck_lock_required",
        "bottleneck_lock_signal",
        "rethlas_defeat_loop_required",
        "exact_librarian_companion_required",
        "advisor_compression_after_integration_required",
        "diagnostic_cooldown_active",
        "diagnostic_artifact_ids",
        "sublemma_extraction_required",
        "side_branch_roi_cap_active",
        "main_trunk_compute_reserved",
        "forbidden_outputs",
        "central_obstruction",
        "central_debt_id",
        "central_debt_alias_ids",
        "negative_result_ledger_required",
        "proof_architecture_templates_required",
        "cas_check_recommended",
        "citation_allowed_in_proof",
        "deep_research_required",
        "no_content_research_guard",
        "no_content_research_cluster",
        "proof_attempt_quota",
        "reduce_scope",
        "research_diagnostic_required",
        "needs_proof_dossier",
        "decomposition_plan_id",
        "decomposition_plan_artifact_id",
        "decomposition_step_required",
        "decomposition_parent_id",
        "decomposition_dependencies",
        "decomposition_parallel_group",
        "parent_implication_required",
        "key_failure_analysis_required",
        "decomposition_regulator_required",
        "failed_decomposition_artifact_id",
        "blocked_branch_ids",
        "source_synthesis_required",
        "source_adaptation_digest_required",
        "definition_audit_required",
        "route_triage_required",
        "retrieval_card_id",
        "citation_relation",
        "source_artifact_id",
        "source_artifact_type",
        "search_request_id",
        "search_request_artifact_id",
        "requested_query",
        "local_theorem_search_allowed",
        "source_synthesis_reason",
        "definition_audit_reason",
        "route_triage_reason",
        "active_trunk_pressure",
        "parallel_companion",
        "counterexample_search_required",
        "counterexample_probe_required",
        "counterexample_probe_contract",
        "counterexample_validation_required",
        "candidate_counterexample_artifact_id",
        "confirmed_counterexample_artifact_id",
        "counterexample_status_reconciliation_required",
        "validation_evidence_artifact_ids",
        "validation_acceptance_criteria",
        "advisor_requested_validation",
        "advisor_requested_verification",
        "allow_root_refutation",
        "root_is_interrogative_problem",
        "research_attack_stage",
        "research_synthesis_required",
        "approach_portfolio_synthesis_required",
        "global_synthesis_required",
        "theorem_building_synthesis_required",
        "proof_architecture_required",
        "proof_pressure_scheduler_required",
        "creative_proof_attack_required",
        "wild_mathematician_mode",
        "creative_attack_signal",
        "obstruction_inversion_required",
        "analogy_pass_required",
        "failure_autopsy_required",
        "bottleneck_ownership_required",
        "paperwork_throttle_required",
        "route_contract_required",
        "obligation_reduction_required",
        "speculative_proof_required",
        "repair_loop_required",
        "current_best_plan_required",
        "dead_route_suppression_required",
        "proof_architecture_signal",
        "decisive_theorem_test_required",
        "decisive_theorem_test",
        "paused_route_ids",
        "blocked_route_ids",
        "stalled_route_ids",
        "route_status_semantics",
        "global_synthesis_signal",
        "advisor_evidence_synthesis_required",
        "advisor_evidence_signal",
        "advisor_followup_required",
        "advisor_report_id",
        "advisor_recommended_next_action",
        "advisor_remaining_gaps",
        "advisor_proof_candidate",
        "proof_route_conversion_required",
        "proof_candidate_artifact_id",
        "proof_candidate_summary",
        "verify_ready_route_policy",
        "strict_verifier_scope",
        "verifier_evidence_artifact_ids",
        "verifier_evidence_state_revision",
        "verification_focus_inference_id",
        "strict_verifier_no_fresh_evidence",
        "strict_verifier_no_cas",
        "paper_audit_verification_only",
        "paper_audit_document_review_required",
        "paper_audit_document_integration_required",
        "paper_audit_referee_report_required",
        "paper_audit_source_artifact_ids",
        "strict_report_artifact_id",
        "integration_report_artifact_id",
        "parallel_wave_summary",
        "no_result_search_synthesis_required",
        "no_result_search_cluster",
        "no_result_card_ids",
        "obstruction_route_conversion_required",
        "global_obstruction_architecture_required",
        "obstruction_cluster",
        "obstruction_claim_ids",
        "obstruction_artifact_ids",
        "obstruction_debt_ids",
        "route_readiness",
        "duplicate_work_guard",
        "duplicate_work_key",
        "duplicate_work_count",
        "branch_focus",
        "nearby_lemma_directive",
        "branch_persistence",
        "branch_worker_directive",
        "branch_packet",
        "multi_branch_worker",
        "multi_branch_mode",
        "search_intent",
        "researcher_work_mode",
        "researcher_work_mode_reason",
        "work_mode_source",
        "advisor_mode_directive_artifact_id",
        "write_existing_proofs_on_stop",
        "stop_reason",
        "stop_reason_code",
        "stop_reason_detail",
        "completion_policy",
        "research_mode",
        "terminal_classification",
        "frontier_pressure",
        "critic_lens",
        "artifact_reviewed",
        "state_revision_reviewed",
        "writing_revision",
        "revision_of_artifact_id",
        "writing_gate_round",
        "paper_authoring",
        "paper_revision",
        "paper_review",
        "certificate_artifact_id",
    }
    return {key: action[key] for key in allowed if key in action}


def _fit_manifest(manifest: Dict[str, Any], *, max_chars: int) -> Dict[str, Any]:
    manifest = dict(manifest)
    while True:
        manifest.pop("manifest_hash", None)
        manifest["estimated_context_tokens"] = estimate_tokens_from_text(render_manifest(manifest))
        manifest["manifest_hash"] = manifest_hash(manifest)
        if len(render_manifest(manifest)) <= max_chars:
            return manifest
        if _trim_advisory_context(manifest):
            continue
        if _trim_retrieval_cards(manifest):
            continue
        if manifest.get("theorem_library"):
            manifest["theorem_library"] = manifest["theorem_library"][:-1]
            continue
        if manifest.get("artifacts") and _trim_optional_artifact(manifest):
            continue
        if len(manifest.get("claims", [])) > 1 and _trim_optional_claim(manifest):
            continue
        if manifest.get("inferences") and _trim_optional_inference(manifest):
            continue
        if manifest.get("debts"):
            if _integration_debts_are_authoritative(manifest):
                if _compact_authoritative_debts(manifest):
                    continue
            else:
                manifest["debts"] = manifest["debts"][:-1]
                continue
        graph_focus = manifest.get("graph_focus")
        if isinstance(graph_focus, dict):
            frontier_pressure = graph_focus.get("frontier_pressure")
            if isinstance(frontier_pressure, dict) and len(frontier_pressure.get("sample_claim_ids", [])) > 4:
                frontier_pressure["sample_claim_ids"] = frontier_pressure["sample_claim_ids"][:-1]
                continue
            if len(graph_focus.get("frontier_claim_ids", [])) > 4:
                graph_focus["frontier_claim_ids"] = graph_focus["frontier_claim_ids"][:-1]
                continue
        role_policy = manifest.get("role_context_policy")
        if isinstance(role_policy, dict) and role_policy.pop("summary", None) is not None:
            continue
        authoritative = str(role_policy.get("authoritative_packet") or "") if isinstance(role_policy, Mapping) else ""
        if "verification_packet" in authoritative.lower().replace(" ", "_"):
            # A verifier cannot adjudicate a proof after its authoritative
            # dossier has been shortened to a summary.  Exhaust compactable
            # instructions, strategy, graph, and policy material first; trim
            # proof_artifacts only if that still cannot meet the hard limit.
            if _emergency_trim_manifest(manifest):
                continue
        trimmed_packet = False
        for packet_name in ("verification_packet", "researcher_packet"):
            packet = manifest.get(packet_name)
            if isinstance(packet, dict) and _trim_packet_contents(packet):
                trimmed_packet = True
                break
        if trimmed_packet:
            continue
        if _emergency_trim_manifest(manifest):
            continue
        return manifest


def _integration_debts_are_authoritative(manifest: Mapping[str, Any]) -> bool:
    """Integration must retain every selected route-local debt under compaction.

    Unlike researcher packets, the ordinary integration packet has no nested
    debt copy: ``manifest.debts`` is the integrator's only view of blockers and
    the only allowed source for ``resolved_debt_ids``.  Dropping these rows to
    meet the context budget can make an integration report falsely claim that
    the route has no active blocking debt.
    """
    role_policy = manifest.get("role_context_policy")
    return bool(
        isinstance(role_policy, Mapping)
        and str(role_policy.get("context_role") or "") == "integration_verifier"
    )


def _compact_authoritative_debts(manifest: Dict[str, Any]) -> bool:
    debts = manifest.get("debts")
    if not isinstance(debts, list) or not debts:
        return False
    compact = [
        {
            "debt_id": str(row.get("debt_id") or ""),
            "owner_type": str(row.get("owner_type") or ""),
            "owner_id": str(row.get("owner_id") or ""),
            "debt_type": str(row.get("debt_type") or ""),
            "severity": str(row.get("severity") or ""),
            "status": str(row.get("status") or ""),
            "obligation": _compact_text(str(row.get("obligation") or ""), 260),
        }
        for row in debts
        if isinstance(row, Mapping)
    ]
    if compact == debts:
        return False
    manifest["debts"] = compact
    manifest["debts_compacted"] = True
    return True


def _emergency_trim_manifest(manifest: Dict[str, Any]) -> bool:
    """Last-resort compaction for deliberately tiny context budgets."""
    instructions = manifest.get("instructions")
    if isinstance(instructions, list) and len(instructions) > 1:
        manifest["instructions"] = ["Treat this manifest as authoritative Albilich v1 state."]
        manifest["instructions_trimmed"] = True
        return True
    strategy = manifest.get("research_strategy")
    minimal_strategy = {
        "compact": True,
        "policy": "strategy artifacts and method cards are advisory, not proof premises",
    }
    if isinstance(strategy, dict) and strategy != minimal_strategy:
        manifest["research_strategy"] = minimal_strategy
        return True
    proof_spine = manifest.get("proof_spine")
    if isinstance(proof_spine, dict):
        minimal_spine = {
            "compact": True,
            "target_id": str(proof_spine.get("target_id") or manifest.get("target_id") or "root"),
            "decisive_theorem_test": dict(proof_spine.get("decisive_theorem_test") or {}),
        }
        if proof_spine != minimal_spine:
            manifest["proof_spine"] = minimal_spine
            return True
    completion_policy = manifest.get("completion_policy")
    if isinstance(completion_policy, dict):
        minimal_completion = {"policy": str(completion_policy.get("policy") or DEFAULT_COMPLETION_POLICY), "compact": True}
        if completion_policy != minimal_completion:
            manifest["completion_policy"] = minimal_completion
            return True
    exchange = manifest.get("parallel_exchange")
    if isinstance(exchange, dict) and exchange != {"compact": True}:
        manifest["parallel_exchange"] = {"compact": True}
        return True
    search_policy = manifest.get("local_search_policy")
    if isinstance(search_policy, dict) and search_policy != {"compact": True}:
        if search_policy.get("compact"):
            ultra_compact_policy = {
                "compact": True,
                "rule": "read only manifest-listed evidence paths; no broad prior-run or downloads search",
                "allowed_local_evidence_paths": list(search_policy.get("allowed_local_evidence_paths") or []),
                "local_shell_rule": "Never run `find .`. Never construct artifact paths from artifact ids; inspect only allowed_local_evidence_paths and their children.",
            }
            if search_policy != ultra_compact_policy:
                manifest["local_search_policy"] = ultra_compact_policy
                return True
        else:
            minimal_policy = _minimal_local_search_policy(search_policy)
            if search_policy != minimal_policy:
                manifest["local_search_policy"] = minimal_policy
                return True
    contract = manifest.get("patch_contract")
    if isinstance(contract, dict):
        for key in ("parallel_signal_rule", "artifact_rule"):
            if key in contract:
                contract.pop(key, None)
                contract["compact"] = True
                return True
        emergency_contract = _emergency_patch_contract(contract)
        if contract != emergency_contract:
            manifest["patch_contract"] = emergency_contract
            return True
    role_policy = manifest.get("role_context_policy")
    if isinstance(role_policy, dict):
        compact_role_policy = {
            "context_role": str(role_policy.get("context_role") or ""),
            "authoritative_packet": str(role_policy.get("authoritative_packet") or ""),
            "compact": True,
        }
        if role_policy != compact_role_policy:
            manifest["role_context_policy"] = compact_role_policy
            return True
    retrieval_cards = manifest.get("retrieval_cards")
    action = manifest.get("workflow_action")
    required_card_id = str(action.get("retrieval_card_id") or "") if isinstance(action, Mapping) else ""
    if isinstance(retrieval_cards, list) and retrieval_cards:
        if required_card_id:
            kept = [
                card for card in retrieval_cards
                if isinstance(card, Mapping) and str(card.get("card_id") or "") == required_card_id
            ]
            if kept and kept != retrieval_cards:
                manifest["retrieval_cards"] = kept
                return True
        elif retrieval_cards:
            manifest["retrieval_cards"] = []
            return True
    if isinstance(manifest.get("artifacts"), list) and _trim_optional_artifact(manifest):
        return True
    role_policy = manifest.get("role_context_policy")
    authoritative = ""
    if isinstance(role_policy, Mapping):
        authoritative = str(role_policy.get("authoritative_packet") or "")
    # authoritative_packet values are display strings ("compact graph focus",
    # "retrieval_cards plus verification_packet"), not literal manifest keys, so
    # normalize before deciding which sections must survive emergency trimming.
    normalized = authoritative.lower().replace(" ", "_")
    protected_keys = {
        key for key in ("graph_focus", "research_task", "theorem_library") if key in normalized
    }
    graph_focus = manifest.get("graph_focus")
    if "graph_focus" in protected_keys and isinstance(graph_focus, dict):
        minimal_graph = {
            "compact": True,
            "frontier_claim_ids": list(graph_focus.get("frontier_claim_ids") or [])[:2],
            "total_claim_count": int(graph_focus.get("total_claim_count") or 0),
            "total_active_debt_count": int(graph_focus.get("total_active_debt_count") or 0),
        }
        if graph_focus != minimal_graph:
            manifest["graph_focus"] = minimal_graph
            return True
    for key in ("graph_focus", "research_task", "theorem_library"):
        if key in protected_keys:
            continue
        value = manifest.get(key)
        if value:
            manifest[key] = [] if isinstance(value, list) else {}
            return True
    return False


def _trim_optional_artifact(manifest: Dict[str, Any]) -> bool:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return False
    required_ids = _required_action_artifact_ids(manifest)
    for index in range(len(artifacts) - 1, -1, -1):
        artifact = artifacts[index]
        artifact_id = str(artifact.get("artifact_id") or "") if isinstance(artifact, Mapping) else ""
        if artifact_id not in required_ids:
            del artifacts[index]
            return True
    return False


def _trim_optional_claim(manifest: Dict[str, Any]) -> bool:
    claims = manifest.get("claims")
    if not isinstance(claims, list) or len(claims) <= 1:
        return False
    protected_ids = _protected_packet_claim_ids(manifest)
    for index in range(len(claims) - 1, -1, -1):
        claim = claims[index]
        claim_id = str(claim.get("claim_id") or "") if isinstance(claim, Mapping) else ""
        if claim_id not in protected_ids:
            del claims[index]
            return True
    return False


def _trim_optional_inference(manifest: Dict[str, Any]) -> bool:
    inferences = manifest.get("inferences")
    if not isinstance(inferences, list) or not inferences:
        return False
    protected_ids = _protected_packet_inference_ids(manifest)
    for index in range(len(inferences) - 1, -1, -1):
        inference = inferences[index]
        inference_id = str(inference.get("inference_id") or "") if isinstance(inference, Mapping) else ""
        if inference_id not in protected_ids:
            del inferences[index]
            return True
    return False


def _protected_packet_claim_ids(manifest: Mapping[str, Any]) -> set[str]:
    protected = {"root"}
    target_id = str(manifest.get("target_id") or "")
    if target_id:
        protected.add(target_id)
    routes = manifest.get("routes")
    route_id = str(manifest.get("route_id") or "")
    if isinstance(routes, list):
        for route in routes:
            if not isinstance(route, Mapping):
                continue
            current_route_id = str(route.get("route_id") or "")
            if route_id and current_route_id and current_route_id != route_id:
                continue
            conclusion_id = str(route.get("conclusion_claim_id") or "")
            if conclusion_id:
                protected.add(conclusion_id)
    inferences = manifest.get("inferences")
    if isinstance(inferences, list):
        for inference in inferences:
            if not isinstance(inference, Mapping):
                continue
            current_route_id = str(inference.get("route_id") or "")
            if route_id and current_route_id and current_route_id != route_id:
                continue
            conclusion_id = str(inference.get("conclusion_claim_id") or "")
            if conclusion_id:
                protected.add(conclusion_id)
            protected.update(_string_list(inference.get("premise_claim_ids")))
            protected.update(_string_list(inference.get("condition_claim_ids")))
    return protected


def _protected_packet_inference_ids(manifest: Mapping[str, Any]) -> set[str]:
    route_id = str(manifest.get("route_id") or "")
    if not route_id:
        return set()
    inferences = manifest.get("inferences")
    if not isinstance(inferences, list):
        return set()
    return {
        str(inference.get("inference_id") or "")
        for inference in inferences
        if isinstance(inference, Mapping)
        and str(inference.get("route_id") or "") == route_id
        and str(inference.get("inference_id") or "")
    }


def _required_action_artifact_ids(manifest: Mapping[str, Any]) -> set[str]:
    action = manifest.get("workflow_action")
    required = set()
    if isinstance(action, Mapping):
        required.update(_action_artifact_ids(action))
        if _needs_root_synthesis_context(action):
            for artifact in manifest.get("artifacts", []) if isinstance(manifest.get("artifacts"), list) else []:
                if not isinstance(artifact, Mapping):
                    continue
                if artifact.get("artifact_type") in ROOT_SYNTHESIS_CONTEXT_ARTIFACT_TYPES:
                    artifact_id = str(artifact.get("artifact_id") or "")
                    if artifact_id:
                        required.add(artifact_id)
    route_id = str(manifest.get("route_id") or "")
    protected_claim_ids = _protected_packet_claim_ids(manifest)
    for route in manifest.get("routes", []) if isinstance(manifest.get("routes"), list) else []:
        if not isinstance(route, Mapping):
            continue
        current_route_id = str(route.get("route_id") or "")
        if route_id and current_route_id and current_route_id != route_id:
            continue
        required.update(_string_list(route.get("evidence_artifact_ids")))
    for inference in manifest.get("inferences", []) if isinstance(manifest.get("inferences"), list) else []:
        if not isinstance(inference, Mapping):
            continue
        current_route_id = str(inference.get("route_id") or "")
        if route_id and current_route_id and current_route_id != route_id:
            continue
        required.update(_string_list(inference.get("evidence_artifact_ids")))
    for claim in manifest.get("claims", []) if isinstance(manifest.get("claims"), list) else []:
        if not isinstance(claim, Mapping):
            continue
        if str(claim.get("claim_id") or "") in protected_claim_ids:
            required.update(_string_list(claim.get("evidence_artifact_ids")))
    return required


def _string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        loaded = json_loads(value, None)
        if isinstance(loaded, list):
            value = loaded
        else:
            return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _trim_advisory_context(manifest: Dict[str, Any]) -> bool:
    strategy = manifest.get("research_strategy")
    if isinstance(strategy, dict):
        cards = strategy.get("retrieved_method_cards")
        if isinstance(cards, list) and len(cards) > 1:
            strategy["retrieved_method_cards"] = cards[:1]
            return True
        if isinstance(cards, list) and cards and isinstance(cards[0], Mapping) and "typical_inputs" in cards[0]:
            card = cards[0]
            strategy["retrieved_method_cards"] = [
                {
                    "method_id": card.get("method_id", ""),
                    "method_name": card.get("method_name", ""),
                    "matched_structural_features": card.get("matched_structural_features", []),
                    "known_failure_modes": list(card.get("known_failure_modes", []))[:3],
                    "advisory_only": True,
                }
            ]
            return True
        if strategy.get("memory_separation") and not strategy.get("compact"):
            strategy["memory_separation"] = {
                "policy": "verified facts, external theorems, advisory methods, and private speculation remain separate"
            }
            strategy["compact"] = True
            return True
    workflow_action = manifest.get("workflow_action")
    if isinstance(workflow_action, dict):
        bridge_context = workflow_action.get("bridge_search_context")
        if isinstance(bridge_context, dict):
            if bridge_context.get("retrieved_method_cards"):
                bridge_context["retrieved_method_cards"] = []
                return True
            for key, limit in (("forward_frontier", 4), ("backward_frontier", 4), ("existing_statement_fingerprints", 8)):
                value = bridge_context.get(key)
                if isinstance(value, list) and len(value) > limit:
                    bridge_context[key] = value[:limit]
                    return True
    exchange = manifest.get("parallel_exchange")
    if isinstance(exchange, dict):
        if isinstance(exchange.get("recent_signals"), list) and len(exchange.get("recent_signals", [])) > 4:
            exchange["recent_signals"] = exchange.get("recent_signals", [])[-4:]
            return True
        if "signal_schema" in exchange:
            exchange.pop("signal_schema", None)
            exchange["signal_schema_trimmed"] = True
            return True
        usage = exchange.get("usage")
        if isinstance(usage, list) and len(usage) > 1:
            exchange["usage"] = usage[:1]
            return True
        if not exchange.get("compact"):
            manifest["parallel_exchange"] = _minimal_parallel_exchange(exchange)
            return True

    contract = manifest.get("patch_contract")
    if isinstance(contract, dict):
        templates = contract.get("operation_templates")
        if isinstance(templates, list) and len(templates) > 2:
            contract["operation_templates"] = templates[:2]
            contract["operation_templates_trimmed"] = True
            return True
        if "operation_templates" in contract:
            contract.pop("operation_templates", None)
            contract["operation_templates_trimmed"] = True
            return True
        common = contract.get("common")
        if isinstance(common, dict) and isinstance(common.get("required_top_level"), list):
            common["required_top_level"] = "schema_version, problem_id, base_revision, actor_role, target_id, operations, rationale"
            return True
        if "common" in contract:
            contract.pop("common", None)
            contract["common_trimmed"] = True
            return True
        if not contract.get("compact"):
            manifest["patch_contract"] = _minimal_patch_contract(contract)
            return True

    search_policy = manifest.get("local_search_policy")
    if isinstance(search_policy, dict):
        excluded = search_policy.get("exclude_by_default")
        if isinstance(excluded, list) and len(excluded) > 3:
            search_policy["exclude_by_default"] = excluded[:3]
            search_policy["exclude_list_trimmed"] = True
            return True
        if not search_policy.get("compact"):
            manifest["local_search_policy"] = _minimal_local_search_policy(search_policy)
            return True

    branch_summaries = manifest.get("branch_summaries")
    if isinstance(branch_summaries, list) and branch_summaries:
        if len(branch_summaries) > 1:
            manifest["branch_summaries"] = branch_summaries[:-1]
        else:
            manifest.pop("branch_summaries", None)
            manifest["branch_summaries_trimmed"] = True
        return True
    memory_hygiene = manifest.get("memory_hygiene")
    if isinstance(memory_hygiene, dict) and memory_hygiene and not memory_hygiene.get("compact"):
        manifest["memory_hygiene"] = {
            "compact": True,
            "duplicate_debt_count": len(memory_hygiene.get("duplicate_debts", []) or []),
            "duplicate_retrieval_card_count": len(memory_hygiene.get("duplicate_retrieval_cards", []) or []),
        }
        return True

    instructions = manifest.get("instructions")
    if isinstance(instructions, list) and len(instructions) > 8:
        manifest["instructions"] = instructions[:8]
        manifest["instructions_trimmed"] = True
        return True
    if isinstance(instructions, list) and len(instructions) > 4:
        manifest["instructions"] = instructions[:4]
        manifest["instructions_trimmed"] = True
        return True
    role_policy = manifest.get("role_context_policy")
    if isinstance(role_policy, dict) and "summary" in role_policy:
        role_policy.pop("summary", None)
        return True
    return False


def _minimal_parallel_exchange(exchange: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "compact": True,
        "path": str(exchange.get("path") or ""),
        "recent_signals": list(exchange.get("recent_signals") or [])[-2:],
        "usage": [
            "Read recent_signals before final output; if a new signal matters, return it in top-level parallel_signals."
        ],
    }


def _minimal_patch_contract(contract: Mapping[str, Any]) -> Dict[str, Any]:
    templates = contract.get("operation_templates")
    op_names = [
        str(template.get("op") or "")
        for template in templates
        if isinstance(template, Mapping) and str(template.get("op") or "")
    ] if isinstance(templates, list) else []
    context_role = str(contract.get("context_role") or "")
    if not op_names:
        op_names = _default_operation_names(context_role)
    return {
        "compact": True,
        "context_role": context_role,
        "required_top_level": "schema_version, problem_id, base_revision, actor_role, target_id, operations, rationale",
        "base_revision_rule": "Use manifest.state_revision exactly.",
        "artifact_rule": "Prefer inline attach_artifact content; do not set producer_role.",
        "parallel_signal_rule": "Optional top-level parallel_signals are advisory blackboard signals.",
        "allowed_operation_names": op_names[:8],
    }


def _emergency_patch_contract(contract: Mapping[str, Any]) -> Dict[str, Any]:
    context_role = str(contract.get("context_role") or "")
    op_names = _string_list(contract.get("allowed_operation_names")) or _default_operation_names(context_role)
    compact: Dict[str, Any] = {"compact": True}
    if context_role:
        compact["context_role"] = context_role
    if op_names:
        compact["allowed_operation_names"] = op_names[:8]
    return compact


def _default_operation_names(context_role: str) -> list[str]:
    defaults = {
        "integration_verifier": ["attach_artifact", "propose_status_transition", "add_debt"],
        "strict_verifier": ["attach_artifact", "propose_status_transition", "add_debt"],
        "citation_verifier": ["certify_external_citation", "attach_artifact", "add_debt"],
        "counterexample_validator": ["attach_artifact", "propose_status_transition", "add_debt"],
        "literature_researcher": ["cache_retrieval_card", "attach_artifact", "add_debt"],
        "phd_advisor": ["attach_artifact", "add_debt", "update_debt"],
        "writer": ["attach_artifact"],
        "villain": ["attach_artifact", "add_claim", "propose_status_transition", "add_debt"],
        "researcher": ["attach_artifact", "add_claim", "add_route", "add_inference", "update_inference", "add_debt"],
    }
    return list(defaults.get(context_role, ["attach_artifact", "add_debt"]))


def _minimal_local_search_policy(policy: Mapping[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {
        "compact": True,
        "prefer": [
            "manifest proof-state artifact paths",
            "manifest retrieval cards and theorem-library entries",
            "explicitly named problem-relevant source paths",
        ],
        "download_scope_rule": str(policy.get("download_scope_rule") or ""),
        "allowed_local_evidence_paths": _string_list(policy.get("allowed_local_evidence_paths"))[:20],
        "local_shell_rule": str(policy.get("local_shell_rule") or ""),
        "exclude_by_default": [
            "prior agents/generation/results folders unless manifest-listed",
            "global downloads sweeps",
            "schema/test/source-code reading only to learn patch syntax",
        ],
        "allowed_exception": str(policy.get("allowed_exception") or ""),
    }
    allowed_cas = policy.get("allowed_cas_assets")
    if isinstance(allowed_cas, list) and allowed_cas:
        compact["allowed_cas_assets"] = allowed_cas
    return compact


def _trim_packet_contents(packet: Dict[str, Any]) -> bool:
    for verbose_key in (
        "expected_output",
        "research_diagnostic_gate",
        "verifier_rule",
    ):
        if verbose_key in packet:
            packet.pop(verbose_key, None)
            return True
    active_debts = packet.get("active_debts")
    protected_debt_ids = set(_string_list(packet.get("protected_debt_ids")))
    if isinstance(active_debts, list) and len(active_debts) > 8:
        protected = [row for row in active_debts if str(row.get("debt_id") or "") in protected_debt_ids]
        unprotected = [row for row in active_debts if str(row.get("debt_id") or "") not in protected_debt_ids]
        packet["active_debts"] = [*protected, *unprotected][:8]
        packet["active_debts_trimmed"] = True
        return True
    if isinstance(active_debts, list) and active_debts:
        for index in range(len(active_debts) - 1, -1, -1):
            row = active_debts[index]
            if str(row.get("debt_id") or "") in protected_debt_ids:
                continue
            active_debts.pop(index)
            packet["active_debts_trimmed"] = True
            return True
        for index, row in enumerate(active_debts):
            if not isinstance(row, Mapping) or row.get("compact"):
                continue
            active_debts[index] = {
                "compact": True,
                "debt_id": str(row.get("debt_id") or ""),
                "owner_type": str(row.get("owner_type") or ""),
                "owner_id": str(row.get("owner_id") or ""),
                "debt_type": str(row.get("debt_type") or ""),
                "severity": str(row.get("severity") or ""),
                "status": str(row.get("status") or ""),
                "obligation": _compact_text(str(row.get("obligation") or ""), 500),
                "suggested_next_target": str(row.get("suggested_next_target") or ""),
            }
            packet["active_debts_trimmed"] = True
            return True
    for key in ("proof_artifacts", "proof_dossier_artifacts", "source_adaptation_artifacts", "decomposition_artifacts", "cas_experiment_artifacts"):
        rows = packet.get(key)
        if not isinstance(rows, list) or not rows:
            continue
        if key == "proof_artifacts" and len(rows) > 3:
            rows.pop()
            return True
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            content = row.get("content")
            if isinstance(content, str) and len(content) > 1_200:
                row["content"] = _compact_text(content, max(1_000, len(content) // 2))
                return True
            if isinstance(content, str) and content and key != "proof_artifacts":
                row["content"] = ""
                row["content_loaded"] = False
                row["content_trimmed"] = True
                return True
            if isinstance(content, str) and content and key == "proof_artifacts" and len(content) > 700:
                row["content"] = _compact_text(content, 700)
                row["content_trimmed"] = True
                return True
        if key == "proof_artifacts" and len(rows) <= 1:
            continue
        if key != "proof_artifacts" and len(rows) <= 6:
            # Researcher handoffs depend on the artifact ids/paths themselves. Once
            # content is stripped above, keep a small reference set rather than
            # deleting the route/source/decomposition cards entirely.
            continue
        rows.pop()
        return True
    return False


def _rank_retrieval_cards(rows: List[Mapping[str, Any]], target_id: str) -> List[Mapping[str, Any]]:
    def key(row: Mapping[str, Any]) -> tuple[int, int, str]:
        applicability = json_loads(row.get("applicability_json"), {})
        if not isinstance(applicability, Mapping):
            applicability = {}
        classification = normalize_retrieval_relation(applicability.get("classification") or applicability.get("relation") or "")
        card_target = str(applicability.get("target_id") or target_id)
        target_penalty = 0 if card_target in {target_id, "root"} else 1
        return (target_penalty, RETRIEVAL_RELATION_LADDER.get(classification, 99), row.get("card_id", ""))

    return sorted(rows, key=key)


def _select_retrieval_cards(
    rows: List[Mapping[str, Any]],
    *,
    target_id: str,
    limit: int,
    action: Optional[Mapping[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ranked = _rank_retrieval_cards(rows, target_id)
    # Paraphrased duplicates of the same theorem evade the content-hash dedup;
    # keep only the best-ranked card per normalized statement fingerprint so the
    # manifest does not carry three near-identical cards for one source theorem.
    # The collapse is reported (manifest.memory_hygiene), not silent.
    deduped, duplicates = canonicalize_retrieval_cards(ranked)
    selected = list(deduped[:limit])
    requested_id = str((action or {}).get("retrieval_card_id") or "").strip()
    if requested_id and not any(row.get("card_id") == requested_id for row in selected):
        requested = next((row for row in rows if row.get("card_id") == requested_id), None)
        if requested is not None:
            selected.insert(0, requested)
            selected = selected[: max(1, limit)]
    return [_retrieval_card(row) for row in selected], duplicates


def _trim_retrieval_cards(manifest: Dict[str, Any]) -> bool:
    cards = manifest.get("retrieval_cards")
    if not isinstance(cards, list) or not cards:
        return False
    workflow_action = manifest.get("workflow_action")
    required_id = ""
    if isinstance(workflow_action, Mapping):
        required_id = str(workflow_action.get("retrieval_card_id") or "").strip()
    for index in range(len(cards) - 1, -1, -1):
        card = cards[index]
        card_id = str(card.get("card_id") if isinstance(card, Mapping) else "")
        if required_id and card_id == required_id:
            continue
        del cards[index]
        return True
    if not required_id:
        cards.pop()
        return True
    return False


def _rank_theorem_library_entries(rows: List[Mapping[str, Any]], target_id: str) -> List[Mapping[str, Any]]:
    def key(row: Mapping[str, Any]) -> tuple[int, int, str]:
        tags = {str(tag) for tag in json_loads(row.get("tags_json", row.get("tags", [])))}
        target_penalty = 0 if f"target:{target_id}" in tags or target_id == "root" else 1
        relation = str(row.get("relation_to_target") or "")
        relation_rank = {"exact": 0, "equivalent": 1, "stronger": 2, "partial": 4, "conditional": 5}.get(relation, 9)
        return (target_penalty, relation_rank, str(row.get("entry_id") or ""))

    return sorted(rows, key=key)


def _research_task(
    action: Optional[Mapping[str, Any]],
    target: Mapping[str, Any],
    debts: List[Mapping[str, Any]],
    *,
    state: Mapping[str, Any],
) -> Dict[str, Any]:
    if not action or action.get("mode") != "retrieve":
        return {}
    blocking_debts = [row for row in debts if row.get("severity") == "blocking"]
    debt = next((row for row in blocking_debts if row.get("debt_id") == action.get("debt_id")), None)
    if debt is None and blocking_debts:
        debt = blocking_debts[0]
    task = {
        "mode": "claim_driven_librarian",
        "librarian_level": action.get("librarian_level", "scout"),
        "librarian_escalation_policy": librarian_escalation_policy(str(action.get("librarian_level") or "scout")),
        "target_id": target["claim_id"],
        "target_statement": target["statement"],
        "reason": action.get("reason", ""),
        "search_intent": action.get("search_intent", "literature_scoping"),
        "relation_ladder": [
            "direct_match",
            "stronger_match",
            "equivalent_reformulation",
            "conditional_match",
            "partial_match",
            "method_match",
            "obstructing",
            "background",
            "irrelevant",
        ],
        "stop_rule": "Stop once a useful theorem card is recorded: direct, stronger, equivalent, conditional, partial, method, or obstruction. Do not keep searching after enough evidence exists.",
        "deep_read_rule": "Read an entire source only to check hypotheses, resolve conflicts, solve nontrivial theorem matching, or inspect an unusually related result.",
        "solved_rule": "If an exact, stronger, or equivalent source theorem proves the root statement with no missing hypotheses, declare it a program_victory_candidate in the retrieval card/source_adaptation_notes and stop searching; strict citation certification and root-alignment integration are still the gates that mark the program solved.",
        "partial_rule": "Weaker, conditional, partial, method, or background cards may guide work but must be reported only as partial progress unless a verified implication to the root is later integrated.",
        "root_relevance_rule": "Always classify whether the source attacks the root theorem directly, reframes it by a stronger/equivalent theorem, supports only a local proof obligation, or shows an obstruction.",
        "handoff_rule": "When a source looks usable, attach source_adaptation_notes explaining the local translation, checked hypotheses, missing hypotheses, and the exact proof obligation it might close.",
        "researcher_handoff": "Useful theorem cards should be paired with source_adaptation_notes so the researcher can turn literature into a local proof dossier.",
    }
    task["informal_theorem_search"] = _informal_theorem_search_task(
        action,
        target_statement=str(target.get("statement") or ""),
    )
    if action.get("exact_theorem_search_required") or action.get("support_lemma_precheck_required"):
        task["exact_lookup_policy"] = {
            "max_primary_retrieval_cards": 1,
            "max_source_adaptation_notes": 1,
            "max_supporting_sources": 1,
            "stop_after_first_checked_match": True,
            "fallback_card": "no_useful_result_found",
            "forbid_general_survey": True,
        }
        task["stop_rule"] = (
            "Exact lookup budget: answer requested_query with at most one decisive retrieval card and one linked "
            "source_adaptation_notes handoff. After the first checked direct, stronger, equivalent, conditional, "
            "partial, method, or obstructing match, stop instead of continuing bibliography. Use at most one supporting "
            "source only when it closes a named hypothesis. If no locatable theorem is found, cache exactly one "
            "no_useful_result_found card with the strongest failed query and reason."
        )
    search_request = _search_request_for_action(state, action)
    if search_request:
        task["mode"] = "researcher_requested_librarian"
        task["researcher_search_request"] = search_request
        task["stop_rule"] = (
            "Answer the researcher_search_request. If no useful source exists in the allowed search scope, cache a no_useful_result_found "
            "retrieval card tied to search_request_id so the researcher can move on."
        )
        task["handoff_rule"] = (
            "For any plausibly useful source, attach source_adaptation_notes linked to search_request_id with local statement translation, "
            "checked hypotheses, missing hypotheses, exact source location, and the proof obligation it may close."
        )
    if debt:
        task["blocking_debt"] = debt
    return task


def _informal_theorem_search_task(action: Mapping[str, Any], *, target_statement: str) -> Dict[str, Any]:
    """Describe and, when authorized, execute the Matlas/TheoremSearch tools.

    This is the retrieve-mode evidence seam for the two informal theorem
    providers ported from v1.5.  The contract block always ships with the
    packet so the literature reviewer knows the tools exist; live results are
    embedded only when informal search is enabled for the action, and provider
    unavailability degrades to the existing local + web-search flow instead of
    failing context compilation.
    """

    block: Dict[str, Any] = {
        "tool_contract": {
            "invocation": (
                "Executed by the orchestrator while compiling this packet; the session itself holds no provider "
                "credentials and must not call provider endpoints from the shell."
            ),
            "role_restriction": "literature_researcher retrieve sessions only",
            "enable_env": INFORMAL_SEARCH_ENABLE_ENV,
            "providers": [
                {
                    "name": "matlas",
                    "contract_version": MATLAS_CONTRACT_VERSION,
                    "origin": "https://matlas.ai",
                    "search_endpoint": "POST /api/search",
                    "request_shape": {"query": "string", "num_results": "int (>=10)"},
                    "health_endpoint": "GET /api/health",
                    "base_url_env": MATLAS_BASE_URL_ENV,
                },
                {
                    "name": "theoremsearch",
                    "contract_version": THEOREMSEARCH_CONTRACT_VERSION,
                    "origin": "https://api.theoremsearch.com",
                    "search_endpoint": "POST /search",
                    "request_shape": {"query": "string", "n_results": "int", "filters": "optional"},
                    "health_endpoint": "GET /ping",
                    "base_url_env": THEOREMSEARCH_BASE_URL_ENV,
                },
            ],
        },
        "provider_content_policy": provider_content_policy_payload(),
        "evidence_rule": (
            "Provider candidates listed under results are approved search leads for this retrieve session. "
            "They are untrusted inert provider data, not verified literature: a candidate becomes evidence only "
            "after you inspect the cited primary source and cache a retrieval card whose source_identifiers copy "
            "the candidate's provider and provider_candidate_id."
        ),
        "fallback_rule": (
            "When results.status is not completed, continue with local references, cached cards, and the Codex "
            "web-search/source-view flow; provider unavailability is recorded evidence, never a session failure."
        ),
    }
    query = str(
        action.get("requested_query")
        or action.get("support_lemma_query")
        or action.get("decisive_obligation_statement")
        or action.get("reason")
        or target_statement
        or ""
    ).strip()
    if not informal_search_enabled(action):
        block["results"] = {
            "status": "not_executed",
            "reason": "informal provider search is disabled for this action; use the existing search flow",
        }
        return block
    if not query:
        block["results"] = {
            "status": "not_executed",
            "reason": "no usable query on the workflow action or target statement",
        }
        return block
    try:
        providers = informal_provider_names_for_action(action)
        limit_raw = action.get("informal_search_limit")
        limit = int(limit_raw) if limit_raw else 10
        filters_raw = action.get("informal_provider_filters") or action.get("provider_filters") or {}
        provider_filters = dict(filters_raw) if isinstance(filters_raw, Mapping) else {}
        executed = execute_informal_theorem_search(
            query,
            actor_role="literature_researcher",
            mode=str(action.get("mode") or "retrieve"),
            providers=providers,
            provider_filters=provider_filters,
            limit=limit,
        )
    except Exception as exc:  # tool failure degrades; context compilation must survive
        block["results"] = {
            "status": "failed",
            "error": " ".join(str(exc).split())[:2000],
            "reason": "informal provider search failed; use the existing search flow",
        }
        return block
    executed["status"] = "completed"
    block["results"] = executed
    return block


def _search_request_for_action(state: Mapping[str, Any], action: Mapping[str, Any]) -> Dict[str, Any]:
    artifact_id = str(action.get("search_request_artifact_id") or "")
    if not artifact_id:
        return {}
    row = next(
        (
            artifact for artifact in state.get("artifacts", [])
            if artifact.get("artifact_id") == artifact_id
        ),
        None,
    )
    if row is None:
        return {
            "artifact_id": artifact_id,
            "search_request_id": action.get("search_request_id", ""),
            "query": action.get("requested_query", ""),
        }
    metadata = json_loads(row.get("metadata_json"), {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    return {
        "artifact_id": artifact_id,
        "search_request_id": action.get("search_request_id") or metadata.get("search_request_id") or metadata.get("request_id") or artifact_id,
        "target_id": metadata.get("target_id") or action.get("target_id") or "root",
        "route_id": metadata.get("route_id") or action.get("route_id") or "",
        "query": action.get("requested_query") or metadata.get("query") or metadata.get("search_query") or row.get("content_summary", ""),
        "missing_theorem": metadata.get("missing_theorem", ""),
        "proof_obligation": metadata.get("proof_obligation", ""),
        "acceptance_criteria": metadata.get("acceptance_criteria", []),
        "forbidden_sources": metadata.get("forbidden_sources", []),
        "local_theorem_search_allowed": bool(action.get("local_theorem_search_allowed")),
        "path": row.get("path", ""),
        "content": _read_artifact_content(str(row.get("path") or ""), 4_000),
    }


def _compact_text(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 24)].rstrip() + " ... [truncated]"
