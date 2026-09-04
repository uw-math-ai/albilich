# Albilich fourth-pass fix-and-audit report

Date: 2026-09-01

This report records another adversarial fix--test--review cycle over Albilich's
harness design, context management, long-horizon behavior, idea generation,
and mathematical assurance. It supersedes the implementation assessment in
[`third_pass_systems_review.md`](third_pass_systems_review.md), while that
document remains useful as a historical record.

## Executive assessment

This pass found and repaired additional defects after the previous test suite
was green. The most consequential were an event/configuration integrity gap, a
missing seal over run-selection provenance, a production-only catalog paging
bug, race-prone artifact copying during certified-scope import, and an external
checkpoint output that could follow a pre-existing symbolic link. It also
bounded patch structure, strengthened process accounting and output handling,
made snapshots and reference ingestion single-snapshot operations, and made
integrity checks return explicit failures for malformed database values.

The repaired system is a stronger **orchestrator for model-assisted
mathematical research**. It is not a sound or complete theorem prover. A green
test suite establishes the tested engineering contracts, not the truth of an
informal proof, the originality of an idea, scheduler liveness, or general
mathematical ability. No finite review can justify the claim that every defect
has been found.

## Scheduler follow-up, 2026-09-02

A focused scheduler redesign followed this review. Research-strategy policies
now materialize every simultaneously admissible top-level operation, selection
is independent of generator traversal order, a front-door comparator covers
actionable context and explicit external work, and a twelve-stratum open-proof
comparator covers integration, verification, recovery, mathematical-text
cadence, proof-obligation routing, and residual work. The verification stratum
now has a complete scoped candidate set: every verifier-ready route,
proof-evidence handoff, support-theorem precheck, verifier loop, threatened
dependency, pending counterexample, status reconciliation, and unrouted proof
claim is represented. Competing routes for one claim remain distinct.
The evidence-assimilation stratum now likewise emits every eligible
exact-citation obligation, checked source handoff, proof artifact awaiting
conversion, root-target citation card, and root-target definition-audit card. Candidate identity,
cooldown, durable completion, and bounded deferral are scoped to the exact
proof obligation, artifact, or card, so processing one object does not consume
its unselected peers.
Selection uses lexicographic policy tiers before applying
the three-rejection deferral bound within the maximal tier, so overdue
exploration cannot displace verification. Candidate inputs, nested traces, the
selected action, and every disposition are hash-bound and revalidated when run
telemetry is accepted and when database invariants are checked. Policy v7
commits candidate-keyed nested traces for selected and unselected strata.
Nested deferral accounting follows comparison ancestry, so a local winner still
counts as deferred when the outer comparator rejects its branch.

The later closure pass completed the remaining object-valued strata. Recovery
now enumerates every eligible bottleneck proof obligation; obligation routing
enumerates every request, obstruction, mathematical obligation, route repair,
and failed/blocked decomposition; residual work enumerates all ready steps
across every active plan and every eligible route/claim; and sequential
integration compares every eligible verified route with exact snapshot-bound
assurance. It also fixed a redundant-reintegration bug for already integrated
claims and removed quadratic obligation/artifact rescans from integration.

Parallel companion planning now uses one scheduler projection and a final
deterministic admission pass after multi-branch filling. The admission relation
prevents duplicate route ownership, same-claim certification races, and
verification/integration overlap; it imposes proof-search, role, and total wave
capacities plus an aggregate token grant and records materialized accept/reject
reasons. Strict informal verification can consume, and is charged against, the
protected verification allocation despite retaining `mode=prove`. Each
admitted companion carries a hash-bound decision trace embedding the wave
record, so its normal run telemetry preserves selection provenance. Specialized
generators now return every verifier, support-precheck, citation,
decomposition, and integration candidate before admission, and the wave trace
is complete within that registered scope. Stable candidate identifiers bind
exact object fields and do not depend on traversal position or token grants.
The workflow now performs one final admission over the complete materialized
wave using persisted budget state. Current parallel policy v9 retains the v4
canonical-JSON identity prefix, v6 sibling-conflict fairness, an explicit class
priority, bounded capacity aging across classes, minimum-useful token
enforcement, and one live/replay transition. It also retains v7 full-payload
identity and the v8 serializable-primary distinction. It ages a candidate queued behind an
admitted conflicting sibling and now distinguishes a serializable fixed-primary
ownership conflict from a permanent structural exclusion. Replay-validated
outcome codes, rather than English reason matching, drive current fairness.
The admission transition emits those codes directly rather than deriving them
from prose. V9 searches bounded feasible subsets globally with a deterministic
64-state beam, max-weight service for overdue candidates, and fixed host
admission weights. It evaluates v8 as an executable lower bound, so pruning can
improve but cannot regress under the declared objective. The committed search
record includes its expansion bound, pruning and optimality status, both
objective values, and the fact that no model self-score was used. A complete stable-action-payload digest now extends semantic
identity, so an unregistered field such as an exact query cannot collide with a
different task. Because old counters cannot identify which newly distinguished
task they described, the v7 identity epoch resets rather than guesses their
assignment.
After three stable v8 serialization rejections, a registered same-tier leader
comparison can promote the overdue candidate only when the scheduled primary is
nonmandatory. The workflow then regenerates every companion family under the
new leader from the same snapshot; it never reuses the old leader's conditional
companion set. Subsequent rotations use authenticated generic candidate state,
so changing leaders does not erase the other members of a stable cohort.
Its wave ID
commits the candidate set and declared scope, authenticated snapshot, worker
configuration, initial allocation, and generator-evaluation manifest; generic primary and companion traces
bind the exact admitted input row. Valid policy-v3 wave records remain
replayable, as do v4/v5 records, with fairness continuity only for unambiguous
legacy aliases.
Store migration v10 now persists compact authenticated counters for both the
generic comparison tree and parallel admission. Generic state advances only on
the primary decision, parallel state advances once per wave, and companion
completion order cannot duplicate or erase either update. Nested candidate
identifiers are globally unique, and hard policy exclusions no longer accrue
fairness counts that can never affect their stratum.
Store migration v11 separates scheduler dispatch from run telemetry. The whole
admitted wave is committed in one system patch before any executor is entered;
both fairness projections cite that dispatch, and later run telemetry carries a
unique foreign-key link without applying the transition again. Dispatch rows
metadata are covered by row-exact patch replay and the run-provenance seal.
The larger recovery body is committed by its action digest and hash-chained
record operation, then rechecked on recovery and during explicit full audit.
Store migration v12 adds the canonical action body and execution-recovery
contract needed to resume an unlinked dispatch. An execute-mode workflow holds
one non-inheritable process lock per proof store; the kernel refuses a new wave
while any earlier group is unresolved. On restart, the workflow validates the
stored action against its decision digest and resumes only the unresolved
members. The built-in supervised backend must have the same recorded model,
sandbox, search, timeout, and context configuration. A custom backend must
additionally declare dispatch-key idempotency and the same stable executor
identity; otherwise recovery stops for operator action. Historical v11 rows,
whose action bodies do not exist, fail closed rather than guessing.
Store migration v13 adds append-only attempt claims and one durable returned
result per dispatch. Hash-chained non-policy events bind each transition;
compact record metadata is included in the run-provenance seal, and recovery
and full audit recompute the bounded result digest. Dispatch-derived patch IDs
make result application idempotent: a restart consumes an already returned
result without calling the executor, and recognizes an exact proof patch that
was accepted before run telemetry could be written. The built-in contract now
also binds the resolved executable path and SHA-256 when resolution succeeds.
The result callback commits its receipt before waiting at the live proof-merge
barrier, so a completed companion is not held only in process memory. Recovery
applies the same proof-critical ordering as the live barrier and cannot replay a
lower-priority receipt ahead of an unreturned verifier.
Store migration v14 preserves the committed wave cardinality when only a subset
remains unresolved, permits a validated returned proof patch across only the
automatic crash-stop/restart policy sequence, and still rejects any operator or
scheduler-policy change. Path-based result artifacts commit the staged file's
SHA-256 and size and enforce them during both binary copying and writer-text
ingestion. Result recording reserves the run ID transactionally; collisions are
mapped to dispatch-derived host IDs while retaining the executor ID for
diagnostics, and the central run writer enforces the reservation across tables.
Store startup requires the exact contiguous migration history through v20 and
fully validates v13 before backfilling reservations.
Migration v15 then places runs, dispatches, executor claims, and returned
results in one authenticated append-only provenance chain. Online checks use
its tail and exact database-guard definitions; explicit audit still
recomputes every source-row commitment. Mathematical proof-state hashing no
longer serializes this accumulated control history. Before a v14 upgrade
establishes a projection baseline, it verifies both legacy current-state seals,
revision coverage, delta shape, and every patch-chain entry. Because v14
allowed scheduler rows in its proof digest to change between patches, this is
not mislabeled as row-semantic replay. A nonempty upgrade records an immutable
projection baseline plus a SHA-256-bound full database backup instead of
rewriting earlier patch hashes. Event rows are immutable
after their one-time hash finalization, allowing steering to use the current
event-tail seal and an indexed steering-only query while reserving complete
event replay for explicit audit.
Migrations v16--v20 validate and freeze the patch journal, add trigger-generated
source sequences for scheduler and event rows, and maintain seal-bound
sufficient statistics for total runs, outcome runs, all retrieval calls, the
registered policy-relevant retrieval intents, and session-authored patches.
Consequently the online boundary uses indexed tails and compact current
statistics rather than counts or replay over accumulated control history.
Complete patch, scheduler, and event audits remain linear by design. The
bounded per-intent view discloses its registry and exact untracked total.

