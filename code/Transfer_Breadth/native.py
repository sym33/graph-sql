"""Native real-entity growth comparison on dedicated test stores."""
from pathlib import Path
import argparse,hashlib,http.server,json,platform,random,sqlite3,statistics,sys,threading,time,urllib.request,datetime,getpass
R=Path(__file__).resolve().parent;sys.path[:0]=[str(R.parent/'Transfer_Peers'),str(R.parent)]
from model import canon,digest,reference,sql,anchored_sql,cypher,SCHEMA
p=argparse.ArgumentParser();p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
import psycopg2
from psycopg2.extras import execute_values
protocol=json.loads((R/'protocol.json').read_text());cases=json.loads(a.models.read_text());assert cases['protocol_sha256']==digest(protocol)
neo_url='http://127.0.0.1:18774/db/neo4j/tx/commit';pg=psycopg2.connect(host='127.0.0.1',port=15432,user=getpass.getuser(),dbname='postgres');pg.autocommit=True;db=None

def fetch(url,q,parameters=None,plan=False):
 body=json.dumps({'statements':[{'statement':q,'parameters':parameters or {}}]}).encode()
 with urllib.request.urlopen(urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'}),timeout=180) as f:x=json.load(f)
 assert not x['errors'],x['errors'];r=x['results'][0]
 return r['plan'] if plan else [dict(zip(r['columns'],v['row'])) for v in r['data']]
def neo(q,params=None,plan=False):return fetch(neo_url,q,params,plan)
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  q=json.loads(self.rfile.read(int(self.headers['Content-Length'])))['statements'][0]['statement']
  if self.path.startswith('/pg'):
   with pg.cursor() as c:c.execute(q);cols=[x.name for x in c.description];rows=c.fetchall()
  else:
   c=db.execute(q);cols=[x[0] for x in c.description];rows=c.fetchall()
  body=json.dumps({'errors':[],'results':[{'columns':cols,'data':[{'row':list(v)} for v in rows]}]}).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
urls={'Neo4j':neo_url,'SQLite_global':base+'/sql','SQLite_anchored':base+'/sql','PostgreSQL_global':base+'/pg','PostgreSQL_anchored':base+'/pg'}
queries={e:{d:cypher(d) if e=='Neo4j' else (anchored_sql(d) if e.endswith('_anchored') else sql(d)) for d in protocol['depths']} for e in protocol['arms']}
out={'protocol_sha256':digest(protocol),'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'input_models_sha256':hashlib.sha256(a.models.read_bytes()).hexdigest(),'environment':{'python':sys.version,'platform':platform.platform(),'SQLite':sqlite3.sqlite_version,'PostgreSQL':pg.server_version,'psycopg2':psycopg2.__version__,'Neo4j':neo('CALL dbms.components() YIELD versions,edition RETURN versions,edition'),'transport':'Full local HTTP response and decoding; SQL Python bridge versus native Neo4j HTTP. Same dedicated instance settings as Transfer_Peers.'},'queries':{e:{str(d):q for d,q in qs.items()} for e,qs in queries.items()},'cases':[],'measurements':[],'summaries':[],'checks':[]}
a.output.parent.mkdir(parents=True,exist_ok=True)
def save():a.output.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
neo('CREATE CONSTRAINT peer_witness IF NOT EXISTS FOR (w:PeerWitness) REQUIRE w.key IS UNIQUE');neo('CREATE CONSTRAINT peer_code IF NOT EXISTS FOR (c:PeerCode) REQUIRE c.key IS UNIQUE');neo('CREATE INDEX peer_anchor IF NOT EXISTS FOR (w:PeerWitness) ON (w.ns,w.product)');neo('CALL db.awaitIndexes(120)')
def batch(q,rows):
 for i in range(0,len(rows),1000):neo(q,{'rows':rows[i:i+1000]})
try:
 for ci,case in enumerate(cases['cases']):
  key=f"{case['corpus']}:{case['fraction']}";m=case['model'];anchors=case['anchors'];ws=[(0,w['id'],w['product'],w['code'],w['kind'],w['premises']) for w in m['witnesses']];parents=[(0,c,p) for c,p in m['parents'].items()];seeds=[(0,x) for x in anchors]
  if db:db.close()
  path=a.output.parent/f'breadth_{ci}.sqlite'
  if path.exists():path.unlink()
  db=sqlite3.connect(path,check_same_thread=False);db.executescript(SCHEMA);db.executemany('INSERT INTO witness VALUES(?,?,?,?,?,?)',ws);db.executemany('INSERT INTO parent VALUES(?,?,?)',parents);db.executemany('INSERT INTO seed VALUES(?,?)',seeds);db.commit();db.execute('ANALYZE');db.commit()
  with pg.cursor() as c:
   c.execute('DROP TABLE IF EXISTS witness,parent,seed');c.execute(SCHEMA);execute_values(c,'INSERT INTO witness VALUES %s',ws);execute_values(c,'INSERT INTO parent VALUES %s',parents);execute_values(c,'INSERT INTO seed VALUES %s',seeds);c.execute('ANALYZE witness');c.execute('ANALYZE parent');c.execute('ANALYZE seed')
  neo('MATCH (n) WHERE n:PeerWitness OR n:PeerCode OR n:PeerSeed DETACH DELETE n')
  batch('UNWIND $rows AS r CREATE (c:PeerCode) SET c=r',[{'key':'0:'+c,'ns':0,'code':c} for c in m['codes']])
  batch('UNWIND $rows AS r CREATE (w:PeerWitness) SET w=r WITH w,r MATCH (c:PeerCode {key:"0:"+r.code}) CREATE (w)-[:RECORDED]->(c)',[dict(w,ns=0,key='0:'+w['id']) for w in m['witnesses']])
  batch('UNWIND $rows AS r MATCH (c:PeerCode {key:r.child}),(p:PeerCode {key:r.parent}) CREATE (c)-[:PARENT]->(p)',[{'child':'0:'+c,'parent':'0:'+p} for c,p in m['parents'].items()])
  batch('UNWIND $rows AS r CREATE (s:PeerSeed) SET s=r',[{'ns':0,'product':x} for x in anchors])
  expected={d:sorted([dict(ns=0,**r) for r in reference(m,anchors,d)],key=canon) for d in protocol['depths']};hashes={d:digest(x) for d,x in expected.items()}
  plans={}
  for d in protocol['depths']:
   plans[str(d)]={'Neo4j':neo('EXPLAIN '+cypher(d),plan=True)}
   for form,q in [('global',sql(d)),('anchored',anchored_sql(d))]:
    with pg.cursor() as c:c.execute('EXPLAIN (FORMAT JSON) '+q);pgplan=c.fetchone()[0]
    plans[str(d)][form]={'SQLite':[list(x) for x in db.execute('EXPLAIN QUERY PLAN '+q)],'PostgreSQL':pgplan}
  out['cases'].append({'key':key,'corpus':case['corpus'],'fraction':case['fraction'],'anchors':anchors,'structure':case['structure'],'source_hashes':m['inputs'],'plans':plans})
  def execute(e,d):
   t=time.perf_counter_ns();rows=fetch(urls[e],queries[e][d]);ms=(time.perf_counter_ns()-t)/1e6;rows.sort(key=canon);assert rows==expected[d],(key,e,d,len(rows),len(expected[d]))
   return {'key':key,'engine':e,'depth':d,'retrieval_ms':ms,'rows':len(rows),'answer_sha256':hashes[d]}
  for e in protocol['arms']:
   for d in protocol['depths']:
    for _ in range(protocol['timing']['warmups']):execute(e,d)
  rng=random.Random(protocol['timing']['seed']+ci)
  for repeat in range(protocol['timing']['repetitions']):
   jobs=[(e,d) for e in protocol['arms'] for d in protocol['depths']];rng.shuffle(jobs)
   for e,d in jobs:out['measurements'].append(dict(repeat=repeat,**execute(e,d)))
   save();print(key,'repeat',repeat,flush=True)
  for e in protocol['arms']:
   for d in protocol['depths']:
    samples=[x['retrieval_ms'] for x in out['measurements'] if x['key']==key and x['engine']==e and x['depth']==d];q=statistics.quantiles(samples,n=4)
    out['summaries'].append({'key':key,'engine':e,'depth':d,'median_ms':statistics.median(samples),'q1_ms':q[0],'q3_ms':q[2],'rows':len(expected[d]),'answer_sha256':hashes[d]})
  # Absent-source entity is a native negative control for each backend.
  neo('MATCH (s:PeerSeed) DELETE s');neo('CREATE (:PeerSeed {ns:0,product:"ABSENT_CONTROL"})');db.execute('DELETE FROM seed');db.execute("INSERT INTO seed VALUES(0,'ABSENT_CONTROL')");db.commit()
  with pg.cursor() as c:c.execute('DELETE FROM seed');c.execute("INSERT INTO seed VALUES(0,'ABSENT_CONTROL')")
  for e in protocol['arms']:assert fetch(urls[e],queries[e][4])==[]
  out['checks'].append({'key':key,'absent_anchor_all_variants':True});save()
 out['complete']=True;save();print('ALL CASES COMPLETE',flush=True)
finally:server.shutdown();pg.close()
