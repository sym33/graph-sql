"""Reconstruct evidence graph with the exact, frozen implementation supplied."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();root=args.root.resolve();rebuilt=root/'Validation_Study/Rebuilt_Snapshot';rebuilt.mkdir(parents=True,exist_ok=True);(rebuilt/'results').mkdir(exist_ok=True)
sys.path.insert(0,str(rebuilt/'code'))
spec=importlib.util.spec_from_file_location('frozen_builder',rebuilt/'code/analyze_evidence.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
files,records=mod.read_inputs(root);layer=mod.build_layer(files,records);reverse=mod.build_layer(files,records,reverse=True);assert layer==reverse
implementation=hashlib.sha256((rebuilt/'code/analyze_evidence.py').read_bytes()).hexdigest();assert all(a['implementation_sha256']==implementation for a in layer['associations'].values())
mod.export_layer(rebuilt,layer);original=mod.load_layer(rebuilt,layer,'original');reversed_graph=mod.load_layer(rebuilt,reverse,'reverse')
assert all(original['fingerprints'][k]==reversed_graph['fingerprints'][k] for k in ['logical_records','logical_associations','logical_products','logical_indications'])
manifest={'implementation_sha256':implementation,'associations':len(layer['associations']),'source_records':len(records),'original':original,'reversed':reversed_graph,'reproduction_boundary':'root/input frozen silver; exact implementation under Rebuilt_Snapshot/code'}
(rebuilt/'results/reconstruction_manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({'implementation_sha256':implementation,'associations':len(layer['associations']),'loaded_order_invariant':True}),flush=True)
