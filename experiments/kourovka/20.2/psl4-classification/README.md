# Complete classification of totally 3-closed \(\operatorname{PSL}_4(q)\)

## Classification

No nonabelian simple group \(\operatorname{PSL}_4(q)\) is totally 3-closed.

The proof splits into two exhaustive cases:

1. For \(q>2\), the faithful action on
   \((\mathbb F_q^4\setminus\{0\})/Z(\operatorname{SL}_4(q))\) has
   \[
   \operatorname{PSL}_4(q)
   <\operatorname{GL}_4(q)/Z(\operatorname{SL}_4(q))
   \leq\operatorname{PSL}_4(q)^{(3)}.
   \]
2. For \(q=2\), the faithful degree-28 action on
   \(\operatorname{PSL}_4(2)/\operatorname{Sp}_4(2)\) has an orthogonal
   ruling-switch outside \(\operatorname{PSL}_4(2)\) that preserves every
   ordered-triple orbit.

Both case proofs were strictly verified and integrated in the revision-610
\(\operatorname{PSL}_n(q)\) study. Their conjunction is the displayed
classification; it is a direct case assembly, not a separately run root
experiment. This is internal Albilich verification, not independent peer
review.

## Contents

- `classification.md`: the complete two-case theorem assembly.
- `source_problem.md`: exact broad \(\operatorname{PSL}_n(q)\) prompt from
  which this family result was extracted.
- `provenance.json`: source revision and result-scope metadata.
- `evidence/`: both proofs and their strict-verifier and integration records.
- `SHA256SUMS`: integrity manifest for this public package.

The source problem and evidence were copied byte-for-byte from Rethlas-CAS
commit `e0ce0ebf55ede6281e7b49e2d7d6318017baf4a0`. Raw child logs, session
identifiers, absolute local paths, and SQLite state are excluded.
