# Proof dossier: saturation and the operator-module obstruction in the metabelian-core case

## Local setting

Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). Assume that (G,M) is a minimal-order counterexample to d(G)-d(M)≤2. Write

a=d(G), b=d(M), r=d(K), h=d(M/K), ε=d(G/K)-d(M/K).

The verified minimal-counterexample lemma gives a=b+3 and a unique minimal normal subgroup A≤K' such that A=G^(a-1), d(G/A)=a-1, and d(M/A)=b. Monakhov's affine primitive reduction gives ε∈{0,1}.

## Lemma 1: core-complexity inequality

One has r+ε≥3. Consequently, if ε=0 then r≥3. If r=2, then necessarily ε=1 and h=b.

Proof. The extension inequality and the definition of ε give

a≤d(K)+d(G/K)=r+h+ε.

Since a=b+3 and h≤b,

b+3≤r+h+ε≤r+b+ε,

so r+ε≥3. If ε=0 this gives r≥3. If r=2, it forces ε=1. In that case

b+3=a≤2+h+1=h+3≤b+3,

and hence equality holds throughout, in particular h=b and d(G/K)=b+1. ∎

Thus the first unresolved core case is rigid: a metabelian core is possible only when the primitive quotient contributes its full extra derived layer and quotienting M by K does not shorten M at all.

## Lemma 2: the terminal affine term

Assume r=2. Put P=G/K and H=M/K. Let V=F(P), and let N be its full inverse image in G. Then

P=V⋊H, d(P)=b+1, d(H)=b, and P^(b)=V.

Proof. The source adaptation gives that V is the unique elementary abelian minimal normal subgroup of P, that H acts irreducibly on V, and that P=V⋊H. Lemma 1 gives d(P)=b+1 and d(H)=b. Since P/V≅H, P^(b)≤V. It is nontrivial because d(P)=b+1. Moreover P^(b) is characteristic in P, hence is an H-invariant nonzero subgroup of V. Irreducibility forces P^(b)=V. ∎

Let L=G^(b). Its image in P is P^(b)=V. Therefore L≤N, LK=N, and, since P=VH and K≤M,

G=LM.

Also N∩M=K, so

L∩M=L∩K.

The minimal-counterexample identities give

