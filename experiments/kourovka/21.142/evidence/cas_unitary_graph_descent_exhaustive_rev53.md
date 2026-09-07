# Exhaustive finite check of the unitary graph-descent formulas

## Question
The challenged unitary route uses two algebraic assertions after writing a graph-coset automorphism as [A]bar: (i) projective order two can be norm-normalized so that T=B bar is an involution; and (ii) the fixed space of T carries exactly the claimed nondegenerate symmetric or alternating form. The experiment attempted to falsify either assertion before further work on abstract automorphism classification.

## Finite scope and method
Using an explicit standard-library implementation of F_4=F_2[u]/(u^2+u+1) and F_9=F_3[u]/(u^2+1), the computation exhaustively enumerated all 4^9 matrices in Mat_3(F_4) and all 9^4 matrices in Mat_2(F_9). For every invertible unitary similitude A satisfying A bar(A)=lambda I, it found c with c bar(c)=lambda^{-1}, formed B=cA, checked B bar(B)=I, computed Fix(B bar) as an F_q-nullspace, and computed the Gram matrix of the descended form. It also directly checked bar(g)=(g^{-1})^T for every unitary g in these standard models.

## Output
For (q,n)=(2,3): 262144 matrices were enumerated, 181440 were invertible, 648 were unitary similitudes, and 108 represented projective graph involutions. All 108 normalized successfully; every fixed space had dimension 3 and a nondegenerate symmetric F_2-form. There were no graph-identity or descent failures.

For (q,n)=(3,2): 6561 matrices were enumerated, 5760 were invertible, 192 were unitary similitudes, and 80 represented projective graph involutions. All 80 normalized successfully; 72 yielded a nondegenerate symmetric fixed form and 8 yielded a nondegenerate alternating fixed form. There were no graph-identity or descent failures. One alternating example, in the basis 1,u with u^2=-1, is B=[[0,1+u],[2+2u,0]], for which B bar(B)=I and the unitary multiplier is -1.

## Mathematical conclusion
No counterexample occurs in either exhaustive finite scope. More importantly, the calculation separates the route into two representations: the semilinear matrix/fixed-space calculation behaves exactly as claimed, whereas the computation cannot address whether every abstract automorphism of PSU is represented semilinearly. Thus the next proof move is not another repair of graph descent; it is the strictly narrower building-recognition theorem isolated in the companion proof dossier. This finite calculation is sanity evidence only and does not certify any infinite statement.
