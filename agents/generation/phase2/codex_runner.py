from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from .budget import parse_token_usage
from .context_builder import build_context_manifest, build_resume_delta_manifest, manifest_hash, render_manifest
from .models import sha256_text, utc_now
from .patches import preflight_patch_errors
from .role_capabilities import role_can_use_cas, session_cas_enabled
from .store import ProofStateStore

DEFAULT_CODEX_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_SANDBOX = "workspace-write"
DEFAULT_CHILD_TIMEOUT_SECONDS = 7200
LOG_PARSE_HEAD_BYTES = 64_000
LOG_PARSE_TAIL_BYTES = 256_000
LIVE_LOG_TAIL_BYTES = 12_000
CODEX_SESSION_ROOT_ENV = "ALBILICH_CODEX_SESSION_ROOT"
DEFAULT_PROGRESS_INTERVAL_SECONDS = 15.0
DEFAULT_CODEX_STALE_RETRY_SECONDS = 90.0
DEFAULT_CODEX_CHILD_TMPDIR = Path(__file__).resolve().parents[3] / ".albilich" / "tmp" / "codex-child"
DEFAULT_CODEX_CHILD_RUST_LOG = (
    "warn,codex_core_plugins::manifest=error,codex_core_skills::loader=error,"
    "codex_mcp::rmcp_client=error,codex_core::shell_snapshot=error,"
    "codex_rollout::list=error,codex_rollout::state_db=error"
)
CODEX_CHILD_USE_USER_CONFIG_ENV = "ALBILICH_CODEX_CHILD_USE_USER_CONFIG"
DEFAULT_CODEX_CHILD_EXEC_ARGS = ("--ignore-user-config",)
DEFAULT_CODEX_CHILD_DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "goals",
    "image_generation",
    "memories",
    "multi_agent",
    "plugins",
    "skill_mcp_dependency_install",
    "tool_suggest",
    "workspace_dependencies",
)
NOISY_CODEX_STARTUP_LOG_FRAGMENTS = (
    " WARN codex_core_plugins::manifest: ignoring interface.defaultPrompt",
    " WARN codex_core_skills::loader: ignoring interface.icon_small",
    " WARN codex_core_skills::loader: ignoring interface.icon_large",
    " WARN codex_mcp::rmcp_client: failed to initialize MCP client during shutdown: MCP startup failed: Environment variable GITHUB_PAT_TOKEN",
    " WARN codex_core::shell_snapshot: Failed to delete shell snapshot",
    " WARN codex_rollout::list: state db discrepancy during find_thread_path_by_id_str_in_subdir",
    " WARN codex_rollout::state_db: state db discrepancy during read_repair_rollout_path",
    " WARN codex_rollout::state_db: state db reconcile_rollout extraction failed",
)
STALE_RETRY_LOG_FRAGMENTS = (
    "codex_core::responses_retry",
    "stream disconnected - retrying sampling request",
    "retrying sampling request",
)
ProgressCallback = Callable[[Mapping[str, Any]], None]
_SESSION_PATH_CACHE: dict[str, Optional[Path]] = {}


def actor_role_for_action(action: Mapping[str, Any]) -> str:
    mode = str(action.get("mode") or "prove")
    route_id = str(action.get("route_id") or "")
    if mode == "integrate":
        return "integration_verifier"
    if mode == "formalize":
        return "formal_backend"
    if mode == "validate_counterexample":
        return "counterexample_validator"
    if mode == "retrieve":
        return "literature_researcher"
    if mode == "synthesize_sources":
        return "literature_researcher"
    if mode == "audit_definitions":
        return "literature_researcher"
    if mode == "triage_routes":
        return "phd_advisor"
    if mode == "regulate_decomposition":
        return "phd_advisor"
    if mode == "refute":
        return "villain"
    if mode == "write":
        return "writer"
    if mode == "prove" and (route_id or action.get("citation_certification_required") or action.get("citation_triage_required")):
        return "strict_informal_verifier"
    if mode in {"reduce", "weaken", "strengthen"} and action.get("debt_id"):
        if route_id or action.get("proof_repair_required") or action.get("research_diagnostic_required"):
            return "researcher"
        return "phd_advisor"
    return "researcher"


def build_session_prompt(*, context_path: Path, action: Mapping[str, Any], actor_role: str, resume: bool = False) -> str:
    mode = str(action.get("mode") or "prove")
    target_id = str(action.get("target_id") or "root")
    route_id = str(action.get("route_id") or "")
    guidance = _mode_guidance(mode, actor_role, route_id, action=action)
    if resume:
        header = [
            f"CONTINUE your prior Albilich v1 session. Read ONLY the delta context at {context_path} — it lists what changed since your last turn.",
            "You already hold the full manifest and every artifact you read earlier in this session; do NOT re-read them — rely on your existing context.",
            f"You are actor_role={actor_role} for mode={mode} targeting {target_id}.",
        ]
    else:
        header = [
            f"Read the Albilich v1 context manifest at {context_path}.",
            f"You are actor_role={actor_role} for mode={mode} targeting {target_id}.",
        ]
    if session_cas_enabled(actor_role, action):
        cas_guidance = [
            "If manifest.cas_tooling is present, you may read, run, and query the listed CAS/data assets through tool calls (run a Macaulay2 .m2 file with M2, a Julia .jl script with julia, and query a .jsonl/.csv invariant-vector dataset with jq/julia/python) for bounded computations and example/counterexample search, even though their directory is otherwise excluded; filter large datasets rather than loading them whole, and attach a cas_experiment_report when the computation matters.",
            "Use CAS lifecycle tools for CAS computations when available. Do not start unbounded shell computations, and never use broad process-control commands such as pkill, killall, or pattern-based kill to manage stuck work; stop only CAS sessions you started via cas_stop, or abandon a failed shell probe and record the obstruction. Do not assume optional Python packages such as sympy are installed; if plain Python is enough, use the standard library.",
        ]
    elif actor_role in {"researcher", "villain"}:
        cas_guidance = [
            f"CAS lifecycle tools are not available in this {actor_role} work mode (see manifest.workflow_action.researcher_work_mode). Do not call discover_cas_backends, cas_start, cas_poll, or cas_stop, and do not run CAS/data assets directly in this pass. If a bounded computation is genuinely the next decisive move, say so precisely (backend, finite scope, expected decisive output) in your artifact metadata so the advisor or scheduler can route a cas-mode pass.",
        ]
    else:
        cas_guidance = [
            "CAS lifecycle tools and CAS/data asset execution are not available to this role. Do not compute independently. Do not call discover_cas_backends, cas_start, cas_poll, or cas_stop, and do not run CAS/data assets directly. If a computation would help, request a bounded researcher or villain CAS check and reason from existing cas_experiment_report artifacts only.",
        ]
    return "\n".join(
        [
            *header,
            "Return only one JSON object, with no markdown fence and no prose.",
            "It must be an Albilich v1 patch with schema_version=1, the manifest problem_id, the manifest state_revision as base_revision, this exact actor_role, target_id, and a nonempty operations list.",
            "Do not set producer_role on artifacts; the workflow records it from actor_role and rejects spoofing.",
            "For add_debt/update_debt, owner_id must be a concrete claim_id, route_id, or inference_id from the manifest or same patch; never use role names like researcher, phd_advisor, advisor, verifier, or literature_researcher as graph owners.",
            "Use manifest.patch_contract for patch shape; do not inspect framework source, schemas, tests, or README just to learn patch syntax.",
            "Do not add a new active sufficient route concluding an already integrated claim; closed branches should feed root synthesis by updating an existing inference with genuinely new evidence or by attacking the next root-level gap.",
            "Do not call tool_search, plugin discovery, connector discovery, plugin installation, browser/app/thread tools, or memory tools. "
            "The Albilich child session is already given its manifest and approved evidence boundary; plugin/tool discovery is outside the workflow and can corrupt structured patch output.",
            "Stay inside the evidence boundary of this run: use the manifest, manifest-listed artifact paths, listed source files, problem-relevant manifest-listed downloads/.refs/theorem-library material, and explicitly named context only.",
            "Follow manifest.local_search_policy: prefer manifest.artifacts[].path, manifest.local_search_policy.allowed_local_evidence_paths, theorem-library entries, and exact manifest paths; do not sweep the whole global downloads tree.",
            "For shell path searches, use only manifest.local_search_policy.allowed_local_evidence_paths and their children. Never construct artifact paths from artifact_id guesses, never run `find .` to discover downloads, and never run broad `find`/`rg`/`grep` commands over agents/generation/downloads; unlisted local evidence paths are tainted evidence and the workflow may reject the patch.",
            "Do not search or read prior results, logs, memory directories, or other problem-id folders under agents/generation/results unless the manifest explicitly lists them as allowed benchmark provenance; never use those prior artifacts as mathematical evidence. Do not grep, inspect, query, or quote workflow_runs, codex.log, final_patch.json, console files, proof_state.sqlite3, raw SQLite proof databases, or raw prior session transcripts; use only the manifest-listed artifacts and context entries as proof evidence.",
            "Use manifest.parallel_exchange as a live blackboard. If you find evidence, an obstruction, a contradiction, a useful lemma, a failed path, or a source that could affect another active branch, include a top-level parallel_signals array in your returned patch. Do not write manifest.parallel_exchange.path directly; the workflow writes and deduplicates accepted patch signals.",
            "Never mark a claim or inference informally_verified, formally_verified, refuted, or integrated unless this role and the evidence gates permit that transition.",
            *cas_guidance,
            guidance,
        ]
    )


def _researcher_work_mode_guidance(action: Mapping[str, Any]) -> str:
    work_mode = str(action.get("researcher_work_mode") or "").strip().lower()
    if not work_mode:
        return ""
    reason = str(action.get("researcher_work_mode_reason") or "").strip()
    source = str(action.get("work_mode_source") or "").strip()
    header = (
        f"RESEARCHER WORK MODE: {work_mode} (source: {source or 'scheduler'}). "
        + (f"Why: {reason} " if reason else "")
        + "The researcher loop rotates through online (search and read), offline (think and prove), and cas (compute and "
        "experiment) passes, and the PhD advisor may override the rotation when it believes you should search more, think "
        "more, or experiment more. Respect this pass's mode. "
    )
    if work_mode == "online":
        return header + (
            "This is an ONLINE pass: live web search is enabled for you in this session. Use it like a research "
            "mathematician at the library: hunt for exact/stronger/equivalent theorems, surveys, and methods bearing on the "
            "current bottleneck; read the strongest candidates; and translate what you find into local notation. Record "
            "genuinely useful sources precisely (authors, title, exact theorem/lemma number or page/section, hypotheses, "
            "definition mismatches) inside your proof_dossier/source_adaptation_notes or a literature_search_request so the "
            "librarian and verifier can act on them. Stop searching once you have a usable result and spend the remaining "
            "budget converting it into proof-state mathematics; do not keep browsing after the decisive source is in hand. "
        )
    if work_mode == "cas":
        return header + (
            "This is a CAS EXPERIMENT pass: computation is the point of this session. Design one or a few bounded, decisive "
            "computations (examples, counterexample sweeps, finite case checks, invariant calculations) that can change the "
            "next mathematical decision; run them with the CAS lifecycle tools (discover_cas_backends, cas_start, cas_poll, "
            "cas_stop) or the manifest-listed CAS assets; and attach a cas_experiment_report with backend, code, finite "
            "scope, output summary, conclusion, and proof relevance. If no CAS backend is runnable, do the small cases by "
            "hand in the dossier and record exactly which computation should run when a backend exists. End the pass by "
            "stating what the computation decided and what the next proof move is; raw output without a mathematical "
            "conclusion is a wasted experiment. "
        )
    return header + (
        "This is an OFFLINE pass: no web search and no CAS in this session. Work like a mathematician at the blackboard: "
        "use the manifest, cached retrieval cards, theorem-library entries, and your own knowledge to push the actual "
        "proof — direct arguments, route repair, bridge lemmas, obstruction analysis, and careful case work recorded in a "
        "proof_dossier or proof_blueprint. If you hit a wall that genuinely needs a source or a computation, do not stall: "
        "finish the strongest local argument you can, then record a precise literature_search_request or a named bounded "
        "CAS request in metadata so a later online or cas pass (or the advisor) can pick it up. "
    )


