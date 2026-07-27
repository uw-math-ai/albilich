# PhD-advisor ablation — Kourovka 21.142

**Date:** 2026-07-27

**Result:** the advisor-off arm had not solved the problem when the operator
stopped it after 10.44 hours of active compute, or 1.53 times the baseline's
solve time. The advisor-on baseline solved.

This is a matched-model, single-variable study of the `phd_advisor` role. It
does not establish that an advisor-free run could never solve the problem.

## Method

The ablation used a fresh initialization from the byte-identical problem file.
The following settings matched the baseline:

- model: `gpt-5.6-sol`
- reasoning effort: `xhigh`
- token budget: 80 million
- verification reserve: 12 million
- maximum reduction depth: 4
- completion policy: `full_proof_first`
- root-statement SHA

The only intended difference was `ALBILICH_ADVISOR_ENABLED=0`. Gated scheduler
branches fell through to the next eligible action, so advisor opportunities
were reallocated to other roles rather than recorded as skipped no-ops. The
ablation recorded zero advisor sessions across all 110 child runs.

The operator-specified allowance was twice the baseline's 6.81 hours of active
compute, or 13.6 hours. The run was stopped at 10.44 hours, before that cap.

## Results

| Measurement | Advisor off | Advisor on |
| --- | ---: | ---: |
| Root status | active / untested | integrated / informally verified |
| Routes concluding root | 0 | 1 |
| Child runs | 110 | 80 |
| Active compute | 10.44 h | 6.81 h |
| Raw recorded tokens | 54.9M | 29.7M |
| Budget charged | 9.67M | 6.00M |
| Claims / verified | 20 / 18 | 11 / 10 |
| Patch-rejection rate | 8% | 1% |
| Advisor sessions | 0 | 12 |
| Researcher sessions | 55 | 26 |
| Strict-verifier sessions | 22 | 13 |
| Integration-verifier sessions | 19 | 10 |
| Villain / literature sessions | 10 / 4 | 9 / 8 |

## Finding: assembly, not local productivity

The advisor-off arm was not short of accepted mathematics. It produced 80%
more verified claims than the baseline needed, using 1.85 times the raw tokens
and 1.53 times the active compute, but none of its 16 integrated routes
concluded the root.

The baseline followed a connected CFSG family sweep: outer-coset decomposition
normalizers for the projective linear, symplectic, unitary, and orthogonal
families; Borel–Tits; a monolithic wreath reduction; an alternating-group
obstruction; and terminal simple-factor exclusion. Those results formed one
proof spine ending at the root.

The advisor-off arm instead accumulated locally scoped results, including
several `PGL(2,9)` special cases. At the stop it had five separate blocking
frontiers: a \(C_5\) interface, a monolithic bridge, simple groups with 5
divisors, the sporadic case, and an alternating-family bridge. Its patch
rejection rate improved during the run, from 17% early to 8% overall, so the
observed failure was not simply low-quality local work. The accepted pieces
were not assembled into a root route.

This run therefore supports the hypothesis that the advisor's contribution on
this problem is global direction and proof assembly. It is evidence from one
paired run, not a general causal estimate.

## Threats to validity

1. There was one run per arm; run-to-run variance is uncharacterized.
2. The ablation stopped at 1.53 times the baseline's solve time, not at the full
   two-times cap. It establishes only that the arm had not solved by the stop.
3. The model and main run configuration matched, so the comparison has no
   intended model confound.

## Reproduction

```bash
ALBILICH_ADVISOR_ENABLED=0 python3 -m agents.generation.phase2.cli run "<problem-id>" \
  --execute --steps 0 --model gpt-5.6-sol --reasoning-effort xhigh \
  --research-mode hard_problem --completion-policy full_proof_first \
  --web-search live --max-wall-sec 49061 \
  --write-report --no-dashboard --no-stop-on-rejection
```

The advisor kill switch was experimental control code and was not merged into
the public mainline.

## Public archive boundary

This package publishes the findings and aggregate comparison only. It excludes
raw child logs, session identifiers, SQLite state, and local absolute paths.
The source findings were recorded in Rethlas-CAS commit
`b46d272d99dd44ed833bce2340e45c3ddcec56f8`.
