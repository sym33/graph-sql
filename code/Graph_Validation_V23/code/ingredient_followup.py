"""Protocol-bound follow-up using materialized ingredient/tariff relationships."""
from pathlib import Path
import argparse,collections,hashlib,json,re,sys,sqlite3,datetime
from rdflib import Graph,Namespace,URIRef,Literal,RDF,OWL
from owlrl import DeductiveClosure,OWLRL_Semantics
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path[:0]=[str(P/'Validation_Study/code'),str(P/'Graph_Validation_V17/code')]
from reference_oracle import Reference
from route_policies import assess
ap=argparse.ArgumentParser();ap.add_argument('--neo4j-url');args=ap.parse_args()
protocol_path=R/'FOLLOWUP_PROTOCOL.json';protocol=json.loads(protocol_path.read_text());protocol_sha=hashlib.sha256(protocol_path.read_bytes()).hexdigest()
ref=Reference(P/'Graph_Validation_V9/temporal_snapshot');assert ref.files==protocol['inputs']
canon=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
normal=lambda s:' '.join(s.strip().casefold().split())
EX=Namespace('https://example.org/medigraph/evidence/')
def uri(kind,key):return URIRef(str(EX)+kind+'/'+hashlib.sha256(key.encode()).hexdigest())
ontology=P/'Graph_Validation_V15/ontology/medication_evidence.ttl';assert hashlib.sha256(ontology.read_bytes()).hexdigest()==protocol['ontology_sha256']
g=Graph().parse(ontology);tariffs={rid:x for rid,x in ref.records.items() if rid.startswith('ze_definitions.csv:')};index=collections.defaultdict(list)
for rid,x in tariffs.items():index[x['code']].append(rid);g.add((uri('code',x['code']),EX.listedByTariff,uri('tariff',rid)))
paths=[];ingredient_ids={};witness_ids={};tariff_ids={uri('tariff',rid):rid for rid in tariffs}
for w in ref.witnesses.values():
 if w['jurisdiction']!='CH' or w['rule'] not in {'direct_SAI','via_authorization_SL'} or not index[w['atc']]:continue
 wu=uri('witness',w['id']);witness_ids[wu]=w['id'];g.add((wu,EX.recordedCode,uri('code',w['atc'])))
 if w['rule']!='via_authorization_SL':continue
 sid=next(p for p in w['premise_ids'] if p.startswith('sai_praeparate.csv:'));rid=next(p for p in w['premise_ids'] if p.startswith('sl.csv:'));sl=ref.records[rid];text=sl.get('substanzen','')
 if normal(text) in {'','na','n/a','null','none','nan'}:continue
 iu=uri('ingredient-declaration',rid);ingredient_ids[iu]=rid;g.add((wu,EX.ingredientDeclaration,iu));g.add((iu,EX.lexicalValue,Literal(text)))
 for tid in index[w['atc']]:
  paths.append({'witness':w['id'],'product':w['subject'],'sai_record':sid,'SL_record':rid,'tariff_record':tid,'tariff':tariffs[tid]['ze_code'],'ingredient':text,'ingredient_key':normal(text),'code':w['atc'],'package':sl['bezeichnung'],'group':sl['gammenbezeichnung'],'tariff_routes':tariffs[tid]['va'],'premise_ids':sorted(w['premise_ids']+[tid])})
