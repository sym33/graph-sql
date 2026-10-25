"""Compare relevant source values without treating a new file hash as a field change."""
from pathlib import Path
import argparse,collections,json,sys

def group(ref,name,key,fields):
 g=collections.defaultdict(set)
 for rid,p in ref.records.items():
  if not rid.startswith(name+':'):continue
  identifier=p.get(key)
  if not identifier or identifier in {'NA',''}:continue
  g[identifier].add(tuple(p[f] for f in fields))
 return g

def main(root,initial,updated,output):
 sys.path.insert(0,str(root.resolve()/'Validation_Study/code'));from reference_oracle import Reference
 initial,updated=Reference(initial),Reference(updated);out={}
 for source,key,fields in [('sl.csv','swissmedic_nr',['atc','gammenbezeichnung','bezeichnung']),('sai_praeparate.csv','ZULASSUNGSNUMMER',['ATC_CODE','PRAEPARATENAME'])]:
  a=group(initial,source,key,fields);b=group(updated,source,key,fields);shared=set(a)&set(b)
  out[source]={'key':key,'field_order':fields,'initial_distinct_keys':len(a),'new_distinct_keys':len(b),'shared':len(shared),'added':len(b.keys()-a.keys()),'removed':len(a.keys()-b.keys()),'keys_with_changed_relevant_fields':sum(a[k]!=b[k] for k in shared),'field_changes':{field:sum({v[i] for v in a[k]}!={v[i] for v in b[k]} for k in shared) for i,field in enumerate(fields)}}
 sl=[p for rid,p in updated.records.items() if rid.startswith('sl.csv:')];out['mapping']={'normalized_SL_rows':len(sl),'original_excel_rows':len({p['official_row'] for p in sl}),'without_authorization':sum(p['zulassungsnummer']=='NA' for p in sl),'expanded_rows':len(sl)-len({p['official_row'] for p in sl})}
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--initial',type=Path,required=True);p.add_argument('--updated',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root,a.initial,a.updated,a.output)
