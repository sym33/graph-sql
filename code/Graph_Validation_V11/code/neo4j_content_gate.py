"""Idempotent additive quality layer on the isolated June research graph."""
from pathlib import Path
from urllib.request import Request,urlopen
import json,hashlib,datetime
R=Path(__file__).resolve().parents[1]
POLICY={'version':'indication-content-v1','missing_markers':['','na','n/a','null','none','nan'],'target':'available lexical indication content','scope':'Availability of text only; documentary fidelity and clinical adequacy are separate targets.'}
policyhash=hashlib.sha256(json.dumps(POLICY,sort_keys=True).encode()).hexdigest()
def run(q,parameters=None):
 body=json.dumps({'statements':[{'statement':q,'parameters':parameters or {}}]}).encode()
 with urlopen(Request('http://127.0.0.1:17474/db/neo4j/tx/commit',data=body,headers={'Content-Type':'application/json'}),timeout=300) as f:response=json.load(f)
 assert not response['errors'],response['errors'];r=response['results'][0]
 return [dict(zip(r['columns'],x['row'])) for x in r['data']]
def fingerprint():
 rows=run('MATCH (a:IndicationAssertion) RETURN properties(a) AS assertion, [(a)-[:ABOUT_PRODUCT]->(p:ProductRef) | p.id] AS products, [(a)-[:SUPPORTED_BY]->(r:SourceRecord) | properties(r)] AS records ORDER BY a.id')
 return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),len(rows)
q='''MATCH (a:IndicationAssertion)
MERGE (q:IndicationContentAssessment {witness_id:a.id, policy_sha256:$policy})
SET q.content_available = a.term IS NOT NULL AND NOT toLower(trim(a.term)) IN $markers,
 q.evidence_target = 'available_indication_content',
 q.status = CASE WHEN a.term IS NULL OR toLower(trim(a.term)) IN $markers THEN 'MISSING' ELSE 'AVAILABLE' END
MERGE (a)-[:HAS_CONTENT_ASSESSMENT]->(q)
RETURN count(a) AS assessed'''
query='''MATCH (a:IndicationAssertion)-[:HAS_CONTENT_ASSESSMENT]->(q:IndicationContentAssessment)
WHERE q.policy_sha256=$policy AND q.content_available=true
RETURN a.subject AS product, a.term AS indication, a.kind AS source_kind, a.id AS witness_id
ORDER BY witness_id'''
before,n=fingerprint();assert n==17447
created=run(q,{'policy':policyhash,'markers':POLICY['missing_markers']})
after,n2=fingerprint();assert before==after and n==n2
ungated=run("MATCH (a:IndicationAssertion) WHERE a.kind='EMA_therapeutic_area_MeSH' RETURN count(a) AS paths, count(DISTINCT a.term) AS distinct_terms")
gated=run(query,{'policy':policyhash})
missing=run('MATCH (a:IndicationAssertion)-[:HAS_CONTENT_ASSESSMENT]->(q:IndicationContentAssessment) WHERE q.policy_sha256=$policy AND q.content_available=false RETURN a.id AS witness_id, a.term AS term, a.subject AS subject ORDER BY witness_id',{'policy':policyhash})
assert len(missing)==14 and len(gated)==17433
assert not any(x['indication'].strip().casefold() in POLICY['missing_markers'] for x in gated)
# Idempotence: repeated application does not add duplicate assessments or edges.
run(q,{'policy':policyhash,'markers':POLICY['missing_markers']})
census=run('MATCH (a:IndicationAssertion)-[r:HAS_CONTENT_ASSESSMENT]->(q:IndicationContentAssessment) WHERE q.policy_sha256=$policy RETURN count(r) AS edges,count(DISTINCT q) AS nodes',{'policy':policyhash})[0]
assert census=={'edges':17447,'nodes':17447}
summary={'executed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'graph':'isolated June research store','policy':POLICY,'policy_sha256':policyhash,'all_indication_paths':n,'eligible_indication_paths':len(gated),'excluded_missing_paths':len(missing),'EMA_MeSH_ungated':ungated[0]['paths'],'EMA_MeSH_gated':sum(x['source_kind']=='EMA_therapeutic_area_MeSH' for x in gated),'original_assertion_and_premise_fingerprint_before':before,'original_assertion_and_premise_fingerprint_after':after,'original_evidence_unchanged':before==after,'idempotence':census,'remediation':'Additive versioned content assessments; gated query excludes missing content while preserving original assertions.'}
(R/'results/neo4j_content_gate.json').write_text(json.dumps(summary,indent=2))
(R/'results/excluded_missing_content.json').write_text(json.dumps(missing,indent=2))
(R/'queries/create_content_assessment.cypher').write_text(q+';\n')
(R/'queries/available_indications.cypher').write_text(query+';\n')
print(json.dumps(summary,indent=2))
