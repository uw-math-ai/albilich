# Albilich

Albilich is an auditable multi-agent research system for difficult mathematics.
It coordinates proof construction, counterexample search, literature review,
computer algebra, strict verification, integration checking, and final writing
around one persistent proof graph. A run returns a verified proof, a verified
counterexample, or an honest partial result that names the remaining
obstructions.

This is not a single-pass prover. Every mathematical claim, route, inference,
debt, source record, and proof artifact lives in a versioned SQLite proof state.
Agents can advance that state only through validated patches, and only verifier
roles can certify or refute mathematics. A theorem counts as solved only after
its proof spine passes strict verification and a separate integration check
confirms that it proves the original statement.

## Current release: a major research-engine upgrade

This release brings the strongest current Albilich workflow to the standalone
public repository. It is a substantial upgrade to how long runs choose their
next mathematical move, retrieve external results, coordinate parallel work,
recover verifier evidence, close proof routes, report live state, and turn a
verified result into a readable paper.

- **Research intelligence is now proof-graph aware.** The scheduler computes
  the smallest active sufficient-route obligation cut, scores the decisive
  bottleneck, retrieves from eighteen reviewed method cards, and learns local
  strategy-family outcomes only from later verifier-accepted evidence.
- **Stalled attacks change mathematics, not just wording.** Repeated
  bottlenecks trigger a representation-switch contract, theorem-adaptation
  packets, proof-interface checks, or a new research philosophy. Multi-branch
  waves must use genuinely different strategy families rather than launch
  paraphrases of the same attempt.
- **Literature search has a dedicated high-signal path.** Optional Matlas and
  UW TheoremSearch adapters give the literature reviewer bounded theorem
  candidates. Provider text is normalized, size-limited, origin-checked, and
  treated as untrusted discovery data until the reviewer inspects the primary
  source and records an exact retrieval card.
- **Parallel research and verification are substantially more robust.** Hard
  problems use three research branches with shared compact summaries and
  negative evidence. Fresh source handoffs are prioritized, strict verifier
  proof evidence survives context compaction, and compatible stale verifier
  patches are recovered and revalidated instead of silently discarded.
- **Proof closure is stricter and more accurate.** Integration debts remain
  authoritative, repaired routes return to verification, integrated claims and
  routes leave the active frontier, and a strictly verified root is displayed
  as integration-pending until the final alignment gate actually accepts it.
- **The live dashboard tells the truth about a large proof tree.** It shows
  claim hierarchy and containment, lifecycle colors, recovered verification,
  active debts, branch work, verifier capacity, run progress, and
  cached-versus-new token accounting without presenting retired work as open.
- **Long-running sessions recover more safely.** Structured-output repair
  handles malformed JSON and LaTeX escapes, parallel patch recovery preserves
  compatible evidence, abnormal child exits remain visible, duplicate advisor
  loops are suppressed, and solved runs stop before optional publication work.
- **Verified mathematics now has a stronger publication path.** The writing
  gate normalizes LaTeX, detects thin or fragmented exposition, preserves
  location-specific editorial debts, compiles with restricted service paths,
  and exports the certificate, article source, and PDF as distinct artifacts.
- **The public regression suite grew with the engine.** The synchronized
  release passes 890 tests and 312 subtests across scheduling, retrieval,
  research intelligence, proof-state mutation, parallel recovery, verifier
  gates, dashboard state, CAS contracts, and mathematical writing.

In practice, the new engine spends less time circling around attractive side
lemmas and more time attacking the exact statement that would close the best
route. It also makes the boundary between “promising,” “strictly verified,”
“integrated,” and “solved” explicit at every stage.

## Quickstart

```bash
npm install -g @openai/codex          # default execution backend
python3 -m agents.generation.phase2.cli init    agents/generation/data/example.md
python3 -m agents.generation.phase2.cli attempt agents/generation/data/example.md
```

A problem file is Markdown. Its full text becomes the immutable root statement,
so a problem-id is fixed once and a re-run resumes the same proof state. Write a
problem file under `agents/generation/data/`; `example.md` is a runnable demo.

