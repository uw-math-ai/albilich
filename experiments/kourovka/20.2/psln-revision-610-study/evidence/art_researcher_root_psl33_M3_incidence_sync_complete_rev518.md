# M3 by projective-quotient synchronization

## Statement

Let G=PSL_3(3). Let P and P* be respectively a point stabilizer and a line stabilizer in the projective plane PG(2,3). Let T be the six G-conjugacy classes of exceptional subgroups H<P identified by E3, and let T* be their dual classes inside P*. Assume the E3 conclusion that every action G/H with H in T union T* is 3-closed. Then, for every H,K in T union T*, including H=K and two distinct copies of the same G-set, the diagonal action of G on

X disjoint-union Y = G/H disjoint-union G/K

is 3-closed.

## Lemma 1: ternary closure preserves binary orbitals

If a permutation sigma preserves every G-orbit on ordered triples, then it preserves every G-orbit on ordered pairs. Indeed, the pair (u,v) is encoded by the triple (u,v,v). If (sigma(u),sigma(v),sigma(v)) lies in the G-orbit of (u,v,v), then some g in G sends u to sigma(u) and v to sigma(v). Consequently sigma preserves every G-invariant binary relation, since such a relation is a union of G-orbits on ordered pairs.

The same diagonal-triple argument shows that sigma preserves X and Y separately, even when they are isomorphic copies: the G-orbits of (x,x,x) belonging to the two copies are distinct.

## Lemma 2: constituent factorization

Take sigma in the 3-closure of the diagonal action on X disjoint-union Y. Its restrictions to X and Y preserve all constituent triple-orbits. By E3, there are a,b in G such that sigma acts as a on X and as b on Y. Composing with the diagonal action of a^{-1}, it is enough to treat

tau|X = 1 and tau|Y = c,

where c=a^{-1}b is in G. Thus M3 reduces to proving c=1.

All exceptional point-type coset actions have a canonical G-map

q_H:G/H -> G/P,  gH |-> gP,

and all exceptional line-type actions have the dual map

l_H:G/H -> G/P*,  gH |-> gP*.

These maps are well defined because H is contained in the relevant parabolic. Independently conjugating H or K does not change the diagonal G-set up to G-isomorphism, so representatives inside the fixed P or P* may be used.

## Lemma 3: the quotient incidence relations force c=1

There are four cases.

### Point-point, including repeated types

Suppose H,K are point-type. On X times Y consider

R_eq={(x,y):q_H(x)=q_K(y)}.

This is G-invariant, hence tau preserves it by Lemma 1. For any y in Y choose x in X above the same projective point. Since tau fixes x,

q_K(cy)=q_H(x)=q_K(y).

By G-equivariance q_K(cy)=c q_K(y). Surjectivity of q_K therefore implies that c fixes all 13 projective points. The projective point action of PSL_3(3) is faithful, so c=1. Nothing in this argument requires H and K to be distinct; it covers two copies of the same exceptional action.

### Line-line, including repeated types

The identical argument uses equality of the underlying lines in G/P*. It implies that c fixes every projective line. The line action is faithful, hence c=1.

### Point-line

Suppose X is point-type and Y is line-type. Define

R_inc={(x,y):q_H(x) is incident with l_K(y)}.

This is G-invariant and is therefore preserved by tau. Fix y above a line L. For every projective point Q choose x above Q. Preservation gives

Q incident with L if and only if Q incident with cL.

Thus L and cL have the same incident point set. A line of PG(2,3) is determined by its points, so cL=L. As L was arbitrary, c fixes every line and hence c=1.

### Line-point

If X is line-type and Y is point-type, preservation of incidence says that a point Q and cQ lie on exactly the same projective lines. Distinct points in a projective plane are separated by their incident-line sets, so cQ=Q for every Q. Again c=1.

These cases exhaust T union T*, including repetitions. Hence tau=1, sigma is the diagonal action of a, and the diagonal action on X disjoint-union Y is 3-closed. This proves M3.

## Short proof spine and assembly

1. E3 gives 3-closedness of each exceptional constituent.
2. Restriction and normalization give sigma=(1,c) with c in G.
3. Repeated-coordinate triples imply preservation of all binary G-invariant relations.
4. Equality of projective quotients handles point-point and line-line pairs; incidence handles both mixed orientations.
5. Faithfulness of the point and line actions forces c=1.

Thus 1 -> 2 -> 3 -> 4 -> 5 proves M3. For the later PSL_3(3) assembly, the two-point-base synchronization lemma handles every pair with a nonexceptional constituent, E3 handles each exceptional constituent, M3 handles the remaining exceptional-exceptional pairs, and the certified two-orbit reduction then proves total 3-closure once the separate maximal-subgroup completeness input and the exact E3 certificate have passed their own gates.

## Boundary and self-check

The proof uses no unrecorded subgroup classification and no computation beyond the stated E3 premise. It checks that the two constituent copies cannot be interchanged, that triple-orbit preservation really implies binary-relation preservation, that all quotient maps are well defined and surjective, that both mixed orientations and repeated types are covered, and that the final kernel is trivial. The strongest discarded approach was a raw correction-set calculation c in intersections of products H(K^u intersect K^v); it would require unnecessary cross-subgroup tables. Passing to the common projective quotient removes that obstruction completely. There is no remaining gap in M3 itself; exact certification of E3 and maximal-subgroup completeness remain separate upstream assembly obligations.
