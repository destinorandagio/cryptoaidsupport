import argparse
import asyncio
import hashlib
import json
import os
import random
from pathlib import Path

from telegram import Bot

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "evergreen.json"
STATE = ROOT / "data" / "state.json"


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"recent_ids": [], "published": 0}


def select_content(destination, state):
    items = json.loads(CONTENT.read_text())
    eligible = [
        x for x in items
        if x["destination"] == destination
        and x["id"] not in state.get("recent_ids", [])[-3:]
        and x.get("status", "READY") == "READY"
    ]
    if not eligible:
        eligible = [x for x in items if x["destination"] == destination and x.get("status", "READY") == "READY"]
    if not eligible:
        raise RuntimeError("no_publishable_content")
    return random.choice(eligible)


def render_caption(item):
    text = item.get("caption") or item.get("text") or ""
    cta = item.get("cta_primary")
    cta_url = item.get("cta_url")
    if cta and cta not in text:
        text = f"{text.rstrip()}\n\n👉 <b>{cta}</b>"
    if cta_url and cta_url not in text:
        text = f"{text.rstrip()}\n{cta_url}"
    return text.strip()


def fingerprint(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def publish(bot, chat, item):
    caption = render_caption(item)
    image_url = item.get("image_url")
    if image_url:
        try:
            await bot.send_photo(chat_id=chat, photo=image_url, caption=caption, parse_mode="HTML")
            return "photo"
        except Exception as exc:
            print(f"WARN: image publish failed; safe text fallback: {type(exc).__name__}")
    await bot.send_message(chat_id=chat, text=caption, parse_mode="HTML", disable_web_page_preview=True)
    return "text"


async def run(destination, live):
    state = load_state()
    item = select_content(destination, state)
    caption = render_caption(item)
    print(f"selected={item['id']} category={item['category']} fp={fingerprint(caption)} asset={item.get('image_asset_id','none')}")
    if not live:
        return
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.getenv("TELEGRAM_CHANNEL", "@cryptoaidsup") if destination == "channel" else os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter")
    mode = await publish(Bot(token), chat, item)
    state["recent_ids"] = (state.get("recent_ids", []) + [item["id"]])[-20:]
    state["published"] = state.get("published", 0) + 1
    print(f"OK: published mode={mode}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--destination", choices=["channel", "group"], required=True)
    p.add_argument("--live", action="store_true")
    a = p.parse_args()
    asyncio.run(run(a.destination, a.live))
