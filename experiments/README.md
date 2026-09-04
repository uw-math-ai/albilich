# Albilich experiments

This directory preserves historical benchmark inputs and curated run evidence.
Every currently listed archive is classified `historical_unvalidated` in
`archive_status.json`: the runs are useful case studies, but their outcome
labels are not independent grades, their ablations are not repeated matched
trials, and they are not evidence of a general proof-solving success rate.

Future archives may be labelled `protocol_validated` only after the machine
auditor verifies immutable prompts and problem hashes, environment and seed,
complete run/event logs and proof snapshot, artifact hashes, independent
grading, exact identity between the selected and prompted problem, separation
of reference answers from every agent-visible file, independently backed
scoreboard labels, and (for ablations) at least three matched trials per
condition. General or novelty claims newly produced by this repository use
protocol v5: at least two conditions
must occur exactly once in every problem/repeat block; problem, prompt, budget,
stopping rule, and seed must match within a block; condition specifications and
the selection, block-assignment schedule, and analysis plans are
content-addressed; condition order is replayed with rejection-sampled SHA-256
Fisher--Yates; and the reported problem-level contrast and SHA-256-driven
cluster-bootstrap interval are recomputed by the auditor. The auditor also
recomputes the required number of paired problems using the registered
two-sided normal approximation, rather than trusting a self-reported sample
size. Its minimum detectable effect and problem-level standard-deviation
assumption remain explicit design assumptions whose scientific plausibility
requires external review.

Protocol v4 remains supported only for faithful replay of existing archives.
It validates the declared power-analysis fields structurally but does not
recompute the sample size, so a v4 archive must not be described as carrying
the stronger v5 power-design guarantee. Unknown protocol versions fail closed.

Protocol v5 is the generic experiment-evidence format. Scheduler comparisons use
protocol v6, which additionally replays every archived scheduler decision and
the exact dispatched action, verifies that the registered v17/v18 condition
governed every workflow exposure, and requires complete protocol-v3 randomized
blocks. The assignment commits the exact problem bytes as well as its identifier.
A preregistered schedule also fixes the exact run identifier for every arm,
problem and prompt digests, token budget, and stopping rule, preventing an
operator from selecting among extra replicas after observing outcomes.
A finalization record commits the number and digest of all dispatches plus the
event, snapshot, and result hashes. Condition-blind graders sign only the
condition-free grading-artifact manifest and grading attestation; a separate
out-of-band execution-trace auditor signs commitments to the unblinded trial
manifest and the exact finalized independent-grade file, and attests that the
trace is complete and that labels were finalized before trace review.

Protocol v6 does not accept a merely chosen integer seed. The assignment schedule
preregisters a future randomness event. A separate randomization authority signs
the observed randomness after registration, and every 256-bit block seed is
derived from that value, problem identifier, and repeat index. The authority's
public key is an out-of-band trust input and must differ from registration and
grader keys. This is still a trust statement about the named authority and
source, not an independently proved physical-randomness claim.

Protocol v5 also requires an Ed25519 receipt over the preregistration,
selection rule, assignment schedule, grader protocol, rubric, and analysis
plan. Its public key is deliberately not trusted from the archive itself.
Each grader separately signs the complete label map together with the rubric
and registration receipt. Supply the independently held keys with:

```bash
python -m agents.generation.phase2.experiment_audit \
  --experiments-root experiments \
  --trusted-registration-key /independent/custody/registration-public.pem \
  --trusted-randomization-key /randomization/custody/public.pem \
  --trusted-trace-key /trace-audit/custody/public.pem \
  --trusted-grader-key /grader-a/custody/public.pem \
  --trusted-grader-key /grader-b/custody/public.pem
```

