# Exact parabolic-index experiment for the orthogonal BRK bottleneck

## Decision question
Can maximal defining-characteristic parabolics in the high-rank orthogonal families be recognized merely from their subgroup orders, equivalently from their permutation indices, so that every abstract automorphism is forced to preserve vertex types?

## Computation
No GAP, Sage, or Magma executable was available. Exact integer arithmetic was therefore performed with the Python 3 standard library. For split types B_m and D_m, the index of the maximal parabolic of node i was evaluated from the Weyl-group Poincare quotient P_W(q)/P_{W_i}(q), using P_A_n(q)=product_{j=2}^{n+1}[j]_q, P_B_n(q)=product_{j=1}^n[2j]_q, and P_D_n(q)=[n]_q product_{j=1}^{n-1}[2j]_q, where [d]_q=(q^d-1)/(q-1). The finite sweep covered 5 <= m <= 12 and q in {2,3,4,5,7,8,9}.

The split B_m sweep found persistent collisions: B_5 has equal indices at nodes 3 and 4, B_8 at nodes 5 and 6, and B_11 at nodes 7 and 8, for every tested q. Exact samples are B_5(2): [1023,86955,782595,782595,75735] and B_5(3): [29524,24209680,677871040,677871040,22408960]. In split D_m the only collisions in the entire sweep were the expected terminal pair m-1,m.

The B-family collision is not a numerical accident. If I_i denotes the node-i index, then
I_{i+1}/I_i=[2(m-i)]_q/[i+1]_q.
Since q-integers are strictly increasing in their index, I_i=I_{i+1} exactly when 2(m-i)=i+1. Thus, whenever m=3k+2, nodes i=2k+1 and i+1=2k+2 have identical indices for every prime power q. Consequently their maximal parabolics have identical orders. This gives an infinite analytic obstruction to every order-only recognition strategy; the finite computation merely exposed the pattern.

## Mathematical conclusion
The index/order representation cannot prove intrinsic building recognition, already in the B_m family. The correct replacement is p-local structure. Conditional on the finite Borel-Tits property that every subgroup H with nontrivial O_p(H) lies in a proper parabolic, maximal parabolics are exactly maximal subgroups M with O_p(M) nontrivial. This property is invariant under abstract automorphisms and recovers the unlabelled building using common Sylow-p containment. The next proof move is therefore an exact proof or source certification of that finite Borel-Tits interface, followed by the orthogonal polar-coordinate theorem. Repeating parabolic order calculations cannot close the bottleneck.
