"""Ephemeral private field-care delivery. Never mutates saves or certifies healing."""
import re,secrets,time
TOKEN=re.compile(r'[0-9a-f]{16}\Z')
def current(s,c):
 return not c.get('closing') and s.link_channels.get(c['id']) is c and c['sock'] in s.connections and s.peers.get(c['id']) is c['presence'] and not c['presence'].get('closing')
def paired(s,a,b):
 p=s.link_protocol;tag=p._tags.get(p._tag_actor.get(a['id']))
 if not tag or not tag.active or tag.coop_wire or set(tag.participants)!={a['id'],b['id']}:return False
 if any(x in p.sessions._locks or x in p._encounters for x in tag.participants):return False
 if not current(s,a) or not current(s,b):return False
 pa,pb=a['presence'],b['presence'];x,y=pa.get('state'),pb.get('state');now=time.monotonic()
 return bool(x and y and len(x)>=7 and len(y)>=7 and x[6] and y[6] and x[:2]==y[:2] and abs(x[2]-y[2])+abs(x[3]-y[3])<=2 and all(0<=now-v.get('state_time',0)<=2 for v in (pa,pb)))
def clear(p):
 for c in (p['source'],p['target']):
  if c.get('field_support') is p:c.pop('field_support',None)
def finish(p,result):
 clear(p)
 return [(p['source'],f"FS RESULT {p['seq']} {p['token']} {result}\n"),(p['target'],f"FS END {p['token']}\n")]
def reap(c):
 p=c.get('field_support')
 if p and time.monotonic()>p['expires']:return finish(p,2 if p['phase']=='committed' else 0)
 return []
def wire(s,c,raw):
 output=reap(c)
 try:
  w=raw.decode('ascii').split()
  if len(w)==4 and w[:2]==['FS','OFFER']:
   seq=w[2]
   if not re.fullmatch(r'[1-9][0-9]{0,9}',seq) or int(seq)>4294967295:raise ValueError()
   if int(seq)<=c.get('field_support_seq',0):raise ValueError()
   c['field_support_seq']=int(seq)
   b=s.link_channels.get(w[3]);now=time.monotonic()
   if b:output+=reap(b)
   if not b or b is c or not paired(s,c,b) or c.get('field_support') or b.get('field_support') or now<c.get('field_support_next',0):raise ValueError()
   c['field_support_next']=now+5
   token=secrets.token_hex(8);p=dict(source=c,target=b,seq=int(seq),token=token,phase='offered',expires=now+30)
   c['field_support']=b['field_support']=p
   return output+[(c,f'FS PENDING {seq} {token}\n'),(b,f"FS OFFER {token} {c['id']}\n")]
  if len(w)<3 or w[0]!='FS' or not TOKEN.fullmatch(w[2]):raise ValueError()
  p=c.get('field_support')
  if not p or p['token']!=w[2]:raise ValueError()
  if not paired(s,p['source'],p['target']):return output+finish(p,2 if p['phase']=='committed' else 0)
  if w[1]=='ACCEPT' and len(w)==3 and c is p['target'] and p['phase']=='offered':
   p['phase']='accepted';p['expires']=time.monotonic()+4
   return output+[(p['source'],f"FS READY {p['seq']} {p['token']}\n")]
  if w[1]=='COMMIT' and len(w)==3 and c is p['source'] and p['phase']=='accepted':
   p['phase']='committed';p['expires']=time.monotonic()+4
   return output+[(p['target'],f"FS APPLY {p['token']}\n")]
  if w[1]=='ACK' and len(w)==4 and w[3] in ('0','1') and c is p['target'] and p['phase']=='committed':return output+finish(p,int(w[3]))
  if w[1]=='CANCEL' and len(w)==3:
   # After commit, the server cannot infer whether the receiver already applied.
   return output+finish(p,2 if p['phase']=='committed' else 0)
 except (ValueError,KeyError,TypeError,UnicodeError):pass
 seq=w[2] if 'w' in locals() and len(w)>2 and w[1]=='OFFER' and re.fullmatch(r'[0-9]{1,10}',w[2]) else '0'
 return output+[(c,f'FS FAIL {seq}\n')]
