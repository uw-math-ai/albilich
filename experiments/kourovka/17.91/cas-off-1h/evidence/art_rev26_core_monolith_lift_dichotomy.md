# Proof dossier: the core-monolith lemma and the split/Frattini lift dichotomy

## Setting

Assume that (G,M) is a minimal-order counterexample to d(G)-d(M)≤2. Put a=d(G), b=d(M), and K=Core_G(M). By the verified minimal-counterexample theorem,

a=b+3,

and there is a minimal normal elementary abelian subgroup A≤K' such that

A=G^(a-1)=G^(b+2),  d(G/A)=b+2,  d(M/A)=b.

Write |A|=p^n.

## 1. Core-monolith lemma

Lemma 1. Every nontrivial normal subgroup N of G contained in K contains A.

Proof. Suppose N is nontrivial, normal in G, contained in K, and does not contain A. Minimality of A gives A∩N=1. Hence

(G/N)^(a-1)=G^(a-1)N/N=AN/N≠1,

so d(G/N)=a. Since N≤K≤M, the subgroup M/N is maximal in G/N and d(M/N)≤b. Thus (G/N,M/N) is a smaller counterexample with gap at least a-b=3, contrary to the choice of G. Therefore A≤N. ∎

Consequently every nonzero G-invariant subgroup of K, and in particular every nonzero characteristic subgroup of K, contains A. This strengthens the previously known uniqueness of A inside K': A is the unique minimal G-normal subgroup anywhere in the core.

## 2. Exact split/Frattini dichotomy

Either A≤Phi(G), or A has a complement H in G. Indeed, if A is not contained in Phi(G), choose a maximal subgroup H not containing A. Then G=AH. The subgroup A∩H is normalized by H and, because A is abelian, by A; hence it is normal in G. Minimality of A and A not≤H give A∩H=1. Thus G=A⋊H.

Assume the split alternative and put J=H∩M. Since A≤M, unique decomposition in A⋊H gives M=A⋊J. Moreover J is maximal in H: if J<X<H, then M=AJ<AX<G, contradicting maximality of M. The quotient identifications H≅G/A and J≅M/A give

d(H)=b+2,  d(J)=b.

Let C=H∩K. Then C=Core_H(J). The inclusion C≤Core_H(J) is immediate. Conversely, if D=Core_H(J), then AD is normalized by H and A, hence is normal in G; also AD≤AJ=M. Therefore AD≤Core_G(M)=K, and intersection with H gives D≤C. Finally K=A⋊C.

Thus a split minimal counterexample is an irreducible-module inflation of a smaller sharp gap-two maximal pair (H,J), with exactly the same primitive quotient H/C≅G/K and J/C≅M/K.

## 3. Derived-operator filtration

For a semidirect product X=A⋊Y with A abelian, define

U_0(Y)=A,  U_(i+1)(Y)=[U_i(Y),Y^(i)].

Induction gives

X^(i)=U_i(Y)Y^(i).

For Y=H, every U_i(H) is H-invariant. Since A is a minimal normal subgroup of A⋊H, A is an irreducible H-module. The equality d(G)=b+3 while d(H)=b+2 implies U_(b+2)(H)≠1. Hence no earlier U_i(H) is zero, and irreducibility yields

U_i(H)=A and [A,H^(i)]=A for 0≤i≤b+1.                 (1)

For Y=J, write V_i=U_i(J). Since d(M)=d(J)=b, the same formula gives

V_b=1.                                                    (2)

Because A≤K' and K=A⋊C, one has K'=[A,C]C'. If [A,C]=1, then K'≤C, contradicting A≤K' and A∩C=1. Since C is normal in H, [A,C] is H-invariant; irreducibility therefore gives [A,C]=A. As C≤J,

V_1=[A,J]=A.                                             (3)

The filtration cannot drop directly from A to zero. More precisely, suppose V_(t-1)=A and V_t=0 for some 1≤t≤b. Then J^(t-1) centralizes A. Let

N=⟨(J^(t-1))^H⟩.

If N is not contained in J, maximality gives H=JN, and H/N is a quotient of J/J^(t-1), so d(H/N)≤t-1. If N≤J, then J/N is maximal in H/N, d(J/N)≤t-1, and minimality of the original counterexample applies to the smaller pair (H/N,J/N), giving d(H/N)≤t+1. In either case

