"""Authored current-map sensing; separately volunteered client-report clues."""
import json,time
from .shared_outbreaks import ROUTES
from .build_catalog import catalog_maps
from .move_selectors import resolve

def setup(db):db.execute('CREATE TABLE IF NOT EXISTS move_sensing_profiles(map TEXT PRIMARY KEY,actor TEXT,document TEXT,revision INTEGER)')
def catalog(server):
 setup(server.db)
 return dict(maps=list(ROUTES),profiles=[dict(map=m,actor=a,revision=r,**json.loads(d)) for m,a,d,r in server.db.execute('SELECT * FROM move_sensing_profiles ORDER BY map')],limits='Native Itemfinder possession, actual learned move, personal flags; optional explicitly shared clues are client reports, not world-owned items.')
def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'map','selector','radius','pp'} or args['map'] not in ROUTES:raise ValueError('Select reviewed route')
 if type(args['selector']) is not str or len(args['selector'])>300:raise ValueError('Bounded move selector required')
 selector=json.loads(args['selector']);resolve(selector)
 if type(args['radius']) is not int or not 1<=args['radius']<=5 or type(args['pp']) is not int or not 1<=args['pp']<=4:raise ValueError('Radius 1..5, PP cost 1..4')
 old=server.db.execute('SELECT actor FROM move_sensing_profiles WHERE map=?',(args['map'],)).fetchone()
 if old and old[0]!=actor:raise ValueError('Another actor owns this sensing profile')
 doc=dict(selector=selector,radius=args['radius'],pp=args['pp'])
 seq=server.memory.append('move_sensing_authored',dict(character_id=actor,map=args['map'],profile=doc,basis='configuration_not_sensing_or_collection'))
 server.db.execute('INSERT INTO move_sensing_profiles VALUES(?,?,?,?) ON CONFLICT(map) DO UPDATE SET document=excluded.document,revision=excluded.revision',(args['map'],actor,json.dumps(doc),seq));server.revision=seq
 return dict(outcome='move_sensing_authored',map=args['map'],revision=seq,profile=doc)

def handle(server,channel,conn,f,seq):
 setup(server.db);state=conn.get('state');now=time.monotonic()
 if not state or not state[6] or not 0<=now-conn.get('state_time',0)<=3:raise ValueError('Fresh field presence required')
 if f[1]=='SGET' and len(f)==4 and f[3].isdigit():
  move=int(f[3]);name=catalog_maps().get(tuple(state[:2]),{}).get('name');row=server.db.execute('SELECT document,revision FROM move_sensing_profiles WHERE map=?',(name,)).fetchone()
  channel.pop('sensing_offer',None)
  if not row or move not in resolve(json.loads(row[0])['selector']):return f'FM SNONE {seq}\n'
  d=json.loads(row[0]);channel['sensing_offer']=dict(seq=seq,move=move,position=state[:4],radius=d['radius'],until=now+60)
  return 'FM SENSOR '+' '.join(map(str,[seq,*state[:2],row[1],move,d['radius'],d['pp']]))+'\n'
 if f[1]=='CLUE' and len(f)==6 and all(x.isdigit() for x in f[3:]):
  o=channel.pop('sensing_offer',None);x,y,move=map(int,f[3:])
  if not o or o['seq']!=seq or o['move']!=move or now>o['until'] or state[:4]!=o['position'] or max(abs(x-state[2]),abs(y-state[3]))>o['radius']:raise ValueError('Stale/outside sensing offer')
  from .spatial_signals import insert
  with server.db:insert(server,'player:'+conn['id']+' (reported clue)',*state[:2],x,y,'look')
  return f'FM SHARED {seq}\n'
 raise ValueError('Invalid sensing request')
