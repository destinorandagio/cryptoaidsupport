import asyncio
import os
import sys

from telegram import Bot


async def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not configured")
        return 2

    bot = Bot(token=token)
    me = await bot.get_me()
    print(f"OK: authenticated as @{me.username} (id={me.id})")

    expected = os.getenv("EXPECTED_BOT_USERNAME", "CryptoAIDsupportBOT").lstrip("@")
    if me.username and me.username.lower() != expected.lower():
        print("ERROR: authenticated bot does not match expected CryptoAID bot")
        return 3

    for label, chat in (
        ("group", os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter")),
        ("channel", os.getenv("TELEGRAM_CHANNEL", "@cryptoaidsup")),
    ):
        try:
            info = await bot.get_chat(chat)
            print(f"OK: {label} reachable: {info.title or info.username or info.id}")
        except Exception as exc:
            print(f"ERROR: {label} unreachable: {type(exc).__name__}: {exc}")
            return 4

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