H^(t+1)≤N.                                                (4)

But C_H(A) is normal in H and contains J^(t-1), so it contains N. Equation (4) says H^(t+1) centralizes A, contradicting (1). Therefore a first drop V_t≠A must satisfy

0<V_t<A.

Together with V_1=A and V_b=0, this proves that every split minimal counterexample has b≥3 and has an index 2≤t≤b-1 for which

V_(t-1)=A and 0<V_t=[A,J^(t-1)]<A.                       (5)

Thus restriction of the irreducible H-module A to J must acquire a proper nonzero derived-operator submodule before eventually being annihilated. In particular, a minimal counterexample with d(M)≤2 must be a Frattini lift A≤Phi(G); the split alternative is impossible in those boundary cases.

## 4. Additional localization when the core is metabelian

Assume d(K)=2 and put B=K'. Then B is an abelian p-group. Indeed, B is nontrivial and contains A. For q≠p, the q-primary component B_q is characteristic in B and hence normal in G. If B_q were nontrivial, Lemma 1 would force A≤B_q, impossible. Thus B has no q-primary component for q≠p. Lemma 1 also says every nonzero G-invariant subgroup of B contains A, so A is the essential minimal G-operator subgroup of B.

Since B is abelian and A≤B, B centralizes A. Hence R=K/C_K(A) is abelian. If R is nontrivial, then [A,K] is a nonzero G-normal subgroup of A and therefore equals A. Furthermore R is a p'-group. To see this, regard R as a normal abelian subgroup of G/C_G(A). A Sylow p-subgroup R_p is characteristic in R and hence normal in G/C_G(A). A p-group acting on the nonzero F_p-space A has nonzero fixed points. The fixed-point space C_A(R_p) is G-invariant, so irreducibility forces it to be A. Faithfulness of R on A then gives R_p=1.

Thus the metabelian-core case has the exhaustive action dichotomy

A≤Z(K),

or

K/C_K(A) is a nontrivial abelian p'-group and [A,K]=A.     (6)

In the split alternative, [A,C]=A already excludes A≤Z(K), so only the coprime-action side of (6) can occur.

## 5. Representation switch and remaining obstruction

The quotient-delay representation records only that quotienting by A lowers d(G) but not d(M); it cannot distinguish different lifts. The chief-factor representation gives the exact dichotomy between a Frattini chief-factor lift and a complemented irreducible-module lift. The operator-filtration representation translates the complemented case into equations (1)–(5), while the core-monolith representation makes B p-local and yields (6) when d(K)=2.

The operator/core representation is selected because it strictly narrows the metabelian bridge. A metabelian minimal counterexample must now realize one of only two packages:

(F) A≤Phi(G), B=K' is an abelian p-group with every nonzero G-invariant subgroup containing A, and the nonsplit Frattini lift raises d(G) but not d(M);

(S) A is complemented, b≥3, the smaller pair (H,J) has gap two, K=A⋊Core_H(J), the core acts nontrivially and coprimely on A, and the J-operator filtration has the proper nonzero drop (5) while every H-derived operator in (1) remains surjective.

This is a genuine reduction, not a proof that either package is impossible.

## 6. Full-root assembly

The verified Q8⋊C3 example gives k≥2. If the upper bound two failed, the verified minimal-counterexample theorem and the present lemmas would produce the monolithic layer A and the exhaustive packages (F) or (S). Excluding both packages for d(K)=2 would close the mandatory metabelian-core case. The same split/Frattini dichotomy and the core-monolith lemma remain valid for d(K)≥3, but the p-local conclusion about all of K' uses metabelianity and does not by itself close those higher-core cases.

## 7. Failed direct attack and self-check

The strongest failed route was the attempt to force L'≤K' from numerical saturation and G=G^(b)M alone. The certified Q8⋊C3 equality example shows why scalar derived-length information cannot forbid a nonabelian lift of an affine terminal layer; the Frattini and operator compatibility must be used.

All quotient pairs used with minimality have a normal subgroup contained in the relevant maximal subgroup. The proof that Core_H(J)=H∩K checks normality after adjoining A. The semidirect derived-series formula uses a recursively defined operator filtration and does not make the unjustified assertion that d(A⋊J)=d(J) forces J^(b-1) to centralize all of A. That false shortcut is replaced by the proved first-drop argument. No claim is made that the root theorem or the full metabelian exclusion is proved.
