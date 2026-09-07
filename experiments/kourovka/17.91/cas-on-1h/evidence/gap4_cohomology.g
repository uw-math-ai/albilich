#############################################################################
## Kourovka 17.91: prioritized nonsplit-extension frontier.
## GAP 4.16+ native pc cohomology.
##
## The restriction class is tested concretely: an H^2 class restricts to zero
## on L iff the full inverse image of L has a complement to the elementary
## abelian kernel.  This avoids inferring anything nonsplit from the regular
## split-ideal computation.
#############################################################################

if not IsBound(COH_MODE) then COH_MODE:="heisenberg_q8_frontier"; fi;
if not IsBound(COH_PRIMES) then COH_PRIMES:=[2]; fi;
if not IsBound(COH_MIN_DIM) then COH_MIN_DIM:=7; fi;
if not IsBound(COH_MAX_DIM) then COH_MAX_DIM:=12; fi;
if not IsBound(COH_CLASS_CAP) then COH_CLASS_CAP:=512; fi;
if not IsBound(COH_CSV) then COH_CSV:="h2_frontier.csv"; fi;
if not IsBound(COH_CHECKPOINT) then
  COH_CHECKPOINT:="checkpoints/cohomology.checkpoint";
fi;

US_MODE:="library";
Read("gap4_universal_split.g");

CohCsvField:=function(value)
  local s;
  if value=fail then s:="";
  elif IsString(value) then s:=value;
  else s:=String(value); fi;
  return Concatenation("\"",ReplacedString(s,"\"","\"\""),"\"");
end;

CohWriteCsv:=function(out,row)
  PrintTo(out,JoinStringsWithSeparator(List(row,CohCsvField),","),"\n");
end;

CohCheckpoint:=function(parts)
  local out;
  out:=OutputTextFile(COH_CHECKPOINT,true); SetPrintFormattingStatus(out,false);
  PrintTo(out,JoinStringsWithSeparator(List(parts,String),"|"),"\n");
  CloseStream(out);
end;

CohProjectionToBase:=function(extension,base,moduleDimension)
  return GroupHomomorphismByImagesNC(extension,base,Pcgs(extension),
    Concatenation(Pcgs(base),List([1..moduleDimension],i->One(base))));
end;

CohPairHeisenbergQ8:=function()
  local h,classes;
  h:=SmallGroup(216,88);
  classes:=Filtered(ConjugacyClassesMaximalSubgroups(h),c->
    IdGroup(Representative(c))=[24,11]);
  if Length(classes)<>1 then Error("Heisenberg-Q8 maximal class not unique"); fi;
  return rec(name:="SG216_88__SG24_11",H:=h,L:=Representative(classes[1]),
    targetGap:=3,terminalPrerequisite:="not_applicable_gap2_parent");
end;

CohPairKnownGap3:=function()
  local seed;
  seed:=USKnownSharpSeed();
  return rec(name:=seed.name,H:=seed.H,L:=seed.L,targetGap:=4,
    terminalPrerequisite:="contained_prune");
end;

CohRestrictionSplits:=function(preimage,kernel)
  local caught;
  caught:=CALL_WITH_CATCH(function()
    return Length(ComplementClassesRepresentatives(preimage,kernel))>0;
  end,[]);
  if not caught[1] then return fail; fi;
  return caught[2];
end;

CohRunPair:=function(pair,out)
  local h,l,p,irreds,basegens,modules,j,module,h2caught,h2,h2dim,classCount,
        extcaught,extensions,k,g,projection,m,kernel,resZero,dg,dm,gap,
        terminalContained,seriesG,seriesM,constructed,skipped;
  h:=pair.H; l:=pair.L; constructed:=0; skipped:=0;
  for p in COH_PRIMES do
    irreds:=IrreducibleModules(h,GF(p),COH_MAX_DIM);
    basegens:=irreds[1]; modules:=irreds[2];
    for j in [1..Length(modules)] do
      module:=modules[j];
      if module.dimension>=COH_MIN_DIM and module.dimension<=COH_MAX_DIM then
        h2caught:=CALL_WITH_CATCH(function() return TwoCohomology(h,module); end,[]);
        if not h2caught[1] then
          CohWriteCsv(out,[pair.name,p,j,module.dimension,"failed","","","",
            "","","","TwoCohomology_failed","not_classified"]);
        else
          h2:=h2caught[2]; h2dim:=Dimension(Image(h2.cohom));
          classCount:=p^h2dim;
          if classCount>COH_CLASS_CAP then
            skipped:=skipped+1;
            CohWriteCsv(out,[pair.name,p,j,module.dimension,h2dim,classCount,"",
              "","","","","class_cap_exceeded",
              Concatenation("all ",String(classCount),
                " cohomology classes remain; Aut_H(A) orbit reduction not computed")]);
          else
            extcaught:=CALL_WITH_CATCH(function() return Extensions(h,module); end,[]);
            if not extcaught[1] then
              CohWriteCsv(out,[pair.name,p,j,module.dimension,h2dim,classCount,
                "","","","","","Extensions_failed","all_classes_unconstructed"]);
            else
              extensions:=extcaught[2];
              for k in [1..Length(extensions)] do
                g:=extensions[k];
                projection:=CohProjectionToBase(g,h,module.dimension);
                m:=PreImage(projection,l); kernel:=Kernel(projection);
                resZero:=CohRestrictionSplits(m,kernel);
                dg:=USDerivedLength(g); dm:=USDerivedLength(m); gap:=dg-dm;
                seriesG:=DerivedSeriesOfGroup(g); seriesM:=DerivedSeriesOfGroup(m);
                if gap=3 then
                  terminalContained:=IsSubgroup(seriesM[dm],seriesG[dm+3]);
                else terminalContained:=fail; fi;
                constructed:=constructed+1;
                CohWriteCsv(out,[pair.name,p,j,module.dimension,h2dim,classCount,
                  k-1,resZero,Order(g),dg,dm,gap,terminalContained,
                  "class_constructed_and_restriction_tested"]);
              od;
            fi;
          fi;
        fi;
        CohCheckpoint([pair.name,p,j,module.dimension,"constructed",constructed,
          "skipped_modules",skipped]);
      fi;
    od;
  od;
  return rec(constructed:=constructed,skippedModules:=skipped);
end;

CohOut:=OutputTextFile(COH_CSV,false); SetPrintFormattingStatus(CohOut,false);
CohWriteCsv(CohOut,["parent_seed","characteristic","module_index",
  "module_dimension","h2_dimension","class_count","class_index",
  "restriction_class_zero","extension_order","d_ambient","d_preimage",
  "gap","terminal_contained_if_gap3","status"]);

if COH_MODE="known_gap3_pruned" then
  CohPair:=CohPairKnownGap3();
  CohWriteCsv(CohOut,[CohPair.name,"all","all","all","","","","","",
    6,3,3,true,
    "pruned_without_H2: terminal containment excludes an exceptional gap4 lift"]);
  Print("COHOMOLOGY_PRUNED known gap-three seed is terminal-contained\n");
elif COH_MODE="heisenberg_q8_frontier" then
  CohPair:=CohPairHeisenbergQ8();
  CohSummary:=CohRunPair(CohPair,CohOut);
  Print("COHOMOLOGY_SUMMARY ",CohSummary,"\n");
else
  Error("unknown COH_MODE");
fi;
CloseStream(CohOut);
