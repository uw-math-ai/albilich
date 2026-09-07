# Exact finite all-characteristic certificate

Let R_Z be a free abelian group of rank n, identified with the integral group ring Z[H] in its group basis. Let J_Z and P_Z be sublattices generated respectively by the columns of integer matrices B in Mat(n,m;Z) and A in Mat(n,k;Z). Assume these are the canonical integral generators whose reductions generate J_p and P_p in F_p[H].

Take a Smith normal form

U B V = diag(d_1,...,d_a,0,...,0),

where U and V are unimodular, each d_i is nonzero, d_i divides d_(i+1), and a=rank_Q(B). Put C=U A.

## Lemma

For every prime p, P_p is contained in J_p if and only if both of the following conditions hold:

1. every entry C_(i,j) with i>a is divisible by p;
2. for every i≤a such that p divides d_i, every entry in row i of C is divisible by p.

Consequently this single integral Smith packet classifies containment in every characteristic.

If the tail formed by the rows i>a of C is not zero, let t be the positive gcd of all its entries. Then P_p is not contained in J_p for every prime p not dividing t. For a prime p dividing t, containment is decided by condition 2 above. Thus only the finitely many prime divisors of t can be exceptions to generic noncontainment.

If the tail is zero, then P_Z lies in the saturation of J_Z. Put D=the product of the absolute values |d_1...d_a|, with D=1 when a=0. Then P_p is contained in J_p for every prime p not dividing D. For p dividing D, noncontainment occurs exactly when some row i with p dividing d_i has an entry of C not divisible by p. Thus only the finitely many prime divisors of D can be exceptions to generic containment.

## Proof

Reduce the Smith identity modulo p. Because U and V are unimodular, their reductions are invertible. Hence U identifies the column space of B modulo p with the column space of the diagonal matrix. The latter contains the coordinate direction e_i exactly when i≤a and p does not divide d_i. It contains no nonzero vector in coordinate i when i>a or when i≤a and p divides d_i.

The columns of A lie in the column space of B modulo p precisely when the transformed columns C=UA have zero coordinates in every unavailable direction. These are exactly conditions 1 and 2. This proves the equivalence.

If the tail is nonzero, condition 1 holds precisely when p divides the gcd t of all tail entries, proving the first finite classification. If the tail is zero, condition 1 is automatic. For p not dividing D, none of the d_i vanish modulo p, so every one of the first a coordinate directions is available and containment follows. At a divisor p of D, the displayed row test is exactly condition 2. This proves the second classification.

## Dual certificate

The same result has an independently checkable dual form:

P_p is not contained in J_p if and only if there exists a linear functional lambda on F_p^n such that lambda B=0 but lambda A is nonzero.

Whenever the Smith test detects an unavailable row i containing a nonzero entry of C modulo p, lambda=e_i^T U modulo p is such a functional. Conversely, finite-dimensional linear separation supplies such a lambda whenever containment fails. Thus every positive split-lift decision has a short row-functional certificate, while containment is certified by the row divisibilities above.

## Application to the gap-four problem

For a fixed exact gap-three maximal pair (H,L), take B to generate the genuine two-sided lattice J_Z=Z[H] P_L Z[H] and A to generate P_Z=P_H. The already verified fixed-field criterion says that a split gap-four lift in characteristic p exists exactly when P_p is not contained in J_p. The Smith-row lemma therefore replaces infinitely many modular computations by one integral Smith form and finitely many divisibility checks. It also avoids the invalid shortcut of tensoring (J_Z+P_Z)/J_Z with F_p.

Given an explicit terminal-escaping seed and its genuine matrices A,B, there are two outcomes. If the row criterion gives noncontainment for some p, the verified universal witness F_p[H]/J_p constructs a finite soluble gap-four pair. If it gives containment for every p, all split elementary-abelian lifts of that seed are excluded in every characteristic. Hence the modular-certificate half of the active bottleneck is solved; the remaining root-level input is an explicit terminal-escaping exact gap-three seed with exact group-ring generators.

## Direct construction attack and obstruction

A direct assembly from the manifest's order-1296 seeds cannot supply that input: all three known seeds satisfy H^(5)≤L^(2), so they are terminal-contained. Moreover, the audited computation used a right-closed surrogate of dimension 1230 rather than the genuine two-sided ideal of dimension 1231 in characteristic 3. It therefore cannot be promoted into a terminal-escaping seed or a valid all-characteristic certificate.

## Self-check

The argument uses the exact generator lattices rather than their saturations; reduction of the canonical augmentation products and genuine two-sided ideal generators is the compatibility hypothesis already verified in the fixed-field dossier. Rank drops modulo exceptional primes are included through the factors d_i. The cases J_Z=0, P_Z=0, and full-rank J_Z are covered by the stated empty-product and zero-tail conventions. No Smith invariant of the abstract quotient (J_Z+P_Z)/J_Z is used.
