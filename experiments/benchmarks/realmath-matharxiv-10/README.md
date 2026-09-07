# RealMath Math_arXiv benchmark — 10 problems

This archive records a ten-problem RealMath `Math_arXiv` evaluation run with
Albilich using `gpt-5.6-sol`, `xhigh` reasoning, `hard_problem` research mode,
and CAS enabled.

## Reported result

- 10/10 runs reached Albilich's `solved_final` state.
- CAS fired in 10/10 runs.
- About 28.1 million tokens were recorded in total.
- Human inspection found 9 clear matches to the supplied RealMath references.
- Problem 08 remains an explicit symbolic-equivalence review item; its two
  answer forms were not declared equivalent merely from inspection.

The benchmark's `solved_final` field is an Albilich workflow verdict, not an
independent RealMath grade. See `results/scoreboard.md` for the per-problem
evidence boundary.

## Contents

- `problems/`: ten exact benchmark prompts and supplied reference answers.
- `results/scoreboard.md`: per-problem outcome and human comparison.
- `run_bench.sh`: portable sequential runner for the public checkout.
- `benchmark_landscape.md`: contemporaneous benchmark-selection context.
- `metrics.json`: aggregate benchmark record.
- `SHA256SUMS`: integrity manifest.
