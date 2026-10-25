"""Attach source-bound before/after records to every changed candidate judgment."""
from pathlib import Path
import argparse,collections,json,sys

def main(root,initial,updated,receipt,output):
 sys.path.insert(0,str(root.resolve()/'Validation_Study/code'));from reference_oracle import Reference
 refs={'before':Reference(initial),'after':Reference(updated)};d=json.loads(receipt.read_text());changes=d['source_refresh_changes'];keys={tuple(k) for k in changes['added_keys']+changes['removed_keys']}|{(c['product'],c['tariff_record']) for c in changes['changed_shared_judgments']};result=[]
 for product,tariff in sorted(keys):
  auth=product.split(':')[-1];contexts={}
  for state,ref in refs.items():
   target=ref.records[tariff];sai=[];packages=[]
   for rid,p in ref.records.items():
    if rid.startswith('sai_praeparate.csv:') and p['ZULASSUNGSNUMMER']==auth:sai.append({'record':rid,'product_name':p['PRAEPARATENAME'],'ATC':p['ATC_CODE'],'matches_tariff':p['ATC_CODE']==target['code']})
    if rid.startswith('sl.csv:') and p['zulassungsnummer']==auth:packages.append({'record':rid,'package_code':p['swissmedic_nr'],'ATC':p['atc'],'package':p['bezeichnung'],'recorded_group':p['gammenbezeichnung'],'matches_tariff':p['atc']==target['code']})
   contexts[state]={'tariff_record':tariff,'tariff':target['ze_code'],'ATC':target['code'],'tariff_routes':target['va'],'SAI_records':sai,'SL_records':packages}
  result.append({'product':product,'tariff_record':tariff,'candidate_added':[product,tariff] in changes['added_keys'],'candidate_removed':[product,tariff] in changes['removed_keys'],'judgment_changes':[c for c in changes['changed_shared_judgments'] if (c['product'],c['tariff_record'])==(product,tariff)],'source_contexts':contexts})
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Source traces for',len(result),'affected candidate keys.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--initial',type=Path,required=True);p.add_argument('--updated',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root,a.initial,a.updated,a.receipt,a.output)
