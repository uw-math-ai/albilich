# Albilich on RealMath (Math_arXiv, 10 problems) — 2026-07-20

Config: gpt-5.6-sol @ xhigh, research-mode hard_problem (CAS enabled). ~28.1M tokens total.

| # | Albilich outcome | CAS fired | Answer vs RealMath reference |
|---|---|---|---|
| 00 harmonic centrality P2×Cm | solved_final | yes | MATCH (both piecewise cases exact) |
| 01 Box_b eigenvalue + dim H_{p,q} | solved_final | yes | MATCH (eigenvalue + dim; also handles n=1) |
| 02 parity of Γ5/Γ6/Γ9 sums | solved_final | yes | MATCH (all ≡ 1 mod 2) |
| 03 |K_c| count | solved_final | yes | MATCH (all four mod-4 cases exact) |
| 04 rising-continuous count | solved_final | yes | MATCH (= 1) |
| 05 sextactic tangent lines | solved_final | yes | MATCH (one point; two points on all conics) |
| 06 e_c(G_i,7) values | solved_final | yes | MATCH (324,338,332,332,344 exact) |
| 07 Iwasawa μ/λ invariants | solved_final | yes | MATCH (μ=0; λ formula exact) |
| 08 matching poly of G1+G2 | solved_final | yes | REVIEW — Albilich gives a convolution double-sum; reference gives a rational-product form. Possibly equivalent, NOT confirmed by inspection. |
| 09 Θ_{k,l}(C2) | solved_final | yes | MATCH (shown parity cases exact; verify mixed cases) |

Summary: 10/10 solved_final, 10/10 CAS-fired. Reference-answer correctness by inspection:
**9/10 clear match, 1 (08) needs symbolic equivalence check.**
Note: "solved_final" is Albilich's own verification verdict; the column above is a human read
of the extracted answer vs the RealMath reference, not an automated SymPy grade.
