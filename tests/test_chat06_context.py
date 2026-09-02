import pytest
from knowledge.context_contract import STATUS_MAP, publishability, validate_context_pack

def pack(status="VERIFIED"):
    return {"pack_id":"kp-1","version":"1.0.0","status":status,"generated_at":"2026-09-02T10:30:00Z","provenance":{"source":"canonical-registry","source_date":"2026-09-02"},"payload":{"summary":"safe derived context"}}
def test_existing_manifest_verification_levels_are_mapped_non_destructively():
    assert STATUS_MAP["VERIFIED_PRIMARY_SOURCE"]=="VERIFIED"; assert STATUS_MAP["HIGH_CONFIDENCE"]=="SUPPORTED"; assert STATUS_MAP["ANALYSIS"]=="TO_VERIFY"; assert STATUS_MAP["DRAFT"]=="TO_VERIFY"; assert STATUS_MAP["CONFLICT"]=="TO_VERIFY"; assert STATUS_MAP["OBSOLETE"]=="UNKNOWN"
def test_context_pack_requires_provenance_and_version():
    candidate=pack(); candidate.pop("version")
    with pytest.raises(ValueError): validate_context_pack(candidate)
    candidate=pack(); candidate["provenance"]={}
    with pytest.raises(ValueError): validate_context_pack(candidate)
def test_private_user_evidence_is_rejected_from_context_pack():
    candidate=pack(); candidate["provenance"]["private_evidence"]=True
    with pytest.raises(ValueError): validate_context_pack(candidate)
def test_analysis_is_to_verify_for_domain_consumers():
    result=validate_context_pack(pack("ANALYSIS")); assert result["status"]=="TO_VERIFY"; assert result["truth_label"]=="TO_VERIFY"
def test_verified_primary_source_is_derived_context_not_domain_promotion():
    result=validate_context_pack(pack("VERIFIED_PRIMARY_SOURCE")); assert result["status"]=="VERIFIED"; assert result["truth_label"]=="DERIVED"
def test_publishability_preserves_global_manifest_policy():
    assert publishability("VERIFIED_PRIMARY_SOURCE")=="ALLOW"; assert publishability("HIGH_CONFIDENCE")=="ALLOW"; assert publishability("ANALYSIS")=="ALLOW_WITH_ANALYSIS_LABEL"; assert publishability("DRAFT")=="DENY"; assert publishability("CONFLICT")=="DENY"; assert publishability("NOT_A_STATUS")=="TO_VERIFY"
