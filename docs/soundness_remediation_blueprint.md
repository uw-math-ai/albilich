# Albilich soundness remediation blueprint

Status: implemented acceptance contract with fourth-pass repairs. Current
residual limitations are recorded in
[`fourth_pass_systems_review.md`](fourth_pass_systems_review.md); the earlier
`third_pass_systems_review.md` and
`post_remediation_systems_review.md` are historical snapshots.

This document turns the 2026 systems review into falsifiable engineering
requirements.  A finding is not closed because a prompt tells an agent to act
correctly.  It is closed only when the orchestrator or proof-state kernel
enforces the corresponding invariant and an adversarial test demonstrates that
the former failure is rejected.

## Finding-to-implementation traceability

This table maps every finding in the original systems review to its current
enforcement point. “Partial” is used deliberately where the correctness risk is
contained but a structural or empirical goal is not yet complete.

| Original finding | Remediation | Verification | Status |
| --- | --- | --- | --- |
| 1. Role spoofing and ignored preflight failures | Host-created `PatchAuthority`; workflow/session identity binding; all residual preflight errors reject the patch | authority, workflow, patch, and soundness-remediation tests | Closed |
| 2. Child-controlled metrics and budget poisoning | `record_run_metrics` is system-only, run identifiers are insert-only, and usage is derived from provider output | patch, token-usage, workflow tests | Closed |
| 3. Cyclic or dangling proof graphs | Parent/condition existence, nonnegative depth, finite priorities, cycle detection, and recursively grounded derivations are kernel invariants | patch, invariant, fact-graph, scope-state tests | Closed |
| 4. Forged/off-by-one artifact revisions | The host stamps the resulting revision and rejects child-supplied revision metadata | patch and workflow tests | Closed |
| 5. Incomplete resume identity and deltas | Resume identity includes role, target, approach, work/tool modes, model profile, and context hash; row-exact journal deltas cover all state tables | scheduler, workflow, context, replay tests | Closed |
| 6. Silent context loss | Verifier/integration packets contain complete mandatory dependency closures; oversized closures fail with `context_too_large`; optional compaction is marked | context, memory-and-pause, scheduler tests | Closed for verification; compact research packets remain intentionally lossy and marked |
| 7. Artifact type mistaken for verification | Memory classification requires role, verdict, lifecycle, freshness, and a host certificate; negative reports remain unverified | memory, certificate, fact-graph tests | Closed |
| 8. Operator-erasing/truncated fingerprints | Exact identity hashes full Unicode-normalized text without stripping mathematical operators; similarity is advisory | patch and soundness-remediation tests | Closed |
| 9. Monolithic planner and decorative scores | Probability/expected-value claims were removed; top-level action priorities are ordinal and host-derived; all top-level strategy alternatives, every registered open-theorem and solved-root phase, exact integration route, and front-door precondition are compared with versioned canonical hashes, lexicographic policy tiers, and an ancestry-aware within-tier three-deferral bound; parallel waves enumerate candidates before one shared deterministic conflict/capacity transition; snapshot-scoped indexes remove repeated graph, obligation, artifact, and assurance scans; graph v5/manifest v2 distinguishes evaluated zero-output policies from explicitly skipped policies, registers same-tier leader rotation, and corrects its scheduled-primary producer declaration; parallel policy v25 retains v6--v24 identity, liveness, allocation, bound, quotient, tie, dominance, completion, and intrinsic-filter semantics, resumes bounded completion from the pruned beam frontier when it fits, and safely falls back to root search if the frontier memory cap is exceeded | scheduler, research-strategy, research-intelligence, provenance, snapshot-stability, liveness, sibling- and primary-conflict rotation, non-greedy, dominance, bounded-frontier completion, irrelevant-state, and allocation-feasibility counterexamples, exhaustive conflict and budget oracles, partition and neighborhood-mask oracles, objective and canonicality certificates, wave-admission, leader regeneration, exact-integration, evaluated/skipped provenance, full-manifest deletion, schema-downgrade, legacy-replay, wide/deep/dense scale, mutation-fuzz, and latency tests | Partial: graph v5 covers 97 families across twelve scopes and parallel admission is an acyclic standalone module, but the scheduler still has over 17,000 lines, the registry is not a proof that no generator is missing, bounded frontier completion can still honestly retain a nonzero objective or canonicality gap, and there is no verifier-guided long-horizon reachability theorem |
| 10. Self-reported productive progress | Progress and learning use accepted row/artifact deltas linked to the run; strategy family is host assigned | research-intelligence, branch-workbench, scheduler tests | Closed |
| 11. Retroactive/corrupt outcome learning | Only post-run, causally linked evidence receives credit; failed executions cannot inherit later unrelated success | research-intelligence tests | Closed, subject to the observational limits in the post-review |
| 12. Incorrect budget arithmetic | Gross provider tokens include cached input; reasoning tokens are not added twice; protected verification reserve is enforced | token-usage, scheduler, completion-policy tests | Closed |
| 13. Content-free certificates and no revocation | Host certificates bind canonical subject, dependencies, evidence hashes, and revision; downstream status is revoked on change/refutation | certificate, scope-state, fact-graph, soundness-remediation tests | Closed against ordinary workflow mutation |
| 14. Hidden mutations and unstable replay | Generic application no longer synthesizes routes, supersession, or obligation closure; all production artifact ingestion/synchronization and publication escalation use patches; row-exact deltas, complete `1..current_revision` coverage, and stable state hashes are replay checked | patch, workflow, host-artifact replay, deletion-attack, and state-tamper tests | Closed for row-level deterministic audit; semantic re-execution, patch-annotation authentication, and external tamper proofing remain open |
| 15. Weak/self-scored novelty | Portfolio v2 requires at least six categorized approaches, exact semantic signatures, separated selection, prior-failure comparison, and explicit falsification tests | research-strategy and scheduler tests | Closed at contract level; semantic originality still cannot be guaranteed automatically |
| 16. Unreproduced CAS/formal claims | CAS programs are rerun by the host in a networkless resource-limited sandbox; formal authority requires a supported host checker; computation alone has no proof authority | CAS, formal-handoff, patch, soundness-remediation tests | Closed fail-safe boundary; installed backend coverage is incomplete |
| 17. Regex-only security and permissive Claude mode | Per-session evidence capsules, least-privilege Codex profiles, fail-closed Claude settings, denied network/tool delegation, and metadata-forgery rejection | Codex, Claude, scheduler, workflow, soundness-remediation tests | Closed in command/configuration tests; a live Claude smoke test was unavailable locally |
| 18. Schema/snapshot/CI/maintainability gaps | Schema v3 ordered migrations, backups, row-exact snapshot/journal data, replay audit, and CI were added | migration, replay, full regression suite | Partial: current-schema audit/CI are closed; pre-v3 histories cannot acquire v3 replay proof retroactively, and scheduler/context/patch modules remain too large |
| 19. Noncausal, self-graded experiments | Existing archives are labeled `historical_unvalidated`; an archive registry/auditor enforces checksums and the future protocol; README performance claims were withdrawn | experiment auditor and soundness-remediation tests | Closed as an honesty defect; no existing archive establishes general or causal performance |

