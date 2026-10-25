"""Complete paired source-attribution/content-target assessment on June witnesses."""
from pathlib import Path
import json,sys,collections
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path[:0]=[str(P/'Graph_Validation_V14/code'),str(P/'Graph_Validation_V10/code')]
from context_contract import evaluate,MARKERS
from indication_reference import IndicationReference
ref=IndicationReference(P/'Graph_Validation_V9/temporal_snapshot');counts=collections.Counter();changes=[];n=0
with (P/'Graph_Validation_V10/results/June_indication_bundles.jsonl').open() as f:
 for line in f:
  b=json.loads(line);a=b['assertion'];n+=1;missing=not isinstance(a['term'],str) or a['term'].strip().casefold() in MARKERS
  base={'witness':a['id'],**{k:a[k] for k in ['subject','term','kind','jurisdiction']},'source_snapshot':ref.files[a['record_id'].split(':')[0]],'time_scope':'frozen_documentary','statement_kind':'source_recorded_indication'}
  for altered in [False,True]:
   claim={**base,'term':a['term']+' [controlled conflict]'} if altered else base
   for target in ['documentary_fidelity','available_indication_content']:
    d=evaluate(claim,b,ref,target);expected='UNDETERMINED' if missing and target=='available_indication_content' else 'CONTRADICTED' if altered else 'VERIFIED'
    assert d['verdict']==expected,(a['id'],target,d)
    assert d['frozen_field_comparison']['agrees']==(not altered)
    counts[target+('/field_conflict' if altered else '/faithful')+'/'+d['verdict']]+=1
    if missing and altered and target=='available_indication_content':changes.append({'witness':a['id'],'source_record':a['record_id'],'old':'CONTRADICTED','new':d['verdict'],'source_diagnostic':d['frozen_field_comparison'],'reason':d['reason']})
assert n==17447 and len(changes)==14
out={'June_witnesses':n,'decisions':4*n,'counts':dict(counts),'changed_information_target_decisions':len(changes),'record_attribution_decisions_changed':0,'authenticated_conflict_diagnostics_preserved':len(changes),'changes':changes,'scope':'Complete source-bound paired target test. Altered claims are controlled probes; the 14 missing source fields are natural records.'}
(R/'results').mkdir(exist_ok=True);(R/'results/content_semantics.json').write_text(json.dumps(out,indent=2)+'\n');print({k:v for k,v in out.items() if k!='changes'})
