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

    cfg_path = Path("config/telegram_topics.json")
    state_path = Path("data/telegram_topics.runtime.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    chat = call(token, "getChat", {"chat_id": chat_id})
    if chat.get("type") != "supergroup":
        sys.exit("Target must be a Telegram supergroup")
    if not chat.get("is_forum"):
        sys.exit("BLOCKED: Telegram Topics/Forum is OFF. Enable Topics in the group settings, then rerun this workflow.")

    me = call(token, "getMe", {})
    member = call(token, "getChatMember", {"chat_id": chat_id, "user_id": me["id"]})
    if member.get("status") not in {"administrator", "creator"} or not member.get("can_manage_topics", False):
        sys.exit("BLOCKED: bot must be admin with Manage Topics permission")

    existing = {}
    if state_path.exists():
        try:
            existing = json.loads(state_path.read_text(encoding="utf-8")).get("topics", {})
        except Exception:
            existing = {}

    topics = dict(existing)
    created = []
    skipped = []
    for item in cfg["topics"]:
        key, name = item["key"], item["name"]
        if key in topics and topics[key].get("message_thread_id"):
            skipped.append(key)
            continue
        result = call(token, "createForumTopic", {"chat_id": chat_id, "name": name})
        topics[key] = {"name": name, "message_thread_id": result["message_thread_id"]}
        created.append(key)

    output = {
        "group": chat_id,
        "group_title": chat.get("title"),
        "is_forum": True,
        "topics": topics,
        "routing": cfg.get("routing", {}),
        "created": created,
        "skipped": skipped,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
