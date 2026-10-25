"""Unchanged completion kernel: temporal replay, new EMA cohort, equal-budget acquisition."""
from pathlib import Path
import collections,csv,hashlib,itertools,json,random,re,sqlite3,subprocess,sys
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path[:0]=[str(R/'code'),str(P/'Validation_Study/code'),str(P/'Graph_Validation_V17/code')]
from completion_kernel import Completion,Field,Question
from reference_oracle import Reference
from route_policies import available_routes,family,TOKENS
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protocol=json.loads((R/'PROTOCOL.json').read_text());assert sha(R/'code/completion_kernel.py')==protocol['kernel_sha256']
canonical=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))

# Independent SQL path expression followed by complete candidate aggregation.
def sql_check(model):
 db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE fields(id TEXT,k TEXT,p TEXT);CREATE TABLE questions(id TEXT,o TEXT);CREATE TABLE paths(q TEXT,f TEXT);CREATE TABLE vocabulary(v TEXT);')
 db.executemany('INSERT INTO fields VALUES(?,?,?)',[(f.key,canonical(sorted(f.known)),canonical(sorted(f.possible))) for f in model.fields.values()])
 db.executemany('INSERT INTO questions VALUES(?,?)',[(q.key,canonical(sorted(q.options))) for q in model.questions.values()])
 db.executemany('INSERT INTO paths VALUES(?,?)',[(q.key,f) for q in model.questions.values() for f in q.fields]);db.executemany('INSERT INTO vocabulary VALUES(?)',[(v,) for v in model.vocabulary])
 sql="""WITH decisions AS (SELECT q.id,p.f,CASE WHEN p.f IS NULL OR json_array_length(q.o)=0 THEN 1
 WHEN json_array_length(f.k)>0 THEN CASE WHEN EXISTS(SELECT 1 FROM json_each(f.k) a JOIN json_each(q.o) b ON a.value=b.value) THEN 2 WHEN EXISTS(SELECT 1 FROM json_each(q.o) WHERE value NOT IN (SELECT v FROM vocabulary)) THEN 1 ELSE 0 END
 WHEN NOT EXISTS(SELECT 1 FROM json_each(f.p) WHERE value NOT IN (SELECT value FROM json_each(q.o))) THEN 2
 WHEN EXISTS(SELECT 1 FROM json_each(q.o) WHERE value NOT IN (SELECT v FROM vocabulary)) THEN 1
 WHEN EXISTS(SELECT 1 FROM json_each(f.p) a JOIN json_each(q.o) b ON a.value=b.value) THEN 1 ELSE 0 END s
 FROM questions q LEFT JOIN paths p ON p.q=q.id LEFT JOIN fields f ON f.id=p.f)
 SELECT id,CASE MAX(s) WHEN 2 THEN 'V' WHEN 0 THEN 'C' ELSE 'U' END FROM decisions GROUP BY id ORDER BY id"""
 actual=dict(db.execute(sql));assert actual==model.states();return {'questions':len(actual),'paths':sum(len(q.fields) for q in model.questions.values()),'agreement':True,'sql':sql}

def swiss(root):
 ref=Reference(root);tariffs={k:v for k,v in ref.records.items() if k.startswith('ze_definitions.csv:')};idx=collections.defaultdict(list)
 for key,row in tariffs.items():idx[row['code']].append(key)
 qs={};fields={};labels={};logical={}
 for w in ref.witnesses.values():
  if w['jurisdiction']!='CH' or w['rule'] not in {'direct_SAI','via_authorization_SL'}:continue
  for tid in idx[w['atc']]:
   key=canonical([w['subject'],tid]);q=qs.setdefault(key,{'fields':set(),'options':frozenset(x.strip() for x in tariffs[tid]['va'].split(',') if x.strip())});logical[key]=(w['subject'],tid)
   if w['rule']=='via_authorization_SL':
    rid=next(x for x in w['premise_ids'] if x.startswith('sl.csv:'));row=ref.records[rid];f=family(row['gammenbezeichnung']);known=frozenset(available_routes(row['gammenbezeichnung'],row['bezeichnung'],'exact_code'));possible=frozenset(protocol['possibilities'][f or 'unknown'])
    fields[rid]=Field(rid,possible,known);labels[rid]={'family':f,'ATC':row['atc'],'authorization':w['subject']};q['fields'].add(rid)
 model=Completion(list(fields.values()),[Question(k,tuple(sorted(x['fields'])),x['options']) for k,x in sorted(qs.items())],TOKENS)
 return model,labels,logical,{name:digest for name,digest in ref.files.items()}

