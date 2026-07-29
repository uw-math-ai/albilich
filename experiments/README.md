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
| [Kourovka 21.142, advisor off](kourovka/21.142/advisor-off-study-20260727/) | GPT-5.6 Sol, xhigh, `ALBILICH_ADVISOR_ENABLED=0` | — | 10h 26m | 54.9M | Unsolved at operator stop; 18 verified claims but no root route |
| [Kourovka 20.2](kourovka/20.2/) | GPT-5.6 Sol, xhigh | 1h 16m 6s | 1h 39m 43s | 6,714,757 | Stronger theorem certified |
| [Kourovka 20.2, advisor off](kourovka/20.2/advisor-off-5h-20260727/) | GPT-5.6 Sol, xhigh, `ALBILICH_ADVISOR_ENABLED=0` | 1h 46m 48s | 2h 8m 20s | 6,306,998 | Same stronger theorem certified with zero advisor runs |
| [Problem 20.2, complete \(\operatorname{PSL}_2(q)\) classification](kourovka/20.2/psl2-classification/) | Albilich proof ledger | — | — | — | Exact classification |
| [Problem 20.2, complete \(\operatorname{PSL}_3(q)\) classification](kourovka/20.2/psl3-classification/) | Revision 1356 | 110h 5m 12s | 80h 3m 52s | 378,602,459 | Exact classification |
| [Problem 20.2, complete \(\operatorname{PSL}_4(q)\) classification](kourovka/20.2/psl4-classification/) | Extracted from revision 610 | — | — | — | Empty survivor list proved |
| [Problem 20.2, broad \(\operatorname{PSL}_n(q)\) study](kourovka/20.2/psln-revision-610-study/) | Revision 610 | 30h 56m 53s | 30h 0m 32s | 154,772,501 | Certified partial progress; root unsolved |

Wall clock is the run-lifecycle measurement printed by Albilich. Active backend
compute is the sum of child-session wall times and can exceed wall clock when
branches run in parallel. Token counts are gross recorded model tokens
(`input_tokens + output_tokens`), including cached input.

Every leaf directory contains a `SHA256SUMS` file covering its public artifacts.
