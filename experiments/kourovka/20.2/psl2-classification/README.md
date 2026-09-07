# Complete classification of totally 3-closed \(\operatorname{PSL}_2(q)\)

## Classification

Among the nonabelian simple groups \(\operatorname{PSL}_2(q)\), total
3-closure holds exactly when

\[
q=p\ \text{is prime and}\ p\geq 7.
\]

Thus every proper extension-field case \(q=p^f\), \(f>1\), is excluded, as is
\(\operatorname{PSL}_2(5)\). The positive cases are
\(\operatorname{PSL}_2(p)\) for every prime \(p\geq7\).

## Evidence boundary

This package combines the exact rank-one classification packet archived by
Rethlas-CAS with the full positive proof dossiers for \(p=7,11,13,19\), the
uniform proof for \(p\geq17\), \(p\neq19\), and the symbolic negative proof for
extension fields and \(q=5\). The classification is also recorded as a
certified prior premise in the revision-610 \(\operatorname{PSL}_n(q)\)
study.

The evidence was copied byte-for-byte from Rethlas-CAS commit
`e0ce0ebf55ede6281e7b49e2d7d6318017baf4a0`. This is an internal Albilich
verification result, not independent peer review.

## Contents

- `problem.md`: exact strengthened Lie-type classification prompt from the
  source run; this package extracts its complete rank-one result.
- `provenance.json`: source commit and result-scope metadata.
- `evidence/`: proof, verifier, and integration artifacts for every parameter
  class in the theorem.
- `SHA256SUMS`: integrity manifest for this public package.

Raw child logs, session identifiers, absolute local paths, and SQLite state are
excluded.
