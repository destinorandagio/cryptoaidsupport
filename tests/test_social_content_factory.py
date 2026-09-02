import pytest

from bot.social_content_factory import ContentRejected, OFFICIAL_LINKS, build_post_package, choose_asset


def test_verified_post_has_explicit_cta_and_fingerprint():
    post = build_post_package(
        post_id="sec-001", language="en", pillar="security", audience="web3_users",
        objective="education_trust", hook="Protect your wallet before you need recovery.",
        body="Never share a seed phrase or private key. Verify official usernames and links before acting.",
        cta_primary="Join CryptoAID", destination="channel", verification_level="VERIFIED",
        source_ref="knowledge/cryptoaid_master.json",
    )
    assert post.cta_url == OFFICIAL_LINKS["channel"]
    assert "Join CryptoAID" in post.caption
    assert len(post.fingerprint) == 16


def test_unverified_or_guaranteed_recovery_copy_is_rejected():
    base = dict(
        post_id="x", language="it", pillar="recovery", audience="users", objective="trust",
        hook="Recovery", body="Analizziamo evidenze pubbliche.", cta_primary="Entra",
        destination="channel", source_ref="knowledge/recovery/RECOVERY_PLAYBOOK.md",
    )
    with pytest.raises(ContentRejected, match="knowledge_not_publishable"):
        build_post_package(**base, verification_level="UNRESOLVED")
    with pytest.raises(ContentRejected, match="prohibited_claim"):
        build_post_package(**{**base, "body": "Ti offriamo recupero garantito."}, verification_level="VERIFIED")


def test_asset_matcher_is_deterministic_and_ignores_unready_assets():
    assets = [
        {"id": "b", "tags": ["security", "wallet"], "status": "READY"},
        {"id": "a", "tags": ["security", "wallet", "phishing"], "status": "READY"},
        {"id": "z", "tags": ["security", "wallet", "phishing"], "status": "TO_REVIEW"},
    ]
    assert choose_asset(["security", "wallet", "phishing"], assets)["id"] == "a"
