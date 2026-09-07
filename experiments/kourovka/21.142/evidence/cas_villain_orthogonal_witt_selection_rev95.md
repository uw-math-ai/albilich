# Adversarial test of the orthogonal Witt-selection interface

## Target
The attack targets the block-selection step inside inference `inf_orthogonal_semilinear_decomposition_normalizer_rev69` on route `route_orthogonal_semilinear_decomposition_normalizer_rev69`. For an element of projective prime order r, that step assumes an orthogonal decomposition into nondegenerate invariant blocks of dimensions e<=2r, with at most two quadratic isometry types in each dimension. With R=max(p,q), E=4*lcm(1,...,2R), and n0=4RE, it claims that n>=n0 forces E/e mutually isometric e-blocks for some e; their sum is hyperbolic because E/e is divisible by four.

## Competing structural conjectures
H1: the numerical and Witt-class interface is sound: every admissible block inventory of total dimension at least n0 contains the claimed hyperbolic E-summand.

H2: an adversarial distribution across dimensions and the two quadratic types can have total dimension at least n0 while keeping every type multiplicity below E/e, invalidating the common-overgroup construction before conjugator correction.

## Finite adversarial computation
Python 3 standard-library exact integer arithmetic tested every distinct prime pair drawn from {2,3,5,7} and both r in {p,q}. The search used a relaxation containing every actual quadratic block inventory: it allowed two types in every dimension 1<=e<=2r, even where characteristic-two quadratic spaces impose stronger restrictions. If no E-summand is selectable, each type can occur at most E/e-1 times, so the exact maximum dimension in this relaxed counterexample space is

max_avoid = sum_{e=1}^{2r} 2e(E/e-1).

The code also checked E mod e=0 and (E/e) mod 4=0 for every tested e.

```python
from math import gcd
from itertools import combinations

def lcm(a,b): return a//gcd(a,b)*b
primes=[2,3,5,7]
for p,q in combinations(primes,2):
    R=max(p,q)
    L=1
    for j in range(1,2*R+1): L=lcm(L,j)
    E=4*L
    n0=4*R*E
    for r in (p,q):
        N={e:E//e for e in range(1,2*r+1)}
        assert all(E%e==0 and N[e]%4==0 for e in N)
        max_avoid=sum(2*e*(N[e]-1) for e in N)
        print((p,q),r,E,n0,max_avoid,n0-max_avoid)
```

## Exact output summary
For (p,q)=(2,3), E=240 and n0=2880: max_avoid is 1900 for r=2 and 2838 for r=3, leaving margins 980 and 42.

For (2,5), E=10080 and n0=201600: max_avoid is 80620 for r=2 and 201490 for r=5, leaving margins 120980 and 110.

For (2,7), E=1441440 and n0=40360320: max_avoid is 11531500 for r=2 and 40360110 for r=7, leaving margins 28828820 and 210.

For (3,5): max_avoid is 120918 for r=3 and 201490 for r=5, leaving margins 80682 and 110.

For (3,7): max_avoid is 17297238 for r=3 and 40360110 for r=7, leaving margins 23063082 and 210.

For (5,7): max_avoid is 28828690 for r=5 and 40360110 for r=7, leaving margins 11531630 and 210.

No divisibility failure or relaxed block-inventory counterexample occurred. In the worst cases r=R, the margin is only 2r(2r+1), so the estimate is close to sharp for an argument using only block dimension and the two-type bound.

## Refutation conclusion
Status: not_refuted in the stated finite scope. Because the computed search space strictly contains the inventories arising from actual quadratic spaces, the obvious multiplicity-distribution attack cannot falsify the Witt-selection implication for these six prime pairs. The computation rules out a numerical threshold or fourfold-divisibility failure as the smallest vulnerability of this inference. It exposes near-tightness: lowering n0 below max_avoid+1 cannot be justified from these counting hypotheses alone. The next independent attack should therefore test the preceding structural assertion that every projective prime-order similarity admits the claimed nondegenerate invariant-block decomposition, or the later assertion that the fixed decomposition normalizer realizes every required outer coset; repeating block-count sweeps will not change the proof decision. No infinite statement or full root theorem is certified by this experiment.
