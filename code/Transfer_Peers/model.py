"""Source-derived peer discovery; no tariff, route or legacy graph exports required."""
from pathlib import Path
import collections,csv,hashlib,json
LENGTHS=(1,3,4,5,7)
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def read(path,delimiter):
 sha=hashlib.sha256(path.read_bytes()).hexdigest()
 with path.open(encoding='utf-8-sig',newline='') as f:
  return [(f'{path.name}:{sha}:record:{i}',r) for i,r in enumerate(csv.DictReader(f,delimiter=delimiter,escapechar='\\'),1)]
def inputs(root,snapshot):
 root=Path(root);base=root/'Graph_Validation_V9/temporal_snapshot/input/silver'
 return {f:(root/'Source_Refresh/input/silver'/f if snapshot=='D1' and f!='atc_list.csv' else base/f) for f in ('sai_praeparate.csv','sl.csv','atc_list.csv')}
def build(root,snapshot):
 paths=inputs(root,snapshot);sai=read(paths['sai_praeparate.csv'],',');sl=read(paths['sl.csv'],'|');dictionary=read(paths['atc_list.csv'],'|')
 codes={r['atc_code'] for _,r in dictionary};names={r['ZULASSUNGSNUMMER']:r['PRAEPARATENAME'] for _,r in sai};auth=collections.defaultdict(list)
 for rid,r in sai:auth[r['ZULASSUNGSNUMMER']].append(rid)
 parent={c:c[:LENGTHS[LENGTHS.index(len(c))-1]] for c in codes if len(c) in LENGTHS and len(c)>1 and c[:LENGTHS[LENGTHS.index(len(c))-1]] in codes}
 groups=collections.defaultdict(set);excluded=collections.Counter()
 for rid,r in sai:
  c=r['ATC_CODE']
  if c in codes and len(c)==7:groups[(r['ZULASSUNGSNUMMER'],c,'direct')].add(rid)
  else:excluded['direct_nonleaf_or_unlisted']+=1
 for rid,r in sl:
  c=r['atc'];a=r['zulassungsnummer']
  if a in auth and c in codes and len(c)==7:groups[(a,c,'package')].update([rid]+auth[a])
  else:excluded['package_unlinked_nonleaf_or_unlisted']+=1
 witnesses=[{'id':digest([a,c,k]),'product':a,'code':c,'kind':k,'premises':canon(sorted(records))} for (a,c,k),records in sorted(groups.items())]
 return {'snapshot':snapshot,'witnesses':witnesses,'parents':parent,'codes':sorted(codes),'names':names,'excluded':dict(excluded),'inputs':{f:hashlib.sha256(p.read_bytes()).hexdigest() for f,p in paths.items()}}
def select(model):
 byproduct=collections.defaultdict(lambda:collections.defaultdict(set))
 for w in model['witnesses']:byproduct[w['product']][w['kind']].add(w['code'])
 classes=collections.defaultdict(list)
 for a,k in byproduct.items():
  if k['direct'] and k['package']:
   # The source has one direct code per authorization in the selected population.
   assert len(k['direct'])==1
   classes[next(iter(k['direct']))[0]].append(a)
 hashkey=lambda x:hashlib.sha256(('transfer-20261025:'+x).encode()).hexdigest()
 return [min(classes[k],key=hashkey) for k in sorted(classes,key=hashkey)[:3]]
def ancestors(model,code,depth):
 # Expected hierarchy is enumerated by source-code prefixes, independently of SQL recursion/Cypher.
 out=[(code,0)];current=code
 for step in range(1,depth+1):
  pos=LENGTHS.index(len(current))
  if not pos:break
  parent=current[:LENGTHS[pos-1]]
  if parent not in model['codes']:break
  out.append((parent,step));current=parent
 return out
def reference(model,anchors,depth,direct_only=False):
 ws=[w for w in model['witnesses'] if not direct_only or w['kind']=='direct'];index=collections.defaultdict(list)
 for w in ws:
  for c,d in ancestors(model,w['code'],depth):index[c].append((w,d))
 rows=[]
 for a in ws:
  if a['product'] not in anchors:continue
  for common,da in ancestors(model,a['code'],depth):
   for b,db in index[common]:
    if a['product']==b['product']:continue
    rows.append({'anchor':a['product'],'peer':b['product'],'ancestor':common,'anchor_code':a['code'],'peer_code':b['code'],'anchor_depth':da,'peer_depth':db,'anchor_witness':a['id'],'peer_witness':b['id'],'anchor_premises':a['premises'],'peer_premises':b['premises']})
 return sorted(rows,key=canon)