# Same boundaries and exact positive patterns as the earlier V25 label census.
def ema():
 source=P/'Graph_Validation_V9/temporal_snapshot/input/silver/ema_products.csv';assert sha(source)==protocol['source_sha256']
 expected=[{'ordinal':i,'name':x['product_name'],'page_url':x['url'],'ATC':x['atc']} for i,x in enumerate(csv.DictReader(source.open(),delimiter='|'),1) if x['atc']=='L04AC05'];assert expected==protocol['heldout_cohort']
 retrieval=json.loads((R/'external/retrieval.json').read_text());assert [x['page_url'] for x in retrieval]==[x['page_url'] for x in expected]
 heading=re.compile(r'^\s*5\.\s*METHOD AND ROUTE(?:\(S\))? OF ADMINISTRATION\s*$',re.M);closing=re.compile(r'^\s*6\.\s*SPECIAL WARNING',re.M);title=re.compile(r'^\s*1\.\s*NAME OF THE MEDICINAL PRODUCT\s*$',re.M);second=re.compile(r'^\s*2\.\s*(?:STATEMENT OF ACTIVE|QUALITATIVE)',re.M)
 patterns={'IV':r'(?:for )?intravenous (?:infusion|use)(?: after dilution)?','SC':r'(?:for )?subcutaneous (?:use|injection)(?: only)?','IM':r'(?:for )?intramuscular (?:use|injection)','IT':r'(?:for )?intrathecal (?:use|injection)','O':r'(?:for )?oral use'}
 inventories={};medicines=[];extracted=[]
 for item in retrieval:
  record={k:item[k] for k in ['name','page_url','ATC','status']};found=[];complete=item['status']=='retrieved'
  if complete:
   pdf=R/'external'/f"{item['slug']}.pdf";assert sha(pdf)==item['pdf_sha256'];text=subprocess.check_output(['pdftotext','-enc','UTF-8','-layout',str(pdf),'-']).decode()
   for i,m in enumerate(heading.finditer(text)):
    end=closing.search(text,m.end());previous=list(title.finditer(text,0,m.start()));boundary=second.search(text,previous[-1].end()) if previous else None
    valid=bool(end and boundary and boundary.start()<m.start());value=text[m.end():end.start()] if end else '';name=' '.join(text[previous[-1].end():boundary.start()].split()) if valid else ''
    routes=sorted({r for r,pat in patterns.items() for line in value.splitlines() if re.fullmatch(pat,line.strip().lower().rstrip('.'))});valid=valid and bool(routes)
    f={'id':item['slug']+':label5:'+str(i+1),'medicine':item['page_url'],'title':name,'page':text[:m.start()].count('\f')+1,'field':value.strip(),'routes':routes,'complete':valid,'pdf_sha256':item['pdf_sha256'],'url':item['pdf_url']};found.append(f);extracted.append(f)
   complete=bool(found) and all(f['complete'] for f in found)
   codes=sorted(set(re.findall(r'ATC\s+code\s*:\s*([A-Z]\d{2}[A-Z]{2}\d{2})',text,re.I)));record.update(reference_ATC=codes,ATC_agrees=codes==[item['ATC']],pdf_sha256=item['pdf_sha256'])
  routes=frozenset(r for f in found if f['complete'] for r in f['routes']);record.update(complete_inventory=complete,label_fields=len(found),routes=sorted(routes));medicines.append(record)
  inventories[item['page_url']]=routes if complete else frozenset()
 fields=[Field(key,frozenset(protocol['possibilities']['unknown']),value) for key,value in inventories.items()]
 questions=[Question(canonical([a,b,r]),(b,),frozenset({r})) for a,routes in inventories.items() for r in sorted(routes) for b in inventories if a!=b]
 return Completion(fields,questions,TOKENS),medicines,extracted

