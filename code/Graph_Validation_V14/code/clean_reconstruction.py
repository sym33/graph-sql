"""Executable from the public code candidate; accepts separately supplied frozen CSVs."""
from pathlib import Path
import argparse,sys,json,hashlib,shutil,tempfile,importlib.util
P=Path(__file__).resolve().parents[2];R=P/'Graph_Validation_V14'
parser=argparse.ArgumentParser();parser.add_argument('--source-data-root',required=True);args=parser.parse_args();source=Path(args.source_data_root)
sys.path[:0]=[str(P/'Validation_Study/Rebuilt_Snapshot/code'),str(P/'Validation_Study/code'),str(P/'Graph_Validation_V10/code')]
import analyze_evidence
from reference_oracle import Reference
from indication_reference import IndicationReference,digest
expected=json.loads((R/'results/reconstruction_expected.json').read_text());results={}
with tempfile.TemporaryDirectory(prefix='medication-frozen-inputs-') as work:
 for population,inputroot in [('baseline',source),('June',source/'Graph_Validation_V9/temporal_snapshot')]:
  root=Path(work)/population;(root/'input/silver').mkdir(parents=True);(root/'Validation_Study/Rebuilt_Snapshot/code').mkdir(parents=True)
  # Reference implementation identity is bound to the packaged builder bytes.
  for name in ['analyze_evidence.py','run_baseline.py']:shutil.copy2(P/'Validation_Study/Rebuilt_Snapshot/code'/name,root/'Validation_Study/Rebuilt_Snapshot/code'/name)
  for path in (inputroot/'input/silver').glob('*.csv'):shutil.copy2(path,root/'input/silver'/path.name)
  files,records=analyze_evidence.read_inputs(root);layer=analyze_evidence.build_layer(files,records);ref=Reference(root);ir=IndicationReference(root)
  assert layer['associations']==ref.witnesses and layer['indications']==ir.assertions
  classification_digest=digest(layer['associations']);indication_digest=digest(layer['indications'])
  assert classification_digest==expected[population]['classification_digest'];assert indication_digest==expected[population]['indication_digest']
  assert ref.files==expected[population]['input_hashes']
  results[population]={'files':len(files),'records':len(records),'classification_witnesses':len(layer['associations']),'indication_witnesses':len(layer['indications']),'complete_SQL_and_physical_digest_agreement':True,'classification_digest':classification_digest,'indication_digest':indication_digest}
results['scope']='New workspace, isolated Python, packaged builder and separately expressed references; frozen CSVs supplied separately; same-team execution.'
print(json.dumps(results,indent=2))