During the post-fix review, operation-level scope was tightened further: a
session may now refer only to entity identifiers disclosed in its exact context
packet (plus same-patch identifiers). Valid resume chains retain the union of
previously disclosed identifiers. This prevents a model from guessing and
mutating an unrelated record in the same database.

The post-fix review also found and closed two replay gaps. Operator input,
reference solutions, hard-stop records, branch workbench versions, and
publication-review escalation now mutate proof state only through explicit
operator/system patches. Replay now rejects a missing leading journal prefix or
an entirely deleted patch table by requiring exactly one applied record for
every proof-state revision after genesis.

## Third-pass closure addendum

The original R1-R15 requirements remain the acceptance baseline. A further
adversarial pass found failures at subsystem boundaries that those requirements
did not state precisely enough:

| Addendum | Enforced requirement | Status and verification |
| --- | --- | --- |
| T1. Concurrent audit history | Acquire a write transaction before reading an event-chain predecessor; compute checkpoint state and all heads in one read snapshot | Closed; concurrent-writer and checkpoint-interleaving tests |
| T2. Audit custody | Chain patch annotations and policy events separately; optionally sign the complete state/head statement outside SQLite; reject unsafe private-key permissions | Closed for local integrity and optional signatures; public transparency/WORM custody remains open |
| T3. Planning consistency | Bracket planning with audit heads and reject every prepared primary or companion session whose planning heads no longer match before launch | Closed in the workflow dispatch path; direct scheduler callers remain outside this wrapper |
| T4. Heterogeneous assurance | Require each qualifying reviewer class to cover the exact claim and every inference; never pool partial coverage; pause once when a required backend family is unavailable | Closed at the recorded-provenance level; model-family labels do not prove epistemic independence |
| T5. Host parser/compiler isolation | Bound and sandbox reference PDF extraction and LaTeX compilation; attest executables; disable network/shell escape; hash sources, extracted text, compilers, and new PDFs | Closed for new artifacts and tested host paths; legacy PDFs and complete runtime-closure attestation remain partial |
| T6. Formal/computational adapters | Bind the exact formal target; reproduce deterministic CAS programs twice with stable stdout/stderr and successful exits | Closed as a fail-safe contract; semantic encoding and unavailable live backends remain outside the result |
| T7. Focused-context discovery | Use a type-fair bounded catalog, exact coverage metadata, deterministic revision pagination, and cold exact-object requests | Closed against entity-type starvation; explicit page selection and unbounded project retention remain open |
| T8. Mathematical terminology | Expose proof obligations, proof drafts, catalogs/records, test suites, and adversarial reviewers while preserving exact identifiers and quoted evidence | Closed for model/public interfaces; legacy schema and compatibility names remain intentionally internal |
| T9. Dashboard control boundary | Require an unguessable per-instance token and a bounded request for steering mutations; cap and integrity-check served publication files | Closed for loopback anti-forgery and bounded PDF serving; non-loopback read authentication remains open |

