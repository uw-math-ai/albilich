# Scheduler redesign: implemented boundary and remaining work

## Status

The scheduler now has deterministic, hash-bound comparison boundaries for the
base action and every simultaneously admissible research-strategy operation.
A complete front-door comparison covers actionable context requests, external
writing, paper audit, publication-route repair, and explicit formalization.
For an open theorem, one comparison materializes all twelve top-level policy
strata, including integration, verification, recovery, proof-obligation
routing, periodic mathematical text, and residual mathematical work. Every
object-valued recovery, obligation-routing, residual-work, and parallel-wave
queue is now enumerated before comparison or admission. Sequential integration
has its own complete child comparison over every eligible verified route,
including alternative routes to the same conclusion; assurance is bound to
each exact route in the planning snapshot. This
removed the source-order inversion that allowed periodic text maintenance to
preempt a ready strict-verification handoff. The verification stratum now
materializes every verifier-ready route (including competing routes for one
claim), proof-evidence handoff, support-theorem precheck, repeated verifier
loop, threatened dependency, pending counterexample, status reconciliation,
and unrouted proof claim. Its scoped trace is complete. The true no-work
retrieval action is excluded from fairness unless it is genuinely the
fallback. The evidence-assimilation stratum is also complete within its
declared scope: it emits every eligible exact-citation obligation, checked
source handoff, proof artifact awaiting conversion, root-target
external-citation card, and root-target definition-audit card. Object-keyed
cooldowns and durable result links ensure that selecting one item never
consumes an unselected peer. Open-theorem and parallel-admission traces now set
`candidate_set_complete=true` for their declared, registered generator scopes.
Candidate-generator graph v5 covers 97 families across twelve scopes,
including the outer research-strategy comparison, fine-grained parallel-wave
composition, serialized leader rotation, and solved-root delivery. Each comparison row is attributed to
one or more generator families; cardinalities, active families, counts, and
compact assignment runs are replay-validated. Manifest v2 also records the
canonical set of policies whose applicability was evaluated and a machine-
readable reason for every policy skipped by an enclosing phase or feature
gate. A zero count therefore means "evaluated with no row" only when the
evaluation set says so. The published v1--v4 graphs remain replayable and
all five graph epochs are protected by golden digests; graph v3 and later make the
stronger manifest mandatory so a current trace cannot be downgraded to the
legacy schema while retaining its current graph epoch. Registered generic
comparisons are stamped with decision epoch v8, so deleting the entire
manifest also fails closed; ordinary non-registry and historical comparisons
retain decision policy v7 or their original epoch.
Declarations are content-addressed by an immutable versioned digest rather
than copied into every nested trace.
This is not an exhaustive claim over every mathematically imaginable action:
later writing/publication phases remain a sequential state machine, several
state-level policies deliberately emit one aggregate action, and the registry
does not prove that a missing generator should have existed.

## Implemented design

1. One SQLite read transaction supplies invariants, the scheduling projection,
   and authenticated steering. Planning then verifies that the proof revision,
   event-chain head, and policy-event head are unchanged. A legacy
   synchronization write or concurrent proof/configuration update causes a
   bounded replan; four continuously unstable attempts fail safely instead of
   dispatching an action from a mixed snapshot.
2. Research-strategy policies generate a set of alternatives instead of
   returning the first matching branch. Hard verification and safety
   constraints remain non-probabilistic.
3. Selection is deterministic and lexicographic: admissibility, mandatory
   constraints, maximal policy tier, bounded-deferral fairness within that
   tier, ordinal priority, then a canonical candidate identifier. Generator
   traversal order is irrelevant. An overdue exploratory action cannot
   displace verification or state repair.
4. A continuously admissible top-level or extracted base-stratum candidate
   becomes due after three consecutive rejections among candidates in the
   current maximal policy tier. Nested accounting follows the complete
   comparison ancestry: a candidate locally selected inside a base stratum is
   still counted as deferred when the outer strategy comparator rejects the
   base branch. A mandatory constraint or persistently higher tier can still
   preempt it. This is conditional bounded liveness at the explicit comparison
   boundaries, not yet a global theorem for the complete planner.
5. The canonical candidate-set hash commits to candidate identity, action
   hash, policy tier, admissibility, mandatory status, priority, and deferral
   state. The nested base-policy trace has its own canonical digest committed
   by the base candidate, so it cannot be silently removed. Run telemetry
   stores the hash and policy version as deterministic selection provenance.
   Policy v7 stores candidate-keyed nested traces and commits every
   materialized nested comparison, including a stratum whose parent was not
   selected. Removing or modifying an unselected nested trace is detectable,
   and its candidates contribute ancestry-aware deferral history. Patch
   validation and state invariants recompute versioned hashes; valid v4-v6
   traces remain verifiable after the v7 upgrade.
6. Online outcome history is bounded to 96 recent run rows and 384 recent session
   patches. Decision traces in the scheduler projection also have a 16 MiB
   aggregate byte limit, always retain the newest trace, and disclose the
   included count/bytes and truncation state. The immutable audit rows are not
   deleted. Historical outcome summaries remain descriptive and have no
   ranking effect. Fairness no longer depends on this lossy projection: store
   migration v10 maintains compact authenticated deferral state for both the
   generic comparison tree and parallel admission.
7. Every action carries a `scheduler_policy_id`. New code uses standard terms
   such as proof obligation, admissibility, candidate set, priority, and
   deferral. Legacy database and compatibility fields named `debt` remain to be
   migrated separately.
8. Candidate generators for circling and root-revision notifications are pure.
   Their authenticated human notification is published only after the action
   wins the outer comparison, so a latent candidate cannot mutate the policy
   head or alert an operator. Periodic mathematical-text cadence is read from
   the shared scheduler projection rather than a second database snapshot.
9. Publication route-error repair and deterministic writing lint/compile
   synchronization run in explicit reconciliation phases before candidate
   generation. Rejected reconciliation patches fail closed. Writing and
   publication candidate builders are observationally pure, and required
   human-blocker notification failure is disclosed on the selected action.
10. Safety, verification, and recovery classes are declared in a validated
    policy registry with an explicit precedence relation. Context-request and
    formalization strata materialize every pending group/obligation instead of
    hiding all but the first.
11. Parallel companion planning loads one scheduler snapshot and applies a
    deterministic wave-admission policy. The workflow materializes ordinary
    and multi-branch candidates first, then performs exactly one admission
    against the persisted token and verification-reserve state. It rejects duplicate route ownership,
    same-claim certification races, and verification/integration conflicts;
    caps proof-search, role-specific, total concurrency, and the aggregate wave
    token grant; and records every materialized selection or rejection. The
    final trace contains pre-admission alternatives as well as the actual
    dispatched wave. Strict informal verification now both receives
    and is charged against the protected verification allocation even though its
    action mode remains `prove` for compatibility. Each admitted companion wraps
    the wave record in a valid hash-bound decision trace, so normal run telemetry
    preserves the provenance instead of recording companion selection as merely
    observational.
