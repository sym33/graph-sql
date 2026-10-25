"""Replay the second medication question and verify native results without a server."""
from pathlib import Path
import collections,csv,hashlib,json,sqlite3,sys
from model import build,canon,digest,reference,select,inputs,SCHEMA,sql,anchored_sql
R=Path(__file__).resolve().parent;root=R.parent;protocol=json.loads((R/'protocol.json').read_text())
def populate(db,model,anchors,copies=1):
 db.executescript(SCHEMA)
 for ns in range(copies):
  db.executemany('INSERT INTO witness VALUES(?,?,?,?,?,?)',[(ns,w['id'],w['product'],w['code'],w['kind'],w['premises']) for w in model['witnesses']])
  db.executemany('INSERT INTO parent VALUES(?,?,?)',[(ns,c,p) for c,p in model['parents'].items()])
  db.executemany('INSERT INTO seed VALUES(?,?)',[(ns,a) for a in anchors])
 db.commit();db.execute('ANALYZE');db.commit()
def normalize(rows):return sorted(rows,key=canon)
def expanded(rows,copies):return normalize([dict(ns=ns,**x) for ns in range(copies) for x in rows])
def summarize(rows):
 return {'rows':len(rows),'peer_pairs':len({(x['anchor'],x['peer']) for x in rows}),'sha256':digest(rows)}
def check_source_projection(model,snapshot):
 # Independently expressed relational source projection, not a query over generated witnesses.
 paths=inputs(root,snapshot);db=sqlite3.connect(':memory:')
 db.executescript('CREATE TABLE s(rid TEXT,auth TEXT,code TEXT);CREATE TABLE l(rid TEXT,auth TEXT,code TEXT);CREATE TABLE d(code TEXT PRIMARY KEY);CREATE INDEX sa ON s(auth);')
 for name,delimiter,table,fields in [('sai_praeparate.csv',',','s',('ZULASSUNGSNUMMER','ATC_CODE')),('sl.csv','|','l',('zulassungsnummer','atc'))]:
  path=paths[name];sha=hashlib.sha256(path.read_bytes()).hexdigest()
  with path.open(encoding='utf-8-sig',newline='') as f:
   db.executemany('INSERT INTO '+table+' VALUES(?,?,?)',[(f'{name}:{sha}:record:{i}',row[fields[0]],row[fields[1]]) for i,row in enumerate(csv.DictReader(f,delimiter=delimiter,escapechar='\\'),1)])
 with paths['atc_list.csv'].open(encoding='utf-8-sig',newline='') as f:db.executemany('INSERT OR IGNORE INTO d VALUES(?)',[(r['atc_code'],) for r in csv.DictReader(f,delimiter='|',escapechar='\\')])
 groups=collections.defaultdict(set)
 q="""SELECT s.auth,s.code,'direct',s.rid FROM s JOIN d ON d.code=s.code WHERE length(s.code)=7
 UNION ALL SELECT s.auth,l.code,'package',s.rid FROM s JOIN l ON s.auth=l.auth JOIN d ON d.code=l.code WHERE length(l.code)=7
 UNION ALL SELECT s.auth,l.code,'package',l.rid FROM s JOIN l ON s.auth=l.auth JOIN d ON d.code=l.code WHERE length(l.code)=7"""
 for a,c,k,rid in db.execute(q):groups[a,c,k].add(rid)
 expected={(a,c,k):sorted(rows) for (a,c,k),rows in groups.items()}
 actual={(w['product'],w['code'],w['kind']):json.loads(w['premises']) for w in model['witnesses']}
 assert actual==expected
 q="""SELECT c.code,p.code FROM d c JOIN d p ON p.code=substr(c.code,1,CASE length(c.code) WHEN 7 THEN 5 WHEN 5 THEN 4 WHEN 4 THEN 3 WHEN 3 THEN 1 ELSE 0 END) WHERE length(c.code) IN (3,4,5,7)"""
 assert model['parents']==dict(db.execute(q));db.close()

