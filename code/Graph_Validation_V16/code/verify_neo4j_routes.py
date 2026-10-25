from pathlib import Path
import json,hashlib,urllib.request,datetime
from route_context import decide
R=Path(__file__).resolve().parents[1]
q="""MATCH (a:Association {rule:'via_authorization_SL'})-[:ABOUT_PRODUCT]->(p:ProductRef), (a)-[:SUPPORTED_BY]->(r:SourceRecord {file:'sl.csv'}), (a)-[:TARGET_ATC]->(c:ATCConcept), (t:SourceRecord {file:'ze_definitions.csv'})
WHERE a.jurisdiction='CH' AND t.tariff_atc=c.id
RETURN DISTINCT a.id AS witness,r.id AS SL_record,t.id AS tariff_record,r.payload_json AS SL_payload,t.payload_json AS tariff_payload ORDER BY witness,tariff_record"""
req=urllib.request.Request('http://127.0.0.1:17474/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':q}]}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=120) as f:response=json.load(f)
assert not response['errors'],response['errors'];result=response['results'][0];actual=[]
for z in result['data']:
 x=dict(zip(result['columns'],z['row']));sl=json.loads(x.pop('SL_payload'));tar=json.loads(x.pop('tariff_payload'));x['recorded_group']=sl['gammenbezeichnung'];x['tariff_routes']=tar['va'];x['status']=decide(x['recorded_group'],x['tariff_routes']);actual.append(x)
keys=['witness','SL_record','tariff_record','recorded_group','tariff_routes','status']
expected=sorted([{k:x[k] for k in keys} for x in json.loads((R/'results/route_decisions.json').read_text())],key=lambda x:(x['witness'],x['tariff_record']));assert actual==expected,(len(actual),len(expected))
(R/'queries/package_route.cypher').write_text(q+';\n')
receipt={'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete_physical_source_and_decision_agreement':True,'cases':len(actual),'canonical_output_sha256':hashlib.sha256(json.dumps(actual,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'scope':'Physical source paths and exact fields; same declared coarse route policy applied to retrieved fields.'};(R/'results/neo4j_route_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