12. Scheduler-owned projections opt into a revision-local derived-view cache.
    The graph-policy index, route scoreboard, paused-route set, readiness index,
    verifier-ready candidates and summaries, route-evidence index, parsed
    deferral history, and entity maps are reused only within that immutable
    planning operation and reset at every scheduler entry. Cached row
    collections use copy-on-read so one consumer cannot alter a later policy's
    view.
13. Root distances are computed for the whole dependency graph by one
    reverse-edge breadth-first traversal. Wide and deep proof graphs are now
    linear in the number of claims plus parent edges; disconnected and cyclic
    components retain the documented reduction-depth fallback.
14. Counterexample validation cooldown is artifact-specific when v7 provenance
    is available, so checking one candidate does not hide a different candidate
    against the same claim. Confirmed-artifact references use exact identifiers
    or exact path basenames rather than substring identity. Advisor directives
    are ordered across roles, while completion remains role- and target-scoped.
    Unrouted proof detection uses typed proof artifacts rather than identifier
    substrings.
15. Evidence-assimilation candidates use the exact proof-obligation, artifact,
    or root-target retrieval-card identifier. Exact-object deferral histories apply within
    a queue. Completed source adaptations, negative proof-draft
    classifications, citation triage reports, and definition audits bind their
    originating object in durable metadata; rejected peers remain schedulable.
    Snapshot indexes replace per-artifact rescans of the proof graph.
16. Recovery enumerates every eligible bottleneck lock, with a stable exact
    proof-obligation identity. Residual work enumerates every ready step across
    all active decompositions, every route-triage/root-alignment/proof-
    compression target, and every active unverified claim. Obligation routing
    enumerates every source request, obstruction cluster, mathematical proof
    obligation, route without inference evidence, and failed/blocked
    decomposition. Duplicate ownership paths were removed.
17. Parallel generators materialize every verifier, support-precheck, exact
    citation, decomposition, and integration candidate before one admission
    pass applies conflicts, class capacities, total capacity, and token limits.
    The admission schema, semantic identity, pure state transition, replay
    validator, and wave binding now live in `parallel_admission.py`, so neither
    generic decision validation nor replay imports the scheduler. Policy v4
    encodes object fields as canonical JSON rather than delimiter-joined text
    and hashes the exact serialization, eliminating delimiter collisions and
    whitespace-normalization aliases while retaining v3 trace validation and
    fairness aliases. Its bounded aging promotes a capacity-deferred candidate
    across admission classes after three deferrals; ownership or resource
    inadmissibility does not age. The same pure transition determines live
    dispatch and replay. The wave identifier commits the candidate set,
    proof-state and run-provenance hashes, state revision, capacities, aggregate
    budget mode, and initial total/reserved budget. Policy v5 additionally
    commits the candidate-generator manifest in the wave identifier, so two
    zero-row waves with different evaluated/skipped policies are distinct for
    replay and fairness accounting. Every capacity rejection remains in the
    complete wave trace. Policy v6 distinguishes a conflict with the fixed
    primary (inadmissible in that wave) from queueing behind a selected sibling.
    Sibling-conflict queueing receives the same bounded-deferral service as
    capacity queueing, with a replay-validated machine outcome code rather than
    inference from prose. Policies v3--v5 remain replayable.
18. Sequential integration no longer hides the first route in a scheduler
    projection. It compares all eligible routes with route-keyed deferral and
    assurance state, skips already integrated conclusions, indexes blockers
    and certificate artifacts once, and avoids per-route SQL for standard
    assurance. A 1,000-route diagnostic fell from about 354 ms to 109 ms.
19. Generic decision rows retain only selection inputs, the exact action hash,
    and the validator-checkable disposition. Redundant mode/target/route labels
    and unvalidated explanatory prose were removed. In the 6,144-candidate
    obligation fixture this reduced a trace from 4.40 MiB to 2.85 MiB and
    increased retained online history from three to five complete traces.
20. Model-visible manifests and prompts translate compatibility names into
    ordinary mathematical terms. In addition to proof obligation/proof draft/
    test suite/adversarial reviewer, the former branded defeat-loop,
    paperwork-throttle, and proof-pressure names are exposed as a decisive
    proof-obligation cycle, mathematical-output focus, and proof-strategy
    review. Exact identifiers and quoted source text remain byte-exact.
21. Nested scheduler traces are recursively validated once at the final
    dispatch boundary rather than once at every enclosing comparison. This
    retains fail-closed validation while removing repeated traversal of dense
    child traces. Repeated immutable history payloads are decoded once per
    snapshot, and the route scoreboard now actually populates its cache and
    copies only the requested prefix on limited reads.
22. Generic decision selection and validation use the same pure
    `decision_outcomes` transition. Validators accept only the exact supported
    v4--v7 versions and validate scalar/container types before ordering,
    hashing, or membership operations. Deterministic nested-mutation fuzzing
    completed 30,000 generic and 50,000 parallel cases without an escaping
    exception; permanent mutation matrices cover both primary and companion
    wave records. These are robustness tests, not a formal totality proof.
23. The final adversarial pass made exclusive/terminal conflicts symmetric,
    rejects a nonterminal primary that lacks budget authorization, and prevents
    ambiguous v3 aliases from aging more than one v4 candidate. Production wave
    creation now requires authenticated state/provenance digests. The wave ID
    also commits its declared generator scope, and each generic wrapper binds
    the exact admitted candidate ID and pre-admission action hash. The validator
    derives the post-comparison-transformation flag from the two action hashes
    instead of trusting it as prose.
24. Store migration v10 replaces operational reconstruction of fairness from
    bounded trace history with two compact projections. Generic counters
    advance once per primary decision; companion completions are observational
    for that projection. Parallel counters advance once per distinct wave,
    regardless of which admitted run completes first. Counter rows refer to
    their exact authenticated provenance record, are included in the
    run-provenance seal, and are checked
    against the authenticated trace on every update and invariant pass. A
    caller cannot inject an invented prior count. Migration uses database
    insertion order rather than caller-supplied timestamps and seeds from the
    latest available primary decision and wave; a v9 store's old run-selection
    seal is verified before the derived state is installed and resealed.
    Candidate identifiers are unique across the complete nested comparison
    tree, and only rejections
    that fairness can actually override accrue generic deferrals.
25. Store migration v11 persists an admitted scheduler wave before executor
    entry. Dispatch and completion are separate relations: compact fairness
    cites the dispatch, each eventual run may cite exactly one dispatch through
    a unique foreign key, and completion cannot advance the transition again.
    The decision revision remains distinct from the later context revision.
    Through v14, dispatch metadata participated in row-exact proof-state
    replay. Migration v15 retains those historical commitments behind an
    explicit projection baseline and moves new execution metadata to its own
    provenance chain. Migration v11 verifies the v10 seal before rebuilding
    the fairness provenance columns. A stale dispatch transaction replans before launch,
    while a simulated orchestrator crash proves the committed transition
    survives with no fabricated run row.
