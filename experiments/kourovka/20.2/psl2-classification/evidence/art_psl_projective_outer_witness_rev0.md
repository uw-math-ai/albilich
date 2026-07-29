# Uniform exclusion lemma for type A

## Result

Let \(q=p^f\), let \(n\ge 2\), and let \(G=\operatorname{PSL}_n(q)\) be simple in its faithful action on
\[
\Omega=\mathbb P^{n-1}(\mathbb F_q).
\]
Then:

1. if \(n\ge 3\),
\[
\operatorname{P\Gamma L}_n(q)\le G^{(3),\Omega};
\]
2. if \(n=2\), every field automorphism of \(\mathbb F_q\), acting componentwise on \(\mathbb P^1(q)\), belongs to \(G^{(3),\Omega}\).

Consequently, if \(\operatorname{PSL}_n(q)\) is totally 3-closed, then \(f=1\), and either \(n=2\) or \(\gcd(n,p-1)=1\). Thus the projective linear part of the classification is reduced to
\[
\operatorname{PSL}_2(p)\quad(p\text{ prime})
\]
and
\[
\operatorname{PSL}_n(p)\quad(n\ge3,\ p\text{ prime},\ \gcd(n,p-1)=1).
\]
This is only a necessary condition: the groups in the residual set still require other faithful actions.

## Source interface

The only external closure result used is the following complete statement.

Freedman, Giudici and Praeger, *Total closure for permutation actions of finite nonabelian simple groups*, Monatshefte für Mathematik 203 (2024), 323–340, Lemma 2.1, DOI 10.1007/s00605-023-01822-5, arXiv:2206.02347:

> Let \(K\) act on a set \(X\), and let \(k\ge1\). A permutation \(h\in\operatorname{Sym}(X)\) lies in \(K^{(k),X}\) if and only if, for every \((x_1,\ldots,x_k)\in X^k\), there is \(g\in K\) such that \((x_1,\ldots,x_k)^g=(x_1,\ldots,x_k)^h\).

The paper attributes this to Wielandt, Theorem 5.6. Its terminology agrees exactly with the present problem: the closure fixes every orbit on ordered tuples individually. The source's Theorem 1.2 gives only upper bounds for closure numbers of simple Lie-type groups, so it does not decide which have closure number 3; the argument below instead supplies an explicit larger subgroup in one faithful 3-closure.

## Proof for \(n\ge3\)

Write \(V=\mathbb F_q^n\). The determinant induces a surjective homomorphism
\[
\overline{\det}:\operatorname{PGL}(V)\longrightarrow
\mathbb F_q^*/(\mathbb F_q^*)^n
\]
whose kernel is \(\operatorname{PSL}(V)\). Indeed, multiplying a matrix by a scalar changes its determinant by an \(n\)-th power, and a projective class has trivial determinant class precisely when it has a determinant-one representative.

Fix an ordered triple \(T=(L_1,L_2,L_3)\in\Omega^3\), allowing repetitions, and put \(W=L_1+L_2+L_3\). We claim that the pointwise stabilizer \(\operatorname{PGL}(V)_T\) maps surjectively under \(\overline{\det}\).

If \(\dim W<n\), choose a complement of \(W\). For every \(a\in\mathbb F_q^*\), the linear transformation which is the identity on \(W\), multiplies one fixed complement vector by \(a\), and fixes the remaining complement vectors fixes all three projective points and has determinant \(a\).

The only remaining possibility is \(\dim W=n\). Since \(n\ge3\) and \(T\) contains only three points, this forces \(n=3\) and the three lines to be independent. Choose nonzero \(v_i\in L_i\). The diagonal transformation
\[
v_1\mapsto av_1,\qquad v_2\mapsto v_2,\qquad v_3\mapsto v_3
\]
again fixes \(T\) and has determinant \(a\). This proves the claim.

Let \(h\in\operatorname{PGL}(V)\). By the claim, choose \(s\in\operatorname{PGL}(V)_T\) with
\(\overline{\det}(s)=\overline{\det}(h)^{-1}\). Then \(sh\in G\) and
\[
T^{sh}=(T^s)^h=T^h.
\]
The cited tuple criterion therefore gives
\[
\operatorname{PGL}_n(q)\le G^{(3),\Omega}.
\]
In particular, \(G\) and \(\operatorname{PGL}_n(q)\) have exactly the same orbits on ordered triples.

It remains to include field automorphisms. The \(\operatorname{PGL}_n(q)\)-orbit of an ordered triple of projective points is determined by its equality pattern and, when the points are distinct, whether their span has dimension two or three. For three distinct collinear points this follows from the sharp 3-transitivity of \(\operatorname{PGL}_2(q)\) on a projective line; for three independent points it follows by extending representative vectors to bases. A field automorphism preserves equality and span dimension, hence preserves each \(\operatorname{PGL}_n(q)\)-orbit and therefore each \(G\)-orbit on triples. The tuple criterion puts every field automorphism in \(G^{(3),\Omega}\). Since the 3-closure is a group and already contains \(\operatorname{PGL}_n(q)\), it contains \(\operatorname{P\Gamma L}_n(q)\).

