# Albilich post-remediation systems review

> Historical second-pass snapshot retained for provenance. It is superseded by
> [`third_pass_systems_review.md`](third_pass_systems_review.md).

Date: 2026-09-01

This is a second, adversarial review of the remediated implementation. It does
not assume that passing tests makes generated mathematics true. The accompanying
`soundness_remediation_blueprint.md` maps every original finding to its
enforcement point and records the two areas that remain only partially
remediated.

## Executive assessment

The proof-state kernel is materially safer than the reviewed version. A child
model is now an untrusted proposer rather than the source of its own role,
telemetry, context identity, artifact revision, certificate, or computational
verdict. Proof records have well-founded dependency checks, exact mathematical
identity, content-bound host certificates, deterministic invalidation, explicit
proof-obligation closure, and a row-exact audit journal. Verifier contexts fail
closed instead of silently omitting mandatory mathematics. Historical
experiment archives no longer support performance claims they cannot justify.

That does **not** make Albilich a sound automated theorem prover. Its informal
verification remains fallible model judgment; its planner remains structurally
overgrown; its novelty checks enforce diversity of proposals rather than genuine
originality; and there is no protocol-valid benchmark evidence for general
mathematical performance. The correct description is now: an auditable,
fail-closed orchestration system for model-assisted mathematical research, with
optional mechanically reproduced computation and formal checking.

## Review method

The review inspected the trust boundary, schema and migrations, patch kernel,
graph invariants, certificate construction/revocation, replay, context building,
resume logic, budget accounting, outcome learning, planner, novelty portfolio,
CAS/formal adapters, Codex/Claude launch policies, experiment archives, public
documentation, and tests. Formerly permissive fixtures were rewritten to pass
through real researcher, strict-verifier, and integration-verifier transitions
rather than directly forging verified SQL state.

Tests include negative cases for role and target spoofing, host-metadata
forgery, graph cycles, dangling dependencies, false obligation closure,
certificate staleness, evidence changes, context overflow, revision forgery,
resume-identity changes, token-accounting attacks, replay tampering, distinct
mathematical operators, unknown formal backends, archive overclaiming, symbolic
link evidence, mutation of an undisclosed database entity, unjournaled host
artifact workflows, and deletion of a leading or complete patch history.

The tests do not include a paid live model proof run, a live Claude process, a
successful Lean/Coq/Agda check, or Julia/Macaulay2 reproduction in this
environment. Those omissions are limitations, not implied successes.

## Review by system dimension

### Harness design

What is now strong:

- `PatchAuthority` binds a session to host-selected role, mode, target, proof
  approach, revision, context hash, work mode, and tool policy. Operation-level
  identifiers must also have been disclosed by the host packet or created in
  the same patch.
- Child output cannot write host telemetry, artifact revisions, reproduction
  results, or certificate bindings. The kernel rejects unresolved preflight
  errors and applies accepted patches transactionally.
- Claim/inference dependencies are checked for existence and acyclicity.
  Integration requires a recursively grounded verified derivation rather than
  a status label on an isolated conclusion.
- Verification and integration certificates bind the canonical subject,
  dependency closure, and exact evidence content. Relevant changes or
  refutations revoke downstream status.
- State changes have row-exact before/after deltas and chained hashes. Ordinary
  unjournaled mutation, missing revisions, and modified deltas are detected.
  Operator document/reference ingestion, hard-stop records, immutable branch
  workbench versions, and publication escalation all pass through this same
  journal rather than writing proof-state rows directly.

What remains weak:

- The scheduler is 11,462 lines, while `context_builder.py` is 6,366 lines and
  `patches.py` is 4,985 lines. The main planner is still a long sequential
  priority chain. A branch inserted early can shadow later policy despite broad
  regression coverage. This is the largest remaining engineering defect.
- Not every admissible action is materialized into one uniform candidate set.
  Research-strategy actions have comparable ordinal assessments, but many
  maintenance/safety branches return immediately. Consequently, the audit log
  cannot always show the complete rejected-candidate set for a decision.
- The operation-scope checker uses an explicit registry of identifier fields.
  A future operation that introduces a new reference field must update this
  registry or it can recreate an authority gap. The schema should generate this
  registry mechanically.
- The audit journal is integrity-checking, not tamper-proof. An administrator
  able to rewrite the database, every delta, and every chained hash can forge a
  coherent history. There is no external signature, transparency log, or
  immutable checkpoint. Moreover, state endpoint hashes bind row changes but
  not non-state patch annotations such as rationale; those annotations need a
  separate entry hash if accidental edits must also be detected.
- Replay validates row transitions backwards; it does not re-execute every
  historical operation through the current or original kernel. It detects
  ordinary corruption but is not a full semantic determinism proof.