def finite_controls():
 domains=frozenset({'a','b','OTHER'});values=(frozenset(),)+Completion.completions(domains);cases=worlds_checked=preserved=0
 for known in itertools.product(values,repeat=2):
  for options in [frozenset(),frozenset({'a'}),frozenset({'b'}),frozenset({'a','b'}),frozenset({'unmapped'})]:
   fields=[Field(str(i),domains,k) for i,k in enumerate(known)];m=Completion(fields,[Question('q',('0','1'),options)],{'a','b'});observed=m.state('q');outcomes=set()
   completions=[(k,) if k else Completion.completions(domains) for k in known]
   for pair in itertools.product(*completions):
    # Literal completed-world semantics, independently of kernel.path/state.
    outcomes.add('U' if not options else 'V' if any(v&options for v in pair) else 'C' if options<=m.vocabulary else 'U');worlds_checked+=1
   expected=next(iter(outcomes)) if len(outcomes)==1 else 'U';assert observed==expected
   for field in ('0','1'):
    if known[int(field)]:continue
    bound=m.bounds(field);real=[]
    for value in Completion.completions(domains):
     after=m.state('q',{field:value});real.append(int(observed=='U' and after!='U'))
     if observed!='U':assert after==observed;preserved+=1
    assert bound['minimum']==min(real) and bound['maximum']==max(real)
    for label,expect in [('minimum',bound['minimum']),('maximum',bound['maximum'])]:
     actual=int(observed=='U' and m.state('q',{field:frozenset(bound[label+'_witness_routes'])})!='U');assert actual==expect
   cases+=1
 # Explicit complementarity and redundancy counterexamples.
 m=Completion([Field('a',frozenset({'x','y'})),Field('b',frozenset({'x','y'}))],[Question('q',('a','b'),frozenset({'x'}))],{'x','y'})
 assert m.state('q',{'a':frozenset({'y'})})=='U' and m.state('q',{'b':frozenset({'y'})})=='U'
 assert m.state('q',{'a':frozenset({'y'}),'b':frozenset({'y'})})=='C'
 assert m.state('q',{'a':frozenset({'x'})})==m.state('q',{'b':frozenset({'x'})})==m.state('q',{'a':frozenset({'x'}),'b':frozenset({'x'})})=='V'
 empty=Completion([], [Question('q',(),frozenset({'x'}))],{'x'});assert empty.state('q')=='U'
 return {'fixtures':cases,'completed_world_evaluations':worlds_checked,'determinate_preservation_probes':preserved,'sharp_bounds_witnesses_checked':True,'complementarity_and_redundancy_checked':True,'missing_bridge_remains_U':True}

