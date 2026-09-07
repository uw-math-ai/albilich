# Kourovka Problem 17.91: universal-lift certificate report

## 1. Outcome

No finite soluble maximal pair with derived-length gap four was found.
The largest verified gap remains three.

The new substantive result is not another bounded order sweep.  An exact
integral group-algebra computation proves that the verified order-1296
gap-three seed has no split elementary-abelian gap-four lift over **any**
field, for **any** module dimension, including reducible and indecomposable
modules.  A second argument and complete finite $H^2$ calculation eliminate
all elementary-abelian minimal-normal lifts of the order-216
Heisenberg-$Q_8$ gap-two seed in every characteristic.

The search found no terminal-escaping exact-gap-three seed.  It reduces the
first new Glasby-Howlett extraspecial-tower layer to three finite coherent-lift
problems.

These are computer-assisted family exclusions and search reductions, not a
solution of the universal Kourovka problem.

## 2. Previous results used as pruning rules

The full inventory is [`previous_family_manifest.json`](previous_family_manifest.json).
The main rules were:

- do not repeat the complete soluble SmallGroups search through order 255;
- do not repeat the complete order-1296 maximal-subgroup search;
- retain all three order-1296 exact-gap-three pairs as controls;
- reject them as lifting priorities because $H^{(5)}\le L^{(2)}$;
- replace finite irreducible/permutation-module lists by the regular-algebra
  universal criterion;
- keep split and nonsplit extension conclusions logically separate;
- reject local class-two, normalizer, or exact-derived-length conditions that
  the earlier corpus already showed to be insufficient.

The named audit TeX/PDF files in the brief were not present in the accessible
filesystem.  The comprehensive revision-2166 Markdown corpus, its selected
verified packet, its publication audit, the current Rethlas-CAS durable
artifacts, and all previous GAP scripts/reports were used instead.

## 3. Universal split-lift criterion

Let $F$ be a field, let $(H,L)$ be an exact gap-three pair, and put
$r=d(L)$.  In $R=F[H]$, define

