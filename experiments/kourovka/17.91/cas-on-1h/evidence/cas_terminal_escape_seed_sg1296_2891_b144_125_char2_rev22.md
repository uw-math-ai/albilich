# Decisive GAP experiment: an explicit terminal-escaping seed

## Decision gate

The competing possibilities were that every available exact gap-two maximal pair remains trapped by the derived-chain/common-kernel obstruction, or that an alternate maximal subgroup of a known high-derived-length group defeats that obstruction and the exact group-algebra criterion.

A structural regression over all 7,012 SmallGroups of orders at most 255 found 135 conjugacy classes of maximal pairs with d(B)>=2 and d(K)=d(B)+2. Every one has d(B)=2 and K'''<=B (hence K'''<=Core_K(B)). Therefore A_K=I(K)I(K')I(K'')I(K''') is contained in R I(B)=R Q_B, so none can satisfy the terminal-escape criterion in any characteristic.

The three known groups SmallGroup(1296,i), i=2889,2890,2891, were then inspected through their maximal-subgroup classes rather than through their known gap-three maximal subgroups. For K=SmallGroup(1296,2891), the unique maximal class isomorphic to SmallGroup(144,125) gives B of index 9 with derived-series orders

K: [1296,648,216,54,27,3,1],
B: [144,72,8,2,1].

Thus d(K)=6=d(B)+2 with s=d(B)=4. The aligned subgroup obstruction fails: K''' is not contained in B, K'''' is not contained in B', and K''''' is not contained in B''.

## Corrected group-algebra calculation

The supplied right-coset initialization was not used for the B-products. The computation began with the actual embedded augmentation space I(B), successively multiplied it on the right by I(B'), I(B''), and I(B'''), closed Q_B=I(B)I(B')I(B'') under left multiplication by generators of K to obtain RQ_B, and closed P_B=I(B)I(B')I(B'')I(B''') under both left and right multiplication to obtain J_B=RP_BR. Closure continued until the exact finite-field row space stabilized.

Over F_2 the exact ranks are:

- successive embedded A_K ranks: [1295,1294,1286,1262,1248,864], with dim(RA_K)=864;
- successive embedded Q_B ranks: [143,142,122], with dim(RQ_B)=1098;
- successive embedded P_B ranks: [143,142,122,50], with dim(J_B)=1154;
- dim(E_B)=dim(RQ_B+J_B)=1250;
- dim(E_B+RA_K)=1286.

Consequently dim((E_B+RA_K)/E_B)=36 and RA_K is not contained in E_B. As a control, the corrected characteristic-three calculation gives dim(E_B)=dim(E_B+RA_K)=1290, so this pair is characteristic-sensitive rather than generically positive.

The decisive GAP calculation used exact BaseMat row reduction over GF(2) and GF(3). Its essential commands were: construct vectors b-1 in the ordered basis AsList(K); apply v -> v(g-1) for generators of each required derived subgroup; close Q_B under left K-translates; close P_B under left and right K-translates; and compare Length(BaseMat(Concatenation(E,A))) with Length(E).

## Conclusion

Let R=F_2[K], J_B=RP_BR, V=R/J_B, H=V semidirect K, and L=V semidirect B. Then dim_F2(V)=1296-1154=142. The already verified terminal-escape criterion gives

d(H)=7, d(L)=4, H^6 not contained in L^3,

and L is maximal in H of index 9. Thus this is an explicit finite soluble terminal-escaping exact gap-three seed. The seed-construction half of the central obstruction is resolved; the next proof move is the second-stage split-ideal test for this specific (H,L), preferably through a quotient or graded-algebra representation rather than the infeasible full regular algebra of H.
