import json, os, sys, urllib.request
from pathlib import Path
API='https://api.telegram.org/bot{}/{}'
def call(t,m,p):
 r=urllib.request.Request(API.format(t,m),data=json.dumps(p).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(r,timeout=30) as x:d=json.loads(x.read().decode())
 if not d.get('ok'):raise RuntimeError(d)
 return d['result']
def main():
 token=os.environ.get('TELEGRAM_BOT_TOKEN'); event=os.environ.get('TELEGRAM_EVENT','general'); text=os.environ.get('TELEGRAM_TEXT','🧪 CryptoAID routing test')
 if not token:sys.exit('token missing')
 state=Path('data/telegram_topics.runtime.json')
 if not state.exists():sys.exit('topic registry missing')
 d=json.loads(state.read_text()); key=d.get('routing',{}).get(event)
 if not key:sys.exit('unknown event')
 topic=(d.get('created_topics',{}).get(key) or d.get('topics',{}).get(key))
 if not topic or not topic.get('message_thread_id'):sys.exit('topic id unavailable (preexisting topic must be registered separately)')
 call(token,'sendMessage',{'chat_id':d['group'],'message_thread_id':topic['message_thread_id'],'text':text,'disable_web_page_preview':True})
 print('sent',event,'to',key)
if __name__=='__main__':main()
