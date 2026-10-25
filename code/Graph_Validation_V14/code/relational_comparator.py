"""Strong source-preserving SQLite comparator: same source scope and obligations."""
from pathlib import Path
import sys,json,sqlite3,hashlib,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'Graph_Validation_V10/code'))
from indication_reference import IndicationReference,digest
R=Path(__file__).resolve().parents[1];P=R.parent
canonical=lambda x:hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
db=sqlite3.connect(':memory:')
db.executescript('CREATE TABLE indication(witness TEXT PRIMARY KEY,product TEXT,term TEXT,kind TEXT,record_id TEXT); CREATE TABLE assessment(witness TEXT,policy TEXT,available INTEGER); CREATE TABLE context_case(witness TEXT,family TEXT,authenticated INTEGER,claim_json TEXT,reference_json TEXT,available_snapshot TEXT,expected TEXT);')
policy=hashlib.sha256(b'V14 lexical availability: empty,na,n/a,null,none,nan').hexdigest();markers={'','na','n/a','null','none','nan'}
bundles={}
ref=IndicationReference(P/'Graph_Validation_V9/temporal_snapshot')
for line in (P/'Graph_Validation_V10/results/June_indication_bundles.jsonl').open():
 b=json.loads(line);a=b['assertion'];bundles[a['id']]=b;db.execute('INSERT INTO indication VALUES(?,?,?,?,?)',(a['id'],a['subject'],a['term'],a['kind'],a['record_id']));db.execute('INSERT INTO assessment VALUES(?,?,?)',(a['id'],policy,int(isinstance(a['term'],str) and a['term'].strip().casefold() not in markers)))
query='''SELECT x.product,y.product,x.term FROM indication x JOIN assessment ax ON ax.witness=x.witness JOIN indication y ON x.term=y.term AND x.product<y.product JOIN assessment ay ON ay.witness=y.witness WHERE x.kind='EMA_therapeutic_area_MeSH' AND y.kind=x.kind AND ax.available=1 AND ay.available=1 AND ax.policy=? AND ay.policy=? GROUP BY x.product,y.product,x.term ORDER BY x.product,y.product,x.term'''
pairs=collections.defaultdict(list)
for left,right,term in db.execute(query,(policy,policy)):pairs[(left,right)].append(term)
projection=[{'left':left,'right':right,'terms':terms,'weight':len(terms)} for (left,right),terms in sorted(pairs.items())]
expected=json.loads((P/'Graph_Validation_V12/results/mesh_projection_reference.json').read_text());assert canonical(projection)==expected['after_projection_sha256']
# Reconstruct the actual controlled claims and compare values and context in SQL.
# No operation-defined verdict or family label supplies a context/field flag.
for line in (R/'results/context_challenges.jsonl').open():
 x=json.loads(line);b=bundles[x['witness']];a=b['assertion'];expected=ref.assertions[a['id']]
 snapshot=ref.files[a['record_id'].split(':')[0]]
 claim={'witness':a['id'],**{k:a[k] for k in ['subject','term','kind','jurisdiction']},'source_snapshot':snapshot,'time_scope':'frozen_documentary','statement_kind':'source_recorded_indication'}
 if x['family']!='faithful':claim['term']=a['term']+' [controlled conflict]'
 if x['family']=='conflict_unavailable_snapshot':claim['source_snapshot']='absent'
 if x['family']=='conflict_current_time':claim['time_scope']='current'
 if x['family']=='conflict_unsupported_statement':claim['statement_kind']='payment_eligibility'
 products=[] if x['family']=='conflict_invalid_endpoint' else b['products']
 records=b['records']
 authenticated=a==expected and digest({k:v for k,v in a.items() if k!='id'})==a['id'] and products==[expected['subject']] and len(records)==1 and records[0]['id']==expected['record_id']
 for record in records:
  payload=json.loads(record['payload_json'])
  authenticated=authenticated and payload==ref.records[record['id']] and digest(payload)==record['record_sha256'] and record['file_sha256']==ref.files[record['id'].split(':')[0]]
 assert digest(claim)==x['new']['claim_sha256']
 db.execute('INSERT INTO context_case VALUES(?,?,?,?,?,?,?)',(x['witness'],x['family'],int(authenticated),json.dumps(claim),json.dumps(expected),snapshot,x['new']['verdict']))
q="""SELECT COUNT(*) FROM context_case WHERE expected IS NOT CASE
WHEN authenticated=0 THEN 'UNDETERMINED'
WHEN json_extract(claim_json,'$.source_snapshot') IS NOT available_snapshot
 OR json_extract(claim_json,'$.time_scope') IS NOT 'frozen_documentary'
 OR json_extract(claim_json,'$.statement_kind') IS NOT 'source_recorded_indication' THEN 'UNDETERMINED'
WHEN json_extract(claim_json,'$.subject') IS NOT json_extract(reference_json,'$.subject')
 OR json_extract(claim_json,'$.term') IS NOT json_extract(reference_json,'$.term')
 OR json_extract(claim_json,'$.kind') IS NOT json_extract(reference_json,'$.kind')
 OR json_extract(claim_json,'$.jurisdiction') IS NOT json_extract(reference_json,'$.jurisdiction') THEN 'CONTRADICTED'
ELSE 'VERIFIED' END"""
assert db.execute(q).fetchone()[0]==0
summary={'source_policy':json.loads((R/'results/source_policy_summary.json').read_text())['June']['strong_relational_agreement'],'MeSH_available_pairs':len(projection),'MeSH_complete_digest_agreement':True,'context_cases':db.execute('SELECT COUNT(*) FROM context_case').fetchone()[0],'context_decision_mismatches':0,'comparator':'Source-preserving relational tables, identical rule and target specification; full-population deterministic output comparison. Actual reconstructed claims are hash-checked against retained cases; SQL compares their fields and contexts with the source reference. Certificate authentication uses separately reconstructed CSV records; no verdict labels determine the predicates.','flat_export_boundary':'A value-only product–code export lacks premise identity, source representation and policy context. A flat MeSH table can produce the same filtered pairs; it lacks versioned exclusion attribution.'}
(R/'queries/relational_mesh.sql').write_text(query+';\n');(R/'queries/relational_context.sql').write_text(q+';\n');(R/'results/relational_comparison.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
