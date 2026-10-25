from pathlib import Path
import sys,argparse,json,hashlib
R=Path(__file__).resolve().parents[1];P=R.parent
ap=argparse.ArgumentParser();ap.add_argument('--data-root',type=Path,default=P);D=ap.parse_args().data_root
sys.path.insert(0,str(P/'Validation_Study/code'));from reference_oracle import Reference
ref=Reference(D/'Graph_Validation_V9/temporal_snapshot')
base=json.loads((D/'Graph_Validation_V15/results/documentary_candidates.json').read_text());direct={(x['product'],x['tariff_record']) for x in base if x['rule']=='direct_SAI'};who=json.loads((D/'Thesis_Recovery/results/WHO_full_code_alterations.json').read_text());positive={}
for x in base:
 if (x['product'],x['tariff_record']) in direct:continue
 saiid=next(p for p in x['premise_ids'] if p.startswith('sai_praeparate.csv:'));slid=next(p for p in x['premise_ids'] if p.startswith('sl.csv:'));sai=ref.records[saiid];sl=ref.records[slid];t=ref.records[x['tariff_record']];alterations=[a for a in who if a['old']==sai['ATC_CODE'] and a['new']==sl['atc']];assert alterations
 positive[(x['product'],x['tariff_record'])]={'product':x['product'],'name':sai['PRAEPARATENAME'],'SAI_code':sai['ATC_CODE'],'SL_code':sl['atc'],'SL_group':sl['gammenbezeichnung'],'tariff':t['ze_code'],'tariff_code':t['code'],'tariff_route':t['va'],'witness':x['witness'],'premise_ids':x['premise_ids'],'WHO_alterations':alterations,'proof_steps':['equal authorization identifiers bind SAI and SL records','SL recorded classification equals frozen tariff code','recorded route family supports coarse tariff-route compatibility'],'statement_scope':'Frozen source attribution and coarse compatibility; current authorization/payment remain undetermined'}
assert len(positive)==4
(R/'results/natural_positive_traces.json').write_text(json.dumps(list(positive.values()),indent=2))
routes=json.loads((R/'results/route_decisions.json').read_text());neg=[]
for auth in ['CH:authorization:66173','CH:authorization:57843']:
 x=next(z for z in routes if z['product']==auth and z['status']=='CONTRADICTED');neg.append(x)
(R/'results/natural_route_counterexamples.json').write_text(json.dumps(neg,indent=2));print('Four complete positive traces and two selected natural route counterexamples retained.')
