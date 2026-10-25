"""Selective verifier of structured, witness-indexed documentary claims.
No natural-language parsing and no clinical truth oracle are implemented.
"""
import json, hashlib
V='VERIFIED'; C='CONTRADICTED'; U='UNDETERMINED'
RESIDUAL_OBLIGATIONS={
 'payment_eligibility':['applicable_tariff_version','treatment_and_dose_context','eligibility_conditions'],
 'current_authorized_classification':['product_specific_authoritative_validity','effective_date'],
 'source_exclusivity':['authoritative_source_completeness','declared_population_and_time_boundary'],
}
REASON_OBLIGATIONS={
 'evidence_unavailable':['retrieved_witness_evidence'],
 'unavailable_requested_snapshot':['requested_snapshot_evidence'],
 'product_specific_validity_unavailable':['product_specific_authoritative_validity','effective_date'],
}
def digest(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
class EvidenceJudge:
 def __init__(self,reference): self.ref=reference
 def assess(self,claim,bundle,mode='full'):
  def answer(verdict,reason):
   item={'claim_id':digest(claim),'verdict':verdict,'reason':reason,'witness':claim.get('witness'),'reference_implementation':self.ref.implementation_sha,'mode':mode}
   item['unmet_obligations']=(RESIDUAL_OBLIGATIONS.get(claim.get('kind'),['implemented_claim_contract']) if reason=='unsupported_claim_scope' else REASON_OBLIGATIONS.get(reason,['valid_documentary_certificate'] if verdict==U else []))
   item['decision_sha256']=digest(item);return item
  if mode=='always_abstain':return answer(U,'no_verification_attempted')
  if not isinstance(bundle,dict) or not bundle.get('association'): return answer(U,'evidence_unavailable')
  a=bundle['association'];wid=claim.get('witness')
  # Stronger policy comparator: checks asserted metadata and scope, but trusts the bundle.
  if mode=='schema':
   if a.get('id')!=wid:return answer(U,'certificate_identity_mismatch')
   for key in ['subject','atc','rule','jurisdiction']:
    if claim.get(key)!=a.get(key):return answer(C,'witness_contradicts_'+key)
   if claim.get('kind')!='documentary_association':return answer(U,'unsupported_claim_scope')
   if claim.get('source_snapshot')!=self.ref.files['atc_list.csv']:return answer(U,'unavailable_requested_snapshot')
   if claim.get('time_scope')!='frozen_documentary':return answer(U,'product_specific_validity_unavailable')
   return answer(V,'metadata_and_scope_match')
  # Path existence is intentionally a permissive comparator.
  if mode=='path':return answer(V,'path_exists')
  if a.get('id')!=wid:return answer(U,'certificate_identity_mismatch')
  props={k:v for k,v in a.items() if k!='id'}
  if digest(props)!=wid:return answer(U,'association_hash_invalid')
  if bundle.get('products')!=[a.get('subject')] or bundle.get('targets')!=[a.get('atc')]:return answer(U,'physical_endpoint_invalid')
  premises=bundle.get('records',[])
  if sorted(r.get('id','') for r in premises)!=sorted(a.get('premise_ids',[])):return answer(U,'physical_premise_invalid')
  for r in premises:
   try:payload=json.loads(r['payload_json'])
   except (ValueError,KeyError,TypeError):return answer(U,'payload_unreadable')
   if digest(payload)!=r.get('record_sha256'):return answer(U,'payload_hash_invalid')
  if mode=='lineage':return answer(V,'locally_consistent_lineage')
  expected=self.ref.witnesses.get(wid)
  if expected!=a:return answer(U,'independent_derivation_failed')
  for r in premises:
   rid=r['id'];filename=rid.split(':',1)[0]
   if json.loads(r['payload_json'])!=self.ref.records.get(rid) or r.get('file_sha256')!=self.ref.files.get(filename):return answer(U,'frozen_source_mismatch')
  # These fields describe the selected witness, not an existential global claim.
  for key in ['subject','atc','rule','jurisdiction']:
   if claim.get(key)!=expected[key]:return answer(C,'witness_contradicts_'+key)
  if mode=='derivation':return answer(V,'derivation_matches')
  if claim.get('kind')!='documentary_association':return answer(U,'unsupported_claim_scope')
  if claim.get('source_snapshot')!=self.ref.files['atc_list.csv']:return answer(U,'unavailable_requested_snapshot')
  if claim.get('time_scope')!='frozen_documentary':return answer(U,'product_specific_validity_unavailable')
  return answer(V,'all_documentary_obligations_satisfied')