def _villain_work_mode_guidance(action: Mapping[str, Any]) -> str:
    work_mode = str(action.get("researcher_work_mode") or "").strip().lower()
    if not work_mode:
        return ""
    reason = str(action.get("researcher_work_mode_reason") or "").strip()
    source = str(action.get("work_mode_source") or "").strip()
    header = (
        f"VILLAIN WORK MODE: {work_mode} (source: {source or 'scheduler'}). "
        + (f"Why: {reason} " if reason else "")
        + "The refuter runs the same online/offline/cas loop as the researcher (computation-first cycle), and the PhD "
        "advisor may direct your next mode when you should search more, construct more, or compute more. Respect this "
        "pass's mode. "
    )
    if work_mode == "online":
        return header + (
            "This is an ONLINE refutation pass: live web search is enabled for you in this session. Hunt the literature "
            "adversarially: known counterexample families, published theorems that contradict or constrain the target, "
            "missing-hypothesis folklore, and prior art that already settles the claim under attack in either direction "
            "(a published proof kills a refutation route as decisively as a published counterexample kills a proof "
            "route). Record decisive sources precisely (authors, exact theorem/page, hypotheses) inside your obstruction "
            "or candidate_counterexample artifacts, and stop searching once you have a decisive lead — spend the rest of "
            "the pass converting it into a concrete obstruction. "
        )
    if work_mode == "cas":
        return header + (
            "This is a CAS REFUTATION pass: computation is the point of this session. Design bounded adversarial "
            "computations — counterexample sweeps, hypothesis-failure searches, invariant checks on the smallest "
            "candidates — run them with the CAS lifecycle tools or manifest-listed assets, and attach a "
            "cas_experiment_report with backend, code, finite scope, output summary, and the refutation relevance. If no "
            "backend is runnable, enumerate the smallest cases by hand. End by stating what the computation ruled out or "
            "exposed; a sweep without a conclusion is a wasted attack. "
        )
    return header + (
        "This is an OFFLINE refutation pass: no web search and no CAS in this session. Attack like a mathematician at "
        "the blackboard: stress hypotheses, build candidate counterexamples by hand, and hunt hidden assumptions and "
        "boundary cases in the manifest's routes and dossiers. If a decisive computation or a known counterexample "
        "family would settle it, record that as a precise bounded request in your artifact metadata so a later cas or "
        "online pass can pick it up. "
    )


