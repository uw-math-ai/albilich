# Albilich experiments

This directory collects reproducible benchmark inputs and curated research-run
evidence. Each experiment keeps the exact problem statement, the generated
Albilich report, aggregate run metrics, and the proof or CAS artifacts needed
to audit the reported outcome.

Raw child-session logs, session identifiers, transient SQLite files, and local
absolute paths are deliberately excluded from this public archive.

## Included experiments

| Experiment | Configuration | Wall clock | Active backend compute | Tokens | Outcome |
| --- | --- | ---: | ---: | ---: | --- |
| [Kourovka 17.91, CAS on](kourovka/17.91/cas-on-1h/) | GPT-5.6 Sol, xhigh, one-hour benchmark | 1h 0m 13s | 1h 30m 17s | 5,250,897 | Certified partial progress |
| [Kourovka 17.91, CAS off](kourovka/17.91/cas-off-1h/) | GPT-5.6 Sol, xhigh, one-hour benchmark | 1h 3m 40s lifecycle | 1h 30m 11s | 9,981,614 | Certified partial progress |
| [RealMath Math_arXiv](benchmarks/realmath-matharxiv-10/) | GPT-5.6 Sol, xhigh, CAS enabled | — | — | about 28.1M | 10/10 `solved_final`; 9 clear reference matches and 1 equivalence review |
| [Kourovka 21.142](kourovka/21.142/) | GPT-5.6 Sol, xhigh | 5h 51m 23s | 6h 48m 48s | 29,684,464 | Exact solution certified |
| [Kourovka 20.2](kourovka/20.2/) | GPT-5.6 Sol, xhigh | 1h 16m 6s | 1h 39m 43s | 6,714,757 | Stronger theorem certified |

Wall clock is the run-lifecycle measurement printed by Albilich. Active backend
compute is the sum of child-session wall times and can exceed wall clock when
branches run in parallel. Token counts are gross recorded model tokens
(`input_tokens + output_tokens`), including cached input.

Every leaf directory contains a `SHA256SUMS` file covering its public artifacts.
