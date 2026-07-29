# Albilich v1 Report: kourovka/problem_20_2_psl3_family_classification

- Outcome: solved_final
- Public status: solved
- Result kind: exact
- Result classification: full_theorem_solved
- Relation to target: exact
- Result summary: Solved exactly: the verified result matches the target theorem.
- Completion policy: full_proof_first
- Revision: 1356
- Claims: 86 total, 85 verified, 83 integrated
- Routes: 87 total, 2 active
- Active debts (ledger only): 3 total, 3 blocking
- Tokens: 378602459 reported spent, 41232795 remaining, 10000000 reserved
- Run status: completed
- Wall-clock elapsed since run start: 110h 5m 12s
- Active backend compute (child-session wall time): 80h 3m 52s
- Paused time (excluded from active compute): 8m 54s across 2 pause interval(s)
- Peak recorded child memory: 1.43 GB
- Stored memory artifacts: 2.69 MB (2818856 bytes)
- Native result directory: 351.70 MB (368782361 bytes)
- Downloaded source directory: 0 bytes

## Root Statement

# Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_3(q)\)

## Definitions

For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), its
**3-closure** \(G^{(3)}\) is the largest subgroup of
\(\operatorname{Sym}(\Omega)\) having the same orbits as \(G\) on ordered
triples \(\Omega^3\). A finite abstract group is **totally 3-closed** when
every faithful finite permutation representation of it is 3-closed.

## Restricted classification problem

Classify, up to isomorphism, every nonabelian simple group

\[
S=\operatorname{PSL}_3(q)
\]

that is totally 3-closed, for every prime power \(q\) for which
\(\operatorname{PSL}_3(q)\) is nonabelian simple.

This run concerns the projective dimension-three family only. Do not schedule
research on \(\operatorname{PSL}_n(q)\) with \(n\neq3\), or on unitary,
symplectic, orthogonal, exceptional, twisted, Suzuki, Ree, or alternating
families, except to use the exceptional isomorphism
\(\operatorname{PSL}_3(2)\cong\operatorname{PSL}_2(7)\).

The final result must be an if-and-only-if theorem. It must:

1. prove total 3-closure for every surviving \(\operatorname{PSL}_3(q)\) in
   every faithful finite permutation representation;
2. exclude every other simple \(\operatorname{PSL}_3(q)\) by a uniform theorem
   or an explicit faithful action with strictly larger 3-closure;
3. cover all prime powers, simplicity exceptions, and the exceptional
   isomorphism at \(q=2\);
4. distinguish uniform arguments from bounded computations;
5. give exact references, theorem numbers, and checked hypothesis translations
   for every maximal-subgroup, base-size, orbit, or classification theorem.

## Certified premises from the current PSL ledger

The supervising mathematician authorizes the following integrated results as
fixed premises. Preserve their exact scope and import their certified dependency
closure rather than reproving them.

1. **Two-orbit reduction.** For a finite nonabelian simple group \(S\), total
   3-closure is equivalent to 3-closedness of every diagonal action on
   \(S/H\sqcup S/K\), for all proper \(H,K<S\), with repetition allowed.
2. **Projective outer obstruction.** If \(q=p^f\) with \(f>1\), or if
   \(\gcd(3,q-1)>1\), then \(\operatorname{PSL}_3(q)\) is not totally
   3-closed; its natural projective-point action has a proper semilinear or
   diagonal 3-closure overgroup.
3. **The \(q=2\) survivor.**
   \(\operatorname{PSL}_3(2)\cong\operatorname{PSL}_2(7)\) is totally
   3-closed.
4. **Base-two synchronization.** A two-constituent diagonal action is
   3-closed when its constituent actions are 3-closed and one constituent has
   a base of size at most two.
5. **Rank-three scalar-fiber rigidity.** If \(p\) is prime and
   \(\gcd(3,p-1)=1\), every action of \(\operatorname{PSL}_3(p)\) on
   \((\mathbb F_p^3\setminus\{0\})/C\), for \(C\leq\mathbb F_p^\times\),
   is faithful and 3-closed. Determinant-character twists of the point
   parabolic give the same actions. This is a route obstruction: scalar fibers
   cannot provide a nonclosure witness.
6. **Exact \(\operatorname{PSL}_3(3)\) exceptional-parabolic theorem E3.**
   For a point stabilizer \(P\), the exceptional family
   \(\mathcal E(P)=\{H<P:H\cap H^g\neq1\text{ for every }g\in G\}\)
   consists of 24 subgroups in six \(G\)-classes, represented by orders
   \(48,54,72,108,144,216\). Every corresponding transitive action is
   3-closed, as is every dual line-parabolic action.
7. **Exact exceptional mixed-pair theorem M3.** Every diagonal action on
   \(G/H\sqcup G/K\), with \(H,K\) in those six exceptional point classes or
   their dual line classes, is 3-closed.

The unresolved prime-field parameters are therefore

\[
p=3\quad\text{or}\quad p\equiv2\pmod3.
\]

Do not treat the failure of a proposed graph, scalar-fiber, flag, or coset
witness as evidence of total 3-closure. Conversely, do not declare a group
non-totally-3-closed without an explicit faithful action and a proved proper
triple-orbit preserver.

## Research order

### Priority 1: finish \(\operatorname{PSL}_3(3)\)

Attempt the shortest complete two-orbit proof now. The decisive obligations are:

1. certify an exact complete maximal-subgroup list for
   \(\operatorname{PSL}_3(3)\), with source theorem or reproducible bounded
   computation and checked fusion/conjugacy information;
2. prove that the point and line parabolics, Singer normalizer, conic
   stabilizer, and every proper subgroup below them exhaust all proper
   subgroups;
3. assemble every pair \(G/H\sqcup G/K\), explicitly including pairs involving
   the point or line parabolic itself, exceptional refinements, repeated
   constituents, Singer-normalizer descendants, and conic-stabilizer
   descendants;
4. either integrate the resulting total-3-closure theorem or exhibit a concrete
   counterexample pair action.

### Priority 2: classify residual prime parameters uniformly

For primes \(p\equiv2\pmod3\), decide whether
\(\operatorname{PSL}_3(p)\) is totally 3-closed. Seek one theorem-level
architecture that scales with \(p\):

- a maximal-subgroup/base-size reduction plus exact synchronization of the
  high-base constituents;
- a genuinely nonnormalizing two-coset witness satisfying all mixed triple
  conditions;
- a graph-stable nonparabolic action with verified quotient-surjectivity for
  every ordered triple;
- or a structural invariant forcing every faithful action to be 3-closed.

The scalar-fiber route is closed and must not be repeated without a genuinely
new action. Test small primes \(p=5,11,17\) only as bounded probes designed to
distinguish competing uniform conjectures; do not extrapolate finite output.

### Parallel branches

When three branches are available, use genuinely different philosophies:

1. **finite closure assembly:** close \(\operatorname{PSL}_3(3)\) with an exact
   maximal-subgroup interface and a complete two-orbit proof;
2. **uniform structural branch:** attack all primes \(p\equiv2\pmod3\) through
   maximal subgroups, bases, factorizations, or a conceptual invariant;
3. **adversarial/literature/CAS branch:** search for a full-hypothesis witness
   or counterexample pattern at \(p=5,11,17\), and adapt exact cited theorems
   rather than performing a broad survey.

Run full-proof-first. Periodically draft the shortest complete classification
proof and mark each unsupported sentence. Suppress all binary and higher-rank
branches as out of scope; retain their certified results only as archived
background.

## Benchmark Quantitative Snapshot

| Quantity | Albilich v1 benchmark run |
| --- | ---: |
| Iterations / generator calls | 730 |
| Wall-clock elapsed (seconds) | 396312.258 |
| Active compute wall time (seconds) | 288232.361 |
| Active compute wall time (hours) | 80.06 |
| Paused time (seconds) | 533.606 |
| Reported tokens | 378602459 |
| Search / theorem-retrieval calls | 29 |
| Verifier-call estimate | 166 |
| Advisor / reducer calls | 192 |
| Stored memory artifacts | 2818856 bytes |
| Native result directory | 368782361 bytes |
| Downloaded source directory | 0 bytes |

Memory in this table follows the legacy benchmark convention: stored artifact/source directory size, not peak process RSS. Peak RSS is reported separately when the runner can sample it.

Timing convention: wall-clock elapsed runs from problem init to the last recorded activity; active compute is the recorded child-session wall time; paused time covers explicit run-pause intervals and is excluded from active compute.

## Run Control Events

- `2026-07-17T09:14:26.045782+00:00` `running -> pause_requested` [cli] Initialize PSL_3-only target paused for certified scope import from the current PSL_n ledger.
- `2026-07-17T09:15:05.688706+00:00` `pause_requested -> paused` [workflow] pause request honored: current child session finished; no new actions dispatched
- `2026-07-17T09:17:42.708005+00:00` `paused -> running` [cli] Begin PSL_3-only classification research from certified imported PSL ledger; prioritize PSL_3(3) completion and the residual prime classes p congruent to 2 mod 3.
- `2026-07-17T22:19:47.343190+00:00` `running -> pause_requested` [cli] Operator requested an immediate safe pause; finish current active children, apply admissible patches, and dispatch no new actions.
- `2026-07-18T04:48:45.274186+00:00` `pause_requested -> paused` [workflow] pause request honored: current child session finished; no new actions dispatched
- `2026-07-18T04:55:01.860427+00:00` `paused -> running` [cli] Operator requested continuation from revision 179 after the stalled transport child was terminated; preserve the current proof state and resume the residual PSL_3(p), p congruent to 2 mod 3, classification.
- `2026-07-18T12:12:24.670200+00:00` `running -> stopped` [workflow_exception] workflow aborted by _WorkflowTerminationSignal: received signal 15
- `2026-07-18T12:12:24.903802+00:00` `stopped -> running` [workflow] workflow started; clearing already-honored run_status stopped
- `2026-07-21T23:19:38.192504+00:00` `running -> completed` [workflow] scheduler stopped: stop_solved

## Final Proof

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

## Proved Result

Among the nonabelian simple groups PSL_3(q), total 3-closure holds if and only if q is prime and either q=3 or q is congruent to 2 modulo 3.

## Certified Partial Results

