# Decisive finite experiment for G=PSL(2,7)

## Mathematical question
Are all transitive coset actions of G 3-closed, and do mixed triples synchronize every unordered pair of transitive constituent types?

## Finite scope and method
GAP 4.16.0 constructs G as a faithful permutation group of order 168, computes `ConjugacyClassesSubgroups(G)`, removes G, and obtains exactly 14 proper-subgroup conjugacy classes. For each representative H, it forms the faithful coset image P_H on G/H. Since a 3-closure is contained in the 2-closure, it computes `TwoClosure(P_H)`. If this is larger than P_H, it successively takes the setwise stabilizers of the exact P_H-orbits on ordered triples; the resulting group is precisely the 3-closure. For each of the 105 unordered pairs it forms the diagonal image D isomorphic to G, takes a fixed element x of order 3, lets q=(1,x), and finds a mixed ordered triple t for which `RepresentativeAction(D,t,t^q,OnTuples)=fail`.

## Exact GAP 4.16.0 code

```
DirectSumPerm := function(p,q,n1,n2)
  return PermList(Concatenation(List([1..n1],a->a^p),List([1..n2],b->n1+b^q)));
end;;
OnSetsOfTuples := function(S,g)
  return Set(List(S,t->OnTuples(t,g)));
end;;
TripleClosureFromTwo := function(P)
  local n,triples,porbs,K,used,O;
  n:=LargestMovedPoint(P); triples:=Tuples([1..n],3);
  porbs:=OrbitsDomain(P,triples,OnTuples); K:=TwoClosure(P); used:=0;
  for O in porbs do
    K:=Stabilizer(K,Set(O),OnSetsOfTuples); used:=used+1;
    if Size(K)=Size(P) then break; fi;
  od;
  return rec(group:=K,tripleOrbitCount:=Length(porbs),orbitColorsUsed:=used);
end;;
MixedWitness := function(G,hi,hj,n1,n2,x)
  local gens,D,q,a,b,c,t,u,r,checked;
  gens:=GeneratorsOfGroup(G);
  D:=Group(List(gens,g->DirectSumPerm(Image(hi,g),Image(hj,g),n1,n2)));
  q:=DirectSumPerm((),Image(hj,x),n1,n2); checked:=0;
  for a in [1..n1] do for b in [1..n2] do for c in [1..n2] do
    t:=[a,n1+b,n1+c]; u:=OnTuples(t,q); checked:=checked+1;
    r:=RepresentativeAction(D,t,u,OnTuples);
    if r=fail then return rec(pattern:="I-J-J",tuple:=t,image:=u,checked:=checked); fi;
  od; od; od;
  for a in [1..n1] do for b in [1..n1] do for c in [1..n2] do
    t:=[a,b,n1+c]; u:=OnTuples(t,q); checked:=checked+1;
    r:=RepresentativeAction(D,t,u,OnTuples);
    if r=fail then return rec(pattern:="I-I-J",tuple:=t,image:=u,checked:=checked); fi;
  od; od; od;
  return fail;
end;;
G:=Image(IsomorphismPermGroup(PSL(2,7)));;
cc:=ConjugacyClassesSubgroups(G);;
props:=Filtered(cc,c->Size(Representative(c))<Size(G));;
SortBy(props,c->[Index(G,Representative(c)),Size(Representative(c)),StructureDescription(Representative(c))]);;
homs:=[];; images:=[];; degrees:=[];; labels:=[];; localFailures:=0;;
for i in [1..Length(props)] do
  H:=Representative(props[i]); hom:=ActionHomomorphism(G,RightCosets(G,H),OnRight);
  P:=Image(hom); Q:=TwoClosure(P);
  if Size(Q)=Size(P) then TC:=rec(group:=P,tripleOrbitCount:=-1,orbitColorsUsed:=0);
  else TC:=TripleClosureFromTwo(P); fi;
  if Size(TC.group)<>Size(P) then localFailures:=localFailures+1; fi;
  Add(homs,hom); Add(images,P); Add(degrees,NrMovedPoints(P));
  Add(labels,Concatenation(StructureDescription(H),"@",String(Index(G,H))));
  Print("LOCAL ",i," ",labels[i]," H=",Size(H)," degree=",degrees[i]," image=",Size(P)," 2cl=",Size(Q)," 3cl=",Size(TC.group)," orbits=",TC.tripleOrbitCount," used=",TC.orbitColorsUsed,"\n");
od;
x:=GeneratorsOfGroup(G)[1];; count:=0;; failures:=0;;
for i in [1..Length(props)] do for j in [i..Length(props)] do
  W:=MixedWitness(G,homs[i],homs[j],degrees[i],degrees[j],x); count:=count+1;
  if W=fail then failures:=failures+1; Print("PAIR ",i,",",j," NO_WITNESS\n");
  else Print("PAIR ",i,",",j," t=",W.tuple," tq=",W.image," separated=true\n"); fi;
od; od;
Print("SUMMARY properClasses=",Length(props)," localFailures=",localFailures," unorderedPairs=",count," pairFailures=",failures,"\n");
QUIT;
```

