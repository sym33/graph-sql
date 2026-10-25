"""Composable documentary contract; each omitted obligation is a targeted ablation."""
import json
from indication_reference import digest
FIELDS=('subject','term','kind','jurisdiction')
STAGES=('source_binding','physical_endpoints','claim_fields','scope')

def assess(claim,bundle,reference,omit=None):
    def decision(verdict,reason,missing=()):
        row={'verdict':verdict,'reason':reason,'unmet_obligations':list(missing),'claim_sha256':digest(claim),'omitted_stage':omit}
        row['decision_sha256']=digest(row);return row
    if not isinstance(bundle,dict) or not bundle.get('assertion'):
        return decision('UNDETERMINED','evidence_unavailable',('selected_assertion',))
    assertion=bundle['assertion'];wid=claim.get('witness')
    expected=reference.assertions.get(wid)
    if assertion.get('id')!=wid or digest({k:v for k,v in assertion.items() if k!='id'})!=wid or expected!=assertion:
        return decision('UNDETERMINED','derivation_certificate_invalid',('reference_derivation',))
    records=bundle.get('records',[])
    if len(records)!=1 or records[0].get('id')!=assertion.get('record_id'):
        return decision('UNDETERMINED','source_premise_invalid',('exact_source_premise',))
    record=records[0]
    try:payload=json.loads(record['payload_json'])
    except (TypeError,KeyError,ValueError):return decision('UNDETERMINED','unreadable_source_payload',('source_payload',))
    if digest(payload)!=record.get('record_sha256'):
        return decision('UNDETERMINED','payload_integrity_invalid',('payload_digest',))
    filename=record['id'].split(':',1)[0]
    if omit!='source_binding' and (payload!=reference.records.get(record['id']) or record.get('file_sha256')!=reference.files.get(filename)):
        return decision('UNDETERMINED','source_binding_invalid',('frozen_source_bytes',))
    if omit!='physical_endpoints' and (bundle.get('products')!=[assertion['subject']]):
        return decision('UNDETERMINED','physical_endpoint_invalid',('scoped_product_endpoint',))
    if omit!='claim_fields':
        for field in FIELDS:
            if claim.get(field)!=expected.get(field):return decision('CONTRADICTED','witness_contradicts_'+field)
    if omit!='scope':
        if claim.get('source_snapshot')!=reference.files[filename]:return decision('UNDETERMINED','requested_snapshot_unavailable',('requested_source_snapshot',))
        if claim.get('time_scope')!='frozen_documentary':return decision('UNDETERMINED','current_validity_unavailable',('product_specific_authority','effective_date'))
        if claim.get('statement_kind')!='source_recorded_indication':return decision('UNDETERMINED','requested_scope_unavailable',('scope_specific_evidence',))
    return decision('VERIFIED','documentary_contract_satisfied')