26. Store migration v12 retains each canonical dispatched action and its
    execution-recovery contract. Execute-mode workflows take an exclusive,
    non-inheritable store lock; the kernel admits no new group while an older
    one is unresolved. Restart recovery verifies the action digest and resumes
    only unlinked members under the same configuration. Custom executors must
    declare both dispatch-key idempotency and a stable executor identity;
    incompatible or legacy dispatches stop for operator action.
27. Store migration v13 adds append-only executor-attempt claims and one
    returned-result record per dispatch. Each record has a corresponding
    hash-chained non-policy event; compact metadata participates in the
    run-provenance seal, while recovery and full audit recompute the digest of
    the bounded result body. The host assigns a dispatch-derived patch ID.
    Therefore a restart after result persistence does not invoke the executor,
    and a restart after proof-patch acceptance recognizes the exact accepted
    patch before recording the missing run telemetry. The built-in recovery
    contract also commits the resolved executable path and SHA-256 when it is
    available. A completed result is persisted before it waits at the live
    proof-merge barrier, and recovery uses the same proof-critical ordering so
    a stored lower-priority result cannot pass an unreturned verifier.
28. Store migration v14 preserves the original committed wave cardinality
    during partial recovery, so an unresolved primary retains its safe
    parallel-rebase semantics after a sibling lands. A returned proof patch
    remains applicable across only the host's automatic crash-stop/restart
    policy transitions; operator and scheduler-policy changes still invalidate
    it. Path-based artifacts bind the staged source SHA-256 and size before the
    receipt commits and enforce both during copying or writer ingestion.
    Finally, the result transaction reserves its run ID across pending results
    and completed telemetry, assigning a dispatch-derived host ID on collision
    while retaining the executor ID for diagnosis. Migration history must be
    exact and contiguous through v25, and v13 is fully validated before its run
    IDs are backfilled.
29. Store migration v15 separates mathematical proof state from scheduler
    execution history. Runs, dispatches, executor claims, and returned results
    are committed to one append-only authenticated provenance chain; database
    guards reject updates and deletion after insertion, while explicit audit
    recomputes every source-row digest and chain link. A v14 upgrade verifies
    both old current-state seals, revision coverage, delta shape, and every
    authenticated patch-chain entry before backfill. V14 allowed scheduler rows
    in its proof digest to change between patches, so migration does not
    mislabel this check as row-semantic replay. When nonempty control history
    changes the proof-projection identity, migration records an immutable
    projection baseline and the SHA-256 of the complete pre-migration database
    backup rather than silently rewriting old patch hashes. Online steering
    likewise validates an immutable event tail and reads only indexed steering
    event types; complete event replay remains an explicit audit operation.
    Patch application reuses the exact authenticated pre-state it has already
    materialized, and the immediate dispatch handoff verifies only the newly
    committed patch and event tails.
30. Store migration v16 fully replays an existing v15 patch journal before
    installing exact insert, update, and delete guards. A partial unique index
    enforces one applied patch per revision. Since the validated chain can then
    change only by appending the next revision, the online seal checks indexed
    endpoints rather than aggregating every historical patch; complete
    bidirectional replay remains the explicit audit path.
31. Store migration v17 adds a trigger-generated source insertion sequence for
    runs, dispatches, executor claims, and returned results. Each provenance
    entry must occupy the same ordinal as its source row. This detects an
    unpaired direct insertion without four full-table counts and preserves
    row-by-row recomputation for audit.
32. Store migration v18 applies the same construction to the event journal.
    The current event count is the tail ordinal of an immutable source sequence,
    not `COUNT(*)`; full event replay verifies every source ordinal against its
    corresponding event.
33. Store migration v19 backfills and seals trigger-maintained sufficient
    statistics for total runs, outcome runs, all retrieval calls, the registered
    policy-relevant retrieval intents, and session-authored patches. Online
    scheduling reads these compact rows while full audit recomputes them from
    authoritative history. Direct statistic mutation changes the current
    run-provenance seal. The per-intent view names its registered intents and
    reports the exact untracked total instead of implying that a bounded map is
    a complete census.
34. Version 3 of the acyclic candidate-generator graph declares 95 generator
    families across the top-level, parallel, precondition, solved-root, integration,
    verification, evidence, recovery, proof-obligation, residual, and
    open-theorem scopes. Static analysis checks exact producer coverage at each
    comparison boundary. Host generation records canonical active families,
    per-family counts, and run-length-encoded row assignments; exact duplicate
    parallel candidates retain every source family. Generation and replay
    enforce declared cardinalities and reject an omitted, reordered, unknown,
    or recomputed declaration. Manifest v2 partitions every declaration into
    evaluated and deliberately skipped families, requires canonical snake-
    case skip codes, forbids a skipped family from producing a row, and hashes
    that partition. Graph v3 and later require manifest v2, preventing schema downgrade;
    genuine graph-v1/v2 legacy manifests still replay. The immutable declaration is stored once and
    referenced by version and SHA-256, reducing a representative nested
    decision trace from 11,638 to 6,773 bytes. A property test over every
    registered scope establishes conditional bounded service for a stable,
    admissible, same-tier cohort. It does not establish service across
    permanent higher tiers or ownership conflicts, nor prove that an omitted
    useful policy should have existed. The 82-family/ten-scope v1 declaration
    and the 95-family v2/v3 declarations remain available for exact historical replay;
    the 97-family v4 declaration also remains replayable,
    and golden whole-graph digests prevent any published version from being
    edited silently.
35. Parallel companion generation, multi-branch generation, and final wave
    admission now consume the same scheduler projection in the workflow. This
    removes two redundant database projections per composed wave and closes an
    avoidable mixed-projection interval; the dispatch transaction still
    rejects a concurrent state or policy change.
36. The integrated-root branch is now an explicit solved-root comparison.
    When post-integration literature work precedes document delivery, the
    already-materialized writing and terminal actions remain in the trace as
    inadmissible rows instead of disappearing behind an early return.
37. Candidate-generator manifest v2 removes zero-count ambiguity. Production
    workflow composition shares one wave-local evaluation record across
    companion generation, multi-branch generation, and admission; disabled
    features and excluded phases receive explicit reason codes. Production
    admission rejects any declaration left neither evaluated nor explicitly
    skipped, so a missing instrumentation call cannot be silently relabelled
    as inapplicable; only the low-level direct-admission API synthesizes an
    explicit direct-call exclusion for families outside its input. Parallel
    policy v5 binds the resulting manifest digest into `wave_id`; registered
    generic comparisons use decision epoch v8 to make manifest presence
    mandatory. Tests cover
    zero-output versus disabled policies, multi-source deduplication, manifest
    tampering, graph-schema downgrade, and exact replay of v1, v2, v3, v4, and
    v5 contracts where applicable.
