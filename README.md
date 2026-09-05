# Albilich

Albilich is an auditable multi-agent research system for difficult mathematics.
It coordinates proof construction, counterexample search, literature review,
computer algebra, strict verification, integration checking, and final writing
around one persistent proof graph. A run returns an argument that has passed
the configured review gates, a validated counterexample, or an honest partial
result that names the remaining obstructions. Informal model review is not a
formal proof.

The current trust-boundary assessment, real-versus-simulated test record, and
remaining design weaknesses are documented in
[`docs/fourth_pass_systems_review.md`](docs/fourth_pass_systems_review.md). The
corresponding finding-to-control plan is
[`docs/soundness_remediation_blueprint.md`](docs/soundness_remediation_blueprint.md).

This is not a single-pass prover. Every mathematical claim, route, inference,
proof obligation, source record, and proof artifact lives in a versioned SQLite proof state.
After initialization or an explicit schema migration, agents and host workflows
can advance that state only through validated patches, and only verifier roles
can issue content-bound review certificates or refutations. A theorem receives
the internal `solved` status only after
its proof spine passes strict verification and a separate integration check
confirms that it proves the original statement.

## Current release

This release brings the current Albilich workflow to the standalone public
repository. It changes how long runs choose their
next mathematical move, retrieve external results, coordinate parallel work,
recover verifier evidence, close proof approaches, report live state, and turn
a reviewed result into a readable paper.

- **Research intelligence is now proof-graph aware.** The scheduler computes
  the smallest active sufficient-route obligation cut, scores the decisive
  bottleneck, retrieves from eighteen reviewed method cards, and learns local
  strategy-family outcomes only from later verifier-accepted evidence. Context
  assembly now builds one revision-local graph-policy index and reuses it for
  root distance, frontier, route, proof-obligation, and artifact decisions. Evidence-driven
  proof programs add explicit case coverage, continuation and abandonment
  criteria, verifier handoffs, threat propagation, and root-leverage accounting.
- **Stalled attacks change mathematics, not just wording.** Repeated
  bottlenecks trigger a representation-switch contract, theorem-adaptation
  packets, proof-interface checks, a creative proof portfolio, or a new research
  philosophy. Operator steering now forces a fresh approach-alignment wave and
  carries the selected strategy into its decisive pilot instead of being lost
  at the next scheduler boundary.
- **Literature search has a dedicated high-signal path.** Optional Matlas and
  UW TheoremSearch adapters give the literature reviewer bounded theorem
  candidates. Provider text is normalized, size-limited, origin-checked, and
  treated as untrusted discovery data until the reviewer inspects the primary
  source and records an exact retrieval card.
- **Parallel research and verification are substantially more robust.** Hard
  problems use three research branches with shared compact summaries and
  negative evidence. Fresh source handoffs are prioritized, strict verifier
  targets and proof evidence survive root cuts and context compaction, locally
  proved lemmas are recovered for verification, and compatible stale verifier
  patches are revalidated instead of silently discarded.
- **Proof closure is stricter and more accurate.** Integration obligations remain
  authoritative, confirmed counterexamples close only explicitly named obligations with
  bound validation evidence, quantitative claim strengthenings are preserved, and
  repaired routes return to verification. Integrated claims and routes leave
  the active frontier, while a strictly verified root remains visibly
  integration-pending until the final alignment gate accepts it.
- **The live dashboard tells the truth about a large proof tree.** It shows
  claim hierarchy and containment, lifecycle colors, recovered verification,
  active proof obligations, branch work, verifier capacity, run progress, and
  cached-versus-new token accounting without presenting retired work as open.
  Mathematical notation is rendered as LaTeX, steering delivery is visible,
  and cumulative human-readable papers can be opened in the embedded viewer.
