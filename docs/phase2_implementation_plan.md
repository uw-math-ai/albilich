# Albilich v1 Implementation Plan

## Current Architecture Map

This checkout documents the Albilich v0.5 line and the later Albilich v1 proof-state workflow.

- `agents/generation/tests/run_example.sh` is the baseline generation runner. It launches Codex, resumes local sessions, records iteration logs, calls the verifier, and invokes the PhD advisor when `ENABLE_PHD_ADVISOR=1`.
- `agents/generation/AGENTS.md` is the generation-agent contract. It defines problem IDs, memory requirements, CAS access, bounded tool discipline, and proof-blueprint output.
- `agents/verification/api/server.py` exposes `/health` and `/verify`. It launches the verification agent through Codex and expects `verification.json`.
- `agents/verification/AGENTS.md` is the strict verification-agent contract and JSON verdict policy.
- `agents/generation/mcp/server.py` implements existing memory tools, theorem search, proof verification, and direct CAS lifecycle tools.
- `agents/cas_lifecycle.py` implements `discover_cas_backends`, `cas_start`, `cas_poll`, and `cas_stop`.
- `agents/generation/reduction.py` implements the current PhD advisor trigger/state/context/materialization flow.
- `agents/generation/prompts/phd_advisor.md` is the prose advisor role contract.
- `tests/` currently covers CAS lifecycle and the v0.5 PhD advisor runner/reduction behavior.

## Integration Points

Albilich v1 was introduced as an opt-in additive workflow.

- New package: `agents/generation/phase2/`.
- New CLI: `python -m agents.generation.phase2.cli ...`.
- New MCP tools are registered in `agents/generation/mcp/server.py` without changing existing memory tools.
- Existing `run_example.sh` remains the default runner. A feature flag hook may route to Albilich v1 later, but this implementation keeps the baseline unchanged.
- Existing PhD advisor prose artifacts are preserved. Albilich v1 adds an adapter that can parse/propose structured patches from advisor certificates.

## Data Model

The authoritative Albilich v1 state is a versioned SQLite store under:

`agents/generation/results/{problem_id}/phase2/proof_state.sqlite3`

The store includes:

- `problem_state` with immutable root statement, schema version, current revision, token budget, and reduction settings;
- `claims` for theorems, lemmas, definitions, obstructions, counterexample claims, and references;
- `routes` for alternative proof/reduction strategies;
- `inferences` plus `inference_premises` for hyperedges;
- `debts` attached to claims/routes/inferences;
- `artifacts` with SHA-256 hashes and role provenance;
- `runs` with mode, target, token usage, status, and context hash;
- `patches` and `events` for append-only audit;
- `retrieval_cards` for cached theorem cards.

Each accepted patch increments the state revision and writes:

`agents/generation/results/{problem_id}/phase2/proof_state_snapshot.json` when written explicitly with the `snapshot` CLI command

## Migration And Backward Compatibility

- Existing append-only memory JSONL files remain as evidence/archive artifacts, not the authoritative state.
- Existing results, logs, memory, verifier API, and PhD advisor outputs remain valid.
- Albilich v1 can initialize a state store from a problem markdown file without changing the problem file.
- Explicit snapshots and generated reports are inspectable JSON/Markdown; the SQLite database remains the canonical state during normal workflow execution.
- No new production dependency is introduced; the implementation uses Python standard-library modules including `sqlite3`, `json`, `hashlib`, `argparse`, and `subprocess`.

## Implementation Phases

### Phase A - State Foundation

Implement models/enums, SQLite migrations, artifact hashing, patch validation/application, transition guards, invariant checks, explicit snapshots, and unit tests.

### Phase B - Existing-System Adapters

Implement verifier-report normalization, debt extraction and deduplication, PhD advisor certificate adapter, and memory evidence adapter.

### Phase C - Efficient Orchestration

Implement deterministic scheduler, budget policy, compact context builder, token-usage parser, and dry-run CLI.

### Phase D - Correctness Gates

Implement counterexample gate contracts, integration verification contracts, retrieval cache/theorem cards, and formal handoff manifest generation.

### Phase E - Runnable Vertical Slice

Implement `phase2 init/status/check/report/step/run`, MCP proof-state tools, metrics, Markdown reports, fixture-driven end-to-end tests, and documentation.

## Exact Test Commands

Focused checks during implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 agents/verification/.venv/bin/python -m unittest tests.test_phase2_state
PYTHONDONTWRITEBYTECODE=1 agents/verification/.venv/bin/python -m compileall -q agents/generation/phase2 agents/generation/mcp/server.py tests/test_phase2_state.py
```

Full relevant suite:

```bash
bash -n agents/generation/tests/run_example.sh
PYTHONDONTWRITEBYTECODE=1 agents/verification/.venv/bin/python -m unittest discover -s tests
```

## Design Deviations From Prompt

- The first implementation did not add live Codex execution to the Albilich v1 run loop. It provides a safe `CodexRunner` command builder and JSONL usage parser, and tests those offline.
- The first implementation does not run a formal backend. It emits `formalization_manifest.json` and only allows `formally_verified` when a formal-backend artifact is explicitly present.
- The baseline runner is not rewritten. Albilich v1 is opt-in through CLI/MCP and can be wired into `run_example.sh` after the state layer has proven stable.
