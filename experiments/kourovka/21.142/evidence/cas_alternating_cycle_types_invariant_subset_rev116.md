# CAS experiment: a uniform intransitive subgroup for alternating factors

## Mathematical question

For distinct primes p and q and n>pq, does one fixed intransitive subgroup D=Stab_{S_n}(K), |K|=pq, meet, up to A_n-conjugacy, every conjugacy class of elements whose order divides p or q? A positive answer supplies the elementwise input needed by the wreath-cycle gauge; a negative cycle type would kill this construction.

## Competing hypotheses

H1: every order-dividing-r cycle type, r in {p,q}, has an invariant pq-subset once n>=pq+1.

H2: for some p,q,n and number c of r-cycles, the available invariant-set sizes miss pq.

## Finite experiment

Backend: Python 3 standard library, used as a bounded exhaustive combinatorial checker because no CAS lifecycle backend is exposed in this manifest. The experiment considered all 15 unordered pairs from {2,3,5,7,11,13}; for each pair it used n=pq+1, pq+2, and 2pq; for r=p and r=q it enumerated every c from 0 to floor(n/r). Thus 915 cycle types were checked.

from itertools import combinations
primes=[2,3,5,7,11,13]

def invariant_sizes(n,r,c):
    f=n-r*c
    return {r*a+b for a in range(c+1) for b in range(f+1)}

def universal_sizes(n,r):
    u=set(range(n+1))
    for c in range(n//r+1):
        u &= invariant_sizes(n,r,c)
    return u

checked_types=0
for p,q in combinations(primes,2):
    for n in (p*q+1,p*q+2,2*p*q):
        k=p*q
        assert k in universal_sizes(n,p)
        assert k in universal_sizes(n,q)
        for r,s in ((p,q),(q,p)):
            for c in range(n//r+1):
                f=n-r*c
                a=min(c,s)
                b=k-r*a
                assert 0<=a<=c and 0<=b<=f and r*a+b==k
                checked_types += 1
print("all_15_prime_pairs_passed=True")
print("cycle_types_checked=",checked_types)

Output:

all_15_prime_pairs_passed=True
cycle_types_checked=915

## Structured observation and symbolic extraction

For an r-element with c disjoint r-cycles, put s equal to the other prime, k=rs, and f=n-rc. The successful witness is a=min(c,s), b=k-ra. Choose the supports of a r-cycles and b fixed points. If c>=s then b=0. If c<s then b=r(s-c), while f=n-rc>=rs+1-rc=r(s-c)+1>b. Hence every order-dividing-r element preserves a k-subset.

No counterexample occurred in the finite scope. At n=pq the designated k-set is the entire point set, so D is not proper; the construction requires n>=pq+1.

## Decision and proof relevance

The experiment decided the alternating branch in favor of H1 and exposed the exact witness needed for a proof. It does not certify the infinite statement; the companion dossier supplies the symbolic argument, parity correction, and wreath-product gauge. After verification, the next root bottleneck is the terminal exclusion of sufficiently large A_m from bounded-natural-dimension classical, exceptional, and sporadic simple factors.