A valid receipt proves that the named custodian signed the registered bytes; it
does not prove that no undisclosed pilot runs preceded registration. That
limitation must remain in any empirical claim. General-evidence labels also
require two distinct out-of-band Ed25519 grader keys; names and boolean
`independent` fields inside the archive are not treated as authentication.
Literal condition identifiers are rejected in grading artifacts and evaluation
identifiers, but encoded or semantic condition leakage remains a procedural
blinding risk rather than something this file format can prove absent. No
current checked-in archive uses protocol v6 or supplies held-out evidence for
the scheduler's fixed weights or allocation rule.

Raw child-session logs, session identifiers, transient SQLite files, and local
absolute paths are deliberately excluded from this public archive.

## Included experiments

The [AAAI-27 final-paper data index](aaai27-final-paper/) is itself historical
and unvalidated. Its mappings and dashboard screenshot are retained for audit,
not endorsed as causal or independently verified claims.

| Experiment | Configuration | Wall clock | Active backend compute | Tokens | Historical run label |
| --- | --- | ---: | ---: | ---: | --- |
| [Kourovka 17.91, CAS on](kourovka/17.91/cas-on-1h/) | GPT-5.6 Sol, xhigh, one-hour benchmark | 1h 0m 13s | 1h 30m 17s | 5,250,897 | Certified partial progress |
| [Kourovka 17.91, CAS off](kourovka/17.91/cas-off-1h/) | GPT-5.6 Sol, xhigh, one-hour benchmark | 1h 3m 40s lifecycle | 1h 30m 11s | 9,981,614 | Certified partial progress |
| [RealMath Math_arXiv](benchmarks/realmath-matharxiv-10/) | GPT-5.6 Sol, xhigh, CAS enabled | — | — | about 28.1M | 10/10 `solved_final`; 9 clear reference matches and 1 equivalence review |
| [Kourovka 21.142](kourovka/21.142/) | GPT-5.6 Sol, xhigh | 5h 51m 23s | 6h 48m 48s | 29,684,464 | Exact solution certified |
| [Kourovka 21.142, advisor off](kourovka/21.142/advisor-off-study-20260727/) | GPT-5.6 Sol, xhigh, `ALBILICH_ADVISOR_ENABLED=0` | — | 10h 26m | 54.9M | Unsolved at operator stop; 18 verified claims but no root route |
| [Kourovka 20.2](kourovka/20.2/) | GPT-5.6 Sol, xhigh | 1h 16m 6s | 1h 39m 43s | 6,714,757 | Stronger theorem certified |
| [Kourovka 20.2, advisor off](kourovka/20.2/advisor-off-5h-20260727/) | GPT-5.6 Sol, xhigh, `ALBILICH_ADVISOR_ENABLED=0` | 1h 46m 48s | 2h 8m 20s | 6,306,998 | Same stronger theorem certified with zero advisor runs |
| [Problem 20.2, complete \(\operatorname{PSL}_2(q)\) classification](kourovka/20.2/psl2-classification/) | Albilich proof-state database | — | — | — | Exact classification |
| [Problem 20.2, complete \(\operatorname{PSL}_3(q)\) classification](kourovka/20.2/psl3-classification/) | Revision 1356 | 110h 5m 12s | 80h 3m 52s | 378,602,459 | Exact classification |
| [Problem 20.2, complete \(\operatorname{PSL}_4(q)\) classification](kourovka/20.2/psl4-classification/) | Extracted from revision 610 | — | — | — | Empty survivor list proved |
| [Problem 20.2, broad \(\operatorname{PSL}_n(q)\) study](kourovka/20.2/psln-revision-610-study/) | Revision 610 | 30h 56m 53s | 30h 0m 32s | 154,772,501 | Certified partial progress; root unsolved |

Wall clock is the run-lifecycle measurement printed by Albilich. Active backend
compute is the sum of child-session wall times and can exceed wall clock when
branches run in parallel. Token counts are gross recorded model tokens
(`input_tokens + output_tokens`), including cached input.

Every leaf directory contains a `SHA256SUMS` file covering its public artifacts.
Run `python -m agents.generation.phase2.experiment_audit` through the test suite
to check registry coverage, archive checksums, and the stricter future protocol.
