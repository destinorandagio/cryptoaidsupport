#!/usr/bin/env python3
"""Fail-closed guard for the CryptoAID 48H MVP Case-payment authority boundary."""
from __future__ import annotations
import argparse, json
from pathlib import Path

CANONICAL_CHAIN_ID=137
CANONICAL_CASE_TREASURY="0x3C320B3a0917fF44BF6551CDdee44402AFcF250C"
REQUIRED_MVP_SETTLEMENT_MODE="SANDBOX_ONLY_NO_CONTRACT_DEPLOY"
REQUIRED_CASE_AUTHORITY="CHAT02_EVIDENCE_PAYMENT_ENTITLEMENT"
FORBIDDEN_CASE_CONTRACT="CryptoAIDCasePayment"
FORBIDDEN_STALE_ECONOMIC_MARKERS=("onboarding 100","first-case payment 400","first case payment 400")

def validate_plan(plan:dict)->list[str]:
    errors=[]
    if plan.get("chainId")!=CANONICAL_CHAIN_ID: errors.append("chainId must be 137")
    if plan.get("caseTreasury")!=CANONICAL_CASE_TREASURY: errors.append("caseTreasury does not match canonical control-plane address")
    if plan.get("humanGate") is not True: errors.append("humanGate must remain true")
    if plan.get("mvpCaseSettlement")!=REQUIRED_MVP_SETTLEMENT_MODE: errors.append("MVP Case settlement must remain sandbox-only with no contract deploy")
    if plan.get("casePaymentAuthority")!=REQUIRED_CASE_AUTHORITY: errors.append("deployment metadata must point to CHAT02 rather than define Case payment truth")
    if "paymentAsset" in plan: errors.append("top-level paymentAsset is forbidden in the MVP deployment plan")
    exclusions=set(plan.get("mvpReleaseExclusions") or [])
    if FORBIDDEN_CASE_CONTRACT not in exclusions: errors.append(f"{FORBIDDEN_CASE_CONTRACT} must be explicitly excluded from the MVP release")
    steps=[s for s in (plan.get("steps") or []) if s.get("contract")==FORBIDDEN_CASE_CONTRACT]
    if len(steps)!=1: errors.append(f"deployment plan must contain exactly one quarantined {FORBIDDEN_CASE_CONTRACT} step")
    elif steps[0].get("enabled") is not False or steps[0].get("phase")!="POST_MVP": errors.append(f"{FORBIDDEN_CASE_CONTRACT} must be enabled=false and phase=POST_MVP")
    serialized=json.dumps(plan,sort_keys=True).lower()
    for marker in FORBIDDEN_STALE_ECONOMIC_MARKERS:
        if marker in serialized: errors.append(f"stale conflicting Case-economics marker present: {marker}")
    return sorted(set(errors))

def validate_deployer_source(source:str)->list[str]:
    errors=[]
    required={
      "hard forbidden contract constant":"FORBIDDEN_CASE_CONTRACT='CryptoAIDCasePayment'",
      "deployability policy":"function isMvpDeployableStep(s)",
      "enabled=false exclusion":"s.enabled!==false",
      "POST_MVP exclusion":"s.phase!=='POST_MVP'",
      "plan exclusion list":"plan?.mvpReleaseExclusions",
      "selector filters plan":"plan.steps.filter(isMvpDeployableStep)",
      "explicit deploy/preflight block":"Contract excluded from 48H MVP release",
      "bundle rejects forbidden contract":"Bundle contains forbidden MVP Case-payment contract",
      "Guided Next uses deployable list":"deployableSteps().find",
      "sandbox output truth":"mvpCaseSettlement:'SANDBOX_ONLY_NO_CONTRACT_DEPLOY'",
      "CHAT02 output truth":"casePaymentAuthority:'CHAT02_EVIDENCE_PAYMENT_ENTITLEMENT'"}
    for label,marker in required.items():
        if marker not in source: errors.append(f"deployer missing {label}: {marker}")
    for forbidden in ("Payments USDT","paymentAsset:'USDT'",'paymentAsset:"USDT"'):
        if forbidden in source: errors.append(f"deployer still exposes forbidden Case-payment wording: {forbidden}")
    return sorted(set(errors))

def validate_exporter_source(source:str)->list[str]:
    errors=[]
    required={"reads deployment plan":"deployment-plan.json","reads mvp release exclusions":"mvpReleaseExclusions","hard requires CasePayment exclusion":"CryptoAIDCasePayment","filters excluded artifacts":"exclusions.has(artifact.contractName)","bundle carries settlement mode":"mvpCaseSettlement","bundle carries Case authority":"casePaymentAuthority"}
    for label,marker in required.items():
        if marker not in source: errors.append(f"bundle exporter missing {label}: {marker}")
    return sorted(set(errors))

def validate_bundle(bundle:dict)->list[str]:
    errors=[]
    if bundle.get("target",{}).get("chainId")!=CANONICAL_CHAIN_ID: errors.append("deploy bundle target chainId must be 137")
    if bundle.get("mvpCaseSettlement")!=REQUIRED_MVP_SETTLEMENT_MODE: errors.append("deploy bundle must declare sandbox-only Case settlement")
    if bundle.get("casePaymentAuthority")!=REQUIRED_CASE_AUTHORITY: errors.append("deploy bundle must declare CHAT02 Case-payment authority")
    if FORBIDDEN_CASE_CONTRACT in {c.get("name") for c in bundle.get("contracts") or []}: errors.append(f"deploy bundle must not contain {FORBIDDEN_CASE_CONTRACT}")
    return sorted(set(errors))

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("plan",nargs="?",type=Path,default=Path("web3/deploy/deployment-plan.json")); p.add_argument("--deployer",type=Path,default=Path("web3/deploy/index.html")); p.add_argument("--exporter",type=Path,default=Path("web3/scripts/export-deploy-bundle.js")); p.add_argument("--bundle",type=Path); a=p.parse_args(); errors=[]
    try:
        plan=json.loads(a.plan.read_text(encoding="utf-8")); errors+=validate_plan(plan); errors+=validate_deployer_source(a.deployer.read_text(encoding="utf-8")); errors+=validate_exporter_source(a.exporter.read_text(encoding="utf-8"));
        if a.bundle: errors+=validate_bundle(json.loads(a.bundle.read_text(encoding="utf-8")))
    except (OSError,json.JSONDecodeError) as e: errors.append(f"cannot read release authority surface: {e}")
    print(json.dumps({"status":"PASS" if not errors else "FAIL","plan":str(a.plan),"deployer":str(a.deployer),"exporter":str(a.exporter),"bundle":str(a.bundle) if a.bundle else None,"errors":sorted(set(errors))},indent=2,sort_keys=True)); return 0 if not errors else 2
if __name__=="__main__": raise SystemExit(main())
