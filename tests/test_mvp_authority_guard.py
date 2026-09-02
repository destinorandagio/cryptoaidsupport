from copy import deepcopy

from scripts.check_mvp_authority import (
    CANONICAL_CASE_TREASURY,
    REQUIRED_CASE_AUTHORITY,
    REQUIRED_MVP_SETTLEMENT_MODE,
    validate_plan,
)


def valid_plan():
    return {
        "chainId": 137,
        "humanGate": True,
        "caseTreasury": CANONICAL_CASE_TREASURY,
        "rewardAsset": "USDT",
        "mvpCaseSettlement": REQUIRED_MVP_SETTLEMENT_MODE,
        "casePaymentAuthority": REQUIRED_CASE_AUTHORITY,
        "mvpReleaseExclusions": ["CryptoAIDCasePayment"],
        "steps": [
            {
                "contract": "CryptoAIDCasePayment",
                "enabled": False,
                "phase": "POST_MVP",
                "notes": "Not part of the 48H MVP release path.",
            },
            {"contract": "CryptoAIDUSDTRewardRouter", "external_tokens": ["USDT"]},
        ],
    }


def test_valid_plan_passes_without_defining_case_economics():
    plan = valid_plan()
    assert "activation" not in plan
    assert "firstCase" not in plan
    assert validate_plan(plan) == []


def test_active_parallel_case_contract_fails_closed():
    plan = valid_plan()
    plan["steps"][0]["enabled"] = True
    plan["steps"][0]["phase"] = "MVP"
    errors = validate_plan(plan)
    assert any("disabled and POST_MVP" in error for error in errors)


def test_ambiguous_top_level_payment_asset_fails_closed():
    plan = valid_plan()
    plan["paymentAsset"] = "USDT"
    assert any("paymentAsset" in error for error in validate_plan(plan))


def test_stale_conflicting_case_economics_marker_fails_closed():
    plan = valid_plan()
    plan["steps"][0]["notes"] = "onboarding 100, first-case payment 400, subsequent 500"
    errors = validate_plan(plan)
    assert any("onboarding 100" in error for error in errors)
    assert any("first-case payment 400" in error for error in errors)


def test_wrong_chain_or_treasury_fails_closed():
    plan = valid_plan()
    plan["chainId"] = 1
    plan["caseTreasury"] = "0x0000000000000000000000000000000000000000"
    errors = validate_plan(plan)
    assert any("chainId" in error for error in errors)
    assert any("caseTreasury" in error for error in errors)


def test_missing_chat02_authority_or_exclusion_fails_closed():
    plan = deepcopy(valid_plan())
    plan["casePaymentAuthority"] = "WEB3_DEPLOYMENT_PLAN"
    plan["mvpReleaseExclusions"] = []
    errors = validate_plan(plan)
    assert any("CHAT02" in error for error in errors)
    assert any("explicitly excluded" in error for error in errors)