Invariant checks, the scheduling projection, and authenticated steering now
come from one SQLite read transaction. Proof-revision and policy-head checks
replan after a legacy synchronization write or concurrent update rather than
dispatching a mixed-snapshot action. Online run history is bounded and its omitted population
is disclosed. Snapshot-local graph views are reused with copy-on-read, and one
reverse-edge traversal computes all root distances. Generic decision rows now
store only selection inputs, an exact action hash, and a validated disposition;
this reduced the 6,144-candidate obligation trace from 4.40 MiB to 2.85 MiB.
Candidate-generator declarations are now content-addressed, and compact
assignment runs bind every materialized row to its source family; a
representative nested trace fell from 11,638 to 6,773 bytes after replacing the
first naïve per-row encoding. The latest hard-gate run measured 5.78 ms p95 for
ordinary planning, 6.21 ms for parallel-wave planning, 0.0075 ms for compact
64-candidate fairness lookup, and 0.909 ms for the legacy
64-candidate/96-run history path. Over 1,000
complete durable lifecycles, decision/dispatch/attempt/result/completion p95
were 13.75/11.45/4.79/4.75/10.27 ms; the final 50-sample tail measured
13.76/11.49/4.81/4.78/10.28 ms. Invariant-valid wide/deep 2,000-item states
measured 225.56 and 275.27 ms p95.
Dense verification, evidence, and obligation fixtures emitted 4,000, 2,000,
and 6,144 complete candidates in 175.21, 53.12, and 187.89 ms p95; validation
measured 28.36, 11.73, and 39.44 ms p95; bounded-history compatibility replay
measured 203.48, 68.15, and 214.08 ms p95. The heterogeneous
2,000-candidate parallel subset search measured 194.48 ms p95.
This is engineering evidence, not proof-success evidence.

The original incomplete-enumeration finding is closed for 97 registered
families across the outer, open-theorem, child-stratum, and parallel-admission
boundaries. All registered stable same-tier cohorts have a bounded-service
property; this is not a global optimality or liveness theorem.
`_plan_next_action` is down to 69 lines and the open-theorem and solved-root
policy layers are explicit comparisons. The registry
does not prove that every policy that ought to exist has been registered, the
generic three-deferral guarantee is conditional on maximal-tier admissibility,
and admission still uses static rather than empirically calibrated workload values. See
[`scheduler_redesign.md`](scheduler_redesign.md) for the exact boundary and
remaining work.

## Method and evidence classes

The review combined source inspection, adversarial fixtures, migration and
journal replay tests, concurrency tests, filesystem-race tests, resource-limit
tests, static searches for unbounded input and unjournaled mutation, Python
compilation, Git whitespace validation, and full test discovery.

Evidence is classified as follows:

1. **Live local evidence** means the installed program or operating-system
   boundary actually ran on this host.
2. **Simulated adapter evidence** means a controlled fake executable or fixture
   exercised parsing and fail-closed behavior. It is not evidence that a real
   prover or computer-algebra system succeeded.
3. **Unavailable** means the backend was absent and no success is claimed.

## Defects found and repaired in this cycle

