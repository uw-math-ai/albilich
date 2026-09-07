# Partial theorem

Let q=p^f≥4. If f>1, then PSL(2,q) is not totally 3-closed. The same conclusion holds for q=5.

## Proof

Put Ω=P¹(F_q) and G=PSL(2,q) in its faithful projective-line action.

### Case 1: q is even

Here f>1 because q≥4. Every nonzero element of F_q is a square, so PSL(2,q)=PGL(2,q). The latter acts sharply 3-transitively on Ω: there is a unique projectivity carrying any ordered triple of distinct points to any other such triple. Consequently the G-orbits on Ω³ are determined solely by the equality pattern among the three coordinates. These are also exactly the Sym(Ω)-orbits. Hence

G^(3),Ω = Sym(Ω).

Since |Ω|=q+1≥5 and |G|=(q+1)q(q−1)<(q+1)!, this closure is strictly larger than G. Thus G is not 3-closed in this faithful action and is not totally 3-closed.

### Case 2: q is odd and f>1

Let H=PGL(2,q), let T₀=(∞,0,1), and identify H/G with F_q^×/(F_q^×)² via the determinant square class. This is well-defined on projective matrices because multiplying a matrix by a scalar multiplies its determinant by a square.

For every ordered triple T of distinct points there is a unique h_T∈H satisfying T₀^{h_T}=T. Define ε(T) to be the determinant square class of h_T. Since G is the kernel of the determinant-square-class homomorphism H→F_q^×/(F_q^×)², two ordered triples of distinct points lie in the same G-orbit exactly when they have the same value of ε. Thus G has precisely two orbits on ordered triples of distinct points.

Let σ be the permutation of Ω induced by the nontrivial Frobenius automorphism x↦x^p, fixing ∞. It fixes T₀. If T=T₀^h, then T^σ=T₀^{h^σ}, where h^σ is obtained by applying Frobenius to the matrix entries. Hence

ε(T^σ)=[det(h^σ)]=[det(h)^p]=[det(h)]=ε(T),

because every field automorphism preserves the subgroup of squares. Therefore σ preserves each of the two G-orbits on ordered triples of distinct points. The group G is 2-transitive on Ω (the translations x↦x+b already show that a point stabilizer is transitive on the remaining points), so its orbits on triples with repeated coordinates are determined solely by the equality pattern and are also preserved by σ. It follows that σ∈G^(3),Ω.

On the other hand σ∉G. Indeed, σ fixes ∞, 0, and 1, while a projectivity fixing three distinct points is the identity; σ is nonidentity because f>1. Thus G<G^(3),Ω, proving that G is not totally 3-closed.

### Case 3: q=5

The standard isomorphism PSL(2,5)≅A₅ gives a faithful action on five letters. This action is 3-transitive: a permutation carrying one ordered triple of distinct letters to another can, if it is odd, be composed with the transposition of the two unused letters without changing the prescribed triple. Hence A₅ and S₅ have the same orbits on ordered triples, so A₅^(3)=S₅>A₅. Therefore PSL(2,5) is not totally 3-closed.

This proves the partial theorem.

## Source adaptation and comparison

Freedman, Giudici, and Praeger, “Total closure for permutation actions of finite nonabelian simple groups,” Monatshefte für Mathematik (2023), DOI 10.1007/s00605-023-01822-5, arXiv:2206.02347, explicitly identify determining simple groups of closure number 3 as open. Their Corollary 3.3 states: if G is a finite nonabelian simple group and b_maxprim(G) is the maximum base size among its faithful primitive actions, then k(G)≤b_maxprim(G)+1. Its proof reduces an arbitrary faithful action to a primitive action through a maximal block system and then applies Wielandt’s base-size theorem. Their Theorem 1.2 supplies upper bounds k(G)≤7 for exceptional groups of Lie type and dimension-dependent bounds for classical groups. [Published paper](https://doi.org/10.1007/s00605-023-01822-5)

Those results do not themselves refute total 3-closure: base sizes give upper bounds on closure numbers, whereas a negative result requires a faithful action with an explicit element outside G preserving every G-orbit on triples. The projective-line argument above supplies exactly such an element—either all of Sym(Ω) in even characteristic or Frobenius in odd nonprime-field characteristic.

## Independent attacks and failure analysis

1. Base-size attack: the cited reduction was checked in local notation. It is one-directional and cannot prove non-3-closure from a base of size three, so it does not settle the target family.
2. Orbit-invariant attack: replacing base size by the determinant-square-class coloring of ordered projective triples produces an explicit proper element of the 3-closure and proves the stated infinite-family obstruction.
3. Sanity checks: q=4 yields the sharply 3-transitive action of PSL(2,4)≅A₅ on five points; q=9 yields the explicit witness x↦x³; q=5 is handled by the separate five-letter action.

The argument deliberately does not cover PSL(2,p) for odd primes p≥7. In the projective-line action the field automorphism is trivial, while the diagonal coset PGL(2,p)\PSL(2,p) interchanges, rather than fixes, the two G-orbits on distinct ordered triples. Thus that overgroup is not contained in the 3-closure, and a different action or a positive total-closure argument is required.

## Self-check

The projective action is faithful; determinant square class is independent of the matrix representative; triples with repeated coordinates are covered using 2-transitivity; Frobenius preserves rather than merely permutes the two distinct-triple orbits; and Frobenius is proved external to G by its three fixed points. No conclusion is asserted for prime-field PSL(2,p), p≥7, or for higher-rank and exceptional families.
