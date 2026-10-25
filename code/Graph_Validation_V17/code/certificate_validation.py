"""Authenticate recorded fields and validate their claimed policy decisions with SHACL-SPARQL."""
from pathlib import Path
import argparse,json,hashlib,sys,copy,collections
from rdflib import Graph,Namespace,RDF,Literal,URIRef
from pyshacl import validate
from route_policies import assess
R=Path(__file__).resolve().parents[1];P=R.parent
ap=argparse.ArgumentParser();ap.add_argument('--data-root',type=Path,default=P);D=ap.parse_args().data_root
sys.path.insert(0,str(P/'Validation_Study/code'));from reference_oracle import Reference
ref=Reference(D/'Graph_Validation_V9/temporal_snapshot')
rows=json.loads((D/'Graph_Validation_V16/results/route_decisions.json').read_text())
EX=Namespace('https://example.org/medigraph/evidence/')
def uri(kind,value):return URIRef(str(EX)+kind+'/'+hashlib.sha256(value.encode()).hexdigest())
policy_hash=hashlib.sha256((R/'code/route_policies.py').read_bytes()).hexdigest()
targets={'coarse':'coarse_package_route_compatibility','exact_code':'recorded_route_code_compatibility','explicit_formulation':'formulation_supported_route_compatibility'}
sources=Graph();canonical={}
for x in rows:
 w=uri('witness',x['witness']);t=uri('tariff',x['tariff_record']);sl=ref.records[x['SL_record']];tar=ref.records[x['tariff_record']];a=ref.witnesses[x['witness']]
 assert a['subject']==x['product'] and a['atc']==x['code']==sl['atc']==tar['code']
 assert x['SL_record'] in a['premise_ids'] and a['atc_index_snapshot_sha256']==x['snapshot']
 assert sl['gammenbezeichnung']==x['recorded_group'] and sl['bezeichnung']==x['package'] and tar['va']==x['tariff_routes']
 sources.add((w,EX.group,Literal(sl['gammenbezeichnung'])));sources.add((w,EX.package,Literal(sl['bezeichnung'])));sources.add((w,EX.snapshot,Literal(a['atc_index_snapshot_sha256'])))
 sources.add((w,EX.allowedTariff,t));sources.add((t,EX.routes,Literal(tar['va'])))
 for p in x['premise_ids']:
  assert p in ref.records
  pair=uri('pair',x['witness']+x['tariff_record']);sources.add((pair,EX.witness,w));sources.add((pair,EX.tariff,t));sources.add((pair,EX.requiresPremise,uri('source',p)))
 for token in {r.strip() for r in tar['va'].split(',') if r.strip()}:sources.add((t,EX.option,Literal(token)))
 for policy,target in targets.items():
  key=(x['witness'],x['tariff_record'],policy)
  canonical[key]={'witness':x['witness'],'tariff_record':x['tariff_record'],'policy':policy,'policy_hash':policy_hash,'target':target,'status':assess(sl['gammenbezeichnung'],sl['bezeichnung'],tar['va'],policy),'group':sl['gammenbezeichnung'],'package':sl['bezeichnung'],'routes':tar['va'],'snapshot':a['atc_index_snapshot_sha256'],'premises':x['premise_ids']}
for policy,target in targets.items():
 p=EX[policy];sources.add((p,EX.expectedHash,Literal(policy_hash)));sources.add((p,EX.expectedTarget,Literal(target)))
def accepted(c):
 expected=canonical.get((c.get('witness'),c.get('tariff_record'),c.get('policy')))
 return expected is not None and c==expected
def add(c,g,node):
 g.add((node,RDF.type,EX.DecisionCertificate))
 fields={'pair':uri('pair',c['witness']+c['tariff_record']),'witness':uri('witness',c['witness']),'tariff':uri('tariff',c['tariff_record']),'policy':EX[c['policy']]}
 for k in ['policy_hash','target','status','group','package','routes','snapshot']:fields[k]=Literal(c[k])
 for k,v in fields.items():g.add((node,EX[k],v))
 for p in c['premises']:g.add((node,EX.premise,uri('source',p)))
