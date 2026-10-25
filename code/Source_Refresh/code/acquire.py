"""Freeze a later official source release and retain the published transformations."""
from pathlib import Path
import urllib.request,zipfile,hashlib,json,shutil,subprocess,datetime
ROOT=Path(__file__).resolve().parents[1]
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://epl.bag.admin.ch/'})
 with urllib.request.urlopen(req,timeout=90) as f:return f.read()
def main(existing,downloads):
 existing=Path(existing);downloads=Path(downloads);work=ROOT/'input/transform';silver=work/'src/2 silver/staging area';bronze=work/'src/1 bronze/staging area';silver.mkdir(parents=True,exist_ok=True);(bronze/'SAI').mkdir(parents=True,exist_ok=True)
 records=[]
 for name,url in [('sl.zip','https://epl.bag.admin.ch/static/sl/current/excel/all/ExcelPublicationsSL,GGSLundAenderungen.zip'),('refdata.zip','https://sai.refdata.ch/download/structuredexportzip/9029')]:
  data=(downloads/name).read_bytes();(ROOT/'input'/name).write_bytes(data);records.append({'path':'input/'+name,'url':url,'sha256':hashlib.sha256(data).hexdigest(),'acquired_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'refdata_publication':'2026-10-05' if name=='refdata.zip' else None})
  with zipfile.ZipFile(downloads/name) as z:
   for member in z.namelist():
    if member.endswith('Publications.xlsx'):(bronze/'Publications.xlsx').write_bytes(z.read(member))
    if member in ['SAI/SAI-Praeparate.XML','SAI/SAI-Adressen.XML']:(bronze/member).write_bytes(z.read(member))
 commit=json.loads(fetch('https://api.github.com/repos/teletrabbie/medi_graph/commits/main'))['sha']
 for name in ['05_refdata.R','07_bag_sl.R']:
  url=f'https://raw.githubusercontent.com/teletrabbie/medi_graph/{commit}/src/2%20silver/scripts/{name}';data=fetch(url);p=ROOT/'code'/name;p.write_bytes(data);records.append({'path':'code/'+name,'url':url,'sha256':hashlib.sha256(data).hexdigest()})
  subprocess.run(['Rscript',str(p if name=='05_refdata.R' else ROOT/'code/sl_adapter.R')],cwd=work,check=True)
 target=ROOT/'input/updated/input/silver';target.mkdir(parents=True,exist_ok=True)
 for p in (existing/'Graph_Validation_V9/temporal_snapshot/input/silver').glob('*.csv'):shutil.copy2(p,target/p.name)
 for name in ['sl.csv','sai_praeparate.csv']:shutil.copy2(silver/name,target/name)
 code=ROOT/'input/updated/code';code.mkdir(exist_ok=True);shutil.copy2(existing/'Validation_Study/Rebuilt_Snapshot/code/analyze_evidence.py',code/'analyze_evidence.py')
 (ROOT/'input/acquisition.json').write_text(json.dumps({'source_commit':commit,'sources':records,'scope':'Two replaced sources; fixed June tariff and remaining inputs; unchanged Refdata curated corrections; explicit new SL field adapter preserves original columns and SL/GGSL scope.'},indent=2)+'\n')
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--existing',required=True);a.add_argument('--downloads',required=True);x=a.parse_args();main(x.existing,x.downloads)