\[
P_H=I(H)I(H')\cdots I(H^{(r+2)}),
\]

\[
P_L=I(L)I(L')\cdots I(L^{(r-1)}),\qquad J_L=RP_LR.
\]

Here $I(X)$ is the $F$-span of $x-1$, $x\in X$, in $F[H]$.

### Proposition

A right $FH$-module $V$ gives

\[
d(V\rtimes H)=r+4,\qquad d(V\rtimes L)=r
\]

if and only if $VP_H\ne0$ and $VP_L=0$.  Such a module exists if and
only if

\[
P_H\not\subseteq J_L.
\]

When containment fails, $V=R/J_L$ is a universal witness.

### Proof

For a right $FX$-module $V$, induction gives

\[
(V\rtimes X)^{(i)}=
V I(X)I(X')\cdots I(X^{(i-1)})\rtimes X^{(i)}.
\]

Since $d(H)=r+3$, the ambient split extension has one additional
derived layer precisely when $VP_H\ne0$.  Since $d(L)=r$, the maximal
preimage retains derived length $r$ precisely when $VP_L=0$.

If $VP_L=0$, then for $v\in V$ and $a,b\in R$,

\[
v(aP_Lb)=(va)P_Lb=0,
\]

so $VJ_L=0$.  Thus $P_H\subseteq J_L$ forces $VP_H=0$ for every
module.  Conversely, if $p\in P_H\setminus J_L$, then in the right module
$R/J_L$,

\[
(1+J_L)p\ne0,\qquad (R/J_L)P_L=0.
\]

This proves the criterion.  The subgroup $V\rtimes L$ is maximal in
$V\rtimes H$ because it is the full inverse image of the maximal subgroup
$L<H$.  Quotienting by $V$ also supplies the lower derived-length bounds,
so the displayed equalities are exact.

This proof does not assume $V$ irreducible.

## 4. Correct integral-to-modular certificate

Let $R_{\mathbb Z}=\mathbb Z[H]$, and let $J$ and $S=J+P_H$ be the
integral row lattices.  The brief proposed using only

\[
Q=S/J.
\]

That is not sufficient in general: tensoring a lattice inclusion into
$R_{\mathbb Z}$ need not be left exact.  For example,
$4\mathbb Z\subset2\mathbb Z\subset\mathbb Z$ has
$(2\mathbb Z/4\mathbb Z)\otimes\mathbf F_2\ne0$, while both embedded
lattices reduce to zero in $\mathbf F_2$.

The exact modular obstruction is

\[
\frac{\operatorname{im}(S\otimes\mathbf F_p\to R_{\mathbb Z}\otimes\mathbf F_p)}
{\operatorname{im}(J\otimes\mathbf F_p\to R_{\mathbb Z}\otimes\mathbf F_p)}.
\]

Consequently the implementation computes:

1. a row-Hermite basis of $J$;
2. a row-Hermite basis of $S$;
3. the abstract Smith invariants of $S/J$;
4. the Smith diagonals of both ambient embeddings $J\hookrightarrow R$ and
   $S\hookrightarrow R$;
5. the exact ranks of both reductions for every prime at which either Smith
   diagonal can drop.

If the rational ranks differ, the positive modular gap holds away from a
finite exceptional set and that finite set is checked directly.  If the
rational ranks agree, only primes in the two Smith diagonals can be candidates.
This is a complete all-characteristic procedure.  Extension fields need no
extra test because extending the prime field does not change matrix rank.

In the lattice products, augmentation by a subgroup is generated using a
group-generating set.  This is exact because the preceding product lattice is
stable under right multiplication by the next member of the derived chain;
the usual telescoping expression for $x-1$ then reduces every augmentation
element to generator differences.  The final closure repeatedly adjoins right
translates by generators of $H$ until the row-Hermite lattice itself, not
merely its rational span, stabilizes.

## 5. Integral certificate for the known gap-three seed

The regression pair is

\[
H=\operatorname{SmallGroup}(1296,2891),\qquad
L\cong\operatorname{SmallGroup}(324,39).
\]

GAP independently checked solubility, maximality, and

\[
|H^{(i)}|=(1296,648,216,54,27,3,1),
\]

\[
|L^{(i)}|=(324,81,9,1).
\]

The exact integral product ranks were

\[
P_H:\quad 1295,1294,1290,1272,1248,864,
\]

\[
P_L\text{ before two-sided closure}:\quad1292,1278,1152.
\]

The two-sided closure $J_L$ has rational rank 1248.  The final result is

\[
\boxed{P_H\subseteq J_L\text{ in }\mathbb Z[H].}
\]

More strongly, the exported row-Hermite bases of $J_L$ and
$J_L+P_H$ are byte-identical.  Hence

\[
Q=(J_L+P_H)/J_L=0.
\]

The Smith diagonal of either ambient lattice has multiplicities

\[
1^{1230},\;3^{18}.
\]

Thus both lattices lose the same 18 ranks in characteristic 3, and there are
no candidate characteristics.  The direct modular regressions agree:

| characteristic | $\dim P_H$ | $\dim J_L$ | containment |
|---:|---:|---:|:---:|
| 2 | 864 | 1248 | yes |
| 3 | 768 | 1230 | yes |

Therefore every split elementary-abelian extension of this seed, over every
field and for every right module, fails to produce gap four.  This is an
infinite construction family, not a finite irreducible-module list.

Because containment holds, the universal quotient $F[H]/J_L$ is not a
witness and there is no surviving element of $P_H$ to minimize.  Radical,
socle, indecomposable-quotient, and generator-matrix minimization are therefore
correctly skipped rather than reported as a failed finite search.

The exact bases are:

- `certificates/SG1296_2891__SG324_39_PH_Z.mtx`;
- `certificates/SG1296_2891__SG324_39_JL_Z.mtx`;
- `certificates/SG1296_2891__SG324_39_SUM_Z.mtx`.

Their SHA-256 hashes are recorded in `certificate_checksums.sha256`.

## 6. Recursive exact-gap-two search

The seed database contains 29 exact-gap-two maximal pairs from SmallGroups of
order at most 96 and the separately verified pair

\[
(K,B)=(\operatorname{SmallGroup}(216,88),
       \operatorname{SmallGroup}(24,11)).
\]

Nine pairs have $d(B)=1$.  A full-preimage split lift of such a pair can
never be terminal-escaping, because its terminal module lies in
$L=L^{(0)}$, so these were retained in the database but not lifted.

For the other 21 pairs, 105 universal regular-quotient tests were performed
in characteristics $2,3,5,7,11$.  In every test the ambient terminal product
was contained in the maximal two-sided ideal.  Thus no new split gap-three
seed was produced, and in particular no terminal-escaping seed was produced.

This recursive result is finite-characteristic evidence only.  Integral
certificates were not computed for all 21 pairs, so they are not claimed
eliminated in every characteristic.

## 7. Complete elementary-abelian lift exclusion for the order-216 seed

For

\[
K=\operatorname{SmallGroup}(216,88),\qquad
B=\operatorname{SmallGroup}(24,11),
\]

one has $d(K)=4$, $d(B)=2$, and the previously proved odd-characteristic
argument excludes every elementary-abelian lift that would raise the ambient
length without raising the maximal preimage.

For completeness, that argument is short.  Let $q$ be the central involution
in the quaternion subgroup, viewed in $B'$, and let $z$ generate
$K^{(3)}$ of order 3.  Exact normal-closure computation gives
$z\in\langle q^K\rangle$.  In an extension with elementary-abelian kernel
$A$, full preimage $M$ of $B$, and $d(M)=2$, put $W=[A,M]\le M'$.  A lift
of $q$ lies in the abelian group $M'$, so $(q-1)A\le W$ and
$(q-1)^2A=0$.  In odd characteristic the involution is semisimple, hence it
acts trivially on $A$.  The action kernel is normal in $K$, contains $q$,
and therefore contains $z$.  The group $G^{(3)}$ then has central
intersection with $A$ and cyclic quotient generated by $z$, so it is
abelian.  Thus $G^{(4)}=1$, contradicting the required rise from derived
length 4 to 5.  This covers every odd characteristic and does not assume the
extension split.

In characteristic 2, GAP returns exactly three irreducible $K$-modules,
of dimensions 1, 8, and 6.  Minimal elementary-abelian normal kernels are
irreducible, so this is the complete characteristic-two list.  Native exact
cohomology and extension construction gave:

| dimension | $\dim H^2(K,V)$ | classes | $d(G)$ | $d(M)$ | gap |
|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 4 | 4 | 2 | 2 |
| 8 | 0 | 1 | 4 | 3 | 1 |
| 6 | 0 | 1 | 5 | 3 | 2 |

All six classes were explicitly constructed.  Restriction to $B$ was tested
by complement enumeration in the full inverse image, rather than inferred
from split data.  Consequently this fixed exact-gap-two pair has no
elementary-abelian minimal-normal exceptional lift in any characteristic,
split or nonsplit.

This completes a second infinite family of proposed lifts.

## 8. Extraspecial-tower frontier

[Glasby and Howlett](https://arxiv.org/abs/1405.7228) construct the tower

\[
\operatorname{GL}_2(3)\ltimes E\ltimes Q_3\ltimes E_4
\]

of order $2^{11}3^{13}$ and ambient derived length 10.  Their paper proves
existence of the actions but does not give the derived lengths of the full
preimages of the Borel subgroup.

The present finite first-layer calculation found five irreducible
$\mathbf F_2H$-modules of dimension at most 6.  Exactly three are
terminal-active, faithful, and 6-dimensional.  For each of those three modules, the
space of $H$-invariant quadratic forms has dimension 1 and contains exactly
one nonzero form; that form is nondegenerate of minus type.  Thus the first
$Q_3$ layer is reduced to precisely three module/form pairs:

\[
(V_3,q_3),\quad(V_4,q_4),\quad(V_5,q_5),
\]

using the indices in `tower_frontier.csv`.

For each pair, the remaining finite problem is to solve the inner-lift
coherence equations for the action on the extraspecial group $Q_3$, build

\[
H_1=Q_3\rtimes H,\qquad L_1=Q_3\rtimes L,
\]

and compute $d(H_1)$, $d(L_1)$, and terminal containment.  At least one
coherent action exists by the cited construction, but the local corpus does
not identify which of the three GAP module labels it realizes.  If none of
the three first layers is terminal-escaping, the $E_4$ layer is pruned.  If
one escapes, it becomes the next priority seed before any further tower layer.

This is the precise finite next frontier; the ambient tower alone is not a
gap-four candidate until the maximal-preimage lengths are computed.

## 9. Candidates and remaining obstruction

`gap4_candidates.csv` contains no data rows.  There is no smallest explicit
gap-four candidate.

The exact obstruction remains the absence of a terminal-escaping exact-gap-three
seed

\[
H^{(d(L)+2)}\nleq L^{(d(L)-1)}.
\]

The next computation should solve the three first-layer $Q_3$ coherence
problems above.  In parallel, the 21 recursive exact-gap-two seeds can receive
integral certificates if a complete all-characteristic exclusion of that
bounded seed database is desired.  Nonsplit $H^2$ work above a gap-three
seed remains unjustified until terminal escape is found.

## 10. Scope limitations

- Only one of the three order-1296 controls received the new integral
  certificate.  The other two remain covered by the earlier modular tests and
  terminal-containment pruning.
- The recursive 21-pair lift test used five prime characteristics, not an
  integral certificate for every pair.
- The Sage checker is supplied but was not executed because SageMath is not
  installed locally.
- The Glasby-Howlett inner-lift coherence equations and maximal-preimage
  derived lengths remain unresolved.
- Higher extraspecial ranks, core-top, crown, diagonal, fiber-product, and
  general subdirect families are not claimed eliminated.
- No theorem about the universal bound is inferred from these computations.
