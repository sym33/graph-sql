"""Evidence-scoped OWL-RL chains, independently reconstructed SQL, and SHACL.
Outputs are documentary tariff candidates; product/payment validity is not entailed.
"""
from pathlib import Path
import sys,json,hashlib,collections,copy,importlib.metadata,argparse
from rdflib import Graph,Namespace,RDF,Literal,URIRef
from owlrl import DeductiveClosure,OWLRL_Semantics
from pyshacl import validate
R=Path(__file__).resolve().parents[1];P=R.parent
parser=argparse.ArgumentParser();parser.add_argument('--data-root',type=Path,default=P);D=parser.parse_args().data_root
sys.path.insert(0,str(P/'Validation_Study/code'))
sys.path.insert(0,str(P/'Graph_Validation_V14/code'))
from reference_oracle import Reference,canonical_hash
from context_contract import evaluate_classification
EX=Namespace('https://example.org/medigraph/evidence/')
def uri(kind,value):return URIRef(str(EX)+kind+'/'+hashlib.sha256(value.encode()).hexdigest())
ref=Reference(D/'Graph_Validation_V9/temporal_snapshot')
bundles=json.loads((D/'Graph_Validation_V9/results/temporal_physical_bundles.json').read_text())
assert {b['association']['id']:b['association'] for b in bundles}==ref.witnesses
byid={b['association']['id']:b for b in bundles}
tariffs={rid:row for rid,row in ref.records.items() if rid.startswith('ze_definitions.csv:')}
codes={rid:row['code'] for rid,row in tariffs.items()}
index=collections.defaultdict(list)
for rid,code in codes.items():index[code].append(rid)
# Independently expressed relational candidate join. No observed graph outputs supplied.
ref.db.execute('CREATE TABLE tariff(rid TEXT,code TEXT)');ref.db.executemany('INSERT INTO tariff VALUES(?,?)',codes.items())
ref.db.execute('CREATE TABLE derivation(id TEXT,product TEXT,code TEXT,rule TEXT,jurisdiction TEXT)')
ref.db.executemany('INSERT INTO derivation VALUES(?,?,?,?,?)',[(a['id'],a['subject'],a['atc'],a['rule'],a['jurisdiction']) for a in ref.witnesses.values()])
sql="SELECT d.id,t.rid FROM derivation d JOIN tariff t ON d.code=t.code WHERE d.jurisdiction='CH' AND d.rule IN ('direct_SAI','via_authorization_SL') ORDER BY d.id,t.rid"
(R/'queries/tariff_candidates.sql').write_text(sql+';\n')
expected={tuple(x) for x in ref.db.execute(sql)}
def classification_claim(a):
 return {**a,'witness':a['id'],'kind':'documentary_association','source_snapshot':ref.files['atc_list.csv'],'time_scope':'frozen_documentary'}
def assess_tariff(claim,bundle,tariff_payload):
 # Authenticate source derivation and requested snapshot before comparing fields.
 d=evaluate_classification(claim,bundle,ref)
 if d['verdict']!='VERIFIED':return d['verdict']
 rid=claim.get('tariff_record')
 if rid not in tariffs or tariffs[rid]!=tariff_payload:return 'UNDETERMINED'
 if claim.get('tariff_version')!=tariff_payload.get('version'):return 'UNDETERMINED'
 if claim.get('target') not in {'documentary_tariff_candidate','historical_tariff_review_candidate'}:return 'UNDETERMINED'
 a=bundle['association']
 if a['jurisdiction']!='CH':return 'UNDETERMINED'
 if (a['rule']=='historical_candidate')!=(claim['target']=='historical_tariff_review_candidate'):return 'UNDETERMINED'
 if a['atc']!=tariff_payload.get('code') or claim.get('tariff_code')!=tariff_payload.get('code'):return 'CONTRADICTED'
 return 'VERIFIED'
