import argparse
import asyncio
import os

from telegram import Bot

MESSAGES = {
    "test": (
        "🧪 <b>CryptoAID System Test</b>\n"
        "Automation is online. No action is required.\n\n"
        "🇮🇹 <b>Test sistema CryptoAID</b>\n"
        "L'automazione è online. Non è richiesta alcuna azione."
    ),
    "security": (
        "🛡 <b>CryptoAID Security Reminder</b>\n"
        "Never share your seed phrase, private key, password or 2FA code. "
        "CryptoAID support will never ask for them.\n\n"
        "🇮🇹 <b>Promemoria sicurezza CryptoAID</b>\n"
        "Non condividere mai seed phrase, chiave privata, password o codice 2FA. "
        "Il supporto CryptoAID non te li chiederà mai."
    ),
}


async def publish(destination: str, message_key: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    bot = Bot(token=token)
    await bot.send_message(
        chat_id=destination,
        text=MESSAGES[message_key],
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    print(f"OK: published message={message_key} destination={destination}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", choices=("group", "channel"), required=True)
    parser.add_argument("--message", choices=tuple(MESSAGES), default="test")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    target = (
        os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter")
        if args.destination == "group"
        else os.getenv("TELEGRAM_CHANNEL", "@cryptoaidsup")
    )

    if not args.live:
        print(f"DRY RUN: would publish message={args.message} destination={target}")
        return

    asyncio.run(publish(target, args.message))


if __name__ == "__main__":
    main()
