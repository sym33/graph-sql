"""Frozen-cohort documentary route transfer; no clinical substitution inference."""
from pathlib import Path
import csv,collections,hashlib,json,re,sqlite3,subprocess,sys
R=Path(__file__).resolve().parents[1]; P=R.parent
sys.path[:0]=[str(P/'Graph_Validation_V17/code'),str(P/'Graph_Validation_V21/code')]
from section_documents import blocks
from route_assertions import extract
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protocol=json.loads((R/'TRANSFER_PROTOCOL.json').read_text()); retrieval=json.loads((R/'external/retrieval.json').read_text())
source=P/'Graph_Validation_V9/temporal_snapshot/input/silver/ema_products.csv'
assert sha(source)==protocol['source_sha256']
with source.open(newline='',encoding='utf-8-sig') as handle:
 cohort=[(i,row['product_name'],row['url']) for i,row in enumerate(csv.DictReader(handle,delimiter="|"),1) if row['atc']=='L04AC07']
assert cohort==[(m['ordinal'],m['name'],m['page_url']) for m in protocol['cohort']]
heading=re.compile(r'^\s*5\.\s*METHOD AND ROUTE(?:\(S\))? OF ADMINISTRATION\s*$',re.M)
closing=re.compile(r'^\s*6\.\s*SPECIAL WARNING',re.M)
title=re.compile(r'^\s*1\.\s*NAME OF THE MEDICINAL PRODUCT\s*$',re.M)
second=re.compile(r'^\s*2\.\s*(?:STATEMENT OF ACTIVE|QUALITATIVE)',re.M)
patterns={'IV':r'(?:for )?intravenous (?:infusion|use)(?: after dilution)?','SC':r'(?:for )?subcutaneous (?:use|injection)(?: only)?','IM':r'(?:for )?intramuscular (?:use|injection)','IT':r'(?:for )?intrathecal (?:use|injection)','O':r'(?:for )?oral use'}
medicines=[]; fields=[]
for item in retrieval:
 assert item['status']=='retrieved', 'Unavailable documents must be accounted for before a complete census claim'
 pdf=R/'external'/f"{item['slug']}.pdf";assert sha(pdf)==item['pdf_sha256']
 text=subprocess.check_output(['pdftotext','-enc','UTF-8','-layout',str(pdf),'-']).decode('utf-8'); found=[]
 for i,m in enumerate(heading.finditer(text)):
  end=closing.search(text,m.end());assert end,'Incomplete scoped field'
  previous=list(title.finditer(text,0,m.start()));assert previous,'Unbound label title'
  begin=previous[-1].end(); boundary=second.search(text,begin);assert boundary and boundary.start()<m.start()
  name=' '.join(text[begin:boundary.start()].split());value=text[m.end():end.start()]
  routes=sorted({r for r,pat in patterns.items() for line in value.splitlines() if re.fullmatch(pat,line.strip().lower().rstrip('.'))})
  assert routes,'Scoped field lacks a recognized positive route; preserve and investigate before census interpretation'
  f={'id':item['slug']+':label5:'+str(i+1),'medicine':item['page_url'],'title':name,'page':text[:m.start()].count('\f')+1,'field':value.strip(),'routes':routes,'pdf_sha256':item['pdf_sha256'],'url':item['pdf_url']};found.append(f);fields.append(f)
 assert found
 codes=sorted(set(re.findall(r'ATC\s+code\s*:\s*([A-Z]\d{2}[A-Z]{2}\d{2})',text,re.I)))
 assert codes==[item['ATC']]
 parsed=set();block_details=[]
 for b in blocks(text):
  a=b['administration'].rsplit('Method of administration',1)[-1];result=extract(a)
  parsed.update(result['positive_routes']);block_details.append(result)
 routes=sorted({x for f in found for x in f['routes']})
 medicines.append({'name':item['name'],'id':item['page_url'],'ATC':item['ATC'],'reference_ATC':codes,'routes':routes,'label_fields':len(found),'old_matcher_routes':sorted(parsed),'old_matcher_blocks':len(block_details),'missing_old_matcher_routes':sorted(set(routes)-parsed),'pdf_sha256':item['pdf_sha256']})
assert len(medicines)==len(protocol['cohort'])==5
# Independent relational construction uses source cohort codes and normalized label rows.
db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE medicines(id TEXT,atc TEXT);CREATE TABLE routes(id TEXT,route TEXT);')
db.executemany('INSERT INTO medicines VALUES(?,?)',[(m['id'],m['ATC']) for m in medicines]);db.executemany('INSERT INTO routes VALUES(?,?)',sorted({(f['medicine'],r) for f in fields for r in f['routes']}))
query='SELECT DISTINCT a.id,b.id,r.route FROM medicines a JOIN medicines b ON a.atc=b.atc AND a.id<>b.id JOIN routes r ON r.id=a.id ORDER BY a.id,b.id,r.route'
keys=list(db.execute(query));inventory={m['id']:set(m['routes']) for m in medicines}
family=lambda r:'oral' if r=='O' else 'parenteral'
assess=lambda r,target:'UNDETERMINED' if not target else 'VERIFIED' if r in target else 'CONTRADICTED'
rows=[{'source':a,'target':b,'route':r,'exact':assess(r,inventory[b]),'coarse':assess(family(r),{family(x) for x in inventory[b]})} for a,b,r in keys]
assert all(assess(r,set())=='UNDETERMINED' for a,b,r in keys)
summary={'protocol_sha256':sha(R/'TRANSFER_PROTOCOL.json'),'medicines':medicines,'label_fields':len(fields),'medicine_route_edges':sum(len(m['routes']) for m in medicines),'candidate_keys':len(rows),'exact':dict(collections.Counter(x['exact'] for x in rows)),'coarse':dict(collections.Counter(x['coarse'] for x in rows)),'ATC_comparisons':len(medicines),'ATC_agreements':sum(m['reference_ATC']==[m['ATC']] for m in medicines),'missing_reference_intervention_UNDETERMINED':len(rows),'existing_matcher_missing_routes':sum(len(m['missing_old_matcher_routes']) for m in medicines),'rows':rows,'fields':fields,'SQL':query}
(R/'results').mkdir(exist_ok=True);(R/'results/transfer.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k not in {'rows','fields','SQL','medicines'}},indent=2))
