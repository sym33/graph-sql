"""Isolate the ontology layer over an identical, already admitted evidence ABox."""
from pathlib import Path
import argparse,json,time,hashlib
from rdflib import Graph,Namespace,RDF,OWL
from owlrl import DeductiveClosure,OWLRL_Semantics
R=Path(__file__).resolve().parents[1];P=R.parent
ap=argparse.ArgumentParser();ap.add_argument('--data-root',type=Path,default=P);D=ap.parse_args().data_root
EX=Namespace('https://example.org/medigraph/evidence/')
source=Graph().parse(D/'Graph_Validation_V15/results/inference_input.ttl')
predicates=[EX.documentaryTariff,EX.historicalTariff,EX.recordedBroaderGroup,EX.ingredientTariffCandidate]
def pairs(g):return {str(p).split('/')[-1]:set((str(s),str(o)) for s,o in g.subject_objects(p)) for p in predicates}
def explicit(g):
 out={str(p).split('/')[-1]:set() for p in predicates};doc={}
 for prop,target in [(EX.recordedCode,'documentaryTariff'),(EX.historicalCode,'historicalTariff')]:
  for w,code in g.subject_objects(prop):
   for tariff in g.objects(code,EX.listedByTariff):out[target].add((str(w),str(tariff)))
   if prop==EX.recordedCode:
    for parent in g.objects(code,EX.broader):out['recordedBroaderGroup'].add((str(w),str(parent)))
 for w,ingredient in g.subject_objects(EX.ingredientDeclaration):
  for sw,t in out['documentaryTariff']:
   if sw==str(w):out['ingredientTariffCandidate'].add((str(ingredient),t))
 return out
reference=explicit(source);summary={};timings={};digests={}
for policy in ['full','no_ontology','without_documentary_chain','without_historical_chain','without_broader_chain','without_ingredient_chain']:
 g=Graph()
 for triple in source:g.add(triple)
 if policy=='no_ontology':
  for s,p,o in list(g):
   if str(p).startswith(str(OWL)) or (p==RDF.type and str(o).startswith(str(OWL))) or isinstance(s,__import__('rdflib').BNode):g.remove((s,p,o))
 else:
  remove={'without_documentary_chain':EX.documentaryTariff,'without_historical_chain':EX.historicalTariff,'without_broader_chain':EX.recordedBroaderGroup,'without_ingredient_chain':EX.ingredientTariffCandidate}.get(policy)
  if remove:g.remove((remove,OWL.propertyChainAxiom,None))
 started=time.perf_counter()
 if policy!='no_ontology':DeductiveClosure(OWLRL_Semantics).expand(g)
 timings[policy]=round(time.perf_counter()-started,3);actual=pairs(g)
 if policy=='full':assert actual==reference
 if policy=='no_ontology':assert all(not x for x in actual.values())
 expected={k:set(v) for k,v in reference.items()}
 if policy=='without_documentary_chain':expected['documentaryTariff']=set();expected['ingredientTariffCandidate']=set()
 if policy=='without_historical_chain':expected['historicalTariff']=set()
 if policy=='without_broader_chain':expected['recordedBroaderGroup']=set()
 if policy=='without_ingredient_chain':expected['ingredientTariffCandidate']=set()
 if policy not in {'full','no_ontology'}:assert actual==expected
 summary[policy]={k:len(v) for k,v in actual.items()}
 digests[policy]={k:hashlib.sha256(json.dumps(sorted(v),separators=(',',':')).encode()).hexdigest() for k,v in actual.items()}
summary['explicit_rules']={k:len(v) for k,v in reference.items()}
result={'policies':summary,'complete_output_digests':digests,'complete_explicit_rule_agreement':True,'fixed_ABox':True,'interpretation':'Ontology axioms determine materialized inference predicates and dependency propagation; explicitly programmed equivalent rules recover all tested outputs. No demonstrated advantage in accuracy or expressive power for these tasks.','run_seconds_descriptive_only':timings}
(R/'results/ontology_ablation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
