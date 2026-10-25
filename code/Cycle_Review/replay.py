"""Reconstruct native classification-cycle answers and the SQL plan control."""
from pathlib import Path
import collections,csv,gzip,hashlib,json,sqlite3
R=Path(__file__).resolve().parent
r=json.loads((R/'observed/results.json').read_text());control=json.loads((R/'observed/cycle_plan_control.json').read_text());facts=json.loads(gzip.decompress((R/'observed/facts.json.gz').read_bytes()))
canon=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))
norm=lambda rows:sorted(rows,key=canon)
assert hashlib.sha256(canon(norm(facts['edges'])).encode()).hexdigest()==r['graph_facts_sha256']
expected=set()
for original in sorted((R.parent/'Graph_Validation_V9/temporal_snapshot/input/silver').glob('*.csv')):
 p=R.parent/'Source_Refresh/input/silver'/original.name if original.name in ('sl.csv','sai_praeparate.csv') else original
 sha=hashlib.sha256(p.read_bytes()).hexdigest();delimiter={'sai_praeparate.csv':',','technisches_begleitblatt.csv':',','atc_alterations.csv':';','geloeschte_substanzen.csv':';'}.get(original.name,'|')
 with p.open(encoding='utf-8-sig',newline='') as f:
  for i,_ in enumerate(csv.DictReader(f,delimiter=delimiter,escapechar='\\'),1):expected.add(f'{original.name}:{sha}:record:{i}')
assert len(expected)==38211 and expected=={n['id'] for n in facts['nodes'] if n['label']=='SourceRecord'}
db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
db.executescript('CREATE TABLE node(id TEXT PRIMARY KEY,label TEXT,source_id TEXT); CREATE TABLE edge(s TEXT,r TEXT,t TEXT); CREATE INDEX es ON edge(s,r,t); CREATE INDEX et ON edge(t,r,s); CREATE INDEX ni ON node(label,source_id);')
uid=lambda l,i:l+':'+i
db.executemany('INSERT INTO node VALUES(?,?,?)',[(uid(n['label'],n['id']),n['label'],n['id']) for n in facts['nodes']]);db.executemany('INSERT INTO edge VALUES(?,?,?)',[(uid(e['al'],e['a']),e['rel'],uid(e['bl'],e['b'])) for e in facts['edges']])
sql=r['tasks']['redundant_classification_cycles']['SQL'];ordered=control['ordered_SQL'];found=[]
for c in r['cases']:
 rows=norm([dict(z) for z in db.execute(sql,c['parameters'])]);assert len(rows)==c['rows'] and hashlib.sha256(canon(rows).encode()).hexdigest()==c['answer_sha256']
 assert rows==norm([dict(z) for z in db.execute(ordered,c['parameters'])])
 assert not list(db.execute(sql,{**c['parameters'],'product':'ABSENT_CONTROL'}))
 found.extend((c['parameters']['product'],x) for x in rows)
assert len(found)==1
product,row=found[0];proofs=[]
for key in ['first','second']:
 a=row[key];proofs.append({'association':a,'source_records':sorted(e['b'] for e in facts['edges'] if e['a']==a and e['rel']=='SUPPORTED_BY'),'rules':sorted(e['b'].split(':')[0] for e in facts['edges'] if e['a']==a and e['rel']=='GENERATED_BY')})
assert product=='CH:authorization:41330' and row['code']=='B02BD01'
assert set(proofs[0]['source_records'])&set(proofs[1]['source_records'])
print('3 native cycle answers reproduced; 3 missing-product controls and 3 ordered-SQL answer checks passed. One undirected cycle at authorization 41330 / B02BD01. Its two classification records share a SAI source row; only the SL-derived record additionally uses an SL row. Native timings were not repeated.')
