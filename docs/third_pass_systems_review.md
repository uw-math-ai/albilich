# Albilich third-pass systems review

Date: 2026-09-01

This report reviews the implementation after the original remediation and a
second adversarial repair pass. It evaluates harness design, context
management, long-horizon reasoning, idea generation, and mathematical ability.
The finding-to-control blueprint is in
[`soundness_remediation_blueprint.md`](soundness_remediation_blueprint.md).

## Executive assessment

Albilich is now a substantially more defensible **orchestrator for
model-assisted mathematical research**. Its strongest properties are
host-controlled authority, transactional proof-state mutation, content-bound
certificates, explicit proof obligations, bounded verifier packets, replayable
row changes, process-level isolation for supported host tools, and honest
distinctions among informal review, reproduced computation, and formal
checking.

It is still not a sound or complete automated theorem prover. Informal
verification is fallible model judgment; the planner remains a very large
sequential policy program; provider-side resumed context is unobservable; the
novelty machinery measures structured diversity rather than originality; and
there is no protocol-valid held-out evaluation establishing general
mathematical performance. No successful formal proof was checked in the review
environment because Lean, Rocq, Agda, and an independent Lean kernel were not
installed.

No finite code review or test suite can establish that every weakness has been
found. The strongest justified conclusion is narrower: the concrete failures
listed below are repaired and covered by regression tests, while the residual
risks are published rather than converted into unsupported claims.

## Scope and method

The review inspected the execution boundary, backend contracts, scheduler and
workflow, proof-state transactions, patch and event journals, external audit
checkpoints, context construction and resume deltas, certificate semantics,
heterogeneous assurance, computation and formal adapters, reference ingestion,
LaTeX/PDF publication, monitor serving, novelty policy, experiment archives,
CI, public terminology, and tests.

Testing used three evidence classes:

1. **Live local checks** actually executed installed programs such as Codex,
   Python, bubblewrap, `prlimit`, OpenSSL, and pdfLaTeX.
2. **Simulated adapter tests** used controlled fake executables and fixtures to
   test rejection, parsing, binding, and failure behavior. These do not prove a
   real theorem prover works.
3. **Unavailable checks** were reported as unavailable. They were not counted
   as successes.

## Defects found and repaired in this pass