38. Parallel policy v6 closes canonical-order starvation among stable
    candidates that are individually compatible with the primary but mutually
    conflict. Conflicts with the fixed primary remain non-ageing; conflicts
    only with an admitted sibling are recorded as `sibling_conflict_queue` and
    accrue durable, sealed deferrals. Exhaustive clique tests for populations
    two through six establish first service within the declared bound plus
    cohort size, and the existing durable SQLite/migration test now exercises
    sibling-conflict rotation. Machine `outcome_code` values drive current
    fairness state; the transition emits the typed code directly, replay
    independently checks it against policy and explanation, and prose parsing
    remains only for older policies or validation diagnostics.
39. Aggregate allocation no longer reserves tokens for future work that cannot
    consume them. Policy v6 remains replay-frozen. For each protected
    candidate, policy v7 projects the
    deterministic greedy continuation conditional on its admission, enforcing
    budget authorization, ownership conflicts, total capacity, and class
    capacity before summing future unprotected demand. Tests cover unauthorized
    rows, a research action excluded by the selected verifier, and candidates
    beyond the remaining wave capacity.
40. Policy v7 removes the manually curated identity-field blind spot. It
    retains the legacy routing/object prefix for conflict semantics and appends
    a canonical SHA-256 commitment to every stable action field except budget,
    operational placement, and recursive post-admission bindings. Prompt-bearing
    `reason` text is committed because it can determine the exact search query. Tasks differing
    only in a previously unregistered exact query now remain distinct and
    input-order invariant. Since a v6 counter cannot prove which new task it
    represents, the identity epoch resets those counters rather than assigning
    them heuristically; v4--v6 traces remain replayable under their own rules.
41. Shared live/replay code is no longer the only guard against semantic drift.
    Import-time conformance commitments freeze parallel policies v3--v25 and
    generic decision policies v4--v8 over canonical mandatory-constraint,
    policy-tier, bounded-deferral, tie-break, ownership-conflict, authorization,
    capacity, allocation, committed-row schema, candidate-indexed nested-trace,
    and generator-manifest scenarios. All five generic epochs now have distinct
    executable trace-contract digests. Editing an existing transition without
    updating its explicit commitment fails immediately even if generation and
    replay were edited together.
42. CI now compares each scheduler policy contract and the candidate-generator
    graph contract with the pull-request base or previous pushed revision.
    Published version/digest pairs may not be removed or changed; versions must
    remain a contiguous append-only sequence; and the active selector may
    advance but not retreat. The guard parses source without importing it, fails
    closed on unreadable Git objects, and has a real temporary-repository
    regression. This protection depends on the workflow being a required check;
    an administrator who controls both repository history and CI is still
    outside the trust model.
43. Parallel policy v8 distinguishes a serializable primary-ownership conflict
    from a permanent structural exclusion. Only the former accrues authenticated
    waiting time. When its three-wave bound is reached, a separate registered
    leader comparison may promote it only if the scheduled primary is
    nonmandatory and both actions occupy the same policy tier. The first
    promotion bootstraps an authenticated leader cohort; subsequent rotations
    use the ordinary candidate-indexed decision state so nonselected peers do
    not lose their waiting time when the leader changes. The workflow discards
    the old companion set and reruns every enabled companion and multi-branch
    generator under the promoted leader using the same scheduler snapshot.
    Four-candidate bounded-service, mandatory/tier exclusion, legacy-v7 replay,
    exact trace validation, and full-regeneration tests pass. This is a
    conditional service result, not global wait-freedom.
44. Candidate-generator graph v5 corrects the producer provenance of the
    scheduled-primary row in the parallel-leader comparison. Graph v4 had
    attributed both leader families to `_parallel_leader_candidate_actions`,
    although that helper emits only serialized candidates. The scheduled row
    now comes through the separately declared
    `_scheduled_parallel_leader_action`; exact AST producer coverage and the
    new whole-graph digest pass, while graph v4 remains immutable and
    replayable.
45. The executable-mode contract now includes `regulate_decomposition`, which
    was already emitted by the obligation scheduler, budgeted, assigned to the
    mathematical advisor, and supported by context construction, but was
    rejected by the authoritative dispatch table. A real store-level dispatch
    regression now commits that mode. The append-only action contract is now
    at v5: v1 declares executability, budget class, and role class; v2 commits
    pure actor-role routing; v3 checks resource-allocation arithmetic; v4
    distinguishes direct proof construction from strict verification when both
    use `prove`; and v5 types the requested limit separately from the granted
    allocation. Budgeting, literature
    search, generic selection, role routing, leader eligibility, workflow
    dispatch, and authoritative persistence consume it. Its semantic vector,
    derived sets, literal scheduler emissions, and invalid-input behavior are
    guarded, and every new decision trace persists the exact contract version
    and digest. The leader promotion boundary also refuses unknown modes and
    empty or noncanonical targets before they can displace a valid primary.
46. Durable dispatch now validates the reported remaining and reserved
    allocation against the authenticated planning state, enforces total and
    non-verification limits across the complete group, and refuses deterministic
    completion telemetry without a prior dispatch, executor-attempt claim, and
    durable result. Before executor entry, the attempt boundary verifies the
    exact dispatched action, routing, revision, role, model profile, and the
    bounded context manifest's semantic hash; result persistence rechecks the
    claimed plan hash. Completion must use the result's reserved run identifier and
    exact normalized token usage, timing, execution configuration, context,
    strategy, failure classification, and derived final status. Only artifacts
    attached by an accepted result patch are attributed as authenticated run
    outputs. A group must contain exactly
    the primary and companions admitted by its parallel-wave trace. Mathematical
    strategy enrichment and work-mode selection occur before admission; the
    invariant checker reconstructs each admitted input and rejects subsequent
    mutation. Only the operational companion index is added afterward.
47. Parallel policy v9 replaces the greedy companion prefix with a
    deterministic fixed-width beam search over the complete materialized wave.
    Its lexicographic objective first serves authenticated overdue candidates,
    then maximizes the sum of fixed host admission weights and useful
    parallelism subject to ownership, class, total-capacity, and token
    constraints. An admissible v8 execution is evaluated as an executable
    lower bound, so a pruned beam can improve but cannot regress under the
    declared objective. The wave identifier commits the algorithm, beam width,
    expansion/pruning counts, objective values, selected policy and rows, and
    the explicit fact that no model self-score was used. Replay recomputes that
    evidence exactly. Exhaustive comparison over 100 random small conflict
    graphs, 30 pruned 100-candidate comparisons against v8, a constructed
    greedy counterexample, metadata-tamper tests, and a heterogeneous
    2,000-candidate latency gate exercise this policy. This optimizes resource
    admission, not long-horizon mathematical search or proof quality.
48. Store migration v20 removes two accumulated-history scans from dispatch.
    Primary assignments have a partial unique expression index on experiment
    and assignment-unit identifiers. Duplicate-unit and fixed-design checks
    use indexed point lookups; companions use the existing dispatch-group
    index. The unresolved-wave boundary uses the authenticated latest dispatch
    source entry and then checks only that indexed group; the inductive
    invariant forbids an older unresolved group behind a newer one. The
    restart-recovery lookup uses the same authenticated tail instead of
    searching accumulated dispatch history. The
    complete cohort and history are still replayed during explicit audit.
    Tests verify both SQLite query plans, reject duplicate units and design
    drift, detect missing indexes, and repair altered v19 indexes during
    migration.
