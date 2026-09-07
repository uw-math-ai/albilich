# Kourovka Notebook Problem 21.142 — long run

## Configuration

- Model: `gpt-5.6-sol`
- Reasoning effort: `xhigh`
- Recorded child runs: 80
- Lifecycle wall clock: 5h 51m 23s
- Active backend compute: 6h 48m 48s
- Peak child memory: 237.4 MB

## Result

Albilich reported an exact, verified solution at revision 156. Ten claims were
verified and integrated. The final proof and its certification boundary appear
in `report.md`; the remaining ledger debts are retained in that report rather
than silently discarded.

## Advisor-off study

The [matched-model advisor-off study](advisor-off-study-20260727/) reran the
same problem with `ALBILICH_ADVISOR_ENABLED=0`. It had not solved when stopped
after 10.44 hours of active compute, 1.53 times the baseline's solve time,
despite producing 18 verified claims. None of its 16 integrated routes
concluded the root.

| Measurement | Advisor on | Advisor off |
| --- | ---: | ---: |
| Root outcome | solved | unsolved at operator stop |
| Active compute | 6.81 h | 10.44 h |
| Raw recorded tokens | 29.7M | 54.9M |
| Verified claims | 10 | 18 |
| Routes concluding root | 1 | 0 |
| Advisor sessions | 12 | 0 |

This is one paired run, and the advisor-off arm stopped before its full
two-times allowance. It supports a proof-assembly hypothesis but does not show
that an advisor-free run could never solve.

## Contents

- `problem.md`: exact problem statement and run instructions.
- `report.md`: complete report, including the final proof.
- `metrics.json`: aggregate run measurements.
- `evidence/`: deduplicated proof, source-adaptation, CAS, and verifier artifacts.
- `SHA256SUMS`: integrity manifest.
- `advisor-off-study-20260727/`: public-safe ablation findings and checksum.