- A pre-v3 database can be migrated conservatively, but its old decisions did
  not record v3 deltas and certificates. Such history is correctly
  non-replayable; migration cannot manufacture retrospective audit evidence.
- Operator run configuration and event history (for example completion policy,
  branch count, pause state, and steering notes) is deliberately outside the
  mathematical state projection. It cannot create a certificate, but it can
  change stopping and scheduling behavior without being covered by the proof
  journal hashes.

### Context management

What is now strong:

- Strict and integration verifiers receive the complete mandatory transitive
  closure for the subject. Required statements, proof text, dependencies, and
  blocking proof obligations are indivisible. If they do not fit, scheduling
  fails explicitly with `context_too_large`.
- Mathematical identity no longer depends on truncated text. Optional prose
  compaction is marked and retains both head and tail.
- Resume identity includes all policy-relevant fields and the previous packet
  hash. Resume deltas are derived from the exact patch journal and contain all
  changed row classes. Missing prior identity or an oversized/incomplete delta
  forces a cold, complete packet.
- Evidence is copied into a new per-session capsule; symbolic-link sources and
  source swaps fail closed. Registered artifacts and existing configured CAS
  assets are checked byte-for-byte against packet SHA-256 values before the
  child sees them. Valid resume chains retain the union of disclosed entity
  identifiers.

What remains weak:

- Researcher packets are intentionally lossy. They mark omissions, but there is
  no first-class on-demand retrieval handshake by omitted object identifier.
  A useful but nonmandatory old branch can therefore disappear from practical
  attention even though it remains in the database.
- Context completeness is syntactic, not cognitive. A model can overlook an
  included hypothesis, especially in a large closure. The proof-interface
  checklist reduces this risk but does not eliminate it.
- Resume correctness still depends on the provider actually preserving the
  session associated with its identifier. Hash-bound deltas prevent silent
  state mismatch, but they cannot inspect the provider's hidden context.
- State and audit history grow without a formal retention/compaction policy.
  Context is bounded, but database, artifact, event, and outcome-history growth
  can become an operational long-run problem.

### Long-horizon reasoning

What is now strong:

- Progress is computed from accepted state deltas and evidence links, not model
  self-report. A failed run cannot inherit success from an unrelated later run.
- Proof approaches, exact obligations, negative results, branch summaries,
  verification reserve, bottleneck leases, and resume deltas give long runs
  persistent state outside any model context window.
- Strategy outcomes are explicitly ordinal and host assigned. The system no
  longer calls its heuristic values Bayesian posteriors, probabilities,
  expected values, or information gain.
- Hidden auto-routing, semantic supersession, and implicit obligation closure
  were removed from generic patch application, making long-run state changes
  inspectable.

What remains weak:

- Outcome learning is observational and selection-biased. The scheduler chooses
  which strategy receives effort, so later success rates cannot identify causal
  strategy quality without randomized or matched exploration.
- The sequential planner contains many hand-tuned guard interactions and
  cooldowns. Tests establish examples of reachability, not global absence of
  starvation or oscillation across all proof states.
- There is no formal convergence or fairness property for branches. The system
  can still spend a large allocation on a coherent but false research program
  if model-generated evidence repeatedly looks locally promising.
- Long-horizon coordination uses one proof-state worldview. Independent
  verifiers can share the same model family and correlated blind spots; there
  is no required heterogeneous second model or human checkpoint for high-impact
  informal certificates.

### Ability to generate novel ideas

What is now strong:

- Portfolio version 2 requires at least six proposals across independently
  seeded mechanism categories, with full semantic signatures, root
  consequences, failure modes, falsification tests, and comparison against
  prior approaches and negative results.
- Generation and selection are separated. Self-scores are advisory and
  duplicates cannot count as diversity merely by paraphrase.
- Method retrieval uses mathematical-object and operation tags in addition to
  text overlap, and records why a method was retrieved.

What remains weak:

- Diversity constraints are not originality proofs. Six category-distinct
  cards can still be standard rediscoveries, shallow variants, or mathematically
  irrelevant.
- The generator, comparator, and informal verifier may be the same model family.
  Correlated taste can make an idea look novel, useful, and correct to every
  stage.
- There is no protocol-valid held-out evaluation with independent expert labels
  for novelty, usefulness, non-rediscovery, and eventual proof contribution.
- The method-card library is curated and finite. Its taxonomy can bias search
  toward represented techniques and away from genuinely new mathematical
  language.

### Mathematical ability and verification

What is now strong:

- Verification levels are separated: informal review, reproduced finite
  computation, and formal proof are distinct. A CAS boolean never certifies an
  infinite statement; the finite-to-general reduction must appear as a verified
  dependency.
