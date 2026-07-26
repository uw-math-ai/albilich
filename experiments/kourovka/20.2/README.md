# Kourovka Notebook Problem 20.2 — experiment series

This directory contains the original advisor-on run and a controlled rerun with
the PhD-advisor role disabled. Both use the byte-identical original Problem
20.2 input and both certify `PSL(2,7)` as a totally 3-closed nonabelian simple
group of Lie type.

## Original advisor-on run

- Model: `gpt-5.6-sol`
- Reasoning effort: `xhigh`
- Recorded child runs: 23
- Lifecycle wall clock: 1h 16m 6s
- Active backend compute: 1h 39m 43s
- Peak child memory: 381.2 MB

Albilich reported a verified stronger theorem at revision 44: an explicit
nonabelian simple group of Lie type satisfying the target property. Four claims
were verified and integrated. The full proof and the residual ledger debt are
preserved in `report.md`.

The original run used four `phd_advisor` sessions. Its curated archive remains
at this directory's top level.

## Advisor-off ablation

The [advisor-off five-hour-cap rerun](advisor-off-5h-20260727/) preserved the
model, problem, research mode, search policy, and three-branch configuration,
while setting `ALBILICH_ADVISOR_ENABLED=0`. It recorded zero advisor sessions
and solved the same root with the same explicit witness in 1h 46m 48s.

| Measurement | Advisor on | Advisor off |
| --- | ---: | ---: |
| Lifecycle wall clock | 1h 16m 6s | 1h 46m 48s |
| Active backend compute | 1h 39m 43s | 2h 8m 20s |
| Reported tokens | 6,714,757 | 6,306,998 |
| Recorded runs | 23 | 18 |
| Advisor runs | 4 | 0 |
| Outcome | `PSL(2,7)` certified | `PSL(2,7)` certified |

This single paired comparison demonstrates successful completion without the
advisor; it does not establish a general causal effect.

## Original-run contents

- `problem.md`: exact problem statement and run instructions.
- `report.md`: complete report, including the final proof.
- `metrics.json`: aggregate run measurements.
- `evidence/`: deduplicated proof, CAS, integration, and verifier artifacts.
- `SHA256SUMS`: integrity manifest.

The advisor-off rerun has its own README, metrics, evidence, and checksum
manifest in `advisor-off-5h-20260727/`.
