"""Uncertainty-preserving route inference and bounded value of source-field acquisition."""
from pathlib import Path
import argparse,collections,hashlib,itertools,json,sqlite3,sys
P=Path(__file__).resolve().parents[2];R=P/'Graph_Validation_V29'
sys.path[:0]=[str(P/'Validation_Study/code'),str(P/'Graph_Validation_V17/code')]
from reference_oracle import Reference
from route_policies import available_routes,family,TOKENS,assess
canon=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main(D):
 protocol=json.loads((R/'PROTOCOL.json').read_text())
 for p,h in protocol['inputs'].items():assert sha(D/p if (D/p).exists() else P/p)==h
 ref=Reference(D/'Graph_Validation_V9/temporal_snapshot');rows=json.loads((D/'Graph_Validation_V16/results/route_decisions.json').read_text())
 tariffs={k:v for k,v in ref.records.items() if k.startswith('ze_definitions.csv:')};ti=collections.defaultdict(list)
 for tid,t in tariffs.items():ti[t['code']].append(tid)
 pairs=set();expected_paths=set()
 for w in ref.witnesses.values():
  if w['jurisdiction']!='CH' or w['rule'] not in {'direct_SAI','via_authorization_SL'}:continue
  for tid in ti[w['atc']]:
   pairs.add((w['subject'],tid))
   if w['rule']=='via_authorization_SL':expected_paths.add((w['id'],tid))
 assert len(pairs)==564 and len(rows)==999 and {(x['witness'],x['tariff_record']) for x in rows}==expected_paths
 facts=[];groups=collections.defaultdict(list);byrecord=collections.defaultdict(set)
 for i,x in enumerate(rows):
  sl=ref.records[x['SL_record']];t=ref.records[x['tariff_record']];w=ref.witnesses[x['witness']]
  assert sl['bezeichnung']==x['package'] and sl['gammenbezeichnung']==x['recorded_group'] and t['va']==x['tariff_routes']
  assert x['SL_record'] in w['premise_ids'] and w['subject']==x['product'] and sl['atc']==t['code']==x['code']
  known=available_routes(x['recorded_group'],x['package'],'exact_code');f=family(x['recorded_group']);poss=set(protocol['possibilities'][f or 'unknown']);options={v.strip() for v in t['va'].split(',') if v.strip()}
  z={**x,'known':known,'poss':poss,'options':options,'family':f};facts.append(z);pair=(x['product'],x['tariff_record']);groups[pair].append(i);byrecord[x['SL_record']].add(pair)
 def decide(z,known=None):
  k=z['known'] if known is None else known;o=z['options'];q=z['poss']
  if not o:return 'U'
  if k:return 'V' if k&o else 'U' if not o<=TOKENS else 'C'
  if q<=o:return 'V'
  if not o<=TOKENS:return 'U'
  return 'C' if q.isdisjoint(o) else 'U'
 def aggregate(pair,overrides=None):
  xs=groups[pair];overrides=overrides or {};vals=[decide(facts[i],overrides.get(facts[i]['SL_record'])) for i in xs]
  return 'V' if 'V' in vals else 'C' if vals and set(vals)=={'C'} else 'U'
 original={p:('V' if any(assess(facts[i]['recorded_group'],facts[i]['package'],facts[i]['tariff_routes'],'exact_code')=='VERIFIED' for i in groups[p]) else 'C' if groups[p] and all(assess(facts[i]['recorded_group'],facts[i]['package'],facts[i]['tariff_routes'],'exact_code')=='CONTRADICTED' for i in groups[p]) else 'U') for p in pairs}
 baseline={p:aggregate(p) for p in pairs};assert collections.Counter(original.values())=={'V':102,'C':36,'U':426}
 assert all(baseline[p]==old for p,old in original.items() if old!='U')
 # Separate SQLite expression for the complete path decisions.
 db=sqlite3.connect(':memory:');db.execute('CREATE TABLE paths(id INTEGER PRIMARY KEY,k TEXT,p TEXT,o TEXT)');db.executemany('INSERT INTO paths VALUES(?,?,?,?)',[(i,canon(sorted(z['known'])),canon(sorted(z['poss'])),canon(sorted(z['options']))) for i,z in enumerate(facts)]);db.execute('CREATE TABLE vocabulary(code TEXT)');db.executemany('INSERT INTO vocabulary VALUES(?)',[(x,) for x in TOKENS])
 sql="""SELECT id,CASE WHEN json_array_length(o)=0 THEN 'U' WHEN json_array_length(k)>0 THEN CASE WHEN EXISTS(SELECT 1 FROM json_each(k) k1 JOIN json_each(o) o1 ON k1.value=o1.value) THEN 'V' WHEN EXISTS(SELECT 1 FROM json_each(o) WHERE value NOT IN (SELECT code FROM vocabulary)) THEN 'U' ELSE 'C' END WHEN NOT EXISTS(SELECT 1 FROM json_each(p) WHERE value NOT IN (SELECT value FROM json_each(paths.o))) THEN 'V' WHEN EXISTS(SELECT 1 FROM json_each(o) WHERE value NOT IN (SELECT code FROM vocabulary)) THEN 'U' WHEN EXISTS(SELECT 1 FROM json_each(p) p1 JOIN json_each(o) o1 ON p1.value=o1.value) THEN 'U' ELSE 'C' END status FROM paths"""
 assert dict(db.execute(sql))=={i:decide(z) for i,z in enumerate(facts)}
 # Exhaustive small-vocabulary controls, including an opaque route and unknown tariff code.
 controls=0
 for q in [{'O'},{'IV','SC','OTHER_PAREN'}]:
  for k in [set(),{'O'},{'IV'},{'IV','SC'}]:
   for o in [set(),{'O'},{'IV'},{'IV','SC'},{'unknown'}]:
    z={'known':k,'poss':q,'options':o};db.execute('DELETE FROM paths');db.execute('INSERT INTO paths VALUES(0,?,?,?)',(canon(sorted(k)),canon(sorted(q)),canon(sorted(o))));assert db.execute(sql).fetchone()[1]==decide(z);controls+=1
 def worlds(poss):
  xs=sorted(poss)
  return [set(c) for n in range(1,len(xs)+1) for c in itertools.combinations(xs,n)]
 def bounds(rid,current):
  affected=byrecord[rid];possible=facts[next(i for p in affected for i in groups[p] if facts[i]['SL_record']==rid)]['poss'];gains=[]
  for routes in worlds(possible):gains.append(sum(current[p]=='U' and aggregate(p,{rid:routes})!='U' for p in affected))
  return min(gains),max(gains),len(gains)
 missing=[]
 for rid,affected in sorted(byrecord.items()):
  z=facts[next(i for p in affected for i in groups[p] if facts[i]['SL_record']==rid)]
  if z['known'] or not any(baseline[p]=='U' for p in affected):continue
  lo,hi,n=bounds(rid,baseline);missing.append({'SL_record':rid,'package':z['package'],'ATC':z['code'],'family':z['family'],'affected_unresolved_pairs':sum(baseline[p]=='U' for p in affected),'minimum_determinate_gain':lo,'maximum_determinate_gain':hi,'worlds':n,'candidate_keys':[list(p) for p in sorted(affected) if baseline[p]=='U']})
 missing.sort(key=lambda x:(-x['minimum_determinate_gain'],-x['maximum_determinate_gain'],-x['affected_unresolved_pairs'],x['SL_record']))
 cause=collections.Counter();paircauses=[]
 for pair in sorted(pairs):
  if baseline[pair]!='U':continue
  blockers=set()
  if not groups[pair]:blockers.add('missing_linked_SL_package')
  for i in groups[pair]:
   z=facts[i]
   if decide(z)!='U':continue
   if not z['options']:blockers.add('missing_tariff_route')
   elif not z['options']<=TOKENS:blockers.add('unknown_tariff_route_token')
   elif not z['known']:blockers.add('missing_exact_route' if z['family'] else 'unmapped_source_family')
  key='+'.join(sorted(blockers)) or 'mixed_available_evidence';cause[key]+=1;paircauses.append({'pair':list(pair),'blockers':sorted(blockers)})
 # Complete masked-record reveal evaluation. No class is chosen based on a favorable outcome.
 trials=[]
 for rid,affected in sorted(byrecord.items()):
  z=facts[next(i for p in affected for i in groups[p] if facts[i]['SL_record']==rid)]
  if z['family']!='parenteral' or not z['known']:continue
  hidden={p:aggregate(p,{rid:set()}) for p in affected};lo,hi,n=bounds(rid,hidden)
  actual=sum(hidden[p]=='U' and baseline[p]!='U' for p in affected)
  assert lo<=actual<=hi and z['known']<=z['poss']
  for p in affected:
   if hidden[p]!='U':assert hidden[p]==baseline[p]
  trials.append({'SL_record':rid,'ATC':z['code'],'ATC_level2':z['code'][:3],'authorization':z['product'],'tariffs':len(affected),'hidden_unresolved_pairs':sum(v=='U' for v in hidden.values()),'minimum_gain':lo,'maximum_gain':hi,'actual_reveal_gain':actual,'bound_contains_actual':True})
 classes=[]
 for cls in sorted({x['ATC_level2'] for x in trials}):
  xs=[x for x in trials if x['ATC_level2']==cls];classes.append({'ATC_level2':cls,'records':len(xs),'authorizations':len({x['authorization'] for x in xs}),'masked_pair_occurrences':sum(x['hidden_unresolved_pairs'] for x in xs),'actual_reveal_gain_occurrences':sum(x['actual_reveal_gain'] for x in xs),'all_bounds_valid':all(x['bound_contains_actual'] for x in xs)})
 changed=[{'pair':list(p),'from':original[p],'to':baseline[p]} for p in sorted(pairs) if original[p]!=baseline[p]]
 result={'protocol_sha256':sha(R/'PROTOCOL.json'),'code_sha256':sha(Path(__file__)),'pairs':len(pairs),'paths':len(rows),'original_exact_status':dict(collections.Counter(original.values())),'partial_information_status':dict(collections.Counter(baseline.values())),'newly_determinate':changed,'unresolved_cause_counts':dict(cause),'unresolved_causes':paircauses,'field_priorities':missing,'missing_route_records':len(missing),'guaranteed_positive_value_records':sum(x['minimum_determinate_gain']>0 for x in missing),'potential_positive_value_records':sum(x['maximum_determinate_gain']>0 for x in missing),'maximum_single_field_gain':max(x['maximum_determinate_gain'] for x in missing),'maximum_guaranteed_single_field_gain':max(x['minimum_determinate_gain'] for x in missing),'masked_trials':trials,'masked_records':len(trials),'masked_authorizations':len({x['authorization'] for x in trials}),'masked_by_ATC_level2':classes,'complete_SQL_decisions_agree':True,'finite_SQL_controls':controls,'original_determinate_judgments_preserved':True,'all_masked_bounds_valid':True,'interpretation':'Acquisition bounds concern recorded exact-route judgments. Mask trials reveal archived fields, not newly acquired clinical evidence. Repeated pair occurrences across trials are reported separately from unique candidates. Single-record gains are not additive.'}
 (R/'results').mkdir(exist_ok=True);(R/'results/evidence_planning.json').write_text(json.dumps(result,indent=2)+'\n');(R/'results/partial_decision.sql').write_text(sql+';\n')
 print(json.dumps({k:v for k,v in result.items() if k not in {'field_priorities','unresolved_causes','masked_trials','newly_determinate'}},indent=2));print('First 5 field priorities:',json.dumps(missing[:5],indent=2))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--data-root',type=Path,default=P);args=a.parse_args();main(args.data_root)