- **Long-running sessions recover more safely.** Structured-output repair
  handles malformed JSON, LaTeX commands, and inequality escapes; reconnecting
  Codex sessions receive bounded grace; monitor refreshes cannot pile up; and
  abnormal child exits remain visible. Terminal, steering, and branch dispatch
  priorities are protected so optional writing cannot preempt required work.
- **Reviewed mathematics now has a stronger publication path.** The writing
  gate normalizes LaTeX, detects thin or fragmented exposition, preserves
  location-specific editorial issues, compiles with restricted service paths,
  and exports the certificate, article source, and PDF as distinct artifacts.
  A non-blocking writer sidecar also produces a cumulative HMT paper after each
  ten newly integrated claims without spending research budget or mutating the
  proof revision.
- **The public regression suite grew with the engine.** The synchronized
  release is continuously tested across scheduling, retrieval,
  research intelligence, proof-state mutation, parallel recovery, verifier
  gates, dashboard state, CAS contracts, and mathematical writing.

In practice, the new engine spends less time circling around attractive side
lemmas and more time attacking the exact statement that would close the best
route. It also makes the boundary between “promising,” “strictly verified,”
“integrated,” and “solved” explicit at every stage.

## Experiment archives

The [`experiments/`](experiments/) tree contains checksum-audited historical
run records. Its registry marks the current archives as
`historical_unvalidated`: the files are useful for provenance and case-study
inspection, but they are not evidence for general performance or causal claims.
An archive may be promoted to `protocol_validated` only with a complete protocol
manifest, hashed problem and prompt files, environment and seed records, run and
event logs, proof snapshot, independent grade, a predeclared stopping rule, and
matched repeated controls for any ablation. General-performance protocol v5
additionally requires at least two completely matched conditions, archived and
hashed distinct condition specifications, an Ed25519 preregistration receipt
and two grader signatures whose public keys are supplied to the auditor out of
band, and a preregistered deterministic
problem-cluster bootstrap. A signed assignment schedule fixes every
problem/repeat block and the replayable within-block condition order. The
auditor reconstructs the primary contrast and its interval from the registered
independent labels; reported statistics are not trusted as opaque numbers. A
two-sided normal approximation for paired problem means also recomputes the
registered sample-size requirement from alpha, desired power, minimum
detectable effect, and the stated standard-deviation assumption. The assumption
and its basis remain scientific inputs rather than facts proved by the auditor.
Protocol v4 archives remain replayable under their historical, structurally
validated power declarations, but do not satisfy this stronger v5 guarantee. See
[`experiments/README.md`](experiments/README.md).

Scheduler-calibration protocol v6 adds the missing runtime join. Each matched
workflow condition is a protocol-v3 randomized block assignment tied to the
exact problem bytes, policy semantic digest, candidate sets, dispatched actions,
and contiguous exposure sequence. The signed schedule fixes every problem and
prompt digest, arm-to-run mapping, budget, and stopping rule before execution.
Block seeds are derived from an Ed25519-signed
post-registration randomness receipt whose authority key is supplied out of
band and must differ from registration and grading keys. The archive carries a
complete trace finalization record. Condition-blind graders sign only their
condition-free grading-artifact manifest and blinded grading attestation; a
separate execution-trace auditor signs the
unblinded manifest and completeness statement. This validates an archived design; it does
not turn the repository's historical runs into scheduler-calibration evidence.

## Quickstart

```bash
npm install -g @openai/codex@0.152.0   # CI-tested execution backend
python3 -m agents.generation.phase2.cli init    agents/generation/data/example.md
python3 -m agents.generation.phase2.cli attempt agents/generation/data/example.md
```

Execution requires Linux, `bubblewrap` (`bwrap`), and `prlimit` (util-linux).
PDF export and the complete test suite also require `pdflatex` and the house
template packages, including `newpxtext`/`newpxmath`. On Debian/Ubuntu install
`texlive-latex-base texlive-latex-recommended texlive-latex-extra
texlive-fonts-recommended texlive-fonts-extra texlive-plain-generic tex-gyre`.
On macOS, run the worker **and dashboard in the same Linux VM**. Do not open
one live SQLite WAL database concurrently from the host and guest; their
shared-memory and locking mechanisms are not a cross-OS database service.
Prefer a VM-local disk for proof state and export snapshots for host inspection.

