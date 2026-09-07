# Imported prior Problem 20.2 evidence

- Provenance class: prior_result
- Original source: `experiments/kourovka_20_2_totally_3_closed_20260703/solution/art_writer_root_final_proof_psl211_total3_closed_rev662.md`
- Import note: This is prior mathematical evidence authorized by the user for the new classification run. It must be audited under the current verifier and integration gates before theorem-level use.

# Final Proof: PSL_2(11) is totally 3-closed

## Statement
Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and let \(k \ge 1\). The \(k\)-closure \(G^{(k)}\) of \(G\) is the largest subgroup of \(\operatorname{Sym}(\Omega)\) whose orbits on \(\Omega^k\) coincide with the orbits of \(G\) on \(\Omega^k\). The group \(G\) is \(k\)-closed on \(\Omega\) if \(G^{(k)}=G\). An abstract group \(G\) is totally \(k\)-closed if, for every faithful finite permutation representation of \(G\), the image of \(G\) is \(k\)-closed.

The question is whether there is a nonabelian simple group of Lie type which is totally \(3\)-closed.

## Theorem
The answer is yes. The group \(\operatorname{PSL}_2(11)\) is a nonabelian simple group of Lie type and is totally \(3\)-closed.

## Certified finite certificate
The integrated route uses the following finite certificate for \(G=\operatorname{PSL}_2(11)\). The certificate was computed in SageMath 10.6 with GAP 4.14.0 and then audited in the manifest-listed proof dossiers and verifier reports.

First, GAP enumerates the \(15\) conjugacy classes of proper subgroups of \(G\). For every representative \(H<G\), the right-coset action of \(G\) on \(H\backslash G\) has \(3\)-closure equal to the image of \(G\). Equivalently, every nonfixed transitive coset constituent of \(G\) is \(3\)-closed.

Second, for every unordered pair of proper subgroup classes \((H,K)\), including the repeated case \(H=K\), the certificate tests the relative displacement that can remain after one coset constituent is normalized. There are \(120\) such unordered pairs. In \(114\) pairs the double-coset predicate on ordered cross-pairs forces the relative displacement to be the identity. The only pair-level exceptions are the six class pairs \((10,14)\), \((10,15)\), \((11,13)\), \((12,13)\), \((13,14)\), and \((13,15)\), in the subgroup-class ordering used by the certificate.

Third, for each of those six exceptional pairs, the mixed ordered-triple predicates on products of types \(AAB\) and \(ABB\), and in the later reaudit all coordinate placements of those mixed types, leave exactly one relative displacement, namely the identity. Thus every pair of nonfixed constituents is forced to use the same element of \(G\).

## Proof
Let \(\Omega\) be any faithful finite \(G\)-set, where \(G=\operatorname{PSL}_2(11)\), and let \(x\in G^{(3)}\). By definition, \(x\) preserves every \(G\)-orbit on ordered triples from \(\Omega\).

We first show that \(x\) preserves each point orbit of \(G\). If \(O\) is a \(G\)-orbit and \(\alpha\in O\), then the \(G\)-orbit of the diagonal triple \((\alpha,\alpha,\alpha)\) is precisely the set of all diagonal triples \((\beta,\beta,\beta)\) with \(\beta\in O\). Since \(x\) preserves this triple orbit, \(\alpha^x\) again lies in \(O\). If \(O\) is a fixed point orbit, this diagonal triple orbit is a singleton, so \(x\) fixes that point.

Now let \(O\) be a nonfixed orbit. Then \(O\) is isomorphic to a right-coset action \(H\backslash G\) with \(H<G\). Since \(G\) is simple and \(H\) is proper, the core of \(H\) in \(G\) is trivial, so this transitive constituent is faithful. The restriction of \(x\) to \(O\) preserves the \(G\)-orbits on \(O^3\). By the transitive part of the finite certificate, this restriction is induced by right multiplication by a unique element \(g_O\in G\).

It remains to prove that the elements \(g_O\) are independent of the nonfixed orbit \(O\). Let \(A=H\backslash G\) and \(B=K\backslash G\) be two nonfixed constituents. Suppose that \(x\) acts on them by right multiplication by \(g_A\) and \(g_B\), respectively. Composing with the global diagonal action of \(g_A^{-1}\), we may assume that \(x\) fixes \(A\) and acts on \(B\) by a relative displacement \(d\in G\). The diagonal \(G\)-orbit of an ordered cross-pair \((Ha,Kb)\) is determined by the double coset \(H a b^{-1} K\). Therefore pair-orbit preservation requires the double-coset label of \((Ha,Kb)\) to agree with that of \((Ha,Kbd)\) for all \(a,b\in G\), or equivalently requires the same double-coset labels to be preserved under the left multiplications by conjugates of \(d^{-1}\).

This is exactly the pair predicate in the certificate. For \(114\) of the \(120\) unordered subgroup-class pairs, that predicate leaves only the identity relative displacement, so \(d=1\). For the six exceptional pairs, pair orbits alone do not decide \(d\), but the preservation of mixed triple orbits does. In the same normalization, triples of type \(AAB\) are sent from \((a_1,a_2,b)\) to \((a_1,a_2,bd)\), and triples of type \(ABB\) are sent from \((a,b_1,b_2)\) to \((a,b_1d,b_2d)\). The certified mixed-triple computation says that in each of the six exceptional pairs these orbit labels also leave only the identity relative displacement. Hence \(d=1\) in every case.

Thus \(g_A=g_B\) for every pair of nonfixed constituents, including repeated isomorphic constituents because repeated pairs are included in the \(120\)-pair audit. All nonfixed orbits are therefore acted on by one common element \(g\in G\), while all fixed points are fixed. Consequently \(x\) is exactly the global diagonal action of \(g\) on \(\Omega\). This proves \(G^{(3)}=G\) for the arbitrary faithful finite \(G\)-set \(\Omega\).

Since every faithful finite permutation representation of \(\operatorname{PSL}_2(11)\) is \(3\)-closed, \(\operatorname{PSL}_2(11)\) is totally \(3\)-closed. The group \(\operatorname{PSL}_2(11)\) is a nonabelian simple group of Lie type \(A_1\) over \(\mathbb{F}_{11}\). Therefore there exists a nonabelian simple group of Lie type which is totally \(3\)-closed.

## Certification Status
This proof is written from the integrated root route in manifest revision 662. The writer has not run a new computation or a new verification pass. The mathematical inputs are the manifest-integrated strict informal verification, the integration verifier report, and the listed PSL_2(11) certificate and assembly artifacts.

## References
No external mathematical references are used. The reference list is empty for external mathematics, and this report was written by the Albilich writer from internal artifacts.

Internal artifacts: art_researcher_root_psl211_total3_closed_cas_rev361, CAS experiment report by researcher; art_researcher_root_psl211_certificate_assembly_dossier_rev451, proof dossier by researcher; art_researcher_root_psl211_disjoint_union_assembly_predicate_repair_rev461, proof dossier by researcher; art_researcher_root_psl211_exception_mixed_triple_reaudit_cas_rev534, CAS experiment report by researcher; art_researcher_root_psl211_certificate_semantics_reaudit_cas_rev616, CAS experiment report by researcher; art_strict_informal_verifier_root_psl211_total3_closed_verification_rev641, strict informal verifier report; art_integration_verifier_root_psl211_integration_report_rev660, integration verifier report.
