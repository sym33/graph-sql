"""External classification-compatibility census; matching excludes the asserted ATC."""
import json,csv,hashlib,unicodedata,collections,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PACKAGE=ROOT.parent;OUT=ROOT/'results'
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s or '').casefold().split())
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
class ExternalReference:
 def __init__(self):
  self.status=json.loads((ROOT/'raw/chembl_status.json').read_text());self.molecules={};self.preferred=collections.defaultdict(set);self.synonyms=collections.defaultdict(set);self.parents=collections.defaultdict(list)
  for path in sorted((ROOT/'raw').glob('chembl_molecules_*.json')):
   for m in json.loads(path.read_text())['molecules']:
    mid=m['molecule_chembl_id'];self.molecules[mid]=m;parent=(m.get('molecule_hierarchy') or {}).get('parent_chembl_id') or mid;self.parents[parent].append(m)
    if norm(m.get('pref_name')):self.preferred[norm(m['pref_name'])].add(parent)
    for syn in m.get('molecule_synonyms') or []:
     name=norm(syn.get('molecule_synonym') or syn.get('synonyms'))
     if name:self.synonyms[name].add(parent)
  self.changes=json.loads((PACKAGE/'Thesis_Recovery/results/WHO_full_code_alterations.json').read_text())
 def assess(self,substance,code):
  name=norm(substance);result={'substance':substance,'asserted_atc':code,'reference_release':self.status['chembl_db_version'],'identity_resolution_uses_atc':False}
  if not name or name in ['na','n/a']:return {**result,'status':'UNRESOLVED','reason':'missing_substance'}
  if ';' in name:return {**result,'status':'UNRESOLVED','reason':'multi_component_not_resolved'}
  parents=self.preferred.get(name,set());tier='exact_preferred_name'
  if not parents:parents=self.synonyms.get(name,set());tier='exact_synonym'
  result.update(identity_tier=tier,candidate_parents=sorted(parents))
  if not parents:return {**result,'status':'UNRESOLVED','reason':'not_matched_in_ATC_bearing_collection'}
  if len(parents)!=1:return {**result,'status':'UNRESOLVED','reason':'ambiguous_parent_identity'}
  parent=next(iter(parents));members=self.parents[parent];codes=sorted({c for m in members for c in m.get('atc_classifications',[])})
  result.update(parent_chembl_id=parent,reference_atc_codes=codes,reference_molecules=[{'id':m['molecule_chembl_id'],'preferred_name':m.get('pref_name'),'codes':m.get('atc_classifications',[])} for m in members])
  if not code or norm(code) in ['na','n/a','not yet assigned']:return {**result,'status':'UNRESOLVED','reason':'missing_or_unassigned_staged_ATC'}
  tokens=sorted(set(t.strip() for t in code.split(';') if t.strip()))
  legal=lambda t:bool(re.fullmatch(r'[ABCDGHJLMNPRSV](?:[0-9]{2}(?:[A-Z](?:[A-Z](?:[0-9]{2})?)?)?)?',t))
  if any(not legal(t) for t in tokens):return {**result,'status':'MALFORMED_CODE_REVIEW_REQUIRED','reason':'invalid_ATC_level_encoding','asserted_code_tokens':tokens}
  def compare(t):
   if t in codes:return {'token':t,'status':'EXACT_EXTERNAL_SUPPORT','reference_codes':[t]}
   descendants=[c for c in codes if len(t)<7 and c.startswith(t)]
   if descendants:return {'token':t,'status':'HIERARCHICAL_EXTERNAL_COMPATIBILITY','reference_codes':descendants}
   forward=[c for c in self.changes if c['old']==t and c['new'] in codes and norm(c['substance'])==name]
   reverse=[c for c in self.changes if c['new']==t and c['old'] in codes and norm(c['substance'])==name]
   if forward:return {'token':t,'status':'WHO_FORWARD_RECONCILIATION','official_changes':forward}
   if reverse:return {'token':t,'status':'WHO_REVERSE_RECONCILIATION','official_changes':reverse}
   historical=[c for c in self.changes if len(t)<7 and c['old'].startswith(t) and c['new'] in codes and norm(c['substance'])==name]
   if historical:return {'token':t,'status':'WHO_HIERARCHICAL_RECONCILIATION','official_changes':historical}
   return {'token':t,'status':'DISCORDANT_REVIEW_REQUIRED'}
  components=[compare(t) for t in tokens];statuses={c['status'] for c in components};result['code_comparisons']=components
  if len(statuses)==1:status=next(iter(statuses))
  elif 'DISCORDANT_REVIEW_REQUIRED' in statuses:status='PARTIAL_MULTI_CODE_SUPPORT'
  else:status='MIXED_EXTERNAL_COMPATIBILITY'
  return {**result,'status':status,'reason':'granularity_and_version_aware_external_comparison'}

def run():
 ext=ExternalReference();path=PACKAGE/'input/silver/ema_products.csv';filehash=hashlib.sha256(path.read_bytes()).hexdigest();rows=[]
 with path.open(encoding='utf-8-sig',newline='') as f:
  for ordinal,payload in enumerate(csv.DictReader(f,delimiter='|',escapechar='\\'),1):
   r=ext.assess(payload['substance'],payload['atc']);r.update(record_id=f'ema_products.csv:{filehash}:record:{ordinal}',product=payload['product_name'],product_url=payload['url'],source_file_sha256=filehash)
   r['decision_id']=digest(r);rows.append(r)
 unique={ (norm(r['substance']),r['asserted_atc']):r for r in rows};names={norm(r['substance']) for r in rows}
 def summarize(items):
  return {'n':len(items),'status_counts':dict(collections.Counter(r['status'] for r in items)),'reason_counts':dict(collections.Counter(r['reason'] for r in items)),'identity_tiers':dict(collections.Counter(r.get('identity_tier','not_attempted') for r in items if r.get('parent_chembl_id')))}
 summary={'reference_status':ext.status,'reference_molecules':len(ext.molecules),'reference_parent_families':len(ext.parents),'population':'complete frozen EMA staging census','row_level':summarize(rows),'unique_substance_ATC_level':summarize(list(unique.values())),'unique_substance_names':len(names),'decision_scope':'external substance-level compatibility; discordance is not product-level falsity; no clinical gold precision estimate','analysis_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256((ROOT/'PROTOCOL.json').read_bytes()).hexdigest()}
 with (OUT/'external_classification_decisions.jsonl').open('w') as f:
  for r in rows:f.write(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n')
 (OUT/'external_validation_summary.json').write_text(json.dumps(summary,indent=2));(OUT/'discordant_cases.json').write_text(json.dumps([r for r in rows if r['status']=='DISCORDANT_REVIEW_REQUIRED'],indent=2,ensure_ascii=False));(OUT/'temporal_cases.json').write_text(json.dumps([r for r in rows if r['status'].startswith('WHO_') or any(c['status'].startswith('WHO_') for c in r.get('code_comparisons',[]))],indent=2,ensure_ascii=False));print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