An `attempt` run serves a live dashboard at `http://127.0.0.1:8765/` showing the
proof graph, route scores, verifier health, the active bottleneck, token and
wall-clock use, and the current work modes. Pass `--no-dashboard` to disable it.

## Proof state

The store holds one problem per database:

```text
problem_state   the immutable root statement and run budgets
claims          theorems, lemmas, definitions, obstructions, counterexamples
routes          proof strategies for a conclusion claim
inferences      the proof steps a verifier checks
debts           precise missing references, hypotheses, gaps, repair obligations
artifacts       proof dossiers, verifier reports, source notes, CAS reports, final proofs
retrieval_cards external sources with exact location and hypotheses
runs, patches, events   metrics and the append-only history
```

Claims carry a validation status (`untested`, `plausible`, `challenged`,
`informally_verified`, `formally_verified`, `refuted`) and a lifecycle status
(`active`, `blocked`, `abandoned`, `integrated`, `superseded`). A verified
statement repair supersedes stale wording so the system stops proving a
sentence the verifier already corrected. A retrieval card is source evidence,
not proof: a cited theorem closes a goal only after the verifier checks its
location, hypotheses, definitions, and implication to the target.

## Roles

| Role | Responsibility | May verify |
| --- | --- | --- |
| `researcher` | The mathematician: direct proofs, route repair, examples, source adaptation, CAS, proof dossiers. | No |
| `villain` | Independent refuter: attacks claims, stress-tests hypotheses, builds candidate counterexamples. | No |
| `literature_researcher` | Searches sources and writes retrieval cards, theorem-library entries, and adaptation notes. | No |
| `phd_advisor` | Reads fresh evidence against the original problem, names what remains, steers the next move and the work-mode loops. | No |
| `strict_informal_verifier` | Checks one bounded proof packet; triages and certifies exact citations. | Yes |
| `integration_verifier` | Checks that a verified sufficient route proves the target and aligns with the root. | Yes |
| `counterexample_validator` | Validates candidate counterexamples. | Yes |
| `writer` | Writes the final proof or partial report from verified material. | No |
| `scheduler` | Picks the next action from proof state. | No |

The researcher and villain are adversaries of equal strength, one proving and
one refuting, in the style of the Nagata working seminar. The advisor
diagnoses and recommends; the researcher turns recommendations into routes,
inferences, dossiers, or sharper debts. Only a verifying role resolves a debt,
which stops a researcher-submitted repair from reading as closed before a
verifier accepts it.

## The loop

The scheduler is deterministic. It reads proof state and picks one action, so a
run is reproducible from its patch log. Action names are part of the contract:
`prove` with no route is a direct attack on a statement, `prove` with a route is
strict verification of that route, and `reduce` is route construction, repair,
source digestion, or a decomposition branch.

```text
proof spine and current root bottleneck
  researcher proof / construction / citation attempt, with CAS when useful
  literature and villain companions add independent evidence in parallel
  advisor synthesizes after durable evidence or repeated strategic failure
  researcher converts advice into routes, inferences, dossiers, or precise debts
  strict verifier checks a bounded proof packet or an exact citation
  integration verifier checks sufficiency and root alignment
  writer emits the final proof or an honest partial report
```

The ordering resists circling. A ready route goes to the verifier before more
search or decomposition. A verifier gap returns to repair, then to
verification. A repeated broad task, or search and repair alternating without a
new mathematical delta, triggers a bottleneck lock or an advisor pass instead of
another identical prompt.

### Research strategy layer

Mature runs add a deterministic strategy layer over the same persisted proof
state. It does not add roles or verification authority.

- Bidirectional bridge search compares the verified forward frontier with the
  backward obligations from the root and selects at most two serious bridge
  candidates.
- The PhD advisor alternates tactical steering with persisted global syntheses
  that identify one decisive missing statement and supersede stale advice.
- Bottleneck-local conjectures and exceptional auxiliary definitions are
  capped, stress-tested, and admitted only when they have a precise route back
  to the root.
