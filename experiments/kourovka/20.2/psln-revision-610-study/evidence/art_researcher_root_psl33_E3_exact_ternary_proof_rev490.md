# E3: exceptional parabolic coset actions of PSL_3(3)

## Statement

Let G=PSL_3(3), let P be a point stabilizer, and put E(P)={H<P proper: H intersects H^g nontrivially for every g in G}. Then E(P) consists of 24 subgroups forming six G-conjugacy classes, with representatives of orders 48,54,72,108,144,216. For every H in E(P), the faithful transitive action of G on G/H is 3-closed. The analogous assertion holds for the dual line-parabolic family.

## Proof

Because gcd(3,3-1)=1, SL_3(3) has trivial center and equals PSL_3(3). Its six elementary transvections generate the faithfully represented order-5616 group on the 13 projective points. The exact calculation in art_researcher_root_psl33_E3_exact_ternary_cas_rev490 constructs the order-432 point stabilizer P and enumerates its subgroup lattice by the following exhaustive induction: starting with the identity subgroup, for every recorded H it adjoins one representative x from each left H-coset and records <H,x>. Every subgroup K is reached by adjoining a finite generating sequence for K, so the resulting 646-member list is complete.

For each of the 645 proper H<P and each g in G the calculation forms H intersect H^g. Exactly 24 subgroups have no trivial conjugate intersection. Direct G-conjugacy testing partitions them into six classes, one at each order 48,54,72,108,144,216, with respectively 9,4,3,4,3,1 representatives inside the fixed P.

Fix one representative H and write Omega=G/H with base point alpha=H. Let C_H be the coloring of Omega squared by H-orbits. A base-fixing element of the 3-closure must preserve C_H. Exact color-preserving backtracking gives base-local automorphism orders 48,54,72,108,288,1944. Thus the first four classes immediately have no base-local automorphism outside H.

For the remaining classes one must not confuse base-local orbital symmetry with global ternary symmetry. Choose representatives r_i with r_iH=i and put T_i(j)=r_i^{-1}j. The G-orbit of (i,j,k) is determined exactly by C_H(T_i(j),T_i(k)): applying r_i^{-1} carries its first coordinate to alpha, and two triples with first coordinate alpha are G-conjugate precisely when their last two coordinates are H-conjugate. Hence a permutation pi preserves every G-orbit on Omega cubed if and only if

C_H(T_i(j),T_i(k))=C_H(T_{pi(i)}(pi(j)),T_{pi(i)}(pi(k)))

for every i,j,k. Exhaustively imposing these equalities on all base-local color automorphisms leaves stabilizer orders 144 and 216 in the last two cases. In every class, therefore, the stabilizer of alpha in G^(3) has order |H| and equals the image of H. Since G is transitive, G is contained in G^(3), and both groups have the same point stabilizer, |G^(3)|=|Omega||H|=|G|; thus G^(3)=G.

Contragredient duality is an automorphism of G carrying point-parabolic subgroups to the corresponding line-parabolic subgroups and gives permutation-isomorphic coset actions, so the dual classes are also 3-closed.

## Root assembly boundary

This proves E3 only. Combined with the prior two-point-base sieve it removes every exceptional transitive constituent as an individual nonclosure witness. It does not decide diagonal actions on two exceptional constituents, and it does not replace the separate maximal-subgroup completeness requirement. The next exact theorem is M3 for G/H disjoint union G/K.

## Self-check

The group representation is faithful; all subgroups of P and all conjugators are enumerated; conjugacy is tested in G rather than merely in P; coset conventions are left cosets with left G-action; local orbital automorphisms are treated only as necessary candidates; the transport formula checks every ordered triple, including repeats; and no statement about the infinite residual PSL family is inferred.
