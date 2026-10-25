from pathlib import Path
import sys,argparse,json,collections,hashlib,copy
from rdflib import Graph,Namespace,RDF,Literal,URIRef
from owlrl import DeductiveClosure,OWLRL_Semantics
from pyshacl import validate
from route_context import package_family,decide,ROUTE_FAMILIES
R=Path(__file__).resolve().parents[1];P=R.parent
ap=argparse.ArgumentParser();ap.add_argument('--data-root',type=Path,default=P);D=ap.parse_args().data_root
sys.path.insert(0,str(P/'Validation_Study/code'));from reference_oracle import Reference
ref=Reference(D/'Graph_Validation_V9/temporal_snapshot')
EX=Namespace('https://example.org/medigraph/evidence/')
def uri(kind,value):return URIRef(str(EX)+kind+'/'+hashlib.sha256(value.encode()).hexdigest())
base=json.loads((D/'Graph_Validation_V15/results/documentary_candidates.json').read_text());rows=[]
g=Graph().parse(D/'Graph_Validation_V15/results/inference_input.ttl');g.parse(R/'ontology/route_extension.ttl')
glossary={rid:r for rid,r in ref.records.items() if rid.startswith('technisches_begleitblatt.csv:') and r['sprache']=='de' and r['variablenname']=='medi_verabreichungsart'}
byroute={r['kuerzel']:rid for rid,r in glossary.items()};assert all(x in byroute for x in ROUTE_FAMILIES)
for x in base:
 a=ref.witnesses[x['witness']];assert (a['subject'],a['atc'],a['rule'])==(x['product'],x['code'],x['rule'])
 assert sorted(a['premise_ids']+[x['tariff_record']])==x['premise_ids']
 assert ref.records[x['tariff_record']]['code']==x['code']
 if x['rule']!='via_authorization_SL':continue
 sl_ids=[p for p in x['premise_ids'] if p.startswith('sl.csv:')];assert len(sl_ids)==1;rid=sl_ids[0];sl=ref.records[rid];t=ref.records[x['tariff_record']]
 status=decide(sl['gammenbezeichnung'],t['va']);family=package_family(sl['gammenbezeichnung']);tokens=t['va'].split(',')
 item={**x,'SL_record':rid,'package':sl['bezeichnung'],'recorded_group':sl['gammenbezeichnung'],'tariff_routes':t['va'],'route_family':family,'target':'coarse_package_route_compatibility','status':status,'premise_ids':sorted(set(x['premise_ids']+[byroute[v] for v in tokens if v in byroute])),'route_policy_sha256':hashlib.sha256((R/'code/route_context.py').read_bytes()).hexdigest()};rows.append(item)
 if family:g.add((uri('witness',x['witness']),EX.recordedOralCode if family=='oral' else EX.recordedParenteralCode,uri('code',x['code'])))
for rid,t in ref.records.items():
 if not rid.startswith('ze_definitions.csv:'):continue
 for family in {ROUTE_FAMILIES[x] for x in t['va'].split(',') if x in ROUTE_FAMILIES}:
  g.add((uri('code',t['code']),EX.listedByOralTariff if family=='oral' else EX.listedByParenteralTariff,uri('tariff',rid)))
# Fully separate SQL expression uses source suffixes and comma-delimited tariff fields.
ref.db.execute('CREATE TABLE tariffs(rid TEXT,code TEXT,va TEXT)');ref.db.executemany('INSERT INTO tariffs VALUES(?,?,?)',[(rid,x['code'],x['va']) for rid,x in ref.records.items() if rid.startswith('ze_definitions.csv:')])
sql="""WITH matched AS (
 SELECT DISTINCT s.rid sai,l.rid sl,t.rid tariff,lower(trim(json_extract(i.payload,'$.gammenbezeichnung'))) g,t.va routes
 FROM sai s JOIN sl l ON s.auth=l.auth JOIN input i ON i.rid=l.rid JOIN tariffs t ON l.code=t.code),
 families AS (SELECT *,CASE WHEN g LIKE '% oral' OR g LIKE '% oralretard' OR g LIKE '% oralfluessig' OR g LIKE '% oralflüssig' THEN 'oral'
 WHEN g LIKE '% parenteral' OR g LIKE '% parenteraldepot' THEN 'parenteral' ELSE NULL END family FROM matched)
 SELECT sai,sl,tariff,CASE WHEN family IS NULL THEN 'UNDETERMINED'
 WHEN family='oral' AND EXISTS(SELECT 1 FROM json_each('['||replace(json_quote(routes),',','","')||']') WHERE trim(value)='O') THEN 'VERIFIED'
 WHEN family='parenteral' AND EXISTS(SELECT 1 FROM json_each('['||replace(json_quote(routes),',','","')||']') WHERE trim(value) IN ('IV','SC','IM','IT')) THEN 'VERIFIED'
 WHEN EXISTS(SELECT 1 FROM json_each('['||replace(json_quote(routes),',','","')||']') WHERE trim(value) NOT IN ('O','IV','SC','IM','IT')) THEN 'UNDETERMINED'
 ELSE 'CONTRADICTED' END status FROM families"""
