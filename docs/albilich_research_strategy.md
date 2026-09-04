# Albilich Research Strategy

The research-strategy layer strengthens mature mathematical search without
changing Albilich's roles, authoritative SQLite proof state, verification
authority, or root-alignment rules. Every strategy decision is derived
deterministically from persisted state. Strategy artifacts are advisory until
ordinary claims, routes, and inferences pass their existing verifier gates.

## Persisted strategy artifacts

| Artifact | Producer | Purpose | Hard limit or gate |
| --- | --- | --- | --- |
| `approach_portfolio` | researcher | Initial and periodic breadth-first map of genuinely different proof, reformulation, experimental, and counterexample mechanisms | 6-12 initial or 3-12 refresh candidates; 2-3 selected; duplicate semantic signatures rejected; no proof authority |
| `bridge_lemma_search` | researcher | Forward/backward frontier and sufficiency-prechecked bridge portfolio | 1-3 candidates; 1-2 selected; duplicates and gap-moving candidates rejected |
| `advisor_synthesis` | PhD advisor | Periodic global proof architecture and budget allocation | One decisive missing statement; newest artifact must supersede the prior synthesis |
| `invention_authorization` | PhD advisor | Exceptional permission to invent an auxiliary definition or object | All authorization conditions true; at most 2 candidates and 2 research passes |
| `definition_candidate` | researcher | Bounded candidate lifecycle under one authorization | Only `adopted` after well-defined, nontrivial, proof-relevant checks and an exact root-relevant theorem |
| `conjecture_portfolio` | researcher or adversarial reviewer | Bottleneck-local intermediate conjectures | 1-3 candidates; at most 2 selected; explicit prechecks and falsification plan |
| `proof_compression` | researcher or PhD advisor | Shortest plausible proof skeleton and weakest sufficient bridge | Full history preserved; essential dependency ids must exist |
| `deep_session_report` | researcher | Delta-bearing fallback when a root-critical long session cannot emit a proof draft | Productive mathematical delta required; no verification authority |
| `cas_experiment_report` | researcher or adversarial reviewer | Decision-oriented experimental mathematics | New reports use `experiment_workflow_version=2`, capture reproducible input and environment data, and require host reproduction before computational evidence can support verification |

All new strategy-specific artifacts use `strategy_schema_version=1`. Historical
CAS artifacts remain readable; a newly scheduled experiment receives the strict
versioned contract.

## Deterministic planning

The scheduler first preserves high-priority retrieval, verification, integration,
writing, counterexample validation, exact non-research obligation handling, and existing
circuit breakers. On a new hard problem, exact source scouting can run in
parallel while the first researcher pass builds an approach portfolio instead
of committing immediately to a local calculation. For unprotected mature-run
actions it may schedule:

1. initial or periodic portfolio brainstorming and a selected low-cost pilot;
2. a selected bridge or conjecture, including a decisive CAS refutation test;
3. proof compression before a due global synthesis;
4. global-synthesis mode on the existing `phd_advisor`;
5. an invention pass only while a persisted authorization remains within both
   candidate and pass budgets.

A local bottleneck receives an evidence-based lease. It may continue without a
wall-clock limit while it produces mathematical deltas. After two completed
passes with no root-relevant mathematical delta, or two consecutive execution
failures, the lock no longer outranks creative/global work: the scheduler
refreshes the portfolio and changes mechanism, representation, or proof
direction. This fixes the former priority inversion in which `debt_id` and
`proof_repair_required` made bottleneck research permanently non-preemptible.

Global synthesis becomes due from persisted signals such as three substantive
passes without root-relevant progress, multiple routes sharing an obstruction,
claim growth without verified-core growth, a refuted central bridge, repeated
strategic verifier rejection, or the meaningful-action cadence. A fresh
synthesis suppresses stale directives until a new major event or its revision
window expires.

Every scheduled action exposes ordinal priority components:

- estimated ability to close the bottleneck;
- estimated ability to refute a proof approach;
- root relevance;
- discriminating value;
- reuse value;
- duplication risk;
- token, wall-time, and verification cost.

