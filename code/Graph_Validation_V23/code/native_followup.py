"""Temporary native Cypher inference overlay; existing graph facts stay untouched."""
from pathlib import Path
import collections,hashlib,json,urllib.request
from route_policies import assess
def verify_native(url,run,paths,profiles,expected_pairs):
 def query(statement,parameters=None):
  req=urllib.request.Request(url.rstrip('/')+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':statement,'parameters':parameters or {}}]}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=180) as f:r=json.load(f)
  assert not r['errors'],r['errors'];x=r['results'][0];return [dict(zip(x['columns'],y['row'])) for y in x['data']]
 def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 original_q="""MATCH (a:Association) RETURN a.id AS id,properties(a) AS properties,[(a)-[:ABOUT_PRODUCT]->(p) | p.id] AS products,[(a)-[:TARGET_ATC]->(c) | c.id] AS codes,[(a)-[:SUPPORTED_BY]->(r) | {id:r.id,payload:r.payload_json}] AS premises ORDER BY id"""
 before=query(original_q)
 for x in before:x['premises']=sorted(x['premises'],key=lambda y:y['id'])
 before_digest=digest(before)
 source_q="MATCH (r:SourceRecord) RETURN r.id AS id,r.payload_json AS payload ORDER BY id";source_before=digest(query(source_q))
 assert query("MATCH (n:Followup23Ingredient {run:$run}) RETURN count(n) AS n",{'run':run})[0]['n']==0
 assert query("MATCH (n:Followup23Assessment {run:$run}) RETURN count(n) AS n",{'run':run})[0]['n']==0
 infer="""MATCH (i:Followup23Ingredient {run:$run})<-[:Followup23IngredientOf {run:$run}]-(a:Association)-[:TARGET_ATC]->(c:ATCConcept)-[:Followup23ListedBy {run:$run}]->(t:SourceRecord)
WHERE a.jurisdiction='CH' AND a.rule='via_authorization_SL'
MERGE (i)-[:Followup23DerivedTariff {run:$run}]->(t)"""
 follow="""MATCH (i:Followup23Ingredient {run:$run})-[:Followup23DerivedTariff {run:$run}]->(t:SourceRecord), (a:Association)-[:Followup23IngredientOf {run:$run}]->(i), (a)-[:ABOUT_PRODUCT]->(p:ProductRef), (z:Followup23Assessment {run:$run})
WHERE z.witness=a.id AND z.tariff_record=t.id AND z.policy=$policy
RETURN i.key AS ingredient_key,i.id AS SL_record,t.id AS tariff_record,a.id AS witness,p.id AS product,z.status AS status ORDER BY ingredient_key,tariff_record,witness"""
 pair_q="MATCH (i:Followup23Ingredient {run:$run})-[:Followup23DerivedTariff {run:$run}]->(t:SourceRecord) RETURN i.id AS SL_record,t.id AS tariff_record ORDER BY SL_record,tariff_record"
 try:
  for start in range(0,len(paths),250):
   batch=paths[start:start+250]
   verified=query("""UNWIND $rows AS x MATCH (a:Association {id:x.witness})-[:SUPPORTED_BY]->(r:SourceRecord {id:x.SL_record}), (a)-[:TARGET_ATC]->(c:ATCConcept {id:x.code}), (t:SourceRecord {id:x.tariff_record}) WHERE t.tariff_atc=x.code RETURN a.id AS witness,r.id AS SL_record,r.payload_json AS sl_payload,t.id AS tariff_record,t.payload_json AS tariff_payload""",{'rows':batch})
   assert {(x['witness'],x['SL_record'],x['tariff_record']) for x in verified}=={(x['witness'],x['SL_record'],x['tariff_record']) for x in batch}
   bykey={(x['witness'],x['SL_record'],x['tariff_record']):x for x in batch}
   for x in verified:
    p=bykey[(x['witness'],x['SL_record'],x['tariff_record'])];sl=json.loads(x['sl_payload']);tariff=json.loads(x['tariff_payload'])
    assert (sl['substanzen'],sl['gammenbezeichnung'],sl['bezeichnung'],tariff['va'])==(p['ingredient'],p['group'],p['package'],p['tariff_routes'])
   query("""UNWIND $rows AS x MATCH (a:Association {id:x.witness})-[:SUPPORTED_BY]->(r:SourceRecord {id:x.SL_record}), (a)-[:TARGET_ATC]->(c:ATCConcept {id:x.code}), (t:SourceRecord {id:x.tariff_record})
MERGE (i:Followup23Ingredient {run:$run,id:x.SL_record}) ON CREATE SET i.key=x.ingredient_key
MERGE (a)-[:Followup23IngredientOf {run:$run}]->(i)
MERGE (c)-[:Followup23ListedBy {run:$run}]->(t)""",{'rows':batch,'run':run})
   assessments=[{'witness':x['witness'],'tariff_record':x['tariff_record'],'policy':p,'status':assess(x['group'],x['package'],x['tariff_routes'],p)} for x in batch for p in ['coarse','exact_code','explicit_formulation']]
   query("UNWIND $rows AS x CREATE (z:Followup23Assessment) SET z=x,z.run=$run",{'rows':assessments,'run':run})
  assert not query(pair_q,{'run':run}) and not query(follow,{'run':run,'policy':'exact_code'})
  query(infer,{'run':run});actual=query(pair_q,{'run':run});assert {(x['SL_record'],x['tariff_record']) for x in actual}==expected_pairs
  query(infer,{'run':run});assert query(pair_q,{'run':run})==actual
  counts={}
  for policy in profiles:
   rows=query(follow,{'run':run,'policy':policy});cells=collections.defaultdict(list)
   for x in rows:cells[(x['ingredient_key'],x['tariff_record'])].append(x)
   actual_profiles={k:{'status_counts':dict(collections.Counter(x['status'] for x in xs)),'products':sorted({x['product'] for x in xs}),'source_rows':sorted({x['SL_record'] for x in xs})} for k,xs in cells.items()}
   expected_profiles={(x['ingredient_key'],x['tariff_record']):{k:x[k] for k in ['status_counts','products','source_rows']} for x in profiles[policy]}
   assert actual_profiles==expected_profiles
   assert {(x['witness'],x['SL_record'],x['tariff_record'],x['status']) for x in rows}=={(x['witness'],x['SL_record'],x['tariff_record'],x['status']) for g in profiles[policy] for x in g['paths']}
   counts[policy]=len(rows)
  # Remove derived edges only, then recompute from the unchanged explicit paths.
  query("MATCH ()-[r:Followup23DerivedTariff {run:$run}]->() DELETE r",{'run':run});assert not query(follow,{'run':run,'policy':'exact_code'})
  query(infer,{'run':run});assert query(pair_q,{'run':run})==actual
  result={'native_materialized_pairs':len(actual),'native_query_paths':counts,'all_group_profiles_and_witnesses_agree':True,'before_materialization_selected_rows':0,'after_derived_edge_removal_selected_rows':0,'rematerialization_pair_set_unchanged':True,'materialization_idempotent':True,'inference_query_sha256':hashlib.sha256(infer.encode()).hexdigest(),'followup_query_sha256':hashlib.sha256(follow.encode()).hexdigest()}
 finally:
  query("MATCH ()-[r:Followup23ListedBy {run:$run}]->() DELETE r",{'run':run})
  query("MATCH (n:Followup23Ingredient {run:$run}) DETACH DELETE n",{'run':run})
  query("MATCH (n:Followup23Assessment {run:$run}) DETACH DELETE n",{'run':run})
  after=query(original_q)
  for x in after:x['premises']=sorted(x['premises'],key=lambda y:y['id'])
  assert digest(after)==before_digest and digest(query(source_q))==source_before
  assert query("MATCH ()-[r]->() WHERE type(r) STARTS WITH 'Followup23' AND r.run=$run RETURN count(r) AS n",{'run':run})[0]['n']==0
 result['native_helper_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 result['original_witness_and_source_fingerprints_preserved']=True;result['temporary_overlay_removed']=True
 return result
