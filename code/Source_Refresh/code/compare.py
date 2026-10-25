"""Four-arm source-refresh experiment; complete independent output checks."""
from pathlib import Path
import argparse,collections,hashlib,http.server,importlib.util,json,math,platform,random,re,sqlite3,statistics,sys,threading,time,urllib.request
HERE=Path(__file__).resolve().parents[1]
canon=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
norm=lambda rows:sorted(rows,key=canon)
digest=lambda x:hashlib.sha256(canon(x).encode()).hexdigest()
DOC_RULES={'direct_SAI','via_authorization_SL'}

def query(url,statement,parameters=None):
 req=urllib.request.Request(url+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':statement,'parameters':parameters or {}}]}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=240) as f:x=json.load(f)
 assert not x['errors'],x['errors'];r=x['results'][0]
 if statement.startswith('EXPLAIN '):return r['plan']
 return [dict(zip(r['columns'],z['row'])) for z in r['data']]

def workloads(root):
 spec=importlib.util.spec_from_file_location('fixed_workloads',root/'Graph_Validation_V27/code/workloads.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 ws={k:dict(v) for k,v in m.WORKLOADS.items()}
 ws['L6_route_evidence']={'question':'Which exact package fields support route judgments?',
 'SQL':"""SELECT w.id witness,p.id product,c.id code,t.id tariff_record,r.id SL_record,json_extract(r.payload,'$.bezeichnung') package,json_extract(r.payload,'$.gammenbezeichnung') recorded_group,json_extract(tr.payload,'$.va') tariff_routes FROM witness w JOIN product p ON p.id=w.product JOIN concept c ON c.id=w.code JOIN tariff t ON t.code=c.id JOIN premise link ON link.witness=w.id JOIN record r ON r.id=link.record AND r.file='sl.csv' JOIN record tr ON tr.id=t.id WHERE w.jurisdiction='CH' AND w.rule='via_authorization_SL'""",
 'Cypher':"""MATCH (w:Association)-[:ABOUT_PRODUCT]->(p:ProductRef),(w)-[:TARGET_ATC]->(c:ATCConcept),(t:SourceRecord {file:'ze_definitions.csv'}),(w)-[:SUPPORTED_BY]->(r:SourceRecord {file:'sl.csv'}) WHERE w.jurisdiction='CH' AND w.rule='via_authorization_SL' AND t.tariff_atc=c.id RETURN w.id AS witness,p.id AS product,c.id AS code,t.id AS tariff_record,r.id AS SL_record,r.package AS package,r.recorded_group AS recorded_group,t.routes AS tariff_routes"""}
 ws['L7_refresh_explanations']={**ws['L2_source_lineage'],'question':'Which refreshed-source premises explain current candidates?'}
 ws['L7_refresh_explanations']['SQL']+=" AND r.file IN ('sai_praeparate.csv','sl.csv')"
 ws['L7_refresh_explanations']['Cypher']=ws['L7_refresh_explanations']['Cypher'].replace(' RETURN '," AND r.file IN ['sai_praeparate.csv','sl.csv'] RETURN ")
 for k,v in ws.items():
  var='b' if k=='L4_cross_source_context' else 'src' if k=='L5_peer_indication_evidence' else 'w'
  code='cb' if var=='b' else 'c'
  sql=v['SQL'].replace(f'JOIN tariff t ON t.code={code}.id',f'JOIN candidate cached ON cached.witness={var}.id JOIN tariff t ON t.id=cached.tariff')
  cy=v['Cypher'].replace("(t:SourceRecord {file:'ze_definitions.csv'})",f"({var})-[:CachedTariff]->(t:SourceRecord {{file:'ze_definitions.csv'}})").replace(f' AND t.tariff_atc={code}.id','')
  if k=='L5_peer_indication_evidence':
   sql=sql.replace('JOIN witness peer ON peer.code=c.id','JOIN candidate cached_peer ON cached_peer.tariff=t.id JOIN witness peer ON peer.id=cached_peer.witness')
   cy=cy.replace('(i:IndicationAssertion)', '(peer)-[:CachedTariff]->(t),(i:IndicationAssertion)')
  assert sql!=v['SQL'] and cy!=v['Cypher'];v['SQL_stored']=sql;v['Cypher_stored']=cy
 return ws

def expected_outputs(ref,ws):
 ts={rid:p for rid,p in ref.records.items() if rid.startswith('ze_definitions.csv:')};ti=collections.defaultdict(list);wi=collections.defaultdict(list);ii=collections.defaultdict(list);direct=collections.defaultdict(list)
 for rid,t in ts.items():ti[t['code']].append(rid)
 docs=[w for w in ref.witnesses.values() if w['jurisdiction']=='CH' and w['rule'] in DOC_RULES]
 for w in docs:
  wi[w['atc']].append(w)
  if w['rule']=='direct_SAI':direct[w['subject']].append(w)
 for i in ref.indications.values():ii[i['subject']].append(i)
 out={k:[] for k in ws};pairs=set();snap=lambda rid:rid.split(':')[1];ridrule=lambda w:w['rule']+':'+w['implementation_sha256']
 for w in docs:
  for tid in ti[w['atc']]:
   pairs.add((w['subject'],tid,w['atc']));b={'witness':w['id'],'product':w['subject'],'code':w['atc'],'tariff_record':tid};out['L1_candidates'].append(b)
   for rid in w['premise_ids']:
    b2={**b,'premise':rid,'source_snapshot':snap(rid)};out['L2_source_lineage'].append(b2);out['L3_rule_dictionary'].append({**b2,'derivation_rule':ridrule(w),'implementation':w['implementation_sha256'],'dictionary_snapshot':w['atc_index_snapshot_sha256'],'tariff_snapshot':snap(tid)})
    if rid.split(':')[0] in {'sai_praeparate.csv','sl.csv'}:out['L7_refresh_explanations'].append(b2)
   if w['rule']=='via_authorization_SL':
    sid=next(x for x in w['premise_ids'] if x.startswith('sai_praeparate.csv:'));lid=next(x for x in w['premise_ids'] if x.startswith('sl.csv:'));package=ref.records[lid]
    out['L6_route_evidence'].append({**b,'SL_record':lid,'package':package['bezeichnung'],'recorded_group':package['gammenbezeichnung'],'tariff_routes':ts[tid]['va']})
    for d in direct[w['subject']]:
     if sid in d['premise_ids']:out['L4_cross_source_context'].append({'direct_witness':d['id'],'package_witness':w['id'],'product':w['subject'],'direct_code':d['atc'],'package_code':w['atc'],'tariff_record':tid,'authorization_record':sid,'package_record':lid,'authorization_snapshot':snap(sid),'package_snapshot':snap(lid),'direct_rule':ridrule(d),'package_rule':ridrule(w),'direct_dictionary':d['atc_index_snapshot_sha256'],'package_dictionary':w['atc_index_snapshot_sha256']})
 for subject,tid,code in pairs:
  peers=[w for w in wi[code] if w['subject']!=subject and ii[w['subject']]]
  if not peers:continue
  indic={i['id']:i for w in peers for i in ii[w['subject']]};out['L5_peer_indication_evidence'].append({'product':subject,'tariff_record':tid,'peer_count':len({w['subject'] for w in peers}),'indication_witnesses':len(indic),'source_records':len({i['record_id'] for i in indic.values()}),'derivation_rules':len({ridrule(w) for w in peers})})
 return {k:norm(v) for k,v in out.items()}

SCHEMA='''CREATE TABLE product(id TEXT PRIMARY KEY);CREATE TABLE concept(id TEXT PRIMARY KEY);CREATE TABLE snapshot(id TEXT PRIMARY KEY,file TEXT);CREATE TABLE rule(id TEXT PRIMARY KEY,implementation TEXT);CREATE TABLE record(id TEXT PRIMARY KEY,file TEXT,snapshot TEXT,payload TEXT);CREATE TABLE witness(id TEXT PRIMARY KEY,product TEXT,code TEXT,rule TEXT,jurisdiction TEXT,rule_id TEXT,dictionary_snapshot TEXT);CREATE TABLE premise(witness TEXT,record TEXT,PRIMARY KEY(witness,record));CREATE TABLE tariff(id TEXT PRIMARY KEY,code TEXT);CREATE TABLE indication(id TEXT PRIMARY KEY,product TEXT,record TEXT);CREATE TABLE candidate(witness TEXT,tariff TEXT,PRIMARY KEY(witness,tariff));CREATE INDEX candidate_tariff ON candidate(tariff,witness);CREATE INDEX wc ON witness(code);CREATE INDEX wp ON witness(product,rule);CREATE INDEX wj ON witness(jurisdiction,rule);CREATE INDEX pc ON premise(record,witness);CREATE INDEX tc ON tariff(code);CREATE INDEX rf ON record(file);CREATE INDEX ip ON indication(product);'''
TABLES=['candidate','indication','tariff','premise','witness','record','rule','snapshot','concept','product']
def load_sql(db,ref):
 for name in TABLES:db.execute('DELETE FROM '+name)
 ws=list(ref.witnesses.values());ins=list(ref.indications.values());ridrule=lambda w:w['rule']+':'+w['implementation_sha256']
 db.executemany('INSERT INTO product VALUES(?)',[(x,) for x in sorted({w['subject'] for w in ws}|{i['subject'] for i in ins})]);db.executemany('INSERT INTO concept VALUES(?)',[(x,) for x in sorted({w['atc'] for w in ws})]);db.executemany('INSERT INTO snapshot VALUES(?,?)',[(sha,f) for f,sha in ref.files.items()]);db.executemany('INSERT INTO rule VALUES(?,?)',list({ridrule(w):w['implementation_sha256'] for w in ws}.items()));db.executemany('INSERT INTO record VALUES(?,?,?,?)',[(rid,rid.split(':')[0],rid.split(':')[1],json.dumps(p,ensure_ascii=False)) for rid,p in ref.records.items()]);db.executemany('INSERT INTO witness VALUES(?,?,?,?,?,?,?)',[(w['id'],w['subject'],w['atc'],w['rule'],w['jurisdiction'],ridrule(w),w['atc_index_snapshot_sha256']) for w in ws]);db.executemany('INSERT INTO premise VALUES(?,?)',[(w['id'],rid) for w in ws for rid in w['premise_ids']]);db.executemany('INSERT INTO tariff VALUES(?,?)',[(rid,p['code']) for rid,p in ref.records.items() if rid.startswith('ze_definitions.csv:')]);db.executemany('INSERT INTO indication VALUES(?,?,?)',[(i['id'],i['subject'],i['record_id']) for i in ins]);db.commit()

def load_neo(url,ref):
 query(url,'MATCH (n) DETACH DELETE n')
 def batch(rows,statement):
  for n in range(0,len(rows),500):query(url,statement,{'rows':rows[n:n+500]})
 ws=list(ref.witnesses.values());ins=list(ref.indications.values());products=sorted({w['subject'] for w in ws}|{i['subject'] for i in ins})
 batch([{'id':sha,'file':f} for f,sha in ref.files.items()],'UNWIND $rows AS x MERGE (n:SourceSnapshot {id:x.id}) SET n.file=x.file')
 rows=[]
 for rid,p in ref.records.items():
  row={'id':rid,'file':rid.split(':')[0],'snapshot':rid.split(':')[1],'payload_json':json.dumps(p,ensure_ascii=False)}
  if rid.startswith('ze_definitions.csv:'):row.update(tariff_atc=p['code'],routes=p['va'])
  if rid.startswith('sl.csv:'):row.update(package=p['bezeichnung'],recorded_group=p['gammenbezeichnung'])
  rows.append(row)
 batch(rows,'UNWIND $rows AS x MERGE (n:SourceRecord {id:x.id}) SET n+=x WITH n,x MATCH (s:SourceSnapshot {id:x.snapshot}) MERGE (n)-[:IN_SNAPSHOT]->(s)')
 batch([{'id':x} for x in products],'UNWIND $rows AS x MERGE (n:ProductRef {id:x.id})')
 batch([{'id':x} for x in sorted({w['atc'] for w in ws})],'UNWIND $rows AS x MERGE (n:ATCConcept {id:x.id})')
 batch([{'id':k,'implementation_sha256':v} for k,v in {w['rule']+':'+w['implementation_sha256']:w['implementation_sha256'] for w in ws}.items()],'UNWIND $rows AS x MERGE (n:Rule {id:x.id}) SET n+=x')
 batch(ws,'''UNWIND $rows AS x MERGE (n:Association {id:x.id}) SET n+=x WITH n,x MATCH (p:ProductRef {id:x.subject}),(c:ATCConcept {id:x.atc}),(g:Rule {id:x.rule+':'+x.implementation_sha256}),(s:SourceSnapshot {id:x.atc_index_snapshot_sha256}) MERGE (n)-[:ABOUT_PRODUCT]->(p) MERGE (n)-[:TARGET_ATC]->(c) MERGE (n)-[:GENERATED_BY]->(g) MERGE (n)-[:CHECKED_AGAINST]->(s) WITH n,x UNWIND x.premise_ids AS premise MATCH (r:SourceRecord {id:premise}) MERGE (n)-[:SUPPORTED_BY]->(r)''')
 batch(ins,'''UNWIND $rows AS x MERGE (n:IndicationAssertion {id:x.id}) SET n+=x WITH n,x MATCH (p:ProductRef {id:x.subject}),(r:SourceRecord {id:x.record_id}) MERGE (n)-[:ABOUT_PRODUCT]->(p) MERGE (n)-[:SUPPORTED_BY]->(r)''')

SQL_MATERIALIZE="INSERT INTO candidate SELECT w.id,t.id FROM witness w JOIN tariff t ON w.code=t.code WHERE w.jurisdiction='CH' AND w.rule IN ('direct_SAI','via_authorization_SL')"
NEO_MATERIALIZE="MATCH (w:Association)-[:TARGET_ATC]->(c:ATCConcept),(t:SourceRecord {file:'ze_definitions.csv'}) WHERE w.jurisdiction='CH' AND w.rule IN ['direct_SAI','via_authorization_SL'] AND t.tariff_atc=c.id MERGE (w)-[:CachedTariff]->(t) RETURN count(*) AS count"

def route_judgments(rows,candidates,assess):
 groups=collections.defaultdict(list)
 for x in rows:
  for policy in ['coarse','exact_code','explicit_formulation']:groups[(x['product'],x['tariff_record'],policy)].append(assess(x['recorded_group'],x['package'],x['tariff_routes'],policy))
 out=[]
 for product,tariff in sorted({(x['product'],x['tariff_record']) for x in candidates}):
  for p in ['coarse','exact_code','explicit_formulation']:
   vals=groups[(product,tariff,p)];status='VERIFIED' if 'VERIFIED' in vals else 'CONTRADICTED' if vals and all(v=='CONTRADICTED' for v in vals) else 'UNDETERMINED';out.append({'product':product,'tariff_record':tariff,'policy':p,'status':status})
 return norm(out)

def summary(measurements,keys):
 out=[]
 groups=collections.defaultdict(list)
 for row in measurements:groups[tuple(row[k] for k in keys)].append(row['milliseconds'])
 for key,values in groups.items():
  q=statistics.quantiles(values,n=4);out.append({**dict(zip(keys,key)),'median_ms':statistics.median(values),'q1_ms':q[0],'q3_ms':q[2],'min_ms':min(values),'max_ms':max(values),'n':len(values)})
 return out

def main(root,initial,updated,url,output):
 assert url=='http://127.0.0.1:18474','Only the dedicated refresh experiment endpoint is permitted.'
 sys.path.insert(0,str(root/'Validation_Study/code'));from reference_oracle import Reference
 sys.path.insert(0,str(root/'Graph_Validation_V17/code'));from route_policies import assess
 refs={'June':Reference(initial),'October':Reference(updated)};ws=workloads(root);expected={state:expected_outputs(ref,ws) for state,ref in refs.items()}
 output.mkdir(parents=True,exist_ok=True)
 result={'protocol_sha256':hashlib.sha256((root/'next_experiment.json').read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'workloads':ws,'environment':{'platform':platform.platform(),'python':sys.version,'SQLite':sqlite3.sqlite_version},'sources':{state:ref.files for state,ref in refs.items()},'timings':[],'maintenance':[],'correctness':[],'refresh_strategy':'Complete replacement of the source-derived layer; stored derivations invalidated and regenerated. No incremental-update claim.','cost_scope':'HTTP batched graph load versus local SQLite load are measured deployment costs, not transport-controlled insertion speed.'}
 result['Neo4j_version']=query(url,'CALL dbms.components() YIELD name,versions,edition RETURN name,versions,edition')
 for label in ['SourceRecord','ProductRef','Association','IndicationAssertion','SourceSnapshot','Rule','ATCConcept']:query(url,f'CREATE CONSTRAINT Refresh_{label} IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE')
 for name,statement in [('Refresh_scope','CREATE RANGE INDEX Refresh_scope IF NOT EXISTS FOR (n:Association) ON (n.jurisdiction,n.rule)'),('Refresh_subject','CREATE RANGE INDEX Refresh_subject IF NOT EXISTS FOR (n:Association) ON (n.subject,n.rule)'),('Refresh_tariff','CREATE RANGE INDEX Refresh_tariff IF NOT EXISTS FOR (n:SourceRecord) ON (n.file,n.tariff_atc)')]:query(url,statement)
 query(url,'CALL db.awaitIndexes(120)')
 disk=output/'comparison.sqlite';db=sqlite3.connect(str(disk),check_same_thread=False);db.row_factory=sqlite3.Row
 for name in TABLES:db.execute('DROP TABLE IF EXISTS '+name)
 db.executescript(SCHEMA);db.commit()
 class Handler(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));rows=[dict(x) for x in db.execute(body['statements'][0]['statement'])];cols=list(rows[0]) if rows else [];b=json.dumps({'errors':[],'results':[{'columns':cols,'data':[{'row':[x[c] for c in cols]} for x in rows]}]}).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 server=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();sqlurl='http://127.0.0.1:'+str(server.server_port)
 def clock(engine,phase,cycle,fn):
  start=time.perf_counter_ns();ret=fn();ms=(time.perf_counter_ns()-start)/1e6;result['maintenance'].append({'engine':engine,'phase':phase,'cycle':cycle,'milliseconds':ms});return ret
 def execute(state,k,engine,stored):
  start=time.perf_counter_ns();rows=query(sqlurl if engine=='SQLite' else url,ws[k][('SQL' if engine=='SQLite' else 'Cypher')+('_stored' if stored else '')]);ms=(time.perf_counter_ns()-start)/1e6;rows=norm(rows)
  assert rows==expected[state][k],(state,k,engine,stored,len(rows),len(expected[state][k]),rows[:1],expected[state][k][:1]);return {'state':state,'workload':k,'engine':engine,'stored':stored,'milliseconds':ms,'rows':len(rows),'sha256':digest(rows)}
 try:
  for cycle in range(7):
   print('cycle',cycle+1,'of 7',flush=True)
   query(url,'MATCH (n) DETACH DELETE n')
   for name in TABLES:db.execute('DELETE FROM '+name)
   db.commit()
   for state in ['June','October']:
    phase='initial_base' if state=='June' else 'refresh_base'
    if state=='October':
     clock('Neo4j','invalidate',cycle,lambda:query(url,'MATCH ()-[r:CachedTariff]->() DELETE r'))
     clock('SQLite','invalidate',cycle,lambda:(db.execute('DELETE FROM candidate'),db.commit()))
    clock('Neo4j',phase,cycle,lambda:load_neo(url,refs[state]));clock('SQLite',phase,cycle,lambda:load_sql(db,refs[state]))
    before=disk.stat().st_size
    cached=clock('Neo4j','initial_stored' if state=='June' else 'refresh_stored',cycle,lambda:query(url,NEO_MATERIALIZE));clock('SQLite','initial_stored' if state=='June' else 'refresh_stored',cycle,lambda:(db.execute(SQL_MATERIALIZE),db.commit()))
    assert cached[0]['count']==len(expected[state]['L1_candidates']);assert db.execute('SELECT count(*) FROM candidate').fetchone()[0]==len(expected[state]['L1_candidates'])
    db.execute('ANALYZE');db.commit();db.close();db=sqlite3.connect(str(disk),check_same_thread=False);db.row_factory=sqlite3.Row
    for engine in ['Neo4j','SQLite']:
     for stored in [False,True]:
      outputs={k:execute(state,k,engine,stored) for k in ws};actual_routes=query(sqlurl if engine=='SQLite' else url,ws['L6_route_evidence'][('SQL' if engine=='SQLite' else 'Cypher')+('_stored' if stored else '')]);actual_candidates=query(sqlurl if engine=='SQLite' else url,ws['L1_candidates'][('SQL' if engine=='SQLite' else 'Cypher')+('_stored' if stored else '')]);judged=route_judgments(actual_routes,actual_candidates,assess);oracle=route_judgments(expected[state]['L6_route_evidence'],expected[state]['L1_candidates'],assess);assert judged==oracle
      result['correctness'].append({'cycle':cycle,'state':state,'engine':engine,'stored':stored,'workloads':{k:{'rows':x['rows'],'sha256':x['sha256']} for k,x in outputs.items()},'judgments':len(judged),'judgment_sha256':digest(judged),'stale_or_mismatched_outputs':0})
    result.setdefault('storage',[]).append({'cycle':cycle,'state':state,'SQLite_before_materialization_bytes':before,'SQLite_after_materialization_bytes':disk.stat().st_size,'stored_derivations':cached[0]['count'],'Neo4j_storage_unit':'additional CachedTariff relationships; allocated bytes are not isolated'})
    if cycle==6:
     for k in ws:
      for engine in ['Neo4j','SQLite']:
       for stored in [False,True]:
        for _ in range(3):execute(state,k,engine,stored)
     rng=random.Random(73291)
     for repeat in range(15):
      order=[(k,e,s) for k in ws for e in ['Neo4j','SQLite'] for s in [False,True]];rng.shuffle(order)
      for k,e,s in order:result['timings'].append({'repeat':repeat,**execute(state,k,e,s)})
    (output/'checkpoint.json').write_text(json.dumps(result,indent=2)+'\n')
  result['retrieval_summary']=summary(result['timings'],['state','workload','engine','stored']);result['maintenance_summary']=summary(result['maintenance'],['engine','phase'])
  judgments={s:route_judgments(expected[s]['L6_route_evidence'],expected[s]['L1_candidates'],assess) for s in refs};keys={s:{(x['product'],x['tariff_record']) for x in expected[s]['L1_candidates']} for s in refs};oldj={(x['product'],x['tariff_record'],x['policy']):x['status'] for x in judgments['June']};newj={(x['product'],x['tariff_record'],x['policy']):x['status'] for x in judgments['October']}
  changes=[{'product':k[0],'tariff_record':k[1],'policy':k[2],'before':oldj[k],'after':newj[k]} for k in sorted(oldj.keys()&newj.keys()) if oldj[k]!=newj[k]]
  for state in refs:(output/(state+'_judgments.json')).write_text(json.dumps(judgments[state],indent=2)+'\n')
  result['population']={s:{'candidates':len(keys[s]),'authorizations':len({p for p,t in keys[s]}),'derivations':len(expected[s]['L1_candidates']),'route_paths':len(expected[s]['L6_route_evidence']),'judgments':len(judgments[s]),'status_counts':{p:dict(collections.Counter(x['status'] for x in judgments[s] if x['policy']==p)) for p in ['coarse','exact_code','explicit_formulation']}} for s in refs}
  result['source_refresh_changes']={'added':len(keys['October']-keys['June']),'removed':len(keys['June']-keys['October']),'shared':len(keys['June']&keys['October']),'added_keys':sorted(keys['October']-keys['June']),'removed_keys':sorted(keys['June']-keys['October']),'changed_shared_judgments':changes,'shared_judgment_transitions':dict(collections.Counter(x['policy']+': '+x['before']+' -> '+x['after'] for x in changes))}
  # Actual supporting field changes, distinguished from source-file hash changes.
  def slmap(ref):return {p.get('swissmedic_nr',rid):p for rid,p in ref.records.items() if rid.startswith('sl.csv:')}
  oldsl,newsl=slmap(refs['June']),slmap(refs['October']);shared=set(oldsl)&set(newsl)
  result['source_record_changes']={'SL_shared_package_keys':len(shared),'SL_added_package_keys':len(newsl.keys()-oldsl.keys()),'SL_removed_package_keys':len(oldsl.keys()-newsl.keys()),'SL_changed_ATC':sum(oldsl[k]['atc']!=newsl[k]['atc'] for k in shared),'SL_changed_route_group':sum(oldsl[k]['gammenbezeichnung']!=newsl[k]['gammenbezeichnung'] for k in shared),'SL_changed_package_description':sum(oldsl[k]['bezeichnung']!=newsl[k]['bezeichnung'] for k in shared)}
  phases={(x['engine'],x['phase']):x['median_ms'] for x in result['maintenance_summary']};costs=[]
  for state in refs:
   for k in ws:
    for engine in ['Neo4j','SQLite']:
     vals={x['stored']:x['median_ms'] for x in result['retrieval_summary'] if x['state']==state and x['workload']==k and x['engine']==engine};overhead=phases[(engine,'initial_stored')]+phases[(engine,'invalidate')]+phases[(engine,'refresh_stored')];saving=vals[False]-vals[True]
     costs.append({'state':state,'workload':k,'engine':engine,'stored_extra_initial_and_refresh_ms':overhead,'per_request_saving_ms':saving,'break_even_requests':math.ceil(overhead/saving) if saving>0 else None,'request_budgets':{str(n):{'query_time_ms':phases[(engine,'initial_base')]+phases[(engine,'refresh_base')]+n*vals[False],'stored_ms':phases[(engine,'initial_base')]+phases[(engine,'refresh_base')]+overhead+n*vals[True]} for n in [1,10,100,1000]}})
  result['lifecycle_costs']=costs;result['all_complete_outputs_equal']=True;result['stale_outputs']=0
  result['query_plans']={'Neo4j':{k:{str(s):query(url,'EXPLAIN '+v['Cypher_stored' if s else 'Cypher']) for s in [False,True]} for k,v in ws.items()},'SQLite':{k:{str(s):[dict(x) for x in db.execute('EXPLAIN QUERY PLAN '+v['SQL_stored' if s else 'SQL'])] for s in [False,True]} for k,v in ws.items()}}
  (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'population':result['population'],'changes':result['source_refresh_changes'],'all_complete_outputs_equal':True},indent=2),flush=True)
 finally:server.shutdown();server.server_close();db.close()
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--initial',type=Path,required=True);a.add_argument('--updated',type=Path,required=True);a.add_argument('--neo4j-url',default='http://127.0.0.1:18474');a.add_argument('--output',type=Path,required=True);x=a.parse_args();main(x.root.resolve(),x.initial.resolve(),x.updated.resolve(),x.neo4j_url,x.output.resolve())