49. Randomized-assignment protocol v2 makes the assignment unit a complete
    workflow rather than one dispatch group. Every new wave binds the same
    arm to its exact candidate set and action under a contiguous exposure
    index. The assignment is reconstructed from the latest valid certificate
    after restart; retries reuse an uncommitted index, whereas a committed
    wave advances it. Store migration v21 uniquely indexes experiment, unit,
    and exposure while retaining protocol-v1 one-group uniqueness. Online
    insertion and full-history audit reject gaps, duplicates, arm changes,
    and deterministic or differently assigned waves after activation.
50. Parallel policy v10 retains v9's bounded search and executable v8 lower
    bound, and additionally records the greatest admissible objective bound
    among every frontier state discarded by beam truncation. The selected
    objective and this replayed upper bound form an optimality certificate:
    equality proves global optimality under the declared host objective;
    otherwise the trace says `bounded_approximation` and exposes the bound
    rather than implying an unqualified optimum. Policy v9 remains replayable
    with its historical metadata.
51. Randomized-block assignment protocol v3 and experiment protocol v6 close
    the scheduler-condition/runtime join. Every arm occurs exactly once per
    problem/repeat block, and its workflow certificate commits the exact problem
    bytes, policy semantics, candidate set, action, and contiguous exposure
    index. The preregistered schedule fixes all arm-to-run mappings, problem and
    prompt digests, budgets, and stopping rules. A role-separated authority signs
    a post-registration randomness
    receipt; block seeds are deterministically derived from that value. The
    archive replays complete decision traces and action preimages, verifies the
    registered policy on every wave, and requires a trace-finalization digest
    attested by a role-separated execution-trace auditor whose signature also
    binds the exact finalized independent-grade file. Condition-blind graders
    sign only the condition-free grading-artifact manifest and grading
    attestation. Identifier reuse,
    locally chosen seeds, incomplete blocks, trace truncation, and locally
    rehashed forgeries have adversarial regressions.
52. Parallel policy v11 repairs the resource-feasibility blind spot in v10's
    search transition. V10 charged the full request immediately and could
    certify one selected task as exact even when two tasks could both receive
    the supported minimum useful grant. V11 searches over minimum-feasible
    grants, retains the replayed lower and upper certificates, and distributes
    residual reserved and shared tokens by deterministic integer max--min
    allocation after fixing the companion subset. Historical v10 traces retain
    their exact full-request semantics. A constructed two-task counterexample
    and randomized exhaustive budget/capacity oracles check feasibility,
    selected value, and the reported upper bound.
53. Parallel policy v12 strengthens the branch-and-bound relaxation itself.
    Its suffix dynamic program respects each remaining class capacity and the
    global exclusion between verification and integration while continuing to
    relax exact route, target, and token conflicts. This remains an admissible
    upper bound but is substantially tighter: the heterogeneous 2,000-candidate
    fixture now proves `(24, 3400, 6, 0)` optimal instead of reporting the loose
    v11 upper bound `(24, 3600, 6, 0)`. Random exhaustive conflict-graph oracles
    verify that the new bound contains the true optimum, and v11 remains
    immutable for replay.
54. Parallel policy v13 closes the remaining resource blind spot in that
    relaxation. It excludes candidates that are unauthorized, intrinsically
    below the minimum useful allocation, or incompatible with the fixed primary;
    its suffix dynamic program jointly tracks total positive-token selections,
    selections restricted to the shared pool, and the exact minimum-token
    decrement in the fourth objective coordinate. A 40-candidate counterexample
    improves from the v12 bound `(0, 600, 6, 0)` to the exact v13 certificate
    `(0, 200, 2, 0)`. A mixed-class resource fixture also removes an impossible
    10,000-token remainder. Random exhaustive resource/conflict oracles cover
    unauthorized rows, subminimum requests, both resource pools, ownership
    conflicts, and every objective coordinate; v12 remains immutable for replay.
55. Parallel policy v14 adds route-clique and certification-target-clique
    partitions to the admissible suffix bound. The 100-candidate same-route
    research instance now proves its exact value `(4, 100, 1, 0)` after two
    state expansions instead of retaining v13's safe `(24, 600, 6, 0)` bound.
56. Parallel policy v15 evaluates each clique partition under the applicable
    verification-or-integration regime instead of intersecting that exclusion
    only after scalar optimization. This tightens overlapping certification
    instances while leaving v14 replay semantics unchanged.
57. Parallel policy v16 also enforces class capacities inside each clique
    partition and adds two valid mixed-route partitions, respectively merging
    same-route certification actions with research and adversarial cliques. A
    12-candidate conflict instance tightens from v14's `(18, 1500, 5, 0)` and
    v15's `(18, 1400, 5, 0)` upper bounds to the exact
    `(16, 1000, 4, 0)` certificate. Random exhaustive conflict/resource oracles
    preserve bound safety for every epoch.
58. Parallel policy v17 quotients equal-value partial states with the same
    future structural-conflict projection. It retains the lexicographically
    least candidate-id tuple and keeps exact full identities only while an
    identical suffix candidate remains, so the quotient preserves feasible
    continuations and canonical tie-breaking. On a 48-candidate payload-
    distinct repetition, v16 selected the true `(24, 1000, 4, 0)` value but
    certified only `(28, 1500, 5, 0)`; v17 proves the exact value after 216
    expansions and 42 state identifications.
59. Parallel policy v18 indexes the exact pairwise conflict relation as suffix
    bitsets and identifies partial states by their complete blocked suffix,
    class counts, resource pools, and objective value. This covers distinct
    structural labels with identical feasible continuations. On a synthetic
    capacity-eight, 13-candidate stress case, v17 selected `(30, 2600, 5, 0)`
    below the exhaustive optimum `(36, 1800, 6, 0)`; v18 reaches and certifies
    the optimum. Capacity eight is outside the live scheduler's maximum of
    seven, so a separate minimized live-capacity fixture is the production
    regression: v17 selected the true `(30, 2300, 5, 0)` optimum but could
    bound it only by `(36, 1500, 6, 0)`, whereas v18 certifies equality after
    204 expansions and 34 state identifications. The indexed masks match the
    authoritative pairwise predicate on randomized identities.
    Exact-neighborhood indexing is capped at 4,096 candidates to bound bitset
    memory; larger waves use v17's structural quotient. Small waves use a
    128-state frontier while larger waves keep the 64-state bound.
