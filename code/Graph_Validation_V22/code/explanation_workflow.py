"""Equal-information explanation workflow: normalized SQL and physical graph paths.
Optional native Neo4j is read-only; offline mode uses hash-bound physical exports.
No query-length, human-effort or engine-performance advantage is inferred.
"""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,sqlite3,sys,urllib.request
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path[:0]=[str(P/'Validation_Study/code'),str(P/'Graph_Validation_V17/code')]
from reference_oracle import Reference
from route_policies import assess
ap=argparse.ArgumentParser();ap.add_argument('--neo4j-url');args=ap.parse_args()
ref=Reference(P/'Graph_Validation_V9/temporal_snapshot')
SQL='''SELECT w.id AS witness,w.product,w.code,w.rule,t.id AS tariff_record,t.payload AS tariff_payload,
 (SELECT json_group_array(json_object('id',r.id,'payload',r.payload)) FROM premise p JOIN record r ON r.id=p.record WHERE p.witness=w.id) AS premises
 FROM witness w JOIN tariff t ON w.code=t.code WHERE w.jurisdiction='CH' AND w.rule IN (SELECT value FROM json_each(?)) ORDER BY witness,tariff_record'''
CYPHER='''MATCH (a:Association)-[:ABOUT_PRODUCT]->(p:ProductRef), (a)-[:TARGET_ATC]->(c:ATCConcept), (t:SourceRecord {file:'ze_definitions.csv'})
WHERE a.jurisdiction='CH' AND a.rule IN $rules AND t.tariff_atc=c.id
RETURN a.id AS witness,p.id AS product,a.atc AS code,a.rule AS rule,t.id AS tariff_record,t.payload_json AS tariff_payload,
[(a)-[:SUPPORTED_BY]->(r:SourceRecord) | {id:r.id,payload:r.payload_json}] AS premises ORDER BY witness,tariff_record'''
canon=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def normalize(x):
 x=dict(x);x['tariff_payload']=json.loads(x['tariff_payload']) if isinstance(x['tariff_payload'],str) else x['tariff_payload']
 x['premises']=json.loads(x['premises']) if isinstance(x['premises'],str) else x['premises']
 for p in x['premises']:
  if isinstance(p['payload'],str):p['payload']=json.loads(p['payload'])
 x['premises']=sorted(x['premises'],key=lambda p:p['id']);return x