def _mode_guidance(mode: str, actor_role: str, route_id: str, action: Optional[Mapping[str, Any]] = None) -> str:
    action = action or {}
    if actor_role == "strict_informal_verifier":
        route_text = f"route {route_id}" if route_id else "the selected route"
        citation_guidance = ""
        if mode == "prove" and not route_id:
            citation_guidance = (
                " If manifest.workflow_action.citation_triage_required=true, this is a fast citation triage task. Check whether the "
                "retrieval card gives a source that is actually locatable, a named theorem/proposition/lemma/corollary or precise page/section "
                "location, a statement close enough to compare, no visible missing hypotheses, and a plausible exact/equivalent/stronger "
                "deduction to the target. Do not certify the root during triage; attach a verification_report with verdict "
                "citation_triage_pass or citation_triage_fail, checked_items, gaps, and the single next missing item if it fails. "
                "If manifest.workflow_action.citation_certification_required=true, this is an external citation certification task, "
                "not an internal reconstruction task. Inspect manifest.workflow_action.retrieval_card_id and the matching retrieval card. "
                "If and only if the card gives source metadata precise enough for a reader to locate the result, a theorem/proposition/lemma/"
                "corollary number or precise page/section location, no missing hypotheses, checked local definitions, and an exact/equivalent/"
                "stronger implication to the target, return a single "
                "certify_external_citation operation with card_id, target_id, relation_to_target, implication_verified=true, hidden_assumptions=false, "
                "checked_items, and a concise summary. If any item is missing or mismatched, do not certify; attach a verification_report and add "
                "one precise missing_reference or missing_hypothesis debt."
            )
        return (
            "Use manifest.verification_packet as the required local proof packet when present: read the exact target statement, "
            "selected route, premise claims, route inferences, active debts, and every proof_artifacts content entry before deciding. "
            "Treat this as a bounded verification job, not a proof-search job: do not run CAS, do not perform live literature search, "
            "do not create proof_dossier/proof_blueprint/cas_experiment_report artifacts, and do not introduce new mathematical evidence. "
            "Only attach verification_report artifacts, propose allowed verification/refutation status changes, and add precise gap debts. "
            "If a routed local verification lacks proof_artifacts or proof_dossier content, do not certify from graph summaries; "
            "attach a verification_report and add one precise gap debt asking the researcher for a complete local argument. "
            "If manifest.workflow_action.parent_implication_required=true or workflow_action.decomposition_plan_id is present, "
            "check the decomposition implication itself: the listed subgoals, hypotheses, and route inferences must actually imply "
            "the parent claim without hidden assumptions. Verifying subgoals separately is not enough. Perform structural plan validation: "
            "subgoals must be precise mathematical claims, dependency_edges must be acyclic, cases must be exhaustive when plan_kind is a "
            "case split, cited theorem hypotheses must appear as explicit assumptions or subgoals, and the assembly_argument must connect "
            "all verified branches to the parent. "
            f"Rigorously check {route_text}. If it is correct with no gaps, attach a verification_report artifact "
            "with concise metadata: verdict, checked_items, a short summary, critical_errors, gaps, blocking_gap, and repair_hints. "
            "Use verdict='verified' or verdict='correct_no_gaps' for a zero-gap pass; verdict='pass' is accepted for "
            "backward compatibility but the canonical verifier verdicts are preferred. "
            "External mathematics may discharge a step when a retrieval card or source artifact gives a reasonable citation: a locatable "
            "paper/book/source, theorem/proposition/lemma/corollary number or precise page/section location, source version when available, "
            "statement, hypotheses, definitions, and source location, and you independently check that those hypotheses match the current "
            "claim and the cited result implies exactly the needed step. In that case record the citation in checked_items and in the "
            "report body; do not demand an internal reproof of a properly cited theorem. Otherwise "
            "add a missing_reference or missing_hypothesis debt. "
            "CAS experiment reports may support examples, counterexamples, or bounded finite computations only when the finite scope, code, "
            "output, and deduction to the claimed step are explicit; otherwise ask for a sharper computation or a proof. "
            "For a correct proof use critical_errors=[] and gaps=[], then propose informally_verified for the checked inference(s) "
            "and the target claim. If there is any gap or error, do not verify; attach the short report and add precise active "
            "proof debts. Put long prose only in an external artifact path when truly needed."
            + citation_guidance
        )
    if actor_role == "integration_verifier":
        return (
            "Check that the selected sufficient route has verified inferences, verified premises, a verified conclusion claim, "
            "and no unresolved active blocking debt. For root integration, also perform statement alignment: the proved statement must be "
            "exactly the target, an equivalent reformulation, or a stronger theorem with a verified implication to the target. "
            "When you set root_alignment.target_statement, COPY it verbatim from manifest.root_statement (the full text, or the "
            "problem file's '## Problem' section / its question paragraph, byte-for-byte). Never paraphrase, summarize, retitle, or "
            "reformat the target statement: the alignment gate compares against the immutable root text and rejects paraphrases. "
            "If the action has root_alignment_audit=true, perform an audit only: attach a root_alignment_audit artifact with "
            "metadata relation_to_root, target_statement, current_route_statement, missing_alignment_evidence, hidden_assumptions, "
            "extra_assumptions, and recommended_next_action. Do not integrate unless all ordinary integration gates are also met. "
            "Never integrate a weaker, conditional, or nearby partial theorem as solved. If and only if integration is valid, "
            "attach an integration_report artifact with concise metadata integrates=true, route_id, claim_id, missing, outcome, resolved_debt_ids, "
            "and root_alignment={relation_to_root: exact|equivalent|stronger, target_statement, proved_statement, "
            "implication_verified: true, hidden_assumptions: false, extra_assumptions: []}; then propose lifecycle integrated "
            "for the target claim with the route_id and copy resolved_debt_ids onto that status-transition operation. "
            "Only list debts that the integrated route genuinely closes. Otherwise add a blocking debt or leave the result as certified partial progress."
        )
    if actor_role == "formal_backend":
        return (
            "Only attach formal_backend_result and propose formally_verified if a real formal backend result is present in the context "
            "or produced by this session. Otherwise add a formalization debt or handoff artifact; do not pretend informal reasoning is formal."
        )
    if actor_role == "counterexample_validator":
        return (
            "Validate candidate counterexamples independently. Only attach confirmed_counterexample and propose refuted if the counterexample is fully checked."
        )
    if actor_role == "writer":
        return (
            "Act as a mathematically careful proof-writing agent, not a ledger dumper. Write polished, LaTeX-friendly mathematical "
            "exposition: distinguish prose from formulas, put genuine formulas and mathematical objects in inline/display LaTeX math, "
            "use theorem/lemma/proof-style paragraphs when appropriate, and separate certified facts from conjectural, plausible, failed, "
            "or unresolved material. Make the main body read as mathematics: statement, proof, certification status, and references. "
            "Because the response must be a JSON patch, every LaTeX backslash inside artifact content must be JSON-escaped as a doubled "
            "backslash, for example write \\mid in the final mathematical text as \\\\mid in the JSON string. If unsure, prefer plain "
            "mathematical English over a LaTeX command that risks invalid JSON. "
            "Follow disciplined mathematical writing practice: theorem and lemma statements must be self-contained; every displayed "
            "formula must be part of a sentence with surrounding prose; do not start a sentence with a bare symbol; avoid raw prose "
            "shorthand such as =>, forall, exists, iff, or wlog when ordinary mathematical English is clearer; use reader-directed "
            "'we' when it helps the proof flow; introduce definitions and hypotheses before using them; and never write 'clearly', "
            "'obviously', or 'straightforward' unless the next sentence gives the actual reason. "
            "Do not dump raw graph metadata such as tags, parent claim JSON, evidence-id JSON, file paths, or lifecycle bookkeeping into "
            "the exposition; use such data only to choose what to cite or to write a short certification note when needed. "
            "If the root claim is integrated, assemble a self-contained final proof from the integrated route, "
            "verified inferences, verified premises, and cited artifacts. Attach exactly one final_proof artifact with content containing "
            "the polished proof and metadata including claim_id='root', route_id, proof_status='written_from_integrated_route', "
            "result_kind='exact'|'equivalent'|'stronger', proved_statement, relation_to_target, and source_artifact_ids. "
            "All writer content artifacts are exported by the workflow as LaTeX and PDF sidecars, so write complete LaTeX-friendly prose "
            "in the artifact content and do not attach separate ad-hoc PDF artifacts. "
            "Use citations as mathematical evidence only when they are present in verified artifacts or retrieval_cards with exact source "
            "identifiers and exact theorem/proposition/lemma numbers or page/section locations. When citing a theorem, name the source, "
            "the exact theorem number/location, the statement used, and any hypotheses checked. End every final_proof, partial_proof_report, "
            "stop_summary_report, proof_compression_report, or writer_report with a 'References' section written by the writer, "
            "using the literal markdown heading '## References'. The section "
            "must use this format for external mathematics whenever the data is available: Author(s), title of paper/book, exact "
            "Theorem/Proposition/Lemma/Corollary number or page/section, arXiv/DOI/URL if available, and the proof step or claim it supports. "
            "For internal artifacts, cite artifact title/id and role only after the external references. If there are no external references, "
            "state that the reference list is empty and that the report was written by the Albilich writer from internal artifacts. "
            "If the action has proof_compression_required=true and the root is not integrated, do not write a final proof; instead "
            "attach a proof_compression_report artifact that compresses verified progress, identifies redundant lemmas/routes, and "
            "states the shortest current route outline plus remaining proof debts. "
            "If the action has write_existing_proofs_on_stop=true, the workflow has stopped before a solved final proof. Do not write "
            "a final_proof unless the root is already integrated. Instead attach exactly one stop_summary_report or partial_proof_report "
            "artifact recording the stop reason, public result kind, strongest verified/integrated claims, exact statements proved so far, "
            "source artifact ids/paths, relation to the original target, unresolved debts/gaps, and the shortest honest route outline. "
            "For stop-writer reports, keep the artifact content compact and JSON-safe: use plain prose where possible, avoid display math and "
            "unnecessary backslashes, do not paste long artifact excerpts, and keep content under roughly 8000 characters. "
            "If the result is partial or unresolved, copy every manifest.partial_result_receipt.verified_side_lemmas item into a "
            "'Verified Side Lemmas' section and every manifest.partial_result_receipt.other_claims item into a 'Claim Status Ledger' "
            "section, preserving claim_id, validation_status, lifecycle_status, relation_to_target, statement, conditions, evidence ids, "
            "and the proof_artifacts proof/report material for each verified side lemma; rewrite surrounding prose for readability but "
            "do not change claim ids, statuses, mathematical content, or certification level. "
            "Label every result as exact, equivalent, stronger, partial, conditional, failed, or unresolved; preserve gaps explicitly. "
            "If the result is not exact, explicitly say in the proof artifact metadata and text what stronger/equivalent result was proved "
            "and why it implies the target. Do not verify, refute, integrate, add new mathematical claims, or use uncited plausible material. "
            "If the integrated route is missing or the proof cannot be written honestly, attach a short writer_report artifact and add "
            "a blocking proof debt explaining the missing piece."
        )
    if actor_role == "literature_researcher":
        if mode == "retrieve":
            return (
                "Act as an adaptive claim-driven literature researcher. Follow manifest.research_task.librarian_level: scout cheaply for "
                "candidate sources, reader extracts theorem cards from promising sources, and research_librarian spends serious reasoning "
                "only on hard theorem matching, hypothesis translation, or implications that may close a debt. Stop once a genuinely useful "
                "card is found; do not keep searching merely to fill cards. Before caching a new card, check manifest.retrieval_cards for the "
                "same theorem (same source and statement, even paraphrased): if a card already covers it, do not cache a near-duplicate — add "
                "the missing precision (exact theorem number, page, hypotheses) via source_adaptation_notes referencing the existing card_id. "
                "If manifest.research_task.researcher_search_request is present, answer that exact request first and copy its "
                "search_request_id and source_request_artifact_id into every cache_retrieval_card applicability object and every "
                "source_adaptation_notes metadata object you produce. If no useful source exists in the allowed scope, cache a "
                "no_useful_result_found retrieval card tied to the search_request_id with the strongest failed queries and reason. Search local "
                "references, theorem_library entries, manifest-listed artifact paths, manifest-listed or source-card-linked downloaded/extracted source text, and .refs material before or alongside live search; when "
                "workflow_action.local_theorem_search_allowed=true, local-only search is acceptable even if web_search is disabled. Do not repeat "
                "old benchmark result directories, raw logs, prior problem folders, or experiment reports unless manifest.local_search_policy "
                "explicitly lists them as current proof-state artifacts or the user asked for provenance/audit. Do not treat old run outputs as "
                "mathematical evidence. Do not repeat "
                "a search already answered by cached retrieval cards or theorem_library entries; synthesize or refine the exact missing hypothesis instead. "
                "When workflow_action.exact_theorem_search_required=true or workflow_action.support_lemma_precheck_required=true, treat this as an exact theorem lookup: "
                "return at most one primary retrieval card and one linked source handoff with theorem number or page/section, statement, hypotheses, and applicability. "
                "Do not continue bibliography after the first checked useful match; include at most one supporting source only when it closes a named hypothesis. If no such theorem is found, "
                "cache one no_useful_result_found card with the strongest failed query and do not broaden into general survey notes. Search against "
                "the root theorem as well as the selected local "
                "obligation, because a result that reframes the root theorem is often more valuable than a narrow lemma hit. Download or "
                "cache source text/PDF metadata when the source is plausibly relevant, record source_version/content_hash, and make the "
                "source reproducible enough for a later writer reference. For live internet sources, use the Codex web-search/source-view "
                "capability; do not use shell network commands such as curl, wget, or python requests, because the child shell sandbox may "
                "fail DNS/network access or return empty content. Shell commands are only for exact local file paths already present in the manifest; do not derive paths from artifact ids or scan sibling artifacts. "
                "Skim/search within sources first, and read a whole source only "
                "when needed to check hypotheses, resolve conflicts, solve nontrivial theorem matching, or inspect an unusually related result. "
                "If you find an exact, stronger, or equivalent theorem that proves the root target with no missing hypotheses, declare a "
                "program_victory_candidate=true in applicability and in source_adaptation_notes metadata, set theorem_matching_status to a "
                "checked match, set implication_to_target_verified=true when the implication is checked, and stop searching; the next role "
                "will certify the citation rather than asking the system to reprove known mathematics. "
                "Return cache_retrieval_card operations with exact_statement, source_identifiers, hypotheses, local_definitions, applicability, "
                "missing_hypotheses, source_location, source_version, and content_hash. In applicability, include target_id, classification, "
                "relation, theorem_matching_status, theorem_matching_confidence, implication_to_target_verified, and classify the result as one of direct_match, "
                "stronger_match, equivalent_reformulation, conditional_match, partial_match, method_match, obstructing, background, "
                "irrelevant, or no_useful_result_found. For mathematical citations, source_identifiers must include enough bibliographic data "
                "to support writer references in this exact shape whenever possible: author, title, theorem_number or proposition_number or "
                "lemma_number or corollary_number, section/page, arxiv/doi/url, venue, and year. When a source is plausibly usable, also "
                "attach a source_adaptation_notes artifact recording the local statement translation, checked hypotheses, missing hypotheses, "
                "definition translation, exact source location, and the proof obligation or debt it may close; if the source_adaptation_notes "
                "metadata names source_card_id or retrieval_card_id, include a cache_retrieval_card operation for that exact id in the same patch. "
                "This is the handoff to the "
                "researcher, not just bibliography. Retrieval cards are literature evidence only; "
                "do not verify, refute, or integrate anything."
            )
        if mode == "synthesize_sources":
            return (
                "Act as a source-synthesis mathematical literature researcher. Your job is to combine retrieval cards, theorem-library entries, "
                "and relevant artifacts into a concise synthesis report, not to certify a proof. Make a table of source result, "
                "exact theorem location, hypotheses, definitions, which target obligation it covers, and which obligation remains uncovered. "
                "When multiple sources cover complementary hypotheses, identify the exact compatibility lemma needed to combine them. "
                "If the synthesis reveals a promising route, add at most one root-local route or at most three coarse mathematical claims. "
                "If it reveals a missing compatibility condition, add one precise blocking debt with debt_type='missing_hypothesis' or 'gap'. "
                "Attach a source_synthesis_report artifact with metadata including covered_obligations, uncovered_obligations, "
                "candidate_compatibility_lemmas, source_card_ids, theorem_library_entry_ids, and recommended_next_action. "
                "Also attach source_adaptation_notes when the synthesis translates an external theorem into a local proof obligation. "
                "Do not mark claims verified, refuted, or integrated; do not perform citation certification."
            )
        if mode == "audit_definitions":
            return (
                "Act as a definition-auditing mathematical literature researcher. Compare the target statement with the local definitions in retrieval cards, "
                "theorem-library entries, and artifacts. Check whether terms such as ring hypotheses, local/noetherian/completion/formal fiber, "
                "smooth/stable/projective, and other domain-specific words mean the same thing in the source and target. Attach a "
                "definition_audit_report artifact with metadata: audited_source_ids, matched_definitions, mismatched_definitions, "
                "hidden_hypotheses, notation_translation, verdict='definitions_match'|'definitions_mismatch'|'needs_more_source_context', "
                "and recommended_next_action. If definitions do not match, add one precise missing_hypothesis or missing_reference debt. "
                "If they match, you may add a route or claim saying a verifier should certify the exact citation, but do not verify, refute, "
                "integrate, or certify citations yourself."
            )
    if actor_role == "phd_advisor":
        if mode == "regulate_decomposition":
            return (
                "Act as a decomposition regulator, not a new decomposer. Read the failed_decomposition_plan or blocked decomposition_plan, "
                "the branch proof dossiers, verifier reports, source handoffs, active debts, and recent runs. Classify the failure as exactly "
                "one of: proof_execution_error (the plan is sound but a branch proof needs repair), plan_gap (the plan misses a case, "
                "dependency, citation hypothesis, or assembly implication), strategy_failure (the whole approach is mathematically wrong), "
                "or branch_incompatibility (parallel branches introduced incompatible assumptions or definitions). Attach an advisor_report "
                "or key_failure_analysis artifact with metadata failure_classification, affected_plan_id, affected_branch_ids, kept_branch_ids, "
                "revised_dependency_edges, recommended_next_action, and whether to Revise_Proof, Revise_Plan, or Rewrite. Preserve verified "
                "branches whenever possible. Do not verify, refute, integrate, or create administrative subgoals."
            )
        if mode == "triage_routes":
            return (
                "Act as the human-style PhD advisor for the proof project: you are responsible for steering the next research direction, "
                "not merely summarizing the state. Inspect the route scoreboard, active debts, active trunk pressure, and recent runs. "
                "Every advisor patch must make one decisive steering recommendation: keep/repair one route, block/abandon one route, "
                "promote one central obstruction, or send one exact task to researcher, villain, verifier, or literature. "
                "You also supervise both work-mode loops (Nagata working mode: prover and refuter equally capable). The researcher "
                "rotates through online (live literature search), offline (pure proof thinking), and cas (bounded computation) passes; "
                "the villain runs the same loop computation-first. manifest.researcher_mode_state shows both recent mode histories and "
                "any active directives. When the researcher should search more, think more, or experiment more, add metadata "
                "directed_researcher_mode='online'|'offline'|'cas' with directed_researcher_mode_reason (one sentence naming what to "
                "search for, prove, or compute) and optionally directed_researcher_mode_steps (1-3, default 1) to your advisor_report. "
                "When the VILLAIN should hunt published counterexamples/prior art (online), construct counterexamples by hand "
                "(offline), or run adversarial sweeps (cas), add directed_villain_mode with directed_villain_mode_reason and optional "
                "directed_villain_mode_steps the same way; the two directives are independent. Direct online when a missing known "
                "theorem, survey, or counterexample family is the bottleneck; offline when search keeps returning nothing and the "
                "attack needs invention or repair; cas when a finite computation or example sweep would decide the next step. Do not "
                "issue a directive when the default rotation is already doing the right thing. "
                "Do not use CAS yourself; when computation is needed, request a bounded researcher or villain check with exact acceptance criteria. "
                "Keep route_triage_report compact: keep/repair/block/abandon, one reason, one next action, and no broad narrative unless new "
                "mathematical evidence changed the route decision. "
                "If manifest.workflow_action.advisor_evidence_synthesis_required=true, act as a parallel evidence-synthesis advisor: keep the "
                "original root problem in view, read the fresh artifacts named in workflow_action.advisor_evidence_signal, and think hard about "
                "how the current evidence could become a full proof. Attach a compact advisor_report with metadata current_best_plan, "
                "bottleneck_obligation, remaining_gaps, next_decisive_task, route_decisions, next_role, next_target_id, next_task_acceptance_criteria, "
                "recommended_next_action, advisor_followup_required=true, and risks_or_hidden_assumptions; include candidate_full_proof_strategy only when "
                "you genuinely see a proof-shaped strategy that the researcher should turn into proof-state "
                "material, set proof_candidate=true, but still do not verify, refute, integrate, or close debts yourself. "
                "If manifest.workflow_action.post_integration_compression_required=true, compress the newly integrated fact into the shortest "
                "current proof spine, state exactly what remains to finish the root theorem, and hand the next role one theorem-level task "
                "rather than a route inventory. "
                "When you decide one bottleneck is decisive for the root, say so explicitly in advisor_report metadata with "
                "advisor_followup_required=true, bottleneck_obligation, next_decisive_task, next_role, next_target_id, route_decisions, "
                "recommended_next_action, and triage_status=decisive_root_bottleneck. The scheduler treats that as executive steering, so "
                "use it only when the next researcher should work that theorem before older local repairs. "
                "If manifest.workflow_action.verifier_loop_classification_required=true, stop the verifier-repair loop before asking for another patch. "
                "Classify the named route as exactly one of local_repair_or_typo, missing_theorem, bad_strategy, or abandon_or_pause_route; explain "
                "which verifier_gap_debt_ids force that classification, and give one next mathematical task with acceptance criteria. If the route "
                "still looks repairable, ask the researcher for the missing theorem or local repair; if not, pause or abandon the route and name the "
                "replacement bottleneck. Do not certify the proof yourself. "
                "If manifest.workflow_action.advisor_obstruction_conversion_required=true, a researcher already stalled while trying to convert the "
                "fresh obstruction. Do the compact mathematical triage yourself: classify the obstruction as route_killing_obstruction, "
                "route_repair_signal, missing_hypothesis, generalized_construction_needed, or candidate_counterexample_needing_validator; attach "
                "a route_triage_report or advisor_report with the classification, the affected route or root bottleneck, and exactly one next role/task. "
                "Do not ask for the same broad researcher synthesis again unless you narrow it to one lemma or construction test with acceptance criteria. "
                "If manifest.workflow_action.stream_stall_recovery_required=true, the preceding researcher failed from a Codex transport retry stall, "
                "not from a mathematical refutation. Do not summarize the infrastructure problem as proof evidence. Instead, preserve the current "
                "mathematical state, choose the smallest next proof obligation or route repair, and hand the researcher one compact task with "
                "clear acceptance criteria. "
                "Keep at most three serious root-local proof trunks active. For stalled or low-yield routes, either abandon the route, add "
                "one precise obstruction debt, or attach a route_triage_report explaining why it should pause. Prefer preserving routes with "
                "verified inferences, high root impact, small root distance, exact citation candidates, clear next verifier actions, or "
                "active blocking debts whose owner or suggested_next_target is the route or its conclusion claim. Do not abandon those "
                "debt-bearing routes; mark them blocked with a failure_fingerprint and recommend the next proof-repair/workbench action for the debt. "
                "Attach metadata with kept_route_ids, paused_or_abandoned_route_ids, obstruction_debts, active_trunk_count_before, "
                "active_trunk_count_after, and recommended_next_action. Do not verify, refute, integrate, or add fine-grained subclaim sprawl."
            )
        return (
            "Act as a strategic PhD advisor and senior research mathematician, not a schema designer. Your job is to steer the proof search "
            "toward closure: identify the live bottleneck, choose which route deserves proof effort, retire routes that are blocked, and give "
            "the next role a concrete mathematical task with acceptance criteria. Read the researcher's proof dossiers, source_adaptation_notes, "
            "and research_diagnostic artifacts before proposing management actions. First try to repair the current mathematical route or identify "
            "a direct proof trunk. Decomposition is primarily researcher-owned; as advisor, triage, prune, and ask for key_failure_analysis "
            "before another split rather than making decomposition your default output. "
            "You also supervise the researcher's and the villain's online/offline/cas work-mode loops "
            "(manifest.researcher_mode_state shows both mode histories and any active directives). When the researcher should search "
            "more, think more, or experiment more, add metadata directed_researcher_mode='online'|'offline'|'cas' with "
            "directed_researcher_mode_reason and optionally directed_researcher_mode_steps (1-3) to your advisor_report; use "
            "directed_villain_mode (+reason, +steps) the same way to point the refuter at published counterexamples (online), hand "
            "construction (offline), or adversarial computation (cas). The scheduler imposes each directive on the next pass(es) of "
            "that role. Use them sparingly — only when the default rotation is misallocating effort. "
            "When proof architecture pressure is visible, behave like a global research director: name the current best plan, state route "
            "contracts for the kept routes, reduce the whole project to one bottleneck obligation, and recommend exactly one next decisive "
            "research action. A blocked route is an explicit pause; a stalled route is a health warning from repeated blockers. Do not revive "
            "either without a concrete repair contract and acceptance criteria. "
            "If you see a proof-shaped synthesis, hand it to the researcher as a candidate proof route or proof_dossier target; do not verify, "
            "refute, or integrate it yourself. "
            "Keep advisor reports compact by default: current_best_plan, bottleneck_obligation, next_decisive_task, route_decisions, and "
            "acceptance criteria. Use broader narrative only when new evidence changes the proof architecture. "
            "Decomposition is allowed only after real mathematical "
            "diagnosis: use an existing research_diagnostic/decomposition_plan or attach one recording direct attempts, pattern matches, "
            "examples/counterexamples, the failure point, and why the proposed subgoals follow. If decomposition is genuinely needed, "
            "recommend at most three coarse mathematical trunk obligations, each visibly close to the target theorem and carrying high root_impact; "
            "avoid chains of tiny administrative subclaims. "
            "If manifest.workflow_action.frontier_pressure.over_claim_cap=true, do not add more route-less claims; instead repair or "
            "select one existing trunk, add inference evidence for the selected route, or explain the nearest obstruction in an advisor_report. "
            "Do not create JSON/schema/validator/serialization/metadata/candidate-inventory/bookkeeping targets unless the theorem "
            "itself is about that formal object. Such items may be mentioned in an advisor_report artifact, but they are not proof "
            "subgoals. If manifest.workflow_action.duplicate_work_guard=true, do not ask for another broad pass over the same target. "
            "Name the exact repeated task, preserve useful previous content, and recommend one sharper next delta: verifier check, route repair, "
            "source synthesis, regulator decision, or abandonment of a low-yield route. "
            "If a computation would clarify a route, do not run it yourself; ask researcher or villain for one bounded CAS check with backend/task, "
            "finite scope, expected decisive output, and stop condition. "
            "If the current debt is already far from the target theorem or mainly about bookkeeping, stop decomposing: attach "
            "a concise advisor_report artifact summarizing the useful partial mathematical result, its relation to the original target "
            "(exact, stronger, equivalent, partial, conditional, or unrelated), and the nearest remaining mathematical obstruction; then "
            "add at most one blocking proof debt pointing back to that obstruction. Do not verify, refute, or integrate anything."
        )
    if actor_role == "villain":
        return (
            _villain_work_mode_guidance(action)
            + "Act as the villain: an independent refutation researcher whose job is to attack the target, not to help the proof branch. "
            "Try to falsify the target by stress-testing hypotheses, edge cases, and examples. Treat this as a bounded adversarial "
            "research pass: find a genuine obstruction, candidate counterexample, or hypothesis mismatch, or report that the obvious "
            "stress tests did not break the claim. Attach candidate_counterexample artifacts only for concrete falsifying candidates "
            "that should be independently validated; use route_obstruction, hypothesis_gap, construction_failure, or necessary_condition "
            "artifacts for softer route-level stress signals. Mark claims challenged when there is a serious candidate. Use CAS tools for bounded example searches or algebraic checks "
            "when they can materially test the claim, and attach cas_experiment_report with backend, code, finite scope, output summary, "
            "and conclusion when the computation matters. When you find an obstruction, make it actionable for route conversion: include "
            "metadata target_id, route_id when known, obstruction_type, failed_hypothesis or example_family, and the exact claim or route "
            "it threatens. Do not verify, refute, or integrate anything; confirmed "
            "refutations belong to counterexample_validator."
        )
    if actor_role == "researcher":
        direct_solve_guidance = ""
        if mode == "prove" and not route_id:
            direct_solve_guidance = (
                "This is a direct-solve researcher action. First try to solve the target itself in local notation: direct proof, known theorem "
                "pattern match, source handoff adaptation, examples/counterexamples, and hypothesis check. Do not reduce immediately merely "
                "because reduction is available. Reduce or decompose only after the direct attempt identifies a natural mathematical structure, "
                "missing theorem, case split, construction, filtration, equivalent reformulation, or genuine obstruction; record that attempt in "
                "the proof_dossier or research_notebook. "
            )
        return (
            _researcher_work_mode_guidance(action)
            + direct_solve_guidance
            + "Act as a working mathematician, not a graph manager. Your default output is a proof_dossier or proof_blueprint artifact, "
            "with verifier-ready inferences only when the artifact contains the actual local argument. Use an Albilich-native research loop: "
            "try direct consequences, pattern-match known theorems, test examples and counterexamples, adapt any source_adaptation_notes, "
            "run several independent proof attacks when the first attack stalls, repair the selected route, then decide whether a new "
            "mathematical milestone is necessary. Use staged attacks to save time: on workflow_action.research_attack_stage='fast', make one "
            "sharp proof/citation attempt, one hypothesis check, and one example/counterexample sanity check before deciding the next artifact; "
            "on ordinary research actions, deepen only the attacks that changed the mathematical state. Spend most tokens on the mathematical "
            "attack itself; keep metadata and reporting compact unless workflow_action.proof_architecture_required=true. Attach a research_notebook only "
            "when it changes later choices by recording attack branches, failed lemmas, citations considered, CAS checks, and why the chosen next step is the cheapest serious "
            "mathematical move. Stop a research pass once it has one concrete output: a verifier-ready proof candidate, a precise literature "
            "search request, a named citation with checked local deduction, a candidate counterexample/obstruction, or a decomposition_plan "
            "whose branches naturally assemble the target. Write real mathematics in the proof_dossier: definitions in local notation, lemmas used, "
            "proof attempt, obstruction, examples, source translations, and a self-check of hidden assumptions. Prefer advancing the manifest graph "
            "frontier: root, target, local route premises, active mathematical debts, and claims with small root_distance. "
            "If workflow_action.checkpointed_synthesis_required=true, preserve one natural mathematical checkpoint before the pass can be lost: "
            "attach a proof_dossier/proof_blueprint/route_obstruction/construction_failure/source_adaptation_notes/cas_experiment_report whose metadata "
            "includes checkpoint_kind, global_context_summary, local_obligation, what_changed, and next_decisive_action. This checkpoint is not an "
            "invitation to split the problem into tiny formal fragments; keep the global plan visible and save the single proof move, obstruction, "
            "or bridge theorem that actually changed. "
            "If workflow_action.proof_construction_required=true, do not behave like a reducer or manager. The internal mode may be reduce, "
            "but the mathematical task is to prove the selected route: write the actual argument, fill the inference, adapt exact citations, "
            "or identify the precise obstruction that prevents the route from becoming verifier-ready. Do not decompose unless the proof attempt "
            "itself exposes a necessary case split or construction. If workflow_action.deep_research_required=true, spend the pass like a serious "
            "working mathematician: try several proof attacks, compare them, and end with the strongest proof dossier, citation route, or obstruction. "
            "If workflow_action.no_content_research_guard=true, the recent run history produced too little durable mathematics; this pass must "
            "emit one concrete mathematical artifact such as a proof_dossier, proof_blueprint, source_adaptation_notes, cas_experiment_report, "
            "candidate_counterexample, or a precise literature_search_request. "
            "Do not attach research_diagnostic or research_notebook as ornamental paperwork. Such artifacts must include metadata artifact_roi "
            "with one of: verifier_ready_route, route_repaired, route_blocked_or_abandoned, bottleneck_narrowed, debt_closed_or_sharpened, "
            "source_or_cas_changed_next_step, or failed_method_do_not_retry. "
            "If workflow_action.bridge_lemma_workbench_required=true, this is construction closure, not broad synthesis. Treat "
            "manifest.central_obstruction as the named local theorem to attack: state it precisely, produce sublemmas, toy cases, "
            "obstruction cases, acceptance criteria, and either a proof_dossier, route_obstruction, construction_failure, sharper "
            "sub-bridge, or verifier-ready route/inference. If the output is an obstruction, construction_failure, or sharper sub-bridge "
            "rather than a verifier-ready proof, also include an update_debt for workflow_action.central_debt_id or one new precise "
            "blocking add_debt so the next workbench targets the narrowed obligation instead of repeating this pass. "
            "If workflow_action.closure_pressure_required=true, do not request another "
            "broad search; prove the bridge, refute it, or make a strictly narrower theorem/case split. Consult manifest.negative_result_ledger "
            "before reusing an old idea. Use manifest.proof_architecture_templates only when a template matches the domain. "
            "If workflow_action.decisive_theorem_test_required=true, work only the theorem-level obligation in "
            "manifest.workflow_action.decisive_theorem_test: state the exact theorem/counterexample test, then prove it, refute it, "
            "find a precise citation with checked hypotheses, or replace it with one strictly narrower theorem-level debt. Do not write "
            "a broad route inventory or split the problem into bookkeeping subgoals. "
            "If workflow_action.bottleneck_lock_required=true, diagnostic cooldown is active. Spend the pass on the named bottleneck itself: "
            "prove it, refute it, find an exact citation with checked hypotheses, or replace it with one strictly narrower theorem-level debt. "
            "Do not attach a broad research_diagnostic, route inventory, or management-only research_notebook as the primary output. If the "
            "obligation is too large, extract one verifier-checkable sublemma and explain exactly how that sublemma assembles back into the "
            "parent proof route. Keep side branches under an ROI cap: they must produce a concrete proof dossier, obstruction, counterexample, "
            "exact citation, bounded CAS result, or verifier-ready inference. "
            "If workflow_action.executive_advisor_lock_required=true, the PhD advisor has made a binding steering decision. Work the named "
            "advisor bottleneck now, respect paused/blocked route decisions, and do not detour to older local proof-candidate cleanup unless it "
            "directly proves or refutes that bottleneck. "
            "If workflow_action.hard_theorem_attack_required=true or workflow_action.theorem_workbench_required=true, spend the pass as a hard "
            "theorem workbench: first attempt the actual proof/counterexample, then isolate the exact failed lemma if needed. Do not end with "
            "a route inventory, broad literature request, or management-only notebook. "
            "If workflow_action.near_solution_spine_synthesis_required=true, treat the manifest as a near-proof portfolio. Assemble the shortest "
            "root proof spine, identify the single theorem-level gap, and attack that gap immediately before creating any new side branch. "
            "If workflow_action.proof_spine_mode_required=true, compress your output into a short proof spine: 3-6 named lemmas/steps, "
            "dependency arrows, an assembly argument to the target/root, and exactly one remaining theorem-level gap if not solved. "
            "If any lemma is already locally proved, create or repair a route/inference so strict verification can run; do not leave it as "
            "mere research progress. "
            "If workflow_action.duplicate_math_guard_required=true, compare against recent proof artifacts and do not restate an already "
            "accepted theorem unless you use it to attack the newest child debt. "
            "If workflow_action.near_miss_memory_required=true, name the strongest failed route in one sentence and either remove that "
            "obstruction, promote it to a lemma, or abandon the route precisely. "
            "If workflow_action.villain_obstruction_to_lemma_required=true, try to convert construction failures or counterexample pressure "
            "into a route obstruction, necessary condition, or usable proof step. "
            "If workflow_action.cas_check_recommended=true or manifest.cas_trigger_policy.recommended=true, run a bounded computation when "
            "a toy model, construction lemma, finite case, or obstruction can change the next mathematical decision. "
            "If workflow_action.proof_route_conversion_required=true, this is a proof-critical scheduling repair, not a new research pass. "
            "Read the named proof_candidate_artifact_id and either create exactly one active sufficient route plus one untested/plausible "
            "inference whose evidence_artifact_ids include that proof dossier, or attach one short research_diagnostic explaining why the "
            "candidate is not verifier-ready and add one precise blocking debt. Do not request literature or decompose before making that "
            "route/diagnostic decision. "
            "If workflow_action.research_synthesis_required=true, this is not another small patch pass. Act as the mathematical owner of the "
            "target: read the recent proof, literature, counterexample, CAS, and decomposition signals; compare the approaches; state what "
            "changed mathematically; kill, merge, or prioritize routes; and produce one paper-like synthesis note with the next serious proof "
            "move. If workflow_action.approach_portfolio_synthesis_required=true, explicitly compare direct proof, citation/theorem, construction/CAS, "
            "and counterexample branches. If workflow_action.no_result_search_synthesis_required=true, do not ask for another broad theorem search; "
            "turn the repeated no-useful-result cards into a sharper construction attempt, repaired route, precise obstruction, or one strictly "
            "narrower search request. If workflow_action.global_synthesis_required=true, behave like a mathematician assembling a paper from "
            "a near-proof portfolio: prove or seriously attempt the missing bridge theorem from the endpoint obstructions, local lemmas, "
            "and citations already in the manifest. Use citations as components when their hypotheses match, but do not stop at 'no exact "
            "source found'; either produce a verifier-ready route/inference, a precise theorem-level gap, or one narrowly formulated lemma "
            "that would finish the proof. If workflow_action.advisor_followup_required=true, treat the named advisor_report as immediate "
            "consulting from a mathematician who is also trying to solve the original problem. Convert its candidate strategy into proof-state "
            "material when possible: add or repair a route, add inference evidence, attach a proof_dossier, or state the exact remaining gap. "
            "If workflow_action.advisor_proof_candidate=true, do not leave the proof sketch as advice; translate it into a route/inference/"
            "proof_dossier for strict verification. Do not mark it verified yourself. "
            "If workflow_action.obstruction_route_conversion_required=true, treat the villain obstruction or candidate "
            "counterexample as a route-level research signal: classify it as route_killing_obstruction, route_repair_signal, missing_hypothesis, "
            "generalized_construction_needed, or candidate_counterexample_needing_validator, then attach a proof_dossier or research_notebook "
            "that chooses exactly one next action: repair the route/inference, pause or abandon the route with a precise reason, create an "
            "approach_portfolio decomposition plan, request one narrow source, or send the candidate counterexample to validation. "
            "If workflow_action.global_obstruction_architecture_required=true, treat the run as a possible false-root situation: build a "
            "global obstruction architecture with host/composition-factor/quotient constraints, promote obstruction lemmas into claims/routes "
            "for verification, and stop defaulting to repair of the positive construction route unless the obstruction analysis genuinely supports it. "
            "If workflow_action.creative_proof_attack_required=true, enter wild-but-disciplined mathematician mode. Spend this pass on hard "
            "mathematics, not on workflow narration: own one bottleneck for the whole pass, draft the most plausible full proof with every "
            "gap explicitly labeled, invert the central obstruction by asking what construction or theorem would evade it, generate one or two "
            "speculative bridge theorems with exact hypotheses and known failure modes, compare one nearby-method analogy only if it produces "
            "a concrete lemma, and autopsy the strongest failed route in one sentence. The output should be a proof_dossier or proof_blueprint "
            "unless you have a genuine route_obstruction/construction_failure; do not attach a management-only research_notebook or broad "
            "inventory. End with exactly one of: a verifier-ready route/inference, a narrower theorem-level proof debt, a precise literature/CAS "
            "request, or a route-killing obstruction. Do not mark anything verified yourself. "
            "Use manifest.researcher_packet as the active workbench when present; if it contains source_adaptation_artifacts, translate those "
            "sources into the local proof dossier instead of merely citing them. If workflow_action.source_adaptation_digest_required=true, "
            "digest the named source artifact first: either turn it into a local proof dossier/inference, record the exact missing hypothesis, "
            "or attach a sharper literature_search_request for the remaining theorem. "
            "If workflow_action.proof_architecture_required=true, stop doing isolated local moves. Attach a proof_blueprint, proof_dossier, "
            "or research_notebook whose metadata includes current_best_plan, route_contracts, bottleneck_obligation, repair_attempt, "
            "speculative_proof_attempt, remaining_gaps, next_decisive_action, and paused_route_ids_respected. The current_best_plan must be "
            "one plan, not a menu. Each route_contract should say hypotheses, proof obligation, available evidence, missing evidence, acceptance "
            "criteria, and abandonment criteria. If workflow_action.obligation_reduction_required=true, name the smallest mathematical lemma or "
            "debt whose resolution would unlock the plan. If workflow_action.speculative_proof_required=true, write a possible proof skeleton "
            "and explicitly mark every unproved step. If workflow_action.repair_loop_required=true, try to repair the strongest existing route "
            "before opening a new trunk. If workflow_action.dead_route_suppression_required=true, keep blocked/stalled routes out of ordinary "
            "proof construction unless you provide a concrete repair contract. "
            "When independent work exposes a precise missing external "
            "input, attach a literature_search_request artifact with metadata target_id, route_id, search_request_id, query, missing_theorem, "
            "proof_obligation, acceptance_criteria, forbidden_sources, and librarian_level; make it specific enough that the librarian can "
            "search like a collaborator rather than doing a generic survey. Cite external mathematics responsibly when it genuinely saves "
            "time or prevents rediscovering known theorems: record the source theorem number/location or precise page/section, hypotheses, definition translation, "
            "and the exact local deduction. A cited theorem may support a verifier-ready inference only when the local implication is written "
            "clearly enough for the strict verifier to check. Use CAS tools when computation is likely to clarify an example, obstruction, "
            "finite case, normal form, or algebraic calculation: discover available backends, run one bounded script, poll directly, repair "
            "at most one simple script error, stop runs that no longer change the mathematical next step, and attach cas_experiment_report "
            "with backend, code, output summary, scope, conclusion, and proof relevance. Treat CAS output as evidence, examples, or checked "
            "finite computation; explain any theorem-level use in the proof dossier. Reuse existing claim_ids when a proposed statement is an "
            "obvious restatement or duplicate. For a selected route or proof_repair_required action, repair the route first: attach a "
            "proof_dossier/proof_blueprint and add or update the inference that the verifier should check. Before emitting a verifier-ready "
            "inference, include a self_check section saying which hypotheses, definitions, boundary cases, and dependencies were checked. "
            "For an existing decomposition branch, stop the branch once you have one of four concrete outcomes: a verifier-ready proof candidate, "
            "a counterexample or obstruction, a reduction to a named theorem/citation with checked hypotheses, or a precise blocker/debt. "
            "If manifest.workflow_action.duplicate_work_guard=true, do not repeat the previous broad attack. State what was tried, what changed, "
            "and produce only the missing delta needed for verifier/librarian/advisor to act. "
            "For reduce actions without workflow_action.proof_construction_required=true, keep reduction narrow: produce a genuinely simpler theorem, "
            "natural case split with assembly argument, citation reduction with checked hypotheses, construction, or obstruction. Do not use reduce "
            "as a generic place to push work around. "
            "Do not send verifier-known gaps "
            "as plausible inferences. Add new trunks only when they are root-local, mathematically substantive, and likely to help close "
            "the target route. Treat decomposition as a natural mathematical proof move, not only a panic button after being stuck. "
            "Use decomposition_plan when the theorem's shape calls for natural_case_split, standard_reduction, parallel_ingredients, "
            "approach_portfolio, construction_and_checks, citation_adaptation, induction_or_filtration, or equivalence_reformulation; do not create "
            "bookkeeping subgoals. Before adding decomposition claims or routes, attach a decomposition_plan artifact with metadata "
            "decomposition_plan_id, parent_claim_id, route_id, plan_kind, trigger, subgoal_claim_ids, dependency_edges, "
            "assembly_argument or why_subgoals_imply_parent, and acceptance_criteria. Add optional fields such as parallelizable_groups only "
            "when they change the math. "
            "If workflow_action.decomposition_step_required=true, work the named existing decomposition_plan before proposing another. "
            "If a plan fails, attach failed_decomposition_plan. If workflow_action.decomposition_regulator_required=true, do not propose "
            "another split; let the PhD advisor classify whether this is a proof execution error, plan gap, branch incompatibility, or "
            "strategy failure. If "
            "manifest.workflow_action.research_diagnostic_required=true, a diagnostic/decomposition artifact is mandatory. If "
            "manifest.workflow_action.frontier_pressure.over_claim_cap=true, do not add new route-less claims; work the selected route, "
            "add missing inference evidence, or compress the current route outline instead. Leave verification/refutation/integration to "
            "verifier roles."
        )
    return "Leave verification/refutation/integration to the gated verifier roles."


