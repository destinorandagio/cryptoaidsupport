"""Scheduled Telegram group engagement publisher.
Publishes native polls only when --live is explicitly supplied.
"""
import argparse
import asyncio
import os
from telegram import Bot
from bot.poll_engine import choose


async def run(language: str, live: bool) -> None:
    poll = choose(language)
    print(f"poll_id={poll.id} language={poll.language} category={poll.category}")
    if not live:
        return
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    group = os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter")
    await Bot(token).send_poll(
        chat_id=group,
        question=poll.question,
        options=list(poll.options),
        is_anonymous=True,
        allows_multiple_answers=False,
    )
    print("OK: poll published")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--language", choices=["en", "it"], default="en")
    p.add_argument("--live", action="store_true")
    args = p.parse_args()
    asyncio.run(run(args.language, args.live))