Third-pass tests also require state rows and audit/policy heads in one context
snapshot, prevent stale plans from dispatching, reject split-family review
coverage, preserve validation certificates across a compatible lifecycle
integration, and verify PDF content before new HMT/publication artifacts are
served.

## Fourth-pass closure addendum

The next adversarial cycle added the following enforceable requirements. The
remaining structural and empirical work is listed in the fourth-pass report;
it is not marked closed here merely because an implementation plan exists.

| Addendum | Enforced requirement | Status and verification |
| --- | --- | --- |
| F1. Current projection integrity | Seal run-selection provenance and the current event/configuration projection alongside mathematical rows and the patch head; bind full replay to the recorded native-genesis seal; schema-check policy events and bind run-control policy to its exact telemetry event | Closed for the current projection, genesis, and tail; full replay or an external checkpoint is still required for old non-head entries |
| F2. Total integrity checks | Malformed database integers, event payloads, and journal-head rows must return an invalid seal rather than escape as parser exceptions | Closed by malformed-row regressions |
| F3. Bounded patch structure | Bound operation count, nesting, node count, UTF-8 size, individual strings, integer magnitude, and finite numeric values before and after normalization | Closed at the patch kernel boundary |
| F4. Stable evidence copying | Certified-scope import must read through a stable no-follow descriptor, install atomically, verify the managed copy, and roll it back on ordinary failure | Closed for process-level failures; database/filesystem crash atomicity remains impossible without a different storage design |
| F5. Output path safety | Snapshot, oversized-output, scope-artifact, and external-checkpoint writers must not follow a final symbolic link | Closed for the tested writers; same-user replacement of broader directory trees remains in the host threat model |
| F6. Production catalog paging | The type-fair context catalog must derive its page from the actual `problem_state.current_revision` snapshot field | Closed in catalog v3; explicit page selection remains open |
| F7. Long-run query support | Index policy-event and applied-patch endpoint lookups used by current seals | Closed; the underlying projection/provenance hashes remain linear in current state |
| F8. Process accounting | Use collision-resistant run identifiers, enumerate Linux descendants from every thread, fail conservatively when RSS cannot be observed, sum concurrent locally supervised Codex/Claude child process trees across primary, companion, HMT, repair, and stop-writer execution, cancel the complete set on crossing, and bind the committed limit plus a millimebibyte-precision observed aggregate peak into the durable result | Closed as sampled local supervisor accounting; transient spikes, detached descendants, unsupervised external executors, and a cgroup/service quota remain open |

