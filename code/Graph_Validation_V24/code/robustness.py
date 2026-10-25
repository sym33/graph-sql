"""Protocol-bound source-path and route-policy robustness over complete candidates."""
from pathlib import Path
import collections,datetime,gzip,hashlib,json,sys,subprocess,importlib.util,re
R=Path(__file__).resolve().parents[1];P=R.parent
sys.path[:0]=[str(P/'Validation_Study/code'),str(P/'Graph_Validation_V17/code'),str(P/'Graph_Validation_V21/code')]
from reference_oracle import Reference
from route_policies import assess
from route_assertions import extract
canon=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protocol=json.loads((R/'ROBUSTNESS_PROTOCOL.json').read_text())
for p,h in protocol['inputs'].items():assert sha(P/p)==h
ref=Reference(P/'Graph_Validation_V9/temporal_snapshot');tariffs={k:v for k,v in ref.records.items() if k.startswith('ze_definitions.csv:')};index=collections.defaultdict(list)
for rid,t in tariffs.items():index[t['code']].append(rid)
physical=json.loads(gzip.decompress((P/'Graph_Validation_V9/results/temporal_physical_bundles.json.gz').read_bytes()))
paths=[]
for b in physical:
 a=b['association']
 if a['jurisdiction']!='CH' or a['rule'] not in {'direct_SAI','via_authorization_SL'}:continue
 assert b['products']==[a['subject']] and b['targets']==[a['atc']]
 for tid in index[a['atc']]:
  premises={x['id']:json.loads(x['payload_json']) for x in b['records']}
  assert premises=={rid:ref.records[rid] for rid in ref.witnesses[a['id']]['premise_ids']}
  sl=next(((rid,p) for rid,p in premises.items() if rid.startswith('sl.csv:')),None)
  paths.append({'product':a['subject'],'tariff_record':tid,'tariff':tariffs[tid]['ze_code'],'tariff_route':tariffs[tid]['va'],'rule':a['rule'],'witness':a['id'],'code':a['atc'],'premise_ids':sorted(premises),'SL_record':sl[0] if sl else None,'package':sl[1]['bezeichnung'] if sl else None,'group':sl[1]['gammenbezeichnung'] if sl else None,'ingredient':sl[1]['substanzen'] if sl else None})
# Independent relational query obtains source support and pair population directly from CSV tables.
db=ref.db;db.execute('CREATE TABLE tariffs(rid TEXT,code TEXT)');db.executemany('INSERT INTO tariffs VALUES(?,?)',[(k,v['code']) for k,v in tariffs.items()])
SQL="""SELECT DISTINCT d.subject product,t.rid tariff_record,d.rule FROM derivations d JOIN tariffs t ON d.code=t.code WHERE d.jurisdiction='CH' AND d.rule IN ('direct_SAI','via_authorization_SL')"""
expected={tuple(x) for x in db.execute(SQL)};actual={(x['product'],x['tariff_record'],x['rule']) for x in paths};assert actual==expected
cells=collections.defaultdict(list)
for x in paths:cells[(x['product'],x['tariff_record'])].append(x)
policies=protocol['policies'];profiles=[]
for (product,tid),xs in sorted(cells.items()):
 rules={x['rule'] for x in xs};source='both_classification_paths' if len(rules)==2 else 'SAI_ATC_only' if 'direct_SAI' in rules else 'SL_ATC_only'
 sl=[x for x in xs if x['SL_record']];counts={p:dict(collections.Counter(assess(x['group'],x['package'],x['tariff_route'],p) for x in sl)) for p in policies}
 status={p:'VERIFIED' if c.get('VERIFIED',0) else 'CONTRADICTED' if sl and c.get('CONTRADICTED',0)==len(sl) else 'UNDETERMINED' for p,c in counts.items()}
 values=set(status.values());category='stable_supported' if values=={'VERIFIED'} else 'stable_conflict' if values=={'CONTRADICTED'} else 'unavailable_all' if values=={'UNDETERMINED'} else 'policy_sensitive'
 any_conflict=any(c.get('CONTRADICTED',0) for c in counts.values());any_unknown=any(c.get('UNDETERMINED',0) for c in counts.values())
 profiles.append({'product':product,'tariff_record':tid,'tariff':xs[0]['tariff'],'source_support':source,'route_category':category,'aggregate_status':status,'package_status_counts':counts,'strong_robustness':source=='both_classification_paths' and category=='stable_supported' and not any_conflict,'any_conflicting_package':any_conflict,'any_undetermined_package':any_unknown,'packages':len(sl),'witnesses':sorted({x['witness'] for x in xs}),'premise_ids':sorted({p for x in xs for p in x['premise_ids']}|{tid})})
