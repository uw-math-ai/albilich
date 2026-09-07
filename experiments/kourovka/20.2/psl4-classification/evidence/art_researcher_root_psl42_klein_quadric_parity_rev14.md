# A self-contained Klein-quadric proof for PSL_4(2)

## Theorem

The finite simple group PSL_4(2) is not totally 3-closed.

## 1. The 28-point orthogonal model

Let V=F_2^4 with basis e_1,e_2,e_3,e_4, and put W=Λ^2V. For

u=Σ_{i<j} a_{ij}e_i∧e_j

define

q(u)=a_{12}a_{34}+a_{13}a_{24}+a_{14}a_{23}.

Its polar form b(u,v)=q(u+v)+q(u)+q(v) is nondegenerate. The three pairs

(e_1∧e_2,e_3∧e_4), (e_1∧e_3,e_2∧e_4), (e_1∧e_4,e_2∧e_3)

are hyperbolic pairs, so (W,q) is a six-dimensional plus-type quadratic space of Witt index three. The Plücker relation says that a nonzero bivector u is decomposable exactly when q(u)=0. Equivalently, q is the Pfaffian of the alternating 4 by 4 matrix represented by u.

Let G=GL(V). Since F_2 has only one nonzero scalar, G=SL_4(2)=PSL_4(2). Exterior squaring gives

ρ:G→O(W,q),  ρ(g)=Λ^2g,

because q(Λ^2g(u))=det(g)q(u)=q(u). This representation is faithful: if Λ^2g is the identity, then g fixes every projective line of PG(V), hence every projective point, and therefore is scalar; over F_2 that scalar is one.

Put X={u∈W:q(u)=1}. In hyperbolic coordinates q=Σ_{i=1}^3 x_i y_i. There are 8 choices with x=0 and 7·4 choices with x nonzero for which q=0, hence |X|=64-(8+28)=28. Every member of X is a nondegenerate alternating bivector, and the symplectic normal form shows that G is transitive on X. The stabilizer of

r_0=e_1∧e_2+e_3∧e_4

is Sp_4(2). Thus this is precisely the degree-28 action G/Sp_4(2) from the earlier dossier.

The action is faithful. Indeed X spans W. To see this, write W with hyperbolic basis a_i,b_i for 1≤i≤3. The six nonsingular vectors

a_1+b_1, a_2+b_2, a_3+b_3, a_1+b_1+a_2, a_1+b_1+a_3, a_2+b_2+a_1

span all a_i,b_i.

## 2. Ruling parity and the exact index-two overgroup

For a projective point P of PG(V) and a projective hyperplane H define

A_P=P∧V,  B_H=Λ^2H.

These are three-dimensional totally singular subspaces of W. They are all the maximal totally singular subspaces, in two families.

Here is a direct proof. The seven nonzero vectors of a three-dimensional totally singular subspace M correspond through the Plücker map to seven projective lines of PG(3,2). Any two of those lines meet, because b(u,v)=0 is equivalent to u∧v=0. Choose two distinct lines L_1,L_2, let P=L_1∩L_2, and let H be the plane they span. Any line meeting both L_1 and L_2 either passes through P or lies in H. If the family contains a line in H not through P, then a line through P but outside H would be disjoint from it, so all seven lines lie in H. Otherwise all seven pass through P. Since a point-star and a plane each contain exactly seven lines, M is respectively A_P or B_H.

For distinct points P,Q, dim(A_P∩A_Q)=1. For distinct hyperplanes H,K, dim(B_H∩B_K)=1. Across the two families,

dim(A_P∩B_H)=2 if P≤H, and 0 otherwise.

Consequently every element of O(W,q) either preserves both families or interchanges them. Let K be the subgroup preserving the two families.

