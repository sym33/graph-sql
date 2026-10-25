"""Compare independently implemented source-link rules with the canonical input layer."""
from pathlib import Path
import argparse,importlib.util,sys,json

def main(root,updated,output):
 root=root.resolve();sys.path.insert(0,str(root/'Validation_Study/code'));from reference_oracle import Reference
 path=root/'Validation_Study/Rebuilt_Snapshot/code/analyze_evidence.py';sys.path.insert(0,str(path.parent));spec=importlib.util.spec_from_file_location('frozen_source_builder',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 files,records=m.read_inputs(updated);layer=m.build_layer(files,records);ref=Reference(updated);result=ref.compare(list(layer['associations'].values()));assert not result['missing'] and not result['extra'] and not result['property_mismatches'],result
 result['independent_source_derivation_agreement']=True;output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--updated',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root,a.updated,a.output)
