# Classification of the totally \(3\)-closed groups \(\operatorname{PSL}_4(q)\)

## Theorem

For every prime power \(q\) for which \(\operatorname{PSL}_4(q)\) is
nonabelian simple, \(\operatorname{PSL}_4(q)\) is not totally \(3\)-closed.
Equivalently, the complete list of totally \(3\)-closed groups in this family
is empty.

## Proof assembly

Let \(q\) be a prime power.

If \(q>2\), apply the central-vector theorem in
`evidence/art_researcher_root_central_vector_statement_repair_rev399.md` with
\(n=4\). It supplies a faithful action on
\[
(\mathbb F_q^4\setminus\{0\})/Z(\operatorname{SL}_4(q))
\]
and a proper overgroup
\[
\operatorname{PSL}_4(q)
<\operatorname{GL}_4(q)/Z(\operatorname{SL}_4(q))
\leq\operatorname{PSL}_4(q)^{(3)}.
\]
Thus this faithful action is not \(3\)-closed. The strict-verifier and
integration records are included beside the proof.

If \(q=2\), apply
`evidence/art_researcher_root_psl42_klein_quadric_parity_rev14.md`. In the
faithful degree-28 action on
\(\operatorname{PSL}_4(2)/\operatorname{Sp}_4(2)\), an orthogonal
ruling-switch lies outside the permutation image but preserves every orbit on
ordered triples. Hence that action is not \(3\)-closed. Its strict-verifier and
integration records are also included.

These two cases exhaust all prime powers \(q\), proving the theorem.