records=[];historical=[];outscope=[]
for b in bundles:
 a=b['association'];ts=index.get(a['atc'],[])
 if not ts:continue
 decision=evaluate_classification(classification_claim(a),b,ref)
 assert decision['verdict']=='VERIFIED',decision
 for tid in ts:
  item={'witness':a['id'],'product':a['subject'],'code':a['atc'],'tariff_record':tid,'tariff':tariffs[tid]['ze_code'],'tariff_version':tariffs[tid]['version'],'premise_ids':sorted(a['premise_ids']+[tid]),'rule':a['rule'],'jurisdiction':a['jurisdiction'],'target':'documentary_tariff_candidate','snapshot':a['atc_index_snapshot_sha256'],'classification_recording':'June replay','status':'VERIFIED','current_payment_eligibility':'UNDETERMINED'}
  if a['jurisdiction']!='CH':item['status']='UNDETERMINED';item['reason']='unavailable_Swiss_product_identity';outscope.append(item)
  elif a['rule']=='historical_candidate':item['target']='historical_tariff_review_candidate';historical.append(item)
  else:records.append(item)
assert {(x['witness'],x['tariff_record']) for x in records}==expected
# RDF only contains admissible Swiss documentary and separately marked historical witnesses.
g=Graph().parse(R/'ontology/medication_evidence.ttl');shapes=Graph().parse(R/'ontology/inference_shapes.ttl')
for rid,code in codes.items():
 t=uri('tariff',rid);c=uri('code',code);g.add((t,RDF.type,EX.SwissTariffRecord));g.add((c,RDF.type,EX.ATCConcept));g.add((c,EX.listedByTariff,t))
parents=[]
for code in sorted(ref.atc):
 for n in [1,3,4,5]:
  parent=code[:n]
  if n<len(code) and parent in ref.atc:
   parents.append((code,parent));g.add((uri('code',code),EX.broader,uri('code',parent)));g.add((uri('code',parent),RDF.type,EX.ATCConcept))
selected={x['witness']:x for x in records+historical}
ingredients={};ingredient_expected=set()
for wid,item in selected.items():
 w=uri('witness',wid);p=uri('product',item['product']);c=uri('code',item['code']);hist=item['rule']=='historical_candidate'
 g.add((w,RDF.type,EX.HistoricalWitness if hist else EX.DocumentaryWitness));g.add((w,EX.historicalCode if hist else EX.recordedCode,c));g.add((c,RDF.type,EX.ATCConcept));g.add((w,EX.subject,p));g.add((p,RDF.type,EX.SwissProduct));g.add((w,EX.snapshot,Literal(item['snapshot'])))
 for rid in byid[wid]['association']['premise_ids']:u=uri('source',rid);g.add((u,RDF.type,EX.SourceRecord));g.add((w,EX.premise,u))
# Ingredient declarations are source-row entities, never presumed molecule identities.
for item in records:
 if item['rule']!='via_authorization_SL':continue
 for rid in byid[item['witness']]['association']['premise_ids']:
  if not rid.startswith('sl.csv:'):continue
  text=ref.records[rid].get('substanzen','')
  if not text or text.strip().casefold() in {'na','n/a','null','none','nan'}:continue
  u=uri('ingredient-declaration',rid);w=uri('witness',item['witness'])
  g.add((u,RDF.type,EX.IngredientDeclaration));g.add((u,EX.lexicalValue,Literal(text)));g.add((w,EX.ingredientDeclaration,u));g.add((u,EX.sourceRecord,uri('source',rid)))
  ingredients[rid]=text;ingredient_expected.add((rid,item['tariff_record']))
