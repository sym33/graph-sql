from pathlib import Path
from urllib.request import Request,urlopen
import json,hashlib,datetime
R=Path(__file__).resolve().parents[1]
policy='4250a4195469fe1043275a12d03593add73f0446bce1d324b6303fa4369a90ca'
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def run(q):
 with urlopen(Request('http://127.0.0.1:17474/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':q,'parameters':{'policy':policy}}]}).encode(),headers={'Content-Type':'application/json'}),timeout=120) as f:r=json.load(f)
 assert not r['errors'],r['errors'];result=r['results'][0]
 return [dict(zip(result['columns'],x['row'])) for x in result['data']]
start="MATCH (a:IndicationAssertion)-[:ABOUT_PRODUCT]->(p:ProductRef) "
where="WHERE a.kind='EMA_therapeutic_area_MeSH' "
finish='''WITH a.term AS term, collect(DISTINCT p.id) AS products
UNWIND products AS left UNWIND products AS right
WITH term, left, right WHERE left < right
RETURN left, right, collect(DISTINCT term) AS terms ORDER BY left, right'''
queries={'before':start+where+finish,'after':start+'MATCH (a)-[:HAS_CONTENT_ASSESSMENT]->(q:IndicationContentAssessment) '+where+'AND q.policy_sha256=$policy AND q.content_available=true '+finish}
summary={'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'access':'read-only physical Neo4j projection on isolated June research graph','policy_sha256':policy,'queries':{}}
ref=json.loads((R/'results/mesh_projection_reference.json').read_text())
projections={}
for name,q in queries.items():
 rows=run(q)
 for x in rows:x['terms']=sorted(x['terms']);x['weight']=len(x['terms'])
 expected=ref[name+'_projection_sha256'];assert digest(rows)==expected,(name,digest(rows),expected)
 summary['queries'][name]={'pairs':len(rows),'query_sha256':hashlib.sha256(q.encode()).hexdigest(),'projection_sha256':digest(rows),'complete_reference_agreement':True}
 projections[name]={(x['left'],x['right']):set(x['terms']) for x in rows}
 (R/'queries'/('mesh_projection_'+name+'.cypher')).write_text(q+';\n')
removed=set(projections['before'])-set(projections['after'])
assert len(removed)==ref['removed_pairs']
assert all(projections['before'][p]=={'na'} for p in removed)
summary['removed_pairs']=len(removed);summary['removed_pair_evidence']='all and only lowercased source NA marker'
summary['retained_weights_unchanged']=all(v==projections['before'][p] for p,v in projections['after'].items())
(R/'results/neo4j_projection_verification.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