60. Parallel policy v19 distinguishes objective optimality from canonical
    tie-breaking. V18 pruned every state whose objective upper bound equalled
    the incumbent, so it could certify the four-coordinate optimum while
    missing the lexicographically least optimal candidate-ID tuple. A minimized
    five-candidate live-capacity instance reproduces the defect. V19 retains
    equal-objective bounds on waves of at most 128 candidates, evaluates every
    terminal state before pruning, and lets an equal-valued v8 lower bound
    replace a lexicographically larger result. Certificate v11 records the tie
    rule, whether equality retention ran, how many incumbent-equal states were
    pruned, and whether canonical selection is proved. On larger waves, strict
    pruning preserves measured latency and the trace explicitly reports
    canonicality as unproved when necessary. Random exhaustive conflict and
    protected/shared-resource oracles verify both the objective and candidate-ID
    tuple on small waves; v18 remains replayable.
61. Parallel policy v20 replaces size-limited equality retention with a suffix
    lower bound on the candidate-ID tuple. Dynamic programming computes the
    lexicographically least subsequence for every suffix and every selectable
    cardinality (at most the candidate population, even if a direct caller
    supplies an excessive capacity). An incumbent-equal state is discarded only
    if that optimistic tuple cannot improve the incumbent. Beam truncation binds
    both the greatest discarded objective and the least candidate-ID tuple at
    that objective. Certificate v12 proves global canonicality when the selected
    objective meets its upper bound and no discarded tuple can beat it. This
    restores canonical certificates on the 2,000-candidate benchmark shapes
    without retaining all equal-objective states. A 10,000-case independent
    exhaustive campaign, including 1,412 forced truncations and protected/shared
    resources, found no false objective or canonical certificate. V19 remains
    replayable.
62. Parallel policy v21 adds a proved partial-state dominance relation. At the
    same search layer, a retained state dominates another only if it uses no
    more total or per-class capacity, has at least as much of each protected and
    shared token pool, blocks a subset of the exact suffix conflict neighborhood,
    and has a lexicographically no-worse objective; equality also requires a
    no-worse candidate-ID tuple. Applying an identical continuation therefore
    preserves feasibility and cannot improve the removed state. Pairwise
    dominance runs only on waves of at most 128 candidates or when the current
    post-quotient frontier has at most 32 states, avoiding the 4.3x regression observed when
    the first unconditional prototype scanned every 2,000-candidate frontier.
    With a four-state frontier, a 16-candidate exhaustive counterexample moves
    from v20's unresolved `(32, 1500, 6, 0)` upper bound to the exact selected
    value `(30, 2200, 6, 0)` after two dominance reductions. Certificate v13
    records whether the reduction ran and its count. V21 also caps the
    candidate-ID suffix table at cardinality 32; larger cardinalities receive a
    conservative empty-tuple lower bound. This bounds direct-call memory while
    preserving soundness and has no effect on the live capacity of at most
    seven. V20 remains replayable.
63. Parallel policy v22 adds a certificate-triggered best-first completion
    phase. It starts only when the beam's replayable objective bound exceeds its
    selected value or its canonical lower bound can still beat the selection.
    The queue is ordered by the existing admissible objective and candidate-ID
    bounds, quotients exact future-equivalent states, and expands at most 20,000
    states. Queue exhaustion is an exact proof; limit exhaustion reports the
    greatest remaining objective bound and least associated candidate-ID bound.
    A deterministic default-width 129-candidate fixture improves from v21's
    `(34, 5200, 6, 0)` against `(36, 3900, 6, 0)` to the exact
    `(36, 3900, 6, 0)` after 484 expansions. A separate one-state-frontier
    fixture improves the selected objective itself from `(26, 4200, 6, 0)` to
    exact `(30, 3000, 6, 0)`. A 10,000-case independent oracle exercised 140
    completions, including 76 deliberately state-limited frontiers, and found
    no false objective or canonical certificate. V21 remains replayable.
64. Parallel policy v23 removes individually infeasible candidates before
    optimization while retaining them in the outcome trace. The filter covers
    authorization, fixed-primary conflicts, classes already at capacity,
    subminimum positive requests, and insufficient protected/shared availability
    after the primary. Search population, beam-width selection, conflict masks,
    equivalence signatures, suffix bounds, and completion search now depend only
    on candidates that can individually participate. Inserting 154 infeasible
    rows leaves the selected set, bound, beam width, and expansion count
    unchanged. A 10,000-case conflict/resource oracle filtered 25,466 rows and
    found no false certificate. V22 remains replayable.
65. Parallel policy v24 preserves every non-pruned state discarded by beam
    truncation and starts certificate-triggered best-first completion from that
    disjoint frontier instead of restarting at the root. Regions removed by an
    admissible bound, exact future equivalence, or exact dominance need no
    representative; all other unexplored branches have exactly one frontier
    ancestor. The default-width 129-candidate regression retains the same exact
    `(36, 3900, 6, 0)` result while completion falls from 484 to 91 expansions.
    The one-state-frontier regression falls from 15 to 6 expansions; with a
    six-state limit v23 remains unresolved while v24 is exact. A 10,000-case
    exhaustive conflict/resource campaign exercised 2,225 truncated beams, 264
    completions, and 100 deliberately state-limited residual frontiers without
    a false objective or canonical certificate. V23 remains replayable.
66. Parallel policy v25 caps the retained completion frontier at 20,000 states.
    While the cap is respected, it uses v24's faster disjoint frontier. If the
    cap is exceeded, it releases that cache and falls back to v23's root search,
    preserving the fixed expansion limit and conservative residual certificate
    instead of allowing hidden memory growth. The trace binds retained size,
    total discarded-state count, limit, overflow flag, and selected source. A
    second 10,000-case exhaustive campaign varied frontier limits 1, 2, and
    20,000; it exercised 354 overflows and 48 triggered root fallbacks across
    2,321 truncated beams without a false objective or canonical certificate.
    V24 remains replayable.

## Performance result

The latest hard-gate run used 100 ordinary iterations, 1,000 complete durable
scheduler lifecycles, and 10--12 iterations for each dense/2,000-item shape.
Including proof-revision and policy-head stability checks, ordinary
`next_action` measured 8.60 ms at p95; parallel-wave planning measured 10.04
ms. Compact fairness lookup over 64 candidates measured 0.0132 ms p95; the
legacy compatibility replay over 64 candidates and 96 trace rows measured 1.77
ms. Every final-50 decision, dispatch, attempt, result, and completion tail
remained below its unchanged 25/20/10/10/15 ms hard gate. Accumulated control
history did not produce decision-tail growth in this test. Before v15, a
300-cycle diagnostic reached 125.64 ms dispatch, 57.63 ms attempt, and 56.71 ms
result p95 and took about 92 seconds. The invariant-valid 2,000-item wide and
deep graphs measured 227.00 and 300.72 ms p95.