| Defect | Repair | Adversarial check |
| --- | --- | --- |
| Run assignment and scheduler decision traces were excluded from the legacy replay projection and could be rewritten without invalidating the current seal | Store migration v9 adds a companion SHA-256 seal over selection design, assignment probability, exploration stratum, candidate-set hash, policy version, and decision trace; every accepted patch updates it atomically | direct run-provenance rewrite is rejected by `current_state_seal` |
| New external checkpoints did not explicitly sign the companion run-provenance seal | newly created Ed25519 checkpoint payloads include `run_provenance_hash`; verification validates the field and compares it directly when checking the same revision, while retaining compatibility with older version-2 checkpoints | live checkpoint creation asserts the signed digest and append-prefix verification remains valid |
| Full patch replay had no patch endpoint or migration baseline to compare against at native revision zero | replay now always compares the live projection, run provenance, and journal head with the recorded current seals, including genesis | direct revision-zero row mutation makes full replay invalid |
| The current proof-state seal did not bind the event tail or live scheduling configuration | `current_event_seal` checks row count, tail hash and predecessor, latest policy head, and the completion, parallelism, and run-control projections; `current_state_seal` incorporates the result | payload mutation, tail deletion, configuration mismatch, and malformed payload tests |
| A correctly hashed but schema-empty policy event could be mistaken for the absence of an event when live state had its default value | append-time and seal-time schemas now require a valid completion target, a consistent parallel worker/mode pair, or a valid run-control target linked to its exact telemetry event | self-consistent empty-payload and missing-companion-link tests |
| Malformed numeric values in SQLite or policy JSON could make an integrity check throw instead of returning an invalid result | seal-specific integer decoding and guarded journal hashing now turn malformed values into explicit errors | malformed event revision, current proof revision, and parallel-worker payload tests |
| Patch input had no complete structural resource boundary | the kernel rejects more than 512 operations, nesting beyond 40 levels, more than 100,000 JSON nodes, aggregate UTF-8 beyond 16 MiB, a string beyond 8 MiB, non-string keys, non-finite numbers, and oversized integers, before and after alias normalization | excessive-operation and `NaN` patches are rejected without advancing the revision |
| Same-time child runs could receive colliding identifiers | run identifiers now combine a standard UTC timestamp with a UUID suffix | frozen-time identifiers remain distinct |
| Linux descendant-memory accounting inspected only the process leader's child list | `/proc/<pid>/task/*/children` is traversed with bounded enumeration and missing measurements fail closed | a child forked by a nonleader thread contributes to measured resident memory |
| Parallel local sessions each had only an independent memory ceiling, so an admitted wave and the periodic HMT sidecar could exceed any workflow-wide bound; one-decimal result rounding could also report a crossed peak as equal to the limit | one thread-safe governor sums the latest complete process-tree RSS observations for every locally supervised Codex or bundled Claude primary, companion, HMT, repair, and stop-writer child; a crossing permanently trips the workflow governor, cancels every registered session, prevents later launch, records the committed limit and observed aggregate peak to millimebibyte precision, and classifies the cause as `resource_limit` | synchronized cross-session cancellation, real allocated-memory termination for both runners, 30 repeated near-threshold terminations, pre-launch refusal, invalid-limit, contract-tamper, durable-result, recovery, and full-suite regressions |
| Scheduler admission could call a custom backend a parallel wave while `_execute_scheduled_sessions` always invoked custom sessions serially; conversely, the HMT thread could overlap even an undeclared serial executor | concurrency is an explicit execution-contract capability; undeclared custom executors stay serial and defer HMT, parallel declarations must accept cancellation and the shared aggregate governor, and the bundled Claude executor declares and exercises the capability | simultaneous-rendezvous, missing-cancellation/resource-capability rejection, serial-HMT deferral, execution-contract replay, Claude-runner, HMT-plumbing, workflow, and full-suite tests |
| Oversized model-output replacement could follow a final symbolic link and did not preserve a stable head/tail under one descriptor | replacement opens a no-follow regular descriptor, reads stable bounded excerpts, and installs an atomic diagnostic file | linked target remains unchanged |
| Reference-solution ingestion hashed, parsed, and copied through separate reads | one bounded, stable byte read now supplies the source hash and text/PDF extraction path | reader-call count and mutation tests |
| Snapshot creation could mix validation and serialization moments and wrote directly to the final pathname | validation and snapshot extraction share one transaction; JSON rejects non-finite values; output uses an atomic temporary file and rejects a final symbolic link | valid snapshot and protected-link tests |
| Certified-scope import bypassed the proof-state and run-provenance seals when advancing the target revision | both stores are write-locked and seal-checked; the target patch entry, proof-state hash, run-provenance hash, and journal head advance atomically | post-import seal, replay, and concurrency tests |
| Certified-scope artifact import verified one pathname and later copied it, and could accept a destination symbolic link | import uses the patch kernel's stable no-follow descriptor copy and rollback journal; the managed copy is hashed after installation | target-link test preserves the external file; altered source bytes are rejected |
| `artifact_hash(path=missing)` silently fell back to hashing metadata | supplying a path now means a regular no-follow file must open successfully; invariant checks report unsafe files instead of crashing | missing-file and symbolic-link regressions |
| An external signed-checkpoint output symlink was resolved and its target overwritten | checkpoint creation rejects a final output symbolic link and nonregular existing targets | live OpenSSL test proves the protected target is unchanged |
| The omitted-entity catalog claimed revision rotation but read `state["problem"]`; production snapshots use `state["problem_state"]`, so real runs stayed on page zero | catalog v3 reads the production snapshot field and retains deterministic type-fair revision paging | production-shaped state moves from page zero to page one after a revision |
| Reference and monitor text could be consumed after file mutation | authenticated bounded reads now stream the complete digest while retaining only a bounded text prefix | tampered monitor content is suppressed and marked invalid |
| A transient bubblewrap namespace exhaustion was recorded as a mathematical writing failure | LaTeX compilation retries the specific transient condition and distinguishes persistent sandbox unavailability from compilation failure | writing-gate regressions and the full suite |
| Frequent current-tail queries lacked supporting indexes | indexes now cover `(events.event_type, event_id)` and `(patches.status, applied_revision)` | schema creation and all migration tests |
| Parallel semantic identities used delimiter-joined fields and a whitespace-normalizing text fingerprint | policy v4 uses canonical JSON object encoding and exact SHA-256 while accepting v3 traces and carrying v3 fairness aliases forward | a constructed delimiter collision separates under v4; legacy replay and deferral-history regressions pass |
| Parallel live admission and replay had separate implementations inside the scheduler, while generic validation used a lazy import back to that module | identity, ordering, conflict, history, one pure admission transition, replay, and wave binding moved to `parallel_admission.py`; generic selection and validation likewise share `decision_outcomes` | architecture-cycle, transition-spy, disposition-matrix, and replay regressions |
| Parallel aging applied only among equal-priority candidates and all rejection causes accumulated deferrals | policy v4 promotes a stable candidate across admission classes at the bound and ages only capacity/allocation rejections | stable lower-class service, permanent-inadmissibility, interleaved-wave deduplication, and v3-alias tests |
| A parallel wave identifier did not commit the state/configuration inputs that determined admission | v4 commits state revision, proof-state and run-provenance hashes, capacities, aggregate-budget mode, and initial total/reserved budget | independent tampering of every committed input invalidates the trace |
| Malformed decision and admission records could reach hashing, sorting, or set operations with invalid scalar/container types or non-canonical JSON | both validators reject exact types and unhashable/non-finite structures before policy execution; live and replay paths use the same total transition | permanent mutation matrices plus deterministic 30,000-case generic and 50,000-case parallel nested-mutation fuzz campaigns completed without an escaping exception |
| Terminal primaries could appear to admit companions that the workflow never dispatched; a valid wave could be transplanted into an unrelated generic trace | conflict checking is symmetric; nonterminal primaries require budget authorization; production waves require authenticated digests and commit their scope; primary/companion wrappers bind one admitted row and input-action hash; the transformation flag is derived | terminal-primary, unauthorized-primary, wrapper-transplant, snapshot/scope-tamper, and flag-mutation regressions |
| A collision in the v3 delimiter identity could age two distinct v4 candidates through the compatibility alias | legacy history is used only when an alias has exactly one current owner | ambiguous-alias history resets safely while a unique v3 alias retains continuity |
| Generic and parallel fairness depended on the lossy 96-run/16-MiB online history projection, and companion completion could be mistaken for a new generic decision | migration v10 maintains sealed compact state, advances parallel counters once per wave and generic counters once per primary decision, and reconstructs legacy state by insertion order rather than untrusted timestamps after verifying the v9 provenance seal | poisoned prior counts are rejected transactionally; empty-history, companion-interleaving, sealed migration, bounded-service, foreign-key, and direct-tamper checks pass |
| A late or concurrently planned run could be rejected as stale fairness input, discarding valid status and token telemetry; the invariant also guessed whether an unjournaled run was transaction-local from its state revision, which is normally older after the child patch | only the first decision at a scheduler snapshot advances fairness while stale completions remain recorded; `validate_conn` receives the exact transaction-local run IDs instead of inferring them from revision order | same-snapshot generic and parallel completions retain telemetry without rewinding counters, a real workflow asserts accepted metrics after its proof patch, and a committed orphan still fails validation |
| Fairness advanced only after run telemetry, so an orchestrator crash between launch and telemetry could erase a primary decision or whole wave | migration v11 commits an authenticated dispatch group before executor entry, advances fairness from that record, links completion telemetry by a unique foreign key, and replans a stale pre-commit transaction without launching | injected process-boundary crash, completion-link/no-double-transition, stale-dispatch retry, current-seal, tamper, migration, and full reverse/forward journal-replay tests |
| An unlinked dispatch could neither reconstruct its exact action nor distinguish a compatible retry from an unsafe backend change | migration v12 stores the hash-bound action and execution contract, serializes execute-mode orchestrators, forbids overlapping unresolved groups, resumes only unlinked wave members, and requires stable dispatch-key idempotency from custom executors | built-in and custom crash recovery, non-idempotent and identity-mismatch refusal, partial-wave recovery, lock contention, payload tamper, migration-seal, and full-audit regressions |
| A crash after an executor returned could relaunch it, a completed parallel result could remain only in RAM while waiting to merge, recovery could reorder it around an unreturned verifier, and a crash after proof-patch acceptance could reapply the output before telemetry | migration v13 records attempt claims and validated returned results as sealed execution records before the merge barrier, applies the same proof-critical barrier during recovery, assigns dispatch-derived patch IDs, replays a stored result without an executor, and recognizes its exact accepted patch; built-in contracts bind resolved executable bytes and migration history is gap-free | injected crashes at both boundaries, pre-barrier persistence, recovery-ordering, zero-reinvocation, one-copy artifact, result-body tamper, migration downgrade/gap, full-audit, and growing-history latency tests |
| Partial-wave recovery forgot the original parallel cardinality; crash-status policy events invalidated an already validated returned proof; staged artifact paths did not bind file bytes; and duplicate executor run IDs could create permanently un-linkable receipts | migration v14 carries committed group cardinality, recognizes only the exact automatic crash-stop/restart policy sequence, binds path sources by SHA-256 and size, and transactionally reserves result run IDs across the result/run tables with a dispatch-derived collision fallback | partial-wave propagation, successful post-crash proof application, operator-policy refusal, same-size file substitution for binary and writer paths, concurrent duplicate-ID, cross-table ownership, tampered-v13, and real v13-schema backfill tests |
| Every scheduler transition reserialized all prior runs and dispatches; every steering read replayed all unrelated events; patch application serialized its pre-state twice; the first v15 projection baseline could hide an edited interior v14 patch entry; and replay incorrectly compared a valid post-baseline suffix directly with its baseline | migration v15 uses an authenticated append-only execution chain, separates control history from mathematical state, authenticates the complete legacy patch chain before establishing its baseline, makes event history immutable after hash finalization, reads indexed steering events after a tail check, reuses the authenticated pre-state, and replays a nonempty suffix against its latest endpoint before checking the reconstructed baseline | v14 backfill followed by a live post-baseline patch, interior-patch and proof/control tamper rejection, normal mutation guards, privileged-bypass full audit, exact query-plan check, 1,000-lifecycle final-tail gates, and complete regression suites |
| Online seals still counted every historical patch, scheduler row, event, and run-derived population; applied patch rows themselves lacked immutable database guards | migrations v16--v19 first replay and freeze the patch chain, then add ordinal source sequences and seal-bound sufficient statistics maintained by exact triggers | altered same-name guard, direct update/delete/insert, unpaired source/provenance, compact-statistic tamper, migration rejection, full replay, and 1,000-lifecycle final-window regressions |
| Randomized dispatch validation scanned and decoded every prior randomized group for each new action, making a long calibration cohort quadratic | migration v20 adds a partial unique expression index on experiment and assignment unit; online duplicate and fixed-design checks use point lookups while explicit audit retains complete cohort replay | query-plan, duplicate-unit, missing-index, altered-index migration, lifecycle, and full invariant regressions |
| The unresolved-wave guard and restart recovery scanned all historical dispatches before locating an incomplete group | migration v20 locates the authenticated latest dispatch through an indexed source tail, then checks only that group; the append-only transition invariant guarantees no older unresolved group can be hidden behind a later valid group | source-tail query plan, missing/altered index, crash-recovery, 1,000-lifecycle tail, and full-suite regressions |
| Scheduler randomization assigned only one dispatch wave, so later waves reverted to the production arm and could not estimate an end-to-end proof-attempt effect | protocol v2 assigns the complete workflow, binds every wave with a contiguous exposure index, reconstructs the assignment across restart, and migration v21 indexes experiment/unit/exposure while protocol v1 remains replayable | four-wave/two-invocation lifecycle, both-arm, gap, duplicate, omitted-assignment, migration, and full-history audit regressions |
| Workflow startup silently ignored any `ValueError` raised while synchronizing branch workbenches and could continue to child launch with malformed state | the already-normalized branch setting and workbench synchronization now fail closed through the abnormal-exit recorder | an injected malformed-state error launches no executor, propagates to the caller, persists `stopped`, and records `workflow_aborted` |
| Candidate identifiers were unique only within one comparison node, allowing an ancestor and nested candidate to alias one persistent counter | candidate IDs must be unique across the complete nested comparison tree | the generator and trace validator reject a constructed ancestor/child collision |
| Generic deferrals accrued for work excluded by a mandatory constraint or higher policy tier even though fairness cannot override either | only ordinal/fairness rejections within the active comparison stratum accrue; unselected child strata retain ancestry-aware aging | hard-exclusion and stable same-tier cohort properties pass |
| Candidate generation remained a manually assembled call graph: traces could not show which generator produced each row, declared cardinalities were unchecked, the residual fallback was invisible, and outer strategy and parallel composition were outside the registry | graph v2 now declares 95 families in eleven scopes, including fine parallel internals and solved-root delivery; content-addressed declarations, active counts, and run-length-encoded row assignments are validated during generation and replay; the 82-family v1 declaration remains replayable | AST producer equality, golden whole-graph digests, v1 replay, exact-declaration/digest tamper, malformed assignment, cardinality, duplicate-source, all-scope conditional-service, dense-trace, and full-suite regressions |
| A zero candidate count could not distinguish a policy whose applicability was evaluated from a policy skipped by an enclosing feature or phase gate; a first manifest upgrade could also be stripped while retaining the rest of a current standalone trace; automatic completion of missing evaluation labels could mask instrumentation omissions | graph epoch v3 requires candidate-generator manifest v2, which partitions every declaration into evaluated and skipped families, assigns canonical machine-readable skip codes, forbids output from skipped families, and preserves genuine graph-v1/v2 replay; production admission rejects unresolved families, generator-bound generic comparisons use decision epoch v8, and parallel policy v5 includes the manifest digest in wave identity | evaluated-zero versus disabled-wave tests, unresolved-production-partition rejection, full-manifest deletion, partition/count/cardinality tampering, current-epoch schema downgrade rejection, v1/v2 legacy replay, v4 admission replay, v5 identity separation, soundness suite, and full regression suite |
| A candidate rejected only because an earlier companion owned the same claim or route was treated like a permanently inadmissible action, so canonical order could starve it forever; fairness also depended on parsing English reason strings | policy v6 separates fixed-primary conflicts from sibling queueing, assigns durable bounded deferrals only to the latter, and emits typed outcome codes directly from the admission transition; replay independently verifies both code and explanation | conflict-clique populations two through six all receive service within the declared bound plus population; primary and budget-unauthorized conflicts never age; forged current traces fail replay and cannot affect history; durable SQLite, seal, migration, legacy-v3/v4/v5 replay, and full-suite tests |
| Aggregate token allocation reserved demand for every later unprotected row, including actions that were unauthorized, conflicted with the selected verifier, or could not fit the remaining worker capacity; changing this under the same version would also have invalidated persisted replay | policy v7 freezes v6 semantics, then projects the deterministic conflict- and capacity-feasible continuation conditional on admitting the current protected action and reserves only the unprotected demand that continuation can consume | direct v6/v7 semantic-separation, legacy-v4/v5/v6 replay, unauthorized-demand, certification/discovery-conflict, capacity-excess, token-conservation, replay, and full-suite regressions |
| Parallel identity depended on a manually curated list of object fields; two tasks differing only in an omitted field such as the exact query collided and aborted the wave, while adding fields later risked transferring old fairness state to the wrong task | policy v7 appends a canonical digest of every stable action field while retaining the legacy routing prefix used by conflict checks; only budget and operational/post-admission fields are excluded, while prompt-bearing `reason` text is committed; ambiguous pre-v7 counters reset | arbitrary-query and prompt-text distinction, operational-decoration invariance, input-order invariance, budget-stability, non-string-field rejection, malformed identity, v4/v5/v6 replay, and counter-reset regressions |
| A candidate blocked by a serializable ownership conflict with the scheduled primary could never accrue waiting time; merely swapping it into the primary row would also have reused companions generated under a different leader | policy v8 gives serializable primary conflicts a distinct outcome, promotes only an overdue same-tier candidate against a nonmandatory primary, records the leader cohort in the ordinary durable comparison state, and regenerates the complete companion set under the selected leader | serializable-versus-structural aging, mandatory and tier exclusions, four-candidate bounded service, legacy-v7 replay, exact leader-trace validation, and full workflow-regeneration regressions |
| Greedy companion admission could choose one high-priority integration and thereby exclude two compatible verification jobs with a larger declared wave value; an initial bounded beam could itself fall below the greedy result after pruning | policy v9 performs deterministic fixed-width global subset search with authenticated max-weight fairness and a replayed v8 lower bound, so it can improve a wave but cannot regress under its declared host objective; the complete search evidence is wave-ID-bound and explicitly excludes model self-scores | constructed greedy counterexample, exhaustive optimum on 100 random small conflict graphs, 30 pruned 100-candidate v8 comparisons exercising both improvements and lower-bound fallbacks, metadata/NaN tampering, shared live/replay transition, and a checked heterogeneous 2,000-candidate benchmark |
| A pruned v9 beam reported only `bounded_approximation`, with no replayable upper bound and therefore no way to distinguish an exact result found despite pruning from a genuinely unresolved optimization gap | policy v10 records the greatest admissible bound of every discarded frontier, compares it with the selected v8-or-better lower bound, and marks exactness only on equality; the bound is part of the wave identity and deterministic replay | a 20-candidate pruned instance certifies the known global optimum, independent bound tampering fails replay, legacy v9 semantics remain committed, and scheduler regressions pass |
| V10 charged each selected task's full request during subset search, so it could certify one task as exact even when two tasks could both receive the supported minimum useful grant; canonical residual allocation would also arbitrarily favor the first selected row | policy v11 searches over minimum-feasible grants, then distributes reserved and shared residual tokens by deterministic integer max--min allocation without changing the certified subset; v10 remains immutable for replay | a direct v10 counterexample is repaired by v11, max--min grants are checked exactly, and randomized exhaustive budget/capacity oracles verify feasibility, selected objective, and every reported upper bound |
| V11's admissible upper bound ignored class-specific choice and the global verification/integration exclusion, leaving the dense fixture at `(24,3400,6,0)` against a loose `(24,3600,6,0)` bound despite an apparently optimal selected set | policy v12 computes a suffix dynamic-programming relaxation that enforces remaining class capacities and verification/integration exclusion while safely relaxing exact identity and token conflicts | the dense 2,000-candidate fixture now certifies exact equality and runs substantially faster; constructed and randomized exhaustive conflict-graph oracles prove the reported bound contains the true optimum; v11 remains replayable |
| V12's bound still counted unauthorized, subminimum, and fixed-primary-conflicting candidates; it limited neither total nor shared-pool minimum allocations and could pair the right first three objective coordinates with an impossible positive remaining-token coordinate | policy v13 filters intrinsic and fixed-primary infeasibility, then uses a resource-indexed suffix dynamic program over class capacity, total positive-token count, shared-only count, and exact minimum-token decrement | a 40-candidate resource counterexample tightens from `(0,600,6,0)` to the exact `(0,200,2,0)`; a mixed resource fixture removes an impossible 10,000-token remainder; randomized exhaustive mixed-class/resource/conflict oracles verify all four coordinates; both unbudgeted and resource-constrained 2,000-candidate benchmarks hard-gate exact certificates; v12 remains replayable |
| V13 still relaxed every sibling conflict in its suffix bound, and independently optimized class/certification, route, and target relaxations can miss their intersection | policy v14 adds route and certification-target clique partitions; v15 evaluates them within the applicable certification regime; v16 enforces class capacities within the partitions and adds mixed certification/research and certification/adversarial route cliques; v17 identifies equal structural-conflict states; v18 indexes exact suffix conflict neighborhoods and quotients equal-value states with identical feasible continuations | the 100-candidate same-route gap closes from `(24,600,6,0)` to exact `(4,100,1,0)`; an overlapping gap closes to `(16,1000,4,0)` under v16; a 48-candidate label-symmetry gap closes under v17; a synthetic capacity-eight case improves from v17's `(30,2600,5,0)` to the exhaustive `(36,1800,6,0)`; and, separately, a live-capacity case tightens v17's loose `(36,1500,6,0)` upper bound to its exact selected value `(30,2300,5,0)`; partition, pairwise-mask, randomized exhaustive, replay, and five dense certificate gates pass; v13--v17 remain replayable |
| V18's branch-and-bound pruned states whose objective bound equalled the incumbent; its objective certificate could therefore be exact while the selected candidate-ID tuple was not the declared lexicographic minimum | policy v19 retains incumbent-equal bounds for waves of at most 128 candidates, evaluates terminal states before pruning, compares an equal-valued v8 lower bound by candidate IDs, and emits separate replay-bound objective and canonicality certificates; larger waves preserve strict pruning and report canonicality unproved if equal-bound states were discarded | a minimized five-candidate live-capacity counterexample changes only the tied representative; exhaustive randomized conflict and protected/shared-resource oracles verify the exact objective and candidate-ID tuple; a forced one-state frontier refuses to certify canonicality; v18 remains replayable |
| V19's exact tie retention was deliberately limited to 128 candidates because applying it to all waves made the 2,000-candidate resource fixture take 1.64 s; large waves therefore could not certify their tied representative | policy v20 precomputes the lexicographically least ID subsequence for each suffix and exact remaining cardinality, prunes an incumbent-equal state only when this lower bound cannot improve the tuple, and binds the least tuple associated with the greatest objective discarded by beam truncation | all five dense shapes certify both objective and canonical selection in focused runs; a 10,000-case independent exhaustive campaign with arbitrary IDs, protected/shared resources, widths 1/2/4/8/128, and 1,412 truncated searches found no false objective or canonical certificate; the suffix table is capped by candidate count against excessive direct-call capacity; v19 remains replayable |
| V20 retained partial states even when another state could realize every one of their continuations with no worse value; its suffix table also grew quadratically in retained tuple elements if a direct caller supplied both a large population and excessive capacity | policy v21 removes a state only under componentwise slot, class, protected/shared resource, exact suffix-conflict, objective, and canonical-ID dominance; the pairwise reduction is limited to small waves or post-quotient frontiers of at most 32 states, and suffix cardinality is capped at 32 with an empty-tuple conservative fallback | an exhaustive 16-candidate, four-state-frontier regression tightens v20's unresolved `(32,1500,6,0)` bound to exact `(30,2200,6,0)` after two reductions; a 10,000-case independent conflict/resource oracle produced 955 truncated searches, 1,065 reductions, and no false objective or canonical certificate; all dense gates validate the applied flag, prune count, frontier limit, suffix cap, and completeness; an unconditional prototype that regressed the heterogeneous wave from about 213 ms to 914 ms was rejected; v20 remains replayable |
| A bounded v21 frontier could still select a strictly suboptimal wave or retain a nonzero certificate gap even at the default width | policy v22 invokes a deterministic best-first branch-and-bound completion only when the beam certificate remains unresolved; it uses the same objective and canonical bounds, exact future-equivalence quotient, and a fixed 20,000-state ceiling, reporting the residual frontier if the ceiling is reached | a one-state-frontier case improves selection from `(26,4200,6,0)` to exact `(30,3000,6,0)` after 15 states; a default-width 129-candidate case moves from `(34,5200,6,0)` against `(36,3900,6,0)` to exact `(36,3900,6,0)` after 484 states; a 10,000-case oracle exercised 140 completions, including 76 deliberately limited frontiers and 27 improved selections, with no false certificate; v21 remains replayable |
| Candidates that could never be admitted still affected beam-width selection, conflict signatures, suffix tables, and equivalence, so irrelevant rejected rows could perturb bounded-search behavior and cost | policy v23 filters authorization failures, primary conflicts, already-full classes, subminimum requests, and candidates without an individually available token pool from optimization while preserving every original outcome row | inserting 154 infeasible rows leaves selection, objective, upper bound, beam width, and expansion count unchanged; a 10,000-case resource/conflict oracle filtered 25,466 rows across 953 truncated beams and found no false certificate; all dense gates bind total, searchable, and filtered counts; v22 remains replayable |
| Certificate-triggered completion restarted at the root and spent its fixed state allowance re-expanding the beam prefix | policy v24 records the disjoint non-pruned frontier removed by beam truncation and resumes best-first branch-and-bound there; bound-pruned, exactly equivalent, and exactly dominated regions retain their existing proofs | the default-width 129-candidate case falls from 484 to 91 completion expansions; the forced one-state frontier falls from 15 to 6, and under a six-state limit v23 remains unresolved while v24 is exact; a 10,000-case exhaustive campaign covered 2,225 truncated beams, 264 completions, and 100 deliberately limited residual frontiers without a false objective or canonical certificate; v23 remains replayable |
| V24 bounded completion expansions but retained every discarded frontier state, so an adversarially long wave could create unbounded auxiliary memory before completion began | policy v25 caps the saved frontier at 20,000 states; within the cap it uses v24 continuation, while overflow releases the cache and safely falls back to bounded v23 root search with an explicit residual certificate | a forced one-state cap exercises the fallback and remains exact; a 10,000-case exhaustive campaign varied frontier limits 1/2/20,000, covered 354 overflows and 48 triggered root fallbacks across 2,321 truncated beams, and found no false objective or canonical certificate; v24 remains replayable |
| A matched scheduler archive could name v12/v13 conditions without proving which policy governed runtime waves; independent arm identifiers and unregistered run IDs permitted post-selection, problem identifiers did not bind problem bytes, chosen seeds did not establish randomization, a contiguous trace prefix did not prove completion, and asking condition-blind graders to inspect policy-bearing traces was contradictory | assignment protocol v3 emits every arm in one complete registered block, commits exact problem content and the complete arm-to-run map, and derives block seeds from a signed post-registration randomness receipt; the signed schedule fixes problem/prompt hashes, budgets, and stopping rules; experiment protocol v6 replays every decision/action and policy, requires complete blocks, binds a final dispatch digest, gives graders a condition-free artifact manifest, and assigns the unblinded completeness review to a separate trace auditor whose signature binds the exact finalized grade file | exact-problem mismatch, postselected-run, incomplete-block, wrong-policy, grading-condition leakage, grade-file replacement, forged-randomness, missing randomization/trace trust anchors, trace-finalization rewrite, certificate-tamper, and valid end-to-end archive regressions |
| Candidate-generator graph v4 attributed the scheduled-primary leader row to a helper that emits only serialized candidates | graph v5 gives the scheduled row its own materializer and producer declaration while preserving graph v4 unchanged for replay | exact graph-v4/v5 digests, immutable-version coverage, leader-trace validation, and AST producer-equality regression |
| `regulate_decomposition` was a scheduler-produced, budgeted, role-classified action but absent from the authoritative executable-mode set; raw malformed leader candidates could also displace a valid primary before failing at dispatch | append-only action contract v1--v5 declares every mode, actor route, budget class, polymorphic `prove` classification, allocation arithmetic, and request limit; budgeting, literature search, selection, role routing, leader eligibility, workflow dispatch, and authoritative persistence consume it, and each new trace persists its exact contract identity | semantic mutation, literal-producer exhaustiveness, derived-consumer equality, invalid-selection, resource-allocation mutation, real store-level dispatch, and malformed-leader regressions |
| A deterministic run could be recorded without a prior durable dispatch or result; attempt claims accepted substituted plans or changed context; allocations could disagree with authenticated state or overcommit a group; run telemetry could relabel a recorded executor result; a rejected patch could advertise unattached output artifacts; a group could omit an admitted companion; and mathematical enrichment occurred after admission | deterministic telemetry now requires the dispatch/attempt/result lifecycle; the attempt boundary checks exact action, plan, revision, routing, model profile, and prelaunch context hash, while result persistence rechecks the claimed plan; the patch boundary checks allocations and binds completion to the result's reserved identifier, normalized usage, timing, execution configuration, context, strategy, failure class, derived status, and accepted-patch outputs; every admitted wave member occurs once; enrichment precedes admission | plan/context substitution, changed-result-plan, missing-result, run-ID/usage/timing/model/context/strategy/status tamper, unattached-output sanitization, false-snapshot, protected-reserve, omitted-companion, post-admission-mutation, complete-wave, full-suite, and 1,000-lifecycle benchmark tests |
| Live selection and replay shared one transition, but that allowed both to change together and reinterpret an old trace under new semantics without any failing test | every supported parallel epoch v3--v25 and generic decision epoch v4--v8, plus action contract v1--v5, now has an import-time SHA-256 semantic commitment; a history-aware CI guard also covers all candidate-generator graph epochs, requiring contiguous append-only versions, immutable published digests, and nondecreasing active selectors | semantic-vector completeness and mutation, cross-epoch distinction, malformed/modified/removed/downgraded epoch rejection, real-Git base comparison, import gate, focused soundness suite, full suite, and hard benchmark; enforcement still depends on protected CI and is not an external witness |

