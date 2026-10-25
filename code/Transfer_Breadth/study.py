"""Cross-source census and real-entity growth; reuses the fixed answer contract."""
from pathlib import Path
import argparse,collections,csv,gzip,hashlib,json,math,sqlite3,sys
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent/'Transfer_Peers'))
from model import build,canon,digest,ancestors,reference,LENGTHS
PROTOCOL=json.loads((R/'protocol.json').read_text())
def chembl_blocks(root):
 folder=Path(root)/'External_Knowledge_Validation/raw'
 names=sorted({p.name.removesuffix('.gz') for p in folder.glob('chembl_molecules_*.json*')})
 assert len(names)==4
 for name in names:
  p=folder/name;raw=p.read_bytes() if p.exists() else gzip.decompress((folder/(name+'.gz')).read_bytes())
  if p.exists() and (folder/(name+'.gz')).exists():assert raw==gzip.decompress((folder/(name+'.gz')).read_bytes())
  yield name,hashlib.sha256(raw).hexdigest(),json.loads(raw)

def chembl(root):
 root=Path(root);dictionary=root/'Graph_Validation_V9/temporal_snapshot/input/silver/atc_list.csv'
 with dictionary.open(encoding='utf-8-sig') as f:codes={x['atc_code'] for x in csv.DictReader(f,delimiter='|')}
 parent={c:c[:LENGTHS[LENGTHS.index(len(c))-1]] for c in codes if len(c) in LENGTHS and len(c)>1 and c[:LENGTHS[LENGTHS.index(len(c))-1]] in codes}
 witnesses=[];names={};files={'atc_list.csv':hashlib.sha256(dictionary.read_bytes()).hexdigest()};excluded=collections.Counter();raw_count=0
 for filename,sha,block in chembl_blocks(root):
  files[filename]=sha
  for i,row in enumerate(block['molecules'],1):
   raw_count+=1;entity=row['molecule_chembl_id'];names[entity]=row.get('pref_name') or entity;admitted={c for c in row.get('atc_classifications',[]) if len(c)==7 and c in codes}
   if not admitted:excluded['molecules_without_admitted_code']+=1
   for c in sorted(admitted):witnesses.append({'id':digest([entity,c,'direct']),'product':entity,'code':c,'kind':'direct','premises':canon([f'{filename}:{sha}:molecule:{i}:{entity}'])})
 return {'snapshot':'ChEMBL_37','witnesses':witnesses,'codes':sorted(codes),'parents':parent,'names':names,'inputs':files,'excluded':dict(excluded),'raw_entities':raw_count}
def source_check(model,root,corpus):
 # Original rows, unexpanded ATC arrays and SQL joins form the independent source projection.
 db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE dictionary(code TEXT PRIMARY KEY);CREATE TABLE raw(id TEXT,payload TEXT);CREATE TABLE s(rid TEXT,auth TEXT,code TEXT);CREATE TABLE l(rid TEXT,auth TEXT,code TEXT);CREATE INDEX sa ON s(auth);')
 dictionary=Path(root)/'Graph_Validation_V9/temporal_snapshot/input/silver/atc_list.csv'
 with dictionary.open(encoding='utf-8-sig') as f:db.executemany('INSERT OR IGNORE INTO dictionary VALUES(?)',[(x['atc_code'],) for x in csv.DictReader(f,delimiter='|')])
 if corpus=='ChEMBL_37':
  for filename,sha,block in chembl_blocks(root):
   db.executemany('INSERT INTO raw VALUES(?,?)',[(f"{filename}:{sha}:molecule:{i}:{x['molecule_chembl_id']}",json.dumps(x)) for i,x in enumerate(block['molecules'],1)])
  q="SELECT json_extract(r.payload,'$.molecule_chembl_id'),a.value,'direct',r.id FROM raw r,json_each(r.payload,'$.atc_classifications') a JOIN dictionary d ON d.code=a.value WHERE length(a.value)=7"
 else:
  for name,table,delim,fields in [('sai_praeparate.csv','s',',',('ZULASSUNGSNUMMER','ATC_CODE')),('sl.csv','l','|',('zulassungsnummer','atc'))]:
   p=Path(root)/'Source_Refresh/input/silver'/name;sha=hashlib.sha256(p.read_bytes()).hexdigest()
   with p.open(encoding='utf-8-sig',newline='') as f:db.executemany('INSERT INTO '+table+' VALUES(?,?,?)',[(f'{name}:{sha}:record:{i}',x[fields[0]],x[fields[1]]) for i,x in enumerate(csv.DictReader(f,delimiter=delim,escapechar='\\'),1)])
  q="""SELECT s.auth,s.code,'direct',s.rid FROM s JOIN dictionary d ON d.code=s.code WHERE length(s.code)=7
  UNION ALL SELECT s.auth,l.code,'package',s.rid FROM s JOIN l ON s.auth=l.auth JOIN dictionary d ON d.code=l.code WHERE length(l.code)=7
  UNION ALL SELECT s.auth,l.code,'package',l.rid FROM s JOIN l ON s.auth=l.auth JOIN dictionary d ON d.code=l.code WHERE length(l.code)=7"""
 groups=collections.defaultdict(set)
 for entity,code,kind,premise in db.execute(q):groups[entity,code,kind].add(premise)
 assert {(w['product'],w['code'],w['kind']):json.loads(w['premises']) for w in model['witnesses']}=={k:sorted(v) for k,v in groups.items()}
 # SQL creates the hierarchy from raw dictionary prefixes, independently of model.parents.
 parents=dict(db.execute("SELECT c.code,p.code FROM dictionary c JOIN dictionary p ON p.code=substr(c.code,1,CASE length(c.code) WHEN 7 THEN 5 WHEN 5 THEN 4 WHEN 4 THEN 3 WHEN 3 THEN 1 ELSE 0 END) WHERE length(c.code) IN (3,4,5,7)"));assert parents==model['parents']
 # Return independently projected source membership codes for the census.
 bindings={(a,c,k) for a,c,k in groups};db.close();return bindings