# Both structure and semantics are checked. Trusted source facts are admitted from Reference.
binding='''PREFIX ex: <https://example.org/medigraph/evidence/>
SELECT $this WHERE {
 $this ex:pair ?pair; ex:witness ?w; ex:tariff ?t; ex:policy ?policy; ex:policy_hash ?hash; ex:target ?target; ex:snapshot ?snapshot; ex:group ?g; ex:package ?pkg; ex:routes ?r.
 FILTER (NOT EXISTS {?pair ex:witness ?w; ex:tariff ?t. ?w ex:allowedTariff ?t; ex:snapshot ?snapshot; ex:group ?g; ex:package ?pkg. ?t ex:routes ?r. ?policy ex:expectedHash ?hash; ex:expectedTarget ?target}
 || EXISTS {?pair ex:requiresPremise ?p FILTER NOT EXISTS {$this ex:premise ?p}}
 || EXISTS {$this ex:premise ?p FILTER NOT EXISTS {?pair ex:requiresPremise ?p}})
}'''
decision=r'''PREFIX ex: <https://example.org/medigraph/evidence/>
SELECT $this WHERE {
 $this ex:witness ?w; ex:tariff ?t; ex:policy ?policy; ex:status ?claimed.
 ?w ex:group ?g; ex:package ?pkg.
 BIND(REGEX(LCASE(?g), "(^|\\s)oral(retard|fluessig|flüssig)?\\s*$") AS ?oral)
 BIND(REGEX(LCASE(?g), "(^|\\s)parenteral(depot)?\\s*$") AS ?par)
 BIND(?policy=ex:coarse AS ?coarse)
 BIND(?policy=ex:explicit_formulation AS ?strict)
 BIND(!?strict || REGEX(LCASE(?pkg), "\\b(filmtabl|tabl|kaps)\\b") AS ?oralForm)
 BIND(!?strict || REGEX(LCASE(?pkg), "\\b(inf|inj|trockensub)\\b") AS ?parForm)
 BIND(?oral && ?oralForm AS ?hasO)
 BIND(?par && ?parForm && (?coarse || REGEX(LCASE(?pkg), "(^|[^\\w])i\\.?\\s*v\\.?([^\\w]|$)")) AS ?hasIV)
 BIND(?par && ?parForm && (?coarse || REGEX(LCASE(?pkg), "(^|[^\\w])s\\.?\\s*c\\.?([^\\w]|$)|\\bsubkutan\\b")) AS ?hasSC)
 BIND(?par && ?parForm && (?coarse || REGEX(LCASE(?pkg), "(^|[^\\w])i\\.?\\s*m\\.?([^\\w]|$)")) AS ?hasIM)
 BIND(?par && ?parForm && (?coarse || REGEX(LCASE(?pkg), "(^|[^\\w])i\\.?\\s*t\\.?([^\\w]|$)")) AS ?hasIT)
 BIND(?hasO || ?hasIV || ?hasSC || ?hasIM || ?hasIT AS ?available)
 BIND(EXISTS {?t ex:option ?v FILTER((?v="O" && ?hasO) || (?v="IV" && ?hasIV) || (?v="SC" && ?hasSC) || (?v="IM" && ?hasIM) || (?v="IT" && ?hasIT))} AS ?overlap)
 BIND(EXISTS {?t ex:option ?v FILTER(IF(?coarse, ?v NOT IN ("O","IV","SC","IM","IT"), ?v NOT IN ("O","IV","SC","IM","IT","SR","Inhal","ET")))} AS ?unknown)
 BIND(IF(!?available || NOT EXISTS {?t ex:option ?v}, "UNDETERMINED", IF(?overlap,"VERIFIED",IF(?unknown,"UNDETERMINED","CONTRADICTED"))) AS ?expected)
 FILTER(?claimed != ?expected)
}'''
shape=Graph();SH=Namespace('http://www.w3.org/ns/shacl#');S=EX.DecisionShape
shape.add((S,RDF.type,SH.NodeShape));shape.add((S,SH.targetClass,EX.DecisionCertificate))
for field in ['pair','witness','tariff','policy','policy_hash','target','status','group','package','routes','snapshot']:
 n=EX['field-'+field];shape.add((S,SH.property,n));shape.add((n,SH.path,EX[field]));shape.add((n,SH.minCount,Literal(1)));shape.add((n,SH.maxCount,Literal(1)))
for name,query in [('SourceBinding',binding),('DecisionMeaning',decision)]:
 n=EX[name];shape.add((S,SH.sparql,n));shape.add((n,SH.select,Literal(query)));shape.add((n,SH.message,Literal(name)))
shape.serialize(R/'ontology/decision_shapes.ttl',format='turtle')
g=Graph()
for triple in sources:g.add(triple)
for i,c in enumerate(canonical.values()):assert accepted(c);add(c,g,EX['faithful-'+str(i)])
core=Graph()
for triple in shape:
 if not(triple[0]==S and triple[1]==SH.sparql):core.add(triple)
ok,report,report_text=validate(g,shacl_graph=core);assert ok,report_text[:4000]
for query in [binding,decision]:
 violations=list(g.query(query.replace('$this','?certificate')));assert not violations,str(violations[:5])
print('Complete source-binding and decision constraint queries pass.',flush=True)
# Mutate all three complete policies imperatively; declarative mutants are stratified by status/policy.
families=['status','target','routes','premise','snapshot','policy_hash','witness']
def mutate(c,f):
 c=copy.deepcopy(c)
 if f=='status':c[f]='CONTRADICTED' if c[f]=='VERIFIED' else 'VERIFIED'
 elif f=='target':c[f]='current_payment_eligibility'
 elif f=='routes':c[f]='O' if c[f]!='O' else 'IV'
 elif f=='premise':c['premises']=c['premises'][1:]
 elif f=='witness':c[f]='not-an-authenticated-witness'
 else:c[f]='unavailable'
 return c
mutants=0;sample={}
for c in canonical.values():
 sample.setdefault((c['policy'],c['status']),c)
 for f in families:assert not accepted(mutate(c,f));mutants+=1
bad=Graph()
for triple in sources:bad.add(triple)
nodes=set();labels={}
for c in sample.values():
 for f in families:
  n=EX['mutant-'+str(len(nodes))];nodes.add(n);labels[str(n)]=f;add(mutate(c,f),bad,n)
ok,report,_=validate(bad,shacl_graph=shape);assert not ok
reported={str(o) for o in report.objects(None,SH.focusNode)};assert reported=={str(n) for n in nodes},(len(reported),len(nodes))
result={'faithful_certificates':len(canonical),'complete_declarative_constraint_agreement':True,'batch_constraint_engine':'RDFLib SPARQL over every certificate; identical SHACL constraint SELECT bodies','full_core_SHACL_conformance':True,'complete_source_authentication':True,'imperative_mutant_rejections':mutants,'mutant_families':families,'SHACL_stratified_mutant_rejections':len(nodes),'strata':len(sample),'all_stratified_mutants_rejected':True,'source_records_and_policy_fields_checked':True,'scope':'Certificate source binding and declared decision meaning; not independent clinical correctness.'}
(R/'results/certificate_validation.json').write_text(json.dumps(result,indent=2));(R/'results/declarative_mutant_families.json').write_text(json.dumps(dict(collections.Counter(labels.values())),indent=2));print(json.dumps(result,indent=2))