The pass also made the reference-source read single-use, made process RSS
failure conservative, prevented output-diagnostic replacement from following a
link, and ensured scope-import rollback removes newly copied evidence on an
ordinary exception. Database and filesystem changes still cannot be made one
crash-atomic transaction; that remains explicit below.

## Review by system dimension

### Harness design

The child model remains an untrusted proposer. Host-created authority binds the
role, action, target, proof approach, context revision and hash, model/tool
policy, and disclosed identifiers. Mathematical state changes occur through a
write-serialized patch boundary, and content-bound certificates are issued
only by the corresponding host workflow. Patch shape, state invariants,
current projection seals, event policy, and journal endpoints are checked
before mutation.

The audit boundary is materially stronger after this pass: current proof rows,
run-selection provenance, the patch head, event tail, and live policy
projection are checked together. Full replay remains available, and optional
external Ed25519 checkpoints can bind the complete history heads outside the
database.

The principal unresolved harness defect is structural. `scheduler.py` has
17,032 lines and 401 functions after extracting the complete parallel
admission policy and its replay verifier. The extracted module has itself grown
to 4,909 lines, including a 2,104-line search transition, separate 69-line
dominance reduction, and 439-line validator;
the generic 239-line resource/clique relaxation is now isolated in its own module;
the other central context, patch, and workflow modules also remain large. The
scheduler records a typed comparison for candidates it constructs. A
versioned graph v5 now covers 97 generator families across twelve principal scopes,
binds each materialized row to its source family, enforces cardinality, and
records whether each zero-output family was evaluated or skipped with a phase
reason. It also property-checks conditional same-tier service for every
registered scope.
Complete flags remain scoped: this cannot prove that an absent useful policy
should have been designed, nor establish service across permanent higher tiers
or structural conflicts. Generator declarations and row assignments are
compact/content-addressed, but immutable candidate rows still grow linearly and
a sufficiently large single trace can exceed patch limits.

