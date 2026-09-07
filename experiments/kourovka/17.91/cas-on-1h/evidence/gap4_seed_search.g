#############################################################################
## Kourovka 17.91: recursive exact-gap-two -> exact-gap-three search.
## GAP 4.16+
##
## SmallGroups is used only to make a seed database.  Every lift is tested by
## the regular-algebra universal quotient F[K]/J_B, not by enumerating simple
## modules.  The default finite seed frontier is intentionally modest and is
## restartable by order.
#############################################################################

if not IsBound(SEED_MODE) then SEED_MODE:="all"; fi;
if not IsBound(SEED_MAX_ORDER) then SEED_MAX_ORDER:=96; fi;
if not IsBound(SEED_PRIMES) then SEED_PRIMES:=[2,3,5,7,11]; fi;
if not IsBound(SEED_GAP2_CSV) then SEED_GAP2_CSV:="gap2_seed_database.csv"; fi;
if not IsBound(SEED_GAP3_CSV) then SEED_GAP3_CSV:="gap3_seeds.csv"; fi;
if not IsBound(SEED_GAP4_CSV) then SEED_GAP4_CSV:="gap4_candidates.csv"; fi;
if not IsBound(SEED_CHECKPOINT) then
  SEED_CHECKPOINT:="checkpoints/seed_search.checkpoint";
fi;

US_MODE:="library";
Read("gap4_universal_split.g");

SeedCsvField:=function(value)
  local s;
  if value=fail then s:="";
  elif IsString(value) then s:=value;
  else s:=String(value); fi;
  return Concatenation("\"",ReplacedString(s,"\"","\"\""),"\"");
end;

SeedWriteCsv:=function(out,row)
  PrintTo(out,JoinStringsWithSeparator(List(row,SeedCsvField),","),"\n");
end;

SeedAppendCheckpoint:=function(parts)
  local out;
  out:=OutputTextFile(SEED_CHECKPOINT,true); SetPrintFormattingStatus(out,false);
  PrintTo(out,JoinStringsWithSeparator(List(parts,String),"|"),"\n");
  CloseStream(out);
end;

SeedPairKey:=function(k,b)
  return Concatenation(String(IdGroup(k)),"/",String(IdGroup(b)));
end;

## Construction-family hook.  Extraspecial, core-top, wreath, crown, fiber,
## or subdirect constructors may pass a concrete pair here.  The hook proves
## the finite/soluble/maximal assertions before admitting the pair and returns
## its exact terminal classification; it never assumes that an obvious wreath
## or diagonal subgroup is maximal.
SeedConstructionHook:=function(h,l,label)
  local dh,dl,intermediate,seriesH,seriesL,r,t,contained;
  if not IsFinite(h) or not IsSolvableGroup(h) then return fail; fi;
  if not IsSubgroup(h,l) or Order(l)>=Order(h) then return fail; fi;
  intermediate:=IntermediateSubgroups(h,l).subgroups;
  if Length(intermediate)<>0 then return fail; fi;
  dh:=USDerivedLength(h); dl:=USDerivedLength(l);
  if dh-dl<2 then return fail; fi;
  seriesH:=DerivedSeriesOfGroup(h); seriesL:=DerivedSeriesOfGroup(l);
  if dh-dl=3 then
    r:=dl; t:=seriesH[r+3]; contained:=IsSubgroup(seriesL[r],t);
  else
    t:=fail; contained:=fail;
  fi;
  return rec(H:=h,L:=l,key:=label,source:="construction_family_hook",
    dH:=dh,dL:=dl,gap:=dh-dl,maximal:=true,terminal:=t,
    terminalContained:=contained);
end;

