# Exact 3-closedness of the rank-three scalar-fiber actions

## Local theorem

Let p be prime with gcd(3,p-1)=1, let V=F_p^3, let C be any subgroup of F_p^*, and put

Ω_C=(V minus {0})/C,

where C acts by scalar multiplication. Then S=SL_3(p)=PSL_3(p) acts faithfully and 3-closedly on Ω_C.

Consequently no action obtained by retaining any cyclic amount of scalar information above the projective points can extend the central-vector nonclosure construction to the residual rank-three family.

## Attack 1: direct fiber-label proof

### Faithfulness

If A in SL_3(p) fixes every C-orbit, then for every nonzero v there is c_v in C with Av=c_vv. Applying linearity to independent u,v and u+v gives c_u=c_v=c_(u+v). Hence A=λI. Since det(A)=λ^3=1 and gcd(3,p-1)=1, λ=1. Thus the action is faithful.

### The projective block system

Two points Cv,Cw of Ω_C lie in the same projective block exactly when w is a nonzero scalar multiple of v. This relation is a union of S-orbits on ordered pairs. Since every element of S^(3) preserves all pair orbits by applying it to triples of the form (x,y,y), every π in S^(3) permutes the projective blocks. It therefore induces a permutation bar(π) of PG(2,p).

For any ordered triple of projective blocks, choose one point of Ω_C above each block. Preservation of the S-orbit of the lifted triple shows that bar(π) sends the block triple into its S-orbit. Hence bar(π) lies in the 3-closure of the projective action.

### Projective rigidity in rank three

Because gcd(3,p-1)=1, PGL_3(p)=PSL_3(p)=S. Its orbits on ordered projective triples are determined by the equality pattern and, for three distinct points, by whether the points are collinear. Indeed, ordered noncollinear triples are projective frames, while a line stabilizer induces PGL_2(p), which is transitive on ordered triples of distinct points of that line.

Thus a member of the projective 3-closure preserves collinearity. Here no external theorem is needed: compose such a collinearity-preserving bijection with a projectivity so that it fixes the frame [e_1], [e_2], [e_3], [e_1+e_2+e_3]. Its restrictions to the three coordinate lines have the form

[e_i+t e_j] maps to [e_i+φ(t)e_j]

for one bijection φ of F_p fixing 0 and 1. Intersections of the standard affine constructions for addition and multiplication give φ(x+y)=φ(x)+φ(y) and φ(xy)=φ(x)φ(y). Since F_p is a prime field, φ is the identity. The normalized bijection is therefore the identity, so the full projective collinearity group is PGL_3(p)=S. Hence bar(π) is induced by some s in S.

Replace π by s^(-1)π. It now fixes every projective block setwise.

### The noncollinear product invariant

For each projective point L choose a representative v_L. Write

A=F_p^*/C.

The points over L are uniquely written as C a v_L with a in A. Since π fixes the blocks, it induces a bijection f_L:A to A on each block.

Let L_1,L_2,L_3 be noncollinear. Their chosen representatives form a basis. An element of S fixing all three projective points is diagonal in this basis, with eigenvalues d_1,d_2,d_3 satisfying d_1d_2d_3=1. It carries the label triple (a_1,a_2,a_3) to (b_1,b_2,b_3) precisely when

(b_1a_1^(-1))(b_2a_2^(-1))(b_3a_3^(-1))=1 in A.

Therefore the product a_1a_2a_3 in A is the complete S-orbit invariant for triples lying over this fixed noncollinear projective triple. Since π preserves each triple orbit,

f_(L_1)(a_1) f_(L_2)(a_2) f_(L_3)(a_3)=a_1a_2a_3

for all a_1,a_2,a_3 in A.

Varying one label at a time shows that f_L(a)=u_La for some u_L in A. Moreover

u_(L_1)u_(L_2)u_(L_3)=1

for every noncollinear triple. Given any projective points L and M, choose a line containing neither and two distinct points N,R on that line. Both (L,N,R) and (M,N,R) are noncollinear, so the two product equations give u_L=u_M. Thus all u_L equal one element u. A noncollinear triple then gives u^3=1. The order of A divides p-1 and is coprime to 3, so u=1. Hence every f_L is the identity, π is the identity after normalization, and the original π belongs to S. This proves S^(3)=S.

