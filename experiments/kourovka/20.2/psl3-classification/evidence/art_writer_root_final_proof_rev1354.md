# Classification of the totally \(3\)-closed groups \(\operatorname{PSL}_3(q)\)

## Statement

For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), write \(G^{(3)}\) for the largest subgroup of \(\operatorname{Sym}(\Omega)\) having the same orbits as \(G\) on ordered triples in \(\Omega^3\). A finite abstract group is totally \(3\)-closed if every faithful finite permutation representation of it is \(3\)-closed.

Among the nonabelian simple groups
\[
S=\operatorname{PSL}_3(q),
\]
the totally \(3\)-closed groups are exactly those for which \(q\) is prime and either \(q=3\) or \(q\equiv2\pmod 3\). In particular, \(q=2\) is included through the exceptional isomorphism \(\operatorname{PSL}_3(2)\cong\operatorname{PSL}_2(7)\).

## Proof

We use the following certified reductions from the integrated route.

1. For a finite nonabelian simple group \(S\), total \(3\)-closure is equivalent to \(3\)-closedness of every diagonal action on \(S/H\sqcup S/K\) for proper subgroups \(H,K<S\), with repetition allowed.

2. If \(q=r^f\) with \(f>1\), or if \(\gcd(3,q-1)>1\), the natural action of \(\operatorname{PSL}_3(q)\) on projective points has a proper \(3\)-closure containing, respectively, a field or diagonal outer automorphism. Thus \(\operatorname{PSL}_3(q)\) is not totally \(3\)-closed in either case.

3. The finite certificates for the two small survivors prove that \(\operatorname{PSL}_3(2)\cong\operatorname{PSL}_2(7)\) and \(\operatorname{PSL}_3(3)\) are totally \(3\)-closed.

4. A diagonal action on two faithful transitive constituents is \(3\)-closed if both constituents are \(3\)-closed and one has a base of size at most two.

5. If \(p\) is prime and \(\gcd(3,p-1)=1\), every scalar-fiber action of \(\operatorname{PSL}_3(p)\) on
\[
(\mathbb F_p^3\setminus\{0\})/C,\qquad C\leq\mathbb F_p^\times,
\]
is faithful and \(3\)-closed.

We prove the uniform positive result for a prime \(p\geq5\) satisfying \(p\equiv2\pmod3\). In this range the center of \(\operatorname{SL}_3(p)\) is trivial, so throughout we identify
\[
G=\operatorname{SL}_3(p)=\operatorname{PSL}_3(p).
\]

### The Levi split-torus separator

**Lemma 1.** Let \(L=\operatorname{GL}_2(p)\), let \(M\leq L\) not contain \(\operatorname{SL}_2(p)\), and let \(D\) be a split maximal torus of \(L\). Then there is \(g\in L\) such that
\[
D\cap M^g=D\cap\operatorname{core}_L(M).
\]

**Proof.** Let \(Z=Z(L)\), let \(\pi:L\to\operatorname{PGL}_2(p)\), and put \(A=\pi(M)\). The group \(A\) does not contain \(\operatorname{PSL}_2(p)\). Otherwise \(\pi([M,M])\) would contain the perfect group \(\operatorname{PSL}_2(p)\), while \([M,M]\leq M\cap\operatorname{SL}_2(p)\). Hence \(M\cap\operatorname{SL}_2(p)\) would either be all of \(\operatorname{SL}_2(p)\) or an index-two subgroup of it; the latter is impossible because \(\operatorname{SL}_2(p)\) is perfect.