def choose(model,corpus):
 classes=collections.defaultdict(set)
 for w in model['witnesses']:classes[w['code'][0]].add(w['product'])
 selected=[]
 for group,entities in sorted(classes.items()):selected.append(min(entities-set(selected),key=lambda a:hashlib.sha256(f'breadth-20261025:{corpus}:{group}:{a}'.encode()).hexdigest()))
 return selected

def subset(model,corpus,fraction):
 anchors=choose(model,corpus);entities={w['product'] for w in model['witnesses']};ranked=sorted(entities,key=lambda a:hashlib.sha256(f'growth-20261025:{corpus}:{a}'.encode()).hexdigest());keep=set(ranked[:math.ceil(len(ranked)*fraction)])|set(anchors)
 ws=[w for w in model['witnesses'] if w['product'] in keep];active=set()
 for w in ws:active.update(c for c,_ in ancestors(model,w['code'],4))
 m={**model,'witnesses':ws,'codes':sorted(active),'parents':{c:p for c,p in model['parents'].items() if c in active and p in active}}
 counts=collections.Counter(w['code'] for w in ws);branch=collections.Counter(m['parents'].values());degree=collections.Counter(w['product'] for w in ws)
 stats={'entities':len(keep),'witnesses':len(ws),'hierarchy_nodes':len(active),'hierarchy_edges':len(m['parents']),'occupied_leaf_codes':len(counts),'maximum_witnesses_per_leaf':max(counts.values()),'mean_witnesses_per_occupied_leaf':len(ws)/len(counts),'maximum_children':max(branch.values()),'maximum_codes_or_source_witnesses_per_entity':max(degree.values()),'source_kinds':dict(collections.Counter(w['kind'] for w in ws))}
 return {'corpus':corpus,'fraction':fraction,'anchors':anchors,'model':m,'structure':stats}

