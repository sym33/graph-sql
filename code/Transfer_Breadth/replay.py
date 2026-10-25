"""Reconstruct both full-population censuses and verify every native answer hash."""
from pathlib import Path
import collections,hashlib,json,sqlite3,sys
from study import PROTOCOL,build,chembl,source_check,census,subset,canon,digest,reference
R=Path(__file__).resolve().parent;ROOT=R.parent
sys.path.insert(0,str(ROOT/'Transfer_Peers'))
from model import SCHEMA,sql,anchored_sql,cypher

def run():
 observed=json.loads((R/'observed/native.json').read_text());expected_census=json.loads((R/'observed/census.json').read_text())
 assert observed['complete'] and observed['protocol_sha256']==digest(PROTOCOL)==expected_census['protocol_sha256']
 cells=collections.Counter((x['key'],x['engine'],x['depth']) for x in observed['measurements'])
 models={'Swiss_D1':build(ROOT,'D1'),'ChEMBL_37':chembl(ROOT)}
 payload=(canon({'protocol_sha256':digest(PROTOCOL),'cases':[subset(m,c,f) for c,m in models.items() for f in PROTOCOL['fractions']]})+'\n').encode()
 assert hashlib.sha256(payload).hexdigest()==observed['input_models_sha256']
 for engine in PROTOCOL['arms']:
  for d in PROTOCOL['depths']:
   q=cypher(d) if engine=='Neo4j' else (anchored_sql(d) if engine.endswith('_anchored') else sql(d))
   assert observed['queries'][engine][str(d)]==q
 keys={f'{c}:{f}' for c in models for f in PROTOCOL['fractions']}
 assert set(cells)=={(k,e,d) for k in keys for e in PROTOCOL['arms'] for d in PROTOCOL['depths']};assert set(cells.values())=={PROTOCOL['timing']['repetitions']}
 assert len(observed['summaries'])==len(cells)
 assert len(observed['checks'])==len(keys) and all(x['absent_anchor_all_variants'] for x in observed['checks'])
 actual={'protocol_sha256':digest(PROTOCOL),'corpora':{}};subset_checks=0;membership=0
 for corpus,m in models.items():
  print('Reconstructing full census',corpus,flush=True);actual['corpora'][corpus]=census(m,source_check(m,ROOT,corpus),corpus);assert actual['corpora'][corpus]==expected_census['corpora'][corpus]
  membership+=sum(v['directed_peer_pairs'] for v in actual['corpora'][corpus]['tasks'].values())
  previous=set()
  for f in PROTOCOL['fractions']:
   case=subset(m,corpus,f);key=f'{corpus}:{f}';ids={w['product'] for w in case['model']['witnesses']};assert previous<=ids;previous=ids
   recorded=next(x for x in observed['cases'] if x['key']==key);assert recorded['anchors']==case['anchors'] and recorded['structure']==case['structure'] and recorded['source_hashes']==m['inputs']
   db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;db.executescript(SCHEMA)
   db.executemany('INSERT INTO witness VALUES(?,?,?,?,?,?)',[(0,w['id'],w['product'],w['code'],w['kind'],w['premises']) for w in case['model']['witnesses']]);db.executemany('INSERT INTO parent VALUES(?,?,?)',[(0,c,p) for c,p in case['model']['parents'].items()]);db.executemany('INSERT INTO seed VALUES(?,?)',[(0,x) for x in case['anchors']]);db.execute('ANALYZE')
   for d in PROTOCOL['depths']:
    rows=sorted([dict(ns=0,**x) for x in reference(case['model'],case['anchors'],d)],key=canon);h=digest(rows)
    for query in (sql(d),anchored_sql(d)):assert sorted([dict(x) for x in db.execute(query)],key=canon)==rows;subset_checks+=1
    for result in observed['measurements']+observed['summaries']:
     if result['key']==key and result['depth']==d:assert result['rows']==len(rows) and result['answer_sha256']==h
   db.close()
 output=R/'results';output.mkdir(exist_ok=True);(output/'replay.json').write_text(json.dumps({'census_anchors':sum(x['eligible_entities'] for x in actual['corpora'].values()),'directed_memberships_checked':membership,'native_timed_outputs_verified':len(observed['measurements']),'SQL_complete_explanation_checks':subset_checks,'native_missing_anchor_controls':len(observed['checks']),'nested_real_entity_growth':True,'native_timings_repeated':False},indent=2)+'\n')
 print((output/'replay.json').read_text(),flush=True)
if __name__=='__main__':run()