We use Faber's Theorem D. Its complete statement in the notation needed here is as follows. Let \(q=p^r\). Every conjugacy class of nontrivial subgroups of \(\operatorname{PGL}_2(\mathbb F_q)\) occurs in one of ten cases: (1) for \(n\geq2\) with \(q\equiv1\pmod n\), one class of split cyclic groups of order \(n\); (2) for \(n\geq2\) with \(q\equiv-1\pmod n\), one class of nonsplit cyclic groups of order \(n\); (3) for \(n\geq3\) with \(q\equiv1\pmod n\), split dihedral groups of order \(2n\), with two classes when \(q\equiv1\pmod{2n}\) and one otherwise; (4) for \(n\geq3\) with \(q\equiv-1\pmod n\), nonsplit dihedral groups of order \(2n\), with two classes when \(q\equiv-1\pmod{2n}\) and one otherwise; (5) when \(q\) is odd, exactly two classes of Klein four-groups; (6) one class of \(A_4\) when \(p\) is odd, or when \(p=2\) and \(r\) is even; (7) one class of \(S_4\) when \(p\neq2\); (8) one class of \(A_5\) when \(q\equiv0,\pm1\pmod5\); (9) for every \(s\mid r\), one class of each of \(\operatorname{PSL}_2(\mathbb F_{p^s})\) and \(\operatorname{PGL}_2(\mathbb F_{p^s})\); and (10) if \(m,n\) are positive, \(m\leq r\), \(\gcd(n,p)=1\), and \(e=\operatorname{ord}_n(p)\) divides \(\gcd(r,m)\), then \(p\)-semi-elementary groups of order \(p^m n\), whose classes correspond to homothety classes of \(m/e\)-dimensional \(\mathbb F_{p^e}\)-subspaces of \(\mathbb F_q\). Here \(p\)-semi-elementary means that the group has a unique Sylow \(p\)-subgroup of exponent \(p\) and cyclic quotient; in the finite-field case such a group has a unique rational fixed point and is conjugate into an affine Borel. This is Theorem D of Faber, paper_id Faber-PGL2-2023, arXiv:1112.1999v4, pages 3--4, with proof on pages 28--30.

For \(q=p\), the subfield alternatives are only \(\operatorname{PSL}_2(p)\) and \(\operatorname{PGL}_2(p)\), which are excluded here, and every \(p\)-semi-elementary group is affine. We now obtain a two-point base for \(A\) in every remaining case. An affine subgroup, written as \(z\mapsto az+b\), has base \((0,1)\). In a split torus normalizer, written as \(z\mapsto az\) or \(z\mapsto a/z\), the pair \((1,c)\) is a base whenever \(c\neq0,\pm1\). In a nonsplit torus normalizer, a nonidentity torus element fixes no rational point. Only the \(p+1\) elements outside the torus can fix rational points, and each fixes at most two ordered pairs of distinct points. They therefore cover at most \(2(p+1)<p(p+1)\) such pairs, so an uncovered base pair exists. A Klein four-group lies in one of these normalizers, by taking the centralizer of one of its involutions.

For an exceptional subgroup \(E\), a base pair exists whenever
\[
2(|E|-1)<p(p+1).
\]
This treats \(A_4\) for \(p\geq5\), \(S_4\) for \(p\geq7\), and \(A_5\) for \(p\geq11\). Under \(p\equiv2\pmod3\), the only remaining prime is \(p=5\). There \(A_5=\operatorname{PSL}_2(5)\) is excluded. For \(S_4\leq\operatorname{PGL}_2(5)\), take
\[
a(z)=2z,\qquad b(z)=\frac{z+2}{z+3}.
\]
Then \(a^4=b^3=(ab)^2=1\), and the generated group is \(S_4\). It is transitive on \(\mathbb P^1(\mathbb F_5)\); the stabilizer of \(\infty\) is \(\langle a\rangle\), and no nonidentity power of \(a\) fixes \(1\). Hence \((\infty,1)\) is a base. Faber's uniqueness of the \(S_4\)-class transfers this conclusion to every such subgroup. Thus \(A\) always has an ordered pair of distinct projective points with trivial pointwise stabilizer.

The core of \(A\) in \(\operatorname{PGL}_2(p)\) is trivial: its intersection with the simple normal subgroup \(\operatorname{PSL}_2(p)\) is trivial, and it must therefore centralize that subgroup, whose centralizer in \(\operatorname{PGL}_2(p)\) is trivial. Consequently
\[
\operatorname{core}_L(M)=M\cap Z.
\]
A split maximal torus is the full inverse image of the pointwise stabilizer of an ordered pair of distinct projective points. Conjugating the base pair just found to the eigenline pair of \(D\) gives
\[
D\cap M^g=D\cap(M\cap Z)=D\cap\operatorname{core}_L(M),
\]
as required. \(\square\)

### Parabolic descendants

**Lemma 2.** If \(P\) is a point or line parabolic of \(G\) and \(H\leq P\), then the coset action of \(G\) associated with \(H\) is \(3\)-closed.

