"""Context-first contract with separate frozen-document comparison diagnostics."""
from pathlib import Path
import sys,json
P=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(P/'Graph_Validation_V10/code'))
from typed_contract import assess,FIELDS
from indication_reference import digest
MARKERS={'','na','n/a','null','none','nan'}
def evaluate(claim,bundle,reference,target='documentary_fidelity'):
 def answer(verdict,reason,comparison=None):
  out={'verdict':verdict,'reason':reason,'frozen_field_comparison':comparison,'claim_sha256':digest(claim),'evidence_target':target};out['decision_sha256']=digest(out);return out
 if target not in {'documentary_fidelity','available_indication_content'}:return answer('UNDETERMINED','unsupported_evidence_target')
 if not isinstance(claim,dict) or not isinstance(bundle,dict) or not isinstance(bundle.get('assertion'),dict) or not isinstance(bundle.get('records'),list):return answer('UNDETERMINED','malformed_certificate')
 a=bundle['assertion'];expected=reference.assertions.get(claim.get('witness'))
 if not expected:return answer('UNDETERMINED','selected_derivation_unavailable')
 faithful={**claim,**{f:expected[f] for f in FIELDS},'source_snapshot':reference.files[expected['record_id'].split(':')[0]],'time_scope':'frozen_documentary','statement_kind':'source_recorded_indication'}
 try:auth=assess(faithful,bundle,reference)
 except (TypeError,ValueError,KeyError,AttributeError):return answer('UNDETERMINED','malformed_certificate')
 if auth['verdict']!='VERIFIED':return answer('UNDETERMINED',auth['reason'])
 conflicts=[f for f in FIELDS if claim.get(f)!=expected[f]]
 comparison={'representation':'selected_frozen_source','conflicting_fields':conflicts,'agrees':not conflicts}
 if claim.get('source_snapshot')!=faithful['source_snapshot']:return answer('UNDETERMINED','requested_snapshot_unavailable',comparison)
 if claim.get('time_scope')!='frozen_documentary':return answer('UNDETERMINED','requested_time_unavailable',comparison)
 if claim.get('statement_kind')!='source_recorded_indication':return answer('UNDETERMINED','requested_statement_unavailable',comparison)
 if target=='available_indication_content' and (not isinstance(a.get('term'),str) or a['term'].strip().casefold() in MARKERS):return answer('UNDETERMINED','missing_content',comparison)
 if conflicts:return answer('CONTRADICTED','authenticated_requested_context_field_conflict',comparison)
 return answer('VERIFIED','requested_context_contract_satisfied',comparison)

def evaluate_classification(claim,bundle,reference):
 sys.path.insert(0,str(P/'Automated_Verification/code'))
 from evidence_judge import EvidenceJudge
 judge=EvidenceJudge(reference)
 a=bundle.get('association',{}) if isinstance(bundle,dict) else {}
 expected=reference.witnesses.get(claim.get('witness'))
 if not expected:return {'verdict':'UNDETERMINED','reason':'derivation_unavailable'}
 faithful={**claim,**{k:expected[k] for k in ['subject','atc','rule','jurisdiction']},'kind':'documentary_association','source_snapshot':reference.files['atc_list.csv'],'time_scope':'frozen_documentary'}
 try:auth=judge.assess(faithful,bundle)
 except (TypeError,ValueError,KeyError,AttributeError):return {'verdict':'UNDETERMINED','reason':'malformed_certificate'}
 if auth['verdict']!='VERIFIED':return auth
 comparison={'agrees':all(claim.get(k)==expected[k] for k in ['subject','atc','rule','jurisdiction'])}
 if any(claim.get(k)!=faithful[k] for k in ['kind','source_snapshot','time_scope']):return {'verdict':'UNDETERMINED','reason':'requested_context_unavailable','frozen_field_comparison':comparison}
 out=judge.assess(claim,bundle);out['frozen_field_comparison']=comparison;return out

def evaluate_attribution(claim,evidence,audited_reference):
 """Targets over the 22 archive-bound physically audited intervention certificates."""
 def result(verdict,reason,diagnostic=None):
  out={'verdict':verdict,'reason':reason,'claim_sha256':digest(claim),'selected_witness':evidence.get('witness_id') if isinstance(evidence,dict) else None,'frozen_field_comparison':diagnostic};out['decision_sha256']=digest(out);return out
 if not isinstance(claim,dict) or not isinstance(evidence,dict):return result('UNDETERMINED','certificate_unavailable')
 ref=audited_reference.get(evidence.get('witness_id'))
 keys=['authorization','witness_id','source_record','raw_archive_sha256','raw_member','raw_code','staged_code']
 if not ref or any(evidence.get(k)!=ref.get(k) for k in keys):return result('UNDETERMINED','audited_source_binding_unavailable')
 target=claim.get('evidence_target')
 if target not in {'raw_refdata_field','curated_staging_field'}:return result('UNDETERMINED','requested_target_context_unavailable')
 snapshot=ref['raw_archive_sha256'] if target=='raw_refdata_field' else ref['source_record'].split(':')[1]
 value=ref['raw_code' if target=='raw_refdata_field' else 'staged_code']
 diagnostic={'representation':target,'agrees':claim.get('authorization')==ref['authorization'] and claim.get('value')==value}
 if claim.get('time_scope','frozen_documentary')!='frozen_documentary' or claim.get('source_snapshot',snapshot)!=snapshot:return result('UNDETERMINED','requested_context_unavailable',diagnostic)
 return result('VERIFIED' if diagnostic['agrees'] else 'CONTRADICTED','audited_documentary_target_comparison',diagnostic)
