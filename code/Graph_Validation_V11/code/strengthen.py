"""New combined challenges, explicit information target, and frozen case protocol."""
from pathlib import Path
import sys,json,hashlib,copy,collections
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path.insert(0,str(P/'Graph_Validation_V10/code'))
from indication_reference import IndicationReference,digest
from typed_contract import assess
MARKERS={'','na','n/a','null','none','nan'}
def available(term):return isinstance(term,str) and term.strip().casefold() not in MARKERS

def evaluate(claim,bundle,ref,target='documentary_fidelity'):
    # Structural availability is established before dereferencing certificate fields.
    if not isinstance(bundle,dict) or not isinstance(bundle.get('assertion'),dict) or not isinstance(bundle.get('records'),list):
        return {'verdict':'UNDETERMINED','reason':'malformed_evidence_structure'}
    for record in bundle['records']:
        if not isinstance(record,dict) or not isinstance(record.get('id'),str) or not isinstance(record.get('payload_json'),str):
            return {'verdict':'UNDETERMINED','reason':'malformed_source_record'}
        try:payload=json.loads(record['payload_json'])
        except ValueError:return {'verdict':'UNDETERMINED','reason':'unreadable_source_payload'}
        if not isinstance(payload,dict):return {'verdict':'UNDETERMINED','reason':'nonobject_source_payload'}
    try:result=assess(claim,bundle,ref)
    except (KeyError,TypeError,ValueError,AttributeError):return {'verdict':'UNDETERMINED','reason':'incomplete_evidence_structure'}
    if result['verdict']=='VERIFIED' and target=='available_indication_content' and not available(bundle['assertion'].get('term')):
        return {'verdict':'UNDETERMINED','reason':'missing_indication_content'}
    if target not in {'documentary_fidelity','available_indication_content'}:
        return {'verdict':'UNDETERMINED','reason':'unsupported_evidence_target'}
    return result

