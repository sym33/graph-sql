"""Native Cypher: source-bound strength numerator judgments and field revelation."""
from pathlib import Path
import argparse,hashlib,json,sys,urllib.request
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path.insert(0,str(P/'Graph_Validation_V30/code'))
from completion_kernel import Completion,Field,Question

def main(url):
 data=json.loads((R/'results/extended_transfer.json').read_text());d=data['datasets']['June'];run=data['protocol_sha256'];vocabulary=json.loads((R/'PROTOCOL.json').read_text())['vocabulary']
 fields=[Field(x['field'],frozenset(vocabulary),frozenset(x['known'])) for x in d['fields_receipt']];questions=[Question(x['id'],tuple(x['fields']),frozenset(x['options'])) for x in d['questions_receipt']];model=Completion(fields,questions,vocabulary)
 def query(statement,parameters=None):
  request=urllib.request.Request(url+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':statement,'parameters':parameters or {}}]}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(request,timeout=180) as response:r=json.load(response)
  assert not r['errors'],r['errors'];result=r['results'][0];return [dict(zip(result['columns'],row['row'])) for row in result['data']]
 nodefp="MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH 'Evidence31') RETURN elementId(n) AS id,labels(n) AS labels,properties(n) AS properties ORDER BY id"
 relfp="MATCH ()-[r]->() WHERE NOT type(r) STARTS WITH 'Evidence31' RETURN elementId(r) AS id,type(r) AS type,properties(r) AS properties ORDER BY id"
 digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 before_nodes=digest(query(nodefp));before_rels=digest(query(relfp));assert query("MATCH (n) WHERE n.run=$run AND any(l IN labels(n) WHERE l STARTS WITH 'Evidence31') RETURN count(n) AS count",{'run':run})==[{'count':0}]
 bound=query("UNWIND $ids AS id MATCH (r:SourceRecord {id:id}) RETURN id,r.payload_json AS payload",{'ids':[f.key for f in fields]});assert {x['id']:json.loads(x['payload'])['bezeichnung'] for x in bound}=={x['field']:x['package'] for x in d['fields_receipt']}
 rows=[{'id':f.key,'known':sorted(f.known),'possible':sorted(f.possible)} for f in fields]
 qrows=[{'id':q.key,'fields':list(q.fields),'options':sorted(q.options),'product':json.loads(q.key)[0],'tariff':json.loads(q.key)[1]} for q in questions]
 statement="""MATCH (q:Evidence31Question {run:$run}) OPTIONAL MATCH (q)-[:Evidence31Uses]->(f:Evidence31Field)
 WITH q,f,CASE WHEN f.id IN $hidden THEN [] ELSE f.known END AS k
 WITH q,CASE WHEN f IS NULL OR size(q.options)=0 THEN 1
 WHEN size(k)>0 THEN CASE WHEN any(x IN k WHERE x IN q.options) THEN 2 WHEN any(x IN q.options WHERE NOT x IN $vocabulary) THEN 1 ELSE 0 END
 WHEN all(x IN f.possible WHERE x IN q.options) THEN 2
 WHEN any(x IN q.options WHERE NOT x IN $vocabulary) THEN 1
 WHEN any(x IN f.possible WHERE x IN q.options) THEN 1 ELSE 0 END AS s
 RETURN q.id AS id,CASE max(s) WHEN 2 THEN 'V' WHEN 0 THEN 'C' ELSE 'U' END AS state ORDER BY id"""
 receipts=[]
 try:
  query("UNWIND $rows AS row MATCH (r:SourceRecord {id:row.id}) CREATE (f:Evidence31Field {run:$run,id:row.id,known:row.known,possible:row.possible}) CREATE (f)-[:Evidence31FromRecord]->(r)",{'run':run,'rows':rows})
  query("UNWIND $rows AS row MATCH (p:ProductRef {id:row.product}),(z:SourceRecord {id:row.tariff}) CREATE (q:Evidence31Question {run:$run,id:row.id,options:row.options}) CREATE (q)-[:Evidence31About]->(p) CREATE (q)-[:Evidence31Tariff]->(z)",{'run':run,'rows':qrows})
  query("UNWIND $rows AS row MATCH (q:Evidence31Question {run:$run,id:row.id}) UNWIND row.fields AS id MATCH (f:Evidence31Field {run:$run,id:id}) CREATE (q)-[:Evidence31Uses]->(f)",{'run':run,'rows':qrows})
  eligible=[f.key for f in fields if f.known]
  arms=[('observed',0,[])]+[(p,b,list(set(eligible)-{x['field'] for x in d['acquisition'][t][:b]})) for p,t in [('bounds','bound_trace'),('degree','degree_trace'),('interpreted_degree','interpreted_degree_trace')] for b in [0,5,20]]
  for policy,budget,hidden in arms:
   expected=model.states({f:frozenset() for f in hidden});actual={x['id']:x['state'] for x in query(statement,{'run':run,'hidden':hidden,'vocabulary':vocabulary})};assert actual==expected
   receipts.append({'policy':policy,'budget':budget,'questions':len(actual),'status':{s:list(actual.values()).count(s) for s in sorted(set(actual.values()))},'agreement':True})
 finally:
  query("MATCH (n) WHERE n.run=$run AND any(l IN labels(n) WHERE l STARTS WITH 'Evidence31') DETACH DELETE n",{'run':run})
  assert digest(query(nodefp))==before_nodes and digest(query(relfp))==before_rels
 receipt={'protocol_sha256':run,'source_fields_authenticated':len(fields),'queries':receipts,'overlay_removed':True,'original_node_and_relationship_fingerprints_preserved':True,'Cypher':statement}
 (R/'results/native_units.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='Cypher'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--neo4j-url',default='http://127.0.0.1:17474');main(p.parse_args().neo4j_url)
