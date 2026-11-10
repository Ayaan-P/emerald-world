"""Public proximity conversations with independent NPC recipients and session delivery."""
import json,secrets,time
from collections import deque
from .characters import records
from .guilds import GuildError


def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS spatial_speech(seq INTEGER PRIMARY KEY,origin TEXT,name TEXT,text TEXT,created REAL)')
 db.execute('CREATE TABLE IF NOT EXISTS spatial_speech_audience(seq INTEGER,trainer TEXT,session TEXT,delivered INTEGER DEFAULT 0,PRIMARY KEY(seq,trainer))')
 db.execute('CREATE TABLE IF NOT EXISTS spatial_speech_cooldown(actor TEXT PRIMARY KEY,until REAL)')


def footprint(server,origin):
 x,y=origin['x'],origin['y'];radius=origin['radius'];revision=origin.get('region_revision')
 if revision is None:return {(x+dx,y+dy) for dx in range(-radius,radius+1) for dy in range(-radius,radius+1) if abs(dx)+abs(dy)<=radius}
 from .shared_cave import SharedCave
 saved=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()
 if not saved:raise ValueError('Speech geometry is no longer available')
 cave=SharedCave(saved[0])
 if cave.identity!=revision or not cave.walkable(x,y):raise ValueError('Invalid speech origin')
 cells={(x,y)};queue=deque([(x,y,0)])
 while queue:
  x,y,d=queue.popleft()
  if d>=radius:continue
  for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
   if p not in cells and cave.walkable(*p):cells.add(p);queue.append((*p,d+1))
 return cells


def scope(obj,origin):return all(obj.get(k)==origin.get(k) for k in ('group','num','region_revision'))

def ready_actor(server,actor):
 from .character_walks import walking
 c=records(server.module_state).get(actor);obj=next((o for o in server.objects if o['id']==actor),None)
 if not c or c['status']!='active' or not obj or walking(server.module_state,actor):return None
 if any(type(p.get('character_pending')) is dict and p['character_pending'].get('id')==actor for p in server.peers.values()):return None
 return c,obj


def player_near(server,peer,origin,cells):
 from .region_characters import scoped
 state=peer.get('state')
 if (server.peers.get(peer.get('id')) is not peer or peer.get('closing') or not state or not state[6]
     or not 0<=time.monotonic()-peer.get('state_time',0)<=5 or state[:2]!=[origin['group'],origin['num']]
     or tuple(state[2:4]) not in cells):return False
 return scoped(server,peer,origin,origin.get('region_revision'))


def validate_text(text):
 if type(text) is not str or not 1<=len(text)<=80 or any(not 32<=ord(c)<127 for c in text):raise ValueError('Use 1..80 printable characters of public fictional speech')


def emit(server,origin,name,text,actor=None):
 setup(server.db);validate_text(text);cells=footprint(server,origin)
 recipients=[]
 for identity in records(server.module_state):
  if identity==actor:continue
  ready=ready_actor(server,identity)
  if ready and scope(ready[1],origin) and (ready[1]['x'],ready[1]['y']) in cells:recipients.append(dict(id=identity,version=ready[0]['version']))
 audience=[p for p in server.peers.values() if player_near(server,p,origin,cells)]
 if not recipients and not audience:raise ValueError('No actual nearby audience; no conversation asserted')
 if actor is None and not recipients:raise ValueError('Stand near an available recurring NPC before speaking to the group')
 data=dict(character_id=actor,recipients=recipients,text=text,origin=origin,publication='explicit_public_spatial_speech',basis='authority_positions_and_opted_public_dialogue',
           limits='Public fictional speech, not truth of its claims, agreement, completed action or proof of rendered hearing. Native maps use same-map proximity, not wall-aware acoustics.')
 seq=server.memory.append('spatial_public_speech',data)
 server.db.execute('INSERT INTO spatial_speech VALUES(?,?,?,?,?)',(seq,json.dumps(origin,sort_keys=True),name,text,time.time()))
 for peer in audience:
  token=peer.setdefault('npc_speech_session',secrets.token_hex(16))
  server.db.execute('INSERT INTO spatial_speech_audience(seq,trainer,session) VALUES(?,?,?)',(seq,peer['id'],token))
 server.revision=seq
 return dict(outcome='public_spatial_speech_committed',speech=seq,recipients=[r['id'] for r in recipients],limits='Recipients choose whether to respond. Live chat is attempted once for eligible original sessions only; no player identity published.')


