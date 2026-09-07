# Albilich v1 Report: kourovka/problem_20_2_totally_3_closed_lie_type

- Outcome: solved_final
- Public status: solved
- Result kind: stronger
- Result classification: full_theorem_solved
- Relation to target: stronger
- Result summary: Solved by a verified stronger theorem whose implication to the target was checked.
- Completion policy: full_proof_first
- Revision: 44
- Claims: 5 total, 4 verified, 4 integrated
- Routes: 4 total, 0 active
- Active debts (ledger only): 1 total, 1 blocking
- Tokens: 6714757 reported spent, 78590522 remaining, 12000000 reserved
- Run status: completed
- Wall-clock elapsed since run start: 1h 16m 6s
- Active backend compute (child-session wall time): 1h 39m 43s
- Paused time (excluded from active compute): 0s across 0 pause interval(s)
- Peak recorded child memory: 381.2 MB
- Stored memory artifacts: 306.75 KB (314116 bytes)
- Native result directory: 5.27 MB (5523129 bytes)
- Downloaded source directory: 0 bytes

## Root Statement

# Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type

## Problem

Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set
\(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is
the largest subgroup of \(\operatorname{Sym}(\Omega)\) whose orbits on the set
\(\Omega^{k}\) of ordered \(k\)-tuples coincide with the orbits of \(G\) on
\(\Omega^{k}\) (Wielandt). The group \(G\) is **\(k\)-closed** on \(\Omega\) if
\(G^{(k)} = G\).

An abstract group \(G\) is **totally \(k\)-closed** if for every faithful
permutation representation of \(G\) on a finite set \(\Omega\), the image of
\(G\) in \(\operatorname{Sym}(\Omega)\) is \(k\)-closed.

**Question (Problem 20.2).** Are there any nonabelian simple groups of Lie type
which are totally 3-closed?

Known context: the finite nonabelian simple totally 2-closed groups are
completely classified — there are exactly six, all sporadic groups
(\(\mathrm{J}_1\), \(\mathrm{J}_3\), \(\mathrm{J}_4\), \(\mathrm{Ly}\),
\(\mathrm{Th}\), and the Monster \(\mathrm{M}\)), the largest being the Monster.
Since a totally 2-closed group is totally 3-closed, the real content of the
question is whether total 3-closure can occur for simple groups of Lie type,
where total 2-closure provably cannot.

## Instructions

Treat this as a serious research problem, not only as a benchmark. The target is
to either exhibit a nonabelian simple group of Lie type that is totally
3-closed (with proof), or prove that no nonabelian simple group of Lie type is
totally 3-closed, or establish an honest, precisely stated partial result.

Use direct proof attempts before reducing unless a reduction is mathematically
motivated. Literature search and citations are allowed, and cited theorems may
be used to close a case when the statement is properly identified and logically
applied. The classification of totally 2-closed simple groups and the toolkit
around \(k\)-closures of permutation groups (Wielandt's theory, Praeger–Saxl,
recent work of Abdollahi, Arezoomand, Tracey and coauthors on total
\(k\)-closure) are natural starting points. If an exact published result
answers the question, integrate it responsibly instead of reproving it.

Group-theoretic computation (e.g. GAP) may be used for examples, sanity checks,
and small Lie-type groups: computing \(3\)-closures of specific faithful
permutation representations of small groups such as \(\mathrm{PSL}(2,q)\) for
small \(q\) is encouraged as evidence, and a single faithful representation
that fails to be 3-closed rules that group out. The final argument must be a
mathematical proof or a mathematically rigorous obstruction; finite
computations alone settle individual groups, not the general question, unless
combined with a reduction theorem.

## Benchmark Quantitative Snapshot

| Quantity | Albilich v1 benchmark run |
| --- | ---: |
| Iterations / generator calls | 23 |
| Wall-clock elapsed (seconds) | 4566.488 |
| Active compute wall time (seconds) | 5983.210 |
| Active compute wall time (hours) | 1.66 |
| Paused time (seconds) | 0.000 |
| Reported tokens | 6714757 |
| Search / theorem-retrieval calls | 1 |
| Verifier-call estimate | 10 |
| Advisor / reducer calls | 5 |
| Stored memory artifacts | 314116 bytes |
| Native result directory | 5523129 bytes |
| Downloaded source directory | 0 bytes |

Memory in this table follows the legacy benchmark convention: stored artifact/source directory size, not peak process RSS. Peak RSS is reported separately when the runner can sample it.

Timing convention: wall-clock elapsed runs from problem init to the last recorded activity; active compute is the recorded child-session wall time; paused time covers explicit run-pause intervals and is excluded from active compute.

## Run Control Events

- `2026-07-15T01:51:27.098098+00:00` `running -> completed` [workflow] scheduler stopped: stop_solved

## Final Proof

# A totally 3-closed nonabelian simple group of Lie type

## Theorem

The group $G=\operatorname{PSL}(2,7)$ is totally $3$-closed. In particular, there exists a nonabelian simple group of Lie type which is totally $3$-closed, so Problem 20.2 has an affirmative answer.

## Proof

For a finite $G$-set $X$, write $G_X^{(3)}$ for the largest subgroup of $\operatorname{Sym}(X)$ having the same orbits as $G$ on $X^3$. Thus a permutation $\sigma$ belongs to $G_X^{(3)}$ precisely when, for every ordered triple $(x_1,x_2,x_3)$, there is an element $g\in G$, depending on the triple, such that

$$
(\sigma x_1,\sigma x_2,\sigma x_3)=(g x_1,g x_2,g x_3).
$$

We use the standard identification

$$
G\cong \operatorname{GL}(3,2)\cong \operatorname{PSL}(3,2).
$$

This is a nonabelian simple group of Lie type of order $168$. Let $V=\mathbb F_2^3$. Denote by $\mathcal P$ the seven one-dimensional subspaces of $V$, by $\mathcal P^*$ the seven two-dimensional subspaces, and by $\mathcal Q=\mathbb P^1(\mathbb F_7)$ the eight points of the natural projective-line action of $\operatorname{PSL}(2,7)$.

### The two-orbit criterion

We first record a reduction from arbitrary faithful actions to pairs of transitive actions.

**Lemma 1.** Let $S$ be a finite nonabelian simple group. Then $S$ is totally $3$-closed if and only if the diagonal action on

$$
S/H\sqcup S/K
$$

is $3$-closed for every pair of proper subgroups $H,K<S$, with repeated pairs allowed.

**Proof.** Necessity follows because every nontrivial coset action of a simple group is faithful.

Conversely, let $X$ be an arbitrary faithful finite $S$-set and let $\sigma\in S_X^{(3)}$. Applying the closure condition to $(x,x,x)$ shows that $\sigma$ preserves each $S$-orbit on points. Its restriction to any union of point-orbits belongs to the $3$-closure of the restricted action. Every non-singleton orbit is faithful: its kernel is a proper normal subgroup of $S$ and hence is trivial. Singleton orbits are fixed pointwise by both $S$ and $\sigma$.

Write the non-singleton orbits as $X_1,\ldots,X_r$. If $r=1$, let $\tau=\sigma|_{X_1}$. Acting as $\tau$ on each of two tagged copies of $X_1$ gives an element of the $3$-closure on $X_1\sqcup X_1$: for every tagged triple, the element of $S$ supplied for its underlying triple also preserves all copy tags. The repeated-pair hypothesis therefore implies that $\tau$ is induced by an element of $S$.

If $r\geq 2$, then for every $j>1$ the restriction of $\sigma$ to $X_1\sqcup X_j$ is induced by some $s_j\in S$. All the elements $s_j$ induce the same permutation on the faithful orbit $X_1$, so they are equal. Their common value induces $\sigma$ on every non-singleton orbit and, together with $\sigma$, fixes every singleton orbit. Hence $\sigma\in S$. This proves the lemma. $\square$

### Two-point bases

A tuple $(u,v)$ is a base for a faithful $G$-set if its pointwise stabilizer is trivial; repetition is allowed when a one-point base exists.

**Lemma 2.** A faithful $G$-set with a base of size at most two is $3$-closed.

**Proof.** Let $(u,v)$ be such a base and let $\sigma$ lie in the $3$-closure. Choose $g\in G$ carrying $(u,v,u)$ to its $\sigma$-image. For arbitrary $x$, choose $g_x\in G$ carrying $(u,v,x)$ to its $\sigma$-image. The elements $g$ and $g_x$ agree on the base, so $g=g_x$. Thus $\sigma x=gx$ for every $x$, and $\sigma=g$. $\square$

**Lemma 3.** Let $X$ and $Y$ be faithful, individually $3$-closed $G$-sets. If $X$ has a base of size at most two, then the diagonal action on $X\sqcup Y$ is $3$-closed.

**Proof.** A closure permutation preserves the two point-orbits and, by individual $3$-closedness, restricts to elements $g,h\in G$ on $X$ and $Y$. After multiplication by the diagonal action of $g^{-1}$, it is the identity on $X$ and acts as some $t\in G$ on $Y$. If $(u,v)$ is a base for $X$, the closure condition applied to $(u,v,y)$ supplies an element $s\in G$ fixing $u$ and $v$ and satisfying $sy=ty$. The base property gives $s=1$, so $ty=y$ for every $y\in Y$. Faithfulness of $Y$ gives $t=1$. $\square$

### Reduction to three maximal geometries

The maximal proper subgroups of $G$ form three geometric conjugacy classes:

1. point stabilizers $G_p\cong S_4$ for $p\in\mathcal P$;
2. line stabilizers $G_L\cong S_4$ for $L\in\mathcal P^*$;
3. normalizers of Sylow $7$-subgroups, isomorphic to $C_7\!:\!C_3$, which are the point stabilizers in the action on $\mathcal Q$.

For completeness, let $M$ be maximal. If $M$ is not transitive on the seven nonzero vectors of $V$, take the sum of the vectors in each $M$-orbit. A nonzero orbit sum is an $M$-fixed point. If every orbit sum is zero, the nontransitive orbit partition must have sizes $3$ and $4$; the three-vector orbit is the set of nonzero vectors in a two-dimensional subspace, so $M$ fixes a line. Thus $M$ is a point or line stabilizer.

If $M$ is transitive, then $7$ divides $|M|$. The group $G$ has eight Sylow $7$-subgroups. A proper $M$ cannot contain all eight, since their conjugates generate the nontrivial normal closure of a Sylow subgroup in the simple group $G$. Hence $M$ has a normal Sylow $7$-subgroup and lies in its normalizer of order $21$. This normalizer is maximal: a proper overgroup would have order $42$ or $84$ and would give a faithful action of the simple group $G$ of degree $4$ or $2$, which is impossible.

Every proper subgroup of an $S_4$ maximal subgroup is contained in a subgroup of type $A_4$, $D_8$, or $S_3$. Every proper subgroup of $C_7\!:\!C_3$ is contained in $C_7$ or $C_3$. Each such subgroup is contained in a subgroup having a conjugate with trivial intersection:

- For $p=\langle e_1\rangle$, the canonical $A_4$ in $G_p$ is the inverse image of $A_3$ under the action on $V/p$. The corresponding canonical $A_4$ subgroups for $\langle e_1\rangle$ and $\langle e_2\rangle$ intersect trivially. Indeed, an element in their intersection fixes $e_1,e_2$ and has $e_3\mapsto e_3+a e_1+b e_2$; membership in the first $A_4$ forces $b=0$, while membership in the second forces $a=0$. Duality gives the same conclusion for the line-type $A_4$ subgroups.
- A Sylow $D_8$ is the stabilizer of an incident point-line flag. The stabilizers of $(\langle e_1\rangle,\langle e_1,e_2\rangle)$ and $(\langle e_3\rangle,\langle e_2,e_3\rangle)$ intersect trivially: an element in the intersection fixes $e_1,e_3$, while preservation of both planes forces it to fix $e_2$.
- An $S_3$ is the stabilizer of a nonincident point-line pair. The stabilizers of $(\langle e_1\rangle,\langle e_2,e_3\rangle)$ and $(\langle e_2\rangle,\langle e_1,e_2+e_3\rangle)$ intersect trivially, as follows directly by writing the first stabilizer in block-diagonal form relative to $\langle e_1\rangle\oplus\langle e_2,e_3\rangle$.
- Distinct Sylow $7$-subgroups intersect trivially. An order-$3$ subgroup is conjugate into one of the displayed $S_3$ subgroups, so it is covered as well.

The property $H\cap H^g=1$ passes to subgroups of $H$ and says exactly that the coset action on $G/H$ has a two-point base. Consequently every proper-subgroup coset action except the three maximal actions $\mathcal P$, $\mathcal P^*$, and $\mathcal Q$ has base size at most two.

### The three exceptional actions

**Lemma 4.** The actions of $G$ on $\mathcal P$, $\mathcal P^*$, and $\mathcal Q$ are individually $3$-closed.

**Proof.** On $\mathcal P$, the $G$-orbits on ordered triples of distinct points distinguish collinear from noncollinear triples. A permutation in the $3$-closure therefore preserves the lines of the Fano plane. Three noncollinear points form a vector-space basis, so their images determine a unique element of $\operatorname{GL}(3,2)$. Preservation of the third point on each Fano line then determines all remaining points. Thus every element of the $3$-closure lies in $G$. Duality proves the assertion for $\mathcal P^*$.

For $\mathcal Q=\mathbb P^1(\mathbb F_7)$, the group $\operatorname{PGL}(2,7)$ acts sharply transitively on ordered triples of distinct points, while $G=\operatorname{PSL}(2,7)$ has two orbits on those triples. For a distinct triple $T$, let $\varepsilon(T)$ be the quadratic character of the determinant of the unique projective transformation carrying $(\infty,0,1)$ to $T$. Projective rescaling changes the determinant by a square, so $\varepsilon$ is well-defined and its two values distinguish the two $G$-orbits.

Let $\sigma$ belong to the $3$-closure. After composition with an element of $G$, assume that it fixes $\infty,0,1$. For $x\in\mathbb F_7\setminus\{0,1\}$, preservation of the colors of $(\infty,0,x)$ and $(\infty,1,x)$ preserves the pair

$$
(\chi(x),\chi(x-1)),
$$

where $\chi$ is the quadratic character. Since the nonzero squares modulo $7$ are $1,2,4$, the signatures are

$$
2:(+,+),\quad 3:(-,+),\quad 4:(+,-),\quad 5:(-,+),\quad 6:(-,-).
$$

Thus $\sigma$ fixes $2,4,6$ and can at most interchange $3$ and $5$. The colors of $(\infty,2,3)$ and $(\infty,2,5)$ are respectively $\chi(1)=+$ and $\chi(3)=-$, so that interchange is impossible. Hence the normalized permutation is the identity, and the action on $\mathcal Q$ is $3$-closed. $\square$

### Synchronizing the exceptional pairs

Consider a closure permutation on a disjoint union of two exceptional orbits. Lemma 4 permits us to normalize it so that it is the identity on the first orbit and is induced by some $t\in G$ on the second.

For $\mathcal P\sqcup\mathcal P$, choose distinct points $p,q$ in the first copy and let $r$ be the third point on their Fano line. The mixed tagged triple with $r$ in the second copy shows that $t(r)=r$, because every element fixing $p$ and $q$ also fixes $r$. Every point can occur as such an $r$, so $t=1$. Duality treats $\mathcal P^*\sqcup\mathcal P^*$.

For $\mathcal P\sqcup\mathcal P^*$, use distinct points $p,q$ in the first orbit and their joining line $L$ in the second. The closure condition forces $t(L)=L$. Every line is the join of two points, so $t=1$. The reversed pair is identical after exchanging the roles of the two orbits.

For $\mathcal Q\sqcup\mathcal Q$, choose distinct $u,v$ in the first copy and use the point $u$ in the second copy as the third entry. The closure condition supplies an element fixing $u$ and $v$ in the first action and hence fixing the corresponding point $u$ in the second action. Therefore $t(u)=u$. Varying $u$ gives $t=1$.

It remains to synchronize $\mathcal P$ with $\mathcal Q$. Fix distinct $p,q\in\mathcal P$, let $\ell$ be their Fano line, and put $E=G_{p,q}$. Then $E$ is the normal Klein four subgroup of the line stabilizer $G_\ell\cong S_4$. Every point stabilizer on $\mathcal Q$ has odd order $21$, so $E$ acts semiregularly on $\mathcal Q$ and has two orbits $B$ and $B^c$, each of size four.

We claim that the setwise stabilizer $G_B$ is the canonical $A_4$ inside $G_\ell$. First, $N_G(E)=G_\ell$: the line stabilizer normalizes $E$ and is maximal, while $E$ is not normal in the simple group $G$. Moreover, $G_\ell$ is transitive on $\mathcal Q$. Indeed, for $y\in\mathcal Q$, the order of $(G_\ell)_y$ divides both $24$ and $21$. It is therefore $1$ or $3$; the first possibility would give an orbit of length $24$ on an eight-point set, so the stabilizer has order $3$ and the orbit has length $8$. Since $E$ is normal in $G_\ell$, the two $E$-orbits are interchanged transitively, and their stabilizer inside $G_\ell$ is its index-two subgroup $A_4$.

This $A_4$ is all of $G_B$. Otherwise, a maximal proper overgroup of it would be an $S_4$. The $A_4$ is normal in that $S_4$, and its characteristic Klein four subgroup $E$ would also be normalized. The overgroup would therefore lie in $N_G(E)=G_\ell$ and hence equal $G_\ell$, contrary to the fact that $G_\ell$ interchanges $B$ and $B^c$. Thus $G_B=A_4\leq G_\ell$.

Now normalize a closure permutation on $\mathcal P\sqcup\mathcal Q$ to be the identity on $\mathcal P$ and to act as $t\in G$ on $\mathcal Q$. Applied to $(p,q,y)$, the closure condition gives

$$
t(y)\in E y
$$

for every $y\in\mathcal Q$. Hence $t$ stabilizes both $E$-orbits, so $t\in G_B\leq G_\ell$. The line $\ell$ was arbitrary; therefore $t$ lies in every line stabilizer. Their intersection is the kernel of the faithful action on $\mathcal P^*$, and hence is trivial. Thus $t=1$. The dual argument, with points and lines exchanged, synchronizes $\mathcal P^*$ with $\mathcal Q$.

We have now proved that every diagonal action on $G/H\sqcup G/K$, for arbitrary proper subgroups $H,K<G$ and with repetitions allowed, is $3$-closed. Indeed, if at least one stabilizer is nonmaximal, Lemmas 2 and 3 apply; if both are maximal, the preceding exceptional-pair arguments apply. Lemma 1 therefore shows that every faithful finite permutation representation of $G$ is $3$-closed. Hence $\operatorname{PSL}(2,7)$ is totally $3$-closed.

The proved statement is stronger than bare existence: it identifies a specific nonabelian simple Lie-type group and proves total $3$-closedness for all of its faithful finite permutation representations. It therefore implies the affirmative answer requested in Problem 20.2. $\square$

## Certification status

This proof is written from the integrated route `route_psl27_positive_example_rev32`. The two-orbit reduction and the complete $\operatorname{PSL}(2,7)$ pair analysis were independently accepted by the strict informal verifier, and the resulting sufficient route was accepted by the integration verifier with no unresolved proof debt.

## References

No external references are used. This final proof was written by the Albilich writer from the following internal artifacts:

- *PSL(2,7) is totally 3-closed*, artifact `proof_dossier_psl27_total_3closure_rev32`, researcher.
- *Two-orbit criterion for total 3-closure*, artifact `proof_dossier_two_orbit_reduction_rev24`, researcher.
- *Verification of the two-orbit reduction*, artifact `verification_report_two_orbit_reduction_rev28`, strict informal verifier.
- *Verification of the PSL(2,7) positive example*, artifact `verification_report_psl27_positive_example_rev36`, strict informal verifier.
- *Root integration report for the PSL(2,7) positive example*, artifact `integration_report_psl27_positive_example_root_rev40`, integration verifier.

## Proved Result

The finite group PSL(2,7) is a nonabelian simple group of Lie type and is totally 3-closed.

## Certified Partial Results

- `claim_psl2_proper_field_nonclosure` `informally_verified` `partial`: Let q=p^f≥4. If f>1, then PSL(2,q) is not totally 3-closed. Moreover, PSL(2,5) is not totally 3-closed.
- `claim_psln_projective_nonclosure` `informally_verified` `partial`: Let n≥3 and q=p^f. If f>1 or gcd(n,q−1)>1, then PSL(n,q) is not totally 3-closed; its natural action on P^{n−1}(F_q) has 3-closure properly containing PSL(n,q).
- `claim_two_orbit_reduction_total_3closure` `informally_verified` `partial`: Let S be a finite nonabelian simple group. Then S is totally 3-closed if and only if, for every pair H,K of proper subgroups of S with repetition allowed, the diagonal action of S on S/H disjoint union S/K is 3-closed.

## Route Scoreboard

- `route_psl27_positive_example_rev32` `verified_part` score=2.9 root_distance=0 verified=1/1
- `route_two_orbit_reduction_total_3closure` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_psl2_projective_witness` `stalled` score=0.82 root_distance=1 verified=1/1 reasons=['advisor or triage report paused this stale route']
- `route_psln_projective_nonclosure` `stalled` score=0.82 root_distance=1 verified=1/1 reasons=['advisor or triage report paused this stale route']

## Branches

- Parallel branch mode: `multi_branch_research` with up to 3 simultaneous branch workers

```text
Branch: route_psl27_positive_example_rev32
Goal: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is the largest subgr...
Status: needs_cas
Verified facts: root: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and...
Candidate facts: none recorded
Active blockers: debt_psl27_complete_pair_coset_closures (blocking): For S=PSL(2,7), enumerate every conjugacy class of proper subgroups H,K, including H=K and the trivial subgroup, and determine the exact 3-closure of the diagonal action on S/H...
Failed methods: none recorded
Useful sources: retrieval_freedman_giudici_praeger_2024_thm_1_2b: Writing k(G) for the least total-closure degree, every finite simple exceptional Lie-type group outside the alternating isomorphism class satisfies k(G) <= 7.
Next recommended lemma: prove root: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and...
Similar lemmas worth trying: prove a special case of the branch goal first: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is the largest subgr...; prove a bridge lemma connecting the verified branch facts to: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is the largest subgr...
Failed methods (do not retry unchanged): obstruction_psl24_not_totally_3closed_rev0: root_not_refuted_candidate_eliminated [fingerprint candidate_group_eliminated]; obstruction_psl27_low_degree_cosets_rev16: Targeted interface: `PSL(2,7) has a faithful transitive coset action of degree at most 32 whose 3-closure properly contains PSL(2,7)`. The exhaustive GAP cer... [fingerprint route_killing_bounded_finite_obstruction]; obstruction_psl27_bounded_transitive_bridge_rev18: # Offline adversarial audit of the PSL(2,7) interface ## Named interface attacked Let G=PSL(2,7). The advisor interface asserts that there is a proper subgro... [fingerprint exhaustive_finite_scope_failure_and_missing_reduction]
Last useful delta: verified_claim: claim root verified (at 2026-07-15T01:46:52.558726+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim root verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_two_orbit_reduction_total_3closure
Goal: Let S be a finite nonabelian simple group. Then S is totally 3-closed if and only if, for every pair H,K of proper subgroups of S with repetition allowed, the diagonal action of S on S/H disjoint union S/K is 3-closed.
Status: keep_exploiting
Verified facts: claim_two_orbit_reduction_total_3closure: Let S be a finite nonabelian simple group. Then S is totally 3-closed if and only if, for every pair H,K of proper subgroups of S with repetition allowed, the diagonal action of...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: retrieval_freedman_giudici_praeger_2024_thm_1_2b: Writing k(G) for the least total-closure degree, every finite simple exceptional Lie-type group outside the alternating isomorphism class satisfies k(G) <= 7.
Next recommended lemma: extend the verified chain toward the branch goal: Let S be a finite nonabelian simple group. Then S is totally 3-closed if and only if, for every pair H,K of proper subgroups of S with repetition allowed, the diagonal action of S on S/H disjoint union S/K is 3-closed.
Similar lemmas worth trying: prove a special case of the branch goal first: Let S be a finite nonabelian simple group. Then S is totally 3-closed if and only if, for every pair H,K of proper subgroups of S with repetition allowed, the diagonal action of S on S/H disjoint union S/K is 3-closed.; prove a bridge lemma connecting the verified branch facts to: Let S be a finite nonabelian simple group. Then S is totally 3-closed if and only if, for every pair H,K of proper subgroups of S with repetition allowed, the diagonal action of S on S/H disjoint union S/K is 3-closed.
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim claim_two_orbit_reduction_total_3closure verified (at 2026-07-15T01:28:05.329904+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim claim_two_orbit_reduction_total_3closure verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_psl2_projective_witness
Goal: Let q=p^f≥4. If f>1, then PSL(2,q) is not totally 3-closed. Moreover, PSL(2,5) is not totally 3-closed.
Status: pause_or_merge
Verified facts: claim_psl2_proper_field_nonclosure: Let q=p^f≥4. If f>1, then PSL(2,q) is not totally 3-closed. Moreover, PSL(2,5) is not totally 3-closed.
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: none recorded
Next recommended lemma: extend the verified chain toward the branch goal: Let q=p^f≥4. If f>1, then PSL(2,q) is not totally 3-closed. Moreover, PSL(2,5) is not totally 3-closed.
Similar lemmas worth trying: prove a special case of the branch goal first: Let q=p^f≥4. If f>1, then PSL(2,q) is not totally 3-closed. Moreover, PSL(2,5) is not totally 3-closed.; prove a bridge lemma connecting the verified branch facts to: Let q=p^f≥4. If f>1, then PSL(2,q) is not totally 3-closed. Moreover, PSL(2,5) is not totally 3-closed.
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim claim_psl2_proper_field_nonclosure verified (at 2026-07-15T00:51:36.977951+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim claim_psl2_proper_field_nonclosure verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_psln_projective_nonclosure
Goal: Let n≥3 and q=p^f. If f>1 or gcd(n,q−1)>1, then PSL(n,q) is not totally 3-closed; its natural action on P^{n−1}(F_q) has 3-closure properly containing PSL(n,q).
Status: pause_or_merge
Verified facts: claim_psln_projective_nonclosure: Let n≥3 and q=p^f. If f>1 or gcd(n,q−1)>1, then PSL(n,q) is not totally 3-closed; its natural action on P^{n−1}(F_q) has 3-closure properly containing PSL(n,q).
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: retrieval_freedman_giudici_praeger_2024_thm_1_2b: Writing k(G) for the least total-closure degree, every finite simple exceptional Lie-type group outside the alternating isomorphism class satisfies k(G) <= 7.
Next recommended lemma: extend the verified chain toward the branch goal: Let n≥3 and q=p^f. If f>1 or gcd(n,q−1)>1, then PSL(n,q) is not totally 3-closed; its natural action on P^{n−1}(F_q) has 3-closure properly containing PSL(n,q).
Similar lemmas worth trying: prove a special case of the branch goal first: Let n≥3 and q=p^f. If f>1 or gcd(n,q−1)>1, then PSL(n,q) is not totally 3-closed; its natural action on P^{n−1}(F_q) has 3-closure properly containing PSL(n,q).; prove a bridge lemma connecting the verified branch facts to: Let n≥3 and q=p^f. If f>1 or gcd(n,q−1)>1, then PSL(n,q) is not totally 3-closed; its natural action on P^{n−1}(F_q) has 3-closure properly containing PSL(n,q).
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim claim_psln_projective_nonclosure verified (at 2026-07-15T01:20:13.193205+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim claim_psln_projective_nonclosure verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

## Research Strategy

Strategic artifacts are persisted proof-state context, not verified mathematical evidence.

- Latest global advisor synthesis: `art_auto_phd_advisor_root_advisor_synthesis_945e95aec86a`
- Latest active proof compression: `none`
- Bridge search: `bridge_lemma_search_psl27_rev32`; candidates=2, selected=`bridge_base_two_pair_synchronization`
- Conjecture portfolio: `none`; candidates=0, selected=`none`
- Active invention authorization: `none`
- Global synthesis due: `False`; reasons=[]
- Graph-derived decisive obligation: `none`; selected route=`none`, ready_for_verification=False
- Verifier-filtered outcome learning: family=`research`; local families=0; reference_solution_used=False
- Deep-session ROI: allowed=True; reason=deep-session ROI gate is open
- Information-gain policy: scheduler exposes closing, refuting, root-progress, information, reuse, duplication, token, wall-time, verification-cost, and verifier-filtered outcome components; speculative work never consumes the protected verification reserve.
- Method library policy: 18 developer-curated structural/domain method cards are advisory only and are kept separate from verified facts, external theorem cards, and private speculation.

## Fact Graph

Read-only graph view generated from claims, routes, inferences, debts, and sources.

- Nodes: verified_fact=8, candidate_fact=1, obstruction=1, source_fact=1, branch_cluster=4
- Edges: uses=0, depends_on=0, blocks=1, repairs=0, same_as=0, supersedes=0
- Edge types awaiting a data source (not derived): contradicts, generalizes, specializes
- Branch depth report:
  - `route_psl2_projective_witness` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_psln_projective_nonclosure` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_two_orbit_reduction_total_3closure` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_psl27_positive_example_rev32` blocked (depth=0, verified=2, candidate=0, active_obstructions=1, blocked)

## Retrieval Cards

- `retrieval_freedman_giudici_praeger_2024_thm_1_2b` `partial_match` confidence=high: Writing k(G) for the least total-closure degree, every finite simple exceptional Lie-type group outside the alternating isomorphism class satisfies k(G) <= 7.

## Claims

- `claim_psl2_proper_field_nonclosure` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let q=p^f≥4. If f>1, then PSL(2,q) is not totally 3-closed. Moreover, PSL(2,5) is not totally 3-closed.
- `claim_psln_projective_nonclosure` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let n≥3 and q=p^f. If f>1 or gcd(n,q−1)>1, then PSL(n,q) is not totally 3-closed; its natural action on P^{n−1}(F_q) has 3-closure properly containing PSL(n,q).
- `claim_two_orbit_reduction_total_3closure` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let S be a finite nonabelian simple group. Then S is totally 3-closed if and only if, for every pair H,K of proper subgroups of S with repetition allowed, the diagonal action of S on S/H disjoint union S/K is 3-closed.
- `root` `informally_verified` `integrated` `root_theorem` maturity=integrated root_distance=0: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type

## Problem

Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set
\(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is
the largest subgroup of \(\operatorname{Sym}(\Omega)\) whose orbits on the set
\(\Omega^{k}\) of ordered \(k\)-tuples coincide with the orbits of \(G\) on
\(\Omega^{k}\) (Wielandt). The group \(G\) is **\(k\)-closed** on \(\Omega\) if
\(G^{(k)} = G\).

An abstract group \(G\) is **totally \(k\)-closed** if for every faithful
permutation representation of \(G\) on a finite set \(\Omega\), the image of
\(G\) in \(\operatorname{Sym}(\Omega)\) is \(k\)-closed.

**Question (Problem 20.2).** Are there any nonabelian simple groups of Lie type
which are totally 3-closed?

Known context: the finite nonabelian simple totally 2-closed groups are
completely classified — there are exactly six, all sporadic groups
(\(\mathrm{J}_1\), \(\mathrm{J}_3\), \(\mathrm{J}_4\), \(\mathrm{Ly}\),
\(\mathrm{Th}\), and the Monster \(\mathrm{M}\)), the largest being the Monster.
Since a totally 2-closed group is totally 3-closed, the real content of the
question is whether total 3-closure can occur for simple groups of Lie type,
where total 2-closure provably cannot.

## Instructions

Treat this as a serious research problem, not only as a benchmark. The target is
to either exhibit a nonabelian simple group of Lie type that is totally
3-closed (with proof), or prove that no nonabelian simple group of Lie type is
totally 3-closed, or establish an honest, precisely stated partial result.

Use direct proof attempts before reducing unless a reduction is mathematically
motivated. Literature search and citations are allowed, and cited theorems may
be used to close a case when the statement is properly identified and logically
applied. The classification of totally 2-closed simple groups and the toolkit
around \(k\)-closures of permutation groups (Wielandt's theory, Praeger–Saxl,
recent work of Abdollahi, Arezoomand, Tracey and coauthors on total
\(k\)-closure) are natural starting points. If an exact published result
answers the question, integrate it responsibly instead of reproving it.

Group-theoretic computation (e.g. GAP) may be used for examples, sanity checks,
and small Lie-type groups: computing \(3\)-closures of specific faithful
permutation representations of small groups such as \(\mathrm{PSL}(2,q)\) for
small \(q\) is encouraged as evidence, and a single faithful representation
that fails to be 3-closed rules that group out. The final argument must be a
mathematical proof or a mathematically rigorous obstruction; finite
computations alone settle individual groups, not the general question, unless
combined with a reduction theorem.
- `claim_psl24_not_totally_3closed` `plausible` `active` `main_trunk` maturity=proposed root_distance=1: The nonabelian simple Lie-type group PSL(2,4) is not totally 3-closed: in its faithful degree-5 projective action, 3-transitivity makes the five orbits on ordered triples equal to the five equality-pattern classes, so the 3-closure is S5, strictly larger than PSL(2,4) of order 60.

## Active Proof Debts

- `debt_psl27_complete_pair_coset_closures` `blocking` on `root`: For S=PSL(2,7), enumerate every conjugacy class of proper subgroups H,K, including H=K and the trivial subgroup, and determine the exact 3-closure of the diagonal action on S/H disjoint union S/K. Produce either one certified proper closure or a complete certificate that every pair action is 3-closed.
