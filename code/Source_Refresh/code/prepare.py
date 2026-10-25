"""Assemble the refreshed snapshot without duplicating unchanged release inputs."""
from pathlib import Path
import argparse,shutil,hashlib,json

def main(root,target):
 root=root.resolve();target=target.resolve();initial=root/'Graph_Validation_V9/temporal_snapshot/input/silver';overlay=root/'Source_Refresh/input/silver'
 destination=target/'input/silver';destination.mkdir(parents=True,exist_ok=True)
 for p in initial.glob('*.csv'):shutil.copy2(p,destination/p.name)
 for name in ['sl.csv','sai_praeparate.csv']:shutil.copy2(overlay/name,destination/name)
 code=target/'code';code.mkdir(exist_ok=True);shutil.copy2(root/'Validation_Study/Rebuilt_Snapshot/code/analyze_evidence.py',code/'analyze_evidence.py')
 hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.glob('*.csv')};print(json.dumps(hashes,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--target',type=Path,default=Path('.runs/refresh-updated'));a=p.parse_args();main(a.root,a.target)
