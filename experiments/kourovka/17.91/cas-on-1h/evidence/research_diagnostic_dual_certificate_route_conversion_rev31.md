# Route-conversion decision

The advisor report is not a verifier-ready proof candidate. It selects the explicit characteristic-two seed as the sole root trunk but proves neither the pending second-stage noncontainment nor the first-stage computational assertions summarized in the seed dossier. Therefore no active sufficient root route or root inference should be created from that report alone.

## Exact compression of the decisive verification obligation

Put F=F_2, R=F[K],

A_K=I(K)I(K')I(K'')I(K''')I(K'''')I(K'''''),
Q_B=I(B)I(B')I(B''),
P_B=I(B)I(B')I(B'')I(B'''),
E_B=RQ_B+RP_BR.

The seed inference needs RA_K not contained in E_B. Because R is a finite-dimensional F-vector space, this is equivalent to the existence of a pair (a,lambda) with

a in RA_K, lambda in Hom_F(R,F), lambda(E_B)=0, and lambda(a)=1.

This dual certificate is exact and avoids publishing complete row-echelon bases. Indeed, RA_K and E_B have the following canonical finite spanning lists:

- RA_K is spanned by g(x_0-1)(x_1-1)(x_2-1)(x_3-1)(x_4-1)(x_5-1), where g is in K and x_i is in K^(i);
- RQ_B is spanned by g(y_0-1)(y_1-1)(y_2-1), where g is in K and y_i is in B^(i);
- RP_BR is spanned by g(y_0-1)(y_1-1)(y_2-1)(y_3-1)h, where g,h are in K and y_i is in B^(i).

Consequently an explicit coefficient expansion of a in the first list, together with the coefficient vector of lambda in the group basis of R, is independently checkable by evaluating lambda on these finite generators. Such a packet proves the reported strict rank inequality without relying on an unrecorded row space or on the rejected surrogate ideal.

## Short root proof spine

1. The integrated terminal-escape criterion converts a certified relation RA_K not contained in RQ_B+RP_BR into the exact terminal-escaping pair H=(R/RP_BR) semidirect K and L=(R/RP_BR) semidirect B.
2. The dual pair (a,lambda), together with reproducible subgroup and derived-series checks, is the smallest exact certificate needed to validate that seed inference.
3. The integrated universal split criterion reduces the root to the genuine second-stage test P_H not contained in F_p[H]P_LF_p[H].
4. Noncontainment in one characteristic supplies the universal quotient module and hence a gap-four maximal pair.

After the seed evidence packet is supplied, the sole remaining theorem-level gap is the genuine second-stage containment test. The present advisor report does not decide it.

## Self-check

The separation equivalence uses only finite-dimensional linear algebra. The displayed generator families span the genuine embedded augmentation products and genuine two-sided ideal, so the certificate cannot silently substitute a one-sided or coset surrogate. No rank value from the existing summary is promoted to a verified fact, and no second-stage conclusion is inferred from terminal escape.