SeedExtractGapTwo:=function()
  local result,n,count,i,k,dk,classes,c,b,db,key,seen,explicitK,explicitB;
  result:=[]; seen:=[];
  for n in [1..SEED_MAX_ORDER] do
    if SmallGroupsAvailable(n) then
      count:=NrSmallGroups(n);
      for i in [1..count] do
        k:=SmallGroup(n,i);
        if IsSolvableGroup(k) then
          dk:=USDerivedLength(k);
          if dk>=3 then
            classes:=ConjugacyClassesMaximalSubgroups(k);
            for c in classes do
              b:=Representative(c); db:=USDerivedLength(b);
              if dk-db=2 then
                key:=SeedPairKey(k,b);
                if not key in seen then
                  Add(seen,key);
                  Add(result,rec(K:=k,B:=b,key:=key,source:="SmallGroups_seed_database"));
                fi;
              fi;
            od;
          fi;
        fi;
      od;
      SeedAppendCheckpoint(["extracted_order",n,"pairs",Length(result)]);
    fi;
  od;

  ## Structurally different, previously verified Heisenberg-Q8 seed.
  explicitK:=SmallGroup(216,88);
  explicitB:=SmallGroup(24,11);
  ## Embed the correct maximal class rather than use an abstract copy.
  classes:=Filtered(ConjugacyClassesMaximalSubgroups(explicitK),c->
    IdGroup(Representative(c))=[24,11]);
  if Length(classes)=1 then
    explicitB:=Representative(classes[1]); key:=SeedPairKey(explicitK,explicitB);
    if not key in seen then
      Add(result,rec(K:=explicitK,B:=explicitB,key:=key,
        source:="Heisenberg_Q8_verified_seed"));
    fi;
  fi;
  return result;
end;

SeedRankSumFF:=function(parts)
  return Length(BaseMat(Concatenation(parts)));
end;

SeedProductPrefixFF:=function(k,x,steps,field,elements)
  local chain;
  if steps=0 then return rec(basis:=IdentityMat(Order(k),field),dims:=[Order(k)],
    dimension:=Order(k)); fi;
  chain:=DerivedSeriesOfGroup(x);
  chain:=chain{[1..steps]};
  return USProductBasisFF(k,chain,field,elements,false);
end;

SeedQuotientDimension:=function(jbasis,ubasis)
  return Length(BaseMat(Concatenation(jbasis,ubasis)))-Length(jbasis);
end;

SeedExtensionDerivedLength:=function(k,x,field,elements,jbasis)
  local dx,prod,finaldim;
  dx:=USDerivedLength(x);
  if dx=0 then return 1; fi;
  prod:=SeedProductPrefixFF(k,x,dx,field,elements);
  finaldim:=SeedQuotientDimension(jbasis,prod.basis);
  if finaldim>0 then return dx+1; fi;
  return dx;
end;

SeedUniversalGapThreeLift:=function(pair,p)
  local k,b,s,field,elements,kchain,bchain,pk,jb,sumrank,witnessDim,
        terminalDim,bpen,bpenRank,terminalContained,core,coreDL,top,
        orderH,orderL,terminalOrder;
  k:=pair.K; b:=pair.B; s:=USDerivedLength(b);
  field:=GF(p); elements:=AsList(k);
  kchain:=DerivedSeriesOfGroup(k);
  kchain:=kchain{[1..Length(kchain)-1]};
  bchain:=DerivedSeriesOfGroup(b);
  bchain:=bchain{[1..Length(bchain)-1]};
  pk:=USProductBasisFF(k,kchain,field,elements,false);
  jb:=USProductBasisFF(k,bchain,field,elements,true);
  sumrank:=Length(BaseMat(Concatenation(jb.basis,pk.basis)));
  if sumrank=jb.dimension then return fail; fi;
  witnessDim:=Order(k)-jb.dimension;
  terminalDim:=sumrank-jb.dimension;
  if s=1 then
    terminalContained:=true;
  else
    bpen:=SeedProductPrefixFF(k,b,s-1,field,elements);
    bpenRank:=Length(BaseMat(Concatenation(jb.basis,bpen.basis)));
    terminalContained:=Length(BaseMat(Concatenation(jb.basis,bpen.basis,
      pk.basis)))=bpenRank;
  fi;
  core:=Core(k,b);
  coreDL:=SeedExtensionDerivedLength(k,core,field,elements,jb.basis);
  top:=Image(NaturalHomomorphismByNormalSubgroup(b,core));
  orderH:=Order(k)*p^witnessDim; orderL:=Order(b)*p^witnessDim;
  terminalOrder:=p^terminalDim;
  return rec(parent:=pair.key,source:=pair.source,characteristic:=p,
    witnessDimension:=witnessDim,orderH:=orderH,orderL:=orderL,
    dH:=s+3,dL:=s,coreOrder:=Order(core)*p^witnessDim,
    dCore:=coreDL,dTop:=USDerivedLength(top),terminalDimension:=terminalDim,
    terminalOrder:=terminalOrder,terminalContained:=terminalContained,
    rankPK:=pk.dimension,rankJB:=jb.dimension,rankSum:=sumrank,
    candidateCharacteristics:=[p]);