We claim K=ρ(G). The inclusion ρ(G)≤K is immediate. Conversely, k∈K induces bijections on the points and hyperplanes of PG(V), and the displayed intersection dimensions show that these bijections preserve incidence. This incidence automorphism is induced by a linear map g∈GL(V): choose four independent point images to define g; over F_2, every projective line through independent vectors u,v has the unique third point u+v, so induction on support shows that the incidence map sends every point represented by Σ e_i to the point represented by Σ g(e_i). Now k and ρ(g) agree on every singular vector. Indeed, the vector representing the projective line through P and Q is the unique nonzero vector in A_P∩A_Q, uniqueness being literal over F_2. Singular decomposable bivectors span W, so k=ρ(g). This proves K=ρ(G).

For r∈X define the orthogonal symmetry

τ_r(w)=w+b(w,r)r.

Since q(r)=1, direct substitution gives q(τ_r(w))=q(w), and τ_r is an involution. For r_0 as above,

τ_{r_0}(A_{⟨e_1⟩})=span(e_3∧e_4,e_1∧e_3,e_1∧e_4)=B_{⟨e_1,e_3,e_4⟩}.

Thus τ_{r_0} interchanges the two rulings and lies outside ρ(G). Since G is transitive on X and ρ(g)τ_rρ(g)^{-1}=τ_{ρ(g)r}, every τ_r with r∈X interchanges the rulings. Hence O(W,q)/ρ(G) has order two, detected by ruling parity.

## 3. Every ordered triple has an odd pointwise stabilizer

Fix an ordered triple T=(x_1,x_2,x_3)∈X^3, allowing repetitions, and let U=span(x_1,x_2,x_3). We claim that U^⊥ contains some r∈X.

If dim U≤2, then dim U^⊥≥4, whereas a totally singular subspace of the plus-type six-space has dimension at most three. Hence U^⊥ contains a nonsingular vector. If dim U=3 and U^⊥ contained no nonsingular vector, then U^⊥ would be a three-dimensional totally singular subspace. It would satisfy U^⊥≤(U^⊥)^⊥=U, and equality of dimensions would give U^⊥=U. This would make U totally singular, contradicting q(x_i)=1. The claim follows in all cases.

Choose r∈U^⊥∩X. Then τ_r fixes x_1,x_2,x_3 pointwise. Let δ=τ_{r_0}. Both δ and τ_r interchange the rulings, so δτ_r preserves them and therefore belongs to K=ρ(G). Since τ_r fixes T,

δ(T)=(δτ_r)(T)∈G·T.

Thus δ sends every ordered triple to a triple in its own G-orbit. Equivalently, δ belongs to the 3-closure of the permutation group induced by G on X.

The induced permutation δ is not in G. Otherwise δ and some ρ(g) would agree on X; their quotient would fix X pointwise, hence fix the spanning set X and all of W, contradicting δ∉ρ(G). Therefore

G < G^(3)

in this faithful degree-28 action. This proves that PSL_4(2) is not totally 3-closed.

## 4. Relation to the earlier two-subset argument

The ruling-preserving subgroup ρ(G) and the full orthogonal group play the roles of A_8 and S_8. An odd transposition fixing two unused letters is replaced by a symmetry τ_r whose nonsingular center lies in the orthogonal complement of the three triple entries. The dimension argument proving U^⊥∩X≠∅ is the exact linear-algebraic counterpart of the unused-letter argument, but it avoids both the exceptional isomorphism PSL_4(2)≅A_8 and the aggregate finite computation.

## 5. Assembly and self-check

This closes only the residual parameter (n,p)=(4,2). Together with the certified survivor PSL_3(2)≅PSL_2(7), it reduces the higher-rank classification to the still-open residual exclusion theorem for gcd(n,p-1)=1 with (n,p) outside {(3,2),(4,2)}.

All repeated-coordinate and linearly dependent triples are covered because the proof uses dim span(x_1,x_2,x_3)≤3 rather than assuming three distinct independent entries. Faithfulness is proved directly. The assertion that δ is outside the permutation image uses that X spans W. No CAS output, exceptional-group isomorphism, external classification, or unproved orbit enumeration is used.
