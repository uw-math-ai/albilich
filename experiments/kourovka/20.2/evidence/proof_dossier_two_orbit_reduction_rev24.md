# Two-orbit criterion for total 3-closure

## Local theorem

Let S be a finite nonabelian simple group. Then S is totally 3-closed if and only if, for every pair H,K of proper subgroups of S, allowing H=K, the diagonal action of S on the disjoint union S/H ⊔ S/K is 3-closed. It suffices to choose one representative of each conjugacy class of proper subgroups.

## Closure membership

For an S-set X and a permutation σ of X,

σ ∈ S^(3) if and only if, for every a=(a1,a2,a3)∈X³, there is an element s=s(a)∈S such that a^σ=a^s.

This is the elementwise form of preserving every S-orbit on X³.

## Orbit-restriction lemma

Suppose X is an arbitrary finite S-set and σ∈S^(3). Every S-orbit Y on points is preserved setwise by σ: for y∈Y, applying the closure condition to (y,y,y) shows that σ(y)∈Y. If U is a union of point-orbits, then σ|U lies in the 3-closure of the restricted diagonal action on U, since the closure condition may be applied to every triple in U³.

Every non-singleton point-orbit of a simple group S is faithful. Indeed, its kernel is normal in S; it cannot equal S because the orbit is nontrivial, so it is trivial. Such an orbit is isomorphic to S/H for a proper subgroup H. A singleton orbit is fixed pointwise by every element of S^(3), because its diagonal triple is itself a singleton S-orbit.

## Double-copy lifting lemma

Let Y be a transitive faithful S-set and let τ∈S_Y^(3). On two tagged copies Y_1⊔Y_2 define τ̂ by applying τ on both copies. Then τ̂ belongs to the 3-closure of the diagonal S-action on Y_1⊔Y_2.

To see this, take a tagged triple ((y1,i1),(y2,i2),(y3,i3)). Since τ∈S_Y^(3), some s∈S sends the underlying triple (y1,y2,y3) to (τ(y1),τ(y2),τ(y3)). The diagonal action of the same s preserves the copy tags and therefore sends the tagged triple to its τ̂-image.

## Proof of the criterion

Necessity is immediate. Each action on S/H⊔S/K is faithful, because each nontrivial coset action of the simple group S is faithful, and total 3-closure applies to every faithful action.

Conversely, assume every indicated two-orbit action is 3-closed. Let X be any faithful finite S-set and let σ∈S_X^(3). Decompose X into its singleton orbits and its nontrivial orbits X_1,…,X_r. The singleton orbits are fixed pointwise by σ, and r≥1 because X is faithful.

If r=1, the restriction τ=σ|X_1 lies in S_{X_1}^(3). By the double-copy lifting lemma, τ̂ lies in the 3-closure of X_1⊔X_1. The assumed 3-closedness of this two-copy action gives an s∈S inducing τ on X_1. Thus σ is induced by s on all of X.

Suppose r≥2. Fix X_1. For each j>1, the orbit-restriction lemma places σ|X_1⊔X_j in the 3-closure of the diagonal action on X_1⊔X_j. By hypothesis there is s_j∈S inducing σ on both components. All s_j induce the same permutation σ|X_1. Since the action on X_1 is faithful, s_j=s_k for all j,k. Their common value s therefore induces σ on every nontrivial orbit, while both s and σ fix every singleton orbit. Hence σ=s∈S. Thus the original action is 3-closed, proving that S is totally 3-closed.

Conjugating H or K merely replaces the associated coset action by a permutation-isomorphic action, so subgroup-conjugacy representatives suffice.

## Consequence for PSL(2,7)

The manifest evidence obstruction_psl27_low_degree_cosets_rev16 reports that all eight transitive coset actions of degree at most 32 are individually 3-closed. Consequently the advisor's proposed existence statement in that bounded scope has no witness and the single-orbit route should not be retried. That computation does not decide total 3-closure, but the theorem above supplies an exact finite replacement: enumerate all conjugacy classes of proper subgroups H,K of PSL(2,7), including the trivial subgroup and pairs with repetition, and compute the exact 3-closure on PSL(2,7)/H ⊔ PSL(2,7)/K. If every such closure is PSL(2,7), then PSL(2,7) is totally 3-closed and gives a positive answer to the root question. One larger closure gives a faithful counterexample action and excludes PSL(2,7).

## Short proof spine

1. Triple-orbit preservation implies preservation of every point-orbit and restriction to every union of point-orbits.
2. Simplicity implies that every nontrivial point-orbit is faithful.
3. A closure element on one orbit lifts diagonally to the closure on two copies.
4. Closure on every pair of nontrivial orbits forces all component permutations to be induced by one common element of S.

Dependencies: 1→3; 1+2+pairwise 3-closedness→4; 3 handles the one-orbit boundary case; 3+4 imply the criterion.

Exactly one remaining PSL(2,7) gap is the complete proper-subgroup-pair closure computation described above.

## Self-check

The proof checks arbitrary intransitive faithful actions, repeated isomorphic orbits, the case of exactly one nontrivial orbit, fixed points, and the trivial stabilizer H=1. The use of simplicity occurs only in proving faithfulness of every nontrivial orbit and uniqueness of the synchronizing group element. No finite computation is used to claim either total 3-closedness or non-total 3-closedness of PSL(2,7).
