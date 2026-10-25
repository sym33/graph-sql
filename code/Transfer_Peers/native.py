"""Dedicated-instance comparison; does not access the original study stores."""
from pathlib import Path
import argparse,collections,http.server,json,platform,random,sqlite3,statistics,threading,time,urllib.request,sys
from model import canon,digest,reference,sql,anchored_sql,cypher,SCHEMA
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--output',required=True);p.add_argument('--plan-control',action='store_true');p.add_argument('--pg-user',default=__import__('getpass').getuser());args=p.parse_args()
import psycopg2
from psycopg2.extras import execute_values
R=Path(__file__).resolve().parent;protocol=json.loads((R/'protocol.json').read_text());model=json.loads(Path(args.model).read_text());out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
neo_url='http://127.0.0.1:18774/db/neo4j/tx/commit';pg=psycopg2.connect(host='127.0.0.1',port=15432,dbname='postgres',user=args.pg_user);pg.autocommit=True
NAMES=['Neo4j','SQLite','PostgreSQL']+(['SQLite_anchored','PostgreSQL_anchored'] if args.plan_control else []);db=None
control=json.loads((R/'plan_control_protocol.json').read_text()) if args.plan_control else None

def raw_query(url,statement,parameters=None):
 req=urllib.request.Request(url,data=json.dumps({'statements':[{'statement':statement,'parameters':parameters or {}}]}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=180) as f:x=json.load(f)
 assert not x['errors'],x['errors'];r=x['results'][0]
 return [dict(zip(r['columns'],v['row'])) for v in r['data']]
def neo(q,params=None):return raw_query(neo_url,q,params)
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  q=json.loads(self.rfile.read(int(self.headers['Content-Length'])))['statements'][0]['statement']
  try:
   if self.path.startswith('/postgres'):
    with pg.cursor() as c:c.execute(q);cols=[x.name for x in c.description];rows=c.fetchall()
   else:
    c=db.execute(q);cols=[x[0] for x in c.description];rows=c.fetchall()
   payload=json.dumps({'errors':[],'results':[{'columns':cols,'data':[{'row':list(row)} for row in rows]}]}).encode()
   self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
  except Exception as e:
   payload=json.dumps({'errors':[str(e)]}).encode();self.send_response(500);self.end_headers();self.wfile.write(payload)
server=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();urls={'Neo4j':neo_url,'SQLite':f'http://127.0.0.1:{server.server_port}/sqlite','PostgreSQL':f'http://127.0.0.1:{server.server_port}/postgres'}
urls.update(SQLite_anchored=urls['SQLite'],PostgreSQL_anchored=urls['PostgreSQL'])
result={'control_protocol_sha256':digest(control) if control else None,'execution_code_sha256':__import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest(),'executed_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'protocol_sha256':digest(protocol),'input_hashes':model['inputs'],'environment':{'platform':platform.platform(),'python':sys.version,'SQLite':sqlite3.sqlite_version,'PostgreSQL':pg.server_version,'psycopg2':psycopg2.__version__,'Neo4j':neo('CALL dbms.components() YIELD name,versions,edition RETURN name,versions,edition'),'transport':'one local HTTP JSON request per engine; SQL bridge uses sqlite3/psycopg2; Neo4j uses native transactional HTTP; execution, transfer, decode included; sorting and agreement outside timer','PostgreSQL_settings':{},'Neo4j_memory':'heap initial 1G, max 2G; page cache 1G'},'queries':{str(d):{'SQL':sql(d),'Cypher':cypher(d),'SQL_anchored':anchored_sql(d)} for d in protocol['depths']},'construction':[],'measurements':[],'summaries':[],'plans':{},'checks':[]}
with pg.cursor() as c:
 for setting in ('shared_buffers','work_mem','jit','synchronous_commit'):
  c.execute('SHOW '+setting);result['environment']['PostgreSQL_settings'][setting]=c.fetchone()[0]
neo('CREATE CONSTRAINT peer_witness IF NOT EXISTS FOR (w:PeerWitness) REQUIRE w.key IS UNIQUE');neo('CREATE CONSTRAINT peer_code IF NOT EXISTS FOR (c:PeerCode) REQUIRE c.key IS UNIQUE');neo('CREATE INDEX peer_anchor IF NOT EXISTS FOR (w:PeerWitness) ON (w.ns,w.product)');neo('CALL db.awaitIndexes(120)')
expected_base={d:reference(model,protocol['anchors'],d) for d in protocol['depths']}
def save():out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
def construct(copies):
 global db
 ws=[(ns,w['id'],w['product'],w['code'],w['kind'],w['premises']) for ns in range(copies) for w in model['witnesses']];ps=[(ns,c,p) for ns in range(copies) for c,p in model['parents'].items()];seeds=[(ns,a) for ns in range(copies) for a in protocol['anchors']]
 if db:db.close()
 path=out.parent/f'peers_{copies}.sqlite'
 if path.exists():path.unlink()
 t=time.perf_counter();db=sqlite3.connect(path,check_same_thread=False);db.executescript(SCHEMA);db.executemany('INSERT INTO witness VALUES(?,?,?,?,?,?)',ws);db.executemany('INSERT INTO parent VALUES(?,?,?)',ps);db.executemany('INSERT INTO seed VALUES(?,?)',seeds);db.commit();db.execute('ANALYZE');db.commit();sqlite_s=time.perf_counter()-t
 with pg.cursor() as c:
  c.execute('DROP TABLE IF EXISTS witness,parent,seed');t=time.perf_counter();c.execute(SCHEMA)
  execute_values(c,'INSERT INTO witness VALUES %s',ws,page_size=1000);execute_values(c,'INSERT INTO parent VALUES %s',ps,page_size=1000);execute_values(c,'INSERT INTO seed VALUES %s',seeds);c.execute('ANALYZE witness');c.execute('ANALYZE parent');c.execute('ANALYZE seed')
 pg_s=time.perf_counter()-t
 neo('MATCH (n) DETACH DELETE n');t=time.perf_counter()
 def batch(q,rows):
  for start in range(0,len(rows),1000):neo(q,{'rows':rows[start:start+1000]})
 codes=[{'key':f'{ns}:{c}','ns':ns,'code':c} for ns in range(copies) for c in model['codes']]
 batch('UNWIND $rows AS r CREATE (c:PeerCode) SET c=r',codes)
 wrows=[dict(zip(('ns','id','product','code','kind','premises'),w),key=f'{w[0]}:{w[1]}') for w in ws]
 batch('UNWIND $rows AS r CREATE (w:PeerWitness) SET w=r WITH w,r MATCH (c:PeerCode {key:toString(r.ns)+":"+r.code}) CREATE (w)-[:RECORDED]->(c)',wrows)
 batch('UNWIND $rows AS r MATCH (c:PeerCode {key:r.child}),(p:PeerCode {key:r.parent}) CREATE (c)-[:PARENT]->(p)',[{'child':f'{n}:{c}','parent':f'{n}:{p}'} for n,c,p in ps])
 batch('UNWIND $rows AS r CREATE (s:PeerSeed) SET s=r',[{'ns':n,'product':a} for n,a in seeds]);neo_s=time.perf_counter()-t
 assert neo('MATCH (w:PeerWitness) RETURN count(w) AS n')[0]['n']==len(ws)
 result['construction'].append({'copies':copies,'witnesses':len(ws),'hierarchy_nodes':len(codes),'hierarchy_edges':len(ps),'SQLite_seconds':sqlite_s,'PostgreSQL_seconds':pg_s,'Neo4j_seconds':neo_s,'SQLite_bytes':path.stat().st_size,'scope':'single construction per size; tuning and starting services excluded; native client ingestion paths differ'})
 result['plans'][str(copies)]={}
 for d in protocol['depths']:
  with pg.cursor() as c:c.execute('EXPLAIN (FORMAT JSON) '+sql(d));plan=c.fetchone()[0]
  result['plans'][str(copies)][str(d)]={'SQLite':[list(x) for x in db.execute('EXPLAIN QUERY PLAN '+sql(d))],'PostgreSQL':plan}
 expected={d:sorted([dict(ns=ns,**x) for ns in range(copies) for x in rows],key=canon) for d,rows in expected_base.items()}
 hashes={d:digest(v) for d,v in expected.items()}
 def execute(engine,d,record=True):
  q=cypher(d) if engine=='Neo4j' else (anchored_sql(d) if engine.endswith('_anchored') else sql(d));t=time.perf_counter_ns();rows=raw_query(urls[engine],q);ms=(time.perf_counter_ns()-t)/1e6;rows.sort(key=canon)
  assert rows==expected[d],(engine,copies,d,len(rows),len(expected[d]),rows[:1],expected[d][:1])
  return {'copies':copies,'depth':d,'engine':engine,'retrieval_ms':ms,'rows':len(rows),'answer_sha256':hashes[d]}
 for d in protocol['depths']:
  for engine in NAMES:
   for _ in range(protocol['timing']['warmups']):execute(engine,d)
 # Native ablation and absent-anchor checks at each size; not timed.
 for engine in NAMES:
  for d in protocol['depths']:
   rows=raw_query(urls[engine],cypher(d,True) if engine=='Neo4j' else (anchored_sql(d,True) if engine.endswith('_anchored') else sql(d,True)));rows.sort(key=canon);direct=sorted([dict(ns=ns,**x) for ns in range(copies) for x in reference(model,protocol['anchors'],d,True)],key=canon);assert rows==direct
  result['checks'].append({'copies':copies,'engine':engine,'direct_only_agreement':True})
 rng=random.Random((control['timing']['seed'] if control else protocol['timing']['seed'])+copies)
 for repeat in range(protocol['timing']['repetitions']):
  tasks=[(e,d) for e in NAMES for d in protocol['depths']];rng.shuffle(tasks)
  for e,d in tasks:result['measurements'].append(dict(repeat=repeat,**execute(e,d)))
  print('completed',copies,'repeat',repeat,flush=True);save()
 for e in NAMES:
  for d in protocol['depths']:
   samples=[x['retrieval_ms'] for x in result['measurements'] if (x['copies'],x['engine'],x['depth'])==(copies,e,d)];q=statistics.quantiles(samples,n=4)
   result['summaries'].append({'copies':copies,'engine':e,'depth':d,'median_ms':statistics.median(samples),'q1_ms':q[0],'q3_ms':q[2],'rows':len(expected[d]),'answer_sha256':hashes[d]})
 save()
try:
 for copies in protocol['timing']['copies']:construct(copies)
 result['complete']=True;save();print(json.dumps(result['summaries'],indent=2),flush=True)
finally:server.shutdown();pg.close()
