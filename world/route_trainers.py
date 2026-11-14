"""Authored route dispositions affect opt-in sight encounters, never defeats."""
import json,re,time
from .build_catalog import catalog_maps
MODES={'usual':0,'resting':1,'watchful':2}
def setup(db):db.execute('CREATE TABLE IF NOT EXISTS route_trainer_dispositions(route TEXT PRIMARY KEY,actor TEXT NOT NULL,revision INTEGER NOT NULL,expires REAL NOT NULL,mode TEXT NOT NULL,reason TEXT NOT NULL)')
def routes():return {v['name']:k for k,v in catalog_maps().items() if re.fullmatch(r'Route(?:10[1-9]|1[12][0-9]|13[0-4])',v.get('name',''))}
def catalog(server):
 setup(server.db)
 return dict(routes=sorted(routes()),modes=list(MODES),active=[dict(route=r,actor=a,revision=v,expires=e,mode=m,reason=t) for r,a,v,e,m,t in server.db.execute('SELECT * FROM route_trainer_dispositions WHERE expires>?',(time.time(),))],limits='Authored opt-in normal trainer sight only. Resting stops sight challenges, direct talk still battles. Watchful extends sight by up to two tiles capped at eight. No actual mood, walking, badge, defeat or character agreement is inferred.')
def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'route','mode','minutes','reason'} or args['route'] not in routes() or args['mode'] not in MODES or type(args['minutes']) is not int or not 0<=args['minutes']<=1440:raise ValueError('Choose reviewed Hoenn route, disposition and up to one day; zero closes')
 reason=args['reason']
 if type(reason) is not str or not 1<=len(reason)<=28 or any(not 32<=ord(c)<127 for c in reason):raise ValueError('Use a short printable public explanation')
 old=server.db.execute('SELECT actor,expires FROM route_trainer_dispositions WHERE route=?',(args['route'],)).fetchone()
 if old and old[0]!=actor and old[1]>time.time():raise ValueError('Another actor owns this active route disposition')
 expires=time.time()+args['minutes']*60
 seq=server.memory.append('route_trainer_disposition_changed',dict(actor=actor,**args,expires=expires,basis='authored_optional_native_sight_policy',limits='Not a trainer defeat, observation, agreement or story progression. Personal opt-in required.'))
 if not 0<seq<=2147483647:raise ValueError('Native revision range exhausted')
 server.db.execute('INSERT OR REPLACE INTO route_trainer_dispositions VALUES(?,?,?,?,?,?)',(args['route'],actor,seq,expires,args['mode'],reason));server.revision=seq
 return dict(outcome='route_disposition_published' if args['minutes'] else 'route_disposition_withdrawn',revision=seq,route=args['route'],expires=expires)
def wire(server,channel,raw):
 setup(server.db)
 try:
  w=raw.decode('ascii').split();peer=channel['presence'];state=peer.get('state')
  if len(w)!=3 or w[:2]!=['TD','GET'] or not re.fullmatch('[1-9][0-9]{0,9}',w[2]) or int(w[2])>4294967295 or server.link_channels.get(channel['id']) is not channel or server.peers.get(channel['id']) is not peer or peer.get('closing') or not state or not state[6] or not 0<=time.monotonic()-peer.get('state_time',0)<=3:raise ValueError()
  route=next((r for r,p in routes().items() if tuple(state[:2])==tuple(p)),None)
  row=server.db.execute('SELECT revision,expires,mode,reason FROM route_trainer_dispositions WHERE route=?',(route,)).fetchone()
  ttl=min(15,int(row[1]-time.time())) if row else 0
  if ttl<=0:return f'TD NONE {w[2]}\n'
  return f'TD OFFER {w[2]} {state[0]} {state[1]} {row[0]} {MODES[row[2]]} {ttl} {row[3].encode("ascii").hex()}\n'
 except (ValueError,KeyError,TypeError,UnicodeError):return 'TD FAIL\n'
