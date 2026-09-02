"""CryptoAID CHAT07 verified social post-package factory.

This module owns presentation only. It does not create project facts or replace the
Global Knowledge authority. Callers must supply publishable facts/claims only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Iterable

ALLOWED_LEVELS = {"VERIFIED_PRIMARY_SOURCE", "VERIFIED", "HIGH_CONFIDENCE"}
OFFICIAL_LINKS = {
    "website": "https://cryptoaid.support",
    "channel": "https://t.me/cryptoaidsup",
    "group": "https://t.me/cryptoAIDsupporter",
}


class ContentRejected(ValueError):
    pass


@dataclass(frozen=True)
class PostPackage:
    post_id: str
    language: str
    pillar: str
    audience: str
    objective: str
    hook: str
    body: str
    cta_primary: str
    cta_url: str
    destination: str
    verification_level: str
    source_ref: str
    image_asset_id: str | None = None
    image_role: str | None = None

    @property
    def caption(self) -> str:
        return f"{self.hook}\n\n{self.body}\n\n👉 {self.cta_primary}\n{self.cta_url}"

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.caption.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["caption"] = self.caption
        data["fingerprint"] = self.fingerprint
        return data


def build_post_package(*, post_id: str, language: str, pillar: str, audience: str,
                       objective: str, hook: str, body: str, cta_primary: str,
                       destination: str, verification_level: str, source_ref: str,
                       cta_url: str | None = None, image_asset_id: str | None = None,
                       image_role: str | None = None) -> PostPackage:
    if verification_level not in ALLOWED_LEVELS:
        raise ContentRejected("knowledge_not_publishable")
    if language not in {"en", "it"}:
        raise ContentRejected("unsupported_language")
    if destination not in {"channel", "group"}:
        raise ContentRejected("invalid_destination")
    required = [post_id, pillar, audience, objective, hook, body, cta_primary, source_ref]
    if any(not str(x).strip() for x in required):
        raise ContentRejected("missing_required_field")
    if len(hook) > 180 or len(body) > 2600 or len(cta_primary) > 120:
        raise ContentRejected("content_too_long")
    if any(term in (hook + " " + body).lower() for term in ("guaranteed recovery", "recupero garantito", "guaranteed return", "rendimento garantito")):
        raise ContentRejected("prohibited_claim")
    return PostPackage(
        post_id=post_id.strip(), language=language, pillar=pillar.strip(),
        audience=audience.strip(), objective=objective.strip(), hook=hook.strip(),
        body=body.strip(), cta_primary=cta_primary.strip(),
        cta_url=cta_url or OFFICIAL_LINKS["channel"], destination=destination,
        verification_level=verification_level, source_ref=source_ref.strip(),
        image_asset_id=image_asset_id, image_role=image_role,
    )


def choose_asset(required_tags: Iterable[str], assets: Iterable[dict]) -> dict | None:
    """Deterministic semantic asset selection from a pre-indexed asset catalog."""
    wanted = {str(t).lower() for t in required_tags if str(t).strip()}
    ranked = []
    for asset in assets:
        tags = {str(t).lower() for t in asset.get("tags", [])}
        if asset.get("status", "READY") != "READY":
            continue
        score = len(wanted & tags)
        if score:
            ranked.append((score, str(asset.get("id", "")), asset))
    if not ranked:
        return None
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return ranked[0][2]