def _codex_config(key: str, value: Any) -> str:
    return f"{key}={json.dumps(value)}"


def build_codex_command(
    *,
    context_path: Path,
    mode: str,
    model_profile: str = "default",
    extra_args: Sequence[str] | None = None,
    prompt: str | None = None,
    actor_role: str | None = None,
    codex_bin: str = "codex",
    model: str | None = None,
    reasoning_effort: str | None = None,
    sandbox: str | None = None,
    web_search: str | None = None,
    output_last_message: Path | None = None,
    codex_workdir: Path | None = None,
    resume_session_id: str | None = None,
) -> list[str]:
    """Build a scoped Codex command for one Albilich v1 session.

    When ``resume_session_id`` is set, build a ``codex exec resume <id>`` command so
    the same agent continues its prior session (keeping already-read artifacts in
    context) instead of cold-starting.
    """
    prompt = prompt or f"Use the Albilich v1 context in {context_path} and return a structured Albilich v1 patch for mode={mode}."
    argv = [codex_bin, "exec"]
    if resume_session_id:
        argv.extend(["resume", resume_session_id])
    if codex_workdir is not None:
        argv.extend(["-C", str(codex_workdir)])
    if model:
        argv.extend(["-m", model])
    if model_profile and model_profile != "default":
        argv.extend(["--profile", model_profile])
    if reasoning_effort:
        argv.extend(["--config", _codex_config("model_reasoning_effort", reasoning_effort)])
    if sandbox:
        argv.extend(["--sandbox", sandbox])
    if web_search:
        if web_search not in {"disabled", "live"}:
            raise ValueError(f"unsupported web_search policy: {web_search}")
        argv.extend(["--config", _codex_config("web_search", web_search)])
    if output_last_message is not None:
        argv.extend(["--output-last-message", str(output_last_message)])
    argv.extend(extra_args or [])
    argv.append(prompt)
    return argv


