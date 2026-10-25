"""Five complete source-grounded tasks; timed HTTP access paths and reversible indexes."""
from pathlib import Path
import tempfile,os
import argparse,collections,hashlib,http.server,json,platform,random,re,sqlite3,statistics,sys,threading,time,urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'Graph_Validation_V27/code'))
from workloads import WORKLOADS

def main(root,url,output):
 R=Path(__file__).resolve().parents[1];protocol=json.loads((R/'COMPLEXITY_PROTOCOL.json').read_text());assert hashlib.sha256((R.parent/'Graph_Validation_V27/code/workloads.py').read_bytes()).hexdigest()==protocol['query_sha256']
 root=Path(root);sys.path.insert(0,str(root/'Validation_Study/code'));from reference_oracle import Reference
 ref=Reference(root/'Graph_Validation_V9/temporal_snapshot');canon=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'));digest=lambda x:hashlib.sha256(canon(x).encode()).hexdigest();normalize=lambda rows:sorted(rows,key=canon)
 db=sqlite3.connect(':memory:',check_same_thread=False);db.row_factory=sqlite3.Row
 db.executescript('CREATE TABLE product(id TEXT PRIMARY KEY);CREATE TABLE concept(id TEXT PRIMARY KEY);CREATE TABLE snapshot(id TEXT PRIMARY KEY,file TEXT);CREATE TABLE rule(id TEXT PRIMARY KEY,implementation TEXT);CREATE TABLE record(id TEXT PRIMARY KEY,file TEXT,snapshot TEXT);CREATE TABLE witness(id TEXT PRIMARY KEY,product TEXT,code TEXT,rule TEXT,jurisdiction TEXT,rule_id TEXT,dictionary_snapshot TEXT);CREATE TABLE premise(witness TEXT,record TEXT,PRIMARY KEY(witness,record));CREATE TABLE tariff(id TEXT PRIMARY KEY,code TEXT);CREATE TABLE indication(id TEXT PRIMARY KEY,product TEXT,record TEXT);CREATE INDEX wc ON witness(code);CREATE INDEX wp ON witness(product,rule);CREATE INDEX wj ON witness(jurisdiction,rule);CREATE INDEX pc ON premise(record,witness);CREATE INDEX tc ON tariff(code);CREATE INDEX rf ON record(file);CREATE INDEX ip ON indication(product);')
 ws=list(ref.witnesses.values());ins=list(ref.indications.values());ridrule=lambda w:w['rule']+':'+w['implementation_sha256'];snap=lambda rid:rid.split(':')[1]
 db.executemany('INSERT INTO product VALUES(?)',[(x,) for x in sorted({w['subject'] for w in ws}|{i['subject'] for i in ins})]);db.executemany('INSERT INTO concept VALUES(?)',[(x,) for x in sorted({w['atc'] for w in ws})]);db.executemany('INSERT INTO snapshot VALUES(?,?)',[(sha,f) for f,sha in ref.files.items()]);rules={ridrule(w):w['implementation_sha256'] for w in ws};db.executemany('INSERT INTO rule VALUES(?,?)',rules.items());db.executemany('INSERT INTO record VALUES(?,?,?)',[(rid,rid.split(':')[0],snap(rid)) for rid in ref.records]);db.executemany('INSERT INTO witness VALUES(?,?,?,?,?,?,?)',[(w['id'],w['subject'],w['atc'],w['rule'],w['jurisdiction'],ridrule(w),w['atc_index_snapshot_sha256']) for w in ws]);db.executemany('INSERT INTO premise VALUES(?,?)',[(w['id'],rid) for w in ws for rid in w['premise_ids']]);ts={rid:p for rid,p in ref.records.items() if rid.startswith('ze_definitions.csv:')};db.executemany('INSERT INTO tariff VALUES(?,?)',[(rid,p['code']) for rid,p in ts.items()]);db.executemany('INSERT INTO indication VALUES(?,?,?)',[(i['id'],i['subject'],i['record_id']) for i in ins])
 # Independent Python oracle constructs relation sets from source facts, not timed query outputs.
 ti=collections.defaultdict(list);wi=collections.defaultdict(list);ii=collections.defaultdict(list);direct=collections.defaultdict(list)
 for rid,t in ts.items():ti[t['code']].append(rid)
 docs=[w for w in ws if w['jurisdiction']=='CH' and w['rule'] in {'direct_SAI','via_authorization_SL'}]
 for w in docs:
  wi[w['atc']].append(w)
  if w['rule']=='direct_SAI':direct[w['subject']].append(w)
 for i in ins:ii[i['subject']].append(i)
 expected={k:[] for k in WORKLOADS};pairs=set()
 for w in docs:
  for tid in ti[w['atc']]:
   pairs.add((w['subject'],tid,w['atc']));base={'witness':w['id'],'product':w['subject'],'code':w['atc'],'tariff_record':tid};expected['L1_candidates'].append(base)
   for rid in w['premise_ids']:
    b={**base,'premise':rid,'source_snapshot':snap(rid)};expected['L2_source_lineage'].append(b);expected['L3_rule_dictionary'].append({**b,'derivation_rule':ridrule(w),'implementation':w['implementation_sha256'],'dictionary_snapshot':w['atc_index_snapshot_sha256'],'tariff_snapshot':snap(tid)})
   if w['rule']=='via_authorization_SL':
    sid=next(x for x in w['premise_ids'] if x.startswith('sai_praeparate.csv:'));lid=next(x for x in w['premise_ids'] if x.startswith('sl.csv:'))
    for a in direct[w['subject']]:
     if sid not in a['premise_ids']:continue
     expected['L4_cross_source_context'].append({'direct_witness':a['id'],'package_witness':w['id'],'product':w['subject'],'direct_code':a['atc'],'package_code':w['atc'],'tariff_record':tid,'authorization_record':sid,'package_record':lid,'authorization_snapshot':snap(sid),'package_snapshot':snap(lid),'direct_rule':ridrule(a),'package_rule':ridrule(w),'direct_dictionary':a['atc_index_snapshot_sha256'],'package_dictionary':w['atc_index_snapshot_sha256']})
 for subject,tid,code in sorted(pairs):
  peers=[w for w in wi[code] if w['subject']!=subject and ii[w['subject']]]
  if not peers:continue
  indic={i['id']:i for w in peers for i in ii[w['subject']]};expected['L5_peer_indication_evidence'].append({'product':subject,'tariff_record':tid,'peer_count':len({w['subject'] for w in peers}),'indication_witnesses':len(indic),'source_records':len({i['record_id'] for i in indic.values()}),'derivation_rules':len({ridrule(w) for w in peers})})
 expected={k:normalize(v) for k,v in expected.items()}
 db.commit();diskdir=tempfile.TemporaryDirectory(prefix='medigraph-sqlite-');diskpath=Path(diskdir.name)/'comparison.sqlite';disk=sqlite3.connect(str(diskpath),check_same_thread=False);disk.row_factory=sqlite3.Row;db.backup(disk);disk.commit();disk.close();disk=sqlite3.connect(str(diskpath),check_same_thread=False);disk.row_factory=sqlite3.Row
 assert list(db.execute('SELECT count(*) FROM witness'))[0][0]==list(disk.execute('SELECT count(*) FROM witness'))[0][0]
 class Handler(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));sql=body['statements'][0]['statement'];connection=disk if self.path.startswith('/disk/') else db;rows=[dict(x) for x in connection.execute(sql)];cols=list(rows[0]) if rows else [];payload=json.dumps({'errors':[],'results':[{'columns':cols,'data':[{'row':[x[c] for c in cols]} for x in rows]}]}).encode();self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 server=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();sqlurl='http://127.0.0.1:'+str(server.server_port)
 def query(base,statement):
  req=urllib.request.Request(base+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':statement}]}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=protocol['timeout_seconds']) as f:x=json.load(f)
  assert not x['errors'],x['errors'];r=x['results'][0]
  if statement.startswith('EXPLAIN '):return r['plan']
  return [dict(zip(r['columns'],z['row'])) for z in r['data']]
 before=query(url,'SHOW INDEXES YIELD name,type,labelsOrTypes,properties,state RETURN name,type,labelsOrTypes,properties,state');names={x['name'] for x in before};newindexes=[('Complex27_assoc_scope','CREATE RANGE INDEX Complex27_assoc_scope IF NOT EXISTS FOR (n:Association) ON (n.jurisdiction,n.rule)'),('Complex27_assoc_subject','CREATE RANGE INDEX Complex27_assoc_subject IF NOT EXISTS FOR (n:Association) ON (n.subject,n.rule)'),('Complex27_tariff_code','CREATE RANGE INDEX Complex27_tariff_code IF NOT EXISTS FOR (n:SourceRecord) ON (n.file,n.tariff_atc)')];assert not names.intersection(x[0] for x in newindexes)
 result={'protocol_sha256':hashlib.sha256((R/'COMPLEXITY_PROTOCOL.json').read_bytes()).hexdigest(),'environment':{'platform':platform.platform(),'python':sys.version,'SQLite':sqlite3.sqlite_version},'input_hashes':ref.files,'measurements':[],'summaries':[],'queries':WORKLOADS,'SQL_plans':{k:[dict(x) for x in db.execute('EXPLAIN QUERY PLAN '+v['SQL'])] for k,v in WORKLOADS.items()},'SQLite_storage':{'memory':':memory:','disk':'temporary file, committed, closed and reopened before warmups','disk_bytes':diskpath.stat().st_size,'cache':'warm; no OS-cache eviction','journal_mode':disk.execute('PRAGMA journal_mode').fetchone()[0]},'SQL_schema':[dict(x) for x in db.execute('SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL')]}
 def execute(k,e):
  start=time.perf_counter_ns();rows=query(sqlurl+('/disk' if e=='SQLite_disk_HTTP' else '') if e.startswith('SQLite') else url,WORKLOADS[k]['SQL' if e.startswith('SQLite') else 'Cypher']);ms=(time.perf_counter_ns()-start)/1e6;rows=normalize(rows);assert rows==expected[k],(k,e,len(rows),len(expected[k]),rows[:1],expected[k][:1]);return {'workload':k,'engine':e,'retrieval_ms':ms,'rows':len(rows),'output_sha256':digest(rows)}
 try:
  start=time.perf_counter()
  for name,statement in newindexes:query(url,statement)
  query(url,'CALL db.awaitIndexes(120)');result['additional_Neo4j_index_creation_seconds']=time.perf_counter()-start;result['Neo4j_indexes_during_run']=query(url,'SHOW INDEXES YIELD name,type,labelsOrTypes,properties,state RETURN name,type,labelsOrTypes,properties,state');result['Neo4j_version']=query(url,'CALL dbms.components() YIELD name,versions,edition RETURN name,versions,edition')
  result['Neo4j_plans']={k:query(url,'EXPLAIN '+w['Cypher']) for k,w in WORKLOADS.items()}
  for k in WORKLOADS:
   for e in ['SQLite_HTTP','SQLite_disk_HTTP','Neo4j_HTTP']:
    for _ in range(protocol['warmups']):execute(k,e)
  rng=random.Random(protocol['seed'])
  for repeat in range(protocol['repetitions']):
   order=[(k,e) for k in WORKLOADS for e in ['SQLite_HTTP','SQLite_disk_HTTP','Neo4j_HTTP']];rng.shuffle(order)
   for k,e in order:result['measurements'].append({'repeat':repeat,**execute(k,e)})
  for k,w in WORKLOADS.items():
   for e in ['SQLite_HTTP','SQLite_disk_HTTP','Neo4j_HTTP']:
    xs=[x['retrieval_ms'] for x in result['measurements'] if x['workload']==k and x['engine']==e];q=statistics.quantiles(xs,n=4);result['summaries'].append({'workload':k,'engine':e,'rows':len(expected[k]),'SQL_JOIN_count':len(re.findall(r'\bJOIN\b',w['SQL'])),'median_ms':statistics.median(xs),'q1_ms':q[0],'q3_ms':q[2],'min_ms':min(xs),'max_ms':max(xs)})
  result['all_complete_outputs_equal']=True
 except Exception as error:
  result['failure']=repr(error);Path(output).write_text(json.dumps(result,indent=2)+'\n');raise
 finally:
  for name,_ in newindexes:
   if name not in names:query(url,'DROP INDEX '+name+' IF EXISTS')
  after=query(url,'SHOW INDEXES YIELD name,type,labelsOrTypes,properties,state RETURN name,type,labelsOrTypes,properties,state');assert normalize(before)==normalize(after);result['original_indexes_restored']=True;server.shutdown();server.server_close();disk.close();db.close();diskdir.cleanup()
 Path(output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['summaries'],indent=2),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--neo4j-url',default='http://127.0.0.1:17474');a.add_argument('--output',required=True);x=a.parse_args();main(x.root,x.neo4j_url.rstrip('/'),x.output)