def acquisition(model,eligible):
 eligible=tuple(sorted(eligible));sealed={f:model.fields[f].known for f in eligible};assert all(sealed.values())
 hidden={f:frozenset() for f in eligible};initial=model.states(hidden);unresolved={q for q,s in initial.items() if s=='U'};original=model.states();budgets=sorted({b for b in protocol['budgets'] if b<=len(eligible)}|{len(eligible)})
 def run(policy,rep=0):
  current=dict(hidden);remaining=set(eligible);trace=[];order=list(eligible);random.Random(protocol['seed']+rep).shuffle(order)
  for step in range(1,len(eligible)+1):
   if policy=='bounds':chosen=model.ranking(remaining,current)[0]['field']
   elif policy=='degree':chosen=min(remaining,key=lambda f:(-sum(model.state(q,current)=='U' for q in model.affected[f]),f))
   else:chosen=order[step-1]
   certificate=model.bounds(chosen,current);before=model.states(current);current[chosen]=sealed[chosen];remaining.remove(chosen);after=model.states(current)
   actual=sum(before[q]=='U' and after[q]!='U' for q in model.affected[chosen]);assert certificate['minimum']<=actual<=certificate['maximum']
   assert all(after[q]==v for q,v in before.items() if v!='U')
   gain=sum(after[q]!='U' for q in unresolved);trace.append({'step':step,'field':chosen,'minimum_gain':certificate['minimum'],'maximum_gain':certificate['maximum'],'actual_increment':actual,'resolved':gain})
  assert model.states(current)==original
  return trace
 bound=run('bounds');degree=run('degree');randoms=[run('random',i) for i in range(protocol['random_orders'])]
 curves=[]
 for b in budgets:
  values=sorted(t[b-1]['resolved'] for t in randoms);curves.append({'budget':b,'bounds_resolved':bound[b-1]['resolved'],'degree_resolved':degree[b-1]['resolved'],'random_median':(values[63]+values[64])/2,'random_min':min(values),'random_max':max(values),'random_values':values})
 return {'eligible_fields':len(eligible),'initial_U':len(unresolved),'original_status':dict(collections.Counter(original.values())),'hidden_status':dict(collections.Counter(initial.values())),'curves':curves,'bound_trace':bound,'degree_trace':degree,'random_orders':protocol['random_orders'],'all_selected_field_bounds_valid':True,'all_determinate_judgments_preserved':True,'all_full_restorations_agree':True}

def main():
 results={'protocol_sha256':sha(R/'PROTOCOL.json'),'kernel_sha256':sha(R/'code/completion_kernel.py'),'code_sha256':sha(Path(__file__)),'controls':finite_controls()};models={};logical={}
 for name,root in [('baseline',P),('June',P/'Graph_Validation_V9/temporal_snapshot')]:
  m,labels,keys,digests=swiss(root);models[name]=m;logical[name]=set(keys.values());eligible=[f for f in m.fields if labels[f]['family']=='parenteral' and m.fields[f].known];missing=[f for f in m.fields if not m.fields[f].known and any(m.state(q)=='U' for q in m.affected[f])];bounds=[m.bounds(f) for f in missing]
  results[name]={'source_sha256':digests,'candidate_keys':len(m.questions),'linked_records':len(m.fields),'status':dict(collections.Counter(m.states().values())),'SQL':sql_check(m),'missing_fields':len(missing),'positive_minimum_fields':sum(b['minimum']>0 for b in bounds),'field_certificates':bounds,'acquisition':acquisition(m,eligible)}
 assert results['June']['status']=={'V':102,'C':43,'U':419} and results['June']['positive_minimum_fields']==97
 common_keys=set(models['baseline'].questions)&set(models['June'].questions)
 results['temporal_logical_candidates']={'common':len(logical['baseline']&logical['June']),'baseline_only':len(logical['baseline']-logical['June']),'June_only':len(logical['June']-logical['baseline']),'common_decision_transitions':dict(collections.Counter(models['baseline'].state(k)+'->'+models['June'].state(k) for k in common_keys))}
 m,medicines,fields=ema();missing=[f for f in m.fields if not m.fields[f].known];results['EMA']={'medicines':medicines,'label_fields':fields,'candidate_keys':len(m.questions),'status':dict(collections.Counter(m.states().values())),'field_certificates':[m.bounds(f) for f in missing],'SQL':sql_check(m),'acquisition':acquisition(m,[f for f in m.fields if m.fields[f].known])}
 (R/'results').mkdir(exist_ok=True);(R/'results/transfer.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'controls':results['controls'],'temporal':results['temporal_logical_candidates'],'datasets':{name:{k:results[name][k] for k in ['candidate_keys','status']} for name in ['baseline','June','EMA']},'EMA_medicines':[{k:x[k] for k in ['name','complete_inventory','label_fields','routes']} for x in medicines],'budget_curves':{name:[{k:v for k,v in row.items() if k!='random_values'} for row in results[name]['acquisition']['curves']] for name in ['baseline','June','EMA']}},indent=2))
if __name__=='__main__':main()