| Finding | Repair and enforcement point | Regression evidence |
| --- | --- | --- |
| Concurrent configuration events could race and lose or fork the event-chain head | Event writes now acquire the SQLite write lock before deriving the next chained entry | concurrent writer and event-journal tests |
| Audit checkpoint creation could combine state and journal heads from different database moments | State hash, patch head, event head, and policy head are read in one transaction snapshot | checkpoint interleaving tests |
| Database-local hashes did not resist an administrator rewriting the whole database coherently | Optional Ed25519 OpenSSL checkpoints sign the complete audit-head statement outside the database; private-key permission checks fail closed | signing, tampering, rollback, and key-permission tests |
| Patch annotations and configuration events were outside authenticated history | Patch-entry annotations and event entries now have independent chained hashes; verification covers both chains | annotation/event mutation and deletion tests |
| A Rocq adapter could accept a successful process without proving that the configured target was checked | The host binds the exact declaration/target and rejects spoofed or missing target evidence | formal-adapter adversarial tests |
| CAS reproduction treated one matching run too generously and did not require stable stderr or universal successful exit | Reproduction runs twice, requires stable stdout and stderr, successful untruncated exits, expected output, and an unchanged attested executable | CAS repeat, mismatch, stderr, timeout, and executable-swap tests |
| Backend capability probes were less isolated than proof sessions | Probes use attested executables, bounded output/time, a cleared environment, and the process sandbox | backend-contract tests and a live Codex probe |
| Older novelty records could satisfy a newer declaration by silent downgrade | Novelty contract v3 is explicit; missing v3 evidence is incomplete rather than interpreted as success | version-downgrade and incomplete-portfolio tests |
| High-assurance scheduling could repeatedly select an unavailable reviewer family | The workflow stops in `awaiting_human` with an explicit backend-selection/configuration request instead of consuming steps forever | heterogeneous-backend loop regression |
| Context state and completion-policy/audit heads could come from separate snapshots | Ordinary and resume manifests read the relevant state and all audit heads through the same caller-owned transaction | exact policy/state interleaving regression |
| A policy or proof mutation could occur after planning but before dispatch | Workflow planning is optimistically bracketed by audit heads, retries on change, records planning heads, and discards stale primary or companion plans before launch | planning/dispatch race regression |
| Two reviewer families could split a claim and its inferences and collectively appear to provide complete heterogeneous review | Each qualifying independence class must cover the exact designated claim and every inference on the selected proof approach; partial classes do not combine | split-coverage adversarial regression |
| Integrating a claim invalidated otherwise-current validation evidence because validation and lifecycle were flattened into one status | Certificate currency now treats validation and lifecycle as separate coordinates; approach integration remains a distinct certificate | complete review-to-integration lifecycle regression |
| PDF reference extraction was unrestricted, unbounded, and mislabeled an extracted-text hash as the source-file hash | Inputs and outputs are capped; source bytes are hashed before and after; `pdftotext` must run under an attested, networkless, resource-limited sandbox; source and extracted-text digests are distinct | oversized, mutation, metadata, and failure-path tests |
| LaTeX compilation ran an unrestricted host process and publication sidecars could be served without content integrity | pdfLaTeX runs without shell escape in a bounded bubblewrap namespace; compiler and source are attested; new PDFs record digest and size; HMT and monitor paths verify those values | live valid compile, unmounted-secret attack, oversized source, and tampered-PDF tests |
| A large claim collection could consume the entire omitted-entity catalog and hide every other entity type | Catalog v2 interleaves entity types, exposes exact per-type coverage, pages deterministically, and rotates pages by proof revision | type-starvation and revision-pagination regression |
| The dashboard accepted steering mutations without a per-instance anti-forgery secret and could read an arbitrarily large paper into memory | Every steering POST requires a random token embedded only in the served page and is capped at 64 KiB; served PDFs and HMT catalog sizes are checked against a 64 MiB ceiling and recorded sizes | missing-token, oversized-request, valid-token, PDF-integrity, and HMT-tamper tests |
| Public/model-facing text still relied on metaphors such as debts, ledgers, batteries, villains, and dossiers | Public patch/context/prompt vocabulary now uses proof obligation, catalog or record, test suite, adversarial reviewer, and proof draft. Exact legacy identifiers and quoted evidence remain unchanged | public-vocabulary and patch-contract tests |

The pass also modernized tests that had directly forged revision counters, made
pause/stop control entries distinct from failed executions, and aligned a
concurrency fixture with the newly authenticated rejection event. These were
test-harness defects exposed by stricter production invariants, not evidence
that the invariants should be weakened.

## Review by system dimension

### Harness design

The child model is now consistently treated as an untrusted proposer.
`PatchAuthority` binds its host-selected role, action, target, proof approach,
context revision/hash, model profile, and tool policy. Child-controlled
telemetry, artifact revisions, verification bindings, PDF metadata, and CAS or
formal outcomes are rejected. Accepted mathematical changes are transactional
and checked against graph, scope, certificate, and revision invariants.

The audit model is also materially better. Mathematical row deltas, patch
annotations, and configuration events have separate hash chains. A signed
checkpoint can bind the current state and all heads outside SQLite. Replay
detects ordinary deletion, reordering, mutation, and unjournaled state changes.

The principal harness weakness is architectural size. At this review,
`scheduler.py` has 11,721 lines, `context_builder.py` 7,032,
`patches.py` 5,583, and `workflow.py` 2,771. Much of scheduling is still an
ordered series of branches rather than generation of one complete admissible
candidate set followed by a single comparison. This makes policy shadowing,
starvation, and unreachable branches hard to rule out. Tests cover known paths
but provide no global fairness, convergence, or reachability proof.

Additional harness limits remain:

- Replay applies authenticated before/after row deltas; it is not historical
  re-execution through the exact original kernel and toolchain.
- A signed local checkpoint is not a public transparency log or write-once
  store. An administrator controlling the database, checkpoint destination,
  and signing key can still manufacture a coherent alternate history.
- OpenSSL and the host operating system remain trusted. The signing operation
  is not itself performed in the same sandbox/attestation regime as CAS and
  publication tools.
- The workflow brackets planning, but direct callers of `next_action` do not
  automatically receive that cross-snapshot stability guarantee.