def census(model,bindings,corpus):
 db=sqlite3.connect(':memory:');db.execute('CREATE TABLE binding(product TEXT,code TEXT,kind TEXT)');db.executemany('INSERT INTO binding VALUES(?,?,?)',sorted(bindings));db.execute('CREATE TABLE parent(child TEXT PRIMARY KEY,parent TEXT)');db.executemany('INSERT INTO parent VALUES(?,?)',sorted(model['parents'].items()))
 db.executescript('''CREATE TABLE closure AS WITH RECURSIVE c(product,ancestor,d) AS (SELECT DISTINCT product,code,0 FROM binding UNION SELECT c.product,p.parent,c.d+1 FROM c JOIN parent p ON p.child=c.ancestor WHERE c.d<4) SELECT * FROM c;CREATE INDEX cp ON closure(product,d,ancestor);CREATE INDEX ca ON closure(ancestor,d,product);''')
 predicate="kind='direct'" if corpus=='Swiss_D1' else 'code=(SELECT min(b.code) FROM binding b WHERE b.product=binding.product)'
 db.executescript('CREATE TABLE reduced_binding AS SELECT * FROM binding WHERE '+predicate+'; CREATE INDEX rbp ON reduced_binding(product,code); CREATE TABLE reduced_closure AS WITH RECURSIVE c(product,ancestor,d) AS (SELECT DISTINCT product,code,0 FROM reduced_binding UNION SELECT c.product,p.parent,c.d+1 FROM c JOIN parent p ON p.child=c.ancestor WHERE c.d<4) SELECT * FROM c; CREATE INDEX rcp ON reduced_closure(product,d,ancestor); CREATE INDEX rca ON reduced_closure(ancestor,d,product); ANALYZE;')
 entities=sorted({w['product'] for w in model['witnesses']});index={d:collections.defaultdict(set) for d in PROTOCOL['depths']};reduced={d:collections.defaultdict(set) for d in PROTOCOL['depths']};codes=collections.defaultdict(set)
 for w in model['witnesses']:codes[w['product']].add(w['code'])
 reduced_codes=collections.defaultdict(set)
 for w in model['witnesses']:
  if (corpus=='Swiss_D1' and w['kind']=='direct') or (corpus=='ChEMBL_37' and w['code']==min(codes[w['product']])):reduced_codes[w['product']].add(w['code'])
 for entity,cs in codes.items():
  for d in index:
   for c in cs:
    for a,_ in ancestors(model,c,d):index[d][a].add(entity)
   for c in reduced_codes[entity]:
    for a,_ in ancestors(model,c,d):reduced[d][a].add(entity)
 out={}
 for d in PROTOCOL['depths']:
  h=hashlib.sha256();count=0;additional=0;affected=0;reduced_count=0;maxpeers=0;nonempty=0
  for entity in entities:
   peers=set();before=set()
   for c in codes[entity]:
    for a,_ in ancestors(model,c,d):peers.update(index[d][a])
   for c in reduced_codes[entity]:
    for a,_ in ancestors(model,c,d):before.update(reduced[d][a])
   peers.discard(entity);before.discard(entity);assert before<=peers
   observed={x[0] for x in db.execute('SELECT DISTINCT b.product FROM closure a JOIN closure b ON a.ancestor=b.ancestor WHERE a.product=? AND a.d<=? AND b.d<=? AND b.product<>?',(entity,d,d,entity))};assert peers==observed,(corpus,entity,d)
   reduced_observed={x[0] for x in db.execute('SELECT DISTINCT b.product FROM reduced_closure a JOIN reduced_closure b ON a.ancestor=b.ancestor WHERE a.product=? AND a.d<=? AND b.d<=? AND b.product<>?',(entity,d,d,entity))};assert before==reduced_observed,(corpus,entity,d,'ablation')
   n=len(peers);count+=n;reduced_count+=len(before);additional+=len(peers-before);affected+=bool(peers-before);maxpeers=max(maxpeers,n);nonempty+=bool(peers)
   for peer in sorted(peers):h.update((canon([entity,peer])+'\n').encode())
  assert count%2==0 and additional%2==0
  out[str(d)]={'unordered_peer_pairs':count//2,'additional_unordered_pairs':additional//2,'anchors':len(entities),'directed_peer_pairs':count,'nonempty_anchors':nonempty,'maximum_peers':maxpeers,'reduced_pairs':reduced_count,'additional_pairs':additional,'anchors_gaining_peers':affected,'answer_sha256':h.hexdigest()}
 db.close();cross=sum(len({c[0] for c in cs})>1 for cs in codes.values())
 return {'corpus':corpus,'eligible_entities':len(entities),'source_witnesses':len(model['witnesses']),'source_hashes':model['inputs'],'excluded':model['excluded'],'entities_in_multiple_first_level_groups':cross,'entities_with_multiple_admitted_codes':sum(len(cs)>1 for cs in codes.values()),'Swiss_entities_gaining_codes_from_packages':sum(bool(cs-reduced_codes[e]) for e,cs in codes.items()) if corpus=='Swiss_D1' else None,'tasks':out,'reference':'Independent SQL source projection and closure-query equality for every anchor; Python prefix membership oracle.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=R.parent);p.add_argument('--export',type=Path);p.add_argument('--census',type=Path);a=p.parse_args();models={'Swiss_D1':build(a.root,'D1'),'ChEMBL_37':chembl(a.root)}
 if a.export:a.export.write_text(canon({'protocol_sha256':digest(PROTOCOL),'cases':[subset(m,c,f) for c,m in models.items() for f in PROTOCOL['fractions']]})+'\n')
 if a.census:
  out={'protocol_sha256':digest(PROTOCOL),'corpora':{}}
  for c,m in models.items():
   print('Checking census',c,flush=True);out['corpora'][c]=census(m,source_check(m,a.root,c),c);a.census.parent.mkdir(parents=True,exist_ok=True);a.census.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(c,out['corpora'][c]['eligible_entities'],flush=True)
if __name__=='__main__':main()
