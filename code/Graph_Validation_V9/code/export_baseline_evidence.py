from pathlib import Path
import sys,json,argparse
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);args=parser.parse_args();P=args.root.resolve();sys.path.insert(0,str(P/'code'))
from run_baseline import query
out=P/'Graph_Validation_V9/results';out.mkdir(parents=True,exist_ok=True)
q='''MATCH (a:Association) RETURN properties(a) AS association, [(a)-[:ABOUT_PRODUCT]->(p) | p.id] AS products, [(a)-[:TARGET_ATC]->(c) | c.id] AS targets, [(a)-[:SUPPORTED_BY]->(r) | properties(r)] AS records ORDER BY a.id'''
rows=query(q);assert len(rows)==18339;(out/'baseline_physical_bundles.json').write_text(json.dumps(rows,ensure_ascii=False));print({'physical_baseline_witnesses':len(rows)})
