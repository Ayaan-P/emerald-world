"""Agent-organized optional rematch availability, not fictional trainer results."""
import time
from .build_catalog import catalog_maps
ROUTES=tuple('Route'+str(n) for n in (102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,123,124,125,126,127,128))
def setup(db):db.execute('CREATE TABLE IF NOT EXISTS route_rematch_events(route TEXT PRIMARY KEY,actor TEXT,expires REAL,revision INTEGER)')
def catalog(server):
 setup(server.db)
 return dict(routes=list(ROUTES),active=[dict(route=r,actor=a,expires=e,revision=v) for r,a,e,v in server.db.execute('SELECT * FROM route_rematch_events WHERE expires>? ORDER BY route',(time.time(),))],limits='Temporary native availability, not attendance or NPC decisions. Registered previously defeated ordinary trainers only, with each player native badge eligibility; scripts, canonical teams and progression unchanged.')
def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'route','minutes'} or args['route'] not in ROUTES or type(args['minutes']) is not int or not 0<=args['minutes']<=1440:raise ValueError('Choose discovered route and 0..1440 minutes; zero closes own event')
 if args['route'] not in {m['name'] for m in catalog_maps().values()}:raise ValueError('Route absent from build')
 old=server.db.execute('SELECT actor,expires FROM route_rematch_events WHERE route=?',(args['route'],)).fetchone()
 if old and old[0]!=actor and old[1]>time.time():raise ValueError('Another actor owns this active event')
 expires=time.time()+args['minutes']*60
 seq=server.memory.append('route_rematch_event_configured',dict(character_id=actor,route=args['route'],expires=expires,basis='authored_optional_rematch_availability',limits='No battle, attendance, agreement, NPC growth or victory claimed. Players choose original trainer interactions; personal eligibility and progression stay native.'))
 server.db.execute('INSERT OR REPLACE INTO route_rematch_events VALUES(?,?,?,?)',(args['route'],actor,expires,seq));server.revision=seq
 return dict(outcome='rematch_event_opened' if args['minutes'] else 'rematch_event_closed',route=args['route'],expires=expires,revision=seq)
def wire(server,conn,raw):
 setup(server.db)
 if raw not in (b'J GET 1',b'J GET 2'):return 'J NONE\n'
 peer=conn.get('presence',{});state=peer.get('state')
 if not state or time.monotonic()-peer.get('state_time',0)>5:return 'J NONE\n'
 if raw==b'J GET 2':
  by_name={row['name']:pair for pair,row in catalog_maps().items()}
  now=time.time();entries=[]
  for name,expires in server.db.execute('SELECT route,expires FROM route_rematch_events WHERE expires>? ORDER BY route',(now,)):
   pair=by_name.get(name);seconds=min(30,int(expires-now))
   if name not in ROUTES or not pair or seconds<=0:continue
   entries.append('%02x%02x%02x'%(*pair,seconds))
  return 'J LIST '+''.join(entries)+'\n' if entries else 'J NONE\n'
 name=catalog_maps().get(tuple(state[:2]),{}).get('name')
 row=server.db.execute('SELECT expires FROM route_rematch_events WHERE route=?',(name,)).fetchone()
 seconds=min(30,int(row[0]-time.time())) if row else 0
 return 'J MAP %d %d %d\n'%(*state[:2],seconds) if seconds>0 else 'J NONE\n'
def command(server,conn,words):
 from .guilds import GuildError
 if words:raise GuildError('Use /guild rematches')
 rows=catalog(server)['active']
 return ['Optional route rematch events:']+[r['route']+' organized by '+r['actor'] for r in rows]+['Approach registered trainers you already defeated. Personal badge rules apply. No forced battle or shared credit.']
