#############################################################################
## Kourovka 17.91: universal split-lift criterion and exact certificates.
## GAP 4.16+
##
## This file deliberately works in the regular group algebra.  It tests every
## right FH-module at once; it does not enumerate irreducible modules.
##
## Usage examples (from this directory):
##   gap -q -A -c 'US_MODE:="regression"; Read("gap4_universal_split.g");'
##   gap -q -A -c 'US_MODE:="modular"; US_PRIMES:=[2,3];
##                 Read("gap4_universal_split.g");'
##   gap -q -A -c 'US_MODE:="integral";
##                 Read("gap4_universal_split.g");'
#############################################################################

if not IsBound(US_MODE) then US_MODE := "library"; fi;
if not IsBound(US_PRIMES) then US_PRIMES := [2,3,5,7]; fi;
if not IsBound(US_CERTIFICATE_DIR) then US_CERTIFICATE_DIR := "certificates"; fi;
if not IsBound(US_LOG) then US_LOG := "logs/universal_split.log"; fi;

USAppend := function(parts)
  local out;
  out := OutputTextFile(US_LOG,true);
  SetPrintFormattingStatus(out,false);
  PrintTo(out,JoinStringsWithSeparator(List(parts,String),"|"),"\n");
  CloseStream(out);
end;

USDerivedLength := function(g)
  return Length(DerivedSeriesOfGroup(g))-1;
end;

USDerivedOrders := function(g)
  return List(DerivedSeriesOfGroup(g),Order);
end;

USKnownSharpSeed := function()
  local h,classes,hits,l;
  h := SmallGroup(1296,2891);
  classes := ConjugacyClassesMaximalSubgroups(h);
  hits := Filtered(classes,c->Order(Representative(c))=324 and
    IdGroup(Representative(c))=[324,39]);
  if Length(hits)<>1 then
    Error("expected one [324,39] maximal class in [1296,2891]");
  fi;
  l := Representative(hits[1]);
  return rec(name:="SG1296_2891__SG324_39",H:=h,L:=l);
end;

USCheckExactPair := function(seed,expectedGap)
  local h,l,dh,dl,intermediate;
  h:=seed.H; l:=seed.L;
  dh:=USDerivedLength(h); dl:=USDerivedLength(l);
  if not IsSolvableGroup(h) then Error("ambient group is not soluble"); fi;
  if not IsSubgroup(h,l) or Order(l)>=Order(h) then
    Error("L is not a proper subgroup of H");
  fi;
  intermediate:=IntermediateSubgroups(h,l).subgroups;
  if Length(intermediate)<>0 then Error("L is not maximal in H"); fi;
  if dh-dl<>expectedGap then Error("unexpected derived-length gap"); fi;
  return rec(orderH:=Order(h),orderL:=Order(l),dH:=dh,dL:=dl,
    derivedH:=USDerivedOrders(h),derivedL:=USDerivedOrders(l),
    maximal:=true,soluble:=true);
end;

#############################################################################
## Finite-field regular-algebra engine.
#############################################################################

USRightPerm := function(elements,g)
  return PermList(List(elements,x->PositionCanonical(elements,x*g)));
end;

USCosetAugmentationBasisFF := function(h,k,field,elements)
  local basis,coset,list,rep,x,v,n,one;
  basis:=[]; n:=Length(elements); one:=One(field);
  for coset in RightCosets(h,k) do
    list:=AsList(coset); rep:=PositionCanonical(elements,list[1]);
    for x in list{[2..Length(list)]} do
      v:=List([1..n],i->Zero(field));
      v[PositionCanonical(elements,x)]:=one; v[rep]:=-one;
      ConvertToVectorRep(v,field); Add(basis,v);
    od;
  od;
  return basis;
end;

USAugmentationStepFF := function(basis,k,field,elements)
  local perms,vectors,v,perm,w;
  if Length(basis)=0 then return []; fi;
  perms:=List(GeneratorsOfGroup(k),g->USRightPerm(elements,g));
  vectors:=[];
  for v in basis do for perm in perms do
    w:=Permuted(v,perm)-v;
    if not IsZero(w) then Add(vectors,w); fi;
  od; od;
  if Length(vectors)=0 then return []; fi;
  return BaseMat(vectors);
