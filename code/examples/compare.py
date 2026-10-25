"""Replay and export the study's paired queries; no database service required."""
from pathlib import Path
import ast, hashlib, json, sqlite3, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/results'
OUT.mkdir(parents=True,exist_ok=True)
def constants(path,names):
    values={}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in names:
                    values[target.id]=ast.literal_eval(node.value)
    assert set(values)==set(names)
    return values
source=ROOT/'Graph_Validation_V22/code/explanation_workflow.py'
queries=constants(source,['SQL','CYPHER'])
subprocess.run([sys.executable,str(source)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
report=json.loads((ROOT/'Graph_Validation_V22/results/explanation_workflow.json').read_text())
for language,key in [('sql','SQL'),('cypher','CYPHER')]:
    (OUT/f'discovery.{language}').write_text(queries[key]+';\n')
material=constants(ROOT/'Source_Refresh/code/compare.py',['SQL_MATERIALIZE','NEO_MATERIALIZE'])
for language,key in [('sql','SQL_MATERIALIZE'),('cypher','NEO_MATERIALIZE')]:
    (OUT/f'store_connections.{language}').write_text(material[key]+';\n')
sys.path.insert(0,str(ROOT/'Validation_Study/code'))
from reference_oracle import Reference
ref=Reference(ROOT/'Graph_Validation_V9/temporal_snapshot')
db=sqlite3.connect(':memory:')
db.executescript('CREATE TABLE witness(id TEXT,code TEXT,rule TEXT,jurisdiction TEXT); CREATE TABLE tariff(id TEXT,code TEXT); CREATE TABLE candidate(witness TEXT,tariff TEXT);')
db.executemany('INSERT INTO witness VALUES(?,?,?,?)',[(w['id'],w['atc'],w['rule'],w['jurisdiction']) for w in ref.witnesses.values()])
db.executemany('INSERT INTO tariff VALUES(?,?)',[(r,p['code']) for r,p in ref.records.items() if r.startswith('ze_definitions.csv:')])
expected=sorted(db.execute("SELECT w.id,t.id FROM witness w JOIN tariff t ON w.code=t.code WHERE w.jurisdiction='CH' AND w.rule IN ('direct_SAI','via_authorization_SL')"))
for _ in range(2):
    db.execute('DELETE FROM candidate')
    db.execute(material['SQL_MATERIALIZE'])
    assert sorted(db.execute('SELECT * FROM candidate'))==expected
assert len(expected)==1559
sys.path.insert(0,str(ROOT/'Graph_Validation_V17/code'))
from route_policies import assess
route_examples=[('Example oral','Example tablets','O','VERIFIED'),('Example oral','Example tablets','IV','CONTRADICTED'),('Example parenteral','Example injection','IV','UNDETERMINED')]
for group,package,tariff,status in route_examples:
    assert assess(group,package,tariff,'exact_code')==status
summary={'route_example_checks':len(route_examples),'explained_answer_and_route_replay':report,'stored_derivations':len(expected),'two_SQL_invalidate_rebuild_cycles_identical':True,'native_Neo4j_executed':False,'query_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(OUT/'checks.json').write_text(json.dumps(summary,indent=2)+'\n')
print('Explained SQL answers and route judgments match frozen physical graph exports.\nStored SQL connections: 1559; two rebuild checks passed.\nExported original Cypher/SQL and checks to examples/results/.\nNative Neo4j was not executed by this offline example.')