- `claim_import_psl27_totally_3closed` `informally_verified` `partial`: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
- `claim_import_psln_projective_nonclosure` `informally_verified` `partial`: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or diagonal outer automorphism.
- `claim_import_two_orbit_reduction` `informally_verified` `partial`: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
- `claim_root_a5_degree3_orthogonal_internal_rev1059` `informally_verified` `partial`: Let p > 5 be prime with p congruent to 2 modulo 3. Every subgroup A of SL_3(p) isomorphic to A_5 is contained in an SL_3(p)-conjugate of SO_3(p).
- `claim_root_base2_constituent_synchronization_rev369` `informally_verified` `partial`: Let G act faithfully on two transitive sets Omega_1 and Omega_2. Assume both constituent actions are 3-closed and the action on Omega_1 has a base of size at most two. Then the diagonal action of G on the disjoint union Omega_1 disjoint union Omega_2 is 3-closed.
- `claim_root_bloom_nonorthogonal_simple_subgroups_rev1051` `informally_verified` `partial`: Let p >= 5 be prime with p congruent to 2 modulo 3, and let T < SL_3(p) be a proper nonabelian simple subgroup. If T is not contained in any conjugate of SO_3(p), then T is isomorphic to PSL_2(7); moreover p^3 is congruent to 1 modulo 7.
- `claim_root_c2c3_uniform_base2_descendants_rev966` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3 and G=SL_3(p)=PSL_3(p). Let N_2 be the determinant-one monomial subgroup and N_3=GammaL_1(p^3) intersect G. For every H<=N_2 or H<=N_3, the action of G on G/H has a base of size at most two and hence is 3-closed. Moreover, if G on G/K is 3-closed, then the diagonal action on G/H disjoint union G/K is 3-closed.
- `claim_root_c2c3s_uniform_base2_descendants_rev1155` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3 and G=PSL_3(p). If H≤M<G, where M is a maximal subgroup of Aschbacher type C2, C3, or S, then b(G,G/H)≤2. For M itself the base size is exactly two. In the linear C2 family there is no maximal C2 row at p=5.
- `claim_root_c8_s_base2_hosts_rev1216` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). Every subgroup H contained in an orthogonal C8 subgroup of G has b(G,G/H)≤2. Every subgroup H contained in an Aschbacher-S maximal subgroup of G also has b(G,G/H)≤2.
- `claim_root_core_overlap_frame_gluing_rev1234` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P a point or line parabolic, H<=P, and X_x the fibers of H backslash G -> P backslash G. Put N_x=core_(P_x)(H_x). If H does not contain P^0, then N_x intersect N_y=1 for all distinct x,y; if H contains P^0, every determinant-neutral fiberwise permutation is pointwise trivial. Consequently, any quotient-fixing permutation whose restrictions on the three complete fibers of every projective frame are induced by one frame-stabilizer element is the identity.
- `claim_root_cyclic_antiframe_3closed_rev648` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3, let G=SL_3(p)=PSL_3(p), and let D≤F_p^×. For Y_D={(v,φ):v≠0, φ≠0, φ(v)=1}/D, where d sends (v,φ) to (dv,d^{-1}φ), the natural permutation action of G on Y_D is 3-closed.
- `claim_root_dihedral_frame_tensor_block_kernel_rev1173` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3, let G=SL_3(p), let P=Q⋊GL_2(p) be a point parabolic, let L be generated by [[0,1],[1,0]] and [[0,1],[-1,1]], and let H=Q⋊L. In the action on H\G, assume the canonical projective block system is invariant under G^(3). Then the kernel of G^(3) on that block system is trivial. The dual line-parabolic assertion also holds.
- `claim_root_dihedral_levi_fixedfiber_reduction_rev891` `informally_verified` `partial`: For the p=11 and p=17 dihedral-Levi actions G on G/H used in the selected separator route, 37 of the 64 fixed-set inclusions hold formally because at least one row entry is the identity. For every remaining row, Fix(<k_1^(-1)k_0,k_2^(-1)k_0>) subseteq Fix(k_0) is equivalent to the projective invariant-line and GL_2/L fiber-extension conditions stated in art_researcher_root_dihedral_levi_fixedfiber_reduction_rev891.
- `claim_root_general_multiseparator_criterion_rev148` `informally_verified` `partial`: Let a finite group X act transitively on Lambda. Choose a0,a1,a2 in Lambda and, for {i,j,k}={0,1,2}, put K_i=X_{a_j,a_k}. If for every k_i in K_i minus {1}, the subgroup <k_1^{-1}k_0,k_2^{-1}k_0> is not contained in any X-conjugate of X_{a0}, then X is 3-closed on Lambda.
- `claim_root_graphcentralizer_uniform_obstruction_rev69` `informally_verified` `partial`: Let p be prime and n>=3 with gcd(n,p-1)=1. Put S=PSL_n(p)=SL_n(p), X=S semidirect <tau> with tau(g)=g^{-T}, and L=C_X(tau). Then there is an ordered triple in X/L whose pointwise stabilizer is contained in S. Consequently X is not contained in the 3-closure of S on X/L. In particular, the graph-centralizer action cannot witness non-total 3-closure for PSL_5(2) or for any member of the residual prime-field family.
- `claim_root_graphstable_geometric_nogo_rev93` `informally_verified` `partial`: Let p be prime, n>=3, gcd(n,p-1)=1, S=SL_n(p)=PSL_n(p), and X=S semidirect <tau> with tau(g)=g^{-T}. (i) If P<S is a proper parabolic with N_X(P) not contained in S, then on X/N_X(P) the relative outer base of X over S is at most three, so X is not contained in the 3-closure of S. (ii) If J is the stabilizer of a standard ordered two-block direct decomposition and H=<J,tau>, then on X/H the relative outer base is at most two, so again X is not contained in the 3-closure of S.
- `claim_root_graphstable_multiblock_imprimitive_nogo_rev99` `informally_verified` `partial`: Let p be prime, n=rd with r>=3, d>=1, gcd(n,p-1)=1, and S=PSL_n(p) nonabelian simple. Let X=S semidirect <tau>, tau(g)=g^{-T}, and let H be generated by tau and the S-stabilizer of an unordered decomposition of F_p^n into r equal d-dimensional summands. On Omega=X/H, b_rel(X,S;Omega)<=3; hence X intersect S^(3)=S. Thus this full graph-stable imprimitive action cannot witness non-3-closure via the graph extension.
- `claim_root_highbase_certificate_assembly_rev193` `informally_verified` `partial`: Let G be a finite nonabelian simple group. Suppose every proper H<G with b(G,G/H)>2 has a 3-closed coset action, and suppose that for every ordered pair H,K of such high-base subgroups there exist anchors a_0,a_1,a_2∈G/H whose three fixed pair-stabilizers L_i satisfy L_0x∩L_1x∩L_2x={x} for every x∈G/H⊔G/K. Then G is totally 3-closed.
- `claim_root_intrinsic_psl27_srow_base2_rev934` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3 and put G=SL_3(p)=PSL_3(p). If S≤G is isomorphic to PSL_2(7), then b(G,G/S)=2. Moreover, the existence of S forces p modulo 7 to lie in {1,2,4}.
- `claim_root_irreducible_levi_structural_reduction_rev111` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, G=PSL_3(p)=PGL_3(p), P=Q semidirect GL_2(p) a point parabolic, and H<=P with irreducible Levi image L. Every 3-closure element on G/H induces an element of G on G/P and, after normalization, preserves Orb_2(G_x,PG(2,p)) for every x; injectivity of this fingerprint on P/H implies 3-closure. Moreover H intersect Q is 1 or Q. In the first case H is a cocycle graph and H intersect H^{q_v} is isomorphic to C_L(v), so b(G,H)>2 implies L has no regular orbit on Q. In the second case H=Q semidirect L. If H is normal in P, then H=Q semidirect det^{-1}(C) for some C<=F_p^times and is a certified scalar-fiber stabilizer. The contragredient-dual line statements hold.
- `claim_root_large_levi_cohomology_antiframe_rev640` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P=Q semidirect GL_2(p), and H<=P have Levi projection R whose projective image contains PSL_2(p). Put D=det(R). Then R=det^(-1)(D). If H intersects Q trivially, H is Q-conjugate to R and b(G,G/H)<=3, with b(G,G/H)<=2 when D=1. If H contains Q, then G/H is the D-scalar-fiber action on nonzero vectors and is 3-closed. The dual statement holds in a line parabolic.
- `claim_root_large_levi_kernel_dichotomy_rev626` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, let G=PSL_3(p)=SL_3(p), and let P=Q semidirect GL_2(p) be a point or line parabolic. If H<=P and the projective image of pi(H) contains PSL_2(p), then SL_2(p)<=pi(H), H intersect Q is either 1 or Q, and H is respectively a 1-cocycle graph over pi(H) or Q semidirect pi(H). Moreover the projective image is PSL_2(p) or PGL_2(p).
- `claim_root_levi_split_torus_separator_rev1210` `informally_verified` `partial`: For every prime p≥5, every subgroup M≤GL_2(p) not containing SL_2(p), and every split maximal torus D≤GL_2(p), there exists g∈GL_2(p) such that D∩M^g=D∩core_{GL_2(p)}(M). Equivalently, the projective image of M has an ordered pair of distinct points of P^1(F_p) whose pointwise stabilizer is its projective core.
- `claim_root_listed_nonparabolic_base2_rev774` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). If M is the determinant-one monomial subgroup, a Singer-torus normalizer, a conic stabilizer SO(B), or any subgroup isomorphic to PSL_2(7) or A_6, then b(G,G/M)=2.
- `claim_root_local_quotient_surjectivity_criterion_rev42` `informally_verified` `partial`: Let G be normal in a faithful finite permutation group X on Omega. For alpha in Omega^3 let X_alpha be the pointwise stabilizer. Then X is contained in G^(3) if and only if X_alpha G=X for every alpha, equivalently every X_alpha maps surjectively onto X/G. If moreover G<X, this faithful action proves that G is not totally 3-closed.
- `claim_root_mixed_anchor_code_pair_criterion_rev179` `informally_verified` `partial`: Let G≤Sym(Λ) be finite. Choose a_0,a_1,a_2∈Λ and, for {i,j,k}={0,1,2}, put K_i=G_{a_j,a_k}. If K_0x∩K_1x∩K_2x={x} for every x∈Λ, then G^(3)=G. If Λ is the disjoint union of two equivariantly isomorphic copies and the anchors lie in the first copy, it suffices to verify the singleton condition on that copy. Consequently, for G=PGL_3(5)=PSL_3(5) and H=Q⋊<[[0,1],[1,0]],[[0,1],[4,1]]> in the audited degree-1240 action, the diagonal action on G/H disjoint-union G/H is 3-closed.
- `claim_root_mixed_parabolic_quotient_incidence_rev1290` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). Let H and K be proper subgroups contained in point or line parabolics. If the constituent actions on G/H and G/K are individually 3-closed, then the diagonal action on G/H disjoint union G/K is 3-closed. This covers all point-point, point-line, line-point, line-line, dual, descendant, and repeated-constituent cases without a base-two hypothesis.
- `claim_root_mutual_orbital_character_scalar_test_rev150` `informally_verified` `partial`: Let G be a finite group and H,K≤G. If χ_H=Ind_H^G(1_H), then K and G have the same orbits on (G/H)^2 if and only if ⟨Res_K χ_H,Res_K χ_H⟩_K=⟨χ_H,χ_H⟩_G. Hence H,K form a mutual-orbital pair exactly when this equality and its version with H and K interchanged both hold.
- `claim_root_mutual_orbital_double_coset_defect_criterion_rev588` `informally_verified` `partial`: Let G be a finite group and let H,K<=G satisfy G=HK. Put L=H intersection K and r(A;B)=|A backslash G/B|. Then H=L(H intersection xHx^(-1)) for every x in G if and only if r(L;H)=r(H;H), and K=L(K intersection xKx^(-1)) for every x in G if and only if r(L;K)=r(K;K). Equivalently, the two mutual pair-orbital equalities hold exactly when both associated nonnegative double-coset defects vanish.
- `claim_root_nonparabolic_maximal_host_base2_rev1278` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). If H<G is contained in a maximal subgroup M which is neither a point nor a line parabolic, then b(G,G/H)≤2. More precisely, every such M is contained in the determinant-one monomial C2 host, the extension-field C3 host ΓL_1(p^3)∩G, an orthogonal C8 host, or is an almost-simple Aschbacher-S host.
- `claim_root_normal_elementary_abelian_c2c3_dichotomy_rev962` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3, V=F_p^3, and G=SL(V)=PSL_3(p). If M<G acts irreducibly on V and has a nontrivial normal elementary-abelian subgroup, then either M preserves an unordered decomposition of V into three one-dimensional F_p-subspaces or M preserves a one-dimensional F_{p^3}-vector-space structure. Equivalently, M lies in a C2 decomposition stabilizer or a C3 extension-field normalizer. If M is maximal in G, it equals the corresponding determinant-one normalizer.
- `claim_root_p11_p17_dihedral_levi_coset_actions_3closed_rev885` `informally_verified` `partial`: For p in {11,17}, let G=SL_3(p)=PSL_3(p), let L=<[[0,1],[1,0]],[[0,1],[-1,1]]> in GL_2(p), and let H_p consist of the determinant-one point-parabolic matrices whose Levi block lies in L. Then the faithful transitive action of G on G/H_p is 3-closed.
- `claim_root_p5_central_scalar_block_criterion_rev736` `informally_verified` `partial`: Let X=GL_2(5), Z_0={±I}, L=<A,B> as in the exact p=5 tensor action, W=X/Z_0 acting on D=X/L, and z=(2I)Z_0. Every non-singleton W-block containing L contains zL. Consequently, if U<=Sym(D) is normalized by W and preserves a labeled vertex invariant Sigma with Sigma(L) distinct from Sigma(zL), then U=1.
- `claim_root_p5_crossblock_tensor_projection_reduction_rev710` `informally_verified` `partial`: In the exact p=5 action, assume the established 31-block system is preserved by C=G^(3), let K be its block kernel, D=P/H, and W=P^D. For representative ordered off-D block pairs of equal, D-collinear, and D-noncollinear type, let I_t be the first-coordinate image of the corresponding G-orbit-color tensor autotopism group and put J=⋂_t⋂_{w∈W}wI_tw^(−1). Then pr_D(K)≤J. Consequently J≤N_P(H)/H implies the required fiberwise normalizer projection.
- `claim_root_p5_dihedral_levi_coset_action_3closed_rev123` `informally_verified` `partial`: Let G=PGL_3(5)=PSL_3(5), let P=Q⋊GL_2(5) be a point parabolic, let L=<[[0,1],[1,0]],[[0,1],[4,1]]>≤GL_2(5), and put H=Q⋊L. Then the faithful action of G on G/H has 3-closure equal to G.
- `claim_root_p5_exact_right_normalizer_interface_rev714` `informally_verified` `partial`: For A=((0,1),(1,0)), B=((0,1),(4,1)), C=I+B in GL_2(5), L=<A,B>, P=Q⋊GL_2(5), H=Q⋊L and D=P/H, one has N_P(H)/H=<hat(C)H>≅C_4. In the left coset action W=P^D, the corresponding four right translations form the full centralizer C_Sym(D)(W).
- `claim_root_p5_local_determinant_kernel_collapse_rev1016` `informally_verified` `partial`: Let G=PGL_3(5)=PSL_3(5), P=Q⋊GL_2(5), L=<[[0,1],[1,0]],[[0,1],[4,1]]>, H=Q⋊L, Ω=G/H, C=G^(3), and K the kernel induced by C on the 31 blocks G/P. Then K=1. Consequently G is 3-closed on Ω.
- `claim_root_p5_pair_and_phase_reduction_rev131` `informally_verified` `partial`: In the action of G=PGL_3(5) on G/H, where H=Q semidirect <[[0,1],[1,0]],[[0,1],[4,1]]>, every two-point stabilizer has order at least four: a same-projective-block pair stabilizer contains Q of order 25, while a distinct-block pair stabilizer contains two distinct involutory homologies centered at the two block points. Hence no three-involution separator triangle exists. Moreover, the action induced by a point parabolic P on one fiber P/H has kernel Q semidirect {plus or minus I}, has a two-point base, and is 3-closed. Consequently any normalizer-valued block phase belonging to the global 3-closure takes values only in the scalar subgroup F_5^times/{plus or minus I} of order two.
- `claim_root_p5_remote_anchor_inequality_rev522` `informally_verified` `partial`: Let G=PGL_3(5)=SL_3(5), P=Q⋊GL_2(5), H=Q⋊<[[0,1],[1,0]],[[0,1],[4,1]]>, and Ω=G/H. For every fibre D of Ω→G/P there exist distinct x,y∈Ω\D such that |G_{x,y}|=4; consequently |G_{x,y}|<20.
- `claim_root_p5_semiregular_kernel_collapse_rev994` `informally_verified` `partial`: Let G=PGL_3(5)=PSL_3(5), P=Q semidirect GL_2(5), L=<((0,1),(1,0)),((0,1),(4,1))>, H=Q semidirect L, Omega=G/H, C=G^(3), and K the kernel of C on the 31 blocks G/P. If K is semiregular, then K centralizes G and lies in N_G(H)/H, where |N_G(H)/H|=4. Hence, if the three nonidentity right-normalizer permutations are excluded from C, then C=G.
- `claim_root_p5_tensor_pairhist_core_trivial_rev722` `informally_verified` `partial`: In the exact p=5 setup of the three cross-block tensors T_eq, T_col, and T_ncol on D=P/H, the W-normal tensor core J=intersection_{t,w} w I_t w^{-1} is trivial. Consequently [J,W]=1 and, for the block kernel K of the 3-closure, pr_D(K)=1.
- `claim_root_p5_three_fibre_binary_separator_rev1000` `informally_verified` `partial`: Let G=PGL_3(5), H=Q semidirect <A,B>, Omega=G/H, pi:Omega->PG(2,5), and let B_0 be the pointwise block kernel. Put b_1=[0:1:0], b_2=[0:0:1], b_3=[1:1:1]. Their pointwise stabilizer in H is trivial. If lifts y_i in pi^{-1}(b_i) satisfy (i) pairwise H-orbital reconstruction of the anchor triple and (ii) pi^{-1}(pi(w)) intersect H_{y_1}w intersect H_{y_2}w intersect H_{y_3}w={w} for every w in Omega, then H^(2) intersect B_0=1.
- `claim_root_pair_thick_affine_root_group_rev622` `informally_verified` `partial`: Let p≥3 be prime and Y≤PGL₂(p) act naturally on P¹(F_p). If the pointwise stabilizer Y_{a,b} is nontrivial for every pair of distinct projective points a,b, then PSL₂(p)≤Y. Equivalently, if PSL₂(p) is not contained in Y, then Y has a pointwise free pair.
- `claim_root_pair_thick_p_divisibility_rev686` `informally_verified` `partial`: Let p be a prime and Y<=PGL_2(p). If the pointwise stabilizer Y_{a,b} is nontrivial for every pair of distinct points a,b in P^1(p), then p divides |Y|.
- `claim_root_pair_thick_pgl2_affine_rootgroup_rev551` `informally_verified` `partial`: Let p≥5 be prime with p≡2 (mod 3), and let Y≤PGL₂(p) act on P¹(F_p). If Y has no global fixed point and every pointwise two-point stabilizer Y_{a,b}, for a≠b, is nontrivial, then PSL₂(p)≤Y. Equivalently, if PSL₂(p) is not contained in Y, then Y has a pointwise base of size two.
- `claim_root_pair_thick_pgl2_dichotomy_rev516` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, let X=P^1(F_p), and let Y<=PGL_2(p). For distinct a,b in X, write Y_{a,b} for the pointwise stabilizer of a and b. If Y has no global fixed point on X and Y_{a,b} is nontrivial for every distinct a,b, then PSL_2(p)<=Y.
- `claim_root_pair_thick_pgl2_dichotomy_rev591` `informally_verified` `partial`: Let p>2 be prime and Y≤PGL_2(p). If Y has no global fixed point on P^1(p) and Y_a∩Y_b is nontrivial for every pair of distinct projective points a,b, then PSL_2(p)≤Y. In particular this holds for every prime p≥5 with p≡2 mod 3.
- `claim_root_pair_thick_pgl2_kernel_rev606` `informally_verified` `partial`: Let p>2 be prime and let Y≤PGL₂(p). If the pointwise stabilizer Y_{a,b}=Y_a∩Y_b is nontrivial for every two distinct points a,b∈P¹(p), then PSL₂(p)≤Y. Equivalently, every subgroup of PGL₂(p) omitting PSL₂(p) has a pair of distinct projective points with trivial pointwise stabilizer.
- `claim_root_pair_thick_pgl2_p5_boundary_rev487` `informally_verified` `partial`: Let Y≤PGL_2(5) act naturally on P^1(F_5). If Y has no global fixed point and the pointwise stabilizer Y_{a,b} is nontrivial for every two distinct projective points a,b, then PSL_2(5)≤Y. In fact the only such subgroups are PSL_2(5) and PGL_2(5).
- `claim_root_pair_thick_pgl2_subgroup_dichotomy_rev501` `informally_verified` `partial`: For every prime p≥5 with p≡2 (mod 3) and every subgroup Y≤PGL₂(p), if Y has no global fixed point on P¹(F_p) and the pointwise stabilizer Y_{a,b} is nontrivial for every two distinct projective points a,b, then PSL₂(p)≤Y.
- `claim_root_pair_thick_pgl2_subgroup_dichotomy_rev561` `informally_verified` `partial`: Let p≥5 be prime with p≡2 (mod 3), and let Y≤PGL₂(p) act on P¹(F_p). If Y has no global fixed point and the pointwise stabilizer Y_{a,b} is nontrivial for every pair of distinct projective points a,b, then PSL₂(p)≤Y. Equivalently, if PSL₂(p) is not contained in Y, then Y has a pointwise base of size two. In fact, the conclusion remains true without the congruence and no-global-fixed-point hypotheses.
- `claim_root_pair_thick_pgl2_subgroup_dichotomy_rev670` `informally_verified` `partial`: Let p≥5 be prime with p≡2 (mod 3), and let Y≤PGL_2(p) act on P^1(F_p). For distinct a,b, write Y_{a,b}=Y_a∩Y_b for the pointwise pair stabilizer. If Y has no global fixed point and Y_{a,b}≠1 for every pair of distinct points a,b, then PSL_2(p)≤Y.
- `claim_root_parabolic_determinant_multiplier_annihilation_rev1171` `informally_verified` `partial`: Let p≥5 be prime with p≡2 mod 3, G=SL_3(p)=PSL_3(p)=PGL_3(p), P a point or line parabolic, H≤P, Ω=H\G, C=G^(3), and K the kernel of C on the canonical blocks P\G. For a point block x let λ_x:P_x→F_p^× be the eigenvalue on x, using the dual one-space for a line block, and put P_x^0=ker λ_x. Then every k∈K satisfies αk∈α^{P_x^0} for every α lying over x. Equivalently, the canonical displacement class in F_p^×/λ_x(G_α) is trivial on every fiber.
- `claim_root_parabolic_local_determinant_criterion_rev1021` `informally_verified` `partial`: Let p be prime, G=PGL_3(p), P a projective-point stabilizer with unipotent radical Q, M=P/Q≅GL_2(p), L≤M, H the inverse image of L, and N=core_M(L). If N≤Z(M), the faithful action M/N on M/L has base at most two, and det(L)∩r^{-1}(F_p^×)^2 is empty for every scalar rI outside N, then G on G/H is 3-closed. For p=5 and L generated by [[0,1],[1,0]] and [[0,1],[4,1]], all hypotheses hold, so the exact PSL_3(5) action on G/(Q⋊L) is 3-closed.
- `claim_root_piecewise_inner_twocoset_criterion_rev140` `informally_verified` `partial`: Let G be a finite nonabelian simple group and H,K<G proper. On A=G/H disjoint-union B=G/K, let pi_s act as a nonidentity s in G on A and trivially on B. Then pi_s lies in the 3-closure of diagonal G for some nonidentity s if and only if K and G have the same orbits on A^2 and H and G have the same orbits on B^2. Equivalently, G=HK and, for L=H intersection K, H=L(H intersection xHx^(-1)) and K=L(K intersection xKx^(-1)) for every x in G. If these conditions hold, every pi_s lies in the 3-closure and nonidentity pi_s lies outside diagonal G. Any such pair promotes to a pair of proper maximal overgroups with the same property.
- `claim_root_primefield_geometric_pruning_rev827` `informally_verified` `partial`: Let p≥5 be prime with p≡2 mod 3, V=F_p^3, and G=SL(V)=PSL_3(p). If M<G is a nonparabolic maximal subgroup belonging to an Aschbacher geometric class, then M can arise only through C2, C3, or orthogonal C8; C4, C5, C6, C7, symplectic C8, and genuinely unitary C8 are absent. Moreover, if H≤M and b(G,G/M)≤2, then b(G,G/H)≤2.
- `claim_root_primefield_geometric_pruning_rev841` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, put G=SL_3(p)=PSL_3(p), and let M<G be a nonparabolic maximal subgroup belonging to an Aschbacher geometric family. Then M has type C2, C3, or orthogonal C8. Moreover, if the action of G on G/M has a base of size at most two, then the action of G on G/H has a base of size at most two for every H<=M.
- `claim_root_projective_levi_free_pair_three_conjugate_base_rev483` `informally_verified` `partial`: Let p be prime, V=F_p^3, G=PGL(V), U a projective point, J≤G_U, and rho_U:G_U→PGL(V/U) the induced quotient projectivity. If Y=rho_U(J) has a two-point base on P(V/U), then there exist three G-conjugates of J with trivial intersection; hence G/J is faithful and has base size at most three. Moreover, the two-point-base hypothesis holds whenever |Y|-1<p(p+1)/2.
- `claim_root_psl33_E3_maximal_parabolic_subgroups_rev419` `informally_verified` `partial`: Let G=SL_3(3), let P be a projective point stabilizer, and let E(P)={H<P: H intersect H^g is nontrivial for every g in G}. Every maximal subgroup of P belongs to E(P). Up to P-conjugacy the maximal subgroups are precisely the geometric stabilizers of orders 48,108,144,216 (anti-flag, incident flag, partition of the four-line pencil, and nonzero vector), occurring inside P with multiplicities 9,4,3,1 respectively.
- `claim_root_psl33_exceptional_mixed_M3_incidence_sync_rev504` `informally_verified` `partial`: Let G=PSL_3(3), let T be the six G-conjugacy types in E(P) certified by art_researcher_root_psl33_E3_exact_ternary_proof_rev490, and let T* be their dual line-parabolic types. For every H,K in T union T*, with repetition allowed, the diagonal action on G/H disjoint union G/K is 3-closed.
- `claim_root_psl33_exceptional_mixed_pair_M3_rev41` `informally_verified` `partial`: Let G=PSL_3(3). Let H and K belong to the six exceptional point-parabolic classes in E(P), or to their dual line-parabolic classes in E(P*). Then the diagonal action of G on G/H disjoint-union G/K is 3-closed, including repeated constituents and every point/line orientation.
- `claim_root_psl33_exceptional_parabolic_E3_rev496` `informally_verified` `partial`: Let G=PSL_3(3), let P be a point stabilizer, and define E(P)={H<P proper : H intersects H^g nontrivially for every g in G}. Then E(P) consists of 24 subgroups forming six G-conjugacy classes, represented by subgroups of orders 48, 54, 72, 108, 144, and 216. For every H in E(P), the faithful transitive action of G on G/H is 3-closed. The corresponding assertion holds for the six dual line-parabolic classes.
- `claim_root_psl33_exceptional_transitive_E3_rev403` `informally_verified` `partial`: Let G=PSL_3(3), let P be a point stabilizer, and let E(P)={H<P proper : H cap H^g is nontrivial for every g in G}. For every H in E(P), the transitive coset action G on G/H is 3-closed. The same conclusion holds for the dual family E(P*) inside a line stabilizer.
- `claim_root_psl33_exhaustive_maximal_subgroups_theorem_C_rev55` `informally_verified` `partial`: Let G=PSL_3(3)=SL_3(3). Let P be a point stabilizer, P* a line stabilizer, J a Singer normalizer 13:3, and M a conic stabilizer S4. Every maximal subgroup of G is conjugate to exactly one of P, P*, J, or M. Consequently every proper subgroup of G is contained in a conjugate of one of these four subgroups.
- `claim_root_psl33_four_explicit_maximal_classes_cas_rev7` `informally_verified` `partial`: Let G=SL_3(3)=PSL_3(3). Let P_1 be the stabilizer of <e_1>, P_2 the stabilizer of ker(e_1^*), J the explicit Singer normalizer generated by multiplication by a root of X^3-X-1 and Frobenius, and M the determinant-one monomial conic stabilizer. Then P_1,P_2,J,M are self-normalizing maximal subgroups of orders 432,432,39,24. Their G-conjugacy classes have sizes 13,13,144,234; P_1 and P_2 are not conjugate; and the union of all conjugates of these four subgroups is G. This claim does not assert that these are all maximal-subgroup classes.
- `claim_root_psl33_maximal_list_C_rev25` `informally_verified` `partial`: Let G=SL_3(3)=PSL_3(3). Let P_1 and P_2 be respectively a projective-point stabilizer and a projective-line stabilizer, let J be the normalizer 13:3 of a Singer subgroup, and let M be the determinant-one monomial subgroup, equivalently the stabilizer of a nonsingular four-point conic. Every maximal subgroup of G is G-conjugate to exactly one of P_1, P_2, J, or M; P_1 and P_2 are not conjugate.
- `claim_root_psl33_six_geometric_actions_3closed_rev411` `informally_verified` `partial`: Let G=PSL_3(3). The transitive coset action G/H is 3-closed whenever H is one of the six point-parabolic geometric stabilizers of orders 48,54,72,108,144,216 described in art_researcher_root_psl33_E3_geometric_certificate_repair_rev411, or a contragredient-dual stabilizer.
- `claim_root_psl33_totally_3closed_A3_rev37` `informally_verified` `partial`: Let G=PSL_3(3). For every pair of proper subgroups H,K<G, the diagonal action of G on G/H disjoint-union G/K is 3-closed. Consequently PSL_3(3) is totally 3-closed.
- `claim_root_psl3_scalar_fiber_3closed_obstruction_rev313` `informally_verified` `partial`: Let p be prime with gcd(3,p-1)=1, let C be any subgroup of F_p^*, and let S=PSL_3(p)=SL_3(p). The natural faithful action of S on (F_p^3 minus {0})/C is 3-closed. Moreover, every determinant-character twist H_(e,C) of the point parabolic restricts to this same S-action, so no such scalar-fiber construction supplies a proper 3-closure witness.
- `claim_root_residual_C2_C3_direct_base2_rev856` `informally_verified` `partial`: Let p≥5 be prime with p≡2 mod 3 and G=SL_3(p)=PSL_3(p). The determinant-one monomial C2 subgroup and the degree-three Singer-normalizer C3 subgroup each have a two-point base in their coset action. Every subgroup contained in a conjugate of either also has base size at most two and hence has a 3-closed coset action.
- `claim_root_residual_S_A6_PSL27_base2_rev1035` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, let G=SL_3(p)=PSL_3(p), and let M<G be isomorphic to A_6 or PSL_2(7). Then there exists g in G such that M intersect M^g is trivial. Consequently every H<=M has base size at most two on G/H, and the transitive action of G on G/H is 3-closed.
- `claim_root_residual_flag_descendants_3closed_rev87` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, put G=PSL_3(p), and let B be the stabilizer of an incident projective point-line flag in PG(2,p). For every subgroup J<=B, the natural action of G on G/J is faithful and 3-closed.
- `claim_root_residual_host_exhaustion_direct_sbase2_rev1090` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). Every proper subgroup H<G lies in a conjugate of a point or line parabolic, N_2=(GL_1(p) wr S_3)∩G, N_3=ΓL_1(p^3)∩G, SO_3(p), or PSL_2(7), with the last case possible only for p modulo 7 in {1,2,4}. Every H contained in N_2, N_3, or PSL_2(7) has base size at most two. Consequently every high-base H lies under a parabolic or SO_3(p).
- `claim_root_residual_nonparabolic_base2_rev872` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3 and G=PSL_3(p). If H<G is not contained in a point or line parabolic subgroup, then b(G,G/H)<=2. Consequently the transitive coset action G on G/H is 3-closed.
- `claim_root_residual_nonparabolic_maximal_exhaustion_rev984` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, let V=F_p^3, and let G=PSL_3(p)=SL_3(p). If M<G is maximal and stabilizes neither a point nor a plane of V, then M is exactly one of: (i) the determinant-one monomial normalizer N_2; (ii) the determinant-one extension-field normalizer N_3=GammaL_1(p^3) intersect G; (iii) the conic stabilizer C_8=rho(PGL_2(p)); or (iv) a self-normalizing subgroup isomorphic to PSL_2(7), the last possibility occurring only when p^3 is congruent to 1 modulo 7.
- `claim_root_residual_nonsplit_torus_normalizer_3closed_rev100` `informally_verified` `partial`: For every prime p>=5 with p congruent to 2 modulo 3, let G=PSL_3(p), let Q be the unipotent radical of a point parabolic P, and embed GammaL_1(p^2) as the normalizer of a nonsplit torus in the Levi factor GL_2(p) of P. If H_p=Q semidirect GammaL_1(p^2), then the faithful coset action of G on G/H_p is 3-closed.
- `claim_root_residual_prime_conic_base2_rev768` `informally_verified` `partial`: Let p≥5 be prime with p≡2 (mod 3), let G=PSL_3(p), and let M be a conic stabilizer, equivalently M=SO(B) for a nondegenerate symmetric bilinear form B on F_p^3. Then there exists g∈G with M∩M^g=1. Consequently b(G,G/M)=2 and b(G,G/H)≤2 for every H≤M.
- `claim_root_residual_primitive_core_PC_bloom_rev794` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, put G=SL_3(p)=PSL_3(p), and let M<G be a proper primitive maximal subgroup whose generalized Fitting subgroup has a unique nonabelian simple component E. Then either M is the conic stabilizer rho(PGL_2(p))=SO_3(p) with E=rho(PSL_2(p)), or p mod 7 belongs to {1,2,4} and M=E is a self-normalizing degree-three image of PSL_2(7). The image in the latter case is unique up to G-conjugacy. No other simple component occurs.
- `claim_root_residual_reduction_to_parabolic_capture_rev63` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3 and G=PSL_3(p). Assume D_p: every proper H<G of base size greater than two admits a G-equivariant quotient to projective points or projective lines and is either a certified scalar-fiber action, up to duality, or contains the pointwise stabilizer of a suitable ordered triple in that quotient. Then every faithful transitive G-action and every diagonal action on two faithful transitive G-sets is 3-closed. Consequently G is totally 3-closed.
- `claim_root_residual_srow_local_elimination_rev938` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, V=F_p^3, and G=SL(V). Let M<=G be almost simple with socle T, and assume T acts absolutely irreducibly on V. Then T is not A6 or A7; if T is A5 or PSL2(p), M preserves a nondegenerate symmetric bilinear form and is geometric C8; and if T is PSL2(7), then p modulo 7 is in {1,2,4}, N_G(T)=T, and hence M=T. Consequently, conditional only on the exhaustive simple-socle list T in {PSL2(p),A5,PSL2(7),A6,A7}, every nongeometric M is exactly a self-normalizing PSL2(7).
- `claim_root_uniform_parabolic_block_kernel_triviality_rev1262` `informally_verified` `partial`: Let p>=5 be prime with p congruent to 2 modulo 3, let G=SL_3(p)=PSL_3(p), let P be a point or line parabolic, let H<=P, and let C=G^(3) in the coset action on Omega={Hg:g in G}. If K is the kernel of the induced action of C on the projective block system P\G, then K=1. In particular, every k in K satisfying alpha k in alpha^{P_x^0} on every fiber is the identity, so DNFK(p) holds.
- `claim_root_uniform_parabolic_small_levi_base3_rev573` `informally_verified` `partial`: Let p≥5 be prime with p≡2 modulo 3, let G=PSL_3(p), and let H<G be contained in a point parabolic. Let Y≤PGL_2(p) be the projective image induced by H on the two-dimensional quotient. If PSL_2(p) is not contained in Y, then the coset action G on G/H has a pointwise base of size at most three. The same conclusion holds for a line parabolic by contragredient duality.
- `claim_root_residual_orthogonal_descendants_base2_rev1106` `informally_verified` `orthogonal`: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). If M≤G is a conjugate of SO_3(p), then there exists g∈G with M∩M^g=1. Consequently, for every H contained in a conjugate of M, the coset action G on G/H has base size at most two.
- `claim_root_residual_parabolic_quotient_normalization_rev1106` `informally_verified` `conditional`: Let p≥5 be prime with p≡2 modulo 3, G=SL_3(p)=PSL_3(p), P_ε a point or line parabolic, and H≤P_ε. The 3-closure of G on G/H preserves the fibers of the canonical map G/H→G/P_ε and induces an element of G on the quotient. For a diagonal action on two such coset spaces, the two induced quotient elements agree, using equality for equal quotient types and incidence for point-line quotient types.

