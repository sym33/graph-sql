"""Read-only extraction from isolated research Neo4j; all evidence in one statement."""
import argparse,json,hashlib,datetime
from pathlib import Path
from urllib.request import Request,urlopen
p=argparse.ArgumentParser();p.add_argument('--population',choices=['baseline','June'],required=True);a=p.parse_args()
R=Path(__file__).resolve().parents[1];out=R/'results';out.mkdir(exist_ok=True)
q='''MATCH (a:IndicationAssertion) RETURN properties(a) AS assertion,
 [(a)-[:ABOUT_PRODUCT]->(p:ProductRef) | p.id] AS products,
 [(a)-[:SUPPORTED_BY]->(r:SourceRecord) | properties(r)] AS records ORDER BY a.id'''
body=json.dumps({'statements':[{'statement':q}]}).encode()
with urlopen(Request('http://127.0.0.1:17474/db/neo4j/tx/commit',data=body,headers={'Content-Type':'application/json'}),timeout=300) as f:result=json.load(f)
assert not result['errors'],result['errors'];part=result['results'][0]
rows=[dict(zip(part['columns'],r['row'])) for r in part['data']]
path=out/f'{a.population}_indication_bundles.jsonl'
with path.open('w') as f:
 for row in rows:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
(out/f'{a.population}_extraction_receipt.json').write_text(json.dumps({'population':a.population,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':len(rows),'query_sha256':hashlib.sha256(q.encode()).hexdigest(),'payload_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'access':'read-only single-statement physical Neo4j extraction'},indent=2))
(R/'queries/indication_evidence.cypher').write_text(q+';\n');print({'population':a.population,'rows':len(rows)})