- Eighteen reviewed method cards are retrieved by structural signature and
  domain tags. They include hypotheses, proof moves, diagnostic examples, and
  failure modes; they guide proof search but never become proof premises.
- The proof graph supplies the smallest active sufficient-route obligation cut;
  side lemmas cannot outrank its decisive obligation merely through model
  self-scoring.
- High-leverage branches can receive a coherent deep session, but it is
  persisted only when it produces a concrete proof-state mathematical delta.
  Two no-delta sessions force a change of research philosophy.
- Scheduler actions expose information-gain components and a local
  verifier-filtered outcome posterior. This learns only from Albilich's later
  verified or integrated evidence, never from a reference solution or private
  cross-problem cache.
- Repeated bottlenecks trigger a representation-switch contract; literature
  work produces exact source-to-local theorem-adaptation packets; strict and
  integration verification run a selective deterministic proof-interface
  checklist without requiring Lean.
- Multi-branch waves require different mathematical strategy families as well
  as disjoint claim/debt ownership, so parallel slots pursue genuinely distinct
  proof, adversarial, conceptual, or source-adaptation philosophies.
- Proof compression preserves the full history while shrinking the primary
  context to the best route's dependency closure and weakest sufficient bridge.

The complete contracts and artifact schemas are documented in
[`docs/albilich_research_strategy.md`](docs/albilich_research_strategy.md).

## Verification discipline

The strict verifier checks one route packet: the target claim, the route and
its inferences, premise claims, active debts, and the bounded proof, source, and
CAS artifacts. It does not run CAS, search for a new proof, or add fresh
evidence. It certifies

- a local inference when the attached proof artifact proves it;
- an external theorem when the source gives a locatable reference, checked
  hypotheses, checked definitions, and a checked implication to the target;
- a finite computation when the scope, code, output, and deduction are explicit.

It rejects with a precise debt when proof content is missing or truncated, a
citation lacks location or hypothesis checks, a decomposition parent lacks an
assembly argument, or a blocking debt remains. The path to a solved root:

```text
proof evidence or exact citation
  citation triage and certification for an external theorem
  strict informal verification of local proof steps
  integration verification with root alignment
  writer final proof
```

## Work modes

Each primary researcher session runs in one work mode, after the online/offline
loop of the original rethlas proposer plus a computation mode:

| Mode | Session behavior |
| --- | --- |
| `online` | Live web search enabled: find exact/stronger/equivalent theorems and methods, read the strongest sources, translate them into local notation. No CAS. |
| `offline` | No web, no CAS: prove from the manifest, cached cards, and the theorem library; record precise requests for later passes. |
| `cas` | CAS enabled: run bounded decisive computations and end with a conclusion in a `cas_experiment_report`. No web. |

The scheduler rotates `online → offline → cas` by default, dropping `online`
when live search is off. Bottleneck locks and synthesis passes bias `offline`;
`cas_check_recommended` forces `cas`. The villain runs the same loop with its
own history, computation-first (`cas → offline → online`), so it can sweep for
counterexamples, construct by hand, and hunt published prior art in turn.

The advisor supervises both loops. Its manifest shows both mode histories, and
its report can set `directed_researcher_mode` or `directed_villain_mode` (with a
reason and a step count) to send either agent to search, think, or compute for
the next passes. A run consumes a directive only on a completed pass.

The `literature_researcher` stays a separate role because it alone writes
retrieval cards, so it holds the auditable source catalog that citation triage
and certification read. Online researcher and villain passes search for what the
current attack needs; the librarian maintains the catalog and answers precise
`literature_search_request` debts as a cheap parallel companion.

For retrieve-mode actions, optional informal theorem search can query Matlas
and UW TheoremSearch before the literature-review session starts. Enable it with
`RETHLAS_INFORMAL_SEARCH=1`. The orchestrator owns the network boundary; child
agents receive only bounded inert candidate data, and no provider result becomes
proof evidence without primary-source review. See
[`agents/generation/phase2/INFORMAL_RETRIEVAL.md`](agents/generation/phase2/INFORMAL_RETRIEVAL.md)
for the provider and safety contracts.

Run-level research modes set the opening portfolio:

| Mode | Behavior |
| --- | --- |
| `hard_problem` | Default. Literature scout, deep researcher attack, route construction, and villain stress run in parallel when state safety allows. |
| `balanced` | Cheaper. Literature scout, a fast researcher pass, and villain stress in parallel. |
| `proof_first` | Researcher first; live search follows the caller policy. |
| `independent` | Live search disabled. |
| `citation_pass` | Reference cleanup after integration. |

## Commands

Run from the repository root. The default backend is the Codex CLI. With live
search on, an executed session may export repo-derived proof context to external
model and search services; use `--web-search disabled` for offline attempts.
Codex sessions default to `gpt-5.6-sol` with `xhigh` (Extra High) reasoning;
use `--model` and `--reasoning-effort` to override either setting for a run.

```bash
# initialize, then attempt with defaults
python3 -m agents.generation.phase2.cli init    agents/generation/data/example.md
python3 -m agents.generation.phase2.cli attempt agents/generation/data/example.md

# a long hard-problem run to the wall-clock cap, dashboard on a chosen port
ALBILICH_UI_HEARTBEAT_SECONDS=5 \
python3 -m agents.generation.phase2.cli attempt \
  agents/generation/data/example.md \
  --steps 0 --timeout-sec 7200 --max-wall-sec 86400 \
  --research-mode hard_problem --web-search live \
  --dashboard-port 8793 --no-open-dashboard

# Claude Code as an alternate execution backend
python3 -m agents.generation.phase2.cli attempt agents/generation/data/example.md \
  --backend claude --claude-bin claude --claude-permission-mode bypassPermissions

# plan without executing; inspect state and outputs
python3 -m agents.generation.phase2.cli attempt agents/generation/data/example.md --dry-run --steps 4
python3 -m agents.generation.phase2.cli status  agents/generation/data/example.md
python3 -m agents.generation.phase2.cli report  agents/generation/data/example.md --write
python3 -m agents.generation.phase2.cli monitor agents/generation/data/example.md --port 8793 --no-open
```

`--steps 0` runs until the wall-clock cap, the token budget, or a terminal
scheduler state stops the attempt. If the backend binary is off `PATH`, pass it
with `--codex-bin` or `--claude-bin`. Default `attempt` settings:

```text
research_mode = hard_problem      steps = 48              web_search = live
timeout_sec = 7200                max_wall_sec = 86400    max_reduction_depth = 4
total_token_budget = 80000000     reserved_verification_budget = 12000000
parallel_branches = 3
```

A run writes to `agents/generation/results/<problem_id>/phase2/`: the SQLite
proof state, `albilich_run_console.md` and `.json`, `phase2_report.md`, and an
`artifacts/` directory with dossiers, verifier reports, and the final proof.

## Repository layout

```text
agents/generation/
  data/        problem files (example.md is a runnable demo)
  phase2/      the Albilich proof-state workflow (scheduler, runners, store, verifiers)
  results/     per-problem databases, consoles, reports, artifacts (gitignored)
  tests/       the test suite
math-writing-harness/   deterministic paper-quality rules and source corpus
docs/          architecture, research-strategy, and writing-gate documentation
```

Role prompts are assembled in `agents/generation/phase2/codex_runner.py`.

## Development

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s agents/generation/tests -t .
```

The public suite currently passes 890 tests and 312 subtests covering the
scheduler, patch validator, proof store, parallel workflow, theorem retrieval,
research intelligence, runners, dashboard, work-mode loops, verification gates,
recovery paths, and paper-writing checks.

## Requirements

- Python 3.10 or newer; the workflow uses only the standard library and
  repository modules.
- Node.js and the Codex CLI for the default backend, or the Claude Code CLI for
  `--backend claude`.
- CAS backends for `cas`-mode passes when available: Sage, GAP, Macaulay2,
  Singular, or Lean. Point Albilich at an install outside `PATH` with
  `ALBILICH_GAP_PATH`, `ALBILICH_SAGE_PATH`, and the matching variables.

## License

Apache License 2.0. See [LICENSE](LICENSE).