end;

USRightIdealClosureFF := function(basis,h,field,elements)
  local perms,old,bigger,v,perm;
  if Length(basis)=0 then return []; fi;
  perms:=List(GeneratorsOfGroup(h),g->USRightPerm(elements,g));
  repeat
    old:=Length(basis); bigger:=ShallowCopy(basis);
    for v in basis do for perm in perms do
      Add(bigger,Permuted(v,perm));
    od; od;
    basis:=BaseMat(bigger);
  until Length(basis)=old;
  return basis;
end;

USProductBasisFF := function(h,chain,field,elements,closeRight)
  local basis,dims,i;
  basis:=USCosetAugmentationBasisFF(h,chain[1],field,elements);
  dims:=[Length(basis)];
  for i in [2..Length(chain)] do
    basis:=USAugmentationStepFF(basis,chain[i],field,elements);
    Add(dims,Length(basis));
  od;
  if closeRight then basis:=USRightIdealClosureFF(basis,h,field,elements); fi;
  return rec(basis:=basis,dims:=dims,dimension:=Length(basis));
end;

USModularCertificate := function(seed,p)
  local h,l,elements,field,hchain,lchain,ph,jl,contained,sumdim;
  h:=seed.H; l:=seed.L; elements:=AsList(h); field:=GF(p);
  hchain:=DerivedSeriesOfGroup(h);
  hchain:=hchain{[1..Length(hchain)-1]};
  lchain:=DerivedSeriesOfGroup(l);
  lchain:=lchain{[1..Length(lchain)-1]};
  ph:=USProductBasisFF(h,hchain,field,elements,false);
  jl:=USProductBasisFF(h,lchain,field,elements,true);
  sumdim:=Length(BaseMat(Concatenation(jl.basis,ph.basis)));
  contained:=sumdim=jl.dimension;
  return rec(characteristic:=p,ambientProductDims:=ph.dims,
    maximalProductDims:=jl.dims,rankPH:=ph.dimension,rankJL:=jl.dimension,
    rankSum:=sumdim,contained:=contained);
end;

#############################################################################
## Integral lattice engine.
##
## Rows are coordinates in the basis H of Z[H].  BaseIntMat supplies a
## canonical row-Hermite basis.  Equality after adjoining rows is therefore
## an exact lattice-containment test, not a rational-rank test.
#############################################################################

USNonzeroRows := function(mat)
  return Filtered(mat,v->not IsZero(v));
end;

USCosetAugmentationBasisZZ := function(h,k,elements)
  local basis,coset,list,rep,x,v,n;
  basis:=[]; n:=Length(elements);
  for coset in RightCosets(h,k) do
    list:=AsList(coset); rep:=PositionCanonical(elements,list[1]);
    for x in list{[2..Length(list)]} do
      v:=ListWithIdenticalEntries(n,0);
      v[PositionCanonical(elements,x)]:=1; v[rep]:=-1;
      Add(basis,v);
    od;
  od;
  return BaseIntMat(basis);
end;

USAugmentationStepZZ := function(basis,k,elements)
  local perms,vectors,v,perm,w;
  if Length(basis)=0 then return []; fi;
  perms:=List(GeneratorsOfGroup(k),g->USRightPerm(elements,g));
  vectors:=[];
  for v in basis do for perm in perms do
    w:=Permuted(v,perm)-v;
    if not IsZero(w) then Add(vectors,w); fi;
  od; od;
  if Length(vectors)=0 then return []; fi;
  return USNonzeroRows(BaseIntMat(vectors));
end;

USRightIdealClosureZZ := function(basis,h,elements)
  local perms,bigger,newbasis,v,perm,round;
  if Length(basis)=0 then return []; fi;
  perms:=List(GeneratorsOfGroup(h),g->USRightPerm(elements,g));
  round:=0;
  repeat
    round:=round+1; bigger:=ShallowCopy(basis);
    for v in basis do for perm in perms do
      Add(bigger,Permuted(v,perm));
    od; od;
    newbasis:=USNonzeroRows(BaseIntMat(bigger));
    USAppend(["integral_right_closure",round,Length(basis),Length(newbasis)]);
    if newbasis=basis then return basis; fi;
    basis:=newbasis;
  until false;
