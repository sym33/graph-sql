import argparse,sys,json,hashlib,urllib.request,time
from pathlib import Path
a=argparse.ArgumentParser();a.add_argument('--neo4j-url',default='http://127.0.0.1:17474');a.add_argument('--receipt',required=True);a.add_argument('--output',required=True);args=a.parse_args()
from workloads import WORKLOADS
base=args.neo4j_url.rstrip('/')
def call(s):
 req=urllib.request.Request(base+'/db/neo4j/tx/commit',data=json.dumps({'statements':[{'statement':s}]}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=180) as f:r=json.load(f)
 assert not r['errors'],r['errors'];return r['results'][0]
listing='SHOW INDEXES YIELD name,type,labelsOrTypes,properties,state RETURN name,type,labelsOrTypes,properties,state'
def rows(r):return [dict(zip(r['columns'],x['row'])) for x in r['data']]
before=rows(call(listing));names={x['name'] for x in before};idx=[('Complex27_assoc_scope','CREATE RANGE INDEX Complex27_assoc_scope FOR (n:Association) ON (n.jurisdiction,n.rule)'),('Complex27_assoc_subject','CREATE RANGE INDEX Complex27_assoc_subject FOR (n:Association) ON (n.subject,n.rule)'),('Complex27_tariff_code','CREATE RANGE INDEX Complex27_tariff_code FOR (n:SourceRecord) ON (n.file,n.tariff_atc)')];assert not names.intersection(n for n,_ in idx)
old=json.load(open(args.receipt));canon=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
result={'purpose':'Diagnostic PROFILE of two predefined complex tasks, outside original timing experiment; repeated warmup, no new engine-ranking claim','profiles':{}}
try:
 for n,q in idx:call(q)
 call('CALL db.awaitIndexes(120)')
 for name in ['L4_cross_source_context','L5_peer_indication_evidence']:
  query=WORKLOADS[name]['Cypher']
  for _ in range(3):call(query)
  r=call('PROFILE '+query);actual=sorted(rows(r),key=canon);sha=hashlib.sha256(canon(actual).encode()).hexdigest();assert sha==next(m['output_sha256'] for m in old['measurements'] if m['workload']==name)
  result['profiles'][name]={'rows':len(actual),'output_sha256':sha,'profile':{k:v for k,v in r.items() if k not in {'data','columns'}},'result_keys':list(r)}
finally:
 for n,_ in idx:call('DROP INDEX '+n+' IF EXISTS')
 after=rows(call(listing));assert sorted(before,key=canon)==sorted(after,key=canon);result['original_indexes_restored']=True
json.dump(result,open(args.output,'w'),indent=2);print({k:v['result_keys'] for k,v in result['profiles'].items()})
