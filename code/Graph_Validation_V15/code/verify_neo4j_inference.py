from pathlib import Path
import json,hashlib,urllib.request,datetime
R=Path(__file__).resolve().parents[1]
def query(q):
 req=urllib.request.Request('http://127.0.0.1:17474/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':q}]}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=120) as f:r=json.load(f)
 assert not r['errors'],r['errors'];x=r['results'][0];return [dict(zip(x['columns'],z['row'])) for z in x['data']]
q="""MATCH (a:Association)-[:ABOUT_PRODUCT]->(p:ProductRef), (a)-[:TARGET_ATC]->(c:ATCConcept), (t:SourceRecord {file:'ze_definitions.csv'})
WHERE a.jurisdiction='CH' AND a.rule IN ['direct_SAI','via_authorization_SL'] AND t.tariff_atc=c.id
RETURN DISTINCT a.id AS witness,t.id AS tariff_record ORDER BY witness,tariff_record"""
actual=query(q);expected=sorted([{'witness':x['witness'],'tariff_record':x['tariff_record']} for x in json.loads((R/'results/documentary_candidates.json').read_text())],key=lambda x:(x['witness'],x['tariff_record']));assert actual==expected,(len(actual),len(expected))
hq=q.replace("a.rule IN ['direct_SAI','via_authorization_SL']","a.rule='historical_candidate'")
h=query(hq);he=sorted([{'witness':x['witness'],'tariff_record':x['tariff_record']} for x in json.loads((R/'results/historical_candidates.json').read_text())],key=lambda x:(x['witness'],x['tariff_record']));assert h==he
(R/'queries/documentary_tariff.cypher').write_text(q+';\n');(R/'queries/historical_tariff.cypher').write_text(hq+';\n')
iq="""MATCH (a:Association {rule:'via_authorization_SL'})-[:ABOUT_PRODUCT]->(p:ProductRef), (a)-[:SUPPORTED_BY]->(r:SourceRecord {file:'sl.csv'}), (a)-[:TARGET_ATC]->(c:ATCConcept), (t:SourceRecord {file:'ze_definitions.csv'})
WHERE a.jurisdiction='CH' AND t.tariff_atc=c.id
RETURN DISTINCT r.id AS ingredient_declaration_record,t.id AS tariff_record,r.payload_json AS payload ORDER BY ingredient_declaration_record,tariff_record"""
ingredient=[{k:x[k] for k in ['ingredient_declaration_record','tariff_record']} for x in query(iq) if json.loads(x['payload']).get('substanzen','').strip().casefold() not in {'','na','n/a','null','none','nan'}]
expected_ingredient=[{k:x[k] for k in ['ingredient_declaration_record','tariff_record']} for x in json.loads((R/'results/ingredient_tariff_candidates.json').read_text())];assert ingredient==expected_ingredient
(R/'queries/ingredient_tariff.cypher').write_text(iq+';\n')
inventory={'labels':query('CALL db.labels() YIELD label RETURN label ORDER BY label'),'relationship_types':query('CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType'),'semantic_procedures':query("SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'n10s.' RETURN name")}
s={'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete_documentary_agreement':True,'complete_historical_agreement':True,'complete_ingredient_declaration_agreement':True,'ingredient_declaration_tariff_pairs':len(ingredient),'documentary_derivations':len(actual),'historical_derivations':len(h),'documentary_digest':hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest(),'server_inventory':inventory,'scope':'Read-only physical paths; OWL-RL evaluated by separate explicit ontology adapter.'}
(R/'results/neo4j_inference_receipt.json').write_text(json.dumps(s,indent=2));print(json.dumps(s,indent=2))
