Question. Does any Coxeter-diagram automorphism in the local high-rank orthogonal families move the point or line types, as triality does in type D_4?

Competing hypotheses. H1: B_m has trivial diagram automorphism group and, for D_m with m>=5, the only diagram automorphism swaps the two terminal spin nodes while fixing types 1 and 2. H2: some m>=5 admits an additional type-moving automorphism, obstructing the translation from the cited full-automorphism theorem to projective semisimilarities.

Method. No GAP, Sage, Julia, Macaulay2, or Singular executable was available, so an exact bounded Python standard-library enumeration was used. For each labeled Coxeter matrix of B_m and D_m with 4<=m<=9, all vertex permutations were tested for preservation of every Coxeter entry.

Code.
from itertools import permutations

def coxeter_B(m):
    M=[[1 if i==j else 2 for j in range(m)] for i in range(m)]
    for i in range(m-1): M[i][i+1]=M[i+1][i]=3
    M[m-2][m-1]=M[m-1][m-2]=4
    return M

def coxeter_D(m):
    M=[[1 if i==j else 2 for j in range(m)] for i in range(m)]
    for a,b in [(i,i+1) for i in range(m-3)]+[(m-3,m-2),(m-3,m-1)]:
        M[a][b]=M[b][a]=3
    return M

def automorphisms(M):
    n=len(M)
    return [p for p in permutations(range(n))
            if all(M[p[i]][p[j]]==M[i][j]
                   for i in range(n) for j in range(n))]

for typ,builder in [('B',coxeter_B),('D',coxeter_D)]:
    for m in range(4,10):
        A=automorphisms(builder(m))
        print(typ,m,len(A),sorted({p[0]+1 for p in A}),
              sorted({p[1]+1 for p in A}))

Output summary. For every B_m, 4<=m<=9, the automorphism group had order 1 and fixed types 1 and 2. For D_4 it had order 6 and the orbit of type 1 was {1,3,4}, displaying triality. For every D_m, 5<=m<=9, it had order 2 and fixed types 1 and 2.

Interpretation. The computation detects exactly the cited D_4 exception and no high-rank analogue. The infinite pattern has an elementary proof: in B_m the unique edge labeled 4 fixes its incident end and then the whole path; in D_m for m>=5 the trivalent vertex has arms of lengths 1, 1, and m-3, so an automorphism can only exchange the two length-one spin arms. It therefore fixes every vertex on the long arm, including the point and line types. The computation is a finite audit, not a proof of the infinite automorphism-classification theorem.

Conclusion and proof relevance. The diagram check supports the precise failure boundary in Kleidman-Liebeck Theorem 2.1.4: D_4 triality is genuine, while the local range m>=5 has only the ordinary D_m involution already realized by a projective orthogonal similarity. The next proof move is therefore to use the exact source equality Aut(PΩ(V,Q))=PΓ(V,Q), rather than reopening building reconstruction.