**Proof.** It is enough to use right cosets and treat a point parabolic; the standard left-coset formulation is permutation-equivalent, and contragredient duality gives the line case. Write
\[
P^0=Q\rtimes\operatorname{SL}_2(p),
\]
where \(Q\cong\mathbb F_p^2\) is the unipotent radical, and put \(J=HP^0\). The \(J\)-block relation on \(H\backslash G\) is a union of \(G\)-orbits on ordered pairs, hence is preserved by the \(3\)-closure \(C\) of the coset action. The induced action on \(J\backslash G\) belongs to the \(3\)-closure of that quotient action. The quotient is one of the certified scalar-fiber actions from reduction 5, so it is \(3\)-closed.

Take \(c\in C\). After multiplying by a suitable element of \(G\), we obtain \(k\in C\) that fixes every \(J\)-block. For each projective point \(x\), let \(X_x\) denote the complete fiber over \(x\), and let \(P_x^0\) be the corresponding conjugate of \(P^0\). Then
\[
\alpha^k\in\alpha^{P_x^0}\qquad(\alpha\in X_x).
\]

Transport \(H\) into \(P_x\), call the resulting subgroup \(H_x\), and let
\[
N_x=\operatorname{core}_{P_x}(H_x),
\]
the kernel of \(P_x\) on \(X_x\). Write \(P_x=Q_x\rtimes L_x\), with \(L_x\cong\operatorname{GL}_2(p)\). On row vectors \(u\in Q_x\), the Levi action is
\[
\rho(A)u=(\det A)^{-1}uA^{-1}.
\]
Since \(N_x\cap Q_x\) is \(L_x\)-invariant, it is either \(1\) or \(Q_x\). If it is \(1\), then \(N_x\) centralizes \(Q_x\). The displayed representation is faithful because a scalar \(cI\) acts trivially only when \(c^3=1\), and \(\gcd(3,p-1)=1\). Hence \(C_{P_x}(Q_x)=Q_x\), so \(N_x=1\).

If \(Q_x\leq N_x\), then \(N_x/Q_x\) is normal in \(\operatorname{GL}_2(p)\). Either it contains \(\operatorname{SL}_2(p)\), in which case \(P_x^0\leq N_x\), or its projective image is trivial, in which case it is scalar. Thus either
\[
P_x^0\leq N_x,
\]
or
\[
N_x=1\quad\text{or}\quad N_x=Q_x\rtimes Z_x
\]
for a scalar subgroup \(Z_x\). In the latter, small-core alternatives,
\[
N_x\cap N_y=1\qquad(x\neq y).
\]
Indeed, after taking \(x=\langle e_1\rangle\) and \(y=\langle e_2\rangle\), an element in the intersection has both matrix forms
\[
\begin{pmatrix}c^{-2}&u&v\\0&c&0\\0&0&c\end{pmatrix},
\qquad
\begin{pmatrix}d&0&0\\u'&d^{-2}&v'\\0&0&d\end{pmatrix}.
\]
Equality kills the off-diagonal entries and gives \(c=d=c^{-2}\), whence \(c^3=1\) and the element is the identity. Since the pairs \((P_x,H_x)\) are \(G\)-conjugate, the large-core or small-core alternative is uniform over all fibers.

Fix an ordered projective basis \(F=(x,y,z)\), and put
\[
D_F=P_x\cap P_y\cap P_z.
\]
For a coordinate \(x\), let \(K_x=D_F\cap N_x\). In the small-core case we claim that \(D_F\) has a point \(\eta_x\in X_x\) whose stabilizer is exactly \(K_x\).

Identify \(P_x=Q\rtimes L\), let \(M\) be the Levi image of \(H_x\), and set \(W=H_x\cap Q\). If \(M\) contains \(\operatorname{SL}_2(p)\), the small-core hypothesis forces \(W=0\). The central element \(-I\) acts as \(-1\) on \(Q\), so the elementary cocycle identity shows that every complement to \(Q\) in \(Q\rtimes\operatorname{SL}_2(p)\) is \(Q\)-conjugate to the standard complement. After conjugacy, \(H_x\leq L\). The two characters of \(D_F\) on \(Q\) have exponent matrix of determinant \(3\); since \(3\) is invertible modulo \(p-1\), the character map is bijective. A vector with both root coordinates nonzero then has trivial \(D_F\)-stabilizer, as required.

