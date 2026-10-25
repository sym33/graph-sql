"""Native Cypher replay of the new cohort's immutable field dependencies."""
from pathlib import Path
import argparse,hashlib,json,sys,urllib.request
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'code'),str(R.parent/'Graph_Validation_V17/code')]
from completion_kernel import Completion,Field,Question
from route_policies import TOKENS

def main(url):
 data=json.loads((R/'results/transfer.json').read_text());protocol=json.loads((R/'PROTOCOL.json').read_text());run=data['protocol_sha256'];ema=data['EMA']
 def q(statement,parameters=None):
  request=urllib.request.Request(url+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':statement,'parameters':parameters or {}}]}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(request,timeout=180) as response:r=json.load(response)
  assert not r['errors'],r['errors'];result=r['results'][0];return [dict(zip(result['columns'],row['row'])) for row in result['data']]
 nodefp="MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH 'Evidence30') RETURN elementId(n) AS id,labels(n) AS labels,properties(n) AS properties ORDER BY id"
 relfp="MATCH ()-[r]->() WHERE NOT type(r) STARTS WITH 'Evidence30' RETURN elementId(r) AS id,type(r) AS type,properties(r) AS properties ORDER BY id"
 digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 before_nodes=digest(q(nodefp));before_rels=digest(q(relfp))
 assert q("MATCH (n) WHERE n.run=$run AND any(l IN labels(n) WHERE l STARTS WITH 'Evidence30') RETURN count(n) AS count",{'run':run})==[{'count':0}]
 meds=ema['medicines'];expected={(m['page_url'],m['ATC']) for m in meds}
 matches=q("UNWIND $ids AS id MATCH (a:Association {rule:'direct_EMA'})-[:ABOUT_PRODUCT]->(p:ProductRef {id:'EMA:medicine:'+id}),(a)-[:TARGET_ATC]->(c:ATCConcept) RETURN DISTINCT id,c.id AS code",{'ids':[m['page_url'] for m in meds]});assert {(x['id'],x['code']) for x in matches}==expected
 fields=[Field(m['page_url'],frozenset(protocol['possibilities']['unknown']),frozenset(m['routes']) if m['complete_inventory'] else frozenset()) for m in meds];inventories={f.key:f.known for f in fields};keys=[(a,b,r) for a,rs in inventories.items() for r in sorted(rs) for b in inventories if a!=b]
 model=Completion(fields,[Question(json.dumps([a,b,r],sort_keys=True,ensure_ascii=False,separators=(',',':')),(b,),frozenset({r})) for a,b,r in keys],TOKENS)
 rows=[{'id':f.key,'known':sorted(f.known),'possible':sorted(f.possible),'sha':m['pdf_sha256']} for f,m in zip(fields,meds)]
 questions=[{'id':qu.key,'field':qu.fields[0],'options':sorted(qu.options)} for qu in model.questions.values()]
 statement="""MATCH (q:Evidence30Question {run:$run})-[:Evidence30Uses]->(f:Evidence30Field)
 WITH q,f,CASE WHEN f.id IN $hidden THEN [] ELSE f.known END AS k
 RETURN q.id AS id,CASE WHEN size(q.options)=0 THEN 'U'
 WHEN size(k)>0 THEN CASE WHEN any(x IN k WHERE x IN q.options) THEN 'V' WHEN any(x IN q.options WHERE NOT x IN $vocabulary) THEN 'U' ELSE 'C' END
 WHEN all(x IN f.possible WHERE x IN q.options) THEN 'V'
 WHEN any(x IN q.options WHERE NOT x IN $vocabulary) THEN 'U'
 WHEN any(x IN f.possible WHERE x IN q.options) THEN 'U' ELSE 'C' END AS state ORDER BY id"""
 try:
  q("UNWIND $rows AS row MATCH (p:ProductRef {id:'EMA:medicine:'+row.id}) CREATE (f:Evidence30Field {run:$run,id:row.id,known:row.known,possible:row.possible,pdf_sha256:row.sha}) CREATE (f)-[:Evidence30FromMedicine]->(p)",{'run':run,'rows':rows})
  q("UNWIND $rows AS row MATCH (f:Evidence30Field {run:$run,id:row.field}) CREATE (q:Evidence30Question {run:$run,id:row.id,options:row.options}) CREATE (q)-[:Evidence30Uses]->(f)",{'run':run,'rows':questions})
  eligible=[f.key for f in fields if f.known];order=[x['field'] for x in ema['acquisition']['bound_trace']];receipts=[]
  for budget in [0]+[x['budget'] for x in ema['acquisition']['curves']]:
   hidden=eligible if budget==0 else list(set(eligible)-set(order[:budget]));observed={x['id']:x['state'] for x in q(statement,{'run':run,'hidden':hidden,'vocabulary':sorted(TOKENS)})};expected=model.states({key:frozenset() for key in hidden});assert observed==expected;receipts.append({'budget':budget,'questions':len(observed),'status':{state:list(observed.values()).count(state) for state in sorted(set(observed.values()))},'agreement':True})
 finally:
  q("MATCH (n) WHERE n.run=$run AND any(l IN labels(n) WHERE l STARTS WITH 'Evidence30') DETACH DELETE n",{'run':run})
  assert digest(q(nodefp))==before_nodes and digest(q(relfp))==before_rels
 receipt={'protocol_sha256':run,'source_medicines_bound_to_original_graph':len(meds),'queries':receipts,'original_node_and_relationship_fingerprints_preserved':True,'overlay_removed':True,'Cypher':statement}
 (R/'results/native_completion.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='Cypher'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--neo4j-url',default='http://127.0.0.1:17474');main(p.parse_args().neo4j_url)
