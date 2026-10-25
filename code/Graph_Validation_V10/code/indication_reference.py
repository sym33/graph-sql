"""Independent CSV/SQL reconstruction of staged indication assertions.
No graph-builder functions or graph exports enter the reference construction.
"""
import csv,hashlib,json,sqlite3
from pathlib import Path

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

class IndicationReference:
    def __init__(self,root):
        self.files={};self.records={};db=sqlite3.connect(':memory:')
        db.create_function('py_lower',1,lambda x:x.lower())
        db.execute('CREATE TABLE input (id TEXT,file TEXT,authorization TEXT,url TEXT,name TEXT,application TEXT,mesh TEXT,indication TEXT,icd TEXT,original_icd TEXT,original_term TEXT)')
        for filename in ['sai_praeparate.csv','ema_products.csv','gBA_icd.csv']:
            path=Path(root)/'input/silver'/filename
            sha=hashlib.sha256(path.read_bytes()).hexdigest();self.files[filename]=sha
            with path.open(encoding='utf-8-sig',newline='') as f:
                for ordinal,row in enumerate(csv.DictReader(f,delimiter=',' if filename=='sai_praeparate.csv' else '|',escapechar='\\'),1):
                    rid=f'{filename}:{sha}:record:{ordinal}';self.records[rid]=row
                    db.execute('INSERT INTO input VALUES (?,?,?,?,?,?,?,?,?,?,?)',(rid,filename,row.get('ZULASSUNGSNUMMER'),row.get('url'),row.get('product_name',row.get('NAME_HN')),row.get('ANWENDUNGSGEBIET'),row.get('mesh'),row.get('indication',row.get('NAME_ICD_GROUPED')),row.get('ID_ICD_GROUPED'),row.get('ID_ICD'),row.get('NAME_ICD')))
        self.assertions={}
        # Recursive token extraction and SQL projection deliberately do not import the builder.
        sql="""WITH RECURSIVE split(id,file,subject,kind,jurisdiction,term,rest) AS (
          SELECT id,file,CASE WHEN file='sai_praeparate.csv' THEN 'CH:authorization:'||authorization
          ELSE 'EMA:medicine:'||CASE WHEN url IS NOT NULL AND trim(url)<>'' AND trim(url)<>'NA' THEN url ELSE name END END,
          CASE WHEN file='sai_praeparate.csv' THEN 'SAI_application_text' ELSE 'EMA_therapeutic_area_MeSH' END,
          CASE WHEN file='sai_praeparate.csv' THEN 'CH' ELSE 'EU' END,'',
          CASE WHEN file='sai_praeparate.csv' THEN application ELSE mesh END || ';'
          FROM input WHERE file IN ('sai_praeparate.csv','ema_products.csv')
          UNION ALL SELECT id,file,subject,kind,jurisdiction,py_lower(substr(rest,1,instr(rest,';')-1)),substr(rest,instr(rest,';')+1) FROM split WHERE rest<>''
        ) SELECT id,subject,kind,jurisdiction,term FROM split WHERE trim(term)<>'' AND trim(term)<>'NA'"""
        for rid,subject,kind,jurisdiction,term in db.execute(sql):
            self.add({'subject':subject,'term':term,'kind':kind,'record_id':rid,'jurisdiction':jurisdiction})
        for rid,subject,term in db.execute("SELECT id,'EMA:medicine:'||CASE WHEN trim(url)<>'' AND trim(url)<>'NA' THEN url ELSE name END,indication FROM input WHERE file='ema_products.csv' AND trim(indication)<>'' AND trim(indication)<>'NA'"):
            self.add({'subject':subject,'term':term,'kind':'EMA_therapeutic_indication_text','record_id':rid,'jurisdiction':'EU'})
        for rid,subject,term,icd,original_icd,original_term in db.execute("SELECT id,'DE:GBA:trade_name:'||py_lower(name),indication,icd,original_icd,original_term FROM input WHERE file='gBA_icd.csv'"):
            self.add({'subject':subject,'term':term,'kind':'GBA_grouped_ICD_context','icd':icd,'original_icd':original_icd,'original_term':original_term,'record_id':rid,'jurisdiction':'DE'})
        db.close();self.reference_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    def add(self,item):
        item['id']=digest(item);self.assertions[item['id']]=item
