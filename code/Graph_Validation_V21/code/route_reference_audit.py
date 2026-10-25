"""Census of complete formulation sections; explicit positive route assertions only."""
from pathlib import Path
from html.parser import HTMLParser
import importlib.util,json,re,subprocess,hashlib
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sections',R.parent/'Graph_Validation_V17/code/section_documents.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Rows(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.row=[];self.cell=None
 def handle_starttag(self,t,a):
  if t=='tr':self.row=[]
  if t=='td':self.cell=[]
 def handle_data(self,d):
  if self.cell is not None:self.cell.append(d)
 def handle_endtag(self,t):
  if t=='td' and self.cell is not None:self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
  if t=='tr' and self.row:self.rows.append(self.row)
p=Rows();p.feed((R/'external/edqm_routes.html').read_text());concepts=[{'code':r[1],'display':r[2],'definition':r[3]} for r in p.rows if len(r)>=5 and r[0]=='http://standardterms.edqm.eu' and re.fullmatch(r'\d+',r[1])];assert len(concepts)==85,len(concepts)
labels={'IV':'Intravenous use','O':'Oral use','SC':'Subcutaneous use','IM':'Intramuscular use','IT':'Intrathecal use','Inhal':'Inhalation use','SR':'Subretinal use'}
crosswalk={k:next(c for c in concepts if c['display']==v) for k,v in labels.items()}
from route_assertions import extract,controls
records=[]
for name in ['cresemba','noxafil','entyvio','ocrevus','rybrevant','darzalex','tabrecta','votrient']:
 pdf=R/'external'/f'{name}.pdf';txt=subprocess.check_output(['pdftotext','-enc','UTF-8','-layout',str(pdf),'-']).decode()
 for b in m.blocks(txt):
  # Restrict to the final dedicated method subsection inside the complete formulation.
  method=b['administration'].rsplit('Method of administration',1)[-1];assessment=extract(method);pos,neg=assessment['positive_routes'],assessment['excluded_routes']
  records.append({'document':name,'title':b['title'],'positive_routes':pos,'excluded_routes':neg,'status':assessment['status'],'conflicting_routes':assessment['conflicting_routes'],'eligible_routes':assessment['eligible_routes'],'assertion_evidence':assessment,'pages':b['PDF_pages_administration'],'method_sha256':hashlib.sha256(method.encode()).hexdigest(),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()})
control_results=controls()
assert len(records)==16
out={'scope':'Complete formulation-section census of eight selected documents; not a population extraction accuracy estimate. Crosswalk authored against published EDQM concepts.','EDQM_concepts':len(concepts),'observed_tariff_tokens_mapped':crosswalk,'documents':8,'complete_formulation_blocks':len(records),'explicit_positive_blocks':sum(x['status']=='explicit' for x in records),'blocks_with_exclusions':sum(bool(x['excluded_routes']) for x in records),'adversarial_controls_passed':len(control_results),'conflicting_blocks':sum(x['status']=='conflicting' for x in records),'control_results':control_results,'parser_sha256':hashlib.sha256((R/'code/route_assertions.py').read_bytes()).hexdigest(),'records':records}
(R/'results/route_reference_audit.json').write_text(json.dumps(out,indent=2));print({k:v for k,v in out.items() if k not in ['records','observed_tariff_tokens_mapped','control_results']})
