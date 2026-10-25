"""Read-only complete audit of the refreshed physical graph and source premises."""
from pathlib import Path
import argparse,sys,json
from compare import query,digest,norm

def main(root,updated,url,output):
 sys.path.insert(0,str(root.resolve()/'Validation_Study/code'));from reference_oracle import Reference
 ref=Reference(updated)
 rows=query(url,'MATCH (r:SourceRecord) RETURN r.id AS id,r.payload_json AS payload,[(r)-[:IN_SNAPSHOT]->(s) | s.id] AS snapshots');assert {x['id']:json.loads(x['payload']) for x in rows}==ref.records;assert all(x['snapshots']==[x['id'].split(':')[1]] for x in rows)
 ws=query(url,'MATCH (w:Association) RETURN properties(w) AS payload,[(w)-[:ABOUT_PRODUCT]->(p) | p.id] AS products,[(w)-[:TARGET_ATC]->(c) | c.id] AS codes,[(w)-[:SUPPORTED_BY]->(r) | r.id] AS premises');assert {x['payload']['id']:x['payload'] for x in ws}==ref.witnesses;assert all(x['products']==[x['payload']['subject']] and x['codes']==[x['payload']['atc']] and sorted(x['premises'])==x['payload']['premise_ids'] for x in ws)
 result={'source_records':len(rows),'classification_associations':len(ws),'complete_payload_and_endpoint_agreement':True,'source_record_sha256':digest(norm([{'id':x['id'],'payload':json.loads(x['payload'])} for x in rows]))};output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--updated',type=Path,required=True);p.add_argument('--neo4j-url',default='http://127.0.0.1:18474');p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root,a.updated,a.neo4j_url,a.output)
