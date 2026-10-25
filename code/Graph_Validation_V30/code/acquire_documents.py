"""Acquire every official English product-information document in the frozen cohort."""
from pathlib import Path
import concurrent.futures,datetime,gzip,hashlib,html,json,re,ssl,urllib.request,urllib.parse
import certifi
TLS=ssl.create_default_context(cafile=certifi.where())
R=Path(__file__).resolve().parents[1]
protocol=json.loads((R/'PROTOCOL.json').read_text())
def acquire(item):
 page=item['page_url'];slug=page.rstrip('/').split('/')[-1];row={**item,'slug':slug,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  request=urllib.request.Request(page,headers={'User-Agent':'Mozilla/5.0 (academic reproducibility study)'})
  with urllib.request.urlopen(request,timeout=90,context=TLS) as response:body=response.read();row['page_final_url']=response.url
  (R/'external'/f'{slug}.html.gz').write_bytes(gzip.compress(body,mtime=0));row['page_sha256']=hashlib.sha256(body).hexdigest()
  links=sorted(set(urllib.parse.urljoin(page,html.unescape(x)) for x in re.findall(r'href=[\"\x27]([^\"\x27]*product-information[^\"\x27]*_en\.pdf)[\"\x27]',body.decode('utf-8',errors='replace'),re.I)))
  assert len(links)==1,f'Expected one English product-information URL, got {links}'
  url=links[0];assert urllib.parse.urlparse(url).hostname=='www.ema.europa.eu'
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=120,context=TLS) as response:data=response.read();row['pdf_final_url']=response.url
  assert data.startswith(b'%PDF');(R/'external'/f'{slug}.pdf').write_bytes(data)
  row.update(status='retrieved',pdf_url=url,pdf_sha256=hashlib.sha256(data).hexdigest(),pdf_bytes=len(data))
 except Exception as exc:row.update(status='unavailable',reason=str(exc))
 return row
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:rows=list(pool.map(acquire,protocol['heldout_cohort']))
(R/'external/retrieval.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
print(json.dumps([{k:x[k] for k in ['name','status']+(['reason'] if 'reason' in x else ['pdf_bytes'])} for x in rows],indent=2))
