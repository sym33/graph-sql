from pathlib import Path
import json,collections,copy
from context_contract import evaluate_attribution
R=Path(__file__).resolve().parents[1];P=R.parent
records=json.loads((R/'results/audited_attribution_reference.json').read_text());reference={x['witness_id']:x for x in records};old=json.loads((R/'results/attribution_initial_decisions.json').read_text());lookup={x['authorization']:x for x in records};rows=[]
for item in old:
 claim=item['claim'];result=evaluate_attribution(claim,lookup[claim['authorization']],reference);assert result['verdict']==item['verdict'];rows.append({'claim':claim,'decision':result})
probes=[]
for b in records:
 c={'authorization':'CONTROLLED_OTHER_AUTHORIZATION','value':'CONTROLLED_OTHER_CODE','evidence_target':'current_authorized_classification'}
 result=evaluate_attribution(c,b,reference);assert result['verdict']=='UNDETERMINED';probes.append(result)
 wrong=copy.deepcopy(b);wrong['raw_code']='CONTROLLED_FORGED_VALUE';result=evaluate_attribution({'authorization':b['authorization'],'value':b['staged_code'],'evidence_target':'raw_refdata_field'},wrong,reference);assert result['verdict']=='UNDETERMINED';probes.append(result)
(R/'results/attribution_context_regression.json').write_text(json.dumps({'natural_decisions':rows,'additional_probes':probes,'natural_verdicts':dict(collections.Counter(x['decision']['verdict'] for x in rows)),'natural_decisions_preserved':len(rows),'current_context_conflict_and_forgery_probes':len(probes)},indent=2));print('66 natural judgments preserved; 44 mixed-context or forged-source probes undetermined.')