- The custom executor hook is a trusted host extension. Passing untrusted code
  through that hook can invalidate process-boundary assumptions.
- Scope import spans database and filesystem work and therefore cannot be one
  atomic transaction across a process crash; cleanup is best effort.

### Context management

Strict and integration verification packets contain the complete selected
proof dependency closure. Mandatory statements, hypotheses, inference text,
proof artifacts, and blocking proof obligations are indivisible; an oversized
packet raises `context_too_large` rather than silently deleting mathematics.
Ordinary research packets are explicitly lossy and carry population hashes,
included/omitted counts, and a bounded identifier catalog. An agent can request
an exact disclosed object and receive a cold, exact local-dependency packet.

State rows and policy/audit heads now come from one database snapshot. Resume
identity includes the action and tool-policy dimensions, and row-exact deltas
are hash-bound. Ordinary packet construction no longer loads the complete patch
and event histories into memory.

Residual context weaknesses are:

- The entity catalog is bounded. Type-fair revision rotation reduces permanent
  starvation, but an identifier absent from the current page cannot be guessed
  safely, and catalog membership changes can perturb future pages. There is no
  explicit operator/agent command to request page *n*.
- Manifest fitting can shorten even the selected catalog page; metadata marks
  that fact, but discoverability is correspondingly weaker.
- SQLite rows are snapshot-consistent, while filesystem sidecars such as
  steering and parallel-exchange files are read outside the same transaction.
- A provider's hidden resumed context cannot be inspected. A correct local
  delta proves what was sent, not what the provider retained or attended to.
- The database, run table, artifact collection, and audit history still grow
  without a complete retention/compaction protocol. Session cold storage is
  bounded, but whole-project growth is not.
- Completeness is syntactic. A model can overlook an included hypothesis or
  proof step, especially in a large packet.

### Long-horizon reasoning

The system has genuine long-horizon machinery: persistent claims and
inferences, explicit proof obligations, branch summaries, exact negative
results, strategy changes after repeated no-delta work, resume identities,
operator steering, budget reserve, certificate invalidation, and a scheduler
that prioritizes verification and integration once a proof approach is ready.
Progress credit is based on accepted causally linked state changes rather than
the model's self-description.

Nevertheless, persistence is not the same as successful reasoning. The planner
does not have a formal liveness argument: it can spend indefinitely on locally
admissible maintenance or repair actions, and its fixed branch order can
starve a later but globally better action. Bounded decomposition depth and
stagnation switches control some loops, not every loop. Alternate reviewer
selection now pauses honestly when unavailable but does not automatically
provision or select a valid backend.

The outcome heuristic is local and observational. It is not a calibrated
probability of success and can inherit selection bias, sparse data, and
confounding from which actions the scheduler chose to run. Long-term provider
sessions also remain subject to opaque context loss. Consequently the system
can preserve a rigorous account of a stalled research program without itself
finding the missing idea.

### Ability to generate novel ideas

Novelty v3 enforces a useful engineering contract: multiple declared
approaches, semantic signatures, structural method tags, separation between
generation and selection, comparison with prior failures, and explicit
falsification criteria. Parallel branches must differ in strategy family and
ownership. These controls reduce superficial paraphrase and repeated failed
work.

They do not establish originality. Semantic signatures and lexical/structural
features have false positives and false negatives; several declaration fields
still originate with the proposer; and the built-in method collection biases
search toward anticipated mathematical patterns. There is no independent
expert study or held-out corpus measuring rediscovery, usefulness, or genuine
novel contribution. A diverse portfolio can consist entirely of six wrong or
well-known ideas.

Claims about improved creativity, novelty rate, or superiority to a simpler
agent are therefore unsupported. The archived experiments are correctly
classified as `historical_unvalidated` and provide provenance case studies,
not causal or general performance evidence.

### Mathematical ability

Albilich's kernel can enforce consistency properties around mathematics: exact
statement identity, acyclic dependencies, grounded derivations, current
evidence bindings, explicit obligation closure, root-statement alignment, and
separation of validation from integration. It can also reproduce bounded
deterministic computations and invoke supported formal checkers under a narrow
contract.

