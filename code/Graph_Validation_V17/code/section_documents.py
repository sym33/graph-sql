"""Bind formulation titles and administration evidence within one complete SmPC."""
from pathlib import Path
import argparse,json,hashlib,re,subprocess
R=Path(__file__).resolve().parents[1];P=R.parent
def normalize(text):return ' '.join(text.split())
def blocks(text):
 # Page breaks are whitespace; requiring an exact heading excludes labeling headings.
 name=re.compile(r'(?:^|\n|\f)\s*1\.\s*NAME OF THE MEDICINAL PRODUCT\s*(?:\r?\n)',re.I)
 starts=list(name.finditer(text));out=[]
 for i,m in enumerate(starts):
  end=starts[i+1].start() if i+1<len(starts) else len(text);part=text[m.end():end]
  sec2=re.search(r'(?:^|\n|\f)\s*2\.\s*QUALITATIVE AND QUANTITATIVE COMPOSITION',part,re.I)
  sec42=re.search(r'(?:^|\n|\f)\s*4\.2\s+Posology and method of administration',part,re.I)
  sec43=re.search(r'(?:^|\n|\f)\s*4\.3\s+Contraindications',part,re.I)
  if not(sec2 and sec42 and sec43 and sec2.start()<sec42.start()<sec43.start()):continue
  absolute42=m.end()+sec42.end();absolute43=m.end()+sec43.start()
  out.append({'title':normalize(part[:sec2.start()]),'title_span':[m.end(),m.end()+sec2.start()],'administration':normalize(text[absolute42:absolute43]),'administration_span':[absolute42,absolute43],'PDF_pages_title':[text[:m.end()].count('\f')+1,text[:m.end()+sec2.start()].count('\f')+1],'PDF_pages_administration':[text[:absolute42].count('\f')+1,text[:absolute43].count('\f')+1]})
 return out
def evidence(block,title,phrase):
 return title.casefold() in block['title'].casefold() and phrase.casefold() in block['administration'].casefold()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--data-root',type=Path,default=P);D=ap.parse_args().data_root
 version=subprocess.run(['pdftotext','-v'],capture_output=True,text=True);extractor=(version.stderr or version.stdout).splitlines()[0]
 manifest=json.loads((D/'Graph_Validation_V16/external/retrieval_manifest.json').read_text());out=[];tests=[]
 for name,title,route in [('cresemba','200 mg powder for concentrate for solution for infusion','intravenous use'),('noxafil','40 mg/mL oral suspension','For oral use')]:
  meta=next(x for x in manifest if x['name']==name);pdf=D/'Graph_Validation_V16/external'/f'{name}.pdf'
  assert hashlib.sha256(pdf.read_bytes()).hexdigest()==meta['sha256']
  txt=subprocess.check_output(['pdftotext','-enc','UTF-8','-layout',str(pdf),'-']).decode();found=blocks(txt)
  selected=[b for b in found if title.casefold() in b['title'].casefold()];assert len(selected)==1,(name,[b['title'] for b in found]);b=selected[0];assert evidence(b,title,route)
  out.append({'document':name,'reference':meta,'complete_SmPC_blocks':len(found),'selected_formulation_title':b['title'],'sections':['1','4.2'],'title_span':b['title_span'],'administration_span':b['administration_span'],'PDF_pages_title':b['PDF_pages_title'],'PDF_pages_administration':b['PDF_pages_administration'],'section_text_sha256':hashlib.sha256(b['administration'].encode()).hexdigest(),'same_formulation_binding':True,'pdf_text_extractor':extractor,'scope':'Section-bound documentary interpretation; no Swiss identity bridge or clinical precision estimate.'})
  # Deliberately attach the selected title to another real formulation's administration section.
  alternatives=[a for a in found if a is not b]
  if name=='cresemba':other=next(a for a in alternatives if 'capsule' in a['title'].casefold())
  else:other=next(a for a in alternatives if 'infusion' in a['title'].casefold())
  splice={**b,'administration':other['administration']};assert not evidence(splice,title,route),(name,other['title'])
  tests.append({'document':name,'selected_title':b['title'],'wrong_administration_from':other['title'],'cross_formulation_promotion_rejected':True})
 # Synthetic adversarial controls isolate location and boundary failures.
 template='1. NAME OF THE MEDICINAL PRODUCT\nTarget 200 mg infusion\n2. QUALITATIVE AND QUANTITATIVE COMPOSITION\nx\n4.2 Posology and method of administration\nFor oral use.\n4.3 Contraindications\nintravenous use\n'
 bb=blocks(template);assert len(bb)==1 and not evidence(bb[0],'Target 200 mg infusion','intravenous use')
 tests.append({'fixture':'route phrase outside section 4.2','rejected':True})
 broken=template.replace('4.3 Contraindications','missing boundary');assert not blocks(broken)
 tests.append({'fixture':'missing section boundary','rejected':True})
 (R/'results/section_document_audit.json').write_text(json.dumps(out,indent=2));(R/'results/document_binding_controls.json').write_text(json.dumps(tests,indent=2));print(json.dumps(out,indent=2));print('All four document-location controls pass.')
if __name__=='__main__':main()
