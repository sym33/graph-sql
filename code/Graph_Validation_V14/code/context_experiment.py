from pathlib import Path
import sys,json,collections,copy,hashlib
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path.insert(0,str(P/'Graph_Validation_V10/code'))
from indication_reference import IndicationReference
from typed_contract import assess
from context_contract import evaluate
ref=IndicationReference(P/'Graph_Validation_V9/temporal_snapshot')
summary={'families':{},'input_sha256':hashlib.sha256((P/'Graph_Validation_V10/results/June_indication_bundles.jsonl').read_bytes()).hexdigest()}
out=R/'results/context_challenges.jsonl'
with out.open('w') as f:
 for line in (P/'Graph_Validation_V10/results/June_indication_bundles.jsonl').open():
  b=json.loads(line);a=b['assertion'];c={'witness':a['id'],**{k:a[k] for k in ['subject','term','kind','jurisdiction']},'source_snapshot':ref.files[a['record_id'].split(':')[0]],'time_scope':'frozen_documentary','statement_kind':'source_recorded_indication'}
  conflict=dict(c,term=a['term']+' [controlled conflict]')
  invalid=copy.deepcopy(b);invalid['products']=[]
  cases=[('faithful',c,b,'VERIFIED'),('supported_context_conflict',conflict,b,'CONTRADICTED'),('conflict_unavailable_snapshot',dict(conflict,source_snapshot='absent'),b,'UNDETERMINED'),('conflict_current_time',dict(conflict,time_scope='current'),b,'UNDETERMINED'),('conflict_unsupported_statement',dict(conflict,statement_kind='payment_eligibility'),b,'UNDETERMINED'),('conflict_invalid_endpoint',conflict,invalid,'UNDETERMINED')]
  for name,claim,bundle,label in cases:
   new=evaluate(claim,bundle,ref);old=assess(claim,bundle,ref);assert new['verdict']==label
   counts=summary['families'].setdefault(name,{'n':0,'new':{},'old':{},'changed':0})
   counts['n']+=1
   for k,value in [('new',new['verdict']),('old',old['verdict'])]:counts[k][value]=counts[k].get(value,0)+1
   counts['changed']+=new['verdict']!=old['verdict']
   f.write(json.dumps({'family':name,'witness':a['id'],'expected':label,'old_verdict':old['verdict'],'new':new})+'\n')
summary['cases']=sum(x['n'] for x in summary['families'].values());summary['mismatches']=0
# Reassess the retained 960 combined cases, preserving their observational labels as old-spec labels.
refchanges=[]
for x in json.loads((P/'Graph_Validation_V11/results/combined_challenges.json').read_text()):
 if x['family']=='real_term_conflict_with_scope_escalation':refchanges.append(x['witness'])
summary['earlier_combined_family_requires_relabeling']={'family':'real_term_conflict_with_scope_escalation','cases':len(refchanges),'old':'CONTRADICTED','context_first_expected':'UNDETERMINED'}
(R/'results/context_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