Suppose instead that \(M\) does not contain \(\operatorname{SL}_2(p)\). Lemma 1 allows a Levi conjugation for which
\[
D_F\cap M=D_F\cap\operatorname{core}_L(M)=R.
\]
If \(W=Q\), this equality itself gives an anchor with stabilizer \(K_x\). If \(W<Q\), then \(N_x=1\) and \(R\) is scalar. For each \(1\neq d=cI\in R\), the condition that the pure torus lift \(d\) belong to a \(Q\)-conjugate of \(H_x\) excludes at most one affine coset of \(W\), because \(\rho(d)-1=(c^{-3}-1)I\) is invertible. There are at most \(|R|-1\leq p-2\) forbidden cosets, while \(Q/W\) has \(p\) or \(p^2\) elements. A conjugate outside their union supplies the desired anchor. This proves the claim.

We now descend from one frame to all fibers. We use the following stabilizer fact. If \(A,B\leq\operatorname{Sym}(\Lambda)\) have the same orbits on \(\Lambda^m\), where \(m\geq2\), then \(A_\lambda\) and \(B_\lambda\) have the same orbits on \(\Lambda^{m-1}\). This is Theorem 2.3(ii) of O'Brien--Ponomarenko--Vasil'ev--Vdovin, paper_id OBrien-Ponomarenko-Vasilev-Vdovin-JA607, theorem_id Theorem 2.3(ii), arXiv:2012.14166. Its hypotheses match the present situation with \(A=G\), \(B=C\), and \(m=3\). For completeness, if \(b\in B_\lambda\) and \(u\in\Lambda^{m-1}\), then \((\lambda,u)\) and \((\lambda,u^b)\) are in the same \(B\)-orbit and hence in the same \(A\)-orbit; a witness in \(A\) fixes \(\lambda\). Interchanging \(A\) and \(B\) gives equality. Applying the result twice shows that \(G_{\eta,\theta}\) and \(C_{\eta,\theta}\) have the same orbits on \(\Lambda\).

Choose anchors \(\eta_x,\eta_y,\eta_z\) for \(F\). Since \(k\) preserves the orbit of their ordered triple, there is \(t_F\in D_F\) such that
\[
(\eta_x,\eta_y,\eta_z)^k=(\eta_x,\eta_y,\eta_z)^{t_F}.
\]
We use right actions, so the correctly oriented normalized element is
\[
h_F=kt_F^{-1}.
\]
It fixes all three anchors and preserves the three fibers belonging to \(F\). For \(u\in X_x\), stabilizer descent supplies \(a\in G_{\eta_y,\eta_z}\) with \(u^{h_F}=u^a\). Since both points lie in \(X_x\), the element \(a\) fixes \(x\); fixing the two anchors also forces it to fix \(y\) and \(z\). Hence \(a\in D_F\), and
\[
a\in K_y\cap K_z\leq N_y\cap N_z=1.
\]
Thus \(h_F\) fixes \(X_x\) pointwise, and cyclically it fixes \(X_y\) and \(X_z\). Therefore \(k\) and \(t_F\) induce the same permutation on all three frame fibers.

If adjacent frames \(F,F'\) share \(x,y\), the correctly oriented transition \(t_Ft_{F'}^{-1}\) fixes \(X_x\) and \(X_y\) pointwise, so it lies in \(N_x\cap N_y=1\). The graph of ordered projective bases under basis exchange is connected, hence every \(t_F\) equals one element \(t\in G\). Every projective point occurs in a frame, and each \(t_F\) fixes its frame, so \(t\) fixes every projective point. It is scalar and therefore trivial because \(Z(G)=1\). Since the complete fibers cover \(H\backslash G\), we get \(k=1\).

In the large-core case, \(P_x^0\leq N_x\) on every fiber. Then \(\alpha^k\in\alpha^{P_x^0}\) implies \(\alpha^k=\alpha\) directly. Thus \(k=1\) in both cases, and the original \(c\) belongs to \(G\). The coset action is \(3\)-closed. \(\square\)

### Nonparabolic constituents

**Lemma 3.** For every proper subgroup \(H<G\), the action on \(G/H\) is \(3\)-closed. Moreover, if \(H\) has a nonparabolic maximal overgroup, then this action has a base of size at most two.

**Proof.** Choose a maximal overgroup \(M\) of \(H\). If \(M\) is reducible, maximality makes it a point or line parabolic, and Lemma 2 applies.