If \(f>1\), a nonidentity field automorphism is not projective linear. Indeed it fixes the projective frame
\([e_1],\ldots,[e_n],[e_1+\cdots+e_n]\); a projectivity fixing this frame is the identity, whereas a nonidentity field automorphism moves \([e_1+ae_2]\) for some \(a\notin\mathbb F_p\). Hence it lies outside \(G\). If \(f=1\) but \(\gcd(n,q-1)>1\), then
\[
|\operatorname{PGL}_n(q):\operatorname{PSL}_n(q)|=\gcd(n,q-1)>1.
\]
In either case the faithful projective-point action is not 3-closed.

## Proof for \(n=2\) and \(f>1\)

Let \(G=\operatorname{PSL}_2(q)\) act on \(\Omega=\mathbb P^1(q)\), and let \(\sigma:x\mapsto x^p\) be a nonidentity field automorphism. The group \(G\) is 2-transitive, so \(\sigma\) preserves the orbit of every triple having a repeated entry.

For triples of distinct points, fix \(T_0=(\infty,0,1)\). The group \(\operatorname{PGL}_2(q)\) is sharply 3-transitive, so every ordered distinct triple is uniquely \(T_0^h\) for some \(h\in\operatorname{PGL}_2(q)\). If \(q\) is even then \(\operatorname{PGL}_2(q)=G\), so all distinct triples form one \(G\)-orbit.

Suppose \(q\) is odd. The two \(G\)-orbits on distinct triples are distinguished by the square class of \(\det h\): scalar changes alter the determinant by a square, and the kernel of this square-class map is \(G\). Since \(T_0\) is fixed by \(\sigma\),
\[
(T_0^h)^\sigma=T_0^{h^\sigma},
\qquad
\det(h^\sigma)=\det(h)^p.
\]
Raising to the odd power \(p\) preserves square and nonsquare classes. Thus \(\sigma\) preserves each of the two \(G\)-orbits. It follows from the tuple criterion that \(\sigma\in G^{(3),\Omega}\).

As above, \(\sigma\notin\operatorname{PGL}_2(q)\): it fixes \(\infty,0,1\), while the identity is the only projectivity fixing those three points, and it moves a point with a coordinate outside \(\mathbb F_p\). Hence this action is not 3-closed whenever \(f>1\).

## Assembly into the root classification

This proves a uniform negative certificate for every type-\(A\) simple group \(\operatorname{PSL}_n(p^f)\) with \(f>1\), and also for every \(n\ge3\) with \(\gcd(n,p^f-1)>1\). The certificate is the faithful projective-point action together with an explicit element of \(\operatorname{P\Gamma L}_n(q)\setminus G\) preserving all ordered-triple orbits. It includes all nonprime-field \(\operatorname{PSL}_2(q)\). The surviving necessary-condition ledger contains \(\operatorname{PSL}_2(p)\) and the prime-field higher-dimensional groups with \(\gcd(n,p-1)=1\); exceptional isomorphisms must be deduplicated later. This does not prove that any residual group is totally 3-closed.

## Independent attacks and obstruction analysis

The exact-theorem search located the Freedman–Giudici–Praeger paper, but its base-size method gives upper bounds such as \(k(G)\le n+2\), not the lower obstruction or exact value needed here. A base-size attack therefore cannot by itself exclude total 3-closure and was not pursued further.

The successful attack switched to a single concrete faithful action. The universal negative assertion became a local orbit problem, and the determinant quotient converted that orbit problem into surjectivity of triple stabilizers onto \(\operatorname{PGL}/\operatorname{PSL}\). The same idea is structurally analogous to the natural alternating action: unused coordinates repair determinant class just as unused letters repair parity, leaving a larger overgroup with the same short-tuple orbits.

The principal new obstruction is that this witness disappears exactly for prime-field \(\operatorname{PSL}_n(p)\) with \(\gcd(n,p-1)=1\). In those groups the remaining graph automorphism generally does not act on the point set, so the present representation cannot decide the case. A graph-stable coset action, such as a middle-Grassmannian action when available or an action with a self-dual subgroup, is the next natural representation to test.

## Self-check

- The action is faithful because \(\operatorname{PSL}_n(q)\) is defined as the induced projective action of \(\operatorname{SL}_n(q)\).
- Repeated entries, collinear triples, and independent triples were all covered.
- The determinant quotient is well defined modulo scalar matrices.
- The full-span exceptional case in the stabilizer argument was isolated and handled when \(n=3\).
- For \(n=2\), the diagonal outer automorphism was not incorrectly placed in the 3-closure; only field automorphisms were used.
- The field-automorphism witness was proved external to \(\operatorname{PGL}\), rather than merely assumed outer abstractly.
- The conclusion is stated only as a necessary condition and does not claim that the residual prime-field groups survive.
