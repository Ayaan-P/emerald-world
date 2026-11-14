"""Player-built maps of reported visited tiles, never omniscient geometry or movement."""
from collections import deque
import time
from .guilds import GuildError

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS player_chart_tiles(trainer TEXT,lineage TEXT,revision TEXT,x INTEGER,y INTEGER,PRIMARY KEY(trainer,lineage,revision,x,y))')
 db.execute('CREATE TABLE IF NOT EXISTS shared_chart_tiles(revision TEXT,x INTEGER,y INTEGER,PRIMARY KEY(revision,x,y))')

def identity(server,conn):
 if server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not conn.get('private_commands') or not conn.get('campaign_run'):raise GuildError('Charts require a matched player and active save lineage.')
 return conn['id'],conn['campaign_run']

def location(server,conn):
 identity(server,conn);s=conn.get('state');cave=server._connection_cave(conn)
 if not s or not s[6] or not 0<=time.monotonic()-conn.get('state_time',0)<=5 or not conn.get('in_generated_cave') or not cave or server._region_scope(conn)!=cave.identity or tuple(s[:2]) not in (server.cave_map,server.wilds_map) or not cave.walkable(s[2],s[3]):raise GuildError('Stand on a floor tile in an acknowledged generated place.')
 return cave,s[2],s[3]

def observe(server,conn):
 mode=conn.get('chart_mode')
 if mode not in ('private','shared'):return
 try:
  trainer,lineage=identity(server,conn)
  # Consent is only for the current connection/save, not a switched save.
  if conn.get('chart_lineage')!=lineage:conn.pop('chart_mode',None);return
  cave,x,y=location(server,conn)
 except GuildError:return
 setup(server.db)
 with server.db:
  server.db.execute('INSERT OR IGNORE INTO player_chart_tiles VALUES(?,?,?,?,?)',(trainer,lineage,cave.identity,x,y))
  if mode=='shared':server.db.execute('INSERT OR IGNORE INTO shared_chart_tiles VALUES(?,?,?)',(cave.identity,x,y))

def tiles(server,conn,revision,shared):
 setup(server.db);trainer,lineage=identity(server,conn)
 if shared:return set(server.db.execute('SELECT x,y FROM shared_chart_tiles WHERE revision=?',(revision,)))
 return set(server.db.execute('SELECT x,y FROM player_chart_tiles WHERE trainer=? AND lineage=? AND revision=?',(trainer,lineage,revision)))

def route(known,start,end):
 queue=deque([start]);previous={start:None}
 while queue:
  p=queue.popleft()
  if p==end:
   result=[]
   while previous[p] is not None:result.append(p);p=previous[p]
   return result[::-1]
  for q in ((p[0]+1,p[1]),(p[0]-1,p[1]),(p[0],p[1]+1),(p[0],p[1]-1)):
   if q in known and q not in previous:previous[q]=p;queue.append(q)
 return None

def command(server,conn,words):
 setup(server.db);_,lineage=identity(server,conn)
 help=['Charts: /guild chart private | share yes | stop.',
       'share yes publishes FUTURE visited tile coordinates to ALL world players, permanently.',
       'No names or save IDs appear on the shared chart. The host retains your private chart.',
       '/guild chart show [shared] [X Y] | route [shared] X Y. No automatic movement.']
 if not words:return help
 if words==['stop']:conn.pop('chart_mode',None);return ['Mapping stopped. Existing private/shared chart tiles remain.']
 if words==['share']:return help
 if words in (['private'],['share','yes']):
  location(server,conn);conn['chart_mode']='private' if words==['private'] else 'shared';conn['chart_lineage']=lineage
  observe(server,conn)
  return ['Mapping '+conn['chart_mode']+' for this connection/save. Old private tiles are never backfilled.']
 cave,x,y=location(server,conn);shared=len(words)>1 and words[1]=='shared';args=words[2:] if shared else words[1:]
 if words[0] not in ('show','route') or len(args) not in (0,2) or (words[0]=='route' and not args):raise GuildError('Use show [shared] [X Y] or route [shared] X Y.')
 if args:
  if any(not v.isascii() or not v.isdecimal() or len(v)>3 for v in args):raise GuildError('Use map tile coordinates.')
  tx,ty=map(int,args)
  if not 0<=tx<cave.side or not 0<=ty<cave.side:raise GuildError('Coordinates outside this place.')
 else:tx,ty=x,y
 known=tiles(server,conn,cave.identity,shared)
 label='Shared' if shared else 'Your save'
 if words[0]=='show':
  left=max(0,min(tx-4,cave.side-9));top=max(0,min(ty-4,cave.side-9))
  return [f'{label} chart {cave.identity[:8]}: {len(known)} reported tiles.',f'9x9 from ({left},{top}); @ you, . visited, ? uncharted.']+[
   ''.join('@' if (a,b)==(x,y) else '.' if (a,b) in known else '?' for a in range(left,min(left+9,cave.side))) for b in range(top,min(top+9,cave.side))]+['Remembered positions, not a current collision or visibility map.']
 path=route(known,(x,y),(tx,ty)) if (x,y) in known and (tx,ty) in known else None
 if path is None:return ['No connected reported path on this chart. Explore or choose another chart.']
 if not path:return ['You are at that tile.']
 # Show actionable cardinal runs, not a fabricated travel result.
 runs=[];prev=(x,y)
 for point in path:
  delta=(point[0]-prev[0],point[1]-prev[1]);direction={(1,0):'E',(-1,0):'W',(0,1):'S',(0,-1):'N'}[delta]
  if runs and runs[-1][0]==direction:runs[-1][1]+=1
  else:runs.append([direction,1])
  prev=point
 return [f'Remembered path: {len(path)} steps. Check current obstacles yourself.',
         'Then: '+' '.join(f'{d}{n}' for d,n in runs[:16])]+(['More turns remain; request again after walking.'] if len(runs)>16 else [])