### Context management

Strict verification, integration, and formalization packets fail closed when
their mandatory dependency closure does not fit. Ordinary research packets are
intentionally lossy and disclose exact population hashes, counts, and a bounded
type-fair identifier catalog. Selected artifact text is read through a stable
descriptor and checked against the recorded digest. State, current seals, and
policy heads come from one SQLite snapshot.

Catalog v3 now actually rotates in production. It still lacks an explicit
request for page *n*. If the page is shortened during final context fitting,
discoverability decreases even though the manifest reports the truncation. A
correct packet also cannot prove that a provider retained or attended to every
included premise.

### Long-horizon reasoning

Persistent claims, inferences, proof approaches, proof obligations, negative
results, branch summaries, exact resume identities, strategy switching, and
certificate invalidation provide a real long-horizon substrate. Progress
credit is tied to accepted, causally linked state changes rather than a model's
self-report.

The substrate does not supply a liveness theorem. The ordered planner can
spend indefinitely on locally admissible maintenance or repeatedly choose a
weaker approach. Current-state verification is also not constant-time:
projection hashing is proportional to current state, the provenance seal to
the run table, authenticated steering to event history, and artifact
authentication to selected file size. Authoritative database, evidence, and
journal growth has no complete compaction protocol.

### Ability to generate novel ideas

