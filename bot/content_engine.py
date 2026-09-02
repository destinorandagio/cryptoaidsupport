import argparse
import asyncio
import hashlib
import json
import os
import random
from pathlib import Path

from telegram import Bot

try:
    from .drive_media import MediaTransportError, fetch_drive_media
except ImportError:  # direct script execution
    from drive_media import MediaTransportError, fetch_drive_media

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "evergreen.json"
STATE = ROOT / "data" / "state.json"
ASSET_MAP = ROOT / "config" / "drive_asset_seed_map.json"

CATEGORY_ASSET_BUCKET = {
    "security": "security",
    "scam_awareness": "security",
    "education": "evidence",
    "recovery": "recovery",
    "engagement": "community_growth",
    "cryptoaid": "brand",
    "onboarding": "onboarding",
    "evidence": "evidence",
    "poll": "poll",
}


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"recent_ids": [], "published": 0, "recent_asset_ids": []}


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


def select_asset(item, state):
    if not ASSET_MAP.exists():
        return None
    data = json.loads(ASSET_MAP.read_text())
    bucket = CATEGORY_ASSET_BUCKET.get(item.get("category", ""), "brand")
    assets = list(data.get("assets", {}).get(bucket, []))
    if not assets:
        return None
    recent = set(state.get("recent_asset_ids", [])[-3:])
    fresh = [asset for asset in assets if asset.get("id") not in recent]
    return random.choice(fresh or assets)


async def publish(bot, chat, item, state):
    caption = render_caption(item)
    asset = select_asset(item, state)
    if asset:
        try:
            media = await fetch_drive_media(
                file_id=asset["id"], mime_type=asset["mime"], name=asset["name"]
            )
            if media.mime_type.startswith("image/"):
                await bot.send_photo(chat_id=chat, photo=media.as_buffer(), caption=caption, parse_mode="HTML")
                return "photo", asset["id"]
            if media.mime_type == "video/mp4":
                await bot.send_video(
                    chat_id=chat,
                    video=media.as_buffer(),
                    caption=caption,
                    parse_mode="HTML",
                    supports_streaming=True,
                )
                return "video", asset["id"]
        except Exception as exc:
            print(f"WARN: media publish failed; safe text fallback: {type(exc).__name__}")

    image_url = item.get("image_url")
    if image_url:
        try:
            await bot.send_photo(chat_id=chat, photo=image_url, caption=caption, parse_mode="HTML")
            return "photo_url", None
        except Exception as exc:
            print(f"WARN: image URL failed; safe text fallback: {type(exc).__name__}")

    await bot.send_message(chat_id=chat, text=caption, parse_mode="HTML", disable_web_page_preview=True)
    return "text", None


async def run(destination, live):
    state = load_state()
    item = select_content(destination, state)
    caption = render_caption(item)
    asset = select_asset(item, state)
    print(f"selected={item['id']} category={item['category']} fp={fingerprint(caption)} asset={(asset or {}).get('id','none')}")
    if not live:
        return
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.getenv("TELEGRAM_CHANNEL", "@cryptoaidsup") if destination == "channel" else os.getenv("TELEGRAM_GROUP", "@cryptoAIDsupporter")
    mode, asset_id = await publish(Bot(token), chat, item, state)
    state["recent_ids"] = (state.get("recent_ids", []) + [item["id"]])[-20:]
    if asset_id:
        state["recent_asset_ids"] = (state.get("recent_asset_ids", []) + [asset_id])[-20:]
    state["published"] = state.get("published", 0) + 1
    print(f"OK: published mode={mode}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--destination", choices=["channel", "group"], required=True)
    p.add_argument("--live", action="store_true")
    a = p.parse_args()
    asyncio.run(run(a.destination, a.live))
