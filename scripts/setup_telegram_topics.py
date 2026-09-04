import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.telegram.org/bot{token}/{method}"

def call(token, method, payload):
    req = urllib.request.Request(API.format(token=token, method=method), data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data=json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode(errors="replace")) from exc
    if not data.get("ok"):
        raise RuntimeError(str(data))
    return data["result"]

def main():
    token=os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id=os.environ.get("TELEGRAM_GROUP_ID","@cryptoAIDsupporter")
    if not token: sys.exit("TELEGRAM_BOT_TOKEN required")
    cfg=json.loads(Path("config/telegram_topics.json").read_text(encoding="utf-8"))
    state=Path("data/telegram_topics.runtime.json")
    if state.exists(): sys.exit("SAFE STOP: registry exists; refusing duplicate creation")
    chat=call(token,"getChat",{"chat_id":chat_id})
    if chat.get("type")!="supergroup" or not chat.get("is_forum"): sys.exit("BLOCKED: target must be forum supergroup")
    me=call(token,"getMe",{})
    member=call(token,"getChatMember",{"chat_id":chat_id,"user_id":me["id"]})
    if member.get("status") not in {"administrator","creator"} or not member.get("can_manage_topics",False): sys.exit("BLOCKED: bot needs Manage Topics admin permission")
    created={}
    for item in cfg.get("create_topics",[]):
        result=call(token,"createForumTopic",{"chat_id":chat_id,"name":item["name"]})
        created[item["key"]]={"name":item["name"],"message_thread_id":result["message_thread_id"]}
    output={"config_version":cfg["version"],"group":chat_id,"preexisting_topics":cfg.get("preexisting_topics",[]),"created_topics":created,"routing":cfg.get("routing",{})}
    state.parent.mkdir(parents=True,exist_ok=True)
    state.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"SUCCESS: created exactly {len(created)} missing topics; pre-existing topics untouched")
    print(json.dumps(output,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