def _codex_child_exec_args(extra_args: Sequence[str] | None = None) -> list[str]:
    """Default Albilich children to manifest-only Codex config.

    Patch-producing child sessions should not inherit desktop/plugin MCP tools:
    a single hallucinated tool call can kill a JSON-only proof step before the
    workflow gets a usable patch or diagnostic. Shell, sandbox, model, and the
    explicit web-search setting still come from the command line.
    """

    args = list(extra_args or ())
    use_user_config = os.environ.get(CODEX_CHILD_USE_USER_CONFIG_ENV, "").strip().lower()
    if use_user_config in {"1", "true", "yes", "on"}:
        return args
    guards: list[str] = []
    for guard in DEFAULT_CODEX_CHILD_EXEC_ARGS:
        if guard not in args:
            guards.append(guard)
    disabled_features = {
        args[index + 1]
        for index, token in enumerate(args[:-1])
        if token == "--disable"
    }
    for feature in DEFAULT_CODEX_CHILD_DISABLED_FEATURES:
        if feature not in disabled_features:
            guards.extend(["--disable", feature])
    return guards + args


def prepare_session(
    store: ProofStateStore,
    action: Mapping[str, Any],
    *,
    max_context_chars: int = 12_000,
    model_profile: str = "default",
    resume_session_id: str | None = None,
    resume_since_revision: int | None = None,
) -> Dict[str, Any]:
    actor_role = actor_role_for_action(action)
    context_char_budget = _context_char_budget_for_action(max_context_chars, action, actor_role)
    if resume_session_id:
        # Same-role continuation: send only a compact delta of what changed; the agent
        # keeps the prior manifest + read artifacts in its session context.
        manifest = build_resume_delta_manifest(
            store,
            target_id=str(action.get("target_id") or "root"),
            route_id=str(action.get("route_id") or "") or None,
            action=action,
            since_revision=int(resume_since_revision or 0),
        )
    else:
        manifest = build_context_manifest(
            store,
            target_id=str(action.get("target_id") or "root"),
            route_id=str(action.get("route_id") or "") or None,
            max_chars=context_char_budget,
            action=action,
        )
    context_hash = manifest_hash(manifest)
    path = _context_path(store, action, context_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    capsule = _materialize_evidence_capsule(manifest, path)
    manifest_for_child = capsule["manifest"]
    path = capsule["context_path"]
    path.write_text(render_manifest(manifest_for_child), encoding="utf-8")
    command = build_codex_command(
        context_path=path,
        mode=str(action.get("mode", "prove")),
        model_profile=model_profile,
        actor_role=actor_role,
        extra_args=_codex_child_exec_args(),
        codex_workdir=capsule["workdir"],
    )
    return {
        "session_plan_version": 2,
        "created_at": utc_now(),
        "problem_id": store.problem_id,
        "state_revision": manifest_for_child["state_revision"],
        "resume_session_id": resume_session_id or "",
        "resume_delta": bool(resume_session_id),
        "mode": action.get("mode"),
        "actor_role": actor_role,
        "target_id": action.get("target_id"),
        "route_id": action.get("route_id", ""),
        "context_path": str(path),
        "codex_workdir": str(capsule["workdir"]),
        "context_hash": context_hash,
        "estimated_context_tokens": manifest_for_child.get("estimated_context_tokens", 0),
        "context_char_budget": context_char_budget,
        "search_intent": action.get("search_intent", ""),
        "researcher_work_mode": action.get("researcher_work_mode", ""),
        "work_mode_source": action.get("work_mode_source", ""),
        "model_profile": model_profile,
        "model_routing_hint": _model_routing_hint(action, actor_role),
        "command": command,
        "execute": False,
    }


def _materialize_evidence_capsule(manifest: Mapping[str, Any], context_path: Path) -> Dict[str, Any]:
    """Copy manifest-listed local evidence into a per-context child workspace."""
    capsule_dir = context_path.with_suffix("")
    evidence_dir = capsule_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    child_manifest = json.loads(json.dumps(manifest))
    path_map: dict[str, str] = {}

    def capsule_path_for(source: str) -> str:
        if source in path_map:
            return path_map[source]
        source_path = Path(source)
        if not source_path.exists() or not source_path.is_file():
            path_map[source] = source
            return source
        target = evidence_dir / source_path.name
        counter = 1
        while target.exists() and target.read_bytes() != source_path.read_bytes():
            target = evidence_dir / f"{source_path.stem}_{counter}{source_path.suffix}"
            counter += 1
        if not target.exists():
            shutil.copy2(source_path, target)
        path_map[source] = str(target)
        return path_map[source]

    artifacts = child_manifest.get("artifacts", [])
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict) and artifact.get("path"):
                artifact["path"] = capsule_path_for(str(artifact["path"]))
    policy = child_manifest.get("local_search_policy")
    if isinstance(policy, dict):
        allowed = policy.get("allowed_local_evidence_paths")
        if isinstance(allowed, list):
            policy["allowed_local_evidence_paths"] = [capsule_path_for(str(path)) for path in allowed]
        cas_assets = policy.get("allowed_cas_assets")
        if isinstance(cas_assets, list):
            policy["allowed_cas_assets"] = [capsule_path_for(str(path)) for path in cas_assets]
    cas_tooling = child_manifest.get("cas_tooling")
    if isinstance(cas_tooling, dict) and isinstance(cas_tooling.get("assets"), list):
        for asset in cas_tooling["assets"]:
            if isinstance(asset, dict) and asset.get("path"):
                asset["path"] = capsule_path_for(str(asset["path"]))
    context_in_capsule = capsule_dir / "context.json"
    return {"manifest": child_manifest, "context_path": context_in_capsule, "workdir": capsule_dir}