L''=G^(b+2)=A≠1 and L'''=1;

thus L has derived length exactly three. Since P^(b+1)=1, one also has L'=G^(b+1)≤K.

## Lemma 3: the nonzero operator-module obstruction

Let B=K' and define

W=L'B/B≤K/B.

Then K/B is naturally a ZP-module under conjugation, W is a nonzero P-submodule, and the G-normal lift S=L' of W satisfies

S'=A≠1.

Proof. Because B is characteristic in the normal subgroup K, it is normal in G. Conjugation by an element of K acts trivially on K/B: for x,k∈K, x^kB=x[x,k]B=xB. Hence the conjugation action of G on K/B factors through P=G/K, making K/B a ZP-module.

Both L' and B are normal in G, so W is P-invariant. If W were zero, then L'≤B. But r=2 means B=K' is abelian, and hence L''=1, contradicting L''=A≠1. Thus W≠0. Finally S=L' is G-normal, maps onto W with kernel S∩B, and S'=L''=A. ∎

This isolates the extra unmatched derived layer. It cannot arise merely from the affine chief factor V. It requires a nonzero P-submodule W of the abelianization K/K' together with a G-normal, nonabelian lift S≤K whose derived subgroup is the unique minimal normal subgroup A.

## Representation switch

Three representations were compared.

1. Derived-delay representation: the obstruction is numerical, through a=b+3 and a≤r+h+ε. This proves r+ε≥3 but does not locate the last commutator.
2. Affine permutation representation: P=V⋊H and P^(b)=V identify L=G^(b) as a normal supplement generating G with M. This locates the terminal quotient layer but still hides the structure inside K.
3. Operator-module/extension representation: W=L'K'/K' is a nonzero P-submodule of K/K', and L' is a nonabelian G-normal lift with (L')'=A. This turns the metabelian-core case into a concrete extension problem.

The third representation is chosen because proving W=0, equivalently L'≤K', immediately gives L''=1 and contradicts the minimal-counterexample package. The implication back to the original obligation is exact. The converse is deliberately not asserted: an abstract module W and an abstract nonabelian lift do not reconstruct a counterexample without the compatibility, maximality, core, irreducibility, and derived-length conditions.

## Two independent attacks and their outcomes

Attack A, numerical saturation, succeeds: it proves r+ε≥3 and shows that r=2 forces ε=1 and d(M/K)=d(M).

Attack B, terminal affine analysis, succeeds: irreducibility proves P^(b)=V and hence G=G^(b)M.

Attack C, direct comparison with the derived series of M, does not finish. The equality d(M/K)=d(M) is only a derived-length equality; it does not imply that G-derived word values lying in K occur in M^(b). The verified Q8⋊C3 example already warns that a core layer may be invisible to the terminal derived subgroup of M. What remains is therefore an extension-action statement, not another scalar derived-length inequality.

## Source adaptation packet

Source location: V. S. Monakhov, “Indices of Maximal Subgroups of Finite Soluble Groups,” Algebra and Logic 43 (2004), 230–237, DOI 10.1023/B:ALLO.0000035114.00094.62, MathNet paper_id al80, MR2105846, Lemma 4; no arXiv id.

Exact source statement available in the local source card: if P is a finite primitive soluble group with core-free maximal subgroup H, then Φ(P)=1; F(P) is an elementary abelian p-group and the unique minimal normal subgroup; P=F(P)⋊H; and H acts irreducibly on F(P).

Definition dictionary: P=G/K; H=M/K; K=Core_G(M); V=F(P); primitivity is the faithful action on the right cosets of H; the local inverse image of V is N.

Hypothesis dictionary and checks: G is finite soluble, hence so is P. Maximality of M makes H maximal in P. The definition of K makes Core_P(H)=1, so the coset action is faithful and primitive. Thus every hypothesis of Lemma 4 is satisfied.

Local deduction: P=V⋊H with V abelian gives d(P)≤d(H)+1 and therefore ε∈{0,1}. In the saturated metabelian-core case, irreducibility additionally gives P^(b)=V.

Reusable proof moves: pass to the core-free primitive quotient; identify its regular elementary abelian minimal normal subgroup; use irreducibility to identify a nonzero characteristic subgroup contained in V with all of V.

Failure boundary: Lemma 4 contains no information about the action of P on K/K', the extension 1→K'→K→K/K'→1, or the nonabelian lift L'. It therefore cannot rule out W by itself.

## Full-root assembly and exact remaining bridge

The certified lower-bound example gives k≥2. The certified abelian-core lemma handles r≤1, and the minimal-counterexample lemma reduces any failure of the upper bound two to exact gap three. The present dossier further proves that every such counterexample satisfies r+ε≥3, and that the r=2 case necessarily produces the nonzero module-lift package (P,W,L',A) above.

Consequently the metabelian-core case is closed as soon as one proves the following exact bridge:

If P=V⋊H is the primitive affine quotient described above, d(H)=d(M)=b, K is metabelian, and L=G^(b), then L'≤K'.

Indeed K' is abelian, so this inclusion gives L''=1, contradicting L''=A≠1. A counterexample to the bridge must instead supply a nonzero P-submodule W=L'K'/K' and a compatible G-normal lift L' with (L')'=A, while preserving all original maximality and derived-length conditions. The cases r≥3 remain separate after the metabelian case is resolved.

## Self-check

The use of irreducibility occurs only after proving P^(b) is nonzero and contained in V. The action on K/K' factors through P because inner automorphisms from K are trivial on the abelianization. W is treated as a ZP-submodule, not assumed to be a vector space over one field. No converse construction from W is claimed. No step asserts the root theorem or the metabelian bridge is proved.