Suppose \(M\) is nonparabolic. If it is irreducible imprimitive, its three one-dimensional imprimitivity blocks place it in the determinant-one monomial host \(N_2\). If it is primitive and \(F(M)\neq1\), then \(O_p(M)=1\), since a normal \(p\)-subgroup cannot act nontrivially on an irreducible module in characteristic \(p\). A nontrivial characteristic abelian subgroup of \(F(M)\) therefore has order prime to \(p\) and generates a commutative semisimple algebra on \(\mathbb F_p^3\). Primitivity forces that algebra to be the field \(\mathbb F_{p^3}\), so \(M\) lies in the extension-field host
\[
N_3=\Gamma L_1(p^3)\cap G.
\]

It remains that \(M\) is primitive and \(F(M)=1\). A minimal normal subgroup is a direct product \(T_1\times\cdots\times T_k\) of isomorphic nonabelian simple groups. Semisimplicity and primitivity make the natural module homogeneous. Each nontrivial tensor factor has dimension at least two, so \(2^k\leq3\) and \(k=1\). The resulting simple group \(T\) acts absolutely irreducibly, \(C_M(T)=1\), and
\[
T\leq M\leq\operatorname{Aut}(T).
\]
If the module is self-dual, its invariant form is symmetric because \(p\) is odd and the dimension is three. Every \(m\in M\) is then a similitude with multiplier \(\lambda_m\), and taking determinants gives
\[
\lambda_m^3=\det(m)^2=1.
\]
Since \(\gcd(3,p-1)=1\), \(\lambda_m=1\), so \(M\) lies in an orthogonal \(C_8\)-host. If the module is not self-dual, \(M\) lies in an almost-simple \(S\)-host.

The certified uniform host theorems prove that every subgroup of any of \(N_2,N_3,C_8,S\) has base size at most two in its coset action. Thus \(G/H\) has a two-point base whenever \(M\) is nonparabolic. Such an action is \(3\)-closed: after normalizing an element of its \(3\)-closure to fix a base pair \((\alpha,\beta)\), preservation of the orbit of \((\alpha,\beta,\gamma)\) forces every \(\gamma\) to be fixed. Together with Lemma 2, this proves the lemma. \(\square\)

### Synchronization of two parabolic descendants

**Lemma 4.** Let \(H\leq P_X\) and \(K\leq P_Y\), where \(P_X,P_Y\) are point or line parabolics. Then the diagonal action on
\[
A\sqcup B=G/H\sqcup G/K
\]
is \(3\)-closed.

**Proof.** By Lemma 2, both constituent actions are \(3\)-closed. There are surjective \(G\)-equivariant maps
\[
\rho_A:G/H\longrightarrow G/P_X,\qquad
\rho_B:G/K\longrightarrow G/P_Y.
\]
The targets are the projective point or line sets \(X,Y\).

Let \(\pi\) belong to the \(3\)-closure of the diagonal action. The orbits of constant triples show that \(\pi\) preserves the two tagged constituents separately, even for isomorphic or repeated constituents. Internal triples and constituent \(3\)-closedness give \(a,b\in G\) inducing its restrictions. Normalize by \(a^{-1}\); the resulting permutation fixes \(A\) pointwise and acts on \(B\) as \(\delta=a^{-1}b\).

For \(x\in X\) and \(y\in Y\), choose \(\alpha\in\rho_A^{-1}(x)\) and \(\beta\in\rho_B^{-1}(y)\). The mixed triple \((\alpha,\alpha,\beta)\) and its image \((\alpha,\alpha,\delta\beta)\) lie in the same \(G\)-orbit. Hence some \(t\in G\) fixes \(\alpha\) and sends \(\beta\) to \(\delta\beta\), so \(tx=x\) and \(ty=\delta y\).

If \(X,Y\) have the same type, let \(R(x,y)\) mean equality; if they have opposite types, let it mean incidence. The relation is \(G\)-invariant, and therefore
\[
R(x,y)\quad\Longleftrightarrow\quad R(x,\delta y)
\]
for every \(x\). Equality profiles are singletons. Incidence profiles are injective because distinct points are separated by a line through exactly one of them, and distinct lines are separated by a point on exactly one of them. Hence \(\delta y=y\) for every \(y\in Y\).

A linear transformation fixing every projective point is scalar. The same follows from fixing every projective line, by intersecting lines. Thus \(\delta=\lambda I\) with \(\lambda^3=1\), and \(\gcd(3,p-1)=1\) gives \(\delta=1\). Therefore \(\pi\) is induced diagonally by \(a\in G\). \(\square\)