g.serialize(R/'results/inference_input.ttl',format='turtle')
initial=len(g);DeductiveClosure(OWLRL_Semantics).expand(g)
actual={(wid,tid) for wid in selected for tid in codes if (uri('witness',wid),EX.documentaryTariff,uri('tariff',tid)) in g};assert actual==expected
hp={(x['witness'],x['tariff_record']) for x in historical};ha={(wid,tid) for wid in selected for tid in codes if (uri('witness',wid),EX.historicalTariff,uri('tariff',tid)) in g};assert hp==ha
bp={(wid,parent) for wid,item in selected.items() if item['rule']!='historical_candidate' for code,parent in parents if code==item['code']}
ba={(wid,str(parent)) for wid in selected for parent in g.objects(uri('witness',wid),EX.recordedBroaderGroup)};assert ba=={(wid,str(uri('code',parent))) for wid,parent in bp}
ingredient_sql="SELECT DISTINCT l.rid,t.rid FROM sai s JOIN sl l ON s.auth=l.auth JOIN tariff t ON l.code=t.code JOIN input i ON i.rid=l.rid WHERE lower(trim(coalesce(json_extract(i.payload,'$.substanzen'),''))) NOT IN ('','na','n/a','null','none','nan')"
assert {tuple(x) for x in ref.db.execute(ingredient_sql)}==ingredient_expected
(R/'queries/ingredient_tariff.sql').write_text(ingredient_sql+';\n')
ingredient_actual={(rid,tid) for rid in ingredients for tid in codes if (uri('ingredient-declaration',rid),EX.ingredientTariffCandidate,uri('tariff',tid)) in g};assert ingredient_actual==ingredient_expected
ingredient_certificates=[]
for rid,tid in sorted(ingredient_expected):
 support=[x for x in records if x['tariff_record']==tid and rid in x['premise_ids'] and x['rule']=='via_authorization_SL']
 assert support
 ingredient_certificates.append({'ingredient_declaration_record':rid,'recorded_ingredient':ingredients[rid],'tariff_record':tid,'tariff':tariffs[tid]['ze_code'],'witness_ids':sorted({x['witness'] for x in support}),'premise_ids':sorted({p for x in support for p in x['premise_ids']}),'inference_rule':'declaredInWitness/documentaryTariff','scope':'Recorded SL ingredient declaration, not verified molecule identity'})
(R/'results/ingredient_tariff_candidates.json').write_text(json.dumps(ingredient_certificates,indent=2))
dictionary_records=collections.defaultdict(list)
for rid,row in ref.records.items():
 if rid.startswith('atc_list.csv:'):dictionary_records[row['atc_code']].append(rid)
broader_certificates=[]
for wid,parent in sorted(bp):
 a=byid[wid]['association'];assert dictionary_records[a['atc']] and dictionary_records[parent]
 broader_certificates.append({'witness':wid,'product':a['subject'],'recorded_code':a['atc'],'broader_code':parent,'inference_rule':'recordedCode/dictionary_supported_broader','premise_ids':sorted(a['premise_ids']+dictionary_records[a['atc']]+dictionary_records[parent]),'dictionary_snapshot':ref.files['atc_list.csv'],'scope':'Recorded classification generalization, not clinical treatment inference'})
(R/'results/broader_group_certificates.json').write_text(json.dumps(broader_certificates,indent=2))
conforms,report,_=validate(g,shacl_graph=shapes,inference='none');assert conforms
# OWL-RL materialization is not a full OWL-DL consistency certificate.
violations=[]
for c1,c2 in g.subject_objects(URIRef('http://www.w3.org/2002/07/owl#disjointWith')):
 violations.extend(str(x) for x in g.subjects(RDF.type,c1) if (x,RDF.type,c2) in g)
assert not violations
# Certificate challenge: all documentary candidates, exactly one defect per family.
challenges=collections.Counter();casefile=R/'results/inference_challenges.jsonl'
with casefile.open('w') as f:
 for item in records:
  b=byid[item['witness']];a=b['association']
  for family in ['faithful','missing_source','wrong_endpoint','wrong_snapshot','current_payment','wrong_tariff','wrong_jurisdiction','tampered_tariff_source','unavailable_tariff_version']:
   claim={**classification_claim(a),'tariff_record':item['tariff_record'],'tariff_code':item['code'],'target':item['target'],'tariff_version':item['tariff_version']};bundle=copy.deepcopy(b);tariff_payload=copy.deepcopy(tariffs[item['tariff_record']])
   if family=='missing_source':bundle['records']=[]
   elif family=='wrong_endpoint':bundle['products']=[]
   elif family=='wrong_snapshot':claim['source_snapshot']='other'
   elif family=='wrong_jurisdiction':claim['jurisdiction']='EU'
   if family=='current_payment':claim['target']='current_payment_eligibility'
   if family=='wrong_tariff':claim['tariff_code']=item['code']+'X'
   if family=='tampered_tariff_source':tariff_payload['code']='invalid'
   if family=='unavailable_tariff_version':claim['tariff_version']='unavailable'
   status=assess_tariff(claim,bundle,tariff_payload)
   expected_status={'faithful':'VERIFIED','wrong_tariff':'CONTRADICTED','wrong_jurisdiction':'CONTRADICTED'}.get(family,'UNDETERMINED')
   assert status==expected_status,(family,status)
   challenges[family+':'+status]+=1;f.write(json.dumps({'witness':item['witness'],'tariff_record':item['tariff_record'],'family':family,'status':status})+'\n')
