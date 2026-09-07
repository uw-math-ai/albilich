# Proof dossier: affine quotient, core delay, and the shape of a minimal counterexample

Throughout, d(1)=0 and a nontrivial abelian group has derived length 1. Let G be finite soluble, let M be maximal in G, and put K=Core_G(M).

## 1. The primitive affine quotient

The quotient pair (G/K,M/K) is primitive and core-free. Choose a minimal normal subgroup V/K of G/K. Because G/K is soluble, V/K is elementary abelian. Its orbits in the primitive action on the cosets of M/K form a block system, so V/K is transitive. Hence G/K=(V/K)(M/K). Moreover (V/K)∩(M/K) is normalized by M/K and, since V/K is abelian, also by V/K; it is therefore normal in G/K. Core-freeness makes this intersection trivial. Thus

G/K = (V/K) ⋊ (M/K),

with V/K elementary abelian. Consequently

d(G/K) ≤ d(M/K)+1.

Since M/K is a subgroup of G/K, the reverse inequality d(M/K)≤d(G/K) also holds. Therefore

ε(G,M):=d(G/K)-d(M/K) belongs to {0,1}.

For comparison, if M is normal then G/M is cyclic of prime order and G^(i+1)≤M^(i) for every i, so d(G)-d(M)≤1.

## 2. Exact core-delay accounting

For X equal to G or M define

λ_X(K):=d(X)-d(X/K).

Then the desired difference has the exact decomposition

d(G)-d(M)=ε(G,M)+λ_G(K)-λ_M(K).                 (1)

Thus primitive permutation-group theory accounts for at most one unit. Every possible larger gap is caused by an asymmetric derived-length delay across the common core K.

This is also a round-trip translation: starting from the coset action gives K and ε; substituting the definitions of the two λ terms in (1) recovers the original difference identically.

## 3. A proved sharp case: abelian core

Claim. If K is abelian, then d(G)-d(M)≤2.

Proof. An extension by an abelian normal subgroup raises derived length by at most one, so

d(G)≤d(G/K)+1.

By the affine quotient argument,

d(G/K)≤d(M/K)+1≤d(M)+1.

Combining the inequalities gives d(G)≤d(M)+2. In the delay notation, λ_G(K)≤1 and λ_M(K)≥0, so (1) gives the same conclusion. In particular, any counterexample to the proposed sharp bound 2 must have nonabelian core. ∎

The core-free case K=1 is sharper: d(G)-d(M)≤1.

## 4. A self-contained equality example, proving k≥2

Let Q=Q8={±1,±i,±j,±k}. Let α be the automorphism of order 3 cycling i,j,k, and put

G=Q ⋊ ⟨α⟩.

Let Z={±1}=Z(Q) and M=Z×⟨α⟩, a cyclic group of order 6.

Maximality: if M≤H≤G, then H=(H∩Q)M. The subgroup H∩Q contains Z and is α-invariant. The only subgroups of Q containing Z are Z, the three cyclic subgroups of order 4, and Q; α cycles the three order-4 subgroups. Hence the only α-invariant possibilities are Z and Q, giving H=M or H=G. Thus M is maximal.

Derived lengths: G/Q is abelian, while [i,α]=i^(-1)i^α=-k and [j,α]=-i, so [Q,α]=Q. Hence G'=Q. Also Q'=Z and Z'=1, so d(G)=3. Since M is nontrivial abelian, d(M)=1. Therefore d(G)-d(M)=2.

Furthermore Core_G(M)=Z: modulo Z the pair is A4 with a Sylow 3-subgroup, whose core is trivial. Thus equality already occurs in the abelian-core case. Any universal constant must satisfy k≥2.

## 5. Shape theorem for a minimal counterexample to k=2

Claim. Suppose some pair satisfies d(G)-d(M)>2, and choose such a pair with |G| minimal. Write a=d(G), b=d(M), and K=Core_G(M). Then:

1. M is nonnormal and K is nonabelian;
2. a-b=3;
3. K' contains a unique minimal normal subgroup A of G;
4. A=G^(a-1);
5. d(G/A)=a-1, d(M/A)=b, and d(G/A)-d(M/A)=2.

Proof. Normal maximal subgroups have gap at most 1, and Section 3 treats abelian K, proving (1). Since K' is a nontrivial normal subgroup of the finite soluble group G, choose a minimal normal subgroup A of G with A≤K'. Then A is elementary abelian and A≤M. The subgroup M/A is maximal in G/A, so minimality of |G| gives

d(G/A)-d(M/A)≤2.                                      (2)

An abelian extension changes derived length by at most one. Hence there are x,y∈{0,1} such that

d(G/A)=a-x,   d(M/A)=b-y.

Put g=a-b≥3. The left side of (2) is g-x+y. Its minimum possible value is g-1. Therefore (2) forces g=3, x=1, and y=0. This proves (2) and (5). Since d(G/A)=a-1, the nontrivial group G^(a-1) lies in A. Minimality of A gives A=G^(a-1), proving (4). Applying the same argument to any minimal normal subgroup of G contained in K' identifies it with G^(a-1), so A is unique in K', proving (3). ∎

Thus a counterexample to k=2 cannot be diffuse: it must be a one-layer asymmetric lift of an already extremal gap-2 quotient. The added minimal normal layer A is the last derived subgroup of G, but quotienting by A does not reduce the derived length of M.

## 6. Full-root assembly attempt and remaining theorem-level gap

If no extension having the structural package in Section 5 exists, then every pair has gap at most 2. Section 4 would then show that the minimum constant is exactly k=2.

The single remaining theorem-level obligation is therefore:

Rule out a finite soluble pair (G,M) in which M is maximal, K=Core_G(M) is nonabelian, A=G^(d(G)-1) is the unique minimal normal subgroup inside K', the quotient pair (G/A,M/A) has gap 2, and d(M/A)=d(M).

Equivalently, classify one-layer extensions of sharp gap-2 quotient pairs and prove that a layer which raises d(G) must also raise d(M). A counterexample to this statement would immediately produce a genuine gap-3 pair and change the candidate minimum.

## 7. Source adaptation

V. S. Monakhov, “Indices of Maximal Subgroups of Finite Soluble Groups,” Algebra and Logic 43 (2004), 230–237, DOI 10.1023/B:ALLO.0000035114.00094.62, MathNet paper_id al80, MR2105846, Lemma 4, no arXiv id. The lemma states that a finite primitive soluble group P with core-free maximal subgroup H has Φ(P)=1; its Fitting subgroup is an elementary abelian p-group, is the unique minimal normal subgroup, and P=F(P)⋊H; moreover H acts irreducibly on F(P). In local notation P=G/K and H=M/K. The deduction needed here is only that the normal factor is abelian and P is its semidirect product with H, giving d(P)≤d(H)+1. The argument in Section 1 reproves that portion directly, so no unexpanded black box remains.

## 8. Self-check

The subgroup M in the equality example was checked for maximality rather than merely asserted. The commutators explicitly give G'=Q8 and Q8'=Z. The primitive reduction uses core-freeness exactly once to make the regular normal subgroup intersect the point stabilizer trivially. The abelian-core proof uses only the standard extension inequality d(X)≤d(N)+d(X/N). In the minimal-counterexample argument, A≤K' guarantees A≤M, so the quotient maximal subgroup is legitimate. No step claims the root theorem is solved; the nonabelian-core one-layer extension obstruction remains open.
