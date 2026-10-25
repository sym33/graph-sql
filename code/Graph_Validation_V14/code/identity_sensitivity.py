"""Complete reference-identity sensitivity without ATC-based identity selection."""
from pathlib import Path
import json,csv,unicodedata,collections,hashlib
R=Path(__file__).resolve().parents[1];P=R.parent
norm=lambda s:' '.join(unicodedata.normalize('NFKC',s or '').casefold().split())
preferred=collections.defaultdict(set);trusted=collections.defaultdict(set);allnames=collections.defaultdict(set);molecular=collections.defaultdict(set)
trusted_types={'INN','BAN','USAN','JAN','DCF','FDA'}
for path in sorted((P/'External_Knowledge_Validation/raw').glob('chembl_molecules_*.json')):
 for m in json.loads(path.read_text())['molecules']:
  mid=m['molecule_chembl_id'];parent=(m.get('molecule_hierarchy') or {}).get('parent_chembl_id') or mid
  if norm(m.get('pref_name')):preferred[norm(m['pref_name'])].add(parent);molecular[norm(m['pref_name'])].add(mid)
  for syn in m.get('molecule_synonyms',[]):
   name=norm(syn.get('molecule_synonym') or syn.get('synonyms'))
   if name:
    allnames[name].add(parent)
    if syn.get('syn_type') in trusted_types:trusted[name].add(parent)
rows=list(csv.DictReader((P/'input/silver/ema_products.csv').open(encoding='utf-8-sig'),delimiter='|',escapechar='\\'))
old=[json.loads(x) for x in (P/'External_Knowledge_Validation/results/external_classification_decisions.jsonl').read_text().splitlines()]
results=[]
for row,previous in zip(rows,old):
 name=norm(row['substance']);valid=name not in {'','na','n/a'} and ';' not in name
 candidates={}
 for policy,index in [('preferred_only',preferred),('preferred_then_nomenclature',trusted),('preferred_then_all_synonyms',allnames)]:
  values=(preferred.get(name) or index.get(name,set())) if valid else set();candidates[policy]=sorted(values)
 candidates['preferred_exact_molecule']=sorted(molecular.get(name,set())) if valid else []
 def resolved(vals):return vals[0] if len(vals)==1 else None
 assert resolved(candidates['preferred_then_all_synonyms'])==previous.get('parent_chembl_id')
 results.append({'product_url':row['url'],'substance':row['substance'],'candidates':candidates,'resolved':{p:resolved(v) for p,v in candidates.items()}})
summary={'rows':len(rows),'policies':{},'nomenclature_synonym_types':sorted(trusted_types),'selection_excludes_asserted_ATC':True}
for policy in results[0]['resolved']:
 summary['policies'][policy]={'resolved':sum(x['resolved'][policy] is not None for x in results),'ambiguous':sum(len(x['candidates'][policy])>1 for x in results),'unresolved':sum(len(x['candidates'][policy])==0 for x in results)}
summary['all_synonym_resolutions_withheld_by_nomenclature']=sum(x['resolved']['preferred_then_all_synonyms'] is not None and x['resolved']['preferred_then_nomenclature'] is None for x in results)
summary['parent_resolved_preferred_but_multiple_exact_molecules']=sum(x['resolved']['preferred_only'] is not None and len(x['candidates']['preferred_exact_molecule'])>1 for x in results)
(R/'results/identity_sensitivity_records.json').write_text(json.dumps(results,indent=2));(R/'results/identity_sensitivity_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