Fourth-pass tests also require single-read reference ingestion, same-transaction
snapshot validation, authenticated monitor text, correct scope-import seal
advancement, and a distinct `sandbox_unavailable` outcome for persistent
namespace-allocation failure.

## Scheduler-closure addendum

| Addendum | Enforced requirement | Status and verification |
| --- | --- | --- |
| S1. Complete nested provenance | Commit every supplied nested comparison by parent candidate, including comparisons below an unselected parent; reject missing, orphaned, or modified nested traces | Closed in decision-policy v7 with v4-v6 validation compatibility |
| S2. Complete verification enumeration | Materialize every verifier-ready route (including alternatives for one claim), fresh-evidence handoff, support-theorem precheck, verifier loop, dependency threat, pending counterexample, status reconciliation, and unrouted proof claim | Closed within the declared verification-stratum scope; global completeness remains limited by the registered generator graph |
| S3. Subject-specific cooldown | Scope counterexample-validation history to the exact selected artifact when v7 provenance exists; scope advisor completion to the assigned role and target | Closed by multiple-candidate, failed-run, unrelated-target, and cross-role directive regressions |
| S4. Semantic evidence identity | Detect unrouted proof evidence by artifact type and confirmed counterexamples by exact identifier/path basename, never identifier substrings | Closed by arbitrary-ID and prefix-collision regressions |
| S5. Dense scheduling scale | Cache route evidence, readiness results, verifier candidates, coverage checks, and parsed deferral history per immutable planning snapshot; prohibit quadratic candidate membership checks; byte-bound the online trace projection | Closed for the measured synthetic fixtures; the latest 2,000-route/4,000-candidate run enumerated in 175.83 ms p95, validated in 27.73 ms p95, and replayed the bounded history in 200.37 ms p95; immutable trace-storage growth remains open |
| S6. Complete evidence assimilation | Enumerate every eligible exact-citation obligation, source handoff, proof artifact awaiting conversion, root-target citation card, and root-target definition-audit card; bind cooldown, completion, and bounded deferral to the exact object | Closed within the declared evidence-stratum scope by simultaneous-queue, peer-survival, durable-subject, starvation, and dense-scale regressions; the latest 2,000-candidate run enumerated in 52.38 ms p95 and replayed the byte-bounded history in 67.75 ms p95 |
| S7. Complete recovery, obligation, and residual enumeration | Enumerate every exact bottleneck, request, obstruction cluster, mathematical obligation, route repair, failed/blocked decomposition, ready decomposition step, route-triage/root-alignment/proof-compression target, and unverified claim; give every object a stable identity and exact cooldown/deferral accounting | Closed within the registered strata by simultaneous-object, peer-survival, cross-plan, exact-lease, and dense 6,144-candidate regressions |
| S8. Complete sequential integration | Compare every eligible verified sufficient route, including same-conclusion alternatives; bind assurance to each exact route in the same snapshot; never reintegrate an integrated claim | Closed by exact-route trace, lifecycle, assurance-projection, blocker semantics, and parallel distinct-claim regressions |
| S9. Compact authoritative traces | Persist only candidate selection inputs, exact action commitments, and validator-checkable dispositions; do not duplicate uncommitted explanatory fields | Closed for row compaction and online history: the dense obligation trace fell from 4.40 MiB to 2.85 MiB; immutable content-addressed/Merkle storage remains open |
| S10. Complete parallel admission input | Materialize all verifier, support-precheck, citation, decomposition, integration, and branch-template companions before one persisted-budget conflict/capacity/token admission pass; keep exact stable IDs and every rejection | Closed within the registered wave scope by policy v25: canonical full-stable-payload identities, exact hashing, bounded aging across capacity classes and sibling conflicts, typed distinction between serializable primary ownership and structural exclusion, same-tier nonmandatory leader rotation with full companion regeneration, minimum-feasible-grant subset search, deterministic max--min residual allocation, an executable v8 non-regression lower bound, replayable resource/clique/neighborhood upper certificates, exact future-equivalence quotients, exact-cardinality suffix bounds, exact partial-state dominance, certificate-triggered bounded pruned-frontier completion with a bounded-memory root fallback, intrinsic infeasibility filtering, fail-closed memory/state caps, one shared live/replay transition, search/configuration/snapshot/evaluation-manifest-bound wave identifiers, and full v3--v25 replay validation; empirically calibrated workload value/cost remains open |
| S11. Total deterministic policy validation | Reject malformed versions, scalar/container types, identities, capacities, digests, dispositions, non-canonical JSON, and nested values before comparison; use one pure outcome transition for both live selection and replay; detect semantic drift independently of that shared implementation | Closed for the tested generic, parallel, and action-routing schemas by permanent mutation matrices, deterministic 30,000/50,000-case nested-mutation fuzz campaigns, import-time semantic commitments for parallel v3--v25, generic v4--v8, and action contract v1--v5, and a real-Git CI guard over those contracts and the candidate-generator graph that rejects modified/removed commitments, noncontiguous insertion, and active-epoch downgrade. This remains executable evidence rather than a formal proof, and an administrator who can bypass required CI is outside the trust model |
| S12. Admission dependency direction | Keep identity, conflict, capacity, outcome, history, replay, and wave-binding logic outside the scheduler; prohibit a validation import edge back to the scheduler | Closed by module extraction, architecture regression, and live/replay transition-spy tests |
| S13. Cross-layer wave binding | Reject companions beside terminal/exclusive primaries; require authenticated production snapshot digests; commit the declared generator scope; bind every generic wrapper to one admitted wave candidate and its input-action hash; enrich mathematical strategy before admission; require every admitted action exactly once in the durable group; reconstruct and verify each admitted input | Closed by terminal-primary, budget-authorization, scope/snapshot-tamper, wrapper-transplant, transformation-flag, omitted-companion, and post-admission-mutation regressions |
| S14. Executable action contract | Keep scheduler-produced modes consistent with the authoritative dispatch/run contract and prevent malformed raw generator rows from becoming wave leaders | Partial: append-only action contract v1--v5 commits modes, executability, budget/role classification, actor routing, resource-allocation arithmetic, polymorphic `prove` classification, and request limits; each new trace persists its exact contract identity. Construction and dispatch fail closed, dispatch allocations must match authenticated state and group limits, pre-execution claims verify the action/plan/context binding, and deterministic telemetry requires the complete dispatch/attempt/result lifecycle and must equal the durable result's resource, execution, context, status, and accepted-output projection. Execution contract v2 additionally binds local aggregate child-RSS and concurrency capabilities and distinguishes unsupervised external enforcement. Mode-specific auxiliary payload fields remain untyped |