The novelty contract enforces declared structural diversity, separated
generation and selection, comparison with previous failures, and explicit
falsification criteria. These controls reduce paraphrase and accidental repeat
work.

They do not measure originality or usefulness. The built-in method collection
biases search toward anticipated patterns; proposer-supplied semantic labels
can be wrong; and several diverse candidates may all be standard or false.
There is no preregistered held-out study with independent expert grading that
supports a claim of improved novelty.

### Mathematical ability

The kernel can establish consistency of recorded mathematical structure:
statement identity, dependency closure, acyclicity, current evidence binding,
proof-obligation status, and the distinction between informal review,
reproduced computation, and formal checking. It cannot decide the truth of an
informal argument.

Distinct provider/model-family labels do not establish epistemic independence;
reviewers can share training material and systematic errors. A reproduced
computer-algebra output establishes that captured code produced captured bytes
under the recorded contract, not that the code represents the theorem or that
the mathematical inference from it is valid. Exact formal-target binding does
not prove that the formal statement is a faithful translation of the informal
problem.

## Residual findings after the fixes

No tested ordinary child patch bypasses the current authority and certificate
gates. This is a bounded empirical statement, not a proof of absence.

### High priority

1. **No global scheduler liveness theorem.** The registered comparison scopes
   now have exact producer/row provenance and conditional same-tier service
   properties, including fine parallel, leader, and solved-root phases. Stable
   same-tier serializable ownership conflicts with a nonmandatory primary now
   receive bounded service. Structural exclusions, changing inputs, higher
   tiers, resource infeasibility, terminal transitions, and execution failure
   can still prevent service.
2. **Informal verification remains fallible and correlated.** Treat it as
   review, never formal proof. High-consequence results need a real formal
   proof or independent human mathematical review.
3. **No protocol-valid general ability or novelty evaluation.** Historical
   archives remain provenance examples. They do not establish a success rate,
   causal advantage, or originality.
4. **No live formal success on this host.** Lean, `lean4checker`, Rocq/Coq, and
   Agda are unavailable. Adapter tests demonstrate fail-closed behavior only.
5. **Local aggregate RSS containment remains observational rather than a
   kernel quota.** Locally supervised Codex and bundled Claude sessions now
   share one workflow-wide sampled RSS
   governor, but polling can miss a short memory spike, a descendant can detach
   or reparent, and a hostile same-user process can interfere with `/proc`
   accounting. CPU time, process count, network use, and aggregate output are
   not governed by the same object. External executors are deliberately marked
   unverified. A third-party in-process executor's concurrency/resource
   capability attributes are also a host-trust declaration, not remote
   attestation. Use a cgroup- or service-level CPU, memory, process, network,
   and output quota for a hard deployment boundary.

### Medium priority

1. The current seal authenticates the live projection, compact provenance,
   patch and event endpoints, and exact append-only guards. It does not
   recompute every old entry on every mutation; a privileged actor that drops
   the guards, rewrites a non-head row, and restores the exact definitions is
   detected only by full replay. An external checkpoint prevents an
   undetectable coherent head rewrite, but a retained old head alone does not
   prove that every locally stored interior row is still present.
2. An administrator controlling SQLite and every signing key can manufacture a
   coherent alternate history. There is no write-once store, public witness,
   independent timestamp, or custody separation.
3. SQLite commits and evidence-file installation are not one cross-resource
   transaction. Scope import cleans up ordinary failures, but a process or
   machine crash can leave unreferenced copied files.
4. Cold-storage pruning has a final check/unlink race because the operating
   system provides no conditional unlink by inode. Quiescence is procedural,
   not kernel-enforced.
5. The HMT sidecar catalog and proof database are separate persistence domains.
6. Provider resume state and attention remain opaque.
7. Whole-project authoritative storage grows without a complete retention or
   compaction design. Pre-launch admission does not cap growth during a child
   run.
8. Catalog rotation works, but there is no explicit page-selection operation.
9. Dashboard steering tokens prevent cross-site request forgery; they are not
   user identity. A deliberately non-loopback dashboard still needs an
   authenticated proxy or first-class read authentication.
10. Runtime closures are not fully content-addressed. The host kernel, system
    mounts, dynamic loader, and libraries remain trusted.
11. The custom executor hook is trusted host code and can invalidate the normal
    process boundary if untrusted code is passed through it.
12. Online control-history checks now use indexed tails, ordinal source
    sequences, and compact statistics rather than accumulated-row scans. Full
    audit and storage remain linear, and the 1,000-lifecycle gate does not
    justify million-row, multi-year retention claims.
13. Trigger-maintained source ordinals fail closed after an unpaired direct SQL
    insertion, but there is no automated quarantine/repair command. Recovery
    currently requires restoring a checkpoint or an explicitly audited
    administrator intervention.

### Mathematical and empirical limits

1. Portfolio diversity is not originality.
2. Outcome learning is observational and selection-biased, not a calibrated
   probability of progress.
3. No independent computer-algebra engine cross-check is required.
4. Rocq and Agda have no separately implemented second kernel in this harness;
   some assumption checks are syntactic.
