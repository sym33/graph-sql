from pathlib import Path
import json,hashlib,datetime,urllib.request
R=Path(__file__).resolve().parents[1]
q="""MATCH (a:Association)-[:ABOUT_PRODUCT]->(p:ProductRef)
WHERE a.rule IN ['direct_SAI','via_authorization_SL']
WITH p.id AS product,collect(DISTINCT CASE WHEN a.rule='direct_SAI' THEN a.atc END) AS SAI_codes,
collect(DISTINCT CASE WHEN a.rule='via_authorization_SL' THEN a.atc END) AS SL_codes
RETURN product,SAI_codes,SL_codes ORDER BY product"""
# Match actual evidence-layer endpoint name from schema, never infer a path from IDs.
request=urllib.request.Request('http://127.0.0.1:17474/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':q}]}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=90) as f:response=json.load(f)
assert not response['errors'],response['errors']
result=response['results'][0];actual=[dict(zip(result['columns'],x['row'])) for x in result['data']]
for x in actual:x['SAI_codes']=sorted(x['SAI_codes']);x['SL_codes']=sorted(x['SL_codes'])
ref=json.loads((R/'results/June_source_policy_records.json').read_text());expected=[{k:x[k] for k in ['product','SAI_codes','SL_codes']} for x in ref]
assert actual==expected,(len(actual),len(expected),actual[:1])
(R/'queries/source_policy.cypher').write_text(q+';\n')
summary={'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'products':len(actual),'complete_physical_agreement':True,'query_sha256':hashlib.sha256(q.encode()).hexdigest(),'canonical_source_groups_sha256':hashlib.sha256(json.dumps(actual,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
(R/'results/neo4j_source_policy.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
