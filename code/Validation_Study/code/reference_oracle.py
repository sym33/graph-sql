"""Independent CSV/SQLite reference: does not import the graph builder or exports."""
import csv,hashlib,json,sqlite3
from pathlib import Path
DELIMS={'sai_praeparate.csv':',','technisches_begleitblatt.csv':',','atc_alterations.csv':';','geloeschte_substanzen.csv':';'}
SOURCE_FILES=['sai_praeparate.csv','ema_products.csv','sl.csv','atc_alterations.csv']
def canonical_hash(item):
    return hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
class Reference:
    def __init__(self,root):
        self.root=Path(root);self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE input(file TEXT,rid TEXT PRIMARY KEY,payload TEXT,sha TEXT)')
        self.records={};self.files={}
        for path in sorted((self.root/'input/silver').glob('*.csv')):
            sha=hashlib.sha256(path.read_bytes()).hexdigest();self.files[path.name]=sha
            with path.open(encoding='utf-8-sig',newline='') as f:
                for ordinal,row in enumerate(csv.DictReader(f,delimiter=DELIMS.get(path.name,'|'),escapechar='\\'),1):
                    assert None not in row and None not in row.values()
                    rid=f'{path.name}:{sha}:record:{ordinal}';self.records[rid]=row
                    self.db.execute('INSERT INTO input VALUES(?,?,?,?)',(path.name,rid,json.dumps(row,ensure_ascii=False),sha))
        self.db.executescript('''
        CREATE TABLE sai AS SELECT rid,json_extract(payload,'$.ZULASSUNGSNUMMER') auth,json_extract(payload,'$.ATC_CODE') code FROM input WHERE file='sai_praeparate.csv';
        CREATE TABLE ema AS SELECT rid,'EMA:medicine:' || CASE WHEN coalesce(trim(json_extract(payload,'$.url')),'') NOT IN ('','NA') THEN json_extract(payload,'$.url') ELSE json_extract(payload,'$.product_name') END subject,json_extract(payload,'$.atc') code FROM input WHERE file='ema_products.csv';
        CREATE TABLE sl AS SELECT rid,json_extract(payload,'$.zulassungsnummer') auth,json_extract(payload,'$.atc') code FROM input WHERE file='sl.csv';
        CREATE TABLE alterations AS SELECT rid,json_extract(payload,'$."ATC code"') oldcode,json_extract(payload,'$."New ATC code"') newcode,json_extract(payload,'$."Year changed"') year FROM input WHERE file='atc_alterations.csv';
        CREATE TABLE dictionary AS SELECT DISTINCT json_extract(payload,'$.atc_code') code FROM input WHERE file='atc_list.csv';
        CREATE INDEX sai_auth ON sai(auth);
        CREATE INDEX sl_auth ON sl(auth);
        CREATE INDEX history_old ON alterations(oldcode);
        CREATE VIEW direct AS
          SELECT 'CH:authorization:' || auth subject,code,'direct_SAI' rule,rid p1,NULL p2,'CH' jurisdiction,NULL origin,NULL year FROM sai WHERE coalesce(trim(code),'') NOT IN ('','NA')
          UNION ALL SELECT subject,code,'direct_EMA',rid,NULL,'EU',NULL,NULL FROM ema WHERE coalesce(trim(code),'') NOT IN ('','NA');
        CREATE VIEW derivations AS
          SELECT * FROM direct
          UNION ALL SELECT 'CH:authorization:' || s.auth,l.code,'via_authorization_SL',s.rid,l.rid,'CH',NULL,NULL FROM sai s JOIN sl l ON s.auth=l.auth WHERE coalesce(trim(l.code),'') NOT IN ('','NA')
          UNION ALL SELECT d.subject,h.newcode,'historical_candidate',d.p1,h.rid,d.jurisdiction,d.code,h.year FROM direct d JOIN alterations h ON d.code=h.oldcode WHERE coalesce(trim(h.newcode),'') NOT IN ('','NA');
        ''')
        # Preserve the SQL definition in the reference output for review.
        self.sql={row['name']:row['sql'] for row in self.db.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL")}
        self.atc={row[0] for row in self.db.execute('SELECT code FROM dictionary')}
        frozen=self.root/'Validation_Study/Rebuilt_Snapshot/code/analyze_evidence.py'
        self.implementation_path=frozen if frozen.exists() else self.root/'code/analyze_evidence.py'
        self.implementation_sha=hashlib.sha256(self.implementation_path.read_bytes()).hexdigest()
        self.witnesses={};self.db.execute('CREATE TABLE witnesses(id TEXT PRIMARY KEY,subject TEXT,atc TEXT,mask INTEGER)')
        for row in self.db.execute('SELECT DISTINCT * FROM derivations').fetchall():
            premises=sorted({p for p in (row['p1'],row['p2']) if p is not None})
            status='source_association'
            if row['rule']=='historical_candidate':status='context_review_required' if row['origin'] in self.atc and row['code'] in self.atc else 'historical_mapping_candidate'
            item={'subject':row['subject'],'atc':row['code'],'rule':row['rule'],'premise_ids':premises,'jurisdiction':row['jurisdiction'],'evidence_status':status,'atc_in_snapshot':row['code'] in self.atc,'atc_index_snapshot_sha256':self.files['atc_list.csv'],'implementation_sha256':self.implementation_sha,'validity_status':'unknown_product_specific_validity'}
            if row['rule']=='historical_candidate':item.update(origin_atc=row['origin'],alteration_year=row['year'])
            item['id']=canonical_hash(item);self.witnesses[item['id']]=item
            mask=0
            for premise in premises:mask|=1<<SOURCE_FILES.index(premise.split(':',1)[0])
            self.db.execute('INSERT OR IGNORE INTO witnesses VALUES(?,?,?,?)',(item['id'],item['subject'],item['atc'],mask))
        self.indications={}
        for rid,payload in self.records.items():
            filename=rid.split(':',1)[0]
            if filename=='sai_praeparate.csv':
                subject='CH:authorization:'+payload['ZULASSUNGSNUMMER']
                for term in payload['ANWENDUNGSGEBIET'].split(';'):self.add_indication(subject,term.lower(),'SAI_application_text',rid,'CH')
            elif filename=='ema_products.csv':
                url=payload['url'];subject='EMA:medicine:'+(url if url and url.strip() not in ('','NA') else payload['product_name'])
                for term in payload['mesh'].split(';'):self.add_indication(subject,term.lower(),'EMA_therapeutic_area_MeSH',rid,'EU')
                self.add_indication(subject,payload['indication'],'EMA_therapeutic_indication_text',rid,'EU')
            elif filename=='gBA_icd.csv':
                item={'subject':'DE:GBA:trade_name:'+payload['NAME_HN'].lower(),'term':payload['NAME_ICD_GROUPED'],'kind':'GBA_grouped_ICD_context','icd':payload['ID_ICD_GROUPED'],'original_icd':payload['ID_ICD'],'original_term':payload['NAME_ICD'],'record_id':rid,'jurisdiction':'DE'}
                item['id']=canonical_hash(item);self.indications[item['id']]=item
    def add_indication(self,subject,term,kind,rid,jurisdiction):
        if not term or term.strip() in ('','NA'):return
        item={'subject':subject,'term':term,'kind':kind,'record_id':rid,'jurisdiction':jurisdiction};item['id']=canonical_hash(item);self.indications[item['id']]=item
    def pairs(self,mask=15):
        return {tuple(row) for row in self.db.execute('SELECT DISTINCT subject,atc FROM witnesses WHERE mask & ? = mask',(mask,))}
    def compare(self,observed):
        actual={a['id']:a for a in observed};expected=self.witnesses
        return {'expected':len(expected),'observed':len(actual),'missing':sorted(expected.keys()-actual.keys()),'extra':sorted(actual.keys()-expected.keys()),'property_mismatches':[k for k in sorted(expected.keys()&actual.keys()) if expected[k]!=actual[k]]}