def _model_routing_hint(action: Mapping[str, Any], actor_role: str) -> Dict[str, Any]:
    mode = str(action.get("mode") or "")
    if actor_role in {"researcher", "villain", "strict_informal_verifier", "integration_verifier"}:
        return {
            "tier": "strong_math",
            "reason": "proof construction, refutation pressure, strict verification, or integration alignment needs maximum mathematical reasoning",
        }
    if actor_role == "literature_researcher":
        level = "strong_math" if mode in {"synthesize_sources", "audit_definitions"} or action.get("librarian_level") == "research_librarian" else "search_reader"
        return {
            "tier": level,
            "reason": "literature search can use search/reader routing unless theorem matching or source synthesis is hard",
        }
    if actor_role == "phd_advisor":
        return {
            "tier": "planning",
            "reason": "route triage and decomposition regulation should be faster than proof construction but still mathematically careful",
        }
    if actor_role == "writer":
        return {
            "tier": "writing",
            "reason": "proof exposition uses verified artifacts and should prioritize clarity over exploration",
        }
    return {
        "tier": "default",
        "reason": "no special model routing requested",
    }


def _context_char_budget_for_action(max_context_chars: int, action: Mapping[str, Any], actor_role: str) -> int:
    mode = str(action.get("mode") or "")
    if actor_role == "strict_informal_verifier" and (action.get("route_id") or action.get("proof_repair_verification_required")):
        return max(max_context_chars, 60_000)
    if actor_role == "researcher" and action.get("creative_proof_attack_required"):
        return max(max_context_chars, 80_000)
    if actor_role == "researcher" and mode in {"prove", "reduce", "weaken", "strengthen"}:
        return max(max_context_chars, 50_000)
    if actor_role == "villain":
        return max(max_context_chars, 50_000)
    if actor_role == "literature_researcher":
        return max(max_context_chars, 30_000)
    if actor_role == "phd_advisor":
        return max(max_context_chars, 30_000)
    return max_context_chars


