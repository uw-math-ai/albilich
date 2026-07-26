# Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type

## Problem

Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set
\(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is
the largest subgroup of \(\operatorname{Sym}(\Omega)\) whose orbits on the set
\(\Omega^{k}\) of ordered \(k\)-tuples coincide with the orbits of \(G\) on
\(\Omega^{k}\) (Wielandt). The group \(G\) is **\(k\)-closed** on \(\Omega\) if
\(G^{(k)} = G\).

An abstract group \(G\) is **totally \(k\)-closed** if for every faithful
permutation representation of \(G\) on a finite set \(\Omega\), the image of
\(G\) in \(\operatorname{Sym}(\Omega)\) is \(k\)-closed.

**Question (Problem 20.2).** Are there any nonabelian simple groups of Lie type
which are totally 3-closed?

Known context: the finite nonabelian simple totally 2-closed groups are
completely classified — there are exactly six, all sporadic groups
(\(\mathrm{J}_1\), \(\mathrm{J}_3\), \(\mathrm{J}_4\), \(\mathrm{Ly}\),
\(\mathrm{Th}\), and the Monster \(\mathrm{M}\)), the largest being the Monster.
Since a totally 2-closed group is totally 3-closed, the real content of the
question is whether total 3-closure can occur for simple groups of Lie type,
where total 2-closure provably cannot.

## Instructions

Treat this as a serious research problem, not only as a benchmark. The target is
to either exhibit a nonabelian simple group of Lie type that is totally
3-closed (with proof), or prove that no nonabelian simple group of Lie type is
totally 3-closed, or establish an honest, precisely stated partial result.

Use direct proof attempts before reducing unless a reduction is mathematically
motivated. Literature search and citations are allowed, and cited theorems may
be used to close a case when the statement is properly identified and logically
applied. The classification of totally 2-closed simple groups and the toolkit
around \(k\)-closures of permutation groups (Wielandt's theory, Praeger–Saxl,
recent work of Abdollahi, Arezoomand, Tracey and coauthors on total
\(k\)-closure) are natural starting points. If an exact published result
answers the question, integrate it responsibly instead of reproving it.

Group-theoretic computation (e.g. GAP) may be used for examples, sanity checks,
and small Lie-type groups: computing \(3\)-closures of specific faithful
permutation representations of small groups such as \(\mathrm{PSL}(2,q)\) for
small \(q\) is encouraged as evidence, and a single faithful representation
that fails to be 3-closed rules that group out. The final argument must be a
mathematical proof or a mathematically rigorous obstruction; finite
computations alone settle individual groups, not the general question, unless
combined with a reduction theorem.
