"""Full-census transfer and targeted component ablations on physical evidence."""
from pathlib import Path
import json,hashlib,collections,copy
from indication_reference import IndicationReference,digest
from typed_contract import assess
R=Path(__file__).resolve().parents[1];P=R.parent
protocol=json.loads((R/'TRANSFER_PROTOCOL.json').read_text())
for name,sha in protocol['code_SHA256'].items():
 assert hashlib.sha256((R/'code'/name).read_bytes()).hexdigest()==sha,name
all_summary={}
for population,root in [('baseline',P),('June',P/'Graph_Validation_V9/temporal_snapshot')]:
 ref=IndicationReference(root)
 assert ref.files==protocol['input_SHA256'][population]
 physical={x['assertion']['id']:x for x in map(json.loads,(R/'results'/f'{population}_indication_bundles.jsonl').read_text().splitlines())}
 assert set(physical)==set(ref.assertions)
 census=collections.Counter();matrix=collections.defaultdict(collections.Counter);families=collections.defaultdict(collections.Counter);n=0
 output=R/'results'/f'{population}_indication_decisions.jsonl'
 with output.open('w') as f:
  for wid,b in sorted(physical.items()):
   assertion=b['assertion'];assert assertion==ref.assertions[wid]
   claim={'witness':wid,**{k:assertion[k] for k in ['subject','term','kind','jurisdiction']},'source_snapshot':ref.files[assertion['record_id'].split(':',1)[0]],'time_scope':'frozen_documentary','statement_kind':'source_recorded_indication'}
   assert assess(claim,b,ref)['verdict']=='VERIFIED'
   census[assertion['kind']]+=1
   cases=[('faithful',claim,b,'VERIFIED')]
   for field,value in [('subject','NONEXISTENT_PRODUCT'),('term','NONEXISTENT_TERM'),('kind','NONEXISTENT_SOURCE_KIND'),('jurisdiction','OTHER_JURISDICTION')]:
    c=dict(claim);c[field]=value;cases.append(('wrong_'+field,c,b,'CONTRADICTED'))
   for scope in ['current_authorized_indication','treatment_recommendation','payment_eligibility']:
    c=dict(claim);c['statement_kind']=scope;cases.append((scope,c,b,'UNDETERMINED'))
   c=dict(claim);c['source_snapshot']='UNAVAILABLE_SNAPSHOT';cases.append(('unavailable_snapshot',c,b,'UNDETERMINED'))
   c=dict(claim);c['time_scope']='current';cases.append(('current_validity',c,b,'UNDETERMINED'))
   cases.append(('missing_evidence',claim,None,'UNDETERMINED'))
   modified=copy.deepcopy(b);record=modified['records'][0];payload=json.loads(record['payload_json']);payload['added_challenge_field']='coherent_forgery';record['payload_json']=json.dumps(payload,ensure_ascii=False);record['record_sha256']=digest(payload);cases.append(('coherent_source_forgery',claim,modified,'UNDETERMINED'))
   modified=copy.deepcopy(b);modified['products']=['NONEXISTENT_PRODUCT'];cases.append(('physical_endpoint_corruption',claim,modified,'UNDETERMINED'))
   assert len(cases)==13
   for family,c,e,gold in cases:
    outcomes={mode:assess(c,e,ref,None if mode=='complete' else mode.removeprefix('omit_')) for mode in ['complete','omit_source_binding','omit_physical_endpoints','omit_claim_fields','omit_scope']}
    row={'population':population,'witness_id':wid,'source_kind':assertion['kind'],'family':family,'operation_reference':gold,'claim':c,'decisions':outcomes}
    f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n');n+=1
    for mode,result in outcomes.items():
     matrix[mode][(gold,result['verdict'])]+=1
     families[family][mode+'_false_verified']+=int(gold!='VERIFIED' and result['verdict']=='VERIFIED')
 metrics={}
 for mode,counts in matrix.items():
  metrics[mode]={'cases':sum(counts.values()),'operation_label_mismatches':sum(count for (g,pred),count in counts.items() if g!=pred),'false_verifications':sum(count for (g,pred),count in counts.items() if g!='VERIFIED' and pred=='VERIFIED'),'faithful_verified':counts[('VERIFIED','VERIFIED')],'verdict_counts':{v:sum(count for (g,pred),count in counts.items() if pred==v) for v in ['VERIFIED','CONTRADICTED','UNDETERMINED']}}
 assert metrics['complete']['operation_label_mismatches']==0
 assert n==13*len(physical)
 summary={'physical_assertions':len(physical),'source_records':len(ref.records),'source_kinds':dict(census),'controlled_cases':n,'CSV_SQL_physical_complete_agreement':True,'metrics':metrics,'family_false_verifications':dict(families),'reference_sha256':ref.reference_sha256,'contract_sha256':hashlib.sha256((R/'code/typed_contract.py').read_bytes()).hexdigest(),'decisions_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'scope':'operation-defined engineering evaluation; same-team specification; within-setting relation transfer; no new clinical gold labels'}
 all_summary[population]=summary
 (R/'results'/f'{population}_indication_summary.json').write_text(json.dumps(summary,indent=2))
 print(json.dumps({'population':population,'assertions':len(physical),'cases':n,'metrics':metrics}),flush=True)
assert all_summary['baseline']['contract_sha256']==all_summary['June']['contract_sha256']
(R/'results/indication_transfer_summary.json').write_text(json.dumps(all_summary,indent=2))