## Attack 2: independent determinant-intersection cross-check

Fix L=<e_1>, let P=G_L in G=GL_3(p), and let a(g) be the scalar induced by g on L. For an integer e define

H_(e,C)={g in P: a(g)det(g)^(-e) lies in C}.

The determinant of H_(e,C) is all of F_p^*: for a prescribed δ choose a=δ^e and a two-dimensional block of determinant δ/a. Hence G=SH_(e,C). Furthermore

H_(e,C) intersection S={s in S_L: a(s) lies in C},

independently of e, so every coset action G/H_(e,C), restricted to S, is exactly Ω_C.

The kernel K of G on G/H_(e,C) is contained in the scalar center because H_(e,C) is contained in a point parabolic. Directly,

K={λI: λ^(1-3e) lies in C}.

Suppose a scalar z=λI not in K could be locally matched by S on the triple of cosets whose overlying projective points are the three coordinate lines. Then z s^(-1) would lie in the intersection of the three corresponding conjugates of H_(e,C) for some s in S. This intersection is diagonal. Writing its diagonal entries as b_i and its determinant as δ=λ^3, the three membership conditions give

b_i δ^(-e) in C for i=1,2,3.

Multiplication yields δ^(1-3e) in C, hence λ^(3(1-3e)) in C. Cubing is injective on F_p^*/C because its order divides p-1 and is coprime to 3. Therefore λ^(1-3e) lies in C, contrary to z not in K. Thus every nontrivial induced scalar extension is separated by this one basis triple. This independently confirms that twisting the parabolic character cannot evade the direct fiber-label theorem. The dual hyperplane-fiber construction has the identical argument with three independent covectors.

## Sanity checks and attempted counterexamples

For p=3 and C={1}, every block has two labels. The tempting simultaneous sign flip has multiplier u of order two, and a noncollinear triple changes its label product by u^3=u, so it is detected. For p=5, every quotient F_5^*/C again has order coprime to three, and the same calculation excludes every nontrivial constant label multiplier. The proof also covers C=F_p^*, where Ω_C is the projective action.

The strongest repairable near miss was the central-vector construction in dimension three. In dimensions at least four, three tested vectors leave a complement on which one corrects the determinant. In dimension three a noncollinear triple is a basis; the missing complement becomes the product invariant above. This converts the boundary observation into an exact obstruction theorem. The separate mutual-orbital maximal-factorization route remains abandoned because its manifest-listed PSL_6(2) obstruction attacks its full hypotheses.

## Root proof spine

1. Certified rank-one classification plus the certified projective outer-witness theorem reduces the higher-rank problem to prime p, n at least 3, and gcd(n,p-1)=1.
2. The central-vector theorem excludes every residual case with n at least 4 and p greater than 2.
3. The present theorem proves that every natural scalar-fiber action Ω_C of residual PSL_3(p) is 3-closed; hence neither the original central-vector action nor any cyclic scalar quotient or character twist can supply the missing rank-three witness.
4. The single remaining theorem-level gap is the narrowed residual theorem R*: decide the residual rank-three groups by actions outside this scalar-fiber parabolic family and decide the binary family PSL_n(2), n at least 5. A smallest discriminating instance is PSL_3(3): total 3-closure there would refute the current universal exclusion conjecture, whereas one explicit two-orbit witness would identify a new architecture.

Dependencies are certified reductions -> central-vector exclusion -> present scalar-fiber obstruction -> R*.

## Self-check

The proof checks the action kernel, repeated points through the projective-block reduction, all dependent and nondependent projective triples, and arbitrary subgroups C. The label calculation uses only noncollinear triples, whose representatives are bases. The step u^3=1 uses exactly gcd(3,p-1)=1. The character-twist calculation checks the action kernel rather than confusing an abstract GL overgroup with a proper permutation overgroup. No assertion is made about arbitrary subgroups inside a parabolic, nonparabolic actions, binary ranks at least five, or total 3-closure of PSL_3(p).
