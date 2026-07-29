# Imported prior Problem 20.2 evidence

- Provenance class: prior_result
- Original source: `agents/generation/results/kourovka/problem_20_2_totally_3_closed_lie_type/phase2/artifacts/final_proof_psl27_total_3closure_root_rev42.md`
- Import note: This is prior mathematical evidence authorized by the user for the new classification run. It must be audited under the current verifier and integration gates before theorem-level use.

# A totally 3-closed nonabelian simple group of Lie type

## Theorem

The group $G=\operatorname{PSL}(2,7)$ is totally $3$-closed. In particular, there exists a nonabelian simple group of Lie type which is totally $3$-closed, so Problem 20.2 has an affirmative answer.

## Proof

For a finite $G$-set $X$, write $G_X^{(3)}$ for the largest subgroup of $\operatorname{Sym}(X)$ having the same orbits as $G$ on $X^3$. Thus a permutation $\sigma$ belongs to $G_X^{(3)}$ precisely when, for every ordered triple $(x_1,x_2,x_3)$, there is an element $g\in G$, depending on the triple, such that

$$
(\sigma x_1,\sigma x_2,\sigma x_3)=(g x_1,g x_2,g x_3).
$$

We use the standard identification

$$
G\cong \operatorname{GL}(3,2)\cong \operatorname{PSL}(3,2).
$$

This is a nonabelian simple group of Lie type of order $168$. Let $V=\mathbb F_2^3$. Denote by $\mathcal P$ the seven one-dimensional subspaces of $V$, by $\mathcal P^*$ the seven two-dimensional subspaces, and by $\mathcal Q=\mathbb P^1(\mathbb F_7)$ the eight points of the natural projective-line action of $\operatorname{PSL}(2,7)$.

### The two-orbit criterion

We first record a reduction from arbitrary faithful actions to pairs of transitive actions.

**Lemma 1.** Let $S$ be a finite nonabelian simple group. Then $S$ is totally $3$-closed if and only if the diagonal action on

$$
S/H\sqcup S/K
$$

is $3$-closed for every pair of proper subgroups $H,K<S$, with repeated pairs allowed.

**Proof.** Necessity follows because every nontrivial coset action of a simple group is faithful.

Conversely, let $X$ be an arbitrary faithful finite $S$-set and let $\sigma\in S_X^{(3)}$. Applying the closure condition to $(x,x,x)$ shows that $\sigma$ preserves each $S$-orbit on points. Its restriction to any union of point-orbits belongs to the $3$-closure of the restricted action. Every non-singleton orbit is faithful: its kernel is a proper normal subgroup of $S$ and hence is trivial. Singleton orbits are fixed pointwise by both $S$ and $\sigma$.

Write the non-singleton orbits as $X_1,\ldots,X_r$. If $r=1$, let $\tau=\sigma|_{X_1}$. Acting as $\tau$ on each of two tagged copies of $X_1$ gives an element of the $3$-closure on $X_1\sqcup X_1$: for every tagged triple, the element of $S$ supplied for its underlying triple also preserves all copy tags. The repeated-pair hypothesis therefore implies that $\tau$ is induced by an element of $S$.

If $r\geq 2$, then for every $j>1$ the restriction of $\sigma$ to $X_1\sqcup X_j$ is induced by some $s_j\in S$. All the elements $s_j$ induce the same permutation on the faithful orbit $X_1$, so they are equal. Their common value induces $\sigma$ on every non-singleton orbit and, together with $\sigma$, fixes every singleton orbit. Hence $\sigma\in S$. This proves the lemma. $\square$

### Two-point bases

A tuple $(u,v)$ is a base for a faithful $G$-set if its pointwise stabilizer is trivial; repetition is allowed when a one-point base exists.

**Lemma 2.** A faithful $G$-set with a base of size at most two is $3$-closed.

