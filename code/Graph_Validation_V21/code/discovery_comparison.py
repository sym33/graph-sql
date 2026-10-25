"""Information ablations on identical frozen inputs; full SQL is the strong comparator.
Measures results lost by declared source/context restrictions, not engine superiority.
"""
from pathlib import Path
import sys,json,collections,itertools,hashlib
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path[:0]=[str(P/'Validation_Study/code'),str(P/'Graph_Validation_V17/code')]
from reference_oracle import Reference
from route_policies import assess
ref=Reference(P/'Graph_Validation_V9/temporal_snapshot')
tariffs={r:x for r,x in ref.records.items() if r.startswith('ze_definitions.csv:')};bycode=collections.defaultdict(list)
for r,t in tariffs.items():bycode[t['code']].append(r)
direct=set();full=set();paths=[];routes=[]
for w in ref.witnesses.values():
 if w['jurisdiction']!='CH' or w['rule'] not in {'direct_SAI','via_authorization_SL'}:continue
 for tid in bycode[w['atc']]:
  pair=(w['subject'],tid);full.add(pair);paths.append((w['id'],tid))
  if w['rule']=='direct_SAI':direct.add(pair)
  else:
   rid=next(r for r in w['premise_ids'] if r.startswith('sl.csv:'));sl=ref.records[rid];t=tariffs[tid]
   judgments={p:assess(sl['gammenbezeichnung'],sl['bezeichnung'],t['va'],p) for p in ['coarse','exact_code','explicit_formulation']}
   routes.append({'witness':w['id'],'product':w['subject'],'SL_record':rid,'tariff_record':tid,'judgments':judgments})
# Independently expressed source-complete SQL, avoiding the derivation view.
ref.db.execute('CREATE TABLE tariff_cmp(rid TEXT,code TEXT)');ref.db.executemany('INSERT INTO tariff_cmp VALUES(?,?)',[(r,x['code']) for r,x in tariffs.items()])
sql="SELECT 'CH:authorization:'||s.auth,t.rid FROM sai s JOIN tariff_cmp t ON s.code=t.code UNION SELECT 'CH:authorization:'||s.auth,t.rid FROM sai s JOIN sl l ON s.auth=l.auth JOIN tariff_cmp t ON l.code=t.code"
sqlfull={tuple(x) for x in ref.db.execute(sql)};assert sqlfull==full
new=[x for x in routes if x['judgments']['coarse']=='VERIFIED' and x['judgments']['exact_code']=='CONTRADICTED'];stable=[x for x in routes if all(v=='CONTRADICTED' for v in x['judgments'].values())]
terms=collections.defaultdict(set)
for a in ref.indications.values():
 if a['kind']=='EMA_therapeutic_area_MeSH':terms[a['term']].add(a['subject'])
def project(gated):
 pairs=collections.defaultdict(set)
 for term,products in terms.items():
  if gated and term.strip().casefold() in {'','na','n/a','null','none','nan'}:continue
  for key in itertools.combinations(sorted(products),2):pairs[key].add(term)
 return pairs
raw,content=project(False),project(True);removed=set(raw)-set(content)
assert all(raw[k]==content[k] for k in content)
assert (len(direct),len(full),len(full-direct),len(paths),len(routes),len(new),len(stable),len(raw),len(content))==(560,564,4,1559,999,6,64,18600,18509)
summary={'design':'Retrospective information ablation; identical frozen June inputs and candidate definitions; source and context restrictions declared explicitly. Full source-preserving SQL retains the same information as the graph.','source_direct_pairs':len(direct),'source_complete_pairs':len(full),'additional_pairs':len(full-direct),'full_SQL_complete_set_agreement':True,'documentary_paths':len(paths),'route_paths':len(routes),'route_policies':{p:dict(collections.Counter(x['judgments'][p] for x in routes)) for p in ['coarse','exact_code','explicit_formulation']},'coarse_positive_exact_conflicts':len(new),'authorizations_new_conflicts':len({x['product'] for x in new}),'stable_conflict_paths':len(stable),'literal_coannotation_pairs':len(raw),'content_coannotation_pairs':len(content),'marker_only_pairs':len(removed),'retained_term_sets_unchanged':True,'additional_pair_keys':sorted(full-direct),'new_conflict_paths':new,'source_hashes':ref.files,'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(R/'results').mkdir(exist_ok=True);(R/'results/discovery_comparison.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in {'additional_pair_keys','new_conflict_paths','source_hashes'}},indent=2))
