# Complete classification of totally 3-closed \(\operatorname{PSL}_3(q)\)

## Classification

Among the nonabelian simple groups \(\operatorname{PSL}_3(q)\), total
3-closure holds exactly when \(q\) is prime and

\[
q=3\quad\text{or}\quad q\equiv2\pmod3.
\]

The parameter \(q=2\) is included through
\(\operatorname{PSL}_3(2)\cong\operatorname{PSL}_2(7)\).

## Run result

Albilich reported `solved_final` at revision 1356:

- exact full theorem;
- 86 claims, 85 verified, and 83 integrated;
- 730 recorded generator calls;
- 110h 5m 12s lifecycle wall clock;
- 80h 3m 52s active backend compute;
- 378,602,459 reported tokens.

The final route covers all prime powers. Proper extension fields and prime
parameters congruent to \(1\) modulo \(3\) are excluded by projective outer
obstructions. The surviving prime parameters are proved uniformly, with
bounded certified analyses only for \(q=2,3\).

The strict informal verifier reported no mathematical or dependency gap, and
the integration verifier accepted the exact classification. These are internal
Albilich judgments, not independent peer review.

## Contents

- `problem.md`: exact restricted \(\operatorname{PSL}_3(q)\) prompt.
- `report.md`: complete generated revision-1356 report.
- `metrics.json`: terminal run measurements and source provenance.
- `evidence/art_writer_root_final_proof_rev1354.md`: final proof.
- `evidence/`: the principal proof, verifier, and integration dependency
  packets used by the final route.
- `SHA256SUMS`: integrity manifest for this public package.

The report and evidence were copied byte-for-byte from Rethlas-CAS commit
`e0ce0ebf55ede6281e7b49e2d7d6318017baf4a0`. Raw child logs, session
identifiers, absolute local paths, SQLite state, and writer build logs are
excluded.