These closures do not establish global scheduler liveness, global optimality,
or theorem-solving quality. A registered scope can be complete while the
generator registry itself omits a useful policy, and all measured fixtures are
synthetic.

## Standard terminology

New user-facing interfaces use ordinary mathematical language:

| Legacy expression | Preferred expression |
| --- | --- |
| debt | proof obligation |
| debt ledger | list of open proof obligations |
| claim ledger | theorem/lemma status table |
| battery | test suite or collection of checks |
| villain | counterexample researcher |
| proof dossier | proof draft |
| route | proof approach (where prose permits) |
| branded defeat loop | decisive proof-obligation cycle |
| paperwork throttle | mathematical-output focus |
| proof-pressure scheduler | proof-strategy review |

The SQLite `debts` table and the v1 operation names remain readable during a
compatibility period.  The public patch contract accepts and emits
`add_proof_obligation`, `update_proof_obligation`, and
`resolve_proof_obligation`; old operation names are normalized at the storage
boundary.  No migration may reinterpret an existing mathematical record.

## Non-negotiable trust model

The child model is an untrusted proposer.  It may propose mathematical text and
state changes, but it may not choose its authority, manufacture run telemetry,
declare the context it saw, or determine whether its own proof is certified.
Authority and telemetry originate in the host process.  Proof certification is
valid only for a canonical, immutable subject and dependency closure.

