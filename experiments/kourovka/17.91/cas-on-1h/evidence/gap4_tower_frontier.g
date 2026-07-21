#############################################################################
## Kourovka 17.91: finite first-layer frontier for the Glasby-Howlett tower.
##
## For every irreducible F_2 H-module of dimension at most six, where H is
## the verified order-1296 gap-three group, compute the ambient/maximal
## derived module filtrations and *all* H-invariant quadratic forms.  A
## nondegenerate minus-type form is the datum needed to realize Q_3/Z(Q_3)
## for the extraspecial quaternion central product Q_3.
#############################################################################

if not IsBound(TOWER_CSV) then TOWER_CSV:="tower_frontier.csv"; fi;

US_MODE:="library";
Read("gap4_universal_split.g");

TowerCsvField:=function(value)
  local s;
  if IsString(value) then s:=value; else s:=String(value); fi;
  return Concatenation("\"",ReplacedString(s,"\"","\"\""),"\"");
end;

TowerWriteCsv:=function(out,row)
  PrintTo(out,JoinStringsWithSeparator(List(row,TowerCsvField),","),"\n");
end;

TowerAugmentationStep:=function(basis,subgroup,rho,field,dim)
  local vectors,identity,v,g,w;
  if Length(basis)=0 then return []; fi;
  vectors:=[]; identity:=IdentityMat(dim,field);
  for v in basis do for g in GeneratorsOfGroup(subgroup) do
    w:=v*(Image(rho,g)-identity);
    if not IsZero(w) then Add(vectors,w); fi;
  od; od;
  if Length(vectors)=0 then return []; fi;
  return BaseMat(vectors);
end;

TowerFiltrationDims:=function(group,rho,module)
  local basis,dims,series,i;
  basis:=IdentityMat(module.dimension,module.field);
  dims:=[module.dimension]; series:=DerivedSeriesOfGroup(group);
  for i in [1..Length(series)-1] do
    basis:=TowerAugmentationStep(basis,series[i],rho,module.field,
      module.dimension);
    Add(dims,Length(basis));
  od;
  return dims;
end;

TowerVectors:=function(n,field)
  return AsList(FullRowSpace(field,n));
end;

TowerQuadraticMonomials:=function(v)
  local n,result,i,j;
  n:=Length(v); result:=ShallowCopy(v);
  for i in [1..n-1] do for j in [i+1..n] do Add(result,v[i]*v[j]); od; od;
  return result;
end;

TowerInvariantQuadraticForms:=function(mats,n)
  local field,vectors,equations,g,v,w,kernel,space,forms,coeff,polar,
        i,j,pos,rank,zeros,plus,minus,degenerate;
  field:=GF(2); vectors:=TowerVectors(n,field); equations:=[];
  for g in mats do for v in vectors do
    w:=v*g;
    Add(equations,TowerQuadraticMonomials(w)+TowerQuadraticMonomials(v));
  od; od;
  equations:=BaseMat(equations);
  if Length(equations)=0 then
    kernel:=IdentityMat(n+n*(n-1)/2,field);
  else
    kernel:=NullspaceMat(TransposedMat(equations));
  fi;
  if Length(kernel)=0 then
    forms:=[Zero(FullRowSpace(field,n+n*(n-1)/2))];
  else
    space:=Subspace(FullRowSpace(field,n+n*(n-1)/2),kernel);
    forms:=AsList(space);
  fi;
  plus:=0; minus:=0; degenerate:=0;
  for coeff in forms do
    polar:=NullMat(n,n,field); pos:=n+1;
    for i in [1..n-1] do for j in [i+1..n] do
      polar[i][j]:=coeff[pos]; polar[j][i]:=coeff[pos]; pos:=pos+1;
    od; od;
    rank:=RankMat(polar);
    if rank<n then degenerate:=degenerate+1;
    else
      zeros:=Number(vectors,v->
        ScalarProduct(coeff,TowerQuadraticMonomials(v))=Zero(field));
      if zeros=2^(n-1)+2^(n/2-1) then plus:=plus+1;
      elif zeros=2^(n-1)-2^(n/2-1) then minus:=minus+1;
      else Error("nondegenerate quadratic form has unexpected zero count"); fi;
    fi;
  od;
  return rec(kernelDimension:=Length(kernel),formCount:=Length(forms),
    nondegeneratePlus:=plus,nondegenerateMinus:=minus,
    degenerate:=degenerate);
end;

TowerSeed:=USKnownSharpSeed();
TowerH:=TowerSeed.H; TowerL:=TowerSeed.L; TowerField:=GF(2);
TowerIrreds:=IrreducibleModules(TowerH,TowerField,6);
TowerBaseGens:=TowerIrreds[1]; TowerModules:=TowerIrreds[2];
TowerOut:=OutputTextFile(TOWER_CSV,false); SetPrintFormattingStatus(TowerOut,false);
TowerWriteCsv(TowerOut,["module_index","dimension","ambient_filtration",
  "maximal_filtration","kernel_order","image_order",
  "ambient_terminal_active","maximal_final_zero",
  "invariant_quadratic_space_dimension","invariant_quadratic_form_count",
  "nondegenerate_plus_forms","nondegenerate_minus_forms",
  "degenerate_forms","coherent_lift_status"]);

for TowerIndex in [1..Length(TowerModules)] do
  TowerModule:=TowerModules[TowerIndex];
  TowerMatGroup:=Group(TowerModule.generators);
  TowerRho:=GroupHomomorphismByImagesNC(TowerH,TowerMatGroup,TowerBaseGens,
    TowerModule.generators);
  TowerFDH:=TowerFiltrationDims(TowerH,TowerRho,TowerModule);
  TowerFDL:=TowerFiltrationDims(TowerL,TowerRho,TowerModule);
  TowerKernel:=Kernel(TowerRho);
  TowerQuadratics:=TowerInvariantQuadraticForms(TowerModule.generators,
    TowerModule.dimension);
  TowerWriteCsv(TowerOut,[TowerIndex,TowerModule.dimension,TowerFDH,TowerFDL,
    Order(TowerKernel),Order(Image(TowerRho)),
    Last(TowerFDH)>0,Last(TowerFDL)=0,TowerQuadratics.kernelDimension,
    TowerQuadratics.formCount,TowerQuadratics.nondegeneratePlus,
    TowerQuadratics.nondegenerateMinus,TowerQuadratics.degenerate,
    "finite inner-lift coherence equations not yet solved"]);
od;
CloseStream(TowerOut);
Print("TOWER_FRONTIER modules=",Length(TowerModules)," output=",TOWER_CSV,"\n");
