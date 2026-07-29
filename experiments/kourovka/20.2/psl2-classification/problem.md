# Problem 20.2 strengthened target: classify the totally 3-closed simple groups of Lie type

## Definitions

Let \(G\leq \operatorname{Sym}(\Omega)\) be a permutation group on a finite
set \(\Omega\). The **3-closure** \(G^{(3)}\) is the largest subgroup of
\(\operatorname{Sym}(\Omega)\) having the same orbits as \(G\) on the ordered
triples \(\Omega^3\). The action is **3-closed** when \(G^{(3)}=G\). A finite
abstract group is **totally 3-closed** when every faithful finite permutation
representation of it is 3-closed.

## Classification problem

Classify, up to isomorphism, all finite nonabelian simple groups of Lie type
that are totally 3-closed.

The target is an if-and-only-if theorem, not merely another existence proof.
The current confirmed candidates from earlier work are
\(\operatorname{PSL}_2(7)\) and \(\operatorname{PSL}_2(11)\). Determine
whether this list is complete. The final result must:

1. prove total 3-closure for every group on the surviving list, for all
   faithful finite permutation representations;
2. exclude every other finite nonabelian simple group of Lie type by a
   rigorous uniform theorem or by an explicit faithful permutation
   representation whose 3-closure is strictly larger;
3. cover classical, exceptional, twisted, Suzuki, and Ree families, all field
   sizes, and all low-rank exceptional isomorphisms without double counting;
4. state precisely which uses of the classification of finite simple groups,
   maximal-subgroup classifications, base-size results, or closure theorems
   are required, with exact citations and checked hypotheses;
5. distinguish proofs for infinite families from bounded CAS evidence. A
   finite computation settles only the explicitly certified finite groups
   unless it is combined with a proved reduction theorem.

Maintain a case ledger throughout the run. Every Lie-type family must end in
exactly one of: positively proved survivor, rigorously excluded family,
explicitly listed finite exceptions still requiring audit, or a precisely
stated unresolved theorem-level obstruction. Do not declare the classification
complete while any family or exceptional parameter remains unaccounted for.

## Permission to use all earlier Problem 20.2 work

For this run, all earlier Albilich and Rethlas work on Problem 20.2 is permitted
as local research evidence. Inspect and reuse the useful proofs, computations,
failed routes, citations, and verifier reports in these repository-relative
locations:

- `agents/generation/results/kourovka/problem_20_2_totally_3_closed_lie_type/phase2/`
- `experiments/kourovka_20_2_totally_3_closed_20260703/`
- `experiments/kourovka_20_2_totally_3_closed_20260703/solution/`
- `experiments/kourovka_20_2_paper_v3_20260714/`

In particular, recover the complete finite certificates and assembly arguments
for \(\operatorname{PSL}_2(7)\) and \(\operatorname{PSL}_2(11)\), as well as
the earlier negative results for projective linear families. Prior artifacts
are evidence, not automatic authority: preserve their provenance, reconcile
conflicts between revisions, rerun decisive computations when reproducibility
is material, and send imported theorem-level claims through the current strict
verification and integration gates.

## Research directions

Use live literature search aggressively but selectively. Relevant starting
points include total \(k\)-closure, relational complexity and binary/ternary
actions, base sizes of primitive actions, automorphisms preserving orbits on
ordered triples, and the maximal-subgroup structure of finite simple groups of
Lie type. Search for exact classification or reduction theorems before
attempting a family-by-family computation.

A useful negative certificate for a group \(S\) consists of a proper subgroup
\(H<S\) and an element of
\(\operatorname{Sym}(S/H)\setminus S\) preserving all \(S\)-orbits on ordered
triples. Natural field, diagonal, graph, or graph-field automorphisms may
provide such witnesses, but their triple-orbit preservation must be proved,
not inferred merely from normalizing \(S\). Multi-orbit faithful actions and
the earlier two-orbit reduction should also be used when a transitive action
does not distinguish a candidate.

For positive candidates, do not infer total 3-closure from the transitive
coset actions alone. The proof must also control coupling between arbitrary
repeated and nonisomorphic transitive constituents and fixed points, as in the
earlier finite-certificate assembly arguments.

Run in full-proof-first mode. Periodically assemble the shortest complete
classification proof and expose the single decisive missing family or theorem.
Prefer a small number of high-leverage, verifier-checkable claims over a large
inventory of weak case labels, while keeping the family ledger exhaustive.