These values only order admissible actions. They are not probabilities,
expected utilities, information-theoretic quantities, or Bayesian posteriors.
As the run proceeds, the scheduler updates a local outcome heuristic for each
host-assigned strategy family using later verifier/integration evidence.
Producing prose is not success: credit requires an output artifact to
enter verified evidence, a concrete target claim to be verified, or the worked
approach to integrate. The heuristic weights verified contributions placed in a
sufficient root approach more heavily than isolated local verifications.
Rejections and timeouts are negative evidence. No reference
solution and no private cross-problem run cache is consulted. When scores are
close, work-mode rotation remains the diversity tie-breaker. Speculative actions
never consume the protected verification reserve.

## Brainstorming, creativity, and proof obligations

Brainstorming has a short dedicated researcher prompt rather than the full
local-proof instruction block. Each approach card records its mechanism,
mathematical objects, representation or invariant, exact root consequence,
weakest bridge statement, likely failure, cheapest decisive test, qualitative
contribution level 0-5, cost, novelty, confidence basis, status, and a semantic
signature. The signature spans mechanism, representation, proof direction,
theorem family, root obligation, and failure mode; paraphrases therefore do not
count as creative diversity.

The search state separates three layers:

1. **Ideas** are advisory portfolio entries. They may be numerous, speculative,
   and mutually incompatible.
2. **Research questions** are conceptual, source, counterexample, or experiment
   questions. Up to six decision-changing questions may be recorded as minor
   nonblocking proof obligations once a concrete graph owner exists (major only
   for a selected pilot); the system does not create one obligation per idea.
3. **Proof obligations** are exact requirements on selected claims, proof
   approaches, or inferences. A blocking obligation is created only after a selected approach exposes a
   statement whose proof is actually necessary.

The qualitative allocation is 50% exploitation, 30% exploration, and 20%
adversarial testing. It is a diversity policy, not a calibrated probability or
a relaxation of verification.

## Graph-derived decisive obligation frontier

For every active, unpaused sufficient proof approach near the root, the strategy layer
derives its unresolved premises, unchecked inferences, and active owned obligations.
It chooses the route with the smallest weighted obligation cut and exposes its
highest-severity item as the decisive obligation. This graph calculation does
not trust model-reported root leverage. Research may replace the decisive item
only by a strictly smaller obligation with an explicit implication back to the
selected route.

## Bridge and conjecture discipline

Bridge search uses verified or integrated facts as the forward frontier and
active root/route obligations as the backward frontier. Each candidate records
support, route consequence, hidden obligations, difficulty, root leverage,
methods, falsifiability, and a sufficiency precheck. A route-closing candidate
must outrank a merely interesting side lemma. Existing claim fingerprints and
same-portfolio fingerprints suppress duplicates.

Intermediate conjectures are restricted to bridge conjectures, equivalent
reformulations, sharp special cases, necessary conditions on minimal
counterexamples, and structural explanations of examples. Every candidate must
record root utility, nontriviality, small-example and counterexample checks,
literature status, estimated cost, and duplication status. Equivalent
reformulations must preserve exact hypotheses and quantifiers. Refuted
conjectures retain a negative-result summary.

## Experimental mathematics

New strategic CAS reports follow:

```text
precise obstruction
  -> discriminating experiment
  -> structured observations
  -> candidate pattern
  -> counterexample search
  -> sharpened conjecture
  -> proof attempt
```

The report states the mathematical question, competing hypotheses, finite
scope, method and code, decisive expected outputs, observations,
counterexamples, interpretation, changed research decision, and next proof
move. Computation cannot certify an infinite statement without a separately
verified complete finite reduction. A researcher-submitted CAS report may
provide evidence toward a proof obligation, but only a verifier can discharge
that obligation.

## Method cards and memory separation

`agents/generation/phase2/method_cards.json` is a reviewed developer-curated
library of proof mechanisms. It includes general methods plus domain playbooks
for chief-factor induction, character restriction, extension cohomology,
permutation fixed-point geometry, double counting, probabilistic witnesses,
spectral encodings, generating functions, normal forms, duality, classification
endpoints, and representation switching. Retrieval maps the current problem and
bottleneck to both structural features and domain tags. Every returned card
requires a transfer packet: hypothesis match, object dictionary, reusable proof
moves, failure boundary, and decisive test. Cards remain advisory and never
become theorem evidence.

Manifests keep four categories separate:

1. verified problem facts;
2. external theorem and retrieval cards;
3. developer-curated strategic method cards;
4. private local speculative artifacts.

There is no automatic cross-user or cross-project learning from private runs.

## Deep sessions and compression