The proof-state kernel has four trust domains:

1. `session`: a host-created session contract binds role, mode, target, proof
   approach, context revision/hash, research mode, CAS permission, and web
   permission.
2. `system`: deterministic orchestrator mutations such as run telemetry and
   lint synchronization.
3. `operator`: an explicit human-initiated local patch.
4. `migration`: versioned, deterministic schema/data migrations.

No API that ingests child output may fall back to self-declared authority.

## Remediation and acceptance matrix

### R1. Session authority and preflight enforcement

- Add an immutable host-side session contract.
- Compare the returned patch's role and target with the contract.  Bind mode,
  proof approach, context hash/revision, research mode, and tool permissions
  from the contract rather than from child JSON.
- Validate operation scope against the scheduled action.
- Reject a patch whenever preflight errors remain, including failed/timed-out
  repair and the Claude detection-only path.
- Record the session contract in the applied-patch audit row/event.
- Tests: every role-spoofing permutation; target/approach/context mismatch;
  residual preflight error; stale retry preserving the original authority.

### R2. Host-only telemetry and budget integrity

- `record_run_metrics` is legal only under `system` authority.
- Use insert-only run identifiers.  A duplicate run is an error, never an
  `INSERT OR REPLACE` overwrite.
- Derive actor, action, revisions, context hash, output artifacts, usage, and
  status from host execution data.
- Define the allocation as gross model tokens: use provider `total_tokens`, or
  `input_tokens + output_tokens`; reasoning tokens are a subset of output and
  are never added twice.  Cached input remains part of gross usage.
- Protect the verification reserve from non-verification overrun and record any
  provider overrun explicitly.
- Tests: researcher telemetry injection, duplicate-run overwrite, cache-heavy
  usage, reasoning-token double count, and reserve overrun.

### R3. Well-founded proof graph and recursive integration

- Validate every claim parent and every condition identifier.
- Require nonnegative reduction depth and finite bounded numeric priorities.
- Reject self-dependencies and every strongly connected component in the
  claim/inference dependency graph.
- Define a recursively grounded verified derivation.  A verified conclusion is
  grounded only if one verified inference has grounded premises/conditions, or
  a premise-free inference has subject-bound verification evidence.
- An integrated proof approach must have a grounded derivation of its exact
  conclusion; all proof obligations in that derivation must be discharged.
- Tests: two-node and longer cycles, cross-approach cycles, dangling parents,
  negative depth, verified but ungrounded premises, alternative good/bad
  derivations, and a valid acyclic proof.

### R4. Canonical certification and revocation

- Canonicalize each claim/inference/approach and its dependency closure with
  SHA-256, preserving mathematical punctuation and operators.
- Bind verification and integration reports to subject digest, dependency
  digest, context revision, and exact reviewed artifact hashes.
- Any post-certification change to a statement, explanation, premises,
  conditions, approach membership, or evidence invalidates downstream
  certification deterministically.