**Proof.** Let $(u,v)$ be such a base and let $\sigma$ lie in the $3$-closure. Choose $g\in G$ carrying $(u,v,u)$ to its $\sigma$-image. For arbitrary $x$, choose $g_x\in G$ carrying $(u,v,x)$ to its $\sigma$-image. The elements $g$ and $g_x$ agree on the base, so $g=g_x$. Thus $\sigma x=gx$ for every $x$, and $\sigma=g$. $\square$

**Lemma 3.** Let $X$ and $Y$ be faithful, individually $3$-closed $G$-sets. If $X$ has a base of size at most two, then the diagonal action on $X\sqcup Y$ is $3$-closed.

**Proof.** A closure permutation preserves the two point-orbits and, by individual $3$-closedness, restricts to elements $g,h\in G$ on $X$ and $Y$. After multiplication by the diagonal action of $g^{-1}$, it is the identity on $X$ and acts as some $t\in G$ on $Y$. If $(u,v)$ is a base for $X$, the closure condition applied to $(u,v,y)$ supplies an element $s\in G$ fixing $u$ and $v$ and satisfying $sy=ty$. The base property gives $s=1$, so $ty=y$ for every $y\in Y$. Faithfulness of $Y$ gives $t=1$. $\square$

### Reduction to three maximal geometries

The maximal proper subgroups of $G$ form three geometric conjugacy classes:

1. point stabilizers $G_p\cong S_4$ for $p\in\mathcal P$;
2. line stabilizers $G_L\cong S_4$ for $L\in\mathcal P^*$;
3. normalizers of Sylow $7$-subgroups, isomorphic to $C_7\!:\!C_3$, which are the point stabilizers in the action on $\mathcal Q$.

For completeness, let $M$ be maximal. If $M$ is not transitive on the seven nonzero vectors of $V$, take the sum of the vectors in each $M$-orbit. A nonzero orbit sum is an $M$-fixed point. If every orbit sum is zero, the nontransitive orbit partition must have sizes $3$ and $4$; the three-vector orbit is the set of nonzero vectors in a two-dimensional subspace, so $M$ fixes a line. Thus $M$ is a point or line stabilizer.

If $M$ is transitive, then $7$ divides $|M|$. The group $G$ has eight Sylow $7$-subgroups. A proper $M$ cannot contain all eight, since their conjugates generate the nontrivial normal closure of a Sylow subgroup in the simple group $G$. Hence $M$ has a normal Sylow $7$-subgroup and lies in its normalizer of order $21$. This normalizer is maximal: a proper overgroup would have order $42$ or $84$ and would give a faithful action of the simple group $G$ of degree $4$ or $2$, which is impossible.

Every proper subgroup of an $S_4$ maximal subgroup is contained in a subgroup of type $A_4$, $D_8$, or $S_3$. Every proper subgroup of $C_7\!:\!C_3$ is contained in $C_7$ or $C_3$. Each such subgroup is contained in a subgroup having a conjugate with trivial intersection:

- For $p=\langle e_1\rangle$, the canonical $A_4$ in $G_p$ is the inverse image of $A_3$ under the action on $V/p$. The corresponding canonical $A_4$ subgroups for $\langle e_1\rangle$ and $\langle e_2\rangle$ intersect trivially. Indeed, an element in their intersection fixes $e_1,e_2$ and has $e_3\mapsto e_3+a e_1+b e_2$; membership in the first $A_4$ forces $b=0$, while membership in the second forces $a=0$. Duality gives the same conclusion for the line-type $A_4$ subgroups.
- A Sylow $D_8$ is the stabilizer of an incident point-line flag. The stabilizers of $(\langle e_1\rangle,\langle e_1,e_2\rangle)$ and $(\langle e_3\rangle,\langle e_2,e_3\rangle)$ intersect trivially: an element in the intersection fixes $e_1,e_3$, while preservation of both planes forces it to fix $e_2$.
- An $S_3$ is the stabilizer of a nonincident point-line pair. The stabilizers of $(\langle e_1\rangle,\langle e_2,e_3\rangle)$ and $(\langle e_2\rangle,\langle e_1,e_2+e_3\rangle)$ intersect trivially, as follows directly by writing the first stabilizer in block-diagonal form relative to $\langle e_1\rangle\oplus\langle e_2,e_3\rangle$.
- Distinct Sylow $7$-subgroups intersect trivially. An order-$3$ subgroup is conjugate into one of the displayed $S_3$ subgroups, so it is covered as well.

