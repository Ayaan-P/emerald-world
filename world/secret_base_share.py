"""Ephemeral bilateral own-base delivery, never public history or save authority."""
import re
import secrets
import time

BYTES=154

def handle(server,conn,fields):
 seq=0
 def reply(code):server._queue(conn,f'BASE_STATUS {seq} {code}\n')
 try:
  if len(fields)<2 or not fields[1].isascii() or not fields[1].isdecimal():raise ValueError()
  seq=int(fields[1])
  if not 0<seq<=2**32-1 or seq<=conn.get('base_seq',0):raise ValueError()
  conn['base_seq']=seq
  if not conn.get('chat') or conn.get('closing'):raise ValueError()
  now=time.monotonic()
  offers=getattr(server,'base_offers',{})
  offers={k:v for k,v in offers.items() if v['expires']>now and server.peers.get(v['sender']['id']) is v['sender'] and server.peers.get(v['target']['id']) is v['target']}
  server.base_offers=offers
  def near(a,b):
   states=[]
   for c in (a,b):
    s=c.get('state')
    if not s or s[6]!=1 or not 0<=now-c.get('state_time',0)<=5 or c.get('closing'):raise ValueError()
    states.append(s)
   a,b=states
   if tuple(a[:2])!=tuple(b[:2]) or abs(a[2]-b[2])+abs(a[3]-b[3])!=1:raise ValueError()
   # Do not confuse two private generated instances sharing a physical map.
   if server._region_scope(conn)!=server._region_scope(target):raise ValueError()
  if fields[0]=='BASE_OFFER':
   if len(fields)!=4 or not re.fullmatch('[A-Za-z0-9_-]{1,24}',fields[2]) or not re.fullmatch('[0-9a-f]{308}',fields[3]):raise ValueError()
   target=server.peers.get(fields[2])
   if not target or target is conn or not target.get('chat'):raise ValueError()
   near(conn,target)
   if len(offers)>=8 or any(v['sender'] is conn or v['target'] is target for v in offers.values()):return reply('BUSY')
   token=secrets.token_hex(8)
   offers[token]=dict(sender=conn,target=target,payload=fields[3],expires=now+60)
   server.guild_chat.message(target,'World',f"{conn['id']} offers their Secret Base, decorations and recorded party.")
   server.guild_chat.message(target,'World',f'/base accept {token} or /base decline {token} (60 seconds).')
   server._queue(target,server._snapshot(target));reply('OFFERED')
  elif fields[0] in ('BASE_ACCEPT','BASE_DECLINE'):
   if len(fields)!=3 or not re.fullmatch('[0-9a-f]{16}',fields[2]):raise ValueError()
   offer=offers.get(fields[2])
   if not offer or offer['target'] is not conn:raise ValueError()
   target=offer['sender'];near(conn,target)
   del offers[fields[2]]
   if fields[0]=='BASE_DECLINE':return reply('DECLINED')
   # Consumed exactly once. This means delivered for local validation, NOT saved.
   server._queue(conn,f"BASE_DATA {seq} {offer['payload']}\n")
   server.guild_chat.message(target,'World','Secret Base delivered for local validation. No import or save success is inferred.')
  else:raise ValueError()
 except (ValueError,KeyError,TypeError,IndexError):reply('UNAVAILABLE')
