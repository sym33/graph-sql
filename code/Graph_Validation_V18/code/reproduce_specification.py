"""Public, data-independent specification check; NOT natural-data replication."""
from pathlib import Path
import itertools,json,hashlib,sqlite3
from dataclasses import asdict
from contract import ORDER,judge,select
R=Path(__file__).resolve().parents[1]
rows=[]
# Independent declarative truth table, not calling judge to construct expectations.
db=sqlite3.connect(':memory:')
db.execute('CREATE TABLE obligations (id INTEGER,I INTEGER,S INTEGER,E INTEGER,K INTEGER,F INTEGER,A INTEGER)')
for n,bits in enumerate(itertools.product((False,True),repeat=6)):
    db.execute('INSERT INTO obligations VALUES (?,?,?,?,?,?,?)',(n,*bits))
sql="""SELECT id, CASE WHEN NOT(I AND S AND E AND K) THEN 'UNDETERMINED'
 WHEN NOT A THEN 'UNDETERMINED' WHEN NOT F THEN 'CONTRADICTED' ELSE 'VERIFIED' END,
 CASE WHEN I AND S AND E THEN CASE WHEN F THEN 'AGREEMENT' ELSE 'CONFLICT' END ELSE 'UNAVAILABLE' END FROM obligations"""
expected={n:(status,diagnostic) for n,status,diagnostic in db.execute(sql)}
for n,bits in enumerate(itertools.product((False,True),repeat=6)):
    o=dict(zip(ORDER,bits));j=judge(o)
    assert (j.status,j.diagnostic)==expected[n]
    assert all(o[k] for k in ('I','S','E','K','A')) or j.status!='CONTRADICTED'
    changed={**o,'K':not o['K']}
    assert judge(changed).diagnostic==j.diagnostic
    rows.append({'id':n,'obligations':o,**asdict(j)})
# Synthetic source records establish a missing-content and a context-conflict contrast.
sources={'r1':{'term':'na','code':'A'},'r2':{'term':'term-x','code':'B'}}
source_bytes=json.dumps(sources,sort_keys=True).encode();source_digest=hashlib.sha256(source_bytes).hexdigest()
all_true={k:True for k in ORDER}
claims={'recorded-placeholder':all_true,'information-placeholder':{**all_true,'A':False},
        'missing-content-conflict':{**all_true,'F':False,'A':False},'available-conflict':{**all_true,'F':False},'unavailable-conflict':{**all_true,'F':False,'K':False}}
original={k:judge(v) for k,v in claims.items()};view=select(original)
assert set(view['selected']).isdisjoint(view['excluded'])
assert set(view['selected'])|set(view['excluded'])==set(claims)
extended={**original,'new-target':judge({**all_true,'A':False})}
assert all(extended[k]==v for k,v in original.items())
assert hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()==source_digest
assert original['unavailable-conflict'].diagnostic==original['available-conflict'].diagnostic=='CONFLICT'
assert original['missing-content-conflict'].status=='UNDETERMINED' and original['missing-content-conflict'].diagnostic=='CONFLICT'
result={'scope':'Synthetic specification verification, not medication findings or domain transfer validation',
        'Boolean_cases':len(rows),'independent_SQL_agreement':True,'context_safety':True,
        'diagnostic_preservation':True,'content_safety':True,'selection_accounting':True,'synthetic_source_conservation':True,
        'synthetic_additive_assessment_preservation':True,'synthetic_view':view,'truth_table':rows}
(R/'results').mkdir(exist_ok=True)
(R/'results/specification_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='truth_table'},indent=2))
