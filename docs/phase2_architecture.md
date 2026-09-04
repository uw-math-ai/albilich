# Albilich v1 Architecture

Albilich v1 adds an executable proof-state workflow beside the Albilich v0.5 runner. The current JSONL memory tools and legacy run scripts remain valid. Albilich v1 writes one authoritative SQLite database per problem under `agents/generation/results/<problem_id>/phase2/`; the internal path remains `phase2` for compatibility.

## What Albilich v1 Adds

- Versioned SQLite proof state (schema version 3) with ordered migrations, WAL, revision numbers, row-exact patch deltas, event rows, and explicit JSON snapshots on request.
- Typed objects for claims, proof approaches, inference hyperedges, proof obligations, artifacts, runs, and retrieval cards. The SQLite table and legacy API field remain named `debts` for compatibility.
- Separate claim `validation_status` and `lifecycle_status` fields so plausibility, verification, refutation, active work, abandonment, and integration are not conflated.
- Structured patch application with optimistic concurrency through `base_revision`, plus a host-created authority contract binding role, target, proof approach, context hash, and tool permissions.
- Strict evidence gates: researchers, writers, literature researchers, schedulers, and the PhD advisor cannot mark claims verified, refuted, or integrated.
- Non-spoofable artifact provenance: verifier reports must come from `strict_informal_verifier`, formal results must be reproduced by a supported host checker, confirmed counterexamples from `counterexample_validator`, and integration reports from `integration_verifier`. Child patches cannot supply host certificate metadata.
- Root theorem alignment: root integration requires an exact, equivalent, or stronger verified result with checked implication to the immutable target and no hidden extra assumptions.
- Deterministic scheduler and budget guard that protect a verification reserve and can stop with partial results before exhausting the run.
- Dependency-complete verifier manifests. Required statements, proof text, dependencies, and blocking obligations are indivisible and fail with `context_too_large` instead of being silently truncated; researcher manifests remain compact and explicitly mark optional omissions.
- A live workflow loop that launches Codex sessions, captures structured patches, applies accepted patches atomically, records token/time metrics, and repeats until the scheduler stops.
- Research policy modes that separate independent proof search from literature scoping and post-proof citation passes, with adaptive literature-researcher retrieval levels for scout, reader, and hard theorem-matching work.
- Exact mathematical identity uses full Unicode-normalized content digests that preserve operators and arbitrarily late differences. A separate conservative similarity key may suggest possible duplicates but cannot reject a distinct statement.
- Final proof closing: after root integration, the scheduler runs a writer session to emit a `final_proof` artifact before stopping as solved.
- A persisted research-strategy layer for bridge search, global PhD-advisor synthesis, exceptional invention authorization, experimental mathematics, bounded conjectures, structural method cards, deep sessions, ordinal action-priority assessment, and active proof compression. The layer uses ordinary artifacts and patch gates rather than a second state store; see `docs/albilich_research_strategy.md`.
- Content-bound host certificates and deterministic revocation. Statement, dependency, proof, or evidence changes invalidate affected verification and integration status.
- An exact transition journal and replay checker that detect unjournaled state changes and modified recorded deltas. Replay is an audit check, not a cryptographic defense against a hostile database administrator.

## Use

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 agents/verification/.venv/bin/python -m agents.generation.phase2.cli init agents/generation/data/example.md
PYTHONDONTWRITEBYTECODE=1 agents/verification/.venv/bin/python -m agents.generation.phase2.cli step agents/generation/data/example.md --dry-run
PYTHONDONTWRITEBYTECODE=1 agents/verification/.venv/bin/python -m agents.generation.phase2.cli run agents/generation/data/example.md --execute --steps 10 --write-report
PYTHONDONTWRITEBYTECODE=1 agents/verification/.venv/bin/python -m agents.generation.phase2.cli check agents/generation/data/example.md
PYTHONDONTWRITEBYTECODE=1 agents/verification/.venv/bin/python -m agents.generation.phase2.cli report agents/generation/data/example.md --write
```

`step --dry-run` writes one compact context manifest and returns the planned Codex session. `run --execute` is the live workflow: it chooses the next scheduler action, launches Codex with the appropriate role, applies the returned Albilich v1 patch, records metrics, and continues.

The standard mode is `balanced`: a claim-driven literature researcher may search first, but proof, verification, and integration sessions then run with search disabled. `independent` disables live search for every session. `citation_pass` waits for an integrated root claim and a final proof artifact, then lets the literature researcher collect references as a separate pass, so benchmark reports can distinguish independent solving from citation behavior through `runs.search_intent`. The literature researcher is tiered by retrieval depth: cheap `scout` search finds candidates, `reader` extracts theorem cards, and `research_librarian` is reserved for hard theorem matching, hypothesis translation, and source-to-target implication checks.

### Paper solution audit pipeline

`audit-paper` / `paper_solution_audit` uses the same verification authority as an ordinary proof run. The submitted document remains an immutable `audit_subject`, but its theorem and proof segments are transcribed by the researcher into ordinary proof-state objects:

```text
author statement + author proof
  researcher proof_dossier + paper claim + sufficient route + inference
  strict informal verifier checks the bounded author-text packet
  integration verifier checks verified premises and dependency closure
  referee report shows both validation and integration status
```

Explicit hypotheses and ambient assumptions are represented as premise claims, so a paper inference never bypasses the graph with an empty premise list. Proposed repairs stay in separate `proposed_repair` artifacts and are forbidden as evidence that the submitted proof passed. A failed local proof remains unverified; an integration report may record `integrates=false` and the exact missing dependency rather than rewriting the author's argument.

The terminal ladder is explicit. An integrated root without a `final_proof` artifact schedules `write`; it is not treated as a partial result. A run stops as `stop_solved` only after the final proof artifact exists. `stop_with_partial_results` is reserved for exhausted budget, invariant failure, repeated execution failure, unresolved blocking proof obligations, or external step limits.

Public result classification is explicit in CLI and report output. The workflow distinguishes `solved`, `solved_pending_final_writer`, `certified_partial_progress`, `unresolved_with_obligations`, and `in_progress` (with the old serialized status accepted for compatibility). Certified partial progress lists exact verified non-root statements and their relation to the target; it never downgrades the target theorem itself.

## Migration Notes

No existing problem state is migrated automatically. Initialize Albilich v1 for a problem when you want stateful orchestration. The root theorem statement is immutable after initialization; to change it, use a different problem id. Existing memory JSONL remains available to the old runner and MCP memory tools.

## Current Limits

Formal verification requires a successful host execution by a supported backend adapter; a handoff manifest or unchecked source artifact has no proof authority. Integration is intentionally strict and rejects proof approaches with an unverified conclusion claim, unverified inferences, unverified premises, missing integration evidence, active blocking proof obligations, or root-alignment metadata that is weaker, conditional, unknown, or based on hidden extra assumptions. Informal certificates remain model-fallible: they establish reviewed provenance and graph consistency, not formal truth.
