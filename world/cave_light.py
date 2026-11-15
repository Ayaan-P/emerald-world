"""Visit-scoped, client-reported shared visibility, never shared Flash flags."""
import time,re
def current(s,c):return not c.get('closing') and s.link_channels.get(c['id']) is c and c['sock'] in s.connections and s.peers.get(c['id']) is c['presence'] and not c['presence'].get('closing')
def handle(s,c,raw):
 try:
  w=raw.decode('ascii').split()
  if len(w)!=5 or w[:2]!=['FL','STATE'] or not re.fullmatch('[1-9][0-9]{0,9}',w[2]) or int(w[2])>4294967294 or w[3] not in ('0','1') or w[4] not in ('0','1') or not current(s,c):raise ValueError()
  epoch=int(w[2]);old=c.get('cave_light');now=time.monotonic();p=c['presence'];state=p.get('state')
  if old and epoch<old['epoch']:raise ValueError()
  if not state or len(state)<7 or not state[6] or not 0<=now-p.get('state_time',0)<=2:raise ValueError()
  c['cave_light']=dict(epoch=epoch,enabled=w[3]=='1',lit=w[4]=='1' and w[3]=='1',map=tuple(state[:2]),visit=p.get('cave_light_visit',0),time=now)
  protocol=s.link_protocol;tag=protocol._tags.get(protocol._tag_actor.get(c['id']));bright=False
  if tag and tag.active and not tag.coop_wire and c['cave_light']['enabled'] and not any(x in protocol.sessions._locks or x in protocol._encounters for x in tag.participants):
   other=next((x for x in tag.participants if x!=c['id']),None);b=s.link_channels.get(other)
   if b and current(s,b):
    q=b['presence'];other_state=q.get('state');report=b.get('cave_light',{})
    bright=bool(other_state and len(other_state)>=7 and other_state[6] and report.get('enabled') and report.get('lit') and report.get('visit')==q.get('cave_light_visit',0) and 0<=now-report.get('time',0)<=1.5 and 0<=now-q.get('state_time',0)<=2 and tuple(other_state[:2])==tuple(state[:2])==report.get('map') and abs(state[2]-other_state[2])+abs(state[3]-other_state[3])<=5)
  return f'FL LIGHT {epoch} {int(bright)}\n'
 except (ValueError,KeyError,TypeError,UnicodeError):return 'FL FAIL\n'
