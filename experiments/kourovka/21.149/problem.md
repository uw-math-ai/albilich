# Kourovka Notebook Problem 21.149 (strengthened v45 formulation)

## Exact statement

(V. M. Kopytov, N. Ya. Medvedev). Are there order automorphisms of Dlab groups that are not induced by conjugation by elements of a (possibly bigger) Dlab group?

Proposer: A. V. Zenkov.

Source: *The Kourovka Notebook*, No. 21, arXiv:1401.0300v45, Problem 21.149, PDF page 185.

## Scope and formulation guardrail

This is the strengthened version 45 formulation. An earlier version asked only whether Dlab groups have order automorphisms that are not inner. Aristotle gave a correct affirmative solution to that weaker question. That construction is useful background, but **it does not solve this problem**.

For a positive solution here, construct a specific Dlab group and order automorphism and prove that it is not induced by conjugation by an element of any possibly larger Dlab group in which the original group is embedded in the intended category. It is not enough to show that the automorphism is not conjugation by an element of the original group.

For a negative solution, prove the universal realization assertion matching the exact quantifiers: every order automorphism of every relevant Dlab group is induced by conjugation in some possibly larger Dlab group. State precisely what counts as a Dlab group, an order-preserving embedding into a bigger Dlab group, and induced conjugation.

Do not silently replace "possibly bigger Dlab group" by an arbitrary ordered group, an arbitrary group of order automorphisms, or a completion that has not been proved to be a Dlab group.

## Literature status as of 2026-08-27

Apparently open after exact-phrase and concept searches. The strongest direct evidence is Appendix A of W. van Doorn, E. Judin, P. Monticone, and D. Morrison, *On Some Problems from the Kourovka Notebook*, arXiv:2607.17477v2, which explains the v43/v45 distinction and explicitly says the stronger problem remains open. The companion repository at https://github.com/pitmonticone/Kourovka says the same.

Local references in the adjacent `.refs` directory:

- `van_doorn_judin_monticone_morrison_2026.pdf` — formulation history and the explicit statement that v45 remains open.
- `dlab_1968_simple_ordered_groups.pdf` — foundational definition and structure of Dlab groups.

Additional background:

- N. Ya. Medvedev, *Partial Orders on Dlab Groups*, Algebra and Logic 40 (2001), 75--86, DOI 10.1023/A:1010256703986.
- V. M. Kopytov and N. Ya. Medvedev, *Right-Ordered Groups*, especially the treatment of Chehata and Dlab groups.
- The formal v43 construction in https://github.com/pitmonticone/Kourovka/tree/main/Kourovka/Problem_21_149 is a source of mechanisms and definitions only.

## Research objectives

1. Fix the exact Dlab group model or models relevant to the authors' wording and formalize the ambient-conjugation condition without weakening it.
2. Analyze the known v43 outer order automorphism and determine whether it can be realized by conjugation after a Dlab-group enlargement. If it always embeds, identify and prove the realization theorem; if an obstruction survives every enlargement, make it invariant and prove it.
3. Search structural invariants of Dlab-group embeddings and normalizers: supports, basic characteristics, slope groups, germs at interval endpoints, order cones, and any functorial data preserved under conjugation in an ambient Dlab group.
4. Explore both directions rather than assuming the answer is positive. A counterexample construction must come with a proof against all permitted ambient enlargements. A universal realization construction must verify that the resulting overgroup is genuinely a Dlab group and preserves the intended order structure.
5. Use live web research and CAS or formal computation where informative, but label experiments and heuristics. Computational evidence over finite encodings cannot settle the unrestricted statement without a theorem connecting it to the full class.
6. Produce the strongest rigorous partial result if the root question cannot be closed. Track assumptions and dependencies exactly.

## Mathematical integrity requirements

- Distinguish proved statements, conditional lemmas, heuristic analogies, and computational observations.
- Cite every external theorem with an exact source and verify its hypotheses in the chosen Dlab model.
- Treat the ambient-overgroup quantifier as root-blocking debt until it is fully discharged.
- A complete solution needs a root-closing proof or counterexample, not merely many local lemmas or a successful dashboard state.
- Preserve useful failed constructions and obstruction calculations in writer artifacts.