The kernel cannot decide whether an informal proof is true. One or two language
model reviewers can accept the same subtle false argument, and different
provider/model labels do not establish epistemic independence: families may
share training data, proof patterns, and systematic blind spots. Heterogeneous
assurance now proves only that complete reviews came from distinct recorded
independence classes.

Further mathematical limits are important:

- A reproduced CAS output proves that a captured program deterministically
  produced bytes, not that the program encodes the theorem or that the
  deduction from output is valid. Only Python was exercised live here; Julia,
  Macaulay2, Sage, GAP, and Singular were unavailable, and no independent CAS
  cross-check ran.
- No formal checker succeeded live in this environment. Lean, an independent
  Lean checker, Rocq, and Agda tests are adapter simulations and fail-closed
  absence tests. They are not formal-validation evidence for a theorem.
- Translating an informal statement into a formal target is itself a
  mathematical step. Exact target binding prevents process spoofing but does
  not prove the formal encoding means the original theorem.
- Rocq and Agda lack an independently implemented second kernel in this
  harness. Some assumption/postulate checks are necessarily syntactic.
- Formal and CAS executables are hashed, but their complete runtime closure and
  every library/package byte are not content-addressed. Read-only system mounts
  and the host kernel remain trusted; there is no seccomp policy.

## Residual findings by priority

No currently observed issue permits an ordinary child patch to bypass the
implemented authority and certificate gates. That statement is bounded by the
host trust model and is not a proof that no critical defect exists.

### High priority

1. **Planner monolith and incomplete global comparison.** Decompose the
   scheduler into independent candidate generators, explicit admissibility
   predicates, and one total comparison/trace stage. Add mutation tests,
   starvation scenarios, and bounded-liveness properties.
2. **Fallible and correlated informal verification.** Treat informal review as
   review, never proof. For high-consequence results, require a formal proof or
   independent expert review outside the model families.
3. **No protocol-valid ability evaluation.** Run predeclared held-out problems,
   immutable prompts, repeated matched controls, independent mathematical
   grading, and complete public artifacts before making performance or novelty
   claims.
4. **No live formal success in the tested environment.** Add a pinned CI matrix
   with real Lean/Rocq/Agda examples and an independent kernel where available;
   preserve fail-closed behavior when any component is missing.
5. **Model-backend resource exhaustion is not hard-contained.** Codex and
   Claude sessions have deadlines and pre-launch storage admission, but no
   cgroup/RLIMIT envelope enforcing aggregate memory, CPU, process, or output
   bytes during a run. Logs and Claude stream files can grow until the next
   storage check, and peak memory is observed rather than enforced. Run model
   backends in a separately quota-controlled service or cgroup and reject a
   session as soon as a per-run byte/resource limit is reached.

### Medium priority

1. Row-delta replay is not semantic historical re-execution.
2. Signed checkpoints lack external timestamping, public witnessing, and
   write-once custody separation.
3. Runtime dependencies are not comprehensively content-addressed; executable
   execute-and-restore races and broad read-only system mounts remain in the
   host threat model.
4. Backend version windows and CLI capability probes require maintenance and
   do not prove behavioral compatibility. Claude was not available live.
5. CAS reproduction lacks semantic correspondence and independent-engine
   cross-checking; Julia, Macaulay2, Sage, GAP, and Singular were not available
   live.
6. Provider resume state remains opaque.
7. Whole-project database, artifact, run, and journal growth is unbounded.
8. Catalog pagination has no explicit page-request protocol.
9. Steering and parallel-exchange sidecars are not part of the same SQLite
   snapshot or independently signed chain.
10. Legacy PDFs without stored digests remain readable for compatibility. New
    publications are hashed, but the compatibility path is weaker.
11. A successful `pdftotext` sandbox run was not available locally because the
    executable was absent.
12. Cross-database scope import and copied files cannot commit atomically as one
    unit.
13. Planning stability is enforced by the workflow wrapper, not the scheduler
    API itself.
14. The dashboard is safe by default on loopback and steering POSTs are now
    anti-forgery-token protected. If an operator deliberately binds it to a
    non-loopback interface, however, read endpoints have no user authentication
    and the page itself supplies the steering token. It must not be exposed
    directly to an untrusted network; use an authenticated tunnel/proxy or add
    first-class authentication.
