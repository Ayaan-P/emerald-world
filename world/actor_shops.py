"""Agent-selected ordinary retail catalogs, never fabricated stock or purchases."""
import json
# Exact reviewed Expansion item identifiers; native independently enforces these.
ITEMS={1:'Poke Ball',2:'Great Ball',3:'Ultra Ball',28:'Potion',29:'Super Potion',
       30:'Hyper Potion',31:'Max Potion',32:'Full Restore',33:'Revive',
       43:'Antidote',44:'Paralyze Heal',45:'Burn Heal',46:'Ice Heal',47:'Awakening',
       48:'Full Heal',114:'Repel',115:'Super Repel',116:'Max Repel',120:'Escape Rope'}

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS actor_shops(actor TEXT PRIMARY KEY,revision INTEGER,items TEXT)')

def configure(server,actor,row,args):
 from .characters import records
 if set(args)!={'items'} or type(args['items']) is not str or len(args['items'])>100:raise ValueError('Supply a JSON catalog of up to eight standard item IDs; empty closes service')
 try:items=json.loads(args['items'])
 except ValueError:raise ValueError('Invalid retail catalog')
 if type(items) is not list or len(items)>8 or any(type(i) is not int or i not in ITEMS for i in items) or len(items)!=len(set(items)):raise ValueError('Choose distinct reviewed ordinary retail items')
 current=records(server.module_state).get(actor)
 if not current or current['status']!='active':raise ValueError('Active world-owned character required')
 seq=server.memory.append('character_retail_changed',dict(character_id=actor,items=items,
     basis='authority_catalog_change',limits='Ordinary native unlimited retail at engine prices. No inventory, sale, profit or delivery claimed.'))
 server.db.execute('INSERT INTO actor_shops VALUES(?,?,?) ON CONFLICT(actor) DO UPDATE SET revision=excluded.revision,items=excluded.items',(actor,seq,json.dumps(items)))
 server.revision=seq
 return dict(outcome='retail_catalog_opened' if items else 'retail_catalog_closed',revision=seq,items=items)

def line(server,conn,actor,version):
 if not conn.get('character_shop_capable'):return None
 from .campaign_preparation import offer
 personal=offer(server,conn,actor)
 if personal and personal['items']:
  return 'CHARACTER_SHOP '+' '.join(map(str,[actor,version,personal['revision'],len(personal['items']),*personal['items']]))
 saved=server.db.execute('SELECT revision,items FROM actor_shops WHERE actor=?',(actor,)).fetchone()
 if not saved:return None
 items=json.loads(saved[1])
 if not items:return None
 return 'CHARACTER_SHOP '+' '.join(map(str,[actor,version,saved[0],len(items),*items]))

def catalog(server):
 return dict(items={str(k):v for k,v in ITEMS.items()},services={a:dict(revision=r,items=json.loads(i)) for a,r,i in server.db.execute('SELECT actor,revision,items FROM actor_shops')},
  semantics='Standard native retail, not finite shared stock. Player chooses purchases at actual engine prices; no server bag/money writes or claimed sales.')
