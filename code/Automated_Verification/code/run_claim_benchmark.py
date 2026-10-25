"""Neo4j evidence extraction; operation-labeled engineering challenge, not expert gold."""
import sys,json,copy,hashlib,time,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Validation_Study/code'))
from reference_oracle import Reference
from neo4j_contracts import query
from evidence_judge import EvidenceJudge,digest,V,C,U
OUT=ROOT/'Automated_Verification/results';OUT.mkdir(parents=True,exist_ok=True)
ref=Reference(ROOT);judge=EvidenceJudge(ref)
Q='''MATCH (a:Association) RETURN properties(a) AS association,
 [(a)-[:ABOUT_PRODUCT]->(p) | p.id] AS products,
 [(a)-[:TARGET_ATC]->(c) | c.id] AS targets,
 [(a)-[:SUPPORTED_BY]->(r) | properties(r)] AS records ORDER BY a.id'''
# The read is a single Neo4j statement, so all evidence is read in one transaction.
t0=time.perf_counter();physical=query(Q);retrieval=time.perf_counter()-t0
bundles={r['association']['id']:r for r in physical}
assert set(bundles)==set(ref.witnesses)
# One deterministic witness per product/ATC; retain all pairs rather than sample easy cases.
selected={}
for wid,a in sorted(ref.witnesses.items()):selected.setdefault((a['subject'],a['atc']),wid)
rows=[];counts=collections.defaultdict(collections.Counter);split_counts=collections.Counter();examples={};t0=time.perf_counter()
with (OUT/'claim_decisions.jsonl').open('w') as f:
 for pair,wid in sorted(selected.items()):
  a=ref.witnesses[wid];b=bundles[wid]
  base={'witness':wid,'subject':a['subject'],'atc':a['atc'],'rule':a['rule'],'jurisdiction':a['jurisdiction'],'kind':'documentary_association','source_snapshot':ref.files['atc_list.csv'],'time_scope':'frozen_documentary'}
  split='evaluation' if int(hashlib.sha256(a['subject'].encode()).hexdigest()[:8],16)%5==0 else 'development'
  cases=[('faithful',base,b,V)]
  for field,value in [('subject','CH:authorization:NONEXISTENT'),('atc','NONEXISTENT_ATC'),('jurisdiction','EU' if a['jurisdiction']=='CH' else 'CH'),('rule','direct_EMA' if a['rule']!='direct_EMA' else 'direct_SAI')]:
   c=dict(base);c[field]=value;cases.append(('wrong_'+field,c,b,C))
  for kind in ['payment_eligibility','current_authorized_classification','source_exclusivity']:
   c=dict(base);c['kind']=kind;cases.append((kind,c,b,U))
  c=dict(base);c['source_snapshot']='unavailable-version';cases.append(('unavailable_snapshot',c,b,U))
  c=dict(base);c['time_scope']='current';cases.append(('current_validity',c,b,U))
  cases.append(('missing_evidence',base,None,U))
  corrupt=copy.deepcopy(b);r=corrupt['records'][0];payload=json.loads(r['payload_json']);payload['challenge_extra_field']='coherent_forgery';r['payload_json']=json.dumps(payload,ensure_ascii=False);r['record_sha256']=digest(payload)
  cases.append(('coherent_source_forgery',base,corrupt,U))
  corrupt=copy.deepcopy(b);corrupt['targets']=['NONEXISTENT_ATC'];cases.append(('physical_endpoint_corruption',base,corrupt,U))
  # No labels are passed to assess(). Operational labels are assigned by challenge constructors.
  for family,c,e,gold in cases:
   preds={mode:judge.assess(c,e,mode) for mode in ['path','lineage','derivation','schema','always_abstain','full']}
   row={'pair':list(pair),'split':split,'family':family,'claim':c,'operational_reference':gold,'decisions':preds};f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
   split_counts[split]+=1
   for mode,d in preds.items():
    counts[(split,mode)][(gold,d['verdict'])]+=1;counts[('all',mode)][(gold,d['verdict'])]+=1
   if family not in examples:examples[family]=row
elapsed=time.perf_counter()-t0
metrics={}
for (split,mode),matrix in counts.items():
 n=sum(matrix.values());nonverified=sum(v for (g,p),v in matrix.items() if g!=V);accepted=sum(v for (g,p),v in matrix.items() if p==V);falseaccept=sum(v for (g,p),v in matrix.items() if p==V and g!=V)
 metrics.setdefault(split,{})[mode]={'n':n,'exact_operational_agreement':sum(v for (g,p),v in matrix.items() if g==p)/n,'false_verification_count':falseaccept,'false_verification_rate':falseaccept/nonverified,'verified_count':accepted,'verified_coverage':accepted/n,'undetermined_count':sum(v for (g,p),v in matrix.items() if p==U),'confusion':{g:{p:matrix[(g,p)] for p in [V,C,U]} for g in [V,C,U]}}
summary={'task':'selected-witness claim verification, relative to frozen documentary sources','label_status':'operation-defined engineering labels; same-team specification; no blinded clinical reference','partition_status':'product-grouped descriptive partition, no fitting and no independent held-out mutation families','pair_count':len(selected),'physical_witness_count':len(bundles),'families':list(examples),'split_counts':dict(split_counts),'metrics':metrics,'retrieval_seconds':retrieval,'benchmark_seconds':elapsed,'query':Q,'query_sha256':hashlib.sha256(Q.encode()).hexdigest(),'reference_implementation':ref.implementation_sha,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'judge_sha256':hashlib.sha256((Path(__file__).parent/'evidence_judge.py').read_bytes()).hexdigest()}
(OUT/'benchmark_summary.json').write_text(json.dumps(summary,indent=2));(OUT/'challenge_examples.json').write_text(json.dumps(examples,indent=2,ensure_ascii=False))
print(json.dumps({'pairs':len(selected),'claims':sum(split_counts.values()),'metrics':metrics['all'],'retrieval_seconds':retrieval,'benchmark_seconds':elapsed},indent=2))
