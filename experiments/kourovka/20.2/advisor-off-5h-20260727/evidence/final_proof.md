# A nonabelian simple group of Lie type that is totally 3-closed

## Theorem

There exists a nonabelian simple group of Lie type that is totally 3-closed. More precisely, the group \(G=\operatorname{PSL}_2(7)\), of Lie type \(A_1(7)\), is totally 3-closed.

Thus the stronger, explicit-witness statement proved below answers Problem 20.2 affirmatively.

## Finite certificate

We first record the exact finite information used in the proof. The standard permutation realization of \(G=\operatorname{PSL}_2(7)\) has order \(168\). GAP 4.16.0 enumerates exactly fourteen conjugacy classes of proper subgroups \(H<G\). For each representative it constructs the coset action \(P_H\) on \(G/H\).

For any permutation group \(P\), one has \(P^{(3)}\leq P^{(2)}\): a permutation preserving every orbit on ordered triples also preserves every orbit on ordered pairs, as an ordered pair \((a,b)\) may be encoded by the repeated-coordinate triple \((a,b,b)\). The certificate therefore begins with the exact group \(P_H^{(2)}\). It then lists the \(P_H\)-orbits on ordered triples and successively intersects \(P_H^{(2)}\) with their setwise stabilizers. The resulting intersection is precisely \(P_H^{(3)}\), because it is the full subgroup preserving every \(P_H\)-orbit on ordered triples. The computation gives the following table.

| Index | Structure of \(H\) | Degree | \(|P_H^{(2)}|\) | \(|P_H^{(3)}|\) |
|---:|:---|---:|---:|---:|
| 1 | \(S_4\) | 7 | 5040 | 168 |
| 2 | \(S_4\) | 7 | 5040 | 168 |
| 3 | \(C_7:C_3\) | 8 | 40320 | 168 |
| 4 | \(A_4\) | 14 | 645120 | 168 |
| 5 | \(A_4\) | 14 | 645120 | 168 |
| 6 | \(D_8\) | 21 | 168 | 168 |
| 7 | \(C_7\) | 24 | 336 | 168 |
| 8 | \(S_3\) | 28 | 168 | 168 |
| 9 | \(C_2\times C_2\) | 42 | 168 | 168 |
| 10 | \(C_2\times C_2\) | 42 | 168 | 168 |
| 11 | \(C_4\) | 42 | 168 | 168 |
| 12 | \(C_3\) | 56 | 168 | 168 |
| 13 | \(C_2\) | 84 | 168 | 168 |
| 14 | \(1\) | 168 | 168 | 168 |

Every coset image has order \(168\), so the table proves that all fourteen transitive coset actions are 3-closed.

The certificate also treats every unordered pair of the fourteen action types, including equal types. There are \(14\cdot15/2=105\) such pairs. For a pair with coset images on sets \(X_i\) and \(X_j\), let \(D\cong G\) be the diagonal action on the disjoint union \(X_i\sqcup X_j\). The computation fixes a nonidentity element \(x\in G\), forms the permutation \(q=(1,x)\), and searches the finite sets of mixed triples of patterns \(X_i\times X_j\times X_j\) and \(X_i\times X_i\times X_j\). In every one of the 105 cases it produces a triple \(t\) for which \(t\) and \(t^q\) belong to distinct \(D\)-orbits. Consequently \(q\notin D^{(3)}\) for every pair. The exact GAP code, the complete local output, and all 105 separating triples are contained in the certified finite-computation report listed in the References section.

## Proof

Let \(\Omega\) be an arbitrary finite faithful \(G\)-set, and identify \(G\) with its image in \(\operatorname{Sym}(\Omega)\). Put \(K=G^{(3)}\). We prove that \(K=G\).

First, every element of \(K\) preserves each \(G\)-orbit on \(\Omega\) setwise. Indeed, the \(G\)-orbit of a constant triple \((a,a,a)\) consists exactly of the constant triples \((b,b,b)\) with \(b\in a^G\). Since elements of \(K\) preserve every \(G\)-orbit on ordered triples, they preserve the orbit \(a^G\). In particular, every singleton orbit is fixed pointwise by \(K\).

