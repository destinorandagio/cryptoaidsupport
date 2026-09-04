from copy import deepcopy
from pathlib import Path
from scripts.check_mvp_authority import CANONICAL_CASE_TREASURY, REQUIRED_CASE_AUTHORITY, REQUIRED_MANIFEST_PURPOSE, REQUIRED_MVP_SETTLEMENT_MODE, validate_bundle, validate_deployer_source, validate_exporter_source, validate_manifest, validate_plan
ROOT=Path(__file__).resolve().parents[1]

def valid_plan():
    return {"chainId":137,"humanGate":True,"caseTreasury":CANONICAL_CASE_TREASURY,"rewardAsset":"USDT","mvpCaseSettlement":REQUIRED_MVP_SETTLEMENT_MODE,"casePaymentAuthority":REQUIRED_CASE_AUTHORITY,"mvpReleaseExclusions":["CryptoAIDCasePayment"],"steps":[{"contract":"CryptoAIDCasePayment","enabled":False,"phase":"POST_MVP","notes":"Excluded from 48H MVP release path."},{"contract":"CryptoAIDUSDTRewardRouter","external_tokens":["USDT"]}]}

def valid_manifest():
    return {"chainId":137,"manifestPurpose":REQUIRED_MANIFEST_PURPOSE,"mvpCaseSettlement":REQUIRED_MVP_SETTLEMENT_MODE,"casePaymentAuthority":REQUIRED_CASE_AUTHORITY,"mvpReleaseExclusions":["CryptoAIDCasePayment"],"externalTokens":{"USDT0":"0xc2132D05D31c914a87C6611C10748AEb04B58e8F"},"contracts":{"CryptoAIDCasePayment":"0x47faA2541b69944bABD7045E68CdE0C7FF5223c5"}}

def test_valid_plan_passes_without_defining_case_economics(): assert validate_plan(valid_plan())==[]
def test_active_parallel_case_contract_fails_closed():
    p=valid_plan(); p["steps"][0]["enabled"]=True; p["steps"][0]["phase"]="MVP"; assert any("enabled=false" in e for e in validate_plan(p))
def test_ambiguous_top_level_payment_asset_fails_closed():
    p=valid_plan(); p["paymentAsset"]="USDT"; assert any("paymentAsset" in e for e in validate_plan(p))
def test_stale_conflicting_case_economics_marker_fails_closed():
    p=valid_plan(); p["steps"][0]["notes"]="onboarding 100, first-case payment 400, subsequent 500"; e=validate_plan(p); assert any("onboarding 100" in x for x in e) and any("first-case payment 400" in x for x in e)
def test_wrong_chain_or_treasury_fails_closed():
    p=valid_plan(); p["chainId"]=1; p["caseTreasury"]="0x0000000000000000000000000000000000000000"; e=validate_plan(p); assert any("chainId" in x for x in e) and any("caseTreasury" in x for x in e)
def test_missing_chat02_authority_or_exclusion_fails_closed():
    p=deepcopy(valid_plan()); p["casePaymentAuthority"]="WEB3_DEPLOYMENT_PLAN"; p["mvpReleaseExclusions"]=[]; e=validate_plan(p); assert any("CHAT02" in x for x in e) and any("explicitly excluded" in x for x in e)
def test_valid_polygon_manifest_is_factual_inventory_only(): assert validate_manifest(valid_manifest())==[]
def test_polygon_manifest_cannot_define_case_payment_asset():
    m=valid_manifest(); m["paymentAsset"]="USDT0"; assert any("paymentAsset" in e for e in validate_manifest(m))
def test_polygon_manifest_requires_factual_purpose_chat02_and_exclusion():
    m=valid_manifest(); m["manifestPurpose"]="PAYMENT_AUTHORITY"; m["casePaymentAuthority"]="WEB3"; m["mvpReleaseExclusions"]=[]; e=validate_manifest(m); assert any("factual" in x for x in e) and any("CHAT02" in x for x in e) and any("exclude" in x for x in e)
def test_polygon_manifest_may_retain_casepayment_only_as_address_inventory():
    m=valid_manifest(); assert validate_manifest(m)==[]; m["contracts"]["CryptoAIDCasePayment"]=""; assert any("deployed-address inventory" in e for e in validate_manifest(m))
def test_bundle_rejects_casepayment_even_if_plan_metadata_is_bypassed():
    b={"target":{"chainId":137},"mvpCaseSettlement":REQUIRED_MVP_SETTLEMENT_MODE,"casePaymentAuthority":REQUIRED_CASE_AUTHORITY,"contracts":[{"name":"CryptoAIDCasePayment"}]}; assert any("must not contain" in e for e in validate_bundle(b))
def test_repository_deployer_blocks_selector_guided_next_preflight_deploy_and_output_bypass(): assert validate_deployer_source((ROOT/"web3/deploy/index.html").read_text(encoding="utf-8"))==[]
def test_repository_exporter_excludes_plan_quarantined_contracts(): assert validate_exporter_source((ROOT/"web3/scripts/export-deploy-bundle.js").read_text(encoding="utf-8"))==[]
def test_repository_polygon_manifest_passes_factual_inventory_guard(): assert validate_manifest(__import__("json").loads((ROOT/"web3/deploy/polygon-mainnet-manifest.json").read_text(encoding="utf-8")))==[]
