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
