"""Complete source-policy analysis with separately reconstructed SQL witnesses."""
from pathlib import Path
import sys,json,collections,hashlib,itertools
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path.insert(0,str(P/'Validation_Study/code'))
from reference_oracle import Reference,canonical_hash
changes=json.loads((P/'Thesis_Recovery/results/WHO_full_code_alterations.json').read_text())
alterations={(x['old'],x['new']) for x in changes}
def analyze(rows):
 groups=collections.defaultdict(lambda:collections.defaultdict(set));premises=collections.defaultdict(set)
 for b in rows:
  a=b['association']
  if a['rule'] in {'direct_SAI','via_authorization_SL'}:
   groups[a['subject']][a['rule']].add(a['atc']);premises[a['subject']].update(a['premise_ids'])
 records=[]
 for product,rules in sorted(groups.items()):
  sai=rules.get('direct_SAI',set());sl=rules.get('via_authorization_SL',set());union=sai|sl
  if not sai or not sl:category='single_source'
  elif sai==sl and len(union)==1:category='exact_agreement'
  else:
   pairs=list(itertools.combinations(sorted(union),2))
   if all(a.startswith(b) or b.startswith(a) for a,b in pairs):category='hierarchical_difference'
   elif all((a,b) in alterations or (b,a) in alterations or a.startswith(b) or b.startswith(a) for a,b in pairs):category='recorded_temporal_or_hierarchical_difference'
   else:category='unreconciled_difference'
  records.append({'product':product,'SAI_codes':sorted(sai),'SL_codes':sorted(sl),'union_codes':sorted(union),'category':category,'premise_ids':sorted(premises[product])})
 counts=collections.Counter(x['category'] for x in records)
 union={(r['product'],c) for r in records for c in r['union_codes']}
 agreement={(r['product'],c) for r in records if r['category']=='exact_agreement' for c in r['union_codes']}
 summary={'products':len(records),'categories':dict(counts),'union_product_code_pairs':len(union),'agreement_only_product_code_pairs':len(agreement),'excluded_product_code_pairs':len(union-agreement),'union_digest':canonical_hash(sorted(union)),'agreement_digest':canonical_hash(sorted(agreement)),'source_group_digest':canonical_hash([{k:v for k,v in r.items() if k!='premise_ids'} for r in records])}
 return records,summary
summary={}
for snapshot,filename,root in [('baseline','baseline_physical_bundles.json',P),('June','temporal_physical_bundles.json',P/'Graph_Validation_V9/temporal_snapshot')]:
 path=P/'Graph_Validation_V9/results'/filename;bundles=json.loads(path.read_text());records,s=analyze(bundles)
 ref=Reference(root);expected=[{'association':a} for a in ref.witnesses.values()];_,rs=analyze(expected)
 assert rs==s
 s['complete_SQL_agreement']=True;s['physical_bundle_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();summary[snapshot]=s
 (R/'results'/f'{snapshot}_source_policy_records.json').write_text(json.dumps(records,indent=2))
 # Best simple relational comparator retains witnesses, source records and policy assessments.
 db=ref.db;db.execute('CREATE TABLE policy_assertions(product TEXT,code TEXT,rule TEXT,witness TEXT)')
 db.executemany('INSERT INTO policy_assertions VALUES(?,?,?,?)',[(a['subject'],a['atc'],a['rule'],a['id']) for a in ref.witnesses.values() if a['rule'] in {'direct_SAI','via_authorization_SL'}])
 union=list(db.execute('SELECT DISTINCT product,code FROM policy_assertions ORDER BY product,code'))
 agreement=list(db.execute("SELECT product,MIN(code) FROM policy_assertions GROUP BY product HAVING COUNT(DISTINCT code)=1 AND COUNT(DISTINCT rule)=2 ORDER BY product,MIN(code)"))
 assert canonical_hash([list(x) for x in union])==s['union_digest'];assert canonical_hash([list(x) for x in agreement])==s['agreement_digest']
 s['strong_relational_agreement']=True
summary['interpretation']='Co-recorded classification agreement, not current regulatory truth. Policy trades source coverage for agreement; no claim that withheld products are false.'
(R/'results/source_policy_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
