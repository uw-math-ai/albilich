# Alternating simple factors: fixed-subset normalizer and wreath gauge

## Local theorem

Fix distinct primes p and q. Let n>=pq+1, S=A_n, and G=Aut(S)=S_n. Put k=pq, let K={1,...,k}, and let D=Stab_G(K)=S_k x S_{n-k}. Then D is proper, DS=G, and, for every t>=1, every X with S^t<=X<=G wr Sym(t), and every x in X of order p or q, an S^t-conjugate of x lies in D wr Sym(t). Consequently, any elements x,y in X of respective orders p and q have independent S^t-conjugates in the same proper subgroup X intersect (D wr Sym(t)); in particular they do not invariably generate X.

## Lemma 1: one fixed subset size meets both prime-order families

Let r be p or q and let s be the other prime, so k=rs. An element g in S_n of order dividing r has c disjoint r-cycles and f=n-rc fixed points.

If c>=s, the union of the supports of any s cycles is a g-invariant k-set. If c<s, take the supports of all c cycles and add r(s-c) fixed points. There are enough fixed points because f=n-rc>=rs+1-rc=r(s-c)+1. Thus every element of order dividing p or q preserves a k-subset.

A permutation u sends that subset to K, so g^u lies in D. We can require u in A_n. Indeed k=pq>=6, hence D contains an odd transposition d supported in K. If u is odd, replace it by ud; then ud is even and g^(ud)=(g^u)^d remains in D. Therefore every order-dividing-p or order-dividing-q element of G is S-conjugate into D.

Also d is odd, so DS=G because S has index two in G. Since k<n, D is proper. The standard equality Aut(A_n)=S_n applies because n>=pq+1>=7; the exceptional outer automorphisms of A_6 do not occur.

## Lemma 2: wreath-cycle gauge

Let S be normal in a finite group G, let D<=G satisfy DS=G, and fix a prime r. Assume every element of G of order dividing r is S-conjugate into D. Then every order-r element of G wr Sym(t) is S^t-conjugate into D wr Sym(t).

Write such an element as z=(g_1,...,g_t;sigma). Since sigma has order dividing r, every cycle of sigma has length ell=1 or ell=r. On one cycle, order the labels as g_1,...,g_ell and put c=g_1...g_ell. From z^r=1, c has order dividing r/ell and hence dividing r. Choose h_1 in S with h_1^{-1}ch_1 in D.

For i<ell choose d_i in D with d_iS=g_iS, possible because DS=G, and define h_{i+1}=g_i^{-1}h_id_i. Normality of S and equality of the cosets imply h_{i+1} lies in S. Put d_ell=h_ell^{-1}g_ellh_1. Then d_1...d_ell=h_1^{-1}ch_1 lies in D. Since d_1,...,d_{ell-1} lie in D, so does d_ell. Conjugation by the base element (h_i) changes the labels on this cycle to the d_i. Doing this independently on all cycles proves the lemma.

## Proof of the local theorem

Apply Lemma 2 with r=p and r=q. For x and y of orders p and q there are a,b in S^t such that x^a and y^b lie in D wr Sym(t). Since S^t<=X, both conjugates remain in X and hence lie in M=X intersect (D wr Sym(t)).

The subgroup M is proper. Choose s in A_n that does not stabilize K; the base element supported by s in one coordinate belongs to S^t<=X but not to D wr Sym(t). Therefore M<X, and the selected conjugates generate a subgroup of M rather than X.

## Root synthesis and one remaining theorem-level gap

The integrated minimal-host lemma reduces any hypothetical host of a sufficiently large A_m to S^t<=X<=Aut(S) wr Sym(t), with A_m embedded in the simple factor S. The integrated PSL, PSp, PSU, and orthogonal modules exclude high-dimensional classical S. The theorem above excludes alternating S=A_n once m>=pq+1: an embedding A_m<=A_n forces n>=m because |A_m|=m!/2>n! when n<m.

Thus the alternating branch is a closed local module. Exactly one terminal theorem-level gap remains: establish a characteristic-uniform bound, for each fixed natural dimension or rank bound, on m when A_m embeds in a bounded-dimensional classical or exceptional simple group, and absorb the finite sporadic list. This projective-degree cutoff is not proved here.

## Representation switch

The first representation is geometric and permutational: prime-order classes are cycle counts, and the common overgroup is the stabilizer of a pq-subset. The second is quotient-cohomological: a wreath label is represented by its cycle product and coordinate classes in G/S=C_2. The dictionary is invariant pq-subset to conjugacy into D, parity to outer coset, and top-cycle product to residual gauge invariant. The first representation proves elementwise placement; the second reduces t-factor assembly to Lemma 2.

## Counterexample and self-check

The stronger threshold n>=pq fails for this construction at n=pq because the pq-set is the whole domain and D=G. The parity correction is valid because k>=6. The A_6 exception is excluded by n>=7. Identity cycle products are covered by order dividing r. Top permutation cycles have only lengths 1 and r because r is prime. Properness is checked inside X. No external citation or verification status is asserted.
