"""Exploratory join-order control after the registered four-arm experiment."""
from pathlib import Path
import argparse,http.server,json,random,re,sqlite3,sys,threading,time,hashlib
from compare import query,norm,digest,summary,expected_outputs,workloads

def main(root,updated,database,receipt,url,output):
 assert url=='http://127.0.0.1:18474'
 sys.path.insert(0,str(root.resolve()/'Validation_Study/code'));from reference_oracle import Reference
 ref=Reference(updated);ws=workloads(root);expected=expected_outputs(ref,ws)
 db=sqlite3.connect('file:'+str(database.resolve())+'?mode=ro',uri=True,check_same_thread=False);db.row_factory=sqlite3.Row
 cases={}
 for k in ['L4_cross_source_context','L5_peer_indication_evidence']:
  for stored in [False,True]:
   sql=ws[k]['SQL_stored' if stored else 'SQL'];cypher=ws[k]['Cypher_stored' if stored else 'Cypher'];cases[(k,'SQLite_auto',stored)]=sql;cases[(k,'SQLite_ordered',stored)]=re.sub(r'\bJOIN\b','CROSS JOIN',sql);cases[(k,'Neo4j',stored)]=cypher
 class Handler(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));rows=[dict(x) for x in db.execute(body['statements'][0]['statement'])];cols=list(rows[0]) if rows else [];b=json.dumps({'errors':[],'results':[{'columns':cols,'data':[{'row':[r[c] for c in cols]} for r in rows]}]}).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 server=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();sqlurl='http://127.0.0.1:'+str(server.server_port)
 result={'status':'exploratory robustness control, selected after inspecting the registered SQLite plans','initial_receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'change':'Replace every inner JOIN by CROSS JOIN while retaining all ON predicates; SQL schema, indexes and data unchanged.','state':'October','measurements':[],'queries':{' / '.join(map(str,k)):v for k,v in cases.items()},'plans':{' / '.join(map(str,k)):[dict(r) for r in db.execute('EXPLAIN QUERY PLAN '+s)] for k,s in cases.items() if k[1].startswith('SQLite')}}
 def execute(case):
  k,e,stored=case;start=time.perf_counter_ns();rows=query(url if e=='Neo4j' else sqlurl,cases[case]);elapsed=(time.perf_counter_ns()-start)/1e6;rows=norm(rows);assert rows==expected[k],(case,len(rows),len(expected[k]));return {'workload':k,'engine':e,'stored':stored,'milliseconds':elapsed,'rows':len(rows),'sha256':digest(rows)}
 try:
  for case in cases:
   for _ in range(3):execute(case)
  rng=random.Random(95317)
  for repeat in range(15):
   order=list(cases);rng.shuffle(order)
   for case in order:result['measurements'].append({'repeat':repeat,**execute(case)})
   print('plan-control repetition',repeat+1,'of 15',flush=True)
  result['summaries']=summary(result['measurements'],['workload','engine','stored']);result['all_complete_outputs_equal']=True;output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['summaries'],indent=2),flush=True)
 finally:server.shutdown();server.server_close();db.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--updated',type=Path,required=True);p.add_argument('--database',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--neo4j-url',default='http://127.0.0.1:18474');p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root,a.updated,a.database,a.receipt,a.neo4j_url,a.output)
