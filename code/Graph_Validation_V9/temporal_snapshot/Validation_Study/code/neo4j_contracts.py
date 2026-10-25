"""Executable Cypher contracts and independent premise-level verification."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'code'))
from run_baseline import query
from reference_oracle import canonical_hash
# Each returns violating association IDs; nulls are explicitly violations.
CONTRACTS={
 'required_fields':("shape",'''MATCH (a:Association) WHERE ($ids IS NULL OR a.id IN $ids) AND any(k IN ['id','subject','atc','rule','premise_ids','jurisdiction','evidence_status','implementation_sha256','atc_index_snapshot_sha256','validity_status','atc_in_snapshot'] WHERE a[k] IS NULL) RETURN a.id AS id'''),
 'premise_cardinality':("shape",'''MATCH (a:Association) WHERE $ids IS NULL OR a.id IN $ids OPTIONAL MATCH (a)-[e:SUPPORTED_BY]->(r) WITH a,count(e) AS edges,count(DISTINCT r) AS nodes WHERE edges<>size(a.premise_ids) OR nodes<>size(a.premise_ids) OR edges=0 RETURN a.id AS id'''),
 'target_cardinality':("shape",'''MATCH (a:Association) WHERE $ids IS NULL OR a.id IN $ids OPTIONAL MATCH (a)-[e:TARGET_ATC]->(r) WITH a,count(e) AS n WHERE n<>1 RETURN a.id AS id'''),
 'product_cardinality':("shape",'''MATCH (a:Association) WHERE $ids IS NULL OR a.id IN $ids OPTIONAL MATCH (a)-[e:ABOUT_PRODUCT]->(r) WITH a,count(e) AS n WHERE n<>1 RETURN a.id AS id'''),
 'rule_cardinality':("shape",'''MATCH (a:Association) WHERE $ids IS NULL OR a.id IN $ids OPTIONAL MATCH (a)-[e:GENERATED_BY]->(r) WITH a,count(e) AS n WHERE n<>1 RETURN a.id AS id'''),
 'dictionary_cardinality':("shape",'''MATCH (a:Association) WHERE $ids IS NULL OR a.id IN $ids OPTIONAL MATCH (a)-[e:CHECKED_AGAINST]->(r) WITH a,count(e) AS n WHERE n<>1 RETURN a.id AS id'''),
 'exact_premise_identity':("provenance",'''MATCH (a:Association)-[:SUPPORTED_BY]->(r) WHERE ($ids IS NULL OR a.id IN $ids) AND (NOT r:SourceRecord OR r.id IS NULL OR NOT r.id IN a.premise_ids) RETURN DISTINCT a.id AS id'''),
 'target_identity':("provenance",'''MATCH (a:Association)-[:TARGET_ATC]->(r) WHERE ($ids IS NULL OR a.id IN $ids) AND (NOT r:ATCConcept OR r.id IS NULL OR a.atc IS NULL OR r.id<>a.atc OR r.in_atc_snapshot<>a.atc_in_snapshot) RETURN a.id AS id'''),
 'product_identity':("provenance",'''MATCH (a:Association)-[:ABOUT_PRODUCT]->(r) WHERE ($ids IS NULL OR a.id IN $ids) AND (NOT r:ProductRef OR r.id IS NULL OR a.subject IS NULL OR r.id<>a.subject) RETURN a.id AS id'''),
 'rule_identity':("provenance",'''MATCH (a:Association)-[:GENERATED_BY]->(r) WHERE ($ids IS NULL OR a.id IN $ids) AND (NOT r:Rule OR r.name IS NULL OR r.name<>a.rule OR r.implementation_sha256<>a.implementation_sha256) RETURN a.id AS id'''),
 'dictionary_identity':("provenance",'''MATCH (a:Association)-[:CHECKED_AGAINST]->(r) WHERE ($ids IS NULL OR a.id IN $ids) AND (NOT r:SourceSnapshot OR r.id IS NULL OR r.id<>a.atc_index_snapshot_sha256 OR r.file<>'atc_list.csv') RETURN a.id AS id'''),
 'jurisdiction_scope':("provenance",'''MATCH (a:Association) WHERE ($ids IS NULL OR a.id IN $ids) AND (a.jurisdiction IS NULL OR (a.subject STARTS WITH 'CH:' AND a.jurisdiction<>'CH') OR (a.subject STARTS WITH 'EMA:' AND a.jurisdiction<>'EU') OR NOT (a.subject STARTS WITH 'CH:' OR a.subject STARTS WITH 'EMA:')) RETURN a.id AS id'''),
 'historical_context':("provenance",'''MATCH (a:Association) WHERE ($ids IS NULL OR a.id IN $ids) AND a.rule='historical_candidate' AND (a.origin_atc IS NULL OR a.alteration_year IS NULL OR NOT a.evidence_status IN ['context_review_required','historical_mapping_candidate'] OR a.validity_status<>'unknown_product_specific_validity') RETURN a.id AS id'''),
}
class Validator:
 def __init__(self,reference,query_fn=query):self.ref=reference;self.query=query_fn
 def evaluate(self,ids=None,indication_ids=None,full=False):
    query=self.query
    out={'shape':{},'provenance':{},'reference':{}}
    for name,(tier,statement) in CONTRACTS.items():
        bad=query(statement,{'ids':ids});out[tier][name]=[x['id'] for x in bad]
    actual=query('MATCH (a:Association) WHERE $ids IS NULL OR a.id IN $ids RETURN properties(a) AS p',{'ids':ids})
    badhash=[];badref=[]
    for row in actual:
        item=dict(row['p']);id=item.pop('id',None)
        if isinstance(item.get('premise_ids'),list):item['premise_ids']=sorted(set(item['premise_ids']))
        if canonical_hash(item)!=id:badhash.append(id)
        normalized={'id':id,**item}
        if self.ref.witnesses.get(id)!=normalized:badref.append(id)
    expected=set(self.ref.witnesses) if full else set(ids or [])&set(self.ref.witnesses)
    observed={row['p'].get('id') for row in actual};out['reference']['expected_witnesses']=sorted(expected-observed)+badref
    out['provenance']['association_content_hash']=badhash
    record_query='''MATCH (r:SourceRecord) WHERE $full OR EXISTS { MATCH (a:Association)-[:SUPPORTED_BY]->(r) WHERE $ids IS NULL OR a.id IN $ids } RETURN properties(r) AS p, [(r)-[:IN_SNAPSHOT]->(s) | {id:s.id,file:s.file}] AS snapshots'''
    # For indication-only mutations include their actual premise explicitly.
    if indication_ids is not None and not full:
        records=query('MATCH (i:IndicationAssertion)-[:SUPPORTED_BY]->(r:SourceRecord) WHERE i.id IN $ids RETURN DISTINCT properties(r) AS p, [(r)-[:IN_SNAPSHOT]->(s) | {id:s.id,file:s.file}] AS snapshots',{'ids':indication_ids})
    else:records=query(record_query,{'full':full,'ids':ids or []})
    badpayload=[];badsnapshot=[];badsource=[]
    for row in records:
        r=row['p'];rid=r.get('id')
        try:payload=json.loads(r['payload_json']);ok=canonical_hash(payload)==r['record_sha256']
        except (ValueError,KeyError,TypeError):payload=None;ok=False
        if not ok:badpayload.append(rid)
        if row['snapshots']!=[{'id':r.get('file_sha256'),'file':r.get('file')}]:badsnapshot.append(rid)
        if payload!=self.ref.records.get(rid) or self.ref.files.get(r.get('file'))!=r.get('file_sha256'):badsource.append(rid)
    out['provenance']['record_payload_hash']=badpayload;out['provenance']['record_snapshot_identity']=badsnapshot;out['reference']['frozen_source_payload']=badsource
    # Compare physical premise IDs, not just the redundant premise_ids property.
    physical=query('MATCH (a:Association) WHERE $ids IS NULL OR a.id IN $ids OPTIONAL MATCH (a)-[:SUPPORTED_BY]->(r) RETURN a.id AS id,collect(r.id) AS premises',{'ids':ids})
    out['reference']['physical_reference_premises']=[row['id'] for row in physical if row['id'] not in self.ref.witnesses or sorted(row['premises'])!=self.ref.witnesses[row['id']]['premise_ids']]
    if full or indication_ids is not None:
        indications=query('MATCH (i:IndicationAssertion) WHERE $ids IS NULL OR i.id IN $ids RETURN properties(i) AS p, [(i)-[:ABOUT_PRODUCT]->(p) | p.id] AS products, [(i)-[:SUPPORTED_BY]->(r) | r.id] AS premises',{'ids':indication_ids})
        out['reference']['indication_assertion']=[];out['provenance']['indication_links']=[]
        for row in indications:
            i=row['p'];id=i.get('id')
            if self.ref.indications.get(id)!=i:out['reference']['indication_assertion'].append(id)
            if row['products']!=[i.get('subject')] or row['premises']!=[i.get('record_id')]:out['provenance']['indication_links'].append(id)
        if full:out['reference']['missing_indications']=sorted(set(self.ref.indications)-{row['p'].get('id') for row in indications})
    return out

def violations(report,tier=None):
    groups=report.values() if tier is None else [report[tier]]
    return sum(len(ids) for group in groups for ids in group.values())