The attested Codex interval is `[0.152.0, 0.154.0)`. For a standalone 0.153.x
installation, install the matching `codex-code-mode-host` companion beside the
native Codex executable; downloading only the main CLI archive is insufficient.
`attempt` and `run --execute` check the backend before changing proof state.
The default is GPT-6 Astra (`gpt-6-astra`) with `xhigh` reasoning; explicit
`--model` and `--reasoning-effort` overrides remain supported.

A problem file is Markdown. Its full text becomes the immutable root statement,
so a problem-id is fixed once and a re-run resumes the same proof state. Write a
problem file under `agents/generation/data/`; `example.md` is a runnable demo.

An `attempt` run serves a live dashboard at `http://127.0.0.1:8765/` showing the
proof graph, route scores, verifier health, the active bottleneck, token and
wall-clock use, and the current work modes. Routes and artifacts use readable
mathematical notation, and cumulative HMT papers are available in the embedded
viewer. Pass `--no-dashboard` to disable it.

## Proof state

The store holds one problem per database:

```text
problem_state   the immutable root statement and run budgets
claims          theorems, lemmas, definitions, obstructions, counterexamples
routes          proof strategies for a conclusion claim
inferences      the proof steps a verifier checks
debts           persisted legacy table name for precise proof obligations
artifacts       proof drafts, verifier reports, source notes, CAS reports, final proofs
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
| `researcher` | The mathematician: direct proofs, approach repair, examples, source adaptation, CAS, proof drafts. | No |
| `adversarial_reviewer` | Independent mathematical critic: attacks claims, stress-tests hypotheses, builds candidate counterexamples. | No |
| `literature_researcher` | Searches sources and writes retrieval cards, theorem-library entries, and adaptation notes. | No |
| `phd_advisor` | Reads fresh evidence against the original problem, names what remains, steers the next move and the work-mode loops. | No |
| `strict_informal_verifier` | Checks one bounded proof packet; triages and certifies exact citations. | Yes |
| `integration_verifier` | Checks that a verified sufficient route proves the target and aligns with the root. | Yes |
| `counterexample_validator` | Validates candidate counterexamples. | Yes |
| `writer` | Writes the final proof or partial report from verified material. | No |
| `scheduler` | Picks the next action from proof state. | No |

The researcher and adversarial reviewer are counterparts of equal strength, one proving and
one trying to refute, in the style of the Nagata working seminar. The advisor
diagnoses and recommends; the researcher turns recommendations into proof
approaches, inferences, proof drafts, or sharper proof obligations. Only a verifying role resolves an obligation,
which stops a researcher-submitted repair from reading as closed before a
verifier accepts it.

## The loop

The scheduler is deterministic for a fixed proof state and fixed runtime
configuration. Accepted state changes carry row-exact deltas and linked state
hashes, so missing journal revisions, unjournaled proof-state mutations, and
modified row deltas are detectable by replay. Patch annotations and
configuration events have their own hash chains, and an optional externally
stored Ed25519 checkpoint can bind the state and all chain heads. This is still
not a public transparency log or write-once archive. Action names are part of the contract:
`prove` with no route is a direct attack on a statement, `prove` with a route is
strict verification of that route, and `reduce` is route construction, repair,
source digestion, or a decomposition branch.

Parallel policy v25 admits companion work with a deterministic bounded-width
global subset search rather than a greedy prefix. It maximizes authenticated
overdue service, fixed host admission weights, and useful parallelism under
ownership, class, token, and worker limits. It retains v11's minimum-feasible
grants and deterministic max--min residual allocation, so an early full request
cannot conceal a larger feasible set. Its upper-bound relaxation additionally
retains v12's class capacities and global verification/integration exclusion,
then removes candidates excluded by the primary or their own authorization and
accounts jointly for reserved/shared minimum-token feasibility and the exact
minimum resource decrement. It also intersects class capacity and the global
verification/integration exclusion with safe route and certification-target
clique partitions, including mixed certification/research and
certification/adversarial same-route cliques. The prior v8 result is
recomputed as a lower bound, so pruning cannot make the selected wave worse
under the stated objective. Equality between the replayable upper bound and
selected objective certifies a global optimum; a nonzero gap remains explicitly
a bounded approximation. Policy v17 quotients equal-value partial states that
have the same structural conflict projection. Policy v18 strengthens this to
the exact conflict neighborhood in the unprocessed suffix, represented by
indexed bitsets, and keeps the lexicographically least representative. This
turns payload-label symmetries and structurally different but continuation-
equivalent partial solutions into one state without changing feasibility,
objective value, or canonical tie-breaking within an equivalence class. Policy
v19 additionally retains states whose upper bound equals the incumbent on waves
of at most 128 candidates; this closes a distinct global tie-breaking defect in
which v18 could certify the optimal objective but discard the lexicographically
least optimal candidate-ID tuple. Its trace separately records and certifies
objective optimality and canonical selection. Policy v20 removes the size
restriction without retaining every tied state: for each suffix and remaining
cardinality it precomputes the lexicographically least possible ID subsequence.
An incumbent-equal state is pruned only when this optimistic tuple cannot beat
the incumbent, and the same lower bound is retained for truncated states. The
certificate therefore proves the globally least tied tuple whenever its
objective certificate is exact and the discarded canonical bound is no better.
Policy v21 additionally removes a partial state when another state at the same
layer has used no more total or per-class capacity, retains at least as much of
each token pool, blocks a subset of the remaining candidates, and has a
lexicographically no-worse objective (and candidate-ID tuple on equality).
Every continuation of the removed state is therefore feasible from the retained
state and cannot improve on it. This exact dominance reduction is applied to
small waves and to large-wave layers whose post-quotient frontier has at most
32 states, directly bounding its pairwise comparison cost; other large-wave
layers retain v20 behavior. V21 also caps the suffix-table
cardinality at 32. A cardinality beyond that cap receives the conservative empty
tuple lower bound, which can reduce pruning or leave canonicality unproved but
cannot create a false certificate. The live scheduler's wave capacity is at
most seven, so this cap does not affect production selection.
Policy v22 adds a certificate-triggered best-first completion phase. It runs
only when the beam leaves an objective gap or an unresolved canonical tie,
orders unexplored states by the same admissible upper bound and candidate-ID
lower bound, and stops after a fixed 20,000 expanded states. Exhausting the
queue proves the exact optimum; reaching the state limit records the remaining
frontier bound without overclaiming. A default-width 129-candidate regression
improves from v21's `(34, 5200, 6, 0)` with upper bound
`(36, 3900, 6, 0)` to the certified optimum `(36, 3900, 6, 0)` after 484
completion states.

Policy v23 excludes individually infeasible rows from the optimization state:
unauthorized candidates, primary conflicts, classes already at capacity,
subminimum positive requests, and requests with no individually available
token pool. Every original row remains in the persisted trace with its explicit
rejection. Consequently, impossible rows cannot narrow the beam, pollute exact
conflict signatures, enlarge suffix tables, or perturb the selected feasible
set merely by being present.
Policy v24 replaces the completion phase's root restart with continuation from
the exact beam states discarded at each truncation layer. Bound-pruned,
future-equivalent, and dominated regions remain omitted because their existing
proofs are sufficient; every other unexplored branch has one frontier
representative. On the default-width 129-candidate regression this reduces
completion from 484 expanded states to 91, while the forced one-state-frontier
regression falls from 15 states to 6. The same 20,000-state ceiling and
fail-closed residual objective/canonical bounds remain in force.
Policy v25 also caps the retained completion frontier at 20,000 states. If an
adversarial wave exceeds that memory bound, the cached frontier is released and
completion safely uses the v23 root search; the trace records the overflow,
total discarded-state count, fallback, and residual certificate. Thus both
completion expansion and retained completion state now have explicit limits.
Exact-neighborhood indexing is
bounded to 4,096 candidates to cap worst-case bitset memory; larger waves fall
back to v17's cheaper structural quotient. Waves of at most 128 candidates use
a 128-state frontier; larger waves retain the 64-state frontier. Historical
v10--v24 traces retain their original transitions. The search does not use
model self-scores and is a resource
optimizer, not evidence of mathematical tree-search performance.

```text
proof spine and current root bottleneck
  researcher proof / construction / citation attempt, with CAS when useful
  literature and adversarial-review companions add independent evidence in parallel
  advisor synthesizes after durable evidence or repeated strategic failure
  researcher converts advice into proof approaches, inferences, proof drafts, or precise proof obligations
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
- Scheduler actions expose ordinal action-priority components and a local
  verifier-filtered outcome heuristic. These values are not probabilities or
  expected values. The heuristic learns only from Albilich's later
  verified or integrated evidence, never from a reference solution or private
  cross-problem cache.