The dense verification, evidence, and obligation fixtures measured 177.82,
53.73, and 191.14 ms p95 respectively; their trace validation and bounded
history replay also remained below the unchanged hard gates. The v25
heterogeneous 2,000-candidate admission search measured 220.49 ms
p95, expanded 13,748 states, retained at most 64 states per layer, and certified
the selected objective `(24, 3400, 6, 0)` against the equal upper bound
`(24, 3400, 6, 0)`. The resource-constrained 2,000-candidate fixture measured
69.39 ms p95, expanded 202 states, and certified `(8, 1200, 2, 0)` against the
same upper bound. The 2,000-candidate same-route clique measured 30.53 ms,
expanded two states, and certified `(4, 100, 1, 0)`. A 2,000-candidate repeated-
projection fixture measured 205.77 ms, identified 1,993 equivalent states,
applied 500 dominance reductions, and
certified `(24, 1000, 4, 0)`. The 12-candidate, live-capacity exact-neighborhood
counterexample measured 5.40 ms, applied eight dominance reductions, and
certified `(30, 2300, 5, 0)`. All five
objective and canonical-selection certificates are unconditional hard gates.
The heterogeneous case remains below the 350 ms gate. It retained 881 pruned
frontier states, well below v25's 20,000-state memory cap; the other four
retained none, and completion was not triggered on any of the five. Before the
quadratic membership/index fixes, dense enumeration measured about 571 ms;
before the graph-index and ordering fixes, one sparse 2,000-item decision did
not complete in 60 seconds.
This is a scheduler microbenchmark, not evidence about proof success or
mathematical ability. Run the checked benchmark with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 agents/generation/benchmarks/benchmark_scheduler.py \
  --iterations 100 --warmup 10 --max-p95-ms 10 \
  --max-wave-p95-ms 20 --max-history-p95-ms 20 \
  --max-durable-fairness-p95-ms 1 \
  --dispatch-iterations 1000 --max-durable-dispatch-p95-ms 20 \
  --max-dispatch-attempt-p95-ms 10 --max-dispatch-result-p95-ms 10 \
  --max-durable-decision-tail-p95-ms 25 \
  --max-durable-dispatch-tail-p95-ms 20 \
  --max-durable-attempt-tail-p95-ms 10 \
  --max-durable-result-tail-p95-ms 10 \
  --max-durable-completion-tail-p95-ms 15 \
  --large-state-claims 2000 --large-state-iterations 12 \
  --deep-state-claims 2000 --deep-state-iterations 12 \
  --dense-verification-routes 2000 --dense-verification-iterations 10 \
  --dense-evidence-objects 400 --dense-evidence-iterations 10 \
  --dense-obligation-objects 1024 --dense-obligation-iterations 10 \
  --dense-parallel-candidates 2000 --dense-parallel-iterations 10 \
  --dense-parallel-resource-candidates 2000 \
  --dense-parallel-resource-iterations 10 \
  --dense-parallel-clique-candidates 2000 \
  --dense-parallel-clique-iterations 10 \
  --dense-parallel-equivalence-candidates 2000 \
  --dense-parallel-equivalence-iterations 10 \
  --dense-parallel-neighborhood-iterations 20 \
  --max-large-state-p95-ms 350 --max-deep-state-p95-ms 350 \
  --max-dense-verification-p95-ms 250 \
  --max-dense-trace-validation-p95-ms 50 \
  --max-dense-history-p95-ms 300 \
  --max-dense-evidence-p95-ms 100 \
  --max-dense-evidence-validation-p95-ms 20 \
  --max-dense-evidence-history-p95-ms 160 \
  --max-dense-obligation-p95-ms 300 \
  --max-dense-obligation-validation-p95-ms 50 \
  --max-dense-obligation-history-p95-ms 400 \
  --max-dense-parallel-p95-ms 350 \
  --max-dense-parallel-resource-p95-ms 350 \
  --max-dense-parallel-clique-p95-ms 100 \
  --max-dense-parallel-equivalence-p95-ms 300 \
  --max-dense-parallel-neighborhood-p95-ms 50
