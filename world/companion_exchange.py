"""Voluntary transfers of existing world-owned companions, never catches or player trades."""
import hashlib,json,re
from .characters import records

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS companion_custody(identity TEXT PRIMARY KEY,holder TEXT NOT NULL)')
 db.execute('CREATE TABLE IF NOT EXISTS companion_offers(id TEXT PRIMARY KEY,sender TEXT,recipient TEXT,individual TEXT,recipient_individual TEXT,snapshot TEXT,status TEXT)')

def identity(values):return hashlib.sha256(json.dumps(list(values),sort_keys=True).encode()).hexdigest()

def owned(db,actor,individual):
 # Tables are initialized with the existing companion subsystem.
 row=db.execute('SELECT species,personality,owner FROM character_companions WHERE actor=? AND individual=?',(actor,individual)).fetchone()
 if not row:return False
 holder=db.execute('SELECT holder FROM companion_custody WHERE identity=?',(identity(row),)).fetchone()
 return holder is None or holder[0]==actor

def colocated(server,left,right):
 from .actor_social import participants
 recipient=records(server.module_state).get(right,{})
 _,a,_,b=participants(server,left,dict(target=right,expected_version=recipient.get('version')))
 if abs(a['x']-b['x'])+abs(a['y']-b['y'])!=1:raise ValueError('Companion exchange requires adjacent idle world characters')

def snapshot(server,actor,individual):
 from .character_companions import roster
 from .character_training import saved
 mon=next((m for m in roster(server,actor) if m['individual']==individual),None)
 if not mon or mon['on_team']:raise ValueError('Choose an actually owned benched companion; active teams remain untouched')
 return dict(member=mon,trained=saved(server.db,actor,individual))

def offers(server):
 return [dict(id=i,sender=s,recipient=r,individual=m,recipient_individual=k,status=status)
   for i,s,r,m,k,status in server.db.execute("SELECT id,sender,recipient,individual,recipient_individual,status FROM companion_offers WHERE status='offered' ORDER BY id")]

def offer(server,actor,row,args):
 if set(args)!={'target','individual','recipient_individual'} or not isinstance(args['recipient_individual'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,24}',args['recipient_individual']):raise ValueError('Supply recipient, owned individual and stable recipient-local individual ID')
 colocated(server,actor,args['target']);value=snapshot(server,actor,args['individual'])
 execution=server.actor_tool_execution
 if not execution or execution[0]!=actor:raise ValueError('Durable capability execution required')
 key=hashlib.sha256(json.dumps([actor,execution[2]['id'],execution[3]['id']],sort_keys=True).encode()).hexdigest()
 server.db.execute('INSERT INTO companion_offers VALUES(?,?,?,?,?,?,?)',(key,actor,args['target'],args['individual'],args['recipient_individual'],json.dumps(value,sort_keys=True),'offered'))
 return dict(outcome='companion_offered',offer=key,recipient=args['target'],individual=args['individual'],limits='Recipient independently accepts or declines; no ownership or team change yet.')

def respond(server,actor,row,args):
 from .actor_runtime import Committed,_receipt
 if set(args)!={'offer','decision'} or args['decision'] not in ('accept','decline','withdraw'):raise ValueError('Choose accept, decline or sender withdraw')
 value=server.db.execute('SELECT sender,recipient,individual,recipient_individual,snapshot,status FROM companion_offers WHERE id=?',(args['offer'],)).fetchone()
 if not value or value[5]!='offered':raise ValueError('Offer unavailable')
 sender,recipient,individual,key,encoded,_=value
 if args['decision']=='withdraw':
  if actor!=sender:raise ValueError('Only sender can withdraw')
 elif actor!=recipient:raise ValueError('Only recipient can decide')
 if args['decision']!='accept':
  server.db.execute('UPDATE companion_offers SET status=? WHERE id=?',(args['decision'],args['offer']))
  return dict(outcome='companion_offer_'+args['decision'],offer=args['offer'])
 colocated(server,sender,recipient)
 current=snapshot(server,sender,individual)
 if json.dumps(current,sort_keys=True)!=encoded:raise ValueError('Offered companion changed; sender must make a new offer')
 native=transfer(server,recipient,key,current)
 server.db.execute("UPDATE companion_offers SET status='accepted' WHERE id=?",(args['offer'],))
 seq=server.memory.append('companion_transferred',dict(sender=sender,recipient=recipient,individual=individual,recipient_individual=key,identity=identity(native),species=current['member']['species'],offer=args['offer'],basis='voluntary_adjacent_world_characters',limits='Existing companion transfer; no capture, evolution, victory or player save effect.'))
 result=dict(outcome='companion_transferred',offer=args['offer'],individual=key,world_receipt=seq,identity=identity(native),on_team=False)
 _,record,plan,step=server.actor_tool_execution
 receipt=_receipt(server,actor,record,plan,step,'succeeded',result)
 return Committed(receipt,result)

def transfer(server,recipient,key,current):
 mon=current['member'];native=(mon['species'],mon['personality'],mon['owner'])
 aliases=server.db.execute('SELECT individual FROM character_companions WHERE actor=? AND species=? AND personality=? AND owner=?',(recipient,*native)).fetchall()
 if aliases and (key,) not in aliases:raise ValueError('Reuse the recipient existing local ID for this same companion')
 known=server.db.execute('SELECT species,personality,owner FROM character_companions WHERE actor=? AND individual=?',(recipient,key)).fetchone()
 if known and tuple(known)!=native:raise ValueError('Recipient individual ID already identifies a different Pokemon')
 if known and owned(server.db,recipient,key):raise ValueError('Recipient already owns this companion')
 if any(m.get('individual')==key for m in records(server.module_state)[recipient]['team']):raise ValueError('Recipient active team slot is reserved')
 if not known and server.db.execute('SELECT count(*) FROM character_companions WHERE actor=?',(recipient,)).fetchone()[0]>=32:raise ValueError('Recipient companion archive is full')
 # Ownership changes atomically; old records remain as provenance, not inventory.
 server.db.execute('INSERT INTO companion_custody VALUES(?,?) ON CONFLICT(identity) DO UPDATE SET holder=excluded.holder',(identity(native),recipient))
 server.db.execute('INSERT OR IGNORE INTO character_companions VALUES(?,?,?,?,?)',(recipient,key,*native))
 member=dict(individual=key,species=mon['species'],level=mon['authored_level'])
 server.db.execute('INSERT INTO character_companion_roster VALUES(?,?,?) ON CONFLICT(actor,individual) DO UPDATE SET member=excluded.member',(recipient,key,json.dumps(member,sort_keys=True)))
 trained=current['trained']
 if trained:
  server.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?) ON CONFLICT(actor,individual) DO UPDATE SET engine=excluded.engine,authored_level=excluded.authored_level,state=excluded.state',(recipient,key,trained['engine'],trained['authored_level'],json.dumps(trained['state'],sort_keys=True)))
 return native