def inferred_pairs(graph):return {(ingredient_ids[i],tariff_ids[t]) for i,t in graph.subject_objects(EX.ingredientTariffCandidate)}
def documentary(graph):return {(witness_ids[w],tariff_ids[t]) for w,t in graph.subject_objects(EX.documentaryTariff)}
assert not inferred_pairs(g)
# Separate source SQL builds paths and uses a separately expressed route decision.
db=ref.db;db.create_function('regexp',2,lambda pat,x:int(bool(re.search(pat,x or '',re.I))))
db.execute('CREATE TABLE tariff_followup(rid TEXT,code TEXT,va TEXT)');db.executemany('INSERT INTO tariff_followup VALUES(?,?,?)',[(rid,x['code'],x['va']) for rid,x in tariffs.items()])
base_sql="""SELECT DISTINCT s.rid sai,l.rid sl,t.rid tariff,json_extract(i.payload,'$.substanzen') ingredient,json_extract(i.payload,'$.gammenbezeichnung') grp,json_extract(i.payload,'$.bezeichnung') package,t.va
FROM sai s JOIN sl l ON s.auth=l.auth JOIN tariff_followup t ON l.code=t.code JOIN input i ON i.rid=l.rid WHERE lower(trim(coalesce(json_extract(i.payload,'$.substanzen'),''))) NOT IN ('','na','n/a','null','none','nan')"""
sqlpaths=[dict(x) for x in db.execute(base_sql)];expected_pairs={(x['sl'],x['tariff']) for x in sqlpaths};assert {(x['sai_record'],x['SL_record'],x['tariff_record']) for x in paths}=={(x['sai'],x['sl'],x['tariff']) for x in sqlpaths}
DeductiveClosure(OWLRL_Semantics).expand(g);full_pairs=inferred_pairs(g);full_docs=documentary(g);assert full_pairs==expected_pairs and len(full_pairs)==999
# The downstream query consumes the derived predicate as its relational input.
def downstream(graph,policy):
 admitted=inferred_pairs(graph);out=[]
 for x in paths:
  if (x['SL_record'],x['tariff_record']) in admitted:out.append({**x,'policy':policy,'status':assess(x['group'],x['package'],x['tariff_routes'],policy)})
 return out
# Independent SQL expression: route masks, lexical source rules and known vocabulary.
db.execute('CREATE TABLE path_followup(sai TEXT,sl TEXT,tariff TEXT,ingredient TEXT,grp TEXT,package TEXT,va TEXT)');db.executemany('INSERT INTO path_followup VALUES(?,?,?,?,?,?,?)',[(x['sai'],x['sl'],x['tariff'],x['ingredient'],x['grp'],x['package'],x['va']) for x in sqlpaths])
source_mask="""CASE WHEN f='oral' THEN 1 WHEN f='parenteral' THEN
 2*regexp('(?<!\\w)i\\.?\\s*v\\.?(?!\\w)',package)+4*regexp('(?<!\\w)s\\.?\\s*c\\.?(?!\\w)|\\bsubkutan\\b',package)+8*regexp('(?<!\\w)i\\.?\\s*m\\.?(?!\\w)',package)+16*regexp('(?<!\\w)i\\.?\\s*t\\.?(?!\\w)',package) ELSE 0 END"""
route_sql="""WITH family AS (SELECT *,CASE WHEN lower(trim(grp)) LIKE '% oral' OR lower(trim(grp)) LIKE '% oralretard' OR lower(trim(grp)) LIKE '% oralfluessig' OR lower(trim(grp)) LIKE '% oralflüssig' THEN 'oral' WHEN lower(trim(grp)) LIKE '% parenteral' OR lower(trim(grp)) LIKE '% parenteraldepot' THEN 'parenteral' ELSE NULL END f FROM path_followup),
 masks AS (SELECT *,CASE WHEN :policy='coarse' THEN CASE f WHEN 'oral' THEN 1 WHEN 'parenteral' THEN 30 ELSE 0 END
 WHEN :policy='explicit_formulation' AND NOT ((f='oral' AND regexp('\\b(?:filmtabl|tabl|kaps)\\b',package)) OR (f='parenteral' AND regexp('\\b(?:inf|inj|trockensub)\\b',package))) THEN 0 ELSE SOURCE_MASK END sm,
 (SELECT coalesce(sum(DISTINCT CASE trim(value) WHEN 'O' THEN 1 WHEN 'IV' THEN 2 WHEN 'SC' THEN 4 WHEN 'IM' THEN 8 WHEN 'IT' THEN 16 WHEN 'SR' THEN 32 WHEN 'Inhal' THEN 64 WHEN 'ET' THEN 128 ELSE 0 END),0) FROM json_each('['||replace(json_quote(va),',','","')||']')) tm,
 (SELECT count(*) FROM json_each('['||replace(json_quote(va),',','","')||']') WHERE trim(value) NOT IN ('O','IV','SC','IM','IT') AND (:policy='coarse' OR trim(value) NOT IN ('SR','Inhal','ET'))) unknown FROM family)
 SELECT sai,sl,tariff,CASE WHEN sm=0 OR trim(va)='' THEN 'UNDETERMINED' WHEN (sm & tm)>0 THEN 'VERIFIED' WHEN unknown>0 THEN 'UNDETERMINED' ELSE 'CONTRADICTED' END status FROM masks ORDER BY sai,sl,tariff""".replace('SOURCE_MASK',source_mask)
