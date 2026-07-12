# Albilich Research Strategy

The research-strategy layer strengthens mature mathematical search without
changing Albilich's roles, authoritative SQLite proof state, verification
authority, or root-alignment rules. Every strategy decision is derived
deterministically from persisted state. Strategy artifacts are advisory until
ordinary claims, routes, and inferences pass their existing verifier gates.

## Persisted strategy artifacts

| Artifact | Producer | Purpose | Hard limit or gate |
| --- | --- | --- | --- |
| `bridge_lemma_search` | researcher | Forward/backward frontier and sufficiency-prechecked bridge portfolio | 1-3 candidates; 1-2 selected; duplicates and gap-moving candidates rejected |
| `advisor_synthesis` | PhD advisor | Periodic global proof architecture and budget allocation | One decisive missing statement; newest artifact must supersede the prior synthesis |
| `invention_authorization` | PhD advisor | Exceptional permission to invent an auxiliary definition or object | All authorization conditions true; at most 2 candidates and 2 research passes |
| `definition_candidate` | researcher | Bounded candidate lifecycle under one authorization | Only `adopted` after well-defined, nontrivial, proof-relevant checks and an exact root-relevant theorem |
| `conjecture_portfolio` | researcher or villain | Bottleneck-local intermediate conjectures | 1-3 candidates; at most 2 selected; explicit prechecks and falsification plan |
| `proof_compression` | researcher or PhD advisor | Shortest plausible proof skeleton and weakest sufficient bridge | Full history preserved; essential dependency ids must exist |
| `deep_session_report` | researcher | Coherent output from an eligible root-critical long session | Required deliverable fields; no verification authority |
| `cas_experiment_report` | researcher or villain | Decision-oriented experimental mathematics | New reports use `experiment_workflow_version=1` and the complete experiment contract |

All new strategy-specific artifacts use `strategy_schema_version=1`. Historical
CAS artifacts remain readable; a newly scheduled experiment receives the strict
versioned contract.

## Deterministic planning

The scheduler first preserves high-priority verification, integration, writing,
counterexample validation, explicit debt repair, and existing circuit breakers.
For unprotected mature-run actions it may schedule:

1. a selected bridge or conjecture, including a decisive CAS refutation test;
2. proof compression before a due global synthesis;
3. global-synthesis mode on the existing `phd_advisor`;
4. an invention pass only while a persisted authorization remains within both
   candidate and pass budgets.

Global synthesis becomes due from persisted signals such as three substantive
passes without root-relevant progress, multiple routes sharing an obstruction,
claim growth without verified-core growth, a refuted central bridge, repeated
strategic verifier rejection, or the meaningful-action cadence. A fresh
synthesis suppresses stale directives until a new major event or its revision
window expires.

Every scheduled action exposes heuristic score components:

- probability of closing the bottleneck;
- probability of refuting a route;
- expected root progress;
- expected information gain;
- reuse value;
- duplication risk;
- token, wall-time, and verification cost.

The numbers are deliberately labeled as heuristics rather than calibrated
probabilities. When scores are close, work-mode rotation remains the diversity
tie-breaker. Speculative actions never consume the protected verification
reserve.

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
verified complete finite reduction. A researcher-submitted CAS report can
submit a debt repair, but only a verifier can close the mathematical debt.

## Method cards and memory separation

`agents/generation/phase2/method_cards.json` is a reviewed developer-curated
library of proof mechanisms. Retrieval first maps the current problem and
bottleneck to structural features, then ranks cards by structural overlap; it
does not use method cards as theorem evidence. Every returned card includes
known failure modes.

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
support, debts, negative results, selected sources, competing approaches,
budget, and latest synthesis. It cannot inspect unrelated result directories or
self-verify.

Proof compression is an active research operation. It records the minimal root
skeleton, essential facts and routes, unresolved bridges, conditional steps,
unused branches, shortest route, and weakest sufficient new statement. The
database retains all history, while subsequent research/advisor manifests may
reduce the primary claim context to that dependency closure. The weakest
sufficient statement feeds the next bridge search.

## Observability

The Markdown report includes a Research Strategy section with the latest
synthesis, compression, bridge and conjecture portfolios, selected candidates,
selection reason, invention authorization, and current synthesis trigger. The
monitor JSON includes the same `research_strategy` payload. Each workflow action
also exposes its information-gain score components and the synthesis directive
it follows.
