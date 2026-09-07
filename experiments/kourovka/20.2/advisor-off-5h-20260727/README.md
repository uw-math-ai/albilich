# Problem 20.2 — PhD-advisor-off ablation

This is the advisor-off rerun of the original Kourovka Notebook Problem 20.2,
not the later restricted `PSL_3(q)` classification task. `problem.md` is
byte-identical to the original input (SHA-256
`18255b205a0a8feb49a81aaca2839dcde6c6fe37923f4c134f43f0fbf1fe5c0f`).

## Configuration

- Model: `gpt-5.6-sol`
- Reasoning effort: `xhigh`
- Research mode: `hard_problem`
- Search: live
- Parallel branches: 3
- Advisor control: `ALBILICH_ADVISOR_ENABLED=0`
- Wall-time cap: 18,000 seconds

The advisor switch reassigns an advisor-only scheduler slot to a researcher
`reduce` pass and guards execution against any escaped advisor action. All
other principal run settings match the original advisor-on experiment.

## Result

Albilich stopped after solving the problem, before the five-hour cap:

- lifecycle wall clock: 1h 46m 48s
- active backend compute: 2h 8m 20s
- recorded child runs: 18
- reported tokens: 6,306,998
- terminal revision: 33
- outcome: stronger theorem certified

The certified explicit witness is `PSL(2,7)`. The proof combines an exhaustive
finite GAP certificate for all 14 proper-subgroup coset actions and all 105
unordered constituent-type pairs with a diagonal synchronization argument.
The strict informal verifier declared the repaired route correct with no gaps,
and the integration verifier integrated it into the root.

This is an internal Albilich verification result, not independent peer review.

## Ablation audit

- `phd_advisor` runs: 0
- advisor-only action-mode runs: 0
- advisor-produced artifacts: 0
- reallocated advisor slots: 1

The generated report's “Advisor / reducer calls” value is an aggregate counter:
its value `2` consists of two researcher `reduce` runs, not advisor sessions.

The terminal database also preserved three active blocking ledger debts despite
the integrated root. One is a stale request for the finite certificate that
was subsequently attached and strictly verified; two belong to an alternative
prime-field route. The public report preserves this discrepancy.

## Comparison with the advisor-on run

| Measurement | Advisor on | Advisor off |
| --- | ---: | ---: |
| Outcome | `PSL(2,7)` certified | `PSL(2,7)` certified |
| Lifecycle wall clock | 1h 16m 6s | 1h 46m 48s |
| Active backend compute | 1h 39m 43s | 2h 8m 20s |
| Reported tokens | 6,714,757 | 6,306,998 |
| Recorded runs | 23 | 18 |
| Advisor runs | 4 | 0 |
| Terminal revision | 44 | 33 |

This is one stochastic paired run. It shows that the system could still solve
this instance without an advisor, but it is not enough by itself to estimate a
general causal effect.

## Contents

- `problem.md`: exact original problem statement and run instructions.
- `run_config.json`: source provenance and run settings.
- `metrics.json`: aggregate role, status, token, and wall-time data.
- `report.md`: generated terminal report.
- `evidence/final_proof.md`: writer's final proof.
- `evidence/finite_cas_certificate.md`: exact GAP code, outputs, and finite
  coverage.
- `evidence/repaired_proof_dossier.md`: proof assembly used by the verifier.
- `evidence/verification_initial_missing_certificate.md`: the verifier's first
  rejection.
- `evidence/verification_correct_no_gaps.md`: successful strict verification.
- `evidence/integration_report.md`: root integration record.
- `SHA256SUMS`: integrity manifest.

Raw child logs, session identifiers, absolute local paths, and SQLite state are
excluded from this public package.