end;

USProductBasisZZ := function(h,chain,elements,closeRight,label)
  local basis,dims,i;
  basis:=USCosetAugmentationBasisZZ(h,chain[1],elements);
  dims:=[Length(basis)];
  USAppend(["integral_product",label,1,Length(basis)]);
  for i in [2..Length(chain)] do
    basis:=USAugmentationStepZZ(basis,chain[i],elements);
    Add(dims,Length(basis));
    USAppend(["integral_product",label,i,Length(basis)]);
  od;
  if closeRight then basis:=USRightIdealClosureZZ(basis,h,elements); fi;
  return rec(basis:=basis,dims:=dims,rank:=Length(basis));
end;

USWriteMatrixMarket := function(path,basis,ncols)
  local out,nnz,i,j;
  nnz:=Sum(basis,v->Number(v,x->x<>0));
  out:=OutputTextFile(path,false); SetPrintFormattingStatus(out,false);
  PrintTo(out,"%%MatrixMarket matrix coordinate integer general\n");
  PrintTo(out,"% row-Hermite lattice basis in the ordered GAP list AsList(H)\n");
  PrintTo(out,Length(basis)," ",ncols," ",nnz,"\n");
  for i in [1..Length(basis)] do
    for j in [1..ncols] do
      if basis[i][j]<>0 then PrintTo(out,i," ",j," ",basis[i][j],"\n"); fi;
    od;
  od;
  CloseStream(out);
end;

USPrimeDivisors := function(values)
  local primes,x;
  primes:=[];
  for x in values do
    if AbsInt(x)>1 then UniteSet(primes,Set(FactorsInt(AbsInt(x)))); fi;
  od;
  return primes;
end;

USSNFNonzeroDiagonal := function(mat)
  local snf,d,n,i;
  if Length(mat)=0 then return []; fi;
  snf:=SmithNormalFormIntegerMat(mat);
  n:=Minimum(Length(snf),Length(snf[1])); d:=[];
  for i in [1..n] do if snf[i][i]<>0 then Add(d,AbsInt(snf[i][i])); fi; od;
  return d;
end;

USRankModPrimeFromSNF := function(diagonal,p)
  return Number(diagonal,x->x mod p<>0);
end;

