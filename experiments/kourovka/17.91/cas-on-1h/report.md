# Albilich v1 Report: kourovka/problem_17_91_benchmark_cas_1h_20260721

- Outcome: verified_partial
- Public status: certified_partial_progress
- Result kind: partial
- Result classification: partial_progress
- Relation to target: unknown
- Result summary: The root theorem is not solved; verified non-root claims are available as certified partial progress.
- Completion policy: full_proof_first
- Revision: 37
- Claims: 5 total, 3 verified, 3 integrated
- Routes: 4 total, 1 active
- Active debts: 5 total, 5 blocking
- Tokens: 5250897 reported spent, 78676506 remaining, 12000000 reserved
- Run status: completed
- Wall-clock elapsed since run start: 1h 0m 13s
- Active backend compute (child-session wall time): 1h 30m 17s
- Paused time (excluded from active compute): 0s across 0 pause interval(s)
- Peak recorded child memory: 199.1 MB
- Stored memory artifacts: 61.31 KB (62777 bytes)
- Native result directory: 6.28 MB (6582168 bytes)
- Downloaded source directory: 0 bytes

## Root Statement

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

## Benchmark Quantitative Snapshot

| Quantity | Albilich v1 benchmark run |
| --- | ---: |
| Iterations / generator calls | 20 |
| Wall-clock elapsed (seconds) | 3612.686 |
| Active compute wall time (seconds) | 5417.175 |
| Active compute wall time (hours) | 1.50 |
| Paused time (seconds) | 0.000 |
| Reported tokens | 5250897 |
| Search / theorem-retrieval calls | 0 |
| Verifier-call estimate | 8 |
| Advisor / reducer calls | 5 |
| Stored memory artifacts | 62777 bytes |
| Native result directory | 6582168 bytes |
| Downloaded source directory | 0 bytes |

Memory in this table follows the legacy benchmark convention: stored artifact/source directory size, not peak process RSS. Peak RSS is reported separately when the runner can sample it.

Timing convention: wall-clock elapsed runs from problem init to the last recorded activity; active compute is the recorded child-session wall time; paused time covers explicit run-pause intervals and is excluded from active compute.

## Run Control Events

- `2026-07-21T12:28:30.242852+00:00` `running -> completed` [workflow] scheduler stopped: stop_with_partial_results (stop_reason_code=exhausted_budget)

## Certified Partial Results

