"""Reproduce the frozen experiment; outputs are generated locally."""
from pathlib import Path
import argparse,subprocess,sys,json,gzip,hashlib,os
R=Path(__file__).resolve().parent
STEPS=[['Graph_Validation_V18/code/reproduce_specification.py', []], ['Graph_Validation_V14/code/clean_reconstruction.py', ['--source-data-root', '.']], ['External_Knowledge_Validation/code/evaluate_external_reference.py', []], ['Graph_Validation_V14/code/identity_sensitivity.py', []], ['Graph_Validation_V14/code/document_context.py', []], ['Graph_Validation_V14/code/attribution_regression.py', []], ['Graph_Validation_V14/code/classification_analysis.py', []], ['Graph_Validation_V10/code/run_indication_transfer.py', []], ['Graph_Validation_V12/code/mesh_projection.py', []], ['Graph_Validation_V14/code/context_experiment.py', []], ['Graph_Validation_V14/code/combined_challenges.py', []], ['Graph_Validation_V14/code/relational_comparator.py', []], ['Graph_Validation_V14/code/context_shacl.py', []], ['Graph_Validation_V15/code/inference_extension.py', []], ['Graph_Validation_V16/code/route_extension.py', []], ['Graph_Validation_V16/code/natural_cases.py', []], ['Graph_Validation_V16/code/ontology_ablation.py', []], ['Graph_Validation_V17/code/route_sensitivity.py', []], ['Graph_Validation_V17/code/section_documents.py', []], ['Graph_Validation_V17/code/certificate_validation.py', []], ['Graph_Validation_V21/code/route_reference_audit.py', []], ['Graph_Validation_V21/code/content_semantics.py', []], ['Graph_Validation_V21/code/discovery_comparison.py', []], ['Graph_Validation_V22/code/explanation_workflow.py', []], ['Graph_Validation_V23/code/ingredient_followup.py', []], ['Graph_Validation_V24/code/robustness.py', []], ['Graph_Validation_V25/code/transfer.py', []], ['Graph_Validation_V29/code/evidence_planning.py', []], ['Graph_Validation_V30/code/evaluate_transfer.py', []], ['Graph_Validation_V31/code/extended_transfer.py', []], ['Graph_Validation_V31/code/measure_costs.py', []]]
def run(script,args=()):
 path=R/script
 for base in R.iterdir():
  if base.is_dir() and base.name!='.git':
   for name in ['results','queries','ontology']: (base/name).mkdir(exist_ok=True)
 log=R/'.runs'/f'{path.parent.parent.name}_{path.stem}.log';log.parent.mkdir(exist_ok=True)
 print('Running '+script,flush=True)
 with log.open('w') as f:result=subprocess.run([sys.executable,str(path),*args],cwd=R,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
 if result.returncode:raise SystemExit('Failed: '+script+'; see '+str(log))
 print('Passed',flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true',help='Verify code and packed data without executing experiments.');p.add_argument('--neo4j',action='store_true',help='Rebuild the dedicated localhost:17474 experimental database; clears that database.');p.add_argument('--refresh',action='store_true',help='Run the frozen later-source comparison on the dedicated localhost:18474 refresh database.');a=p.parse_args()
 for row in json.loads((R/'MANIFEST.json').read_text())['files']:
  path=R/row['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'],f'Input/code drift: {path}'
 for row in json.loads((R/'packed_inputs.json').read_text()):
  data=gzip.decompress((R/row['packed']).read_bytes()) if 'packed' in row else (R/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
  if not a.verify_only:
   path=R/row['original'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 if a.verify_only:print('All code and data hashes verified.');return
 if a.neo4j:
  run('Validation_Study/code/rebuild_frozen_layer.py',['--root','.'])
  run('Graph_Validation_V9/code/export_baseline_evidence.py',['--root','.'])
  run('Graph_Validation_V10/code/export_indications.py',['--population','baseline'])
  run('Automated_Verification/code/run_claim_benchmark.py')
  run('Validation_Study/code/rebuild_frozen_layer.py',['--root','Graph_Validation_V9/temporal_snapshot'])
  run('Graph_Validation_V9/code/verify_temporal_physical.py')
  run('Graph_Validation_V10/code/export_indications.py',['--population','June'])
  run('Graph_Validation_V9/temporal_snapshot/Automated_Verification/code/run_claim_benchmark.py')
 run('practical_analysis.py')
 run('Robustness/evaluate.py')
 for script,args in STEPS:run(script,args)
 if a.neo4j:
  for script in ['Graph_Validation_V11/code/neo4j_content_gate.py','Graph_Validation_V12/code/verify_mesh_projection_neo4j.py','Graph_Validation_V14/code/verify_neo4j.py','Graph_Validation_V15/code/verify_neo4j_inference.py','Graph_Validation_V16/code/verify_neo4j_routes.py']:run(script)
  run('Graph_Validation_V22/code/explanation_workflow.py',['--neo4j-url','http://127.0.0.1:17474'])
  run('Graph_Validation_V23/code/ingredient_followup.py',['--neo4j-url','http://127.0.0.1:17474'])
  run('Graph_Validation_V25/code/native_transfer.py',['--neo4j-url','http://127.0.0.1:17474'])
  run('Graph_Validation_V30/code/native_completion.py',['--neo4j-url','http://127.0.0.1:17474'])
  run('Graph_Validation_V31/code/native_units.py',['--neo4j-url','http://127.0.0.1:17474'])
  run('Graph_Validation_V26/code/benchmark.py',['--root','.','--neo4j-url','http://127.0.0.1:17474','--output','Graph_Validation_V26/results/benchmark.json'])
  run('Graph_Validation_V27/code/complexity_benchmark.py',['--root','.','--neo4j-url','http://127.0.0.1:17474','--output','Graph_Validation_V27/results/complexity.json'])
  run('Graph_Validation_V27/code/profile_diagnostics.py',['--neo4j-url','http://127.0.0.1:17474','--receipt','Graph_Validation_V27/results/complexity.json','--output','Graph_Validation_V27/results/profile_diagnostics.json'])
  run('Graph_Validation_V28/code/storage_benchmark.py',['--root','.','--neo4j-url','http://127.0.0.1:17474','--output','Graph_Validation_V28/results/storage.json'])
 run('Graph_Validation_V28/code/query_change_audit.py',['--output','Graph_Validation_V28/results/query_changes.json'])
 if a.refresh:
  run('Source_Refresh/code/prepare.py',['--root','.','--target','.runs/refresh-updated'])
  run('Source_Refresh/code/compare.py',['--root','.','--initial','Graph_Validation_V9/temporal_snapshot','--updated','.runs/refresh-updated','--output','Source_Refresh/results'])
  run('Source_Refresh/code/plan_control.py',['--root','.','--updated','.runs/refresh-updated','--database','Source_Refresh/results/comparison.sqlite','--receipt','Source_Refresh/results/results.json','--output','Source_Refresh/results/plan_control.json'])
  run('Source_Refresh/code/audit_derivations.py',['--root','.','--updated','.runs/refresh-updated','--output','Source_Refresh/results/derivation_audit.json'])
  run('Source_Refresh/code/audit_fields.py',['--root','.','--initial','Graph_Validation_V9/temporal_snapshot','--updated','.runs/refresh-updated','--output','Source_Refresh/results/source_field_audit.json'])
  run('Source_Refresh/code/audit_mapping.py',['--output','Source_Refresh/results/mapping_audit.json'])
  run('Source_Refresh/code/audit_native.py',['--root','.','--updated','.runs/refresh-updated','--output','Source_Refresh/results/native_integrity.json'])
  run('Source_Refresh/code/explain_changes.py',['--root','.','--initial','Graph_Validation_V9/temporal_snapshot','--updated','.runs/refresh-updated','--receipt','Source_Refresh/results/results.json','--output','Source_Refresh/results/change_explanations.json'])
  run('Source_Refresh/code/uncertainty.py',['--receipt','Source_Refresh/results/results.json','--output','Source_Refresh/results/timing_intervals.json'])
  run('Source_Refresh/code/verify_receipt.py',['--root','.','--updated','.runs/refresh-updated','--observed','Source_Refresh/observed/registered_results.json.gz'])
 run('tests/test_deployment_costs.py')
 run('deployment_costs.py',['--task','L1_candidates=100','--refreshes','1'])
 print('All experiments passed.')
if __name__=='__main__':main()