USIntegralCertificate := function(seed)
  local h,l,elements,hchain,lchain,ph,jl,sumBasis,contained,qdata,
        qFree,qTorsion,snfJ,snfS,candidatePool,candidatePrimes,p,
        modular,pathPH,pathJL,pathSum,pathSummary,out;
  h:=seed.H; l:=seed.L; elements:=AsList(h);
  hchain:=DerivedSeriesOfGroup(h);
  hchain:=hchain{[1..Length(hchain)-1]};
  lchain:=DerivedSeriesOfGroup(l);
  lchain:=lchain{[1..Length(lchain)-1]};
  ph:=USProductBasisZZ(h,hchain,elements,false,"PH");
  jl:=USProductBasisZZ(h,lchain,elements,true,"JL");
  sumBasis:=USNonzeroRows(BaseIntMat(Concatenation(jl.basis,ph.basis)));
  contained:=sumBasis=jl.basis;
  qdata:=ComplementIntMat(sumBasis,jl.basis);
  qFree:=Length(qdata.complement);
  qTorsion:=Filtered(qdata.moduli,x->AbsInt(x)>1);

  ## These two ambient-embedding Smith forms, rather than Q alone, decide
  ## modular image ranks.  This is the required saturation/Tor correction.
  snfJ:=USSNFNonzeroDiagonal(jl.basis);
  snfS:=USSNFNonzeroDiagonal(sumBasis);
  candidatePool:=Union(USPrimeDivisors(snfJ),USPrimeDivisors(snfS));
  candidatePrimes:=[];
  for p in candidatePool do
    if USRankModPrimeFromSNF(snfS,p)>USRankModPrimeFromSNF(snfJ,p) then
      Add(candidatePrimes,p);
    fi;
  od;

  pathPH:=Concatenation(US_CERTIFICATE_DIR,"/",seed.name,"_PH_Z.mtx");
  pathJL:=Concatenation(US_CERTIFICATE_DIR,"/",seed.name,"_JL_Z.mtx");
  pathSum:=Concatenation(US_CERTIFICATE_DIR,"/",seed.name,"_SUM_Z.mtx");
  pathSummary:=Concatenation(US_CERTIFICATE_DIR,"/",seed.name,"_integral.json");
  USWriteMatrixMarket(pathPH,ph.basis,Length(elements));
  USWriteMatrixMarket(pathJL,jl.basis,Length(elements));
  USWriteMatrixMarket(pathSum,sumBasis,Length(elements));

  out:=OutputTextFile(pathSummary,false); SetPrintFormattingStatus(out,false);
  PrintTo(out,"{\n");
  PrintTo(out,"  \"seed\": \"",seed.name,"\",\n");
  PrintTo(out,"  \"group_order\": ",Order(h),",\n");
  PrintTo(out,"  \"PH_product_ranks\": ",ph.dims,",\n");
  PrintTo(out,"  \"PL_product_ranks_before_two_sided_closure\": ",jl.dims,",\n");
  PrintTo(out,"  \"rank_PH_Q\": ",ph.rank,",\n");
  PrintTo(out,"  \"rank_JL_Q\": ",jl.rank,",\n");
  PrintTo(out,"  \"rank_sum_Q\": ",Length(sumBasis),",\n");
  PrintTo(out,"  \"integral_containment_PH_in_JL\": ",contained,",\n");
  PrintTo(out,"  \"Q_free_rank\": ",qFree,",\n");
  PrintTo(out,"  \"Q_nontrivial_invariant_factors\": ",qTorsion,",\n");
  PrintTo(out,"  \"SNF_JL_nonzero_diagonal\": ",snfJ,",\n");
  PrintTo(out,"  \"SNF_SUM_nonzero_diagonal\": ",snfS,",\n");
  PrintTo(out,"  \"candidate_characteristics_after_saturation_correction\": ",candidatePrimes,",\n");
  PrintTo(out,"  \"basis_PH\": \"",pathPH,"\",\n");
  PrintTo(out,"  \"basis_JL\": \"",pathJL,"\",\n");
  PrintTo(out,"  \"basis_SUM\": \"",pathSum,"\"\n");
  PrintTo(out,"}\n"); CloseStream(out);

  modular:=List(candidatePrimes,p->USModularCertificate(seed,p));
  return rec(PH:=ph,JL:=jl,sumBasis:=sumBasis,contained:=contained,
    qFreeRank:=qFree,qInvariantFactors:=qTorsion,snfJL:=snfJ,snfSum:=snfS,
    candidatePrimes:=candidatePrimes,modularVerification:=modular,
    summaryPath:=pathSummary);
end;

#############################################################################
## Command modes.
#############################################################################

if US_MODE<>"library" then
  USSeed:=USKnownSharpSeed();
  USRegression:=USCheckExactPair(USSeed,3);
  Print("REGRESSION ",USRegression,"\n");
  if US_MODE="regression" then
    Print("terminal contained: ",IsSubgroup(
      DerivedSeriesOfGroup(USSeed.L)[3],
      DerivedSeriesOfGroup(USSeed.H)[6]),"\n");
  elif US_MODE="modular" then
    for USP in US_PRIMES do
      USMod:=USModularCertificate(USSeed,USP);
      Print("MODULAR ",USMod,"\n");
    od;
  elif US_MODE="integral" then
    USIntegral:=USIntegralCertificate(USSeed);
    Print("INTEGRAL contained=",USIntegral.contained,
      " rankPH=",USIntegral.PH.rank," rankJL=",USIntegral.JL.rank,
      " qFree=",USIntegral.qFreeRank,
      " qTorsion=",USIntegral.qInvariantFactors,
      " candidatePrimes=",USIntegral.candidatePrimes,"\n");
  else
    Error("US_MODE must be library, regression, modular, or integral");
  fi;
fi;
