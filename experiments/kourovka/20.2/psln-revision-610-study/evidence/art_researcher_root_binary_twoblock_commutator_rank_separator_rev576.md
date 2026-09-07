# Exact local result

For every d >= 2, put V = F_2^(2d), G = GL(V), and let P be the projection associated with the standard decomposition V = A direct-sum B, where dim A = dim B = d. Let H be the stabilizer of the unordered pair {A,B}; thus H = GL_d(2) wr Sym(2). The graph automorphism alpha(g) = g^(-T) stabilizes H and induces a permutation of G/H.

We construct explicit x_d,y_d in G for which no h in H simultaneously satisfies

alpha(x_d)H = h x_d H,   alpha(y_d)H = h y_d H.

Consequently alpha does not preserve every G-orbit on ordered triples of G/H. This decides the equal-block C2 test negatively for every d.

# Representation switch

A coset gH is the unordered decomposition represented by the pair of rank-d idempotents

{gPg^(-1), I + gPg^(-1)}.

The transpose image alpha(g)H is represented by

{(gPg^(-1))^T, I + (gPg^(-1))^T}.

Thus the simultaneous-coset condition is equivalent to simultaneous conjugacy of a triple of idempotents to its transpose, with each idempotent allowed to be replaced independently by its complement. This makes a complement-invariant matrix word the appropriate separator.

# Attack 1: why the shortest trace invariant fails

The trilinear expression

delta(P,Q,R) = tr(PQR) + tr(PRQ)

is unchanged when any one of P,Q,R is replaced by its complement. However transposition merely interchanges its two summands, so delta(P^T,Q^T,R^T) = delta(P,Q,R). Hence the natural degree-three trace attack cannot separate a triple from its dual.

# Attack 2: an orientation-sensitive rank invariant

For endomorphisms U,W write [U,W] = UW + WU, since the field has characteristic two. Define

rho(P,Q,R) = rank([P,Q][Q,R][R,P]).

This is invariant under simultaneous conjugation. It is also unchanged under independently replacing any of P,Q,R by its complement, because [I+U,W] = [U,W]. If

X = [P,Q],  Y = [Q,R],  Z = [R,P],

then

rho(P^T,Q^T,R^T) = rank(X^T Y^T Z^T) = rank((ZYX)^T) = rank(ZYX).

It therefore suffices to arrange rank(XYZ) != rank(ZYX).

# Uniform explicit matrices

Let L,N,J be d by d matrices supported on the first two coordinates, with 2 by 2 leading blocks

L_0 = [[1,0],[0,1]],
N_0 = [[0,1],[0,0]],
J_0 = [[0,0],[0,1]],

and zero elsewhere. Thus

N^2 = 0,  JN = 0,  NJ = N,  LN = NL = N.

In d by d block notation set

P = [[I,0],[0,0]],
Q = [[I,L],[0,0]],
R = [[I,J],[N,N]].

These are rank-d idempotents. For R, one may write

R = [[I],[N]] [I,J]

and [I,J][[I],[N]] = I because JN = 0, proving both idempotence and rank d.

They arise from explicit invertible matrices

x_d = [[I,L],[0,I]],
y_d = [[I,J],[N,I]].

Indeed x_d^(-1) = x_d and x_d P x_d^(-1) = Q. The matrix y_d is invertible: if y_d(a,b) = 0, then a = Jb and (I+N)b = 0, hence b=a=0 because N is nilpotent. Moreover [I,J]y_d = [I,0], so y_d P y_d^(-1) = R.

Direct multiplication gives

X = [P,Q] = [[0,L],[0,0]],
Y = [Q,R] = [[N,J+N+L],[N,N]],
Z = [R,P] = [[0,J],[N,0]].

Using the displayed relations,

XY = [[N,N],[0,0]],
XYZ = [[0,N],[0,0]],

so rank(XYZ) = rank(N) = 1. On the other hand,

ZY = 0,

because JN = N^2 = 0 and N(J+N+L) = NJ + N^2 + NL = N+0+N = 0. Hence rank(ZYX) = 0. Therefore

rho(P,Q,R) = 1,   rho(P^T,Q^T,R^T) = 0.

# Translation back to the coset criterion

Suppose that some h in H satisfied both required coset equations. Since h stabilizes the base unordered decomposition, for some epsilon_0 in {0,1},

hPh^(-1) = P + epsilon_0 I.

The two coset equations similarly imply, for epsilon_1,epsilon_2 in {0,1},

hQh^(-1) = Q^T + epsilon_1 I,
hRh^(-1) = R^T + epsilon_2 I.

Conjugacy invariance and independent-complement invariance of rho would then give

1 = rho(P,Q,R) = rho(P^T,Q^T,R^T) = 0,

a contradiction. Thus no such h exists.

# Proof spine and root impact

1. Certified rank-one classification handles n=2.
2. Certified projective outer witnesses remove extension fields and parameters with gcd(n,q-1)>1.
3. The residual prime-field theorem R remains the root classification bottleneck.
4. The present lemma proves that the equal two-block C2 graph-normalizer action cannot supply the needed even-binary witness: contragredient duality already moves an ordered-triple orbit for every d >= 2.

Dependency: explicit idempotents -> complement-invariant rank separator -> failure of the simultaneous-coset criterion -> abandonment of the equal-block graph-normalizer architecture.

The single remaining theorem-level gap is residual exclusion theorem R. On its even-binary part, the next live mechanism is the already stated nonnormalizing two-coset witness obligation, not another repair of this C2 graph action.

# Self-check

The argument uses only characteristic two, d >= 2, and the standard equal-block decomposition. The d=2 boundary is included rather than extrapolated from a computation. All three matrices are verified rank-d idempotents, x_d and y_d are explicitly invertible, alpha(H)=H because inverse-transpose preserves block-diagonal and block-antidiagonal form, and the invariant is checked under each independently allowed complement. No external citation or computation is used. The conclusion is deliberately limited: it refutes this graph-normalizer witness architecture and does not by itself prove total 3-closure or non-total 3-closure of any residual PSL group.
