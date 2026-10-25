"""Recover explicit document labels; keep absent field-effective dates unknown."""
from pathlib import Path
import json,re,hashlib
R=Path(__file__).resolve().parents[1];P=R.parent;raw=P/'External_Knowledge_Validation/raw'
cases=json.loads((P/'External_Knowledge_Validation/results/product_information_crosschecks.json').read_text())['cases'];receipts=[]
for path in [raw/'retrieval_manifest.jsonl',raw/'adjudication_retrieval_manifest.jsonl']:
 if path.exists():receipts.extend(json.loads(s) for s in path.read_text().splitlines())
byfile={x['file']:x for x in receipts};out=[]
for c in cases:
 slug=c['EMA_metadata_url'].rsplit('/',1)[-1];text=(raw/f'ema_{slug}.txt').read_text();pdftext=(raw/f'smpc_{slug}.txt').read_text()
 # This title identifies the English product-information attachment, not generic page dates.
 match=re.search(r'(?i)EPAR\s*-\s*Product Information\s*\nEnglish \(EN\)(.*?)(?:\nView|\nOther languages)',text,re.S)
 block=match.group(1) if match else ''
 dates={key:(re.search(re.escape(label)+r'\s*\n(\d{2}/\d{2}/\d{4})',block).group(1) if re.search(re.escape(label)+r'\s*\n(\d{2}/\d{2}/\d{4})',block) else None) for key,label in [('first_published','First published:'),('last_updated','Last updated:')]}
 rev=re.search(r'\nRevision\s*\n(\d+)\s*\n',text)
 revision_section=re.search(r'10\.\s*DATE OF REVISION OF THE TEXT(.{0,400})',pdftext,re.S)
 section=revision_section.group(1) if revision_section else ''
 effective=re.search(r'\b(?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{2}/\d{2}/\d{4})\b',section)
 row={'product':c['product'],'EMA_metadata_ATC':c['current_EMA_metadata_atc'],'SmPC_ATC':c['SmPC_atc_codes'],'English_attachment_labels':dates,'page_revision_label':rev.group(1) if rev else None,'SmPC_revision_date_explicit':effective.group(0) if effective else None,'ATC_field_effective_date':None,'interpretation':'co-retrieved representations; attachment date and page revision do not establish ATC-field effective date','metadata_receipt':byfile.get(f'ema_{slug}.html'),'SmPC_receipt':byfile.get(f'smpc_{slug}.pdf'),'attachment_label_context':block.strip()}
 out.append(row)
(R/'results/document_temporal_context.json').write_text(json.dumps(out,indent=2));print(json.dumps([{k:v for k,v in x.items() if k in ['product','English_attachment_labels','page_revision_label','SmPC_revision_date_explicit']} for x in out],indent=2))
