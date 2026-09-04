import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.telegram.org/bot{token}/{method}"


def call(token, method, payload):
    req = urllib.request.Request(
        API.format(token=token, method=method),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {exc.code}: {body}") from exc
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data["result"]


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_GROUP_ID", "@cryptoAIDsupporter")
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN is required")

    cfg = json.loads(Path("config/telegram_topics.json").read_text(encoding="utf-8"))
    state_path = Path("data/telegram_topics.runtime.json")

    # FAIL CLOSED: a persisted registry means setup has already run.
    # Never create another batch automatically. Reset requires an explicit code change.
    if state_path.exists():
        sys.exit("SAFE STOP: topic registry already exists. Refusing to create duplicates.")

    chat = call(token, "getChat", {"chat_id": chat_id})
    if chat.get("type") != "supergroup":
        sys.exit("Target must be a Telegram supergroup")
    if not chat.get("is_forum"):
        sys.exit("BLOCKED: Telegram Topics/Forum is OFF. Enable Topics, then run once.")

    me = call(token, "getMe", {})
    member = call(token, "getChatMember", {"chat_id": chat_id, "user_id": me["id"]})
    if member.get("status") not in {"administrator", "creator"} or not member.get("can_manage_topics", False):
        sys.exit("BLOCKED: bot must be admin with Manage Topics permission")

    topics = {}
    for item in cfg["topics"]:
        result = call(token, "createForumTopic", {"chat_id": chat_id, "name": item["name"]})
        topics[item["key"]] = {
            "name": item["name"],
            "message_thread_id": result["message_thread_id"]
        }

    output = {
        "config_version": cfg["version"],
        "group": chat_id,
        "group_title": chat.get("title"),
        "topics": topics,
        "routing": cfg.get("routing", {})
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SUCCESS: exactly", len(topics), "topics created")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