# V23 uses separately expressed SQL route rules; compare its full-path digests.
follow=json.loads((P/'Graph_Validation_V23/results/ingredient_followup.json').read_text())
for p in policies:
 rows=[x for x in paths if x['SL_record'] and ' '.join(x['ingredient'].strip().casefold().split()) not in {'','na','n/a','null','none','nan'}]
 decisions={ (next(i for i in x['premise_ids'] if i.startswith('sai_praeparate.csv:')),x['SL_record'],x['tariff_record']):assess(x['group'],x['package'],x['tariff_route'],p) for x in rows}
 digest=hashlib.sha256(canon(sorted((list(k),v) for k,v in decisions.items())).encode()).hexdigest();assert digest==follow['decision_digests'][p]
full=set(cells);direct={(x['product'],x['tariff_record']) for x in paths if x['rule']=='direct_SAI'};slset={(x['product'],x['tariff_record']) for x in paths if x['rule']=='via_authorization_SL'}
assert direct|slset==full and len(full)==564
# Classification-path ablation; the authorization identity bridge stays available.
ablation={'remove_SL_classification_path':{'retained_pairs':len(direct),'lost_pairs':len(full-direct)},'remove_SAI_classification_path':{'retained_pairs':len(slset),'lost_pairs':len(full-slset)}}
who=json.loads((P/'Thesis_Recovery/results/WHO_full_code_alterations.json').read_text());explanations=[]
for product,tid in sorted(full-direct):
 direct_codes={w['atc'] for w in ref.witnesses.values() if w['subject']==product and w['rule']=='direct_SAI'};hits=[x for x in who if x['old'] in direct_codes and x['new']==tariffs[tid]['code']];assert hits
 explanations.append({'product':product,'tariff':tariffs[tid]['ze_code'],'tariff_record':tid,'WHO_alterations':hits,'scope':'Classification alteration corroboration; not Swiss current authorization or billing eligibility.'})