def speak(server,actor,row,args):
 if set(args)!={'text','radius'} or type(args['radius']) is not int or not 1<=args['radius']<=4:raise ValueError('Supply public text and radius 1..4')
 ready=ready_actor(server,actor)
 if not ready:raise ValueError('Speaker must be an active stationary world character outside battle')
 setup(server.db);prior=server.db.execute('SELECT until FROM spatial_speech_cooldown WHERE actor=?',(actor,)).fetchone()
 if prior and time.time()<prior[0]:raise ValueError('Public group speech is limited to once per character per 30 seconds')
 c,obj=ready;origin={k:obj[k] for k in ('group','num','x','y')}
 if obj.get('region_revision'):origin['region_revision']=obj['region_revision']
 origin['radius']=args['radius'] if obj.get('region_revision') else min(2,args['radius'])
 result=emit(server,origin,c['name'].encode('ascii','replace').decode()[:24],args['text'],actor)
 server.db.execute('INSERT OR REPLACE INTO spatial_speech_cooldown VALUES(?,?)',(actor,time.time()+30))
 return result


def command(server,peer,words):
 if not words:return ['Group NPC speech is PUBLIC history for all world players and agents. Use fictional dialogue only.',
  '/guild npc speak-public MESSAGE addresses available nearby recurring NPCs. Nearby ready players may hear it.']
 try:
  state=peer.get('state')
  if server.peers.get(peer.get('id')) is not peer or peer.get('closing'):raise ValueError('Authenticated current player session required')
  if not state or not state[6] or not 0<=time.monotonic()-peer.get('state_time',0)<=5:raise ValueError('Stand ready near the NPC conversation')
  if time.monotonic()-peer.get('spatial_speech_time',-100)<5:raise ValueError('Give the conversation a moment')
  origin=dict(group=state[0],num=state[1],x=state[2],y=state[3],radius=2)
  if tuple(state[:2]) in (server.cave_map,server.wilds_map):origin['region_revision']=server._region_scope(peer)
  if tuple(state[:2]) in (server.cave_map,server.wilds_map) and not origin.get('region_revision'):raise ValueError('Exact selected place required')
  with server.db:result=emit(server,origin,'Visitor',' '.join(words))
  peer['spatial_speech_time']=time.monotonic()
  return ['Public group speech delivered to '+str(len(result['recipients']))+' nearby NPCs. Each decides whether to respond.']
 except ValueError as exc:raise GuildError(str(exc)) from None


def flush(server):
 setup(server.db)
 rows=server.db.execute('SELECT a.seq,a.trainer,a.session,s.origin,s.name,s.text,s.created FROM spatial_speech_audience a JOIN spatial_speech s ON s.seq=a.seq WHERE a.delivered=0 ORDER BY a.seq,a.trainer LIMIT 32').fetchall()
 for seq,trainer,session,raw,name,text,created in rows:
  peer=server.peers.get(trainer);origin=json.loads(raw)
  valid=bool(peer and peer.get('npc_speech_session')==session and 0<=time.time()-created<=15)
  if valid:
   try:valid=player_near(server,peer,origin,footprint(server,origin))
   except ValueError:valid=False
  # At-most-once handoff, not an acknowledgment that a player saw the line.
  with server.db:server.db.execute('UPDATE spatial_speech_audience SET delivered=1 WHERE seq=? AND trainer=?',(seq,trainer))
  if valid:server.guild_chat.message(peer,'World',(name+': '+text)[:113])


def relevant(event,actor):
 return (event.get('event')=='spatial_public_speech' and event.get('publication')=='explicit_public_spatial_speech'
         and event.get('basis')=='authority_positions_and_opted_public_dialogue'
         and any(r.get('id')==actor for r in event.get('recipients',[]) if type(r) is dict))