## Route Scoreboard

- `route_root_classification_after_quotient_incidence_rev1290` `verified_part` score=2.9 root_distance=0 verified=1/1
- `route_import_two_orbit_reduction` `verified_part` score=2.8 root_distance=1 verified=1/1
- `route_claim_root_core_overlap_frame_gluing_rev1234` `verified_part` score=2.77 root_distance=1 verified=1/1
- `route_claim_root_levi_split_torus_separator_rev1210` `verified_part` score=2.74 root_distance=1 verified=1/1
- `route_import_psl27_certificate` `verified_part` score=2.72 root_distance=1 verified=1/1
- `route_import_psln_projective_nonclosure` `verified_part` score=2.67 root_distance=1 verified=1/1
- `route_claim_root_mixed_anchor_code_pair_criterion_rev179` `verified_part` score=2.58 root_distance=1 verified=1/1
- `route_claim_root_uniform_parabolic_small_levi_base3_rev573` `verified_part` score=2.54 root_distance=1 verified=1/1
- `route_claim_root_residual_nonsplit_torus_normalizer_3closed_rev100` `verified_part` score=2.52 root_distance=1 verified=1/1
- `route_claim_root_general_multiseparator_criterion_rev148` `verified_part` score=2.47 root_distance=1 verified=1/1
- `route_claim_root_base2_constituent_synchronization_rev369` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_claim_root_bloom_nonorthogonal_simple_subgroups_rev1051` `verified_part` score=2.32 root_distance=1 verified=1/1

## Branches

- Parallel branch mode: `multi_branch_research` with up to 3 simultaneous branch workers

```text
Branch: route_root_classification_after_quotient_incidence_rev1290
Goal: # Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_3(q)\) ## Definitions For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), its **3-closure** \(G^{(3)}\) is the largest subgroup of \(\operatorname{Sy...
Status: keep_exploiting
Verified facts: root: # Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_3(q)\) ## Definitions For a finite permutation group \(G\leq\operatorname{Sym}(\Omega...; claim_import_psln_projective_nonclosure: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or...; claim_import_psl27_totally_3closed: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.; claim_root_psl33_totally_3closed_A3_rev37: Let G=PSL_3(3). For every pair of proper subgroups H,K<G, the diagonal action of G on G/H disjoint-union G/K is 3-closed. Consequently PSL_3(3) is totally 3-closed.
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: art_villain_root_lts_interface_gap_rev1325 (hypothesis_gap): Target attacked: inference_root_classification_after_quotient_incidence_rev1290, specifically the DNFK step in art_researcher_root_dependency_audited_route_conversion_rev1317 an...; art_villain_root_dnfk_right_action_normalization_gap_rev1338 (route_obstruction): # Full-hypothesis adversarial check of the DNFK frame descent Targeted interface: inference_root_classification_after_quotient_incidence_rev1290, specifically Section 5 of art_r...
Useful sources: card_bloom1967_thm1_1_residual_simple_subgroups_rev1086: Bloom's Theorem 1.1 classifies every nontrivial subgroup J of PSL_3(r^a), r odd, having no nontrivial normal elementary-abelian subgroup. Subject to its stated field conditions,...; card_bloom1967_psl3_odd_simple_subgroups_theorem1_1_rev1047: Bloom's Theorem 1.1, in normalized notation, states: let q=p^a be odd and let H be a nontrivial subgroup of PSL_3(q) with no nontrivial normal elementary-abelian subgroup. Then...; card_bloom_1967_theorem_5_14_lemmas_6_3_6_5_rev833: Bloom Theorem 5.14 (p. 170): let q=p^a be odd and let \widetilde H be the full inverse image under \Lambda:SL_3(q)\to PSL_3(q) of a nonabelian simple subgroup H of even order. T...
Next recommended lemma: extend the verified chain toward the branch goal: # Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_3(q)\) ## Definitions For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), its **3-closure** \(G^{(3)}\) is the largest subgroup of \(\operatorname{Sy...
Similar lemmas worth trying: prove a special case of the branch goal first: # Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_3(q)\) ## Definitions For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), its **3-closure** \(G^{(3)}\) is the largest subgroup of \(\operatorname{Sy...; prove a bridge lemma connecting the verified branch facts to: # Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_3(q)\) ## Definitions For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), its **3-closure** \(G^{(3)}\) is the largest subgroup of \(\operatorname{Sy...
Failed methods (do not retry unchanged): art_villain_root_psl33_fifth_maximal_class_attack_rev34: not_refuted [fingerprint published_classification_kills_fifth_maximal_class_attack]; art_villain_root_residual_nonsplit_levi_stress_rev96: not_refuted [fingerprint smallest_unsupported_full_hypothesis_family]; art_villain_root_p5_kernel_ladder_not_refuted_rev364: not_refuted [fingerprint not_refuted_after_full_hypothesis_stress_test]; art_auto_villain_root_construction_failure_bd2bd3da302a: not_refuted [fingerprint singleton_strip_anchor_collision]
Last useful delta: verified_claim: claim root verified (at 2026-07-21T23:10:56.563175+00:00)
Passes since useful delta: 0
Rotation: rotate (stuck_and_repeating) — the same failure fingerprint 'counterexample_construction_failed' has been recorded 2+ times on this branch
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_import_two_orbit_reduction
Goal: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
Status: keep_exploiting
Verified facts: claim_import_two_orbit_reduction: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgro...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_bloom1967_thm1_1_residual_simple_subgroups_rev1086: Bloom's Theorem 1.1 classifies every nontrivial subgroup J of PSL_3(r^a), r odd, having no nontrivial normal elementary-abelian subgroup. Subject to its stated field conditions,...; retrieval_card_bloom1967_exact_simple_subgroups_rev1074: Let q=p^a be odd, let Lambda:SL_3(q)->PSL_3(q), let Z=ker(Lambda), and let E=Lambda^{-1}(T) for a nonabelian simple subgroup T of even order. Bloom Theorem 5.14 states that one...; card_bgs2014_l3_s_rows_for_p_rev1142: For an almost simple classical group G with socle G0 and natural-module dimension n<6, the nongeometric almost-simple maximal subgroups H in the source's collection S are exhaus...
Next recommended lemma: extend the verified chain toward the branch goal: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
Similar lemmas worth trying: prove a special case of the branch goal first: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.; prove a bridge lemma connecting the verified branch facts to: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
Failed methods (do not retry unchanged): none recorded
Last useful delta: usable_source: retrieval card retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345 matches the branch goal (at 2026-07-21T22:55:11.493197+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (usable_source: retrieval card retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345 matches the branch goal)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_claim_root_core_overlap_frame_gluing_rev1234
Goal: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P a point or line parabolic, H<=P, and X_x the fibers of H backslash G -> P backslash G. Put N_x=core_(P_x)(H_x). If H does not contain P^0, then N_x intersect N_y=1 for all distinct x,y; if H con...
Status: keep_exploiting
Verified facts: claim_root_core_overlap_frame_gluing_rev1234: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P a point or line parabolic, H<=P, and X_x the fibers of H backslash G -> P backslash G. Put N_x=core_(P_x)(H_x). If...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_bloom1967_theorem1_1_simple_psl3_odd_rev1064: Let q=p^a for odd prime p, and let H <= PSL_3(q) be nontrivial with no nontrivial normal elementary-abelian subgroup. Then H is one of: PSL_3(p^beta) (beta divides a); PU_3(p^be...; card_bgs2014_l3_s_rows_for_p_rev1142: For an almost simple classical group G with socle G0 and natural-module dimension n<6, the nongeometric almost-simple maximal subgroups H in the source's collection S are exhaus...; card_bloom1967_exact_simple_subgroup_packet_rev1124: Normalized complete mathematical content of the cited results: Let q=p^a with p odd. Bloom Theorem 1.1 classifies every nontrivial subgroup J of PSL_3(q) having no nontrivial no...
Next recommended lemma: extend the verified chain toward the branch goal: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P a point or line parabolic, H<=P, and X_x the fibers of H backslash G -> P backslash G. Put N_x=core_(P_x)(H_x). If H does not contain P^0, then N_x intersect N_y=1 for all distinct x,y; if H con...
Similar lemmas worth trying: prove a special case of the branch goal first: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P a point or line parabolic, H<=P, and X_x the fibers of H backslash G -> P backslash G. Put N_x=core_(P_x)(H_x). If H does not contain P^0, then N_x intersect N_y=1 for all distinct x,y; if H con...; prove a bridge lemma connecting the verified branch facts to: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P a point or line parabolic, H<=P, and X_x the fibers of H backslash G -> P backslash G. Put N_x=core_(P_x)(H_x). If H does not contain P^0, then N_x intersect N_y=1 for all distinct x,y; if H con...
Failed methods (do not retry unchanged): none recorded
Last useful delta: usable_source: retrieval card retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345 matches the branch goal (at 2026-07-21T22:55:11.493197+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (usable_source: retrieval card retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345 matches the branch goal)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_claim_root_levi_split_torus_separator_rev1210
Goal: For every prime p≥5, every subgroup M≤GL_2(p) not containing SL_2(p), and every split maximal torus D≤GL_2(p), there exists g∈GL_2(p) such that D∩M^g=D∩core_{GL_2(p)}(M). Equivalently, the projective image of M has an ordered pair of distinct points of P^1(...
Status: keep_exploiting
Verified facts: claim_root_levi_split_torus_separator_rev1210: For every prime p≥5, every subgroup M≤GL_2(p) not containing SL_2(p), and every split maximal torus D≤GL_2(p), there exists g∈GL_2(p) such that D∩M^g=D∩core_{GL_2(p)}(M). Equiva...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_bloom_psl3_odd_primitive_core_exact_rev798: Bloom's Theorem 1.1 classifies every nontrivial subgroup H of PSL_3(q), q=p^a odd, having no nontrivial normal elementary-abelian subgroup. The possibilities are subfield PSL_3(...; retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345: For odd q=p^n, Cameron–Omidi–Tayfeh-Rezaie, Theorem 2, gives the complete subgroup types in PGL_2(q): cyclic and dihedral groups; A_4, S_4, A_5; subfield PSL_2(p^m) and PGL_2(p^...; card_bloom1967_exact_simple_subgroups_packet_rev1057: Let q=p^a with p odd, let Λ:SL_3(q)→PSL_3(q) be the natural quotient, let Z=ker(Λ), and let E be the inverse image under Λ of a nonabelian simple subgroup of even order. Bloom's...
Next recommended lemma: extend the verified chain toward the branch goal: For every prime p≥5, every subgroup M≤GL_2(p) not containing SL_2(p), and every split maximal torus D≤GL_2(p), there exists g∈GL_2(p) such that D∩M^g=D∩core_{GL_2(p)}(M). Equivalently, the projective image of M has an ordered pair of distinct points of P^1(...
Similar lemmas worth trying: prove a special case of the branch goal first: For every prime p≥5, every subgroup M≤GL_2(p) not containing SL_2(p), and every split maximal torus D≤GL_2(p), there exists g∈GL_2(p) such that D∩M^g=D∩core_{GL_2(p)}(M). Equivalently, the projective image of M has an ordered pair of distinct points of P^1(...; prove a bridge lemma connecting the verified branch facts to: For every prime p≥5, every subgroup M≤GL_2(p) not containing SL_2(p), and every split maximal torus D≤GL_2(p), there exists g∈GL_2(p) such that D∩M^g=D∩core_{GL_2(p)}(M). Equivalently, the projective image of M has an ordered pair of distinct points of P^1(...
Failed methods (do not retry unchanged): none recorded
Last useful delta: usable_source: retrieval card retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345 matches the branch goal (at 2026-07-21T22:55:11.493197+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (usable_source: retrieval card retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345 matches the branch goal)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_import_psl27_certificate
Goal: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
Status: keep_exploiting
Verified facts: claim_import_psl27_totally_3closed: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_bloom1967_thm1_1_residual_simple_subgroups_rev1086: Bloom's Theorem 1.1 classifies every nontrivial subgroup J of PSL_3(r^a), r odd, having no nontrivial normal elementary-abelian subgroup. Subject to its stated field conditions,...; card_bloom_psl3_odd_primitive_core_exact_rev798: Bloom's Theorem 1.1 classifies every nontrivial subgroup H of PSL_3(q), q=p^a odd, having no nontrivial normal elementary-abelian subgroup. The possibilities are subfield PSL_3(...; card_root_bloom1967_primitive_simple_psl3_rev1208: Bloom, Theorem 1.1, classifies every nontrivial subgroup X of PSL_3(q), q=p^a odd, having no nontrivial normal elementary-abelian subgroup. The possibilities are: projective lin...
Next recommended lemma: extend the verified chain toward the branch goal: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
Similar lemmas worth trying: prove a special case of the branch goal first: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.; prove a bridge lemma connecting the verified branch facts to: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
Failed methods (do not retry unchanged): none recorded
Last useful delta: usable_source: retrieval card retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345 matches the branch goal (at 2026-07-21T22:55:11.493197+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (usable_source: retrieval card retrieval_card_lts_cameron_omidi_tayfeh_rezaie_2006_rev1345 matches the branch goal)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

## Research Strategy

Strategic artifacts are persisted proof-state context, not verified mathematical evidence.

- Latest global advisor synthesis: `art_auto_phd_advisor_root_advisor_synthesis_3d4684d5eff9`
- Latest active proof compression: `art_researcher_root_compressed_spine_post_lts_rev1210`
- Bridge search: `art_researcher_root_a5_orthogonality_bridge_search_rev1059`; candidates=1, selected=`bridge_root_a5_degree3_orthogonal_rev1059`
- Conjecture portfolio: `none`; candidates=0, selected=`none`
- Active invention authorization: `none`
- Global synthesis due: `False`; reasons=[]
- Graph-derived decisive obligation: `debt_claim_root_c2c3s_p5_mononomial_maximality_rev1168`; selected route=`none`, ready_for_verification=False
- Verifier-filtered outcome learning: family=`research`; local families=0; reference_solution_used=False
- Deep-session ROI: allowed=True; reason=deep-session ROI gate is open
- Information-gain policy: scheduler exposes closing, refuting, root-progress, information, reuse, duplication, token, wall-time, verification-cost, and verifier-filtered outcome components; speculative work never consumes the protected verification reserve.
- Method library policy: 18 developer-curated structural/domain method cards are advisory only and are kept separate from verified facts, external theorem cards, and private speculation.

## Fact Graph

Read-only graph view generated from claims, routes, inferences, debts, and sources.

- Nodes: verified_fact=169, candidate_fact=6, obstruction=93, source_fact=24, branch_cluster=87
- Edges: uses=33, depends_on=33, blocks=1, repairs=6, same_as=0, supersedes=4
- Edge types awaiting a data source (not derived): contradicts, generalizes, specializes
- Branch depth report:
  - `route_claim_root_base2_constituent_synchronization_rev369` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_mutual_orbital_character_scalar_test_rev150` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_mutual_orbital_double_coset_defect_criterion_rev588` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_piecewise_inner_twocoset_criterion_rev140` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl33_E3_maximal_parabolic_subgroups_rev419` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl33_exceptional_mixed_M3_incidence_sync_rev504` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_exceptional_parabolic_E3_rev496` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_exceptional_transitive_E3_rev403` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl33_six_geometric_actions_3closed_rev411` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl3_scalar_fiber_3closed_obstruction_rev313` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_import_psl27_certificate` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_import_psln_projective_nonclosure` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_import_two_orbit_reduction` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_root_graphcentralizer_uniform_obstruction_rev69` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_root_graphstable_geometric_nogo_rev93` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_root_graphstable_multiblock_imprimitive_nogo_rev99` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_local_quotient_surjectivity_criterion_rev42` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl33_four_explicit_maximal_classes_cas_rev7` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_maximal_list_C_rev25` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_totally_3closed_A3_rev37` converging (depth=1, verified=7, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl33_exceptional_mixed_pair_M3_rev41` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl33_exhaustive_maximal_subgroups_theorem_C_rev55` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_reduction_to_parabolic_capture_rev63` converging (depth=1, verified=5, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_residual_flag_descendants_3closed_rev87` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_nonsplit_torus_normalizer_3closed_rev100` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_irreducible_levi_structural_reduction_rev111` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_dihedral_levi_coset_action_3closed_rev123` converging (depth=0, verified=1, candidate=1, active_obstructions=0, converging)
  - `route_claim_root_p5_pair_and_phase_reduction_rev131` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_general_multiseparator_criterion_rev148` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_mixed_anchor_code_pair_criterion_rev179` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_highbase_certificate_assembly_rev193` converging (depth=1, verified=5, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_p5_block_kernel_repair_rev262` converging (depth=1, verified=2, candidate=2, active_obstructions=0, converging)
  - `route_claim_root_projective_levi_free_pair_three_conjugate_base_rev483` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_pgl2_p5_boundary_rev487` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_pgl2_subgroup_dichotomy_rev501` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_pgl2_dichotomy_rev516` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_remote_anchor_inequality_rev522` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_pgl2_affine_rootgroup_rev551` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_pgl2_subgroup_dichotomy_rev561` converging (depth=0, verified=2, candidate=1, active_obstructions=0, converging)
  - `route_claim_root_uniform_parabolic_small_levi_base3_rev573` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_pair_thick_pgl2_dichotomy_rev591` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_pgl2_kernel_rev606` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_affine_root_group_rev622` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_large_levi_kernel_dichotomy_rev626` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_large_levi_cohomology_antiframe_rev640` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_cyclic_antiframe_3closed_rev648` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_pgl2_subgroup_dichotomy_rev670` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_pair_thick_p_divisibility_rev686` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_crossblock_tensor_projection_reduction_rev710` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_exact_right_normalizer_interface_rev714` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_tensor_pairhist_core_trivial_rev722` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_central_scalar_block_criterion_rev736` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_prime_conic_base2_rev768` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_listed_nonparabolic_base2_rev774` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_primitive_core_PC_bloom_rev794` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_primefield_geometric_pruning_rev827` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_primefield_geometric_pruning_rev841` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_C2_C3_direct_base2_rev856` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_nonparabolic_base2_rev872` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p11_p17_dihedral_levi_coset_actions_3closed_rev885` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_dihedral_levi_fixedfiber_reduction_rev891` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_intrinsic_psl27_srow_base2_rev934` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_srow_local_elimination_rev938` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_normal_elementary_abelian_c2c3_dichotomy_rev962` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_c2c3_uniform_base2_descendants_rev966` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_residual_nonparabolic_maximal_exhaustion_rev984` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_semiregular_kernel_collapse_rev994` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_three_fibre_binary_separator_rev1000` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_p5_local_determinant_kernel_collapse_rev1016` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_parabolic_local_determinant_criterion_rev1021` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_S_A6_PSL27_base2_rev1035` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_primitive_nonorthogonal_bloom_rev1049` shallow (depth=0, verified=0, candidate=2, active_obstructions=0)
  - `route_claim_root_bloom_nonorthogonal_simple_subgroups_rev1051` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_a5_degree3_orthogonal_internal_rev1059` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_host_exhaustion_direct_sbase2_rev1090` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_residual_orthogonal_descendants_base2_rev1106` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_residual_parabolic_quotient_normalization_rev1106` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_c2c3s_uniform_base2_descendants_rev1155` blocked (depth=1, verified=3, candidate=0, active_obstructions=1, blocked, converging)
  - `route_claim_root_parabolic_determinant_multiplier_annihilation_rev1171` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_dihedral_frame_tensor_block_kernel_rev1173` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_levi_split_torus_separator_rev1210` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_c8_s_base2_hosts_rev1216` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_core_overlap_frame_gluing_rev1234` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_uniform_parabolic_block_kernel_triviality_rev1262` converging (depth=1, verified=4, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_nonparabolic_maximal_host_base2_rev1278` converging (depth=1, verified=4, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_mixed_parabolic_quotient_incidence_rev1290` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_root_classification_after_quotient_incidence_rev1290` converging (depth=2, verified=10, candidate=0, active_obstructions=0, converging)

## Retrieval Cards

- `card_no_useful_p5_singleton_certificate_rev183` `no_useful_result_found` confidence=0.99: No theorem, proposition, lemma, published table, or reproducible primary-source computation was located that identifies the three anchors and pair stabilizers K_i for the action of G=PSL_3(5) on G/H with H=5^2:D_12, or proves K_0x∩K_1x∩K_2x={x} for all 1240 cosets. The nearest checked primary source, the ATLAS subgroup-program page for L_3(5) inside L_3(5):2, records |L_3(5)|=372000 and standard generators but contains neither this subgroup action nor the required anchors, K_i, code, or exhaustive output.
- `card_bloom_psl3_odd_primitive_core_exact_rev798` `partial_match` confidence=0.99: Bloom's Theorem 1.1 classifies every nontrivial subgroup H of PSL_3(q), q=p^a odd, having no nontrivial normal elementary-abelian subgroup. The possibilities are subfield PSL_3(p^beta), subfield projective unitary groups, specified index-three extensions of these, PSL_2(p^beta) or PGL_2(p^beta), A_5, PSL_2(7), A_6, A_7, or an index-two extension of A_6, with the divisibility and congruence conditions stated there; each indicated type has one GL_3(q)/Z(SL_3(q))-conjugacy class. Theorem 5.14 gives the corresponding exhaustive list of nonabelian simple subgroups. Lemma 6.3 realizes PSL_2(p^beta) by the determinant-normalized symmetric-square representation, gives one GL_3(q)-class, and identifies its SL_3(q)-normalizer with the corresponding PGL_2(p^beta) image times the scalar center. Lemma 6.4 states that, outside characteristic 5, A_5 occurs exactly for q congruent to plus or minus 1 modulo 10, has one GL_3(q)-class, and its inverse image is self-normalizing in SL_3(q). Lemma 6.5 states that, outside characteristic 7, PSL_2(7) occurs exactly when q^3 is congruent to 1 modulo 7, equivalently when the displayed polynomial 2r^2+r+1 has a root; its two parameter choices give conjugate image groups, and its inverse image is self-normalizing. Lemma 6.6 states that A_6 occurs only for q=5^a with a even or q congruent to 1 or 19 modulo 30, and gives its conjugacy and normalizers. Lemma 6.7 states that A_7 occurs only for q=5^a with a even and gives one GL_3(q)-class with self-normalizer. The proof of Theorem 1.1 on page 176 passes from a minimal normal product of simple groups to one simple factor and its calculated normalizer.
- `card_bloom_theorem_5_14_lemmas_6_3_6_5_rev816` `direct_match` confidence=0.98: Bloom 1967 Theorem 5.14: For q=p^a odd and Lambda:SL3(q)->PSL3(q), if S is a nonabelian simple subgroup and S_tilde=Lambda^{-1}(S), then S_tilde is GL3(q)-conjugate to <SL3(p^beta),Z> with beta|a or <U3(p^beta),Z> with 2beta|a; or S is PSL2(p^beta), A5, PSL2(7), A6 with q congruent 1 mod 3, or A7 with p=5 and a even. Lemma 6.3: in the PSL2(p^beta) case beta|a, S_tilde=S0 x Z, all S0 are GL3(q)-conjugate, S0 is the determinant-normalized symmetric-square image, the same map embeds PGL2(p^beta) as S1, and N_SL3(q)(S_tilde)=S1 x Z. Lemma 6.5: if p is not 7 and S is PSL2(7), then S_tilde=S0 x Z; such groups exist iff q^3 congruent 1 mod 7; all S0 are GL3(q)-conjugate; and N_SL3(q)(S_tilde)=S_tilde.
- `card_bloom_1967_theorem_5_14_lemmas_6_3_6_5_rev833` `conditional_match` confidence=0.99: Bloom Theorem 5.14 (p. 170): let q=p^a be odd and let \widetilde H be the full inverse image under \Lambda:SL_3(q)\to PSL_3(q) of a nonabelian simple subgroup H of even order. Then exactly one of the following types occurs: (I) \widetilde H is GL_3(q)-conjugate to \langle SL_3(p^\beta),Z\rangle with \beta\mid a, or to \langle U_3(p^\beta),Z\rangle with 2\beta\mid a; (II) H\cong PSL_2(p^\beta) for some \beta; (III) H\cong A_5 or PSL_2(7); (IV) H\cong A_6 and q\equiv1\pmod 3; (V) H\cong A_7, p=5, and a is even. Here Z=\ker\Lambda, and Bloom notes PSL_2(5)\cong A_5 and PSL_2(9)\cong A_6. Bloom Lemma 6.3 (pp. 171-172): if H\cong PSL_2(p^\beta), then \beta\mid a and \widetilde H=H_0\times Z with H_0\cong PSL_2(p^\beta); for each \beta\mid a these subgroups exist in one GL_3(q)-conjugacy class. A representative is the determinant-normalized symmetric-square image \rho(PSL_2(p^\beta)), formula (6.1), the same formula embeds PGL_2(p^\beta) as H_1\le SL_3(q), and N_{SL_3(q)}(\widetilde H)=H_1\times Z. Bloom Lemma 6.5 (p. 173): assuming p\ne7 and H\cong PSL_2(7), one has \widetilde H=H_0\times Z with H_0\cong PSL_2(7); such subgroups exist iff q^3\equiv1\pmod7, form one GL_3(q)-conjugacy class (the two roots of 2r^2+r+1 give conjugate image groups), and N_{SL_3(q)}(\widetilde H)=\widetilde H.
- `card_psl27_order7_outer_elkies_sec11_rev946` `partial_match` confidence=0.99: Let S=PSL_2(F_7), identified also with SL_3(F_2). Then Aut(S)=PGL_2(F_7), so Out(S)=Aut(S)/S has order two. The elements of order seven form two S-conjugacy classes, denoted 7A and 7B, and every outer automorphism interchanges these classes. If x lies in 7A, its Sylow-seven subgroup P=<x> is cyclic of order seven and N_S(P) has order 21 and structure C_7:C_3; more precisely, N_S(P)=<x,h> for an element h of order three satisfying h^{-1}xh=x^2.
- `card_bloom1967_psl3_odd_simple_subgroups_theorem1_1_rev1047` `stronger_match` confidence=0.98: Bloom's Theorem 1.1, in normalized notation, states: let q=p^a be odd and let H be a nontrivial subgroup of PSL_3(q) with no nontrivial normal elementary-abelian subgroup. Then H is one of the following types: PSL_3(p^b) with b dividing a; a projective unitary subgroup with 2b dividing a; an indicated index-three extension of one of those subfield groups; PSL_2(p^b) or PGL_2(p^b) with b dividing a and p not equal to 3; PSL_2(5) when q is congruent to plus or minus 1 modulo 10; PSL_2(7) when q^3 is congruent to 1 modulo 7; A_6, A_7, or A_6.2 when p=5 and a is even; or A_6 when q is congruent to 1 or 19 modulo 30. The indicated subgroups are unique up to the stated GL_3(q)-conjugacy. The proof first obtains the simple-subgroup list in Theorem 5.14 and then checks occurrence, conjugacy, and normalizers in Lemmas 6.1 through 6.7.
- `card_bloom1967_exact_simple_subgroups_packet_rev1057` `direct_match` confidence=0.99: Let q=p^a with p odd, let Λ:SL_3(q)→PSL_3(q) be the natural quotient, let Z=ker(Λ), and let E be the inverse image under Λ of a nonabelian simple subgroup of even order. Bloom's Theorem 5.14 states that exactly one of the following types occurs: (I) E is GL_3(q)-conjugate to <SL_3(p^β),Z> with β|a, or to <U_3(p^β),Z> with 2β|a; (II) ΛE is isomorphic to PSL_2(p^β); (III) ΛE is isomorphic to A_5 or PSL_2(7); (IV) ΛE is isomorphic to A_6 and q≡1 mod 3; or (V) ΛE is isomorphic to A_7 with p=5 and a even. Lemma 6.3 refines type (II): β|a, E=E_0×Z with E_0≅PSL_2(p^β), all such E_0 are GL_3(q)-conjugate, and a representative is the determinant-normalized symmetric-square map [a b;c d]↦(ad-bc)^{-1}[[a^2,2ab,b^2],[ac,ad+bc,bd],[c^2,2cd,d^2]]; the same formula embeds PGL_2(p^β), and the resulting subgroup gives the normalizer. Lemma 6.4, for p≠5, states that type A_5 has E=E_0×Z with E_0≅A_5, exists exactly when q≡±1 mod 10, is unique up to GL_3(q)-conjugacy, and is represented by the explicit degree-three matrices in equations (6.2)–(6.3), whose parameter satisfies 4t^2-2t-1=0; it is self-normalizing. Lemma 6.5, for p≠7, states that type PSL_2(7) has E=E_0×Z with E_0≅PSL_2(7), exists exactly when q^3≡1 mod 7, is unique up to GL_3(q)-conjugacy, is represented by the matrices displayed there with parameter satisfying 2r^2+r+1=0, and is self-normalizing. Lemma 6.6, for p≠3, states that type A_6 is the unique central triple-cover structure E=E', |Z|=3, E/Z≅A_6, and occurs exactly when either p=5 with a even or q≡1 or 19 mod 30; it also gives the GL_3(q)-conjugacy and normalizer clauses. Lemma 6.7 states that type A_7 occurs when q=5^a with a even; every such inverse image satisfies E=E', |Z|=3, E/Z≅A_7, has the uniquely determined structure described there, is unique up to GL_3(q)-conjugacy, and is self-normalizing.
- `card_bloom1967_theorem1_1_simple_psl3_odd_rev1064` `stronger_match` confidence=0.99: Let q=p^a for odd prime p, and let H <= PSL_3(q) be nontrivial with no nontrivial normal elementary-abelian subgroup. Then H is one of: PSL_3(p^beta) (beta divides a); PU_3(p^beta) (2beta divides a); an index-3 extension of one of these under the stated divisibility conditions; PSL_2(p^beta) or PGL_2(p^beta) (beta divides a, p not equal to 3); A_5 when q is congruent to plus or minus 1 modulo 10; PSL_2(7) when q^3 is congruent to 1 modulo 7; A_6, A_7, or an index-2 extension of A_6 when p=5 and a is even; or A_6 when q is congruent to 1 or 19 modulo 30. Each indicated type is unique up to GL_3(q)/Z(SL_3(q))-conjugacy.
- `retrieval_card_bloom1967_exact_simple_subgroups_rev1074` `direct_match` confidence=0.98: Let q=p^a be odd, let Lambda:SL_3(q)->PSL_3(q), let Z=ker(Lambda), and let E=Lambda^{-1}(T) for a nonabelian simple subgroup T of even order. Bloom Theorem 5.14 states that one of the following holds: (I) E is GL_3(q)-conjugate to <SL_3(p^beta),Z> with beta|a, or to <U_3(p^beta),Z> with 2beta|a; (II) T is PSL_2(p^beta) for some beta; (III) T is A_5 or PSL_2(7); (IV) T is A_6 and q=1 mod 3; (V) T is A_7, p=5, and a is even. Lemma 6.3 sharpens (II): beta|a, E=E_0 x Z with E_0=PSL_2(p^beta), one GL_3(q)-class exists for each beta|a via matrix map (6.1), and N(E)=PGL_2(p^beta) x Z. Lemma 6.4, for p!=5: T=A_5 occurs iff q=+1 or -1 mod 10; E=E_0 x Z, there is one GL_3(q)-class, matrices are given in (6.2)-(6.3), and N(E)=E. Lemma 6.5, for p!=7: T=PSL_2(7) occurs iff q^3=1 mod 7; E=E_0 x Z, there is one GL_3(q)-class, explicit matrices are displayed, and N(E)=E. Lemma 6.6, for p!=3: T=A_6 occurs iff q=5^a with a even, or q=1 or 19 mod 30; E is perfect with center Z of order 3 and E/Z=A_6, its GL_3(q)-class is specified by (6.2),(6.5), and its normalizer is as stated there. Lemma 6.7: when q=5^a with a even, A_7 subgroups exist; every inverse image is perfect with center Z of order 3 and quotient A_7, all are in the displayed GL_3(q)-class, and N(E)=E.
- `card_bloom1967_thm1_1_residual_simple_subgroups_rev1086` `partial_match` confidence=0.99: Bloom's Theorem 1.1 classifies every nontrivial subgroup J of PSL_3(r^a), r odd, having no nontrivial normal elementary-abelian subgroup. Subject to its stated field conditions, J is one of: a subfield PSL_3(r^beta); a projective unitary group PU_3(r^beta); a specified index-three extension of one of those groups; PSL_2(r^beta) or PGL_2(r^beta); PSL_2(5); PSL_2(7); A_6; A_7; or the specified index-two extension of A_6. The proof is completed by Theorem 5.14 and Lemmas 6.3–6.7. In particular, Lemma 6.3 identifies the degree-three PSL_2(r^beta) embedding with the determinant-normalized symmetric-square representation, while Lemma 6.5 gives the PSL_2(7) occurrence condition q^3 congruent to 1 modulo 7. Specializing to a=1, p>=5, and p congruent to 2 modulo 3, every proper nonabelian simple T<SL_3(p) is PSL_2(p), A_5, or PSL_2(7); the first two types preserve nondegenerate symmetric ternary forms. Hence a T not contained in an SL_3(p)-conjugate of SO_3(p) is PSL_2(7), necessarily with p^3 congruent to 1 modulo 7. This is strictly stronger than the requested conclusion (P).
- `card_lavrauw_fundamental_projective_geometry_theorem8_rev1112` `partial_match` confidence=0.99: Theorem 8: The collineation group of PV with dim V at least 3 is PΓL(V).
- `card_bloom_psl3_odd_simple_subgroups_thm514_rev1122` `partial_match` confidence=0.98: Normalized complete mathematical transcription of Bloom, Theorem 5.14 together with the occurrence refinements in Lemmas 6.1–6.7: let q=p^a with p odd, let Lambda:SL_3(q)->PSL_3(q), and let E=Lambda^{-1}(T), where T<=PSL_3(q) is nonabelian simple. Then one of the following holds: (I) E is GL_3(q)-conjugate to <SL_3(p^b),Z> for b|a or <U_3(p^b),Z> for 2b|a; (II) T is isomorphic to PSL_2(p^b); (III) T is isomorphic to A_5 or PSL_2(7); (IV) T is isomorphic to A_6 and q is 1 modulo 3; (V) T is isomorphic to A_7, p=5, and a is even. Lemmas 6.3–6.7 refine this as follows: b|a in the PSL_2 row; PSL_2(7) occurs exactly when q^3 is 1 modulo 7; A_6 occurs exactly when q=5^a with a even or q is 1 or 19 modulo 30; and A_7 occurs only when q=5^a with a even. The proof passage at the end of Section 6 separates these simple subgroups from their normalizers and derives Theorem 1.1 by placing an arbitrary subgroup without a nontrivial normal elementary-abelian subgroup between its unique simple minimal normal subgroup and that subgroup's normalizer.

## Claims

- `claim_root_base2_constituent_synchronization_rev369` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G act faithfully on two transitive sets Omega_1 and Omega_2. Assume both constituent actions are 3-closed and the action on Omega_1 has a base of size at most two. Then the diagonal action of G on the disjoint union Omega_1 disjoint union Omega_2 is 3-closed.
- `claim_root_bloom_nonorthogonal_simple_subgroups_rev1051` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p >= 5 be prime with p congruent to 2 modulo 3, and let T < SL_3(p) be a proper nonabelian simple subgroup. If T is not contained in any conjugate of SO_3(p), then T is isomorphic to PSL_2(7); moreover p^3 is congruent to 1 modulo 7.
- `claim_root_c2c3_uniform_base2_descendants_rev966` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3 and G=SL_3(p)=PSL_3(p). Let N_2 be the determinant-one monomial subgroup and N_3=GammaL_1(p^3) intersect G. For every H<=N_2 or H<=N_3, the action of G on G/H has a base of size at most two and hence is 3-closed. Moreover, if G on G/K is 3-closed, then the diagonal action on G/H disjoint union G/K is 3-closed.
- `claim_root_c2c3s_uniform_base2_descendants_rev1155` `informally_verified` `blocked` `partial_result` maturity=verified root_distance=1: Let p≥5 be prime with p≡2 modulo 3 and G=PSL_3(p). If H≤M<G, where M is a maximal subgroup of Aschbacher type C2, C3, or S, then b(G,G/H)≤2. For M itself the base size is exactly two. In the linear C2 family there is no maximal C2 row at p=5.
- `claim_root_c8_s_base2_hosts_rev1216` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). Every subgroup H contained in an orthogonal C8 subgroup of G has b(G,G/H)≤2. Every subgroup H contained in an Aschbacher-S maximal subgroup of G also has b(G,G/H)≤2.
- `claim_root_cyclic_antiframe_3closed_rev648` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3, let G=SL_3(p)=PSL_3(p), and let D≤F_p^×. For Y_D={(v,φ):v≠0, φ≠0, φ(v)=1}/D, where d sends (v,φ) to (dv,d^{-1}φ), the natural permutation action of G on Y_D is 3-closed.
- `claim_root_dihedral_frame_tensor_block_kernel_rev1173` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3, let G=SL_3(p), let P=Q⋊GL_2(p) be a point parabolic, let L be generated by [[0,1],[1,0]] and [[0,1],[-1,1]], and let H=Q⋊L. In the action on H\G, assume the canonical projective block system is invariant under G^(3). Then the kernel of G^(3) on that block system is trivial. The dual line-parabolic assertion also holds.
- `claim_root_dihedral_levi_fixedfiber_reduction_rev891` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For the p=11 and p=17 dihedral-Levi actions G on G/H used in the selected separator route, 37 of the 64 fixed-set inclusions hold formally because at least one row entry is the identity. For every remaining row, Fix(<k_1^(-1)k_0,k_2^(-1)k_0>) subseteq Fix(k_0) is equivalent to the projective invariant-line and GL_2/L fiber-extension conditions stated in art_researcher_root_dihedral_levi_fixedfiber_reduction_rev891.
- `claim_root_graphcentralizer_uniform_obstruction_rev69` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime and n>=3 with gcd(n,p-1)=1. Put S=PSL_n(p)=SL_n(p), X=S semidirect <tau> with tau(g)=g^{-T}, and L=C_X(tau). Then there is an ordered triple in X/L whose pointwise stabilizer is contained in S. Consequently X is not contained in the 3-closure of S on X/L. In particular, the graph-centralizer action cannot witness non-total 3-closure for PSL_5(2) or for any member of the residual prime-field family.
- `claim_root_graphstable_geometric_nogo_rev93` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime, n>=3, gcd(n,p-1)=1, S=SL_n(p)=PSL_n(p), and X=S semidirect <tau> with tau(g)=g^{-T}. (i) If P<S is a proper parabolic with N_X(P) not contained in S, then on X/N_X(P) the relative outer base of X over S is at most three, so X is not contained in the 3-closure of S. (ii) If J is the stabilizer of a standard ordered two-block direct decomposition and H=<J,tau>, then on X/H the relative outer base is at most two, so again X is not contained in the 3-closure of S.
- `claim_root_graphstable_multiblock_imprimitive_nogo_rev99` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime, n=rd with r>=3, d>=1, gcd(n,p-1)=1, and S=PSL_n(p) nonabelian simple. Let X=S semidirect <tau>, tau(g)=g^{-T}, and let H be generated by tau and the S-stabilizer of an unordered decomposition of F_p^n into r equal d-dimensional summands. On Omega=X/H, b_rel(X,S;Omega)<=3; hence X intersect S^(3)=S. Thus this full graph-stable imprimitive action cannot witness non-3-closure via the graph extension.
- `claim_root_highbase_certificate_assembly_rev193` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be a finite nonabelian simple group. Suppose every proper H<G with b(G,G/H)>2 has a 3-closed coset action, and suppose that for every ordered pair H,K of such high-base subgroups there exist anchors a_0,a_1,a_2∈G/H whose three fixed pair-stabilizers L_i satisfy L_0x∩L_1x∩L_2x={x} for every x∈G/H⊔G/K. Then G is totally 3-closed.
- `claim_root_intrinsic_psl27_srow_base2_rev934` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3 and put G=SL_3(p)=PSL_3(p). If S≤G is isomorphic to PSL_2(7), then b(G,G/S)=2. Moreover, the existence of S forces p modulo 7 to lie in {1,2,4}.
- `claim_root_irreducible_levi_structural_reduction_rev111` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, G=PSL_3(p)=PGL_3(p), P=Q semidirect GL_2(p) a point parabolic, and H<=P with irreducible Levi image L. Every 3-closure element on G/H induces an element of G on G/P and, after normalization, preserves Orb_2(G_x,PG(2,p)) for every x; injectivity of this fingerprint on P/H implies 3-closure. Moreover H intersect Q is 1 or Q. In the first case H is a cocycle graph and H intersect H^{q_v} is isomorphic to C_L(v), so b(G,H)>2 implies L has no regular orbit on Q. In the second case H=Q semidirect L. If H is normal in P, then H=Q semidirect det^{-1}(C) for some C<=F_p^times and is a certified scalar-fiber stabilizer. The contragredient-dual line statements hold.
- `claim_root_large_levi_cohomology_antiframe_rev640` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P=Q semidirect GL_2(p), and H<=P have Levi projection R whose projective image contains PSL_2(p). Put D=det(R). Then R=det^(-1)(D). If H intersects Q trivially, H is Q-conjugate to R and b(G,G/H)<=3, with b(G,G/H)<=2 when D=1. If H contains Q, then G/H is the D-scalar-fiber action on nonzero vectors and is 3-closed. The dual statement holds in a line parabolic.
- `claim_root_large_levi_kernel_dichotomy_rev626` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, let G=PSL_3(p)=SL_3(p), and let P=Q semidirect GL_2(p) be a point or line parabolic. If H<=P and the projective image of pi(H) contains PSL_2(p), then SL_2(p)<=pi(H), H intersect Q is either 1 or Q, and H is respectively a 1-cocycle graph over pi(H) or Q semidirect pi(H). Moreover the projective image is PSL_2(p) or PGL_2(p).
- `claim_root_listed_nonparabolic_base2_rev774` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). If M is the determinant-one monomial subgroup, a Singer-torus normalizer, a conic stabilizer SO(B), or any subgroup isomorphic to PSL_2(7) or A_6, then b(G,G/M)=2.
- `claim_root_local_quotient_surjectivity_criterion_rev42` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be normal in a faithful finite permutation group X on Omega. For alpha in Omega^3 let X_alpha be the pointwise stabilizer. Then X is contained in G^(3) if and only if X_alpha G=X for every alpha, equivalently every X_alpha maps surjectively onto X/G. If moreover G<X, this faithful action proves that G is not totally 3-closed.
- `claim_root_mixed_parabolic_quotient_incidence_rev1290` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). Let H and K be proper subgroups contained in point or line parabolics. If the constituent actions on G/H and G/K are individually 3-closed, then the diagonal action on G/H disjoint union G/K is 3-closed. This covers all point-point, point-line, line-point, line-line, dual, descendant, and repeated-constituent cases without a base-two hypothesis.
- `claim_root_mutual_orbital_character_scalar_test_rev150` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be a finite group and H,K≤G. If χ_H=Ind_H^G(1_H), then K and G have the same orbits on (G/H)^2 if and only if ⟨Res_K χ_H,Res_K χ_H⟩_K=⟨χ_H,χ_H⟩_G. Hence H,K form a mutual-orbital pair exactly when this equality and its version with H and K interchanged both hold.
- `claim_root_mutual_orbital_double_coset_defect_criterion_rev588` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be a finite group and let H,K<=G satisfy G=HK. Put L=H intersection K and r(A;B)=|A backslash G/B|. Then H=L(H intersection xHx^(-1)) for every x in G if and only if r(L;H)=r(H;H), and K=L(K intersection xKx^(-1)) for every x in G if and only if r(L;K)=r(K;K). Equivalently, the two mutual pair-orbital equalities hold exactly when both associated nonnegative double-coset defects vanish.
- `claim_root_nonparabolic_maximal_host_base2_rev1278` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). If H<G is contained in a maximal subgroup M which is neither a point nor a line parabolic, then b(G,G/H)≤2. More precisely, every such M is contained in the determinant-one monomial C2 host, the extension-field C3 host ΓL_1(p^3)∩G, an orthogonal C8 host, or is an almost-simple Aschbacher-S host.
- `claim_root_normal_elementary_abelian_c2c3_dichotomy_rev962` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3, V=F_p^3, and G=SL(V)=PSL_3(p). If M<G acts irreducibly on V and has a nontrivial normal elementary-abelian subgroup, then either M preserves an unordered decomposition of V into three one-dimensional F_p-subspaces or M preserves a one-dimensional F_{p^3}-vector-space structure. Equivalently, M lies in a C2 decomposition stabilizer or a C3 extension-field normalizer. If M is maximal in G, it equals the corresponding determinant-one normalizer.
- `claim_root_p11_p17_dihedral_levi_coset_actions_3closed_rev885` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For p in {11,17}, let G=SL_3(p)=PSL_3(p), let L=<[[0,1],[1,0]],[[0,1],[-1,1]]> in GL_2(p), and let H_p consist of the determinant-one point-parabolic matrices whose Levi block lies in L. Then the faithful transitive action of G on G/H_p is 3-closed.
- `claim_root_p5_central_scalar_block_criterion_rev736` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let X=GL_2(5), Z_0={±I}, L=<A,B> as in the exact p=5 tensor action, W=X/Z_0 acting on D=X/L, and z=(2I)Z_0. Every non-singleton W-block containing L contains zL. Consequently, if U<=Sym(D) is normalized by W and preserves a labeled vertex invariant Sigma with Sigma(L) distinct from Sigma(zL), then U=1.
- `claim_root_p5_crossblock_tensor_projection_reduction_rev710` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: In the exact p=5 action, assume the established 31-block system is preserved by C=G^(3), let K be its block kernel, D=P/H, and W=P^D. For representative ordered off-D block pairs of equal, D-collinear, and D-noncollinear type, let I_t be the first-coordinate image of the corresponding G-orbit-color tensor autotopism group and put J=⋂_t⋂_{w∈W}wI_tw^(−1). Then pr_D(K)≤J. Consequently J≤N_P(H)/H implies the required fiberwise normalizer projection.
- `claim_root_p5_dihedral_levi_coset_action_3closed_rev123` `informally_verified` `blocked` `partial_result` maturity=verified root_distance=1: Let G=PGL_3(5)=PSL_3(5), let P=Q⋊GL_2(5) be a point parabolic, let L=<[[0,1],[1,0]],[[0,1],[4,1]]>≤GL_2(5), and put H=Q⋊L. Then the faithful action of G on G/H has 3-closure equal to G.
- `claim_root_p5_exact_right_normalizer_interface_rev714` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For A=((0,1),(1,0)), B=((0,1),(4,1)), C=I+B in GL_2(5), L=<A,B>, P=Q⋊GL_2(5), H=Q⋊L and D=P/H, one has N_P(H)/H=<hat(C)H>≅C_4. In the left coset action W=P^D, the corresponding four right translations form the full centralizer C_Sym(D)(W).
- `claim_root_p5_local_determinant_kernel_collapse_rev1016` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PGL_3(5)=PSL_3(5), P=Q⋊GL_2(5), L=<[[0,1],[1,0]],[[0,1],[4,1]]>, H=Q⋊L, Ω=G/H, C=G^(3), and K the kernel induced by C on the 31 blocks G/P. Then K=1. Consequently G is 3-closed on Ω.
- `claim_root_p5_pair_and_phase_reduction_rev131` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: In the action of G=PGL_3(5) on G/H, where H=Q semidirect <[[0,1],[1,0]],[[0,1],[4,1]]>, every two-point stabilizer has order at least four: a same-projective-block pair stabilizer contains Q of order 25, while a distinct-block pair stabilizer contains two distinct involutory homologies centered at the two block points. Hence no three-involution separator triangle exists. Moreover, the action induced by a point parabolic P on one fiber P/H has kernel Q semidirect {plus or minus I}, has a two-point base, and is 3-closed. Consequently any normalizer-valued block phase belonging to the global 3-closure takes values only in the scalar subgroup F_5^times/{plus or minus I} of order two.
- `claim_root_p5_semiregular_kernel_collapse_rev994` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PGL_3(5)=PSL_3(5), P=Q semidirect GL_2(5), L=<((0,1),(1,0)),((0,1),(4,1))>, H=Q semidirect L, Omega=G/H, C=G^(3), and K the kernel of C on the 31 blocks G/P. If K is semiregular, then K centralizes G and lies in N_G(H)/H, where |N_G(H)/H|=4. Hence, if the three nonidentity right-normalizer permutations are excluded from C, then C=G.
- `claim_root_p5_tensor_pairhist_core_trivial_rev722` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: In the exact p=5 setup of the three cross-block tensors T_eq, T_col, and T_ncol on D=P/H, the W-normal tensor core J=intersection_{t,w} w I_t w^{-1} is trivial. Consequently [J,W]=1 and, for the block kernel K of the 3-closure, pr_D(K)=1.
- `claim_root_p5_three_fibre_binary_separator_rev1000` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PGL_3(5), H=Q semidirect <A,B>, Omega=G/H, pi:Omega->PG(2,5), and let B_0 be the pointwise block kernel. Put b_1=[0:1:0], b_2=[0:0:1], b_3=[1:1:1]. Their pointwise stabilizer in H is trivial. If lifts y_i in pi^{-1}(b_i) satisfy (i) pairwise H-orbital reconstruction of the anchor triple and (ii) pi^{-1}(pi(w)) intersect H_{y_1}w intersect H_{y_2}w intersect H_{y_3}w={w} for every w in Omega, then H^(2) intersect B_0=1.
- `claim_root_pair_thick_affine_root_group_rev622` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥3 be prime and Y≤PGL₂(p) act naturally on P¹(F_p). If the pointwise stabilizer Y_{a,b} is nontrivial for every pair of distinct projective points a,b, then PSL₂(p)≤Y. Equivalently, if PSL₂(p) is not contained in Y, then Y has a pointwise free pair.
- `claim_root_pair_thick_p_divisibility_rev686` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be a prime and Y<=PGL_2(p). If the pointwise stabilizer Y_{a,b} is nontrivial for every pair of distinct points a,b in P^1(p), then p divides |Y|.
- `claim_root_pair_thick_pgl2_affine_rootgroup_rev551` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 (mod 3), and let Y≤PGL₂(p) act on P¹(F_p). If Y has no global fixed point and every pointwise two-point stabilizer Y_{a,b}, for a≠b, is nontrivial, then PSL₂(p)≤Y. Equivalently, if PSL₂(p) is not contained in Y, then Y has a pointwise base of size two.
- `claim_root_pair_thick_pgl2_dichotomy_rev516` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, let X=P^1(F_p), and let Y<=PGL_2(p). For distinct a,b in X, write Y_{a,b} for the pointwise stabilizer of a and b. If Y has no global fixed point on X and Y_{a,b} is nontrivial for every distinct a,b, then PSL_2(p)<=Y.
- `claim_root_pair_thick_pgl2_dichotomy_rev591` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>2 be prime and Y≤PGL_2(p). If Y has no global fixed point on P^1(p) and Y_a∩Y_b is nontrivial for every pair of distinct projective points a,b, then PSL_2(p)≤Y. In particular this holds for every prime p≥5 with p≡2 mod 3.
- `claim_root_pair_thick_pgl2_kernel_rev606` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>2 be prime and let Y≤PGL₂(p). If the pointwise stabilizer Y_{a,b}=Y_a∩Y_b is nontrivial for every two distinct points a,b∈P¹(p), then PSL₂(p)≤Y. Equivalently, every subgroup of PGL₂(p) omitting PSL₂(p) has a pair of distinct projective points with trivial pointwise stabilizer.
- `claim_root_pair_thick_pgl2_p5_boundary_rev487` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let Y≤PGL_2(5) act naturally on P^1(F_5). If Y has no global fixed point and the pointwise stabilizer Y_{a,b} is nontrivial for every two distinct projective points a,b, then PSL_2(5)≤Y. In fact the only such subgroups are PSL_2(5) and PGL_2(5).
- `claim_root_pair_thick_pgl2_subgroup_dichotomy_rev501` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For every prime p≥5 with p≡2 (mod 3) and every subgroup Y≤PGL₂(p), if Y has no global fixed point on P¹(F_p) and the pointwise stabilizer Y_{a,b} is nontrivial for every two distinct projective points a,b, then PSL₂(p)≤Y.
- `claim_root_pair_thick_pgl2_subgroup_dichotomy_rev561` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 (mod 3), and let Y≤PGL₂(p) act on P¹(F_p). If Y has no global fixed point and the pointwise stabilizer Y_{a,b} is nontrivial for every pair of distinct projective points a,b, then PSL₂(p)≤Y. Equivalently, if PSL₂(p) is not contained in Y, then Y has a pointwise base of size two. In fact, the conclusion remains true without the congruence and no-global-fixed-point hypotheses.
- `claim_root_pair_thick_pgl2_subgroup_dichotomy_rev670` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 (mod 3), and let Y≤PGL_2(p) act on P^1(F_p). For distinct a,b, write Y_{a,b}=Y_a∩Y_b for the pointwise pair stabilizer. If Y has no global fixed point and Y_{a,b}≠1 for every pair of distinct points a,b, then PSL_2(p)≤Y.
- `claim_root_parabolic_determinant_multiplier_annihilation_rev1171` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 mod 3, G=SL_3(p)=PSL_3(p)=PGL_3(p), P a point or line parabolic, H≤P, Ω=H\G, C=G^(3), and K the kernel of C on the canonical blocks P\G. For a point block x let λ_x:P_x→F_p^× be the eigenvalue on x, using the dual one-space for a line block, and put P_x^0=ker λ_x. Then every k∈K satisfies αk∈α^{P_x^0} for every α lying over x. Equivalently, the canonical displacement class in F_p^×/λ_x(G_α) is trivial on every fiber.
- `claim_root_parabolic_local_determinant_criterion_rev1021` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime, G=PGL_3(p), P a projective-point stabilizer with unipotent radical Q, M=P/Q≅GL_2(p), L≤M, H the inverse image of L, and N=core_M(L). If N≤Z(M), the faithful action M/N on M/L has base at most two, and det(L)∩r^{-1}(F_p^×)^2 is empty for every scalar rI outside N, then G on G/H is 3-closed. For p=5 and L generated by [[0,1],[1,0]] and [[0,1],[4,1]], all hypotheses hold, so the exact PSL_3(5) action on G/(Q⋊L) is 3-closed.
- `claim_root_piecewise_inner_twocoset_criterion_rev140` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be a finite nonabelian simple group and H,K<G proper. On A=G/H disjoint-union B=G/K, let pi_s act as a nonidentity s in G on A and trivially on B. Then pi_s lies in the 3-closure of diagonal G for some nonidentity s if and only if K and G have the same orbits on A^2 and H and G have the same orbits on B^2. Equivalently, G=HK and, for L=H intersection K, H=L(H intersection xHx^(-1)) and K=L(K intersection xKx^(-1)) for every x in G. If these conditions hold, every pi_s lies in the 3-closure and nonidentity pi_s lies outside diagonal G. Any such pair promotes to a pair of proper maximal overgroups with the same property.
- `claim_root_primefield_geometric_pruning_rev827` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 mod 3, V=F_p^3, and G=SL(V)=PSL_3(p). If M<G is a nonparabolic maximal subgroup belonging to an Aschbacher geometric class, then M can arise only through C2, C3, or orthogonal C8; C4, C5, C6, C7, symplectic C8, and genuinely unitary C8 are absent. Moreover, if H≤M and b(G,G/M)≤2, then b(G,G/H)≤2.
- `claim_root_primefield_geometric_pruning_rev841` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, put G=SL_3(p)=PSL_3(p), and let M<G be a nonparabolic maximal subgroup belonging to an Aschbacher geometric family. Then M has type C2, C3, or orthogonal C8. Moreover, if the action of G on G/M has a base of size at most two, then the action of G on G/H has a base of size at most two for every H<=M.
- `claim_root_projective_levi_free_pair_three_conjugate_base_rev483` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime, V=F_p^3, G=PGL(V), U a projective point, J≤G_U, and rho_U:G_U→PGL(V/U) the induced quotient projectivity. If Y=rho_U(J) has a two-point base on P(V/U), then there exist three G-conjugates of J with trivial intersection; hence G/J is faithful and has base size at most three. Moreover, the two-point-base hypothesis holds whenever |Y|-1<p(p+1)/2.
- `claim_root_psl33_E3_maximal_parabolic_subgroups_rev419` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=SL_3(3), let P be a projective point stabilizer, and let E(P)={H<P: H intersect H^g is nontrivial for every g in G}. Every maximal subgroup of P belongs to E(P). Up to P-conjugacy the maximal subgroups are precisely the geometric stabilizers of orders 48,108,144,216 (anti-flag, incident flag, partition of the four-line pencil, and nonzero vector), occurring inside P with multiplicities 9,4,3,1 respectively.
- `claim_root_psl33_exceptional_mixed_M3_incidence_sync_rev504` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3), let T be the six G-conjugacy types in E(P) certified by art_researcher_root_psl33_E3_exact_ternary_proof_rev490, and let T* be their dual line-parabolic types. For every H,K in T union T*, with repetition allowed, the diagonal action on G/H disjoint union G/K is 3-closed.
- `claim_root_psl33_exceptional_mixed_pair_M3_rev41` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=2: Let G=PSL_3(3). Let H and K belong to the six exceptional point-parabolic classes in E(P), or to their dual line-parabolic classes in E(P*). Then the diagonal action of G on G/H disjoint-union G/K is 3-closed, including repeated constituents and every point/line orientation.
- `claim_root_psl33_exceptional_parabolic_E3_rev496` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3), let P be a point stabilizer, and define E(P)={H<P proper : H intersects H^g nontrivially for every g in G}. Then E(P) consists of 24 subgroups forming six G-conjugacy classes, represented by subgroups of orders 48, 54, 72, 108, 144, and 216. For every H in E(P), the faithful transitive action of G on G/H is 3-closed. The corresponding assertion holds for the six dual line-parabolic classes.
- `claim_root_psl33_exceptional_transitive_E3_rev403` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3), let P be a point stabilizer, and let E(P)={H<P proper : H cap H^g is nontrivial for every g in G}. For every H in E(P), the transitive coset action G on G/H is 3-closed. The same conclusion holds for the dual family E(P*) inside a line stabilizer.
- `claim_root_psl33_exhaustive_maximal_subgroups_theorem_C_rev55` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=2: Let G=PSL_3(3)=SL_3(3). Let P be a point stabilizer, P* a line stabilizer, J a Singer normalizer 13:3, and M a conic stabilizer S4. Every maximal subgroup of G is conjugate to exactly one of P, P*, J, or M. Consequently every proper subgroup of G is contained in a conjugate of one of these four subgroups.
- `claim_root_psl33_four_explicit_maximal_classes_cas_rev7` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=SL_3(3)=PSL_3(3). Let P_1 be the stabilizer of <e_1>, P_2 the stabilizer of ker(e_1^*), J the explicit Singer normalizer generated by multiplication by a root of X^3-X-1 and Frobenius, and M the determinant-one monomial conic stabilizer. Then P_1,P_2,J,M are self-normalizing maximal subgroups of orders 432,432,39,24. Their G-conjugacy classes have sizes 13,13,144,234; P_1 and P_2 are not conjugate; and the union of all conjugates of these four subgroups is G. This claim does not assert that these are all maximal-subgroup classes.
- `claim_root_psl33_maximal_list_C_rev25` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=SL_3(3)=PSL_3(3). Let P_1 and P_2 be respectively a projective-point stabilizer and a projective-line stabilizer, let J be the normalizer 13:3 of a Singer subgroup, and let M be the determinant-one monomial subgroup, equivalently the stabilizer of a nonsingular four-point conic. Every maximal subgroup of G is G-conjugate to exactly one of P_1, P_2, J, or M; P_1 and P_2 are not conjugate.
- `claim_root_psl33_six_geometric_actions_3closed_rev411` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3). The transitive coset action G/H is 3-closed whenever H is one of the six point-parabolic geometric stabilizers of orders 48,54,72,108,144,216 described in art_researcher_root_psl33_E3_geometric_certificate_repair_rev411, or a contragredient-dual stabilizer.
- `claim_root_psl33_totally_3closed_A3_rev37` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3). For every pair of proper subgroups H,K<G, the diagonal action of G on G/H disjoint-union G/K is 3-closed. Consequently PSL_3(3) is totally 3-closed.
- `claim_root_psl3_scalar_fiber_3closed_obstruction_rev313` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime with gcd(3,p-1)=1, let C be any subgroup of F_p^*, and let S=PSL_3(p)=SL_3(p). The natural faithful action of S on (F_p^3 minus {0})/C is 3-closed. Moreover, every determinant-character twist H_(e,C) of the point parabolic restricts to this same S-action, so no such scalar-fiber construction supplies a proper 3-closure witness.
- `claim_root_residual_C2_C3_direct_base2_rev856` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 mod 3 and G=SL_3(p)=PSL_3(p). The determinant-one monomial C2 subgroup and the degree-three Singer-normalizer C3 subgroup each have a two-point base in their coset action. Every subgroup contained in a conjugate of either also has base size at most two and hence has a 3-closed coset action.
- `claim_root_residual_S_A6_PSL27_base2_rev1035` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, let G=SL_3(p)=PSL_3(p), and let M<G be isomorphic to A_6 or PSL_2(7). Then there exists g in G such that M intersect M^g is trivial. Consequently every H<=M has base size at most two on G/H, and the transitive action of G on G/H is 3-closed.
- `claim_root_residual_flag_descendants_3closed_rev87` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, put G=PSL_3(p), and let B be the stabilizer of an incident projective point-line flag in PG(2,p). For every subgroup J<=B, the natural action of G on G/J is faithful and 3-closed.
- `claim_root_residual_host_exhaustion_direct_sbase2_rev1090` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). Every proper subgroup H<G lies in a conjugate of a point or line parabolic, N_2=(GL_1(p) wr S_3)∩G, N_3=ΓL_1(p^3)∩G, SO_3(p), or PSL_2(7), with the last case possible only for p modulo 7 in {1,2,4}. Every H contained in N_2, N_3, or PSL_2(7) has base size at most two. Consequently every high-base H lies under a parabolic or SO_3(p).
- `claim_root_residual_nonparabolic_base2_rev872` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3 and G=PSL_3(p). If H<G is not contained in a point or line parabolic subgroup, then b(G,G/H)<=2. Consequently the transitive coset action G on G/H is 3-closed.
- `claim_root_residual_nonparabolic_maximal_exhaustion_rev984` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, let V=F_p^3, and let G=PSL_3(p)=SL_3(p). If M<G is maximal and stabilizes neither a point nor a plane of V, then M is exactly one of: (i) the determinant-one monomial normalizer N_2; (ii) the determinant-one extension-field normalizer N_3=GammaL_1(p^3) intersect G; (iii) the conic stabilizer C_8=rho(PGL_2(p)); or (iv) a self-normalizing subgroup isomorphic to PSL_2(7), the last possibility occurring only when p^3 is congruent to 1 modulo 7.
- `claim_root_residual_orthogonal_descendants_base2_rev1106` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3 and G=SL_3(p)=PSL_3(p). If M≤G is a conjugate of SO_3(p), then there exists g∈G with M∩M^g=1. Consequently, for every H contained in a conjugate of M, the coset action G on G/H has base size at most two.
- `claim_root_residual_parabolic_quotient_normalization_rev1106` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3, G=SL_3(p)=PSL_3(p), P_ε a point or line parabolic, and H≤P_ε. The 3-closure of G on G/H preserves the fibers of the canonical map G/H→G/P_ε and induces an element of G on the quotient. For a diagonal action on two such coset spaces, the two induced quotient elements agree, using equality for equal quotient types and incidence for point-line quotient types.
- `claim_root_residual_prime_conic_base2_rev768` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 (mod 3), let G=PSL_3(p), and let M be a conic stabilizer, equivalently M=SO(B) for a nondegenerate symmetric bilinear form B on F_p^3. Then there exists g∈G with M∩M^g=1. Consequently b(G,G/M)=2 and b(G,G/H)≤2 for every H≤M.
- `claim_root_residual_primitive_core_PC_bloom_rev794` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, put G=SL_3(p)=PSL_3(p), and let M<G be a proper primitive maximal subgroup whose generalized Fitting subgroup has a unique nonabelian simple component E. Then either M is the conic stabilizer rho(PGL_2(p))=SO_3(p) with E=rho(PSL_2(p)), or p mod 7 belongs to {1,2,4} and M=E is a self-normalizing degree-three image of PSL_2(7). The image in the latter case is unique up to G-conjugacy. No other simple component occurs.
- `claim_root_residual_reduction_to_parabolic_capture_rev63` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3 and G=PSL_3(p). Assume D_p: every proper H<G of base size greater than two admits a G-equivariant quotient to projective points or projective lines and is either a certified scalar-fiber action, up to duality, or contains the pointwise stabilizer of a suitable ordered triple in that quotient. Then every faithful transitive G-action and every diagonal action on two faithful transitive G-sets is 3-closed. Consequently G is totally 3-closed.
- `claim_root_residual_srow_local_elimination_rev938` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, V=F_p^3, and G=SL(V). Let M<=G be almost simple with socle T, and assume T acts absolutely irreducibly on V. Then T is not A6 or A7; if T is A5 or PSL2(p), M preserves a nondegenerate symmetric bilinear form and is geometric C8; and if T is PSL2(7), then p modulo 7 is in {1,2,4}, N_G(T)=T, and hence M=T. Consequently, conditional only on the exhaustive simple-socle list T in {PSL2(p),A5,PSL2(7),A6,A7}, every nongeometric M is exactly a self-normalizing PSL2(7).
- `claim_root_uniform_parabolic_block_kernel_triviality_rev1262` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, let G=SL_3(p)=PSL_3(p), let P be a point or line parabolic, let H<=P, and let C=G^(3) in the coset action on Omega={Hg:g in G}. If K is the kernel of the induced action of C on the projective block system P\G, then K=1. In particular, every k in K satisfying alpha k in alpha^{P_x^0} on every fiber is the identity, so DNFK(p) holds.
- `claim_root_uniform_parabolic_small_levi_base3_rev573` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p≥5 be prime with p≡2 modulo 3, let G=PSL_3(p), and let H<G be contained in a point parabolic. Let Y≤PGL_2(p) be the projective image induced by H on the two-dimensional quotient. If PSL_2(p) is not contained in Y, then the coset action G on G/H has a pointwise base of size at most three. The same conclusion holds for a line parabolic by contragredient duality.
- `root` `informally_verified` `integrated` `root_theorem` maturity=integrated root_distance=0: # Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_3(q)\)

## Definitions

For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), its
**3-closure** \(G^{(3)}\) is the largest subgroup of
\(\operatorname{Sym}(\Omega)\) having the same orbits as \(G\) on ordered
triples \(\Omega^3\). A finite abstract group is **totally 3-closed** when
every faithful finite permutation representation of it is 3-closed.

## Restricted classification problem

Classify, up to isomorphism, every nonabelian simple group

\[
S=\operatorname{PSL}_3(q)
\]

that is totally 3-closed, for every prime power \(q\) for which
\(\operatorname{PSL}_3(q)\) is nonabelian simple.

This run concerns the projective dimension-three family only. Do not schedule
research on \(\operatorname{PSL}_n(q)\) with \(n\neq3\), or on unitary,
symplectic, orthogonal, exceptional, twisted, Suzuki, Ree, or alternating
families, except to use the exceptional isomorphism
\(\operatorname{PSL}_3(2)\cong\operatorname{PSL}_2(7)\).

The final result must be an if-and-only-if theorem. It must:

1. prove total 3-closure for every surviving \(\operatorname{PSL}_3(q)\) in
   every faithful finite permutation representation;
2. exclude every other simple \(\operatorname{PSL}_3(q)\) by a uniform theorem
   or an explicit faithful action with strictly larger 3-closure;
3. cover all prime powers, simplicity exceptions, and the exceptional
   isomorphism at \(q=2\);
4. distinguish uniform arguments from bounded computations;
5. give exact references, theorem numbers, and checked hypothesis translations
   for every maximal-subgroup, base-size, orbit, or classification theorem.

## Certified premises from the current PSL ledger

The supervising mathematician authorizes the following integrated results as
fixed premises. Preserve their exact scope and import their certified dependency
closure rather than reproving them.

1. **Two-orbit reduction.** For a finite nonabelian simple group \(S\), total
   3-closure is equivalent to 3-closedness of every diagonal action on
   \(S/H\sqcup S/K\), for all proper \(H,K<S\), with repetition allowed.
2. **Projective outer obstruction.** If \(q=p^f\) with \(f>1\), or if
   \(\gcd(3,q-1)>1\), then \(\operatorname{PSL}_3(q)\) is not totally
   3-closed; its natural projective-point action has a proper semilinear or
   diagonal 3-closure overgroup.
3. **The \(q=2\) survivor.**
   \(\operatorname{PSL}_3(2)\cong\operatorname{PSL}_2(7)\) is totally
   3-closed.
4. **Base-two synchronization.** A two-constituent diagonal action is
   3-closed when its constituent actions are 3-closed and one constituent has
   a base of size at most two.
5. **Rank-three scalar-fiber rigidity.** If \(p\) is prime and
   \(\gcd(3,p-1)=1\), every action of \(\operatorname{PSL}_3(p)\) on
   \((\mathbb F_p^3\setminus\{0\})/C\), for \(C\leq\mathbb F_p^\times\),
   is faithful and 3-closed. Determinant-character twists of the point
   parabolic give the same actions. This is a route obstruction: scalar fibers
   cannot provide a nonclosure witness.
6. **Exact \(\operatorname{PSL}_3(3)\) exceptional-parabolic theorem E3.**
   For a point stabilizer \(P\), the exceptional family
   \(\mathcal E(P)=\{H<P:H\cap H^g\neq1\text{ for every }g\in G\}\)
   consists of 24 subgroups in six \(G\)-classes, represented by orders
   \(48,54,72,108,144,216\). Every corresponding transitive action is
   3-closed, as is every dual line-parabolic action.
7. **Exact exceptional mixed-pair theorem M3.** Every diagonal action on
   \(G/H\sqcup G/K\), with \(H,K\) in those six exceptional point classes or
   their dual line classes, is 3-closed.

The unresolved prime-field parameters are therefore

\[
p=3\quad\text{or}\quad p\equiv2\pmod3.
\]

Do not treat the failure of a proposed graph, scalar-fiber, flag, or coset
witness as evidence of total 3-closure. Conversely, do not declare a group
non-totally-3-closed without an explicit faithful action and a proved proper
triple-orbit preserver.

## Research order

### Priority 1: finish \(\operatorname{PSL}_3(3)\)

Attempt the shortest complete two-orbit proof now. The decisive obligations are:

1. certify an exact complete maximal-subgroup list for
   \(\operatorname{PSL}_3(3)\), with source theorem or reproducible bounded
   computation and checked fusion/conjugacy information;
2. prove that the point and line parabolics, Singer normalizer, conic
   stabilizer, and every proper subgroup below them exhaust all proper
   subgroups;
3. assemble every pair \(G/H\sqcup G/K\), explicitly including pairs involving
   the point or line parabolic itself, exceptional refinements, repeated
   constituents, Singer-normalizer descendants, and conic-stabilizer
   descendants;
4. either integrate the resulting total-3-closure theorem or exhibit a concrete
   counterexample pair action.

### Priority 2: classify residual prime parameters uniformly

For primes \(p\equiv2\pmod3\), decide whether
\(\operatorname{PSL}_3(p)\) is totally 3-closed. Seek one theorem-level
architecture that scales with \(p\):

- a maximal-subgroup/base-size reduction plus exact synchronization of the
  high-base constituents;
- a genuinely nonnormalizing two-coset witness satisfying all mixed triple
  conditions;
- a graph-stable nonparabolic action with verified quotient-surjectivity for
  every ordered triple;
- or a structural invariant forcing every faithful action to be 3-closed.

The scalar-fiber route is closed and must not be repeated without a genuinely
new action. Test small primes \(p=5,11,17\) only as bounded probes designed to
distinguish competing uniform conjectures; do not extrapolate finite output.

### Parallel branches

When three branches are available, use genuinely different philosophies:

1. **finite closure assembly:** close \(\operatorname{PSL}_3(3)\) with an exact
   maximal-subgroup interface and a complete two-orbit proof;
2. **uniform structural branch:** attack all primes \(p\equiv2\pmod3\) through
   maximal subgroups, bases, factorizations, or a conceptual invariant;
3. **adversarial/literature/CAS branch:** search for a full-hypothesis witness
   or counterexample pattern at \(p=5,11,17\), and adapt exact cited theorems
   rather than performing a broad survey.

Run full-proof-first. Periodically draft the shortest complete classification
proof and mark each unsupported sentence. Suppress all binary and higher-rank
branches as out of scope; retain their certified results only as archived
background.
- `claim_import_psl27_totally_3closed` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
- `claim_import_psln_projective_nonclosure` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or diagonal outer automorphism.
- `claim_import_two_orbit_reduction` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
- `claim_root_a5_degree3_orthogonal_internal_rev1059` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=2: Let p > 5 be prime with p congruent to 2 modulo 3. Every subgroup A of SL_3(p) isomorphic to A_5 is contained in an SL_3(p)-conjugate of SO_3(p).
- `claim_root_core_overlap_frame_gluing_rev1234` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p>=5 be prime with p congruent to 2 modulo 3, G=SL_3(p), P a point or line parabolic, H<=P, and X_x the fibers of H backslash G -> P backslash G. Put N_x=core_(P_x)(H_x). If H does not contain P^0, then N_x intersect N_y=1 for all distinct x,y; if H contains P^0, every determinant-neutral fiberwise permutation is pointwise trivial. Consequently, any quotient-fixing permutation whose restrictions on the three complete fibers of every projective frame are induced by one frame-stabilizer element is the identity.
- `claim_root_general_multiseparator_criterion_rev148` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let a finite group X act transitively on Lambda. Choose a0,a1,a2 in Lambda and, for {i,j,k}={0,1,2}, put K_i=X_{a_j,a_k}. If for every k_i in K_i minus {1}, the subgroup <k_1^{-1}k_0,k_2^{-1}k_0> is not contained in any X-conjugate of X_{a0}, then X is 3-closed on Lambda.
- `claim_root_levi_split_torus_separator_rev1210` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For every prime p≥5, every subgroup M≤GL_2(p) not containing SL_2(p), and every split maximal torus D≤GL_2(p), there exists g∈GL_2(p) such that D∩M^g=D∩core_{GL_2(p)}(M). Equivalently, the projective image of M has an ordered pair of distinct points of P^1(F_p) whose pointwise stabilizer is its projective core.
- `claim_root_mixed_anchor_code_pair_criterion_rev179` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G≤Sym(Λ) be finite. Choose a_0,a_1,a_2∈Λ and, for {i,j,k}={0,1,2}, put K_i=G_{a_j,a_k}. If K_0x∩K_1x∩K_2x={x} for every x∈Λ, then G^(3)=G. If Λ is the disjoint union of two equivariantly isomorphic copies and the anchors lie in the first copy, it suffices to verify the singleton condition on that copy. Consequently, for G=PGL_3(5)=PSL_3(5) and H=Q⋊<[[0,1],[1,0]],[[0,1],[4,1]]> in the audited degree-1240 action, the diagonal action on G/H disjoint-union G/H is 3-closed.
- `claim_root_p5_remote_anchor_inequality_rev522` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PGL_3(5)=SL_3(5), P=Q⋊GL_2(5), H=Q⋊<[[0,1],[1,0]],[[0,1],[4,1]]>, and Ω=G/H. For every fibre D of Ω→G/P there exist distinct x,y∈Ω\D such that |G_{x,y}|=4; consequently |G_{x,y}|<20.
- `claim_root_primitive_nonorthogonal_bloom_rev1049` `untested` `active` `main_trunk` maturity=routed root_distance=1: Let p≥5 be prime with p congruent to 2 modulo 3, and let T<SL_3(p) be a proper nonabelian simple subgroup. If T is not contained in any conjugate of an orthogonal subgroup SO_3(p), then T is isomorphic to PSL_2(7), and p^3 is congruent to 1 modulo 7. Consequently every absolutely irreducible primitive nonorthogonal T satisfies the previously selected bridge (P).
- `claim_root_residual_nonsplit_torus_normalizer_3closed_rev100` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For every prime p>=5 with p congruent to 2 modulo 3, let G=PSL_3(p), let Q be the unipotent radical of a point parabolic P, and embed GammaL_1(p^2) as the normalizer of a nonsplit torus in the Levi factor GL_2(p) of P. If H_p=Q semidirect GammaL_1(p^2), then the faithful coset action of G on G/H_p is 3-closed.

## Active Proof Debts

- `debt_inference_root_p5_direct_singleton_replay_rev164` `blocking` on `inference_claim_root_p5_dihedral_levi_coset_action_3closed_rev123`: Independently certify the direct p=5 separator premise for explicit matrices g_1,g_2: construct G=PGL_3(5), H=Q⋊<A,B>, Omega=G/H, compute K_i=G_{a_j,a_k}, and verify K_0x∩K_1x∩K_2x={x} for every one of the 1240 cosets. The certificate must include executable source, GAP/package versions, anchor matrices and indices, K_i generators and orders, and either a regenerable collision-free check or an explicit collision. The false two-row D-nonsubconjugacy table and an unsupported aggregate histogram are not acceptable substitutes.
- `debt_inference_root_p5_coordinate_separator_replay_rev589` `blocking` on `inference_claim_root_p5_block_kernel_repair_rev285`: For G=SL_3(5), H=Q⋊<A,B>, and the explicit coordinate anchors H,s_12H,s_13H in art_researcher_root_p5_coordinate_separator_compression_rev589, decide the exact separator theorem by checking all 64 inclusions Fix(<k1^-1k0,k2^-1k0>)⊆Fix(k0).
- `debt_claim_root_c2c3s_p5_mononomial_maximality_rev1168` `blocking` on `claim_root_c2c3s_uniform_base2_descendants_rev1155`: Resolve the p=5 determinant-one monomial maximality collision. Acceptance requires either an explicit strict maximal overgroup M<J<PSL_3(5), with generators, order, and Aschbacher type explaining the omitted row, or an independently reproducible maximality certificate for M together with a corrected exact-source adaptation proving base size two for this p=5 C2 action. A base-size computation alone does not resolve the disputed maximality sentence.
