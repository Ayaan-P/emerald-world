"""Repeatable native templates, never transfers of world-owned companions."""
import json,re,time
SPECIES={'BULBASAUR':1,'CHARMANDER':4,'SQUIRTLE':7,'PIKACHU':25,'ODDISH':43,'PSYDUCK':54,'ABRA':63,'MACHOP':66,'GEODUDE':74,'GASTLY':92,'MAGIKARP':129,'EEVEE':133,'TREECKO':252,'TORCHIC':255,'MUDKIP':258,'ZIGZAGOON':263,'LOTAD':270,'SEEDOT':273,'RALTS':280,'MAKUHITA':296}
def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS native_trade_offers(actor TEXT PRIMARY KEY,requested INTEGER,offered INTEGER,revision INTEGER)')
def catalog(server):
 setup(server.db)
 return dict(species=SPECIES,offers=[dict(actor=a,requested=q,offered=o,revision=r) for a,q,o,r in server.db.execute('SELECT * FROM native_trade_offers ORDER BY actor')],semantics='Repeatable generated native trade templates. No existing NPC companion transfer, limited stock, player inventory upload or outcome attestation. Explicit native selection/confirmation; ordinary save behavior.')
def configure(server,actor,row,args):
 from .characters import records
 setup(server.db)
 if set(args)!={'requested','offered'} or any(type(args[k]) is not str for k in args):raise ValueError('Use requested and offered species names, or both empty to close')
 closing=args==dict(requested='',offered='')
 if not closing and (any(args[k] not in SPECIES for k in args) or args['requested']==args['offered']):raise ValueError('Choose distinct reviewed species')
 current=records(server.module_state).get(actor)
 if not current or current['status']!='active':raise ValueError('Active world character required')
 q,o=(0,0) if closing else (SPECIES[args['requested']],SPECIES[args['offered']])
 seq=server.memory.append('native_trade_template_changed',dict(character_id=actor,requested=q,offered=o,basis='configuration_only',limits='No trade, loss, acquisition or world-owned companion transfer occurred.'))
 if closing:server.db.execute('DELETE FROM native_trade_offers WHERE actor=?',(actor,))
 else:server.db.execute('INSERT INTO native_trade_offers VALUES(?,?,?,?) ON CONFLICT(actor) DO UPDATE SET requested=excluded.requested,offered=excluded.offered,revision=excluded.revision',(actor,q,o,seq))
 server.revision=seq
 return dict(outcome='native_trade_template_closed' if closing else 'native_trade_template_configured',revision=seq,requested=q,offered=o)
def handle(server,channel,raw):
 seq=0
 try:
  from .characters import records
  from .character_walks import walking
  conn=channel['presence']
  if server.link_channels.get(channel['id']) is not channel or server.peers.get(channel['id']) is not conn:raise ValueError()
  f=raw.decode('ascii').split()
  if len(f)!=4 or f[:2]!=['NT','GET'] or not re.fullmatch('[1-9][0-9]{0,9}',f[2]) or int(f[2])>0xffffffff or not re.fullmatch('[A-Za-z0-9_-]{1,24}',f[3]):raise ValueError()
  seq=int(f[2]);actor=f[3];state=conn.get('state')
  if server.link_protocol.busy(conn['id']) or not state or not state[6] or not 0<=time.monotonic()-conn.get('state_time',0)<=3:raise ValueError()
  record=records(server.module_state).get(actor);obj=next((o for o in server.objects if o['id']==actor),None)
  if not record or record['status']!='active' or not obj or obj.get('region_revision') or walking(server.module_state,actor):raise ValueError()
  if (obj['group'],obj['num'])!=tuple(state[:2]) or abs(obj['x']-state[2])+abs(obj['y']-state[3])!=1:raise ValueError()
  if any(type(p.get('character_pending')) is dict and p['character_pending'].get('id')==actor for p in server.peers.values()):raise ValueError()
  setup(server.db);offer=server.db.execute('SELECT requested,offered FROM native_trade_offers WHERE actor=?',(actor,)).fetchone()
  if not offer:raise ValueError()
  return 'NT OFFER '+' '.join(map(str,[seq,*state[:2],*offer]))+'\n'
 except (ValueError,KeyError,UnicodeError):return f'NT FAIL {seq}\n'