```

### Preregistered v17/v18 calibration workflows

Protocol v2 remains available for exploratory workflow-level arm assignment:
it binds one arm to every wave and maintains contiguous exposures across retry
and restart. A matched v17/v18 calibration must instead use protocol v3. Its
complete block assigns each condition exactly once, binds the exact problem
bytes and preregistered run mapping, and derives its order from a signed
post-registration randomness receipt.
Experiment protocol v6 then joins every registered condition to the full
runtime trace, replays the policy and action, verifies block completeness, and
requires a separate execution-trace auditor to sign the unblinded manifest and
trace-completeness attestation; graders bind a separate condition-free artifact
manifest and remain condition-blind.
Legacy protocol-v1 objects remain limited to one workflow step.

These mechanisms establish integrity relative to independently supplied trust
keys. They do not prove that the randomization authority honestly observed the
named public source, that no undisclosed pilot workload existed, or that the
held-out problems are uncontaminated. A calibration command is an experimental
operation, not a production override or a performance claim.

## Relation to current research

Modern agent-search results support search over multiple alternatives with
environmental feedback rather than a single irreversible greedy branch. LATS
combines language-model proposals with Monte Carlo tree search and external
feedback, while Tree Search for Language Model Agents reports gains from
best-first search under increased test-time computation. AlphaProof and
AlphaGeometry show the stronger mathematical pattern: learned proposals are
coupled to formal or symbolic verification. Agent Lightning separates agent
execution telemetry from later credit assignment. These results motivate the
hybrid boundary here, but do not validate this scheduler on Albilich's task
distribution.

The 2026 comparison bar is substantially higher than scheduler correctness.
LEAP reports 70% on its Lean-IMO-Bench and all 12 Putnam 2025 problems through
informal decomposition, iterative refinement, and continuous Lean feedback.
Seed-Prover 1.5 reports 88% on PutnamBench with agentic reinforcement learning
and compute-efficient test-time scaling. DeepMind's Aletheia description uses a
generator/verifier/reviser loop, explicit failure admission, browsing, and
expert grading. Albilich has no comparable preregistered held-out result, no
live Lean backend in this environment, and no independent expert grading;
therefore neither these latency results nor architectural resemblance support
a mathematical state-of-the-art claim.

Primary sources:

- [Language Agent Tree Search](https://arxiv.org/abs/2310.04406)
- [Tree Search for Language Model Agents](https://arxiv.org/abs/2407.01476)
- [Automated Design of Agentic Systems](https://arxiv.org/abs/2408.08435)
- [AlphaProof overview](https://deepmind.google/blog/ai-solves-imo-problems-at-silver-medal-level/)
- [Agent Lightning](https://arxiv.org/abs/2508.03680)
- [LEAP](https://arxiv.org/abs/2606.03303)
- [Seed-Prover 1.5](https://arxiv.org/abs/2512.17260)
- [Aletheia / Gemini Deep Think](https://deepmind.google/blog/accelerating-mathematical-and-scientific-discovery-with-gemini-deep-think/)
- [OpenAI First Proof submissions](https://openai.com/index/first-proof-submissions/)

## Remaining critical work

1. Extract the remaining document-review and publication-loop action builders
   from the scheduler. `_plan_next_action` is now 69 lines with four returns,
   down from roughly 622 lines and 42 returns at the start of this work; the
   solved-root and open-problem layers are explicit comparisons, but the
   207-line document gate still contains seven phase returns.
2. Establish a stronger liveness result across the declarative conflict graph.
   Every registered stable same-tier cohort and lower-class parallel cohort
   now has a bounded-service property, stable primary-compatible sibling
   conflict cliques rotate under policy v6, and stable materialized same-tier
   serial conflicts with a nonmandatory primary rotate under policy v8 after
   complete regeneration. Structural exclusions, changing inputs, higher
   policy tiers, resource infeasibility, and execution failure remain outside
   an end-to-end termination theorem.
3. Replace the remaining linear immutable candidate rows with a
   content-addressed or Merkle-paged representation. Generator declarations
   and assignment runs are now compact/content-addressed, but database growth
   remains unbounded and a sufficiently large single complete trace can exceed
   patch/output limits.
4. Extend scale tests beyond synthetic wide, chain, dense-verification,
   dense-evidence, and dense-obligation
   graphs: dense multi-parent DAGs, heterogeneous artifact payloads,
   concurrent revision churn, heterogeneous-assurance integration at high
   cardinality, and high-cardinality semantic-coverage checks remain
   unmeasured. The cache is per-process and per-decision, not an incrementally
   maintained database index.
5. Calibrate policy v25's fixed host admission weights, minimum grant, and
   max--min token-allocation rule with
   held-out workload evidence. Protocol v6 now supplies the needed matched-block,
   external-randomness, complete-runtime-trace, role-separated signature, and
   statistical-replay machinery. No such independently operated workload has
   yet been run, so the weights and token-value model remain uncalibrated.
6. Continue adversarial analysis of bounded admission. Policies v17--v25
   close the known repeated-projection and exact-suffix-neighborhood failures,
   including a case where v17's selected value was suboptimal. The problem is
   still a bounded combinatorial search: sufficiently difficult waves may
   honestly retain a nonzero upper-bound gap, especially above the 128-candidate
   wider-frontier range; above 4,096 candidates the exact-neighborhood quotient
   is also disabled to cap bitset memory. No claim of universal exact
   optimization is made. The 20,000-state expansion and retained-frontier caps
   do not constitute a wall-clock bound: descriptor validation, conflict
   projection, suffix relaxations, and per-state bound evaluation still scale
   with candidate count. Policy v25 retains a sound candidate-ID suffix lower
   bound, exact partial-state dominance, and bounded best-first completion,
   but canonicality remains conditional on the recorded certificate: an
   unresolved objective gap or a discarded tuple that may be smaller is reported
   rather than hidden.
7. Evaluate non-greedy long-horizon mathematical tree search behind a fixed
   compute budget and a verifier-derived outcome. Policy v25 searches only the
   current wave's feasible resource subsets and deliberately does not use
   model self-scores as value estimates.
8. Run preregistered, repeated comparisons against the current deterministic
   policy. The executable assignment and audit machinery now exists, but until
   independently registered held-out results exist, “state of the art” is a
   design target, not an empirical conclusion.
9. Reduce the remaining scheduler monolith. Parallel admission is now an
   acyclic standalone module, but `scheduler.py` still has 17,032 lines and 401
   functions; `parallel_admission.py` has grown to 4,909 lines with a
   2,104-line search transition, a separate 69-line dominance reduction, and a
   439-line validator. Its generic 239-line
   resource/clique relaxation is isolated in `parallel_relaxation.py`. Several
   individual planners remain too large for easy local reasoning. The experimental audit
   boundary is also concentrated: `experiment_audit.py` has 3,061 lines and
   `_audit_general_evidence_design` spans 1,352 lines.
10. Replace untyped action dictionaries with a versioned typed action schema.
    Policy v7 commits every stable action field and therefore cannot silently
    omit a new ownership-relevant payload, but its short exclusion list is
    manually classified and an accidental operational field can unnecessarily
    reset fairness identity. Action contract v5 now centralizes modes,
    executability, budget classes, actor roles, and resource-allocation
    invariants and validates them at construction, selection, and dispatch.
    Its version and semantic digest are embedded in every new decision and
    dispatch record. Mode-specific auxiliary payload fields remain untyped.
    Likewise, the
    evaluated/skipped manifest is host instrumentation:
    fail-closed partition checks catch an unlabelled registered family, but do
    not independently observe Python execution or reveal a useful family that
    was never registered.
10. Add a renewable owner lease or equivalent distributed coordinator beyond
    the local execution lock. Migrations v13--v14 close the audited local crash
    windows after result persistence and after accepted patch application,
    preserve partial-wave semantics, bind staged source bytes, reserve result
    run IDs, and pin the resolved built-in executable when available;
    migrations v15--v21 harden integrity and long-history latency. A remote backend can still
    complete work while its reply is lost before the local result record, and
    a custom executor identity is declared rather than cryptographically
    attested. The local file lock is not a distributed lease. Permanent
    ownership conflicts may also prevent service. This is conditional
    fairness, not wait-freedom or universal exactly-once execution.
11. Extend predictive resource admission beyond requested tokens and worker
    counts to aggregate wall time, CPU, process, network, and formal-backend
    capacity. Local Codex and bundled Claude execution now have a committed,
    workflow-wide sampled process-tree RSS ceiling across primary, companion,
    periodic HMT, repair, and stop-writer children, with cross-session
    cancellation and durable peak telemetry. Custom concurrency is declared in
    the execution contract: undeclared executors remain serial and defer the
    asynchronous HMT sidecar, while a parallel executor must accept
    cancellation and the shared governor. That
    reactive supervisor is not a kernel reservation, can miss transient spikes
    or detached descendants, and does not attest unsupervised external limits.
    A token-feasible wave can still overload another shared resource.
12. Add an independent witness for the scheduler input. A v6 wave identifier
    now commits state revision, proof-state and run-provenance hashes,
    capacities, aggregate-budget mode, and initial budget. Replay therefore
    detects local snapshot/configuration tampering, but cannot prove that the
    generator registry was exhaustive or that the committed inputs match an
    independently witnessed external state.
13. Add an audited recovery workflow for a fail-closed, unpaired direct SQL
    scheduler insertion. The source ordinal makes corruption immediately
    visible and prevents later writes from concealing it, but today recovery
    means restoring a checkpoint or performing a privileged manual repair.
14. Consolidate the v9--v21 compatibility branches and exact trigger
    definitions into a declarative migration specification with golden-schema
    tests. The current migrations are tested but increasingly expensive to
    reason about as one unit.
15. Independently exercise protocol v6 outside the synthetic verifier fixture.
    The code now joins registered conditions, authenticated randomization,
    complete workflow traces, and outcomes, but its guarantees remain conditional
    on honest out-of-band authorities and complete disclosure. Reproduce it with
    separately operated registration, randomization, execution, and grading;
    publish contamination checks and all exclusions before making a causal claim.
    Literal condition-name checks do not prove the absence of encoded or
    semantic condition leakage in a solution, and the signed trace receipt is
    still an authority's attestation rather than an external execution witness.