# Relational evidence schema retains every source record and exact premise, at full strength.
db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
db.executescript('CREATE TABLE record(id TEXT PRIMARY KEY,payload TEXT); CREATE TABLE witness(id TEXT PRIMARY KEY,product TEXT,code TEXT,rule TEXT,jurisdiction TEXT); CREATE TABLE premise(witness TEXT,record TEXT,PRIMARY KEY(witness,record)); CREATE TABLE tariff(id TEXT PRIMARY KEY,code TEXT,payload TEXT); CREATE INDEX witness_code ON witness(code); CREATE INDEX premise_witness ON premise(witness);')
db.executemany('INSERT INTO record VALUES(?,?)',[(r,canon(p)) for r,p in ref.records.items()])
db.executemany('INSERT INTO witness VALUES(?,?,?,?,?)',[(w['id'],w['subject'],w['atc'],w['rule'],w['jurisdiction']) for w in ref.witnesses.values()]);db.executemany('INSERT INTO premise VALUES(?,?)',[(w['id'],r) for w in ref.witnesses.values() for r in w['premise_ids']])
tariffs={r:p for r,p in ref.records.items() if r.startswith('ze_definitions.csv:')};db.executemany('INSERT INTO tariff VALUES(?,?,?)',[(r,p['code'],canon(p)) for r,p in tariffs.items()])
# Physical exports bind actual node properties and relationships, not expected witness dictionaries.
physical=json.loads(gzip.decompress((P/'Graph_Validation_V9/results/temporal_physical_bundles.json.gz').read_bytes()))
index=collections.defaultdict(list)
for rid,t in tariffs.items():index[t['code']].append(rid)
def graph_rows(rules):
 if args.neo4j_url:
  req=urllib.request.Request(args.neo4j_url.rstrip('/')+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':CYPHER,'parameters':{'rules':rules}}]}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=120) as f:response=json.load(f)
  assert not response['errors'],response['errors'];result=response['results'][0]
  return [normalize(dict(zip(result['columns'],x['row']))) for x in result['data']]
 out=[]
 for b in physical:
  a=b['association']
  if a['jurisdiction']!='CH' or a['rule'] not in rules:continue
  assert b['products']==[a['subject']] and b['targets']==[a['atc']]
  for tid in index[a['atc']]:out.append(normalize({'witness':a['id'],'product':b['products'][0],'code':b['targets'][0],'rule':a['rule'],'tariff_record':tid,'tariff_payload':tariffs[tid],'premises':[{'id':r['id'],'payload':r['payload_json']} for r in b['records']]}))
 return sorted(out,key=lambda x:(x['witness'],x['tariff_record']))
def expected(rules):
 return sorted([normalize({'witness':w['id'],'product':w['subject'],'code':w['atc'],'rule':w['rule'],'tariff_record':tid,'tariff_payload':tariffs[tid],'premises':[{'id':rid,'payload':ref.records[rid]} for rid in w['premise_ids']]}) for w in ref.witnesses.values() if w['jurisdiction']=='CH' and w['rule'] in rules for tid in index[w['atc']]],key=lambda x:(x['witness'],x['tariff_record']))
stages=[];saved={}
for name,rules in [('direct',['direct_SAI']),('alternative_source',['direct_SAI','via_authorization_SL']),('historical_context',['direct_SAI','via_authorization_SL','historical_candidate'])]:
 sqlrows=[normalize(dict(x)) for x in db.execute(SQL,(json.dumps(rules),))];graph=graph_rows(rules);truth=expected(rules)
 assert sqlrows==graph==truth,(name,len(sqlrows),len(graph),len(truth))
 for x in graph:
  assert {p['id'] for p in x['premises']}==set(ref.witnesses[x['witness']]['premise_ids'])
 saved[name]=graph;stages.append({'stage':name,'proof_rows':len(graph),'product_tariff_pairs':len({(x['product'],x['tariff_record']) for x in graph}),'complete_explanation_agreement':True,'proof_digest':hashlib.sha256(canon(graph).encode()).hexdigest()})
def route_rows(rows,policy):
 out=[]
 for x in rows:
  if x['rule']!='via_authorization_SL':continue
  sl=next(p['payload'] for p in x['premises'] if p['id'].startswith('sl.csv:'))
  out.append({**x,'policy':policy,'status':assess(sl['gammenbezeichnung'],sl['bezeichnung'],x['tariff_payload']['va'],policy)})
 return out
assert {canon(x) for x in saved['direct']} <= {canon(x) for x in saved['alternative_source']} <= {canon(x) for x in saved['historical_context']}
assert graph_rows(['direct_SAI'])==saved['direct']
assert [normalize(dict(x)) for x in db.execute(SQL,(json.dumps(['direct_SAI']),))]==saved['direct']
base=saved['alternative_source'];direct={(x['product'],x['tariff_record']) for x in saved['direct']};extra={(x['product'],x['tariff_record']) for x in base}-direct
combined=[];policies={}
for policy in ['coarse','exact_code','explicit_formulation']:
 graph=route_rows(base,policy);sqlrows=route_rows([normalize(dict(x)) for x in db.execute(SQL,(json.dumps(['direct_SAI','via_authorization_SL']),))],policy);assert graph==sqlrows
 policies[policy]={'proof_rows':len(graph),'decisions':dict(collections.Counter(x['status'] for x in graph)),'complete_explanation_and_decision_agreement':True}
 for pair in sorted(extra):
  related=[x for x in graph if (x['product'],x['tariff_record'])==pair]
  status='VERIFIED' if any(x['status']=='VERIFIED' for x in related) else 'CONTRADICTED' if related and all(x['status']=='CONTRADICTED' for x in related) else 'UNDETERMINED'
  combined.append({'product':pair[0],'tariff_record':pair[1],'policy':policy,'status':status,'supporting_witnesses':sorted({x['witness'] for x in related}),'source_premises':sorted({p['id'] for x in related for p in x['premises']})})
assert len(base)==1559 and len(extra)==4 and len(combined)==12
assert collections.Counter(x['status'] for x in combined if x['policy']=='exact_code')=={'VERIFIED':2,'UNDETERMINED':2}
summary={'design':'Equal-information explanation comparison; three source/scope stages and three route targets; retrospective task sequence, no human-effort or runtime study.','graph_execution':'native_read_only_Neo4j' if args.neo4j_url else 'retained_physical_path_exports','stages':stages,'route_targets':policies,'additional_candidate_route_assessments':combined,'previous_proofs_preserved_under_scope_expansion':True,'direct_scope_replay_unchanged':True,'retrieval_query_text_changes':{'Cypher':0,'normalized_SQL':0},'source_updates':'Rule parameters admit additional retained source paths; no new acquisition or data vintage tested.','new_route_targets':'Same extracted package and tariff facts; identical route adapter for both representations.','independence':'Source retrieval and explanation assembly use separate physical paths and normalized SQL; route semantics are deliberately shared.','finding':'Both representations preserve complete explanations with fixed retrieval text. No exclusive graph extensibility advantage demonstrated. Two of four alternative-source candidates retain support under both finer route targets; the other two lack specific route evidence.','Cypher_sha256':hashlib.sha256(CYPHER.encode()).hexdigest(),'SQL_sha256':hashlib.sha256(SQL.encode()).hexdigest(),'input_hashes':ref.files,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(R/'results').mkdir(exist_ok=True);(R/'queries').mkdir(exist_ok=True)
(R/'results/explanation_workflow.json').write_text(json.dumps(summary,indent=2)+'\n');(R/'queries/explanation_workflow.cypher').write_text(CYPHER+';\n');(R/'queries/explanation_workflow.sql').write_text(SQL+';\n');print(json.dumps({k:v for k,v in summary.items() if k not in {'additional_candidate_route_assessments','input_hashes'}},indent=2))
