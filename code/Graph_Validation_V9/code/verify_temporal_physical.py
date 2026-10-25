"""Full census physical checks and snapshot fingerprint for the June graph."""
from pathlib import Path
import sys,json,collections
R=Path(__file__).resolve().parents[1];W=R/'temporal_snapshot';sys.path[:0]=[str(W/'Validation_Study/code'),str(W/'code')]
from reference_oracle import Reference
from neo4j_contracts import Validator,violations,query
ref=Reference(W);report=Validator(ref).evaluate(full=True);assert violations(report)==0,report
q='''MATCH (a:Association) RETURN properties(a) AS association, [(a)-[:ABOUT_PRODUCT]->(p) | p.id] AS products, [(a)-[:TARGET_ATC]->(c) | c.id] AS targets, [(a)-[:SUPPORTED_BY]->(r) | properties(r)] AS records ORDER BY a.id'''
bundles=query(q);assert {x['association']['id'] for x in bundles}==set(ref.witnesses)
(R/'results/temporal_physical_bundles.json').write_text(json.dumps(bundles,ensure_ascii=False))
summary={'physical_witnesses':len(bundles),'structural_provenance_reference_violations':violations(report),'source_records_checked':len(ref.records),'node_counts':query('MATCH (n) UNWIND labels(n) AS label RETURN label,count(*) AS n ORDER BY label'),'relationship_counts':query('MATCH ()-[r]->() RETURN type(r) AS type,count(*) AS n ORDER BY type'),'contracts':report,'scope':'separate research Neo4j data directory; baseline store preserved'}
(R/'results/temporal_physical_validation.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='contracts'},indent=2))
