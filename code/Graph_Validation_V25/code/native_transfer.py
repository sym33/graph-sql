"""Verify and remove a protocol-tagged documentary route inference overlay."""
from pathlib import Path
import argparse,hashlib,json,urllib.request
R=Path(__file__).resolve().parents[1]
def main(url):
 data=json.loads((R/'results/transfer.json').read_text());run=data['protocol_sha256']
 def q(s,p=None):
  req=urllib.request.Request(url+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':s,'parameters':p or {}}]}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=180) as f:x=json.load(f)
  assert not x['errors'],x['errors'];v=x['results'][0];rows=[dict(zip(v['columns'],r['row'])) for r in v['data']]
  for row in rows:
   if 'targets' in row:row['targets']=sorted(row['targets'])
  return rows
 fingerprint="MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH 'Transfer25') RETURN elementId(n) AS id,labels(n) AS labels,properties(n) AS props ORDER BY id"
 before=q(fingerprint);params={'run':run}
 actual=q("UNWIND $ids AS id MATCH (a:Association {rule:'direct_EMA'})-[:ABOUT_PRODUCT]->(m:ProductRef {id:'EMA:medicine:'+id}),(a)-[:TARGET_ATC]->(c:ATCConcept) RETURN DISTINCT id,c.id AS atc",{'ids':[m['id'] for m in data['medicines']]})
 assert {(x['id'],x['atc']) for x in actual}=={(m['id'],m['ATC']) for m in data['medicines']}
 infer="""MATCH (m:ProductRef)<-[:Transfer25ForMedicine {run:$run}]-(d:Transfer25Document)<-[:Transfer25InDocument {run:$run}]-(f:Transfer25Field)-[:Transfer25Declares {run:$run}]->(r:Transfer25Route) MERGE (m)-[:Transfer25DocumentedRoute {run:$run}]->(r)"""
 candidates="""MATCH (a:Association {rule:'direct_EMA'})-[:ABOUT_PRODUCT]->(s:ProductRef)-[:Transfer25DocumentedRoute {run:$run}]->(r:Transfer25Route),(a)-[:TARGET_ATC]->(c:ATCConcept)<-[:TARGET_ATC]-(b:Association {rule:'direct_EMA'})-[:ABOUT_PRODUCT]->(t:ProductRef)<-[:Transfer25ForMedicine {run:$run}]-(:Transfer25Document) WHERE s<>t OPTIONAL MATCH (t)-[:Transfer25DocumentedRoute {run:$run}]->(tr:Transfer25Route) RETURN DISTINCT s.id AS source,t.id AS target,r.id AS route,collect(DISTINCT tr.id) AS targets ORDER BY source,target,route"""
 try:
  for f in data['fields']:
   q("MATCH (m:ProductRef {id:'EMA:medicine:'+$medicine}) MERGE (d:Transfer25Document {run:$run,id:$medicine}) SET d.sha=$sha,d.url=$url MERGE (d)-[:Transfer25ForMedicine {run:$run}]->(m) CREATE (f:Transfer25Field {run:$run,id:$id,page:$page,title:$title,value:$value}) MERGE (f)-[:Transfer25InDocument {run:$run}]->(d) WITH f UNWIND $routes AS route MERGE (r:Transfer25Route {run:$run,id:route}) MERGE (f)-[:Transfer25Declares {run:$run}]->(r)",{'run':run,'medicine':f['medicine'],'sha':f['pdf_sha256'],'url':f['url'],'id':f['id'],'page':f['page'],'title':f['title'],'value':f['field'],'routes':f['routes']})
  assert not q(candidates,params);q(infer,params);rows=q(candidates,params);q(infer,params);assert q(candidates,params)==rows
  observed={(x['source'].removeprefix('EMA:medicine:'),x['target'].removeprefix('EMA:medicine:'),x['route'],'UNDETERMINED' if not x['targets'] else 'VERIFIED' if x['route'] in x['targets'] else 'CONTRADICTED') for x in rows}
  assert observed=={(x['source'],x['target'],x['route'],x['exact']) for x in data['rows']}
  q('MATCH ()-[r:Transfer25DocumentedRoute {run:$run}]->() DELETE r',params);assert not q(candidates,params)
  q(infer,params);assert q(candidates,params)==rows
  receipt={'candidate_keys':len(rows),'native_relational_keys_and_decisions_agree':True,'materialization_idempotent':True,'derived_edge_removal_empty':True,'rematerialization_identical':True,'protocol_sha256':run}
 finally:
  q("MATCH ()-[r:Transfer25DocumentedRoute {run:$run}]->() DELETE r",params)
  q("MATCH (n) WHERE n.run=$run AND any(l IN labels(n) WHERE l STARTS WITH 'Transfer25') DETACH DELETE n",params)
  assert q(fingerprint)==before
 receipt['original_node_fingerprint_preserved']=True;receipt['overlay_removed']=True
 (R/'results/native_transfer.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--neo4j-url',default='http://127.0.0.1:17474');main(p.parse_args().neo4j_url)