# Full SmPC census of a newly retrieved official EMA document, bound to section 4.2.
spec=importlib.util.spec_from_file_location('section_reader',P/'Graph_Validation_V17/code/section_documents.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
pdf=R/'external/vfend.pdf';text=subprocess.check_output(['pdftotext','-enc','UTF-8','-layout',str(pdf),'-']).decode();blocks=m.blocks(text);documents=[]
for b in blocks:
 method=b['administration'].rsplit('Method of administration',1)[-1];assessment=extract(method)
 documents.append({'title':b['title'],'administration_pages':b['PDF_pages_administration'],'assessment':assessment,'method_sha256':hashlib.sha256(method.encode()).hexdigest(),'title_sha256':hashlib.sha256(b['title'].encode()).hexdigest()})
assert blocks and all('vfend' in b['title'].casefold() for b in blocks)
# Supplementary label-field extraction added after inspecting this document; reported separately.
def label_blocks(text):
 starts=list(re.finditer(r'(?:^|\n)\s*1\. NAME OF THE MEDICINAL PRODUCT\s*\n',text));out=[]
 for i,m in enumerate(starts):
  end=starts[i+1].start() if i+1<len(starts) else len(text);part=text[m.end():end]
  s2=re.search(r'2\. STATEMENT OF ACTIVE SUBSTANCE',part);s5=re.search(r'5\. METHOD AND ROUTE\(S\) OF ADMINISTRATION',part);s6=re.search(r'6\. SPECIAL WARNING',part)
  if not(s2 and s5 and s6 and s2.start()<s5.start()<s6.start()):continue
  field=' '.join(part[s5.end():s6.start()].split());title=' '.join(part[:s2.start()].split())
  # Match complete positive route lines in the designated label field only.
  raw=part[s5.end():s6.start()];routes=[]
  for token,pat in [('O',r'^\s*Oral use(?: after constitution)?\.?\s*$'),('IV',r'^\s*Intravenous use\.?\s*$')]:
   if re.search(pat,raw,re.M|re.I):routes.append(token)
  out.append({'title':title,'route_field':field,'routes':routes,'pdf_page':text[:m.end()].count('\f')+1,'field_sha256':hashlib.sha256(field.encode()).hexdigest()})
 return out
labels=label_blocks(text);assert len(labels)==5 and all(len(x['routes'])==1 for x in labels)
assert collections.Counter(x['routes'][0] for x in labels)=={'O':4,'IV':1}
fixture='1. NAME OF THE MEDICINAL PRODUCT\nTest\n2. STATEMENT OF ACTIVE SUBSTANCE(S)\nx\n5. METHOD AND ROUTE(S) OF ADMINISTRATION\nNot for oral use.\n6. SPECIAL WARNING\nOral use\n'
assert label_blocks(fixture)[0]['routes']==[]
assert label_blocks(fixture.replace('6. SPECIAL WARNING','missing boundary'))==[]
external={'url':'https://www.ema.europa.eu/en/documents/product-information/vfend-epar-product-information_en.pdf','pdf_sha256':sha(pdf),'retrieved_utc':json.loads((R/'external/retrieval.json').read_text())['retrieved_utc'],'label_field_analysis':'Exploratory extension after document inspection; complete five-field census, separate from prospective SmPC analysis.','label_fields':labels,'label_fields_with_explicit_routes':len(labels),'label_boundary_controls_passed':2,'full_formulation_blocks':len(documents),'explicit_positive_blocks':sum(x['assessment']['status']=='explicit' for x in documents),'records':documents,'scope':'EU branded formulation context only; no generic-product identity substitution and no Swiss tariff eligibility assertion.'}
by_source={source:dict(collections.Counter(x['route_category'] for x in profiles if x['source_support']==source)) for source in protocol['source_axes']}
summary={'protocol_sha256':sha(R/'ROBUSTNESS_PROTOCOL.json'),'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pairs':len(profiles),'proof_paths':len(paths),'source_support_counts':dict(collections.Counter(x['source_support'] for x in profiles)),'route_category_counts':dict(collections.Counter(x['route_category'] for x in profiles)),'source_by_route':by_source,'strong_robustness_pairs':sum(x['strong_robustness'] for x in profiles),'strong_robustness_with_complete_routes':sum(x['strong_robustness'] and not x['any_undetermined_package'] for x in profiles),'stable_supported_with_conflicting_packages':sum(x['route_category']=='stable_supported' and x['any_conflicting_package'] for x in profiles),'policy_status_counts':{p:dict(collections.Counter(x['aggregate_status'][p] for x in profiles)) for p in policies},'source_path_ablation':ablation,'source_SQL_physical_agreement':True,'independently_verified_route_digests_agree':True,'WHO_recovered_candidates':explanations,'EMA_vfend':external,'profiles':profiles,'code_sha256':sha(Path(__file__))}
(R/'results').mkdir(exist_ok=True);(R/'queries').mkdir(exist_ok=True);(R/'results/robustness.json').write_text(json.dumps(summary,indent=2)+'\n');(R/'queries/source_support.sql').write_text(SQL+';\n')
print(json.dumps({k:v for k,v in summary.items() if k not in {'profiles','WHO_recovered_candidates','EMA_vfend'}},indent=2));print('EMA SmPC blocks:',len(documents),'prior-parser explicit blocks:',external['explicit_positive_blocks'],'label fields:',len(labels))
