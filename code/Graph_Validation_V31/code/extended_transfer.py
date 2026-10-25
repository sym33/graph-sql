"""New numerator-family task, adversarial policy controls, and rule sensitivity.

Pure V30 kernel bytes remain unchanged. This adapter interprets documentary
strength tokens; it never computes administered dose or reimbursement eligibility.
"""
from pathlib import Path
import collections,hashlib,itertools,json,re,sys,random,statistics
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path[:0]=[str(P/'Graph_Validation_V30/code'),str(P/'Validation_Study/code'),str(P/'Graph_Validation_V17/code')]
from completion_kernel import Completion,Field,Question
from evaluate_transfer import swiss,sql_check
from reference_oracle import Reference
from route_policies import available_routes,TOKENS
protocol=json.loads((R/'PROTOCOL.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(P/'Graph_Validation_V30/code/completion_kernel.py')==protocol['kernel_sha256']
VOCAB=frozenset(protocol['vocabulary'])
# Matches an explicit numeric numerator, including decimal/comma strength notation.
PATTERN=re.compile(r'(?<![\w])\d+(?:[.,]\d+)?\s*(mcg|mg|µg|ug|g|I\.?\s*E\.?|IU|UI|ml)(?![\w])',re.I)
MASS={'g','mg','mcg','ug','µg'}
def strength(text,variant='primary'):
 matches=[]
 for m in PATTERN.finditer(text):
  token=re.sub(r'[.\s]','',m[1]).lower(); tail=text[m.end():]
  concentration=bool(re.match(r'\s*/\s*(?:\d+(?:[.,]\d+)?\s*)?ml\b',tail,re.I))
  if variant=='no_concentration' and concentration:continue
  kind='MASS' if token in MASS else 'VOLUME' if token=='ml' else 'ACTIVITY'
  # Volumes elsewhere in a mass strength describe its denominator/container.
  matches.append({'token':m[1],'offset':[m.start(),m.end()],'family':kind,'concentration_numerator':concentration})
 relevant=[m for m in matches if m['family']!='VOLUME'] or matches
 kinds={m['family'] for m in relevant}
 if variant=='no_prefix_normalization':kinds={'MASS' if m['token'].lower()=='mg' else 'UNINTERPRETED:'+m['token'] for m in relevant}
 known=frozenset(kinds) if len(kinds)==1 and kinds<={'MASS','ACTIVITY'} else frozenset()
 return known,matches

def model_units(root,variant='primary'):
 route,labels,logical,digests=swiss(root);ref=Reference(root);fields=[];receipt=[]
 for key in route.fields:
  row=ref.records[key];known,tokens=strength(row['bezeichnung'],variant)
  fields.append(Field(key,VOCAB,known));receipt.append({'field':key,'package':row['bezeichnung'],'known':sorted(known),'tokens':tokens})
 qs=[]
 for key,q in route.questions.items():
  row=ref.records[logical[key][1]];unit=row['dose_unit']
  opts=frozenset({'MASS'}) if unit in {'mg','g','mcg'} else frozenset({'ACTIVITY'}) if variant=='U_as_activity' and unit=='U' else frozenset({'UNINTERPRETED:'+unit})
  qs.append(Question(key,q.fields,opts))
 return Completion(fields,qs,VOCAB),receipt,route,ref

def transitions(before,after):
 assert before.keys()==after.keys()
 return dict(sorted(collections.Counter(before[k]+'->'+after[k] for k in before).items()))

def universal_states(model):
 out={}
 for key,q in model.questions.items():
  states=[model.path(f,q.options) for f in q.fields]
  out[key]='V' if states and all(s=='V' for s in states) else 'C' if 'C' in states else 'U'
 return out

def adapter_controls():
 cases=[('Drug, 2 mg',{'MASS'}),('Drug, 2 g',{'MASS'}),('Drug, 200 mcg',{'MASS'}),('Drug, 2 mg/ml, Fl 50 ml',{'MASS'}),('Drug, 2 mg/5ml',{'MASS'}),('Drug, Fl 150 ml',set()),('Drug 2000 IE',{'ACTIVITY'}),('Drug 2000 IU',{'ACTIVITY'}),('Drug name without strength',set()),('Drug 2 mg + 200 IU',set())]
 for text,expected in cases:assert strength(text)[0]==frozenset(expected)
 assert not strength('Drug, 2 mg/ml, Fl 50 ml','no_concentration')[0]
 assert not strength('Drug, 2 g','no_prefix_normalization')[0]
 return {'authored_boundary_cases':12,'all_passed':True,'clinical_gold_standard':False}

def policy_controls():
 fields=[Field(k,frozenset({'x','y'})) for k in ['A','B','D']]
 qs=[Question('shared'+str(i),('A','B'),frozenset({'x'})) for i in range(3)]+[Question('sole'+str(i),('D',),frozenset({'x'})) for i in range(2)]
 m=Completion(fields,qs,{'x','y'});bounds=m.ranking(['A','D']);degree=sorted(['A','D'],key=lambda f:(-len(m.affected[f]),f));rows=[]
 for a,d in itertools.product(['x','y'],repeat=2):
  gains={f:sum(v!='U' for v in m.states({f:frozenset({a if f=='A' else d})}).values()) for f in ['A','D']}
  rows.append({'A':a,'D':d,'bound_selected':bounds[0]['field'],'degree_selected':degree[0],'bound_gain':gains[bounds[0]['field']],'degree_gain':gains[degree[0]]})
 assert [x['bound_gain'] for x in rows]==[2]*4 and sorted(x['degree_gain'] for x in rows)==[0,0,3,3]
 # All rows retained: a protection against unproductive selection, not domination.
 return {'design':'three shared-witness questions vs two sole-witness questions; B unrevealed','certificates':bounds,'all_singleton_assignments':rows,'bound_worst_gain':2,'degree_worst_gain':0,'bound_best_gain':2,'degree_best_gain':3,'SQL':sql_check(m)}

def budget_replay(model,eligible):
 eligible=tuple(sorted(eligible));sealed={f:model.fields[f].known for f in eligible};hidden={f:frozenset() for f in eligible};initial=model.states(hidden);unresolved={q for q,s in initial.items() if s=='U'};budgets=[b for b in protocol['budgets'] if b<=len(eligible)]
 def run(policy,rep=0):
  current=dict(hidden);remaining=set(eligible);states=dict(initial);order=list(eligible);random.Random(protocol['seed']+rep).shuffle(order);trace=[]
  cache={f:model.bounds(f,current) for f in eligible} if policy=='bounds' else {}
  for step in range(1,max(budgets)+1):
   if policy=='bounds':chosen=min(remaining,key=lambda f:(-cache[f]['minimum'],-cache[f]['maximum'],-cache[f]['affected_unresolved'],f))
   elif policy in {'degree','interpreted_degree'}:chosen=min(remaining,key=lambda f:(-sum(states[q]=='U' and (policy=='degree' or (bool(model.questions[q].options) and model.questions[q].options<=model.vocabulary)) for q in model.affected[f]),f))
   else:chosen=order[step-1]
   bound=model.bounds(chosen,current);current[chosen]=sealed[chosen];remaining.remove(chosen);increment=0
   for q in model.affected[chosen]:
    after=model.state(q,current);assert states[q]=='U' or states[q]==after;increment+=states[q]=='U' and after!='U';states[q]=after
   assert bound['minimum']<=increment<=bound['maximum']
   trace.append({'step':step,'field':chosen,'minimum_gain':bound['minimum'],'maximum_gain':bound['maximum'],'actual_increment':increment,'resolved':sum(states[q]!='U' for q in unresolved)})
   if policy=='bounds':
    touched={f for q in model.affected[chosen] for f in model.questions[q].fields}&remaining
    for f in touched:cache[f]=model.bounds(f,current)
  assert states==model.states(current)
  return trace
 b=run('bounds');d=run('degree');sd=run('interpreted_degree');randoms=[run('random',i) for i in range(protocol['random_orders'])];curves=[]
 for k in budgets:
  vals=sorted(x[k-1]['resolved'] for x in randoms);curves.append({'budget':k,'bounds_resolved':b[k-1]['resolved'],'degree_resolved':d[k-1]['resolved'],'interpreted_degree_resolved':sd[k-1]['resolved'],'random_median':statistics.median(vals),'random_min':min(vals),'random_max':max(vals),'random_values':vals})
 assert model.states({**hidden,**sealed})==model.states()
 return {'eligible_fields':len(eligible),'hidden_status':dict(collections.Counter(initial.values())),'original_status':dict(collections.Counter(model.states().values())),'curves':curves,'bound_trace':b,'degree_trace':d,'interpreted_degree_trace':sd,'all_full_restorations_agree':True,'all_determinate_judgments_preserved':True,'all_selected_field_bounds_valid':True}

def main():
 out={'kernel_sha256':protocol['kernel_sha256'],'protocol_sha256':sha(R/'PROTOCOL.json'),'adapter_controls':adapter_controls(),'policy_control':policy_controls(),'datasets':{}}
 for name,root in [('baseline',P),('June',P/'Graph_Validation_V9/temporal_snapshot')]:
  m,receipt,route,ref=model_units(root);states=m.states();eligible=[f for f,x in m.fields.items() if x.known];variants={}
  for var in ['no_concentration','no_prefix_normalization','U_as_activity']:
   alt,_,_,_=model_units(root,var);variants[var]={'status':dict(collections.Counter(alt.states().values())),'transitions':transitions(states,alt.states()),'SQL':sql_check(alt)}
  variants['all_presentations_required']={'status':dict(collections.Counter(universal_states(m).values())),'transitions':transitions(states,universal_states(m))}
  route_variants={}
  for policy in ['coarse','explicit_formulation']:
   fields=[Field(f.key,f.possible,frozenset(available_routes(ref.records[f.key]['gammenbezeichnung'],ref.records[f.key]['bezeichnung'],policy))) for f in route.fields.values()]
   alt=Completion(fields,list(route.questions.values()),TOKENS);route_variants[policy]={'status':dict(collections.Counter(alt.states().values())),'transitions':transitions(route.states(),alt.states()),'SQL':sql_check(alt)}
  out['datasets'][name]={'questions':len(m.questions),'fields':len(m.fields),'status':dict(collections.Counter(states.values())),'field_known':len(eligible),'SQL':sql_check(m),'fields_receipt':receipt,'questions_receipt':[{'id':q.key,'fields':list(q.fields),'options':sorted(q.options)} for q in m.questions.values()],'unit_variants':variants,'route_variants':route_variants,'acquisition':budget_replay(m,eligible)}
 (R/'results').mkdir(exist_ok=True);(R/'results/extended_transfer.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'control':out['policy_control'],'datasets':{n:{k:v for k,v in d.items() if k not in {'fields_receipt','questions_receipt','SQL','acquisition'}} for n,d in out['datasets'].items()},'budget_curves':{n:[{k:v for k,v in x.items() if k!='random_values'} for x in d['acquisition']['curves']] for n,d in out['datasets'].items()}},indent=2))
if __name__=='__main__':main()
