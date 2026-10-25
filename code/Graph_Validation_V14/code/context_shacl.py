from pathlib import Path
import sys,json,collections,copy,hashlib
import rdflib,pyshacl
from rdflib import Graph,Namespace,Literal,RDF
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path[:0]=[str(P/'Validation_Study/code'),str(P/'Automated_Verification/code')]
from reference_oracle import Reference
from evidence_judge import digest
from context_contract import evaluate_classification
E=Namespace('https://example.org/medigraph-validation/')
ref=Reference(P)
shapes={k:Graph().parse(str(P/'Graph_Validation_V9/code'/filename),format='turtle') for k,filename in [('source','source_shapes.ttl'),('scope','scope_shapes.ttl'),('values','value_shapes.ttl')]}
canonical=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def graph(c,b):
 g=Graph();cn=E.claim;g.add((cn,RDF.type,E.Claim))
 for k in ['witness','subject','atc','rule','jurisdiction','kind']:g.add((cn,E[k],Literal(c.get(k,''))))
 g.add((cn,E.time,Literal(c.get('time_scope',''))));g.add((cn,E.snapshot,Literal(c.get('source_snapshot',''))));g.add((cn,E.availableSnapshot,Literal(ref.files['atc_list.csv'])))
 if not b or not b.get('association'):return g
 a=b['association'];wn=E.witness;g.add((wn,RDF.type,E.Witness));expected=ref.witnesses.get(c['witness'])
 g.add((wn,E.observedAssociation,Literal(canonical(a))))
 if expected:g.add((wn,E.referenceAssociation,Literal(canonical(expected))))
 for k in ['witness','subject','atc','rule','jurisdiction']:g.add((cn,E['expected_'+k],Literal(a.get('id' if k=='witness' else k,''))))
 for k in ['products','targets']:
  for v in b.get(k,[]):g.add((wn,E.product if k=='products' else E.target,Literal(v)))
 g.add((wn,E.associationProduct,Literal(a['subject'])));g.add((wn,E.associationTarget,Literal(a['atc'])))
 g.add((wn,E.observedPremises,Literal(canonical(sorted(r.get('id','') for r in b.get('records',[]))))));g.add((wn,E.referencePremises,Literal(canonical(sorted(a['premise_ids'])))))
 for i,r in enumerate(b.get('records',[])):
  rn=E['record'+str(i)];g.add((rn,RDF.type,E.Record));rid=r.get('id');payload=json.loads(r['payload_json']);expected_payload=ref.records.get(rid)
  for k,v in [('payload',canonical(payload)),('fileDigest',r.get('file_sha256','')),('payloadDigest',r.get('record_sha256',''))]:g.add((rn,E[k],Literal(v)))
  if expected_payload is not None:
   for k,v in [('referencePayload',canonical(expected_payload)),('referenceFileDigest',ref.files[rid.split(':',1)[0]]),('referencePayloadDigest',digest(expected_payload))]:g.add((rn,E[k],Literal(v)))
 return g
def conforms(g,which):return bool(pyshacl.validate(g,shacl_graph=shapes[which],inference='none',abort_on_first=False)[0])

physical=json.loads((P/'Graph_Validation_V9/results/baseline_physical_bundles.json').read_text());byrule=collections.defaultdict(list)
for b in physical:byrule[b['association']['rule']].append(b)
selected=[b for rule in sorted(byrule) for b in sorted(byrule[rule],key=lambda b:b['association']['id'])[:20]]
rows=[]
for b in selected:
 a=b['association'];c={'witness':a['id'],**{k:a[k] for k in ['subject','atc','rule','jurisdiction']},'kind':'documentary_association','source_snapshot':ref.files['atc_list.csv'],'time_scope':'frozen_documentary'}
 wrong=dict(c,atc='CONTROLLED_INVALID_CODE');bad=copy.deepcopy(b);bad['targets']=[]
 cases=[('faithful',c,b,'VERIFIED'),('field_conflict',wrong,b,'CONTRADICTED'),('conflict_other_snapshot',dict(wrong,source_snapshot='absent'),b,'UNDETERMINED'),('conflict_current',dict(wrong,time_scope='current'),b,'UNDETERMINED'),('conflict_other_statement',dict(wrong,kind='payment_eligibility'),b,'UNDETERMINED'),('conflict_invalid_endpoint',wrong,bad,'UNDETERMINED')]
 for family,c,e,gold in cases:
  g=graph(c,e);source=conforms(g,'source');scope=conforms(g,'scope');values=conforms(g,'values')
  declarative='UNDETERMINED' if not source or not scope else 'CONTRADICTED' if not values else 'VERIFIED'
  imperative=evaluate_classification(c,e,ref)['verdict'];assert declarative==imperative==gold
  rows.append({'family':family,'witness':a['id'],'expected':gold,'imperative':imperative,'SHACL':declarative,'source_conforms':source,'scope_conforms':scope,'values_conform':values})
(R/'results/context_SHACL_decisions.json').write_text(json.dumps(rows,indent=2))
summary={'witnesses':len(selected),'cases':len(rows),'families':dict(collections.Counter(r['family'] for r in rows)),'imperative_declarative_mismatches':0,'versions':{'pyshacl':pyshacl.__version__,'rdflib':rdflib.__version__},'scope':'Classification mixed-failure cases; source/scope/value shapes retained, adapter order changed to context-first.'}
(R/'results/context_SHACL_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
