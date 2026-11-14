"""Persistent authored tactics for reviewed original Hoenn rematches.
Results are consenting native-client reports, not server-attested battles or
proof of a trainer's off-screen practice. No private player/party identity in memory.
"""
import json,secrets,time
from .build_catalog import catalog_maps
TRAINERS={'calvin':'Route102','miguel':'Route103','winston':'Route104','cindy':'Route104','karen':'Route116','jerry':'Route116'}
TYPES={'normal':1,'fighting':2,'flying':3,'poison':4,'ground':5,'rock':6,'bug':7,'ghost':8,'steel':9,'fire':11,'water':12,'grass':13,'electric':14,'psychic':15,'ice':16,'dragon':17,'dark':18,'fairy':19}
def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS rematch_strategies(trainer TEXT PRIMARY KEY,actor TEXT,revision INTEGER,body TEXT)')
 db.execute('CREATE TABLE IF NOT EXISTS rematch_strategy_results(ticket TEXT PRIMARY KEY,trainer TEXT,revision INTEGER,outcome INTEGER)')
def catalog(server):
 setup(server.db)
 return dict(trainers=TRAINERS,types=list(TYPES),strategies=[dict(trainer=t,actor=a,revision=r,**json.loads(b)) for t,a,r,b in server.db.execute('SELECT * FROM rematch_strategies ORDER BY trainer')],
  results=[dict(trainer=t,revision=r,native_outcome=o,count=c) for t,r,o,c in server.db.execute('SELECT trainer,revision,outcome,count(*) FROM rematch_strategy_results GROUP BY trainer,revision,outcome')],
  limits='Optional solo rematches only. Original species/levels/items and rewards. Preferences select level-legal native moves, not guaranteed strength. Public results are consenting client reports, never private team data or autonomous training.')
def configure(server,actor,row,args):
 setup(server.db)
 if set(args) not in ({'trainer','expected_revision','types','status_moves'},{'trainer','expected_revision','types','status_moves','active'}) or args['trainer'] not in TRAINERS:raise ValueError('Choose a reviewed original trainer')
 if type(args['expected_revision']) is not int or not 0<=args['expected_revision']<2**32-1:raise ValueError('Inspect current revision first')
 if type(args['types']) is not list or not 1<=len(args['types'])<=3 or any(t not in TYPES for t in args['types']) or len(set(args['types']))!=len(args['types']):raise ValueError('Choose 1..3 distinct type preferences')
 if type(args['status_moves']) is not int or not 0<=args['status_moves']<=2:raise ValueError('Status preference 0..2')
 old=server.db.execute('SELECT actor,revision FROM rematch_strategies WHERE trainer=?',(args['trainer'],)).fetchone()
 if (old and old[0]!=actor) or (old[1] if old else 0)!=args['expected_revision']:raise ValueError('Strategy ownership/revision changed')
 if type(args.get('active',True)) is not bool:raise ValueError('Active must be boolean')
 body=dict(schema=1,active=args.get('active',True),types=args['types'],status_moves=args['status_moves'])
 revision=(old[1] if old else 0)+1
 server.db.execute('INSERT OR REPLACE INTO rematch_strategies VALUES(?,?,?,?)',(args['trainer'],actor,revision,json.dumps(body)))
 seq=server.memory.append('route_trainer_strategy_authored',dict(character_id=actor,trainer=args['trainer'],strategy_revision=revision,**body,basis='authored_optional_native_tactics_not_earned_training'))
 server.revision=seq
 return dict(outcome='strategy_published',trainer=args['trainer'],revision=revision)
def wire(server,conn,raw):
 setup(server.db)
 try:
  words=raw.decode('ascii').split()
  if len(words)==4 and words[:2]==['RS','GET']:
   nonce,key=words[2:]
   if not nonce.isdigit() or not 0<int(nonce)<2**32 or key not in TRAINERS:return 'RS NONE 0\n'
   peer=conn['presence'];state=peer.get('state')
   if not state or time.monotonic()-peer.get('state_time',0)>5 or catalog_maps().get(tuple(state[:2]),{}).get('name')!=TRAINERS[key]:return f'RS NONE {nonce}\n'
   row=server.db.execute('SELECT revision,body FROM rematch_strategies WHERE trainer=?',(key,)).fetchone()
   if not row:return f'RS NONE {nonce}\n'
   body=json.loads(row[1])
   if body.get('schema')!=1 or not body.get('active',True):return f'RS NONE {nonce}\n'
   ticket=secrets.token_hex(16)
   conn['rematch_strategy_pending']=dict(ticket=ticket,trainer=key,revision=row[0],expires=time.monotonic()+7200)
   types=[TYPES[t] for t in body['types']]+[0]*3
   return f"RS PLAN {nonce} {ticket} {row[0]} {types[0]} {types[1]} {types[2]} {body['status_moves']}\n"
  if len(words)==4 and words[:2]==['RS','DONE']:
   ticket,outcome=words[2:]
   pending=conn.get('rematch_strategy_pending')
   if not pending or ticket!=pending['ticket'] or time.monotonic()>pending['expires'] or outcome not in ('1','2','3'):return 'RS NO\n'
   # Consume before recording; duplicate completion cannot fabricate a second result.
   conn.pop('rematch_strategy_pending',None)
   with server.db:
    cursor=server.db.execute('INSERT OR IGNORE INTO rematch_strategy_results VALUES(?,?,?,?)',(ticket,pending['trainer'],pending['revision'],int(outcome)))
    if cursor.rowcount:
     seq=server.memory.append('route_trainer_strategy_result',dict(trainer=pending['trainer'],strategy_revision=pending['revision'],native_outcome=int(outcome),basis='consenting_native_client_report',limits='No player identity, party, partner, story completion or off-screen training inferred.'))
     server.revision=seq
   return 'RS RECORDED\n'
 except (ValueError,KeyError,UnicodeError,TypeError):pass
 return 'RS NO\n'