- Refutation or supersession propagates staleness to every dependent
  certificate and integration.
- Tests: append-after-verification, changed premise, replaced evidence file,
  refuted transitive premise, and unchanged append-free replay.

### R5. Revision and resume correctness

- Artifacts created by patch `N -> N+1` receive state revision `N+1`; child
  patches may not set it.
- Resume identity includes role, mode, target, proof approach, research mode,
  CAS/web permissions, model profile, and prior context hash.
- A changed identity forces a full context packet.
- The delta is generated from applied patch/event history, not artifact-only
  timestamps, and includes changed claims, approaches, inferences, premises,
  artifacts, opened/discharged obligations, and status changes.
- Every resume packet is size-fitted and reports a real size/token estimate.
- Tests: first-post-checkpoint artifact, forged revision, changed approach,
  online-to-offline/CAS transition, resolved obligation, and provider-context
  loss fallback.

### R6. Complete, bounded verification context

- A verifier receives the complete transitive dependency closure for the
  scheduled subject, not fixed global top-N slices.
- Required proof text, subject statements, dependencies, and open blocking
  obligations are indivisible.  If they do not fit, reject scheduling with a
  structured `context_too_large` result or split the proof explicitly; never
  silently truncate them.
- Text compaction is marked and keeps both head and tail only for optional
  expository material.  Mathematical expressions are never prefix-truncated.
- `_fit_manifest` must either meet the bound or raise a typed error.
- Tests: more than 12 inferences, more than 18,000 proof characters, a crucial
  final paragraph, oversized mandatory closure, and omitted-blocker attacks.

### R7. Semantic memory classification

- Artifact type alone never implies verification.  Classification uses
  producer authority, canonical binding, verdict, lifecycle, and staleness.
- Negative integration/verification reports remain unverified evidence.
- The theorem library uses an explicit enum, not substring matching.
- Tests: `integrates=false`, failed formal result, rejected paper, the word
  `uncertified`, revoked certificate, and a valid certificate.

### R8. Mathematical fingerprints and duplicate handling

- Exact fingerprints hash Unicode-normalized full text without truncation.
- A separate conservative similarity key may aid suggestions but can never
  reject a mathematically distinct statement.
- Operator/negation/order symbols are preserved.
- Tests: `<` versus `>`, `=` versus `!=`, sign changes, quantifier changes,
  Unicode/LaTeX equivalents, and differences after character 500.

### R9. Planner architecture and auditable choice

- Break the monolithic priority chain into independent candidate generators,
  hard admissibility constraints, and one comparison stage.
- Score every admissible candidate, including forced maintenance actions, with
  stated features and uncertainty.  Hard safety gates remain non-probabilistic.
- Record all candidates and the reason for selection/rejection.
- Add reachability tests for each policy guard and mutation tests that fail if
  a guard becomes shadowed.

### R10. Objective progress and causal learning

- Productive progress is computed from proof-state diffs and validated links,
  never self-reported metadata.
- Outcome learning uses only evidence that existed after the run and is
  causally linked through output artifact/claim/inference identifiers.
- Failed executions cannot become successes because their target was proved
  later by another run.
- Replace keyword strategy-family assignment with an explicit host-assigned
  strategy identifier and retain an `unknown` category.
- Treat outcome values as ordinal, uncalibrated indicators. Do not call them
  probabilities, posterior probabilities, expected values, or information gain
  unless held-out calibration and the corresponding statistical semantics are
  demonstrated.
- Tests: fake productive labels, unrelated later proof, failed run/later proof,
  and one genuinely causal success.

### R11. Explicit deterministic mutations and replay

- Remove hidden graph mutation from generic patch application.  Auto-routing,
  statement supersession, obligation reconciliation, and integration
  invalidation become explicit system operations recorded in the patch log.
- Never infer evidence from an identifier substring.
- Manifest hashes exclude volatile creation time and include a format version.
- Replaying a snapshot plus ordered applied patches under the recorded schema
  version must reproduce the canonical state hash.