- `claim_exact_snf_modular_certificate` `informally_verified` `partial`: Let J_Z and P_Z be sublattices of Z^n generated by the columns of B and A, and let U B V=diag(d_1,...,d_a,0,...,0) be a Smith normal form with C=UA. For every prime p, the reduction P_p is contained in J_p if and only if every row of C below a is zero modulo p and every row i≤a for which p divides d_i is zero modulo p. Therefore containment in every characteristic is classified by one integral Smith form and finitely many divisibility checks; noncontainment is equivalently certified by a functional annihilating J_p but not P_p.
- `claim_terminal_escape_criterion_and_split_tower_obstruction` `informally_verified` `partial`: Let B be maximal in a finite soluble group K with d(B)=s≥1 and d(K)=s+2. Over a finite field F put R=F[K], A_K=I(K)I(K')⋯I(K^(s+1)), P_B=I(B)I(B')⋯I(B^(s−1)), Q_B=I(B)I(B')⋯I(B^(s−2)), with Q_B=F·1 for s=1, and J_B=RP_BR. A finite split terminal-escaping exact gap-three lift V⋊B<V⋊K exists if and only if RA_K is not contained in RQ_B+J_B; when it exists V=R/J_B is a witness. Moreover, for K_0=Q_8⋊C_3 with cyclic action and B_0=Z(Q_8)×C_3, every regular first lift K_1=F_p[K_0]⋊K_0, B_1=F_p[K_0]⋊B_0 has derived lengths 4 and 2, but every subsequent split exact gap-three lift H=V⋊K_1, L=V⋊B_1 satisfies H^4≤L' and is terminal-contained.
- `claim_universal_split_criterion` `informally_verified` `partial`: Let H be a finite soluble group, L a maximal subgroup with d(L)=r≥1 and d(H)=r+3, F a finite field, R=F[H], P_H=I(H)I(H')⋯I(H^(r+2)), P_L=I(L)I(L')⋯I(L^(r−1)), and J_L=R P_L R. A finite split gap-four lift V⋊L<V⋊H exists if and only if P_H is not contained in J_L; when it exists, V=R/J_L is a witness. For integral lifts P_Z,J_Z, the exact characteristic-p obstruction is (J_Z+P_Z+pZ[H])/(J_Z+pZ[H]), not in general ((J_Z+P_Z)/J_Z) tensor F_p.

## Remaining Obligations

- blocking: Construct or supply an explicit terminal-escaping exact gap-three maximal pair (H,L), then decide P_H⊆J_L in every characteristic using the exact reduced quotient (J_Z+P_Z+pZ[H])/(J_Z+pZ[H]); Smith invariants of (J_Z+P_Z)/J_Z alone do not certify the modular conclusion.
- blocking: Construct one explicit finite soluble exact gap-two maximal pair (K,B) with d(B)≥2 outside the eliminated common-kernel split-escalation family, and supply genuine integral generator matrices proving RA_K is not contained in RQ_B+RP_BR in some characteristic via the exact Smith-row certificate. Then form the universal terminal-escaping seed and apply the already integrated second-stage split criterion.
- blocking: For the explicit terminal-escaping pair H=(F_2[K]/J_B) semidirect K and L=(F_2[K]/J_B) semidirect B constructed from K=SmallGroup(1296,2891) and B=SmallGroup(144,125), decide the second-stage containment P_H subset J_L in some characteristic using a finite quotient, graded-augmentation, cyclic-module, or exact generator certificate. Noncontainment constructs a gap-four pair by the integrated universal split criterion; all-characteristic containment excludes every split lift of this explicit seed.
- blocking: Provide an independently checkable exact computational certificate: executable GAP code plus complete output, or equivalent exact basis/row-reduction data, for the subgroup identification and maximality, derived-series orders, embedded augmentation products and closures, and the ranks establishing dim(E_B+RA_K)>dim(E_B).
- blocking: Replace the dimension-only seed summary by an independently checkable exact packet: give reproducible GAP code and output identifying B and verifying maximality and both derived-series chains, then give an explicit a in RA_K and lambda in F_2[K]^* such that lambda(a)=1 and lambda annihilates every canonical generator of RQ_B and RP_BR. This dual packet implies RA_K is not contained in RQ_B+RP_BR and therefore validates the selected terminal-escaping seed inference.
- The root theorem still requires an exact, equivalent, or stronger verified route.

## Route Scoreboard

- `route_exact_snf_modular_certificate` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_terminal_escape_criterion_and_split_tower_obstruction` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_universal_split_criterion` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_explicit_terminal_escape_seed_sg1296_2891_b144_125_char2` `promising` score=1.67 root_distance=1 verified=0/1

## Branches

- Parallel branch mode: `multi_branch_research` with up to 3 simultaneous branch workers

```text
Branch: route_exact_snf_modular_certificate
Goal: Let J_Z and P_Z be sublattices of Z^n generated by the columns of B and A, and let U B V=diag(d_1,...,d_a,0,...,0) be a Smith normal form with C=UA. For every prime p, the reduction P_p is contained in J_p if and only if every row of C below a is zero modul...
Status: keep_exploiting
Verified facts: claim_exact_snf_modular_certificate: Let J_Z and P_Z be sublattices of Z^n generated by the columns of B and A, and let U B V=diag(d_1,...,d_a,0,...,0) be a Smith normal form with C=UA. For every prime p, the reduc...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: none recorded
Next recommended lemma: extend the verified chain toward the branch goal: Let J_Z and P_Z be sublattices of Z^n generated by the columns of B and A, and let U B V=diag(d_1,...,d_a,0,...,0) be a Smith normal form with C=UA. For every prime p, the reduction P_p is contained in J_p if and only if every row of C below a is zero modul...
Similar lemmas worth trying: prove a special case of the branch goal first: Let J_Z and P_Z be sublattices of Z^n generated by the columns of B and A, and let U B V=diag(d_1,...,d_a,0,...,0) be a Smith normal form with C=UA. For every prime p, the reduction P_p is contained in J_p if and only if every row of C below a is zero modul...; prove a bridge lemma connecting the verified branch facts to: Let J_Z and P_Z be sublattices of Z^n generated by the columns of B and A, and let U B V=diag(d_1,...,d_a,0,...,0) be a Smith normal form with C=UA. For every prime p, the reduction P_p is contained in J_p if and only if every row of C below a is zero modul...
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim claim_exact_snf_modular_certificate verified (at 2026-07-21T11:48:40.063796+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim claim_exact_snf_modular_certificate verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_terminal_escape_criterion_and_split_tower_obstruction
Goal: Let B be maximal in a finite soluble group K with d(B)=s≥1 and d(K)=s+2. Over a finite field F put R=F[K], A_K=I(K)I(K')⋯I(K^(s+1)), P_B=I(B)I(B')⋯I(B^(s−1)), Q_B=I(B)I(B')⋯I(B^(s−2)), with Q_B=F·1 for s=1, and J_B=RP_BR. A finite split terminal-escaping ex...
Status: keep_exploiting
Verified facts: claim_terminal_escape_criterion_and_split_tower_obstruction: Let B be maximal in a finite soluble group K with d(B)=s≥1 and d(K)=s+2. Over a finite field F put R=F[K], A_K=I(K)I(K')⋯I(K^(s+1)), P_B=I(B)I(B')⋯I(B^(s−1)), Q_B=I(B)I(B')⋯I(B^...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: none recorded
Next recommended lemma: extend the verified chain toward the branch goal: Let B be maximal in a finite soluble group K with d(B)=s≥1 and d(K)=s+2. Over a finite field F put R=F[K], A_K=I(K)I(K')⋯I(K^(s+1)), P_B=I(B)I(B')⋯I(B^(s−1)), Q_B=I(B)I(B')⋯I(B^(s−2)), with Q_B=F·1 for s=1, and J_B=RP_BR. A finite split terminal-escaping ex...
Similar lemmas worth trying: prove a special case of the branch goal first: Let B be maximal in a finite soluble group K with d(B)=s≥1 and d(K)=s+2. Over a finite field F put R=F[K], A_K=I(K)I(K')⋯I(K^(s+1)), P_B=I(B)I(B')⋯I(B^(s−1)), Q_B=I(B)I(B')⋯I(B^(s−2)), with Q_B=F·1 for s=1, and J_B=RP_BR. A finite split terminal-escaping ex...; prove a bridge lemma connecting the verified branch facts to: Let B be maximal in a finite soluble group K with d(B)=s≥1 and d(K)=s+2. Over a finite field F put R=F[K], A_K=I(K)I(K')⋯I(K^(s+1)), P_B=I(B)I(B')⋯I(B^(s−1)), Q_B=I(B)I(B')⋯I(B^(s−2)), with Q_B=F·1 for s=1, and J_B=RP_BR. A finite split terminal-escaping ex...
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim claim_terminal_escape_criterion_and_split_tower_obstruction verified (at 2026-07-21T12:01:30.152750+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim claim_terminal_escape_criterion_and_split_tower_obstruction verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_universal_split_criterion
Goal: Let H be a finite soluble group, L a maximal subgroup with d(L)=r≥1 and d(H)=r+3, F a finite field, R=F[H], P_H=I(H)I(H')⋯I(H^(r+2)), P_L=I(L)I(L')⋯I(L^(r−1)), and J_L=R P_L R. A finite split gap-four lift V⋊L<V⋊H exists if and only if P_H is not contained...
Status: keep_exploiting
Verified facts: claim_universal_split_criterion: Let H be a finite soluble group, L a maximal subgroup with d(L)=r≥1 and d(H)=r+3, F a finite field, R=F[H], P_H=I(H)I(H')⋯I(H^(r+2)), P_L=I(L)I(L')⋯I(L^(r−1)), and J_L=R P_L R....
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: none recorded
Next recommended lemma: extend the verified chain toward the branch goal: Let H be a finite soluble group, L a maximal subgroup with d(L)=r≥1 and d(H)=r+3, F a finite field, R=F[H], P_H=I(H)I(H')⋯I(H^(r+2)), P_L=I(L)I(L')⋯I(L^(r−1)), and J_L=R P_L R. A finite split gap-four lift V⋊L<V⋊H exists if and only if P_H is not contained...
Similar lemmas worth trying: prove a special case of the branch goal first: Let H be a finite soluble group, L a maximal subgroup with d(L)=r≥1 and d(H)=r+3, F a finite field, R=F[H], P_H=I(H)I(H')⋯I(H^(r+2)), P_L=I(L)I(L')⋯I(L^(r−1)), and J_L=R P_L R. A finite split gap-four lift V⋊L<V⋊H exists if and only if P_H is not contained...; prove a bridge lemma connecting the verified branch facts to: Let H be a finite soluble group, L a maximal subgroup with d(L)=r≥1 and d(H)=r+3, F a finite field, R=F[H], P_H=I(H)I(H')⋯I(H^(r+2)), P_L=I(L)I(L')⋯I(L^(r−1)), and J_L=R P_L R. A finite split gap-four lift V⋊L<V⋊H exists if and only if P_H is not contained...
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim claim_universal_split_criterion verified (at 2026-07-21T11:38:44.714968+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim claim_universal_split_criterion verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_explicit_terminal_escape_seed_sg1296_2891_b144_125_char2
Goal: Let K=SmallGroup(1296,2891), let B be a representative of the unique maximal-subgroup conjugacy class isomorphic to SmallGroup(144,125), let R=F_2[K], and for s=4 put A_K=I(K)I(K')I(K'')I(K''')I(K'''')I(K'''''), Q_B=I(B)I(B')I(B''), P_B=I(B)I(B')I(B'')I(B''...
Status: keep_exploiting
Verified facts: claim_terminal_escape_criterion_and_split_tower_obstruction: Let B be maximal in a finite soluble group K with d(B)=s≥1 and d(K)=s+2. Over a finite field F put R=F[K], A_K=I(K)I(K')⋯I(K^(s+1)), P_B=I(B)I(B')⋯I(B^(s−1)), Q_B=I(B)I(B')⋯I(B^...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: none recorded
Next recommended lemma: extend the verified chain toward the branch goal: Let K=SmallGroup(1296,2891), let B be a representative of the unique maximal-subgroup conjugacy class isomorphic to SmallGroup(144,125), let R=F_2[K], and for s=4 put A_K=I(K)I(K')I(K'')I(K''')I(K'''')I(K'''''), Q_B=I(B)I(B')I(B''), P_B=I(B)I(B')I(B'')I(B''...
Similar lemmas worth trying: prove a special case of the branch goal first: Let K=SmallGroup(1296,2891), let B be a representative of the unique maximal-subgroup conjugacy class isomorphic to SmallGroup(144,125), let R=F_2[K], and for s=4 put A_K=I(K)I(K')I(K'')I(K''')I(K'''')I(K'''''), Q_B=I(B)I(B')I(B''), P_B=I(B)I(B')I(B'')I(B''...; prove a bridge lemma connecting the verified branch facts to: Let K=SmallGroup(1296,2891), let B be a representative of the unique maximal-subgroup conjugacy class isomorphic to SmallGroup(144,125), let R=F_2[K], and for s=4 put A_K=I(K)I(K')I(K'')I(K''')I(K'''')I(K'''''), Q_B=I(B)I(B')I(B''), P_B=I(B)I(B')I(B'')I(B''...
Failed methods (do not retry unchanged): none recorded
Last useful delta: architecture_improved: inference inference_explicit_terminal_escape_seed_sg1296_2891_b144_125_char2 added (at 2026-07-21T12:09:13.120125+00:00)
Passes since useful delta: 4
Rotation: rotate (stale) — no useful mathematical delta in the last 3 branch passes
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

## Research Strategy

Strategic artifacts are persisted proof-state context, not verified mathematical evidence.

- Latest global advisor synthesis: `none`
- Latest active proof compression: `none`
- Bridge search: `bridge_search_terminal_escape_seed_rev22`; candidates=1, selected=`bridge_explicit_first_stage_noncontainment_sg1296_2891_b144_125`
- Conjecture portfolio: `none`; candidates=0, selected=`none`
- Active invention authorization: `none`
- Global synthesis due: `False`; reasons=[]
- Graph-derived decisive obligation: `debt_dual_exact_certificate_explicit_terminal_seed_rev31`; selected route=`route_explicit_terminal_escape_seed_sg1296_2891_b144_125_char2`, ready_for_verification=False
- Verifier-filtered outcome learning: family=`research`; local families=0; reference_solution_used=False
- Deep-session ROI: allowed=True; reason=deep-session ROI gate is open
- Information-gain policy: scheduler exposes closing, refuting, root-progress, information, reuse, duplication, token, wall-time, verification-cost, and verifier-filtered outcome components; speculative work never consumes the protected verification reserve.
- Method library policy: 18 developer-curated structural/domain method cards are advisory only and are kept separate from verified facts, external theorem cards, and private speculation.

## Fact Graph

Read-only graph view generated from claims, routes, inferences, debts, and sources.

- Nodes: verified_fact=6, candidate_fact=2, obstruction=6, source_fact=0, branch_cluster=4
- Edges: uses=1, depends_on=1, blocks=3, repairs=0, same_as=0, supersedes=0
- Edge types awaiting a data source (not derived): contradicts, generalizes, specializes
- Branch depth report:
  - `route_universal_split_criterion` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_exact_snf_modular_certificate` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_terminal_escape_criterion_and_split_tower_obstruction` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_explicit_terminal_escape_seed_sg1296_2891_b144_125_char2` converging (depth=0, verified=1, candidate=1, active_obstructions=1, converging)

## Claims

- `claim_exact_snf_modular_certificate` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let J_Z and P_Z be sublattices of Z^n generated by the columns of B and A, and let U B V=diag(d_1,...,d_a,0,...,0) be a Smith normal form with C=UA. For every prime p, the reduction P_p is contained in J_p if and only if every row of C below a is zero modulo p and every row i≤a for which p divides d_i is zero modulo p. Therefore containment in every characteristic is classified by one integral Smith form and finitely many divisibility checks; noncontainment is equivalently certified by a functional annihilating J_p but not P_p.
- `claim_explicit_terminal_escape_seed_sg1296_2891_b144_125_char2` `challenged` `active` `main_trunk` maturity=attempted root_distance=1: Let K=SmallGroup(1296,2891), let B be a representative of the unique maximal-subgroup conjugacy class isomorphic to SmallGroup(144,125), let R=F_2[K], and for s=4 put A_K=I(K)I(K')I(K'')I(K''')I(K'''')I(K'''''), Q_B=I(B)I(B')I(B''), P_B=I(B)I(B')I(B'')I(B'''), and J_B=RP_BR. Then RA_K is not contained in RQ_B+J_B. Consequently, with V=R/J_B, H=V semidirect K and L=V semidirect B form a finite soluble maximal pair satisfying d(H)=7, d(L)=4, and H^6 is not contained in L^3.
- `claim_terminal_escape_criterion_and_split_tower_obstruction` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let B be maximal in a finite soluble group K with d(B)=s≥1 and d(K)=s+2. Over a finite field F put R=F[K], A_K=I(K)I(K')⋯I(K^(s+1)), P_B=I(B)I(B')⋯I(B^(s−1)), Q_B=I(B)I(B')⋯I(B^(s−2)), with Q_B=F·1 for s=1, and J_B=RP_BR. A finite split terminal-escaping exact gap-three lift V⋊B<V⋊K exists if and only if RA_K is not contained in RQ_B+J_B; when it exists V=R/J_B is a witness. Moreover, for K_0=Q_8⋊C_3 with cyclic action and B_0=Z(Q_8)×C_3, every regular first lift K_1=F_p[K_0]⋊K_0, B_1=F_p[K_0]⋊B_0 has derived lengths 4 and 2, but every subsequent split exact gap-three lift H=V⋊K_1, L=V⋊B_1 satisfies H^4≤L' and is terminal-contained.
- `claim_universal_split_criterion` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let H be a finite soluble group, L a maximal subgroup with d(L)=r≥1 and d(H)=r+3, F a finite field, R=F[H], P_H=I(H)I(H')⋯I(H^(r+2)), P_L=I(L)I(L')⋯I(L^(r−1)), and J_L=R P_L R. A finite split gap-four lift V⋊L<V⋊H exists if and only if P_H is not contained in J_L; when it exists, V=R/J_L is a witness. For integral lifts P_Z,J_Z, the exact characteristic-p obstruction is (J_Z+P_Z+pZ[H])/(J_Z+pZ[H]), not in general ((J_Z+P_Z)/J_Z) tensor F_p.
- `root` `untested` `active` `root_theorem` maturity=verifier_gap root_distance=0: You are a computational finite-group theorist working on Kourovka Notebook Problem 17.91.

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

## Active Proof Debts

- `debt_terminal_escaping_seed_and_exact_modular_certificate` `blocking` on `root`: Construct or supply an explicit terminal-escaping exact gap-three maximal pair (H,L), then decide P_H⊆J_L in every characteristic using the exact reduced quotient (J_Z+P_Z+pZ[H])/(J_Z+pZ[H]); Smith invariants of (J_Z+P_Z)/J_Z alone do not certify the modular conclusion.
- `debt_non_full_kernel_exact_gap2_terminal_escape_certificate` `blocking` on `root`: Construct one explicit finite soluble exact gap-two maximal pair (K,B) with d(B)≥2 outside the eliminated common-kernel split-escalation family, and supply genuine integral generator matrices proving RA_K is not contained in RQ_B+RP_BR in some characteristic via the exact Smith-row certificate. Then form the universal terminal-escaping seed and apply the already integrated second-stage split criterion.
- `debt_second_stage_certificate_explicit_seed_sg1296_2891_b144_125` `blocking` on `root`: For the explicit terminal-escaping pair H=(F_2[K]/J_B) semidirect K and L=(F_2[K]/J_B) semidirect B constructed from K=SmallGroup(1296,2891) and B=SmallGroup(144,125), decide the second-stage containment P_H subset J_L in some characteristic using a finite quotient, graded-augmentation, cyclic-module, or exact generator certificate. Noncontainment constructs a gap-four pair by the integrated universal split criterion; all-characteristic containment excludes every split lift of this explicit seed.
- `debt_reproducible_cas_certificate_explicit_terminal_escape_rev29` `blocking` on `inference_explicit_terminal_escape_seed_sg1296_2891_b144_125_char2`: Provide an independently checkable exact computational certificate: executable GAP code plus complete output, or equivalent exact basis/row-reduction data, for the subgroup identification and maximality, derived-series orders, embedded augmentation products and closures, and the ranks establishing dim(E_B+RA_K)>dim(E_B).
- `debt_dual_exact_certificate_explicit_terminal_seed_rev31` `blocking` on `inference_explicit_terminal_escape_seed_sg1296_2891_b144_125_char2`: Replace the dimension-only seed summary by an independently checkable exact packet: give reproducible GAP code and output identifying B and verifying maximality and both derived-series chains, then give an explicit a in RA_K and lambda in F_2[K]^* such that lambda(a)=1 and lambda annihilates every canonical generator of RQ_B and RP_BR. This dual packet implies RA_K is not contained in RQ_B+RP_BR and therefore validates the selected terminal-escaping seed inference.