5. Formal encoding equivalence remains a mathematical proof obligation.
6. A rigorous record of a stalled research program is possible even when the
   system cannot generate the missing idea.

### Maintainability limits

1. The four central modules remain too large for confident local reasoning.
2. Compatibility still exposes internal names such as the SQLite `debts`
   table and old operation aliases. Public text uses standard mathematical
   terminology, but a future schema migration is still needed to remove these
   names rather than merely translate them at the boundary.
3. Full patch/event/provenance replay is now confined to explicit audit, but
   current mathematical-state projection hashing and several semantically
   unbounded artifact/review collections still need million-row profiling and
   a retention design.
4. The test-only legacy mutation helper deliberately bypasses normal writer
   APIs under explicit migration authority; it must never become a production
   convenience API.
5. Nineteen store migrations and version-dependent trigger definitions now
   carry substantial compatibility complexity. Golden-schema comparison and a
   smaller declarative migration layer are still needed; passing downgrade
   fixtures do not make this easy to reason about locally.

## Verification record

| Check | Result | What it does and does not show |
| --- | --- | --- |
| Phase 2 modules | All cases found by unrestricted `test_*.py` discovery were included in the clean full run | current implementation, migration, boundary, workflow, and adversarial behavior; not a proof of mathematical truth |
| Entire `agents/generation/tests` collection | 1,427 tests passed in 195.596 s on the final v25 tree under unrestricted `test_*.py` discovery; the focused 311-test soundness module passed in 70.361 s; zero rubric warnings | repository-local regression evidence; deployment races and unavailable tools remain outside coverage |
| Scheduler microbenchmarks | the final unchanged hard-gate command exited zero: 8.60 ms ordinary-planning p95; 10.04 ms parallel-wave p95; 0.0132 ms compact-fairness p95; 1.77 ms legacy bounded-history p95; 227.00/300.72 ms p95 for wide/deep 2,000-item states; v25 optimizer runs measured 220.49/69.39/30.53/205.77 ms p95 for heterogeneous/resource-constrained/same-route-clique/repeated-equivalence 2,000-candidate searches and 5.40 ms for the 12-candidate live-capacity suffix-neighborhood counterexample, all with exact hard-gated objective and canonical-selection certificates. An immediately preceding full run transiently failed only the deep-state gate at 391.15 ms; three isolated repetitions measured 283.85/275.51/278.12 ms and the identical full rerun measured 300.72 ms against the unchanged 350 ms gate | local deterministic scheduler cost and synthetic scale only; not proof success, originality, or end-to-end throughput |
| Python compilation | Passed | syntax/import compilation only |
| Patch-schema JSON parse | Passed | syntax/serialization only |
| Git whitespace validation | Passed | patch formatting only |
| Experiment archive auditor | Passed; all 12 archives remain `historical_unvalidated` | confirms labels and declared checksums, not performance or novelty |
| Scope-import focused module | 8 tests passed | includes stable copy, rollback, link rejection, seal update, and concurrent resume serialization |
| OpenSSL checkpoint link test | Passed live with OpenSSL 3.5.5 | proves the tested output-link rejection; no independent key custodian |
| Installed publication isolation tools | pdfLaTeX 2025, bubblewrap 0.11.1, `prlimit` 2.41.3 present | real local tools; complete runtime closure is not content-addressed |
| Codex backend contract | Passed live with CLI 0.153.0; executable SHA-256 `fce635028842bfe9257140e8b7d53162732945e2f356fc35225be0702b4974be` | real installed binary and networkless capability probe; no paid mathematical run was used as correctness evidence |
| Lean, Lake, `lean4checker`, Rocq/Coq, Agda | Unavailable | no live formal success is claimed |
| Claude, Node.js, Julia, Macaulay2, Sage, GAP, Singular | Unavailable | simulated or absence behavior is not counted as a live integration success |

The latest full clean rerun was performed after base scheduler policy v7,
generator-bound decision epoch v8, twelve
base-policy strata, the 97-family versioned candidate-generator graph v5 and
manifest v2,
content-addressed declarations and compact row-source assignments, complete scoped verification enumeration, explicit
reconciliation, declarative action classes,
ancestry-aware deferrals, conflict-aware parallel-wave admission,
parallel policy v9 bounded global resource search with a v8 lower bound,
v8 serializable-primary leader rotation, v7 full-payload
identity and feasible-demand allocation, v6 cross-class capacity and
sibling-conflict fairness, machine outcome codes,
manifest-bound wave identity,
and replay, single-pass persisted-budget wave
admission, migration-v10 compact fairness state, stale-completion telemetry
preservation, migration-v11 pre-execution dispatch persistence and replay,
v12 exact-action recovery, v13 attempt/result persistence before live merge
waiting, recovery-order preservation, and idempotent post-return recovery,
v14 crash-policy reconciliation, staged-file identity, original-wave recovery,
transactional run-ID reservation, and gap-free migration validation,
v15 control/proof-history separation, v16 immutable patch endpoints, v17/v18
ordinal source sequences, v19 compact sealed scheduler statistics, and v20
indexed randomized-assignment uniqueness,
selection-scoped human notifications, and projection-only HMT cadence. An earlier run exposed two
publication-loop regressions caused by correctly discarding the action built
on the mutation-producing snapshot; the reconciled review now derives the same
repair or operator-pause action from the stable second snapshot. Earlier during
this cycle, a full Phase 2 run exposed nine failures: six
were test fixtures bypassing the newly enforced state writer, one revealed the
real scope-import seal omission, and three were transient bubblewrap namespace
allocation failures. The fixtures were migrated to the production writer, the
scope defect was repaired, and transient sandbox unavailability is now labeled
separately. Only the final clean runs are reported as passing results.
During the v16--v19 continuation, the first full run passed 1,126 tests and
failed one adversarial event-deletion fixture because the new authenticated
source-row foreign key correctly blocked deletion. The fixture was changed to
remove the source commitment under the same explicit guard bypass before
deleting the event; that correction produced a clean 1,129-test run.
The subsequent legacy-boundary audit found that the first v15 projection
baseline could conceal an edited interior v14 patch row. Migration now
authenticates the complete pre-baseline chain and rejects that adversarial
fixture. A further audit repaired post-baseline suffix comparison and made
branch-workbench startup synchronization fail closed. The clean totals at that
stage were 1,190 Phase 2 tests and 1,383 generation tests. After the
randomized-calibration and migration-v20 round, the focused soundness suite
passes 278 tests and the complete generation suite passes 1,394.

## Standard mathematical terminology

New public prose and model-facing contracts use:

| Internal or legacy expression | Public mathematical expression |
| --- | --- |
| debt | proof obligation |
| route | proof approach |
| proof dossier | proof draft |
| ledger | record, catalog, or status table |
| battery | test suite or collection of checks |
| villain | adversarial reviewer or counterexample researcher |
| branded defeat loop | decisive proof-obligation cycle |
| paperwork throttle | mathematical-output focus |
| proof-pressure scheduler | proof-strategy review |

Exact historical text, identifiers, database columns, and compatibility
operations are not silently rewritten because doing so would change hashes and
audit meaning.

## Next acceptance milestones

### Scheduler continuation audit (2026-09-03)

The repaired scheduler passes its executable contracts, but the following are
still open findings rather than aspirational footnotes:

1. There is no preregistered, repeated held-out mathematical comparison with
   independent grading. Scheduler latency, trace consistency, and synthetic
   reachability do not establish proof success, originality, or state of the
   art.
2. Ordinal priorities, class capacities, token requests, and the three-round
   aging bound remain hand-chosen. There is no calibrated workload value/cost
   model, counterfactual policy evaluation, or uncertainty estimate.
3. Liveness is conditional. Property tests prove service for every registered
   stable same-tier generator cohort and for stable conflict-free parallel
   candidates under pure capacity pressure. Stable candidates that conflict
   only with siblings rotate, and stable same-tier serializable conflicts with
   a nonmandatory primary can become the regenerated wave leader. Structural
   exclusions, changing candidate sets, higher policy tiers, resource
   infeasibility, terminal-state transitions, and execution failures remain
   outside any wait-freedom or end-to-end termination theorem.
4. Completeness is relative to a manually registered generator graph. The
   evaluated/skipped partition is host instrumentation: production admission
   now rejects an unresolved family, but the manifest does not independently
   observe Python call execution or prove that an unregistered useful policy
   exists. The
   v7 action-to-identity digest covers every stable field, but the action is
   still an untyped mapping and the small list of allocation, placement, and
   post-admission fields excluded from that digest remains manually curated.
   An accidental new operational field would over-distinguish tasks until it
   was classified; it can no longer silently merge distinct payloads. The
   append-only action contract now makes mode, executability, budget class,
   role routing, and resource-allocation arithmetic exhaustive across the
   audited consumers. Its version and semantic digest are embedded in each new
   decision and dispatch record. Mode-specific auxiliary payload fields remain
   untyped, however.
