#!/usr/bin/env python3
"""Fail-closed guard for the 48H CryptoAID MVP release authority boundary.

This guard does not define Case economics. It prevents DevOps/deployment metadata
from becoming a second Case-payment authority and keeps real contract settlement
out of the MVP release path until the domain authority and HUMAN_GATE approve it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CANONICAL_CHAIN_ID = 137
CANONICAL_CASE_TREASURY = "0x3C320B3a0917fF44BF6551CDdee44402AFcF250C"
REQUIRED_MVP_SETTLEMENT_MODE = "SANDBOX_ONLY_NO_CONTRACT_DEPLOY"
REQUIRED_CASE_AUTHORITY = "CHAT02_EVIDENCE_PAYMENT_ENTITLEMENT"
FORBIDDEN_ACTIVE_CASE_CONTRACT = "CryptoAIDCasePayment"
FORBIDDEN_STALE_ECONOMIC_MARKERS = (
    "onboarding 100",
    "first-case payment 400",
    "first case payment 400",
)


def validate_plan(plan: dict) -> list[str]:
    errors: list[str] = []

    if plan.get("chainId") != CANONICAL_CHAIN_ID:
        errors.append(f"chainId must be {CANONICAL_CHAIN_ID}")
    if plan.get("caseTreasury") != CANONICAL_CASE_TREASURY:
        errors.append("caseTreasury does not match the canonical control-plane address")
    if plan.get("humanGate") is not True:
        errors.append("humanGate must remain true")
    if plan.get("mvpCaseSettlement") != REQUIRED_MVP_SETTLEMENT_MODE:
        errors.append("MVP Case settlement must remain sandbox-only with no contract deploy")
    if plan.get("casePaymentAuthority") != REQUIRED_CASE_AUTHORITY:
        errors.append("deployment metadata must point to CHAT02 rather than define payment truth")
    if "paymentAsset" in plan:
        errors.append("top-level paymentAsset is ambiguous; deployment plan may define rewardAsset, not Case payment truth")

    exclusions = set(plan.get("mvpReleaseExclusions") or [])
    if FORBIDDEN_ACTIVE_CASE_CONTRACT not in exclusions:
        errors.append(f"{FORBIDDEN_ACTIVE_CASE_CONTRACT} must be explicitly excluded from the MVP release")

    for step in plan.get("steps") or []:
        if step.get("contract") != FORBIDDEN_ACTIVE_CASE_CONTRACT:
            continue
        disabled = step.get("enabled") is False
        post_mvp = step.get("phase") == "POST_MVP"
        if not (disabled and post_mvp):
            errors.append(f"{FORBIDDEN_ACTIVE_CASE_CONTRACT} must be disabled and POST_MVP")

    serialized = json.dumps(plan, sort_keys=True).lower()
    for marker in FORBIDDEN_STALE_ECONOMIC_MARKERS:
        if marker in serialized:
            errors.append(f"stale conflicting Case-economics marker present: {marker}")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs="?", type=Path, default=Path("web3/deploy/deployment-plan.json"))
    args = parser.parse_args()

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "errors": [f"cannot read deployment plan: {exc}"]}, indent=2))
        return 2

    errors = validate_plan(plan)
    payload = {
        "status": "PASS" if not errors else "FAIL",
        "plan": str(args.plan),
        "mvpCaseSettlement": plan.get("mvpCaseSettlement"),
        "casePaymentAuthority": plan.get("casePaymentAuthority"),
        "errors": errors,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
