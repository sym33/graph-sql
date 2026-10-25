"""Verify deterministic registered outputs from the included frozen inputs."""
from pathlib import Path
import argparse,gzip,json,sys
from compare import workloads,expected_outputs,route_judgments,digest

def main(root,updated,observed):
 sys.path.insert(0,str(root.resolve()/'Validation_Study/code'));from reference_oracle import Reference
 sys.path.insert(0,str(root.resolve()/'Graph_Validation_V17/code'));from route_policies import assess
 d=json.loads(gzip.decompress(observed.read_bytes()) if observed.suffix=='.gz' else observed.read_bytes());refs={'June':Reference(root/'Graph_Validation_V9/temporal_snapshot'),'October':Reference(updated)};ws=workloads(root);expected={s:expected_outputs(r,ws) for s,r in refs.items()};judgments={s:route_judgments(expected[s]['L6_route_evidence'],expected[s]['L1_candidates'],assess) for s in refs}
 for check in d['correctness']:
  for k,x in check['workloads'].items():assert x['rows']==len(expected[check['state']][k]) and x['sha256']==digest(expected[check['state']][k])
  assert check['judgment_sha256']==digest(judgments[check['state']]) and check['judgments']==len(judgments[check['state']]);assert check['stale_or_mismatched_outputs']==0
 for measurement in d['timings']:assert measurement['sha256']==digest(expected[measurement['state']][measurement['workload']])
 assert len(d['correctness'])==56 and len(d['timings'])==840;print('All 56 state/arm/cycle checks and 840 measured outputs match frozen-source reconstruction.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--updated',type=Path,required=True);p.add_argument('--observed',type=Path,required=True);a=p.parse_args();main(a.root,a.updated,a.observed)