5. Local restart recovery now serializes orchestrators, reconstructs the exact
   action, records every attempt claim and returned result, consumes a returned
   result without relaunch, preserves original-wave merge semantics, binds
   staged source bytes, reserves run IDs, recognizes an already accepted result
   patch, and pins resolved built-in executable bytes. It still has no renewable owner
   lease or distributed coordinator. A remote custom backend can complete work
   while its reply is lost before the local result record, and custom identity
   is self-declared rather than cryptographically attested. Thus the design
   closes the audited local post-return crash windows but does not prove universal
   exactly-once execution. The file lock remains local-host coordination.
   Session context is stably read and semantically rehashed immediately before
   the attempt claim, but a hostile process with direct write access to the
   capsule can still race between that check and the child process opening the
   pathname; eliminating that interval requires immutable descriptor passing,
   a read-only mount, or equivalent operating-system support.
6. Admission controls model tokens and worker counts. The local Codex/Claude
   supervisor now also cancels on the sampled sum of complete child
   process-tree RSS, including the independently timed HMT sidecar, but this is
   reactive execution control rather than predictive memory admission. It does
   not allocate aggregate CPU time, process count, network use, output bytes,
   or scarce formal backends. Usage normalization conservatively reconciles
   inconsistent component and total counts, but the backend's usage envelope
   is not independently attested and a dishonest remote executor can still
   underreport all fields together.
7. Immutable decision traces are duplicated linearly. The online projection is
   byte-bounded, but authoritative storage has no content-addressed/Merkle
   compaction protocol and one very large complete trace can still be awkward
   to transport.
8. `scheduler.py` remains 17,032 lines with 401 functions. Its
   fine-grained parallel planner is 302 lines; the v25 search transition and
   `parallel_wave_admission_errors` are themselves 2,104 and 439 lines, with a
   separate 69-line dominance reduction. The
   239-line generic resource/clique relaxation is separated and the admission
   dependency cycle is gone, but local comprehensibility is not yet
   satisfactory. `experiment_audit.py` is 3,061 lines and its general-evidence
   validator spans 1,352 lines, creating a separate audit-maintainability
   risk.
9. A wave is internally bound to authenticated snapshot/configuration hashes,
   but there is no independent witness that the registered generators were
   exhaustive or that the local snapshot corresponds to externally held
   state. Mathematical strategy enrichment and work-mode selection now precede
   admission; the only post-admission decoration is an operational companion
   index, and replay reconstructs and verifies the admitted input action.
10. Scale evidence is synthetic and single-process. Dense multi-parent DAGs,
    concurrent revision churn, heterogeneous evidence payloads, backend
    contention, repeated crash recovery, remote lost replies, and months-long
    trace retention remain unmeasured. Parallel Claude coverage uses a fake
    local CLI and synchronized executor fixtures, not a sustained real-provider
    load test.
11. Parallel resource admission is no longer greedy: policy v25 performs a
    fixed-width global subset search over minimum-feasible token grants, cannot
    score below v8 under its declared objective, carries a replayable upper
    bound that respects class capacities, verification/integration exclusion,
    primary conflicts, minimum total/shared resource feasibility, class and
    certification constraints within route/target clique partitions, and two
    mixed-route partitions. It additionally identifies equal-value partial
    solutions with the same exact conflict neighborhood in the unprocessed
    suffix, using indexed bitsets and canonical representatives, and
    max--min allocates residual tokens after selection. Both dense reference
    fixtures, the same-route clique fixture, the repeated-projection fixture,
    and the distinct-label suffix-neighborhood fixture now certify exactness;
    the hard benchmark rejects a loose or malformed certificate. When the beam
    cannot certify its result, v25 continues from the exact pruned beam frontier
    in best-first bound order for at most 20,000 states and retains at most
    20,000 frontier states; a frontier overflow releases the cache and uses the
    bounded root fallback. Queue exhaustion is exact, while limit exhaustion
    preserves the residual bound. Global
    optimality is therefore still not guaranteed on every possible wave. V23
    first removes candidates
    that are individually infeasible because of authorization, primary
    conflict, class capacity, or minimum-token availability, while retaining
    their rejection outcomes. Exact-neighborhood indexing is capped at
    4,096 candidates to bound bitset memory; larger waves use the structural
    quotient, and only waves of at most 128 candidates receive the 128-state
    frontier. V25 uses an exact-cardinality suffix lower bound on candidate IDs
    through cardinality 32, so an incumbent-equal state is pruned only when it
    cannot improve the tied tuple; larger cardinalities receive a conservative
    empty-tuple bound. The same bound is attached to the greatest truncated
    objective. It also removes a partial state only when componentwise
    capacity/resource comparison and exact suffix-conflict inclusion prove that
    all of its continuations are reproducible from a no-worse state. The
    reduction is adaptive because an unconditional pairwise pass was too
    expensive on wide heterogeneous waves. The objective and
    canonical-selection claims remain separate and fail closed.
    The
    optimized bitset builder mirrors the authoritative pairwise
    conflict predicate and is protected by a randomized equivalence oracle, not
    a machine-checked proof. The expansion and saved-frontier caps are not a
    wall-clock theorem: input validation, conflict projection, suffix
    relaxations, and each bound computation still scale with candidate count.
    The fixed 10,000-token
    minimum, ordinal weights, and max--min rule have not been calibrated on
    held-out workloads. Top-level and long-horizon mathematical selection are
    still one-step deterministic comparisons. No verifier-guided proof tree
    search has been evaluated under fixed compute, and model self-scores must
    not be substituted for such an outcome signal.
12. Randomized scheduler calibration is now executable and replayable rather
    than a free-form telemetry label. Protocol-v3 assignments form complete
    problem/repeat blocks, bind exact problem bytes, immutable policy semantics,
    candidate sets, actions, and contiguous workflow exposures, and derive each
    block seed from a signed post-registration randomness receipt. The
    randomization, registration, trace-audit, and grading keys are supplied out
    of band and role-separated. General-evidence protocol v6 replays every
    scheduler trace, checks the condition actually executed on every wave, and
    requires the execution-trace auditor to sign an explicit complete-trace
    finalization and the exact finalized grade file while graders remain
    condition-blind. It rejects literal condition identifiers in evaluation
    identifiers and grading artifacts, but cannot prove the absence of encoded
    or semantic condition leakage. It also recomputes
    the paired estimate, cluster-bootstrap interval, and paired-problem
    normal-approximation sample size. This establishes archive integrity relative
    to the trusted authorities, not the absence of undisclosed pilots,
    publication bias, benchmark contamination, a dishonest randomness source,
    or a false trace-auditor attestation. No held-out scheduler-calibration result is checked into this
    repository.
13. Live formal-checker coverage and provider independence remain incomplete.
    A recorded model-family label and a fail-safe unavailable-backend result do
    not prove epistemic independence or mathematical correctness.

1. Analyze liveness across ownership conflicts and policy tiers. Materialized
   row provenance, evaluated/skipped provenance, and conditional same-tier
   service are now checked for every registered scope; wait-freedom is not.
2. Add pinned live Lean/Rocq/Agda CI examples and record the complete runtime
   closure; do not weaken fail-closed absence behavior.
3. Replace sampled local aggregate RSS cancellation with a kernel/service
   resource domain, and require cryptographically attested resource receipts
   from remote executors.
4. Add explicit catalog page selection and latency/retention tests at realistic
   long-history sizes.
5. Add externally witnessed checkpoints or write-once custody separation.
6. Replace duplicated linear decision traces with content-addressed or
   Merkle-paged storage, empirically calibrate policy v25's host weights,
   minimum useful grant, max--min allocation, and workload costs, and
   add a renewable owner lease or distributed coordinator for dispatches whose
   remote reply has not reached the local result record.
7. Run a preregistered held-out mathematical evaluation with independent
   grading before making ability or novelty claims.
8. Continue adversarial search for bounded-width admission instances with a
   nonzero certificate gap, especially large distinct-neighborhood waves, and
   compare alternative exact or anytime solvers under the same compute bound.

## Conclusion

This cycle closes several defects that previous reviews and green tests missed,
including a production-only context-paging error, two symbolic-link boundaries,
and parallel-admission identity, dependency, provenance, liveness, and totality
defects. The remaining weaknesses are concentrated in the still-large scheduler
and composite planners, cross-process dispatch resumption, informal mathematical
judgment, empirical evaluation, external audit custody, hard process quotas,
provider opacity, and long-run scale. Those limits are part of the system's
current specification and must not be converted into stronger claims by
documentation or UI wording.