- Repeated bottlenecks trigger a representation-switch contract; literature
  work produces exact source-to-local theorem-adaptation packets; strict and
  integration verification run a selective deterministic proof-interface
  checklist without requiring Lean.
- Multi-branch waves require different mathematical strategy families as well
  as disjoint claim/proof-obligation ownership, so parallel slots pursue
  structurally distinct proof, adversarial, conceptual, or source-adaptation
  categories. This is a diversity constraint, not a proof of originality.
- Proof compression preserves the full history while shrinking the primary
  context to the best route's dependency closure and weakest sufficient bridge.

The complete contracts and artifact schemas are documented in
[`docs/albilich_research_strategy.md`](docs/albilich_research_strategy.md).

## Verification discipline

The strict verifier checks one route packet: the target claim, the route and
its inferences, premise claims, active proof obligations, and the bounded proof, source, and
CAS artifacts. It does not run CAS, search for a new proof, or add fresh
evidence. It can issue a content-bound informal review certificate for

- a local inference when the attached proof artifact proves it;
- an external theorem when the source gives a locatable reference, checked
  hypotheses, checked definitions, and a checked implication to the target;
- a finite computation only after the host reruns the bounded deterministic
  program in a networkless sandbox and the mathematical deduction is checked;
  computational reproduction alone never has proof authority.