def run():
 answers={};out={'protocol_sha256':digest(protocol),'snapshots':{},'controls':{},'native_receipts':{}}
 for observed in (R/'observed').glob('native_*.json'):
  receipt=json.loads(observed.read_text());engines={'Neo4j','SQLite','PostgreSQL'}
  if observed.name=='native_control.json':engines.update({'SQLite_anchored','PostgreSQL_anchored'})
  cells=collections.Counter((x['copies'],x['depth'],x['engine']) for x in receipt['measurements'])
  assert set(cells)=={(c,d,e) for c in protocol['timing']['copies'] for d in protocol['depths'] for e in engines}
  assert set(cells.values())=={protocol['timing']['repetitions']}
  assert len(receipt['summaries'])==len(cells)
  assert len(receipt['checks'])==len(engines)*len(protocol['timing']['copies']) and all(x['direct_only_agreement'] for x in receipt['checks'])
  out['native_receipts'][observed.name]={'timed_outputs':len(receipt['measurements']),'cells':len(cells),'ablation_checks':len(receipt['checks'])}

 for snapshot in protocol['snapshots']:
  model=build(root,snapshot);check_source_projection(model,snapshot);out['controls'][snapshot+'_independent_source_projection']=True
  if snapshot=='D0':assert select(model)==protocol['anchors']
  db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;populate(db,model,protocol['anchors']);data={}
  for depth in protocol['depths']:
   ref=reference(model,protocol['anchors'],depth);expected=expanded(ref,1);actual=normalize([dict(x) for x in db.execute(sql(depth))]);assert actual==expected
   assert normalize([dict(x) for x in db.execute(anchored_sql(depth))])==expected
   direct=reference(model,protocol['anchors'],depth,True);direct_actual=normalize([dict(x) for x in db.execute(sql(depth,True))]);assert direct_actual==expanded(direct,1)
   pairs={(x['anchor'],x['peer']) for x in ref};dpairs={(x['anchor'],x['peer']) for x in direct}
   data[str(depth)]={'full':summarize(ref),'direct':summarize(direct),'additional_peer_pairs':len(pairs-dpairs),'per_anchor':{a:{'name':model['names'][a],'full_peers':len({x['peer'] for x in ref if x['anchor']==a}),'direct_peers':len({x['peer'] for x in direct if x['anchor']==a})} for a in protocol['anchors']}}
   assert dpairs <= pairs
   codes=collections.defaultdict(lambda:collections.defaultdict(set))
   for w in model['witnesses']:codes[w['product']][w['kind']].add(w['code'])
   data[str(depth)]['new_peer_pairs']=[{'anchor':a,'peer':b,'peer_name':model['names'][b],'common_ancestors':sorted({x['ancestor'] for x in ref if x['anchor']==a and x['peer']==b}),'direct_peer_codes':sorted(codes[b]['direct']),'package_peer_codes':sorted(codes[b]['package'])} for a,b in sorted(pairs-dpairs)]
   answers[snapshot,depth]=pairs
   if snapshot=='D1':
    expected_hashes={c:digest(expanded(ref,c)) for c in protocol['timing']['copies']}
    for observed in (R/'observed').glob('native_*.json'):
     native=json.loads(observed.read_text());assert native['complete'] and native['protocol_sha256']==digest(protocol)
     if observed.name=='native_control.json':assert native['control_protocol_sha256']==digest(json.loads((R/'plan_control_protocol.json').read_text()))
     for run in native['summaries']:
      if run['depth']==depth:assert run['rows']==len(ref)*run['copies'] and run['answer_sha256']==expected_hashes[run['copies']]
     for measurement in native['measurements']:
      if measurement['depth']==depth:assert measurement['rows']==len(ref)*measurement['copies'] and measurement['answer_sha256']==expected_hashes[measurement['copies']]
  # Missing-anchor negative control.
  db.execute('DELETE FROM seed');db.execute("INSERT INTO seed VALUES(0,'ABSENT')");assert not list(db.execute(sql(4)));out['controls'][snapshot+'_absent_anchor']=True
  # Remove one hierarchy edge; expected paths are filtered by whether they cross that edge.
  db.execute('DELETE FROM seed');db.executemany('INSERT INTO seed VALUES(?,?)',[(0,a) for a in protocol['anchors']]);child=next(w['code'] for w in model['witnesses'] if w['product']==protocol['anchors'][0]);parent=model['parents'][child];db.execute('DELETE FROM parent WHERE child=?',(child,))
  expected=[]
  for x in reference(model,protocol['anchors'],4):
   def crosses(code,depth):
    from model import ancestors
    chain=[c for c,_ in ancestors(model,code,depth)]
    return any(a==child and b==parent for a,b in zip(chain,chain[1:]))
   if not crosses(x['anchor_code'],x['anchor_depth']) and not crosses(x['peer_code'],x['peer_depth']):expected.append(x)
  actual=normalize([dict(x) for x in db.execute(sql(4))]);assert actual==expanded(expected,1);assert len(expected)<data['4']['full']['rows'];out['controls'][snapshot+'_missing_parent']=True
  out['snapshots'][snapshot]={'inputs':model['inputs'],'witnesses':len(model['witnesses']),'codes':len(model['codes']),'parent_edges':len(model['parents']),'excluded':model['excluded'],'tasks':data}
 out['updates']={str(d):{'added_peer_pairs':len(answers['D1',d]-answers['D0',d]),'removed_peer_pairs':len(answers['D0',d]-answers['D1',d])} for d in protocol['depths']}
 model=build(root,'D1');db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;populate(db,model,protocol['anchors'],2);rows=normalize([dict(x) for x in db.execute(sql(2))]);assert rows==expanded(reference(model,protocol['anchors'],2),2);out['controls']['two_copy_answer_equality']=True
 (R/'observed').mkdir(exist_ok=True);(R/'observed/transfer.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__':run()