Let \(\Delta\) be a non-singleton \(G\)-orbit and let \(H\) be the stabilizer of one of its points. Then \(H<G\), and \(\Delta\) is equivalent to the coset action on \(G/H\). The kernel of this action is the core of \(H\), hence a normal subgroup of the simple group \(G\). It cannot be all of \(G\), because \(H\) is proper, so it is trivial. Thus every non-singleton constituent is faithful.

Restricting triples to \(\Delta^3\) shows that the restriction of \(K\) to \(\Delta\) lies in the 3-closure of the corresponding coset image. The finite certificate proves that this local 3-closure is the image of \(G\) itself. Therefore, for each non-singleton orbit \(\Delta\) and each \(s\in K\), there is a unique element \(g_\Delta\in G\) whose action on \(\Delta\) agrees with that of \(s\). Uniqueness follows from faithfulness of the constituent.

We next show that these elements are independent of \(\Delta\). We use the following elementary diagonal lemma. If a subgroup \(L\leq G\times G\) contains the diagonal subgroup
\[
\operatorname{Diag}(G)=\{(g,g):g\in G\},
\]
then either \(L=\operatorname{Diag}(G)\) or \(L=G\times G\). To prove this, define
\[
N=\{y\in G:(1,y)\in L\}.
\]
Conjugation by the diagonal shows that \(N\trianglelefteq G\). Since \(G\) is simple, either \(N=1\) or \(N=G\). If \(N=1\), multiplying an arbitrary \((a,b)\in L\) by \((a^{-1},a^{-1})\) shows that \(a=b\), so \(L\) is diagonal. If \(N=G\), then \(1\times G\leq L\), and this subgroup together with the diagonal generates \(G\times G\).

Now choose two non-singleton orbits \(\Delta\) and \(\Gamma\), allowing them to have the same constituent type. Consider the 3-closure of the diagonal action of \(G\) on \(\Delta\sqcup\Gamma\). Constant triples force it to preserve both constituents, while local 3-closedness embeds it in \(G\times G\). It contains the diagonal copy of \(G\), so the diagonal lemma says that it is either diagonal or the full product. After equivariant identification with the corresponding representatives in the finite certificate, the separating mixed triple shows that the element \((1,x)\) is absent. The full-product alternative is therefore impossible, and the pairwise 3-closure is diagonal. This conclusion is unchanged by replacing either constituent by an isomorphic copy or by conjugating its point stabilizer.

The restriction of \(s\in K\) to \(\Delta\sqcup\Gamma\) belongs to this pairwise 3-closure. Hence \((g_\Delta,g_\Gamma)\) is diagonal and \(g_\Delta=g_\Gamma\). Since the pair was arbitrary, there is one element \(g\in G\) that agrees with \(s\) on every non-singleton orbit. Both \(s\) and \(g\) fix every singleton orbit, so they agree on all of \(\Omega\). Thus \(s=g\), proving \(K\leq G\). The reverse inclusion follows directly from the definition of closure, and consequently \(G^{(3)}=G\).

The faithful finite \(G\)-set \(\Omega\) was arbitrary. Hence \(\operatorname{PSL}_2(7)\) is totally 3-closed. This group is nonabelian simple and is a group of Lie type \(A_1(7)\), so it supplies the required example and answers Problem 20.2 affirmatively.

## References

External reference list: empty. This proof was written by the Albilich writer from the following internal artifacts.

- “Repaired proof dossier for total 3-closure of \(\operatorname{PSL}_2(7)\),” artifact `art_psl2_7_total3_repaired_proof_dossier_r25`, researcher. Supports the reduction to coset constituents, the diagonal lemma, synchronization, and final assembly.
- “Decisive finite experiment for \(G=\operatorname{PSL}_2(7)\),” artifact `art_psl2_7_full_subgroup_cas_r25`, researcher. Supplies the exact GAP 4.16.0 code, all fourteen local 3-closure computations, and all 105 mixed-pair certificates.
- “Strict verification of the repaired \(\operatorname{PSL}_2(7)\) route,” artifact `art_verification_psl2_7_total3_correct_r27`, strict informal verifier. Certifies that the sufficient route is correct with no gaps.
- “Integration of the \(\operatorname{PSL}_2(7)\) route,” artifact `art_integration_psl2_7_total3_root_r29`, integration verifier. Certifies that the explicit witness proves the root existential statement.
