"""Observed warm-cache machine costs; no surrogate claim about human effort."""
from pathlib import Path
import csv,hashlib,json,platform,random,statistics,subprocess,sys,time
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path.insert(0,str(R/'code'))
from extended_transfer import model_units,strength,sha
REPEATS=7

def measure(fn):
 fn();values=[]
 for _ in range(REPEATS):
  start=time.perf_counter_ns();fn();values.append((time.perf_counter_ns()-start)/1e6)
 return {'milliseconds':values,'median_ms':statistics.median(values),'minimum_ms':min(values),'maximum_ms':max(values)}

def scan(path):
 content=path.read_bytes();hashlib.sha256(content).hexdigest();return list(csv.DictReader(content.decode('utf-8-sig').splitlines(),delimiter='|'))

def replay(model,eligible,policy,budget):
 overrides={f:frozenset() for f in eligible};remaining=set(eligible);states=model.states(overrides);initial=set(q for q,s in states.items() if s=='U');order=sorted(eligible);random.Random(31011).shuffle(order)
 cache={f:model.bounds(f,overrides) for f in remaining} if policy=='bounds' else {}
 for step in range(budget):
  if policy=='bounds':chosen=min(remaining,key=lambda f:(-cache[f]['minimum'],-cache[f]['maximum'],-cache[f]['affected_unresolved'],f))
  elif policy in {'degree','interpreted_degree'}:chosen=min(remaining,key=lambda f:(-sum(states[q]=='U' and (policy=='degree' or (bool(model.questions[q].options) and model.questions[q].options<=model.vocabulary)) for q in model.affected[f]),f))
  else:chosen=order[step]
  overrides[chosen]=model.fields[chosen].known;remaining.remove(chosen)
  for q in model.affected[chosen]:states[q]=model.state(q,overrides)
  if policy=='bounds':
   touched={f for q in model.affected[chosen] for f in model.questions[q].fields}&remaining
   for f in touched:cache[f]=model.bounds(f,overrides)
 return sum(states[q]!='U' for q in initial)

def main():
 root=P/'Graph_Validation_V9/temporal_snapshot';path=root/'input/silver/sl.csv';rows=scan(path);m,receipt,_,_=model_units(root);eligible=[f for f in m.fields if m.fields[f].known]
 out={'code_sha256':sha(Path(__file__)),'cost_protocol_sha256':sha(R/'COST_PROTOCOL.json'),'scope':'Seven repeated warm-cache local source-recovery and planning runs, one untimed warmup. Network, human review, authoring and clinical adjudication excluded. CSV and PDF stages have different output granularity.','environment':{'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'pdf_renderer':subprocess.run(['pdftotext','-v'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.decode().strip()},'CSV':{'sha256':sha(path),'rows':len(rows),'read_decode_hash_ms':measure(lambda:scan(path))},'token_adapter':measure(lambda:[strength(x['package']) for x in receipt]),'PDF':[],'planning':[]}
 for item in json.loads((P/'Graph_Validation_V30/external/retrieval.json').read_text()):
  path=P/'Graph_Validation_V30/external'/f"{item['slug']}.pdf"
  out['PDF'].append({'medicine':item['name'],'sha256':sha(path),'bytes':path.stat().st_size,'whole_document_text_ms':measure(lambda:subprocess.check_output(['pdftotext','-enc','UTF-8','-layout',str(path),'-']))})
 for budget in [5,20]:
  for policy in ['bounds','degree','interpreted_degree','random']:
   expected=replay(m,eligible,policy,budget);timing=measure(lambda:replay(m,eligible,policy,budget));assert replay(m,eligible,policy,budget)==expected
   out['planning'].append({'budget':budget,'policy':policy,'resolved':expected,'planning_ms':timing,'questions_per_planning_second':expected/(timing['median_ms']/1000)})
 # First three measured extraction runs calibrate costs; four later runs
 # evaluate summed sequential extraction costs without reusing calibration times.
 transfer=json.loads((P/'Graph_Validation_V30/results/transfer.json').read_text())
 complete={x['name'] for x in transfer['EMA']['medicines'] if x['complete_inventory']}
 pdfs={x['medicine']:x for x in out['PDF'] if x['medicine'] in complete}
 train={n:statistics.median(x['whole_document_text_ms']['milliseconds'][:3]) for n,x in pdfs.items()}
 costorder=sorted(pdfs,key=lambda n:(train[n],n));nameorder=sorted(pdfs)
 rng=random.Random(31011);randomorders=[]
 for _ in range(128):
  order=list(nameorder);rng.shuffle(order);randomorders.append(order)
 rows=[]
 for budget in [1,2,5,9]:
  for policy,order in [('cost_ranked',costorder),('name_order',nameorder)]:
   test=[sum(pdfs[n]['whole_document_text_ms']['milliseconds'][rep] for n in order[:budget]) for rep in range(3,7)]
   rows.append({'budget':budget,'policy':policy,'resolved':16*budget,'heldout_component_costs_ms':test,'median_component_cost_ms':statistics.median(test),'selected':order[:budget]})
  sums=[statistics.median([sum(pdfs[n]['whole_document_text_ms']['milliseconds'][rep] for n in order[:budget]) for rep in range(3,7)]) for order in randomorders]
  rows.append({'budget':budget,'policy':'random_128_orders','resolved':16*budget,'median_component_cost_ms':statistics.median(sums),'minimum_component_cost_ms':min(sums),'maximum_component_cost_ms':max(sums)})
 out['cost_aware_EMA']={'scope':'Nine already complete inventories. Cost ranking calibrated on first three timed whole-PDF extractions; assessed on four later repetitions. Sum of extraction components, excluding planning/route parsing/network/human review. All inventories resolve 16 fixed questions. Retrospective machine-cost experiment.','training_costs_ms':train,'rows':rows}
 out['CSV']['equal_share_ms_per_row_proxy']=out['CSV']['read_decode_hash_ms']['median_ms']/out['CSV']['rows']
 out['CSV']['allocation_note']='Equal share of measured whole-file scan; not individually measured record acquisition or human cost.'
 (R/'results').mkdir(exist_ok=True);(R/'results/machine_costs.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:v for k,v in out.items() if k!='PDF'},indent=2));print('PDF median range ms:',min(x['whole_document_text_ms']['median_ms'] for x in out['PDF']),max(x['whole_document_text_ms']['median_ms'] for x in out['PDF']))
if __name__=='__main__':main()