def execute_session(
    store: ProofStateStore,
    action: Mapping[str, Any],
    session_plan: Mapping[str, Any],
    *,
    model: str = DEFAULT_CODEX_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    model_profile: str = "default",
    codex_bin: str = "codex",
    sandbox: str = DEFAULT_SANDBOX,
    web_search: str | None = None,
    timeout_sec: int = DEFAULT_CHILD_TIMEOUT_SECONDS,
    codex_workdir: Path | None = None,
    extra_args: Sequence[str] | None = None,
    progress_callback: ProgressCallback | None = None,
    stop_event: threading.Event | None = None,
) -> Dict[str, Any]:
    actor_role = str(session_plan.get("actor_role") or actor_role_for_action(action))
    mode = str(action.get("mode") or "step")
    target_id = str(action.get("target_id") or "root")
    run_id = _run_id(mode, target_id)
    run_dir = store.state_dir / "workflow_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    final_path = run_dir / "final_patch.json"
    log_path = run_dir / "codex.log"
    context_path = Path(str(session_plan["context_path"]))
    plan_workdir = str(session_plan.get("codex_workdir") or "")
    workdir = codex_workdir or (Path(plan_workdir) if plan_workdir else store.generation_root.parents[1])
    resume_session_id = str(session_plan.get("resume_session_id") or "")
    prompt = build_session_prompt(context_path=context_path, action=action, actor_role=actor_role, resume=bool(resume_session_id))
    command = build_codex_command(
        context_path=context_path,
        mode=mode,
        model_profile=model_profile,
        extra_args=_codex_child_exec_args(extra_args),
        prompt=prompt,
        actor_role=actor_role,
        codex_bin=codex_bin,
        model=model,
        reasoning_effort=reasoning_effort,
        sandbox=sandbox,
        web_search=web_search,
        output_last_message=final_path,
        codex_workdir=workdir,
        resume_session_id=resume_session_id or None,
    )

    started = time.monotonic()
    returncode = -1
    status = "failed"
    failure_kind = ""
    process: subprocess.Popen[str] | None = None
    stream_thread: threading.Thread | None = None
    peak_memory_mb = 0.0

    def sample_peak_memory_mb() -> float:
        nonlocal peak_memory_mb
        if process is not None:
            peak_memory_mb = max(peak_memory_mb, _process_tree_rss_mb(process.pid))
        return peak_memory_mb

    def emit_progress(phase: str, *, progress_status: str = "running", current_returncode: int | str = "") -> None:
        if progress_callback is None:
            return
        log_tail = _compact_live_log_tail(log_path)
        live_parse_log = _join_log_samples(_read_text_head(log_path), log_tail)
        live_session_id = parse_session_id(live_parse_log)
        live_usage = resolve_cli_usage(live_parse_log, session_id=live_session_id)
        payload = {
            "run_id": run_id,
            "actor_role": actor_role,
            "mode": mode,
            "target_id": target_id,
            "route_id": str(action.get("route_id") or ""),
            "researcher_work_mode": str(action.get("researcher_work_mode") or ""),
            "phase": phase,
            "status": progress_status,
            "returncode": current_returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "peak_memory_mb": round(sample_peak_memory_mb(), 1),
            "updated_at": utc_now(),
            "session_id": live_session_id,
            "usage": live_usage,
            "context_path": str(context_path),
            "log_path": str(log_path),
            "final_message_path": str(final_path),
            "log_tail": log_tail,
        }
        try:
            progress_callback(payload)
        except Exception:
            pass

    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            log_lock = threading.Lock()

            def write_log(text: str) -> None:
                with log_lock:
                    log_file.write(text)
                    log_file.flush()

            if stop_event is not None and stop_event.is_set():
                status = "cancelled"
                write_log("[albilich] session cancelled before launch.\n")
                emit_progress("cancelled", progress_status=status, current_returncode=returncode)
            else:
                process = subprocess.Popen(
                    command,
                    cwd=workdir,
                    env=_codex_child_env(actor_role=actor_role, cas_enabled=session_cas_enabled(actor_role, action)),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                if process.stdout is not None:
                    stream_thread = threading.Thread(
                        target=_stream_child_log,
                        args=(process.stdout, log_file, log_lock),
                        daemon=True,
                    )
                    stream_thread.start()
                emit_progress("started")
                deadline = time.monotonic() + max(1, timeout_sec)
                progress_interval = _progress_interval_seconds()
                stale_retry_seconds = _stale_retry_timeout_seconds(timeout_sec)
                last_progress_signature = _codex_live_progress_signature(log_path)
                last_progress_at = time.monotonic()
                active_retry_marker = _codex_retry_stall_marker(log_path)
                retry_stall_started_at: float | None = None
                while True:
                    if stop_event is not None and stop_event.is_set():
                        status = "cancelled"
                        failure_kind = "cancelled"
                        _terminate_process(process)
                        returncode = process.returncode if process.returncode is not None else -1
                        if stream_thread is not None:
                            stream_thread.join(timeout=2)
                        write_log("\n[albilich] session cancelled and was terminated.\n")
                        emit_progress("cancelled", progress_status=status, current_returncode=returncode)
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        status = "timeout"
                        failure_kind = "deadline"
                        _terminate_process(process)
                        returncode = process.returncode if process.returncode is not None else -1
                        if stream_thread is not None:
                            stream_thread.join(timeout=2)
                        write_log("\n[albilich] session timed out and was terminated.\n")
                        emit_progress("timeout", progress_status=status, current_returncode=returncode)
                        break
                    current_signature = _codex_live_progress_signature(log_path)
                    current_retry_marker = _codex_retry_stall_marker(log_path)
                    if current_signature != last_progress_signature:
                        retry_marker_changed = current_retry_marker != active_retry_marker
                        last_progress_signature = current_signature
                        last_progress_at = time.monotonic()
                        active_retry_marker = current_retry_marker
                        if retry_marker_changed and current_retry_marker is not None:
                            retry_stall_started_at = last_progress_at
                        else:
                            retry_stall_started_at = None
                    elif (
                        stale_retry_seconds > 0
                        and retry_stall_started_at is not None
                        and time.monotonic() - retry_stall_started_at >= stale_retry_seconds
                    ):
                        status = "timeout"
                        failure_kind = "stale_stream"
                        _terminate_process(process)
                        returncode = process.returncode if process.returncode is not None else -1
                        if stream_thread is not None:
                            stream_thread.join(timeout=2)
                        write_log(
                            "\n[albilich] session made no log/token progress after a Codex stream retry and was terminated.\n"
                        )
                        emit_progress("stale_retry_timeout", progress_status=status, current_returncode=returncode)
                        break
                    try:
                        wait_timeout = min(progress_interval, remaining)
                        if stop_event is not None:
                            wait_timeout = min(wait_timeout, 1.0)
                        returncode = process.wait(timeout=wait_timeout)
                        if stream_thread is not None:
                            stream_thread.join(timeout=2)
                        status = "completed" if returncode == 0 else "failed"
                        emit_progress("completed", progress_status=status, current_returncode=returncode)
                        break
                    except subprocess.TimeoutExpired:
                        emit_progress("heartbeat")
    except OSError as exc:
        log_path.write_text(f"[albilich] failed to launch Codex session: {exc}\n", encoding="utf-8")
        emit_progress("failed_to_launch", progress_status="failed", current_returncode=returncode)
    except BaseException:
        if process is not None and process.poll() is None:
            _terminate_process(process)
            returncode = process.returncode if process.returncode is not None else -1
            try:
                with log_path.open("a", encoding="utf-8") as log_file:
                    log_file.write("\n[albilich] session interrupted and was terminated.\n")
            except OSError:
                pass
            emit_progress("interrupted", progress_status="cancelled", current_returncode=returncode)
        raise
    wall = time.monotonic() - started
    sample_peak_memory_mb()

    log_head = _read_text_head(log_path)
    log_tail = _read_text_tail(log_path)
    parse_log = _join_log_samples(log_head, log_tail)
    final_text = final_path.read_text(encoding="utf-8") if final_path.exists() else log_tail
    patch, patch_error = extract_patch_from_text(final_text)
    _persist_normalized_final_patch(final_path, final_text, patch)
    if patch is None and status in {"failed", "timeout", "cancelled"}:
        patch_error = _session_failure_summary(
            status=status,
            returncode=returncode,
            log_tail=log_tail,
            fallback=patch_error,
        )
    session_id = parse_session_id(parse_log)
    usage = resolve_cli_usage(parse_log, session_id=session_id)

    # Pre-flight contract check with one in-session repair: when the returned
    # patch would certainly be rejected by the workflow guards (e.g. a verifier
    # proposing informally_verified while its own report lists gaps), resume the
    # same session once with the violations and let it re-emit a corrected
    # patch, instead of losing the whole step to a rejection.
    preflight_repair: Dict[str, Any] = {}
    if patch is not None and status == "completed":
        preflight_errors = preflight_patch_errors(patch, actor_role)
        repair_window = max(1, timeout_sec) - (time.monotonic() - started)
        if preflight_errors and session_id and repair_window > 180:
            repair_prompt = "\n".join(
                [
                    "PATCH PRE-FLIGHT REJECTION. The patch you just returned would be rejected by the Albilich workflow:",
                    *[f"- {error}" for error in preflight_errors],
                    "Re-emit ONE corrected, complete Albilich v1 patch JSON object (not a diff), keeping the same "
                    "base_revision, problem_id, and actor_role.",
                    "Keep your verification_report/evidence artifacts. If the report honestly lists critical errors or "
                    "gaps, do NOT propose a verified status: attach the report, add one precise debt per gap, and leave "
                    "the status transitions out.",
                    "Return only the JSON object, with no markdown fence and no prose.",
                ]
            )
            repair_command = build_codex_command(
                context_path=context_path,
                mode=mode,
                model_profile=model_profile,
                extra_args=_codex_child_exec_args(extra_args),
                prompt=repair_prompt,
                actor_role=actor_role,
                codex_bin=codex_bin,
                model=model,
                reasoning_effort=reasoning_effort,
                sandbox=sandbox,
                web_search=web_search,
                output_last_message=final_path,
                codex_workdir=workdir,
                resume_session_id=session_id,
            )
            emit_progress("preflight_repair")
            try:
                with log_path.open("a", encoding="utf-8") as log_file:
                    log_file.write("\n[albilich] pre-flight repair attempt: " + "; ".join(preflight_errors) + "\n")
                repair_process = subprocess.Popen(
                    repair_command,
                    cwd=workdir,
                    env=_codex_child_env(actor_role=actor_role, cas_enabled=session_cas_enabled(actor_role, action)),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:
                    repair_stdout, _ = repair_process.communicate(timeout=min(repair_window, 1800.0))
                except subprocess.TimeoutExpired:
                    _terminate_process(repair_process)
                    repair_stdout = ""
                with log_path.open("a", encoding="utf-8") as log_file:
                    log_file.write(repair_stdout or "")
                    log_file.write("\n[albilich] pre-flight repair finished.\n")
                repaired_text = final_path.read_text(encoding="utf-8") if final_path.exists() else ""
                repaired_patch, repaired_error = extract_patch_from_text(repaired_text)
                errors_after = (
                    preflight_patch_errors(repaired_patch, actor_role) if repaired_patch is not None else preflight_errors
                )
                preflight_repair = {
                    "attempted": True,
                    "errors_before": preflight_errors,
                    "errors_after": errors_after,
                    "repair_returncode": repair_process.returncode,
                }
                if repaired_patch is not None and not repaired_error:
                    _persist_normalized_final_patch(final_path, repaired_text, repaired_patch)
                    patch = repaired_patch
                    patch_error = ""
                wall = time.monotonic() - started
                repair_parse_log = _join_log_samples(_read_text_head(log_path), _read_text_tail(log_path))
                usage = resolve_cli_usage(repair_parse_log, session_id=session_id)
            except OSError as exc:
                preflight_repair = {"attempted": True, "errors_before": preflight_errors, "repair_failed": str(exc)}

    output_artifact_ids = attached_artifact_ids(patch) if patch else []
    if patch is None and status == "completed":
        status = "no_patch"
    return {
        "run_id": run_id,
        "actor_role": actor_role,
        "status": status,
        "returncode": returncode,
        "wall_time_seconds": round(wall, 3),
        "peak_memory_mb": round(peak_memory_mb, 1),
        "usage": usage,
        "session_id": session_id,
        "patch": patch,
        "patch_error": patch_error,
        "output_artifact_ids": output_artifact_ids,
        "final_message_path": str(final_path),
        "log_path": str(log_path),
        "command": command,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "sandbox": sandbox,
        "web_search": web_search or "",
        "preflight_repair": preflight_repair,
        "failure_kind": failure_kind,
    }


def _session_failure_summary(*, status: str, returncode: int, log_tail: str, fallback: str) -> str:
    tail = log_tail or ""
    if "no log/token progress after a Codex stream retry" in tail:
        return "Codex stream retry stalled with no further log/token progress before a patch was produced."
    if "session timed out and was terminated" in tail:
        return "Codex session reached the Albilich timeout before a patch was produced."
    if "session cancelled" in tail:
        return "Codex session was cancelled before a patch was produced."
    if "failed to launch Codex session" in tail:
        last_line = _last_nonempty_line(tail)
        return last_line or "Codex session failed to launch."
    if status == "failed":
        reason = f"Codex exited with return code {returncode} before a patch was produced."
        last_line = _last_nonempty_line(tail)
        if last_line:
            return f"{reason} Last log line: {last_line}"
        return reason
    return fallback or f"Codex session ended with status {status} before a patch was produced."


def _last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _codex_child_env(actor_role: str = "", cas_enabled: Optional[bool] = None) -> Dict[str, str]:
    env = os.environ.copy()
    tmp_root = Path(env.get("ALBILICH_CODEX_TMPDIR") or DEFAULT_CODEX_CHILD_TMPDIR).expanduser()
    pycache_root = tmp_root / "pycache"
    dot_sage_root = tmp_root / ".sage"
    try:
        tmp_root.mkdir(parents=True, exist_ok=True)
        pycache_root.mkdir(parents=True, exist_ok=True)
        dot_sage_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    env["TMPDIR"] = str(tmp_root)
    env["TEMP"] = str(tmp_root)
    env["TMP"] = str(tmp_root)
    env["PYTHONPYCACHEPREFIX"] = str(pycache_root)
    env["DOT_SAGE"] = str(dot_sage_root)
    env["SAGE_STARTUP_FILE"] = str(tmp_root / "nonexistent_sage_startup.py")
    env["ALBILICH_CAS_ROLE"] = actor_role
    if cas_enabled is None:
        cas_enabled = role_can_use_cas(actor_role)
    env["ALBILICH_CAS_ENABLED"] = "1" if cas_enabled else "0"
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("RUST_LOG", DEFAULT_CODEX_CHILD_RUST_LOG)
    _install_gap_no_history_wrapper(env, tmp_root)
    return env


def _install_gap_no_history_wrapper(env: Dict[str, str], tmp_root: Path) -> None:
    real_gap = env.get("ALBILICH_REAL_GAP_BIN") or env.get("GAP_BIN")
    if not real_gap:
        real_gap = shutil.which("gap", path=env.get("PATH"))
    if not real_gap:
        return
    real_path = Path(real_gap).expanduser()
    if not real_path.exists():
        resolved = shutil.which(real_gap, path=env.get("PATH"))
        if not resolved:
            return
        real_path = Path(resolved)
    wrapper_dir = tmp_root / "bin"
    wrapper_path = wrapper_dir / "gap"
    gap_home = tmp_root / "gap-home"
    try:
        wrapper_dir.mkdir(parents=True, exist_ok=True)
        gap_home.mkdir(parents=True, exist_ok=True)
        gap_home_arg = shlex.quote(str(gap_home))
        wrapper_path.write_text(
            "#!/bin/sh\n"
            f'ALBILICH_GAP_HOME="${{ALBILICH_GAP_HOME:-{gap_home_arg}}}"\n'
            'mkdir -p "$ALBILICH_GAP_HOME" 2>/dev/null || true\n'
            'export HOME="$ALBILICH_GAP_HOME"\n'
            'export GAP_HISTFILE="${GAP_HISTFILE:-/dev/null}"\n'
            'exec "$ALBILICH_REAL_GAP_BIN" -n "$@"\n',
            encoding="utf-8",
        )
        wrapper_path.chmod(0o755)
    except OSError:
        return
    env["ALBILICH_REAL_GAP_BIN"] = str(real_path)
    env["GAP_BIN"] = str(wrapper_path)
    env["PATH"] = str(wrapper_dir) + os.pathsep + env.get("PATH", "")


def _should_suppress_child_log_line(line: str) -> bool:
    return any(fragment in line for fragment in NOISY_CODEX_STARTUP_LOG_FRAGMENTS)


def _stream_child_log(pipe: Any, log_file: Any, log_lock: threading.Lock) -> None:
    try:
        for line in pipe:
            if _should_suppress_child_log_line(line):
                continue
            with log_lock:
                log_file.write(line)
                log_file.flush()
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def parse_session_usage(payload: Any) -> Dict[str, int]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return parse_token_usage({})
    usage = parse_token_usage(payload)
    if usage["total_tokens"] and not usage["input_tokens"] and not usage["output_tokens"]:
        usage["input_tokens"] = usage["total_tokens"]
    return usage


def resolve_cli_usage(
    text: str,
    *,
    session_id: str = "",
    session_root: Path | str | None = None,
) -> Dict[str, int]:
    cli_usage = parse_cli_usage(text)
    resolved_session_id = session_id or parse_session_id(text)
    session_usage = parse_codex_session_usage(resolved_session_id, session_root=session_root)
    # The CLI footer collapses to a lone total (input=total, output/cached=0).
    # The session file carries the real breakdown, so prefer it when it is at
    # least as large and actually has detail, not only when it is strictly larger.
    session_has_detail = (
        session_usage["output_tokens"] > 0
        or session_usage["cached_input_tokens"] > 0
        or session_usage["reasoning_output_tokens"] > 0
    )
    if session_usage["total_tokens"] > cli_usage["total_tokens"]:
        return session_usage
    if session_has_detail and session_usage["total_tokens"] >= cli_usage["total_tokens"] > 0:
        return session_usage
    return cli_usage


def _join_log_samples(head: str, tail: str) -> str:
    if not head:
        return tail
    if not tail or head == tail:
        return head
    return head + "\n" + tail


def parse_cli_usage(text: str) -> Dict[str, int]:
    json_usage = _parse_usage_json_from_log(text)
    if json_usage["total_tokens"]:
        return json_usage

    matches = list(re.finditer(r"tokens used\s*\r?\n\s*([0-9][0-9,]*)", text, flags=re.IGNORECASE))
    if matches:
        total = int(matches[-1].group(1).replace(",", ""))
        return {
            "input_tokens": total,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
            "total_tokens": total,
        }

    usage = {
        "input_tokens": _last_number_for_patterns(
            text,
            r"input[_\s-]*tokens?\s*[:=]\s*([0-9][0-9,]*)",
            r"prompt[_\s-]*tokens?\s*[:=]\s*([0-9][0-9,]*)",
        ),
        "cached_input_tokens": _last_number_for_patterns(
            text,
            r"cached[_\s-]*(?:input|prompt)[_\s-]*tokens?\s*[:=]\s*([0-9][0-9,]*)",
            r"cache[_\s-]*(?:read|hit)[_\s-]*tokens?\s*[:=]\s*([0-9][0-9,]*)",
        ),
        "output_tokens": _last_number_for_patterns(
            text,
            r"output[_\s-]*tokens?\s*[:=]\s*([0-9][0-9,]*)",
            r"completion[_\s-]*tokens?\s*[:=]\s*([0-9][0-9,]*)",
        ),
        "reasoning_output_tokens": _last_number_for_patterns(
            text,
            r"reasoning[_\s-]*(?:output[_\s-]*)?tokens?\s*[:=]\s*([0-9][0-9,]*)",
        ),
        "total_tokens": _last_number_for_patterns(
            text,
            r"total[_\s-]*tokens?\s*[:=]\s*([0-9][0-9,]*)",
            r"tokens?\s*total\s*[:=]\s*([0-9][0-9,]*)",
            r"tokens?\s*used\s*[:=]\s*([0-9][0-9,]*)",
        ),
    }
    if usage["total_tokens"] <= 0:
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
    if usage["total_tokens"] and not usage["input_tokens"] and not usage["output_tokens"]:
        usage["input_tokens"] = usage["total_tokens"]
    return usage


def _parse_usage_json_from_log(text: str) -> Dict[str, int]:
    for match in reversed(list(re.finditer(r'"usage"\s*:\s*\{', text))):
        start = match.start()
        brace = text.find("{", start)
        if brace < 0:
            continue
        depth = 0
        for index in range(brace, min(len(text), brace + 16_000)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        payload = json.loads(text[brace : index + 1])
                    except json.JSONDecodeError:
                        break
                    usage = parse_session_usage({"usage": payload})
                    if usage["total_tokens"]:
                        return usage
                    break
    return parse_token_usage({})


def parse_codex_session_usage(
    session_id: str,
    *,
    session_root: Path | str | None = None,
) -> Dict[str, int]:
    path = _find_codex_session_file(session_id, session_root=session_root)
    if path is None:
        return parse_token_usage({})
    return _parse_codex_session_usage_file(path)


def _find_codex_session_file(session_id: str, *, session_root: Path | str | None = None) -> Optional[Path]:
    if not session_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", session_id):
        return None
    root = _codex_session_root(session_root)
    cache_key = f"{root}:{session_id}"
    if cache_key in _SESSION_PATH_CACHE:
        cached = _SESSION_PATH_CACHE[cache_key]
        if cached is not None and cached.exists():
            return cached
    if not root.exists():
        return None
    try:
        candidates = sorted(
            (path for path in root.rglob(f"*{session_id}*.jsonl") if session_id in path.name),
            key=lambda path: (path.stat().st_mtime, str(path)),
            reverse=True,
        )
    except OSError:
        candidates = []
    if not candidates:
        return None
    path = candidates[0]
    _SESSION_PATH_CACHE[cache_key] = path
    return path


def _codex_session_root(session_root: Path | str | None = None) -> Path:
    if session_root is not None:
        return Path(session_root).expanduser()
    env_root = os.environ.get(CODEX_SESSION_ROOT_ENV)
    if env_root:
        return Path(env_root).expanduser()
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "sessions"
    return Path.home() / ".codex" / "sessions"


def _parse_codex_session_usage_file(path: Path) -> Dict[str, int]:
    latest = parse_token_usage({})
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return latest
    for line in lines:
        if "token_count" not in line and "total_token_usage" not in line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload") if isinstance(event, Mapping) else {}
        if not isinstance(payload, Mapping) or payload.get("type") != "token_count":
            continue
        info = payload.get("info") if isinstance(payload.get("info"), Mapping) else {}
        usage = parse_session_usage(info.get("total_token_usage"))
        if usage["total_tokens"] >= latest["total_tokens"]:
            latest = usage
    return latest


def _last_number_for_patterns(text: str, *patterns: str) -> int:
    values: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            values.append(int(match.group(1).replace(",", "")))
    return values[-1] if values else 0


def parse_session_id(text: str) -> str:
    match = re.search(r"session id:\s*([^\s]+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_patch_from_text(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    stripped = text.strip()
    if not stripped:
        return None, "empty model response"
    decoder = json.JSONDecoder()
    first_decode_error = ""
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        candidate = stripped[index:]
        try:
            obj, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError as exc:
            if not first_decode_error:
                first_decode_error = f"invalid JSON patch near character {index + exc.pos}: {exc.msg}"
            obj = _repair_extra_object_close_before_array(candidate, exc, decoder)
            if obj is None:
                continue
            return obj, ""
        if isinstance(obj, dict) and obj.get("schema_version") == 1 and isinstance(obj.get("operations"), list):
            return obj, ""
    return None, first_decode_error or "no Albilich v1 patch JSON object found"


def _persist_normalized_final_patch(final_path: Path, final_text: str, patch: Mapping[str, Any] | None) -> None:
    """Make final_patch.json a valid patch file after tolerant extraction succeeds."""
    if not patch:
        return
    persisted_patch = _normalized_patch_for_persistence(patch)
    normalized = json.dumps(persisted_patch, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if final_text != normalized:
        try:
            current = json.loads(final_text)
        except json.JSONDecodeError:
            current = None
        if current != persisted_patch:
            raw_path = final_path.with_name("final_patch.raw.txt")
            raw_path.write_text(final_text, encoding="utf-8")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(normalized, encoding="utf-8")


def _normalized_patch_for_persistence(patch: Mapping[str, Any]) -> Dict[str, Any]:
    from .patches import _normalize_patch_aliases

    return _normalize_patch_aliases(dict(patch))


def _repair_extra_object_close_before_array(
    candidate: str,
    exc: json.JSONDecodeError,
    decoder: json.JSONDecoder,
) -> Optional[Dict[str, Any]]:
    """Recover a near-valid patch with one extra `}` at an operation boundary."""
    pos = exc.pos
    if exc.msg != "Expecting ',' delimiter":
        return None
    if pos < 0 or pos + 1 >= len(candidate):
        return None
    if candidate[pos] != "}" or candidate[pos + 1] not in {"]", ","}:
        return None
    repaired = candidate[:pos] + candidate[pos + 1 :]
    try:
        obj, _ = decoder.raw_decode(repaired)
    except json.JSONDecodeError:
        return None
    if isinstance(obj, dict) and obj.get("schema_version") == 1 and isinstance(obj.get("operations"), list):
        return obj
    return None


def attached_artifact_ids(patch: Mapping[str, Any] | None) -> list[str]:
    if not patch:
        return []
    ids = []
    for op in patch.get("operations", []):
        if not isinstance(op, Mapping):
            continue
        kind = _operation_kind(op)
        if kind not in {"attach_artifact", "add_artifact"}:
            continue
        artifact = op.get("artifact")
        artifact_id = artifact.get("artifact_id") if isinstance(artifact, Mapping) else op.get("artifact_id")
        if isinstance(artifact_id, str):
            ids.append(artifact_id)
    return ids


def _operation_kind(op: Mapping[str, Any]) -> str:
    for key in ("op", "operation_type", "operation", "operation_name", "type"):
        value = op.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def run_metrics_operation(
    *,
    run_id: str,
    action: Mapping[str, Any],
    session_plan: Mapping[str, Any],
    usage_payload: Any,
    status: str = "completed",
    wall_time_seconds: float = 0.0,
    peak_memory_mb: float = 0.0,
    model: str = "",
) -> Dict[str, Any]:
    usage = parse_session_usage(usage_payload)
    return {
        "op": "record_run_metrics",
        "run_id": run_id,
        "actor_role": session_plan.get("actor_role", ""),
        "mode": action.get("mode", "prove"),
        "target_id": action.get("target_id", ""),
        "route_id": action.get("route_id", ""),
        "researcher_work_mode": action.get("researcher_work_mode", ""),
        "work_mode_source": action.get("work_mode_source", ""),
        "state_revision": session_plan.get("state_revision", 0),
        "context_revision": session_plan.get("state_revision", 0),
        "session_id": session_plan.get("session_id", ""),
        "model_profile": session_plan.get("model_profile", "default"),
        "model": model,
        "budget_requested": action.get("budget", {}).get("requested_tokens", 0) if isinstance(action.get("budget"), Mapping) else 0,
        "input_tokens": usage["input_tokens"],
        "cached_input_tokens": usage["cached_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "reasoning_output_tokens": usage["reasoning_output_tokens"],
        "total_tokens": usage["total_tokens"],
        "wall_time_seconds": wall_time_seconds,
        "peak_memory_mb": peak_memory_mb,
        "status": status,
        "prompt_context_hash": session_plan.get("context_hash", ""),
    }


def _context_path(store: ProofStateStore, action: Mapping[str, Any], context_hash: str) -> Path:
    safe_mode = str(action.get("mode") or "step").replace("/", "_")
    safe_target = str(action.get("target_id") or "root").replace("/", "_")
    revision = store.get_revision()
    return store.state_dir / "contexts" / f"rev{revision}_{safe_mode}_{safe_target}_{context_hash[:10]}.json"


def _run_id(mode: str, target_id: str) -> str:
    stamp = utc_now().replace(":", "").replace("-", "").replace(".", "_").replace("+", "Z")
    safe_mode = re.sub(r"[^A-Za-z0-9_.-]+", "_", mode).strip("_") or "step"
    safe_target = re.sub(r"[^A-Za-z0-9_.-]+", "_", target_id).strip("_") or "root"
    return f"v1_{safe_mode}_{safe_target}_{stamp}"


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except Exception:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            process.kill()
        process.wait(timeout=5)


def _process_tree_rss_mb(root_pid: int) -> float:
    """Best-effort resident memory sample for a Codex subprocess tree."""
    if root_pid <= 0:
        return 0.0
    pids = {root_pid}
    frontier = [root_pid]
    for _ in range(8):
        next_frontier: list[int] = []
        for pid in frontier:
            try:
                output = subprocess.check_output(
                    ["pgrep", "-P", str(pid)],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                continue
            for raw in output.split():
                try:
                    child_pid = int(raw)
                except ValueError:
                    continue
                if child_pid not in pids:
                    pids.add(child_pid)
                    next_frontier.append(child_pid)
        if not next_frontier:
            break
        frontier = next_frontier
    try:
        output = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", ",".join(str(pid) for pid in sorted(pids))],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return 0.0
    rss_kb = 0
    for raw in output.split():
        try:
            rss_kb += int(raw)
        except ValueError:
            continue
    return round(rss_kb / 1024.0, 3) if rss_kb > 0 else 0.0


def _read_text_head(path: Path, max_bytes: int = LOG_PARSE_HEAD_BYTES) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as fh:
        return fh.read(max_bytes).decode("utf-8", errors="replace")


def _compact_live_log_tail(path: Path) -> str:
    return _read_text_tail(path, max_bytes=LIVE_LOG_TAIL_BYTES).strip()[-4_000:]


def _progress_interval_seconds() -> float:
    raw = os.environ.get("ALBILICH_UI_HEARTBEAT_SECONDS", "").strip()
    if raw:
        try:
            return max(0.1, float(raw))
        except ValueError:
            pass
    return DEFAULT_PROGRESS_INTERVAL_SECONDS


def _stale_retry_timeout_seconds(timeout_sec: int) -> float:
    raw = os.environ.get("ALBILICH_CODEX_STALE_RETRY_SECONDS", "").strip()
    if raw:
        try:
            value = float(raw)
        except ValueError:
            value = DEFAULT_CODEX_STALE_RETRY_SECONDS
    else:
        value = DEFAULT_CODEX_STALE_RETRY_SECONDS
    if value <= 0:
        return 0.0
    return max(0.1, min(value, max(1.0, float(timeout_sec))))


def _codex_live_progress_signature(path: Path) -> tuple[int, int, int, int]:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    sample = _join_log_samples(_read_text_head(path), _read_text_tail(path))
    usage = resolve_cli_usage(sample, session_id=parse_session_id(sample))
    return (
        size,
        int(usage.get("input_tokens") or 0),
        int(usage.get("output_tokens") or 0),
        int(usage.get("total_tokens") or 0),
    )


def _codex_retry_stall_seen(path: Path) -> bool:
    return _codex_retry_stall_marker(path) is not None


def _codex_retry_stall_marker(path: Path) -> tuple[int, str, str] | None:
    if not path.exists():
        return None
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > LOG_PARSE_TAIL_BYTES:
                fh.seek(-LOG_PARSE_TAIL_BYTES, os.SEEK_END)
                base_offset = size - LOG_PARSE_TAIL_BYTES
            else:
                base_offset = 0
            data = fh.read()
    except OSError:
        return None

    best_index = -1
    best_fragment = ""
    for fragment in STALE_RETRY_LOG_FRAGMENTS:
        index = data.rfind(fragment.encode("utf-8"))
        if index > best_index:
            best_index = index
            best_fragment = fragment
    if best_index < 0:
        return None

    line_start = data.rfind(b"\n", 0, best_index) + 1
    line_end = data.find(b"\n", best_index)
    if line_end < 0:
        line_end = len(data)
    line = data[line_start:line_end].decode("utf-8", errors="replace").strip()
    return (base_offset + best_index, best_fragment, line[:500])


def _read_text_tail(path: Path, max_bytes: int = LOG_PARSE_TAIL_BYTES) -> str:
    if not path.exists():
        return ""
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size > max_bytes:
            fh.seek(-max_bytes, os.SEEK_END)
        return fh.read().decode("utf-8", errors="replace")