### Completion of the classification

Take arbitrary proper subgroups \(H,K<G\). Choose maximal overgroups of both. Lemma 3 makes each constituent \(3\)-closed. If at least one selected maximal overgroup is nonparabolic, the corresponding constituent has a base of size at most two, so certified base-two synchronization makes the diagonal action on \(G/H\sqcup G/K\) \(3\)-closed. If both selected maximal overgroups are parabolic, Lemma 4 gives the same conclusion. The two cases exhaust all \(H,K\). By the two-orbit reduction, \(G\) is totally \(3\)-closed.

We have therefore proved total \(3\)-closure for every prime \(p\geq5\) with \(p\equiv2\pmod3\). The certified finite results supply \(q=2\) and \(q=3\). Conversely, write an arbitrary prime power as \(q=r^f\). If \(f>1\), the projective outer obstruction excludes it. If \(f=1\) and \(q\equiv1\pmod3\), then \(\gcd(3,q-1)=3\), and the same obstruction excludes it. The remaining prime parameters are exactly \(q=3\) and \(q\equiv2\pmod3\). There are no simplicity exceptions in dimension three. This proves the stated if-and-only-if classification.

The exclusion argument and the proof for all \(p\geq5\) are uniform. Only the two small positive cases \(q=2,3\) use the certified bounded finite analyses. The result is exact, rather than conditional or merely sufficient.

## References

Xander Faber, “Finite \(p\)-Irregular Subgroups of \(\operatorname{PGL}(2,k)\),” *La Matematica* 2 (2023), 479--522, Theorem D, pages 3--4 with proof on pages 28--30, arXiv:1112.1999v4, DOI 10.1007/s44007-023-00051-4. Supports Lemma 1, the exhaustive projective-subgroup list used in the Levi split-torus separator.

E. A. O'Brien, I. Ponomarenko, A. V. Vasil'ev, and E. Vdovin, “The \(3\)-closure of a solvable permutation group is solvable,” *Journal of Algebra* 607 (2022), 618--637, Theorem 2.3(ii), arXiv:2012.14166, DOI 10.1016/j.jalgebra.2021.07.002. Supports the stabilizer-descent step in Lemma 2; the theorem is general and no solvability hypothesis is used in that step.

Internal certified artifacts, listed after the external references:

- “Exact source packet and proof of LTS(p),” art_researcher_root_faber_lts_exact_packet_rev1345, researcher.
- “Oriented right-gauge repair of the DNFK frame descent,” art_researcher_root_oriented_right_gauge_dnfk_repair_rev1341, researcher.
- “Wielandt stabilizer descent and the two-layer frame invariant for DNFK(p),” art_researcher_root_wielandt_frame_descent_dnfk_rev1336, researcher.
- “Replacement section: scalar-quotient reduction and determinant-neutral parabolic rigidity,” art_researcher_root_scalar_quotient_dnfk_closure_rev1313, researcher.
- “Verifier-ready quantified cover and root classification assembly,” art_researcher_root_quantified_cover_route_conversion_rev1298, researcher.
- “Quotient-incidence synchronization and final root assembly,” art_researcher_root_quotient_incidence_synchronization_rev1290, researcher.
- “Two-orbit reduction verification,” art_verification_import_two_orbit_reduction_rev15, verifier.
- “Projective outer-obstruction verification,” art_verification_import_psln_projective_nonclosure_rev44, verifier.
- “\(\operatorname{PSL}_2(7)\) total \(3\)-closure certificate,” art_verification_import_psl27_certificate_rev15, verifier.
- “\(\operatorname{PSL}_3(3)\) total \(3\)-closure verification,” art_strict_verification_claim_root_psl33_totally_3closed_A3_rev59, strict verifier.
- “Base-two constituent synchronization verification,” art_strict_informal_verifier_base2_constituent_synchronization_rev371, strict informal verifier.
- “Uniform \(C_2/C_3\) base-two descendants verification,” art_strict_informal_verifier_root_c2c3_uniform_base2_descendants_rev970, strict informal verifier.
- “Uniform \(C_8/S\) base-two hosts verification,” art_strict_informal_verifier_root_c8_s_base2_hosts_rev1224, strict informal verifier.
- “Root-route verification with no gaps,” art_strict_informal_verifier_root_route_correct_no_gaps_rev1349, strict informal verifier.
