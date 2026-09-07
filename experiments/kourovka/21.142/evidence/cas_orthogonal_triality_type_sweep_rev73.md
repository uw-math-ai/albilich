# Bounded orthogonal triality/type experiment

## Mathematical question

Does the remaining upgrade from the verified semilinear orthogonal normalizer theorem to the full abstract automorphism group require a new unbounded family of graph-automorphism cosets, or is the only extra diagram phenomenon the bounded \(D_4\) triality case?

## Competing hypotheses

- H1: exceptional type permutations not induced by projective semilinear quadratic similarities persist for arbitrarily large \(B_m\) or \(D_m\), so the semilinear route needs a new outer-coset construction.
- H2: the only extra diagram phenomenon is \(D_4\) triality; for \(B_m\) the diagram is rigid and for \(D_m\), \(m\ge 5\), the only diagram automorphism swaps the two terminal nodes and is already realized by an improper isometry.

No GAP, Sage, or Magma executable was present. I therefore used the finite, exact standard-library Python calculation recorded in the metadata.

## Finite scope and output

The program enumerated all vertex permutations preserving the colored \(B_m\) and uncolored \(D_m\) Dynkin diagrams for \(4\le m\le 8\). It also evaluated, for split \(D_m^+(q)\), the exact formulas
\[
 N_1=(q^{m-1}+1)\frac{q^m-1}{q-1},\qquad
 N_{\max}=\prod_{i=1}^{m-1}(q^i+1)
\]
for \(q\in\{2,3,4,5,7,8,9\}\), where \(N_1\) is the number of singular points and \(N_{\max}\) is the number of maximal singular \(m\)-spaces in either one of the two families.

The diagram outputs were
\[
\begin{array}{c|ccccc}
m&4&5&6&7&8\\ \hline
|\operatorname{Aut}(D_m)|&6&2&2&2&2\\
|\operatorname{Aut}(B_m)|&1&1&1&1&1.
\end{array}
\]
For every tested \(q\), \(N_1=N_{\max}\) at \(m=4\), while \(N_{\max}>N_1\) at every \(m\ge5\). Representative pairs \((N_1,N_{\max})\) are \((135,135)\) for \((m,q)=(4,2)\), \((527,2295)\) for \((5,2)\), and \((9922,91840)\) for \((5,3)\).

## Exact interpretation

The finite calculation suggested the correct sharp pattern, which has a short proof independent of the computation. A colored \(B_m\) diagram is a path with its unique double edge at one end, so its automorphism group is trivial. The \(D_4\) diagram has a central node with three indistinguishable leaves, giving \(S_3\). If \(m\ge5\), the \(D_m\) branch node has two arms of length one and one longer arm; hence only the two short terminal arms can be exchanged, giving \(C_2\).

The type counts explain geometrically why triality is confined to \(D_4\). At \(m=4\),
\[
(q-1)(q+1)(q^2+1)=q^4-1,
\]
so \(N_1=N_{\max}\). For \(m\ge5\), after cancelling \(q^{m-1}+1\),
\[
\frac{N_{\max}}{N_1}=\frac{(q-1)\prod_{i=1}^{m-2}(q^i+1)}{q^m-1}>1,
\]
because \(\sum_{i=1}^{m-2}i=(m-1)(m-2)/2>m\) and \(q\ge2\). Thus point type and maximal-singular type already have different cardinalities in split rank at least five.

This does not prove the infinite abstract-automorphism theorem: the computation neither recognizes parabolics intrinsically nor proves that an arbitrary abstract automorphism acts on the building. It does decide the next mathematical move. The verified semilinear dossier already realizes the \(D_m\), \(m\ge5\), terminal swap by an improper isometry and excludes \(D_4\) by its dimension bound. Therefore no further outer-coset experiment is warranted. The remaining orthogonal task should be narrowed to the intrinsic building-recognition and chamber-kernel interface.
