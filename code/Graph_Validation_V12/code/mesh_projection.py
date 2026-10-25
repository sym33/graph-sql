"""Frozen MeSH coannotation projection and explicit content-target selection.
Coannotation is a documentary relationship, not therapeutic interchangeability.
"""
from pathlib import Path
import collections,json,hashlib,itertools,sys
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path.insert(0,str(P/'Graph_Validation_V11/code'))
from strengthen import available

def sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def project(rows,gated):
 terms=collections.defaultdict(set)
 for b in rows:
  a=b['assertion']
  if a['kind']!='EMA_therapeutic_area_MeSH':continue
  if gated and not available(a['term']):continue
  terms[a['term']].add(a['subject'])
 pairs=collections.defaultdict(set)
 for term,subjects in terms.items():
  for left,right in itertools.combinations(sorted(subjects),2):pairs[(left,right)].add(term)
 return terms,pairs

def main():
 input_path=P/'Graph_Validation_V10/results/June_indication_bundles.jsonl'
 rows=[json.loads(x) for x in input_path.read_text().splitlines()]
 protocol={'population':'complete June EMA MeSH assertions','question':'Which source-scoped EMA medicine pairs share at least one recorded MeSH term?','before':'all literal recorded terms','after':'terms with available lexical content under V11 policy','edge':'unordered distinct source-scoped medicine pair, at least one common term','weight':'distinct shared terms','interpretation':'documentary coannotation only','design':'follow-up analytical consequence of previously identified missing markers, not blinded prospective discovery','bundle_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 path=R/'PROJECTION_PROTOCOL.json'
 if path.exists():assert json.loads(path.read_text())==protocol
 else:path.write_text(json.dumps(protocol,indent=2))
 before_terms,before=project(rows,False);after_terms,after=project(rows,True)
 removed=set(before)-set(after);retained=set(before)&set(after)
 changed={p for p in retained if before[p]!=after[p]}
 missing_subjects=set().union(*(s for t,s in before_terms.items() if not available(t)))
 retained_subjects=set().union(*after_terms.values())
 out=lambda pairs:[{'left':a,'right':b,'terms':sorted(t),'weight':len(t)} for (a,b),t in sorted(pairs.items())]
 summary={'all_mesh_witnesses':sum(x['assertion']['kind']=='EMA_therapeutic_area_MeSH' for x in rows),'available_mesh_witnesses':sum(x['assertion']['kind']=='EMA_therapeutic_area_MeSH' and available(x['assertion']['term']) for x in rows),'before_terms':len(before_terms),'after_terms':len(after_terms),'before_annotated_medicines':len(set().union(*before_terms.values())),'after_annotated_medicines':len(retained_subjects),'before_projected_pairs':len(before),'after_projected_pairs':len(after),'removed_pairs':len(removed),'retained_pairs':len(retained),'retained_pairs_with_changed_weights':len(changed),'missing_marker_medicines':len(missing_subjects),'missing_marker_medicines_with_other_available_mesh':len(missing_subjects & retained_subjects),'before_projection_sha256':sha(out(before)),'after_projection_sha256':sha(out(after)),'retained_pair_weights_preserved':not changed,'interpretation':protocol['interpretation']}
 (R/'results/mesh_projection_reference.json').write_text(json.dumps(summary,indent=2))
 (R/'results/removed_projection_pairs.json').write_text(json.dumps(out({p:before[p] for p in removed}),indent=2))
 (R/'results/missing_mesh_medicines.json').write_text(json.dumps(sorted(missing_subjects),indent=2))
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
