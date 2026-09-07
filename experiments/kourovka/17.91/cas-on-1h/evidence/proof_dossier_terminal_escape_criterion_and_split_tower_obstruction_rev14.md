# Universal terminal-escape criterion and a split-tower obstruction

## 1. Exact quotient criterion

Let B be maximal in a finite soluble group K, with d(B)=s and d(K)=s+2, where s≥1. Let F be a finite field, R=F[K], and I(X) the F-span of the elements x−1 for x in X. Put

A_K=I(K)I(K')⋯I(K^(s+1)),
P_B=I(B)I(B')⋯I(B^(s−1)),
Q_B=I(B)I(B')⋯I(B^(s−2)).

For s=1, interpret Q_B as F·1. Finally put

J_B=R P_B R,
E_B=R Q_B+J_B.

Here E_B is only required to be an F-subspace of R; it need not be a right ideal.

### Theorem

There exists a finite right FK-module V such that, for

H=V⋊K and L=V⋊B,

L is maximal in H,

d(H)=s+3,
d(L)=s,

and

H^(s+2) is not contained in L^(s−1)

if and only if

R A_K is not contained in E_B.

When this containment fails, the universal witness is V=R/J_B.

### Proof

For every right FK-module V, the standard commutator calculation gives

(V⋊K)^(n)=V I(K)I(K')⋯I(K^(n−1))⋊K^(n),

and the analogous formula for B. Hence

H^(s+2)=V A_K,
L^s=V P_B,

while

L^(s−1)∩V=V Q_B.

The last equality also holds for s=1 under the convention Q_B=F·1, because L^0∩V=V.

Suppose first that a module V has all the stated properties. Since d(L)=s, the formula for L^s gives V P_B=0. Therefore

VJ_B=V(RP_BR)=(VR)P_BR=VP_BR=0.

If RA_K were contained in RQ_B+J_B, then

VA_K=VRA_K⊆VRQ_B+VJ_B=VQ_B,

contradicting H^(s+2) not contained in L^(s−1). This proves necessity.

Conversely, assume RA_K is not contained in RQ_B+J_B and take V=R/J_B. Then VP_B=0. Moreover,

VA_K=(RA_K+J_B)/J_B,
VQ_B=(RQ_B+J_B)/J_B.

The assumed noncontainment therefore gives VA_K not contained in VQ_B. In particular VA_K is nonzero. Since K has derived length s+2, the displayed derived-series formula now gives d(H)=s+3. Since VP_B=0 and L maps onto B, it gives d(L)=s. The same formula and VA_K not contained in VQ_B give the terminal-escape condition. Finally L is the full inverse image of the maximal subgroup B under H→K, so L is maximal in H. The module R/J_B is finite because F and K are finite.

This proves both directions without irreducibility, semisimplicity, or a choice of characteristic.

## 2. All-characteristic form

For an explicitly presented pair (K,B), define the corresponding integral lattices

X_Z=Z[K] A_K,
E_Z=Z[K] Q_B+Z[K] P_B Z[K].

Integral augmentation products and two-sided ideal generation commute with reduction modulo every prime. Thus the already verified exact Smith-row lemma applies with X_Z as the numerator lattice and E_Z as the comparison lattice. One Smith packet therefore decides RA_K⊆E_B in every characteristic, including all rank-drop primes. This turns construction of a terminal-escaping split gap-three seed into one exact finite group-algebra certificate on an exact gap-two pair.

## 3. Boundary case and obstruction

When s=1, Q_B=F·1 and E_B=R, so the criterion can never hold. This agrees with the direct group argument: H^3≤V≤L=L^0. Consequently no split lift of an exact gap-two pair with abelian maximal subgroup can itself be a terminal-escaping gap-three seed.

There is a stronger obstruction to the tempting strategy of first raising both derived lengths and then making an exceptional split lift.

Let

K_0=Q_8⋊⟨c⟩,

where c has order 3 and cyclically permutes the three quaternion generators. Write z for the central involution of Q_8 and set

B_0=⟨z,c⟩≅C_6.

The commutators with c generate Q_8, so K_0'=Q_8, K_0''=⟨z⟩, and d(K_0)=3. Thus K_0/K_0'≅C_3. The subgroup B_0 has order 6. Any proper overgroup of B_0 would have order 12, hence index 2 and therefore be normal, but K_0 has no quotient of order 2. Hence B_0 is maximal and d(B_0)=1.

For any prime p, let U=F_p[K_0] be the right regular module and form

K_1=U⋊K_0,
B_1=U⋊B_0.

The group-algebra element

(c−1)(i−1)(z−1)

is nonzero: its expansion has eight distinct group-basis terms, four in cQ_8 and four in Q_8. It belongs to

I(K_0)I(K_0')I(K_0''),

so the derived-series formula gives d(K_1)=4. Since B_0 is nontrivial abelian, UI(B_0) is nonzero and B_1'=UI(B_0), while B_1''=1. Hence d(B_1)=2. Maximality of B_1 follows by taking the full inverse image of B_0. Thus (K_1,B_1) is an explicit infinite family of exact gap-two maximal pairs, of orders 24p^24 and 6p^24.

Nevertheless this entire family is unusable for the next split step. Indeed K_1''' is contained in U, and U is contained in B_1. Let k be any finite field and V any right kK_1-module. If

H=V⋊K_1,
L=V⋊B_1,

then

H^4=V I(K_1)I(K_1')I(K_1'')I(K_1''')⊆V I(B_1)⊆L'.

Thus every exact gap-three pair obtained by an arbitrary second split full-preimage lift from (K_1,B_1) is terminal-contained. Equivalently, in the quotient criterion for s=2 one has Q_B=I(B_1), and the last augmentation factor already forces

R A_{K_1}⊆R I(B_1)=R Q_{B_1}.

This is characteristic-independent and excludes every module, not merely irreducible or low-dimensional modules. By the terminal obstruction recorded in the root context, a third elementary-abelian lift of this tower cannot provide the required least gap-four construction.

## 4. Proof spine and root assembly

1. The verified semidirect-product criterion converts a terminal-escaping exact gap-three seed into a gap-four pair whenever its second-stage group-algebra containment fails.
2. The theorem above converts construction of such a terminal-escaping gap-three seed into the first-stage containment test RA_K⊄RQ_B+RP_BR on an exact gap-two maximal pair.
3. The verified Smith-row theorem makes both first- and second-stage containment tests exact and all-characteristic.
4. The split-tower calculation eliminates the canonical regular escalation of the abelian-maximal SL_2(3) seed, and more generally any second split lift whose preceding terminal derived subgroup lies in the common kernel contained in B.

The dependency chain is

exact gap-two seed + first Smith noncontainment → terminal-escaping exact gap-three seed + second Smith noncontainment → explicit split gap-four pair.

Exactly one theorem-level gap remains in this spine: exhibit one explicit exact gap-two maximal pair outside the common-kernel obstruction, together with first- and second-stage Smith packets whose row certificates show the two required noncontainments.

## 5. Failed-route autopsy and self-check

The strongest failed route was to take a cross-characteristic regular lift of the abelian-maximal SL_2(3) seed merely to raise d(B) from 1 to 2 and then attempt another split lift. The common first kernel contains the terminal derived subgroup of the raised ambient group, forcing every subsequent ambient terminal layer into L'; this route is abandoned for all primes and all second-stage modules.

The proof checks the s=1 boundary separately, uses the genuine two-sided ideal RP_BR, and compares H^(s+2) with the exact intersection L^(s−1)∩V rather than merely requiring H^(s+2)≠1. The universal witness is a right module because J_B is two-sided. No modular rank assertion is inferred from the abstract quotient (E_Z+X_Z)/E_Z; the existing Smith-row test is applied directly to genuine generator matrices after reduction.