- Tests: no unrequested route creation, missing artifact named `proof`, stable
  manifest hash, and replay equivalence.

### R12. Novelty and mathematical evaluation

- Generate a declared minimum number of independently seeded approaches;
  validate semantic diversity against statements, dependencies, method cards,
  theorem library, and prior failures.
- Separate generation from selection and require an explicit comparison of all
  candidates.  Self-scores are advisory only.
- Expand method retrieval beyond fixed keyword overlap with mathematical-object
  and operation tags; record why a method was retrieved.
- Add held-out evaluation for novelty, usefulness, correctness, and genuine
  non-rediscovery, graded independently of the generator.
- Mathematical verification must distinguish informal review, mechanically
  checked finite computation, and formal proof.  CAS evidence is independently
  rerun from captured input/environment/output before it supports a theorem.
- Infinite conclusions require a verified reduction encoded as a proof-graph
  dependency, not a self-authored boolean.

### R13. Evidence isolation and process security

- Execute children in a materialized, content-hashed evidence capsule with no path to the main
  repository, result databases, sibling experiments, or answer keys.
- Enforce filesystem/network/CAS policy at process level.  Log regexes are
  supplemental detection only.
- Default Claude to a restricted permission mode.  Elevated access is an
  explicit operator opt-in.
- Treat retrieved text and problem files as untrusted data; prevent them from
  changing tool or patch authority.
- Tests: direct/symlink/path-traversal reads, SQLite access, sibling experiment
  access, answer-key access, forbidden network mode, and allowed capsule reads.

### R14. Schema, snapshots, and maintainability

- Increment the schema and implement ordered, idempotent migrations with a
  compatibility check and backup/rollback behavior.
- Add SQL checks/foreign keys where SQLite can express the invariant; retain
  kernel checks for polymorphic relations.
- Full audit snapshots include patches and events or explicitly reference an
  immutable log segment hash.
- Split the scheduler/context/patch monoliths at stable domain boundaries and
  add architecture tests for dependency direction.
- Add CI that runs unit, adversarial, migration, replay, lint, and monitor tests.
- Documentation reports test counts mechanically, not as a hard-coded number.

### R15. Experimental claims and reproducibility

- Do not present self-judged answer extraction as proof-solving evidence.
- Publish problem-selection rules, exact immutable prompts, environment,
  externally authenticated randomization inputs, complete run/event logs, proof database/snapshot, all proof and
  CAS artifacts, independent grades, and hashes.
- Ablations must share the same problem, prompt, context, budget, model, and
  stopping rule and use repeated trials.
- Add an archive auditor that fails on missing declared material, target/answer
  leakage, prompt mismatch, semantic problem mismatch, and unverified
  scoreboard labels.
- Existing incomplete archives remain available but are labeled
  `historical_unvalidated`; headline claims are removed until compliant runs
  exist.

## Implementation order

1. R1-R4: authority, telemetry, graph soundness, certificate binding.
2. R5-R8: revisions, context completeness, memory, fingerprints.
3. R10-R11 and budget accounting: objective learning and deterministic replay.
4. R13-R15: isolation, schema/auditability, and experimental honesty.
5. R9/R12: planner and novelty redesign after the state/evaluation substrate is
   trustworthy.
6. Terminology/UI/docs migration and removal of remaining legacy prose.
7. Full adversarial suite, full regression suite, migration/replay tests, then
   a fresh design review whose residual findings are published rather than
   suppressed.

## Release criterion

The fixed version may call a result `formally verified` only when a supported
formal backend has checked it.  It may call a result `independently reviewed`
when the informal-review certificate and recursive grounding checks pass.  It
may call the root `established by the recorded argument` only after recursive
integration, certificate freshness, and all blocking proof obligations pass.
Until the experimental protocol is satisfied, benchmark results are descriptive
case studies and not evidence of a general theorem-proving success rate.