15. Several trusted/operator and generated-artifact paths still use whole-file
    reads. Admission caps bound many individual artifacts, but transactions
    that snapshot several large files can create high transient memory use.

### Low priority

1. Legacy internal names such as `debts`, `villain`, and `proof_dossier` remain
   in schema fields, compatibility aliases, identifiers, and implementation
   variables. Public/model-facing language is normalized, and quoted evidence
   is deliberately not rewritten. A future schema migration should remove the
   aliases only with explicit compatibility tooling.
2. Novelty signatures remain heuristic and cannot certify originality.
3. Pre-v3 history cannot gain evidence that was never recorded; migration
   correctly establishes a new baseline instead.
4. Some optional telemetry and sidecar boundaries deliberately catch broad
   exceptions and degrade. Core proof-state and certification paths fail
   closed, but these catches can hide observability defects.
5. The CI workflow runs Python unit/adversarial tests and a live Codex contract,
   but not Claude, live formal provers, multiple Python versions/operating
   systems, successful PDF extraction, or a Julia/Macaulay2 matrix.

## Verification record

| Check | Result | Evidence class and limitation |
| --- | --- | --- |
| Entire `agents/generation/tests` discovery | 1,107 tests passed | Real local code/tests; fixtures still cannot model every deployment race |
| Phase 2 discovery | 914 tests passed | Real local unit, migration, replay, workflow, and adversarial tests |
| Soundness-remediation module | 61 tests passed | Real local targeted regressions |
| Python compilation and JSON schema parse | Passed | Syntax/serialization only |
| Experiment archive auditor | Passed | Confirms hashes and honest `historical_unvalidated` labels; not performance evidence |
| Git whitespace validation | Passed | Formatting only |
| Codex backend contract | Passed live with CLI 0.152.0; executable SHA-256 `f541420d35d3ad757fe71c0a34a3de0ec80fd513e10e5c52596b39d8be6e445c` | Real installed binary and capability probe; not a paid mathematical proof run |
| Python CAS reproduction of `6*7` | Reproduced twice with stable stdout/stderr and unchanged executable | Real sandboxed Python; trivial computation and no theorem-level authority |
| pdfLaTeX publication | Valid paper compiled; attempted read of an unmounted secret failed | Real sandbox boundary on this host; TeX runtime closure is not fully content-addressed |
| Signed audit checkpoints | Creation, verification, tamper, rollback, and key-permission paths passed | Real OpenSSL-backed tests; no public timestamp or independent custodian |
| Lean/Rocq/Agda/formal-kernel success | Unavailable | Adapter behavior is simulated/fail-closed only |
| Claude, Julia, Macaulay2, Sage, GAP, Singular, and `pdftotext` live success | Unavailable | Not counted as passing integration coverage |

The CI definition in `.github/workflows/phase2-tests.yml` compiles Phase 2,
attests the pinned Codex CLI, runs the Phase 2 tests, audits experiment labels,
and validates the patch schema. It does not yet cover the unavailable live
matrix above.

## Claims the implementation may and may not make

It may say:

- a patch was accepted under a recorded host authority;
- a proof graph and its recorded certificates satisfy the implemented
  invariants at a particular revision;
- an informal proof received complete reviews from the recorded reviewer
  classes;
- a captured computation was reproduced under the recorded sandbox contract;
- a supported formal target was checked, but only when the real checker result
  and target binding exist;
- an experiment archive has the declared files and hashes.

It may not infer from those facts that:

- an informally reviewed theorem is formally proved;
- two model-family reviews are independent in the statistical or epistemic
  sense;
- deterministic computation proves the mathematical interpretation of its
  program;
- portfolio diversity establishes originality;
- the historical archives establish a success rate, causal gain, or general
  mathematical superiority;
- passing this suite means every design or implementation flaw has been found.

## Conclusion

The third pass closes several serious race, assurance, sandbox, publication,
and context-discovery defects. The remaining risks are now concentrated less
in ordinary child-authority bypass and more in the limits of informal
mathematical judgment, a monolithic planner, incomplete empirical evaluation,
host/toolchain trust, provider opacity, and long-term operational scale. Those
are substantive limitations. They should govern deployment claims and the next
engineering milestone rather than being hidden behind a green test suite.