- Python computation is actually rerun with exact input/output digests in a
  networkless `bubblewrap` sandbox under memory, CPU, process, file-size, time,
  and output limits. Reproduction has no proof authority by itself.
- Lean 4, Coq, and Agda are the only accepted formal backend names. Unsupported
  or unavailable checkers fail closed, and unchecked formal-looking text cannot
  certify a claim.
- Exact fingerprints preserve inequalities, negation, quantifiers, and late
  text differences. Integration checks verified premises, inferences,
  dependencies, blocking obligations, and root alignment.

What remains weak:

- Informal verification is still language-model judgment and can accept a
  subtle false proof. Host certificates prove what was reviewed and whether it
  changed; they do not prove mathematical truth.
- No supported formal checker was installed for a successful end-to-end formal
  test here. Only fail-closed behavior was exercised.
- Only Python reproduction was executed in this environment. Julia and
  Macaulay2 adapters were not available for a live reproduction test.
- The host verifies deterministic output equality, not that the program models
  the claimed mathematical object correctly. That link remains part of the
  mathematical proof and informal/formal review.
- No independent cross-implementation arithmetic or CAS comparison is required
  for high-stakes finite computations.

## Residual findings by priority

| Priority | Residual finding | Required next change |
| --- | --- | --- |
| High | Planner/context/patch architectural concentration and shadowing risk | Split candidate generation by domain, evaluate all admissible candidates in one typed comparator, record every rejection, and add mutation/reachability tests |
| High | Informal certificates can share correlated model errors | Require heterogeneous double review or a human/formal checkpoint for designated high-impact claims |
| High | No protocol-valid general performance or novelty evidence | Run preregistered, matched, repeated trials with immutable prompts, independent graders, complete snapshots, and confidence intervals |
| High | Audit history is not externally tamper-evident | Sign periodic state/journal roots and publish or store them outside the mutable proof database |
| Medium | Research context has no object-level retrieval handshake | Add an explicit `request_context_entity` protocol that can cold-start with a complete dependency packet |
| Medium | Outcome heuristic is observational and selection-biased | Add randomized exploration strata or matched propensity-aware evaluation; keep production priorities ordinal |
| Medium | Formal and non-Python backend coverage is untested locally | Add CI images with pinned Lean/Coq/Agda and Julia/Macaulay2 versions plus successful and adversarial fixtures |
| Medium | Process isolation depends on external CLI/runtime semantics | Version-gate Codex/Claude policies and run executable boundary smoke tests in CI; fail closed on unknown versions |
| Medium | Unbounded database/artifact growth | Add signed compaction checkpoints, retention classes, and restoration tests without deleting proof provenance |
| Medium | Polymorphic relations and legacy JSON fields limit SQL constraints | Migrate toward typed relation tables while retaining a read-only compatibility view |
| Medium | Patch annotations and authority records are not independently hash-bound | Add a canonical journal-entry hash covering authority, operation, rationale, delta, and the previous entry hash |
| Medium | Pre-v3 histories cannot be replay-certified under v3 semantics | Preserve them as explicitly legacy provenance and establish a signed v3 migration checkpoint rather than fabricating old deltas |
| Medium | Operator configuration/events are recorded but not hash-bound with mathematical state | Add a separate append-only, signed configuration/event chain and bind its head into every session identity |
| Low | Broad exception catches and stale `TODO` labels obscure whether optional failures are intentional | Replace silent catches with typed exceptions/events and convert completed planning notes into ordinary design comments |
| Low | Legacy internal names (`debts`, `villain`, `negative_result_ledger`) remain in persisted schemas and metadata | Complete a versioned data migration once downstream consumers can read canonical names; do not silently reinterpret old records |

## Verification record

The final regression command is:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s agents/generation/tests -p 'test_phase2*.py' -q
```

The focused adversarial command is:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  agents.generation.tests.test_phase2_soundness_remediation -v
```

Additional checks are `python3 -m compileall -q agents/generation/phase2`,
`python3 -m agents.generation.phase2.experiment_audit`, `git diff --check`, and
an actual `codex sandbox` command that confirmed the child profile could read
its selected working directory but not the repository-level README outside it.

Final execution on 2026-09-01: **860 tests passed in 56.324 seconds** with
`ResourceWarning` promoted to an error. The focused soundness-remediation
module contains 21 adversarial tests. Compilation, JSON-schema parsing,
experiment-archive auditing, and `git diff --check` also passed. This is a dated
verification record, not a promise that future revisions retain the same test
count.

## Conclusion

The original kernel-level soundness and provenance failures are substantially
remediated, and the system now fails closed in the most important trust
transitions. Two original goals remain incomplete: architectural decomposition
of the planner/context/patch monoliths, and empirical validation of novelty and
general performance. The next release should prioritize those rather than add
more scheduling heuristics.