It rejects with a precise proof obligation when proof content is missing or truncated, a
citation lacks location or hypothesis checks, a decomposition parent lacks an
assembly argument, or a blocking proof obligation remains. The path to a solved root:

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
`cas_check_recommended` forces `cas`. The adversarial reviewer runs the same loop with its
own history, computation-first (`cas → offline → online`), so it can sweep for
counterexamples, construct by hand, and hunt published prior art in turn.

The advisor supervises both loops. Its manifest shows both mode histories, and
its report can set `directed_researcher_mode` or
`directed_adversarial_review_mode` (stored under a legacy-compatible internal
field), with a
reason and a step count) to send either agent to search, think, or compute for
the next passes. A run consumes a directive only on a completed pass.

The `literature_researcher` stays a separate role because it alone writes
retrieval cards, so it holds the auditable source catalog that citation triage
and certification read. Online researcher and adversarial-review passes search for what the
current attack needs; the librarian maintains the catalog and answers precise
`literature_search_request` proof obligations as a cheap parallel companion.

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
| `hard_problem` | Default. Literature scout, deep researcher attack, route construction, and adversarial review run in parallel when state safety allows. |
| `balanced` | Cheaper. Literature scout, a fast researcher pass, and adversarial review in parallel. |
| `proof_first` | Researcher first; live search follows the caller policy. |
| `independent` | Live search disabled. |
| `citation_pass` | Reference cleanup after integration. |

