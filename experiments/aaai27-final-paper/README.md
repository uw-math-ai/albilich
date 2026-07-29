# AAAI-27 final-paper data index

This directory maps the quantitative and mathematical claims in
“Albilich: Steerable Proof-State Orchestration for LLM-Based Mathematical
Research with CAS Integration” to the public experiment artifacts that support
them.

The audit used the `Rethlas-CAS` main checkout at
`b46d272d99dd44ed833bce2340e45c3ddcec56f8`. It checked the relevant tracked
benchmark and ablation records, queried all 40 available Albilich proof-state
databases, and searched the main-branch history for the manuscript’s unmatched
values. `paper_data.json` records the result in a machine-readable form.

## Supported paper results

- The CAS-enabled ten-problem RealMath result is archived at
  [`../benchmarks/realmath-matharxiv-10/`](../benchmarks/realmath-matharxiv-10/).
- Both Problem 17.91 runs are archived at
  [`../kourovka/17.91/`](../kourovka/17.91/).
- The Problem 21.142 advisor comparison is archived at
  [`../kourovka/21.142/`](../kourovka/21.142/).
- The Problem 20.2 advisor comparison and the PSL-family results are archived
  at [`../kourovka/20.2/`](../kourovka/20.2/).
- `dashboard.png` is the anonymized revision-1356 monitor screenshot for the
  reported \(\operatorname{PSL}_3(q)\) classification run.

The experiment directories contain the exact prompts, reports, aggregate
metrics, and curated proof/CAS evidence. This index does not duplicate those
files.

## Unmatched manuscript values

The source audit did not find a RealMath no-CAS run supporting the abstract’s
separate 9/10 claim.

For Problem 17.91, the archived CAS-on database records 5,031,315 input tokens,
219,582 output tokens, 5,250,897 total tokens, and 5,417.175 seconds of active
backend compute. These values agree with the paper’s rounded 5.25M
experiment-summary row, but not with its detailed 6.590M/0.194M/6.784M row or
the nearby 5,244.145-second sentence. No alternative proof-state database in
the checkout contained those detailed CAS-on values.

The archived Problem 17.91 README also preserves the fact that the historical
CAS-on and CAS-off prompts/search settings were not identical. The available
records therefore support an archival comparison, not a single-variable
controlled ablation.

## Integrity

`SHA256SUMS` covers this README, `paper_data.json`, and the dashboard image.
Every linked experiment leaf has its own checksum manifest.
