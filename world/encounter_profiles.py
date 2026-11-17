"""Authored opt-in local encounter filters, never sightings or caught individuals."""
import json,time
from .shared_outbreaks import ROUTES
from .build_catalog import catalog_maps
from .move_selectors import resolve

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS encounter_profiles(map TEXT PRIMARY KEY,actor TEXT NOT NULL,document TEXT NOT NULL,revision INTEGER NOT NULL)')

def catalog(server):
 setup(server.db)
 return dict(maps=list(ROUTES),profiles=[dict(map=m,actor=a,revision=r,**json.loads(d)) for m,a,d,r in server.db.execute('SELECT * FROM encounter_profiles ORDER BY map')],limits='Voluntary native walking filters, not new species, guaranteed encounters or reported successes. Personal roamers/outbreaks bypass filters.')

def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'map','selector','accept','prefer_move_type','steps','pp'} or args['map'] not in ROUTES:raise ValueError('Select a reviewed ordinary Hoenn route')
 if type(args['selector']) is not str or len(args['selector'])>300:raise ValueError('Bounded move selector JSON required')
 selector=json.loads(args['selector']);resolve(selector)
 if type(args['prefer_move_type']) is not int or args['prefer_move_type'] not in (0,1):raise ValueError('prefer_move_type must be 0 or 1')
 for k,lo,hi in [('accept',25,100),('steps',10,200),('pp',1,4)]:
  if type(args[k]) is not int or not lo<=args[k]<=hi:raise ValueError('Invalid bounded '+k)
 if args['accept']==100:raise ValueError('100 percent acceptance would have no effect')
 old=server.db.execute('SELECT actor FROM encounter_profiles WHERE map=?',(args['map'],)).fetchone()
 if old and old[0]!=actor:raise ValueError('Another actor owns this route profile')
 if not any(m['name']==args['map'] for m in catalog_maps().values()):raise ValueError('Unknown native map')
 doc={k:args[k] for k in ('accept','prefer_move_type','steps','pp')};doc['selector']=selector
 seq=server.memory.append('encounter_profile_authored',dict(character_id=actor,map=args['map'],profile=doc,basis='configuration_not_activation_or_encounter'))
 server.db.execute('INSERT INTO encounter_profiles VALUES(?,?,?,?) ON CONFLICT(map) DO UPDATE SET document=excluded.document,revision=excluded.revision',(args['map'],actor,json.dumps(doc,sort_keys=True),seq));server.revision=seq
 return dict(outcome='encounter_profile_authored',map=args['map'],revision=seq,profile=doc)

def offer(server,conn,seq,move):
 setup(server.db)
 state=conn.get('state');name=catalog_maps().get(tuple(state[:2]),{}).get('name') if state else None
 row=server.db.execute('SELECT document,revision FROM encounter_profiles WHERE map=?',(name,)).fetchone()
 if not row:return f'FM PNONE {seq}\n'
 d=json.loads(row[0])
 if move not in resolve(d['selector']):return f'FM PNONE {seq}\n'
 return 'FM PROFILE '+' '.join(map(str,[seq,*state[:2],row[1],move,d['accept'],int(d['prefer_move_type']),d['steps'],d['pp']]))+'\n'