SCHEMA='''CREATE TABLE witness(ns INTEGER,id TEXT,product TEXT,code TEXT,kind TEXT,premises TEXT,PRIMARY KEY(ns,id));CREATE INDEX wp ON witness(ns,product);CREATE INDEX wc ON witness(ns,code);CREATE TABLE parent(ns INTEGER,child TEXT,parent TEXT,PRIMARY KEY(ns,child));CREATE INDEX pp ON parent(ns,parent,child);CREATE TABLE seed(ns INTEGER,product TEXT,PRIMARY KEY(ns,product));'''
def sql(depth,direct=False):
 filter_a=" AND a.kind='direct'" if direct else '';filter_b=" AND b.kind='direct'" if direct else ''
 return f'''WITH RECURSIVE up(ns,leaf,ancestor,d) AS (
 SELECT ns,code,code,0 FROM witness GROUP BY ns,code
 UNION ALL SELECT u.ns,u.leaf,p.parent,u.d+1 FROM up u JOIN parent p ON p.ns=u.ns AND p.child=u.ancestor WHERE u.d<{depth})
 SELECT a.ns,a.product anchor,b.product peer,x.ancestor,a.code anchor_code,b.code peer_code,x.d anchor_depth,y.d peer_depth,a.id anchor_witness,b.id peer_witness,a.premises anchor_premises,b.premises peer_premises
 FROM seed s JOIN witness a ON a.ns=s.ns AND a.product=s.product
 JOIN up x ON x.ns=a.ns AND x.leaf=a.code
 JOIN up y ON y.ns=x.ns AND y.ancestor=x.ancestor
 JOIN witness b ON b.ns=y.ns AND b.code=y.leaf
 WHERE b.product<>a.product{filter_a}{filter_b}'''
# A named path for each side retains exact depth, including depth zero.
def cypher(depth,direct=False):
 filt=" AND a.kind='direct' AND b.kind='direct'" if direct else ''
 return f'''MATCH (s:PeerSeed),(a:PeerWitness {{ns:s.ns,product:s.product}})-[:RECORDED]->(ca:PeerCode)
 MATCH pa=(ca)-[:PARENT*0..{depth}]->(c:PeerCode)
 MATCH pb=(c)<-[:PARENT*0..{depth}]-(cb:PeerCode)<-[:RECORDED]-(b:PeerWitness)
 WHERE a.ns=b.ns AND a.product<>b.product{filt}
 RETURN a.ns AS ns,a.product AS anchor,b.product AS peer,c.code AS ancestor,a.code AS anchor_code,b.code AS peer_code,
 length(pa) AS anchor_depth,length(pb)-1 AS peer_depth,a.id AS anchor_witness,b.id AS peer_witness,a.premises AS anchor_premises,b.premises AS peer_premises'''

def anchored_sql(depth,direct=False):
 """Traverse from selected anchors, then down only their reachable ancestor groups."""
 fa=" AND a.kind='direct'" if direct else '';fb=" AND b.kind='direct'" if direct else ''
 return f'''WITH RECURSIVE au(ns,aw,anchor,anchor_code,ancestor,ad) AS (
 SELECT a.ns,a.id,a.product,a.code,a.code,0 FROM seed s JOIN witness a ON a.ns=s.ns AND a.product=s.product WHERE 1=1{fa}
 UNION ALL SELECT u.ns,u.aw,u.anchor,u.anchor_code,p.parent,u.ad+1 FROM au u JOIN parent p ON p.ns=u.ns AND p.child=u.ancestor WHERE u.ad<{depth}),
 down(ns,aw,anchor,anchor_code,ancestor,ad,code,pd) AS (
 SELECT ns,aw,anchor,anchor_code,ancestor,ad,ancestor,0 FROM au
 UNION ALL SELECT d.ns,d.aw,d.anchor,d.anchor_code,d.ancestor,d.ad,p.child,d.pd+1 FROM down d JOIN parent p ON p.ns=d.ns AND p.parent=d.code WHERE d.pd<{depth})
 SELECT d.ns,d.anchor,b.product peer,d.ancestor,d.anchor_code,b.code peer_code,d.ad anchor_depth,d.pd peer_depth,a.id anchor_witness,b.id peer_witness,a.premises anchor_premises,b.premises peer_premises
 FROM down d JOIN witness a ON a.ns=d.ns AND a.id=d.aw JOIN witness b ON b.ns=d.ns AND b.code=d.code
 WHERE b.product<>d.anchor{fb}'''

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--snapshot',choices=['D0','D1'],default='D1');p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.write_text(canon(build(args.root,args.snapshot))+'\n')
