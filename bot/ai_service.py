"""Shared CryptoAID AI orchestration for DAPP and Telegram.

Authority remains the verified Knowledge layer. AI only rewrites/synthesizes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from bot.ai_provider import AIUnavailable, synthesize
from bot.knowledge_engine import answer as knowledge_answer, detect_language


@dataclass(frozen=True)
class AssistantResult:
    text: str
    language: str
    source: str
    confidence: float
    ai_used: bool
    ai_provider: str | None = None
    ai_model: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


async def answer_user(message: str, language: str | None = None) -> AssistantResult:
    lang = language or detect_language(message)
    grounded_text, confidence, source = knowledge_answer(message, lang)
    if source == "escalation" or confidence <= 0:
        return AssistantResult(
            text=grounded_text,
            language=lang,
            source=source,
            confidence=confidence,
            ai_used=False,
        )
    try:
        ai = await synthesize(
            verified_context=grounded_text,
            user_message=message,
            language=lang,
        )
        return AssistantResult(
            text=ai.text,
            language=lang,
            source=source,
            confidence=confidence,
            ai_used=True,
            ai_provider=ai.provider,
            ai_model=ai.model,
        )
    except AIUnavailable:
        return AssistantResult(
            text=grounded_text,
            language=lang,
            source=source,
            confidence=confidence,
            ai_used=False,
        )