Deep sessions are limited to a central bridge, difficult source adaptation,
near-integration route, repeatedly surviving bottleneck, or other high-leverage
branch. The packet contains the exact target and root relation, verified
support, proof obligations, negative results, selected sources, competing approaches,
budget, and latest synthesis. It cannot inspect unrelated result directories or
self-verify. A proof draft is the preferred output. A `deep_session_report` is
only a fallback and must record a productive mathematical delta such as a proved
lemma, verifier-ready proof, refuted conjecture, source adaptation, narrowed
obligation, route-killing obstruction, or decisive counterexample. Two recent
no-delta long sessions suppress another deep session and force a different
research philosophy.

Proof compression is an active research operation. It records the minimal root
skeleton, essential facts and routes, unresolved bridges, conditional steps,
unused branches, shortest route, and weakest sufficient new statement. The
database retains all history, while subsequent research/advisor manifests may
reduce the primary claim context to that dependency closure. The weakest
sufficient statement feeds the next bridge search.

## Representation, sources, verification, and parallel diversity

A repeatedly attacked or root-critical bottleneck receives a representation
switch contract. The researcher compares two to four mathematical languages,
records the object dictionary and the implication/equivalence back to the
original obligation, and chooses only a representation that makes the missing
step strictly simpler.

Literature actions receive a theorem-adaptation contract: exact source location
and statement, local notation and definition translation, full hypothesis map,
checked and missing hypotheses, exact local deduction, reusable moves from the
source proof, and the boundary where transfer fails. Survey-only handoffs do not
satisfy this contract.

Route and integration verification receive a selective proof-interface
checklist for quantifiers, hypothesis propagation, case exhaustiveness,
reduction direction, finite-to-universal overclaiming, and dependency assembly.
A zero-gap verdict requires every interface check to pass. This is deterministic
metadata validation and does not require Lean 4.

Parallel research waves suppress not only duplicate goals and overlapping graph
ownership but also duplicate strategy families. Active workers must pursue
different mathematical philosophies and share concrete cross-branch signals.

## Observability

The Markdown report includes a Research Strategy section with the latest
approach portfolio and bottleneck lease, synthesis, compression, bridge and
conjecture portfolios, selected candidates, selection reason, invention
authorization, and current synthesis trigger. The monitor JSON includes the
same `research_strategy` payload. The dashboard renders every approach with its
possible root contribution, bridge, decisive test, failure mode, cost, novelty,
confidence, and selection status. “Steer to pilot” and “Generate new
approaches” populate the existing human-steering control; they never mutate
proof state silently. Each workflow action also exposes its ordinal
action-priority components and the synthesis directive it follows.

## Proof programs, coverage, and long research sessions

The strategy layer derives a compact proof-program view from ordinary routes
and artifact metadata. A program records its mathematical philosophy, exact
root implication, decisive obligation, validation evidence, reset criterion,
covered cases, and open cases. This is a view over the existing graph, not a new
role, approval gate, or database authority. Advisors compare genuinely
different programs only at evidence-triggered checkpoints: new counterevidence,
repeated research without verifier handoff, semantically duplicate obligations,
uncovered root cases, or multiple mature proof philosophies.

Elapsed time is never a strategy-reset signal. `attempt` defaults to `--steps 0`
with no wall-clock cap, and the long-session workspace points later workers back
to the canonical proof artifact. A coherent proof may continue indefinitely
while it produces or sharpens mathematical deltas. An operator may still impose
an explicit resource cap with `--max-wall-sec`.

Fresh proof-grade evidence marked `proof_candidate` or `ready_for_verifier` is
handed directly to the strict verifier, including repairs to an already
integrated route. Fresh counterevidence propagates to downstream certified
dependencies as `threatened_pending_revalidation`; certification remains
recorded until the strict verifier confirms a repair or a refutation.

Semantically overlapping blocking proof obligations are collapsed into one scheduling
frontier without rewriting their database status. Aliases remain provenance and
only verifier-certified mathematical work resolves them. Reports and metrics
therefore emphasize root-closing programs, terminal root inferences, exhaustive
case coverage, minimal blocking-frontier size, and pending revalidations rather
than artifact counts.

Use `ingest-reference-solution` to attach a human-supplied Markdown, LaTeX,
plain-text, or text-extractable PDF solution to an existing run. The scheduler
reconstructs it in local notation, maps every hypothesis and case, and creates
or repairs the ordinary route/inference. The reference is advisory and never
bypasses strict verification or integration.
