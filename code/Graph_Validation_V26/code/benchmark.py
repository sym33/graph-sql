"""Protocol-bound warm-cache retrieval benchmark, with explicit transport asymmetry."""
from pathlib import Path
import http.server,threading,argparse,ast,collections,hashlib,json,platform,random,sqlite3,statistics,sys,time,urllib.request

def main(root,url,out):
 root=Path(root);sys.path.insert(0,str(root/'Validation_Study/code'));from reference_oracle import Reference
 protocol=json.loads(Path(__file__).resolve().parents[1].joinpath('BENCHMARK_HTTP_PROTOCOL.json').read_text())
 source=root/'Graph_Validation_V22/code/explanation_workflow.py';assert hashlib.sha256(source.read_bytes()).hexdigest()==protocol['query_source_sha256']
 tree=ast.parse(source.read_text());queries={}
 for node in tree.body:
  if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant):
   for target in node.targets:
    if isinstance(target,ast.Name) and target.id in {'SQL','CYPHER'}:queries[target.id]=node.value.value
 canon=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
 digest=lambda x:hashlib.sha256(canon(x).encode()).hexdigest()
 def normalize(rows):
  for x in rows:
   x['tariff_payload']=json.loads(x['tariff_payload']) if isinstance(x['tariff_payload'],str) else x['tariff_payload']
   x['premises']=json.loads(x['premises']) if isinstance(x['premises'],str) else x['premises']
   for p in x['premises']:
    if isinstance(p['payload'],str):p['payload']=json.loads(p['payload'])
   x['premises']=sorted(x['premises'],key=lambda p:p['id'])
  return sorted(rows,key=lambda x:(x['witness'],x['tariff_record']))
 setup=time.perf_counter();ref=Reference(root/'Graph_Validation_V9/temporal_snapshot');db=sqlite3.connect(':memory:',check_same_thread=False);db.row_factory=sqlite3.Row
 db.executescript('CREATE TABLE record(id TEXT PRIMARY KEY,payload TEXT);CREATE TABLE witness(id TEXT PRIMARY KEY,product TEXT,code TEXT,rule TEXT,jurisdiction TEXT);CREATE TABLE premise(witness TEXT,record TEXT,PRIMARY KEY(witness,record));CREATE TABLE tariff(id TEXT PRIMARY KEY,code TEXT,payload TEXT);CREATE INDEX witness_code ON witness(code);CREATE INDEX premise_witness ON premise(witness);CREATE INDEX tariff_code ON tariff(code);')
 db.executemany('INSERT INTO record VALUES(?,?)',[(rid,canon(p)) for rid,p in ref.records.items()]);db.executemany('INSERT INTO witness VALUES(?,?,?,?,?)',[(w['id'],w['subject'],w['atc'],w['rule'],w['jurisdiction']) for w in ref.witnesses.values()]);db.executemany('INSERT INTO premise VALUES(?,?)',[(w['id'],rid) for w in ref.witnesses.values() for rid in w['premise_ids']]);tariffs={rid:p for rid,p in ref.records.items() if rid.startswith('ze_definitions.csv:')};db.executemany('INSERT INTO tariff VALUES(?,?,?)',[(rid,p['code'],canon(p)) for rid,p in tariffs.items()]);setup=time.perf_counter()-setup
 class SQLHandler(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));rules=body['statements'][0]['parameters']['rules'];rows=[dict(x) for x in db.execute(queries['SQL'],(json.dumps(rules),)).fetchall()];columns=list(rows[0]) if rows else [];payload=json.dumps({'errors':[],'results':[{'columns':columns,'data':[{'row':[x[c] for c in columns]} for x in rows]}]}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 server=http.server.HTTPServer(('127.0.0.1',0),SQLHandler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();sql_url='http://127.0.0.1:'+str(server.server_port)
 def neo(statement,params=None,base=None):
  req=urllib.request.Request((base or url).rstrip('/')+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':statement,'parameters':params or {}}]}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=180) as response:data=json.load(response)
  assert not data['errors'],data['errors'];r=data['results'][0];return [dict(zip(r['columns'],x['row'])) for x in r['data']]
 scopes={'direct':['direct_SAI'],'alternative_source':['direct_SAI','via_authorization_SL'],'historical_context':['direct_SAI','via_authorization_SL','historical_candidate']};expected={}
 for name,rules in scopes.items():
  expected[name]=normalize([{'witness':w['id'],'product':w['subject'],'code':w['atc'],'rule':w['rule'],'tariff_record':rid,'tariff_payload':p,'premises':[{'id':r,'payload':ref.records[r]} for r in w['premise_ids']]} for w in ref.witnesses.values() if w['jurisdiction']=='CH' and w['rule'] in rules for rid,p in tariffs.items() if p['code']==w['atc']])
 def execute(name,engine):
  start=time.perf_counter_ns()
  rows=[dict(x) for x in db.execute(queries['SQL'],(json.dumps(scopes[name]),)).fetchall()] if engine=='SQLite' else neo(queries['SQL'] if engine=='SQLite_HTTP' else queries['CYPHER'],{'rules':scopes[name]},sql_url if engine=='SQLite_HTTP' else None)
  retrieval=(time.perf_counter_ns()-start)/1e6;start=time.perf_counter_ns();rows=normalize(rows);assert rows==expected[name];normalization=(time.perf_counter_ns()-start)/1e6
  return {'workload':name,'engine':engine,'retrieval_ms':retrieval,'normalization_and_equality_ms':normalization,'rows':len(rows),'output_sha256':digest(rows)}
 for name in scopes:
  for engine in ['SQLite','SQLite_HTTP','Neo4j_HTTP']:
   for _ in range(protocol['warmups_per_workload_engine']):execute(name,engine)
 rng=random.Random(protocol['seed']);measurements=[]
 for repeat in range(protocol['measured_repetitions_per_workload_engine']):
  order=[(n,e) for n in scopes for e in ['SQLite','SQLite_HTTP','Neo4j_HTTP']];rng.shuffle(order)
  for n,e in order:measurements.append({'repeat':repeat,**execute(n,e)})
 summaries=[]
 for n in scopes:
  for e in ['SQLite','SQLite_HTTP','Neo4j_HTTP']:
   xs=[m['retrieval_ms'] for m in measurements if m['workload']==n and m['engine']==e];summaries.append({'workload':n,'engine':e,'n':len(xs),'rows':len(expected[n]),'median_ms':statistics.median(xs),'q1_ms':statistics.quantiles(xs,n=4)[0],'q3_ms':statistics.quantiles(xs,n=4)[2],'min_ms':min(xs),'max_ms':max(xs)})
 result={'protocol_sha256':hashlib.sha256(Path(__file__).resolve().parents[1].joinpath('BENCHMARK_HTTP_PROTOCOL.json').read_bytes()).hexdigest(),'environment':{'platform':platform.platform(),'python':sys.version,'SQLite':sqlite3.sqlite_version,'Neo4j':neo('CALL dbms.components() YIELD name,versions,edition RETURN name,versions,edition'),'indexes':neo('SHOW INDEXES YIELD name,type,labelsOrTypes,properties,state RETURN name,type,labelsOrTypes,properties,state'),'SQL_schema':[dict(x) for x in db.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL")]},'SQLite_setup_seconds_not_comparable_to_existing_Neo4j_load':setup,'all_complete_outputs_equal':True,'warmups':27,'measured_queries':len(measurements),'retrieval_query_text_versions':{'SQL':1,'Cypher':1},'retrieval_text_changes_across_scopes':{'SQL':0,'Cypher':0},'summaries':summaries,'measurements':measurements,'interpretation':protocol['target'],'input_hashes':ref.files}
 server.shutdown();server.server_close()
 Path(out).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--neo4j-url',default='http://127.0.0.1:17474');a.add_argument('--output',required=True);args=a.parse_args();main(args.root,args.neo4j_url,args.output)