# Historical and cross-authority candidates must never be silently promoted.
blocked={}
for label,items in [('historical_promotion',historical),('EU_to_Swiss',outscope)]:
 for item in items:
  a=byid[item['witness']]['association'];claim={**classification_claim(a),'tariff_record':item['tariff_record'],'tariff_code':item['code'],'tariff_version':item['tariff_version'],'target':'documentary_tariff_candidate'}
  assert assess_tariff(claim,byid[item['witness']],tariffs[item['tariff_record']])=='UNDETERMINED'
 blocked[label]=len(items)
# Declarative checks actually exercised: cloned minimal certificates, independent of labels.
probe=next(x for x in records);w=uri('witness',probe['witness']);c=uri('code',probe['code']);p=uri('product',probe['product']);t=uri('tariff',probe['tariff_record']);s=uri('source',probe['premise_ids'][0])
def fixture():
 h=Graph()
 for triple in [(w,RDF.type,EX.DocumentaryWitness),(p,RDF.type,EX.SwissProduct),(c,RDF.type,EX.ATCConcept),(t,RDF.type,EX.SwissTariffRecord),(s,RDF.type,EX.SourceRecord),(w,EX.subject,p),(w,EX.recordedCode,c),(w,EX.documentaryTariff,t),(w,EX.premise,s),(w,EX.snapshot,Literal(probe['snapshot']))]:h.add(triple)
 return h
checks={}
for family in ['faithful','missing_premise','wrong_product_type','missing_snapshot','historical_leakage']:
 h=fixture()
 if family=='missing_premise':h.remove((w,EX.premise,None))
 if family=='wrong_product_type':h.remove((p,RDF.type,EX.SwissProduct));h.add((p,RDF.type,EX.EuropeanMedicine))
 if family=='missing_snapshot':h.remove((w,EX.snapshot,None))
 if family=='historical_leakage':h.remove((w,RDF.type,EX.DocumentaryWitness));h.add((w,RDF.type,EX.HistoricalWitness));h.add((w,EX.historicalCode,c))
 ok,_,_=validate(h,shacl_graph=shapes,inference='none');assert bool(ok)==(family=='faithful');checks[family]=bool(ok)
base={(x['product'],x['tariff_record']) for x in records if x['rule']=='direct_SAI'};allpairs={(x['product'],x['tariff_record']) for x in records};added=allpairs-base
hproducts={x['product'] for x in historical}-{x['product'] for x in records}
(R/'results/documentary_candidates.json').write_text(json.dumps(records,indent=2));(R/'results/historical_candidates.json').write_text(json.dumps(historical,indent=2));(R/'results/out_of_scope_candidates.json').write_text(json.dumps(outscope,indent=2))
summary={'witness_tariff_derivations':len(records),'unique_product_tariff_candidates':len(allpairs),'products':len({x['product'] for x in records}),'tariff_records':len({x['tariff_record'] for x in records}),'additional_SL_product_tariff_pairs':len(added),'additional_SL_examples':[x for x in records if (x['product'],x['tariff_record']) in added][:8],'historical_derivations':len(historical),'historical_only_products':len(hproducts),'out_of_scope_EU_derivations':len(outscope),'recorded_broader_group_derivations':len(bp),'ingredient_declaration_tariff_pairs':len(ingredient_expected),'ingredient_declarations':len(ingredients),'OWL_RL_complete_agreement':True,'SQL_complete_agreement':True,'SHACL_conforms':bool(conforms),'disjoint_type_violations':violations,'blocked_scope_promotions':blocked,'SHACL_controlled_probes':checks,'controlled_case_counts':dict(challenges),'RDF_triples_before':initial,'RDF_triples_after':len(g),'versions':{m:importlib.metadata.version(m) for m in ['rdflib','owlrl','pyshacl']},'scope':'Local evidence ontology; OWL-RL property-chain materialization and explicit disjoint-type audit, not full OWL-DL consistency or clinical/payment inference.'}
(R/'results/inference_summary.json').write_text(json.dumps(summary,indent=2));g.serialize(R/'results/inference_closure.ttl',format='turtle');print(json.dumps(summary,indent=2))