(R/'queries/route_context.sql').write_text(sql+';\n')
expected={(x['sai'],x['sl'],x['tariff']):x['status'] for x in ref.db.execute(sql)}
actual={tuple([next(p for p in x['premise_ids'] if p.startswith('sai_praeparate.csv:')),x['SL_record'],x['tariff_record']]):x['status'] for x in rows};assert actual==expected,(len(actual),len(expected))
# Preserve pre-existing inference output regression, then evaluate the new predicates.
DeductiveClosure(OWLRL_Semantics).expand(g)
positive={(str(uri('witness',x['witness'])),str(uri('tariff',x['tariff_record']))) for x in rows if x['status']=='VERIFIED'}
observed={(str(s),str(o)) for s,o in g.subject_objects(EX.routeCompatibleTariff)};assert observed==positive
original=Graph().parse(D/'Graph_Validation_V15/results/inference_closure.ttl')
regression={}
for p in [EX.documentaryTariff,EX.historicalTariff,EX.recordedBroaderGroup,EX.ingredientTariffCandidate]:
 a={(str(s),str(o)) for s,o in g.subject_objects(p)};b={(str(s),str(o)) for s,o in original.subject_objects(p)};assert a==b;regression[str(p).split('/')[-1]]=len(a)
# Selection units are kept distinct from derivation and package counts.
status_groups=collections.defaultdict(set)
for x in rows:status_groups[(x['product'],x['tariff_record'])].add(x['status'])
cohort_status={pair:('VERIFIED' if 'VERIFIED' in vals else ('CONTRADICTED' if vals=={'CONTRADICTED'} else 'UNDETERMINED')) for pair,vals in status_groups.items()}
# Target changes leave every documentary candidate intact.
assert len({(x['product'],x['tariff_record']) for x in base})==564
probes=[('Drug Oral','IV','CONTRADICTED'),('Drug Parenteral','O','CONTRADICTED'),('Drug Oral','IV,O','VERIFIED'),('Drug Parenteral','IV,Inhal','VERIFIED'),('Drug Parenteral','SR','UNDETERMINED'),('Drug Inhalation','IV,Inhal','UNDETERMINED'),('Drug TopischOral','O','UNDETERMINED'),('Drug Oral','OIV','UNDETERMINED'),('Drug Oral','','UNDETERMINED')]
for group,routes,status in probes:assert decide(group,routes)==status
(R/'results/route_policy_controls.json').write_text(json.dumps([{'group':a,'routes':b,'expected':c,'actual':decide(a,b)} for a,b,c in probes],indent=2))
# Certificate shape for every new assessment, including abstentions and conflicts.
shapes=Graph().parse(data='''@prefix ex: <https://example.org/medigraph/evidence/> . @prefix sh: <http://www.w3.org/ns/shacl#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:RouteShape a sh:NodeShape ; sh:targetClass ex:RouteAssessment ; sh:property [sh:path ex:witness ; sh:minCount 1 ; sh:maxCount 1] ; sh:property [sh:path ex:tariffRecord ; sh:minCount 1 ; sh:maxCount 1] ; sh:property [sh:path ex:premise ; sh:minCount 3] ; sh:property [sh:path ex:policy ; sh:minCount 1 ; sh:maxCount 1] ; sh:property [sh:path ex:status ; sh:in ('VERIFIED' 'CONTRADICTED' 'UNDETERMINED') ; sh:minCount 1 ; sh:maxCount 1] .''',format='turtle')
shapes.serialize(R/'ontology/route_shapes.ttl',format='turtle');cert=Graph()
for x in rows:
 n=uri('route-assessment',x['witness']+x['tariff_record']);cert.add((n,RDF.type,EX.RouteAssessment));cert.add((n,EX.witness,uri('witness',x['witness'])));cert.add((n,EX.tariffRecord,uri('tariff',x['tariff_record'])));cert.add((n,EX.policy,Literal(x['route_policy_sha256'])));cert.add((n,EX.status,Literal(x['status'])))
 for p in x['premise_ids']:cert.add((n,EX.premise,uri('source',p)))
assert validate(cert,shacl_graph=shapes)[0]
# Declarative ontology extension contract counts: two chains, four input properties, one output property.
summary={'evaluated_witness_tariff_cases':len(rows),'decisions':dict(collections.Counter(x['status'] for x in rows)),'SL_package_rows':len({x['SL_record'] for x in rows}),'SL_supported_product_tariff_pairs':len(status_groups),'route_cohort_decisions':dict(collections.Counter(cohort_status.values())),'documentary_candidates_without_SL_route_context':564-len(status_groups),'route_policy_controls_passed':len(probes),'product_tariff_pairs_with_compatible_package':len({(x['product'],x['tariff_record']) for x in rows if x['status']=='VERIFIED'}),'product_tariff_pairs_with_only_conflicting_packages':len({(x['product'],x['tariff_record']) for x in rows if x['status']=='CONTRADICTED'}-{(x['product'],x['tariff_record']) for x in rows if x['status']!='CONTRADICTED'}),'SQL_complete_decision_agreement':True,'OWL_complete_positive_set_agreement':True,'SHACL_all_certificates_conform':True,'existing_rule_output_regression':regression,'new_source_role':'technical companion route glossary, previously retained context','extension_interface':{'new_source_projection':1,'new_input_properties':4,'new_output_properties':1,'new_property_chains':2,'new_certificate_shape':1,'changed_V15_rule_files':0},'scope':'Explicit coarse source-group policy; no exact authorized route, Swiss product identity adjudication or payment eligibility claim.'}
(R/'results/route_decisions.json').write_text(json.dumps(rows,indent=2));(R/'results/route_summary.json').write_text(json.dumps(summary,indent=2));g.serialize(R/'results/route_closure.ttl',format='turtle');print(json.dumps(summary,indent=2))
