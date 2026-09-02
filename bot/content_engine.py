import argparse
import asyncio
import hashlib
import json
import os
import random
from pathlib import Path

from telegram import Bot

ROOT=Path(__file__).resolve().parents[1]
CONTENT=ROOT/"content"/"evergreen.json"
STATE=ROOT/"data"/"state.json"


def load_state():
    if STATE.exists():
        try: return json.loads(STATE.read_text())
        except Exception: pass
    return {"recent_ids":[],"published":0}


def select_content(destination, state):
    items=json.loads(CONTENT.read_text())
    eligible=[x for x in items if x["destination"]==destination and x["id"] not in state.get("recent_ids",[])[-3:]]
    if not eligible: eligible=[x for x in items if x["destination"]==destination]
    return random.choice(eligible)


def fingerprint(text): return hashlib.sha256(text.encode()).hexdigest()[:16]

async def run(destination, live):
    state=load_state(); item=select_content(destination,state)
    print(f"selected={item['id']} category={item['category']} fp={fingerprint(item['text'])}")
    if not live: return
    token=os.environ["TELEGRAM_BOT_TOKEN"]
    chat=os.getenv("TELEGRAM_CHANNEL","@cryptoaidsup") if destination=="channel" else os.getenv("TELEGRAM_GROUP","@cryptoAIDsupporter")
    await Bot(token).send_message(chat_id=chat,text=item["text"],parse_mode="HTML",disable_web_page_preview=True)
    state["recent_ids"]=(state.get("recent_ids",[])+[item["id"]])[-20:]
    state["published"]=state.get("published",0)+1
    print("OK: published")

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--destination",choices=["channel","group"],required=True); p.add_argument("--live",action="store_true"); a=p.parse_args()
    asyncio.run(run(a.destination,a.live))