The property $H\cap H^g=1$ passes to subgroups of $H$ and says exactly that the coset action on $G/H$ has a two-point base. Consequently every proper-subgroup coset action except the three maximal actions $\mathcal P$, $\mathcal P^*$, and $\mathcal Q$ has base size at most two.

### The three exceptional actions

**Lemma 4.** The actions of $G$ on $\mathcal P$, $\mathcal P^*$, and $\mathcal Q$ are individually $3$-closed.

**Proof.** On $\mathcal P$, the $G$-orbits on ordered triples of distinct points distinguish collinear from noncollinear triples. A permutation in the $3$-closure therefore preserves the lines of the Fano plane. Three noncollinear points form a vector-space basis, so their images determine a unique element of $\operatorname{GL}(3,2)$. Preservation of the third point on each Fano line then determines all remaining points. Thus every element of the $3$-closure lies in $G$. Duality proves the assertion for $\mathcal P^*$.

For $\mathcal Q=\mathbb P^1(\mathbb F_7)$, the group $\operatorname{PGL}(2,7)$ acts sharply transitively on ordered triples of distinct points, while $G=\operatorname{PSL}(2,7)$ has two orbits on those triples. For a distinct triple $T$, let $\varepsilon(T)$ be the quadratic character of the determinant of the unique projective transformation carrying $(\infty,0,1)$ to $T$. Projective rescaling changes the determinant by a square, so $\varepsilon$ is well-defined and its two values distinguish the two $G$-orbits.

Let $\sigma$ belong to the $3$-closure. After composition with an element of $G$, assume that it fixes $\infty,0,1$. For $x\in\mathbb F_7\setminus\{0,1\}$, preservation of the colors of $(\infty,0,x)$ and $(\infty,1,x)$ preserves the pair

$$
(\chi(x),\chi(x-1)),
$$

where $\chi$ is the quadratic character. Since the nonzero squares modulo $7$ are $1,2,4$, the signatures are

$$
2:(+,+),\quad 3:(-,+),\quad 4:(+,-),\quad 5:(-,+),\quad 6:(-,-).
$$

Thus $\sigma$ fixes $2,4,6$ and can at most interchange $3$ and $5$. The colors of $(\infty,2,3)$ and $(\infty,2,5)$ are respectively $\chi(1)=+$ and $\chi(3)=-$, so that interchange is impossible. Hence the normalized permutation is the identity, and the action on $\mathcal Q$ is $3$-closed. $\square$

### Synchronizing the exceptional pairs

Consider a closure permutation on a disjoint union of two exceptional orbits. Lemma 4 permits us to normalize it so that it is the identity on the first orbit and is induced by some $t\in G$ on the second.

For $\mathcal P\sqcup\mathcal P$, choose distinct points $p,q$ in the first copy and let $r$ be the third point on their Fano line. The mixed tagged triple with $r$ in the second copy shows that $t(r)=r$, because every element fixing $p$ and $q$ also fixes $r$. Every point can occur as such an $r$, so $t=1$. Duality treats $\mathcal P^*\sqcup\mathcal P^*$.

For $\mathcal P\sqcup\mathcal P^*$, use distinct points $p,q$ in the first orbit and their joining line $L$ in the second. The closure condition forces $t(L)=L$. Every line is the join of two points, so $t=1$. The reversed pair is identical after exchanging the roles of the two orbits.

For $\mathcal Q\sqcup\mathcal Q$, choose distinct $u,v$ in the first copy and use the point $u$ in the second copy as the third entry. The closure condition supplies an element fixing $u$ and $v$ in the first action and hence fixing the corresponding point $u$ in the second action. Therefore $t(u)=u$. Varying $u$ gives $t=1$.

