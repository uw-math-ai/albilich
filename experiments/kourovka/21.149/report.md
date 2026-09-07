# A Dlab order automorphism that is not induced in any Dlab overgroup

## Theorem

There exist a Dlab group \(G\) and an order automorphism \(\alpha\) of \(G\) such that, for every source-defined Dlab group \(A\), every order-preserving embedding \(e:G\hookrightarrow A\), and every \(u\in A\), the identity
\[
e(\alpha(f))=u^{-1}e(f)u
\]
fails for some \(f\in G\). In particular, the answer to Kourovka Notebook Problem 21.149 is affirmative.

## Source results used

We use the following source results with their full interfaces relevant here.

First, Dlab's Theorem 4.1 states that, for every subgroup \(K\leq \mathbb R_{>0}^{\times}\), the compact-support group \(D_K([0,1])\) is linearly orderable and its linear orders are in one-to-one correspondence with the linear orders of \(K\); in the proof, the sign of a nonidentity element is the sign of the first nontrivial gradient in its well-ordered basic characteristic. Dlab's Theorem 4.3 states that \(D_K([0,1])\) is algebraically simple. These are Theorems 4.1 and 4.3 on pp. 602 and 603 of Dlab 1968 (paper_id Dlab1968; theorem_id Theorem 4.1 and Theorem 4.3; arXiv id none). We apply them to \(K=\langle2\rangle\) and to affine copies supported in smaller intervals. Those copies are nonabelian, so simplicity implies perfectness.

Second, Dlab's Lemma 3.6 gives this centralizer interface. If \(a\) is a simple locally right \(K\)-linear element with support interval \((c,d)\) and initial gradient \(s_0\), then, for every \(s\in K\), there is a locally right \(K\)-linear element \(b\), unique even in the full real-slope group, such that \(ab=ba\), the initial gradient of \(b\) is \(s\), and every support component of \(b\) meets \([c,d)\). If \(s=1\), then \(b=1\); otherwise \(b\) is simple with support interval \((c,d)\). This is Lemma 3.6 on p. 599 of Dlab 1968 (paper_id Dlab1968; theorem_id Lemma 3.6; arXiv id none). We use it only after restricting commuting transformations to a support component, where all of its hypotheses hold.

Third, Zenkov and Medvedev define the native interval and extended-real Dlab transformation groups by increasing, locally right \(K\)-linear maps with well-ordered breakpoint data. The complete displayed family of linearly ordered Dlab groups on Russian p. 546, immediately before Theorem 3.2, consists of the four interval models and the two extended-real models
\[
D_K(\mathbf I),\quad D_{K*}(\mathbf I),\quad D_{*K}(\mathbf I),\quad \bar D_K(\mathbf I),\quad D_K,\quad D_{K*}.
\]
This is the all-ordered-family statement in Zenkov--Medvedev 1999 (paper_id ZenkovMedvedev1999; theorem_id the displayed taxonomy immediately before Theorem 3.2; arXiv id none). Medvedev 2001 repeats these six models in the abstract and on Russian p. 135, English p. 75 (paper_id Medvedev2001; theorem_id abstract and first-page family enumeration; arXiv id none). Thus an abstract ambient Dlab group may be transported by its defining order isomorphism to one of these native models.

Finally, Zenkov--Medvedev 1999, Propositions 1.1 and 1.2 on p. 537, identify the endpoint-germ quotients used in the interval orders with subgroups of \(K\times K\), or with one copy of \(K\) in a one-sided case, and hence with abelian groups. Theorem 2.1 on pp. 538--541 states that the one-sided extended-real group \(D_{K*}\) has exactly two linear orders, determined by the first right derivative at the first breakpoint. Proposition 2.2 on pp. 541--543 states that
\[
D_K=D_{K*}\rtimes T_K,\qquad T_K\cong \mathbb R\rtimes K,
\]
and that every linear order on \(D_K\) is a lexicographic extension of an order on \(D_{K*}\) by an order on \(T_K\). The group \(T_K\) is metabelian. These are paper_id ZenkovMedvedev1999, theorem_id Propositions 1.1, 1.2, and 2.2 and Theorem 2.1, arXiv id none. Their hypotheses apply to each of the six native models above.

