import json, os, sys, urllib.request
API='https://api.telegram.org/bot{}/{}'
def call(t,m,p):
 r=urllib.request.Request(API.format(t,m),data=json.dumps(p).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(r,timeout=30) as x: d=json.loads(x.read().decode())
 if not d.get('ok'): raise RuntimeError(d)
 return d['result']
def main():
 t=os.environ.get('TELEGRAM_BOT_TOKEN'); group=os.environ.get('TELEGRAM_GROUP_ID','@cryptoAIDsupporter'); channel=os.environ.get('TELEGRAM_CHANNEL_ID','@cryptoaidsup')
 if not t: sys.exit('TELEGRAM_BOT_TOKEN required')
 me=call(t,'getMe',{})
 required_group=['can_manage_chat','can_delete_messages','can_restrict_members','can_invite_users','can_pin_messages','can_manage_topics']
 required_channel=['can_manage_chat','can_post_messages','can_edit_messages','can_delete_messages','can_invite_users']
 failed=False
 for label,cid,req in [('GROUP',group,required_group),('CHANNEL',channel,required_channel)]:
  chat=call(t,'getChat',{'chat_id':cid}); member=call(t,'getChatMember',{'chat_id':cid,'user_id':me['id']})
  missing=[p for p in req if not member.get(p,False)]
  print(json.dumps({'target':label,'title':chat.get('title'),'status':member.get('status'),'missing_permissions':missing},ensure_ascii=False))
  if member.get('status') not in {'administrator','creator'} or missing: failed=True
 if failed: sys.exit('ADMIN AUDIT FAILED: grant the listed Telegram admin permissions, then rerun')
 print('ADMIN AUDIT SUCCESS')
if __name__=='__main__': main()
