"""Descriptive audit of frozen equivalent query artifacts, not human effort."""
from pathlib import Path
import argparse,difflib,hashlib,json,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'Graph_Validation_V27/code'))
from workloads import WORKLOADS

def main(output):
 rows=[];tokens=lambda q:re.findall(r"[A-Za-z_][A-Za-z_0-9]*|<>|[^\s]",q)
 keys=list(WORKLOADS)
 for key in keys:
  for lang in ['SQL','Cypher']:
   q=WORKLOADS[key][lang];rows.append({'task':key,'language':lang,'characters':len(q),'lexical_tokens':len(tokens(q)),'SQL_JOIN_clauses':len(re.findall(r'\bJOIN\b',q)) if lang=='SQL' else None,'Cypher_relationship_patterns':len(re.findall(r'\[:',q)) if lang=='Cypher' else None,'sha256':hashlib.sha256(q.encode()).hexdigest()})
 transitions=[]
 for left,right in [('L1_candidates','L2_source_lineage'),('L2_source_lineage','L3_rule_dictionary'),('L3_rule_dictionary','L4_cross_source_context'),('L1_candidates','L5_peer_indication_evidence')]:
  for lang in ['SQL','Cypher']:
   a,b=map(tokens,[WORKLOADS[left][lang],WORKLOADS[right][lang]]);ops=difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes();transitions.append({'from':left,'to':right,'language':lang,'inserted_tokens':sum(j2-j1 for tag,i1,i2,j1,j2 in ops if tag in ['insert','replace']),'removed_tokens':sum(i2-i1 for tag,i1,i2,j1,j2 in ops if tag in ['delete','replace'])})
 result={'scope':'Frozen V27 equivalent query artifacts; deterministic lexical audit','interpretation':'Length and edit counts describe these implementations. They do not measure comprehension, authoring time, cognitive complexity, or general language superiority. Both use unchanged source schemas across all tasks. L3-to-L4 changes the question as well as evidence scope.','queries':rows,'transitions':transitions}
 Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(rows,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();main(a.output)