## Complete local output

|i|H|degree|2-closure order|3-closure order|triple orbits / colors used|
|---:|---|---:|---:|---:|---|
|1|S4|7|5040|168|6 / 5|
|2|S4|7|5040|168|6 / 5|
|3|C7:C3|8|40320|168|6 / 5|
|4|A4|14|645120|168|20 / 6|
|5|A4|14|645120|168|20 / 6|
|6|D8|21|168|168|not needed|
|7|C7|24|336|168|90 / 25|
|8|S3|28|168|168|not needed|
|9|C2 x C2|42|168|168|not needed|
|10|C2 x C2|42|168|168|not needed|
|11|C4|42|168|168|not needed|
|12|C3|56|168|168|not needed|
|13|C2|84|168|168|not needed|
|14|1|168|168|168|not needed|

Thus six, not five, classes require a genuine 3-orbit refinement (indices 1--5 and 7), while eight, not nine, classes are already 2-closed.

## All 105 mixed-pair certificates
Indices refer to the table. Every displayed `t -> tq` satisfies `RepresentativeAction(D,t,tq,OnTuples)=fail`.

```
(1,1) [1,8,8]->[1,10,10]; (1,2) [1,8,8]->[1,10,10]; (1,3) [1,8,9]->[1,12,9]; (1,4) [1,8,8]->[1,10,10]; (1,5) [1,8,8]->[1,10,10]; (1,6) [1,8,8]->[1,10,10]; (1,7) [1,8,11]->[1,22,13]; (1,8) [1,8,8]->[1,10,10]; (1,9) [1,8,8]->[1,10,10]; (1,10) [1,8,8]->[1,10,10]; (1,11) [1,8,8]->[1,10,10]; (1,12) [1,8,8]->[1,40,40]; (1,13) [1,8,8]->[1,10,10]; (1,14) [1,8,8]->[1,120,120]
(2,2) [1,8,8]->[1,10,10]; (2,3) [1,8,9]->[1,12,9]; (2,4) [1,8,8]->[1,10,10]; (2,5) [1,8,9]->[1,10,8]; (2,6) [1,8,8]->[1,10,10]; (2,7) [1,8,11]->[1,22,13]; (2,8) [1,8,8]->[1,10,10]; (2,9) [1,8,8]->[1,10,10]; (2,10) [1,8,8]->[1,10,10]; (2,11) [1,8,8]->[1,10,10]; (2,12) [1,8,8]->[1,40,40]; (2,13) [1,8,8]->[1,10,10]; (2,14) [1,8,8]->[1,120,120]
(3,3) [1,9,9]->[1,13,13]; (3,4) [1,9,10]->[1,11,9]; (3,5) [1,9,10]->[1,11,9]; (3,6) [1,9,10]->[1,11,9]; (3,7) [1,9,9]->[1,23,23]; (3,8) [1,9,10]->[1,11,9]; (3,9) [1,9,10]->[1,11,9]; (3,10) [1,9,10]->[1,11,9]; (3,11) [1,9,10]->[1,11,9]; (3,12) [1,9,9]->[1,41,41]; (3,13) [1,9,10]->[1,11,9]; (3,14) [1,9,9]->[1,121,121]
(4,4) [1,15,15]->[1,17,17]; (4,5) [1,15,15]->[1,17,17]; (4,6) [1,15,15]->[1,17,17]; (4,7) [1,15,15]->[1,29,29]; (4,8) [1,15,15]->[1,17,17]; (4,9) [1,15,15]->[1,17,17]; (4,10) [1,15,15]->[1,17,17]; (4,11) [1,15,15]->[1,17,17]; (4,12) [1,15,15]->[1,47,47]; (4,13) [1,15,15]->[1,17,17]; (4,14) [1,15,15]->[1,127,127]
(5,5) [1,15,15]->[1,17,17]; (5,6) [1,15,16]->[1,17,15]; (5,7) [1,15,15]->[1,29,29]; (5,8) [1,15,15]->[1,17,17]; (5,9) [1,15,15]->[1,17,17]; (5,10) [1,15,15]->[1,17,17]; (5,11) [1,15,15]->[1,17,17]; (5,12) [1,15,15]->[1,47,47]; (5,13) [1,15,15]->[1,17,17]; (5,14) [1,15,15]->[1,127,127]
(6,6) [1,22,22]->[1,24,24]; (6,7) [1,22,22]->[1,36,36]; (6,8) [1,22,22]->[1,24,24]; (6,9) [1,22,22]->[1,24,24]; (6,10) [1,22,22]->[1,24,24]; (6,11) [1,22,22]->[1,24,24]; (6,12) [1,22,22]->[1,54,54]; (6,13) [1,22,22]->[1,24,24]; (6,14) [1,22,22]->[1,134,134]
(7,7) [1,25,25]->[1,39,39]; (7,8) [1,25,26]->[1,27,25]; (7,9) [1,25,26]->[1,27,25]; (7,10) [1,25,26]->[1,27,25]; (7,11) [1,25,26]->[1,27,25]; (7,12) [1,25,25]->[1,57,57]; (7,13) [1,25,26]->[1,27,25]; (7,14) [1,25,25]->[1,137,137]
(8,8) [1,29,29]->[1,31,31]; (8,9) [1,29,29]->[1,31,31]; (8,10) [1,29,29]->[1,31,31]; (8,11) [1,29,29]->[1,31,31]; (8,12) [1,29,29]->[1,61,61]; (8,13) [1,29,29]->[1,31,31]; (8,14) [1,29,29]->[1,141,141]
(9,9) [1,43,43]->[1,45,45]; (9,10) [1,43,43]->[1,45,45]; (9,11) [1,43,43]->[1,45,45]; (9,12) [1,43,43]->[1,75,75]; (9,13) [1,43,43]->[1,45,45]; (9,14) [1,43,43]->[1,155,155]
(10,10) [1,43,43]->[1,45,45]; (10,11) [1,43,43]->[1,45,45]; (10,12) [1,43,43]->[1,75,75]; (10,13) [1,43,43]->[1,45,45]; (10,14) [1,43,43]->[1,155,155]
(11,11) [1,43,43]->[1,45,45]; (11,12) [1,43,43]->[1,75,75]; (11,13) [1,43,43]->[1,45,45]; (11,14) [1,43,43]->[1,155,155]
(12,12) [1,57,57]->[1,89,89]; (12,13) [1,57,57]->[1,59,59]; (12,14) [1,57,57]->[1,169,169]
(13,13) [1,85,85]->[1,87,87]; (13,14) [1,85,85]->[1,197,197]
(14,14) [1,169,169]->[1,281,281]
SUMMARY properClasses=14 localFailures=0 unorderedPairs=105 pairFailures=0
```

## Interpretation and proof relevance
The computation supplies the missing finite certificate: all 14 faithful transitive actions are 3-closed and every one of the 105 pairs has a mixed triple excluding (1,x). The CAS output itself is finite; the companion proof dossier supplies the reduction from arbitrary faithful G-sets. The next move is strict re-verification of the repaired existing inference.
