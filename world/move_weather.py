"""Authored opt-in local temporary weather; no activation or shared climate claims."""
import json,time
from .shared_outbreaks import ROUTES
from .build_catalog import catalog_maps
from .move_selectors import resolve

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS move_weather_profiles(map TEXT PRIMARY KEY,actor TEXT NOT NULL,document TEXT NOT NULL,revision INTEGER NOT NULL)')

def catalog(server):
 setup(server.db)
 return dict(maps=list(ROUTES),profiles=[dict(map=m,actor=a,revision=r,**json.loads(d)) for m,a,d,r in server.db.execute('SELECT * FROM move_weather_profiles ORDER BY map')],limits='Voluntary local weather, not shared climate. Native requires clear stable saved/map weather. 600..3600 native weather-task ticks; battles pause lifetime. Stock forms/battle weather apply. Story setters supersede the overlay.')

def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'map','selector','weather','frames','pp'} or args['map'] not in ROUTES:raise ValueError('Select a reviewed ordinary Hoenn route')
 if type(args['selector']) is not str or len(args['selector'])>300:raise ValueError('Bounded move selector JSON required')
 selector=json.loads(args['selector']);resolve(selector)
 if args['weather'] not in ('rain','sandstorm','sun'):raise ValueError('Select rain, sandstorm or sun')
 for k,lo,hi in [('frames',600,3600),('pp',1,4)]:
  if type(args[k]) is not int or not lo<=args[k]<=hi:raise ValueError('Invalid bounded '+k)
 old=server.db.execute('SELECT actor FROM move_weather_profiles WHERE map=?',(args['map'],)).fetchone()
 if old and old[0]!=actor:raise ValueError('Another actor owns this route profile')
 if not any(m['name']==args['map'] for m in catalog_maps().values()):raise ValueError('Unknown native map')
 doc={k:args[k] for k in ('weather','frames','pp')};doc['selector']=selector
 seq=server.memory.append('move_weather_authored',dict(character_id=actor,map=args['map'],profile=doc,basis='configuration_not_activation_or_encounter'))
 server.db.execute('INSERT INTO move_weather_profiles VALUES(?,?,?,?) ON CONFLICT(map) DO UPDATE SET document=excluded.document,revision=excluded.revision',(args['map'],actor,json.dumps(doc,sort_keys=True),seq));server.revision=seq
 return dict(outcome='move_weather_authored',map=args['map'],revision=seq,profile=doc)

def offer(server,conn,seq,move):
 setup(server.db)
 state=conn.get('state');name=catalog_maps().get(tuple(state[:2]),{}).get('name') if state else None
 row=server.db.execute('SELECT document,revision FROM move_weather_profiles WHERE map=?',(name,)).fetchone()
 if not state or not state[6] or not 0<=time.monotonic()-conn.get('state_time',0)<=3:raise ValueError('Fresh field presence required')
 if not row:return f'FM WNONE {seq}\n'
 d=json.loads(row[0])
 if move not in resolve(d['selector']):return f'FM WNONE {seq}\n'
 return 'FM WEATHER '+' '.join(map(str,[seq,*state[:2],row[1],move,{'rain':3,'sandstorm':8,'sun':12}[d['weather']],d['frames'],d['pp']]))+'\n'