def groups(rows):
 cells=collections.defaultdict(list)
 for x in rows:cells[(x['ingredient_key'],x['tariff_record'])].append(x)
 return [{'ingredient_key':k[0],'tariff_record':k[1],'tariff':xs[0]['tariff'],'status_counts':dict(collections.Counter(x['status'] for x in xs)),'products':sorted({x['product'] for x in xs}),'source_rows':sorted({x['SL_record'] for x in xs}),'paths':sorted(xs,key=lambda x:(x['witness'],x['tariff_record']))} for k,xs in sorted(cells.items())]
profiles={};mixed={};decision_digests={}
for policy in ['coarse','exact_code','explicit_formulation']:
 rows=downstream(g,policy);actual={(x['sai_record'],x['SL_record'],x['tariff_record']):x['status'] for x in rows};expected={(x['sai'],x['sl'],x['tariff']):x['status'] for x in db.execute(route_sql,{'policy':policy})};assert actual==expected,[(k,actual[k],expected.get(k)) for k in actual if actual[k]!=expected.get(k)][:5]
 profiles[policy]=groups(rows);mixed[policy]=[x for x in profiles[policy] if 'VERIFIED' in x['status_counts'] and 'CONTRADICTED' in x['status_counts']];decision_digests[policy]=hashlib.sha256(canon(sorted((list(k),v) for k,v in actual.items())).encode()).hexdigest()
# Remove only the ingredient chain from the original ABox; retain all other inference rules.
ablated=Graph().parse(ontology)
for triple in g:
 if triple[1] in {EX.recordedCode,EX.listedByTariff,EX.ingredientDeclaration,EX.lexicalValue}:ablated.add(triple)
chain=next(ablated.objects(EX.ingredientTariffCandidate,OWL.propertyChainAxiom));ablated.remove((EX.ingredientTariffCandidate,OWL.propertyChainAxiom,None));DeductiveClosure(OWLRL_Semantics).expand(ablated)
assert not inferred_pairs(ablated) and not downstream(ablated,'exact_code') and documentary(ablated)==full_docs
ablated.add((EX.ingredientTariffCandidate,OWL.propertyChainAxiom,chain));DeductiveClosure(OWLRL_Semantics).expand(ablated);assert inferred_pairs(ablated)==full_pairs and groups(downstream(ablated,'exact_code'))==profiles['exact_code']
key=lambda x:(x['ingredient_key'],x['tariff_record'])
sets={p:{key(x) for x in mixed[p]} for p in mixed}
summary={'protocol_sha256':protocol_sha,'protocol_frozen_utc':protocol['fixed_before_first_followup_execution_utc'],'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_paths':len(paths),'inferred_ingredient_tariff_pairs':len(full_pairs),'ingredient_source_rows':len({x['SL_record'] for x in paths}),'declaration_tariff_groups':len(profiles['exact_code']),'distinct_normalized_declarations':len({x['ingredient_key'] for x in paths}),'mixed_groups':{p:len(mixed[p]) for p in mixed},'exact_and_formulation_mixed':len(sets['exact_code']&sets['explicit_formulation']),'new_exact_mixed_vs_coarse':len(sets['exact_code']-sets['coarse']),'source_SQL_pair_agreement':True,'independent_SQL_route_decision_agreement':True,'decision_digests':decision_digests,'no_materialization_derived_pairs':0,'ingredient_chain_ablation_derived_pairs':0,'documentary_predicates_preserved_by_ablation':len(full_docs),'restoration_full_output_agreement':True,'interpretation':protocol['interpretation'],'profiles':{p:[{k:v for k,v in x.items() if k!='paths'} for x in profiles[p]] for p in profiles},'selected_groups':mixed,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
if args.neo4j_url:
 from native_followup import verify_native
 summary['native_neo4j']=verify_native(args.neo4j_url,protocol_sha,paths,profiles,full_pairs)
(R/'results').mkdir(exist_ok=True);(R/'queries').mkdir(exist_ok=True);(R/'results/ingredient_followup.json').write_text(json.dumps(summary,indent=2)+'\n');(R/'queries/ingredient_followup.sql').write_text(base_sql+';\n\n'+route_sql+';\n')
print(json.dumps({k:v for k,v in summary.items() if k not in {'profiles','selected_groups'}},indent=2))
for x in mixed['exact_code']:print(x['ingredient_key'],x['tariff'],x['status_counts'],len(x['products']))