def main():
 ref=IndicationReference(P/'Graph_Validation_V9/temporal_snapshot')
 bundles=[json.loads(s) for s in (P/'Graph_Validation_V10/results/June_indication_bundles.jsonl').read_text().splitlines()]
 bykind=collections.defaultdict(list)
 for b in bundles:bykind[b['assertion']['kind']].append(b)
 selected=[]
 for kind,rows in sorted(bykind.items()):selected.extend(sorted([b for b in rows if available(b['assertion']['term'])],key=lambda b:digest({'challenge_selection':b['assertion']['id']}))[:20])
 cases=[]
 for b in selected:
  a=b['assertion'];c={'witness':a['id'],**{k:a[k] for k in ['subject','term','kind','jurisdiction']},'source_snapshot':ref.files[a['record_id'].split(':')[0]],'time_scope':'frozen_documentary','statement_kind':'source_recorded_indication'}
  neighbor=next(x for x in bykind[a['kind']] if x['assertion']['term']!=a['term'] and x['assertion']['record_id']!=a['record_id'])
  def add(family,claim,bundle,label):cases.append({'family':family,'claim':claim,'bundle':bundle,'expected':label})
  add('faithful_control',c,b,'VERIFIED')
  changed=dict(c,term=neighbor['assertion']['term'],subject=neighbor['assertion']['subject']);add('real_neighbor_term_and_product',changed,b,'CONTRADICTED')
  changed=dict(c,term=neighbor['assertion']['term'],statement_kind='current_authorized_indication',time_scope='current');add('real_term_conflict_with_scope_escalation',changed,b,'CONTRADICTED')
  changed=copy.deepcopy(b);changed['records']=copy.deepcopy(neighbor['records']);add('authentic_source_record_transplant',c,changed,'UNDETERMINED')
  changed=copy.deepcopy(b);changed['records']*=2;add('duplicate_authentic_premise',c,changed,'UNDETERMINED')
  changed=copy.deepcopy(b);changed['products'].append(neighbor['assertion']['subject']);add('additional_real_product_endpoint',c,changed,'UNDETERMINED')
  changed=copy.deepcopy(b);payload=json.loads(changed['records'][0]['payload_json']);payload['near_valid_extra']='altered';changed['records'][0]['payload_json']=json.dumps(payload);changed['records'][0]['record_sha256']=digest(payload);changed['products']=neighbor['products'];add('coherent_payload_and_real_endpoint_transplant',c,changed,'UNDETERMINED')
  changed=copy.deepcopy(b);changed['records'][0]['payload_json']='[]';changed['records'][0]['record_sha256']=digest([]);add('valid_JSON_wrong_payload_type',c,changed,'UNDETERMINED')
  changed=copy.deepcopy(b);changed['records'][0].pop('id');add('missing_record_id',c,changed,'UNDETERMINED')
  changed=copy.deepcopy(b);changed['records']=None;add('null_premise_collection',c,changed,'UNDETERMINED')
  changed=dict(c,source_snapshot='other_snapshot',time_scope='current',statement_kind='payment_eligibility');add('combined_snapshot_time_payment_scope',changed,b,'UNDETERMINED')
  changed=copy.deepcopy(b);changed['products']=neighbor['products'];add('endpoint_transplant_with_claim_conflict',dict(c,term=neighbor['assertion']['term']),changed,'UNDETERMINED')
 protocol={'design':'deterministic within-setting combined engineering challenges, designed after V10 inspection; not held-out clinical labels','selected_per_kind':20,'cases':len(cases),'family_counts':dict(collections.Counter(x['family'] for x in cases)),'cases_sha256':digest(cases),'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'reference_input_hashes':ref.files,'precedence':'Unavailable certificate or physical support => UNDETERMINED; authenticated field disagreement => CONTRADICTED; unavailable scope => UNDETERMINED; otherwise VERIFIED.'}
 pp=R/'CHALLENGE_PROTOCOL.json'
 if pp.exists():assert json.loads(pp.read_text())==protocol
 else:pp.write_text(json.dumps(protocol,indent=2))
 output=[];old_errors=collections.Counter();matrix=collections.Counter()
 for x in cases:
  try:old=assess(x['claim'],x['bundle'],ref)['verdict']
  except Exception as exc:old='EXCEPTION';old_errors[type(exc).__name__]+=1
  new=evaluate(x['claim'],x['bundle'],ref);matrix[(x['expected'],new['verdict'])]+=1
  output.append({'family':x['family'],'witness':x['claim']['witness'],'expected':x['expected'],'original_verdict':old,'hardened_decision':new,'case_sha256':digest(x)})
 (R/'results/combined_challenges.json').write_text(json.dumps(output,indent=2))
 missing=[b for b in bundles if not available(b['assertion']['term'])]
 summary={'cases':len(cases),'witnesses':len(selected),'families':12,'original_exceptions':dict(old_errors),'hardened_mismatches':sum(n for (a,b),n in matrix.items() if a!=b),'hardened_verdicts':dict(collections.Counter(x['hardened_decision']['verdict'] for x in output)),'indications':len(bundles),'missing_content':len(missing),'eligible_content':len(bundles)-len(missing),'excluded_markers':sorted({b['assertion']['term'] for b in missing}),'missing_witness_ids':[b['assertion']['id'] for b in missing]}
 assert summary['hardened_mismatches']==0
 # Regression: original controlled populations retain all their decisions.
 regress=collections.Counter()
 for population,root in [('baseline',P),('June',P/'Graph_Validation_V9/temporal_snapshot')]:
  rr=IndicationReference(root)
  for b in map(json.loads,(P/'Graph_Validation_V10/results'/f'{population}_indication_bundles.jsonl').read_text().splitlines()):
   aa=b['assertion'];cc={'witness':aa['id'],**{k:aa[k] for k in ['subject','term','kind','jurisdiction']},'source_snapshot':rr.files[aa['record_id'].split(':')[0]],'time_scope':'frozen_documentary','statement_kind':'source_recorded_indication'}
   assert evaluate(cc,b,rr)['verdict']==assess(cc,b,rr)['verdict'];regress[population]+=1
 summary['faithful_regression_populations']=dict(regress)
 (R/'results/strengthening_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='missing_witness_ids'},indent=2))
if __name__=='__main__':main()