## Commands

Run from the repository root. The default backend is the Codex CLI. With live
search on, an executed session may export repo-derived proof context to external
model and search services; use `--web-search disabled` for offline attempts.
Codex sessions default to `gpt-6-astra` (GPT-6 Astra) with `xhigh` (Extra High) reasoning;
use `--model` and `--reasoning-effort` to override either setting for a run.

```bash
# initialize, then attempt with defaults
python3 -m agents.generation.phase2.cli init    agents/generation/data/example.md
python3 -m agents.generation.phase2.cli attempt agents/generation/data/example.md

# a long hard-problem run with no wall-clock cap, dashboard on a chosen port
ALBILICH_UI_HEARTBEAT_SECONDS=5 \
python3 -m agents.generation.phase2.cli attempt \
  agents/generation/data/example.md \
  --steps 0 --timeout-sec 7200 \
  --research-mode hard_problem --web-search live \
  --dashboard-port 8793 --no-open-dashboard

# Claude Code as an alternate execution backend
python3 -m agents.generation.phase2.cli attempt agents/generation/data/example.md \
  --backend claude --claude-bin claude --claude-permission-mode dontAsk

# plan without executing; inspect state and outputs
python3 -m agents.generation.phase2.cli attempt agents/generation/data/example.md --dry-run --steps 4
python3 -m agents.generation.phase2.cli status  agents/generation/data/example.md
python3 -m agents.generation.phase2.cli report  agents/generation/data/example.md --write
python3 -m agents.generation.phase2.cli monitor agents/generation/data/example.md --port 8793 --no-open
```

`--steps 0` runs until the token budget, an operator stop, or a terminal
scheduler state stops the attempt. `--max-wall-sec` remains available as an
explicit operator resource cap. If the backend binary is off `PATH`, pass it
with `--codex-bin` or `--claude-bin`. Default `attempt` settings:

```text
research_mode = hard_problem      steps = 0               web_search = live
timeout_sec = 7200                max_wall_sec = none     max_reduction_depth = 4
total_token_budget = 80000000     reserved_verification_budget = 12000000
parallel_branches = 3
```

Local Codex and bundled Claude execution apply an 8 GiB process-tree RSS limit
per child and a 16 GiB limit to the sum of concurrently supervised child
process trees across primary, companion, periodic HMT, and stop-writer
sessions. Set
`ALBILICH_CHILD_MAX_RSS_MB` and
`ALBILICH_MAX_AGGREGATE_CHILD_RSS_MB` to finite positive MiB values to change
them. These are sampled supervisor limits, not kernel memory reservations.
Other custom executors remain serial unless they explicitly declare the
thread-safe/cancellable capability and accept the shared governor; executors
without local supervision are recorded as unverified.

The periodic writer produces one cumulative HMT partial paper after every ten
newly integrated claims. Set `ALBILICH_HMT_INTEGRATED_CLAIM_INTERVAL` to another
positive integer to change the cadence, or to `0` to disable periodic HMT
snapshots. The deprecated `ALBILICH_HMT_REVISION_INTERVAL` name remains a
compatibility alias and is interpreted as an integrated-claim interval.

A run writes to `agents/generation/results/<problem_id>/phase2/`: the SQLite
proof state, `albilich_run_console.md` and `.json`, `phase2_report.md`, and an
`artifacts/` directory with proof drafts, verifier reports, and the final proof.

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

The suite covers the scheduler, patch validator, proof store, parallel
workflow, theorem retrieval, research intelligence, runners, dashboard,
work-mode loops, verification gates, recovery paths, and paper-writing checks.
The latest audited counts and the distinction between live, simulated, and
unavailable backend checks are recorded in the
[`fourth-pass systems review`](docs/fourth_pass_systems_review.md#verification-record).

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
