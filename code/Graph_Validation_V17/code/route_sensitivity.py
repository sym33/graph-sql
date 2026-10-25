from pathlib import Path
import argparse,json,collections,hashlib,sys
from route_policies import assess,available_routes
R=Path(__file__).resolve().parents[1];P=R.parent
ap=argparse.ArgumentParser();ap.add_argument('--data-root',type=Path,default=P);D=ap.parse_args().data_root
rows=json.loads((D/'Graph_Validation_V16/results/route_decisions.json').read_text())
sys.path.insert(0,str(P/'Validation_Study/code'));from reference_oracle import Reference
ref=Reference(D/'Graph_Validation_V9/temporal_snapshot')
for x in rows:
 sl=ref.records[x['SL_record']];t=ref.records[x['tariff_record']]
 assert sl['bezeichnung']==x['package'] and sl['gammenbezeichnung']==x['recorded_group'] and t['va']==x['tariff_routes']
 assert sl['atc']==t['code']==x['code']
 assert assess(x['recorded_group'],x['package'],x['tariff_routes'],'coarse')==x['status']
policies=['coarse','exact_code','explicit_formulation'];decisions=[];summary={}
for policy in policies:
 groups=collections.defaultdict(set);status=collections.Counter()
 for x in rows:
  verdict=assess(x['recorded_group'],x['package'],x['tariff_routes'],policy);status[verdict]+=1;groups[(x['product'],x['tariff_record'])].add(verdict)
  decisions.append({'witness':x['witness'],'product':x['product'],'SL_record':x['SL_record'],'tariff_record':x['tariff_record'],'policy':policy,'status':verdict,'available_source_routes':sorted(available_routes(x['recorded_group'],x['package'],policy))})
 cohort=collections.Counter('VERIFIED' if 'VERIFIED' in v else 'CONTRADICTED' if v=={'CONTRADICTED'} else 'UNDETERMINED' for v in groups.values());cohort['UNDETERMINED']+=137
 summary[policy]={'derivations':dict(status),'product_tariff_pairs':dict(cohort),'complete_output_sha256':hashlib.sha256(json.dumps([d for d in decisions if d['policy']==policy],sort_keys=True).encode()).hexdigest()}
bykey={(x['witness'],x['tariff_record'],x['policy']):x for x in decisions}
transitions={};new_conflicts=[]
for policy in policies[1:]:
 counts=collections.Counter()
 for x in rows:
  new=bykey[(x['witness'],x['tariff_record'],policy)]['status'];counts[x['status']+' -> '+new]+=1
  if x['status']=='VERIFIED' and new=='CONTRADICTED':new_conflicts.append({**x,'policy':policy,'refined_status':new})
 transitions[policy]=dict(counts)
stable=[x for x in rows if all(bykey[(x['witness'],x['tariff_record'],p)]['status']=='CONTRADICTED' for p in policies)]
result={'cases_per_policy':len(rows),'policies':summary,'transitions_from_coarse':transitions,'conflicts_stable_all_policies':len(stable),'products_with_stable_conflicts':len({x['product'] for x in stable}),'policy_sha256':hashlib.sha256((R/'code/route_policies.py').read_bytes()).hexdigest(),'scope':'Resolution/availability sensitivity of source-bound recorded-route comparisons; no exact authorized-route gold standard.'}
(R/'results/route_sensitivity.json').write_text(json.dumps(result,indent=2));(R/'results/route_policy_decisions.json').write_text(json.dumps(decisions,indent=2));(R/'results/refined_route_counterexamples.json').write_text(json.dumps(new_conflicts,indent=2));print(json.dumps(result,indent=2))