It remains to synchronize $\mathcal P$ with $\mathcal Q$. Fix distinct $p,q\in\mathcal P$, let $\ell$ be their Fano line, and put $E=G_{p,q}$. Then $E$ is the normal Klein four subgroup of the line stabilizer $G_\ell\cong S_4$. Every point stabilizer on $\mathcal Q$ has odd order $21$, so $E$ acts semiregularly on $\mathcal Q$ and has two orbits $B$ and $B^c$, each of size four.

We claim that the setwise stabilizer $G_B$ is the canonical $A_4$ inside $G_\ell$. First, $N_G(E)=G_\ell$: the line stabilizer normalizes $E$ and is maximal, while $E$ is not normal in the simple group $G$. Moreover, $G_\ell$ is transitive on $\mathcal Q$. Indeed, for $y\in\mathcal Q$, the order of $(G_\ell)_y$ divides both $24$ and $21$. It is therefore $1$ or $3$; the first possibility would give an orbit of length $24$ on an eight-point set, so the stabilizer has order $3$ and the orbit has length $8$. Since $E$ is normal in $G_\ell$, the two $E$-orbits are interchanged transitively, and their stabilizer inside $G_\ell$ is its index-two subgroup $A_4$.

This $A_4$ is all of $G_B$. Otherwise, a maximal proper overgroup of it would be an $S_4$. The $A_4$ is normal in that $S_4$, and its characteristic Klein four subgroup $E$ would also be normalized. The overgroup would therefore lie in $N_G(E)=G_\ell$ and hence equal $G_\ell$, contrary to the fact that $G_\ell$ interchanges $B$ and $B^c$. Thus $G_B=A_4\leq G_\ell$.

Now normalize a closure permutation on $\mathcal P\sqcup\mathcal Q$ to be the identity on $\mathcal P$ and to act as $t\in G$ on $\mathcal Q$. Applied to $(p,q,y)$, the closure condition gives

$$
t(y)\in E y
$$

for every $y\in\mathcal Q$. Hence $t$ stabilizes both $E$-orbits, so $t\in G_B\leq G_\ell$. The line $\ell$ was arbitrary; therefore $t$ lies in every line stabilizer. Their intersection is the kernel of the faithful action on $\mathcal P^*$, and hence is trivial. Thus $t=1$. The dual argument, with points and lines exchanged, synchronizes $\mathcal P^*$ with $\mathcal Q$.

We have now proved that every diagonal action on $G/H\sqcup G/K$, for arbitrary proper subgroups $H,K<G$ and with repetitions allowed, is $3$-closed. Indeed, if at least one stabilizer is nonmaximal, Lemmas 2 and 3 apply; if both are maximal, the preceding exceptional-pair arguments apply. Lemma 1 therefore shows that every faithful finite permutation representation of $G$ is $3$-closed. Hence $\operatorname{PSL}(2,7)$ is totally $3$-closed.

The proved statement is stronger than bare existence: it identifies a specific nonabelian simple Lie-type group and proves total $3$-closedness for all of its faithful finite permutation representations. It therefore implies the affirmative answer requested in Problem 20.2. $\square$

## Certification status

This proof is written from the integrated route `route_psl27_positive_example_rev32`. The two-orbit reduction and the complete $\operatorname{PSL}(2,7)$ pair analysis were independently accepted by the strict informal verifier, and the resulting sufficient route was accepted by the integration verifier with no unresolved proof debt.

## References

No external references are used. This final proof was written by the Albilich writer from the following internal artifacts:

- *PSL(2,7) is totally 3-closed*, artifact `proof_dossier_psl27_total_3closure_rev32`, researcher.
- *Two-orbit criterion for total 3-closure*, artifact `proof_dossier_two_orbit_reduction_rev24`, researcher.
- *Verification of the two-orbit reduction*, artifact `verification_report_two_orbit_reduction_rev28`, strict informal verifier.
- *Verification of the PSL(2,7) positive example*, artifact `verification_report_psl27_positive_example_rev36`, strict informal verifier.
- *Root integration report for the PSL(2,7) positive example*, artifact `integration_report_psl27_positive_example_root_rev40`, integration verifier.