## Proof

Let \(H=\langle2\rangle\) and let
\[
G=D_H([0,1]).
\]
This is the compact-support Dlab group of increasing locally right \(H\)-linear homeomorphisms of \([0,1]\), equipped with the Dlab order determined by the first nontrivial gradient.

Put \(x_n=2^{-(n+1)}\). Define an increasing homeomorphism \(h\) by taking \(h\) to be the identity on \([1/2,1]\), of slope \(2\) on each interval \([x_{2m+2},x_{2m+1}]\), and of slope \(1/2\) on each interval \([x_{2m+1},x_{2m}]\). On the block \([x_{2m+2},x_{2m}]\), the two image lengths add to
\[
2(x_{2m+1}-x_{2m+2})+\frac12(x_{2m}-x_{2m+1})
=x_{2m}-x_{2m+2}.
\]
Starting with \(h(x_0)=x_0\), induction gives \(h(x_{2m})=x_{2m}\) for every \(m\). Hence the pieces fit together continuously and define the asserted homeomorphism.

Every \(f\in G\) is the identity near both endpoints. Its support therefore meets only a compact subinterval of \((0,1)\), on which \(h\) and \(h^{-1}\) have finitely many affine pieces. It follows that \(h^{-1}fh\) again belongs to \(G\), and the same argument with \(h^{-1}\) proves \(h^{-1}Gh=G\). If \(a\) is the left boundary of a support component of \(f\), \(a'=h^{-1}(a)\), and the local formulas are
\[
f(a+t)=a+kt,\qquad h(a'+t)=a+ct,
\]
then
\[
(h^{-1}fh)(a'+t)=a'+kt
\]
for all sufficiently small positive \(t\). Increasing conjugacy also preserves the left-to-right order of support components. Thus it preserves the first nontrivial gradient and hence the Dlab sign. Consequently
\[
\alpha_h:G\longrightarrow G,\qquad \alpha_h(f)=h^{-1}fh,
\]
is an order automorphism.

We now show that no ambient Dlab element can induce \(\alpha_h\). Suppose, to the contrary, that \(A\) is a Dlab group, \(e:G\hookrightarrow A\) is an order-preserving embedding, and \(u\in A\) satisfies
\[
e(\alpha_h(f))=u^{-1}e(f)u\qquad(f\in G).
\]
By the source taxonomy, an order isomorphism transports \(A\), \(e\), and \(u\) to one of the six native interval or extended-real models without changing injectivity, order preservation, or this equation. We therefore work in the native chain of that model.

The group \(G\) is nonabelian and simple by Dlab's Theorem 4.3, so it is perfect. Every endpoint-germ quotient in the interval models is abelian, and the affine quotient in the full extended-real model is metabelian. Since a homomorphic image of a perfect group is perfect and the only perfect solvable group is trivial, the image \(e(G)\) lies in the relevant first-characteristic kernel. Therefore the inherited order on \(e(G)\) is read from the first nontrivial right gradient on its least nontrivial action component, including for the inverse first-characteristic orders.

Let \(F\) be the common fixed set of \(e(G)\). On every component \(J\) of the complement of \(F\), the kernel of the restriction action is normal in the simple group \(G\); the restriction is nontrivial by the definition of \(F\), and hence it is faithful. Fix \(1\neq b\in G\). Every action component contains a support component of \(e(b)\). Because the support components of every native Dlab element form a well-ordered chain, the action components also form a well-ordered chain. Let \(J_0\) be the least one.

The implementing equation implies \(u^{-1}e(G)u=e(G)\), so \(u(F)=F\). As \(u\) is increasing, it induces an order-preserving permutation of the action components and consequently fixes \(J_0\) setwise. Moreover, the first characteristic of every \(e(f)\), for \(f\neq1\), occurs inside \(J_0\). Thus the restriction action on \(J_0\) detects the Dlab sign and is order preserving.

We next reconstruct this faithful action spatially. For every relatively compact open interval \(L\Subset(0,1)\), set
\[
G(L)=\{g\in G:\operatorname{supp}(g)\Subset L\}
\]
and let
\[
\Sigma(L)=\operatorname{supp}(e(G(L))|_{J_0}).
\]
Each \(G(L)\) is an affine copy of \(G\), and hence is perfect. Two such groups commute when their source intervals are disjoint.

We need one centralizer consequence. If \(a\) is a native Dlab element and \(O\) is one of its support components, every element centralizing \(a\) preserves \(O\): it permutes the well-ordered support components in order, and an order automorphism of a well-ordered set is the identity. Truncate \(a\) and a commuting element to \(O\). Dlab's Lemma 3.6 says that the truncated commuting map is uniquely determined by its initial gradient. Since gradients lie in the abelian group \(K\), any two such restrictions commute. Hence the restriction to \(O\) of the centralizer of \(a\) is abelian. It follows that commuting perfect subgroups have disjoint carriers: if perfect groups \(P\) and \(Q\) commuted and moved a common point, restriction of \(Q\) to a support component of an appropriate element of \(P\) would be both abelian and nontrivial, contradicting perfectness.

Dlab bump fragmentation now gives the carrier identities. If finitely many intervals \(L_i\) cover \(L\), then
\[
G(L)=\langle G(L_1),\ldots,G(L_m)\rangle,
\qquad
\Sigma(L)=\bigcup_i\Sigma(L_i).
\]
Indeed, two-slope bumps give ordered two-point transitivity inside every source interval, and a chain of overlapping \(L_i\) moves a compact interval supporting any prescribed element of \(G(L)\) into one member of the cover. Carrier disjointness for disjoint intervals, followed by fragmentation across two crossing intervals, yields
\[
\Sigma(L\cap M)=\Sigma(L)\cap\Sigma(M).
\]
Conjugation of local groups also gives the covariance identity
\[
e(g)\Sigma(L)=\Sigma(g(L)).
\]

For \(y\in J_0\), repeated fragmentation produces nested intervals \(L_n\) with \(y\in\Sigma(L_n)\), with \(\overline{L_{n+1}}\subset L_n\), and with diameters tending to zero. Define \(\pi(y)\) to be the unique point of \(\bigcap_n\overline{L_n}\). The carrier intersection identity makes this independent of all choices and gives
\[
\pi^{-1}(L)=\Sigma(L)
\]
for every relatively compact interval \(L\). Therefore \(\pi:J_0\to(0,1)\) is continuous, and covariance gives
\[
\pi(e(g)y)=g(\pi(y)).
\]
Its image is nonempty and \(G\)-invariant. The standard Dlab action is transitive on \((0,1)\), by the same two-slope bump construction, so \(\pi\) is surjective.

The carrier identity also forces \(\pi\) to be monotone. If \(\pi\) had a hill, choose a compact component of a superlevel set around a local maximum and a source bump, supported above the boundary level, that moves the maximum upward. Its image under \(e\) fixes the endpoints of that component, while equivariance produces a value larger than the maximum. This is impossible. A bump moving downward gives the analogous contradiction for a valley. Thus \(\pi\) is nondecreasing or nonincreasing. If one fiber were nondegenerate, transitivity would make every fiber nondegenerate, producing uncountably many pairwise disjoint nonempty open intervals in the separable interval \(J_0\). Hence every fiber is a singleton, and \(\pi\) is a monotone homeomorphism.

In fact, \(\pi\) is increasing. If it were decreasing, choose disjoint source intervals \(L<R\), a positive simple bump \(f_L\in G(L)\), and a negative simple bump \(f_R\in G(R)\). The product \(f_Lf_R\) is positive because its leftmost nontrivial component is the component of \(f_L\). Decreasing spatial conjugacy reverses the two target components, so the leftmost component of the restricted image product comes from \(f_R\) and is negative. This contradicts the sign transfer on \(J_0\). We have therefore proved
\[
e(g)|_{J_0}=\pi^{-1}g\pi\qquad(g\in G)
\]
with \(\pi\) increasing.

Set
\[
v=\pi(u|_{J_0})\pi^{-1}.
\]
Restricting the implementation equation to \(J_0\) and transporting it through \(\pi\) gives
\[
v^{-1}fv=h^{-1}fh\qquad(f\in G).
\]
Thus \(vh^{-1}\) centralizes the standard action of \(G\) on \((0,1)\). That centralizer is trivial. Indeed, if a commuting increasing homeomorphism \(c\) moved a point, there would be an interval \(U\) with \(U\cap c(U)=\varnothing\). A nonidentity Dlab bump supported in \(U\) would have support invariant under \(c\), by commutation, while its image under \(c\) would lie in the disjoint interval \(c(U)\), a contradiction. Hence \(v=h\).

Finally, the support components of \(h\) are
\[
C_m=(x_{2m+2},x_{2m})
=(2^{-(2m+3)},2^{-(2m+1)})\qquad(m\geq0).
\]
They satisfy \(C_{m+1}<C_m\), so this nonempty family has no least member. Since \(u\) preserves \(J_0\), the intervals \(\pi^{-1}(C_m)\) are full support components of \(u\), separated by fixed points. Because \(\pi\) is increasing, they too have no least member. This contradicts the defining well ordering of the support components of every element in every native Dlab model.

The contradiction proves the theorem. The result is stronger than the literal overgroup formulation: it excludes implementation after every order-preserving embedding into every source-defined Dlab group, and therefore excludes implementation after any ordered inclusion into a possibly larger Dlab group.

## References

- V. Dlab, "On a Family of Simple Ordered Groups," Journal of the Australian Mathematical Society 8 (1968), 591--608, Lemma 3.6, p. 599; Theorem 4.1, p. 602; Theorem 4.3, p. 603; DOI 10.1017/S1446788700006261; arXiv id none. Supports the Dlab order, simplicity and perfectness, and the component-centralizer argument.
- A. V. Zenkov and N. Ya. Medvedev, "On Dlab Groups," Algebra i Logika 38 (1999), 531--548; English translation, Algebra and Logic 38 (1999), 289--298, Propositions 1.1 and 1.2, p. 537; Theorem 2.1, pp. 538--541; Proposition 2.2, pp. 541--543; complete family display immediately before Theorem 3.2, Russian p. 546; DOI 10.1007/BF02671746; arXiv id none. Supports the native Dlab taxonomy, germ quotients, extended-real orders, and well-ordered support data.
- N. Ya. Medvedev, "Partial Orders on Dlab Groups," Algebra i Logika 40 (2001), 135--157; English translation, Algebra and Logic 40 (2001), 75--86, abstract and first-page enumeration, Russian p. 135 and English p. 75; DOI 10.1023/A:1010256703986; arXiv id none. Supports the exhaustive six-model terminology.
- V. M. Kopytov and N. Ya. Medvedev, Problem 21.149 in The Kourovka Notebook, No. 21, version 45, PDF p. 185, arXiv:1401.0300v45. States the target problem.
- "Strict verification of the endpoint-support lattice route," artifact verification_report_root_rev211_endpoint_support_lattice_route, strict informal verifier. Certifies the assembled proof and its source interfaces.
- "Root integration report for the endpoint-support lattice route," artifact integration_report_root_rev213_endpoint_support_lattice_route, integration verifier. Certifies that the route proves the root claim.
- "Exact Dlab-category and germ-kernel closure," artifact proof_dossier_root_rev207_source_category_and_germ_kernel_closure, researcher. Supplies the native-category reduction and final germ-kernel assembly.
- "Dlab source-family carrier closure," artifact proof_dossier_root_rev195_source_family_carrier_closure, researcher. Supplies the carrier reconstruction and support-component obstruction.
- "Endpoint-singular normalizer route conversion," artifact proof_dossier_root_rev143_endpoint_singularity_route_conversion, researcher. Supplies the explicit alternating-slope normalizer.