end;

SeedWriteGapTwoDatabase:=function(pairs)
  local out,pair,k,b,core;
  out:=OutputTextFile(SEED_GAP2_CSV,false); SetPrintFormattingStatus(out,false);
  SeedWriteCsv(out,["source","pair","order_K","id_K","d_K","order_B",
    "id_B","d_B","index","core_order","terminal_escape_possible"]);
  for pair in pairs do
    k:=pair.K; b:=pair.B; core:=Core(k,b);
    SeedWriteCsv(out,[pair.source,pair.key,Order(k),IdGroup(k),
      USDerivedLength(k),Order(b),IdGroup(b),USDerivedLength(b),
      Index(k,b),Order(core),USDerivedLength(b)>=2]);
  od;
  CloseStream(out);
end;

SeedWriteKnownControls:=function(out)
  local i,certificateStatus;
  for i in [1..3] do
    if i=3 then
      certificateStatus:="integral Z[H] containment; no characteristic survives";
    else
      certificateStatus:="previous modular tests only; integral certificate not run here";
    fi;
    SeedWriteCsv(out,["known_order_1296_control",
      String([[1296,2888+i],[324,42-i]]),1296,6,324,3,
      54,3,2,3,1,true,certificateStatus,"none",
      "bounded H2 previously complete through dimension 6"]);
  od;
end;

SeedSearchRecursiveLifts:=function(pairs)
  local out,candOut,pair,p,lift,hits,escaping,tested;
  out:=OutputTextFile(SEED_GAP3_CSV,false); SetPrintFormattingStatus(out,false);
  SeedWriteCsv(out,["construction","parent_seed","order_H","d_H","order_L",
    "d_L","core_order","d_core","d_top","terminal_order",
    "terminal_dimension","terminal_contained","split_lift_certificate_status",
    "candidate_characteristics","cohomology_status"]);
  SeedWriteKnownControls(out);
  candOut:=OutputTextFile(SEED_GAP4_CSV,false);
  SetPrintFormattingStatus(candOut,false);
  SeedWriteCsv(candOut,["construction","parent_seed","characteristic",
    "module_dimension","split_or_nonsplit","group_order","d_G","d_M",
    "maximality_certificate","independent_verification_status"]);
  hits:=0; escaping:=0; tested:=0;
  for pair in pairs do
    ## r=1 can never terminal-escape because H^(3) lies in V<=L=L^(0).
    if USDerivedLength(pair.B)>=2 then
      for p in SEED_PRIMES do
        tested:=tested+1; lift:=SeedUniversalGapThreeLift(pair,p);
        if lift<>fail then
          hits:=hits+1;
          if not lift.terminalContained then escaping:=escaping+1; fi;
          SeedWriteCsv(out,["universal_split_regular_quotient",lift.parent,
            lift.orderH,lift.dH,lift.orderL,lift.dL,lift.coreOrder,lift.dCore,
            lift.dTop,lift.terminalOrder,lift.terminalDimension,
            lift.terminalContained,
            Concatenation("PK_not_subset_JB; ranks=",String([
              lift.rankPK,lift.rankJB,lift.rankSum])),
            lift.candidateCharacteristics,"not_started_until_terminal_escape"]);
        fi;
      od;
    fi;
    SeedAppendCheckpoint(["lifted_pair",pair.key,"tested",tested,"hits",hits,
      "escaping",escaping]);
    GASMAN("collect");
  od;
  CloseStream(out); CloseStream(candOut);
  Print("RECURSIVE_SUMMARY pairs=",Length(pairs)," modular_tests=",tested,
    " gap3_lifts=",hits," terminal_escaping=",escaping,"\n");
end;

if SEED_MODE<>"library" then
  SeedPairs:=SeedExtractGapTwo();
  SeedWriteGapTwoDatabase(SeedPairs);
  Print("GAP2_SEEDS ",Length(SeedPairs),"\n");
  if SEED_MODE="all" or SEED_MODE="lift" then
    SeedSearchRecursiveLifts(SeedPairs);
  elif SEED_MODE<>"extract" then
    Error("SEED_MODE must be library, extract, lift, or all");
  fi;
fi;
