"""Agent-curated native rental sets, not recruitment, earned growth or victories."""
import itertools,json
from pathlib import Path
CATALOG=json.loads(Path(__file__).with_name('rental_catalog.json').read_text())
SETS={r['id']:r for r in CATALOG['sets']}
def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS rental_pools(venue TEXT PRIMARY KEY,actor TEXT,sets TEXT,revision INTEGER)')
def validate(ids):
 if type(ids) is not list or len(ids)!=6 or any(type(i) is not int or i not in SETS for i in ids):raise ValueError('Choose exactly six native rental set IDs')
 mons=[SETS[i] for i in ids];species={m['species'] for m in mons};items=[m['item'] for m in mons if m['item']!='ITEM_NONE']
 if len(species)!=6 or len(set(items))!=len(items):raise ValueError('Rental species and nonempty held items must be distinct')
 eligible=0
 for trainer in CATALOG['trainers']:
  if len(trainer['sets'])<=8:continue
  eligible+=1
  remaining=[SETS[i] for i in trainer['sets'] if SETS[i]['species'] not in species]
  def legal(team):
   held=[m['item'] for m in team if m['item']!='ITEM_NONE']
   return len({m['species'] for m in team})==3 and len(set(held))==len(held)
  if len(remaining)<3:raise ValueError('Selection leaves too few opponent options')
  for first in remaining:
   partners=[second for second in remaining if second['species']!=first['species'] and (first['item']=='ITEM_NONE' or first['item']!=second['item'])]
   if not partners or any(not any(legal([first,second,third]) for third in remaining) for second in partners):
    raise ValueError('Selection can strand the native greedy opponent generator')
 if not eligible:raise ValueError('No reviewed opponent catalog')
 return ids

def catalog(server):
 row=server.db.execute("SELECT actor,sets,revision FROM rental_pools WHERE venue='slateport'").fetchone()
 return dict(pages=7,active=None if not row else dict(actor=row[0],sets=json.loads(row[1]),revision=row[2]))

def configure(server,actor,row,args):
 if set(args)!={'sets'} or type(args['sets']) is not str:raise ValueError('Use JSON native rental set IDs, or [] to close')
 try:ids=json.loads(args['sets'])
 except ValueError:raise ValueError('Invalid set IDs') from None
 if ids!=[]:validate(ids)
 old=server.db.execute("SELECT actor FROM rental_pools WHERE venue='slateport'").fetchone()
 if old and old[0]!=actor:raise ValueError('Another actor owns the current venue pool')
 seq=server.memory.append('rental_pool_configured',dict(character_id=actor,venue='slateport',sets=ids,basis='authored_native_rental_selection',limits='Not a player selection, recruitment, battle result or NPC training'))
 if ids:server.db.execute("INSERT INTO rental_pools VALUES('slateport',?,?,?) ON CONFLICT(venue) DO UPDATE SET actor=excluded.actor,sets=excluded.sets,revision=excluded.revision",(actor,json.dumps(ids),seq))
 else:server.db.execute("DELETE FROM rental_pools WHERE venue='slateport'")
 server.revision=seq
 return dict(outcome='rental_pool_configured' if ids else 'rental_pool_closed',venue='slateport',sets=ids,revision=seq)

def line(server,conn):
 if not conn.get('rental_capable'):return None
 row=server.db.execute("SELECT sets,revision FROM rental_pools WHERE venue='slateport'").fetchone()
 return None if not row else 'RENTAL_POOL '+' '.join(map(str,[row[1],*json.loads(row[0])]))

def inspect_sets(server,actor,row,args):
 if set(args)!={'page'} or type(args['page']) is not int or not 0<=args['page']<7:raise ValueError('Rental catalog page must be 0..6')
 return dict(outcome='native_rental_catalog',page=args['page'],pages=7,active=catalog(server)['active'],source_revision=CATALOG['source_revision'],sets=CATALOG['sets'][args['page']*10:args['page']*10+10])

def tool(server,actor,row,args):
 if set(args)!={'operation','value'}:raise ValueError('Use operation and value')
 if args['operation']=='inspect':return inspect_sets(server,actor,row,dict(page=args['value']))
 if args['operation']=='configure':return configure(server,actor,row,dict(sets=args['value']))
 raise ValueError('Use inspect or configure')
