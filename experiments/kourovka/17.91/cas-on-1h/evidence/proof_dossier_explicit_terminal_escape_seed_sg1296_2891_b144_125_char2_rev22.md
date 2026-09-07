# Explicit terminal-escaping exact gap-three seed

Let K=SmallGroup(1296,2891), and let B be a representative of the unique conjugacy class of maximal subgroups of K isomorphic to SmallGroup(144,125). Exact GAP calculations give

|K^(i)|=[1296,648,216,54,27,3,1],
|B^(i)|=[144,72,8,2,1].

Hence B is maximal of index 9, K and B have derived lengths 6 and 4, and (K,B) is an exact gap-two maximal pair with s=4.

Over F=F_2 put R=F[K] and

A_K=I(K)I(K')I(K'')I(K''')I(K'''')I(K'''''),
Q_B=I(B)I(B')I(B''),
P_B=I(B)I(B')I(B'')I(B'''),
J_B=RP_BR,
E_B=RQ_B+J_B.

The computation used the actual embedded augmentation spaces. Each product was obtained by exact multiplication by augmentation generators; RQ_B was left-closed and J_B was closed on both sides under generators of K. Thus the computed spaces are precisely the spaces in the verified terminal-escape theorem, not the previously criticized right-coset surrogate.

Exact row reduction over F_2 gives

dim RA_K=864,
dim RQ_B=1098,
dim J_B=1154,
dim E_B=1250,
dim(E_B+RA_K)=1286.

Therefore RA_K is not contained in E_B. Take the right RK-module V=R/J_B. It has dimension 142. By the verified terminal-escape criterion, for H=V semidirect K and L=V semidirect B one has

d(H)=s+3=7,
d(L)=s=4,
H^(s+2)=H^6 not contained in L^(s-1)=L^3.

Moreover L is the full inverse image of B under H -> K, so L is maximal in H and has index 9. Both groups are finite and soluble, with orders 1296*2^142 and 144*2^142. This proves that (H,L) is an explicit terminal-escaping exact gap-three maximal pair.

Self-check: maximality, solubility, derived lengths, the exact B-derived chain, the correct left/two-sided closures, and both characteristic-two rank sides were checked. No conclusion about the second-stage split criterion is inferred from terminal escape alone. The root now reduces to deciding the verified second-stage containment P_H subset J_L for this explicit pair.
