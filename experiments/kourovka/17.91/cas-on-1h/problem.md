You are a computational finite-group theorist working on Kourovka Notebook Problem 17.91.

The target is to determine whether there exists a finite soluble group $G$ with a maximal subgroup $M<G$ such that

$$
d(G)-d(M)=4.
$$

A successful run must either:

1. construct and independently verify an explicit gap-four pair;
2. prove that a substantial infinite construction family cannot contain a gap-four pair;
3. isolate a precise finite list of nonsplit extension problems whose resolution would decide the next search frontier.

Do not repeat the previous low-order and small-module searches. The expected candidate may have extremely large order. Search through presentations, modules, extensions, and group-algebra certificates rather than enumerating groups by order.

# 1. Read the previous 17.91 corpus first

Before writing code, locate and read all available files concerning Problem 17.91, especially files with names resembling:

* `problem_17_91_all_results.md`;
* `problem_17_91_selected_verified_results_with_proofs.md`;
* `problem_17_91_publishable_results_and_paper_plan.md`;
* `Albilich_17_91_Absolute_Bound_Audit*.tex`;
* `Albilich_17_91_Absolute_Bound_Audit*.pdf`;
* `albilich_kourovka_17_91_strong_math_paper.tex`;
* previous GAP scripts and computational reports.

Write a short machine-readable summary of all previously tested families before beginning a new computation.

# 2. Treat these negative results as constraints

The following searches have already been performed and must not simply be repeated.

## 2.1 Low-order enumeration

Previous exhaustive searches found:

* no gap-three pair among soluble groups of order at most $255$;
* maximum gap $2$ in that range;
* exactly three gap-three maximal-subgroup pairs at order $1296$;
* no gap-four pair at order $1296$.

Do not rerun these enumerations except as a ten-second regression test of new code.

## 2.2 Known order-$1296$ gap-three pairs

The known benchmark has

$$
G_0=E\rtimes\operatorname{GL}_2(3),\qquad
M_0=E\rtimes B,
$$

where $E$ is extraspecial of order $27$ and exponent $3$, and $B$ is upper triangular.

It satisfies

$$
d(G_0)=6,\qquad d(M_0)=3,
$$

with derived-series orders

$$
G_0:\ 1296,648,216,54,27,3,1,
$$

$$
M_0:\ 324,81,9,1.
$$

All three order-$1296$ gap-three pairs satisfy

$$
G_0^{(5)}\leq M_0^{(2)}.
$$

Therefore they satisfy the terminal-containment condition that obstructs the simplest further exceptional lift.

## 2.3 Previously tested split lifts

For the known gap-three seed, previous computations tested many permutation modules and the regular module in characteristics

$$
2,3,5,7.
$$

They found that every tested module that produced an additional ambient derived layer also produced an additional maximal-subgroup layer.

A characteristic-two six-dimensional extension of a smaller Heisenberg-$Q_8$ seed was also negative: the ambient derived length increased, but the maximal preimage increased as well.

Do not repeat finite lists of irreducible or permutation modules over these characteristics. Replace them with the universal group-algebra test below.

## 2.4 Logical obstructions already known

Do not use any of the following false or insufficient principles:

* every exact gap-three pair automatically satisfies terminal containment;
* every elementary abelian extension of a gap-three pair is split;
* checking irreducible modules is enough to rule out all split modules;
* failure for characteristics $2,3,5,7$ implies failure in every characteristic;
* exact derived-length equalities and maximality alone imply
  $H^{(r+2)}\leq L^{(r-1)}$;
* a local class-two commutator pairing alone excludes the remaining lift.

# 3. The necessary structure of a least gap-four pair

Use the following reduction as the central guide.

Assume that $(G,M)$ is a least-order gap-four pair and put

$$
r=d(M).
$$

Then there is an elementary abelian minimal normal subgroup

$$
A\leq\operatorname{core}_G(M)
$$

such that, with

$$
H=G/A,\qquad L=M/A,
$$

one has

$$
d(G)=r+4,\qquad d(M)=r,
$$

$$
d(H)=r+3,\qquad d(L)=r,
$$

and

$$
A=G^{(r+3)}.
$$

Thus $(H,L)$ is an exact gap-three maximal pair.

Put

$$
T=H^{(r+2)}.
$$

The existing terminal obstruction proves that a gap-four lift is impossible when

$$
T\leq L^{(r-1)}.
$$

Therefore a least gap-four pair requires an exact gap-three seed satisfying

$$
\boxed{H^{(r+2)}\nleq L^{(r-1)}.}
$$

Call such a pair a terminal-escaping gap-three seed.

The search has two stages:

1. find or construct a terminal-escaping exact gap-three seed $(H,L)$;
2. lift it through an elementary abelian kernel without increasing $d(L)$.

Do not spend most resources lifting terminal-contained seeds.

# 4. Universal split-lift criterion

This is the principal improvement over the previous searches.

Let $(H,L)$ be an exact gap-three pair with

$$
d(L)=r,\qquad d(H)=r+3.
$$

Let $F$ be a field and put

$$
R=F[H].
$$

For a subgroup $X\leq H$, write $I(X)$ for its augmentation ideal in $R$.

Define the ambient terminal product

$$
P_H=
I(H)I(H')\cdots I(H^{(r+2)}).
$$

Define the maximal-subgroup product

$$
P_L=
I(L)I(L')\cdots I(L^{(r-1)}).
$$

Let

$$
J_L=R,P_L,R
$$

be the two-sided ideal generated by $P_L$.

For a right $FH$-module $V$, the split extensions

$$
X=V\rtimes H,\qquad Y=V\rtimes L
$$

satisfy

$$
d(X)=r+4,\qquad d(Y)=r
$$

whenever

$$
VP_H\neq0,\qquad VP_L=0.
$$

Prove and implement the following exact criterion:

$$
\boxed{
\text{A split gap-four lift over }F
\text{ exists if and only if }
P_H\nsubseteq J_L.
}
$$

When the containment fails, the universal witness module is

$$
V=R/J_L.
$$

Indeed,

$$
VP_L=0,
$$

while

$$
VP_H\neq0.
$$

Since $H$ and $L$ are quotients of the two semidirect products,

$$
d(V\rtimes H)=r+4,\qquad
d(V\rtimes L)=r.
$$

The full inverse image $V\rtimes L$ is maximal in $V\rtimes H$ because $L$ is maximal in $H$.

This criterion tests every split module at once. Do not enumerate only irreducible modules.

# 5. All-characteristic integral certificate

Do not test only a short list of primes.

Work first in the integral group ring

$$
R_{\mathbb Z}=\mathbb Z[H].
$$

Construct the integral lattices corresponding to $P_H$ and $J_L$. Let

$$
Q=\frac{J_L+P_H}{J_L}
$$

as a finitely generated abelian group.

Compute a Smith normal form for $Q$.

For a prime $p$, a split gap-four lift over $\mathbf F_p$ exists precisely when

$$
Q\otimes_{\mathbb Z}\mathbf F_p\neq0.
$$

Thus:

* if $Q$ has positive free rank, split gap-four lifts exist in every characteristic except possibly primes requiring a separate reduction check;
* if $Q$ is finite, only primes dividing its invariant factors can produce split gap-four lifts;
* if $Q=0$, no split elementary abelian lift exists in any characteristic.

Verify the integral-to-modular implication carefully. Do not rely on floating-point rank computations.

For each seed, output an exact certificate consisting of:

* bases for $P_H$ and $J_L$;
* their ranks over $\mathbb Q$;
* Smith invariant factors of $Q$;
* the complete set of candidate characteristics;
* direct modular verification in every candidate characteristic.

This replaces the previous tests over $p=2,3,5,7$ with an all-characteristic result.

# 6. Minimize the universal witness module

The module

$$
V=F[H]/J_L
$$

may be very large. That is acceptable for proving existence, but attempt to produce a smaller explicit witness.

Inside $F[H]/J_L$:

1. compute the submodule generated by a surviving element of $P_H$;
2. compute the radical and socle filtrations;
3. search submodules and quotients on which $P_H$ remains nonzero;
4. use the MeatAxe or equivalent algorithms to find a smallest indecomposable quotient with
   $$
   VP_H\neq0;
   $$
5. do not insist that $V$ be irreducible.

Record:

* the dimension of the regular quotient;
* the dimension of the smallest witness found;
* matrices for generators of $H$ on the witness;
* dimensions of the derived module filtration;
* the resulting group order
  $$
  |G|=|H|p^{\dim V}.
  $$

The expected group order may be enormous. Do not reject a mathematically valid candidate because it is outside the SmallGroups library.

# 7. Recursive search from gap two to gap three to gap four

Do not rely only on the three known order-$1296$ gap-three seeds.

Construct new exact gap-three seeds recursively.

## 7.1 Start from exact gap-two pairs

Find manageable exact gap-two pairs

$$
(K,B),\qquad d(K)=d(B)+2.
$$

Use SmallGroups only for the seed database. Good initial seeds include the known $\operatorname{SL}_2(3)$ and Heisenberg-$Q_8$ examples, but search for structurally different pairs as well.

## 7.2 Apply the universal module criterion

For an exact gap-two seed, form the analogous augmentation products. Search for a module $V$ satisfying

$$
d(V\rtimes K)=d(K)+1,
$$

$$
d(V\rtimes B)=d(B).
$$

This produces an exact gap-three pair

$$
(H,L)=(V\rtimes K,V\rtimes B).
$$

Immediately test whether this newly constructed pair is terminal-escaping:

$$
H^{(d(L)+2)}\nleq L^{(d(L)-1)}.
$$

If it is terminal-escaping, give it highest priority for a second universal lift.

This recursive construction is preferable to enumerating all groups of a large order.

# 8. Search for terminal-escaping exact gap-three seeds

Run several theory-guided seed generators in parallel.

## 8.1 Split exceptional lifts of gap-two seeds

Use the universal ideal criterion, not finite irreducible-module lists.

## 8.2 Nonsplit lifts of gap-two seeds

For promising $FK$-modules $V$, compute

$$
H^2(K,V).
$$

Construct extension classes for which the ambient derived length rises while the full inverse image of $B$ keeps the same derived length.

Prioritize classes in the kernel of the restriction map

$$
H^2(K,V)\longrightarrow H^2(B,V),
$$

since these are invisible or simpler over the maximal subgroup.

## 8.3 Extraspecial and class-two kernels

Construct

$$
H=E\rtimes K,\qquad L=E\rtimes B,
$$

where:

* $E$ is extraspecial or class two;
* $B$ is maximal in the soluble group $K$;
* $K$ acts irreducibly on $E/Z(E)$;
* the action preserves or scales the alternating commutator pairing
  $$
  \bigwedge^2(E/Z(E))\to Z(E).
  $$

Search primes $3,5,7,11$ and higher extraspecial ranks. Use pc presentations and matrix actions rather than permutation representations.

## 8.4 Core-top constructions

For a minimal gap-four pair with $d(M)=3$, the core estimate forces

$$
d(\operatorname{core}_G(M))=3,
$$

and

$$
d(M/\operatorname{core}_G(M))=3.
$$

Construct candidate maximal pairs of the form

$$
H=C\rtimes K,\qquad L=C\rtimes B,
$$

where $B$ is maximal in $K$, with

$$
d(C)=3,\qquad d(B)=3,
$$

but the action compresses

$$
d(C\rtimes B)=3
$$

while allowing

$$
d(C\rtimes K)=6.
$$

Then attempt one further exceptional lift.

## 8.5 Wreath, crown, and subdirect constructions

Test:

* regular and imprimitive wreath products;
* crown-based powers;
* diagonal maximal subgroups;
* fiber products;
* subdirect products;
* extraspecial towers.

Prove maximality explicitly. Do not assume that the obvious subgroup in a wreath product is maximal.

Reject constructions that merely increase $d(H)$ and $d(L)$ by the same amount unless they change terminal containment.

# 9. Nonsplit gap-four lifts

If the universal split criterion gives

$$
P_H\subseteq J_L
$$

in every characteristic, the seed has no split gap-four lift. Then test nonsplit extensions.

For an elementary abelian $FH$-module $A$, compute

$$
H^2(H,A)
$$

and the restriction map

$$
\operatorname{res}:H^2(H,A)\to H^2(L,A).
$$

Prioritize:

1. classes in $\ker(\operatorname{res})$;
2. classes whose restriction does not create a new derived layer in the preimage of $L$;
3. modules on which
   $$
   T=H^{(r+2)}
   $$
   acts nontrivially;
4. classes whose commutator cocycle generates $A$ from the preimage of $T$.

For each extension class construct

$$
1\to A\to G\to H\to1
$$

and let $M$ be the full inverse image of $L$.

Verify directly:

$$
d(G)=r+4,
$$

$$
d(M)=r,
$$

$$
M\text{ maximal in }G.
$$

Do not infer the nonsplit result from the split ideal calculation.

When complete extension enumeration is infeasible, classify the untested orbits under

$$
\operatorname{Aut}_H(A)
$$

and state exactly what remains.

# 10. Large-order computation policy

Assume the smallest gap-four group may have order in the millions, billions, or much larger.

Therefore:

* do not enumerate groups by order;
* do not require `IdGroup`;
* use pc groups, matrix groups, modules, and finite presentations;
* use sparse linear algebra for group-algebra ideals;
* avoid regular permutation representations unless needed for verification;
* checkpoint by seed, characteristic, and construction family;
* save intermediate lattices and Smith forms;
* make every search restartable;
* estimate memory before constructing a regular group algebra;
* use quotient and induced-module methods when $|H|$ is too large;
* allow witness modules of dimension much greater than $12$;
* report a mathematically explicit group even when its order is too large for element enumeration.

A finite presentation, module matrices, semidirect-product description, and derived-filtration certificate are sufficient for an explicit candidate.

# 11. Verification of a candidate

A purported gap-four pair must have two independent verification paths.

## 11.1 Structural verification

Verify:

* $G$ is finite;
* $G$ is soluble;
* $M<G$;
* $M$ is maximal;
* $d(G)=d(M)+4$;
* the core and quotient structure;
* all derived module layers;
* failure of terminal containment in the gap-three quotient;
* the extension kernel is elementary abelian;
* the kernel is the final nonzero derived subgroup when expected.

## 11.2 Computational verification

Construct the group in a second form when feasible:

* pc group and matrix semidirect product;
* pc group and permutation representation;
* two independently generated module bases.

Compute the derived series in both forms.

For groups too large to enumerate, verify the derived length using exact module filtrations and quotient derived series, and state why these imply the claimed group derived series.

# 12. Required implementation

Create a new directory

`experiments/problem_17_91_gap4/`

containing the following.

## `README.md`

State:

* the target;
* all previous negative results;
* the new universal ideal criterion;
* the search architecture;
* exact commands to reproduce each stage.

## `gap4_universal_split.g`

Implement:

* derived subgroup and derived-length utilities;
* augmentation ideals;
* products $P_H$ and $P_L$;
* the two-sided ideal $J_L$;
* containment tests;
* universal witness construction;
* module-filtration verification;
* sparse finite-field calculations.

## `gap4_integral_certificate.sage`

Use SageMath, GAP, or another exact integer-linear-algebra system to compute:

* integral group-ring lattices;
* Smith normal forms;
* all-characteristic candidate primes;
* certificate files.

## `gap4_seed_search.g`

Implement:

* exact gap-two seed extraction;
* recursive split lifts to gap three;
* terminal-containment classification;
* construction-family hooks;
* checkpointing.

## `gap4_cohomology.g`

Implement:

* $H^2$ calculations where supported;
* restriction maps;
* extension representatives;
* derived-length verification of nonsplit lifts.

## `gap3_seeds.csv`

Include:

* construction;
* order;
* $d(H)$;
* $d(L)$;
* core data;
* terminal subgroup;
* terminal-containment status;
* split-lift certificate status;
* candidate characteristics;
* cohomology status.

## `gap4_candidates.csv`

Include:

* construction;
* parent seed;
* characteristic;
* module dimension;
* split or nonsplit;
* group order;
* $d(G)$;
* $d(M)$;
* maximality certificate;
* independent verification status.

## `gap4_report.md`

Write a mathematical report, not a raw log.

The report must contain:

1. previous negative results used as pruning rules;
2. exact statement and proof of the universal split-lift criterion;
3. all-characteristic Smith-form results;
4. every terminal-escaping gap-three seed found;
5. every split and nonsplit gap-four candidate;
6. families completely eliminated;
7. families only partially tested;
8. the smallest explicit candidate;
9. the precise remaining obstruction if no candidate is found.

# 13. Search order

Run in this order.

1. Regression-test the known order-$1296$ example.
2. Apply the integral all-characteristic split-lift test to the known seed.
3. Determine whether the previous $p=2,3,5,7$ negative result extends to every characteristic.
4. Generate new gap-three seeds recursively from exact gap-two pairs.
5. Retain only terminal-escaping or structurally unusual gap-three seeds for expensive lifting.
6. Apply the all-characteristic split criterion to every retained seed.
7. Construct a universal witness whenever containment fails.
8. Minimize the witness module and verify the resulting gap-four pair.
9. Only after split lifts are exhausted, compute nonsplit extension classes.
10. Search extraspecial, core-top, crown, wreath, and tower families.
11. Stop broad low-order enumeration once it repeats the known negative frontier.

# 14. Success and failure criteria

## Full success

Produce an explicit finite soluble maximal pair satisfying

$$
d(G)-d(M)=4.
$$

The preferred profile is

$$
d(G)=7,\qquad d(M)=3.
$$

## Strong partial success

Prove, by exact group-algebra and Smith-form certificates, that an infinite family of exact gap-three seeds has no split gap-four lift in any characteristic.

## Useful partial success

Find a terminal-escaping exact gap-three seed

$$
H^{(d(L)+2)}\nleq L^{(d(L)-1)}.
$$

Even without a completed lift, this directly attacks the missing theoretical step.

## Unacceptable outcome

Do not finish with only:

* another SmallGroups sweep;
* another list of small irreducible modules;
* another negative test in characteristics $2,3,5,7$;
* an unverified semidirect product;
* a report that says merely “no candidate found.”

Every negative conclusion must be attached to a complete, mathematically specified family and a reproducible certificate.
