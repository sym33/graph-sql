"""Independently compare used staged fields with their frozen official Excel rows."""
from pathlib import Path
import argparse,csv,io,json,re,zipfile,xml.etree.ElementTree as E
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def rows_from_xlsx(data):
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  wb=E.fromstring(z.read('xl/workbook.xml'));sheet=next(s for s in wb.find('s:sheets',NS) if s.attrib['name']=='Datenstamm');rid=sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'];rels=E.fromstring(z.read('xl/_rels/workbook.xml.rels'));target=next(r.attrib['Target'] for r in rels if r.attrib['Id']==rid);path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
  strings=[]
  if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))]
  out={}
  for row in E.fromstring(z.read(path)).find('s:sheetData',NS):
   values={}
   for c in row:
    col=re.match(r'[A-Z]+',c.attrib['r'])[0];v=c.find('s:v',NS)
    if c.attrib.get('t')=='s':value=strings[int(v.text)] if v is not None else None
    elif c.attrib.get('t')=='inlineStr':value=''.join(x.text or '' for x in c.findall('.//s:t',NS))
    else:value=v.text if v is not None else None
    values[col]=value
   out[int(row.attrib['r'])]=values
  header=out[1];return {n:{header[col]:value for col,value in cells.items() if col in header} for n,cells in out.items() if n!=1}

def main(inputs,output):
 with zipfile.ZipFile(inputs/'sl.zip') as z:
  names=[n for n in z.namelist() if n.endswith('/Publications.xlsx')];assert len(names)==1;raw=rows_from_xlsx(z.read(names[0]))
 with (inputs/'silver/sl.csv').open(encoding='utf-8-sig',newline='') as f:staged=list(csv.DictReader(f,delimiter='|',escapechar='\\'))
 null=lambda x:'NA' if x is None or x.strip()=='' else x.strip()
 for p in staged:
  r=raw[int(p['official_row'])];assert r['Listung (GGSL, SL, GGML)'] in {'SL','GGSL'}
  for field,title in [('atc','ATC-Code'),('substanzen','Wirkstoffe'),('gammenbezeichnung','Gammenbezeichnung'),('swissmedic_code_packung','Swissmedic Code Packung')]:assert p[field]==null(r.get(title)),(field,p['official_row'],p[field],r.get(title))
  assert p['bezeichnung']==', '.join(null(r.get(f)) for f in ['Handelsname','gal.Form/Dosierung','Packung'])
  codes=[x.strip() for x in r['Swissmedic Code Packung'].split(',')] if r.get('Swissmedic Code Packung') else ['NA'];assert p['swissmedic_nr'] in codes
  assert p['zulassungsnummer']==('NA' if p['swissmedic_nr']=='NA' else str(int(p['swissmedic_nr'])//1000))
 expected={n for n,p in raw.items() if p.get('Listung (GGSL, SL, GGML)') in {'SL','GGSL'}};assert {int(p['official_row']) for p in staged}==expected
 report={'staged_rows':len(staged),'covered_official_rows':len(expected),'used_fields_agree_with_official_rows':True,'all_declared_package_codes_retained':all({p['swissmedic_nr'] for p in staged if int(p['official_row'])==n}==({x.strip() for x in raw[n]['Swissmedic Code Packung'].split(',')} if raw[n].get('Swissmedic Code Packung') else {'NA'}) for n in expected)};assert report['all_declared_package_codes_retained'];output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=Path(__file__).resolve().parents[1]/'input');p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.inputs,a.output)
